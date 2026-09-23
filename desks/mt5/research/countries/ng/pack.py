"""THE NIGERIA COUNTRY PACK -- a managed float that publishes its own quantity, held as data.

THE STRUCTURAL FACT THAT SHAPES EVERY LINE BELOW: USDNGN IS NOT ON THIS BROKER. The naira is not
deliverable offshore, Fusion does not quote it, and no amount of Nigerian insight converts into a
naira position here. Nigeria is therefore a TRANSMISSION-ONLY pack: `OWN_PRICE` is empty on
purpose, and every actor's `impact` and every edge's `targets` must land on an instrument the
account can actually trade. A pack that forgets this produces beautiful mechanisms that reach no
docket cell, which is the failure mode the two-lane order and III.16 both exist to prevent.

SO WHY IS NIGERIA TIER 2 AND NOT A FOOTNOTE. Because it publishes the QUANTITY.

  * THE NFEM DAILY PRINT CARRIES TURNOVER AND DEAL COUNT, not just a rate. Under a managed float
    the RATE IS THE POLICY VARIABLE AND THE QUANTITY IS THE TRUTH. A stable rate on collapsing
    turnover is not a calm market; it is a market that has stopped clearing, and it is the single
    most diagnostic thing any African central bank publishes daily. That is an FX-stress state
    for the largest economy in West Africa, free, dated and machine-readable -- an exogenous
    frontier-risk sensor for the EM and African instruments the desk already trades.
  * THE OFFICIAL-VERSUS-PARALLEL SPREAD IS A CAPITAL CONTROL WITH A PRICE ON IT. When the wedge
    widens the control is binding; when it closes in one step, a devaluation has happened. The
    wedge is observable weeks before the step, and the step is the event.
  * CRUDE IS THE FISCAL BASE AND THE FX BASE AT ONCE. Oil is roughly a twentieth of Nigerian GDP
    and the great majority of its export receipts and federal revenue, so a production disruption
    is simultaneously a Brent supply event, a federal revenue event and an FX event. Very few
    economies join those three through one observable.

THE DESIGN CONTRAST WITH SOUTH AFRICA IS THE POINT OF HAVING BOTH. The SARB has NO exchange-rate
objective and says so in every statement; the CBN has almost nothing else. South Africa gives the
desk a clean, liquid, globally traded price with real physical production behind it. Nigeria gives
the desk a rationed price, a queue, a quantity and a regime that changes by decree. They are two
different research designs and each is the other's control.

WHAT THIS PACK MAY NOT DO. No single-name equity is ever a hypothesis (two-lane order,
2026-09-06): the NGX names are observables and never docket symbols. No crypto-exchange ground is
hunted (universe mandate, 2026-08-18) -- and Nigeria is exactly where that refusal has to be said
out loud, because its peer-to-peer crypto market functions as a parallel FX channel and would be
the most tempting venue ground on the continent. It is carried as PUBLIC COMMENTARY with
`pit_feasible=False`, no venue is named or crawled anywhere here, and the executable leg is the
broker's own BTCUSD CFD.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from .. import (
    DATASET_FIELDS,
    actor,
    build_pack,
    dataset,
    domain,
    edge,
    era,
    holiday_table,
    miner,
    resolve,
    source_class,
)

CODE = "ng"
NAME = "Nigeria"
REGION_COMMAND = "AFRICA"
CURRENCY = "NGN"
#: Nigerian English is the language of the official record; Hausa, Yoruba and Igbo are the
#: languages of the market floor; Nigerian Pidgin is a REGISTER rather than a language and is
#: where retail FX sentiment is actually expressed. All four are mined.
NATIVE_LANGUAGES = ("en", "ha", "yo", "ig")

#: COMPUTE PRIORITY. Tier 2, below South Africa's 1.00. A PRIOR that the source-ROI layer is
#: expected to overwrite by measured survivors, not a verdict to defend.
PRIORITY_WEIGHT: float = 0.62

#: EMPTY ON PURPOSE AND IT IS THE PACK'S DEFINING FACT. USDNGN is not quoted on this account and
#: the naira is not deliverable offshore. Nigeria reaches the docket only through carriers.
OWN_PRICE: tuple[str, ...] = ()

#: What the NG department may place an order in. Not one of these is Nigerian: they are the
#: instruments Nigerian information is claimed to move. Every one is in the broker registry and
#: none is a single-name equity.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "XBRUSD", "XTIUSD", "XNGUSD", "USDZAR", "USDTRY", "USDBRL", "USDMXN", "USDX", "EURUSD",
    "GBPUSD", "UST10Y", "UST05Y", "UKGILT", "XAUUSD", "UK100", "BTCUSD")

#: The instruments a Lagos desk reaches for that THIS broker does not quote. Named with what
#: carries each, because an instrument dropped in silence takes a mechanism with it.
ABSENT_INSTRUMENTS: tuple[dict[str, str], ...] = (
    {"instrument": "USDNGN -- the naira itself",
     "why": "not in desks/mt5/data/universe/universe.json and not deliverable offshore; there "
            "is no NDF market on this account either",
     "carried_by": "USDZAR as the liquid African risk carrier and USDTRY/USDBRL as EM "
                   "devaluation-regime peers. THIS IS A CARRIER, NOT A SUBSTITUTE: the naira's "
                   "idiosyncratic regime risk is precisely what the carriers do not contain, "
                   "and every edge that uses one says so."},
    {"instrument": "Nigerian sovereign eurobonds (the 2032s and 2038s are the liquid points)",
     "why": "absent; the broker quotes UKGILT, UST05Y and UST10Y and no EM credit",
     "carried_by": "UST10Y as the global duration leg, with the Nigeria-specific credit spread "
                   "left UNMEASURED BY NAME rather than proxied by a developed-market curve"},
    {"instrument": "NGX All-Share Index",
     "why": "absent; no Nigerian equity index CFD is quoted",
     "carried_by": "nothing adequate. UK100 carries a fraction of the oil-major beta and no "
                   "Nigerian domestic beta at all; the pack declares this a GAP rather than "
                   "pretending a carrier exists"},
    {"instrument": "Bonny Light and Qua Iboe crude grades",
     "why": "absent; the broker quotes XBRUSD and XTIUSD only",
     "carried_by": "XBRUSD. Nigerian grades are light and sweet and price at a differential to "
                   "Brent that is itself an observable; the DIFFERENTIAL is not tradable here "
                   "and is used only as a conditioning variable"},
    {"instrument": "Nigerian Treasury bills and OMO bills",
     "why": "absent; the carry trade that drives foreign portfolio flow has no executable leg",
     "carried_by": "UST05Y for the global rate leg, and the flow itself is treated as a "
                   "conditioning observable rather than as something the desk can hold"},
)


# --------------------------------------------------------------------------- central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "Central Bank of Nigeria (CBN)",
    "framework": "managed_float",
    "framework_history": (
        "Nigeria has changed exchange-rate REGIME more often than it has changed governor, and "
        "the regime is the single most important conditioning variable in this pack. The "
        "sequence that matters: (1) a MULTIPLE-WINDOW regime to mid-2023, in which an official "
        "or CBN rate, an Investors' and Exporters' (I&E / NAFEX) window rate and a parallel "
        "street rate coexisted, sometimes with a spread of tens of per cent between the first "
        "and the last -- so the question 'what was the naira worth' had three answers and every "
        "study must say which one it used; (2) UNIFICATION on 2023-06-14, when the new "
        "administration collapsed the windows and the official rate moved to meet the market; "
        "(3) FURTHER LIBERALISATION through 2024, including a reworking of the Bureau de Change "
        "licensing regime and a sequence of clearances of the FX forwards backlog; (4) the "
        "ELECTRONIC FOREIGN EXCHANGE MATCHING SYSTEM (EFEMS) from December 2024, with the "
        "Nigerian Foreign Exchange Market (NFEM) rate replacing NAFEM as the published "
        "benchmark, and a published daily rate RANGE, TURNOVER and DEAL COUNT alongside it."),
    "committee": "Monetary Policy Committee (MPC); the decision is delivered by the Governor at "
                 "a press briefing rather than by a timed statement release",
    "policy_rate": "the Monetary Policy Rate (MPR), with an asymmetric corridor and a Cash "
                   "Reserve Ratio that is used as aggressively as the rate itself -- so A RATE "
                   "STUDY THAT IGNORES THE CRR IS MISSING HALF THE POLICY INSTRUMENT",
    "meetings_per_year": 6,
    "schedule_rule": (
        "Six scheduled two-day MPC meetings a year, normally in the second half of alternate "
        "months, with the decision announced at the end of the second day. The announcement is "
        "a PRESS BRIEFING, not a timed wire release: the exact minute varies by tens of minutes "
        "and the desk records the OBSERVED timestamp rather than a nominal one. WAT is UTC+1 "
        "all year and Nigeria observes no daylight saving, so the local time never moves -- but "
        "the briefing's start does, which is a different kind of uncertainty and is treated as "
        "such."),
    "timezone": "WAT = UTC+1 all year, no DST.",
    "fx_operations": (
        "THE OPPOSITE OF SOUTH AFRICA, AND THAT CONTRAST IS THE RESEARCH DESIGN. The SARB has no "
        "exchange-rate objective and says so in every statement; the CBN has almost nothing "
        "else. Its toolkit is public and graded: retail and wholesale FX auctions to banks and "
        "BDCs, direct sales at a declared rate, clearance of the forwards backlog, net open "
        "position limits on banks that force them to sell dollars they are holding, and moral "
        "suasion. Each is an ANNOUNCED, DATED intervention -- so unlike the rand, the naira has "
        "an intervention reaction function that can in principle be fitted."),
    "reserves": (
        "Gross external reserves are published as a THIRTY-DAY MOVING AVERAGE on the CBN's own "
        "page, near-daily. THE MOVING AVERAGE IS A TRAP: it smooths exactly the step changes an "
        "event study needs, and the level it reports on day T embeds thirty days of history. A "
        "study that differences the published series is differencing a filter, not the "
        "underlying stock, and the pack says so here so that nobody rediscovers it."),
    "publication_classes": ("MPC communique and personal statements", "Monetary Policy Review",
                            "Statistical Bulletin", "Economic and Financial Review",
                            "daily exchange rates and reserves pages",
                            "business and consumer expectation surveys"),
    "decision_dates": {
        2024: ("2024-02-27", "2024-03-26", "2024-05-21", "2024-07-23", "2024-09-24",
               "2024-11-26"),
        2025: ("2025-02-20", "2025-05-20", "2025-07-22", "2025-09-23", "2025-11-25"),
        2026: ("2026-02-24", "2026-05-19", "2026-07-21", "2026-09-22", "2026-11-24"),
    },
    "decision_dates_status": {
        2024: "PUBLIC_RECORD -- an unusually crowded year: the February and March meetings were "
              "three weeks apart during the emergency tightening sequence",
        2025: "PUBLIC_RECORD",
        2026: "RULE_DERIVED_UNVERIFIED -- the alternate-month, second-half-of-month, Tuesday "
              "pattern projected forward. THE DATA PLANE MUST REPLACE THESE WITH THE PUBLISHED "
              "CALENDAR BEFORE ANY 2026 EVENT STUDY IS SCORED. An event study anchored on a "
              "guessed date measures the wrong session and reports it with full confidence, "
              "which is worse than not running it.",
    },
    "decision_time_utc": "approximately 13:00-15:00; OBSERVED, not nominal -- the briefing's "
                         "start time varies and the plane records what it saw",
    "notes": "The CBN's statistics pages are old-style ASP endpoints that render HTML tables. "
             "They are free and have been stable for years, but they are PAGES, not an API, so "
             "the data plane's shape check is what stands between this pack and a silently "
             "empty series after a site redesign.",
}


# --------------------------------------------------------------------------- fixings
FIXING_CONVENTIONS: dict[str, Any] = {
    "nfem_rate": {
        "name": "NFEM -- the Nigerian Foreign Exchange Market rate",
        "publisher": "FMDQ Securities Exchange, with the CBN publishing its own daily rates "
                     "alongside",
        "definition": "the benchmark rate struck in the interbank FX market, published daily "
                      "with a HIGH, a LOW and a CLOSE",
        "history": "replaced NAFEM from December 2024 alongside the EFEMS matching platform; "
                   "NAFEM itself replaced the I&E window convention at the 2023 unification. "
                   "THREE NAMES, THREE DEFINITIONS, ONE SERIES NAME IN MOST DATA VENDORS -- and "
                   "that silent splice is the commonest error in naira research.",
        "why_the_range_matters": "the published daily RANGE is a free intraday volatility "
                                 "measure for a market with no tick data available to this desk",
    },
    "nfem_quantity": {
        "name": "NFEM daily turnover and deal count",
        "definition": "the total US dollar value transacted and the NUMBER OF DEALS struck",
        "why_it_is_the_flagship": (
            "UNDER A MANAGED FLOAT THE RATE IS THE POLICY VARIABLE AND THE QUANTITY IS THE "
            "TRUTH. A rate that barely moves while turnover halves and the deal count collapses "
            "is a market that has stopped clearing, not a calm one -- and the rate series alone "
            "cannot tell those two apart. Turnover and deal count are also two DIFFERENT "
            "observables: turnover falling with a stable deal count is smaller tickets; deal "
            "count falling with stable turnover is a market that has become a few large "
            "participants. The stress state in `data_plane.nfem_stress_state` reads both."),
    },
    "parallel_rate": {
        "name": "the parallel or street rate",
        "publisher": "no official publisher; quoted by BDC operators, aggregator sites and the "
                     "Nigerian financial press",
        "status": "PUBLIC COMMENTARY, NOT AN OFFICIAL SERIES. It is carried with "
                  "pit_feasible=False for any single day's quote and is used as a REGIME "
                  "observable at weekly or monthly resolution, where the level is corroborated "
                  "across several independent reporters.",
        "why_it_matters": "the official-versus-parallel SPREAD is the capital control with a "
                          "price on it: it widens while the control binds and closes in one "
                          "step when the regime breaks. The wedge leads the step.",
    },
    "deliverability": "THE NAIRA IS NOT DELIVERABLE OFFSHORE and there is no broker quote and no "
                      "NDF on this account. Every mechanism in this pack must be carried by "
                      "another instrument, and the pack refuses to pretend otherwise.",
    "dst": "NONE. WAT is UTC+1 year-round.",
}


# --------------------------------------------------------------------------- settlement
SETTLEMENT_CONVENTIONS: dict[str, Any] = {
    "spot": "T+2 in the interbank market, settled in naira through the CBN's own systems and in "
            "dollars through correspondent banks -- and THE CORRESPONDENT LEG IS A CONSTRAINT, "
            "not a formality: correspondent banking access has itself been an episodic "
            "bottleneck for Nigerian banks",
    "equity_settlement": "T+3 at the NGX through the Central Securities Clearing System",
    "bond_settlement": "T+2 for FGN bonds through FMDQ and the CSCS",
    "net_open_position": "Nigerian banks operate under a CBN-set net open position limit. THIS "
                         "IS A FORCED-FLOW MECHANISM WITH A PUBLISHED TRIGGER: when the limit is "
                         "tightened, banks holding dollars above it must sell, on a deadline the "
                         "circular states. It is one of the very few dated, quantified forced "
                         "flows in African FX.",
    "faac_cycle": "THE MOST DISTINCTIVE NIGERIAN CALENDAR OBJECT. The Federation Account "
                  "Allocation Committee distributes federally collected revenue -- most of it "
                  "dollar oil receipts -- to the federal, state and local governments MONTHLY, "
                  "in naira. That is a scheduled, large, naira-liquidity injection whose SIZE IS "
                  "PUBLISHED, and the local hypothesis is that it shows up as FX demand and as "
                  "parallel-market pressure in the days after. A monthly liquidity event with a "
                  "published number is rare anywhere.",
    "month_end": "importer demand and corporate obligations concentrate at month end, on top of "
                 "the FAAC cycle, so the two calendars interact and a study of either must "
                 "control for the other",
    "forwards_backlog": "between 2020 and 2024 the CBN ran a backlog of unsettled FX forward "
                        "obligations to banks and corporates. The backlog's size and its "
                        "clearance tranches were announced -- a QUEUE with a published length, "
                        "which is the purest capital-control observable this civilization has.",
}


# --------------------------------------------------------------------------- exchanges
EXCHANGES: dict[str, Any] = {
    "cash": {
        "name": "Nigerian Exchange Group (NGX)",
        "hours_local": "10:00-14:30 WAT",
        "hours_utc": "09:00-13:30",
        "settlement": "T+3",
        "index_symbols": (),
        "index_symbols_note": "the NGX All-Share is NOT quoted on this account; it is named in "
                              "ABSENT_INSTRUMENTS with an explicit statement that NO adequate "
                              "carrier exists, rather than being proxied by something unrelated",
        "market_data": "NGX sells a market-data REST API. IT IS A PAID PRODUCT and is catalogued "
                       "as such: key-required, priced by expected information gain against its "
                       "cost, and NEVER fetched without a key present on this box.",
    },
    "fixed_income_and_fx": {
        "name": "FMDQ Securities Exchange",
        "why_it_matters": "FOR THIS PACK FMDQ MATTERS MORE THAN NGX. It is where the NFEM rate, "
                          "the FX turnover and deal count, the money-market rates and the FGN "
                          "bond market actually live. A researcher who goes to the equity "
                          "exchange for Nigerian market data has gone to the wrong building.",
        "publications": "daily FX market summary, money-market rates, fixed-income turnover",
    },
    "derivatives": {
        "status": "NO LIQUID EXCHANGE-TRADED NAIRA DERIVATIVE reaches this desk. FMDQ has listed "
                  "FX futures and the CBN has at times been the counterparty to OTC forwards, "
                  "but neither produces a positioning series the desk can read. This is declared "
                  "rather than left as an empty field.",
    },
}


FISCAL_YEAR_END: dict[str, str] = {
    "government": "31 December. The Appropriation Act is normally signed around the turn of the "
                  "year and its OIL PRICE AND PRODUCTION BENCHMARKS are published -- which makes "
                  "the budget a public statement of the fiscal break-even and therefore of how "
                  "much pressure a given Brent level puts on the naira.",
    "corporate": "31 December for most listed companies",
    "cbn": "31 December",
    "note": "The budget's oil benchmark is the single most useful fiscal number in the pack: it "
            "converts a Brent price into a Nigerian fiscal state without any modelling.",
}


# --------------------------------------------------------------------------- holidays
#: Nigeria's Public Holidays Act, with the Islamic days declared annually by the Ministry of
#: Interior and therefore MOON-DEPENDENT. The Islamic rows below are ESTIMATES and say so in
#: their own name strings: this desk does not trade a guessed Eid window.
_NG_HOLIDAYS: dict[int, dict[str, str]] = {
    2024: {
        "2024-01-01": "New Year's Day",
        "2024-03-29": "Good Friday",
        "2024-04-01": "Easter Monday",
        "2024-04-10": "Eid al-Fitr day 1 (moon-dependent; declared by the Ministry of Interior)",
        "2024-04-11": "Eid al-Fitr day 2 (moon-dependent)",
        "2024-05-01": "Workers' Day",
        "2024-06-12": "Democracy Day",
        "2024-06-17": "Eid al-Adha day 1 (moon-dependent)",
        "2024-06-18": "Eid al-Adha day 2 (moon-dependent)",
        "2024-09-16": "Maulud an-Nabi (moon-dependent)",
        "2024-10-01": "Independence Day",
        "2024-12-25": "Christmas Day",
        "2024-12-26": "Boxing Day",
    },
    2025: {
        "2025-01-01": "New Year's Day",
        "2025-03-31": "Eid al-Fitr day 1 (moon-dependent)",
        "2025-04-01": "Eid al-Fitr day 2 (moon-dependent)",
        "2025-04-18": "Good Friday",
        "2025-04-21": "Easter Monday",
        "2025-05-01": "Workers' Day",
        "2025-06-07": "Eid al-Adha day 1 (moon-dependent)",
        "2025-06-08": "Eid al-Adha day 2 (moon-dependent)",
        "2025-06-12": "Democracy Day",
        "2025-09-05": "Maulud an-Nabi (moon-dependent)",
        "2025-10-01": "Independence Day",
        "2025-12-25": "Christmas Day",
        "2025-12-26": "Boxing Day",
    },
    2026: {
        "2026-01-01": "New Year's Day",
        "2026-03-20": "Eid al-Fitr day 1 (moon-dependent; ESTIMATE, not gazetted)",
        "2026-03-21": "Eid al-Fitr day 2 (moon-dependent; ESTIMATE, not gazetted)",
        "2026-04-03": "Good Friday",
        "2026-04-06": "Easter Monday",
        "2026-05-01": "Workers' Day",
        "2026-05-27": "Eid al-Adha day 1 (moon-dependent; ESTIMATE, not gazetted)",
        "2026-05-28": "Eid al-Adha day 2 (moon-dependent; ESTIMATE, not gazetted)",
        "2026-06-12": "Democracy Day",
        "2026-08-26": "Maulud an-Nabi (moon-dependent; ESTIMATE, not gazetted)",
        "2026-10-01": "Independence Day",
        "2026-12-25": "Christmas Day",
        "2026-12-26": "Boxing Day",
    },
}

HOLIDAYS_RULE: dict[str, Any] = {
    "rule": (
        "The Public Holidays Act, plus annual declarations by the Minister of Interior. THREE "
        "LAYERS. (1) FIXED GREGORIAN: 1 January, 1 May (Workers' Day), 12 June (Democracy Day, "
        "moved from 29 May in 2018), 1 October (Independence Day), 25 December and 26 December. "
        "(2) MOVEABLE CHRISTIAN: Good Friday and Easter Monday, computed from Easter. "
        "(3) MOVEABLE ISLAMIC, DECLARED ANNUALLY AND MOON-DEPENDENT: Eid al-Fitr (two days), Eid "
        "al-Adha (two days) and Maulud an-Nabi. The Islamic days are the honest-uncertainty "
        "point of this table: they are set by sighting and announced by the Ministry of Interior "
        "days -- sometimes ONE DAY -- in advance, and a projected date can be wrong by a day in "
        "either direction. Every Islamic row here says so in its own name string. SUBSTITUTION: "
        "a holiday falling on a weekend is normally observed on the following working day by "
        "Ministerial declaration, but the declaration is discretionary and not automatic, so "
        "this table records the statutory day and leaves the bridge to the gazette."),
    "authority": "the Public Holidays Act and the Federal Ministry of Interior's annual "
                 "declarations, published in the Federal Government Gazette and the national "
                 "press",
    "table": _NG_HOLIDAYS,
    "status": {
        2024: "GAZETTED for the Gregorian and Christian days; the Islamic days are as declared "
              "and are recorded here from the public record",
        2025: "GAZETTED for the Gregorian and Christian days; Islamic days as declared",
        2026: "MIXED. The Gregorian days are statutory and certain. The Christian days follow "
              "from Easter Sunday 2026-04-05 and are certain. THE ISLAMIC DAYS ARE ESTIMATES "
              "FROM THE HIJRI CALENDAR AND ARE NOT GAZETTED: they may move by a day in either "
              "direction and any event study that lands on one must be re-run against the "
              "gazette or reported UNMEASURED.",
    },
    "market_effect": (
        "THIS IS WHERE A TRANSMISSION-ONLY PACK DIFFERS FROM SOUTH AFRICA'S, AND THE DIFFERENCE "
        "IS NOT COSMETIC. When Johannesburg shuts, USDZAR keeps trading offshore and the closure "
        "is a LIQUIDITY REGIME in a price the desk holds. When Lagos shuts, there is no naira "
        "price on this account to have a regime -- what stops is the DATA: no NFEM rate, no "
        "turnover, no deal count, no CBN page update. So a Nigerian holiday is an OBSERVABILITY "
        "OUTAGE, and the rule that follows is absolute: A MISSING NFEM DAY IS NOT A ZERO AND IS "
        "NOT A CALM DAY. It is UNMEASURED, by name, and any stress state computed across one "
        "must carry the gap explicitly. Meanwhile the carriers -- Brent, the rand, the EM peers "
        "-- trade through the closure with no Nigerian information arriving, which means the "
        "post-holiday reopening print is the first observation in several days and is a "
        "different object from an ordinary daily print."),
    "callable": "countries.ng.pack:holidays",
}


def holidays(year: int) -> dict[str, str]:
    """Nigeria's closure table for one year, `{"YYYY-MM-DD": name}`. `{}` if untabulated."""
    return holiday_table(HOLIDAYS_RULE, year)


