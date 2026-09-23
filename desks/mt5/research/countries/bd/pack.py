"""BANGLADESH: one export, one import, a crawling peg, and a week that starts on Sunday.

WHAT BANGLADESH IS AS A MARKET MECHANISM, AND WHY IT IS NOT A SMALLER INDIA OR PAKISTAN. Five
things belong to this economy and to no other in the desk's book, and each is why a domain
below exists rather than a row in a generic frontier-market domain:

  1. THE ECONOMY IS A GARMENT FACTORY THAT IMPORTS ITS COTTON. Ready-made garments are about
     85% of goods exports (US$40-45bn), and the mills that feed them make Bangladesh the LARGEST
     cotton importer in the world in most years (1.5-2 mt). The Export Promotion Bureau prints
     the export figure in the first week of every month and the BGMEA publishes the order book
     commentary; the cotton import that follows is the cleanest outward edge the country has,
     and it reaches the ICE contract.

  2. THE EXCHANGE RATE IS A DECLARED CRAWL. After two years of a fixed official rate that the
     kerb and the exporters' 'encashment' rate ignored, Bangladesh Bank declared a CRAWLING PEG
     on 2024-05-08 (mid-rate 117, band +/-1), then moved to a managed float in May 2025 under
     the IMF programme. The gap between the official, the kerb and the remittance-house rates is
     a state variable, exactly as in Pakistan, and the 2.5% remittance incentive is the policy
     lever that closes it.

  3. THE WEEK IS SUNDAY TO THURSDAY. Banks and the Dhaka Stock Exchange close on FRIDAY and
     SATURDAY. A study that assumes a Saturday-Sunday weekend puts every Bangladeshi Friday
     into the wrong bucket, and the Thursday afternoon is the country's week-end liquidity
     window, not Friday's.

  4. 2024 WAS A REGIME CHANGE WITH A DATE. The 5 August 2024 fall of the Hasina government, the
     interim administration under Muhammad Yunus, a new central bank governor (Ahsan Mansur, 14
     August 2024), the cancellation of eight public holidays (October 2024), the unification of
     the exchange rate and the IMF programme's re-negotiation are one break, and the diaspora's
     July 2024 'remittance boycott' is a natural experiment on the remittance channel that no
     other country offers.

  5. ADMINISTERED PRICES HAVE A CALENDAR. The Bangladesh Petroleum Corporation moved to a
     monthly automatic fuel-price formula in March 2024; the Bangladesh Jewellers' Association
     (BAJUS) sets the retail gold price by karat and announces every change; the Dhaka Stock
     Exchange ran a FLOOR PRICE rule from July 2022 to January 2024 that froze most of the
     market. Each is a dated rule state a screen must carry or mis-measure.

WHAT IS EXECUTABLE AND WHAT IS NOT. The taka, the DSEX, the T-bill curve, the BAJUS gold price
and the JKM cargo benchmark are absent from `data/universe/universe.json`. Every one is named in
`TRANSMISSION_TARGETS` with the broker symbols its mechanism reaches (L1.49). No share CFD
appears in any instrument tuple: Grameenphone, BAT Bangladesh and Square are actors at most.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, timedelta
from typing import Any

# --------------------------------------------------------------------------- identity
CODE = "BD"
NAME = "Bangladesh"
REGION_COMMAND = "asia"
REGION_DESK = "SOUTH_ASIA"
FOREST = "south_asia"
CURRENCY = "BDT"
FISCAL_YEAR_END = "06-30"          # 1 July to 30 June; the budget is presented in early June
NATIVE_LANGUAGES: tuple[str, ...] = ("bn", "en-BD")
COT_CURRENCY = ""
EXPORT_ECONOMY = "manufacturing_exporter"      # ready-made garments ~85% of goods exports
RETAIL_LEVERAGE_REGIME = "restricted"          # BSEC margin rules; no retail forex/CFD
MISSION = ("mine Bangladesh as the garment-and-cotton, crawling-peg, Friday-Saturday-weekend "
           "economy it is: the EPB export print, the cotton import it implies, the remittance "
           "channel and its 2024 boycott, the BB rate regime, the BPC fuel formula, the BAJUS "
           "gold price, the DSE floor-price rule state, and the LNG tenders")

EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "COTTON",                                          # the world's largest cotton importer
    "WHEAT", "SOYBEAN", "SUGAR",                       # the food and feed import bill
    "XTIUSD", "XBRUSD", "XNGUSD",                      # the BPC formula and the LNG tenders
    "XAUUSD",                                          # BAJUS, Dubai smuggling, Eid
    "USDINR", "USDCNH",                                # the two neighbours' crosses
    "EURUSD", "GBPUSD", "USDX",                        # the RMG destinations and the dollar
    "US500",                                           # US retail demand for garments
)

TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "USD/BDT official, interbank and kerb rates", "venue": "Bangladesh Bank / banks",
     "why": "the currency every mechanism here is about; absent, so read through the trade it "
            "drives", "proxies": ("USDINR", "COTTON", "USDX")},
    {"name": "DSEX and the DS30", "venue": "Dhaka Stock Exchange",
     "why": "no CFD is quoted; the floor-price regime (2022-07 to 2024-01) is a rule state the "
            "pack carries", "proxies": ("US500", "USDINR")},
    {"name": "Bangladesh Bank 91/182/364-day T-bill cut-offs and the repo rate",
     "venue": "Bangladesh Bank auctions",
     "why": "the domestic rate path; the 'SMART' lending-rate formula (2023-24) was built on "
            "the 182-day yield", "proxies": ("USDINR",)},
    {"name": "BAJUS retail gold price (22-karat per bhori)", "venue": "Bangladesh Jewellers' "
                                                                       "Association",
     "why": "an administered retail price that follows LBMA x the kerb rate with a lag; the "
            "premium is the smuggling and stress signal", "proxies": ("XAUUSD",)},
    {"name": "Platts JKM LNG (the Petrobangla tender benchmark)", "venue": "Platts",
     "why": "spot cargoes are JKM-priced; XNGUSD is a weak proxy and every gas edge says so",
     "proxies": ("XNGUSD", "XBRUSD")},
    {"name": "Bangladesh sovereign risk (no traded Eurobond; the IMF ECF/EFF/RSF programme)",
     "venue": "IMF / bilateral", "why": "the programme review calendar is the stress clock",
     "proxies": ("USDINR", "XAUUSD")},
    {"name": "Chattogram port container throughput and the Matarbari coal terminal",
     "venue": "Chittagong Port Authority",
     "why": "the physical count of the import bill and the RMG raw-material inflow",
     "proxies": ("COTTON", "XBRUSD")},
)

# --------------------------------------------------------------------------- the central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "Bangladesh Bank",
    "short": "BB",
    "framework": "crawling_peg",
    "committee": "the Governor and the monetary policy committee; the Monetary Policy Statement "
                 "is published twice a year (January and June/July) and the repo rate is "
                 "changed by circular between statements",
    "policy_instrument": "the overnight repo (policy) rate inside a corridor (standing "
                         "lending and deposit facilities), and since 2024-05-08 a declared "
                         "crawling-peg mid-rate for the taka",
    "mandate": "price stability and growth under the Bangladesh Bank Order 1972; an IMF ECF/EFF "
               "(2023-01-30, US$4.7bn, later augmented) with quantitative targets on net "
               "reserves",
    "decision_rule": "two Monetary Policy Statements a year (H1 in January, H2 in June or "
                     "July) plus rate changes by circular with immediate effect; the "
                     "crawling-peg mid-rate was announced 2024-05-08 and the managed float on "
                     "2025-05-14",
    "decision_calendar_rule": "semi-annual statements; circulars between them are dated events "
                              "that the press reports the same day",
    "decision_dates": ("2024-01-17", "2024-05-08", "2024-07-18", "2024-08-25", "2024-09-24",
                       "2024-10-22", "2025-02-10", "2025-05-14", "2025-07-31"),
    "dates_status": "2024-01-17 the H1 statement (repo to 8.00%); 2024-05-08 the crawling peg "
                    "and repo 8.50%; 2024-07-18 the H2 statement; 2024-08-25 repo 9.00%; "
                    "2024-09-24 repo 9.50%; 2024-10-22 repo 10.00%; 2025-02-10 the H1 "
                    "statement; 2025-05-14 the managed float announced; 2025-07-31 the H2 "
                    "statement -- re-verify each against the BB circular before a cell is "
                    "compiled; 2026: NOT LISTED, the calendar is not published ahead",
    "decision_time_utc": "09:00",
    "announce_local": "afternoon Asia/Dhaka (UTC+6, no DST); the minute varies",
    "dst_rule": "Bangladesh keeps UTC+6 all year",
    "minutes_lag_days": 0,
    "publication_classes": ("monetary_policy_statement", "circulars", "monthly_major_economic_"
                            "indicators", "remittance_data", "reserves_bpm6"),
    "policy_rate_series": "BB:repo_rate",
    "expected_rate_series": "UNMEASURED",
    "consensus_proxy": "the 182-day T-bill cut-off and the press previews (The Daily Star, "
                       "Financial Express)",
    "consensus_proxy_trap": "the T-bill cut-off is administered through the auction committee's "
                            "devolvement; it is not a free market expectation",
    "reserves_clock": "gross reserves are published weekly in the BPM6 measure since 2023 "
                      "beside the older gross measure; the two differ by about US$5bn and a "
                      "study must name which it read",
    "programme": "IMF ECF/EFF/RSF approved 2023-01-30; reviews semi-annual; the 2024 political "
                 "change re-opened the programme's conditions",
    "regime_break": "2024-08-05 the government fell; 2024-08-14 Ahsan H. Mansur became "
                    "Governor; the exchange-rate unification and the bank-sector clean-up date "
                    "from there",
    "root": "https://www.bb.org.bd",
}

# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "Bangladesh Bank exchange rate posting (official/interbank)",
     "local": "posted each banking day, about 11:00 Asia/Dhaka", "time_utc": "05:00",
     "time_utc_dst": "05:00", "dst_rule": "none (UTC+6 all year)",
     "instruments": ("USDINR", "USDX"), "window_minutes": 60,
     "why": "the official reference; under the crawling peg it moved inside a declared band"},
    {"name": "BAJUS gold price announcement",
     "local": "announced by press release, usually late afternoon Dhaka, effective the next day",
     "time_utc": "11:00", "time_utc_dst": "11:00", "dst_rule": "none",
     "instruments": ("XAUUSD",), "window_minutes": 60,
     "why": "the administered retail gold price; the premium to LBMA x kerb is BD-H's signal"},
    {"name": "BPC monthly fuel price formula (effective the 1st)",
     "local": "notified at the end of the month, effective 00:00 Dhaka on the 1st",
     "time_utc": "18:00", "time_utc_dst": "18:00", "dst_rule": "none",
     "instruments": ("XBRUSD", "XTIUSD"), "window_minutes": 60,
     "why": "the automatic pass-through of Brent and the taka since March 2024"},
    {"name": "LBMA gold price PM auction", "local": "15:00 Europe/London", "time_utc": "15:00",
     "time_utc_dst": "14:00", "dst_rule": "GMT/BST", "instruments": ("XAUUSD",),
     "window_minutes": 15, "why": "the dollar leg of the BAJUS price"},
    {"name": "DSE close", "local": "14:30 Asia/Dhaka (Sunday-Thursday)", "time_utc": "08:30",
     "time_utc_dst": "08:30", "dst_rule": "none", "instruments": ("US500",),
     "window_minutes": 30, "why": "the end of the Bangladeshi week is THURSDAY 08:30 UTC"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "BPC fuel price month", "kind": "day_of_month", "days": (1,), "roll": "none",
     "window_utc": ("17:00", "19:00"), "instruments": ("XBRUSD", "XTIUSD"),
     "why": "the formula price takes effect on the 1st"},
    {"name": "EPB export print", "kind": "day_of_month", "days": (3, 4, 5), "roll": "next",
     "window_utc": ("06:00", "12:00"), "instruments": ("COTTON", "EURUSD"),
     "why": "the monthly export figure lands in the first week"},
    {"name": "The Bangladeshi weekend (Friday-Saturday)", "kind": "weekday", "weekday": 3,
     "roll": "previous", "window_utc": ("06:00", "09:00"), "instruments": ("USDINR", "XAUUSD"),
     "why": "Thursday afternoon is the week-end liquidity window; Friday is closed"},
    {"name": "Month-end LC settlements for fuel, cotton and food imports", "kind": "month_end",
     "roll": "previous", "window_utc": ("04:00", "11:00"),
     "instruments": ("XBRUSD", "COTTON", "WHEAT"),
     "why": "the importers' dollar demand clusters; the 2022-24 LC rationing was its own regime"},
    {"name": "Fiscal year end (30 June)", "kind": "fiscal_year_end", "roll": "previous",
     "window_utc": ("04:00", "11:00"), "instruments": ("USDINR",),
     "why": "the reserves target and the budget clock"},
)

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Dhaka Stock Exchange (DSE) -- DSEX",
     "index_symbols": (),
     "open_local": "10:00", "close_local": "14:30 (post-close to 14:50)",
     "open_utc": "04:00", "close_utc": "08:30", "dst_rule": "none (UTC+6)",
     "auction": "pre-open 09:55-10:00; closing price is the last 30 minutes' weighted average",
     "expiry_rule": "no listed derivatives",
     "holidays": "government holidays; the weekend is FRIDAY and SATURDAY",
     "notes": "NO CFD IS QUOTED. The FLOOR PRICE rule (2022-07-28 to 2024-01-18, lifted in "
              "phases) froze most listed prices at a reference level: a rule state that makes "
              "every index statistic of that window an artefact"},
    {"name": "Chittagong Stock Exchange (CSE)", "index_symbols": (),
     "open_local": "10:00", "close_local": "14:30", "open_utc": "04:00", "close_utc": "08:30",
     "dst_rule": "none", "auction": "n/a", "expiry_rule": "n/a",
     "holidays": "as the DSE", "notes": "thin; the DSE sets the price"},
)

SESSION_WINDOWS: tuple[dict[str, Any], ...] = (
    {"name": "bd_dhaka_morning", "start_utc": "04:00", "end_utc": "06:00",
     "notes": "the DSE open, the BB rate posting, the EPB and BBS releases"},
    {"name": "bd_thursday_close", "start_utc": "07:30", "end_utc": "09:00",
     "notes": "the week ends on Thursday: the last liquidity window before the two-day close"},
    {"name": "bd_fuel_and_gold_notices", "start_utc": "10:00", "end_utc": "12:00",
     "notes": "BAJUS announcements and the month-end BPC notification"},
)

RELEASE_CLASSES: tuple[dict[str, Any], ...] = (
    {"name": "EPB monthly export earnings", "cadence": "monthly", "time_utc": "06:00",
     "source": "Export Promotion Bureau", "actual_series": "EPB:exports",
     "expected_series": "UNMEASURED",
     "notes": "the first week; RMG (knit and woven) is the line; REVISED in 2024 when the EPB "
              "and the BB reconciled a US$10bn+ overstatement -- a vintage break"},
    {"name": "Bangladesh Bank monthly remittances", "cadence": "monthly", "time_utc": "06:00",
     "source": "Bangladesh Bank", "actual_series": "BB:remittances",
     "expected_series": "UNMEASURED", "notes": "the 1st-3rd; the Eid months and the incentive "
                                              "rate explain most of the variance; July 2024 is "
                                              "the boycott month"},
    {"name": "BBS CPI", "cadence": "monthly", "time_utc": "06:00", "source": "Bangladesh Bureau "
                                                                              "of Statistics",
     "actual_series": "BBS:cpi", "expected_series": "UNMEASURED",
     "notes": "food inflation dominated by rice; the base year was changed to 2021-22 in 2024"},
    {"name": "BPC fuel price notification", "cadence": "monthly", "time_utc": "18:00",
     "source": "Bangladesh Petroleum Corporation / Energy Division",
     "actual_series": "BPC:fuel", "expected_series": "UNMEASURED",
     "notes": "the automatic formula since March 2024; the last days of the month"},
    {"name": "BAJUS gold price change", "cadence": "weekly", "time_utc": "11:00",
     "source": "BAJUS", "actual_series": "BAJUS:gold_22k", "expected_series": "n/a",
     "notes": "irregular; announced whenever the international price or the taka moves enough"},
    {"name": "Petrobangla LNG spot tender", "cadence": "monthly", "time_utc": "UNMEASURED",
     "source": "Petrobangla / RPGCL", "actual_series": "RPGCL:tenders", "expected_series": "n/a",
     "notes": "tenders through the master sale-and-purchase agreements; awards are reported"},
    {"name": "IMF review of the ECF/EFF/RSF", "cadence": "quarterly", "time_utc": "UNMEASURED",
     "source": "IMF", "actual_series": "IMF:bangladesh_reviews", "expected_series": "n/a",
     "notes": "staff-level agreement, Board approval and disbursement are three dated events"},
)

# --------------------------------------------------------------------------- holidays
#: FIXED national holidays. THE OCTOBER 2024 CANCELLATIONS ARE A REGIME FACT: the interim
#: government removed eight days including 15 August (National Mourning Day) and 17 March
#: (Mujib's birthday), so the 2024 and 2025 calendars differ by decree, not by drift.
FIXED_NATIONAL: dict[int, tuple[tuple[int, int, str], ...]] = {
    2024: ((2, 21, "Shaheed Day / International Mother Language Day"),
           (3, 17, "Sheikh Mujib's birthday (cancelled from October 2024)"),
           (3, 26, "Independence Day"), (4, 14, "Pahela Baishakh (Bengali New Year)"),
           (5, 1, "May Day"), (8, 15, "National Mourning Day (cancelled from October 2024)"),
           (12, 16, "Victory Day"), (12, 25, "Christmas Day")),
    2025: ((2, 21, "Shaheed Day / International Mother Language Day"),
           (3, 26, "Independence Day"), (4, 14, "Pahela Baishakh (Bengali New Year)"),
           (5, 1, "May Day"), (8, 5, "July Mass Uprising Day (new from 2025)"),
           (12, 16, "Victory Day"), (12, 25, "Christmas Day")),
    2026: ((2, 21, "Shaheed Day / International Mother Language Day"),
           (3, 26, "Independence Day"), (4, 14, "Pahela Baishakh (Bengali New Year)"),
           (5, 1, "May Day"), (8, 5, "July Mass Uprising Day"),
           (12, 16, "Victory Day"), (12, 25, "Christmas Day")),
}
#: Religious holidays as GAZETTED (2024-2025) and PROJECTED (2026). Eid blocks are routinely
#: extended by executive order; the Eid-ul-Fitr 2025 block ran nine days with the weekends.
LUNAR_AND_RELIGIOUS: dict[int, tuple[tuple[date, str, str], ...]] = {
    2024: ((date(2024, 2, 26), "Shab-e-Barat", "GAZETTED"),
           (date(2024, 4, 7), "Shab-e-Qadr", "GAZETTED"),
           (date(2024, 4, 10), "Eid-ul-Fitr (day 1)", "GAZETTED"),
           (date(2024, 4, 11), "Eid-ul-Fitr (day 2)", "GAZETTED"),
           (date(2024, 4, 12), "Eid-ul-Fitr (day 3, Friday)", "GAZETTED"),
           (date(2024, 5, 23), "Buddha Purnima", "GAZETTED"),
           (date(2024, 6, 16), "Eid-ul-Azha (day 1, Sunday)", "GAZETTED"),
           (date(2024, 6, 17), "Eid-ul-Azha (day 2)", "GAZETTED"),
           (date(2024, 6, 18), "Eid-ul-Azha (day 3)", "GAZETTED"),
           (date(2024, 7, 17), "Ashura", "GAZETTED"),
           (date(2024, 8, 26), "Janmashtami", "GAZETTED"),
           (date(2024, 9, 16), "Eid-e-Miladunnabi", "GAZETTED"),
           (date(2024, 10, 13), "Bijoya Dashami (Durga Puja, Sunday)", "GAZETTED")),
    2025: ((date(2025, 2, 15), "Shab-e-Barat (Saturday)", "GAZETTED"),
           (date(2025, 3, 28), "Shab-e-Qadr (Friday)", "GAZETTED"),
           (date(2025, 3, 30), "Eid-ul-Fitr block (Sunday)", "GAZETTED"),
           (date(2025, 3, 31), "Eid-ul-Fitr (day 1)", "GAZETTED"),
           (date(2025, 4, 1), "Eid-ul-Fitr (day 2)", "GAZETTED"),
           (date(2025, 4, 2), "Eid-ul-Fitr (day 3)", "GAZETTED"),
           (date(2025, 4, 3), "Eid-ul-Fitr block (extended)", "GAZETTED"),
           (date(2025, 5, 11), "Buddha Purnima (Sunday)", "GAZETTED"),
           (date(2025, 6, 5), "Eid-ul-Azha block (Thursday)", "GAZETTED"),
           (date(2025, 6, 7), "Eid-ul-Azha (day 1, Saturday)", "GAZETTED"),
           (date(2025, 6, 8), "Eid-ul-Azha (day 2)", "GAZETTED"),
           (date(2025, 6, 9), "Eid-ul-Azha (day 3)", "GAZETTED"),
           (date(2025, 6, 10), "Eid-ul-Azha block (extended)", "GAZETTED"),
           (date(2025, 6, 11), "Eid-ul-Azha block (extended)", "GAZETTED"),
           (date(2025, 7, 6), "Ashura (Sunday)", "GAZETTED"),
           (date(2025, 8, 16), "Janmashtami (Saturday)", "GAZETTED"),
           (date(2025, 9, 5), "Eid-e-Miladunnabi (Friday)", "GAZETTED"),
           (date(2025, 10, 1), "Maha Navami (new: two Puja days from 2024)", "GAZETTED"),
           (date(2025, 10, 2), "Bijoya Dashami", "GAZETTED")),
    2026: ((date(2026, 2, 4), "Shab-e-Barat", "PROJECTED"),
           (date(2026, 3, 17), "Shab-e-Qadr", "PROJECTED"),
           (date(2026, 3, 20), "Eid-ul-Fitr (day 1, Friday)", "PROJECTED"),
           (date(2026, 3, 22), "Eid-ul-Fitr (day 3, Sunday)", "PROJECTED"),
           (date(2026, 5, 1), "Buddha Purnima (coincides with May Day)", "PROJECTED"),
           (date(2026, 5, 27), "Eid-ul-Azha (day 1)", "PROJECTED"),
           (date(2026, 5, 28), "Eid-ul-Azha (day 2)", "PROJECTED"),
           (date(2026, 6, 25), "Ashura", "PROJECTED"),
           (date(2026, 8, 25), "Eid-e-Miladunnabi", "PROJECTED"),
           (date(2026, 10, 20), "Maha Navami", "PROJECTED"),
           (date(2026, 10, 21), "Bijoya Dashami", "PROJECTED")),
}
DECLARED_CLOSURES: dict[date, str] = {
    date(2024, 1, 7): "general election day (Sunday, declared holiday)",
    date(2024, 7, 19): "the July uprising: curfew from the night of 19 July; banks closed "
                       "21-23 July (Sunday-Tuesday) -- an unscheduled closure",
    date(2024, 7, 21): "curfew closure (banks and DSE)",
    date(2024, 7, 22): "curfew closure (banks and DSE)",
    date(2024, 7, 23): "curfew closure (banks and DSE)",
    date(2024, 8, 5): "the government fell; banks closed 5-7 August",
    date(2024, 8, 6): "post-uprising closure", date(2024, 8, 7): "post-uprising closure",
}
WEEKEND: tuple[int, ...] = (4, 5)          # FRIDAY and SATURDAY


def national_holidays(year: int) -> dict[date, str]:
    out: dict[date, str] = {}
    for m, d, name in FIXED_NATIONAL.get(year, ()):
        out[date(year, m, d)] = name
    for day, name, status in LUNAR_AND_RELIGIOUS.get(year, ()):
        out[day] = f"{name} [{status}]"
    for day, name in DECLARED_CLOSURES.items():
        if day.year == year:
            out[day] = name
    return dict(sorted(out.items()))


def market_holidays(year: int) -> dict[date, str]:
    """DSE/bank closed days on what would otherwise be TRADING days (Sunday-Thursday)."""
    return {d: n for d, n in national_holidays(year).items() if d.weekday() not in WEEKEND}


def gazetted_dates(year: int) -> dict[date, str]:
    return {d: n for d, n, st in LUNAR_AND_RELIGIOUS.get(year, ()) if st == "GAZETTED"}


def week_end_days(year: int) -> list[date]:
    """Every Thursday of the year: the Bangladeshi week's last trading day."""
    d = date(year, 1, 1)
    d += timedelta(days=(3 - d.weekday()) % 7)
    out: list[date] = []
    while d.year == year:
        out.append(d)
        d += timedelta(days=7)
    return out


