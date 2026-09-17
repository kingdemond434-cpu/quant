"""THE SWITZERLAND PACK -- a published intervention series, a censored era, and the gold refinery.

Fourteen actors with their eleven fields, twelve domains A..L with objects, conditions,
instruments and negative controls, nine datasets with all six point-in-time stamps, ten
transmission edges naming real Fusion symbols, seven policy eras and two holiday calendars (the
SIX trading one and the cantonal banking one, which disagree on about a dozen days a year).

THREE THINGS THIS PACK REFUSES TO DO.

  * IT DOES NOT TREAT THE FLOOR ERA AS A SAMPLE. Between 2011-09-06 and 2015-01-15 EURCHF's
    downside was censored at 1.20 by a standing central-bank commitment. Any statistic estimated
    on a censored series and applied to an uncensored one is wrong in a way no amount of
    bootstrapping fixes. The era row says so and the desk's bars begin in 2018 anyway, which the
    pack states rather than letting a session discover it mid-study.
  * IT DOES NOT USE EURCHF AS A PROXY FOR SNB POLICY. EURCHF is the ECB's currency pair as much
    as it is the SNB's: about half its variance on an ECB decision day belongs to Frankfurt. The
    domains carry USDCHF and the CHF crosses as the separating controls.
  * IT DOES NOT NAME AN SMI CONSTITUENT. Three pharmaceutical and food names are roughly half the
    Swiss index; they are the loudest mechanism in the country and they are forbidden hypothesis
    ground (two-lane order 2026-09-06). They appear as observables inside actors and nowhere else.
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta
from typing import Any

from countries import actor, build_pack, dataset, domain, edge, era, miner, source_class

CODE = "CH"
NAME = "Switzerland"
REGION_COMMAND = "EUROPE"
CURRENCY = "CHF"

PIT_STAMPS: tuple[str, ...] = ("event_time", "period_time", "publication_time", "available_time",
                               "revision_time", "retrieval_time")

#: Every Swiss-franc leg the box can quote, plus the metal and dollar legs a Swiss mechanism
#: actually reaches. No equity: the SMI is absent from the broker universe and its constituents
#: are forbidden hypothesis ground.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "USDCHF", "EURCHF", "GBPCHF", "CHFJPY", "AUDCHF", "CADCHF", "NZDCHF",
    "CHFSEK", "CHFNOK", "CHFDKK", "CHFPLN", "CHFHUF", "CHFSGD",
    "XAUUSD", "XAUEUR", "XAGUSD", "USDX",
)

#: What Switzerland's economics run through that Fusion does not quote.
TRANSMISSION_TARGETS: tuple[dict[str, str], ...] = (
    {"name": "SMI (Swiss Market Index)", "venue": "SIX Swiss Exchange / Eurex",
     "role": "the Swiss equity bloc; its expiry settles on the OPENING auction, which is a "
             "different mechanic from every other European index the desk quotes",
     "route": "no executable Swiss index exists here. Swiss equity risk reaches the desk only "
              "through the franc, and that is a weak and lagged route which the pack states."},
    {"name": "SARON and SARON futures", "venue": "SIX / Eurex",
     "role": "the Swiss overnight benchmark; SARON compounded is the reference in the Swiss "
             "mortgage market and the instrument the SNB policy rate steers",
     "route": "USDCHF, EURCHF -- the policy path is an input and never a leg"},
    {"name": "Swiss Confederation 10y bond and the CONF future", "venue": "Eurex",
     "role": "the only Swiss duration instrument; the Confederation's debt brake makes issuance "
             "tiny, so the bond trades at a scarcity premium that is itself an observable",
     "route": "USDCHF, EURCHF"},
    {"name": "SNB sight deposits (Giroguthaben / avoirs a vue)", "venue": "SNB publication",
     "role": "NOT AN INSTRUMENT BUT THE CENTRAL OBSERVABLE OF THIS PACK. The weekly change is "
             "the mechanical footprint of FX intervention plus banking-system noise.",
     "route": "USDCHF, EURCHF, CHFJPY -- the conditioning variable for every intervention edge"},
    {"name": "CHF/USD cross-currency basis", "venue": "OTC",
     "role": "the price of borrowing dollars against francs; it dislocates over reporting dates "
             "and is the mechanism behind the franc's year-end behaviour",
     "route": "USDCHF, EURCHF"},
    {"name": "SXI Real Estate and the Swiss mortgage complex", "venue": "SIX",
     "role": "the domestic transmission channel of the SNB's rate; Swiss mortgages are heavily "
             "SARON-linked, so transmission is fast by European standards",
     "route": "no executable leg; a domestic-demand observable only"},
)


def easter_sunday(year: int) -> date:
    """Gregorian Easter. Four Swiss market closures hang off it."""
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
    """SIX Swiss Exchange trading holidays -- eleven days, the longest list in western Europe.

    Switzerland closes its exchange on both 2 January (Berchtoldstag) and both halves of the
    year-end (24 and 31 December), which no other market in this department does. A cross-market
    spread with a Swiss leg therefore has more forced one-sided days than any other European pair.
    Note that 1 August, the national day, is a FIXED date with no substitution: in 2026 it falls
    on a Saturday and costs the market nothing at all.
    """
    e = easter_sunday(year)
    return {
        date(year, 1, 1): "Neujahr (New Year's Day)",
        date(year, 1, 2): "Berchtoldstag (2 January -- Swiss-specific closure)",
        e - timedelta(days=2): "Karfreitag (Good Friday)",
        e + timedelta(days=1): "Ostermontag (Easter Monday)",
        date(year, 5, 1): "Tag der Arbeit (Labour Day)",
        e + timedelta(days=39): "Auffahrt (Ascension)",
        e + timedelta(days=50): "Pfingstmontag (Whit Monday)",
        date(year, 8, 1): "Bundesfeier (National Day -- no weekend substitution)",
        date(year, 12, 24): "Heiligabend (Christmas Eve)",
        date(year, 12, 25): "Weihnachten (Christmas Day)",
        date(year, 12, 26): "Stephanstag (Boxing Day)",
        date(year, 12, 31): "Silvester (New Year's Eve)",
    }


def cantonal_holidays(canton: str, year: int) -> dict[date, str]:
    """Cantonal BANKING holidays -- the days a Swiss counterparty cannot settle while SIX trades.

    Switzerland has one federal holiday (1 August) and twenty-six cantonal calendars. The
    research object is the asymmetry: on Fronleichnam a Zug or Lucerne bank is shut and the
    exchange is open; on Sechselaeuten Zurich's own working day is half a day while Geneva's is
    whole. A Swiss settlement study that uses one national calendar is wrong roughly a dozen days
    a year, and always in the same cantons.
    """
    code = str(canton).lower()
    e = easter_sunday(year)
    if code == "zh":
        return {
            date(year, 1, 2): "Berchtoldstag",
            e + timedelta(days=39): "Auffahrt",
            # Sechselaeuten: the third Monday of April, a Zurich half-day
            date(year, 4, 1 + (0 - date(year, 4, 1).weekday()) % 7 + 14): (
                "Sechselaeuten (Zurich half-day; the city's own working calendar, not SIX's)"),
            date(year, 9, 1 + (0 - date(year, 9, 1).weekday()) % 7 + 7): (
                "Knabenschiessen Monday (Zurich half-day)"),
        }
    if code == "ge":
        return {
            e + timedelta(days=39): "Ascension",
            date(year, 9, 1 + (3 - date(year, 9, 1).weekday()) % 7 + 7): (
                "Jeune genevois (the Thursday after the first Sunday of September)"),
            date(year, 12, 31): "Restauration de la Republique (31 December)",
        }
    if code == "zg":
        return {
            date(year, 1, 2): "Berchtoldstag",
            e + timedelta(days=60): "Fronleichnam (Corpus Christi -- Catholic cantons only)",
            date(year, 8, 15): "Mariae Himmelfahrt (Assumption)",
            date(year, 11, 1): "Allerheiligen (All Saints)",
            date(year, 12, 8): "Mariae Empfaengnis (Immaculate Conception)",
        }
    if code == "ti":
        return {
            date(year, 1, 6): "Epifania",
            date(year, 3, 19): "San Giuseppe",
            e + timedelta(days=60): "Corpus Domini",
            date(year, 6, 29): "Santi Pietro e Paolo",
            date(year, 8, 15): "Assunzione",
            date(year, 11, 1): "Ognissanti",
            date(year, 12, 8): "Immacolata Concezione",
        }
    raise KeyError(f"unknown canton {canton!r}; this pack carries zh, ge, zg, ti as the four "
                   f"that matter for banking, trading and language")


def third_friday(year: int, month: int) -> date:
    """Eurex expiry for the SMI complex."""
    first = date(year, month, 1)
    return date(year, month, 1 + (4 - first.weekday()) % 7 + 14)


def snb_assessment_rule(year: int) -> str:
    """The SNB's own published cadence, as a sentence a miner can check a date against."""
    return (f"four monetary policy assessments in {year}, one per quarter, in the second half of "
            f"March, June, September and December; announcement 09:30 CET, news conference "
            f"10:00 CET; the June and December assessments carry the full conditional inflation "
            f"forecast")


def _iso(table: dict[date, str]) -> dict[str, str]:
    return {d.isoformat(): n for d, n in sorted(table.items())}


HOLIDAYS_RULE: dict[str, Any] = {
    "calendar": "SIX Swiss Exchange trading holidays, with the cantonal banking calendars beside",
    "rule": "SIX closes on 1 and 2 January, Good Friday, Easter Monday, 1 May, Ascension, Whit "
            "Monday, 1 August, and 24, 25, 26 and 31 December. The movable four are derived from "
            "the Gregorian computus in `easter_sunday`; the fixed seven never shift for a "
            "weekend, so a 1 August on a Saturday costs the market no session at all.",
    "function": "countries.ch.pack:holidays",
    "table": {y: _iso(holidays(y)) for y in (2024, 2025, 2026)},
    "cantonal_tables": {c: {y: _iso(cantonal_holidays(c, y)) for y in (2024, 2025, 2026)}
                        for c in ("zh", "ge", "zg", "ti")},
    "asymmetries": (
        "2 January: SIX closed, Xetra and Euronext open. One forced one-sided day every year in "
        "any GER40-or-FRA40-versus-Swiss spread, and it lands in the thinnest week of the year.",
        "Fronleichnam (Corpus Christi, Easter+60): the Catholic cantons' banks are shut and SIX "
        "trades. A Swiss settlement date computed from a national calendar is wrong that day.",
        "1 August 2026 falls on a Saturday: the national day costs zero sessions. The count of "
        "Swiss trading days per year is NOT constant and a per-year normalisation must use the "
        "computed calendar rather than a fixed 252.",
        "Ascension and Whit Monday: SIX closed, Euronext open, Xetra closed on Whit Monday only. "
        "Three different European answers to the same two days.",
    ),
    "status": "DERIVED_FROM_RULE",
    "verified": {"2026-01-02": "Berchtoldstag, SIX closed -- Xetra and Euronext open",
                 "2026-08-01": "National Day, IN the table because it is the federal "
                               "holiday, but it falls on a Saturday in 2026 and Swiss law "
                               "has no weekend substitution, so it costs the market no "
                               "session. The table is the HOLIDAY list; the count of "
                               "sessions lost is the table minus its weekend entries."},
}