# --------------------------------------------------------------------------- custom miners
def ng_faac_window(year: int, month: int) -> dict[str, Any]:
    """The FAAC naira-liquidity window for one month, and the days the pressure is claimed in.

    THE MECHANISM IN ONE SENTENCE: the Federation Account Allocation Committee converts dollar
    oil receipts into naira and distributes them to three tiers of government once a month, so a
    large, scheduled naira liquidity injection lands and is followed, on the local hypothesis, by
    FX demand as the recipients and their contractors buy dollars.

    The meeting is normally held in the second half of the month and the distribution figure is
    ANNOUNCED. This function returns the window the desk conditions on rather than a date it has
    invented: a range, plus the explicit statement that the actual announcement date is read from
    the record and is not derivable from a rule.
    """
    if not 1 <= int(month) <= 12:
        raise ValueError(f"month {month!r} out of range")
    start = date(int(year), int(month), 15)
    end = date(int(year), int(month), 28)
    return {
        "year": int(year), "month": int(month),
        "window_start": start.isoformat(), "window_end": end.isoformat(),
        "rule": "the FAAC meeting is normally held in the second half of the month and the "
                "allocation figure is announced; the exact date is NOT derivable from a rule "
                "and is read from the public record",
        "claimed_pressure_days": "the three to seven business days following the announcement",
        "observable": "the announced allocation total in naira, published by the Office of the "
                      "Accountant-General and carried by the Nigerian press",
        "status": "WINDOW_ONLY -- this function returns the conditioning window, never an "
                  "asserted announcement date. A study that anchors on an invented date is "
                  "measuring the wrong week with full confidence.",
        "controls": ("the same calendar window in months with no allocation announced",
                     "randomised announcement dates inside the window",
                     "month-end importer demand, which overlaps and must be separated"),
    }


def ng_regime_of(day: str) -> dict[str, Any]:
    """Which FX regime a date falls in. The single most important conditioning call in this pack.

    A naira study pooled across the 2023 unification is not noisy -- it is measuring two
    different currencies with one name. This returns the regime label, its boundary dates and
    what a pooled estimate across the boundary would actually be measuring, so a downstream
    miner can refuse to pool rather than discovering the problem in a p-value.
    """
    iso = str(day)[:10]
    for row in POLICY_ERAS:
        start = str(row.get("start") or "")
        end = row.get("end")
        if start <= iso and (end is None or iso <= str(end)):
            return {"date": iso, "era": row["id"], "label": row["label"],
                    "invalidates": row["invalidates"], "status": "OK"}
    return {"date": iso, "era": None, "status": "UNMEASURED", "why": "NO_ERA_COVERS_THIS_DATE",
            "detail": "the era table does not span this date; a regime call that is not in the "
                      "table is a gap in the table, never a default to the nearest regime"}


CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    miner("ng_faac_liquidity_window",
          domain_ids=("ng_fiscal_faac_liquidity", "ng_parallel_premium"),
          kind="calendar",
          entry="countries.ng.pack:ng_faac_window",
          cadence_s=86400.0,
          steerable=False,
          notes="A monthly liquidity event with a PUBLISHED SIZE is rare anywhere and is the "
                "most distinctive calendar object Nigeria offers. It is a fixed cost: the "
                "window must be read every pass, because conditioning on the wrong week "
                "produces a confident wrong number."),
    miner("ng_fx_regime_classifier",
          domain_ids=("ng_fx_regime_state", "ng_frontier_stress_transmission"),
          kind="mechanism",
          entry="countries.ng.pack:ng_regime_of",
          cadence_s=3600.0,
          steerable=True,
          notes="Refuses to pool across a regime boundary. The 2023 unification and the 2024 "
                "EFEMS/NFEM change are not noise to be averaged; they are different currencies "
                "sharing a name."),
)


