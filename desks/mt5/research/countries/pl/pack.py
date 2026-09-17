"""THE CENTRAL EUROPE PACK -- Poland, with Czechia and Hungary as sub-labs inside it.

Fifteen actors with their eleven fields, thirteen domains A..M with objects, conditions,
instruments and negative controls, three sub-labs with their own central banks and calendars,
ten datasets with all six point-in-time stamps, twelve transmission edges naming real Fusion
symbols, nine policy eras, and four holiday calendars derived from their rules.

FOUR THINGS THIS PACK INSISTS ON.

  * THE NBP DECISION HAS NO FIXED ANNOUNCEMENT TIME. The Monetary Policy Council meets for two
    days and the release appears when it finishes -- usually in the afternoon, not at a clock
    time the desk can key an event window to. The governor's press conference is the NEXT DAY.
    So Poland is a TWO-DAY, VARIABLE-TIME event and any study using a fixed intraday window is
    studying a window it invented. The pack records the release time as UNMEASURED rather than
    assuming one (L1.28a).
  * THE CZECH FLOOR AND THE HUNGARIAN ONE-WEEK RATE ARE REGIME BREAKS, NOT FOOTNOTES. EUR/CZK
    was CENSORED at 27.00 from 2013-11-07 to 2017-04-06, and from 2021 to 2023 the Hungarian
    base rate was NOT the policy rate -- the one-week deposit rate was, and it reached 18%. A
    study that reads "the Hungarian policy rate" off a base-rate series for 2022 is reading the
    wrong number by up to 500 basis points.
  * THE HOLIDAY ASYMMETRY IS ENORMOUS HERE. Poland closes for Trzech Kroli, 3 May, Boze Cialo,
    15 August, 1 and 11 November; Czechia for 8 May, 5 and 6 July, 28 September, 28 October and
    17 November; Hungary for 15 March, 20 August and 23 October. TARGET2 observes NONE of them.
    On each, the euro leg of EURPLN, EURCZK or EURHUF settles normally and the local leg does
    not. That is roughly twenty one-sided settlement days a year across the three.
  * NO COT, FOR ANY OF THE THREE. Declared, not worked around.
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta
from typing import Any

from countries import actor, build_pack, dataset, domain, edge, era, miner, source_class

CODE = "PL"
NAME = "Poland (with Czechia and Hungary)"
REGION_COMMAND = "EUROPE"
CURRENCY = "PLN"

SUB_LAB_CODES: tuple[str, ...] = ("pl", "cz", "hu")

PIT_STAMPS: tuple[str, ...] = ("event_time", "period_time", "publication_time", "available_time",
                               "revision_time", "retrieval_time")

#: The twelve CEE currency legs the broker quotes, plus the German index and dollar legs the
#: region's dominant external driver actually runs through.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "EURPLN", "USDPLN", "GBPPLN", "CHFPLN",
    "EURCZK", "USDCZK",
    "EURHUF", "USDHUF", "GBPHUF", "CHFHUF", "AUDHUF", "NZDHUF",
    "GER40", "EURUSD", "USDX",
)

#: What central Europe's economics run through that Fusion does not quote.
TRANSMISSION_TARGETS: tuple[dict[str, str], ...] = (
    {"name": "WIG20 and the GPW derivatives complex", "venue": "Gielda Papierow Wartosciowych",
     "role": "the Polish equity bloc, bank- and energy-heavy; the most liquid CEE index",
     "route": "GER40 is the executable proxy and carries the shared industrial driver, not the "
              "Polish bank or state-ownership factors. Polish index mechanisms are routed into "
              "EURPLN or declared UNMEASURED."},
    {"name": "PX index", "venue": "Prague Stock Exchange",
     "role": "the Czech equity bloc -- a handful of names and NO liquid listed derivatives "
             "complex, which is itself the finding: there is no Czech expiry mechanic to hunt",
     "route": "GER40; EURCZK for the currency leg"},
    {"name": "BUX index and the BET derivatives", "venue": "Budapesti Ertektozsde",
     "role": "the Hungarian equity bloc, four names dominant",
     "route": "GER40; EURHUF for the currency leg"},
    {"name": "Polish government bonds (POLGB) and the 10y benchmark",
     "venue": "Ministry of Finance auctions, OTC secondary",
     "role": "the largest CEE local bond market; foreign ownership fell sharply after 2016 and "
             "domestic banks now hold the bulk, which changed who the marginal seller is",
     "route": "EURPLN, USDPLN"},
    {"name": "Czech and Hungarian government bonds (CZGB, HGB)",
     "venue": "CNB / AKK auctions",
     "role": "the Hungarian curve is unusual: a large share is held by HOUSEHOLDS through the "
             "retail programme rather than by funds, which makes it insensitive to global risk "
             "in a way no other CEE curve is",
     "route": "EURCZK, EURHUF"},
    {"name": "WIBOR, WIRON, PRIBOR and BUBOR",
     "venue": "GPW Benchmark / CNB / MNB",
     "role": "the local money-market benchmarks. WIBOR is the Polish mortgage reference and is "
             "being replaced by WIRON, a transaction-based rate -- a live benchmark transition "
             "with legal and contractual consequences.",
     "route": "EURPLN, EURCZK, EURHUF -- inputs, never legs"},
    {"name": "The CHF-mortgage litigation stock in Poland",
     "venue": "Polish courts and the CJEU",
     "role": "a legally forced conversion flow with public, dated rulings; the Swiss pack carries "
             "the other side of it",
     "route": "CHFPLN, EURPLN"},
    {"name": "EU Recovery and Resilience Facility and cohesion disbursements",
     "venue": "European Commission",
     "role": "a dated, sized, one-way euro inflow converted into local currency, and for Poland "
             "and Hungary it was politically suspended and resumed",
     "route": "EURPLN, EURHUF, EURCZK"},
)


def easter_sunday(year: int) -> date:
    """Gregorian Easter. All three countries hang closures off it, and not the same ones."""
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
    """Warsaw Stock Exchange (GPW) trading holidays -- the pack's primary calendar.

    WIELKI PIATEK (Good Friday) IS THE ODD ONE: it is NOT a statutory public holiday in Poland
    and the exchange closes anyway, the same shape as Sweden's Midsommarafton. Everything else
    is a statutory holiday, and Polish law has NO weekend substitution for any of them -- so a
    3 May on a Saturday costs the market nothing.
    """
    e = easter_sunday(year)
    table = {
        date(year, 1, 1): "Nowy Rok (New Year's Day)",
        date(year, 1, 6): "Trzech Kroli (Epiphany) -- TARGET2 open",
        e - timedelta(days=2): "Wielki Piatek (Good Friday -- exchange closed, not a statutory "
                               "public holiday)",
        e + timedelta(days=1): "Poniedzialek Wielkanocny (Easter Monday)",
        date(year, 5, 1): "Swieto Pracy (Labour Day)",
        date(year, 5, 3): "Swieto Konstytucji 3 Maja -- TARGET2 open",
        e + timedelta(days=60): "Boze Cialo (Corpus Christi) -- TARGET2 open",
        date(year, 8, 15): "Wniebowziecie NMP / Swieto Wojska Polskiego -- TARGET2 open",
        date(year, 11, 1): "Wszystkich Swietych (All Saints) -- TARGET2 open",
        date(year, 11, 11): "Narodowe Swieto Niepodleglosci -- TARGET2 open",
        date(year, 12, 24): "Wigilia (Christmas Eve -- exchange closed)",
        date(year, 12, 25): "Boze Narodzenie (Christmas Day)",
        date(year, 12, 26): "Drugi dzien Bozego Narodzenia",
    }
    return table


def national_holidays(sub_lab: str, year: int) -> dict[date, str]:
    """The national BANKING holidays of one sub-lab -- Poland, Czechia or Hungary.

    These are the days on which the local leg of EURPLN, EURCZK or EURHUF cannot settle while
    TARGET2 is open. Across the three there are roughly twenty such days a year, which makes CEE
    settlement asymmetry the largest in this department by a wide margin.
    """
    code = str(sub_lab).lower()
    e = easter_sunday(year)
    if code == "pl":
        return dict(holidays(year))
    if code == "cz":
        return {
            date(year, 1, 1): "Den obnovy samostatneho ceskeho statu (New Year)",
            e - timedelta(days=2): "Velky patek (Good Friday -- a statutory holiday in Czechia "
                                   "since 2016, unlike in Poland)",
            e + timedelta(days=1): "Velikonocni pondeli (Easter Monday)",
            date(year, 5, 1): "Svatek prace (Labour Day)",
            date(year, 5, 8): "Den vitezstvi (Victory Day) -- TARGET2 open",
            date(year, 7, 5): "Den slovanskych verozvestu Cyrila a Metodeje -- TARGET2 open",
            date(year, 7, 6): "Den upaleni mistra Jana Husa -- TARGET2 open",
            date(year, 9, 28): "Den ceske statnosti (St Wenceslas) -- TARGET2 open",
            date(year, 10, 28): "Den vzniku samostatneho ceskoslovenskeho statu -- TARGET2 open",
            date(year, 11, 17): "Den boje za svobodu a demokracii -- TARGET2 open",
            date(year, 12, 24): "Stedry den (Christmas Eve)",
            date(year, 12, 25): "1. svatek vanocni",
            date(year, 12, 26): "2. svatek vanocni",
        }
    if code == "hu":
        return {
            date(year, 1, 1): "Ujev (New Year's Day)",
            date(year, 3, 15): "Az 1848-as forradalom unnepe -- TARGET2 open",
            e - timedelta(days=2): "Nagypentek (Good Friday)",
            e + timedelta(days=1): "Husvethetfo (Easter Monday)",
            date(year, 5, 1): "A munka unnepe (Labour Day)",
            e + timedelta(days=50): "Punkosdhetfo (Whit Monday)",
            date(year, 8, 20): "Az allamalapitas unnepe (St Stephen's Day) -- TARGET2 open",
            date(year, 10, 23): "Az 1956-os forradalom unnepe -- TARGET2 open",
            date(year, 11, 1): "Mindenszentek (All Saints) -- TARGET2 open",
            date(year, 12, 24): "Szenteste (Christmas Eve)",
            date(year, 12, 25): "Karacsony",
            date(year, 12, 26): "Karacsony masnapja",
        }
    raise KeyError(f"unknown CEE sub-lab {sub_lab!r}; this pack carries {SUB_LAB_CODES}")


def target2_open_but_local_closed(sub_lab: str, year: int) -> dict[date, str]:
    """The asymmetric days: the local banking system is shut and the euro settles normally.

    This is the pack's most distinctive calendar object. It is DERIVED by differencing the local
    calendar against the six TARGET2 closing days rather than hand-listed, so it extends to any
    year and cannot drift from the rule that produced it.
    """
    e = easter_sunday(year)
    t2 = {
        date(year, 1, 1), e - timedelta(days=2), e + timedelta(days=1),
        date(year, 5, 1), date(year, 12, 25), date(year, 12, 26),
    }
    return {d: label for d, label in national_holidays(sub_lab, year).items()
            if d not in t2 and d.weekday() < 5}


def third_friday(year: int, month: int) -> date:
    """The GPW and BET index-derivative expiry candidate."""
    first = date(year, month, 1)
    return date(year, month, 1 + (4 - first.weekday()) % 7 + 14)


def wig20_expiry(year: int, month: int) -> date:
    """WIG20 futures expiry: the third Friday of March, June, September and December, rolled
    back over any GPW closure.

    Confidence: the third-Friday quarterly rule is DECLARED from public knowledge; the final
    settlement mechanic (an average of index values from the closing phase of the session) is
    DECLARED and unverified. Re-read the GPW contract specification before keying a study to the
    settlement print rather than to the date.
    """
    day = third_friday(year, month)
    closures = set(holidays(year))
    while day.weekday() >= 5 or day in closures:
        day -= timedelta(days=1)
    return day


def _iso(table: dict[date, str]) -> dict[str, str]:
    return {d.isoformat(): n for d, n in sorted(table.items())}


HOLIDAYS_RULE: dict[str, Any] = {
    "calendar": "GPW Warsaw trading holidays, with the Czech and Hungarian banking calendars "
                "and the derived TARGET2-asymmetry tables beside them",
    "rule": "GPW closes on Nowy Rok, Trzech Kroli (6 January), WIELKI PIATEK (Good Friday -- an "
            "exchange closure that is not a statutory holiday), Poniedzialek Wielkanocny, "
            "1 May, 3 May, Boze Cialo (Easter+60), 15 August, 1 November, 11 November, and "
            "24-26 December. Polish law has NO weekend substitution, so the trading-day count "
            "varies. The Czech and Hungarian calendars are separate and are carried in "
            "`national_tables`; `asymmetry_tables` is the DERIVED difference against the six "
            "TARGET2 closing days.",
    "function": "countries.pl.pack:holidays",
    "table": {y: _iso(holidays(y)) for y in (2024, 2025, 2026)},
    "national_tables": {cc: {y: _iso(national_holidays(cc, y)) for y in (2024, 2025, 2026)}
                        for cc in SUB_LAB_CODES},
    "asymmetry_tables": {cc: {y: _iso(target2_open_but_local_closed(cc, y))
                              for y in (2024, 2025, 2026)}
                         for cc in SUB_LAB_CODES},
    "asymmetries": (
        "Roughly twenty weekday sessions a year across the three countries on which the local "
        "banking system is closed and TARGET2 is open. The euro leg of EURPLN, EURCZK or EURHUF "
        "settles and the local leg does not, so the value date moves for one side only.",
        "Wielki Piatek: GPW closed, and it is NOT a Polish public holiday -- the same shape as "
        "Sweden's Midsommarafton. A calendar built from statutory holidays gets it wrong.",
        "Velky patek IS a statutory holiday in Czechia (since 2016) and is not one in Poland. "
        "Two neighbours, one date, two legal statuses, and a vendor calendar that uses one "
        "national rule for 'CEE' is wrong about at least one of them.",
        "Hungary relocates working days (athelyezett munkanap) to build long weekends and "
        "compensates with a working Saturday. DECLARED and unverified for the exchange: verify "
        "against the BET calendar. The consequence is on VALUE DATES rather than on FX trading, "
        "since spot FX does not trade at a weekend regardless -- but a Hungarian settlement date "
        "computed on a Monday-to-Friday grid can still be wrong.",
        "3 May 2026 is a Sunday and 15 August 2026 is a Saturday: two Polish closures cost "
        "nothing that year. A per-year normalisation must use these functions, not 252.",
    ),
    "status": "DERIVED_FROM_RULE",
    "verified": {"2026-01-06": "Trzech Kroli -- GPW closed, TARGET2 open",
                 "2026-04-03": "Wielki Piatek -- GPW closed and TARGET2 also closed, the one "
                               "Good Friday where the two agree"},
}

CENTRAL_BANK: dict[str, Any] = {
    "name": "Narodowy Bank Polski (NBP)",
    "committee": "Rada Polityki Pienieznej (RPP) -- the Monetary Policy Council, ten members "
                 "including the NBP President, appointed in staggered political blocs, which "
                 "makes the Council's composition a scheduled political variable",
    "policy_rates": ("stopa referencyjna (the reference rate, the operative one)",
                     "stopa lombardowa", "stopa depozytowa", "stopa redyskontowa weksli"),
    "operational_framework": "open market operations in NBP bills steer POLONIA toward the "
                             "reference rate. A structural liquidity SURPLUS has been the norm, "
                             "so the reference rate binds from above rather than below.",
    "decision_rule": "the Council meets MONTHLY, usually over two days, and the decision is "
                     "published when that meeting concludes. The governor's press conference is "
                     "the FOLLOWING DAY, around 15:00 CET.",
    "announcement_local": "NO FIXED TIME. The release appears in the afternoon of the second "
                          "day of the meeting.",
    "announcement_utc": {"winter_cet": "UNMEASURED", "summer_cest": "UNMEASURED"},
    "press_conference_local": "the NEXT day, around 15:00 CET/CEST (declared; verify)",
    "dst_note": "Poland observes CET/CEST on euro-area switch weekends, so the Warsaw-Frankfurt "
                "offset is zero all year. THAT IS NOT THE PROBLEM HERE: the problem is that the "
                "NBP publishes at no announced clock time at all, so there is no fixed local "
                "time to convert. An event window must be built from the RELEASE TIMESTAMP of "
                "each individual decision, and until that is collected the intraday effect is "
                "UNMEASURED (L1.28a).",
    "time_change_note": "the two-day structure makes Poland a TWO-EVENT country: the decision on "
                        "day two and the press conference on day three. They routinely move "
                        "price in different directions and pooling them averages two mechanisms.",
    "projections": "the NBP projection (projekcja inflacji i PKB) is published three times a "
                   "year -- in March, July and November -- and those Councils carry the larger "
                   "surprises",
    "decisions": {
        "2024": {"dates": (),
                 "confidence": "UNMEASURED. The RPP meets monthly on dates published in an annual "
                               "schedule the desk does not hold. Read nbp.pl for the calendar; "
                               "the pack refuses to invent twelve dates a year."},
        "2025": {"dates": (), "confidence": "UNMEASURED -- as above"},
        "2026": {"dates": (), "confidence": "UNMEASURED -- as above"},
    },
    "rule_if_dates_unknown": "monthly, a two-day meeting usually in the first half of the month, "
                             "with no meeting in August in some years; the decision lands on the "
                             "second day and the press conference on the third. Projection "
                             "Councils are in March, July and November.",
    "intervention_history": "the NBP intervened to WEAKEN the zloty in December 2020 -- a rare "
                            "case of a central bank selling its own currency at the year-end "
                            "accounting date, which was widely read as a profit-management "
                            "operation as much as a policy one. It has also intervened to "
                            "strengthen the zloty in stress episodes. Interventions are not "
                            "pre-announced and are inferred from reserve data afterwards.",
    "source": "https://nbp.pl/en/monetary-policy/",
}

FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "NBP average exchange rate table A (kurs sredni NBP, tabela A)",
     "administrator": "Narodowy Bank Polski",
     "local_time": "the rate is set from a bank survey around 11:00 CET/CEST and the table is "
                   "published between 11:45 and 12:15 CET/CEST, effective the same day",
     "utc": {"winter": "10:00Z set / 10:45-11:15Z published",
             "summer": "09:00Z set / 09:45-10:15Z published"},
     "dst_note": "CET/CEST on euro-area switch weekends. Published on POLISH banking days only, "
                 "so the table has holes on Trzech Kroli, 3 May, Boze Cialo, 15 August, 1 and "
                 "11 November -- six-plus days a year on which the euro settles and the Polish "
                 "reference rate does not exist. A daily join must be an outer join.",
     "window": "a survey of bank quotes rather than a transaction window; the PUBLICATION is a "
               "range (11:45-12:15) rather than an instant, which is unusual and matters at "
               "tick resolution",
     "what_it_prices": "the zloty for tax, accounting, customs and a large volume of contractual "
                       "indexation -- including, historically, CHF mortgage instalments",
     "why_it_matters": "the CHF-mortgage litigation turns on which rate a bank applied, so this "
                       "fixing has been the subject of court rulings. It is a legal object as "
                       "much as a market one."},
    {"name": "CNB declared exchange rates (CZ)",
     "administrator": "Ceska narodni banka",
     "local_time": "declared at 14:30 CET/CEST, valid for the following business day",
     "utc": {"winter": "13:30Z", "summer": "12:30Z"},
     "dst_note": "CET/CEST. Confidence: DECLARED from public knowledge; verify against cnb.cz. "
                 "Note the 14:30 CET declaration coincides with the CNB's own policy "
                 "announcement time, so on decision days the fix and the decision share a "
                 "minute and an event study must separate them by instrument.",
     "window": "a snapshot at the declaration time",
     "what_it_prices": "the koruna for accounting and statistics",
     "why_it_matters": "the collision with the decision time is the interesting part and is the "
                       "sort of thing only a country pack would notice"},
    {"name": "MNB official exchange rates (HU)",
     "administrator": "Magyar Nemzeti Bank",
     "local_time": "fixed around 11:00 CET/CEST",
     "utc": {"winter": "10:00Z", "summer": "09:00Z"},
     "dst_note": "CET/CEST on euro-area switch weekends, so the Budapest-Frankfurt offset is"
                 "zero all year. Published on HUNGARIAN banking days only, so the series has"
                 "holes on 15 March, 20 August and 23 October that a euro series does not --"
                 "a daily join must be an outer join or those days vanish silently."
                 "Confidence: the 11:00 CET fixing time is DECLARED; verify against mnb.hu.",
     "window": "a survey-based fixing",
     "what_it_prices": "the forint for accounting and statistics",
     "why_it_matters": "Hungary's retail government bond programme is forint-denominated and "
                       "household-held, so the official rate is the one a very large domestic "
                       "investor base marks against"},
    {"name": "WIBOR and the WIRON transition (PL)",
     "administrator": "GPW Benchmark",
     "local_time": "WIBOR fixing published around 11:00 CET/CEST",
     "utc": {"winter": "10:00Z", "summer": "09:00Z"},
     "dst_note": "CET/CEST, Polish banking days. Confidence: DECLARED; verify against GPW "
                 "Benchmark.",
     "window": "panel submissions, moving to a transaction-based waterfall under WIRON",
     "what_it_prices": "term zloty funding, and through it the floating Polish mortgage stock",
     "why_it_matters": "A LIVE BENCHMARK TRANSITION. WIBOR is being replaced by WIRON, which "
                       "changes the reference in existing mortgage contracts and has its own "
                       "legal and political timeline. Any long Polish rates series has a "
                       "scheduled definitional break in it."},
    {"name": "WM/Refinitiv 16:00 London closing spot rate",
     "administrator": "LSEG (WM/Refinitiv)", "local_time": "16:00 London",
     "utc": {"winter": "16:00Z", "summer": "15:00Z"},
     "dst_note": "London is GMT (=UTC) in winter and BST (=UTC+1) in summer, on the same"
                 "switch weekends as CET/CEST, so the offset from Warsaw, Prague and Budapest"
                 "is a constant one hour all year and this fix always lands at 17:00 local."
                 "The three CEE fixes are struck HOURS earlier, so a day's move between the"
                 "local fix and the London one is a systematic gap, not noise.",
     "window": "15:57:30-16:02:30 London",
     "what_it_prices": "the benchmark emerging-market index funds convert at",
     "why_it_matters": "the three CEE currencies sit in local-currency EM bond indices, so index "
                       "rebalancing reaches them through this window and not through their own "
                       "central banks' fixes"},
)

SETTLEMENT_CONVENTIONS: dict[str, Any] = {
    "fx_spot": "T+2 for EURPLN, EURCZK and EURHUF; the value date must be good in BOTH "
               "currencies, and the local calendars close on roughly twenty weekday sessions a "
               "year that TARGET2 does not -- the largest settlement asymmetry in this department",
    "fx_value_date_note": "a Polish trade struck before Boze Cialo or 11 November values later "
                          "than the equivalent euro trade, and the extra carry is priced into "
                          "the forward points on dates `target2_open_but_local_closed` derives",
    "cls": "HUF settles in CLS. PLN AND CZK DO NOT. That is a real structural difference: a "
           "zloty or koruna FX settlement carries principal (Herstatt) risk that a forint, euro "
           "or krona one does not, and it is priced into the bid-ask and the basis. It is also "
           "why CEE FX activity concentrates in the London morning when both settlement systems "
           "are open.",
    "cash_equity": "T+2 on GPW, PSE and BET; all three follow the EU timetable to T+1 on "
                   "11 October 2027 (declared -- verify)",
    "bonds": "T+2 for POLGBs, CZGBs and HGBs through the local depositories (KDPW, CDCP, KELER)",
    "derivatives": "WIG20 futures are cash-settled on the quarterly third Friday; PX has no "
                   "liquid listed derivatives complex at all, which means CZECHIA HAS NO EXPIRY "
                   "MECHANIC TO HUNT -- an absence, recorded",
    "month_end": "EM local-currency index rebalancing lands in the 16:00 London fix on the T-2 "
                 "date; the three CEE currencies' index weights are small but their turnover is "
                 "smaller, so the relative flow is large",
}

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Gielda Papierow Wartosciowych (GPW Warsaw)", "mic": "XWAR", "tz": "Europe/Warsaw",
     "symbols": (),
     "session_local": "09:00-17:00 CET continuous, closing auction 17:00-17:05",
     "expiry_rule": "the third Friday of March, June, September and December for WIG20 futures, "
                    "rolled back over a GPW closure. `wig20_expiry` computes it.",
     "settlement_price_rule": "the final settlement value is an average of WIG20 values taken "
                              "from the closing phase of the session on the last trading day. "
                              "CONFIDENCE: DECLARED AND UNVERIFIED -- re-read the GPW contract "
                              "specification before keying a study to the print.",
     "witching": "the quarterly cycle; GPW's is smaller and less discussed than the European one",
     "notes": "NO EXECUTABLE SYMBOL. WIG20 is absent from the broker universe."},
    {"name": "Burza cennych papiru Praha (Prague Stock Exchange)", "mic": "XPRA",
     "tz": "Europe/Prague", "symbols": (),
     "session_local": "09:00-16:20 CET",
     "expiry_rule": "NONE THAT MATTERS. The PX index has no liquid listed derivatives complex.",
     "settlement_price_rule": "not applicable",
     "witching": "none",
     "notes": "THE ABSENCE IS THE FINDING. Czechia is the one CEE country with no expiry "
              "mechanic to hunt, which makes it a clean control for any claim that a CEE "
              "calendar effect is driven by derivative expiry rather than by the calendar."},
    {"name": "Budapesti Ertektozsde (Budapest Stock Exchange)", "mic": "XBUD",
     "tz": "Europe/Budapest", "symbols": (),
     "session_local": "09:00-17:00 CET",
     "expiry_rule": "the third Friday for BUX futures (declared; verify against BET)",
     "settlement_price_rule": "settlement against the BUX value on the expiry day; declared",
     "witching": "the quarterly cycle",
     "notes": "NO EXECUTABLE SYMBOL. BET may also designate working Saturdays under the "
              "Hungarian relocated-working-day rule -- declared and unverified, and the "
              "consequence is on value dates rather than on FX trading."},
)

POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "NO CFTC POSITIONING SERIES FOR PLN, CZK OR HUF -- declared absence",
     "covers": "nothing. None of the three has a CFTC-reportable futures contract with a usable "
               "position series.",
     "published": "never", "lag_days": 0.0, "licence": "n/a", "root": "n/a",
     "note": "A DECLARED GAP covering the whole pack. Every CEE crowding hypothesis here is "
             "UNMEASURED on positioning (L1.28a). The named substitutes and their defects: "
             "local central bank foreign-ownership statistics (monthly, lagged, and they measure "
             "BONDS rather than FX); EPFR fund flows (licensed, not public); the EUR COT, which "
             "is a European risk proxy and not a CEE positioning series and must only ever be "
             "used as a NEGATIVE control."},
    {"name": "Ministry of Finance monthly foreign-holdings statistics (PL)",
     "covers": "non-resident holdings of Polish government bonds",
     "published": "monthly, with about a five-week lag", "lag_days": 35.0, "licence": "public",
     "root": "https://www.gov.pl/web/finanse",
     "note": "the share fell sharply after 2016 and domestic banks took up the slack, which "
             "CHANGED WHO THE MARGINAL SELLER IS. A crowding model fitted before that shift is "
             "describing a different market."},
    {"name": "CNB and MNB foreign-holdings and reserve statistics",
     "covers": "non-resident holdings and official reserves for CZ and HU",
     "published": "monthly", "lag_days": 30.0, "licence": "public",
     "root": "https://www.cnb.cz/en/statistics/",
     "note": "the Hungarian case is unusual: a large share of the local curve is held by "
             "HOUSEHOLDS through the retail bond programme, which makes it structurally "
             "insensitive to global risk appetite in a way no other CEE curve is"},
    {"name": "NBP reserve statistics as the intervention trace",
     "covers": "NBP official reserve assets, monthly",
     "published": "monthly, around the 7th working day", "lag_days": 10.0, "licence": "public",
     "root": "https://nbp.pl/en/statistic-and-financial-reporting/",
     "note": "the NBP does not pre-announce interventions, so the reserve change is the only "
             "public trace and it is monthly, contaminated by valuation, and far too slow to "
             "time anything. It supports an ACTOR claim and never a timing one."},
)

NATIVE_LANGUAGES: tuple[str, ...] = ("pl", "cs", "hu", "en")

#: Polish, Czech and Hungarian market vocabulary, written with its real diacritics. A miner
#: asking a Czech source for "exchange rate commitment" finds nothing; it must ask for
#: "kurzovy zavazek" with its hacek and its acute, because that is what the source says.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "pl_policy": ("Rada Polityki Pieniężnej", "RPP", "stopa referencyjna", "stopa lombardowa",
                  "decyzja RPP", "konferencja prezesa NBP", "projekcja inflacji",
                  "posiedzenie RPP", "łagodzenie polityki pieniężnej", "zacieśnianie"),
    "pl_fx": ("złoty", "umocnienie złotego", "osłabienie złotego", "kurs średni NBP",
              "tabela A", "interwencja walutowa", "rezerwy walutowe", "kurs referencyjny"),
    "pl_rates": ("WIBOR", "WIRON", "trzymiesięczny WIBOR", "obligacje skarbowe", "przetarg",
                 "Ministerstwo Finansów", "BGK", "rentowność dziesięciolatek", "spread"),
    "pl_credit": ("kredyt hipoteczny", "wakacje kredytowe", "frankowicze", "kredyt frankowy",
                  "unieważnienie umowy", "TSUE", "Sąd Najwyższy", "rezerwy na ryzyko prawne"),
    "pl_market": ("GPW", "WIG20", "wygaśnięcie kontraktów", "dzień wygaśnięcia",
                  "kurs rozliczeniowy", "Wielki Piątek", "Boże Ciało", "sesja giełdowa"),
    "pl_macro": ("GUS", "inflacja bazowa", "CPI", "produkcja przemysłowa", "KPO",
                 "Krajowy Plan Odbudowy", "fundusze unijne", "deficyt budżetowy"),
    "cs_policy": ("ČNB", "bankovní rada", "dvoutýdenní repo sazba", "2T repo sazba",
                  "měnové rozhodnutí", "tisková konference", "prognóza ČNB", "úroková sazba"),
    "cs_fx": ("kurzový závazek", "devizové intervence", "koruna", "oslabení koruny",
              "posílení koruny", "devizové rezervy", "kurz koruny"),
    "cs_market": ("PRIBOR", "PX index", "Burza cenných papírů Praha", "státní dluhopisy",
                  "refixace hypoték", "hypotéka", "Ministerstvo financí", "ČSÚ", "inflace"),
    "hu_policy": ("MNB", "Monetáris Tanács", "alapkamat", "egyhetes betéti kamat",
                  "kamatdöntés", "kamatfolyosó", "inflációs jelentés", "szigorítás"),
    "hu_fx": ("forint", "forintgyengülés", "forinterősödés", "devizatartalék",
              "hivatalos árfolyam", "intervenció"),
    "hu_market": ("BUBOR", "BUX", "Budapesti Értéktőzsde", "ÁKK", "MÁP Plusz",
                  "lakossági állampapír", "államkötvény", "hozam"),
    "hu_macro": ("KSH", "infláció", "maginfláció", "uniós források", "helyreállítási alap",
                 "költségvetési hiány", "áthelyezett munkanap", "munkaszüneti nap"),
    "en_desk": ("the CEE beta", "the German industrial channel", "EU funds conversion", "the "
                "koruna floor", "the one-week deposit rate", "no COT for CEE"),
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
    _src("cee.official.central_banks", "NBP, CNB and MNB decisions, minutes and statistics",
         layer="official",
         roots=("https://nbp.pl/en/monetary-policy/", "https://nbp.pl/polityka-pieniezna/",
                "https://www.cnb.cz/en/monetary-policy/", "https://www.cnb.cz/cs/menova-politika/",
                "https://www.mnb.hu/en/monetary-policy", "https://www.mnb.hu/monetaris-politika"),
         languages=("pl", "cs", "hu", "en"), licence="public, attribution",
         access_label="OPEN_DATA", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         weight=1.0,
         queries=("decyzja RPP komunikat po posiedzeniu stopa referencyjna",
                  "harmonogram posiedzeń Rady Polityki Pieniężnej",
                  "měnové rozhodnutí bankovní rady 2T repo sazba tisková konference",
                  "kurzový závazek ukončení intervence archiv",
                  "kamatdöntés Monetáris Tanács közlemény alapkamat",
                  "egyhetes betéti kamat tender eredmény"),
         notes="THE NBP RELEASE HAS NO ANNOUNCED CLOCK TIME, so the crawler's own fetch stamp is "
               "the only timestamp the desk owns for a Polish decision -- which is why the NBP "
               "dataset row carries pit_feasible=False. The CNB and MNB both announce at fixed "
               "times and are therefore better identified than the largest economy of the three."),
    _src("cee.official.state_and_stats",
         "Finance ministries, debt agencies and the three statistical offices",
         layer="official",
         roots=("https://www.gov.pl/web/finanse", "https://www.mfcr.cz/", "https://akk.hu/",
                "https://stat.gov.pl/", "https://www.czso.cz/", "https://www.ksh.hu/",
                "https://www.knf.gov.pl/"),
         languages=("pl", "cs", "hu", "en"), licence="public, attribution",
         access_label="OPEN_DATA", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         weight=1.0,
         queries=("kalendarz przetargów obligacji skarbowych Ministerstwo Finansów",
                  "wymiana walut z UE przez NBP czy rynek komunikat",
                  "emisní kalendář státních dluhopisů ministerstvo financí",
                  "lakossági állampapír MÁP Plusz állomány heti adat ÁKK",
                  "szybki szacunek inflacji GUS publikacja godzina"),
         notes="the Polish ministry sometimes DISCLOSES whether an EU-funds euro inflow was "
               "converted at the NBP or in the market -- a rare piece of public information "
               "about HOW a flow reaches the price, and the conditioning variable in domain "
               "PL-E. AKK publishes the retail bond stock weekly."),
    _src("cee.institutional.venue_and_bodies",
         "GPW, PSE, BET, the benchmark administrators and the banking associations",
         layer="institutional",
         roots=("https://www.gpw.pl/", "https://gpwbenchmark.pl/", "https://www.pse.cz/",
                "https://bet.hu/", "https://www.zbp.pl/", "https://cbaonline.cz/",
                "https://www.bankszovetseg.hu/"),
         languages=("pl", "cs", "hu", "en"), licence="public page, restricted redistribution",
         access_label="PUBLIC_WITH_TERMS", credibility="AUTHORITATIVE",
         predictive_state="UNTESTED", weight=1.0,
         queries=("standard kontraktu terminowego WIG20 kurs rozliczeniowy wygaśnięcie",
                  "WIRON reforma wskaźnika referencyjnego harmonogram GPW Benchmark",
                  "BUX határidős kontraktus specifikáció lejárat",
                  "PX index deriváty burza Praha likvidita"),
         notes="GPW Benchmark administers BOTH WIBOR and WIRON and publishes the transition "
               "timetable, which is the definitional break in era pl.wibor_to_wiron. The Prague "
               "exchange page is here to DOCUMENT AN ABSENCE: the PX has no liquid listed "
               "derivatives complex, and that absence is the control in domain PL-K."),
    _src("cee.academic.research", "CEE central bank research and the regional institutes",
         layer="academic",
         roots=("https://nbp.pl/en/publications/working-papers/",
                "https://www.cnb.cz/en/economic-research/",
                "https://www.mnb.hu/en/publications/mnb-financial-and-economic-review",
                "https://www.cerge-ei.cz/", "https://www.sgh.waw.pl/"),
         languages=("pl", "cs", "hu", "en"), licence="public, attribution",
         access_label="PUBLIC", credibility="RELIABLE", predictive_state="UNTESTED", weight=0.9,
         queries=("kurzový závazek vyhodnocení dopad ČNB výzkum",
                  "exchange rate commitment Czech National Bank assessment working paper",
                  "wpływ kredytów frankowych na banki analiza NBP",
                  "egyhetes betéti eszköz monetáris transzmisszió tanulmány"),
         notes="the CNB's own research on the 2013-2017 commitment is the best public account "
               "anywhere of what a HARD FX FLOOR does to a small open economy, and it is the "
               "only way to study era cz.koruna_floor at all -- this box's exotic bars begin "
               "2020-09-14, five years after the floor ended."),
    _src("cee.practitioner.bank_research",
         "Polish, Czech and Hungarian bank research desks and the professional bodies",
         layer="practitioner",
         roots=("https://www.mbank.pl/serwis-ekonomiczny/",
                "https://www.pkobp.pl/centrum-analiz/", "https://think.ing.com/",
                "https://www.erstegroup.com/en/research",
                "https://www.kb.cz/cs/o-bance/ekonomicke-analyzy",
                "https://www.otpbank.hu/portal/hu/Elemzesek"),
         languages=("pl", "cs", "hu", "en"),
         licence="mixed: public commentary, licensed full notes",
         access_label="ACCESS_UNCLEAR", credibility="RELIABLE", predictive_state="UNTESTED",
         weight=0.6,
         queries=("komentarz do decyzji RPP prognoza stóp analitycy",
                  "prognoza kursu EURPLN analiza banku",
                  "komentář k rozhodnutí ČNB sazby výhled",
                  "forint árfolyam előrejelzés elemzés kamatdöntés"),
         notes="mBank's serwis ekonomiczny is unusually open and is the closest thing to a "
               "public Polish dealer view; ING's CEE desk publishes the most consistent "
               "cross-country commentary on the three currencies at once, which is exactly the "
               "shared-factor question in domain PL-G."),
    _src("cee.retail_ecology.communities",
         "Polish, Czech and Hungarian retail forums and the CHF-borrower communities",
         layer="retail_ecology",
         roots=("https://www.bankier.pl/forum/", "https://www.stockwatch.pl/forum/",
                "https://www.kurzy.cz/diskuse/", "https://www.patria.cz/diskuse.html",
                "https://www.portfolio.hu/forum", "https://www.reddit.com/r/Polska/"),
         languages=("pl", "cs", "hu"), licence="public forum, quote-and-cite only",
         access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE", predictive_state="UNTESTED",
         weight=0.25, machine_use_allowed=False,
         queries=("frankowicze pozew unieważnienie umowy forum doświadczenia",
                  "wakacje kredytowe czy się opłaca dyskusja",
                  "wygaśnięcie kontraktów WIG20 spekulacje",
                  "refixace hypotéky 2026 diskuse sazba",
                  "forint gyengülés miért fórum"),
         notes="machine_use_allowed=False: bankier and stockwatch both forbid automated "
               "extraction in their terms, so they are REGISTERED and never scraped. THE "
               "FRANKOWICZE FORUMS ARE THE MOST VALUABLE ITEM IN THIS LAYER ANYWHERE IN THE "
               "DEPARTMENT: Polish CHF-mortgage litigation requires INDIVIDUAL filings, so "
               "public retail coordination genuinely leads the balance-sheet flow in domain "
               "PL-I. Kept at weight 0.25 and never dropped; a contradicted legal claim in a "
               "forum is still evidence about how many people will file."),
    _src("cee.app_ecosystem.platforms", "CEE broker platforms, neobanks and comparison sites",
         layer="app_ecosystem",
         roots=("https://www.xtb.com/pl", "https://www.mbank.pl/inwestycje/",
                "https://www.revolut.com/", "https://www.portu.cz/", "https://www.fio.cz/",
                "https://www.tradingview.com/symbols/GPW-WIG20/"),
         languages=("pl", "cs", "hu", "en"), licence="per-platform terms",
         access_label="PUBLIC_WITH_TERMS", credibility="UNKNOWN",
         predictive_state="NARRATIVE_FEATURE", weight=0.4,
         queries=("XTB najczęściej handlowane instrumenty statystyka",
                  "porównanie kont maklerskich prowizje ranking",
                  "Fio e-Broker nejobchodovanější tituly",
                  "Portu portfolio složení statistika"),
         notes="XTB is a Polish-headquartered retail CFD broker with a large regional book, so "
               "its public statistics are a genuine read on CEE retail positioning in exactly "
               "the instruments this desk trades. Labelled NARRATIVE_FEATURE because attention "
               "is not a forecast until it has been tested as one."),
    _src("cee.media.business_press", "Polish, Czech and Hungarian business press",
         layer="media",
         roots=("https://www.parkiet.com/", "https://www.rp.pl/", "https://www.pb.pl/",
                "https://hn.cz/", "https://www.e15.cz/", "https://www.vg.hu/",
                "https://www.portfolio.hu/"),
         languages=("pl", "cs", "hu"), licence="paywalled; terms forbid bulk extraction",
         access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
         predictive_state="NARRATIVE_FEATURE", weight=0.5, machine_use_allowed=False,
         queries=("Parkiet komentarz po decyzji RPP rynek obligacji",
                  "kurs złotego dziś komentarz analityków",
                  "koruna oslabila důvod komentář",
                  "forint árfolyam hír elemzés"),
         notes="machine_use_allowed=False: Parkiet, Puls Biznesu, HN and Vilaggazdasag all "
               "paywall with terms forbidding bulk extraction. Registered, never scraped. "
               "portfolio.hu is the best Hungarian market analysis outside the MNB and its "
               "open surface is the most usable part of this layer."),
    _src("cee.archive.historical", "CEE historical statistics and digitised national press",
         layer="archive",
         roots=("https://nbp.pl/en/statistic-and-financial-reporting/",
                "https://polona.pl/", "https://www.digitalniknihovna.cz/",
                "https://adt.arcanum.com/", "https://web.archive.org/"),
         languages=("pl", "cs", "hu"), licence="public archive",
         access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         weight=0.8,
         queries=("archiwum komunikatów RPP interwencja walutowa grudzień 2020",
                  "ČNB archiv kurzový závazek listopad 2013 tisková zpráva",
                  "MNB egyhetes betéti kamat 2022 október 18 százalék archívum",
                  "Arcanum digitális tudománytár tőzsde forint történeti"),
         notes="THE ARCHIVE IS NOT OPTIONAL HERE. This box's exotic FX bars begin 2020-09-14, so "
               "the Czech floor (2013-2017), the December 2020 Polish intervention and the "
               "pre-2020 Hungarian instrument history are all outside the sample. Arcanum's "
               "digitised Hungarian press is among the deepest national archives in Europe."),
    _src("cee.physical_economy.industry_energy_freight",
         "CEE industrial production, power grids, gas transit and rail freight",
         layer="physical_economy",
         roots=("https://www.pse.pl/", "https://www.ceps.cz/en/", "https://www.mavir.hu/",
                "https://www.gaz-system.pl/", "https://www.tge.pl/",
                "https://www.pkpcargo.com/", "https://www.skoda-auto.com/"),
         languages=("pl", "cs", "hu", "en"), licence="public / registration",
         access_label="OPEN_DATA", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         weight=0.9,
         queries=("PSE raporty dobowe zapotrzebowanie mocy system",
                  "Gaz-System przepustowość gazociąg przesył dane",
                  "TGE ceny energii elektrycznej notowania",
                  "Škoda Auto výroba vozů měsíční statistika",
                  "MAVIR rendszerterhelés adatok"),
         notes="THE GERMAN INDUSTRIAL CHANNEL IN DOMAIN PL-G HAS A PHYSICAL COUNTERPART and this "
               "is it: Czech vehicle production, Polish rail freight and the three grid "
               "operators' load data are the region's real economy measured directly rather "
               "than surveyed. All three grids publish free, high-frequency, revision-free load."),
    _src("cee.source_graph.citation_and_link", "Citation and link graphs over the CEE corpus",
         layer="source_graph",
         roots=("https://ideas.repec.org/s/nbp/nbpmis.html", "https://openalex.org/",
                "https://cohesiondata.ec.europa.eu/",
                "https://github.com/search?q=WIBOR+OR+PRIBOR+OR+BUBOR"),
         languages=("pl", "cs", "hu", "en"), licence="open data",
         access_label="OPEN_DATA", credibility="RELIABLE", predictive_state="UNTESTED",
         weight=0.5,
         queries=("RePEc cited by CNB working paper exchange rate commitment",
                  "OpenAlex citations CEE currencies German business cycle",
                  "cohesion data payments Poland Hungary milestone linked datasets",
                  "github polish holiday calendar boże ciało python"),
         notes="the Commission's cohesion data portal is a LINK graph as much as a data set: it "
               "connects a payment decision to its milestone documents and to the member state's "
               "own filings, which is how a disbursement in domain PL-E is dated precisely "
               "rather than approximately."),
)

#: All ten layers are populated across the three CEE countries, so this table is empty BY
#: MEASUREMENT. Note that coverage is uneven WITHIN a layer -- the Czech derivatives complex
#: does not exist and the institutional row says so by name rather than leaving a hole.
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
    _ds("NBP policy decisions and the two-day meeting structure",
        source="NBP press releases", coverage="every RPP decision",
        frequency="monthly", publication_lag_days=0.0,
        revisions="never revised; the MINUTES arrive weeks later and are a separate event",
        licence="public, attribution", history_from="1998", pit_feasible=False,
        assets=("EURPLN", "USDPLN", "CHFPLN"),
        mechanism_families=("policy_surprise", "two_day_event", "event_drift"),
        how_to_fetch="nbp.pl press release pages; THE RELEASE TIMESTAMP MUST BE CAPTURED PER "
                     "DECISION, because there is no announced clock time",
        pit={"event_time": "the afternoon of day two of the meeting -- NO FIXED TIME. This is "
                           "why pit_feasible is False: without a collected release timestamp the "
                           "event_time stamp cannot be filled and the row can only produce "
                           "NOT_PIT_SAFE cells.",
             "period_time": "the month the decision applies from",
             "publication_time": "variable, afternoon CET",
             "available_time": "same as publication",
             "revision_time": "never",
             "retrieval_time": "crawler stamp -- and for this dataset the crawler stamp is the "
                               "ONLY timestamp the desk actually owns"}),
    _ds("CNB policy decisions and the published forecast",
        source="Czech National Bank", coverage="every CNB decision",
        frequency="8 per year", publication_lag_days=0.0,
        revisions="never; the forecast is superseded quarterly",
        licence="public, attribution", history_from="1993", pit_feasible=True,
        assets=("EURCZK", "USDCZK"),
        mechanism_families=("policy_surprise", "path_revision", "event_drift"),
        how_to_fetch="cnb.cz monetary policy pages",
        pit={"event_time": "14:30 CET announcement -- a FIXED time, unlike Poland's",
             "period_time": "the forecast horizon",
             "publication_time": "14:30 CET, press conference 15:45 CET",
             "available_time": "14:30 CET, and note the CNB's own daily FX declaration shares "
                               "that minute, so the two must be separated by instrument",
             "revision_time": "never",
             "retrieval_time": "crawler stamp"}),
    _ds("MNB policy decisions, base rate and one-week deposit rate",
        source="Magyar Nemzeti Bank", coverage="every Monetary Council decision",
        frequency="monthly", publication_lag_days=0.0,
        revisions="never revised. THE INSTRUMENT CHANGED: from 2021 to September 2023 the "
                  "effective policy rate was the ONE-WEEK DEPOSIT RATE and not the base rate. A "
                  "single 'Hungarian policy rate' series is wrong by up to 500bp in 2022.",
        licence="public, attribution", history_from="2001", pit_feasible=True,
        assets=("EURHUF", "USDHUF", "CHFHUF"),
        mechanism_families=("policy_surprise", "instrument_change", "crisis_response"),
        how_to_fetch="mnb.hu monetary policy pages; BOTH rate series must be collected",
        pit={"event_time": "14:00 CET announcement (declared; verify)",
             "period_time": "the month; for the one-week rate, the tender week",
             "publication_time": "14:00 CET, press conference 15:00 CET",
             "available_time": "same",
             "revision_time": "never",
             "retrieval_time": "crawler stamp"}),
    _ds("EU Recovery and Resilience Facility disbursements by member state",
        source="European Commission RRF scoreboard",
        coverage="dated, sized disbursements to Poland, Czechia and Hungary",
        frequency="event-driven", publication_lag_days=0.0,
        revisions="the schedule is revised when milestones slip, and the SUSPENSION and "
                  "resumption for Poland and Hungary were political decisions with their own "
                  "announcement dates -- which are separate, tradable events from the payments",
        licence="public", history_from="2021", pit_feasible=True,
        assets=("EURPLN", "EURHUF", "EURCZK"),
        mechanism_families=("announced_flow", "forced_flow", "political_event"),
        how_to_fetch="Commission RRF scoreboard and the payment press releases",
        pit={"event_time": "the disbursement decision date",
             "period_time": "the milestone period being paid for",
             "publication_time": "the Commission's announcement",
             "available_time": "same",
             "revision_time": "milestone slippage changes future dates",
             "retrieval_time": "crawler stamp"}),
    _ds("Polish CHF-mortgage court rulings and bank litigation provisions",
        source="CJEU, Polish Supreme Court, bank quarterly reports",
        coverage="rulings and the provisioning they force",
        frequency="event-driven", publication_lag_days=0.0,
        revisions="provisions are restated each quarter as the case flow develops",
        licence="public", history_from="2019 (the CJEU Dziubak ruling is the reference point)",
        pit_feasible=True, assets=("CHFPLN", "EURPLN"),
        mechanism_families=("legal_forced_flow", "event_drift", "conversion"),
        how_to_fetch="CJEU and Supreme Court judgment pages; bank reports for the provisions",
        pit={"event_time": "the ruling's publication, at a scheduled hearing time",
             "period_time": "the contracts the ruling applies to",
             "publication_time": "the hearing date",
             "available_time": "same; major rulings are scheduled in advance, which makes them "
                               "rare examples of a KNOWABLE legal event date",
             "revision_time": "provisions restated quarterly",
             "retrieval_time": "crawler stamp"}),
    _ds("GUS, CZSO and KSH consumer price indices",
        source="the three statistical offices", coverage="PL, CZ, HU", frequency="monthly",
        publication_lag_days=13.0,
        revisions="Poland publishes a FLASH and then a FINAL, and the gap between them is a "
                  "routine source of spurious surprise measures; GUS also rebases annually in "
                  "a way that rewrites the recent history",
        licence="public, attribution", history_from="1990s", pit_feasible=True,
        assets=("EURPLN", "EURCZK", "EURHUF"),
        mechanism_families=("data_surprise", "policy_expectation"),
        how_to_fetch="stat.gov.pl, czso.cz and ksh.hu release pages",
        pit={"event_time": "10:00 CET (GUS) release; CZSO and KSH publish at 09:00 CET",
             "period_time": "the reference month",
             "publication_time": "as above",
             "available_time": "same",
             "revision_time": "the Polish final print roughly two weeks later; annual rebasing",
             "retrieval_time": "crawler stamp"}),
    _ds("WIBOR, PRIBOR and BUBOR fixings",
        source="GPW Benchmark, CNB, MNB", coverage="CEE term money market",
        frequency="daily on local banking days", publication_lag_days=0.0,
        revisions="not revised. WIBOR IS BEING REPLACED BY WIRON, which is a scheduled "
                  "definitional break in the Polish series with legal consequences for existing "
                  "mortgage contracts.",
        licence="mixed: WIBOR is licensed, PRIBOR and BUBOR are public",
        history_from="1990s", pit_feasible=True,
        assets=("EURPLN", "EURCZK", "EURHUF"),
        mechanism_families=("funding", "policy_transmission", "benchmark_transition"),
        how_to_fetch="GPW Benchmark, cnb.cz and mnb.hu daily publications",
        pit={"event_time": "the fixing day",
             "period_time": "the term the rate prices",
             "publication_time": "around 11:00 CET",
             "available_time": "same",
             "revision_time": "never; the WIBOR-to-WIRON transition is a break, not a revision",
             "retrieval_time": "crawler stamp"}),
    _ds("Hungarian retail government bond programme (MAP Plusz) stock",
        source="AKK", coverage="household holdings of Hungarian government debt",
        frequency="weekly and monthly", publication_lag_days=7.0,
        revisions="none",
        licence="public", history_from="2019", pit_feasible=True,
        assets=("EURHUF", "USDHUF"),
        mechanism_families=("household_flow", "funding_structure", "regime_condition"),
        how_to_fetch="akk.hu statistics pages",
        pit={"event_time": "the week the subscription occurred",
             "period_time": "the week or month",
             "publication_time": "weekly, within about a week",
             "available_time": "same",
             "revision_time": "never",
             "retrieval_time": "crawler stamp"}),
    _ds("Czech mortgage refixation volumes",
        source="CNB banking statistics and the Czech Banking Association",
        coverage="the stock of fixed-rate mortgages coming up for refixation",
        frequency="monthly and quarterly", publication_lag_days=45.0,
        revisions="restated as the loan book is reclassified",
        licence="public", history_from="2015", pit_feasible=True,
        assets=("EURCZK",),
        mechanism_families=("delayed_transmission", "housing_channel", "regime_condition"),
        how_to_fetch="cnb.cz ARAD statistics database",
        pit={"event_time": "the month the refixation falls due, which is KNOWN IN ADVANCE from "
                           "the original loan dates -- a forced cash-flow shock with a publicly "
                           "computable schedule",
             "period_time": "the month",
             "publication_time": "quarterly with a six-week lag",
             "available_time": "same",
             "revision_time": "reclassification restatements",
             "retrieval_time": "crawler stamp"}),
    _ds("CNB exchange rate commitment archive (2013-2017)",
        source="Czech National Bank", coverage="the EUR/CZK 27.00 floor and its exit",
        frequency="historical", publication_lag_days=0.0,
        revisions="none; it is a closed and fully documented episode",
        licence="public", history_from="2013-11-07", pit_feasible=True,
        assets=("EURCZK", "USDCZK"),
        mechanism_families=("censored_distribution", "regime_break", "intervention"),
        how_to_fetch="cnb.cz monetary policy archive and its research papers",
        pit={"event_time": "2013-11-07 (imposition) and 2017-04-06 (exit)",
             "period_time": "the whole commitment period",
             "publication_time": "both announcements were made on the day",
             "available_time": "same; the EXIT was unscheduled and that is the point",
             "revision_time": "never",
             "retrieval_time": "crawler stamp"}),
)


def actors() -> tuple[dict[str, Any], ...]:
    """Fifteen central European participants whose constraints produce dated or measurable flow."""
    return (
        actor("Rada Polityki Pienieznej (the Polish Monetary Policy Council)",
              holds="the zloty's reference rate",
              forced_to=("meet monthly over two days",
                         "publish the decision when the meeting ends -- at no announced time",
                         "hold the governor's press conference the FOLLOWING day"),
              when="monthly; the decision on day two, the conference on day three",
              information=("GUS flash CPI at 10:00 CET",
                           "the NBP projection three times a year",
                           "the zloty's own level"),
              constraints=("a ten-member council appointed in staggered political blocs, so its "
                           "composition is a scheduled POLITICAL variable and its reaction "
                           "function changes with the appointment cycle rather than with the "
                           "economy",),
              instruments=("EURPLN", "USDPLN", "CHFPLN"),
              counterparties=("Polish banks", "the WIBOR-linked mortgage stock"),
              observables=("the decision release and its captured timestamp",
                           "the next-day press conference",
                           "the minutes, weeks later"),
              impact="a TWO-DAY event with a variable release time; the decision and the "
                     "conference routinely move price in different directions",
              persistence="days",
              falsifier="if EURPLN's day-two and day-three returns have the same sign and "
                        "magnitude distribution across a sample of meetings, the two-event "
                        "framing adds nothing and the pack should pool them after all",
              notes="the absent announcement clock is the reason the NBP dataset row carries "
                    "pit_feasible=False; that is a measurement fact, not a modelling choice"),
        actor("Ceska narodni banka Bank Board",
              holds="the koruna's two-week repo rate and a history of hard FX commitments",
              forced_to=("decide eight times a year and announce at 14:30 CET",
                         "publish a forecast with a rate path",
                         "declare the official exchange rate at the same 14:30 CET minute"),
              when="eight meetings a year, 14:30 CET",
              information=("CZSO CPI at 09:00 CET", "its own published forecast"),
              constraints=("a small, very open economy subcontracted to German manufacturing, so "
                           "the koruna's fundamentals are largely German",
                           "an institutional willingness to use the exchange rate as an "
                           "instrument outright, demonstrated 2013-2017"),
              instruments=("EURCZK", "USDCZK", "GER40"),
              counterparties=("Czech banks", "the FX market directly, when it chooses"),
              observables=("the 14:30 CET announcement",
                           "the published forecast path",
                           "reserve changes as the intervention trace"),
              impact="the most transparent of the three central banks and the one most willing "
                     "to act on the currency itself",
              persistence="the forecast horizon",
              falsifier="if EURCZK's 14:30-15:30 CET move on decision days is indistinguishable "
                        "from a matched non-decision day, the fixed announcement time buys "
                        "nothing and Czechia is no better identified than Poland",
              notes="the decision and the daily FX declaration share the 14:30 CET minute, which "
                    "an event study must separate by instrument rather than by time"),
        actor("Magyar Nemzeti Bank Monetary Council",
              holds="the forint's policy stance, through whichever instrument it is currently "
                    "using",
              forced_to=("decide monthly and announce at 14:00 CET",
                         "publish an Inflation Report quarterly"),
              when="monthly, usually a Tuesday, 14:00 CET",
              information=("KSH CPI at 09:00 CET", "the forint's level, which it reacts to"),
              constraints=("a currency with a long history of stress and a household sector that "
                           "remembers it; an EU-funds dispute that removed a large expected "
                           "inflow for two years",),
              instruments=("EURHUF", "USDHUF", "CHFHUF"),
              counterparties=("Hungarian banks", "households through the retail bond programme"),
              observables=("the 14:00 CET announcement",
                           "the one-week deposit tender, when that was the operative instrument",
                           "the Inflation Report"),
              impact="THE INSTRUMENT ITSELF IS A VARIABLE. From 2021 to September 2023 the "
                     "effective policy rate was the one-week deposit rate, which reached 18% in "
                     "October 2022 while the base rate stood far below it",
              persistence="regime-like; the instrument changes are the regime boundaries",
              falsifier="if a study using the base rate for 2022 reproduces the same forint "
                        "dynamics as one using the one-week rate, the instrument distinction is "
                        "cosmetic -- which would be surprising given a 500bp gap",
              notes="the single most expensive mistake available in CEE data work"),
        actor("Polish households with WIBOR-linked mortgages",
              holds="a floating-rate mortgage stock referenced to a benchmark that is being "
                    "replaced",
              forced_to=("accept WIBOR resets",
                         "and NOT, during the statutory payment holidays (wakacje kredytowe), "
                         "which suspended instalments by law in 2022 and again in 2024"),
              when="reset at the WIBOR tenor; the payment holidays were legislated windows",
              information=("WIBOR", "the WIRON transition timetable", "the legislation"),
              constraints=("a STATUTORY payment holiday is a fiscal transfer legislated in "
                           "response to a monetary tightening -- the government partly undoing "
                           "the central bank, on a dated schedule",),
              instruments=("EURPLN", "USDPLN"),
              counterparties=("Polish banks, who bore the cost",),
              observables=("the legislation's dates",
                           "take-up rates, published",
                           "bank earnings, which absorbed it"),
              impact="Polish monetary transmission was deliberately interrupted by fiscal "
                     "policy on dated occasions -- a natural experiment in blocking a channel",
              persistence="the legislated windows",
              falsifier="if Polish consumption and housing show the same response to WIBOR "
                        "inside and outside the payment-holiday windows, the interruption did "
                        "not bind and the transfer was inframarginal",
              notes="no other country in this department has a legislated suspension of "
                    "mortgage payments to study"),
        actor("Polish CHF-mortgage borrowers and the litigating banks",
              holds="franc-denominated mortgages against zloty income, and a legal system that "
                    "has been voiding the contracts",
              forced_to=("service or litigate",
                         "and for the banks: provision against the litigation, quarterly, in "
                         "public"),
              when="ruling-driven; major CJEU and Supreme Court judgments are SCHEDULED in "
                   "advance, which makes them rare knowable legal event dates",
              information=("the judgment calendar", "banks' disclosed provisions"),
              constraints=("a court-ordered conversion that ignores the exchange rate entirely",),
              instruments=("CHFPLN", "EURPLN"),
              counterparties=("Polish banks", "the Swiss franc market"),
              observables=("scheduled hearing dates",
                           "the rulings themselves",
                           "quarterly litigation provisions"),
              impact="a legally forced franc flow with a public, dated trigger",
              persistence="the stock shrinks with each wave of rulings, so the effect decays "
                          "mechanically over the sample",
              falsifier="if CHFPLN shows no abnormal move around scheduled major rulings, the "
                        "legal channel is priced in advance and there is no event to trade",
              notes="the Swiss pack carries the other side; CHFHUF is the switched-off control "
                    "because Hungary converted its entire stock by law in 2015"),
        actor("Czech households on three-to-five-year fixed mortgages",
              holds="fixed-rate mortgages taken at very low rates that refix on a KNOWN schedule",
              forced_to=("refix at the prevailing rate when the fixation ends -- a cash-flow "
                         "shock whose DATE is knowable years in advance from the original loan",),
              when="the refixation wave, concentrated where origination was concentrated",
              information=("the original loan dates", "current mortgage rates"),
              constraints=("a fixed-rate contract means the tightening arrives YEARS late and "
                           "ALL AT ONCE per cohort, instead of smoothly",),
              instruments=("EURCZK",),
              counterparties=("Czech banks",),
              observables=("CNB ARAD refixation volumes",
                           "Czech house prices",
                           "the original origination distribution"),
              impact="Czech transmission is the SLOWEST in this pack and the most precisely "
                     "dateable, because the schedule is arithmetic",
              persistence="years",
              falsifier="if Czech consumption shows no relation to the refixation schedule, the "
                        "cohort framing adds nothing over the simple rate level",
              notes="the contrast is the point: Poland floats, Czechia refixes, Hungary is fixed "
                    "with a competing retail bond -- one tightening, three arrival times"),
        actor("Hungarian households in the retail government bond programme",
              holds="a large share of Hungarian government debt, directly",
              forced_to=("choose between a state-guaranteed inflation-linked retail bond and a "
                         "bank deposit, on terms the state sets",),
              when="continuous subscription, with weekly published stocks",
              information=("the MAP Plusz coupon", "published inflation"),
              constraints=("a government funding channel aimed at households changes WHO HOLDS "
                           "THE CURVE: a household investor does not sell on a global risk shock "
                           "the way a foreign fund does",),
              instruments=("EURHUF", "USDHUF"),
              counterparties=("AKK", "Hungarian banks, who lose the deposits"),
              observables=("weekly AKK retail stock data",
                           "the coupon against deposit rates",
                           "the foreign-ownership share, which fell as this grew"),
              impact="the Hungarian curve is structurally less sensitive to global risk appetite "
                     "than the Polish one, for a reason that is institutional rather than "
                     "macroeconomic",
              persistence="structural while the programme runs",
              falsifier="if Hungarian yields respond to global risk shocks exactly as Polish "
                        "ones do, the ownership structure has no effect and the programme is a "
                        "funding detail",
              notes="a genuinely unusual institution with a measurable, published stock"),
        actor("The European Commission as a CEE FX flow",
              holds="the Recovery and Resilience and cohesion envelopes for the three countries",
              forced_to=("disburse against milestones on a published schedule",
                         "suspend when a rule-of-law condition is unmet, and resume when it is -- "
                         "both as dated public decisions"),
              when="event-driven, with the decisions publicly announced",
              information=("milestone assessments", "the political process"),
              constraints=("a conditionality mechanism that made a large expected inflow "
                           "POLITICALLY GATED for Poland and Hungary, so the flow's on-off "
                           "switch had nothing to do with markets",),
              instruments=("EURPLN", "EURHUF", "EURCZK"),
              counterparties=("the three finance ministries, who convert the euros",),
              observables=("the RRF scoreboard, dated and sized",
                           "suspension and resumption announcements",
                           "the ministries' own conversion disclosures, where they exist"),
              impact="a dated, sized, one-way euro inflow with a political switch -- the "
                     "cleanest exogenous flow in the region and the one with the clearest "
                     "identification",
              persistence="the disbursement schedule",
              falsifier="if EURPLN showed no abnormal behaviour around the 2023-2024 unlock "
                        "decisions relative to EURCZK, which was never gated, the conversion is "
                        "either pre-hedged or too small to see",
              notes="EURCZK is the untreated control: Czechia's funds were never suspended"),
        actor("CEE exporters subcontracted to German manufacturing",
              holds="euro receivables against local-currency cost bases, in automotive and "
                    "machinery supply chains",
              forced_to=("hedge on a treasury policy",
                         "produce to German order books they do not control"),
              when="quarterly hedge rolls; continuous production",
              information=("German orders and the Ifo survey", "their own order books"),
              constraints=("a supply-chain position that makes CEE output a derivative of German "
                           "output, with a lag",),
              instruments=("EURPLN", "EURCZK", "EURHUF", "GER40"),
              counterparties=("German manufacturers", "bank FX desks"),
              observables=("German factory orders and Ifo",
                           "CEE industrial production",
                           "GER40's own performance"),
              impact="THE dominant shared external driver of all three currencies, and the "
                     "reason a CEE pair is closer to a European risk asset than to a carry trade",
              persistence="quarters",
              falsifier="if the three CEE currencies' weekly returns have no common factor "
                        "loading on GER40 once the euro's own move is removed, the shared "
                        "industrial channel does not exist and the three should be modelled "
                        "independently",
              notes="the shared driver is why these three are ONE pack; the differences above "
                    "are why they are three sub-labs"),
        actor("The Polish Ministry of Finance and BGK",
              holds="the largest CEE issuance programme, part of it off-budget through BGK",
              forced_to=("auction on a published calendar",
                         "convert EU-funds euros into zloty, sometimes through the NBP and "
                         "sometimes through the market -- a CHOICE that is itself disclosed"),
              when="auctions on a published calendar; conversions at the ministry's discretion",
              information=("the borrowing requirement", "EU disbursement timing"),
              constraints=("a growing borrowing need and a bond market whose foreign ownership "
                           "has fallen, so domestic banks are the marginal buyer",),
              instruments=("EURPLN", "USDPLN"),
              counterparties=("Polish banks", "the NBP", "foreign investors"),
              observables=("the auction calendar and results",
                           "the ministry's own statements about where it converts",
                           "monthly foreign-holdings statistics"),
              impact="whether a given EU inflow reaches the market or is absorbed at the central "
                     "bank is a DISCLOSED CHOICE that determines whether the flow moves the "
                     "zloty at all",
              persistence="episodic",
              falsifier="if EURPLN behaves identically around disbursements converted at the NBP "
                        "and those converted in the market, the conversion channel is not the "
                        "mechanism and the effect is sentiment",
              notes="the conversion-route disclosure is a rare piece of public information about "
                    "HOW a flow reaches the market"),
        actor("Foreign investors in CEE local-currency bonds",
              holds="positions in three small local markets inside EM local-currency indices",
              forced_to=("rebalance to index weights at month-end",
                         "reduce on a global EM risk shock regardless of local news"),
              when="month-end index rebalancing; risk-driven otherwise",
              information=("global EM risk appetite", "index weights"),
              constraints=("index membership forces mechanical flows into currencies whose "
                           "turnover is small relative to their index weight",),
              instruments=("EURPLN", "EURHUF", "EURCZK", "USDPLN"),
              counterparties=("local banks", "the finance ministries"),
              observables=("monthly foreign-holdings statistics",
                           "EM index rebalancing dates",
                           "the currencies' moves on days with no CEE news"),
              impact="CEE currencies sell off on global EM stress with no local trigger, which "
                     "is the single most common source of a spurious 'Polish' or 'Hungarian' "
                     "finding",
              persistence="days",
              falsifier="if the three currencies' largest weekly losses are NOT concentrated on "
                        "global EM risk days with no local releases, the foreign-flow channel is "
                        "not dominant",
              notes="this actor is why every CEE domain here needs a global-EM-risk control"),
        actor("Local banks as the marginal holders of CEE government debt",
              holds="large domestic sovereign portfolios, grown as foreign ownership fell",
              forced_to=("absorb issuance the foreign bid no longer takes",
                         "meet capital and liquidity ratios that make the holdings sticky"),
              when="continuous; concentrated at auctions",
              information=("the auction calendar", "their own liquidity"),
              constraints=("a regulatory and tax framework that encourages sovereign holdings, "
                           "so the bank-sovereign link in CEE is closer than in western Europe",),
              instruments=("EURPLN", "EURCZK", "EURHUF"),
              counterparties=("the finance ministries", "depositors"),
              observables=("holdings statistics",
                           "auction bid-to-cover",
                           "bank sector disclosures"),
              impact="the domestic bid dampens the yield response to a foreign risk shock and "
                     "concentrates the adjustment in the CURRENCY instead -- which is why CEE "
                     "risk shows up in FX more than in rates",
              persistence="structural",
              falsifier="if CEE yields respond to global risk shocks as strongly as the "
                        "currencies do, the domestic-bid dampening is not operating",
              notes="this actor explains why an FX-only desk sees more of a CEE shock than a "
                    "rates desk would, which is a favourable structural fact here"),
        actor("GPW market makers in the WIG20 complex",
              holds="option and future books into a quarterly third-Friday expiry",
              forced_to=("hedge continuously",
                         "unwind against a settlement average taken from the closing phase"),
              when="the third Friday of March, June, September and December",
              information=("GPW open interest", "their own inventory"),
              constraints=("a small derivatives market where a single participant can be a large "
                           "share of open interest",),
              instruments=("EURPLN", "GER40"),
              counterparties=("Polish institutional hedgers", "retail warrant issuers"),
              observables=("GPW open interest",
                           "expiry-day behaviour against matched Fridays"),
              impact="a Polish expiry effect that coincides with the European third Friday, "
                     "which makes it HARD to identify -- unlike Sweden's fourth Friday",
              persistence="the expiry day",
              falsifier="if EURPLN's expiry-day behaviour is indistinguishable from GER40's on "
                        "the same day, the effect is European and not Polish",
              notes="Czechia's total absence of a derivatives complex is the control: if a CEE "
                    "calendar effect appears in CZK too, it is not about expiry"),
        actor("CEE retail investors and the Polish forum ecosystem",
              holds="direct equity and, historically, franc-denominated mortgages",
              forced_to=("coordinate litigation through public forums, which is where the "
                         "CHF-mortgage wave was organised before it reached the courts",),
              when="continuous; litigation waves are visible in forum activity before rulings",
              information=("bankier and stockwatch forums", "law firm campaigns"),
              constraints=("a legal process that requires individual claims, so aggregate legal "
                           "risk is the sum of a coordination problem that happens in public",),
              instruments=("CHFPLN", "EURPLN"),
              counterparties=("Polish banks", "the courts"),
              observables=("forum activity on franc mortgages",
                           "the number of active cases, published",
                           "bank provisions"),
              impact="a rare case where public retail coordination is a LEADING INDICATOR of a "
                     "balance-sheet flow, because the flow requires individual filings",
              persistence="years",
              falsifier="if forum activity has no lead over filed case counts or over bank "
                        "provisioning, the coordination signal is noise",
              notes="mined for VERBATIM claims only; the two-lane order forbids trading the "
                    "banks themselves"),
        actor("The NBP as an FX intervention actor",
              holds="the reserves and the discretion to use them, without pre-announcement",
              forced_to=("publish monthly reserve statistics, which is the only public trace",
                         "mark its own balance sheet at the year-end exchange rate, which is why "
                         "the December 2020 episode looked like profit management as much as "
                         "policy"),
              when="unannounced; the December 2020 operation is the reference case",
              information=("the zloty's level", "its own balance sheet position"),
              constraints=("no pre-announcement and no published reaction function, so an "
                           "intervention is only ever identified after the fact and imprecisely",),
              instruments=("EURPLN", "USDPLN"),
              counterparties=("Polish banks", "the FX market"),
              observables=("monthly reserve changes, contaminated by valuation",
                           "unexplained intraday moves in thin sessions",
                           "the year-end accounting date"),
              impact="a discretionary, unannounced flow that is the opposite of Norway's "
                     "announced one -- and the contrast is exactly what makes the Norwegian case "
                     "identifiable and the Polish one not",
              persistence="episodic",
              falsifier="if monthly reserve changes have no relation to the zloty's prior-month "
                        "move, there is no detectable reaction function and every Polish "
                        "intervention claim on this desk is UNMEASURED",
              notes="Norway and Poland are the two poles of central-bank FX transparency in this "
                    "department; the pack carries both so the contrast is available as a control"),
    )


def domains() -> tuple[dict[str, Any], ...]:
    """Thirteen research domains, each with negative controls."""
    return (
        domain("PL-A", "The NBP two-day decision with no fixed announcement time",
               objects=("the day-two decision release",
                        "the day-three governor's press conference",
                        "the minutes, weeks later",
                        "the projection Councils in March, July and November"),
               conditions=("projection Council versus ordinary Council",
                           "whether the captured release timestamp is available at all",
                           "the Council's political composition era"),
               instruments=("EURPLN", "USDPLN", "CHFPLN"),
               controls=("day three against day two: if the conference carries the information, "
                         "the decision alone is the wrong event",
                         "matched non-Council days",
                         "EURCZK and EURHUF on the same day, which separate a Polish event from "
                         "a regional one",
                         "the explicit UNMEASURED verdict when no release timestamp exists, "
                         "which for most historical decisions is the honest answer"),
               notes="the absent clock is a MEASUREMENT problem and the domain's first output "
                     "should be a timestamp-collection job, not a return study"),
        domain("PL-B", "CNB decisions at a fixed 14:30 CET, and the fix that shares the minute",
               objects=("the 14:30 CET announcement",
                        "the 15:45 CET press conference",
                        "the CNB's own daily FX declaration at the same 14:30 CET"),
               conditions=("forecast meeting versus ordinary meeting",
                           "the path revision",
                           "whether the koruna was near an intervention level"),
               instruments=("EURCZK", "USDCZK", "GER40"),
               controls=("matched non-decision days at the same clock time",
                         "EURPLN and EURHUF on the same day as the regional control",
                         "GER40 on the same day, since a German move will masquerade as a CEE "
                         "policy reaction",
                         "the 14:30 CET minute on non-decision days, where the FX declaration "
                         "still happens and the decision does not"),
               notes="the last control is the one that separates the fix from the decision, and "
                     "it exists only because the CNB collides them"),
        domain("PL-C", "MNB decisions and the instrument that changed",
               objects=("the 14:00 CET announcement",
                        "the base rate series",
                        "the one-week deposit rate series, which WAS the policy rate 2021-2023",
                        "the October 2022 emergency move to 18%"),
               conditions=("which instrument was operative",
                           "the EU-funds dispute state",
                           "the forint's distance from its stress levels"),
               instruments=("EURHUF", "USDHUF", "CHFHUF"),
               controls=("the base-rate series used ALONE as an explicit NEGATIVE control: if it "
                         "reproduces the one-week-rate result, the instrument distinction is "
                         "cosmetic",
                         "EURPLN and EURCZK on the same days",
                         "the pre-2020 period, before the one-week rate existed",
                         "matched non-decision Tuesdays"),
               notes="using the wrong rate for 2022 is a 500bp error and it is the single most "
                     "expensive mistake available in CEE data work"),
        domain("PL-D", "The Czech koruna floor as a censored distribution",
               objects=("the EUR/CZK 27.00 commitment, 2013-11-07 to 2017-04-06",
                        "the censored return distribution while it held",
                        "the unscheduled exit"),
               conditions=("inside versus outside the commitment",
                           "distance from 27.00 while it held"),
               instruments=("EURCZK", "USDCZK"),
               controls=("USDCZK during the commitment, which was not pegged and shows what the "
                         "koruna would have done",
                         "EURPLN and EURHUF over the same window as the unpegged neighbours",
                         "a simulated censoring applied to a post-2017 sample, to show what a "
                         "floor does to a statistic mechanically",
                         "the Swiss 1.20 floor as the structural analogue, with its own exit"),
               notes="NOT TESTABLE ON THIS BOX: the exotic FX bars begin 2020-09-14 and the "
                     "commitment ended in 2017. The era is carried so an external study is "
                     "designed correctly and so no session quietly pools across it."),
        domain("PL-E", "EU funds as a dated, politically gated FX flow",
               objects=("RRF and cohesion disbursement decisions",
                        "the suspension and resumption announcements for Poland and Hungary",
                        "the ministries' disclosed conversion route"),
               conditions=("gated versus ungated period",
                           "the size of the disbursement relative to monthly FX turnover",
                           "whether conversion went through the central bank or the market"),
               instruments=("EURPLN", "EURHUF", "EURCZK"),
               controls=("EURCZK as the UNTREATED CONTROL: Czech funds were never suspended, so "
                         "a move shared with the koruna is regional sentiment and not a "
                         "conversion",
                         "the announcement date against the payment date",
                         "disbursements converted at the central bank against those converted in "
                         "the market",
                         "a placebo announcement date one month displaced"),
               notes="a forced flow with a political on-off switch and an untreated neighbour is "
                     "about as close to a controlled experiment as macro gets"),
        domain("PL-F", "One tightening cycle, three mortgage contracts, three arrival times",
               objects=("Polish WIBOR floating resets and the legislated payment holidays",
                        "Czech three-to-five-year fixations and the refixation wave",
                        "Hungarian fixed rates against the competing retail bond"),
               conditions=("the contract type",
                           "whether a payment holiday was in force",
                           "the position in the refixation schedule"),
               instruments=("EURPLN", "EURCZK", "EURHUF"),
               controls=("the three countries against each other, which is the whole design: one "
                         "external shock, three contractual filters",
                         "Sweden and Norway as the Nordic comparison, with a third and fourth "
                         "contract type",
                         "the payment-holiday windows against the periods either side",
                         "Germany as the slowest case"),
               notes="the cleanest natural experiment in this department: the same European "
                     "tightening arriving at three neighbouring household sectors at three "
                     "different times, for purely contractual reasons"),
        domain("PL-G", "The German industrial channel as the shared CEE driver",
               objects=("GER40 and German factory orders",
                        "the common factor across EURPLN, EURCZK and EURHUF",
                        "the idiosyncratic residuals, which is where the country packs live"),
               conditions=("the German industrial cycle's state",
                           "the global risk regime",
                           "whether any local event occurred"),
               instruments=("EURPLN", "EURCZK", "EURHUF", "GER40"),
               controls=("the euro's own move removed first, since all three are euro crosses",
                         "EURSEK, another German-industrial-exposed currency outside CEE",
                         "days with a local release removed",
                         "a principal-component decomposition, because if one factor explains "
                         "most of the three it is the shared driver and the country-specific "
                         "stories are residuals"),
               notes="this domain exists partly to SIZE the shared factor, so every other CEE "
                     "domain knows how much variance it is competing against"),
        domain("PL-H", "CEE calendar asymmetry against TARGET2",
               objects=("the roughly twenty weekday sessions a year where a local banking system "
                        "is shut and the euro settles",
                        "Wielki Piatek, which closes GPW without being a Polish holiday",
                        "Velky patek, which IS a Czech statutory holiday, on the same date"),
               conditions=("which country is closed",
                           "whether the exchange is also closed",
                           "proximity to a long weekend"),
               instruments=("EURPLN", "EURCZK", "EURHUF", "CHFPLN"),
               controls=("matched weekdays with all legs open",
                         "the day after, for the catch-up test",
                         "turnover as the direct control",
                         "the OTHER two CEE currencies on the same day, which is the sharpest "
                         "control available: only the closed country should show the effect"),
               notes="the two-CEE-neighbour control is unusually clean because the three share a "
                     "driver and differ on the calendar"),
        domain("PL-I", "The Polish CHF-mortgage litigation flow",
               objects=("scheduled CJEU and Supreme Court rulings",
                        "bank litigation provisions, quarterly",
                        "the shrinking outstanding stock"),
               conditions=("the ruling's direction",
                           "whether it was expected",
                           "the size of the remaining stock, which decays over the sample"),
               instruments=("CHFPLN", "EURPLN", "CHFHUF"),
               controls=("CHFHUF as the SWITCHED-OFF control: Hungary converted its entire stock "
                         "by law in 2015, so the mechanism cannot operate there",
                         "EURPLN on the same day, separating a zloty move from a franc one",
                         "rulings that went the banks' way",
                         "a placebo date one week before the scheduled hearing"),
               notes="a mechanism switched off by law in a neighbouring country is the best kind "
                     "of control and this domain has one"),
        domain("PL-J", "Who holds the curve, and what that does to a risk shock",
               objects=("Polish foreign ownership, which collapsed after 2016",
                        "the Hungarian retail bond stock, which grew",
                        "domestic bank holdings in all three"),
               conditions=("the ownership mix",
                           "the size of the global risk shock",
                           "the period, since the mix changed materially"),
               instruments=("EURPLN", "EURHUF", "EURCZK"),
               controls=("the pre-2016 Polish period, when foreign ownership was high, against "
                         "the post-2020 period when it was not -- the same country, two "
                         "ownership structures",
                         "Hungary against Poland at the same moment, with different mixes",
                         "global EM risk days with no local news",
                         "yields against currencies: if the domestic bid dampens yields, the "
                         "adjustment should appear in FX instead"),
               notes="the claim that CEE risk shows up in FX rather than rates is testable and "
                     "is the structural reason this desk sees CEE shocks at all"),
        domain("PL-K", "CEE expiry, and the Czech control that has none",
               objects=("the WIG20 quarterly third Friday",
                        "BUX futures on the same date",
                        "the total ABSENCE of a Czech derivatives complex"),
               conditions=("quarterly expiry versus ordinary Friday",
                           "open interest concentration",
                           "whether the European expiry falls the same day, which it does"),
               instruments=("EURPLN", "EURHUF", "EURCZK", "GER40"),
               controls=("EURCZK as the NO-DERIVATIVES control: if a CEE calendar effect appears "
                         "in the koruna too, it is not about expiry",
                         "GER40 on the same day, since the European expiry coincides",
                         "matched non-expiry Fridays",
                         "the fourth Friday, which is Sweden's expiry and nobody's here"),
               notes="the Czech absence is the most valuable thing in this domain; it is the "
                     "only way to separate a CEE expiry effect from a European one"),
        domain("PL-L", "Central-bank transparency as a spectrum: Norway to Poland",
               objects=("the NBP's unannounced interventions and monthly reserve trace",
                        "the CNB's documented commitment and fixed announcement clock",
                        "Norway's announced daily amount, as the opposite pole"),
               conditions=("how much of the operation is public before it happens",
                           "the lag and contamination of the only public trace"),
               instruments=("EURPLN", "USDPLN", "EURCZK"),
               controls=("Norway's announced-flow result as the benchmark: if an announced flow "
                         "is detectable and an unannounced one of similar size is not, the "
                         "difference is the announcement and not the flow",
                         "months with no plausible intervention as the null",
                         "valuation-adjusted reserve changes, since raw changes are dominated by "
                         "the exchange rate itself",
                         "the December year-end accounting date specifically"),
               notes="this domain is a cross-pack comparison by design; the Norwegian pack "
                     "supplies the other pole and neither result means much alone"),
        domain("PL-M", "CEE positioning: the declared gap, three times over",
               objects=("the ABSENCE of a CFTC series for PLN, CZK and HUF",
                        "monthly foreign-holdings statistics as the slow substitute",
                        "the EUR COT as the thing that must NOT be used as a proxy"),
               conditions=("whether a crowding claim can be measured at the horizon asked",
                           "the ownership-share level"),
               instruments=("EURPLN", "EURCZK", "EURHUF"),
               controls=("the EUR COT applied to CEE as an explicit NEGATIVE control: an "
                         "apparent result there is evidence of the European factor from domain "
                         "PL-G and not of CEE positioning",
                         "a randomised ownership series, to show the monthly statistic carries "
                         "information beyond its own persistence",
                         "the same hypothesis on EUR, where the measurement exists",
                         "the explicit UNMEASURED verdict, which must remain available"),
               notes="three currencies, one gap, and the substitute most likely to be reached "
                     "for is the one that manufactures a European result and calls it Polish"),
    )


TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    edge("PL-E01",
         source="an EU Recovery and Resilience disbursement decision for Poland or Hungary",
         mechanism="a dated, sized euro inflow converted into local currency on a schedule set "
                   "in Brussels rather than by the market",
         targets=("EURPLN", "EURHUF"),
         sign="disbursement -> local currency firmer",
         horizon="days to weeks", lag="the conversion is not same-day and the lag is the "
                                     "unmeasured part of this edge",
         control="EURCZK as the untreated control -- Czech funds were never suspended; the "
                 "announcement date against the payment date",
         evidence="HYPOTHESIS",
         notes="the euro-area pack carries the sending side of this edge"),
    edge("PL-E02",
         source="GER40's weekly return",
         mechanism="CEE manufacturing is subcontracted to German industry, so all three "
                   "currencies load on the German cycle before they load on anything local",
         targets=("EURPLN", "EURCZK", "EURHUF"),
         sign="GER40 down -> all three CEE currencies weaker against the euro",
         horizon="days to weeks", lag="same session",
         control="the euro's own move removed first; EURSEK as the non-CEE German-exposed "
                 "comparison; days with a local release removed",
         evidence="MEASURED_ELSEWHERE",
         notes="the shared factor. Every other CEE edge competes with this one for variance and "
               "must be measured on the RESIDUAL."),
    edge("PL-E03",
         source="a scheduled CJEU or Polish Supreme Court ruling on franc mortgages",
         mechanism="a court-ordered conversion is a legally forced franc flow with a publicly "
                   "dated trigger",
         targets=("CHFPLN", "EURPLN"),
         sign="a pro-borrower ruling -> CHFPLN lower",
         horizon="days", lag="the hearing time is scheduled",
         control="CHFHUF, where the stock was extinguished by law in 2015; EURPLN to separate "
                 "a zloty move from a franc one",
         evidence="HYPOTHESIS",
         notes="the Swiss pack carries the mirror of this edge"),
    edge("PL-E04",
         source="the MNB one-week deposit rate, 2021 to September 2023",
         mechanism="the operative Hungarian policy rate detached from the base rate and reached "
                   "18% in October 2022; the differential that mattered was the one-week one",
         targets=("EURHUF", "USDHUF", "CHFHUF"),
         sign="one-week rate up -> forint firmer, with the base rate showing nothing",
         horizon="days to weeks", lag="the tender is weekly",
         control="the BASE RATE series used alone as the negative control; EURPLN and EURCZK on "
                 "the same days",
         evidence="HYPOTHESIS",
         notes="if the base-rate series reproduces the result, the instrument distinction is "
               "cosmetic -- which would be surprising across a 500bp gap"),
    edge("PL-E05",
         source="a Polish, Czech or Hungarian national holiday on which TARGET2 is open",
         mechanism="the local banking system is shut while the euro settles, so participation "
                   "collapses on one leg of a quoted pair and the value date moves for one side",
         targets=("EURPLN", "EURCZK", "EURHUF", "CHFPLN"),
         sign="compressed range, wider effective spreads, abnormal forward points",
         horizon="intraday and the value-date window", lag="none",
         control="the OTHER two CEE currencies on the same day -- only the closed country should "
                 "move; turnover as the direct control; matched open weekdays",
         evidence="HYPOTHESIS",
         notes="the days are DERIVED by `target2_open_but_local_closed`, so the sample is "
               "reproducible and extends to any year"),
    edge("PL-E06",
         source="a global EM risk shock with no central European release",
         mechanism="foreign index investors reduce local-currency exposure mechanically, and CEE "
                   "turnover is small relative to index weight",
         targets=("EURPLN", "EURHUF", "USDPLN"),
         sign="EM risk-off -> CEE currencies weaker",
         horizon="days", lag="same session",
         control="GER40's own move removed, since the German channel is the competing "
                 "explanation; days with a local release removed; EURCZK, whose ownership mix "
                 "differs",
         evidence="MEASURED_ELSEWHERE",
         notes="the most common source of a spurious country-specific CEE finding"),
    edge("PL-E07",
         source="the Czech mortgage refixation schedule, computable years in advance",
         mechanism="a fixed-rate stock refixes on a known calendar, so the tightening arrives "
                   "late and per cohort rather than smoothly",
         targets=("EURCZK",),
         sign="a heavy refixation quarter -> Czech demand weaker -> koruna weaker at the macro "
              "horizon",
         horizon="quarters", lag="years, by construction",
         control="Poland's floating stock over the same window as the fast-transmission control; "
                 "Sweden's three-month reset as the fastest case",
         evidence="HYPOTHESIS",
         notes="the schedule is arithmetic from the origination distribution, which makes this "
               "one of the few genuinely knowable future cash-flow shocks in the region"),
    edge("PL-E08",
         source="a Polish statutory mortgage payment holiday (wakacje kredytowe)",
         mechanism="a legislated suspension of instalments partially undoes the monetary "
                   "tightening on a dated schedule",
         targets=("EURPLN", "USDPLN"),
         sign="a payment holiday in force -> the WIBOR-to-demand channel is blocked",
         horizon="the legislated window", lag="the legislation dates it",
         control="the periods either side of each window; Czechia and Hungary, which had no "
                 "such legislation; the take-up rate as a dose measure",
         evidence="HYPOTHESIS",
         notes="a legislated interruption of a transmission channel is a natural experiment in "
               "blocking it, and no other country in this department has one"),
    edge("PL-E09",
         source="the WIG20 quarterly third-Friday expiry",
         mechanism="dealer hedging into a settlement average taken from the closing phase",
         targets=("EURPLN", "GER40"),
         sign="altered expiry-day volatility profile",
         horizon="intraday", lag="none",
         control="EURCZK as the NO-DERIVATIVES control; GER40 on the same day, since the "
                 "European expiry coincides; matched non-expiry Fridays",
         evidence="HYPOTHESIS",
         notes="the coincidence with the European third Friday makes this the hardest expiry "
               "claim in the department to identify, and the Czech absence is the only way in"),
    edge("PL-E10",
         source="a CNB decision at 14:30 CET",
         mechanism="a fixed-time announcement from the most transparent CEE central bank, which "
                   "publishes a rate path",
         targets=("EURCZK", "USDCZK"),
         sign="hawkish path revision -> EURCZK down", horizon="intraday to a week",
         lag="0 to 30 minutes",
         control="the 14:30 CET minute on non-decision days, when the CNB's FX declaration still "
                 "happens; EURPLN and EURHUF as the regional control; GER40 on the same day",
         evidence="HYPOTHESIS",
         notes="the fix-and-decision collision at 14:30 CET is what the first control removes"),
    edge("PL-E11",
         source="an NBP month-on-month reserve change, valuation-adjusted",
         mechanism="the only public trace of an unannounced intervention",
         targets=("EURPLN", "USDPLN"),
         sign="an unexplained reserve rise -> zloty-weakening intervention",
         horizon="the following month", lag="about ten days to publication, and the series is "
                                            "monthly",
         control="Norway's ANNOUNCED daily amount as the benchmark: if the announced flow is "
                 "detectable and this is not, the difference is announcement rather than flow; "
                 "months with no plausible intervention; the December accounting date",
         evidence="HYPOTHESIS",
         notes="expected to be UNMEASURABLE at this frequency, and establishing that cleanly is "
               "a useful result about the limits of inference from reserves"),
    edge("PL-E12",
         source="the Hungarian retail government bond stock, weekly",
         mechanism="household ownership of the curve makes Hungarian yields structurally less "
                   "responsive to global risk than Polish ones, pushing the adjustment into FX",
         targets=("EURHUF", "EURPLN"),
         sign="a larger household-held share -> a larger FX response per unit of risk shock",
         horizon="weeks to quarters", lag="the stock is published weekly",
         control="Poland at the same moment, with a bank-held curve; the pre-2019 Hungarian "
                 "period, before the programme existed",
         evidence="HYPOTHESIS",
         notes="an institutional fact with a published weekly stock is the rarest kind of "
               "conditioning variable"),
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
    era("cz.koruna_floor", start="2013-11-07", end="2017-04-06",
        label="the CNB exchange rate commitment at EUR/CZK 27.00",
        what_changed="the koruna's appreciation was CENSORED by a standing commitment, so its "
                     "return distribution was truncated by construction",
        invalidates="every EURCZK statistic estimated across 2017-04-06; a volatility or tail "
                    "estimate pooled over it averages a bounded market and an unbounded one",
        notes="NOT TESTABLE ON THIS BOX: the exotic FX bars begin 2020-09-14. Carried so an "
              "external study is designed correctly."),
    era("pl.chf_litigation", start="2019-10-03", end=None,
        label="the CJEU Dziubak ruling and the Polish franc-mortgage litigation wave",
        what_changed="Polish courts began voiding franc mortgage contracts, converting a "
                     "currency exposure into a legal liability with dated triggers",
        invalidates="a CHFPLN model with no legal-event term after late 2019",
        notes="OPEN ERA; the stock shrinks with each ruling wave, so the effect DECAYS "
              "mechanically over the sample and a pooled estimate understates the early period"),
    era("pl.nbp_intervention_2020", start="2020-12-01", end="2020-12-31",
        label="the December 2020 NBP zloty-weakening intervention",
        what_changed="a central bank sold its own currency at the year-end accounting date, "
                     "which was read as profit management as much as policy",
        invalidates="a reaction-function estimate that assumes interventions strengthen the "
                    "domestic currency",
        notes="a one-month era on purpose: it is the reference case for Polish intervention and "
              "it is at the very start of this box's exotic bars"),
    era("hu.one_week_rate", start="2021-11-01", end="2023-09-25",
        label="the MNB one-week deposit rate as the effective policy rate",
        what_changed="the operative Hungarian policy rate DETACHED from the base rate and "
                     "reached 18% in October 2022 while the base rate stood far below",
        invalidates="ANY study using a single 'Hungarian policy rate' series across this period. "
                    "The error is up to 500 basis points and it is silent.",
        notes="fully inside this box's bars and the most consequential data trap in the pack"),
    era("hu.forint_crisis", start="2022-09-01", end="2022-11-30",
        label="the October 2022 forint crisis",
        what_changed="EURHUF reached its weakest levels on record and the MNB responded with an "
                     "emergency instrument",
        invalidates="a tail model for the forint calibrated without it",
        notes="on this box's bars; the reference observation for HUF tail risk"),
    era("cee.hiking", start="2021-06-01", end="2022-10-31",
        label="the CEE tightening cycle, led by the CNB and the NBP ahead of the ECB",
        what_changed="all three central banks hiked before the ECB did, so for the first time in "
                     "the sample CEE carry was positive against the euro on a large margin",
        invalidates="anything estimated on the 2015-2020 sample, where all three were near zero",
        notes="fully on this box's bars"),
    era("pl.eu_funds_gate", start="2021-01-01", end="2023-12-31",
        label="the rule-of-law conditionality suspension of Polish and Hungarian EU funds",
        what_changed="a large, expected, dated euro inflow was switched off for political "
                     "reasons and later switched back on, with Czechia untouched throughout",
        invalidates="a CEE flow model that treats EU funds as a smooth entitlement",
        notes="the dates are the desk's reading of a process with several partial steps and are "
              "DECLARED rather than measured; the untreated Czech control is what makes the "
              "episode usable at all"),
    era("pl.payment_holidays", start="2022-08-01", end=None,
        label="the Polish statutory mortgage payment holidays",
        what_changed="fiscal policy legislated a suspension of mortgage instalments in direct "
                     "response to the central bank's tightening",
        invalidates="a Polish transmission estimate that ignores the interruption",
        notes="the programme was legislated twice with different eligibility; the end is "
              "UNMEASURED and the eligibility change is itself a regime boundary"),
    era("pl.wibor_to_wiron", start="2022-07-01", end=None,
        label="the WIBOR-to-WIRON benchmark transition",
        what_changed="the reference rate in existing Polish mortgage contracts is being replaced "
                     "by a transaction-based rate, with legal and political consequences",
        invalidates="a long Polish rates series joined by NAME across the transition; the break "
                    "is definitional and scheduled",
        notes="OPEN ERA. The timetable has slipped more than once, so the end is genuinely "
              "unknown rather than omitted."),
)

CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    miner("cee_nbp_timestamp", domain_ids=("PL-A",), kind="data",
          entry="countries.pl.miners:nbp_timestamp", cadence_s=86400.0, steerable=False,
          notes="NOT WIRED, and it is a DATA miner rather than a mechanism one on purpose: its "
                "first job is to collect the NBP release timestamps that do not exist in any "
                "calendar, because without them domain PL-A is UNMEASURED."),
    miner("cee_policy_clocks", domain_ids=("PL-B", "PL-C"), kind="mechanism",
          entry="countries.pl.miners:policy_clocks",
          notes="NOT WIRED. The CNB's 14:30 CET fix-and-decision collision and the MNB's "
                "instrument change are both handled here."),
    miner("cee_eu_funds", domain_ids=("PL-E",), kind="mechanism",
          entry="countries.pl.miners:eu_funds",
          notes="NOT WIRED. EURCZK is the untreated control and is mandatory."),
    miner("cee_mortgage_contracts", domain_ids=("PL-F",), kind="transfer",
          entry="countries.pl.miners:mortgage_contracts",
          notes="NOT WIRED. Three-country by construction; a single-country result proves "
                "nothing about contractual filtering."),
    miner("cee_german_factor", domain_ids=("PL-G",), kind="residual",
          entry="countries.pl.miners:german_factor",
          notes="NOT WIRED. Sizes the shared factor first so every other CEE miner knows how "
                "much variance it is competing against."),
    miner("cee_calendar_asymmetry", domain_ids=("PL-H",), kind="data",
          entry="countries.pl.miners:calendar_asymmetry", cadence_s=86400.0, steerable=False,
          notes="NOT WIRED. A fixed cost: derives the local calendars and differences them "
                "against TARGET2 using the rules in this module."),
    miner("cee_chf_litigation", domain_ids=("PL-I",), kind="scout",
          entry="countries.pl.miners:chf_litigation",
          notes="NOT WIRED. Shared with the Swiss pack; CHFHUF is the switched-off control."),
    miner("cee_ownership_structure", domain_ids=("PL-J", "PL-M"), kind="data",
          entry="countries.pl.miners:ownership_structure", cadence_s=604800.0,
          notes="NOT WIRED. Emits a declared UNMEASURED verdict for positioning and a measured "
                "one for ownership, which are different things."),
    miner("cee_expiry_czech_control", domain_ids=("PL-K",), kind="mechanism",
          entry="countries.pl.miners:expiry_czech_control",
          notes="NOT WIRED. The Czech no-derivatives control is the only identification here."),
    miner("cee_transparency_spectrum", domain_ids=("PL-L",), kind="transfer",
          entry="countries.pl.miners:transparency_spectrum",
          notes="NOT WIRED. A cross-pack comparison: the Norwegian announced-flow result is the "
                "benchmark and neither half means much alone."),
)

#: The three sub-labs. One shared external driver, three central banks, three mortgage contracts,
#: three calendars, three languages.
SUB_LABS: dict[str, dict[str, Any]] = {
    "pl": {
        "name": "Poland",
        "executable": ("EURPLN", "USDPLN", "GBPPLN", "CHFPLN"),
        "central_bank": "Narodowy Bank Polski / Rada Polityki Pienieznej",
        "policy_rate": "stopa referencyjna",
        "announcement": "NO FIXED TIME -- the afternoon of day two of a two-day meeting; the "
                        "governor's press conference is the FOLLOWING day around 15:00 CET",
        "intervention_regime": "discretionary and unannounced. December 2020 is the reference "
                               "case: the NBP sold zloty at the year-end accounting date.",
        "debt_agency": "Ministerstwo Finansow, with BGK issuing off-budget",
        "exchange": "GPW Warsaw",
        "expiry": "third Friday of Mar/Jun/Sep/Dec for WIG20 futures (declared)",
        "holiday_function": "countries.pl.pack:national_holidays('pl', year)",
        "asymmetry_function": "countries.pl.pack:target2_open_but_local_closed('pl', year)",
        "mortgage_contract": "WIBOR floating, with STATUTORY payment holidays legislated in 2022 "
                             "and 2024 and a live CHF-mortgage litigation stock",
        "statistics": ("GUS CPI flash at 10:00 CET, with a final print about two weeks later",
                       "GUS industrial production and retail sales"),
        "language": "pl",
        "terminology_keys": ("pl_policy", "pl_fx", "pl_rates", "pl_credit", "pl_market",
                             "pl_macro"),
        "sources": ("https://nbp.pl/en/", "https://www.gov.pl/web/finanse",
                    "https://stat.gov.pl/en/", "https://www.gpw.pl/",
                    "https://www.bankier.pl/forum/"),
        "why_it_matters": "the largest CEE economy and the only one with a legislated "
                          "interruption of its own monetary transmission to study",
    },
    "cz": {
        "name": "Czechia",
        "executable": ("EURCZK", "USDCZK"),
        "central_bank": "Ceska narodni banka",
        "policy_rate": "dvoutydenni repo sazba (the two-week repo rate)",
        "announcement": "14:30 CET, a FIXED time, with the press conference at 15:45 CET; the "
                        "CNB's own daily FX declaration shares the 14:30 minute",
        "intervention_regime": "explicit and documented. A hard EUR/CZK 27.00 floor from "
                               "2013-11-07 to 2017-04-06, koruna-strengthening intervention in "
                               "2022, and a programme of selling FX reserve returns from 2023.",
        "debt_agency": "Ministerstvo financi",
        "exchange": "Burza cennych papiru Praha (PSE)",
        "expiry": "NONE. The PX index has no liquid listed derivatives complex, which makes "
                  "Czechia the department's control for every expiry claim.",
        "holiday_function": "countries.pl.pack:national_holidays('cz', year)",
        "asymmetry_function": "countries.pl.pack:target2_open_but_local_closed('cz', year)",
        "mortgage_contract": "fixed for three to five years, with a REFIXATION WAVE whose "
                             "schedule is arithmetic from the origination distribution",
        "statistics": ("CZSO CPI at 09:00 CET", "CZSO industrial production"),
        "language": "cs",
        "terminology_keys": ("cs_policy", "cs_fx", "cs_market"),
        "sources": ("https://www.cnb.cz/en/", "https://www.czso.cz/csu/czso/home",
                    "https://www.mfcr.cz/", "https://www.kurzy.cz/"),
        "why_it_matters": "the most transparent CEE central bank, the only documented hard FX "
                          "floor in the region, and an equity market with no derivatives -- "
                          "three separate reasons it is the region's best control",
    },
    "hu": {
        "name": "Hungary",
        "executable": ("EURHUF", "USDHUF", "GBPHUF", "CHFHUF", "AUDHUF", "NZDHUF"),
        "central_bank": "Magyar Nemzeti Bank / Monetaris Tanacs",
        "policy_rate": "alapkamat (the base rate) -- BUT from 2021 to September 2023 the "
                       "effective policy rate was the EGYHETES BETETI KAMAT (one-week deposit "
                       "rate), which reached 18% in October 2022",
        "announcement": "14:00 CET, usually a Tuesday, press conference 15:00 CET (declared)",
        "intervention_regime": "instrument-based rather than direct: the one-week deposit rate "
                               "and a set of targeted facilities were used to defend the forint "
                               "in 2022 instead of spot intervention",
        "debt_agency": "AKK, with a large RETAIL government bond programme (MAP Plusz) that "
                       "places debt directly with households",
        "exchange": "Budapesti Ertektozsde (BET)",
        "expiry": "third Friday for BUX futures (declared)",
        "holiday_function": "countries.pl.pack:national_holidays('hu', year)",
        "asymmetry_function": "countries.pl.pack:target2_open_but_local_closed('hu', year)",
        "mortgage_contract": "predominantly fixed, with the retail bond programme competing for "
                             "the same household savings; the entire CHF-mortgage stock was "
                             "converted BY LAW in 2015, which makes CHFHUF a switched-off "
                             "control for the Polish litigation channel",
        "statistics": ("KSH CPI at 09:00 CET", "KSH industrial production"),
        "language": "hu",
        "terminology_keys": ("hu_policy", "hu_fx", "hu_market", "hu_macro"),
        "sources": ("https://www.mnb.hu/en/", "https://akk.hu/", "https://www.ksh.hu/?lang=en",
                    "https://bet.hu/", "https://www.portfolio.hu/"),
        "why_it_matters": "six executable forint pairs -- more than any other CEE currency -- an "
                          "instrument that changed twice, and a curve held by households",
    },
}


def pack() -> Any:
    """The central European pack: `CountryPack` when the framework has landed, else a dict."""
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
