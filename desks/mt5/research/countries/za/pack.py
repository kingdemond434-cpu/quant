"""THE SOUTH AFRICA COUNTRY PACK -- the rand, the reef and the grid, held as data.

WHY SOUTH AFRICA IS TIER 1 AND NOT "THE AFRICAN ONE". Three facts, none of them about Africa:

  * IT IS THE PGM MARKET. South Africa mines the large majority of the world's platinum and
    rhodium and most of its palladium, and Stats SA publishes the PHYSICAL PRODUCTION of every
    mineral group monthly (P2041, mining production and sales). XPTUSD and XPDUSD are on this
    broker. So the supply side of two executable metals is published on a schedule, by a
    statistics agency, for free -- which is an exogenous sensor for an instrument the desk
    already trades, not a South African trade.
  * IT PUBLISHES ITS OWN SUPPLY CONSTRAINT, HOURLY. Eskom's data portal publishes system load,
    available capacity and unplanned outages (UCLF) at hourly granularity, and the load-shedding
    STAGE is the most-watched number in the country. A smelter is an electricity price with a
    furnace attached: when the grid sheds, PGM and ferrochrome output falls with a lag that is
    weeks, not quarters, and the rand reprices in minutes. That is one observable with two
    horizons, and both are testable here.
  * THE RAND IS THE WORLD'S EM RISK PROXY WITH AN AFRICAN CASH LEG. USDZAR is one of the most
    liquid EM crosses, trades 24 hours offshore, and is quoted here four ways. It is used as a
    hedge for exposures that have nothing to do with South Africa, which means USDZAR carries
    GLOBAL risk information -- and separating the global beta from the domestic sensor is the
    central econometric problem of this pack, not a footnote to it.

WHAT THIS PACK MAY NOT DO. No single-name equity is ever a hypothesis (two-lane order,
2026-09-06). The JSE-listed miners are the loudest South African story and they enter here as
INDEX, METAL and FX transmission only: production volumes are observables, the companies are in
terminology so a local-language miner recognises the words, and no ticker is ever on a docket.
No crypto-exchange ground is hunted (universe mandate, 2026-08-18); the rand's retail crypto
premium is a real risk-appetite observable and is carried as PUBLIC COMMENTARY with
`pit_feasible=False`, its executable leg being the broker's own BTCUSD CFD.

WHAT IS EXECUTABLE AND WHAT ONLY TRANSMITS. USDZAR, EURZAR, GBPZAR and ZARJPY are the country's
own price. XAUUSD, XAGUSD, XPTUSD, XPDUSD, XCUUSD, XTIUSD, XBRUSD, UK100, US500, AUDUSD and USDX
are the carriers its economics land in. The JSE Top 40, the R2030 bond, API4 coal and iron ore
are NOT on this broker and are named in `ABSENT_INSTRUMENTS` with what carries them instead --
a silently dropped instrument becomes a silently dropped mechanism.
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

CODE = "za"
NAME = "South Africa"
REGION_COMMAND = "AFRICA"
CURRENCY = "ZAR"
NATIVE_LANGUAGES = ("en", "af", "zu")

#: COMPUTE PRIORITY. The principal's order of 2026-09-17 sets the opening ladder
#: ZA > NG > EG > KE > GH/CFA, and the source-ROI layer reallocates it afterwards BY MEASURED
#: SURVIVORS. This number is therefore a PRIOR, not a verdict: it says where the first hour goes
#: before any African ground has produced a survivor, and it is expected to be overwritten by
#: measurement rather than defended.
PRIORITY_WEIGHT: float = 1.00

#: South Africa's own price on this broker -- four of them, which no other African pack has.
OWN_PRICE: tuple[str, ...] = ("USDZAR", "EURZAR", "GBPZAR", "ZARJPY")

#: What the ZA department may place an order in: its own currency plus every carrier its
#: transmission seeds terminate in. Each is in the broker registry and none is a single name.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "USDZAR", "EURZAR", "GBPZAR", "ZARJPY", "XAUUSD", "XAGUSD", "XPTUSD", "XPDUSD", "XCUUSD",
    "XALUSD", "XTIUSD", "XBRUSD", "UK100", "US500", "AUDUSD", "USDX", "BTCUSD")

#: The instruments a Johannesburg desk reaches for that THIS broker does not quote. Named with
#: what carries them, because an instrument dropped in silence takes a mechanism with it.
ABSENT_INSTRUMENTS: tuple[dict[str, str], ...] = (
    {"instrument": "FTSE/JSE Top 40 (ALSI) index or its future",
     "why": "no South African equity index CFD in desks/mt5/data/universe/universe.json",
     "carried_by": "UK100 for the London-listed mining majors that dominate the Top 40's "
                   "resources block, and USDZAR for the rand leg of the same flow"},
    {"instrument": "South African government bond (R2030, R186) or the ALBI",
     "why": "absent; the broker quotes UKGILT, UST05Y and UST10Y and no EM curve",
     "carried_by": "UST10Y as the global duration leg, with the South Africa-specific term "
                   "premium and the fiscal risk premium left UNMEASURED BY NAME"},
    {"instrument": "API4 Richards Bay coal, iron ore 62% Fe, ferrochrome, manganese",
     "why": "absent; no bulk-commodity contract is quoted on this account",
     "carried_by": "XALUSD and XCUUSD as the industrial-metals complex, AUDUSD as the "
                   "bulk-exporter currency beta, and the PGM pair XPTUSD/XPDUSD where the "
                   "mechanism is a shared South African electricity constraint"},
    {"instrument": "ZAR/CNH, the direct rand-renminbi cross",
     "why": "absent; the broker quotes USDZAR and USDCNH separately",
     "carried_by": "a synthetic USDCNH / USDZAR ratio, which carries two spreads and is stated "
                   "as a cost rather than assumed away"},
    {"instrument": "JSE-listed miners as single names",
     "why": "REFUSED, not absent. Several are quotable elsewhere; the two-lane order "
            "(2026-09-06) forbids hunting any single name for a statistical hypothesis",
     "carried_by": "the metal itself (XPTUSD, XPDUSD, XAUUSD) and UK100"},
)


# --------------------------------------------------------------------------- central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "South African Reserve Bank (SARB)",
    "native_name": "Suid-Afrikaanse Reserwebank (af); iBhange loMbuso laseNingizimu Afrika (zu)",
    "framework": "inflation_targeter",
    "committee": "Monetary Policy Committee (MPC); votes are DISCLOSED as a count, which is a "
                 "harder observable than most EM central banks give",
    "policy_rate": "the repurchase (repo) rate; the prime lending rate is the repo + 3.50%",
    "target": "3-6% CPI band since 2000. THE BAND IS THE MECHANISM: the SARB has publicly "
              "preferred the 4.5% midpoint since 2017 and has been arguing for a LOWER point "
              "target (3%) since 2023 -- so a reaction function fitted on the band's midpoint "
              "and one fitted on its ceiling are two different models of the same bank.",
    "meetings_per_year": 6,
    "schedule_rule": (
        "The MPC met eight times a year until 2016 and SIX times a year since. Dates for year N "
        "are published during year N-1 on resbank.co.za. The Governor delivers the statement "
        "from about 15:00 SAST -- 13:00 UTC year-round, because South Africa observes NO "
        "daylight saving and SAST is UTC+2 always. The statement runs 20-40 minutes and the "
        "vote split is given at the end, so the DECISION and the VOTE are two events inside one "
        "broadcast and a one-minute bar study must treat them as two."),
    "timezone": "SAST = UTC+2 all year, no DST. The broker's server moves (UTC+2 winter, UTC+3 "
                "summer) and Johannesburg does not, so every SAST->broker-hour mapping must be "
                "recomputed per season even though the local times never change.",
    "fx_operations": (
        "The SARB DOES NOT TARGET THE RAND and says so in every statement. It buys foreign "
        "exchange opportunistically to build reserves and it has not conducted defensive "
        "intervention in the modern float. THIS IS THE PACK'S MOST IMPORTANT NEGATIVE FACT: "
        "USDZAR has no intervention reaction function to model, which is exactly why it is used "
        "as a global EM hedge and why its beta to global risk is so high. Nigeria and Egypt are "
        "the opposite case and the contrast is the research design."),
    "gold_and_forex_reserves": (
        "Gross gold and foreign exchange reserves are published MONTHLY, around the 7th, with "
        "the gold tranche valued at market. The Gold and Foreign Exchange Contingency Reserve "
        "Account (GFECRA) was partially distributed to the National Treasury from 2024 -- a "
        "fiscal event driven by the GOLD PRICE and the rand, which is a direct XAUUSD linkage "
        "with a South African fiscal transmission and is seeded below."),
    "publication_classes": ("MPC statement", "Monetary Policy Review", "Quarterly Bulletin",
                            "Financial Stability Review", "monthly reserves release",
                            "daily and historical exchange rates via the SARB Web API"),
    "decision_dates": {
        2024: ("2024-01-25", "2024-03-27", "2024-05-30", "2024-07-18", "2024-09-19",
               "2024-11-21"),
        2025: ("2025-01-30", "2025-03-20", "2025-05-29", "2025-07-31", "2025-09-18",
               "2025-11-20"),
        2026: ("2026-01-29", "2026-03-19", "2026-05-21", "2026-07-23", "2026-09-17",
               "2026-11-19"),
    },
    "decision_dates_status": {
        2024: "PUBLIC_RECORD",
        2025: "PUBLIC_RECORD",
        2026: "RULE_DERIVED_UNVERIFIED -- six meetings, the historical late-January / mid-March "
              "/ late-May / late-July / mid-September / late-November spacing, Thursday "
              "announcements. THE DATA PLANE MUST REPLACE THESE WITH THE PUBLISHED CALENDAR "
              "BEFORE ANY 2026 EVENT STUDY IS SCORED; an event study anchored on a guessed date "
              "measures the wrong session and reports it confidently.",
    },
    "decision_time_utc": "13:00",
    "notes": "The SARB's own Web API (custom.resbank.co.za/SarbWebApi) serves the repo rate, the "
             "daily rand rates and the macro indicator set, so this pack's policy leg is "
             "machine-readable without a licence -- which is rare for an EM central bank and is "
             "why the ZA data plane exists first.",
}


# --------------------------------------------------------------------------- fixings
FIXING_CONVENTIONS: dict[str, Any] = {
    "sarb_daily_rates": {
        "name": "SARB daily exchange rates (the published mid-rates)",
        "publisher": "South African Reserve Bank",
        "definition": "indicative rand mid-rates against the major currencies, published each "
                      "business day for accounting and official use",
        "published_local": "late afternoon SAST, after the local interbank session",
        "published_utc": "approximately 14:00-16:00 UTC; the EXACT stamp is what the data plane "
                         "records per vintage, because the pack refuses to assert a minute it "
                         "has not read from the payload",
        "note": "It is a REFERENCE, not a tradable fix. Treating it as a contemporaneous "
                "transaction price is the single most common error in rand research.",
    },
    "zaronia": {
        "name": "ZARONIA -- the South African Rand Overnight Index Average",
        "publisher": "SARB",
        "definition": "volume-weighted trimmed mean of overnight unsecured deposit transactions",
        "published_local": "10:00 SAST on the business day FOLLOWING the transaction day",
        "published_utc": "08:00",
        "why_it_matters": "ZARONIA is replacing JIBAR as the reference rate. THE TRANSITION IS A "
                          "REGIME BOUNDARY: a funding or carry study that pools JIBAR-referenced "
                          "history with ZARONIA-referenced history is pooling two different "
                          "definitions of the same quantity.",
    },
    "jibar": {
        "name": "JIBAR -- Johannesburg Interbank Average Rate (3-month is the benchmark)",
        "publisher": "JSE, on behalf of the market",
        "published_local": "about 11:00 SAST",
        "published_utc": "09:00",
        "status": "BEING RETIRED in favour of ZARONIA; the cessation date is set by the Market "
                  "Practitioners Group and is a declared, dated regime break for this pack",
    },
    "wmr_london_fix": {
        "name": "WM/Refinitiv 16:00 London fix",
        "time_utc": "15:00 in British Summer Time, 16:00 in GMT",
        "why_it_matters": "index rebalances and benchmark-tracking flows in ZAR-denominated "
                          "assets execute at this fix, not at the Johannesburg close. The "
                          "largest non-event USDZAR volume spikes of the month cluster in the "
                          "five minutes around it on month-end and index-rebalance days.",
        "dst_rule": "moves with LONDON, not with Johannesburg -- so the fix's UTC time changes "
                    "twice a year while SAST never does, and a fixed-UTC window loses it for "
                    "half the year",
    },
    "jse_closing_auction": {
        "name": "JSE closing auction",
        "time_local": "16:50-17:00 SAST (a random-stop auction)",
        "time_utc": "14:50-15:00",
        "why_it_matters": "the cash equity close, and therefore the moment foreign portfolio "
                          "flow crystallises into a settlement obligation that becomes an FX "
                          "order one to three days later. The FLOW LEADS ITS OWN FX.",
    },
    "dst": "NONE in South Africa. SAST is UTC+2 year-round. London's fix and New York's close "
           "both move against it twice a year, and any ZA session study that hard-codes a UTC "
           "offset for a LONDON-anchored event is wrong for half the sample.",
}


# --------------------------------------------------------------------------- settlement
SETTLEMENT_CONVENTIONS: dict[str, Any] = {
    "spot": "T+2 for USDZAR, settled through the South African Multiple Option Settlement "
            "(SAMOS) system for the rand leg",
    "deliverability": "THE RAND IS FULLY DELIVERABLE OFFSHORE and trades 24 hours. This is the "
                      "structural difference from every other African currency in this "
                      "civilization: there is no NDF basis to mine, no parallel rate, and no "
                      "capital-control wedge. What South Africa offers instead is a clean, "
                      "liquid, globally traded price with real physical-production data behind "
                      "it -- the opposite research design from Nigeria and Egypt.",
    "equity_settlement": "T+3 at the JSE through Strate. A foreign net-buy print on day T "
                         "becomes an FX conversion on T+3, so the JSE's daily foreign-flow table "
                         "LEADS its own rand flow by three business days -- a testable lag, not "
                         "a contemporaneous correlation.",
    "bond_settlement": "T+3 for South African government bonds through Strate",
    "month_end": "Importer and corporate demand concentrates in the last two to three business "
                 "days of the month; index-tracking rebalances execute at the LONDON 16:00 fix "
                 "on the final business day. Both windows are in the tape and neither is an "
                 "event the pack has to source externally.",
    "quarter_end": "Adds the FTSE/JSE quarterly index review (effective after the third Friday "
                   "of March, June, September and December) and the offshore-allocation "
                   "rebalancing of the large ZA pension funds, whose 45% offshore limit "
                   "(Regulation 28, raised from 30% in February 2022) makes their rebalancing a "
                   "STRUCTURAL rand-selling flow with a published rule behind it.",
    "fiscal_events": "The Budget (late February) and the Medium Term Budget Policy Statement "
                     "(late October / early November) are the two largest scheduled domestic "
                     "risk events of the South African year, both delivered in the early "
                     "afternoon SAST while London is open.",
}


# --------------------------------------------------------------------------- exchanges
EXCHANGES: dict[str, Any] = {
    "cash": {
        "name": "Johannesburg Stock Exchange (JSE)",
        "hours_local": "09:00-17:00 SAST",
        "hours_utc": "07:00-15:00",
        "opening_auction": "08:30-09:00 SAST (06:30-07:00 UTC)",
        "closing_auction": "16:50-17:00 SAST (14:50-15:00 UTC), random stop",
        "index_symbols": (),
        "index_symbols_note": "the FTSE/JSE Top 40 is NOT quoted on this account; it is named in "
                              "ABSENT_INSTRUMENTS and carried by UK100 and USDZAR rather than "
                              "silently dropped",
        "public_data": "JSE publishes daily market statistics and equity/bond FOREIGN PORTFOLIO "
                       "FLOW (non-resident net purchases and sales) free of charge -- one of the "
                       "few daily, free, official foreign-flow series in any emerging market",
    },
    "derivatives": {
        "name": "JSE Derivatives Market (equity, currency, commodity and interest-rate)",
        "expiry_rule": "the THIRD THURSDAY of March, June, September and December for the "
                       "quarterly equity index (ALSI/Top 40) futures close-out. Not the third "
                       "Friday (US), not the second Thursday (Korea).",
        "settlement_price": "struck from an auction in the early afternoon of close-out day; the "
                            "exact window is set by JSE notice and is DECLARED, NOT RE-DERIVED "
                            "here -- a guessed auction window makes an expiry study measure the "
                            "wrong minutes",
        "currency_futures": "the JSE lists rand futures and options against USD, EUR, GBP and "
                            "others, and publishes their open interest -- South Africa's nearest "
                            "equivalent to a domestic positioning report",
        "commodity_futures": "SAFEX grain (white and yellow maize, wheat, soybeans, sunflower) "
                             "settles against a rand-denominated import/export parity, so THE "
                             "RAND IS INSIDE THE LOCAL GRAIN PRICE. A maize move that is really "
                             "a currency move is the standard confound of South African "
                             "agricultural research and is controlled for explicitly here.",
    },
    "note": "The JSE is the deepest exchange in Africa by a wide margin and the only one in this "
            "civilization whose public data can support a daily flow study without a licence.",
}


FISCAL_YEAR_END: dict[str, str] = {
    "government": "31 March. The Budget is tabled in late February for the year beginning 1 "
                  "April, and the MTBPS revises it in late October or early November.",
    "corporate": "mixed; a June or December year-end is common and there is NO single dominant "
                 "corporate year-end, so South Africa has no Japan-style fiscal-repatriation "
                 "seasonal and a study that assumes one is importing another country's calendar",
    "sarb": "the SARB's own financial year ends 31 March",
    "tax": "the personal tax year ends on the last day of February, which concentrates "
           "retirement-annuity contributions and therefore institutional buying into late "
           "February -- a domestic flow with a statutory date",
}


# --------------------------------------------------------------------------- holidays
#: The Public Holidays Act 36 of 1994 with the Sunday substitution rule applied. Saturdays are
#: NOT substituted, which is why 2024-04-27 and 2026-03-21 are simply lost days.
_ZA_HOLIDAYS: dict[int, dict[str, str]] = {
    2024: {
        "2024-01-01": "New Year's Day",
        "2024-03-21": "Human Rights Day",
        "2024-03-29": "Good Friday",
        "2024-04-01": "Family Day (Easter Monday)",
        "2024-04-27": "Freedom Day (falls on a Saturday; NOT substituted)",
        "2024-05-01": "Workers' Day",
        "2024-05-29": "National and provincial election day (declared public holiday)",
        "2024-06-17": "Youth Day observed (16 June fell on a Sunday)",
        "2024-08-09": "National Women's Day",
        "2024-09-24": "Heritage Day",
        "2024-12-16": "Day of Reconciliation",
        "2024-12-25": "Christmas Day",
        "2024-12-26": "Day of Goodwill",
    },
    2025: {
        "2025-01-01": "New Year's Day",
        "2025-03-21": "Human Rights Day",
        "2025-04-18": "Good Friday",
        "2025-04-21": "Family Day (Easter Monday)",
        "2025-04-28": "Freedom Day observed (27 April fell on a Sunday)",
        "2025-05-01": "Workers' Day",
        "2025-06-16": "Youth Day",
        "2025-08-09": "National Women's Day (falls on a Saturday; NOT substituted)",
        "2025-09-24": "Heritage Day",
        "2025-12-16": "Day of Reconciliation",
        "2025-12-25": "Christmas Day",
        "2025-12-26": "Day of Goodwill",
    },
    2026: {
        "2026-01-01": "New Year's Day",
        "2026-03-21": "Human Rights Day (falls on a Saturday; NOT substituted)",
        "2026-04-03": "Good Friday",
        "2026-04-06": "Family Day (Easter Monday)",
        "2026-04-27": "Freedom Day",
        "2026-05-01": "Workers' Day",
        "2026-06-16": "Youth Day",
        "2026-08-10": "National Women's Day observed (9 August falls on a Sunday)",
        "2026-09-24": "Heritage Day",
        "2026-12-16": "Day of Reconciliation",
        "2026-12-25": "Christmas Day",
        "2026-12-26": "Day of Goodwill (falls on a Saturday; NOT substituted)",
    },
}

HOLIDAYS_RULE: dict[str, Any] = {
    "rule": (
        "Public Holidays Act 36 of 1994. TWELVE statutory days, of which TEN are fixed solar "
        "dates -- 1 January, 21 March (Human Rights Day), 27 April (Freedom Day), 1 May "
        "(Workers' Day), 16 June (Youth Day), 9 August (National Women's Day), 24 September "
        "(Heritage Day), 16 December (Day of Reconciliation), 25 December (Christmas Day) and "
        "26 December (Day of Goodwill) -- and TWO are moveable and Christian-computed: Good "
        "Friday and Family Day, the Friday before and the Monday after Easter Sunday. "
        "SUBSTITUTION: section 2(1) moves a public holiday falling on a SUNDAY to the following "
        "Monday. A holiday falling on a SATURDAY is NOT substituted and is simply lost -- which "
        "is why 2024-04-27, 2025-08-09, 2026-03-21 and 2026-12-26 appear in these tables as "
        "unsubstituted Saturdays rather than as Monday closures. The President may additionally "
        "declare an ad hoc public holiday under section 2A, as was done for the 2024-05-29 "
        "national election; no rule predicts one and it can only be added when gazetted."),
    "authority": "Public Holidays Act 36 of 1994 (as amended) and any Presidential proclamation "
                 "in the Government Gazette; the JSE publishes its own trading calendar, which "
                 "follows the Act",
    "table": _ZA_HOLIDAYS,
    "status": {
        2024: "GAZETTED",
        2025: "GAZETTED",
        2026: "DERIVED_FROM_STATUTE -- the fixed dates, the Easter computation (Easter Sunday "
              "2026-04-05) and the Sunday substitution rule are applied. Any section 2A ad hoc "
              "holiday declared later is NOT in this table and can only be added when gazetted.",
    },
    "market_effect": (
        "USDZAR KEEPS TRADING THROUGH EVERY ONE OF THESE CLOSURES, priced in London and New "
        "York, while the JSE and the local interbank market are shut. A South African holiday "
        "is therefore a LIQUIDITY REGIME for the rand and not an absence of price: the domestic "
        "bid is gone, offshore flow dominates, and the reopening session carries a day of "
        "accumulated local order flow into a single auction. The asymmetry is the tradable "
        "object; the closure itself is not. The December closure is the deepest of the year, "
        "with 16, 25 and 26 December landing inside the thinnest two weeks of South African "
        "liquidity."),
    "callable": "countries.za.pack:holidays",
}


def holidays(year: int) -> dict[str, str]:
    """The South African closure table for one year, `{"YYYY-MM-DD": name}`. `{}` if untabulated."""
    return holiday_table(HOLIDAYS_RULE, year)


# --------------------------------------------------------------------------- custom miners
def za_index_expiry_dates(year: int) -> dict[str, Any]:
    """FTSE/JSE Top 40 quarterly futures close-out dates, by the THIRD-THURSDAY rule.

    Code rather than a table because the rule is computable and a table rots. Every close-out is
    checked against the statutory holiday table: when the third Thursday is a public holiday the
    close-out moves, and an event study anchored on the nominal date is then measuring a session
    the market was shut for. The collision is REPORTED, never guessed away.
    """
    rows: list[dict[str, Any]] = []
    table = holidays(year)
    for month in (3, 6, 9, 12):
        first = date(year, month, 1)
        offset = (3 - first.weekday()) % 7  # Thursday = 3
        day = date(year, month, 1 + offset + 14)
        iso = day.isoformat()
        rows.append({
            "date": iso,
            "month": month,
            "holiday_collision": table.get(iso),
            "settlement": "cash-settled against an auction in the early afternoon SAST; the "
                          "exact window is a JSE notice and is not re-derived here",
        })
    return {"year": int(year), "rule": "third Thursday of March, June, September and December",
            "expiries": tuple(rows),
            "unresolved": tuple(r["date"] for r in rows if r["holiday_collision"]),
            "note": "a close-out flagged with a holiday_collision moves by JSE notice; this "
                    "function reports the collision and refuses to invent the roll"}


def za_loadshedding_stage_mw(stage: int) -> dict[str, Any]:
    """The MW that load-shedding stage N removes from the grid, and what that means physically.

    The stage ladder is the most-quoted number in South Africa and it is LINEAR BY DESIGN: each
    stage sheds a further 1,000 MW of national demand. That linearity is what makes the stage a
    usable regressor rather than a label -- stage 6 is not "worse than stage 4", it is 2,000 MW
    more, and a smelter's pot line is a MW number, not a mood.
    """
    n = max(0, int(stage))
    return {
        "stage": n,
        "mw_shed": n * 1000,
        "rule": "each stage sheds a further 1,000 MW of national demand; stages 1-8 are defined "
                "in the NRS 048-9 code of practice and stages above 4 were only ever used from "
                "2022 onward",
        "industrial_effect": (
            "Deep-level PGM and gold mines cannot hoist or ventilate below a power floor, and "
            "ferrochrome and aluminium smelters carry contractual load-curtailment clauses that "
            "bind BEFORE household shedding starts. So the industrial effect of a given stage "
            "arrives EARLIER and is LARGER than the headline suggests, and it shows up in the "
            "Stats SA production print six to ten weeks later."),
        "fx_effect": "the rand reprices the stage within minutes as a risk-premium and "
                     "terms-of-trade signal; the PRODUCTION effect is weeks away. ONE "
                     "OBSERVABLE, TWO HORIZONS, and conflating them is the standard error.",
        "measurable": n > 0,
    }


CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    miner("za_index_expiry_calendar",
          domain_ids=("za_derivatives_expiry", "za_session_microstructure"),
          kind="calendar",
          entry="countries.za.pack:za_index_expiry_dates",
          cadence_s=86400.0,
          steerable=False,
          notes="A fixed cost, not a steerable one: the close-out grid must be read every pass "
                "whatever it yielded last quarter, because a miner conditioning on the wrong "
                "session produces a confident wrong number rather than nothing."),
    miner("za_grid_constraint",
          domain_ids=("za_electricity_constraint", "za_mining_supply"),
          kind="mechanism",
          entry="countries.za.pack:za_loadshedding_stage_mw",
          cadence_s=3600.0,
          steerable=True,
          notes="Turns the load-shedding stage into MW, which is the only form in which it can "
                "be joined to a production series or a metal price."),
)


# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"id": "cftc_cot_zar",
     "name": "CFTC Commitments of Traders -- South African Rand (CME contract)",
     "covers": "non-commercial long, short and spread positions in the CME ZAR future, weekly",
     "frequency": "weekly (Tuesday snapshot)",
     "lag": "published Friday 15:30 ET; the desk's own axis uses a 4-day knowable lag",
     "root": "cftc.gov Commitments of Traders, legacy and disaggregated reports",
     "licence": "free, public",
     "availability": "YES -- South Africa is the ONLY country in this African civilization whose "
                     "currency has a CFTC-reportable futures contract, so it is the only one "
                     "with a genuine speculative-positioning series.",
     "desk_status": "NOT YET MAPPED ON THIS BOX. Measured against "
                    "desks/mt5/data/axes/cot.json: 22 symbols are mapped and ZAR is not among "
                    "them. That is a NAMED GAP with a free public source behind it, not an "
                    "absence of data -- the positioning miner reports UNMEASURED for ZAR until "
                    "the axis carries it."},
    {"id": "jse_foreign_flows",
     "name": "JSE daily foreign portfolio flows -- non-resident net purchases of equities "
             "and bonds",
     "covers": "daily net non-resident purchase/sale value, equities and bonds separately",
     "frequency": "daily", "lag": "same day after the close; about 15:30 UTC",
     "root": "jse.co.za market statistics",
     "licence": "free, public",
     "note": "A FLOW, not a stock, and it is the best daily foreign-positioning series in "
             "Africa. It leads its own FX conversion by the T+3 equity settlement cycle, which "
             "makes the lag structural rather than fitted."},
    {"id": "jse_currency_futures_oi",
     "name": "JSE currency futures and options open interest",
     "covers": "USD/ZAR, EUR/ZAR, GBP/ZAR contracts by open interest and volume",
     "frequency": "daily", "lag": "same day",
     "root": "jse.co.za derivatives market statistics",
     "licence": "free, public",
     "note": "The domestic mirror of the CFTC series: onshore rather than offshore positioning, "
             "and a divergence between the two IS AN OBSERVABLE about who is on which side."},
    {"id": "sarb_forward_book",
     "name": "SARB net open forward position and the forward book",
     "covers": "the central bank's own forward FX exposure",
     "frequency": "monthly", "lag": "published with the reserves release, around the 7th",
     "root": "SARB Web API and the monthly reserves statement",
     "licence": "free, public",
     "note": "HISTORICALLY THE MOST IMPORTANT ZAR SERIES THERE IS and now close to dormant: the "
             "1998 and 2001 crises were amplified by a large negative forward book, which the "
             "SARB has since closed. It is carried for REGIME CONTEXT -- a pre-2004 rand study "
             "is about a central bank that no longer exists."},
)


# --------------------------------------------------------------------------- terminology
#: NATIVE TERMS, KEYED BY DOMAIN. English is an official language of South Africa and most
#: financial reporting is in it, so this table would be lazy if it stopped there: Afrikaans is
#: the language of the agricultural and much of the mining commentary, and isiZulu is the largest
#: home language in the country and the language of the labour and community coverage that
#: precedes a strike. A miner that only knows English words finds an announced strike two days
#: after the union told its members.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "core": ("rand", "randwaarde", "wisselkoers", "valutamark", "verswak", "versterk",
             "irandi", "inani lemali", "intengiso", "imakethe", "exchange rate", "the rand"),
    "za_policy_reaction": ("Reserwebank", "repokoers", "prima koers", "inflasieteiken",
                           "monetêre beleid", "iBhange loMbuso", "izinga lenzalo",
                           "ukwenyuka kwamanani", "repo rate", "MPC", "prime rate",
                           "inflation target", "hawkish", "dovish", "vote split"),
    "za_mining_supply": ("mynbou", "mynproduksie", "platinum", "goud", "chroom", "mangaan",
                         "steenkool", "smeltery", "skag", "imayini", "igolide", "amalahle",
                         "mining production", "shaft", "smelter", "refined output",
                         "PGM basket price", "Section 189", "care and maintenance"),
    "za_electricity_constraint": ("beurtkrag", "kragonderbreking", "Eskom", "netwerk",
                                  "ukucinywa kukagesi", "ugesi", "load-shedding", "stage 6",
                                  "grid", "EAF", "energy availability factor", "diesel burn",
                                  "open-cycle gas turbine", "unplanned outages", "UCLF"),
    "za_labour_and_strikes": ("staking", "vakbond", "loononderhandelinge", "isiteleka",
                              "inyunyana", "strike", "wage talks", "NUM", "AMCU", "Solidarity",
                              "Section 77", "protected strike", "stay-away"),
    "za_fiscal_risk": ("begroting", "staatskuld", "belasting", "tesourie", "isabelomali",
                       "budget", "MTBPS", "Treasury", "debt-to-GDP", "GFECRA", "SOE bailout",
                       "credit rating", "Moody's", "S&P", "greylisting"),
    "za_foreign_flow": ("buitelandse beleggers", "netto aankope", "JSE", "obligasies",
                        "abatshalizimali bangaphandle", "foreign investors", "net purchases",
                        "non-resident", "portfolio flows", "index rebalance", "WGBI"),
    "za_terms_of_trade": ("handelsbalans", "uitvoere", "invoere", "kommoditeitspryse",
                          "ukuthengisa phesheya", "trade balance", "exports", "commodity price",
                          "terms of trade", "current account"),
    "za_agriculture": ("mielies", "witmielies", "geelmielies", "koring", "sojabone", "oes",
                       "droogte", "reënval", "ummbila", "isomiso", "imvula", "maize", "white "
                       "maize", "SAFEX", "import parity", "export parity", "El Nino", "drought"),
    "za_logistics": ("Transnet", "hawe", "spoorlyn", "Richardsbaai", "Durban", "itheku",
                     " port congestion", "rail", "Transnet Freight Rail", "Richards Bay Coal "
                     "Terminal", "backlog", "derailment", "truck queue"),
    "za_session_microstructure": ("opemaak", "slot", "handelsvolume", "wisselvalligheid",
                                  "ukuvulwa kwemakethe", "open", "close", "closing auction",
                                  "gap", "volatility", "turnover", "thin liquidity"),
    "za_risk_proxy_crypto_premium": ("kripto premie", "Bitcoin premie", "arbitrage limiet",
                                     "crypto premium", "arbitrage allowance", "SARS approval",
                                     "single discretionary allowance"),
    "za_gold_fiscal_link": ("goudprys", "goudreserwes", "GFECRA", "igolide", "gold price",
                            "gold reserves", "contingency reserve account", "Treasury "
                            "distribution"),
}


# --------------------------------------------------------------------------- source classes
#: THE TEN LAYERS (principal's per-country depth rule, 2026-09-17). Exactly one per source, and
#: every layer either covered or DECLARED ABSENT WITH A REASON -- never blank. The rule exists
#: because a country "covered" by five obvious official sources is a country whose whole
#: information surface has been mistaken for its front page: the official layer says what the
#: state has decided to publish, and almost nothing about what the people transacting actually
#: see, price and say.
LAYERS: tuple[str, ...] = ("official", "institutional", "academic", "practitioner",
                           "retail_ecology", "app_ecosystem", "media", "archive",
                           "physical_economy", "source_graph")

#: HOW THE DESK IS ALLOWED TO TOUCH IT. Separate from credibility on purpose: a source can be
#: perfectly public and completely wrong, or authoritative and unusable.
ACCESS_LABELS: tuple[str, ...] = ("PUBLIC", "PUBLIC_WITH_TERMS", "LICENSED", "OPEN_DATA",
                                  "PUBLIC_ARCHIVE", "PUBLIC_SOCIAL", "USER_SUBMITTED",
                                  "ACCESS_UNCLEAR", "PRIVATE", "CONFIDENTIAL_MNPI",
                                  "STOLEN_UNAUTHORIZED")

#: WHETHER TO BELIEVE IT. `FRINGE` and `CONTRADICTED` are KEPT, never dropped -- a devaluation
#: rumour that turned out wrong is still evidence about expectations, and a scam report is
#: evidence about a market's plumbing.
CREDIBILITY: tuple[str, ...] = ("AUTHORITATIVE", "RELIABLE", "UNRELIABLE", "FRINGE",
                                "CONTRADICTED", "UNKNOWN")

#: WHETHER IT HAS EVER PREDICTED ANYTHING ON THIS BOX. Every row starts UNTESTED and only a
#: measured screen may move it -- `NARRATIVE_FEATURE` is the honest resting place for material
#: that is informative about sentiment and has never forecast a price.
PREDICTIVE_STATES: tuple[str, ...] = ("UNTESTED", "PREDICTIVE", "NOT_PREDICTIVE",
                                      "NARRATIVE_FEATURE")


def _src(sid: str, label: str, *, layer: str, roots: Any, languages: Any, licence: str,
         access_label: str, credibility: str, predictive_state: str, queries: Any,
         machine_use_allowed: bool = True, notes: str = "") -> dict[str, Any]:
    """`source_class()` plus the principal's five labels, with the enums checked on the way in.

    A MISLABELLED SOURCE IS WORSE THAN AN UNLABELLED ONE, because a wrong label is read as a
    measurement. So a typo in any of the four vocabularies raises here rather than travelling
    into a report. `queries` are NATIVE-LANGUAGE and are not translations: an Afrikaans farming
    forum does not contain the phrase "maize import parity" and an isiZulu labour notice does not
    contain the phrase "protected strike".
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
    _src("za_official_cb", "The South African Reserve Bank and its machine-readable API",
         layer="official",
         roots=("resbank.co.za",
                "custom.resbank.co.za/SarbWebApi",
                "custom.resbank.co.za/SarbWebApi/swagger/index.html",
                "resbank.co.za/en/home/publications/quarterly-bulletin"),
         languages=("en",),
         licence="free, public; the Web API is open and needs no key",
         access_label="OPEN_DATA", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         queries=("repokoers besluit", "SARB MPC statement vote split", "reporate aankondiging",
                  "izinga lenzalo elisha", "rand wisselkoers SARB", "gold and forex reserves "
                  "monthly release"),
         notes="THE HIGHEST-VALUE PUBLIC ROUTE IN THIS CIVILIZATION: a free, documented, "
               "swagger-described REST API from an emerging-market central bank serving "
               "historical exchange rates, current market rates and the macro indicator set. "
               "The ZA data plane catalogues its endpoints from that swagger rather than "
               "hard-coding a guessed path."),
    _src("za_official_stats", "Statistics South Africa and the National Treasury",
         layer="official",
         roots=("statssa.gov.za",
                "statssa.gov.za/?page_id=1854&PPN=P2041 (mining production and sales)",
                "statssa.gov.za/?page_id=1854&PPN=P0141 (CPI)",
                "treasury.gov.za", "sars.gov.za (trade statistics)"),
         languages=("en",),
         licence="free, public; releases are PDF and XLSX on a published calendar",
         access_label="OPEN_DATA", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         queries=("mynproduksie en verkope P2041", "platinum production year on year",
                  "Stats SA mining production release date", "verbruikersprysindeks",
                  "begrotingsrede Februarie", "MTBPS medium term budget"),
         notes="P2041, MINING PRODUCTION AND SALES, is the sensor this pack exists for: physical "
               "output by mineral group, monthly, on a scheduled clock, for the country that "
               "produces most of the world's platinum group metals."),
    _src("za_exchange", "The JSE and its public statistics",
         layer="institutional",
         roots=("jse.co.za", "jse.co.za/services/market-data",
                "jse.co.za/trade/derivative-market", "clientportal.jse.co.za"),
         languages=("en",),
         licence="free public summary tables; the full real-time feed is a LICENSED product and "
                 "is never scraped",
         access_label="PUBLIC_WITH_TERMS", credibility="AUTHORITATIVE",
         predictive_state="UNTESTED",
         queries=("JSE buitelandse beleggers netto aankope", "JSE foreign net purchases daily",
                  "ALSI close-out third Thursday", "currency futures open interest JSE",
                  "obligasie netto aankope nie-inwoners"),
         notes="Daily foreign portfolio flows, derivatives open interest and the close-out "
               "calendar. The free tier is enough for every hypothesis in this pack, and the "
               "real-time feed is deliberately not sought."),
    _src("za_institutional_bodies", "Industry bodies, the unions and the prudential authorities",
         layer="institutional",
         roots=("mineralscouncil.org.za", "asisa.org.za", "banking.org.za",
                "num.org.za", "amcu.co.za", "solidariteit.co.za", "cosatu.org.za",
                "labour.gov.za", "ccma.org.za", "nersa.org.za"),
         languages=("en", "af", "zu"),
         licence="public statements, gazettes and industry reports",
         access_label="PUBLIC", credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("Section 64 kennisgewing staking", "loononderhandelinge platinum",
                  "isiteleka sezimayini", "inyunyana yabasebenzi basemayini",
                  "Minerals Council production statistics", "NERSA tariff determination"),
         notes="A WAGE ROUND IS ANNOUNCED BEFORE IT BECOMES A PRODUCTION NUMBER, and the union "
               "notice reaches members in isiZulu and Afrikaans before it reaches the English "
               "financial press. This is the layer where the native-language requirement is not "
               "decorative."),
    _src("za_academic", "South African academic and policy literature",
         layer="academic",
         roots=("scholar.sun.ac.za", "wiredspace.wits.ac.za", "repository.up.ac.za",
                "econrsa.org", "resbank.co.za working papers",
                "papers.ssrn.com (South African FX and commodity microstructure)"),
         languages=("en", "af"),
         licence="mixed: institutional repositories are open, journals often licensed; never "
                 "scrape a paywall",
         access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("rand deurvloei inflasie pass-through", "exchange rate pass-through South "
                  "Africa", "platinum supply elasticity Bushveld", "load shedding output cost "
                  "estimate", "JSE microstructure closing auction"),
         notes="South African monetary and mining economics carries rand pass-through and PGM "
               "supply-elasticity estimates with no English-market equivalent. It is the best "
               "external check on this pack's own mechanisms."),
    _src("za_practitioner", "Professional market commentary and the sell-side vernacular",
         layer="practitioner",
         roots=("moneyweb.co.za", "sharenet.co.za", "businesslive.co.za",
                "sharenet.co.za/v3/sens_display.php", "profile.co.za",
                "intellidex.co.za", "codera.co.za"),
         languages=("en", "af"),
         licence="public web; mined for VERBATIM CLAIMS only, never for advice",
         access_label="PUBLIC", credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("rand uitkyk begrotingsdag", "rand outlook budget day", "PGM basket price "
                  "rand", "beurtkrag impak op mynbou", "JSE resources rally commentary"),
         notes="The value is a testable mechanism stated in professional shorthand. 'The rand "
               "always weakens on Budget day' is a hypothesis with a date rule inside it; the "
               "author's seniority is irrelevant and is never scored."),
    _src("za_retail_ecology", "Retail boards, Afrikaans farming forums and the crowd's own words",
         layer="retail_ecology",
         roots=("reddit.com/r/JSE_Bets", "reddit.com/r/southafrica (economy threads)",
                "mybroadband.co.za/forum (investments)", "landbou.com forums",
                "forum.sharenet.co.za", "hellopeter.com (broker complaint threads)"),
         languages=("en", "af", "zu"),
         licence="public web; mined for VERBATIM CLAIMS only, never for personal data and never "
                 "for advice",
         access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
         predictive_state="NARRATIVE_FEATURE",
         queries=("rand gaan verswak", "irandi izowa", "beurtkrag stadium 6 vandag",
                  "mielies prys SAFEX bespreking", "EasyEquities offshore allowance limiet",
                  "wanneer koop ek dollars"),
         notes="LOW WEIGHT, NEVER DROPPED. Retail boards are where the load-shedding stage and "
               "the maize price are discussed hours before either reaches a market note, and "
               "where the crowd's positioning is stated out loud. Retained as an evidence object "
               "with credibility UNRELIABLE because that is what it is -- and a crowd that was "
               "wrong is still a measurement of what the crowd believed."),
    _src("za_retail_fringe", "Fringe, contradicted and scam-adjacent public material",
         layer="retail_ecology",
         roots=("public rand-collapse and 'imminent devaluation' commentary",
                "hellopeter.com and consumer-complaint threads on broker and crypto platforms",
                "public warnings and enforcement notices from the FSCA",
                "failure post-mortems on collapsed local schemes"),
         languages=("en", "af"),
         licence="public web; verbatim claims only, no personal data, no re-publication",
         access_label="PUBLIC_SOCIAL", credibility="FRINGE",
         predictive_state="NARRATIVE_FEATURE",
         queries=("rand collapse voorspelling", "SARB gaan bankrot", "FSCA waarskuwing skema",
                  "Bitcoin premie Suid-Afrika arbitrage", "forex scam South Africa warning"),
         notes="KEPT ON PURPOSE AND WEIGHTED NEAR ZERO. A devaluation rumour that turned out "
               "wrong is still evidence about expectations, and a scam report is evidence about "
               "a market's plumbing -- which channels retail actually uses, and where the "
               "friction is. Dropping this class would remove exactly the material that "
               "distinguishes a stressed retail market from a calm one, and it is the class "
               "most likely to be silently discarded by a tidy-minded crawler."),
    _src("za_app_ecosystem", "The apps South Africans actually price the rand and the grid in",
         layer="app_ecosystem",
         roots=("easyequities.co.za", "shyft.standardbank.co.za (retail FX allowance app)",
                "sepush.co.za / EskomSePush (load-shedding stage app and its API docs)",
                "tradingview.com public South African ideas and scripts",
                "app store and play store listings and public release notes for the above"),
         languages=("en", "af"),
         licence="public listings and documentation; the EskomSePush API is KEY-REQUIRED and is "
                 "catalogued in the data plane rather than fetched without one",
         access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("EskomSePush stadium nou", "load shedding app schedule today",
                  "Shyft dollar koop koers", "EasyEquities offshore transfer fee",
                  "TradingView USDZAR idea"),
         notes="A LAYER THAT MATTERS MORE IN AFRICA THAN IN A DEVELOPED MARKET. The stage a "
               "household experiences arrives through an app, not through a utility press "
               "release, and the retail FX allowance is consumed through a bank app with a "
               "posted rate. These are where the population's OWN price and OWN grid state "
               "live, and they are timestamped."),
    _src("za_media", "South African financial press, in both market languages",
         layer="media",
         roots=("news24.com/fin24", "netwerk24.com/sake (Afrikaans)", "sabcnews.com/business",
                "ewn.co.za/business", "dailymaverick.co.za/section/business-maverick",
                "engineeringnews.co.za and miningweekly.com"),
         languages=("en", "af"),
         licence="public headlines and article text; respect robots and rate limits",
         access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("Eskom kondig beurtkrag aan", "Eskom announces stage 6",
                  "Transnet hawe agterstand", "mynbou staking begin", "begroting reaksie rand"),
         notes="Mining Weekly and Engineering News are the specialist pair: they carry shaft, "
               "smelter and rail detail months before it reaches a statistic, and they are "
               "free. Netwerk24's Afrikaans business desk carries the agricultural and "
               "labour-relations coverage first."),
    _src("za_licensed_vendor", "Licensed vendor and exchange products this desk may not extract",
         layer="media",
         roots=("the JSE real-time market data feed and its redistribution licence",
                "subscription-only research portals whose terms forbid automated extraction",
                "vendor terminals carrying South African fixed income and FX"),
         languages=("en",),
         licence="LICENSED. The terms forbid machine extraction and redistribution.",
         access_label="LICENSED", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         machine_use_allowed=True,
         queries=("(none -- this row is REGISTERED AND NEVER QUERIED)",),
         notes="REGISTERED, NEVER SCRAPED, NEVER OMITTED. machine_use_allowed=True is the whole "
               "content of this row: the desk knows these sources exist, knows what they would "
               "add, and does not take them. Omitting the row instead would make the refusal "
               "invisible and would let a later session 'discover' the source and quietly "
               "breach the terms."),
    _src("za_archive", "Historical archives, superseded editions and moved pages",
         layer="archive",
         roots=("resbank.co.za Quarterly Bulletin archive (back editions)",
                "statssa.gov.za publication archive by PPN",
                "web.archive.org captures of SARB, Stats SA, Eskom and JSE pages",
                "nationalgovernment.co.za gazette archive",
                "historicalpapers.wits.ac.za"),
         languages=("en", "af"),
         licence="free, public archives",
         access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         queries=("Quarterly Bulletin 2008 archive", "Stats SA P2041 historical release",
                  "Eskom annual report load factor history", "gazette proclamation public "
                  "holiday", "argief SARB kwartaalblad"),
         notes="THE LAYER THAT MAKES A REVISION VISIBLE. Stats SA restates mining production for "
               "two to three prints and the SARB's snapshot endpoints keep no history at all, so "
               "the ONLY way to know what was knowable in the past is a superseded edition. The "
               "Internet Archive is also the only route back to a page whose shape changed -- "
               "which is how a SHAPE_CHANGED verdict in the data plane gets diagnosed rather "
               "than merely recorded."),
    _src("za_physical_economy", "The grid, the rail, the ports and the grain, measured directly",
         layer="physical_economy",
         roots=("eskom.co.za/dataportal (hourly system data)", "loadshedding.eskom.co.za",
                "transnet.net and transnetportterminals.net operational reports",
                "sagis.org.za (weekly grain deliveries and stocks)", "sagl.co.za",
                "grainsa.co.za", "daff.gov.za crop estimates committee", "weathersa.co.za"),
         languages=("en", "af"),
         licence="free, public; the Eskom portal serves CSV and SAGIS publishes weekly XLSX",
         access_label="OPEN_DATA", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         queries=("Eskom unplanned outages UCLF hourly", "energy availability factor weekly",
                  "SAGIS weeklikse leweringe mielies", "Richards Bay coal terminal throughput",
                  "Durban hawe skepe wag", "reënval afwyking mieliedriehoek"),
         notes="THE LAYER THIS PACK IS TIER 1 FOR. Megawatts, tonnes, wagons and millimetres -- "
               "the physical quantities behind the prices, published free and hourly or weekly, "
               "by a country that produces most of the world's platinum. A price series is what "
               "the market thinks; this is what actually happened."),
    _src("za_source_graph", "How new South African sources are found, and what is refused",
         layer="source_graph",
         roots=("citation and data-annex trails in IMF Article IV and World Bank South Africa "
                "reports", "reference lists in SARB working papers and Quarterly Bulletin "
                "articles", "outbound link graphs from statssa.gov.za and resbank.co.za",
                "the desk's own frontier map in desks/mt5/data/", "opendata.gov.za"),
         languages=("en",),
         licence="free, public",
         access_label="PUBLIC", credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("IMF Article IV South Africa statistical annex", "SARB working paper "
                  "references", "opendata.gov.za dataset list", "Stats SA metadata catalogue"),
         notes="THE META-LAYER, AND THE ONE THAT KEEPS THE OTHER NINE FROM GOING STALE. A source "
               "list is a snapshot; a method for finding sources is not. IMF and World Bank "
               "staff reports are the highest-yield entry point because their annexes cite "
               "series the authorities do not advertise. THIS ROW ALSO CARRIES THE REFUSALS: "
               "(1) any crypto-exchange venue order book, API or native feed is REFUSED "
               "(universe mandate 2026-08-18) -- the South African crypto premium is taken from "
               "public commentary only, is marked pit_feasible=False, and its executable leg is "
               "the broker's own BTCUSD CFD; (2) single-name JSE hypothesis mining is REFUSED "
               "(two-lane order 2026-09-06) -- SENS is read for EVENT context and never mints a "
               "statistical hypothesis; (3) redistribution of any licensed JSE real-time feed or "
               "vendor terminal is REFUSED, and is registered as its own row above rather than "
               "omitted."),
)