CENTRAL_BANK: dict[str, Any] = {
    "name": "Swiss National Bank (SNB / BNS / BNS)",
    "committee": "the Governing Board -- THREE members, the smallest policy committee in G10, "
                 "which makes the reaction function a person's rather than a vote's and makes "
                 "individual-speaker events unusually informative",
    "policy_rates": ("the SNB policy rate (since 2019, replacing the target range for 3m LIBOR)",
                     "remuneration tiers on sight deposits, which are the operative instrument"),
    "operational_framework": "the SNB steers SARON toward the policy rate through a TIERED "
                             "remuneration of sight deposits. The tiering threshold is itself a "
                             "policy variable and has been changed without a rate change -- an "
                             "easing or tightening that no rate series records.",
    "decision_rule": "FOUR assessments a year, quarterly, in the second half of March, June, "
                     "September and December. Unscheduled decisions are rare and enormous: "
                     "2011-09-06 (the floor) and 2015-01-15 (its abandonment) were both "
                     "unscheduled and both were the largest one-day moves in the pair's history.",
    "announcement_local": "09:30 CET/CEST",
    "announcement_utc": {"winter_cet": "08:30Z", "summer_cest": "07:30Z"},
    "press_conference_local": "10:00 CET/CEST",
    "dst_note": "CET=UTC+1 winter, CEST=UTC+2 summer, switching on the last Sunday of March and "
                "October -- the same weekends as the euro area, so the Zurich-Frankfurt offset "
                "is zero all year and the Zurich-London offset a constant one hour. It is the "
                "Zurich-to-New-York offset that breaks for two weeks in March and one in "
                "November, which matters because the 09:30 CET announcement lands in the Asian "
                "afternoon and the US is not yet a participant.",
    "time_change_note": "the 09:30 CET announcement time has been stable through the sample the "
                        "desk's bars cover; no known clock break since 2018.",
    "assessments": "the June and December assessments carry the full conditional inflation "
                   "forecast; March and September carry a shorter statement. The forecast "
                   "meetings are the ones with the larger franc reaction.",
    "decisions": {
        "2024": {"dates": ("2024-03-21", "2024-06-20", "2024-09-26", "2024-12-12"),
                 "confidence": "high -- the four published 2024 assessments. 2024-03-21 was the "
                               "first cut by any G10 central bank in the cycle, which is why the "
                               "franc's reaction that day is not comparable to any other."},
        "2025": {"dates": ("2025-03-20", "2025-06-19", "2025-09-25", "2025-12-11"),
                 "confidence": "high"},
        "2026": {"dates": ("2026-03-19", "2026-06-18", "2026-09-24", "2026-12-10"),
                 "confidence": "DECLARED, UNVERIFIED -- derived from the SNB's standing quarterly "
                               "rule (third or fourth Thursday of the quarter-ending month). "
                               "Re-read snb.ch before any 2026 event study."},
    },
    "rule_if_dates_unknown": "a Thursday in the second half of March, June, September and "
                             "December; announcement 09:30 CET; see `snb_assessment_rule`.",
    "intervention_policy": "the SNB states it is willing to be active in the foreign exchange "
                           "market as necessary. It does NOT announce individual operations, so "
                           "the weekly sight-deposit series is the only public trace and it is "
                           "contaminated by ordinary banking-system flows -- which is exactly "
                           "why it needs a control and not a threshold.",
    "source": "https://www.snb.ch/en/the-snb/mandates-goals/monetary-policy",
}

FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "SNB weekly sight deposits (Giroguthaben / avoirs a vue)",
     "administrator": "Swiss National Bank",
     "local_time": "Monday, around 09:00 CET/CEST, for the week ended the previous Friday",
     "utc": {"winter": "08:00Z Monday", "summer": "07:00Z Monday"},
     "dst_note": "CET/CEST; the publication is a WEEKDAY rule, not a clock rule, so a Monday "
                 "that is a Swiss holiday shifts it. The 2 January and Easter Monday cases both "
                 "occur and a weekly series joined on a fixed Monday grid silently drops them.",
     "window": "a weekly stock, not a flow: the research object is the WEEK-ON-WEEK CHANGE",
     "what_it_prices": "nothing directly. It is the balance-sheet counterpart of franc-selling "
                       "intervention and of every other central-bank operation at once.",
     "why_it_matters": "the nearest thing in G10 to a published central-bank FX footprint, free "
                       "and dated. It is also the pack's most dangerous series: a rise can be "
                       "intervention, a maturing repo, a government account movement or a "
                       "year-end banking effect, and only a control tells them apart."},
    {"name": "SARON fixings",
     "administrator": "SIX Swiss Exchange",
     "local_time": "intraday fixings around 12:00 and 16:00 CET; the definitive close at 18:00 CET",
     "utc": {"winter": "11:00Z / 15:00Z / 17:00Z", "summer": "10:00Z / 14:00Z / 16:00Z"},
     "dst_note": "CET/CEST. Confidence: the three-fixing structure is declared from public "
                 "knowledge; verify the exact times against the SIX SARON specification before "
                 "using an intraday fixing as an event time.",
     "window": "a volume-weighted rate over the repo trading day up to the fixing",
     "what_it_prices": "secured overnight francs; the compounded SARON is the reference in the "
                       "Swiss mortgage market",
     "why_it_matters": "SARON is where an SNB tiering change shows up WITHOUT a policy-rate "
                       "change, which is the only way to observe that kind of easing"},
    {"name": "LBMA Gold Price (the London fixes)",
     "administrator": "ICE Benchmark Administration",
     "local_time": "10:30 and 15:00 London",
     "utc": {"winter": "10:30Z and 15:00Z", "summer": "09:30Z and 14:00Z"},
     "dst_note": "London clock, moving with BST on the same weekends as CET/CEST, so the "
                 "Zurich-to-London offset is a constant hour. The physical Swiss refining day "
                 "is a CET one and the price is a London one; the pack keeps them separate.",
     "window": "an electronic auction with price rounds",
     "what_it_prices": "the settlement price for physical gold, including the metal Swiss "
                       "refineries are transforming",
     "why_it_matters": "Switzerland is the physical market's workshop; the customs gold-flow "
                       "statistics are upstream of this price and are published monthly"},
    {"name": "WM/Refinitiv 16:00 London closing spot rate",
     "administrator": "LSEG (WM/Refinitiv)", "local_time": "16:00 London",
     "utc": {"winter": "16:00Z", "summer": "15:00Z"},
     "dst_note": "London is GMT (=UTC) in winter and BST (=UTC+1) in summer, switching on the"
                 "same weekends as CET/CEST, so the Zurich-to-London offset is a constant one"
                 "hour all year and this fix always lands 17:00 Zurich. It is the"
                 "Zurich-to-New-York offset that breaks for two weeks in March and one in"
                 "November, which is when a franc month-end study keyed to a US clock drifts.",
     "window": "15:57:30-16:02:30 London",
     "what_it_prices": "the benchmark index funds convert at",
     "why_it_matters": "Swiss pension funds' currency hedge rebalancing lands here; the Swiss "
                       "hedge ratio is high by international standards, so the month-end franc "
                       "flow is larger relative to the economy than the euro one"},
    {"name": "SNB daily exchange rates",
     "administrator": "Swiss National Bank",
     "local_time": "end of the Swiss banking day; published in the SNB data portal",
     "utc": {"winter": "declared: evening CET", "summer": "declared: evening CEST"},
     "dst_note": "CET/CEST. Confidence: the SNB publishes daily FX rates in its data portal, but "
                 "unlike the ECB it does not operate a CONCERTATION FIX with a named time. The "
                 "pack records that as a structural difference rather than inventing a time: "
                 "Switzerland has no equivalent of the 14:15 CET ECB reference rate, so no "
                 "Swiss fix-flow hypothesis has a domestic clock to hang on.",
     "window": "none published",
     "what_it_prices": "statistical and accounting reference only",
     "why_it_matters": "its ABSENCE is the finding: every franc fix effect on this desk must be "
                       "attributed to the London WMR fix or to the ECB's, never to a Swiss one"},
)

SETTLEMENT_CONVENTIONS: dict[str, Any] = {
    "fx_spot": "T+2 for USDCHF and the franc crosses; the value date must be good in both "
               "currencies, and the SIX/cantonal split means a Swiss bank holiday can block a "
               "value date on a day the exchange is trading",
    "fx_value_date_note": "Berchtoldstag (2 January) is a Swiss settlement closure in the same "
                          "week as the year-end turn, so the first franc spot value date of a "
                          "year is systematically later than the first euro one -- which shows "
                          "up as an apparent jump in CHF forward points every January",
    "cls": "CHF settles in CLS, so the franc leg of a G10 pair carries no Herstatt risk; the "
           "CHFPLN and CHFHUF legs in this pack's executable list do, because the other side "
           "does not settle in CLS",
    "cash_equity": "T+2 on SIX today; Switzerland has aligned with the EU and UK on the "
                   "11 October 2027 move to T+1 (declared; verify against SIX)",
    "bonds": "T+2 for Confederation bonds through SIX SIS",
    "derivatives": "SMI futures and options are Eurex contracts, cash-settled T+1",
    "month_end": "Swiss pension funds rebalance currency hedges at month-end into the 16:00 "
                 "London fix, two business days before the value date; the Swiss hedge ratio is "
                 "high enough that this is a first-order franc flow rather than a footnote",
}

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "SIX Swiss Exchange", "mic": "XSWX", "tz": "Europe/Zurich",
     "symbols": (),
     "session_local": "09:00-17:20 CET continuous, closing auction 17:20-17:30",
     "expiry_rule": "third Friday of the expiry month (the derivatives trade on Eurex)",
     "settlement_price_rule": "the SMI final settlement value is derived from the OPENING prices "
                              "of the constituents on the last trading day -- the opening "
                              "auction, not the close and not a midday auction. Switzerland is "
                              "therefore the third distinct European settlement mechanic after "
                              "the DAX's 13:00 CET auction and the CAC's afternoon average. "
                              "Confidence: declared; verify against the Eurex SMI specification.",
     "witching": "the quarterly Mar/Jun/Sep/Dec expiry, locally Verfall or grosser Verfall",
     "notes": "NO EXECUTABLE SYMBOL. The SMI is absent from the broker universe; this row exists "
              "so a Swiss expiry hypothesis is routed into the franc or declared UNMEASURED "
              "rather than silently proxied by GER40."},
    {"name": "Eurex (the Swiss derivatives listing venue)", "mic": "XEUR", "tz": "Europe/Zurich",
     "symbols": (),
     "session_local": "SMI futures trade well beyond the SIX cash session",
     "expiry_rule": "third Friday",
     "settlement_price_rule": "as above; the futures' last trading day is the settlement day",
     "witching": "shared with the German and European complex, so a Swiss expiry effect and a "
                 "German one land on the same morning and must be separated by the index, not "
                 "by the date",
     "notes": "the shared date is why GER40 is a CONTROL and not a proxy in domain CH-F"},
)

POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "CFTC Commitments of Traders -- Swiss Franc (CME contract 6S)",
     "covers": "CHF", "published": "Friday 15:30 ET for Tuesday's positions", "lag_days": 3.0,
     "licence": "public domain", "root": "https://www.cftc.gov/MarketReports/CommitmentsofTraders/",
     "note": "the franc's speculative position has been structurally SHORT for most of the "
             "sample because the franc is a funding currency in carry trades. An 'extreme short' "
             "is therefore the normal state and a percentile against a rolling window is the "
             "only defensible reading; a raw level threshold fires permanently."},
    {"name": "SNB weekly sight deposits",
     "covers": "the SNB's own balance sheet, weekly", "published": "Monday around 09:00 CET",
     "lag_days": 3.0, "licence": "public", "root": "https://data.snb.ch/",
     "note": "THE pack's central series. It measures the central bank's footprint rather than "
             "speculators', which makes it the complement of COT and not a substitute."},
    {"name": "SNB quarterly foreign currency reserves and their currency allocation",
     "covers": "the stock and mix of SNB FX reserves", "published": "quarterly, about one month "
               "after quarter end", "lag_days": 30.0, "licence": "public",
     "root": "https://data.snb.ch/",
     "note": "the currency allocation is the reason SNB intervention is a EURUSD event as well "
             "as a franc event: francs sold for euros are partly recycled into dollars"},
    {"name": "SNB quarterly equity holdings (13F filings in the US)",
     "covers": "the SNB's US equity portfolio", "published": "quarterly with the SEC 13F cycle",
     "lag_days": 45.0, "licence": "public domain (SEC)",
     "root": "https://www.sec.gov/cgi-bin/browse-edgar",
     "note": "a central bank that files a 13F is unique. It is an observable about the SNB's "
             "balance sheet and NOT hypothesis ground: acting on its single-name holdings would "
             "breach the two-lane order."},
    {"name": "NO DAILY SWISS POSITIONING SERIES EXISTS -- declared absence",
     "covers": "nothing", "published": "never", "lag_days": 0.0, "licence": "n/a", "root": "n/a",
     "note": "Eurex publishes SMI open interest but the desk has no SMI leg, so there is no "
             "daily Swiss positioning input that is also executable. Every Swiss crowding "
             "hypothesis at daily frequency is UNMEASURED and must say so (L1.28a)."},
)

NATIVE_LANGUAGES: tuple[str, ...] = ("de", "fr", "it", "en")

#: Swiss German, Swiss French and Swiss Italian market vocabulary. Note the three words for
#: inflation: Teuerung, rencherissement and rincaro. A miner asking for "Inflation", "inflation"
#: or "inflazione" on a Swiss source finds the foreign word and misses the domestic one.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "de_policy": ("SNB-Zinsentscheid", "geldpolitische Lagebeurteilung", "Leitzins",
                  "SNB-Leitzins", "Teuerung", "bedingte Inflationsprognose", "Negativzins",
                  "Freibetrag", "Abstufung der Verzinsung", "Mediengespräch"),
    "de_fx": ("Sichtguthaben", "Girokonten", "Giroguthaben", "Devisenmarktinterventionen",
              "Mindestkurs", "Untergrenze", "Frankenschock", "Frankenstärke",
              "Aufwertungsdruck", "sicherer Hafen", "Devisenreserven"),
    "de_market": ("SMI-Verfall", "grosser Verfall", "Verfallstag", "Eröffnungsauktion",
                  "Schlussauktion", "Berchtoldstag", "Bundesfeier", "Sechseläuten",
                  "Fronleichnam", "Handelstag"),
    "de_macro": ("KOF-Konjunkturbarometer", "Landesindex der Konsumentenpreise", "LIK",
                 "SECO-Konjunkturprognose", "Uhrenexporte", "Pensionskasse", "BVG-Mindestzins",
                 "Schuldenbremse", "Nationalbankgewinn", "Gewinnausschüttung"),
    "fr_policy": ("BNS", "taux directeur", "examen de la situation économique et monétaire",
                  "renchérissement", "prévision conditionnelle d'inflation", "taux négatif",
                  "conférence de presse"),
    "fr_fx": ("avoirs à vue", "interventions sur le marché des changes", "cours plancher",
              "franc fort", "pression à la hausse", "valeur refuge", "réserves de devises"),
    "fr_market": ("échéance", "séance de clôture", "jour férié cantonal", "Jeûne genevois",
                  "Restauration de la République"),
    "fr_macro": ("indice des prix a la consommation", "baromètre conjoncturel du KOF",
                 "caisse de pension", "exportations horlogères", "frein à l'endettement"),
    "it_policy": ("BNS", "tasso guida", "valutazione della situazione economica e monetaria",
                  "rincaro", "previsione condizionata di inflazione", "tasso negativo"),
    "it_fx": ("depositi a vista", "interventi sul mercato dei cambi", "corso minimo",
              "franco forte", "bene rifugio", "riserve valutarie"),
    "it_market": ("scadenza", "asta di chiusura", "giorno festivo cantonale", "Corpus Domini",
                  "San Giuseppe"),
    "en_desk": ("sight deposits", "the franc floor", "the Frankenshock", "safe haven",
                "tiering threshold", "conditional inflation forecast", "refining flows",
                "the year-end turn"),
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
    _src("ch.official.snb", "SNB publications, data portal, speeches and the weekly balance sheet",
         layer="official",
         roots=("https://www.snb.ch/en/", "https://data.snb.ch/",
                "https://www.snb.ch/en/publications/communication/speeches",
                "https://www.snb.ch/en/the-snb/mandates-goals/monetary-policy"),
         languages=("de", "fr", "it", "en"), licence="public, attribution",
         access_label="OPEN_DATA", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         weight=1.0,
         queries=("Sichtguthaben inländischer Banken wöchentlich Statistik",
                  "geldpolitische Lagebeurteilung Leitzins Teuerungsprognose",
                  "avoirs à vue des banques résidentes statistique hebdomadaire",
                  "examen de la situation économique et monétaire taux directeur",
                  "depositi a vista banche residenti statistica settimanale"),
         notes="data.snb.ch carries the weekly sight deposits, the quarterly reserves and their "
               "currency allocation, all free and all with a stable series key. The SPEECHES "
               "matter more here than anywhere else in this department because the Governing "
               "Board is three people, so an individual speaker is a third of the reaction "
               "function."),
    _src("ch.official.federal", "Federal statistics, customs, SECO and the pension supervisor",
         layer="official",
         roots=("https://www.bfs.admin.ch/", "https://www.seco.admin.ch/",
                "https://www.bazg.admin.ch/", "https://www.oak-bv.admin.ch/",
                "https://www.bsv.admin.ch/"),
         languages=("de", "fr", "it", "en"), licence="public, attribution",
         access_label="OPEN_DATA", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         weight=1.0,
         queries=("Landesindex der Konsumentenpreise Monatswerte BFS",
                  "Aussenhandelsstatistik Gold Einfuhr Ausfuhr nach Land",
                  "statistique du commerce extérieur or importations par pays",
                  "OAK BV Erhebung Vermögensallokation Währungsabsicherung Pensionskassen"),
         notes="BAZG (customs) is the one that publishes MONTHLY GOLD IMPORTS AND EXPORTS BY "
               "COUNTERPARTY COUNTRY -- a physical-flow series with no equivalent anywhere else "
               "and the direct upstream of domain CH-G. OAK BV publishes the aggregate SECOND-"
               "PILLAR CURRENCY HEDGE RATIO, which is the forced-flow parameter behind the "
               "month-end franc bid."),
    _src("ch.institutional.venue_and_bodies",
         "SIX, Eurex and the Swiss banking, funds and pension industry bodies",
         layer="institutional",
         roots=("https://www.six-group.com/en/products-services/the-swiss-stock-exchange",
                "https://www.eurex.com/ex-en/", "https://www.swissbanking.ch/",
                "https://www.asip.ch/", "https://www.sfama.ch/"),
         languages=("de", "fr", "en"), licence="public page, restricted redistribution",
         access_label="PUBLIC_WITH_TERMS", credibility="AUTHORITATIVE",
         predictive_state="UNTESTED", weight=1.0,
         queries=("SMI Schlussabrechnung Eröffnungskurse Verfall Kontraktspezifikation",
                  "SARON Fixing Methodik SIX Berechnung",
                  "ASIP Anlagerichtlinien Währungsabsicherung Empfehlung",
                  "Bankiervereinigung Zinsmarge Hypothekarmarkt Studie"),
         notes="the ONLY authority on the SMI's OPENING-auction settlement, which is the third "
               "distinct European settlement mechanic after the DAX's midday auction and the "
               "CAC's afternoon average. ASIP's investment guidelines are where the pension "
               "hedging convention is actually written."),
    _src("ch.academic.research", "SNB research, KOF, Gerzensee and the Swiss Finance Institute",
         layer="academic",
         roots=("https://www.snb.ch/en/publications/research/working-papers",
                "https://kof.ethz.ch/", "https://www.szgerzensee.ch/",
                "https://www.sfi.ch/", "https://www.suerf.org/"),
         languages=("de", "en"), licence="public, attribution",
         access_label="PUBLIC", credibility="RELIABLE", predictive_state="UNTESTED", weight=0.9,
         queries=("SNB Working Paper Devisenmarktinterventionen Reaktionsfunktion",
                  "Mindestkurs Aufhebung Ereignisstudie Franken",
                  "KOF Konjunkturbarometer Revision Vintage Methodik",
                  "safe haven currency Swiss franc risk-off empirical"),
         notes="the SNB's own working papers describe the intervention reaction function in more "
               "detail than any commentary does, and KOF publishes its BAROMETER VINTAGES -- "
               "which is what makes the hindsight control in domain CH-I constructible at all."),
    _src("ch.practitioner.strategy", "Swiss bank strategy notes and the pension practitioner press",
         layer="practitioner",
         roots=("https://www.ubs.com/global/en/wealth-management/insights.html",
                "https://www.zkb.ch/de/blog.html", "https://www.vontobel.com/en/insights/",
                "https://www.vorsorgeforum.ch/", "https://www.cfainstitute.org/societies"),
         languages=("de", "fr", "en"), licence="mixed: public commentary, licensed full notes",
         access_label="ACCESS_UNCLEAR", credibility="RELIABLE", predictive_state="UNTESTED",
         weight=0.6,
         queries=("Frankenausblick SNB Zinsentscheid Prognose Kommentar",
                  "perspectives franc suisse BNS taux directeur commentaire",
                  "Deckungsgrad Pensionskassen Währungsabsicherung Diskussion",
                  "Umwandlungssatz BVG Mindestzins Debatte"),
         notes="vorsorgeforum is the Swiss pension practitioners' own trade press and is where "
               "the hedge-ratio debate actually happens in German. ACCESS_UNCLEAR: bank pieces "
               "have a public teaser and a licensed body, and confusing the two is the standard "
               "error in this layer."),
    _src("ch.retail_ecology.communities",
         "Swiss retail investor forums and the personal-finance communities",
         layer="retail_ecology",
         roots=("https://www.cash.ch/forum", "https://www.finanzen.ch/forum",
                "https://forum.mustachianpost.com/",
                "https://www.reddit.com/r/SwissPersonalFinance/"),
         languages=("de", "fr", "en"), licence="public forum, quote-and-cite only",
         access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE", predictive_state="UNTESTED",
         weight=0.25, machine_use_allowed=False,
         queries=("Negativzins Freibetrag Bank Weitergabe Diskussion",
                  "Frankenstärke Exporteure Absicherung Meinung",
                  "SMI Verfall Abrechnung Spekulation Forum",
                  "hypothèque SARON ou taux fixe discussion"),
         notes="machine_use_allowed=False: the cash.ch and finanzen.ch forum terms forbid "
               "automated extraction, so they are REGISTERED and never scraped. Credibility "
               "UNRELIABLE at weight 0.25 -- kept, not dropped: the retail debate about SARON "
               "versus fixed mortgages is a real-time read on the transmission channel in "
               "domain CH-K even when every individual post is wrong."),
    _src("ch.app_ecosystem.platforms", "Swiss broker and neobank platforms and their data surfaces",
         layer="app_ecosystem",
         roots=("https://www.swissquote.ch/", "https://www.yuh.com/", "https://www.neon-free.ch/",
                "https://www.postfinance.ch/en/private/products/investing.html",
                "https://www.moneyland.ch/en/mortgage-comparison",
                "https://www.tradingview.com/symbols/SIX-SMI/"),
         languages=("de", "fr", "en"), licence="per-platform terms",
         access_label="PUBLIC_WITH_TERMS", credibility="UNKNOWN",
         predictive_state="NARRATIVE_FEATURE", weight=0.4,
         queries=("Swissquote meistgehandelte Titel Statistik",
                  "moneyland Hypothekarzinsen Vergleich SARON Festhypothek",
                  "comparis Hypothek Richtsatz Verlauf"),
         notes="moneyland's published MORTGAGE RATE COMPARISON is the one item in this layer with "
               "a real predictive claim attached: it is the retail-visible price of the SARON "
               "transmission in domain CH-K and it is updated continuously. The rest is "
               "attention data and is labelled NARRATIVE_FEATURE accordingly."),
    _src("ch.media.business_press", "Swiss financial newspapers in three languages",
         layer="media",
         roots=("https://www.nzz.ch/", "https://www.fuw.ch/", "https://www.letemps.ch/",
                "https://www.handelszeitung.ch/", "https://www.cdt.ch/"),
         languages=("de", "fr", "it"), licence="paywalled; terms forbid bulk extraction",
         access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
         predictive_state="NARRATIVE_FEATURE", weight=0.5, machine_use_allowed=False,
         queries=("Finanz und Wirtschaft SNB Devisenmarkt Interventionen Analyse",
                  "NZZ Franken Aufwertung Nationalbank Bilanz",
                  "Le Temps BNS interventions marché des changes",
                  "Corriere del Ticino franco forte esportazioni"),
         notes="machine_use_allowed=False for all five: paywalled with terms forbidding bulk "
               "extraction. Registered, never scraped. Finanz und Wirtschaft is the one that "
               "actually reports the sight-deposit print each Monday with a mechanism attached "
               "rather than as a number."),
    _src("ch.archive.historical", "Swiss historical statistics and digitised record",
         layer="archive",
         roots=("https://data.snb.ch/en/topics/snb#!/doc/explanations_snb",
                "https://www.bar.admin.ch/", "https://www.e-periodica.ch/",
                "https://www.bfs.admin.ch/bfs/en/home/statistics/catalogues-databases.html",
                "https://web.archive.org/"),
         languages=("de", "fr", "it"), licence="public archive",
         access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         weight=0.8,
         queries=("SNB historische Zeitreihen Sichtguthaben seit 1907",
                  "Mindestkurs 2011 Medienmitteilung Archiv",
                  "e-periodica Schweizerische Nationalbank Quartalsheft historisch",
                  "Bundesarchiv Nationalbank Goldreserven Dossier"),
         notes="THE ARCHIVE IS LOAD-BEARING FOR THIS PACK. This box's FX bars begin 2018-01-02, "
               "so the 1.20 floor (2011-2015), the Frankenschock and the whole negative-rate "
               "introduction are OUTSIDE the sample. Every statistic this pack quotes about them "
               "must come from here and be cited, never recomputed from bars that do not exist."),
    _src("ch.physical_economy.refining_and_trade",
         "Swiss refining, watch exports, power and the physical gold corridor",
         layer="physical_economy",
         roots=("https://www.bazg.admin.ch/bazg/en/home/themen/schweizerische-"
                "aussenhandelsstatistik.html",
                "https://www.fhs.swiss/", "https://www.swissgrid.ch/",
                "https://www.lbma.org.uk/prices-and-data"),
         languages=("de", "fr", "en"), licence="public",
         access_label="OPEN_DATA", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         weight=0.9,
         queries=("Swiss-Impex Gold Zolltarifnummer 7108 Ausfuhr Hongkong Indien",
                  "exportations horlogères mensuelles par destination FH",
                  "Swissgrid Netzlast Import Export Bilanz"),
         notes="two-thirds of world gold refining capacity sits in four Swiss plants and the "
               "customs regime obliges them to report. Swiss net exports to Asia against net "
               "imports from the United Kingdom IS the physical gold market's direction, "
               "observed from the workshop; the UK pack observes the same flow from the vault."),
    _src("ch.source_graph.citation_and_link",
         "Citation and link graphs over the Swiss corpus",
         layer="source_graph",
         roots=("https://ideas.repec.org/s/snb/snbwpa.html", "https://openalex.org/",
                "https://www.e-periodica.ch/", "https://github.com/search?q=SARON"),
         languages=("en", "de"), licence="open data",
         access_label="OPEN_DATA", credibility="RELIABLE", predictive_state="UNTESTED",
         weight=0.5,
         queries=("RePEc cited by SNB working paper foreign exchange intervention",
                  "OpenAlex citations Swiss franc safe haven",
                  "github SARON compounding convention implementation"),
         notes="used to find what this pack has NOT named: who cites the SNB's intervention "
               "papers, and which public repositories implement the SARON compounding convention "
               "-- the fiddly part of Swiss rates that people publish because it is tedious."),
)