def is_market_holiday(day: date) -> bool:
    return day.weekday() in WEEKEND or day in market_holidays(day.year)


#: The years this pack's holiday tables resolve. Named once so the rule text, the derived
#: `table` below and `_holiday_rule_row()` cannot disagree about which years exist.
YEARS: tuple[int, ...] = (2024, 2025, 2026)
#: Which keys of HOLIDAYS_RULE are PROSE (the derivation a human reads) as opposed to data or
#: a function. The `rule` string the sibling checker wants is these, joined -- so a rule that
#: is edited in one place is edited in both views at once.
_PROSE_KEYS: tuple[str, ...] = (
    "authority", "weekend", "national_rule", "market_rule", "moon_sighting_rule",
    "cancellation_rule", "moving_feasts")

HOLIDAYS_RULE: dict[str, Any] = {
    "kind": "computed_from_rules",
    "authority": "the Cabinet Division gazettes the year's holidays each autumn and adds "
                 "executive-order extensions around Eid; the interim government's October "
                 "2024 order removed eight days and added the 5 August uprising day",
    "years": YEARS,
    "weekend": "FRIDAY and SATURDAY; the trading week is Sunday-Thursday",
    "national_rule": "Shaheed Day 21 Feb, Independence Day 26 Mar, Pahela Baishakh 14 Apr, May "
                     "Day, Victory Day 16 Dec, Christmas; from 2025 the 5 August uprising day; "
                     "Eid-ul-Fitr and Eid-ul-Azha blocks of 3+ days, Shab-e-Barat, Shab-e-Qadr, "
                     "Ashura, Eid-e-Miladunnabi, Buddha Purnima, Janmashtami, Durga Puja (two "
                     "days from 2024)",
    "market_rule": "the gazetted calendar on trading days; unscheduled closures are declared",
    "cancellation_rule": "DECLARED, not inferred: 15 August and 17 March are holidays in the "
                         "2024 table and absent from 2025 onward by the October 2024 order",
    "moving_feasts": "the Islamic dates drift eleven days a year; Puja and Buddha Purnima "
                     "follow the lunisolar calendar",
    "known_dates": {
        "2024-01-07": "general election day, a Sunday, declared a holiday",
        "2024-07-21": "curfew closure: banks and the DSE shut 21-23 July during the uprising",
        "2024-08-05": "the government fell; a three-day closure followed",
        "2024-08-15": "National Mourning Day, still observed in 2024 and cancelled from 2025",
        "2025-03-30": "the Eid-ul-Fitr block opened on a Sunday; with the extension and the "
                      "weekends the closure ran nine days to 3 April",
        "2025-06-05": "the Eid-ul-Azha block opened on Thursday 5 June and ran to 11 June with "
                      "the extension",
        "2026-03-20": "PROJECTED Eid-ul-Fitr; the gazetted date can differ by a day",
    },
    # THE SIBLING SCHEMA, DERIVED (2026-09-23). `research.countries.check_pack` reads a
    # `rule` string and a `table` of resolved years; this pack is computed from rules and
    # carried neither, so the parity checker could not read its calendar at all while every
    # other pack's was checked. Both are DERIVED from the functions above rather than typed,
    # so the two views cannot drift: the rule is this dict's own prose joined, and the table
    # is exactly what `market_holidays` returns for the declared years.
    "fn": market_holidays,
    "national_fn": national_holidays,
    "gazetted_fn": gazetted_dates,
    "week_end_fn": week_end_days,
}