#: EVERY LAYER ACCOUNTED FOR, BY NAME. The principal's rule is that a layer is either covered or
#: DECLARED ABSENT WITH A REASON -- never blank, because a blank reads as "nothing there" when it
#: usually means "nobody looked". Derived from the rows above rather than typed, so it cannot
#: drift from them.
SOURCE_LAYER_COVERAGE: dict[str, str] = {
    layer: (", ".join(s["id"] for s in SOURCE_CLASSES if s["layer"] == layer)
            or f"ABSENT: no {layer} source declared for {NAME}")
    for layer in LAYERS
}


# --------------------------------------------------------------------------- datasets

DATASETS: tuple[dict[str, Any], ...] = (
    dataset("za_sarb_historical_fx",
            source="SARB Web API, historical exchange rates "
                   "(custom.resbank.co.za/SarbWebApi)",
            coverage="daily rand rates against the majors, with the SARB's own history",
            frequency="daily",
            publication_lag_days=1.0,
            revisions="the published mid-rate for a past date is not revised; the ENDPOINT can "
                      "change shape, which is a different failure and is detected by the plane's "
                      "shape check rather than by a silently empty series",
            licence="free, public, no key",
            history_from="varies by series; the API exposes its own earliest date per code",
            pit_feasible=True,
            assets=("USDZAR", "EURZAR", "GBPZAR", "ZARJPY"),
            mechanism_families=("fx_reference", "policy_reaction", "regime_state"),
            how_to_fetch="GET the historical exchange rate endpoints listed in the SarbWebApi "
                         "swagger; store the response bytes and the fetch timestamp as a vintage "
                         "so a later re-read is point-in-time"),
    dataset("za_sarb_current_market_rates",
            source="SARB Web API, current market rates and home-page rates",
            coverage="the SARB's own snapshot of spot rates and key policy rates",
            frequency="daily, intraday refresh",
            publication_lag_days=0.0,
            revisions="a snapshot is never revised; it is SUPERSEDED, which makes vintage "
                      "storage the only way to reconstruct what was knowable at a past moment",
            licence="free, public, no key",
            history_from="no history is served -- history exists ONLY as the vintages this desk "
                         "keeps, which is precisely why the plane vaults every fetch",
            pit_feasible=True,
            assets=("USDZAR", "EURZAR", "GBPZAR"),
            mechanism_families=("fx_reference", "regime_state"),
            how_to_fetch="GET /WebIndicators/CurrentMarketRates and /WebIndicators/HomePageRates; "
                         "one vintage per fetch, content-hashed"),
    dataset("za_sarb_macro_indicators",
            source="SARB Web API, macro indicator and timeseries observation endpoints",
            coverage="repo rate, CPI, reserves, GDP, the SARB's published indicator set",
            frequency="mixed: daily, monthly and quarterly by series code",
            publication_lag_days=7.0,
            revisions="GDP and current-account series ARE revised; the API serves the CURRENT "
                      "vintage only, so a PIT study must use the desk's stored vintages and not "
                      "the live endpoint",
            licence="free, public, no key",
            history_from="per series code",
            pit_feasible=True,
            assets=("USDZAR", "XAUUSD", "UST10Y"),
            mechanism_families=("macro_surprise", "policy_reaction", "terms_of_trade"),
            how_to_fetch="GET the timeseries observation endpoint per indicator code; the code "
                         "list itself is read from the API rather than hard-coded"),
    dataset("za_statssa_mining_production",
            source="Statistics South Africa, P2041 Mining: production and sales",
            coverage="physical production and sales VOLUME AND VALUE by mineral group -- PGMs, "
                     "gold, iron ore, coal, chromium, manganese, copper, nickel, diamonds",
            frequency="monthly",
            publication_lag_days=45.0,
            revisions="EVERY MONTH IS REVISED, often materially, for two to three prints. This "
                      "is the dataset where vintage storage is not optional: the first print and "
                      "the third revision of the same month can disagree by more than the "
                      "signal, and a study joined to the LATEST value is using data nobody had.",
            licence="free, public",
            history_from="1980s in the Stats SA archive; the modern PPN series from the 2000s",
            pit_feasible=True,
            assets=("XPTUSD", "XPDUSD", "XAUUSD", "XCUUSD", "USDZAR", "AUDUSD"),
            mechanism_families=("commodity_production_sensor", "terms_of_trade",
                                "supply_shock", "china_africa_transmission"),
            how_to_fetch="the release is published on the Stats SA calendar at about 11:30 SAST "
                         "(09:30 UTC), normally in the second week of the month and covering the "
                         "month two months prior; the plane records the RELEASE timestamp, not "
                         "the reference month, because the release timestamp is what was "
                         "knowable"),
    dataset("za_statssa_cpi",
            source="Statistics South Africa, P0141 Consumer Price Index",
            coverage="headline and core CPI, monthly and annual",
            frequency="monthly",
            publication_lag_days=21.0,
            revisions="rarely revised; the WEIGHTS are re-based periodically, which is a series "
                      "break rather than a revision and is declared as an era",
            licence="free, public",
            history_from="2008 for the current basket definition",
            pit_feasible=True,
            assets=("USDZAR", "UST10Y"),
            mechanism_families=("macro_surprise", "policy_reaction"),
            how_to_fetch="Stats SA release calendar, published at about 10:00 SAST (08:00 UTC) "
                         "on a Wednesday mid-month"),
    dataset("za_eskom_system_data",
            source="Eskom Data Portal, hourly national system data",
            coverage="national demand, available capacity, unplanned outages (UCLF), energy "
                     "availability factor, OCGT (diesel) generation, and the load-shedding stage",
            frequency="hourly",
            publication_lag_days=0.04,
            revisions="the hourly series is restated as metered data replaces estimates; the "
                      "STAGE is an announcement and is never revised",
            licence="free, public CSV from the data portal. EskomSePush's stage API is a "
                    "THIRD-PARTY KEYED service: catalogued, key-required, never fetched "
                    "without a key present",
            history_from="2018 in the data portal",
            pit_feasible=True,
            assets=("USDZAR", "XPTUSD", "XPDUSD", "XALUSD"),
            mechanism_families=("commodity_production_sensor", "supply_shock", "regime_state"),
            how_to_fetch="the data portal's CSV export for the hourly series; the stage is "
                         "announced through Eskom's own channels and is recorded with its "
                         "announcement timestamp"),
    dataset("za_jse_foreign_flows",
            source="JSE daily market statistics, non-resident net purchases",
            coverage="daily net non-resident purchases and sales of JSE equities and bonds",
            frequency="daily",
            publication_lag_days=0.5,
            revisions="occasionally restated for late trade reporting",
            licence="free, public summary tables",
            history_from="2000s",
            pit_feasible=True,
            assets=("USDZAR", "UK100"),
            mechanism_families=("local_market_ecology", "portfolio_flow"),
            how_to_fetch="the JSE market statistics tables; stamp the publication time, which "
                         "is after the 17:00 SAST close"),
    dataset("za_sagis_grain",
            source="SAGIS -- South African Grain Information Service",
            coverage="weekly producer deliveries, stocks and imports/exports of maize, wheat, "
                     "soybeans and sunflower",
            frequency="weekly",
            publication_lag_days=7.0,
            revisions="deliveries are restated as late returns arrive",
            licence="free, public",
            history_from="1997",
            pit_feasible=True,
            assets=("CORN", "WHEAT", "SOYBEAN", "USDZAR"),
            mechanism_families=("weather_agriculture", "supply_shock"),
            how_to_fetch="SAGIS publishes weekly XLSX; the CEC crop estimates are a separate "
                         "monthly release with its own calendar"),
    dataset("za_transnet_port_rail",
            source="Transnet and Transnet National Ports Authority operational reports",
            coverage="port throughput, ship waiting times, rail volumes on the coal and iron-ore "
                     "export lines",
            frequency="weekly to monthly, irregular",
            publication_lag_days=14.0,
            revisions="irregular publication is itself the problem: a missing week is NOT a zero",
            licence="free, public but inconsistently published",
            history_from="patchy; treated as NOT_PIT_SAFE until a stable vintage series exists",
            pit_feasible=False,
            assets=("XALUSD", "XCUUSD", "USDZAR"),
            mechanism_families=("trade_shipping_logistics", "supply_shock"),
            how_to_fetch="Transnet media releases and port authority reports; this is the "
                         "weakest link in the ZA data plane and is declared so rather than "
                         "papered over"),
    dataset("za_cot_zar",
            source="CFTC Commitments of Traders, CME South African Rand contract",
            coverage="weekly non-commercial and commercial positioning in the ZAR future",
            frequency="weekly",
            publication_lag_days=4.0,
            revisions="not revised",
            licence="free, public",
            history_from="1990s",
            pit_feasible=True,
            assets=("USDZAR", "ZARJPY"),
            mechanism_families=("positioning", "crowding"),
            how_to_fetch="the CFTC weekly report; NOTE that desks/mt5/data/axes/cot.json does "
                         "not currently map ZAR (22 symbols, none of them the rand), so the "
                         "positioning miner reports UNMEASURED for this pack until it does"),
)