#: All ten layers are populated for Switzerland, so this table is empty BY MEASUREMENT and
#: `source_layer_coverage` proves it rather than asserting it.
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
    _ds("SNB weekly sight deposits",
        source="SNB data portal", coverage="total sight deposits and the domestic-bank split",
        frequency="weekly", publication_lag_days=3.0,
        revisions="the SNB restates prior weeks occasionally and without announcement; a naive "
                  "cache never sees it, which is the classic leak in every published study that "
                  "uses this series",
        licence="public, attribution", history_from="1997", pit_feasible=True,
        assets=("USDCHF", "EURCHF", "CHFJPY"),
        mechanism_families=("central_bank_flow", "intervention", "regime_condition"),
        how_to_fetch="data.snb.ch series for Giroguthaben, CSV per series key",
        pit={"event_time": "the Friday the stock is measured at",
             "period_time": "the week ending that Friday",
             "publication_time": "the following Monday around 09:00 CET",
             "available_time": "same -- a three-day lag that means Monday's franc move is NOT "
                               "conditionable on the week that just ended until after the open",
             "revision_time": "silent restatements of prior weeks",
             "retrieval_time": "crawler stamp"}),
    _ds("SNB monetary policy assessments",
        source="SNB press releases", coverage="every assessment since 2000",
        frequency="4 per year", publication_lag_days=0.0,
        revisions="none; the conditional inflation forecast is superseded rather than revised",
        licence="public", history_from="2000", pit_feasible=True,
        assets=("USDCHF", "EURCHF", "CHFJPY", "XAUUSD"),
        mechanism_families=("policy_surprise", "event_drift"),
        how_to_fetch="snb.ch press release pages, one per assessment",
        pit={"event_time": "09:30 CET announcement",
             "period_time": "the quarter the assessment covers",
             "publication_time": "09:30 CET",
             "available_time": "09:30 CET",
             "revision_time": "never",
             "retrieval_time": "crawler stamp"}),
    _ds("SNB quarterly FX reserves and currency allocation",
        source="SNB", coverage="stock and mix of reserves", frequency="quarterly",
        publication_lag_days=30.0,
        revisions="restated with valuation changes; the ALLOCATION shares are the stable part",
        licence="public", history_from="2005", pit_feasible=True,
        assets=("USDCHF", "EURCHF", "EURUSD"),
        mechanism_families=("central_bank_flow", "reserve_recycling"),
        how_to_fetch="data.snb.ch quarterly series",
        pit={"event_time": "quarter end",
             "period_time": "the quarter",
             "publication_time": "about one month after quarter end",
             "available_time": "same",
             "revision_time": "valuation restatements",
             "retrieval_time": "crawler stamp"}),
    _ds("Swiss gold imports and exports by country",
        source="Federal Office for Customs and Border Security (BAZG)",
        coverage="monthly physical gold trade by counterparty country",
        frequency="monthly", publication_lag_days=20.0,
        revisions="routinely revised in the following month's release; the revisions are large "
                  "enough to change the sign of a month's net flow, so the FIRST print and the "
                  "revised one are different series and must not be mixed",
        licence="public", history_from="2012 (the by-country detail was withheld before that)",
        pit_feasible=True, assets=("XAUUSD", "XAUEUR", "XAGUSD"),
        mechanism_families=("physical_flow", "terms_of_trade", "demand_proxy"),
        how_to_fetch="BAZG Swiss-Impex portal, monthly download by commodity code",
        pit={"event_time": "the month the trade occurred in",
             "period_time": "the calendar month",
             "publication_time": "around the 20th of the following month",
             "available_time": "same",
             "revision_time": "the following month's release, routinely",
             "retrieval_time": "crawler stamp"}),
    _ds("KOF Economic Barometer",
        source="KOF Swiss Economic Institute, ETH Zurich", coverage="Switzerland",
        frequency="monthly", publication_lag_days=0.0,
        revisions="the barometer is REBUILT annually and the whole history changes; a backtest "
                  "run on today's vintage is using numbers that did not exist at the time, and "
                  "KOF publishes the vintages, so there is no excuse for getting this wrong",
        licence="public headline", history_from="1991", pit_feasible=True,
        assets=("USDCHF", "EURCHF"),
        mechanism_families=("survey_surprise", "regime_condition"),
        how_to_fetch="kof.ethz.ch release page, monthly, with the vintage archive",
        pit={"event_time": "the release, around 09:00 CET on the last working days of the month",
             "period_time": "the survey month",
             "publication_time": "as above",
             "available_time": "same",
             "revision_time": "the annual rebuild, which rewrites everything",
             "retrieval_time": "crawler stamp"}),
    _ds("Swiss CPI (Landesindex der Konsumentenpreise)",
        source="Federal Statistical Office (BFS)", coverage="Switzerland", frequency="monthly",
        publication_lag_days=3.0,
        revisions="not revised month to month; rebased periodically",
        licence="public", history_from="1914", pit_feasible=True,
        assets=("USDCHF", "EURCHF"),
        mechanism_families=("data_surprise", "policy_expectation"),
        how_to_fetch="bfs.admin.ch release page, 08:30 CET on the release day",
        pit={"event_time": "08:30 CET release",
             "period_time": "the reference month",
             "publication_time": "08:30 CET, typically in the first few working days",
             "available_time": "08:30 CET -- one hour BEFORE the SNB's own 09:30 announcement "
                               "time, which matters on the rare days both fall together",
             "revision_time": "rebasing only",
             "retrieval_time": "crawler stamp"}),
    _ds("Swiss watch exports",
        source="Federation of the Swiss Watch Industry", coverage="export value by destination",
        frequency="monthly", publication_lag_days=20.0,
        revisions="minor", licence="public headline, licensed detail", history_from="2000",
        pit_feasible=True, assets=("USDCHF", "CHFJPY"),
        mechanism_families=("terms_of_trade", "demand_proxy", "cross_asset"),
        how_to_fetch="fhs.swiss monthly press release",
        pit={"event_time": "the month of export",
             "period_time": "the calendar month",
             "publication_time": "around the 20th of the following month",
             "available_time": "same",
             "revision_time": "occasional minor restatement",
             "retrieval_time": "crawler stamp"}),
    _ds("OAK BV Swiss pension fund survey",
        source="Oberaufsichtskommission Berufliche Vorsorge",
        coverage="aggregate Swiss second-pillar assets, allocation and currency hedge ratios",
        frequency="annual", publication_lag_days=120.0,
        revisions="none, but the survey population changes year to year",
        licence="public", history_from="2012", pit_feasible=True,
        assets=("USDCHF", "EURCHF"),
        mechanism_families=("forced_flow", "hedging_demand"),
        how_to_fetch="oak-bv.admin.ch annual report PDF",
        pit={"event_time": "the 31 December the survey refers to",
             "period_time": "the calendar year",
             "publication_time": "the following spring",
             "available_time": "same",
             "revision_time": "never",
             "retrieval_time": "crawler stamp"}),
    _ds("CFTC Commitments of Traders, Swiss Franc",
        source="CFTC", coverage="CME franc futures and options", frequency="weekly",
        publication_lag_days=3.0,
        revisions="silent corrections in later weekly files",
        licence="public domain", history_from="1986", pit_feasible=True,
        assets=("USDCHF", "EURCHF", "CHFJPY"),
        mechanism_families=("positioning", "crowding", "carry_unwind"),
        how_to_fetch="CFTC weekly text and historical archives",
        pit={"event_time": "the Tuesday the positions are as of",
             "period_time": "the same Tuesday close",
             "publication_time": "Friday 15:30 ET",
             "available_time": "Friday 15:30 ET",
             "revision_time": "silent corrections",
             "retrieval_time": "crawler stamp"}),
)


