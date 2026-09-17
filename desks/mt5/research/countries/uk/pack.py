"""THE UNITED KINGDOM PACK -- a noon decision, a morning settlement average, and Thursday dividends.

Sixteen actors with their eleven fields, fourteen domains A..N with objects, conditions,
instruments and negative controls, ten datasets with all six point-in-time stamps, twelve
transmission edges naming real Fusion symbols, nine policy eras, and a bank-holiday calendar
derived from the rule -- substitution law included, because the UK is the only country in this
department that HAS one.

FOUR THINGS THIS PACK INSISTS ON.

  * THE UK IS THE ONE COUNTRY HERE WITH AN EXECUTABLE BOND LEG, AND ITS HISTORY IS SHORT.
    UKGILT's H1 bars on this box begin 2024-02-26 (measured 2026-09-17, from the desk's own
    parquet). Everything before that -- the LDI episode, the whole hiking cycle, the start of QT
    -- has no gilt series on this desk. Every gilt era row carries that by name, because a gate
    that cannot run is a claim the desk cannot cash (L1.49).
  * THE SUBSTITUTION RULE IS REAL AND IT MOVES DATES. When Christmas Day falls on a Saturday the
    bank holiday moves to the following Monday, and Boxing Day's to the Tuesday. No other
    calendar in this department substitutes. `bank_holidays` implements it, so the UK closure
    count is stable at eight where the Nordic and CEE counts are not -- and that difference is
    itself a cross-country control.
  * THE EDSP IS NOT THE CLOSE. UK100 index derivatives settle on an average of FTSE 100 values
    between 10:10 and 10:30 London. A study that keys a UK expiry effect to the close is looking
    six hours after the event.
  * EX-DIVIDEND IS A THURSDAY EFFECT. The mechanical index drop is concentrated on one weekday by
    market convention, which means any UK day-of-week study that ignores dividends is measuring
    the dividend calendar and calling it a Thursday anomaly.
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta
from typing import Any

from countries import actor, build_pack, dataset, domain, edge, era, miner, source_class

CODE = "GB"
NAME = "United Kingdom"
REGION_COMMAND = "UK"
CURRENCY = "GBP"

PIT_STAMPS: tuple[str, ...] = ("event_time", "period_time", "publication_time", "available_time",
                               "revision_time", "retrieval_time")

#: The sterling complex plus every London-priced instrument the broker quotes. This is the
#: longest executable list in the department and it is why the UK is the one country whose rates
#: hypotheses need not be routed through its currency.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    # sterling against the majors
    "GBPUSD", "EURGBP", "GBPJPY", "GBPCHF", "GBPAUD", "GBPCAD", "GBPNZD",
    # sterling against the European periphery of currencies
    "GBPSEK", "GBPNOK", "GBPDKK", "GBPPLN", "GBPHUF",
    # sterling against the rest
    "GBPSGD", "GBPTRY", "GBPZAR", "GBPMXN",
    # the London-priced complex
    "UK100", "UKGILT", "XBRUSD", "UKCOCOA", "XAUUSD", "XAGUSD", "USDX",
)

#: MEASURED ON THIS BOX 2026-09-17 from the desk's own parquet files. Carried because a bar
#: history is a hard constraint on which eras are testable and nothing else in the repository
#: states it per symbol.
BARS_FROM: dict[str, str] = {
    "GBPUSD": "2018-01-02", "EURGBP": "2018-01-02",
    "UK100": "2020-09-14", "XBRUSD": "2020-09-14", "UKCOCOA": "2020-09-14",
    "XAUUSD": "2018-03-19",
    "UKGILT": "2024-02-26",
}

#: What the UK's economics run through that Fusion does not quote.
TRANSMISSION_TARGETS: tuple[dict[str, str], ...] = (
    {"name": "The 10-year gilt YIELD (as opposed to the Long Gilt future)",
     "venue": "OTC / Tradeweb",
     "role": "UKGILT is the FUTURE and the desk has it only from 2024-02-26. The cash yield "
             "series is what every historical UK study needs and it is not on this box.",
     "route": "UKGILT from 2024 onward; GBPUSD and UK100 for anything earlier"},
    {"name": "Index-linked gilts (linkers) and the RPI-CPIH reform",
     "venue": "OTC",
     "role": "the instrument LDI strategies actually held, and the one whose 2030 index change "
             "is a scheduled, legislated valuation event",
     "route": "UKGILT, GBPUSD -- the linker leg itself is unavailable"},
    {"name": "SONIA futures and the OIS curve", "venue": "ICE Futures Europe",
     "role": "the market-implied Bank Rate path; the only way to turn a decision into a SURPRISE",
     "route": "GBPUSD, UK100, UKGILT -- an input, never a leg"},
    {"name": "FTSE 250", "venue": "London Stock Exchange",
     "role": "the domestically-exposed UK index. THE FTSE 100 IS NOT A UK ECONOMY INDEX -- most "
             "of its revenue is foreign and it RISES when sterling falls. The FTSE 250 is the "
             "domestic read and the desk cannot trade it.",
     "route": "UK100 is the wrong sign for a UK-domestic hypothesis and the pack says so"},
    {"name": "UK residential property price indices (Nationwide, Halifax, ONS/Land Registry)",
     "venue": "lender and ONS publications",
     "role": "the housing channel's observable; Nationwide prints on the first working day of "
             "the month, which is the fastest housing read in Europe after Norway's",
     "route": "GBPUSD, UK100"},
    {"name": "The Bank of England Asset Purchase Facility gilt sales calendar",
     "venue": "Bank of England",
     "role": "a PRE-ANNOUNCED, sized, one-way supply operation with published dates -- the UK's "
             "closest analogue to Norway's announced FX amount",
     "route": "UKGILT from 2024; GBPUSD earlier"},
    {"name": "UK natural gas (NBP) and the day-ahead power price",
     "venue": "ICE / EPEX",
     "role": "the UK energy channel; NBP gas and TTF are coupled by interconnector and neither "
             "is a Fusion symbol",
     "route": "UK100, GBPUSD; XBRUSD is executable and is the crude leg only"},
)


def easter_sunday(year: int) -> date:
    """Gregorian Easter. Two of the eight England-and-Wales bank holidays hang off it."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    ell = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ell) // 451
    month = (h + ell - 7 * m + 114) // 31
    day = ((h + ell - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _first_weekday(year: int, month: int, weekday: int) -> date:
    first = date(year, month, 1)
    return date(year, month, 1 + (weekday - first.weekday()) % 7)


def _last_weekday(year: int, month: int, weekday: int) -> date:
    day = date(year + (month == 12), (month % 12) + 1, 1) - timedelta(days=1)
    while day.weekday() != weekday:
        day -= timedelta(days=1)
    return day


def _substitute(day: date, taken: set[date]) -> date:
    """The UK substitution rule: a bank holiday falling at a weekend moves to the next weekday
    that is not already a bank holiday. This is why Christmas on a Saturday costs Monday AND
    Tuesday, and it is the reason the UK closure count is stable at eight while the Nordic and
    CEE counts vary year to year."""
    out = day
    while out.weekday() >= 5 or out in taken:
        out += timedelta(days=1)
    return out


def bank_holidays(year: int) -> dict[date, str]:
    """England and Wales bank holidays, substitution applied. The LSE follows this calendar.

    Eight days every year, without exception, because of the substitution rule -- the only
    calendar in this department with that property. Scotland (2 January, the first Monday in
    August, St Andrew's Day) and Northern Ireland (St Patrick's Day, the Twelfth) differ, and
    neither closes the exchange; they close BANKS, so a Scottish settlement date can differ from
    a London one.
    """
    e = easter_sunday(year)
    taken: set[date] = set()
    out: dict[date, str] = {}

    def add(day: date, label: str) -> None:
        placed = _substitute(day, taken)
        taken.add(placed)
        suffix = "" if placed == day else f" (substitute day for {day.isoformat()})"
        out[placed] = label + suffix

    add(date(year, 1, 1), "New Year's Day")
    good_friday = e - timedelta(days=2)
    taken.add(good_friday)
    out[good_friday] = "Good Friday"
    easter_monday = e + timedelta(days=1)
    taken.add(easter_monday)
    out[easter_monday] = "Easter Monday"
    early_may = _first_weekday(year, 5, 0)
    taken.add(early_may)
    out[early_may] = "Early May bank holiday (first Monday in May)"
    spring = _last_weekday(year, 5, 0)
    taken.add(spring)
    out[spring] = "Spring bank holiday (last Monday in May)"
    summer = _last_weekday(year, 8, 0)
    taken.add(summer)
    out[summer] = "Summer bank holiday (last Monday in August)"
    add(date(year, 12, 25), "Christmas Day")
    add(date(year, 12, 26), "Boxing Day")
    return out


def holidays(year: int) -> dict[date, str]:
    """The LSE trading calendar: the England and Wales bank holidays, unchanged.

    The exchange does not add closures of its own -- no Christmas Eve, no New Year's Eve, no
    Berchtoldstag, no Midsommarafton. London is the most continuously open market in this
    department and that is itself the comparison: a UK calendar effect cannot be a closure
    artefact, because there are almost no closures to be an artefact of.
    """
    return bank_holidays(year)


def scottish_only_bank_holidays(year: int) -> dict[date, str]:
    """Scottish bank holidays that are NOT England and Wales ones. Banks shut, LSE trades.

    Carried because a sterling SETTLEMENT date computed against a single "UK" calendar is wrong
    on these days for a Scottish counterparty, and because 2 January is one of them -- the same
    date as Switzerland's Berchtoldstag, in the same thin week.
    """
    taken: set[date] = set()
    out: dict[date, str] = {}
    second = _substitute(date(year, 1, 2), taken)
    taken.add(second)
    out[second] = "2 January (Scotland only; England and Wales trade and settle)"
    out[_first_weekday(year, 8, 0)] = "Summer bank holiday, Scotland (FIRST Monday in August, "
    out[_first_weekday(year, 8, 0)] += "three weeks before the England and Wales one)"
    andrew = _substitute(date(year, 11, 30), taken)
    out[andrew] = "St Andrew's Day (Scotland only)"
    return out


def third_friday(year: int, month: int) -> date:
    """UK100 index-derivative expiry: the third Friday, with the EDSP struck 10:10-10:30 London."""
    first = date(year, month, 1)
    return date(year, month, 1 + (4 - first.weekday()) % 7 + 14)


def uk100_expiry(year: int, month: int) -> date:
    """The third Friday, rolled back over a bank holiday.

    Good Friday can and does fall on a third Friday -- 2019-04-19, 2022-04-15, 2025-04-18 and
    2030-04-19 all are -- so the roll-back is not hypothetical. In April 2025 the expiry moved to
    Thursday the 17th. A hard-coded third-Friday rule tests a closed market in four years out of
    thirteen, and the desk's own bars cover two of them.
    """
    day = third_friday(year, month)
    closures = set(holidays(year))
    while day.weekday() >= 5 or day in closures:
        day -= timedelta(days=1)
    return day


def uk_fiscal_year(day: date) -> str:
    """The UK government financial year containing `day`: 1 April to 31 March.

    The PERSONAL tax year is a different thing again -- 6 April to 5 April -- and the five-day
    gap between them is where the DMO's remit year and the retail ISA season sit side by side.
    """
    start = day.year if day.month >= 4 else day.year - 1
    return f"{start}-{str(start + 1)[-2:]}"


def _iso(table: dict[date, str]) -> dict[str, str]:
    return {d.isoformat(): n for d, n in sorted(table.items())}


HOLIDAYS_RULE: dict[str, Any] = {
    "calendar": "England and Wales bank holidays (the LSE calendar), with the Scottish-only days "
                "beside them",
    "rule": "EIGHT days every year: New Year's Day, Good Friday, Easter Monday, the first Monday "
            "in May, the last Monday in May, the last Monday in August, Christmas Day and Boxing "
            "Day. A fixed-date holiday falling at a weekend SUBSTITUTES to the next weekday not "
            "already taken -- which is why Christmas on a Saturday costs both the Monday and the "
            "Tuesday. The substitution rule is implemented in `_substitute` and is unique to "
            "this pack: no other country in this department has one, so the UK closure count is "
            "constant at eight while the Nordic and CEE counts vary.",
    "function": "countries.uk.pack:bank_holidays",
    "table": {y: _iso(bank_holidays(y)) for y in (2024, 2025, 2026)},
    "scottish_only": {y: _iso(scottish_only_bank_holidays(y)) for y in (2024, 2025, 2026)},
    "asymmetries": (
        "The LSE adds NO closures of its own -- no Christmas Eve, no New Year's Eve. London "
        "trades on days when Xetra, SIX, Nasdaq Stockholm and Oslo are all shut, which makes it "
        "the natural control leg for every continental closure study in this department.",
        "2 January: Scottish banks are shut and the LSE trades. Switzerland is shut the same day. "
        "A GBPCHF value date in that week is constrained on the Swiss side and, for a Scottish "
        "counterparty, on the sterling side too.",
        "Scotland's summer bank holiday is the FIRST Monday in August and England's is the LAST "
        "-- three weeks apart, which is a genuinely odd fact about one country's calendar.",
        "Good Friday can be the third Friday: 2019-04-19, 2022-04-15, 2025-04-18 and "
        "2030-04-19 all are, so those months' UK100 expiries roll back a day. "
        "`uk100_expiry` handles it; a hard-coded third-Friday rule tests a closed market.",
        "The substitution rule means a per-year normalisation over UK trading days is SAFE "
        "at a constant eight closures -- the only calendar here where that is true.",
    ),
    "status": "DERIVED_FROM_RULE",
    "verified": {"2026-05-25": "Spring bank holiday 2026, the last Monday in May",
                 "2025-04-18": "Good Friday AND the third Friday -- the expiry rolled back to "
                               "Thursday 2025-04-17, which `uk100_expiry` computes"},
}

CENTRAL_BANK: dict[str, Any] = {
    "name": "Bank of England",
    "committee": "the Monetary Policy Committee -- nine members, five internal and four external, "
                 "and the INDIVIDUAL VOTE of each is published with the decision. That makes the "
                 "UK's reaction function attributable person by person, which no other central "
                 "bank in this department allows.",
    "policy_rates": ("Bank Rate",),
    "operational_framework": "a floor system: reserves are remunerated at Bank Rate, so Bank "
                             "Rate is the effective overnight rate and SONIA tracks it closely. "
                             "The balance sheet is steered separately through the Asset Purchase "
                             "Facility, and QT is a SEPARATE annual decision taken each "
                             "September -- a second, dated policy event with its own calendar.",
    "decision_rule": "EIGHT meetings a year, announced at 12:00 London. Since the 2015 reform "
                     "the DECISION, the VOTE SPLIT and the MINUTES are all published in that one "
                     "instant; four times a year (February, May, August, November) the Monetary "
                     "Policy Report and the press conference come with them.",
    "announcement_local": "12:00 London",
    "announcement_utc": {"winter_gmt": "12:00Z", "summer_bst": "11:00Z"},
    "press_conference_local": "12:30 London on Report days",
    "dst_note": "London is GMT (=UTC) from the last Sunday in October to the last Sunday in "
                "March and BST (=UTC+1) otherwise. The switch weekends are the SAME as the euro "
                "area's, so the London-Frankfurt offset is a constant hour all year; it is the "
                "London-to-New-York offset that breaks for two weeks in March and one in "
                "November. A 12:00 London announcement lands at 07:00 or 08:00 New York "
                "depending on the season, which is either before or after the US cash open in "
                "different parts of the year -- and that alone changes what else is in the "
                "window.",
    "time_change_note": "THE STRUCTURE CHANGED IN AUGUST 2015. Before that the minutes were "
                        "published roughly two weeks after the decision, as a SECOND event; "
                        "since then they land at the same instant. Any study of UK policy "
                        "events spanning 2015-08 is pooling a one-event regime with a two-event "
                        "one. The announcement CLOCK (12:00 London) has been stable throughout.",
    "reports": "the Monetary Policy Report (formerly the Inflation Report) is published at the "
               "February, May, August and November meetings with the press conference; the other "
               "four meetings carry the decision, vote and minutes alone",
    "decisions": {
        "2024": {"dates": ("2024-02-01", "2024-03-21", "2024-05-09", "2024-06-20", "2024-08-01",
                           "2024-09-19", "2024-11-07", "2024-12-19"),
                 "confidence": "high -- the eight published 2024 MPC announcement dates, all "
                               "Thursdays at 12:00 London"},
        "2025": {"dates": ("2025-02-06", "2025-03-20", "2025-05-08", "2025-06-19", "2025-08-07",
                           "2025-09-18", "2025-11-06", "2025-12-18"),
                 "confidence": "high -- the eight published 2025 MPC announcement dates"},
        "2026": {"dates": ("2026-02-05", "2026-03-19", "2026-05-07", "2026-06-18", "2026-08-06",
                           "2026-09-17", "2026-11-05", "2026-12-17"),
                 "confidence": "DECLARED, UNVERIFIED -- derived from the standing pattern "
                               "(Thursday, eight a year, Reports in February, May, August and "
                               "November). Re-read bankofengland.co.uk before any 2026 event "
                               "study: a wrong date does not weaken the study, it relocates it "
                               "onto a day when nothing happened."},
    },
    "rule_if_dates_unknown": "a Thursday, eight times a year, roughly every six weeks, with "
                             "Monetary Policy Reports in February, May, August and November; "
                             "announcement 12:00 London, press conference 12:30 on Report days.",
    "qt_decision": "the ANNUAL QT envelope is decided at the September meeting and runs from "
                   "October to September. It is a separate, dated, sized supply decision and it "
                   "has been revised downward once -- which makes September a second UK policy "
                   "event every year that most event calendars do not carry.",
    "source": "https://www.bankofengland.co.uk/monetary-policy/upcoming-mpc-dates",
}

FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "WM/Refinitiv 16:00 London closing spot rate (the 4pm fix)",
     "administrator": "LSEG (WM/Refinitiv)",
     "local_time": "16:00 London",
     "utc": {"winter": "16:00Z", "summer": "15:00Z"},
     "dst_note": "GMT in winter, BST in summer, switching the last Sunday of March and October. "
                 "THE FIX IS DEFINED IN LONDON TIME, so its UTC hour moves twice a year while "
                 "its London hour never does. A backtest keyed to 16:00 UTC is an hour late for "
                 "seven months of every year and is testing an ordinary minute.",
     "window": "a five-minute window, 15:57:30-16:02:30 London, median of sampled rates and "
               "trades. It was WIDENED from one minute to five in 2015 after the fixing "
               "investigations -- a microstructure regime break inside the benchmark itself.",
     "what_it_prices": "the rate essentially every global equity and bond index converts at",
     "why_it_matters": "this is a LONDON benchmark. The UK is the only country in this "
                       "department whose own session contains the fix that moves everyone "
                       "else's month-end, which means UK liquidity conditions are an input to a "
                       "global flow rather than a recipient of one."},
    {"name": "SONIA",
     "administrator": "Bank of England",
     "local_time": "09:00 London on the following business day",
     "utc": {"winter": "09:00Z", "summer": "08:00Z"},
     "dst_note": "GMT/BST. Published on UK business days only, so the Easter and Christmas gaps "
                 "are longer than a weekend and a naive daily difference shows a spurious jump.",
     "window": "volume-weighted trimmed mean of the prior day's unsecured overnight sterling "
               "transactions",
     "what_it_prices": "actual overnight sterling; the reference that replaced LIBOR in "
                       "essentially every sterling contract",
     "why_it_matters": "SONIA minus Bank Rate is the sterling liquidity observable, and it "
                       "widened visibly as the Term Funding Scheme repayments drained reserves "
                       "-- a dated, scheduled drain with a published repayment profile"},
    {"name": "LBMA Gold Price",
     "administrator": "ICE Benchmark Administration",
     "local_time": "10:30 and 15:00 London",
     "utc": {"winter": "10:30Z and 15:00Z", "summer": "09:30Z and 14:00Z"},
     "dst_note": "London clock; both fixes move with BST. The 15:00 London fix is the settlement "
                 "price for the physical market and lands one hour before the WMR currency fix, "
                 "so on month-end days the gold and sterling benchmark flows are adjacent rather "
                 "than simultaneous -- a separation a study can actually use.",
     "window": "an electronic auction with price rounds until the imbalance is inside tolerance",
     "what_it_prices": "physical gold settlement worldwide",
     "why_it_matters": "London is the physical gold market's clearing centre; XAUUSD and XAGUSD "
                       "are executable here and the fix that prices them is a UK-session event"},
    {"name": "LBMA Silver Price",
     "administrator": "ICE Benchmark Administration",
     "local_time": "12:00 London",
     "utc": {"winter": "12:00Z", "summer": "11:00Z"},
     "dst_note": "London clock: GMT (=UTC) in winter, BST (=UTC+1) in summer, switching the"
                 "last Sunday of March and October. The silver fix sits BETWEEN the two gold"
                 "fixes and inside the UK lunch hour, so the gold-silver ratio has a London"
                 "intraday shape that is an artefact of three auction times rather than of"
                 "any metal fundamental -- and both legs are executable here.",
     "window": "an electronic auction",
     "what_it_prices": "physical silver settlement",
     "why_it_matters": "silver's fix sits between the two gold fixes and inside the UK lunch "
                       "hour; the gold-silver ratio has a London intraday shape for that reason "
                       "alone and it is testable on XAUUSD and XAGUSD, both executable"},
    {"name": "FTSE 100 closing auction and official close",
     "administrator": "London Stock Exchange / FTSE Russell",
     "local_time": "closing auction 16:30-16:35 London with a RANDOM end inside the last 30 "
                   "seconds",
     "utc": {"winter": "16:30-16:35Z", "summer": "15:30-15:35Z"},
     "dst_note": "London clock: GMT (=UTC) in winter and BST (=UTC+1) in summer, so the "
                 "uncrossing is 16:30-16:35Z in winter and 15:30-15:35Z in summer. Note "
                 "it runs AFTER the 16:00 WMR currency fix, so on "
                 "month-end the sterling flow and the equity flow are half an hour apart and can "
                 "be separated -- unlike in Frankfurt or Paris, where the closing auction and "
                 "the fix are closer together.",
     "window": "a five-minute call with a randomised uncrossing, specifically so the exact "
               "instant cannot be gamed",
     "what_it_prices": "the official close every UK index fund must match",
     "why_it_matters": "the RANDOM END is the mechanic: it converts a single defendable instant "
                       "into a distribution, which changes the whole hedging problem relative to "
                       "the DAX's fixed 13:00 CET auction"},
    {"name": "UK100 Exchange Delivery Settlement Price (EDSP)",
     "administrator": "ICE Futures Europe",
     "local_time": "an average of FTSE 100 index values between 10:10 and 10:30 London on the "
                   "third Friday",
     "utc": {"winter": "10:10-10:30Z", "summer": "09:10-09:30Z"},
     "dst_note": "London clock: GMT (=UTC) in winter and BST (=UTC+1) in summer, so the "
                 "averaging window is 10:10-10:30Z in winter and 09:10-09:30Z in "
                 "summer. The settlement happens in the MORNING and the session then runs "
                 "another six hours with the expiry behind it -- the opposite shape from the "
                 "DAX's midday auction and from Sweden's whole-day average.",
     "window": "a twenty-minute averaging window",
     "what_it_prices": "the final settlement of FTSE 100 futures and options",
     "why_it_matters": "a twenty-minute average is long enough that a single print cannot set it "
                       "and short enough to be defended, which is a genuinely different "
                       "incentive from either a single auction or a whole-day average. The UK, "
                       "Germany and Sweden give three different answers to the same problem and "
                       "the desk can trade two of them."},
)

