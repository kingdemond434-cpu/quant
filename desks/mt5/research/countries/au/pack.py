"""AUSTRALIA: a traded consensus, three countable cargoes, and a regulated hedge ratio.

WHAT AUSTRALIA IS AS A MARKET MECHANISM, AND WHY IT IS NOT A SMALLER ANYTHING. Four things
belong to this economy and to no other country in the desk's book, and each one is why a domain
below exists rather than a row in some generic macro domain:

  1. THE CONSENSUS IS A TRADED INSTRUMENT, NOT A SURVEY. The ASX 30-day interbank cash rate
     future (IB) settles to the MONTHLY AVERAGE of the RBA cash rate, so the market's expectation
     of a decision is readable in basis points at any minute before it. Almost nowhere else in
     this book can a policy surprise be measured against a continuously-traded curve instead of a
     stale median of economists. That makes the RBA the desk's cleanest monetary natural
     experiment -- and it comes with a trap: the monthly-average settlement means an implied rate
     part-way through a month already embeds the days elapsed, so an extraction that does not
     divide those out biases every surprise toward zero.

  2. THE TERMS OF TRADE ARE THREE CARGOES SOMEBODY COUNTS. Iron ore, coal and LNG are roughly
     60% of goods exports, and every one of them leaves through a port that PUBLISHES its monthly
     tonnage -- Pilbara Ports, Port of Newcastle, Gladstone. The AUD's fundamental driver is a
     counted physical flow, free, monthly, and not a vendor's model. No other currency in this
     pack's region has that.

  3. THE HEDGE RATIO IS A REGULATED, SCHEDULED, SIGN-FLIPPING FLOW. A$4trn of superannuation
     holds a large offshore allocation with a declared hedge ratio and an APRA-supervised duty to
     return to it. When offshore equities RALLY the hedged sleeve is under-covered and the fund
     BUYS foreign currency -- selling AUD -- and the reverse on a drawdown. The sign is set by the
     offshore equity return. An unconditional "month-end flow" study averages this mechanism to
     zero and concludes, wrongly, that it is not there. `AU-H` exists to stop that.

  4. THE CLOSE IS AN AUCTION WITH A RANDOM END AND THE FUTURE SETTLES TO AN OPEN. The S&P/ASX 200
     official close is a single-price auction at 16:10-16:12 Sydney whose exact end minute is
     random, while the SPI 200 future cash-settles to a Special Opening Quotation built from
     constituent OPENING prices on the third Thursday. Expiry risk in Australia therefore sits in
     the overnight gap into an open, not in a close -- the opposite of the intuition imported from
     US index expiry -- and the quarterly index rebalance lands on the third FRIDAY, a different
     day again. `AU-G` keeps those three apart because conflating them destroys the test.

WHAT IS EXECUTABLE AND WHAT IS NOT. AUDUSD and eight AUD crosses, AUS200, XAUAUD and the metals,
energy and softs complex are quotable here. The instruments this pack's mechanisms are actually
ABOUT are mostly not: iron ore, Newcastle coal, coking coal, JKM LNG, the SPI 200 future, the IB
cash-rate future, the 3- and 10-year bond futures and the cash index itself are all absent from
`data/universe/universe.json`. Every one is named in `TRANSMISSION_TARGETS` with the universe
symbols its mechanism reaches, so an absent instrument produces a transmission hypothesis and
never a cell that can never be filled (L1.49).

THE TWO CALENDARS, AND THE TRAP THEY DISARM. Australia has no national public holiday act:
holidays are STATE law, and so is the substitution rule when one falls on a weekend. Anzac Day
2026 is SATURDAY 2026-04-25. Western Australia and the Northern Territory gazette Monday
2026-04-27 as a substitute; New South Wales does not. The ASX and ASX 24 follow the NSW calendar,
so AUS200 trades a normal session on 2026-04-27 while a Perth payroll does not run. This pack
therefore publishes TWO functions -- `national_holidays` and `market_holidays` -- and declares its
substitution rule explicitly rather than picking one and hoping. Mixing them silently drops or
invents a full trading day.

THE TWO-LANE ORDER IS EASY TO BREAK HERE. Australian market commentary is overwhelmingly
single-name: the AFR, Livewire and HotCopper talk about BHP, CBA and Fortescue, and every one of
those is an EVENT-lane instrument. They appear in this pack only as ACTORS -- a forced USD seller,
a scheduled dividend payer, a royalty payer -- and the instruments those actors move are FX,
indices, metals, energy and softs. No share CFD appears in any instrument tuple in this file.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, timedelta
from typing import Any

# --------------------------------------------------------------------------- identity
CODE = "AU"
NAME = "Australia"
#: The canonical token from `country_lab.REGION_COMMANDS`; `REGION_DESK` is the desk-facing label.
REGION_COMMAND = "oceania"
REGION_DESK = "OCEANIA"
CURRENCY = "AUD"
FISCAL_YEAR_END = "06-30"  # 1 July to 30 June; the Commonwealth Budget is presented in May
NATIVE_LANGUAGES: tuple[str, ...] = ("en-AU",)

#: Fusion-quotable instruments an Australian mechanism can actually reach. Nothing here is an
#: equity: the two-lane order (2026-09-06) keeps single names in the event lane.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "AUDUSD",                                          # the sovereign quote, median spread 0 pts
    "AUDJPY", "AUDNZD", "AUDCAD", "AUDCHF",            # the carry and relative-policy crosses
    "AUDSGD", "AUDHUF", "EURAUD", "GBPAUD",            # the rest of the AUD complex
    "AUS200",                                          # Indices, contract size 1.0, 80 pt spread
    "XAUAUD", "XAUUSD", "XAGUSD",                      # gold in AUD is an identity; see AU-N
    "XCUUSD", "XALUSD", "XNIUSD", "XZNUSD", "XPBUSD",  # the base metals Australia mines
    "XTIUSD", "XBRUSD", "XNGUSD",                      # the LNG contract's lagged oil linkage
    "WHEAT", "CORN", "SUGAR", "COTTON",                # the export crop complex
    "USDCNH", "CHINAH", "HK50",                        # the China channel, AU-D
    "NZDUSD", "NZDJPY",                                # the Tasman leg, AU-E
    "USDX",                                            # the dollar factor every AUD cell needs
    "US500", "UST10Y",                                 # the global risk and duration controls
)

#: Instruments this pack's mechanisms are ABOUT that this broker does not quote. Each names the
#: universe symbols its mechanism reaches instead.
TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "SGX TSI iron ore 62% Fe swap/future", "venue": "SGX",
     "why": "the single largest Australian export price; it sets export receipts, WA royalties "
            "and the materials half of the index",
     "proxies": ("AUDUSD", "AUS200", "AUDJPY", "XCUUSD")},
    {"name": "Newcastle thermal coal (GCNewc) and premium hard coking coal", "venue": "ICE / SGX",
     "why": "the second and third bulk exports; the coking-coal price is a steel-margin variable "
            "and the thermal price is a European and Asian power variable",
     "proxies": ("AUDUSD", "AUS200", "XNGUSD")},
    {"name": "Platts JKM LNG and the oil-linked contract slope", "venue": "Platts / ICE",
     "why": "most Australian LNG volume is sold at 11-15% of a LAGGED crude average, so LNG "
            "revenue follows Brent with about a quarter's lag; the lag IS the mechanism",
     "proxies": ("XBRUSD", "XNGUSD", "AUDUSD")},
    {"name": "ASX SPI 200 index future (AP)", "venue": "ASX 24",
     "why": "expiry cash-settles to a Special Opening Quotation from constituent OPENING prices, "
            "so the expiry risk is an overnight gap into an open, not a close",
     "proxies": ("AUS200",)},
    {"name": "ASX 30-day interbank cash rate future (IB)", "venue": "ASX 24",
     "why": "the traded consensus for the cash rate; the surprise in AU-A is measured against it "
            "and cannot be reconstructed after the fact from end-of-day data alone",
     "proxies": ("AUDUSD", "AUDNZD", "AUS200")},
    {"name": "ASX 24 3-year (YT) and 10-year (XT) Treasury bond futures", "venue": "ASX 24",
     "why": "the AUD duration leg; the AGS-UST spread is where offshore demand for AUD duration "
            "shows up, and UST10Y is the only bond the desk holds",
     "proxies": ("UST10Y", "AUDUSD", "AUDJPY")},
    {"name": "S&P/ASX 200 cash index, its rebalance file and its dividend-point series",
     "venue": "S&P DJI / ASX",
     "why": "AUS200 is a broker CFD on the index, not the index's own book; the auction print, "
            "the rebalance effective date and the dividend points are external references",
     "proxies": ("AUS200",)},
    {"name": "NBS and Caixin China manufacturing PMI", "venue": "NBS / S&P Global",
     "why": "printed at 01:30 and 01:45 UTC inside the Sydney session, before Europe; the AUD is "
            "the most liquid China proxy open at that minute",
     "proxies": ("AUDUSD", "AUS200", "USDCNH", "CHINAH", "HK50")},
    {"name": "Port Hedland and Port of Newcastle monthly throughput",
     "venue": "Pilbara Ports Authority / Port of Newcastle",
     "why": "a counted physical export VOLUME, separable from price; the only way to ask whether "
            "the terms-of-trade channel is quantity or price",
     "proxies": ("AUDUSD", "AUS200")},
    {"name": "RBA trade-weighted index (TWI)", "venue": "RBA table F11",
     "why": "the Bank's own object of concern is the TWI, not the bilateral rate; USDX is the "
            "dollar's index and is not a substitute",
     "proxies": ("AUDUSD", "EURAUD", "GBPAUD", "AUDJPY")},
    {"name": "AUD/USD cross-currency basis swap", "venue": "OTC",
     "why": "where the major banks' offshore issuance hedge shows up; a regulatory consequence of "
            "NSFR-driven term funding, not a view",
     "proxies": ("AUDUSD", "AUDJPY")},
)

# --------------------------------------------------------------------------- the central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "Reserve Bank of Australia",
    "short": "RBA",
    "framework": "inflation_targeter",
    "committee": "Monetary Policy Board (from 2025; previously the Reserve Bank Board)",
    "policy_instrument": "cash rate target -- the unsecured overnight interbank rate, published "
                         "as AONIA",
    "corridor": "exchange settlement balances are remunerated 10bp below the target and the "
                "overnight repo facility sits 25bp above it",
    "mandate": "consumer price inflation of 2-3% on average over time, together with full "
               "employment, under the Statement on the Conduct of Monetary Policy",
    "decision_rule": "EIGHT scheduled meetings a year since 2024, down from eleven (previously "
                     "the first Tuesday of every month except January). Meetings run two days, "
                     "Monday and Tuesday; the decision and statement are published at 14:30 "
                     "Sydney and the Governor holds a press conference at 15:30 Sydney.",
    "announce_local": "14:30 Australia/Sydney",
    "announce_utc": "04:30",
    "announce_utc_dst": "03:30",
    "dst_rule": "Australia/Sydney is AEST (UTC+10) from the first Sunday in April to the first "
                "Sunday in October and AEDT (UTC+11) otherwise; the decision minute in UTC "
                "therefore MOVES twice a year and a fixed-UTC event window puts half the sample "
                "in the wrong bar",
    "presser_utc": "05:30",
    "minutes_lag_days": 14,
    "consensus_proxy": "ASX 30-day interbank cash rate future (IB). It settles to the MONTHLY "
                       "AVERAGE cash rate, so the implied rate immediately before the "
                       "announcement is a traded expectation in basis points -- this is the "
                       "cleanest consensus proxy in the desk's book.",
    "consensus_proxy_trap": "the monthly-average settlement means an implied rate part-way "
                            "through a month already embeds the days elapsed at the current "
                            "rate; an extraction that does not divide those out biases every "
                            "surprise toward zero and makes hawkish meetings look neutral",
    "balance_sheet_history": (
        "the 3-year yield target at 0.10% on the April-2024 bond, March 2020 to November 2021",
        "the Term Funding Facility, closed to new drawings June 2021 and fully repaid by mid-2024",
        "outright government bond purchases, November 2020 to February 2022"),
    "off_cycle": "the Board met out of cycle in March 2020 (twice); an unscheduled decision is "
                 "the single largest AUD event class and must not be pooled with scheduled ones",
    "other_clocks": (
        {"what": "Statement on Monetary Policy (the forecast table)",
         "when_local": "14:30 Sydney on the February, May, August and November decision days",
         "when_utc": "04:30", "reference_lag_days": 0},
        {"what": "Monetary Policy Board minutes",
         "when_local": "11:30 Sydney, about two weeks after the meeting",
         "when_utc": "01:30", "reference_lag_days": 14},
        {"what": "semi-annual parliamentary testimony (House Economics Committee)",
         "when_local": "Friday morning, February and August", "when_utc": "22:30",
         "reference_lag_days": 0},
        {"what": "Financial Stability Review", "when_local": "April and October",
         "when_utc": "01:30", "reference_lag_days": 0},
    ),
    "root": "https://www.rba.gov.au",
}

# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "RBA daily exchange rates (statistical table F11)",
     "local": "16:00 Australia/Sydney", "time_utc": "06:00", "time_utc_dst": "05:00",
     "dst_rule": "AEST/AEDT",
     "instruments": ("AUDUSD", "EURAUD", "AUDJPY"),
     "window_minutes": 5,
     "why": "the official Australian reference rate, used for accounting and ABS conversion; it "
            "is NOT a transactable benchmark and nobody is forced to trade at it, which is "
            "exactly why an effect here would be informative rather than mechanical"},
    {"name": "WM/Refinitiv 16:00 London fix",
     "local": "16:00 Europe/London, window 15:57:30-16:02:30", "time_utc": "16:00",
     "time_utc_dst": "15:00", "dst_rule": "GMT/BST",
     "instruments": ("AUDUSD", "EURAUD", "AUDJPY", "AUDNZD"),
     "window_minutes": 5,
     "why": "the benchmark superannuation hedge rebalancing and index funds transact at; the "
            "month-end fix is the heaviest of the year and is where AU-H's flow lands"},
    {"name": "ASX closing single-price auction",
     "local": "16:10-16:12 Australia/Sydney with a RANDOM end inside the window",
     "time_utc": "06:10", "time_utc_dst": "05:10", "dst_rule": "AEST/AEDT",
     "instruments": ("AUS200",), "window_minutes": 2,
     "why": "the official close of the S&P/ASX 200 and the reference price for every index event; "
            "the random end is a design choice against gaming and it predicts DIFFUSION of flow "
            "across the window rather than a spike at a known second"},
    {"name": "ASX SPI 200 Special Opening Quotation (SOQ)",
     "local": "constituent opening prices on expiry morning, 10:00-10:09 Sydney staggered",
     "time_utc": "00:00", "time_utc_dst": "23:00", "dst_rule": "AEST/AEDT",
     "instruments": ("AUS200",), "window_minutes": 30,
     "why": "the expiring SPI 200 cash-settles to an OPEN, not a close; Australian index expiry "
            "risk is therefore an overnight gap, the opposite of the US intuition"},
    {"name": "LBMA gold price PM auction (the USD leg of XAUAUD)",
     "local": "15:00 Europe/London", "time_utc": "15:00", "time_utc_dst": "14:00",
     "dst_rule": "GMT/BST", "instruments": ("XAUUSD", "XAUAUD"), "window_minutes": 15,
     "why": "the reference for Australian producer hedge marks and Perth Mint product pricing"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "AUD spot value date", "kind": "weekday", "convention": "T+2",
     "rollover_utc": "21:00 (EST) / 22:00 (EDT), 17:00 America/New_York",
     "instruments": ("AUDUSD", "AUDJPY", "AUDNZD"),
     "why": "Wednesday rollover carries the TRIPLE swap for the weekend value date; an AUDJPY "
            "carry study that ignores it books three days of carry into one bar and manufactures "
            "a Wednesday effect out of an accounting convention"},
    {"name": "superannuation quarter-end rebalance", "kind": "quarter_end",
     "convention": "last three business days of March, June, September and December",
     "rollover_utc": "15:00/16:00 (the WMR fix)",
     "instruments": ("AUDUSD", "EURAUD", "AUDJPY"),
     "why": "the flow's SIGN is set by the offshore equity return over the month, not by the "
            "calendar; see AU-H"},
    {"name": "Australian fiscal year end", "kind": "fiscal_year_end", "convention": "30 June",
     "rollover_utc": "15:00/16:00", "instruments": ("AUDUSD", "AUS200"),
     "why": "EOFY is the single largest rebalancing date of the Australian year and it is NOT 31 "
            "December; a December-anchored year-end study measures the wrong country"},
    {"name": "ASX cash equity settlement", "kind": "weekday", "convention": "T+2",
     "rollover_utc": "", "instruments": ("AUS200",),
     "why": "the ex-date is two business days before the record date; the price index drops the "
            "dividend on the ex-date and that drop is not a return"},
    {"name": "IB cash-rate future settlement", "kind": "month_end",
     "convention": "cash settled to the monthly AVERAGE cash rate; last trading day is the last "
                   "business day of the contract month",
     "rollover_utc": "06:30", "instruments": ("AUDUSD",),
     "why": "the averaging is what makes the implied-rate extraction non-trivial and it is the "
            "commonest source of a wrong surprise in AU-A"},
    {"name": "AUD OIS and swap conventions", "kind": "weekday",
     "convention": "T+2, quarterly AONIA compounding", "rollover_utc": "",
     "instruments": ("AUDUSD", "UST10Y"),
     "why": "AONIA (the RBA's own cash rate series) is the risk-free reference; BBSW survives as "
            "the CREDIT benchmark, so a curve built from the wrong one is a different curve and "
            "the spread between them is a funding-stress signal, not noise"},
)

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Australian Securities Exchange (ASX) -- cash market",
     "index_symbols": ("AUS200",),
     "open_local": "10:00 (staggered alphabetical 10:00-10:09)", "close_local": "16:00",
     "open_utc": "00:00", "close_utc": "06:00", "dst_rule": "AEST/AEDT, subtract one hour on AEDT",
     "auction": "pre-open 07:00-10:00, closing single-price auction 16:10-16:12 with a random end",
     "expiry_rule": "n/a (cash market)",
     "holidays": "the NEW SOUTH WALES public holiday calendar plus NSW Labour Day; early close "
                 "at 14:10 on 24 and 31 December",
     "notes": "the staggered open means the index level in the first nine minutes is a blend of "
              "opened and unopened constituents; an opening-gap study on AUS200 that uses the "
              "00:00 UTC bar is measuring a partially-open index"},
    {"name": "ASX 24 (derivatives)",
     "index_symbols": ("AUS200",),
     "open_local": "day 09:50, night 17:10", "close_local": "day 16:30, night 07:00",
     "open_utc": "23:50", "close_utc": "06:30", "dst_rule": "AEST/AEDT",
     "auction": "n/a",
     "expiry_rule": "SPI 200 (AP): third THURSDAY of March, June, September and December, cash "
                    "settled to the Special Opening Quotation. Bond futures YT/XT: the 15th of "
                    "March, June, September and December or the next business day. IB 30-day "
                    "cash rate: the last business day of the contract month.",
     "holidays": "the NSW calendar; the NIGHT session belongs to the PRECEDING business day's "
                 "calendar, which is the trap on an Australian holiday Monday",
     "notes": "the quarterly index REBALANCE is effective after the close of the third FRIDAY -- "
              "a different day from the third-Thursday expiry, and conflating them destroys AU-G"},
    {"name": "Cboe Australia (formerly Chi-X)",
     "index_symbols": (),
     "open_local": "10:00", "close_local": "16:00", "open_utc": "00:00", "close_utc": "06:00",
     "dst_rule": "AEST/AEDT", "auction": "no closing auction that sets the official index close",
     "expiry_rule": "n/a", "holidays": "the NSW calendar",
     "notes": "roughly a fifth of Australian lit volume trades here, so an ASX-only volume series "
              "understates turnover; the OFFICIAL close is still ASX's auction"},
)


# --------------------------------------------------------------------------- holidays
def _western_easter(year: int) -> date:
    """Anonymous Gregorian computus, exact for 1583-4099. Good Friday is this minus two days."""
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


def _next_business_day(day: date) -> date:
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


#: Fixed-date national observances. STATE-only holidays (WA and QLD Labour Day, the Queen's/King's
#: Birthday in WA and QLD, agricultural show days, Melbourne Cup) are deliberately absent: they
#: are state law, they move, and the ASX does not observe them.
FIXED_NATIONAL: tuple[tuple[int, int, str], ...] = (
    (1, 1, "New Year's Day"),
    (1, 26, "Australia Day"),
    (4, 25, "Anzac Day"),
    (12, 25, "Christmas Day"),
    (12, 26, "Boxing Day"),
)

#: THE ANZAC DAY SUBSTITUTION RULE THIS PACK USES, DECLARED because there is no national rule and
#: guessing one would be wrong for four states whichever way it was written. When 25 April falls
#: on a Saturday or Sunday, Western Australia and the Northern Territory gazette the following
#: Monday as an additional public holiday; New South Wales, Victoria, Tasmania and South
#: Australia do not. Queensland and the ACT have varied their practice and are recorded as
#: UNMEASURED rather than asserted. The ASX and ASX 24 follow the NSW calendar, so
#: `market_holidays` never carries the substitute.
ANZAC_SUBSTITUTING_STATES: tuple[str, ...] = ("WA", "NT")
ANZAC_NON_SUBSTITUTING_STATES: tuple[str, ...] = ("NSW", "VIC", "TAS", "SA")
ANZAC_UNMEASURED_STATES: tuple[str, ...] = ("QLD", "ACT")


def national_holidays(year: int) -> dict[date, str]:
    """The federal-plus-common Australian public holidays for `year`, computed from rules.

    New Year's Day, Australia Day, Christmas and Boxing Day are Mondayised in every state.
    ANZAC DAY IS NOT MONDAYISED HERE -- see `state_substitutions`, because the answer is state law.
    """
    out: dict[date, str] = {}
    easter = _western_easter(year)
    out[easter - timedelta(days=2)] = "Good Friday"
    out[easter - timedelta(days=1)] = "Easter Saturday"
    out[easter + timedelta(days=1)] = "Easter Monday"
    out[_nth_weekday(year, 6, 0, 2)] = "King's Birthday (NSW, VIC and most states)"
    for month, day, label in FIXED_NATIONAL:
        actual = date(year, month, day)
        out[actual] = label
        if label == "Anzac Day" or actual.weekday() < 5:
            continue
        substitute = _next_business_day(actual)
        while substitute in out:
            substitute += timedelta(days=1)
        out[substitute] = f"{label} (observed)"
    return dict(sorted(out.items()))


def state_substitutions(year: int) -> dict[date, str]:
    """The Anzac Day substitute Monday and who takes it. Empty when 25 April is a weekday, which
    is the whole reason this is kept apart from the national set."""
    anzac = date(year, 4, 25)
    if anzac.weekday() < 5:
        return {}
    states = ", ".join(ANZAC_SUBSTITUTING_STATES)
    return {_next_business_day(anzac):
            f"Anzac Day substitute ({states} only; NSW does not, so the ASX trades)"}


def market_holidays(year: int) -> dict[date, str]:
    """The days the ASX and ASX 24 are CLOSED -- the New South Wales calendar, which is what
    AUS200 obeys. Excludes Easter Saturday (a Saturday anyway), excludes the Anzac substitute,
    and adds NSW Labour Day on the first Monday of October."""
    out = {d: n for d, n in national_holidays(year).items() if n != "Easter Saturday"}
    out[_nth_weekday(year, 10, 0, 1)] = "Labour Day (NSW)"
    return dict(sorted(out.items()))


def market_half_days(year: int) -> dict[date, str]:
    """ASX early closes at 14:10 Sydney (04:10 UTC AEDT)."""
    return {date(year, 12, 24): "Christmas Eve (ASX closes 14:10)",
            date(year, 12, 31): "New Year's Eve (ASX closes 14:10)"}


def spi_expiries(year: int) -> dict[date, str]:
    """SPI 200 expiry: the third THURSDAY of March, June, September and December."""
    return {_nth_weekday(year, m, 3, 3): f"SPI 200 expiry {year}-{m:02d}" for m in (3, 6, 9, 12)}


def index_rebalance_effective(year: int) -> dict[date, str]:
    """S&P/ASX quarterly rebalance, effective after the close of the third FRIDAY. A DIFFERENT
    day from the expiry above."""
    return {_nth_weekday(year, m, 4, 3): f"S&P/ASX rebalance effective {year}-{m:02d}"
            for m in (3, 6, 9, 12)}


def is_market_holiday(day: date) -> bool:
    return day in market_holidays(day.year)


HOLIDAYS_RULE: dict[str, Any] = {
    "kind": "computed_from_rules",
    "authority": "STATE law; there is no national public holiday act. The ASX and ASX 24 observe "
                 "the New South Wales calendar.",
    "years": (2024, 2025, 2026),
    "weekend": "Saturday and Sunday",
    "national_rule": "New Year's Day, Australia Day (26 January), Good Friday, Easter Saturday, "
                     "Easter Monday, Anzac Day (25 April), King's Birthday (second Monday of "
                     "June in NSW/VIC and most states), Christmas Day and Boxing Day. All except "
                     "Anzac Day are Mondayised when they fall on a weekend.",
    "market_rule": "the NSW calendar plus NSW Labour Day (first Monday of October); early close "
                   "at 14:10 Sydney on 24 and 31 December",
    "anzac_substitution_rule": "DECLARED, not inferred: WA and NT gazette the following Monday "
                               "when 25 April falls on a weekend; NSW, VIC, TAS and SA do not; "
                               "QLD and ACT practice has varied and is UNMEASURED here",
    "moving_feasts": "only Easter, which is computed exactly by the anonymous Gregorian algorithm",
    "known_dates": {
        "2024-04-25": "Anzac Day, Thursday -- no substitution anywhere",
        "2025-01-27": "Australia Day observed (26 January 2025 was a Sunday)",
        "2025-04-25": "Anzac Day, Friday -- no substitution anywhere",
        "2026-01-26": "Australia Day, Monday -- no substitution needed",
        "2026-04-25": "Anzac Day, SATURDAY. WA and NT take Monday 2026-04-27; the ASX does NOT, "
                      "so AUS200 trades a normal session that day",
        "2026-04-27": "the Anzac substitute: a public holiday in WA and NT only",
    },
    "fn": market_holidays,
    "national_fn": national_holidays,
    "substitutions_fn": state_substitutions,
    "half_days_fn": market_half_days,
    "expiry_fn": spi_expiries,
    "rebalance_fn": index_rebalance_effective,
}

# --------------------------------------------------------------------------- positioning
COT_CURRENCY = "AUD"
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "CFTC Commitments of Traders -- CME Australian dollar futures (6A, code 232741)",
     "root": "https://www.cftc.gov/MarketReports/CommitmentsofTraders/",
     "fields": ("non_commercial_long", "non_commercial_short", "commercial_long",
                "commercial_short", "leveraged_funds_net", "asset_manager_net", "open_interest"),
     "frequency": "weekly", "snapshot": "Tuesday close",
     "publish_utc": "19:30 (EDT) / 20:30 (EST), Friday", "lag_days": 3,
     "licence": "free, public (US government work)", "available": True,
     "why": "AUD is one of the few currencies in this pack with a real positioning series; "
            "extremes in leveraged-fund net are the forced-liquidation risk AU-F is about",
     "pit_warning": "the snapshot is THREE DAYS STALE on release. Aligning it to the Tuesday bar "
                    "is a look-ahead bug that manufactures predictability out of nothing"},
    {"name": "CME 6A daily volume and open interest",
     "root": "https://www.cmegroup.com/markets/fx/g10/australian-dollar.volume.html",
     "fields": ("volume", "open_interest"), "frequency": "daily", "snapshot": "session close",
     "publish_utc": "12:00", "lag_days": 1, "licence": "free, public", "available": True,
     "why": "the fast complement to the weekly COT; OI change is same-direction evidence",
     "pit_warning": "preliminary OI is restated the following morning"},
    {"name": "RBA foreign exchange transactions (the Bank's own flows)",
     "root": "https://www.rba.gov.au/statistics/tables/",
     "fields": ("net_transactions_aud", "spot", "swap"), "frequency": "monthly",
     "snapshot": "calendar month", "publish_utc": "01:30", "lag_days": 25,
     "licence": "free, public", "available": True,
     "why": "the only published record of official AUD flow; small, but it is the actor's own "
            "ledger rather than an inference",
     "pit_warning": "weeks of lag; never usable intramonth and never as a same-month conditioner"},
    {"name": "an Australian-venue trader-category positioning report",
     "root": "", "fields": (), "frequency": "n/a", "snapshot": "", "publish_utc": "",
     "lag_days": 0, "licence": "", "available": False,
     "why": "ASX publishes open interest but NOT a trader-category breakdown",
     "pit_warning": "DOES NOT EXIST. Australian-venue positioning is UNMEASURED and must be "
                    "reported as such, never silently proxied by the CME series -- the two books "
                    "have different participants and different hours"},
)

# --------------------------------------------------------------------------- terminology
#: Australia's native language is English, so this layer is a VOCABULARY problem, not a
#: translation problem: these are the terms Australian market text uses that a screen trained on
#: US or European sources mis-reads, and each mis-read assigns the wrong actor to a claim.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "AU-A": ("the cash rate", "the cash rate target", "on hold", "the Board", "a live meeting",
             "the IB strip", "trimmed mean", "the underlying"),
    "AU-B": ("SoMP", "Statement on Monetary Policy", "the minutes", "forecast revision",
             "the technical assumptions"),
    "AU-C": ("terms of trade", "the bulks", "the Pilbara", "tonnage", "FOB", "the ore price",
             "Newcastle coal", "hard coking"),
    "AU-D": ("China PMI", "the credit impulse", "port stocks", "mill margins", "Caixin"),
    "AU-E": ("the cross", "the Tasman", "the Tasman cross", "relative carry", "the OCR"),
    "AU-F": ("the carry", "the unwind", "risk-off", "the yen cross", "margin call"),
    "AU-G": ("the SPI", "the close", "the auction", "the rebalance", "the SOQ", "expiry week"),
    "AU-H": ("super", "the super funds", "the hedge ratio", "rebalance", "EOFY", "strategic asset "
             "allocation"),
    "AU-I": ("franking", "fully franked", "the imputation credit", "ex-date", "the payout",
             "dividend season"),
    "AU-J": ("labour force", "the unemployment rate", "WPI", "the monthly indicator",
             "retail trade", "the trade balance"),
    "AU-K": ("ACGB", "the tender", "coverage", "the spread to Treasuries", "the linker",
             "syndication"),
    "AU-L": ("the rollover", "tom-next", "the Sydney open", "triple swap", "the handover"),
    "AU-M": ("the crop report", "the harvest", "FOB basis", "the pool", "ABARES"),
    "AU-N": ("the gold price in Aussie", "producer hedging", "the Mint", "the AUD gold price"),
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


#: AUSTRALIA'S TEN LAYERS. English is the native language here, so the `queries` are not
#: translations -- they are the Australian VOCABULARY and slang a US- or UK-trained screen
#: misreads: "the majors" is four banks and not an FX pair, "the SPI" is a futures contract,
#: "ramping" is a forum accusation with a regulatory meaning, and "EOFY" is 30 June.
SOURCE_CLASSES: tuple[dict[str, Any], ...] = (
    source_class(
        "au_rba", "Reserve Bank of Australia primary publications", layer="official",
        roots=("https://www.rba.gov.au/media-releases/",
               "https://www.rba.gov.au/monetary-policy/rba-board-minutes/",
               "https://www.rba.gov.au/publications/smp/",
               "https://www.rba.gov.au/statistics/tables/"),
        queries=("cash rate decision", "cash rate target", "Statement on Monetary Policy",
                 "SoMP", "trimmed mean", "Board minutes", "exchange settlement balances",
                 "AONIA", "yield target", "Term Funding Facility"),
        languages=("en",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="Creative Commons BY 4.0",
        notes="the four objects AU-A and AU-B are built on; media releases are never revised and "
              "carry a published timestamp"),
    source_class(
        "au_abs", "Australian Bureau of Statistics", layer="official",
        roots=("https://www.abs.gov.au/release-calendar",
               "https://www.abs.gov.au/statistics/economy",
               "https://www.abs.gov.au/statistics/labour"),
        queries=("labour force", "unemployment rate", "consumer price index", "trimmed mean",
                 "wage price index", "retail trade", "international trade in goods",
                 "monthly CPI indicator", "release calendar"),
        languages=("en",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="Creative Commons BY 4.0",
        notes="REVISED: seasonally adjusted series are re-estimated, so a vintage stamp is "
              "mandatory and the first print must be kept separately"),
    source_class(
        "au_fiscal", "AOFM, Commonwealth Budget and the WA state budget", layer="official",
        roots=("https://www.aofm.gov.au/auction-results", "https://budget.gov.au",
               "https://www.ourstatebudget.wa.gov.au"),
        queries=("AOFM tender", "coverage ratio", "weighted average yield", "ACGB",
                 "issuance programme", "MYEFO", "iron ore price assumption", "royalty receipts"),
        languages=("en",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the tender calendar for AU-K and the published iron-ore price assumption for AU-C"),
    source_class(
        "au_apra_cftc", "APRA prudential statistics and the CFTC Commitments of Traders",
        layer="official",
        roots=("https://www.apra.gov.au/quarterly-superannuation-statistics",
               "https://www.apra.gov.au/monthly-authorised-deposit-taking-institution-statistics",
               "https://www.cftc.gov/MarketReports/CommitmentsofTraders/"),
        queries=("quarterly superannuation performance", "international assets", "net flows",
                 "monthly ADI statistics", "Commitments of Traders", "leveraged funds net",
                 "Australian dollar futures"),
        languages=("en",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="APRA back series are RESTATED when reporting standards change, a silent break; the "
              "COT Tuesday snapshot is three days stale and the staleness is structural"),
    source_class(
        "au_asx", "ASX and Cboe Australia exchange publications", layer="institutional",
        roots=("https://www.asx.com.au/about/market-info",
               "https://www.asx.com.au/markets/trade-our-derivatives-market",
               "https://www.cboe.com.au/"),
        queries=("SPI 200", "the SPI", "ASX 24", "special opening quotation", "SOQ",
                 "closing single price auction", "CSPA", "expiry calendar", "30-day interbank",
                 "IB futures"),
        languages=("en",), access_label="PUBLIC_WITH_TERMS", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED",
        licence="headline and end-of-day free; DEPTH AND TICK DATA ARE LICENSED",
        notes="AU-G's order-book questions are declared UNMEASURED rather than approximated, "
              "because the depth feed is a licensed product the desk does not hold"),
    source_class(
        "au_spdji_afma", "S&P Dow Jones Indices and the Australian industry bodies",
        layer="institutional",
        roots=("https://www.spglobal.com/spdji/en/index-announcements/",
               "https://afma.com.au/", "https://www.superannuation.asn.au/"),
        queries=("index announcement", "effective date", "quarterly rebalance",
                 "float adjustment", "index dividend points", "AFMA conventions",
                 "AUD market conventions", "ASFA"),
        languages=("en",), access_label="PUBLIC_WITH_TERMS", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free headline; index data licensed",
        notes="AFMA publishes the authoritative AUD market conventions this pack's settlement "
              "rules describe; an S&P announcement's EFFECTIVE date is not its announcement date"),
    source_class(
        "au_multilateral", "BIS, IMF and OECD Australia coverage", layer="institutional",
        roots=("https://www.bis.org/statistics/", "https://www.imf.org/en/Countries/AUS",
               "https://data.oecd.org/"),
        queries=("triennial survey", "FX turnover", "cross-currency basis", "Article IV",
                 "external position", "terms of trade"),
        languages=("en",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the BIS Triennial is the only survey of Australian FX turnover and it is "
              "triennial, so an intervening year is UNMEASURED rather than interpolated"),
    source_class(
        "au_rba_research", "RBA Research Discussion Papers and Bulletin", layer="academic",
        roots=("https://www.rba.gov.au/publications/rdp/",
               "https://www.rba.gov.au/publications/bulletin/"),
        queries=("research discussion paper", "RDP", "hedging behaviour", "currency overlay",
                 "terms of trade shock", "commodity currency", "market operations",
                 "liquidity in the foreign exchange market"),
        languages=("en",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="CC BY 4.0",
        notes="the RBA writes unusually explicit papers on its own operations, the AUD's "
              "commodity relationship and the superannuation hedging channel -- the best free "
              "description of AU-C and AU-H that exists anywhere"),
    source_class(
        "au_academic", "Australian finance research and working-paper repositories",
        layer="academic",
        roots=("https://papers.ssrn.com/", "https://ideas.repec.org/",
               "https://arxiv.org/list/q-fin/recent"),
        queries=("closing auction price discovery ASX", "index inclusion effect Australia",
                 "franking credit", "imputation", "dividend drop-off ratio",
                 "superannuation hedge ratio", "commodity currency predictability"),
        languages=("en",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED",
        licence="per-paper; some repository terms forbid bulk download",
        notes="the dividend drop-off and closing-auction literature is largely Australian and "
              "largely here; a working paper is revised in place so the VERSION is the datum"),
    source_class(
        "au_practitioner", "Livewire, MacroBusiness and Australian practitioner commentary",
        layer="practitioner",
        roots=("https://www.livewiremarkets.com/", "https://www.macrobusiness.com.au/"),
        queries=("the bulks", "the Pilbara", "iron ore price deck", "super fund flows",
                 "unhedged international equities", "the majors", "franking", "EOFY",
                 "the cross", "the Tasman"),
        languages=("en",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", machine_use_allowed=True,
        licence="public web; terms restrict automated extraction",
        notes="fund managers and economists describing the mechanism they think they are "
              "trading; READ AND CITED, NEVER SCRAPED, and registered here so the ground is "
              "known to exist"),
    source_class(
        "au_sellside", "Published Australian bank and independent economist notes",
        layer="practitioner",
        roots=("https://www.amp.com.au/insights-hub", "https://business.nab.com.au/insight/",
               "https://www.westpaciq.com.au/"),
        queries=("cash rate call", "terminal rate", "RBA preview", "CPI preview",
                 "labour force preview", "AUD forecast", "house view"),
        languages=("en",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NOT_PREDICTIVE", machine_use_allowed=True,
        licence="public web; redistribution restricted",
        notes="the SURVEY consensus AU-A deliberately does not use, kept precisely so the "
              "traded-curve surprise can be compared against it -- NOT_PREDICTIVE is a measured "
              "verdict about economist medians, not a slur"),
    source_class(
        "au_hotcopper", "HotCopper", layer="retail_ecology",
        roots=("https://hotcopper.com.au/",),
        queries=("ramping", "ramper", "bag holder", "DYOR", "T+2", "the punt", "tinnies",
                 "going to the moon", "shorters", "sp on fire"),
        languages=("en",), access_label="PUBLIC_SOCIAL", credibility="FRINGE",
        predictive_state="UNTESTED", machine_use_allowed=True,
        licence="public forum; terms restrict automated extraction",
        notes="Australia's largest retail equity forum, overwhelmingly single-name and "
              "promotional. KEPT AT LOW WEIGHT RATHER THAN DROPPED: ramping episodes are a real "
              "microstructure phenomenon with dates and this is where they are visible"),
    source_class(
        "au_reddit", "Reddit r/AusFinance and r/ASX_Bets, Aussie Stock Forums",
        layer="retail_ecology",
        roots=("https://www.reddit.com/r/AusFinance/", "https://www.reddit.com/r/ASX_Bets/",
               "https://www.aussiestockforums.com/"),
        queries=("switching to cash", "the super switch", "salary sacrifice", "franking refund",
                 "ASX bets", "YOLO", "offset account", "fixed vs variable"),
        languages=("en",), access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="public social; API terms govern automated access",
        notes="the super-switching behaviour discussed here is a genuine flow channel into "
              "AU-H; low weight, never zero, and deleted content is unrecoverable"),
    source_class(
        "au_whirlpool", "Whirlpool finance and mortgage forums", layer="retail_ecology",
        roots=("https://forums.whirlpool.net.au/forum/136",),
        queries=("fixed rate roll off", "mortgage cliff", "refinance cashback", "offset",
                 "rate rise", "repayment shock"),
        languages=("en",), access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
        predictive_state="NARRATIVE_FEATURE", machine_use_allowed=True,
        licence="public forum; automated extraction restricted",
        notes="Australia's variable-rate mortgage book is the RBA's main transmission channel, "
              "and this is where households describe reacting to it in real time -- a "
              "high-frequency read on a channel that is otherwise quarterly"),
    source_class(
        "au_mql5", "MQL5 Market, CodeBase and forum for AUD and AUS200 robots",
        layer="app_ecosystem",
        roots=("https://www.mql5.com/en/market", "https://www.mql5.com/en/code",
               "https://www.mql5.com/en/forum"),
        queries=("expert advisor", "EA", "MQL5", "MT4", "MT5", "strategy tester",
                 "optimisation", "indicator", "grid EA", "martingale", "AUDUSD scalper",
                 "AUS200 bot", "depth of market", "DOM"),
        languages=("en",), access_label="PUBLIC_WITH_TERMS", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="public with terms; the desk already mines this",
        notes="the MetaTrader ecosystem is where retail algorithmic ideas about AUDUSD and "
              "AUS200 are written down as CODE -- a mechanism claim with an implementation, "
              "which is rarer and far more testable than prose. Published backtests are "
              "curve-fitted almost without exception and are treated as CLAIMS"),
    source_class(
        "au_tradingview", "TradingView public scripts and ideas on AUD and AUS200",
        layer="app_ecosystem",
        roots=("https://www.tradingview.com/scripts/",
               "https://www.tradingview.com/symbols/AUDUSD/"),
        queries=("Pine Script", "indicator", "strategy", "AUDUSD idea", "AUS200 idea",
                 "session open range", "London breakout", "Asian range"),
        languages=("en",), access_label="PUBLIC_WITH_TERMS", credibility="UNRELIABLE",
        predictive_state="UNTESTED", machine_use_allowed=True,
        licence="public with terms; automated extraction restricted",
        notes="the largest public library of executable indicator definitions; registered and "
              "read, never scraped"),
    source_class(
        "au_brokers", "Australian retail broker and investing app ecosystems",
        layer="app_ecosystem",
        roots=("https://www.commsec.com.au/", "https://hellostake.com/",
               "https://superhero.com.au/", "https://www.sharesight.com/"),
        queries=("CommSec", "Stake", "Superhero", "Pearler", "Sharesight", "brokerage",
                 "CHESS sponsored", "custodial model", "fractional shares", "CFD leverage cap"),
        languages=("en",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", machine_use_allowed=True,
        licence="public marketing pages; account data is PRIVATE and is never sought",
        notes="which instruments Australian retail can actually reach and at what cost -- the "
              "feasibility side of any retail-flow hypothesis. NO ACCOUNT-LEVEL DATA is sought: "
              "that would be PRIVATE and is out of bounds"),
    source_class(
        "au_press", "Australian Financial Review, The Australian and the public broadcasters",
        layer="media",
        roots=("https://www.afr.com", "https://www.theaustralian.com.au/business",
               "https://www.abc.net.au/news/business"),
        queries=("Chanticleer", "market wrap", "the close", "results season",
                 "profit downgrade", "guidance", "block trade", "capital raising"),
        languages=("en",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", machine_use_allowed=True,
        licence="paywalled; terms forbid automated extraction (ABC is free and open)",
        notes="the AFR breaks Australian market-structure stories first; read and cited, never "
              "scraped. Stories are updated in place with no version history, so the timestamp "
              "is first publication only"),
    source_class(
        "au_wires", "Reuters and Bloomberg Australian coverage", layer="media",
        roots=("https://www.reuters.com/markets/asia/", "https://www.bloomberg.com/australia"),
        queries=("RBA decision", "AUD reaction", "iron ore", "headline", "flash"),
        languages=("en",), access_label="LICENSED", credibility="RELIABLE",
        predictive_state="UNTESTED", machine_use_allowed=True,
        licence="terminal and wire content is LICENSED; the desk holds no licence",
        notes="REGISTERED BECAUSE THE ABSENCE MATTERS: for a story that moved the market the "
              "desk's best timestamp is a free outlet's republication, minutes to hours late. "
              "That gap is a named limitation on every AU-J event window, not an oversight"),
    source_class(
        "au_trove", "Trove, the National Library of Australia's archive", layer="archive",
        roots=("https://trove.nla.gov.au/",),
        queries=("historical newspaper", "contemporaneous report", "market report",
                 "wool price", "credit squeeze", "float of the dollar"),
        languages=("en",), access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public; an open API",
        notes="recovers the CONTEMPORANEOUS view of a policy episode. The 2021 yield-target break "
              "reads very differently in 2021 than in hindsight, and AU-A's era work needs the "
              "first reading, not the remembered one"),
    source_class(
        "au_wayback", "Internet Archive captures of RBA, ASX and ABS pages", layer="archive",
        roots=("https://web.archive.org/web/*/rba.gov.au*",
               "https://web.archive.org/web/*/asx.com.au*",
               "https://web.archive.org/web/*/abs.gov.au*"),
        queries=("first print", "superseded release", "revised in place", "back series",
                 "vintage", "historical announcement"),
        languages=("en",), access_label="PUBLIC_ARCHIVE", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE POINT-IN-TIME TOOL OF LAST RESORT: where a publisher revised a page in place, "
              "the Wayback capture is the only surviving first print and the only defence "
              "against a source that overwrites its own history"),
    source_class(
        "au_ports", "Pilbara Ports, Port of Newcastle and Gladstone Ports throughput",
        layer="physical_economy",
        roots=("https://www.pilbaraports.com.au", "https://www.portofnewcastle.com.au",
               "https://www.gpcl.com.au"),
        queries=("Port Hedland", "Dampier", "Cape Lambert", "monthly throughput", "tonnes",
                 "vessel line-up", "iron ore exports", "coal exports", "LNG throughput"),
        languages=("en",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="A COUNTED PHYSICAL FLOW. The AUD's largest fundamental driver is a tonnage "
              "somebody publishes monthly and free, which is the only reason AU-C can separate "
              "export price from export volume at all"),
    source_class(
        "au_abares_bom", "ABARES crop reports and the Bureau of Meteorology",
        layer="physical_economy",
        roots=("https://www.agriculture.gov.au/abares/research-topics/agricultural-commodities/"
               "australian-crop-report", "http://www.bom.gov.au/climate/"),
        queries=("crop report", "production estimate", "winter crop", "rainfall deciles",
                 "soil moisture", "harvest", "receivals", "FOB basis"),
        languages=("en",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="rainfall is the exogenous driver behind AU-M's production revisions, and weather "
              "is the cleanest instrument in agricultural economics because nothing the market "
              "does causes it"),
    source_class(
        "au_aemo_ais", "AEMO market data and shipping AIS", layer="physical_economy",
        roots=("https://aemo.com.au/energy-systems/electricity/national-electricity-market-nem/"
               "data-nem", "https://www.marinetraffic.com/"),
        queries=("NEM dispatch", "demand forecast", "interconnector flow", "AIS", "vessel "
                 "tracking", "laycan", "loading"),
        languages=("en",), access_label="LICENSED", credibility="RELIABLE",
        predictive_state="UNTESTED", machine_use_allowed=True,
        licence="AEMO is OPEN_DATA; AIS history and bulk access are LICENSED and not held",
        notes="AEMO publishes five-minute dispatch free, among the highest-frequency real-economy "
              "series in this department. AIS would give ore loadings at daily rather than "
              "monthly frequency and the desk holds no licence -- a NAMED GAP, not an omission"),
    source_class(
        "au_citation_graph", "RePEc, Semantic Scholar and OpenAlex citation graphs",
        layer="source_graph",
        roots=("https://ideas.repec.org/", "https://www.semanticscholar.org/",
               "https://openalex.org/"),
        queries=("cited by", "replication", "working paper version", "who cites whom",
                 "Australian market microstructure", "dividend drop-off replication"),
        languages=("en",), access_label="OPEN_DATA", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public; open citation graphs",
        notes="WHO CITES WHOM says which Australian mechanism claims were replicated and which "
              "are one paper repeated -- a survivorship check the papers themselves cannot give"),
    source_class(
        "au_desk_registry", "The desk's own source registry and coverage map",
        layer="source_graph",
        roots=("desks/mt5/data/data_universe_map.json",
               "desks/mt5/data/deep_forest_sources.json"),
        queries=("coverage map", "source registry", "already mined", "duplicate ground"),
        languages=("en",), access_label="PRIVATE", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="desk-owned",
        notes="the edge set between this pack's sources and the desk's existing corpus; it is how "
              "a new source is recognised as new rather than as a fourth copy of one already "
              "mined, which is the failure mode of every hand-kept source list"),
    source_class(
        "au_code_graph", "GitHub and package-index graphs for Australian quant code",
        layer="source_graph",
        roots=("https://github.com/search?q=asx+backtest", "https://pypi.org/"),
        queries=("asx backtest", "australian equities data", "yfinance ASX", "fork",
                 "dependency", "stars"),
        languages=("en",), access_label="PUBLIC_WITH_TERMS", credibility="UNRELIABLE",
        predictive_state="UNTESTED",
        licence="per-repository licences; check each before reading, never vendor code",
        notes="fork and dependency edges show which Australian backtest ideas propagated and "
              "which died -- a POPULARITY signal, not an evidence signal, and weighted as such"),
)

#: Layers with no Australian source worth naming. Empty here: all ten are populated, which is
#: itself the measurement -- Australia is a deep, open, English-language ground and a thin pack
#: would have been a statement about the reader rather than about the country.
LAYER_ABSENCES: dict[str, str] = {}

# --------------------------------------------------------------------------- datasets
DATASETS: tuple[dict[str, Any], ...] = (
    {"name": "RBA cash rate decisions and statements", "source": "RBA media releases",
     "coverage": "1990 onward", "frequency": "8 per year", "publication_lag_days": 0.0,
     "revisions": "never revised", "licence": "free, public", "history_from": "1990-01",
     "pit_feasible": True, "assets": ("AUDUSD", "AUDNZD", "AUS200"),
     "fields": ("decision_date", "effective_date", "target_pct", "change_bp", "statement_text",
                "scheduled_flag"),
     "pit_fields": ("release_ts_utc", "scheduled_flag"),
     "mechanism_families": ("event_reaction", "policy_surprise"),
     "how_to_fetch": "rba.gov.au/media-releases/ index by year; the RSS feed carries timestamps"},
    {"name": "ASX 30-day interbank cash rate future implied path", "source": "ASX settlements",
     "coverage": "2001 onward", "frequency": "daily", "publication_lag_days": 0.0,
     "revisions": "settlements final", "licence": "free end-of-day", "history_from": "2001-01",
     "pit_feasible": False, "assets": ("AUDUSD", "AUDNZD", "AUS200"),
     "fields": ("trade_date", "contract_month", "settlement_price", "implied_avg_cash_rate"),
     "pit_fields": ("settlement_ts_utc", "contract_expiry"),
     "mechanism_families": ("policy_surprise",),
     "how_to_fetch": "ASX daily settlement files. PIT IS PARTIAL: the pre-announcement INTRADAY "
                     "snapshot at 04:25 UTC cannot be reconstructed from end-of-day data and must "
                     "be captured live, so a past meeting whose snapshot was not captured has an "
                     "UNMEASURED surprise rather than a zero one"},
    {"name": "Statement on Monetary Policy forecast table", "source": "RBA",
     "coverage": "1997 onward", "frequency": "quarterly", "publication_lag_days": 0.0,
     "revisions": "each issue supersedes the last; the revision IS the datum",
     "licence": "free, public", "history_from": "1997-05", "pit_feasible": True,
     "assets": ("AUDUSD", "AUS200", "UST10Y"),
     "fields": ("somp_date", "horizon", "gdp_pct", "unemployment_pct", "trimmed_mean_pct",
                "headline_cpi_pct", "cash_rate_assumption"),
     "pit_fields": ("release_ts_utc", "vintage", "prior_vintage_ref"),
     "mechanism_families": ("event_reaction", "forecast_revision"),
     "how_to_fetch": "rba.gov.au/publications/smp/ -- the forecast table is a stable HTML table"},
    {"name": "Consumer Price Index, quarterly and the monthly indicator", "source": "ABS",
     "coverage": "1948 quarterly, 2018 monthly", "frequency": "quarterly and monthly",
     "publication_lag_days": 25.0,
     "revisions": "headline not revised; seasonally adjusted components are",
     "licence": "free, public (CC BY 4.0)", "history_from": "1948-09", "pit_feasible": True,
     "assets": ("AUDUSD", "AUS200", "AUDNZD"),
     "fields": ("reference_period", "headline_qoq", "trimmed_mean_qoq", "weighted_median_qoq",
                "monthly_indicator_yoy"),
     "pit_fields": ("release_ts_utc", "vintage", "first_print_flag"),
     "mechanism_families": ("event_reaction", "macro_condition"),
     "how_to_fetch": "abs.gov.au release pages; the 11:30 Sydney embargo minute is the event time"},
    {"name": "Labour Force, Australia", "source": "ABS", "coverage": "1978 onward",
     "frequency": "monthly", "publication_lag_days": 15.0,
     "revisions": "REVISED: seasonal factors are re-estimated and the back series moves",
     "licence": "free, public", "history_from": "1978-02", "pit_feasible": True,
     "assets": ("AUDUSD", "AUS200"),
     "fields": ("reference_month", "unemployment_rate", "employment_change", "participation_rate",
                "full_time_change", "hours_worked"),
     "pit_fields": ("release_ts_utc", "vintage", "seasonal_revision_flag"),
     "mechanism_families": ("event_reaction",),
     "how_to_fetch": "abs.gov.au/statistics/labour; typically the third Thursday at 11:30 Sydney"},
    {"name": "International Trade in Goods", "source": "ABS", "coverage": "1971 onward",
     "frequency": "monthly", "publication_lag_days": 35.0, "revisions": "revised for two months",
     "licence": "free, public", "history_from": "1971-07", "pit_feasible": True,
     "assets": ("AUDUSD", "AUS200"),
     "fields": ("reference_month", "exports_total", "exports_metal_ores", "exports_coal",
                "exports_lng", "imports_total", "balance"),
     "pit_fields": ("release_ts_utc", "vintage"),
     "mechanism_families": ("macro_condition", "terms_of_trade"),
     "how_to_fetch": "abs.gov.au/statistics/economy/international-trade"},
    {"name": "Pilbara Ports monthly throughput", "source": "Pilbara Ports Authority",
     "coverage": "2010 onward", "frequency": "monthly", "publication_lag_days": 12.0,
     "revisions": "occasionally restated", "licence": "free, public", "history_from": "2010-07",
     "pit_feasible": True, "assets": ("AUDUSD", "AUS200"),
     "fields": ("month", "port", "iron_ore_tonnes", "total_tonnes", "vessel_calls"),
     "pit_fields": ("publish_ts_utc", "vintage"),
     "mechanism_families": ("terms_of_trade", "corporate_flow"),
     "how_to_fetch": "pilbaraports.com.au monthly throughput tables (HTML/PDF)"},
    {"name": "Resources and Energy Quarterly", "source": "ABARES", "coverage": "2010 onward",
     "frequency": "quarterly", "publication_lag_days": 20.0,
     "revisions": "forecasts revised every issue", "licence": "free, public",
     "history_from": "2010-03", "pit_feasible": True,
     "assets": ("AUDUSD", "XBRUSD", "XNGUSD"),
     "fields": ("quarter", "commodity", "export_volume", "export_value", "price_forecast"),
     "pit_fields": ("release_ts_utc", "vintage"),
     "mechanism_families": ("terms_of_trade",),
     "how_to_fetch": "agriculture.gov.au/abares -- CSV data cubes accompany each issue"},
    {"name": "Australian Crop Report", "source": "ABARES", "coverage": "1998 onward",
     "frequency": "quarterly (Mar, Jun, Sep, Dec)", "publication_lag_days": 0.0,
     "revisions": "each issue revises the last", "licence": "free, public",
     "history_from": "1998-03", "pit_feasible": True, "assets": ("WHEAT", "CORN", "AUDUSD"),
     "fields": ("report_date", "crop", "state", "area_ha", "production_kt", "yield_tha"),
     "pit_fields": ("release_ts_utc", "vintage", "prior_estimate"),
     "mechanism_families": ("supply_shock",),
     "how_to_fetch": "agriculture.gov.au/abares/research-topics/agricultural-commodities"},
    {"name": "Quarterly Superannuation Performance Statistics", "source": "APRA",
     "coverage": "2004 onward", "frequency": "quarterly", "publication_lag_days": 60.0,
     "revisions": "back series RESTATED when reporting standards change -- a silent break",
     "licence": "free, public", "history_from": "2004-06", "pit_feasible": True,
     "assets": ("AUDUSD", "EURAUD"),
     "fields": ("quarter", "total_assets", "international_assets", "cash", "fixed_income",
                "net_flows"),
     "pit_fields": ("publish_ts_utc", "vintage", "reporting_standard_version"),
     "mechanism_families": ("institutional_flow",),
     "how_to_fetch": "apra.gov.au quarterly superannuation statistics XLSX"},
    {"name": "AOFM tender results", "source": "AOFM", "coverage": "2000 onward",
     "frequency": "weekly", "publication_lag_days": 0.0, "revisions": "final",
     "licence": "free, public", "history_from": "2000-01", "pit_feasible": True,
     "assets": ("AUDUSD", "UST10Y"),
     "fields": ("tender_date", "line", "maturity", "amount_offered", "amount_allotted",
                "coverage_ratio", "weighted_average_yield"),
     "pit_fields": ("result_ts_utc", "announcement_ts_utc"),
     "mechanism_families": ("institutional_flow", "supply_shock"),
     "how_to_fetch": "aofm.gov.au/auction-results -- the announcement is the preceding Friday"},
    {"name": "ASX 24 expiry and settlement calendar", "source": "ASX", "coverage": "2000 onward",
     "frequency": "annual calendar", "publication_lag_days": 0.0,
     "revisions": "rare, announced", "licence": "free, public", "history_from": "2000-01",
     "pit_feasible": True, "assets": ("AUS200",),
     "fields": ("contract", "expiry_date", "settlement_method", "last_trading_time"),
     "pit_fields": ("published_ts_utc",), "mechanism_families": ("derivatives_expiry",),
     "how_to_fetch": "asx.com.au derivatives calendars; also computable as the third Thursday"},
    {"name": "S&P/ASX index rebalance announcements", "source": "S&P Dow Jones Indices",
     "coverage": "2000 onward", "frequency": "quarterly plus ad hoc",
     "publication_lag_days": 0.0, "revisions": "amended by later announcement",
     "licence": "free headline", "history_from": "2000-03", "pit_feasible": True,
     "assets": ("AUS200",),
     "fields": ("announcement_date", "effective_date", "index", "additions", "deletions",
                "float_changes"),
     "pit_fields": ("announcement_ts_utc", "effective_date"),
     "mechanism_families": ("index_flow",),
     "how_to_fetch": "spglobal.com/spdji index announcements; keep BOTH dates"},
    {"name": "ASX dividends and S&P/ASX 200 dividend points", "source": "ASX and S&P DJI",
     "coverage": "2000 onward", "frequency": "continuous", "publication_lag_days": 0.0,
     "revisions": "amended by announcement", "licence": "free, public",
     "history_from": "2000-01", "pit_feasible": True, "assets": ("AUS200", "AUDUSD"),
     "fields": ("security", "ex_date", "pay_date", "amount", "franked_pct", "index_points"),
     "pit_fields": ("announcement_ts_utc", "ex_date"),
     "mechanism_families": ("corporate_flow",),
     "how_to_fetch": "ASX announcements at the single-name level (EVENT lane); the aggregated "
                     "index dividend-point series is the hypothesis-lane object"},
    {"name": "NBS and Caixin manufacturing PMI", "source": "NBS; S&P Global/Caixin",
     "coverage": "2005 onward", "frequency": "monthly", "publication_lag_days": 0.0,
     "revisions": "not revised", "licence": "free headline", "history_from": "2005-01",
     "pit_feasible": True, "assets": ("AUDUSD", "AUS200", "USDCNH"),
     "fields": ("reference_month", "nbs_mfg", "nbs_nonmfg", "caixin_mfg", "new_export_orders"),
     "pit_fields": ("release_ts_utc", "consensus_at_release"),
     "mechanism_families": ("event_reaction", "macro_condition"),
     "how_to_fetch": "stats.gov.cn at 01:30 UTC month-end; pmi.spglobal.com at 01:45 UTC"},
    {"name": "China customs monthly commodity imports", "source": "GACC",
     "coverage": "2005 onward", "frequency": "monthly", "publication_lag_days": 15.0,
     "revisions": "revised; the combined Jan-Feb print BREAKS any naive monthly series",
     "licence": "free headline", "history_from": "2005-01", "pit_feasible": True,
     "assets": ("AUDUSD", "AUS200", "XCUUSD"),
     "fields": ("reference_month", "commodity", "tonnes", "value_usd", "origin"),
     "pit_fields": ("release_ts_utc", "vintage"),
     "mechanism_families": ("terms_of_trade",),
     "how_to_fetch": "customs.gov.cn monthly statistics"},
    {"name": "FFAJ retail FX margin statistics", "source": "Financial Futures Association of Japan",
     "coverage": "2010 onward", "frequency": "monthly", "publication_lag_days": 20.0,
     "revisions": "not revised", "licence": "free, public", "history_from": "2010-01",
     "pit_feasible": True, "assets": ("AUDJPY", "NZDJPY"),
     "fields": ("month", "pair", "long_positions", "short_positions", "turnover"),
     "pit_fields": ("publish_ts_utc",), "mechanism_families": ("positioning", "carry_funding"),
     "how_to_fetch": "ffaj.or.jp statistics pages"},
    {"name": "Desk MT5 bars (H1, M15, D1) and tick tape", "source": "the desk's own Fusion tape",
     "coverage": "2018 onward for FX majors; AUS200 from 2018", "frequency": "tick to daily",
     "publication_lag_days": 0.0,
     "revisions": "append-only; a re-pull can restate a bar and the restatement must be recorded",
     "licence": "desk-owned", "history_from": "2018-01", "pit_feasible": True,
     "assets": ("AUDUSD", "AUS200", "AUDJPY", "XAUAUD"),
     "fields": ("time", "open", "high", "low", "close", "tick_volume", "spread"),
     "pit_fields": ("time",), "mechanism_families": ("all",),
     "how_to_fetch": "desks/mt5/data/universe/<SYMBOL>_<TF>.parquet"},
)

# --------------------------------------------------------------------------- the actors
#: Eleven content fields each, after the name: holds, forced_to, when, information, constraints,
#: instruments, counterparties, observables, impact, persistence, falsifier. An actor whose
#: FALSIFIER is empty is a story, and a story is not a research object.
ACTORS: tuple[dict[str, Any], ...] = (
    {
        "name": "Reserve Bank of Australia Monetary Policy Board",
        "holds": "the cash rate target, roughly A$30bn of remunerated exchange settlement "
                 "balances, and a government bond portfolio still running off from the 2020-2022 "
                 "purchase programme",
        "forced_to": ("decide at eight pre-announced meetings a year and publish the decision "
                      "and its reasoning the same afternoon -- it cannot decline to decide",
                      "publish a quarterly forecast table whose revisions are on the record",
                      "release minutes about two weeks later, naming the options considered"),
        "when": "14:30 Sydney on the second day of each two-day meeting: 04:30 UTC under AEST and "
                "03:30 UTC under AEDT, with the press conference one hour later",
        "information": ("the full ABS dataset before the market sees the next print",
                        "liaison with firms through the Bank's business liaison programme",
                        "the payments system it operates", "its own staff forecasts"),
        "constraints": ("the 2-3% inflation target on average over time",
                        "the Statement on the Conduct of Monetary Policy agreed with the "
                        "Treasurer",
                        "a predominantly VARIABLE-rate A$2.4trn mortgage book, which makes "
                        "transmission fast and politically visible",
                        "the RBA Review governance changes that cut meetings from eleven to eight"),
        "instruments": ("AUDUSD", "AUDNZD", "AUDJPY", "AUS200", "EURAUD"),
        "counterparties": ("the banks holding exchange settlement balances",
                           "the Commonwealth, for which it acts as banker",
                           "other central banks through swap lines"),
        "observables": ("the media release at the announcement minute",
                        "the IB future's implied cash rate immediately before and after",
                        "the SoMP forecast table and its revision",
                        "the minutes' dissent and options language"),
        "impact": "reprices the whole AUD short-rate path in seconds; the currency move is "
                  "proportional to the SURPRISE against the IB curve, not to the decision, which "
                  "is why a study using the decision alone finds almost nothing",
        "persistence": "the level effect is permanent until the next meeting; the excess move "
                       "decays over minutes to hours, and the decay rate itself changed when "
                       "meetings went from eleven to eight a year because each one now carries "
                       "more information",
        "falsifier": "the same event-window statistic on the eight nearest NON-meeting Tuesdays. "
                     "A move that survives there is a Tuesday effect wearing a central bank's hat",
        "notes": "the 2024 meeting-count change is a structural break in the event sample: 2023 "
                 "and 2025 meetings are not exchangeable observations",
    },
    {
        "name": "Australian superannuation funds and their currency overlay managers",
        "holds": "about A$4.1trn in total, roughly half in international assets, with declared "
                 "hedge ratios typically 0-40% on offshore equity and 70-100% on offshore debt",
        "forced_to": ("return to the strategic asset allocation and to the declared hedge ratio "
                      "when drift breaches the band -- a breach is a governance failure, not a "
                      "view",
                      "BUY foreign currency (sell AUD) after an offshore equity rally, because "
                      "the hedged sleeve's short-foreign-currency leg is then under-covered",
                      "SELL foreign currency (buy AUD) after an offshore drawdown, the same "
                      "mechanism with the sign reversed"),
        "when": "month-end and quarter-end, concentrated in the last three business days and in "
                "the WMR 16:00 London fix; 30 June is the fiscal year end and the largest of all",
        "information": ("their own daily unit pricing and drift against the SAA",
                        "custodian FX exposure reports",
                        "the offshore equity return they are re-covering against"),
        "constraints": ("the SIS Act duty and APRA Prudential Standard SPS 530 on investment "
                        "governance",
                        "each fund's published investment governance framework and rebalancing "
                        "band",
                        "the Your Future Your Super performance test, which penalises tracking "
                        "error against a benchmark with a fixed hedge assumption"),
        "instruments": ("AUDUSD", "EURAUD", "AUDJPY", "US500"),
        "counterparties": ("custodian banks running the overlay",
                           "interbank FX dealers at the London fix",
                           "the funds' own internal trading desks, increasingly"),
        "observables": ("APRA quarterly superannuation statistics for the asset totals",
                        "the offshore equity return over the month, which SIGNS the flow",
                        "AUDUSD behaviour in the 15:00-16:00 UTC fix window at month end"),
        "impact": "a directional, price-insensitive AUD flow in the last three business days "
                  "whose sign is set by the offshore equity return; the magnitude scales with the "
                  "size of that return and with the hedged share of the offshore book",
        "persistence": "structural and growing -- the super pool compounds at roughly the "
                       "contribution rate -- but the SIGN is conditional every month, so the "
                       "unconditional effect has no persistence at all and looks like noise",
        "falsifier": "the same conditional test in months where the offshore equity return was "
                     "within +/-0.5%. With no drift there is nothing to re-cover, so a flow that "
                     "still appears there was never the hedge rebalance",
        "notes": "this is the actor most often mis-modelled as a generic 'month-end effect'; the "
                 "conditioning variable is the whole mechanism",
    },
    {
        "name": "Pilbara iron-ore exporters (BHP, Rio Tinto, Fortescue, Roy Hill)",
        "holds": "the world's lowest-cost seaborne iron-ore supply, shipping roughly 830-870 Mt a "
                 "year through Port Hedland, Dampier and Cape Lambert",
        "forced_to": ("convert USD sales receipts into AUD for wages, royalties, company tax and "
                      "franked dividends, on a fixed obligations calendar rather than a view",
                      "pay WA royalties at 7.5% ad valorem on the FOB value of fine ore",
                      "ship to contracted lifting schedules regardless of the spot price"),
        "when": "monthly royalty and shipment cycles; quarterly production reports mid-January, "
                "April, July and October; dividends paid in late February-March and August-October",
        "information": ("their own forward lifting schedules and customer nominations",
                        "port queue and vessel line-up data before it is published",
                        "Chinese mill inventory levels through their own marketing arms"),
        "constraints": ("USD-denominated contracts against AUD-denominated costs",
                        "the WA Mining Act royalty regime",
                        "Corporations Act dividend declaration and continuous disclosure",
                        "rail and port capacity, which is fixed in the short run"),
        "instruments": ("AUDUSD", "AUS200", "AUDJPY", "XCUUSD"),
        "counterparties": ("Chinese steel mills and state trading houses",
                           "Japanese and Korean mills on long-term contracts",
                           "the WA state government as royalty recipient"),
        "observables": ("Pilbara Ports monthly throughput",
                        "quarterly production reports",
                        "the WA budget royalty line and its iron-ore price assumption",
                        "ABS international trade in goods, metal ores line"),
        "impact": "a persistent structural AUD bid that scales with USD ore price times tonnes; "
                  "it is the single largest identifiable commercial FX flow in the country",
        "persistence": "decades, and the most stable actor in this pack; what varies is the "
                       "MAGNITUDE, which is why AU-C separates price from volume rather than "
                       "treating the pair as one variable",
        "falsifier": "the same statistic on Brazilian shipment months out of Ponta da Madeira. A "
                     "tonnage effect that appears there too is an ore PRICE effect, not an "
                     "Australian export-conversion effect",
        "notes": "the single names here are ACTORS only; no share CFD appears in any instrument "
                 "tuple in this pack",
    },
    {
        "name": "Government of Western Australia (Department of Treasury)",
        "holds": "a budget built on a published iron-ore price assumption, and royalty receipts "
                 "of the order of A$8-11bn per financial year",
        "forced_to": ("publish a price assumption and revise it on a fixed calendar when the "
                      "market moves away from it",
                      "book royalty revenue as a legislated percentage of FOB value, with no "
                      "discretion over the rate"),
        "when": "the state budget in May, the mid-year review in December, quarterly financial "
                "results in between",
        "information": ("actual royalty receipts before anyone else sees them",
                        "company-level production forecasts provided confidentially"),
        "constraints": ("the Mining Act 1978 royalty schedule",
                        "the Government Financial Responsibility Act reporting requirements",
                        "GST relativity, which claws back part of any royalty windfall"),
        "instruments": ("AUDUSD", "AUS200"),
        "counterparties": ("the Commonwealth, through GST distribution and company tax",
                           "the iron-ore producers as royalty payers"),
        "observables": ("the iron-ore price assumption in the WA budget papers",
                        "the Commonwealth's own, different assumption in the Budget and MYEFO",
                        "published royalty receipts against forecast"),
        "impact": "no direct FX flow; the published assumption is the cleanest DATED record of the "
                  "terms-of-trade expectation embedded in Australian fiscal policy, and the gap "
                  "between assumption and spot is a measurable fiscal surprise",
        "persistence": "the assumption is deliberately conservative and has been wrong in the "
                       "same direction for most of the last decade, which is itself a stable and "
                       "exploitable bias in the fiscal forecast",
        "falsifier": "compare the WA revision against the Commonwealth's independent assumption. "
                     "A common surprise is the ore price; a divergence is fiscal politics and "
                     "carries no market information",
        "notes": "roughly A$85-95m of WA royalty per US$1/t on the annual average price",
    },
    {
        "name": "Australian Office of Financial Management (AOFM)",
        "holds": "responsibility for roughly A$900bn-1.0trn of Australian Government Securities "
                 "on issue, across nominals, indexed bonds and Treasury notes",
        "forced_to": ("fund the Commonwealth's published borrowing task through a pre-announced "
                      "tender programme; the calendar is committed before each auction",
                      "issue into whatever conditions exist on the announced day"),
        "when": "weekly tenders, most commonly Thursday, announced the preceding Friday; "
                "syndications announced several days ahead",
        "information": ("the Commonwealth's cash position",
                        "dealer-panel indications of demand before the tender"),
        "constraints": ("the Commonwealth Inscribed Stock Act",
                        "the annual Issuance Programme statement, which is a public commitment",
                        "a maturity profile it must keep smooth"),
        "instruments": ("AUDUSD", "UST10Y", "AUDJPY"),
        "counterparties": ("the AOFM dealer panel",
                           "offshore reserve managers and index funds, who are roughly half the "
                           "AGS holder base"),
        "observables": ("tender results: coverage ratio, weighted average yield, allotment",
                        "the AGS-UST 10-year spread",
                        "the published issuance calendar"),
        "impact": "creates dated AUD duration supply; offshore participation is a dated AUD "
                  "demand, and the hedged pickup over Treasuries is what moves it",
        "persistence": "structural; the offshore share of AGS has ranged roughly 45-75% over the "
                       "last fifteen years and that share is itself a slow-moving regime variable",
        "falsifier": "the same statistic on New Zealand Debt Management tender days. A coverage "
                     "effect present in both is a global duration bid, not an Australian funding "
                     "fact",
        "notes": "",
    },
    {
        "name": "Australian major-bank offshore wholesale funding desks",
        "holds": "of the order of A$80-120bn of offshore term issuance a year across the four "
                 "majors, swapped back into AUD",
        "forced_to": ("swap foreign-currency issuance back to AUD, because the regulatory "
                      "requirement the issue satisfies is an AUD liquidity requirement",
                      "term out funding to meet the Net Stable Funding Ratio, whatever the basis "
                      "costs on the day"),
        "when": "clustered in January and after the half-year results blackouts end in "
                "February-March and August-September",
        "information": ("their own funding plans and deposit growth",
                        "investor reverse enquiry before a deal is announced"),
        "constraints": ("APRA APS 210 liquidity and APS 117 interest-rate risk standards",
                        "the Banking Act 1959",
                        "rating-agency expectations on funding composition"),
        "instruments": ("AUDUSD", "AUDJPY", "EURAUD"),
        "counterparties": ("offshore bond investors",
                           "cross-currency basis swap dealers",
                           "domestic real-money buyers of the swapped AUD leg"),
        "observables": ("the AUD/USD 3- and 5-year cross-currency basis",
                        "APRA monthly ADI statistics",
                        "each bank's pillar 3 and funding disclosures"),
        "impact": "compresses the AUD cross-currency basis when issuance is heavy and widens it "
                  "when it stops; the basis is the price of the hedge, not of the currency, which "
                  "is why a basis move need not move spot at all",
        "persistence": "seasonal within the year and structural across it; the level of the basis "
                       "shifted permanently after the post-GFC regulatory regime landed",
        "falsifier": "the same basis statistic in months with NO offshore benchmark issuance. A "
                     "compression that persists there is a global dollar-funding condition and "
                     "has nothing to do with Australian banks",
        "notes": "",
    },
    {
        "name": "Index funds and ETFs tracking the S&P/ASX 200 and ASX 300",
        "holds": "of the order of A$180-220bn tracking Australian large-cap benchmarks",
        "forced_to": ("buy additions and sell deletions at the reference price on the effective "
                      "date, which is the closing single-price auction",
                      "match float and share-count revisions exactly, however small",
                      "never express a view on price: the flow is size-determined"),
        "when": "quarterly, effective after the close of the third FRIDAY of March, June, "
                "September and December, executed in the 16:10-16:12 Sydney auction",
        "information": ("the S&P DJI announcement about two weeks ahead, which everyone has",
                        "their own tracking error against the index"),
        "constraints": ("each fund's PDS and the S&P DJI Australian index methodology",
                        "tracking-error budgets that make deviation from the auction expensive"),
        "instruments": ("AUS200",),
        "counterparties": ("index arbitrageurs who front-run the announcement",
                           "the liquidity providers who supply the other side of the auction"),
        "observables": ("S&P DJI index announcements with BOTH announcement and effective dates",
                        "ASX closing auction volume",
                        "the close-versus-VWAP gap on effective dates"),
        "impact": "a concentrated, price-insensitive auction imbalance on four days a year; the "
                  "predictable part is arbitraged away between announcement and effective date, "
                  "so the residual is in the auction itself",
        "persistence": "the ANNOUNCEMENT effect has decayed as passive share grew and arbitrage "
                       "capital arrived; the AUCTION effect is mechanical and has not",
        "falsifier": "the same close-versus-VWAP statistic on the eleven non-rebalance quarterly "
                     "Fridays. An effect present there is auction microstructure, not index flow",
        "notes": "the rebalance FRIDAY and the SPI expiry THURSDAY are different days; AU-G tests "
                 "them separately for exactly this reason",
    },
    {
        "name": "CFTC-reportable leveraged funds in CME Australian dollar futures (6A)",
        "holds": "typically 40k-130k contracts of gross non-commercial open interest at A$100,000 "
                 "notional each",
        "forced_to": ("report the position on a fixed weekly clock whatever it is",
                      "liquidate at the clearing house's margin call when an adverse move "
                      "exhausts variation margin -- the only genuine forcing in this row"),
        "when": "positions as of Tuesday close, published Friday 15:30 America/New_York",
        "information": ("their own flow and their prime brokers' balances",
                        "the same public macro everyone else has"),
        "constraints": ("CME margin requirements",
                        "CFTC large-trader reporting",
                        "fund-level risk limits and drawdown stops"),
        "instruments": ("AUDUSD", "AUDJPY", "AUDNZD"),
        "counterparties": ("commercial hedgers on the other side of the COT",
                           "dealer banks warehousing the risk"),
        "observables": ("the COT disaggregated report, contract 232741",
                        "CME daily volume and open interest",
                        "the net position percentile against its own three-year history"),
        "impact": "a crowded extreme is not a signal about value, it is a statement about who "
                  "must sell if the market moves against them; the asymmetry it creates is the "
                  "mechanism, not the level",
        "persistence": "positioning extremes mean-revert over weeks; the SPEED of reversion is "
                       "faster after 2015 as the participant mix shifted toward faster funds",
        "falsifier": "the identical percentile rule with the Tuesday position aligned to the "
                     "FRIDAY bar instead of the following Monday. An effect that survives only "
                     "under that alignment is a point-in-time bug, not positioning",
        "notes": "the three-day staleness is the single commonest error in COT research",
    },
    {
        "name": "Chinese steel mills and state commodity buyers",
        "holds": "roughly 1.0-1.1bn tonnes of annual crude steel capacity and the port inventory "
                 "that feeds it; they take about 65-70% of Australia's iron-ore exports",
        "forced_to": ("buy ore and coking coal on a production schedule set by blast-furnace "
                      "utilisation and by a state output plan, not by price",
                      "restock to administrative port-inventory targets"),
        "when": "continuous purchasing, with the information arriving monthly: customs data "
                "around the 7th-20th, NBS PMI at 01:30 UTC on the last day of the month, Caixin "
                "at 01:45 UTC on the first business day",
        "information": ("their own order books and mill margins",
                        "provincial production quota guidance before it is public"),
        "constraints": ("annual crude steel output guidance and provincial production controls",
                        "environmental curtailment orders, which arrive with little notice",
                        "steel margin, which is the real short-run constraint on ore demand"),
        "instruments": ("AUDUSD", "AUS200", "USDCNH", "CHINAH", "HK50"),
        "counterparties": ("the Pilbara exporters", "Brazilian and West African supply",
                           "domestic Chinese scrap and ore"),
        "observables": ("NBS and Caixin PMI headlines and new-export-orders subindex",
                        "China customs iron-ore and coal import tonnage",
                        "port inventory series"),
        "impact": "the demand side of the terms-of-trade channel; a PMI surprise moves AUD within "
                  "minutes because the AUD is the most liquid China proxy open at that minute",
        "persistence": "the PMI reaction has been stable for a decade; the LEVEL relationship "
                       "between Chinese steel output and Australian tonnage weakened as Chinese "
                       "steel output plateaued after 2020",
        "falsifier": "the same PMI-window statistic on EURUSD and USDCAD. A move present in every "
                     "dollar pair is a dollar event wearing a Chinese hat, and the AUD-minus-NZD "
                     "residual is the part that is genuinely about ore",
        "notes": "",
    },
    {
        "name": "Australian LNG exporters (North West Shelf, Gorgon, Wheatstone, APLNG, Ichthys)",
        "holds": "roughly 80-82 Mt a year of LNG export capacity, most of it sold under long-term "
                 "contracts priced at 11-15% of a LAGGED crude average",
        "forced_to": ("deliver contracted cargoes on schedule",
                      "convert part of USD revenue to AUD for domestic costs and the Petroleum "
                      "Resource Rent Tax",
                      "accept a revenue determined by a PAST oil price, not today's gas market"),
        "when": "continuous shipment; the revenue signal is Brent lagged roughly one quarter, and "
                "the PRRT and tax obligations fall on the Australian fiscal calendar",
        "information": ("their own cargo schedules and contract slopes",
                        "buyer nomination flexibility"),
        "constraints": ("the contract slopes themselves, which are public in outline",
                        "the Australian Domestic Gas Security Mechanism",
                        "PRRT and company tax obligations in AUD"),
        "instruments": ("XBRUSD", "XNGUSD", "AUDUSD", "AUS200"),
        "counterparties": ("Japanese, Korean, Chinese and Taiwanese utilities",
                           "spot buyers in the JKM market for uncontracted volume"),
        "observables": ("ABARES Resources and Energy Quarterly export values",
                        "Gladstone Ports monthly LNG throughput",
                        "ABS international trade, LNG line"),
        "impact": "an AUD flow that follows Brent with about a quarter's lag; an unlagged "
                  "Brent-to-AUD regression is measuring risk appetite, not the LNG channel",
        "persistence": "the lag structure is contractual and therefore extremely stable; it will "
                       "weaken only as contracts reprice toward hub indexation at renewal",
        "falsifier": "the same lag structure applied to US Henry Hub-linked LNG contracts. An "
                     "Australian lag that also appears there is a global LNG fact and not a "
                     "contract-structure fact about Australia",
        "notes": "",
    },
    {
        "name": "Australian grain exporters and bulk handlers (CBH Group, GrainCorp)",
        "holds": "a 25-40 Mt wheat crop of which roughly two-thirds is exported, plus canola, "
                 "barley and pulses; Australia is typically a top-five wheat exporter and the "
                 "swing supplier into Asia",
        "forced_to": ("clear the crop within a season, because storage is finite and the next "
                      "harvest arrives on a biological calendar",
                      "sell AUD-denominated grain for USD and hedge the receipt forward",
                      "book shipping slots ahead of knowing the price"),
        "when": "harvest October-January, export programme December-April; ABARES crop reports in "
                "March, June, September and December",
        "information": ("their own receival and stock positions before ABARES publishes",
                        "grower delivery intentions"),
        "constraints": ("the Port Terminal Access code",
                        "co-operative delivery obligations to growers",
                        "vessel availability and port capacity"),
        "instruments": ("WHEAT", "CORN", "AUDUSD"),
        "counterparties": ("Asian and Middle Eastern millers and state buyers",
                           "international grain trading houses"),
        "observables": ("ABARES Australian Crop Report production estimate and its REVISION",
                        "ABS export volumes",
                        "the Australian-to-Chicago wheat spread"),
        "impact": "a seasonal AUD demand from hedged USD receipts, and a supply shock into the "
                  "world wheat balance when the Australian crop misses",
        "persistence": "the seasonal is biological and permanent; the SIZE is rainfall-dependent "
                       "and varies by a factor of two between drought and normal years",
        "falsifier": "the same seasonal statistic on the northern-hemisphere harvest months of "
                     "June-August. A December effect that also appears in July is a grain-market "
                     "seasonal, not an Australian one",
        "notes": "the desk holds CHICAGO wheat; the Australian FOB basis is a transmission target, "
                 "and treating WHEAT as an Australian series is the error AU-M guards against",
    },
    {
        "name": "Australian Bureau of Statistics",
        "holds": "a monopoly on the official Australian macro dataset and a pre-announced, "
                 "embargoed release calendar",
        "forced_to": ("publish on the announced date at the announced minute, to the whole market "
                      "simultaneously",
                      "revise seasonally adjusted series when factors are re-estimated, whether "
                      "or not that breaks somebody's backtest"),
        "when": "11:30 Sydney: 01:30 UTC under AEST and 00:30 UTC under AEDT. Labour force is "
                "typically the third Thursday; quarterly CPI lands in late January, April, July "
                "and October",
        "information": ("the number before anyone else, under embargo",
                        "the full microdata behind it"),
        "constraints": ("the Census and Statistics Act 1905",
                        "the published release calendar and the embargo policy",
                        "statistical methodology it cannot change mid-series without announcing"),
        "instruments": ("AUDUSD", "AUS200", "AUDNZD", "AUDJPY", "EURAUD"),
        "counterparties": ("every market participant at once, by design"),
        "observables": ("the release itself",
                        "the IB curve's repricing across the print, which RANKS the releases by "
                        "how much they actually matter"),
        "impact": "creates the dated information events the AUD reprices on; the labour force and "
                  "the quarterly trimmed mean are the only two that reliably move the IB curve by "
                  "more than a basis point",
        "persistence": "permanent as a class; the RANKING within the class shifts with the "
                       "policy regime -- labour force dominated in 2021-2022 and CPI in "
                       "2022-2024, and a pooled study averages two different reaction functions",
        "falsifier": "the same 01:30 UTC window on days with NO scheduled ABS release. A "
                     "systematic move there is the Tokyo-to-Sydney liquidity handover, not data",
        "notes": "the AEST/AEDT switch moves the release minute in UTC twice a year",
    },
    {
        "name": "The RBA's foreign exchange operations desk (agency business)",
        "holds": "reserve assets of the order of A$80-95bn plus the Commonwealth's FX payment "
                 "obligations",
        "forced_to": ("transact FX as banker to the Commonwealth, on the government's payment "
                      "schedule rather than on a view",
                      "publish the monthly net transaction figures afterwards"),
        "when": "daily execution, published monthly in the Bank's statistical tables",
        "information": ("the Commonwealth's FX payment pipeline",
                        "interbank flow it sees as a settlement participant"),
        "constraints": ("Reserve Bank Act 1959 Part IV",
                        "the Bank's published statement on foreign exchange market operations, "
                        "which commits it to smoothing rather than targeting"),
        "instruments": ("AUDUSD",),
        "counterparties": ("the Commonwealth", "interbank FX dealers", "other central banks"),
        "observables": ("the daily foreign exchange market intervention transactions table",
                        "the monthly net agency transaction figure"),
        "impact": "small and largely offsetting in normal conditions; the value of this actor is "
                  "that its flow is PUBLISHED, so it is one of the few places where a claimed "
                  "flow effect can be checked against the actor's own ledger",
        "persistence": "the agency business is permanent; discretionary intervention has been "
                       "rare since 2008 and each episode must be treated as its own regime",
        "falsifier": "the same statistic in months where the published net transaction is within "
                     "+/-A$100m. No flow, so no effect -- or the effect was never the flow",
        "notes": "",
    },
    {
        "name": "Retail and systematic carry participants in AUDJPY",
        "holds": "long AUDJPY carry positions, funded in yen; Japanese margin-trading aggregates "
                 "are published monthly by the FFAJ",
        "forced_to": ("liquidate at the broker's maintenance margin level when the pair falls, "
                      "regardless of their view of the carry",
                      "pay or receive the swap at the daily rollover, with the triple charge on "
                      "Wednesday"),
        "when": "continuous, concentrated in the Tokyo morning (23:00-02:00 UTC) and around both "
                "central banks' decision days",
        "information": ("nothing the market does not have; this actor is forced, not informed"),
        "constraints": ("ASIC's CFD product intervention order capping Australian retail leverage "
                        "at 30:1 on major FX",
                        "Japanese FSA leverage caps on the other side of the pair",
                        "broker maintenance margin, which is the binding one in a fast move"),
        "instruments": ("AUDJPY", "NZDJPY", "AUDCHF", "AUDUSD", "AUS200"),
        "counterparties": ("retail brokers warehousing or hedging the flow",
                           "the dealer banks they hedge into"),
        "observables": ("FFAJ monthly FX margin statistics",
                        "the AUDJPY-to-US500 rolling beta as the risk-state proxy",
                        "realised downside versus upside semivariance"),
        "impact": "one-sided in stress: carry positions are long, so a risk shock forces SELLING "
                  "into a falling market. That is why AUDJPY's downside is faster than its upside "
                  "and why variance is the wrong statistic for it",
        "persistence": "the asymmetry appears in every risk-off episode since at least 2007 and "
                       "scales with the rate differential; it nearly vanished in 2020-2021 when "
                       "the differential was near zero, which is the cleanest era control",
        "falsifier": "the same semivariance ratio on AUDCHF and AUDSGD, carry pairs with a "
                     "different retail base. Shared asymmetry is risk-off in general, not "
                     "Japanese margin in particular",
        "notes": "",
    },
    {
        "name": "Australian resource and bank dividend payers in the franking system",
        "holds": "of the order of A$90-110bn of annual dividends from ASX-listed companies, "
                 "heavily concentrated in the four banks and the large miners",
        "forced_to": ("pay declared dividends on the announced date -- a cash obligation, not a "
                      "decision, once declared",
                      "attach franking credits to the extent of company tax already paid"),
        "when": "two seasons: interim ex-dates and payments from late February to early April, "
                "final ex-dates and payments from late August to early October",
        "information": ("their own earnings and franking account balance before the market"),
        "constraints": ("Income Tax Assessment Act imputation rules",
                        "ASX Listing Rule 3.1 continuous disclosure",
                        "the franking account balance, which caps how much can be franked"),
        "instruments": ("AUS200", "AUDUSD"),
        "counterparties": ("domestic holders, to whom franking credits are worth roughly 30% more",
                           "foreign holders, to whom they are worth nothing and who repatriate"),
        "observables": ("ASX dividend announcements with ex- and pay-dates",
                        "the S&P/ASX 200 dividend-points series",
                        "the gap between price-index and total-return performance"),
        "impact": "the price index drops the dividend mechanically on the ex-date; foreign-holder "
                  "repatriation is a small AUD sale around the pay-date",
        "persistence": "the mechanical drop is permanent and exact; any FLOW effect on top of it "
                       "has to be demonstrated against a total-return control and usually is not",
        "falsifier": "the same seasonal statistic computed on a TOTAL-RETURN reconstruction. An "
                     "effect that vanishes once dividends are added back was never a flow -- it "
                     "was the price index dropping the coupon",
        "notes": "the single commonest false discovery in Australian index seasonality",
    },
)

# --------------------------------------------------------------------------- the domains
DOMAINS: tuple[dict[str, Any], ...] = (
    {
        "id": "AU-A", "title": "Cash rate decisions against the traded consensus",
        "objects": ("the eight scheduled decisions a year at 04:30/03:30 UTC",
                    "the IB-implied cash rate in the minutes before the announcement",
                    "the statement's forward-guidance sentence",
                    "the 15:30 Sydney press conference, a second event an hour later",
                    "the two unscheduled March 2020 decisions, which are their own class"),
        "conditions": ("the surprise in BASIS POINTS against the IB curve, never against a survey",
                       "the policy era, because the meeting count changed in 2024",
                       "whether forward guidance changed as well as the rate",
                       "whether the meeting fell in a week with a CPI or labour-force print"),
        "instruments": ("AUDUSD", "AUDNZD", "AUDJPY", "AUS200", "EURAUD"),
        "controls": ("the same window on the eight nearest NON-meeting Tuesdays, separating the "
                     "event from the weekday",
                     "the same window on EURUSD, which has no RBA exposure",
                     "the same window on RBNZ decision days, separating 'a central bank decided' "
                     "from 'the RBA decided'",
                     "a placebo surprise drawn from the IB curve's own daily noise distribution"),
        "notes": "the press conference is a separate information event and is routinely folded "
                 "into the decision window, which blends two reactions into one estimate",
    },
    {
        "id": "AU-B", "title": "The SoMP and the minutes as separate information events",
        "objects": ("the quarterly SoMP forecast table and its revision",
                    "the minutes released about two weeks after each meeting",
                    "the semi-annual parliamentary testimony",
                    "the technical assumptions the forecasts are conditioned on"),
        "conditions": ("the SIGN of the trimmed-mean forecast revision",
                       "residualised against the decision-day return, so the two are not "
                       "double-counted",
                       "whether the SoMP accompanies a decision or stands alone"),
        "instruments": ("AUDUSD", "AUS200", "AUDNZD", "UST10Y"),
        "controls": ("the same statistic on the decision day itself, to prove the SoMP adds "
                     "something the decision did not",
                     "the same window on non-SoMP Fridays",
                     "the same window on RBNZ MPS days, separating 'a forecast was revised' from "
                     "'the RBA revised one'",
                     "a placebo built from the Financial Stability Review, which carries no "
                     "forecast revision"),
        "notes": "the minutes are 14 days stale and therefore assumed to be priced; they are not "
                 "stale to a change in the OPTIONS CONSIDERED, which is new information",
    },
    {
        "id": "AU-C", "title": "The terms-of-trade channel: bulk export prices and volumes",
        "objects": ("the iron-ore price", "Newcastle thermal coal",
                    "premium hard coking coal", "JKM LNG and the lagged oil linkage",
                    "Port Hedland and Newcastle monthly tonnage",
                    "the ABS terms-of-trade series"),
        "conditions": ("price and VOLUME entered separately -- the whole question is which one "
                       "carries the information",
                       "conditioned on USDX so a dollar move is not read as a terms-of-trade move",
                       "the three-month lag on the oil-linked LNG component and no lag on ore",
                       "the policy era, because the 2021 coal export ban to China re-routed trade"),
        "instruments": ("AUDUSD", "AUS200", "XBRUSD", "XNGUSD", "USDX", "AUDCAD"),
        "controls": ("the same regression on AUDCAD, which nets two commodity currencies: what "
                     "survives there is Australia-specific and what vanishes is 'commodity FX'",
                     "the same regression with XBRUSD alone, an energy-exporter control",
                     "shuffle the tonnage series within calendar month, killing the seasonal and "
                     "keeping the level",
                     "the same statistic on NZDUSD, which shares China exposure but not ore"),
        "notes": "the ore price is not quoted here; it is an INPUT and every cell must terminate "
                 "in AUDUSD, AUS200 or a cross",
    },
    {
        "id": "AU-D", "title": "China transmission: PMI, imports and the credit impulse",
        "objects": ("NBS manufacturing PMI, month end, 01:30 UTC",
                    "Caixin manufacturing PMI, first business day, 01:45 UTC",
                    "monthly China customs iron-ore and coal import tonnage",
                    "the total social financing credit impulse"),
        "conditions": ("surprise against published consensus where it exists and against a "
                       "six-month random walk where it does not",
                       "whether USDCNH moved in the same window",
                       "whether the print landed before or after the 00:00 UTC ASX cash open",
                       "the Chinese policy era: the 2021 property retrenchment changed the map "
                       "from PMI to ore demand"),
        "instruments": ("AUDUSD", "AUS200", "USDCNH", "CHINAH", "HK50", "NZDUSD", "XCUUSD"),
        "controls": ("the same window on EURUSD and USDCAD -- a move in every dollar pair is a "
                     "dollar event",
                     "the AUD-minus-NZD residual, which isolates the ore-specific part from the "
                     "shared China-demand part",
                     "the same UTC minute on non-PMI days",
                     "the same statistic on XCUUSD, a China-demand instrument with no Australian "
                     "export concentration"),
        "notes": "this is the domain where a dollar factor most easily masquerades as a China "
                 "factor, because both print inside the Asian session",
    },
    {
        "id": "AU-E", "title": "AUD/NZD as a relative-policy instrument",
        "objects": ("the ASX IB-implied RBA path", "the NZ OIS-implied RBNZ path",
                    "the two non-overlapping decision calendars",
                    "the ore-versus-dairy relative export price"),
        "conditions": ("each country's OWN market-implied path, never a survey",
                       "whether the two banks met in the same fortnight",
                       "the dairy-versus-ore relative price, separating policy from terms of "
                       "trade",
                       "excluding 2020-2021, when both curves were pinned and there is no "
                       "dispersion to measure"),
        "instruments": ("AUDNZD", "AUDUSD", "NZDUSD", "AUDJPY", "NZDJPY"),
        "controls": ("the same statistic on EURGBP-style G10 relative-policy pairs: a mechanism "
                     "that works everywhere is a relative-rates fact, not an Oceania one",
                     "randomise which leg is labelled AU and re-run",
                     "the 2020-2021 pinned-floor window as a vacuity check -- a result there is "
                     "an artefact by construction",
                     "the same test using survey consensus instead of the traded curves, which "
                     "should be WEAKER if the traded curve is the right conditioner"),
        "notes": "AUDNZD strips the dollar out of both legs, which is exactly why it is the "
                 "cleanest relative-policy expression the desk can execute",
    },
    {
        "id": "AU-F", "title": "AUD/JPY carry, margin and the asymmetry of unwinds",
        "objects": ("the AUD-JPY policy rate differential",
                    "FFAJ margin aggregates",
                    "AUDJPY realised downside and upside semivariance",
                    "the AUDJPY-to-US500 rolling beta"),
        "conditions": ("semivariance, never variance -- the mechanism is one-sided",
                       "the global risk state, so the asymmetry is not just equity beta",
                       "which of the two central banks moved most recently",
                       "the size of the rate differential, which scales the position"),
        "instruments": ("AUDJPY", "NZDJPY", "AUDCHF", "AUDUSD", "US500", "AUS200"),
        "controls": ("the same ratio on AUDCHF and AUDSGD, carry pairs with a different retail "
                     "base: shared asymmetry is risk-off, not Japanese margin",
                     "the same ratio on USDJPY, which is not a carry pair in the same sense",
                     "2016-2019, when the differential was near zero and the mechanism should be "
                     "absent",
                     "the same ratio on AUS200, to separate an FX unwind from an equity drawdown"),
        "notes": "the Wednesday triple swap is an accounting artefact that will manufacture a "
                 "day-of-week effect in any carry study that does not remove it",
    },
    {
        "id": "AU-G", "title": "ASX microstructure: the auction, SPI expiry and the rebalance",
        "objects": ("the 16:10-16:12 Sydney closing auction with a random end",
                    "SPI 200 expiry on the third THURSDAY of March, June, September and December",
                    "the S&P/ASX quarterly rebalance effective after the third FRIDAY",
                    "the 10:00 Sydney staggered alphabetical open",
                    "the Special Opening Quotation, built from constituent OPENING prices"),
        "conditions": ("close-versus-last-trade and close-versus-VWAP measured separately",
                       "expiry aligned to THURSDAY and rebalance to FRIDAY -- different days",
                       "excluding sessions shortened by a holiday or an early close",
                       "the AEST/AEDT switch, which moves every one of these minutes in UTC"),
        "instruments": ("AUS200",),
        "controls": ("the eleven non-expiry third Thursdays of the year",
                     "the same statistic on JPN225 and HK50 expiry days: a shared effect is "
                     "'index futures expire', not an ASX fact",
                     "the same close-versus-VWAP statistic on ordinary Fridays",
                     "a placebo auction window shifted thirty minutes earlier"),
        "notes": "the random auction end predicts DIFFUSION of flow across the window, not a "
                 "spike at a known second; that is the testable claim and it distinguishes the "
                 "ASX close from the venues most auction literature is written about",
    },
    {
        "id": "AU-H", "title": "Superannuation hedge rebalancing at month and quarter end",
        "objects": ("the last three business days of each month",
                    "quarter ends and the 30 June fiscal year end",
                    "the offshore equity return over the month, which SIGNS the flow",
                    "the WMR 16:00 London fix window"),
        "conditions": ("the sign MUST be conditioned on the offshore equity return; an "
                       "unconditional month-end test is the wrong test and averages to zero",
                       "June separated from the other quarter ends",
                       "the size of the offshore move, which scales the re-cover",
                       "the growth of the super pool over the sample, which scales everything"),
        "instruments": ("AUDUSD", "EURAUD", "AUDJPY", "US500"),
        "controls": ("months where the offshore equity return was within +/-0.5%: no drift, so no "
                     "re-cover, so no flow",
                     "the same conditional test on USDCAD, whose pension system hedges "
                     "differently: a shared effect is global month-end",
                     "the window shifted five business days",
                     "the same test on non-fix hours at month end, isolating the benchmark"),
        "notes": "this is the pack's best example of a mechanism that is invisible unless the "
                 "conditioning variable is right, and the reason AU-H is a domain of its own",
    },
    {
        "id": "AU-I", "title": "The franking and dividend season",
        "objects": ("interim ex-dates from late February to early April",
                    "final ex-dates from late August to early October",
                    "the index dividend-point series",
                    "foreign-holder repatriation around pay-dates"),
        "conditions": ("a PRICE index statistic compared against a TOTAL-RETURN reconstruction",
                       "the franking percentage of the payout",
                       "the AUD leg, to catch repatriation separately from the index drop"),
        "instruments": ("AUS200", "AUDUSD"),
        "controls": ("the total-return reconstruction, which is the primary control and usually "
                     "the whole answer",
                     "the same seasonal on GER40, whose dividend season is a single May-June "
                     "cluster",
                     "non-ex-dates in the same weeks",
                     "a placebo season shifted by one month"),
        "notes": "",
    },
    {
        "id": "AU-J", "title": "The ABS calendar as a ranked set of information events",
        "objects": ("labour force, typically the third Thursday",
                    "quarterly CPI in late January, April, July and October",
                    "the monthly CPI indicator, which partially anticipates the quarterly",
                    "wage price index, retail trade, GDP and the trade balance"),
        "conditions": ("the 11:30 Sydney embargo minute in UTC, which MOVES with AEST/AEDT",
                       "prints ranked by measured IB-curve repricing, not by reputation",
                       "the monthly indicator treated as partially anticipating the quarterly, so "
                       "the residual is the tradeable part",
                       "the policy era, because the ranking changed between 2021 and 2024"),
        "instruments": ("AUDUSD", "AUS200", "AUDNZD", "AUDJPY", "EURAUD"),
        "controls": ("the same UTC window on days with no scheduled release",
                     "the same window on NZ releases at 22:45 UTC, separating 'data landed' from "
                     "'ABS data landed'",
                     "a placebo calendar shifted one week",
                     "the same window on US releases, to remove the global data factor"),
        "notes": "",
    },
    {
        "id": "AU-K", "title": "AGS issuance and offshore demand for AUD duration",
        "objects": ("the weekly tender calendar and the preceding Friday's announcement",
                    "coverage ratio and weighted average yield",
                    "syndication announcements",
                    "the AGS-UST 10-year spread"),
        "conditions": ("announcement and tender tested as two separate events",
                       "whether the spread widened INTO the tender",
                       "nominal bonds, indexed bonds and Treasury notes kept apart",
                       "the offshore holder share, a slow regime variable"),
        "instruments": ("AUDUSD", "UST10Y", "AUDJPY", "AUS200"),
        "controls": ("the same statistic on NZ Debt Management tender days",
                     "weeks with no tender at all",
                     "US Treasury refunding days, removing the global duration bid",
                     "a placebo tender calendar shifted one week"),
        "notes": "",
    },
    {
        "id": "AU-L", "title": "Sydney session mechanics and the daily rollover",
        "objects": ("the 17:00 New York rollover: 21:00 UTC under EST, 22:00 UTC under EDT",
                    "the Sydney open at 22:00 UTC under AEST and 23:00 UTC under AEDT",
                    "the Tokyo handover",
                    "the swap point charged at rollover, tripled on Wednesday"),
        "conditions": ("BOTH hemispheres' DST transitions applied -- Australia and the US switch "
                       "in opposite directions and the misalignment window is several weeks long",
                       "the swap-point jump separated from the price move",
                       "Wednesday rollovers separated from the rest",
                       "the day of the week, because the thinnest hour is not the same every day"),
        "instruments": ("AUDUSD", "AUDJPY", "NZDUSD", "AUDNZD"),
        "controls": ("the same statistic on EURUSD at the same UTC minutes",
                     "Wednesday versus non-Wednesday rollovers",
                     "a placebo rollover minute one hour early",
                     "the same statistic in the weeks when the two hemispheres' DST disagree, "
                     "which is a natural experiment on the clock itself"),
        "notes": "the AUD's day starts in the thinnest liquidity in the G10 cycle; much of what "
                 "is reported as Australian 'overnight' behaviour is this hour",
    },
    {
        "id": "AU-M", "title": "The agricultural export programme",
        "objects": ("the October-January harvest and the December-April export programme",
                    "ABARES crop reports in March, June, September and December",
                    "the production estimate REVISION, which is the tradeable object",
                    "cotton and sugar export seasons"),
        "conditions": ("conditioned on the ABARES revision, not on the calendar alone",
                       "drought years separated from normal years using the published estimate",
                       "the Australian FOB basis treated as a transmission target, not an "
                       "instrument"),
        "instruments": ("WHEAT", "CORN", "SUGAR", "COTTON", "AUDUSD"),
        "controls": ("the northern-hemisphere harvest months of June-August",
                     "the same statistic on CORN, which Australia barely exports",
                     "shuffle years while keeping the calendar, killing the level and keeping the "
                     "seasonal",
                     "the same statistic on SUGAR, whose Australian share is smaller than wheat's"),
        "notes": "",
    },
    {
        "id": "AU-N", "title": "Gold in Australian dollars",
        "objects": ("the XAUAUD quote",
                    "Australian gold production of roughly 290-320 t a year, second in the world",
                    "producer hedge books",
                    "Perth Mint product flows"),
        "conditions": ("the IDENTITY decomposition first, always: reconstruct XAUAUD from XAUUSD "
                       "and AUDUSD and test the RESIDUAL, never the level",
                       "whether gold and the AUD moved in the same direction",
                       "the producer hedging regime, which has changed twice in twenty years"),
        "instruments": ("XAUAUD", "XAUUSD", "AUDUSD", "XAGUSD", "AUS200"),
        "controls": ("the reconstructed cross itself, which is the primary control -- an effect "
                     "that does not survive it is an identity, not a discovery",
                     "the same statistic on XAUEUR, where no comparable producer base exists",
                     "the same statistic on XAGUSD, where the Australian production share is far "
                     "smaller",
                     "the spread and rounding floor: a residual smaller than the quoted spread is "
                     "UNMEASURED, not a finding"),
        "notes": "XAUAUD is the pack's designated trap: every claim of 'Australian gold demand' "
                 "must clear the arithmetic identity before it is a claim about Australia at all",
    },
)

# --------------------------------------------------------------------------- miners
#: DECLARED, NOT WIRED. On this desk "built" is not a status (III.16): a miner is done when it
#: runs on a clock and leaves an artifact. None of these do yet, and `wired=False` says so.
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    {"name": "au_rba_surprise_event_study", "domain_ids": ("AU-A",), "kind": "event",
     "cadence_s": 86400.0, "steerable": False, "wired": False,
     "entry": "countries.au.miners:rba_surprise_event_study",
     "needs": ("CENTRAL_BANK decision dates", "the IB-implied rate at 04:25 UTC",
               "AUDUSD and AUS200 M15 bars"),
     "notes": "refuses a verdict when the pre-announcement IB snapshot is unavailable rather than "
              "treating every meeting as a surprise; runs the non-meeting-Tuesday control first"},
    {"name": "au_somp_revision_residual", "domain_ids": ("AU-B",), "kind": "event",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.au.miners:somp_revision_residual",
     "needs": ("SoMP forecast tables and their priors", "AUDUSD H1 bars"),
     "notes": "residualises against the decision-day return so the SoMP is not credited twice"},
    {"name": "au_terms_of_trade_decomposition", "domain_ids": ("AU-C",), "kind": "macro",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.au.miners:terms_of_trade_decomposition",
     "needs": ("ABS trade goods", "Pilbara throughput", "USDX bars", "AUDUSD D1 bars"),
     "notes": "enters price and volume separately; reports the AUDCAD control alongside"},
    {"name": "au_china_pmi_transmission", "domain_ids": ("AU-D",), "kind": "event",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.au.miners:china_pmi_transmission",
     "needs": ("NBS and Caixin release times", "AUDUSD, NZDUSD, USDCNH M15 bars"),
     "notes": "the AUD-minus-NZD residual is the headline output, not the raw AUD response"},
    {"name": "au_tasman_relative_policy", "domain_ids": ("AU-E",), "kind": "macro",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.au.miners:tasman_relative_policy",
     "needs": ("RBA and RBNZ decision dates", "the two implied paths", "AUDNZD H1 bars"),
     "notes": "excludes 2020-2021 by construction: pinned curves carry no dispersion"},
    {"name": "au_carry_semivariance", "domain_ids": ("AU-F",), "kind": "microstructure",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.au.miners:carry_semivariance",
     "needs": ("AUDJPY, AUDCHF, AUDSGD, US500 M15 bars", "FFAJ margin statistics"),
     "notes": "removes the Wednesday triple swap before measuring anything"},
    {"name": "au_asx_close_and_expiry", "domain_ids": ("AU-G",), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": False, "wired": False,
     "entry": "countries.au.miners:asx_close_and_expiry",
     "needs": ("the third-Thursday and third-Friday calendars", "AUS200 M15 bars"),
     "notes": "tests expiry and rebalance as SEPARATE days; a merged test is refused"},
    {"name": "au_super_hedge_rebalance", "domain_ids": ("AU-H",), "kind": "flow",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.au.miners:super_hedge_rebalance",
     "needs": ("US500 monthly return", "AUDUSD M15 bars around the WMR fix"),
     "notes": "conditions the sign on the offshore return; the unconditional version is refused "
              "because it is known in advance to average the mechanism to zero"},
    {"name": "au_franking_season", "domain_ids": ("AU-I",), "kind": "calendar",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.au.miners:franking_season",
     "needs": ("index dividend points", "AUS200 D1 bars"),
     "notes": "reports the total-return control before the price-index result"},
    {"name": "au_data_calendar_ranking", "domain_ids": ("AU-J",), "kind": "event",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.au.miners:data_calendar_ranking",
     "needs": ("ABS calendar", "the IB curve", "AUDUSD M15 bars"),
     "notes": "ranks prints by measured repricing and publishes the ranking, which is the output"},
    {"name": "au_aofm_tender_footprint", "domain_ids": ("AU-K",), "kind": "flow",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.au.miners:aofm_tender_footprint",
     "needs": ("AOFM tender results", "AUDUSD and UST10Y H1 bars"),
     "notes": "tests the announcement and the tender as two events"},
    {"name": "au_session_rollover", "domain_ids": ("AU-L",), "kind": "microstructure",
     "cadence_s": 3600.0, "steerable": True, "wired": False,
     "entry": "countries.au.miners:session_rollover",
     "needs": ("AUDUSD and EURUSD M15 bars", "both hemispheres' DST transition dates"),
     "notes": "the DST-disagreement weeks are the natural experiment and are reported separately"},
    {"name": "au_gold_identity_residual", "domain_ids": ("AU-N",), "kind": "basis",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.au.miners:gold_identity_residual",
     "needs": ("XAUAUD, XAUUSD, AUDUSD H1 bars"),
     "notes": "reports the reconstruction residual against the quoted spread; a residual inside "
              "the spread is UNMEASURED, never a finding"},
)

# --------------------------------------------------------------------------- transmission edges
#: Every `target` is a symbol in `data/universe/universe.json`. A source that is not quotable here
#: appears in `TRANSMISSION_TARGETS` above with the symbols it reaches.
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    {"source": "China Caixin manufacturing PMI (01:45 UTC, first business day)",
     "target": "AUDUSD", "sign": "+",
     "mechanism": "a China demand surprise raises expected bulk export volumes and prices; the "
                  "AUD is the most liquid China proxy open at that minute",
     "horizon": "0 to 4 hours",
     "condition": "only when USDCNH moves in the same direction; otherwise it is a dollar event",
     "control": "the same window on EURUSD and USDCAD, and the same UTC minute on non-PMI days",
     "falsifier": "an AUD response of the same size on days with no Chinese release"},
    {"source": "China NBS manufacturing PMI (01:30 UTC, month end)", "target": "AUS200",
     "sign": "+",
     "mechanism": "the index carries roughly 20% materials weight and the cash market is open at "
                  "that minute, so the print reprices the index directly rather than via the open",
     "horizon": "0 to 1 session",
     "condition": "conditioned on whether the print landed before or after the 00:00 UTC open",
     "control": "the same window on JPN225 and HK50, which share China exposure but not ore",
     "falsifier": "an equal response in an index with no materials weight"},
    {"source": "SGX TSI iron ore 62% Fe", "target": "AUDUSD", "sign": "+",
     "mechanism": "iron ore is the largest single Australian export; the price sets export "
                  "receipts, WA royalties and Commonwealth company tax",
     "horizon": "same day to 20 sessions",
     "condition": "conditioned on USDX, so a dollar move is not read as an ore move",
     "control": "the same regression on AUDCAD, which nets two commodity currencies",
     "falsifier": "an equal ore beta in a currency with no ore exports"},
    {"source": "SGX TSI iron ore 62% Fe", "target": "AUS200", "sign": "+",
     "mechanism": "the index's materials weight transmits the ore price into the index level "
                  "without passing through the currency at all",
     "horizon": "same day",
     "condition": "strongest when the ore move exceeds 3% in a session",
     "control": "the same statistic on US500, which has no comparable materials weight",
     "falsifier": "an ore beta in US500 of the same magnitude"},
    {"source": "RBA cash rate surprise versus the IB-implied rate at 04:25 UTC",
     "target": "AUDUSD", "sign": "+",
     "mechanism": "a hawkish surprise raises the expected AUD short-rate path and the carry the "
                  "currency pays",
     "horizon": "0 to 60 minutes, with most of it in the first five",
     "condition": "measured in basis points against the traded curve, never against a survey",
     "control": "the eight nearest non-meeting Tuesdays, and the same window on EURUSD",
     "falsifier": "an equal move on non-meeting Tuesdays at the same minute"},
    {"source": "RBA-minus-RBNZ expected-path difference", "target": "AUDNZD", "sign": "+",
     "mechanism": "the cross removes the dollar from both legs, leaving relative policy and "
                  "relative terms of trade",
     "horizon": "1 to 20 sessions",
     "condition": "only where both curves carry dispersion; 2020-2021 is vacuous by construction",
     "control": "randomise which leg is labelled AU; and the same test on EURGBP",
     "falsifier": "a result inside the 2020-2021 pinned window, which would prove the estimator "
                  "is finding structure in noise"},
    {"source": "XBRUSD", "target": "AUDUSD", "sign": "+",
     "mechanism": "Australian LNG contracts price at 11-15% of a LAGGED crude average, so LNG "
                  "export revenue follows Brent by about a quarter -- the LAG is the mechanism",
     "horizon": "60 to 120 days",
     "condition": "only on the lagged relationship; the contemporaneous one is risk appetite",
     "control": "the contemporaneous Brent-AUD regression, and the same lag applied to USDCAD",
     "falsifier": "a contemporaneous beta as large as the lagged one"},
    {"source": "Australian quarterly trimmed-mean CPI surprise (01:30 UTC)", "target": "AUDUSD",
     "sign": "+",
     "mechanism": "the Board reacts to the trimmed mean, so a core surprise reprices the IB curve "
                  "and the currency with it",
     "horizon": "0 to 2 sessions",
     "condition": "quarterly CPI only; the monthly indicator partially anticipates it",
     "control": "the same window on no-release days, and on monthly-indicator days",
     "falsifier": "an equal response to the headline print with no trimmed-mean surprise"},
    {"source": "Australian quarterly trimmed-mean CPI surprise (01:30 UTC)", "target": "AUS200",
     "sign": "-",
     "mechanism": "a hotter core print raises the discount rate applied to the index and lowers "
                  "the probability of near-term easing",
     "horizon": "0 to 2 sessions",
     "condition": "the sign flips in a growth-scare regime where a hot print reads as demand",
     "control": "the same window on US500 at the same UTC minute",
     "falsifier": "a stable positive sign across both regimes, which would falsify the "
                  "discount-rate story"},
    {"source": "Superannuation quarter-end hedge rebalance", "target": "AUDUSD",
     "sign": "conditional on the offshore equity return",
     "mechanism": "a fund with unhedged offshore assets BUYS foreign currency (sells AUD) after "
                  "an offshore rally and sells it after a drawdown",
     "horizon": "the last three business days of the quarter, at the 16:00 London fix",
     "condition": "the sign MUST be conditioned on the US500 return over the month",
     "control": "months where that return was within +/-0.5%, and the same test on USDCAD",
     "falsifier": "a month-end drift of the same sign regardless of the offshore return"},
    {"source": "US500 overnight session return", "target": "AUS200", "sign": "+",
     "mechanism": "the Australian cash open is the first liquid venue to price the completed US "
                  "session, so the open gap is mechanical rather than informational",
     "horizon": "the open gap",
     "condition": "strongest when the overnight US move exceeds one daily sigma",
     "control": "the same gap statistic on JPN225, where a shared effect is the Asia handover",
     "falsifier": "an open gap uncorrelated with the preceding US session"},
    {"source": "XAUUSD and AUDUSD jointly", "target": "XAUAUD", "sign": "identity",
     "mechanism": "XAUAUD IS XAUUSD divided by AUDUSD to rounding. This edge exists to be the "
                  "NEGATIVE CONTROL for every claim of Australian gold demand",
     "horizon": "instantaneous",
     "condition": "always; the identity holds continuously",
     "control": "the reconstruction residual against the quoted spread",
     "falsifier": "a residual indistinguishable from spread and rounding, which means no "
                  "Australian gold mechanism has been measured at all"},
    {"source": "SPI 200 expiry (third Thursday of Mar/Jun/Sep/Dec)", "target": "AUS200",
     "sign": "+",
     "mechanism": "cash settlement to a Special Opening Quotation built from constituent OPENING "
                  "prices concentrates hedge unwinds into the expiry-morning auction",
     "horizon": "the expiry session, principally the open",
     "condition": "expiry Thursdays only; the rebalance Friday is a different day",
     "control": "the eleven non-expiry third Thursdays, and HK50 expiry days",
     "falsifier": "an effect at the CLOSE rather than the open, which would contradict the SOQ "
                  "settlement mechanism"},
)

# --------------------------------------------------------------------------- eras
#: Cut at reaction-function changes, never at calendar years. A cell fitted across two of these
#: is an average over two different markets and describes neither.
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    {"name": "post-boom easing", "start": "2011-11-01", "end": "2016-08-01",
     "regime": "cash rate 4.75% to 1.50% as the mining investment boom ended and the terms of "
               "trade fell from their 2011 peak",
     "markers": ("the 2011 terms-of-trade peak", "AUDUSD's fall from above parity"),
     "why_it_matters": "the AUD's level relationship to commodity prices was re-based here and "
                       "pre-2011 betas do not transfer across it",
     "status": "SETTLED"},
    {"name": "the 1.50% plateau", "start": "2016-08-02", "end": "2019-06-03",
     "regime": "the cash rate unchanged at 1.50% for 34 months, the longest run on record",
     "markers": ("34 consecutive meetings with no change",),
     "why_it_matters": "policy surprises are near zero BY CONSTRUCTION; an AU-A study pooled "
                       "across this era finds nothing, and that is the correct answer rather "
                       "than a failure of the method",
     "status": "SETTLED"},
    {"name": "the pre-pandemic easing", "start": "2019-06-04", "end": "2020-03-02",
     "regime": "1.50% to 0.50% in three cuts as unemployment stalled",
     "markers": ("three cuts in five months",),
     "why_it_matters": "the last conventional easing cycle before the balance-sheet era",
     "status": "SETTLED"},
    {"name": "emergency, QE and the three-year yield target", "start": "2020-03-03",
     "end": "2021-11-02",
     "regime": "a 0.10% cash rate, a 0.10% target on the April-2024 bond, the Term Funding "
               "Facility and outright bond purchases",
     "markers": ("2020-03-19 the yield target announced", "2021-11-02 the target abandoned"),
     "why_it_matters": "the yield target BROKE in the week of 2021-11-02 when the Bank declined "
                       "to defend it. That week is a structural break in every AUD rates series "
                       "and must be excluded or modelled, never pooled",
     "status": "SETTLED"},
    {"name": "taper and exit", "start": "2021-11-03", "end": "2022-05-02",
     "regime": "the yield target gone, bond purchases wound down, the cash rate still 0.10%",
     "markers": ("2022-02 the end of bond purchases",),
     "why_it_matters": "a short era where the curve repriced violently with no policy change, "
                       "which makes it the cleanest test of whether AU-A measures the decision "
                       "or the curve",
     "status": "SETTLED"},
    {"name": "the hiking cycle", "start": "2022-05-03", "end": "2023-11-07",
     "regime": "0.10% to 4.35% in thirteen increases, the fastest tightening of the "
               "inflation-targeting period",
     "markers": ("2022-05-03 the first increase", "2023-11-07 the last"),
     "why_it_matters": "the IB curve carried large, frequent surprises; this is the richest era "
                       "for AU-A and the era every event study is implicitly fitted to",
     "status": "SETTLED"},
    {"name": "the 4.35% plateau and the governance change", "start": "2023-11-08",
     "end": "2025-02-17",
     "regime": "the cash rate unchanged at 4.35% while the meeting schedule changed underneath it",
     "markers": ("2024-02 eight meetings a year instead of eleven, two-day meetings, and a "
                 "post-meeting press conference",),
     "why_it_matters": "the MEETING COUNT CHANGE is itself a break. An event sample that treats "
                       "a 2023 meeting and a 2025 meeting as exchangeable observations is mixing "
                       "two different information schedules, and each 2025 meeting carries more "
                       "information than each 2023 one did",
     "status": "SETTLED"},
    {"name": "the easing cycle under the Monetary Policy Board", "start": "2025-02-18",
     "end": "2099-12-31",
     "regime": "cuts from 4.35% under the new Monetary Policy Board created by the RBA Review "
               "legislation",
     "markers": ("2025-02 the first cut", "the Board/Monetary Policy Board split"),
     "why_it_matters": "UNVERIFIED TAIL. Anything this pack asserts about 2025-2026 policy must "
                       "be re-read from rba.gov.au/media-releases/ before a study conditions on "
                       "it; the desk's knowledge of this era is not point-in-time and is treated "
                       "as UNMEASURED until checked",
     "status": "UNVERIFIED_TAIL"},
)

# --------------------------------------------------------------------------- access constraints
ACCESS_CONSTRAINTS: tuple[dict[str, Any], ...] = (
    {"constraint": "no iron ore, coal or LNG instrument is quoted by this broker",
     "measured": "data/universe/universe.json holds no ore, coal or LNG symbol",
     "consequence": "the AUD's largest fundamental driver can only ever be an INPUT; every "
                    "terms-of-trade hypothesis must terminate in AUDUSD, AUS200 or a cross"},
    {"constraint": "the ASX 30-day interbank cash rate future is not quoted here",
     "measured": "no short-rate future appears in the universe registry",
     "consequence": "the cleanest consensus proxy in the book must come from ASX end-of-day "
                    "settlements, and the 04:25 UTC pre-announcement snapshot CANNOT be "
                    "reconstructed after the fact. A meeting whose snapshot was not captured "
                    "live has an UNMEASURED surprise, never a zero one"},
    {"constraint": "AUS200 is a broker CFD on the cash index, not the index or its future",
     "measured": "universe.json: asset_class Indices, contract_size 1.0, median spread 80 points, "
                 "34,253 H1 bars",
     "consequence": "the auction print, the dividend points and the SOQ are external references; "
                    "the CFD's own close is the broker's and the two can differ on an expiry "
                    "morning, which is exactly the session AU-G is about"},
    {"constraint": "ASX depth and tick data are licensed products",
     "measured": "public ASX data is end-of-day; intraday depth requires a market data agreement",
     "consequence": "auction microstructure runs on the desk's own CFD tape and public summaries; "
                    "order-book studies are out of reach and are declared UNMEASURED rather than "
                    "approximated from a CFD's synthetic spread"},
)

# --------------------------------------------------------------------------- assembly
_PACK_FIELDS: tuple[str, ...] = (
    "code", "name", "region_command", "currency", "executable_instruments", "central_bank",
    "fixing_conventions", "settlement_conventions", "exchanges", "holidays_rule",
    "fiscal_year_end", "positioning_sources", "native_languages", "terminology", "source_classes",
    "datasets", "actors", "domains", "custom_miners", "transmission_edges_seed", "policy_eras")


def as_dict() -> dict[str, Any]:
    """The pack as a plain mapping, with `transmission_targets`, `access_constraints` and
    `cot_currency` carried alongside the frozen fields so nothing is silently dropped."""
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

    IMPORTED LAZILY AND ON PURPOSE. The framework is a sibling builder's file and this pack ships
    beside it; a module-scope import would make the whole country department un-importable on a
    tree where the framework has not arrived. Any failure to construct the dataclass -- absent,
    renamed, a different signature -- degrades to the mapping rather than raising, because the
    DATA is the deliverable here and the container is not.
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