def actors() -> tuple[dict[str, Any], ...]:
    """Fourteen Swiss participants whose constraints produce dated or measurable flow."""
    return (
        actor("Swiss National Bank Governing Board",
              holds="the franc's exchange rate as an explicit policy concern and the largest "
                    "central-bank balance sheet in the world relative to GDP",
              forced_to=("assess policy four times a year on a published calendar",
                         "publish a conditional inflation forecast in June and December",
                         "publish the balance sheet weekly, which reveals the footprint"),
              when="quarterly, second half of March, June, September and December, 09:30 CET",
              information=("Swiss CPI, released 08:30 CET days earlier",
                           "the KOF barometer",
                           "the euro area's own policy stance, which it imports"),
              constraints=("a three-person board, so the reaction function is personal and a "
                           "speech by any one of them is a first-order event",
                           "price stability defined as inflation below 2%, which in Switzerland "
                           "binds on the DEFLATION side more often than the inflation one",
                           "a balance sheet whose size is politically contested"),
              instruments=("USDCHF", "EURCHF", "CHFJPY", "XAUUSD"),
              counterparties=("Swiss banks, through sight deposit remuneration",
                              "the global FX market, through intervention"),
              observables=("the 09:30 CET announcement and the 10:00 CET news conference",
                           "weekly sight deposits",
                           "quarterly reserves and their currency allocation"),
              impact="four scheduled franc events a year plus an unscheduled tail that has twice "
                     "produced the largest one-day move in the pair's history",
              persistence="the stance persists for quarters; the announcement-minute move is "
                          "smaller than the euro area's because the surprise space is narrower",
              falsifier="if USDCHF's 09:30-10:30 CET move on assessment days is "
                        "indistinguishable from the same window on a matched non-assessment "
                        "Thursday across sixteen assessments, the scheduled event carries no "
                        "information on this desk's instruments",
              notes="the June and December forecast assessments should dominate March and "
                    "September; a study that pools all four is averaging two event sizes"),
        actor("Swiss banks holding sight deposits at the SNB",
              holds="franc reserves remunerated in tiers",
              forced_to=("hold whatever reserves the SNB creates -- the aggregate is not their "
                         "choice, only its distribution is",
                         "manage the tiering threshold, which determines the marginal rate"),
              when="continuously, with a pronounced quarter-end and year-end distortion",
              information=("the SNB's tiering parameters", "their own balance-sheet limits"),
              constraints=("leverage ratio and balance-sheet costs that bind at reporting dates, "
                           "which is exactly when the sight-deposit series is least informative "
                           "about intervention",),
              instruments=("USDCHF", "EURCHF"),
              counterparties=("the SNB", "the repo market", "cross-currency basis desks"),
              observables=("the weekly sight-deposit change",
                           "SARON against the policy rate",
                           "the CHF cross-currency basis"),
              impact="they are the channel that turns an intervention into a measurable number "
                     "and the noise that makes that number ambiguous",
              persistence="the quarter-end distortion is annual and predictable",
              falsifier="if the sight-deposit weekly change has the same distribution in "
                        "reporting weeks and non-reporting weeks, the banking-system noise "
                        "component is not separable and the whole intervention proxy is weaker "
                        "than the pack assumes",
              notes="the single most important control in this pack: a sight-deposit rise in the "
                    "last week of a quarter is probably not intervention"),
        actor("Swiss occupational pension funds (Pensionskassen / caisses de pension)",
              holds="around a trillion francs of assets against franc liabilities, with a large "
                    "foreign-asset share and a HIGH currency hedge ratio",
              forced_to=("hedge a policy fraction of foreign exposure, rebalanced on a schedule",
                         "meet the BVG minimum interest rate, which is set politically",
                         "report a coverage ratio"),
              when="month-end and quarter-end, executed into the 16:00 London fix",
              information=("their own coverage ratio",
                           "the OAK BV annual survey of the aggregate"),
              constraints=("a hedging policy set by a board, executed mechanically; when foreign "
                           "equities rally the hedge must be INCREASED, which sells foreign "
                           "currency and buys francs -- the franc's pro-cyclical month-end bid",),
              instruments=("USDCHF", "EURCHF", "CHFJPY"),
              counterparties=("bank FX desks", "the WMR fix window"),
              observables=("the OAK BV hedge ratio",
                           "month-end fix volume",
                           "the month's realised foreign equity return, which sets the sign"),
              impact="a mechanical month-end franc bid after a strong foreign equity month, and "
                     "the reverse after a weak one",
              persistence="the fix window; the sign persists across the month",
              falsifier="if USDCHF's return in the 15:57:30-16:02:30 window on the last business "
                        "day of a month has no relation to the month's realised S&P return, the "
                        "hedge-rebalancing mechanism is not visible at this frequency",
              notes="Switzerland's hedge ratio is high relative to the economy's size, which is "
                    "why this is a first-order franc flow and only a footnote in the euro area"),
        actor("Swiss life insurers under the Swiss Solvency Test",
              holds="long franc liabilities against a scarce supply of franc duration",
              forced_to=("match duration in a market where the Confederation issues almost "
                         "nothing, because the debt brake caps the deficit",
                         "report an SST ratio annually"),
              when="continuous, with an annual reporting cycle",
              information=("the SST risk-free curve", "their own solvency ratio"),
              constraints=("a structural shortage of franc duration, so they hold foreign bonds "
                           "hedged back into francs -- which converts a rates problem into a "
                           "cross-currency basis exposure",),
              instruments=("USDCHF", "EURCHF"),
              counterparties=("cross-currency basis dealers", "foreign sovereign issuers"),
              observables=("the CHF cross-currency basis, persistently negative",
                           "SST disclosures"),
              impact="a persistent structural demand to receive francs in the basis market, "
                     "which is why the CHF basis is negative almost all the time",
              persistence="structural, measured in years",
              falsifier="if the CHF basis shows no widening around Swiss insurer reporting dates "
                        "and no relation to Confederation issuance volume, the scarcity story is "
                        "not the driver and the basis is a dollar-side phenomenon",
              notes="the basis is a TRANSMISSION_TARGET; this actor cannot be traded directly"),
        actor("Swiss pharmaceutical and machinery exporters",
              holds="dollar, euro and yen receivables against a franc cost base",
              forced_to=("hedge on a treasury policy with a rolling horizon",
                         "report in francs, so every appreciation is a reported-earnings event"),
              when="quarterly, and at every board-mandated hedge roll",
              information=("their own order books", "the KOF and SECO surveys"),
              constraints=("a hedging policy that executes regardless of the level; a franc "
                           "appreciation is not a decision for them, it is a cost",),
              instruments=("USDCHF", "EURCHF", "CHFJPY"),
              counterparties=("bank FX desks",),
              observables=("Swiss goods exports",
                           "watch exports by destination, the cleanest monthly luxury read",
                           "the KOF export expectations component"),
              impact="a persistent corporate offer in the franc that partially offsets the "
                     "safe-haven bid and is the reason the franc does not appreciate without limit",
              persistence="quarters",
              falsifier="if USDCHF shows no relation to the monthly watch export surprise once "
                        "the dollar's own move is removed, the corporate channel is not "
                        "measurable at monthly frequency",
              notes="single names are observables here and never hypothesis ground"),
        actor("Swiss gold refiners",
              holds="roughly two-thirds of world gold refining capacity in four plants",
              forced_to=("transform doré and scrap into kilobars on order",
                         "declare every import and export to customs, which publishes it"),
              when="continuous; the customs print is monthly around the 20th",
              information=("their own order book", "Asian premium and discount structures"),
              constraints=("capacity and logistics, and a customs regime that makes the flow "
                           "PUBLIC -- a physical market that is obliged to report itself",),
              instruments=("XAUUSD", "XAUEUR", "XAGUSD", "USDCHF"),
              counterparties=("London bullion banks", "Asian wholesalers", "mints"),
              observables=("BAZG monthly gold imports and exports by counterparty country",
                           "the direction of net flow to and from the UK, which is the London "
                           "vault, and to and from Asia, which is demand"),
              impact="a public read on where physical gold is going that leads the ETF and "
                     "vault statistics; Swiss net exports to Asia are a physical-demand proxy",
              persistence="months; physical flows are slow and directional",
              falsifier="if XAUUSD's subsequent one-month return has no relation to the Swiss "
                        "net export direction across the sample, the physical-flow series is a "
                        "coincident report rather than a leading one",
              notes="the by-country detail was withheld before 2012; the series has a structural "
                    "break there and the pack's history_from says so"),
        actor("Geneva and Zug commodity trading houses",
              holds="dollar-funded commodity inventories against a franc cost base",
              forced_to=("fund inventory in dollars through Swiss banks",
                         "post margin in a currency they do not earn"),
              when="continuous, with stress concentrated in commodity price spikes",
              information=("their own positions", "the commodity forward curves"),
              constraints=("bank credit lines that contract exactly when commodity volatility "
                           "rises, forcing deleveraging into a moving market",),
              instruments=("USDCHF", "USDX", "XAUUSD"),
              counterparties=("Swiss banks", "global commodity producers"),
              observables=("Swiss bank commodity-finance disclosures",
                           "commodity volatility as the stress trigger"),
              impact="a franc funding demand that spikes with commodity volatility, which is one "
                     "of the reasons the franc is not a pure risk-off currency",
              persistence="episodic",
              falsifier="if USDCHF shows no abnormal behaviour in the weeks of the largest "
                        "energy volatility spikes once global risk is controlled for, the "
                        "commodity-finance channel is not visible at this frequency",
              notes="deliberately routed through USDX rather than a commodity leg, because the "
                    "mechanism is about FUNDING and not about the commodity's price"),
        actor("Global safe-haven buyers of the franc",
              holds="risk portfolios that need a hedge with no yield requirement",
              forced_to=("de-risk on a volatility trigger, mechanically, under a VaR limit",),
              when="on shocks; unscheduled by nature",
              information=("realised and implied volatility", "their own risk budgets"),
              constraints=("a VaR or volatility-target mandate converts a price move into a "
                           "forced trade, which is what makes the safe-haven bid mechanical "
                           "rather than sentimental",),
              instruments=("USDCHF", "EURCHF", "CHFJPY", "XAUUSD"),
              counterparties=("Swiss banks", "dealers"),
              observables=("VSTOXX and VIX levels",
                           "the BTP-Bund spread, when the shock is European",
                           "CHFJPY, which separates the two classic haven currencies"),
              impact="the franc's defining behaviour: it appreciates on European risk more "
                     "reliably than on global risk, because its haven role is regional",
              persistence="days to weeks; it decays as the shock resolves",
              falsifier="if EURCHF's response to a one-standard-deviation BTP-Bund widening is "
                        "not larger than its response to an equal-sized move in US high yield, "
                        "the franc's haven role is global rather than European and the pack's "
                        "regional framing is wrong",
              notes="CHFJPY is the pack's sharpest instrument: it nets two haven currencies "
                    "against each other and isolates what is Swiss"),
        actor("Legacy CHF-mortgage borrowers in central Europe",
              holds="franc-denominated mortgage debt against local-currency income",
              forced_to=("service a franc liability from zloty, forint or kuna income",
                         "convert under court-ordered settlements when litigation rules against "
                         "the banks"),
              when="monthly servicing; litigation-driven conversions in waves",
              information=("court rulings, which are public and dated",
                           "the franc's level against their own currency"),
              constraints=("a legal obligation that does not care about the exchange rate, and a "
                           "conversion mechanism set by a court rather than a market",),
              instruments=("CHFPLN", "CHFHUF"),
              counterparties=("central European banks, who hold the other side and hedge it",),
              observables=("Polish and Hungarian court rulings and their dates",
                           "banks' disclosed litigation provisions",
                           "CHFPLN and CHFHUF levels"),
              impact="a dated, legally forced franc flow with no market logic; the Hungarian "
                     "conversion of 2015 was a single-event extinguishment of a whole stock",
              persistence="the Hungarian stock is gone; the Polish one shrinks with each ruling",
              falsifier="if CHFPLN shows no abnormal move around the dates of major Polish "
                        "Supreme Court or CJEU rulings on franc mortgages, the litigation "
                        "channel is priced in advance and there is no event to trade",
              notes="the Polish pack carries the other side of this actor; it is stated in both "
                    "rather than in neither"),
        actor("The Swiss Confederation under the debt brake",
              holds="one of the smallest sovereign debt stocks in the developed world",
              forced_to=("balance the budget over the cycle by constitutional rule",
                         "issue only what that permits, which is very little"),
              when="a published but small auction calendar",
              information=("the federal budget", "tax receipts"),
              constraints=("the Schuldenbremse is constitutional, so Swiss fiscal expansion is "
                           "not a policy option in the way it is elsewhere",),
              instruments=("USDCHF", "EURCHF"),
              counterparties=("Swiss insurers and pension funds, who need the duration",),
              observables=("Confederation issuance volume",
                           "the Confederation bond's spread to the swap curve, which is the "
                           "scarcity premium"),
              impact="a permanent shortage of franc duration that pushes domestic institutions "
                     "into hedged foreign bonds and therefore into the cross-currency basis",
              persistence="structural",
              falsifier="if the CHF cross-currency basis shows no relation to Confederation "
                        "issuance volume across years, the scarcity channel is not the driver",
              notes="an actor whose defining feature is how LITTLE it does"),
        actor("Index funds and market makers in the SMI complex",
              holds="replicating portfolios and option books on an index with three dominant names",
              forced_to=("trade the quarterly review at the effective close",
                         "unwind into an expiry settled on the OPENING auction, which is a "
                         "different hedging problem from a close-settled index"),
              when="third Friday; quarterly reviews",
              information=("Eurex open interest", "the index provider's announcements"),
              constraints=("tracking error and risk limits",),
              instruments=("USDCHF", "EURCHF"),
              counterparties=("Eurex", "structured-product issuers"),
              observables=("Eurex SMI open interest",
                           "the opening auction volume on the third Friday"),
              impact="a Swiss expiry effect that lands at the OPEN rather than midday or the "
                     "close, which is unique among the European indices the desk quotes",
              persistence="the expiry morning",
              falsifier="if USDCHF and EURCHF show no abnormal behaviour in the first hour of a "
                        "third Friday relative to matched Fridays, the Swiss expiry does not "
                        "reach the franc at all and this actor is index-only",
              notes="NO EXECUTABLE SWISS INDEX. This actor can only be tested through the franc, "
                    "which is a weak route and is declared as one."),
        actor("Swiss cantonal and mortgage banks",
              holds="a domestic mortgage book that is heavily SARON-linked",
              forced_to=("pass the SNB policy rate through to SARON mortgages quickly, because "
                         "the contract says so",
                         "fund with deposits whose rate they set discretionarily"),
              when="continuously; the pass-through is contractual and fast",
              information=("SARON", "the SNB policy rate"),
              constraints=("a mortgage market where a large share of contracts reprice with "
                           "SARON makes Swiss monetary transmission FAST by European standards "
                           "-- faster than Germany's fixed-rate stock and comparable to Spain's",),
              instruments=("USDCHF", "EURCHF"),
              counterparties=("Swiss households", "the SNB"),
              observables=("moneyland's published mortgage rate comparison",
                           "SNB mortgage lending statistics"),
              impact="Swiss domestic demand responds to the policy rate faster than the euro "
                     "area's average, which changes the horizon of any macro-to-FX edge",
              persistence="quarters",
              falsifier="if Swiss mortgage rates do not move within a quarter of an SNB policy "
                        "change while German ones take a year, the fast-transmission claim is "
                        "wrong and the horizon conditioning should be dropped",
              notes="the comparison economy is Germany, whose fixed-rate stock transmits slowly; "
                    "that contrast is the testable part"),
        actor("CFTC-reportable franc speculators",
              holds="leveraged CME franc futures, structurally short because the franc funds "
                    "carry trades",
              forced_to=("report weekly", "meet margin in a squeeze"),
              when="positions as of Tuesday, published Friday 15:30 ET",
              information=("public macro", "their own limits"),
              constraints=("a short franc position is a short volatility position: it pays a "
                           "small carry and loses violently in a risk-off, which is the "
                           "mechanism behind every franc squeeze",),
              instruments=("USDCHF", "EURCHF", "CHFJPY"),
              counterparties=("dealers", "commercial hedgers"),
              observables=("the COT net position percentile against a rolling window",
                           "realised volatility as the squeeze trigger"),
              impact="crowding conditions the TAIL, not the mean: a crowded short raises the "
                     "conditional probability of a violent franc appreciation on a shock",
              persistence="weeks to build, days to unwind",
              falsifier="if conditioning the franc's worst weekly returns on the prior COT "
                        "percentile adds nothing to an unconditional tail model, the squeeze "
                        "story is folklore",
              notes="a raw level threshold fires permanently because the position is almost "
                    "always short; only a rolling percentile is defensible"),
        actor("SNB profit distribution to the cantons and the Confederation",
              holds="a distribution agreement that converts central-bank profit into fiscal "
                    "transfers, and a political constituency that watches it",
              forced_to=("distribute according to a published agreement when reserves permit",
                         "publish provisional annual results in early January"),
              when="provisional results in the first days of January; the annual report in March",
              information=("its own balance sheet, marked at year end",
                           "the gold price and the dollar's level, which dominate the P&L"),
              constraints=("a loss year suspends the distribution, which is a political event in "
                           "Switzerland and creates pressure on the balance sheet's size -- a "
                           "political constraint on future intervention capacity",),
              instruments=("USDCHF", "EURCHF", "XAUUSD"),
              counterparties=("the cantons", "the Confederation"),
              observables=("the early-January provisional result",
                           "the franc's and gold's year-end levels, which determine it"),
              impact="an annual, dated Swiss political event whose input is the franc's own "
                     "level -- a rare feedback loop from price to policy constraint",
              persistence="annual",
              falsifier="if the franc shows no abnormal behaviour in the first week of January "
                        "across the sample, the provisional-result announcement is not a market "
                        "event and this actor is political only",
              notes="the early-January announcement lands in the same thin week as Berchtoldstag "
                    "and the year-end turn; separating the three is the whole difficulty"),
    )