SETTLEMENT_CONVENTIONS: dict[str, Any] = {
    "fx_spot": "T+2 for GBPUSD and the sterling crosses; the value date must be good in both "
               "currencies, and because the LSE adds no closures of its own the sterling leg is "
               "constrained on only eight days a year",
    "fx_value_date_note": "Easter costs the UK Friday AND Monday, the same as the euro area, so "
                          "the GBP and EUR legs of EURGBP move together at Easter and diverge at "
                          "Whit Monday, 24 and 31 December, when Germany is shut and London is "
                          "not. EURGBP is therefore the department's cleanest one-sided-closure "
                          "pair.",
    "cls": "GBP settles in CLS; so do every counter-currency in this pack's executable list "
           "except PLN. GBPPLN is the one sterling pair here carrying principal settlement risk.",
    "cash_equity": "T+2 on the LSE today. The UK has committed to T+1 on 11 OCTOBER 2027, the "
                   "same date as the EU and Switzerland (declared -- verify against the "
                   "Accelerated Settlement Taskforce). A T+1 move shifts every month-end FX "
                   "hedging deadline by one business day, so every month-end study in this pack "
                   "has a scheduled structural break in 2027.",
    "gilts": "T+1 for gilts -- ALREADY, and this is not a typo. UK government bonds have settled "
             "T+1 for years while UK equities settle T+2, so a cash-and-carry or "
             "asset-swap trade spans two different settlement conventions inside one country.",
    "derivatives": "UK100 futures and options are cash-settled against the 10:10-10:30 EDSP; "
                   "UKGILT (the Long Gilt future) is PHYSICALLY DELIVERABLE against a basket, "
                   "which means it has a cheapest-to-deliver and a delivery month -- the only "
                   "instrument in this department with that structure, and it makes the roll a "
                   "real economic event rather than a bookkeeping one",
    "month_end": "the 16:00 WMR fix on the T-2 date carries the FX flow; the 16:30-16:35 closing "
                 "auction carries the equity flow half an hour later. Two separable windows on "
                 "the same afternoon.",
    "fiscal_boundaries": "the government financial year ends 31 March and the personal tax year "
                         "ends 5 April. Five days apart, and both matter: the DMO's remit year "
                         "turns on the first and the retail ISA subscription deadline is the "
                         "second.",
}

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "London Stock Exchange", "mic": "XLON", "tz": "Europe/London",
     "symbols": ("UK100",),
     "session_local": "08:00-16:30 London continuous, closing auction 16:30-16:35 with a random "
                      "uncrossing in the final 30 seconds",
     "expiry_rule": "third Friday of the expiry month, rolled back over a bank holiday. "
                    "`uk100_expiry` computes it, and the roll-back is not hypothetical: "
                    "2025-04-18 was both Good Friday and the third Friday, and the expiry "
                    "moved to Thursday the 17th.",
     "settlement_price_rule": "the EDSP is an AVERAGE OF FTSE 100 INDEX VALUES BETWEEN 10:10 AND "
                              "10:30 LONDON on the last trading day -- a morning window, six "
                              "hours before the close. Confidence: DECLARED from public "
                              "knowledge; verify against the ICE Futures Europe contract "
                              "specification before keying a study to the print.",
     "witching": "the quarterly March, June, September and December cycle",
     "notes": "the LSE adds NO closures beyond the eight bank holidays, which makes UK100 the "
              "control leg for every continental closure study in this department"},
    {"name": "ICE Futures Europe", "mic": "IFLL", "tz": "Europe/London",
     "symbols": ("UK100", "UKGILT", "XBRUSD", "UKCOCOA"),
     "session_local": "electronic sessions well beyond the cash hours; Brent trades nearly 23 "
                      "hours",
     "expiry_rule": "UK100 on the third Friday; UKGILT on a delivery-month cycle with a notice "
                    "period; Brent expires on the last business day of the second month "
                    "preceding the contract month",
     "settlement_price_rule": "UK100 on the EDSP average; UKGILT is PHYSICALLY DELIVERED against "
                              "a basket, so the future tracks a cheapest-to-deliver gilt and the "
                              "roll has real economics; Brent settles against the ICE Brent "
                              "Index.",
     "witching": "shared with the UK100 cycle",
     "notes": "four executable London contracts on one venue -- the densest executable cluster "
              "in this department, and the reason the UK pack can test a rates hypothesis "
              "without routing it through the currency"},
)

POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "CFTC Commitments of Traders -- British Pound (CME contract 6B)",
     "covers": "GBP", "published": "Friday 15:30 ET for Tuesday's positions", "lag_days": 3.0,
     "licence": "public domain", "root": "https://www.cftc.gov/MarketReports/CommitmentsofTraders/",
     "note": "sterling has one of the longest and cleanest COT histories, and its speculative "
             "position has been a genuine regime variable -- most obviously around the 2016 "
             "referendum and the 2022 mini-Budget, both of which produced record short readings. "
             "The Tuesday snapshot and Friday publication mean a Wednesday-to-Friday move is "
             "invisible until the following week."},
    {"name": "Bank of England Asset Purchase Facility sales calendar",
     "covers": "the size and dates of QT gilt sales",
     "published": "quarterly schedule, announced in advance", "lag_days": 0.0,
     "licence": "public", "root": "https://www.bankofengland.co.uk/markets/",
     "note": "a PRE-ANNOUNCED, sized, one-way supply operation with published dates -- the "
             "closest UK analogue to Norway's announced daily FX amount, and the only forced "
             "flow in this pack that is knowable before it happens"},
    {"name": "UK DMO auction and syndication calendar",
     "covers": "gilt supply", "published": "quarterly calendar; the annual remit at the Budget",
     "lag_days": 0.0, "licence": "public", "root": "https://www.dmo.gov.uk/",
     "note": "THE REMIT IS PUBLISHED AT THE SAME INSTANT AS THE BUDGET. That makes the fiscal "
             "event and the supply event simultaneous, which is convenient for a trader and "
             "awkward for an econometrician: the two cannot be separated by time and must be "
             "separated by instrument."},
    {"name": "FCA short-selling disclosures and LSE open interest",
     "covers": "disclosed net short positions and index derivative open interest",
     "published": "daily", "lag_days": 1.0, "licence": "public",
     "root": "https://www.fca.org.uk/markets/short-selling",
     "note": "the equity half is forbidden hypothesis ground under the two-lane order; the index "
             "open interest is usable for the expiry domain"},
    {"name": "Bank of England Money and Credit statistics",
     "covers": "mortgage approvals, consumer credit, deposits", "published": "monthly, around "
               "the end of the following month", "lag_days": 30.0, "licence": "public",
     "root": "https://www.bankofengland.co.uk/statistics/money-and-credit",
     "note": "mortgage APPROVALS lead completions by roughly three months, so this is the "
             "leading edge of the housing channel and it is published at 09:30 London"},
)

NATIVE_LANGUAGES: tuple[str, ...] = ("en-GB",)

#: UK market vocabulary. English, but not international English: a search for "government bond"
#: on a British source finds the explanation and a search for "gilt" finds the market. `linker`,
#: `EDSP`, `Super Thursday`, `ISA season`, `SVR` and `the Twelfth` are all terms that mean
#: nothing outside the UK and everything inside it.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "en-GB_policy": ("Bank Rate", "the MPC", "Monetary Policy Report", "Super Thursday",
                     "the vote split", "hold or cut", "the minutes", "forward guidance",
                     "the Governor", "external member", "dissent"),
    "en-GB_rates": ("gilt", "gilts", "gilt-edged market maker", "GEMM", "linker",
                    "index-linked gilt", "conventional gilt", "the long end", "strips",
                    "the DMO remit", "syndication", "tap", "auction tail", "cover ratio",
                    "cheapest-to-deliver", "the gilt roll", "SONIA", "OIS", "the swap spread"),
    "en-GB_qt": ("quantitative tightening", "QT", "the APF", "gilt sales", "the envelope",
                 "run-off", "reinvestment", "the indemnity", "Term Funding Scheme", "TFSME"),
    "en-GB_equity": ("the Footsie", "FTSE 100", "FTSE 250", "the closing auction",
                     "the random uncrossing", "EDSP", "triple witching", "ex-dividend",
                     "ex-div Thursday", "the quarterly review", "free float", "stamp duty",
                     "SDRT", "the AIM market"),
    "en-GB_fx": ("cable", "the 4pm fix", "the London fix", "sterling", "quid",
                 "the trade-weighted index", "carry", "the Brexit premium"),
    "en-GB_fiscal": ("the Budget", "the Autumn Statement", "the Spring Statement", "the OBR",
                     "the Economic and Fiscal Outlook", "headroom", "the fiscal rules",
                     "the remit", "the tax year", "ISA season", "the 5 April deadline"),
    "en-GB_housing": ("the mortgage cliff", "fixed-rate roll-off", "tracker mortgage",
                      "standard variable rate", "SVR", "loan-to-value", "stress test",
                      "Nationwide HPI", "Halifax HPI", "mortgage approvals", "remortgaging"),
    "en-GB_market": ("bank holiday", "the Twelfth", "Boxing Day", "the substitute day",
                     "the summer lull", "the City", "the Square Mile", "LDI",
                     "liability-driven investment", "bulk purchase annuity", "the gilts crisis"),
    "en-GB_commodity": ("the LBMA", "the London fix", "loco London", "the vaults",
                        "ICE Brent", "the Brent complex", "London cocoa", "terminal market"),
}

# --------------------------------------------------------------------------- source taxonomy
#: THE TEN LAYERS (principal's per-country depth rule, 2026-09-17). A country is NEVER "covered"
#: by five obvious sources. Every layer is either NAMED with at least one source or declared
#: ABSENT WITH A REASON in `LAYER_ABSENCES`; a blank is not an available answer, and
#: `source_layer_coverage()` is the audit that proves which of the two happened.
LAYERS: tuple[str, ...] = ("official", "institutional", "academic", "practitioner",
                           "retail_ecology", "app_ecosystem", "media", "archive",
                           "physical_economy", "source_graph")
#: HOW the material may be obtained. Says nothing whatever about whether it is true.
ACCESS_LABELS: tuple[str, ...] = (
    "PUBLIC", "PUBLIC_WITH_TERMS", "LICENSED", "OPEN_DATA", "PUBLIC_ARCHIVE", "PUBLIC_SOCIAL",
    "USER_SUBMITTED", "ACCESS_UNCLEAR", "PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")
#: HOW MUCH the desk believes it. Orthogonal to access: an AUTHORITATIVE page is often PUBLIC and
#: so is a FRINGE one.
CREDIBILITY: tuple[str, ...] = ("AUTHORITATIVE", "RELIABLE", "UNRELIABLE", "FRINGE",
                                "CONTRADICTED", "UNKNOWN")
#: WHETHER IT HAS EVER PREDICTED ANYTHING ON THIS DESK. Orthogonal to both of the above. An
#: AUTHORITATIVE source can be NOT_PREDICTIVE and a FRINGE one PREDICTIVE, and collapsing these
#: three axes into one score is how a desk mistakes prestige for edge.
PREDICTIVE_STATES: tuple[str, ...] = ("UNTESTED", "PREDICTIVE", "NOT_PREDICTIVE",
                                      "NARRATIVE_FEATURE")


def _src(sid: str, label: str, *, layer: str, roots: Sequence[str], languages: Sequence[str],
         licence: str, access_label: str, credibility: str, predictive_state: str,
         queries: Sequence[str], machine_use_allowed: bool = True, weight: float = 1.0,
         notes: str = "") -> dict[str, Any]:
    """One source class, carrying its LAYER and THREE INDEPENDENT LABELS.

    FRINGE, CONTRADICTORY OR PLAINLY FALSE PUBLIC MATERIAL IS KEPT, at low `weight`, as an
    evidence object. It is never dropped: what a crowd believes wrongly is itself a tradable
    fact, and a corpus that deletes the wrong claims can no longer measure the belief.

    A page whose terms forbid machine extraction is registered with `machine_use_allowed=False`
    and is NEVER SCRAPED AND NEVER OMITTED. The desk records that the source exists and that a
    machine may not read it, which is a measurement rather than a gap (L1.28a).

    `queries` are in the SOURCE'S OWN LANGUAGE and in its traders' own slang. A translated
    English query against a German board returns the German word for nothing.
    """
    if layer not in LAYERS:
        raise ValueError(f"source {sid}: layer {layer!r} is not one of {LAYERS}")
    if access_label not in ACCESS_LABELS:
        raise ValueError(f"source {sid}: access_label {access_label!r} is not known")
    if credibility not in CREDIBILITY:
        raise ValueError(f"source {sid}: credibility {credibility!r} is not known")
    if predictive_state not in PREDICTIVE_STATES:
        raise ValueError(f"source {sid}: predictive_state {predictive_state!r} is not known")
    if not tuple(queries):
        raise ValueError(f"source {sid}: no native-language queries; a source with no way in is "
                         f"a bookmark, not a source")
    row = source_class(sid, label, roots=roots, languages=languages, licence=licence, notes=notes)
    row.update({"layer": layer, "access_label": access_label, "credibility": credibility,
                "predictive_state": predictive_state, "queries": tuple(queries),
                "machine_use_allowed": bool(machine_use_allowed), "weight": float(weight)})
    return row