# --------------------------------------------------------------------------- actors
ACTORS: tuple[dict[str, Any], ...] = (
    actor("South African Reserve Bank",
          holds="gold and foreign exchange reserves, the repo rate and the GFECRA",
          forced_to=("set the repo rate against a 3-6% band it has publicly outgrown",
                     "buy foreign exchange opportunistically to rebuild reserves",
                     "value and distribute GFECRA gains to the National Treasury"),
          when="six scheduled MPC meetings a year at 13:00 UTC, plus a monthly reserves release "
               "around the 7th",
          information=("CPI", "the output gap", "the rand's pass-through", "global rates",
                       "its own reserve adequacy"),
          constraints=("an explicit inflation mandate and NO exchange-rate objective",
                       "a fiscal authority whose debt path it cannot control",
                       "reserve adequacy measured against short-term external debt"),
          instruments=("USDZAR", "EURZAR", "ZARJPY", "XAUUSD"),
          counterparties=("the National Treasury", "domestic banks", "foreign portfolio "
                          "investors"),
          observables=("the MPC statement and vote split", "the monthly reserves print",
                       "the GFECRA distribution", "the Quarterly Bulletin"),
          impact="the vote split moves the front of the curve and the rand within minutes; the "
                 "GFECRA distribution links the GOLD PRICE to South African fiscal risk",
          persistence="structural -- the mandate has been stable since 2000, which is why the "
                      "surprise is measurable against a stable reaction function",
          falsifier="if USDZAR shows no differential response to a vote split conditional on "
                    "the same rate decision, the vote-split channel does not exist and the "
                    "statement is the only event",
          notes="The SARB's refusal to defend the rand is the pack's key negative fact and the "
                "control condition for every Nigerian and Egyptian intervention hypothesis."),
    actor("Eskom, the state electricity utility",
          holds="the national grid, an ageing coal fleet and the load-shedding schedule",
          forced_to=("shed load in 1,000 MW stages when available capacity falls below demand",
                     "burn diesel in open-cycle turbines to avoid shedding, at a cost it "
                     "publishes",
                     "curtail large industrial customers under contract BEFORE households"),
          when="continuously, announced within the hour; hourly system data is published",
          information=("unplanned outage levels", "unit trips", "diesel stock", "demand forecast"),
          constraints=("a fleet whose energy availability factor has run in the 50-60% range",
                       "regulated tariffs and a balance sheet the Treasury underwrites",
                       "a legal duty to supply"),
          instruments=("USDZAR", "XPTUSD", "XPDUSD", "XALUSD"),
          counterparties=("mines and smelters on curtailment contracts", "households",
                          "the National Treasury"),
          observables=("the announced stage", "hourly UCLF and EAF", "OCGT diesel burn",
                       "the Stats SA production print six to ten weeks later"),
          impact="the rand prices the stage in minutes as a risk premium; the METAL prices it "
                 "weeks later through physically lost output. One observable, two horizons.",
          persistence="multi-year, and it has ERAS -- the 2022-2023 crisis, the 2024 suspension "
                      "and the intermittent returns since -- which is why a pooled estimate "
                      "across them measures an average of different grids",
          falsifier="if a stage escalation produces no measurable change in the following "
                    "quarter's PGM production print once seasonality and the base effect are "
                    "controlled, the production channel is absent and only the risk-premium "
                    "channel exists",
          notes="This actor is the reason South Africa is an exogenous sensor for XPTUSD rather "
                "than a currency story with a mining anecdote attached."),
    actor("The PGM producers as a class",
          holds="deep-level platinum, palladium and rhodium shafts on the Bushveld Complex",
          forced_to=("suspend hoisting when power is curtailed",
                     "place high-cost shafts on care and maintenance when the PGM basket price "
                     "falls below cash cost",
                     "issue Section 189 restructuring notices before large retrenchments"),
          when="production decisions are quarterly; power curtailment is immediate; Section 189 "
               "notices are public and dated",
          information=("the rand PGM basket price", "power availability", "wage settlements",
                       "the cost curve"),
          constraints=("rand-denominated costs against dollar-denominated revenue -- a WEAKER "
                       "rand is a margin subsidy, which is why ZA supply does NOT respond to a "
                       "falling dollar metal price the way a US producer's would",
                       "shaft depth and ventilation limits", "a unionised workforce"),
          instruments=("XPTUSD", "XPDUSD", "USDZAR"),
          counterparties=("autocatalyst manufacturers", "Chinese and European importers",
                          "Eskom"),
          observables=("Stats SA P2041 PGM production", "Section 189 notices",
                       "care-and-maintenance announcements", "refined vs mined output gaps"),
          impact="a sustained production fall tightens the physical PGM market with a lag of "
                 "one to two quarters; the ANNOUNCEMENT moves the metal within the session",
          persistence="structural: there is no substitute source of primary supply at this scale "
                      "on the relevant horizon",
          falsifier="if PGM prices show no conditional response to South African production "
                    "surprises after controlling for the global auto cycle and the dollar, the "
                    "supply-sensor hypothesis for this pack is dead and the pack's Tier 1 status "
                    "should be re-argued",
          notes="Named as a CLASS. No producer is ever a symbol on a docket (two-lane order)."),
    actor("Gold producers and the deep-level gold mines",
          holds="the deepest operating gold mines in the world, on a declining reserve base",
          forced_to=("hoist within a power and ventilation envelope",
                     "hedge or not hedge a rand-dollar margin that is mostly currency"),
          when="quarterly operational updates; monthly in the Stats SA print",
          information=("the rand gold price", "grade", "power", "the wage round"),
          constraints=("depth, heat and seismicity", "a falling national reserve base",
                       "rand costs against dollar revenue"),
          instruments=("XAUUSD", "USDZAR"),
          counterparties=("refiners", "the SARB's reserve management", "global bullion demand"),
          observables=("Stats SA gold production volume", "the rand gold price",
                       "mine closure and restructuring announcements"),
          impact="South Africa is no longer a marginal global gold supplier, so the channel runs "
                 "mainly the OTHER WAY: the dollar gold price drives South African export "
                 "revenue, fiscal receipts and the rand. THE PACK DECLARES THIS DIRECTION "
                 "EXPLICITLY because assuming the supply direction is the error the country's "
                 "history invites.",
          persistence="structural decline",
          falsifier="if rand gold revenue has no measurable effect on the current account or on "
                    "USDZAR conditional on the dollar, the fiscal-gold channel is absent",
          notes="The GFECRA distribution makes the gold price a SOUTH AFRICAN FISCAL VARIABLE, "
                "which is unusual and is seeded as its own edge."),
    actor("The National Treasury and the fiscal authority",
          holds="the sovereign balance sheet, the bond programme and the SOE guarantees",
          forced_to=("fund a persistent deficit in a market that prices political risk",
                     "publish a Budget in February and an MTBPS in October or November",
                     "absorb state-owned-enterprise bailouts"),
          when="two scheduled fiscal events a year, both in the early afternoon SAST, plus "
               "weekly bond auctions",
          information=("revenue collections", "the debt path", "rating-agency reviews"),
          constraints=("a debt-to-GDP path the market watches more than the level",
                       "credit ratings and index inclusion", "SOE contingent liabilities"),
          instruments=("USDZAR", "UST10Y", "UK100"),
          counterparties=("foreign bondholders", "rating agencies", "the SARB via GFECRA"),
          observables=("Budget and MTBPS documents and their timestamps",
                       "weekly auction bid-to-cover", "rating actions",
                       "FATF greylisting status"),
          impact="Budget day and MTBPS day are the largest scheduled domestic rand events of the "
                 "year, and a rating action is the largest unscheduled one",
          persistence="structural",
          falsifier="if USDZAR realised volatility in the Budget-day afternoon window is "
                    "statistically indistinguishable from matched non-Budget Wednesdays, the "
                    "fiscal event channel does not exist",
          notes="The February Budget is one of very few EM fiscal events with a fixed, "
                "pre-announced delivery time."),
    actor("Foreign portfolio investors in JSE equities and SAGBs",
          holds="a large share of South African government bonds and JSE free float",
          forced_to=("rebalance to index weights at the LONDON fix on rebalance dates",
                     "convert settlement proceeds into hard currency on T+3",
                     "sell the rand as a liquid proxy when EM risk turns, regardless of South "
                     "African news"),
          when="daily flows; index rebalances on scheduled dates; risk-off episodes unscheduled",
          information=("global EM risk appetite", "the carry", "rating actions",
                       "index membership"),
          constraints=("mandate limits on EM exposure", "index-tracking error",
                       "the rand's own liquidity, which invites its use as a proxy hedge"),
          instruments=("USDZAR", "UK100", "US500"),
          counterparties=("local banks and asset managers", "the JSE", "global EM funds"),
          observables=("JSE daily non-resident net purchases", "index rebalance calendars",
                       "EM fund flow reports"),
          impact="the T+3 settlement lag makes the equity flow a LEADING indicator of the FX "
                 "flow it causes -- the rare case where the causal ordering is institutional "
                 "rather than assumed",
          persistence="structural, with a level shift at each index-inclusion or exclusion event",
          falsifier="if the JSE's non-resident net purchase series has no predictive content for "
                    "USDZAR at a three-business-day lag after controlling for the global EM "
                    "beta, the settlement-lag channel is not there",
          notes="This is the actor that makes USDZAR a GLOBAL instrument and is therefore the "
                "main confound for every domestic sensor in this pack."),
    actor("South African pension funds under Regulation 28",
          holds="the country's contractual savings pool, with a 45% offshore allowance",
          forced_to=("rebalance towards the offshore limit when it is raised",
                     "buy foreign assets, and therefore sell rand, as domestic returns lag"),
          when="quarterly rebalancing; a step change on 2022-02-23 when the limit went from 30% "
               "to 45%",
          information=("relative returns", "the regulatory limit", "trustee mandates"),
          constraints=("Regulation 28 of the Pension Funds Act",
                       "prudential limits per asset class", "member liability profiles"),
          instruments=("USDZAR", "US500", "UK100"),
          counterparties=("global asset managers", "local banks providing the FX"),
          observables=("quarterly fund statistics", "the regulatory change dates",
                       "asset manager survey data"),
          impact="a STRUCTURAL, slow, one-directional rand-selling flow with a published rule "
                 "behind it -- the closest thing South Africa has to Korea's pension FX actor",
          persistence="multi-year; the 2022 limit increase is a dated regime boundary",
          falsifier="if USDZAR shows no drift differential across the 2022-02-23 boundary after "
                    "controlling for the dollar and the carry, the structural-flow hypothesis "
                    "is not measurable at this frequency",
          notes="Slow flows are hard to detect and easy to assert. This actor's falsifier is "
                "deliberately strict."),
    actor("The mining unions -- NUM, AMCU and Solidarity",
          holds="the labour supply of the platinum, gold and coal complexes",
          forced_to=("negotiate multi-year wage agreements on a public cycle",
                     "serve a Section 64 notice before a protected strike, which is DATED and "
                     "public"),
          when="wage rounds are seasonal and announced; notices precede action by days",
          information=("the rand basket price", "producer margins", "inflation",
                       "member expectations"),
          constraints=("the Labour Relations Act's procedural requirements",
                       "inter-union competition for membership", "member hardship in a strike"),
          instruments=("XPTUSD", "XPDUSD", "XAUUSD", "USDZAR"),
          counterparties=("the producers", "the CCMA", "the Department of Labour"),
          observables=("Section 64 notices", "union statements in isiZulu and English",
                       "CCMA referrals", "wage settlement percentages"),
          impact="a protected strike at a major PGM complex removes physical supply on a known "
                 "start date -- one of the very few genuinely scheduled supply shocks in any "
                 "commodity market",
          persistence="episodic but recurrent; the 2014 five-month platinum strike is the "
                      "canonical case and the base rate is low",
          falsifier="if PGM prices show no abnormal return in the window following a Section 64 "
                    "notice relative to matched non-notice days, the notice carries no "
                    "information the market has not already priced",
          notes="n is small by construction and the pack says so: this edge exists to be SIZED "
                "honestly, never to be fitted."),
    actor("Chinese buyers of South African ore and metal",
          holds="the demand side of South Africa's largest single export relationship",
          forced_to=("build or draw inventory against a domestic industrial cycle",
                     "source chrome, manganese and PGMs where they are actually produced"),
          when="monthly customs data on both sides; Chinese PMI monthly",
          information=("Chinese industrial demand", "port inventories", "steel margins"),
          constraints=("the physical geography of supply -- there is no alternative Bushveld",
                       "shipping capacity and freight rates"),
          instruments=("USDZAR", "XPTUSD", "AUDUSD", "XCUUSD"),
          counterparties=("South African producers", "bulk shippers", "Chinese steel mills"),
          observables=("Chinese customs imports by origin", "South African export volumes",
                       "port and rail throughput", "Chinese PMI"),
          impact="the China demand state CONDITIONS every South African supply signal: the same "
                 "production fall is bullish in a strong demand state and noise in a weak one, "
                 "which is why this pack's headline hypotheses are TRIPLES rather than pairs",
          persistence="structural, and the single most important conditioner in the Africa "
                      "civilization",
          falsifier="if the conditional effect of a ZA production surprise on XPTUSD is "
                    "statistically identical across high and low Chinese demand states, the "
                    "conditioning adds nothing and the pair is the right object after all",
          notes="This actor is the join between the ZA pack and the China-Africa family in "
                "desks/mt5/research/africa_interaction.py."),
    actor("Transnet, the rail and port monopoly",
          holds="the coal line to Richards Bay, the iron-ore line to Saldanha and the container "
                "ports",
          forced_to=("move export volume on a rail network with a declining locomotive fleet",
                     "berth ships at ports with published waiting times"),
          when="continuous; reported weekly to monthly and irregularly",
          information=("cable theft and derailment incidents", "locomotive availability",
                       "berth queues"),
          constraints=("capital constraints and an ageing fleet", "theft and vandalism",
                       "a single-operator structure now being partially opened"),
          instruments=("USDZAR", "XALUSD", "XCUUSD"),
          counterparties=("miners", "shipping lines", "the fiscus"),
          observables=("port waiting times", "rail volumes on the export lines",
                       "Transnet operational updates"),
          impact="a logistics failure converts a production success into an inventory build at "
                 "the mine gate -- so PRODUCTION AND EXPORT CAN DIVERGE, and a study using "
                 "production as a proxy for supply reaching the world market is wrong in exactly "
                 "the episodes that matter",
          persistence="multi-year structural degradation with episodic acute failures",
          falsifier="if South African export volumes track production volumes with no "
                    "independent logistics residual, the logistics channel carries no separate "
                    "information",
          notes="The weakest data link in this pack and it is declared: Transnet's publication "
                "is irregular and the dataset is marked pit_feasible=False."),
    actor("South African agricultural producers and the maize belt",
          holds="the largest maize crop in southern Africa, rain-fed and therefore ENSO-exposed",
          forced_to=("plant in a summer-rainfall window that El Nino can close",
                     "sell into a SAFEX price that is set by import or export parity, which "
                     "embeds the rand"),
          when="planting October to December; harvest April to July; weekly SAGIS deliveries",
          information=("rainfall", "the CEC crop estimates", "the rand", "world grain prices"),
          constraints=("a rain-fed system with limited irrigation",
                       "the parity band, which caps how far local prices can diverge from world "
                       "prices plus freight"),
          instruments=("CORN", "WHEAT", "SOYBEAN", "USDZAR"),
          counterparties=("regional importers across southern Africa", "millers", "SAFEX"),
          observables=("SAGIS weekly deliveries and stocks", "CEC crop estimates",
                       "rainfall anomalies", "SAFEX vs CBOT parity spreads"),
          impact="a southern-African drought turns the region from an exporter into an importer, "
                 "which is a regional food-inflation and FX event with a world-grain leg",
          persistence="seasonal with multi-year ENSO cycles",
          falsifier="if the SAFEX-to-CBOT parity spread shows no conditional response to "
                    "measured rainfall anomalies after controlling for USDZAR, the local weather "
                    "channel is subsumed by the currency and is not separately tradable",
          notes="THE RAND IS INSIDE THE LOCAL GRAIN PRICE. Any maize hypothesis must control for "
                "USDZAR explicitly or it is a currency study wearing an agricultural label."),
    actor("South African households and the retail investor",
          holds="a small but growing offshore and crypto allocation under the exchange-control "
                "allowances",
          forced_to=("use the R1m single discretionary allowance and the R10m foreign investment "
                     "allowance, which CAP the arbitrage that would close a local premium"),
          when="continuous; the allowance resets annually",
          information=("local returns", "the rand's direction", "offshore platform access"),
          constraints=("exchange control allowances and SARS tax clearance for the larger one",
                       "platform and banking friction"),
          instruments=("USDZAR", "BTCUSD"),
          counterparties=("local banks", "offshore brokers", "local crypto platforms"),
          observables=("public commentary on the local crypto premium",
                       "retail platform statistics", "SARB exchange-control reporting"),
          impact="the allowance CAP is why a local premium can persist: the arbitrage is legal "
                 "but rationed, so the premium is a measure of local risk appetite rather than "
                 "of a broken market",
          persistence="structural while exchange control exists",
          falsifier="if the observed premium shows no relationship to USDZAR volatility or to "
                    "local risk appetite proxies, it is a platform artefact and not a signal",
          notes="Carried as PUBLIC COMMENTARY with pit_feasible=False. NO crypto-exchange venue "
                "is named, subscribed or crawled anywhere in this pack (universe mandate "
                "2026-08-18); the executable leg is the broker's own BTCUSD CFD."),
    actor("Rating agencies and index providers",
          holds="the sovereign's credit rating and its membership of global bond indices",
          forced_to=("publish scheduled review dates and act on them",
                     "include or exclude the sovereign from indices by published rules"),
          when="two scheduled reviews per agency per year, on published dates",
          information=("the fiscal path", "growth", "governance", "SOE liabilities"),
          constraints=("their own published methodologies", "the review calendar"),
          instruments=("USDZAR", "UST10Y"),
          counterparties=("the Treasury", "index-tracking funds"),
          observables=("review calendars", "rating actions and outlook changes",
                       "index inclusion or exclusion announcements"),
          impact="an index exclusion is a MECHANICAL forced-seller event with a known date and a "
                 "known size, which is a rarer and cleaner object than a rating opinion",
          persistence="episodic; the 2020 WGBI exclusion is the canonical South African case",
          falsifier="if USDZAR shows no abnormal move in the window around scheduled review "
                    "dates relative to matched non-review Fridays, the scheduled-review channel "
                    "is absent and only unscheduled actions matter",
          notes="Scheduled review dates are one of the few genuinely exogenous date grids "
                "available for an EM currency."),
)