# --------------------------------------------------------------------------- positioning
#: THE HONEST ANSWER IS THAT NIGERIA HAS NO POSITIONING DATA, and this tuple exists to say so by
#: name rather than to leave a field empty. South Africa has a CFTC contract and daily JSE
#: foreign flows; Nigeria has neither. What follows is what STANDS IN, with each substitute's
#: limitation stated, because a substitute presented without its limitation becomes a claim.
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"id": "cftc_cot_ngn",
     "name": "CFTC Commitments of Traders -- Nigerian naira",
     "availability": "DOES NOT EXIST. There is no CME naira futures contract and therefore no "
                     "COT report. South Africa is the only country in this African civilization "
                     "with one, and the contrast is worth stating: the rand has measurable "
                     "speculative positioning and the naira has none at all.",
     "covers": "n/a", "frequency": "n/a", "lag": "n/a",
     "root": "cftc.gov (checked; no naira contract)",
     "licence": "n/a",
     "desk_status": "DECLARED ABSENT. Any positioning miner asked about the naira reports "
                    "UNMEASURED naming this row, which is a measurement of the world rather "
                    "than of this box."},
    {"id": "nfem_turnover_and_deals",
     "name": "NFEM daily turnover and deal count",
     "covers": "the dollar value transacted and the number of deals struck in the interbank "
               "market each day",
     "frequency": "daily", "lag": "same day, published after the close",
     "root": "fmdqgroup.com, with the CBN publishing rates alongside",
     "licence": "free, public",
     "desk_status": "THE CLOSEST THING NIGERIA HAS TO A POSITIONING SERIES, and it is a FLOW "
                    "and a PARTICIPATION COUNT rather than a stock of positions. It cannot tell "
                    "you who is long; it can tell you whether anybody is trading at all, which "
                    "under a managed float is the more useful question."},
    {"id": "cbn_intervention_and_auctions",
     "name": "CBN FX auctions, direct sales and forwards-backlog clearances",
     "covers": "announced intervention size, the rate cleared and the class of buyer",
     "frequency": "episodic, announced", "lag": "same day to a few days",
     "root": "cbn.gov.ng circulars and press releases",
     "licence": "free, public",
     "desk_status": "A DATED, QUANTIFIED, ANNOUNCED FORCED FLOW -- the thing the rand does not "
                    "have. Its weakness is that announcement and settlement are different "
                    "dates and only the first is reliably public."},
    {"id": "cbn_net_open_position_limits",
     "name": "Bank net open position limits and their changes",
     "covers": "the regulatory cap on Nigerian banks' FX exposure",
     "frequency": "episodic, by circular", "lag": "same day",
     "root": "cbn.gov.ng banking supervision circulars",
     "licence": "free, public",
     "desk_status": "A TIGHTENING IS A FORCED SALE WITH A DEADLINE IN THE CIRCULAR. One of very "
                    "few African FX mechanisms where the trigger, the direction, the size class "
                    "and the deadline are all in one public document."},
    {"id": "cbn_external_reserves",
     "name": "CBN gross external reserves (thirty-day moving average)",
     "covers": "the reserve stock as the CBN publishes it",
     "frequency": "near-daily", "lag": "one to three days",
     "root": "cbn.gov.ng/IntOps/Reserve.asp",
     "licence": "free, public",
     "desk_status": "USABLE BUT FILTERED. The published series is a THIRTY-DAY MOVING AVERAGE, "
                    "so it smooths exactly the step changes an event study wants and its day-T "
                    "value embeds a month of history. Differencing it differences a filter."},
    {"id": "ng_eurobond_spread",
     "name": "Nigerian sovereign eurobond spread over US Treasuries",
     "covers": "the market's price of Nigerian sovereign credit",
     "frequency": "daily", "lag": "same day",
     "root": "public bond market commentary and DMO issuance documents",
     "licence": "free commentary; the tradable instrument is NOT on this account",
     "desk_status": "The best single summary of foreign investor sentiment toward Nigeria, and "
                    "the desk holds NO instrument in it. Carried as a conditioning observable "
                    "only, with UST10Y as the executable global-duration leg."},
)


# --------------------------------------------------------------------------- terminology
#: NATIVE TERMS, KEYED BY DOMAIN. Nigerian English is the language of the official record; Hausa,
#: Yoruba and Igbo are the languages of the market floor and of the trade press outside Lagos;
#: and Nigerian PIDGIN is a REGISTER RATHER THAN A LANGUAGE -- it has no official status and it
#: is exactly where retail FX sentiment is expressed. A miner that only knows the CBN's English
#: learns a devaluation from the communique that follows it.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "core": ("naira", "kuɗi", "owó", "ego", "dala", "dollar", "exchange rate", "canjin kuɗi",
             "owó òkèèrè", "ọnụahịa", "farashi", "iye owó", "bei", "rate"),
    "ng_fx_regime_state": ("CBN rate", "official rate", "I&E window", "NAFEX", "NAFEM", "NFEM",
                           "EFEMS", "unification", "devaluation", "float", "managed float",
                           "bankin ƙasa", "báńkì", "ụlọ akụ", "naira don fall",
                           "naira don gain", "CBN don devalue"),
    "ng_parallel_premium": ("black market rate", "parallel market", "street rate", "aboki",
                            "mallam", "mai canji", "BDC", "bureau de change", "Wuse Zone 4",
                            "dollar don rise", "e don cost", "premium", "spread", "round-"
                            "tripping", "arbitrage"),
    "ng_nfem_liquidity": ("turnover", "deal count", "market turnover", "FX liquidity",
                          "forex scarcity", "dollar scarcity", "no dollar for market",
                          "illiquid", "bid", "offer", "interbank"),
    "ng_reserves_pressure": ("external reserves", "foreign reserves", "reserve drawdown",
                             "import cover", "ajiyar kuɗi", "reserves don drop", "IMF",
                             "balance of payments", "current account"),
    "ng_oil_production": ("crude oil", "Bonny Light", "Qua Iboe", "OPEC quota", "production "
                          "quota", "oil theft", "pipeline vandalism", "force majeure", "NNPC",
                          "NUPRC", "man fetur", "epo", "mmanụ", "barrels per day", "terminal"),
    "ng_fiscal_faac_liquidity": ("FAAC", "federation account", "allocation", "federal "
                                 "allocation", "state government", "accountant-general",
                                 "revenue sharing", "excess crude account", "kason kuɗi",
                                 "budget benchmark", "oil benchmark"),
    "ng_trade_and_refining_shift": ("Dangote refinery", "refinery", "PMS", "premium motor "
                                    "spirit", "petrol", "fuel import", "crude swap", "DSDP",
                                    "product import", "refined import", "man fetur", "epo"),
    "ng_inflation_passthrough": ("inflation", "headline inflation", "food inflation", "NBS",
                                 "consumer price index", "hauhawar farashi", "fuel subsidy",
                                 "subsidy removal", "transport cost", "wahala", "cost of living"),
    "ng_portfolio_repatriation_queue": ("OMO bills", "treasury bills", "carry trade",
                                        "foreign portfolio investor", "FPI", "repatriation",
                                        "backlog", "unsettled forwards", "trapped funds",
                                        "capital importation", "japa"),
    "ng_policy_reaction": ("MPC", "monetary policy rate", "MPR", "CRR", "cash reserve ratio",
                           "communique", "hawkish", "dovish", "tightening", "liquidity "
                           "mop-up", "bankin ƙasa", "Governor"),
    "ng_frontier_stress_transmission": ("frontier market", "emerging market", "eurobond",
                                        "spread", "sovereign risk", "credit rating",
                                        "default risk", "restructuring", "IMF programme"),
    "ng_risk_proxy_crypto_premium": ("P2P", "peer to peer", "USDT", "stablecoin", "crypto "
                                     "premium", "naira premium", "diaspora remittance",
                                     "remittance", "IMTO", "money transfer"),
    "ng_session_microstructure_carrier": ("market open", "market close", "interbank session",
                                          "Lagos session", "London open", "spillover",
                                          "ọjà", "ahịa", "kasuwa"),
}


# --------------------------------------------------------------------------- source classes
#: THE TEN LAYERS (principal's per-country depth rule, 2026-09-17). Exactly one per source, and
#: every layer either covered or DECLARED ABSENT WITH A REASON -- never blank. Nigeria is the
#: country where the rule pays for itself most obviously: the official layer publishes a rate the
#: CBN chose, and the retail and app layers publish the rate at which people actually transacted.
#: A Nigeria "covered" by five CBN pages is a Nigeria whose parallel market does not exist.
LAYERS: tuple[str, ...] = ("official", "institutional", "academic", "practitioner",
                           "retail_ecology", "app_ecosystem", "media", "archive",
                           "physical_economy", "source_graph")

#: HOW THE DESK IS ALLOWED TO TOUCH IT. Separate from credibility on purpose: a source can be
#: perfectly public and completely wrong, or authoritative and unusable.
ACCESS_LABELS: tuple[str, ...] = ("PUBLIC", "PUBLIC_WITH_TERMS", "LICENSED", "OPEN_DATA",
                                  "PUBLIC_ARCHIVE", "PUBLIC_SOCIAL", "USER_SUBMITTED",
                                  "ACCESS_UNCLEAR", "PRIVATE", "CONFIDENTIAL_MNPI",
                                  "STOLEN_UNAUTHORIZED")

#: WHETHER TO BELIEVE IT. `FRINGE` and `CONTRADICTED` are KEPT, never dropped -- in Nigeria the
#: devaluation rumour that turned out wrong is the single best record of what the market expected
#: while the official rate was insisting otherwise.
CREDIBILITY: tuple[str, ...] = ("AUTHORITATIVE", "RELIABLE", "UNRELIABLE", "FRINGE",
                                "CONTRADICTED", "UNKNOWN")

#: WHETHER IT HAS EVER PREDICTED ANYTHING ON THIS BOX. Every row starts UNTESTED and only a
#: measured screen may move it.
PREDICTIVE_STATES: tuple[str, ...] = ("UNTESTED", "PREDICTIVE", "NOT_PREDICTIVE",
                                      "NARRATIVE_FEATURE")


def _src(sid: str, label: str, *, layer: str, roots: Any, languages: Any, licence: str,
         access_label: str, credibility: str, predictive_state: str, queries: Any,
         machine_use_allowed: bool = True, notes: str = "") -> dict[str, Any]:
    """`source_class()` plus the principal's five labels, with the enums checked on the way in.

    A MISLABELLED SOURCE IS WORSE THAN AN UNLABELLED ONE, because a wrong label is read as a
    measurement. `queries` are NATIVE-LANGUAGE and are not translations: a Hausa trading board
    does not contain the phrase "parallel market premium", it contains "farashin dala yau", and a
    Pidgin thread does not say "the naira depreciated", it says "naira don fall".
    """
    if layer not in LAYERS:
        raise ValueError(f"source {sid}: layer {layer!r} not one of {list(LAYERS)}")
    if access_label not in ACCESS_LABELS:
        raise ValueError(f"source {sid}: access_label {access_label!r} not in "
                         f"{list(ACCESS_LABELS)}")
    if credibility not in CREDIBILITY:
        raise ValueError(f"source {sid}: credibility {credibility!r} not in {list(CREDIBILITY)}")
    if predictive_state not in PREDICTIVE_STATES:
        raise ValueError(f"source {sid}: predictive_state {predictive_state!r} not in "
                         f"{list(PREDICTIVE_STATES)}")
    row = source_class(sid, label, roots=roots, languages=languages, licence=licence, notes=notes)
    row.update({"layer": layer, "access_label": access_label, "credibility": credibility,
                "predictive_state": predictive_state,
                "machine_use_allowed": bool(machine_use_allowed), "queries": tuple(queries)})
    return row


