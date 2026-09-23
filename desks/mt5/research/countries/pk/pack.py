"""PAKISTAN: an IMF-programme economy whose forced flows are administered on a calendar.

WHAT PAKISTAN IS AS A MARKET MECHANISM, AND WHY IT IS NOT A SMALLER INDIA. Five things belong
to this economy and to no other in the desk's book, and each is why a domain below exists rather
than a row in a generic emerging-market domain:

  1. THE PROGRAMME IS THE CLOCK. Since 2019 Pakistan has lived inside successive IMF
     arrangements (the 2019 EFF, the 2023 Stand-By, the 37-month EFF approved 2024-09-25), and
     the programme's reviews, prior actions and tranche disbursements are DATED events that move
     the State Bank's reserves in one jump. Reserves are published every Thursday; the tranche
     lands as a step in that series. Almost everything else in the country -- the petrol price,
     the electricity tariff, the budget, the rate decision -- is negotiated against that clock.

  2. THE PETROL PRICE IS SET BY NOTIFICATION EVERY FORTNIGHT. On the 1st and the 16th of each
     month the Finance Division notifies petrol and diesel prices (OGRA recommends), passing Brent
     and the rupee through with a two-week lag and a discretionary levy. The pass-through is a
     scheduled administered event, not a market price, and it is the single largest input to the
     monthly CPI the Monetary Policy Committee reads.

  3. THERE ARE TWO EXCHANGE RATES AND THE GAP IS A STATE VARIABLE. The interbank rate is the
     bank market; the open-market (kerb) rate is posted by the exchange companies (ECAP). When
     the gap widens -- it reached Rs 20-30 in 2022-23 -- remittances leave the banking channel
     for hundi/hawala and the SBP's reserves fall while the country's dollars do not. The
     September 2023 crackdown on the exchange companies closed the gap and remittances jumped.
     The premium is therefore a LEAD indicator of both SBP action and the remittance print.

  4. HOLIDAYS ARE ANNOUNCED THE EVENING BEFORE. Eid, Ashura and Eid Milad follow the Central
     Ruet-e-Hilal Committee's moon sighting; the exact closed day is not known until the sighting
     is announced (or refused) the previous evening, and the government sometimes extends the
     holiday by a day the same week. A holiday-liquidity study that uses a projected calendar is
     measuring the wrong days in a third of the sample; the pack carries the ANNOUNCED dates and
     labels the future ones PROJECTED.

  5. THE COUNTRY IS A PRICE-TAKER IN EVERYTHING EXCEPT ITS OWN TRADE DECISIONS. The rupee is
     not quoted by this broker and the KSE-100 has no CFD, so the executable map runs OUTWARD
     through what Pakistan buys and sells in size: it is one of the largest cotton importers in
     the world in a bad crop year, a 2-3 mt wheat importer when the harvest fails, a 2 mt soybean
     importer for the poultry industry, a sugar exporter in surplus years, and a spot-LNG buyer
     whose tenders go unfilled when it cannot pay. Those decisions are dated, public, and reach
     COTTON, WHEAT, SOYBEAN, SUGAR and the gas leg; everything else in the pack is an INPUT
     direction (Brent, the dollar, gold) and is recorded as such.

WHAT IS EXECUTABLE AND WHAT IS NOT. USDPKR, the KSE-100, KIBOR, the T-bill auction, the PMEX
gold and cotton futures, Pakistan's Eurobonds and CDS, the ECAP kerb rate and JKM are all absent
from `data/universe/universe.json`. Every one is named in `TRANSMISSION_TARGETS` with the broker
symbols its mechanism reaches, so an absent instrument produces a transmission hypothesis and
never a cell that can never be filled (L1.49).

THE TWO-LANE ORDER. Pakistani market commentary is company-heavy -- Engro, Lucky, HBL, PSO --
and every one of those is an EVENT-lane instrument. They enter this pack only as ACTORS (an oil
marketing company that pays for cargoes, a textile mill that imports cotton), and the
instruments those actors move are softs, energy, metals and the regional crosses. No share CFD
appears in any instrument tuple in this file.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, timedelta
from typing import Any

# --------------------------------------------------------------------------- identity
CODE = "PK"
NAME = "Pakistan"
REGION_COMMAND = "asia"            # the framework's command; the forest is south_asia
REGION_DESK = "SOUTH_ASIA"
FOREST = "south_asia"
CURRENCY = "PKR"
FISCAL_YEAR_END = "06-30"          # 1 July to 30 June; the budget is presented in early June
NATIVE_LANGUAGES: tuple[str, ...] = ("ur", "en-PK", "pa", "sd", "ps")
COT_CURRENCY = ""                  # no CFTC contract exists for the rupee
EXPORT_ECONOMY = "manufacturing_exporter"      # textiles are ~60% of goods exports; rice second
RETAIL_LEVERAGE_REGIME = "restricted"          # SECP: no retail forex/CFD margin; PSX margin only
MISSION = ("mine Pakistan as the programme-clocked, administered-price, two-exchange-rate "
           "economy it is: the IMF review calendar, the fortnightly petrol notification, the "
           "kerb premium, the moon-sighting holidays, and the trade decisions -- cotton, wheat, "
           "soybean, sugar, LNG -- that reach the broker's softs and energy")

#: The instruments this pack may compile a cell against. Every one is in the broker registry
#: and none is a single-name equity. The rupee itself is absent (see TRANSMISSION_TARGETS).
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "COTTON", "WHEAT", "SUGAR", "SOYBEAN",            # what Pakistan buys and sells in size
    "XTIUSD", "XBRUSD", "XNGUSD",                     # the import bill and the LNG tenders
    "XAUUSD",                                          # the tola price, Eid demand, smuggling
    "USDINR", "USDCNH",                                # the regional and the CPEC crosses
    "USDX", "EURUSD", "GBPUSD",                        # the dollar, the GSP+ and diaspora legs
    "US500",                                           # global risk, the FIPI flow's other side
)

TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "USD/PKR interbank rate (SBP weighted average)", "venue": "interbank / SBP",
     "why": "the currency every mechanism here is about, absent from the broker; its moves are "
            "read through what Pakistan then buys and sells abroad",
     "proxies": ("USDINR", "USDX", "COTTON", "WHEAT")},
    {"name": "ECAP open-market (kerb) dollar rate", "venue": "exchange companies",
     "why": "the second exchange rate; the premium over interbank is the hundi-diversion state "
            "variable PK-C conditions on",
     "proxies": ("USDINR", "XAUUSD")},
    {"name": "KSE-100 index", "venue": "Pakistan Stock Exchange",
     "why": "no CFD is quoted; the foreign portfolio flow (NCCPL FIPI) is read instead",
     "proxies": ("US500", "USDINR")},
    {"name": "KIBOR and the SBP T-bill / PIB auctions", "venue": "SBP / primary dealers",
     "why": "the domestic rate path and the consensus before an MPC decision",
     "proxies": ("USDINR", "XAUUSD")},
    {"name": "Pakistan Eurobonds and the 5-year CDS", "venue": "OTC",
     "why": "the sovereign-stress channel of 2022-23 (CDS above 100 points upfront); the "
            "maturity calendar is a forced-flow clock",
     "proxies": ("USDINR", "XAUUSD", "US500")},
    {"name": "PMEX gold and cotton futures", "venue": "Pakistan Mercantile Exchange",
     "why": "the domestic hedging venue; thin, and priced off the same international legs",
     "proxies": ("XAUUSD", "COTTON")},
    {"name": "Karachi Cotton Association spot rate (per maund)",
     "venue": "Karachi Cotton Association",
     "why": "the domestic cotton price; its spread to ICE cotton is the import-demand signal",
     "proxies": ("COTTON",)},
    {"name": "Platts JKM LNG (the PLL/PSO tender benchmark)", "venue": "Platts",
     "why": "spot cargoes are priced off JKM; XNGUSD is Henry Hub and only a weak proxy, which "
            "is stated on every gas edge",
     "proxies": ("XNGUSD", "XBRUSD")},
    {"name": "TCP wheat and sugar import/export tenders",
     "venue": "Trading Corporation of Pakistan / ECC",
     "why": "the state's trade decisions in grain and sugar, dated and public",
     "proxies": ("WHEAT", "SUGAR")},
    {"name": "Pakistan basmati and IRRI rice export prices", "venue": "REAP",
     "why": "the second export; no rice symbol is quoted here, so India's export bans are read "
            "through wheat and the regional cross instead",
     "proxies": ("WHEAT", "USDINR")},
)

# --------------------------------------------------------------------------- the central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "State Bank of Pakistan -- Monetary Policy Committee",
    "short": "SBP",
    "framework": "inflation_targeter",
    "committee": "the MPC under the SBP Act as amended in January 2022: the Governor, three "
                 "Deputy Governors or Board members, and three external members",
    "policy_instrument": "the policy rate (target for the overnight money-market repo rate), "
                         "inside an interest-rate corridor of +/-100bp",
    "mandate": "domestic price stability as the primary objective under the 2022 amendment; a "
               "medium-term inflation target of 5-7% announced by the government",
    "decision_rule": "eight scheduled MPC meetings a year on a half-yearly published schedule; "
                     "the decision and the statement are released the same afternoon and the "
                     "minutes follow; an emergency meeting is its own event class "
                     "(2022-04-07, +250bp, and 2023-06-26, +100bp, were unscheduled)",
    "decision_calendar_rule": "eight meetings a year, published half-yearly at sbp.org.pk; the "
                              "announcement minute varies (mid-afternoon Karachi) and must be "
                              "stamped from the press release, never assumed",
    "decision_dates": (
        "2024-01-29", "2024-03-18", "2024-04-29", "2024-06-10", "2024-07-29", "2024-09-12",
        "2024-11-04", "2024-12-16",
        "2025-01-27", "2025-03-10", "2025-05-05", "2025-06-16", "2025-07-30", "2025-09-15",
        "2025-10-27", "2025-12-15"),
    "dates_status": "2024: the eight decisions as announced (22% held through April, then "
                    "150/100/200/250/200bp cuts to 13%); 2025: the published half-yearly "
                    "schedules, re-verify each date against the SBP press release before a "
                    "cell is compiled on it; 2026: NOT LISTED -- the schedule is published in "
                    "halves and the pack refuses to invent it",
    "decision_time_utc": "11:00",
    "announce_local": "afternoon Asia/Karachi (PKT, UTC+5, no DST); the minute varies",
    "dst_rule": "Pakistan keeps UTC+5 all year; the UTC minute of a Karachi event never moves",
    "minutes_lag_days": 14,
    "publication_classes": ("monetary_policy_statement", "mpc_minutes", "weekly_reserves",
                            "monthly_remittances", "annual_report", "governor_press_conference"),
    "policy_rate_series": "SBP:policy_rate",
    "expected_rate_series": "UNMEASURED",
    "consensus_proxy": "the 3-month KIBOR and the T-bill cut-off yields between meetings; the "
                       "press surveys (Topline, Arif Habib) are the stated expectation",
    "consensus_proxy_trap": "KIBOR embeds the corridor and the liquidity injections (OMOs run "
                            "at Rs 10-13trn); a KIBOR move is not a decision expectation alone",
    "reserves_clock": "SBP-held reserves are published every THURSDAY for the week ending the "
                      "previous Friday; an IMF tranche appears as a single step in that series",
    "programme": "IMF 37-month EFF approved 2024-09-25 (US$7bn); the first review completed "
                 "2025-05-09 with a Resilience and Sustainability Facility added; reviews are "
                 "semi-annual and each carries prior actions the budget, the tariff and the "
                 "rate decision are negotiated against",
    "off_cycle": ("2022-04-07 emergency +250bp", "2023-06-26 emergency +100bp to 22%"),
    "root": "https://www.sbp.org.pk",
}

# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "SBP weighted-average customer exchange rate (interbank close)",
     "local": "published after the interbank close, about 17:00 Asia/Karachi",
     "time_utc": "12:00", "time_utc_dst": "12:00", "dst_rule": "none (UTC+5 all year)",
     "instruments": ("USDINR", "USDX"), "window_minutes": 30,
     "why": "the official rupee reference the SBP, the customs and the petrol formula read"},
    {"name": "ECAP open-market rate posting",
     "local": "posted by the exchange companies each morning, about 10:00 Asia/Karachi",
     "time_utc": "05:00", "time_utc_dst": "05:00", "dst_rule": "none",
     "instruments": ("XAUUSD", "USDINR"), "window_minutes": 60,
     "why": "the kerb rate; its gap to the interbank close is the state variable of PK-C"},
    {"name": "Fortnightly petroleum price notification",
     "local": "effective 00:00 Asia/Karachi on the 1st and the 16th; notified the evening before",
     "time_utc": "19:00", "time_utc_dst": "19:00", "dst_rule": "none",
     "instruments": ("XBRUSD", "XTIUSD"), "window_minutes": 60,
     "why": "the administered pass-through of Brent and the rupee; PK-D's event"},
    {"name": "Karachi Sarafa tola gold rate",
     "local": "set daily by the All Pakistan Gems and Jewellers Association, late morning",
     "time_utc": "06:30", "time_utc_dst": "06:30", "dst_rule": "none",
     "instruments": ("XAUUSD",), "window_minutes": 60,
     "why": "the domestic gold price; its premium to LBMA x interbank is the smuggling signal"},
    {"name": "LBMA gold price PM auction (the dollar leg of the tola price)",
     "local": "15:00 Europe/London", "time_utc": "15:00", "time_utc_dst": "14:00",
     "dst_rule": "GMT/BST", "instruments": ("XAUUSD",), "window_minutes": 15,
     "why": "the reference the tola price is derived from"},
    {"name": "Karachi Cotton Association spot rate", "local": "about 14:00 Asia/Karachi daily",
     "time_utc": "09:00", "time_utc_dst": "09:00", "dst_rule": "none",
     "instruments": ("COTTON",), "window_minutes": 60,
     "why": "the domestic cotton price per maund; the KCA-ICE spread is PK-F's signal"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "Petroleum price fortnight", "kind": "day_of_month", "days": (1, 16),
     "roll": "none", "window_utc": ("18:00", "20:00"),
     "instruments": ("XBRUSD", "XTIUSD"),
     "why": "the notified price takes effect at midnight on the 1st and the 16th"},
    {"name": "SBP weekly reserves release", "kind": "weekday", "weekday": 3, "roll": "none",
     "window_utc": ("11:00", "13:00"), "instruments": ("USDINR", "XAUUSD"),
     "why": "every Thursday; the IMF tranche and the bilateral rollovers show up here"},
    {"name": "Month-end oil and LNG letter-of-credit settlements", "kind": "month_end",
     "roll": "previous", "window_utc": ("04:00", "12:00"),
     "instruments": ("XBRUSD", "XNGUSD", "USDINR"),
     "why": "the importers' dollar demand clusters into the last three business days; the "
            "SBP's 2022-23 LC restrictions were a forced-flow regime of their own"},
    {"name": "Fiscal year end (30 June)", "kind": "fiscal_year_end", "roll": "previous",
     "window_utc": ("04:00", "12:00"), "instruments": ("USDINR", "XAUUSD"),
     "why": "the SBP reserves target and the bilateral deposit rollovers are dated to it; "
            "1 July is a bank holiday for the half-year closing"},
    {"name": "Quarter-end IMF performance-criteria test dates", "kind": "quarter_end",
     "roll": "previous", "window_utc": ("04:00", "12:00"), "instruments": ("USDINR",),
     "why": "net international reserves and the primary balance are tested at quarter ends"},
)

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Pakistan Stock Exchange (PSX) -- KSE-100",
     "index_symbols": (),
     "open_local": "09:30 (pre-open 09:15)", "close_local": "15:30 (Friday 12:00-14:30 break)",
     "open_utc": "04:30", "close_utc": "10:30", "dst_rule": "none (UTC+5)",
     "auction": "pre-open call 09:15-09:30; closing price is the last 30-minute VWAP",
     "expiry_rule": "deliverable and cash-settled futures expire on the last Friday of the "
                    "contract month",
     "holidays": "federal holidays plus SBP bank holidays; Friday prayers break; Ramadan hours "
                 "shift earlier",
     "notes": "NO CFD IS QUOTED on the KSE-100, so the index enters only as a transmission "
              "target; the NCCPL publishes foreign and local portfolio investment DAILY, which "
              "is the positioning series PK-K reads"},
    {"name": "Pakistan Mercantile Exchange (PMEX)", "index_symbols": (),
     "open_local": "24h Monday-Friday with breaks", "close_local": "n/a",
     "open_utc": "00:00", "close_utc": "23:59", "dst_rule": "none",
     "auction": "n/a", "expiry_rule": "monthly gold, crude and cotton contracts",
     "holidays": "federal holidays", "notes": "thin; priced off the international legs"},
)

SESSION_WINDOWS: tuple[dict[str, Any], ...] = (
    {"name": "pk_kerb_posting", "start_utc": "05:00", "end_utc": "06:00",
     "notes": "the exchange companies post the open-market rate"},
    {"name": "pk_sbp_afternoon", "start_utc": "09:00", "end_utc": "12:00",
     "notes": "MPC announcements, the weekly reserves release and the interbank close"},
    {"name": "pk_petrol_notification", "start_utc": "18:00", "end_utc": "20:00",
     "notes": "the fortnightly price notification lands the evening before it takes effect"},
)

RELEASE_CLASSES: tuple[dict[str, Any], ...] = (
    {"name": "SBP weekly foreign exchange reserves", "cadence": "weekly", "time_utc": "11:30",
     "source": "SBP", "actual_series": "SBP:reserves_weekly", "expected_series": "UNMEASURED",
     "notes": "Thursday for the week to the previous Friday; an IMF tranche is a step"},
    {"name": "Workers' remittances (monthly)", "cadence": "monthly", "time_utc": "11:00",
     "source": "SBP", "actual_series": "SBP:remittances", "expected_series": "UNMEASURED",
     "notes": "around the 10th; Eid months and the kerb premium explain most of the variance"},
    {"name": "CPI (national, urban, rural) and the SPI weekly basket", "cadence": "monthly",
     "time_utc": "06:00", "source": "Pakistan Bureau of Statistics",
     "actual_series": "PBS:cpi", "expected_series": "UNMEASURED",
     "notes": "the 1st or 2nd of the month; the SPI is WEEKLY (Thursday) and leads it"},
    {"name": "Fortnightly petroleum price notification", "cadence": "monthly",
     "time_utc": "19:00", "source": "Finance Division / OGRA", "actual_series": "OGRA:petrol",
     "expected_series": "UNMEASURED",
     "notes": "the 15th and the last day of the month, effective the next day; twice a month"},
    {"name": "Trade balance (goods)", "cadence": "monthly", "time_utc": "06:00",
     "source": "PBS", "actual_series": "PBS:trade", "expected_series": "UNMEASURED",
     "notes": "textile exports by category and the import bill; the cotton and wheat lines"},
    {"name": "PCGA cotton arrivals (fortnightly)", "cadence": "monthly", "time_utc": "10:00",
     "source": "Pakistan Cotton Ginners Association", "actual_series": "PCGA:arrivals",
     "expected_series": "UNMEASURED",
     "notes": "1st and 16th during the arrival season (September-February); the crop signal"},
    {"name": "IMF review / Board decisions", "cadence": "quarterly", "time_utc": "UNMEASURED",
     "source": "IMF", "actual_series": "IMF:pakistan_reviews", "expected_series": "n/a",
     "notes": "staff-level agreement, Board approval and disbursement are three dated events"},
)

# --------------------------------------------------------------------------- holidays
#: FIXED federal holidays. Iqbal Day (9 November) was restored in 2022 after a hiatus; the
#: 1 July SBP bank holiday closes the banks for the half-year account closing.
FIXED_NATIONAL: tuple[tuple[int, int, str], ...] = (
    (2, 5, "Kashmir Solidarity Day"), (3, 23, "Pakistan Day"), (5, 1, "Labour Day"),
    (8, 14, "Independence Day"), (11, 9, "Iqbal Day"), (12, 25, "Quaid-e-Azam Day / Christmas"),
)
BANK_HOLIDAYS: tuple[tuple[int, int, str], ...] = ((7, 1, "SBP bank holiday (half-year closing)"),)

#: THE MOON-SIGHTING HOLIDAYS, as ANNOUNCED for 2024-2025 and PROJECTED for 2026. The Central
#: Ruet-e-Hilal Committee announces the sighting the evening before; a projected date can be
#: one day off and the government can extend the block. Each row: (date, name, status).
LUNAR_HOLIDAYS: dict[int, tuple[tuple[date, str, str], ...]] = {
    2024: ((date(2024, 4, 10), "Eid-ul-Fitr (day 1)", "ANNOUNCED"),
           (date(2024, 4, 11), "Eid-ul-Fitr (day 2)", "ANNOUNCED"),
           (date(2024, 4, 12), "Eid-ul-Fitr (day 3)", "ANNOUNCED"),
           (date(2024, 6, 17), "Eid-ul-Azha (day 1)", "ANNOUNCED"),
           (date(2024, 6, 18), "Eid-ul-Azha (day 2)", "ANNOUNCED"),
           (date(2024, 6, 19), "Eid-ul-Azha (day 3)", "ANNOUNCED"),
           (date(2024, 7, 16), "Ashura (9 Muharram)", "ANNOUNCED"),
           (date(2024, 7, 17), "Ashura (10 Muharram)", "ANNOUNCED"),
           (date(2024, 9, 17), "Eid Milad-un-Nabi", "ANNOUNCED")),
    2025: ((date(2025, 3, 31), "Eid-ul-Fitr (day 1)", "ANNOUNCED"),
           (date(2025, 4, 1), "Eid-ul-Fitr (day 2)", "ANNOUNCED"),
           (date(2025, 4, 2), "Eid-ul-Fitr (day 3)", "ANNOUNCED"),
           (date(2025, 6, 7), "Eid-ul-Azha (day 1, Saturday)", "ANNOUNCED"),
           (date(2025, 6, 9), "Eid-ul-Azha (day 3)", "ANNOUNCED"),
           (date(2025, 6, 10), "Eid-ul-Azha (day 4, extended)", "ANNOUNCED"),
           (date(2025, 7, 5), "Ashura (9 Muharram, Saturday)", "ANNOUNCED"),
           (date(2025, 7, 6), "Ashura (10 Muharram, Sunday)", "ANNOUNCED"),
           (date(2025, 9, 5), "Eid Milad-un-Nabi", "ANNOUNCED")),
    2026: ((date(2026, 3, 20), "Eid-ul-Fitr (day 1)", "PROJECTED"),
           (date(2026, 3, 23), "Eid-ul-Fitr (day 3, Monday)", "PROJECTED"),
           (date(2026, 5, 27), "Eid-ul-Azha (day 1)", "PROJECTED"),
           (date(2026, 5, 28), "Eid-ul-Azha (day 2)", "PROJECTED"),
           (date(2026, 5, 29), "Eid-ul-Azha (day 3)", "PROJECTED"),
           (date(2026, 6, 25), "Ashura (9 Muharram)", "PROJECTED"),
           (date(2026, 6, 26), "Ashura (10 Muharram)", "PROJECTED"),
           (date(2026, 8, 25), "Eid Milad-un-Nabi", "PROJECTED")),
}
#: One-off closures the government declared, which no rule produces.
DECLARED_CLOSURES: dict[date, str] = {
    date(2024, 2, 8): "general election day (declared public holiday)",
    date(2024, 11, 9): "Iqbal Day on a Saturday (no substitution in Pakistan)",
}


def national_holidays(year: int) -> dict[date, str]:
    """Federal holidays: the fixed ones, the lunar ones as announced or projected, and the
    one-off declarations. No weekend substitution exists in Pakistan: a holiday on a Saturday
    is simply lost, which is itself a fact a liquidity study must carry."""
    out: dict[date, str] = {}
    for m, d, name in FIXED_NATIONAL:
        out[date(year, m, d)] = name
    for day, name, status in LUNAR_HOLIDAYS.get(year, ()):
        out[day] = f"{name} [{status}]"
    for day, name in DECLARED_CLOSURES.items():
        if day.year == year:
            out[day] = name
    return dict(sorted(out.items()))


def bank_holidays(year: int) -> dict[date, str]:
    out = national_holidays(year)
    for m, d, name in BANK_HOLIDAYS:
        out[date(year, m, d)] = name
    return dict(sorted(out.items()))


def market_holidays(year: int) -> dict[date, str]:
    """PSX closed days: the bank calendar, weekdays only (the exchange does not open at the
    weekend, so a Saturday holiday is not a closure the tape can see)."""
    return {d: n for d, n in bank_holidays(year).items() if d.weekday() < 5}


def announced_dates(year: int) -> dict[date, str]:
    """Only the moon-sighting dates that were ANNOUNCED; a study that pools PROJECTED dates
    into the announced sample must say so, because the projected ones can be a day off."""
    return {d: n for d, n, st in LUNAR_HOLIDAYS.get(year, ()) if st == "ANNOUNCED"}


def ramadan_span(year: int) -> tuple[date, date] | None:
    """The fasting month as (first day, last day), projected from the Eid-ul-Fitr row: the
    market's hours shift earlier and the kerb demand for dollars and gold rises into it."""
    eid = next((d for d, n, _ in LUNAR_HOLIDAYS.get(year, ()) if "Fitr (day 1)" in n), None)
    if eid is None:
        return None
    return (eid - timedelta(days=30), eid - timedelta(days=1))