# THE SIBLING SCHEMA, DERIVED (2026-09-23). `research.countries.check_pack` reads a `rule`
# string and a `table` of resolved years, and this pack is computed from rules and carried
# neither -- so the parity checker could not read its calendar at all while every other pack's
# was checked. Both are DERIVED here rather than typed, which is the whole point: the rule is
# this dict's own prose joined and the table is exactly what `market_holidays` returns, so the
# two views cannot drift from the functions above them.
HOLIDAYS_RULE["rule"] = " | ".join(
    str(HOLIDAYS_RULE[k]) for k in _PROSE_KEYS if HOLIDAYS_RULE.get(k))
HOLIDAYS_RULE["table"] = {
    y: {d.isoformat(): n for d, n in market_holidays(y).items()} for y in YEARS}
HOLIDAYS_RULE["status"] = (
    "COMPUTED: the table is regenerated from the rule functions on import, so a year added to "
    "YEARS appears in both views at once")

# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "Bangladesh Bank weekly gross reserves (BPM6 and gross), and the net reserves "
             "under the IMF definition",
     "root": "https://www.bb.org.bd/en/index.php/econdata/intreserve",
     "fields": ("gross_reserves_usd", "bpm6_reserves_usd", "net_reserves_imf"),
     "frequency": "weekly", "snapshot": "Wednesday", "publish_utc": "06:00", "lag_days": 1,
     "licence": "free, public", "available": True,
     "why": "three definitions of one number; the programme tests the third",
     "pit_warning": "a study must name which measure it read; the gap is about US$5bn"},
    {"name": "Bangladesh Bank monthly remittances by country and by bank",
     "root": "https://www.bb.org.bd/en/index.php/econdata/wageremitance",
     "fields": ("total_usd", "saudi", "uae", "usa", "uk", "malaysia", "by_bank"),
     "frequency": "monthly", "snapshot": "calendar month", "publish_utc": "06:00", "lag_days": 2,
     "licence": "free, public", "available": True,
     "why": "the channel the 2.5% incentive and the kerb premium steer; July 2024 is the boycott",
     "pit_warning": "two days stale; the by-bank split shows the state-bank share"},
    {"name": "DSE foreign investor turnover and the BSEC margin data",
     "root": "https://www.dsebd.org", "fields": ("foreign_turnover", "margin_loans"),
     "frequency": "monthly", "snapshot": "month", "publish_utc": "06:00", "lag_days": 10,
     "licence": "free, public", "available": True,
     "why": "the foreign share of DSE turnover is small and its sign is the risk read",
     "pit_warning": "monthly and stale; never a same-month conditioner"},
    {"name": "a traded taka positioning series", "root": "", "fields": (), "frequency": "n/a",
     "snapshot": "", "publish_utc": "", "lag_days": 0, "licence": "", "available": False,
     "why": "no taka future exists anywhere",
     "pit_warning": "DOES NOT EXIST; the NDF market is offshore and unreported"},
)

# --------------------------------------------------------------------------- terminology
#: Bengali is the language of nearly every source that matters -- Prothom Alo, Bonik Barta,
#: the Bangladesh Bank's Bengali circulars, the DSE retail groups -- and English carries The
#: Daily Star and the Financial Express. Both are carried; a query in English alone finds the
#: two English dailies and calls that the country.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "BD-A": ("বাংলাদেশ ব্যাংক", "রেপো রেট", "নীতি সুদহার", "মুদ্রানীতি", "স্মার্ট রেট",
             "Bangladesh Bank repo rate", "monetary policy statement", "SMART rate"),
    "BD-B": ("ক্রলিং পেগ", "ডলারের দাম", "বিনিময় হার", "খোলাবাজার", "কার্ব মার্কেট", "রিজার্ভ",
             "crawling peg", "dollar rate", "kerb market", "reserves BPM6", "exchange rate"),
    "BD-C": ("রেমিট্যান্স", "প্রবাসী আয়", "হুন্ডি", "প্রণোদনা", "রেমিট্যান্স বয়কট",
             "remittance", "hundi", "2.5% incentive", "remittance boycott", "expatriate income"),
    "BD-D": ("পোশাক রপ্তানি", "তৈরি পোশাক", "রপ্তানি আয়", "ইপিবি", "বিজিএমইএ", "অর্ডার",
             "RMG export", "EPB export data", "BGMEA", "apparel orders", "knitwear", "woven"),
    "BD-E": ("তুলা আমদানি", "সুতা", "স্পিনিং মিল", "বিটিএমএ", "এলসি খোলা",
             "cotton import", "yarn", "spinning mills", "BTMA", "LC opening"),
    "BD-F": ("জ্বালানি তেলের দাম", "বিপিসি", "অটোমেটিক প্রাইসিং", "ডিজেলের দাম", "অকটেন",
             "BPC fuel price", "automatic pricing formula", "diesel price", "octane price"),
    "BD-G": ("এলএনজি", "স্পট কার্গো", "পেট্রোবাংলা", "গ্যাস সংকট", "লোডশেডিং",
             "LNG spot cargo", "Petrobangla tender", "gas crisis", "load-shedding"),
    "BD-H": ("স্বর্ণের দাম", "বাজুস", "ভরি", "২২ ক্যারেট", "সোনা চোরাচালান",
             "BAJUS gold price", "bhori", "22 karat", "gold smuggling"),
    "BD-I": ("চালের দাম", "বোরো", "আমন", "গম আমদানি", "ভোজ্যতেল", "চিনির দাম", "সয়াবিন",
             "rice price", "Boro harvest", "Aman", "wheat import", "soybean oil", "sugar price"),
    "BD-J": ("শেয়ারবাজার", "ডিএসই", "ফ্লোর প্রাইস", "ডিএসইএক্স", "বিএসইসি", "মার্জিন ঋণ",
             "DSE", "floor price", "DSEX", "BSEC", "margin loan"),
    "BD-K": ("ঈদের ছুটি", "শুক্রবার", "সাপ্তাহিক ছুটি", "ছুটি বাতিল", "পূজার ছুটি",
             "Eid holidays", "weekend Friday Saturday", "holiday cancelled", "Puja holiday"),
    "BD-L": ("আইএমএফ ঋণ", "কিস্তি", "শর্ত", "রিভিউ মিশন", "নিট রিজার্ভ",
             "IMF loan", "tranche", "conditions", "review mission", "net reserves"),
    "BD-M": ("অন্তর্বর্তী সরকার", "৫ আগস্ট", "গভর্নর", "ব্যাংক খাত সংস্কার", "নির্বাচন",
             "interim government", "5 August", "new governor", "bank reform", "election"),
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
    if layer not in SOURCE_LAYERS:
        raise ValueError(f"absent layer {layer!r}")
    return {"id": f"absent_{layer}", "label": f"NO SOURCE IN THIS LAYER: {layer}", "layer": layer,
            "roots": (), "queries": (), "languages": (), "access_label": "ACCESS_UNCLEAR",
            "credibility": "UNKNOWN", "predictive_state": "UNTESTED",
            "machine_use_allowed": False, "licence": "n/a",
            "notes": f"DECLARED ABSENT, NOT BLANK: {reason}"}