SOURCE_CLASSES: tuple[dict[str, Any], ...] = (
    _src("ng_official_cb", "The Central Bank of Nigeria's statistics estate",
         layer="official",
         roots=("cbn.gov.ng",
                "cbn.gov.ng/rates/ExchRateByCurrency.asp",
                "cbn.gov.ng/rates/exrate.asp",
                "cbn.gov.ng/IntOps/Reserve.asp",
                "cbn.gov.ng/rates/mnymktind.asp",
                "cbn.gov.ng/rates/crudeoil.asp",
                "cbn.gov.ng/documents/statbulletin.asp",
                "cbn.gov.ng/MonetaryPolicy/decisions.asp"),
         languages=("en",),
         licence="free, public; HTML pages rather than an API, with no terms beyond ordinary "
                 "public access",
         access_label="PUBLIC", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         queries=("CBN official rate today", "external reserves 30-day moving average",
                  "MPC communique monetary policy rate", "cash reserve ratio circular",
                  "net open position limit circular", "farashin canjin kudi na CBN"),
         notes="THE PAGES ARE OLD-STYLE ASP ENDPOINTS THAT RENDER TABLES, which is both their "
               "virtue and their risk: stable for years, and they will break silently on a site "
               "redesign. The data plane's shape check is what stands between this pack and an "
               "empty series that reads like a calm market."),
    _src("ng_official_stats", "National Bureau of Statistics and the fiscal agencies",
         layer="official",
         roots=("nigerianstat.gov.ng", "nigerianstat.gov.ng/elibrary",
                "dmo.gov.ng", "budgetoffice.gov.ng", "oagf.gov.ng"),
         languages=("en",),
         licence="free, public",
         access_label="OPEN_DATA", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         queries=("NBS CPI report headline inflation", "NBS foreign trade statistics quarterly",
                  "FAAC allocation this month", "kason kudi na FAAC", "DMO eurobond maturity "
                  "schedule", "budget oil price benchmark"),
         notes="NBS publishes CPI, GDP and trade; the DMO publishes the debt stock and the "
               "issuance calendar; the Office of the Accountant-General publishes the monthly "
               "FAAC allocation, which is this pack's monthly liquidity number."),
    _src("ng_fmdq", "FMDQ Securities Exchange -- where Nigerian FX data actually lives",
         layer="institutional",
         roots=("fmdqgroup.com", "fmdqgroup.com/exchange/data-portal",
                "fmdqgroup.com/markets/foreign-exchange"),
         languages=("en",),
         licence="free public daily summaries; deeper historical products are commercial and are "
                 "not redistributed",
         access_label="PUBLIC_WITH_TERMS", credibility="AUTHORITATIVE",
         predictive_state="UNTESTED",
         queries=("NFEM daily rate high low close", "FX market turnover daily NFEM",
                  "number of deals interbank FX", "EFEMS matching system daily summary",
                  "NAFEM historical rate"),
         notes="THE NFEM RATE, THE DAILY RANGE, THE TURNOVER AND THE DEAL COUNT. A researcher "
               "who goes to the equity exchange for Nigerian market data has gone to the wrong "
               "building. This is the single highest-value institutional route in the pack."),
    _src("ng_exchange_paid", "NGX Group market data (PAID, key required)",
         layer="institutional",
         roots=("ngxgroup.com", "data.ngxgroup.com", "docs.ngxgroup.com"),
         languages=("en",),
         licence="PAID, key required. Catalogued and priced by expected information gain against "
                 "its cost; NEVER fetched without a key present on this box, and never "
                 "redistributed",
         access_label="LICENSED", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         queries=("NGX All-Share Index daily close", "NGX market data API documentation",
                  "NGX foreign portfolio participation report", "NGX domestic and foreign "
                  "investor report"),
         notes="Listed so the cost is VISIBLE AND ARGUABLE rather than invisible. Under the "
               "two-lane order the equity data can never mint a statistical hypothesis, so its "
               "expected information gain for THIS desk is index-level and flow content only -- "
               "which is exactly the number the EVIG pricing in africa_interaction.py values. "
               "Machine use IS permitted under the vendor's terms WITH a key; without one the "
               "plane reports NO_KEY by name, which is a configuration state and not a dead "
               "route."),
    _src("ng_academic", "Nigerian and West African academic and policy literature",
         layer="academic",
         roots=("cbn.gov.ng Economic and Financial Review", "niser.gov.ng",
                "papers.ssrn.com (Nigerian FX and parallel-market studies)",
                "aercafrica.org", "journals.ezenwaohaetorc.org", "cbn.gov.ng working papers"),
         languages=("en",),
         licence="mixed; the CBN's own review is open, journals often licensed. Never scrape a "
                 "paywall",
         access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("Nigeria parallel market premium determinants", "naira exchange rate "
                  "pass-through inflation", "FAAC allocation money supply Nigeria",
                  "oil revenue fiscal dominance Nigeria", "dual exchange rate rent seeking"),
         notes="THE NIGERIAN PARALLEL-MARKET LITERATURE IS UNUSUALLY DEEP because the wedge has "
               "been a live policy question for forty years. It is the best external check on "
               "any premium mechanism this pack proposes, and it will usually have tested the "
               "obvious version already."),
    _src("ng_practitioner", "Nigerian professional market commentary",
         layer="practitioner",
         roots=("nairametrics.com", "proshare.co", "businessday.ng",
                "cardinalstone.com and comparable local research notes",
                "financialnigeria.com", "arise.tv business"),
         languages=("en",),
         licence="public web; mined for VERBATIM CLAIMS only, never for advice",
         access_label="PUBLIC", credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("naira outlook after MPC", "FX turnover decline analysis", "reserves accretion "
                  "outlook Nigeria", "Dangote refinery crude intake update",
                  "eurobond yield Nigeria commentary"),
         notes="Nairametrics and Proshare are the two that reliably publish the NFEM turnover "
               "and deal count in a readable form on the day, which makes them a practical "
               "cross-check on the FMDQ page's shape."),
    _src("ng_retail_ecology", "Nairaland, the trading boards and the crowd in four languages",
         layer="retail_ecology",
         roots=("nairaland.com/business", "nairaland.com/investment",
                "nairaland.com/politics (subsidy and FX threads)",
                "reddit.com/r/Nigeria (economy threads)",
                "public Telegram and WhatsApp-adjacent BDC rate channels, described generically",
                "public X/Twitter threads quoting the street rate"),
         languages=("en", "ha", "yo", "ig"),
         licence="public web; mined for VERBATIM CLAIMS only, never for personal data and never "
                 "for advice",
         access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
         predictive_state="NARRATIVE_FEATURE",
         queries=("aboki rate today", "black market dollar rate now", "farashin dala yau",
                  "canjin kudi aboki yau", "owó dọ́là lónìí", "ọnụahịa dollar taa",
                  "dollar don rise", "naira don fall", "wetin be the rate for Wuse Zone 4"),
         notes="LOW WEIGHT, NEVER DROPPED, AND IN NIGERIA IT IS NOT OPTIONAL. The parallel rate "
               "has no official publisher: it exists as quotes on boards, in Hausa on northern "
               "trading channels, and in Pidgin on Lagos threads. This is the ONLY route to the "
               "observable that the pack's whole capital-control mechanism is built on. Carried "
               "at WEEKLY resolution with corroboration across independent reporters; a single "
               "day's street quote is pit_feasible=False and is never an event anchor."),
    _src("ng_retail_fringe", "Fringe, contradicted and scam-adjacent public material",
         layer="retail_ecology",
         roots=("'naira to 5000' and imminent-collapse prediction threads",
                "Ponzi and high-yield-scheme post-mortems (the MMM and CBEX episodes are the "
                "canonical Nigerian cases)",
                "SEC Nigeria and EFCC public warnings and enforcement notices",
                "public complaint threads about failed FX and investment platforms"),
         languages=("en", "ha", "yo", "ig"),
         licence="public web; verbatim claims only, no personal data, no re-publication",
         access_label="PUBLIC_SOCIAL", credibility="FRINGE",
         predictive_state="NARRATIVE_FEATURE",
         queries=("naira go crash to 5000", "SEC Nigeria warning investment scheme",
                  "ponzi scheme Nigeria collapse", "japa savings dollar hedge advice",
                  "kudin haram gargadi", "forex platform don scam me"),
         notes="KEPT ON PURPOSE AND WEIGHTED NEAR ZERO. A devaluation rumour that turned out "
               "wrong is still evidence about EXPECTATIONS while the official rate insisted "
               "otherwise -- and in Nigeria the expectation is the mechanism. Scheme collapses "
               "are evidence about the plumbing: which channels retail actually uses to hold "
               "dollars, and where the friction is. This is the class a tidy-minded crawler "
               "deletes first, and deleting it would remove exactly the material that "
               "distinguishes a stressed retail market from a calm one."),
    _src("ng_app_ecosystem", "The apps Nigerians actually price the dollar in",
         layer="app_ecosystem",
         roots=("abokifx.com and its rate app (a widely quoted parallel-rate aggregator)",
                "bamboo, risevest, trove and chaka -- retail offshore investing apps and their "
                "public fee and rate pages",
                "chippercash, opay, palmpay and moniepoint public rate and status pages",
                "flutterwave and paystack public status and FX-rate documentation",
                "app store and play store listings and public release notes for the above"),
         languages=("en", "ha", "yo", "ig"),
         licence="public listings and documentation; no account creation, no scraping behind a "
                 "login, no personal data",
         access_label="PUBLIC_WITH_TERMS", credibility="UNRELIABLE", predictive_state="UNTESTED",
         queries=("abokiFX rate today", "aboki dollar rate app", "Bamboo funding rate naira",
                  "Chipper Cash dollar rate", "Moniepoint dollar transfer rate",
                  "PalmPay dollar wallet rate"),
         notes="A LAYER THAT MATTERS FAR MORE IN NIGERIA THAN IN A DEVELOPED MARKET, and one "
               "with its own history: a parallel-rate aggregator app was publicly accused by the "
               "authorities of setting rather than reporting the rate, which is itself a "
               "measurement of how much the market watches it. These apps are where tens of "
               "millions of people SEE a dollar price, and that seen price is the expectation "
               "the pack's premium mechanism runs on. Credibility is UNRELIABLE by construction "
               "-- they aggregate quotes, not transactions -- and that is the honest label."),
    _src("ng_media", "Nigerian press in English, Hausa, Yoruba and Igbo",
         layer="media",
         roots=("punchng.com", "premiumtimesng.com", "thecable.ng", "channelstv.com/business",
                "bbc.com/hausa (economy and market coverage)",
                "bbc.com/yoruba and bbc.com/igbo", "dailytrust.com (northern coverage)",
                "leadership.ng"),
         languages=("en", "ha", "yo", "ig"),
         licence="public headlines and article text; respect robots and rate limits",
         access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("naira exchange rate news today", "CBN devalue naira announcement",
                  "farashin man fetur ya karu", "NNPC force majeure terminal",
                  "subsidy removal protest", "epo ti won ni owo ga"),
         notes="BBC HAUSA IS NOT A CURIOSITY, IT IS THE NORTHERN MARKET'S NEWS SOURCE, and the "
               "northern trading corridor is where a large share of physical currency changes "
               "hands. Daily Trust covers the same ground in English. An English-Lagos-only "
               "media crawl systematically misses half the country's FX ecology."),
    _src("ng_terms_restricted", "Sources whose terms forbid machine extraction",
         layer="media",
         roots=("subscription-only research portals covering Nigerian fixed income and FX whose "
                "terms of use forbid automated access",
                "vendor terminals redistributing FMDQ and NGX data",
                "paywalled international press archives covering Nigerian policy"),
         languages=("en",),
         licence="LICENSED or PUBLIC_WITH_TERMS where the terms explicitly forbid automated "
                 "extraction",
         access_label="ACCESS_UNCLEAR", credibility="RELIABLE", predictive_state="UNTESTED",
         machine_use_allowed=True,
         queries=("(none -- this row is REGISTERED AND NEVER QUERIED)",),
         notes="REGISTERED, NEVER SCRAPED, NEVER OMITTED. machine_use_allowed=True is the whole "
               "content of this row. The desk knows these sources exist and knows roughly what "
               "they would add; it does not take them. Omitting the row instead would make the "
               "refusal invisible and would let a later session 'discover' the source and "
               "quietly breach the terms -- which is the exact failure mode this label exists "
               "to prevent. ACCESS_UNCLEAR rather than LICENSED because the class is "
               "heterogeneous and some members' terms have not been individually read; an "
               "unread term is not a permission."),
    _src("ng_archive", "Back editions, superseded bulletins and captures of moved pages",
         layer="archive",
         roots=("cbn.gov.ng Statistical Bulletin back editions (annual, to the 1970s)",
                "nigerianstat.gov.ng e-library archive",
                "web.archive.org captures of the CBN rates and reserves ASP pages",
                "dmo.gov.ng historical debt reports",
                "opec.org Monthly Oil Market Report archive"),
         languages=("en",),
         licence="free, public archives",
         access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         queries=("CBN statistical bulletin 2015 edition", "NBS CPI archive pre-rebasing",
                  "web archive cbn.gov.ng exrate", "OPEC MOMR archive Nigeria production",
                  "DMO debt report historical"),
         notes="THE LAYER THAT MAKES NIGERIA'S THREE SERIES BREAKS SURVIVABLE. The benchmark "
               "rate has been called I&E, NAFEM and NFEM under three different definitions, the "
               "CPI was rebased, and the balance-of-payments tables are restated across "
               "editions -- so the only way to know what a number MEANT when it was published "
               "is the edition it was published in. The Internet Archive is also the only route "
               "back to a CBN page whose shape changed, which is how a SHAPE_CHANGED verdict in "
               "the data plane gets diagnosed rather than merely recorded."),
    _src("ng_physical_economy", "Barrels, terminals, refineries and ports, measured directly",
         layer="physical_economy",
         roots=("nuprc.gov.ng (monthly crude and condensate production by terminal)",
                "nnpcgroup.com", "opec.org Monthly Oil Market Report (secondary sources)",
                "nigerianports.gov.ng", "publicly reported Dangote refinery crude intake and "
                "product cargoes", "nigerianoilandgasonline.com"),
         languages=("en",),
         licence="free, public",
         access_label="OPEN_DATA", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         queries=("NUPRC monthly crude oil production by terminal", "Bonny Light force majeure",
                  "OPEC secondary sources Nigeria production", "Dangote refinery crude cargo",
                  "PMS import volume Nigeria", "man fetur shigo da kaya"),
         notes="THE NUPRC FIGURE AND OPEC'S SECONDARY-SOURCE ESTIMATE OFTEN DISAGREE, sometimes "
               "by a material fraction of output, and THE DISAGREEMENT IS ITSELF THE OBSERVABLE: "
               "it is a measure of how much crude is actually leaving versus how much is "
               "reported. A study that uses only one of the two has silently taken a side."),
    _src("ng_source_graph", "How new Nigerian sources are found, and what is refused",
         layer="source_graph",
         roots=("citation and data-annex trails in IMF Article IV Nigeria staff reports",
                "World Bank Nigeria Development Update reference lists",
                "reference lists in CBN Economic and Financial Review articles",
                "outbound link graphs from cbn.gov.ng and nigerianstat.gov.ng",
                "ecowas.int, bceao.int, afdb.org and afreximbank.com regional publications",
                "the desk's own frontier map in desks/mt5/data/"),
         languages=("en", "fr"),
         licence="free, public",
         access_label="PUBLIC", credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("IMF Article IV Nigeria statistical annex", "World Bank Nigeria Development "
                  "Update", "BCEAO statistiques taux de change", "AfDB Nigeria country report"),
         notes="THE META-LAYER, AND THE ONE THAT KEEPS THE OTHER NINE FROM GOING STALE. IMF and "
               "World Bank staff reports are the highest-yield entry point because their annexes "
               "cite series the authorities do not advertise, and for Nigeria they routinely "
               "publish a parallel-rate estimate the authorities do not. THE REGIONAL LEG IS "
               "DELIBERATE: BCEAO and BEAC are the euro-pegged neighbours, and they are the "
               "cleanest natural control in West Africa for every Nigerian FX hypothesis -- same "
               "region, same commodities, same weather, opposite monetary regime. THIS ROW ALSO "
               "CARRIES THE REFUSALS: (1) ANY crypto-exchange venue order book, API, P2P board "
               "or native feed is REFUSED (universe mandate 2026-08-18), and Nigeria is "
               "precisely where this has to be said out loud because its peer-to-peer market "
               "functions as a parallel FX channel and would be the most tempting venue ground "
               "on the continent -- the premium is taken from public commentary only, is marked "
               "pit_feasible=False, and its executable leg is the broker's own BTCUSD CFD; "
               "(2) single-name NGX hypothesis mining is REFUSED (two-lane order 2026-09-06); "
               "(3) redistribution of any paid NGX or vendor product is REFUSED, and is "
               "registered as its own row above rather than omitted."),
)

#: EVERY LAYER ACCOUNTED FOR, BY NAME. Derived from the rows above rather than typed, so it
#: cannot drift from them. A layer with no row resolves to an ABSENT string carrying the reason,
#: because a blank reads as "nothing there" when it usually means "nobody looked".
SOURCE_LAYER_COVERAGE: dict[str, str] = {
    layer: (", ".join(s["id"] for s in SOURCE_CLASSES if s["layer"] == layer)
            or f"ABSENT: no {layer} source declared for {NAME}")
    for layer in LAYERS
}