def is_market_holiday(day: date) -> bool:
    return day in market_holidays(day.year)


HOLIDAYS_RULE: dict[str, Any] = {
    "kind": "computed_from_rules",
    "authority": "the federal Interior Ministry notifies the fixed holidays; the Central "
                 "Ruet-e-Hilal Committee's moon sighting sets Eid, Ashura and Milad the "
                 "EVENING BEFORE; the SBP adds the 1 July bank holiday",
    "years": (2024, 2025, 2026),
    "weekend": "Saturday and Sunday (the banks); the PSX takes a Friday prayer break",
    "national_rule": "Kashmir Day 5 Feb, Pakistan Day 23 Mar, Labour Day 1 May, Independence "
                     "Day 14 Aug, Iqbal Day 9 Nov, Quaid Day 25 Dec; Eid-ul-Fitr (3 days), "
                     "Eid-ul-Azha (3 days), Ashura (2 days), Eid Milad-un-Nabi (1 day). NO "
                     "weekend substitution.",
    "market_rule": "the bank calendar on weekdays; Ramadan shortens the PSX session",
    "moon_sighting_rule": "DECLARED, not inferred: 2024-2025 rows are the ANNOUNCED closures; "
                          "2026 rows are PROJECTED and may be one day off or extended",
    "moving_feasts": "the lunar holidays drift about eleven days earlier each solar year",
    "known_dates": {
        "2024-02-08": "general election day, declared a public holiday",
        "2024-04-10": "Eid-ul-Fitr day 1 as announced after the 9 April sighting",
        "2024-06-17": "Eid-ul-Azha day 1 (Monday); three-day block to 19 June",
        "2025-03-31": "Eid-ul-Fitr day 1 (Monday); the announced block ran to 2 April",
        "2025-06-07": "Eid-ul-Azha on a Saturday; the government extended the block to Tuesday "
                      "10 June, so the closed weekdays were 9-10 June",
        "2026-03-20": "PROJECTED Eid-ul-Fitr; the announced date can differ by a day",
    },
    # THE SIBLING SCHEMA, DERIVED (2026-09-23). `research.countries.check_pack` reads a
    # `rule` string and a `table` of resolved years; this pack is computed from rules and
    # carried neither, so the parity checker could not read its calendar at all while every
    # other pack's was checked. Both are DERIVED from the functions above rather than typed,
    # so the two views cannot drift: the rule is this dict's own prose joined, and the table
    # is exactly what `market_holidays` returns for the declared years.
    "rule": " | ".join(str(v) for v in (_HOLIDAY_PROSE) if v),
    "table": {y: {d.isoformat(): n for d, n in market_holidays(y).items()} for y in YEARS},
    "status": "COMPUTED: the table is regenerated from the rule functions on import, so a "
              "year added to YEARS appears in both views at once",
    "fn": market_holidays,
    "national_fn": national_holidays,
    "bank_fn": bank_holidays,
    "announced_fn": announced_dates,
    "ramadan_fn": ramadan_span,
}

# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "NCCPL foreign and local investor portfolio investment (FIPI / LIPI), daily",
     "root": "https://www.nccpl.com.pk/en/market-information/fipi-lipi",
     "fields": ("foreign_net_usd", "by_category", "by_sector", "mutual_funds_net",
                "individuals_net", "banks_net"),
     "frequency": "daily", "snapshot": "session close", "publish_utc": "13:00", "lag_days": 0,
     "licence": "free, public", "available": True,
     "why": "the only daily investor-category flow series in South Asia outside India; the "
            "foreign leg is the FIPI line PK-K reads",
     "pit_warning": "posted the same evening; a T+1 alignment is the only PIT-safe one"},
    {"name": "SBP weekly liquid foreign exchange reserves (SBP-held and bank-held)",
     "root": "https://www.sbp.org.pk/ecodata/forex.pdf",
     "fields": ("sbp_reserves_usd", "bank_reserves_usd", "total"),
     "frequency": "weekly", "snapshot": "Friday", "publish_utc": "11:30", "lag_days": 6,
     "licence": "free, public", "available": True,
     "why": "the programme's binding number; an IMF tranche or a bilateral rollover is a step",
     "pit_warning": "six days stale on release; never a same-week conditioner"},
    {"name": "SBP monthly workers' remittances by corridor",
     "root": "https://www.sbp.org.pk/ecodata/Homeremit.pdf",
     "fields": ("total_usd", "saudi", "uae", "uk", "usa", "eu", "other_gcc"),
     "frequency": "monthly", "snapshot": "calendar month", "publish_utc": "11:00",
     "lag_days": 10, "licence": "free, public", "available": True,
     "why": "the largest dollar inflow; the kerb premium and Eid explain its swings",
     "pit_warning": "ten days stale; the corridor split is what carries the mechanism"},
    {"name": "a CFTC or exchange-traded rupee positioning series",
     "root": "", "fields": (), "frequency": "n/a", "snapshot": "", "publish_utc": "",
     "lag_days": 0, "licence": "", "available": False,
     "why": "no rupee future trades on any exchange the desk can read",
     "pit_warning": "DOES NOT EXIST: rupee positioning is UNMEASURED and is never proxied by "
                    "the rupee-dollar forward premium, which is a KIBOR object"},
)