SOURCE_CLASSES: tuple[dict[str, Any], ...] = (
    source_class(
        "bd_bb", "Bangladesh Bank: circulars, MPS, reserves, remittances, exchange rates",
        layer="official",
        roots=("https://www.bb.org.bd/en/index.php/monetaryactivity/mpd",
               "https://www.bb.org.bd/en/index.php/econdata/index",
               "https://www.bb.org.bd/en/index.php/mediaroom/circular"),
        queries=("মুদ্রানীতি ঘোষণা", "রেপো রেট", "রিজার্ভ", "প্রবাসী আয়", "সার্কুলার",
                 "monetary policy statement", "repo rate", "foreign exchange reserves",
                 "wage earners' remittance", "crawling peg"),
        languages=("bn", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="circulars carry the effective date; the crawling-peg and float announcements are "
              "dated circulars; the reserves page carries both the gross and BPM6 numbers"),
    source_class(
        "bd_epb_bgmea", "Export Promotion Bureau and BGMEA/BKMEA export data",
        layer="official",
        roots=("http://epb.gov.bd/site/view/epb_export_data",
               "https://www.bgmea.com.bd/page/Export_Performance"),
        queries=("রপ্তানি আয়", "পোশাক রপ্তানি", "মাসিক রপ্তানি", "export earnings", "RMG export "
                 "performance", "knitwear export", "woven export"),
        languages=("bn", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="REVISED in 2024: the EPB and the Bangladesh Bank reconciled a large "
              "overstatement of exports; every pre-2024 vintage must be kept as a vintage"),
    source_class(
        "bd_bbs_finance", "Bangladesh Bureau of Statistics, the Finance Division budget, the "
                          "BPC and Energy Division notifications", layer="official",
        roots=("https://bbs.gov.bd", "https://mof.gov.bd/site/page/budget",
               "https://bpc.gov.bd", "https://powerdivision.gov.bd"),
        queries=("মূল্যস্ফীতি", "সিপিআই", "বাজেট বক্তৃতা", "জ্বালানি তেলের মূল্য সমন্বয়",
                 "inflation", "budget speech", "fuel price adjustment", "automatic pricing"),
        languages=("bn", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the BPC notification is dated and effective on the 1st; the CPI base changed"),
    source_class(
        "bd_dse_bsec", "Dhaka Stock Exchange and the BSEC: notices, the floor-price orders, "
                       "foreign turnover", layer="official",
        roots=("https://www.dsebd.org", "https://sec.gov.bd"),
        queries=("ফ্লোর প্রাইস প্রত্যাহার", "বিএসইসি নির্দেশনা", "ডিএসইএক্স", "floor price "
                 "withdrawal", "BSEC directive", "DSEX", "market summary"),
        languages=("bn", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the floor-price orders (2022-07-28 on, 2024-01-18 phased off) are rule states"),
    source_class(
        "bd_imf_wb", "IMF Bangladesh programme documents and World Bank Bangladesh updates",
        layer="official",
        roots=("https://www.imf.org/en/Countries/BGD",
               "https://www.worldbank.org/en/country/bangladesh/publication/bangladesh-development-update"),
        queries=("Bangladesh ECF EFF RSF review", "net international reserves", "exchange rate "
                 "unification", "Bangladesh Development Update"),
        languages=("en",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the review calendar is BD-L's clock; the staff reports date each prior action"),
    source_class(
        "bd_trade_bodies", "BTMA (textile mills), BAJUS (jewellers), BAB, the Foreign Exchange "
                           "Dealers' Association and the remittance houses", layer="institutional",
        roots=("https://www.btmadhaka.com", "https://www.bajus.org", "https://www.bab-bd.com"),
        queries=("বিটিএমএ", "বাজুস স্বর্ণের দাম", "ব্যাংকার্স অ্যাসোসিয়েশন", "রেমিট্যান্স হাউস",
                 "BTMA cotton", "BAJUS price", "bankers' association", "exchange house rate"),
        languages=("bn", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="BAJUS announces every gold price change; BTMA states the cotton import need"),
    source_class(
        "bd_brokers_banks", "Broker and bank research published openly: LankaBangla, IDLC, "
                            "BRAC EPL, City Bank Capital, Standard Chartered Bangladesh notes",
        layer="institutional",
        roots=("https://www.lankabangla.com/research", "https://idlc.com/monthly-business-review",
               "https://bracepl.com/research"),
        queries=("Bangladesh macro update", "taka outlook", "MPS review", "reserves adequacy",
                 "DSE strategy"),
        languages=("en",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free notes; some behind registration",
        notes="the stated expectations the surprise is measured against; never a view"),
    source_class(
        "bd_academic", "BIDS, the Policy Research Institute, CPD, SANEM, the BB research "
                       "department and university working papers", layer="academic",
        roots=("https://bids.org.bd/publications", "https://cpd.org.bd/publications/",
               "https://sanemnet.org", "https://www.bb.org.bd/en/index.php/publication/publictn/0/2"),
        queries=("remittance hundi Bangladesh", "exchange rate pass-through taka", "RMG order "
                 "book", "cotton import demand", "CPD budget analysis", "SANEM inflation"),
        languages=("en", "bn"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="open access / publisher terms",
        notes="CPD's and SANEM's dated briefings are the best public timing of policy fights"),
    source_class(
        "bd_english_press", "The Daily Star business, the Financial Express, The Business "
                            "Standard, Dhaka Tribune", layer="practitioner",
        roots=("https://www.thedailystar.net/business", "https://thefinancialexpress.com.bd",
               "https://www.tbsnews.net/economy", "https://www.dhakatribune.com/business"),
        queries=("dollar crisis", "LC opening restrictions", "reserves fall", "remittance "
                 "incentive", "cotton import", "LNG cargo tender", "floor price", "BAJUS"),
        languages=("en",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="The Business Standard's daily kerb-rate and exchange-house rate reporting is a "
              "usable PIT record of the three-rate regime"),
    source_class(
        "bd_bengali_press", "Prothom Alo, Bonik Barta, Samakal, Kaler Kantho business pages",
        layer="practitioner",
        roots=("https://www.prothomalo.com/business", "https://bonikbarta.com",
               "https://samakal.com/economics", "https://www.kalerkantho.com/online/business"),
        queries=("ডলার সংকট", "খোলাবাজারে ডলার", "রেমিট্যান্সে প্রণোদনা", "সোনার দাম বাড়ল",
                 "তেলের দাম কমল", "এলসি খুলতে পারছে না", "ফ্লোর প্রাইস", "ঈদের ছুটি"),
        languages=("bn",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="Bonik Barta is the business daily the mills and the banks read; the Bengali "
              "press dates the LC-rationing episodes better than the English press"),
    source_class(
        "bd_retail_groups", "DSE retail investor groups on Facebook, YouTube stock channels, "
                            "the r/bangladesh finance threads", layer="retail_ecology",
        roots=("https://www.facebook.com/groups/dsebd", "https://www.youtube.com/results?"
               "search_query=%E0%A6%B6%E0%A7%87%E0%A6%AF%E0%A6%BC%E0%A6%BE%E0%A6%B0%E0%A6%AC%E0%A6%BE%E0%A6%9C%E0%A6%BE%E0%A6%B0",
               "https://www.reddit.com/r/bangladesh/"),
        queries=("শেয়ারবাজার টিপস", "কোন শেয়ার কিনব", "ফ্লোর প্রাইস উঠে গেছে", "মার্জিন কল",
                 "DSE tips", "which share to buy", "floor price lifted"),
        languages=("bn", "en"), access_label="PUBLIC_SOCIAL", credibility="FRINGE",
        predictive_state="UNTESTED", licence="platform terms; public posts only",
        notes="KEPT AT LOW WEIGHT: single names are the event lane's; the retail dollar and "
              "gold panic vocabulary dates the stress episodes"),
    source_class(
        "bd_offshore_retail", "Bengali-language forex and gold-signal sellers and prop-firm "
                              "promoters (Telegram, YouTube)", layer="retail_ecology",
        roots=("https://www.youtube.com/results?search_query=forex+trading+bangla",
               "https://t.me/s/forexbangladesh"),
        queries=("ফরেক্স ট্রেডিং বাংলা", "গোল্ড সিগন্যাল", "প্রপ ফার্ম", "forex bangla",
                 "gold signal bangla", "prop firm bangladesh"),
        languages=("bn", "en"), access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="platform terms; public posts only",
        notes="illegal for residents under BB rules yet large; the XAUUSD stop-cluster "
              "vocabulary is a microstructure observable, never a source of edge"),
    source_class(
        "bd_apps", "bKash, Nagad, Rocket, the Bangladesh Bank's remittance apps, TapTap Send "
                   "and the exchange-house apps, and the DSE mobile app", layer="app_ecosystem",
        roots=("https://www.bkash.com", "https://nagad.com.bd", "https://www.dsebd.org/mobile.php"),
        queries=("বিকাশে রেমিট্যান্স", "নগদ", "রকেট", "মোবাইল ব্যাংকিং", "remittance via bKash",
                 "MFS statistics", "exchange house app rate"),
        languages=("bn", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="BB MFS statistics free; app stores public",
        notes="the BB publishes monthly mobile-financial-service statistics; the exchange-house "
              "app rates are the diaspora's real exchange rate"),
    source_class(
        "bd_p2p_commentary", "Press coverage of the USDT-taka peer-to-peer premium as a kerb "
                             "proxy", layer="app_ecosystem",
        roots=("https://www.tbsnews.net/search?q=usdt",),
        queries=("ইউএসডিটি", "ক্রিপ্টো নিষিদ্ধ", "USDT taka premium"),
        languages=("bn", "en"), access_label="PUBLIC_WITH_TERMS", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="publisher terms",
        notes="PUBLIC COMMENTARY ONLY: no venue feed, no order book (mandate 2026-08-18); a "
              "taka stress observable at low weight beside the kerb rate"),
    source_class(
        "bd_broadcast", "Somoy TV, Jamuna TV, Channel 24 business bulletins and the BSS wire",
        layer="media",
        roots=("https://www.somoynews.tv/economy", "https://www.jamuna.tv/economy",
               "https://www.bssnews.net/business"),
        queries=("ডলারের দাম আজ", "সোনার দাম আজ", "তেলের নতুন দাম", "বাংলাদেশ ব্যাংকের ঘোষণা",
                 "dollar rate today", "gold price today", "Bangladesh Bank announces"),
        languages=("bn", "en"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="the broadcast minute is the best public stamp of a circular or a BAJUS change"),
    source_class(
        "bd_licensed", "Bloomberg, Refinitiv and the licensed Bangladesh data vendors",
        layer="media", roots=("https://www.bloomberg.com/",),
        queries=("BDT NDF", "Bangladesh taka forward"),
        languages=("en",), access_label="LICENSED", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="subscription; terms forbid machine extraction",
        machine_use_allowed=False,
        notes="REGISTERED, NEVER SCRAPED: the offshore NDF is only visible on terminals"),
    source_class(
        "bd_archive", "Bangladesh Economic Review (annual, pre-budget), BB annual reports, BBS "
                      "yearbooks, the Household Income and Expenditure Survey", layer="archive",
        roots=("https://mof.gov.bd/site/page/28ba57f5-59ff-4426-970a-bf014242179e/Bangladesh-Economic-Review",
               "https://www.bb.org.bd/en/index.php/publication/publictn/0/1"),
        queries=("বাংলাদেশ অর্থনৈতিক সমীক্ষা", "বার্ষিক প্রতিবেদন", "Bangladesh Economic Review",
                 "BB annual report", "HIES"),
        languages=("bn", "en"), access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the Economic Review lands with the budget in June: one dated release a year"),
    source_class(
        "bd_physical", "Chattogram port throughput, Petrobangla gas production and LNG "
                       "regasification, BPDB load-shedding, the Department of Agricultural "
                       "Extension crop estimates, the Meteorological Department's cyclone "
                       "bulletins", layer="physical_economy",
        roots=("https://cpa.gov.bd", "https://petrobangla.org.bd", "https://www.bpdb.gov.bd",
               "https://dae.gov.bd", "https://live.bmd.gov.bd"),
        queries=("চট্টগ্রাম বন্দর কনটেইনার", "গ্যাস উৎপাদন", "লোডশেডিং", "বোরো উৎপাদন", "ঘূর্ণিঝড়",
                 "port throughput", "gas production", "load-shedding schedule", "Boro output",
                 "cyclone warning"),
        languages=("bn", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the port count is the import bill in boxes; the cyclone season (April-May and "
              "October-November) is the physical clock of the delta"),
    source_class(
        "bd_usda_fao", "USDA FAS GAIN and FAO GIEWS for Bangladesh cotton, grain, oilseeds and "
                       "sugar", layer="physical_economy",
        roots=("https://fas.usda.gov/data/search?f%5B0%5D=country%3A%22Bangladesh%22",
               "https://www.fao.org/giews/countrybrief/country.jsp?code=BGD"),
        queries=("Bangladesh cotton and products annual", "Bangladesh grain and feed annual",
                 "Bangladesh oilseeds", "GIEWS Bangladesh"),
        languages=("en",), access_label="OPEN_DATA", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="public domain (US government work)",
        notes="USDA's cotton import line for Bangladesh is the number ICE reads"),
    source_class(
        "bd_source_graph", "Who cites whom: the BB circular -> Bonik Barta/TBS -> retail chain, "
                           "and the IMF -> Finance Division -> BPC/BB circular chain",
        layer="source_graph",
        roots=("https://www.bb.org.bd/en/index.php/mediaroom/circular",
               "https://www.tbsnews.net/economy"),
        queries=("বাংলাদেশ ব্যাংকের সূত্র", "সূত্র জানায়", "according to Bangladesh Bank",
                 "IMF conditions require", "BAJUS said"),
        languages=("bn", "en"), access_label="PUBLIC", credibility="UNKNOWN",
        predictive_state="UNTESTED", licence="derived from the public sources above",
        notes="'সূত্র জানায়' (sources say) marks the leak before a circular; the graph tells a "
              "leak from a repost"),
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
    {"name": "Bangladesh Bank repo rate changes and Monetary Policy Statements",
     "source": "Bangladesh Bank", "coverage": "2003 onward", "frequency": "semi-annual + circulars",
     "publication_lag_days": 0.0, "revisions": "never", "licence": "free, public",
     "history_from": "2003-01", "pit_feasible": True, "assets": ("USDINR", "XAUUSD"),
     "mechanism_families": ("policy_surprise", "event_reaction"),
     "how_to_fetch": "bb.org.bd MPD page and the circular archive; each circular is dated"},
    {"name": "Official, interbank and exchange-house dollar rates (the three-rate regime)",
     "source": "Bangladesh Bank / TBS daily tables", "coverage": "2015 onward",
     "frequency": "daily", "publication_lag_days": 0.0, "revisions": "never",
     "licence": "free, public", "history_from": "2015-01", "pit_feasible": True,
     "assets": ("USDINR", "XAUUSD"), "mechanism_families": ("stress_indicator", "flow_diversion"),
     "how_to_fetch": "bb.org.bd exchange rate page for the official; TBS/Bonik Barta archives "
                     "for the kerb and exchange-house rates; the premium is derived"},
    {"name": "Wage earners' remittances by country and by bank", "source": "Bangladesh Bank",
     "coverage": "1976 onward (by country from 1995)", "frequency": "monthly",
     "publication_lag_days": 2.0, "revisions": "minor", "licence": "free, public",
     "history_from": "1995-07", "pit_feasible": True, "assets": ("XAUUSD", "GBPUSD", "USDINR"),
     "mechanism_families": ("seasonal_flow", "natural_experiment"),
     "how_to_fetch": "bb.org.bd/econdata/wageremitance; July 2024 is the boycott month"},
    {"name": "EPB monthly export earnings by product (RMG knit/woven, jute, leather)",
     "source": "Export Promotion Bureau", "coverage": "2000 onward", "frequency": "monthly",
     "publication_lag_days": 4.0, "revisions": "the 2024 reconciliation restated 2022-24",
     "licence": "free, public", "history_from": "2000-07", "pit_feasible": True,
     "assets": ("COTTON", "EURUSD", "GBPUSD"), "mechanism_families": ("export_demand",),
     "how_to_fetch": "epb.gov.bd export data; keep the pre- and post-2024 vintages apart"},
    {"name": "USDA Bangladesh cotton import forecast and BTMA import statements",
     "source": "USDA FAS / BTMA", "coverage": "2005 onward", "frequency": "monthly (USDA)",
     "publication_lag_days": 0.0, "revisions": "monthly WASDE revisions", "licence": "public "
                                                                                     "domain",
     "history_from": "2005-01", "pit_feasible": True, "assets": ("COTTON",),
     "mechanism_families": ("import_demand",),
     "how_to_fetch": "USDA PSD online for the Bangladesh cotton balance; GAIN reports"},
    {"name": "BPC fuel price notifications (formula from March 2024)",
     "source": "Bangladesh Petroleum Corporation", "coverage": "2016 onward",
     "frequency": "monthly",
     "publication_lag_days": 0.0, "revisions": "never", "licence": "free, public",
     "history_from": "2016-04", "pit_feasible": True, "assets": ("XBRUSD", "XTIUSD"),
     "mechanism_families": ("administered_price", "pass_through"),
     "how_to_fetch": "bpc.gov.bd notices; effective on the 1st"},
    {"name": "BAJUS gold price announcements (22k per bhori)", "source": "BAJUS",
     "coverage": "2015 onward", "frequency": "irregular, several per month",
     "publication_lag_days": 0.0, "revisions": "never", "licence": "free, public",
     "history_from": "2015-01", "pit_feasible": True, "assets": ("XAUUSD",),
     "mechanism_families": ("administered_price", "premium_signal"),
     "how_to_fetch": "bajus.org press releases; the effective date is the next day"},
    {"name": "Petrobangla / RPGCL LNG spot tenders and awards", "source": "RPGCL",
     "coverage": "2018 onward (spot from 2020)", "frequency": "monthly",
     "publication_lag_days": 1.0,
     "revisions": "never", "licence": "free, public", "history_from": "2020-09",
     "pit_feasible": False, "assets": ("XNGUSD", "XBRUSD"),
     "mechanism_families": ("spot_demand", "tender_event"),
     "how_to_fetch": "rpgcl.org.bd tender notices and press reports of awards; PIT IS PARTIAL: "
                     "award minutes are not always published and those cargoes are UNMEASURED"},
    {"name": "DSE daily market summary, floor-price orders and foreign turnover",
     "source": "DSE / BSEC", "coverage": "2013 onward", "frequency": "daily",
     "publication_lag_days": 0.0, "revisions": "never", "licence": "free, public",
     "history_from": "2013-01", "pit_feasible": True, "assets": ("US500", "USDINR"),
     "mechanism_families": ("rule_state", "foreign_flow"),
     "how_to_fetch": "dsebd.org; the floor-price orders are dated BSEC directives"},
    {"name": "BBS CPI (2021-22 base) and food-price bulletins", "source": "BBS / TCB",
     "coverage": "2005 onward", "frequency": "monthly", "publication_lag_days": 3.0,
     "revisions": "rebasing only", "licence": "free, public", "history_from": "2005-07",
     "pit_feasible": True, "assets": ("WHEAT", "SUGAR", "SOYBEAN"),
     "mechanism_families": ("release_surprise",),
     "how_to_fetch": "bbs.gov.bd CPI release; the TCB daily commodity prices are the lead"},
    {"name": "IMF ECF/EFF/RSF programme documents and disbursement dates", "source": "IMF",
     "coverage": "2023 onward (ECF 2012 before)", "frequency": "per review",
     "publication_lag_days": 7.0, "revisions": "never", "licence": "free, public",
     "history_from": "2012-04", "pit_feasible": True, "assets": ("USDINR", "XAUUSD"),
     "mechanism_families": ("programme_clock",),
     "how_to_fetch": "imf.org/en/Countries/BGD press releases and staff reports"},
    {"name": "Chattogram port monthly container and cargo throughput",
     "source": "Chittagong Port Authority", "coverage": "2010 onward", "frequency": "monthly",
     "publication_lag_days": 15.0, "revisions": "never", "licence": "free, public",
     "history_from": "2010-01", "pit_feasible": True, "assets": ("COTTON", "XBRUSD"),
     "mechanism_families": ("physical_count",),
     "how_to_fetch": "cpa.gov.bd statistics; a counted physical flow"},
)

# --------------------------------------------------------------------------- actors
ACTORS: tuple[dict[str, Any], ...] = (
    {"name": "Bangladesh Bank (the Governor and the monetary policy committee)",
     "holds": "the repo rate and corridor, the declared exchange-rate regime, about US$20-26bn "
              "of gross reserves and the surrender rules for exporters and banks",
     "forced_to": ("publish a Monetary Policy Statement twice a year and change the repo rate "
                   "by circular between them",
                   "meet the IMF's net-reserve floor at each test date",
                   "sell dollars to the state banks for fuel, fertiliser and food LCs when "
                   "the market will not"),
     "when": "statements in January and June/July; circulars any banking day, effective at "
             "once; reserves weekly",
     "information": ("the banks' LC pipeline", "the remittance flow by bank in real time",
                     "the IMF mission's numbers"),
     "constraints": ("the IMF programme's reserve and rate conditions",
                     "a banking system with 10-30% non-performing loans in the state banks",
                     "the 2024 regime change and the new Governor's clean-up mandate"),
     "instruments": ("USDINR", "XAUUSD", "COTTON"),
     "counterparties": ("the state-owned banks it sells dollars to", "the IMF",
                        "the exchange houses"),
     "observables": ("the circular and its effective date", "the weekly reserves in both "
                     "definitions", "the official-kerb gap"),
     "impact": "a regime announcement (2024-05-08 crawl, 2025-05-14 float) moves the official "
               "rate by 5-10% in a day; the executable effect is on the trade the taka drives",
     "persistence": "the regime persists for a year or more; a repo change persists to the next",
     "falsifier": "the same window on the eight nearest non-announcement banking days; a move "
                  "on the regional cross or on cotton that matches a non-announcement Sunday is "
                  "the weekday, not the bank",
     "notes": "the two statements a year make the scheduled-decision sample tiny; the "
              "circulars are the real sample"},
    {"name": "The garment exporters (BGMEA/BKMEA members) and their buyers",
     "holds": "about 85% of goods exports; a US$40-45bn order book placed by EU, US and UK "
              "retailers on 60-120 day terms",
     "forced_to": ("ship to the buyers' seasonal calendars (spring/summer orders placed in the "
                   "autumn)", "repatriate proceeds within the BB's deadline and encash at the "
                   "regulated rate", "import cotton, yarn and fabric on LCs to fill the orders"),
     "when": "the EPB print in the first week of the month; buyer order cycles in September-"
             "November and February-April",
     "information": ("the order book before the EPB print", "the buyers' inventory positions"),
     "constraints": ("US and EU retail demand", "the minimum wage rounds (2023) and the "
                     "strikes", "gas and power availability", "the LC regime"),
     "instruments": ("COTTON", "EURUSD", "GBPUSD", "US500"),
     "counterparties": ("the EU/US/UK retailers", "the spinning mills", "the banks"),
     "observables": ("EPB monthly exports", "US apparel imports from Bangladesh (OTEXA)",
                     "BGMEA's order commentary", "the strike and gas-shortage reports"),
     "impact": "the export print sets the next quarter's cotton import need and the taka's "
               "dollar supply; US and EU retail sales lead it by a quarter",
     "persistence": "one order season",
     "falsifier": "the EPB print carries no information for COTTON or for the next quarter's "
                  "USDA import line once US retail sales are controlled",
     "notes": "the two-lane order: no listed garment maker appears as an instrument"},
    {"name": "The spinning mills (BTMA members) as the world's largest cotton importer",
     "holds": "about 1.5-2 mt a year of cotton imports (West Africa, Brazil, the US, India)",
     "forced_to": ("import on LCs the banks must fund in dollars", "buy against the buyers' "
                   "order calendar", "switch origins on price and the LC constraint"),
     "when": "purchases cluster ahead of the two order seasons; USDA's PSD updates monthly",
     "information": ("their own order pipeline", "the origin basis"),
     "constraints": ("the LC regime", "gas for the mills", "the yarn price in India"),
     "instruments": ("COTTON", "USDINR"),
     "counterparties": ("the cotton merchants", "the banks", "the Indian yarn exporters"),
     "observables": ("USDA's Bangladesh import line", "Chattogram port cotton arrivals",
                     "BTMA's public statements on the LC constraint"),
     "impact": "a 10% swing in Bangladesh's import is ~0.2 mt, a visible share of world trade; "
               "the 2022-23 LC rationing cut imports and ICE read it",
     "persistence": "a season to a year",
     "falsifier": "USDA's Bangladesh import revisions carry no information for COTTON against "
                  "the randomised-release null",
     "notes": "the strongest outward edge in the pack"},
    {"name": "Overseas Bangladeshis (the Gulf, Malaysia, the US, the UK) as remittance senders",
     "holds": "about US$22-27bn a year; the choice between the banks and hundi",
     "forced_to": ("send ahead of the two Eids", "choose the channel on the rate gap and the "
                   "2.5% incentive", "in July 2024, WITHHOLD as a political act -- the "
                   "remittance boycott, a natural experiment"),
     "when": "the Eid months; the BB prints on the 1st-3rd",
     "information": ("the exchange-house app rates", "the hundi rate", "the political news"),
     "constraints": ("the Gulf labour cycle", "the Malaysian labour agreements",
                     "the incentive rate the BB sets"),
     "instruments": ("XAUUSD", "GBPUSD", "USDINR"),
     "counterparties": ("the banks and exchange houses", "the hundi operators", "the gold "
                        "retailers the cash reaches"),
     "observables": ("the monthly print by country", "the exchange-house rate vs official",
                     "the July 2024 print (down ~25% year on year)"),
     "impact": "the Eid month is 15-25% above trend; the July 2024 boycott month is the "
               "cleanest identification of the channel's elasticity anywhere in South Asia",
     "persistence": "seasonal, and one political episode",
     "falsifier": "the boycott month's shortfall is explained by the rate gap alone, or the "
                  "Eid-month gold demand shows no premium against matched non-Eid months",
     "notes": "the boycott is the pack's natural experiment; BD-C carries it"},
    {"name": "The Bangladesh Petroleum Corporation as the monthly fuel price setter",
     "holds": "the import monopoly for refined fuel and the formula the Energy Division adopted "
              "in March 2024",
     "forced_to": ("notify the formula price by the end of the month, effective the 1st",
                   "pass the previous month's Platts and the taka through", "borrow dollars "
                   "from the state banks and the BB when arrears build"),
     "when": "the last days of the month, effective 00:00 Dhaka on the 1st",
     "information": ("the Platts averages", "the taka path", "the arrears position"),
     "constraints": ("the subsidy budget", "the IMF's demand for formula pricing",
                     "political tolerance for a hike"),
     "instruments": ("XBRUSD", "XTIUSD"),
     "counterparties": ("the state banks funding the LCs", "the refiners and traders",
                        "the Energy Division"),
     "observables": ("the notification", "the formula's inputs", "the arrears reports"),
     "impact": "sets the transport and power components of CPI; an INPUT-direction mechanism "
               "measured honestly on the crude legs",
     "persistence": "one month by construction",
     "falsifier": "the notification window on XBRUSD matches the matched weekday control and "
                  "the 15th placebo; that is the expected result and is recorded as such",
     "notes": "the honest expectation is no outward effect"},
    {"name": "Petrobangla and RPGCL as spot LNG buyers",
     "holds": "the two regasification terminals (Moheshkhali) and the spot tender programme "
              "under the master agreements",
     "forced_to": ("tender for spot cargoes when domestic gas (Bibiyana in decline) falls short",
                   "stop when the dollars are not there (mid-2022)", "ration gas to industry"),
     "when": "tenders monthly, more in summer for power; awards are reported within days",
     "information": ("the gas balance", "the BB's dollar release"),
     "constraints": ("JKM affordability", "the terminal capacity", "the dollar position"),
     "instruments": ("XNGUSD", "XBRUSD"),
     "counterparties": ("the trading houses", "Qatar and Oman under long-term SPAs",
                        "the state banks"),
     "observables": ("the tender notice and award", "the load-shedding schedule"),
     "impact": "a South Asian spot buyer's tender is JKM demand; the Henry Hub leg is a weak "
               "proxy and the edge is carried as such",
     "persistence": "seasonal",
     "falsifier": "no move on XNGUSD beyond the matched control (the expected result, recorded)",
     "notes": "an honest weak edge"},
    {"name": "BAJUS (the jewellers' association) and the gold smuggling channel",
     "holds": "the administered retail gold price and the retail book; supply arrives "
              "largely through baggage from Dubai",
     "forced_to": ("re-price whenever LBMA x the kerb moves enough", "clear Eid and wedding "
                   "demand", "source outside the official import channel"),
     "when": "announcements late afternoon Dhaka, effective the next day; demand peaks into "
             "Eid and the November-February wedding season",
     "information": ("the kerb rate", "the Dubai premium"),
     "constraints": ("the BB's import rules (the 2018 gold policy)", "customs seizures"),
     "instruments": ("XAUUSD",),
     "counterparties": ("Dubai bullion dealers", "retail buyers", "the exchange houses"),
     "observables": ("the BAJUS price vs LBMA x kerb", "seizure reports at Dhaka airport"),
     "impact": "the BAJUS premium is a clean stress-state measure; the executable leg is global "
               "gold, on which Bangladesh's retail demand is small",
     "persistence": "seasonal plus stress episodes",
     "falsifier": "the BAJUS premium carries no information about the next kerb gap or the "
                  "remittance print, and Eid windows on XAUUSD match the matched control",
     "notes": "the premium is the observable; the price is administered"},
    {"name": "The IMF mission and Board (the ECF/EFF/RSF programme)",
     "holds": "the undisbursed tranches and the review calendar; the reserve-floor test",
     "forced_to": ("review semi-annually against dated performance criteria",
                   "re-negotiate after the 2024 regime change", "disburse only on Board approval"),
     "when": "staff-level agreement, Board approval and disbursement are three dated events",
     "information": ("the fiscal and reserve data ahead of the market"),
     "constraints": ("the programme's conditionality", "the exchange-rate unification demand"),
     "instruments": ("USDINR", "XAUUSD"),
     "counterparties": ("the Finance Division", "the BB", "the World Bank and ADB co-financiers"),
     "observables": ("the press release", "the reserves step"),
     "impact": "a review sets the timing of the rate-regime moves; the disbursement is a step "
               "in the Wednesday reserves",
     "persistence": "one review cycle",
     "falsifier": "IMF Board dates for other programme countries show the same move on the "
                  "regional cross -- a dollar or risk event, not a Bangladesh event",
     "notes": "the exchange-rate unification of 2024-25 was a programme condition"},
    {"name": "The Dhaka Stock Exchange, the BSEC and the floor-price regime",
     "holds": "the rule book: the FLOOR PRICE (2022-07-28 to 2024-01-18), circuit breakers, "
              "the margin rules",
     "forced_to": ("freeze prices at the floor when the regulator orders it", "lift it in "
                   "phases when the order is withdrawn", "halt on a curfew day"),
     "when": "orders are dated BSEC directives; the lifting ran 2024-01-18 to 2024-02",
     "information": ("the regulator's own intent"),
     "constraints": ("political tolerance for a fall", "the margin-loan overhang"),
     "instruments": ("US500", "USDINR"),
     "counterparties": ("the brokers and margin lenders", "the foreign investors who exited"),
     "observables": ("the directive", "the share of listed names frozen at the floor",
                     "foreign turnover"),
     "impact": "every DSEX statistic inside the floor window is an artefact; a study that pools "
               "it with free-trading months measures the rule, not the market",
     "persistence": "eighteen months of frozen prices",
     "falsifier": "the DSEX's beta to US500 is the same inside and outside the floor window "
                  "(it cannot be, which is the point of carrying the rule state)",
     "notes": "the index has no CFD; the rule state conditions the flow domain"},
    {"name": "The rice farmers, millers and the Ministry of Food (Boro and Aman)",
     "holds": "the two rice harvests (Boro in April-May is about 55% of output; Aman in "
              "November-December), the procurement price and the import decisions",
     "forced_to": ("set procurement prices before each harvest", "import wheat (6-7 mt, the "
                   "largest food import) and rice when the harvest or the Indian ban forces it",
                   "release open-market sales when the retail price spikes"),
     "when": "procurement price March and October; wheat imports year-round by G2G and tender",
     "information": ("the DAE crop estimate", "the stock position"),
     "constraints": ("India's export bans (rice 2023-24, wheat 2022)", "the fiscal cost",
                     "the LC regime"),
     "instruments": ("WHEAT", "SOYBEAN", "SUGAR", "USDINR"),
     "counterparties": ("Russian, Ukrainian and Australian wheat exporters", "Indian rice "
                        "exporters when open", "the flour mills"),
     "observables": ("the procurement price", "the tender awards", "TCB retail prices",
                     "USDA's Bangladesh grain balance"),
     "impact": "Bangladesh's 6-7 mt wheat import is about 3% of world trade; a G2G deal with "
               "Russia is dated Black Sea demand",
     "persistence": "one marketing year",
     "falsifier": "the tender and G2G windows on WHEAT match the matched weekday control and "
                  "the GASC reference importer's windows explain them entirely",
     "notes": "soybean and sugar imports follow the same channel and are carried as edges"},
    {"name": "The Chattogram port and the Matarbari coal terminal",
     "holds": "about 90% of the country's sea trade; 3.2m TEU; the deep-sea port under "
              "construction",
     "forced_to": ("publish monthly throughput", "close for cyclones and for the 2024 curfew"),
     "when": "monthly statistics; cyclone closures in April-May and October-November",
     "information": ("the vessel queue", "the customs backlog"),
     "constraints": ("draft limits", "the cyclone season", "the customs strike calendar"),
     "instruments": ("COTTON", "XBRUSD", "WHEAT"),
     "counterparties": ("the importers", "the shipping lines"),
     "observables": ("monthly TEU and cargo tonnes", "the cyclone bulletins"),
     "impact": "the counted import bill; a closure delays the cotton and fuel inflow",
     "persistence": "monthly",
     "falsifier": "port throughput carries no lead for the next EPB print or the USDA import "
                  "line beyond the seasonal cycle",
     "notes": "the physical-economy layer's counted flow"},
    {"name": "The interim government (from 2024-08-08) and the election calendar",
     "holds": "executive power until the next election (announced for February 2026), the "
              "holiday decree, the bank-reform agenda and the IMF re-negotiation",
     "forced_to": ("hold the election on the announced timetable", "keep the programme alive",
                   "re-write the holiday calendar and the bank-resolution law"),
     "when": "dated decrees; the election date once gazetted",
     "information": ("its own reform agenda"),
     "constraints": ("the political settlement", "the programme", "the street"),
     "instruments": ("USDINR", "XAUUSD", "US500"),
     "counterparties": ("the parties", "the IMF and the World Bank", "the BB"),
     "observables": ("the decrees", "the election date announcement", "the curfew closures"),
     "impact": "the 5 August 2024 break is a regime change with a date; every domain's era "
               "split uses it",
     "persistence": "one government",
     "falsifier": "the regime-change window on the regional cross and gold matches the "
                  "matched control -- possible, since the taka is absent; the pack records it",
     "notes": "the era boundary, not a tradeable"},
)

# --------------------------------------------------------------------------- domains
DOMAINS: tuple[dict[str, Any], ...] = (
    {"id": "BD-A", "title": "Bangladesh Bank decisions: two statements, many circulars",
     "objects": ("the semi-annual MPS", "the repo circulars with immediate effect",
                 "the corridor and the SMART formula era (2023-24)"),
     "conditions": ("statement vs circular", "the era (SMART, crawl, float)",
                    "whether an IMF review was pending"),
     "instruments": ("USDINR", "XAUUSD"),
     "controls": ("the eight nearest non-announcement banking days",
                  "RBI decision days on the same instruments, separating 'South Asia' from "
                  "'Bangladesh'", "a randomised-date null"),
     "notes": "the scheduled sample is two a year; the circular sample is the real one"},
    {"id": "BD-B", "title": "The three-rate regime: official, kerb, exchange-house",
     "objects": ("the official rate and its declared regime", "the kerb rate", "the exchange-"
                 "house rate", "the 2024-05-08 crawl and the 2025-05-14 float"),
     "conditions": ("the gap bucket", "the regime", "the remittance-incentive rate"),
     "instruments": ("USDINR", "COTTON", "XAUUSD"),
     "controls": ("Pakistan's kerb premium in the same months (the sibling channel)",
                  "the gap lagged one month against the remittance print vs a shuffled-lag null",
                  "the BAJUS premium as the alternative stress measure"),
     "notes": "the gap is a lead indicator, tested on what follows it"},
    {"id": "BD-C", "title": "Remittances, the incentive, the boycott and Eid",
     "objects": ("the monthly print by country", "the 2.5% incentive changes", "July 2024",
                 "the Eid months"),
     "conditions": ("the gap state", "the lunar month", "the political state"),
     "instruments": ("XAUUSD", "GBPUSD", "USDINR"),
     "controls": ("Pakistan's remittance print in the same months (no boycott)",
                  "the Indian Diwali windows on gold, separating 'festival' from 'Eid'",
                  "matched non-Eid months"),
     "notes": "July 2024 identifies the channel's elasticity; nothing else in the region does"},
    {"id": "BD-D", "title": "The RMG export print and the buyers' demand cycle",
     "objects": ("EPB monthly exports (knit and woven)", "OTEXA US apparel imports from "
                 "Bangladesh", "US and EU retail sales", "the minimum-wage and strike episodes"),
     "conditions": ("the retail-sales surprise in the destination", "the strike state",
                    "the gas-shortage state"),
     "instruments": ("COTTON", "EURUSD", "GBPUSD", "US500"),
     "controls": ("Vietnam's apparel export print (the competitor)", "the EPB release day vs "
                  "the same weekday in non-release weeks", "a randomised-date null"),
     "notes": "the export print is the import need's leading number"},
    {"id": "BD-E", "title": "The cotton import: the world's largest buyer's swing",
     "objects": ("USDA's Bangladesh import line and its revisions", "BTMA statements",
                 "Chattogram cotton arrivals", "the LC-rationing episodes"),
     "conditions": ("the LC regime", "the yarn price in India", "the order season"),
     "instruments": ("COTTON", "USDINR"),
     "controls": ("Pakistan's PCGA arrivals in the same fortnights (the sibling importer)",
                  "USDA revision days for Vietnam and Turkey (the other importers)",
                  "the matched weekday control on COTTON"),
     "notes": "the pack's strongest outward edge"},
    {"id": "BD-F", "title": "The BPC monthly fuel formula as an administered pass-through",
     "objects": ("the notification", "the formula's Platts and taka inputs",
                 "the pre-2024 discretionary changes"),
     "conditions": ("formula era or not", "the sign and size of the change"),
     "instruments": ("XBRUSD", "XTIUSD"),
     "controls": ("the 15th as a placebo day", "the matched weekday control",
                  "Pakistan's 1st/16th notifications on the same instruments"),
     "notes": "an INPUT-direction mechanism; the expected outward effect is none"},
    {"id": "BD-G", "title": "LNG spot tenders and the gas shortfall",
     "objects": ("RPGCL tenders and awards", "the 2022 halt", "load-shedding"),
     "conditions": ("awarded vs no-bid", "the season", "the dollar release"),
     "instruments": ("XNGUSD", "XBRUSD"),
     "controls": ("Pakistan's PLL tender windows (the sibling buyer)", "non-tender weeks",
                  "the matched weekday control"),
     "notes": "JKM is absent; every reading is a weak-proxy reading"},
    {"id": "BD-H", "title": "The BAJUS gold price and the smuggling premium",
     "objects": ("the announcement series", "the premium to LBMA x kerb", "seizures",
                 "the Eid and wedding calendar"),
     "conditions": ("the import regime", "the kerb gap", "the season"),
     "instruments": ("XAUUSD",),
     "controls": ("the Indian retail premium", "the Pakistani tola premium",
                  "matched non-festival windows on gold"),
     "notes": "the premium is the observable; the executable leg is global gold"},
    {"id": "BD-I", "title": "Rice, wheat, soybean and sugar: the food import bill",
     "objects": ("the Boro and Aman harvests", "the wheat tenders and G2G deals",
                 "India's export bans", "TCB retail prices", "the soybean-oil price fixes"),
     "conditions": ("the Indian ban state", "the harvest estimate", "the LC regime"),
     "instruments": ("WHEAT", "SOYBEAN", "SUGAR", "USDINR"),
     "controls": ("GASC/Egypt tender windows on WHEAT", "Pakistan's TCP tenders",
                  "the matched weekday control"),
     "notes": "Bangladesh's wheat import is ~3% of world trade; a real demand line"},
    {"id": "BD-J", "title": "The DSE floor-price regime and the foreign flow",
     "objects": ("the floor-price orders and their lifting", "foreign turnover",
                 "the margin-loan overhang", "the curfew closures"),
     "conditions": ("inside vs outside the floor window", "the regime era"),
     "instruments": ("US500", "USDINR"),
     "controls": ("Pakistan's FIPI on the same dates", "Vietnam's foreign flow",
                  "the DSEX-US500 beta inside vs outside the floor window as the artefact test"),
     "notes": "the index has no CFD; the rule state and the flow are the objects"},
    {"id": "BD-K", "title": "The Friday-Saturday weekend, the Eid blocks and the cancelled days",
     "objects": ("the Thursday close", "the gazetted Eid blocks and their extensions",
                 "the October 2024 cancellations", "the curfew closures"),
     "conditions": ("gazetted vs projected", "block length", "extension or not"),
     "instruments": ("XAUUSD", "USDINR"),
     "controls": ("Pakistan's and India's closures on the same days",
                  "the projected-but-not-holiday dates as the placebo",
                  "the matched weekday control"),
     "notes": "the weekend itself is the pack's first calendar fact"},
    {"id": "BD-L", "title": "The IMF programme clock and the reserve definitions",
     "objects": ("review dates", "the BPM6 vs gross vs net reserve series",
                 "the disbursement steps", "the 2024 re-negotiation"),
     "conditions": ("on-time vs delayed review", "which reserve measure",
                    "the political state"),
     "instruments": ("USDINR", "XAUUSD"),
     "controls": ("Pakistan's and Sri Lanka's IMF Board dates on the same instruments",
                  "Wednesdays with no tranche", "a randomised-date null"),
     "notes": "three definitions of one number; a study must name which it read"},
    {"id": "BD-M", "title": "The 2024 regime change as an era boundary",
     "objects": ("2024-08-05", "the new Governor", "the holiday decree", "the election date"),
     "conditions": ("before vs after", "the curfew days"),
     "instruments": ("USDINR", "XAUUSD", "US500"),
     "controls": ("Sri Lanka's 2022 regime change as the sibling break",
                  "the matched control on the same instruments", "non-event days"),
     "notes": "the era split every other domain uses"},
)

# --------------------------------------------------------------------------- the pack's miners
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    {"name": "bd_bb_circular_windows", "domain_ids": ("BD-A", "BD-B"), "kind": "event",
     "cadence_s": 86400.0, "steerable": False, "wired": False,
     "entry": "countries.bd.miners:bb_circular_windows",
     "needs": ("CENTRAL_BANK decision dates", "USDINR, XAUUSD, COTTON H1 bars"),
     "notes": "statements and circulars pooled with the era split; the regime announcements are "
              "flagged"},
    {"name": "bd_thursday_week_end", "domain_ids": ("BD-K",), "kind": "microstructure",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.bd.miners:thursday_week_end",
     "needs": ("XAUUSD, USDINR H1 bars",),
     "notes": "the Bangladeshi week ends on Thursday; the Friday placebo is built in"},
    {"name": "bd_export_print_and_cotton", "domain_ids": ("BD-D", "BD-E"), "kind": "macro",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.bd.miners:export_print_and_cotton",
     "needs": ("EPB:exports and USDA import series if on the box", "COTTON D1/H1 bars"),
     "notes": "the EPB release days as an event study; the series lead-lag where the series is "
              "on the box"},
    {"name": "bd_gazetted_holiday_eves", "domain_ids": ("BD-K", "BD-C"), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.bd.miners:gazetted_holiday_eves",
     "needs": ("the gazetted holiday rows", "XAUUSD, USDINR H1 bars"),
     "notes": "gazetted dates only; projected rows form the placebo"},
    {"name": "bd_transmission_seeds", "domain_ids": ("BD-F", "BD-G", "BD-H", "BD-I", "BD-J",
                                                     "BD-L", "BD-M"), "kind": "transfer",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.bd.miners:transmission_seeds",
     "needs": ("TRANSMISSION_EDGES_SEED",),
     "notes": "the pack's map as HYPOTHESIS discoveries"},
)
MINER_DOMAINS: dict[str, tuple[str, ...]] = {
    "central_bank_surprise": ("BD-A",), "release_surprise": ("BD-D", "BD-F"),
    "calendar_settlement": ("BD-F", "BD-K"), "holiday_liquidity": ("BD-K",),
    "positioning": ("BD-J",), "carry_funding": ("BD-B",), "corporate_flow": ("BD-D", "BD-E"),
    "institutional_flow": ("BD-C", "BD-L"), "equity_mechanics": ("BD-J",),
    "derivatives_expiry": ("BD-J",), "failure": ("BD-F", "BD-G"), "residual": ("BD-B", "BD-H"),
    "transfer": ("BD-E", "BD-I"), "scouts": ("BD-B", "BD-M"),
}

# --------------------------------------------------------------------------- transmission
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    {"id": "BD-E1", "source": "USDA's Bangladesh cotton import line and its revisions",
     "target": "COTTON", "targets": ("COTTON",), "to_country": "global", "sign": "+",
     "mechanism": "the world's largest cotton importer's demand step, read by ICE through the "
                  "merchants' export sales", "horizon": "1 to 8 weeks", "horizon_class":
     "multi_day", "lag_days": 7.0, "actor": "BTMA spinning mills",
     "constraint": "the mills must fill the buyers' orders", "flow": "import demand",
     "condition": "an open LC regime; a revision above 0.1 mt",
     "control": "revision days for Vietnam and Turkey; Pakistan's PCGA arrivals",
     "falsifier": "a revision that ICE does not read against the randomised-release null",
     "evidence": "HYPOTHESIS"},
    {"id": "BD-E2", "source": "The EPB monthly export print (RMG)", "target": "COTTON",
     "targets": ("COTTON", "EURUSD"), "to_country": "global", "sign": "+",
     "mechanism": "the export figure sets the next quarter's cotton and yarn import need",
     "horizon": "1 to 3 months", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "BGMEA/BKMEA exporters", "constraint": "the buyers' order calendar",
     "flow": "export orders", "condition": "conditioned on US and EU retail sales",
     "control": "Vietnam's apparel export print", "falsifier": "no information beyond the "
                                                                 "destination retail sales",
     "evidence": "HYPOTHESIS"},
    {"id": "BD-E3", "source": "Wheat G2G deals and tenders (Russia, Ukraine, Australia)",
     "target": "WHEAT", "targets": ("WHEAT",), "to_country": "global", "sign": "+",
     "mechanism": "a 6-7 mt importer's dated purchase is Black Sea demand the CBOT export "
                  "basis reads", "horizon": "0 to 5 sessions", "horizon_class": "multi_day",
     "lag_days": 1.0, "actor": "the Ministry of Food", "constraint": "the food-security stock",
     "flow": "state import", "condition": "an open LC regime",
     "control": "GASC tender windows; Pakistan's TCP tenders",
     "falsifier": "the deal window matches the matched control", "evidence": "HYPOTHESIS"},
    {"id": "BD-E4", "source": "Soybean and soybean-oil imports for feed and cooking oil",
     "target": "SOYBEAN", "targets": ("SOYBEAN",), "to_country": "global", "sign": "+",
     "mechanism": "about 2.5 mt of soybean plus meal and oil imports; the poultry and edible-"
                  "oil demand is a dated tender flow", "horizon": "1 to 3 months",
     "horizon_class": "multi_day", "lag_days": 30.0, "actor": "the crushers and refiners",
     "constraint": "the LC regime and the administered oil price", "flow": "import demand",
     "condition": "the administered edible-oil price change dates",
     "control": "Pakistan's soybean line", "falsifier": "USDA's Bangladesh oilseed import "
                                                         "line does not move",
     "evidence": "HYPOTHESIS"},
    {"id": "BD-E5", "source": "Raw sugar imports (about 2 mt) and the refiners' tenders",
     "target": "SUGAR", "targets": ("SUGAR", "SUGARRAW"), "to_country": "global", "sign": "+",
     "mechanism": "a 2 mt raw importer's dated purchases are Brazilian and Indian demand",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 2.0,
     "actor": "the private refiners (City, Meghna, S. Alam) and the BSFIC",
     "constraint": "the duty and LC regime", "flow": "import demand",
     "condition": "Ramadan pre-stocking", "control": "India's export policy dates",
     "falsifier": "the tender windows match the matched control", "evidence": "HYPOTHESIS"},
    {"id": "BD-E6", "source": "The Eid remittance peak and the BAJUS demand season",
     "target": "XAUUSD", "targets": ("XAUUSD",), "to_country": "global", "sign": "+",
     "mechanism": "part of the Eid-month remittance excess reaches the gold retailers; the "
                  "regional festive window is a demand season", "horizon": "the two weeks into "
                  "Eid", "horizon_class": "multi_day", "lag_days": 0.0,
     "actor": "overseas Bangladeshis and BAJUS", "constraint": "the lunar calendar",
     "flow": "retail demand", "condition": "a narrow kerb gap",
     "control": "the same lunar windows in wide-gap years; Diwali windows",
     "falsifier": "the Eid window on gold matches matched non-Eid months",
     "evidence": "HYPOTHESIS"},
    {"id": "BD-E7", "source": "RPGCL spot LNG tender awards", "target": "XNGUSD",
     "targets": ("XNGUSD", "XBRUSD"), "to_country": "global", "sign": "+",
     "mechanism": "a South Asian spot buyer's tender is JKM demand; Henry Hub is a weak proxy",
     "horizon": "0 to 5 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "Petrobangla / RPGCL", "constraint": "the dollar release", "flow": "spot demand",
     "condition": "an awarded tender", "control": "Pakistan's PLL tender windows",
     "falsifier": "no move beyond the matched control (expected)", "evidence": "HYPOTHESIS"},
    {"id": "BD-E8", "source": "The exchange-rate regime announcements (crawl 2024-05-08, float "
                              "2025-05-14)", "target": "USDINR", "targets": ("USDINR",),
     "to_country": "in", "sign": "+",
     "mechanism": "a South Asian devaluation is read by the rupee's offshore market as regional "
                  "stress; small and recorded as such", "horizon": "0 to 2 sessions",
     "horizon_class": "intraday", "lag_days": 0.0, "actor": "Bangladesh Bank",
     "constraint": "the IMF's unification demand", "flow": "regional stress",
     "condition": "announcement dates only", "control": "non-announcement Sundays",
     "falsifier": "no measurable move (the expected result)", "evidence": "HYPOTHESIS"},
    {"id": "BD-E9", "source": "The July 2024 remittance boycott and the regime change",
     "target": "XAUUSD", "targets": ("XAUUSD", "USDINR"), "to_country": "global", "sign": "+",
     "mechanism": "a withheld remittance month is a natural experiment on the channel; the "
                  "diaspora's withheld dollars reached gold and the hundi market instead",
     "horizon": "1 to 2 months", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "overseas Bangladeshis", "constraint": "the political act", "flow": "channel "
                                                                              "diversion",
     "condition": "July-August 2024 only", "control": "Pakistan's July 2024 print",
     "falsifier": "the shortfall is explained by the rate gap alone", "evidence": "HYPOTHESIS"},
)

# --------------------------------------------------------------------------- policy eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    {"name": "the pre-crisis fixed rate", "start": "2018-01-01", "end": "2022-06-30",
     "regime": "the taka held near 84-86 per dollar with a 6% lending-rate cap (April 2020)",
     "markers": ("2020-04-01 the 9% lending cap", "2022-03 the dollar squeeze begins"),
     "why_it_matters": "the official rate carried no information; the kerb did",
     "status": "SETTLED"},
    {"name": "the dollar crisis and the floor price", "start": "2022-07-01", "end": "2024-05-07",
     "regime": "LC rationing, the DSE floor price (2022-07-28 to 2024-01-18), the three-rate "
               "regime, the IMF programme (2023-01-30), the SMART lending formula",
     "markers": ("2022-07-28 the floor price", "2023-01-30 the IMF programme",
                 "2024-01-07 the election", "2024-01-18 the floor lifted"),
     "why_it_matters": "the stress channel and the rule states every domain conditions on",
     "status": "SETTLED"},
    {"name": "the crawling peg", "start": "2024-05-08", "end": "2024-08-04",
     "regime": "the declared crawl at 117 with a band; the repo at 8.50%",
     "markers": ("2024-05-08 the crawl announced", "2024-07-19 the curfew"),
     "why_it_matters": "the framework the pack's central-bank row names; three months long",
     "status": "SETTLED"},
    {"name": "the interim government and the float", "start": "2024-08-05", "end": "2026-12-31",
     "regime": "the regime change, the new Governor, repo to 10%, the holiday decree, the "
               "exchange-rate unification and the managed float (2025-05-14), the election "
               "calendar",
     "markers": ("2024-08-05 the government fell", "2024-08-14 the new Governor",
                 "2024-10-22 repo 10%", "2025-05-14 the float"),
     "why_it_matters": "the current regime; the boycott month and the unification live here",
     "status": "OPEN"},
)

ACCESS_CONSTRAINTS: tuple[dict[str, Any], ...] = (
    {"constraint": "the taka is not quoted by this broker",
     "measured": "data/universe/universe.json holds no BDT symbol",
     "consequence": "every domestic mechanism terminates in a soft, an energy leg, gold or a "
                    "neighbour's cross; the taka is an INPUT"},
    {"constraint": "the DSEX has no CFD and the floor-price window is an artefact",
     "measured": "no Bangladeshi index is in the universe; the BSEC orders are dated",
     "consequence": "the foreign flow and the rule state are the objects; the index is a target"},
    {"constraint": "the week is Sunday-Thursday",
     "measured": "the DSE and the banks close Friday and Saturday",
     "consequence": "every weekday bucket is shifted; the Thursday close is the week-end window"},
    {"constraint": "the EPB export series was restated in 2024",
     "measured": "the EPB and the BB reconciled a multi-billion overstatement",
     "consequence": "pre-2024 vintages are kept as vintages and never mixed with the restated "
                    "series"},
    {"constraint": "the offshore NDF and the terminal feeds are licensed",
     "measured": "their terms forbid machine extraction; registered machine_use_allowed=false",
     "consequence": "the NDF is UNMEASURED; the BB posting and the press tables are the record"},
)
INSTITUTIONAL_FLOW_SOURCES: tuple[str, ...] = (
    "Bangladesh Bank remittances by bank", "DSE foreign turnover", "BB MFS statistics",
    "the IMF disbursement schedule", "the exchange-house rate postings")
SERIES: dict[str, str] = {
    "BD_POLICY": "BB:repo_rate", "BD_RESERVES": "BB:reserves_bpm6", "BD_REMIT": "BB:remittances",
    "BD_EXPORTS": "EPB:exports", "BD_COTTON_IMPORT": "USDA:bd_cotton_imports",
    "BD_FUEL": "BPC:fuel", "BD_GOLD": "BAJUS:gold_22k", "BD_CPI": "BBS:cpi",
}

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
        "source_layers": SOURCE_LAYERS, "layer_absences": LAYER_ABSENCES,
        "layer_terms": layer_terms(), "source_layer_coverage": source_layer_coverage(),
        "datasets": DATASETS, "actors": ACTORS, "domains": DOMAINS,
        "custom_miners": CUSTOM_MINERS, "miner_domains": MINER_DOMAINS,
        "transmission_edges_seed": TRANSMISSION_EDGES_SEED, "policy_eras": POLICY_ERAS,
        "transmission_targets": TRANSMISSION_TARGETS, "access_constraints": ACCESS_CONSTRAINTS,
        "region_desk": REGION_DESK, "forest": FOREST, "cot_currency": COT_CURRENCY,
        "export_economy": EXPORT_ECONOMY, "retail_leverage_regime": RETAIL_LEVERAGE_REGIME,
        "institutional_flow_sources": INSTITUTIONAL_FLOW_SOURCES, "series": SERIES,
        "mission": MISSION,
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
    dates = sorted({d.isoformat() for y in HOLIDAYS_RULE["years"] for d in market_holidays(y)})
    fixed = sorted({f"{m:02d}-{d:02d}" for rows in FIXED_NATIONAL.values() for m, d, _ in rows})
    return {"dates": tuple(dates), "fixed_md": tuple(fixed), "weekly_closed": WEEKEND,
            "notes": HOLIDAYS_RULE["authority"] + "; the weekend is Friday-Saturday"}


def lab_kwargs() -> dict[str, Any]:
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