# --------------------------------------------------------------------------- datasets

DATASETS: tuple[dict[str, Any], ...] = (
    dataset("ng_cbn_exchange_rate_by_currency",
            source="CBN exchange rate by currency (cbn.gov.ng/rates/ExchRateByCurrency.asp)",
            coverage="the CBN's published buying, selling and central rates against a list of "
                     "currencies, by date",
            frequency="daily",
            publication_lag_days=1.0,
            revisions="a published daily rate is not revised; the SERIES DEFINITION has changed "
                      "three times (I&E, NAFEM, NFEM) and most vendors splice them silently, "
                      "which is a break dressed as a revision",
            licence="free, public",
            history_from="the page serves a selectable date range; the usable modern history "
                         "begins with the I&E window",
            pit_feasible=True,
            assets=("USDZAR", "USDTRY", "XBRUSD"),
            mechanism_families=("fx_regime_sensor", "regime_state"),
            how_to_fetch="GET the ASP page with a date parameter and parse the rendered table; "
                         "vault the bytes so a site redesign is detectable as a shape change "
                         "rather than as an empty series"),
    dataset("ng_nfem_daily",
            source="FMDQ NFEM daily FX market summary",
            coverage="the NFEM rate high, low and close, the day's TURNOVER in US dollars and "
                     "the DEAL COUNT",
            frequency="daily",
            publication_lag_days=0.5,
            revisions="occasionally restated for late trade reporting",
            licence="free, public daily summary",
            history_from="December 2024 for NFEM as named; NAFEM and I&E history exists under "
                         "the earlier definitions and MUST NOT be spliced without a regime flag",
            pit_feasible=True,
            assets=("USDZAR", "USDTRY", "USDBRL", "XBRUSD"),
            mechanism_families=("fx_regime_sensor", "liquidity_stress", "regime_state"),
            how_to_fetch="the FMDQ daily market summary; the desk's stress state is computed by "
                         "data_plane.nfem_stress_state and a MISSING DAY IS UNMEASURED, NEVER A "
                         "ZERO -- a holiday and a seized market must never look alike"),
    dataset("ng_cbn_external_reserves",
            source="CBN external reserves (cbn.gov.ng/IntOps/Reserve.asp)",
            coverage="gross external reserves, published as a thirty-day moving average",
            frequency="near-daily",
            publication_lag_days=2.0,
            revisions="the moving average is recomputed as its window rolls, so YESTERDAY'S "
                      "PUBLISHED VALUE CHANGES WITHOUT ANY NEW INFORMATION -- a property that "
                      "will produce spurious 'revisions' in any naive vintage diff and is "
                      "flagged here so it is recognised rather than discovered",
            licence="free, public",
            history_from="2000s",
            pit_feasible=True,
            assets=("USDZAR", "UST10Y"),
            mechanism_families=("fx_regime_sensor", "sovereign_stress"),
            how_to_fetch="GET the reserves page; store the raw table. The SMOOTHING IS IN THE "
                         "SOURCE and cannot be undone from the published series alone"),
    dataset("ng_cbn_money_market",
            source="CBN money market indicators (cbn.gov.ng/rates/mnymktind.asp)",
            coverage="open buy-back, overnight and interbank call rates",
            frequency="daily",
            publication_lag_days=1.0,
            revisions="not revised",
            licence="free, public",
            history_from="2000s",
            pit_feasible=True,
            assets=("USDZAR", "UST05Y"),
            mechanism_families=("liquidity_stress", "policy_reaction"),
            how_to_fetch="GET and parse the rendered table. A NAIRA LIQUIDITY SPIKE AROUND THE "
                         "FAAC WINDOW is the specific joint observation this series exists for "
                         "in this pack"),
    dataset("ng_cbn_crude_price",
            source="CBN crude oil price series (cbn.gov.ng/rates/crudeoil.asp)",
            coverage="the CBN's own reference crude price, which is the fiscal input",
            frequency="daily to weekly",
            publication_lag_days=2.0,
            revisions="not revised",
            licence="free, public",
            history_from="2000s",
            pit_feasible=True,
            assets=("XBRUSD", "XTIUSD"),
            mechanism_families=("commodity_production_sensor", "fiscal_state"),
            how_to_fetch="GET and parse; useful mainly as the CBN's OWN VIEW of the price, "
                         "which is what enters its fiscal arithmetic and can differ from Brent"),
    dataset("ng_cbn_statistical_bulletin",
            source="CBN Statistical Bulletin (cbn.gov.ng/documents/statbulletin.asp)",
            coverage="money and credit, external payments and balance of payments, government "
                     "finance, and the business and consumer expectation surveys",
            frequency="quarterly and annual, with monthly tables inside",
            publication_lag_days=90.0,
            revisions="HEAVILY REVISED. The balance-of-payments tables in particular are "
                      "restated across editions, so the bulletin is the pack's clearest case "
                      "for keeping every edition rather than the latest",
            licence="free, public",
            history_from="1970s in the archive",
            pit_feasible=True,
            assets=("USDZAR", "UST10Y", "XBRUSD"),
            mechanism_families=("macro_surprise", "sovereign_stress"),
            how_to_fetch="download each edition as published and vault it; the bulletin is the "
                         "only public route to Nigerian external-payments detail"),
    dataset("ng_cbn_expectation_surveys",
            source="CBN business and consumer expectation surveys",
            coverage="firms' and households' stated expectations for the exchange rate, "
                     "inflation and credit conditions",
            frequency="quarterly (business) and monthly to quarterly (consumer)",
            publication_lag_days=30.0,
            revisions="not revised; the SAMPLE changes between rounds, which is a different "
                      "problem and is declared",
            licence="free, public",
            history_from="2000s",
            pit_feasible=True,
            assets=("USDZAR", "XBRUSD"),
            mechanism_families=("expectations", "fx_regime_sensor"),
            how_to_fetch="the survey PDFs on the CBN site. THE EXCHANGE-RATE EXPECTATION "
                         "QUESTION IS THE VALUABLE ONE: a survey-measured devaluation "
                         "expectation is a rare, dated, official read on the thing the parallel "
                         "premium is supposed to proxy"),
    dataset("ng_nbs_cpi",
            source="National Bureau of Statistics consumer price index",
            coverage="headline, food and core inflation, monthly, with a state breakdown",
            frequency="monthly",
            publication_lag_days=15.0,
            revisions="the BASKET WAS REBASED in 2025, which is a SERIES BREAK and not a "
                      "revision; a pre- and post-rebasing splice measures two different indices",
            licence="free, public",
            history_from="2009 for the previous basket; the rebased series starts again",
            pit_feasible=True,
            assets=("USDZAR", "UST10Y"),
            mechanism_families=("macro_surprise", "policy_reaction"),
            how_to_fetch="the NBS e-library release; record the publication timestamp, which is "
                         "what was knowable, not the reference month"),
    dataset("ng_nbs_trade",
            source="National Bureau of Statistics foreign trade statistics",
            coverage="exports and imports by product and partner, quarterly",
            frequency="quarterly",
            publication_lag_days=75.0,
            revisions="revised across editions",
            licence="free, public",
            history_from="2000s",
            pit_feasible=True,
            assets=("XBRUSD", "USDCNH", "EURUSD"),
            mechanism_families=("trade_shipping_logistics", "china_africa_transmission"),
            how_to_fetch="NBS e-library; the CHINA SHARE of Nigerian imports is the leg this "
                         "dataset serves in the China-Africa family"),
    dataset("ng_crude_production",
            source="NUPRC monthly crude and condensate production, with OPEC secondary sources "
                   "as the independent check",
            coverage="production by terminal and by stream, monthly",
            frequency="monthly",
            publication_lag_days=25.0,
            revisions="revised; and the NUPRC figure and OPEC's secondary-source estimate OFTEN "
                      "DISAGREE materially -- the disagreement is itself the observable",
            licence="free, public",
            history_from="2009 at NUPRC; longer at OPEC",
            pit_feasible=True,
            assets=("XBRUSD", "XTIUSD"),
            mechanism_families=("commodity_production_sensor", "supply_shock"),
            how_to_fetch="the NUPRC monthly report and the OPEC Monthly Oil Market Report; KEEP "
                         "BOTH and treat the gap as data"),
    dataset("ng_dmo_debt",
            source="Debt Management Office debt stock and issuance calendar",
            coverage="external and domestic debt stock, eurobond issuance and maturities, the "
                     "domestic auction calendar",
            frequency="quarterly stock, monthly auctions",
            publication_lag_days=45.0,
            revisions="restated across editions",
            licence="free, public",
            history_from="2010s",
            pit_feasible=True,
            assets=("UST10Y", "UKGILT", "USDZAR"),
            mechanism_families=("sovereign_stress", "frontier_transmission"),
            how_to_fetch="dmo.gov.ng publications; the EUROBOND MATURITY CALENDAR is the "
                         "scheduled-risk object here"),
    dataset("ng_faac_allocation",
            source="Office of the Accountant-General of the Federation, monthly FAAC allocation",
            coverage="the total federally collected revenue distributed each month, in naira, "
                     "split across the three tiers of government",
            frequency="monthly",
            publication_lag_days=3.0,
            revisions="not revised; the figure is announced at the meeting",
            licence="free, public, carried by the national press",
            history_from="2000s",
            pit_feasible=True,
            assets=("USDZAR", "XBRUSD"),
            mechanism_families=("fiscal_liquidity", "fx_regime_sensor"),
            how_to_fetch="the OAGF communique and press coverage; the ANNOUNCEMENT DATE IS NOT "
                         "DERIVABLE FROM A RULE and is read from the record -- "
                         "`ng_faac_window` returns the conditioning window, never a guessed date"),
    dataset("ng_ngx_market_data",
            source="NGX Group market data REST API (data.ngxgroup.com)",
            coverage="index levels, equity prices, trade and order statistics",
            frequency="intraday to daily",
            publication_lag_days=0.0,
            revisions="n/a",
            licence="PAID, key required. Catalogued and priced by expected information gain "
                    "against cost; never fetched without a key and never redistributed",
            history_from="per the vendor's terms",
            pit_feasible=True,
            assets=("UK100",),
            mechanism_families=("local_market_ecology",),
            how_to_fetch="NEVER WITHOUT A KEY. The plane reports NO_KEY by name, which is a "
                         "configuration state and not a dead route. Its expected information "
                         "gain for THIS desk is index-level and flow content only, because the "
                         "two-lane order forbids single-name hypothesis mining -- and that is "
                         "exactly the number the EVIG pricing in africa_interaction.py values."),
)


