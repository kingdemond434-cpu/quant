"""THE NORWAY PACK -- an announced daily central-bank FX order, and a six-week statutory lag.

Thirteen actors with their eleven fields, eleven domains A..K with objects, conditions,
instruments and negative controls, nine datasets with all six point-in-time stamps, ten
transmission edges naming real Fusion symbols, seven policy eras, and a holiday calendar derived
from the rule.

THREE THINGS THIS PACK INSISTS ON.

  * THE NORGES BANK DAILY FX AMOUNT IS THE PACK'S CENTRE. It is announced before the month it
    applies to, it is a fixed daily size, it is one-way for the whole month, and it is public.
    The announcement is the EVENT and the execution is the FLOW, and they are different objects
    with different dates -- an edge that conflates them is measuring the wrong thing.
  * BRENT DOES NOT MOVE NOK UNCONDITIONALLY. The state captures the rent and sterilises it, so
    the oil-to-krone channel runs through the fiscal rule and the fund's conversion, not through
    the trade balance. Every oil edge in this pack is CONDITIONAL on the fiscal setting and on
    the announced daily amount, and the unconditional version is carried only as the null.
  * XNGUSD IS HENRY HUB AND NORWAY SELLS INTO TTF. Norway became Europe's largest pipeline gas
    supplier after 2022, and the gas price that matters to it is the Dutch TTF, which Fusion does
    not quote. XNGUSD is a CONTROL for that channel and never a proxy; the two benchmarks
    decoupled by an order of magnitude in 2022.
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta
from typing import Any

from countries import actor, build_pack, dataset, domain, edge, era, miner, source_class

CODE = "NO"
NAME = "Norway"
REGION_COMMAND = "EUROPE"
CURRENCY = "NOK"

PIT_STAMPS: tuple[str, ...] = ("event_time", "period_time", "publication_time", "available_time",
                               "revision_time", "retrieval_time")

#: The krone complex, plus the energy and dollar legs a Norwegian mechanism actually reaches.
#: XBRUSD is genuinely Norwegian economics; XNGUSD is a CONTROL for the gas channel, not a proxy.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "EURNOK", "USDNOK", "NOKSEK", "CHFNOK", "GBPNOK", "NOKJPY",
    "XBRUSD", "XTIUSD", "XNGUSD", "EURUSD", "USDX",
)

#: What Norway's economics run through that Fusion does not quote.
TRANSMISSION_TARGETS: tuple[dict[str, str], ...] = (
    {"name": "OBX / OSEBX", "venue": "Euronext Oslo",
     "role": "the Norwegian equity bloc, dominated by energy and seafood",
     "route": "XBRUSD carries most of the index's variance and IS executable, which makes Norway "
              "the one country in this department whose equity beta has a tradable proxy that is "
              "not an index at all"},
    {"name": "Dutch TTF natural gas", "venue": "ICE Endex",
     "role": "THE price Norway sells gas at. After 2022 Norway became Europe's largest pipeline "
             "supplier, so the Norwegian terms of trade are a TTF variable and not a Brent one.",
     "route": "EURNOK, USDNOK; XNGUSD is the CONTROL and not the proxy"},
    {"name": "NIBOR and NOWA", "venue": "Norske Finansielle Referanser / Norges Bank",
     "role": "the term and overnight krone benchmarks. NIBOR is a USD-derived construction -- it "
             "is built from a dollar rate and the forward points -- so it carries dollar funding "
             "stress into Norwegian mortgage pricing, which no other Nordic benchmark does.",
     "route": "EURNOK, USDNOK -- an input, never a leg"},
    {"name": "Norwegian government bonds (statsobligasjoner)",
     "venue": "Norges Bank auctions, OTC secondary",
     "role": "a tiny market: the state has no net borrowing need because the fund exists, so "
             "issuance is for market-maintenance rather than funding",
     "route": "EURNOK, USDNOK"},
    {"name": "Nord Pool NO1-NO5 power prices and the interconnectors",
     "venue": "Nord Pool / Statnett",
     "role": "five price areas, hydro-dominated, with cables to Germany and the UK that couple "
             "southern Norwegian power to the continental price and leave the north decoupled",
     "route": "GER40 and UK100 carry the continental leg; there is no executable Norwegian one"},
    {"name": "Norwegian salmon spot price (NASDAQ salmon index)",
     "venue": "Nasdaq / Fish Pool",
     "role": "seafood is Norway's second export; the spot index is public and weekly",
     "route": "EURNOK -- a second-order terms-of-trade input with a real publication clock"},
)


def easter_sunday(year: int) -> date:
    """Gregorian Easter. Norway hangs FOUR closures off it, one more than most of Europe."""
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
    """Euronext Oslo trading holidays.

    MAUNDY THURSDAY (skjaertorsdag) IS THE DISTINCTIVE ONE. Oslo closes on the Thursday before
    Good Friday; Xetra, Euronext Paris, Nasdaq Stockholm and the London exchanges all trade that
    day. It is a guaranteed annual one-sided session in any Nordic or European cross-index
    spread with a Norwegian leg, and it is derivable from the computus.

    Norwegian law has NO weekend substitution, so 1 May and 17 May cost the market nothing when
    they fall at a weekend -- in 2026, 17 May is a Sunday and 1 May is a Friday.
    """
    e = easter_sunday(year)
    table = {
        date(year, 1, 1): "Nyttarsdag (New Year's Day)",
        e - timedelta(days=3): "Skjaertorsdag (Maundy Thursday -- Oslo closed, most of Europe "
                               "open)",
        e - timedelta(days=2): "Langfredag (Good Friday)",
        e + timedelta(days=1): "Andre paskedag (Easter Monday)",
        e + timedelta(days=39): "Kristi himmelfartsdag (Ascension)",
        e + timedelta(days=50): "Andre pinsedag (Whit Monday)",
        date(year, 12, 24): "Julaften (Christmas Eve)",
        date(year, 12, 25): "Forste juledag (Christmas Day)",
        date(year, 12, 26): "Andre juledag (Boxing Day)",
        date(year, 12, 31): "Nyttarsaften (New Year's Eve)",
    }
    for fixed, label in ((date(year, 5, 1), "Offentlig hoytidsdag (Labour Day)"),
                         (date(year, 5, 17), "Grunnlovsdagen (Constitution Day)")):
        if fixed.weekday() < 5:
            table[fixed] = label + " -- no weekend substitution in Norwegian law"
    return table


def fellesferie(year: int) -> tuple[date, date]:
    """The common holiday: weeks 28-30, the Norwegian July liquidity hole.

    Not a market closure -- the exchange trades and the country is at a cabin. Norwegian turnover
    in these three weeks is a fraction of normal, which makes them a liquidity treatment with no
    information confound, the same shape as the Swedish klamdagar and three weeks long.
    """
    jan4 = date(year, 1, 4)
    week1_monday = jan4 - timedelta(days=jan4.weekday())
    start = week1_monday + timedelta(weeks=27)
    return start, start + timedelta(days=20)


def third_thursday(year: int, month: int) -> date:
    """The OBX derivatives expiry candidate, before the closure roll-back."""
    first = date(year, month, 1)
    return date(year, month, 1 + (3 - first.weekday()) % 7 + 14)


def obx_expiry(year: int, month: int) -> date:
    """OBX derivatives expiry: the THIRD THURSDAY, rolled back over any closure.

    Confidence: DECLARED from public knowledge. Oslo's index derivatives expire on a Thursday
    rather than the European third Friday; verify against the Euronext Oslo contract
    specification before keying an event study to it. The pack states the uncertainty instead of
    asserting a date it has not checked -- a wrong expiry rule does not weaken a study, it
    relocates it onto a day where nothing happened.
    """
    day = third_thursday(year, month)
    closures = set(holidays(year))
    while day.weekday() >= 5 or day in closures:
        day -= timedelta(days=1)
    return day


def _iso(table: dict[date, str]) -> dict[str, str]:
    return {d.isoformat(): n for d, n in sorted(table.items())}


HOLIDAYS_RULE: dict[str, Any] = {
    "calendar": "Euronext Oslo trading holidays, with the fellesferie window beside them",
    "rule": "Closed on Nyttarsdag, SKJAERTORSDAG (Maundy Thursday), Langfredag, Andre paskedag, "
            "Kristi himmelfartsdag, Andre pinsedag, Julaften, Forste and Andre juledag and "
            "Nyttarsaften, plus 1 May and 17 May WHEN THEY FALL ON A WEEKDAY. The six movable "
            "days come from the Gregorian computus. Norwegian law has no weekend substitution, "
            "so the trading-day count varies year to year.",
    "function": "countries.no.pack:holidays",
    "table": {y: _iso(holidays(y)) for y in (2024, 2025, 2026)},
    "fellesferie": {y: [d.isoformat() for d in fellesferie(y)] for y in (2024, 2025, 2026)},
    "asymmetries": (
        "SKJAERTORSDAG: Oslo closed, Xetra and Euronext Paris and Nasdaq Stockholm and London "
        "all open. One guaranteed one-sided session every year in any spread with a Norwegian "
        "leg, and it is the single most reliable calendar asymmetry in this department.",
        "17 May 2026 is a Sunday and 17 May 2024 was a Friday: Constitution Day costs one "
        "session in some years and none in others, with no substitution. A per-year "
        "normalisation must use this function and not 252.",
        "Whit Monday: Oslo and Xetra closed, Euronext open. Ascension: Oslo, Xetra and Nasdaq "
        "Stockholm closed, Euronext open. Three European answers to two days, again.",
        "Fellesferie (weeks 28-30) is NOT a closure. The exchange trades, the information flow "
        "is normal, and the participation is not -- which is exactly what makes it usable.",
    ),
    "status": "DERIVED_FROM_RULE",
    "verified": {"2026-04-02": "Skjaertorsdag 2026, Oslo closed while the rest of Europe trades",
                 "2026-05-17": "Constitution Day on a Sunday -- NOT a closure, by derivation"},
}

CENTRAL_BANK: dict[str, Any] = {
    "name": "Norges Bank",
    "committee": "the Monetary Policy and Financial Stability Committee (five members since 2020, "
                 "a structural change from the earlier Executive Board arrangement)",
    "policy_rates": ("styringsrenten (the policy rate)",),
    "operational_framework": "a quota system for reserve remuneration: banks are remunerated at "
                             "the policy rate up to a quota and below it beyond. That is a second "
                             "instrument which no policy-rate series records, and it is the "
                             "reason NOWA can sit away from the policy rate without any "
                             "announcement having been made.",
    "decision_rule": "EIGHT monetary policy meetings a year, with a Monetary Policy Report "
                     "(Pengepolitisk rapport) at four of them -- March, June, September and "
                     "December. The report meetings carry the published rate path and are the "
                     "larger events; the four interim meetings usually carry a short statement.",
    "announcement_local": "10:00 CET/CEST",
    "announcement_utc": {"winter_cet": "09:00Z", "summer_cest": "08:00Z"},
    "press_conference_local": "10:30 CET/CEST on report days (declared; verify against "
                              "norges-bank.no)",
    "dst_note": "Norway observes CET/CEST on the same switch weekends as the euro area, so the "
                "Oslo-Frankfurt offset is zero all year and the Oslo-London offset a constant "
                "hour. The 10:00 CET announcement lands 45 minutes after the Riksbank's 09:30 "
                "CET one, which matters in the rare weeks both banks decide -- NOKSEK is then a "
                "two-event series inside one morning.",
    "time_change_note": "no known announcement-clock break on this desk's bars. The COMMITTEE "
                        "changed in 2020, which changes the reaction function's authorship but "
                        "not the clock.",
    "reports": "Norges Bank publishes its own rate path in the Monetary Policy Report, like the "
               "Riksbank and unlike the ECB, so the surprise is measurable against the bank's "
               "published prior forecast",
    "decisions": {
        "2024": {"dates": ("2024-01-25", "2024-03-21", "2024-05-03", "2024-06-20", "2024-08-15",
                           "2024-09-19", "2024-11-07", "2024-12-19"),
                 "confidence": "DECLARED from public knowledge, eight meetings with reports in "
                               "March, June, September and December. Verify against "
                               "norges-bank.no before use."},
        "2025": {"dates": ("2025-01-23", "2025-03-27", "2025-05-08", "2025-06-19", "2025-08-14",
                           "2025-09-18", "2025-11-06", "2025-12-18"),
                 "confidence": "DECLARED, UNVERIFIED"},
        "2026": {"dates": (),
                 "confidence": "UNMEASURED. The desk does not hold the 2026 Norges Bank calendar "
                               "and will not invent one. Read norges-bank.no and fill this in, "
                               "or condition on the rule below."},
    },
    "rule_if_dates_unknown": "eight meetings a year, decision at 10:00 CET, with Monetary Policy "
                             "Reports in March, June, September and December; the interim four "
                             "cluster in late January, early May, mid-August and early November.",
    "fx_operations": "SEPARATE FROM POLICY AND FAR MORE IMPORTANT FOR THE KRONE. Norges Bank "
                     "announces the DAILY amount of foreign currency it will buy or sell on "
                     "behalf of the state for the coming month, before that month begins. This "
                     "is a scheduled, sized, one-way, publicly announced FX flow -- unique in "
                     "G10 -- and it is carried as its own fixing convention and its own domain.",
    "source": "https://www.norges-bank.no/en/topics/Monetary-policy/",
}

FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "Norges Bank daily foreign exchange transactions for the state (the announced "
             "daily amount)",
     "administrator": "Norges Bank",
     "local_time": "ANNOUNCED on or about the last business day of the preceding month; the "
                   "transactions themselves are executed through the following month",
     "utc": {"winter": "the announcement is a press release rather than a clocked fix; the desk "
                       "does NOT hold its intraday time",
             "summer": "same -- UNMEASURED, read it off the release timestamp"},
     "dst_note": "CET/CEST for the execution month's Norwegian business days. THE INTRADAY "
                 "ANNOUNCEMENT TIME IS UNMEASURED BY THIS PACK and must be taken from the "
                 "release's own timestamp rather than assumed: an event study that assumes a "
                 "time is studying a window it chose, not the one the market saw (L1.28a).",
     "window": "a fixed daily amount, executed across the month on Norwegian business days",
     "what_it_prices": "the conversion of the state's petroleum revenue into or out of krone",
     "why_it_matters": "THE CENTRAL OBSERVABLE OF THIS PACK. No other G10 central bank publishes "
                       "the size of its daily currency operations a month in advance. The "
                       "ANNOUNCEMENT is an event (a change in the daily amount is news) and the "
                       "EXECUTION is a flow (a month of one-way, price-insensitive orders). They "
                       "have different dates and an edge that conflates them measures neither."},
    {"name": "Norges Bank daily exchange rates",
     "administrator": "Norges Bank",
     "local_time": "struck around 16:00 CET/CEST and published shortly after",
     "utc": {"winter": "15:00Z", "summer": "14:00Z"},
     "dst_note": "CET/CEST; Norwegian business days only, so the series has holes on "
                 "Skjaertorsdag and 17 May that a euro series does not. Confidence: the 16:00 "
                 "CET timing is declared; verify against norges-bank.no before tick-level use.",
     "window": "a snapshot",
     "what_it_prices": "the krone for statistical and accounting purposes",
     "why_it_matters": "the domestic reference, one hour before the 16:00 London WMR fix in "
                       "winter terms; index flow goes through the London one and not this one"},
    {"name": "NIBOR",
     "administrator": "Norske Finansielle Referanser",
     "local_time": "published around 12:00 CET/CEST",
     "utc": {"winter": "11:00Z", "summer": "10:00Z"},
     "dst_note": "CET/CEST, Norwegian banking days. Confidence: the 12:00 CET publication is "
                 "declared; verify against the NoRe methodology.",
     "window": "panel submissions",
     "what_it_prices": "term krone funding -- but NIBOR IS CONSTRUCTED FROM A DOLLAR RATE AND "
                       "THE FORWARD POINTS rather than from krone deposits. That makes it the "
                       "only Nordic benchmark that carries dollar funding stress directly into "
                       "domestic mortgage pricing.",
     "why_it_matters": "a dollar squeeze raises Norwegian mortgage rates through the fixing's "
                       "own construction, with no Norwegian event having occurred -- a "
                       "mechanical channel that is testable and mostly untested"},
    {"name": "NOWA",
     "administrator": "Norges Bank",
     "local_time": "published the following banking day, around 10:00 CET/CEST",
     "utc": {"winter": "09:00Z", "summer": "08:00Z"},
     "dst_note": "CET/CEST, T+1 on Norwegian banking days; the Easter gap is four days long "
                 "because of Skjaertorsdag, which shows as a spurious jump in a naive daily "
                 "difference.",
     "window": "volume-weighted overnight unsecured transactions",
     "what_it_prices": "actual overnight krone borrowing",
     "why_it_matters": "NOWA minus the policy rate reveals when the reserve QUOTA is binding, "
                       "which is an easing or tightening that the policy-rate series never shows"},
    {"name": "WM/Refinitiv 16:00 London closing spot rate",
     "administrator": "LSEG (WM/Refinitiv)", "local_time": "16:00 London",
     "utc": {"winter": "16:00Z", "summer": "15:00Z"},
     "dst_note": "GMT/BST on the same switch weekends as CET/CEST; a constant one-hour offset "
                 "from Oslo all year.",
     "window": "15:57:30-16:02:30 London",
     "what_it_prices": "the benchmark index funds convert krone exposure at",
     "why_it_matters": "NOK's index weight is small and its turnover is smaller, so a given "
                       "month-end index flow is a LARGER share of krone liquidity than of "
                       "krona or euro liquidity -- the thinness is the mechanism"},
)

SETTLEMENT_CONVENTIONS: dict[str, Any] = {
    "fx_spot": "T+2 for EURNOK and USDNOK; the value date must be good in both currencies, so a "
               "Norwegian-only closure (Skjaertorsdag, 17 May) pushes the krone leg alone",
    "fx_value_date_note": "Skjaertorsdag plus Good Friday plus Easter Monday makes a FOUR-DAY "
                          "Norwegian settlement break every spring, one day longer than the "
                          "euro's. The krone's Easter forward points therefore price an extra "
                          "day of carry that the euro's do not, on dates this module derives.",
    "cls": "NOK settles in CLS; the CHFNOK and GBPNOK legs are CLS-eligible on both sides",
    "cash_equity": "T+2 on Euronext Oslo; Norway is expected to follow the EU timetable to T+1 "
                   "on 11 October 2027 (declared -- verify against Euronext and the Norwegian "
                   "FSA, since Norway is EEA rather than EU and its adoption is not automatic)",
    "bonds": "T+2 through Euronext Securities Oslo (VPS)",
    "derivatives": "OBX futures and options are cash-settled; the expiry rule is a THURSDAY one "
                   "and is DECLARED rather than verified in this pack",
    "month_end": "the Norges Bank daily FX amount for the NEXT month is announced at the end of "
                 "the current one, so Norway has a month-end EVENT that is about the month "
                 "ahead -- distinct from the month-end index rebalancing flow, and easy to "
                 "confound with it",
}

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Euronext Oslo Bors", "mic": "XOSL", "tz": "Europe/Oslo",
     "symbols": (),
     "session_local": "09:00-16:20 CET continuous, closing auction 16:20-16:25",
     "expiry_rule": "the THIRD THURSDAY of the expiry month, rolled back over closures. "
                    "CONFIDENCE: DECLARED, NOT VERIFIED. Oslo's index derivatives expire on a "
                    "Thursday rather than the European third Friday; `obx_expiry` computes the "
                    "declared rule and the pack flags it so no session mistakes it for a "
                    "checked fact.",
     "settlement_price_rule": "OBX derivatives settle against an index average on the expiry "
                              "day. Declared; verify against the Euronext Oslo specification.",
     "witching": "the quarterly cycle, one day earlier in the week than the rest of Europe",
     "notes": "NO EXECUTABLE SYMBOL for the index -- but XBRUSD is executable and carries most "
              "of OSEBX's variance, which makes Norway the only country here whose equity beta "
              "has a tradable proxy that is not an index"},
)

POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "NO CFTC POSITIONING SERIES FOR THE KRONE -- declared absence",
     "covers": "nothing. NOK has no CFTC-reportable futures contract with a usable position "
               "series, exactly as with SEK, PLN, CZK, HUF and DKK.",
     "published": "never", "lag_days": 0.0, "licence": "n/a", "root": "n/a",
     "note": "A DECLARED GAP. Every Norwegian crowding hypothesis here is UNMEASURED on "
             "positioning (L1.28a). Using EUR or even SEK positioning as a stand-in would be "
             "inventing a measurement; the pack names the substitutes and their defects instead."},
    {"name": "Norges Bank announced daily FX transaction amount",
     "covers": "the state's own krone flow, sized and scheduled",
     "published": "monthly, before the month it applies to", "lag_days": 0.0,
     "licence": "public", "root": "https://www.norges-bank.no/en/news-events/news-publications/",
     "note": "not positioning in the speculative sense and far better than it: a known, sized, "
             "one-way flow announced in advance. It is the reason this pack has a forced-flow "
             "domain that does not depend on inference."},
    {"name": "NBIM quarterly and annual reporting",
     "covers": "the Government Pension Fund Global's holdings and its rebalancing",
     "published": "quarterly, a few weeks after quarter end", "lag_days": 25.0,
     "licence": "public", "root": "https://www.nbim.no/",
     "note": "NBIM publishes its full holdings annually -- unusual transparency. The REBALANCING "
             "rule between equities and fixed income is public, which makes the fund's largest "
             "flows conditionally predictable from market returns alone."},
    {"name": "Oslo Bors / Euronext short-selling register and open interest",
     "covers": "disclosed short positions and index derivative open interest",
     "published": "daily", "lag_days": 1.0, "licence": "public",
     "root": "https://ssr.finanstilsynet.no/",
     "note": "the Norwegian FSA runs a public short-sale register. It is equity ground and "
             "therefore not hypothesis material under the two-lane order; it is carried as an "
             "observable for the risk-regime conditioning only."},
)

NATIVE_LANGUAGES: tuple[str, ...] = ("nb", "en")

#: Norwegian (bokmal) market vocabulary. `fellesferie`, `seks ukers varsel` and `handlingsregelen`
#: have no English equivalent a search engine will match, which is why they are here.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "nb_policy": ("Norges Bank", "styringsrenten", "rentebeslutning", "rentemøte",
                  "Pengepolitisk rapport", "rentebanen", "komiteen for pengepolitikk og "
                  "finansiell stabilitet", "inflasjonsmålet", "kvotesystemet",
                  "foliorenten"),
    "nb_fx": ("kronekursen", "kronesvekkelse", "kronestyrking", "valutakjøp", "valutasalg",
              "daglige valutatransaksjoner", "importveid kursindeks", "I-44",
              "valutareserver", "sikring"),
    "nb_fund": ("oljefondet", "Statens pensjonsfond utland", "SPU", "NBIM",
                "handlingsregelen", "oljepengebruk", "strukturelt oljekorrigert underskudd",
                "rebalansering", "nasjonalbudsjettet", "statsbudsjettet"),
    "nb_rates": ("NIBOR", "NOWA", "tremaneders NIBOR", "statsobligasjon", "statskasseveksel",
                 "påslag", "rentemargin", "obligasjon med fortrinnsrett", "OMF"),
    "nb_market": ("Oslo Børs", "OBX", "OSEBX", "bortfall", "forfall", "sluttauksjon",
                  "børsdag", "skjærtorsdag", "Grunnlovsdagen", "fellesferie",
                  "utbytte", "eks-utbytte"),
    "nb_housing": ("boliglån", "flytende rente", "fastrente", "seks ukers varsel",
                   "boligprisindeks", "Eiendom Norge", "gjeldsgrad", "utlånsforskriften",
                   "avdragsfrihet"),
    "nb_macro": ("SSB", "konsumprisindeksen", "KPI-JAE", "arbeidsledighet", "NAV",
                 "regionalt nettverk", "oljeinvesteringer", "petroleumsvirksomheten",
                 "laksepris", "sjømateksport"),
    "en_desk": ("the announced daily amount", "the fiscal rule", "the oil fund", "the six-week "
                "notice", "the common holiday", "Maundy Thursday closure", "no COT for NOK"),
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
    _src("no.official.norgesbank",
         "Norges Bank decisions, reports, statistics and THE FX transaction announcements",
         layer="official",
         roots=("https://www.norges-bank.no/en/topics/Monetary-policy/",
                "https://www.norges-bank.no/en/news-events/news-publications/",
                "https://www.norges-bank.no/en/topics/Statistics/",
                "https://www.norges-bank.no/tema/pengepolitikk/Rentemoter/"),
         languages=("nb", "en"), licence="public, attribution",
         access_label="OPEN_DATA", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         weight=1.0,
         queries=("daglige valutakjøp for staten neste måned beløp",
                  "valutatransaksjoner på vegne av staten pressemelding",
                  "rentebeslutning styringsrenten pengepolitisk rapport rentebanen",
                  "regionalt nettverk rapport bedriftsintervjuer"),
         notes="THE MONTHLY FX TRANSACTION ANNOUNCEMENT IS A PLAIN PRESS RELEASE ON THE NEWS "
               "PAGE and it is the single most valuable document this pack points at: a "
               "scheduled, sized, one-way currency operation published before the month it "
               "applies to, which no other G10 central bank does. Regionalt nettverk is a "
               "structured firm-interview panel with no Nordic equivalent."),
    _src("no.official.state",
         "NBIM, the Ministry of Finance, Statistics Norway, the FSA and the Offshore Directorate",
         layer="official",
         roots=("https://www.nbim.no/", "https://www.regjeringen.no/en/dep/fin/",
                "https://www.ssb.no/en/", "https://www.finanstilsynet.no/en/",
                "https://www.sodir.no/en/"),
         languages=("nb", "en"), licence="public, attribution",
         access_label="OPEN_DATA", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         weight=1.0,
         queries=("handlingsregelen strukturelt oljekorrigert underskudd nasjonalbudsjettet",
                  "oljefondet rebalansering regel aksjeandel",
                  "konsumprisindeksen KPI-JAE månedsutgivelse klokka åtte",
                  "investeringsundersøkelsen olje og gass anslag"),
         notes="NBIM publishes its ENTIRE holdings annually and its rebalancing RULE publicly, "
               "which makes the fund's largest flows conditionally predictable from public "
               "returns alone. SSB's petroleum investment survey is a forward-looking capex "
               "series whose REVISION, not level, is the signal."),
    _src("no.institutional.venue_and_bodies",
         "Euronext Oslo, the NIBOR administrator and the Norwegian industry bodies",
         layer="institutional",
         roots=("https://live.euronext.com/en/markets/oslo",
                "https://www.referanserenter.no/", "https://www.finansnorge.no/",
                "https://vff.no/"),
         languages=("nb", "en"), licence="public page, restricted redistribution",
         access_label="PUBLIC_WITH_TERMS", credibility="AUTHORITATIVE",
         predictive_state="UNTESTED", weight=1.0,
         queries=("OBX derivater bortfall tredje torsdag kontraktsspesifikasjon",
                  "NIBOR fastsettelse metodikk Norske Finansielle Referanser",
                  "Finans Norge boliglånsundersøkelse rentestatistikk",
                  "seks ukers varsel renteendring boliglån regel"),
         notes="referanserenter.no is the NIBOR administrator and the only authority on NIBOR's "
               "CONSTRUCTION -- which is a dollar rate plus forward points and is the mechanism "
               "behind domain NO-H. The OBX Thursday expiry rule in this pack is DECLARED and "
               "must be re-read from the Euronext Oslo specification here."),
    _src("no.academic.research", "Norges Bank working papers, SSB discussion papers, NHH and BI",
         layer="academic",
         roots=("https://www.norges-bank.no/en/news-events/news-publications/Papers/"
                "Working-Papers/",
                "https://www.ssb.no/en/forskning/discussion-papers",
                "https://www.nhh.no/en/research/", "https://www.bi.edu/research/"),
         languages=("nb", "en"), licence="public, attribution",
         access_label="PUBLIC", credibility="RELIABLE", predictive_state="UNTESTED", weight=0.9,
         queries=("Norges Bank working paper krone liquidity premium exchange rate",
                  "kronekursen svak forklaring analyse arbeidsnotat",
                  "oljepris kronekurs sammenheng empirisk studie",
                  "boliglånsrente overveltning styringsrente studie"),
         notes="Norges Bank's own papers describe the krone's liquidity premium and the fund's "
               "FX conversion better than any commentary does, and they are the only serious "
               "public attempt to explain the 2022-2025 structural weakness that the folk "
               "terms-of-trade model gets backwards."),
    _src("no.practitioner.bank_research",
         "Norwegian and Nordic bank strategy notes and the professional community",
         layer="practitioner",
         roots=("https://www.dnb.no/dnbnyheter/no/markets",
                "https://research.nordea.com/",
                "https://www.handelsbanken.no/no/om-oss/makro-og-marked",
                "https://www.cfa.no/"),
         languages=("nb", "en"), licence="mixed: public commentary, licensed full notes",
         access_label="ACCESS_UNCLEAR", credibility="RELIABLE", predictive_state="UNTESTED",
         weight=0.6,
         queries=("rentebeslutning kommentar Norges Bank forventning analytiker",
                  "kronekurs prognose EURNOK analyse",
                  "valutakjøp effekt krone kommentar",
                  "boliglånsrente prognose bank analyse"),
         notes="DNB Markets is the dominant NOK price-maker and its public commentary is the "
               "closest thing to a published dealer view of the announced-amount flow in domain "
               "NO-A. ACCESS_UNCLEAR: public commentary and licensed notes share a site."),
    _src("no.retail_ecology.communities", "Norwegian retail investor forums and communities",
         layer="retail_ecology",
         roots=("https://www.hegnar.no/forum", "https://www.nordnet.no/blogg",
                "https://www.reddit.com/r/aksjer/",
                "https://www.reddit.com/r/norge/"),
         languages=("nb",), licence="public forum, quote-and-cite only",
         access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE", predictive_state="UNTESTED",
         weight=0.25, machine_use_allowed=True,
         queries=("hvorfor er kronen så svak diskusjon",
                  "fastrente eller flytende boliglån diskusjon",
                  "oljefondet rebalansering spekulasjon forum",
                  "fellesferie børsen tynn handel"),
         notes="machine_use_allowed=True: Hegnar's forum terms forbid automated extraction, so "
               "it is REGISTERED and never scraped. Kept at weight 0.25: 'why is the krone so "
               "weak' has been a live Norwegian public argument for three years and the "
               "folk-model consensus in it is exactly what domain NO-C exists to falsify."),
    _src("no.app_ecosystem.platforms", "Norwegian broker and banking platforms",
         layer="app_ecosystem",
         roots=("https://www.nordnet.no/", "https://www.dnb.no/privat/sparing-og-investering",
                "https://kron.no/", "https://www.tradingview.com/symbols/OSL-OBX/"),
         languages=("nb", "en"), licence="per-platform terms",
         access_label="PUBLIC_WITH_TERMS", credibility="UNKNOWN",
         predictive_state="NARRATIVE_FEATURE", weight=0.4,
         queries=("Nordnet mest kjøpte aksjer i dag Norge",
                  "Shareville mest eide Norge statistikk",
                  "beste boliglånsrente sammenligning finansportalen"),
         notes="Finansportalen (the FSA's own price-comparison site, reachable from the "
               "official layer) is the regulated analogue of this layer and is the one with a "
               "real predictive claim: it publishes every lender's advertised mortgage rate, "
               "which is where the six-week notice in domain NO-D becomes visible."),
    _src("no.media.business_press", "Norwegian business press",
         layer="media",
         roots=("https://e24.no/", "https://www.dn.no/", "https://www.finansavisen.no/",
                "https://www.nrk.no/okonomi/"),
         languages=("nb",), licence="paywalled; terms forbid bulk extraction",
         access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
         predictive_state="NARRATIVE_FEATURE", weight=0.5, machine_use_allowed=True,
         queries=("Norges Bank valutakjøp neste måned nyhet",
                  "kronekursen svakeste på flere år analyse",
                  "oljefondet verdi rekord nyhet",
                  "boligprisene Eiendom Norge månedstall"),
         notes="machine_use_allowed=True for DN and Finansavisen, both hard paywalls with terms "
               "forbidding bulk extraction; E24 and NRK are more open but are registered under "
               "the same label for consistency and read only through compliant routes. E24 is "
               "the one that reliably reports the monthly FX-amount press release."),
    _src("no.archive.historical", "Norwegian historical monetary statistics and digitised press",
         layer="archive",
         roots=("https://www.norges-bank.no/en/topics/Statistics/Historical-monetary-statistics/",
                "https://www.nb.no/", "https://www.ssb.no/en/statbank",
                "https://web.archive.org/"),
         languages=("nb", "en"), licence="public archive",
         access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         weight=0.8,
         queries=("Norges Bank historiske monetære statistikk 1819 renter valutakurser",
                  "nb.no digitalisert avis børs krone historisk",
                  "valutakjøp pressemelding arkiv 2014 2015"),
         notes="Norges Bank's historical monetary statistics run back to 1819 and nb.no has "
               "digitised essentially the entire Norwegian press. THE ARCHIVE IS HOW THE "
               "ANNOUNCED-AMOUNT SERIES IS BUILT: the monthly press releases are individual "
               "pages and the historical ones are only reachable through the archive, so "
               "reconstructing the series at all is an archive job before it is a data job."),
    _src("no.physical_economy.petroleum_power_seafood",
         "Norwegian petroleum production, pipeline gas flows, power and seafood",
         layer="physical_economy",
         roots=("https://www.sodir.no/en/", "https://www.gassco.no/",
                "https://www.nordpoolgroup.com/", "https://www.statnett.no/",
                "https://www.nve.no/", "https://www.fishpool.eu/"),
         languages=("nb", "en"), licence="public",
         access_label="OPEN_DATA", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         weight=0.9,
         queries=("Gassco gasstrømmer til Europa sanntid rørledning",
                  "sokkeldirektoratet produksjonstall måned felt",
                  "NVE magasinstatistikk fyllingsgrad uke",
                  "Fish Pool lakspris spot uke"),
         notes="Gassco publishes pipeline gas flows to Europe in near real time and NVE "
               "publishes weekly reservoir fill. Both are free, physical and revision-free. The "
               "salmon spot index is here because it is a terms-of-trade variable UNCORRELATED "
               "with oil, which makes it the ideal control for the oil channel in domain NO-C."),
    _src("no.source_graph.citation_and_link", "Citation and link graphs over the Norwegian corpus",
         layer="source_graph",
         roots=("https://ideas.repec.org/s/bno/worpap.html", "https://openalex.org/",
                "https://www.nb.no/search", "https://github.com/search?q=NIBOR+OR+NOWA"),
         languages=("nb", "en"), licence="open data",
         access_label="OPEN_DATA", credibility="RELIABLE", predictive_state="UNTESTED",
         weight=0.5,
         queries=("RePEc cited by Norges Bank working paper krone",
                  "OpenAlex citations petroleum fund fiscal rule Norway",
                  "github norwegian trading calendar skjærtorsdag"),
         notes="used to find what this pack has NOT named. The GitHub query is concrete: "
               "Skjaertorsdag is the calendar trap in every Nordic library and somebody has "
               "already got it right or wrong in public."),
)

#: All ten layers are populated for Norway, so this table is empty BY MEASUREMENT.
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
    _ds("Norges Bank announced daily FX transactions for the state",
        source="Norges Bank press releases",
        coverage="the daily NOK amount bought or sold for the state, per month",
        frequency="monthly announcement, daily execution", publication_lag_days=0.0,
        revisions="the amount for a month is occasionally CHANGED mid-month, and that change is "
                  "itself an announcement and a second event; a series that keeps only the "
                  "latest value per month destroys exactly the observations worth having",
        licence="public", history_from="2014 (the modern announced-amount regime)",
        pit_feasible=True, assets=("EURNOK", "USDNOK", "NOKSEK"),
        mechanism_families=("announced_flow", "forced_flow", "central_bank_flow"),
        how_to_fetch="norges-bank.no news page, one press release per month",
        pit={"event_time": "the ANNOUNCEMENT, on or about the last business day of the preceding "
                           "month. The desk does NOT hold its intraday time -- read it off the "
                           "release timestamp rather than assuming one.",
             "period_time": "the calendar month the daily amount applies to",
             "publication_time": "the announcement date",
             "available_time": "the announcement date -- BEFORE the flow starts, which is what "
                               "makes this the rarest kind of observable: a forced flow that is "
                               "knowable in advance",
             "revision_time": "a mid-month change, announced separately",
             "retrieval_time": "crawler stamp"}),
    _ds("Norges Bank policy decisions and the published rate path",
        source="Norges Bank", coverage="every Norwegian policy decision",
        frequency="8 per year, 4 with a Monetary Policy Report", publication_lag_days=0.0,
        revisions="the decision is never revised; the rate path is re-published quarterly and "
                  "both vintages must be kept",
        licence="public, attribution", history_from="1999", pit_feasible=True,
        assets=("EURNOK", "USDNOK", "NOKSEK"),
        mechanism_families=("policy_surprise", "path_revision", "event_drift"),
        how_to_fetch="norges-bank.no press release and report pages",
        pit={"event_time": "10:00 CET announcement",
             "period_time": "the forecast horizon the path covers",
             "publication_time": "10:00 CET",
             "available_time": "10:00 CET -- 30 minutes after the Riksbank's 09:30 CET, which "
                               "makes NOKSEK a two-event series on the rare shared mornings",
             "revision_time": "never for the decision",
             "retrieval_time": "crawler stamp"}),
    _ds("Norwegian petroleum production and pipeline gas flows",
        source="Offshore Directorate (Sokkeldirektoratet) and Gassco",
        coverage="production by field; gas export flows to Europe",
        frequency="monthly production, near-real-time flows", publication_lag_days=20.0,
        revisions="production figures are revised for months afterwards; the FLOW data is "
                  "operational and essentially final",
        licence="public", history_from="1971 (production), 2010s (flow portal)",
        pit_feasible=True, assets=("EURNOK", "USDNOK", "XBRUSD", "XNGUSD"),
        mechanism_families=("terms_of_trade", "physical_flow", "supply_shock"),
        how_to_fetch="sodir.no monthly statistics; Gassco flow portal",
        pit={"event_time": "the production or flow month",
             "period_time": "the calendar month, or the gas day for flows",
             "publication_time": "around the 20th for production; continuous for flows",
             "available_time": "same",
             "revision_time": "production is revised repeatedly; flows are not",
             "retrieval_time": "crawler stamp"}),
    _ds("Eiendom Norge house price index",
        source="Eiendom Norge", coverage="Norway, national and by city", frequency="monthly",
        publication_lag_days=5.0,
        revisions="seasonal adjustment is re-estimated; the nominal index is stable",
        licence="public headline", history_from="2003", pit_feasible=True,
        assets=("EURNOK", "USDNOK"),
        mechanism_families=("housing_channel", "policy_transmission"),
        how_to_fetch="eiendomnorge.no monthly release, early in the following month",
        pit={"event_time": "the transaction month",
             "period_time": "the calendar month",
             "publication_time": "the first days of the following month -- among the fastest "
                                 "housing prints in Europe",
             "available_time": "same",
             "revision_time": "seasonal re-estimation",
             "retrieval_time": "crawler stamp"}),
    _ds("Statistics Norway CPI and CPI-ATE",
        source="SSB", coverage="Norway", frequency="monthly", publication_lag_days=10.0,
        revisions="not routinely revised; weights updated annually",
        licence="public, attribution", history_from="1920", pit_feasible=True,
        assets=("EURNOK", "USDNOK"),
        mechanism_families=("data_surprise", "policy_expectation"),
        how_to_fetch="ssb.no statistics bank, 08:00 CET release",
        pit={"event_time": "08:00 CET release",
             "period_time": "the reference month",
             "publication_time": "08:00 CET around the 10th",
             "available_time": "08:00 CET",
             "revision_time": "annual reweighting",
             "retrieval_time": "crawler stamp"}),
    _ds("SSB petroleum investment survey",
        source="Statistics Norway", coverage="planned oil and gas capital expenditure",
        frequency="quarterly", publication_lag_days=0.0,
        revisions="each survey REVISES the prior estimate for the same year, and the revision is "
                  "the signal -- a level read of this series is meaningless",
        licence="public", history_from="1985", pit_feasible=True,
        assets=("EURNOK", "XBRUSD"),
        mechanism_families=("investment_cycle", "terms_of_trade", "survey_surprise"),
        how_to_fetch="ssb.no quarterly release",
        pit={"event_time": "the survey release",
             "period_time": "the investment YEAR being estimated, which is ahead of the survey",
             "publication_time": "quarterly, 08:00 CET",
             "available_time": "same",
             "revision_time": "every subsequent survey for the same target year",
             "retrieval_time": "crawler stamp"}),
    _ds("NBIM Government Pension Fund Global reporting",
        source="Norges Bank Investment Management",
        coverage="fund value, returns, allocation and (annually) full holdings",
        frequency="quarterly and annual", publication_lag_days=25.0,
        revisions="restated with valuation; the ALLOCATION and the rebalancing rule are stable",
        licence="public", history_from="1998", pit_feasible=True,
        assets=("EURNOK", "USDNOK", "USDX"),
        mechanism_families=("forced_flow", "rebalancing", "sovereign_wealth"),
        how_to_fetch="nbim.no reports",
        pit={"event_time": "quarter end",
             "period_time": "the quarter",
             "publication_time": "a few weeks after quarter end",
             "available_time": "same",
             "revision_time": "valuation restatement",
             "retrieval_time": "crawler stamp"}),
    _ds("NIBOR and NOWA",
        source="Norske Finansielle Referanser and Norges Bank",
        coverage="Norwegian term and overnight rates", frequency="daily on banking days",
        publication_lag_days=0.0,
        revisions="not revised; NIBOR's METHODOLOGY has changed and that is a series break",
        licence="licensed (NIBOR) / public (NOWA)", history_from="1986 (NIBOR), 2011 (NOWA)",
        pit_feasible=True, assets=("EURNOK", "USDNOK"),
        mechanism_families=("funding", "dollar_stress", "policy_transmission"),
        how_to_fetch="NoRe daily publication; norges-bank.no for NOWA",
        pit={"event_time": "the fixing day",
             "period_time": "the term the rate prices",
             "publication_time": "around 12:00 CET (NIBOR), 10:00 CET T+1 (NOWA)",
             "available_time": "same",
             "revision_time": "methodology breaks only",
             "retrieval_time": "crawler stamp"}),
    _ds("Norges Bank Regionalt nettverk (regional network survey)",
        source="Norges Bank", coverage="a structured interview panel of Norwegian firms",
        frequency="quarterly", publication_lag_days=0.0,
        revisions="none; each round is a fresh panel reading",
        licence="public", history_from="2002", pit_feasible=True,
        assets=("EURNOK", "USDNOK"),
        mechanism_families=("survey_surprise", "regime_condition"),
        how_to_fetch="norges-bank.no publication page",
        pit={"event_time": "the publication, which accompanies or precedes a report meeting",
             "period_time": "the interview window, several weeks earlier",
             "publication_time": "quarterly",
             "available_time": "same",
             "revision_time": "never",
             "retrieval_time": "crawler stamp"}),
)


def actors() -> tuple[dict[str, Any], ...]:
    """Thirteen Norwegian participants whose constraints produce dated or measurable flow."""
    return (
        actor("Norges Bank's FX transaction desk (on behalf of the state)",
              holds="the obligation to convert the state's petroleum cash flow",
              forced_to=("announce the DAILY amount for the coming month before it starts",
                         "execute that amount every Norwegian business day regardless of level",
                         "announce any mid-month change separately"),
              when="announced on or about the last business day of the preceding month; executed "
                   "daily through the following month",
              information=("the state's petroleum revenue", "the fiscal rule's withdrawal",
                           "the budget's structural non-oil deficit"),
              constraints=("the amount follows from the budget arithmetic, not from a view on "
                           "the krone; it is price-insensitive by design",),
              instruments=("EURNOK", "USDNOK", "NOKSEK"),
              counterparties=("bank FX desks", "the krone market as a whole"),
              observables=("the monthly press release with the daily amount",
                           "changes in the amount, which are the news",
                           "the amount's size relative to daily krone turnover"),
              impact="a known, sized, one-way flow running every business day for a month. The "
                     "ANNOUNCEMENT is an event and the EXECUTION is a flow; they have different "
                     "dates and different signs of evidence",
              persistence="the month",
              falsifier="if EURNOK shows no relation to the MONTH-ON-MONTH CHANGE in the "
                        "announced daily amount across the sample, an announced central-bank "
                        "flow of this relative size does not move the price, and the pack's "
                        "central claim is wrong",
              notes="unique in G10. No other central bank publishes the size of tomorrow's "
                    "currency operation, let alone the next twenty of them"),
        actor("Norges Bank Investment Management (the oil fund)",
              holds="the largest single pool of capital in the world relative to its economy",
              forced_to=("rebalance between equities and fixed income when the weights drift "
                         "past a published band",
                         "publish holdings annually and results quarterly",
                         "receive or return cash according to the fiscal rule"),
              when="rebalancing is rule-driven and therefore conditionally predictable from "
                   "market returns alone",
              information=("its own benchmark and bands", "market returns"),
              constraints=("a mandate that forces contrarian rebalancing: a large equity "
                           "drawdown makes the fund a mechanical BUYER of equities",),
              instruments=("USDX", "EURNOK", "USDNOK"),
              counterparties=("global equity and bond markets", "the Ministry of Finance"),
              observables=("quarterly reports", "the published rebalancing rule",
                           "cumulative market returns against the band"),
              impact="a globally significant, rule-driven, contrarian flow whose TRIGGER is "
                     "computable in advance from public returns",
              persistence="episodic, triggered by drawdowns",
              falsifier="if global equity markets show no abnormal behaviour in the windows where "
                        "the published band would have been breached, the fund's rebalancing is "
                        "either pre-hedged or too small to see, and the flow story is decorative",
              notes="a rule-driven flow whose trigger is public is the rarest object in this "
                    "department and the fund has one"),
        actor("Norwegian households with floating mortgages under the six-week notice rule",
              holds="high household debt at a floating rate that CANNOT be raised without six "
                    "weeks' individual written notice",
              forced_to=("accept the increase after the statutory notice period",
                         "meet the lending regulation's debt-to-income and stress-test limits "
                         "when borrowing"),
              when="six weeks after each lender decides, which is after each policy change",
              information=("the lender's notice letter", "NIBOR and the policy rate"),
              constraints=("a STATUTORY delay, not a contractual one. Sweden's reset is "
                           "quarterly and contractual; Norway's is a fixed six-week legal lag "
                           "applied per borrower, which makes the aggregate pass-through a "
                           "smooth, knowable lag structure rather than a quarterly step.",),
              instruments=("EURNOK", "USDNOK"),
              counterparties=("Norwegian banks", "the covered bond market (OMF)"),
              observables=("banks' announced rate changes and their effective dates",
                           "the Eiendom Norge monthly house price index",
                           "SSB household consumption"),
              impact="Norwegian transmission is fast but LAGGED BY A KNOWN CONSTANT, which is a "
                     "cleaner identification than Sweden's continuous reset",
              persistence="quarters",
              falsifier="if the Norwegian house price index responds to the policy rate with the "
                        "same lag profile as the Swedish one, the six-week rule has no "
                        "measurable aggregate effect and the two economies can be pooled after all",
              notes="SE and NO are separate packs largely because of this actor; the comparison "
                    "is the experiment"),
        actor("The Norwegian Ministry of Finance under the fiscal rule",
              holds="the handlingsregelen: a rule limiting the structural non-oil deficit to a "
                    "share of the fund's value",
              forced_to=("present a national budget each October on a fixed calendar",
                         "revise it each May",
                         "set the withdrawal that determines the FX conversion"),
              when="the nasjonalbudsjett in early October and the revised budget in May",
              information=("the fund's value, which moves with global markets",
                           "petroleum revenue forecasts"),
              constraints=("the withdrawal is a share of a fund whose value depends on global "
                           "equity markets, so a global drawdown mechanically tightens Norwegian "
                           "fiscal space with a lag -- a fiscal channel from world equities that "
                           "exists nowhere else",),
              instruments=("EURNOK", "USDNOK"),
              counterparties=("Norges Bank, which executes the conversion",
                              "the Norwegian economy"),
              observables=("the October budget and the May revision, both dated",
                           "the structural non-oil deficit figure",
                           "the fund's value"),
              impact="the fiscal setting determines the announced daily FX amount, so the budget "
                     "is upstream of the krone's largest scheduled flow",
              persistence="a year at a time",
              falsifier="if the announced daily FX amount shows no relation to the budget's "
                        "published withdrawal across years, the fiscal-rule chain is broken "
                        "somewhere and the flow is being set another way",
              notes="this actor is why an unconditional Brent-to-NOK regression is misspecified: "
                    "the rent is captured and sterilised before it reaches the currency"),
        actor("Norwegian petroleum producers and the state's direct interest",
              holds="oil and gas production sold in dollars and euros",
              forced_to=("sell production continuously",
                         "pay a high marginal tax rate, which is what routes the rent to the "
                         "state rather than to the currency"),
              when="continuous; the tax payments are on a published schedule",
              information=("XBRUSD and the TTF gas price", "field production schedules"),
              constraints=("a petroleum tax regime that captures the majority of the marginal "
                           "rent, so a Brent move is a FISCAL event before it is a corporate one",),
              instruments=("XBRUSD", "XTIUSD", "EURNOK", "USDNOK"),
              counterparties=("global crude and European gas buyers", "the Norwegian state"),
              observables=("Offshore Directorate monthly production",
                           "Gassco pipeline flows to Europe, near real time",
                           "the SSB petroleum investment survey"),
              impact="the oil-to-krone channel is indirect and conditional; the direct corporate "
                     "FX flow is much smaller than the gross export value suggests",
              persistence="structural",
              falsifier="if EURNOK's beta to XBRUSD is stable across fiscal regimes and across "
                        "the 2022 gas shock, the conditioning this pack insists on is "
                        "unnecessary and the simple regression was right",
              notes="after 2022 the GAS price matters more than crude, and the gas price the "
                    "desk can trade is the wrong one"),
        actor("Norwegian banks and the NIBOR panel",
              holds="a mortgage book funded partly in dollars and swapped into krone",
              forced_to=("submit to the NIBOR panel",
                         "give six weeks' notice before raising a mortgage rate",
                         "roll covered bond (OMF) funding"),
              when="daily fixing; notice-driven rate changes",
              information=("the dollar funding market", "the forward points"),
              constraints=("NIBOR IS CONSTRUCTED FROM A DOLLAR RATE AND THE FX FORWARD, so a "
                           "dollar squeeze raises Norwegian mortgage funding costs mechanically, "
                           "with no Norwegian event having occurred",),
              instruments=("USDNOK", "EURNOK"),
              counterparties=("Norwegian households", "the dollar funding market"),
              observables=("NIBOR against the policy rate",
                           "the cross-currency basis",
                           "OMF spreads"),
              impact="an imported funding channel: global dollar stress reaches Norwegian "
                     "households through the construction of their own benchmark",
              persistence="episodic, tied to dollar funding stress",
              falsifier="if the NIBOR-to-policy-rate spread shows no relation to a global dollar "
                        "funding stress measure, the construction argument has no empirical bite",
              notes="the single most mechanical and least discussed channel in the Nordic region"),
        actor("Foreign investors in the krone",
              holds="positions in a currency whose turnover is small relative to its economy's "
                    "openness",
              forced_to=("reduce exposure on a global risk shock regardless of Norwegian news",
                         "pay a liquidity premium to enter and exit"),
              when="on global risk events",
              information=("global risk appetite", "the oil price"),
              constraints=("a market thin enough that a modest reallocation is a large move; the "
                           "krone's liquidity premium widens exactly when it is most needed",),
              instruments=("EURNOK", "USDNOK", "NOKJPY"),
              counterparties=("Norwegian banks", "Norges Bank as the residual"),
              observables=("the krone's move on days with no Norwegian news",
                           "bid-ask behaviour in stress",
                           "NOKJPY, which nets two risk-sensitive currencies"),
              impact="the krone weakens in global risk-off beyond what oil or rates explain -- "
                     "the liquidity premium, which is the most robust NOK stylised fact",
              persistence="days, with a slow retracement",
              falsifier="if the krone's largest weekly losses are explained by oil and rate "
                        "differentials alone, there is no separate liquidity premium and the "
                        "thinness story is redundant",
              notes="this actor is why every Norwegian domain needs a global-risk control"),
        actor("Norwegian seafood exporters",
              holds="salmon export revenue in euros and dollars against a krone cost base",
              forced_to=("sell perishable production continuously -- salmon cannot be stored, "
                         "which makes the supply curve genuinely inelastic week to week",
                         "report weekly volumes to the export council"),
              when="weekly, with a published spot price index",
              information=("the Nasdaq salmon index", "biomass and harvest data"),
              constraints=("biological production cycles and a licensing regime that caps "
                           "capacity, so supply cannot respond to price within a year",),
              instruments=("EURNOK",),
              counterparties=("EU and Asian buyers",),
              observables=("the weekly salmon spot index",
                           "SSB seafood export values"),
              impact="Norway's second export and a genuinely independent terms-of-trade variable "
                     "-- uncorrelated with oil, which makes it the ideal control for the oil "
                     "channel",
              persistence="weeks to seasons",
              falsifier="if EURNOK shows no relation to salmon price changes once oil and global "
                        "risk are removed, seafood is too small to matter and the pack should "
                        "stop carrying it",
              notes="its value here is as a CONTROL: a terms-of-trade shock with no oil content"),
        actor("Nordic cross-rate arbitrageurs in NOKSEK",
              holds="relative positions between two similar small open economies",
              forced_to=("mark against two central banks whose calendars rarely align",
                         "handle a 30-minute gap between the two announcements when they do"),
              when="around each Norges Bank (10:00 CET) and Riksbank (09:30 CET) decision",
              information=("both published rate paths", "the oil price, which moves one leg only"),
              constraints=("NOKSEK nets the shared European risk factor, leaving relative policy "
                           "and the oil differential",),
              instruments=("NOKSEK", "EURNOK", "EURSEK", "XBRUSD"),
              counterparties=("Nordic bank FX desks",),
              observables=("the two policy paths",
                           "XBRUSD, which is the Norwegian-only driver",
                           "the 30-minute window between the two announcements"),
              impact="the cleanest relative-policy pair in Europe, with one named confound (oil) "
                     "that is itself executable and can therefore be controlled directly",
              persistence="weeks to months",
              falsifier="if NOKSEK's variance is not materially lower than EURNOK's after "
                        "removing a common European factor and oil, the netting fails",
              notes="the Swedish pack carries the mirror of this actor"),
        actor("Statnett and the Norwegian power system",
              holds="a hydro-dominated system with five price areas and cables to Germany, "
                    "Denmark, the Netherlands and the United Kingdom",
              forced_to=("dispatch against reservoir levels and cable capacity",
                         "publish flows and area prices"),
              when="continuous, seasonal in reservoir filling",
              information=("hydrological balance", "continental and UK power prices"),
              constraints=("the interconnectors COUPLE southern Norwegian power to continental "
                           "prices and leave the north decoupled, which turned a domestic "
                           "resource into an imported price after 2021 -- and into a political "
                           "issue that constrains future policy",),
              instruments=("GER40", "UK100", "EURNOK"),
              counterparties=("Nord Pool", "continental and UK buyers"),
              observables=("NO1-NO5 area prices and their spread",
                           "reservoir levels",
                           "cable flows"),
              impact="a Norwegian domestic cost shock imported through cables, with a political "
                     "feedback onto energy policy",
              persistence="seasonal and structural",
              falsifier="if NO1 prices show no coupling to German power once hydrology is "
                        "controlled for, the cable channel is not binding and the political "
                        "story is not an economic one",
              notes="no executable Norwegian power leg; GER40 and UK100 carry the shared "
                    "continental component and are therefore controls rather than targets"),
        actor("Euronext Oslo market makers in the OBX complex",
              holds="option books into a THURSDAY expiry",
              forced_to=("hedge continuously", "unwind into an expiry one day earlier in the "
                         "week than the rest of Europe"),
              when="the third Thursday, declared and unverified",
              information=("Euronext open interest", "their own inventory"),
              constraints=("a small index with a heavy energy weight, so the hedging problem is "
                           "closer to an oil book than to an equity one",),
              instruments=("EURNOK", "XBRUSD"),
              counterparties=("Norwegian institutional hedgers",),
              observables=("Euronext Oslo open interest",
                           "expiry-day behaviour against matched days"),
              impact="a Norwegian expiry that does not coincide with the European third Friday, "
                     "which makes it a control for European expiry studies",
              persistence="the expiry day",
              falsifier="if EURNOK and XBRUSD show nothing on declared OBX expiry days relative "
                        "to matched days, either the rule is wrong or the effect does not reach "
                        "the currency -- and the pack cannot tell which until the rule is verified",
              notes="the expiry RULE ITSELF is DECLARED and unverified; that uncertainty is part "
                    "of the actor and is stated rather than buried"),
        actor("Norwegian life insurers and municipal pension providers",
              holds="krone liabilities with a guaranteed return against a shortage of domestic "
                    "duration",
              forced_to=("meet a guaranteed rate on legacy contracts",
                         "hold foreign bonds hedged into krone because the state barely issues"),
              when="continuous; annual reporting",
              information=("the guaranteed rate", "the krone bond market's depth"),
              constraints=("the fiscal rule means the state has NO net borrowing need, so there "
                           "is almost no domestic duration to buy -- an institutional demand "
                           "with no domestic supply, which is forced into the basis market",),
              instruments=("EURNOK", "USDNOK"),
              counterparties=("cross-currency basis dealers", "foreign sovereign issuers"),
              observables=("the NOK cross-currency basis",
                           "insurer annual reports",
                           "government issuance volume, which is tiny"),
              impact="a structural hedging demand in the krone basis that has no counterpart in "
                     "any normally indebted country",
              persistence="structural",
              falsifier="if the NOK basis shows no relation to domestic issuance volume or "
                        "insurer demand, the scarcity story is wrong and the basis is a "
                        "dollar-side phenomenon",
              notes="the same shape as the Swiss case and for the same reason: a rich sovereign "
                    "that does not need to borrow starves its own institutions of duration"),
        actor("Norwegian retail investors and the fellesferie",
              holds="direct equity and fund exposure, with a pronounced seasonal absence",
              forced_to=("take the common holiday in weeks 28-30, which is a social norm with "
                         "the force of a schedule",),
              when="July, every year",
              information=("Norwegian financial media and the Hegnar forum",),
              constraints=("a national holiday convention that empties the market for three "
                           "weeks while the exchange stays open",),
              instruments=("EURNOK", "USDNOK"),
              counterparties=("Euronext Oslo", "Norwegian brokers"),
              observables=("turnover in weeks 28-30 against the annual average",
                           "forum activity",
                           "realised range in the same weeks"),
              impact="a three-week liquidity treatment with no information confound, the "
                     "Norwegian analogue of the Swedish klamdagar and far longer",
              persistence="annual",
              falsifier="if EURNOK turnover and realised range in weeks 28-30 are "
                        "indistinguishable from the rest of the summer, the fellesferie is a "
                        "social fact with no market content",
              notes="the window is DERIVED from the ISO week rule in this module rather than "
                    "hand-listed, so the sample is reproducible"),
    )


def domains() -> tuple[dict[str, Any], ...]:
    """Eleven research domains, each with negative controls."""
    return (
        domain("NO-A", "The announced daily FX transaction amount",
               objects=("the monthly announcement and its size",
                        "the MONTH-ON-MONTH CHANGE in the daily amount, which is the news",
                        "the execution month as a one-way flow",
                        "mid-month changes, which are separate events"),
               conditions=("the direction and size of the change",
                           "the amount relative to daily krone turnover",
                           "whether the fiscal setting changed in the same period"),
               instruments=("EURNOK", "USDNOK", "NOKSEK"),
               controls=("the announcement date against the execution period: if the effect is "
                         "entirely on the announcement, the flow is pre-priced and there is no "
                         "execution edge",
                         "months where the amount was UNCHANGED, which is the null",
                         "EURSEK over the same window, which shares the Nordic factor and has no "
                         "such programme",
                         "a placebo announcement date one month displaced"),
               notes="the most valuable domain in this pack. A publicly announced, sized, "
                     "one-way, month-long central-bank flow has no analogue in G10."),
        domain("NO-B", "Norges Bank decisions and the published rate path",
               objects=("the 10:00 CET decision",
                        "the quarterly Monetary Policy Report and its rate path",
                        "the Regionalt nettverk survey that precedes report meetings"),
               conditions=("report meeting versus interim meeting",
                           "the sign and size of the path revision",
                           "whether the Riksbank decided the same morning at 09:30 CET"),
               instruments=("EURNOK", "USDNOK", "NOKSEK"),
               controls=("matched non-decision days",
                         "the Riksbank's own 09:30 CET decision, 30 minutes earlier, as the "
                         "separating control on shared mornings",
                         "EURSEK, which shares the Nordic risk factor and not the Norwegian path",
                         "XBRUSD on the same day, since an oil move on a decision day will "
                         "masquerade as a policy reaction"),
               notes="the oil control is mandatory here and is the single most common omission "
                     "in published Norwegian event studies"),
        domain("NO-C", "The conditional oil channel",
               objects=("XBRUSD's relation to EURNOK",
                        "the fiscal rule and the announced daily amount as the conditioning "
                        "variables",
                        "the post-2022 shift from crude to gas"),
               conditions=("the fiscal setting and the size of the announced amount",
                           "before and after the 2022 gas shock",
                           "the global risk regime"),
               instruments=("EURNOK", "USDNOK", "XBRUSD", "XTIUSD", "XNGUSD"),
               controls=("XTIUSD against XBRUSD, to show the effect is about the oil COMPLEX and "
                         "not a Brent-specific basis move",
                         "XNGUSD as the explicit CONTROL for the gas channel -- it is Henry Hub "
                         "and Norway sells into TTF, so a shared move is a global gas move",
                         "the unconditional regression as the declared null: if conditioning on "
                         "the fiscal setting adds nothing, this pack's framing is wrong",
                         "EURSEK, which has the same European beta and no oil"),
               notes="the unconditional Brent-to-NOK regression is the folk model; this domain "
                     "exists to test whether conditioning actually beats it"),
        domain("NO-D", "The six-week statutory notice and the housing channel",
               objects=("banks' announced rate changes and their effective dates",
                        "the Eiendom Norge monthly index, one of Europe's fastest housing prints",
                        "the lending regulation's debt-to-income limits"),
               conditions=("the direction of the policy cycle",
                           "the notice period's fixed lag",
                           "the lending regulation's regime"),
               instruments=("EURNOK", "USDNOK"),
               controls=("SWEDEN as the matched control economy: same housing structure, "
                         "quarterly contractual reset instead of a six-week statutory one. If "
                         "the lag profiles are identical the notice rule has no aggregate effect.",
                         "Germany as the slow-transmission control",
                         "the announcement date against the effective date, which the notice "
                         "rule separates by a constant",
                         "a placebo lag with the lead and lag reversed"),
               notes="SE and NO are separate packs largely for this comparison; running it "
                     "against Sweden is the point"),
        domain("NO-E", "The oil fund's rule-driven rebalancing",
               objects=("the published rebalancing rule and its bands",
                        "cumulative equity-versus-bond drift since the last rebalancing",
                        "the fund's quarterly reports"),
               conditions=("distance from the band",
                           "whether a drawdown has been large enough to trigger",
                           "the fund's size relative to global turnover"),
               instruments=("USDX", "EURNOK", "USDNOK"),
               controls=("windows where the band was approached but not breached, which is the "
                         "natural null",
                         "a placebo band at a different threshold",
                         "other sovereign funds with no published rule, which should show nothing",
                         "the announcement of a rule change versus its application"),
               notes="a flow whose TRIGGER is computable in advance from public returns is very "
                     "rare; whether it is large enough to see is the question"),
        domain("NO-F", "Skjaertorsdag and the Easter settlement break",
               objects=("Maundy Thursday as an Oslo-only closure",
                        "the four-day Norwegian settlement break at Easter",
                        "the krone's Easter forward points"),
               conditions=("Oslo closed while the rest of Europe trades",
                           "the length of the value-date gap",
                           "the year's Easter timing"),
               instruments=("EURNOK", "NOKSEK", "USDNOK", "GER40"),
               controls=("Nasdaq Stockholm and Xetra on the same Thursday, both open, as the "
                         "direct control",
                         "Good Friday, when everyone is shut, as the symmetric case",
                         "turnover as the direct control on the Thursday",
                         "the following Tuesday for the catch-up test"),
               notes="the most reliable calendar asymmetry in this department: one guaranteed "
                     "annual one-sided session, derivable from the computus"),
        domain("NO-G", "The krone's liquidity premium",
               objects=("the krone's move on global risk days with no Norwegian news",
                        "bid-ask and range behaviour in stress",
                        "NOKJPY as the risk-sensitive-versus-haven pair"),
               conditions=("the volatility regime",
                           "whether any Norwegian release occurred",
                           "the direction of the move"),
               instruments=("EURNOK", "USDNOK", "NOKJPY", "NOKSEK"),
               controls=("oil and rate differentials removed first -- the premium is what is "
                         "LEFT, and a study that does not remove them is measuring the oil beta",
                         "EURSEK, a similarly sized but more liquid Nordic currency",
                         "days with a Norwegian release removed",
                         "an asymmetry split, since the premium predicts a larger downside beta"),
               notes="the most robust NOK stylised fact and the easiest to double-count with the "
                     "oil channel"),
        domain("NO-H", "NIBOR's dollar construction as an imported funding channel",
               objects=("NIBOR's spread to the policy rate",
                        "the cross-currency basis",
                        "global dollar funding stress episodes"),
               conditions=("dollar funding stress present or absent",
                           "quarter-end and year-end reporting dates",
                           "the reserve quota's bindingness, visible in NOWA"),
               instruments=("USDNOK", "EURNOK"),
               controls=("STIBOR's spread over the same window: STIBOR is not dollar-constructed, "
                         "so a shared move is a Nordic funding move and not a construction effect",
                         "reporting dates, where balance-sheet effects dominate",
                         "the NOWA-to-policy spread, which isolates the quota rather than the "
                         "dollar",
                         "a period with no dollar stress as the null"),
               notes="mechanical, testable and almost never tested; the Swedish comparison is "
                     "what makes it identifiable"),
        domain("NO-I", "Fellesferie: three weeks of an open market with nobody in it",
               objects=("ISO weeks 28-30",
                        "turnover against the annual average",
                        "realised range and overnight gaps"),
               conditions=("inside versus outside the window",
                           "whether scheduled news fell inside it",
                           "the year"),
               instruments=("EURNOK", "USDNOK", "NOKSEK"),
               controls=("turnover as the direct control: normal turnover means the treatment "
                         "did not apply",
                         "the Swedish klamdagar as the short-duration analogue",
                         "a non-Nordic pair over the same weeks, to separate the Norwegian "
                         "absence from the general European summer",
                         "weeks 27 and 31 as the immediate neighbours"),
               notes="three weeks is long enough to measure and short enough to control; the "
                     "general European summer is the confound and the neighbour weeks remove it"),
        domain("NO-J", "NOKSEK as the relative-policy pair",
               objects=("the two central banks' non-aligned calendars",
                        "the 30-minute gap between 09:30 and 10:00 CET on shared mornings",
                        "oil as the one-sided driver"),
               conditions=("which bank met most recently",
                           "the oil regime",
                           "whether both met the same morning"),
               instruments=("NOKSEK", "EURNOK", "EURSEK", "XBRUSD"),
               controls=("XBRUSD as the mandatory one-sided control",
                         "EURNOK and EURSEK separately, to show the netting removes a common "
                         "factor rather than adding noise",
                         "days when both banks are silent",
                         "the 09:30-10:00 CET window on shared mornings, where the Swedish event "
                         "precedes the Norwegian one and the order is identifiable"),
               notes="the Swedish pack carries the mirror; both name oil as the confound"),
        domain("NO-K", "Norwegian positioning: the declared gap",
               objects=("the ABSENCE of a CFTC krone series",
                        "the announced daily FX amount as the superior substitute",
                        "the FSA short-sale register as an equity-only observable"),
               conditions=("whether a crowding claim can be measured at the horizon asked",),
               instruments=("EURNOK", "USDNOK"),
               controls=("EUR positioning applied to NOK as an explicit NEGATIVE control: if it "
                         "appears to work, that is evidence of a European effect and not of a "
                         "Norwegian measurement",
                         "SEK, which has the same gap, as the structural comparison",
                         "the same hypothesis on EUR, where the measurement exists",
                         "the explicit UNMEASURED verdict, which must remain available"),
               notes="Norway is the one country in this department where the missing speculative "
                     "series matters less, because the central bank publishes a better one"),
    )


TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    edge("NO-E01",
         source="the month-on-month CHANGE in Norges Bank's announced daily FX transaction amount",
         mechanism="a publicly announced, sized, one-way, price-insensitive flow for the coming "
                   "month; a change in its size is genuinely new information about the state's "
                   "conversion",
         targets=("EURNOK", "USDNOK", "NOKSEK"),
         sign="a larger announced NOK PURCHASE -> krone firmer",
         horizon="the announcement day, and the execution month",
         lag="the announcement precedes the flow by days",
         control="months with an unchanged amount; EURSEK over the same window; the announcement "
                 "day removed, to separate news from execution",
         evidence="HYPOTHESIS",
         notes="the pack's central claim. The intraday announcement time is UNMEASURED and must "
               "be read from the release timestamp."),
    edge("NO-E02",
         source="XBRUSD's weekly return, CONDITIONED on the fiscal setting and the announced "
                "daily amount",
         mechanism="the petroleum rent reaches the krone through the state's conversion rather "
                   "than through the trade balance, so the oil beta is a function of the fiscal "
                   "setting",
         targets=("EURNOK", "USDNOK"),
         sign="Brent up -> EURNOK down, with the magnitude conditional on the fiscal regime",
         horizon="days to weeks", lag="same session",
         control="the UNCONDITIONAL regression as the declared null; XTIUSD for the crude "
                 "complex; EURSEK for the shared European beta",
         evidence="MEASURED_ELSEWHERE",
         notes="the unconditional version is the folk model and is widely published; this edge "
               "claims only that conditioning beats it, which is a testable increment"),
    edge("NO-E03",
         source="Dutch TTF gas prices after 2022",
         mechanism="Norway became Europe's largest pipeline gas supplier, so the Norwegian terms "
                   "of trade became a gas variable rather than a crude one",
         targets=("EURNOK", "USDNOK", "XNGUSD"),
         sign="TTF up -> krone firmer", horizon="weeks",
         lag="Gassco flow data is near real time; the price is not tradable here",
         control="XNGUSD as the explicit Henry Hub control -- a shared move is global gas and "
                 "not European; the pre-2022 sample, where the channel should be absent",
         evidence="HYPOTHESIS",
         notes="the tradable gas leg is the WRONG gas. That is a data dependency, stated."),
    edge("NO-E04",
         source="a Norwegian bank's announced floating mortgage rate change, dated six weeks "
                "before its effective date",
         mechanism="a statutory notice period creates a known constant lag between the decision "
                   "and the household cash-flow shock",
         targets=("EURNOK", "USDNOK"),
         sign="tightening -> Norwegian housing and demand weaker at a knowable lag",
         horizon="quarters", lag="six weeks by statute, plus the macro lag",
         control="Sweden's quarterly contractual reset as the matched control; the announcement "
                 "date against the effective date; Germany as the slow case",
         evidence="HYPOTHESIS",
         notes="the identification comes from the CONSTANT lag, which Sweden does not have"),
    edge("NO-E05",
         source="Skjaertorsdag, when Oslo is closed and the rest of Europe trades",
         mechanism="Norwegian participation is absent while the price moves, and the Norwegian "
                   "settlement break is a day longer than the euro's",
         targets=("EURNOK", "NOKSEK", "USDNOK"),
         sign="compressed range on the day, abnormal Easter forward points, larger gap after",
         horizon="intraday and the value-date window", lag="none",
         control="Nasdaq Stockholm and Xetra on the same Thursday; Good Friday as the symmetric "
                 "case; turnover as the direct control",
         evidence="HYPOTHESIS",
         notes="one guaranteed annual observation, derivable from the computus"),
    edge("NO-E06",
         source="a global risk shock with no Norwegian release",
         mechanism="the krone's liquidity premium widens in stress because its turnover is small "
                   "relative to the economy's openness",
         targets=("EURNOK", "USDNOK", "NOKJPY"),
         sign="risk-off -> krone weaker beyond what oil and rates explain",
         horizon="days", lag="same session",
         control="oil and rate differentials removed FIRST; EURSEK as the more liquid Nordic "
                 "comparison; days with Norwegian news removed",
         evidence="MEASURED_ELSEWHERE",
         notes="the most robust NOK fact in the literature and the easiest to double-count with "
               "the oil beta"),
    edge("NO-E07",
         source="a global dollar funding squeeze",
         mechanism="NIBOR is constructed from a dollar rate and the forward points, so dollar "
                   "stress raises Norwegian term rates mechanically with no Norwegian event",
         targets=("USDNOK", "EURNOK"),
         sign="dollar squeeze -> NIBOR spread wider -> krone weaker",
         horizon="days", lag="same session",
         control="STIBOR's spread over the same window, since it is not dollar-constructed; "
                 "reporting dates; the NOWA spread to isolate the quota effect",
         evidence="HYPOTHESIS",
         notes="the Swedish comparison is what makes the construction effect identifiable"),
    edge("NO-E08",
         source="ISO weeks 28-30 (fellesferie)",
         mechanism="a three-week national absence with an open exchange: a liquidity treatment "
                   "with no information content",
         targets=("EURNOK", "USDNOK", "NOKSEK"),
         sign="lower turnover, compressed range, larger overnight gaps",
         horizon="three weeks", lag="none",
         control="turnover as the direct control; weeks 27 and 31; a non-Nordic pair over the "
                 "same weeks to remove the general European summer",
         evidence="HYPOTHESIS",
         notes="the window is DERIVED from the ISO week rule, so the sample is reproducible"),
    edge("NO-E09",
         source="a Norges Bank rate-path revision at 10:00 CET on a report day",
         mechanism="the bank publishes its own forecast path, so the surprise is a revision to a "
                   "public prior rather than a deviation from a survey",
         targets=("EURNOK", "NOKSEK", "USDNOK"),
         sign="upward path revision -> EURNOK down", horizon="intraday to a week",
         lag="0 to 30 minutes",
         control="interim meetings with no report; the Riksbank's 09:30 CET decision on shared "
                 "mornings; XBRUSD on the same day as the mandatory oil control",
         evidence="HYPOTHESIS",
         notes="only four of the eight annual meetings carry a path; pooling all eight averages "
               "two event sizes"),
    edge("NO-E10",
         source="the Norwegian salmon spot price, oil and global risk removed",
         mechanism="an independent terms-of-trade variable with genuinely inelastic short-run "
                   "supply and a public weekly price",
         targets=("EURNOK",),
         sign="salmon price up -> krone firmer", horizon="weeks",
         lag="the index is weekly",
         control="oil and global risk removed first; EURSEK as the no-seafood comparison; a "
                 "placebo with the price series shuffled",
         evidence="HYPOTHESIS",
         notes="carried mainly as a CONTROL for the oil channel -- a terms-of-trade shock with "
               "no oil content is exactly what that channel needs to be tested against"),
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
    era("no.announced_amount", start="2014-01-01", end=None,
        label="the modern announced daily FX transaction regime",
        what_changed="Norges Bank began publishing the daily amount for the coming month in "
                     "advance, converting an opaque operation into a scheduled public flow",
        invalidates="any krone study before this date that assumes the flow was knowable; it "
                    "was not",
        notes="the start year is DECLARED from public knowledge and should be verified; the "
              "regime is open and running as of 2026-09-17"),
    era("no.covid_intervention", start="2020-03-13", end="2020-04-30",
        label="the March 2020 krone collapse and Norges Bank's own NOK purchases",
        what_changed="the krone fell further and faster than any G10 currency and the central "
                     "bank intervened directly -- a rare, dated, discretionary operation on top "
                     "of the scheduled one",
        invalidates="a liquidity-premium model calibrated without it; this is the tail "
                    "observation the premium exists to describe",
        notes="on this box's FX bars; the index and energy bars begin 2020-09-14 and miss it"),
    era("no.hiking", start="2021-09-24", end="2023-12-14",
        label="the hiking cycle to 4.50%",
        what_changed="Norges Bank was among the first G10 banks to hike, so for part of the "
                     "cycle it was the relative-policy leader rather than a follower",
        invalidates="anything estimated on the 2015-2021 sample; the krone's carry sign changed",
        notes="fully on this box's FX bars"),
    era("no.gas_pivot", start="2022-03-01", end=None,
        label="Norway as Europe's largest pipeline gas supplier",
        what_changed="the Norwegian terms of trade shifted from crude toward gas, and the gas "
                     "price that matters became TTF, which the desk cannot trade",
        invalidates="a Brent-only terms-of-trade model after early 2022; the elasticity changed "
                    "because the export mix did",
        notes="OPEN ERA; the end is UNMEASURED"),
    era("no.structural_weakness", start="2022-01-01", end="2025-06-30",
        label="the persistent krone weakness episode",
        what_changed="the krone weakened despite a strong terms of trade and a hawkish central "
                     "bank, which is the anomaly the liquidity-premium and fund-conversion "
                     "stories exist to explain",
        invalidates="a naive terms-of-trade model, comprehensively -- this era is where it fails",
        notes="the end date is the desk's reading and is DECLARED, not measured; it is the "
              "single most informative era in this pack precisely because the folk model "
              "predicted the wrong sign for three years"),
    era("no.committee_2020", start="2020-01-01", end=None,
        label="the Monetary Policy and Financial Stability Committee replaces the Executive Board",
        what_changed="who makes the decision and how it is communicated",
        invalidates="a reaction-function estimate pooled across the change; the authorship of "
                    "the decision is different even though the clock is not",
        notes="a governance break with no immediate market content, carried because a reaction "
              "function estimated across it is estimating two committees as one"),
    era("no.cutting", start="2025-06-19", end=None,
        label="the cutting cycle",
        what_changed="the krone's rate differential narrowed from the Norwegian side",
        invalidates="carry studies calibrated on 2022-2024",
        notes="OPEN ERA. The 2025 start is DECLARED from public knowledge and should be verified "
              "against norges-bank.no; the end is UNMEASURED by definition."),
)

CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    miner("no_announced_amount", domain_ids=("NO-A",), kind="mechanism",
          entry="countries.no.miners:announced_amount", cadence_s=86400.0,
          notes="NOT WIRED. Must separate the ANNOUNCEMENT event from the EXECUTION flow and "
                "must read the intraday announcement time from the release rather than assume it."),
    miner("no_policy_path", domain_ids=("NO-B", "NO-J"), kind="mechanism",
          entry="countries.no.miners:policy_path",
          notes="NOT WIRED. The XBRUSD control on decision days is mandatory."),
    miner("no_oil_conditional", domain_ids=("NO-C",), kind="mechanism",
          entry="countries.no.miners:oil_conditional",
          notes="NOT WIRED. Must run the UNCONDITIONAL regression as the declared null; if "
                "conditioning does not beat it, that is the finding."),
    miner("no_six_week_notice", domain_ids=("NO-D",), kind="transfer",
          entry="countries.no.miners:six_week_notice",
          notes="NOT WIRED. Cross-country by construction; Sweden is the control economy."),
    miner("no_fund_rebalance", domain_ids=("NO-E",), kind="mechanism",
          entry="countries.no.miners:fund_rebalance",
          notes="NOT WIRED. The trigger is computable from public returns; near-misses are the "
                "natural null."),
    miner("no_calendar_thin", domain_ids=("NO-F", "NO-I"), kind="data",
          entry="countries.no.miners:calendar_thin", cadence_s=86400.0, steerable=False,
          notes="NOT WIRED. A fixed cost: derives Skjaertorsdag and the fellesferie window from "
                "the rules in this module so both samples are reproducible."),
    miner("no_liquidity_premium", domain_ids=("NO-G",), kind="residual",
          entry="countries.no.miners:liquidity_premium",
          notes="NOT WIRED. The premium is the RESIDUAL after oil and rates; a miner that does "
                "not remove them first is measuring the oil beta twice."),
    miner("no_nibor_dollar", domain_ids=("NO-H",), kind="mechanism",
          entry="countries.no.miners:nibor_dollar",
          notes="NOT WIRED. STIBOR is the identifying control because it is not "
                "dollar-constructed."),
    miner("no_positioning_gap", domain_ids=("NO-K",), kind="data",
          entry="countries.no.miners:positioning_gap", cadence_s=604800.0,
          notes="NOT WIRED. Emits a declared UNMEASURED verdict naming the substitutes, which "
                "is a real answer (L1.28a)."),
)


def pack() -> Any:
    """The Norwegian country pack: `CountryPack` when the framework has landed, else a dict."""
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
