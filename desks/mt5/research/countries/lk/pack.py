"""SRI LANKA: a defaulted island whose closures are lunar and whose prices are administered.

WHAT SRI LANKA IS AS A MARKET MECHANISM, AND WHY IT IS NOT A SMALLER INDIA. Six things belong to
this economy and to no other in the desk's book, and each is why a domain below exists rather
than a row in a generic frontier-economy domain:

  1. THE MARKET CLOSES ON THE FULL MOON. Every FULL MOON POYA DAY is a statutory public holiday:
     the banks shut, the Colombo Stock Exchange shuts, and the date moves with the moon rather
     than with a weekday rule. Twelve or thirteen times a year -- 2026 carries thirteen full
     moons and therefore an intercalary Adhi Poya -- the country's only cash market is closed on
     a day nothing else in the desk's calendar knows about. No other pack on this desk has a
     LUNAR MONTHLY closure; the Islamic packs have lunar ANNUAL feasts and the East Asian packs
     have lunar NEW YEARS. A liquidity study built on weekday rules measures the wrong days here
     in every month of the sample.

  2. THE SOVEREIGN DEFAULTED AND WAS RE-PAPERED WITH A GDP TRIGGER. On 12 April 2022 Sri Lanka
     announced a standstill on its external debt -- the first sovereign default in the country's
     history. The IMF Extended Fund Facility approved on 20 March 2023 (about USD 3bn over 48
     months) put the whole state on a QUARTERLY review clock with dated structural benchmarks,
     and the December 2024 bondholder exchange replaced the old ISBs with MACRO-LINKED BONDS
     whose coupon and principal step UP or DOWN against the IMF's own nominal-USD-GDP path. The
     sovereign's payoff is now a derivative on a statistic the state publishes, which is a
     mechanism and not a metaphor: the GDP print and the review calendar are the two clocks.

  3. THE POLICY RATE IS NEW AND SINGLE. The Central Bank of Sri Lanka ran an SDFR/SLFR CORRIDOR
     for a decade and replaced it with ONE Overnight Policy Rate, the OPR, with the standing
     facilities retained only as a band around it. The Monetary Policy Board meets on a
     pre-announced calendar of EIGHT reviews a year and the decision is released at 07:30
     Colombo -- 02:00 UTC, in the European pre-open, which is where its executable reach is.

  4. THE FUEL PRICE IS A PUBLISHED FORMULA ON A MONTHLY CLOCK. The Ceylon Petroleum Corporation
     revises retail petrol, diesel and kerosene at month end under the cost-reflective formula
     the IMF programme required, with the Public Utilities Commission on the electricity leg.
     The pass-through of Brent and the rupee into the domestic price is a scheduled administered
     event and the largest single input to the CCPI the Monetary Policy Board reads.

  5. TEA IS SOLD AT A WEEKLY AUCTION AND THE CROP WAS DESTROYED BY DECREE. The Colombo Tea
     Auction sits every Tuesday and Wednesday and is the price-discovery venue for essentially
     all Ceylon tea. In April 2021 the government banned chemical fertiliser imports outright;
     yields collapsed, and the ban is the cleanest policy-induced agricultural supply shock in
     the desk's book. NO TEA CONTRACT EXISTS ON THIS BROKER. The auction is therefore carried as
     an INPUT-side mechanism whose only executable reach is the beverage complex and the
     country's own export-earnings run-rate, and every reading on it says so.

  6. THE RUPEE IS MANAGED AND ABSENT. LKR floated in March 2022 (200 to about 370 in weeks),
     exporters are subject to a SURRENDER REQUIREMENT on proceeds, and the CBSL runs a spot
     window and publishes a daily indicative rate. None of that is quotable here: LKR is not in
     `data/universe/universe.json`. Every domestic mechanism therefore terminates in a regional
     cross, a soft, an energy leg, gold or the frontier-stress rate, and the rupee is an INPUT.

WHAT IS EXECUTABLE AND WHAT IS NOT. USDLKR, the ASPI and the S&P SL20, AWPLR, the weekly T-bill
auction, the restructured ISBs and their macro-linked coupons, the Colombo tea auction average
and the CPC pump price are all ABSENT from the broker registry. Every one is named in
`TRANSMISSION_TARGETS` with the broker symbols its mechanism reaches, so an absent instrument
produces a transmission hypothesis and never a cell that can never be filled (L1.49).

THE TWO-LANE ORDER. Sri Lankan market commentary is company-heavy -- John Keells, Dialog, Hayleys,
Commercial Bank, the plantation companies -- and every one of those is an EVENT-lane instrument.
They enter this pack only as ACTORS (a tea broker that runs the auction, an apparel group that
imports yarn, a terminal operator that counts boxes), and the instruments those actors move are
softs, energy, metals, the regional crosses and the frontier rate. No share CFD appears in any
instrument tuple in this file.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from typing import Any

# --------------------------------------------------------------------------- identity
CODE = "LK"
NAME = "Sri Lanka"
REGION_COMMAND = "asia"            # the framework's command; the forest is south_asia
REGION_DESK = "SOUTH_ASIA"
FOREST = "south_asia"
CURRENCY = "LKR"
FISCAL_YEAR_END = "12-31"          # the government's year is the calendar year; the budget is
                                   # presented in the last quarter for the year that follows
NATIVE_LANGUAGES: tuple[str, ...] = ("si", "ta", "en-LK")
COT_CURRENCY = ""                  # no CFTC contract exists for the rupee
EXPORT_ECONOMY = "manufacturing_exporter"   # apparel is ~45% of goods exports; tea second
RETAIL_LEVERAGE_REGIME = "restricted"       # margin FX by residents is forbidden under the
                                            # Foreign Exchange Act; CBSL gazettes warnings
MISSION = ("mine Sri Lanka as the lunar-calendar, administered-price, freshly-restructured "
           "frontier sovereign it is: the OPR reviews, the monthly full-moon Poya closure, the "
           "weekly Colombo Tea Auction, the month-end CPC fuel formula, the quarterly IMF EFF "
           "clock and the GDP trigger on the macro-linked bonds -- and route every one of them "
           "through the softs, energy, metals, regional crosses and frontier rate the broker "
           "actually quotes, because the rupee is not one of them")

#: The instruments this pack may compile a cell against. Every one is in the broker registry and
#: none is a single-name equity. The rupee itself is absent (see TRANSMISSION_TARGETS).
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "COTTON",                                   # the apparel chain's imported fibre
    "SUGAR", "WHEAT",                           # two administered-levy food imports
    "COFARA", "COFROB",                         # the only auction-priced beverage softs quoted
    "XBRUSD", "XTIUSD",                         # the CPC monthly formula's input legs
    "XAUUSD",                                   # reserves, pawning advances, the Dubai channel
    "USDINR",                                   # India: credit lines, ACU, arrivals, feeder trade
    "USDSGD", "USDJPY",                         # Colombo vs Singapore transhipment; Japan as
                                                # the second-largest bilateral creditor
    "USDCNH", "CHINAH",                         # the Chinese creditor and Hambantota channel
    "UST10Y",                                   # the frontier-stress discount rate on the MLBs
    "US500",                                    # global risk, the other side of the frontier flow
    "EURUSD",                                   # the GSP+ apparel market's currency
)

TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "USD/LKR spot and the CBSL daily indicative exchange rate",
     "venue": "interbank / Central Bank of Sri Lanka",
     "why": "the currency every mechanism here is about, absent from the broker; its moves are "
            "read through what the island then buys, sells and cannot pay for",
     "proxies": ("USDINR", "USDSGD", "XAUUSD")},
    {"name": "ASPI and S&P SL20", "venue": "Colombo Stock Exchange",
     "why": "no CFD is quoted; the CSE's own daily net-foreign line is the flow object instead",
     "proxies": ("US500", "USDINR")},
    {"name": "Colombo Tea Auction weekly average price (USD/kg) by elevation",
     "venue": "Colombo Tea Traders Association / the broking houses",
     "why": "the world's largest orthodox black-tea auction by value, and there is no tea "
            "contract on this broker at all; the auction is an INPUT observable",
     "proxies": ("COFARA", "COFROB")},
    {"name": "The restructured ISBs: the macro-linked bonds and the governance-linked bond",
     "venue": "OTC", "why": "the sovereign's stress premium and the only instrument on earth "
                            "whose coupon steps off Sri Lanka's own nominal-USD-GDP print",
     "proxies": ("UST10Y", "US500")},
    {"name": "AWPLR and the weekly Treasury bill / Treasury bond auction yields",
     "venue": "CBSL Public Debt Department / primary dealers",
     "why": "the domestic rate path and the consensus between Monetary Policy Reviews",
     "proxies": ("UST10Y", "USDINR")},
    {"name": "CPC and Lanka IOC retail fuel prices and the Litro LP gas price",
     "venue": "Ceylon Petroleum Corporation / Ministry of Energy",
     "why": "the administered pass-through of Brent and the rupee; the event of LK-E",
     "proxies": ("XBRUSD", "XTIUSD")},
    {"name": "CEB electricity tariff (PUCSL determinations)",
     "venue": "Public Utilities Commission of Sri Lanka",
     "why": "the second cost-reflective price the programme forced; quarterly determinations",
     "proxies": ("XBRUSD",)},
    {"name": "Colombo gold jewellery and pawning rate per sovereign (8 g)",
     "venue": "Sea Street jewellers / the licensed banks' pawning books",
     "why": "remittance-financed retail bullion and the banks' pawning advances are one book; "
            "the premium to the LBMA price times the indicative rate is the import-stress read",
     "proxies": ("XAUUSD",)},
    {"name": "Special Commodity Levy prices for sugar, wheat flour and milk powder",
     "venue": "Ministry of Finance gazettes / Sri Lanka Customs",
     "why": "an entire food-import basket priced by gazette rather than by market; the levy "
            "changes are dated and public",
     "proxies": ("SUGAR", "WHEAT")},
    {"name": "SLPA Colombo transhipment volume and the Indian feeder trade",
     "venue": "Sri Lanka Ports Authority", "why": "South Asia's transhipment hub; the volume is "
                                                  "an Asian trade-cycle observable with no "
                                                  "contract on this broker",
     "proxies": ("USDSGD", "USDINR")},
)

# --------------------------------------------------------------------------- the central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "Central Bank of Sri Lanka -- Monetary Policy Board",
    "short": "CBSL",
    "framework": "inflation_targeter",
    "committee": "the Monetary Policy Board created by the Central Bank of Sri Lanka Act No. 16 "
                 "of 2023, which split the old Monetary Board into a Governing Board (oversight) "
                 "and a Monetary Policy Board (rates): the Governor, the Deputy Governor in "
                 "charge of monetary policy, one more Deputy Governor and external members; the "
                 "Secretary to the Treasury sits on NEITHER, which is the point of the Act",
    "policy_instrument": "the Overnight Policy Rate (OPR), a SINGLE policy rate that replaced "
                         "the SDFR/SLFR corridor as the operating target, with the standing "
                         "deposit and lending facilities retained only as a narrow band around "
                         "it",
    "mandate": "domestic price stability as the primary objective under the 2023 Act, with a "
               "headline-CCPI inflation target agreed with the Ministry of Finance in a "
               "published Monetary Policy Framework Agreement (5% mid-point)",
    "decision_rule": "eight scheduled Monetary Policy Reviews a year on a pre-announced "
                     "calendar; the decision and the statement are released the same morning and "
                     "the Board's summary follows; an emergency meeting is its own event class "
                     "(2022-04-08, +700bp, was unscheduled and is the largest single move in the "
                     "bank's history)",
    "decision_calendar_rule": "eight reviews a year, published as an advance release calendar at "
                              "cbsl.gov.lk; the release is at 07:30 Asia/Colombo and the press "
                              "conference follows, so the minute is stamped from the release and "
                              "never assumed",
    #: VERIFIED decisions only. The dates the desk has actually read off a CBSL release.
    "decision_dates": ("2024-01-23", "2024-03-26", "2024-07-09", "2024-11-27"),
    "dates_status": "VERIFIED-ONLY. 2024-01-23 and 2024-03-26 are the two 50bp cuts, 2024-07-09 "
                    "the 25bp cut, and 2024-11-27 the announcement that replaced the SDFR/SLFR "
                    "corridor with the single Overnight Policy Rate. The rest of the eight-a-year "
                    "calendar is carried SEPARATELY in REPORTED_DECISION_DATES and is NOT pooled "
                    "with this sample; 2026 is NOT LISTED because the advance calendar for it has "
                    "not been read. The transition date to the OPR is the one fact in this pack "
                    "the desk has seen stated two ways (a 2024 announcement and a 2025 "
                    "operational date) and it is registered in ACCESS_CONSTRAINTS as DISPUTED "
                    "rather than resolved by preference -- no level cell is compiled on it",
    "decision_time_utc": "02:00",
    "announce_local": "07:30 Asia/Colombo (UTC+5:30, no DST); the statement PDF carries the date "
                      "and the wires carry the minute",
    "dst_rule": "Sri Lanka keeps UTC+5:30 all year; the UTC minute of a Colombo event never moves",
    "minutes_lag_days": 14,
    "publication_classes": ("monetary_policy_review", "monetary_policy_board_summary",
                            "weekly_economic_indicators", "monthly_external_sector_performance",
                            "official_reserve_assets", "annual_report",
                            "governor_press_conference"),
    "policy_rate_series": "CBSL:opr",
    "expected_rate_series": "UNMEASURED",
    "consensus_proxy": "the weekly Treasury bill cut-off yields (91/182/364 day, Wednesday) and "
                       "AWPLR between reviews; the local houses (First Capital, CAL, Frontier "
                       "Research) publish rate-decision previews that are the stated expectation",
    "consensus_proxy_trap": "the T-bill cut-off embeds the government's own funding need and the "
                            "CBSL's primary-market participation limits under the 2023 Act; a "
                            "cut-off move is not a decision expectation on its own",
    "reserves_clock": "official reserve assets are published MONTHLY in the first week for the "
                      "prior month end; an IMF tranche appears as a step, and the PBOC swap line "
                      "is disclosed inside the total with a usability caveat the desk carries",
    "programme": "IMF Extended Fund Facility approved 2023-03-20, about USD 3bn over 48 months, "
                 "with QUARTERLY reviews, quantitative performance criteria and dated structural "
                 "benchmarks; the reviews are what the budget, the tariff, the fuel formula and "
                 "the tax file are negotiated against",
    "off_cycle": ("2022-04-08 emergency +700bp (SDFR 13.50%, SLFR 14.50%)",
                  "2021-08-19 the first hike of the crisis cycle"),
    "root": "https://www.cbsl.gov.lk",
}

#: REPORTED, NOT VERIFIED. Dates the desk believes are Monetary Policy Review days and has NOT
#: read off a CBSL release. They exist here so the gap between the eight-a-year rule and the four
#: verified rows is VISIBLE rather than quietly absent (L1.28a), and `cbsl_policy_windows` runs
#: them as a separate, labelled arm that never pools with the verified sample.
REPORTED_DECISION_DATES: tuple[str, ...] = (
    "2024-05-07", "2024-08-27", "2025-03-26", "2025-07-23")

# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "CBSL daily indicative USD/LKR exchange rate",
     "local": "published each business morning, about 09:00 Asia/Colombo",
     "time_utc": "03:30", "time_utc_dst": "03:30", "dst_rule": "none (UTC+5:30 all year)",
     "instruments": ("USDINR", "USDSGD"), "window_minutes": 30,
     "why": "the official rupee reference customs, the fuel formula and the banks' boards read"},
    {"name": "Monetary Policy Review announcement",
     "local": "07:30 Asia/Colombo on the review day", "time_utc": "02:00",
     "time_utc_dst": "02:00", "dst_rule": "none",
     "instruments": ("USDINR", "XAUUSD", "UST10Y"), "window_minutes": 60,
     "why": "the OPR decision lands in the European pre-open, which is where it is executable"},
    {"name": "Colombo Tea Auction sale (Tuesday and Wednesday)",
     "local": "09:00-17:00 Asia/Colombo on the two sale days",
     "time_utc": "03:30", "time_utc_dst": "03:30", "dst_rule": "none",
     "instruments": ("COFARA", "COFROB"), "window_minutes": 480,
     "why": "the price discovery of essentially all Ceylon tea; no tea contract is quoted here, "
            "so the reach into this desk's tape is the beverage complex and is declared weak"},
    {"name": "CPC month-end retail fuel price revision",
     "local": "announced on the last day of the month, effective from midnight Asia/Colombo",
     "time_utc": "15:00", "time_utc_dst": "15:00", "dst_rule": "none",
     "instruments": ("XBRUSD", "XTIUSD"), "window_minutes": 120,
     "why": "the cost-reflective formula's monthly pass-through; the event of LK-E"},
    {"name": "Colombo sovereign gold rate per pawning sovereign (8 g)",
     "local": "set by the Sea Street trade each morning off the international price",
     "time_utc": "04:30", "time_utc_dst": "04:30", "dst_rule": "none",
     "instruments": ("XAUUSD",), "window_minutes": 60,
     "why": "the pawning advance the banks lend against; its premium to LBMA times the "
            "indicative rate is the import-restriction stress measure"},
    {"name": "LBMA gold price PM auction (the dollar leg of the Colombo rate)",
     "local": "15:00 Europe/London", "time_utc": "15:00", "time_utc_dst": "14:00",
     "dst_rule": "GMT/BST", "instruments": ("XAUUSD",), "window_minutes": 15,
     "why": "the reference the Colombo sovereign rate is derived from"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "CPC monthly fuel price revision", "kind": "month_end", "roll": "none",
     "window_utc": ("14:00", "18:00"), "instruments": ("XBRUSD", "XTIUSD"),
     "why": "the formula is applied at month end and the new price runs from midnight"},
    {"name": "Colombo Tea Auction sale week", "kind": "weekday", "weekday": 1, "roll": "none",
     "window_utc": ("03:30", "11:30"), "instruments": ("COFARA", "COFROB"),
     "why": "the sale sits every Tuesday and continues on Wednesday; the catalogue closes the "
            "week before, so the offered quantity is known ahead of the price"},
    {"name": "CBSL weekly Treasury bill auction", "kind": "weekday", "weekday": 2,
     "roll": "none", "window_utc": ("05:00", "09:00"), "instruments": ("UST10Y", "USDINR"),
     "why": "Wednesday; the cut-off yields are the between-review rate expectation"},
    {"name": "Month-end oil and food letter-of-credit settlements", "kind": "month_end",
     "roll": "previous", "window_utc": ("03:00", "11:00"),
     "instruments": ("XBRUSD", "USDINR", "WHEAT"),
     "why": "the importers' dollar demand clusters into the last business days; the 2021-22 LC "
            "refusals were a forced-flow regime of their own and are a dated era"},
    {"name": "Fiscal year end (31 December) and the two bank half-closes",
     "kind": "fiscal_year_end", "roll": "previous", "window_utc": ("03:00", "11:00"),
     "instruments": ("USDINR", "XAUUSD"),
     "why": "the government's year is the calendar year; 30 June and 31 December are BANK "
            "holidays for the closing of accounts and are not the same set as the market's"},
    {"name": "Quarterly IMF EFF review test dates", "kind": "quarter_end", "roll": "previous",
     "window_utc": ("03:00", "11:00"), "instruments": ("UST10Y", "USDINR"),
     "why": "net international reserves and the primary balance are tested at quarter ends and "
            "the review that follows is the tranche"},
)

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Colombo Stock Exchange (CSE) -- ASPI and S&P SL20",
     "index_symbols": (),
     "open_local": "09:30 (pre-open 09:00-09:30)", "close_local": "14:30",
     "open_utc": "04:00", "close_utc": "09:00", "dst_rule": "none (UTC+5:30)",
     "auction": "pre-open call 09:00-09:30; a closing-price auction sets the last trade",
     "expiry_rule": "no listed index derivative; settlement of equity trades is T+2",
     "holidays": "every statutory public holiday, which includes EVERY FULL MOON POYA DAY, the "
                 "two days of the Sinhala and Tamil New Year, Vesak and the day after it, Thai "
                 "Pongal, Eid, Deepavali, Good Friday, Mahasivarathri and Christmas",
     "notes": "NO CFD IS QUOTED on the ASPI or the S&P SL20, so the index enters only as a "
              "transmission target; the CSE publishes DAILY net foreign purchases and sales, "
              "which is the positioning series LK-K reads. Market-wide circuit breakers halt "
              "trading on a set intraday fall in the S&P SL20 and a per-security price band "
              "applies; in April 2022 the exchange suspended trading for five sessions from the "
              "18th, which is the only multi-day non-holiday closure in the modern record"},
    {"name": "Colombo Tea Auction (Colombo Tea Traders Association; Forbes & Walker, John "
             "Keells, Asia Siyaka and the other broking houses)",
     "index_symbols": (),
     "open_local": "09:00 Tuesday and Wednesday", "close_local": "about 17:00",
     "open_utc": "03:30", "close_utc": "11:30", "dst_rule": "none",
     "auction": "open outcry by elevation and grade, catalogued the week before the sale",
     "expiry_rule": "physical lots only; there is no forward or futures contract",
     "holidays": "Poya days and the public-holiday calendar move the sale within the week",
     "notes": "a PHYSICAL auction, not a financial exchange, and the only weekly price-discovery "
              "venue in the pack; its numbers reach the desk as data and never as an instrument"},
)

SESSION_WINDOWS: tuple[dict[str, Any], ...] = (
    {"name": "lk_cbsl_announcement", "start_utc": "01:30", "end_utc": "03:00",
     "notes": "the 07:30 Colombo Monetary Policy Review release and the indicative rate"},
    {"name": "lk_tea_auction", "start_utc": "03:30", "end_utc": "11:30",
     "notes": "the Tuesday/Wednesday Colombo sale and the brokers' market reports"},
    {"name": "lk_month_end_fuel", "start_utc": "14:00", "end_utc": "18:00",
     "notes": "the CPC price revision notice on the last day of the month"},
)

RELEASE_CLASSES: tuple[dict[str, Any], ...] = (
    {"name": "Colombo Consumer Price Index (CCPI)", "cadence": "monthly", "time_utc": "10:00",
     "source": "Department of Census and Statistics", "actual_series": "DCS:ccpi",
     "expected_series": "UNMEASURED",
     "notes": "released on the LAST WORKING DAY of the reference month, which is unusually early "
              "for a CPI and is why it and not the NCPI is the Board's headline target"},
    {"name": "National Consumer Price Index (NCPI)", "cadence": "monthly", "time_utc": "10:00",
     "source": "Department of Census and Statistics", "actual_series": "DCS:ncpi",
     "expected_series": "UNMEASURED",
     "notes": "around the 21st of the following month; the rural basket, three weeks behind"},
    {"name": "CBSL External Sector Performance (trade, remittances, tourism earnings)",
     "cadence": "monthly", "time_utc": "09:00", "source": "CBSL",
     "actual_series": "CBSL:external_sector", "expected_series": "UNMEASURED",
     "notes": "about the last week of the following month; the remittance and tourism lines are "
              "the two largest inflows and the tea and apparel lines the two largest exports"},
    {"name": "Official reserve assets", "cadence": "monthly", "time_utc": "09:00",
     "source": "CBSL", "actual_series": "CBSL:official_reserve_assets",
     "expected_series": "UNMEASURED",
     "notes": "first week for the prior month end; the PBOC swap component is disclosed with a "
              "usability condition and must never be read as free reserves"},
    {"name": "SLTDA monthly tourist arrivals", "cadence": "monthly", "time_utc": "06:00",
     "source": "Sri Lanka Tourism Development Authority", "actual_series": "SLTDA:arrivals",
     "expected_series": "UNMEASURED",
     "notes": "first days of the following month, by source market; India, Russia and the UK are "
              "the three that move the total"},
    {"name": "Colombo Tea Auction weekly sale averages and quantities", "cadence": "weekly",
     "time_utc": "11:30", "source": "Forbes & Walker / Asia Siyaka market reports",
     "actual_series": "CTA:auction_average", "expected_series": "UNMEASURED",
     "notes": "published the evening of the sale; the catalogued quantity is known days earlier, "
              "which is the only part of this mechanism that is PIT-safe ahead of the price"},
    {"name": "Weekly Treasury bill auction result", "cadence": "weekly", "time_utc": "08:00",
     "source": "CBSL Public Debt Department", "actual_series": "CBSL:tbill_cutoff",
     "expected_series": "UNMEASURED",
     "notes": "Wednesday; the 91/182/364-day cut-offs are the between-review expectation"},
    {"name": "IMF EFF review milestones (staff-level agreement, Board, disbursement)",
     "cadence": "quarterly", "time_utc": "UNMEASURED", "source": "IMF",
     "actual_series": "IMF:sri_lanka_reviews", "expected_series": "n/a",
     "notes": "three dated events weeks apart per review; pooling them blends three reactions"},
)

# --------------------------------------------------------------------------- holidays
#: The genuinely FIXED public holidays. Everything else in Sri Lanka's calendar moves: the Poya
#: days follow the moon, the New Year follows the solar transit, and the Islamic, Hindu and
#: Christian feasts follow their own calendars.
FIXED_NATIONAL: tuple[tuple[int, int, str], ...] = (
    (2, 4, "National Day (Independence Day)"),
    (5, 1, "May Day"),
    (12, 25, "Christmas Day"),
)
#: BANK holidays that are not public holidays: the half-yearly and yearly closing of accounts.
#: The banks and the money market shut; the exchange's observance is the one row this pack marks
#: UNVERIFIED rather than asserting either way.
BANK_HOLIDAYS: tuple[tuple[int, int, str], ...] = (
    (6, 30, "Bank Holiday (half-year closing of accounts)"),
    (12, 31, "Special Bank Holiday (year-end closing of accounts)"),
)

#: THE FULL MOON POYA DAYS -- Sri Lanka's own monthly closure, and the only lunar MONTHLY market
#: holiday in the desk's book. 2024 and 2025 are the gazetted dates; 2026 is PROJECTED from the
#: astronomical full moon in Asia/Colombo and carries THIRTEEN moons, so the Buddhist calendar
#: inserts an intercalary Adhi month whose naming the gazette settles and this pack does not.
#: Each row: (date, name, status).
POYA_DAYS: dict[int, tuple[tuple[date, str, str], ...]] = {
    2024: ((date(2024, 1, 25), "Duruthu Full Moon Poya Day", "ANNOUNCED"),
           (date(2024, 2, 23), "Navam Full Moon Poya Day", "ANNOUNCED"),
           (date(2024, 3, 24), "Medin Full Moon Poya Day", "ANNOUNCED"),
           (date(2024, 4, 23), "Bak Full Moon Poya Day", "ANNOUNCED"),
           (date(2024, 5, 23), "Vesak Full Moon Poya Day", "ANNOUNCED"),
           (date(2024, 5, 24), "Day following Vesak Full Moon Poya Day", "ANNOUNCED"),
           (date(2024, 6, 21), "Poson Full Moon Poya Day", "ANNOUNCED"),
           (date(2024, 7, 20), "Esala Full Moon Poya Day", "ANNOUNCED"),
           (date(2024, 8, 19), "Nikini Full Moon Poya Day", "ANNOUNCED"),
           (date(2024, 9, 17), "Binara Full Moon Poya Day", "ANNOUNCED"),
           (date(2024, 10, 17), "Vap Full Moon Poya Day", "ANNOUNCED"),
           (date(2024, 11, 15), "Ill Full Moon Poya Day", "ANNOUNCED"),
           (date(2024, 12, 14), "Unduvap Full Moon Poya Day", "ANNOUNCED")),
    2025: ((date(2025, 1, 13), "Duruthu Full Moon Poya Day", "ANNOUNCED"),
           (date(2025, 2, 12), "Navam Full Moon Poya Day", "ANNOUNCED"),
           (date(2025, 3, 13), "Medin Full Moon Poya Day", "ANNOUNCED"),
           (date(2025, 4, 12), "Bak Full Moon Poya Day", "ANNOUNCED"),
           (date(2025, 5, 12), "Vesak Full Moon Poya Day", "ANNOUNCED"),
           (date(2025, 5, 13), "Day following Vesak Full Moon Poya Day", "ANNOUNCED"),
           (date(2025, 6, 10), "Poson Full Moon Poya Day", "ANNOUNCED"),
           (date(2025, 7, 10), "Esala Full Moon Poya Day", "ANNOUNCED"),
           (date(2025, 8, 8), "Nikini Full Moon Poya Day", "ANNOUNCED"),
           (date(2025, 9, 7), "Binara Full Moon Poya Day", "ANNOUNCED"),
           (date(2025, 10, 6), "Vap Full Moon Poya Day", "ANNOUNCED"),
           (date(2025, 11, 5), "Ill Full Moon Poya Day", "ANNOUNCED"),
           (date(2025, 12, 4), "Unduvap Full Moon Poya Day", "ANNOUNCED")),
    2026: ((date(2026, 1, 3), "Duruthu Full Moon Poya Day", "PROJECTED"),
           (date(2026, 2, 2), "Navam Full Moon Poya Day", "PROJECTED"),
           (date(2026, 3, 3), "Medin Full Moon Poya Day", "PROJECTED"),
           (date(2026, 4, 2), "Bak Full Moon Poya Day", "PROJECTED"),
           (date(2026, 5, 1), "Vesak Full Moon Poya Day", "PROJECTED"),
           (date(2026, 5, 2), "Day following Vesak Full Moon Poya Day", "PROJECTED"),
           (date(2026, 5, 31), "Adhi (intercalary) Full Moon Poya Day", "PROJECTED"),
           (date(2026, 6, 30), "Poson Full Moon Poya Day", "PROJECTED"),
           (date(2026, 7, 29), "Esala Full Moon Poya Day", "PROJECTED"),
           (date(2026, 8, 28), "Nikini Full Moon Poya Day", "PROJECTED"),
           (date(2026, 9, 26), "Binara Full Moon Poya Day", "PROJECTED"),
           (date(2026, 10, 26), "Vap Full Moon Poya Day", "PROJECTED"),
           (date(2026, 11, 24), "Ill Full Moon Poya Day", "PROJECTED"),
           (date(2026, 12, 24), "Unduvap Full Moon Poya Day", "PROJECTED")),
}

#: Everything else that moves: the solar New Year, the Hindu feasts, the Islamic feasts on the
#: moon sighting, Good Friday on the Christian computus, and Deepavali.
MOVING_HOLIDAYS: dict[int, tuple[tuple[date, str, str], ...]] = {
    2024: ((date(2024, 1, 15), "Tamil Thai Pongal Day", "ANNOUNCED"),
           (date(2024, 3, 8), "Mahasivarathri Day", "ANNOUNCED"),
           (date(2024, 3, 29), "Good Friday", "ANNOUNCED"),
           (date(2024, 4, 10), "Id-Ul-Fitr (Ramazan Festival Day)", "ANNOUNCED"),
           (date(2024, 4, 12), "Day prior to Sinhala and Tamil New Year Day", "ANNOUNCED"),
           (date(2024, 4, 13), "Sinhala and Tamil New Year Day", "ANNOUNCED"),
           (date(2024, 6, 17), "Id-Ul-Alha (Hadji Festival Day)", "ANNOUNCED"),
           (date(2024, 9, 16), "Milad-un-Nabi (Holy Prophet's Birthday)", "ANNOUNCED"),
           (date(2024, 10, 31), "Deepavali Festival Day", "ANNOUNCED")),
    2025: ((date(2025, 1, 14), "Tamil Thai Pongal Day", "ANNOUNCED"),
           (date(2025, 2, 26), "Mahasivarathri Day", "ANNOUNCED"),
           (date(2025, 3, 31), "Id-Ul-Fitr (Ramazan Festival Day)", "ANNOUNCED"),
           (date(2025, 4, 13), "Day prior to Sinhala and Tamil New Year Day", "ANNOUNCED"),
           (date(2025, 4, 14), "Sinhala and Tamil New Year Day", "ANNOUNCED"),
           (date(2025, 4, 18), "Good Friday", "ANNOUNCED"),
           (date(2025, 6, 7), "Id-Ul-Alha (Hadji Festival Day)", "ANNOUNCED"),
           (date(2025, 9, 5), "Milad-un-Nabi (Holy Prophet's Birthday)", "ANNOUNCED"),
           (date(2025, 10, 20), "Deepavali Festival Day", "ANNOUNCED")),
    2026: ((date(2026, 1, 14), "Tamil Thai Pongal Day", "PROJECTED"),
           (date(2026, 2, 15), "Mahasivarathri Day", "PROJECTED"),
           (date(2026, 3, 20), "Id-Ul-Fitr (Ramazan Festival Day)", "PROJECTED"),
           (date(2026, 4, 3), "Good Friday", "ANNOUNCED"),
           (date(2026, 4, 13), "Day prior to Sinhala and Tamil New Year Day", "PROJECTED"),
           (date(2026, 4, 14), "Sinhala and Tamil New Year Day", "PROJECTED"),
           (date(2026, 5, 27), "Id-Ul-Alha (Hadji Festival Day)", "PROJECTED"),
           (date(2026, 8, 25), "Milad-un-Nabi (Holy Prophet's Birthday)", "PROJECTED"),
           (date(2026, 11, 8), "Deepavali Festival Day", "PROJECTED")),
}

#: One-off closures that no rule produces.
DECLARED_CLOSURES: dict[date, str] = {
    date(2024, 11, 14): "parliamentary general election day (declared public holiday)",
}


def _merge(out: dict[date, str], day: date, name: str) -> None:
    """Two holidays on one date are BOTH named. 2026 puts Vesak Poya on May Day and Unduvap Poya
    the day before Christmas; a table that kept only the last one would lose the Poya."""
    prior = out.get(day)
    out[day] = f"{prior} / {name}" if prior and name not in prior else name


def national_holidays(year: int) -> dict[date, str]:
    """Every gazetted public holiday: the three fixed days, every Poya, the moving feasts and
    the one-off declarations. Sri Lanka has NO weekend substitution: a holiday on a Saturday is
    simply lost, which is itself a fact a liquidity study must carry."""
    out: dict[date, str] = {}
    for m, d, name in FIXED_NATIONAL:
        _merge(out, date(year, m, d), name)
    for day, name, status in POYA_DAYS.get(year, ()):
        _merge(out, day, f"{name} [{status}]")
    for day, name, status in MOVING_HOLIDAYS.get(year, ()):
        _merge(out, day, f"{name} [{status}]")
    for day, name in DECLARED_CLOSURES.items():
        if day.year == year:
            _merge(out, day, name)
    return dict(sorted(out.items()))


def bank_holidays(year: int) -> dict[date, str]:
    """The public holidays plus the two closing-of-accounts bank holidays."""
    out = national_holidays(year)
    for m, d, name in BANK_HOLIDAYS:
        _merge(out, date(year, m, d), name)
    return dict(sorted(out.items()))


def market_holidays(year: int) -> dict[date, str]:
    """CSE closed days: the bank calendar restricted to weekdays, because the exchange does not
    open at the weekend and a Saturday holiday is not a closure the tape can see."""
    return {d: n for d, n in bank_holidays(year).items() if d.weekday() < 5}


def poya_days(year: int) -> dict[date, str]:
    """The full-moon closures alone -- the pack's own calendar mechanism."""
    return {d: f"{n} [{s}]" for d, n, s in POYA_DAYS.get(year, ())}