# --------------------------------------------------------------------------- actors
ACTORS: tuple[dict[str, Any], ...] = (
    actor("Central Bank of Nigeria as exchange-rate manager",
          holds="external reserves, the FX auction window, the net open position rule and the "
                "MPR",
          forced_to=("supply dollars to a market that structurally demands more than it earns",
                     "choose between defending a rate and preserving reserves",
                     "announce and clear a forwards backlog it accumulated"),
          when="MPC six times a year; auctions and circulars episodic and announced",
          information=("reserves", "oil receipts", "the parallel premium",
                       "the forwards backlog", "IMF and rating-agency pressure"),
          constraints=("reserves that are a published, falling number",
                       "an import bill that does not fall when the currency does",
                       "political cost of a devaluation"),
          instruments=("USDZAR", "USDTRY", "XBRUSD", "UST10Y"),
          counterparties=("Nigerian banks", "BDC operators", "importers",
                          "foreign portfolio investors"),
          observables=("NFEM rate, turnover and deal count", "reserves",
                       "auction announcements", "net open position circulars",
                       "the official-parallel spread"),
          impact="a regime change reprices Nigerian risk and transmits to frontier and EM "
                 "carriers; the naira itself is untradable here, so the impact is measured on "
                 "USDZAR, USDTRY and the eurobond-adjacent rates leg",
          persistence="the regime persists until reserves force a change, which is why the "
                      "reserve path is the leading indicator of the regime",
          falsifier="if Nigerian devaluation and unification events produce no measurable "
                    "abnormal move in USDZAR or USDTRY relative to matched non-event days, the "
                    "frontier-transmission channel does not exist and this pack's carriers are "
                    "the wrong ones",
          notes="The CBN's intervention reaction function is the exact thing the SARB does not "
                "have. Each is the other's control."),
    actor("NNPC and the crude export complex",
          holds="Nigeria's crude production, its export terminals and its swap contracts",
          forced_to=("meet or miss an OPEC quota that is public",
                     "declare force majeure when a terminal or pipeline is down",
                     "fund federal revenue from dollar receipts"),
          when="monthly production reporting; force majeure announcements are immediate",
          information=("terminal uptime", "oil theft and vandalism levels",
                       "OPEC quota", "the crude-for-product swap terms"),
          constraints=("pipeline security and oil theft, which have at times removed a "
                       "substantial fraction of output",
                       "OPEC quota discipline", "field decline and underinvestment"),
          instruments=("XBRUSD", "XTIUSD", "USDZAR"),
          counterparties=("international oil companies", "trading houses", "the federation"),
          observables=("NUPRC monthly production", "OPEC secondary-source estimates",
                       "force majeure declarations", "terminal loading programmes"),
          impact="Nigeria is a small share of global supply, so THE EDGE IS ABOUT DISRUPTION "
                 "EVENTS AND NOT STEADY-STATE VOLUME: a force majeure at a major terminal is a "
                 "dated, discrete supply event in a light sweet grade; a 2% quarterly decline "
                 "is not a Brent signal and the pack refuses to claim it is",
          persistence="the disruption regime has persisted for over a decade with varying "
                      "intensity",
          falsifier="if XBRUSD shows no abnormal return in the sessions following Nigerian force "
                    "majeure declarations relative to matched non-event sessions, the disruption "
                    "channel carries no information the market has not already priced",
          notes="THE DISAGREEMENT BETWEEN NUPRC AND OPEC IS DATA. Using only one silently takes "
                "a side on how much crude is actually leaving."),
    actor("The federation and the FAAC monthly allocation",
          holds="federally collected revenue, most of it dollar oil receipts, distributed "
                "monthly in naira",
          forced_to=("convert dollar receipts into naira and distribute them on a monthly cycle",
                     "publish the allocation total"),
          when="monthly, in the second half of the month; the figure is announced",
          information=("oil receipts", "the exchange rate used for conversion",
                       "non-oil revenue"),
          constraints=("a constitutional revenue-sharing formula",
                       "state governments with immediate spending obligations"),
          instruments=("USDZAR", "XBRUSD"),
          counterparties=("state and local governments", "contractors", "the banking system"),
          observables=("the announced FAAC total", "naira interbank rates in the following "
                       "days", "the parallel premium in the following week"),
          impact="A SCHEDULED, PUBLISHED, LARGE NAIRA LIQUIDITY INJECTION. The local hypothesis "
                 "is that it becomes FX demand within days; the pack treats that as a testable "
                 "claim with a window, not as folklore",
          persistence="structural; the mechanism is constitutional",
          falsifier="if the parallel premium and the naira interbank rate show no differential "
                    "behaviour in the week following a FAAC announcement relative to matched "
                    "weeks, the liquidity-to-FX channel is not measurable at this frequency",
          notes="A monthly liquidity event with a published size is rare anywhere in the world."),
    actor("Nigerian commercial banks under net open position limits",
          holds="the banking system's FX positions and its correspondent relationships",
          forced_to=("hold FX exposure within a regulatory cap",
                     "sell dollars on a stated deadline when the cap is tightened",
                     "ration FX to customers when the interbank market is thin"),
          when="continuous; cap changes arrive by circular with a deadline",
          information=("the cap", "their own position", "customer demand",
                       "the CBN's auction schedule"),
          constraints=("the net open position rule",
                       "correspondent banking access, which has itself been a bottleneck",
                       "capital adequacy"),
          instruments=("USDZAR", "USDTRY"),
          counterparties=("the CBN", "importers", "foreign correspondents"),
          observables=("net open position circulars and their deadlines",
                       "NFEM turnover and deal count", "bank FX disclosures"),
          impact="A TIGHTENING IS A FORCED SALE WITH A PUBLISHED DEADLINE -- direction, trigger "
                 "and timing all in one document, which is rarer than it sounds",
          persistence="the rule is structural; its level changes by circular",
          falsifier="if NFEM turnover and the rate show no differential behaviour in the window "
                    "around a net-open-position circular relative to matched windows, the "
                    "forced-sale mechanism is not visible in the published data",
          notes="One of very few African FX mechanisms with a dated, quantified trigger."),
    actor("Bureau de Change operators and the parallel market",
          holds="the retail and small-corporate FX market outside the banking system",
          forced_to=("price off scarcity rather than off a benchmark",
                     "operate inside or outside a licensing regime that has been repeatedly "
                     "rewritten"),
          when="continuous; the street rate moves intraday and is quoted publicly",
          information=("official supply", "auction outcomes", "demand from importers and "
                       "travellers", "sentiment"),
          constraints=("licensing and capital requirements that have been raised and lowered",
                       "periodic exclusion from official FX supply"),
          instruments=("USDZAR", "BTCUSD"),
          counterparties=("travellers", "importers", "the diaspora", "the CBN when supplied"),
          observables=("the quoted street rate", "the official-parallel spread",
                       "licensing circulars"),
          impact="THE SPREAD IS THE CAPITAL CONTROL WITH A PRICE ON IT. It widens while the "
                 "control binds and closes in one step at a devaluation -- so the wedge is the "
                 "leading indicator and the step is the event",
          persistence="the parallel market has existed continuously for decades under every "
                      "regime, which is itself the strongest evidence that the wedge is "
                      "structural rather than episodic",
          falsifier="if the width of the official-parallel spread has no predictive content for "
                    "the timing or size of subsequent official devaluations, the wedge is a "
                    "coincident price rather than a leading indicator and every edge built on "
                    "it is mis-specified",
          notes="Carried as PUBLIC COMMENTARY at weekly or monthly resolution with "
                "corroboration across independent reporters; a single day's street quote is "
                "pit_feasible=False."),
    actor("Nigerian importers under FX rationing",
          holds="import obligations denominated in dollars against naira revenue",
          forced_to=("queue for official FX or pay the parallel rate",
                     "hold unsettled letters of credit when supply stops"),
          when="continuous; the queue lengthens and shortens with official supply",
          information=("auction outcomes", "the parallel rate", "the backlog's length"),
          constraints=("working capital", "supplier credit terms",
                       "the regulatory channel they are allowed to use"),
          instruments=("USDZAR", "XBRUSD"),
          counterparties=("banks", "foreign suppliers", "the CBN"),
          observables=("the forwards and letter-of-credit backlog", "import cover",
                       "trade data", "the premium"),
          impact="the QUEUE is the purest capital-control observable this civilization has: a "
                 "published length, a published clearance, and a direct consequence for the "
                 "premium when it clears",
          persistence="episodic but recurrent under every regime that has rationed FX",
          falsifier="if backlog clearance announcements produce no measurable narrowing of the "
                    "official-parallel spread within a month, the queue is not the binding "
                    "constraint the mechanism assumes",
          notes="The 2020-2024 forwards backlog is the canonical case and its clearance tranches "
                "were announced."),
    actor("Foreign portfolio investors in OMO and treasury bills",
          holds="naira carry positions that must be repatriated in dollars to be realised",
          forced_to=("wait in a repatriation queue when official FX is short",
                     "roll positions they cannot exit",
                     "price a devaluation risk they cannot hedge"),
          when="continuous; entry is at auction dates, exit is when FX is available",
          information=("the yield", "the reserve path", "the premium", "the queue"),
          constraints=("no deliverable hedge", "the repatriation queue itself",
                       "mandate limits on frontier exposure"),
          instruments=("UST05Y", "UST10Y", "USDZAR"),
          counterparties=("the CBN", "Nigerian banks", "other frontier investors"),
          observables=("capital importation statistics", "OMO auction results",
                       "reported repatriation delays"),
          impact="MONEY THAT CANNOT GET OUT IS THE CAPITAL CONTROL MADE VISIBLE, and the memory "
                 "of a queue raises the yield demanded for years afterwards -- a persistent "
                 "risk premium with a dated cause",
          persistence="the memory outlasts the queue by years, which is why post-queue yields "
                      "do not return to pre-queue levels",
          falsifier="if Nigerian yields show no persistent level shift after a documented "
                    "repatriation episode, controlling for the global rate cycle, the "
                    "queue-memory mechanism does not exist",
          notes="The carry trade has no executable leg on this account and is a conditioning "
                "observable only."),
    actor("The diaspora remittance sender",
          holds="the single most stable dollar inflow Nigeria has",
          forced_to=("choose between the official channel at the official rate and the informal "
                     "channel at the parallel rate"),
          when="continuous, with festival and year-end seasonality",
          information=("the spread between the two channels", "transfer fees",
                       "recipient preference"),
          constraints=("the international money transfer operator regime and the rate it must "
                       "pay", "compliance requirements on the sending side"),
          instruments=("USDZAR",),
          counterparties=("money transfer operators", "banks", "informal networks"),
          observables=("official remittance statistics in the CBN balance of payments",
                       "the official-parallel spread", "IMTO policy changes"),
          impact="THE CHANNEL SWITCH IS A DIRECT, MEASURABLE CONSEQUENCE OF THE WEDGE: when the "
                 "spread widens, officially recorded remittances FALL without the underlying "
                 "flow falling at all -- so a drop in the official series can mean either less "
                 "money or more informality, and the two have opposite implications",
          persistence="structural; the channel choice reappears every time the wedge widens",
          falsifier="if officially recorded remittance inflows show no relationship to the "
                    "official-parallel spread after controlling for seasonality, the channel-"
                    "switch mechanism is not present in the published data",
          notes="A rare case where a published series measures OBSERVABILITY rather than the "
                "quantity it names, and the pack says so before anybody regresses on it."),
    actor("The Dangote refinery and the refining transition",
          holds="domestic refining capacity where Nigeria previously had almost none",
          forced_to=("source crude, domestically or by import",
                     "sell refined product into a market whose pricing is politically "
                     "sensitive"),
          when="continuous, with a multi-year ramp",
          information=("crude availability and pricing", "domestic product demand",
                       "export economics"),
          constraints=("crude supply agreements and their currency of settlement",
                       "product pricing policy", "the ramp's own engineering"),
          instruments=("XBRUSD", "XTIUSD", "XNGUSD"),
          counterparties=("NNPC", "international crude sellers", "product marketers",
                          "export buyers"),
          observables=("refinery crude intake", "Nigerian refined product import volumes",
                       "product export cargoes"),
          impact="A STRUCTURAL FLIP IN NIGERIA'S TRADE COMPOSITION, from exporting crude and "
                 "importing product to refining at home -- which changes the FX demand profile "
                 "and the crude flow direction at the same time. It is a live regime change and "
                 "is declared as an era.",
          persistence="multi-year and structural once complete",
          falsifier="if Nigerian refined-product import volumes show no trend break coincident "
                    "with the refinery's reported ramp, the transition is not yet visible in "
                    "the trade data and every edge built on it is premature",
          notes="The most consequential structural change in West African energy in a "
                "generation, and the desk's evidence for it is trade statistics with a "
                "seventy-five-day lag. The lag is the constraint."),
    actor("Fuel subsidy removal and the domestic pump price",
          holds="the pass-through from crude and the exchange rate to the domestic pump price",
          forced_to=("pass through crude and FX moves once the subsidy is removed",
                     "absorb them politically when it is not"),
          when="the removal was announced 2023-05-29; pass-through is continuous thereafter",
          information=("crude", "the exchange rate", "the political tolerance for price rises"),
          constraints=("political economy", "transport cost pass-through into food prices"),
          instruments=("XBRUSD", "USDZAR"),
          counterparties=("households", "marketers", "the federation"),
          observables=("pump prices", "NBS transport and food inflation", "subsidy line items"),
          impact="AFTER REMOVAL, CRUDE AND FX MOVES REACH NIGERIAN INFLATION DIRECTLY where "
                 "before they were absorbed fiscally. The same Brent move therefore has a "
                 "different domestic consequence either side of 2023-05-29, and any "
                 "pass-through estimate pooled across that date is an average of two regimes",
          persistence="structural while the removal holds",
          falsifier="if the estimated pass-through from Brent and the exchange rate into "
                    "Nigerian headline inflation is statistically identical before and after "
                    "2023-05-29, the subsidy regime was not binding and the era is not a break",
          notes="One of the cleanest policy-regime breaks in the pack because it has a single "
                "announced date."),
    actor("International oil companies divesting onshore assets",
          holds="onshore and shallow-water Nigerian production being sold to local operators",
          forced_to=("obtain regulatory approval for each divestment",
                     "hand over fields whose output history is public"),
          when="episodic; each transaction is announced and approved on a date",
          information=("field economics", "security and theft losses",
                       "regulatory conditions"),
          constraints=("regulatory approval", "decommissioning and liability terms",
                       "local operator financing"),
          instruments=("XBRUSD", "XTIUSD"),
          counterparties=("NUPRC", "local operators", "lenders"),
          observables=("announced transactions and approvals",
                       "post-handover production from the transferred fields"),
          impact="the transferred fields' subsequent output is a NATURAL EXPERIMENT in whether "
                 "operatorship or geology explains Nigerian decline -- and the answer bears "
                 "directly on how much of the disruption discount is permanent",
          persistence="multi-year",
          falsifier="if post-divestment production from transferred assets is "
                    "indistinguishable from their pre-divestment trend, operatorship explains "
                    "nothing and the divestment wave carries no supply information",
          notes="Named as a class; no operator is ever a symbol on a docket."),
    actor("Nigerian retail users of peer-to-peer dollar channels",
          holds="small dollar balances held outside the banking system as a devaluation hedge",
          forced_to=("use whatever channel is available when official FX is rationed"),
          when="continuous, intensifying with the wedge",
          information=("the parallel rate", "official supply", "channel availability"),
          constraints=("regulatory restriction on the channels", "banking access",
                       "transaction size"),
          instruments=("BTCUSD", "USDZAR"),
          counterparties=("each other", "informal networks", "remittance senders"),
          observables=("public commentary on the local premium",
                       "regulatory statements about the channel"),
          impact="the premium is a rationed-arbitrage measure of domestic devaluation "
                 "expectation -- a household-level read on the same quantity the parallel "
                 "spread measures at wholesale",
          persistence="structural while FX is rationed",
          falsifier="if the observed local premium shows no relationship to the "
                    "official-parallel spread or to devaluation expectations in the CBN's own "
                    "survey, it is a channel artefact and not a signal",
          notes="PUBLIC COMMENTARY ONLY, pit_feasible=False. NO crypto-exchange venue, order "
                "book, API or P2P board is named, subscribed or crawled anywhere in this pack "
                "(universe mandate 2026-08-18). The executable leg is the broker's own BTCUSD "
                "CFD. Nigeria is exactly where this refusal has to be explicit."),
    actor("OPEC and the quota constraint",
          holds="Nigeria's production ceiling and the compliance table that reports it",
          forced_to=("assign a quota and publish compliance",
                     "reconcile member self-reporting with secondary-source estimates"),
          when="monthly reporting; quota decisions at scheduled and ad hoc meetings",
          information=("member production", "global balances", "compliance history"),
          constraints=("member politics", "the gap between quota and capacity -- Nigeria has "
                       "frequently produced BELOW its quota, which inverts the usual "
                       "compliance question"),
          instruments=("XBRUSD", "XTIUSD"),
          counterparties=("member states", "the market"),
          observables=("the Monthly Oil Market Report", "quota decisions",
                       "the secondary-source versus direct-communication gap"),
          impact="for most members a quota is a ceiling; FOR NIGERIA IT HAS OFTEN BEEN A TARGET "
                 "IT COULD NOT REACH, so a Nigerian quota increase is not a supply increase and "
                 "a study that treats it as one is measuring an announcement, not a barrel",
          persistence="structural while capacity is below quota",
          falsifier="if Nigerian quota changes move XBRUSD after controlling for the aggregate "
                    "OPEC decision, the country-level quota carries independent information "
                    "after all and this actor's central claim is wrong",
          notes="The inversion is the point: the usual compliance intuition is backwards here."),
)


