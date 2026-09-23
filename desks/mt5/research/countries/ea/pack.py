"""THE EURO AREA PACK -- the ECB's one rate, twenty sovereigns' twenty calendars, as data.

WHAT IS IN HERE. Sixteen actors with their eleven fields, fourteen domains A..N with objects,
conditions, instruments and negative controls, four sub-labs (DE/FR/IT/ES) with their own debt
agencies and political calendars, the euro-area dataset catalogue with all six point-in-time
stamps on every row, twelve transmission edges naming real Fusion symbols, the ECB policy eras
back to the sovereign crisis, and TWO holiday calendars that deliberately disagree.

THREE MEASURED FACTS THIS PACK CARRIES THAT A DOCUMENT WOULD HAVE GOT WRONG.

  * EURRUB IS IN THE BROKER REGISTRY AND HAS NO BARS AFTER 2022-02-28 (measured on this box's own
    parquet, 2026-09-17). It is registry-present and DEAD. It is therefore NOT in
    `EXECUTABLE_INSTRUMENTS`: a symbol whose quote stopped is not a tradable instrument, and a
    pack that listed it would hand a miner a cell it can never fill.
  * THE INDEX BARS START 2020-09-14 AND THE FX MAJORS START 2018-01-02 (same measurement). So the
    APP era, the negative-deposit-rate decision and the whole 2015-2019 regime are NOT testable on
    this box's own bars. Every era row carries `bars` saying so by name, because an era study the
    desk cannot run is a gate that never runs (L1.49).
  * TTF IS NOT A FUSION SYMBOL. The euro area's defining shock of 2021-2023 arrived through Dutch
    TTF gas and the desk cannot trade it. It is named in `TRANSMISSION_TARGETS` and routed into
    GER40/EURUSD, with XNGUSD (Henry Hub) used as a CONTROL rather than a proxy -- the two gas
    benchmarks decoupled by a factor of ten in 2022 and a study that swapped one for the other
    would have measured the LNG arbitrage, not the European shock.

THE BOUNDARIES. No single-name equity is executable or hunted (two-lane order 2026-09-06); no
crypto-exchange ground is touched (mandate 2026-08-18); nothing here allocates capital. Every
calendar is DERIVED from its rule by a function in this module rather than typed, so 2027 is one
call away and a typo in 2025 cannot survive the test.
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta
from typing import Any

from countries import actor, build_pack, dataset, domain, edge, era, miner, source_class

CODE = "EA"
NAME = "Euro area"
REGION_COMMAND = "EUROPE"
CURRENCY = "EUR"

#: EVERY MEMBER OF THE MONETARY UNION THIS PACK ANSWERS FOR (added 2026-09-23).
#:
#: `scripts/check_regional_parity.py::jurisdictions_of` reads this tuple and credits the pack
#: with every country in it; a multi-jurisdiction pack that declares nothing is credited with
#: exactly ONE, which is why eleven euro-area members sat on the fence's UNANSWERED list while
#: this pack was already the department that covers them. The fence said so in its own words --
#: "the euro-area pack covers eleven members and declares none of them" -- and the fix it named
#: is this tuple.
#:
#: DECLARING ALL TWENTY IS THE HONEST READING, not an inflation, and the distinction that makes
#: it honest is `JURISDICTION_DEPTH` below. The ECB's single monetary policy, the single
#: settlement system, the single HICP construction, the single Governing Council calendar and
#: the single currency ARE the mechanism for all twenty members equally: a rate decision binds
#: Malta exactly as it binds Germany, and there is no second euro. What differs is the FISCAL
#: and political plane, which is national -- and this pack carries a sub-lab for the five that
#: move the price and says plainly that the other fifteen are covered by the monetary plane
#: alone. A reader who needs to know which is which reads one dict rather than guessing.
JURISDICTIONS: tuple[str, ...] = (
    "at", "be", "cy", "de", "ee", "es", "fi", "fr", "gr", "hr",
    "ie", "it", "lt", "lu", "lv", "mt", "nl", "pt", "si", "sk")

#: The sub-labs this pack carries inside it. The euro area is one monetary authority and four
#: fiscal ones that matter for price; each keeps its own calendar, agency and language.
SUB_LAB_CODES: tuple[str, ...] = ("de", "fr", "it", "es", "nl")

#: WHAT EACH DECLARED JURISDICTION ACTUALLY GETS FROM THIS PACK. `SUB_LAB` means a national
#: fiscal plane of its own -- debt agency, auction calendar, political clock, national language
#: terminology. `MONETARY_PLANE` means the ECB's single policy, settlement, HICP and calendar and
#: nothing national: an honest statement that the country is covered where the mechanism is
#: common and NOT covered where it is national. A member that later earns a sub-lab moves rows
#: here rather than appearing from nowhere.
JURISDICTION_DEPTH: dict[str, str] = {
    **dict.fromkeys(("de", "fr", "it", "es", "nl"), "SUB_LAB"),
    **dict.fromkeys(("at", "be", "cy", "ee", "fi", "gr", "hr", "ie",
                     "lt", "lu", "lv", "mt", "pt", "si", "sk"), "MONETARY_PLANE"),
}

#: The six point-in-time stamps every dataset row must be able to answer (region mandate s21).
PIT_STAMPS: tuple[str, ...] = ("event_time", "period_time", "publication_time", "available_time",
                               "revision_time", "retrieval_time")

#: Every euro-denominated or euro-area symbol the box can actually quote TODAY. Checked against
#: `desks/mt5/data/universe/universe.json` by `countries.check_pack`; no equity may appear here.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    # the euro complex
    "EURUSD", "EURGBP", "EURJPY", "EURCHF", "EURAUD", "EURCAD", "EURNZD",
    # the euro against the European periphery of currencies
    "EURSEK", "EURNOK", "EURDKK", "EURPLN", "EURCZK", "EURHUF", "EURTRY",
    # the euro against the rest
    "EURSGD", "EURHKD", "EURMXN", "EURZAR", "EURILS",
    # the four cash indices the broker quotes for euro-area blocs
    "GER40", "FRA40", "E35", "NETH25", "EUSTX50",
    # euro-denominated metal, and the dollar side of every euro trade
    "XAUEUR", "XAGEUR", "XAUUSD", "USDX",
    # the energy legs the euro-area shock is routed through
    "XBRUSD", "XNGUSD",
)

#: Registry-present and DEAD. Measured on this box 2026-09-17: the parquet's last H1 bar is
#: 2022-02-28 and the quote never resumed. Named here so a future session does not rediscover it.
DEAD_QUOTES: tuple[dict[str, str], ...] = (
    {"symbol": "EURRUB", "last_bar": "2022-02-28",
     "why": "quotation ceased with the sanctions regime; the registry row survives the feed",
     "consequence": "never executable; any EUR/RUB mechanism must be routed through USDRUB, "
                    "whose bars do continue, or declared UNMEASURED"},
)

#: What the euro area's economics run through that Fusion does not quote. Named, never dropped:
#: absence is recorded and routed (L1.28a), and every one of these is the SOURCE side of an edge.
TRANSMISSION_TARGETS: tuple[dict[str, str], ...] = (
    {"name": "Euro-Bund future (FGBL)", "venue": "Eurex",
     "role": "the euro area's risk-free duration anchor; the 10y Bund yield is the level every "
             "euro-area spread is quoted against",
     "route": "GER40, EURUSD, EURCHF; the bond leg itself is unavailable"},
    {"name": "Euro-BTP future (FBTP) and the BTP-Bund 10y spread", "venue": "Eurex",
     "role": "the price of euro-area redenomination risk; the single most-watched European risk "
             "observable and the one Italian retail quotes by name (lo spread)",
     "route": "E35, FRA40, EURUSD, EURCHF -- periphery stress is a EUR-negative, CHF-positive"},
    {"name": "Euro-OAT future (FOAT)", "venue": "Eurex",
     "role": "French duration; the OAT-Bund spread is the French political risk observable",
     "route": "FRA40, EURUSD"},
    {"name": "Euro-Schatz (FGBS) and Euro-Bobl (FGBM)", "venue": "Eurex",
     "role": "the 2y and 5y points where an ECB repricing shows up first",
     "route": "EURUSD, EURCHF"},
    {"name": "Dutch TTF natural gas", "venue": "ICE Endex",
     "role": "THE euro-area energy shock channel 2021-2023; the terms-of-trade shock that moved "
             "EURUSD below parity ran through this contract and not through crude",
     "route": "GER40, NETH25, EURUSD; XNGUSD is a CONTROL for it, never a proxy"},
    {"name": "EUA (EU ETS carbon allowance)", "venue": "ICE Endex / EEX",
     "role": "the carbon cost inside every euro-area industrial margin and power price",
     "route": "GER40, EUSTX50"},
    {"name": "German power baseload (Phelix)", "venue": "EEX",
     "role": "the price at which the German industrial base decides to run or idle",
     "route": "GER40"},
    {"name": "3M Euribor and ESTR futures", "venue": "ICE / Eurex",
     "role": "the market-implied ECB path; the only way to separate a decision from a surprise",
     "route": "EURUSD, EURCHF, GER40 -- the surprise is the conditioning variable, not the level"},
    {"name": "EUR 10y and 30y interest-rate swap", "venue": "OTC / cleared at LCH and Eurex",
     "role": "the instrument Dutch pension funds actually hold their duration in; the Wtp "
             "transition is a swap-book event before it is a bond-market event",
     "route": "EURUSD, NETH25"},
    {"name": "FTSE MIB", "venue": "Euronext Milan",
     "role": "the Italian equity bloc; ABSENT from the broker universe although GER40, FRA40, "
             "E35 and NETH25 are present, so Italy has no executable index leg on this desk",
     "route": "E35 and EUSTX50 are the nearest executable periphery proxies, and both are "
              "imperfect: E35 is Spanish and EUSTX50 is 40% French"},
    {"name": "EURO STOXX Banks (SX7E)", "venue": "Eurex",
     "role": "the sovereign-bank doom-loop leg; periphery spreads reach equity through it",
     "route": "EUSTX50, E35"},
    {"name": "VSTOXX", "venue": "Eurex",
     "role": "euro-area implied volatility; the regime variable for every index domain here",
     "route": "GER40, EUSTX50"},
)


# --------------------------------------------------------------------------- the calendars
def easter_sunday(year: int) -> date:
    """Gregorian Easter (the anonymous computus). Five of the six T2 closing days hang off it.

    Verified against the desk's own test: 2024-03-31, 2025-04-20, 2026-04-05. Derived rather than
    typed so 2027 costs nothing and a mistyped year cannot survive.
    """
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


def holidays(year: int) -> dict[date, str]:
    """TARGET2/T2 closing days: the euro's own settlement calendar, and only six days long.

    T2 is closed on Saturdays and Sundays and on exactly these six: 1 January, Good Friday, Easter
    Monday, 1 May, 25 December and 26 December. Nothing national closes it -- German Unity Day,
    Bastille Day, Ferragosto and the Spanish Constitution Day all settle normally -- and that
    asymmetry is the research object, not a nuisance.
    """
    e = easter_sunday(year)
    return {
        date(year, 1, 1): "New Year's Day",
        e - timedelta(days=2): "Good Friday",
        e + timedelta(days=1): "Easter Monday",
        date(year, 5, 1): "Labour Day",
        date(year, 12, 25): "Christmas Day",
        date(year, 12, 26): "Christmas holiday (26 December)",
    }


def euronext_holidays(year: int) -> dict[date, str]:
    """Euronext (Paris, Amsterdam, Brussels, Lisbon, Milan) trading holidays.

    Measured coincidence worth knowing: the harmonised Euronext calendar is the SAME six days as
    T2. So FRA40, NETH25 and E35 trade on every day the euro settles, and Xetra does not.
    """
    return dict(holidays(year))


def xetra_holidays(year: int) -> dict[date, str]:
    """Xetra and Eurex trading holidays: the T2 six PLUS Whit Monday, 24 and 31 December.

    This is the euro area's most exploitable calendar asymmetry. On Whit Monday GER40 does not
    trade and FRA40 does; on 24 and 31 December the same. A cross-index spread with a German leg
    has three forced one-sided days a year, and a study that pooled them measured a stub.
    """
    e = easter_sunday(year)
    table = dict(holidays(year))
    table[e + timedelta(days=50)] = "Whit Monday (Pfingstmontag)"
    table[date(year, 12, 24)] = "Christmas Eve (Heiligabend)"
    table[date(year, 12, 31)] = "New Year's Eve (Silvester)"
    return table


def national_holidays(sub_lab: str, year: int) -> dict[date, str]:
    """The NATIONAL public holidays of one sub-lab -- banks and settlement, not the exchange.

    These are the days the local banking system is shut while T2 is open: a domestic corporate
    cannot fund, a domestic auction cannot settle, and the local retail flow is absent while the
    price keeps moving. `holidays()` is the settlement calendar; this is the participation one.
    """
    code = str(sub_lab).lower()
    e = easter_sunday(year)
    common = {
        date(year, 1, 1): "New Year's Day",
        e + timedelta(days=1): "Easter Monday",
        date(year, 5, 1): "Labour Day",
        date(year, 12, 25): "Christmas Day",
    }
    if code == "de":
        return {**common, **{
            e - timedelta(days=2): "Karfreitag (Good Friday)",
            e + timedelta(days=39): "Christi Himmelfahrt (Ascension)",
            e + timedelta(days=50): "Pfingstmontag (Whit Monday)",
            date(year, 10, 3): "Tag der Deutschen Einheit (Unity Day -- XETRA TRADES)",
            date(year, 12, 26): "Zweiter Weihnachtsfeiertag",
        }}
    if code == "fr":
        return {**common, **{
            e - timedelta(days=2): "Vendredi saint (Alsace-Moselle only)",
            date(year, 5, 8): "Victoire 1945",
            e + timedelta(days=39): "Ascension",
            e + timedelta(days=50): "Lundi de Pentecote (Euronext TRADES)",
            date(year, 7, 14): "Fete nationale (Euronext TRADES)",
            date(year, 8, 15): "Assomption (Euronext TRADES)",
            date(year, 11, 1): "Toussaint (Euronext TRADES)",
            date(year, 11, 11): "Armistice 1918 (Euronext TRADES)",
        }}
    if code == "it":
        return {**common, **{
            date(year, 1, 6): "Epifania",
            date(year, 4, 25): "Festa della Liberazione",
            date(year, 6, 2): "Festa della Repubblica",
            date(year, 8, 15): "Ferragosto (market open, liquidity absent)",
            date(year, 11, 1): "Ognissanti",
            date(year, 12, 8): "Immacolata Concezione",
            date(year, 12, 26): "Santo Stefano",
        }}
    if code == "es":
        return {**common, **{
            date(year, 1, 6): "Epifania (Reyes)",
            e - timedelta(days=2): "Viernes Santo",
            date(year, 8, 15): "Asuncion",
            date(year, 10, 12): "Fiesta Nacional (Hispanidad)",
            date(year, 11, 1): "Todos los Santos",
            date(year, 12, 6): "Dia de la Constitucion",
            date(year, 12, 8): "Inmaculada Concepcion",
        }}
    if code == "nl":
        return {**common, **{
            e - timedelta(days=2): "Goede Vrijdag (Euronext closed)",
            date(year, 4, 27): "Koningsdag (Euronext TRADES)",
            e + timedelta(days=39): "Hemelvaartsdag (Euronext TRADES)",
            e + timedelta(days=50): "Tweede Pinksterdag (Euronext TRADES)",
            date(year, 12, 26): "Tweede Kerstdag",
        }}
    raise KeyError(f"unknown euro-area sub-lab {sub_lab!r}; this pack carries {SUB_LAB_CODES}")


def third_friday(year: int, month: int) -> date:
    """The Eurex and Euronext derivatives expiry day. Quadruple witching in Mar/Jun/Sep/Dec."""
    first = date(year, month, 1)
    return date(year, month, 1 + (4 - first.weekday()) % 7 + 14)


def witching_days(year: int) -> dict[date, str]:
    """The four Hexensabbat / quatre sorcieres / le tre streghe / cuadruple hora bruja days."""
    return {third_friday(year, m): "quadruple witching (index and single-stock futures and "
                                   "options expire together)" for m in (3, 6, 9, 12)}


def _iso(table: dict[date, str]) -> dict[str, str]:
    return {d.isoformat(): n for d, n in sorted(table.items())}


HOLIDAYS_RULE: dict[str, Any] = {
    "calendar": "TARGET2 / T2 closing days (the euro's settlement calendar)",
    "rule": "T2 is closed on Saturdays, Sundays, 1 January, Good Friday, Easter Monday, 1 May, "
            "25 December and 26 December, and on no other day. Good Friday and Easter Monday are "
            "derived from the Gregorian computus in `easter_sunday`; the rest are fixed dates and "
            "never shift for a weekend -- there is no substitution rule in T2, so a 1 May on a "
            "Saturday simply costs the euro no settlement day at all.",
    "function": "countries.ea.pack:holidays",
    "table": {y: _iso(holidays(y)) for y in (2024, 2025, 2026)},
    "exchange_tables": {
        "euronext (FRA40, NETH25, E35, Euronext Milan)": {
            y: _iso(euronext_holidays(y)) for y in (2024, 2025, 2026)},
        "xetra / eurex (GER40)": {y: _iso(xetra_holidays(y)) for y in (2024, 2025, 2026)},
    },
    "national_tables": {cc: {y: _iso(national_holidays(cc, y)) for y in (2024, 2025, 2026)}
                        for cc in SUB_LAB_CODES},
    "asymmetries": (
        "Whit Monday, 24 December and 31 December: GER40 closed, FRA40/NETH25/E35 open. Three "
        "forced one-sided days a year in any German-versus-French index spread.",
        "3 October (German Unity Day): a national bank holiday on which Xetra TRADES. German "
        "domestic flow is absent and the index is not.",
        "14 July, 15 August, 1 November, 11 November: French national holidays on which Euronext "
        "Paris trades. Same shape, opposite country.",
        "15 August (Ferragosto): Euronext Milan is open and Italian participation collapses; the "
        "BTP-Bund spread is at its thinnest of the year in the week around it.",
        "No T2 substitution rule: when 1 May or 25/26 December falls on a weekend the euro loses "
        "that closure entirely, so the count of T2 days per year is not constant.",
    ),
    "status": "DERIVED_FROM_RULE",
    "verified": {"2026-04-03": "Good Friday, T2 closed", "2026-04-06": "Easter Monday, T2 closed"},
}

CENTRAL_BANK: dict[str, Any] = {
    "name": "European Central Bank (ECB) / the Eurosystem",
    "committee": "Governing Council (6 Executive Board members + 20 national governors, voting "
                 "on a rotation since 2015)",
    "policy_rates": ("deposit facility rate (DFR) -- the operative rate since 2014",
                     "main refinancing operations rate (MRO)",
                     "marginal lending facility rate (MLF)"),
    "operational_framework": "the corridor. Announced 2024-03-13 and effective 2024-09-18, the "
                             "MRO-DFR spread was narrowed from 50bp to 15bp and the MLF-MRO "
                             "spread set at 25bp. That is a REGIME BREAK in every study that "
                             "uses MRO as the policy rate: the same policy stance produces a "
                             "different MRO print on either side of 2024-09-18.",
    "decision_rule": "eight scheduled monetary policy meetings a year, roughly every six weeks; "
                     "non-monetary-policy Governing Council meetings sit between them and do not "
                     "move rates but do decide on instruments (TPI activation would be one).",
    "announcement_local": "14:15 CET/CEST",
    "announcement_utc": {"winter_cet": "13:15Z", "summer_cest": "12:15Z"},
    "press_conference_local": "14:45 CET/CEST",
    "dst_note": "the ECB publishes in LOCAL Frankfurt time and never in UTC. CET = UTC+1 from the "
                "last Sunday in October to the last Sunday in March; CEST = UTC+2 otherwise. An "
                "event study keyed to a fixed UTC hour is wrong for seven months of every year, "
                "and the EU's 'abolish DST' directive has never been implemented, so the rule "
                "still holds as of 2026-09-17.",
    "time_change_note": "the announcement moved from 13:45 CET (press conference 14:30 CET) to "
                        "14:15 CET (press conference 14:45 CET) from 2022. Any intraday study "
                        "spanning that boundary is pooling two different clocks. Confidence: "
                        "declared from public knowledge; re-read the ECB press calendar before "
                        "running a pre-2022 window.",
    "accounts": "the 'account' of each monetary policy meeting is published about four weeks "
                "later, 13:30 CET -- a second, smaller event on the same mechanism",
    "projections": "Eurosystem staff macroeconomic projections at the March, June, September and "
                   "December meetings; ECB staff projections at the other four. The projection "
                   "meetings carry systematically larger rate-path revisions.",
    "decisions": {
        "2024": {"dates": ("2024-01-25", "2024-03-07", "2024-04-11", "2024-06-06", "2024-07-18",
                           "2024-09-12", "2024-10-17", "2024-12-12"),
                 "confidence": "high -- these are the eight published 2024 policy meetings"},
        "2025": {"dates": ("2025-01-30", "2025-03-06", "2025-04-17", "2025-06-05", "2025-07-24",
                           "2025-09-11", "2025-10-30", "2025-12-18"),
                 "confidence": "high -- these are the eight published 2025 policy meetings"},
        "2026": {"dates": ("2026-02-05", "2026-03-19", "2026-04-30", "2026-06-11", "2026-07-23",
                           "2026-09-10", "2026-10-29", "2026-12-17"),
                 "confidence": "DECLARED, UNVERIFIED. Re-read ecb.europa.eu press calendar before "
                               "any 2026 event study; a wrong date does not degrade the study, it "
                               "inverts it, because the window lands on a non-event day."},
    },
    "rule_if_dates_unknown": "Thursday, roughly every six weeks, never in the first week of "
                             "January and never in August; the projection meetings are the ones "
                             "in the last month of a quarter.",
    "source": "https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html",
}

FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "ECB euro foreign exchange reference rates",
     "administrator": "European Central Bank",
     "local_time": "14:15 CET/CEST concertation; published around 16:00 CET/CEST",
     "utc": {"winter": "13:15Z struck / 15:00Z published",
             "summer": "12:15Z struck / 14:00Z published"},
     "dst_note": "CET=UTC+1 winter, CEST=UTC+2 summer; the switch is the last Sunday of March and "
                 "of October, and it is NOT the same weekend as the US switch -- for two weeks in "
                 "March and one in November the Frankfurt-to-New York offset is one hour off its "
                 "usual value, which is exactly the window a naive UTC-offset backtest breaks in.",
     "window": "a single concertation snapshot, not a window average",
     "conflict": "the ECB's own page states the concertation normally takes place at 14:10 CET; "
                 "the desk's standing note says 14:15 CET. The pack records BOTH rather than "
                 "picking: both sit inside one five-minute bar, so an H1-bar study is unaffected "
                 "and a tick-level study must resolve it from the source first.",
     "what_it_prices": "the euro against 30-odd currencies, used for accounting, tax, statistics "
                       "and a large volume of corporate invoicing",
     "why_it_matters": "it is the only euro fix a EURO-AREA CORPORATE is contractually exposed to; "
                       "the 16:00 London WMR fix is the one an INDEX FUND is exposed to. Two "
                       "different forced participants, two different times of day."},
    {"name": "WM/Refinitiv 16:00 London closing spot rate",
     "administrator": "LSEG (WM/Refinitiv)",
     "local_time": "16:00 London",
     "utc": {"winter": "16:00Z", "summer": "15:00Z"},
     "dst_note": "London is GMT=UTC in winter and BST=UTC+1 in summer, switching on the last "
                 "Sunday of March and October -- the SAME weekends as the euro area, so the "
                 "London-Frankfurt offset is a constant one hour all year. It is the London-to-US "
                 "offset that breaks, not this one.",
     "window": "a five-minute window 15:57:30-16:02:30 London, median of sampled rates",
     "what_it_prices": "the benchmark every global equity and bond index uses to convert",
     "why_it_matters": "month-end index rebalancing is mechanically forced INTO this window; the "
                       "euro-area leg is the largest non-dollar leg of it."},
    {"name": "EURIBOR",
     "administrator": "European Money Markets Institute (EMMI)",
     "local_time": "determined 10:45 CET/CEST, published 11:00 CET/CEST",
     "utc": {"winter": "10:00Z published", "summer": "09:00Z published"},
     "dst_note": "CET/CEST as above. EURIBOR is published on TARGET2 days only, so its series has "
                 "exactly the six-day-a-year holes `holidays()` computes and a daily-frequency "
                 "join against a US series must be an outer join or it silently drops them.",
     "window": "panel contributions, trimmed mean",
     "what_it_prices": "term unsecured euro funding, 1w to 12m; the reference in most euro-area "
                       "floating mortgages, which is how an ECB decision reaches a Spanish or "
                       "Italian household budget",
     "why_it_matters": "the 12m EURIBOR is the Spanish mortgage reset reference; its monthly "
                       "average is a dated, published, forced-flow observable"},
    {"name": "EUR short-term rate (ESTR)",
     "administrator": "European Central Bank",
     "local_time": "08:00 CET/CEST on the following TARGET2 day",
     "utc": {"winter": "07:00Z", "summer": "06:00Z"},
     "dst_note": "CET/CEST; T2 days only. ESTR for a Friday appears on the following Monday, and "
                 "over a T2 closure the gap is longer -- an alignment bug that shows up as a "
                 "spurious jump every Easter.",
     "window": "volume-weighted trimmed mean of the prior day's unsecured overnight borrowing",
     "what_it_prices": "the actual overnight euro rate the DFR is supposed to anchor",
     "why_it_matters": "ESTR minus DFR is the euro-area excess-liquidity observable; it drifted "
                       "as the PEPP and TLTRO stock ran off and is the cleanest measure of when "
                       "the corridor started to bind"},
    {"name": "LBMA Gold Price (the London fix)",
     "administrator": "ICE Benchmark Administration",
     "local_time": "10:30 and 15:00 London",
     "utc": {"winter": "10:30Z and 15:00Z", "summer": "09:30Z and 14:00Z"},
     "dst_note": "London clock; both fixes move with BST. XAUEUR inherits BOTH this London clock "
                 "and the EURUSD leg's Frankfurt clock, so its intraday seasonality is the "
                 "convolution of two calendars and cannot be read off either alone.",
     "window": "an electronic auction with price rounds until imbalance is inside a tolerance",
     "what_it_prices": "the settlement price for the overwhelming majority of physical gold",
     "why_it_matters": "XAUEUR and XAGEUR are EUR-quoted metal; a euro-area shock reaches them "
                       "through the EUR leg while the metal leg is fixed on London's clock"},
)

SETTLEMENT_CONVENTIONS: dict[str, Any] = {
    "fx_spot": "T+2 for EURUSD and the euro crosses; value date must be a good business day in "
               "BOTH currencies, so a T2 closure and a US holiday each push the date and a "
               "Good Friday pushes it twice",
    "fx_value_date_note": "EURUSD spot struck on the Wednesday before Good Friday values on the "
                          "Tuesday after Easter Monday -- a four-calendar-day carry in one tick "
                          "of the swap points, and the single largest predictable jump in the "
                          "EUR overnight forward of the year",
    "cls": "EUR, GBP, CHF, SEK, NOK, DKK and HUF settle in CLS; PLN and CZK do not. The CEE pack "
           "carries the consequence: a Polish or Czech FX settlement carries Herstatt risk that "
           "a euro one does not, and it is priced in the basis.",
    "cash_equity_and_index": "T+2 across the EU today. The EU, the UK and Switzerland have all "
                             "targeted 11 October 2027 for the move to T+1 (declared; verify "
                             "against ESMA before pricing anything off it). A T+1 move changes "
                             "every month-end FX hedging deadline by one business day, so every "
                             "month-end study has a scheduled structural break in 2027.",
    "bonds": "T+2 for euro-area govvies through Euroclear/Clearstream; auction settlement is "
             "typically T+2 to T+3 from the auction date and is published in the agency's own "
             "calendar rather than inferred",
    "eurex_derivatives": "cash-settled index futures and options settle T+1 against the venue's "
                         "own settlement price; the settlement price rule differs per index and "
                         "is recorded per exchange in EXCHANGES below",
    "month_end": "the last T2 business day is the index-rebalancing value date; the hedging flow "
                 "is struck two business days earlier because spot is T+2. A study that puts "
                 "month-end flow ON the last day of the month is one to two days late.",
}

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Eurex (Deutsche Boerse)", "mic": "XEUR", "tz": "Europe/Berlin",
     "symbols": ("GER40", "EUSTX50"),
     "session_local": "01:10-22:00 CET for index futures; the cash Xetra session is 09:00-17:30",
     "expiry_rule": "third Friday of the expiry month, monthly for options and Mar/Jun/Sep/Dec "
                    "for the quarterly futures cycle",
     "settlement_price_rule": "the DAX final settlement price is the price from the INTRADAY "
                              "AUCTION on Xetra at 13:00 CET on the third Friday -- not the "
                              "close. EURO STOXX 50 settles on the average of index values "
                              "between 11:50 and 12:00 CET. Two different euro-area indices, two "
                              "different settlement mechanics, four hours apart.",
     "witching": "Hexensabbat: the quadruple witching of March, June, September and December, "
                 "when index futures, index options, single-stock futures and single-stock "
                 "options all expire. German retail names the day itself.",
     "notes": "GER40 is closed on Whit Monday, 24 and 31 December when FRA40 is open"},
    {"name": "Euronext Paris", "mic": "XPAR", "tz": "Europe/Paris",
     "symbols": ("FRA40",),
     "session_local": "09:00-17:30 CET continuous, closing auction 17:30-17:35",
     "expiry_rule": "third Friday of the expiry month",
     "settlement_price_rule": "CAC 40 futures and options settle on the ARITHMETIC MEAN of the "
                              "index taken between 15:40 and 16:00 CET on the expiry day. "
                              "Confidence: declared from public knowledge; verify against the "
                              "Euronext contract specification before trading the print.",
     "witching": "les quatre sorcieres, the same four months",
     "notes": "Euronext's harmonised holiday calendar is the same six days as T2"},
    {"name": "Euronext Amsterdam", "mic": "XAMS", "tz": "Europe/Amsterdam",
     "symbols": ("NETH25",),
     "session_local": "09:00-17:30 CET continuous, closing auction 17:30-17:35",
     "expiry_rule": "third Friday of the expiry month",
     "settlement_price_rule": "AEX index derivatives settle on the average of index values in a "
                              "window at the end of the expiry session. Confidence: declared; "
                              "verify the exact window against the Euronext specification.",
     "witching": "the same four months",
     "notes": "the AEX is the most concentrated of the four euro-area indices the desk quotes; a "
              "single-name event in it is an index event, which is precisely why NETH25 is a "
              "TRANSMISSION target for single-name news and never a hypothesis ground"},
    {"name": "BME / Bolsa de Madrid", "mic": "XMAD", "tz": "Europe/Madrid",
     "symbols": ("E35",),
     "session_local": "09:00-17:30 CET continuous, closing auction 17:30-17:35",
     "expiry_rule": "third Friday of the expiry month (MEFF)",
     "settlement_price_rule": "IBEX 35 futures settle on the arithmetic mean of the index between "
                              "16:15 and 16:45 CET on the expiry day. Confidence: declared; "
                              "verify against the MEFF specification.",
     "witching": "el vencimiento trimestral / la cuadruple hora bruja",
     "notes": "E35 is Spain; the euro area has NO executable Italian index on this desk"},
    {"name": "Euronext Milan (ex Borsa Italiana)", "mic": "MTAA", "tz": "Europe/Rome",
     "symbols": (),
     "session_local": "09:00-17:30 CET",
     "expiry_rule": "third Friday (IDEM)",
     "settlement_price_rule": "FTSE MIB settles on the opening auction prices of the constituents "
                              "on the third Friday. Confidence: declared.",
     "witching": "le tre streghe",
     "notes": "NO EXECUTABLE SYMBOL. FTSE MIB is absent from the broker universe and is carried "
              "in TRANSMISSION_TARGETS; Italian equity risk reaches this desk only through "
              "EUSTX50, E35 and the euro itself."},
)

POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "CFTC Commitments of Traders -- Euro FX (CME contract 6E)",
     "covers": "EUR", "published": "Friday 15:30 ET for Tuesday's positions",
     "lag_days": 3.0, "licence": "public domain (US government)",
     "root": "https://www.cftc.gov/MarketReports/CommitmentsofTraders/",
     "note": "both the legacy report and the Traders in Financial Futures (TFF) breakdown exist "
             "for EUR; TFF's leveraged-funds line is the one that behaves like a speculator "
             "series. The Tuesday snapshot means a Wednesday-to-Friday move is invisible until "
             "the following week -- the standing point-in-time trap in every COT study."},
    {"name": "CFTC Commitments of Traders -- British Pound and Swiss Franc",
     "covers": "GBP, CHF", "published": "Friday 15:30 ET for Tuesday's positions",
     "lag_days": 3.0, "licence": "public domain",
     "root": "https://www.cftc.gov/MarketReports/CommitmentsofTraders/",
     "note": "carried here because a euro-area risk episode is normally a EUR-down/CHF-up pair "
             "trade, and the CHF line is the cleaner of the two for measuring the safe-haven leg"},
    {"name": "NO COT FOR THE EUROPEAN PERIPHERY OF CURRENCIES -- declared absence",
     "covers": "SEK, NOK, DKK, PLN, CZK, HUF: NONE of these has a CFTC-reportable futures "
               "contract with a meaningful position series",
     "published": "never", "lag_days": 0.0, "licence": "n/a",
     "root": "n/a",
     "note": "This is a DECLARED GAP, not an oversight. Any Nordic or CEE crowding hypothesis on "
             "this desk is UNMEASURED on positioning and must say so (L1.28a); the substitutes "
             "are the BIS Triennial (three-yearly, useless for timing) and the local central "
             "bank's own foreign-holdings statistic, which is monthly and lagged."},
    {"name": "Eurex daily open interest and the large-position statistics",
     "covers": "GER40 (FDAX/FESX complex), EUSTX50", "published": "daily, T+1 morning CET",
     "lag_days": 1.0, "licence": "public on the exchange site, redistribution restricted",
     "root": "https://www.eurex.com/ex-en/data/statistics",
     "note": "the only DAILY euro-area positioning series that exists; open interest by strike "
             "around the third Friday is the raw material of every gamma-pinning hypothesis"},
    {"name": "ECB Securities Holdings Statistics (SHS) by sector",
     "covers": "who in the euro area holds which sovereign bond, by holder sector and country",
     "published": "quarterly, roughly four months after the reference quarter",
     "lag_days": 120.0, "licence": "public (ECB Data Portal)",
     "root": "https://data.ecb.europa.eu/",
     "note": "far too slow to time anything and exactly right for establishing WHO the forced "
             "holder of a periphery bond is -- which is the actor question, not the timing one"},
    {"name": "ESMA net short position register",
     "covers": "disclosed net short positions in EU shares and sovereign debt",
     "published": "daily by each national competent authority",
     "lag_days": 1.0, "licence": "public",
     "root": "https://www.esma.europa.eu/",
     "note": "the sovereign-debt half is the interesting one here; the share half is equity "
             "ground and the two-lane order forbids mining it for hypotheses"},
)

NATIVE_LANGUAGES: tuple[str, ...] = ("de", "fr", "it", "es", "nl", "en")

#: Native market vocabulary, keyed by domain then language. A miner reading wallstreet-online for
#: "rate decision" finds nothing; it must ask for "Zinsentscheid". This table is the only part of
#: a pack that CANNOT be written in English, and it is written with its real diacritics on
#: purpose -- an accent-folded term does not match the source it exists to match.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "de_policy": ("EZB-Zinsentscheid", "Leitzins", "Einlagesatz", "Einlagefazilität",
                  "Hauptrefinanzierungssatz", "Zinsschritt", "Pressekonferenz", "Protokoll",
                  "geldpolitische Straffung", "Bilanzabbau", "Anleihekaufprogramm"),
    "de_rates": ("Bundesanleihe", "Bund-Rendite", "Umlaufrendite", "Emissionskalender",
                 "Aufstockung", "Bietungsverhältnis", "Auktion", "Zinsstrukturkurve",
                 "Bundesschatzanweisung", "Finanzagentur"),
    "de_market": ("Hexensabbat", "Verfallstag", "grosser Verfall", "Xetra-Schlussauktion",
                  "Schlusskurs", "Tagesgeld", "Dividendenabschlag", "Leerverkauf",
                  "Handelsschluss", "Feiertagsbörse"),
    "de_macro": ("Ifo-Geschäftsklimaindex", "ZEW-Konjunkturerwartungen", "Einkaufsmanagerindex",
                 "Verbraucherpreisindex", "Erzeugerpreise", "Auftragseingänge",
                 "Industrieproduktion", "Schuldenbremse", "Sondervermoegen", "Gasspeicherstand"),
    "fr_policy": ("BCE", "taux directeur", "taux de dépôt", "conseil des gouverneurs",
                  "resserrement monétaire", "compte rendu", "projections des services"),
    "fr_rates": ("OAT", "adjudication", "Agence France Trésor", "AFT", "écart de taux",
                 "spread OAT-Bund", "rendement à dix ans", "émission syndiquée"),
    "fr_market": ("quatre sorcières", "échéance", "séance de clôture", "fixing de clôture",
                  "CAC 40", "détachement du dividende", "jour férié", "carnet d'ordres"),
    "fr_macro": ("indice des prix à la consommation", "IPCH", "projet de loi de finances",
                 "PLF", "déficit public", "motion de censure", "dissolution", "INSEE"),
    "it_policy": ("BCE", "tasso di riferimento", "tasso sui depositi", "consiglio direttivo",
                  "stretta monetaria", "verbali"),
    "it_rates": ("spread BTP-Bund", "lo spread", "asta dei BTP", "BTP", "BOT", "CCT",
                 "Dipartimento del Tesoro", "rendimento decennale", "collocamento sindacato",
                 "premio al rischio"),
    "it_market": ("le tre streghe", "scadenza tecnica", "giorno di scadenza", "FTSE MIB",
                  "asta di chiusura", "stacco cedola", "Ferragosto"),
    "it_macro": ("manovra di bilancio", "DEF", "NADEF", "legge di bilancio", "ISTAT",
                 "procedura per disavanzo eccessivo", "debito pubblico"),
    "es_policy": ("BCE", "tipo de interés oficial", "facilidad de depósito",
                  "consejo de gobierno", "endurecimiento monetario", "actas"),
    "es_rates": ("prima de riesgo", "subasta del Tesoro", "Tesoro Público", "bono a diez años",
                 "obligaciones del Estado", "letras del Tesoro", "sindicación",
                 "rentabilidad del bono"),
    "es_market": ("IBEX 35", "cuádruple hora bruja", "vencimiento de derivados", "subasta de "
                  "cierre", "descuento de dividendo", "MEFF"),
    "es_macro": ("IPC", "IPC armonizado", "Presupuestos Generales del Estado", "déficit público",
                 "euribor a doce meses", "hipoteca variable", "INE"),
    "nl_policy": ("ECB", "depositorente", "beleidsrente", "rentebesluit"),
    "nl_market": ("AEX", "expiratie", "slotveiling", "ex-dividend", "Damrak"),
    "nl_pension": ("pensioenfonds", "Wet toekomst pensioenen", "Wtp", "dekkingsgraad",
                   "invaarmoment", "renteafdekking", "ABP", "PFZW", "DNB"),
    "en_desk": ("quadruple witching", "the WMR fix", "month-end rebalancing", "carry", "basis",
                "cross-currency basis", "the turn", "periphery spread", "redenomination risk"),
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

    A page whose terms forbid machine extraction is registered with `machine_use_allowed=True`
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
    _src("ea.official.ecb", "ECB press, calendars, Data Portal and the Eurosystem's own notes",
         layer="official",
         roots=("https://www.ecb.europa.eu/press/calendars/",
                "https://www.ecb.europa.eu/press/pr/date/",
                "https://data.ecb.europa.eu/",
                "https://www.ecb.europa.eu/press/accounts/html/index.en.html"),
         languages=("en", "de", "fr", "it", "es"), licence="public, attribution",
         access_label="PUBLIC", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         weight=1.0,
         queries=("EZB-Zinsentscheid Termine", "geldpolitische Beschlüsse Protokoll",
                  "réunion de politique monétaire calendrier BCE",
                  "decisioni di politica monetaria BCE verbali",
                  "decisiones de política monetaria BCE actas",
                  "ECB-rentebesluit notulen"),
         notes="the decision, the account, the projections and the whole Data Portal. The "
               "German, French, Italian and Spanish language versions are NOT translations of "
               "equal reach: national press quotes the national-language release, so the "
               "national wording is what the retail and media layers propagate."),
    _src("ea.official.ncb_agencies_stats",
         "National central banks, debt agencies and statistical offices",
         layer="official",
         roots=("https://www.bundesbank.de/", "https://www.banque-france.fr/",
                "https://www.bancaditalia.it/", "https://www.bde.es/", "https://www.dnb.nl/",
                "https://www.deutsche-finanzagentur.de/", "https://www.aft.gouv.fr/",
                "https://www.dt.mef.gov.it/", "https://www.tesoro.es/",
                "https://ec.europa.eu/eurostat", "https://www.destatis.de/",
                "https://www.insee.fr/", "https://www.istat.it/", "https://www.ine.es/"),
         languages=("de", "fr", "it", "es", "nl", "en"), licence="public, attribution",
         access_label="OPEN_DATA", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         weight=1.0,
         queries=("Emissionskalender Bundesanleihen Aufstockung",
                  "Bietungsverhältnis Auktionsergebnis Bund",
                  "calendrier indicatif des adjudications OAT AFT",
                  "calendario aste BTP Dipartimento del Tesoro",
                  "subastas del Tesoro calendario obligaciones",
                  "HVPI Schnellschätzung Verbraucherpreise",
                  "IPCH estimation provisoire INSEE"),
         notes="the auction calendars are the euro area's only flow that is published a quarter "
               "in advance with a date, a size and an obliged buyer. The national CPI prints "
               "land BEFORE the euro-area flash, which is why the national offices are here "
               "rather than folded into Eurostat."),
    _src("ea.institutional.venues_and_bodies",
         "Exchange specifications, index providers and the European industry bodies",
         layer="institutional",
         roots=("https://www.eurex.com/ex-en/", "https://live.euronext.com/",
                "https://www.bmeexchange.es/", "https://www.eex.com/",
                "https://www.stoxx.com/", "https://www.eiopa.europa.eu/",
                "https://www.esma.europa.eu/", "https://www.afme.eu/",
                "https://www.efama.org/", "https://www.insuranceeurope.eu/"),
         languages=("en", "de", "fr", "es"), licence="public page, restricted redistribution",
         access_label="PUBLIC_WITH_TERMS", credibility="AUTHORITATIVE",
         predictive_state="UNTESTED", weight=1.0,
         queries=("DAX Schlussabrechnung Auktion Verfallstag Kontraktspezifikation",
                  "règlement CAC 40 cours de compensation échéance",
                  "especificaciones contrato futuro IBEX 35 vencimiento",
                  "EIOPA risk-free rate term structure monthly publication",
                  "EFAMA fund flows quarterly statistics"),
         notes="the contract specification is the ONLY authority on a settlement window; every "
               "settlement rule this pack states is to be re-read from here. EIOPA's monthly "
               "curve is the insurers' discounting input and therefore upstream of domain EA-H."),
    _src("ea.academic.working_papers",
         "Euro-area working papers, policy research and the discussion-paper series",
         layer="academic",
         roots=("https://www.ecb.europa.eu/pub/research/working-papers/",
                "https://www.bundesbank.de/en/publications/research/discussion-papers",
                "https://www.suerf.org/", "https://cepr.org/voxeu",
                "https://www.esrb.europa.eu/pub/", "https://papers.ssrn.com/",
                "https://www.bis.org/publ/"),
         languages=("en", "de", "fr"), licence="public, attribution",
         access_label="PUBLIC", credibility="RELIABLE", predictive_state="UNTESTED", weight=0.9,
         queries=("Diskussionspapier Zinsstrukturkurve Bundesanleihen Liquiditätsprämie",
                  "document de travail prime de risque souveraine OAT",
                  "working paper sovereign spread redenomination risk euro area",
                  "SUERF policy brief pension transition interest rate hedging"),
         notes="SUERF and VoxEU carry the central-bank-adjacent mechanism papers months before a "
               "journal does, and the Bundesbank's discussion papers are where German market "
               "microstructure is actually written down."),
    _src("ea.practitioner.strategy_desks",
         "Bank strategy notes, practitioner blogs and the professional societies",
         layer="practitioner",
         roots=("https://research.nordea.com/", "https://think.ing.com/",
                "https://www.dbresearch.com/", "https://www.cfainstitute.org/societies",
                "https://www.risk.net/", "https://substack.com/search/EZB%20Zinsen"),
         languages=("de", "fr", "en"), licence="mixed: public summaries, licensed full notes",
         access_label="ACCESS_UNCLEAR", credibility="RELIABLE", predictive_state="UNTESTED",
         weight=0.6,
         queries=("Zinsmeinung EZB Ausblick Einlagesatz Prognose",
                  "stratégie de taux zone euro spread OAT Bund commentaire",
                  "commento tassi BCE strategia obbligazionaria",
                  "estrategia de tipos zona euro prima de riesgo comentario"),
         notes="ACCESS_UNCLEAR is the honest label: the public teaser of a bank note is public "
               "and the note itself is not, and the two are routinely confused. Only the public "
               "teaser may be used, and the pack records that the full note EXISTS and is out of "
               "reach rather than pretending the public fragment is the research."),
    _src("ea.retail_ecology.boards",
         "German, French, Italian, Spanish and Dutch retail message boards",
         layer="retail_ecology",
         roots=("https://www.wallstreet-online.de/", "https://www.ariva.de/forum/",
                "https://www.finanzen.net/forum/", "https://www.boursorama.com/bourse/forum/",
                "https://forum.finanzaonline.com/", "https://www.rankia.com/foros/",
                "https://www.iex.nl/Forum.aspx"),
         languages=("de", "fr", "it", "es", "nl"), licence="public forum, quote-and-cite only",
         access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE", predictive_state="UNTESTED",
         weight=0.25, machine_use_allowed=True,
         queries=("Hexensabbat DAX Verfall Abrechnungskurs Spekulation",
                  "großer Verfall Stillhalter Basispreis Magnet",
                  "quatre sorcières CAC écart de clôture rumeur",
                  "lo spread BTP Bund oggi paura",
                  "prima de riesgo hoy subasta comentarios cuádruple hora bruja",
                  "AEX expiratie slotveiling forum"),
         notes="machine_use_allowed=True: several of these boards' terms forbid automated "
               "extraction. They are REGISTERED and never scraped -- the desk records that a "
               "German retail consensus about the Hexensabbat exists and is unreadable by "
               "machine here, which is a measurement and not a gap. Credibility UNRELIABLE and "
               "weight 0.25: what a crowd believes wrongly is still a tradable fact, so fringe "
               "and contradicted claims are kept as evidence objects at low weight, never "
               "dropped."),
    _src("ea.app_ecosystem.brokers_and_platforms",
         "Euro-area retail broker apps, their public data surfaces and the idea streams",
         layer="app_ecosystem",
         roots=("https://traderepublic.com/", "https://de.scalable.capital/",
                "https://www.degiro.de/", "https://www.onvista.de/",
                "https://www.comdirect.de/cms/ueberuns/de/service/api.html",
                "https://www.tradingview.com/ideas/dax/",
                "https://www.justetf.com/de/"),
         languages=("de", "fr", "es", "nl", "en"), licence="per-platform terms",
         access_label="PUBLIC_WITH_TERMS", credibility="UNKNOWN",
         predictive_state="NARRATIVE_FEATURE", weight=0.4,
         queries=("Trade Republic Sparplan meistgehandelt DAX",
                  "justETF Fondsvolumen Zufluss Europa",
                  "TradingView Idee DAX Verfallstag Analyse",
                  "meest verhandelde aandelen DEGIRO"),
         notes="NARRATIVE_FEATURE is the right predictive_state: platform most-traded lists and "
               "idea streams measure retail ATTENTION, which is a feature of the narrative and "
               "not a forecast. justETF's fund-volume pages are the closest public European "
               "analogue to a flow series and are the one part of this layer worth a real test."),
    _src("ea.media.business_press", "Euro-area business newspapers and newswires",
         layer="media",
         roots=("https://www.handelsblatt.com/", "https://www.boersen-zeitung.de/",
                "https://www.lesechos.fr/", "https://www.ilsole24ore.com/",
                "https://www.expansion.com/", "https://fd.nl/"),
         languages=("de", "fr", "it", "es", "nl"),
         licence="paywalled; terms forbid bulk extraction",
         access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
         predictive_state="NARRATIVE_FEATURE", weight=0.5, machine_use_allowed=True,
         queries=("Börsen-Zeitung Bundesanleihe Auktion Kommentar",
                  "Les Échos adjudication OAT tension taux",
                  "Il Sole 24 Ore spread BTP Bund chiusura",
                  "Expansión subasta Tesoro prima de riesgo",
                  "FD pensioenfondsen dekkingsgraad renteafdekking"),
         notes="machine_use_allowed=True for all six: every one of these paywalls forbids "
               "machine extraction in its terms. They are registered so the desk knows the "
               "coverage exists, and headlines reached through a licensed aggregator are the "
               "only compliant route. Boersen-Zeitung is the one that actually reports auction "
               "mechanics rather than the political story."),
    _src("ea.archive.historical", "Historical euro-area and pre-euro statistics and documents",
         layer="archive",
         roots=("https://www.bundesbank.de/en/statistics/time-series-databases",
                "https://data.ecb.europa.eu/",
                "https://eur-lex.europa.eu/",
                "https://gallica.bnf.fr/", "https://web.archive.org/",
                "https://www.deutsche-digitale-bibliothek.de/"),
         languages=("de", "fr", "en"), licence="public archive",
         access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         weight=0.8,
         queries=("Bundesbank Zeitreihen Umlaufrendite historisch seit 1948",
                  "EUR-Lex Verordnung Ratingagenturen Veröffentlichungskalender",
                  "archive ECB press release deposit facility rate history",
                  "Gallica cote de la Bourse de Paris historique"),
         notes="THIS LAYER IS WHY A PRE-2018 ERA IS STATABLE AT ALL. This box's bars begin in "
               "2018 (FX) and 2020 (indices), so every era before that -- APP, the negative "
               "deposit rate, OMT -- is reachable only through an archive. EUR-Lex is also where "
               "the CRA Regulation's after-close publication rule is actually written down."),
    _src("ea.physical_economy.energy_and_logistics",
         "European gas, power, grid and freight physical data",
         layer="physical_economy",
         roots=("https://agsi.gie.eu/", "https://transparency.entsoe.eu/",
                "https://www.entsog.eu/", "https://www.pegelonline.wsv.de/",
                "https://www.portofrotterdam.com/en/experience-online/throughput",
                "https://ec.europa.eu/eurostat/web/international-trade-in-goods"),
         languages=("en", "de", "nl"), licence="public / free registration",
         access_label="OPEN_DATA", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         weight=0.9,
         queries=("Gasspeicherstand Füllstand Deutschland AGSI",
                  "ENTSO-E day-ahead price Germany Luxembourg bidding zone",
                  "Pegel Kaub Rheinpegel Niedrigwasser Schifffahrt",
                  "doorvoer Rotterdam containeroverslag kwartaal"),
         notes="the Rhine gauge at Kaub is a genuinely physical euro-area constraint: below a "
               "threshold, barge loading falls and German chemical and steel logistics bind. It "
               "is free, daily, revision-free and almost nobody trades it. AGSI and ENTSO-E are "
               "the best point-in-time fundamental series in Europe."),
    _src("ea.source_graph.citation_and_link",
         "Citation, reference and link graphs over the euro-area corpus",
         layer="source_graph",
         roots=("https://econpapers.repec.org/", "https://ideas.repec.org/",
                "https://eur-lex.europa.eu/", "https://github.com/topics/quantitative-finance",
                "https://openalex.org/"),
         languages=("en", "de", "fr"), licence="public / open data",
         access_label="OPEN_DATA", credibility="RELIABLE", predictive_state="UNTESTED",
         weight=0.5,
         queries=("RePEc cited by Bundesbank discussion paper sovereign spread",
                  "OpenAlex citation graph euro area monetary transmission",
                  "EUR-Lex cited-by regulation credit rating agencies sovereign calendar",
                  "github euribor day count convention TARGET2 calendar python"),
         notes="the point of a source graph is to find the sources the desk has NOT named: who "
               "cites the Bundesbank paper, what links to the CRA Regulation, which repositories "
               "depend on a TARGET2 calendar library. It is the layer that keeps the other nine "
               "from being a fixed list somebody wrote once."),
)

#: A layer with no source above must say WHY, in one sentence, and the reason must be a fact
#: about the country rather than about the session's patience. All ten are populated for the
#: euro area, so this table is empty by measurement -- and `source_layer_coverage` proves it
#: rather than asserting it.
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
    """A catalogue row plus the six point-in-time stamps. A dataset whose vintage cannot be
    reconstructed can only ever produce NOT_PIT_SAFE cells, so the stamps are not optional."""
    row = dataset(name, **kw)
    missing = [s for s in PIT_STAMPS if not str(pit.get(s, "")).strip()]
    if missing:
        raise ValueError(f"dataset {name}: missing PIT stamps {missing}")
    row["pit"] = dict(pit)
    return row


DATASETS: tuple[dict[str, Any], ...] = (
    _ds("ECB monetary policy decisions and the rate path",
        source="ECB press releases and the ECB Data Portal",
        coverage="all euro-area policy decisions since 1999", frequency="8 per year",
        publication_lag_days=0.0,
        revisions="none to the decision; the ACCOUNT four weeks later adds information and is a "
                  "separate event with its own timestamp",
        licence="public, attribution", history_from="1999-01-01", pit_feasible=True,
        assets=("EURUSD", "EURCHF", "GER40", "EUSTX50"),
        mechanism_families=("policy_surprise", "event_drift", "carry"),
        how_to_fetch="ECB press calendar page, one HTML page per decision; the rate table is in "
                     "the ECB Data Portal series key FM.D.U2.EUR.4F.KR.DFR.LEV",
        pit={"event_time": "the 14:15 CET announcement timestamp on the press release",
             "period_time": "the maintenance period the new rate applies from, which is NOT the "
                            "announcement date -- it is the next reserve maintenance period",
             "publication_time": "14:15 CET/CEST, same instant as the event",
             "available_time": "same instant; the ECB does not embargo its own rate line",
             "revision_time": "never revised",
             "retrieval_time": "stamped by the crawler at fetch"}),
    _ds("Euribor and ESTR fixings",
        source="EMMI (Euribor) and ECB (ESTR)", coverage="euro money market",
        frequency="daily on TARGET2 days", publication_lag_days=0.0,
        revisions="ESTR is republished the same day if an error exceeds a threshold; Euribor is "
                  "not revised. The ESTR republication is a real PIT hazard -- the 09:00 CET "
                  "value can differ from the 08:00 CET one.",
        licence="EMMI licence for Euribor redistribution; ESTR is public",
        history_from="ESTR 2019-10-01, Euribor 1999-01-01", pit_feasible=True,
        assets=("EURUSD", "EURCHF", "EURSEK"),
        mechanism_families=("funding", "carry", "policy_transmission"),
        how_to_fetch="ECB Data Portal for ESTR; Euribor requires an EMMI licence for anything "
                     "beyond the daily headline",
        pit={"event_time": "the trading day the rate is computed over",
             "period_time": "the overnight or term period the rate prices",
             "publication_time": "08:00 CET (ESTR) / 11:00 CET (Euribor)",
             "available_time": "same, but the ESTR republication window runs to 09:00 CET",
             "revision_time": "ESTR: same day by 09:00 CET when triggered; Euribor: never",
             "retrieval_time": "crawler stamp"}),
    _ds("Sovereign auction calendars and results (DE, FR, IT, ES)",
        source="Finanzagentur, AFT, Dipartimento del Tesoro, Tesoro Publico",
        coverage="all euro-area benchmark issuance", frequency="quarterly calendar, weekly events",
        publication_lag_days=0.0,
        revisions="the SIZE is announced a few days before the auction and can be changed; the "
                  "calendar itself is published a quarter ahead. Two different announcement "
                  "times, and the size announcement is the tradable one.",
        licence="public", history_from="1999", pit_feasible=True,
        assets=("EURUSD", "GER40", "FRA40", "E35"),
        mechanism_families=("supply_concession", "forced_flow", "event_drift"),
        how_to_fetch="each agency publishes a calendar PDF/ICS and a results page per auction",
        pit={"event_time": "the auction bidding deadline (11:00 CET for the Bund; agency-specific "
                           "otherwise)",
             "period_time": "the settlement date, T+2 to T+3, which is when the cash actually "
                            "moves and is the date a flow study should use",
             "publication_time": "results within minutes of the deadline",
             "available_time": "same",
             "revision_time": "never; a cancelled auction is a separate announcement",
             "retrieval_time": "crawler stamp"}),
    _ds("HICP flash and final, euro area and member states",
        source="Eurostat and the national statistical offices",
        coverage="euro area and each member state", frequency="monthly",
        publication_lag_days=0.0,
        revisions="the FLASH is revised by the FINAL about two weeks later, and the national "
                  "prints (Germany, Spain, France) land BEFORE the euro-area flash -- so the "
                  "euro-area surprise is partly predictable from prints already public. A study "
                  "that treats the euro-area flash as new information is measuring a residual.",
        licence="public, attribution", history_from="1997", pit_feasible=True,
        assets=("EURUSD", "EURCHF", "GER40", "EUSTX50"),
        mechanism_families=("data_surprise", "policy_expectation", "event_drift"),
        how_to_fetch="Eurostat bulk download; national offices for the country prints and their "
                     "individual release clocks",
        pit={"event_time": "the release timestamp, 11:00 CET for the euro-area flash",
             "period_time": "the reference month",
             "publication_time": "11:00 CET euro area; 08:00 CET Germany; 09:00 CET Spain",
             "available_time": "same as publication; no embargo copy reaches the market early",
             "revision_time": "the final print, roughly 14 days later, and annual reweighting "
                              "each January which rewrites the whole recent history",
             "retrieval_time": "crawler stamp"}),
    _ds("Ifo Business Climate and ZEW Economic Sentiment",
        source="ifo Institut and ZEW Mannheim", coverage="Germany",
        frequency="monthly", publication_lag_days=0.0,
        revisions="both revise the prior month routinely; the REVISION is published in the same "
                  "release as the new print and is frequently larger than the surprise",
        licence="public headline, licensed detail", history_from="Ifo 1991, ZEW 1991",
        pit_feasible=True, assets=("GER40", "EURUSD", "EUSTX50"),
        mechanism_families=("survey_surprise", "event_drift", "regime_condition"),
        how_to_fetch="ifo.de and zew.de release pages; the historical series is downloadable",
        pit={"event_time": "10:00 CET (Ifo) / 11:00 CET (ZEW) release",
             "period_time": "the survey month",
             "publication_time": "as above",
             "available_time": "same",
             "revision_time": "the following month's release",
             "retrieval_time": "crawler stamp"}),
    _ds("AGSI+ European gas storage",
        source="Gas Infrastructure Europe", coverage="every EU storage facility and country",
        frequency="daily", publication_lag_days=1.0,
        revisions="restatements happen and are visible in the API's own version field; the "
                  "revision is small but real and the API exposes it, which is rare",
        licence="public with registration", history_from="2011", pit_feasible=True,
        assets=("GER40", "NETH25", "EURUSD", "XNGUSD"),
        mechanism_families=("terms_of_trade", "energy_shock", "regime_condition"),
        how_to_fetch="AGSI+ REST API, one call per country per day",
        pit={"event_time": "the gas day the level refers to",
             "period_time": "the same gas day (06:00-06:00 CET)",
             "publication_time": "the following day, typically before 19:00 CET",
             "available_time": "same",
             "revision_time": "occasional restatement, versioned in the API",
             "retrieval_time": "crawler stamp"}),
    _ds("Eurex daily settlement prices and open interest",
        source="Eurex", coverage="FDAX, FESX and their option chains",
        frequency="daily", publication_lag_days=1.0,
        revisions="a settlement price can be corrected the following morning; the correction is "
                  "published and is the reason a gamma study must use the T+1 file, not the "
                  "T+0 screen",
        licence="public page, restricted redistribution", history_from="2000-ish for the web files",
        pit_feasible=True, assets=("GER40", "EUSTX50"),
        mechanism_families=("dealer_gamma", "expiry_pinning", "positioning"),
        how_to_fetch="Eurex statistics pages, one CSV per trading day",
        pit={"event_time": "the trading day",
             "period_time": "the same trading day's close",
             "publication_time": "the following morning CET",
             "available_time": "same",
             "revision_time": "corrections the next morning",
             "retrieval_time": "crawler stamp"}),
    _ds("Dutch pension fund coverage ratios and the Wtp transition register",
        source="De Nederlandsche Bank and the funds' own filings",
        coverage="all Dutch occupational pension funds", frequency="quarterly (DNB), event-driven "
                 "for the transition dates",
        publication_lag_days=45.0,
        revisions="coverage ratios are restated when the discount curve is restated; the "
                  "TRANSITION DATE per fund is announced in advance and is the tradable item",
        licence="public", history_from="2007", pit_feasible=True,
        assets=("EURUSD", "NETH25"),
        mechanism_families=("forced_flow", "duration_demand", "scheduled_reallocation"),
        how_to_fetch="DNB statistics pages; the per-fund invaardatum from the fund's own site",
        pit={"event_time": "the announcement of a fund's transition date",
             "period_time": "the quarter the coverage ratio refers to",
             "publication_time": "DNB quarterly, about six weeks after quarter end",
             "available_time": "same",
             "revision_time": "restated with curve changes",
             "retrieval_time": "crawler stamp"}),
    _ds("CFTC Commitments of Traders, Euro FX",
        source="CFTC", coverage="CME euro futures and options",
        frequency="weekly", publication_lag_days=3.0,
        revisions="the CFTC republishes corrected weeks without fanfare; a naive cache never "
                  "sees the correction, which is the classic COT backtest leak",
        licence="public domain", history_from="1986 (legacy), 2006 (TFF)", pit_feasible=True,
        assets=("EURUSD", "EURCHF", "EURJPY"),
        mechanism_families=("positioning", "crowding", "reversal"),
        how_to_fetch="CFTC weekly text and the historical compressed archives",
        pit={"event_time": "the Tuesday the positions are as of",
             "period_time": "the same Tuesday close",
             "publication_time": "Friday 15:30 ET",
             "available_time": "Friday 15:30 ET -- three days after the snapshot, and the gap is "
                               "the whole point-in-time problem",
             "revision_time": "silent corrections in later weekly files",
             "retrieval_time": "crawler stamp"}),
    _ds("ECB euro foreign exchange reference rates",
        source="ECB", coverage="EUR against 30-odd currencies",
        frequency="daily on TARGET2 days", publication_lag_days=0.0,
        revisions="never revised", licence="public, attribution", history_from="1999-01-04",
        pit_feasible=True, assets=("EURUSD", "EURPLN", "EURSEK", "EURNOK", "EURHUF", "EURCZK"),
        mechanism_families=("fix_flow", "corporate_hedging", "benchmark_effect"),
        how_to_fetch="ECB Data Portal EXR dataset, daily CSV",
        pit={"event_time": "the 14:15 CET concertation",
             "period_time": "the same trading day",
             "publication_time": "around 16:00 CET",
             "available_time": "around 16:00 CET -- roughly 105 minutes AFTER the rate is struck, "
                               "which is the window any fix-front-running hypothesis lives in",
             "revision_time": "never",
             "retrieval_time": "crawler stamp"}),
)


def actors() -> tuple[dict[str, Any], ...]:
    """The sixteen euro-area participants whose constraints produce dated, forced flow."""
    return (
        actor("ECB Governing Council",
              holds="the euro area's monetary policy stance and the Eurosystem balance sheet",
              forced_to=("meet on a calendar published a year ahead",
                         "publish a decision at 14:15 CET whether or not anything changed",
                         "publish staff projections four times a year",
                         "publish the account of each meeting four weeks later"),
              when="eight scheduled policy meetings a year, Thursday, roughly six weeks apart",
              information=("the euro-area HICP flash, which lands the week before",
                           "the national HICP prints, which land before the euro-area flash",
                           "the bank lending survey and the SAFE survey",
                           "market pricing of its own path in Euribor and ESTR futures"),
              constraints=("a single rate for twenty economies with different mortgage-reset "
                           "conventions, so transmission speed differs by country",
                           "the price-stability mandate is primary and is not discretionary",
                           "a rotating vote that makes the reaction function a committee's, "
                           "not a governor's"),
              instruments=("EURUSD", "EURCHF", "EURGBP", "GER40", "EUSTX50"),
              counterparties=("euro-area banks through the refinancing operations",
                              "the sovereign issuers through the reinvestment portfolios",
                              "the whole global rates complex through the path"),
              observables=("the decision statement and its diff against the prior one",
                           "the Euribor/ESTR-implied path immediately before and after",
                           "the four-week-later account",
                           "the projection tables"),
              impact="the largest single scheduled euro-area price event; the SURPRISE (the "
                     "change in the implied path) is the signed quantity, never the level",
              persistence="the path repricing persists for weeks; the announcement-minute move "
                          "is frequently reversed within the press conference",
              falsifier="if the post-decision move regressed on the implied-path surprise has a "
                        "coefficient statistically indistinguishable from zero across the eight "
                        "meetings of a year, the decision is not the event and the projections "
                        "or the press conference are",
              notes="the decision and the press conference are TWO events thirty minutes apart "
                    "and they routinely move price in opposite directions"),
        actor("Deutsche Finanzagentur (German debt agency)",
              holds="the issuance programme for Bunds, Bobls, Schaetze and Bubills",
              forced_to=("publish an issuance calendar each quarter",
                         "auction on the announced date whatever the market does",
                         "retain part of every auction for market-making (the Marktpflegequote), "
                         "which makes a German 'failed' auction a bookkeeping artefact rather "
                         "than an event"),
              when="Wednesdays for the capital-market instruments, bidding deadline 11:00 CET",
              information=("the federal funding need, set by the budget",
                           "the debt brake and any Sondervermoegen carve-out"),
              constraints=("the Schuldenbremse caps the core deficit, so German supply is small "
                           "relative to the euro area's and its scarcity is itself a price",
                           "a quarterly-announced calendar cannot be moved for convenience"),
              instruments=("GER40", "EURUSD"),
              counterparties=("the Bund auction group of primary dealers",
                              "every euro-area investor who benchmarks against the Bund"),
              observables=("the quarterly calendar", "the size announcement days before",
                           "the bid-to-cover and the retained share"),
              impact="a supply concession into the auction and a relief afterwards; the German "
                     "case is unusually weak because the retention mechanism absorbs the tail",
              persistence="hours to a day around the auction",
              falsifier="if the yield change from T-1 close to the bidding deadline has no "
                        "relation to the announced size across a year of auctions, the "
                        "concession does not exist in the German curve and the hypothesis should "
                        "be transferred to the Italian one",
              notes="German scarcity is the reason the Bund can trade through the swap curve; "
                    "that spread is the cleanest euro-area collateral-stress observable"),
        actor("Agence France Tresor (AFT)",
              holds="the French issuance programme, the largest in the euro area",
              forced_to=("adjudicate long OATs on the first Thursday of each month",
                         "adjudicate short and index-linked paper on other Thursdays",
                         "publish the annual programme with the budget"),
              when="Thursdays, 10:50 CET deadline for the long line",
              information=("the PLF (the budget bill) and its deficit path",
                           "any rating agency review scheduled for the coming Friday"),
              constraints=("France funds a structurally large deficit, so the calendar cannot "
                           "flex downward",
                           "a political crisis does not suspend the calendar"),
              instruments=("FRA40", "EURUSD"),
              counterparties=("the SVT primary dealers", "foreign official reserve managers"),
              observables=("the monthly adjudication result and its bid-to-cover",
                           "the OAT-Bund 10y spread on the day"),
              impact="French political risk is priced in the OAT-Bund spread and reaches FRA40 "
                     "through the banks; the auction is the day the price is tested",
              persistence="the spread level persists across a political regime; the auction "
                          "effect is intraday",
              falsifier="if the OAT-Bund spread does not widen into the first-Thursday deadline "
                        "in a sample of twelve months, the supply-concession mechanism is absent "
                        "in France too and the whole family should go to Italy or nowhere",
              notes="the OAT-Bund spread is the euro area's second spread and the one that "
                    "reprices on a dissolution or a censure motion"),
        actor("Dipartimento del Tesoro (Italian Treasury)",
              holds="the euro area's largest sovereign debt stock",
              forced_to=("auction BOTs mid-month and BTPs at the end of the month",
                         "publish the quarterly issuance programme",
                         "fund a debt-to-GDP ratio that makes the spread a political variable"),
              when="the BOT auction around the 10th-13th and the BTP auction around the 28th-30th",
              information=("the NADEF and the manovra di bilancio in autumn",
                           "the European Commission's opinion on the budget",
                           "rating reviews, which are scheduled for Fridays after the close"),
              constraints=("a high debt stock means a rollover calendar that cannot be paused",
                           "domestic banks hold a large share, which is the doom loop"),
              instruments=("EUSTX50", "E35", "EURUSD", "EURCHF"),
              counterparties=("the specialisti in titoli di Stato",
                              "Italian retail, which the Treasury courts directly with BTP Valore "
                              "issues -- a dated, announced retail flow with no analogue in "
                              "Germany or France"),
              observables=("lo spread, the BTP-Bund 10y differential, quoted hourly by Italian "
                           "media and therefore a genuine public sentiment series",
                           "the end-of-month auction results",
                           "the BTP Valore subscription windows"),
              impact="periphery stress is a EUR-negative and a CHF-positive; it reaches the desk "
                     "through EURCHF before it reaches any index",
              persistence="regime-like: the spread has levels that persist for years and jumps "
                          "that are political",
              falsifier="if EURCHF has no measurable response to a 25bp one-day widening in the "
                        "BTP-Bund spread across the sample, the safe-haven leg of the periphery "
                        "mechanism does not exist on this desk's instruments and every edge "
                        "routed through it is void",
              notes="the desk CANNOT trade the spread: FBTP and FGBL are both absent from the "
                    "universe, so the spread is an INPUT and never a leg"),
        actor("Tesoro Publico (Spanish Treasury)",
              holds="the Spanish issuance programme",
              forced_to=("auction Letras on the first and third Tuesday and Bonos/Obligaciones "
                         "on the first and third Thursday",
                         "publish an annual strategy in January"),
              when="Tuesdays and Thursdays, 10:30 CET deadline",
              information=("the Presupuestos Generales del Estado, when one is passed at all",
                           "the mortgage-reset channel through 12m Euribor"),
              constraints=("a fragmented parliament has repeatedly rolled the prior year's "
                           "budget forward, so Spanish fiscal news is IRREGULAR, not calendared",),
              instruments=("E35", "EURUSD"),
              counterparties=("the Spanish primary dealers", "domestic banks and insurers"),
              observables=("la prima de riesgo, the Spain-Germany 10y spread",
                           "the 12m Euribor monthly average, which resets a large stock of "
                           "variable-rate Spanish mortgages"),
              impact="Spanish household cash flow is unusually rate-sensitive because the "
                     "mortgage stock is variable and resets annually against 12m Euribor -- a "
                     "slower and more measurable transmission than the German fixed-rate case",
              persistence="the mortgage reset is an annual, dated cash-flow event per cohort",
              falsifier="if E35's relative performance against GER40 shows no relation to the "
                        "12m Euribor twelve-month change, the Spanish rate-sensitivity channel "
                        "is not in the index and belongs to banks alone",
              notes="the two-lane order forbids trading the Spanish banks directly; the channel "
                    "is expressed as an index-relative and never as a single name"),
        actor("Euro-area life insurers and pension funds",
              holds="long euro-denominated liabilities discounted on a published curve",
              forced_to=("match duration under Solvency II",
                         "report a solvency ratio quarterly",
                         "de-risk when the ratio falls, which forces BUYING of duration exactly "
                         "when duration is expensive"),
              when="quarter-end reporting; continuous hedging in between",
              information=("the EIOPA risk-free curve, published monthly",
                           "their own funding ratio"),
              constraints=("a regulatory capital charge that is convex in the rate level, so the "
                           "hedging demand is non-linear and largest at low rates",),
              instruments=("EURUSD", "EUSTX50"),
              counterparties=("swap dealers", "sovereign issuers"),
              observables=("the EIOPA monthly curve publication",
                           "quarterly solvency disclosures",
                           "the 30y EUR swap spread"),
              impact="a persistent, price-insensitive bid for long euro duration that steepens "
                     "or flattens the curve independently of the ECB",
              persistence="structural, measured in years",
              falsifier="if the 30y-10y EUR slope shows no relation to the published aggregate "
                        "solvency ratio across quarters, the convex-hedging story is not "
                        "operating at the aggregate level",
              notes="this is the euro area's analogue of the UK LDI complex, with a slower fuse "
                    "and no repo leverage -- which is why it has not produced a 2022-style event"),
        actor("Dutch pension funds in the Wtp transition",
              holds="around 1.5 trillion euro of assets against liabilities that STOP being "
                    "discounted the way they are today when each fund crosses its transition date",
              forced_to=("convert from defined benefit to defined contribution on a per-fund "
                         "date announced in advance, between 2025 and 2027",
                         "reduce interest-rate hedging as the liability definition changes"),
              when="per-fund invaardatum, published, clustered on 1 January of 2025, 2026 and 2027",
              information=("the fund's own coverage ratio",
                           "DNB's quarterly statistics",
                           "the published transition plan"),
              constraints=("the transition is statutory and dated; a fund cannot defer it for "
                           "market reasons past the legal backstop",),
              instruments=("EURUSD", "NETH25"),
              counterparties=("swap dealers holding the other side of the hedge",
                              "euro-area sovereign issuers"),
              observables=("the announced transition dates",
                           "DNB coverage ratios",
                           "the 30y EUR swap spread around 1 January"),
              impact="the single largest SCHEDULED duration reallocation in European fixed income; "
                     "a reduction in hedge ratio is a paying-fixed flow, which steepens",
              persistence="a dated, one-way, multi-year flow -- the rarest kind of observable",
              falsifier="if the 30y EUR swap spread shows no abnormal move in the five sessions "
                        "around a cluster of announced transition dates, the flow is being "
                        "pre-hedged smoothly and there is no dateable event to trade",
              notes="the swap leg is not executable here; the edge routes into EURUSD and NETH25 "
                    "and is weaker for it, which the pack says rather than hides"),
        actor("German industrial exporters",
              holds="dollar and renminbi receivables against a euro cost base",
              forced_to=("hedge on a treasury policy with a fixed horizon, typically rolling "
                         "quarterly",
                         "publish quarterly results that reveal the hedge ratio's effect"),
              when="quarter-end, concentrated into the 16:00 London fix",
              information=("their own order book and the Ifo survey they answer",
                           "the EURUSD forward curve"),
              constraints=("a hedging policy is a board mandate, not a view; it executes "
                           "regardless of the level",),
              instruments=("EURUSD", "GER40"),
              counterparties=("bank FX desks", "the WMR fix window"),
              observables=("the Ifo export expectations component",
                           "German goods exports from Destatis",
                           "quarter-end fix volume"),
              impact="a mechanical quarter-end EUR bid or offer whose SIGN is set by the "
                     "quarter's realised move, not by a view",
              persistence="minutes around the fix; the sign persists across the quarter",
              falsifier="if EURUSD's return in the 15:57:30-16:02:30 window on the last business "
                        "day of a quarter has no relation to the quarter's realised return, the "
                        "rebalancing mechanism is not visible at this frequency",
              notes="this is the euro-area leg of the standard month-end model and the one place "
                    "where the WMR fix and a national actor coincide exactly"),
        actor("Passive index funds tracking DAX, CAC 40, AEX and IBEX 35",
              holds="replicating portfolios that must match an index they do not control",
              forced_to=("trade the index change on the effective date at the closing price",
                         "trade the free-float and capping revisions on the same dates"),
              when="quarterly review effective after the close of the third Friday",
              information=("the index provider's announced changes, typically two to three weeks "
                           "ahead",),
              constraints=("tracking error is the only thing they are measured on, so they pay "
                           "the closing auction price whatever it is",),
              instruments=("GER40", "FRA40", "NETH25", "E35"),
              counterparties=("the market makers who warehouse the imbalance",
                              "the closing auction"),
              observables=("the announcement date and the effective date",
                           "closing auction volume on the effective date"),
              impact="a concentrated, forecastable, one-sided flow in the closing auction; the "
                     "index LEVEL effect is small and the single-name effect is large, and only "
                     "the index level is hypothesis ground here",
              persistence="one auction, with a partial reversal over the following week",
              falsifier="if the index's own return in the last fifteen minutes of a review "
                        "effective date is indistinguishable from an ordinary third Friday, the "
                        "index-level effect is absent and only the single-name one exists -- "
                        "which the two-lane order puts out of reach",
              notes="deliberately kept at index level; a single-name rebalancing hypothesis is "
                    "forbidden ground under the 2026-09-06 order"),
        actor("Eurex index option market makers",
              holds="short gamma into a monthly expiry against a book they must delta-hedge",
              forced_to=("hedge continuously as spot moves through strikes",
                         "roll or close before the 13:00 CET DAX settlement auction"),
              when="daily, and violently on the third Friday morning",
              information=("open interest by strike, published daily by Eurex",
                           "their own inventory"),
              constraints=("a risk limit that forces hedging rather than a view",),
              instruments=("GER40", "EUSTX50"),
              counterparties=("structured-product issuers, who are the natural other side in "
                              "Germany -- the German retail certificate market is unusually "
                              "large and is where the dealer's short gamma comes from",),
              observables=("Eurex open interest by strike",
                           "realised versus implied volatility into the expiry week"),
              impact="pinning toward high-open-interest strikes into the 13:00 CET auction and a "
                     "release of realised volatility after it",
              persistence="the expiry week; gone by the following Monday",
              falsifier="if GER40's realised volatility in the four hours before the 13:00 CET "
                        "settlement auction is not lower than a matched non-expiry Friday, "
                        "pinning is not measurable at this resolution",
              notes="GER40's settlement at a 13:00 CET AUCTION rather than at the close is what "
                    "makes this testable at all -- the release is at a known instant"),
        actor("European utilities and industrial gas buyers",
              holds="forward gas and power positions against contracted customer demand",
              forced_to=("refill storage to a regulatory target ahead of each winter",
                         "hedge a fixed fraction of expected load on a published policy"),
              when="the April-October injection season, with an EU storage target for 1 November",
              information=("AGSI+ daily storage levels",
                           "weather forecasts",
                           "LNG cargo tracking"),
              constraints=("a statutory storage target converts a price-elastic buyer into a "
                           "price-INELASTIC one for part of the year -- which is exactly what "
                           "made 2022 a squeeze rather than a rally",),
              instruments=("GER40", "NETH25", "EURUSD"),
              counterparties=("Norwegian and US LNG sellers", "the TTF market"),
              observables=("AGSI+ fill percentage against the seasonal norm",
                           "TTF front-month, which the desk cannot trade",
                           "the TTF-to-Henry-Hub ratio, which is the arbitrage"),
              impact="a euro-area terms-of-trade shock: a gas price spike is a EUR-negative and a "
                     "GER40-negative simultaneously, which is a rare same-sign pair",
              persistence="seasonal, with regime shifts on supply events",
              falsifier="if the 20-day correlation between GER40 returns and a TTF proxy is "
                        "indistinguishable from zero outside 2021-2023, the energy channel is a "
                        "crisis-only regime and must be conditioned, not pooled",
              notes="TTF is NOT in the universe. XNGUSD is Henry Hub and is a CONTROL for this "
                    "actor, never a proxy: the two decoupled by an order of magnitude in 2022"),
        actor("Supranational euro issuers (EU/NGEU, ESM, EIB)",
              holds="a syndicated euro issuance programme that competes with sovereigns",
              forced_to=("publish a funding plan each half-year",
                         "syndicate on announced windows, which crowd the same days"),
              when="funding windows announced weeks ahead; the EU issues in clusters",
              information=("the NGEU disbursement schedule",
                           "member-state drawdown requests"),
              constraints=("a disbursement schedule set by the Recovery and Resilience Facility, "
                           "not by market conditions",),
              instruments=("EURUSD", "EURPLN"),
              counterparties=("syndicate banks", "official reserve managers"),
              observables=("the EU funding plan and its calendar",
                           "the EU-Bund spread, which is the swap-spread proxy for supply"),
              impact="a syndication day crowds out sovereign supply and compresses the whole "
                     "euro spread complex for a session",
              persistence="days",
              falsifier="if EURPLN shows no relation to announced RRF disbursements to Poland "
                        "across the disbursement calendar, the EU-funds channel into CEE "
                        "currencies is not measurable at this frequency",
              notes="the CEE link is why this actor is in the euro-area pack and referenced from "
                    "the Polish one"),
        actor("Euro-area money market funds and the excess liquidity complex",
              holds="short euro paper and deposits at a rate anchored to the DFR",
              forced_to=("roll continuously",
                         "report a weekly liquid asset ratio under the MMF Regulation"),
              when="daily, with a pronounced quarter-end and year-end distortion",
              information=("ESTR and the DFR", "the Eurosystem's excess liquidity number"),
              constraints=("regulatory liquidity ratios that bind hardest at reporting dates, "
                           "which is why the year-end turn exists at all",),
              instruments=("EURUSD", "EURCHF", "EURSEK"),
              counterparties=("banks shrinking balance sheets over a reporting date",
                              "the cross-currency basis market"),
              observables=("ESTR minus DFR",
                           "the EUR/USD cross-currency basis, especially the turn-of-year point",
                           "Eurosystem excess liquidity, published weekly"),
              impact="the year-end turn: a dated, annual, mechanical dislocation in euro funding "
                     "that is visible in the forward points of every euro pair",
              persistence="a few days spanning the reporting date, every year",
              falsifier="if the EURUSD overnight forward point spanning 31 December is not "
                        "abnormal relative to neighbouring days across five years, the turn is "
                        "not present at the desk's resolution",
              notes="the year-end turn is one of the few genuinely annual, genuinely mechanical "
                    "effects in FX and it is visible in H1 bars"),
        actor("Foreign official reserve managers holding euro",
              holds="the euro's roughly one-fifth share of global reserves",
              forced_to=("rebalance to a currency-composition benchmark",
                         "reinvest coupon and redemption proceeds"),
              when="quarterly, around the COFER reporting cycle",
              information=("IMF COFER, published quarterly with a long lag",
                           "their own benchmark"),
              constraints=("a benchmark that is set politically and changes slowly, so the "
                           "rebalancing is mechanical and price-insensitive",),
              instruments=("EURUSD", "XAUEUR", "USDX"),
              counterparties=("the sovereign issuers they buy from", "bank FX desks"),
              observables=("IMF COFER quarterly shares",
                           "the ECB's own annual international role of the euro report"),
              impact="a slow, persistent flow that shows up as a level, not an event; it is the "
                     "reason EURUSD has a mean-reverting component at multi-quarter horizons",
              persistence="quarters to years",
              falsifier="if EURUSD's quarterly return shows no relation to the change in the "
                        "COFER euro share once the dollar's own move is removed, the "
                        "rebalancing is accounting rather than flow",
              notes="COFER's lag makes this an ACTOR study and never a timing one"),
        actor("Rating agencies on the EU sovereign review calendar",
              holds="the sovereign ratings that drive index eligibility and capital charges",
              forced_to=("publish a calendar of sovereign review dates at the start of each year",
                         "publish rating actions AFTER the close on the scheduled date"),
              when="scheduled Fridays, after the European close, under the EU CRA Regulation",
              information=("the sovereign's own fiscal data", "the Commission's opinions"),
              constraints=("the EU regulation forces a PUBLISHED CALENDAR and an after-close "
                           "publication -- a constraint that exists nowhere else in the world and "
                           "creates a genuinely dateable weekend-gap event",),
              instruments=("EURUSD", "E35", "FRA40", "EUSTX50"),
              counterparties=("index providers", "bank treasuries with capital charges"),
              observables=("the published annual review calendar",
                           "the action itself, Friday after the close"),
              impact="a Monday gap in the affected sovereign's spread and, when the sovereign is "
                     "large, in the euro itself",
              persistence="one gap, mostly retraced unless the action changes index eligibility",
              falsifier="if the Monday open-to-close return of FRA40 or E35 after a scheduled "
                        "review Friday is indistinguishable from an ordinary Monday across the "
                        "sample, the weekend-gap mechanism does not survive at index level",
              notes="THE cleanest scheduled European event nobody outside rates watches: the "
                    "calendar is public, the timing is forced by regulation, and the market "
                    "cannot react until Monday"),
        actor("CFTC-reportable euro speculators",
              holds="leveraged futures positions in CME euro FX",
              forced_to=("report positions weekly",
                         "meet margin, which forces liquidation at the wrong moment"),
              when="positions as of Tuesday, published Friday 15:30 ET",
              information=("the same public macro everyone has",
                           "their own risk limits"),
              constraints=("margin and a value-at-risk limit, which makes a crowded position a "
                           "forced seller in a volatility spike",),
              instruments=("EURUSD", "EURJPY", "EURCHF"),
              counterparties=("dealers", "commercial hedgers on the other side of the report"),
              observables=("the weekly COT net position and its percentile",
                           "the TFF leveraged-funds line"),
              impact="crowding is a conditioning variable, not a signal: an extreme reading "
                     "raises the conditional probability of a sharp reversal on a shock",
              persistence="weeks; positions build slowly and unwind fast",
              falsifier="if conditioning EURUSD's weekly return on a COT percentile adds nothing "
                        "to an unconditional model out of sample, crowding is not informative on "
                        "this pair at this frequency",
              notes="the three-day snapshot lag is the point-in-time trap; the pack's dataset "
                    "row carries it explicitly"),
    )


def domains() -> tuple[dict[str, Any], ...]:
    """Fourteen research domains. Every one carries negative controls, without exception."""
    return (
        domain("EA-A", "ECB decisions, projections and the account",
               objects=("the 14:15 CET decision", "the 14:45 CET press conference",
                        "the quarterly staff projections", "the four-week-later account"),
               conditions=("projection meeting versus non-projection meeting",
                           "the sign and size of the implied-path surprise",
                           "the policy era (hiking, holding, cutting)"),
               instruments=("EURUSD", "EURCHF", "EURGBP", "GER40", "EUSTX50"),
               controls=("the same window on a NON-decision Thursday in the same month",
                         "the same window on the Federal Reserve's own decision days, to show "
                         "the effect is not simply 'a central bank spoke today'",
                         "a placebo at 14:15 CET on the day before each decision",
                         "EURSEK and EURNOK, which share the European session but not the ECB, "
                         "to separate the euro leg from a general European risk move"),
               notes="the decision and the press conference are separate events; pooling them "
                     "averages two different mechanisms with opposite typical signs"),
        domain("EA-B", "The two euro fixes: 14:15 CET reference rate and 16:00 London WMR",
               objects=("the ECB reference rate concertation and its ~105-minute publication lag",
                        "the WMR five-minute window",
                        "month-end and quarter-end concentration in the WMR window"),
               conditions=("month-end versus mid-month", "quarter-end versus ordinary month-end",
                           "the sign of the month's realised EURUSD return"),
               instruments=("EURUSD", "EURGBP", "EURCHF", "EURSEK"),
               controls=("the same clock time on a mid-month day",
                         "the same window in a pair with NO euro leg (GBPUSD is not in this "
                         "pack's executable list, so USDX is the available control)",
                         "a 15:00-15:05 London placebo window one hour early",
                         "a day-of-week control, because month-ends cluster on weekdays "
                         "unevenly and a raw month-end mean is partly a Friday effect"),
               notes="two fixes, two forced participants, two times of day: the corporate is "
                     "exposed to the ECB fix and the index fund to the WMR one"),
        domain("EA-C", "Sovereign spreads as the euro-area risk observable",
               objects=("the BTP-Bund 10y spread", "the OAT-Bund 10y spread",
                        "la prima de riesgo (Spain-Germany)"),
               conditions=("a political event (dissolution, censure motion, budget rejection)",
                           "a scheduled rating review Friday",
                           "the ECB's reinvestment flexibility and TPI availability"),
               instruments=("EURUSD", "EURCHF", "E35", "FRA40", "EUSTX50"),
               controls=("the same spread move on a day with no euro-area political news",
                         "US HY credit spreads on the same day, to separate euro-area "
                         "redenomination risk from global risk appetite",
                         "EURCHF versus EURSEK: the safe-haven leg should appear in the first "
                         "and not the second if the mechanism is Swiss and not merely risk-off",
                         "a pre-2012 placebo is IMPOSSIBLE on this box -- FX bars start 2018 -- "
                         "and that absence is recorded, not silently skipped"),
               notes="the spread itself is not executable here; it is an input and every edge "
                     "using it inherits a data dependency the desk does not own"),
        domain("EA-D", "Primary supply: auction concessions across four sovereigns",
               objects=("the Bund Wednesday 11:00 CET auction",
                        "the AFT first-Thursday adjudication",
                        "the Italian end-of-month BTP auction",
                        "the Spanish first-and-third-Thursday rhythm"),
               conditions=("announced size relative to the recent average",
                           "the auction's position in the quarter's programme",
                           "whether a syndication is scheduled the same week"),
               instruments=("GER40", "FRA40", "E35", "EURUSD"),
               controls=("the same weekday with no auction scheduled",
                         "the German case as a control for the Italian one: German retention "
                         "absorbs the tail, so a concession that appears in both is not about "
                         "supply",
                         "a placebo auction date shifted one week forward",
                         "the US Treasury's own auction days, to separate a euro supply effect "
                         "from a global duration effect"),
               notes="the bond leg is not executable; the equity index is the proxy and it is a "
                     "weak one, which is why the controls matter more than usual here"),
        domain("EA-E", "Index expiry: Hexensabbat and four different settlement mechanics",
               objects=("the DAX 13:00 CET intraday settlement auction",
                        "the EURO STOXX 50 11:50-12:00 CET average",
                        "the CAC 40 15:40-16:00 CET average",
                        "the IBEX 35 16:15-16:45 CET average"),
               conditions=("quarterly witching versus an ordinary monthly expiry",
                           "open interest concentration by strike",
                           "the realised move into the expiry week"),
               instruments=("GER40", "EUSTX50", "FRA40", "E35"),
               controls=("the third Friday of a NON-expiry contract month for the same index",
                         "the fourth Friday of the same month",
                         "the other three indices on the same day: a common move is a European "
                         "risk move and not a settlement mechanic",
                         "the same clock windows on the Thursday before"),
               notes="FOUR settlement windows spread over four hours on the same morning is the "
                     "single most distinctive euro-area market mechanic and the reason a pooled "
                     "'European expiry' study measures nothing"),
        domain("EA-F", "Month-end and quarter-end rebalancing",
               objects=("the last T2 business day and its T-2 hedging date",
                        "the 16:00 London fix on that date",
                        "quarter-end amplification"),
               conditions=("the month's realised equity and FX returns",
                           "quarter-end and half-year-end versus ordinary month-end",
                           "whether the last business day is itself a holiday in one leg"),
               instruments=("EURUSD", "EURGBP", "EURJPY", "GER40", "EUSTX50"),
               controls=("mid-month days matched on weekday",
                         "the same calendar day in a month where it is NOT the last business day",
                         "a pair with no rebalancing story on the same day",
                         "the T-2 date versus the T+0 date, to show the effect follows the value "
                         "date and not the calendar date"),
               notes="spot is T+2, so the hedging date is two business days BEFORE month-end; a "
                     "study anchored on the last calendar day is measuring the wrong session"),
        domain("EA-G", "The energy channel: TTF, storage and the euro terms of trade",
               objects=("AGSI+ storage fill against the seasonal norm",
                        "the 1 November EU storage target",
                        "the TTF-Henry Hub ratio as the arbitrage state"),
               conditions=("injection season versus withdrawal season",
                           "storage below or above the statutory target path",
                           "the 2021-2023 crisis era versus everything else"),
               instruments=("GER40", "NETH25", "EURUSD", "XNGUSD"),
               controls=("XNGUSD as an explicit control: a move shared with Henry Hub is a global "
                         "gas move and not a European one",
                         "XBRUSD, to separate the gas shock from a general energy shock",
                         "US indices are not in this pack, so USDX carries the dollar leg and "
                         "separates a EUR-specific move from a dollar move",
                         "the same storage anomaly outside the 2021-2023 era, where the effect "
                         "should be absent if the mechanism needs a binding constraint"),
               notes="the tradable gas leg does not exist on this desk. That is a data dependency "
                     "and it is stated rather than papered over with a Henry Hub substitution."),
        domain("EA-H", "Pension and insurer duration flows",
               objects=("the Dutch Wtp per-fund transition dates",
                        "EIOPA's monthly risk-free curve publication",
                        "quarterly solvency reporting dates"),
               conditions=("a cluster of transition dates versus none",
                           "the aggregate coverage ratio level",
                           "the rate level, because the hedging demand is convex"),
               instruments=("EURUSD", "NETH25"),
               controls=("the same calendar dates in years before the transition began",
                         "a non-Dutch euro index (GER40) on the same dates",
                         "the EIOPA publication day versus a matched non-publication day",
                         "a placebo cluster one month displaced"),
               notes="the instrument this flow actually moves -- the 30y EUR swap -- is absent "
                     "from the universe; the edges route into EURUSD and NETH25 and are weaker "
                     "for it. Recorded, not hidden."),
        domain("EA-I", "National political and fiscal calendars (DE/FR/IT/ES)",
               objects=("the German budget and any Sondervermoegen decision",
                        "the French PLF, censure motions and dissolutions",
                        "the Italian NADEF and manovra di bilancio in autumn",
                        "the Spanish Presupuestos, when one exists at all"),
               conditions=("scheduled versus unscheduled political events",
                           "whether a rating review is scheduled within two weeks",
                           "the prevailing spread level"),
               instruments=("FRA40", "E35", "EUSTX50", "EURUSD", "EURCHF"),
               controls=("the same index on a day with a comparable move in the OTHER three "
                         "countries, which separates a national event from a European one",
                         "GER40 as the national control for a French or Italian event",
                         "a placebo date one week before the scheduled event",
                         "days matched on VSTOXX level, so a political effect is not a "
                         "volatility-regime effect in disguise"),
               notes="Spanish fiscal news is IRREGULAR because budgets are routinely rolled "
                     "forward; a calendar-driven study finds nothing there and must be "
                     "event-driven instead"),
        domain("EA-J", "Euro-area data releases and their release clocks",
               objects=("the flash HICP at 11:00 CET and the national prints before it",
                        "the flash PMIs at 09:15-10:00 CET across countries",
                        "Ifo at 10:00 CET and ZEW at 11:00 CET"),
               conditions=("the surprise against a published consensus",
                           "whether the national prints already revealed the euro-area number",
                           "the proximity to the next ECB meeting"),
               instruments=("EURUSD", "GER40", "EUSTX50", "EURCHF"),
               controls=("the residual surprise after the national prints, which is the only "
                         "genuinely new information in the euro-area flash",
                         "the same clock time on a no-release day",
                         "the US session's own releases on the same day",
                         "a survey-versus-hard-data split, since Ifo and ZEW should behave "
                         "differently from industrial production if the channel is expectations"),
               notes="the German and Spanish HICP prints land BEFORE the euro-area flash; a "
                     "euro-area surprise that ignores them is mostly already public"),
        domain("EA-K", "Cross-currency basis and the year-end turn",
               objects=("the EURUSD cross-currency basis",
                        "the turn-of-year forward point",
                        "quarter-end balance-sheet compression"),
               conditions=("reporting date versus ordinary date",
                           "the level of Eurosystem excess liquidity",
                           "dollar funding stress episodes"),
               instruments=("EURUSD", "EURCHF", "EURSEK", "EURNOK"),
               controls=("the same spanning-date effect in a currency with no European reporting "
                         "constraint",
                         "a non-year-end quarter-end, where the effect should be smaller but "
                         "present if the mechanism is regulatory",
                         "the days immediately before and after the spanning window",
                         "a year with no reporting-date change, as a stability check"),
               notes="one of very few genuinely annual and genuinely mechanical FX effects; it is "
                     "visible in H1 forward points and invisible in spot closes"),
        domain("EA-L", "Calendar asymmetry: T2 open, exchange closed, and the reverse",
               objects=("Whit Monday, 24 and 31 December (GER40 shut, FRA40 open)",
                        "3 October German Unity Day (national holiday, Xetra trading)",
                        "14 July, 15 August, 1 and 11 November (French holidays, Euronext open)"),
               conditions=("which leg of a cross-index pair is closed",
                           "whether the euro itself settles that day",
                           "proximity to a long weekend"),
               instruments=("GER40", "FRA40", "NETH25", "E35", "EURUSD"),
               controls=("the same weekday in the same month with both legs open",
                         "the day AFTER the asymmetric closure, where a catch-up should appear "
                         "if the mechanism is stale pricing rather than absent flow",
                         "a matched pair with no closure asymmetry at all",
                         "volume as the direct control: if volume is normal the closure did not "
                         "bind and the effect must be something else"),
               notes="the single most under-studied euro-area mechanic, because it requires two "
                     "calendars and every vendor ships one"),
        domain("EA-M", "The scheduled sovereign rating review calendar",
               objects=("the annual published review calendar per sovereign and agency",
                        "the after-close Friday publication forced by the EU CRA Regulation",
                        "the Monday gap"),
               conditions=("the sovereign's outlook before the review",
                           "whether a downgrade would cross an index-eligibility threshold",
                           "the spread level going in"),
               instruments=("E35", "FRA40", "EUSTX50", "EURUSD", "EURCHF"),
               controls=("Mondays after an ordinary Friday, matched on the prior week's move",
                         "the sovereign's own index versus the euro-area aggregate, to separate "
                         "national from regional",
                         "reviews that produced NO action, which are the majority and are the "
                         "right null",
                         "a placebo review date one week displaced"),
               notes="a European regulation creating a forced, dated, after-close event is a gift "
                     "to event studies and almost nobody outside rates desks trades it"),
        domain("EA-N", "Positioning and crowding in the euro complex",
               objects=("the CFTC euro net position and its percentile",
                        "the TFF leveraged-funds line",
                        "Eurex open interest as the only daily European positioning series"),
               conditions=("the position percentile against a rolling window",
                           "a volatility shock arriving into a crowded position",
                           "the policy era"),
               instruments=("EURUSD", "EURJPY", "EURCHF", "GER40"),
               controls=("the commercial line as the mechanical mirror of the speculative one: a "
                         "'signal' present in both is an artefact of the report's accounting",
                         "a randomised Tuesday-to-Friday realignment, to show the effect is not "
                         "created by the three-day publication lag",
                         "the same percentile conditioning on a currency with no COT series, "
                         "which is impossible by construction -- and that impossibility is the "
                         "declared gap for the Nordic and CEE packs",
                         "a subperiod split, because COT behaviour changed with the TFF "
                         "reclassification in 2006 and again as ETFs grew"),
               notes="crowding is a conditioning variable. Treating a COT extreme as a standalone "
                     "entry signal is the classic failure in this domain."),
    )


TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    edge("EA-E01",
         source="ECB implied-path surprise from Euribor/ESTR futures around the 14:15 CET decision",
         mechanism="a hawkish surprise raises the euro's short-rate differential against the "
                   "dollar and compresses euro-area equity multiples in the same instant",
         targets=("EURUSD", "GER40", "EUSTX50"),
         sign="surprise up -> EURUSD up, GER40 down", horizon="intraday to 3 days",
         lag="0 to 30 minutes for FX, the whole press conference for equity",
         control="the same window on the Fed's decision day, and on a non-decision Thursday",
         evidence="HYPOTHESIS",
         notes="the futures leg is a TRANSMISSION_TARGET; without it the surprise cannot be "
               "constructed and the whole edge is UNMEASURED, not zero"),
    edge("EA-E02",
         source="the BTP-Bund 10y spread widening by more than 15bp in a session",
         mechanism="redenomination and periphery risk is a euro-negative that shows up first in "
                   "the Swiss cross, because CHF is the euro area's own safe haven",
         targets=("EURCHF", "EURUSD", "E35"),
         sign="spread wider -> EURCHF down, EURUSD down, E35 down",
         horizon="same day to 5 days", lag="minutes",
         control="US high-yield spreads on the same day, and EURSEK as the non-safe-haven leg",
         evidence="HYPOTHESIS",
         notes="the spread is not executable here; this edge depends on an external series"),
    edge("EA-E03",
         source="Dutch TTF front-month gas price in the April-October injection season",
         mechanism="a euro-area terms-of-trade shock raises the industrial cost base and the "
                   "import bill at once, so equity and currency fall together",
         targets=("GER40", "NETH25", "EURUSD"),
         sign="TTF up -> GER40 down, EURUSD down", horizon="days to weeks",
         lag="same session",
         control="XNGUSD (Henry Hub) as the global-gas control and XBRUSD as the general-energy "
                 "control; an effect shared with either is not European",
         evidence="MEASURED_ELSEWHERE",
         notes="the 2022 episode is widely documented in public research; the desk has not "
               "reproduced it and the pack says so"),
    edge("EA-E04",
         source="AGSI+ EU gas storage fill versus the five-year seasonal norm",
         mechanism="a storage deficit against a statutory 1 November target converts utilities "
                   "into price-inelastic buyers and raises the tail of the energy shock",
         targets=("GER40", "EURUSD", "XNGUSD"),
         sign="fill below norm -> GER40 down, EURUSD down", horizon="weeks",
         lag="1 day (AGSI publishes the gas day the following evening)",
         control="the same deficit in the withdrawal season, when the target does not bind",
         evidence="HYPOTHESIS",
         notes="one of the few free, dated, revision-poor European fundamental series"),
    edge("EA-E05",
         source="the last two business days before a quarter-end value date",
         mechanism="corporate and index-fund hedging is mechanically concentrated into the 16:00 "
                   "London fix, with a sign set by the quarter's realised move",
         targets=("EURUSD", "EURGBP", "EURJPY"),
         sign="quarter's equity return up -> EUR sold into the fix (hedge ratio rebalancing)",
         horizon="intraday", lag="the fix window only",
         control="mid-month days matched on weekday, and the T+0 date versus the T-2 date",
         evidence="MEASURED_ELSEWHERE",
         notes="the month-end model is old and public; the euro-area-specific claim here is the "
               "T-2 anchoring, which most published versions get wrong"),
    edge("EA-E06",
         source="the third Friday 13:00 CET DAX settlement auction",
         mechanism="dealer short gamma from the German retail certificate market pins spot toward "
                   "high-open-interest strikes until the auction releases it",
         targets=("GER40", "EUSTX50"),
         sign="realised volatility suppressed before 13:00 CET, released after",
         horizon="intraday", lag="none",
         control="the third Friday of a non-expiry month, and EUSTX50's own 11:50-12:00 window "
                 "which settles ninety minutes earlier",
         evidence="HYPOTHESIS",
         notes="the 13:00 CET auction time is what makes this testable; a close-settled index "
               "would confound the release with the close"),
    edge("EA-E07",
         source="a scheduled sovereign rating review published after the Friday close",
         mechanism="the EU CRA Regulation forces the publication into a window when no European "
                   "market is open, so the entire reaction is a Monday gap",
         targets=("E35", "FRA40", "EUSTX50", "EURUSD"),
         sign="downgrade -> Monday gap down; affirmation -> no effect",
         horizon="the Monday session", lag="the weekend",
         control="Mondays after an ordinary Friday matched on the prior week's move; reviews "
                 "that produced no action",
         evidence="HYPOTHESIS",
         notes="the review calendar is published in January for the whole year, which makes this "
               "one of the few European events that is knowable a year ahead"),
    edge("EA-E08",
         source="a cluster of announced Dutch pension Wtp transition dates",
         mechanism="a statutory reduction in liability hedging is a paying-fixed flow that "
                   "steepens the euro curve on a date nobody chose for market reasons",
         targets=("EURUSD", "NETH25"),
         sign="a transition cluster -> euro curve steeper, EURUSD supported at the long end",
         horizon="days around the date", lag="pre-hedging may run for weeks beforehand",
         control="the same calendar dates in 2022-2024, before the transition began",
         evidence="HYPOTHESIS",
         notes="the natural instrument is the 30y EUR swap and it is not executable here"),
    edge("EA-E09",
         source="the 12-month Euribor monthly average",
         mechanism="it resets a large stock of Spanish variable-rate mortgages annually, so it is "
                   "a dated cash-flow shock to Spanish households with a one-year distributed lag",
         targets=("E35", "EURUSD"),
         sign="12m Euribor up -> E35 underperforms GER40 over the following quarters",
         horizon="quarters", lag="up to 12 months by construction",
         control="GER40 as the fixed-rate-mortgage control economy; the pre-2022 low-rate era "
                 "where the reset was not binding",
         evidence="HYPOTHESIS",
         notes="the clearest case in Europe of one policy rate reaching two economies at "
               "different speeds because their mortgage contracts differ"),
    edge("EA-E10",
         source="the year-end turn in euro funding (the forward point spanning 31 December)",
         mechanism="bank balance-sheet compression over the regulatory reporting date dislocates "
                   "euro cross-currency funding on a date known a year ahead",
         targets=("EURUSD", "EURCHF", "EURSEK", "EURNOK"),
         sign="the spanning forward point is abnormal relative to neighbouring days",
         horizon="a few sessions", lag="none",
         control="quarter-ends other than year-end; the same spanning dates in the years before "
                 "the reporting framework changed",
         evidence="MEASURED_ELSEWHERE",
         notes="documented repeatedly in BIS work; the desk-specific question is whether it is "
               "visible in H1 bars of a spot pair at all"),
    edge("EA-E11",
         source="a French dissolution, censure motion or budget rejection",
         mechanism="French political risk reprices the OAT-Bund spread and reaches the index "
                   "through bank capital charges on domestic sovereign holdings",
         targets=("FRA40", "EUSTX50", "EURUSD"),
         sign="political shock -> FRA40 underperforms GER40, EURUSD down",
         horizon="days to weeks", lag="immediate on the headline",
         control="GER40 on the same day; E35 as the other-periphery control; days matched on "
                 "VSTOXX level so the effect is not a volatility regime",
         evidence="HYPOTHESIS",
         notes="unscheduled by nature, so this is an event study and never a calendar one"),
    edge("EA-E12",
         source="an announced EU/NGEU disbursement to a central European member state",
         mechanism="euro funds are converted into local currency on a schedule set by the "
                   "Recovery and Resilience Facility rather than by the market",
         targets=("EURPLN", "EURCZK", "EURHUF"),
         sign="disbursement announced -> local currency firmer against the euro",
         horizon="days to weeks", lag="the conversion is not same-day and the lag is the "
                                     "unmeasured part of this edge",
         control="the other two CEE currencies on the same day, since only the recipient should "
                 "move if the mechanism is a conversion rather than regional sentiment",
         evidence="HYPOTHESIS",
         notes="the Polish pack carries the receiving side of this edge; it is deliberately "
               "stated once in each pack rather than owned by neither"),
)

def _seeded(rows: tuple[dict[str, Any], ...]) -> tuple[dict[str, Any], ...]:
    """Copy each edge's PRIMARY executable target into `asset`.

    `libs.research.country_lab.TransmissionSeed` carries ONE `asset`; every edge here names
    several, because a mechanism that reaches only one instrument is rarely a mechanism. The
    first target is the primary and is copied into the field the framework reads, so a coerced
    row is useful on its own; the full tuple stays in `targets` and the framework folds it into
    the row's notes rather than dropping it. Nothing is lost in either direction.
    """
    return tuple({**row, "asset": row["targets"][0]} for row in rows)


TRANSMISSION_EDGES_SEED = _seeded(TRANSMISSION_EDGES_SEED)


POLICY_ERAS: tuple[dict[str, Any], ...] = (
    era("ea.smp_omt", start="2010-05-10", end="2012-09-06",
        label="Securities Markets Programme and the OMT announcement",
        what_changed="the ECB began buying periphery sovereigns and then promised to, which "
                     "changed the distribution of the BTP-Bund spread rather than its level",
        invalidates="any spread study pooled across 2012-07-26 is averaging a market with "
                    "redenomination risk and one without",
        notes="NOT TESTABLE ON THIS BOX: FX bars start 2018-01-02 and index bars 2020-09-14"),
    era("ea.negative_dfr", start="2014-06-11", end="2022-07-27",
        label="the negative deposit rate era",
        what_changed="the DFR went below zero and stayed there for eight years, inverting the "
                     "sign of every euro carry relationship",
        invalidates="a carry study pooled across 2022-07-27 has the euro as a funding currency "
                    "for most of its sample and a carry currency for the rest",
        notes="only the 2018-2022 tail is on this box's FX bars; the index bars miss it entirely"),
    era("ea.app_qe", start="2015-03-09", end="2018-12-31",
        label="APP net asset purchases",
        what_changed="the Eurosystem became the marginal buyer of euro duration",
        invalidates="auction-concession studies: with a price-insensitive buyer present, supply "
                    "effects are mechanically smaller",
        notes="NOT TESTABLE ON THIS BOX"),
    era("ea.pepp", start="2020-03-18", end="2022-03-31",
        label="PEPP net purchases (reinvestments continued to 2024-12-31)",
        what_changed="explicitly flexible purchases across jurisdictions, which capped the "
                     "spread without a formal target",
        invalidates="periphery spread studies in 2020-2022 measure a managed variable",
        notes="on this box's FX bars throughout; index bars from 2020-09-14, so the March 2020 "
              "crisis itself is missing"),
    era("ea.hiking", start="2022-07-27", end="2023-09-20",
        label="the fastest hiking cycle in the euro's history (DFR -0.50% to 4.00%)",
        what_changed="450bp in fourteen months, with the energy shock as the driver",
        invalidates="anything estimated on the 2015-2021 sample; the euro's rate differential "
                    "against the dollar reversed sign twice inside eighteen months",
        notes="fully on this box's bars and the single most informative era here"),
    era("ea.tpi", start="2022-07-21", end=None,
        label="the Transmission Protection Instrument, announced and never used",
        what_changed="an unactivated backstop that nonetheless changes the conditional "
                     "distribution of a spread widening",
        invalidates="a tail study of the BTP-Bund spread after 2022-07-21 is measuring a "
                    "truncated distribution",
        notes="an ERA WITH NO EVENTS is still an era; its effect is on the tail, not the mean"),
    era("ea.qt", start="2023-07-01", end=None,
        label="balance-sheet run-off: APP reinvestments ended, PEPP tapered and ended 2024-12-31",
        what_changed="the Eurosystem stopped being the marginal buyer; excess liquidity began a "
                     "multi-year decline that is still running",
        invalidates="ESTR-minus-DFR studies and any excess-liquidity conditioning estimated in "
                    "the abundant-reserves period",
        notes="running as of 2026-09-17; the end date is genuinely unknown, not omitted"),
    era("ea.corridor_2024", start="2024-09-18", end=None,
        label="the narrowed operating corridor (MRO-DFR spread 50bp -> 15bp)",
        what_changed="the MRO print changed by 35bp with no change in stance",
        invalidates="ANY study that uses the MRO as 'the ECB policy rate' across this date; the "
                    "series has a step in it that is pure definition",
        notes="the cheapest available way to fail a euro-area rates backtest"),
    era("ea.cutting", start="2024-06-06", end="2025-06-05",
        label="the cutting cycle back to a 2.00% deposit rate",
        what_changed="the differential against the dollar narrowed from both sides",
        invalidates="carry studies spanning it; the sign of the EURUSD carry leg changes",
        notes="the end date is the desk's reading of when cuts stopped, and it is DECLARED "
              "rather than measured -- a session that can verify it should"),
    era("ea.post_cut_hold", start="2025-06-06", end=None,
        label="the data-dependent hold",
        what_changed="the ECB's own path became the flattest of the major central banks, which "
                     "makes euro-area events smaller and dollar events larger for EURUSD",
        invalidates="an event-size study calibrated on 2022-2023 will over-size every window",
        notes="OPEN ERA. Its end is UNMEASURED by definition and must never be back-filled."),
    era("ea.energy_shock", start="2021-09-01", end="2023-06-30",
        label="the European gas crisis as a market regime",
        what_changed="the euro area's terms of trade collapsed and EURUSD traded below parity "
                     "for the first time in twenty years",
        invalidates="every energy-to-index correlation estimated inside it; outside it the same "
                    "correlation is near zero",
        notes="the era that makes the energy domain a CONDITIONAL family rather than a pooled one"),
)

CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    miner("ea_ecb_decision_clock", domain_ids=("EA-A",), kind="mechanism",
          entry="countries.ea.miners:ecb_decision_clock",
          notes="NOT WIRED. Would measure the decision-minute and press-conference windows "
                "against the four controls in EA-A and record a discovery per era."),
    miner("ea_two_fix_miner", domain_ids=("EA-B", "EA-F"), kind="mechanism",
          entry="countries.ea.miners:two_fix_miner",
          notes="NOT WIRED. The 14:15 CET reference-rate window versus the 16:00 London WMR "
                "window, on the same days, with the T-2 month-end anchoring."),
    miner("ea_calendar_asymmetry", domain_ids=("EA-L",), kind="data",
          entry="countries.ea.miners:calendar_asymmetry", cadence_s=86400.0, steerable=False,
          notes="NOT WIRED. A fixed cost: derives the three calendars from the rules in this "
                "module and emits the days on which GER40 and FRA40 disagree."),
    miner("ea_expiry_settlement", domain_ids=("EA-E",), kind="mechanism",
          entry="countries.ea.miners:expiry_settlement",
          notes="NOT WIRED. Four indices, four settlement windows, one morning."),
    miner("ea_spread_transfer", domain_ids=("EA-C", "EA-I", "EA-M"), kind="transfer",
          entry="countries.ea.miners:spread_transfer",
          notes="NOT WIRED. Requires an external BTP-Bund series; must report UNMEASURED rather "
                "than substituting an index proxy."),
    miner("ea_energy_channel", domain_ids=("EA-G",), kind="mechanism",
          entry="countries.ea.miners:energy_channel",
          notes="NOT WIRED. Conditions on the 2021-2023 era and uses XNGUSD as a control."),
    miner("ea_supply_concession", domain_ids=("EA-D",), kind="mechanism",
          entry="countries.ea.miners:supply_concession",
          notes="NOT WIRED. Four sovereigns, four auction rhythms, German retention as the "
                "built-in control."),
    miner("ea_positioning_scout", domain_ids=("EA-N",), kind="scout",
          entry="countries.ea.miners:positioning_scout", cadence_s=604800.0,
          notes="NOT WIRED. Weekly by nature: the COT snapshot is weekly and pretending "
                "otherwise manufactures a lag."),
    miner("ea_retail_forest", domain_ids=("EA-I", "EA-J"), kind="scout",
          entry="countries.ea.miners:retail_forest",
          notes="NOT WIRED. Mines the German, French, Italian and Spanish retail boards in "
                "TERMINOLOGY for verbatim mechanism claims, never for tips."),
)

#: The four fiscal sub-labs plus the Dutch pension lab. Each is a country's own mechanics inside
#: the single currency: its debt agency, its auction rhythm, its exchange, its politics and its
#: language. The euro area is where these disagree, and the disagreement is the research surface.
SUB_LABS: dict[str, dict[str, Any]] = {
    "de": {
        "name": "Germany",
        "executable": ("GER40", "EURUSD", "EURCHF"),
        "debt_agency": "Deutsche Finanzagentur",
        "auction_rule": "Wednesdays, 11:00 CET bidding deadline; Bunds, Bobls, Schaetze and "
                        "Bubills on a quarterly-published calendar. The Marktpflegequote "
                        "(market-making retention) absorbs the tail, so a German auction cannot "
                        "'fail' the way an Italian one can.",
        "exchange": "Xetra / Eurex",
        "expiry": "third Friday; the DAX final settlement price comes from the INTRADAY AUCTION "
                  "at 13:00 CET, not the close",
        "holiday_function": "countries.ea.pack:national_holidays('de', year)",
        "exchange_holiday_function": "countries.ea.pack:xetra_holidays(year)",
        "political_calendar": ("the federal budget (Haushalt) passes in the autumn",
                               "the Schuldenbremse caps the structural deficit and any "
                               "Sondervermoegen is a constitutional-scale event",
                               "Bundestag elections are scheduled four-yearly and the "
                               "coalition-collapse case is the unscheduled one"),
        "statistics": ("Destatis CPI at 08:00 CET, which precedes the euro-area flash",
                       "Ifo at 10:00 CET", "ZEW at 11:00 CET",
                       "factory orders and industrial production at 08:00 CET"),
        "language": "de",
        "terminology_keys": ("de_policy", "de_rates", "de_market", "de_macro"),
        "sources": ("https://www.bundesbank.de/", "https://www.deutsche-finanzagentur.de/",
                    "https://www.destatis.de/", "https://www.ifo.de/", "https://www.zew.de/",
                    "https://www.wallstreet-online.de/", "https://www.finanzen.net/"),
        "why_it_matters": "the euro area's risk-free anchor, its largest industrial exposure to "
                          "gas, and the one index on this desk with an auction-settled expiry",
    },
    "fr": {
        "name": "France",
        "executable": ("FRA40", "EURUSD"),
        "debt_agency": "Agence France Tresor (AFT)",
        "auction_rule": "long OATs on the FIRST THURSDAY of each month, 10:50 CET; short-dated "
                        "and index-linked paper on other Thursdays; the annual programme is "
                        "published with the budget",
        "exchange": "Euronext Paris",
        "expiry": "third Friday; CAC 40 derivatives settle on the arithmetic mean of the index "
                  "between 15:40 and 16:00 CET (declared -- verify against Euronext)",
        "holiday_function": "countries.ea.pack:national_holidays('fr', year)",
        "exchange_holiday_function": "countries.ea.pack:euronext_holidays(year)",
        "political_calendar": ("the PLF (budget bill) runs from September to December",
                               "a motion de censure can fall at any time and is the French "
                               "unscheduled event",
                               "a dissolution resets the whole calendar"),
        "statistics": ("INSEE CPI flash at 08:45 CET",
                       "INSEE business climate at 08:45 CET",
                       "the Banque de France monthly business survey"),
        "language": "fr",
        "terminology_keys": ("fr_policy", "fr_rates", "fr_market", "fr_macro"),
        "sources": ("https://www.banque-france.fr/", "https://www.aft.gouv.fr/",
                    "https://www.insee.fr/", "https://www.boursorama.com/bourse/forum/"),
        "why_it_matters": "the euro area's largest issuer and the sovereign whose spread moves on "
                          "POLITICS rather than on debt levels -- the cleanest political-risk "
                          "laboratory in the single currency",
    },
    "it": {
        "name": "Italy",
        "executable": ("EUSTX50", "EURUSD", "EURCHF"),
        "debt_agency": "Dipartimento del Tesoro",
        "auction_rule": "BOTs around the 10th-13th, BTPs around the 28th-30th, on a quarterly "
                        "programme; BTP Valore retail issues are announced windows of several "
                        "days and are a genuine dated retail flow with no German or French twin",
        "exchange": "Euronext Milan (ex Borsa Italiana)",
        "expiry": "third Friday (IDEM); FTSE MIB settles on constituents' opening auction prices",
        "holiday_function": "countries.ea.pack:national_holidays('it', year)",
        "exchange_holiday_function": "countries.ea.pack:euronext_holidays(year)",
        "political_calendar": ("NADEF in late September and the manovra di bilancio passing by "
                               "31 December",
                               "the European Commission's opinion on the draft budget in November",
                               "rating reviews on scheduled Fridays after the close"),
        "statistics": ("ISTAT CPI flash at 11:00 CET", "ISTAT industrial production",
                       "Banca d'Italia's monthly bank lending and sovereign-holdings data"),
        "language": "it",
        "terminology_keys": ("it_policy", "it_rates", "it_market", "it_macro"),
        "sources": ("https://www.bancaditalia.it/", "https://www.dt.mef.gov.it/",
                    "https://www.istat.it/", "https://forum.finanzaonline.com/"),
        "why_it_matters": "NO EXECUTABLE ITALIAN INDEX EXISTS ON THIS DESK. Italy enters through "
                          "lo spread, EURCHF and EUSTX50, and that limitation is a standing "
                          "property of every Italian hypothesis here.",
    },
    "es": {
        "name": "Spain",
        "executable": ("E35", "EURUSD"),
        "debt_agency": "Tesoro Publico",
        "auction_rule": "Letras on the first and third Tuesday, Bonos and Obligaciones on the "
                        "first and third Thursday, 10:30 CET deadline",
        "exchange": "BME / Bolsa de Madrid (MEFF for derivatives)",
        "expiry": "third Friday; IBEX 35 futures settle on the arithmetic mean of the index "
                  "between 16:15 and 16:45 CET (declared -- verify against MEFF)",
        "holiday_function": "countries.ea.pack:national_holidays('es', year)",
        "exchange_holiday_function": "countries.ea.pack:euronext_holidays(year)",
        "political_calendar": ("the Presupuestos Generales del Estado, which a fragmented "
                               "parliament has repeatedly failed to pass -- so Spanish fiscal "
                               "news is EVENT-DRIVEN and not calendar-driven",
                               "regional elections, which move the national arithmetic"),
        "statistics": ("INE CPI flash at 09:00 CET, which precedes the euro-area flash",
                       "the 12m Euribor monthly average, the mortgage reset reference",
                       "INE labour force survey, quarterly"),
        "language": "es",
        "terminology_keys": ("es_policy", "es_rates", "es_market", "es_macro"),
        "sources": ("https://www.bde.es/", "https://www.tesoro.es/", "https://www.ine.es/",
                    "https://www.rankia.com/foros/"),
        "why_it_matters": "the variable-rate mortgage stock makes Spain the euro area's "
                          "fastest-transmitting household sector, and 12m Euribor is the dated, "
                          "published instrument that does it",
    },
    "nl": {
        "name": "Netherlands (the pension lab)",
        "executable": ("NETH25", "EURUSD"),
        "debt_agency": "Dutch State Treasury Agency (DSTA)",
        "auction_rule": "DDA (Dutch Direct Auction) for new benchmarks, tap auctions monthly",
        "exchange": "Euronext Amsterdam",
        "expiry": "third Friday; AEX derivatives settle on an end-of-session average window",
        "holiday_function": "countries.ea.pack:national_holidays('nl', year)",
        "exchange_holiday_function": "countries.ea.pack:euronext_holidays(year)",
        "political_calendar": ("the Wtp pension transition, 2025-2027, with per-fund dates",
                               "Prinsjesdag on the third Tuesday of September: the budget is "
                               "presented on a fixed, ancient calendar rule"),
        "statistics": ("CBS CPI", "DNB quarterly pension coverage ratios"),
        "language": "nl",
        "terminology_keys": ("nl_policy", "nl_market", "nl_pension"),
        "sources": ("https://www.dnb.nl/", "https://www.cbs.nl/",
                    "https://live.euronext.com/"),
        "why_it_matters": "the largest scheduled duration reallocation in European fixed income "
                          "is Dutch, dated and published -- and the desk cannot trade the "
                          "instrument it moves",
    },
}


def pack() -> Any:
    """The euro-area country pack: `CountryPack` when the framework has landed, else a dict."""
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
        fiscal_year_end="12-31",
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
