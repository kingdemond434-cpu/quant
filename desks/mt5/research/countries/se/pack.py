"""THE SWEDEN PACK -- a three-month mortgage reset, a fourth-Friday expiry, and Midsommar.

Thirteen actors with their eleven fields, eleven domains A..K with objects, conditions,
instruments and negative controls, nine datasets with all six point-in-time stamps, ten
transmission edges naming real Fusion symbols, seven policy eras, and a holiday calendar derived
from the rule rather than typed.

THREE THINGS THIS PACK INSISTS ON.

  * THE EXPIRY RULE IS FOURTH FRIDAY WITH A ROLL-BACK, AND THE ROLL-BACK BITES. `omxs30_expiry`
    computes it, and December 2026's fourth Friday is 25 December -- Christmas Day. The function
    rolls back through the closed days to 23 December. A hard-coded "third Friday" or a naive
    "fourth Friday" both produce a date on which nothing happened.
  * SEK IS NOT IN THE COT REPORT. There is no CFTC-reportable krona contract with a usable
    position series. The pack DECLARES that rather than substituting the euro's positioning, and
    every Swedish crowding domain carries UNMEASURED as an available verdict.
  * THE SWEDISH EVENT COUNT HAS A STEP IN IT. The Riksbank moved from five policy meetings a year
    to eight from 2023. An event study that normalises per-meeting across that boundary is
    dividing by two different numbers, and the era row says so.
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta
from typing import Any

from countries import actor, build_pack, dataset, domain, edge, era, miner, source_class

CODE = "SE"
NAME = "Sweden"
REGION_COMMAND = "EUROPE"
CURRENCY = "SEK"

PIT_STAMPS: tuple[str, ...] = ("event_time", "period_time", "publication_time", "available_time",
                               "revision_time", "retrieval_time")

#: The krona complex, plus the euro, dollar and German index legs a Swedish mechanism actually
#: reaches. The last three are TRANSMISSION legs and not Swedish instruments; they are here
#: because a Swedish hypothesis that cannot name an executable target is not a hypothesis.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "EURSEK", "USDSEK", "NOKSEK", "CHFSEK", "GBPSEK", "SEKJPY",
    "GER40", "EURUSD", "USDX",
)

#: What Sweden's economics run through that Fusion does not quote.
TRANSMISSION_TARGETS: tuple[dict[str, str], ...] = (
    {"name": "OMXS30", "venue": "Nasdaq Stockholm",
     "role": "the Swedish equity bloc, and the only index in this department with a FOURTH "
             "Friday expiry",
     "route": "GER40 is the nearest executable proxy and a poor one -- Sweden's index is bank- "
              "and industrial-heavy with a different currency exposure. Swedish equity "
              "mechanisms are routed to the krona or declared UNMEASURED."},
    {"name": "Swedish government bonds (statsobligationer) and the 10y benchmark",
     "venue": "Riksgalden auctions, OTC secondary",
     "role": "the krona's duration anchor; the market is small and foreign-owned, which is why "
             "Swedish yields move on foreign flow rather than domestic demand",
     "route": "EURSEK, USDSEK"},
    {"name": "STIBOR and SWESTR", "venue": "Swedish Financial Benchmark Facility / Riksbank",
     "role": "the term and overnight krona benchmarks; the THREE-MONTH STIBOR is the reference "
             "that resets the Swedish mortgage stock and is therefore the transmission clock",
     "route": "EURSEK, USDSEK -- an input, never a leg"},
    {"name": "Swedish covered bonds (sakerstallda obligationer)",
     "venue": "OTC, the largest krona bond market",
     "role": "the funding instrument behind the mortgage book; the covered-bond spread to "
             "government is the Swedish bank-funding stress observable",
     "route": "EURSEK, GER40"},
    {"name": "Valueguard HOX Swedish house price index", "venue": "Valueguard/KTH",
     "role": "a monthly, hedonic, revision-poor house price index -- the best housing observable "
             "in Europe and directly downstream of the three-month mortgage reset",
     "route": "EURSEK, USDSEK"},
    {"name": "Nord Pool SE1-SE4 power prices", "venue": "Nord Pool",
     "role": "Sweden has four price areas and the north-south spread is a real industrial cost "
             "signal, not a curiosity",
     "route": "GER40 (the shared European power complex); no Swedish executable leg"},
)


def easter_sunday(year: int) -> date:
    """Gregorian Easter. Three Swedish market closures hang off it."""
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


def midsummer_day(year: int) -> date:
    """Midsommardagen: the Saturday falling between 20 and 26 June inclusive."""
    d = date(year, 6, 20)
    while d.weekday() != 5:
        d += timedelta(days=1)
    return d


def midsummer_eve(year: int) -> date:
    """Midsommarafton: the Friday before Midsummer Day, and a full Nasdaq Stockholm closure.

    It is NOT a statutory public holiday in Swedish law and it IS an exchange holiday, which is
    the sort of discrepancy that makes a vendor calendar wrong. 2026-06-19 by derivation.
    """
    return midsummer_day(year) - timedelta(days=1)


def holidays(year: int) -> dict[date, str]:
    """Nasdaq Stockholm trading holidays, derived from the Swedish calendar law plus the
    exchange's own three eves.

    Nationaldagen (6 June) is included ONLY when it falls on a weekday -- there is no weekend
    substitution in Sweden, so in 2026 (a Saturday) it costs the market nothing. That is why the
    count of Swedish trading days is not constant and a per-year normalisation must use this
    function rather than 252.
    """
    e = easter_sunday(year)
    table = {
        date(year, 1, 1): "Nyarsdagen (New Year's Day)",
        date(year, 1, 6): "Trettondedag jul (Epiphany)",
        e - timedelta(days=2): "Langfredagen (Good Friday)",
        e + timedelta(days=1): "Annandag pask (Easter Monday)",
        date(year, 5, 1): "Forsta maj (Labour Day)",
        e + timedelta(days=39): "Kristi himmelsfardsdag (Ascension)",
        midsummer_eve(year): "Midsommarafton (Midsummer Eve -- exchange closed, not a "
                             "statutory public holiday)",
        date(year, 12, 24): "Julafton (Christmas Eve)",
        date(year, 12, 25): "Juldagen (Christmas Day)",
        date(year, 12, 26): "Annandag jul (Boxing Day)",
        date(year, 12, 31): "Nyarsafton (New Year's Eve)",
    }
    national_day = date(year, 6, 6)
    if national_day.weekday() < 5:
        table[national_day] = "Nationaldagen (no weekend substitution in Swedish law)"
    return table


def klamdagar(year: int) -> dict[date, str]:
    """Klamdagar: the squeeze days. A single working day wedged between a holiday and a weekend.

    The exchange is OPEN and the country is not. Swedish volume on a klamdag is a fraction of a
    normal session, which makes them the cleanest available natural experiment on what "thin"
    does to a price -- a liquidity treatment with no information content whatsoever.
    """
    closures = set(holidays(year))
    out: dict[date, str] = {}
    day = date(year, 1, 1)
    while day <= date(year, 12, 31):
        if day.weekday() < 5 and day not in closures:
            before = day - timedelta(days=1)
            after = day + timedelta(days=1)
            shut_before = before.weekday() >= 5 or before in closures
            shut_after = after.weekday() >= 5 or after in closures
            if shut_before and shut_after:
                out[day] = "klamdag (open exchange, absent country)"
        day += timedelta(days=1)
    return out


def _fourth_friday(year: int, month: int) -> date:
    first = date(year, month, 1)
    return date(year, month, 1 + (4 - first.weekday()) % 7 + 21)


def omxs30_expiry(year: int, month: int) -> date:
    """OMXS30 derivatives expiry: the FOURTH Friday, rolled back to the preceding trading day.

    Every other index in this department expires on the third Friday. December 2026's fourth
    Friday is 25 December, so the roll-back is not hypothetical -- it moves the date to the 23rd,
    a Wednesday, two days earlier than a naive rule and nine days later than a third-Friday one.
    """
    day = _fourth_friday(year, month)
    closures = set(holidays(year))
    while day.weekday() >= 5 or day in closures:
        day -= timedelta(days=1)
    return day


def _iso(table: dict[date, str]) -> dict[str, str]:
    return {d.isoformat(): n for d, n in sorted(table.items())}


HOLIDAYS_RULE: dict[str, Any] = {
    "calendar": "Nasdaq Stockholm trading holidays, with the klamdagar beside them",
    "rule": "Closed on Nyarsdagen, Trettondedag jul (6 January), Langfredagen, Annandag pask, "
            "Forsta maj, Kristi himmelsfardsdag, Midsommarafton, Julafton, Juldagen, Annandag "
            "jul and Nyarsafton, plus Nationaldagen (6 June) WHEN IT FALLS ON A WEEKDAY. The "
            "movable three come from the Gregorian computus; Midsommarafton is the Friday before "
            "the Saturday falling 20-26 June. Swedish law has NO weekend substitution, so the "
            "trading-day count varies year to year.",
    "function": "countries.se.pack:holidays",
    "table": {y: _iso(holidays(y)) for y in (2024, 2025, 2026)},
    "klamdag_table": {y: _iso(klamdagar(y)) for y in (2024, 2025, 2026)},
    "asymmetries": (
        "Midsommarafton: Nasdaq Stockholm closed while every other market in this department "
        "trades. EURSEK keeps quoting and the Swedish side of it does not participate.",
        "Trettondedag jul (6 January): Sweden and Finland closed, Germany's southern Laender "
        "closed, Xetra and Euronext open. The first full week of the year is asymmetric across "
        "Europe every single year.",
        "6 June 2026 is a Saturday: Nationaldagen costs no session. 6 June 2024 was a Thursday "
        "and did, which produced a klamdag on Friday the 7th -- an open exchange with almost "
        "nobody in it.",
        "Klamdagar are the point: the exchange is open, the information flow is normal, and the "
        "participation is not. That is a liquidity treatment with no confound.",
    ),
    "status": "DERIVED_FROM_RULE",
    "verified": {"2026-06-19": "Midsommarafton, Nasdaq Stockholm closed",
                 "2026-06-06": "Nationaldagen on a Saturday -- NOT a closure, by derivation"},
}

CENTRAL_BANK: dict[str, Any] = {
    "name": "Sveriges Riksbank",
    "committee": "the Executive Board (direktionen), six members",
    "policy_rates": ("styrrantan (the policy rate; called reporantan before 2022-06)",),
    "operational_framework": "a corridor around the policy rate, with the Riksbank's own "
                             "certificates and standing facilities. The RATE WAS RENAMED in 2022 "
                             "from reporanta to styrranta with a change in the operational "
                             "target -- a series break that is pure definition and catches out "
                             "anyone joining two vendor series by name.",
    "decision_rule": "EIGHT monetary policy meetings a year since 2023 (FIVE before that). The "
                     "decision is published at 09:30 CET on the day AFTER the meeting itself, "
                     "which is why the Riksbank's 'meeting date' and 'announcement date' differ "
                     "in most vendor calendars and only one of them is tradable.",
    "announcement_local": "09:30 CET/CEST",
    "announcement_utc": {"winter_cet": "08:30Z", "summer_cest": "07:30Z"},
    "press_conference_local": "11:00 CET/CEST (declared; verify against riksbank.se)",
    "dst_note": "Sweden observes CET/CEST on the same switch weekends as the euro area, so the "
                "Stockholm-Frankfurt offset is zero all year and the Stockholm-London offset a "
                "constant hour. The 09:30 CET announcement lands BEFORE the London open in "
                "winter terms and squarely inside the European morning in both.",
    "time_change_note": "no known announcement-clock break since 2018 on this desk's bars. The "
                        "CADENCE break (five meetings to eight, from 2023) is the one that "
                        "matters and it is carried as an era.",
    "reports": "a Monetary Policy Report accompanies the decision at the report meetings and "
               "carries the rate path (rantebanan) -- the Riksbank publishes its own forecast "
               "path, which few central banks do, so the SURPRISE can be measured against the "
               "bank's own previous path rather than against a survey",
    "decisions": {
        "2024": {"dates": ("2024-02-01", "2024-03-27", "2024-05-08", "2024-06-27", "2024-08-20",
                           "2024-09-25", "2024-11-07", "2024-12-19"),
                 "confidence": "DECLARED from public knowledge, eight meetings under the "
                               "post-2023 cadence. Verify against riksbank.se before use."},
        "2025": {"dates": ("2025-01-29", "2025-03-20", "2025-05-08", "2025-06-18", "2025-08-20",
                           "2025-09-23", "2025-11-05", "2025-12-16"),
                 "confidence": "DECLARED, UNVERIFIED"},
        "2026": {"dates": (),
                 "confidence": "UNMEASURED. The desk does not hold the 2026 Riksbank calendar "
                               "and will not invent one: an event window on a guessed date is "
                               "not a weaker study, it is a study of a non-event. Read "
                               "riksbank.se/en/monetary-policy/monetary-policy-meetings and fill "
                               "this in, or condition on the rule below."},
    },
    "rule_if_dates_unknown": "eight meetings a year, roughly every six to seven weeks, with the "
                             "decision published 09:30 CET the day after the meeting; report "
                             "meetings cluster in late March, June, September and November.",
    "source": "https://www.riksbank.se/en-gb/monetary-policy/",
}

FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "Riksbank daily reference exchange rates",
     "administrator": "Sveriges Riksbank",
     "local_time": "struck around 16:00 CET/CEST, published shortly after",
     "utc": {"winter": "15:00Z", "summer": "14:00Z"},
     "dst_note": "CET/CEST on euro-area switch weekends. The rate is published on SWEDISH "
                 "banking days, so it has holes on Midsommarafton and 6 January that a euro or "
                 "dollar series does not -- a daily join must be an outer join or those days "
                 "vanish silently.",
     "window": "a snapshot, not a window average. Confidence: the 16:00 CET timing is declared "
               "from public knowledge; verify against riksbank.se before using it as an event "
               "time at tick resolution.",
     "what_it_prices": "the krona for statistical and accounting purposes",
     "why_it_matters": "the domestic accounting reference, but NOT the one index funds use -- "
                       "that is the 16:00 London WMR fix, one hour later in winter terms. Two "
                       "different forced participants, one hour apart, and only the London one "
                       "carries index flow."},
    {"name": "WM/Refinitiv 16:00 London closing spot rate",
     "administrator": "LSEG (WM/Refinitiv)", "local_time": "16:00 London",
     "utc": {"winter": "16:00Z", "summer": "15:00Z"},
     "dst_note": "GMT/BST on the same switch weekends as CET/CEST; the Stockholm-London offset "
                 "is a constant hour all year, so the Riksbank fix always precedes the WMR fix "
                 "by exactly sixty minutes.",
     "window": "15:57:30-16:02:30 London",
     "what_it_prices": "the benchmark global index funds convert krona exposure at",
     "why_it_matters": "Sweden's weight in global equity indices is larger than its economy's "
                       "share, so month-end index hedging is a first-order krona flow"},
    {"name": "STIBOR",
     "administrator": "Swedish Financial Benchmark Facility",
     "local_time": "published around 11:00 CET/CEST",
     "utc": {"winter": "10:00Z", "summer": "09:00Z"},
     "dst_note": "CET/CEST, Swedish banking days only. Confidence: the 11:00 CET publication is "
                 "declared; verify against the SFBF methodology.",
     "window": "panel submissions under a hybrid waterfall methodology",
     "what_it_prices": "term krona funding. THREE-MONTH STIBOR is the reference that resets the "
                       "floating Swedish mortgage stock and is therefore the transmission clock "
                       "of Swedish monetary policy.",
     "why_it_matters": "the fastest policy-to-household channel in Europe runs through this "
                       "fixing; its spread to the policy rate is the bank-funding stress read"},
    {"name": "SWESTR",
     "administrator": "Sveriges Riksbank",
     "local_time": "published 09:00 CET/CEST on the following Swedish banking day",
     "utc": {"winter": "08:00Z", "summer": "07:00Z"},
     "dst_note": "CET/CEST. Published T+1 on banking days, so the gap across Midsommar and the "
                 "Christmas eves is longer than a weekend and shows as a spurious jump in any "
                 "naive daily-difference series.",
     "window": "volume-weighted trimmed mean of the prior day's overnight transactions",
     "what_it_prices": "actual overnight krona borrowing",
     "why_it_matters": "the only Swedish rate that is transaction-based rather than submitted; "
                       "SWESTR minus the policy rate is the clean liquidity observable"},
)

SETTLEMENT_CONVENTIONS: dict[str, Any] = {
    "fx_spot": "T+2 for EURSEK and USDSEK; the value date must be good in both currencies, so a "
               "Swedish-only closure (Midsommarafton, 6 January) pushes the krona leg while the "
               "euro leg is unaffected",
    "fx_value_date_note": "Midsommarafton falls on a Friday, so a Wednesday trade in that week "
                          "values on the following Monday rather than the Friday -- a weekend "
                          "of extra carry priced into a single tick of the swap points, every "
                          "June, on a date derivable from the rule in this module",
    "cls": "SEK settles in CLS, so the krona leg of a G10 pair carries no Herstatt risk; the "
           "CHFSEK and GBPSEK legs are both CLS-eligible on both sides",
    "cash_equity": "T+2 on Nasdaq Stockholm; Sweden follows the EU timetable for the move to "
                   "T+1 on 11 October 2027 (declared -- verify against Nasdaq and ESMA)",
    "bonds": "T+2 for Swedish government bonds through Euroclear Sweden",
    "derivatives": "OMXS30 futures and options are cash-settled against the expiration-day index "
                   "average; the settlement date follows the FOURTH-Friday rule in "
                   "`omxs30_expiry`, not the third",
    "month_end": "AP funds and insurers rebalance currency hedges at month-end into the 16:00 "
                 "London fix, two business days before the value date",
}

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Nasdaq Stockholm", "mic": "XSTO", "tz": "Europe/Stockholm",
     "symbols": (),
     "session_local": "09:00-17:25 CET continuous, closing auction 17:25-17:30",
     "expiry_rule": "THE FOURTH FRIDAY of the expiry month, rolled back to the preceding trading "
                    "day when that Friday is a closure. `omxs30_expiry` computes it. This is the "
                    "only fourth-Friday expiry in this whole department.",
     "settlement_price_rule": "OMXS30 derivatives settle against an average of index values "
                              "computed across the expiration DAY rather than a single auction "
                              "or a short window. A whole-day averaging window is a different "
                              "pinning problem from the DAX's 13:00 CET auction: there is no "
                              "single instant to defend, so the incentive is spread across the "
                              "session. Confidence: declared; verify against the Nasdaq Nordic "
                              "contract specification.",
     "witching": "the quarterly Mar/Jun/Sep/Dec cycle, still on the fourth Friday",
     "notes": "NO EXECUTABLE SYMBOL. OMXS30 is absent from the broker universe; Swedish expiry "
              "effects must be routed into the krona or declared UNMEASURED."},
)

POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "NO CFTC POSITIONING SERIES FOR THE KRONA -- declared absence",
     "covers": "nothing. SEK has no CFTC-reportable futures contract with a usable position "
               "series, unlike EUR, GBP, CHF, JPY, AUD, CAD, NZD and MXN.",
     "published": "never", "lag_days": 0.0, "licence": "n/a", "root": "n/a",
     "note": "THIS IS THE DECLARED GAP AND IT IS NOT AN OVERSIGHT. Every Swedish crowding "
             "hypothesis on this desk is UNMEASURED on positioning (L1.28a). The available "
             "substitutes are all bad in a named way: the euro's COT is not the krona's, "
             "Riksbank foreign-ownership statistics are monthly and lagged, and BIS turnover is "
             "three-yearly. A pack that quietly used EUR positioning for SEK would be inventing "
             "the measurement it does not have."},
    {"name": "Riksbank statistics on foreign ownership of Swedish government bonds",
     "covers": "the share of the krona bond market held abroad",
     "published": "monthly, with a lag", "lag_days": 30.0, "licence": "public",
     "root": "https://www.riksbank.se/en-gb/statistics/",
     "note": "the closest thing Sweden has to a positioning series. Monthly and lagged, so it is "
             "an ACTOR observable and never a timing one; its level explains why Swedish yields "
             "move on foreign risk appetite rather than domestic demand."},
    {"name": "Riksgalden auction results and bid-to-cover",
     "covers": "primary demand for Swedish government paper",
     "published": "within minutes of each auction", "lag_days": 0.0, "licence": "public",
     "root": "https://www.riksgalden.se/",
     "note": "a dated, high-frequency demand read with a published calendar -- the only "
             "Swedish flow observable that is both timely and precise"},
    {"name": "Nasdaq Nordic open interest for the OMXS30 complex",
     "covers": "Swedish index derivatives positioning",
     "published": "daily", "lag_days": 1.0,
     "licence": "public page, restricted redistribution",
     "root": "https://www.nasdaqomxnordic.com/",
     "note": "useful for the expiry domain and NOT executable: the desk has no OMXS30 leg, so "
             "this can condition a krona hypothesis but can never be traded directly"},
)

NATIVE_LANGUAGES: tuple[str, ...] = ("sv", "en")

#: Swedish market vocabulary. `klamdag`, `rantebanan` and `amorteringskrav` have no English
#: equivalent that a search engine will match, which is precisely why they are here.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "sv_policy": ("Riksbanken", "styrränta", "reporänta", "räntebesked",
                  "penningpolitiskt möte", "penningpolitisk rapport", "räntebanan",
                  "direktionen", "protokoll", "reservation", "inflationsmålet"),
    "sv_rates": ("STIBOR", "SWESTR", "tremånaders STIBOR", "statsobligation",
                 "säkerställda obligationer", "Riksgälden", "auktion", "emission",
                 "täckningsgrad", "ränteskillnad"),
    "sv_fx": ("kronan", "kronförsvagning", "kronförstärkning", "valutasäkring",
              "valutareserven", "säkringsgrad", "terminssäkring", "kronkursindex"),
    "sv_market": ("Nasdaq Stockholm", "OMXS30", "slutdag", "fjärde fredagen",
                  "stängningsauktion", "börsdag", "klämdag", "midsommarafton",
                  "utdelningsdag", "handelsstopp"),
    "sv_macro": ("KPIF", "KPI", "KPIF exklusive energi", "SCB", "Konjunkturinstitutet",
                 "barometerindikatorn", "arbetslöshet", "hushållens skuldsättning",
                 "bostadspriser", "Valueguard", "HOX-index"),
    "sv_housing": ("bolån", "rörlig ränta", "bunden ränta", "amorteringskrav",
                   "skuldkvotstak", "Finansinspektionen", "bostadsrätt", "villapriser",
                   "bolånetak", "räntenetto"),
    "en_desk": ("the fourth Friday", "the three-month reset", "the krona smile", "high beta",
                "the summer liquidity hole", "no COT for SEK"),
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
    _src("se.official.riksbank", "Riksbank decisions, minutes, the rate path and its statistics",
         layer="official",
         roots=("https://www.riksbank.se/en-gb/monetary-policy/",
                "https://www.riksbank.se/en-gb/statistics/",
                "https://www.riksbank.se/sv/penningpolitik/penningpolitiska-mooten/"),
         languages=("sv", "en"), licence="public, attribution",
         access_label="OPEN_DATA", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         weight=1.0,
         queries=("penningpolitiskt möte räntebesked datum kalender",
                  "penningpolitisk rapport räntebanan prognos",
                  "protokoll reservation direktionen styrränta",
                  "valutareserven säkring beslut pressmeddelande"),
         notes="the Riksbank publishes its OWN rate path, so a policy surprise is a revision to a "
               "public prior rather than a deviation from a survey -- cleaner than most countries "
               "allow. The MINUTES name individual dissenters and are a second, dated event."),
    _src("se.official.state", "Riksgälden, SCB, Finansinspektionen and Konjunkturinstitutet",
         layer="official",
         roots=("https://www.riksgalden.se/en/", "https://www.scb.se/en/",
                "https://www.fi.se/en/", "https://www.konj.se/"),
         languages=("sv", "en"), licence="public, attribution",
         access_label="OPEN_DATA", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         weight=1.0,
         queries=("auktionsvillkor statsobligation emissionsvolym Riksgälden",
                  "KPIF utfall månad SCB publicering klockan åtta",
                  "amorteringskrav förslag remiss Finansinspektionen",
                  "barometerindikatorn Konjunkturinstitutet månadsutfall"),
         notes="Finansinspektionen's amorteringskrav is a DATED regulatory lever on the same "
               "household channel the Riksbank works on, and the two authorities have pulled in "
               "opposite directions -- which no single policy-rate series captures."),
    _src("se.institutional.venue_and_bodies",
         "Nasdaq Stockholm specifications and the Swedish industry associations",
         layer="institutional",
         roots=("https://www.nasdaqomxnordic.com/",
                "https://www.nasdaq.com/solutions/nordic-derivatives",
                "https://www.swedishbankers.se/", "https://www.fondbolagen.se/",
                "https://www.svenskforsakring.se/"),
         languages=("sv", "en"), licence="public page, restricted redistribution",
         access_label="PUBLIC_WITH_TERMS", credibility="AUTHORITATIVE",
         predictive_state="UNTESTED", weight=1.0,
         queries=("OMXS30 slutdag fjärde fredagen kontraktsspecifikation",
                  "slutavräkningspris genomsnitt index slutdagen",
                  "Fondbolagens förening nettosparande månadsstatistik",
                  "Bankföreningen bolånemarknaden räntebindningstid statistik"),
         notes="the ONLY authority on the FOURTH-Friday rule and the expiration-day averaging "
               "window, both of which this pack carries as declared. Fondbolagens förening "
               "publishes monthly net fund flows -- the closest Swedish thing to a public "
               "retail flow series."),
    _src("se.academic.research", "Riksbank working papers and the Swedish research institutes",
         layer="academic",
         roots=("https://www.riksbank.se/en-gb/press-and-published/publications/"
                "working-paper-series/",
                "https://www.hhs.se/en/research/", "https://www.ifn.se/en/", "https://www.sns.se/",
                "https://www.suerf.org/"),
         languages=("sv", "en"), licence="public, attribution",
         access_label="PUBLIC", credibility="RELIABLE", predictive_state="UNTESTED", weight=0.9,
         queries=("Riksbank working paper household debt transmission mortgage",
                  "hushållens skuldsättning räntekänslighet studie",
                  "amorteringskrav effekt bostadspriser utvärdering",
                  "kronans växelkurs riskpremie forskning"),
         notes="the Riksbank's own papers on household debt and transmission are the best public "
               "description of the three-month reset mechanism this pack is built around, and "
               "the FI evaluations of the amorteringskrav are the only serious impact studies of "
               "the regulatory lever."),
    _src("se.practitioner.bank_research",
         "Nordic bank strategy notes and the professional community",
         layer="practitioner",
         roots=("https://research.nordea.com/", "https://seb.se/om-seb/analys-och-rapporter",
                "https://www.handelsbanken.se/sv/om-oss/makro-och-marknad",
                "https://swedbank.com/investor-relations/macro-research.html",
                "https://www.cfasweden.se/"),
         languages=("sv", "en"), licence="mixed: public summaries, licensed full notes",
         access_label="ACCESS_UNCLEAR", credibility="RELIABLE", predictive_state="UNTESTED",
         weight=0.6,
         queries=("räntebesked kommentar analytiker Riksbanken förväntan",
                  "kronprognos EURSEK analys bank",
                  "boräntor prognos rörlig bunden kommentar",
                  "makroanalys Sverige BNP prognos revidering"),
         notes="the four Swedish banks publish public macro commentary and licensed full notes; "
               "ACCESS_UNCLEAR is the honest label for the boundary between them. Their "
               "published BORÄNTEPROGNOS (mortgage rate forecast) is the retail-facing "
               "expectation series and has no official equivalent."),
    _src("se.retail_ecology.communities",
         "Swedish retail investor forums and social trading communities",
         layer="retail_ecology",
         roots=("https://www.avanza.se/placera/forum.html", "https://www.shareville.se/",
                "https://www.flashback.org/f169", "https://www.reddit.com/r/ISKbets/"),
         languages=("sv",), licence="public forum, quote-and-cite only",
         access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE", predictive_state="UNTESTED",
         weight=0.25, machine_use_allowed=True,
         queries=("rörlig eller bunden bolåneränta diskussion 2026",
                  "kronan rasar varför forum",
                  "slutdag OMXS30 fjärde fredagen spekulation",
                  "klämdag börsen tunn handel"),
         notes="machine_use_allowed=True: Avanza's and Flashback's terms forbid automated "
               "extraction, so both are REGISTERED and never scraped. Kept at weight 0.25 rather "
               "than dropped: the rörlig-versus-bunden debate is a live read on where Swedish "
               "households think rates are going, which is the household side of domain SE-B."),
    _src("se.app_ecosystem.platforms", "Swedish broker platforms, robo-advisers and their data",
         layer="app_ecosystem",
         roots=("https://www.avanza.se/", "https://www.nordnet.se/",
                "https://www.nordnet.se/se/tjanster/api", "https://www.savr.com/",
                "https://lysa.se/", "https://www.tradingview.com/symbols/OMXSTO-OMXS30/"),
         languages=("sv", "en"), licence="per-platform terms",
         access_label="PUBLIC_WITH_TERMS", credibility="UNKNOWN",
         predictive_state="NARRATIVE_FEATURE", weight=0.4,
         queries=("Avanza mest ägda aktier statistik",
                  "Nordnet Shareville mest köpta idag",
                  "Nordnet API dokumentation orderbok"),
         notes="Sweden has the deepest retail platform ecosystem in Europe relative to its size, "
               "and Avanza's and Nordnet's most-owned lists are public. They measure ATTENTION "
               "and are labelled NARRATIVE_FEATURE; the Nordnet API documentation is here "
               "because a public order-book API is itself a structural fact about the market."),
    _src("se.media.business_press", "Swedish business press",
         layer="media",
         roots=("https://www.di.se/", "https://www.svd.se/naringsliv",
                "https://www.affarsvarlden.se/", "https://www.realtid.se/",
                "https://www.placera.se/"),
         languages=("sv",), licence="paywalled; terms forbid bulk extraction",
         access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
         predictive_state="NARRATIVE_FEATURE", weight=0.5, machine_use_allowed=True,
         queries=("Dagens industri räntebesked Riksbanken analys",
                  "kronan försvagas orsak analys",
                  "bostadspriser Valueguard HOX månadsstatistik nyhet"),
         notes="machine_use_allowed=True: Dagens industri and SvD both paywall with terms "
               "forbidding bulk extraction. Registered, never scraped. Placera is the one with a "
               "largely open surface and it is also the one closest to the retail layer, which "
               "is why its credibility label is inherited from the media layer and its content "
               "is read as narrative."),
    _src("se.archive.historical", "Swedish historical monetary and price statistics",
         layer="archive",
         roots=("https://www.riksbank.se/en-gb/statistics/historical-monetary-statistics-of-"
                "sweden/",
                "https://www.scb.se/hitta-statistik/sverige-i-siffror/",
                "https://tidningar.kb.se/", "https://web.archive.org/"),
         languages=("sv", "en"), licence="public archive",
         access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         weight=0.8,
         queries=("Historical Monetary Statistics of Sweden riksbanken 1668",
                  "reporänta historik negativ ränta 2015 arkiv",
                  "tidningar.kb.se börsen kronan historisk artikel"),
         notes="the Riksbank's Historical Monetary Statistics runs back to 1668 -- the longest "
               "continuous central-bank series in the world and free. This layer is load-bearing "
               "for the negative-rate era (2015-2019), which is OUTSIDE this box's bars, and for "
               "the pre-2023 five-meeting cadence that era se.eight_meetings depends on."),
    _src("se.physical_economy.power_and_industry",
         "Nordic power, grid, ore and forest-product physical data",
         layer="physical_economy",
         roots=("https://www.nordpoolgroup.com/", "https://www.svk.se/",
                "https://www.portofgothenburg.com/about-the-port/statistics/",
                "https://www.skogsindustrierna.se/", "https://www.lkab.com/en/"),
         languages=("sv", "en"), licence="public / registration",
         access_label="OPEN_DATA", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         weight=0.9,
         queries=("elområde SE1 SE2 SE3 SE4 elpris skillnad",
                  "Svenska kraftnät överföringskapacitet snitt begränsning",
                  "Göteborgs hamn containerstatistik kvartal",
                  "massa och papper produktion export statistik"),
         notes="Sweden has FOUR electricity price areas inside one country and the north-south "
               "spread is a real industrial cost signal, not a curiosity -- a domestic cost "
               "dispersion with no analogue in Germany or France. Free, hourly, and upstream of "
               "the industrial exporters in domain SE-C."),
    _src("se.source_graph.citation_and_link", "Citation and link graphs over the Swedish corpus",
         layer="source_graph",
         roots=("https://ideas.repec.org/s/hhs/rbnkwp.html", "https://openalex.org/",
                "https://swepub.kb.se/", "https://github.com/search?q=STIBOR+OR+SWESTR"),
         languages=("sv", "en"), licence="open data",
         access_label="OPEN_DATA", credibility="RELIABLE", predictive_state="UNTESTED",
         weight=0.5,
         queries=("RePEc cited by Riksbank working paper household debt",
                  "SwePub avhandling bolån räntekänslighet",
                  "github swedish holiday calendar midsommarafton python"),
         notes="SwePub is the Swedish national research bibliography and covers theses, which is "
               "where Swedish housing microdata work actually lives. The GitHub query is here "
               "for a concrete reason: the Swedish trading calendar with Midsommarafton and the "
               "klämdagar is exactly the sort of thing somebody has already implemented."),
)

#: All ten layers are populated for Sweden, so this table is empty BY MEASUREMENT.
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
    _ds("Riksbank policy decisions and the published rate path",
        source="Riksbank press releases and the Monetary Policy Report",
        coverage="every Swedish policy decision", frequency="8 per year since 2023, 5 before",
        publication_lag_days=0.0,
        revisions="the decision is never revised; the RATE PATH is re-published at each report "
                  "meeting and the change in the path is the surprise, so the two vintages must "
                  "both be kept",
        licence="public, attribution", history_from="1994", pit_feasible=True,
        assets=("EURSEK", "USDSEK", "NOKSEK"),
        mechanism_families=("policy_surprise", "path_revision", "event_drift"),
        how_to_fetch="riksbank.se press release and report pages, one per meeting",
        pit={"event_time": "09:30 CET on the day AFTER the meeting -- the meeting date in most "
                           "vendor calendars is NOT the tradable date",
             "period_time": "the forecast horizon the path covers",
             "publication_time": "09:30 CET",
             "available_time": "09:30 CET",
             "revision_time": "never for the decision; the path is superseded at the next report",
             "retrieval_time": "crawler stamp"}),
    _ds("Swedish CPIF and CPI",
        source="Statistics Sweden (SCB)", coverage="Sweden", frequency="monthly",
        publication_lag_days=13.0,
        revisions="CPIF is not routinely revised; the weights are updated annually in January "
                  "and that rewrites the recent history of the index's composition",
        licence="public, attribution", history_from="1987 (CPIF from 1995)", pit_feasible=True,
        assets=("EURSEK", "USDSEK"),
        mechanism_families=("data_surprise", "policy_expectation"),
        how_to_fetch="scb.se statistical database, monthly release at 08:00 CET",
        pit={"event_time": "08:00 CET on the release day",
             "period_time": "the reference month",
             "publication_time": "08:00 CET, around the middle of the following month",
             "available_time": "08:00 CET -- one hour before the European equity open, so the "
                               "krona reaction is a pure FX reaction with no index confound",
             "revision_time": "annual reweighting each January",
             "retrieval_time": "crawler stamp"}),
    _ds("Valueguard HOX Swedish house price index",
        source="Valueguard / KTH", coverage="Sweden, by region and property type",
        frequency="monthly", publication_lag_days=20.0,
        revisions="small and infrequent; the hedonic method makes it more stable than a "
                  "transaction median",
        licence="public headline, licensed detail", history_from="2005", pit_feasible=True,
        assets=("EURSEK", "USDSEK"),
        mechanism_families=("housing_channel", "policy_transmission", "regime_condition"),
        how_to_fetch="valueguard.se monthly release",
        pit={"event_time": "the month the transactions occurred in",
             "period_time": "the calendar month",
             "publication_time": "around the 20th of the following month",
             "available_time": "same",
             "revision_time": "occasional minor restatement",
             "retrieval_time": "crawler stamp"}),
    _ds("Three-month STIBOR",
        source="Swedish Financial Benchmark Facility",
        coverage="term krona funding", frequency="daily on Swedish banking days",
        publication_lag_days=0.0,
        revisions="not revised; the methodology CHANGED to a hybrid waterfall, which is a series "
                  "break that no vendor flags",
        licence="licensed for redistribution", history_from="1987", pit_feasible=True,
        assets=("EURSEK", "USDSEK"),
        mechanism_families=("funding", "policy_transmission", "mortgage_reset"),
        how_to_fetch="SFBF daily publication; the Riksbank republishes a history",
        pit={"event_time": "the fixing day",
             "period_time": "the three-month term the rate prices",
             "publication_time": "around 11:00 CET",
             "available_time": "same",
             "revision_time": "never; but the methodology break is a discontinuity",
             "retrieval_time": "crawler stamp"}),
    _ds("Riksgalden auction calendar and results",
        source="Swedish National Debt Office", coverage="Swedish government bonds and bills",
        frequency="weekly auctions on a published calendar", publication_lag_days=0.0,
        revisions="the calendar is published ahead; auction VOLUMES are announced closer in and "
                  "are the tradable announcement",
        licence="public", history_from="2000", pit_feasible=True,
        assets=("EURSEK", "USDSEK"),
        mechanism_families=("supply_concession", "forced_flow"),
        how_to_fetch="riksgalden.se auction pages",
        pit={"event_time": "the auction deadline",
             "period_time": "the settlement date, T+2",
             "publication_time": "results within minutes",
             "available_time": "same",
             "revision_time": "never",
             "retrieval_time": "crawler stamp"}),
    _ds("Riksbank foreign exchange reserves and the 2023 hedging programme",
        source="Riksbank", coverage="the reserve stock and its currency composition",
        frequency="monthly, with event-driven announcements", publication_lag_days=15.0,
        revisions="valuation restatements",
        licence="public", history_from="2000", pit_feasible=True,
        assets=("EURSEK", "USDSEK", "EURUSD"),
        mechanism_families=("central_bank_flow", "announced_flow"),
        how_to_fetch="riksbank.se statistics and the 2023 hedging press releases",
        pit={"event_time": "the ANNOUNCEMENT date of the hedging programme, which is the "
                           "tradable event -- the transactions themselves were spread over "
                           "months and were never individually dated",
             "period_time": "the month the reserve stock refers to",
             "publication_time": "monthly statistics with about a fortnight's lag",
             "available_time": "same",
             "revision_time": "valuation restatements",
             "retrieval_time": "crawler stamp"}),
    _ds("Konjunkturinstitutet barometer",
        source="National Institute of Economic Research", coverage="Sweden",
        frequency="monthly", publication_lag_days=0.0,
        revisions="seasonal factors are re-estimated annually and rewrite the history",
        licence="public", history_from="1996", pit_feasible=True,
        assets=("EURSEK", "GER40"),
        mechanism_families=("survey_surprise", "regime_condition"),
        how_to_fetch="konj.se monthly release, 09:00 CET",
        pit={"event_time": "09:00 CET release",
             "period_time": "the survey month",
             "publication_time": "09:00 CET near month end",
             "available_time": "same",
             "revision_time": "annual seasonal re-estimation",
             "retrieval_time": "crawler stamp"}),
    _ds("Finansinspektionen mortgage market report and the amorteringskrav",
        source="Swedish Financial Supervisory Authority",
        coverage="new mortgage lending, loan-to-value and loan-to-income distributions",
        frequency="annual report, event-driven rule changes", publication_lag_days=90.0,
        revisions="none; the sample changes year to year",
        licence="public", history_from="2011", pit_feasible=True,
        assets=("EURSEK", "USDSEK"),
        mechanism_families=("regulatory_lever", "housing_channel", "forced_flow"),
        how_to_fetch="fi.se annual Den svenska bolanemarknaden report and rule announcements",
        pit={"event_time": "the ANNOUNCEMENT of a rule change, which is dated and tradable",
             "period_time": "the lending year the report covers",
             "publication_time": "spring, for the prior year",
             "available_time": "same",
             "revision_time": "never",
             "retrieval_time": "crawler stamp"}),
    _ds("Nasdaq Stockholm trading calendar and OMXS30 expiry dates",
        source="Nasdaq Nordic", coverage="Swedish trading days and derivative expiries",
        frequency="annual calendar", publication_lag_days=0.0,
        revisions="published a year ahead and rarely changed",
        licence="public page", history_from="2000", pit_feasible=True,
        assets=("EURSEK", "GER40"),
        mechanism_families=("calendar", "expiry", "liquidity"),
        how_to_fetch="nasdaqomxnordic.com calendar page; this module derives the same dates from "
                     "the rule in `holidays` and `omxs30_expiry` and the two must agree",
        pit={"event_time": "the trading day itself",
             "period_time": "the calendar year",
             "publication_time": "the preceding year",
             "available_time": "the preceding year -- a rare dataset that is knowable in advance",
             "revision_time": "occasional amendment",
             "retrieval_time": "crawler stamp"}),
)


def actors() -> tuple[dict[str, Any], ...]:
    """Thirteen Swedish participants whose constraints produce dated or measurable flow."""
    return (
        actor("Riksbank Executive Board",
              holds="the krona's policy rate and a balance sheet built during the QE years",
              forced_to=("decide eight times a year on a published calendar",
                         "publish its OWN rate path, which almost no other central bank does",
                         "publish minutes naming individual dissenters"),
              when="eight meetings a year since 2023, decision at 09:30 CET the day AFTER the "
                   "meeting",
              information=("CPIF from SCB at 08:00 CET",
                           "the Konjunkturinstitutet barometer",
                           "the krona's own level, which the board comments on explicitly"),
              constraints=("an inflation target with a currency that transmits import prices "
                           "fast, so a weak krona is itself an inflation problem",
                           "a household sector with the highest debt-to-income in Europe, which "
                           "makes every hike a fiscal event for the median voter"),
              instruments=("EURSEK", "USDSEK", "NOKSEK"),
              counterparties=("Swedish banks", "the mortgage market through STIBOR"),
              observables=("the 09:30 CET decision",
                           "the published rate path and its revision",
                           "the minutes, roughly two weeks later"),
              impact="the rate path revision is a cleaner surprise measure than a survey, because "
                     "the bank's own prior forecast is public and dated",
              persistence="the path revision persists for weeks",
              falsifier="if EURSEK's move on decision days regressed on the change in the "
                        "published two-year path has a coefficient indistinguishable from zero "
                        "across the post-2023 meetings, the path is not the transmission "
                        "variable and the level is",
              notes="the DAY AFTER the meeting is the tradable date; a vendor calendar that "
                    "stamps the meeting date is off by one session"),
        actor("Swedish households with three-month floating mortgages",
              holds="the highest household debt-to-income ratio in Europe, mostly at a rate that "
                    "resets every three months",
              forced_to=("accept the reset; the contract is not renegotiable",
                         "amortise under the FSA's amorteringskrav when loan-to-value or "
                         "loan-to-income exceeds a threshold"),
              when="every three months per loan, so the aggregate reset is continuous and the "
                   "pass-through is complete within roughly two quarters",
              information=("three-month STIBOR", "the banks' published listrantor"),
              constraints=("a regulatory amortisation requirement that converts a rate rise into "
                           "a larger cash-flow shock than the rate alone implies",),
              instruments=("EURSEK", "USDSEK"),
              counterparties=("the four large Swedish banks", "the covered bond market"),
              observables=("three-month STIBOR",
                           "the Valueguard HOX house price index, monthly",
                           "SCB household consumption"),
              impact="Swedish domestic demand responds to policy within two quarters, against a "
                     "year in Spain and far longer in Germany -- so the macro-to-FX horizon in "
                     "Sweden is genuinely shorter and a horizon transferred from the euro area "
                     "will be wrong",
              persistence="quarters",
              falsifier="if the HOX index shows no relation to three-month STIBOR at a one-to- "
                        "two-quarter lag while German house prices take years, the "
                        "fast-transmission claim is wrong and the whole housing domain collapses "
                        "to a generic one",
              notes="this is the actor that makes Sweden a CONTROL ECONOMY for the department's "
                    "transmission-speed hypotheses"),
        actor("Swedish mortgage banks and the covered bond market",
              holds="a mortgage book funded with sakerstallda obligationer in krona",
              forced_to=("roll covered bond funding continuously",
                         "publish listrantor (list rates) that customers negotiate against"),
              when="continuous issuance; quarterly reporting",
              information=("STIBOR", "the covered-bond spread to government"),
              constraints=("a funding market that is large relative to the sovereign's, so a "
                           "Swedish credit event would be a housing event first",),
              instruments=("EURSEK", "GER40"),
              counterparties=("Swedish and foreign investors in covered bonds",
                              "Swedish households"),
              observables=("the covered bond spread to government",
                           "banks' published list rates against STIBOR"),
              impact="the spread between the policy rate and the mortgage rate is the actual "
                     "transmission, and it widens in stress independently of the policy rate",
              persistence="months",
              falsifier="if the covered-bond spread shows no widening in the episodes where "
                        "EURSEK sold off hardest, bank funding is not the krona's stress channel",
              notes="the covered bond market is a TRANSMISSION_TARGET; only the krona is tradable"),
        actor("Riksgalden (Swedish National Debt Office)",
              holds="the sovereign's small and shrinking funding programme",
              forced_to=("auction on a published calendar",
                         "publish a borrowing forecast three times a year"),
              when="weekly auctions, calendar published ahead",
              information=("the central government borrowing requirement",
                           "the fiscal framework's surplus target"),
              constraints=("Sweden's debt ratio is among the lowest in the EU, so the programme "
                           "is small and the market is thin -- a given auction size is a larger "
                           "share of the market than in Germany",),
              instruments=("EURSEK", "USDSEK"),
              counterparties=("primary dealers", "foreign investors, who own a large share"),
              observables=("the auction calendar and its volume announcements",
                           "bid-to-cover",
                           "the borrowing forecast revisions"),
              impact="a supply concession that should be LARGER than Germany's in relative terms "
                     "because the market is thinner -- a directly testable cross-country claim",
              persistence="hours around the auction",
              falsifier="if the Swedish auction concession measured in krona terms is no larger "
                        "relative to the market's depth than the German one, market thinness is "
                        "not the driver and the supply family should be abandoned in both",
              notes="the bond leg is not executable; the krona is the proxy and a weak one"),
        actor("The AP funds and Swedish insurers",
              holds="a large foreign asset book against krona liabilities, with policy hedge "
                    "ratios",
              forced_to=("rebalance to a strategic allocation on a schedule",
                         "hedge a policy fraction of currency exposure",
                         "publish annual reports with the allocation"),
              when="month-end and quarter-end, executed into the 16:00 London fix",
              information=("their own allocation and hedge policy",
                           "the month's realised foreign return"),
              constraints=("a board-mandated hedge ratio that executes mechanically; a strong "
                           "foreign equity month forces krona BUYING",),
              instruments=("EURSEK", "USDSEK", "SEKJPY"),
              counterparties=("bank FX desks", "the WMR fix"),
              observables=("annual reports with hedge ratios",
                           "month-end fix volume",
                           "the month's foreign equity return, which sets the sign"),
              impact="a mechanical month-end krona flow whose sign is set by the past month",
              persistence="the fix window",
              falsifier="if USDSEK's return in the WMR window on the last business day of a "
                        "month has no relation to the month's realised S&P return, the hedge "
                        "rebalancing is not visible at this frequency",
              notes="Sweden's index weight exceeds its economic weight, so the flow is large "
                    "relative to krona turnover"),
        actor("Swedish industrial exporters",
              holds="euro and dollar receivables against a krona cost base, in a capital-goods "
                    "sector levered to the German industrial cycle",
              forced_to=("hedge on a treasury policy",
                         "report in krona, so a weak krona flatters earnings"),
              when="quarterly hedge rolls",
              information=("their own order books", "the German Ifo survey"),
              constraints=("order books that follow German capital expenditure, which is why the "
                           "krona is a leveraged play on GER40 rather than an independent "
                           "small-economy currency",),
              instruments=("EURSEK", "GER40", "USDSEK"),
              counterparties=("bank FX desks", "German and global industrial customers"),
              observables=("SCB goods exports",
                           "the Ifo expectations component",
                           "GER40's own performance"),
              impact="the krona's high beta to European industrial risk; EURSEK is closer to a "
                     "risk asset than to a rate differential trade",
              persistence="quarters",
              falsifier="if EURSEK's weekly return has no relation to GER40's once the euro's own "
                        "move is removed, the industrial-beta story is wrong and the krona is a "
                        "rate-differential currency after all",
              notes="this is the edge the pack is most confident in and the one most likely to be "
                    "already crowded"),
        actor("Foreign investors in Swedish government bonds",
              holds="a large share of a small krona bond market",
              forced_to=("hedge the currency, or not, on a mandate",
                         "reduce exposure on a global risk shock regardless of Swedish news"),
              when="on global risk events, not Swedish ones",
              information=("global risk appetite", "the krona's own carry"),
              constraints=("a market small enough that a modest foreign reallocation is a large "
                           "domestic flow",),
              instruments=("EURSEK", "USDSEK", "GER40"),
              counterparties=("Riksgalden", "Swedish banks"),
              observables=("Riksbank monthly foreign-ownership statistics",
                           "the krona's move on days with no Swedish news at all"),
              impact="the krona sells off on global risk with no Swedish trigger, which is the "
                     "single most common source of a spurious 'Swedish' finding",
              persistence="days",
              falsifier="if the krona's largest weekly losses are NOT concentrated on days with "
                        "global risk moves and no Swedish releases, the foreign-flow channel is "
                        "not dominant and domestic news matters more than the pack assumes",
              notes="this actor is the reason every Swedish domain needs a global-risk control"),
        actor("Nasdaq Stockholm market makers in the OMXS30 complex",
              holds="option books into a FOURTH-Friday expiry settled on a whole-day average",
              forced_to=("hedge continuously",
                         "unwind against an averaging window spread over the whole expiry day "
                         "rather than a single auction"),
              when="the fourth Friday of each month",
              information=("Nasdaq open interest", "their own inventory"),
              constraints=("a whole-day settlement average means there is no single instant to "
                           "defend, which spreads the hedging demand across the session instead "
                           "of concentrating it -- a structurally different pinning problem from "
                           "the DAX's 13:00 CET auction",),
              instruments=("EURSEK", "GER40"),
              counterparties=("Swedish retail warrant issuers", "institutional hedgers"),
              observables=("Nasdaq Nordic open interest",
                           "expiry-day realised volatility against matched Fridays"),
              impact="a Swedish expiry effect on a date one week later than the rest of Europe, "
                     "which means European and Swedish expiry effects never coincide",
              persistence="the expiry day",
              falsifier="if EURSEK shows no abnormal behaviour on fourth Fridays relative to "
                        "matched Fridays, the Swedish expiry does not reach the krona and this "
                        "actor is index-only -- which given there is no executable index means "
                        "the domain is closed",
              notes="the non-coincidence with the European third Friday is itself the most useful "
                    "fact here: it makes Sweden a clean control for a European expiry study"),
        actor("Finansinspektionen (the Swedish FSA)",
              holds="the macroprudential levers over the mortgage market",
              forced_to=("consult publicly before changing the amorteringskrav",
                         "publish an annual mortgage market report"),
              when="event-driven, with a public consultation period that dates the announcement",
              information=("its own lending survey", "household debt statistics"),
              constraints=("a mandate that forces it to act on household leverage even when the "
                           "Riksbank is easing -- the two Swedish authorities can and do pull in "
                           "opposite directions, which no single policy-rate series captures",),
              instruments=("EURSEK", "USDSEK"),
              counterparties=("Swedish banks", "households"),
              observables=("consultation documents and their dates",
                           "the annual mortgage market report",
                           "new-lending loan-to-value distributions"),
              impact="a dated regulatory shock to the housing channel that is independent of the "
                     "policy rate",
              persistence="structural once implemented",
              falsifier="if HOX and new-lending volumes show no break around amorteringskrav "
                        "changes, the regulatory lever is not binding and only the rate matters",
              notes="a rare case of two domestic authorities with opposing levers on one channel"),
        actor("Nordic cross-rate arbitrageurs in NOKSEK",
              holds="relative-policy positions between two similar small open economies",
              forced_to=("mark against two central banks whose meeting calendars do not align",),
              when="around each Riksbank and Norges Bank decision, which rarely coincide",
              information=("both policy paths", "the oil price, which moves one leg only"),
              constraints=("NOKSEK is the cleanest available relative-policy pair in Europe: two "
                           "small, open, commodity-adjacent economies with different central "
                           "banks and a shared risk beta, so the shared component nets out",),
              instruments=("NOKSEK", "EURSEK", "EURNOK"),
              counterparties=("Nordic bank FX desks",),
              observables=("the two policy rate paths",
                           "XBRUSD, which should move EURNOK and not EURSEK"),
              impact="NOKSEK isolates the relative policy stance from the shared European risk "
                     "factor, which neither EURSEK nor EURNOK does alone",
              persistence="weeks to months",
              falsifier="if NOKSEK's variance is not materially lower than EURSEK's after "
                        "removing a common European factor, the two krona are not close "
                        "substitutes and the netting argument fails",
              notes="the Norwegian pack carries the other side of this actor"),
        actor("Swedish energy-intensive industry across four price areas",
              holds="electricity cost exposure that differs by a factor across SE1 and SE4",
              forced_to=("buy power at the area price, which transmission constraints set",
                         "hedge on a policy horizon"),
              when="continuous, seasonal in winter",
              information=("Nord Pool area prices", "hydrological balance in the north"),
              constraints=("a north-south transmission constraint that makes one country have "
                           "four electricity prices -- a domestic cost dispersion with no "
                           "analogue in Germany or France",),
              instruments=("GER40", "EURSEK"),
              counterparties=("Nord Pool", "Svenska kraftnat"),
              observables=("SE1-SE4 area prices and their spread",
                           "Nordic hydrological balance"),
              impact="an industrial cost shock that is regional within Sweden and invisible in "
                     "any national aggregate",
              persistence="seasonal",
              falsifier="if the SE1-SE4 spread has no relation to Swedish industrial production "
                        "or to the krona, the area-price dispersion is an electricity-market "
                        "artefact with no macro content",
              notes="no executable Swedish power leg; GER40 carries the shared European component "
                    "and is therefore a control rather than a target here"),
        actor("Swedish retail investors in the equity and warrant market",
              holds="one of the highest rates of direct and fund equity participation in Europe",
              forced_to=("make the annual ISK tax-account decisions on a calendar",
                         "roll warrants into the fourth-Friday expiry"),
              when="continuous, with a January effect from tax-year behaviour",
              information=("Swedish financial media and retail forums",
                           "the ISK schablonskatt rate, which is set annually"),
              constraints=("a tax wrapper (ISK) that taxes a notional return rather than a "
                           "realised gain, which removes the lock-in effect that shapes retail "
                           "behaviour in most countries",),
              instruments=("GER40", "EURSEK"),
              counterparties=("warrant issuers", "Nasdaq Stockholm"),
              observables=("retail forum activity",
                           "warrant open interest into the fourth Friday",
                           "January flows"),
              impact="Swedish retail is unusually active and unusually untaxed on realisation, so "
                     "the classic December tax-loss and January reversal patterns should be "
                     "WEAKER in Sweden than elsewhere -- a testable cross-country prediction",
              persistence="seasonal",
              falsifier="if a Swedish January effect is as strong as the international average, "
                        "the ISK argument is wrong and the seasonality is not tax-driven",
              notes="a prediction of ABSENCE is still a prediction, and this one is cheap to test"),
        actor("The Riksbank's own FX reserve hedging desk",
              holds="a foreign currency reserve whose krona value moves with the exchange rate",
              forced_to=("execute an announced hedging programme once the board has decided it",
                         "publish the decision, which is what makes it tradable"),
              when="event-driven: the September 2023 programme is the reference case",
              information=("the reserve's currency composition", "the krona's level"),
              constraints=("a board decision that, once announced, must be executed regardless of "
                           "the level -- a central bank publicly committing to a months-long "
                           "one-way FX flow is rare and it is dated",),
              instruments=("EURSEK", "USDSEK", "EURUSD"),
              counterparties=("bank FX desks",),
              observables=("the announcement itself, which is the tradable event",
                           "monthly reserve statistics, which confirm it after the fact"),
              impact="a dated, announced, one-way krona bid running for months; the announcement "
                     "is the event and the execution is not observable day by day",
              persistence="the length of the programme",
              falsifier="if the krona showed no abnormal appreciation over the announced hedging "
                        "window in 2023-2024 relative to a matched control period, an announced "
                        "central-bank flow of that size does not move the price and the whole "
                        "announced-flow family is weaker than the pack claims",
              notes="the single cleanest natural experiment in this pack: a public, dated, "
                    "one-way flow with a known start"),
    )


def domains() -> tuple[dict[str, Any], ...]:
    """Eleven research domains, each with negative controls."""
    return (
        domain("SE-A", "Riksbank decisions and the published rate path",
               objects=("the 09:30 CET decision, the day AFTER the meeting",
                        "the published rate path (rantebanan) and its revision",
                        "the minutes, roughly two weeks later, naming dissenters"),
               conditions=("report meeting versus non-report meeting",
                           "the sign and size of the path revision",
                           "the cadence era: five meetings a year before 2023, eight after"),
               instruments=("EURSEK", "USDSEK", "NOKSEK", "SEKJPY"),
               controls=("the same window on a matched non-decision day",
                         "the ECB's own decision days, since EURSEK has a euro leg that the "
                         "Riksbank does not control",
                         "NOKSEK, which nets the shared Nordic risk factor out and leaves only "
                         "the relative policy stance",
                         "a placebo at 09:30 CET on the MEETING day rather than the "
                         "announcement day, which is the error a vendor calendar induces"),
               notes="the path revision is a better surprise measure than a survey because the "
                     "bank's own prior forecast is public; almost no other country allows this"),
        domain("SE-B", "The three-month mortgage reset as Europe's fastest transmission",
               objects=("three-month STIBOR as the reset clock",
                        "the Valueguard HOX index at a one-to-two-quarter lag",
                        "the banks' list rates against STIBOR"),
               conditions=("the direction of the policy cycle",
                           "the amorteringskrav regime",
                           "the household debt level"),
               instruments=("EURSEK", "USDSEK"),
               controls=("Germany as the slow-transmission control economy: the same regression "
                         "should be near-zero at a two-quarter lag there",
                         "Spain as the intermediate case, where the reset is annual",
                         "a placebo lag structure with the lead and lag reversed",
                         "the pre-2022 low-rate era, where the reset was not binding"),
               notes="this is a CROSS-COUNTRY domain by construction; a Swedish result with no "
                     "German comparison proves nothing about speed"),
        domain("SE-C", "The krona as a high-beta European risk asset",
               objects=("EURSEK's relation to GER40",
                        "the krona's behaviour on global risk days with no Swedish news",
                        "the asymmetry between krona weakness and krona strength"),
               conditions=("the volatility regime",
                           "whether any Swedish release occurred that day",
                           "the direction of the move"),
               instruments=("EURSEK", "USDSEK", "GER40", "SEKJPY"),
               controls=("days with a Swedish release removed entirely, which is the cleanest "
                         "test of whether the krona needs Swedish news at all",
                         "EURNOK on the same day, which shares the Nordic beta and not the "
                         "industrial one",
                         "USDX, to separate a dollar move from a krona move",
                         "a symmetric-versus-asymmetric split, since the high-beta claim "
                         "predicts a larger downside beta"),
               notes="the most likely already-crowded edge in this pack, which is a reason to "
                     "measure the CROWDING and not only the effect"),
        domain("SE-D", "The fourth-Friday expiry",
               objects=("the fourth Friday and its roll-back rule",
                        "the whole-day averaging settlement window",
                        "the one-week separation from the European third Friday"),
               conditions=("quarterly versus monthly expiry",
                           "whether the roll-back moved the date",
                           "open interest concentration"),
               instruments=("EURSEK", "GER40"),
               controls=("the THIRD Friday of the same month, which is the European expiry and "
                         "should show the European effect and not the Swedish one",
                         "matched non-expiry Fridays",
                         "GER40 on the same fourth Friday, which should show nothing if the "
                         "effect is Swedish",
                         "December 2026 specifically, where the roll-back moves the date to a "
                         "Wednesday and any Friday-based study is testing an empty date"),
               notes="the one-week separation makes Sweden a clean control for European expiry "
                     "studies, which is worth more than the Swedish effect itself"),
        domain("SE-E", "Riksgalden supply in a thin market",
               objects=("the weekly auction calendar and volume announcements",
                        "bid-to-cover", "the borrowing forecast revisions"),
               conditions=("announced size relative to recent average",
                           "the share of the market held abroad",
                           "whether a foreign risk event fell in the same week"),
               instruments=("EURSEK", "USDSEK"),
               controls=("the German auction on a comparable day, scaled by market depth -- the "
                         "claim is that thinness amplifies, so the RATIO is the test",
                         "weeks with no auction",
                         "auctions that fell in a global risk week, which should be "
                         "indistinguishable from the risk effect alone",
                         "a placebo auction date one week displaced"),
               notes="no executable Swedish bond leg; the krona is a weak proxy and the domain "
                     "expects a small or null result"),
        domain("SE-F", "Month-end hedge rebalancing by the AP funds and insurers",
               objects=("the 16:00 London fix on the T-2 date",
                        "the sign set by the month's realised foreign return",
                        "quarter-end amplification"),
               conditions=("month-end versus quarter-end",
                           "the magnitude of the foreign equity move",
                           "whether the T-2 date is a Swedish-only closure"),
               instruments=("USDSEK", "EURSEK", "SEKJPY"),
               controls=("mid-month days matched on weekday",
                         "the last CALENDAR day against the T-2 value date, to show the effect "
                         "follows settlement and not the calendar",
                         "months with a near-zero foreign return, where no flow is predicted",
                         "the euro area's own month-end effect, scaled -- Sweden's index weight "
                         "exceeds its economic weight, so the Swedish effect should be larger "
                         "relative to turnover"),
               notes="Midsommarafton and 6 January can both land on a T-2 date, which shifts the "
                     "whole window; the calendar in this module is what catches it"),
        domain("SE-G", "Midsommar, klamdagar and the summer liquidity hole",
               objects=("Midsommarafton as a full exchange closure",
                        "the klamdagar the rule in this module computes",
                        "July as the Swedish holiday month"),
               conditions=("exchange open versus closed",
                           "klamdag versus ordinary weekday",
                           "the presence or absence of scheduled news"),
               instruments=("EURSEK", "USDSEK", "NOKSEK"),
               controls=("volume as the direct control: if turnover is normal the day was not "
                         "thin and the mechanism did not operate",
                         "matched weekdays in the same month",
                         "a non-Swedish pair on the same day, which isolates the Swedish leg",
                         "the day after, where a catch-up should appear if the flow was delayed "
                         "rather than absent"),
               notes="a liquidity treatment with no information confound is rare; klamdagar are "
                     "the closest thing Europe has to one"),
        domain("SE-H", "Swedish housing data and the regulatory lever",
               objects=("the Valueguard HOX monthly index",
                        "Finansinspektionen's amorteringskrav changes and their consultation dates",
                        "new-lending loan-to-value distributions"),
               conditions=("the policy cycle direction",
                           "whether the FSA and the Riksbank are pulling the same way",
                           "the debt-to-income level"),
               instruments=("EURSEK", "USDSEK"),
               controls=("the Norwegian housing market, which has the same structure and a "
                         "different regulator",
                         "the period before the amorteringskrav existed, where only the rate "
                         "should matter",
                         "a placebo announcement date from the consultation period rather than "
                         "the decision",
                         "German house prices as the slow-transmission control"),
               notes="two domestic authorities with opposing levers on one channel is unusual and "
                     "means a single policy-rate series cannot describe Swedish conditions"),
        domain("SE-I", "The Riksbank's announced FX reserve hedging",
               objects=("the September 2023 hedging announcement",
                        "the execution window",
                        "the monthly reserve statistics that confirm it afterwards"),
               conditions=("inside versus outside the announced window",
                           "the announcement day itself versus the execution period"),
               instruments=("EURSEK", "USDSEK", "EURUSD"),
               controls=("a matched control period of equal length before the announcement",
                         "EURNOK over the same window, which shares the Nordic factor and had no "
                         "such programme",
                         "the announcement day removed, to test whether the EXECUTION rather "
                         "than the news moved the price",
                         "EURUSD, since selling dollars for krona is also a dollar trade"),
               notes="a public, dated, one-way central-bank flow with a known start is the "
                     "cleanest natural experiment in this pack and there is exactly one of it"),
        domain("SE-J", "NOKSEK as the relative-policy pair",
               objects=("the two central banks' non-aligned calendars",
                        "the oil price, which moves one leg only",
                        "the shared European risk factor, which nets out"),
               conditions=("which central bank met most recently",
                           "the oil regime",
                           "the volatility regime"),
               instruments=("NOKSEK", "EURSEK", "EURNOK", "XBRUSD"),
               controls=("EURSEK and EURNOK separately, to show the netting actually removes the "
                         "common factor rather than adding noise",
                         "XBRUSD as the Norwegian-only driver: a NOKSEK move on an oil move is "
                         "not a policy signal",
                         "days when both banks are silent",
                         "a variance decomposition against a common European factor"),
               notes="the Norwegian pack carries the mirror of this domain; stated in both "
                     "rather than in neither"),
        domain("SE-K", "Swedish positioning: the declared gap",
               objects=("the ABSENCE of a CFTC krona series",
                        "Riksbank foreign-ownership statistics as the monthly substitute",
                        "Nasdaq open interest as the non-executable daily substitute"),
               conditions=("whether a crowding claim can be measured at all at the horizon asked",
                           "the ownership share level"),
               instruments=("EURSEK", "USDSEK"),
               controls=("the euro's own COT applied to SEK as an explicit NEGATIVE control: if "
                         "it appears to work, that is evidence the effect is European and not "
                         "Swedish, not evidence that EUR positioning proxies SEK",
                         "a randomised ownership series, to show the monthly statistic carries "
                         "information beyond its own persistence",
                         "the same hypothesis on EUR, where the measurement exists",
                         "the explicit UNMEASURED verdict, which must remain available"),
               notes="the domain exists so that 'we could not measure it' is a RECORDED verdict "
                     "rather than a silent omission (L1.28a)"),
    )


TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    edge("SE-E01",
         source="the Riksbank's published two-year rate path revision at 09:30 CET the day after "
                "a policy meeting",
         mechanism="the bank publishes its own forecast, so the surprise is the revision to a "
                   "public prior rather than a deviation from a survey",
         targets=("EURSEK", "USDSEK", "NOKSEK"),
         sign="upward path revision -> EURSEK down", horizon="intraday to a week",
         lag="0 to 30 minutes",
         control="matched non-decision days; ECB decision days; the MEETING date as an explicit "
                 "placebo, because that is the date a vendor calendar gives you",
         evidence="HYPOTHESIS",
         notes="the announcement is the day AFTER the meeting; getting that wrong tests an "
               "empty date"),
    edge("SE-E02",
         source="three-month STIBOR, at a one-to-two-quarter lead",
         mechanism="a large floating mortgage stock resets every three months, so policy reaches "
                   "Swedish household cash flow within two quarters",
         targets=("EURSEK", "USDSEK"),
         sign="STIBOR up -> Swedish demand down -> krona weaker at the macro horizon",
         horizon="one to two quarters", lag="the reset is contractual",
         control="Germany at the same lag, where the fixed-rate stock predicts near-zero; Spain "
                 "as the intermediate annual-reset case",
         evidence="HYPOTHESIS",
         notes="the sign is not obvious: a hike supports the krona through carry and weakens it "
               "through demand, and which dominates at which horizon is the actual question"),
    edge("SE-E03",
         source="GER40's weekly return",
         mechanism="Swedish capital-goods exporters follow German capital expenditure, so the "
                   "krona is a leveraged play on European industrial risk",
         targets=("EURSEK", "USDSEK", "SEKJPY"),
         sign="GER40 down -> EURSEK up (krona weaker), with a larger downside beta",
         horizon="days to weeks", lag="same session",
         control="EURNOK, which shares the Nordic beta and not the industrial one; USDX for the "
                 "dollar leg; days with a Swedish release removed",
         evidence="MEASURED_ELSEWHERE",
         notes="widely known; the desk-specific questions are the asymmetry and the crowding"),
    edge("SE-E04",
         source="the OMXS30 fourth-Friday expiry, roll-back applied",
         mechanism="a whole-day averaging settlement spreads hedging demand across the session "
                   "instead of concentrating it at an auction",
         targets=("EURSEK", "GER40"),
         sign="altered intraday volatility profile on the expiry day",
         horizon="intraday", lag="none",
         control="the THIRD Friday of the same month, which is the European expiry; matched "
                 "non-expiry Fridays; GER40 on the same day",
         evidence="HYPOTHESIS",
         notes="December 2026's fourth Friday is Christmas Day and the roll-back moves it to "
               "the 23rd -- a naive rule tests an empty date"),
    edge("SE-E05",
         source="the last two business days before a month-end value date, conditioned on the "
                "month's realised foreign equity return",
         mechanism="AP funds and insurers rebalance a policy currency hedge into the 16:00 "
                   "London fix; Sweden's index weight exceeds its economic weight",
         targets=("USDSEK", "EURSEK", "SEKJPY"),
         sign="strong foreign equity month -> krona bid into the fix",
         horizon="intraday", lag="the fix window",
         control="mid-month weekday-matched days; the last calendar day against the T-2 date; "
                 "months with a near-zero foreign return",
         evidence="HYPOTHESIS",
         notes="Midsommarafton and 6 January can both land on a T-2 date and shift the window"),
    edge("SE-E06",
         source="a Midsommarafton or klamdag session",
         mechanism="the country is absent while the price keeps moving; a liquidity treatment "
                   "with no information content",
         targets=("EURSEK", "USDSEK", "NOKSEK"),
         sign="compressed realised range, wider effective spreads, larger overnight gap after",
         horizon="intraday", lag="none",
         control="turnover as the direct control; matched weekdays; a non-Swedish pair on the "
                 "same day; the following session for the catch-up test",
         evidence="HYPOTHESIS",
         notes="the klamdag calendar is DERIVED in this module, so the sample is reproducible "
               "rather than hand-listed"),
    edge("SE-E07",
         source="the Valueguard HOX monthly house price print",
         mechanism="Swedish housing is the most rate-sensitive large asset in Europe and its "
                   "turn is the clearest read on whether the reset has bitten",
         targets=("EURSEK", "USDSEK"),
         sign="HOX weaker than expected -> krona weaker on the Riksbank-easing channel",
         horizon="weeks", lag="published around the 20th for the prior month",
         control="the Norwegian housing market, same structure and different regulator; German "
                 "prices as the slow-transmission control",
         evidence="HYPOTHESIS",
         notes="the sign runs through expected policy, not through direct wealth effects"),
    edge("SE-E08",
         source="an announced Riksbank FX reserve hedging programme",
         mechanism="a public, dated, months-long one-way krona bid that the board has committed "
                   "to execute regardless of level",
         targets=("EURSEK", "USDSEK", "EURUSD"),
         sign="announcement -> krona firmer over the programme window",
         horizon="months", lag="the announcement is instant, the execution is not observable",
         control="a matched control period before the announcement; EURNOK over the same window; "
                 "the announcement day removed to separate news from execution",
         evidence="HYPOTHESIS",
         notes="one observation. A single natural experiment is a case study and the pack says "
               "so rather than calling it a sample."),
    edge("SE-E09",
         source="a Finansinspektionen amorteringskrav change",
         mechanism="a macroprudential lever on household cash flow that operates independently "
                   "of the policy rate and is dated by a public consultation",
         targets=("EURSEK", "USDSEK"),
         sign="tightening -> Swedish housing and demand weaker -> krona weaker at the macro "
              "horizon",
         horizon="quarters", lag="the consultation dates the announcement ahead of the effect",
         control="the consultation date as a placebo against the decision date; the period "
                 "before the requirement existed; Norway's own regulator on different dates",
         evidence="HYPOTHESIS",
         notes="the two Swedish authorities can pull in opposite directions, so the policy rate "
               "alone does not describe Swedish conditions"),
    edge("SE-E10",
         source="a Norges Bank decision with no Riksbank decision in the same week",
         mechanism="NOKSEK isolates the relative policy stance because the shared European risk "
                   "factor nets out across two similar small open economies",
         targets=("NOKSEK", "EURSEK", "EURNOK"),
         sign="a hawkish Norges Bank -> NOKSEK up",
         horizon="days", lag="0 to 30 minutes on the announcement",
         control="XBRUSD, since an oil move also moves NOKSEK and is not a policy signal; days "
                 "when both banks are silent; EURSEK and EURNOK separately",
         evidence="HYPOTHESIS",
         notes="the Norwegian pack carries the mirror; both name the oil control"),
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
    era("se.negative", start="2015-02-18", end="2019-12-19",
        label="the negative repo rate era",
        what_changed="the repo rate went below zero and the Riksbank bought government bonds; "
                     "the krona was a funding currency throughout",
        invalidates="carry studies spanning the 2019 exit; the krona's role in a carry basket "
                    "changes sign",
        notes="only the 2018-2019 tail is on this box's FX bars, and the index bars miss it "
              "entirely"),
    era("se.rate_rename", start="2022-06-01", end=None,
        label="reporanta renamed styrranta with a change in the operational target",
        what_changed="the name and the operational definition of the policy rate",
        invalidates="ANY series joined by NAME across this date. A vendor that switched series "
                    "silently produces a continuous-looking number with a definitional break in "
                    "it -- the cheapest available way to fail a Swedish rates backtest.",
        notes="pure definition, no policy content, and exactly the sort of thing a pack exists "
              "to record"),
    era("se.hiking", start="2022-04-28", end="2023-09-21",
        label="the hiking cycle to 4.00%",
        what_changed="the fastest Swedish tightening in decades into the most indebted household "
                     "sector in Europe, with a three-month reset transmitting it",
        invalidates="anything estimated on the 2015-2021 sample; the housing channel switched "
                    "from dormant to dominant",
        notes="fully on this box's bars and the most informative era in the pack"),
    era("se.eight_meetings", start="2023-01-01", end=None,
        label="the cadence change from five policy meetings a year to eight",
        what_changed="the NUMBER OF EVENTS per year, and therefore the average information "
                     "content of each one",
        invalidates="any per-meeting normalisation across 2023, and any 'average decision-day "
                    "move' statistic pooled over the boundary -- the denominator changed",
        notes="a regime break with no economic content whatsoever, which makes it a perfect "
              "test of whether a study is measuring events or measuring the calendar"),
    era("se.fx_hedge", start="2023-09-25", end="2024-06-30",
        label="the announced hedging of part of the FX reserves",
        what_changed="the Riksbank publicly committed to a months-long one-way krona purchase",
        invalidates="a krona model with no announced-flow term over this window; the flow was "
                    "public and price-insensitive",
        notes="the start date is DECLARED from public knowledge and the end date is the desk's "
              "reading; both should be verified against riksbank.se before the window is used"),
    era("se.cutting", start="2024-05-08", end=None,
        label="the cutting cycle",
        what_changed="the krona's rate differential narrowed from the Swedish side while the "
                     "housing channel was still repairing",
        invalidates="carry studies calibrated on 2022-2023",
        notes="OPEN ERA; the end is UNMEASURED and must not be back-filled"),
    era("se.housing_correction", start="2022-04-01", end="2024-06-30",
        label="the Swedish house price correction",
        what_changed="HOX fell materially as the three-month reset transmitted the hiking cycle, "
                     "which is the mechanism working exactly as the pack describes it",
        invalidates="a housing-to-FX relation estimated only in the appreciation phase",
        notes="the end date is the desk's reading and is DECLARED, not measured"),
)

CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    miner("se_riksbank_path", domain_ids=("SE-A",), kind="mechanism",
          entry="countries.se.miners:riksbank_path",
          notes="NOT WIRED. Must key on the ANNOUNCEMENT date (the day after the meeting) and "
                "run the meeting-date placebo."),
    miner("se_transmission_speed", domain_ids=("SE-B", "SE-H"), kind="transfer",
          entry="countries.se.miners:transmission_speed",
          notes="NOT WIRED. Cross-country by construction: a Swedish lag structure with no "
                "German comparison proves nothing about speed."),
    miner("se_krona_beta", domain_ids=("SE-C",), kind="mechanism",
          entry="countries.se.miners:krona_beta",
          notes="NOT WIRED. Must remove Swedish-release days entirely as the primary control."),
    miner("se_fourth_friday", domain_ids=("SE-D",), kind="mechanism",
          entry="countries.se.miners:fourth_friday",
          notes="NOT WIRED. Uses `omxs30_expiry` so the roll-back is applied; the third Friday "
                "of the same month is the European control."),
    miner("se_calendar_thin", domain_ids=("SE-G",), kind="data",
          entry="countries.se.miners:calendar_thin", cadence_s=86400.0, steerable=False,
          notes="NOT WIRED. A fixed cost: derives the closures and klamdagar from the rules in "
                "this module so the sample is reproducible rather than hand-listed."),
    miner("se_month_end_hedge", domain_ids=("SE-F",), kind="mechanism",
          entry="countries.se.miners:month_end_hedge",
          notes="NOT WIRED. Anchors on the T-2 value date computed against the Swedish calendar."),
    miner("se_announced_flow", domain_ids=("SE-I",), kind="failure",
          entry="countries.se.miners:announced_flow",
          notes="NOT WIRED. One observation. Must report n=1 and refuse to call it a sample."),
    miner("se_nordic_relative", domain_ids=("SE-J",), kind="transfer",
          entry="countries.se.miners:nordic_relative",
          notes="NOT WIRED. Shared with the Norwegian pack; the oil control is mandatory."),
    miner("se_positioning_gap", domain_ids=("SE-K",), kind="data",
          entry="countries.se.miners:positioning_gap", cadence_s=604800.0,
          notes="NOT WIRED. Its output is a declared UNMEASURED verdict with the substitutes "
                "named, which is a real answer (L1.28a)."),
)


def pack() -> Any:
    """The Swedish country pack: `CountryPack` when the framework has landed, else a dict."""
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