# --------------------------------------------------------------------------- domains
DOMAINS: tuple[dict[str, Any], ...] = (
    domain("ng_fx_regime_state", "Which naira regime a date is in, and what may be pooled",
           objects=("the regime label per date", "regime boundary events",
                    "the definition of the published benchmark rate in each regime"),
           conditions=("reserve adequacy", "the parallel premium", "political cycle"),
           instruments=("USDZAR", "USDTRY", "XBRUSD"),
           controls=("the CFA zone next door, which shares the region, the commodities and the "
                     "weather and has the opposite monetary regime -- the cleanest natural "
                     "control in West Africa",
                     "matched windows inside a single regime",
                     "randomised regime assignment"),
           notes="THE FIRST DOMAIN BECAUSE IT GATES EVERY OTHER ONE. A naira study pooled "
                 "across 2023-06-14 is measuring two currencies with one name."),
    domain("ng_nfem_liquidity", "Turnover and deal count as the FX-stress state",
           objects=("daily turnover", "daily deal count", "the published intraday range",
                    "the joint state of all three"),
           conditions=("the regime", "FAAC week", "auction days", "holiday gaps"),
           instruments=("USDZAR", "USDTRY", "USDBRL"),
           controls=("matched days in the same regime with normal turnover",
                     "randomised assignment of the collapse flag",
                     "the rate series alone, which should carry LESS information than the "
                     "quantity if the pack's central claim is right"),
           notes="THE PACK'S FLAGSHIP. A missing day is UNMEASURED, never a zero -- a holiday "
                 "and a seized market must never look alike."),
    domain("ng_parallel_premium", "The official-versus-parallel wedge as a capital-control price",
           objects=("the spread in per cent", "its width, persistence and rate of change",
                    "the one-step closures that mark devaluations"),
           conditions=("official supply", "the backlog", "the regime"),
           instruments=("USDZAR", "USDTRY", "BTCUSD"),
           controls=("periods of equal reserve cover with no wedge",
                     "the CFA neighbour, which has no wedge by construction",
                     "randomised devaluation dates"),
           notes="Public commentary at weekly resolution with corroboration; a single day's "
                 "street quote is pit_feasible=False and is never used as an event anchor."),
    domain("ng_reserves_pressure", "The reserve path as the regime's leading indicator",
           objects=("the published thirty-day moving average", "import cover",
                    "the rate of drawdown"),
           conditions=("oil receipts", "the intervention schedule", "eurobond issuance"),
           instruments=("USDZAR", "UST10Y", "XBRUSD"),
           controls=("other frontier sovereigns' reserve paths",
                     "matched windows with equal oil receipts",
                     "randomised drawdown dates"),
           notes="THE PUBLISHED SERIES IS A FILTER. Differencing a thirty-day moving average is "
                 "differencing the filter, not the stock."),
    domain("ng_oil_production", "Disruption events, not steady-state volume",
           objects=("force majeure declarations", "terminal loading programmes",
                    "the NUPRC-versus-OPEC estimate gap"),
           conditions=("the security situation", "OPEC quota", "global balances"),
           instruments=("XBRUSD", "XTIUSD"),
           controls=("matched non-event sessions",
                     "disruptions in other light sweet producers",
                     "randomised force majeure dates"),
           notes="Nigeria is a small share of global supply. The pack claims DISCRETE EVENTS "
                 "and explicitly refuses to claim a steady-state volume signal."),
    domain("ng_fiscal_faac_liquidity", "The monthly naira liquidity injection and its FX echo",
           objects=("the announced FAAC total", "naira interbank rates after it",
                    "the parallel premium in the following week"),
           conditions=("the oil price", "the conversion rate used", "month-end demand"),
           instruments=("USDZAR", "XBRUSD"),
           controls=("the same calendar window in months with no announcement",
                     "randomised announcement dates inside the window",
                     "month-end importer demand, which overlaps and must be separated"),
           notes="A monthly liquidity event with a PUBLISHED SIZE. The window, not a guessed "
                 "date, is what the miner conditions on."),
    domain("ng_portfolio_repatriation_queue", "Money that cannot leave, and the premium it "
                                              "leaves behind",
           objects=("capital importation statistics", "reported repatriation delays",
                    "the backlog's announced length and its clearance tranches"),
           conditions=("official FX supply", "the yield on offer", "the global rate cycle"),
           instruments=("UST05Y", "UST10Y", "USDZAR"),
           controls=("the global frontier yield level",
                     "matched frontier sovereigns with no queue",
                     "pre-queue and post-queue yields at equal global rates"),
           notes="The memory outlasts the queue by years, which is the testable part."),
    domain("ng_inflation_passthrough", "Crude and FX into Nigerian prices, before and after the "
                                       "subsidy",
           objects=("headline, food and core CPI", "pump prices",
                    "the estimated pass-through coefficient"),
           conditions=("the subsidy regime", "the FX regime", "the rebasing break"),
           instruments=("XBRUSD", "USDZAR", "UST10Y"),
           controls=("the pre-2023-05-29 sample as the regime control",
                     "the CFA neighbour with a pegged currency and different subsidy policy",
                     "randomised removal dates"),
           notes="Two breaks in one series: the subsidy removal and the CPI rebasing. Neither "
                 "is a revision and both are eras."),
    domain("ng_trade_and_refining_shift", "The structural flip from product import to domestic "
                                          "refining",
           objects=("refined product import volumes", "crude intake",
                    "product export cargoes", "the trade composition"),
           conditions=("the refinery ramp", "crude supply agreements", "product pricing policy"),
           instruments=("XBRUSD", "XTIUSD", "XNGUSD"),
           controls=("the pre-ramp import trend",
                     "other West African product importers",
                     "randomised ramp dates"),
           notes="The evidence is trade statistics with a seventy-five-day lag; the lag is the "
                 "binding constraint on how early this can be measured."),
    domain("ng_frontier_stress_transmission", "Nigeria as a frontier-risk sensor for tradable "
                                              "carriers",
           objects=("the joint state of turnover, premium and reserves",
                    "eurobond spread moves", "devaluation events"),
           conditions=("the global EM risk state", "the dollar", "oil"),
           instruments=("USDZAR", "USDTRY", "USDBRL", "UST10Y"),
           controls=("the global EM factor, which must be removed before any Nigeria-specific "
                     "claim survives",
                     "matched EM stress episodes with no Nigerian component",
                     "randomised event dates"),
           notes="THE DOMAIN THE WHOLE PACK IS FOR. If Nigerian stress does not reach a tradable "
                 "carrier, Tier 2 is the wrong rank and the pack should say so."),
    domain("ng_session_microstructure_carrier", "When Nigerian information arrives, and into "
                                                "which session",
           objects=("the CBN briefing window", "the NFEM publication time",
                    "the Lagos-to-London overlap"),
           conditions=("holidays, which stop the data and not the carriers",
                       "the London session state"),
           instruments=("USDZAR", "XBRUSD", "USDTRY"),
           controls=("matched sessions with no Nigerian publication",
                     "the same clock time on days with no release",
                     "randomised publication times"),
           notes="A TRANSMISSION-ONLY PACK STILL HAS A CLOCK: the information has an arrival "
                 "time even when the instrument it moves is somebody else's."),
    domain("ng_policy_reaction", "The MPC, the corridor and the cash reserve ratio",
           objects=("the MPR decision against expectation", "CRR changes",
                    "the communique language", "the briefing's observed timestamp"),
           conditions=("the inflation regime", "the FX regime", "the global rate cycle"),
           instruments=("USDZAR", "UST05Y", "XBRUSD"),
           controls=("matched non-MPC days",
                     "decisions with the same rate move and a different CRR move",
                     "other frontier central banks in the same week"),
           notes="A RATE STUDY THAT IGNORES THE CRR IS MISSING HALF THE INSTRUMENT."),
    domain("ng_risk_proxy_crypto_premium", "The household devaluation hedge under rationed "
                                           "arbitrage",
           objects=("publicly reported local premium",
                    "the relationship between the premium and the wholesale wedge"),
           conditions=("official FX supply", "regulatory restriction", "devaluation "
                       "expectation"),
           instruments=("BTCUSD", "USDZAR"),
           controls=("periods of equal wedge with no premium",
                     "other rationed markets",
                     "randomised premium dates"),
           notes="PUBLIC COMMENTARY ONLY, pit_feasible=False, no venue named or crawled "
                 "(universe mandate 2026-08-18)."),
)


# --------------------------------------------------------------------------- transmission
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    edge("ng_force_majeure_to_brent",
         source="Nigerian force majeure declarations and terminal outages at the export "
                "terminals",
         mechanism="a declared outage removes a dated, discrete quantity of light sweet crude "
                   "from the seaborne market; the grade matters because light sweet barrels are "
                   "not interchangeable with the medium sour barrels that dominate spare "
                   "capacity",
         targets=("XBRUSD", "XTIUSD"),
         sign="force majeure declared -> XBRUSD UP in the following sessions",
         lag="the declaration timestamp",
         horizon="one to twenty sessions",
         control="matched non-event sessions; disruptions in other light sweet producers, which "
                 "share the grade mechanism and not the Nigerian security situation; and "
                 "randomised declaration dates",
         evidence="HYPOTHESIS",
         notes="THE EDGE IS ABOUT EVENTS, NOT VOLUME. Nigeria is a small share of global supply "
               "and the pack explicitly refuses to claim a steady-state production signal."),
    edge("ng_fx_seizure_to_frontier_stress",
         source="NFEM turnover collapse and deal-count collapse joined to a widening "
                "official-versus-parallel spread",
         mechanism="a market that has stopped clearing in the largest economy in West Africa is "
                   "information about frontier risk appetite generally, and it arrives days "
                   "before the rating and eurobond channels reprice",
         targets=("USDZAR", "USDTRY", "USDBRL"),
         sign="TURNOVER_COLLAPSE with a widening wedge -> frontier carriers WEAKEN against the "
              "dollar over the following sessions",
         lag="the daily NFEM publication, after the Lagos close",
         horizon="one to ten sessions",
         control="THE GLOBAL EM FACTOR MUST BE REMOVED FIRST -- matched EM stress episodes with "
                 "no Nigerian component are the primary control; plus randomised collapse flags "
                 "and days with equal wedge and normal turnover",
         evidence="HYPOTHESIS",
         notes="THE PACK'S FLAGSHIP EDGE. It is also the one most likely to be a global factor "
               "in disguise, which is why the control is stated first."),
    edge("ng_reserve_drawdown_to_sovereign_stress",
         source="the reserve path, import cover and eurobond maturity calendar",
         mechanism="falling reserves against a known maturity wall raises the market's price of "
                   "Nigerian sovereign credit, which transmits to the frontier credit complex "
                   "and to the global duration leg the desk can actually hold",
         targets=("UST10Y", "UKGILT", "USDZAR"),
         sign="accelerating drawdown into a maturity -> frontier credit stress -> flight into "
              "the global duration leg",
         lag="the reserve series is published near-daily with a filter; the maturity dates are "
             "known years in advance",
         horizon="ten to sixty sessions",
         control="other frontier sovereigns with equal reserve paths and no maturity wall; "
                 "matched windows with the same global rate cycle; randomised maturity dates",
         evidence="HYPOTHESIS",
         notes="Remember the published reserve series is a THIRTY-DAY MOVING AVERAGE: any "
               "differencing is differencing a filter."),
    edge("ng_faac_to_premium",
         source="the announced monthly FAAC allocation total",
         mechanism="a large scheduled naira liquidity injection is converted into dollar demand "
                   "by recipients and their contractors, pressing the parallel market in the "
                   "days that follow",
         targets=("USDZAR", "XBRUSD"),
         sign="a large allocation -> naira liquidity UP -> parallel premium WIDENS within a week",
         lag="three to seven business days after the announcement",
         horizon="five to fifteen sessions",
         control="the same calendar window in months with no announcement; randomised "
                 "announcement dates inside the window; and month-end importer demand, which "
                 "overlaps the window and must be separated",
         evidence="HYPOTHESIS",
         notes="The premium leg is public commentary at weekly resolution; the allocation leg "
               "is an official number. The edge is only as strong as its weaker leg."),
    edge("ng_devaluation_to_em_peers",
         source="Nigerian devaluation and unification events",
         mechanism="a large frontier devaluation updates the market's prior about the "
                   "sustainability of every similar managed float, so the peers reprice even "
                   "with no news of their own",
         targets=("USDTRY", "USDBRL", "USDZAR"),
         sign="a Nigerian devaluation -> EM devaluation-regime peers WEAKEN in the following "
              "sessions",
         lag="the announcement timestamp",
         horizon="one to ten sessions",
         control="matched non-event sessions; devaluations in economies with no managed-float "
                 "peer group; and the global dollar factor, removed first",
         evidence="HYPOTHESIS",
         notes="n is small: there have been a handful of these events. The edge exists to be "
               "SIZED honestly and can never clear a gauntlet on a single episode."),
    edge("ng_nop_circular_to_fx_turnover",
         source="CBN net open position circulars and their stated deadlines",
         mechanism="a tightening forces Nigerian banks to sell dollars by a published date, "
                   "which is a dated forced flow into a thin market",
         targets=("USDZAR", "USDTRY"),
         sign="a tightening circular -> NFEM turnover UP and the rate FIRMS into the deadline",
         lag="the circular's publication, with the deadline days to weeks later",
         horizon="one to twenty sessions",
         control="matched windows with no circular; circulars that loosened rather than "
                 "tightened, which should show the opposite sign; randomised deadlines",
         evidence="HYPOTHESIS",
         notes="Direction, trigger and timing are all in one public document, which is rare."),
    edge("ng_refining_shift_to_crude_flow",
         source="the Dangote refinery ramp, crude intake and Nigerian refined-product import "
                "volumes",
         mechanism="domestic refining converts Nigeria from a crude exporter and product "
                   "importer into a crude consumer and product exporter, changing both the "
                   "direction of the flow and the currency composition of the trade balance",
         targets=("XBRUSD", "XTIUSD", "XNGUSD"),
         sign="ramp progressing -> Nigerian product imports DOWN and domestic crude intake UP; "
              "the Atlantic basin light sweet balance tightens at the margin",
         lag="trade statistics arrive with a seventy-five-day lag, which is the binding "
             "constraint on measuring this at all",
         horizon="one to four quarters",
         control="the pre-ramp import trend; other West African product importers with no "
                 "domestic refinery; randomised ramp dates",
         evidence="HYPOTHESIS",
         notes="The most consequential structural change in West African energy in a generation "
               "and the slowest to measure. The pack states the lag rather than pretending to a "
               "faster read."),
    edge("ng_subsidy_removal_to_passthrough",
         source="the 2023-05-29 fuel subsidy removal and subsequent pump prices",
         mechanism="with the subsidy gone, crude and exchange-rate moves reach the domestic "
                   "price level directly instead of being absorbed fiscally, so the same Brent "
                   "move has a larger inflation consequence and therefore a larger policy "
                   "consequence",
         targets=("XBRUSD", "USDZAR", "UST05Y"),
         sign="post-removal, a Brent rise -> Nigerian inflation UP -> tighter policy -> "
              "frontier stress",
         lag="pump prices move within weeks; CPI is published with a fifteen-day lag",
         horizon="one to two quarters",
         control="THE PRE-2023-05-29 SAMPLE IS THE CONTROL and the comparison is the test; plus "
                 "the CFA neighbour with a pegged currency and different subsidy policy",
         evidence="HYPOTHESIS",
         notes="One announced date, one clean regime break. Also note the CPI rebasing is a "
               "SECOND break in the same series and the two must not be confused."),
    edge("ng_opec_quota_inversion",
         source="Nigerian OPEC quota changes and the compliance table",
         mechanism="for most members a quota is a ceiling; for Nigeria it has frequently been a "
                   "target it could not reach, so a quota increase is an announcement rather "
                   "than a barrel",
         targets=("XBRUSD", "XTIUSD"),
         sign="a Nigerian quota increase -> NO measurable XBRUSD response once the aggregate "
              "OPEC decision is controlled for",
         lag="the decision timestamp",
         horizon="one to ten sessions",
         control="the aggregate OPEC decision, removed first; members whose quota does bind; "
                 "randomised quota dates",
         evidence="HYPOTHESIS",
         notes="A DELIBERATELY NULL-SHAPED EDGE. If it fails -- if the Nigerian quota does move "
               "Brent independently -- the pack has learned something specific, which is what a "
               "falsifier is for."),
    edge("ng_china_import_share_to_trade_cycle",
         source="Nigerian trade statistics by partner, joined to the Chinese demand state",
         mechanism="China is the largest single source of Nigerian imports and a growing "
                   "counterparty for its crude, so the Nigerian import bill carries information "
                   "about Chinese export volumes and the Chinese demand state conditions "
                   "Nigerian crude offtake",
         targets=("USDCNH", "XBRUSD", "USDZAR"),
         sign="Chinese demand state HIGH -> Nigerian crude offtake UP and import bill UP",
         lag="quarterly trade data with a seventy-five-day lag",
         horizon="one to three quarters",
         control="other West African crude exporters' China share; matched quarters with equal "
                 "global demand; randomised state assignment",
         evidence="HYPOTHESIS",
         notes="The leg this pack contributes to the China-Africa family in "
               "desks/mt5/research/africa_interaction.py."),
    edge("ng_holiday_observability_gap",
         source="the Nigerian statutory holiday table and the moon-dependent Islamic days",
         mechanism="a Nigerian closure stops the DATA rather than the price: no NFEM print, no "
                   "CBN update, no turnover. The carriers trade through with no Nigerian "
                   "information arriving, so the reopening print is the first observation in "
                   "several days and is a different object from an ordinary daily print",
         targets=("USDZAR", "XBRUSD"),
         sign="the post-closure reopening NFEM print shows an elevated absolute change relative "
              "to matched ordinary prints",
         lag="the closure itself; the effect is in the next published print",
         horizon="one to three sessions",
         control="matched non-holiday prints; closures of different lengths, since a two-day "
                 "Eid and a one-day national holiday accumulate different amounts of "
                 "information; and randomised closure dates",
         evidence="HYPOTHESIS",
         notes="A MISSING NFEM DAY IS UNMEASURED, NEVER A ZERO. This edge exists partly to make "
               "that rule operational rather than decorative."),
    edge("ng_cfa_neighbour_control",
         source="the CFA franc zone next door -- same region, same commodities, same weather, a "
                "euro peg instead of a managed float",
         mechanism="not a transmission so much as THE CONTROL EDGE: whatever a Nigerian FX "
                   "mechanism claims, the CFA zone provides a regional counterfactual in which "
                   "the monetary regime is the only thing that differs",
         targets=("EURUSD", "UKCOCOA", "USDZAR"),
         sign="a shock common to the region should move both; a shock specific to the Nigerian "
              "regime should move only the Nigerian observables",
         lag="contemporaneous",
         horizon="five to sixty sessions",
         control="the shock itself is the control; the test is the DIFFERENCE in response",
         evidence="HYPOTHESIS",
         notes="THE CLEANEST NATURAL EXPERIMENT IN WEST AFRICA, and the reason the GH/CFA pack "
               "exists alongside this one."),
)

