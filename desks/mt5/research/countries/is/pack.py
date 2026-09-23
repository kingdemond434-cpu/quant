"""THE ICELAND PACK -- a reservoir level that bounds world aluminium supply, on a published clock.

Fourteen actors with their eleven fields, thirteen domains IS-A..IS-M with objects, conditions,
instruments and negative controls, seventeen datasets, eleven transmission edges naming real
Fusion symbols, eight policy eras, nine source layers in Icelandic and ONE DECLARED ABSENT, and
a holiday calendar derived from Easter and from two Icelandic weekday rules.

THE THREE THINGS THIS PACK INSISTS ON, and each of them is a way an Iceland study goes wrong:

  * THE KRONA IS NOT A SYMBOL AND MUST NOT BE FAKED. ISK is absent from the broker registry and
    it is NEVER proxied by EURNOK or EURSEK: those are floating commodity currencies of open
    economies with deep markets, and the krona is a 390,000-person currency that spent nine
    years behind capital controls. They enter this pack as CONTROLS -- the North Atlantic small
    open economy WITHOUT Iceland's specifics -- and never as a stand-in.
  * THE ALUMINIUM CHANNEL IS PHYSICAL AND THE GAS CHANNEL IS A SPREAD. Iceland smelts on
    stranded renewable power at a cost that does not move with gas, so a European power crisis
    curtails European smelters and NOT Icelandic ones. The mechanism is therefore the SPREAD
    between a gas-exposed and a non-gas-exposed producer, not a level effect, and XNGUSD is
    Henry Hub rather than the European benchmark -- a control-grade leg, declared as such.
  * A POOLED ISK STUDY IS MEASURING FOUR COUNTRIES. `capital_controls_state(day)` returns the
    regime, and the regimes are not exchangeable: a pre-2008 carry destination, a collapsed
    banking system, nine years of controls with an offshore-krona overhang, and an open economy
    with a special reserve requirement that was 40%, then 20%, then nothing.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Any

# --------------------------------------------------------------------------- identity
CODE = "IS"
NAME = "Iceland"
REGION_COMMAND = "europe"
REGION_DESK = "EUROPE"
FOREST = "europe"
CURRENCY = "ISK"
#: THE PARITY FENCE COUNTS THIS (scripts/check_regional_parity.py::jurisdictions_of).
JURISDICTIONS: tuple[str, ...] = ("is",)
#: AND IT WILL NOT FIND IT ON THE ROSTER, WHICH IS A MEASUREMENT AND NOT AN ERROR.
#: `libs/research/forests.py` names 76 countries and Iceland is not one of them -- the europe
#: forest's roster stops at the four large Nordics. This pack is therefore an OFF-ROSTER
#: jurisdiction: it answers for a country the desk's own machinery has not yet named, which is
#: the opposite failure from an unanswered roster row and is recorded here rather than fixed by
#: editing another department's roster from inside a country pack.
OFF_ROSTER_JURISDICTIONS: dict[str, str] = {
    "is": ("Iceland is absent from every Forest.countries roster in libs/research/forests.py "
           "(the europe forest lists GB, DE, FR, IT, ES, NL, SE, NO, DK, FI, PL, CZ, HU, CH, "
           "PT, AT, BE, IE, GR, RO, BG, RS and stops). The pack is written anyway because the "
           "country smelts about 2% of world primary aluminium on stranded power and is the "
           "only place on earth where a published reservoir level bounds a world commodity's "
           "supply; adding it to the roster is the forests module's own change to make"),
}
FISCAL_YEAR_END = "12-31"
NATIVE_LANGUAGES: tuple[str, ...] = ("is", "en", "da")
COT_CURRENCY = ""                  # no CFTC contract exists for the krona
EXPORT_ECONOMY = "power_to_metal_and_marine_exporter"
RETAIL_LEVERAGE_REGIME = "eea_esma_capped_no_domestic_margin_industry"
MISSION = ("mine Iceland as the stranded-power, quota-fished, capital-controlled economy it is: "
           "the hydrological year at Thorisvatn and Halslon bounding smelter output, the power "
           "contracts and the curtailment clause, the capelin and cod advice on a dated "
           "fishing-year clock, the 2008-2017 controls and the special reserve requirement as "
           "named policy eras no pooled study may cross, the Sedlabanki's intervention, the "
           "Keflavik arrivals series, and the Reykjanes eruptions as dated supply-risk events -- "
           "all routed into XALUSD, the softs and the European planes, because the krona is not "
           "a symbol the desk can trade")

#: The instruments this pack may compile a cell against. Every one is in the broker registry and
#: none is a single-name equity. THE KRONA IS ABSENT and is routed, never faked.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "XALUSD",                       # the metal the whole economy is a power contract for
    "XNGUSD",                       # the European smelters' marginal cost, which Iceland's is not
    "SOYBEAN",                      # fishmeal and fish oil substitute for soymeal in feed
    "XBRUSD",                       # the ONLY fossil exposure: transport fuel, never power
    "EURNOK", "EURSEK",             # the North Atlantic small-open-economy controls
    "EUSTX50",                      # the EEA market Iceland sells fish into and flies over
    "EURUSD",                       # revenues in USD (metal) and EUR (fish): the terms of trade
)
EXECUTABLE_SET: frozenset[str] = frozenset(EXECUTABLE_INSTRUMENTS)

#: What Iceland's economics run through that the broker does not quote. The first row is the
#: currency itself: ISK IS NOT A BROKER SYMBOL and this pack never pretends otherwise.
TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "ISK: EURISK, USDISK, GBPISK and the trade-weighted index (gengisvisitala)",
     "venue": "the Icelandic interbank FX market; the official rate is struck by Sedlabanki",
     "why": "THE CURRENCY EVERY MECHANISM HERE IS ABOUT, and it is absent from the broker. It "
            "is never proxied: EURNOK and EURSEK are floating currencies of deep, open "
            "economies and the krona is a 390,000-person currency that spent nine years behind "
            "capital controls. They are CONTROLS for the North Atlantic factor, not stand-ins",
     "proxies": ("EURNOK", "EURSEK", "EURUSD")},
    {"name": "Landsvirkjun and Orkusalan power contracts to the smelters",
     "venue": "bilateral long-term contracts; some LME-linked, some fixed, some indexed",
     "why": "THE PRICE THE WHOLE ECONOMY TURNS ON, and it is commercially confidential except "
            "where a renegotiation is announced. The contract's CURTAILMENT CLAUSE is the "
            "readable part: the utility may cut supply in a poor water year, and does",
     "proxies": ("XALUSD", "XNGUSD")},
    {"name": "LME aluminium three-month and the European duty-paid premium",
     "venue": "London Metal Exchange and the physical premium assessments",
     "why": "the broker's XALUSD is the aluminium leg the desk can actually trade; the PREMIUM "
            "is where a regional supply shock shows up first and it is a licensed assessment",
     "proxies": ("XALUSD",)},
    {"name": "OMXI15 and OMXIPI (Nasdaq Iceland)",
     "venue": "Nasdaq Iceland",
     "why": "no Icelandic index CFD exists, the free float is small, and the index is dominated "
            "by a handful of banks, insurers and fishing companies -- a country index that is a "
            "sector bet, which the two-lane order keeps out of the hypothesis lane entirely",
     "proxies": ("EUSTX50",)},
    {"name": "Icelandic government bonds: RIKB (nominal) and RIKS (CPI-indexed)",
     "venue": "Nasdaq Iceland / the Government Debt Management office",
     "why": "the CPI-INDEXED curve is the unusual one: Iceland indexes a large share of its "
            "household and government debt to the consumer price index, so the real and nominal "
            "curves together are a traded inflation expectation in a tiny economy",
     "proxies": ("EURNOK", "EUSTX50")},
    {"name": "The offshore krona (aflandskronur) and the 2016 auction",
     "venue": "the auction run by Sedlabanki in June 2016 and the residual stock after it",
     "why": "the overhang the whole capital-control era existed to unwind; its price was TWO "
            "prices for one currency at once, which is the single cleanest capital-control "
            "observable any pack in this department has",
     "proxies": ("EURNOK", "EURSEK")},
    {"name": "Fresh-fish auction prices and the pelagic landings price",
     "venue": "the Icelandic fish markets and the producers' settlements",
     "why": "the export earnings the krona's current account runs on; there is no fish symbol, "
            "and the executable leg is the FEED complex that fishmeal and fish oil compete with",
     "proxies": ("SOYBEAN",)},
    {"name": "North Atlantic container and air freight (Eimskip, Samskip, the Keflavik hub)",
     "venue": "bilateral shipping and the airlines' own capacity",
     "why": "an island with no land border imports everything by sea or air; freight is a real "
            "cost channel and there is no freight symbol in the registry",
     "proxies": ("XBRUSD", "EUSTX50")},
)

# --------------------------------------------------------------------------- the water year
#: THE HYDROLOGICAL YEAR. Iceland's reservoirs fill on snowmelt and glacier melt through the
#: summer and draw down through the winter. Thorisvatn (the Thjorsa system) and Halslon (the
#: Karahnjukar system that feeds the Fjardaal smelter) are the two that matter, and their levels
#: are PUBLISHED. When the year is poor the utility invokes the curtailment clause and cuts
#: power to the smelters and the fishmeal plants -- which is a physical bound on world aluminium
#: supply arriving through a weather series.
HYDRO_PHASES: tuple[tuple[int, int, int, int, str], ...] = (
    (5, 1, 9, 30, "FILLING"),
    (10, 1, 12, 31, "DRAWDOWN"),
    (1, 1, 2, 28, "DRAWDOWN"),
    (3, 1, 4, 30, "TROUGH"),
)
HYDRO_RESERVOIRS: tuple[dict[str, Any], ...] = (
    {"name": "Thorisvatn", "native": "Þórisvatn", "system": "Thjorsa / Tungnaa",
     "serves": "the Grundartangi and Straumsvik smelters through the national grid",
     "why": "the largest reservoir in the country and the one the whole southern system is "
            "balanced against"},
    {"name": "Halslon", "native": "Hálslón", "system": "Karahnjukar / Fljotsdalur",
     "serves": "the Fjardaal smelter at Reydarfjordur, effectively a dedicated supply",
     "why": "glacier-fed and built for one customer, so its level maps almost one-for-one to "
            "one smelter's available power"},
)
#: DATED CURTAILMENT EPISODES. Rows are (start, end, what, status). These are the observations
#: that turn 'the reservoir is low' into 'metal was not produced'.
CURTAILMENT_EPISODES: tuple[tuple[date, date, str, str], ...] = (
    (date(2013, 12, 1), date(2014, 4, 30),
     "a poor water year: curtailment of secondary and interruptible power to large users",
     "PRESS_REPORTED"),
    (date(2021, 12, 1), date(2022, 6, 30),
     "a low-water winter after a dry autumn: announced curtailment of interruptible power to "
     "the smelters and the fishmeal plants, with a turbine outage compounding it",
     "PRESS_REPORTED"),
    (date(2024, 1, 1), date(2024, 5, 31),
     "a second low-water winter: renewed curtailment to large users and to the fishmeal plants, "
     "which ran on oil instead -- the one case where an Icelandic water shortage becomes a "
     "small, real oil demand",
     "PRESS_REPORTED"),
)


def hydrological_year_phase(day: date) -> str:
    """FILLING, DRAWDOWN or TROUGH for a date. The phase is the conditioning state of IS-A:
    a low reading in September and the same reading in April mean opposite things."""
    for m0, d0, m1, d1, label in HYDRO_PHASES:
        lo = date(day.year, m0, d0)
        hi_day = d1
        if m1 == 2 and d1 == 28 and day.year % 4 == 0 and (day.year % 100 != 0
                                                           or day.year % 400 == 0):
            hi_day = 29
        hi = date(day.year, m1, hi_day)
        if lo <= day <= hi:
            return label
    return "DRAWDOWN"


def hydrological_year(day: date) -> str:
    """The water year a date belongs to, labelled 'YYYY/YYYY' and starting on 1 May with the
    melt. A study that slices Icelandic power on calendar years cuts every water year in half."""
    start = day.year if day.month >= 5 else day.year - 1
    return f"{start}/{start + 1}"


def curtailment_state(day: date) -> str:
    """CURTAILED or NORMAL on a date, from the declared episodes. The falsifiable half of IS-A:
    a reservoir claim that never reaches a curtailment is a claim about the weather."""
    for lo, hi, _what, _status in CURTAILMENT_EPISODES:
        if lo <= day <= hi:
            return "CURTAILED"
    return "NORMAL"


# --------------------------------------------------------------------------- the fishing year
#: THE FISHING YEAR RUNS 1 SEPTEMBER TO 31 AUGUST. The Marine and Freshwater Research Institute
#: (Hafrannsoknastofnun) publishes its advice for the coming year in June; the minister sets the
#: total allowable catch before the year starts; and the CAPELIN advice is revised in-season on
#: the autumn and winter acoustic surveys, which is why capelin can go to ZERO after the year
#: has already begun.
FISHING_YEAR_START_MONTH = 9
CAPELIN_WINDOWS: tuple[tuple[int, int, str], ...] = (
    (6, 15, "the June advice for the coming fishing year, including a provisional capelin "
            "figure derived from the previous autumn's juvenile survey"),
    (10, 15, "the autumn acoustic survey: the first in-season measurement of the stock"),
    (1, 20, "the winter acoustic survey and the revised advice -- the decision that has "
            "repeatedly moved the capelin quota by a factor of several, or to zero"),
    (2, 15, "the final quota allocation and the start of the main capelin season"),
)
#: SEASONS IN WHICH THE CAPELIN ADVICE WAS ESSENTIALLY ZERO. A whole export line disappearing
#: for a year is a shock nothing in a G10 economy has an analogue for.
CAPELIN_ZERO_SEASONS: tuple[str, ...] = ("2018/2019", "2019/2020")
CAPELIN_ZERO_STATUS = ("PRESS_REPORTED: two consecutive seasons with no commercial capelin "
                       "fishery; re-verify each against Hafrannsoknastofnun's own advice "
                       "documents before a cell is compiled on the dates")


def fishing_year(day: date) -> str:
    """The Icelandic fishing year a date belongs to: 1 September to 31 August, 'YYYY/YYYY'."""
    start = day.year if day.month >= FISHING_YEAR_START_MONTH else day.year - 1
    return f"{start}/{start + 1}"


def fishing_year_start(year: int) -> date:
    """The first day of the fishing year that OPENS in a calendar year."""
    return date(year, FISHING_YEAR_START_MONTH, 1)


def capelin_calendar(year: int) -> tuple[dict[str, Any], ...]:
    """The four dated capelin decision windows that fall inside a calendar year.

    These are advisory and allocation events on a published clock, not price observations. The
    January window is the one that matters: it has moved the quota by a factor of several and to
    zero, after the fishing year had already started.
    """
    return tuple({"date": date(year, m, d), "what": what,
                  "fishing_year": fishing_year(date(year, m, d)),
                  "is_decision": m in (1, 2)}
                 for m, d, what in CAPELIN_WINDOWS)


# --------------------------------------------------------------------------- capital controls
#: THE ERA FUNCTION. Rows are (start, label, note). An ISK series that crosses any of these
#: boundaries is two different objects with one name.
CONTROL_ERAS: tuple[tuple[date, str, str], ...] = (
    (date(2001, 3, 27), "FLOAT_INFLATION_TARGET",
     "the krona is floated and Sedlabanki adopts an inflation target; the carry era begins"),
    (date(2008, 10, 6), "COLLAPSE",
     "the Emergency Act (neydarlogin) is passed as the three banks fail; the currency market "
     "ceases to function normally"),
    (date(2008, 11, 28), "CONTROLS",
     "capital controls are imposed alongside the IMF programme; an OFFSHORE krona develops at a "
     "different price from the onshore one, which is two prices for one currency"),
    (date(2016, 6, 4), "SRR_40",
     "the special reserve requirement on new foreign inflows into krona bonds and deposits is "
     "introduced at 40%, unremunerated, for twelve months -- an explicit capital-flow-management "
     "measure of a kind almost no other country has published"),
    (date(2017, 3, 14), "CONTROLS_LIFTED",
     "the controls on residents and on most capital movement are substantially lifted; the "
     "special reserve requirement stays on new carry inflows"),
    (date(2018, 11, 3), "SRR_20", "the special reserve requirement is reduced to 20%"),
    (date(2019, 3, 6), "SRR_0",
     "the special reserve requirement is set to zero; the krona is an ordinary floating "
     "currency again, ten and a half years after the collapse"),
)
SRR_SCHEDULE: tuple[tuple[date, float, str], ...] = (
    (date(2016, 6, 4), 40.0, "PRESS_REPORTED: introduced by central bank rules"),
    (date(2018, 11, 3), 20.0, "PRESS_REPORTED"),
    (date(2019, 3, 6), 0.0, "PRESS_REPORTED"),
)
OFFSHORE_AUCTION = (date(2016, 6, 16),
                    "the offshore-krona auction: holders of the overhang were offered an exit "
                    "at an auction-clearing rate materially weaker than the onshore rate, and "
                    "what did not participate was moved to locked accounts")


def capital_controls_state(day: date) -> str:
    """The Icelandic capital-account regime on a date. THE MOST IMPORTANT FUNCTION IN THIS PACK.

    A pooled ISK study is measuring four countries at once: a carry destination, a collapsed
    banking system, nine years of controls with two prices for one currency, and an open economy
    with a numeric tax on carry inflows. `POLICY_ERAS` carries the same boundaries as prose;
    this returns them as a state a cell can condition on.
    """
    label = "PRE_FLOAT"
    for start, name, _note in CONTROL_ERAS:
        if start <= day:
            label = name
    return label


def srr_rate(day: date) -> float | None:
    """The special reserve requirement in percent on a date, or None before it existed.

    A NUMERIC, DATED TAX ON CARRY INFLOWS. Three steps -- 40, 20, 0 -- each of which is a natural
    experiment on whether a capital-flow-management measure actually changes the flow.
    """
    got: float | None = None
    for start, rate, _status in SRR_SCHEDULE:
        if start <= day:
            got = rate
    return got


def controls_invalidate(start: date, end: date) -> list[str]:
    """Which regime boundaries a sample spans. An empty list is the only safe answer for a
    pooled ISK study, and this function exists so a study has to LOOK."""
    return [name for boundary, name, _note in CONTROL_ERAS if start < boundary <= end]


# --------------------------------------------------------------------------- eruptions
#: DATED VOLCANIC EVENTS. The met office publishes seismic data and the ICAO aviation colour
#: code; the 2010 Eyjafjallajokull ash cloud is the measured precedent for European airspace and
#: air freight, and the Reykjanes sequence since 2021 sits beside the Svartsengi power plant and
#: the Grindavik town that was evacuated in November 2023.
ERUPTIONS: tuple[tuple[date, str, str], ...] = (
    (date(2010, 4, 14), "Eyjafjallajokull: the ash cloud closes most of European airspace for "
                        "six days and disrupts air freight for weeks", "HISTORICAL"),
    (date(2011, 5, 21), "Grimsvotn: a larger eruption with a far smaller aviation impact, which "
                        "is the control for the 2010 case", "HISTORICAL"),
    (date(2021, 3, 19), "Fagradalsfjall: the first Reykjanes eruption in about eight centuries",
     "PRESS_REPORTED"),
    (date(2022, 8, 3), "Meradalir: the second Fagradalsfjall-system eruption", "PRESS_REPORTED"),
    (date(2023, 7, 10), "Litli-Hrutur: the third", "PRESS_REPORTED"),
    (date(2023, 11, 10), "the Grindavik evacuation as a dyke intrudes under the town; the "
                         "Svartsengi power plant and the Blue Lagoon are inside the affected "
                         "area", "PRESS_REPORTED"),
    (date(2023, 12, 18), "Sundhnukur: the first of the repeated fissure eruptions north of "
                         "Grindavik", "PRESS_REPORTED"),
)
AVIATION_COLOUR_CODES: tuple[str, ...] = ("GREEN", "YELLOW", "ORANGE", "RED")


def eruption_events(since: date | None = None) -> tuple[tuple[date, str, str], ...]:
    """The declared eruption events at or after a date. The event sample of IS-I."""
    if since is None:
        return ERUPTIONS
    return tuple(row for row in ERUPTIONS if row[0] >= since)


def reykjanes_state(day: date) -> str:
    """ACTIVE once the Reykjanes sequence began, PRE_SEQUENCE before it. The regime label IS-I
    conditions on: 2010 is a different volcano, a different system and a different mechanism."""
    return "REYKJANES_ACTIVE" if day >= date(2021, 3, 19) else "PRE_REYKJANES_SEQUENCE"


# --------------------------------------------------------------------------- tourism
#: KEFLAVIK IS THE COUNTRY'S FRONT DOOR AND IT IS COUNTED. Foreign departures through Keflavik
#: are published monthly by the tourist board and the airport operator, with a lag of days. In a
#: 390,000-person economy tourism became the largest export earner within a decade, collapsed to
#: essentially nothing in 2020 and recovered -- which is the largest peacetime swing in a
#: current account anywhere in this department.
TOURISM_SEASONS: dict[str, tuple[int, ...]] = {
    "PEAK": (6, 7, 8), "SHOULDER": (5, 9), "LOW": (1, 2, 3, 4, 10, 11, 12),
}
TOURISM_SHOCKS: tuple[tuple[date, date, str], ...] = (
    (date(2020, 3, 1), date(2021, 6, 30),
     "the pandemic: foreign arrivals fall to a small fraction of normal and the largest export "
     "earner disappears for five quarters"),
    (date(2019, 3, 28), date(2019, 12, 31),
     "the failure of a domestic carrier removes a large block of seat capacity mid-season"),
)


def keflavik_season(day: date) -> str:
    """PEAK, SHOULDER or LOW for a date. Icelandic tourism is violently seasonal and a
    year-on-year comparison that ignores the season is comparing two different businesses."""
    for label, months in TOURISM_SEASONS.items():
        if day.month in months:
            return label
    return "LOW"


def tourism_shock_state(day: date) -> str:
    """SHOCK or NORMAL, from the declared episodes."""
    for lo, hi, _what in TOURISM_SHOCKS:
        if lo <= day <= hi:
            return "SHOCK"
    return "NORMAL"


# --------------------------------------------------------------------------- the central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "Sedlabanki Islands (Central Bank of Iceland)",
    "short": "CBI",
    "framework": "inflation_target_with_declared_fx_intervention",
    "committee": "the Monetary Policy Committee (peningastefnunefnd): the Governor, the Deputy "
                 "Governor for monetary policy and three others, with a PUBLISHED VOTE and "
                 "minutes -- unusual transparency for an economy this size",
    "policy_instrument": "the seven-day term deposit rate (meginvextir) inside a corridor; the "
                         "bank also uses FX intervention and, from 2016, a special reserve "
                         "requirement on carry inflows",
    "mandate": "price stability with a 2.5% inflation target adopted on 2001-03-27, alongside "
               "financial stability; since 2020-01-01 the bank has ALSO absorbed the financial "
               "supervisor (Fjarmalaeftirlitid), so one institution runs monetary policy, "
               "macroprudential policy and supervision -- which makes its reaction function "
               "wider than a pure inflation targeter's",
    "decision_rule": "EIGHT scheduled MPC meetings a year on a calendar published in advance, "
                     "with the decision announced in the morning and the Monetary Bulletin "
                     "(Peningamal) published four times a year alongside it",
    "decision_calendar_rule": "eight announcements a year, published at sedlabanki.is; the "
                              "announcement minute must be stamped from the bank's own release "
                              "and never assumed",
    "decision_dates": (),
    "dates_status": "NOT LISTED. The bank publishes its calendar a year ahead and this pack "
                    "refuses to invent dates it has not read (L1.28a); the calendar is fetched "
                    "from sedlabanki.is and matched to the announcements",
    "decision_time_utc": "08:30",
    "announce_local": "mid-morning Atlantic/Reykjavik, followed by a press conference on "
                      "Monetary Bulletin dates",
    "dst_rule": "ICELAND HAS NO DAYLIGHT SAVING. The country is on UTC+0 all year round, at a "
                "longitude that would put it two hours west -- so the Icelandic working day is "
                "fixed in UTC while every European counterpart's moves twice a year, and a "
                "session study that assumes a European DST rule for Reykjavik is wrong for "
                "seven months of every year",
    "minutes_lag_days": 14,
    "publication_classes": ("vaxtaakvordun", "peningamal", "fundargerd_peningastefnunefndar",
                            "fjarmalastodugleiki", "gjaldeyrismarkadur", "gjaldeyrisfordi",
                            "hagvisar", "working_papers"),
    "policy_rate_series": "CBI:meginvextir",
    "expected_rate_series": "UNMEASURED",
    "consensus_proxy": "the three banks' research departments (Landsbankinn, Islandsbanki, "
                       "Arion) publish a pre-meeting forecast; the indexed and nominal bond "
                       "curves together give a traded real-rate and breakeven expectation",
    "consensus_proxy_trap": "the breakeven is contaminated by the INDEXATION DEMAND of a "
                            "household sector whose mortgages are CPI-linked, so it is a "
                            "hedging price as much as an expectation",
    "reserves_clock": "the foreign reserve and the bank's FX market transactions are published "
                      "monthly, with the intervention amounts named",
    "programme": "an IMF Stand-By Arrangement ran from November 2008 to August 2011 and is "
                 "OVER; the country has no programme today and the capital controls it enabled "
                 "were lifted in 2017",
    "off_cycle": ("2008-10-06 the Emergency Act and the failed peg attempt",
                  "2008-10-28 the policy rate is raised to 18% under the IMF programme",
                  "2016-06-04 the special reserve requirement is introduced"),
    "root": "https://www.sedlabanki.is",
}

# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "Sedlabanki official exchange rate (opinbert gengi) and the trade-weighted index",
     "local": "struck late morning Atlantic/Reykjavik on the interbank market and published the "
              "same day",
     "time_utc": "11:00", "time_utc_dst": "11:00",
     "dst_rule": "NONE -- Iceland stays on UTC+0 all year, so this fixing does not move in UTC "
                 "while every European fixing does",
     "instruments": ("EURUSD", "EURNOK"), "window_minutes": 60,
     "why": "the official krona rate and the gengisvisitala the whole economy is indexed "
            "against; the krona is absent from the broker so the EUR/USD leg is what carries it"},
    {"name": "Sedlabanki Monetary Policy Committee announcement",
     "local": "mid-morning Atlantic/Reykjavik on eight scheduled dates a year",
     "time_utc": "08:30", "time_utc_dst": "08:30", "dst_rule": "none (UTC+0 all year)",
     "instruments": ("EURNOK", "EURSEK"), "window_minutes": 60,
     "why": "the only scheduled Icelandic macro event with a published vote and minutes"},
    {"name": "LME aluminium official price",
     "local": "the second ring, London", "time_utc": "12:55", "time_utc_dst": "11:55",
     "dst_rule": "GMT/BST", "instruments": ("XALUSD",), "window_minutes": 30,
     "why": "the price the LME-linked share of Icelandic power contracts is settled against, "
            "which is the one place the country's power price becomes a world price"},
    {"name": "Nasdaq Iceland closing auction",
     "local": "15:30 Atlantic/Reykjavik", "time_utc": "15:30", "time_utc_dst": "15:30",
     "dst_rule": "none (UTC+0 all year), so the Icelandic close moves RELATIVE to the "
                 "continental close twice a year while staying fixed in UTC",
     "instruments": ("EUSTX50",), "window_minutes": 20,
     "why": "the domestic close; no Icelandic index CFD exists and the tape is licensed"},
    {"name": "Hagstofa consumer price index release",
     "local": "late in the month, FOR THE SAME MONTH", "time_utc": "09:00",
     "time_utc_dst": "09:00", "dst_rule": "none",
     "instruments": ("EURNOK", "EUSTX50"), "window_minutes": 60,
     "why": "UNUSUAL AND IMPORTANT: Iceland publishes the CPI for the CURRENT month before the "
            "month has ended, because a very large stock of CPI-indexed debt has to be revalued "
            "on a known date. Almost no other statistics office does this, and it means the "
            "Icelandic inflation print has the shortest publication lag in this department"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "The fishing year (1 September to 31 August)", "kind": "annual_window",
     "roll": "next", "window_utc": ("08:00", "16:00"), "instruments": ("SOYBEAN", "EURNOK"),
     "why": "quota allocations, vessel plans and the whole marine export calendar hang off this "
            "boundary; `fishing_year(day)` returns it"},
    {"name": "The capelin decision windows (June, October, January, February)",
     "kind": "quarterly_window", "roll": "next", "window_utc": ("09:00", "15:00"),
     "instruments": ("SOYBEAN",),
     "why": "the January acoustic survey has moved the quota by a factor of several, and to "
            "zero, AFTER the fishing year had begun"},
    {"name": "The hydrological year (1 May to 30 April)", "kind": "annual_window",
     "roll": "previous", "window_utc": ("08:00", "16:00"), "instruments": ("XALUSD", "XNGUSD"),
     "why": "reservoirs fill May to September and draw down October to April; a calendar-year "
            "slice cuts every water year in half"},
    {"name": "Month-end CPI indexation reset (verdbaetur)", "kind": "month_end", "roll": "next",
     "window_utc": ("09:00", "16:00"), "instruments": ("EURNOK",),
     "why": "indexed loans and bonds are revalued on a published monthly index; the release "
            "lands BEFORE the month ends, which is why the reset is a dated mechanical event"},
    {"name": "Fiscal year end (31 December)", "kind": "fiscal_year_end", "roll": "previous",
     "window_utc": ("08:00", "16:00"), "instruments": ("EURNOK", "EUSTX50"),
     "why": "the budget year is the calendar year; the fishing fee and the resource-rent tax "
            "are set in it"},
    {"name": "The peak tourism season (June to August)", "kind": "annual_window", "roll": "next",
     "window_utc": ("08:00", "20:00"), "instruments": ("XBRUSD", "EUSTX50"),
     "why": "the FX inflow is violently seasonal in a way no G10 current account is"},
)

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Nasdaq Iceland -- OMXI15, OMXIPI, the bond list",
     "index_symbols": (),
     "open_local": "09:30 (pre-open from 09:00)", "close_local": "15:30",
     "open_utc": "09:30", "close_utc": "15:30",
     "dst_rule": "NONE. Iceland is on UTC+0 all year, so this session is fixed in UTC and moves "
                 "relative to every continental session twice a year",
     "auction": "opening call, continuous trading, closing call at 15:30",
     "expiry_rule": "no listed derivatives worth mining; the market is too small",
     "holidays": "the Icelandic statutory calendar, including two days computed from weekday "
                 "rules found nowhere else: Sumardagurinn fyrsti (the first Thursday after "
                 "18 April) and Fridagur verslunarmanna (the first Monday of August)",
     "notes": "NO CFD IS QUOTED on the Icelandic indices, the free float is tiny and the index "
              "is a handful of banks, insurers and fishing companies -- a country index that is "
              "a sector bet, which the two-lane order keeps out of the hypothesis lane"},
    {"name": "The Icelandic interbank FX and money market",
     "index_symbols": (), "open_local": "09:15", "close_local": "16:00",
     "open_utc": "09:15", "close_utc": "16:00", "dst_rule": "none (UTC+0 all year)",
     "auction": "Sedlabanki's weekly term-deposit auctions and its declared FX intervention",
     "expiry_rule": "none listed",
     "holidays": "the Icelandic banking calendar",
     "notes": "a market of a handful of participants in which the central bank is routinely the "
              "largest; the intervention amounts are PUBLISHED, which is rare, and it is the "
              "reason an Icelandic FX study can be about flow rather than about price alone"},
)

SESSION_WINDOWS: tuple[dict[str, Any], ...] = (
    {"name": "is_cash_session", "start_utc": "09:30", "end_utc": "15:30",
     "notes": "the Nasdaq Iceland session, FIXED IN UTC ALL YEAR because Iceland keeps no "
              "daylight saving; there is deliberately no summer twin of this window"},
    {"name": "is_mpc_announcement", "start_utc": "08:00", "end_utc": "10:00",
     "notes": "the eight scheduled Monetary Policy Committee announcements"},
    {"name": "is_fixing_window", "start_utc": "10:30", "end_utc": "12:00",
     "notes": "the official rate and the trade-weighted index"},
    {"name": "is_cpi_release", "start_utc": "08:30", "end_utc": "10:00",
     "notes": "the consumer price index, published late in the month FOR that month"},
    {"name": "is_lme_overlap", "start_utc": "11:30", "end_utc": "13:30",
     "notes": "the LME rings, which is when the Icelandic power contracts' LME-linked share is "
              "actually priced"},
)

RELEASE_CLASSES: tuple[dict[str, Any], ...] = (
    {"name": "Sedlabanki Monetary Policy Committee decision", "cadence": "8 per year",
     "time_utc": "08:30", "source": "Sedlabanki Islands", "actual_series": "CBI:meginvextir",
     "expected_series": "UNMEASURED",
     "notes": "with a published vote and minutes two weeks later"},
    {"name": "Vísitala neysluverds (consumer price index)", "cadence": "monthly",
     "time_utc": "09:00", "source": "Hagstofa Islands", "actual_series": "HAG:vnv",
     "expected_series": "UNMEASURED",
     "notes": "PUBLISHED FOR THE CURRENT MONTH, late in that month -- the shortest publication "
              "lag of any CPI in this department, because indexed debt must be revalued"},
    {"name": "Sedlabanki FX market transactions and reserves", "cadence": "monthly",
     "time_utc": "09:00", "source": "Sedlabanki Islands", "actual_series": "CBI:intervention",
     "expected_series": "n/a",
     "notes": "the bank names its own purchases and sales, which very few central banks do"},
    {"name": "Hafrannsoknastofnun stock advice (radgjof)", "cadence": "annual plus in-season",
     "time_utc": "10:00", "source": "Hafrannsoknastofnun", "actual_series": "HAF:radgjof",
     "expected_series": "n/a",
     "notes": "the June advice for the fishing year, and the capelin revisions in October and "
              "January that have moved the quota to zero"},
    {"name": "Brottfarir erlendra farthega (foreign departures via Keflavik)",
     "cadence": "monthly", "time_utc": "09:00", "source": "Ferdamalastofa / Isavia",
     "actual_series": "FMS:brottfarir", "expected_series": "n/a",
     "notes": "counted, not surveyed, and published within days -- the fastest read on the "
              "largest export earner"},
    {"name": "Vorudskipti vid utlond (external trade in goods)", "cadence": "monthly",
     "time_utc": "09:00", "source": "Hagstofa Islands", "actual_series": "HAG:voruvidskipti",
     "expected_series": "UNMEASURED",
     "notes": "aluminium and marine products dominate the export side, so the trade print is "
              "mostly two prices and two volumes"},
    {"name": "Landsvirkjun reservoir levels and generation", "cadence": "weekly",
     "time_utc": "12:00", "source": "Landsvirkjun / Landsnet",
     "actual_series": "LV:midlunarlon", "expected_series": "n/a",
     "notes": "the physical bound on smelter output, published by the utility"},
    {"name": "Vedurstofa seismic and aviation colour code", "cadence": "continuous",
     "time_utc": "continuous", "source": "Vedurstofa Islands", "actual_series": "VI:litakodi",
     "expected_series": "n/a",
     "notes": "the ICAO colour code is the machine-readable form of an eruption's aviation risk"},
)

# --------------------------------------------------------------------------- holidays
#: ICELAND IS EASTER PLUS TWO WEEKDAY RULES THAT EXIST NOWHERE ELSE. Sumardagurinn fyrsti (the
#: First Day of Summer) is the first Thursday AFTER 18 April, and Fridagur verslunarmanna
#: (Commerce Day) is the first Monday of August -- both are computed here rather than typed.
FIXED_DAYS: tuple[tuple[int, int, str, str], ...] = (
    (1, 1, "Nýársdagur", "statutory"),
    (5, 1, "Verkalýðsdagurinn (1. maí)", "statutory"),
    (6, 17, "Þjóðhátíðardagurinn", "statutory"),
    (12, 24, "Aðfangadagur (half day from 13:00)", "exchange"),
    (12, 25, "Jóladagur", "statutory"),
    (12, 26, "Annar í jólum", "statutory"),
    (12, 31, "Gamlársdagur (half day from 13:00)", "exchange"),
)
EASTER_DAYS: tuple[tuple[int, str, str], ...] = (
    (-3, "Skírdagur", "statutory"),
    (-2, "Föstudagurinn langi", "statutory"),
    (0, "Páskadagur", "statutory"),
    (1, "Annar í páskum", "statutory"),
    (39, "Uppstigningardagur", "statutory"),
    (49, "Hvítasunnudagur", "statutory"),
    (50, "Annar í hvítasunnu", "statutory"),
)


def easter_sunday(year: int) -> date:
    """Gregorian Easter by the anonymous Gauss/Meeus algorithm. SEVEN Icelandic closures hang
    off this one date and the pack computes it rather than typing a table that ends."""
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


def sumardagurinn_fyrsti(year: int) -> date:
    """The First Day of Summer: the first THURSDAY AFTER 18 April.

    'After' is strict: when 18 April is itself a Thursday the holiday is the 25th. This is an
    Icelandic weekday rule that exists in no other country's calendar, and getting it wrong
    moves a closed session by a week in a third of all years.
    """
    anchor = date(year, 4, 18)
    return anchor + timedelta(days=((3 - anchor.weekday()) % 7) or 7)


def fridagur_verslunarmanna(year: int) -> date:
    """Commerce Day: the first Monday of August, and the Monday of the country's largest
    holiday weekend. The Friday before it is a de facto half day across the economy."""
    first = date(year, 8, 1)
    return first + timedelta(days=(0 - first.weekday()) % 7)


def national_holidays(year: int) -> dict[date, str]:
    """The statutory Icelandic holidays of one year, computed. There is no weekend-substitution
    rule: a holiday that falls at the weekend is lost, which changes the trading-day count."""
    out: dict[date, str] = {}
    for m, d, label, kind in FIXED_DAYS:
        if kind == "statutory":
            out[date(year, m, d)] = label
    easter = easter_sunday(year)
    for offset, label, _kind in EASTER_DAYS:
        out[easter + timedelta(days=offset)] = label
    out[sumardagurinn_fyrsti(year)] = "Sumardagurinn fyrsti"
    out[fridagur_verslunarmanna(year)] = "Frídagur verslunarmanna"
    return dict(sorted(out.items()))


def exchange_closures(year: int) -> dict[date, str]:
    """Every day the exchange and the banks are shut: the statutory days plus the two December
    half days, which are closures for settlement purposes."""
    out = national_holidays(year)
    for m, d, label, kind in FIXED_DAYS:
        if kind == "exchange":
            out[date(year, m, d)] = label
    return dict(sorted(out.items()))


def market_holidays(year: int) -> dict[date, str]:
    """Closed SESSIONS: the exchange calendar on weekdays only."""
    return {d: n for d, n in exchange_closures(year).items() if d.weekday() < 5}


def is_market_holiday(day: date) -> bool:
    return day in market_holidays(day.year)


def lost_holidays(year: int) -> dict[date, str]:
    """Statutory days that fell at the weekend and were therefore lost."""
    return {d: n for d, n in national_holidays(year).items() if d.weekday() >= 5}


HOLIDAYS_RULE: dict[str, Any] = {
    "kind": "computed_from_easter_plus_two_icelandic_weekday_rules",
    "authority": "lög nr. 88/1971 um 40 stunda vinnuviku and the customary helgidagar, as "
                 "published by Stjórnarráðið and applied by Nasdaq Iceland in its trading "
                 "calendar; the two computed days are Icelandic in origin and appear in no "
                 "other country's statute",
    "rule": "FOUR fixed statutory days -- 1 January (Nýársdagur), 1 May "
            "(Verkalýðsdagurinn), 17 June (Þjóðhátíðardagurinn, the national day) and "
            "25-26 December (Jóladagur, Annar í jólum) -- plus SEVEN Easter-derived days "
            "computed from `easter_sunday(year)`: Skírdagur (E-3), Föstudagurinn langi (E-2), "
            "Páskadagur (E+0), Annar í páskum (E+1), Uppstigningardagur (E+39), "
            "Hvítasunnudagur (E+49) and Annar í hvítasunnu (E+50); plus TWO WEEKDAY RULES "
            "found in no other calendar on this desk: Sumardagurinn fyrsti, the first Thursday "
            "AFTER 18 April, and Frídagur verslunarmanna, the first Monday of August. The "
            "MARKET calendar adds two half days that close for settlement: Aðfangadagur "
            "(24 December) and Gamlársdagur (31 December). NO WEEKEND SUBSTITUTION: a holiday "
            "at the weekend is lost and `lost_holidays(year)` names which.",
    "years": (2024, 2025, 2026),
    "weekend": "Saturday and Sunday",
    "national_rule": "see `rule`; `national_holidays(year)` is the computed form",
    "market_rule": "`market_holidays(year)` -- the exchange calendar on weekdays only",
    "clock_note": "ICELAND KEEPS NO DAYLIGHT SAVING. Every Icelandic session and release is "
                  "fixed in UTC all year while its European counterparts move twice a year, so "
                  "the Reykjavik-to-Frankfurt offset is ONE hour in winter and TWO in summer",
    "table": {y: {d.isoformat(): n for d, n in exchange_closures(y).items()}
              for y in (2024, 2025, 2026)},
    "status": {2024: "COMPUTED", 2025: "COMPUTED", 2026: "COMPUTED"},
    "known_dates": {
        "2024-04-25": "Sumardagurinn fyrsti 2024 -- 18 April was itself a Thursday, so the "
                      "holiday is the NEXT one, which is the case the rule is most often got "
                      "wrong on",
        "2025-04-24": "Sumardagurinn fyrsti 2025",
        "2026-04-23": "Sumardagurinn fyrsti 2026",
        "2025-08-04": "Frídagur verslunarmanna 2025, the first Monday of August",
        "2026-06-17": "Þjóðhátíðardagurinn, fixed in every year",
    },
    "fn": market_holidays,
    "national_fn": national_holidays,
    "exchange_fn": exchange_closures,
    "easter_fn": easter_sunday,
    "summer_fn": sumardagurinn_fyrsti,
    "commerce_fn": fridagur_verslunarmanna,
    "lost_fn": lost_holidays,
}

# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "Sedlabanki foreign-exchange market transactions (intervention, by amount)",
     "root": "https://www.sedlabanki.is/hagtolur/",
     "fields": ("cb_purchases_isk_m", "cb_sales_isk_m", "market_turnover_isk_m", "month"),
     "frequency": "monthly", "snapshot": "calendar month", "publish_utc": "09:00",
     "lag_days": 10, "licence": "free, public", "available": True,
     "why": "the central bank NAMES ITS OWN INTERVENTION, which very few do; in a market of a "
            "handful of participants the bank is routinely the largest and the published amount "
            "is most of the flow",
     "pit_warning": "monthly and aggregated; the daily book is not published"},
    {"name": "Sedlabanki foreign exchange reserve and the reserve adequacy metrics",
     "root": "https://www.sedlabanki.is/hagtolur/",
     "fields": ("reserve_isk_m", "reserve_eur_m", "short_term_liabilities", "month"),
     "frequency": "monthly", "snapshot": "month end", "publish_utc": "09:00", "lag_days": 15,
     "licence": "free, public", "available": True,
     "why": "the reserve was the binding constraint through the control era and the metric the "
            "IMF programme was judged on; its level is the state variable of IS-G",
     "pit_warning": "month-end and revised; conditions an era, not a week"},
    {"name": "Pension fund assets and their foreign-currency share (lifeyrissjodir)",
     "root": "https://www.sedlabanki.is/hagtolur/",
     "fields": ("assets_isk_m", "foreign_share_pct", "net_foreign_purchases_isk_m", "quarter"),
     "frequency": "monthly and quarterly", "snapshot": "period end", "publish_utc": "09:00",
     "lag_days": 30, "licence": "free, public", "available": True,
     "why": "a pension system with assets far above GDP, legally capped in foreign currency and "
            "held BEHIND CAPITAL CONTROLS for nine years -- when the cap and the controls "
            "moved, the outflow was the single largest krona flow in the country",
     "pit_warning": "the foreign-share series is revised; the CAP itself is a statute and its "
                    "changes are dated events rather than data"},
    {"name": "Offshore krona (aflandskronur) stock and the 2016 auction result",
     "root": "https://www.sedlabanki.is/gjaldeyrismal/",
     "fields": ("offshore_stock_isk_m", "auction_clearing_rate", "onshore_rate", "date"),
     "frequency": "irregular, dated", "snapshot": "event", "publish_utc": "12:00",
     "lag_days": 0, "licence": "free, public", "available": True,
     "why": "TWO PRICES FOR ONE CURRENCY AT ONCE, published by the central bank. There is no "
            "cleaner capital-control observable anywhere in this department",
     "pit_warning": "event-dated and sparse; it measures an era, and the era ended"},
    {"name": "a CFTC or exchange-traded Icelandic krona positioning series",
     "root": "", "fields": (), "frequency": "n/a", "snapshot": "", "publish_utc": "",
     "lag_days": 0, "licence": "", "available": False,
     "why": "DECLARED ABSENT: no ISK futures contract trades anywhere the desk reads and no COT "
            "row exists for the krona",
     "pit_warning": "DOES NOT EXIST. Krona positioning is UNMEASURED and is never proxied by "
                    "the NOK or SEK COT legs: those are positions in two deep commodity "
                    "currencies and carry no information about a 390,000-person economy"},
)

# --------------------------------------------------------------------------- terminology
#: ICELANDIC, AND THE PACK MEANS IT. Icelandic officialdom, its statute book, its met office and
#: its fisheries science all publish in Icelandic first; the English versions are partial,
#: delayed or absent. A miner that searches English finds the English corner of a country whose
#: whole scientific and regulatory record is in a language 390,000 people speak.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "IS-A": ("miðlunarlón", "vatnsbúskapur", "Þórisvatn", "Hálslón", "vatnsár",
             "skerðing á raforku", "skerðing til stórnotenda", "Landsvirkjun"),
    "IS-B": ("raforkusamningur", "raforkuverð", "orkusala", "stórnotendur", "álver",
             "álframleiðsla", "langtímasamningur", "orkuskortur"),
    "IS-C": ("álverð", "framleiðslukostnaður", "endurnýjanleg orka", "jarðvarmi", "vatnsafl",
             "kolefnisspor", "samkeppnishæfni"),
    "IS-D": ("loðna", "loðnukvóti", "loðnuvertíð", "þorskur", "þorskkvóti", "aflamark",
             "ráðgjöf Hafrannsóknastofnunar", "fiskveiðiár", "aflaheimildir", "mjöl og lýsi",
             "uppsjávarfiskur"),
    "IS-E": ("fjármagnshöft", "losun hafta", "aflandskrónur", "gjaldeyrishöft",
             "stöðugleikaframlag", "útboð aflandskróna", "neyðarlögin"),
    "IS-F": ("sérstök bindiskylda", "bindiskylda", "innflæðishöft", "vaxtamunarviðskipti",
             "fjármagnsinnflæði", "þjóðhagsvarúð"),
    "IS-G": ("inngrip á gjaldeyrismarkaði", "gjaldeyrisforði", "gengisvísitala", "gengi",
             "Seðlabanki Íslands", "meginvextir", "peningastefnunefnd", "Peningamál"),
    "IS-H": ("ferðamenn", "brottfarir", "Keflavíkurflugvöllur", "gistinætur", "ferðaþjónusta",
             "erlendir farþegar", "gjaldeyristekjur"),
    "IS-I": ("eldgos", "kvikuhlaup", "Reykjanesskagi", "Grindavík", "Svartsengi", "öskufall",
             "jarðskjálftahrina", "Veðurstofa Íslands", "litakóði fyrir flug"),
    "IS-J": ("lífeyrissjóðir", "eignir lífeyrissjóða", "erlendar fjárfestingar",
             "gjaldeyrisjöfnuður", "fjárfestingarheimildir", "útstreymi"),
    "IS-K": ("verðtrygging", "verðtryggð lán", "vísitala neysluverðs", "verðbætur",
             "óverðtryggt lán", "raunvextir", "verðbólga", "verðbólgumarkmið"),
    "IS-L": ("krónan", "gengisþróun", "vöruskiptajöfnuður", "viðskiptajöfnuður", "útflutningur",
             "innflutningur", "hrein staða við útlönd"),
    "IS-M": ("flutningar", "Eimskip", "Samskip", "gámaflutningar", "fraktflug", "hafnir",
             "vöruflutningar"),
    "IS-GEN": ("Hagstofa Íslands", "hagvöxtur", "Alþingi", "Stjórnartíðindi", "lög", "reglugerð",
               "Kauphöllin", "ríkisbréf", "Orkustofnun", "Fiskistofa", "Landsnet",
               "Hafrannsóknastofnun", "Ferðamálastofa"),
}

#: The Icelandic letters. A phrase carrying one of them is unambiguously Icelandic rather than
#: an English phrase about Iceland, and the tests assert on this rather than on a language tag.
ICELANDIC_LETTERS: tuple[str, ...] = tuple("þðæöáéíóúýÞÐÆÖÁÉÍÓÚÝ")
#: Icelandic market words with no special letter that are still unambiguously Icelandic.
ICELANDIC_MARKERS: tuple[str, ...] = (
    "loðna", "kvóti", "gengi", "vextir", "banki", "höft", "haft", "orka", "orku", "raforka",
    "afli", "afla", "fiskur", "fisk", "lán", "sjóður", "markaður", "gjaldeyri", "eldgos", "lón",
    "hagstofa", "álver", "flug", "krónu", "krónan", "verð", "hafnir", "skip", "lands", "vatn",
    "peninga", "bindiskyld", "brottfar", "flutning", "kolefni", "kviku", "reykjanes",
    "svartsengi",
)


def has_icelandic_letter(text: str) -> bool:
    """True when a phrase carries one of the letters only Icelandic (and Faroese) still use."""
    return any(ch in str(text) for ch in ICELANDIC_LETTERS)


def is_icelandic(text: str) -> bool:
    """True when a phrase is Icelandic by letter or by working vocabulary.

    Icelandic is written in the Latin alphabet, so `countries.has_script` cannot answer this.
    The test is therefore lexical and deliberately strict: a phrase carrying neither a thorn,
    eth, accented vowel nor an Icelandic market word is an English query wearing an Icelandic
    label, and it will find the English corner of the ground.
    """
    blob = str(text).lower()
    return has_icelandic_letter(blob) or any(m in blob for m in ICELANDIC_MARKERS)


def icelandic_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    rows = TERMINOLOGY if terminology is None else terminology
    return [t for terms in rows.values() for t in terms if is_icelandic(t)]


def term_count(terminology: Mapping[str, Iterable[str]] | None = None) -> int:
    rows = TERMINOLOGY if terminology is None else terminology
    return len({t for terms in rows.values() for t in terms})


# --------------------------------------------------------------------------- source layers
SOURCE_LAYERS: tuple[str, ...] = (
    "official", "institutional", "academic", "practitioner", "retail_ecology",
    "app_ecosystem", "media", "archive", "physical_economy", "source_graph")
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
    labels. `queries` are Icelandic, never translations."""
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