def announced_poya(year: int) -> list[date]:
    """Only the Poya dates the gazette has already fixed. A study that pools PROJECTED rows into
    the announced sample must say so: a projected full moon near local midnight can be a day off
    and an intercalary month's naming is the calendar committee's to settle."""
    return [d for d, _n, st in POYA_DAYS.get(year, ()) if st == "ANNOUNCED"]


def new_year_span(year: int) -> tuple[date, date] | None:
    """The two days of the Sinhala and Tamil New Year, when the whole island stops for a week in
    practice and the auction, the ports and the banks all thin out."""
    rows = [d for d, n, _s in MOVING_HOLIDAYS.get(year, ()) if "New Year" in n]
    return (min(rows), max(rows)) if rows else None


def is_market_holiday(day: date) -> bool:
    return day in market_holidays(day.year)


#: The resolved table `research.countries.check_pack` reads, derived from the functions above so
#: the two can never disagree. A table with no rule beside it cannot be extended, and a rule with
#: no table cannot be checked, so this pack carries both.
HOLIDAY_TABLE: dict[int, dict[str, str]] = {
    year: {d.isoformat(): n for d, n in national_holidays(year).items()}
    for year in (2024, 2025, 2026)
}

HOLIDAYS_RULE: dict[str, Any] = {
    "kind": "computed_from_rules_plus_declared_lunar_table",
    "rule": ("Sri Lanka's closures are gazetted by the Ministry of Public Administration. THREE "
             "are fixed by date: National Day 4 February, May Day 1 May, Christmas 25 December. "
             "EVERY FULL MOON POYA DAY is a public holiday and there are twelve or thirteen a "
             "year, set by the Buddhist calendar on the astronomical full moon in Asia/Colombo; "
             "Vesak carries a second day. The Sinhala and Tamil New Year is the solar transit, "
             "13-14 April in most years and 12-13 April when the transit falls a day earlier. "
             "Thai Pongal (14 or 15 January), Mahasivarathri and Deepavali follow the Hindu "
             "calendar; Id-Ul-Fitr, Id-Ul-Alha and Milad-un-Nabi follow the moon sighting and "
             "are known only days ahead; Good Friday follows the Christian computus. THERE IS NO "
             "WEEKEND SUBSTITUTION. Separately, 30 June and 31 December are BANK holidays for "
             "the closing of accounts and are not public holidays. The table below is DERIVED "
             "from the module's own functions, and every row carries ANNOUNCED or PROJECTED."),
    "authority": "the Ministry of Public Administration gazettes the public and bank holidays; "
                 "the Buddhist calendar sets the Poya days and the CBSL adds the two "
                 "closing-of-accounts bank holidays",
    "years": (2024, 2025, 2026),
    "weekend": "Saturday and Sunday",
    "national_rule": "the three fixed days plus every Poya, the two New Year days, Thai Pongal, "
                     "Mahasivarathri, Good Friday, the two Eids, Milad-un-Nabi and Deepavali",
    "market_rule": "the bank calendar on weekdays; the CSE observes the public holidays and the "
                   "pack marks the exchange's treatment of the 30 June / 31 December bank "
                   "holidays UNVERIFIED rather than asserting a closure it has not read",
    "poya_rule": "the full moon in Asia/Colombo (UTC+5:30). 2024 and 2025 rows are ANNOUNCED; "
                 "2026 rows are PROJECTED from the astronomical instant and a moon falling near "
                 "local midnight can move the gazetted day by one",
    "moving_feasts": "the Islamic feasts drift about eleven days earlier each solar year and "
                     "are fixed on the sighting; Deepavali and Mahasivarathri drift within a "
                     "month; the New Year is solar and moves by at most one day",
    "status_field": "every lunar and moving row carries ANNOUNCED or PROJECTED; the two are "
                    "never pooled in a sample",
    "known_dates": {
        "2024-04-12": "day prior to the New Year -- the transit fell on the 13th that year, so "
                      "the two-day block was 12-13 April and NOT 13-14",
        "2025-04-14": "Sinhala and Tamil New Year Day, with the 13th as the day prior",
        "2026-04-14": "Sinhala and Tamil New Year Day; the 13th is the day prior",
        "2026-05-01": "Vesak Poya falls on May Day: ONE closed day, not two, and a study that "
                      "counts holidays rather than closed dates double-counts it",
        "2026-05-31": "an intercalary Adhi Poya -- 2026 has thirteen full moons",
        "2022-04-18": "not a holiday: the CSE suspended trading for five sessions from this day, "
                      "the only multi-day non-holiday closure in the modern record",
    },
    "table": HOLIDAY_TABLE,
    "fn": market_holidays,
    "national_fn": national_holidays,
    "bank_fn": bank_holidays,
    "poya_fn": poya_days,
    "announced_poya_fn": announced_poya,
    "new_year_fn": new_year_span,
}

# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "CSE daily foreign purchases and sales (net foreign flow)",
     "root": "https://www.cse.lk/pages/trade-summary/trade-summary.component.html",
     "fields": ("foreign_purchases_lkr", "foreign_sales_lkr", "net_foreign_lkr", "turnover",
                "aspi", "sl20"),
     "frequency": "daily", "snapshot": "session close", "publish_utc": "09:30", "lag_days": 0,
     "licence": "free, public", "available": True,
     "why": "the only daily foreign-flow series the island publishes; the sign of the five-day "
            "sum is LK-K's object and the 2022 exodus is visible in it to the day",
     "pit_warning": "posted after the close; only a T+1 alignment is PIT-safe"},
    {"name": "Foreign holdings of Treasury bills and bonds",
     "root": "https://www.cbsl.gov.lk/en/statistics/economic-indicators",
     "fields": ("foreign_holdings_tbill", "foreign_holdings_tbond", "share_of_outstanding"),
     "frequency": "weekly", "snapshot": "Friday", "publish_utc": "09:00", "lag_days": 5,
     "licence": "free, public", "available": True,
     "why": "the rupee-debt leg of foreign positioning; it went to near zero through 2022 and "
            "its return is the cleanest single read of frontier risk appetite for Sri Lanka",
     "pit_warning": "five days stale on release; never a same-week conditioner"},
    {"name": "CBSL official reserve assets and the PBOC swap component",
     "root": "https://www.cbsl.gov.lk/en/statistics/statistical-tables/external-sector",
     "fields": ("gross_official_reserves_usd", "pboc_swap_usd", "usable_reserves_note"),
     "frequency": "monthly", "snapshot": "month end", "publish_utc": "09:00", "lag_days": 7,
     "licence": "free, public", "available": True,
     "why": "the programme's binding number; the swap line is inside the headline and carries a "
            "usability condition, so headline and usable reserves are two different series",
     "pit_warning": "a week stale; a study that uses the headline as usable reserves is "
                    "measuring a number the government itself could not spend in 2022"},
    {"name": "a CFTC or exchange-traded rupee positioning series",
     "root": "", "fields": (), "frequency": "n/a", "snapshot": "", "publish_utc": "",
     "lag_days": 0, "licence": "", "available": False,
     "why": "no LKR future or option trades on any exchange the desk can read",
     "pit_warning": "DOES NOT EXIST: rupee positioning is UNMEASURED and is never proxied by the "
                    "forward premium, which is an AWPLR and surrender-rule object"},
)

# --------------------------------------------------------------------------- terminology
#: SINHALA AND TAMIL ARE BOTH OFFICIAL LANGUAGES and they do not cover the same ground: the
#: plantation districts, the north and the east read Tamil, the south and the Sinhala business
#: press read Sinhala, and English reaches only the Colombo professional corner. A query in
#: English alone finds Daily FT and EconomyNext and misses the ground the fuel queue, the pawning
#: rate and the Poya week are actually discussed on.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "LK-A": ("ශ්‍රී ලංකා මහ බැංකුව", "මහ බැංකු අධිපති", "පොලී අනුපාතය",
             "මුදල් ප්‍රතිපත්ති සමාලෝචනය", "එක්දින ප්‍රතිපත්ති පොලී අනුපාතිකය", "උද්ධමනය",
             "இலங்கை மத்திய வங்கி", "வட்டி விகிதம்", "நாணயக் கொள்கை", "பணவீக்கம்",
             "Overnight Policy Rate", "OPR", "Monetary Policy Board", "Monetary Policy Review",
             "CCPI inflation"),
    "LK-B": ("ජාත්‍යන්තර මූල්‍ය අරමුදල", "ණය වැඩසටහන", "සමාලෝචනය", "වාරිකය", "කොන්දේසි",
             "சர்வதேச நாணய நிதியம்", "கடன் திட்டம்", "மறுஆய்வு", "தவணை",
             "IMF Extended Fund Facility", "EFF review", "structural benchmark",
             "staff-level agreement", "debt sustainability analysis"),
    "LK-C": ("ණය ප්‍රතිව්‍යුහගතකරණය", "බංකොලොත්භාවය", "ස්වෛරී බැඳුම්කර", "ණය හිමියන්",
             "கடன் மறுசீரமைப்பு", "இறையாண்மைப் பத்திரம்", "கடன் தவணை தவறல்",
             "macro-linked bond", "governance-linked bond", "ISB exchange",
             "bondholder committee", "Official Creditor Committee", "GDP trigger",
             "domestic debt optimisation"),
    "LK-D": ("රුපියල", "ඩොලරය", "විනිමය අනුපාතිකය", "විදේශ සංචිත", "ඩොලර් හිඟය",
             "ரூபாய்", "அமெரிக்க டொலர்", "அன்னிய செலாவணி இருப்பு", "பணமாற்று வீதம்",
             "indicative exchange rate", "surrender requirement", "CBSL spot window",
             "managed float", "open account imports"),
    "LK-E": ("ඉන්ධන මිල", "ඉන්ධන මිල සූත්‍රය", "ගෑස් මිල", "විදුලි ගාස්තු", "ඉන්ධන පෝලිම්",
             "எரிபொருள் விலை", "எரிவாயு விலை", "மின்சாரக் கட்டணம்",
             "CPC price formula", "cost-reflective pricing", "PUCSL determination",
             "Lanka IOC", "fuel pass QR", "power cut schedule"),
    "LK-F": ("තේ වෙන්දේසිය", "තේ නිෂ්පාදනය", "තේ අපනයනය", "කාබනික පොහොර", "පොහොර තහනම", "දළු",
             "தேயிலை ஏலம்", "தேயிலை உற்பத்தி", "உரத் தடை", "தோட்டத் தொழிலாளர்",
             "Colombo Tea Auction", "elevation grades", "Forbes and Walker market report",
             "Tea Board production", "green leaf price"),
    "LK-G": ("ඇඟලුම් කර්මාන්තය", "ඇඟලුම් අපනයන", "නිදහස් වෙළඳ කලාප",
             "ஆடைத் தொழில்", "ஆடை ஏற்றுமதி",
             "JAAF", "EU GSP Plus", "GSP Plus conditionality", "apparel export earnings",
             "yarn and fabric imports", "board of investment zones"),
    "LK-H": ("විදේශ රැකියා", "සේවක ප්‍රේෂණ", "විදේශ සේවා නියුක්ති කාර්යාංශය", "රත්තරන් මිල", "උකස්",
             "வெளிநாட்டு வேலைவாய்ப்பு", "பணம் அனுப்புதல்", "தங்க விலை", "அடகு",
             "SLBFE departures", "worker remittances", "undiyal hawala",
             "gold pawning advances"),
    "LK-I": ("සංචාරක පැමිණීම්", "සංචාරක ව්‍යාපාරය", "හෝටල් ආදායම",
             "சுற்றுலாப் பயணிகள்", "சுற்றுலாத் துறை",
             "SLTDA monthly arrivals", "arrivals by source market", "Easter Sunday attacks",
             "tourism earnings"),
    "LK-J": ("කොළඹ වරාය", "හම්බන්තොට වරාය", "වරාය නගරය", "ප්‍රතිනැව්ගත කිරීම",
             "கொழும்புத் துறைமுகம்", "துறைமுக நகரம்",
             "SLPA throughput", "transhipment TEU", "Colombo West International Terminal",
             "China Merchants Port", "Hambantota lease"),
    "LK-K": ("කොළඹ කොටස් වෙළඳපොල", "සියලුම කොටස් මිල දර්ශකය", "කොටස් වෙළඳාම නැවැත්වීම",
             "විදේශ ආයෝජන",
             "கொழும்பு பங்குச் சந்தை", "பங்கு வர்த்தகம்",
             "ASPI", "S&P SL20", "circuit breaker halt", "net foreign purchases", "CSE turnover"),
    "LK-L": ("පෝය දිනය", "පුර පසළොස්වක පෝය දිනය", "වෙසක් පෝය", "පොසොන් පෝය",
             "සිංහල හා දෙමළ අලුත් අවුරුද්ද", "බැංකු නිවාඩු", "රජයේ නිවාඩු",
             "பௌர்ணமி தினம்", "தைப்பொங்கல்", "சித்திரைப் புத்தாண்டு", "வங்கி விடுமுறை",
             "தீபாவளி",
             "Poya holiday", "full moon Poya day", "bank holiday 30 June", "market closed"),
    "LK-M": ("සීනි බද්ද", "විශේෂ වෙළඳ භාණ්ඩ බද්ද", "සහල් මිල", "කිරිපිටි මිල", "ආනයන සීමා",
             "පාන් මිල",
             "சீனி வரி", "அரிசி விலை", "பால்மா விலை", "இறக்குமதிக் கட்டுப்பாடு",
             "Special Commodity Levy", "sugar tax scam", "wheat flour price", "Prima Ceylon",
             "import restrictions gazette"),
}

# --------------------------------------------------------------------------- the ten layers
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
    """One class of source with the roots a crawler starts from and its three INDEPENDENT
    labels. `queries` are native-script terms, never translations. `machine_use_allowed=True`
    registers ground whose terms forbid extraction: never scraped, never omitted."""
    if layer not in SOURCE_LAYERS:
        raise ValueError(f"source {sid}: layer {layer!r} not one of {list(SOURCE_LAYERS)}")
    if access_label not in ACCESS_LABELS:
        raise ValueError(f"source {sid}: access_label {access_label!r}")
    if credibility not in CREDIBILITY_LABELS:
        raise ValueError(f"source {sid}: credibility {credibility!r}")
    if predictive_state not in PREDICTIVE_STATES:
        raise ValueError(f"source {sid}: predictive_state {predictive_state!r}")
    return {"id": sid, "label": label, "layer": layer, "roots": _seq(roots),
            "queries": _seq(queries), "languages": _seq(languages),
            "access_label": access_label, "credibility": credibility,
            "predictive_state": predictive_state,
            "machine_use_allowed": bool(machine_use_allowed), "licence": licence, "notes": notes}


def absent_layer(layer: str, reason: str) -> dict[str, Any]:
    """A layer this country has nothing in, declared BY NAME with the reason (L1.28a)."""
    if layer not in SOURCE_LAYERS:
        raise ValueError(f"absent layer {layer!r}")
    return {"id": f"absent_{layer}", "label": f"NO SOURCE IN THIS LAYER: {layer}", "layer": layer,
            "roots": (), "queries": (), "languages": (), "access_label": "ACCESS_UNCLEAR",
            "credibility": "UNKNOWN", "predictive_state": "UNTESTED",
            "machine_use_allowed": False, "licence": "n/a",
            "notes": f"DECLARED ABSENT, NOT BLANK: {reason}"}