#: Derived, never hand-maintained. With OWN_PRICE empty, EVERY target is a transmission target --
#: which is the arithmetic statement of this pack being transmission-only.
TRANSMISSION_TARGETS: tuple[str, ...] = tuple(sorted(
    {t for e in TRANSMISSION_EDGES_SEED for t in e["targets"]} - set(OWN_PRICE)))


# --------------------------------------------------------------------------- eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    era("ng_multiple_windows", start="2017-04-01", end="2023-06-13",
        label="The multiple-window regime: official, I&E/NAFEX and parallel",
        what_changed="an official or CBN rate, an Investors' and Exporters' window rate and a "
                     "parallel street rate coexisted, at times tens of per cent apart",
        invalidates="EVERY naira series in this window has three possible values and most "
                    "vendors publish one without saying which. Any study that does not name the "
                    "window it used is not reproducible, and any study that splices across the "
                    "end of this era is splicing two currencies."),
    era("ng_subsidy_removal", start="2023-05-29", end=None,
        label="Fuel subsidy removal",
        what_changed="the domestic pump price was freed, so crude and exchange-rate moves reach "
                     "Nigerian inflation directly instead of being absorbed fiscally",
        invalidates="pass-through estimates from crude or FX into Nigerian inflation pooled "
                    "across this date are averaging a regime where the shock was absorbed and "
                    "one where it is transmitted"),
    era("ng_unification_2023", start="2023-06-14", end="2024-11-30",
        label="Unification: the windows collapse and the official rate meets the market",
        what_changed="the official rate moved sharply to meet the parallel market; the "
                     "published benchmark became NAFEM; the forwards backlog began to be "
                     "addressed",
        invalidates="volatility, drift and carry estimates from the window era do not transfer; "
                    "the currency's data-generating process changed on a single announced date"),
    era("ng_efems_nfem", start="2024-12-02", end=None,
        label="EFEMS and the NFEM benchmark",
        what_changed="an electronic matching system was introduced and the published benchmark "
                     "became the NFEM rate, with a daily range, turnover and deal count "
                     "alongside it",
        invalidates="microstructure estimates from the pre-matching market do not transfer -- "
                    "the price formation mechanism itself changed. It also STARTS the turnover "
                    "and deal-count series this pack's flagship domain depends on, so that "
                    "domain simply has no history before this date."),
    era("ng_dangote_ramp", start="2024-01-01", end=None,
        label="The domestic refining transition",
        what_changed="Nigeria began refining at scale domestically for the first time, flipping "
                     "the direction of its crude and product trade",
        invalidates="trade-composition and FX-demand-profile studies pooled across the ramp are "
                    "fitting one structure to two different economies; the ramp is gradual, so "
                    "the boundary is a PERIOD rather than a date and is treated as such"),
    era("ng_cpi_rebasing", start="2025-01-01", end=None,
        label="The CPI basket rebasing",
        what_changed="the consumer price index was rebased onto a new basket and weights",
        invalidates="THIS IS A SERIES BREAK AND NOT A REVISION. A pre- and post-rebasing splice "
                    "measures two different indices; any inflation surprise computed across the "
                    "boundary is measuring the rebasing"),
    era("ng_forwards_backlog", start="2020-04-01", end="2024-03-31",
        label="The unsettled FX forwards backlog",
        what_changed="the CBN accumulated and then cleared a backlog of unsettled forward "
                     "obligations to banks and corporates, announced in tranches",
        invalidates="any study of Nigerian FX availability in this window is measuring a QUEUE "
                    "rather than a price, and the queue's length is the state variable the "
                    "price alone cannot show"),
)


# --------------------------------------------------------------------------- the pack
def spec() -> dict[str, Any]:
    """THIS PACK AS PLAIN DATA -- the twenty-one fields exactly as this department declares them.

    THE SOURCE OF TRUTH, and the thing the tests validate. The country lab's frozen `CountryPack`
    has row classes with their own field names and DROPS any row it cannot construct -- correct
    behaviour for the framework, but it makes the typed object a LOSSY VIEW of a pack written in
    this package's richer vocabulary. The plain data is therefore kept, `pack()` adapts it
    explicitly, and nothing is silently thinner than what was written here.
    """
    return {
        "code": CODE,
        "name": NAME,
        "region_command": REGION_COMMAND,
        "currency": CURRENCY,
        "executable_instruments": EXECUTABLE_INSTRUMENTS,
        "central_bank": CENTRAL_BANK,
        "fixing_conventions": FIXING_CONVENTIONS,
        "settlement_conventions": SETTLEMENT_CONVENTIONS,
        "exchanges": EXCHANGES,
        "holidays_rule": HOLIDAYS_RULE,
        "fiscal_year_end": FISCAL_YEAR_END,
        "positioning_sources": POSITIONING_SOURCES,
        "native_languages": NATIVE_LANGUAGES,
        "terminology": TERMINOLOGY,
        "source_classes": SOURCE_CLASSES,
        "datasets": DATASETS,
        "actors": ACTORS,
        "domains": DOMAINS,
        "custom_miners": CUSTOM_MINERS,
        "transmission_edges_seed": TRANSMISSION_EDGES_SEED,
        "policy_eras": POLICY_ERAS,
    }


def framework_rows() -> dict[str, Any]:
    """The fields whose vocabulary differs from the country lab's, translated into its shape.

    ONE EDGE BECOMES SEVERAL SEEDS because a `TransmissionSeed` is keyed on `(to_country, asset)`
    and an edge here names several targets. Everything the typed row has no field for is kept in
    `notes` rather than dropped. Open-ended eras take a sentinel end date because the framework's
    `Era` requires one -- THE SENTINEL IS A FRAMEWORK REQUIREMENT AND NEVER A CLAIM about when
    the era ends. `cot_currency` is deliberately EMPTY: there is no CFTC naira contract, and an
    invented ticker there would make the positioning miner report a number instead of UNMEASURED.
    """
    seeds: list[dict[str, Any]] = []
    for e in TRANSMISSION_EDGES_SEED:
        detail = (f"SIGN: {e['sign']} | HORIZON: {e['horizon']} | LAG: {e['lag']} | "
                  f"CONTROL: {e['control']} | EVIDENCE: {e['evidence']}")
        if e.get("notes"):
            detail += f" | NOTE: {e['notes']}"
        for target in e["targets"]:
            seeds.append({"to_country": CODE, "asset": target, "actor": e["id"],
                          "constraint": e["mechanism"], "flow": e["source"],
                          "source_series": e["source"], "notes": detail})
    eras = tuple({"name": r["id"], "start": r["start"], "end": r["end"] or "2099-12-31",
                  "notes": f"{r['label']} | CHANGED: {r['what_changed']} | "
                           f"INVALIDATES: {r['invalidates']}"
                           + ("" if r["end"] else " | OPEN ERA: the end date is a framework "
                                                  "sentinel, not a claim")}
                 for r in POLICY_ERAS)
    carriers = EXECUTABLE_INSTRUMENTS[:4]
    fixings = tuple({"name": str(v.get("name") or k), "time_utc": "", "dst_rule": "none",
                     "instruments": carriers,
                     "notes": "; ".join(f"{kk}={vv}" for kk, vv in v.items() if kk != "name")}
                    for k, v in FIXING_CONVENTIONS.items() if isinstance(v, dict))
    settle = tuple({"name": k, "kind": "month_end", "instruments": carriers, "notes": str(v)}
                   for k, v in SETTLEMENT_CONVENTIONS.items())
    venues = tuple({"name": str(v.get("name") or k), "index_symbols": (),
                    "expiry_rule": str(v.get("expiry_rule") or ""),
                    "open_utc": "", "close_utc": "",
                    "notes": "; ".join(f"{kk}={vv}" for kk, vv in v.items() if kk != "name")}
                   for k, v in EXCHANGES.items() if isinstance(v, dict))
    every_day = tuple(sorted(d for tbl in _NG_HOLIDAYS.values() for d in tbl))
    return {"transmission_edges_seed": tuple(seeds), "policy_eras": eras,
            "fixing_conventions": fixings, "settlement_conventions": settle,
            "exchanges": venues,
            "holidays_rule": {"dates": every_day, "notes": str(HOLIDAYS_RULE["rule"])},
            "fiscal_year_end": "12-31",
            "export_economy": "energy_exporter",
            "retail_leverage_regime": "restricted",
            "cot_currency": "",
            "positioning_sources": tuple(str(p["id"]) for p in POSITIONING_SOURCES),
            "source_classes": tuple(str(s["id"]) for s in SOURCE_CLASSES),
            "custom_miners": tuple(str(m["entry"]) for m in CUSTOM_MINERS),
            "miner_domains": {str(m["name"]): tuple(m["domain_ids"]) for m in CUSTOM_MINERS},
            "mission": "mine Nigeria to exhaustion as an exogenous frontier-FX-stress and crude "
                       "disruption sensor for the EM carriers and energy instruments the desk "
                       "already trades; the naira itself is untradable here and every finding "
                       "must land on a carrier or it is not a finding"}


def pack() -> Any:
    """The Nigeria country pack. `CountryPack` when the framework has landed, else a dict."""
    return build_pack(**{**spec(), **framework_rows()})


def priority_weight() -> float:
    """This pack's share of the opening African compute ladder. A PRIOR, replaced by survivors."""
    return PRIORITY_WEIGHT


def instrument_report(path: Any = None) -> dict[str, Any]:
    """What this pack can trade, what carries its economics and what is missing, MEASURED against
    the broker registry. `own_price` is empty and that is the measurement, not an oversight."""
    split = resolve(EXECUTABLE_INSTRUMENTS, path)
    return {"code": CODE, "own_price": OWN_PRICE, "executable": tuple(split["tradable"]),
            "equities_refused": tuple(split["equities"]),
            "absent_from_universe": tuple(split["absent"]),
            "transmission_targets": TRANSMISSION_TARGETS,
            "named_absent_instruments": ABSENT_INSTRUMENTS,
            "priority_weight": PRIORITY_WEIGHT,
            "transmission_only": not OWN_PRICE,
            "dataset_fields": DATASET_FIELDS}