def domains() -> tuple[dict[str, Any], ...]:
    """Twelve research domains, each with negative controls."""
    return (
        domain("CH-A", "SNB quarterly assessments and the three-person board",
               objects=("the 09:30 CET announcement", "the 10:00 CET news conference",
                        "the June and December conditional inflation forecasts",
                        "speeches by the three board members between assessments"),
               conditions=("forecast assessment versus short statement",
                           "the policy era (floor, negative, normalising, zero)",
                           "whether the ECB met in the same week"),
               instruments=("USDCHF", "EURCHF", "CHFJPY", "XAUUSD"),
               controls=("the same 09:30-10:30 CET window on a matched non-assessment Thursday",
                         "EURCHF versus USDCHF: an SNB-specific move should be larger in USDCHF, "
                         "because EURCHF is half an ECB instrument",
                         "the ECB's own decision days, to show the effect is not 'a European "
                         "central bank spoke'",
                         "a placebo at 09:30 CET the day before"),
               notes="the smallest policy committee in G10 makes individual speeches unusually "
                     "informative, which is testable and mostly untested"),
        domain("CH-B", "Sight deposits as the weekly intervention observable",
               objects=("the Monday publication of the week ended Friday",
                        "the week-on-week change",
                        "the domestic-bank versus total split"),
               conditions=("reporting week versus ordinary week",
                           "the franc's own move in the week measured",
                           "the intervention era: buying 2015-2021, selling 2022-2023"),
               instruments=("USDCHF", "EURCHF", "CHFJPY"),
               controls=("quarter-end and year-end weeks, where balance-sheet effects dominate "
                         "and the series is least informative",
                         "weeks in which the franc did NOT appreciate, where intervention should "
                         "be absent if the reaction function is what it claims",
                         "the 2022-2023 selling era, where the sign of the whole relationship "
                         "should INVERT -- the strongest available control",
                         "a lag-reversal placebo: the change should not predict the PRIOR week's "
                         "franc move once the current week is removed"),
               notes="the era inversion in 2022-2023 is the best negative control in this pack: "
                     "a mechanism that does not flip sign when the policy flipped is not the "
                     "mechanism claimed"),
        domain("CH-C", "The floor era and the 2015 regime break",
               objects=("the 1.20 minimum exchange rate, 2011-09-06 to 2015-01-15",
                        "the censored return distribution while it held",
                        "the abandonment itself"),
               conditions=("inside versus outside the floor",
                           "distance from 1.20 while it held"),
               instruments=("EURCHF", "USDCHF"),
               controls=("USDCHF during the floor, which was NOT pegged and so shows what the "
                         "franc would have done",
                         "any other European currency in the same window",
                         "a simulated censoring applied to a post-2015 sample, to show what a "
                         "floor does to a statistic mechanically",
                         "a post-2015 placebo at an arbitrary level"),
               notes="NOT TESTABLE ON THIS BOX: FX bars begin 2018-01-02. The era is carried so "
                     "that an external-data study is designed correctly, and every statistic "
                     "quoting the pre-2015 period must be sourced, not computed here."),
        domain("CH-D", "The franc as a REGIONAL rather than global safe haven",
               objects=("the response to European risk versus global risk",
                        "CHFJPY as the haven-versus-haven pair",
                        "the BTP-Bund spread as the European trigger"),
               conditions=("European-origin shock versus US-origin shock",
                           "the volatility regime",
                           "whether the SNB was intervening at the time"),
               instruments=("EURCHF", "USDCHF", "CHFJPY", "XAUUSD"),
               controls=("US high yield as the global-risk control against the BTP-Bund spread",
                         "CHFJPY: if both havens move together the effect is 'haven' and not "
                         "'Swiss'",
                         "XAUUSD as the third haven, which has no central bank",
                         "days matched on realised volatility, so the effect is not a "
                         "volatility-regime artefact"),
               notes="the regional claim is the pack's sharpest falsifiable statement and the "
                     "one most likely to be wrong"),
        domain("CH-E", "Pension and insurer hedging flows",
               objects=("the month-end 16:00 London fix",
                        "the OAK BV hedge ratio as the scaling parameter",
                        "the sign set by the month's foreign equity return"),
               conditions=("month-end versus quarter-end",
                           "the sign and size of the month's foreign equity move",
                           "the hedge ratio's level in the most recent survey"),
               instruments=("USDCHF", "EURCHF", "CHFJPY"),
               controls=("mid-month days matched on weekday",
                         "the T-2 date versus the last calendar day, since spot is T+2",
                         "a month with a near-zero foreign equity return, where the mechanism "
                         "predicts no flow at all",
                         "the euro area's own month-end effect on the same day, which should be "
                         "smaller relative to the economy if the hedge-ratio story is Swiss"),
               notes="the sign is set by the PAST month's return, which makes this one of the "
                     "few genuinely predictable FX flows"),
        domain("CH-F", "SMI expiry and the opening-auction settlement",
               objects=("the third Friday",
                        "the SMI's opening-auction settlement, unique among European indices",
                        "Eurex open interest by strike"),
               conditions=("quarterly versus monthly expiry",
                           "open interest concentration"),
               instruments=("USDCHF", "EURCHF"),
               controls=("GER40's 13:00 CET auction and FRA40's afternoon average on the SAME "
                         "morning: a shared move is European and not Swiss",
                         "a non-expiry third Friday",
                         "the first hour of matched Fridays",
                         "volume as the direct control"),
               notes="no executable Swiss index. This domain can only be tested through the "
                     "franc and is expected to find little; it is carried because a NEGATIVE "
                     "result here is informative about how far an index mechanic reaches into FX"),
        domain("CH-G", "Physical gold: Swiss refining flows",
               objects=("BAZG monthly gold imports and exports by counterparty country",
                        "net flow to and from the United Kingdom (the London vault)",
                        "net flow to and from Asia (physical demand)"),
               conditions=("the direction of the UK net flow, which proxies ETF creation and "
                           "redemption",
                           "the Asian premium regime",
                           "the first print versus the revised one"),
               instruments=("XAUUSD", "XAUEUR", "XAGUSD"),
               controls=("XAGUSD, which shares the monetary driver and not the Asian physical "
                         "one; a move in both is a rates move and not a physical one",
                         "the revised vintage against the first print, to show the effect is not "
                         "an artefact of revisions",
                         "months with no unusual net flow as the null",
                         "the dollar's own move via USDX, since gold in dollars is half a dollar "
                         "trade"),
               notes="the by-country detail starts in 2012; before that the series is a "
                     "different object and must not be spliced"),
        domain("CH-H", "The CHF cross-currency basis and the year-end turn",
               objects=("the persistently negative CHF basis",
                        "its dislocation over reporting dates",
                        "Berchtoldstag as a settlement closure inside the turn week"),
               conditions=("reporting date versus ordinary date",
                           "Confederation issuance volume",
                           "the level of Swiss insurer hedging demand"),
               instruments=("USDCHF", "EURCHF", "CHFSEK", "CHFNOK"),
               controls=("the euro's own year-end turn on the same dates, since a shared effect "
                         "is a dollar-funding effect and not a Swiss one",
                         "quarter-ends other than year-end",
                         "the days immediately outside the spanning window",
                         "years in which Berchtoldstag fell on a weekend, which removes the "
                         "Swiss settlement closure while leaving the reporting date"),
               notes="the Berchtoldstag control is the Swiss-specific separator and it exists "
                     "only because the holiday has no weekend substitution"),
        domain("CH-I", "Swiss macro releases and their clocks",
               objects=("CPI at 08:30 CET", "the KOF barometer at 09:00 CET",
                        "SECO forecasts and the quarterly GDP"),
               conditions=("the surprise against consensus",
                           "proximity to the next SNB assessment",
                           "the KOF vintage, because the barometer is rebuilt annually"),
               instruments=("USDCHF", "EURCHF"),
               controls=("the same clock time on a no-release day",
                         "the euro area's own release on the same morning, where there is one",
                         "the CURRENT KOF vintage against the ORIGINAL one, which measures how "
                         "much of any apparent edge is hindsight",
                         "a placebo release time thirty minutes early"),
               notes="the KOF annual rebuild is the cleanest available demonstration on this "
                     "desk that a revised series is not the series that was tradable"),
        domain("CH-J", "Cantonal calendar asymmetry",
               objects=("Fronleichnam and the Catholic cantons",
                        "Jeune genevois", "Sechselaeuten and Knabenschiessen half-days",
                        "Berchtoldstag against the rest of Europe"),
               conditions=("whether SIX is open while a canton's banks are shut",
                           "which canton, since Zurich and Geneva are the two that matter",
                           "proximity to a long weekend"),
               instruments=("USDCHF", "EURCHF", "CHFSEK", "CHFDKK"),
               controls=("the same weekday in the same month with no cantonal closure",
                         "the day after, where a catch-up should appear if the mechanism is "
                         "delayed flow rather than absent flow",
                         "volume as the direct control",
                         "a non-Swiss pair on the same day"),
               notes="the smallest effects in this pack and the easiest to fool yourself with; "
                     "the volume control is doing most of the work"),
        domain("CH-K", "The legacy central European CHF-mortgage stock",
               objects=("Polish court and CJEU rulings on franc mortgages",
                        "banks' disclosed litigation provisions",
                        "the Hungarian 2015 conversion as a completed natural experiment"),
               conditions=("ruling versus no ruling",
                           "the size of the outstanding stock, which shrinks each year",
                           "whether the ruling was expected"),
               instruments=("CHFPLN", "CHFHUF", "EURCHF"),
               controls=("CHFHUF as the post-conversion control: the Hungarian stock is GONE, so "
                         "a mechanism that still moves CHFHUF on a Polish ruling is regional "
                         "sentiment and not the mortgage channel",
                         "EURPLN on the same day, which separates a zloty move from a franc one",
                         "rulings that went the banks' way",
                         "a placebo date one week before the ruling"),
               notes="the Hungarian conversion gives this domain something almost no domain has: "
                     "a control economy where the mechanism was switched off by law on a date"),
        domain("CH-L", "Imported policy: EURCHF as half an ECB instrument",
               objects=("EURCHF on ECB decision days",
                        "the franc's response to euro-area events it did not cause",
                        "the SNB's own reaction to imported easing"),
               conditions=("ECB decision day versus SNB assessment day",
                           "whether the two fall in the same week",
                           "the direction of the ECB surprise"),
               instruments=("EURCHF", "USDCHF", "CHFJPY"),
               controls=("USDCHF on the same ECB day: a move there is a franc move, a move only "
                         "in EURCHF is a euro move",
                         "EURSEK and EURNOK as the other European crosses, which share the euro "
                         "leg and not the haven one",
                         "SNB days as the mirror control",
                         "weeks in which both central banks met, where the two effects must be "
                         "separated by instrument rather than by date"),
               notes="the single most common error in Swiss analysis is reading EURCHF as an SNB "
                     "series; this domain exists to make that error testable"),
    )


TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    edge("CH-E01",
         source="an unexplained weekly rise in SNB sight deposits outside a reporting week",
         mechanism="franc-selling intervention adds reserves to the banking system, so the "
                   "balance-sheet counterpart is visible before any statement is made",
         targets=("USDCHF", "EURCHF", "CHFJPY"),
         sign="sight deposits up -> franc weaker (USDCHF up, EURCHF up)",
         horizon="the week after publication", lag="published Monday for the prior Friday",
         control="reporting weeks, where the series is dominated by balance-sheet effects; and "
                 "the 2022-2023 selling era, where the sign must invert",
         evidence="MEASURED_ELSEWHERE",
         notes="widely discussed in public research; the desk has not reproduced it"),
    edge("CH-E02",
         source="a one-standard-deviation widening in the BTP-Bund 10y spread",
         mechanism="European sovereign stress drives a regional haven bid that lands in the "
                   "franc before it lands in gold or the yen",
         targets=("EURCHF", "USDCHF", "CHFJPY"),
         sign="spread wider -> EURCHF down, CHFJPY up",
         horizon="same day to a week", lag="minutes",
         control="US high yield on the same day as the global-risk control; XAUUSD as the "
                 "central-bank-free haven",
         evidence="HYPOTHESIS",
         notes="the spread series is external to this desk; without it the edge is UNMEASURED"),
    edge("CH-E03",
         source="the last two business days before a month-end value date, conditioned on the "
                "month's realised foreign equity return",
         mechanism="Swiss pension funds rebalance a high currency hedge ratio into the 16:00 "
                   "London fix, buying francs after a strong foreign month",
         targets=("USDCHF", "EURCHF", "CHFJPY"),
         sign="strong foreign equity month -> franc bid into the fix",
         horizon="intraday", lag="the fix window",
         control="mid-month days matched on weekday; months with a near-zero foreign return",
         evidence="HYPOTHESIS",
         notes="the sign is set by the PAST month, which makes it forecastable rather than "
               "merely explainable"),
    edge("CH-E04",
         source="Swiss net gold exports to Asia in the monthly customs print",
         mechanism="physical demand pulls metal out of the London vault through Swiss refineries, "
                   "and the flow leads the price because physical logistics are slow",
         targets=("XAUUSD", "XAUEUR"),
         sign="large net exports to Asia -> XAUUSD supported over the following month",
         horizon="one to three months", lag="the print lands around the 20th of the next month",
         control="XAGUSD, which shares the monetary driver and not the Asian physical one; and "
                 "the revised vintage against the first print",
         evidence="HYPOTHESIS",
         notes="the by-country detail begins in 2012; do not splice across that break"),
    edge("CH-E05",
         source="an SNB policy assessment surprise at 09:30 CET",
         mechanism="a four-times-a-year rate decision in the smallest policy committee in G10, "
                   "with a wider surprise distribution on forecast quarters",
         targets=("USDCHF", "CHFJPY", "EURCHF"),
         sign="hawkish surprise -> USDCHF down", horizon="intraday to 3 days",
         lag="0 to 30 minutes",
         control="matched non-assessment Thursdays; ECB decision days; USDCHF versus EURCHF to "
                 "separate the Swiss leg from the euro one",
         evidence="HYPOTHESIS",
         notes="expected to be smaller than the euro-area equivalent because the surprise space "
               "is narrower, which is itself the testable claim"),
    edge("CH-E06",
         source="a Polish Supreme Court or CJEU ruling on franc-denominated mortgages",
         mechanism="a court-ordered conversion is a legally forced franc flow with no market "
                   "logic and a publicly dated trigger",
         targets=("CHFPLN", "EURCHF"),
         sign="a pro-borrower ruling -> CHFPLN lower on forced conversion and provisioning",
         horizon="days", lag="the ruling is published at a known time",
         control="CHFHUF, where the stock was extinguished in 2015 and the mechanism cannot "
                 "operate; EURPLN to separate a zloty move from a franc one",
         evidence="HYPOTHESIS",
         notes="the Hungarian control is a genuine switched-off mechanism, which is rare"),
    edge("CH-E07",
         source="the year-end turn spanning 31 December, with Berchtoldstag inside the window",
         mechanism="bank balance-sheet compression plus a Swiss settlement closure on 2 January "
                   "makes the franc's turn structurally longer than the euro's",
         targets=("USDCHF", "EURCHF", "CHFSEK", "CHFNOK"),
         sign="abnormal forward points and spot behaviour across the turn",
         horizon="a few sessions", lag="none",
         control="the euro's own turn on the same dates; years where 2 January fell on a weekend",
         evidence="HYPOTHESIS",
         notes="the weekend-Berchtoldstag years are the Swiss-specific separator"),
    edge("CH-E08",
         source="an ECB decision surprise at 14:15 CET",
         mechanism="the franc imports euro-area policy through EURCHF without any Swiss decision "
                   "having been made",
         targets=("EURCHF", "USDCHF"),
         sign="hawkish ECB -> EURCHF up, with a much smaller USDCHF response",
         horizon="intraday", lag="0 to 30 minutes",
         control="USDCHF as the franc-only leg; EURSEK and EURNOK as the euro-only legs",
         evidence="HYPOTHESIS",
         notes="the RATIO of the EURCHF response to the USDCHF response is the quantity of "
               "interest, not either alone"),
    edge("CH-E09",
         source="the KOF barometer surprise at 09:00 CET, first vintage only",
         mechanism="a survey that leads Swiss activity and therefore the SNB's own forecast",
         targets=("USDCHF", "EURCHF"),
         sign="upside surprise -> franc firmer", horizon="intraday to days",
         lag="none",
         control="the CURRENT vintage against the ORIGINAL one, which measures how much of the "
                 "edge is hindsight; a no-release day at the same clock time",
         evidence="HYPOTHESIS",
         notes="KOF publishes its vintages, so the hindsight control is actually constructible "
               "here, which is unusual"),
    edge("CH-E10",
         source="a Fronleichnam or Jeune genevois cantonal banking closure while SIX trades",
         mechanism="domestic Swiss participation is absent while the price keeps moving, so the "
                   "franc's intraday microstructure changes without any information arriving",
         targets=("USDCHF", "EURCHF", "CHFDKK", "CHFSEK"),
         sign="reduced realised range and wider effective spreads in the Swiss session",
         horizon="intraday", lag="none",
         control="matched weekdays with no cantonal closure; volume as the direct control; a "
                 "non-Swiss pair on the same day",
         evidence="HYPOTHESIS",
         notes="the smallest claim in the pack and the one where a volume control most likely "
               "explains the whole thing -- which is a finding and not a failure"),
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
    era("ch.floor", start="2011-09-06", end="2015-01-15",
        label="the EURCHF 1.20 minimum exchange rate",
        what_changed="EURCHF's downside was CENSORED by a standing commitment; the pair's return "
                     "distribution was truncated by construction rather than by the market",
        invalidates="every statistic estimated on EURCHF across 2015-01-15. A volatility, a "
                    "correlation or a tail estimate pooled over this boundary is an average of a "
                    "bounded market and an unbounded one, and no resampling fixes it.",
        notes="NOT TESTABLE ON THIS BOX: FX bars begin 2018-01-02. Carried so an external study "
              "is designed correctly and so no session quietly pools across it."),
    era("ch.frankenschock", start="2015-01-15", end="2015-01-15",
        label="the abandonment of the floor",
        what_changed="a single unscheduled announcement produced the largest one-day move in the "
                     "pair's history and destroyed several retail brokers",
        invalidates="any gap-risk or maximum-drawdown assumption calibrated without it; it is "
                    "the reference event for franc tail risk and it is not in this box's bars",
        notes="a one-day era on purpose: it is the observation the tail model needs and the one "
              "the sample does not contain"),
    era("ch.negative", start="2015-01-22", end="2022-09-21",
        label="the negative policy rate era (to -0.75%, the deepest in the world)",
        what_changed="the franc became the world's cheapest funding currency, which is why the "
                     "speculative position was structurally short for seven years",
        invalidates="carry studies and COT-level thresholds spanning 2022-09-22; the franc's "
                    "role in a carry basket inverts at that date",
        notes="on this box's bars from 2018-01-02, so roughly the second half of the era is "
              "testable here"),
    era("ch.intervention_buy", start="2015-01-22", end="2021-12-31",
        label="the franc-selling intervention era",
        what_changed="the SNB was a persistent buyer of foreign currency; sight deposits trended "
                     "up and the reaction function was one-sided",
        invalidates="a symmetric intervention model; during this era the SNB responded to "
                    "appreciation and not to depreciation",
        notes="the sign of every sight-deposit edge is defined by this era"),
    era("ch.intervention_sell", start="2022-01-01", end="2023-12-31",
        label="the reversal: the SNB SOLD foreign currency to strengthen the franc",
        what_changed="with imported inflation the objective inverted; a stronger franc became "
                     "policy, and sight deposits fell",
        invalidates="anything estimated on the 2015-2021 sample. THIS IS THE PACK'S BEST "
                    "NEGATIVE CONTROL: a sight-deposit mechanism that does not change sign here "
                    "was never the mechanism claimed.",
        notes="fully inside this box's bars, which makes it the most useful era in the pack"),
    era("ch.cs_ubs", start="2023-03-19", end="2023-06-12",
        label="the Credit Suisse resolution and the UBS takeover",
        what_changed="a systemic Swiss bank ceased to exist over a weekend, and the franc's "
                     "safe-haven behaviour was tested against a shock originating in Switzerland "
                     "itself -- the one case where the haven and the risk were the same country",
        invalidates="a safe-haven model estimated on foreign shocks; this is the counter-example "
                    "and it is a single observation",
        notes="fully on this box's bars"),
    era("ch.normalisation_and_zero", start="2024-03-21", end=None,
        label="the first G10 cut, and the return to a zero policy rate in 2025",
        what_changed="the SNB cut before every other major central bank in March 2024 and "
                     "reached 0.00% in June 2025, so the franc's rate differential narrowed from "
                     "the Swiss side while everyone else's widened",
        invalidates="cross-country policy-differential models calibrated on 2022-2023, where the "
                    "SNB moved with the pack rather than ahead of it",
        notes="OPEN ERA. The 2025 zero-rate date is DECLARED from public knowledge; a session "
              "that can verify it against snb.ch should, and the end is UNMEASURED by definition."),
)

CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    miner("ch_sight_deposit_miner", domain_ids=("CH-B",), kind="mechanism",
          entry="countries.ch.miners:sight_deposit_miner", cadence_s=604800.0,
          notes="NOT WIRED. Weekly by nature. Must run the reporting-week control and the "
                "2022-2023 sign-inversion control before recording any discovery."),
    miner("ch_assessment_clock", domain_ids=("CH-A", "CH-L"), kind="mechanism",
          entry="countries.ch.miners:assessment_clock",
          notes="NOT WIRED. Measures the 09:30 CET window and separates the SNB leg from the ECB "
                "leg by comparing USDCHF with EURCHF."),
    miner("ch_haven_regional", domain_ids=("CH-D",), kind="mechanism",
          entry="countries.ch.miners:haven_regional",
          notes="NOT WIRED. Tests the regional-versus-global haven claim; requires an external "
                "BTP-Bund series and must report UNMEASURED without it."),
    miner("ch_gold_customs", domain_ids=("CH-G",), kind="data",
          entry="countries.ch.miners:gold_customs", cadence_s=86400.0,
          notes="NOT WIRED. Monthly data on a daily poll; must keep the FIRST print and the "
                "revised one as separate series."),
    miner("ch_month_end_hedge", domain_ids=("CH-E",), kind="mechanism",
          entry="countries.ch.miners:month_end_hedge",
          notes="NOT WIRED. Anchors on the T-2 value date, not the last calendar day."),
    miner("ch_cantonal_calendar", domain_ids=("CH-J", "CH-H"), kind="data",
          entry="countries.ch.miners:cantonal_calendar", cadence_s=86400.0, steerable=False,
          notes="NOT WIRED. A fixed cost: derives the SIX and four cantonal calendars from the "
                "rules in this module and emits the asymmetric days."),
    miner("ch_cee_mortgage_litigation", domain_ids=("CH-K",), kind="scout",
          entry="countries.ch.miners:cee_mortgage_litigation",
          notes="NOT WIRED. Watches Polish and CJEU ruling calendars; the Hungarian series is "
                "the switched-off control."),
    miner("ch_kof_vintage", domain_ids=("CH-I",), kind="data",
          entry="countries.ch.miners:kof_vintage", cadence_s=86400.0,
          notes="NOT WIRED. Keeps the original KOF vintages so the hindsight control in CH-I is "
                "actually constructible."),
)


def pack() -> Any:
    """The Swiss country pack: `CountryPack` when the framework has landed, else a dict."""
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