# --------------------------------------------------------------------------- domains
DOMAINS: tuple[dict[str, Any], ...] = (
    domain("za_mining_supply", "Physical mineral production as an exogenous supply sensor",
           objects=("Stats SA P2041 production volume by mineral group",
                    "production surprise versus a seasonal and trend baseline",
                    "the refined-versus-mined gap", "revision behaviour across vintages"),
           conditions=("the Chinese industrial demand state", "the dollar state",
                       "the electricity-constraint state", "the reference month's base effect"),
           instruments=("XPTUSD", "XPDUSD", "XAUUSD", "XCUUSD", "USDZAR"),
           controls=("the same release date shifted forward one year",
                     "Australian and Chilean production surprises, which share the global "
                     "demand factor but not the South African grid",
                     "matched non-release Thursdays",
                     "randomised assignment of the surprise sign"),
           notes="THE PACK'S CENTRAL DOMAIN. The vintage requirement is absolute: the first "
                 "print and the third revision can disagree by more than the signal."),
    domain("za_electricity_constraint", "Load-shedding as a two-horizon supply and risk shock",
           objects=("the announced stage and its MW equivalent",
                    "hourly unplanned outages and the energy availability factor",
                    "OCGT diesel burn as a stress proxy",
                    "stage escalations and de-escalations as separate events"),
           conditions=("season, because winter demand and summer maintenance are different "
                       "regimes", "the PGM basket price", "whether curtailment clauses bind"),
           instruments=("USDZAR", "XPTUSD", "XPDUSD", "XALUSD"),
           controls=("matched hours in weeks with no stage change",
                     "randomised escalation dates within the same month",
                     "the same escalation in a year with a different demand regime",
                     "EURZAR against USDZAR, to separate the rand leg from the dollar leg"),
           notes="One observable, two horizons: minutes for the rand, weeks for the metal. A "
                 "study that mixes them measures neither."),
    domain("za_policy_reaction", "The MPC decision, the vote split and the statement window",
           objects=("the repo decision against expectation", "the vote count",
                    "the statement's own language", "the gap between decision and press "
                    "conference"),
           conditions=("the inflation regime", "the global rate cycle", "the rand's level"),
           instruments=("USDZAR", "EURZAR", "UST10Y"),
           controls=("matched non-MPC Thursdays at 13:00 UTC",
                     "the same decision with a different vote split",
                     "other EM central bank decisions in the same week"),
           notes="Six events a year: n is small and the pack will not pretend otherwise."),
    domain("za_fiscal_risk", "Budget day, the MTBPS and the rating calendar",
           objects=("the Budget and MTBPS delivery windows", "the debt path revision",
                    "scheduled rating review dates", "index inclusion and exclusion events"),
           conditions=("the global EM risk state", "the level of foreign bond ownership"),
           instruments=("USDZAR", "UST10Y", "UK100"),
           controls=("matched non-Budget Wednesdays in the same afternoon window",
                     "scheduled reviews that produced no action",
                     "other EM sovereigns reviewed the same month"),
           notes="The February Budget has a fixed pre-announced delivery time, which is rare."),
    domain("za_foreign_flow", "Non-resident portfolio flow and its T+3 currency consequence",
           objects=("JSE daily non-resident net purchases of equities and bonds",
                    "index rebalance dates", "the settlement-lagged FX conversion"),
           conditions=("the global EM flow regime", "index event windows", "month-end"),
           instruments=("USDZAR", "UK100"),
           controls=("the same flow magnitude on non-rebalance days",
                     "other EM currencies with the same global flow and different settlement "
                     "conventions", "randomised lag assignment between 0 and 6 business days"),
           notes="The three-day lag is INSTITUTIONAL, not fitted -- which is what makes this "
                 "domain a causal-ordering test rather than a correlation."),
    domain("za_terms_of_trade", "Commodity prices as South Africa's income, and the rand as the "
                                "adjustment variable",
           objects=("the rand-denominated export basket", "the trade balance",
                    "the commodity terms-of-trade index"),
           conditions=("the dollar state", "the China demand state", "the freight cost state"),
           instruments=("USDZAR", "AUDUSD", "XPTUSD", "XCUUSD"),
           controls=("AUDUSD as a matched commodity currency with a different commodity mix "
                     "and no electricity constraint",
                     "the same commodity move in a period of stable South African supply",
                     "randomised pairing of commodity moves to rand moves"),
           notes="AUDUSD is the pack's single best control: same global factor, different "
                 "domestic institutions."),
    domain("za_labour_and_strikes", "Scheduled and announced supply interruption",
           objects=("Section 64 strike notices", "wage round calendars",
                    "settlement percentages", "strike start and end dates"),
           conditions=("the PGM basket price relative to cash costs", "inter-union competition"),
           instruments=("XPTUSD", "XPDUSD", "USDZAR"),
           controls=("wage rounds that settled without a notice",
                     "matched windows in years with no strike",
                     "randomised notice dates within the wage season"),
           notes="Small n by construction. This domain exists to be sized honestly."),
    domain("za_agriculture", "Southern African rainfall, the maize crop and the parity band",
           objects=("SAGIS weekly deliveries and stocks", "CEC crop estimates",
                    "rainfall anomalies", "the SAFEX-to-CBOT parity spread"),
           conditions=("the ENSO state", "the planting window", "the rand"),
           instruments=("CORN", "WHEAT", "SOYBEAN", "USDZAR"),
           controls=("USDZAR as an explicit regressor, because the rand is INSIDE the local "
                     "price", "the same rainfall anomaly in a year with a different currency "
                     "regime", "northern-hemisphere crop years as a placebo season"),
           notes="Every hypothesis here must control for the rand or it is a currency study."),
    domain("za_logistics", "Rail and port capacity as the gap between production and export",
           objects=("port waiting times", "rail volumes on the export lines",
                    "the production-minus-export residual"),
           conditions=("the acute-failure state", "the commodity price"),
           instruments=("USDZAR", "XALUSD", "XCUUSD"),
           controls=("periods with the same production and no logistics incident",
                     "other bulk exporters' port data",
                     "randomised incident dates"),
           notes="Declared NOT_PIT_SAFE at the dataset level: Transnet's publication is "
                 "irregular and a missing week is not a zero."),
    domain("za_session_microstructure", "The rand's day: Johannesburg, London and the offshore "
                                        "hours",
           objects=("the 07:00-15:00 UTC local session", "the London overlap",
                    "the closing auction window", "the overnight gap into the local open"),
           conditions=("local holidays, when the rand trades and Johannesburg does not",
                       "month-end and the London fix", "the DST mismatch between SAST and "
                       "London"),
           instruments=("USDZAR", "EURZAR", "GBPZAR", "ZARJPY"),
           controls=("matched non-holiday sessions",
                     "EURZAR versus USDZAR to separate the rand leg from the dollar leg",
                     "the same window in the opposite DST half of the year"),
           notes="South African holidays are a LIQUIDITY regime for the rand, not an absence of "
                 "price, and that asymmetry is the tradable object."),
    domain("za_derivatives_expiry", "JSE quarterly close-out and index rebalance pressure",
           objects=("third-Thursday close-out dates", "currency futures open interest",
                    "the FTSE/JSE quarterly review"),
           conditions=("open interest concentration", "whether the close-out collides with a "
                       "holiday"),
           instruments=("USDZAR", "UK100"),
           controls=("non-close-out third Thursdays",
                     "the same calendar position in non-quarterly months",
                     "randomised close-out dates"),
           notes="The close-out auction window is a JSE notice and is declared, not guessed."),
    domain("za_gold_fiscal_link", "The gold price as a South African fiscal variable via GFECRA",
           objects=("GFECRA valuation and distribution events",
                    "the monthly gold and foreign exchange reserves print",
                    "the rand gold price"),
           conditions=("the dollar gold price level", "the rand", "the fiscal cycle"),
           instruments=("XAUUSD", "USDZAR"),
           controls=("months with a large gold move and no distribution event",
                     "other gold-holding sovereigns with no equivalent mechanism",
                     "matched non-announcement months"),
           notes="An unusual two-way link: the gold price is normally exogenous to a currency, "
                 "and here it enters the fiscus directly."),
    domain("za_risk_proxy_crypto_premium", "The local crypto premium as a rationed-arbitrage "
                                           "risk-appetite gauge",
           objects=("publicly reported local premium or discount",
                    "the exchange-control allowance as the arbitrage cap"),
           conditions=("USDZAR volatility", "local risk appetite", "allowance reset timing"),
           instruments=("BTCUSD", "USDZAR"),
           controls=("periods of equal USDZAR volatility with no premium",
                     "other rationed markets", "randomised premium dates"),
           notes="PUBLIC COMMENTARY ONLY, pit_feasible=False, no venue named or crawled. The "
                 "executable leg is the broker's own BTCUSD CFD (universe mandate 2026-08-18)."),
)