SOURCE_CLASSES: tuple[dict[str, Any], ...] = (
    _src("uk.official.boe", "Bank of England decisions, votes, reports, statistics and research",
         layer="official",
         roots=("https://www.bankofengland.co.uk/monetary-policy/upcoming-mpc-dates",
                "https://www.bankofengland.co.uk/monetary-policy-report",
                "https://www.bankofengland.co.uk/statistics",
                "https://www.bankofengland.co.uk/markets/"),
         languages=("en-GB",), licence="public, Open Government Licence",
         access_label="OPEN_DATA", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         weight=1.0,
         queries=("MPC vote split members voted to maintain Bank Rate",
                  "Monetary Policy Report projections modal path Bank Rate",
                  "APF gilt sales operations schedule quarterly announcement",
                  "Money and Credit mortgage approvals release"),
         notes="the VOTE SPLIT is published with the decision, so committee disagreement is a "
               "public dated time series -- an input no other country in this department "
               "provides. The markets pages carry the QT sales calendar, which is a "
               "pre-announced sized one-way supply flow and the UK's closest analogue to "
               "Norway's announced FX amount."),
    _src("uk.official.state", "DMO, HM Treasury, the OBR, the ONS and the FCA",
         layer="official",
         roots=("https://www.dmo.gov.uk/", "https://obr.uk/efo/",
                "https://www.ons.gov.uk/releasecalendar",
                "https://www.gov.uk/government/organisations/hm-treasury",
                "https://www.fca.org.uk/markets/short-selling", "https://www.gov.uk/bank-holidays"),
         languages=("en-GB",), licence="public, Open Government Licence",
         access_label="OPEN_DATA", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         weight=1.0,
         queries=("DMO gilt remit revision financing requirement Budget",
                  "gilt auction result cover ratio tail basis points",
                  "OBR fiscal headroom against the fiscal rules EFO",
                  "ONS release calendar 7am publication CPI labour market"),
         notes="gov.uk/bank-holidays is the statutory authority for the substitution rule this "
               "pack implements in `_substitute`, and it is machine-readable JSON. THE REMIT IS "
               "PUBLISHED AT THE BUDGET, so the fiscal event and the supply event are "
               "simultaneous and can only be separated by instrument -- the identification "
               "problem stated in domain UK-I."),
    _src("uk.institutional.venues_and_bodies",
         "LSE, FTSE Russell, ICE Futures Europe, the LBMA and the UK industry bodies",
         layer="institutional",
         roots=("https://www.londonstockexchange.com/", "https://www.ftserussell.com/",
                "https://www.ice.com/futures-europe", "https://www.lbma.org.uk/",
                "https://www.ukfinance.org.uk/", "https://www.plsa.co.uk/",
                "https://www.abi.org.uk/", "https://www.thepensionsregulator.gov.uk/"),
         languages=("en-GB",), licence="public page, restricted redistribution",
         access_label="PUBLIC_WITH_TERMS", credibility="AUTHORITATIVE",
         predictive_state="UNTESTED", weight=1.0,
         queries=("FTSE 100 EDSP settlement 10:10 10:30 averaging contract specification",
                  "closing auction random uncrossing 30 seconds LSE market model",
                  "Long Gilt future deliverable basket cheapest to deliver ICE",
                  "FTSE 100 dividend index points ex-dividend calendar",
                  "Pensions Regulator LDI collateral buffer guidance"),
         notes="the ONLY authority on the EDSP window, the random uncrossing and the gilt "
               "future's delivery basket -- three claims this pack carries as DECLARED. FTSE "
               "Russell also publishes the FORECAST INDEX DIVIDEND POINTS, which is the series "
               "that makes the ex-dividend Thursday control in domain UK-G constructible."),
    _src("uk.academic.research", "Bank of England research, Bank Underground and the institutes",
         layer="academic",
         roots=("https://www.bankofengland.co.uk/working-paper",
                "https://bankunderground.co.uk/", "https://www.niesr.ac.uk/",
                "https://ifs.org.uk/", "https://www.resolutionfoundation.org/"),
         languages=("en-GB",), licence="public, Open Government Licence / attribution",
         access_label="PUBLIC", credibility="RELIABLE", predictive_state="UNTESTED", weight=0.9,
         queries=("Bank Underground LDI gilt market dysfunction September 2022",
                  "working paper quantitative tightening gilt yields elasticity",
                  "IFS Budget analysis fiscal rules headroom day after",
                  "Resolution Foundation mortgage cliff fixed rate roll off cohort"),
         notes="Bank Underground is the Bank's own staff blog and frequently describes a "
               "mechanism months before the working paper; the IFS publishes its Budget analysis "
               "the MORNING AFTER, which is a dated, high-quality second read on the fiscal "
               "event in domain UK-I. The Resolution Foundation's roll-off cohort work is the "
               "public source for the mortgage-cliff schedule in domain UK-H."),
    _src("uk.practitioner.strategy_and_commentary",
         "UK rates strategy, practitioner blogs and the professional bodies",
         layer="practitioner",
         roots=("https://www.ft.com/alphaville", "https://www.risk.net/",
                "https://www.cfauk.org/", "https://www.moneymarketsblog.com/",
                "https://substack.com/search/gilt%20market"),
         languages=("en-GB",), licence="mixed: public commentary, paywalled and licensed notes",
         access_label="ACCESS_UNCLEAR", credibility="RELIABLE", predictive_state="UNTESTED",
         weight=0.6, machine_use_allowed=False,
         queries=("gilt market strategy comment auction tail concession",
                  "Bank Rate call terminal rate revision comment",
                  "LDI leverage collateral waterfall practitioner explanation",
                  "swap spread gilt cheapening comment"),
         notes="machine_use_allowed=False and ACCESS_UNCLEAR together: Alphaville is paywalled "
               "with terms forbidding extraction, Risk.net is licensed, and the Substack layer "
               "is a mix. All are REGISTERED so the desk knows the commentary exists; none is "
               "scraped. The UK practitioner layer is the deepest in this department and the "
               "hardest to access compliantly, and saying so is more useful than a blank."),
    _src("uk.retail_ecology.communities", "UK retail investor boards and personal-finance forums",
         layer="retail_ecology",
         roots=("https://www.lse.co.uk/ShareChat.html", "https://www.advfn.com/",
                "https://forums.moneysavingexpert.com/",
                "https://www.reddit.com/r/UKPersonalFinance/",
                "https://www.reddit.com/r/UKInvesting/"),
         languages=("en-GB",), licence="public forum, quote-and-cite only",
         access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE", predictive_state="UNTESTED",
         weight=0.25, machine_use_allowed=False,
         queries=("fix ending 2026 remortgage offer rate what did you get",
                  "should I fix for 2 or 5 years mortgage thread",
                  "ISA deadline 5 April last minute where to put it",
                  "gilt ladder platform holding to maturity CGT"),
         notes="machine_use_allowed=False: MoneySavingExpert's and ADVFN's terms forbid "
               "automated extraction, so both are REGISTERED and never scraped. MSE's mortgage "
               "threads are the household side of domain UK-H -- borrowers post their fix end "
               "dates and the offers they receive, which is the roll-off schedule observed from "
               "the inside. Weight 0.25 and never dropped: wrong individual posts still measure "
               "the cohort's timing."),
    _src("uk.app_ecosystem.platforms",
         "UK retail broker platforms, their public statistics and the savings-rate surfaces",
         layer="app_ecosystem",
         roots=("https://www.hl.co.uk/", "https://www.ajbell.co.uk/",
                "https://www.ii.co.uk/", "https://freetrade.io/", "https://www.trading212.com/",
                "https://www.ig.com/uk", "https://www.moneyfactscompare.co.uk/",
                "https://www.tradingview.com/symbols/FTSE-UKX/"),
         languages=("en-GB",), licence="per-platform terms",
         access_label="PUBLIC_WITH_TERMS", credibility="UNKNOWN",
         predictive_state="NARRATIVE_FEATURE", weight=0.4,
         queries=("Hargreaves Lansdown most bought shares this week",
                  "interactive investor most traded ISA season",
                  "Moneyfacts best fixed rate mortgage average rate today",
                  "IG client sentiment FTSE long short percentage"),
         notes="Moneyfacts publishes the AVERAGE ADVERTISED MORTGAGE RATE daily, which is the "
               "single most useful item in this layer: it is the price at which the roll-off in "
               "domain UK-H actually happens, published, dated and free. IG's client-sentiment "
               "percentages are a genuine retail positioning read on UK100 -- and the only "
               "positioning series in this department that is daily and retail-side."),
    _src("uk.media.business_press", "UK financial press and newswires",
         layer="media",
         roots=("https://www.ft.com/", "https://www.reuters.com/world/uk/",
                "https://www.thetimes.co.uk/business", "https://www.telegraph.co.uk/business/",
                "https://www.thisismoney.co.uk/", "https://news.sky.com/business"),
         languages=("en-GB",), licence="paywalled; terms forbid bulk extraction",
         access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
         predictive_state="NARRATIVE_FEATURE", weight=0.5, machine_use_allowed=False,
         queries=("gilt yields rise Budget reaction market comment",
                  "Bank Rate decision vote split reaction sterling",
                  "mortgage rates rise swap rates lenders reprice",
                  "pension funds LDI margin calls gilt crisis"),
         notes="machine_use_allowed=False across the board: the FT, Times and Telegraph all "
               "paywall with terms forbidding bulk extraction. Registered, never scraped, and "
               "reached only through a licensed aggregator. This is Money is the most open and "
               "is also the closest to the retail layer, so its content is read as narrative."),
    _src("uk.archive.historical", "UK historical macro-financial data and the digitised record",
         layer="archive",
         roots=("https://www.bankofengland.co.uk/statistics/research-datasets",
                "https://www.dmo.gov.uk/data/", "https://www.nationalarchives.gov.uk/",
                "https://www.britishnewspaperarchive.co.uk/", "https://hansard.parliament.uk/",
                "https://web.archive.org/"),
         languages=("en-GB",), licence="public archive; some subscription",
         access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         weight=0.8,
         queries=("A Millennium of Macroeconomic Data Bank of England spreadsheet",
                  "gilt yields historical series DMO since 1700",
                  "Hansard mini-budget September 2022 statement text",
                  "web archive Bank of England gilt purchase operation October 2022"),
         notes="THE ARCHIVE IS LOAD-BEARING FOR THE MOST IMPORTANT UK CLAIM IN THIS PACK. "
               "UKGILT's bars on this box begin 2024-02-26 (measured), so the 2022 LDI episode "
               "has NO gilt series here at all; every statistic about it must come from the "
               "Bank's historical datasets and be cited. 'A Millennium of Macroeconomic Data' "
               "runs back to 1086 and is free."),
    _src("uk.physical_economy.energy_metal_freight",
         "UK grid and gas flows, the London gold vaults, ports and customs",
         layer="physical_economy",
         roots=("https://www.neso.energy/data-portal", "https://www.nationalgas.com/data-and-"
                "operations", "https://www.lbma.org.uk/prices-and-data/london-vault-holdings",
                "https://www.uktradeinfo.com/", "https://www.abports.co.uk/"),
         languages=("en-GB",), licence="public / Open Government Licence",
         access_label="OPEN_DATA", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         weight=0.9,
         queries=("NESO data portal demand outturn interconnector flows",
                  "National Gas within-day system entry NBP flows interconnector",
                  "LBMA London vault holdings monthly gold silver tonnes",
                  "uktradeinfo trade statistics by commodity code monthly"),
         notes="LBMA vault holdings are the OTHER END of the Swiss customs gold flow in the CH "
               "pack: metal leaving London arrives in Switzerland to be recast, and both halves "
               "are public. Agreement between the two series is the actual test in edge UK-E11. "
               "NESO's data portal is free, half-hourly and revision-free."),
    _src("uk.source_graph.citation_and_link", "Citation and link graphs over the UK corpus",
         layer="source_graph",
         roots=("https://ideas.repec.org/s/boe/boeewp.html", "https://openalex.org/",
                "https://hansard.parliament.uk/", "https://www.gov.uk/search/all",
                "https://github.com/search?q=gilt+OR+SONIA+language%3APython"),
         languages=("en-GB",), licence="open data",
         access_label="OPEN_DATA", credibility="RELIABLE", predictive_state="UNTESTED",
         weight=0.5,
         queries=("RePEc cited by Bank of England working paper LDI gilt",
                  "OpenAlex citation graph quantitative tightening sovereign yields",
                  "gov.uk linked documents DMO remit Budget publications",
                  "github UK bank holiday substitute day calendar implementation"),
         notes="GOV.UK's own link structure connects a Budget to its remit, its EFO and its "
               "statutory instruments, which is how the simultaneous documents in domain UK-I "
               "are enumerated rather than guessed. The GitHub query is concrete: the "
               "substitution rule implemented in this module is exactly the sort of thing "
               "published libraries get subtly wrong."),
)

#: All ten layers are populated for the United Kingdom, so this table is empty BY MEASUREMENT.
#: Note that the PRACTITIONER and MEDIA layers, the deepest in this department, are also the
#: least machine-accessible -- both carry machine_use_allowed=False and that is recorded rather
#: than resolved.
LAYER_ABSENCES: dict[str, str] = {}

def source_layer_coverage() -> dict[str, dict[str, Any]]:
    """The per-layer audit. Every one of the ten layers gets a row, always.

    A layer with sources lists them. A layer with none carries the REASON from `LAYER_ABSENCES`,
    and a layer with neither is a defect this pack's own test fails on -- which is the point: a
    country is never "covered" by five obvious sources, and the only way to know that is to make
    the emptiness impossible to leave blank.
    """
    out: dict[str, dict[str, Any]] = {}
    for layer in LAYERS:
        rows = tuple(s for s in SOURCE_CLASSES if s.get("layer") == layer)
        out[layer] = {
            "sources": tuple(str(s.get("id")) for s in rows),
            "n": len(rows),
            "n_machine_readable": sum(1 for s in rows if s.get("machine_use_allowed")),
            "queries": sum(len(s.get("queries") or ()) for s in rows),
            "absent_reason": "" if rows else str(LAYER_ABSENCES.get(layer, "")),
        }
    return out


def _ds(name: str, *, pit: dict[str, str], **kw: Any) -> dict[str, Any]:
    """A catalogue row plus the six point-in-time stamps."""
    row = dataset(name, **kw)
    missing = [s for s in PIT_STAMPS if not str(pit.get(s, "")).strip()]
    if missing:
        raise ValueError(f"dataset {name}: missing PIT stamps {missing}")
    row["pit"] = dict(pit)
    return row


DATASETS: tuple[dict[str, Any], ...] = (
    _ds("Bank of England MPC decisions, vote splits and minutes",
        source="Bank of England", coverage="every MPC decision since 1997",
        frequency="8 per year", publication_lag_days=0.0,
        revisions="never revised. THE STRUCTURE CHANGED in August 2015: before it, the minutes "
                  "were a separate event roughly two weeks later; after it, they are "
                  "simultaneous. The vote series is continuous and the EVENT COUNT is not.",
        licence="public, Open Government Licence", history_from="1997-06", pit_feasible=True,
        assets=("GBPUSD", "EURGBP", "UK100", "UKGILT"),
        mechanism_families=("policy_surprise", "committee_dissent", "event_drift"),
        how_to_fetch="bankofengland.co.uk decision pages, one per meeting",
        pit={"event_time": "12:00 London announcement",
             "period_time": "the period the decision applies from",
             "publication_time": "12:00 London, press conference 12:30 on Report days",
             "available_time": "12:00 London -- which is 07:00 or 08:00 New York depending on "
                               "the season, so what else is in the window changes twice a year",
             "revision_time": "never",
             "retrieval_time": "crawler stamp"}),
    _ds("UK DMO gilt auction calendar, results and the annual remit",
        source="UK Debt Management Office", coverage="all gilt issuance",
        frequency="quarterly calendar, weekly auctions, annual remit",
        publication_lag_days=0.0,
        revisions="the remit is REVISED at the Spring Statement and at any fiscal event; each "
                  "revision is a dated supply announcement in its own right",
        licence="public, Open Government Licence", history_from="1998", pit_feasible=True,
        assets=("UKGILT", "GBPUSD", "UK100"),
        mechanism_families=("supply_concession", "forced_flow", "fiscal_event"),
        how_to_fetch="dmo.gov.uk calendar and results pages; the remit arrives with the Budget",
        pit={"event_time": "the auction bidding deadline, 10:00 London",
             "period_time": "the settlement date, T+1 for gilts",
             "publication_time": "results within about thirty minutes of the deadline",
             "available_time": "same",
             "revision_time": "the remit is revised at fiscal events; auction results are not",
             "retrieval_time": "crawler stamp"}),
    _ds("Bank of England Asset Purchase Facility QT sales schedule",
        source="Bank of England", coverage="the QT envelope and the individual sale operations",
        frequency="annual envelope decided each September; operations on a quarterly schedule",
        publication_lag_days=0.0,
        revisions="the envelope has been revised downward; each revision is a dated policy event "
                  "that most event calendars do not carry",
        licence="public", history_from="2022-11", pit_feasible=True,
        assets=("UKGILT", "GBPUSD"),
        mechanism_families=("announced_flow", "supply", "central_bank_flow"),
        how_to_fetch="bankofengland.co.uk markets pages and the September MPC minutes",
        pit={"event_time": "the September envelope decision, and each operation's date",
             "period_time": "the October-to-September QT year",
             "publication_time": "the announcement",
             "available_time": "BEFORE the operations happen -- a forced flow that is knowable "
                               "in advance, which is rare",
             "revision_time": "the annual review, and any unscheduled change",
             "retrieval_time": "crawler stamp"}),
    _ds("ONS CPI, labour market and GDP",
        source="Office for National Statistics", coverage="United Kingdom",
        frequency="monthly and quarterly", publication_lag_days=17.0,
        revisions="GDP is revised repeatedly and substantially; CPI is not revised but is "
                  "reweighted each January; the labour market survey's response rate fell far "
                  "enough after 2023 that the ONS suspended and rebuilt it -- a data-quality "
                  "break that is not a revision and is not flagged in any vendor series",
        licence="public, Open Government Licence", history_from="1988", pit_feasible=True,
        assets=("GBPUSD", "EURGBP", "UK100", "UKGILT"),
        mechanism_families=("data_surprise", "policy_expectation", "event_drift"),
        how_to_fetch="ons.gov.uk release calendar and the statistical bulletins",
        pit={"event_time": "07:00 London -- EVERY ONS release, without exception",
             "period_time": "the reference month or quarter",
             "publication_time": "07:00 London",
             "available_time": "07:00 London, one hour before the equity open, so a UK data "
                               "surprise is a pure FX event for sixty minutes",
             "revision_time": "GDP repeatedly; CPI reweighted each January; the labour survey "
                              "has a structural break",
             "retrieval_time": "crawler stamp"}),
    _ds("OBR Economic and Fiscal Outlook and the fiscal headroom",
        source="Office for Budget Responsibility",
        coverage="the fiscal forecast and the margin against the fiscal rules",
        frequency="twice a year, with the Budget and the Spring Statement",
        publication_lag_days=0.0,
        revisions="each EFO supersedes the last; the HEADROOM number is the market-relevant "
                  "line and it moves by tens of billions between forecasts",
        licence="public, Open Government Licence", history_from="2010", pit_feasible=True,
        assets=("UKGILT", "GBPUSD", "UK100"),
        mechanism_families=("fiscal_event", "supply", "event_drift"),
        how_to_fetch="obr.uk EFO pages, published at the fiscal event",
        pit={"event_time": "the fiscal statement, typically 12:30 London after PMQs",
             "period_time": "the five-year forecast horizon",
             "publication_time": "at the statement, simultaneously with the DMO remit",
             "available_time": "same -- and the SIMULTANEITY is the problem: the fiscal news and "
                               "the supply news cannot be separated by time",
             "revision_time": "the next EFO",
             "retrieval_time": "crawler stamp"}),
    _ds("Nationwide and Halifax house price indices",
        source="Nationwide Building Society and Lloyds Banking Group",
        coverage="UK residential prices, lender approvals basis", frequency="monthly",
        publication_lag_days=1.0,
        revisions="seasonal adjustment is re-estimated; the raw index is stable",
        licence="public headline", history_from="1952 (Nationwide)", pit_feasible=True,
        assets=("GBPUSD", "UK100"),
        mechanism_families=("housing_channel", "policy_transmission"),
        how_to_fetch="the lenders' own index pages",
        pit={"event_time": "Nationwide publishes on the FIRST WORKING DAY of the following month",
             "period_time": "the calendar month",
             "publication_time": "07:00 London on the first working day",
             "available_time": "same -- the earliest housing read in Europe after Norway's",
             "revision_time": "seasonal re-estimation",
             "retrieval_time": "crawler stamp"}),
    _ds("Bank of England Money and Credit: mortgage approvals",
        source="Bank of England", coverage="UK mortgage approvals and consumer credit",
        frequency="monthly", publication_lag_days=30.0,
        revisions="routinely revised by small amounts",
        licence="public", history_from="1993", pit_feasible=True,
        assets=("GBPUSD", "UK100"),
        mechanism_families=("housing_channel", "credit_cycle", "leading_indicator"),
        how_to_fetch="bankofengland.co.uk statistics, 09:30 London release",
        pit={"event_time": "09:30 London on the release day",
             "period_time": "the reference month",
             "publication_time": "09:30 London, around the end of the following month",
             "available_time": "same; approvals LEAD completions by roughly three months, which "
                               "is the reason to carry a series this lagged at all",
             "revision_time": "small monthly revisions",
             "retrieval_time": "crawler stamp"}),
    _ds("SONIA and the sterling OIS curve",
        source="Bank of England / ICE", coverage="overnight and term sterling rates",
        frequency="daily on UK business days", publication_lag_days=1.0,
        revisions="SONIA is republished the same morning if an error is found -- a real PIT "
                  "hazard, the same shape as ESTR's",
        licence="public (SONIA); licensed (OIS quotes)", history_from="1997", pit_feasible=True,
        assets=("GBPUSD", "UKGILT"),
        mechanism_families=("funding", "policy_expectation", "surprise_construction"),
        how_to_fetch="bankofengland.co.uk database for SONIA; OIS requires a licensed feed",
        pit={"event_time": "the trading day the rate is computed over",
             "period_time": "the overnight period",
             "publication_time": "09:00 London the following business day",
             "available_time": "same",
             "revision_time": "same-morning republication when triggered",
             "retrieval_time": "crawler stamp"}),
    _ds("LBMA gold and silver prices and vault holdings",
        source="LBMA / ICE Benchmark Administration",
        coverage="the London fixes and monthly London vault stocks",
        frequency="daily prices, monthly vault data", publication_lag_days=30.0,
        revisions="vault holdings are restated occasionally",
        licence="public headline, licensed history", history_from="1968 (fix), 2016 (vaults)",
        pit_feasible=True, assets=("XAUUSD", "XAGUSD", "GBPUSD"),
        mechanism_families=("physical_flow", "benchmark_effect", "fix_flow"),
        how_to_fetch="lbma.org.uk prices and data pages",
        pit={"event_time": "the auction (10:30 and 15:00 London for gold, 12:00 for silver)",
             "period_time": "the month, for vault holdings",
             "publication_time": "immediately for prices; about a month for vaults",
             "available_time": "same",
             "revision_time": "vault restatements",
             "retrieval_time": "crawler stamp"}),
    _ds("CFTC Commitments of Traders, British Pound",
        source="CFTC", coverage="CME sterling futures and options", frequency="weekly",
        publication_lag_days=3.0,
        revisions="silent corrections in later weekly files",
        licence="public domain", history_from="1986", pit_feasible=True,
        assets=("GBPUSD", "EURGBP", "GBPJPY"),
        mechanism_families=("positioning", "crowding", "reversal"),
        how_to_fetch="CFTC weekly text and historical archives",
        pit={"event_time": "the Tuesday the positions are as of",
             "period_time": "the same Tuesday close",
             "publication_time": "Friday 15:30 ET",
             "available_time": "Friday 15:30 ET",
             "revision_time": "silent corrections",
             "retrieval_time": "crawler stamp"}),
)