# --------------------------------------------------------------------------- terminology
#: Urdu is the language of the sources that matter here -- the SBP's Urdu press, the Urdu
#: business press (Express, Jang, Dunya) and the trader groups -- and English is Pakistan's
#: second official language, so both scripts are carried. A query in English alone reaches
#: Dawn and Business Recorder and misses the ground the kerb rate is discussed on.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "PK-A": ("اسٹیٹ بینک", "شرح سود", "مانیٹری پالیسی", "پالیسی ریٹ", "زری پالیسی کمیٹی",
             "State Bank policy rate", "MPC decision", "KIBOR"),
    "PK-B": ("آئی ایم ایف", "قرض کی قسط", "جائزہ مذاکرات", "اسٹاف لیول معاہدہ", "پیشگی اقدامات",
             "IMF review", "staff-level agreement", "tranche", "prior actions", "EFF"),
    "PK-C": ("اوپن مارکیٹ", "انٹر بینک", "ڈالر ریٹ", "حوالہ ہنڈی", "ایکسچینج کمپنیاں",
             "kerb rate", "open market rate", "interbank rate", "hundi", "hawala", "ECAP"),
    "PK-D": ("پیٹرول کی قیمت", "ڈیزل کی قیمت", "اوگرا", "پیٹرولیم لیوی", "پندرہ روزہ",
             "petrol price notification", "petroleum levy", "OGRA summary"),
    "PK-E": ("ترسیلات زر", "بیرون ملک پاکستانی", "روشن ڈیجیٹل اکاؤنٹ", "عید سے پہلے",
             "remittances", "Roshan Digital Account", "overseas Pakistanis", "Eid inflows"),
    "PK-F": ("کپاس", "پھٹی", "روئی کی قیمت", "کاٹن جنرز", "ٹیکسٹائل برآمدات", "اپٹما",
             "cotton arrivals", "PCGA", "phutti", "APTMA", "cotton import"),
    "PK-G": ("گندم", "امدادی قیمت", "گندم کی درآمد", "چینی", "چینی کی برآمد", "پاسکو", "ٹی سی پی",
             "wheat support price", "wheat import", "sugar export", "PASSCO", "TCP tender"),
    "PK-H": ("ایل این جی", "گیس لوڈشیڈنگ", "کارگو", "ٹینڈر", "قطر معاہدہ",
             "LNG tender", "spot cargo", "gas load-shedding", "PLL", "RLNG"),
    "PK-I": ("سونا فی تولہ", "صرافہ", "سونے کی اسمگلنگ", "دبئی سے سونا", "زیورات",
             "tola rate", "Sarafa", "gold smuggling", "APGJA"),
    "PK-J": ("سعودی ڈپازٹ", "چینی قرضے", "رول اوور", "یورو بانڈ", "سکوک", "ڈیفالٹ کا خطرہ",
             "Saudi deposit rollover", "SAFE deposit", "Eurobond maturity", "CDS"),
    "PK-K": ("اسٹاک ایکسچینج", "کے ایس ای 100", "غیر ملکی سرمایہ کاری", "میوچل فنڈ", "بروکر",
             "KSE-100", "FIPI", "foreign selling", "PSX volume", "MSCI frontier"),
    "PK-L": ("چاند نظر آگیا", "رویت ہلال کمیٹی", "عید کی چھٹیاں", "بینک بند", "محرم",
             "moon sighted", "Ruet-e-Hilal", "Eid holidays", "bank holiday", "Ashura"),
    "PK-M": ("سی پیک", "چینی یوآن", "یوآن میں ادائیگی", "کرنسی سواپ", "گوادر",
             "CPEC", "yuan settlement", "currency swap line", "Gwadar"),
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
    labels. `queries` are native-script terms, never translations. `machine_use_allowed=False`
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
        "pk_sbp", "State Bank of Pakistan: monetary policy, reserves, remittances, statistics",
        layer="official",
        roots=("https://www.sbp.org.pk/m_policy/index.asp", "https://www.sbp.org.pk/ecodata/",
               "https://www.sbp.org.pk/press/", "https://www.sbp.org.pk/reports/"),
        queries=("مانیٹری پالیسی بیان", "شرح سود", "زرمبادلہ کے ذخائر", "ترسیلات زر",
                 "monetary policy statement", "policy rate", "liquid foreign exchange reserves",
                 "workers' remittances", "MPC minutes"),
        languages=("en", "ur"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public (SBP website terms)",
        notes="the decision statements are timestamped; the weekly reserves PDF is the "
              "programme's binding series; Urdu press releases are posted beside the English"),
    source_class(
        "pk_pbs", "Pakistan Bureau of Statistics: CPI, SPI, trade, LSM",
        layer="official",
        roots=("https://www.pbs.gov.pk/cpi", "https://www.pbs.gov.pk/trade-summary",
               "https://www.pbs.gov.pk/spi"),
        queries=("مہنگائی کی شرح", "ہفتہ وار مہنگائی", "برآمدات", "درآمدات", "consumer price "
                 "index", "sensitive price indicator", "trade summary", "large scale "
                 "manufacturing"),
        languages=("en", "ur"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the SPI is WEEKLY (Thursday) and leads the monthly CPI; base-year rebasings "
              "(2015-16) break the history and must be carried as a vintage"),
    source_class(
        "pk_finance_ogra", "Finance Division, OGRA and the ECC: petrol notifications, trade "
                           "decisions, budget", layer="official",
        roots=("https://www.finance.gov.pk", "https://ogra.org.pk/petroleum-prices",
               "https://www.finance.gov.pk/press_releases.html"),
        queries=("پیٹرولیم مصنوعات کی قیمتوں میں", "نوٹیفکیشن", "اقتصادی رابطہ کمیٹی", "گندم "
                 "درآمد", "چینی برآمد", "petroleum prices notification", "ECC decision",
                 "wheat import", "sugar export permission", "budget speech"),
        languages=("en", "ur"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the fortnightly notification is dated and effective at midnight; ECC decisions "
              "on sugar and wheat are the trade events of PK-G"),
    source_class(
        "pk_imf", "IMF Pakistan country page: staff reports, reviews, Board decisions",
        layer="official", roots=("https://www.imf.org/en/Countries/PAK",),
        queries=("Pakistan Extended Fund Facility", "staff-level agreement", "first review",
                 "prior actions", "net international reserves", "structural benchmarks"),
        languages=("en",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the staff report's conditionality tables date every prior action; PK-B's clock"),
    source_class(
        "pk_secp_psx_nccpl", "SECP, PSX and NCCPL: notices, FIPI/LIPI, indices",
        layer="official",
        roots=("https://www.psx.com.pk/psx/resources-and-tools/market-summaries",
               "https://www.nccpl.com.pk/en/market-information/fipi-lipi",
               "https://www.secp.gov.pk"),
        queries=("غیر ملکی سرمایہ کاروں کی فروخت", "مارکیٹ سمری", "FIPI", "foreign portfolio "
                 "investment", "market summary", "circuit breaker", "SECP notification"),
        languages=("en", "ur"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the daily FIPI/LIPI table is the positioning series; PSX itself has no CFD"),
    # ---- institutional
    source_class(
        "pk_brokers_research", "Brokerage research notes published openly: Topline, Arif Habib, "
                               "AKD, JS, Ismail Iqbal, Intermarket", layer="institutional",
        roots=("https://www.topline.com.pk/research", "https://www.arifhabibltd.com/research",
               "https://www.akdsecurities.net/research", "https://jsgcl.com/research"),
        queries=("MPC preview", "policy rate expectation survey", "Pakistan strategy",
                 "economy update", "kerb premium", "reserves adequacy", "Eurobond"),
        languages=("en",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free notes; some behind registration",
        notes="the MPC expectation SURVEYS these houses run are the stated consensus PK-A "
              "measures the surprise against; kept as the expectation source, never as a view"),
    source_class(
        "pk_mufap_ecap_aptma", "Trade bodies: MUFAP (funds), ECAP (exchange companies), APTMA "
                               "(textiles), PSMA (sugar), PCGA (ginners), REAP (rice)",
        layer="institutional",
        roots=("https://www.mufap.com.pk", "https://ecap.org.pk", "https://aptma.org.pk",
               "https://www.pcga.org", "https://www.reap.com.pk"),
        queries=("ایکسچینج کمپنیز ایسوسی ایشن", "اپٹما", "کاٹن جنرز", "شوگر ملز ایسوسی ایشن",
                 "open market rates", "fund flows", "cotton arrivals report", "textile "
                 "export data", "sugar stock position"),
        languages=("en", "ur"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="ECAP posts the kerb rate; PCGA's fortnightly arrivals are a counted crop; APTMA "
              "lobbies for cotton import duty changes and says so in dated press releases"),
    # ---- academic
    source_class(
        "pk_academic", "PIDE, SBP research bulletin and working papers, Lahore School of "
                       "Economics, LUMS, IBA", layer="academic",
        roots=("https://pide.org.pk/research/", "https://www.sbp.org.pk/research/",
               "https://lahoreschoolofeconomics.edu.pk/publications", "https://ideas.repec.org/"),
        queries=("exchange rate pass-through Pakistan", "remittances kerb premium", "monetary "
                 "transmission Pakistan", "hundi hawala", "cotton crop forecast", "PIDE policy "
                 "viewpoint", "SBP working paper"),
        languages=("en",), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="open access / publisher terms",
        notes="pass-through and remittance-diversion papers are the mechanism sources for "
              "PK-C and PK-D; they are hypotheses until the desk reproduces them"),
    # ---- practitioner
    source_class(
        "pk_practitioner_press", "Profit (Pakistan Today), Business Recorder's Brecorder, "
                                 "Dawn Business, The Express Tribune business", layer="practitioner",
        roots=("https://profit.pakistantoday.com.pk", "https://www.brecorder.com/business-finance",
               "https://www.dawn.com/business", "https://tribune.com.pk/business"),
        queries=("kerb premium", "dollar shortage", "LC restrictions", "reserves fall",
                 "MPC expected to", "IMF talks", "wheat import scandal", "sugar export",
                 "LNG cargo tender", "cotton import"),
        languages=("en",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="the English business press carries the dated trade and tender news; Brecorder's "
              "daily open-market and interbank tables are a usable PIT record"),
    source_class(
        "pk_urdu_business_press", "Urdu business press: Express, Jang, Dunya, Nawa-i-Waqt business "
                                  "pages and their TV tickers", layer="practitioner",
        roots=("https://www.express.pk/business/", "https://jang.com.pk/category/business",
               "https://urdu.dunyanews.tv/index.php/ur/Business"),
        queries=("ڈالر مہنگا", "ڈالر سستا", "اوپن مارکیٹ میں ڈالر", "سونا مہنگا", "پیٹرول مہنگا",
                 "شرح سود میں کمی", "آئی ایم ایف کی شرط", "چاند نظر"),
        languages=("ur",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="the Urdu tickers report the kerb rate and the tola price intraday, hours before "
              "the English tables; the ground PK-C lives on"),
    # ---- retail ecology
    source_class(
        "pk_retail_forums", "PSX retail communities: Facebook stock groups, the PSX subreddit, "
                            "Investor's Lounge, YouTube stock channels", layer="retail_ecology",
        roots=("https://www.reddit.com/r/PSX/", "https://www.youtube.com/results?search_query="
               "psx+stocks+urdu", "https://www.facebook.com/groups/psxinvestors"),
        queries=("کے ایس ای 100 آج", "کون سا شیئر خریدیں", "بلو چپ", "منافع", "اسٹاک مارکیٹ "
                 "کریش", "psx tips", "KSE 100 today", "dividend stocks pakistan"),
        languages=("ur", "en"), access_label="PUBLIC_SOCIAL", credibility="FRINGE",
        predictive_state="UNTESTED", licence="platform terms; public posts only",
        notes="KEPT AT LOW WEIGHT: single-name tips are the event lane's, but the retail "
              "crowd's dollar and gold panic vocabulary dates the stress episodes PK-C studies"),
    source_class(
        "pk_forex_signal_sellers", "Urdu/English 'forex signal' and MT4/MT5 EA sellers targeting "
                                   "Pakistani retail (Telegram, YouTube, TikTok)",
        layer="retail_ecology",
        roots=("https://www.youtube.com/results?search_query=forex+trading+urdu",
               "https://t.me/s/forexpakistan"),
        queries=("فاریکس ٹریڈنگ اردو", "گولڈ سگنل", "ای اے روبوٹ", "پراپ فرم", "forex urdu "
                 "course", "gold signals pakistan", "prop firm pakistan"),
        languages=("ur", "en"), access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="platform terms; public posts only",
        notes="SECP-unregulated; kept because Pakistan is one of the largest prop-firm and "
              "gold-signal retail bases on earth and its XAUUSD stop clusters are a real "
              "microstructure observable; nothing here is a source of edge"),
    # ---- app ecosystem
    source_class(
        "pk_fintech_apps", "Easypaisa, JazzCash, Roshan Digital Account, Sadapay/NayaPay, "
                           "KTrade/Sarmaaya and the SBP's Raast", layer="app_ecosystem",
        roots=("https://www.sbp.org.pk/RDA/index.html", "https://www.sbp.org.pk/dfs/",
               "https://sarmaaya.pk"),
        queries=("روشن ڈیجیٹل اکاؤنٹ", "ایزی پیسہ", "جاز کیش", "راست", "ڈیجیٹل ادائیگی",
                 "RDA inflows", "Raast transactions", "digital remittance app"),
        languages=("ur", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="SBP statistics free; app stores public",
        notes="RDA inflows are a published monthly diaspora-account flow, a forced flow with a "
              "stamp; the payments statistics are quarterly"),
    source_class(
        "pk_p2p_stablecoin_commentary", "Press coverage of the USDT-rupee peer-to-peer premium "
                                        "as a kerb-rate proxy", layer="app_ecosystem",
        roots=("https://profit.pakistantoday.com.pk/?s=usdt",
               "https://www.dawn.com/search?q=stablecoin+rupee"),
        queries=("یو ایس ڈی ٹی ریٹ", "کرپٹو پر پابندی", "USDT rupee premium", "P2P dollar rate"),
        languages=("ur", "en"), access_label="PUBLIC_WITH_TERMS", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="publisher terms",
        notes="PUBLIC COMMENTARY ONLY: no venue feed, no order book, no exchange named as a "
              "source (mandate 2026-08-18). The premium is a PKR stress observable reported in "
              "the press, carried at low weight beside the ECAP kerb rate"),
    # ---- media
    source_class(
        "pk_broadcast_wire", "Geo, ARY, Dunya, Samaa business tickers and the APP wire",
        layer="media",
        roots=("https://www.geo.tv/category/business", "https://arynews.tv/category/business/",
               "https://www.app.com.pk/business/"),
        queries=("اسٹیٹ بینک کا اعلان", "ڈالر کی قیمت", "سونے کی قیمت", "پیٹرول کی نئی قیمتیں",
                 "State Bank announces", "dollar rate today", "gold rate today"),
        languages=("ur", "en"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="the broadcast minute of an SBP or petrol announcement is the best public stamp "
              "when the press release carries none"),
    source_class(
        "pk_licensed_terminals", "Bloomberg, Refinitiv and the paid Pakistan data vendors "
                                 "(Mettis Global)", layer="media",
        roots=("https://mettisglobal.news",),
        queries=("Mettis Pakistan", "PKR interbank tick"),
        languages=("en",), access_label="LICENSED", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="subscription; terms forbid machine extraction",
        machine_use_allowed=False,
        notes="REGISTERED, NEVER SCRAPED: Mettis publishes interbank ticks behind a paywall; "
              "the desk reads only its public headlines"),
    # ---- archive
    source_class(
        "pk_archive", "Pakistan Economic Survey (annual, pre-budget), SBP annual reports, "
                      "State of the Economy, PBS census and historical CPI",
        layer="archive",
        roots=("https://www.finance.gov.pk/survey_2425.html",
               "https://www.sbp.org.pk/reports/annual/index.htm",
               "https://www.pbs.gov.pk/publications"),
        queries=("اقتصادی سروے", "سالانہ رپورٹ", "Pakistan Economic Survey", "State of the "
                 "Economy", "annual report SBP", "historical CPI"),
        languages=("en", "ur"), access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the Economic Survey lands in early June every year, the day before the budget: "
              "a dated release with the crop, remittance and reserve tables of the whole year"),
    # ---- physical economy
    source_class(
        "pk_physical", "OCAC petroleum sales, PCGA cotton arrivals, port of Karachi / Qasim "
                       "throughput, NEPRA electricity, NDMA flood bulletins, PMD monsoon",
        layer="physical_economy",
        roots=("https://www.ocac.org.pk", "https://www.pcga.org", "https://kpt.gov.pk",
               "https://nepra.org.pk", "https://www.ndma.gov.pk", "https://www.pmd.gov.pk"),
        queries=("پیٹرولیم مصنوعات کی فروخت", "کپاس کی آمد", "بجلی کی طلب", "سیلاب", "مون سون",
                 "petroleum sales OCAC", "cotton arrivals", "port throughput", "load-shedding",
                 "flood bulletin", "monsoon outlook"),
        languages=("en", "ur"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the 2022 floods destroyed about 40% of the cotton crop and turned the country "
              "into a record importer; the PCGA arrivals series is where that shows first"),
    source_class(
        "pk_usda_fao", "USDA FAS GAIN reports and FAO GIEWS for Pakistan cotton, wheat, sugar, "
                       "soybean and rice", layer="physical_economy",
        roots=("https://fas.usda.gov/data/search?f%5B0%5D=country%3A%22Pakistan%22",
               "https://www.fao.org/giews/countrybrief/country.jsp?code=PAK"),
        queries=("Pakistan cotton and products annual", "Pakistan grain and feed", "Pakistan "
                 "sugar annual", "Pakistan oilseeds", "GIEWS Pakistan"),
        languages=("en",), access_label="OPEN_DATA", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="public domain (US government work)",
        notes="the import forecasts the softs market actually reads for Pakistan; dated"),
    # ---- source graph
    source_class(
        "pk_source_graph", "Who cites whom: the SBP -> brokers -> press -> retail chain, and the "
                           "IMF -> Finance Division -> OGRA notification chain",
        layer="source_graph",
        roots=("https://www.sbp.org.pk/press/", "https://profit.pakistantoday.com.pk"),
        queries=("citing the State Bank", "according to the IMF staff report", "Topline survey "
                 "shows", "ECAP said", "بحوالہ اسٹیٹ بینک", "ذرائع کے مطابق"),
        languages=("en", "ur"), access_label="PUBLIC", credibility="UNKNOWN",
        predictive_state="UNTESTED", licence="derived from the public sources above",
        notes="'ذرائع کے مطابق' (according to sources) marks the unattributed leak a day before "
              "a notification; the graph is how a leak is told from a repost"),
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
    {"name": "SBP policy rate decisions and MPC statements", "source": "SBP",
     "coverage": "1991 onward (MPC statements from 2005)", "frequency": "8 per year",
     "publication_lag_days": 0.0, "revisions": "never revised", "licence": "free, public",
     "history_from": "2005-01", "pit_feasible": True,
     "assets": ("USDINR", "XAUUSD", "US500"),
     "mechanism_families": ("policy_surprise", "event_reaction"),
     "how_to_fetch": "sbp.org.pk/m_policy -- the statement PDF and the press release; the "
                     "announcement minute is stamped from the release, never assumed"},
    {"name": "SBP weekly liquid foreign exchange reserves", "source": "SBP",
     "coverage": "2001 onward", "frequency": "weekly", "publication_lag_days": 6.0,
     "revisions": "rarely; a restatement is a dated event", "licence": "free, public",
     "history_from": "2001-07", "pit_feasible": True,
     "assets": ("USDINR", "XAUUSD", "XBRUSD"), "mechanism_families": ("programme_clock",),
     "how_to_fetch": "sbp.org.pk/ecodata/forex.pdf every Thursday; keep each PDF as a vintage"},
    {"name": "Workers' remittances by corridor", "source": "SBP",
     "coverage": "1972 onward (corridor split from 2000)", "frequency": "monthly",
     "publication_lag_days": 10.0, "revisions": "minor, next month", "licence": "free, public",
     "history_from": "2000-07", "pit_feasible": True,
     "assets": ("XAUUSD", "USDINR", "GBPUSD"), "mechanism_families": ("seasonal_flow",),
     "how_to_fetch": "sbp.org.pk/ecodata/Homeremit.pdf; the Eid month is the seasonal spike"},
    {"name": "ECAP open-market and SBP interbank daily rates (the kerb premium)",
     "source": "ECAP / SBP / Brecorder tables", "coverage": "2010 onward", "frequency": "daily",
     "publication_lag_days": 0.0, "revisions": "never", "licence": "free, public",
     "history_from": "2010-01", "pit_feasible": True, "assets": ("USDINR", "XAUUSD"),
     "mechanism_families": ("stress_indicator", "flow_diversion"),
     "how_to_fetch": "ecap.org.pk daily posting and sbp.org.pk/ecodata/rates; Brecorder's "
                     "archive carries both back to 2010; the premium is derived"},
    {"name": "Fortnightly petroleum price notifications", "source": "Finance Division / OGRA",
     "coverage": "2016 onward (fortnightly from 2020)", "frequency": "twice a month",
     "publication_lag_days": 0.0, "revisions": "never", "licence": "free, public",
     "history_from": "2016-01", "pit_feasible": True, "assets": ("XBRUSD", "XTIUSD"),
     "mechanism_families": ("administered_price", "pass_through"),
     "how_to_fetch": "finance.gov.pk press releases; each carries the effective date; the "
                     "OGRA summary the day before is the expectation"},
    {"name": "PCGA fortnightly cotton arrivals", "source": "Pakistan Cotton Ginners Association",
     "coverage": "2005 onward", "frequency": "fortnightly in season", "publication_lag_days": 2.0,
     "revisions": "cumulative; never restated", "licence": "free, public",
     "history_from": "2005-09", "pit_feasible": True, "assets": ("COTTON",),
     "mechanism_families": ("supply_count", "import_demand"),
     "how_to_fetch": "pcga.org arrivals report; a counted physical flow by province"},
    {"name": "NCCPL FIPI / LIPI daily portfolio investment", "source": "NCCPL",
     "coverage": "2007 onward", "frequency": "daily", "publication_lag_days": 0.0,
     "revisions": "never", "licence": "free, public", "history_from": "2007-01",
     "pit_feasible": True, "assets": ("US500", "USDINR"),
     "mechanism_families": ("positioning", "foreign_flow"),
     "how_to_fetch": "nccpl.com.pk market information; posted after the close"},
    {"name": "PBS CPI, SPI and trade summary", "source": "Pakistan Bureau of Statistics",
     "coverage": "CPI 2008 base to 2016 base; SPI weekly from 2008", "frequency": "monthly / weekly",
     "publication_lag_days": 1.0, "revisions": "rebasing only", "licence": "free, public",
     "history_from": "2008-07", "pit_feasible": True, "assets": ("XBRUSD", "WHEAT", "SUGAR"),
     "mechanism_families": ("release_surprise",),
     "how_to_fetch": "pbs.gov.pk; the SPI is released on Thursday and leads the CPI"},
    {"name": "IMF programme documents: staff reports, reviews, disbursement dates",
     "source": "IMF", "coverage": "2008 onward (SBA 2008, EFF 2013, EFF 2019, SBA 2023, EFF 2024)",
     "frequency": "per review", "publication_lag_days": 7.0, "revisions": "never",
     "licence": "free, public", "history_from": "2008-11", "pit_feasible": True,
     "assets": ("USDINR", "XAUUSD", "US500"), "mechanism_families": ("programme_clock",),
     "how_to_fetch": "imf.org/en/Countries/PAK; the press release dates the Board decision and "
                     "the disbursement; the staff report tables date every prior action"},
    {"name": "TCP / ECC wheat and sugar trade decisions", "source": "TCP tenders, ECC minutes",
     "coverage": "2010 onward", "frequency": "irregular, dated", "publication_lag_days": 1.0,
     "revisions": "never", "licence": "free, public", "history_from": "2010-01",
     "pit_feasible": True, "assets": ("WHEAT", "SUGAR"),
     "mechanism_families": ("trade_decision", "import_demand"),
     "how_to_fetch": "tcp.gov.pk tender notices; ECC press releases at finance.gov.pk"},
    {"name": "PLL / PSO LNG spot cargo tenders and awards", "source": "Pakistan LNG Ltd / PSO",
     "coverage": "2015 onward", "frequency": "monthly, irregular", "publication_lag_days": 1.0,
     "revisions": "never", "licence": "free, public", "history_from": "2015-03",
     "pit_feasible": False, "assets": ("XNGUSD", "XBRUSD"),
     "mechanism_families": ("spot_demand", "tender_event"),
     "how_to_fetch": "paklng.com tender notices and the press coverage of bids; PIT IS PARTIAL: "
                     "the award minute is not always published, so a cell compiled on it is "
                     "UNMEASURED for the cargoes without a stamp"},
    {"name": "Bilateral deposits and Eurobond/Sukuk maturities (Saudi, UAE, China SAFE)",
     "source": "SBP, Finance Division, bond prospectuses", "coverage": "2018 onward",
     "frequency": "irregular, dated", "publication_lag_days": 0.0, "revisions": "never",
     "licence": "free, public", "history_from": "2018-11", "pit_feasible": True,
     "assets": ("USDINR", "XAUUSD", "USDCNH"), "mechanism_families": ("forced_flow_calendar",),
     "how_to_fetch": "the rollover is announced by the Finance Division; maturities are in the "
                     "prospectuses; the SAFE deposits are in the SBP's reserve notes"},
)

# --------------------------------------------------------------------------- actors
ACTORS: tuple[dict[str, Any], ...] = (
    {"name": "State Bank of Pakistan Monetary Policy Committee",
     "holds": "the policy rate and the corridor, Rs 10-13trn of OMO injections that fund the "
              "banks' T-bill holdings, and about US$10-15bn of own reserves",
     "forced_to": ("decide at eight scheduled meetings on a published half-yearly calendar and "
                   "publish the statement the same afternoon",
                   "publish the reserves every Thursday and the remittances every month",
                   "meet the IMF's net-international-reserves and primary-balance tests at "
                   "quarter ends"),
     "when": "mid-afternoon Karachi on the meeting day (about 09:00-12:00 UTC; the minute varies "
             "and is stamped from the release); reserves at about 11:30 UTC Thursdays",
     "information": ("the full weekly reserves before the market", "the IMF mission's numbers",
                     "the remittance corridors in real time through the banks",
                     "the exchange companies' books it supervises"),
     "constraints": ("the IMF programme's performance criteria and prior actions",
                     "a 5-7% medium-term inflation target with a fiscal dominance problem (debt "
                     "service over half of federal revenue)",
                     "a corridor of +/-100bp around the policy rate",
                     "the 2022 SBP Act amendment forbidding direct government financing"),
     "instruments": ("USDINR", "XAUUSD", "US500"),
     "counterparties": ("the primary dealers holding T-bills against OMOs", "the IMF",
                        "the exchange companies", "the Finance Division"),
     "observables": ("the statement and its press conference", "the weekly reserves PDF",
                     "the T-bill cut-off yields between meetings",
                     "the kerb premium the week before a decision"),
     "impact": "a decision moves KIBOR and the T-bill curve immediately; the rupee reacts through "
               "the kerb before the interbank; the executable effect is on the regional and "
               "gold legs through the stress channel, not on PKR itself",
     "persistence": "the level effect lasts to the next meeting; the 2022-23 emergency hikes "
                    "and the 2024 cutting cycle (22% to 11% in twelve months) are one era each",
     "falsifier": "the same window on the eight nearest non-meeting weekdays; an effect that "
                  "survives there is a weekday effect wearing the State Bank's hat, and a "
                  "decision-day move on USDINR that matches a non-decision Monday is noise",
     "notes": "the emergency meetings of 2022-04-07 and 2023-06-26 are their own class"},
    {"name": "The Finance Division and OGRA as the fortnightly petrol price setter",
     "holds": "the petroleum levy (up to Rs 70-80 per litre) and the notification power",
     "forced_to": ("notify petrol and diesel prices effective the 1st and the 16th",
                   "pass the previous fortnight's Brent and rupee through with a discretionary "
                   "levy adjustment", "meet the IMF's petroleum-levy revenue target"),
     "when": "the evening of the 15th and the last day of the month, effective at midnight "
             "Karachi (19:00 UTC)",
     "information": ("the OGRA summary a day ahead", "the IMF's levy target",
                     "the rupee's fortnightly average"),
     "constraints": ("the levy revenue target in the budget", "the political cost of a hike",
                     "the OGRA formula's two-week lag"),
     "instruments": ("XBRUSD", "XTIUSD"),
     "counterparties": ("the oil marketing companies", "the refineries", "the IMF"),
     "observables": ("the notification and its effective date", "the OGRA summary",
                     "the levy per litre line"),
     "impact": "sets the transport component of the monthly CPI; a large hike is followed by a "
               "protest cycle and by the MPC statement's 'administered prices' line",
     "persistence": "two weeks by construction; the levy component drifts with the budget",
     "falsifier": "the notification-eve window on XBRUSD shows no abnormal move against the "
                  "matched weekday control; Pakistan is a price-taker in crude and this actor's "
                  "effect is on domestic CPI, so an outward edge that survives the control is "
                  "the finding, and an absent one is the expected result",
     "notes": "the pass-through is an INPUT-direction mechanism; PK-D measures it honestly"},
    {"name": "The IMF mission and Executive Board (Pakistan programme)",
     "holds": "the 2024 EFF's undisbursed tranches and the review calendar",
     "forced_to": ("complete semi-annual reviews against dated performance criteria",
                   "publish the staff report with its prior actions", "disburse only on Board "
                   "approval, which the Thursday reserves then show"),
     "when": "staff-level agreement, Board approval and disbursement are three dated events "
             "weeks apart; the Board meets on a published calendar",
     "information": ("the fiscal and reserve data ahead of the market",
                     "the bilateral financing assurances"),
     "constraints": ("the programme's own conditionality", "the financing gap the bilaterals "
                     "must fill before a Board meeting"),
     "instruments": ("USDINR", "XAUUSD", "US500"),
     "counterparties": ("the Finance Division", "the SBP", "Saudi Arabia, the UAE and China as "
                        "the financing-assurance providers"),
     "observables": ("the press release", "the staff report's tables", "the reserves step"),
     "impact": "the sovereign's stress premium collapses or widens around each review; 2022-23 "
               "saw CDS above 100 points upfront while the ninth review stalled",
     "persistence": "one review cycle; the effect is a step, not a drift",
     "falsifier": "the same window around IMF Board dates for OTHER programme countries shows "
                  "the same move on the regional cross, in which case it is a dollar or "
                  "risk event and not a Pakistan programme event",
     "notes": "the stalled 2022-23 ninth review is the natural experiment of the stress era"},
    {"name": "Exchange companies (ECAP members) and the kerb market",
     "holds": "the open-market dollar book; about a fifth of remittance conversion",
     "forced_to": ("post a daily open-market rate", "surrender a share of purchases to the "
                   "interbank under SBP rules", "close when the SBP or FIA raids them, as in "
                   "September 2023"),
     "when": "posting around 10:00 Karachi (05:00 UTC); the rate moves through the day",
     "information": ("the street's dollar demand before the banks see it",
                     "the hundi rate the competing channel offers"),
     "constraints": ("SBP licensing and the 2023 consolidation into larger companies",
                     "the surrender requirement", "physical cash logistics"),
     "instruments": ("USDINR", "XAUUSD"),
     "counterparties": ("remittance recipients", "importers refused interbank dollars",
                        "gold traders", "the hundi operators"),
     "observables": ("the kerb-interbank premium", "the volume the companies report",
                     "the press reports of dollar shortages"),
     "impact": "a premium above Rs 5-10 diverts remittances out of the banking channel within a "
               "month; the September 2023 crackdown closed a Rs 20+ gap and the next remittance "
               "print jumped",
     "persistence": "weeks; the premium is the fastest stress indicator the country has",
     "falsifier": "a rising kerb premium that is NOT followed by a lower banking-channel "
                  "remittance print within two months, and a crackdown not followed by a "
                  "higher one, refutes the diversion mechanism the domain is built on",
     "notes": "the premium is the state variable of PK-C and a conditioner for PK-E"},
    {"name": "Overseas Pakistanis (the Gulf, the UK, the US) as remittance senders",
     "holds": "about US$30-35bn a year of remittances; the Roshan Digital Account balances",
     "forced_to": ("send ahead of Eid and Ramadan for family consumption", "choose the bank "
                   "channel or hundi on the kerb premium", "convert at the posted rate"),
     "when": "the two Eid months carry the seasonal peak; the SBP prints on about the 10th",
     "information": ("the kerb rate from the Urdu press and the apps",
                     "the hundi rate from the diaspora networks"),
     "constraints": ("Gulf labour-market cycles", "the UK and US cost of living",
                     "the SBP incentive schemes for banking-channel flows"),
     "instruments": ("XAUUSD", "GBPUSD", "USDINR"),
     "counterparties": ("the banks and exchange companies", "the hundi operators",
                        "the gold retailers the cash reaches"),
     "observables": ("the monthly remittance print by corridor", "RDA inflows",
                     "the Eid date the moon-sighting committee announces"),
     "impact": "the Eid month is 10-20% above the trend month; part of it reaches the Sarafa "
               "gold market, which is where the executable leg is",
     "persistence": "seasonal, every year, on the lunar calendar",
     "falsifier": "the Eid-month excess disappears once the kerb premium and the lunar date "
                  "are controlled, or the tola-gold premium shows no rise into Eid against the "
                  "matched non-Eid months",
     "notes": "the corridor split matters: Saudi and UAE flows follow the Gulf oil cycle"},
    {"name": "Textile mills (APTMA members) as cotton importers and dollar earners",
     "holds": "about 60% of goods exports; a cotton import bill of 1-4 mt in bad crop years",
     "forced_to": ("import cotton when the domestic crop fails (2022 floods: about 40% lost)",
                   "book LCs for imports and repatriate export proceeds under SBP rules",
                   "lobby the ECC for duty and gas tariff relief in dated press releases"),
     "when": "the arrival season September-February sets the import need; import contracts "
             "cluster December-March",
     "information": ("PCGA arrivals before the public summary", "their own order books from EU "
                     "and US buyers", "the gas tariff decisions"),
     "constraints": ("the domestic crop and its quality", "the SBP's LC restrictions in stress "
                     "eras", "the GSP+ status for EU market access"),
     "instruments": ("COTTON", "EURUSD", "GBPUSD"),
     "counterparties": ("US, Brazilian and West African cotton exporters", "EU and US apparel "
                        "buyers", "the banks issuing LCs"),
     "observables": ("PCGA arrivals vs the prior year", "USDA's Pakistan import forecast",
                     "PBS textile export lines", "the KCA-ICE spread"),
     "impact": "Pakistan's import swing of 1-2 mt is a few percent of world trade; a bad crop "
               "year is a real demand shock the ICE contract reads with a lag",
     "persistence": "one crop year; the 2022-23 import surge is the reference episode",
     "falsifier": "PCGA arrivals materially below the prior year that are NOT followed by higher "
                  "USDA import forecasts and a firmer ICE-KCA spread within a quarter",
     "notes": "the two-lane order: mills are actors; no share CFD enters an instrument tuple"},
    {"name": "PASSCO, the provincial food departments and TCP as the wheat authority",
     "holds": "the support price, the procurement target (about 5-7 mt) and the import decision",
     "forced_to": ("announce the support price before the April harvest", "procure at it",
                   "import through TCP tenders when the harvest falls short (2023: about 3.5 mt) "
                   "or ban imports when it does not (2024)"),
     "when": "support price in February-March; harvest April-May; import tenders July-January",
     "information": ("the crop estimate from the provinces", "the stock position"),
     "constraints": ("the fiscal cost of the support price", "the IMF's objection to commodity "
                     "operations", "flour price politics"),
     "instruments": ("WHEAT",),
     "counterparties": ("the flour mills", "Black Sea and Australian exporters",
                        "the farmers selling at or below support"),
     "observables": ("the support price notification", "the TCP tender notices and awards",
                     "USDA's Pakistan wheat balance"),
     "impact": "a 3 mt import programme is about 1.5% of world trade; the tenders are dated and "
               "the market reads them as Black Sea demand",
     "persistence": "one marketing year",
     "falsifier": "TCP tender windows on WHEAT show no abnormal move against the matched control, "
                  "or the same move appears on non-tender Fridays",
     "notes": "the 2024 private-import glut and its inquiry are the negative case"},
    {"name": "Pakistan LNG Ltd and PSO as spot LNG buyers",
     "holds": "the long-term Qatar contracts and the spot tender programme",
     "forced_to": ("tender for spot cargoes for the winter when domestic gas falls short",
                   "pay in dollars the SBP may not release (2022 tenders went unfilled)",
                   "cut gas to industry when cargoes are missed"),
     "when": "tenders issued weeks ahead of delivery windows; winter is the season",
     "information": ("the gas demand-supply balance", "the SBP's willingness to release "
                     "dollars"),
     "constraints": ("JKM affordability", "the dollar position", "the terminal capacity"),
     "instruments": ("XNGUSD", "XBRUSD"),
     "counterparties": ("the trading houses bidding", "Qatar Energy", "the terminals"),
     "observables": ("the tender notice", "the award or the no-bid press report",
                     "the load-shedding schedule"),
     "impact": "Pakistan's spot demand is marginal to the Atlantic-basin Henry Hub; the true leg "
               "is JKM, which is absent, so this edge is carried as weak and says so",
     "persistence": "seasonal",
     "falsifier": "a tender window that moves XNGUSD is a coincidence unless the same window "
                  "moves JKM-linked series more; the desk cannot see JKM and records UNMEASURED",
     "notes": "an honest weak edge: the pack refuses to promote it above HYPOTHESIS"},
    {"name": "The Sarafa market (APGJA) and the gold smuggling channel",
     "holds": "the daily tola price and the retail bullion book; Dubai is the supply",
     "forced_to": ("set the tola price off LBMA and the interbank rate each morning",
                   "clear demand into Eid and the wedding season", "source supply through "
                   "Dubai when official import is restricted, at a premium"),
     "when": "the daily rate in the late morning Karachi; demand peaks into Eid and October-"
             "December weddings",
     "information": ("the kerb rate", "the Dubai premium", "the wedding-season order book"),
     "constraints": ("the SBP's import restrictions", "customs enforcement",
                     "the LBMA reference"),
     "instruments": ("XAUUSD",),
     "counterparties": ("Dubai bullion dealers", "retail buyers", "the exchange companies"),
     "observables": ("the tola price vs LBMA x interbank", "the smuggling seizure reports",
                     "the Eid and wedding calendar"),
     "impact": "Pakistan's retail demand is a small share of the world's, but its premium to "
               "LBMA is a clean measure of the kerb-and-import stress state",
     "persistence": "seasonal plus the stress episodes",
     "falsifier": "the tola premium carries no information about the next remittance print or "
                  "the kerb premium once both are lagged, and Eid windows on XAUUSD match the "
                  "matched-weekday control",
     "notes": "the executable leg is the global gold price; the premium is the observable"},
    {"name": "Bilateral depositors: Saudi Arabia, the UAE and China's SAFE",
     "holds": "about US$12-13bn of deposits at the SBP that roll over on dated maturities",
     "forced_to": ("roll or withdraw at maturity", "announce the rollover, which the Finance "
                   "Division then publishes"),
     "when": "maturities cluster around the fiscal year end and the IMF Board dates",
     "information": ("the IMF's financing-assurance requests"),
     "constraints": ("their own diplomatic calendars", "the IMF's requirement that the "
                     "financing gap be closed before the Board meets"),
     "instruments": ("USDINR", "USDCNH", "XAUUSD"),
     "counterparties": ("the SBP", "the IMF"),
     "observables": ("the rollover announcement", "the reserves step or its absence"),
     "impact": "a missed rollover is a reserves cliff; every one so far has rolled",
     "persistence": "one maturity",
     "falsifier": "rollover announcement windows carry no abnormal move on the regional cross or "
                  "gold against the matched control; the desk expects that and records it",
     "notes": "a forced-flow calendar with a known date and a binary outcome"},
    {"name": "Foreign portfolio investors and the local mutual funds at the PSX",
     "holds": "the FIPI and LIPI lines the NCCPL publishes daily",
     "forced_to": ("rebalance on the MSCI Frontier reviews (Pakistan was demoted from EM to "
                   "Frontier in 2021)", "sell into a rupee stress episode", "buy the "
                   "programme-approval rallies"),
     "when": "MSCI reviews in May and November; daily flows after the close",
     "information": ("the same public data as everyone; the funds' own redemptions"),
     "constraints": ("the dollar repatriation rules", "the index weight"),
     "instruments": ("US500", "USDINR"),
     "counterparties": ("local individuals and banks on the other side of the FIPI line"),
     "observables": ("FIPI net by category", "the MSCI review announcement"),
     "impact": "small in dollars; the sign of FIPI is a clean read of foreign risk appetite for "
               "Pakistan and co-moves with the frontier complex",
     "persistence": "episodic",
     "falsifier": "FIPI carries no lead on the regional cross or on frontier risk beyond what "
                  "US500 already carries",
     "notes": "the KSE-100 itself has no CFD; the flow is the object"},
    {"name": "The Central Ruet-e-Hilal Committee (moon sighting)",
     "holds": "the power to declare the first day of Shawwal, Dhu al-Hijjah and Muharram",
     "forced_to": ("meet on the 29th of the lunar month and announce the sighting or its "
                   "absence the same evening", "accept or reject provincial testimonies"),
     "when": "after sunset Karachi on the 29th of the lunar month",
     "information": ("the astronomical prediction", "the testimonies"),
     "constraints": ("the astronomical possibility of sighting", "the political pressure to "
                     "align with Saudi Arabia, which Pakistan usually refuses"),
     "instruments": ("XAUUSD", "USDINR"),
     "counterparties": ("the government, which then notifies the holidays", "the banks"),
     "observables": ("the announcement minute", "the notification of the holiday block"),
     "impact": "the closed day is fixed the evening before; a liquidity study on the projected "
               "date is wrong in the years the sighting is refused",
     "persistence": "three times a year, every year",
     "falsifier": "the ANNOUNCED holiday dates show the same liquidity signature as PROJECTED "
                  "dates that were not holidays, in which case the mechanism is the lunar "
                  "season and not the closure",
     "notes": "the only actor in the pack whose decision is astronomical"},
    {"name": "China's policy banks and the CPEC creditors",
     "holds": "about US$25-30bn of Pakistan's external debt, the yuan swap line (CNY 30bn) and "
              "the power-project receivables",
     "forced_to": ("roll over commercial loans at maturity", "receive the circular-debt "
                   "payments the IMF programme schedules", "settle some trade in yuan"),
     "when": "loan maturities and the IMF's financing-assurance windows",
     "information": ("the receivables position", "the Chinese state's own priorities"),
     "constraints": ("China's own capital rules", "the IMF's insistence on rollovers"),
     "instruments": ("USDCNH", "USDINR"),
     "counterparties": ("the SBP and the Finance Division", "the IPPs"),
     "observables": ("the rollover announcements", "the swap-line usage in SBP notes"),
     "impact": "negligible for USDCNH itself; the edge is recorded as HYPOTHESIS and weak",
     "persistence": "one maturity",
     "falsifier": "no measurable move on USDCNH around Pakistan rollover dates -- the expected "
                  "result, which the pack records rather than hides",
     "notes": "carried for completeness of the actor map, not for its executable strength"},
)

# --------------------------------------------------------------------------- domains
DOMAINS: tuple[dict[str, Any], ...] = (
    {"id": "PK-A", "title": "SBP decisions on a published calendar with a stress channel",
     "objects": ("the eight scheduled decisions and the two emergency meetings",
                 "the statement's 'administered prices' and 'external account' lines",
                 "the T-bill cut-off drift between meetings",
                 "the kerb premium the week before a decision"),
     "conditions": ("the era: hiking (2021-23), the 22% plateau, the 2024-25 easing",
                    "whether the meeting fell inside an IMF review window",
                    "the sign of the kerb premium change into the meeting"),
     "instruments": ("USDINR", "XAUUSD", "US500"),
     "controls": ("the same window on the eight nearest non-meeting weekdays",
                  "the same window on RBI decision days, separating 'a South Asian bank "
                  "decided' from 'the SBP decided'",
                  "a placebo drawn from the T-bill curve's daily noise"),
     "notes": "the rupee is absent, so the executable effect is a stress-channel effect"},
    {"id": "PK-B", "title": "The IMF programme clock: reviews, prior actions, tranches",
     "objects": ("staff-level agreement dates", "Board approval dates", "disbursement steps in "
                 "the Thursday reserves", "prior-action deadlines (budget, tariff, levy)"),
     "conditions": ("whether the review was on time or stalled (2022-23)",
                    "whether the bilateral assurances were in place before the Board",
                    "the era"),
     "instruments": ("USDINR", "XAUUSD", "US500"),
     "controls": ("IMF Board dates for other programme countries on the same instruments",
                  "the same window on non-Board Fridays",
                  "the reserves step on Thursdays with no tranche"),
     "notes": "three dated events per review; pooling them blends three reactions"},
    {"id": "PK-C", "title": "The kerb premium and remittance diversion",
     "objects": ("the ECAP open-market rate", "the SBP interbank close", "the premium and its "
                 "sign", "the September 2023 crackdown as a break"),
     "conditions": ("the premium level bucket (below Rs 2, 2-10, above 10)",
                    "the direction of the change over the prior week",
                    "whether a crackdown or an SBP circular landed"),
     "instruments": ("USDINR", "XAUUSD"),
     "controls": ("the same premium series lagged by one month against the remittance print, "
                  "vs a shuffled-lag null",
                  "the Bangladesh kerb premium in the same months (a sibling economy with the "
                  "same channel), to separate 'South Asia' from 'Pakistan'",
                  "the tola-gold premium as an alternative stress measure"),
     "notes": "the premium is a lead indicator, not a tradeable; the tests are on what follows"},
    {"id": "PK-D", "title": "The fortnightly petrol notification as an administered pass-through",
     "objects": ("the notification on the 15th and the last day", "the OGRA summary a day "
                 "ahead", "the levy per litre", "the two-week Brent and rupee averages"),
     "conditions": ("the sign and size of the change", "whether the levy moved with it",
                    "whether the notification was delayed or split"),
     "instruments": ("XBRUSD", "XTIUSD"),
     "controls": ("the same UTC window on the 8th and the 23rd (no notification)",
                  "the matched weekday+hour control on XBRUSD",
                  "the OGRA summary date as an alternative event, to see which of the two "
                  "carries any move"),
     "notes": "an INPUT-direction mechanism; the honest expectation is no outward effect"},
    {"id": "PK-E", "title": "Remittances, Ramadan and Eid on the lunar calendar",
     "objects": ("the monthly remittance print by corridor", "the Eid months", "RDA inflows",
                 "the Gulf corridor's oil-cycle beta"),
     "conditions": ("the lunar month relative to Eid", "the kerb premium state",
                    "the Gulf oil price over the prior quarter"),
     "instruments": ("XAUUSD", "GBPUSD", "USDINR"),
     "controls": ("the same lunar windows on gold in years with a low kerb premium",
                  "the Indian remittance seasonality on the same dates (Diwali, not Eid), "
                  "separating 'festival' from 'Eid'",
                  "the matched non-Eid months"),
     "notes": "the executable leg is gold through the Sarafa channel; small but clean"},
    {"id": "PK-F", "title": "The cotton crop, the arrivals count and the import swing",
     "objects": ("PCGA fortnightly arrivals vs prior year", "USDA's Pakistan import forecast",
                 "the KCA spot rate vs ICE", "the 2022 flood year"),
     "conditions": ("arrivals shortfall bucket at mid-season (November)",
                    "the SBP's LC regime (restricted or open)",
                    "the ICE price level relative to the KCA rate"),
     "instruments": ("COTTON",),
     "controls": ("Indian CCI arrivals in the same fortnights (the sibling crop), to separate "
                  "'South Asian crop' from 'Pakistan crop'",
                  "the same fortnight windows on COTTON in years with a normal crop",
                  "a randomised-date null on the arrivals release days"),
     "notes": "the strongest outward edge in the pack; a counted physical flow"},
    {"id": "PK-G", "title": "Wheat and sugar: support prices, tenders, export permissions",
     "objects": ("the wheat support price notification", "TCP wheat import tenders",
                 "ECC sugar export permissions and import decisions", "the April-May harvest"),
     "conditions": ("the harvest estimate vs the procurement target", "the stock position at "
                    "the decision", "the era (2023 import programme vs 2024 import ban)"),
     "instruments": ("WHEAT", "SUGAR"),
     "controls": ("Egypt's GASC / Mostakbal Misr tender windows on WHEAT, the reference "
                  "importer, to scale Pakistan's tender effect",
                  "the same window on non-tender days",
                  "India's sugar export policy dates on SUGAR, the larger neighbour"),
     "notes": "Pakistan is a swing importer of wheat and a swing exporter of sugar"},
    {"id": "PK-H", "title": "LNG spot tenders and the winter gas shortfall",
     "objects": ("PLL/PSO tender notices and awards", "the unfilled tenders of 2022",
                 "the load-shedding schedule", "the Qatar contract slope"),
     "conditions": ("whether the tender was awarded or received no bids",
                    "the SBP's dollar release state", "the season"),
     "instruments": ("XNGUSD", "XBRUSD"),
     "controls": ("Bangladesh's Petrobangla tender windows (the sibling buyer) on the same "
                  "instruments", "non-tender weeks", "the matched weekday control"),
     "notes": "JKM is absent; every reading here is declared a weak-proxy reading"},
    {"id": "PK-I", "title": "The tola gold price, its premium and the smuggling channel",
     "objects": ("the APGJA daily rate", "the premium to LBMA x interbank",
                 "seizure reports", "the Eid and wedding calendar"),
     "conditions": ("the import-restriction regime", "the kerb premium state",
                    "the season"),
     "instruments": ("XAUUSD",),
     "controls": ("the Indian retail premium (the larger neighbour's same measure)",
                  "the Dubai retail premium", "the matched non-festival windows on gold"),
     "notes": "the premium measures stress; the executable leg is global gold"},
    {"id": "PK-J", "title": "Bilateral deposits, Eurobonds and the default-risk calendar",
     "objects": ("the Saudi, UAE and SAFE deposit maturities", "the Eurobond/Sukuk maturities",
                 "the 2022-23 CDS episode", "the rollover announcements"),
     "conditions": ("whether an IMF Board date was pending", "the reserves level in weeks of "
                    "imports", "the era"),
     "instruments": ("USDINR", "XAUUSD", "USDCNH"),
     "controls": ("Egypt's and Sri Lanka's rollover and restructuring dates on the same "
                  "instruments, separating 'a frontier sovereign' from 'Pakistan'",
                  "the same window on non-maturity days", "a randomised-date null"),
     "notes": "binary, dated events; the expected result is no executable move"},
    {"id": "PK-K", "title": "The PSX foreign flow (FIPI) and the frontier-index reviews",
     "objects": ("daily FIPI by category", "the MSCI Frontier review dates",
                 "the programme-approval rallies", "the 2021 EM-to-Frontier demotion"),
     "conditions": ("the sign of the five-day FIPI sum", "review month or not",
                    "the rupee stress state"),
     "instruments": ("US500", "USDINR"),
     "controls": ("the Vietnam and Bangladesh frontier flows on the same dates",
                  "the same window with FIPI shuffled in time (block permutation)",
                  "the LIPI mutual-fund line as the domestic counterpart"),
     "notes": "the KSE-100 is a target, not an instrument; the flow is the object"},
    {"id": "PK-L", "title": "The moon-sighting holiday clock and announced-date liquidity",
     "objects": ("the announced Eid, Ashura and Milad closures", "the projected dates",
                 "the extension decisions", "Ramadan trading hours"),
     "conditions": ("announced vs projected date", "whether the block was extended",
                    "whether the sighting aligned with Saudi Arabia"),
     "instruments": ("XAUUSD", "USDINR"),
     "controls": ("the projected dates that were NOT holidays, as the placebo",
                  "the Indian and Bangladeshi Eid closures on the same days",
                  "the matched weekday control on the same instruments"),
     "notes": "the pack's own calendar; the announced rows are the sample"},
    {"id": "PK-M", "title": "CPEC, the yuan swap line and China settlement",
     "objects": ("the swap-line usage", "the CPEC loan rollovers", "the yuan-settled trade "
                 "share", "the power-project receivables"),
     "conditions": ("whether an IMF financing-assurance window was open", "the era"),
     "instruments": ("USDCNH", "USDINR"),
     "controls": ("other Belt-and-Road rollover dates on USDCNH", "non-event days",
                  "the matched control"),
     "notes": "recorded as weak; the pack expects and reports an absent executable effect"},
)

# --------------------------------------------------------------------------- the pack's miners
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    {"name": "pk_sbp_decision_windows", "domain_ids": ("PK-A",), "kind": "event",
     "cadence_s": 86400.0, "steerable": False, "wired": False,
     "entry": "countries.pk.miners:sbp_decision_windows",
     "needs": ("CENTRAL_BANK decision dates", "USDINR, XAUUSD, US500 H1 bars"),
     "notes": "the decision-day study with the matched weekday control and the era split"},
    {"name": "pk_petrol_fortnight_clock", "domain_ids": ("PK-D",), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.pk.miners:petrol_fortnight_clock",
     "needs": ("the 1st/16th notification calendar", "XBRUSD, XTIUSD H1 bars"),
     "notes": "an input-direction mechanism measured honestly; the 8th/23rd placebo is built in"},
    {"name": "pk_moon_sighting_holidays", "domain_ids": ("PK-L", "PK-E"), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.pk.miners:moon_sighting_holidays",
     "needs": ("the announced holiday rows", "XAUUSD, USDINR H1 bars"),
     "notes": "announced dates only; projected dates form the placebo"},
    {"name": "pk_softs_trade_transmission", "domain_ids": ("PK-F", "PK-G"), "kind": "macro",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.pk.miners:softs_trade_transmission",
     "needs": ("PCGA arrivals and TCP tender dates", "COTTON, WHEAT, SUGAR D1 bars"),
     "notes": "series lead-lag where the series is on the box; the edges are seeded regardless"},
    {"name": "pk_transmission_seeds", "domain_ids": ("PK-B", "PK-C", "PK-H", "PK-I", "PK-J",
                                                     "PK-K", "PK-M"), "kind": "transfer",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.pk.miners:transmission_seeds",
     "needs": ("TRANSMISSION_EDGES_SEED",),
     "notes": "the pack's map as HYPOTHESIS discoveries, deduplicated by the registry"},
)
MINER_DOMAINS: dict[str, tuple[str, ...]] = {
    "central_bank_surprise": ("PK-A",), "release_surprise": ("PK-D", "PK-E"),
    "calendar_settlement": ("PK-D", "PK-J"), "holiday_liquidity": ("PK-L",),
    "positioning": ("PK-K",), "carry_funding": ("PK-C",), "corporate_flow": ("PK-F", "PK-G"),
    "institutional_flow": ("PK-B", "PK-J", "PK-K"), "equity_mechanics": ("PK-K",),
    "derivatives_expiry": ("PK-K",), "failure": ("PK-D", "PK-H", "PK-M"),
    "residual": ("PK-C", "PK-I"), "transfer": ("PK-F", "PK-G"), "scouts": ("PK-C", "PK-L"),
}

# --------------------------------------------------------------------------- transmission
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    {"id": "PK-E1", "source": "PCGA fortnightly cotton arrivals below the prior year",
     "target": "COTTON", "targets": ("COTTON",), "to_country": "global", "sign": "+",
     "mechanism": "a short domestic crop turns Pakistan into one of the largest cotton "
                  "importers in the world for the season; the import contracts reach ICE",
     "horizon": "2 to 20 weeks", "horizon_class": "multi_day", "lag_days": 14.0,
     "actor": "APTMA textile mills", "constraint": "the mills must run on imported lint",
     "flow": "import demand", "condition": "arrivals shortfall above 15% at mid-season and an "
                                          "open LC regime",
     "control": "Indian CCI arrivals in the same fortnights; normal-crop years",
     "falsifier": "a shortfall year without a rise in USDA's import forecast and the ICE-KCA "
                  "spread", "evidence": "HYPOTHESIS"},
    {"id": "PK-E2", "source": "EU and US apparel demand through GSP+ (textile export orders)",
     "target": "EURUSD", "targets": ("EURUSD", "COTTON"), "to_country": "global", "sign": "+",
     "mechanism": "the export orders set the mills' cotton import need and the dollar earnings "
                  "the SBP counts on; a strong euro raises the GSP+ margin",
     "horizon": "1 to 3 months", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "APTMA", "constraint": "GSP+ status", "flow": "export orders",
     "condition": "conditioned on EU retail sales", "control": "Bangladesh's RMG export print",
     "falsifier": "PBS textile exports carry no information about COTTON beyond the crop",
     "evidence": "HYPOTHESIS"},
    {"id": "PK-E3", "source": "TCP wheat import tender awards", "target": "WHEAT",
     "targets": ("WHEAT",), "to_country": "global", "sign": "+",
     "mechanism": "a 0.3-0.5 mt award is Black Sea demand the CBOT contract reads through the "
                  "export basis", "horizon": "0 to 5 sessions", "horizon_class": "multi_day",
     "lag_days": 1.0, "actor": "TCP", "constraint": "the harvest shortfall",
     "flow": "state import", "condition": "an import programme year (2023), not a ban year (2024)",
     "control": "GASC tender windows; non-tender days",
     "falsifier": "the tender window matches the matched-weekday control",
     "evidence": "HYPOTHESIS"},
    {"id": "PK-E4", "source": "The wheat support price and the April-May harvest estimate",
     "target": "WHEAT", "targets": ("WHEAT",), "to_country": "global", "sign": "-",
     "mechanism": "a large harvest removes a swing importer for the year", "horizon": "1 to 3 "
                  "months", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "PASSCO and the provinces", "constraint": "the procurement target",
     "flow": "import need", "condition": "harvest estimate vs the 27-28 mt norm",
     "control": "India's harvest estimate on the same dates",
     "falsifier": "no relation between the harvest surprise and USDA's Pakistan import line",
     "evidence": "HYPOTHESIS"},
    {"id": "PK-E5", "source": "ECC sugar export permission", "target": "SUGAR",
     "targets": ("SUGAR", "SUGARRAW"), "to_country": "global", "sign": "-",
     "mechanism": "a 0.5-1 mt export quota is regional supply into Afghanistan and Central "
                  "Asia and, at the margin, the world raw market", "horizon": "0 to 10 sessions",
     "horizon_class": "multi_day", "lag_days": 1.0, "actor": "PSMA mills and the ECC",
     "constraint": "the domestic stock position", "flow": "export quota",
     "condition": "a surplus year", "control": "India's export policy dates on SUGAR",
     "falsifier": "the permission window matches the matched control",
     "evidence": "HYPOTHESIS"},
    {"id": "PK-E6", "source": "Soybean import clearance (the 2022-23 GMO port hold-up and its "
                              "resolution)", "target": "SOYBEAN", "targets": ("SOYBEAN",),
     "to_country": "global", "sign": "+",
     "mechanism": "Pakistan's 1.5-2 mt of soybean imports feed the poultry industry; a "
                  "clearance regime change is a demand step",
     "horizon": "1 to 3 months", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "the feed mills and customs", "constraint": "the GMO approval regime",
     "flow": "import demand", "condition": "regime change dates only",
     "control": "Bangladesh's soybean import line", "falsifier": "USDA's Pakistan oilseed "
                                                                "import forecast does not move",
     "evidence": "HYPOTHESIS"},
    {"id": "PK-E7", "source": "The Eid remittance peak and the Sarafa demand", "target": "XAUUSD",
     "targets": ("XAUUSD",), "to_country": "global", "sign": "+",
     "mechanism": "part of the Eid-month remittance excess reaches the gold market; the "
                  "regional festive window (Pakistan, India, the Gulf) is a demand season",
     "horizon": "the two weeks into Eid", "horizon_class": "multi_day", "lag_days": 0.0,
     "actor": "overseas Pakistanis and the Sarafa", "constraint": "the lunar calendar",
     "flow": "retail demand", "condition": "kerb premium below Rs 5",
     "control": "the same lunar windows in high-premium years; Diwali windows",
     "falsifier": "the Eid window on gold matches the matched non-Eid months",
     "evidence": "HYPOTHESIS"},
    {"id": "PK-E8", "source": "PLL/PSO spot LNG tender awards", "target": "XNGUSD",
     "targets": ("XNGUSD", "XBRUSD"), "to_country": "global", "sign": "+",
     "mechanism": "a South Asian spot buyer's tender is JKM demand; Henry Hub is only a weak "
                  "proxy and this edge says so", "horizon": "0 to 5 sessions",
     "horizon_class": "multi_day", "lag_days": 1.0, "actor": "PLL / PSO",
     "constraint": "the dollar release", "flow": "spot cargo demand",
     "condition": "an awarded tender, not a no-bid one", "control": "Petrobangla tender windows",
     "falsifier": "no move on XNGUSD beyond the matched control (the expected result)",
     "evidence": "HYPOTHESIS"},
    {"id": "PK-E9", "source": "CPEC loan rollovers and yuan swap-line usage", "target": "USDCNH",
     "targets": ("USDCNH",), "to_country": "cn", "sign": "+",
     "mechanism": "a rollover settled in yuan is marginal yuan demand; negligible and recorded "
                  "as such", "horizon": "0 to 5 sessions", "horizon_class": "multi_day",
     "lag_days": 1.0, "actor": "China's policy banks", "constraint": "the IMF financing "
                                                                       "assurances",
     "flow": "debt rollover", "condition": "rollover announcement dates",
     "control": "other BRI rollover dates", "falsifier": "no measurable move (expected)",
     "evidence": "HYPOTHESIS"},
)

# --------------------------------------------------------------------------- policy eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    {"name": "the 2018 balance-of-payments crisis and the 2019 EFF", "start": "2018-07-01",
     "end": "2020-03-16",
     "regime": "the rupee from 120 to 160, the policy rate to 13.25%, the 2019 EFF",
     "markers": ("2019-05-20 the rupee's free-float week", "2019-07-03 EFF approval"),
     "why_it_matters": "the modern kerb-premium and LC-restriction regime begins here",
     "status": "SETTLED"},
    {"name": "the pandemic easing", "start": "2020-03-17", "end": "2021-09-19",
     "regime": "the policy rate cut from 13.25% to 7% in three months; the programme paused",
     "markers": ("2020-03-17 the first emergency cut", "2020-06-25 the 7% floor"),
     "why_it_matters": "decision surprises are one-sided and large; not exchangeable with the "
                       "scheduled-meeting sample",
     "status": "SETTLED"},
    {"name": "the hiking cycle, the floods and the default scare", "start": "2021-09-20",
     "end": "2023-06-30",
     "regime": "7% to 22%, the 2022 floods, the stalled ninth review, CDS above 100 points, the "
               "kerb premium above Rs 20, the September 2022 to January 2023 administered "
               "interbank rate",
     "markers": ("2022-04-07 emergency +250bp", "2022-08-29 flood emergency",
                 "2023-01-26 the interbank cap released (the rupee fell 10% in two days)",
                 "2023-06-26 emergency +100bp to 22%"),
     "why_it_matters": "the stress channel every domain conditions on is measured here",
     "status": "SETTLED"},
    {"name": "the Stand-By plateau", "start": "2023-07-01", "end": "2024-06-09",
     "regime": "the US$3bn SBA, the policy rate held at 22%, the September 2023 crackdown on the "
               "exchange companies, the February 2024 election",
     "markers": ("2023-07-12 SBA approval", "2023-09-05 the exchange-company crackdown",
                 "2024-02-08 election day"),
     "why_it_matters": "policy surprises are near zero by construction at the plateau; the "
                       "kerb premium's collapse is the era's experiment",
     "status": "SETTLED"},
    {"name": "the 2024 EFF and the easing cycle", "start": "2024-06-10", "end": "2026-12-31",
     "regime": "22% to 11% in twelve months, the 37-month EFF approved 2024-09-25, reserves "
               "rebuilt above US$10bn",
     "markers": ("2024-06-10 the first cut", "2024-09-25 EFF approval",
                 "2025-05-09 the first review completed"),
     "why_it_matters": "the current regime; the decision sample is cuts and holds only",
     "status": "OPEN"},
)

ACCESS_CONSTRAINTS: tuple[dict[str, Any], ...] = (
    {"constraint": "the rupee is not quoted by this broker",
     "measured": "data/universe/universe.json holds no PKR symbol",
     "consequence": "every domestic mechanism terminates in a regional cross, a soft, an energy "
                    "leg or gold; the rupee is an INPUT, never a cell"},
    {"constraint": "the KSE-100 has no CFD and PMEX is not reachable",
     "measured": "no Pakistani index or commodity future is in the universe",
     "consequence": "the NCCPL flow series is the object; the index level is a target"},
    {"constraint": "the SBP announcement minute varies and is not always in the release",
     "measured": "MPC press releases carry a date; the broadcast tickers carry the minute",
     "consequence": "a decision cell is compiled on the broadcast stamp or declared UNMEASURED"},
    {"constraint": "the moon-sighting holidays are known only the evening before",
     "measured": "the Ruet-e-Hilal announcement and the notification follow the sighting",
     "consequence": "PROJECTED dates are never pooled with ANNOUNCED ones; the projected rows "
                    "form the placebo"},
    {"constraint": "Mettis and the terminal vendors forbid machine extraction",
     "measured": "their terms; registered machine_use_allowed=false",
     "consequence": "the intraday interbank tick is UNMEASURED; the SBP close and the ECAP "
                    "posting are the PIT record"},
)
INSTITUTIONAL_FLOW_SOURCES: tuple[str, ...] = (
    "NCCPL FIPI/LIPI daily", "SBP remittances by corridor", "RDA inflows", "MUFAP fund flows",
    "the bilateral deposit rollover announcements")
SERIES: dict[str, str] = {
    "PK_POLICY": "SBP:policy_rate", "PK_RESERVES": "SBP:reserves_weekly",
    "PK_REMIT": "SBP:remittances", "PK_KERB_PREMIUM": "ECAP:kerb_minus_interbank",
    "PK_PETROL": "OGRA:petrol", "PK_COTTON_ARRIVALS": "PCGA:arrivals",
    "PK_FIPI": "NCCPL:fipi_net", "PK_CPI": "PBS:cpi",
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
    """The framework's HolidayRule shape: every closed date the rule produces for 2024-2026."""
    dates = sorted({d.isoformat() for y in HOLIDAYS_RULE["years"] for d in market_holidays(y)})
    return {"dates": tuple(dates), "fixed_md": tuple(f"{m:02d}-{d:02d}" for m, d, _ in
                                                      FIXED_NATIONAL),
            "weekly_closed": (5, 6), "notes": HOLIDAYS_RULE["authority"]}


def lab_kwargs() -> dict[str, Any]:
    """The keyword set `country_lab.CountryPack` is built from, in the shapes its coercion
    reads best: sources as rows AND as tagged lines, positioning and miners as strings, the
    holiday rule as dates, absent layers as a mapping."""
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