# --------------------------------------------------------------------------- transmission
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    edge("za_pgm_production_to_metal",
         source="Stats SA P2041 platinum-group-metals production volume, monthly",
         mechanism="South Africa produces the large majority of world primary PGM supply, so a "
                   "production shortfall is a direct reduction in the physical availability of "
                   "an executable metal, with a one-to-two-quarter lag into the refined market",
         targets=("XPTUSD", "XPDUSD"),
         sign="production surprise DOWN -> XPTUSD and XPDUSD UP over the following weeks",
         lag="release timestamp, about 09:30 UTC, covering the month two months prior",
         horizon="five to sixty sessions",
         control="Australian and Chilean production surprises, which share the global demand "
                 "factor but not the South African grid; and the same release date shifted "
                 "forward one year",
         evidence="HYPOTHESIS",
         notes="THE PACK'S FLAGSHIP EDGE and the reason South Africa is Tier 1. It must be "
               "measured against the CURRENT vintage the market actually had, not the latest."),
    edge("za_loadshedding_to_rand",
         source="Eskom load-shedding stage escalations and hourly unplanned outage levels",
         mechanism="an escalation is an immediate, public, quantified reduction in national "
                   "output capacity; the rand prices it as a growth and risk-premium shock "
                   "within minutes, long before any production statistic exists",
         targets=("USDZAR", "EURZAR"),
         sign="stage escalation -> USDZAR UP in the hours following the announcement",
         lag="announcement timestamp, usually inside the Johannesburg afternoon",
         horizon="intraday to five sessions",
         control="EURZAR versus USDZAR to strip the dollar leg; matched hours in weeks with no "
                 "stage change; and escalations that were pre-announced versus those that were "
                 "not",
         evidence="HYPOTHESIS"),
    edge("za_loadshedding_to_pgm_supply",
         source="sustained high load-shedding stages and smelter curtailment",
         mechanism="smelters and deep-level shafts are curtailed under contract BEFORE household "
                   "shedding, so a sustained stage regime removes physical metal output with a "
                   "six-to-ten-week lag into the production print",
         targets=("XPTUSD", "XPDUSD", "XALUSD"),
         sign="sustained high-stage regime -> lower ZA production print -> metal UP",
         lag="six to ten weeks from the stage regime to the production print",
         horizon="one to two quarters",
         control="periods of equal metal demand with a stable grid; and aluminium, whose "
                 "smelting is the most power-intensive of the three and should respond most",
         evidence="HYPOTHESIS",
         notes="THE SAME OBSERVABLE AS THE EDGE ABOVE AT A DIFFERENT HORIZON. Declared as two "
               "edges on purpose: pooling them measures neither."),
    edge("za_gold_price_to_fiscus_to_rand",
         source="the dollar gold price and the SARB's GFECRA valuation and distribution",
         mechanism="gold reserve revaluation gains accrue to the GFECRA and have been "
                   "distributed to the National Treasury, so the gold price enters South "
                   "African fiscal arithmetic directly -- an unusual channel that runs from a "
                   "global commodity into a sovereign's deficit funding",
         targets=("USDZAR", "XAUUSD"),
         sign="sustained XAUUSD UP -> improved ZA fiscal position -> USDZAR DOWN around "
              "distribution and Budget events",
         lag="months; the distribution is announced at a fiscal event",
         horizon="one to two quarters",
         control="months with large gold moves and no distribution event; other gold-holding "
                 "sovereigns with no equivalent mechanism",
         evidence="HYPOTHESIS"),
    edge("za_foreign_equity_flow_to_rand",
         source="JSE daily non-resident net purchases of equities and bonds",
         mechanism="equities settle T+3 through Strate, so a non-resident purchase on day T "
                   "creates a rand demand on T+3 by the settlement convention rather than by "
                   "choice -- the causal ordering is institutional",
         targets=("USDZAR",),
         sign="large non-resident net BUY -> USDZAR DOWN three business days later",
         lag="three business days, set by the settlement cycle",
         horizon="three to ten sessions",
         control="randomised lag assignment between zero and six business days, which should "
                 "show no structure if the T+3 story is real; and matched flow magnitudes on "
                 "days with no settlement obligation",
         evidence="HYPOTHESIS"),
    edge("za_mining_shock_to_commodity_currencies",
         source="South African production and export surprises across the mineral complex",
         mechanism="a supply shock in the world's dominant source of a mineral raises the price "
                   "of that mineral, which is income for every other commodity exporter -- the "
                   "shock reaches AUDUSD through the price, not through Australia",
         targets=("AUDUSD", "XCUUSD", "XALUSD"),
         sign="ZA supply shortfall -> metal UP -> AUDUSD UP",
         lag="one to ten sessions after the price responds",
         horizon="five to forty sessions",
         control="AUDUSD moves on days with no ZA release, which isolate the global factor; and "
                 "ZA releases in minerals Australia does not produce",
         evidence="HYPOTHESIS"),
    edge("za_china_demand_conditions_za_supply",
         source="the Chinese industrial demand state joined to South African production surprises",
         mechanism="a supply shortfall only prices when there is demand to disappoint; the same "
                   "ZA production fall should move the metal in a strong Chinese demand state "
                   "and not in a weak one",
         targets=("XPTUSD", "XPDUSD", "XCUUSD", "USDZAR"),
         sign="ZA supply DOWN in a HIGH China demand state -> metal UP strongly; in a LOW state "
              "-> no measurable effect",
         lag="the release timestamp, conditioned on the most recent Chinese demand reading",
         horizon="ten to sixty sessions",
         control="the SAME production surprises sorted into the opposite demand state, which is "
                 "the interaction's own placebo; and randomised state assignment",
         evidence="HYPOTHESIS",
         notes="THE TRIPLE. This is the edge that makes the Africa civilization more than a set "
               "of country notes, and it is mined as an interaction in "
               "desks/mt5/research/africa_interaction.py."),
    edge("za_budget_day_to_rand_volatility",
         source="the February Budget and the October/November MTBPS, both with fixed delivery "
                "times",
         mechanism="the two largest scheduled domestic risk events of the South African year "
                   "resolve fiscal uncertainty in a known afternoon window",
         targets=("USDZAR", "ZARJPY"),
         sign="elevated realised range in the delivery window relative to matched afternoons",
         lag="the delivery timestamp, early afternoon SAST",
         horizon="intraday to three sessions",
         control="matched non-Budget Wednesdays in the same window; and the MTBPS versus the "
                 "Budget, which differ in magnitude but share the mechanism",
         evidence="HYPOTHESIS"),
    edge("za_drought_to_regional_grain_and_rand",
         source="southern African rainfall anomalies and the CEC crop estimates",
         mechanism="a drought turns the region from a maize exporter into an importer, raising "
                   "regional food inflation and the import bill simultaneously",
         targets=("CORN", "WHEAT", "USDZAR"),
         sign="severe rainfall deficit in the planting window -> local price to import parity -> "
              "USDZAR UP and regional grain demand UP",
         lag="the rainfall anomaly leads the crop estimate by one to three months",
         horizon="one to three quarters",
         control="USDZAR as an explicit regressor because the rand is inside the local price; "
                 "and northern-hemisphere crop years as a placebo season",
         evidence="HYPOTHESIS"),
    edge("za_strike_notice_to_pgm",
         source="Section 64 protected-strike notices at PGM operations",
         mechanism="a protected strike removes physical supply on a KNOWN start date -- one of "
                   "the few genuinely scheduled supply shocks in any commodity market",
         targets=("XPTUSD", "XPDUSD"),
         sign="notice served -> XPTUSD and XPDUSD UP into and through the start date",
         lag="notice-to-action is days and is published",
         horizon="five to sixty sessions",
         control="wage rounds that settled with no notice; and matched windows in years with no "
                 "strike",
         evidence="HYPOTHESIS",
         notes="n is tiny by construction. This edge exists to be SIZED honestly and can never "
               "clear a gauntlet on a single episode."),
    edge("za_holiday_liquidity_asymmetry",
         source="the South African statutory holiday table",
         mechanism="the rand trades offshore through every local closure, so a South African "
                   "holiday removes the domestic bid and leaves offshore flow to set the price; "
                   "the reopening session then absorbs a day of accumulated local order flow",
         targets=("USDZAR", "EURZAR", "GBPZAR"),
         sign="reopening session after a local holiday shows an elevated range relative to "
              "matched non-holiday sessions",
         lag="the closure itself; the effect is in the NEXT local open",
         horizon="one to three sessions",
         control="matched weekday sessions with no preceding closure; and UK or US holidays, "
                 "which remove a different bid",
         evidence="HYPOTHESIS"),
    edge("za_logistics_gap_to_metal",
         source="the residual between South African production and South African exports",
         mechanism="rail and port failure strands metal at the mine gate, so the world market "
                   "sees less supply than the production statistic implies -- the production "
                   "print OVERSTATES available supply exactly when logistics fail",
         targets=("XALUSD", "XCUUSD", "USDZAR"),
         sign="widening production-minus-export residual -> metal UP beyond what production "
              "alone predicts",
         lag="one to two months, limited by irregular publication",
         horizon="one to two quarters",
         control="periods with equal production and no logistics incident; other bulk exporters' "
                 "port data",
         evidence="HYPOTHESIS",
         notes="Marked NOT_PIT_SAFE at the dataset level. This edge is declared so the gap is "
               "visible, not so it can be traded before the data supports it."),
)