def actors() -> tuple[dict[str, Any], ...]:
    """Sixteen UK participants whose constraints produce dated or measurable flow."""
    return (
        actor("Bank of England Monetary Policy Committee",
              holds="Bank Rate and, through the APF, the size of the gilt portfolio",
              forced_to=("decide eight times a year on a published calendar",
                         "publish the INDIVIDUAL VOTE of all nine members with the decision",
                         "publish the minutes in the same instant since August 2015",
                         "decide the QT envelope every September"),
              when="Thursday, 12:00 London, eight times a year",
              information=("ONS CPI at 07:00 London, usually the week before",
                           "the labour market release",
                           "SONIA/OIS pricing of its own path"),
              constraints=("a nine-member committee with four external members who dissent "
                           "openly, so the reaction function is a distribution rather than a "
                           "point -- and the distribution is published",
                           "an inflation target with a letter-writing obligation when it is "
                           "missed by more than a point, which is a dated public document"),
              instruments=("GBPUSD", "EURGBP", "UK100", "UKGILT"),
              counterparties=("UK banks through reserves", "the gilt market through the APF"),
              observables=("the 12:00 announcement",
                           "the vote split, which is a public time series of disagreement",
                           "the Monetary Policy Report four times a year"),
              impact="the densest single central-bank instant in this department: rate, vote, "
                     "minutes and sometimes a whole Report in one second",
              persistence="the path repricing persists for weeks",
              falsifier="if GBPUSD's move in the 12:00-12:30 window regressed on the OIS-implied "
                        "path surprise has a coefficient indistinguishable from zero across the "
                        "eight meetings of a year, the decision is not the event and the vote "
                        "split or the Report is",
              notes="the vote split is separately informative from the decision and can be "
                    "tested as its own surprise -- a 5-4 hold is not the same event as a 9-0 one"),
        actor("The Bank of England's QT sales desk (the Asset Purchase Facility)",
              holds="the gilt portfolio accumulated under QE",
              forced_to=("sell to a pre-announced annual envelope",
                         "operate on a published quarterly schedule of dated operations",
                         "sell across maturity buckets on a declared split"),
              when="scheduled operations, dates published in advance",
              information=("the September envelope decision", "market conditions, which it does "
                           "NOT respond to operationally within a schedule"),
              constraints=("a pre-announced, sized, one-way supply programme -- the operations "
                           "happen whatever the price does, which is exactly what makes them "
                           "measurable",),
              instruments=("UKGILT", "GBPUSD"),
              counterparties=("gilt-edged market makers", "the DMO, whose supply it adds to"),
              observables=("the published operation calendar",
                           "the annual envelope and its revisions",
                           "the maturity-bucket split"),
              impact="a forced supply flow that is KNOWABLE BEFORE IT HAPPENS -- the UK's closest "
                     "analogue to Norway's announced daily FX amount",
              persistence="the QT year",
              falsifier="if UKGILT shows no abnormal behaviour into scheduled QT operation dates "
                        "relative to matched non-operation days since 2024, an announced supply "
                        "flow of this size does not move the future and the announced-flow "
                        "family is weaker than this department claims",
              notes="only testable on UKGILT from 2024-02-26, which is most but not all of the "
                    "QT programme"),
        actor("UK Debt Management Office",
              holds="the gilt issuance programme",
              forced_to=("publish the remit AT THE BUDGET, simultaneously with the fiscal news",
                         "publish a quarterly auction calendar",
                         "auction on the announced dates whatever the market does"),
              when="auctions on published dates, 10:00 London deadline; the remit at each fiscal "
                   "event",
              information=("the government's net financing requirement",
                           "the OBR forecast"),
              constraints=("the remit follows arithmetically from the fiscal forecast, so gilt "
                           "supply is a mechanical function of a published number rather than a "
                           "market judgement",),
              instruments=("UKGILT", "GBPUSD", "UK100"),
              counterparties=("gilt-edged market makers", "pension funds and insurers"),
              observables=("the remit and its revisions",
                           "the quarterly calendar",
                           "auction cover ratios and tails"),
              impact="the supply news and the fiscal news arrive in the SAME INSTANT, which is "
                     "convenient to trade and awkward to identify -- they must be separated by "
                     "instrument, not by time",
              persistence="the remit year",
              falsifier="if UKGILT's move at the fiscal event is uncorrelated with the remit's "
                        "surprise once the OBR growth forecast revision is controlled for, "
                        "supply is not what moves the gilt market at the Budget",
              notes="the simultaneity is the identification problem and it is stated rather than "
                    "assumed away"),
        actor("UK defined-benefit pension funds and their LDI managers",
              holds="long inflation-linked liabilities hedged with LEVERAGED gilt and swap "
                    "positions",
              forced_to=("post collateral when yields rise -- and the leverage means a large "
                         "yield move forces SELLING of the very asset that is falling",
                         "meet a hedge ratio set by a trustee mandate",
                         "buy out into insurance when funding permits"),
              when="continuously; violently in September and October 2022",
              information=("their own funding ratio", "the gilt curve"),
              constraints=("LEVERAGE PLUS A COLLATERAL CALL IS A FORCED SELLER. The 2022 episode "
                           "was not a view being wrong; it was a margin mechanic operating "
                           "exactly as designed, at a scale nobody had stress-tested.",),
              instruments=("UKGILT", "GBPUSD", "UK100"),
              counterparties=("gilt-edged market makers", "the Bank of England, which became the "
                              "buyer of last resort for thirteen days"),
              observables=("Pensions Regulator and Bank of England Financial Stability Report "
                           "disclosures on LDI leverage and collateral buffers",
                           "bulk purchase annuity volumes, which are the exit",
                           "the 30-year gilt yield"),
              impact="a convex, leveraged, forced seller at the long end of the UK curve; the "
                     "conditional tail of a UK yield move is fatter than any unconditional model "
                     "implies",
              persistence="the 2022 episode lasted weeks; the structural exposure persists, at "
                          "lower leverage, indefinitely",
              falsifier="if the long end of the UK curve shows no fatter conditional tail than "
                        "comparable sovereign curves after controlling for level and volatility, "
                        "the LDI mechanic leaves no measurable trace and is a story about one "
                        "fortnight",
              notes="NOT TESTABLE ON UKGILT: this box's gilt bars begin 2024-02-26 and the "
                    "episode was 2022. GBPUSD and UK100 carry what can be measured."),
        actor("UK insurers writing bulk purchase annuities",
              holds="pension liabilities bought out from corporate schemes, under Solvency UK",
              forced_to=("match the liabilities they take on with long assets",
                         "meet a matching-adjustment test that constrains what qualifies"),
              when="deal-driven; volumes are published quarterly and have been at records",
              information=("scheme funding ratios, which determine who can afford to buy out",
                           "the Solvency UK reform's eligibility rules"),
              constraints=("a regulatory matching test that makes them buyers of specific kinds "
                           "of long asset, not of duration generally",),
              instruments=("UKGILT", "GBPUSD"),
              counterparties=("the pension schemes they take on", "long-dated credit issuers"),
              observables=("published BPA transaction volumes",
                           "the long end of the gilt curve",
                           "Solvency UK reform milestones, which are dated legislation"),
              impact="a structural, growing, regulated bid for long UK duration that is slowly "
                     "replacing the leveraged LDI bid with an unleveraged one -- a change in WHO "
                     "holds the long end and therefore in how it behaves in stress",
              persistence="structural, measured in years",
              falsifier="if the long end's behaviour in stress episodes has not changed as BPA "
                        "volumes replaced LDI leverage, the ownership shift has no market "
                        "consequence and this actor is an industry story",
              notes="this actor is the reason a 2022-calibrated LDI tail model may overstate "
                    "today's risk -- which is a testable claim about a structural change"),
        actor("UK households rolling off fixed-rate mortgages",
              holds="two- and five-year fixed mortgages taken at very low rates, rolling onto "
                    "much higher ones on a KNOWN schedule",
              forced_to=("remortgage or fall onto the standard variable rate when the fix ends",
                         "pass the lender's stress test to remortgage at all"),
              when="the roll-off schedule, which is arithmetic from the origination distribution "
                   "and therefore knowable years in advance",
              information=("their own fix end date", "swap rates, which set the new offer"),
              constraints=("a fixed-rate contract delays the shock and then delivers it whole; "
                           "the UK's two-year fix is the SHORTEST common fixation in western "
                           "Europe, so the UK sits between Sweden's three-month reset and "
                           "Czechia's five-year one",),
              instruments=("GBPUSD", "UK100"),
              counterparties=("UK banks", "the swap market, which prices the offers"),
              observables=("BoE mortgage approvals at 09:30 London",
                           "Nationwide HPI on the first working day",
                           "the published roll-off profile in the Financial Stability Report"),
              impact="a dated, cohort-by-cohort cash-flow shock to the largest component of UK "
                     "household spending",
              persistence="years",
              falsifier="if UK consumption and house prices show no relation to the published "
                        "roll-off schedule beyond the level of Bank Rate, the cohort structure "
                        "adds nothing and the simple rate level is sufficient",
              notes="the UK completes a four-country transmission ladder with Sweden (three "
                    "months), Norway (six weeks' statutory notice), the UK (two to five years) "
                    "and Czechia (three to five years) -- one shock, four arrival profiles"),
        actor("UK banks under the Term Funding Scheme repayment profile",
              holds="cheap central-bank funding drawn in 2020-2021 that must be repaid on a "
                    "published schedule",
              forced_to=("repay TFSME drawings as they mature, which DRAINS reserves on dates "
                         "known years in advance",
                         "replace that funding in the market or shrink"),
              when="the published repayment profile, concentrated in 2024-2025",
              information=("the repayment schedule", "deposit and wholesale funding costs"),
              constraints=("a maturing central-bank facility is a forced funding event on a date "
                           "nobody chose for market reasons",),
              instruments=("GBPUSD", "UK100"),
              counterparties=("the Bank of England", "depositors", "the covered bond market"),
              observables=("the TFSME repayment profile, published",
                           "SONIA minus Bank Rate",
                           "UK bank deposit rate competition"),
              impact="a scheduled reserve drain that widens sterling funding spreads on knowable "
                     "dates and pushes banks to compete for deposits",
              persistence="the repayment window",
              falsifier="if the SONIA-to-Bank-Rate spread shows no relation to the published "
                        "TFSME repayment profile, the drain is being offset elsewhere and the "
                        "schedule is not a funding event",
              notes="one of very few UK flows whose calendar was fixed several years in advance"),
        actor("FTSE 100 index funds and the closing auction",
              holds="replicating portfolios that must match the official close",
              forced_to=("trade the quarterly review at the effective close",
                         "match a closing price set by an auction with a RANDOM end"),
              when="16:30-16:35 London daily; quarterly reviews in March, June, September and "
                   "December",
              information=("FTSE Russell's announced changes, published in advance",),
              constraints=("tracking error is the only measure, so they pay the auction price; "
                           "and the RANDOM UNCROSSING means the exact instant cannot be timed",),
              instruments=("UK100", "GBPUSD"),
              counterparties=("market makers who warehouse the imbalance",),
              observables=("the review announcement and effective dates",
                           "closing auction volume",
                           "the auction's own price against the continuous close"),
              impact="a concentrated, forecastable, one-sided flow into a window whose end is "
                     "deliberately unpredictable -- a different game from the DAX's fixed "
                     "13:00 CET auction",
              persistence="one auction, partially reversed over the following week",
              falsifier="if UK100's last-fifteen-minute return on review effective dates is "
                        "indistinguishable from an ordinary Friday, the index-level effect is "
                        "absent and only the single-name one exists, which the two-lane order "
                        "puts out of reach",
              notes="the randomisation is a deliberate anti-gaming design and testing whether it "
                    "works is a legitimate microstructure question"),
        actor("UK100 market makers into the 10:10-10:30 EDSP",
              holds="option and future books settling on a twenty-minute MORNING average",
              forced_to=("hedge into a window that is long enough that no single print sets it",
                         "carry residual risk for the six hours of session that follow"),
              when="the third Friday, 10:10-10:30 London",
              information=("open interest by strike", "their own inventory"),
              constraints=("a twenty-minute average cannot be moved by one trade and cannot be "
                           "ignored either -- an incentive structure between the DAX's single "
                           "auction and Sweden's whole-day average",),
              instruments=("UK100", "GBPUSD"),
              counterparties=("UK institutional hedgers", "retail structured-product issuers"),
              observables=("ICE open interest",
                           "realised volatility inside and outside the averaging window",
                           "the post-settlement session, which trades with the expiry behind it"),
              impact="pinning into a morning window and a RELEASE for the remaining six hours -- "
                     "the release is the distinctive part and it is long enough to measure",
              persistence="the expiry day",
              falsifier="if UK100's realised volatility between 10:30 and the close on a third "
                        "Friday is not higher than on matched Fridays, the release does not "
                        "happen and the EDSP is not binding anything",
              notes="Germany, Sweden and the UK give three different settlement answers; the "
                    "desk can trade the German and UK ones and that comparison is the design"),
        actor("FTSE 100 constituents going ex-dividend on Thursdays",
              holds="dividend obligations whose ex-date is set by UK market convention",
              forced_to=("go ex-dividend on the convention date, which in the UK is "
                         "overwhelmingly a THURSDAY",),
              when="Thursdays, clustered in the reporting seasons",
              information=("the announced dividend calendar, public weeks ahead",),
              constraints=("a settlement and record-date convention, not a choice; the index "
                           "drops by the dividend amount mechanically and it carries no "
                           "information whatsoever",),
              instruments=("UK100",),
              counterparties=("index funds", "futures holders, who are unaffected because the "
                              "future already prices the dividend"),
              observables=("the announced ex-dividend calendar",
                           "the index points due to come out, published by the exchange and by "
                           "index providers",
                           "the Thursday-morning gap"),
              impact="a forecastable, information-free, one-directional index drop concentrated "
                     "on one weekday -- and it is the reason a naive UK day-of-week study finds "
                     "a 'Thursday effect' that is entirely a dividend calendar",
              persistence="permanent, and seasonal in intensity",
              falsifier="if UK100's Thursday returns are no different from other weekdays once "
                        "the announced index points are added back, the convention is not "
                        "concentrated enough to matter -- which would itself settle the "
                        "Thursday-effect question",
              notes="this is a CONTROL as much as an effect: it is the single most likely "
                    "explanation of any apparent UK weekday anomaly"),
        actor("HM Treasury and the Office for Budget Responsibility",
              holds="the fiscal rules and the forecast that measures compliance with them",
              forced_to=("hold a Budget and a Spring Statement on announced dates",
                         "publish the OBR forecast at the same instant",
                         "publish the DMO remit at the same instant again"),
              when="two fiscal events a year, typically 12:30 London after Prime Minister's "
                   "Questions",
              information=("tax receipts", "the OBR's own forecast"),
              constraints=("a fiscal rule measured against a five-year forecast means the HEADROOM "
                           "figure is the binding constraint, and it is a single number in a "
                           "long document that the gilt market trades within minutes",),
              instruments=("UKGILT", "GBPUSD", "UK100"),
              counterparties=("the gilt market", "the DMO"),
              observables=("the announced fiscal event date, usually weeks ahead",
                           "the OBR headroom figure",
                           "the remit's financing requirement"),
              impact="the largest scheduled UK domestic event; in 2022 an unscheduled one moved "
                     "the gilt market more than any monetary decision in decades",
              persistence="weeks",
              falsifier="if UKGILT's move at fiscal events is unrelated to the change in OBR "
                        "headroom across the events since 2024, the market is trading something "
                        "else in that instant and the headroom framing is journalism",
              notes="fiscal news, forecast news and supply news arrive together; separating them "
                    "requires instruments, not windows"),
        actor("Gilt-edged market makers (GEMMs)",
              holds="obligations to bid at every auction and to make continuous prices",
              forced_to=("bid at every gilt auction as a condition of their status",
                         "warehouse the inventory until it is distributed"),
              when="every auction, 10:00 London deadline",
              information=("the auction calendar and size", "their own inventory"),
              constraints=("an obligation to bid, whatever the level, is the mechanism behind "
                           "the pre-auction concession: the dealer must make room",),
              instruments=("UKGILT", "GBPUSD"),
              counterparties=("the DMO", "pension funds and insurers"),
              observables=("auction cover ratios and tails",
                           "the yield path from the prior close to the 10:00 deadline",
                           "the post-auction retracement"),
              impact="a concession into the deadline and a relief afterwards, with a size that "
                     "should scale with the auction's size relative to recent issuance",
              persistence="hours",
              falsifier="if UKGILT's return from the prior close to the 10:00 deadline has no "
                        "relation to the announced size across the auctions since 2024, the "
                        "concession does not exist in the future even if it exists in the cash",
              notes="the UK is the ONE country in this department where this can be tested on an "
                    "executable bond instrument rather than on a currency proxy"),
        actor("Foreign official and index investors in gilts",
              holds="a large share of a market that is no longer bought by the central bank",
              forced_to=("rebalance to index weights",
                         "reduce when a fiscal or political shock changes the risk assessment"),
              when="month-end index rebalancing; event-driven otherwise",
              information=("global risk appetite", "UK fiscal credibility"),
              constraints=("QT removed the price-insensitive buyer, so the marginal gilt buyer "
                           "is now a price-sensitive foreigner -- a structural change in who "
                           "sets the price",),
              instruments=("UKGILT", "GBPUSD"),
              counterparties=("the DMO", "GEMMs"),
              observables=("ONS and BoE holdings statistics",
                           "the gilt-Bund and gilt-Treasury spreads",
                           "sterling's behaviour on gilt-negative days"),
              impact="the UK's defining post-2022 fact: gilts and sterling now sell off TOGETHER "
                     "on a fiscal shock, which is an emerging-market correlation and was not the "
                     "UK's historical pattern",
              persistence="episodic, but the structural change persists",
              falsifier="if the GBPUSD-to-UKGILT correlation conditional on a fiscal event is no "
                        "different from its unconditional value, the twin-deficit dynamic is not "
                        "operating and 2022 was idiosyncratic",
              notes="this is the most important UK claim in the pack and the one the desk can "
                    "test directly, because both legs are executable"),
        actor("CFTC-reportable sterling speculators",
              holds="leveraged CME sterling futures",
              forced_to=("report weekly", "meet margin"),
              when="positions as of Tuesday, published Friday 15:30 ET",
              information=("public macro", "their own limits"),
              constraints=("margin, and a position that has repeatedly reached record extremes "
                           "around UK political events",),
              instruments=("GBPUSD", "EURGBP", "GBPJPY"),
              counterparties=("dealers", "commercial hedgers"),
              observables=("the COT net position percentile against a rolling window",
                           "realised volatility as the unwind trigger"),
              impact="crowding conditions the tail: the 2016 and 2022 record shorts both "
                     "preceded violent squeezes",
              persistence="weeks to build, days to unwind",
              falsifier="if conditioning sterling's largest weekly rallies on the prior COT "
                        "percentile adds nothing to an unconditional tail model, the squeeze "
                        "story is folklore",
              notes="sterling has one of the longest usable COT histories, which makes the UK "
                    "the natural place to test the crowding family that the Nordic and CEE packs "
                    "cannot test at all"),
        actor("UK retail investors in the ISA season",
              holds="tax-advantaged accounts with an annual subscription allowance that expires",
              forced_to=("use the allowance by 5 APRIL or lose it -- a statutory deadline with "
                         "no carry-forward",),
              when="the weeks into 5 April, every year",
              information=("the allowance, set at fiscal events",
                           "platform marketing, which is intense in March"),
              constraints=("a use-it-or-lose-it tax deadline is a genuine forced flow: the money "
                           "must be subscribed by a date or the relief is gone",),
              instruments=("UK100", "GBPUSD"),
              counterparties=("investment platforms", "fund managers"),
              observables=("platform-reported ISA inflows, published seasonally",
                           "March fund flow data",
                           "the 5 April boundary itself"),
              impact="a seasonal retail inflow concentrated into late March and early April, "
                     "unique to the UK's tax calendar",
              persistence="annual",
              falsifier="if UK100's late-March returns are indistinguishable from other periods "
                        "once the general equity seasonal is removed, the ISA flow is too small "
                        "or too diversified to reach the index",
              notes="the 5 April boundary is five days after the 31 March fiscal year end -- two "
                    "different UK year ends in one week, and they belong to different actors"),
        actor("The LBMA and the London gold vaults",
              holds="the physical gold that clears the world's over-the-counter market",
              forced_to=("publish monthly vault holdings",
                         "settle loco London, which makes location a price variable"),
              when="continuous clearing; monthly vault publication",
              information=("the fixes", "ETF creations and redemptions",
                           "Swiss customs flows, which are the metal arriving and leaving"),
              constraints=("physical logistics: metal moves slowly, so a change in location "
                           "demand shows up as a spread before it shows up as a price",),
              instruments=("XAUUSD", "XAGUSD", "GBPUSD"),
              counterparties=("Swiss refiners, who are the counterparty in the customs data",
                              "bullion banks", "central banks"),
              observables=("LBMA monthly vault holdings",
                           "the London-versus-futures spread",
                           "the Swiss customs net flow to and from the UK"),
              impact="London vault holdings falling while Swiss net exports to Asia rise is the "
                     "physical market draining westward-to-eastward, and both halves are public",
              persistence="months",
              falsifier="if LBMA vault changes have no relation to Swiss customs flows to and "
                        "from the UK at a one-month lag, the two series are not measuring the "
                        "same metal and the physical narrative is not constructible",
              notes="the Swiss pack holds the other half of this actor; the two series are the "
                    "same flow observed from both ends, which is a rare cross-check"),
    )