#: THE ONE LAYER ICELAND DOES NOT HAVE, named with the reason. A declared absence is a
#: measurement; a padded row would be a lie about a country of 390,000 people.
LAYER_ABSENCES: dict[str, str] = {
    "retail_ecology": (
        "NO RETAIL MARGIN-STATISTICS ECOLOGY EXISTS. There is no Iceland-domiciled CFD, spread-"
        "betting or retail margin broker; no authority publishes a retail-leverage, retail-flow "
        "or retail-positioning series for Icelandic residents; the exchange's retail share is "
        "not published; and residents were legally barred from foreign securities accounts from "
        "2008-11-28 to 2017-03-14, so no continuous behavioural series survives the era anyway. "
        "The domestic investing public is a few tens of thousands of people who hold funds and "
        "deposits through three banks. The layer is therefore UNMEASURED BY CONSTRUCTION rather "
        "than unmapped, and it is named here instead of being padded with a forum thread"),
}

SOURCE_CLASSES: tuple[dict[str, Any], ...] = (
    # ---- official
    source_class(
        "is_sedlabanki", "Seðlabanki Íslands: policy rate decisions and minutes, Peningamál, the "
                         "official exchange rate and trade-weighted index, FX market "
                         "transactions, reserves, the capital-control rules and the special "
                         "reserve requirement, financial stability reports",
        layer="official",
        roots=("https://www.sedlabanki.is/hagtolur/", "https://www.sedlabanki.is/utgefid-efni/",
               "https://www.sedlabanki.is/gjaldeyrismal/",
               "https://www.sedlabanki.is/peningastefna/"),
        queries=("vaxtaákvörðun peningastefnunefndar", "meginvextir Seðlabankans",
                 "inngrip á gjaldeyrismarkaði", "gjaldeyrisforði", "gengisvísitala",
                 "sérstök bindiskylda", "aflandskrónur", "Peningamál", "fjármálastöðugleiki",
                 "fundargerð peningastefnunefndar"),
        languages=("is", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the bank publishes its OWN INTERVENTION AMOUNTS, which very few central banks "
              "do; since 2020 it also absorbed the financial supervisor, so one institution's "
              "site carries monetary policy, macroprudential policy and supervision at once"),
    source_class(
        "is_hagstofa", "Hagstofa Íslands (Statistics Iceland): the consumer price index, "
                       "national accounts, external trade, tourism, labour market, fisheries "
                       "and energy accounts, through the PX-Web statistics API",
        layer="official",
        roots=("https://www.hagstofa.is", "https://px.hagstofa.is/pxis/",
               "https://www.hagstofa.is/talnaefni/"),
        queries=("vísitala neysluverðs", "vöruviðskipti við útlönd", "þjóðhagsreikningar",
                 "ferðaþjónusta gistinætur", "vinnumarkaður", "hagvöxtur", "aflatölur",
                 "orkunotkun"),
        languages=("is", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public; PX-Web API with no key",
        notes="THE CPI IS PUBLISHED FOR THE CURRENT MONTH, before the month ends, because a "
              "very large stock of CPI-indexed debt must be revalued on a known date -- the "
              "shortest CPI publication lag of any country in this department"),
    source_class(
        "is_orkustofnun", "Orkustofnun (the National Energy Authority): electricity generation "
                          "and consumption by category including the smelters, the energy "
                          "balance, geothermal and hydro resource data, and the licensing record",
        layer="official",
        roots=("https://orkustofnun.is/orkustofnun/utgafa/", "https://orkustofnun.is/raforka/"),
        queries=("raforkuframleiðsla", "raforkunotkun stórnotenda", "orkutölur",
                 "vatnsaflsvirkjanir", "jarðvarmavirkjanir", "orkuspá", "orkujöfnuður"),
        languages=("is", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the official count of how much of the country's electricity goes to the three "
              "smelters -- the number that makes Iceland a power-to-metal economy rather than "
              "a small European one"),
    source_class(
        "is_fiskistofa", "Fiskistofa (the Directorate of Fisheries): quota allocations by vessel "
                         "and species, landings, catch against quota, and the quota-transfer "
                         "register",
        layer="official",
        roots=("https://www.fiskistofa.is/", "https://www.fiskistofa.is/afli-og-aflaheimildir/"),
        queries=("aflamark", "aflaheimildir", "löndun afla", "aflatölur", "kvótastaða",
                 "flutningur aflaheimilda", "fiskveiðiár"),
        languages=("is",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="landings are published at high frequency and BY VESSEL, which is a counted "
              "physical flow rather than a survey; the transferable-quota register is the "
              "ownership map of the country's largest natural resource"),
    source_class(
        "is_stjornarrad", "Stjórnarráðið (the government), the Ministry of Finance and the "
                          "Ministry of Industries: the budget, the fisheries-fee and "
                          "resource-rent decisions, the capital-control legislation and the "
                          "stability contributions",
        layer="official",
        roots=("https://www.stjornarradid.is", "https://www.althingi.is"),
        queries=("fjárlög", "veiðigjald", "stöðugleikaframlag", "frumvarp til laga",
                 "lög um gjaldeyrismál", "ríkisfjármál", "þingskjal"),
        languages=("is",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the capital controls and their lifting are STATUTES with numbers and dates, "
              "which is why IS-E's era boundaries are citable rather than remembered"),
    # ---- institutional
    source_class(
        "is_nasdaq_iceland", "Nasdaq Iceland: OMXI15 and OMXIPI rules and reviews, the bond "
                             "list including the CPI-indexed series, the trading calendar and "
                             "the issuers' disclosures",
        layer="institutional",
        roots=("https://www.nasdaqomxnordic.com/indexes", "https://www.nasdaqomxnordic.com/bonds",
               "https://www.nasdaqomxnordic.com/news/companynews"),
        queries=("Kauphöllin", "OMXI15", "skuldabréfaútboð", "ríkisbréf", "verðtryggð bréf",
                 "viðskiptadagatal", "afkomutilkynning"),
        languages=("is", "en"), access_label="PUBLIC_WITH_TERMS", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED",
        licence="index rules and calendars are free; the LIVE TAPE is licensed market data",
        machine_use_allowed=False,
        notes="REGISTERED, NEVER SCRAPED. The rulebooks and the calendar are readable; the tape "
              "is licensed, and in any case the index is a handful of names and belongs to the "
              "event lane, not the hypothesis lane"),
    source_class(
        "is_landsvirkjun", "Landsvirkjun and the other generators (ON Orka, HS Orka): annual and "
                           "quarterly reports, reservoir and generation data, announced power "
                           "contracts and renegotiations, and the curtailment notices",
        layer="institutional",
        roots=("https://www.landsvirkjun.is/frettir", "https://www.landsvirkjun.is/fjarmal",
               "https://www.hsorka.is"),
        queries=("miðlunarlón staða", "skerðing á afhendingu raforku", "raforkusamningur við "
                 "álver", "ársskýrsla Landsvirkjunar", "orkuvinnsla", "vatnsbúskapur"),
        languages=("is", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public (issuer disclosure)",
        notes="a state-owned utility that is also a bond issuer, so it discloses volumes, prices "
              "and the CURTAILMENT decisions -- the contractual mechanism by which a dry winter "
              "becomes less aluminium"),
    source_class(
        "is_sfs_samorka", "Samtök fyrirtækja í sjávarútvegi (the fisheries companies), Samorka "
                          "(the energy utilities), Samtök atvinnulífsins (the employers) and "
                          "Samtök iðnaðarins (industry): sector statistics and positions",
        layer="institutional",
        roots=("https://sfs.is", "https://samorka.is", "https://www.sa.is"),
        queries=("sjávarútvegur tölur", "útflutningsverðmæti sjávarafurða", "orkumál",
                 "kjarasamningar", "iðnaður á Íslandi", "afkoma greinarinnar"),
        languages=("is",), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="in an economy this concentrated the trade bodies publish numbers the statistics "
              "office does not, and the WAGE ROUND (kjarasamningar) is a dated, economy-wide "
              "event with a direct inflation channel"),
    source_class(
        "is_lifeyrissjodir", "Landssamtök lífeyrissjóða and the individual funds (Gildi, LSR, "
                             "Birta, Frjálsi, Lífeyrissjóður verzlunarmanna): annual reports, "
                             "allocation and the foreign-currency share",
        layer="institutional",
        roots=("https://www.lifeyrismal.is", "https://www.gildi.is/um-gildi/utgefid-efni/"),
        queries=("eignir lífeyrissjóða", "erlendar eignir", "fjárfestingarstefna",
                 "ársskýrsla lífeyrissjóðs", "ávöxtun", "gjaldeyrisjöfnuður"),
        languages=("is",), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="assets far above GDP, a statutory foreign-currency limit, and nine years of "
              "forced domestic investment behind the controls -- when the constraint moved, so "
              "did the largest krona flow in the country"),
    # ---- academic
    source_class(
        "is_universities", "Háskóli Íslands (Hagfræðideild and the Institute of Economic "
                           "Studies), Háskólinn í Reykjavík and the CBI's working paper series",
        layer="academic",
        roots=("https://www.hi.is/hagfraedideild", "https://ioes.hi.is",
               "https://www.sedlabanki.is/utgefid-efni/working-papers/"),
        queries=("hagfræði rannsókn Ísland", "fjármagnshöft greining", "verðtrygging rannsókn",
                 "gengi krónunnar líkan", "aflamarkskerfið hagkvæmni", "vinnuskjal Seðlabankans"),
        languages=("is", "en"), access_label="OPEN_DATA", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public; largely open access",
        notes="the Icelandic capital-control episode and the individual transferable quota "
              "system are both internationally studied, and the literature is domestic, open "
              "and bilingual -- an academic layer genuinely ahead of the practitioner one"),
    source_class(
        "is_theses_repos", "Skemman (the national theses repository) and Opin vísindi (the open "
                           "research repository): every Icelandic thesis and a large share of "
                           "the country's published research",
        layer="academic",
        roots=("https://skemman.is", "https://opinvisindi.is"),
        queries=("meistararitgerð hagfræði", "doktorsritgerð sjávarútvegur",
                 "ritgerð um fjármagnshöft", "orkumál ritgerð", "verðtryggð lán ritgerð"),
        languages=("is", "en"), access_label="OPEN_DATA", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, open access",
        notes="a country this small puts its entire graduate output in two repositories, which "
              "makes an exhaustive sweep of the domestic literature actually possible -- rare "
              "enough to be worth saying"),
    # ---- practitioner
    source_class(
        "is_bank_research", "The three banks' research departments: Hagfræðideild Landsbankans, "
                            "Greining Íslandsbanka and Arion greiningardeild -- rate and "
                            "currency forecasts, sector notes and the pre-meeting previews",
        layer="practitioner",
        roots=("https://www.landsbankinn.is/umraedan/", "https://www.islandsbanki.is/is/grein",
               "https://www.arionbanki.is/bankinn/greining/"),
        queries=("vaxtaspá", "gengisspá krónunnar", "verðbólguspá", "greining á ferðaþjónustu",
                 "sjávarútvegsskýrsla", "íbúðamarkaður greining", "þjóðhagsspá"),
        languages=("is",), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="in an economy with three banks the research departments ARE the sell side, and "
              "their published pre-meeting forecast is the only stated consensus against which "
              "an Icelandic policy surprise can be measured"),
    source_class(
        "is_keldan", "Keldan and the market-data and company-information services used by "
                     "Icelandic professionals, plus the Innherji business desk",
        layer="practitioner",
        roots=("https://www.keldan.is", "https://www.visir.is/k/innherji"),
        queries=("gengi hlutabréfa", "markaðsfréttir", "afkoma félaga", "skuldabréfamarkaður",
                 "viðskipti dagsins", "greiningar"),
        languages=("is",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free tier; the data product is subscription",
        machine_use_allowed=False,
        notes="REGISTERED, NEVER SCRAPED. The subscription data product's terms forbid machine "
              "extraction; the ground is named so the desk does not forget the professional "
              "market-data layer exists here"),
    # ---- retail ecology: DECLARED ABSENT, see LAYER_ABSENCES
    absent_layer("retail_ecology", LAYER_ABSENCES["retail_ecology"]),
    # ---- app ecosystem
    source_class(
        "is_public_apis", "The Icelandic public APIs: Ísland.is, the open-data aggregator "
                          "apis.is, Veðurstofa's public weather, seismic and hydrological feeds, "
                          "and Landsnet's real-time grid data",
        layer="app_ecosystem",
        roots=("https://island.is", "https://apis.is", "https://www.vedur.is/vedur/spar/",
               "https://www.landsnet.is/raforkukerfid/"),
        queries=("opin gögn", "vefþjónusta", "veðurspá API", "jarðskjálftar rauntíma",
                 "raforkukerfið staða", "Ísland.is þjónusta"),
        languages=("is", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, open data",
        notes="Veðurstofa's seismic and hydrological feeds are the machine-readable half of two "
              "of this pack's domains at once: the eruptions of IS-I and the water year of IS-A"),
    source_class(
        "is_bank_apps", "The Icelandic banking and payment apps (Íslandsbanki, Landsbankinn, "
                        "Arion, Aur, Kass) and the consumer energy and travel apps",
        layer="app_ecosystem",
        roots=("https://www.islandsbanki.is/is/flokkur/einstaklingar/app",
               "https://aur.is", "https://www.isavia.is/keflavikurflugvollur"),
        queries=("appið", "netbanki", "greiðsluþjónusta", "flugupplýsingar Keflavík",
                 "rafræn skilríki"),
        languages=("is",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="consumer terms; no open trading API",
        notes="THERE IS NO RETAIL TRADING API ECOLOGY HERE, and this row says so rather than "
              "implying one: the apps are banking and payments, which is what a 390,000-person "
              "market supports"),
    # ---- media
    source_class(
        "is_business_press", "Viðskiptablaðið (vb.is), mbl.is viðskipti, Vísir/Innherji, RÚV and "
                             "Heimildin (formerly Kjarninn): the Icelandic business press",
        layer="media",
        roots=("https://www.vb.is", "https://www.mbl.is/vidskipti/",
               "https://www.ruv.is/frettir/vidskipti", "https://heimildin.is"),
        queries=("Seðlabankinn hækkar vexti", "krónan styrkist", "loðnukvóti ákveðinn",
                 "skerðing hjá Landsvirkjun", "ferðamönnum fjölgar", "eldgos hafið"),
        languages=("is",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free headlines; some articles behind a paywall",
        notes="the fastest Icelandic stamp on a quota decision, a curtailment notice or an "
              "eruption -- all three of which are events whose official publication is slower "
              "than the press's"),
    source_class(
        "is_sector_press", "The sector press: Fiskifréttir and the fisheries trade titles, "
                           "Túristi (turisti.is) on tourism and aviation, and Bændablaðið on "
                           "agriculture and land use",
        layer="media",
        roots=("https://www.fiskifrettir.is", "https://turisti.is",
               "https://www.bbl.is"),
        queries=("loðnuvertíð", "aflaverðmæti", "flugsæti til Íslands", "ferðaþjónustan",
                 "útgerðin", "fiskverð"),
        languages=("is",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free and subscription mixed",
        notes="the trade titles carry the vessel-level and seat-capacity detail the national "
              "press does not, which is where a quota or a tourism turn is visible first"),
    # ---- archive
    source_class(
        "is_timarit_archive", "Tímarit.is: the National and University Library's digitised "
                              "archive of Icelandic newspapers and periodicals, full text, free "
                              "and searchable back to the nineteenth century",
        layer="archive",
        roots=("https://timarit.is", "https://landsbokasafn.is"),
        queries=("gengisfelling", "síldarárin", "þorskastríðið", "verðbólga níunda áratugarins",
                 "gjaldeyrisskortur", "kvótakerfið sett á"),
        languages=("is",), access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free for research; some items in-copyright",
        notes="ONE OF THE BEST NATIONAL NEWSPAPER ARCHIVES ANYWHERE, free and full text. The "
              "herring collapse of the late 1960s, the devaluation decades and the introduction "
              "of the quota system are all readable in the contemporary record, which is how a "
              "pre-1999 Icelandic regime can be studied at all"),
    source_class(
        "is_gazette_archive", "Stjórnartíðindi (the gazette) and Alþingi's document archive: "
                              "every act, regulation and parliamentary document with a number "
                              "and a date",
        layer="archive",
        roots=("https://www.stjornartidindi.is", "https://www.althingi.is/altext/"),
        queries=("reglur um gjaldeyrismál", "lög um sérstaka bindiskyldu", "neyðarlögin 2008",
                 "auglýsing í Stjórnartíðindum", "þingmál um fjármagnshöft"),
        languages=("is",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE STATUTE IS THE EVENT for IS-E and IS-F: the controls, their lifting and the "
              "special reserve requirement are all numbered instruments with dates, which is "
              "why this pack's era function can be cited rather than recalled"),
    # ---- physical economy
    source_class(
        "is_vedurstofa", "Veðurstofa Íslands (the Icelandic Met Office): seismicity, volcanic "
                         "unrest, the ICAO aviation colour code, glacier and river discharge, "
                         "snow water equivalent and the hydrological forecasts",
        layer="physical_economy",
        roots=("https://www.vedur.is/jardhraeringar/", "https://www.vedur.is/vatnafar/",
               "https://en.vedur.is/volcanoes/"),
        queries=("jarðskjálftahrina", "kvikusöfnun", "litakóði fyrir flug", "eldgos hafið",
                 "vatnafar", "snjóalög", "jökulhlaup", "rennsli í ám"),
        languages=("is", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, open data",
        notes="TWO DOMAINS IN ONE FEED: the hydrological series that bounds smelter output and "
              "the volcanic series that prices aviation risk, both machine-readable and both "
              "published by the same state agency"),
    source_class(
        "is_hafro", "Hafrannsóknastofnun (the Marine and Freshwater Research Institute): stock "
                    "assessments and advice for cod, capelin, herring, haddock and the rest, "
                    "plus the acoustic survey reports",
        layer="physical_economy",
        roots=("https://www.hafogvatn.is/is/veidiradgjof", "https://www.hafogvatn.is/is/utgafa"),
        queries=("ráðgjöf um loðnuveiðar", "loðnumæling", "þorskstofninn", "stofnmat",
                 "bergmálsmæling", "veiðiráðgjöf", "ástand nytjastofna"),
        languages=("is", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE ADVICE IS THE EVENT of IS-D. The winter acoustic survey has moved the capelin "
              "quota by a factor of several, and to zero, after the fishing year had begun -- a "
              "scientific measurement that is also a dated supply shock"),
    source_class(
        "is_isavia_ports", "Isavia (Keflavík and the airports), Faxaflóahafnir and the other "
                           "port authorities, and the domestic carriers' capacity data",
        layer="physical_economy",
        roots=("https://www.isavia.is/fyrirtaekid/upplysingar-og-tolfraedi",
               "https://www.faxafloahafnir.is", "https://www.ferdamalastofa.is/is/tolur-og-utgafur"),
        queries=("farþegatölur Keflavíkurflugvöllur", "brottfarir erlendra farþega",
                 "sætaframboð", "skipakomur", "gámaflutningar", "hafnartölur"),
        languages=("is", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="a counted, monthly, fast-published series on the country's largest export "
              "earner; an island with no land border imports and exports through exactly these "
              "two chokepoints, which makes the throughput an almost complete trade census"),
    # ---- source graph
    source_class(
        "is_source_graph", "What the other layers cite: OpenAlex and CORE for the Icelandic "
                           "economics, fisheries-science and geoscience literature, the CBI's "
                           "and Hafrannsóknastofnun's reference lists, and the two national "
                           "repositories' citation graphs",
        layer="source_graph",
        roots=("https://openalex.org", "https://core.ac.uk", "https://opinvisindi.is",
               "https://skemman.is"),
        queries=("heimildaskrá", "tilvísanir í skýrslu Hafrannsóknastofnunar",
                 "vitnað í Seðlabankann", "rannsóknargögn Ísland", "gagnasöfn um orkumál"),
        languages=("is", "en"), access_label="OPEN_DATA", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, open metadata",
        notes="the expansion edges: Icelandic fisheries science and volcanology both cite a "
              "small, stable set of data products, and following the citations is how a scout "
              "finds the series the official layer never advertises"),
)


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
            "n_layers_declared": sum(1 for n in counts.values() if n) + len(LAYER_ABSENCES),
            "n_sources": len([s for s in SOURCE_CLASSES
                              if not str(s["id"]).startswith("absent_")]),
            "missing": missing,
            "unexplained_missing": sorted(k for k, why in missing.items() if not why.strip()),
            "declared_absent": sorted(LAYER_ABSENCES),
            "machine_use_forbidden": [str(s["id"]) for s in SOURCE_CLASSES
                                      if not s.get("machine_use_allowed", True)],
            "low_weight_kept": [str(s["id"]) for s in SOURCE_CLASSES
                                if s.get("credibility") in ("FRINGE", "UNRELIABLE",
                                                            "CONTRADICTED")],
            "rule": "ten layers, each carrying a source or named ABSENT with a reason; a "
                    "declared absence is a measurement and a blank layer is work not done; "
                    "ground whose terms forbid machine extraction is registered "
                    "machine_use_allowed=false, never scraped and never omitted"}


#: NATIVE QUERY TERRITORIES -- what the deep-forest miner types, per layer, in Icelandic. The
#: retail_ecology key is DELIBERATELY ABSENT: there is no ground there to search (LAYER_ABSENCES).
QUERY_TERRITORIES: dict[str, tuple[str, ...]] = {
    "official": ("vaxtaákvörðun peningastefnunefndar", "inngrip á gjaldeyrismarkaði",
                 "sérstök bindiskylda reglur", "vísitala neysluverðs", "aflamark fiskveiðiárs",
                 "raforkunotkun stórnotenda", "vöruviðskipti við útlönd"),
    "institutional": ("skerðing á afhendingu raforku", "raforkusamningur við álver",
                      "eignir lífeyrissjóða erlendis", "útflutningsverðmæti sjávarafurða",
                      "ársskýrsla Landsvirkjunar", "kjarasamningar á almennum markaði"),
    "academic": ("rannsókn á fjármagnshöftum", "verðtrygging og heimilin", "aflamarkskerfið",
                 "gengi krónunnar líkan", "vinnuskjal Seðlabanka Íslands",
                 "meistararitgerð um orkumál"),
    "practitioner": ("vaxtaspá bankanna", "gengisspá krónunnar", "þjóðhagsspá",
                     "greining á ferðaþjónustu", "sjávarútvegsskýrsla", "íbúðamarkaður greining"),
    "app_ecosystem": ("opin gögn Ísland", "vefþjónusta apis.is", "jarðskjálftar í rauntíma",
                      "raforkukerfið staða", "veðurspá vefþjónusta"),
    "media": ("Seðlabankinn hækkar vexti", "loðnukvóti ákveðinn", "skerðing hjá Landsvirkjun",
              "eldgos hafið á Reykjanesi", "ferðamönnum fjölgar", "krónan veikist"),
    "archive": ("gengisfelling króna", "þorskastríðið", "kvótakerfið sett á",
                "neyðarlögin 2008", "reglur um gjaldeyrismál", "síldarárin"),
    "physical_economy": ("miðlunarlón staða", "rennsli í ám", "snjóalög á hálendinu",
                         "loðnumæling bergmál", "litakóði fyrir flug", "kvikuhlaup",
                         "farþegatölur Keflavíkurflugvöllur", "löndun afla"),
    "source_graph": ("heimildaskrá Seðlabankans", "tilvísanir Hafrannsóknastofnunar",
                     "gagnasöfn um orkumál", "rannsóknargögn Ísland", "opin vísindi tilvitnanir"),
}

# --------------------------------------------------------------------------- datasets
DATASETS: tuple[dict[str, Any], ...] = (
    {"name": "Sedlabanki policy rate (meginvextir) and MPC decisions",
     "source": "Sedlabanki Islands", "coverage": "1998 onward, with the 2001 target adoption",
     "frequency": "8 per year", "publication_lag_days": 0.0, "revisions": "never",
     "licence": "free, public", "history_from": "2001-03", "pit_feasible": True,
     "assets": ("EURNOK", "EURSEK", "EUSTX50"),
     "mechanism_families": ("policy_surprise", "carry_funding"),
     "how_to_fetch": "sedlabanki.is hagtolur -> vextir Sedlabankans; the decisions, the vote "
                     "and the minutes two weeks later, all dated"},
    {"name": "Sedlabanki FX market transactions (declared intervention)",
     "source": "Sedlabanki Islands", "coverage": "2010 onward in the modern format",
     "frequency": "monthly", "publication_lag_days": 10.0, "revisions": "rare",
     "licence": "free, public", "history_from": "2010-01", "pit_feasible": True,
     "assets": ("EURNOK", "EURSEK", "EURUSD"),
     "mechanism_families": ("intervention", "institutional_flow"),
     "how_to_fetch": "sedlabanki.is gjaldeyrismal -> the bank's own purchases and sales by "
                     "month, in a market where it is routinely the largest participant"},
    {"name": "Sedlabanki official exchange rate and the trade-weighted index",
     "source": "Sedlabanki Islands", "coverage": "1981 onward", "frequency": "daily",
     "publication_lag_days": 0.0, "revisions": "never", "licence": "free, public",
     "history_from": "1999-01", "pit_feasible": True, "assets": ("EURUSD", "EURNOK"),
     "mechanism_families": ("fixing", "regime_break"),
     "how_to_fetch": "sedlabanki.is gengi, daily CSV; the krona is ABSENT from the broker, so "
                     "this series is an INPUT and a regime label and never a tradable leg"},
    {"name": "Special reserve requirement rules and rate history",
     "source": "Sedlabanki Islands / Stjornartidindi",
     "coverage": "2016-06 to 2019-03", "frequency": "irregular, dated",
     "publication_lag_days": 0.0, "revisions": "never", "licence": "free, public",
     "history_from": "2016-06", "pit_feasible": True, "assets": ("EURNOK", "EURSEK"),
     "mechanism_families": ("regime_break", "capital_flow_management"),
     "how_to_fetch": "the numbered rules in Stjornartidindi plus the bank's own announcements; "
                     "`srr_rate(day)` is the pack's copy and the statute is the citation"},
    {"name": "Capital control legislation and the offshore-krona auction",
     "source": "Althingi / Sedlabanki Islands", "coverage": "2008-11 to 2017-03 and after",
     "frequency": "irregular, dated", "publication_lag_days": 0.0, "revisions": "never",
     "licence": "free, public", "history_from": "2008-11", "pit_feasible": True,
     "assets": ("EURNOK", "EURSEK", "EUSTX50"),
     "mechanism_families": ("regime_break", "capital_flow_management"),
     "how_to_fetch": "althingi.is and stjornartidindi.is for the acts; sedlabanki.is for the "
                     "2016-06-16 auction result, which published TWO PRICES FOR ONE CURRENCY"},
    {"name": "Hagstofa consumer price index (visitala neysluverds)",
     "source": "Hagstofa Islands", "coverage": "1939 onward; modern basis from 1988",
     "frequency": "monthly", "publication_lag_days": 0.0,
     "revisions": "never -- an indexed-debt legal reference cannot be revised",
     "licence": "free, public", "history_from": "1999-01", "pit_feasible": True,
     "assets": ("EURNOK", "EUSTX50"),
     "mechanism_families": ("release_surprise", "administered_price"),
     "how_to_fetch": "px.hagstofa.is PX-Web API; PUBLISHED FOR THE CURRENT MONTH, before the "
                     "month ends, because CPI-indexed debt must be revalued on a known date -- "
                     "a zero publication lag that exists almost nowhere else"},
    {"name": "Hagstofa external trade in goods by commodity",
     "source": "Hagstofa Islands", "coverage": "1988 onward", "frequency": "monthly",
     "publication_lag_days": 35.0, "revisions": "revised for two months",
     "licence": "free, public", "history_from": "1999-01", "pit_feasible": True,
     "assets": ("XALUSD", "SOYBEAN", "EURUSD"),
     "mechanism_families": ("external_balance", "physical_flow"),
     "how_to_fetch": "px.hagstofa.is; aluminium and marine products dominate the export side, "
                     "so the trade print is essentially two prices and two volumes and must be "
                     "decomposed rather than read as a macro aggregate"},
    {"name": "Foreign departures via Keflavik (brottfarir erlendra farthega)",
     "source": "Ferdamalastofa and Isavia", "coverage": "2002 onward",
     "frequency": "monthly", "publication_lag_days": 10.0, "revisions": "minor",
     "licence": "free, public", "history_from": "2002-01", "pit_feasible": True,
     "assets": ("XBRUSD", "EUSTX50", "EURUSD"),
     "mechanism_families": ("seasonal_flow", "physical_flow"),
     "how_to_fetch": "ferdamalastofa.is tolur-og-utgafur and isavia.is statistics; COUNTED at "
                     "the border rather than surveyed, and published within days"},
    {"name": "Landsvirkjun reservoir levels and generation",
     "source": "Landsvirkjun and Landsnet", "coverage": "publicly reported from the 2010s",
     "frequency": "weekly and continuous", "publication_lag_days": 3.0,
     "revisions": "operational corrections", "licence": "free, public",
     "history_from": "2012-01", "pit_feasible": False,
     "assets": ("XALUSD", "XNGUSD"),
     "mechanism_families": ("physical_flow", "supply_constraint"),
     "how_to_fetch": "landsvirkjun.is and landsnet.is; NOT POINT-IN-TIME -- the pages are "
                     "overwritten in place, so the vintage exists only in the archive layer's "
                     "crawls and a cell compiled on an un-archived week is UNMEASURED"},
    {"name": "Orkustofnun electricity generation and consumption by category",
     "source": "Orkustofnun", "coverage": "1915 onward for generation; category splits from the "
                                          "1970s",
     "frequency": "annual with monthly series", "publication_lag_days": 120.0,
     "revisions": "minor", "licence": "free, public", "history_from": "1999-01",
     "pit_feasible": True, "assets": ("XALUSD",),
     "mechanism_families": ("physical_flow", "supply_constraint"),
     "how_to_fetch": "orkustofnun.is raforka statistics; the SMELTER SHARE of national "
                     "consumption is the number that defines this economy"},
    {"name": "Hafrannsoknastofnun stock advice and acoustic survey results",
     "source": "Hafrannsoknastofnun", "coverage": "decades for cod; capelin surveys by season",
     "frequency": "annual plus in-season revisions", "publication_lag_days": 0.0,
     "revisions": "the advice IS the revision", "licence": "free, public",
     "history_from": "1999-06", "pit_feasible": True, "assets": ("SOYBEAN", "EURNOK"),
     "mechanism_families": ("administered_event", "supply_constraint"),
     "how_to_fetch": "hafogvatn.is veidiradgjof; the June advice for the fishing year and the "
                     "October and January capelin revisions, each a dated document"},
    {"name": "Fiskistofa catch, quota and landings",
     "source": "Fiskistofa", "coverage": "the quota system from 1984, modern data from 2000",
     "frequency": "daily and monthly", "publication_lag_days": 2.0,
     "revisions": "minor", "licence": "free, public", "history_from": "2000-09",
     "pit_feasible": True, "assets": ("SOYBEAN", "EURNOK"),
     "mechanism_families": ("physical_flow", "administered_event"),
     "how_to_fetch": "fiskistofa.is afli-og-aflaheimildir; landings BY VESSEL AND SPECIES, "
                     "counted and near-real-time, which is an unusually complete physical series"},
    {"name": "Vedurstofa seismic, volcanic and hydrological feeds",
     "source": "Vedurstofa Islands", "coverage": "continuous, decades of history",
     "frequency": "continuous", "publication_lag_days": 0.0, "revisions": "reviewed events",
     "licence": "free, open data", "history_from": "2000-01", "pit_feasible": True,
     "assets": ("XALUSD", "EUSTX50", "XBRUSD"),
     "mechanism_families": ("physical_flow", "event_risk"),
     "how_to_fetch": "vedur.is jardhraeringar and vatnafar plus the apis.is mirrors; the ICAO "
                     "aviation colour code is the machine-readable form of an eruption's "
                     "aviation risk and river discharge is the leading half of the water year"},
    {"name": "Pension fund assets and foreign-currency share",
     "source": "Sedlabanki Islands / Landssamtok lifeyrissjoda",
     "coverage": "1997 onward", "frequency": "monthly and quarterly",
     "publication_lag_days": 30.0, "revisions": "minor", "licence": "free, public",
     "history_from": "1999-01", "pit_feasible": True, "assets": ("EURUSD", "EUSTX50"),
     "mechanism_families": ("institutional_flow", "regime_break"),
     "how_to_fetch": "sedlabanki.is hagtolur -> lifeyrissjodir; the foreign share, the statutory "
                     "cap's changes and the post-2017 outflow are one series and three regimes"},
    {"name": "Nasdaq Iceland index composition and trading calendar",
     "source": "Nasdaq", "coverage": "OMXI15 from 2021; OMXI8/OMXI10 before it",
     "frequency": "semi-annual reviews", "publication_lag_days": 0.0, "revisions": "never",
     "licence": "index rules are free; the price tape is licensed market data",
     "history_from": "2021-01", "pit_feasible": True, "assets": ("EUSTX50",),
     "mechanism_families": ("index_mechanics",),
     "how_to_fetch": "the Nasdaq Nordic rulebooks and review notices; COMPOSITION AND CALENDAR "
                     "ONLY -- the tape is licensed and registered machine_use_allowed=false"},
    {"name": "Stjornartidindi and Althingi: statutes, rules and parliamentary documents",
     "source": "the Icelandic state", "coverage": "digitised from the 1990s onward",
     "frequency": "daily", "publication_lag_days": 0.0, "revisions": "never",
     "licence": "free, public", "history_from": "1999-01", "pit_feasible": True,
     "assets": ("EURNOK", "EUSTX50"),
     "mechanism_families": ("regime_break", "administered_event"),
     "how_to_fetch": "stjornartidindi.is and althingi.is; the capital controls, their lifting "
                     "and the special reserve requirement are numbered instruments with dates"},
    {"name": "Timarit.is digitised newspaper and periodical archive",
     "source": "Landsbokasafn Islands", "coverage": "the nineteenth century to the present",
     "frequency": "n/a (archive)", "publication_lag_days": 0.0, "revisions": "never",
     "licence": "free for research; some items in-copyright", "history_from": "1900-01",
     "pit_feasible": True, "assets": ("EURNOK", "XALUSD"),
     "mechanism_families": ("archive_reconstruction",),
     "how_to_fetch": "timarit.is full-text search; the only way to reconstruct the herring "
                     "collapse, the devaluation decades and the introduction of the quota "
                     "system from the contemporary record rather than from a later summary"},
)

# --------------------------------------------------------------------------- actors
ACTORS: tuple[dict[str, Any], ...] = (
    {"name": "Sedlabanki Islands' Monetary Policy Committee",
     "holds": "the seven-day term deposit rate, a foreign reserve rebuilt after 2008, and -- "
              "since the supervisor was absorbed in 2020 -- the macroprudential and supervisory "
              "toolkit as well",
     "forced_to": ("decide at eight scheduled meetings a year and publish a vote and minutes",
                   "hit a 2.5% inflation target in an economy where a wage round, a fish quota "
                   "and an exchange-rate move can each move the index by themselves",
                   "manage a currency with no depth: a single large flow is a market event"),
     "when": "eight scheduled announcements a year, mid-morning Reykjavik, which is FIXED IN "
             "UTC because Iceland keeps no daylight saving",
     "information": ("the FX market's order flow in a market of a handful of participants",
                     "the pension funds' outflow intentions",
                     "the banks' books, because it supervises them"),
     "constraints": ("a tiny, shallow FX market in which its own intervention is most of the "
                     "flow",
                     "a large stock of CPI-INDEXED household debt, so an inflation surprise is "
                     "transmitted to balance sheets mechanically rather than through behaviour",
                     "an inflation index published for the CURRENT month, which shortens every "
                     "lag it works with"),
     "instruments": ("EURNOK", "EURSEK", "EUSTX50"),
     "counterparties": ("the three commercial banks", "the pension funds",
                        "the foreign carry investor when one exists"),
     "observables": ("the decision, the vote and the minutes",
                     "the monthly FX transactions it names itself",
                     "the reserve level", "Peningamal's published forecast"),
     "impact": "the krona is not a broker symbol, so a policy move reaches the desk only as a "
               "regime label and through the North Atlantic control plane -- which is exactly "
               "why the pack routes Iceland rather than trading it",
     "persistence": "a policy stance holds a quarter or two; the regime labels hold years",
     "falsifier": "Icelandic policy decisions carry no information for EURNOK, EURSEK or the "
                  "European indices beyond the Nordic and euro-area factors of the same days -- "
                  "which is the EXPECTED result and would confirm that Iceland is a "
                  "physical-economy pack and not an FX pack",
     "notes": "the honest prior here is that this actor moves nothing the desk can trade; the "
              "pack keeps it because it defines the regimes every other Icelandic series lives "
              "in"},
    {"name": "The Sedlabanki FX desk and the capital-flow-management toolkit",
     "holds": "the intervention book, the special reserve requirement, and (until 2017) the "
              "capital controls themselves",
     "forced_to": ("publish its own purchases and sales by month, which very few central banks "
                   "do",
                   "hold a reserve sized against a short-term external liability rather than "
                   "against trade",
                   "unwind an offshore-krona overhang it could not simply let out"),
     "when": "continuously; monthly publication; the special reserve requirement moved on three "
             "dated days",
     "information": ("the offshore and onshore krona prices side by side, which nobody else had",
                     "the composition of the inflow it was taxing"),
     "constraints": ("a market so small that a single pension-fund roll is a price event",
                     "a legal toolkit that had to be justified to the EEA and the IMF",
                     "an overhang that could not be released at the onshore price"),
     "instruments": ("EURNOK", "EURSEK"),
     "counterparties": ("the three banks", "the offshore krona holders",
                        "the carry investors the reserve requirement was aimed at"),
     "observables": ("the published monthly intervention amounts", "the reserve",
                     "the special reserve requirement's three rates",
                     "the 2016 auction's clearing rate against the onshore rate"),
     "impact": "a numeric, dated tax on carry inflows is one of the cleanest natural "
               "experiments in capital-flow management anywhere, and the sign of the outcome is "
               "genuinely contested in the literature",
     "persistence": "each rate step held one to two years",
     "falsifier": "the three special-reserve-requirement steps show no measurable change in "
                  "Icelandic bond inflows, the krona's carry-adjusted return or the onshore "
                  "rate, relative to the Norwegian and Swedish comparators over the same months",
     "notes": "the reason IS-F is a domain: the instrument is rare, dated, numeric and "
              "two-sided, which is everything a natural experiment needs"},
    {"name": "Landsvirkjun, the state power company",
     "holds": "most of Iceland's generating capacity, the reservoirs behind it, and long-term "
              "power contracts with the three aluminium smelters",
     "forced_to": ("balance a hydro system with NO INTERCONNECTOR to anywhere, so every "
                   "kilowatt-hour must be consumed domestically or not generated",
                   "invoke the curtailment clause in a poor water year and cut supply to the "
                   "smelters and the fishmeal plants",
                   "publish reservoir levels and report as a bond issuer"),
     "when": "the hydrological year: filling May to September, drawing down October to April, "
             "trough in March and April; curtailment decisions in the winter",
     "information": ("its own inflow forecasts and reservoir trajectory weeks ahead of the "
                     "public series",
                     "the contracted and spot positions of its large customers"),
     "constraints": ("no export cable, so surplus power is worthless and deficit power cannot "
                     "be bought",
                     "reservoir storage measured in months, not years",
                     "contracts that fix price but permit curtailment"),
     "instruments": ("XALUSD", "XNGUSD"),
     "counterparties": ("the three smelters", "the fishmeal and ferrosilicon plants",
                        "the bond market"),
     "observables": ("the published reservoir levels", "the curtailment notices",
                     "the announced contract renegotiations", "generation by category"),
     "impact": "A WEATHER SERIES THAT BOUNDS WORLD ALUMINIUM SUPPLY. Nothing else in this "
               "department has a published hydrological reading that maps to a tradable "
               "commodity's supply through a contract clause",
     "persistence": "a curtailment runs a winter; a contract runs decades",
     "falsifier": "announced Icelandic curtailments show no abnormal XALUSD behaviour relative "
                  "to weeks matched on the European power price and the global aluminium "
                  "inventory -- which would say 2% of world supply is too small to see, and "
                  "that is a real answer the pack will publish",
     "notes": "the single most distinctive actor in this pack and the reason IS-A exists"},
    {"name": "The three aluminium smelters as a class",
     "holds": "roughly 2% of world primary aluminium capacity, run on contracted renewable "
              "power at a cost that does not move with gas",
     "forced_to": ("run at full rate or not at all: a potline that is cut is a potline that "
                   "freezes, which is a months-long and expensive restart",
                   "accept curtailment of interruptible power under the contract",
                   "buy alumina and carbon anodes at world prices, and ship both in"),
     "when": "continuously; curtailment in poor water years; contract renegotiations on "
             "announced dates",
     "information": ("their own production rate and the power available to them before the "
                     "statistics show it",),
     "constraints": ("the potline's physics, which makes output almost perfectly inelastic in "
                     "the short run",
                     "a power contract that is the dominant cost and is fixed or LME-linked",
                     "an island supply chain: alumina in, metal out, all by sea"),
     "instruments": ("XALUSD", "EURUSD"),
     "counterparties": ("Landsvirkjun and the other generators", "the alumina suppliers",
                        "the European and American metal buyers"),
     "observables": ("national electricity consumption by large users",
                     "the export statistics' aluminium line in tonnes and value",
                     "the announced curtailments and restarts"),
     "impact": "the ONLY large smelters on earth whose marginal cost is unaffected by a gas "
               "price -- so when European power crises curtail continental smelters, these do "
               "not, and the mechanism is a SPREAD and not a level",
     "persistence": "a curtailment lasts a season; a closure is permanent and has been "
                    "repeatedly threatened",
     "falsifier": "European smelter curtailment episodes show no abnormal relative behaviour "
                  "in aluminium once inventory and the aluminium-to-power ratio are controlled "
                  "for",
     "notes": "AN ACTOR CLASS. The individual owners are listed abroad and the two-lane order "
              "forbids hunting any of them; no share CFD appears in this pack"},
    {"name": "Hafrannsoknastofnun, the Marine and Freshwater Research Institute",
     "holds": "the stock assessments and the advice on which every Icelandic fishing quota is "
              "set, and the acoustic surveys that measure the pelagic stocks in-season",
     "forced_to": ("publish an advice for the coming fishing year each June",
                   "revise the capelin advice on the autumn and winter surveys, including to "
                   "ZERO, after the fishing year has already begun",
                   "follow a harvest control rule rather than a market view"),
     "when": "the June advice; the October and January acoustic surveys; the February allocation",
     "information": ("the survey result before it is published, which is days, not months",),
     "constraints": ("a scientific procedure it cannot deviate from for economic reasons",
                     "survey vessels and weather windows in the North Atlantic winter"),
     "instruments": ("SOYBEAN", "EURNOK"),
     "counterparties": ("the Ministry that sets the quota", "the quota holders",
                        "the international coastal-state negotiations on shared stocks"),
     "observables": ("the advice documents and their dates",
                     "the acoustic survey reports", "the resulting quota allocations"),
     "impact": "A SCIENTIFIC MEASUREMENT THAT IS ALSO A DATED SUPPLY SHOCK. Capelin is reduced "
               "to fishmeal and fish oil, which substitute for soymeal in aquaculture feed, so "
               "a zero season removes a real block of global feed protein",
     "persistence": "one fishing year per decision; a stock collapse persists for several",
     "falsifier": "capelin advice revisions of more than half the prior figure show no abnormal "
                  "behaviour in the feed complex once the Norwegian and Barents Sea pelagic "
                  "quotas of the same seasons are controlled for",
     "notes": "the advice is the EVENT of IS-D, and its ZERO option is what makes it worth a "
              "domain rather than a row"},
    {"name": "The Icelandic quota holders (the ITQ system's owners)",
     "holds": "permanent, transferable shares of the total allowable catch -- the country's "
              "largest privately held natural-resource right",
     "forced_to": ("fish within the allocation and land the catch against it",
                   "pay a resource rent (veidigjald) set by a formula the parliament revises",
                   "sell into the EU, UK and US markets in EUR, GBP and USD while paying costs "
                   "in krona"),
     "when": "the fishing year from 1 September; the pelagic seasons within it",
     "information": ("their own catch rates and the market's price before the statistics",),
     "constraints": ("the quota itself, which is set by someone else on a published clock",
                     "vessel capacity and the weather",
                     "a currency that moves against their revenue"),
     "instruments": ("EURUSD", "EURNOK", "SOYBEAN"),
     "counterparties": ("the European and Asian fish buyers", "the fishmeal and oil buyers",
                        "the state, through the resource rent"),
     "observables": ("Fiskistofa's landings by vessel and species",
                     "the export statistics' marine line", "the quota-transfer register"),
     "impact": "the export earnings half of the current account, in a country where the other "
               "half is metal and tourism; a quota cut is an FX revenue cut with a known date",
     "persistence": "a fishing year; the quota shares themselves are permanent",
     "falsifier": "Icelandic marine export swings carry no information for the feed complex or "
                  "for the North Atlantic comparators beyond the Norwegian volumes of the same "
                  "quarters",
     "notes": "AN ACTOR CLASS: the listed fishing companies are event-lane instruments and are "
              "never hunted here"},
    {"name": "The Icelandic pension funds",
     "holds": "assets far above GDP in a compulsory, fully funded system, with a statutory "
              "limit on the foreign-currency share",
     "forced_to": ("invest contributions every month whether or not there is anything to buy "
                   "domestically",
                   "hold the money AT HOME from 2008 to 2017, because the controls forbade "
                   "foreign purchases",
                   "diversify abroad once the controls lifted, which is a standing krona "
                   "outflow"),
     "when": "monthly contributions; the post-2017 rebuilding of the foreign share",
     "information": ("their own allocation intentions, which the central bank asks about",),
     "constraints": ("a statutory foreign-currency cap",
                     "a domestic market far too small to absorb the inflow, which distorted "
                     "every Icelandic asset price during the control era",
                     "actuarial return requirements"),
     "instruments": ("EURUSD", "EUSTX50", "EURNOK"),
     "counterparties": ("the global asset managers", "the domestic bond and equity market",
                        "the central bank, on the krona leg"),
     "observables": ("the monthly and quarterly asset and foreign-share statistics",
                     "the net foreign purchases series", "the cap's legislative changes"),
     "impact": "THE LARGEST STANDING KRONA FLOW IN THE COUNTRY, and its size was set by a "
               "statute rather than by a view -- which makes the statute's changes a natural "
               "experiment on forced home bias",
     "persistence": "structural; the rebuilding of the foreign share has run for years",
     "falsifier": "the lifting of the controls and the cap's changes show no measurable break "
                  "in the funds' foreign share or in the krona's trend, relative to the "
                  "comparator Nordic systems",
     "notes": "the reason IS-J is a domain: nine years of FORCED domestic investment is an "
              "experiment no free market would run"},
    {"name": "The Icelandic household with CPI-indexed debt",
     "holds": "mortgages a large share of which are indexed to the consumer price index, so "
              "inflation is added to the PRINCIPAL rather than paid in the coupon",
     "forced_to": ("absorb an inflation surprise as a balance-sheet event on a published date",
                   "choose between indexed and non-indexed debt, which is a leveraged view on "
                   "real rates most households are not equipped to take",
                   "act on a CPI that is published for the CURRENT month"),
     "when": "monthly, on the CPI release late in each month",
     "information": ("nothing the market does not have",),
     "constraints": ("an indexation mechanism written into the loan contract",
                     "a housing market in a country with one real city"),
     "instruments": ("EURNOK", "EUSTX50"),
     "counterparties": ("the banks and the Housing Fund", "the pension funds as mortgage "
                        "lenders"),
     "observables": ("the CPI and the indexation supplement (verdbaetur)",
                     "the split of new lending between indexed and non-indexed",
                     "the real and nominal government curves"),
     "impact": "the transmission of monetary policy runs through a PRINCIPAL rather than a "
               "payment, which changes the sign and the timing of the household's response and "
               "is why the Icelandic breakeven is a hedging price as much as an expectation",
     "persistence": "the loan's whole life; the lending-mix shift takes years",
     "falsifier": "the indexed share of new lending does not respond to the real-rate "
                  "differential between the indexed and non-indexed curves",
     "notes": "the reason IS-K exists; almost no other advanced economy indexes household debt "
              "at this scale"},
    {"name": "Isavia and the Keflavik transatlantic hub",
     "holds": "the country's only international airport and a hub position on the North "
              "Atlantic that carries far more passengers than the country has residents",
     "forced_to": ("publish passenger and departure statistics monthly",
                   "operate through a volcanic sequence on the same peninsula as the airport",
                   "size capacity years ahead of a demand that swings with seat supply"),
     "when": "monthly statistics; the violently seasonal summer peak",
     "information": ("forward bookings and scheduled seat capacity before the arrivals print",),
     "constraints": ("the seat capacity the airlines choose to fly",
                     "a runway 40 kilometres from an active volcanic system",
                     "an island with no alternative international gateway"),
     "instruments": ("XBRUSD", "EUSTX50"),
     "counterparties": ("the domestic and foreign carriers", "the tourism industry",
                        "the transatlantic connecting traffic"),
     "observables": ("monthly foreign departures, counted at the border",
                     "scheduled seat capacity", "the carriers' route announcements"),
     "impact": "the fastest, most complete read on the largest export earner of a country whose "
               "current account swings with it; it is also a jet-fuel demand observable on a "
               "single long-haul corridor",
     "persistence": "seasonal within a year; the capacity cycle runs years",
     "falsifier": "Keflavik departure surprises carry no information for the European travel "
                  "complex or for crude beyond the seat capacity already scheduled",
     "notes": "AN ACTOR AND A PHYSICAL OBSERVABLE; the carriers themselves are event-lane names"},
    {"name": "Vedurstofa Islands, the met office that prices two different risks",
     "holds": "the seismic network, the volcanic monitoring and the ICAO aviation colour code, "
              "AND the hydrological network that measures river discharge and snow",
     "forced_to": ("publish immediately and continuously, in both Icelandic and English",
                   "raise or lower the aviation colour code on evidence rather than on "
                   "consequence",
                   "forecast inflow for a power system with no import option"),
     "when": "continuously; colour-code changes within hours of an event",
     "information": ("the instrument network in real time, which it publishes -- so this actor "
                     "has NO informational advantage and is valuable precisely for that",),
     "constraints": ("physics and the instrument network's coverage",
                     "a public-safety mandate that outranks any market consideration"),
     "instruments": ("EUSTX50", "XALUSD", "XBRUSD"),
     "counterparties": ("the aviation authorities and the airlines",
                        "the power companies", "the civil protection agency"),
     "observables": ("the seismic feed and the colour code",
                     "river discharge and snow water equivalent",
                     "the eruption announcements and their locations"),
     "impact": "ONE AGENCY PUBLISHES THE LEADING INDICATOR OF TWO DIFFERENT DOMAINS: the water "
               "that bounds aluminium supply and the ash that closes airspace",
     "persistence": "an eruption's aviation impact is days to weeks; a water year is a year",
     "falsifier": "aviation colour-code escalations after 2021 show no abnormal European travel "
                  "or freight behaviour, which would say the Reykjanes eruptions are effusive "
                  "and ash-poor and therefore not a 2010 repeat -- a real and useful answer",
     "notes": "the 2010 and 2011 pair is the control built into IS-I: a smaller eruption closed "
              "airspace and a larger one did not, because ash and wind, not size, are the "
              "mechanism"},
    {"name": "The three Icelandic commercial banks",
     "holds": "the entire domestic banking system, rebuilt after 2008 from the wreckage of the "
              "old one, with the state still a large shareholder in part of it",
     "forced_to": ("intermediate a currency market of a handful of participants",
                   "hold capital and liquidity under an EEA framework applied by a supervisor "
                   "that is now inside the central bank",
                   "publish research, because in an economy this size they are the sell side"),
     "when": "quarterly results; continuously in the FX and bond markets",
     "information": ("the domestic payment and FX flow in near-real time",),
     "constraints": ("a domestic market with nowhere else to lend",
                     "concentration limits in an economy of a few large borrowers",
                     "a supervisor that is also the monetary authority"),
     "instruments": ("EURNOK", "EUSTX50"),
     "counterparties": ("the central bank", "the pension funds", "the fishing and energy "
                        "companies", "the households"),
     "observables": ("the published research and forecasts",
                     "the quarterly results and loan books",
                     "the bond issuance in foreign currency"),
     "impact": "their published forecasts ARE the Icelandic consensus, which is the only thing "
               "an Icelandic policy surprise can be measured against",
     "persistence": "structural",
     "falsifier": "the banks' published pre-meeting forecasts carry no information about the "
                  "committee's decision beyond the policy rule the bank itself publishes",
     "notes": "AN ACTOR CLASS; all three are listed and all three are event-lane instruments"},
    {"name": "The foreign carry investor in krona assets",
     "holds": "the 'glacier bond' (joklabref) position of 2005 to 2008, and after 2016 whatever "
              "the special reserve requirement permitted",
     "forced_to": ("accept a numeric, unremunerated reserve requirement on new inflows after "
                   "2016",
                   "hold offshore krona at a price different from the onshore one for nine "
                   "years",
                   "exit through an auction on the state's terms in 2016"),
     "when": "the 2005-2008 carry era; the 2016 auction; the post-2019 open regime",
     "information": ("nothing Iceland does not publish -- this actor is a price taker on "
                     "Icelandic information and a price maker on global risk appetite",),
     "constraints": ("the special reserve requirement's rate",
                     "a market too small to exit through",
                     "a legal regime that changed under it twice"),
     "instruments": ("EURNOK", "EURSEK", "EURUSD"),
     "counterparties": ("the central bank", "the three banks", "the other trapped holders"),
     "observables": ("the offshore-onshore price gap",
                     "the special reserve requirement's three rates",
                     "the auction's clearing rate", "the foreign holdings of krona bonds"),
     "impact": "this actor's entry built the 2005-2008 imbalance and its trapped exit defined "
               "the whole control era; the SRR is the instrument built specifically to stop it "
               "happening again",
     "persistence": "the overhang persisted for eight years",
     "falsifier": "the SRR's three rate steps show no measurable change in foreign holdings of "
                  "krona bonds relative to the Nordic comparators over the same months",
     "notes": "the counterparty IS-F is about, and the reason the instrument was invented"},
    {"name": "The Icelandic state as resource owner and as a post-crisis creditor",
     "holds": "the resource rent on fish, a large stake in the rebuilt banks, and -- through "
              "the 2015-16 stability contributions -- assets handed over by the failed banks' "
              "estates in exchange for an exemption from the controls",
     "forced_to": ("set the fishing fee by a formula parliament revises",
                   "sell down its bank stakes on a political rather than a market clock",
                   "publish every step in Stjornartidindi with a number and a date"),
     "when": "the annual budget; the fishing-fee revisions; the bank sell-downs",
     "information": ("the fiscal position and the estates' asset composition",),
     "constraints": ("an EEA legal framework the controls had to be justified within",
                     "a political economy in which the resource rent is permanently contested"),
     "instruments": ("EURNOK", "EUSTX50"),
     "counterparties": ("the failed banks' creditors", "the quota holders", "the EEA and the "
                        "IMF"),
     "observables": ("the statutes and their dates", "the stability contributions' size",
                     "the fishing fee", "the bank sell-down announcements"),
     "impact": "the stability contributions are how the control era was ENDED without a "
               "devaluation: the overhang was converted into state assets rather than released "
               "into the market",
     "persistence": "the settlement is permanent; the bank stakes are still unwinding",
     "falsifier": "the stability-contribution and control-lifting announcements carry no "
                  "information for the krona's path or for Icelandic asset prices beyond the "
                  "global risk environment of the same weeks",
     "notes": "a sovereign that solved a currency overhang with a balance-sheet transaction is "
              "a case with almost no parallel, and it is why IS-E is a case study domain"},
    {"name": "The fishmeal and fish-oil plants as the marginal energy consumer",
     "holds": "reduction capacity that turns capelin and other pelagic catch into meal and oil, "
              "running on interruptible electricity",
     "forced_to": ("process the catch while it is landed, which is a seasonal, unmovable peak",
                   "switch to OIL when the utility curtails interruptible power in a dry "
                   "winter -- the one case where an Icelandic water shortage creates real oil "
                   "demand",
                   "sell meal and oil into a global feed market they do not set"),
     "when": "the capelin and herring seasons; curtailment winters",
     "information": ("the landings they are receiving before the statistics",),
     "constraints": ("interruptible power contracts that are the first to be cut",
                     "a catch that arrives when it arrives",
                     "an aquaculture feed market whose substitute is soymeal"),
     "instruments": ("SOYBEAN", "XBRUSD", "XALUSD"),
     "counterparties": ("the fishing vessels", "Landsvirkjun", "the Norwegian and Chilean "
                        "aquaculture feed buyers"),
     "observables": ("landings of pelagic species", "the announced curtailments",
                     "the meal and oil export statistics"),
     "impact": "the JOIN between this pack's two physical domains: the same dry winter that "
               "cuts aluminium also cuts fishmeal power and pushes those plants onto oil, so a "
               "reservoir reading touches three executable symbols at once",
     "persistence": "a season",
     "falsifier": "curtailment winters show no abnormal Icelandic oil imports and no abnormal "
                  "fishmeal output relative to the landings of the same seasons",
     "notes": "an actor class that exists in this pack because it is the ONLY place the water "
              "year and the fish year meet"},
)

# --------------------------------------------------------------------------- domains
DOMAINS: tuple[dict[str, Any], ...] = (
    {"id": "IS-A", "title": "The hydrological year, reservoir levels and smelter curtailment",
     "objects": ("the published Thorisvatn and Halslon levels and their seasonal norms",
                 "river discharge and snow water equivalent as the leading half of the inflow",
                 "the declared curtailment episodes in `CURTAILMENT_EPISODES`",
                 "national electricity consumption by large users"),
     "conditions": ("the phase from `hydrological_year_phase(day)`: FILLING, DRAWDOWN or TROUGH",
                    "the level's deviation from its own seasonal norm, in quantiles",
                    "the curtailment state from `curtailment_state(day)`",
                    "the water year from `hydrological_year(day)`, which no calendar year "
                    "aligns with"),
     "instruments": ("XALUSD", "XNGUSD", "EURNOK"),
     "controls": ("the global aluminium inventory and the European power price in the same "
                  "weeks, which are the larger drivers and must be removed before Iceland is "
                  "visible at all",
                  "the same reservoir statistic in years with no curtailment",
                  "a randomised-week null inside the same hydrological phase"),
     "notes": "A WEATHER SERIES THAT BOUNDS A WORLD COMMODITY'S SUPPLY. The honest prior is "
              "that 2% of world capacity is hard to see; the pack says so and measures anyway"},
    {"id": "IS-B", "title": "Power contracts and the power-to-metal economy",
     "objects": ("the announced contract renegotiations and their pricing basis",
                 "the LME-linked versus fixed share of contracted power",
                 "the smelters' share of national electricity consumption",
                 "the aluminium export line in tonnes and value"),
     "conditions": ("a renegotiation announcement against a quiet period",
                    "the LME level relative to the contracts' historic linkage range",
                    "the curtailment state"),
     "instruments": ("XALUSD", "EURUSD"),
     "controls": ("Norwegian and Canadian hydro-powered smelters over the same periods, which "
                  "are the only comparable producers on earth",
                  "the same windows in periods with no announcement",
                  "the global aluminium price itself, as the null"),
     "notes": "THE CONTRACT PRICE IS CONFIDENTIAL and the pack says so: what is readable is the "
              "renegotiation's date, the curtailment clause and the consumption share"},
    {"id": "IS-C", "title": "Stranded power versus gas-exposed smelting: the curtailment spread",
     "objects": ("European smelter curtailment announcements and their dates",
                 "the European power and gas price relative to the aluminium price",
                 "Icelandic production over the same months, which does NOT curtail for price",
                 "the European duty-paid physical premium"),
     "conditions": ("a European power-price regime: pre-2021, the 2021-23 crisis, after it",
                    "whether a European curtailment was announced in the window",
                    "the aluminium-to-power ratio's quantile",
                    "the Icelandic curtailment state, which is a WATER event and not a price one"),
     "instruments": ("XALUSD", "XNGUSD", "EUSTX50"),
     "controls": ("the aluminium-to-power ratio itself, which is the mechanism's own driver and "
                  "must be conditioned on rather than ignored",
                  "Chinese production over the same months, which is an order of magnitude "
                  "larger and dominates world supply",
                  "the same windows in the pre-2021 power regime"),
     "notes": "XNGUSD IS HENRY HUB AND EUROPE PRICES OFF TTF. This domain's gas leg is "
              "CONTROL-GRADE and the pack refuses to call it a proxy; the mechanism is a SPREAD "
              "between a gas-exposed and a non-gas-exposed producer and never a level effect"},
    {"id": "IS-D", "title": "The capelin and cod quota clock",
     "objects": ("the June advice for the fishing year",
                 "the October and January acoustic surveys and the revisions they produce",
                 "the zero-capelin seasons in `CAPELIN_ZERO_SEASONS`",
                 "landings by species from Fiskistofa and the meal and oil export line"),
     "conditions": ("the window from `capelin_calendar(year)`: advice, survey or allocation",
                    "a revision larger than half the prior figure, against a small one",
                    "a zero season against a normal one",
                    "the fishing year from `fishing_year(day)`"),
     "instruments": ("SOYBEAN", "EURNOK", "EURUSD"),
     "controls": ("the Norwegian and Barents Sea pelagic quotas of the same seasons, which is "
                  "the rest of the North Atlantic supply",
                  "the Peruvian anchoveta season, which is the world's dominant fishmeal source "
                  "and would swamp any Icelandic effect",
                  "a randomised-date null on the survey dates"),
     "notes": "A SCIENTIFIC MEASUREMENT THAT IS A DATED SUPPLY SHOCK, with a ZERO option that "
              "has actually been exercised in consecutive seasons"},
    {"id": "IS-E", "title": "The capital-control era and why no pooled ISK study is valid",
     "objects": ("the era boundaries in `CONTROL_ERAS`",
                 "the offshore and onshore krona prices side by side",
                 "the 2016 auction's clearing rate against the onshore rate",
                 "the stability contributions that ended the overhang"),
     "conditions": ("the state from `capital_controls_state(day)`",
                    "whether the sample spans a boundary, from `controls_invalidate(start, end)`",
                    "the offshore-onshore gap's size"),
     "instruments": ("EURNOK", "EURSEK", "EUSTX50"),
     "controls": ("Norway and Sweden over the same years: the same region, the same shocks, no "
                  "controls",
                  "the pre-2008 era, in which the same currency was a carry DESTINATION",
                  "a placebo boundary drawn at a date with no legal change"),
     "notes": "THE MOST IMPORTANT DOMAIN IN THIS PACK FOR A STUDY'S VALIDITY. A krona series "
              "spanning 2008-11-28 or 2017-03-14 is two different objects with one name, and "
              "`controls_invalidate` exists so a study has to look"},
    {"id": "IS-F", "title": "The special reserve requirement as an explicit capital-flow tool",
     "objects": ("the three dated rates in `SRR_SCHEDULE`: 40%, 20% and 0%",
                 "foreign holdings of krona bonds across each step",
                 "the krona's carry-adjusted return across each step",
                 "the rules as published instruments in the gazette"),
     "conditions": ("the rate from `srr_rate(day)`",
                    "the global carry environment, measured on the comparator currencies",
                    "the window around each step against the quiet months between them"),
     "instruments": ("EURNOK", "EURSEK"),
     "controls": ("Norway and Sweden over the same months, which had no such instrument",
                  "the months between the steps, when the rate was constant",
                  "a randomised-date null on the three step dates"),
     "notes": "A RARE, NUMERIC, TWO-SIDED, DATED CAPITAL-FLOW-MANAGEMENT INSTRUMENT. The sign "
              "of its effect is genuinely contested, which is what makes it worth testing"},
    {"id": "IS-G", "title": "Sedlabanki intervention, reserves and a market with no depth",
     "objects": ("the monthly FX transactions the bank names itself",
                 "the reserve level and its adequacy metrics",
                 "the regular purchase programmes when they have run",
                 "the turnover of the whole interbank market, which the bank is most of"),
     "conditions": ("the sign and size of the month's named intervention",
                    "the capital-control state, because intervention means different things "
                    "inside and outside controls",
                    "the tourism season, which is the dominant seasonal inflow"),
     "instruments": ("EURNOK", "EURSEK", "EURUSD"),
     "controls": ("Norges Bank's ANNOUNCED daily FX amount over the same months, which is the "
                  "same instrument with the opposite disclosure regime",
                  "months matched on global risk appetite with no intervention",
                  "a randomised-month null on the intervention flag"),
     "notes": "the bank publishes its own intervention, which almost none do; the krona is "
              "absent from the broker, so this domain's output is a regime label and a "
              "transmission seed rather than a cell the desk trades directly"},
    {"id": "IS-H", "title": "Keflavik arrivals: a counted monthly export series",
     "objects": ("foreign departures counted at the border, monthly",
                 "scheduled seat capacity as the leading indicator",
                 "the declared tourism shocks in `TOURISM_SHOCKS`",
                 "the travel line of the balance of payments"),
     "conditions": ("the season from `keflavik_season(day)`",
                    "the shock state from `tourism_shock_state(day)`",
                    "the year-on-year change in scheduled seat capacity"),
     "instruments": ("XBRUSD", "EUSTX50", "EURUSD"),
     "controls": ("Norwegian and Nordic arrivals over the same months, which share the North "
                  "Atlantic travel cycle",
                  "the same months in years with no capacity shock",
                  "a seasonally matched null drawn from the same month across years"),
     "notes": "the largest export earner of a 390,000-person economy, COUNTED rather than "
              "surveyed and published within days -- and violently seasonal, which is the "
              "first thing a study must condition on"},
    {"id": "IS-I", "title": "Reykjanes: eruptions as dated supply and aviation risk",
     "objects": ("the dated events in `ERUPTIONS` and the aviation colour code",
                 "the 2010 and 2011 pair, which is the built-in control",
                 "the Grindavik evacuation and the Svartsengi plant's exposure",
                 "European airspace and air-freight disruption"),
     "conditions": ("the regime from `reykjanes_state(day)`: the 2021 sequence or before it",
                    "the colour code reached: GREEN, YELLOW, ORANGE or RED",
                    "whether the eruption is explosive and ash-producing or effusive",
                    "the prevailing wind direction, which is what turned 2010 into a closure "
                    "and left 2011 alone"),
     "instruments": ("EUSTX50", "XBRUSD", "XALUSD"),
     "controls": ("the 2011 Grimsvotn eruption, which was LARGER than 2010 and closed almost "
                  "nothing -- the single cleanest control in this pack",
                  "European airline capacity and weather over the same weeks",
                  "a randomised-date null on the eruption dates"),
     "notes": "ASH AND WIND ARE THE MECHANISM, NOT SIZE. A study that treats eruption magnitude "
              "as the treatment is measuring the wrong variable, and the 2010/2011 pair proves it"},
    {"id": "IS-J", "title": "The pension funds' foreign-asset constraint and the outflow",
     "objects": ("assets, the foreign-currency share and net foreign purchases",
                 "the statutory cap and its legislative changes",
                 "the nine years of FORCED domestic investment behind the controls",
                 "the post-2017 rebuilding of the foreign share"),
     "conditions": ("the capital-control state",
                    "the distance of the foreign share from the statutory cap",
                    "the months around a legislative change against the quiet months"),
     "instruments": ("EURUSD", "EUSTX50", "EURNOK"),
     "controls": ("the Norwegian, Swedish and Danish pension systems over the same years, none "
                  "of which was constrained this way",
                  "the pre-2008 era, when the funds were free",
                  "a randomised-month null on the legislative dates"),
     "notes": "NINE YEARS OF FORCED HOME BIAS IS AN EXPERIMENT NO FREE MARKET WOULD RUN, and "
              "its unwinding is the largest standing krona flow in the country"},
    {"id": "IS-K", "title": "CPI indexation: inflation added to the principal",
     "objects": ("the CPI, published for the CURRENT month",
                 "the indexation supplement and the indexed loan stock",
                 "the real (RIKS) and nominal (RIKB) government curves and the breakeven",
                 "the split of new lending between indexed and non-indexed"),
     "conditions": ("the level and change of the breakeven",
                    "the indexed share of new lending, in quantiles",
                    "whether a wage round was open in the window"),
     "instruments": ("EURNOK", "EUSTX50"),
     "controls": ("the equivalent breakeven in a non-indexing Nordic economy",
                  "the periods before indexation's share fell materially",
                  "a randomised-month null on the CPI release dates"),
     "notes": "the Icelandic breakeven is a HEDGING PRICE as much as an expectation, because a "
              "household sector with indexed debt has a structural demand for the indexed leg; "
              "reading it as a clean inflation expectation is the standard error here"},
    {"id": "IS-L", "title": "An absent currency and the North Atlantic control plane",
     "objects": ("EURNOK and EURSEK as the small-open-economy comparators",
                 "the Icelandic trade-weighted index, as an INPUT and never a leg",
                 "the current account's three components: metal, fish and tourism",
                 "the residual of Icelandic conditions after the Nordic factor"),
     "conditions": ("the capital-control state",
                    "the terms of trade: aluminium and fish prices against import prices",
                    "global risk appetite, measured on the comparators"),
     "instruments": ("EURNOK", "EURSEK", "EURUSD"),
     "controls": ("the comparators themselves, which is the point of the domain",
                  "the periods in which the Icelandic and Nordic cycles diverged for known "
                  "reasons",
                  "a block-permutation null on the residual"),
     "notes": "THE KRONA IS NOT A BROKER SYMBOL AND IS NEVER PROXIED. This domain exists to "
              "say what EURNOK and EURSEK are FOR here -- controls for a North Atlantic factor, "
              "not stand-ins for a currency the desk cannot trade"},
    {"id": "IS-M", "title": "Freight and the island logistics plane",
     "objects": ("container volumes through Faxafloahafnir and the other ports",
                 "air freight through Keflavik",
                 "the two domestic carriers' North Atlantic schedules",
                 "import prices and the freight component of them"),
     "conditions": ("the season, because both sea and air capacity are seasonal here",
                    "whether a global freight disruption was open",
                    "the fuel price regime"),
     "instruments": ("XBRUSD", "EUSTX50", "SOYBEAN"),
     "controls": ("the global container indices and the Norwegian ports over the same quarters",
                  "the same months in years with no disruption",
                  "a randomised-quarter null"),
     "notes": "an island with no land border imports and exports through two chokepoints, which "
              "makes throughput close to a complete trade census -- and makes freight a real "
              "cost channel rather than a narrative one"},
)

# --------------------------------------------------------------------------- the cell lattice
CELL_FAMILIES: dict[str, str] = {
    "IS-A": "supply_constraint", "IS-B": "administered_price", "IS-C": "substitution",
    "IS-D": "administered_event", "IS-E": "regime_break", "IS-F": "capital_flow_management",
    "IS-G": "intervention", "IS-H": "seasonal_flow", "IS-I": "event_risk",
    "IS-J": "institutional_flow", "IS-K": "release_surprise", "IS-L": "residual",
    "IS-M": "physical_flow",
}
CELL_HORIZONS: dict[str, str] = {
    "IS-A": "2 to 12 weeks", "IS-B": "1 to 2 quarters", "IS-C": "1 to 8 weeks",
    "IS-D": "0 to 10 sessions", "IS-E": "1 to 3 quarters", "IS-F": "1 to 2 quarters",
    "IS-G": "1 to 3 months", "IS-H": "1 to 3 months", "IS-I": "0 to 10 sessions",
    "IS-J": "1 to 4 quarters", "IS-K": "0 to 5 sessions", "IS-L": "1 to 3 months",
    "IS-M": "1 to 2 quarters",
}


def cells() -> tuple[dict[str, Any], ...]:
    """The testable cells this pack mints: domain x executable instrument x named condition.

    Every condition is one this pack's own data plane can evaluate: each is computed by a
    function in this module (`hydrological_year_phase`, `curtailment_state`,
    `capital_controls_state`, `srr_rate`, `keflavik_season`, `reykjanes_state`,
    `fishing_year`) or read from a dataset row declared in `DATASETS`. Iceland mints fewer cells
    than a large economy and that is correct: a country with one currency the desk cannot trade
    earns its cells through PHYSICAL channels, and there are thirteen of them, not fifty.
    """
    out: list[dict[str, Any]] = []
    for row in DOMAINS:
        did = str(row["id"])
        family = CELL_FAMILIES.get(did, "residual")
        horizon = CELL_HORIZONS.get(did, "1 to 5 sessions")
        control = str(row["controls"][0])
        symbols = [s for s in row["instruments"] if s in EXECUTABLE_SET]
        for sym in symbols:
            for i, condition in enumerate(row["conditions"], start=1):
                out.append({
                    "cell_id": f"{did}:{sym}:C{i}",
                    "domain": did, "symbol": sym, "condition": str(condition),
                    "mechanism_family": family, "horizon": horizon, "control": control,
                    "why": f"{row['title']} measured on {sym}, conditioned on {condition}",
                })
    return tuple(out)


CELLS: tuple[dict[str, Any], ...] = cells()

# --------------------------------------------------------------------------- miners
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    {"name": "is_water_year", "domain_ids": ("IS-A", "IS-B"), "kind": "physical",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.is.pack:mine_water_year",
     "needs": ("LV:midlunarlon reservoir levels", "XALUSD, XNGUSD D1 bars"),
     "notes": "the phase and the curtailment state as conditions, with the aluminium inventory "
              "as the control that must be removed first"},
    {"name": "is_curtailment_spread", "domain_ids": ("IS-C",), "kind": "macro",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.is.pack:mine_curtailment_spread",
     "needs": ("European power and gas prices", "XALUSD, XNGUSD D1 bars"),
     "notes": "a SPREAD between a gas-exposed and a non-gas-exposed producer, never a level"},
    {"name": "is_quota_clock", "domain_ids": ("IS-D",), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.is.pack:mine_quota_clock",
     "needs": ("`capelin_calendar`", "HAF:radgjof advice documents", "SOYBEAN D1 bars"),
     "notes": "the January survey is the event; the Peruvian anchoveta season is the control "
              "that would swamp it"},
    {"name": "is_control_eras", "domain_ids": ("IS-E", "IS-F", "IS-J"), "kind": "regime",
     "cadence_s": 604800.0, "steerable": False, "wired": False,
     "entry": "countries.is.pack:mine_control_eras",
     "needs": ("`capital_controls_state`", "`srr_rate`", "EURNOK, EURSEK D1 bars"),
     "notes": "the era labels every other Icelandic study must condition on; it emits the "
              "boundaries rather than a result"},
    {"name": "is_tourism_season", "domain_ids": ("IS-H", "IS-M"), "kind": "seasonal",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.is.pack:mine_tourism_season",
     "needs": ("FMS:brottfarir monthly departures", "XBRUSD, EUSTX50 D1 bars"),
     "notes": "violently seasonal, so the season is the first condition and never an afterthought"},
    {"name": "is_eruption_risk", "domain_ids": ("IS-I",), "kind": "event",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.is.pack:mine_eruption_risk",
     "needs": ("VI:litakodi aviation colour code", "EUSTX50, XBRUSD H1 bars"),
     "notes": "the 2010/2011 pair is the built-in control: ash and wind, not magnitude"},
    {"name": "is_holiday_clock", "domain_ids": ("IS-K", "IS-L"), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": False, "wired": False,
     "entry": "countries.is.pack:mine_holiday_clock",
     "needs": ("`market_holidays`, `sumardagurinn_fyrsti`", "EURNOK, EUSTX50 H1 bars"),
     "notes": "Iceland keeps NO daylight saving, so the UTC session is fixed all year while "
              "every European counterpart's moves twice"},
    {"name": "is_transmission_seeds",
     "domain_ids": ("IS-A", "IS-C", "IS-D", "IS-G", "IS-I", "IS-M"), "kind": "transfer",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.is.pack:mine_transmission_seeds",
     "needs": ("TRANSMISSION_EDGES_SEED", "INTERACTIONS"),
     "notes": "the pack's map as HYPOTHESIS seeds, deduplicated by the registry"},
)
MINER_DOMAINS: dict[str, tuple[str, ...]] = {
    "central_bank_surprise": ("IS-G", "IS-K"), "release_surprise": ("IS-K", "IS-H"),
    "calendar_settlement": ("IS-D", "IS-L"), "holiday_liquidity": ("IS-L",),
    "positioning": ("IS-J", "IS-F"), "carry_funding": ("IS-F", "IS-G"),
    "corporate_flow": ("IS-B", "IS-M"), "institutional_flow": ("IS-J", "IS-G"),
    "equity_mechanics": ("IS-L",), "derivatives_expiry": ("IS-C",),
    "failure": ("IS-E", "IS-I"), "residual": ("IS-L", "IS-A"),
    "transfer": ("IS-C", "IS-D"), "scouts": ("IS-A", "IS-I"),
    "session_microstructure": ("IS-L",),
}

# --------------------------------------------------------------------------- transmission
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    {"id": "IS-E1", "source": "Icelandic reservoir levels below their seasonal norm",
     "target": "XALUSD", "targets": ("XALUSD",), "to_country": "global", "sign": "+",
     "mechanism": "a poor water year triggers the curtailment clause in the smelters' power "
                  "contracts; the potlines cannot be throttled cheaply, so curtailment is a "
                  "real and near-immediate cut in about 2% of world primary supply",
     "horizon": "2 to 12 weeks", "horizon_class": "multi_day", "lag_days": 14.0,
     "actor": "Landsvirkjun and the three smelters",
     "constraint": "no interconnector: the power cannot be imported and the metal cannot be "
                   "made without it",
     "flow": "physical primary aluminium output",
     "condition": "DRAWDOWN or TROUGH phase with the level in the bottom quintile of its own "
                  "seasonal history",
     "control": "the global aluminium inventory and the European power price in the same weeks; "
                "the same reservoir readings in years with no curtailment",
     "falsifier": "announced Icelandic curtailments show no abnormal XALUSD behaviour relative "
                  "to inventory-matched controls -- which would say 2% is too small to see",
     "evidence": "HYPOTHESIS"},
    {"id": "IS-E2", "source": "A European power and gas price spike",
     "target": "XALUSD", "targets": ("XALUSD", "XNGUSD"), "to_country": "global", "sign": "+",
     "mechanism": "European smelters price power off gas and curtail when the "
                  "aluminium-to-power ratio falls; ICELANDIC SMELTERS DO NOT, because their "
                  "cost is contracted renewable power. The mechanism is therefore the SPREAD "
                  "between the two producer types and the European physical premium",
     "horizon": "1 to 8 weeks", "horizon_class": "multi_day", "lag_days": 7.0,
     "actor": "the European smelters that curtail and the Icelandic ones that do not",
     "constraint": "the aluminium-to-power ratio and the potline's restart cost",
     "flow": "European primary capacity going offline",
     "condition": "the aluminium-to-power ratio in the bottom quintile, in the 2021-23 regime "
                  "or after it",
     "control": "Chinese production over the same months, which is an order of magnitude larger; "
                "the pre-2021 power regime",
     "falsifier": "European curtailment announcements carry no information for aluminium once "
                  "inventory and the aluminium-to-power ratio are controlled for",
     "evidence": "HYPOTHESIS",
     "notes": "XNGUSD IS HENRY HUB and Europe prices off TTF, so the gas leg here is "
              "CONTROL-GRADE; the pack declares the weakness on the edge's own face"},
    {"id": "IS-E3", "source": "The January capelin acoustic survey and its advice revision",
     "target": "SOYBEAN", "targets": ("SOYBEAN",), "to_country": "global", "sign": "-",
     "mechanism": "capelin is reduced to fishmeal and fish oil, which substitute for soymeal in "
                  "aquaculture and livestock feed; a quota revision of several times, or to "
                  "zero, removes or restores a real block of global feed protein on a dated day",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 2.0,
     "actor": "Hafrannsoknastofnun and the reduction plants",
     "constraint": "a harvest control rule the institute cannot deviate from",
     "flow": "fishmeal and fish oil supply",
     "condition": "a revision larger than half the prior figure, or a zero season",
     "control": "the Peruvian anchoveta season, which dominates world fishmeal and would swamp "
                "any Icelandic effect; the Norwegian and Barents pelagic quotas",
     "falsifier": "large capelin revisions show no abnormal feed-complex behaviour once the "
                  "Peruvian season and the Norwegian quotas are controlled for",
     "evidence": "HYPOTHESIS"},
    {"id": "IS-E4", "source": "The June cod advice and the 1 September fishing-year start",
     "target": "EURNOK", "targets": ("EURNOK", "EURUSD"), "to_country": "no", "sign": "+",
     "mechanism": "Iceland and Norway together are most of the North Atlantic cod supply; the "
                  "two advice processes are separate, dated and scientifically linked through "
                  "shared stocks and shared markets, so one country's quota is the other's "
                  "price environment",
     "horizon": "1 to 3 months", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "the two national institutes and the coastal-state negotiations",
     "constraint": "the fishing year's legal boundary",
     "flow": "whitefish export supply into the European market",
     "condition": "a June advice that changes the total allowable catch by more than its own "
                  "historical interquartile range",
     "control": "the Barents Sea joint quota in the same year; the euro-area whitefish demand",
     "falsifier": "Icelandic cod advice changes carry no information for the Norwegian export "
                  "plane beyond the Barents quota already announced",
     "evidence": "HYPOTHESIS"},
    {"id": "IS-E5", "source": "The special reserve requirement's three rate steps",
     "target": "EURNOK", "targets": ("EURNOK", "EURSEK"), "to_country": "global", "sign": "+",
     "mechanism": "an unremunerated reserve requirement on new foreign inflows into krona "
                  "assets is a numeric tax on carry; raising it should cut the inflow and "
                  "removing it should restore it, and the three dated steps are three "
                  "experiments",
     "horizon": "1 to 2 quarters", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "the central bank and the foreign carry investor",
     "constraint": "the rule itself, published with a number and a date",
     "flow": "foreign purchases of krona bonds and deposits",
     "condition": "the three step dates and the windows around them",
     "control": "Norway and Sweden over the same months, which had no such instrument; the "
                "quiet months between the steps",
     "falsifier": "the three steps show no measurable change in foreign holdings of krona bonds "
                  "relative to the Nordic comparators over the same months",
     "evidence": "HYPOTHESIS"},
    {"id": "IS-E6", "source": "The capital controls' imposition and lifting",
     "target": "EURNOK", "targets": ("EURNOK", "EURSEK", "EUSTX50"), "to_country": "global",
     "sign": "+",
     "mechanism": "nine years in which residents could not buy foreign assets and a trapped "
                  "offshore krona traded at a different price from the onshore one; the "
                  "boundaries are the largest regime breaks in any currency series this "
                  "department carries",
     "horizon": "1 to 3 quarters", "horizon_class": "multi_day", "lag_days": 0.0,
     "actor": "the state, the central bank and the trapped holders",
     "constraint": "an EEA legal framework the controls had to be justified within",
     "flow": "the entire capital account",
     "condition": "the windows around 2008-11-28, 2016-06-16 and 2017-03-14",
     "control": "Norway and Sweden over the same years; a placebo boundary at a date with no "
                "legal change",
     "falsifier": "the control boundaries show no break in Icelandic asset prices or in the "
                  "Nordic comparators' relationship to them",
     "evidence": "HYPOTHESIS"},
    {"id": "IS-E7", "source": "Keflavik foreign departures against scheduled seat capacity",
     "target": "EUSTX50", "targets": ("EUSTX50", "XBRUSD"), "to_country": "global", "sign": "+",
     "mechanism": "a counted monthly series on the largest export earner of a tiny economy, and "
                  "a jet-fuel demand observable on one long-haul corridor; the executable legs "
                  "are the European travel complex and crude, both of which are far larger",
     "horizon": "1 to 3 months", "horizon_class": "multi_day", "lag_days": 10.0,
     "actor": "Isavia and the carriers",
     "constraint": "seat capacity fixed a season ahead",
     "flow": "passengers and the jet fuel that moves them",
     "condition": "a year-on-year departure surprise relative to scheduled capacity",
     "control": "Nordic arrivals over the same months; the European airline capacity data",
     "falsifier": "Keflavik departure surprises carry no information for the European travel "
                  "complex beyond the scheduled capacity already published",
     "evidence": "HYPOTHESIS",
     "notes": "DECLARED WEAK: one small country's arrivals cannot move a European index, and "
              "the value of the row is that it is dated, counted and falsifiable"},
    {"id": "IS-E8", "source": "A Reykjanes eruption reaching an ORANGE or RED aviation code",
     "target": "EUSTX50", "targets": ("EUSTX50", "XBRUSD"), "to_country": "global", "sign": "-",
     "mechanism": "an ash-producing eruption under the right wind closes European airspace, as "
                  "in April 2010; the Reykjanes sequence has so far been effusive and ash-poor, "
                  "which is precisely the hypothesis to test rather than assume",
     "horizon": "0 to 10 sessions", "horizon_class": "intraday", "lag_days": 0.0,
     "actor": "Vedurstofa and the aviation authorities",
     "constraint": "ash and wind, not magnitude",
     "flow": "European air traffic and air freight",
     "condition": "a colour-code escalation to ORANGE or RED",
     "control": "the 2011 Grimsvotn eruption, which was larger than 2010 and closed almost "
                "nothing; European airline capacity and weather in the same weeks",
     "falsifier": "colour-code escalations after 2021 show no abnormal European travel or "
                  "freight behaviour, which would confirm the sequence is ash-poor",
     "evidence": "MEASURED_ELSEWHERE",
     "notes": "MEASURED_ELSEWHERE because the 2010 closure's economic cost is a documented "
              "public estimate; the desk has reproduced none of it and says so"},
    {"id": "IS-E9", "source": "The pension funds' post-2017 rebuilding of the foreign share",
     "target": "EURUSD", "targets": ("EURUSD", "EUSTX50"), "to_country": "global", "sign": "+",
     "mechanism": "a compulsory, fully funded system with assets far above GDP was forced home "
                  "for nine years and has been diversifying abroad since; that is a standing, "
                  "one-directional outflow whose size was set by a statute",
     "horizon": "1 to 4 quarters", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "the Icelandic pension funds",
     "constraint": "a statutory foreign-currency cap and an actuarial return requirement",
     "flow": "net foreign purchases of securities",
     "condition": "quarters in which the foreign share moved by more than its own interquartile "
                  "range, or a legislative change to the cap",
     "control": "the other Nordic pension systems over the same years; the pre-2008 era",
     "falsifier": "the control lifting and the cap's changes show no break in the funds' "
                  "foreign share relative to the comparator systems",
     "evidence": "HYPOTHESIS"},
    {"id": "IS-E10", "source": "A curtailment winter forcing the fishmeal plants onto oil",
     "target": "XBRUSD", "targets": ("XBRUSD", "SOYBEAN"), "to_country": "global", "sign": "+",
     "mechanism": "the reduction plants run on INTERRUPTIBLE power and are the first to be cut; "
                  "when they are, they burn oil instead. The same dry winter therefore cuts "
                  "aluminium, cuts fishmeal output and creates a small, real oil demand -- "
                  "three executable symbols from one reservoir reading",
     "horizon": "2 to 12 weeks", "horizon_class": "multi_day", "lag_days": 14.0,
     "actor": "the reduction plants and Landsvirkjun",
     "constraint": "the interruptible clause in the power contract",
     "flow": "fuel oil imports and fishmeal output",
     "condition": "a declared curtailment episode overlapping a pelagic season",
     "control": "the same seasons with no curtailment; the landings volume itself",
     "falsifier": "curtailment winters show no abnormal Icelandic oil imports and no abnormal "
                  "fishmeal output relative to the landings of the same seasons",
     "evidence": "HYPOTHESIS",
     "notes": "DECLARED TINY in absolute terms; it is carried because it is the only place the "
              "water year and the fish year physically meet, which makes it a JOIN and not a "
              "trade"},
    {"id": "IS-E11", "source": "The Icelandic terms of trade: metal in USD, fish in EUR",
     "target": "EURUSD", "targets": ("EURUSD", "XALUSD"), "to_country": "global", "sign": "+",
     "mechanism": "an economy whose two goods exports are priced in DIFFERENT currencies has a "
                  "terms-of-trade exposure to EURUSD itself, not merely to its own exchange "
                  "rate; aluminium settles in dollars and fish sells into the euro and sterling "
                  "markets",
     "horizon": "1 to 3 months", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "the smelters and the quota holders",
     "constraint": "the currency of the contract, which neither chooses",
     "flow": "export receipts in two currencies against costs in one",
     "condition": "quarters with a large EURUSD move and a stable aluminium price, which "
                  "separates the currency effect from the commodity one",
     "control": "Norway, whose exports are dollar-priced on both legs; the aluminium price alone",
     "falsifier": "Icelandic export values carry no EURUSD sensitivity beyond the aluminium "
                  "price's own dollar exposure",
     "evidence": "HYPOTHESIS"},
)

#: INTERACTION MINERS -- the other country packs Iceland has a MEASURABLE interaction with.
INTERACTIONS: tuple[dict[str, Any], ...] = (
    {"with": "no",
     "mechanism": "TWO PLANES AT ONCE. Norway and Iceland are the North Atlantic's two "
                  "hydro-powered aluminium producers and its two largest whitefish and pelagic "
                  "fishing nations; they share stocks, share markets, and negotiate quotas with "
                  "each other as coastal states. Norway also runs an ANNOUNCED daily FX "
                  "programme where Iceland runs an unannounced monthly one",
     "observable": "the Barents Sea joint quota against the Icelandic advice; Norwegian hydro "
                   "reservoir levels against Icelandic ones; Norges Bank's announced amount "
                   "against Sedlabanki's published intervention",
     "targets": ("XALUSD", "SOYBEAN", "EURNOK"),
     "control": "EURSEK as the third Nordic leg, which has neither fish nor smelters",
     "why": "the only other country on this desk whose aluminium is hydro-powered AND whose "
            "fisheries are quota-managed on a dated scientific clock"},
    {"with": "ca",
     "mechanism": "Canada is the world's other large stranded-hydro aluminium economy: Quebec's "
                  "smelters run on contracted hydro at a cost that does not move with gas, "
                  "exactly as Iceland's do. Together they are the non-curtailing share of "
                  "Western supply, and they are also the two North Atlantic cod-history "
                  "economies -- one of which fished its stock to collapse",
     "observable": "Quebec reservoir and generation data against Icelandic reservoir data; the "
                   "two countries' combined share of non-gas-exposed Western smelting",
     "targets": ("XALUSD", "XNGUSD"),
     "control": "Chinese production, which is an order of magnitude larger than both and "
                "dominates the world balance",
     "why": "the curtailment-spread mechanism of IS-C needs BOTH non-curtailing producers to be "
            "measured, or the effect is attributed to Iceland alone and overstated"},
    {"with": "au",
     "mechanism": "Australia is the world's largest bauxite exporter and a major alumina "
                  "refiner, which is the INPUT side of the same metal Iceland smelts. An "
                  "alumina supply shock raises the smelter's variable cost everywhere INCLUDING "
                  "Iceland, which is the one cost channel Icelandic smelters are not insulated "
                  "from",
     "observable": "Australian alumina and bauxite export volumes and any export restriction "
                   "against Icelandic smelter output and the aluminium price",
     "targets": ("XALUSD", "EURUSD"),
     "control": "Chinese refining capacity and the bauxite supply from Guinea over the same "
                "quarters",
     "why": "Iceland's cost insulation is on the POWER leg only; alumina is the leg that still "
            "reaches it, and Australia is where that leg comes from"},
    {"with": "ea",
     "mechanism": "Iceland is inside the European Economic Area but outside the EU and outside "
                  "the Common Fisheries Policy: it takes the single market's rules, sells fish "
                  "into it under a tariff arrangement, and is bound by EEA financial regulation "
                  "including the rules its capital controls had to be justified against",
     "observable": "EEA financial regulation adopted into Icelandic law; the fish tariff quotas "
                   "and their utilisation; euro-area demand for Icelandic exports",
     "targets": ("EUSTX50", "EURUSD", "SOYBEAN"),
     "control": "Norway, which has the identical EEA status and the identical tariff position",
     "why": "the legal environment of IS-E and IS-F is a European one, and a study that treats "
            "the controls as a purely domestic decision misses the constraint they were "
            "designed within"},
    {"with": "uk",
     "mechanism": "the United Kingdom is a principal market for Icelandic whitefish and a "
                  "principal source of tourists, and the two countries' fishing relationship is "
                  "the oldest and most contested in the North Atlantic. Post-Brexit the UK "
                  "negotiates its own quota and tariff position with Iceland directly",
     "observable": "UK whitefish import volumes and prices; UK-origin arrivals at Keflavik; the "
                   "bilateral fisheries arrangements and their dates",
     "targets": ("EUSTX50", "XBRUSD", "SOYBEAN"),
     "control": "euro-area whitefish demand over the same quarters, which is the alternative "
                "destination",
     "why": "an executable-adjacent demand leg with a dated legal calendar, and the only "
            "bilateral relationship in this pack with three centuries of history behind it"},
)

# --------------------------------------------------------------------------- eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    {"name": "the managed-rate era", "start": "1990-01-01", "end": "2001-03-26",
     "regime": "a krona managed against a basket inside a band, with repeated devaluations "
               "behind it and a history of indexation built to survive them",
     "markers": ("1984 the individual transferable quota system is introduced",
                 "the 1990s widening of the exchange-rate band"),
     "why_it_matters": "the regime the indexation habit comes from; an Icelandic series that "
                       "crosses 2001-03-27 crosses a change in what the currency IS",
     "status": "SETTLED"},
    {"name": "the float, the inflation target and the carry era",
     "start": "2001-03-27", "end": "2008-10-05",
     "regime": "the krona is floated and Sedlabanki adopts a 2.5% inflation target; high policy "
               "rates in a tiny open economy attract a carry inflow, and foreign-issued "
               "krona-denominated 'glacier bonds' build an overhang",
     "markers": ("2001-03-27 the float and the target",
                 "2005-2008 the glacier bond issuance"),
     "why_it_matters": "the only era in which the krona was a normal floating carry currency; "
                       "pooling it with the control era is pooling two different assets",
     "status": "SETTLED"},
    {"name": "the collapse", "start": "2008-10-06", "end": "2008-11-27",
     "regime": "the Emergency Act is passed as the three banks fail; a brief attempt to peg the "
               "krona fails within days and the currency market ceases to function normally",
     "markers": ("2008-10-06 the Emergency Act", "2008-10-28 the policy rate is raised to 18%",
                 "2008-11 the IMF Stand-By Arrangement is agreed"),
     "why_it_matters": "seven weeks in which no Icelandic price means what it usually means; "
                       "this window is excluded from every estimation rather than modelled",
     "status": "SETTLED"},
    {"name": "the capital-control years", "start": "2008-11-28", "end": "2016-06-03",
     "regime": "comprehensive capital controls; residents cannot buy foreign assets and a "
               "trapped OFFSHORE krona trades at a materially weaker price than the onshore "
               "one. Domestic asset prices are set by a captive pension sector with nowhere "
               "else to go",
     "markers": ("2008-11-28 the controls are imposed",
                 "2011-08 the IMF programme concludes",
                 "2015-06 the stability conditions are announced"),
     "why_it_matters": "TWO PRICES FOR ONE CURRENCY AND A CAPTIVE DOMESTIC MARKET. Every "
                       "Icelandic asset price in this era is a control-era price, and reading "
                       "one as a market price is the standard error",
     "status": "SETTLED"},
    {"name": "the unwinding: stability contributions, the auction and the reserve requirement",
     "start": "2016-06-04", "end": "2017-03-13",
     "regime": "the special reserve requirement on new inflows is introduced at 40%; the "
               "offshore-krona auction of 2016-06-16 offers the overhang an exit at an "
               "auction-clearing rate; the failed banks' estates hand over stability "
               "contributions in exchange for exemptions",
     "markers": ("2016-06-04 the special reserve requirement at 40%",
                 "2016-06-16 the offshore krona auction"),
     "why_it_matters": "the overhang was converted into state assets rather than released into "
                       "the market, which is how the era ended without a devaluation",
     "status": "SETTLED"},
    {"name": "the lifting and the taper of the reserve requirement",
     "start": "2017-03-14", "end": "2019-03-05",
     "regime": "the controls on residents and on most capital movement are substantially "
               "lifted; the pension funds begin rebuilding a foreign share held at zero growth "
               "for nine years; the special reserve requirement is cut to 20% in November 2018",
     "markers": ("2017-03-14 the lifting", "2018-11-03 the requirement is cut to 20%"),
     "why_it_matters": "the largest standing krona outflow in the country's history begins here "
                       "and it is a STATUTORY consequence rather than a view",
     "status": "SETTLED"},
    {"name": "the open regime and the pandemic", "start": "2019-03-06", "end": "2021-12-31",
     "regime": "the reserve requirement goes to zero and the krona is an ordinary floating "
               "currency again; the financial supervisor is absorbed into the central bank on "
               "2020-01-01; the pandemic then removes the largest export earner for five "
               "quarters and the first Reykjanes eruption in eight centuries begins",
     "markers": ("2019-03-06 the requirement goes to zero",
                 "2020-01-01 the supervisor is absorbed into the central bank",
                 "2020-03 tourism collapses", "2021-03-19 the Fagradalsfjall eruption"),
     "why_it_matters": "the first clean floating sample in a decade, immediately contaminated "
                       "by the largest peacetime shock to a current account in this department",
     "status": "SETTLED"},
    {"name": "inflation, curtailment and the Reykjanes sequence",
     "start": "2022-01-01", "end": "2026-12-31",
     "regime": "an inflation surge met with a policy rate taken far above the Nordic "
               "comparators; two low-water winters with announced curtailment of interruptible "
               "power; the Grindavik evacuation and repeated fissure eruptions beside the "
               "Svartsengi plant; tourism recovered and seat capacity rebuilt",
     "markers": ("2021-12 the first modern curtailment winter",
                 "2023-11-10 the Grindavik evacuation",
                 "2023-12-18 the first Sundhnukur eruption",
                 "2024-01 the second curtailment winter"),
     "why_it_matters": "the current regime, and the one in which all three of this pack's "
                       "physical mechanisms -- water, fish and fire -- are simultaneously live",
     "status": "OPEN"},
)

ACCESS_CONSTRAINTS: tuple[dict[str, Any], ...] = (
    {"constraint": "the krona is not quoted by this broker",
     "measured": "data/universe/universe.json holds no ISK symbol",
     "consequence": "every Icelandic mechanism terminates in XALUSD, the softs, crude, the "
                    "European index or the Nordic comparators; ISK is an INPUT and a regime "
                    "label, never a cell, and is NEVER proxied by EURNOK or EURSEK"},
    {"constraint": "the smelters' power contracts are commercially confidential",
     "measured": "only the renegotiation dates, the pricing BASIS and the curtailment clause "
                 "are ever announced",
     "consequence": "IS-B is tested on the announcement dates, the consumption share and the "
                    "export tonnage, never on a contract price the desk does not have"},
    {"constraint": "reservoir and grid pages are overwritten in place",
     "measured": "Landsvirkjun and Landsnet publish TODAY's reading and keep no public history",
     "consequence": "the point-in-time reservoir series exists only in the archive layer's own "
                    "crawls, and a cell compiled on an un-archived week is UNMEASURED rather "
                    "than assumed"},
    {"constraint": "Nasdaq Iceland market data may not be redistributed",
     "measured": "the exchange's market-data terms; registered machine_use_allowed=false",
     "consequence": "the Icelandic index enters as a COMPOSITION FACT only; in any case it is a "
                    "handful of names and belongs to the event lane"},
    {"constraint": "the professional market-data service's terms forbid machine extraction",
     "measured": "the Keldan subscription product; registered machine_use_allowed=false",
     "consequence": "the professional data layer is REGISTERED and never fetched, so the desk "
                    "does not forget that it exists"},
    {"constraint": "NO RETAIL MARGIN-STATISTICS ECOLOGY EXISTS AT ALL",
     "measured": "LAYER_ABSENCES['retail_ecology'] -- no domestic CFD or margin broker, no "
                 "published retail-flow or leverage series, and residents were legally barred "
                 "from foreign securities accounts from 2008-11-28 to 2017-03-14",
     "consequence": "the layer is DECLARED ABSENT rather than padded; every retail-flow "
                    "mechanism this desk runs elsewhere reports UNMEASURED for Iceland by "
                    "construction, which is a verdict and not a gap"},
    {"constraint": "no ISK futures contract and therefore no COT row exists",
     "measured": "the CFTC publishes no krona contract and no exchange lists one",
     "consequence": "krona positioning is UNMEASURED and is never proxied by the NOK or SEK COT "
                    "legs, which are positions in two deep commodity currencies"},
    {"constraint": "the sample is 390,000 people and three banks",
     "measured": "every Icelandic aggregate is dominated by a handful of entities",
     "consequence": "an Icelandic macro surprise is frequently ONE firm's quarter, so a cell "
                    "compiled on an aggregate must name the composition it is conditioning on "
                    "or report POORLY_MEASURED"},
)
INSTITUTIONAL_FLOW_SOURCES: tuple[str, ...] = (
    "Sedlabanki monthly foreign-exchange market transactions, named by the bank itself",
    "Sedlabanki pension fund assets and foreign-currency share",
    "Sedlabanki foreign holdings of krona-denominated bonds",
    "the offshore krona stock and the 2016 auction result",
    "Fiskistofa landings by vessel and species",
    "Orkustofnun electricity consumption by large users")
SERIES: dict[str, str] = {
    "IS_POLICY": "CBI:meginvextir", "IS_FX": "CBI:gengisvisitala",
    "IS_INTERVENTION": "CBI:intervention", "IS_RESERVE": "CBI:gjaldeyrisfordi",
    "IS_SRR": "CBI:bindiskylda", "IS_CPI": "HAG:vnv",
    "IS_TRADE": "HAG:voruvidskipti", "IS_TOURISM": "FMS:brottfarir",
    "IS_RESERVOIR": "LV:midlunarlon", "IS_POWER": "ORK:raforkunotkun",
    "IS_QUOTA": "HAF:radgjof", "IS_LANDINGS": "FSK:aflatolur",
    "IS_SEISMIC": "VI:jardhraeringar", "IS_PENSION": "CBI:lifeyrissjodir",
}


# --------------------------------------------------------------------------- the pack's miners
def _report(name: str, rows: list[dict[str, Any]], unmeasured: list[str]) -> dict[str, Any]:
    return {"miner": name, "code": CODE, "rows": tuple(rows), "unmeasured": tuple(unmeasured),
            "n_rows": len(rows), "status": "ok" if rows else "UNMEASURED"}


def _note(ctx: Any, what: str, why: str) -> None:
    """ctx.note when a lab context is given, and nothing at all when it is not. Every miner here
    is PURE: no network, no LLM, no heavy import, and no write outside the given context."""
    if ctx is not None and hasattr(ctx, "note"):
        ctx.note(what, why)


def mine_water_year(pack_obj: Any = None, ctx: Any = None) -> dict[str, Any]:
    """IS-A and IS-B: the hydrological phases and the declared curtailment episodes."""
    rows: list[dict[str, Any]] = []
    for year in (2024, 2025, 2026):
        for month in range(1, 13):
            day = date(year, month, 15)
            rows.append({"kind": "water_phase", "domain": "IS-A", "date": day.isoformat(),
                         "phase": hydrological_year_phase(day),
                         "water_year": hydrological_year(day),
                         "curtailment": curtailment_state(day),
                         "control": "the global aluminium inventory in the same weeks"})
    for lo, hi, what, status in CURTAILMENT_EPISODES:
        rows.append({"kind": "curtailment_episode", "domain": "IS-A", "start": lo.isoformat(),
                     "end": hi.isoformat(), "what": what, "status": status,
                     "control": "the same reservoir readings in years with no curtailment"})
    for r in HYDRO_RESERVOIRS:
        rows.append({"kind": "reservoir", "domain": "IS-A", "name": r["name"],
                     "native": r["native"], "system": r["system"], "serves": r["serves"],
                     "control": "n/a -- this row is a definition"})
    _note(ctx, "reservoir_levels", "the published levels are fetched from Landsvirkjun")
    return _report("is_water_year", rows,
                   ["reservoir levels are overwritten in place, so their point-in-time history "
                    "exists only in the archive layer's crawls"])


def mine_curtailment_spread(pack_obj: Any = None, ctx: Any = None) -> dict[str, Any]:
    """IS-C: the spread hypothesis, declared with the leg that is control-grade named as such."""
    rows: list[dict[str, Any]] = [
        {"kind": "spread_definition", "domain": "IS-C",
         "exposed": "European smelters pricing power off gas",
         "unexposed": "Icelandic smelters on contracted renewable power",
         "observable": "the aluminium-to-power ratio and the European duty-paid premium",
         "control": "Chinese production, which dominates the world balance",
         "declared_weakness": "XNGUSD is Henry Hub and Europe prices off TTF, so the gas leg "
                              "here is CONTROL-GRADE and is never called a proxy"},
    ]
    _note(ctx, "european_power_price", "TTF and the European power price are not broker symbols")
    return _report("is_curtailment_spread", rows,
                   ["the European power and gas benchmarks the mechanism actually runs on are "
                    "absent from the broker registry; XNGUSD is a control for them"])


def mine_quota_clock(pack_obj: Any = None, ctx: Any = None) -> dict[str, Any]:
    """IS-D: the capelin decision windows and the fishing-year boundaries."""
    rows: list[dict[str, Any]] = []
    for year in (2024, 2025, 2026):
        for w in capelin_calendar(year):
            rows.append({"kind": "capelin_window", "domain": "IS-D",
                         "date": w["date"].isoformat(), "what": w["what"],
                         "fishing_year": w["fishing_year"], "is_decision": w["is_decision"],
                         "control": "the Peruvian anchoveta season in the same months"})
        rows.append({"kind": "fishing_year_start", "domain": "IS-D",
                     "date": fishing_year_start(year).isoformat(),
                     "fishing_year": fishing_year(fishing_year_start(year)),
                     "control": "the Barents Sea joint quota of the same year"})
    for season in CAPELIN_ZERO_SEASONS:
        rows.append({"kind": "zero_season", "domain": "IS-D", "fishing_year": season,
                     "status": CAPELIN_ZERO_STATUS,
                     "control": "the normal seasons either side of it"})
    _note(ctx, "capelin_advice", "the advice documents are fetched from Hafrannsoknastofnun")
    return _report("is_quota_clock", rows, [])


def mine_control_eras(pack_obj: Any = None, ctx: Any = None) -> dict[str, Any]:
    """IS-E, IS-F and IS-J: the regime boundaries every other Icelandic study must respect."""
    rows: list[dict[str, Any]] = [
        {"kind": "era_boundary", "domain": "IS-E", "date": start.isoformat(), "state": name,
         "note": note, "srr_after": srr_rate(start),
         "control": "Norway and Sweden over the same months"}
        for start, name, note in CONTROL_ERAS]
    rows.append({"kind": "auction", "domain": "IS-E", "date": OFFSHORE_AUCTION[0].isoformat(),
                 "what": OFFSHORE_AUCTION[1],
                 "control": "the onshore rate on the same day, which is the other price"})
    for start, rate, status in SRR_SCHEDULE:
        rows.append({"kind": "srr_step", "domain": "IS-F", "date": start.isoformat(),
                     "rate_pct": rate, "status": status,
                     "control": "the quiet months between the steps"})
    _note(ctx, "foreign_bond_holdings", "the holdings series is fetched from Sedlabanki")
    return _report("is_control_eras", rows, [])


def mine_tourism_season(pack_obj: Any = None, ctx: Any = None) -> dict[str, Any]:
    """IS-H and IS-M: the seasonal state and the declared capacity shocks."""
    rows: list[dict[str, Any]] = []
    for year in (2024, 2025, 2026):
        for month in range(1, 13):
            day = date(year, month, 15)
            rows.append({"kind": "tourism_season", "domain": "IS-H", "date": day.isoformat(),
                         "season": keflavik_season(day), "shock": tourism_shock_state(day),
                         "control": "Nordic arrivals over the same months"})
    for lo, hi, what in TOURISM_SHOCKS:
        rows.append({"kind": "tourism_shock", "domain": "IS-H", "start": lo.isoformat(),
                     "end": hi.isoformat(), "what": what,
                     "control": "the same months in years with no capacity shock"})
    _note(ctx, "keflavik_departures", "the monthly departures series is fetched from Isavia")
    return _report("is_tourism_season", rows, [])


def mine_eruption_risk(pack_obj: Any = None, ctx: Any = None) -> dict[str, Any]:
    """IS-I: the dated eruptions with the 2010/2011 pair carried as the control."""
    rows: list[dict[str, Any]] = [
        {"kind": "eruption", "domain": "IS-I", "date": day.isoformat(), "what": what,
         "status": status, "regime": reykjanes_state(day),
         "control": "the 2011 Grimsvotn eruption, which was larger and closed almost nothing"}
        for day, what, status in ERUPTIONS]
    rows.append({"kind": "colour_code_scale", "domain": "IS-I",
                 "codes": AVIATION_COLOUR_CODES,
                 "control": "European airline capacity and weather in the same weeks"})
    _note(ctx, "aviation_colour_code", "the live colour code is fetched from Vedurstofa")
    return _report("is_eruption_risk", rows, [])


def mine_holiday_clock(pack_obj: Any = None, ctx: Any = None) -> dict[str, Any]:
    """IS-K and IS-L: the closed sessions and the two Icelandic weekday rules."""
    rows: list[dict[str, Any]] = []
    for year in (2024, 2025, 2026):
        rows.append({"kind": "summer_day", "domain": "IS-L", "year": year,
                     "date": sumardagurinn_fyrsti(year).isoformat(),
                     "rule": "the first Thursday AFTER 18 April",
                     "control": "the same seasonal Thursday in a year where the rule lands "
                                "a week earlier"})
        rows.append({"kind": "commerce_day", "domain": "IS-L", "year": year,
                     "date": fridagur_verslunarmanna(year).isoformat(),
                     "rule": "the first Monday of August",
                     "control": "the other Mondays of August in the same year"})
        for day, label in market_holidays(year).items():
            rows.append({"kind": "closed_session", "domain": "IS-L", "year": year,
                         "date": day.isoformat(), "label": label,
                         "control": "a matched-weekday control 26 weeks away"})
        for day, label in lost_holidays(year).items():
            rows.append({"kind": "lost_to_weekend", "domain": "IS-L", "year": year,
                         "date": day.isoformat(), "label": label,
                         "control": "years in which the same holiday fell on a weekday"})
    rows.append({"kind": "clock_note", "domain": "IS-L",
                 "what": "Iceland keeps NO daylight saving; every Icelandic session and release "
                         "is fixed in UTC all year while its European counterparts move twice",
                 "control": "the Nordic sessions, which do observe daylight saving"})
    _note(ctx, "session_liquidity", "session bars are needed to measure the closures' effect")
    return _report("is_holiday_clock", rows, [])


def mine_transmission_seeds(pack_obj: Any = None, ctx: Any = None) -> dict[str, Any]:
    """Every declared edge and interaction as a HYPOTHESIS seed, deduplicated by the registry."""
    rows: list[dict[str, Any]] = []
    for e in TRANSMISSION_EDGES_SEED:
        row = {"kind": "edge", "id": e["id"], "targets": e["targets"], "sign": e["sign"],
               "mechanism": e["mechanism"], "condition": e["condition"],
               "control": e["control"], "falsifier": e["falsifier"], "evidence": e["evidence"]}
        rows.append(row)
        if ctx is not None and hasattr(ctx, "seed_transmission"):
            ctx.seed_transmission(**row)
    for row2 in INTERACTIONS:
        rows.append({"kind": "interaction", "with": row2["with"], "targets": row2["targets"],
                     "mechanism": row2["mechanism"], "observable": row2["observable"],
                     "control": row2["control"], "evidence": "HYPOTHESIS"})
    return _report("is_transmission_seeds", rows, [])


MINERS: dict[str, Any] = {
    "mine_water_year": mine_water_year,
    "mine_curtailment_spread": mine_curtailment_spread,
    "mine_quota_clock": mine_quota_clock,
    "mine_control_eras": mine_control_eras,
    "mine_tourism_season": mine_tourism_season,
    "mine_eruption_risk": mine_eruption_risk,
    "mine_holiday_clock": mine_holiday_clock,
    "mine_transmission_seeds": mine_transmission_seeds,
}


def mine(ctx: Any = None) -> dict[str, Any]:
    """THE DEPARTMENT ENTRY. Pure Python: no network, no LLM, no heavy import.

    It runs every one of the pack's own miners against the pack's own declared data, emits the
    transmission seeds through the lab context when one is given, and returns a plain report
    when one is not. `cells_emitted` is the number the addendum asks for, and `layers_absent`
    names the layer this country genuinely does not have -- which is a measurement carried in
    the report rather than a silence.
    """
    rows: list[dict[str, Any]] = []
    unmeasured: list[str] = []
    for name, fn in MINERS.items():
        got = fn(None, ctx)
        rows.extend(dict(r) for r in got["rows"])
        unmeasured.extend(f"{name}: {u}" for u in got["unmeasured"])
    for layer, reason in LAYER_ABSENCES.items():
        unmeasured.append(f"layer {layer}: DECLARED ABSENT -- {reason}")
    return {
        "code": CODE, "jurisdictions": JURISDICTIONS,
        "off_roster": tuple(OFF_ROSTER_JURISDICTIONS),
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "emitted": len(rows), "cells_emitted": len(CELLS),
        "domains": len(DOMAINS), "actors": len(ACTORS), "datasets": len(DATASETS),
        "edges": len(TRANSMISSION_EDGES_SEED), "interactions": len(INTERACTIONS),
        "layers_absent": tuple(LAYER_ABSENCES),
        "rows": tuple(rows), "unmeasured": tuple(unmeasured),
        "dry_run": bool(ctx is None or getattr(ctx, "dry_run", False)),
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
        "query_territories": QUERY_TERRITORIES,
        "datasets": DATASETS, "actors": ACTORS, "domains": DOMAINS,
        "custom_miners": CUSTOM_MINERS, "miner_domains": MINER_DOMAINS,
        "transmission_edges_seed": TRANSMISSION_EDGES_SEED, "policy_eras": POLICY_ERAS,
        "transmission_targets": TRANSMISSION_TARGETS, "access_constraints": ACCESS_CONSTRAINTS,
        "region_desk": REGION_DESK, "forest": FOREST, "cot_currency": COT_CURRENCY,
        "export_economy": EXPORT_ECONOMY, "retail_leverage_regime": RETAIL_LEVERAGE_REGIME,
        "institutional_flow_sources": INSTITUTIONAL_FLOW_SOURCES, "series": SERIES,
        "mission": MISSION, "jurisdictions": JURISDICTIONS,
        "off_roster_jurisdictions": OFF_ROSTER_JURISDICTIONS, "interactions": INTERACTIONS,
        "cells": CELLS,
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
    """The framework's HolidayRule shape: every closed session the rule produces for 2024-2026."""
    dates = sorted({d.isoformat() for y in HOLIDAYS_RULE["years"] for d in market_holidays(y)})
    return {"dates": tuple(dates),
            "fixed_md": tuple(f"{m:02d}-{d:02d}" for m, d, _n, _k in FIXED_DAYS),
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
