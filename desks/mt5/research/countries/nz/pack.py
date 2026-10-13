"""NEW ZEALAND: a fortnightly auction for the terms of trade, and a calendar Australia's is not.

WHAT NEW ZEALAND IS AS A MARKET MECHANISM. Four things belong to this economy, and each is a
domain below rather than a line in a generic commodity-currency template:

  1. THE TERMS OF TRADE ARE DISCOVERED IN A PUBLIC AUCTION ON A KNOWN CLOCK. GlobalDairyTrade is
     a real ascending-price auction held on the first and third Tuesday of each month. It
     publishes a headline index and a whole-milk-powder price, free, to everybody, at the same
     minute. Roughly a quarter of New Zealand's goods exports reprice against that print. No
     other country in this region has its principal export price set by a dated public auction:
     Australia's ore price is an assessed index, Russia's crude is a differential to a benchmark,
     Turkey's gold import bill is a monthly customs statistic. NZ-C exists because a dated,
     public, free terms-of-trade shock is a natural experiment the desk can actually run.

  2. THE FARMGATE PRICE IS A PUBLISHED FORECAST THAT IS REVISED IN PUBLIC. Fonterra collects
     roughly 80% of New Zealand milk and publishes an opening farmgate milk price forecast in
     late May for the season beginning 1 June, then REVISES it through the season. Farmer income,
     rural credit, and a measurable share of domestic demand follow the revision rather than the
     auction. The forecast revision is therefore a second, slower, independently-dated object,
     and NZ-D tests it separately from the auction for exactly that reason.

  3. THE POLICY MANDATE ITSELF CHANGED, TWICE, INSIDE THE SAMPLE. The RBNZ ran a single price
     mandate, gained an employment objective in 2018, and had it REMOVED in December 2023. A
     reaction-function study pooled across that boundary is averaging two different central
     banks. Few economies in this book offer so clean a mandate experiment, and NZ-A is built on
     it rather than around it.

  4. THE CALENDAR IS NOT AUSTRALIA'S, AND THE DIFFERENCE IS TRADEABLE. New Zealand Mondayises
     Anzac Day under the Holidays Act; New South Wales, whose calendar the ASX follows, does not.
     Anzac Day 2026 falls on Saturday 2026-04-25, so New Zealand is closed on Monday 2026-04-27
     and the Australian market is open. Matariki, a public holiday since 2022, has its dates set
     by an Act of Parliament rather than by an astronomical formula, so it must be tabulated and
     cannot be computed. Any AUDNZD study assuming a shared Oceania calendar is measuring a
     one-sided book on those days.

WHAT IS EXECUTABLE AND WHAT IS NOT. NZDUSD, NZDJPY, AUDNZD, EURNZD, GBPNZD and four more NZD
crosses are quotable here. Everything New Zealand's mechanisms are ABOUT is not: the GDT index
and its whole-milk-powder series, NZX whole-milk-powder futures, the NZX 50 Gross index, 90-day
bank bill futures, the NZ OIS curve, New Zealand government bonds, the Fonterra farmgate forecast
and the ANZ commodity price index are all absent from `data/universe/universe.json`. Every one is
named in `TRANSMISSION_TARGETS` with the symbols its mechanism reaches, so an absent instrument
produces a transmission hypothesis and never an unfillable cell (L1.49).

THE TWO FISCAL YEARS, which catch people. The Crown's financial year ends 30 JUNE; the individual
INCOME TAX year ends 31 MARCH; and the DAIRY season runs 1 June to 31 May. Three different annual
boundaries in one small economy, and a study that picks the wrong one is measuring nothing.

THE TWO-LANE ORDER. Fisher & Paykel Healthcare, a2 Milk, Fonterra's listed fund and the gentailers
appear in this pack only as ACTORS. No share CFD appears in any instrument tuple in this file.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, timedelta
from typing import Any

# --------------------------------------------------------------------------- identity
CODE = "NZ"
NAME = "New Zealand"
REGION_COMMAND = "oceania"
REGION_DESK = "OCEANIA"
CURRENCY = "NZD"
FISCAL_YEAR_END = "06-30"  # the CROWN year; the income tax year ends 31 March, the dairy season
NATIVE_LANGUAGES: tuple[str, ...] = ("en-NZ", "mi")  # English and te reo Maori, both official

#: Fusion-quotable instruments a New Zealand mechanism can reach. No equity appears here.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "NZDUSD",                                          # the sovereign quote, median spread 0 pts
    "NZDJPY", "AUDNZD", "NZDCAD", "NZDCHF",            # the carry and Tasman crosses
    "NZDSGD", "NZDHUF", "EURNZD", "GBPNZD",            # the rest of the NZD complex
    "AUDUSD",                                          # the other half of every Tasman test
    "AUS200",                                          # the nearest equity proxy: NZX is absent
    "USDCNH", "CHINAH", "HK50",                        # China is the largest export market
    "XAUUSD",                                          # the risk/haven leg of NZ-F
    "USDX",                                            # the dollar factor every NZD cell needs
    "US500", "UST10Y",                                 # global risk and duration controls
    "USDJPY",                                          # the funding leg behind NZDJPY
)

#: Instruments this pack's mechanisms are ABOUT that the broker does not quote.
TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "GlobalDairyTrade index and the whole-milk-powder price", "venue": "GDT (auction)",
     "why": "the dated, public, free terms-of-trade shock; roughly a quarter of goods exports "
            "reprice against it on the first and third Tuesday of each month",
     "proxies": ("NZDUSD", "AUDNZD", "NZDJPY")},
    {"name": "NZX whole-milk-powder and butter futures", "venue": "NZX derivatives",
     "why": "the hedging instrument the auction feeds; open interest here is the processors' and "
            "farmers' forward cover and moves ahead of the auction",
     "proxies": ("NZDUSD", "AUDNZD")},
    {"name": "Fonterra farmgate milk price forecast", "venue": "Fonterra (co-operative)",
     "why": "a published forecast, revised in public through the season; farmer income and rural "
            "credit follow the REVISION rather than the auction print",
     "proxies": ("NZDUSD", "AUDNZD")},
    {"name": "NZX 50 Gross index", "venue": "NZX",
     "why": "the domestic equity market; small, gentailer- and healthcare-heavy, and reported as "
            "a GROSS (total return) index, so it is not comparable with a price index",
     "proxies": ("AUS200", "US500")},
    {"name": "NZX 90-day bank bill futures (BB) and the NZ OIS curve", "venue": "NZX / OTC",
     "why": "the consensus proxy for the OCR; New Zealand's answer to the Australian IB future, "
            "and the thing an RBNZ surprise must be measured against",
     "proxies": ("NZDUSD", "AUDNZD", "UST10Y")},
    {"name": "New Zealand Government Bonds and the NZDM tender calendar", "venue": "NZDM",
     "why": "weekly tenders; offshore ownership of NZGBs is high and the hedged pickup over "
            "Treasuries is what moves it",
     "proxies": ("NZDUSD", "UST10Y", "NZDJPY")},
    {"name": "ANZ commodity price index", "venue": "ANZ (public monthly)",
     "why": "the broadest free New Zealand export price index, in both world and NZD terms; the "
            "NZD-terms series is the farmer's actual income and is not the same signal",
     "proxies": ("NZDUSD", "AUDNZD")},
    {"name": "NZD trade-weighted index (RBNZ TWI)", "venue": "RBNZ",
     "why": "the Bank's own object of concern and an explicit input to its published projections; "
            "the bilateral NZDUSD is only the visible face of it",
     "proxies": ("NZDUSD", "AUDNZD", "EURNZD", "NZDJPY")},
    {"name": "Uridashi and Eurokiwi NZD bond issuance", "venue": "Tokyo / Euromarkets",
     "why": "retail Japanese and European demand for NZD coupon; issuance and MATURITY are both "
            "dated NZD flows and the maturity leg is the one nobody watches",
     "proxies": ("NZDJPY", "NZDUSD")},
    {"name": "Statistics New Zealand overseas merchandise trade and tourism arrivals",
     "venue": "Stats NZ",
     "why": "tourism was roughly a fifth of exports before 2020 and its recovery path is a "
            "separate, seasonal NZD demand",
     "proxies": ("NZDUSD", "AUDNZD")},
)

# --------------------------------------------------------------------------- the central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "Reserve Bank of New Zealand -- Te Putea Matua",
    "short": "RBNZ",
    "framework": "inflation_targeter",
    "committee": "Monetary Policy Committee (statutory since 2019, with external members)",
    "policy_instrument": "Official Cash Rate (OCR)",
    "corridor": "settlement cash is remunerated at the OCR; the standing repo facility sits above "
                "it. New Zealand pioneered full remuneration of settlement balances, which is why "
                "the OCR transmits to the overnight rate almost exactly",
    "mandate": "1-3% annual CPI inflation with a 2% midpoint. An employment objective was ADDED "
               "in 2018 and REMOVED in December 2023, returning the Bank to a single price "
               "mandate -- a reaction-function break inside the sample",
    "decision_rule": "SEVEN decisions a year. Four are full Monetary Policy Statements (February, "
                     "May, August, November) carrying a published OCR projection track; three are "
                     "Monetary Policy Reviews with a statement and no new projection. The "
                     "announcement is at 14:00 New Zealand time with a press conference and "
                     "parliamentary select committee appearance on MPS days.",
    "announce_local": "14:00 Pacific/Auckland",
    "announce_utc": "02:00",
    "announce_utc_dst": "01:00",
    "dst_rule": "Pacific/Auckland is NZST (UTC+12) from the first Sunday in April to the last "
                "Sunday in September and NZDT (UTC+13) otherwise; the announcement minute in UTC "
                "moves twice a year, and New Zealand's DST dates are NOT the same as Australia's",
    "presser_utc": "03:00",
    "minutes_lag_days": 0,
    "consensus_proxy": "the NZ OIS curve and NZX 90-day bank bill futures. NEITHER IS QUOTED ON "
                       "THIS BROKER, so unlike Australia the pre-announcement expectation must be "
                       "sourced externally or declared UNMEASURED for that meeting.",
    "consensus_proxy_trap": "the MPS publishes the Bank's OWN projected OCR track, and the market "
                            "trades the gap between that track and its own. A 'surprise' measured "
                            "against the previous TRACK is a different quantity from one measured "
                            "against the OIS curve, and the two disagree most exactly when the "
                            "meeting matters most",
    "distinctive": "the published OCR projection track is unusual: most central banks in this "
                   "pack's region publish forecasts for inflation and growth but not for their "
                   "own policy rate. The TRACK REVISION is therefore a New Zealand-specific "
                   "tradeable object that has no Australian counterpart",
    "balance_sheet_history": (
        "the Large Scale Asset Purchase programme, March 2020 to July 2021",
        "the Funding for Lending Programme, December 2020 to December 2022",
        "a bond sales (quantitative tightening) programme from July 2022"),
    "off_cycle": "the Committee cut 75bp out of cycle on 2020-03-16; an unscheduled decision is "
                 "the largest NZD event class and is never pooled with scheduled ones",
    "other_clocks": (
        {"what": "Monetary Policy Statement with the OCR projection track",
         "when_local": "14:00 Auckland, February, May, August, November", "when_utc": "02:00",
         "reference_lag_days": 0},
        {"what": "Monetary Policy Review (no new projection)",
         "when_local": "14:00 Auckland, the other three meetings", "when_utc": "02:00",
         "reference_lag_days": 0},
        {"what": "Financial Stability Report", "when_local": "09:00 Auckland, May and November",
         "when_utc": "21:00", "reference_lag_days": 0},
        {"what": "RBNZ Survey of Expectations", "when_local": "quarterly", "when_utc": "02:00",
         "reference_lag_days": 0},
    ),
    "root": "https://www.rbnz.govt.nz",
}

# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "GlobalDairyTrade trading event result publication",
     "local": "the auction runs on the first and third Tuesday of each month and results publish "
              "in the European afternoon",
     "time_utc": "15:00", "time_utc_dst": "15:00", "dst_rule": "none (the event is UTC-anchored)",
     "instruments": ("NZDUSD", "AUDNZD", "NZDJPY"), "window_minutes": 180,
     "confidence": "DECLARED, VERIFY. The auction's start minute and the publication minute are "
                   "taken here as roughly 14:00 and 15:00 UTC; the desk must confirm both against "
                   "globaldairytrade.info before an intraday event study conditions on them. A "
                   "study run on the WRONG minute measures the hour, not the auction",
     "why": "the only dated public auction of a New Zealand export price; this is the country's "
            "single cleanest terms-of-trade event"},
    {"name": "RBNZ daily exchange rates and the TWI",
     "local": "published each business day from an 11:00 Auckland observation",
     "time_utc": "23:00", "time_utc_dst": "22:00", "dst_rule": "NZST/NZDT",
     "instruments": ("NZDUSD", "AUDNZD", "EURNZD"), "window_minutes": 5,
     "confidence": "SETTLED",
     "why": "the official reference and the input to the Bank's own TWI, which is what the "
            "projections are conditioned on"},
    {"name": "WM/Refinitiv 16:00 London fix",
     "local": "16:00 Europe/London, window 15:57:30-16:02:30", "time_utc": "16:00",
     "time_utc_dst": "15:00", "dst_rule": "GMT/BST",
     "instruments": ("NZDUSD", "AUDNZD", "EURNZD", "NZDJPY"), "window_minutes": 5,
     "confidence": "SETTLED",
     "why": "where offshore index and hedging flow in NZD transacts; NZD is small enough that a "
            "fix-window imbalance is visible in the bar, which is not true of EURUSD"},
    {"name": "NZX closing auction",
     "local": "16:45-17:00 Pacific/Auckland", "time_utc": "04:45", "time_utc_dst": "03:45",
     "dst_rule": "NZST/NZDT", "instruments": (), "window_minutes": 15,
     "confidence": "SETTLED",
     "why": "sets the official NZX 50 close. The index is NOT quoted here, so this is a "
            "transmission-target clock: it matters as the first equity print of the global day"},
    {"name": "The first liquid quote of the global FX day",
     "local": "the Wellington/Auckland open", "time_utc": "20:00", "time_utc_dst": "19:00",
     "dst_rule": "NZST/NZDT", "instruments": ("NZDUSD", "AUDNZD", "NZDJPY"),
     "window_minutes": 60, "confidence": "SETTLED",
     "why": "New Zealand opens the world's trading week. Weekend news is priced HERE first, in "
            "the thinnest book of the cycle, which is why NZD gaps are the largest in the G10 and "
            "why NZ-L treats the Monday open as its own object"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "NZD spot value date", "kind": "weekday", "convention": "T+2",
     "rollover_utc": "21:00 (EST) / 22:00 (EDT), 17:00 America/New_York",
     "instruments": ("NZDUSD", "NZDJPY", "AUDNZD"),
     "why": "Wednesday carries the triple swap; NZDJPY's carry has been among the largest in the "
            "G10 and the accounting artefact is correspondingly large"},
    {"name": "GDT auction cycle", "kind": "week_of_month",
     "convention": "the first and third Tuesday of each month",
     "rollover_utc": "15:00", "instruments": ("NZDUSD", "AUDNZD"),
     "why": "a fortnightly, not monthly, clock; a monthly-anchored study misses half the events"},
    {"name": "Fonterra advance rate payments", "kind": "day_of_month",
     "convention": "monthly payments to farmers, on the 20th of the month",
     "rollover_utc": "", "instruments": ("NZDUSD",),
     "why": "the dated domestic cash leg of the dairy cycle; rural credit and spending follow it"},
    {"name": "dairy season boundary", "kind": "fiscal_year_end",
     "convention": "1 June to 31 May; the opening farmgate forecast is published in late May",
     "rollover_utc": "", "instruments": ("NZDUSD", "AUDNZD"),
     "why": "the dairy year is NEITHER of the country's two fiscal years; three annual boundaries "
            "in one economy and picking the wrong one measures nothing"},
    {"name": "Crown financial year", "kind": "fiscal_year_end", "convention": "30 June",
     "rollover_utc": "", "instruments": ("NZDUSD",),
     "why": "the Budget is delivered in May for the year beginning 1 July; the Half Year Economic "
            "and Fiscal Update lands in December"},
    {"name": "income tax year", "kind": "fiscal_year_end", "convention": "31 March",
     "rollover_utc": "", "instruments": ("NZDUSD",),
     "why": "individual and most company tax years end 31 March, so corporate repatriation and "
            "provisional tax dates cluster there and NOT at the Crown year end"},
)

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "NZX Main Board",
     "index_symbols": (),
     "open_local": "10:00 (pre-open from 09:00)", "close_local": "16:45",
     "open_utc": "22:00", "close_utc": "04:45", "dst_rule": "NZST/NZDT",
     "auction": "opening auction 09:00-10:00, closing auction 16:45-17:00",
     "expiry_rule": "NZX 20 index futures: quarterly. Equity options are thin.",
     "holidays": "the New Zealand national calendar; Auckland Anniversary Day is observed by the "
                 "exchange and is NOT a national holiday",
     "notes": "the NZX 50 is reported as a GROSS index -- total return, dividends reinvested. "
              "Comparing it with a price index like AUS200 without adjustment is a systematic "
              "upward bias of roughly the dividend yield per year"},
    {"name": "NZX Derivatives (dairy)",
     "index_symbols": (),
     "open_local": "09:00", "close_local": "18:00", "open_utc": "21:00", "close_utc": "06:00",
     "dst_rule": "NZST/NZDT", "auction": "n/a",
     "expiry_rule": "whole-milk-powder, skim-milk-powder, butter and AMF futures settle monthly "
                    "against the GDT auction result for the contract month",
     "holidays": "the New Zealand national calendar",
     "notes": "settlement AGAINST THE AUCTION is the important structural fact: it makes the GDT "
              "result a settlement price and therefore a magnet for hedging flow beforehand"},
    {"name": "ASX 24 (the venue NZD futures liquidity actually uses)",
     "index_symbols": ("AUS200",),
     "open_local": "day 09:50, night 17:10 Sydney", "close_local": "day 16:30, night 07:00",
     "open_utc": "23:50", "close_utc": "06:30", "dst_rule": "AEST/AEDT",
     "auction": "n/a", "expiry_rule": "see the Australian pack",
     "holidays": "the New South Wales calendar -- which is NOT the New Zealand calendar",
     "notes": "listed here because the calendar divergence is the point: on 2026-04-27 New "
              "Zealand is closed for the Anzac Day substitute and ASX 24 is open"},
)


# --------------------------------------------------------------------------- holidays
def _western_easter(year: int) -> date:
    """Anonymous Gregorian computus, exact for 1583-4099."""
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


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    first += timedelta(days=(weekday - first.weekday()) % 7)
    return first + timedelta(days=7 * (n - 1))


#: MATARIKI IS LEGISLATED, NOT COMPUTED. The Te Kahui o Matariki Public Holiday Act 2022 sets the
#: date for each year in a schedule; it tracks the heliacal rising of the Pleiades but it is the
#: SCHEDULE, not an astronomical formula, that is the law. A computed date would be wrong.
MATARIKI: dict[int, date] = {
    2022: date(2022, 6, 24), 2023: date(2023, 7, 14), 2024: date(2024, 6, 28),
    2025: date(2025, 6, 20), 2026: date(2026, 7, 10), 2027: date(2027, 6, 25),
    2028: date(2028, 7, 14), 2029: date(2029, 7, 6), 2030: date(2030, 6, 21),
}

#: The holidays that are MONDAYISED when they fall on a Saturday or Sunday. Waitangi Day and Anzac
#: Day were added by the Holidays (Full Recognition of Waitangi Day and ANZAC Day) Amendment Act
#: 2013, effective from 2014 -- so a pre-2014 calendar must NOT Mondayise them.
MONDAYISED: tuple[tuple[int, int, str], ...] = (
    (1, 1, "New Year's Day"),
    (1, 2, "Day after New Year's Day"),
    (2, 6, "Waitangi Day / Te Ra o Waitangi"),
    (4, 25, "Anzac Day"),
    (12, 25, "Christmas Day"),
    (12, 26, "Boxing Day"),
)

#: Regional anniversary days. NOT national, NOT observed by every employer, and Auckland
#: Anniversary IS observed by NZX. Recorded so a regional day is never mistaken for a national one.
REGIONAL_ANNIVERSARIES: tuple[dict[str, str], ...] = (
    {"region": "Auckland / Northland", "rule": "the Monday nearest 29 January",
     "market": "observed by NZX"},
    {"region": "Wellington", "rule": "the Monday nearest 22 January", "market": "not NZX"},
    {"region": "Canterbury", "rule": "the second Friday after the first Tuesday in November "
                                     "(Show Day)", "market": "not NZX"},
    {"region": "Otago / Southland", "rule": "the Monday nearest 23 March", "market": "not NZX"},
)


def _mondayise(day: date, taken: set[date]) -> date:
    """Saturday and Sunday roll to the following Monday; a pair rolls to Monday and Tuesday."""
    if day.weekday() < 5:
        return day
    moved = day + timedelta(days=(7 - day.weekday()))
    while moved in taken:
        moved += timedelta(days=1)
    return moved


def national_holidays(year: int) -> dict[date, str]:
    """New Zealand's eleven national public holidays for `year`, computed from the Holidays Act
    rules plus the legislated Matariki schedule.

    Mondayisation applies to New Year's Day, 2 January, Waitangi Day, Anzac Day, Christmas Day
    and Boxing Day. It does NOT apply to Matariki, King's Birthday or Labour Day, which are
    already defined as Mondays or as a legislated Friday.
    """
    out: dict[date, str] = {}
    easter = _western_easter(year)
    out[easter - timedelta(days=2)] = "Good Friday"
    out[easter + timedelta(days=1)] = "Easter Monday"
    out[_nth_weekday(year, 6, 0, 1)] = "King's Birthday"
    out[_nth_weekday(year, 10, 0, 4)] = "Labour Day"
    matariki = MATARIKI.get(year)
    if matariki is not None:
        out[matariki] = "Matariki"
    taken: set[date] = set(out)
    for month, day, label in MONDAYISED:
        actual = date(year, month, day)
        observed = _mondayise(actual, taken)
        taken.add(observed)
        out[observed] = label if observed == actual else f"{label} (Mondayised)"
    return dict(sorted(out.items()))


def market_holidays(year: int) -> dict[date, str]:
    """The days the New Zealand market is CLOSED: the national set plus Auckland Anniversary Day,
    which NZX observes and which is not a national holiday."""
    out = dict(national_holidays(year))
    out[auckland_anniversary(year)] = "Auckland Anniversary Day (NZX)"
    return dict(sorted(out.items()))


def auckland_anniversary(year: int) -> date:
    """The Monday nearest 29 January."""
    anchor = date(year, 1, 29)
    offset = anchor.weekday()
    return anchor - timedelta(days=offset) if offset <= 3 else anchor + timedelta(days=7 - offset)


def gdt_events(year: int) -> dict[date, str]:
    """GlobalDairyTrade trading events: the first and third Tuesday of each month.

    DECLARED RULE. GDT has published variations -- a reduced schedule in some months and
    occasional additional events -- so this is the RULE the desk conditions on and the published
    event list is the authority. A miner must reconcile the two and report any date the rule
    produced that the auction did not hold, rather than assuming the rule is the calendar.
    """
    out: dict[date, str] = {}
    for month in range(1, 13):
        for n in (1, 3):
            out[_nth_weekday(year, month, 1, n)] = f"GDT trading event {year}-{month:02d} #{n}"
    return dict(sorted(out.items()))


def is_market_holiday(day: date) -> bool:
    return day in market_holidays(day.year)


def tasman_calendar_divergence(year: int) -> dict[date, str]:
    """Days in `year` where New Zealand is closed and the Australian market is not, or the
    reverse. This is the object NZ-E cares about and the one an AUDNZD study most often misses.

    The Australian side is approximated by the New South Wales rule (the ASX calendar): New Year,
    Australia Day, Good Friday, Easter Monday, Anzac Day, second Monday of June, first Monday of
    October, Christmas and Boxing Day, with Mondayisation for everything EXCEPT Anzac Day.
    """
    nz = market_holidays(year)
    easter = _western_easter(year)
    au: dict[date, str] = {
        easter - timedelta(days=2): "Good Friday",
        easter + timedelta(days=1): "Easter Monday",
        _nth_weekday(year, 6, 0, 2): "King's Birthday (NSW)",
        _nth_weekday(year, 10, 0, 1): "Labour Day (NSW)",
    }
    for month, day, label in ((1, 1, "New Year's Day"), (1, 26, "Australia Day"),
                              (4, 25, "Anzac Day"), (12, 25, "Christmas Day"),
                              (12, 26, "Boxing Day")):
        actual = date(year, month, day)
        au[actual] = label
        if label == "Anzac Day" or actual.weekday() < 5:
            continue
        moved = actual + timedelta(days=(7 - actual.weekday()))
        while moved in au:
            moved += timedelta(days=1)
        au[moved] = f"{label} (observed)"
    out: dict[date, str] = {}
    for day, label in nz.items():
        if day not in au and day.weekday() < 5:
            out[day] = f"NZ closed ({label}), Australia open"
    for day, label in au.items():
        if day not in nz and day.weekday() < 5:
            out[day] = f"Australia closed ({label}), NZ open"
    return dict(sorted(out.items()))


HOLIDAYS_RULE: dict[str, Any] = {
    "kind": "computed_from_rules_plus_legislated_table",
    "authority": "Holidays Act 2003 as amended; the Holidays (Full Recognition of Waitangi Day "
                 "and ANZAC Day) Amendment Act 2013; Te Kahui o Matariki Public Holiday Act 2022",
    "years": (2024, 2025, 2026),
    "weekend": "Saturday and Sunday",
    "mondayisation_rule": "New Year's Day, 2 January, Waitangi Day, Anzac Day, Christmas Day and "
                          "Boxing Day roll to the following Monday (and Tuesday, for the second "
                          "of a pair) when they fall on a weekend. Waitangi and Anzac have been "
                          "Mondayised only since 2014; a pre-2014 calendar must not apply it.",
    "matariki_rule": "LEGISLATED, NOT COMPUTED. The Act sets each year's date in a schedule; it "
                     "tracks the heliacal rising of the Pleiades but the schedule is the law, so "
                     "the date is tabulated and a computed date would be wrong",
    "regional_rule": "anniversary days are REGIONAL and differ by province; NZX observes Auckland "
                     "Anniversary Day, which is not a national holiday",
    "known_dates": {
        "2024-06-28": "Matariki (legislated)",
        "2025-06-20": "Matariki (legislated)",
        "2026-07-10": "Matariki (legislated)",
        "2026-04-25": "Anzac Day, SATURDAY",
        "2026-04-27": "Anzac Day Mondayised -- New Zealand is CLOSED. New South Wales does not "
                      "substitute, so the Australian market is OPEN the same day. This is the "
                      "Tasman calendar divergence AUDNZD studies miss",
        "2026-12-28": "Boxing Day Mondayised (26 December 2026 is a Saturday)",
    },
    "fn": market_holidays,
    "national_fn": national_holidays,
    "divergence_fn": tasman_calendar_divergence,
    "gdt_fn": gdt_events,
    "matariki": MATARIKI,
    "regional": REGIONAL_ANNIVERSARIES,
}

# --------------------------------------------------------------------------- positioning
COT_CURRENCY = "NZD"
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "CFTC Commitments of Traders -- CME New Zealand dollar futures (6N, code 112741)",
     "root": "https://www.cftc.gov/MarketReports/CommitmentsofTraders/",
     "fields": ("non_commercial_long", "non_commercial_short", "commercial_long",
                "commercial_short", "leveraged_funds_net", "open_interest"),
     "frequency": "weekly", "snapshot": "Tuesday close",
     "publish_utc": "19:30 (EDT) / 20:30 (EST), Friday", "lag_days": 3,
     "licence": "free, public (US government work)", "available": True,
     "why": "NZD is a small currency with a large speculative share of open interest, so COT "
            "extremes are a bigger fraction of the float here than in AUD",
     "pit_warning": "three days stale on release. The NZD contract is also SMALL -- weeks with "
                    "few reportable traders produce a noisy net that looks like a signal; the "
                    "trader COUNT must be read alongside the position"},
    {"name": "CME 6N daily volume and open interest",
     "root": "https://www.cmegroup.com/markets/fx/g10/new-zealand-dollar.volume.html",
     "fields": ("volume", "open_interest"), "frequency": "daily", "snapshot": "session close",
     "publish_utc": "12:00", "lag_days": 1, "licence": "free, public", "available": True,
     "why": "the fast complement to the weekly COT",
     "pit_warning": "preliminary OI is restated the next morning"},
    {"name": "NZX dairy futures open interest",
     "root": "https://www.nzx.com/markets/nzx-derivatives",
     "fields": ("contract", "open_interest", "volume"), "frequency": "daily",
     "snapshot": "session close", "publish_utc": "06:30", "lag_days": 1,
     "licence": "free headline", "available": True,
     "why": "the processors' and farmers' forward cover; it moves AHEAD of the auction and is "
            "therefore the only forward-looking dairy positioning series that exists",
     "pit_warning": "thin; a single large hedger dominates the series and the level is not "
                    "comparable across years as the contract's liquidity grew"},
    {"name": "RBNZ foreign exchange intervention capacity and transactions",
     "root": "https://www.rbnz.govt.nz/statistics", "fields": ("net_transactions", "capacity"),
     "frequency": "monthly", "snapshot": "calendar month", "publish_utc": "21:00",
     "lag_days": 25, "licence": "free, public", "available": True,
     "why": "the Bank has intervened rarely (notably 2007-2008) but publishes capacity and "
            "transactions, so the actor's own ledger is checkable",
     "pit_warning": "weeks of lag; never a same-month conditioner"},
    {"name": "a New Zealand-venue trader-category positioning report",
     "root": "", "fields": (), "frequency": "n/a", "snapshot": "", "publish_utc": "",
     "lag_days": 0, "licence": "", "available": False,
     "why": "none exists",
     "pit_warning": "DOES NOT EXIST. Domestic NZD positioning is UNMEASURED; the CME series is a "
                    "different book with different participants and different hours, and using it "
                    "as a domestic proxy must be declared rather than assumed"},
)

# --------------------------------------------------------------------------- terminology
#: English and te reo Maori are both official. The te reo terms are not decoration: the Bank
#: publishes under its Maori name, the Matariki holiday is legislated under one, and a text screen
#: that does not carry them will miss the primary source's own headline.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "NZ-A": ("the OCR", "Official Cash Rate", "Te Putea Matua", "the MPS", "the MPR",
             "the OCR track", "the remit", "Monetary Policy Committee"),
    "NZ-B": ("the projection track", "the forecast track", "the Survey of Expectations",
             "unconstrained OCR"),
    "NZ-C": ("GDT", "the auction", "whole milk powder", "WMP", "the GDT index", "trading event"),
    "NZ-D": ("the farmgate price", "the milk price", "the payout", "the advance rate",
             "Fonterra", "the season", "kaimahi"),
    "NZ-E": ("the cross", "the Tasman", "across the ditch", "relative carry", "the OCR gap"),
    "NZ-F": ("the carry", "the kiwi", "the bird", "risk-off", "uridashi", "eurokiwi"),
    "NZ-G": ("the NZX", "the gross index", "the closing auction", "Aotearoa"),
    "NZ-H": ("terms of trade", "the ANZ commodity price index", "the world price",
             "the NZD price"),
    "NZ-I": ("manuhiri", "visitor arrivals", "the shoulder season", "tourism exports"),
    "NZ-J": ("the labour market survey", "HLFS", "the CPI", "the QSBO", "the ANZ survey"),
    "NZ-K": ("NZDM", "the tender", "NZGB", "the linker", "the spread to Treasuries"),
    "NZ-L": ("the Monday open", "the gap", "the handover", "first to open"),
    "NZ-M": ("Matariki", "Te Kahui o Matariki", "Waitangi Day", "Te Ra o Waitangi",
             "Anzac Day", "Mondayisation"),
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

    `machine_use_allowed=True` registers a source whose terms forbid machine extraction. It is
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


#: NEW ZEALAND'S TEN LAYERS. English and te reo Maori are both official, and the te reo terms are
#: not decoration: the Bank publishes under its Maori name, Matariki is legislated under one, and
#: a screen that does not carry them will miss the primary source's own headline. The English
#: `queries` are New Zealand vocabulary, not translations -- "the payout" is a farmgate milk
#: price, "the bird" is the currency, and "fixing" is a mortgage decision rather than a benchmark.
SOURCE_CLASSES: tuple[dict[str, Any], ...] = (
    source_class(
        "nz_rbnz", "Reserve Bank of New Zealand primary publications", layer="official",
        roots=("https://www.rbnz.govt.nz/monetary-policy/official-cash-rate-decisions",
               "https://www.rbnz.govt.nz/monetary-policy/monetary-policy-statement",
               "https://www.rbnz.govt.nz/statistics"),
        queries=("Official Cash Rate", "OCR decision", "Monetary Policy Statement",
                 "Monetary Policy Review", "OCR track", "unconstrained OCR", "the remit",
                 "Te Putea Matua", "Survey of Expectations", "Financial Stability Report"),
        languages=("en", "mi"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public (CC BY)",
        notes="the PROJECTION TRACK is a downloadable table and every vintage must be kept, "
              "because the REVISION is NZ-B's object and the level is not"),
    source_class(
        "nz_stats", "Statistics New Zealand", layer="official",
        roots=("https://www.stats.govt.nz/release-calendar",
               "https://www.stats.govt.nz/topics/economic-indicators"),
        queries=("consumers price index", "tradables", "non-tradables",
                 "household labour force survey", "HLFS", "labour cost index",
                 "overseas merchandise trade", "international travel", "release calendar"),
        languages=("en", "mi"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="Creative Commons BY 4.0",
        notes="the 10:45 Auckland embargo falls on the PREVIOUS UTC DAY, a classic off-by-one; "
              "and New Zealand has no monthly CPI or employment print, so each quarterly release "
              "carries three months of news"),
    source_class(
        "nz_treasury", "New Zealand Debt Management and the Treasury", layer="official",
        roots=("https://debtmanagement.treasury.govt.nz/",
               "https://www.treasury.govt.nz/publications"),
        queries=("tender results", "NZGB", "inflation-indexed bond", "borrowing programme",
                 "Budget Economic and Fiscal Update", "HYEFU", "syndication"),
        languages=("en",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="a small bond market with a high offshore share, so a modest global reallocation is "
              "a large domestic flow -- the asymmetry NZ-K is built on"),
    source_class(
        "nz_cftc", "CFTC Commitments of Traders, New Zealand dollar futures", layer="official",
        roots=("https://www.cftc.gov/MarketReports/CommitmentsofTraders/",),
        queries=("New Zealand dollar futures", "Commitments of Traders", "non-commercial net",
                 "leveraged funds", "number of traders"),
        languages=("en",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public (US government work)",
        notes="the 6N contract is SMALL: weeks with few reportable traders give a net position "
              "that is noise, so the trader COUNT must be read alongside the position"),
    source_class(
        "nz_nzx", "NZX cash market and dairy derivatives", layer="institutional",
        roots=("https://www.nzx.com/markets", "https://www.nzx.com/markets/nzx-derivatives"),
        queries=("NZX 50 Gross", "closing auction", "whole milk powder futures", "WMP futures",
                 "butter futures", "open interest", "settlement against the auction"),
        languages=("en",), access_label="PUBLIC_WITH_TERMS", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free end-of-day; depth licensed",
        notes="the dairy futures settle AGAINST THE GDT AUCTION, which makes the auction result a "
              "settlement price and therefore a magnet for hedging flow beforehand -- the reason "
              "NZ-C can build an expectation at all. The NZX 50 is a GROSS index"),
    source_class(
        "nz_gdt", "GlobalDairyTrade, the auction operator", layer="institutional",
        roots=("https://www.globaldairytrade.info/en/product-results/",
               "https://www.globaldairytrade.info/en/trading-events/"),
        queries=("trading event", "GDT index", "whole milk powder", "WMP", "skim milk powder",
                 "anhydrous milk fat", "winning bidders", "forward offer volumes"),
        languages=("en",), access_label="PUBLIC_WITH_TERMS", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free headline results; full event data LICENSED",
        notes="THE PACK'S FLAGSHIP GROUND: a real ascending-price auction of the country's "
              "principal export, on a published fortnightly clock. Round-level bidding dynamics "
              "are behind the licence and are declared UNMEASURED rather than approximated"),
    source_class(
        "nz_multilateral", "IMF, OECD and BIS New Zealand coverage", layer="institutional",
        roots=("https://www.imf.org/en/Countries/NZL", "https://data.oecd.org/",
               "https://www.bis.org/statistics/"),
        queries=("Article IV", "external position", "FX turnover", "triennial survey",
                 "housing and financial stability"),
        languages=("en",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the international comparison NZ-E needs to say whether a Tasman result is an "
              "Oceania fact or a small-open-economy fact"),
    source_class(
        "nz_rbnz_research", "RBNZ Analytical Notes and Discussion Papers", layer="academic",
        roots=("https://www.rbnz.govt.nz/hub/publications/analytical-note",
               "https://www.rbnz.govt.nz/hub/publications/discussion-paper"),
        queries=("analytical note", "discussion paper", "OCR track", "forecast performance",
                 "exchange rate pass-through", "dairy terms of trade", "monetary transmission"),
        languages=("en",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the Bank publishes assessments of ITS OWN forecast track record, which is the "
              "rarest kind of document in this department and is the direct evidence NZ-B needs"),
    source_class(
        "nz_academic", "Motu, the universities and the working-paper repositories",
        layer="academic",
        roots=("https://motu.nz/our-research/", "https://papers.ssrn.com/",
               "https://ideas.repec.org/"),
        queries=("dairy price transmission", "commodity currency New Zealand",
                 "Mondayisation", "public holiday effect", "small open economy",
                 "agricultural price volatility"),
        languages=("en",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="per-paper",
        notes="Motu is New Zealand's main independent economic research institute and publishes "
              "the agricultural and climate work nobody else does"),
    source_class(
        "nz_interest", "interest.co.nz", layer="practitioner",
        roots=("https://www.interest.co.nz/", "https://www.interest.co.nz/rural-news"),
        queries=("OCR call", "swap rates", "term deposit rates", "mortgage rates",
                 "the payout", "farmgate milk price", "GDT auction result", "carded rates"),
        languages=("en",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", machine_use_allowed=True,
        licence="public web; terms restrict automated extraction",
        notes="the best free rates-and-dairy analysis in the country and the closest thing New "
              "Zealand has to a public swap-curve record. READ AND CITED, NEVER SCRAPED"),
    source_class(
        "nz_bank_economics", "ANZ, BNZ, Westpac NZ and Kiwibank published economics",
        layer="practitioner",
        roots=("https://www.anz.co.nz/about-us/economic-markets-research/",
               "https://www.bnz.co.nz/business-banking/research",
               "https://www.kiwibank.co.nz/business-banking/news-and-insights/"),
        queries=("ANZ commodity price index", "world price index", "NZD price index",
                 "business outlook survey", "OCR preview", "dairy forecast", "house view"),
        languages=("en",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", machine_use_allowed=True,
        licence="public web; redistribution restricted",
        notes="ANZ publishes the broadest FREE New Zealand export price index, in both world and "
              "NZD terms. The NZD-terms series already contains the exchange rate and regressing "
              "NZD on it is partly regressing the currency on itself -- NZ-H's circularity check"),
    source_class(
        "nz_fonterra_dairynz", "Fonterra investor materials and DairyNZ", layer="practitioner",
        roots=("https://www.fonterra.com/nz/en/investors.html",
               "https://www.dairynz.co.nz/business/dairy-industry-statistics/"),
        queries=("farmgate milk price", "opening forecast", "advance rate", "milk price manual",
                 "kgMS", "the season", "collections", "payout range"),
        languages=("en",), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the forecast is the SLOW leg and the auction is the FAST one; NZ-D's interesting "
              "cell is the divergence between them, not either alone"),
    source_class(
        "nz_reddit", "Reddit r/PersonalFinanceNZ and r/newzealand finance threads",
        layer="retail_ecology",
        roots=("https://www.reddit.com/r/PersonalFinanceNZ/",
               "https://www.reddit.com/r/newzealand/"),
        queries=("KiwiSaver", "which fund", "switching to conservative", "Sharesies",
                 "fixing for how long", "breaking a fix", "term deposit", "the OCR call"),
        languages=("en",), access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="public social; API terms govern automated access",
        notes="KiwiSaver switching is a real flow into and out of offshore equities and this is "
              "where it is discussed before it shows up in a quarterly statistic; low weight, "
              "never zero"),
    source_class(
        "nz_comment_threads", "interest.co.nz and Stuff comment threads", layer="retail_ecology",
        roots=("https://www.interest.co.nz/comments", "https://www.stuff.co.nz/business"),
        queries=("the payout", "farm debt", "rural lending", "the ponzi", "house prices",
                 "the OCR is too high", "the Reserve Bank has lost it"),
        languages=("en",), access_label="PUBLIC_SOCIAL", credibility="FRINGE",
        predictive_state="NARRATIVE_FEATURE", machine_use_allowed=True,
        licence="public comment sections; automated extraction restricted",
        notes="interest.co.nz's comment threads are unusually substantive and unusually "
              "opinionated; KEPT AS A LOW-WEIGHT EVIDENCE OBJECT because rural credit stress is "
              "described here months before it appears in a lending statistic"),
    source_class(
        "nz_farmer_forums", "Farmers Weekly, Rural News and the dairy-farmer boards",
        layer="retail_ecology",
        roots=("https://www.farmersweekly.co.nz/", "https://www.ruralnewsgroup.co.nz/"),
        queries=("payout", "kgMS", "the season", "grass growth", "drying off", "culling",
                 "winter milk", "shed", "sharemilker"),
        languages=("en",), access_label="PUBLIC", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the people who produce the country's main export describing their season in real "
              "time. Drying off early is a supply signal months ahead of any statistic, and it is "
              "reported here and nowhere official"),
    source_class(
        "nz_investing_apps", "Sharesies, Hatch, InvestNow and Kernel", layer="app_ecosystem",
        roots=("https://www.sharesies.nz/", "https://www.hatchinvest.nz/",
               "https://kernelwealth.co.nz/"),
        queries=("Sharesies", "Hatch", "InvestNow", "Kernel", "fractional shares",
                 "KiwiSaver provider", "fund switch", "auto-invest"),
        languages=("en",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", machine_use_allowed=True,
        licence="public marketing pages; account data is PRIVATE and is never sought",
        notes="New Zealand retail reaches offshore equities almost entirely through these "
              "platforms, so their product menus ARE the retail opportunity set. NO "
              "ACCOUNT-LEVEL DATA is sought; that would be PRIVATE and is out of bounds"),
    source_class(
        "nz_mql5", "MQL5 Market and CodeBase for NZD pairs", layer="app_ecosystem",
        roots=("https://www.mql5.com/en/market", "https://www.mql5.com/en/code"),
        queries=("expert advisor", "EA", "MQL5", "strategy tester", "NZDUSD scalper",
                 "NZDJPY carry EA", "AUDNZD mean reversion", "grid", "martingale",
                 "swap arbitrage"),
        languages=("en",), access_label="PUBLIC_WITH_TERMS", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="public with terms",
        notes="AUDNZD mean-reversion and NZDJPY carry robots are the two most common NZD ideas "
              "in this ecosystem; both are mechanism claims with an implementation, which is "
              "more testable than prose, and both are almost always curve-fitted"),
    source_class(
        "nz_tradingview", "TradingView scripts and ideas on NZD pairs", layer="app_ecosystem",
        roots=("https://www.tradingview.com/symbols/NZDUSD/",
               "https://www.tradingview.com/symbols/AUDNZD/"),
        queries=("Pine Script", "NZDUSD idea", "AUDNZD range", "kiwi", "carry", "session range"),
        languages=("en",), access_label="PUBLIC_WITH_TERMS", credibility="UNRELIABLE",
        predictive_state="UNTESTED", machine_use_allowed=True,
        licence="public with terms; automated extraction restricted",
        notes="registered and read, never scraped"),
    source_class(
        "nz_press", "NZ Herald, RNZ, Stuff and BusinessDesk", layer="media",
        roots=("https://www.nzherald.co.nz/business/", "https://www.rnz.co.nz/news/business",
               "https://businessdesk.co.nz/"),
        queries=("OCR decision", "dairy auction", "the payout", "Fonterra", "Reserve Bank",
                 "mortgage rates", "market close"),
        languages=("en", "mi"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", machine_use_allowed=True,
        licence="RNZ is free and open; the Herald and BusinessDesk are paywalled with terms "
                "that restrict automated extraction",
        notes="RNZ is the free, dated, machine-readable half; the paywalled half is read and "
              "cited, never scraped"),
    source_class(
        "nz_rural_press", "Farmers Weekly and the rural trade press as a media layer",
        layer="media",
        roots=("https://www.farmersweekly.co.nz/", "https://www.nzfarmlife.co.nz/"),
        queries=("GDT result", "payout forecast", "milk collections", "drought declaration",
                 "feed prices", "schedule price", "lamb schedule"),
        languages=("en",), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the dairy trade press covers the GDT result and the payout with more precision "
              "than the general press, and it reports drought and feed conditions weeks before "
              "any official statistic"),
    source_class(
        "nz_papers_past", "Papers Past, the National Library of New Zealand", layer="archive",
        roots=("https://paperspast.natlib.govt.nz/",),
        queries=("historical newspaper", "butterfat", "dairy board", "wool", "devaluation",
                 "Muldoon", "the freeze"),
        languages=("en", "mi"), access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="New Zealand's export-price history is long and its policy history is unusually "
              "interventionist; the contemporaneous record is the only way to read an era on its "
              "own terms rather than on hindsight's"),
    source_class(
        "nz_wayback", "Internet Archive captures of RBNZ, Stats NZ and GDT pages",
        layer="archive",
        roots=("https://web.archive.org/web/*/rbnz.govt.nz*",
               "https://web.archive.org/web/*/globaldairytrade.info*"),
        queries=("first print", "superseded", "revised in place", "OCR track vintage",
                 "auction result archive"),
        languages=("en",), access_label="PUBLIC_ARCHIVE", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the GDT site reorganises its result pages and the Wayback capture is sometimes "
              "the only surviving record of an older event's published form -- which matters "
              "because the event NUMBER, not the date, is the stable key"),
    source_class(
        "nz_niwa", "NIWA climate, soil moisture and drought monitoring", layer="physical_economy",
        roots=("https://niwa.co.nz/climate/", "https://niwa.co.nz/climate/nz-drought-monitor"),
        queries=("soil moisture deficit", "drought monitor", "hotspot", "rainfall anomaly",
                 "La Nina", "El Nino", "pasture growth"),
        languages=("en",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="PASTURE IS THE PRODUCTION FUNCTION. New Zealand milk comes off grass, so soil "
              "moisture is the supply-side instrument for the country's principal export -- and "
              "weather is exogenous, which is why it is the cleanest instrument available"),
    source_class(
        "nz_hydro_power", "Transpower, the electricity market and hydro lake levels",
        layer="physical_economy",
        roots=("https://www.transpower.co.nz/system-operator/live-system-and-market-data",
               "https://www.emi.ea.govt.nz/"),
        queries=("hydro storage", "lake levels", "controlled storage", "spot price",
                 "Tiwai", "smelter", "dry year", "security of supply"),
        languages=("en",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="a hydro-dominated grid with ONE aluminium smelter taking a large share of national "
              "electricity. Lake levels are a published physical constraint on industrial output "
              "and on the country's second-largest manufactured export"),
    source_class(
        "nz_ports_mpi", "Port of Tauranga throughput and the MPI primary-industries outlook",
        layer="physical_economy",
        roots=("https://www.port-tauranga.co.nz/investor-centre/",
               "https://www.mpi.govt.nz/resources-and-forms/economic-intelligence/"),
        queries=("throughput", "TEU", "log exports", "dairy exports", "Situation and Outlook",
                 "SOPI", "export volumes", "kiwifruit"),
        languages=("en",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="log exports to China are a single-country exposure now larger than dairy's, and "
              "the port is where they are counted"),
    source_class(
        "nz_citation_graph", "RePEc, OpenAlex and Semantic Scholar citation graphs",
        layer="source_graph",
        roots=("https://ideas.repec.org/", "https://openalex.org/"),
        queries=("cited by", "replication", "dairy price transmission", "commodity currency",
                 "who cites whom"),
        languages=("en",), access_label="OPEN_DATA", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the New Zealand commodity-currency literature is small enough that the citation "
              "graph reveals immediately whether a claim has been replicated or merely repeated"),
    source_class(
        "nz_desk_registry", "The desk's own source registry and coverage map",
        layer="source_graph",
        roots=("desks/mt5/data/data_universe_map.json",
               "desks/mt5/data/deep_forest_sources.json"),
        queries=("coverage map", "source registry", "already mined", "duplicate ground"),
        languages=("en",), access_label="PRIVATE", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="desk-owned",
        notes="how a new source is recognised as new rather than as a copy of one already mined"),
    source_class(
        "nz_code_graph", "GitHub and package graphs for New Zealand market code",
        layer="source_graph",
        roots=("https://github.com/search?q=nzx+data", "https://github.com/search?q=rbnz"),
        queries=("nzx data", "rbnz api", "gdt scraper", "fork", "dependency"),
        languages=("en",), access_label="PUBLIC_WITH_TERMS", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="per-repository; check each, never vendor code",
        notes="the existence of a GDT scraper in public code is itself information about which "
              "series practitioners consider worth automating"),
)

#: All ten layers are populated. New Zealand is a small country with an unusually open data
#: culture -- an auction, a climate service, a grid operator and a national newspaper archive all
#: published free -- so a thin pack here would have been a statement about the reader.
LAYER_ABSENCES: dict[str, str] = {}

# --------------------------------------------------------------------------- datasets
DATASETS: tuple[dict[str, Any], ...] = (
    {"name": "RBNZ Official Cash Rate decisions", "source": "RBNZ", "coverage": "1999 onward",
     "frequency": "7 per year", "publication_lag_days": 0.0, "revisions": "never revised",
     "licence": "free, public", "history_from": "1999-03", "pit_feasible": True,
     "assets": ("NZDUSD", "AUDNZD", "NZDJPY"),
     "fields": ("decision_date", "ocr_pct", "change_bp", "mps_flag", "statement_text"),
     "pit_fields": ("release_ts_utc", "mps_flag", "scheduled_flag"),
     "mechanism_families": ("event_reaction", "policy_surprise"),
     "how_to_fetch": "rbnz.govt.nz OCR decisions index; 14:00 Auckland is the event minute"},
    {"name": "RBNZ published OCR projection track", "source": "RBNZ Monetary Policy Statement",
     "coverage": "1999 onward", "frequency": "quarterly", "publication_lag_days": 0.0,
     "revisions": "each MPS supersedes the last; THE REVISION IS THE DATUM",
     "licence": "free, public", "history_from": "1999-03", "pit_feasible": True,
     "assets": ("NZDUSD", "AUDNZD", "UST10Y"),
     "fields": ("mps_date", "quarter", "projected_ocr", "cpi_forecast", "gdp_forecast",
                "twi_assumption"),
     "pit_fields": ("release_ts_utc", "vintage", "prior_vintage_ref"),
     "mechanism_families": ("forecast_revision", "policy_surprise"),
     "how_to_fetch": "the MPS data file accompanying each statement; keep every vintage"},
    {"name": "GlobalDairyTrade auction results", "source": "GDT", "coverage": "2008 onward",
     "frequency": "fortnightly", "publication_lag_days": 0.0, "revisions": "never revised",
     "licence": "free headline; full event data licensed", "history_from": "2008-07",
     "pit_feasible": True, "assets": ("NZDUSD", "AUDNZD", "NZDJPY"),
     "fields": ("event_date", "gdt_index_change_pct", "wmp_price_usd", "smp_price_usd",
                "butter_price_usd", "volume_sold_tonnes", "winning_bidders"),
     "pit_fields": ("publish_ts_utc", "event_number"),
     "mechanism_families": ("event_reaction", "terms_of_trade"),
     "how_to_fetch": "globaldairytrade.info product results; the event NUMBER is the stable key, "
                     "not the date, because the schedule has varied"},
    {"name": "Fonterra farmgate milk price forecast", "source": "Fonterra",
     "coverage": "2009 onward", "frequency": "irregular, several revisions per season",
     "publication_lag_days": 0.0, "revisions": "revised in public through the season",
     "licence": "free, public", "history_from": "2009-06", "pit_feasible": True,
     "assets": ("NZDUSD", "AUDNZD"),
     "fields": ("announcement_date", "season", "midpoint_nzd_per_kgms", "range_low", "range_high"),
     "pit_fields": ("announcement_ts_utc", "prior_midpoint"),
     "mechanism_families": ("forecast_revision", "corporate_flow"),
     "how_to_fetch": "Fonterra investor announcements; the opening forecast lands in late May"},
    {"name": "Stats NZ Consumers Price Index", "source": "Statistics New Zealand",
     "coverage": "1914 onward", "frequency": "quarterly", "publication_lag_days": 18.0,
     "revisions": "headline not revised; the index is rebased periodically",
     "licence": "free, public (CC BY 4.0)", "history_from": "1914-01", "pit_feasible": True,
     "assets": ("NZDUSD", "AUDNZD"),
     "fields": ("reference_quarter", "cpi_qoq", "cpi_yoy", "tradables", "non_tradables"),
     "pit_fields": ("release_ts_utc", "vintage"),
     "mechanism_families": ("event_reaction",),
     "how_to_fetch": "stats.govt.nz; 10:45 Auckland embargo = 22:45 UTC the previous day in NZST"},
    {"name": "Household Labour Force Survey", "source": "Statistics New Zealand",
     "coverage": "1986 onward", "frequency": "quarterly", "publication_lag_days": 35.0,
     "revisions": "REVISED; seasonal factors re-estimated", "licence": "free, public",
     "history_from": "1986-03", "pit_feasible": True, "assets": ("NZDUSD", "AUDNZD"),
     "fields": ("reference_quarter", "unemployment_rate", "employment_change",
                "participation_rate", "labour_cost_index"),
     "pit_fields": ("release_ts_utc", "vintage"),
     "mechanism_families": ("event_reaction",),
     "how_to_fetch": "stats.govt.nz; quarterly, not monthly -- New Zealand has no monthly "
                     "employment print, which makes each one larger"},
    {"name": "Overseas Merchandise Trade", "source": "Statistics New Zealand",
     "coverage": "1960 onward", "frequency": "monthly", "publication_lag_days": 25.0,
     "revisions": "revised", "licence": "free, public", "history_from": "1960-01",
     "pit_feasible": True, "assets": ("NZDUSD",),
     "fields": ("reference_month", "exports_total", "exports_dairy", "exports_meat",
                "exports_forestry", "imports_total", "balance", "china_share"),
     "pit_fields": ("release_ts_utc", "vintage"),
     "mechanism_families": ("terms_of_trade", "macro_condition"),
     "how_to_fetch": "stats.govt.nz overseas merchandise trade"},
    {"name": "ANZ Commodity Price Index", "source": "ANZ Bank New Zealand",
     "coverage": "1986 onward", "frequency": "monthly", "publication_lag_days": 3.0,
     "revisions": "rarely revised", "licence": "free, public", "history_from": "1986-01",
     "pit_feasible": True, "assets": ("NZDUSD", "AUDNZD"),
     "fields": ("month", "world_price_index", "nzd_price_index", "dairy", "meat", "forestry"),
     "pit_fields": ("publish_ts_utc",),
     "mechanism_families": ("terms_of_trade",),
     "how_to_fetch": "anz.co.nz economic research; the WORLD and NZD series are different "
                     "signals -- the NZD one already contains the exchange rate, so regressing "
                     "NZDUSD on it is partly regressing the currency on itself"},
    {"name": "International Visitor Arrivals", "source": "Statistics New Zealand",
     "coverage": "1980 onward", "frequency": "monthly", "publication_lag_days": 25.0,
     "revisions": "revised", "licence": "free, public", "history_from": "1980-01",
     "pit_feasible": True, "assets": ("NZDUSD",),
     "fields": ("reference_month", "arrivals_total", "arrivals_australia", "arrivals_china",
                "arrivals_usa", "average_stay"),
     "pit_fields": ("release_ts_utc", "vintage"),
     "mechanism_families": ("macro_condition",),
     "how_to_fetch": "stats.govt.nz international travel"},
    {"name": "New Zealand Debt Management tender results", "source": "NZDM (The Treasury)",
     "coverage": "2000 onward", "frequency": "weekly", "publication_lag_days": 0.0,
     "revisions": "final", "licence": "free, public", "history_from": "2000-01",
     "pit_feasible": True, "assets": ("NZDUSD", "UST10Y"),
     "fields": ("tender_date", "bond", "amount_offered", "amount_allotted", "coverage_ratio",
                "weighted_average_yield"),
     "pit_fields": ("result_ts_utc",),
     "mechanism_families": ("institutional_flow", "supply_shock"),
     "how_to_fetch": "debtmanagement.treasury.govt.nz tender results"},
    {"name": "RBNZ trade-weighted index and daily exchange rates", "source": "RBNZ",
     "coverage": "1985 onward", "frequency": "daily", "publication_lag_days": 1.0,
     "revisions": "not revised", "licence": "free, public", "history_from": "1985-03",
     "pit_feasible": True, "assets": ("NZDUSD", "AUDNZD", "EURNZD"),
     "fields": ("date", "twi", "nzd_usd", "nzd_aud", "nzd_jpy"),
     "pit_fields": ("publish_ts_utc",),
     "mechanism_families": ("macro_condition",),
     "how_to_fetch": "rbnz.govt.nz statistics B1/B2 tables"},
    {"name": "NZX dairy derivatives settlements and open interest", "source": "NZX",
     "coverage": "2010 onward", "frequency": "daily", "publication_lag_days": 1.0,
     "revisions": "final", "licence": "free headline", "history_from": "2010-10",
     "pit_feasible": True, "assets": ("NZDUSD",),
     "fields": ("date", "contract", "settlement", "open_interest", "volume"),
     "pit_fields": ("settlement_ts_utc",),
     "mechanism_families": ("positioning", "terms_of_trade"),
     "how_to_fetch": "nzx.com derivatives market data"},
    {"name": "Desk MT5 bars (H1, M15, D1)", "source": "the desk's own Fusion tape",
     "coverage": "NZDUSD from 2018 with 54,205 H1 bars", "frequency": "tick to daily",
     "publication_lag_days": 0.0, "revisions": "append-only", "licence": "desk-owned",
     "history_from": "2018-01", "pit_feasible": True,
     "assets": ("NZDUSD", "AUDNZD", "NZDJPY"),
     "fields": ("time", "open", "high", "low", "close", "tick_volume", "spread"),
     "pit_fields": ("time",), "mechanism_families": ("all",),
     "how_to_fetch": "desks/mt5/data/universe/<SYMBOL>_<TF>.parquet"},
)

# --------------------------------------------------------------------------- the actors
ACTORS: tuple[dict[str, Any], ...] = (
    {
        "name": "Reserve Bank of New Zealand Monetary Policy Committee",
        "holds": "the Official Cash Rate, a fully-remunerated settlement cash system, and a bond "
                 "portfolio running off under the sales programme begun in 2022",
        "forced_to": ("decide at seven pre-announced meetings a year and publish the decision the "
                      "same afternoon",
                      "publish its OWN projected OCR track at the four Monetary Policy "
                      "Statements -- a commitment few central banks make",
                      "front the press and a parliamentary select committee on MPS days"),
        "when": "14:00 Auckland: 02:00 UTC under NZST and 01:00 UTC under NZDT, with the press "
                "conference an hour later",
        "information": ("the full Stats NZ dataset ahead of release",
                        "its own Survey of Expectations",
                        "bank lending and mortgage-rate data it collects directly"),
        "constraints": ("the remit: 1-3% CPI with a 2% midpoint",
                        "an employment objective ADDED in 2018 and REMOVED in December 2023",
                        "a mortgage book that is predominantly FIXED for one to two years, which "
                        "makes transmission slower and more back-loaded than Australia's"),
        "instruments": ("NZDUSD", "AUDNZD", "NZDJPY", "EURNZD"),
        "counterparties": ("the registered banks holding settlement cash",
                           "the Treasury, through the Crown settlement account",
                           "offshore holders of NZGBs"),
        "observables": ("the OCR decision at the announcement minute",
                        "the published projection track and its revision",
                        "the OIS and 90-day bank bill curve before and after",
                        "the Survey of Expectations"),
        "impact": "reprices the NZD short-rate path; because the track is PUBLISHED, the market "
                  "trades the gap between the Bank's own forecast of itself and the curve, which "
                  "is a richer object than a simple rate surprise",
        "persistence": "the level effect lasts to the next meeting; the reaction FUNCTION changed "
                       "twice in the sample when the employment objective arrived and left, so a "
                       "pooled reaction-function estimate describes neither regime",
        "falsifier": "the same event-window statistic on the seven nearest non-meeting Wednesdays. "
                     "A move that survives there is a mid-week effect, not the RBNZ",
        "notes": "New Zealand's fixed-rate mortgage structure is why the same OCR move transmits "
                 "later here than in Australia; a Tasman policy comparison that ignores it is "
                 "comparing two different transmission speeds",
    },
    {
        "name": "GlobalDairyTrade auction participants (Fonterra and the other listed sellers)",
        "holds": "the supply side of a real ascending-price auction covering whole-milk powder, "
                 "skim-milk powder, butter, anhydrous milk fat and cheddar",
        "forced_to": ("offer a pre-announced volume on a pre-announced date, whatever the price "
                      "environment -- the forward offer schedule is published in advance",
                      "clear the offered volume across bidding rounds, which is what makes the "
                      "result a price rather than a quote"),
        "when": "the first and third Tuesday of each month, with the result published in the "
                "European afternoon",
        "information": ("their own forward supply and inventory",
                        "the published forward offer volumes, which everyone has"),
        "constraints": ("the published forward offer schedule, a public commitment",
                        "the co-operative's obligation to collect all member milk",
                        "the physical seasonality of pasture-fed production, which peaks in the "
                        "southern spring and cannot be smoothed"),
        "instruments": ("NZDUSD", "AUDNZD", "NZDJPY"),
        "counterparties": ("Chinese, South-East Asian and Middle Eastern buyers",
                           "global food manufacturers",
                           "NZX dairy futures hedgers on both sides"),
        "observables": ("the GDT index change and the WMP price at publication",
                        "volume sold and the number of winning bidders",
                        "NZX WMP futures before the event, which carry the expectation"),
        "impact": "a dated, public terms-of-trade shock; roughly a quarter of goods exports "
                  "reprice against it, and the NZD reaction is the cleanest commodity-currency "
                  "event study available to this desk",
        "persistence": "the auction has run since 2008 and the mechanism is structural; the "
                       "MAGNITUDE of the NZD response has fallen as dairy's export share fell and "
                       "as futures hedging pre-positioned more of the move",
        "falsifier": "the same window on AUDUSD, which has no dairy exposure. A move of similar "
                     "size there is the hour, not the auction -- and the NZD-minus-AUD residual "
                     "is the part that is genuinely about dairy",
        "notes": "the auction has no public consensus, so a 'surprise' must be constructed from "
                 "the futures curve or a random walk, and the choice must be declared",
    },
    {
        "name": "Fonterra Co-operative Group as farmgate price setter",
        "holds": "roughly 80% of New Zealand's raw milk collection and the obligation to pay a "
                 "farmgate price derived from a published methodology",
        "forced_to": ("publish an opening farmgate forecast in late May for the season beginning "
                      "1 June, and REVISE it publicly as the auction moves",
                      "pay monthly advance rates to farmers on a published schedule",
                      "collect all member milk regardless of price"),
        "when": "the opening forecast in late May; revisions through the season; advance-rate "
                "payments around the 20th of each month",
        "information": ("its own collection volumes and forward sales book",
                        "contracted sales outside the auction, which are the majority"),
        "constraints": ("the Dairy Industry Restructuring Act and the milk price manual",
                        "a methodology it must follow rather than a discretion it may exercise",
                        "its own balance sheet, which caps how far the forecast can lead the "
                        "auction"),
        "instruments": ("NZDUSD", "AUDNZD"),
        "counterparties": ("roughly 9,000 farmer shareholders",
                           "rural lenders, whose credit conditions follow the payout",
                           "the domestic economy, through rural spending"),
        "observables": ("the farmgate forecast midpoint and range at each announcement",
                        "the advance-rate schedule",
                        "rural lending statistics from RBNZ"),
        "impact": "a slower, domestic transmission of the same dairy shock: farmer income and "
                  "rural credit follow the FORECAST, not the auction, and the two can diverge for "
                  "months",
        "persistence": "structural since the co-operative's formation; the forecast's LEAD over "
                       "the auction is the part that varies and is the tradeable residual",
        "falsifier": "regress the NZD response on the auction and on the forecast revision "
                     "jointly. If the forecast adds nothing once the auction is in, this actor "
                     "is a restatement of the previous one and not a separate mechanism",
        "notes": "the single name is an ACTOR only; no share CFD appears in this pack",
    },
    {
        "name": "Chinese dairy importers and state buyers",
        "holds": "the largest single share of New Zealand's dairy exports and a domestic dairy "
                 "industry whose own production swings against imports",
        "forced_to": ("restock when domestic production and inventory fall short of demand",
                      "bid in the GDT auction against a published offer volume"),
        "when": "concentrated ahead of Chinese demand seasons and around domestic milk-production "
                "cycles; the information arrives in monthly customs data",
        "information": ("their own inventory and domestic production before it is published"),
        "constraints": ("domestic milk-production policy and self-sufficiency targets",
                        "import quota and inspection regimes",
                        "storage capacity for powder, which is finite"),
        "instruments": ("NZDUSD", "AUDNZD", "USDCNH", "CHINAH"),
        "counterparties": ("the GDT sellers", "European and US powder exporters"),
        "observables": ("China customs dairy import tonnage",
                        "the share of GDT volume won by North Asian bidders",
                        "Chinese domestic milk price series"),
        "impact": "the demand side of the dairy channel; Chinese restocking cycles have moved the "
                  "GDT index by double digits within a quarter more than once",
        "persistence": "structural, but the SHARE has fallen as Chinese domestic production grew, "
                       "so a 2014-era beta over-states the channel today",
        "falsifier": "the same statistic on European dairy prices (EU butter and SMP quotations). "
                     "A Chinese restock that moves the world price moves those too; one that "
                     "moves only GDT is a New Zealand supply story wearing a demand label",
        "notes": "",
    },
    {
        "name": "Japanese retail buyers of uridashi and eurokiwi NZD bonds",
        "holds": "NZD-denominated coupon bonds sold into Japanese and European retail, whose "
                 "appeal is the rate differential rather than the credit",
        "forced_to": ("roll or repatriate at MATURITY -- a dated NZD sale that is known years in "
                      "advance and is watched by almost nobody",
                      "meet margin on the leveraged version of the same trade"),
        "when": "issuance clusters when the differential is wide; maturities are a known, dated "
                "schedule",
        "information": ("nothing the market lacks; this actor is forced, not informed"),
        "constraints": ("Japanese FSA leverage caps on the margin version",
                        "the bond's own maturity date, which is not negotiable",
                        "the rate differential, which determines whether the roll happens"),
        "instruments": ("NZDJPY", "NZDUSD", "AUDNZD"),
        "counterparties": ("the issuing supranationals and banks",
                           "the swap dealers who hedge the NZD leg"),
        "observables": ("uridashi issuance and redemption schedules",
                        "FFAJ margin statistics for the NZD pairs",
                        "the NZD-JPY rate differential"),
        "impact": "a dated NZD demand at issuance and a dated NZD supply at maturity; the "
                  "maturity leg is the one that surprises, because the issuance leg is announced",
        "persistence": "the channel was large in 2005-2008, shrank as the differential collapsed, "
                       "and revived with the 2022-2023 differential; it is REGIME-DEPENDENT and "
                       "any pooled estimate spans three different worlds",
        "falsifier": "the same maturity-schedule statistic in years when the NZD-JPY differential "
                     "was below 1%. No differential means no roll incentive, so a maturity effect "
                     "there is not this mechanism",
        "notes": "",
    },
    {
        "name": "CFTC-reportable leveraged funds in CME New Zealand dollar futures (6N)",
        "holds": "a speculative net position in a currency whose futures open interest is small "
                 "relative to the underlying spot market",
        "forced_to": ("report weekly on a fixed clock",
                      "liquidate at the clearing house's margin call"),
        "when": "Tuesday close, published Friday 15:30 America/New_York",
        "information": ("their own flow and prime-broker balances"),
        "constraints": ("CME margin", "CFTC large-trader reporting", "fund drawdown limits"),
        "instruments": ("NZDUSD", "NZDJPY", "AUDNZD"),
        "counterparties": ("commercial hedgers", "dealer banks"),
        "observables": ("the COT disaggregated report, contract 112741",
                        "the reportable TRADER COUNT, which matters more here than in AUD",
                        "CME 6N volume and open interest"),
        "impact": "crowded extremes in a small contract; the mechanism is the forced liquidation, "
                  "not the level",
        "persistence": "extremes mean-revert over weeks; the contract's liquidity has grown, so "
                       "an early-sample percentile is not comparable with a late-sample one",
        "falsifier": "the same percentile rule with the Tuesday position aligned to the FRIDAY "
                     "bar. Survival only under that alignment is a point-in-time bug",
        "notes": "the NZD contract is small enough that weeks with few reportable traders produce "
                 "a net position that is noise; read the trader count alongside it",
    },
    {
        "name": "New Zealand Debt Management (The Treasury)",
        "holds": "the Crown's bond programme, with an unusually high offshore ownership share",
        "forced_to": ("fund the published borrowing programme through weekly tenders announced in "
                      "advance",
                      "issue into whatever conditions exist on the announced day"),
        "when": "weekly tenders, commonly Thursday; syndications announced ahead",
        "information": ("the Crown cash position", "dealer indications before the tender"),
        "constraints": ("the published NZGB issuance programme",
                        "a small, concentrated investor base -- a single large offshore buyer "
                        "moves a New Zealand tender in a way it could not move an Australian one"),
        "instruments": ("NZDUSD", "UST10Y", "NZDJPY"),
        "counterparties": ("the NZDM dealer panel",
                           "offshore reserve managers and index funds"),
        "observables": ("tender coverage ratio and weighted average yield",
                        "the NZGB-UST 10-year spread",
                        "the published issuance calendar"),
        "impact": "creates dated NZD duration supply; offshore participation is a dated NZD demand",
        "persistence": "structural; the offshore share is a slow regime variable and has moved by "
                       "tens of percentage points over the last fifteen years",
        "falsifier": "the same statistic on Australian AOFM tender days. A coverage effect present "
                     "in both is a global duration bid and is not a New Zealand funding fact",
        "notes": "",
    },
    {
        "name": "Statistics New Zealand",
        "holds": "the official macro dataset and a pre-announced embargoed release calendar",
        "forced_to": ("publish at 10:45 Auckland on the announced date, to everyone at once",
                      "revise seasonally adjusted series when factors are re-estimated"),
        "when": "10:45 Auckland: 22:45 UTC the previous day under NZST, 21:45 UTC under NZDT",
        "information": ("the number under embargo before release"),
        "constraints": ("the Statistics Act and the published release calendar",
                        "a QUARTERLY labour market survey and a QUARTERLY CPI -- New Zealand has "
                        "no monthly employment or inflation print, which makes each one larger "
                        "and the gaps between them longer"),
        "instruments": ("NZDUSD", "AUDNZD", "NZDJPY", "EURNZD"),
        "counterparties": ("the whole market simultaneously"),
        "observables": ("the release at the embargo minute",
                        "the OIS curve's repricing across it"),
        "impact": "the quarterly CPI is the single largest scheduled NZD event after the OCR, "
                  "precisely because it is quarterly: one print carries three months of news",
        "persistence": "permanent as a class; the ranking within it follows the policy regime",
        "falsifier": "the same 22:45 UTC window on days with no scheduled release. A systematic "
                     "move there is the New Zealand open, not the data",
        "notes": "the 10:45 Auckland embargo falls on the PREVIOUS UTC DAY -- an event study that "
                 "aligns it to the release's own calendar date is off by one",
    },
    {
        "name": "New Zealand tourism operators and inbound visitors",
        "holds": "an export industry that was roughly a fifth of exports before 2020 and whose "
                 "customers physically arrive and convert currency",
        "forced_to": ("price a season ahead of knowing the exchange rate",
                      "accept arrivals concentrated in the southern summer, which cannot be "
                      "smoothed"),
        "when": "the southern summer peak (December-February) and the shoulder seasons",
        "information": ("forward bookings ahead of the published arrival statistics"),
        "constraints": ("physical capacity in accommodation and aviation",
                        "aviation seat capacity, which is set months ahead",
                        "visa and border policy"),
        "instruments": ("NZDUSD", "AUDNZD"),
        "counterparties": ("Australian, Chinese and US visitors",
                           "airlines selling in foreign currency"),
        "observables": ("monthly international visitor arrivals by origin",
                        "aviation seat capacity",
                        "card-spend data by visitor origin"),
        "impact": "a seasonal NZD demand that is real but slow; its value to this pack is as a "
                  "CONTROL on the dairy channel, because the two seasonals differ",
        "persistence": "the seasonal is structural; the LEVEL broke completely in 2020-2022 and "
                       "the recovery path is its own regime, so a pooled seasonal is meaningless",
        "falsifier": "the same seasonal statistic on AUDUSD, whose tourism exposure is smaller "
                     "and differently timed. A shared summer effect is southern-hemisphere "
                     "seasonality and not New Zealand tourism",
        "notes": "",
    },
    {
        "name": "New Zealand banks funding offshore",
        "holds": "a loan book substantially larger than the domestic deposit base, funded by "
                 "offshore wholesale issuance swapped back into NZD",
        "forced_to": ("swap foreign-currency issuance back to NZD to fund an NZD book",
                      "meet the Reserve Bank's Core Funding Ratio, which mandates a minimum share "
                      "of stable funding"),
        "when": "issuance clusters after results blackouts; the Core Funding Ratio is a continuous "
                "constraint",
        "information": ("their own funding plans and deposit growth"),
        "constraints": ("the RBNZ Core Funding Ratio",
                        "capital requirements raised materially after the 2019 review",
                        "the four largest banks are Australian-owned, so group funding decisions "
                        "are made in Sydney and are not purely a New Zealand variable"),
        "instruments": ("NZDUSD", "AUDNZD", "NZDJPY"),
        "counterparties": ("offshore bond investors", "cross-currency basis dealers",
                           "their Australian parents"),
        "observables": ("the NZD/USD cross-currency basis",
                        "RBNZ bank funding and liquidity statistics",
                        "issuance announcements"),
        "impact": "compresses the NZD basis when issuance is heavy; the Australian ownership means "
                  "the NZD and AUD basis move together more than two independent systems would",
        "persistence": "structural since the Core Funding Ratio was introduced in 2010",
        "falsifier": "the same basis statistic in months with no offshore issuance. Persistence "
                     "there is a global dollar-funding condition, not a New Zealand bank fact",
        "notes": "",
    },
    {
        "name": "Index and reserve managers holding NZGBs",
        "holds": "a high offshore share of a small government bond market",
        "forced_to": ("track the index including New Zealand's weight, whatever they think of it",
                      "rebalance when the index changes or when the currency moves the weight"),
        "when": "index rebalance dates and month end",
        "information": ("the index rules, which are public"),
        "constraints": ("tracking-error budgets",
                        "the SIZE of the New Zealand market, which means a modest global "
                        "allocation is a large domestic flow"),
        "instruments": ("NZDUSD", "UST10Y", "NZDJPY"),
        "counterparties": ("NZDM at tender", "domestic banks and funds"),
        "observables": ("NZGB offshore ownership statistics",
                        "the NZGB-UST spread",
                        "index rebalance announcements"),
        "impact": "a small global reweighting is a large New Zealand flow; this asymmetry is the "
                  "mechanism and it does not exist for Australia at the same scale",
        "persistence": "structural; the offshore share moves slowly and predictably with yield "
                       "differentials",
        "falsifier": "the same statistic scaled by market size against Australia. If the New "
                     "Zealand effect is not LARGER per unit of index weight, the smallness story "
                     "is wrong",
        "notes": "",
    },
    {
        "name": "New Zealand meat and forestry exporters",
        "holds": "the second and third export complexes: beef and lamb, and logs and wood pulp, "
                 "the latter overwhelmingly to China",
        "forced_to": ("ship on a processing-season calendar set by livestock and harvest cycles",
                      "sell into whatever price the destination market offers, with almost no "
                      "domestic alternative"),
        "when": "the meat processing season runs roughly October to May; log exports run "
                "continuously but with Chinese port-inventory cycles",
        "information": ("their own kill and harvest schedules"),
        "constraints": ("processing capacity, which is fixed in season",
                        "Chinese construction demand for logs, which is outside their control",
                        "biosecurity and market-access rules"),
        "instruments": ("NZDUSD", "AUDNZD", "USDCNH"),
        "counterparties": ("Chinese log and meat buyers", "US and UK beef importers"),
        "observables": ("Stats NZ merchandise trade by commodity",
                        "the ANZ commodity price index sub-indices",
                        "Chinese log port inventory"),
        "impact": "the non-dairy half of the terms of trade; it matters most as a CONTROL, "
                  "because it separates 'New Zealand export prices rose' from 'dairy rose'",
        "persistence": "structural; the log channel's China concentration has grown and is now a "
                       "single-country exposure larger than dairy's",
        "falsifier": "regress NZD on the dairy sub-index and the non-dairy sub-index jointly. If "
                     "the non-dairy term is not separately significant, this is one channel and "
                     "not two",
        "notes": "",
    },
    {
        "name": "Retail and systematic carry participants in NZDJPY",
        "holds": "long NZDJPY carry positions funded in yen; historically the highest-yielding "
                 "G10 carry pair",
        "forced_to": ("liquidate at the broker's maintenance margin in a fast move",
                      "pay or receive the swap at the daily rollover, tripled on Wednesday"),
        "when": "continuous, concentrated in the Tokyo morning and around both banks' decisions",
        "information": ("nothing the market lacks"),
        "constraints": ("Japanese FSA leverage caps", "broker maintenance margin",
                        "the rate differential, which sizes the position"),
        "instruments": ("NZDJPY", "AUDNZD", "NZDUSD", "USDJPY"),
        "counterparties": ("retail brokers and the dealers they hedge into"),
        "observables": ("FFAJ monthly FX margin statistics",
                        "realised downside versus upside semivariance in NZDJPY",
                        "the NZD-JPY policy differential"),
        "impact": "one-sided liquidation in stress; NZDJPY's drawdowns are faster than its "
                  "rallies, and the asymmetry scales with the differential",
        "persistence": "visible in every risk-off episode since 2007; nearly absent in 2020-2021 "
                       "when the differential was near zero, which is the cleanest era control",
        "falsifier": "the same semivariance ratio on NZDCHF, a carry pair with a different retail "
                     "base. Shared asymmetry is risk-off in general, not Japanese margin",
        "notes": "the desk quotes NZDJPY with a 147-point median spread against AUDJPY's 0 -- the "
                 "cost floor is materially higher on the New Zealand leg and every NZDJPY cell "
                 "must clear it",
    },
    {
        "name": "Australian and New Zealand cross-Tasman corporates",
        "holds": "revenue in one currency and costs, reporting or dividends in the other; the "
                 "four largest New Zealand banks are Australian-owned",
        "forced_to": ("repatriate or hedge earnings on a reporting calendar",
                      "translate New Zealand earnings into Australian reporting currency"),
        "when": "half-year and full-year reporting; dividend payment dates",
        "information": ("their own earnings before the market"),
        "constraints": ("accounting standards on translation",
                        "group treasury policy set in Sydney, not Auckland"),
        "instruments": ("AUDNZD", "NZDUSD", "AUDUSD"),
        "counterparties": ("group treasuries", "interbank dealers in the cross"),
        "observables": ("reporting and dividend calendars",
                        "AUDNZD behaviour around the reporting clusters"),
        "impact": "a dated AUDNZD flow that is specific to the cross and invisible in either "
                  "dollar pair; it is one of the few genuinely cross-specific flows that exists",
        "persistence": "structural while the ownership structure persists",
        "falsifier": "the same statistic on the reconstructed cross from AUDUSD and NZDUSD. An "
                     "effect present in the direct quote but not the reconstruction is a "
                     "liquidity artefact of the cross, not a corporate flow",
        "notes": "",
    },
    {
        "name": "The first price-setters of the global trading week",
        "holds": "no position by mandate; the constraint is TEMPORAL -- Wellington and Auckland "
                 "quote before anyone else",
        "forced_to": ("make a price on Monday morning with the weekend's news and none of the "
                      "week's liquidity",
                      "quote wider, because the risk cannot be laid off until Tokyo opens"),
        "when": "the Monday open: 20:00 UTC Sunday under NZST, 19:00 UTC under NZDT",
        "information": ("the weekend's news, which everyone has, and nothing else"),
        "constraints": ("no depth to hedge into for several hours",
                        "the physical time-zone position of New Zealand, which is not negotiable"),
        "instruments": ("NZDUSD", "AUDNZD", "NZDJPY", "AUDUSD"),
        "counterparties": ("early Asian dealers and whoever must transact before Tokyo"),
        "observables": ("the Monday open gap against the Friday close",
                        "spread widening in the first hour",
                        "the gap's reversal or continuation once Tokyo opens"),
        "impact": "New Zealand prices the weekend first, in the thinnest book of the cycle; NZD "
                  "gaps are the largest in the G10 and much of what is attributed to New Zealand "
                  "news is this hour",
        "persistence": "permanent -- it is geography; the SIZE has fallen as electronic liquidity "
                       "arrived earlier, so a 2010 gap distribution over-states today's",
        "falsifier": "the same gap statistic on EURUSD at the same UTC minute. A gap of similar "
                     "relative size there is a global weekend effect, not a New Zealand one",
        "notes": "",
    },
)

# --------------------------------------------------------------------------- the domains
DOMAINS: tuple[dict[str, Any], ...] = (
    {
        "id": "NZ-A", "title": "OCR decisions and the published projection track",
        "objects": ("the seven decisions a year at 02:00/01:00 UTC",
                    "the four Monetary Policy Statements with an OCR projection track",
                    "the three Monetary Policy Reviews with no new projection",
                    "the press conference and select committee appearance an hour later",
                    "the March 2020 off-cycle 75bp cut, which is its own class"),
        "conditions": ("the surprise measured against the OIS curve where it is available, and "
                       "declared UNMEASURED where it is not -- the curve is not quoted here",
                       "MPS meetings separated from MPR meetings: they carry different objects",
                       "the mandate era, because the employment objective arrived in 2018 and "
                       "left in December 2023",
                       "the gap between the market curve and the Bank's own published track"),
        "instruments": ("NZDUSD", "AUDNZD", "NZDJPY", "EURNZD"),
        "controls": ("the same window on the seven nearest non-meeting Wednesdays",
                     "the same window on EURUSD, which has no RBNZ exposure",
                     "the same window on RBA decision days, separating 'a central bank decided' "
                     "from 'the RBNZ decided'",
                     "the pre-2019 pre-MPC sample, where a single Governor decided alone, as a "
                     "governance control"),
        "notes": "the published track means there are TWO expectations to be surprised against -- "
                 "the market's and the Bank's own -- and they disagree most when it matters most",
    },
    {
        "id": "NZ-B", "title": "The track revision as an information event in its own right",
        "objects": ("the projected OCR path in each MPS",
                    "the revision from the previous MPS at each horizon",
                    "the TWI and oil-price assumptions the projection is conditioned on",
                    "the quarterly Survey of Expectations"),
        "conditions": ("the revision measured at a FIXED horizon, not at the nearest quarter, so "
                       "the passage of time is not read as a revision",
                       "residualised against the decision-day rate surprise",
                       "whether the TWI assumption itself moved, since a track revision driven by "
                       "the currency is partly endogenous"),
        "instruments": ("NZDUSD", "AUDNZD", "UST10Y"),
        "controls": ("the decision-day return alone, to prove the track adds something",
                     "the MPR meetings, which carry no track and should therefore show nothing",
                     "the same statistic on RBA SoMP days, separating 'a forecast moved' from "
                     "'the OCR track moved'",
                     "a placebo revision drawn from the track's own historical revision "
                     "distribution"),
        "notes": "the TWI assumption makes this partly circular: the Bank conditions its track on "
                 "the currency, so a currency move can cause the revision that is then used to "
                 "predict the currency. NZ-B must break that loop explicitly or it measures itself",
    },
    {
        "id": "NZ-C", "title": "The GlobalDairyTrade auction as a dated terms-of-trade shock",
        "objects": ("the fortnightly auction on the first and third Tuesday",
                    "the GDT index change and the whole-milk-powder price",
                    "volume sold and the number of winning bidders",
                    "NZX WMP futures before the event, which carry the expectation"),
        "conditions": ("the surprise built from the futures curve where it exists and from a "
                       "random walk where it does not -- and the choice DECLARED, because the two "
                       "give different answers",
                       "the publication minute, which this pack declares as roughly 15:00 UTC and "
                       "flags for verification",
                       "the dairy season, since spring-flush events are structurally different",
                       "whether the event was a scheduled one or an added one"),
        "instruments": ("NZDUSD", "AUDNZD", "NZDJPY", "USDCNH"),
        "controls": ("the same window on AUDUSD, which has no dairy exposure; the NZD-minus-AUD "
                     "residual is the dairy-specific part",
                     "the same window on non-auction Tuesdays at the same UTC minute",
                     "European butter and skim-milk-powder quotations, separating a world dairy "
                     "move from a New Zealand supply move",
                     "a placebo auction calendar shifted one week"),
        "notes": "this is the pack's flagship domain: a free, public, dated auction of the "
                 "country's principal export price. If a commodity-currency event study cannot be "
                 "made to work here it cannot be made to work anywhere",
    },
    {
        "id": "NZ-D", "title": "The farmgate forecast and the domestic transmission of dairy",
        "objects": ("the opening farmgate forecast in late May",
                    "each in-season revision and its midpoint",
                    "monthly advance-rate payments",
                    "rural lending and rural spending series"),
        "conditions": ("the auction and the forecast entered JOINTLY, because the question is "
                       "whether the forecast adds anything once the auction is known",
                       "the season, since an early revision carries more information than a late "
                       "one",
                       "the size of the revision relative to the published range"),
        "instruments": ("NZDUSD", "AUDNZD"),
        "controls": ("the auction alone, which is the null this domain must beat",
                     "the same statistic on the ANZ commodity index, a broader and slower proxy",
                     "months with no revision at all",
                     "the NZD-terms versus world-terms ANZ index, since the NZD-terms series "
                     "already contains the exchange rate"),
        "notes": "the forecast is the SLOW leg and the auction is the FAST one; the interesting "
                 "cell is the divergence between them, not either alone",
    },
    {
        "id": "NZ-E", "title": "AUD/NZD: two policies, two export baskets, two calendars",
        "objects": ("the RBA IB-implied path against the NZ OIS-implied path",
                    "the non-overlapping decision calendars",
                    "the ore-versus-dairy relative export price",
                    "the days one market is closed and the other is open"),
        "conditions": ("each country's own market-implied path",
                       "whether the two banks met in the same fortnight",
                       "the CALENDAR divergence, which is a one-sided-book condition and not a "
                       "macro one",
                       "excluding 2020-2021, when both curves were pinned"),
        "instruments": ("AUDNZD", "AUDUSD", "NZDUSD", "NZDJPY", "AUS200"),
        "controls": ("the reconstructed cross from AUDUSD and NZDUSD, separating a genuine cross "
                     "effect from a liquidity artefact of the direct quote",
                     "randomise which leg is labelled NZ and re-run",
                     "the same statistic on EURGBP-style relative-policy pairs",
                     "days when BOTH markets are open, as the baseline for the divergence test"),
        "notes": "the calendar divergence is the part nobody models: on 2026-04-27 New Zealand is "
                 "closed for the Anzac Mondayisation and the Australian market is open",
    },
    {
        "id": "NZ-F", "title": "NZD carry, uridashi maturities and the asymmetry of unwinds",
        "objects": ("the NZD-JPY policy differential",
                    "uridashi and eurokiwi issuance and MATURITY schedules",
                    "FFAJ margin aggregates",
                    "NZDJPY realised downside versus upside semivariance"),
        "conditions": ("semivariance rather than variance, because the mechanism is one-sided",
                       "the size of the differential, which sizes the position",
                       "the maturity schedule, which is the dated leg",
                       "the 147-point NZDJPY median spread as a cost floor every cell must clear"),
        "instruments": ("NZDJPY", "NZDCHF", "NZDUSD", "USDJPY", "US500"),
        "controls": ("the same ratio on NZDCHF, a carry pair with a different retail base",
                     "2020-2021, when the differential was near zero and the mechanism should be "
                     "absent",
                     "the same ratio on AUDJPY: a shared asymmetry is Oceania carry in general",
                     "the same statistic net of the quoted spread, since the NZD leg's cost is "
                     "materially higher than the Australian one"),
        "notes": "",
    },
    {
        "id": "NZ-G", "title": "New Zealand equity mechanics as a transmission target",
        "objects": ("the NZX 50 GROSS index and its closing auction at 16:45-17:00 Auckland",
                    "the gentailer and healthcare concentration of the index",
                    "the absence of an NZX index quote on this broker"),
        "conditions": ("the GROSS construction acknowledged explicitly -- comparing it with a "
                       "price index without adjustment biases every cross-market study upward by "
                       "roughly the dividend yield",
                       "the index's small number of large constituents, which makes single-name "
                       "events index events",
                       "the NZX close as the first equity print of the global day"),
        "instruments": ("AUS200", "US500", "NZDUSD"),
        "controls": ("AUS200 as the nearest quoted proxy, with its own price-index construction",
                     "the same statistic on a total-return reconstruction of AUS200",
                     "days when NZX is closed and ASX is open"),
        "notes": "the index is NOT quoted here, so this domain exists to prevent a cell being "
                 "compiled against it and to name the proxies honestly",
    },
    {
        "id": "NZ-H", "title": "The broad terms of trade: dairy against everything else",
        "objects": ("the ANZ commodity price index, world terms and NZD terms",
                    "dairy, meat and forestry sub-indices",
                    "Stats NZ merchandise trade by commodity",
                    "the RBNZ TWI"),
        "conditions": ("dairy and non-dairy entered separately -- the question is whether there "
                       "are two channels or one",
                       "the WORLD-price series used for prediction; the NZD-price series already "
                       "contains the exchange rate and regressing NZD on it is partly circular",
                       "the China share of exports, which has grown and re-weighted the channel"),
        "instruments": ("NZDUSD", "AUDNZD", "USDCNH", "USDX"),
        "controls": ("the NZD-terms index as an explicit circularity check: it should perform "
                     "BETTER in-sample and WORSE out-of-sample, and if it does not, something is "
                     "wrong with the test",
                     "the same regression on AUDUSD with Australian export prices",
                     "USDX, so a dollar move is not read as a terms-of-trade move",
                     "shuffle the sub-index within month to keep the level and kill the timing"),
        "notes": "",
    },
    {
        "id": "NZ-I", "title": "Tourism as a seasonal export with a broken sample",
        "objects": ("monthly international visitor arrivals by origin",
                    "aviation seat capacity, set months ahead",
                    "visitor card spend",
                    "the 2020-2022 border closure"),
        "conditions": ("the sample SPLIT at the border closure; a pooled seasonal spanning it is "
                       "meaningless",
                       "origin mix, since Australian and Chinese visitors have different seasons",
                       "seat capacity as the leading variable, because it is set before arrivals"),
        "instruments": ("NZDUSD", "AUDNZD"),
        "controls": ("the same seasonal on AUDUSD, whose tourism exposure is smaller and "
                     "differently timed",
                     "the pre-2020 and post-2022 samples tested separately and compared",
                     "the southern-summer seasonal in a currency with no tourism exposure"),
        "notes": "included principally as a CONTROL for NZ-C: dairy and tourism have different "
                 "seasonals, so an effect that follows both is a southern-summer artefact",
    },
    {
        "id": "NZ-J", "title": "The quarterly data calendar",
        "objects": ("quarterly CPI", "the quarterly Household Labour Force Survey",
                    "the Quarterly Survey of Business Opinion",
                    "monthly merchandise trade",
                    "the ANZ business outlook survey"),
        "conditions": ("the 10:45 Auckland embargo, which falls on the PREVIOUS UTC DAY and is a "
                       "classic off-by-one",
                       "quarterly prints treated as larger events than monthly ones, because they "
                       "carry three months of news",
                       "the policy era, since the ranking of prints follows the mandate"),
        "instruments": ("NZDUSD", "AUDNZD", "NZDJPY", "EURNZD"),
        "controls": ("the same UTC window on days with no scheduled release",
                     "the same window on Australian releases at 01:30 UTC",
                     "a placebo calendar shifted one week",
                     "the same window on US releases, removing the global data factor"),
        "notes": "New Zealand has no monthly CPI and no monthly employment print; the information "
                 "arrives in fewer, larger lumps than in almost any comparable economy",
    },
    {
        "id": "NZ-K", "title": "NZGB issuance and a small market's offshore dependence",
        "objects": ("the weekly NZDM tender calendar",
                    "coverage ratio and weighted average yield",
                    "the NZGB-UST spread",
                    "offshore ownership statistics"),
        "conditions": ("scaled by market size, because the whole point is that a small global "
                       "allocation is a large domestic flow",
                       "announcement and tender tested as separate events",
                       "the offshore share as a slow-moving regime variable"),
        "instruments": ("NZDUSD", "UST10Y", "NZDJPY"),
        "controls": ("the same statistic on Australian AOFM tender days",
                     "weeks with no tender",
                     "US Treasury refunding days, removing the global duration bid",
                     "the SAME statistic unscaled, to demonstrate that scaling is what makes the "
                     "New Zealand effect visible"),
        "notes": "",
    },
    {
        "id": "NZ-L", "title": "Opening the world's week",
        "objects": ("the Monday open at 20:00 UTC Sunday under NZST, 19:00 under NZDT",
                    "the Friday-close-to-Monday-open gap",
                    "spread widening in the first hour",
                    "the Tokyo handover two to three hours later"),
        "conditions": ("the DST transition applied on the New Zealand side, whose dates differ "
                       "from Australia's",
                       "weekends carrying scheduled news separated from quiet ones",
                       "the gap's reversal or continuation measured out to the Tokyo open"),
        "instruments": ("NZDUSD", "AUDNZD", "NZDJPY", "AUDUSD"),
        "controls": ("the same gap statistic on EURUSD at the same UTC minute: a similar relative "
                     "gap there is a global weekend effect",
                     "the same statistic mid-week at the same hour",
                     "weekends with no scheduled news",
                     "the weeks when New Zealand and Australian DST disagree, a natural "
                     "experiment on the clock"),
        "notes": "much of what is reported as New Zealand-specific price behaviour is this hour: "
                 "the thinnest book in the G10 cycle pricing two days of news",
    },
    {
        "id": "NZ-M", "title": "The New Zealand holiday calendar and the Tasman divergence",
        "objects": ("the eleven national public holidays",
                    "Mondayisation of six of them, and only since 2014 for Waitangi and Anzac",
                    "Matariki, whose date is legislated in a schedule rather than computed",
                    "Auckland Anniversary Day, which NZX observes and the nation does not",
                    "the days New Zealand is closed and Australia is not"),
        "conditions": ("the Mondayisation rule applied only from 2014 for Waitangi and Anzac",
                       "Matariki read from the legislated table, never computed",
                       "regional anniversaries kept out of the national set",
                       "the divergence days tested as a ONE-SIDED BOOK condition, not a macro one"),
        "instruments": ("AUDNZD", "NZDUSD", "AUDUSD", "AUS200"),
        "controls": ("days when both markets are open, as the baseline",
                     "days when both are closed, which should show nothing",
                     "the same statistic on a European holiday divergence, to show the mechanism "
                     "is 'one side is shut' and not 'New Zealand is shut'",
                     "a placebo divergence calendar shifted one week"),
        "notes": "2026-04-27 is the worked example: New Zealand closed for the Anzac Mondayisation "
                 "while the ASX, following New South Wales, trades a normal session",
    },
)

# --------------------------------------------------------------------------- miners
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    {"name": "nz_ocr_surprise_event_study", "domain_ids": ("NZ-A",), "kind": "event",
     "cadence_s": 86400.0, "steerable": False, "wired": False,
     "entry": "countries.nz.miners:ocr_surprise_event_study",
     "needs": ("RBNZ decision dates", "an OIS-implied path if one can be sourced",
               "NZDUSD and AUDNZD M15 bars"),
     "notes": "reports UNMEASURED for any meeting with no sourced curve rather than treating the "
              "decision itself as the surprise; splits MPS from MPR meetings"},
    {"name": "nz_track_revision", "domain_ids": ("NZ-B",), "kind": "event", "cadence_s": 86400.0,
     "steerable": True, "wired": False, "entry": "countries.nz.miners:track_revision",
     "needs": ("every MPS projection-track vintage", "NZDUSD H1 bars"),
     "notes": "measures the revision at a FIXED horizon and breaks the TWI circularity explicitly"},
    {"name": "nz_gdt_event_study", "domain_ids": ("NZ-C",), "kind": "event", "cadence_s": 43200.0,
     "steerable": False, "wired": False, "entry": "countries.nz.miners:gdt_event_study",
     "needs": ("GDT results by event number", "NZDUSD and AUDUSD M15 bars"),
     "notes": "the NZD-minus-AUD residual is the headline output; declares the assumed "
              "publication minute and flags it for verification"},
    {"name": "nz_farmgate_vs_auction", "domain_ids": ("NZ-D",), "kind": "macro",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.nz.miners:farmgate_vs_auction",
     "needs": ("Fonterra forecast vintages", "GDT results", "NZDUSD D1 bars"),
     "notes": "enters both jointly; the auction alone is the null this miner must beat"},
    {"name": "nz_tasman_relative_policy", "domain_ids": ("NZ-E",), "kind": "macro",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.nz.miners:tasman_relative_policy",
     "needs": ("RBA and RBNZ decision dates", "AUDNZD H1 bars", "both holiday calendars"),
     "notes": "runs the reconstructed-cross control before reporting any direct-quote result"},
    {"name": "nz_carry_semivariance", "domain_ids": ("NZ-F",), "kind": "microstructure",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.nz.miners:carry_semivariance",
     "needs": ("NZDJPY, NZDCHF, AUDJPY, US500 M15 bars", "FFAJ margin statistics"),
     "notes": "nets the 147-point NZDJPY median spread before any result is reported"},
    {"name": "nz_terms_of_trade_split", "domain_ids": ("NZ-H",), "kind": "macro",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.nz.miners:terms_of_trade_split",
     "needs": ("ANZ commodity index world and NZD series", "NZDUSD D1 bars"),
     "notes": "runs the NZD-terms circularity check as an explicit control and reports both"},
    {"name": "nz_quarterly_calendar_ranking", "domain_ids": ("NZ-J",), "kind": "event",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.nz.miners:quarterly_calendar_ranking",
     "needs": ("Stats NZ release calendar", "NZDUSD M15 bars"),
     "notes": "handles the 10:45 Auckland embargo falling on the previous UTC day"},
    {"name": "nz_tender_footprint", "domain_ids": ("NZ-K",), "kind": "flow",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.nz.miners:tender_footprint",
     "needs": ("NZDM tender results", "NZDUSD and UST10Y H1 bars"),
     "notes": "reports the size-scaled and unscaled versions side by side"},
    {"name": "nz_monday_open_gap", "domain_ids": ("NZ-L",), "kind": "microstructure",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.nz.miners:monday_open_gap",
     "needs": ("NZDUSD, AUDUSD, EURUSD M15 bars", "New Zealand DST transition dates"),
     "notes": "the EURUSD control is reported first; the DST-disagreement weeks are separate"},
    {"name": "nz_calendar_divergence", "domain_ids": ("NZ-M",), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": False, "wired": False,
     "entry": "countries.nz.miners:calendar_divergence",
     "needs": ("both national holiday calendars", "AUDNZD H1 bars"),
     "notes": "measures the one-sided-book days explicitly; 2026-04-27 is the worked example"},
)

# --------------------------------------------------------------------------- transmission edges
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    {"source": "GlobalDairyTrade index change (first and third Tuesday)", "target": "NZDUSD",
     "sign": "+",
     "mechanism": "roughly a quarter of goods exports reprice against the auction; the result is "
                  "a dated, public terms-of-trade shock with a known publication minute",
     "horizon": "0 to 3 sessions",
     "condition": "the surprise built against the NZX futures curve, or a random walk with the "
                  "choice declared",
     "control": "the same window on AUDUSD, which has no dairy exposure",
     "falsifier": "an AUDUSD response of the same size, which would make the effect the hour "
                  "rather than the auction"},
    {"source": "GlobalDairyTrade index change", "target": "AUDNZD", "sign": "-",
     "mechanism": "the cross is the cleanest dairy expression available: it removes the dollar "
                  "from both legs and leaves the export-basket difference",
     "horizon": "0 to 5 sessions",
     "condition": "conditioned on the ore-versus-dairy relative price so the Australian leg's own "
                  "terms of trade are not read as a dairy effect",
     "control": "the reconstructed cross from AUDUSD and NZDUSD",
     "falsifier": "a response present in the direct quote but absent in the reconstruction, which "
                  "would make it a liquidity artefact"},
    {"source": "RBNZ OCR surprise against the OIS curve", "target": "NZDUSD", "sign": "+",
     "mechanism": "a hawkish surprise raises the expected NZD short-rate path and the carry",
     "horizon": "0 to 60 minutes",
     "condition": "only where an OIS-implied path can be sourced; otherwise UNMEASURED",
     "control": "the seven nearest non-meeting Wednesdays, and the same window on EURUSD",
     "falsifier": "an equal move on non-meeting Wednesdays at the same minute"},
    {"source": "RBNZ published OCR track revision", "target": "NZDUSD", "sign": "+",
     "mechanism": "the Bank publishes a forecast of its own policy rate; a revision upward is a "
                  "commitment the curve must reprice against, distinct from the decision itself",
     "horizon": "0 to 5 sessions",
     "condition": "residualised against the decision-day return and measured at a fixed horizon",
     "control": "the three MPR meetings, which carry no track and should therefore show nothing",
     "falsifier": "an equal effect on MPR days, which would prove the estimator is finding the "
                  "meeting rather than the track"},
    {"source": "RBNZ-minus-RBA expected-path difference", "target": "AUDNZD", "sign": "-",
     "mechanism": "the cross removes the dollar from both legs, leaving relative policy",
     "horizon": "1 to 20 sessions",
     "condition": "only where both curves carry dispersion; 2020-2021 is vacuous",
     "control": "randomise which leg is labelled NZ; and the reconstructed cross",
     "falsifier": "a result inside the pinned-floor window"},
    {"source": "China customs dairy import tonnage", "target": "NZDUSD", "sign": "+",
     "mechanism": "China is the largest single destination; a restocking cycle is the demand side "
                  "of the auction and shows up in customs data before it shows up in the price",
     "horizon": "5 to 40 sessions",
     "condition": "conditioned on Chinese domestic milk production, since a restock driven by a "
                  "domestic shortfall is a different signal from one driven by demand",
     "control": "European butter and skim-milk-powder quotations",
     "falsifier": "a Chinese restock that moves GDT but not the European quotations, which would "
                  "make it a New Zealand supply story"},
    {"source": "USDCNH", "target": "NZDUSD", "sign": "-",
     "mechanism": "China is the largest export market for dairy, logs and meat; a weaker renminbi "
                  "raises the local-currency cost of New Zealand goods",
     "horizon": "1 to 20 sessions",
     "condition": "conditioned on USDX so a dollar move is not double-counted",
     "control": "the same regression on AUDUSD, which shares the China exposure",
     "falsifier": "an NZD beta to CNH no larger than AUD's, which makes it generic China beta"},
    {"source": "New Zealand quarterly CPI surprise (22:45 UTC, previous calendar day)",
     "target": "NZDUSD", "sign": "+",
     "mechanism": "New Zealand has no monthly CPI, so one quarterly print carries three months of "
                  "inflation news and reprices the whole OIS curve",
     "horizon": "0 to 2 sessions",
     "condition": "the embargo minute falls on the PREVIOUS UTC day; an off-by-one here puts the "
                  "whole sample in the wrong bar",
     "control": "the same UTC window on days with no scheduled release",
     "falsifier": "an equal move at the same UTC minute on non-release days"},
    {"source": "NZDJPY carry unwind (forced retail liquidation)", "target": "NZDJPY", "sign": "-",
     "mechanism": "carry positions are long, so a risk shock forces selling into a falling market; "
                  "the distribution is one-sided by construction",
     "horizon": "intraday to 10 sessions",
     "condition": "only where the NZD-JPY differential is wide enough to have built the position",
     "control": "NZDCHF, a carry pair with a different retail base; and the 2020-2021 zero-"
                "differential window",
     "falsifier": "equal downside and upside semivariance when the differential is wide"},
    {"source": "US500 overnight session return", "target": "AUS200", "sign": "+",
     "mechanism": "New Zealand and then Australia are the first liquid venues to price the "
                  "completed US session; the NZX close is the first equity print of the global day",
     "horizon": "the Asia-Pacific open",
     "condition": "strongest after a US move exceeding one daily sigma",
     "control": "the same gap on JPN225 two hours later",
     "falsifier": "an open gap uncorrelated with the preceding US session"},
    {"source": "Anzac Day Mondayisation divergence (NZ closed, Australia open)",
     "target": "AUDNZD", "sign": "two_sided",
     "mechanism": "one side of the cross has no domestic book; liquidity and the ability to hedge "
                  "are asymmetric for a full session, which widens realised spread and changes the "
                  "shape of the intraday range",
     "horizon": "the divergent session",
     "condition": "weekday divergence days only; a divergence that falls on a weekend is nothing",
     "control": "days when both markets are open, and days when both are closed",
     "falsifier": "no measurable difference in realised range or spread on divergence days, which "
                  "would mean the offshore book fully replaces the domestic one"},
    {"source": "NZGB-UST 10-year spread", "target": "NZDUSD", "sign": "+",
     "mechanism": "a small bond market with a high offshore ownership share; a modest global "
                  "reallocation is a large domestic flow and the hedged pickup is what drives it",
     "horizon": "5 to 60 sessions",
     "condition": "scaled by market size; unscaled the effect is invisible",
     "control": "the equivalent Australian spread and AUDUSD, scaled the same way",
     "falsifier": "a New Zealand effect no larger than Australia's per unit of index weight, "
                  "which would falsify the smallness mechanism"},
    {"source": "ANZ commodity price index, world terms", "target": "AUDNZD", "sign": "-",
     "mechanism": "the broadest free measure of New Zealand export prices; in the cross it is "
                  "measured against Australia's own, different export basket",
     "horizon": "20 to 90 sessions",
     "condition": "the WORLD-terms series only; the NZD-terms series already contains the "
                  "exchange rate and is partly circular",
     "control": "the NZD-terms series run deliberately as the circularity check",
     "falsifier": "the NZD-terms series performing better OUT of sample than the world-terms "
                  "series, which would mean the circularity is not what this pack claims"},
)

# --------------------------------------------------------------------------- eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    {"name": "post-crisis easing and the single price mandate", "start": "2011-03-01",
     "end": "2018-03-25",
     "regime": "a single price-stability mandate under a sole decision-maker (the Governor), with "
               "the 2014 tightening cycle reversed in 2015-2016",
     "markers": ("the 2014 hikes to 3.50%", "the 2015-2016 reversal to 1.75%"),
     "why_it_matters": "decisions were made by ONE person; a committee-era reaction function is "
                       "not the same object and should not be pooled with this",
     "status": "SETTLED"},
    {"name": "the dual mandate under a statutory committee", "start": "2018-03-26",
     "end": "2020-03-15",
     "regime": "an employment objective added to the remit in 2018 and a statutory Monetary "
               "Policy Committee with external members from 2019",
     "markers": ("2018-03 the employment objective", "2019-04 the MPC becomes statutory",
                 "2019-08 a 50bp cut that surprised almost every forecaster"),
     "why_it_matters": "the August 2019 surprise is the largest single OCR shock in the sample "
                       "and it happened in this regime, so any surprise-response estimate is "
                       "dominated by it unless the era is conditioned on",
     "status": "SETTLED"},
    {"name": "pandemic, LSAP and the Funding for Lending Programme", "start": "2020-03-16",
     "end": "2021-10-05",
     "regime": "an off-cycle 75bp cut to 0.25%, large scale asset purchases, and a funding "
               "programme that pushed mortgage rates to record lows",
     "markers": ("2020-03-16 the off-cycle cut", "2020-03 LSAP announced",
                 "2020-12 Funding for Lending begins"),
     "why_it_matters": "the OIS curve was pinned and carried no dispersion; a policy-surprise "
                       "study run here is measuring noise by construction",
     "status": "SETTLED"},
    {"name": "the tightening cycle", "start": "2021-10-06", "end": "2023-05-24",
     "regime": "0.25% to 5.50%, including a 75bp increase in November 2022; bond sales began in "
               "July 2022",
     "markers": ("2021-10-06 the first increase", "2022-11-23 the 75bp move",
                 "2023-05-24 the last increase to 5.50%"),
     "why_it_matters": "the richest era for NZ-A: frequent, large surprises against a curve that "
                       "had genuine dispersion",
     "status": "SETTLED"},
    {"name": "the 5.50% plateau and the return to a single mandate", "start": "2023-05-25",
     "end": "2024-08-13",
     "regime": "the OCR held at 5.50% while the employment objective was REMOVED from the remit "
               "in December 2023",
     "markers": ("2023-12 the employment objective removed",),
     "why_it_matters": "the mandate changed WITHOUT the rate changing, which is an unusually "
                       "clean natural experiment on the reaction function: the same economy, the "
                       "same rate, a different objective function",
     "status": "SETTLED"},
    {"name": "the easing cycle", "start": "2024-08-14", "end": "2099-12-31",
     "regime": "cuts from 5.50% as inflation returned toward the band",
     "markers": ("2024-08-14 the first cut",),
     "why_it_matters": "UNVERIFIED TAIL. Anything this pack asserts about 2025-2026 policy must be "
                       "re-read from rbnz.govt.nz before a study conditions on it; the desk's "
                       "knowledge of this era is not point-in-time and is treated as UNMEASURED",
     "status": "UNVERIFIED_TAIL"},
)

# --------------------------------------------------------------------------- access constraints
ACCESS_CONSTRAINTS: tuple[dict[str, Any], ...] = (
    {"constraint": "no NZ short-rate instrument is quoted here",
     "measured": "no 90-day bank bill future and no OIS in data/universe/universe.json",
     "consequence": "unlike Australia, the RBNZ surprise has NO on-broker consensus proxy. A "
                    "meeting whose OIS-implied path cannot be sourced has an UNMEASURED surprise "
                    "and must be reported as such, never as a zero surprise"},
    {"constraint": "no New Zealand equity index is quoted here",
     "measured": "no NZX symbol in the universe registry",
     "consequence": "NZ-G is a transmission-target domain: AUS200 is the nearest proxy and the "
                    "NZX 50's GROSS construction makes even that comparison biased unless the "
                    "dividend yield is adjusted for"},
    {"constraint": "GDT full event data is a licensed product",
     "measured": "globaldairytrade.info publishes headline results free; the detailed round-by-"
                 "round data is behind a licence",
     "consequence": "the desk mines the free headline series. Round-level bidding dynamics are "
                    "UNMEASURED and are declared so rather than approximated"},
    {"constraint": "the GDT publication minute is DECLARED, not verified",
     "measured": "this pack assumes an auction start of roughly 14:00 UTC and publication around "
                 "15:00 UTC",
     "consequence": "an intraday NZ-C event study is only as good as that minute. The miner must "
                    "verify it against globaldairytrade.info before conditioning on it; a study "
                    "run on the wrong minute measures the hour, not the auction"},
    {"constraint": "NZDJPY carries a 147-point median spread against AUDJPY's 0",
     "measured": "universe.json median_spread_pts: NZDJPY 147, AUDJPY 0, NZDUSD 0",
     "consequence": "the New Zealand carry leg's cost floor is materially higher than the "
                    "Australian one; every NZ-F cell must clear it explicitly and a Sharpe "
                    "computed gross of it is not a Sharpe"},
)

# --------------------------------------------------------------------------- assembly
_PACK_FIELDS: tuple[str, ...] = (
    "code", "name", "region_command", "currency", "executable_instruments", "central_bank",
    "fixing_conventions", "settlement_conventions", "exchanges", "holidays_rule",
    "fiscal_year_end", "positioning_sources", "native_languages", "terminology", "source_classes",
    "datasets", "actors", "domains", "custom_miners", "transmission_edges_seed", "policy_eras")


def as_dict() -> dict[str, Any]:
    """The pack as a plain mapping, with the fields the frozen dataclass has no slot for carried
    alongside it so nothing is silently dropped."""
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
    """`libs.research.country_lab.CountryPack` when that module has landed, else this mapping.

    Imported lazily: the framework is a sibling builder's file and any failure to construct the
    dataclass degrades to the mapping rather than raising, because the DATA is the deliverable.
    """
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