def domains() -> tuple[dict[str, Any], ...]:
    """Fourteen research domains, each with negative controls."""
    return (
        domain("UK-A", "MPC decisions at 12:00 London and the published vote",
               objects=("the 12:00 decision", "the vote split as a separate surprise",
                        "the simultaneous minutes", "the Monetary Policy Report four times a year"),
               conditions=("Report meeting versus non-Report meeting",
                           "the OIS-implied path surprise",
                           "the vote split's distance from unanimity",
                           "the pre- and post-August-2015 event structure"),
               instruments=("GBPUSD", "EURGBP", "UK100", "UKGILT"),
               controls=("matched non-decision Thursdays at 12:00 London",
                         "the ECB's own decision days, to separate 'a central bank spoke' from "
                         "'the Bank of England spoke'",
                         "the vote split held constant while the rate surprise varies, and the "
                         "reverse -- the two are separable here and nowhere else",
                         "a placebo at 12:00 London the day before"),
               notes="a 5-4 hold and a 9-0 hold are different events with the same rate outcome; "
                     "the UK is the only country in this department where that is measurable"),
        domain("UK-B", "Gilt QT and the pre-announced sales calendar",
               objects=("the September envelope decision",
                        "the quarterly schedule of dated operations",
                        "the maturity-bucket split"),
               conditions=("operation day versus non-operation day",
                           "the bucket being sold",
                           "the envelope's size relative to DMO issuance"),
               instruments=("UKGILT", "GBPUSD"),
               controls=("matched non-operation days",
                         "DMO auction days, which are the other supply event and must not be "
                         "confounded with QT",
                         "the pre-2024 period, where UKGILT has no bars and the honest verdict "
                         "is UNMEASURED",
                         "Norway's announced FX amount as the cross-pack benchmark for what an "
                         "announced flow of known size should look like"),
               notes="only testable from 2024-02-26 on UKGILT (measured). That is most of the QT "
                     "programme and not the start of it, and the domain says so."),
        domain("UK-C", "The 2022 LDI episode as a regime, and the data gap it sits in",
               objects=("the 23 September 2022 mini-Budget",
                        "the Bank's emergency gilt purchases, 28 September to 14 October 2022",
                        "the leverage and collateral structure that forced the selling"),
               conditions=("inside versus outside the episode",
                           "the level of LDI leverage, which fell afterwards",
                           "whether the shock was fiscal or monetary in origin"),
               instruments=("GBPUSD", "UK100", "UKGILT"),
               controls=("UKGILT IS UNAVAILABLE for the episode itself -- bars begin 2024-02-26 "
                         "-- so the gilt leg is UNMEASURED and only GBPUSD and UK100 can be used",
                         "the euro area's own sovereign spreads over the same window, to "
                         "separate a UK-specific event from a global rates shock",
                         "the post-2024 period at lower leverage, where the same fiscal surprise "
                         "should produce a smaller tail if the mechanism is leverage",
                         "US Treasuries over the same window"),
               notes="the single most important gilt event in fifty years and this box cannot "
                     "see it in its gilt series. Recording that is the domain's first job."),
        domain("UK-D", "The 16:00 WMR fix and month-end, from inside the fixing session",
               objects=("the five-minute 15:57:30-16:02:30 window",
                        "the T-2 month-end value date",
                        "the 2015 widening of the window from one minute to five"),
               conditions=("month-end versus mid-month",
                           "quarter-end amplification",
                           "before versus after the 2015 window change"),
               instruments=("GBPUSD", "EURGBP", "GBPJPY", "UK100"),
               controls=("mid-month days matched on weekday",
                         "the 15:00-15:05 London hour-early placebo",
                         "the pre-2015 one-minute window as the microstructure regime control",
                         "the last CALENDAR day against the T-2 value date"),
               notes="the UK is the only country here whose own session CONTAINS the fix that "
                     "moves everyone else's month-end, so UK liquidity is an input to the flow "
                     "rather than a recipient of it"),
        domain("UK-E", "UK100 expiry and the 10:10-10:30 morning EDSP",
               objects=("the twenty-minute averaging window",
                        "the six hours of session that follow it",
                        "open interest by strike"),
               conditions=("quarterly versus monthly expiry",
                           "whether the roll-back moved the date off the third Friday",
                           "open interest concentration"),
               instruments=("UK100", "GBPUSD"),
               controls=("GER40's 13:00 CET auction on the SAME MORNING -- one date, two "
                         "settlement mechanics, and a shared move is European rather than "
                         "British",
                         "matched non-expiry Fridays",
                         "the post-10:30 session against the pre-10:10 session on the same day, "
                         "which is the release test",
                         "April 2025, when Good Friday WAS the third Friday and the expiry moved "
                         "back to Thursday the 17th"),
               notes="Germany settles at a single midday auction, Sweden across a whole day and "
                     "the UK over twenty morning minutes; two of the three are executable here "
                     "and the comparison is the design"),
        domain("UK-F", "The closing auction and its random uncrossing",
               objects=("the 16:30-16:35 call",
                        "the randomised end inside the final thirty seconds",
                        "the quarterly index review effective dates"),
               conditions=("review effective date versus ordinary day",
                           "the size of the index-fund imbalance",
                           "month-end coincidence"),
               instruments=("UK100", "GBPUSD"),
               controls=("the continuous close at 16:30 against the auction print, which "
                         "measures the auction's own impact",
                         "the 16:00 WMR fix half an hour earlier, which separates the FX flow "
                         "from the equity flow -- a separation Frankfurt and Paris do not offer",
                         "matched non-review days",
                         "GER40's own closing auction, which has no randomisation"),
               notes="the randomisation is an anti-gaming design and whether it works is a "
                     "legitimate and testable microstructure question"),
        domain("UK-G", "Ex-dividend Thursdays",
               objects=("the UK convention that puts ex-dates on Thursdays",
                        "the announced index points coming out",
                        "the reporting-season clustering"),
               conditions=("index points due that Thursday",
                           "the reporting season versus the off-season",
                           "whether the Thursday is also an expiry or a decision day"),
               instruments=("UK100",),
               controls=("the announced index points ADDED BACK, which should remove the whole "
                         "effect if it is purely mechanical",
                         "other weekdays in the same week",
                         "GER40 on the same Thursday, where German ex-dates are clustered in "
                         "the spring AGM season instead and not on one weekday",
                         "Thursdays outside the reporting seasons, where few points come out"),
               notes="carried as much as a CONTROL as an effect: it is the most likely "
                     "explanation of any apparent UK weekday anomaly and every UK day-of-week "
                     "study must remove it first"),
        domain("UK-H", "The mortgage cliff and the UK's place on the transmission ladder",
               objects=("the two- and five-year fixed-rate roll-off schedule",
                        "BoE mortgage approvals at 09:30 London",
                        "Nationwide HPI on the first working day"),
               conditions=("the cohort's original rate against the current offer",
                           "the position in the roll-off profile",
                           "the swap curve, which sets new offers"),
               instruments=("GBPUSD", "UK100"),
               controls=("SWEDEN (three-month reset), NORWAY (six-week statutory notice) and "
                         "CZECHIA (three-to-five-year fix) as the other rungs of the ladder -- "
                         "one European tightening arriving at four household sectors on four "
                         "schedules",
                         "the period before the low-rate cohort existed",
                         "approvals against completions, since approvals lead by three months",
                         "a placebo roll-off profile shifted by a year"),
               notes="the four-country ladder is the department's strongest cross-country design "
                     "and the UK is its middle rung"),
        domain("UK-I", "Fiscal events: the Budget, the remit and the OBR headroom",
               objects=("the fiscal statement at 12:30 London",
                        "the OBR headroom figure",
                        "the DMO remit, published in the same instant"),
               conditions=("Budget versus Spring Statement",
                           "the direction and size of the headroom change",
                           "whether the remit surprised relative to the forecast"),
               instruments=("UKGILT", "GBPUSD", "UK100"),
               controls=("the three arrive together, so they must be separated by INSTRUMENT: a "
                         "supply surprise should move UKGILT more than GBPUSD, and a credibility "
                         "shock should move both in the same direction -- which is the twin-"
                         "deficit signature",
                         "matched non-event days",
                         "euro-area sovereigns on the same day, for the global rates component",
                         "the 2022 mini-Budget as the extreme observation, deliberately held out"),
               notes="the simultaneity of fiscal, forecast and supply news is the UK's defining "
                     "identification problem and the pack states it rather than assuming it away"),
        domain("UK-J", "UK data releases at 07:00 London",
               objects=("EVERY ONS release, at 07:00 London without exception",
                        "the sixty minutes before the equity open",
                        "the labour market survey's post-2023 quality break"),
               conditions=("the surprise against consensus",
                           "proximity to the next MPC meeting",
                           "whether the series has a known quality problem"),
               instruments=("GBPUSD", "EURGBP", "UK100", "UKGILT"),
               controls=("the 07:00-08:00 window against the 08:00-09:00 one, which separates "
                         "the pure FX reaction from the equity-inclusive one",
                         "matched no-release mornings",
                         "the labour market series before and after its rebuild, which is a "
                         "data-quality break and not a revision",
                         "euro-area releases on the same morning"),
               notes="a publication convention gives the UK a clean hour of FX-only reaction. "
                     "That separation is free and almost nobody uses it."),
        domain("UK-K", "The London gold and silver fixes",
               objects=("the 10:30 and 15:00 London gold auctions",
                        "the 12:00 silver auction",
                        "LBMA monthly vault holdings"),
               conditions=("month-end versus mid-month",
                           "the direction of the Swiss customs flow to and from the UK",
                           "the gold-silver ratio's London intraday shape"),
               instruments=("XAUUSD", "XAGUSD", "GBPUSD"),
               controls=("the 15:00 gold fix against the 16:00 currency fix one hour later, "
                         "which separates the metal flow from the FX flow",
                         "matched non-fix minutes",
                         "the Swiss customs series as the physical cross-check, from the other "
                         "end of the same flow",
                         "COMEX hours, to separate a London effect from a US one"),
               notes="the Swiss pack observes this flow from the refinery end and this pack from "
                     "the vault end; agreeing is the test"),
        domain("UK-L", "Brent, London cocoa and the terminal markets",
               objects=("ICE Brent's expiry on the last business day of the second preceding "
                        "month",
                        "London cocoa as a genuine terminal market with physical delivery",
                        "the UK energy channel into UK100"),
               conditions=("the expiry cycle",
                           "the sterling level, since UK100 is majority foreign-revenue",
                           "the energy price regime"),
               instruments=("XBRUSD", "UKCOCOA", "UK100", "GBPUSD"),
               controls=("XTIUSD is NOT in this pack's executable list and the euro-area pack "
                         "carries it; use USDX for the dollar leg",
                         "matched non-expiry days for the Brent roll",
                         "the FTSE 250 is the domestic index and is NOT executable -- so a "
                         "UK-domestic energy hypothesis expressed through UK100 has the WRONG "
                         "SIGN and the domain says so explicitly",
                         "cocoa's own physical supply news, which is West African and not British"),
               notes="UK100 rises when sterling falls, because its revenue is foreign. That "
                     "makes it a poor UK-domestic instrument and an excellent sterling-inverse "
                     "one, and confusing the two is the standard error in UK equity analysis."),
        domain("UK-M", "Sterling positioning and the twin-deficit correlation",
               objects=("the CFTC sterling net position and its percentile",
                        "the GBPUSD-to-UKGILT correlation conditional on a fiscal event",
                        "the 2016 and 2022 record-short episodes"),
               conditions=("the position percentile against a rolling window",
                           "whether the shock is fiscal or monetary",
                           "the era, since the correlation's sign changed after 2022"),
               instruments=("GBPUSD", "UKGILT", "EURGBP"),
               controls=("the commercial COT line as the mechanical mirror of the speculative "
                         "one",
                         "the unconditional GBPUSD-UKGILT correlation as the null against the "
                         "fiscal-event-conditional one",
                         "the euro area's own currency-versus-bond correlation, which should NOT "
                         "show the emerging-market signature if the UK's is special",
                         "a randomised Tuesday-to-Friday realignment, to show the effect is not "
                         "created by the publication lag"),
               notes="THE MOST IMPORTANT UK CLAIM IN THIS PACK: since 2022 gilts and sterling "
                     "sell off together on a fiscal shock, which is an emerging-market pattern "
                     "and was not the UK's historical one. Both legs are executable, so it can "
                     "be tested directly rather than inferred."),
        domain("UK-N", "Bank holidays, the substitution rule and the two UK year ends",
               objects=("eight bank holidays a year, substitution applied",
                        "the Scottish-only days, when banks shut and the LSE trades",
                        "31 March (government) and 5 April (personal) as two different year ends"),
               conditions=("whether a closure is a substitute day",
                           "whether the counterparty is Scottish",
                           "which year end is relevant to the actor"),
               instruments=("GBPUSD", "EURGBP", "UK100", "GBPCHF"),
               controls=("the continental closures on days London trades, which is the reverse "
                         "asymmetry and the larger sample",
                         "EURGBP at Whit Monday and 24 and 31 December, when Germany is shut and "
                         "London is not -- the department's cleanest one-sided-closure pair",
                         "turnover as the direct control",
                         "the 31 March boundary against the 5 April one, which belong to "
                         "different actors and should show different flows"),
               notes="the UK closure count is CONSTANT at eight because of the substitution rule, "
                     "which makes UK per-year normalisation safe where the Nordic and CEE ones "
                     "are not -- and that difference is itself a usable control"),
    )


TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    edge("UK-E01",
         source="the OIS-implied Bank Rate path surprise at the 12:00 London MPC announcement",
         mechanism="an eight-times-a-year rate decision published with its vote split and "
                   "minutes in one instant",
         targets=("GBPUSD", "UKGILT", "UK100", "EURGBP"),
         sign="hawkish surprise -> GBPUSD up, UKGILT down, UK100 down",
         horizon="intraday to 3 days", lag="0 to 30 minutes",
         control="matched non-decision Thursdays; ECB decision days; the vote split held "
                 "constant while the rate surprise varies",
         evidence="HYPOTHESIS",
         notes="the OIS leg is a TRANSMISSION_TARGET; without it the surprise cannot be built "
               "and the edge is UNMEASURED rather than zero"),
    edge("UK-E02",
         source="the MPC vote split's distance from unanimity, holding the rate outcome fixed",
         mechanism="nine published individual votes make committee disagreement a public time "
                   "series, and a 5-4 decision carries more information about the next one",
         targets=("GBPUSD", "UKGILT"),
         sign="a more divided vote in the hawkish direction -> GBPUSD up over the following weeks",
         horizon="days to weeks", lag="0 minutes -- the vote is published with the decision",
         control="decisions with the same rate outcome and different splits; the pre-2015 "
                 "structure, where the vote arrived two weeks later as a separate event",
         evidence="HYPOTHESIS",
         notes="separable from the rate surprise only because the UK publishes both at once; no "
               "other country in this department allows this test"),
    edge("UK-E03",
         source="a UK fiscal event: the change in OBR headroom and the DMO remit, published "
                "together at 12:30 London",
         mechanism="fiscal credibility and gilt supply arrive in one instant, and since 2022 the "
                   "market prices them as a single credibility variable",
         targets=("UKGILT", "GBPUSD", "UK100"),
         sign="headroom cut and remit raised -> UKGILT down AND GBPUSD down together",
         horizon="days to weeks", lag="minutes",
         control="the unconditional GBPUSD-UKGILT correlation as the null; euro-area sovereigns "
                 "on the same day; separation by instrument since time cannot separate them",
         evidence="HYPOTHESIS",
         notes="the SAME-SIGN move in bonds and currency is the emerging-market signature and is "
               "the pack's central UK claim"),
    edge("UK-E04",
         source="a scheduled Bank of England QT gilt sale operation",
         mechanism="a pre-announced, sized, one-way supply operation that happens whatever the "
                   "price does",
         targets=("UKGILT", "GBPUSD"),
         sign="an operation day -> UKGILT concession into it, partial relief after",
         horizon="intraday to a day", lag="the calendar is published in advance",
         control="matched non-operation days; DMO auction days, which are the other supply "
                 "event; Norway's announced FX amount as the cross-pack benchmark",
         evidence="HYPOTHESIS",
         notes="testable on UKGILT only from 2024-02-26 (measured); before that, UNMEASURED"),
    edge("UK-E05",
         source="a gilt auction's announced size, measured to the 10:00 London bidding deadline",
         mechanism="GEMMs are obliged to bid, so they must make room in inventory first",
         targets=("UKGILT", "GBPUSD"),
         sign="a larger auction -> concession into the deadline, retracement after",
         horizon="intraday", lag="none",
         control="non-auction days matched on weekday; QT operation days; the German Bund "
                 "auction as the retention-absorbed comparison",
         evidence="HYPOTHESIS",
         notes="the UK is the only country in this department where a supply concession can be "
               "tested on an executable BOND rather than on a currency proxy"),
    edge("UK-E06",
         source="the 10:10-10:30 London EDSP averaging window on the third Friday",
         mechanism="dealer hedging is pinned into a twenty-minute morning average and released "
                   "for the six hours that follow",
         targets=("UK100", "GBPUSD"),
         sign="volatility suppressed inside the window, elevated after 10:30",
         horizon="intraday", lag="none",
         control="GER40's 13:00 CET auction on the same morning; matched non-expiry Fridays; "
                 "the pre-10:10 session against the post-10:30 one",
         evidence="HYPOTHESIS",
         notes="April 2025's expiry rolled back to Thursday the 17th because Good Friday fell on "
               "the third Friday; `uk100_expiry` handles that and a naive rule does not"),
    edge("UK-E07",
         source="the announced FTSE 100 index points going ex-dividend on a Thursday",
         mechanism="a UK settlement convention concentrates ex-dates on one weekday, so the cash "
                   "index takes a mechanical, information-free drop",
         targets=("UK100",),
         sign="more index points out -> a proportionally larger Thursday-morning drop",
         horizon="intraday", lag="none -- the calendar is published weeks ahead",
         control="the points ADDED BACK, which should remove the effect entirely; other "
                 "weekdays; GER40 on the same Thursday",
         evidence="MEASURED_ELSEWHERE",
         notes="the mechanism is arithmetic. The research question is whether any UK weekday "
               "anomaly survives removing it, and the usual answer elsewhere is no."),
    edge("UK-E08",
         source="the last two business days before a month-end value date, from inside the "
                "London session",
         mechanism="global index hedging is concentrated into the 16:00 London WMR window, which "
                   "sits inside the UK's own session",
         targets=("GBPUSD", "EURGBP", "GBPJPY", "UK100"),
         sign="the month's realised equity return sets the sign of the fix-window flow",
         horizon="intraday", lag="the fix window",
         control="mid-month weekday-matched days; the 15:00-15:05 hour-early placebo; the "
                 "16:30-16:35 closing auction half an hour later, which is the equity flow and "
                 "not the FX one",
         evidence="MEASURED_ELSEWHERE",
         notes="the UK is unusual in being able to separate the FX fix from the equity auction "
               "by thirty minutes; Frankfurt and Paris cannot"),
    edge("UK-E09",
         source="the published fixed-rate mortgage roll-off profile",
         mechanism="a cohort cash-flow shock whose schedule is arithmetic from the origination "
                   "distribution and therefore knowable years ahead",
         targets=("GBPUSD", "UK100"),
         sign="a heavy roll-off quarter -> UK demand weaker -> sterling weaker at the macro "
              "horizon",
         horizon="quarters", lag="years, by construction",
         control="Sweden's three-month reset, Norway's six-week notice and Czechia's five-year "
                 "fix as the other rungs; approvals against completions; a profile shifted by a "
                 "year as the placebo",
         evidence="HYPOTHESIS",
         notes="the four-country ladder is the design; a UK-only result proves nothing about "
               "contractual filtering"),
    edge("UK-E10",
         source="an ONS release at 07:00 London",
         mechanism="a publication convention delivers every UK statistic an hour before the "
                   "equity open, so the first sixty minutes are a pure FX reaction",
         targets=("GBPUSD", "EURGBP", "UKGILT"),
         sign="upside CPI surprise -> GBPUSD up in the 07:00-08:00 window",
         horizon="intraday", lag="none",
         control="the 08:00-09:00 window, which includes equity; matched no-release mornings; "
                 "the labour market series before and after its post-2023 rebuild",
         evidence="HYPOTHESIS",
         notes="a free, clean, hour-long separation between the FX and equity reaction that "
               "exists only because of a UK release convention"),
    edge("UK-E11",
         source="the 15:00 London LBMA gold fix and LBMA monthly vault holdings",
         mechanism="London clears the physical gold market, so vault stocks and the fix are two "
                   "ends of the same flow that the Swiss customs data observes from the other side",
         targets=("XAUUSD", "XAGUSD", "GBPUSD"),
         sign="London vaults draining while Swiss net exports to Asia rise -> physical "
              "tightness, XAUUSD supported",
         horizon="weeks to months", lag="vault data about a month; customs about twenty days",
         control="the 16:00 currency fix one hour later, to separate metal from FX; COMEX hours; "
                 "XAGUSD, which shares the monetary driver and not the Asian physical one",
         evidence="HYPOTHESIS",
         notes="the Swiss pack holds the other half; the two series agreeing is the actual test"),
    edge("UK-E12",
         source="a record extreme in the CFTC sterling net position percentile",
         mechanism="a crowded position is a forced unwind on a shock, and sterling's extremes "
                   "have clustered around UK political events",
         targets=("GBPUSD", "EURGBP", "GBPJPY"),
         sign="an extreme short raises the conditional probability of a violent rally on a shock",
         horizon="weeks", lag="three days from the Tuesday snapshot to Friday publication",
         control="the commercial line as the mechanical mirror; a randomised Tuesday-to-Friday "
                 "realignment; the same test on EUR, where the measurement also exists",
         evidence="HYPOTHESIS",
         notes="the Nordic and CEE packs cannot run this family at all, so the UK and euro-area "
               "results are the only evidence this department will ever have about it"),
)


