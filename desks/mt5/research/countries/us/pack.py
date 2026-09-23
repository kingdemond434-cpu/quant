"""UNITED STATES: the venue everyone else transmits INTO, held as its own forced-flow economy.

WHAT THE UNITED STATES IS AS A MARKET MECHANISM, AND WHY IT IS NOT "THE GLOBAL FOREST". Every
other country pack in this directory ends its transmission map on a US instrument -- US500,
UST10Y, XAUUSD, the dollar -- and it would be easy to conclude that the US therefore needs no
pack of its own. That conclusion is exactly backwards: the US has the largest set of SCHEDULED,
COUNTED, PUBLISHED forcings on the desk, and every one of them is a domestic mechanism first.

  1. THE POSITIONING SPINE IS AMERICAN BY VENUE. The CFTC Commitments of Traders report is the
     only free, weekly, trader-category positioning series on the desk, and it exists because the
     contracts (6E, 6J, ES, ZN, GC, CL, ZC, SB...) clear at CME, CBOT, NYMEX, COMEX and ICE US.
     Every currency, index, metal, energy and grain positioning study on this desk is a study of
     an American ledger with a Tuesday snapshot released on Friday. The PIT trap is the same for
     all of them and is declared once, here: the report is THREE DAYS STALE on release.

  2. THE PLUMBING IS A LEDGER, NOT A THEORY. The Treasury General Account, the overnight reverse
     repo facility, reserve balances and SOFR are published DAILY (Fiscal Data, the New York Fed,
     H.4.1). Corporate tax dates (15 April, June, September, December), settlement of the
     quarterly refunding and month-end bill paydowns move reserves by tens of billions on dates
     known a year ahead. That is a calendar mechanism with a counted flow, not a narrative.

  3. THE AUCTIONS ARE A FORCED BID. Primary dealers are OBLIGED to bid at every Treasury auction
     at a pro-rata share; the tail, the stop-through, the bid-to-cover and the indirect share are
     published within two minutes of the 13:00 ET close and are the cleanest supply-shock event
     class in fixed income. UST05Y and UST10Y are the executable legs.

  4. TWO HOLIDAY CALENDARS. The NYSE and the bond market (SIFMA) diverge: Columbus Day and
     Veterans Day close Treasuries with equities open; Good Friday closes equities with the bond
     market open until noon. A single "US holiday" table gets both sides wrong, so this pack
     declares the equity table as the closure table and the bond-only closures beside it.

  5. THE PHYSICAL ECONOMY IS COUNTED WEEKLY. EIA crude and product inventories (Wednesday 10:30
     ET), natural gas storage (Thursday 10:30 ET), USDA export sales (Thursday 08:30 ET), the
     WASDE (monthly, noon ET), NOAA degree days and hurricane outlooks, the Baker Hughes rig count
     (Friday 13:00 ET) and the Port of Los Angeles/Long Beach TEU counts are FREE, SCHEDULED and
     move XTIUSD, XNGUSD, CORN, WHEAT, SOYBEAN and COTTON directly.

  6. DISCLOSURE IS AGGREGATED HERE, NEVER SINGLE-NAME. EDGAR holds the 13F, Form PF and Form 4
     universe; the two-lane order (2026-09-06) forbids hunting a single name statistically, so
     this pack reads SEC filings only as AGGREGATES (13F sector tilts, aggregate insider buying,
     buyback authorisations by month) that move an INDEX, and no share CFD appears anywhere in it.

WHAT IS EXECUTABLE. The dollar index, the four equity indices, the two Treasury CFDs, gold,
silver, WTI, Brent, Henry Hub, the base and precious metals, the grain and soft complex and every
USD major cross are quotable here. What is NOT quotable is named in `TRANSMISSION_TARGETS` with
the symbols its mechanism reaches: fed funds and SOFR futures (the consensus), TIPS (real
yields), the VIX, the 2-year, MBS, RBOB/heating oil cracks, lumber, cattle and hogs.

THE LANGUAGE. English, and the vocabulary is a real barrier: "the dots", "the skip", "the
refunding", "the tail", "the RRP", "quad witching", "the X-date", "WASDE" and "0DTE" are
tokens a screen trained on textbooks reads as noise, and each one names a scheduled mechanism.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

# --------------------------------------------------------------------------- identity
CODE = "us"
NAME = "United States"
REGION_COMMAND = "north_america"
REGION_DESK = "NORTH_AMERICA"
CURRENCY = "USD"
FISCAL_YEAR_END = "09-30"          # the federal fiscal year; the debt-ceiling clock runs on it
NATIVE_LANGUAGES: tuple[str, ...] = ("en-US",)
COT_CURRENCY = "USD"
EXPORT_ECONOMY = "energy_exporter"          # a net energy exporter since 2019; services beside
RETAIL_LEVERAGE_REGIME = "capped"           # CFTC: 50:1 majors, 20:1 others; no retail CFDs
MISSION = ("mine the United States as a domestic forced-flow economy -- the FOMC, the Treasury "
           "plumbing, the auctions, the COT positioning spine, the EIA/USDA/NOAA physical counts "
           "and the exchange calendar -- and hand every other region the dollar leg it transmits "
           "into, measured rather than assumed")

#: Fusion-quotable instruments a US mechanism can reach. No single name anywhere.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "USDX",                                                    # the dollar factor
    "US500", "NAS100", "US30", "US2000",                       # the four index CFDs
    "UST05Y", "UST10Y",                                        # the two Treasury CFDs
    "XAUUSD", "XAGUSD", "XPTUSD", "XPDUSD", "XCUUSD",          # metals
    "XTIUSD", "XBRUSD", "XNGUSD",                              # energy
    "WHEAT", "CORN", "SOYBEAN", "COTTON", "SUGAR",             # the USDA complex
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD",          # the majors
    "AUDUSD", "NZDUSD", "USDMXN", "USDCNH", "USDZAR",          # the dollar crosses
    "GER40", "JPN225",                                         # foreign-index controls
)

#: Instruments this pack's mechanisms are ABOUT that this broker does not quote.
TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "CME 30-day fed funds futures (ZQ) and SOFR futures (SR3)", "venue": "CME",
     "why": "the traded consensus for every FOMC decision; the surprise in US-A is measured in "
            "basis points against the ZQ contract at 13:55 ET, never against a survey median",
     "proxies": ("USDX", "UST05Y", "US500", "USDJPY")},
    {"name": "Treasury Inflation-Protected Securities (the 10-year real yield)",
     "venue": "Treasury / FRB H.15",
     "why": "gold's dominant fundamental is the REAL yield, not the nominal; UST10Y is the "
            "nominal leg and breakevens are the difference nobody quotes here",
     "proxies": ("XAUUSD", "XAGUSD", "UST10Y")},
    {"name": "Cboe VIX index and VIX futures", "venue": "Cboe",
     "why": "the dealer-gamma and vol-target mechanisms in US-F are stated in VIX terms; the "
            "monthly VIX expiry is a Wednesday, 30 days before the third Friday",
     "proxies": ("US500", "NAS100", "US2000")},
    {"name": "2-year Treasury note (the policy-sensitive tenor)", "venue": "Treasury",
     "why": "the FOMC reprices the 2-year first; UST05Y is the nearest executable tenor and the "
            "2s5s slope is UNMEASURED on this box",
     "proxies": ("UST05Y", "USDX")},
    {"name": "RBOB gasoline and ULSD heating oil (the crack spread)", "venue": "NYMEX",
     "why": "refinery economics drive crude demand in the driving and heating seasons; only the "
            "crude legs are quotable",
     "proxies": ("XTIUSD", "XBRUSD")},
    {"name": "Agency MBS (the convexity hedging flow)", "venue": "TBA market",
     "why": "mortgage hedgers extend and shorten duration with rates, amplifying moves in the "
            "belly; UST10Y is where the flow lands",
     "proxies": ("UST10Y",)},
    {"name": "CME live cattle, lean hogs and CME lumber", "venue": "CME",
     "why": "the USDA Cattle on Feed and Hogs and Pigs reports move contracts this broker does "
            "not carry; the grain legs (feed demand) are the executable channel",
     "proxies": ("CORN", "SOYBEAN")},
    {"name": "ICE coffee and cocoa (US-listed softs)", "venue": "ICE US",
     "why": "the COT disaggregated report covers them; the broker quotes Arabica and Robusta "
            "coffee and both cocoas under their own symbols and they are the coffee/cocoa packs' "
            "business, not this one's",
     "proxies": ("SUGAR", "COTTON")},
    {"name": "S&P 500 E-mini (ES) and Nasdaq-100 E-mini (NQ) futures", "venue": "CME",
     "why": "US500 and NAS100 are broker CFDs on the cash indices; the quarterly expiry and the "
            "Special Opening Quotation belong to the futures, and the CFD's overnight session is "
            "the broker's synthetic tape of Globex",
     "proxies": ("US500", "NAS100")},
)

# --------------------------------------------------------------------------- central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "Federal Reserve -- Federal Open Market Committee",
    "short": "FOMC",
    "framework": "dual_mandate",
    "committee": "the FOMC: seven Governors, the New York Fed president and four rotating "
                 "Reserve Bank presidents; twelve votes, nineteen participants in the SEP",
    "policy_instrument": "the target RANGE for the federal funds rate, implemented through "
                         "interest on reserve balances (IORB) and the overnight RRP rate",
    "corridor": "IORB at the top of the range minus 10bp; ON RRP at the bottom plus 0bp; the "
                "Standing Repo Facility at the top of the range",
    "mandate": "maximum employment and stable prices, interpreted as 2% PCE inflation over the "
               "longer run (the 2012 statement, reaffirmed annually in January)",
    "decision_rule": "EIGHT scheduled two-day meetings a year, roughly six weeks apart, ending "
                     "on a Wednesday. The statement is released at 14:00 ET and the Chair's "
                     "press conference begins at 14:30 ET after EVERY meeting (since 2019). "
                     "The Summary of Economic Projections (the dots) accompanies the March, "
                     "June, September and December meetings. Minutes follow three weeks later "
                     "at 14:00 ET on a Wednesday.",
    "decision_calendar_rule": "eight scheduled meetings a year ending on a Wednesday, published "
                              "a year ahead at federalreserve.gov/monetarypolicy/fomccalendars",
    "decision_dates": (
        "2024-01-31", "2024-03-20", "2024-05-01", "2024-06-12", "2024-07-31", "2024-09-18",
        "2024-11-07", "2024-12-18",
        "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18", "2025-07-30", "2025-09-17",
        "2025-10-29", "2025-12-10",
        "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17", "2026-07-29", "2026-09-16",
        "2026-10-28", "2026-12-09"),
    "dates_status": "2024 and 2025: VERIFIED against the Board's published calendar at writing "
                    "(eight meetings each, all held as scheduled; 2024-11-07 was a Thursday "
                    "because of the election). 2026: PUBLISHED CALENDAR as issued by the Board "
                    "in 2025, re-verify against federalreserve.gov before a cell is compiled on "
                    "a 2026 date; any unscheduled decision is its own event class and is never "
                    "pooled with these.",
    "decision_time_utc": "19:00",
    "announce_local": "14:00 America/New_York",
    "announce_utc_dst": "18:00",
    "dst_rule": "America/New_York is EST (UTC-5) from the first Sunday in November to the second "
                "Sunday in March and EDT (UTC-4) otherwise; the statement minute in UTC moves "
                "twice a year and a fixed-UTC window puts a third of the sample in the wrong bar",
    "presser_utc": "19:30",
    "minutes_lag_days": 21,
    "publication_classes": ("statement", "summary_of_economic_projections", "press_conference",
                            "minutes", "beige_book", "H.4.1", "H.8", "H.15",
                            "semiannual_testimony", "transcripts_5y_lag"),
    "policy_rate_series": "FRED:DFEDTARU",
    "expected_rate_series": "CME:ZQ_implied",
    "consensus_proxy": "CME 30-day fed funds futures (ZQ) at 13:55 ET; the FedWatch probability "
                       "is a derived view of the same contract",
    "consensus_proxy_trap": "the ZQ contract settles to the MONTHLY AVERAGE effective rate, so a "
                            "meeting mid-month embeds the days already elapsed at the old rate; "
                            "the implied change must be scaled by days-remaining/days-in-month "
                            "or every surprise is biased toward zero",
    "blackout": "communications blackout from the second Saturday before the meeting to the "
                "Thursday after it -- Fedspeak has a KNOWN silence and a known re-start",
    "balance_sheet": "runoff caps: Treasuries $25bn/month from June 2024 (from $60bn), agency "
                     "MBS $35bn/month; the caps are a scheduled, counted flow",
    "off_cycle": "2020-03-03 and 2020-03-15 were unscheduled cuts; the intermeeting class is "
                 "the single largest USD event and is never pooled with scheduled meetings",
    "other_clocks": (
        {"what": "FOMC minutes", "when_local": "14:00 ET, three weeks after the meeting",
         "when_utc": "19:00", "reference_lag_days": 21},
        {"what": "Beige Book", "when_local": "14:00 ET, two weeks before the meeting",
         "when_utc": "19:00", "reference_lag_days": -14},
        {"what": "H.4.1 (reserves, RRP, SOMA)", "when_local": "16:30 ET Thursday",
         "when_utc": "21:30", "reference_lag_days": 1},
        {"what": "semiannual Monetary Policy Report testimony",
         "when_local": "10:00 ET, February/March and June/July", "when_utc": "15:00",
         "reference_lag_days": 0},
    ),
    "root": "https://www.federalreserve.gov",
}

# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "WM/Refinitiv 16:00 London fix (the USD leg of every cross)",
     "local": "16:00 Europe/London, window 15:57:30-16:02:30", "time_utc": "16:00",
     "time_utc_dst": "15:00", "dst_rule": "GMT/BST",
     "instruments": ("EURUSD", "GBPUSD", "USDJPY", "USDCAD", "AUDUSD"), "window_minutes": 5,
     "why": "the month-end fix is where US asset managers' currency hedges and index funds "
            "transact; the largest scheduled FX flow of the month and the reference for US-N"},
    {"name": "NYSE closing auction (the official close of US500, US30 and US2000)",
     "local": "16:00 America/New_York, MOC/LOC imbalance published from 15:50",
     "time_utc": "21:00", "time_utc_dst": "20:00", "dst_rule": "EST/EDT",
     "instruments": ("US500", "US30", "US2000"), "window_minutes": 10,
     "why": "index funds, leveraged ETFs and month-end rebalances transact HERE; the imbalance "
            "feed at 15:50 is public and the last ten minutes carry a third of daily volume"},
    {"name": "Nasdaq closing cross (the official close of NAS100)",
     "local": "16:00 America/New_York", "time_utc": "21:00", "time_utc_dst": "20:00",
     "dst_rule": "EST/EDT", "instruments": ("NAS100",), "window_minutes": 10,
     "why": "the Nasdaq-100 reconstitution and the quarterly rebalance settle to this print"},
    {"name": "CME equity index futures daily settlement",
     "local": "15:00 America/Chicago (16:00 ET), the fair-value of the last 30 seconds",
     "time_utc": "21:00", "time_utc_dst": "20:00", "dst_rule": "CST/CDT",
     "instruments": ("US500", "NAS100", "US30", "US2000"), "window_minutes": 1,
     "why": "the margin and variation-margin reference; the quarterly expiry settles instead to "
            "the SOQ from constituent OPENING prices on the third Friday"},
    {"name": "NYMEX WTI and Henry Hub daily settlement",
     "local": "14:28-14:30 America/New_York volume-weighted", "time_utc": "19:30",
     "time_utc_dst": "18:30", "dst_rule": "EST/EDT", "instruments": ("XTIUSD", "XNGUSD"),
     "window_minutes": 2,
     "why": "the settlement window is where producer hedges and index rolls are executed; the "
            "post-settlement tape is a different, thinner market"},
    {"name": "LBMA gold PM auction (the reference for XAUUSD marks)",
     "local": "15:00 Europe/London", "time_utc": "15:00", "time_utc_dst": "14:00",
     "dst_rule": "GMT/BST", "instruments": ("XAUUSD", "XAGUSD"), "window_minutes": 15,
     "why": "COMEX is the price-discovery venue but the London auction is the benchmark the "
            "ETFs and the miners mark to"},
    {"name": "Treasury auction close (the 13:00 ET bid deadline)",
     "local": "13:00 America/New_York; results within about two minutes", "time_utc": "18:00",
     "time_utc_dst": "17:00", "dst_rule": "EST/EDT", "instruments": ("UST10Y", "UST05Y"),
     "window_minutes": 5,
     "why": "the tail, the stop-through, the bid-to-cover and the indirect share are published "
            "at once; US-C's event minute"},
    {"name": "Treasury 15:00 ET marks (the H.15 constant-maturity reference)",
     "local": "15:00 America/New_York", "time_utc": "20:00", "time_utc_dst": "19:00",
     "dst_rule": "EST/EDT", "instruments": ("UST10Y", "UST05Y"), "window_minutes": 5,
     "why": "the daily yields every macro study uses are the 15:00 marks, not the close; a bar "
            "aligned to 17:00 measures a different quantity"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "US cash equities T+1 (since 2024-05-28)", "kind": "weekday", "convention": "T+1",
     "roll": "next", "instruments": ("US500", "NAS100", "US30", "US2000"),
     "why": "the move from T+2 to T+1 on 2024-05-28 is an ERA boundary for every index-flow "
            "study: the day of a rebalance and the day its cash settles are no longer two days "
            "apart, and pre-2024 lag structure does not transfer"},
    {"name": "Treasury coupon and principal payment dates", "kind": "day_of_month",
     "days": (15,), "roll": "next", "window_utc": ("13:00", "21:00"),
     "instruments": ("UST10Y", "UST05Y"),
     "why": "coupons and maturities pay on the 15th and the last day of the month; the "
            "reinvestment flow and the reserve drain land the same day"},
    {"name": "Treasury month-end payment and refunding settlement", "kind": "month_end",
     "roll": "next", "window_utc": ("13:00", "21:00"), "instruments": ("UST10Y", "UST05Y"),
     "why": "the 2/5/7-year auctions settle at month end and the refunding on the 15th; "
            "settlement is when the TGA fills and reserves drain, not the auction day"},
    {"name": "corporate tax dates (reserve drains into the TGA)", "kind": "day_of_month",
     "days": (15,), "months": (4, 6, 9, 12), "roll": "next", "window_utc": ("13:00", "21:00"),
     "instruments": ("US500", "USDX", "UST05Y"),
     "why": "quarterly estimated corporate taxes drain tens of billions of reserves on a known "
            "date; April adds the individual filing deadline and is the largest drain of the "
            "year -- the TGA rises, RRP and repo tighten, and the dollar's funding leg bids"},
    {"name": "quarterly index futures and options expiry (quad witching)", "kind": "weekday",
     "weekday": 4, "week_of_month": 3, "months": (3, 6, 9, 12), "roll": "previous",
     "window_utc": ("14:30", "21:00"), "instruments": ("US500", "NAS100", "US30", "US2000"),
     "why": "index futures, index options, single-stock options and ETF options expire "
            "together on the third Friday of the quarter month; the S&P quarterly rebalance is "
            "effective after that close, so expiry and rebalance are the SAME day here, unlike "
            "Australia where they are two days apart"},
    {"name": "monthly options expiry (opex)", "kind": "weekday", "weekday": 4,
     "week_of_month": 3, "roll": "previous", "window_utc": ("14:30", "21:00"),
     "instruments": ("US500", "NAS100"),
     "why": "dealer gamma is concentrated in the monthly strikes; the week after opex is when "
            "the pin releases -- the hypothesis US-F tests, never assumes"},
    {"name": "month-end pension and asset-allocation rebalance", "kind": "month_end",
     "roll": "previous", "window_utc": ("18:00", "21:00"),
     "instruments": ("US500", "UST10Y", "EURUSD", "USDJPY"),
     "why": "the flow's SIGN is set by the month's equity-minus-bond return: after an equity "
            "rally the rebalancer SELLS equities and buys duration; an unconditional month-end "
            "study averages it to zero, and this pack conditions it"},
    {"name": "US fiscal year end (30 September) and the debt-ceiling clock",
     "kind": "fiscal_year_end", "roll": "previous", "window_utc": ("13:00", "21:00"),
     "instruments": ("UST05Y", "UST10Y", "USDX"),
     "why": "appropriations lapse at midnight on 30 September; a shutdown delays BLS/BEA "
            "releases and the release surprise class simply STOPS for its duration, which is a "
            "measured data gap and never a zero"},
    {"name": "FX spot T+2, USDCAD T+1, Wednesday triple swap", "kind": "weekday",
     "convention": "T+2 value except USDCAD (T+1); rollover at 17:00 New York",
     "roll": "next", "instruments": ("EURUSD", "USDJPY", "USDCAD", "AUDUSD"),
     "why": "the Wednesday roll carries three days of carry into one bar for T+2 pairs and the "
            "THURSDAY roll does so for USDCAD; a carry study that ignores the difference invents "
            "a weekday effect out of the accounting"},
)

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "New York Stock Exchange and NYSE Arca", "index_symbols": ("US500", "US30", "US2000"),
     "open_local": "09:30 America/New_York", "close_local": "16:00",
     "open_utc": "14:30", "close_utc": "21:00", "dst_rule": "EST/EDT, subtract one hour on EDT",
     "auction": "opening auction 09:30; closing auction 16:00 with imbalances from 15:50",
     "expiry_rule": "n/a (cash market); ETF options expire on the third Friday",
     "holidays": "the NYSE holiday calendar; early close at 13:00 on the day after Thanksgiving, "
                 "Christmas Eve and (some years) 3 July",
     "notes": "the S&P 500 quarterly rebalance is effective after the close of the third Friday "
              "of March, June, September and December; the Russell reconstitution lands on the "
              "last Friday of June and is the largest single-day volume of the year for US2000"},
    {"name": "Nasdaq", "index_symbols": ("NAS100",),
     "open_local": "09:30", "close_local": "16:00", "open_utc": "14:30", "close_utc": "21:00",
     "dst_rule": "EST/EDT", "auction": "opening and closing crosses",
     "expiry_rule": "n/a (cash market)",
     "holidays": "the NYSE calendar",
     "notes": "the Nasdaq-100 annual reconstitution is announced the second Friday of December "
              "and effective before the open of the Monday after the third Friday"},
    {"name": "CME Group (CME, CBOT, NYMEX, COMEX)",
     "index_symbols": ("US500", "NAS100", "US30", "US2000"),
     "open_local": "Globex 18:00 America/Chicago Sunday to 17:00 Friday, daily halt 16:00-17:00",
     "close_local": "17:00 (settlement 15:00 for equity indices)",
     "open_utc": "23:00", "close_utc": "22:00", "dst_rule": "CST/CDT",
     "auction": "n/a; the daily settlement is a VWAP window",
     "expiry_rule": "ES/NQ/YM/RTY: third Friday of March, June, September, December, cash "
                    "settled to the SOQ from constituent OPENS. ZN/ZF: last business day of the "
                    "contract month, physically delivered; first notice matters. CL: three "
                    "business days before the 25th of the month before delivery. NG: three "
                    "business days before the first of the delivery month. GC: third-last "
                    "business day of the contract month. ZC/ZW/ZS: the business day before the "
                    "15th of the contract month.",
     "holidays": "the CME holiday calendar (abbreviated sessions on US holidays; Globex often "
                 "OPEN on NYSE holidays with an early close)",
     "notes": "the CFD tape here is the broker's synthetic Globex; the daily 16:00-17:00 CT halt "
              "is a real gap in it and an hourly bar that spans it is two markets"},
    {"name": "ICE Futures US (softs) and ICE (Brent, USDX)", "index_symbols": ("USDX",),
     "open_local": "USDX 20:00-17:00 ET next day; softs 03:30/04:00-13:30/14:20 ET",
     "close_local": "varies by contract", "open_utc": "01:00", "close_utc": "22:00",
     "dst_rule": "EST/EDT", "auction": "n/a",
     "expiry_rule": "USDX: the third Wednesday of March, June, September, December. Sugar No. "
                    "11: the last business day of the month before delivery. Cotton No. 2: "
                    "seventeen business days before the end of the spot month. Brent: the last "
                    "business day of the second month before delivery.",
     "holidays": "the ICE US calendar",
     "notes": "the sugar and cotton expiries are where the physical and the paper markets "
              "meet; the broker's SUGAR and COTTON CFDs roll on the broker's schedule, which is "
              "declared UNMEASURED here until read from the swap table"},
    {"name": "Cboe Options Exchange", "index_symbols": ("US500",),
     "open_local": "09:30 (SPX also 20:15-09:15 global trading hours)", "close_local": "16:15",
     "open_utc": "14:30", "close_utc": "21:15", "dst_rule": "EST/EDT",
     "auction": "n/a",
     "expiry_rule": "SPX monthly: the third Friday AM-settled to the SOQ; weeklies/0DTE: every "
                    "trading day PM-settled since 2022. VIX: the Wednesday 30 days before the "
                    "next month's third Friday, AM-settled to the SOQ of SPX options.",
     "holidays": "the NYSE calendar",
     "notes": "the daily-expiring SPX option is a 2022 market-design change; dealer gamma now "
              "resets DAILY and a pre-2022 opex study measures a market that no longer exists"},
)

SESSION_WINDOWS: tuple[dict[str, Any], ...] = (
    {"name": "us_data_hour", "start_utc": "13:30", "end_utc": "14:30",
     "notes": "08:30 ET: NFP, CPI, PCE, retail sales, claims, GDP land here; the busiest hour"},
    {"name": "us_cash_open", "start_utc": "14:30", "end_utc": "15:30",
     "notes": "09:30 ET open; 10:00 ET ISM/UMich/JOLTS/new home sales; EIA at 10:30"},
    {"name": "us_lunch", "start_utc": "17:00", "end_utc": "18:30",
     "notes": "12:00-13:30 ET; WASDE at noon, auction close at 13:00"},
    {"name": "us_fomc_window", "start_utc": "19:00", "end_utc": "20:30",
     "notes": "14:00 ET statement, 14:30 presser, minutes at 14:00 on their Wednesday"},
    {"name": "us_cash_close", "start_utc": "20:00", "end_utc": "21:15",
     "notes": "the 15:00 ET Treasury mark, the 15:50 imbalance feed, the 16:00 close"},
    {"name": "us_globex_reopen", "start_utc": "23:00", "end_utc": "00:00",
     "notes": "17:00-18:00 CT: the halt, the reopen and the Asia handover"},
)

RELEASE_CLASSES: tuple[dict[str, Any], ...] = (
    {"name": "Employment Situation (NFP)", "cadence": "monthly", "time_utc": "13:30",
     "source": "BLS", "actual_series": "FRED:PAYEMS", "expected_series": "UNMEASURED",
     "notes": "first Friday (or the last of the prior month); the first print is REVISED twice "
             "and the annual benchmark revision lands in February; the household and "
             "establishment surveys disagree by construction"},
    {"name": "Consumer Price Index", "cadence": "monthly", "time_utc": "13:30", "source": "BLS",
     "actual_series": "FRED:CPIAUCSL", "expected_series": "UNMEASURED",
     "notes": "around the 10th-15th; headline, core, shelter/OER and 'supercore' are four "
             "different surprises and the tape reacts to whichever the FOMC last named"},
    {"name": "Personal Income and Outlays (PCE)", "cadence": "monthly", "time_utc": "13:30",
     "source": "BEA", "actual_series": "FRED:PCEPILFE", "expected_series": "UNMEASURED",
     "notes": "the Fed's target measure; largely inferable from CPI and PPI by release day"},
    {"name": "GDP advance / second / third estimate", "cadence": "quarterly", "time_utc": "13:30",
     "source": "BEA", "actual_series": "FRED:GDPC1", "expected_series": "UNMEASURED",
     "notes": "the advance estimate in the last week of the month after the quarter"},
    {"name": "ISM Manufacturing and Services PMI", "cadence": "monthly", "time_utc": "15:00",
     "source": "Institute for Supply Management", "actual_series": "ISM:PMI",
     "expected_series": "UNMEASURED",
     "notes": "first and third business day at 10:00 ET; prices-paid and new orders are the "
             "sub-indices the desk actually trades"},
    {"name": "Initial jobless claims", "cadence": "weekly", "time_utc": "13:30", "source": "DOL",
     "actual_series": "FRED:ICSA", "expected_series": "UNMEASURED",
     "notes": "every Thursday; seasonal factors around holidays are the classic false surprise"},
    {"name": "EIA Weekly Petroleum Status Report", "cadence": "weekly", "time_utc": "15:30",
     "source": "EIA", "actual_series": "EIA:WCRSTUS1", "expected_series": "API:Tuesday",
     "notes": "Wednesday 10:30 ET (Thursday after a Monday holiday); the API industry number "
             "Tuesday 16:30 ET is the market's prior"},
    {"name": "EIA Weekly Natural Gas Storage Report", "cadence": "weekly", "time_utc": "15:30",
     "source": "EIA", "actual_series": "EIA:NW2_EPG0_SWO_R48_BCF", "expected_series": "UNMEASURED",
     "notes": "Thursday 10:30 ET; the injection season (April-October) and withdrawal season "
             "have different surprise distributions"},
    {"name": "USDA WASDE", "cadence": "monthly", "time_utc": "17:00", "source": "USDA",
     "actual_series": "USDA:WASDE", "expected_series": "UNMEASURED",
     "notes": "around the 9th-12th at noon ET; ending stocks by crop are the datum"},
    {"name": "USDA Prospective Plantings / Acreage / Grain Stocks", "cadence": "quarterly",
     "time_utc": "17:00", "source": "USDA NASS", "actual_series": "USDA:NASS",
     "expected_series": "UNMEASURED",
     "notes": "31 March (plantings + stocks), 30 June (acreage + stocks), 30 September and "
             "early January (stocks) -- the four limit-move days of the grain year"},
    {"name": "CFTC Commitments of Traders", "cadence": "weekly", "time_utc": "20:30",
     "source": "CFTC", "actual_series": "CFTC:COT", "expected_series": "n/a",
     "notes": "Friday 15:30 ET for the Tuesday snapshot: THREE DAYS STALE on release"},
    {"name": "Treasury quarterly refunding announcement", "cadence": "quarterly",
     "time_utc": "13:30", "source": "US Treasury", "actual_series": "Treasury:refunding",
     "expected_series": "UNMEASURED",
     "notes": "the first Wednesday of February, May, August and November at 08:30 ET, after the "
             "Monday borrowing estimate; the coupon-size path is the supply shock"},
    {"name": "TIC (Treasury International Capital)", "cadence": "monthly", "time_utc": "21:00",
     "source": "US Treasury", "actual_series": "Treasury:TIC", "expected_series": "n/a",
     "notes": "around the 15th-18th at 16:00 ET for the month before last: six weeks stale, and "
             "never a same-month conditioner"},
    {"name": "University of Michigan sentiment (preliminary)", "cadence": "monthly",
     "time_utc": "15:00", "source": "University of Michigan", "actual_series": "UMich:sentiment",
     "expected_series": "UNMEASURED",
     "notes": "the second Friday at 10:00 ET; the inflation-expectation lines move UST10Y more "
             "than the headline does"},
)

# --------------------------------------------------------------------------- holidays
#: NYSE full closures, the equity table. The bond market's EXTRA closures are beside it because
#: the two calendars diverge and a pack that merges them is wrong on both sides.
HOLIDAY_TABLE: dict[int, dict[str, str]] = {
    2024: {"2024-01-01": "New Year's Day", "2024-01-15": "Martin Luther King Jr. Day",
           "2024-02-19": "Presidents' Day", "2024-03-29": "Good Friday",
           "2024-05-27": "Memorial Day", "2024-06-19": "Juneteenth",
           "2024-07-04": "Independence Day", "2024-09-02": "Labor Day",
           "2024-11-28": "Thanksgiving Day", "2024-12-25": "Christmas Day"},
    2025: {"2025-01-01": "New Year's Day",
           "2025-01-09": "National Day of Mourning (President Carter) -- unscheduled closure",
           "2025-01-20": "Martin Luther King Jr. Day", "2025-02-17": "Presidents' Day",
           "2025-04-18": "Good Friday", "2025-05-26": "Memorial Day",
           "2025-06-19": "Juneteenth", "2025-07-04": "Independence Day",
           "2025-09-01": "Labor Day", "2025-11-27": "Thanksgiving Day",
           "2025-12-25": "Christmas Day"},
    2026: {"2026-01-01": "New Year's Day", "2026-01-19": "Martin Luther King Jr. Day",
           "2026-02-16": "Presidents' Day", "2026-04-03": "Good Friday",
           "2026-05-25": "Memorial Day", "2026-06-19": "Juneteenth",
           "2026-07-03": "Independence Day observed (4 July is a Saturday)",
           "2026-09-07": "Labor Day", "2026-11-26": "Thanksgiving Day",
           "2026-12-25": "Christmas Day"},
}
BOND_MARKET_ONLY_CLOSURES: dict[str, str] = {
    "2024-10-14": "Columbus Day (SIFMA full close; equities open)",
    "2024-11-11": "Veterans Day (SIFMA full close; equities open)",
    "2025-10-13": "Columbus Day (SIFMA full close; equities open)",
    "2025-11-11": "Veterans Day (SIFMA full close; equities open)",
    "2026-10-12": "Columbus Day (SIFMA full close; equities open)",
    "2026-11-11": "Veterans Day (SIFMA full close; equities open)",
}
HALF_DAYS: dict[str, str] = {
    "2024-07-03": "13:00 ET equity close", "2024-11-29": "13:00 ET equity close",
    "2024-12-24": "13:00 ET equity close", "2025-11-28": "13:00 ET equity close",
    "2025-12-24": "13:00 ET equity close", "2026-11-27": "13:00 ET equity close",
    "2026-12-24": "13:00 ET equity close",
}
HOLIDAYS_RULE: dict[str, Any] = {
    "rule": "NYSE: New Year's Day, MLK Day (third Monday of January), Presidents' Day (third "
            "Monday of February), Good Friday, Memorial Day (last Monday of May), Juneteenth "
            "(19 June, since 2022), Independence Day, Labor Day (first Monday of September), "
            "Thanksgiving (fourth Thursday of November), Christmas. A holiday on a Saturday is "
            "observed the preceding Friday and on a Sunday the following Monday, EXCEPT that a "
            "Saturday New Year's Day is not observed. The bond market (SIFMA) adds Columbus Day "
            "and Veterans Day and closes EARLY at 14:00 ET on Good Friday when it is open at "
            "all; those are declared in BOND_MARKET_ONLY_CLOSURES and never merged.",
    "table": HOLIDAY_TABLE,
    "status": "2024 and 2025 VERIFIED against the NYSE published calendar at writing (2025-01-09 "
              "was an unscheduled closure declared four days ahead); 2026 from the NYSE "
              "published calendar, re-verify before compiling",
    "weekly_closed": (5, 6),
    "bond_market_only": BOND_MARKET_ONLY_CLOSURES,
    "half_days": HALF_DAYS,
    "notes": "CME Globex is frequently OPEN with an early close on NYSE holidays, so the broker's "
             "US500 tape carries bars on days the cash index does not print; a holiday study on "
             "the CFD must use the CASH calendar to define the closed day",
}

# --------------------------------------------------------------------------- positioning
#: THE POSITIONING SPINE. Every COT-based study on this desk reads one of these rows.
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "CFTC Commitments of Traders -- legacy, disaggregated and Traders in Financial "
             "Futures (TFF) reports",
     "root": "https://www.cftc.gov/MarketReports/CommitmentsofTraders/",
     "fields": ("non_commercial_long", "non_commercial_short", "commercial_long",
                "commercial_short", "leveraged_funds_net", "asset_manager_net",
                "dealer_net", "managed_money_net", "producer_merchant_net", "open_interest"),
     "frequency": "weekly", "snapshot": "Tuesday close",
     "publish_utc": "20:30 (EST) / 19:30 (EDT), Friday", "lag_days": 3,
     "licence": "free, public (US government work)", "available": True,
     "contracts": ("6E EUR", "6J JPY", "6B GBP", "6A AUD", "6C CAD", "6S CHF", "6M MXN",
                   "6N NZD", "DX dollar index (ICE)", "ES/NQ/YM/RTY (TFF)", "ZN/ZF/ZB/ZT (TFF)",
                   "GC/SI/HG/PL/PA", "CL/NG/RB/HO", "ZC/ZW/ZS/ZM/ZL", "SB/KC/CT/CC"),
     "why": "the only free trader-category positioning on the desk; extremes in leveraged-fund "
            "or managed-money net are the forced-liquidation risk US-E is about",
     "pit_warning": "THREE DAYS STALE on release. Aligning the Tuesday snapshot to the Tuesday "
                    "bar is a look-ahead bug that manufactures predictability out of nothing; "
                    "the report is usable from the Friday 15:30 ET minute"},
    {"name": "CME daily volume and open interest by contract",
     "root": "https://www.cmegroup.com/market-data/volume-open-interest.html",
     "fields": ("volume", "open_interest", "block_volume"), "frequency": "daily",
     "snapshot": "session close", "publish_utc": "12:00", "lag_days": 1,
     "licence": "free end-of-day; real time licensed", "available": True,
     "why": "the fast complement to the COT: an OI build with a price move is new positioning, "
            "an OI fall is liquidation, and the report says which",
     "pit_warning": "preliminary OI is restated the following morning"},
    {"name": "FINRA margin debt and free credit balances",
     "root": "https://www.finra.org/investors/learn-to-invest/advanced-investing/margin-statistics",
     "fields": ("debit_balances", "free_credit_cash", "free_credit_margin"),
     "frequency": "monthly", "snapshot": "month end", "publish_utc": "22:00", "lag_days": 20,
     "licence": "free, public", "available": True,
     "why": "the retail and hedge-fund leverage stock; a peak-and-fall in margin debt is the "
            "deleveraging state US-F conditions on",
     "pit_warning": "three weeks stale; never a same-month conditioner"},
    {"name": "Cboe equity and index put/call ratios and the daily market statistics",
     "root": "https://www.cboe.com/us/options/market_statistics/daily/",
     "fields": ("equity_put_call", "index_put_call", "spx_volume", "vix_level"),
     "frequency": "daily", "snapshot": "session close", "publish_utc": "22:30", "lag_days": 0,
     "licence": "free end-of-day", "available": True,
     "why": "the option-flow half of positioning; 0DTE volume is now the majority of SPX volume",
     "pit_warning": "the daily file is final; intraday snapshots are licensed"},
    {"name": "NYSE and Nasdaq short interest",
     "root": "https://www.nyse.com/markets/reports", "fields": ("short_interest", "days_to_cover"),
     "frequency": "semi-monthly", "snapshot": "the 15th and month end", "publish_utc": "21:00",
     "lag_days": 9, "licence": "free aggregate; single-name detail is the event lane's",
     "available": True,
     "why": "read ONLY as an aggregate (index-level short interest); a single name's short "
            "interest is an event-lane input and never enters a cell here",
     "pit_warning": "nine days stale, semi-monthly; aggregate only"},
)

# --------------------------------------------------------------------------- terminology
#: English is the native language, so this is a VOCABULARY table: the tokens American market
#: text uses that a screen reads as noise, keyed by the domain each one names, plus the layer-
#: keyed queries the native-query builder emits per source layer.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "US-A": ("the dots", "the SEP", "the dot plot", "the presser", "the pause", "the skip",
             "the cut", "the hike", "the terminal rate", "the neutral rate", "r-star",
             "the funds rate", "IORB", "the corridor", "Fedspeak", "the blackout",
             "FedWatch", "the ZQ strip", "an intermeeting move"),
    "US-B": ("NFP", "payrolls", "the print", "the whisper number", "the revision",
             "the household survey", "the establishment survey", "the birth-death model",
             "the benchmark revision", "core PCE", "supercore", "shelter", "OER",
             "the CPI print", "prices paid", "new orders", "the claims number"),
    "US-C": ("the refunding", "the tail", "the stop-through", "bid-to-cover", "the indirects",
             "the directs", "the dealers' take", "the when-issued", "the reopening",
             "the coupon sizes", "the bill share", "the belly", "the long end", "2s10s",
             "bear steepener", "bull flattener", "the term premium", "the basis trade",
             "the swap spread"),
    "US-D": ("the TGA", "the RRP", "reserve balances", "SOFR", "the repo spike",
             "the SRF", "the discount window", "QT", "the runoff", "the caps", "the X-date",
             "the debt ceiling", "the shutdown", "tax day", "bill paydowns", "ample reserves"),
    "US-E": ("the COT", "spec longs", "the commercials", "the managed money",
             "the leveraged funds", "the asset managers", "the TFF", "net spec", "the wash-out",
             "a crowded trade", "the positioning unwind", "the CTA flows", "the systematic bid",
             "trend followers", "vol control", "risk parity"),
    "US-F": ("quad witching", "triple witching", "opex", "the gamma flip", "0DTE", "the pin",
             "dealer gamma", "the vol crush", "the VIX expiry", "the roll", "the SOQ",
             "the reconstitution", "the rebalance", "the MOC imbalance", "the closing cross",
             "the buyback blackout", "the pension rebalance"),
    "US-G": ("the EIA print", "API inventories", "the Cushing draw", "the SPR release",
             "the rig count", "the crack spread", "the injection season", "the storage report",
             "HDD", "CDD", "the polar vortex", "the hurricane season", "the driving season",
             "refinery maintenance", "contango", "backwardation", "the front month",
             "the strip"),
    "US-H": ("WASDE", "ending stocks", "the crop progress", "the planting intentions",
             "prospective plantings", "the acreage report", "the grain stocks", "export sales",
             "the crush", "the Corn Belt", "the drought monitor", "yield", "harvest pressure",
             "limit up", "limit down", "the basis"),
    "US-I": ("the ISM", "the Empire", "the Philly Fed", "the Richmond Fed",
             "the Dallas Fed survey", "GDPNow", "the Cleveland nowcast", "the Beige Book",
             "the regional Feds", "the Conference Board", "UMich", "inflation expectations"),
    "US-J": ("TEUs", "the port backlog", "rail carloads", "truck tonnage", "the Cass index",
             "the ATA index", "intermodal", "the LA/Long Beach count", "AIS", "the Panama draft",
             "the Baltic Dry", "container rates"),
    "US-K": ("the TIC data", "foreign official", "the custody holdings", "the dollar smile",
             "the DXY", "the funding leg", "the safe haven", "the reserve currency",
             "the Fed swap lines", "cross-currency basis", "the year-end turn"),
    "US-L": ("the 13F season", "the 13F tilt", "Form PF", "aggregate insider buying",
             "the buyback authorisation", "the Russell recon", "the S&P add", "index inclusion",
             "the float adjustment"),
    "US-M": ("real yields", "breakevens", "TIPS", "the 10-year real", "gold's real-rate beta",
             "the ETF flows", "COMEX deliveries", "the EFP", "the gold-silver ratio"),
    # layer-keyed queries, so native_query_seeds(layer=...) has something to emit
    "official": ("FOMC statement", "Summary of Economic Projections", "H.4.1", "Fiscal Data "
                 "Treasury General Account", "auction results tail bid-to-cover",
                 "Commitments of Traders disaggregated", "Weekly Petroleum Status Report",
                 "WASDE ending stocks", "degree days outlook", "TIC major foreign holders"),
    "institutional": ("CME FedWatch", "CME open interest report", "DTCC repo volume",
                      "SIFMA holiday schedule", "primary dealer positions", "ISM report on "
                      "business", "Cboe put call ratio", "EEI weekly electric output"),
    "academic": ("NBER working paper monetary policy surprise", "FEDS working paper",
                 "SSRN FOMC announcement drift", "high-frequency identification FOMC",
                 "Treasury auction demand working paper", "post-earnings drift index"),
    "practitioner": ("fed guy blog", "Odd Lots transcript", "macro musings", "FOMC preview",
                     "refunding preview", "month-end rebalance estimate", "CTA positioning "
                     "estimate", "gamma exposure level", "0DTE flows"),
    "retail_ecology": ("wallstreetbets DD", "options flow", "gamma squeeze", "margin call",
                       "YOLO", "diamond hands", "the tape", "elite trader thread", "stocktwits"),
    "app_ecosystem": ("TradingView script", "thinkscript", "QuantConnect algorithm",
                      "Alpaca API", "IBKR TWS API", "polygon.io", "FRED API", "fredapi"),
    "media": ("Fed press conference transcript", "CNBC transcript", "Reuters Fed", "Bloomberg "
              "Fed", "WSJ Fed whisperer", "Barron's roundtable", "MarketWatch economic "
              "calendar"),
    "archive": ("FRASER FOMC transcript", "FOMC transcripts 5 year lag", "archived elite trader",
                "wayback forexfactory", "Greenbook", "Bluebook", "discontinued series"),
    "physical_economy": ("Port of Los Angeles TEU", "Port of Long Beach TEU", "AAR rail traffic",
                         "USACE lock performance", "TSA checkpoint numbers", "Baker Hughes rig "
                         "count", "EIA natural gas storage", "USDA crop progress", "NOAA "
                         "hurricane outlook"),
    "source_graph": ("FRED citations", "RePEc citing", "Fed Guy blogroll", "Odd Lots show "
                     "notes", "SSRN top downloads finance", "fredapi dependents", "arXiv q-fin "
                     "citing FRED"),
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
    """One class of source with its crawl roots, native queries and THREE independent labels.
    `machine_use_allowed=True` registers ground the desk knows and never scrapes."""
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
        "us_fed", "Federal Reserve Board and the FOMC", layer="official",
        roots=("https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
               "https://www.federalreserve.gov/newsevents/pressreleases.htm",
               "https://www.federalreserve.gov/releases/h41/",
               "https://www.federalreserve.gov/monetarypolicy/fomc_historical.htm"),
        queries=("FOMC statement", "Summary of Economic Projections", "implementation note",
                 "FOMC minutes", "H.4.1 factors affecting reserve balances", "Beige Book",
                 "press conference transcript", "balance sheet runoff caps"),
        languages=("en",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="US government work, public domain",
        notes="statements are never revised and carry the 14:00 ET timestamp; the SEP table is "
              "a stable HTML table; US-A and US-L are built on this root"),
    source_class(
        "us_treasury_fiscaldata", "US Treasury: Fiscal Data, TreasuryDirect auctions, TIC",
        layer="official",
        roots=("https://fiscaldata.treasury.gov/", "https://www.treasurydirect.gov/auctions/",
               "https://home.treasury.gov/data/treasury-international-capital-tic-system",
               "https://home.treasury.gov/policy-issues/financing-the-government/"
               "quarterly-refunding"),
        queries=("Daily Treasury Statement", "Treasury General Account", "auction results",
                 "bid-to-cover", "high yield", "indirect bidders", "quarterly refunding "
                 "statement", "major foreign holders", "tentative auction schedule"),
        languages=("en",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="US government work, public domain",
        notes="Fiscal Data has a JSON API with a daily TGA series; auction results are posted "
              "within two minutes of the 13:00 ET close and are the US-C event"),
    source_class(
        "us_bls_bea_census", "BLS, BEA and the Census Bureau (the release surprise class)",
        layer="official",
        roots=("https://www.bls.gov/schedule/news_release/", "https://www.bea.gov/news/schedule",
               "https://www.census.gov/economic-indicators/",
               "https://api.stlouisfed.org/fred/"),
        queries=("Employment Situation", "Consumer Price Index", "Producer Price Index",
                 "Personal Income and Outlays", "advance retail sales", "GDP advance estimate",
                 "JOLTS", "release schedule", "benchmark revision", "seasonal adjustment"),
        languages=("en",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="US government work; FRED terms of use",
        notes="REVISED: every series here is revised, the first print must be kept as its own "
              "vintage (ALFRED holds vintages); the 08:30 ET embargo minute is the event time"),
    source_class(
        "us_cftc_cot", "CFTC Commitments of Traders (the positioning spine)", layer="official",
        roots=("https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm",
               "https://www.cftc.gov/files/dea/history/",
               "https://publicreporting.cftc.gov/"),
        queries=("Commitments of Traders", "disaggregated futures only", "Traders in Financial "
                 "Futures", "legacy report", "open interest", "leveraged funds", "managed money",
                 "producer merchant", "historical compressed"),
        languages=("en",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="US government work, public domain",
        notes="the history files are yearly ZIPs and the Socrata API carries the same rows; the "
              "Tuesday snapshot / Friday release lag is declared in POSITIONING_SOURCES"),
    source_class(
        "us_sec_edgar_aggregate", "SEC EDGAR -- AGGREGATED filings only, never a single name",
        layer="official",
        roots=("https://www.sec.gov/cgi-bin/browse-edgar", "https://efts.sec.gov/LATEST/search-index",
               "https://www.sec.gov/data-research/sec-markets-data/form-pf-data"),
        queries=("13F-HR aggregate", "Form PF statistics", "Form 4 aggregate insider buying",
                 "buyback authorizations by month", "EDGAR full-text search", "money market "
                 "fund N-MFP"),
        languages=("en",), access_label="PUBLIC_WITH_TERMS", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED",
        licence="public; EDGAR fair-access rate limit 10 requests/second with a User-Agent",
        notes="TWO-LANE ORDER: read only as aggregates that move an index (sector tilts, "
              "aggregate insider net buying, N-MFP money fund holdings of bills and RRP); a "
              "single name's filing is the event lane's and never compiles a cell here"),
    source_class(
        "us_eia_usda_noaa", "EIA, USDA and NOAA (the counted physical economy)",
        layer="official",
        roots=("https://www.eia.gov/petroleum/supply/weekly/",
               "https://ir.eia.gov/ngs/ngs.html", "https://www.usda.gov/oce/commodity/wasde",
               "https://www.nass.usda.gov/Publications/", "https://apps.fas.usda.gov/esrquery/",
               "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/cdus/degree_days/",
               "https://www.nhc.noaa.gov/"),
        queries=("Weekly Petroleum Status Report", "Cushing stocks", "natural gas storage "
                 "report", "WASDE", "crop progress", "prospective plantings", "grain stocks",
                 "export sales report", "degree days", "hurricane outlook", "drought monitor"),
        languages=("en",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="US government work, public domain",
        notes="EIA and NASS embargo minutes are exact and are the event times of US-G and US-H; "
              "the degree-day and hurricane products are FORECASTS with their own vintage"),
    source_class(
        "us_regional_feds", "The regional Federal Reserve Banks (New York markets data, "
                            "Atlanta GDPNow, Cleveland nowcast, Dallas energy survey, "
                            "Philadelphia and Richmond surveys)",
        layer="official",
        roots=("https://www.newyorkfed.org/markets/data-hub", "https://www.atlantafed.org/cqer/"
               "research/gdpnow", "https://www.clevelandfed.org/indicators-and-data/"
               "inflation-nowcasting", "https://www.dallasfed.org/research/surveys/des",
               "https://www.philadelphiafed.org/surveys-and-data",
               "https://www.newyorkfed.org/markets/desk-operations/reverse-repo"),
        queries=("SOFR", "reverse repo operations", "primary dealer statistics", "GDPNow",
                 "inflation nowcast", "Empire State Manufacturing Survey", "Dallas Fed Energy "
                 "Survey", "Manufacturing Business Outlook Survey", "consumer expectations"),
        languages=("en",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="public; each Bank's terms of use",
        notes="the New York Fed publishes the RRP take-up at 13:15 ET daily and SOFR at 08:00 ET "
              "the next morning -- the plumbing half of US-D is read here"),
    source_class(
        "us_cme_ice_cboe", "CME Group, ICE and Cboe (contract terms, settlements, FedWatch, "
                           "volume and open interest)",
        layer="institutional",
        roots=("https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html",
               "https://www.cmegroup.com/trading-hours.html",
               "https://www.cmegroup.com/market-data/daily-bulletin.html",
               "https://www.ice.com/report/", "https://www.cboe.com/us/options/market_statistics/"),
        queries=("FedWatch", "daily bulletin", "settlement prices", "expiration calendar",
                 "trading hours", "margin requirements", "block trades", "put call ratio",
                 "VIX settlement"),
        languages=("en",), access_label="PUBLIC_WITH_TERMS", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="end-of-day free; real-time and history licensed",
        notes="the expiry rules in EXCHANGES are read from these pages; the daily bulletin is "
              "the free end-of-day settlement and OI file"),
    source_class(
        "us_dtcc_sifma_ism", "DTCC, SIFMA, the Institute for Supply Management and the "
                             "Conference Board (the private data institutions)",
        layer="institutional",
        roots=("https://www.dtcc.com/charts/daily-total-us-treasury-trade-volume",
               "https://www.sifma.org/resources/general/holiday-schedule/",
               "https://www.ismworld.org/supply-management-news-and-reports/reports/ism-report"
               "-on-business/", "https://www.conference-board.org/topics/consumer-confidence"),
        queries=("Treasury repo volume", "holiday schedule early close", "ISM Report On "
                 "Business", "prices paid index", "new orders index", "consumer confidence",
                 "leading economic index"),
        languages=("en",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="public summaries; detail licensed",
        notes="ISM releases at 10:00 ET on the first and third business day; the headline is "
              "free, the sub-indices are in the free report the same minute"),
    source_class(
        "us_nber_ssrn_feds", "NBER, SSRN and the Board's FEDS/IFDP working paper series",
        layer="academic",
        roots=("https://www.nber.org/papers", "https://papers.ssrn.com/sol3/JELJOUR_Results.cfm"
               "?form_name=journalBrowse&journal_id=1230361",
               "https://www.federalreserve.gov/econres/feds/index.htm"),
        queries=("monetary policy surprises high-frequency", "pre-FOMC announcement drift",
                 "Treasury auction demand", "dealer balance sheet constraints", "month-end "
                 "rebalancing flows", "option expiration effects", "commodity index roll",
                 "macroeconomic announcement", "TIPS liquidity premium"),
        languages=("en",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="abstracts public; NBER PDFs paywalled for "
                                             "non-subscribers, FEDS free",
        notes="a published effect is a HYPOTHESIS here until the gauntlet reproduces it on this "
              "tape; the pre-FOMC drift is the classic effect that decayed after publication"),
    source_class(
        "us_practitioner_blogs", "Practitioner plumbing and flow commentary (Fed Guy, Macro "
                                 "Musings, the Odd Lots transcripts, the refunding previews)",
        layer="practitioner",
        roots=("https://fedguy.com/", "https://www.mercatus.org/macro-musings",
               "https://www.bloomberg.com/oddlots", "https://www.macrovoices.com/"),
        queries=("fed guy", "reserve scarcity", "TGA rebuild", "bill issuance", "refunding "
                 "preview", "month-end rebalance estimate", "CTA positioning", "gamma exposure",
                 "dealer positioning", "basis trade unwind"),
        languages=("en",), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="public posts; podcast transcripts under their "
                                             "publishers' terms",
        notes="the plumbing vocabulary in TERMINOLOGY[US-D] is this layer's; every claim is a "
              "dated, testable mechanism and nothing here is evidence"),
    source_class(
        "us_sellside_flow_notes", "Sell-side flow and positioning notes (dealer gamma, CTA "
                                  "trigger levels, pension rebalance estimates)",
        layer="practitioner",
        roots=("https://www.spotgamma.com/", "https://www.nomura.com/"),
        queries=("gamma flip level", "CTA trigger", "vol control selling", "pension rebalance",
                 "dealer positioning"),
        languages=("en",), access_label="LICENSED", credibility="RELIABLE",
        predictive_state="UNTESTED", machine_use_allowed=True,
        licence="subscription; terms forbid redistribution and machine extraction",
        notes="REGISTERED, NEVER SCRAPED: the desk knows this ground exists and reads only what "
              "the authors publish openly; the mechanisms are reconstructed from public data"),
    source_class(
        "us_retail_forums", "Retail ecology: r/wallstreetbets, r/options, StockTwits, the Elite "
                            "Trader forum",
        layer="retail_ecology",
        roots=("https://www.reddit.com/r/wallstreetbets/", "https://www.reddit.com/r/options/",
               "https://stocktwits.com/", "https://www.elitetrader.com/et/"),
        queries=("DD", "YOLO", "gamma squeeze", "diamond hands", "0DTE", "options flow",
                 "margin call", "the tape", "theta gang", "wheel strategy"),
        languages=("en",), access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
        predictive_state="NARRATIVE_FEATURE", machine_use_allowed=True,
        licence="Reddit and StockTwits API terms; the forum's own terms",
        notes="KEPT AT LOW WEIGHT, NEVER DROPPED: crowding and narrative are features (US-F "
              "conditions on retail option volume); read through the public daily aggregates "
              "and never by scraping accounts"),
    source_class(
        "us_finra_retail_flow", "FINRA margin statistics and the public retail-flow aggregates",
        layer="retail_ecology",
        roots=("https://www.finra.org/investors/learn-to-invest/advanced-investing/"
               "margin-statistics", "https://www.cboe.com/us/options/market_statistics/daily/"),
        queries=("margin debt", "free credit balances", "retail option volume", "single-stock "
                 "option volume", "equity put call"),
        languages=("en",), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="public",
        notes="the measurable half of the retail layer; the forums are its narrative half"),
    source_class(
        "us_apps_apis", "The trading and data app ecosystem: TradingView scripts, thinkscript, "
                        "QuantConnect, Alpaca, IBKR, polygon.io, the FRED API",
        layer="app_ecosystem",
        roots=("https://www.tradingview.com/scripts/", "https://www.quantconnect.com/forum/",
               "https://alpaca.markets/docs/", "https://interactivebrokers.github.io/",
               "https://polygon.io/docs", "https://fred.stlouisfed.org/docs/api/fred/"),
        queries=("pine script", "thinkscript study", "QuantConnect algorithm", "Alpaca "
                 "backtest", "IBKR API", "polygon aggregates", "fredapi", "backtrader"),
        languages=("en",), access_label="PUBLIC_WITH_TERMS", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="each platform's terms; FRED API key terms",
        notes="a public indicator's popularity is a POPULARITY signal, not an evidence signal; "
              "the mechanism named by a script is what gets extracted, never its backtest"),
    source_class(
        "us_wire_media", "Wire and broadcast media: Reuters, CNBC transcripts, MarketWatch, the "
                         "Fed's own press conference transcripts",
        layer="media",
        roots=("https://www.reuters.com/markets/us/", "https://www.cnbc.com/economy/",
               "https://www.marketwatch.com/economy-politics/calendar",
               "https://www.federalreserve.gov/mediacenter/"),
        queries=("Fed", "FOMC", "Treasury yields", "jobs report", "inflation data",
                 "economic calendar", "press conference transcript", "Fed official said"),
        languages=("en",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="publisher terms; headlines and transcripts public",
        notes="a wire headline carries a timestamp to the second, which makes it the PIT anchor "
              "for an event whose official release page carries only a date"),
    source_class(
        "us_paywalled_press", "The Wall Street Journal and Bloomberg (the 'Fed whisperer' "
                              "channel)",
        layer="media",
        roots=("https://www.wsj.com/news/economy", "https://www.bloomberg.com/economics"),
        queries=("Fed whisperer", "Fed officials weigh", "Timiraos", "Bloomberg Economics"),
        languages=("en",), access_label="LICENSED", credibility="RELIABLE",
        predictive_state="UNTESTED", machine_use_allowed=True,
        licence="subscription; terms forbid scraping",
        notes="REGISTERED, NEVER SCRAPED: the WSJ 'leak' before a blackout-period meeting is a "
              "real information event (2022-06-13 is the canonical case) and the desk reads it "
              "only through the public wire echo, timestamped by the echo"),
    source_class(
        "us_fringe_macro", "Fringe macro commentary (ZeroHedge and its ecosystem)",
        layer="media",
        roots=("https://www.zerohedge.com/",),
        queries=("liquidity", "TGA", "gamma", "CTA", "dealer positioning", "Fed pivot"),
        languages=("en",), access_label="PUBLIC", credibility="FRINGE",
        predictive_state="NARRATIVE_FEATURE", licence="public site; republished sell-side "
                                                      "material of unclear licence",
        notes="KEPT AT LOW WEIGHT, NEVER DROPPED: a dubious story still names a mechanism, and "
              "narrative crowding is itself an observable; nothing here is evidence"),
    source_class(
        "us_fraser_archive", "FRASER (the Fed's historical archive), the five-year-lagged FOMC "
                             "transcripts, ALFRED vintages and the Wayback Machine",
        layer="archive",
        roots=("https://fraser.stlouisfed.org/", "https://alfred.stlouisfed.org/",
               "https://www.federalreserve.gov/monetarypolicy/fomc_historical_year.htm",
               "https://web.archive.org/"),
        queries=("FOMC transcript", "Greenbook", "Bluebook", "Tealbook", "vintage data",
                 "real-time data set", "archived forum", "discontinued series"),
        languages=("en",), access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="public domain (FRASER); Wayback terms",
        notes="ALFRED is how a release surprise is rebuilt PIT: the first print, not the revised "
              "series; the transcripts show what the Committee knew and when"),
    source_class(
        "us_ports_rail_power", "Ports, rail, freight and power: LA/Long Beach TEUs, AAR "
                               "carloads, ATA tonnage, EEI electric output, USACE locks, TSA "
                               "checkpoints, Baker Hughes",
        layer="physical_economy",
        roots=("https://www.portoflosangeles.org/business/statistics/container-statistics",
               "https://polb.com/business/port-statistics/", "https://www.aar.org/data-center/",
               "https://www.trucking.org/economics-and-industry-data",
               "https://www.eei.org/resources-and-media/industry-data",
               "https://www.tsa.gov/travel/passenger-volumes", "https://rigcount.bakerhughes.com/"),
        queries=("TEU statistics", "rail carloads intermodal", "truck tonnage index", "weekly "
                 "electric output", "lock performance", "checkpoint travel numbers", "rig "
                 "count"),
        languages=("en",), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="public statistics pages",
        notes="COUNTED, not surveyed: the port TEU count is a monthly physical import volume and "
              "the rig count a weekly capital-allocation decision by the producers themselves"),
    source_class(
        "us_ais_shipping", "AIS vessel tracking and tanker-flow aggregators",
        layer="physical_economy",
        roots=("https://www.marinetraffic.com/",),
        queries=("tanker tracking", "Gulf Coast crude exports", "LNG cargo tracking"),
        languages=("en",), access_label="LICENSED", credibility="RELIABLE",
        predictive_state="UNTESTED", machine_use_allowed=True,
        licence="commercial AIS terms forbid scraping; free tier is view-only",
        notes="REGISTERED, NEVER SCRAPED: the public EIA export numbers are the free lagged echo"),
    source_class(
        "us_source_graph", "What the other nine cite: FRED citations, RePEc citing lists, the "
                           "plumbing blogrolls, podcast show notes, GitHub dependents of fredapi",
        layer="source_graph",
        roots=("https://ideas.repec.org/", "https://github.com/mortada/fredapi/network/dependents",
               "https://fedguy.com/blogroll/", "https://www.bloomberg.com/oddlots"),
        queries=("cited by", "show notes", "blogroll", "dependents", "further reading",
                 "data appendix"),
        languages=("en",), access_label="PUBLIC_WITH_TERMS", credibility="UNKNOWN",
        predictive_state="UNTESTED", licence="each host's terms",
        notes="the expansion edges: every root above is a seed and the graph is how the scouts "
              "find the next one -- a fixed source list is forbidden (LAWS 5f rule 4)"),
)
LAYER_ABSENCES: dict[str, str] = {}

# --------------------------------------------------------------------------- datasets
DATASETS: tuple[dict[str, Any], ...] = (
    {"name": "FOMC decisions, statements and SEP dots", "source": "Federal Reserve Board",
     "coverage": "1994 onward (SEP from 2012)", "frequency": "8 per year",
     "publication_lag_days": 0.0, "revisions": "never revised", "licence": "public domain",
     "history_from": "1994-02", "pit_feasible": True,
     "assets": ("USDX", "UST05Y", "UST10Y", "US500", "USDJPY", "XAUUSD"),
     "mechanism_families": ("policy_surprise", "event_reaction", "forward_guidance"),
     "how_to_fetch": "federalreserve.gov/newsevents/pressreleases -- each statement carries "
                     "the 14:00 ET stamp; the SEP is a stable HTML table on the projections page"},
    {"name": "CME fed funds futures implied path", "source": "CME settlements",
     "coverage": "1988 onward", "frequency": "daily", "publication_lag_days": 0.0,
     "revisions": "settlements final", "licence": "free end-of-day; intraday licensed",
     "history_from": "1988-10", "pit_feasible": False,
     "assets": ("USDX", "UST05Y", "US500"), "mechanism_families": ("policy_surprise",),
     "how_to_fetch": "CME daily bulletin. PIT IS PARTIAL: the 13:55 ET pre-statement snapshot "
                     "must be captured live; a meeting without it has an UNMEASURED surprise, "
                     "never a zero one"},
    {"name": "BLS Employment Situation (first print and vintages)", "source": "BLS / ALFRED",
     "coverage": "1939 onward", "frequency": "monthly", "publication_lag_days": 7.0,
     "revisions": "two monthly revisions and an annual benchmark; ALFRED keeps every vintage",
     "licence": "public domain", "history_from": "1939-01", "pit_feasible": True,
     "assets": ("USDX", "UST10Y", "US500", "XAUUSD", "USDJPY"),
     "mechanism_families": ("event_reaction", "macro_condition"),
     "how_to_fetch": "ALFRED vintage series PAYEMS; the 08:30 ET embargo is the event time"},
    {"name": "Consumer Price Index (headline, core, shelter)", "source": "BLS / ALFRED",
     "coverage": "1913 onward", "frequency": "monthly", "publication_lag_days": 12.0,
     "revisions": "NSA never revised; SA factors revised each February", "licence": "public domain",
     "history_from": "1947-01", "pit_feasible": True,
     "assets": ("USDX", "UST10Y", "UST05Y", "US500", "XAUUSD"),
     "mechanism_families": ("event_reaction", "macro_condition"),
     "how_to_fetch": "bls.gov/cpi release pages; vintages from ALFRED CPIAUCSL/CPILFESL"},
    {"name": "CFTC Commitments of Traders (legacy, disaggregated, TFF)", "source": "CFTC",
     "coverage": "1986 onward (disaggregated 2006, TFF 2010)", "frequency": "weekly",
     "publication_lag_days": 3.0, "revisions": "rare corrections", "licence": "public domain",
     "history_from": "1986-01", "pit_feasible": True,
     "assets": ("EURUSD", "USDJPY", "GBPUSD", "AUDUSD", "USDCAD", "USDMXN", "USDX", "US500",
                "NAS100", "US2000", "UST10Y", "UST05Y", "XAUUSD", "XAGUSD", "XCUUSD", "XTIUSD",
                "XNGUSD", "CORN", "WHEAT", "SOYBEAN", "SUGAR", "COTTON"),
     "mechanism_families": ("positioning_extreme", "positioning_unwind", "crowding"),
     "how_to_fetch": "cftc.gov/files/dea/history yearly ZIPs; usable from Friday 15:30 ET only"},
    {"name": "Treasury auction results (tail, bid-to-cover, allotment by class)",
     "source": "TreasuryDirect", "coverage": "1980 onward", "frequency": "per auction",
     "publication_lag_days": 0.0, "revisions": "never revised", "licence": "public domain",
     "history_from": "1980-01", "pit_feasible": True,
     "assets": ("UST10Y", "UST05Y", "USDX", "US500", "XAUUSD"),
     "mechanism_families": ("supply_shock", "event_reaction", "dealer_absorption"),
     "how_to_fetch": "treasurydirect.gov/auctions/announcements-data-results -- the results "
                     "PDF/XML lands within two minutes of 13:00 ET"},
    {"name": "Daily Treasury Statement: TGA, receipts, bill paydowns", "source": "Fiscal Data",
     "coverage": "2005 onward daily", "frequency": "daily", "publication_lag_days": 1.0,
     "revisions": "never revised", "licence": "public domain", "history_from": "2005-06",
     "pit_feasible": True, "assets": ("USDX", "US500", "UST05Y", "EURUSD"),
     "mechanism_families": ("liquidity_plumbing", "calendar_flow"),
     "how_to_fetch": "fiscaldata.treasury.gov API v1 accounting/dts/operating_cash_balance"},
    {"name": "New York Fed RRP take-up, SOFR and reserve balances (H.4.1)",
     "source": "New York Fed / Board", "coverage": "2013 onward (RRP), 2018 (SOFR)",
     "frequency": "daily / weekly", "publication_lag_days": 0.0, "revisions": "never revised",
     "licence": "public domain", "history_from": "2013-09", "pit_feasible": True,
     "assets": ("USDX", "US500", "UST05Y", "EURUSD", "USDJPY"),
     "mechanism_families": ("liquidity_plumbing", "funding_stress"),
     "how_to_fetch": "newyorkfed.org markets data hub (RRP at 13:15 ET, SOFR 08:00 ET next day)"},
    {"name": "EIA Weekly Petroleum Status Report and Natural Gas Storage", "source": "EIA",
     "coverage": "1982 onward (crude), 1994 (gas)", "frequency": "weekly",
     "publication_lag_days": 5.0, "revisions": "rare; monthly PSM supersedes weekly",
     "licence": "public domain", "history_from": "1982-08", "pit_feasible": True,
     "assets": ("XTIUSD", "XBRUSD", "XNGUSD", "USDCAD"),
     "mechanism_families": ("inventory_surprise", "event_reaction", "seasonal"),
     "how_to_fetch": "eia.gov API v2 petroleum/stoc/wstk and natural-gas/stor/wkly; Wednesday "
                     "and Thursday 10:30 ET embargo minutes"},
    {"name": "USDA WASDE, NASS quarterly stocks/acreage, FAS export sales", "source": "USDA",
     "coverage": "1973 onward", "frequency": "monthly / quarterly / weekly",
     "publication_lag_days": 0.0, "revisions": "each WASDE supersedes the last; the revision is "
                                              "the datum", "licence": "public domain",
     "history_from": "1973-01", "pit_feasible": True,
     "assets": ("CORN", "WHEAT", "SOYBEAN", "COTTON", "SUGAR"),
     "mechanism_families": ("supply_surprise", "event_reaction", "seasonal"),
     "how_to_fetch": "usda.gov/oce/commodity/wasde (noon ET); NASS Quick Stats API; FAS ESR "
                     "Thursday 08:30 ET"},
    {"name": "NOAA degree days, hurricane outlooks and the Drought Monitor",
     "source": "NOAA CPC / NHC / NDMC", "coverage": "1981 onward", "frequency": "daily / weekly",
     "publication_lag_days": 0.0, "revisions": "forecasts are re-issued; each vintage kept",
     "licence": "public domain", "history_from": "1981-01", "pit_feasible": True,
     "assets": ("XNGUSD", "XTIUSD", "CORN", "SOYBEAN", "COTTON"),
     "mechanism_families": ("weather_forecast_revision", "seasonal"),
     "how_to_fetch": "cpc.ncep.noaa.gov degree-day files; nhc.noaa.gov advisories; "
                     "droughtmonitor.unl.edu Thursday release"},
    {"name": "TIC: major foreign holders and monthly net purchases", "source": "US Treasury",
     "coverage": "2000 onward monthly", "frequency": "monthly", "publication_lag_days": 45.0,
     "revisions": "annual benchmark survey restates holdings", "licence": "public domain",
     "history_from": "2000-03", "pit_feasible": True,
     "assets": ("USDX", "UST10Y", "USDJPY", "USDCNH", "EURUSD"),
     "mechanism_families": ("official_flow", "macro_condition"),
     "how_to_fetch": "home.treasury.gov TIC pages; six weeks stale, never a same-month input"},
    {"name": "Port of Los Angeles / Long Beach container statistics", "source": "the ports",
     "coverage": "1995 onward monthly", "frequency": "monthly", "publication_lag_days": 15.0,
     "revisions": "rare", "licence": "public", "history_from": "1995-01", "pit_feasible": True,
     "assets": ("US2000", "USDCNH", "US500"), "mechanism_families": ("physical_volume",
                                                                    "macro_condition"),
     "how_to_fetch": "portoflosangeles.org and polb.com statistics pages (TEU tables)"},
)

# --------------------------------------------------------------------------- actors
ACTORS: tuple[dict[str, Any], ...] = (
    {"name": "The Federal Open Market Committee",
     "holds": "the target range for the funds rate, IORB, the ON RRP rate and a $6-7trn SOMA "
              "portfolio in runoff",
     "forced_to": ("decide at eight pre-announced meetings and publish a statement at 14:00 ET "
                   "the same day", "publish nineteen participants' projections four times a "
                   "year", "release minutes three weeks later",
                   "hold a press conference after every meeting"),
     "when": "14:00 ET on the second day of each meeting (19:00 UTC EST / 18:00 UTC EDT), "
             "presser at 14:30 ET",
     "information": ("the full BLS/BEA dataset and staff forecasts", "the Beige Book liaison",
                     "supervisory data on the banks", "the desk's daily reserve conditions"),
     "constraints": ("the dual mandate", "the 2% PCE target", "a communications blackout it "
                     "imposes on itself", "the runoff caps it announced"),
     "instruments": ("USDX", "UST05Y", "UST10Y", "US500", "USDJPY", "XAUUSD"),
     "counterparties": ("primary dealers", "money market funds at the RRP", "the banks holding "
                        "reserves", "the Treasury as fiscal agent"),
     "observables": ("the statement text diff", "the dots' median and dispersion", "the ZQ "
                     "implied rate before and after", "the presser transcript"),
     "impact": "reprices the whole dollar curve in seconds; the move is proportional to the "
               "SURPRISE against ZQ and to the dots' revision, not to the decision",
     "persistence": "the level effect is permanent until the next meeting; the excess move "
                    "decays over hours; the presser can reverse the statement's move within "
                    "thirty minutes",
     "falsifier": "the same 14:00-15:30 ET window on the eight nearest non-FOMC Wednesdays; a "
                  "move that survives there is a Wednesday effect wearing the Fed's hat",
     "notes": "an intermeeting decision is its own class (2020-03-03, 2020-03-15) and is never "
              "pooled with the scheduled sample"},
    {"name": "The US Treasury (Office of Debt Management and the Fiscal Service)",
     "holds": "the TGA at the Fed, the auction calendar and the coupon-size path",
     "forced_to": ("pay every obligation on its date regardless of receipts", "announce the "
                   "quarterly refunding on the first Wednesday of February, May, August and "
                   "November", "rebuild the TGA after a debt-ceiling resolution",
                   "issue bills to bridge the April and September tax troughs"),
     "when": "08:30 ET refunding days; 13:00 ET auction closes; the 15th and month-end "
             "settlements; tax dates 15 April/June/September/December",
     "information": ("daily receipts and outlays before publication", "the borrowing estimate",
                     "the TBAC's advice"),
     "constraints": ("the debt ceiling", "regular and predictable issuance", "the WAM target",
                     "the cash balance policy (one week of outflows)"),
     "instruments": ("UST05Y", "UST10Y", "USDX", "US500"),
     "counterparties": ("primary dealers", "money market funds", "foreign official accounts",
                        "the Fed as fiscal agent"),
     "observables": ("the Daily Treasury Statement TGA line", "the refunding statement's "
                     "coupon-size table", "the auction results", "bill paydown notices"),
     "impact": "coupon-size increases steepen the curve on refunding day (2023-08-02 and "
               "2023-11-01 are the paired cases); TGA rebuilds drain reserves and bid the "
               "dollar's funding leg",
     "persistence": "refunding shocks persist for weeks; TGA effects last as long as the "
                    "rebuild",
     "falsifier": "the same curve move on the four nearest non-refunding Wednesdays, and a "
                  "TGA-conditioned study run on a placebo balance series with the same "
                  "seasonality",
     "notes": "a shutdown (a lapse of appropriations after 30 September) stops BLS/BEA releases; "
              "the release surprise class is UNMEASURED for its duration, never zero"},
    {"name": "Primary dealers",
     "holds": "inventory of Treasuries, the obligation to bid at every auction and a balance "
              "sheet bound by the SLR",
     "forced_to": ("bid at every auction at a pro-rata share", "make markets in the "
                   "when-issued", "absorb the tail when indirects step back",
                   "finance inventory in repo overnight"),
     "when": "13:00 ET auction closes; quarter-end and year-end balance-sheet dates",
     "information": ("customer flow at the auction", "the repo rate they finance at",
                     "the indirect share before it is published"),
     "constraints": ("the supplementary leverage ratio", "the Fed's dealer surveys",
                     "quarter-end window dressing of the balance sheet"),
     "instruments": ("UST10Y", "UST05Y", "USDX"),
     "counterparties": ("the Treasury", "asset managers and foreign official buyers", "the "
                        "Fed's Standing Repo Facility", "money market funds in repo"),
     "observables": ("the dealer take at each auction", "the NY Fed primary dealer positions",
                     "the tail in basis points", "the repo rate into quarter end"),
     "impact": "a large tail with a high dealer take is a supply indigestion signal that "
               "cheapens the tenor for days; quarter-end balance-sheet retreat spikes repo",
     "persistence": "days after a tailed auction; the repo spike is one to three days",
     "falsifier": "the same tenor's move after auctions with a stop-through and a low dealer "
                  "take; if the sign does not flip, the tail is not the mechanism",
     "notes": "the September 2019 repo spike is the archetype of the quarter-end constraint"},
    {"name": "Money market funds",
     "holds": "$6-7trn, allocated between bills, repo and the Fed's ON RRP facility",
     "forced_to": ("keep a weekly liquid asset floor", "reallocate from RRP to bills when bills "
                   "cheapen after a debt-ceiling resolution", "mark to a stable NAV"),
     "when": "daily at the 13:15 ET RRP operation; heavily around tax dates and bill "
             "issuance surges",
     "information": ("the bill-RRP spread", "their own inflows"),
     "constraints": ("SEC 2a-7 liquidity rules", "the RRP counterparty cap", "a 60-day WAM"),
     "instruments": ("USDX", "US500", "UST05Y"),
     "counterparties": ("the New York Fed", "the Treasury (bills)", "dealers in repo"),
     "observables": ("RRP take-up", "N-MFP holdings", "the bill-OIS spread"),
     "impact": "the RRP is the buffer that makes bill issuance reserve-neutral; when it is "
               "drained, bill issuance drains reserves instead and the funding leg of the "
               "dollar bids",
     "persistence": "regime-length: months",
     "falsifier": "the same reserve-drain study in a period when RRP take-up was above $1trn; "
                  "the effect should be absent there",
     "notes": "the RRP fell from $2.3trn (2023) toward zero in 2024-2025; the era table marks it"},
    {"name": "CTAs, trend followers and vol-target funds",
     "holds": "systematic long/short futures positions sized to realised volatility",
     "forced_to": ("cut exposure when realised vol rises", "flip when a trend signal crosses",
                   "roll into the next contract on the index roll schedule"),
     "when": "at the close, after a vol spike; around the quarterly roll",
     "information": ("their own signals, which are estimable from public prices",),
     "constraints": ("a volatility target", "leverage limits", "the roll calendar"),
     "instruments": ("US500", "NAS100", "US2000", "UST10Y", "XTIUSD", "XAUUSD", "EURUSD"),
     "counterparties": ("dealers", "other systematic funds", "the retail option crowd"),
     "observables": ("the TFF leveraged-funds net", "estimated CTA positioning from sell-side "
                     "notes", "realised vs implied vol"),
     "impact": "mechanical selling after a vol shock amplifies the first move and reverses "
               "over days as vol normalises",
     "persistence": "days",
     "falsifier": "the same post-shock return in a sample where the TFF leveraged-funds net was "
                  "near zero: without a position there is no unwind",
     "notes": "the sell-side estimates are practitioner claims; the COT is the measurement"},
    {"name": "Options dealers and the 0DTE crowd",
     "holds": "the short side of index option gamma, hedged in futures",
     "forced_to": ("buy futures as the index rises and sell as it falls when short gamma",
                   "re-hedge daily since the 2022 daily-expiry change"),
     "when": "into the 16:00 ET close; the third Friday; the Wednesday VIX expiry",
     "information": ("the option order flow they see",),
     "constraints": ("delta neutrality", "the exchange's position limits"),
     "instruments": ("US500", "NAS100"),
     "counterparties": ("retail option buyers", "vol funds", "the pension overwriters"),
     "observables": ("Cboe put/call", "0DTE share of SPX volume", "the largest open-interest "
                     "strikes into opex"),
     "impact": "positive dealer gamma pins the index near large strikes; negative gamma "
               "amplifies moves; the pin releases the Monday after opex",
     "persistence": "intraday to one week",
     "falsifier": "the same pin statistic on weeks with no expiry and on the non-US index "
                  "controls (GER40, JPN225)",
     "notes": "US-F tests this; the sell-side 'gamma flip level' is a claim, never an input"},
    {"name": "Corporate buyback desks",
     "holds": "authorised repurchase programmes executed through 10b5-1 plans",
     "forced_to": ("stop discretionary buying in the blackout before earnings", "execute the "
                   "plan on schedule regardless of price"),
     "when": "the blackout runs roughly from two weeks before quarter end to the earnings "
             "release; the open window is the six weeks after",
     "information": ("their own results before publication (which is why the blackout exists)",),
     "constraints": ("Rule 10b-18 volume limits", "the blackout policy", "the 1% excise tax"),
     "instruments": ("US500", "NAS100", "US2000"),
     "counterparties": ("index funds", "the closing auction"),
     "observables": ("aggregate authorisations by month (EDGAR aggregate)", "the S&P buyback "
                     "yield", "the blackout calendar derived from the earnings calendar"),
     "impact": "a measurable daily bid disappears during blackout; the index's drift and its "
               "response to shocks differ across the two windows",
     "persistence": "the window's length",
     "falsifier": "the same drift difference measured on GER40 and JPN225, which share the "
                  "macro calendar but not the US blackout",
     "notes": "aggregate only: no single name is ever an instrument here"},
    {"name": "Pension funds and target-date allocators",
     "holds": "$10trn+ across equities and bonds at policy weights",
     "forced_to": ("rebalance to policy weights at month and quarter end", "sell the winning "
                   "asset class and buy the losing one"),
     "when": "the last two sessions of the month, heaviest at quarter end",
     "information": ("the month's realised equity-minus-bond return, which is public",),
     "constraints": ("policy ranges", "the investment committee calendar"),
     "instruments": ("US500", "UST10Y", "EURUSD", "USDJPY"),
     "counterparties": ("the closing auction", "the WMR fix", "dealers"),
     "observables": ("the sell-side rebalance estimate", "MOC imbalance at month end"),
     "impact": "sign set by the month's relative return; after a strong equity month the "
               "rebalancer sells equities into the last close and buys duration",
     "persistence": "two sessions",
     "falsifier": "the unconditional month-end return, which should average to zero, versus "
                  "the SIGNED version, which should not",
     "notes": "US-F's conditional half; the same mechanism as Australia's super funds"},
    {"name": "Index providers and passive funds",
     "holds": "the S&P, Nasdaq-100 and Russell methodologies and the trillions that track them",
     "forced_to": ("trade the rebalance at the close on the effective date", "buy the added "
                   "name and sell the deleted one regardless of price"),
     "when": "the S&P quarterly rebalance (third Friday of March/June/September/December), the "
             "Russell reconstitution (last Friday of June), the Nasdaq-100 December "
             "reconstitution",
     "information": ("the methodology, which is public",),
     "constraints": ("tracking error", "the closing auction's capacity"),
     "instruments": ("US500", "NAS100", "US2000"),
     "counterparties": ("the closing auction", "arbitrageurs who pre-position"),
     "observables": ("the closing-auction volume on the effective date", "the pre-announced "
                     "changes"),
     "impact": "the largest closing-auction volume of the year (the Russell recon); index-level "
               "effects are measurable, single-name effects are the event lane's",
     "persistence": "one session, with a documented reversal over the following week",
     "falsifier": "the same close-to-close statistic on the other Fridays of June",
     "notes": "index-level only"},
    {"name": "Foreign official reserve managers",
     "holds": "$3-4trn of Treasuries and agencies in custody at the New York Fed",
     "forced_to": ("sell Treasuries to defend a currency", "buy them to recycle a surplus"),
     "when": "visible in TIC six weeks later and in the weekly custody holdings the Thursday "
             "after",
     "information": ("their own intervention",),
     "constraints": ("their reserve adequacy rules", "sanctions risk"),
     "instruments": ("UST10Y", "USDX", "USDJPY", "USDCNH"),
     "counterparties": ("the Fed as custodian", "dealers"),
     "observables": ("H.4.1 custody holdings", "TIC major foreign holders"),
     "impact": "a defence of the yen or the yuan shows up as Treasury selling; the weekly "
               "custody line is the fast proxy",
     "persistence": "weeks",
     "falsifier": "custody changes in weeks with no intervention should carry no yield effect",
     "notes": "the Japan and China packs own the intervention events; this pack owns the ledger"},
    {"name": "Shale producers and their hedge programmes",
     "holds": "forward production, hedged in the NYMEX strip at fixed prices",
     "forced_to": ("hedge the next 12-24 months when the strip rallies", "cut rigs when the "
                   "strip falls below breakeven"),
     "when": "weekly (rig count Friday 13:00 ET) and quarterly (hedge disclosures, read only in "
             "aggregate)",
     "information": ("their own well economics",),
     "constraints": ("lender-required hedge ratios", "capital discipline promised to investors"),
     "instruments": ("XTIUSD", "XBRUSD", "XNGUSD", "USDCAD"),
     "counterparties": ("swap dealers", "the managed money on the other side of the COT"),
     "observables": ("the Baker Hughes rig count", "the COT producer/merchant net", "the "
                     "Dallas Fed energy survey breakeven"),
     "impact": "producer hedging caps the strip's rallies at the back end; a rig-count "
               "response lags price by months",
     "persistence": "months",
     "falsifier": "the same back-end cap on Brent, where US producers do not hedge",
     "notes": "aggregate only; a single producer is an event-lane instrument"},
    {"name": "Refiners",
     "holds": "crude inventory and the crack spread",
     "forced_to": ("run maintenance in spring and autumn", "maximise gasoline into the driving "
                   "season and distillate into winter"),
     "when": "the WPSR Wednesday; the seasonal turnaround windows",
     "information": ("their own run rates before the EIA prints them",),
     "constraints": ("RVP specification changes on 1 May and 15 September", "RIN obligations"),
     "instruments": ("XTIUSD", "XBRUSD"),
     "counterparties": ("producers", "the SPR", "export buyers"),
     "observables": ("EIA refinery utilisation", "the crack spread", "Cushing stocks"),
     "impact": "a maintenance season pushes crude stocks up and products down; the Cushing "
               "draw is the front-spread mechanism",
     "persistence": "weeks",
     "falsifier": "the same seasonal on Brent, which has no Cushing",
     "notes": "the crack spread itself is not quotable; the crude legs are"},
    {"name": "Farmers, elevators and the crop insurers",
     "holds": "the US corn, soybean, wheat and cotton crops and their forward sales",
     "forced_to": ("price the crop against the February insurance guarantee", "sell at "
                   "harvest for cash flow", "report acreage to FSA and plantings to NASS"),
     "when": "the four NASS report days; the February price-discovery window; harvest "
             "(September-November)",
     "information": ("field conditions before the crop progress report",),
     "constraints": ("storage capacity", "the insurance guarantee", "the basis"),
     "instruments": ("CORN", "SOYBEAN", "WHEAT", "COTTON"),
     "counterparties": ("commercial merchants", "the managed money", "export buyers (China, "
                        "Mexico)"),
     "observables": ("the COT producer/merchant net", "NASS crop progress", "export sales"),
     "impact": "harvest pressure and report-day limit moves; the managed-money extreme against "
               "the commercials is the unwind setup",
     "persistence": "days (reports) to months (harvest)",
     "falsifier": "the same report-day statistic on SUGAR, which has no NASS report",
     "notes": "US-H"},
    {"name": "Natural gas storage operators and utilities",
     "holds": "the working gas in storage across the five EIA regions",
     "forced_to": ("inject April-October and withdraw November-March", "meet weather-driven "
                   "demand regardless of price"),
     "when": "the Thursday 10:30 ET storage report; NOAA's 6-10 and 8-14 day outlooks",
     "information": ("their own nominations",),
     "constraints": ("storage capacity", "pipeline constraints", "LNG feedgas demand"),
     "instruments": ("XNGUSD",),
     "counterparties": ("LNG exporters", "power generators", "the managed money"),
     "observables": ("the storage surplus/deficit to the five-year average", "HDD/CDD "
                     "forecast revisions", "LNG feedgas"),
     "impact": "a storage miss against the survey moves the front month within minutes; a "
               "forecast revision moves it before the report",
     "persistence": "days",
     "falsifier": "the same 10:30 ET window on non-report Thursdays",
     "notes": "US-G and US-I"},
    {"name": "The Strategic Petroleum Reserve (Department of Energy)",
     "holds": "the federal crude stockpile (about 400m barrels after the 2022 releases)",
     "forced_to": ("release on a presidential direction", "refill on a published tender "
                   "schedule at or below a stated price"),
     "when": "tender announcements; the weekly WPSR line",
     "information": ("the refill price ceiling, which is public",),
     "constraints": ("appropriations", "the pipeline capacity of the sites"),
     "instruments": ("XTIUSD", "XBRUSD"),
     "counterparties": ("refiners", "the strip"),
     "observables": ("the SPR line in the WPSR", "the solicitation notices"),
     "impact": "a release adds supply to the Gulf; a stated refill price is a soft floor on "
               "the strip",
     "persistence": "months",
     "falsifier": "the floor should be absent in Brent's own curve beyond the WTI-Brent spread",
     "notes": "a policy actor with a counted flow"},
)

# --------------------------------------------------------------------------- domains
DOMAINS: tuple[dict[str, Any], ...] = (
    {"id": "US-A", "title": "FOMC decisions and the dots against the ZQ-implied path",
     "objects": ("the eight statements at 19:00/18:00 UTC", "the SEP median and its revision",
                 "the presser at 14:30 ET as a second event", "the intermeeting class"),
     "conditions": ("the surprise in basis points against ZQ at 13:55 ET, scaled for days "
                    "elapsed", "the dots' median revision sign", "the era (ZLB, hiking, "
                    "plateau, cutting)", "whether the meeting fell in a CPI week"),
     "instruments": ("USDX", "UST05Y", "UST10Y", "US500", "USDJPY", "XAUUSD"),
     "controls": ("the same window on the eight nearest non-FOMC Wednesdays",
                  "the same window on GER40, which has no Fed exposure beyond risk",
                  "ECB decision days, separating 'a central bank decided' from 'the Fed decided'",
                  "a placebo surprise drawn from ZQ's own daily noise"),
     "notes": "the presser routinely reverses the statement move; US-A keeps the two apart"},
    {"id": "US-B", "title": "Release surprises with their revisions: NFP, CPI, PCE, ISM",
     "objects": ("the 08:30 ET prints", "the first-print vs final vintage", "the 10:00 ET ISM"),
     "conditions": ("the surprise against the survey median", "the revision of the prior "
                    "month, which the tape reads as a second surprise", "the FOMC's named "
                    "sub-index (shelter, supercore, prices paid)", "the blackout state"),
     "instruments": ("USDX", "UST10Y", "US500", "XAUUSD", "EURUSD"),
     "controls": ("the same minute on non-release days", "the same release class in Canada "
                  "(USDCAD), separating 'a data print' from 'a US print'", "a placebo built "
                  "from the SA-factor revision alone"),
     "notes": "a shutdown stops the class: those days are UNMEASURED, not quiet"},
    {"id": "US-C", "title": "Treasury auctions and the quarterly refunding",
     "objects": ("every 2/3/5/7/10/20/30-year auction result", "the four refunding statements",
                 "the borrowing estimate the Monday before"),
     "conditions": ("the tail in bp", "the dealer take vs the indirect share", "the coupon-size "
                    "change in the refunding", "the tenor"),
     "instruments": ("UST10Y", "UST05Y", "USDX", "US500", "XAUUSD"),
     "controls": ("the same 13:00 ET window on non-auction days", "gilt auctions (UKGILT) as "
                  "the 'an auction happened' control", "a placebo tail drawn from the "
                  "when-issued's own noise"),
     "notes": "2023-08-02 and 2023-11-01 are the paired refunding cases: same clock, opposite "
              "coupon-size surprise, opposite curve move"},
    {"id": "US-D", "title": "The plumbing: TGA, RRP, reserves, tax dates and SOFR",
     "objects": ("the daily TGA", "RRP take-up", "reserve balances", "SOFR vs IORB",
                 "the tax-date drains", "the debt-ceiling X-date and the rebuild after"),
     "conditions": ("the reserve regime (abundant, ample, scarce)", "whether the RRP buffer "
                    "is above $200bn", "the tax-date calendar", "quarter-end"),
     "instruments": ("USDX", "US500", "UST05Y", "EURUSD", "USDJPY"),
     "controls": ("the same calendar days in years with an RRP buffer above $1trn",
                  "a placebo drain series with the same seasonality but no reserve effect",
                  "GER40 as the risk control with no US plumbing"),
     "notes": "the RRP drain of 2024-2025 is the era boundary the study conditions on"},
    {"id": "US-E", "title": "The COT positioning spine: extremes, unwinds and crowding",
     "objects": ("leveraged-funds and managed-money net by contract", "the z-score of net "
                 "against three years", "the weekly change", "open interest"),
     "conditions": ("the extreme percentile", "the direction of the following week's price",
                    "the asset class", "the era"),
     "instruments": ("EURUSD", "USDJPY", "AUDUSD", "USDCAD", "USDMXN", "USDX", "US500",
                     "NAS100", "US2000", "UST10Y", "XAUUSD", "XAGUSD", "XCUUSD", "XTIUSD",
                     "XNGUSD", "CORN", "WHEAT", "SOYBEAN", "SUGAR", "COTTON"),
     "controls": ("the same statistic with the report aligned to its Tuesday snapshot (the "
                  "look-ahead version) to measure the leak", "randomised report dates",
                  "the commercial net as the mirror image"),
     "notes": "usable from Friday 15:30 ET; the look-ahead control is the point of the domain"},
    {"id": "US-F", "title": "Expiry, opex, rebalances and the dealer-gamma calendar",
     "objects": ("quad witching", "monthly opex", "the VIX Wednesday", "the S&P rebalance",
                 "the Russell reconstitution", "the month-end pension rebalance",
                 "the buyback blackout windows"),
     "conditions": ("the sign of the month's equity-minus-bond return", "the 0DTE era",
                    "the largest strike's distance from spot", "the blackout state"),
     "instruments": ("US500", "NAS100", "US30", "US2000", "UST10Y"),
     "controls": ("the same weekdays with no expiry", "GER40 and JPN225, which share the macro "
                  "calendar and not the US expiry", "the unconditional month-end return vs the "
                  "signed one"),
     "notes": "expiry and rebalance are the SAME day here, unlike Australia; the study keeps "
              "them one event"},
    {"id": "US-G", "title": "Energy inventories, refinery seasons and the SPR",
     "objects": ("the WPSR Wednesday", "the storage Thursday", "the API Tuesday prior",
                 "Cushing stocks", "refinery utilisation", "SPR tenders", "the rig count"),
     "conditions": ("the surprise against the survey", "the season", "the SPR state",
                    "contango vs backwardation"),
     "instruments": ("XTIUSD", "XBRUSD", "XNGUSD", "USDCAD"),
     "controls": ("the same 10:30 ET minute on non-report days", "Brent as the no-Cushing "
                  "control", "a placebo surprise from the API-EIA gap's own noise"),
     "notes": "the API number is the market's prior and must be in the surprise definition"},
    {"id": "US-H", "title": "USDA reports and the grain calendar",
     "objects": ("WASDE", "the four NASS report days", "weekly export sales", "crop progress",
                 "the February insurance price window", "harvest"),
     "conditions": ("the ending-stocks surprise", "the report class", "the drought monitor "
                    "state", "the managed-money extreme against the commercials"),
     "instruments": ("CORN", "WHEAT", "SOYBEAN", "COTTON", "SUGAR"),
     "controls": ("SUGAR, which has no NASS report, as the 'a grain day' control",
                  "the same noon-ET minute on non-report days", "randomised report dates"),
     "notes": "limit moves truncate the response; the study reports the truncation rate"},
    {"id": "US-I", "title": "Weather as a forecast-revision mechanism",
     "objects": ("NOAA 6-10 and 8-14 day outlooks", "degree-day forecasts", "hurricane "
                 "advisories into the Gulf", "the drought monitor"),
     "conditions": ("the revision of the forecast, not its level", "the season", "the storage "
                    "surplus state"),
     "instruments": ("XNGUSD", "XTIUSD", "CORN", "SOYBEAN", "COTTON"),
     "controls": ("XBRUSD, which the Gulf hurricane season reaches only through WTI",
                  "the same forecast revision in the off-season", "a placebo revision series"),
     "notes": "forecast vintages are kept; the mechanism is the REVISION"},
    {"id": "US-J", "title": "The counted physical economy: ports, rail, trucks, power, air",
     "objects": ("LA/Long Beach TEUs", "AAR carloads and intermodal", "ATA tonnage",
                 "EEI electric output", "TSA checkpoints", "USACE lock traffic"),
     "conditions": ("the month-over-month change", "the China tariff state", "the season"),
     "instruments": ("US2000", "US500", "USDCNH", "USDCAD"),
     "controls": ("the same statistic on GER40 as the 'global cycle' control",
                  "a placebo from the ports' own seasonal noise"),
     "notes": "US2000 is the executable leg for domestic activity"},
    {"id": "US-K", "title": "The dollar smile and the TIC/custody ledger",
     "objects": ("the DXY's response to risk-off vs to US growth surprises", "TIC net "
                 "purchases", "the weekly custody line", "the year-end funding turn"),
     "conditions": ("the risk state", "the growth-differential state", "the Fed swap-line "
                    "state"),
     "instruments": ("USDX", "EURUSD", "USDJPY", "USDCNH", "USDMXN", "USDZAR", "UST10Y"),
     "controls": ("the same study on USDCHF, the other safe haven", "randomised dates"),
     "notes": "the smile is a conditional, never an average"},
    {"id": "US-L", "title": "Aggregated disclosure: 13F tilts, insider aggregates, buyback "
                           "authorisations",
     "objects": ("the 13F season (45 days after quarter end)", "aggregate Form 4 net buying",
                 "monthly buyback authorisations", "N-MFP money fund holdings"),
     "conditions": ("the aggregate tilt's sign", "the blackout state", "the season"),
     "instruments": ("US500", "NAS100", "US2000"),
     "controls": ("the same aggregate on the non-US indices", "randomised filing dates"),
     "notes": "AGGREGATE ONLY: no single name enters a cell; that is the event lane's business"},
    {"id": "US-M", "title": "Gold, silver and the real-yield channel",
     "objects": ("the 10-year real yield", "breakevens", "ETF flows", "COMEX deliveries",
                 "central-bank buying (WGC quarterly)"),
     "conditions": ("the real-yield change sign", "the dollar's direction", "the era"),
     "instruments": ("XAUUSD", "XAGUSD", "XPTUSD", "XPDUSD", "UST10Y", "USDX"),
     "controls": ("the same regression on XCUUSD, which has no monetary demand",
                  "randomised dates"),
     "notes": "the real yield is UNMEASURED on this box until a TIPS series is loaded; the "
              "nominal leg is the proxy and the study says so"},
)

# --------------------------------------------------------------------------- miners
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    {"name": "us_fomc_surprise_vs_zq", "domain_ids": ("US-A",), "kind": "event",
     "cadence_s": 86400.0, "steerable": False, "wired": False,
     "entry": "countries.us.miners:fomc_surprise_vs_zq",
     "needs": ("CENTRAL_BANK decision dates", "the ZQ-implied rate at 13:55 ET",
               "USDX, UST05Y, US500 M15 bars"),
     "notes": "refuses a verdict when the pre-statement ZQ snapshot is missing; runs the "
              "non-FOMC-Wednesday control first"},
    {"name": "us_release_surprise_with_revisions", "domain_ids": ("US-B",), "kind": "event",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.us.miners:release_surprise_with_revisions",
     "needs": ("ALFRED vintages", "survey medians", "USDX and UST10Y M15 bars"),
     "notes": "treats the prior-month revision as a second surprise"},
    {"name": "us_auction_tail_event_study", "domain_ids": ("US-C",), "kind": "event",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.us.miners:auction_tail_event_study",
     "needs": ("TreasuryDirect results", "UST10Y and UST05Y M15 bars"),
     "notes": "the tail is measured against the 13:00 ET when-issued, never the prior close"},
    {"name": "us_plumbing_calendar", "domain_ids": ("US-D",), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.us.miners:plumbing_calendar",
     "needs": ("Daily Treasury Statement", "RRP take-up", "USDX and US500 H1 bars"),
     "notes": "conditions every tax-date and settlement effect on the RRP buffer state"},
    {"name": "us_cot_extreme_unwind", "domain_ids": ("US-E",), "kind": "positioning",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.us.miners:cot_extreme_unwind",
     "needs": ("CFTC history files", "D1 bars for every COT-covered symbol"),
     "notes": "runs the look-ahead control (Tuesday alignment) and reports the leak size"},
    {"name": "us_expiry_gamma_calendar", "domain_ids": ("US-F",), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.us.miners:expiry_gamma_calendar",
     "needs": ("the expiry calendar", "Cboe daily statistics", "US500 and NAS100 M15 bars"),
     "notes": "splits the sample at the 2022 daily-expiry change"},
    {"name": "us_eia_usda_noaa_surprises", "domain_ids": ("US-G", "US-H", "US-I"),
     "kind": "event", "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.us.miners:physical_report_surprises",
     "needs": ("EIA API v2", "USDA report calendar", "NOAA forecast vintages",
               "XTIUSD, XNGUSD, CORN, WHEAT, SOYBEAN M15 bars"),
     "notes": "one miner, three report classes, each with its own control set"},
)
MINER_DOMAINS: dict[str, tuple[str, ...]] = {
    "central_bank_surprise": ("US-A",), "release_surprise": ("US-B", "US-G", "US-H"),
    "calendar_settlement": ("US-C", "US-D", "US-F"), "holiday_liquidity": ("US-F",),
    "derivatives_expiry": ("US-F",), "session_microstructure": ("US-F", "US-J"),
    "positioning": ("US-E",), "carry_funding": ("US-D", "US-K"),
    "corporate_flow": ("US-F", "US-L"), "institutional_flow": ("US-K", "US-L"),
    "equity_mechanics": ("US-F", "US-L"), "failure": ("US-A", "US-E"),
    "residual": ("US-M",), "transfer": ("US-K",), "scouts": ("US-J",),
}

# --------------------------------------------------------------------------- transmission
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    {"id": "US-E1", "source": "FOMC surprise vs ZQ at 13:55 ET", "target": "USDJPY",
     "targets": ("USDJPY", "USDX", "XAUUSD", "US500"), "to_country": "jp", "sign": "+",
     "mechanism": "a hawkish surprise widens the US-Japan short-rate differential the carry "
                  "trade is funded on; USDJPY is the most rate-sensitive major",
     "horizon": "0 to 60 minutes", "lag_days": 0.0, "actor": "FOMC",
     "constraint": "the dual mandate", "flow": "rate-differential repricing",
     "control": "the same window on EURUSD and on non-FOMC Wednesdays",
     "falsifier": "an equal USDJPY response to a Wednesday with no FOMC",
     "evidence": "HYPOTHESIS"},
    {"id": "US-E2", "source": "NFP surprise (08:30 ET first Friday)", "target": "USDX",
     "targets": ("USDX", "EURUSD", "UST10Y"), "to_country": "global", "sign": "+",
     "mechanism": "a payroll beat raises the expected path of the funds rate; the dollar index "
                  "prices it against the ECB's path", "horizon": "0 to 4 hours",
     "lag_days": 0.0, "actor": "BLS", "constraint": "the release calendar",
     "flow": "growth surprise into the rate path",
     "control": "the same minute on the other Fridays of the month",
     "falsifier": "an equal USDX move on non-NFP Fridays", "evidence": "HYPOTHESIS"},
    {"id": "US-E3", "source": "Treasury refunding coupon-size change", "target": "UST10Y",
     "targets": ("UST10Y", "UST05Y", "XAUUSD"), "to_country": "global", "sign": "-",
     "mechanism": "a larger coupon path is a supply shock the dealers must absorb; the belly "
                  "and the long end cheapen on the announcement",
     "horizon": "1 to 10 sessions", "lag_days": 1.0, "actor": "US Treasury",
     "constraint": "regular and predictable issuance", "flow": "supply into the dealer sheet",
     "control": "the four nearest non-refunding Wednesdays",
     "falsifier": "an equal 10-year move on refunding days with unchanged coupon sizes",
     "evidence": "HYPOTHESIS"},
    {"id": "US-E4", "source": "EIA crude inventory surprise vs API", "target": "XTIUSD",
     "targets": ("XTIUSD", "XBRUSD", "USDCAD"), "to_country": "global", "sign": "-",
     "mechanism": "an unexpected build is spot supply; the front month reprices within minutes "
                  "and Brent follows at the WTI-Brent spread", "horizon": "0 to 2 hours",
     "lag_days": 0.0, "actor": "refiners and producers", "constraint": "storage capacity",
     "flow": "inventory into the front spread",
     "control": "the same 10:30 ET minute on non-report days",
     "falsifier": "an equal XTIUSD move on Wednesdays with no WPSR", "evidence": "HYPOTHESIS"},
    {"id": "US-E5", "source": "EIA natural gas storage surprise", "target": "XNGUSD",
     "targets": ("XNGUSD",), "to_country": "global", "sign": "-",
     "mechanism": "a larger-than-expected injection is a storage surplus the market prices "
                  "against the five-year average", "horizon": "0 to 2 hours", "lag_days": 0.0,
     "actor": "storage operators", "constraint": "storage capacity",
     "flow": "storage surprise into the front month",
     "control": "non-report Thursdays at 10:30 ET",
     "falsifier": "an equal move on non-report Thursdays", "evidence": "HYPOTHESIS"},
    {"id": "US-E6", "source": "USDA WASDE ending-stocks surprise", "target": "CORN",
     "targets": ("CORN", "SOYBEAN", "WHEAT"), "to_country": "global", "sign": "-",
     "mechanism": "higher ending stocks lower the stocks-to-use ratio's scarcity premium; the "
                  "response is truncated by limit moves", "horizon": "0 to 1 session",
     "lag_days": 0.0, "actor": "USDA", "constraint": "the report calendar",
     "flow": "supply estimate into the price", "control": "SUGAR on the same day",
     "falsifier": "an equal CORN move on non-WASDE days at noon ET", "evidence": "HYPOTHESIS"},
    {"id": "US-E7", "source": "quad witching and the S&P rebalance close", "target": "US500",
     "targets": ("US500", "NAS100", "US2000"), "to_country": "global", "sign": "+/-",
     "mechanism": "the closing auction absorbs the largest scheduled flow of the quarter; the "
                  "last-hour range and the next-day reversal are the observables",
     "horizon": "the last hour and the next session", "lag_days": 0.0,
     "actor": "index funds and dealers", "constraint": "the methodology's effective date",
     "flow": "rebalance into the auction", "control": "the other Fridays of the quarter month",
     "falsifier": "an equal last-hour range on non-expiry Fridays", "evidence": "HYPOTHESIS"},
    {"id": "US-E8", "source": "COT leveraged-funds net at a three-year extreme",
     "target": "EURUSD", "targets": ("EURUSD", "USDJPY", "XAUUSD", "XTIUSD"),
     "to_country": "global", "sign": "-",
     "mechanism": "a crowded position has no marginal buyer; the following weeks carry a "
                  "measurable unwind, but only from Friday 15:30 ET, never from the Tuesday",
     "horizon": "1 to 4 weeks", "lag_days": 3.0, "actor": "leveraged funds",
     "constraint": "risk limits", "flow": "positioning unwind",
     "control": "the same study with the report aligned to Tuesday (the look-ahead leak)",
     "falsifier": "an unwind of equal size in weeks with median positioning",
     "evidence": "HYPOTHESIS"},
    {"id": "US-E9", "source": "corporate tax date reserve drain (15 April)", "target": "US500",
     "targets": ("US500", "USDX", "UST05Y"), "to_country": "global", "sign": "-",
     "mechanism": "the TGA rises by tens of billions in a week and reserves fall; with the RRP "
                  "buffer drained the funding leg of the dollar bids and risk assets lose a "
                  "marginal bid", "horizon": "the week around the date", "lag_days": 2.0,
     "actor": "the Treasury", "constraint": "the tax calendar",
     "flow": "reserve drain into funding",
     "control": "the same calendar week in years with an RRP buffer above $1trn",
     "falsifier": "an equal effect when the RRP buffer absorbed the drain",
     "evidence": "HYPOTHESIS"},
    {"id": "US-E10", "source": "US CPI surprise (08:30 ET)", "target": "GER40",
     "targets": ("GER40", "JPN225", "EURUSD"), "to_country": "de", "sign": "-",
     "mechanism": "a hot US print reprices the global discount rate; the European index reacts "
                  "inside its own afternoon session", "horizon": "0 to 2 hours",
     "lag_days": 0.0, "actor": "BLS", "constraint": "the release calendar",
     "flow": "US inflation into the global rate", "control": "the same minute on non-CPI days",
     "falsifier": "an equal GER40 move at 13:30 UTC on non-release days",
     "evidence": "HYPOTHESIS"},
    {"id": "US-E11", "source": "Gulf hurricane advisory (NHC) with a Gulf landfall track",
     "target": "XNGUSD", "targets": ("XNGUSD", "XTIUSD", "XBRUSD"), "to_country": "global",
     "sign": "+", "mechanism": "Gulf production and LNG feedgas shut in ahead of landfall; the "
                               "supply loss is priced on the advisory, not the landfall",
     "horizon": "1 to 5 sessions", "lag_days": 1.0, "actor": "NOAA / producers",
     "constraint": "the advisory schedule", "flow": "forecast into shut-in supply",
     "control": "Atlantic storms with no Gulf track",
     "falsifier": "an equal move on advisories for storms that never enter the Gulf",
     "evidence": "HYPOTHESIS"},
    {"id": "US-E12", "source": "Fed cut cycle start (first cut after a plateau)",
     "target": "USDMXN",
     "targets": ("USDMXN", "USDZAR", "XAUUSD"), "to_country": "mx", "sign": "-",
     "mechanism": "the carry differential to the high-yielders compresses from the US side; "
                  "the peso is the most liquid carry cross the desk quotes",
     "horizon": "1 to 20 sessions", "lag_days": 1.0, "actor": "FOMC",
     "constraint": "the dual mandate", "flow": "carry compression",
     "control": "the same cut on USDJPY, a funding currency where the sign should differ",
     "falsifier": "an equal USDMXN move on a hold", "evidence": "HYPOTHESIS"},
)

# --------------------------------------------------------------------------- eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    {"name": "post-liftoff hiking and QT one", "start": "2015-12-16", "end": "2019-07-30",
     "regime": "nine hikes to 2.25-2.50%, balance-sheet runoff from October 2017",
     "markers": ("2015-12-16 liftoff", "2018-12-19 the last hike", "2019-09-17 the repo spike"),
     "why_it_matters": "the only pre-pandemic QT sample; the September 2019 repo spike is the "
                       "reserve-scarcity boundary US-D conditions on", "status": "SETTLED"},
    {"name": "mid-cycle cuts and the pandemic ZLB", "start": "2019-07-31", "end": "2022-03-15",
     "regime": "three cuts, two unscheduled cuts to zero in March 2020, QE at $120bn/month",
     "markers": ("2020-03-15 the intermeeting cut to zero", "2021-11-03 the taper announced"),
     "why_it_matters": "policy surprises are near zero BY CONSTRUCTION at the ZLB; the "
                       "intermeeting class lives here and is never pooled", "status": "SETTLED"},
    {"name": "the fastest hiking cycle", "start": "2022-03-16", "end": "2023-07-26",
     "regime": "525bp in sixteen months, four consecutive 75bp moves, QT two from June 2022",
     "markers": ("2022-06-15 the first 75bp after the WSJ leak", "2023-03-10 SVB"),
     "why_it_matters": "the surprise distribution is fat-tailed and skewed hawkish; pooling "
                       "it with the plateau understates every effect", "status": "SETTLED"},
    {"name": "the 5.25-5.50% plateau", "start": "2023-07-27", "end": "2024-09-17",
     "regime": "fourteen months unchanged; runoff caps cut in June 2024; RRP draining",
     "markers": ("2023-08-02 and 2023-11-01 the paired refundings", "2024-05-28 T+1"),
     "why_it_matters": "policy surprises near zero again; the refunding and plumbing "
                       "mechanisms dominate", "status": "SETTLED"},
    {"name": "the easing cycle", "start": "2024-09-18", "end": "2026-12-31",
     "regime": "a 50bp first cut, 25bp in November and December 2024, a pause through mid-2025, "
               "cuts resumed in September 2025",
     "markers": ("2024-09-18 the 50bp cut", "2025-09-17 cuts resumed"),
     "why_it_matters": "OPEN: the end date is a placeholder and the era is re-derived from the "
                       "decision ledger; the 2025 pause-then-cut sequence is where the dots' "
                       "revision sign mattered more than the decision", "status": "OPEN"},
    {"name": "market-design era: daily SPX expiries", "start": "2022-04-18", "end": "2026-12-31",
     "regime": "Tuesday/Thursday SPX expiries added, giving a daily expiry; 0DTE share of SPX "
               "volume rose past 40%",
     "markers": ("2022-04-18",), "why_it_matters": "dealer gamma resets daily; a pre-2022 opex "
                                                   "study measures a market that no longer "
                                                   "exists", "status": "OPEN"},
)

# --------------------------------------------------------------------------- access
ACCESS_CONSTRAINTS: tuple[dict[str, Any], ...] = (
    {"constraint": "no fed funds or SOFR future is quoted by this broker",
     "measured": "data/universe/universe.json holds no short-rate future",
     "consequence": "the FOMC surprise must be built from CME end-of-day settlements plus a live "
                    "13:55 ET snapshot; a meeting without the snapshot is UNMEASURED"},
    {"constraint": "no TIPS or real-yield series is on this box",
     "measured": "no real-yield symbol or series is loaded",
     "consequence": "US-M runs on the nominal UST10Y leg and says so; the real-yield beta of "
                    "gold is a transmission hypothesis, not a measured cell"},
    {"constraint": "US500/NAS100/US30/US2000 are broker CFDs on cash indices",
     "measured": "universe.json: asset_class Indices; the tape is the broker's synthetic Globex",
     "consequence": "the closing-auction print and the SOQ are external references; the CFD's "
                    "own close is the broker's and the two differ on expiry mornings"},
    {"constraint": "Bloomberg, Refinitiv, the WSJ, SpotGamma and commercial AIS are licensed",
     "measured": "their terms forbid machine extraction",
     "consequence": "registered machine_use_allowed=false, read only through public echoes; "
                    "their mechanisms are reconstructed from public data or declared UNMEASURED"},
    {"constraint": "SEC EDGAR is public but the two-lane order forbids single-name hunting",
     "measured": "the lane split is by asset class in universe_policy",
     "consequence": "only aggregates that move an index enter a cell; every single-name filing "
                    "is the event lane's"},
)
INSTITUTIONAL_FLOW_SOURCES: tuple[str, ...] = (
    "TIC major foreign holders and monthly net purchases", "H.4.1 foreign official custody",
    "ICI money market fund assets", "EPFR-style ETF flow aggregates (licensed; public echoes "
    "only)", "the NY Fed primary dealer statistics", "13F aggregate sector tilts")
SERIES: dict[str, str] = {
    "US_POLICY": "FRED:DFEDTARU", "US_CPI": "FRED:CPIAUCSL", "US_CORE_PCE": "FRED:PCEPILFE",
    "US_NFP": "FRED:PAYEMS", "US_TGA": "fiscaldata:operating_cash_balance",
    "US_RRP": "nyfed:rrp_take_up", "US_SOFR": "FRED:SOFR", "US_CRUDE_STOCKS": "EIA:WCRSTUS1",
    "US_GAS_STORAGE": "EIA:NW2_EPG0_SWO_R48_BCF", "US_COT": "CFTC:disaggregated+TFF",
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
    """The pack as a plain mapping: the twenty-one framework fields plus everything this pack
    knows that the framework has no field for, carried beside them so nothing is dropped."""
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
        "mission": MISSION,
    }


def _source_line(sc: Mapping[str, Any]) -> str:
    """One source as the framework's `::` string, layer tag included, roots kept inside."""
    return (f"{sc['id']} :: layer={sc['layer']} :: {sc['label']} :: "
            f"roots={'; '.join(sc['roots']) or 'NONE'} :: "
            f"queries={'; '.join(sc['queries']) or 'NONE'} :: "
            f"languages={','.join(sc['languages']) or 'NONE'} :: access={sc['access_label']} :: "
            f"credibility={sc['credibility']} :: predictive={sc['predictive_state']} :: "
            f"machine_use_allowed={sc['machine_use_allowed']} :: licence={sc['licence']}")


def _source_row(sc: Mapping[str, Any]) -> dict[str, Any]:
    """One source as a `country_lab.SourceRow` mapping. `verified` is False until a scout
    fetches the root: a typed root is not coverage."""
    return {"id": sc["id"], "layer": sc["layer"], "label": sc["label"], "roots": sc["roots"],
            "languages": sc["languages"], "licence": sc["licence"], "verified": False,
            "query_terms": sc["queries"],
            "notes": (f"access_label={sc['access_label']} | credibility={sc['credibility']} | "
                      f"predictive_state={sc['predictive_state']} | "
                      f"machine_use_allowed={sc['machine_use_allowed']} | {sc['notes']}")}


def lab_kwargs() -> dict[str, Any]:
    """The keyword set `libs.research.country_lab.CountryPack` is built from: the module tables
    in the shapes the framework's coercion reads best (sources as rows AND as tagged lines,
    positioning and miners as strings, absent layers as a mapping)."""
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
    """`libs.research.country_lab.CountryPack` when the framework is present, else the mapping.
    Imported lazily so this department stays importable on a tree where the framework is not."""
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
