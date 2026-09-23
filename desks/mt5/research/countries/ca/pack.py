"""CANADA: a heavy-crude discount set by pipe space, a T+1 currency, and two calendars.

WHAT CANADA IS AS A MARKET MECHANISM, AND WHY IT IS NOT A SMALLER UNITED STATES. Five things
belong to this economy and to no other in the desk's book, and each one is why a domain below
exists rather than a row in the US pack:

  1. THE OIL BETA RUNS THROUGH A DISCOUNT, NOT THROUGH WTI. Canadian heavy crude (Western
     Canadian Select at Hardisty) sells at a differential to WTI that is set by PIPELINE
     TAKEAWAY: Enbridge Mainline apportionment notices, the Trans Mountain expansion that entered
     service in May 2024, rail economics and the Alberta wildfire season. The differential is a
     published, weekly, counted series, and the loonie's response to a $5 move in WTI depends on
     whether the differential is $12 or $30. A CAD study on WTI alone measures the wrong price.

  2. USDCAD SETTLES T+1. It is the only major with next-day value, so the three-day weekend roll
     lands on the THURSDAY rollover rather than the Wednesday one every other pair carries. A
     carry or rollover study copied from EURUSD books the triple swap on the wrong night.

  3. TWO CASH CALENDARS, ONE CURRENCY. The TSX and the NYSE diverge on eleven days a year
     (Victoria Day, Canada Day, the Civic Holiday, Canadian Thanksgiving, Boxing Day on one side;
     Memorial Day, Juneteenth, Independence Day, US Thanksgiving on the other), and Canadian
     Thanksgiving coincides with Columbus Day, when the NYSE is open and the US bond market is
     closed -- a triple divergence. USDCAD trades every one of those days with one side's cash
     market dark, and Remembrance Day closes the Canadian bond market with the TSX open.

  4. THE DATA COLLIDE. Statistics Canada's Labour Force Survey lands at 08:30 ET on the same
     Friday as US payrolls in most months, and Canadian CPI mid-month at 08:30 ET; USDCAD absorbs
     two surprises in one minute and a study that attributes the move to one of them is wrong by
     construction. `CA-B` measures the collision as its own class.

  5. THE TARIFF REGIME IS AN EXTERNAL ACTOR WITH A CALENDAR. Three quarters of Canadian exports
     go to the United States, and from February 2025 the US tariff schedule (fentanyl-related
     25%, steel and aluminium, autos, the USMCA carve-outs and their review) became the largest
     scheduled forcing on the currency. It is modelled as an actor with announcement dates, never
     as a sentiment.

WHAT IS EXECUTABLE AND WHAT IS NOT. USDCAD and six CAD crosses, the S&P/TSX 60 CFD (CA60), WTI,
Brent, Henry Hub, gold, silver and the base metals Canada mines, wheat and the dollar factor are
quotable. WCS, canola, AECO gas, Canada bonds, the BAX/CORRA strip, the SXF future, potash and
lumber are not, and each is named in `TRANSMISSION_TARGETS` with the symbols its mechanism
reaches.

THE LANGUAGES. English and French: the Bank publishes every word in both, Quebec's financial
press (La Presse, Les Affaires, Radio-Canada) writes in French, and "le huard", "le taux
directeur", "l'écart WCS" and "le mur des renouvellements hypothécaires" are the tokens a
screen trained on English misses.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

# --------------------------------------------------------------------------- identity
CODE = "ca"
NAME = "Canada"
REGION_COMMAND = "north_america"
REGION_DESK = "NORTH_AMERICA"
CURRENCY = "CAD"
FISCAL_YEAR_END = "03-31"          # the federal fiscal year; the budget lands in spring
NATIVE_LANGUAGES: tuple[str, ...] = ("en-CA", "fr-CA")
COT_CURRENCY = "CAD"
EXPORT_ECONOMY = "energy_exporter"
RETAIL_LEVERAGE_REGIME = "capped"          # CIRO margin rules; retail FX/CFDs 50:1 at most
MISSION = ("mine Canada as the heavy-crude, T+1, two-calendar economy it is: the WCS "
           "differential and its takeaway, the Bank of Canada against the CORRA strip, the "
           "StatCan/NFP collisions, the tariff calendar, the pension hedge flow and the TSX's "
           "gold-and-oil composition, every one measured on USDCAD, CA60 and the crude legs")

EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "USDCAD",                                            # the sovereign quote
    "CADJPY", "CADCHF", "EURCAD", "GBPCAD", "AUDCAD", "NZDCAD",   # the CAD complex
    "CA60",                                              # the S&P/TSX 60 CFD
    "XTIUSD", "XBRUSD", "XNGUSD",                        # the energy legs
    "XAUUSD", "XAGUSD", "XCUUSD", "XNIUSD", "XALUSD", "XPDUSD",   # what Canada mines
    "WHEAT",                                             # the crop leg (canola is absent)
    "USDX", "US500", "UST10Y",                           # the US controls
)

TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "Western Canadian Select at Hardisty (the WCS-WTI differential)",
     "venue": "Argus / NGX (licensed); Alberta Energy weekly (public)",
     "why": "the heavy-crude discount is THE Canadian oil price; its width is a takeaway "
            "variable, and it transmits into the loonie and the TSX energy weight",
     "proxies": ("USDCAD", "CA60", "XTIUSD")},
    {"name": "Montreal Exchange BAX (three-month CORRA) futures and the OIS strip",
     "venue": "TMX / Montreal Exchange",
     "why": "the traded consensus for every Bank of Canada decision; the surprise in CA-A is "
            "measured in basis points against the strip at 09:40 ET",
     "proxies": ("USDCAD", "CADJPY", "CA60")},
    {"name": "Government of Canada bonds and the CGB/CGF futures", "venue": "Montreal Exchange",
     "why": "the CAD duration leg; the Canada-US 2-year spread is the currency's rate driver "
            "and UST10Y is the only bond the desk holds",
     "proxies": ("UST10Y", "USDCAD", "CADJPY")},
    {"name": "ICE canola futures", "venue": "ICE Futures US (Winnipeg legacy)",
     "why": "Canada is the world's largest canola exporter; the contract is the crop's price "
            "and WHEAT is the nearest quotable grain leg",
     "proxies": ("WHEAT", "USDCAD")},
    {"name": "AECO-C natural gas", "venue": "NGX (licensed); Alberta Energy daily",
     "why": "the Alberta gas price trades at a takeaway-set discount to Henry Hub; LNG Canada's "
            "2025 start changed the discount's era",
     "proxies": ("XNGUSD", "USDCAD")},
    {"name": "S&P/TSX 60 index future (SXF)", "venue": "Montreal Exchange",
     "why": "CA60 is a broker CFD on the cash index; the quarterly expiry and the rebalance "
            "belong to the future and the index provider",
     "proxies": ("CA60",)},
    {"name": "potash (Nutrien-referenced Brazil/US Corn Belt prices) and softwood lumber",
     "venue": "no exchange; trade press assessments",
     "why": "two of the five largest Canadian exports have no contract this broker carries; "
            "their price shocks reach the currency and the index",
     "proxies": ("USDCAD", "CA60", "CORN")},
    {"name": "Bank of Canada Commodity Price Index (BCPI)", "venue": "Bank of Canada",
     "why": "the Bank's own terms-of-trade object, weekly and free; the executable legs are the "
            "components it weights",
     "proxies": ("USDCAD", "XTIUSD", "XNGUSD", "XAUUSD", "WHEAT")},
)

# --------------------------------------------------------------------------- central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "Bank of Canada",
    "short": "BoC",
    "framework": "inflation_targeter",
    "committee": "the Governing Council (Governor, Senior Deputy Governor, four Deputy "
                 "Governors, one external non-executive Deputy since 2023); consensus, no vote "
                 "count published",
    "policy_instrument": "the target for the overnight rate, implemented in a floor system "
                         "with settlement balances remunerated at the target (since 2020)",
    "corridor": "deposit rate at the target since March 2020 (floor system); the Bank rate "
                "25bp above",
    "mandate": "2% CPI inflation, the midpoint of a 1-3% band, under the five-year agreement "
               "with the government renewed in December 2021 (next renewal 2026)",
    "decision_rule": "EIGHT fixed announcement dates a year, published a year ahead; the "
                     "decision is released at 09:45 ET. The Monetary Policy Report accompanies "
                     "the January, April, July and October decisions with a press conference "
                     "at 10:30 ET; a Summary of Deliberations follows every decision about two "
                     "weeks later (since January 2023).",
    "decision_calendar_rule": "eight fixed announcement dates a year, Wednesdays, published "
                              "at bankofcanada.ca for the following year",
    "decision_dates": (
        "2024-01-24", "2024-03-06", "2024-04-10", "2024-06-05", "2024-07-24", "2024-09-04",
        "2024-10-23", "2024-12-11",
        "2025-01-29", "2025-03-12", "2025-04-16", "2025-06-04", "2025-07-30", "2025-09-17",
        "2025-10-29", "2025-12-10",
        "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-10", "2026-07-29", "2026-09-16",
        "2026-10-28", "2026-12-09"),
    "dates_status": "2024 and 2025: VERIFIED against the Bank's published schedule at writing "
                    "(eight each; the 2024 cycle cut from 5.00% to 3.25%, the 2025 cycle to "
                    "2.25% by October). 2026: PUBLISHED SCHEDULE as issued by the Bank in "
                    "2025 -- re-verify against bankofcanada.ca before compiling a 2026 cell. "
                    "The 09:45 ET release time replaced 10:00 ET; the switch date is "
                    "UNMEASURED here and an intraday study must split the sample on it.",
    "decision_time_utc": "14:45",
    "announce_local": "09:45 America/Toronto",
    "announce_utc_dst": "13:45",
    "dst_rule": "America/Toronto follows the US clock: EST (UTC-5) from the first Sunday in "
                "November to the second Sunday in March, EDT (UTC-4) otherwise",
    "presser_utc": "15:30",
    "minutes_lag_days": 14,
    "publication_classes": ("rate_announcement", "monetary_policy_report",
                            "summary_of_deliberations", "press_conference",
                            "business_outlook_survey", "financial_system_review",
                            "speeches"),
    "policy_rate_series": "BoC Valet: V39079",
    "expected_rate_series": "MX:BAX_implied / CORRA OIS",
    "consensus_proxy": "the BAX and CORRA futures strip on the Montreal Exchange at 09:40 ET",
    "consensus_proxy_trap": "CORRA is published at 09:00 ET for the PREVIOUS day; a same-day "
                            "alignment leaks a day; and BAX is a three-month rate whose "
                            "implied step must be scaled for days remaining in the contract",
    "balance_sheet": "QT by full run-off from April 2022; ended in early 2025 with a return to "
                     "routine term repo and bill purchases -- an era boundary for the "
                     "settlement-balance regime",
    "off_cycle": "2020-03-13 and 2020-03-27 were unscheduled cuts; the intermeeting class is "
                 "never pooled with the scheduled sample",
    "other_clocks": (
        {"what": "Business Outlook Survey", "when_local": "10:30 ET, the Monday two weeks "
                                                          "before the January/April/July/October "
                                                          "decision", "when_utc": "15:30",
         "reference_lag_days": -14},
        {"what": "Summary of Deliberations", "when_local": "13:30 ET, about two weeks after",
         "when_utc": "18:30", "reference_lag_days": 14},
        {"what": "daily exchange rates (the 16:30 ET single rate)", "when_local": "16:30 ET",
         "when_utc": "21:30", "reference_lag_days": 0},
    ),
    "root": "https://www.bankofcanada.ca",
}

# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "Bank of Canada daily exchange rate (the single 16:30 ET rate, since 2017)",
     "local": "16:30 America/Toronto, an average of intraday quotes", "time_utc": "21:30",
     "time_utc_dst": "20:30", "dst_rule": "EST/EDT", "instruments": ("USDCAD", "EURCAD"),
     "window_minutes": 5,
     "why": "the accounting and customs reference; NOT transactable, which is why a flow at "
            "this minute would be informative rather than mechanical"},
    {"name": "WM/Refinitiv 16:00 London fix", "local": "16:00 Europe/London",
     "time_utc": "16:00", "time_utc_dst": "15:00", "dst_rule": "GMT/BST",
     "instruments": ("USDCAD", "EURCAD", "CADJPY", "GBPCAD"), "window_minutes": 5,
     "why": "the Maple 8 pension funds and the index hedgers transact here at month end; "
            "CA-H's flow lands in this window"},
    {"name": "TSX closing auction (the official close of the S&P/TSX 60)",
     "local": "16:00 America/Toronto, MOC imbalance published from 15:40", "time_utc": "21:00",
     "time_utc_dst": "20:00", "dst_rule": "EST/EDT", "instruments": ("CA60",),
     "window_minutes": 10,
     "why": "the rebalance and the SXF expiry settle to this print; the 15:40 imbalance is "
            "twenty minutes earlier than the NYSE's, so the two closes are not the same event"},
    {"name": "WCS Hardisty daily settlement", "local": "about 14:30 America/Toronto",
     "time_utc": "19:30", "time_utc_dst": "18:30", "dst_rule": "EST/EDT",
     "instruments": ("XTIUSD", "USDCAD"), "window_minutes": 30,
     "why": "the differential is assessed against the NYMEX WTI settlement window; the public "
            "weekly Alberta series is the free, lagged echo"},
    {"name": "Government of Canada bond auction close", "local": "12:00 America/Toronto; "
                                                                "results within minutes",
     "time_utc": "17:00", "time_utc_dst": "16:00", "dst_rule": "EST/EDT",
     "instruments": ("USDCAD", "UST10Y"), "window_minutes": 5,
     "why": "the CAD supply-shock event; the bond is not quotable, the currency is"},
    {"name": "CORRA publication (for the previous business day)", "local": "09:00 ET",
     "time_utc": "14:00", "time_utc_dst": "13:00", "dst_rule": "EST/EDT",
     "instruments": ("USDCAD",), "window_minutes": 1,
     "why": "a next-morning print; aligning it to the day it measures is a one-day leak"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "USDCAD spot T+1 and the THURSDAY triple roll", "kind": "weekday",
     "weekday": 3, "convention": "T+1 value; rollover 17:00 New York",
     "roll": "next", "instruments": ("USDCAD",),
     "why": "the only major with next-day value: the weekend's three days of carry are booked "
            "at Thursday's rollover, not Wednesday's; a swap study copied from EURUSD books "
            "the triple on the wrong night and invents a Wednesday effect"},
    {"name": "CAD crosses T+2 and the Wednesday triple roll", "kind": "weekday", "weekday": 2,
     "convention": "T+2 value", "roll": "next",
     "instruments": ("CADJPY", "EURCAD", "GBPCAD", "AUDCAD", "NZDCAD", "CADCHF"),
     "why": "the crosses settle T+2 like everything else; USDCAD and CADJPY therefore carry "
            "their weekend swap on DIFFERENT nights, which a carry study must not pool"},
    {"name": "Canadian equities and GoC bonds T+1 (since 2024-05-27)", "kind": "weekday",
     "convention": "T+1", "roll": "next", "instruments": ("CA60",),
     "why": "Canada moved to T+1 one day before the US (27 May 2024); an era boundary for "
            "index-flow lag structure"},
    {"name": "SXF expiry and the S&P/TSX quarterly rebalance", "kind": "weekday", "weekday": 4,
     "week_of_month": 3, "months": (3, 6, 9, 12), "roll": "previous",
     "window_utc": ("14:30", "21:00"), "instruments": ("CA60",),
     "why": "the future expires and the index rebalances on the same third Friday, settled to "
            "the closing auction; like the US and unlike Australia"},
    {"name": "month-end pension hedge rebalance", "kind": "month_end", "roll": "previous",
     "window_utc": ("15:00", "16:00"), "instruments": ("USDCAD", "EURCAD", "CADJPY"),
     "why": "the Maple 8 hold large foreign books with declared hedge ratios; after a US equity "
            "rally the hedger SELLS USD (buys CAD) to restore the ratio -- the sign is set by "
            "the offshore return, and an unconditional month-end study averages it to zero"},
    {"name": "federal fiscal year end (31 March) and the spring budget",
     "kind": "fiscal_year_end", "roll": "previous", "window_utc": ("14:00", "21:00"),
     "instruments": ("USDCAD", "CA60"),
     "why": "the budget's WTI assumption and the provinces' (Alberta's) royalty forecast are "
            "published fiscal objects the currency reacts to"},
    {"name": "personal tax deadline (30 April) and quarterly instalments",
     "kind": "day_of_month", "days": (15,), "months": (3, 6, 9, 12), "roll": "next",
     "window_utc": ("13:00", "21:00"), "instruments": ("USDCAD",),
     "why": "smaller than the US drains and declared so the plumbing study can measure the "
            "absence rather than assume it"},
    {"name": "CFTC 6C snapshot Tuesday, release Friday", "kind": "weekday", "weekday": 1,
     "roll": "next", "instruments": ("USDCAD",),
     "why": "three days stale on release; usable from Friday 15:30 ET only"},
)

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Toronto Stock Exchange (TMX Group)", "index_symbols": ("CA60",),
     "open_local": "09:30 America/Toronto", "close_local": "16:00", "open_utc": "14:30",
     "close_utc": "21:00", "dst_rule": "EST/EDT",
     "auction": "opening auction 09:30; closing auction 16:00 with imbalances from 15:40; "
                "extended session 16:15-17:00 at the closing price",
     "expiry_rule": "n/a (cash market); the S&P/TSX quarterly rebalance is effective after the "
                    "close of the third Friday of March, June, September and December",
     "holidays": "the TSX calendar: New Year's Day, Family Day, Good Friday, Victoria Day, "
                 "Canada Day, the Civic Holiday, Labour Day, Thanksgiving, Christmas, Boxing "
                 "Day; OPEN on Remembrance Day and on the National Day for Truth and "
                 "Reconciliation",
     "notes": "financials about 30%, energy 17%, materials 12% (gold miners): CA60 is a bank, "
              "oil and gold index and its beta to XAUUSD is a composition fact, not a mystery"},
    {"name": "Montreal Exchange (derivatives)", "index_symbols": ("CA60",),
     "open_local": "SXF 09:30-16:15 with an early session from 06:00; BAX/CGB from 06:00",
     "close_local": "16:30", "open_utc": "11:00", "close_utc": "21:30", "dst_rule": "EST/EDT",
     "auction": "n/a",
     "expiry_rule": "SXF: third Friday of March, June, September, December, cash settled to the "
                    "official opening index level. BAX/CRA: the second London business day "
                    "before the third Wednesday of the contract month. CGB: the last business "
                    "day of the contract month, physically delivered.",
     "holidays": "the TSX calendar",
     "notes": "the SXF settles to the OPENING level on expiry Friday -- an overnight gap into an "
              "open, like the SPI 200, not a close like the NYSE"},
)

SESSION_WINDOWS: tuple[dict[str, Any], ...] = (
    {"name": "ca_data_minute", "start_utc": "13:30", "end_utc": "14:30",
     "notes": "08:30 ET: LFS, CPI, trade, GDP, retail; the NFP collision lives here"},
    {"name": "ca_boc_window", "start_utc": "14:45", "end_utc": "16:00",
     "notes": "09:45 ET announcement; 10:30 ET MPR press conference"},
    {"name": "ca_cash_session", "start_utc": "14:30", "end_utc": "21:00",
     "notes": "the TSX day, coinciding with New York"},
    {"name": "ca_wcs_settlement", "start_utc": "19:00", "end_utc": "20:00",
     "notes": "the WTI/WCS settlement window"},
    {"name": "ca_boc_rate_and_close", "start_utc": "21:00", "end_utc": "21:45",
     "notes": "16:00 close, 16:30 BoC daily rate, 17:00 FX rollover (USDCAD T+1 on Thursday)"},
)

RELEASE_CLASSES: tuple[dict[str, Any], ...] = (
    {"name": "Labour Force Survey", "cadence": "monthly", "time_utc": "13:30",
     "source": "Statistics Canada", "actual_series": "StatCan:14-10-0287",
     "expected_series": "UNMEASURED",
     "notes": "the first Friday (usually the SAME minute as US payrolls); the employment change "
             "is noisy by design (a sample of 56,000 households) and the tape over-reads it"},
    {"name": "Consumer Price Index", "cadence": "monthly", "time_utc": "13:30",
     "source": "Statistics Canada", "actual_series": "StatCan:18-10-0004",
     "expected_series": "UNMEASURED",
     "notes": "around the 15th-20th at 08:30 ET; the Bank's preferred core measures (trim, "
             "median) are the surprise the currency trades, not the headline"},
    {"name": "International merchandise trade", "cadence": "monthly", "time_utc": "13:30",
     "source": "Statistics Canada / CBSA", "actual_series": "StatCan:12-10-0011",
     "expected_series": "UNMEASURED",
     "notes": "energy is a quarter of exports; the same minute as the US trade print"},
    {"name": "GDP by industry (monthly) and quarterly GDP", "cadence": "monthly",
     "time_utc": "13:30", "source": "Statistics Canada", "actual_series": "StatCan:36-10-0434",
     "expected_series": "UNMEASURED",
     "notes": "StatCan publishes an ADVANCE estimate for the following month in the same "
             "release; the advance is the surprise"},
    {"name": "Bank of Canada Business Outlook Survey", "cadence": "quarterly",
     "time_utc": "15:30", "source": "Bank of Canada", "actual_series": "BoC:BOS",
     "expected_series": "n/a",
     "notes": "the Monday two weeks before the MPR decision; the capacity and inflation-"
             "expectation questions"},
    {"name": "CREA existing home sales and the MLS HPI", "cadence": "monthly",
     "time_utc": "14:00", "source": "Canadian Real Estate Association",
     "actual_series": "CREA:HPI", "expected_series": "UNMEASURED",
     "notes": "mid-month; the household-leverage constraint the Bank names in every MPR"},
    {"name": "Alberta Energy weekly WCS price and AER monthly production",
     "cadence": "weekly", "time_utc": "22:00", "source": "Government of Alberta / AER",
     "actual_series": "Alberta:WCS_Hardisty", "expected_series": "n/a",
     "notes": "the free echo of the licensed daily assessment; the ST3 production table is "
             "monthly with a two-month lag"},
    {"name": "Enbridge Mainline apportionment notice", "cadence": "monthly",
     "time_utc": "22:00", "source": "Enbridge", "actual_series": "Enbridge:apportionment",
     "expected_series": "n/a",
     "notes": "published in the last week of the month for the next; apportionment above zero "
             "means barrels are stranded in Alberta and the differential widens"},
    {"name": "US tariff actions affecting Canada", "cadence": "irregular", "time_utc": "UNMEASURED",
     "source": "Federal Register / White House / Department of Finance Canada",
     "actual_series": "event_ledger:tariffs_ca", "expected_series": "n/a",
     "notes": "an event class with announcement, effective and exemption dates; each is a "
             "separate event and the effective date is the flow"},
    {"name": "Canadian Grain Commission weekly exports and StatCan crop production",
     "cadence": "weekly", "time_utc": "20:00", "source": "CGC / StatCan",
     "actual_series": "CGC:weekly_exports", "expected_series": "UNMEASURED",
     "notes": "the crop production reports (June, August, December) are the WASDE analogues"},
)

# --------------------------------------------------------------------------- holidays
HOLIDAY_TABLE: dict[int, dict[str, str]] = {
    2024: {"2024-01-01": "New Year's Day", "2024-02-19": "Family Day",
           "2024-03-29": "Good Friday", "2024-05-20": "Victoria Day",
           "2024-07-01": "Canada Day", "2024-08-05": "Civic Holiday",
           "2024-09-02": "Labour Day", "2024-10-14": "Thanksgiving (Canada)",
           "2024-12-25": "Christmas Day", "2024-12-26": "Boxing Day"},
    2025: {"2025-01-01": "New Year's Day", "2025-02-17": "Family Day",
           "2025-04-18": "Good Friday", "2025-05-19": "Victoria Day",
           "2025-07-01": "Canada Day", "2025-08-04": "Civic Holiday",
           "2025-09-01": "Labour Day", "2025-10-13": "Thanksgiving (Canada)",
           "2025-12-25": "Christmas Day", "2025-12-26": "Boxing Day"},
    2026: {"2026-01-01": "New Year's Day", "2026-02-16": "Family Day",
           "2026-04-03": "Good Friday", "2026-05-18": "Victoria Day",
           "2026-07-01": "Canada Day", "2026-08-03": "Civic Holiday",
           "2026-09-07": "Labour Day", "2026-10-12": "Thanksgiving (Canada)",
           "2026-12-25": "Christmas Day", "2026-12-28": "Boxing Day observed (26th is a Saturday)"},
}
BOND_MARKET_ONLY_CLOSURES: dict[str, str] = {
    "2024-11-11": "Remembrance Day (CIRO bond market closed; TSX open)",
    "2025-11-11": "Remembrance Day (CIRO bond market closed; TSX open)",
    "2026-11-11": "Remembrance Day (CIRO bond market closed; TSX open)",
}
#: TSX open while the NYSE is closed, and the reverse: USDCAD trades every one with one cash
#: market dark. Declared so a microstructure study can use the divergence rather than trip on it.
CALENDAR_DIVERGENCES: dict[str, str] = {
    "2024-01-15": "TSX open, NYSE closed (MLK)", "2024-05-27": "TSX open, NYSE closed (Memorial)",
    "2024-06-19": "TSX open, NYSE closed (Juneteenth)",
    "2024-07-04": "TSX open, NYSE closed (Independence Day)",
    "2024-11-28": "TSX open, NYSE closed (US Thanksgiving)",
    "2024-05-20": "TSX closed, NYSE open (Victoria Day)",
    "2024-07-01": "TSX closed, NYSE open (Canada Day)",
    "2024-08-05": "TSX closed, NYSE open (Civic Holiday)",
    "2024-10-14": "TSX closed, NYSE open, SIFMA closed (Thanksgiving / Columbus Day)",
    "2024-12-26": "TSX closed, NYSE open (Boxing Day)",
    "2025-01-20": "TSX open, NYSE closed (MLK)", "2025-05-26": "TSX open, NYSE closed (Memorial)",
    "2025-06-19": "TSX open, NYSE closed (Juneteenth)",
    "2025-07-04": "TSX open, NYSE closed (Independence Day)",
    "2025-11-27": "TSX open, NYSE closed (US Thanksgiving)",
    "2025-05-19": "TSX closed, NYSE open (Victoria Day)",
    "2025-07-01": "TSX closed, NYSE open (Canada Day)",
    "2025-08-04": "TSX closed, NYSE open (Civic Holiday)",
    "2025-10-13": "TSX closed, NYSE open, SIFMA closed (Thanksgiving / Columbus Day)",
    "2025-12-26": "TSX closed, NYSE open (Boxing Day)",
    "2026-01-19": "TSX open, NYSE closed (MLK)", "2026-05-25": "TSX open, NYSE closed (Memorial)",
    "2026-06-19": "TSX open, NYSE closed (Juneteenth)",
    "2026-07-03": "TSX open, NYSE closed (Independence Day observed)",
    "2026-11-26": "TSX open, NYSE closed (US Thanksgiving)",
    "2026-05-18": "TSX closed, NYSE open (Victoria Day)",
    "2026-07-01": "TSX closed, NYSE open (Canada Day)",
    "2026-08-03": "TSX closed, NYSE open (Civic Holiday)",
    "2026-10-12": "TSX closed, NYSE open, SIFMA closed (Thanksgiving / Columbus Day)",
    "2026-12-28": "TSX closed, NYSE open (Boxing Day observed)",
}
HOLIDAYS_RULE: dict[str, Any] = {
    "rule": "TSX: New Year's Day, Family Day (third Monday of February, Ontario), Good Friday, "
            "Victoria Day (the Monday before 25 May), Canada Day (1 July, Mondayised), the Civic "
            "Holiday (first Monday of August), Labour Day (first Monday of September), "
            "Thanksgiving (second Monday of October), Christmas and Boxing Day (Mondayised in "
            "sequence). Remembrance Day (11 November) closes the bond market only; the National "
            "Day for Truth and Reconciliation (30 September) has been observed OPEN by the TSX "
            "-- declared, and re-verified each year rather than assumed.",
    "table": HOLIDAY_TABLE,
    "status": "2024 and 2025 VERIFIED against the TMX published calendar at writing; 2026 from "
              "the TMX published calendar, re-verify before compiling; the divergence table is "
              "derived from the two calendars and is the object CA-E measures",
    "weekly_closed": (5, 6),
    "bond_market_only": BOND_MARKET_ONLY_CLOSURES,
    "divergences": CALENDAR_DIVERGENCES,
    "notes": "the broker's CA60 tape may carry bars on TSX holidays (synthetic from the SXF or "
             "from US trading); a holiday study must use the CASH calendar to define closed",
}

# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "CFTC Commitments of Traders -- CME Canadian dollar futures (6C, code 090741)",
     "root": "https://www.cftc.gov/MarketReports/CommitmentsofTraders/",
     "fields": ("non_commercial_long", "non_commercial_short", "leveraged_funds_net",
                "asset_manager_net", "open_interest"),
     "frequency": "weekly", "snapshot": "Tuesday close",
     "publish_utc": "20:30 (EST) / 19:30 (EDT), Friday", "lag_days": 3,
     "licence": "free, public (US government work)", "available": True,
     "why": "the CAD's only trader-category positioning series; the record leveraged-funds "
            "short of 2024-2025 is the unwind setup CA-G measures",
     "pit_warning": "three days stale on release; the Tuesday alignment is a look-ahead bug"},
    {"name": "Montreal Exchange daily volume and open interest (SXF, BAX, CGB)",
     "root": "https://www.m-x.ca/en/trading/data/daily-statistics",
     "fields": ("volume", "open_interest"), "frequency": "daily", "snapshot": "session close",
     "publish_utc": "23:00", "lag_days": 0, "licence": "free end-of-day", "available": True,
     "why": "the fast complement for the index and rate legs",
     "pit_warning": "preliminary OI restated next morning"},
    {"name": "Bank of Canada balance sheet and settlement balances (weekly)",
     "root": "https://www.bankofcanada.ca/rates/banking-and-financial-statistics/",
     "fields": ("settlement_balances", "government_deposits", "term_repo"),
     "frequency": "weekly", "snapshot": "Wednesday", "publish_utc": "21:00", "lag_days": 2,
     "licence": "free, public", "available": True,
     "why": "the plumbing half: the run-off from 2022 and the 2025 return to bill purchases",
     "pit_warning": "weekly with a two-day lag"},
    {"name": "a Canadian retail FX/CFD positioning report", "root": "", "fields": (),
     "frequency": "n/a", "snapshot": "", "publish_utc": "", "lag_days": 0, "licence": "",
     "available": False,
     "why": "CIRO publishes margin rules, not aggregate positioning",
     "pit_warning": "DOES NOT EXIST; Canadian retail positioning is UNMEASURED and never proxied "
                    "by the CME series"},
)

# --------------------------------------------------------------------------- terminology
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "CA-A": ("the Bank", "the Governing Council", "the overnight target", "the MPR",
             "the Summary of Deliberations", "the BOS", "le taux directeur",
             "la Banque du Canada", "le Rapport sur la politique monétaire",
             "le Conseil de direction", "le taux du financement à un jour", "la cible de 2 %"),
    "CA-B": ("the LFS", "the jobs number", "CPI-trim", "CPI-median", "the core measures",
             "the advance estimate", "l'Enquête sur la population active", "l'IPC",
             "l'inflation fondamentale", "le taux de chômage", "la balance commerciale",
             "les exportations d'énergie"),
    "CA-C": ("WCS", "the differential", "the diff", "the heavy discount", "apportionment",
             "takeaway", "the Mainline", "TMX", "Trans Mountain", "the oil sands", "bitumen",
             "dilbit", "Hardisty", "crude by rail", "the wildfire season", "le pétrole lourd",
             "l'écart WCS", "les sables bitumineux", "l'oléoduc", "les feux de forêt",
             "le différentiel"),
    "CA-D": ("the tariffs", "the fentanyl tariff", "USMCA", "CUSMA", "the review", "the "
             "exemption", "countermeasures", "les droits de douane", "les tarifs douaniers",
             "l'ACEUM", "les contre-mesures", "les exportations vers les États-Unis"),
    "CA-E": ("Family Day", "Victoria Day", "the Civic Holiday", "Canadian Thanksgiving",
             "Boxing Day", "Remembrance Day", "la fête du Canada", "la fête du Travail",
             "le jour du Souvenir", "l'Action de grâce"),
    "CA-F": ("T+1", "the Thursday roll", "tom-next", "the rollover", "le report",
             "le taux de change au comptant"),
    "CA-G": ("the COT", "the 6C", "spec shorts", "the loonie short", "the wash-out",
             "les spéculateurs"),
    "CA-H": ("the Maple 8", "CPPIB", "the Caisse", "OTPP", "the hedge ratio", "the currency "
             "overlay", "la Caisse de dépôt", "les caisses de retraite", "la couverture de "
             "change"),
    "CA-I": ("the renewal wall", "the mortgage cliff", "variable-rate", "the five-year fixed",
             "household debt", "CMHC", "CREA", "the HPI", "le mur des renouvellements "
             "hypothécaires", "l'endettement des ménages", "le marché immobilier", "la SCHL"),
    "CA-J": ("the TSX", "the 60", "the SXF", "the rebalance", "the gold miners", "the "
             "materials weight", "the energy weight", "the banks", "la Bourse de Toronto",
             "l'indice composé", "les minières aurifères", "les banques canadiennes"),
    "CA-K": ("canola", "the crop report", "the CGC", "the Prairies", "potash", "the harvest",
             "le canola", "la potasse", "les Prairies", "la récolte", "le blé"),
    "CA-L": ("AECO", "the AECO basis", "LNG Canada", "Kitimat", "the Montney", "le gaz "
             "naturel", "le GNL"),
    "CA-M": ("non-permanent residents", "the immigration levels plan", "population growth",
             "les résidents non permanents", "l'immigration", "la croissance démographique"),
    "official": ("Bank of Canada announcement", "Monetary Policy Report", "Summary of "
                 "Deliberations", "The Daily Statistics Canada", "Labour Force Survey release",
                 "CPI release", "AER ST3", "Alberta WCS price", "annonce de la Banque du Canada",
                 "Le Quotidien Statistique Canada"),
    "institutional": ("TMX trading calendar", "SXF specifications", "CIRO holiday schedule",
                      "Enbridge apportionment", "Trans Mountain nominations", "CAPP forecast",
                      "calendrier de la Bourse"),
    "academic": ("Bank of Canada staff working paper", "staff analytical note", "C.D. Howe "
                 "monetary policy council", "SSRN Canadian dollar commodity", "document de "
                 "travail du personnel"),
    "practitioner": ("Canadian rates strategy", "loonie outlook", "WCS differential outlook",
                     "BoC preview", "économiste en chef", "perspectives du huard"),
    "retail_ecology": ("r/CanadianInvestor", "r/PersonalFinanceCanada", "RedFlagDeals "
                       "investing", "Stockhouse bullboard", "le huard", "REER", "CELI", "FNB"),
    "app_ecosystem": ("Questrade API", "Wealthsimple Trade", "TradingView TSX", "IBKR Canada",
                      "StatCan WDS API", "Valet API"),
    "media": ("Financial Post", "BNN Bloomberg", "Globe and Mail markets", "La Presse "
              "affaires", "Les Affaires", "Radio-Canada économie", "Reuters Canada"),
    "archive": ("Bank of Canada archives", "CANSIM archived table", "Wayback Stockhouse",
                "archives de la Banque du Canada"),
    "physical_economy": ("Enbridge Mainline apportionment", "CER pipeline throughput", "AER "
                         "production", "CWFIS fire danger", "Port of Vancouver statistics",
                         "Canadian Grain Commission weekly exports", "AESO supply demand",
                         "Great Lakes Seaway tonnage"),
    "source_graph": ("Bank of Canada related research", "RePEc Canada", "r/CanadianInvestor "
                     "wiki", "blogroll économistes", "liens connexes"),
}

# --------------------------------------------------------------------------- sources
SOURCE_LAYERS: tuple[str, ...] = (
    "official", "institutional", "academic", "practitioner", "retail_ecology", "app_ecosystem",
    "media", "archive", "physical_economy", "source_graph")
ACCESS_LABELS: tuple[str, ...] = (
    "PUBLIC", "PUBLIC_WITH_TERMS", "LICENSED", "OPEN_DATA", "PUBLIC_ARCHIVE", "PUBLIC_SOCIAL",
    "USER_SUBMITTED", "ACCESS_UNCLEAR", "PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")
CREDIBILITY_LABELS: tuple[str, ...] = (
    "AUTHORITATIVE", "RELIABLE", "UNRELIABLE", "FRINGE", "CONTRADICTED", "UNKNOWN")
PREDICTIVE_STATES: tuple[str, ...] = (
    "UNTESTED", "PREDICTIVE", "NOT_PREDICTIVE", "NARRATIVE_FEATURE")


def _seq(values: Iterable[Any]) -> tuple[str, ...]:
    return tuple(str(v) for v in values)


def source_class(sid: str, label: str, *, layer: str, roots: Iterable[str],
                 queries: Iterable[str], languages: Iterable[str], access_label: str,
                 credibility: str, predictive_state: str, licence: str,
                 machine_use_allowed: bool = True, notes: str = "") -> dict[str, Any]:
    if layer not in SOURCE_LAYERS:
        raise ValueError(f"source {sid}: layer {layer!r} not one of {list(SOURCE_LAYERS)}")
    if access_label not in ACCESS_LABELS:
        raise ValueError(f"source {sid}: access_label {access_label!r} not recognised")
    if credibility not in CREDIBILITY_LABELS:
        raise ValueError(f"source {sid}: credibility {credibility!r} not recognised")
    if predictive_state not in PREDICTIVE_STATES:
        raise ValueError(f"source {sid}: predictive_state {predictive_state!r} not recognised")
    return {"id": sid, "label": label, "layer": layer, "roots": _seq(roots),
            "queries": _seq(queries), "languages": _seq(languages),
            "access_label": access_label, "credibility": credibility,
            "predictive_state": predictive_state,
            "machine_use_allowed": bool(machine_use_allowed), "licence": licence, "notes": notes}


def absent_layer(layer: str, reason: str) -> dict[str, Any]:
    if layer not in SOURCE_LAYERS:
        raise ValueError(f"absent layer {layer!r} not one of {list(SOURCE_LAYERS)}")
    return {"id": f"absent_{layer}", "label": f"NO SOURCE IN THIS LAYER: {layer}", "layer": layer,
            "roots": (), "queries": (), "languages": (), "access_label": "ACCESS_UNCLEAR",
            "credibility": "UNKNOWN", "predictive_state": "UNTESTED",
            "machine_use_allowed": False, "licence": "n/a",
            "notes": f"DECLARED ABSENT, NOT BLANK: {reason}"}


SOURCE_CLASSES: tuple[dict[str, Any], ...] = (
    source_class(
        "ca_boc", "Bank of Canada: announcements, MPR, deliberations, Valet API",
        layer="official",
        roots=("https://www.bankofcanada.ca/press/press-releases/",
               "https://www.bankofcanada.ca/publications/mpr/",
               "https://www.bankofcanada.ca/valet/docs",
               "https://www.bankofcanada.ca/rates/interest-rates/"),
        queries=("rate announcement", "Monetary Policy Report", "Summary of Deliberations",
                 "Business Outlook Survey", "Valet series V39079", "settlement balances",
                 "annonce du taux directeur", "Rapport sur la politique monétaire",
                 "Résumé des délibérations"),
        languages=("en", "fr"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="Bank of Canada terms of use (free, attribution)",
        notes="every publication is released in both languages at the same minute; the Valet "
              "API carries the policy rate, CORRA, the BCPI and the daily exchange rates"),
    source_class(
        "ca_statcan_cbsa", "Statistics Canada (The Daily, WDS API) and CBSA trade data",
        layer="official",
        roots=("https://www150.statcan.gc.ca/n1/dai-quo/index-eng.htm",
               "https://www150.statcan.gc.ca/t1/wds/", "https://www.cbsa-asfc.gc.ca/"),
        queries=("Labour Force Survey", "Consumer Price Index", "international merchandise "
                 "trade", "gross domestic product by industry", "release schedule", "Web Data "
                 "Service", "Enquête sur la population active", "Indice des prix à la "
                 "consommation", "commerce international de marchandises", "Le Quotidien"),
        languages=("en", "fr"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="Statistics Canada Open Licence",
        notes="REVISED: the LFS is not revised but the GDP and trade series are; the 08:30 ET "
              "embargo minute is the event time and the NFP collision is measured in CA-B"),
    source_class(
        "ca_finance_provinces", "Department of Finance Canada and the Alberta budget",
        layer="official",
        roots=("https://www.canada.ca/en/department-finance.html", "https://budget.canada.ca/",
               "https://www.alberta.ca/budget"),
        queries=("federal budget", "fall economic statement", "WTI assumption", "royalty "
                 "revenue", "debt management strategy", "budget fédéral", "énoncé économique "
                 "de l'automne", "prévision du prix du pétrole"),
        languages=("en", "fr"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="Open Government Licence - Canada",
        notes="the WTI and WCS assumptions in the Alberta budget are published fiscal objects"),
    source_class(
        "ca_aer_alberta_energy", "Alberta Energy Regulator (ST3, ST98) and Alberta Energy "
                                 "(weekly WCS price)",
        layer="official",
        roots=("https://www.aer.ca/providing-information/data-and-reports/statistical-reports",
               "https://economicdashboard.alberta.ca/dashboard/oil-prices/",
               "https://www.cer-rec.gc.ca/en/data-analysis/"),
        queries=("ST3 crude oil production", "ST98 outlook", "Western Canadian Select price",
                 "WCS-WTI differential", "pipeline throughput", "apportionment", "prix du WCS"),
        languages=("en", "fr"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="Open Government Licence - Alberta / Canada",
        notes="the production table lags two months; the WCS weekly is the free echo of the "
              "licensed daily assessment and is the series CA-C conditions on"),
    source_class(
        "ca_nrcan_cwfis", "Natural Resources Canada wildfire information system (CWFIS)",
        layer="official",
        roots=("https://cwfis.cfs.nrcan.gc.ca/home", "https://cwfis.cfs.nrcan.gc.ca/datamart"),
        queries=("fire danger", "active fires", "hotspots", "fire weather index", "Alberta "
                 "wildfire", "feux de forêt actifs", "indice forêt-météo"),
        languages=("en", "fr"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="Open Government Licence - Canada",
        notes="the daily hotspot file is the leading input to an oil sands shut-in (2016 Fort "
              "McMurray, 2023, 2024 Jasper); the shut-in reaches WTI through WCS"),
    source_class(
        "ca_tmx_ciro", "TMX Group and CIRO (calendars, contract terms, margin, market statistics)",
        layer="institutional",
        roots=("https://www.tsx.com/trading/calendars-and-trading-hours/",
               "https://www.m-x.ca/en/markets/products", "https://www.ciro.ca/"),
        queries=("trading calendar", "SXF contract specifications", "BAX", "CGB", "market "
                 "statistics", "margin requirements", "holiday schedule", "calendrier de "
                 "négociation", "spécifications du contrat"),
        languages=("en", "fr"), access_label="PUBLIC_WITH_TERMS", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="TMX terms; end-of-day statistics free",
        notes="the expiry rules and the two-calendar divergence table are read from here"),
    source_class(
        "ca_enbridge_tmx_capp", "Enbridge (Mainline apportionment), Trans Mountain (nominations) "
                                "and CAPP (industry forecasts)",
        layer="institutional",
        roots=("https://www.enbridge.com/customers/liquids-pipelines/mainline-apportionment",
               "https://www.transmountain.com/", "https://www.capp.ca/"),
        queries=("apportionment", "nominations", "line fill", "TMX expansion", "crude oil "
                 "forecast", "répartition proportionnelle", "prévisions de production"),
        languages=("en", "fr"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="company disclosures; public",
        notes="apportionment is a monthly notice with a date; it is the takeaway variable CA-C "
              "is built on and the single most Canadian mechanism in this pack"),
    source_class(
        "ca_boc_research_cdhowe", "Bank of Canada staff working papers and analytical notes; "
                                  "the C.D. Howe Institute",
        layer="academic",
        roots=("https://www.bankofcanada.ca/research/", "https://www.cdhowe.org/"),
        queries=("staff working paper", "staff analytical note", "commodity currency", "oil "
                 "price pass-through", "exchange rate pass-through", "monetary policy council",
                 "document de travail du personnel", "note analytique"),
        languages=("en", "fr"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free; attribution",
        notes="the Bank's own research on the oil beta and pass-through is the hypothesis "
              "source for CA-C; every effect is re-measured on this tape before it is evidence"),
    source_class(
        "ca_bank_economics", "The Big Six bank economics desks (public notes) and the WCS "
                             "differential commentary",
        layer="practitioner",
        roots=("https://thoughtleadership.rbc.com/", "https://economics.td.com/",
               "https://economics.bmo.com/", "https://www.scotiabank.com/ca/en/about/economics",
               "https://economics.cibccm.com/"),
        queries=("BoC preview", "loonie outlook", "WCS differential", "housing forecast", "rate "
                 "path", "économiste en chef", "perspectives économiques", "prévisions du "
                 "huard"),
        languages=("en", "fr"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="public notes; each bank's terms",
        notes="claims, dated and testable; a bank's rate call is a hypothesis about the Bank"),
    source_class(
        "ca_research_subscriptions", "Rosenberg Research and the paid macro letters",
        layer="practitioner",
        roots=("https://www.rosenbergresearch.com/",),
        queries=("Canada housing", "recession call", "loonie"),
        languages=("en",), access_label="LICENSED", credibility="RELIABLE",
        predictive_state="UNTESTED", machine_use_allowed=True,
        licence="subscription; terms forbid redistribution and machine extraction",
        notes="REGISTERED, NEVER SCRAPED; read only through public interviews"),
    source_class(
        "ca_retail_forums", "Retail ecology: r/CanadianInvestor, r/PersonalFinanceCanada, "
                            "RedFlagDeals investing, the Stockhouse bullboards",
        layer="retail_ecology",
        roots=("https://www.reddit.com/r/CanadianInvestor/",
               "https://www.reddit.com/r/PersonalFinanceCanada/",
               "https://forums.redflagdeals.com/investing-f9/", "https://stockhouse.com/"),
        queries=("TFSA", "RRSP", "the loonie", "Norbert's gambit", "the TSX", "oil stocks",
                 "bullboard", "REER", "CELI", "le huard", "FNB"),
        languages=("en", "fr"), access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
        predictive_state="NARRATIVE_FEATURE", machine_use_allowed=True,
        licence="Reddit API terms; forum terms",
        notes="KEPT AT LOW WEIGHT: Stockhouse is single-name-heavy and belongs to the event "
              "lane; 'Norbert's gambit' is a retail USDCAD conversion flow with a real "
              "settlement footprint and is the one mechanism this layer names"),
    source_class(
        "ca_apps_apis", "Questrade and IBKR Canada APIs, Wealthsimple, TradingView TSX scripts, "
                        "the StatCan WDS and Bank of Canada Valet APIs",
        layer="app_ecosystem",
        roots=("https://www.questrade.com/api", "https://www.tradingview.com/markets/stocks-"
               "canada/", "https://www150.statcan.gc.ca/t1/wds/", "https://www.bankofcanada.ca/"
               "valet/docs"),
        queries=("Questrade API", "IBKR Canada", "Wealthsimple Trade", "pine script TSX",
                 "WDS API", "Valet API", "Norbert's gambit"),
        languages=("en", "fr"), access_label="PUBLIC_WITH_TERMS", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="each platform's terms",
        notes="a script's popularity is a popularity signal; its mechanism is what is extracted"),
    source_class(
        "ca_media_en", "Financial Post, BNN Bloomberg and Reuters Canada", layer="media",
        roots=("https://financialpost.com/", "https://www.bnnbloomberg.ca/",
               "https://www.reuters.com/world/americas/"),
        queries=("Bank of Canada", "loonie", "WCS", "tariffs Canada", "TSX", "housing"),
        languages=("en",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="publisher terms; headlines public",
        notes="wire timestamps are the PIT anchor for tariff announcements"),
    source_class(
        "ca_media_fr", "La Presse, Les Affaires and Radio-Canada économie (the French-language "
                       "plane)",
        layer="media",
        roots=("https://www.lapresse.ca/affaires/", "https://www.lesaffaires.com/",
               "https://ici.radio-canada.ca/economie"),
        queries=("Banque du Canada", "taux directeur", "huard", "droits de douane", "sables "
                 "bitumineux", "Caisse de dépôt", "marché immobilier", "inflation"),
        languages=("fr",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="publisher terms",
        notes="the Caisse de dépôt et placement du Québec is covered here first; native "
              "queries, translation after retrieval"),
    source_class(
        "ca_globe_paywall", "The Globe and Mail (Report on Business)", layer="media",
        roots=("https://www.theglobeandmail.com/business/",),
        queries=("Report on Business", "Bank of Canada", "oil patch"),
        languages=("en",), access_label="LICENSED", credibility="RELIABLE",
        predictive_state="UNTESTED", machine_use_allowed=True,
        licence="subscription; terms forbid scraping",
        notes="REGISTERED, NEVER SCRAPED"),
    source_class(
        "ca_archives", "Bank of Canada archives, archived CANSIM tables and the Wayback Machine",
        layer="archive",
        roots=("https://www.bankofcanada.ca/about/corporate-governance/archives/",
               "https://www150.statcan.gc.ca/n1/en/type/data", "https://web.archive.org/"),
        queries=("archived table", "CANSIM", "historical monetary policy", "archived forum",
                 "table archivée", "archives"),
        languages=("en", "fr"), access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="open government / Wayback terms",
        notes="the pre-2017 noon exchange rate and the 10:00 ET announcement era live here"),
    source_class(
        "ca_physical_flows", "Pipeline, port, grain and power counts: CER throughput, Enbridge "
                             "apportionment, AER production, Port of Vancouver, the Canadian "
                             "Grain Commission, AESO",
        layer="physical_economy",
        roots=("https://www.cer-rec.gc.ca/en/data-analysis/energy-commodities/crude-oil-"
               "petroleum-products/statistics/", "https://www.portvancouver.com/about-us/"
               "statistics/", "https://www.grainscanada.gc.ca/en/grain-research/statistics/",
               "http://ets.aeso.ca/"),
        queries=("pipeline throughput", "crude by rail", "port statistics", "weekly grain "
                 "exports", "supply and demand report", "débit des pipelines", "exportations "
                 "hebdomadaires de grains"),
        languages=("en", "fr"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="open government / operator statistics",
        notes="COUNTED: barrels moved, tonnes shipped, megawatts generated"),
    source_class(
        "ca_ngx_argus", "NGX and Argus (the licensed WCS and AECO daily assessments)",
        layer="physical_economy",
        roots=("https://www.argusmedia.com/en/crude-oil/argus-crude",),
        queries=("WCS Hardisty assessment", "AECO daily index"),
        languages=("en",), access_label="LICENSED", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", machine_use_allowed=True,
        licence="commercial; redistribution and machine extraction forbidden",
        notes="REGISTERED, NEVER SCRAPED: the Alberta weekly series is the free echo"),
    source_class(
        "ca_source_graph", "What the other nine cite: the Bank's related-research links, RePEc "
                           "Canada, the r/CanadianInvestor wiki, bank-economics blogrolls",
        layer="source_graph",
        roots=("https://ideas.repec.org/", "https://www.reddit.com/r/CanadianInvestor/wiki/",
               "https://www.bankofcanada.ca/research/"),
        queries=("cited by", "related research", "wiki resources", "further reading",
                 "liens connexes", "lectures complémentaires"),
        languages=("en", "fr"), access_label="PUBLIC_WITH_TERMS", credibility="UNKNOWN",
        predictive_state="UNTESTED", licence="each host's terms",
        notes="the expansion edges; no fixed source list"),
)
LAYER_ABSENCES: dict[str, str] = {}

# --------------------------------------------------------------------------- datasets
DATASETS: tuple[dict[str, Any], ...] = (
    {"name": "Bank of Canada rate announcements and MPR projections", "source": "Bank of Canada",
     "coverage": "2000 onward (fixed dates)", "frequency": "8 per year",
     "publication_lag_days": 0.0, "revisions": "never revised", "licence": "free, public",
     "history_from": "2000-11", "pit_feasible": True,
     "assets": ("USDCAD", "CADJPY", "CA60", "EURCAD"),
     "mechanism_families": ("policy_surprise", "event_reaction", "forward_guidance"),
     "how_to_fetch": "bankofcanada.ca press releases (09:45 ET stamp); Valet V39079 for the rate"},
    {"name": "BAX/CORRA-implied policy path", "source": "Montreal Exchange settlements",
     "coverage": "1988 onward (BAX)", "frequency": "daily", "publication_lag_days": 0.0,
     "revisions": "settlements final", "licence": "free end-of-day", "history_from": "1988-04",
     "pit_feasible": False, "assets": ("USDCAD", "CADJPY"),
     "mechanism_families": ("policy_surprise",),
     "how_to_fetch": "m-x.ca daily statistics. PIT IS PARTIAL: the 09:40 ET pre-announcement "
                     "snapshot must be captured live; a meeting without it is UNMEASURED"},
    {"name": "Labour Force Survey (first print)", "source": "Statistics Canada",
     "coverage": "1976 onward", "frequency": "monthly", "publication_lag_days": 7.0,
     "revisions": "seasonally adjusted series re-estimated annually", "licence": "Open Licence",
     "history_from": "1976-01", "pit_feasible": True,
     "assets": ("USDCAD", "CA60", "CADJPY"), "mechanism_families": ("event_reaction",
                                                                   "release_collision"),
     "how_to_fetch": "WDS table 14-10-0287; the 08:30 ET embargo is the event time"},
    {"name": "Consumer Price Index with the Bank's core measures", "source": "Statistics Canada",
     "coverage": "1914 onward", "frequency": "monthly", "publication_lag_days": 18.0,
     "revisions": "not revised", "licence": "Open Licence", "history_from": "1949-01",
     "pit_feasible": True, "assets": ("USDCAD", "CADJPY", "CA60"),
     "mechanism_families": ("event_reaction", "macro_condition"),
     "how_to_fetch": "WDS table 18-10-0004 and 18-10-0256 (core measures)"},
    {"name": "WCS-WTI differential (Alberta weekly; licensed daily)", "source": "Alberta Energy",
     "coverage": "2005 onward", "frequency": "weekly", "publication_lag_days": 7.0,
     "revisions": "not revised", "licence": "Open Government Licence - Alberta",
     "history_from": "2005-01", "pit_feasible": True,
     "assets": ("USDCAD", "CA60", "XTIUSD"), "mechanism_families": ("terms_of_trade",
                                                                   "takeaway_constraint"),
     "how_to_fetch": "economicdashboard.alberta.ca oil-prices (CSV export)"},
    {"name": "Enbridge Mainline apportionment by month", "source": "Enbridge",
     "coverage": "2010 onward", "frequency": "monthly", "publication_lag_days": 0.0,
     "revisions": "not revised", "licence": "public company notice", "history_from": "2010-01",
     "pit_feasible": True, "assets": ("USDCAD", "XTIUSD", "CA60"),
     "mechanism_families": ("takeaway_constraint", "calendar_flow"),
     "how_to_fetch": "enbridge.com mainline-apportionment page; archived notices via Wayback"},
    {"name": "AER ST3 crude and bitumen production", "source": "Alberta Energy Regulator",
     "coverage": "1990 onward", "frequency": "monthly", "publication_lag_days": 60.0,
     "revisions": "revised for two months", "licence": "Open Government Licence - Alberta",
     "history_from": "1990-01", "pit_feasible": True, "assets": ("USDCAD", "XTIUSD"),
     "mechanism_families": ("physical_volume", "shut_in"),
     "how_to_fetch": "aer.ca statistical reports ST3 (CSV)"},
    {"name": "CWFIS daily hotspots and fire danger", "source": "Natural Resources Canada",
     "coverage": "2003 onward", "frequency": "daily", "publication_lag_days": 0.0,
     "revisions": "not revised", "licence": "Open Government Licence - Canada",
     "history_from": "2003-01", "pit_feasible": True, "assets": ("XTIUSD", "USDCAD", "CA60"),
     "mechanism_families": ("weather_shock", "shut_in"),
     "how_to_fetch": "cwfis.cfs.nrcan.gc.ca datamart (daily hotspot shapefiles/CSV)"},
    {"name": "CFTC COT -- CME Canadian dollar (6C)", "source": "CFTC",
     "coverage": "1986 onward", "frequency": "weekly", "publication_lag_days": 3.0,
     "revisions": "rare", "licence": "public domain", "history_from": "1986-01",
     "pit_feasible": True, "assets": ("USDCAD",),
     "mechanism_families": ("positioning_extreme", "positioning_unwind"),
     "how_to_fetch": "cftc.gov history files; usable from Friday 15:30 ET"},
    {"name": "Bank of Canada Commodity Price Index (BCPI)", "source": "Bank of Canada",
     "coverage": "1972 onward", "frequency": "weekly", "publication_lag_days": 3.0,
     "revisions": "weights re-based", "licence": "free, public", "history_from": "1972-01",
     "pit_feasible": True, "assets": ("USDCAD", "AUDCAD", "CA60"),
     "mechanism_families": ("terms_of_trade",),
     "how_to_fetch": "Valet group BCPI (weekly)"},
    {"name": "CREA existing home sales and MLS HPI", "source": "CREA",
     "coverage": "2005 onward (HPI)", "frequency": "monthly", "publication_lag_days": 15.0,
     "revisions": "seasonally adjusted series revised", "licence": "public summary; detail "
                                                                   "licensed",
     "history_from": "2005-01", "pit_feasible": True, "assets": ("USDCAD", "CA60"),
     "mechanism_families": ("macro_condition", "household_leverage"),
     "how_to_fetch": "creastats.crea.ca (monthly release, mid-month)"},
    {"name": "US tariff actions affecting Canada (event ledger)", "source": "Federal Register / "
                                                                             "Finance Canada",
     "coverage": "2018 onward (232/301 era; 2025 IEEPA era)", "frequency": "irregular",
     "publication_lag_days": 0.0, "revisions": "amended by later actions", "licence": "public",
     "history_from": "2018-03", "pit_feasible": True, "assets": ("USDCAD", "CA60", "XALUSD"),
     "mechanism_families": ("policy_shock", "event_reaction"),
     "how_to_fetch": "federalregister.gov documents search 'Canada'; canada.ca countermeasures "
                     "page; each action carries announcement and effective dates"},
    {"name": "Canadian Grain Commission weekly exports and StatCan crop production",
     "source": "CGC / StatCan", "coverage": "1990 onward", "frequency": "weekly / 3 per year",
     "publication_lag_days": 7.0, "revisions": "crop estimates revised", "licence": "open",
     "history_from": "1990-08", "pit_feasible": True, "assets": ("WHEAT", "USDCAD"),
     "mechanism_families": ("supply_surprise", "seasonal"),
     "how_to_fetch": "grainscanada.gc.ca statistics; WDS table 32-10-0359"},
)

# --------------------------------------------------------------------------- actors
ACTORS: tuple[dict[str, Any], ...] = (
    {"name": "Bank of Canada Governing Council",
     "holds": "the overnight target, settlement balances remunerated at the target, and a "
              "balance sheet that ran off from 2022 and resumed routine purchases in 2025",
     "forced_to": ("decide on eight fixed dates and publish at 09:45 ET", "publish a quarterly "
                   "projection in the MPR", "publish a Summary of Deliberations two weeks "
                   "later", "renew the inflation-target agreement every five years"),
     "when": "09:45 ET on announcement Wednesdays (14:45 UTC EST / 13:45 UTC EDT); MPR "
             "presser 10:30 ET",
     "information": ("the StatCan dataset before the market", "the Business Outlook Survey "
                     "liaison", "the banks' supervisory data via OSFI"),
     "constraints": ("the 2% target", "a household debt ratio near 180% of income with a "
                     "five-year mortgage renewal wall in 2025-2026", "the exchange rate's "
                     "pass-through to a small open economy", "the Fed's path"),
     "instruments": ("USDCAD", "CADJPY", "EURCAD", "CA60"),
     "counterparties": ("the Lynx participants holding settlement balances", "the federal "
                        "government as its banker", "the Fed via the swap line"),
     "observables": ("the announcement text diff", "the BAX-implied rate before and after",
                     "the MPR projection revision", "the deliberations' dissent language"),
     "impact": "reprices the CAD short-rate path in seconds; the currency move is proportional "
               "to the surprise against BAX and to the Canada-US differential's change",
     "persistence": "the level effect persists to the next meeting; the excess move decays in "
                    "hours",
     "falsifier": "the same window on the eight nearest non-announcement Wednesdays",
     "notes": "the 2020 intermeeting cuts are their own class"},
    {"name": "The oil sands producers (as one aggregate actor)",
     "holds": "about 3.3 million barrels a day of bitumen and synthetic crude, sold at WCS",
     "forced_to": ("ship on whatever pipe space apportionment leaves", "rail the remainder or "
                   "store it", "shut in when wildfire threatens sites", "hedge in the NYMEX "
                   "strip at WTI and eat the differential"),
     "when": "monthly on apportionment notices; daily in the wildfire season (May-August); "
             "quarterly in aggregate hedge disclosures",
     "information": ("their own production and rail bookings",),
     "constraints": ("pipeline takeaway (Mainline, TMX, Keystone)", "rail economics at about "
                     "$15-20/bbl", "the Alberta royalty formula tied to WTI", "site safety"),
     "instruments": ("USDCAD", "CA60", "XTIUSD", "XBRUSD"),
     "counterparties": ("PADD 2 and PADD 3 refiners", "Enbridge", "the Alberta treasury"),
     "observables": ("the WCS differential", "apportionment", "AER production", "CWFIS "
                     "hotspots", "the COT producer/merchant net in CL"),
     "impact": "a differential blow-out cuts Canadian export receipts without moving WTI; the "
               "loonie and the TSX energy weight price the differential, not the flat price",
     "persistence": "weeks to months (takeaway) or days (a shut-in)",
     "falsifier": "the same USDCAD response to a WTI move in months when the differential was "
                  "at its five-year median: if it matches the wide-differential months, the "
                  "differential is not the mechanism",
     "notes": "AGGREGATE: no producer is a symbol here; the majors are event-lane instruments"},
    {"name": "Enbridge Mainline (the pipeline operator)",
     "holds": "the largest crude export system in North America and its monthly nomination "
              "process",
     "forced_to": ("apportion nominations pro rata when they exceed capacity", "publish the "
                   "apportionment percentage monthly"),
     "when": "the last week of each month for the following month",
     "information": ("shipper nominations before publication",),
     "constraints": ("physical capacity", "CER tolling decisions", "maintenance"),
     "instruments": ("USDCAD", "XTIUSD", "CA60"),
     "counterparties": ("the producers", "US refiners", "TMX as the alternative"),
     "observables": ("the apportionment notice", "CER throughput"),
     "impact": "apportionment above zero strands barrels in Alberta: the differential widens "
               "and stays wide until capacity clears",
     "persistence": "months",
     "falsifier": "a differential move of equal size in months with zero apportionment and no "
                  "outage",
     "notes": "the May 2024 TMX start is the era boundary: apportionment fell and the "
              "differential narrowed"},
    {"name": "US refiners in PADD 2 (the WCS buyers)",
     "holds": "heavy-crude coking capacity in the Midwest and the Gulf",
     "forced_to": ("buy the heavy barrel the cokers were built for", "cut runs in turnaround "
                   "season"),
     "when": "spring and autumn turnarounds; the EIA Wednesday",
     "information": ("their own run plans",),
     "constraints": ("coker configuration", "the tariff regime on Canadian energy"),
     "instruments": ("XTIUSD", "USDCAD"),
     "counterparties": ("the oil sands producers", "the Mainline"),
     "observables": ("PADD 2 refinery utilisation", "PADD 2 crude imports from Canada"),
     "impact": "a Midwest turnaround widens the differential from the demand side",
     "persistence": "weeks",
     "falsifier": "the differential's seasonal in years with no turnaround clustering",
     "notes": "the buyer side of CA-C"},
    {"name": "The US administration (tariff authority)",
     "holds": "Section 232, 301 and IEEPA tariff powers over Canadian goods",
     "forced_to": ("publish each action in the Federal Register with an effective date",
                   "review USMCA on its statutory schedule (2026)"),
     "when": "announcement dates; effective dates; exemption dates",
     "information": ("its own intentions",),
     "constraints": ("USMCA", "court challenges", "the domestic price of gasoline and "
                     "aluminium"),
     "instruments": ("USDCAD", "CA60", "XALUSD", "XTIUSD"),
     "counterparties": ("Finance Canada (countermeasures)", "Canadian exporters"),
     "observables": ("the Federal Register document", "the countermeasure list", "the "
                     "customs collections"),
     "impact": "an announcement moves USDCAD within minutes; the effective date moves the "
               "trade print months later; the two are separate events",
     "persistence": "announcement: hours; regime: quarters",
     "falsifier": "the same USDCAD move on days with tariff HEADLINES but no Federal Register "
                  "action -- if equal, the market prices talk, not the rule",
     "notes": "an external actor with a calendar; CA-D"},
    {"name": "The Maple 8 pension funds and their currency overlays",
     "holds": "about C$2trn with large foreign allocations and declared hedge ratios",
     "forced_to": ("rebalance the hedge at month end", "sell USD after a US equity rally to "
                   "restore the ratio"),
     "when": "the last two sessions of the month at the WMR fix",
     "information": ("the month's US equity return, which is public",),
     "constraints": ("the policy hedge ratio", "the investment committee's calendar"),
     "instruments": ("USDCAD", "EURCAD", "CADJPY"),
     "counterparties": ("the fix", "dealers"),
     "observables": ("the sell-side rebalance estimate", "the fix-window volume"),
     "impact": "sign set by the offshore return; an unconditional month-end study averages "
               "it to zero",
     "persistence": "two sessions",
     "falsifier": "the unconditional vs the signed month-end return",
     "notes": "CA-H; the same mechanism as Australia's super funds"},
    {"name": "The Big Six banks",
     "holds": "the mortgage book, NHA MBS issuance and the CAD funding market",
     "forced_to": ("reprice variable-rate mortgages on every announcement", "issue covered "
                   "bonds and NHA MBS on schedule", "meet OSFI's stress test"),
     "when": "announcement days; the five-year renewal wave of 2025-2026",
     "information": ("their own renewal schedule",),
     "constraints": ("OSFI B-20", "the domestic stability buffer", "the renewal wall"),
     "instruments": ("CA60", "USDCAD"),
     "counterparties": ("households", "CMHC", "foreign covered-bond buyers"),
     "observables": ("bank funding spreads", "the arrears rate", "CMHC renewal statistics"),
     "impact": "the transmission from the policy rate to households is faster than in the US "
               "because terms are five years, not thirty; the Bank's constraint is the banks'",
     "persistence": "years",
     "falsifier": "the same rate-to-consumption pass-through in the US, where it should be "
                  "slower",
     "notes": "the banks are 30% of CA60; a single bank is an event-lane instrument"},
    {"name": "Canadian households (the mortgage renewal wall)",
     "holds": "C$2.2trn of mortgages, most on five-year terms originated at 2020-2021 rates",
     "forced_to": ("renew at the prevailing rate on the term's end", "cut consumption to "
                   "service the reset"),
     "when": "2025-2026 for the pandemic-era originations",
     "information": ("their own renewal date",),
     "constraints": ("the stress test", "income"),
     "instruments": ("USDCAD", "CA60"),
     "counterparties": ("the banks", "CMHC"),
     "observables": ("CMHC and Bank renewal-share statistics", "retail sales", "arrears"),
     "impact": "the renewal wall is the Bank's stated reason for cutting faster than the Fed; "
               "the Canada-US differential is its price",
     "persistence": "quarters",
     "falsifier": "the differential's move on Bank cuts in years with no renewal wall (2015)",
     "notes": "CA-I"},
    {"name": "Statistics Canada",
     "holds": "the release calendar and the survey designs",
     "forced_to": ("release at 08:30 ET on the published date", "publish the LFS on the first "
                   "Friday in most months"),
     "when": "08:30 ET",
     "information": ("the data before the market",),
     "constraints": ("the release calendar", "the sample size of the LFS"),
     "instruments": ("USDCAD", "CA60", "CADJPY"),
     "counterparties": ("the market",),
     "observables": ("the release calendar's collisions with BLS", "the first print vs "
                     "consensus"),
     "impact": "the collision with NFP makes the USDCAD response a two-surprise mixture",
     "persistence": "hours",
     "falsifier": "the LFS response on the months it did NOT coincide with payrolls",
     "notes": "CA-B"},
    {"name": "Prairie farmers, the Canadian Grain Commission and the grain handlers",
     "holds": "the wheat, canola and pulse crops and their export logistics through Vancouver "
              "and Thunder Bay",
     "forced_to": ("ship on the railways' allocation", "sell into the harvest", "report weekly "
                   "exports"),
     "when": "harvest (August-October); the StatCan crop production reports; weekly CGC data",
     "information": ("field conditions",),
     "constraints": ("rail capacity", "the Port of Vancouver", "China's canola tariffs"),
     "instruments": ("WHEAT", "USDCAD"),
     "counterparties": ("the railways", "export buyers (China, Japan, Mexico)"),
     "observables": ("CGC weekly exports", "StatCan crop production", "rail car orders"),
     "impact": "a Canadian crop surprise moves world wheat through export availability; "
               "canola's price is UNMEASURED here",
     "persistence": "weeks",
     "falsifier": "the WHEAT response on StatCan crop-report days vs USDA-only days",
     "notes": "CA-K"},
    {"name": "Gold and base-metal miners (the TSX materials weight)",
     "holds": "about 12% of the S&P/TSX 60 in materials, dominated by gold producers",
     "forced_to": ("mark reserves and hedge books to the LBMA price", "issue equity in gold "
                   "rallies"),
     "when": "the LBMA PM fix; quarterly results (event lane)",
     "information": ("their own cost curves",),
     "constraints": ("all-in sustaining cost", "hedge covenants"),
     "instruments": ("CA60", "XAUUSD", "XAGUSD", "XCUUSD", "XNIUSD"),
     "counterparties": ("bullion banks", "ETF flows"),
     "observables": ("the materials weight", "XAUUSD"),
     "impact": "CA60's gold beta is a composition fact; a gold rally lifts the index without "
               "touching the loonie",
     "persistence": "same day",
     "falsifier": "the same gold beta in US500, which has no comparable materials weight",
     "notes": "CA-J; aggregate only"},
    {"name": "The Alberta treasury (royalties and the provincial budget)",
     "holds": "the royalty formula on bitumen tied to WTI and the differential",
     "forced_to": ("publish a WTI and WCS assumption in the February budget", "run a surplus or "
                   "deficit with the price"),
     "when": "the February budget; quarterly fiscal updates",
     "information": ("its own royalty receipts",),
     "constraints": ("the royalty formula", "the Heritage Fund rules"),
     "instruments": ("USDCAD", "CA60"),
     "counterparties": ("the producers", "bond investors"),
     "observables": ("the budget's price assumptions", "quarterly royalty receipts"),
     "impact": "a fiscal object that turns the differential into a public number",
     "persistence": "annual",
     "falsifier": "n/a as a price mechanism; the assumption is an input, and the falsifier is "
                  "that the currency does not react to the budget's assumption revision",
     "notes": "a published input for CA-C"},
    {"name": "LNG Canada and the Montney gas producers",
     "holds": "Kitimat's first export train (in service 2025) and the AECO-priced gas behind it",
     "forced_to": ("feed the plant at contracted volumes", "sell the remainder at AECO's "
                   "takeaway-set discount to Henry Hub"),
     "when": "since the first cargo in mid-2025; monthly export statistics",
     "information": ("nominations",),
     "constraints": ("pipeline capacity to the coast", "storage"),
     "instruments": ("XNGUSD", "USDCAD", "USDJPY"),
     "counterparties": ("Japanese and Korean buyers", "US Pacific Northwest"),
     "observables": ("CER gas export data", "AECO basis (licensed daily; public monthly)"),
     "impact": "the AECO discount narrows structurally; Henry Hub loses a marginal Canadian "
               "supply and gains a competitor in the Pacific",
     "persistence": "structural",
     "falsifier": "the AECO basis in the pre-2025 era, which should be wider",
     "notes": "CA-L; an era boundary"},
    {"name": "Immigration, Refugees and Citizenship Canada (the levels plan)",
     "holds": "the immigration levels plan and the non-permanent resident caps",
     "forced_to": ("publish the plan each autumn", "cap study permits and temporary workers "
                   "(2024-2025 tightening)"),
     "when": "the autumn levels plan; StatCan quarterly population estimates",
     "information": ("its own intake",),
     "constraints": ("housing", "politics"),
     "instruments": ("USDCAD", "CA60"),
     "counterparties": ("the housing market", "the Bank's potential-output estimate"),
     "observables": ("StatCan quarterly population growth", "the levels plan"),
     "impact": "population growth of 3% (2023) then a cap: the Bank's potential-growth "
               "assumption moved with it and so did the neutral rate",
     "persistence": "years",
     "falsifier": "n/a as a price mechanism; the falsifier is that the currency ignores the "
                  "levels plan's announcement",
     "notes": "CA-M"},
)

# --------------------------------------------------------------------------- domains
DOMAINS: tuple[dict[str, Any], ...] = (
    {"id": "CA-A", "title": "Bank of Canada decisions against the BAX/CORRA strip",
     "objects": ("the eight 09:45 ET announcements", "the MPR presser as a second event",
                 "the deliberations two weeks later", "the intermeeting class"),
     "conditions": ("the surprise in bp against BAX at 09:40 ET", "the Canada-US "
                    "differential's change", "the era", "whether the Fed decided the same week"),
     "instruments": ("USDCAD", "CADJPY", "EURCAD", "CA60"),
     "controls": ("the eight nearest non-announcement Wednesdays", "FOMC days as the 'a "
                  "central bank decided' control", "a placebo surprise from BAX's own noise"),
     "notes": "the 09:45/10:00 ET switch is an intraday era boundary"},
    {"id": "CA-B", "title": "Release collisions: LFS with NFP, CPI, trade with the US trade print",
     "objects": ("the LFS/NFP same-minute months", "the LFS-only months", "CPI-trim and median"),
     "conditions": ("whether the two prints agreed in sign", "the surprise sizes",
                    "the blackout state"),
     "instruments": ("USDCAD", "CA60", "CADJPY"),
     "controls": ("the LFS-only months as the clean sample", "the same minute on non-release "
                  "Fridays", "AUDUSD at the same minute, which sees NFP but not the LFS"),
     "notes": "the collision is the object; attribution to one print is refused"},
    {"id": "CA-C", "title": "The WCS differential and takeaway: apportionment, TMX, wildfires",
     "objects": ("the weekly differential", "apportionment notices", "the TMX in-service "
                 "boundary", "CWFIS hotspots in the oil sands region", "AER production"),
     "conditions": ("the differential's width vs its five-year median", "apportionment above "
                    "zero", "the fire season", "the WTI direction"),
     "instruments": ("USDCAD", "CA60", "XTIUSD", "XBRUSD"),
     "controls": ("USDCAD's WTI beta in narrow-differential months", "NOKJPY/USDNOK's Brent "
                  "beta as the 'another oil currency' control", "randomised notice dates"),
     "notes": "the most Canadian mechanism in the pack"},
    {"id": "CA-D", "title": "The tariff calendar and the trade prints",
     "objects": ("Federal Register actions", "countermeasure announcements", "exemption dates",
                 "the monthly trade print"),
     "conditions": ("announcement vs effective date", "the goods class (energy exempt or not)",
                    "the USMCA review state"),
     "instruments": ("USDCAD", "CA60", "XALUSD", "XTIUSD", "USDMXN"),
     "controls": ("headline days with no action", "USDMXN as the other USMCA currency",
                  "randomised dates"),
     "notes": "the 2025 IEEPA actions are the sample; 2018 steel/aluminium the prior era"},
    {"id": "CA-E", "title": "Two calendars: TSX/NYSE divergence days and the Remembrance closure",
     "objects": ("the divergence table", "Canadian Thanksgiving/Columbus Day", "Remembrance Day",
                 "Boxing Day"),
     "conditions": ("which side is dark", "whether the bond market is also closed"),
     "instruments": ("USDCAD", "CA60", "CADJPY"),
     "controls": ("the same weekday in adjacent weeks", "EURUSD on the same days as the "
                  "'US holiday only' control"),
     "notes": "a one-sided book is a microstructure state, measured, never assumed"},
    {"id": "CA-F", "title": "USDCAD T+1 and the Thursday triple roll",
     "objects": ("the rollover at 17:00 New York", "Thursday vs Wednesday for USDCAD vs the "
                 "crosses", "holiday value dates"),
     "conditions": ("the carry sign", "a US or Canadian holiday inside the value window"),
     "instruments": ("USDCAD", "CADJPY", "EURCAD"),
     "controls": ("EURUSD's Wednesday roll", "randomised weekdays"),
     "notes": "an accounting convention that manufactures a weekday effect if ignored"},
    {"id": "CA-G", "title": "COT 6C positioning extremes",
     "objects": ("leveraged-funds net", "the three-year z-score", "the weekly change"),
     "conditions": ("the extreme percentile", "the era", "the WTI direction"),
     "instruments": ("USDCAD",),
     "controls": ("the look-ahead (Tuesday-aligned) version", "randomised report dates"),
     "notes": "usable from Friday 15:30 ET"},
    {"id": "CA-H", "title": "The pension hedge flow at the month-end fix",
     "objects": ("the last two sessions' fix-window return", "the sign of the month's US "
                 "equity return"),
     "conditions": ("the signed offshore return", "quarter end vs month end"),
     "instruments": ("USDCAD", "EURCAD", "CADJPY"),
     "controls": ("the unconditional month-end return", "AUDUSD's super-fund analogue"),
     "notes": "conditional, never an average"},
    {"id": "CA-I", "title": "Housing, the renewal wall and household leverage",
     "objects": ("CREA sales and HPI", "CMHC renewal statistics", "arrears", "the debt ratio"),
     "conditions": ("the renewal cohort's rate gap", "the Bank's cutting state"),
     "instruments": ("USDCAD", "CA60"),
     "controls": ("the same housing surprise in the US (USDX)", "randomised dates"),
     "notes": "the Bank's constraint made measurable"},
    {"id": "CA-J", "title": "CA60 composition: gold, oil and the banks; the SXF expiry",
     "objects": ("the materials and energy weights", "the SXF third Friday", "the quarterly "
                 "rebalance"),
     "conditions": ("the gold move's size", "the WTI move's size", "expiry week"),
     "instruments": ("CA60", "XAUUSD", "XTIUSD", "US500"),
     "controls": ("US500's gold and oil beta", "non-expiry Fridays"),
     "notes": "composition first; a mystery second"},
    {"id": "CA-K", "title": "Grains and potash: the Prairie crop and its logistics",
     "objects": ("StatCan crop production", "CGC weekly exports", "rail allocation"),
     "conditions": ("the crop surprise", "the harvest window", "China's canola tariff state"),
     "instruments": ("WHEAT", "USDCAD"),
     "controls": ("USDA-only report days", "randomised dates"),
     "notes": "canola is UNMEASURED; wheat is the executable leg"},
    {"id": "CA-L", "title": "AECO, LNG Canada and the Henry Hub transmission",
     "objects": ("the AECO basis", "CER gas exports", "the 2025 first-cargo boundary"),
     "conditions": ("the era", "the storage state"),
     "instruments": ("XNGUSD", "USDCAD", "USDJPY"),
     "controls": ("the pre-2025 basis", "randomised dates"),
     "notes": "an era boundary, measured per era"},
    {"id": "CA-M", "title": "Population growth as the potential-output nowcast",
     "objects": ("StatCan quarterly population estimates", "the levels plan"),
     "conditions": ("the cap state", "the Bank's neutral-rate revision"),
     "instruments": ("USDCAD", "CA60"),
     "controls": ("randomised dates", "the US population print as a null"),
     "notes": "slow; measured at the quarterly horizon"},
)

# --------------------------------------------------------------------------- miners
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    {"name": "ca_boc_surprise_vs_bax", "domain_ids": ("CA-A",), "kind": "event",
     "cadence_s": 86400.0, "steerable": False, "wired": False,
     "entry": "countries.ca.miners:boc_surprise_vs_bax",
     "needs": ("CENTRAL_BANK decision dates", "the BAX-implied rate at 09:40 ET",
               "USDCAD and CA60 M15 bars"),
     "notes": "refuses a verdict when the pre-announcement BAX snapshot is unavailable"},
    {"name": "ca_release_collision", "domain_ids": ("CA-B",), "kind": "event",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.ca.miners:release_collision",
     "needs": ("the StatCan and BLS calendars", "USDCAD M5 bars"),
     "notes": "splits the LFS sample by NFP coincidence before measuring anything"},
    {"name": "ca_wcs_takeaway", "domain_ids": ("CA-C",), "kind": "macro",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.ca.miners:wcs_takeaway",
     "needs": ("the Alberta weekly WCS series", "apportionment notices", "CWFIS hotspots",
               "USDCAD and XTIUSD D1 bars"),
     "notes": "conditions the loonie's WTI beta on the differential's width"},
    {"name": "ca_tariff_event_ledger", "domain_ids": ("CA-D",), "kind": "event",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.ca.miners:tariff_event_ledger",
     "needs": ("the Federal Register ledger", "USDCAD and CA60 M15 bars"),
     "notes": "announcement and effective dates are separate events"},
    {"name": "ca_calendar_divergence", "domain_ids": ("CA-E", "CA-F"), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.ca.miners:calendar_divergence",
     "needs": ("the divergence table", "USDCAD H1 bars"),
     "notes": "measures the one-sided book and the Thursday roll together"},
)
MINER_DOMAINS: dict[str, tuple[str, ...]] = {
    "central_bank_surprise": ("CA-A",), "release_surprise": ("CA-B", "CA-K"),
    "calendar_settlement": ("CA-F", "CA-H"), "holiday_liquidity": ("CA-E",),
    "derivatives_expiry": ("CA-J",), "session_microstructure": ("CA-E", "CA-F"),
    "positioning": ("CA-G",), "carry_funding": ("CA-F",), "corporate_flow": ("CA-H",),
    "institutional_flow": ("CA-H", "CA-I"), "equity_mechanics": ("CA-J",),
    "failure": ("CA-C",), "residual": ("CA-M",), "transfer": ("CA-C", "CA-D"),
    "scouts": ("CA-L",),
}

# --------------------------------------------------------------------------- transmission
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    {"id": "CA-E1", "source": "Bank of Canada surprise vs BAX at 09:40 ET", "target": "USDCAD",
     "targets": ("USDCAD", "CADJPY", "CA60"), "to_country": "us", "sign": "-",
     "mechanism": "a hawkish surprise narrows the Canada-US differential; the loonie bids",
     "horizon": "0 to 60 minutes", "lag_days": 0.0, "actor": "Bank of Canada",
     "constraint": "the 2% target", "flow": "rate-differential repricing",
     "control": "the same window on non-announcement Wednesdays",
     "falsifier": "an equal USDCAD move on a Wednesday with no announcement",
     "evidence": "HYPOTHESIS"},
    {"id": "CA-E2", "source": "WCS-WTI differential widening beyond its five-year median",
     "target": "USDCAD", "targets": ("USDCAD", "CA60"), "to_country": "us", "sign": "+",
     "mechanism": "export receipts fall without WTI moving; the loonie prices the differential",
     "horizon": "1 to 20 sessions", "lag_days": 5.0, "actor": "oil sands producers",
     "constraint": "pipeline takeaway", "flow": "terms-of-trade shock",
     "control": "USDCAD's WTI beta in narrow-differential months",
     "falsifier": "an equal loonie move for an equal WTI move when the differential is narrow",
     "evidence": "HYPOTHESIS"},
    {"id": "CA-E3", "source": "Enbridge apportionment notice above zero", "target": "XTIUSD",
     "targets": ("XTIUSD", "USDCAD"), "to_country": "us", "sign": "+",
     "mechanism": "stranded Alberta barrels tighten PADD 2 supply of heavy crude and back up "
                  "into Cushing's light-heavy spread", "horizon": "1 to 10 sessions",
     "lag_days": 1.0, "actor": "Enbridge", "constraint": "physical capacity",
     "flow": "takeaway into the differential", "control": "months with zero apportionment",
     "falsifier": "an equal WTI move on notice days with zero apportionment",
     "evidence": "HYPOTHESIS"},
    {"id": "CA-E4", "source": "CWFIS hotspot surge in the oil sands region (May-August)",
     "target": "XTIUSD", "targets": ("XTIUSD", "XBRUSD", "USDCAD"), "to_country": "global",
     "sign": "+", "mechanism": "precautionary shut-ins remove hundreds of thousands of barrels "
                               "a day; WTI prices the loss before the AER counts it",
     "horizon": "1 to 5 sessions", "lag_days": 1.0, "actor": "the producers",
     "constraint": "site safety", "flow": "weather into supply",
     "control": "hotspot surges outside the oil sands region",
     "falsifier": "an equal move on fire days far from production",
     "evidence": "HYPOTHESIS"},
    {"id": "CA-E5", "source": "US tariff action on Canadian goods (Federal Register)",
     "target": "USDCAD", "targets": ("USDCAD", "CA60", "XALUSD"), "to_country": "us",
     "sign": "+", "mechanism": "three quarters of exports face a new price; the currency is "
                               "the adjustment valve", "horizon": "0 to 5 sessions",
     "lag_days": 0.0, "actor": "the US administration", "constraint": "USMCA",
     "flow": "policy shock into the terms of trade",
     "control": "headline-only days", "falsifier": "an equal move on headline days with no action",
     "evidence": "HYPOTHESIS"},
    {"id": "CA-E6", "source": "LFS/NFP same-minute collision with opposite signs",
     "target": "USDCAD", "targets": ("USDCAD",), "to_country": "us", "sign": "+/-",
     "mechanism": "two surprises in one minute; the response is a mixture whose weights the "
                  "study estimates", "horizon": "0 to 2 hours", "lag_days": 0.0,
     "actor": "StatCan and BLS", "constraint": "the calendars",
     "flow": "release surprise", "control": "LFS-only months",
     "falsifier": "a response indistinguishable from the LFS-only months",
     "evidence": "HYPOTHESIS"},
    {"id": "CA-E7", "source": "XAUUSD daily move above 2%", "target": "CA60",
     "targets": ("CA60",), "to_country": "global", "sign": "+",
     "mechanism": "the materials weight transmits gold into the index level without the "
                  "currency", "horizon": "same day", "lag_days": 0.0,
     "actor": "gold miners", "constraint": "index composition",
     "flow": "commodity into index", "control": "US500 on the same days",
     "falsifier": "an equal gold beta in US500", "evidence": "HYPOTHESIS"},
    {"id": "CA-E8", "source": "Canadian Thanksgiving / Columbus Day (TSX closed, NYSE open, "
                              "SIFMA closed)", "target": "USDCAD",
     "targets": ("USDCAD", "CA60"), "to_country": "us", "sign": "+/-",
     "mechanism": "a one-sided book: the loonie trades with its cash equity and the US bond "
                  "market dark; range and spread differ measurably",
     "horizon": "the session", "lag_days": 0.0, "actor": "the two exchanges",
     "constraint": "the calendars", "flow": "liquidity state",
     "control": "the adjacent Mondays", "falsifier": "a range and spread equal to adjacent Mondays",
     "evidence": "HYPOTHESIS"},
    {"id": "CA-E9", "source": "Fed-BoC differential widening (Fed hold, BoC cut)",
     "target": "CADJPY", "targets": ("CADJPY", "USDCAD"), "to_country": "jp", "sign": "-",
     "mechanism": "the loonie's carry against the yen compresses; the cross loses its "
                  "carry bid", "horizon": "1 to 20 sessions", "lag_days": 1.0,
     "actor": "the two central banks", "constraint": "their mandates",
     "flow": "carry compression", "control": "AUDJPY on the same dates",
     "falsifier": "an equal CADJPY move when the differential did not change",
     "evidence": "HYPOTHESIS"},
    {"id": "CA-E10", "source": "StatCan crop production report surprise", "target": "WHEAT",
     "targets": ("WHEAT", "USDCAD"), "to_country": "global", "sign": "-",
     "mechanism": "a larger Canadian crop raises exportable supply into the world wheat balance",
     "horizon": "0 to 3 sessions", "lag_days": 0.0, "actor": "StatCan / farmers",
     "constraint": "the report calendar", "flow": "supply estimate",
     "control": "USDA-only report days", "falsifier": "an equal WHEAT move on non-report days",
     "evidence": "HYPOTHESIS"},
    {"id": "CA-E11", "source": "LNG Canada first-cargo era", "target": "XNGUSD",
     "targets": ("XNGUSD", "USDJPY"), "to_country": "jp", "sign": "-",
     "mechanism": "Pacific LNG supply competes with US Gulf cargoes for the same Japanese and "
                  "Korean buyers; Henry Hub loses a marginal export bid",
     "horizon": "structural", "lag_days": 30.0, "actor": "LNG Canada",
     "constraint": "train capacity", "flow": "supply into a shared buyer",
     "control": "the pre-2025 era", "falsifier": "no change in the JKM-Henry Hub link across "
                                                 "the boundary", "evidence": "HYPOTHESIS"},
)

# --------------------------------------------------------------------------- eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    {"name": "the oil-crash cuts and the 0.50% floor", "start": "2015-01-21", "end": "2017-07-11",
     "regime": "two cuts to 0.50% as WTI fell from $100; the loonie re-based to a lower oil beta",
     "markers": ("2015-01-21 the surprise cut", "2016-05 Fort McMurray fire"),
     "why_it_matters": "the era with the widest differentials and the first wildfire shut-in; "
                       "CA-C's prior era", "status": "SETTLED"},
    {"name": "hikes to 1.75% and the pre-pandemic hold", "start": "2017-07-12",
     "end": "2020-03-03",
     "regime": "five hikes to 1.75%, then a hold while the Fed cut",
     "markers": ("2018-10-24 the last hike", "2018 rail-crisis differential at $50"),
     "why_it_matters": "the Q4 2018 differential blow-out is the archetype takeaway shock",
     "status": "SETTLED"},
    {"name": "the effective lower bound and the first QE", "start": "2020-03-04",
     "end": "2022-03-01",
     "regime": "two unscheduled cuts to 0.25%, GoC bond purchases, then run-off from 2022",
     "markers": ("2020-03-13 and 2020-03-27 intermeeting cuts", "2021-10-27 QE ended"),
     "why_it_matters": "surprises near zero by construction; the intermeeting class lives here",
     "status": "SETTLED"},
    {"name": "the hiking cycle to 5.00%", "start": "2022-03-02", "end": "2023-07-12",
     "regime": "425bp in sixteen months including 100bp in July 2022; QT by run-off",
     "markers": ("2022-07-13 the 100bp hike", "2023-06-07 the resumed hike after a pause"),
     "why_it_matters": "the pause-and-resume of 2023 is the cleanest Canadian guidance surprise",
     "status": "SETTLED"},
    {"name": "the plateau at 5.00%", "start": "2023-07-13", "end": "2024-06-04",
     "regime": "unchanged for eleven months; the renewal wall named in every MPR",
     "markers": ("2024-05-01 TMX line fill", "2024-05-27 T+1"),
     "why_it_matters": "two market-design boundaries inside one policy plateau",
     "status": "SETTLED"},
    {"name": "the easing cycle and the tariff era", "start": "2024-06-05", "end": "2026-12-31",
     "regime": "cuts from 5.00% to 2.25% (October 2025); US tariffs from February 2025; LNG "
               "Canada in service; QT ended and routine purchases resumed in 2025",
     "markers": ("2024-06-05 the first cut", "2025-02-01 the first IEEPA tariff order",
                 "2025-06 LNG Canada's first cargo"),
     "why_it_matters": "OPEN: the end date is a placeholder; the tariff regime dominates the "
                       "currency's event class in this era", "status": "OPEN"},
)

ACCESS_CONSTRAINTS: tuple[dict[str, Any], ...] = (
    {"constraint": "no WCS, canola, AECO or Canada bond instrument is quoted by this broker",
     "measured": "data/universe/universe.json holds none of them",
     "consequence": "every Canadian terms-of-trade mechanism terminates in USDCAD, CA60 or a "
                    "crude leg; the differential is an INPUT read from the free Alberta echo"},
    {"constraint": "the BAX/CORRA strip is not quoted here",
     "measured": "no short-rate future in the universe registry",
     "consequence": "the Bank surprise needs a live 09:40 ET snapshot; a meeting without one is "
                    "UNMEASURED, never zero"},
    {"constraint": "CA60 is a broker CFD on the S&P/TSX 60, not the index or the SXF",
     "measured": "universe.json: asset_class Indices",
     "consequence": "the closing-auction print and the SXF opening settlement are external "
                    "references; the CFD tape may carry bars on TSX holidays"},
    {"constraint": "Argus/NGX assessments, the Globe and Mail and paid research letters are "
                   "licensed",
     "measured": "their terms forbid machine extraction",
     "consequence": "registered machine_use_allowed=false; the public echoes are the inputs"},
)
INSTITUTIONAL_FLOW_SOURCES: tuple[str, ...] = (
    "StatCan international transactions in securities (monthly)", "Bank of Canada settlement "
    "balances", "CPPIB/Caisse/OTPP annual reports (hedge ratios)", "CMHC NHA MBS issuance",
    "CFTC 6C COT")
SERIES: dict[str, str] = {
    "CA_POLICY": "BoC Valet:V39079", "CA_CPI": "StatCan:18-10-0004", "CA_LFS": "StatCan:14-10-0287",
    "CA_WCS_DIFF": "Alberta:WCS_minus_WTI", "CA_APPORTIONMENT": "Enbridge:mainline_pct",
    "CA_BCPI": "BoC Valet:BCPI", "CA_COT": "CFTC:6C", "CA_CORRA": "BoC Valet:AVG.INTWO",
}


# --------------------------------------------------------------------------- coverage
def layer_counts(classes: Iterable[Mapping[str, Any]] | None = None) -> dict[str, int]:
    rows = SOURCE_CLASSES if classes is None else classes
    out = dict.fromkeys(SOURCE_LAYERS, 0)
    for sc in rows:
        layer = str(sc.get("layer") or "")
        if layer in out and not str(sc.get("id") or "").startswith("absent_"):
            out[layer] += 1
    return out


def layer_terms() -> dict[str, tuple[str, ...]]:
    out: dict[str, list[str]] = {layer: [] for layer in SOURCE_LAYERS}
    for sc in SOURCE_CLASSES:
        layer = str(sc.get("layer") or "")
        if layer in out:
            out[layer].extend(q for q in sc.get("queries", ()) if q not in out[layer])
    return {k: tuple(v) for k, v in out.items()}


def source_layer_coverage() -> dict[str, Any]:
    counts = layer_counts()
    missing = {layer: str(LAYER_ABSENCES.get(layer, "")) for layer, n in counts.items() if not n}
    return {"code": CODE, "layer_counts": counts,
            "n_layers_covered": sum(1 for n in counts.values() if n),
            "n_sources": len(SOURCE_CLASSES), "missing": missing,
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


# --------------------------------------------------------------------------- assembly
_PACK_FIELDS: tuple[str, ...] = (
    "code", "name", "region_command", "currency", "executable_instruments", "central_bank",
    "fixing_conventions", "settlement_conventions", "exchanges", "holidays_rule",
    "fiscal_year_end", "positioning_sources", "native_languages", "terminology", "source_classes",
    "datasets", "actors", "domains", "custom_miners", "transmission_edges_seed", "policy_eras")


def as_dict() -> dict[str, Any]:
    return {
        "code": CODE, "name": NAME, "region_command": REGION_COMMAND, "currency": CURRENCY,
        "executable_instruments": EXECUTABLE_INSTRUMENTS, "central_bank": CENTRAL_BANK,
        "fixing_conventions": FIXING_CONVENTIONS,
        "settlement_conventions": SETTLEMENT_CONVENTIONS, "exchanges": EXCHANGES,
        "release_classes": RELEASE_CLASSES, "session_windows": SESSION_WINDOWS,
        "holidays_rule": HOLIDAYS_RULE, "fiscal_year_end": FISCAL_YEAR_END,
        "positioning_sources": POSITIONING_SOURCES, "native_languages": NATIVE_LANGUAGES,
        "terminology": TERMINOLOGY, "source_classes": SOURCE_CLASSES,
        "layer_absences": LAYER_ABSENCES, "layer_terms": layer_terms(),
        "source_layer_coverage": source_layer_coverage(), "datasets": DATASETS,
        "actors": ACTORS, "domains": DOMAINS, "custom_miners": CUSTOM_MINERS,
        "miner_domains": MINER_DOMAINS, "transmission_edges_seed": TRANSMISSION_EDGES_SEED,
        "policy_eras": POLICY_ERAS, "transmission_targets": TRANSMISSION_TARGETS,
        "access_constraints": ACCESS_CONSTRAINTS, "region_desk": REGION_DESK,
        "cot_currency": COT_CURRENCY, "export_economy": EXPORT_ECONOMY,
        "retail_leverage_regime": RETAIL_LEVERAGE_REGIME,
        "institutional_flow_sources": INSTITUTIONAL_FLOW_SOURCES, "series": SERIES,
        "mission": MISSION, "calendar_divergences": CALENDAR_DIVERGENCES,
    }


def _source_line(sc: Mapping[str, Any]) -> str:
    return (f"{sc['id']} :: layer={sc['layer']} :: {sc['label']} :: "
            f"roots={'; '.join(sc['roots']) or 'NONE'} :: "
            f"queries={'; '.join(sc['queries']) or 'NONE'} :: "
            f"languages={','.join(sc['languages']) or 'NONE'} :: access={sc['access_label']} :: "
            f"credibility={sc['credibility']} :: predictive={sc['predictive_state']} :: "
            f"machine_use_allowed={sc['machine_use_allowed']} :: licence={sc['licence']}")


def _source_row(sc: Mapping[str, Any]) -> dict[str, Any]:
    return {"id": sc["id"], "layer": sc["layer"], "label": sc["label"], "roots": sc["roots"],
            "languages": sc["languages"], "licence": sc["licence"], "verified": False,
            "query_terms": sc["queries"],
            "notes": (f"access_label={sc['access_label']} | credibility={sc['credibility']} | "
                      f"predictive_state={sc['predictive_state']} | "
                      f"machine_use_allowed={sc['machine_use_allowed']} | {sc['notes']}")}


def lab_kwargs() -> dict[str, Any]:
    data = as_dict()
    real = [s for s in SOURCE_CLASSES if not str(s["id"]).startswith("absent_")]
    data.update({
        "positioning_sources": tuple(str(p["name"]) for p in POSITIONING_SOURCES),
        "custom_miners": tuple(str(m["entry"]) for m in CUSTOM_MINERS),
        "source_classes": tuple(_source_line(s) for s in real),
        "sources": tuple(_source_row(s) for s in real),
        "absent_layers": dict(LAYER_ABSENCES),
    })
    return data


def pack() -> Any:
    data = lab_kwargs()
    try:
        from libs.research import country_lab
    except ImportError:
        return data
    cls = getattr(country_lab, "CountryPack", None)
    if cls is None:
        return data
    try:
        import dataclasses
        names = {f.name for f in dataclasses.fields(cls)}
    except Exception:
        names = set(_PACK_FIELDS)
    try:
        return cls(**{k: v for k, v in data.items() if k in names})
    except (TypeError, ValueError):
        return data