def _seeded(rows: tuple[dict[str, Any], ...]) -> tuple[dict[str, Any], ...]:
    """Copy each edge's PRIMARY executable target into `asset`.

    `libs.research.country_lab.TransmissionSeed` carries ONE `asset`; every edge here names
    several. The first target is the primary and is copied into the field the framework reads;
    the full tuple stays in `targets` and the framework folds it into the row's notes rather
    than dropping it.
    """
    return tuple({**row, "asset": row["targets"][0]} for row in rows)


TRANSMISSION_EDGES_SEED = _seeded(TRANSMISSION_EDGES_SEED)

POLICY_ERAS: tuple[dict[str, Any], ...] = (
    era("uk.super_thursday", start="2015-08-06", end=None,
        label="the decision, vote and minutes published in one instant",
        what_changed="the EVENT STRUCTURE. Before it, the minutes were a second event two weeks "
                     "later; after it, everything lands at 12:00 London together",
        invalidates="any UK policy event study spanning 2015-08: it is pooling a one-event "
                    "regime with a two-event one, and the per-meeting information content "
                    "changed without the rate series showing anything",
        notes="the announcement CLOCK never moved; only the contents of the instant did"),
    era("uk.brexit_referendum", start="2016-06-23", end="2016-06-24",
        label="the referendum and sterling's largest one-day fall in modern history",
        what_changed="sterling's risk premium and the whole distribution of its tail",
        invalidates="a sterling tail model calibrated without it",
        notes="NOT TESTABLE ON THIS BOX: GBPUSD bars begin 2018-01-02. The reference observation "
              "for GBP gap risk is outside the sample and the pack says so rather than letting a "
              "session assume it is in there."),
    era("uk.zirp_qe", start="2009-03-05", end="2021-12-15",
        label="Bank Rate at or near the floor with an expanding gilt portfolio",
        what_changed="the central bank was the marginal gilt buyer and sterling had no carry",
        invalidates="auction-concession and supply studies: with a price-insensitive buyer "
                    "present, supply effects are mechanically smaller",
        notes="partially on this box's FX bars from 2018; not at all on its gilt bars"),
    era("uk.hiking", start="2021-12-16", end="2023-08-03",
        label="the hiking cycle to a 5.25% Bank Rate",
        what_changed="the fastest UK tightening in three decades, into a household sector on "
                     "two- and five-year fixes, so the cash-flow shock was deferred and then "
                     "delivered cohort by cohort",
        invalidates="anything estimated on the 2009-2021 sample",
        notes="on this box's FX and index bars; NOT on its gilt bars"),
    era("uk.mini_budget_ldi", start="2022-09-23", end="2022-10-14",
        label="the mini-Budget and the LDI gilt crisis",
        what_changed="a fiscal announcement produced a self-reinforcing forced-selling spiral in "
                     "the long gilt, and the Bank became the buyer of last resort for thirteen "
                     "days. Gilts and sterling fell TOGETHER, which was not the UK's historical "
                     "pattern.",
        invalidates="any UK tail model that assumes bonds hedge the currency; the correlation's "
                    "sign flipped and has not fully returned",
        notes="THE MOST IMPORTANT GILT EVENT IN FIFTY YEARS AND UKGILT HAS NO BARS FOR IT "
              "(measured: bars begin 2024-02-26). Only GBPUSD and UK100 can be measured here."),
    era("uk.qt", start="2022-11-01", end=None,
        label="active gilt sales from the Asset Purchase Facility",
        what_changed="the central bank went from the largest holder to a scheduled seller, and "
                     "the marginal gilt buyer became a price-sensitive foreigner",
        invalidates="supply studies calibrated during QE; the price elasticity of gilt supply "
                    "is a different number with and without a price-insensitive buyer",
        notes="the annual envelope is decided each September and has been revised down once; "
              "OPEN ERA, and the only part of it on this box's gilt bars is 2024 onward"),
    era("uk.cutting", start="2024-08-01", end=None,
        label="the cutting cycle",
        what_changed="Bank Rate began falling while the mortgage roll-off was still delivering "
                     "higher rates to cohorts -- policy easing and household tightening at the "
                     "same time, which is a direct consequence of the fixed-rate structure",
        invalidates="a contemporaneous rate-to-consumption mapping; in the UK they diverge by "
                    "construction during a turn",
        notes="OPEN ERA; the end is UNMEASURED and must not be back-filled"),
    era("uk.libor_to_sonia", start="2021-12-31", end=None,
        label="the end of sterling LIBOR and the completion of the SONIA transition",
        what_changed="the reference rate in essentially every sterling contract",
        invalidates="a long sterling rates series joined by name across the transition; the "
                    "break is definitional",
        notes="the UK's benchmark transition is COMPLETE, unlike Poland's WIBOR-to-WIRON one "
              "which is still running -- the two make a useful before-and-after pair"),
    era("uk.t_plus_one", start="2027-10-11", end=None,
        label="the scheduled move of UK cash equities to T+1 settlement",
        what_changed="NOTHING YET. This is a FORWARD-DATED era, recorded now because every "
                     "month-end study in this pack has a scheduled structural break on that day: "
                     "the hedging deadline moves from T-2 to T-1 and every month-end window "
                     "shifts by one business day.",
        invalidates="any month-end model fitted before it and applied after it, on the day it "
                    "happens",
        notes="DECLARED -- verify against the Accelerated Settlement Taskforce. Recording a "
              "known future break is cheaper than discovering it as a live model failure."),
)

CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    miner("uk_mpc_vote", domain_ids=("UK-A",), kind="mechanism",
          entry="countries.uk.miners:mpc_vote",
          notes="NOT WIRED. Must treat the vote split as a surprise SEPARATE from the rate "
                "surprise; that separation is only possible in the UK."),
    miner("uk_qt_and_auctions", domain_ids=("UK-B",), kind="mechanism",
          entry="countries.uk.miners:qt_and_auctions",
          notes="NOT WIRED. Must report UNMEASURED for anything before 2024-02-26 on UKGILT "
                "rather than silently starting the sample where the bars start."),
    miner("uk_ldi_regime", domain_ids=("UK-C", "UK-M"), kind="failure",
          entry="countries.uk.miners:ldi_regime",
          notes="NOT WIRED. The gilt leg of the 2022 episode is UNAVAILABLE on this box; the "
                "miner's first output is that fact."),
    miner("uk_fix_and_auction", domain_ids=("UK-D", "UK-F"), kind="mechanism",
          entry="countries.uk.miners:fix_and_auction",
          notes="NOT WIRED. The 16:00 FX fix and the 16:30 equity auction are thirty minutes "
                "apart and must be measured as two events."),
    miner("uk_edsp", domain_ids=("UK-E",), kind="mechanism",
          entry="countries.uk.miners:edsp",
          notes="NOT WIRED. Uses `uk100_expiry` so the bank-holiday roll-back is applied; GER40's "
                "midday auction on the same morning is the control."),
    miner("uk_ex_div_thursday", domain_ids=("UK-G",), kind="data",
          entry="countries.uk.miners:ex_div_thursday", cadence_s=86400.0, steerable=False,
          notes="NOT WIRED, and a FIXED COST on purpose: the announced index points must be "
                "collected before any UK day-of-week study can be believed."),
    miner("uk_mortgage_ladder", domain_ids=("UK-H",), kind="transfer",
          entry="countries.uk.miners:mortgage_ladder",
          notes="NOT WIRED. Four-country by construction: Sweden, Norway, the UK and Czechia."),
    miner("uk_fiscal_event", domain_ids=("UK-I",), kind="mechanism",
          entry="countries.uk.miners:fiscal_event",
          notes="NOT WIRED. Fiscal, forecast and supply news arrive together and must be "
                "separated by instrument rather than by time."),
    miner("uk_seven_am", domain_ids=("UK-J",), kind="mechanism",
          entry="countries.uk.miners:seven_am",
          notes="NOT WIRED. The 07:00-08:00 window is a pure FX reaction; the 08:00-09:00 one is "
                "not, and that contrast is the whole design."),
    miner("uk_london_metal_fix", domain_ids=("UK-K",), kind="mechanism",
          entry="countries.uk.miners:london_metal_fix",
          notes="NOT WIRED. Shared with the Swiss pack, which observes the same physical flow "
                "from the refinery end."),
    miner("uk_calendar", domain_ids=("UK-N", "UK-L"), kind="data",
          entry="countries.uk.miners:calendar", cadence_s=86400.0, steerable=False,
          notes="NOT WIRED. Derives the bank holidays with substitution and the Scottish-only "
                "days from the rules in this module, and emits the EURGBP one-sided sessions."),
)


def pack() -> Any:
    """The United Kingdom pack: `CountryPack` when the framework has landed, else a dict."""
    return build_pack(
        code=CODE,
        name=NAME,
        region_command=REGION_COMMAND,
        currency=CURRENCY,
        executable_instruments=EXECUTABLE_INSTRUMENTS,
        central_bank=CENTRAL_BANK,
        fixing_conventions=FIXING_CONVENTIONS,
        settlement_conventions=SETTLEMENT_CONVENTIONS,
        exchanges=EXCHANGES,
        holidays_rule=HOLIDAYS_RULE,
        fiscal_year_end="03-31",
        positioning_sources=POSITIONING_SOURCES,
        native_languages=NATIVE_LANGUAGES,
        terminology=TERMINOLOGY,
        source_classes=SOURCE_CLASSES,
        datasets=DATASETS,
        actors=actors(),
        domains=domains(),
        custom_miners=CUSTOM_MINERS,
        transmission_edges_seed=TRANSMISSION_EDGES_SEED,
        policy_eras=POLICY_ERAS,
    )