SOURCE_CLASSES: tuple[dict[str, Any], ...] = (
    # ---- official
    source_class(
        "lk_cbsl", "Central Bank of Sri Lanka: monetary policy, external sector, reserves, "
                   "weekly indicators, debt", layer="official",
        roots=("https://www.cbsl.gov.lk/en/monetary-policy",
               "https://www.cbsl.gov.lk/en/statistics/economic-indicators",
               "https://www.cbsl.gov.lk/en/news/press-releases",
               "https://www.cbsl.gov.lk/en/publications"),
        queries=("මුදල් ප්‍රතිපත්ති සමාලෝචනය", "පොලී අනුපාතය", "විදේශ සංචිත", "සේවක ප්‍රේෂණ",
                 "நாணயக் கொள்கை மறுஆய்வு", "வட்டி விகிதம்", "அன்னிய செலாவணி இருப்பு",
                 "Monetary Policy Review", "Overnight Policy Rate", "official reserve assets",
                 "external sector performance", "weekly economic indicators"),
        languages=("en", "si", "ta"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public (CBSL website terms)",
        notes="the review statements are dated and released at 07:30 Colombo; the Sinhala and "
              "Tamil press releases are posted beside the English and are often the only place "
              "a governor's plain-language framing appears"),
    source_class(
        "lk_dcs_treasury", "Department of Census and Statistics and the Treasury: CCPI, NCPI, "
                           "GDP, trade, the budget and the fiscal tables", layer="official",
        roots=("http://www.statistics.gov.lk/InflationAndPrices",
               "http://www.statistics.gov.lk/NationalAccounts",
               "https://www.treasury.gov.lk/web/fiscal-policy",
               "https://www.treasury.gov.lk/api/file/budget"),
        queries=("උද්ධමනය", "පාරිභෝගික මිල දර්ශකය", "දළ දේශීය නිෂ්පාදිතය", "අයවැය",
                 "பணவீக்கம்", "நுகர்வோர் விலைக் குறியீடு", "வரவு செலவுத் திட்டம்",
                 "Colombo Consumer Price Index", "National Consumer Price Index",
                 "national accounts GDP", "budget speech", "fiscal management report"),
        languages=("en", "si", "ta"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the CCPI lands on the LAST WORKING DAY of the reference month -- earlier than "
              "almost any CPI in the world -- and the nominal-USD-GDP series published here is "
              "the number the macro-linked bonds' step-ups key off, which makes a statistical "
              "release a coupon event"),
    source_class(
        "lk_energy_utilities", "Ceylon Petroleum Corporation, the Ministry of Energy and the "
                               "Public Utilities Commission: fuel, LP gas and electricity",
        layer="official",
        roots=("https://ceypetco.gov.lk/marketing-sales/", "https://www.pucsl.gov.lk",
               "https://energy.gov.lk"),
        queries=("ඉන්ධන මිල සංශෝධනය", "ඉන්ධන මිල සූත්‍රය", "විදුලි ගාස්තු සංශෝධනය",
                 "எரிபொருள் விலை திருத்தம்", "மின்சாரக் கட்டண மாற்றம்",
                 "fuel price revision", "cost reflective pricing formula",
                 "PUCSL tariff determination", "LP gas price"),
        languages=("en", "si", "ta"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the month-end revision is dated and effective at midnight; the PUCSL publishes "
              "the determination papers, which carry the formula's inputs and are the only "
              "public statement of the pass-through coefficients"),
    source_class(
        "lk_imf", "IMF Sri Lanka country page: staff reports, EFF reviews, Board decisions, "
                  "debt sustainability analyses", layer="official",
        roots=("https://www.imf.org/en/Countries/LKA",),
        queries=("Sri Lanka Extended Fund Facility", "staff-level agreement", "second review",
                 "structural benchmarks", "net international reserves",
                 "debt sustainability analysis", "governance diagnostic"),
        languages=("en",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the staff report's conditionality tables date every structural benchmark and its "
              "nominal-USD-GDP path is the reference the macro-linked bonds are written against; "
              "LK-B and LK-C both clock off this page"),
    source_class(
        "lk_cse_sec", "Colombo Stock Exchange and the Securities and Exchange Commission: "
                      "indices, daily foreign flow, halts, rule changes", layer="official",
        roots=("https://www.cse.lk/pages/trade-summary/trade-summary.component.html",
               "https://www.cse.lk/pages/announcement/announcement.component.html",
               "https://www.sec.gov.lk"),
        queries=("කොටස් වෙළඳපොල දෛනික සාරාංශය", "විදේශ ආයෝජන",
                 "பங்குச் சந்தை அறிக்கை",
                 "daily trade summary", "foreign purchases and sales", "market halt",
                 "circuit breaker", "SEC directive"),
        languages=("en", "si", "ta"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the daily net-foreign table is the positioning series LK-K reads; the exchange "
              "itself has no CFD, so nothing here is ever an instrument"),
    # ---- institutional
    source_class(
        "lk_broker_research", "Local research houses publishing openly: First Capital, Capital "
                              "Alliance (CAL), NDB Securities, Asia Securities, Frontier "
                              "Research, Softlogic", layer="institutional",
        roots=("https://www.firstcapital.lk/research/", "https://www.cal.lk/research/",
               "https://www.asiasecurities.net/research",
               "https://www.frontiergroup.info/insights"),
        queries=("Monetary Policy Review preview", "policy rate expectation", "Sri Lanka "
                 "strategy", "yield curve outlook", "reserves adequacy", "ISB restructuring "
                 "note", "tea and apparel earnings"),
        languages=("en",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free notes; some behind registration",
        notes="the pre-review previews these houses publish are the stated consensus LK-A "
              "measures the surprise against; kept as the expectation source, never as a view"),
    source_class(
        "lk_trade_bodies", "Trade bodies: the Colombo Tea Traders Association, the Planters' "
                           "Association, JAAF (apparel), the Ceylon Chamber of Commerce, the "
                           "Shippers' Council, the Bankers' Association", layer="institutional",
        roots=("https://www.colombotea.com", "https://www.ppa.lk",
               "https://www.jaafsl.com", "https://www.chamber.lk"),
        queries=("තේ වෙන්දේසිය සාමාන්‍ය මිල", "ඇඟලුම් අපනයන", "தேயிலை ஏல விலை",
                 "auction average price", "catalogued quantity", "apparel export target",
                 "GSP Plus", "freight surcharge", "plantation wage"),
        languages=("en", "si", "ta"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the Tea Traders Association runs the auction and publishes the catalogued "
              "quantity BEFORE the sale, which is the one PIT-safe half of LK-F; the Planters' "
              "Association is where the fertiliser-ban yield loss was first quantified"),
    # ---- academic
    source_class(
        "lk_academic", "Institute of Policy Studies of Sri Lanka, Advocata, CBSL Staff Studies, "
                       "the universities of Colombo, Peradeniya and Moratuwa, RePEc/SSRN",
        layer="academic",
        roots=("https://www.ips.lk/publications/", "https://www.advocata.org/research",
               "https://www.cbsl.gov.lk/en/publications/other-publications/staff-studies",
               "https://ideas.repec.org/"),
        queries=("exchange rate pass-through Sri Lanka", "organic fertiliser ban yield",
                 "remittances Sri Lanka determinants", "monetary transmission Sri Lanka",
                 "sovereign default Sri Lanka", "tea auction price formation",
                 "tourism arrivals forecasting Sri Lanka"),
        languages=("en",), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="open access / publisher terms",
        notes="the fertiliser-ban yield papers are the mechanism source for LK-F and the "
              "pass-through papers for LK-D and LK-E; they are hypotheses until the desk "
              "reproduces them on its own tape"),
    # ---- practitioner
    source_class(
        "lk_english_business_press", "Daily FT, EconomyNext, Daily Mirror Business, the Sunday "
                                     "Times Business Times, The Morning Business",
        layer="practitioner",
        roots=("https://www.ft.lk", "https://economynext.com",
               "https://www.dailymirror.lk/business", "https://www.sundaytimes.lk/business"),
        queries=("policy rate decision", "reserves rise", "tea auction average", "fuel price "
                 "revised", "IMF review", "bondholder talks", "apparel exports", "tourist "
                 "arrivals", "import restrictions lifted", "sugar levy"),
        languages=("en",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="EconomyNext carries the most careful monetary-operations reporting in the country "
              "and is often the only place a standing-facility or swap-line detail is stated; "
              "Daily FT reprints the auction averages the evening of the sale"),
    source_class(
        "lk_sinhala_tamil_press", "Sinhala and Tamil business pages: Lankadeepa, Divaina, "
                                  "Silumina, Deshaya (si); Virakesari, Thinakkural, Thinakaran "
                                  "(ta)", layer="practitioner",
        roots=("https://www.lankadeepa.lk/business", "https://divaina.lk",
               "https://www.virakesari.lk/category/business",
               "https://www.thinakkural.lk"),
        queries=("ඩොලරය ඉහළට", "ඉන්ධන මිල අඩු වෙයි", "රත්තරන් මිල", "උකස් පොලිය", "සීනි මිල",
                 "தங்க விலை உயர்வு", "எரிபொருள் விலை குறைப்பு", "அரிசி விலை",
                 "வங்கி விடுமுறை"),
        languages=("si", "ta"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="the Sinhala and Tamil pages report the pawning rate, the queue and the pump price "
              "hours before the English tables and cover the plantation and northern districts "
              "the Colombo English press does not; the ground LK-E and LK-H live on"),
    # ---- retail ecology
    source_class(
        "lk_retail_forums", "CSE retail communities: r/srilanka and r/SriLankaStocks, the "
                            "Facebook investor groups, Sinhala YouTube finance channels, the "
                            "Elakiri forum", layer="retail_ecology",
        roots=("https://www.reddit.com/r/srilanka/",
               "https://www.youtube.com/results?search_query=කොටස්+වෙළඳපොල",
               "https://www.elakiri.com"),
        queries=("කොටස් මිලදී ගන්නේ කොහොමද", "කොටස් වෙළඳපොල අද", "ඩොලර් ගන්නේ කොහෙන්ද",
                 "பங்கு சந்தை இன்று", "CSE tips", "ASPI today", "best stocks sri lanka"),
        languages=("si", "ta", "en"), access_label="PUBLIC_SOCIAL", credibility="FRINGE",
        predictive_state="UNTESTED", licence="platform terms; public posts only",
        notes="KEPT AT LOW WEIGHT: single-name tips belong to the event lane, but the retail "
              "crowd's dollar, fuel-queue and pawning vocabulary DATES the stress episodes LK-D "
              "and LK-E study more precisely than any official series does"),
    source_class(
        "lk_forex_signal_sellers", "Sinhala and Tamil 'forex signal' and MT4/MT5 EA sellers "
                                   "targeting Sri Lankan retail on YouTube, Telegram and TikTok",
        layer="retail_ecology",
        roots=("https://www.youtube.com/results?search_query=forex+trading+sinhala",
               "https://t.me/s/forexsrilanka"),
        queries=("ෆොරෙක්ස් ට්‍රේඩින් සිංහලෙන්", "ගෝල්ඩ් සිග්නල්", "forex sinhala course",
                 "gold signals sri lanka", "prop firm sri lanka"),
        languages=("si", "ta", "en"), access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="platform terms; public posts only",
        notes="margin FX by residents is FORBIDDEN under the Foreign Exchange Act and the CBSL "
              "gazettes warning lists naming the platforms; the ecology is kept because the "
              "offshore XAUUSD retail base it feeds is a real stop-cluster observable and "
              "because the warning gazettes themselves are dated events. Nothing here is edge"),
    # ---- app ecosystem
    source_class(
        "lk_fintech_apps", "LankaPay, LANKAQR and JustPay, eZ Cash and mCash, FriMi, the banks' "
                           "own apps and the CSE mobile trading app; CBSL payment statistics",
        layer="app_ecosystem",
        roots=("https://www.cbsl.gov.lk/en/payments-and-settlements",
               "https://www.lankapay.net", "https://www.cse.lk/pages/mobile/mobile.component.html"),
        queries=("ඩිජිටල් ගෙවීම්", "ලංකා කිව් ආර්", "டிஜிட்டல் கொடுப்பனவு",
                 "LANKAQR transactions", "JustPay volume", "payment system statistics",
                 "mobile trading account"),
        languages=("si", "ta", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="CBSL statistics free; app stores public",
        notes="the CBSL's payments statistics are quarterly and carry the retail digital flow; "
              "the inward-remittance apps' share of the total is the banking-channel measure "
              "LK-H needs to tell a remittance fall from a channel shift to undiyal"),
    source_class(
        "lk_p2p_commentary", "Press coverage of the USDT-rupee peer-to-peer premium during the "
                             "2021-22 exchange controls", layer="app_ecosystem",
        roots=("https://economynext.com/?s=crypto+rupee",
               "https://www.ft.lk/?s=cryptocurrency+central+bank"),
        queries=("ක්‍රිප්ටෝ මුදල්", "USDT rupee premium", "CBSL crypto warning",
                 "P2P dollar rate sri lanka"),
        languages=("si", "en"), access_label="PUBLIC_WITH_TERMS", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="publisher terms",
        notes="PUBLIC COMMENTARY ONLY: no venue feed, no order book, no exchange named as a "
              "source (mandate 2026-08-18). The premium is an LKR stress observable reported in "
              "the press and is carried at low weight beside the black-market rate reports"),
    # ---- media
    source_class(
        "lk_broadcast_wire", "Ada Derana (en/si/ta), Hiru News, Newsfirst, Sirasa and the "
                             "state's Daily News and Dinamina", layer="media",
        roots=("https://www.adaderana.lk/business-news/", "https://sinhala.adaderana.lk",
               "https://www.newsfirst.lk/category/business/", "https://www.hirunews.lk"),
        queries=("මහ බැංකුවේ නිවේදනය", "ඉන්ධන මිල ගැන නිවේදනයක්", "රත්තරන් මිල අද",
                 "மத்திய வங்கி அறிவிப்பு", "எரிபொருள் விலை அறிவிப்பு",
                 "central bank announces", "fuel price announcement", "gold rate today"),
        languages=("si", "ta", "en"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="the broadcast minute of a CBSL or CPC announcement is the best public stamp when "
              "the release itself carries only a date; Ada Derana's Sinhala feed is usually "
              "first and its timestamp is the one LK-A's intraday window is anchored on"),
    source_class(
        "lk_licensed_terminals", "LSEG/Refinitiv, Bloomberg and the paid local data vendors "
                                 "carrying LKR ticks and ISB prices", layer="media",
        roots=("https://www.lseg.com/en/data-analytics",),
        queries=("LKR interbank tick", "Sri Lanka ISB indicative price"),
        languages=("en",), access_label="LICENSED", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="subscription; terms forbid machine extraction",
        machine_use_allowed=True,
        notes="REGISTERED, NEVER SCRAPED: the intraday LKR tick and the restructured-bond "
              "indicative prices live here behind a paywall. The desk reads only the public "
              "headlines, and the CBSL indicative rate is the PIT record it uses instead"),
    # ---- archive
    source_class(
        "lk_archive", "CBSL Annual Report and Economic and Social Statistics, the DCS "
                      "Statistical Abstract, the budget speech archive, Hansard, and "
                      "web.archive.org snapshots of the Ceypetco price tables", layer="archive",
        roots=("https://www.cbsl.gov.lk/en/publications/economic-and-financial-reports/"
               "annual-reports",
               "http://www.statistics.gov.lk/Publication/StatisticalAbstract",
               "https://www.parliament.lk/en/business-of-parliament/hansards",
               "https://web.archive.org/web/*/ceypetco.gov.lk/marketing-sales/*"),
        queries=("වාර්ෂික වාර්තාව", "සංඛ්‍යාලේඛන සංග්‍රහය", "ஆண்டறிக்கை",
                 "Annual Report Central Bank", "Economic and Social Statistics",
                 "Statistical Abstract", "budget speech archive", "Hansard fuel price"),
        languages=("en", "si", "ta"), access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the CBSL Annual Report lands in the second quarter and carries the crop, "
              "remittance, arrival and reserve tables of the whole year; the Ceypetco price "
              "page is OVERWRITTEN on every revision, so the Wayback snapshots are the only "
              "vintage record of the administered price the desk can reconstruct"),
    # ---- physical economy
    source_class(
        "lk_physical", "Sri Lanka Tea Board production and exports, SLPA port throughput, SLTDA "
                       "arrivals, SLBFE departures, CEB generation, the Department of "
                       "Meteorology and the Irrigation Department reservoir levels",
        layer="physical_economy",
        roots=("https://www.srilankatea.lk/statistics/", "https://www.slpa.lk/port-colombo/"
               "statistics", "https://www.sltda.gov.lk/en/statistics",
               "http://www.slbfe.lk/page.php?LID=1&MID=204", "https://www.meteo.gov.lk"),
        queries=("තේ නිෂ්පාදනය මාසික", "වරාය බහාලුම් ප්‍රමාණය", "සංචාරක පැමිණීම්",
                 "විදේශගත ශ්‍රමිකයන්", "මෝසම් වර්ෂාපතනය",
                 "தேயிலை உற்பத்தி", "துறைமுக கொள்கலன்", "சுற்றுலா வருகை",
                 "monthly tea production", "container throughput", "monsoon outlook",
                 "reservoir storage"),
        languages=("en", "si", "ta"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the Tea Board's monthly production series is where the 2021-22 fertiliser ban "
              "shows first and largest; the Irrigation Department's reservoir levels lead the "
              "CEB's hydro share, which leads the fuel-oil burn the import bill pays for"),
    source_class(
        "lk_ais_osm", "Port-call and AIS ground for Colombo and Hambantota through the public "
                      "aggregators, and OpenStreetMap's terminal and berth geometry",
        layer="physical_economy",
        roots=("https://www.marinetraffic.com/en/ais/details/ports/lk",
               "https://www.openstreetmap.org/relation/536780",
               "https://overpass-turbo.eu"),
        queries=("Colombo port calls", "Hambantota bunkering call", "CWIT berth",
                 "transhipment feeder vessel", "harbour=port Sri Lanka"),
        languages=("en",), access_label="ACCESS_UNCLEAR", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="OSM is ODbL; the AIS aggregators' free tiers "
                                             "carry terms that limit bulk extraction",
        machine_use_allowed=True,
        notes="REGISTERED, NOT SCRAPED: the AIS aggregators' terms forbid bulk extraction on the "
              "free tier and the desk does not hold a licence, so port calls are UNMEASURED and "
              "the SLPA monthly throughput is the series actually used. The OSM geometry is "
              "ODbL and usable; it is what lets a berth be named rather than guessed"),
    source_class(
        "lk_usda_fao", "USDA FAS GAIN reports and FAO GIEWS for Sri Lanka rice, sugar, wheat, "
                       "cotton and tea", layer="physical_economy",
        roots=("https://fas.usda.gov/data/search?f%5B0%5D=country%3A%22Sri%20Lanka%22",
               "https://www.fao.org/giews/countrybrief/country.jsp?code=LKA"),
        queries=("Sri Lanka grain and feed annual", "Sri Lanka sugar annual",
                 "Sri Lanka cotton and products", "GIEWS Sri Lanka", "rice import forecast"),
        languages=("en",), access_label="OPEN_DATA", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="public domain (US government work)",
        notes="the import forecasts the softs market actually reads for Sri Lanka, and the only "
              "outside quantification of the fertiliser ban's rice and tea losses that is dated"),
    # ---- source graph
    source_class(
        "lk_source_graph", "Who cites whom: the CBSL -> local research houses -> Daily FT and "
                           "EconomyNext -> the Sinhala and Tamil press -> the Facebook groups, "
                           "and the IMF -> Treasury -> PUCSL/CPC notification chain",
        layer="source_graph",
        roots=("https://www.cbsl.gov.lk/en/news/press-releases", "https://economynext.com",
               "https://www.ft.lk"),
        queries=("according to the Central Bank", "citing the IMF staff report",
                 "First Capital Research said", "මහ බැංකු ආරංචි මාර්ග", "ආරංචි මාර්ග පවසන පරිදි",
                 "வட்டாரங்கள் தெரிவிக்கின்றன"),
        languages=("en", "si", "ta"), access_label="PUBLIC", credibility="UNKNOWN",
        predictive_state="UNTESTED", licence="derived from the public sources above",
        notes="'ආරංචි මාර්ග පවසන පරිදි' (according to sources) is the Sinhala marker for the "
              "unattributed leak that precedes a fuel revision or a levy gazette by a day; the "
              "graph is how a leak is told from a repost of an earlier report"),
)

LAYER_ABSENCES: dict[str, str] = {}


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
        if layer not in out:
            continue
        for q in sc.get("queries", ()):
            if q not in out[layer]:
                out[layer].append(q)
    return {k: tuple(v) for k, v in out.items()}


def source_layer_coverage() -> dict[str, Any]:
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


# --------------------------------------------------------------------------- datasets
DATASETS: tuple[dict[str, Any], ...] = (
    {"name": "CBSL policy rate decisions and Monetary Policy Review statements", "source": "CBSL",
     "coverage": "2003 onward (the OPR series from the 2024 transition)", "frequency": "8 per year",
     "publication_lag_days": 0.0, "revisions": "never revised", "licence": "free, public",
     "history_from": "2003-01", "pit_feasible": True,
     "assets": ("USDINR", "XAUUSD", "UST10Y"),
     "mechanism_families": ("policy_surprise", "event_reaction"),
     "how_to_fetch": "cbsl.gov.lk/en/monetary-policy -- the review PDF and the press release; "
                     "the 07:30 Colombo release time is stamped from the wire, never assumed. "
                     "THE SERIES BREAKS at the OPR transition: an SDFR/SLFR level before it and "
                     "an OPR level after are not the same object and must not be spliced"},
    {"name": "CBSL official reserve assets and the PBOC swap component", "source": "CBSL",
     "coverage": "2001 onward", "frequency": "monthly", "publication_lag_days": 7.0,
     "revisions": "rarely; a restatement is a dated event", "licence": "free, public",
     "history_from": "2001-01", "pit_feasible": True,
     "assets": ("USDINR", "XAUUSD", "UST10Y"), "mechanism_families": ("programme_clock",),
     "how_to_fetch": "the external-sector statistical tables; keep the headline and the usable "
                     "figure as TWO series -- conflating them is what made 2022 look survivable"},
    {"name": "CBSL monthly workers' remittances by corridor", "source": "CBSL",
     "coverage": "1990 onward (corridor split from 2005)", "frequency": "monthly",
     "publication_lag_days": 25.0, "revisions": "minor, next month", "licence": "free, public",
     "history_from": "2005-01", "pit_feasible": True,
     "assets": ("XAUUSD", "USDINR"), "mechanism_families": ("seasonal_flow", "flow_diversion"),
     "how_to_fetch": "the external sector performance release; the 2021-22 collapse is a CHANNEL "
                     "shift to undiyal under the surrender rule, not a fall in earnings, and the "
                     "two are separable only with the SLBFE departure series beside it"},
    {"name": "DCS Colombo Consumer Price Index (CCPI) and National CPI (NCPI)",
     "source": "Department of Census and Statistics",
     "coverage": "CCPI 2013 base; NCPI 2021 base", "frequency": "monthly",
     "publication_lag_days": 0.0, "revisions": "rebasing only", "licence": "free, public",
     "history_from": "2013-01", "pit_feasible": True,
     "assets": ("XBRUSD", "WHEAT", "SUGAR"), "mechanism_families": ("release_surprise",),
     "how_to_fetch": "statistics.gov.lk; the CCPI is out on the LAST WORKING DAY of the "
                     "reference month, so it is one of the few CPIs with a zero publication lag"},
    {"name": "CBSL external sector performance: trade, tourism earnings, remittances",
     "source": "CBSL", "coverage": "2005 onward", "frequency": "monthly",
     "publication_lag_days": 25.0, "revisions": "minor", "licence": "free, public",
     "history_from": "2005-01", "pit_feasible": True,
     "assets": ("COTTON", "USDINR", "XBRUSD"), "mechanism_families": ("trade_cycle",),
     "how_to_fetch": "the monthly external sector performance PDF; the tea, apparel and fuel "
                     "import lines are the three this pack reads"},
    {"name": "Colombo Tea Auction weekly sale averages, quantities and elevation splits",
     "source": "Forbes & Walker / Asia Siyaka / John Keells market reports",
     "coverage": "1995 onward in the brokers' archives", "frequency": "weekly",
     "publication_lag_days": 0.0, "revisions": "never", "licence": "free, public",
     "history_from": "2000-01", "pit_feasible": True, "assets": ("COFARA", "COFROB", "USDINR"),
     "mechanism_families": ("auction_clearing", "supply_count"),
     "how_to_fetch": "the brokers' weekly market reports, posted the evening of the sale; the "
                     "CATALOGUED QUANTITY is published days ahead and is the only PIT-safe half"},
    {"name": "Sri Lanka Tea Board monthly production and export statistics",
     "source": "Sri Lanka Tea Board", "coverage": "1990 onward", "frequency": "monthly",
     "publication_lag_days": 20.0, "revisions": "cumulative; rarely restated",
     "licence": "free, public", "history_from": "2000-01", "pit_feasible": True,
     "assets": ("COFARA", "COFROB"), "mechanism_families": ("supply_count", "policy_shock"),
     "how_to_fetch": "srilankatea.lk statistics; the 2021-22 rows are the fertiliser ban's "
                     "yield collapse and are the cleanest policy-induced supply shock the desk "
                     "has a monthly series for"},
    {"name": "CPC retail fuel price revisions under the cost-reflective formula",
     "source": "Ceylon Petroleum Corporation / Ministry of Energy",
     "coverage": "2018 onward, monthly and formula-based from 2022", "frequency": "monthly",
     "publication_lag_days": 0.0, "revisions": "never", "licence": "free, public",
     "history_from": "2018-05", "pit_feasible": True, "assets": ("XBRUSD", "XTIUSD"),
     "mechanism_families": ("administered_price", "pass_through"),
     "how_to_fetch": "ceypetco.gov.lk marketing-sales, which is OVERWRITTEN on every revision -- "
                     "the vintage must come from the Wayback snapshots or the press reports, and "
                     "a cell compiled on the live page is NOT point-in-time"},
    {"name": "SLTDA monthly tourist arrivals by source market",
     "source": "Sri Lanka Tourism Development Authority", "coverage": "1970 onward",
     "frequency": "monthly", "publication_lag_days": 5.0, "revisions": "minor",
     "licence": "free, public", "history_from": "2000-01", "pit_feasible": True,
     "assets": ("USDINR", "US500"), "mechanism_families": ("seasonal_flow", "shock_recovery"),
     "how_to_fetch": "sltda.gov.lk statistics; the 2019 Easter attacks and the 2022 collapse are "
                     "two dated natural experiments in one series"},
    {"name": "SLBFE monthly departures for foreign employment by destination and skill",
     "source": "Sri Lanka Bureau of Foreign Employment", "coverage": "1995 onward",
     "frequency": "monthly", "publication_lag_days": 30.0, "revisions": "minor",
     "licence": "free, public", "history_from": "2000-01", "pit_feasible": True,
     "assets": ("XAUUSD", "USDINR"), "mechanism_families": ("labour_flow", "seasonal_flow"),
     "how_to_fetch": "slbfe.lk statistics; departures LEAD the remittance print by six to twelve "
                     "months and the Gulf share is the oil-cycle beta of LK-H"},
    {"name": "SLPA Colombo and Hambantota throughput and transhipment TEU",
     "source": "Sri Lanka Ports Authority", "coverage": "2005 onward", "frequency": "monthly",
     "publication_lag_days": 30.0, "revisions": "rarely", "licence": "free, public",
     "history_from": "2005-01", "pit_feasible": True, "assets": ("USDSGD", "USDINR", "CHINAH"),
     "mechanism_families": ("trade_cycle", "physical_flow"),
     "how_to_fetch": "slpa.lk statistics; the transhipment share is the part that responds to "
                     "the Indian feeder trade rather than to domestic demand"},
    {"name": "IMF EFF programme documents: staff reports, reviews, benchmarks, disbursements",
     "source": "IMF", "coverage": "2009 onward (SBA 2009, EFF 2016, EFF 2023)",
     "frequency": "per review", "publication_lag_days": 7.0, "revisions": "never",
     "licence": "free, public", "history_from": "2009-07", "pit_feasible": True,
     "assets": ("UST10Y", "USDINR", "US500"), "mechanism_families": ("programme_clock",),
     "how_to_fetch": "imf.org/en/Countries/LKA; the press release dates the Board decision and "
                     "the disbursement, and the staff report's tables date every benchmark"},
    {"name": "The 2024 ISB exchange terms: macro-linked bond thresholds and the GDP trigger",
     "source": "the exchange offer memorandum and the IMF DSA",
     "coverage": "2024-12 onward", "frequency": "per test date", "publication_lag_days": 0.0,
     "revisions": "never", "licence": "free, public (the offer memorandum is published)",
     "history_from": "2024-12", "pit_feasible": True, "assets": ("UST10Y", "US500"),
     "mechanism_families": ("forced_flow_calendar", "state_contingent_claim"),
     "how_to_fetch": "the December 2024 exchange documents and the DSA's nominal-USD-GDP path; "
                     "the step-ups are read against the DCS national accounts release, which "
                     "turns a statistics print into a coupon event and is LK-C's whole point"},
    {"name": "CSE daily market summary: ASPI, S&P SL20, turnover and net foreign flow",
     "source": "Colombo Stock Exchange", "coverage": "1998 onward", "frequency": "daily",
     "publication_lag_days": 0.0, "revisions": "never", "licence": "free, public",
     "history_from": "2005-01", "pit_feasible": True, "assets": ("US500", "USDINR"),
     "mechanism_families": ("positioning", "foreign_flow"),
     "how_to_fetch": "cse.lk trade summary, posted after the close; the halt days and the April "
                     "2022 suspension must be carried as CLOSED rather than as zero-return days"},
)

# --------------------------------------------------------------------------- actors
ACTORS: tuple[dict[str, Any], ...] = (
    {"name": "Central Bank of Sri Lanka Monetary Policy Board",
     "holds": "the Overnight Policy Rate, the standing facilities around it, the open market "
              "operations, and about USD 5-6bn of gross official reserves of which the PBOC swap "
              "is a conditional slice",
     "forced_to": ("decide at eight scheduled reviews a year on a pre-announced calendar and "
                   "publish the statement at 07:30 Colombo the same morning",
                   "publish the external sector performance and the reserves monthly",
                   "meet the EFF's net-international-reserves and primary-balance test dates at "
                   "quarter ends",
                   "stay out of the primary market for government securities under the 2023 Act"),
     "when": "07:30 Asia/Colombo (02:00 UTC) on the review day; the reserves in the first week "
             "of the following month",
     "information": ("the reserve position before the market", "the IMF mission's numbers",
                     "the banks' own FX positions through supervision",
                     "the Treasury's funding need before the auction"),
     "constraints": ("the EFF's performance criteria and structural benchmarks",
                     "a published inflation target agreed with the Ministry of Finance",
                     "the 2023 Act's prohibition on monetary financing, which removed the "
                     "instrument the bank had used through 2021-22",
                     "a banking system still carrying restructured government paper"),
     "instruments": ("USDINR", "XAUUSD", "UST10Y"),
     "counterparties": ("the primary dealers", "the IMF", "the licensed commercial banks",
                        "the Treasury"),
     "observables": ("the review statement and the press conference",
                     "the monthly reserves and the swap-usability note",
                     "the weekly T-bill cut-offs between reviews",
                     "the daily indicative exchange rate"),
     "impact": "a decision moves AWPLR and the bill curve immediately; the rupee is managed, so "
               "the executable effect runs through the frontier-stress legs -- the regional "
               "cross, gold and the ten-year rate -- and never through LKR itself",
     "persistence": "the level effect lasts to the next review; the 2022 emergency +700bp and "
                    "the 2023-24 easing to single digits are one era each",
     "falsifier": "the same window on the eight nearest non-review weekdays; an effect that "
                  "survives there is a weekday effect wearing the central bank's hat, and a "
                  "review-day move on USDINR matching an RBI decision day is South Asia, not "
                  "Sri Lanka",
     "notes": "the 2022-04-08 emergency meeting is its own class and is never pooled"},
    {"name": "The Ministry of Finance and the Treasury as the programme's counterparty",
     "holds": "the budget, the tax file, the Special Commodity Levy gazettes and the External "
              "Resources Department's creditor relationships",
     "forced_to": ("legislate the EFF's revenue benchmarks (VAT, the removal of exemptions)",
                   "publish the fiscal management report and the budget on a statutory calendar",
                   "gazette the commodity levies that price sugar, wheat flour and milk powder",
                   "reach the primary-balance target the quarterly review tests"),
     "when": "the budget in the last quarter for the year that follows; levy gazettes at any "
             "time and usually the evening before they bite",
     "information": ("the revenue run-rate weeks before it is published",
                     "the creditor negotiations", "the import-licence pipeline"),
     "constraints": ("the EFF's quantitative performance criteria",
                     "a revenue-to-GDP ratio that was among the lowest in the world in 2021",
                     "the political cost of every cost-reflective price"),
     "instruments": ("SUGAR", "WHEAT", "UST10Y"),
     "counterparties": ("the IMF", "the Official Creditor Committee", "the bondholders",
                        "the importers who hold the licences"),
     "observables": ("the budget speech", "the levy gazettes", "the fiscal management report",
                     "the monthly revenue tables"),
     "impact": "a levy change is an immediate step in a food import's landed cost and in the "
               "CCPI basket; the 2020 sugar-levy cut is the reference episode and it moved a "
               "measurable share of a year's sugar imports",
     "persistence": "a levy lasts until the next gazette, which can be weeks",
     "falsifier": "levy gazette windows on SUGAR and WHEAT show no abnormal move against the "
                  "matched weekday control -- the expected result for a country this small, and "
                  "the pack records the absence rather than hiding it",
     "notes": "Sri Lanka's food-import basket is small in world terms; this actor's edge is on "
              "the domestic price and the CPI, and the outward leg is honestly weak"},
    {"name": "The IMF mission and Executive Board (Sri Lanka EFF)",
     "holds": "the undisbursed tranches of the 2023 EFF and the review calendar",
     "forced_to": ("complete QUARTERLY reviews against dated performance criteria",
                   "publish the staff report with its structural benchmarks and the DSA",
                   "disburse only on Board approval, which the next reserves print then shows",
                   "publish the nominal-USD-GDP path the macro-linked bonds are written against"),
     "when": "staff-level agreement, Board approval and disbursement are three dated events "
             "weeks apart; the Board meets on a published calendar",
     "information": ("the fiscal and reserve data ahead of the market",
                     "the creditor financing assurances"),
     "constraints": ("the programme's own conditionality",
                     "the requirement that the Official Creditor Committee and the bondholders "
                     "deliver comparable treatment before a review closes"),
     "instruments": ("UST10Y", "USDINR", "US500"),
     "counterparties": ("the Treasury", "the CBSL", "India, Japan and China as the bilateral "
                        "creditors", "the bondholder committee"),
     "observables": ("the press release", "the staff report's tables", "the reserves step",
                     "the DSA's GDP path"),
     "impact": "the sovereign's stress premium steps at each review; the 2023 approval and the "
               "2024 exchange are the two largest repricings in the restructured curve",
     "persistence": "one review cycle; the effect is a step, not a drift",
     "falsifier": "the same windows around IMF Board dates for OTHER programme countries show "
                  "the same move on UST10Y and the regional cross, in which case it is a dollar "
                  "or global-risk event and not a Sri Lanka programme event",
     "notes": "the DSA's GDP path is the only reason a multilateral document is a coupon input"},
    {"name": "The external bondholders and the macro-linked bonds",
     "holds": "the restructured international sovereign bonds issued in the December 2024 "
              "exchange, including the macro-linked instruments and the governance-linked bond",
     "forced_to": ("accept coupons and principal that STEP UP OR DOWN against Sri Lanka's own "
                   "published nominal-USD-GDP path at defined test dates",
                   "price the governance-linked bond off published governance milestones",
                   "mark to a curve that reprices on every EFF review"),
     "when": "the GDP test dates defined in the exchange documents and every quarterly review",
     "information": ("the same public data as everyone; the committee's own soundings during "
                     "the negotiation, which ended with the exchange"),
     "constraints": ("comparability of treatment with the Official Creditor Committee",
                     "the DSA's debt-service envelope",
                     "their own mandates, which forced some holders out at default"),
     "instruments": ("UST10Y", "US500"),
     "counterparties": ("the Treasury", "the Official Creditor Committee", "the IMF"),
     "observables": ("the DCS nominal-GDP release", "the IMF DSA path",
                     "the indicative bond prices the terminals carry", "the review press release"),
     "impact": "a GDP print that crosses a threshold changes the sovereign's contracted debt "
               "service; the executable reach is the frontier-stress rate and global risk, and "
               "the pack does not pretend an absent bond is an instrument",
     "persistence": "each test date is a discrete step; the structure runs for the life of the "
                    "bonds",
     "falsifier": "GDP-release windows show no abnormal move on UST10Y or US500 beyond the "
                  "matched control, which is the expected result for an issuer this small and "
                  "is recorded as a null rather than dropped",
     "notes": "the first state-contingent sovereign instrument in the desk's book; the mechanism "
              "is real even where the executable leg is weak"},
    {"name": "The Official Creditor Committee (India, Japan, the Paris Club) and China EXIM/CDB",
     "holds": "the bilateral claims restructured alongside the bonds; India's credit lines of "
              "2022 and Japan's long-standing JICA project loans",
     "forced_to": ("agree a treatment the IMF can call comparable before a review closes",
                   "publish the memorandum of understanding once signed",
                   "roll or reprofile at the agreed dates"),
     "when": "the OCC's meetings and the signature dates; the quarterly review windows",
     "information": ("the negotiation itself", "their own strategic priorities in the Indian "
                     "Ocean, which are not an economic variable but drive the timing"),
     "constraints": ("China's own preference for maturity extension over haircut, which is why "
                     "its treatment was agreed separately",
                     "India's credit-line exposure from the 2022 rescue",
                     "the Paris Club's comparability rules"),
     "instruments": ("USDCNH", "USDINR", "USDJPY"),
     "counterparties": ("the Treasury", "the IMF", "the bondholders"),
     "observables": ("the OCC statements", "the signature announcements",
                     "the external debt tables in the CBSL Annual Report"),
     "impact": "negligible for the creditor currencies themselves; the edge is recorded as "
               "HYPOTHESIS and weak, and the honest expectation is a null",
     "persistence": "one agreement",
     "falsifier": "no measurable move on USDCNH, USDINR or USDJPY around Sri Lanka OCC dates -- "
                  "the expected result, which the pack records rather than hides",
     "notes": "carried for completeness of the creditor map, not for its executable strength"},
    {"name": "Ceylon Petroleum Corporation and the Public Utilities Commission as price setters",
     "holds": "the refinery at Sapugaskanda, the import tenders for crude and refined product, "
              "and the notification power over the pump price; the PUCSL holds the tariff",
     "forced_to": ("apply the cost-reflective formula at month end",
                   "tender for cargoes in dollars the reserves must release",
                   "publish the determination papers when the electricity tariff changes",
                   "meet the EFF's benchmark that energy prices be cost-reflective"),
     "when": "the last day of the month, effective from midnight Colombo (about 15:00 UTC)",
     "information": ("the tender prices and the freight before the market",
                     "the rupee's monthly average", "the CEB's hydro position"),
     "constraints": ("the formula's own lag structure",
                     "the political cost of a rise, which suspended the formula more than once",
                     "the dollar position the CBSL must release for the cargo"),
     "instruments": ("XBRUSD", "XTIUSD"),
     "counterparties": ("Lanka IOC, the private competitor whose prices track the same formula",
                        "the CEB, whose fuel-oil burn the hydro season sets",
                        "the cargo sellers and the trading houses"),
     "observables": ("the revision notice and its effective date",
                     "the PUCSL determination", "the queue reports in the Sinhala press"),
     "impact": "sets the transport and utilities components of the CCPI; a large rise is followed "
               "by a protest cycle and by the review statement's administered-prices paragraph",
     "persistence": "one month by construction; a suspended formula is a regime break",
     "falsifier": "the revision-eve window on XBRUSD shows no abnormal move against the matched "
                  "weekday control. Sri Lanka is a price-taker in crude and this actor's effect "
                  "is on the domestic price, so an outward edge that survives the control is the "
                  "finding and an absent one is the expected result",
     "notes": "an INPUT-direction mechanism; LK-E measures it honestly and the mid-month placebo "
              "is built into the miner"},
    {"name": "The Colombo Tea Auction brokers and the Sri Lanka Tea Board",
     "holds": "the catalogue: essentially all Ceylon tea passes through this weekly sale, and "
              "the four large broking houses write the market reports the trade prices off",
     "forced_to": ("catalogue lots days before the sale and publish the offered quantity",
                   "hold the sale on Tuesday and Wednesday and move it when a Poya intervenes",
                   "publish the elevation averages the same evening",
                   "clear the crop: the leaf cannot be warehoused indefinitely"),
     "when": "Tuesday and Wednesday, 09:00-17:00 Colombo (03:30-11:30 UTC); the market report "
             "that evening",
     "information": ("the catalogued quantity before the market sees the price",
                     "the buyers' standing orders from the Middle East, Russia, Turkey and Iraq",
                     "the estate-level crop condition weeks before the Tea Board's monthly print"),
     "constraints": ("the crop, which the 2021 fertiliser ban cut hard and which the monsoon "
                     "sets in normal years",
                     "the buyer countries' own currencies and sanctions exposure",
                     "the auction's physical, no-forward structure: there is nothing to hedge in"),
     "instruments": ("COFARA", "COFROB", "USDINR"),
     "counterparties": ("the Middle Eastern and CIS buying houses", "the plantation companies "
                        "and smallholders", "the exporters and blenders"),
     "observables": ("the catalogued quantity", "the weekly elevation averages",
                     "the Tea Board's monthly production series", "the green-leaf price"),
     "impact": "tea is the second-largest goods export and the auction sets its price weekly; "
               "the executable reach on this desk is the beverage complex and the export-earnings "
               "run-rate that feeds the frontier-stress legs, and that is declared weak",
     "persistence": "one crop season; the 2021-22 ban is one era and the recovery another",
     "falsifier": "the auction-day window on COFARA and COFROB matches the same weekdays in "
                  "non-auction weeks and the Mombasa sale days, in which case the mechanism is "
                  "the beverage complex's own calendar and not Colombo",
     "notes": "no tea contract exists on this broker; the auction is an INPUT observable and "
              "every reading built on it says so"},
    {"name": "JAAF apparel exporters as yarn and fabric importers under GSP+",
     "holds": "about 45% of goods exports and roughly 300,000 direct jobs; the order books of "
              "the European and American brands",
     "forced_to": ("import essentially all yarn, fabric and trim, because the island grows no "
                   "cotton of consequence",
                   "meet the EU's GSP+ human-rights and labour conventions or lose the tariff "
                   "preference, which is reviewed on a published cycle",
                   "repatriate proceeds under the surrender rule"),
     "when": "orders placed one to two quarters ahead; the GSP+ review on the Commission's cycle",
     "information": ("their own order books from the EU and US brands before any statistic",
                     "the freight and fabric quotes"),
     "constraints": ("GSP+ status, which is conditional and has been publicly questioned",
                     "power and fuel costs after the cost-reflective reform",
                     "competition from Bangladesh and Vietnam at the same brands"),
     "instruments": ("COTTON", "EURUSD"),
     "counterparties": ("the EU and US brands", "the Indian, Chinese and Pakistani yarn mills",
                        "the banks issuing the LCs"),
     "observables": ("the CBSL monthly apparel export line", "JAAF's own targets",
                     "the EU GSP+ monitoring reports", "the fabric import line"),
     "impact": "Sri Lanka's fibre draw is small against world cotton, so this is a weak outward "
               "edge by construction; the GSP+ decision is a dated binary event and is the part "
               "worth measuring",
     "persistence": "one GSP+ cycle; one order season",
     "falsifier": "apparel export prints and GSP+ decision windows carry no information for "
                  "COTTON or EURUSD beyond what Bangladesh's RMG print already carries",
     "notes": "the two-lane order: the apparel groups are ACTORS and no share CFD enters an "
              "instrument tuple here"},
    {"name": "Sri Lankan migrant workers and the Bureau of Foreign Employment (SLBFE)",
     "holds": "the largest net foreign inflow the country has: worker remittances, and the "
              "departure pipeline that generates them",
     "forced_to": ("register departures with the SLBFE, which counts them monthly",
                   "choose the banking channel or undiyal on the spread between the official "
                   "rate and the street rate -- the 2021-22 surrender rule pushed them to the "
                   "second and the remittance print halved while earnings did not",
                   "send ahead of the New Year, Ramadan and the school term"),
     "when": "the monthly print about 25 days after the month; the New Year and Eid peaks",
     "information": ("the street rate from family before any published series",
                     "the Gulf labour market they work in"),
     "constraints": ("Gulf labour demand and the Korean and Israeli quota schemes",
                     "the surrender rule and the banks' posted rates",
                     "the cost and risk of the informal channel"),
     "instruments": ("XAUUSD", "USDINR"),
     "counterparties": ("the banks and the money transfer operators", "the undiyal networks",
                        "the jewellers and the pawn-broking banks the cash reaches"),
     "observables": ("the monthly remittance print", "SLBFE departures by destination",
                     "the gap between the indicative rate and the reported street rate",
                     "the pawning advance book in the banks' quarterlies"),
     "impact": "the New Year month runs well above trend and part of it reaches the jewellery "
               "and pawning market, which is where the executable gold leg is",
     "persistence": "seasonal every year, plus the 2021-22 channel-shift break",
     "falsifier": "the New Year and Eid month excess disappears once the official-street spread "
                  "and the departure pipeline are controlled, or the Colombo gold premium shows "
                  "no rise into the New Year against the matched non-festival months",
     "notes": "departures LEAD remittances by six to twelve months; the two series must be read "
              "together or a channel shift reads as an earnings collapse"},
    {"name": "The Sri Lanka Tourism Development Authority and the tourism trade",
     "holds": "the arrivals count and the earnings estimate; the hotel and guide capacity",
     "forced_to": ("publish arrivals by source market in the first days of the month",
                   "price in dollars against Thailand, Vietnam and the Maldives",
                   "absorb a shock without any instrument to hedge it"),
     "when": "the monthly release; the December-March high season and the May-September "
             "south-west monsoon trough",
     "information": ("the forward booking curve the hotels see",
                     "the airline seat capacity announced a season ahead"),
     "constraints": ("air capacity into Colombo", "the visa regime, which has changed twice",
                     "security and travel advisories"),
     "instruments": ("USDINR", "US500"),
     "counterparties": ("the airlines", "the Indian, Russian and British source markets",
                        "the competing destinations"),
     "observables": ("the monthly arrivals by source", "the earnings estimate",
                     "the travel advisories", "the seat capacity announcements"),
     "impact": "tourism is the second-largest gross inflow; the 2019 Easter attacks and the 2022 "
               "collapse are two dated shocks with a clean before and after, which is why this "
               "actor is worth carrying even though its executable leg is indirect",
     "persistence": "a shock takes eighteen months to trace out; the seasonality is annual",
     "falsifier": "arrivals surprises carry no information for the regional cross or global risk "
                  "beyond what the source markets' own equity and currency moves already carry",
     "notes": "two natural experiments in one monthly series; the pack uses them as era markers"},
    {"name": "The Sri Lanka Ports Authority and the Colombo terminal operators",
     "holds": "Colombo, the transhipment hub of South Asia, and Hambantota on a 99-year lease to "
              "China Merchants Port signed in 2017; the CWIT terminal opened with Indian and "
              "Japanese capital",
     "forced_to": ("publish monthly throughput and the transhipment split",
                   "serve the Indian feeder trade, which is the majority of the boxes",
                   "compete with Singapore, Klang and the new Indian transhipment capacity"),
     "when": "monthly, about thirty days after the month",
     "information": ("the berth schedule and the feeder bookings before the count is published"),
     "constraints": ("berth and crane capacity", "the Indian ports' own expansion",
                     "the fuel and power cost of the terminal"),
     "instruments": ("USDSGD", "USDINR", "CHINAH"),
     "counterparties": ("the Indian feeder operators", "Maersk, MSC and the alliances",
                        "China Merchants Port at Hambantota", "Adani and the CWIT partners"),
     "observables": ("the monthly TEU and the transhipment share",
                     "the bunkering volume", "the new-terminal commissioning dates"),
     "impact": "an Asian trade-cycle observable with a monthly count and no contract; its "
               "executable reach is the Singapore cross and the China complex, and the edge is "
               "recorded as weak",
     "persistence": "the trade cycle; the Hambantota lease is a structural era marker",
     "falsifier": "Colombo transhipment surprises carry no information for USDSGD or CHINAH "
                  "beyond what Singapore's own container throughput already carries",
     "notes": "the Hambantota lease is the single most-written-about fact about this economy and "
              "is carried here as a counted physical flow rather than as geopolitics"},
    {"name": "The Colombo Stock Exchange, the SEC and the local unit trusts",
     "holds": "the ASPI and the S&P SL20, the daily foreign and local flow, and the halt button",
     "forced_to": ("publish the daily trade summary with foreign purchases and sales",
                   "halt on the market-wide circuit breaker and on the per-security price band",
                   "close on every statutory public holiday, which includes every Poya day"),
     "when": "09:30-14:30 Colombo (04:00-09:00 UTC); the summary after the close",
     "information": ("the order book and the broker-level flow the regulator sees"),
     "constraints": ("a shallow free float and a retail-dominated turnover",
                     "the price band and the circuit breaker",
                     "the foreign exit of 2020-22 that left the register largely domestic"),
     "instruments": ("US500", "USDINR"),
     "counterparties": ("the foreign funds on one side of the net-foreign line",
                        "the local unit trusts and retail on the other",
                        "the EPF, the largest single domestic holder"),
     "observables": ("net foreign purchases by day", "turnover", "the halt log",
                     "the April 2022 five-session suspension"),
     "impact": "small in dollars; the SIGN of the foreign line is a clean read of frontier risk "
               "appetite for Sri Lanka and co-moves with the frontier complex",
     "persistence": "episodic; the 2022 halts are one era",
     "falsifier": "the net-foreign line carries no lead on the regional cross or on frontier "
                  "risk beyond what US500 already carries",
     "notes": "the index itself has no CFD; the flow is the object and the halts are closures"},
    {"name": "The licensed commercial banks and the surrender requirement",
     "holds": "the interbank dollar book, the exporters' proceeds under the surrender rule, and "
              "the pawning advance book that turns gold into credit",
     "forced_to": ("convert a mandated share of export and remittance proceeds at the posted "
                   "rate when the surrender rule is in force",
                   "post a daily rate the CBSL's indicative rate is built from",
                   "mark restructured government securities after the domestic debt operation",
                   "lend against gold at the pawning rate and re-auction on default"),
     "when": "the posted rates each morning; the indicative rate about 09:00 Colombo",
     "information": ("the importers' unfilled dollar demand before any published series",
                     "the pawning book's rollover rate, which rises with household stress"),
     "constraints": ("the surrender rule and the open-account import rules",
                     "capital ratios after the domestic debt optimisation",
                     "the CBSL's spot window and its moral suasion"),
     "instruments": ("XAUUSD", "USDINR"),
     "counterparties": ("exporters and remitters on one side, importers on the other",
                        "the CBSL's spot window", "the pawning customers"),
     "observables": ("the posted and indicative rates and the spread between them",
                     "the pawning advance line in the quarterlies",
                     "the import-LC refusals reported in the press"),
     "impact": "the surrender rule is the mechanism that turned a remittance flow into an "
               "informal one in 2021-22; the pawning book is the cleanest domestic transmission "
               "from the gold price into household credit the desk has anywhere",
     "persistence": "the surrender rule is a regime that has been imposed and lifted; the "
                    "pawning channel is permanent",
     "falsifier": "a widening official-street spread that is NOT followed by a lower "
                  "banking-channel remittance print within two months, and a lifted surrender "
                  "rule not followed by a higher one, refutes the diversion mechanism LK-D and "
                  "LK-H are built on",
     "notes": "the spread is a lead indicator, never a tradeable; the tests are on what follows"},
)

# --------------------------------------------------------------------------- domains
DOMAINS: tuple[dict[str, Any], ...] = (
    {"id": "LK-A", "title": "The OPR and the eight scheduled Monetary Policy Reviews",
     "objects": ("the scheduled review decisions and the 2022 emergency meeting",
                 "the statement's administered-prices and external-sector paragraphs",
                 "the weekly T-bill cut-off drift between reviews",
                 "the OPR transition, which breaks the rate series in two"),
     "conditions": ("the era: hiking (2021-22), the emergency plateau, the 2023-25 easing",
                    "whether the review fell inside an EFF review window",
                    "verified vs reported review date"),
     "instruments": ("USDINR", "XAUUSD", "UST10Y"),
     "controls": ("the same 02:00 UTC window on the eight nearest non-review weekdays",
                  "the same window on RBI decision days, separating 'a South Asian bank decided' "
                  "from 'the CBSL decided'",
                  "a randomised-date null drawn from the same hours of the same months"),
     "notes": "the rupee is absent, so the executable effect is a frontier-stress effect; the "
              "07:30 Colombo release sits in the European pre-open, which is the tradeable hour"},
    {"id": "LK-B", "title": "The IMF EFF clock: quarterly reviews, benchmarks, tranches",
     "objects": ("staff-level agreement dates", "Board approval dates",
                 "the reserves step that follows a disbursement",
                 "the structural benchmarks with dated deadlines"),
     "conditions": ("whether the review was on time or delayed",
                    "whether the creditor assurances were in place before the Board",
                    "the era"),
     "instruments": ("UST10Y", "USDINR", "US500"),
     "controls": ("IMF Board dates for other programme countries on the same instruments",
                  "the same window on non-Board weekdays",
                  "the monthly reserves print in months with no tranche"),
     "notes": "three dated events per review; pooling them blends three different reactions"},
    {"id": "LK-C", "title": "The default, the restructuring and the GDP trigger",
     "objects": ("the 2022-04-12 standstill announcement",
                 "the 2023 domestic debt optimisation",
                 "the December 2024 ISB exchange and the macro-linked bond thresholds",
                 "the DCS nominal-USD-GDP release at each test date"),
     "conditions": ("pre-default, standstill, post-exchange",
                    "whether the GDP print crossed a defined threshold",
                    "whether an EFF review was pending"),
     "instruments": ("UST10Y", "US500"),
     "controls": ("the same GDP-release windows for other restructured frontier sovereigns",
                  "non-test-date GDP releases in the same series",
                  "a randomised-date null on the release days"),
     "notes": "the only state-contingent sovereign instrument in the desk's book; a statistics "
              "release is a coupon event and that is the whole claim"},
    {"id": "LK-D", "title": "The managed rupee: the float, the surrender rule and the spot window",
     "objects": ("the CBSL daily indicative rate", "the surrender requirement's imposition and "
                 "removal", "the reported street rate and its spread to the official rate",
                 "the March 2022 float"),
     "conditions": ("surrender rule in force or not",
                    "the spread bucket between the official and reported street rate",
                    "the import-restriction regime"),
     "instruments": ("USDINR", "XAUUSD"),
     "controls": ("the same spread series lagged one month against the remittance print, "
                  "against a shuffled-lag null",
                  "Pakistan's kerb premium in the same months -- a sibling economy with the same "
                  "channel -- to separate 'South Asia' from 'Sri Lanka'",
                  "the Colombo gold premium as an alternative stress measure"),
     "notes": "the spread is a lead indicator, not a tradeable; the tests are on what follows it"},
    {"id": "LK-E", "title": "The CPC month-end fuel formula as an administered pass-through",
     "objects": ("the month-end revision and its effective midnight",
                 "the PUCSL electricity determinations",
                 "the periods when the formula was suspended",
                 "the two-week Brent and rupee averages the formula reads"),
     "conditions": ("the sign and size of the change",
                    "whether the formula was applied or suspended",
                    "the hydro season, which sets how much fuel oil the CEB burns"),
     "instruments": ("XBRUSD", "XTIUSD"),
     "controls": ("the same UTC window on the 15th of each month (no revision)",
                  "the matched weekday-and-hour control on XBRUSD",
                  "the PUCSL determination date as an alternative event, to see which of the two "
                  "carries any move"),
     "notes": "an INPUT-direction mechanism; the honest expectation is no outward effect and the "
              "mid-month placebo is built into the miner"},
    {"id": "LK-F", "title": "The weekly Colombo Tea Auction and the fertiliser-ban supply shock",
     "objects": ("the Tuesday/Wednesday sale and its elevation averages",
                 "the catalogued quantity published ahead of the sale",
                 "the Tea Board's monthly production series",
                 "the 2021-04 chemical-fertiliser import ban and its reversal"),
     "conditions": ("in the ban era or out of it",
                    "the monsoon state over the prior quarter",
                    "the buyer-country stress (Russia, Turkey, Iran sanctions and currencies)"),
     "instruments": ("COFARA", "COFROB", "USDINR"),
     "controls": ("the Mombasa auction days on the same instruments, separating 'an auctioned "
                  "beverage crop' from 'Colombo'",
                  "the same weekdays in weeks with no Colombo sale",
                  "the catalogued quantity as a pre-announced instrument for the price"),
     "notes": "NO TEA CONTRACT EXISTS HERE. This is an INPUT-side mechanism and every reading "
              "built on it is declared weak; the fertiliser ban is the cleanest policy-induced "
              "agricultural supply shock in the desk's book and is worth the honest null"},
    {"id": "LK-G", "title": "Apparel, GSP+ conditionality and the imported-fibre chain",
     "objects": ("the monthly apparel export line", "the EU GSP+ monitoring cycle and its "
                 "decisions", "the yarn and fabric import line", "JAAF's stated targets"),
     "conditions": ("GSP+ secure, under review, or questioned",
                    "the EU retail cycle", "the competing-supplier cost gap"),
     "instruments": ("COTTON", "EURUSD"),
     "controls": ("Bangladesh's RMG export print on the same dates",
                  "the same windows in years with no GSP+ decision pending",
                  "the matched weekday control"),
     "notes": "a small fibre draw and therefore a weak outward edge; the GSP+ decision is the "
              "dated binary event and is the part worth measuring"},
    {"id": "LK-H", "title": "Remittances, departures and the gold pawning channel",
     "objects": ("the monthly remittance print", "SLBFE departures by destination and skill",
                 "the pawning advance book", "the New Year and Eid seasonal peaks"),
     "conditions": ("the official-street spread bucket",
                    "the surrender rule's state",
                    "the Gulf oil price over the prior quarter"),
     "instruments": ("XAUUSD", "USDINR"),
     "controls": ("the same lunar and solar festival windows on gold in years with a narrow "
                  "spread",
                  "India's remittance seasonality on the same dates, separating 'South Asian "
                  "festival' from 'Sri Lankan New Year'",
                  "the matched non-festival months"),
     "notes": "the executable leg is gold through the pawning and jewellery channel; small but "
              "clean, and departures lead the print by six to twelve months"},
    {"id": "LK-I", "title": "Tourism arrivals and two dated collapses",
     "objects": ("the SLTDA monthly arrivals by source market",
                 "the 2019 Easter Sunday attacks", "the 2022 collapse and the recovery",
                 "the air-capacity and visa-regime changes"),
     "conditions": ("season (December-March high, May-September monsoon trough)",
                    "pre- or post-shock", "the source-market mix"),
     "instruments": ("USDINR", "US500"),
     "controls": ("the Maldives' and Thailand's arrivals on the same months",
                  "the same months in unshocked years",
                  "a randomised-date null on the release days"),
     "notes": "two natural experiments in one monthly series; the indirect executable reach is "
              "stated rather than hidden"},
    {"id": "LK-J", "title": "Colombo transhipment, Hambantota and the Chinese creditor channel",
     "objects": ("SLPA monthly throughput and the transhipment share",
                 "the 2017 Hambantota 99-year lease and the Port City build",
                 "the CWIT terminal's commissioning",
                 "the Chinese bilateral claims restructured alongside the bonds"),
     "conditions": ("the Asian trade cycle", "Indian transhipment capacity added or not",
                    "whether a Chinese creditor milestone was pending"),
     "instruments": ("USDSGD", "USDINR", "CHINAH"),
     "controls": ("Singapore's own container throughput on the same months",
                  "other Belt-and-Road milestone dates on CHINAH",
                  "the matched weekday control"),
     "notes": "recorded as weak; the pack expects and reports an absent executable effect on the "
              "China legs and keeps the counted physical flow because it is real"},
    {"id": "LK-K", "title": "The CSE: the foreign flow, the price band and the 2022 halts",
     "objects": ("daily net foreign purchases and sales", "turnover and the ASPI",
                 "the circuit-breaker halt log",
                 "the five-session suspension from 2022-04-18"),
     "conditions": ("the sign of the five-day net-foreign sum",
                    "halt day or normal day", "the rupee stress state"),
     "instruments": ("US500", "USDINR"),
     "controls": ("Vietnam's and Bangladesh's frontier flows on the same dates",
                  "the same windows with the foreign line shuffled in time (block permutation)",
                  "the local unit-trust line as the domestic counterpart"),
     "notes": "the index is a target, not an instrument; the halts are CLOSED days and must "
              "never be carried as zero-return days"},
    {"id": "LK-L", "title": "The Poya calendar: a lunar monthly closure and the bank/market split",
     "objects": ("every full-moon Poya closure and the day after Vesak",
                 "the two Sinhala and Tamil New Year days",
                 "the 30 June and 31 December bank holidays",
                 "the months where a Poya falls on another holiday"),
     "conditions": ("announced vs projected Poya date",
                    "whether the Poya fell on a weekday",
                    "whether it collided with another holiday, making one closed day and not two"),
     "instruments": ("XAUUSD", "USDINR"),
     "controls": ("the NON-Poya full-moon-adjacent weekdays as the placebo, which separates 'the "
                  "market was shut' from 'it was near a full moon'",
                  "India's and Bangladesh's own closures on the same dates",
                  "the matched weekday control on the same instruments"),
     "notes": "the pack's own calendar and the only lunar MONTHLY closure in the desk's book; "
              "the announced rows are the sample and the projected ones never join it"},
    {"id": "LK-M", "title": "Food imports under gazette: the Special Commodity Levy basket",
     "objects": ("the sugar, wheat-flour and milk-powder levy gazettes",
                 "the 2020 sugar-levy cut and the inquiry that followed",
                 "the import-restriction gazettes of 2020-22 and their removal",
                 "the administered bread price"),
     "conditions": ("levy raised, cut, or restriction lifted",
                    "the reserve position when the decision was taken",
                    "the era"),
     "instruments": ("SUGAR", "WHEAT"),
     "controls": ("India's own sugar and wheat export-policy dates on the same instruments, the "
                  "larger neighbour whose decisions dominate the regional flow",
                  "the same windows on non-gazette days",
                  "a randomised-date null"),
     "notes": "a small importer: the honest expectation is a domestic-price effect and an absent "
              "outward one, and the pack records the null rather than dropping the domain"},
)

# --------------------------------------------------------------------------- the pack's miners
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    {"name": "lk_cbsl_policy_windows", "domain_ids": ("LK-A",), "kind": "event",
     "cadence_s": 86400.0, "steerable": False, "wired": False,
     "entry": "countries.lk.miners:cbsl_policy_windows",
     "needs": ("CENTRAL_BANK decision dates", "USDINR, XAUUSD, UST10Y H1 bars"),
     "notes": "the 02:00 UTC review window with the matched weekday control; the REPORTED "
              "dates run as a separate labelled arm and never pool with the verified sample"},
    {"name": "lk_poya_closure_eves", "domain_ids": ("LK-L", "LK-H"), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.lk.miners:poya_closure_eves",
     "needs": ("the POYA_DAYS table", "XAUUSD, USDINR H1 bars"),
     "notes": "announced Poya eves only; the non-Poya full-moon-adjacent weekdays are the "
              "placebo that separates the closure from the moon"},
    {"name": "lk_tea_auction_week", "domain_ids": ("LK-F",), "kind": "calendar",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.lk.miners:tea_auction_week",
     "needs": ("the Tuesday sale calendar", "COFARA, COFROB H1 bars",
               "CBSL:tea_export_volume"),
     "notes": "an INPUT-side mechanism with no tea contract anywhere; the series lead runs "
              "beside the event study and both are declared weak"},
    {"name": "lk_fuel_formula_month", "domain_ids": ("LK-E",), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.lk.miners:fuel_formula_month",
     "needs": ("the month-end revision calendar", "XBRUSD, XTIUSD H1 bars"),
     "notes": "the administered pass-through measured honestly; the 15th is the placebo"},
    {"name": "lk_transmission_seeds",
     "domain_ids": ("LK-B", "LK-C", "LK-D", "LK-G", "LK-I", "LK-J", "LK-K", "LK-M"),
     "kind": "transfer", "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.lk.miners:transmission_seeds",
     "needs": ("TRANSMISSION_EDGES_SEED",),
     "notes": "the pack's map as HYPOTHESIS discoveries, deduplicated by the registry"},
)
MINER_DOMAINS: dict[str, tuple[str, ...]] = {
    "central_bank_surprise": ("LK-A",), "release_surprise": ("LK-C", "LK-I"),
    "calendar_settlement": ("LK-E", "LK-F"), "holiday_liquidity": ("LK-L",),
    "positioning": ("LK-K",), "carry_funding": ("LK-D",), "corporate_flow": ("LK-G", "LK-J"),
    "institutional_flow": ("LK-B", "LK-C", "LK-K"), "equity_mechanics": ("LK-K",),
    "derivatives_expiry": ("LK-K",), "failure": ("LK-E", "LK-J", "LK-M"),
    "residual": ("LK-D", "LK-H"), "transfer": ("LK-F", "LK-G", "LK-M"),
    "scouts": ("LK-D", "LK-L"),
}

# --------------------------------------------------------------------------- transmission
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    {"id": "LK-E1", "source": "Colombo Tea Auction weekly average times the Tea Board's monthly "
                              "production (the tea export-earnings run-rate)",
     "target": "USDINR", "targets": ("USDINR", "UST10Y"), "to_country": "global", "sign": "-",
     "mechanism": "tea is the second-largest goods export of a sovereign with no reserve buffer; "
                  "a collapse in the auction's earnings run-rate widens the trade deficit, drains "
                  "reserves and widens the frontier-stress premium the regional cross and the "
                  "ten-year rate both carry",
     "horizon": "4 to 26 weeks", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "the Colombo Tea Auction brokers and the Sri Lanka Tea Board",
     "constraint": "the crop cannot be warehoused and the country cannot borrow",
     "flow": "export earnings",
     "condition": "earnings run-rate more than 15% below the prior year, and reserves below "
                  "three months of imports",
     "control": "the Mombasa and Guwahati auction averages in the same weeks; India's own tea "
                "earnings",
     "falsifier": "a tea-earnings collapse that is NOT followed by a wider deficit in the CBSL "
                  "external sector print and a firmer frontier-stress premium within a quarter",
     "evidence": "HYPOTHESIS"},
    {"id": "LK-E2", "source": "The April 2021 chemical-fertiliser import ban and the Tea Board "
                              "yield series that followed it",
     "target": "COFROB", "targets": ("COFROB", "COFARA"), "to_country": "global", "sign": "+",
     "mechanism": "a policy-induced yield collapse in the world's largest orthodox black-tea "
                  "exporter removes supply from the beverage complex; there is NO tea contract "
                  "on this broker, so the claimed reach is the auctioned-beverage substitutes, "
                  "which is a WEAK leg and is declared weak on every reading",
     "horizon": "1 to 4 quarters", "horizon_class": "multi_day", "lag_days": 60.0,
     "actor": "the government that banned the imports and the estates that lost the yield",
     "constraint": "no chemical nutrient was available at any price for two seasons",
     "flow": "supply withdrawal", "condition": "the ban era only (2021-04 to 2022-11)",
     "control": "Kenyan and Indian production in the same seasons; the coffee complex's own "
                "Brazilian supply cycle",
     "falsifier": "the ban-era quarters show no abnormal move in the beverage complex once the "
                  "Brazilian coffee cycle and freight are controlled -- the expected result, and "
                  "the pack records the null rather than promoting the edge",
     "evidence": "HYPOTHESIS"},
    {"id": "LK-E3", "source": "CPC month-end retail fuel price revision under the cost-reflective "
                              "formula", "target": "XBRUSD", "targets": ("XBRUSD", "XTIUSD"),
     "to_country": "global", "sign": "+",
     "mechanism": "an INPUT-direction edge: Brent and the rupee pass into the domestic price on "
                  "a published monthly clock. An outward effect on crude is NOT expected from an "
                  "importer this size and is measured honestly against the mid-month placebo",
     "horizon": "0 to 2 sessions", "horizon_class": "intraday", "lag_days": 0.0,
     "actor": "Ceylon Petroleum Corporation and the Ministry of Energy",
     "constraint": "the formula must be applied at month end under the EFF benchmark",
     "flow": "administered price pass-through",
     "condition": "months in which the formula was actually applied rather than suspended",
     "control": "the 15th of the same months; the matched weekday-and-hour control",
     "falsifier": "the revision window matches the 15th placebo or the matched control",
     "evidence": "HYPOTHESIS"},
    {"id": "LK-E4", "source": "Special Commodity Levy gazettes on sugar and the import-licence "
                              "regime", "target": "SUGAR", "targets": ("SUGAR", "SUGARRAW"),
     "to_country": "global", "sign": "+",
     "mechanism": "the island imports essentially all its sugar and prices it by gazette; a levy "
                  "cut or a licence release is a dated step in import demand, small in world "
                  "terms and dated precisely, which is the only reason it is worth testing",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 2.0,
     "actor": "the Ministry of Finance and the licensed importers",
     "constraint": "the domestic price is administered and the stock position is thin",
     "flow": "import demand", "condition": "gazette dates only",
     "control": "India's sugar export-policy dates on the same instruments; non-gazette days",
     "falsifier": "levy gazette windows match the matched weekday control -- expected for an "
                  "importer this small, and recorded",
     "evidence": "HYPOTHESIS"},
    {"id": "LK-E5", "source": "Wheat and flour import tenders and the administered bread price",
     "target": "WHEAT", "targets": ("WHEAT",), "to_country": "global", "sign": "+",
     "mechanism": "Sri Lanka grows NO wheat and imports about a million tonnes a year through a "
                  "concentrated milling trade; the tenders and the administered bread price are "
                  "dated demand events on a market where the island is a marginal buyer",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 2.0,
     "actor": "the millers and the Ministry of Trade",
     "constraint": "the whole requirement is imported and cannot be substituted quickly",
     "flow": "import demand", "condition": "tender and price-gazette dates",
     "control": "Egypt's GASC tender windows, the reference importer, to scale the effect; "
                "non-tender days",
     "falsifier": "tender windows on WHEAT match the matched weekday control",
     "evidence": "HYPOTHESIS"},
    {"id": "LK-E6", "source": "The monthly remittance print and SLBFE departures for foreign "
                              "employment", "target": "XAUUSD", "targets": ("XAUUSD", "USDINR"),
     "to_country": "global", "sign": "+",
     "mechanism": "remittances are the largest net inflow and a measurable share reaches the "
                  "jewellery and pawning market, which is the executable gold leg; the New Year "
                  "and Eid months carry the seasonal peak",
     "horizon": "the two weeks into the festival", "horizon_class": "multi_day", "lag_days": 0.0,
     "actor": "Sri Lankan migrant workers and the pawn-broking banks",
     "constraint": "the surrender rule and the official-street spread decide the channel",
     "flow": "retail demand", "condition": "a narrow official-street spread",
     "control": "the same festival windows in wide-spread years; India's Diwali windows",
     "falsifier": "the festival window on gold matches the matched non-festival months once the "
                  "spread and the departure pipeline are controlled",
     "evidence": "HYPOTHESIS"},
    {"id": "LK-E7", "source": "IMF EFF review milestones and the DCS nominal-USD-GDP release "
                              "that the macro-linked bonds key off",
     "target": "UST10Y", "targets": ("UST10Y", "US500"), "to_country": "global", "sign": "-",
     "mechanism": "a restructured frontier sovereign whose contracted debt service steps with a "
                  "published GDP statistic; the review and the GDP print reprice the stress "
                  "premium, and the desk reads that on the frontier rate and global risk because "
                  "the bonds themselves are absent from the broker",
     "horizon": "0 to 5 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "the IMF Board and the external bondholders",
     "constraint": "comparability of treatment and the DSA's debt-service envelope",
     "flow": "sovereign repricing",
     "condition": "Board dates and GDP releases at defined test dates",
     "control": "IMF Board dates for other programme countries; non-test GDP releases",
     "falsifier": "no abnormal move on UST10Y or US500 beyond the matched control -- the "
                  "expected result for an issuer this small, recorded as a null",
     "evidence": "HYPOTHESIS"},
    {"id": "LK-E8", "source": "Chinese creditor milestones: the CDB and EXIM treatments, the "
                              "Hambantota lease and the Port City build",
     "target": "USDCNH", "targets": ("USDCNH", "CHINAH"), "to_country": "cn", "sign": "+",
     "mechanism": "a Belt-and-Road creditor event settled in the creditor's own currency is "
                  "marginal yuan demand; negligible and recorded as such rather than dressed up",
     "horizon": "0 to 5 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "China EXIM, the China Development Bank and China Merchants Port",
     "constraint": "the IMF's comparability requirement",
     "flow": "debt treatment", "condition": "milestone announcement dates",
     "control": "other Belt-and-Road restructuring dates on the same instruments",
     "falsifier": "no measurable move (the expected result)",
     "evidence": "HYPOTHESIS"},
    {"id": "LK-E9", "source": "SLPA Colombo transhipment volume and the Indian feeder trade",
     "target": "USDSGD", "targets": ("USDSGD", "USDINR"), "to_country": "global", "sign": "-",
     "mechanism": "Colombo is the transhipment gateway for the Indian subcontinent and competes "
                  "directly with Singapore and Klang; a shift in its transhipment share is an "
                  "Asian trade-cycle observable with a monthly physical count behind it",
     "horizon": "1 to 3 months", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "the Sri Lanka Ports Authority and the terminal operators",
     "constraint": "berth and crane capacity against the Indian ports' own expansion",
     "flow": "transhipment volume", "condition": "months with a published throughput print",
     "control": "Singapore's own container throughput in the same months",
     "falsifier": "Colombo transhipment surprises carry no information for USDSGD or USDINR "
                  "beyond what Singapore's throughput already carries",
     "evidence": "HYPOTHESIS"},
)

# --------------------------------------------------------------------------- policy eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    {"name": "the post-war boom and the commercial-borrowing build-up", "start": "2009-05-19",
     "end": "2019-04-20",
     "regime": "the end of the civil war, a decade of international sovereign bond issuance, a "
               "managed rupee defended with reserves, and the 2017 Hambantota lease",
     "markers": ("2009-05-19 the end of the war", "2016-06-03 the previous IMF EFF",
                 "2017-07-29 the Hambantota 99-year lease"),
     "why_it_matters": "the debt stock every later mechanism is about is accumulated here, and "
                       "the rupee's behaviour under a defended peg is not exchangeable with its "
                       "behaviour after the float",
     "status": "SETTLED"},
    {"name": "the Easter attacks, the tax cuts and the loss of market access",
     "start": "2019-04-21", "end": "2021-04-26",
     "regime": "the tourism collapse of 2019, the deep November 2019 tax cuts, the 2020 import "
               "controls, successive rating downgrades and the end of bond-market access",
     "markers": ("2019-04-21 the Easter Sunday attacks",
                 "2019-11-27 the tax cuts", "2020-03-20 the first import-control gazettes"),
     "why_it_matters": "the two shocks that removed the inflows and the revenue; a tourism or "
                       "revenue study pooled across this boundary measures the shock, not the "
                       "seasonality",
     "status": "SETTLED"},
    {"name": "the fertiliser ban, the controls and the default", "start": "2021-04-27",
     "end": "2023-03-19",
     "regime": "the chemical-fertiliser import ban, the surrender requirement, the March 2022 "
               "float from about 200 to about 370, the April 2022 external-debt standstill, the "
               "fuel queues and power cuts, the emergency +700bp, the CSE suspension",
     "markers": ("2021-04-27 the fertiliser import ban",
                 "2022-03-07 the float", "2022-04-08 the emergency +700bp",
                 "2022-04-12 the external-debt standstill",
                 "2022-04-18 the five-session CSE suspension",
                 "2022-07-09 the occupation of the President's House"),
     "why_it_matters": "every stress mechanism in this pack is identified here, and nothing "
                       "measured in this era is exchangeable with a normal one",
     "status": "SETTLED"},
    {"name": "the EFF, the domestic debt optimisation and the disinflation", "start": "2023-03-20",
     "end": "2024-12-19",
     "regime": "the EFF approved, the domestic debt operation completed, inflation from over "
               "60% to near zero and below it, the policy rate cut back to single digits, and "
               "the transition to a single Overnight Policy Rate",
     "markers": ("2023-03-20 EFF approval", "2023-09-21 the domestic debt optimisation settled",
                 "2024-11-27 the single-policy-rate announcement"),
     "why_it_matters": "the rate series BREAKS at the OPR transition and the CPI turns negative "
                       "inside this era; a policy-surprise study that splices the two rate "
                       "definitions is measuring an artefact",
     "status": "SETTLED"},
    {"name": "the restructured sovereign and the single policy rate", "start": "2024-12-20",
     "end": "2026-12-31",
     "regime": "the ISB exchange settled into macro-linked and governance-linked bonds, the OPR "
               "as the single operating target, quarterly EFF reviews, reserves rebuilt and "
               "tourism and remittances recovering",
     "markers": ("2024-12-20 the ISB exchange settlement",
                 "the quarterly EFF review dates through the period"),
     "why_it_matters": "the current regime and the only one in which the GDP trigger exists; the "
                       "decision sample here is cuts and holds under a rate definition that did "
                       "not exist before it",
     "status": "OPEN"},
)

ACCESS_CONSTRAINTS: tuple[dict[str, Any], ...] = (
    {"constraint": "the rupee is not quoted by this broker",
     "measured": "data/universe/universe.json holds no LKR symbol",
     "consequence": "every domestic mechanism terminates in a regional cross, a soft, an energy "
                    "leg, gold or the frontier rate; LKR is an INPUT and never a cell"},
    {"constraint": "the ASPI, the S&P SL20, the restructured ISBs and the tea auction have no "
                   "instrument here",
     "measured": "no Sri Lankan index, bond or soft contract is in the universe",
     "consequence": "the CSE's daily net-foreign line and the auction's weekly averages are the "
                    "OBJECTS; the index and the price are transmission targets"},
    {"constraint": "the OPR transition date is stated two ways in the desk's own sources",
     "measured": "the pack carries a 2024-11-27 announcement; the builder's brief recorded a "
                 "May 2025 operational date and the two have not been reconciled against "
                 "cbsl.gov.lk",
     "consequence": "DISPUTED, not resolved by preference: no level cell is compiled across the "
                    "transition, the pre- and post-transition rate series are never spliced, and "
                    "the first session to read the release settles it"},
    {"constraint": "only four Monetary Policy Review dates have been read off a CBSL release",
     "measured": "CENTRAL_BANK.decision_dates holds four; the rule says eight a year",
     "consequence": "the rest are carried in REPORTED_DECISION_DATES as a SEPARATE arm that never "
                    "pools with the verified sample, and the gap is visible rather than absent"},
    {"constraint": "the Poya calendar is lunar and the 2026 rows are computed, not gazetted",
     "measured": "POYA_DAYS marks 2024-2025 ANNOUNCED and 2026 PROJECTED; 2026 carries thirteen "
                 "full moons and therefore an intercalary Adhi Poya whose naming is the "
                 "calendar committee's",
     "consequence": "PROJECTED dates are never pooled with ANNOUNCED ones, and the projected "
                    "rows serve as part of the placebo rather than as events"},
    {"constraint": "the Ceypetco price page is overwritten on every revision and the AIS "
                   "aggregators' terms forbid bulk extraction",
     "measured": "the live page carries only the current price; the aggregators' free-tier terms; "
                 "both registered machine_use_allowed=false or vintage-only",
     "consequence": "the fuel price vintage comes from the Wayback snapshots and the press, and "
                    "port calls are UNMEASURED with the SLPA monthly count used instead"},
)
INSTITUTIONAL_FLOW_SOURCES: tuple[str, ...] = (
    "CSE daily foreign purchases and sales", "CBSL foreign holdings of Treasury bills and bonds",
    "CBSL monthly remittances by corridor", "SLBFE monthly departures",
    "the EPF's disclosed holdings in the CSE quarterlies")
SERIES: dict[str, str] = {
    "LK_POLICY": "CBSL:opr", "LK_RESERVES": "CBSL:official_reserve_assets",
    "LK_REMIT": "CBSL:remittances", "LK_TEA_PRICE": "CTA:auction_average",
    "LK_TEA_EXPORTS": "CBSL:tea_export_volume", "LK_FUEL": "CPC:retail_price",
    "LK_ARRIVALS": "SLTDA:arrivals", "LK_CCPI": "DCS:ccpi",
    "LK_TRANSHIP": "SLPA:transhipment_teu", "LK_FOREIGN_FLOW": "CSE:net_foreign",
    "LK_DEPARTURES": "SLBFE:departures",
}

# --------------------------------------------------------------------------- assembly
_PACK_FIELDS: tuple[str, ...] = (
    "code", "name", "region_command", "currency", "executable_instruments", "central_bank",
    "fixing_conventions", "settlement_conventions", "exchanges", "holidays_rule",
    "fiscal_year_end", "positioning_sources", "native_languages", "terminology", "source_classes",
    "datasets", "actors", "domains", "custom_miners", "transmission_edges_seed", "policy_eras")


def as_dict() -> dict[str, Any]:
    """The pack as a plain mapping: the framework fields plus everything the framework has no
    slot for, carried beside them so nothing is silently dropped."""
    return {
        "code": CODE, "name": NAME, "region_command": REGION_COMMAND, "currency": CURRENCY,
        "executable_instruments": EXECUTABLE_INSTRUMENTS, "central_bank": CENTRAL_BANK,
        "fixing_conventions": FIXING_CONVENTIONS,
        "settlement_conventions": SETTLEMENT_CONVENTIONS, "exchanges": EXCHANGES,
        "release_classes": RELEASE_CLASSES, "session_windows": SESSION_WINDOWS,
        "holidays_rule": HOLIDAYS_RULE, "fiscal_year_end": FISCAL_YEAR_END,
        "positioning_sources": POSITIONING_SOURCES, "native_languages": NATIVE_LANGUAGES,
        "terminology": TERMINOLOGY, "source_classes": SOURCE_CLASSES,
        "source_layers": SOURCE_LAYERS, "layer_absences": LAYER_ABSENCES,
        "layer_terms": layer_terms(), "source_layer_coverage": source_layer_coverage(),
        "datasets": DATASETS, "actors": ACTORS, "domains": DOMAINS,
        "custom_miners": CUSTOM_MINERS, "miner_domains": MINER_DOMAINS,
        "transmission_edges_seed": TRANSMISSION_EDGES_SEED, "policy_eras": POLICY_ERAS,
        "transmission_targets": TRANSMISSION_TARGETS, "access_constraints": ACCESS_CONSTRAINTS,
        "region_desk": REGION_DESK, "forest": FOREST, "cot_currency": COT_CURRENCY,
        "export_economy": EXPORT_ECONOMY, "retail_leverage_regime": RETAIL_LEVERAGE_REGIME,
        "institutional_flow_sources": INSTITUTIONAL_FLOW_SOURCES, "series": SERIES,
        "reported_decision_dates": REPORTED_DECISION_DATES, "mission": MISSION,
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


def _holiday_rule_row() -> dict[str, Any]:
    """The framework's HolidayRule shape: every closed date the rule produces for 2024-2026."""
    dates = sorted({d.isoformat() for y in HOLIDAYS_RULE["years"] for d in market_holidays(y)})
    return {"dates": tuple(dates),
            "fixed_md": tuple(f"{m:02d}-{d:02d}" for m, d, _ in FIXED_NATIONAL),
            "weekly_closed": (5, 6), "notes": HOLIDAYS_RULE["authority"]}


def lab_kwargs() -> dict[str, Any]:
    """The keyword set `country_lab.CountryPack` is built from, in the shapes its coercion reads
    best: sources as rows AND as tagged lines, positioning and miners as strings, the holiday
    rule as dates, absent layers as a mapping."""
    data = as_dict()
    real = [s for s in SOURCE_CLASSES if not str(s["id"]).startswith("absent_")]
    data.update({
        "code": CODE.lower(),
        "positioning_sources": tuple(str(p["name"]) for p in POSITIONING_SOURCES),
        "custom_miners": tuple(str(m["entry"]) for m in CUSTOM_MINERS),
        "source_classes": tuple(_source_line(s) for s in real),
        "sources": tuple(_source_row(s) for s in real),
        "absent_layers": dict(LAYER_ABSENCES),
        "holidays_rule": _holiday_rule_row(),
    })
    return data


def pack() -> Any:
    """`country_lab.CountryPack` when the framework is present, else the mapping. Imported
    lazily so this department stays importable on a tree where the framework is not."""
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