#: Derived, never hand-maintained: the executable symbols this pack's economics reach that are
#: not South Africa's own price.
TRANSMISSION_TARGETS: tuple[str, ...] = tuple(sorted(
    {t for e in TRANSMISSION_EDGES_SEED for t in e["targets"]} - set(OWN_PRICE)))


# --------------------------------------------------------------------------- eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    era("za_pre_loadshedding", start="2015-01-01", end="2018-11-30",
        label="Before chronic load-shedding",
        what_changed="the grid was strained but shedding was episodic; mining output was not "
                     "systematically power-constrained",
        invalidates="any PGM supply-elasticity estimate from this period applied to the "
                    "post-2019 grid is estimating a different production function"),
    era("za_loadshedding_returns", start="2018-12-01", end="2021-12-31",
        label="Load-shedding becomes recurrent",
        what_changed="stages 1-4 became a regular feature; large industrial curtailment clauses "
                     "began to bind",
        invalidates="rand volatility estimates pooled with the previous era understate the "
                    "domestic growth-risk component"),
    era("za_grid_crisis", start="2022-01-01", end="2024-03-25",
        label="The grid crisis, stages 5 and 6 and the record shedding year",
        what_changed="shedding reached stages 6 and briefly beyond; energy availability fell to "
                     "the low 50s; the rand carried a persistent domestic growth discount",
        invalidates="EVERY unconditional USDZAR volatility or drift estimate that pools this "
                    "window with either neighbour is averaging two different economies"),
    era("za_grid_suspension", start="2024-03-26", end="2024-12-31",
        label="The long suspension",
        what_changed="load-shedding was suspended for an extended period for the first time in "
                     "years; the growth discount partially unwound",
        invalidates="a load-shedding effect estimated across this era and the crisis measures "
                    "the AVERAGE of a binding and a non-binding constraint, which is a number "
                    "that describes neither"),
    era("za_regulation28_offshore_45", start="2022-02-23", end=None,
        label="The Regulation 28 offshore limit raised from 30% to 45%",
        what_changed="South African pension funds were permitted half again as much offshore "
                     "exposure, creating a multi-year structural rand-selling rebalance",
        invalidates="any structural USDZAR drift estimate pooled across this date is fitting one "
                    "trend to two different regulatory regimes"),
    era("za_gnu", start="2024-06-14", end=None,
        label="The Government of National Unity",
        what_changed="the 2024 election produced a coalition; the domestic political risk "
                     "premium repriced sharply and the rand's correlation with local politics "
                     "changed level",
        invalidates="political-risk-premium estimates from the single-party era do not transfer; "
                    "the reaction function to domestic political news is a different object"),
    era("za_gfecra_distribution", start="2024-02-21", end=None,
        label="GFECRA distributions to the National Treasury begin",
        what_changed="gold and FX revaluation gains started flowing to the fiscus, creating a "
                     "direct gold-price-to-deficit channel that did not previously exist",
        invalidates="a pre-2024 study of the gold price and South African fiscal risk is "
                    "measuring an economy where this channel was closed"),
    era("za_greylisting", start="2023-02-24", end="2025-10-24",
        label="FATF greylisting and its removal",
        what_changed="enhanced due diligence on South African counterparties raised friction in "
                     "cross-border flows and correspondent banking",
        invalidates="cross-border flow and settlement-friction studies must condition on this "
                    "window; the entry and exit dates are both scheduled FATF plenary outcomes"),
    era("za_zaronia_transition", start="2023-11-01", end=None,
        label="ZARONIA becomes the recommended reference rate",
        what_changed="the market began migrating from JIBAR to a transaction-based overnight "
                     "rate; the two are not the same quantity",
        invalidates="carry and funding studies pooled across the transition are pooling two "
                    "definitions of the South African short rate"),
)


# --------------------------------------------------------------------------- the pack
def spec() -> dict[str, Any]:
    """THIS PACK AS PLAIN DATA -- the twenty-one fields exactly as this department declares them.

    THE SOURCE OF TRUTH, and the thing the tests validate. `libs/research/country_lab.py` owns a
    frozen `CountryPack` whose row classes have their own field names, and its `__post_init__`
    DROPS any row it cannot construct. That is the right behaviour for the framework -- a row it
    could not type would otherwise be mined as if it were complete -- but it means the typed
    object is a LOSSY VIEW of a pack written in this package's richer vocabulary. So the plain
    data is kept, `pack()` adapts it explicitly below, and nothing is silently thinner than what
    was written here.
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
    """The four fields whose vocabulary differs from the country lab's, translated into its shape.

    WHY AN EXPLICIT ADAPTER RATHER THAN A CONVENIENT COINCIDENCE. `actors`, `domains` and
    `datasets` already match the lab's `ActorRow`, `DomainRow` and `DatasetRow` field for field,
    so they need nothing. `edge()`, `era()` and the convention dictionaries do NOT: a
    `TransmissionSeed` is keyed on `(to_country, asset)` and a single edge here names several
    targets, so ONE EDGE BECOMES SEVERAL SEEDS, and an `Era` carries only a name, a start, an end
    and free notes where `era()` carries the label, what changed and what a pooled study would be
    measuring. Everything the typed row has no field for is preserved in `notes` rather than
    dropped, and the open-ended eras take a sentinel end date because the framework's `Era`
    requires one -- THE SENTINEL IS A FRAMEWORK REQUIREMENT AND NEVER A CLAIM ABOUT WHEN THE ERA
    ENDS.
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
    fixings = tuple({"name": str(v.get("name") or k), "time_utc": str(v.get("time_utc") or ""),
                     "dst_rule": "none", "instruments": OWN_PRICE,
                     "notes": "; ".join(f"{kk}={vv}" for kk, vv in v.items() if kk != "name")}
                    for k, v in FIXING_CONVENTIONS.items() if isinstance(v, dict))
    settle = tuple({"name": k, "kind": "month_end", "instruments": OWN_PRICE, "notes": str(v)}
                   for k, v in SETTLEMENT_CONVENTIONS.items())
    venues = tuple({"name": str(v.get("name") or k), "index_symbols": (),
                    "expiry_rule": str(v.get("expiry_rule") or ""),
                    "open_utc": "", "close_utc": "",
                    "notes": "; ".join(f"{kk}={vv}" for kk, vv in v.items() if kk != "name")}
                   for k, v in EXCHANGES.items() if isinstance(v, dict))
    every_day = tuple(sorted(d for tbl in _ZA_HOLIDAYS.values() for d in tbl))
    return {"transmission_edges_seed": tuple(seeds), "policy_eras": eras,
            "fixing_conventions": fixings, "settlement_conventions": settle,
            "exchanges": venues,
            "holidays_rule": {"dates": every_day, "notes": str(HOLIDAYS_RULE["rule"])},
            "fiscal_year_end": "03-31",
            "export_economy": "metals_exporter",
            "retail_leverage_regime": "capped",
            "cot_currency": "ZAR",
            "positioning_sources": tuple(str(p["id"]) for p in POSITIONING_SOURCES),
            "source_classes": tuple(str(s["id"]) for s in SOURCE_CLASSES),
            "custom_miners": tuple(str(m["entry"]) for m in CUSTOM_MINERS),
            "miner_domains": {str(m["name"]): tuple(m["domain_ids"]) for m in CUSTOM_MINERS},
            "mission": "mine South Africa to exhaustion as an exogenous supply, grid and "
                       "terms-of-trade sensor for the metals and commodity currencies the desk "
                       "already trades"}


def pack() -> Any:
    """The South Africa country pack. `CountryPack` when the framework has landed, else a dict."""
    return build_pack(**{**spec(), **framework_rows()})


def priority_weight() -> float:
    """This pack's share of the opening African compute ladder. A PRIOR, replaced by survivors."""
    return PRIORITY_WEIGHT


def instrument_report(path: Any = None) -> dict[str, Any]:
    """What this pack can trade, what carries its economics and what is missing, MEASURED against
    the broker registry rather than asserted."""
    split = resolve(EXECUTABLE_INSTRUMENTS, path)
    return {"code": CODE, "own_price": OWN_PRICE, "executable": tuple(split["tradable"]),
            "equities_refused": tuple(split["equities"]),
            "absent_from_universe": tuple(split["absent"]),
            "transmission_targets": TRANSMISSION_TARGETS,
            "named_absent_instruments": ABSENT_INSTRUMENTS,
            "priority_weight": PRIORITY_WEIGHT,
            "dataset_fields": DATASET_FIELDS}
