"""THE KENYA COUNTRY PACK -- a published buy/sell spread, a transit corridor and two rainy seasons.

THE STRUCTURAL FACTS, STATED FIRST BECAUSE THEY BIND EVERYTHING BELOW.

  * USDKES IS NOT ON THIS BROKER. Kenya is TRANSMISSION-ONLY and `OWN_PRICE` is empty on purpose.
  * NEITHER IS TEA, AND TEA IS KENYA'S LARGEST AGRICULTURAL EXPORT. There is no tea contract in
    the broker registry and no adequate substitute: coffee is a different crop, a different
    buyer base and a different price cycle. The pack names this in `ABSENT_INSTRUMENTS` and
    refuses to proxy a tea mechanism into COFARA, because a carrier that does not contain the
    mechanism is worse than no carrier at all -- it produces a measurable number about the wrong
    thing.

SO WHAT IS KENYA FOR. Three things the desk can actually use:

  * A DAILY BUY, SELL AND MEAN EXCHANGE RATE, FREE, FROM THE CENTRAL BANK. Everyone quotes the
    mean. THE SPREAD IS WHERE THE INFORMATION IS: a widening published buy/sell spread on a
    stable mean is a market clearing at a rate the mean does not show. That is the same
    quantity-over-price insight that makes Nigeria's turnover print valuable, arriving in a
    different form, and Kenya publishes it every business day.
  * THE EAST AFRICAN RAINFALL CYCLE. Kenya has TWO growing seasons -- the long rains from March
    to May and the short rains from October to December -- so a failed season is followed by
    another chance six months later, and a MULTI-SEASON failure is a categorically different
    event from a single one. That distinction is the whole of the 2020-2023 drought and it is
    the supply side of a soft complex the desk can trade.
  * THE NORTHERN CORRIDOR. Mombasa is the port for Uganda, Rwanda, South Sudan and eastern DRC,
    so Kenyan port and rail throughput is a REGIONAL trade observable rather than a national one.

THE DESIGN CONTRAST WITH NIGERIA IS THE POINT OF RUNNING BOTH. Nigeria is an oil EXPORTER and
Kenya is an oil IMPORTER. The same Brent move is income for one and a cost for the other, and the
two economies share a continent, a frontier-risk classification and a dollar-funding cycle. A
Brent shock that moves both in the SAME direction is a risk-appetite effect; one that moves them
in OPPOSITE directions is the oil channel itself. Neither country can separate those alone.

WHAT THIS PACK MAY NOT DO. No single-name equity is ever a hypothesis (two-lane order,
2026-09-06) -- and Kenya is where that rule needs naming, because the mobile-money operator is
both the country's most useful liquidity observable and a listed company. It is an OBSERVABLE AND
NEVER A SYMBOL. No crypto-exchange ground is hunted (universe mandate, 2026-08-18).
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

CODE = "ke"
NAME = "Kenya"
REGION_COMMAND = "AFRICA"
CURRENCY = "KES"
NATIVE_LANGUAGES = ("sw", "en")

#: COMPUTE PRIORITY. A satellite: below ZA (1.00), NG (0.62) and EG (0.40), above GH/CFA (0.14).
#: A PRIOR the source-ROI layer is expected to overwrite by measured survivors.
PRIORITY_WEIGHT: float = 0.22

#: EMPTY ON PURPOSE. USDKES is not quoted on this account and the shilling is not deliverable
#: offshore. Kenya reaches the docket only through carriers.
OWN_PRICE: tuple[str, ...] = ()

#: What the KE department may place an order in. Every one is in the broker registry and none is
#: a single-name equity. The soft complex is the export leg, Brent is the IMPORT COST leg, and
#: the African and frontier crosses are the risk leg.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "COFARA", "COFROB", "SUGAR", "SUGARRAW", "CORN", "WHEAT", "COTTON", "XBRUSD", "XTIUSD",
    "USDZAR", "USDTRY", "USDINR", "EURUSD", "GBPUSD", "USDX", "UST10Y", "UKGILT", "XAUUSD")

#: The instruments a Nairobi desk reaches for that THIS broker does not quote.
ABSENT_INSTRUMENTS: tuple[dict[str, str], ...] = (
    {"instrument": "TEA -- the Mombasa auction price, and Kenya's largest agricultural export",
     "why": "there is NO tea contract anywhere in desks/mt5/data/universe/universe.json",
     "carried_by": "NOTHING ADEQUATE, AND THE PACK SAYS SO. The coffee contracts are a "
                   "different crop, a different buyer base and a different price cycle; using "
                   "COFARA as a tea proxy would produce a confident measurement of the wrong "
                   "thing. Tea therefore enters this pack as a CONDITIONING OBSERVABLE for "
                   "Kenyan export earnings and FX supply, never as a price the desk claims to "
                   "trade. This is the single largest declared gap in the pack."},
    {"instrument": "USDKES -- the shilling itself",
     "why": "absent from the broker registry; not deliverable offshore",
     "carried_by": "USDZAR as the liquid African risk carrier. A CARRIER, NOT A SUBSTITUTE: "
                   "Kenya's idiosyncratic FX-management regime is exactly what the rand does "
                   "not contain, and every edge that uses it says so."},
    {"instrument": "Kenyan sovereign eurobonds (the 2024 and 2032 points are the liquid ones)",
     "why": "absent; the broker quotes UKGILT, UST05Y and UST10Y and no frontier credit",
     "carried_by": "UST10Y as the global duration leg, with the Kenya-specific credit spread "
                   "left UNMEASURED BY NAME"},
    {"instrument": "NSE 20 Share Index and NASI",
     "why": "absent; no Kenyan equity index CFD is quoted",
     "carried_by": "nothing adequate; the pack declares this a GAP rather than proxying a "
                   "frontier equity index into a developed-market one"},
    {"instrument": "Cut flowers and fresh horticulture",
     "why": "no contract exists anywhere for these; they are auction and contract goods",
     "carried_by": "EURUSD, because the revenue is euro-denominated and the buyer is European, "
                   "with the volume leg left UNMEASURED"},
)


# --------------------------------------------------------------------------- central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "Central Bank of Kenya (CBK)",
    "native_name": "Benki Kuu ya Kenya",
    "framework": "inflation_targeter",
    "framework_caveat": (
        "THE LABEL IS HONEST ONLY WITH THE CAVEAT. The CBK targets inflation at 5% within a "
        "plus-or-minus 2.5 point band and states that the shilling is market-determined. In "
        "practice it manages the rate through reserve operations and through the banks, and "
        "between roughly 2022 and early 2023 THE PUBLISHED INDICATIVE RATE VISIBLY DIVERGED "
        "FROM THE RATE AT WHICH BANKS WOULD ACTUALLY TRANSACT -- an episode widely discussed at "
        "the time, in which the official series was stable and the interbank market had thinned "
        "to almost nothing. That period is declared as an era precisely because the published "
        "series is the least informative part of it, and any study that uses the official mean "
        "through that window is measuring a policy choice rather than a price."),
    "committee": "Monetary Policy Committee (MPC)",
    "policy_rate": "the Central Bank Rate (CBR), with the Cash Reserve Ratio used alongside it",
    "meetings_per_year": 6,
    "schedule_rule": (
        "The MPC meets roughly every two months -- six to eight times a year depending on the "
        "cycle and on ad hoc meetings -- with the decision announced the same afternoon in "
        "Nairobi. EAT is UTC+3 ALL YEAR and Kenya observes no daylight saving, so a Kenyan "
        "announcement's UTC time never moves. That is the opposite of Egypt, where DST moves "
        "the announcement's UTC stamp twice a year, and it makes Kenya the easier of the two to "
        "anchor an event study on."),
    "timezone": "EAT = UTC+3 all year, no DST.",
    "fx_operations": (
        "Reserve sales and purchases, and moral suasion through the banks. The CBK frames "
        "reserve adequacy in MONTHS OF IMPORT COVER against a statutory floor, which is a "
        "genuinely useful published state variable: it converts a reserve level and an import "
        "bill into one number the market watches and the central bank is accountable for. There "
        "is also a government-to-government fuel import arrangement with Gulf suppliers, which "
        "converted a continuous daily dollar demand into a LUMPY, SCHEDULED one -- a real change "
        "in the shape of Kenyan FX demand and one of the most distinctive mechanisms here."),
    "reserves": "usable foreign exchange reserves, published weekly in the CBK bulletin, with "
                "the months-of-import-cover figure alongside",
    "publication_classes": ("MPC press release", "Weekly Bulletin", "Monthly Economic Indicators",
                            "Annual Report", "daily indicative exchange rates",
                            "national payments and mobile-money statistics"),
    "decision_dates": {
        2024: ("2024-02-06", "2024-04-03", "2024-06-05", "2024-08-06", "2024-10-08",
               "2024-12-05"),
        2025: ("2025-02-05", "2025-04-08", "2025-06-10", "2025-08-12", "2025-10-07",
               "2025-12-09"),
        2026: ("2026-02-10", "2026-04-07", "2026-06-09", "2026-08-11", "2026-10-06",
               "2026-12-08"),
    },
    "decision_dates_status": {
        2024: "PUBLIC_RECORD",
        2025: "PUBLIC_RECORD",
        2026: "RULE_DERIVED_UNVERIFIED -- the bi-monthly, early-in-the-month Tuesday pattern "
              "projected forward. THE DATA PLANE MUST REPLACE THESE WITH THE PUBLISHED CALENDAR "
              "BEFORE ANY 2026 EVENT STUDY IS SCORED. The CBK also calls ad hoc meetings, which "
              "no rule predicts and which are exactly the meetings that matter most.",
    },
    "decision_time_utc": "approximately 11:00-13:00; OBSERVED, not nominal",
    "notes": "The 2024-02 eurobond buyback is the canonical Kenyan episode: a sovereign that the "
             "market had priced for a disorderly maturity bought back a large part of it and the "
             "shilling then appreciated sharply. It is a rare, clean, dated demonstration that "
             "frontier FX is priced off the EXTERNAL FUNDING CALENDAR rather than off the "
             "current account.",
}


# --------------------------------------------------------------------------- fixings
FIXING_CONVENTIONS: dict[str, Any] = {
    "cbk_daily_indicative": {
        "name": "CBK daily indicative exchange rates -- MEAN, BUY and SELL",
        "publisher": "Central Bank of Kenya",
        "definition": "indicative rates across a list of currencies, published each business day "
                      "with a buying rate, a selling rate and their mean",
        "published_local": "late afternoon EAT, after the local market",
        "published_utc": "approximately 13:00-15:00; the plane records the observed stamp per "
                         "vintage rather than asserting a minute",
        "why_the_spread_is_the_signal": (
            "EVERYBODY QUOTES THE MEAN AND THE INFORMATION IS IN THE SPREAD. The mean is an "
            "average of two numbers the central bank publishes; the WIDTH between them is the "
            "price of immediacy in a market the CBK also manages. A widening published spread "
            "on a stable mean is a market clearing at a rate the mean does not show, and it is "
            "the Kenyan analogue of Nigeria's turnover collapse: the price says calm and the "
            "microstructure says otherwise. `data_plane.parse_cbk_daily_fx` computes it in "
            "basis points on every row for exactly this reason."),
    },
    "interbank": {
        "name": "the interbank foreign exchange rate and its volume",
        "publisher": "CBK weekly bulletin",
        "why_it_matters": "the volume is the check on the rate. In the 2022-2023 episode the "
                          "published rate was stable and interbank volume had collapsed, which "
                          "is the same diagnosis Nigeria's deal count gives.",
    },
    "retail_counter": {
        "name": "commercial bank counter rates",
        "status": "PUBLIC COMMENTARY. The gap between the CBK indicative rate and the rate a "
                  "bank will actually quote a corporate was the observable that made the "
                  "2022-2023 divergence visible, and it is carried at weekly resolution with "
                  "corroboration across reporters, pit_feasible=False for any single quote.",
    },
    "deliverability": "THE SHILLING IS NOT DELIVERABLE OFFSHORE and has no broker quote here. "
                      "Every Kenyan mechanism must be carried by another instrument.",
    "dst": "NONE. EAT is UTC+3 year-round, so unlike Egypt the UTC stamp of a Kenyan release "
           "never moves.",
}


# --------------------------------------------------------------------------- settlement
SETTLEMENT_CONVENTIONS: dict[str, Any] = {
    "spot": "T+2 in the interbank market, settled in shillings through the CBK's real-time gross "
            "settlement system",
    "equity_settlement": "T+3 at the Nairobi Securities Exchange through the Central Depository "
                         "and Settlement Corporation",
    "auction_cycle": "THE COFFEE AND TEA AUCTIONS ARE WEEKLY AND THEIR PROCEEDS SETTLE ON A "
                     "PUBLISHED LAG. That makes the export FX inflow a WEEKLY CALENDAR OBJECT "
                     "rather than a continuous flow -- a rare piece of structure in a frontier "
                     "FX market, and one that can be tested against matched non-auction weeks.",
    "fuel_import_cycle": "the government-to-government fuel import arrangement converted a "
                         "continuous daily dollar demand into LUMPY SCHEDULED PAYMENTS on "
                         "extended credit terms. The shape of the demand changed even where the "
                         "annual total did not, and a study spanning the change is pooling two "
                         "different demand processes.",
    "month_end": "corporate and importer demand concentrates at month end, as everywhere; in a "
                 "thin market that concentration is a larger share of total volume than it "
                 "would be in a deep one, which is why the effect should be LARGER here than in "
                 "South Africa if the mechanism is real",
    "fiscal_cycle": "the budget year runs July to June, so the June year-end and the July "
                    "start-up are the Kenyan fiscal calendar's two pressure points -- NOT "
                    "December, and a study that imports a calendar-year fiscal seasonal is "
                    "using the wrong country's calendar",
}


# --------------------------------------------------------------------------- exchanges
EXCHANGES: dict[str, Any] = {
    "cash": {
        "name": "Nairobi Securities Exchange (NSE)",
        "hours_local": "09:00-15:00 EAT",
        "hours_utc": "06:00-12:00",
        "settlement": "T+3",
        "index_symbols": (),
        "index_symbols_note": "neither the NSE 20 nor NASI is quoted on this account; both are "
                              "named in ABSENT_INSTRUMENTS with no carrier claimed",
        "public_data": "the NSE publishes daily market statistics including FOREIGN INVESTOR "
                       "PARTICIPATION and net flow -- a free daily foreign-flow series for a "
                       "frontier market, which is unusual and useful",
    },
    "commodity_auctions": {
        "name": "the Mombasa Tea Auction (EATTA) and the Nairobi Coffee Exchange",
        "cadence": "weekly",
        "why_they_matter": "THESE ARE REAL PRICE-DISCOVERY VENUES FOR PHYSICAL GOODS, with "
                           "published prices and volumes, in a region where most agricultural "
                           "prices are contract-negotiated and invisible. The Mombasa auction is "
                           "the largest tea auction in the world by volume and sets the price "
                           "for East African tea generally, so it is a REGIONAL observable that "
                           "happens to be published in Kenya.",
        "caveat": "and the desk cannot trade tea, which is why this venue is a conditioning "
                  "observable and never a price leg",
    },
    "derivatives": {
        "name": "NEXT -- the NSE's derivatives market",
        "status": "listed and thin. It produces no positioning series this desk can use, and "
                  "that is DECLARED rather than left as an empty field.",
    },
}


FISCAL_YEAR_END: dict[str, str] = {
    "government": "30 June. The Budget Statement is delivered in June for the year beginning "
                  "1 July -- so THE KENYAN FISCAL CALENDAR IS NOT THE CALENDAR YEAR and any "
                  "seasonal imported from a December-year-end economy is wrong by six months.",
    "corporate": "31 December for most listed companies, which means the corporate and "
                 "government cycles are DELIBERATELY OUT OF PHASE and both matter",
    "cbk": "30 June",
    "note": "the Finance Bill, tabled ahead of the July start, has twice become a major "
            "political event in its own right and is a scheduled fiscal-risk date",
}


# --------------------------------------------------------------------------- holidays
#: Kenya's Public Holidays Act with the SUNDAY substitution rule applied (a holiday on a Sunday
#: is observed the following Monday; a SATURDAY holiday is NOT substituted). The Islamic days are
#: declared and moon-dependent and say so in their own name strings.
_KE_HOLIDAYS: dict[int, dict[str, str]] = {
    2024: {
        "2024-01-01": "New Year's Day",
        "2024-03-29": "Good Friday",
        "2024-04-01": "Easter Monday",
        "2024-04-10": "Idd-ul-Fitr (moon-dependent; declared)",
        "2024-05-01": "Labour Day",
        "2024-06-17": "Idd-ul-Azha (moon-dependent; declared)",
        "2024-06-18": "Madaraka Day observed (1 June fell on a Saturday; observed by "
                      "declaration, not by the Sunday rule)",
        "2024-10-10": "Utamaduni Day",
        "2024-10-21": "Mashujaa Day observed (20 October fell on a Sunday)",
        "2024-12-12": "Jamhuri Day",
        "2024-12-25": "Christmas Day",
        "2024-12-26": "Boxing Day",
    },
    2025: {
        "2025-01-01": "New Year's Day",
        "2025-03-31": "Idd-ul-Fitr (moon-dependent; declared)",
        "2025-04-18": "Good Friday",
        "2025-04-21": "Easter Monday",
        "2025-05-01": "Labour Day",
        "2025-06-02": "Madaraka Day observed (1 June fell on a Sunday)",
        "2025-06-07": "Idd-ul-Azha (moon-dependent; declared)",
        "2025-10-10": "Utamaduni Day",
        "2025-10-20": "Mashujaa Day",
        "2025-12-12": "Jamhuri Day",
        "2025-12-25": "Christmas Day",
        "2025-12-26": "Boxing Day",
    },
    2026: {
        "2026-01-01": "New Year's Day",
        "2026-03-20": "Idd-ul-Fitr (moon-dependent; ESTIMATE, not gazetted)",
        "2026-04-03": "Good Friday",
        "2026-04-06": "Easter Monday",
        "2026-05-01": "Labour Day",
        "2026-05-27": "Idd-ul-Azha (moon-dependent; ESTIMATE, not gazetted)",
        "2026-06-01": "Madaraka Day",
        "2026-10-10": "Utamaduni Day (falls on a Saturday; NOT substituted under the Sunday "
                      "rule)",
        "2026-10-20": "Mashujaa Day",
        "2026-12-12": "Jamhuri Day (falls on a Saturday; NOT substituted under the Sunday rule)",
        "2026-12-25": "Christmas Day",
        "2026-12-26": "Boxing Day",
    },
}

HOLIDAYS_RULE: dict[str, Any] = {
    "rule": (
        "The Public Holidays Act, Cap 110. THREE LAYERS. (1) FIXED GREGORIAN: 1 January, 1 May "
        "(Labour Day), 1 June (MADARAKA DAY, the anniversary of internal self-rule), 10 October, "
        "20 October (Mashujaa Day), 12 December (Jamhuri Day, independence), 25 December and "
        "26 December. (2) MOVEABLE CHRISTIAN: Good Friday and Easter Monday. (3) MOVEABLE "
        "ISLAMIC, DECLARED AND MOON-DEPENDENT: Idd-ul-Fitr and Idd-ul-Azha, gazetted by the "
        "Cabinet Secretary. SUBSTITUTION: section 2(2) moves a public holiday falling on a "
        "SUNDAY to the following Monday; a SATURDAY holiday is NOT substituted, which is why "
        "2026-10-10 and 2026-12-12 stand unsubstituted in the table above. THE 10 OCTOBER "
        "HOLIDAY HAS BEEN RENAMED MORE THAN ONCE -- Moi Day, then Huduma Day, then Utamaduni "
        "Day, with a further legislative change proposed since -- and the pack records the date "
        "with the naming uncertainty rather than asserting one name as settled, because the "
        "DATE is what a calendar study needs and the name is not. The President may also declare "
        "an ad hoc holiday, as has been done for national events, and no rule predicts one."),
    "authority": "the Public Holidays Act Cap 110 and gazette notices by the Cabinet Secretary; "
                 "the NSE publishes its own trading calendar, which follows the Act",
    "table": _KE_HOLIDAYS,
    "status": {
        2024: "GAZETTED for the Gregorian and Christian days; Islamic days as declared",
        2025: "GAZETTED for the Gregorian and Christian days; Islamic days as declared",
        2026: "MIXED. The Gregorian days are statutory and certain; the Christian days follow "
              "from Easter Sunday 2026-04-05. THE ISLAMIC DAYS ARE HIJRI ESTIMATES AND ARE NOT "
              "GAZETTED: they may move by a day in either direction and any event study landing "
              "on one must be re-run against the gazette or reported UNMEASURED.",
    },
    "market_effect": (
        "NOTHING KENYAN IS QUOTED ON THIS ACCOUNT, so a Kenyan holiday is an OBSERVABILITY "
        "OUTAGE and not a liquidity regime: no CBK indicative rate, no NSE flow print, no "
        "auction. A MISSING CBK DAY IS NOT A ZERO AND IS NOT A CALM DAY -- it is UNMEASURED, by "
        "name, and any spread or stress series computed across one must carry the gap "
        "explicitly. The auctions are the sharper case: a public holiday inside an auction week "
        "shifts or cancels the sale, so the weekly export-price series has genuinely missing "
        "weeks that are not low-volume weeks. Meanwhile the carriers -- coffee, Brent, the rand "
        "-- trade through with no Kenyan information arriving."),
    "callable": "countries.ke.pack:holidays",
}


def holidays(year: int) -> dict[str, str]:
    """Kenya's closure table for one year, `{"YYYY-MM-DD": name}`. `{}` if untabulated."""
    return holiday_table(HOLIDAYS_RULE, year)


# --------------------------------------------------------------------------- custom miners
def ke_rain_season(day: str) -> dict[str, Any]:
    """Which East African growing season a date falls in, and what a failure there would mean.

    KENYA HAS TWO RAINY SEASONS AND THAT IS THE WHOLE POINT OF THIS FUNCTION. The LONG RAINS
    (March-May) carry the main crop; the SHORT RAINS (October-December) carry a second, smaller
    one. A single failed season is a bad year with a second chance six months away; a SEQUENCE of
    failed seasons is a categorically different event, and the 2020-2023 drought was five
    consecutive failures. A model that treats rainfall as one annual number cannot represent that
    difference, and the difference is where the whole signal lives.

    Returns the season, the crop it feeds and the lag from that season to the price consequence.
    """
    iso = str(day)[:10]
    try:
        d = date.fromisoformat(iso)
    except ValueError:
        return {"status": "UNMEASURED", "why": "UNPARSEABLE_DATE", "date": iso}
    month = d.month
    if 3 <= month <= 5:
        season, crop, lag = "LONG_RAINS", "the main maize and pulse crop", "harvest from August"
    elif 10 <= month <= 12:
        season, crop, lag = "SHORT_RAINS", "the second, smaller crop", "harvest from February"
    elif month in (1, 2):
        season, crop, lag = "SHORT_RAINS_HARVEST", "the short-rains harvest window", "immediate"
    else:
        season, crop, lag = "LONG_RAINS_HARVEST", "the long-rains harvest window", "immediate"
    return {
        "status": "OK", "date": iso, "season": season, "crop": crop, "price_lag": lag,
        "rule": "long rains March-May, short rains October-December; harvests follow each by "
                "about three months",
        "why_two_seasons_matter": "one failed season is a bad year with a second chance six "
                                  "months away; consecutive failures are a different object "
                                  "entirely, and an annual rainfall aggregate cannot tell them "
                                  "apart",
        "controls": ("the same calendar window in a year with normal rainfall",
                     "the southern African maize belt, which has ONE season and the opposite "
                     "hemisphere's timing -- a control that shares the ENSO driver and not the "
                     "season structure",
                     "randomised season labels"),
    }


def ke_fx_spread_state(buy: float, sell: float, mean: float | None = None) -> dict[str, Any]:
    """The published buy/sell spread in basis points, which is the Kenyan stress observable.

    The mean is what everybody quotes and it is an average of two numbers the central bank
    publishes. THE WIDTH BETWEEN THEM IS THE PRICE OF IMMEDIACY, and in a market the CBK also
    manages it is the part that cannot be set by announcement. A negative or zero width is not a
    tight market, it is a BROKEN ROW, and this function refuses it by name rather than reporting
    a suspiciously good number.
    """
    try:
        b, s = float(buy), float(sell)
    except (TypeError, ValueError):
        return {"status": "UNMEASURED", "why": "NON_NUMERIC", "detail": "buy or sell is not a "
                                                                       "number"}
    m = float(mean) if mean is not None else (b + s) / 2.0
    if m <= 0:
        return {"status": "UNMEASURED", "why": "NON_POSITIVE_MEAN",
                "detail": "a non-positive mean cannot normalise a spread"}
    if s <= b:
        return {"status": "UNMEASURED", "why": "INVERTED_QUOTE",
                "detail": f"sell {s} is not above buy {b}; an inverted or equal quote is a "
                          f"broken row, never a tight market, and is refused rather than "
                          f"reported as zero stress"}
    return {"status": "OK", "buy": b, "sell": s, "mean": m,
            "spread_bps": 10000.0 * (s - b) / m,
            "note": "a WIDENING spread on a STABLE mean is a market clearing at a rate the mean "
                    "does not show -- the Kenyan analogue of a Nigerian turnover collapse"}


CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    miner("ke_rain_season_calendar",
          domain_ids=("ke_rainfall_and_drought", "ke_agricultural_export_cycle"),
          kind="calendar",
          entry="countries.ke.pack:ke_rain_season",
          cadence_s=86400.0,
          steerable=False,
          notes="A fixed cost: the season grid must be read every pass, because a rainfall "
                "regressor that ignores which season it is in cannot distinguish a bad year "
                "from a multi-season failure."),
    miner("ke_fx_spread_state",
          domain_ids=("ke_fx_rate_and_spread", "ke_frontier_stress_transmission"),
          kind="mechanism",
          entry="countries.ke.pack:ke_fx_spread_state",
          cadence_s=3600.0,
          steerable=True,
          notes="Turns the published buy and sell into the one number that carries information. "
                "Refuses inverted quotes by name."),
)


# --------------------------------------------------------------------------- positioning
#: KENYA HAS NO POSITIONING DATA IN THE SENSE SOUTH AFRICA DOES, and this tuple says so by name
#: rather than leaving a field empty. What follows is what stands in, each with its limitation,
#: because a substitute presented without its limitation becomes a claim.
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"id": "cftc_cot_kes",
     "name": "CFTC Commitments of Traders -- Kenyan shilling",
     "availability": "DOES NOT EXIST. No CME shilling contract, therefore no COT report. South "
                     "Africa remains the only country in this African civilization with a "
                     "genuine speculative-positioning series.",
     "covers": "n/a", "frequency": "n/a", "lag": "n/a",
     "root": "cftc.gov (checked; no shilling contract)",
     "licence": "n/a",
     "desk_status": "DECLARED ABSENT. Any positioning miner asked about the shilling reports "
                    "UNMEASURED naming this row."},
    {"id": "nse_foreign_participation",
     "name": "NSE daily foreign investor participation and net flow",
     "covers": "the share of daily turnover attributable to foreign investors, and their net "
               "buy or sell",
     "frequency": "daily", "lag": "same day after the close",
     "root": "nse.co.ke market statistics",
     "licence": "free, public",
     "desk_status": "A free daily foreign-flow series in a frontier market, which is unusual. "
                    "Its weakness is the DENOMINATOR: on a thin day a small absolute flow is a "
                    "large participation share, so the ratio and the level must be read "
                    "together or the series says something it does not mean."},
    {"id": "cbk_interbank_volume",
     "name": "CBK interbank FX volume and rate, from the weekly bulletin",
     "covers": "interbank turnover and the rate at which it traded",
     "frequency": "weekly", "lag": "about one week",
     "root": "centralbank.go.ke weekly bulletin",
     "licence": "free, public",
     "desk_status": "THE VOLUME IS THE CHECK ON THE RATE and it is the series that made the "
                    "2022-2023 divergence visible. Weekly resolution is its limitation: it "
                    "cannot anchor a daily event study."},
    {"id": "cbk_reserves_import_cover",
     "name": "usable foreign exchange reserves and months of import cover",
     "covers": "the reserve stock and the CBK's own adequacy metric",
     "frequency": "weekly", "lag": "about one week",
     "root": "centralbank.go.ke weekly bulletin",
     "licence": "free, public",
     "desk_status": "IMPORT COVER IS A GENUINELY GOOD STATE VARIABLE because it is the number "
                    "the central bank is accountable for against a statutory floor -- a "
                    "published target makes the authority's reaction function observable."},
    {"id": "foreign_holdings_govt_securities",
     "name": "non-resident holdings of Kenyan government securities",
     "covers": "the stock of foreign-held domestic debt",
     "frequency": "monthly to quarterly", "lag": "several weeks",
     "root": "CBK and National Treasury debt publications",
     "licence": "free, public",
     "desk_status": "Kenya's foreign holding of domestic debt is SMALL relative to peers, which "
                    "is itself the finding: the shilling is driven by the EXTERNAL funding "
                    "calendar and the trade account far more than by portfolio flow. That is "
                    "the opposite of South Africa and it changes which mechanisms can exist."},
    {"id": "safaricom_mpesa_statistics",
     "name": "mobile-money transaction values, volumes and agent counts",
     "covers": "national mobile-money activity, published by the CBK's national payments "
               "statistics and in the operator's own public results",
     "frequency": "monthly (CBK) and semi-annual (operator results)",
     "lag": "about one month",
     "root": "centralbank.go.ke national payments system statistics",
     "licence": "free, public",
     "desk_status": "A REAL-ECONOMY LIQUIDITY OBSERVABLE, and the closest thing to a "
                    "high-frequency activity index Kenya publishes -- mobile money is a very "
                    "large share of Kenyan transactions, so its value is closer to a measure of "
                    "the economy than a payments statistic usually is. THE OPERATOR IS A LISTED "
                    "SINGLE NAME AND IS REFUSED AS A DOCKET SYMBOL under the two-lane order "
                    "(2026-09-06): it is an observable and never a hypothesis."},
)


# --------------------------------------------------------------------------- terminology
#: NATIVE TERMS, KEYED BY DOMAIN. English is an official language and carries the financial
#: press; SWAHILI carries the food-price, rainfall and political coverage, and it carries them
#: FIRST. The price of `unga` -- maize flour -- is a political variable in Kenya, discussed in
#: Swahili in the constituencies weeks before it reaches an English-language market note, and a
#: miner that only reads English learns about a food-price crisis from its consequences.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "core": ("shilingi", "dola", "pesa", "bei", "soko", "fedha", "thamani", "shilling",
             "exchange rate", "the shilling"),
    "ke_fx_rate_and_spread": ("benki kuu", "kiwango cha ubadilishaji", "kununua", "kuuza",
                              "tofauti ya bei", "Central Bank Rate", "indicative rate", "buy",
                              "sell", "mean", "spread", "interbank", "dollar shortage",
                              "shilling weakens", "shilling gains"),
    "ke_reserve_adequacy": ("akiba ya fedha za kigeni", "miezi ya uagizaji", "reserves",
                            "import cover", "usable reserves", "statutory floor", "IMF"),
    "ke_external_debt_calendar": ("deni", "deni la nje", "hazina", "eurobond", "buyback",
                                  "maturity", "default", "restructuring", "Treasury",
                                  "syndicated loan"),
    "ke_oil_import_bill": ("mafuta", "petroli", "dizeli", "bei ya mafuta", "uagizaji wa mafuta",
                           "fuel import", "EPRA", "pump price", "G2G arrangement",
                           "oil import bill", "fuel levy"),
    "ke_agricultural_export_cycle": ("chai", "kahawa", "maua", "mazao ya kuuza nje", "wakulima",
                                     "mavuno", "tea", "coffee", "horticulture", "cut flowers",
                                     "KTDA", "smallholder", "auction", "export earnings"),
    "ke_tea_auction": ("mnada wa chai", "Mombasa", "chai", "bei ya chai", "KTDA", "EATTA",
                       "tea auction", "lots offered", "lots sold", "average price",
                       "unsold percentage"),
    "ke_coffee_auction": ("mnada wa kahawa", "kahawa", "vyama vya ushirika", "Nairobi Coffee "
                          "Exchange", "cooperative", "AA grade", "auction price", "cherry price"),
    "ke_rainfall_and_drought": ("mvua", "mvua ndefu", "mvua fupi", "ukame", "njaa", "mazao",
                                "long rains", "short rains", "drought", "failed season",
                                "FEWS NET", "food insecurity", "ASAL", "El Nino", "La Nina"),
    "ke_food_price_politics": ("unga", "bei ya unga", "ruzuku", "mahindi", "njaa", "gharama ya "
                               "maisha", "maize flour", "subsidy", "cost of living",
                               "price controls", "maize imports"),
    "ke_transit_corridor_logistics": ("bandari", "Mombasa", "reli", "usafirishaji", "mizigo",
                                      "port", "northern corridor", "SGR", "container",
                                      "dwell time", "transit cargo", "Uganda", "Rwanda"),
    "ke_mobile_money_liquidity": ("M-Pesa", "pesa mkononi", "wakala", "malipo", "mobile money",
                                  "agent", "transaction value", "payments", "float"),
    "ke_frontier_stress_transmission": ("soko linaloibukia", "hatari", "frontier market",
                                        "emerging market", "spread", "sovereign risk",
                                        "credit rating", "IMF programme"),
    "ke_policy_reaction": ("kamati ya sera za fedha", "riba", "mfumuko wa bei", "MPC", "CBR",
                           "Cash Reserve Ratio", "inflation", "policy rate", "tightening"),
    "ke_fiscal_and_protest": ("bajeti", "kodi", "mswada wa fedha", "maandamano", "Finance Bill",
                              "budget", "tax", "protest", "withdrawn", "austerity"),
}


# --------------------------------------------------------------------------- source classes
#: THE TEN LAYERS (principal's per-country depth rule, 2026-09-17). Exactly one per source, and
#: every layer either covered or DECLARED ABSENT WITH A REASON -- never blank. In Kenya the rule
#: buys something specific: the official layer publishes a rate and a CPI, and the SWAHILI retail
#: and media layers publish the price of unga and the state of the rains, which is where the
#: food-price and drought signal actually lives and where it appears FIRST.
LAYERS: tuple[str, ...] = ("official", "institutional", "academic", "practitioner",
                           "retail_ecology", "app_ecosystem", "media", "archive",
                           "physical_economy", "source_graph")

#: HOW THE DESK IS ALLOWED TO TOUCH IT. Separate from credibility on purpose.
ACCESS_LABELS: tuple[str, ...] = ("PUBLIC", "PUBLIC_WITH_TERMS", "LICENSED", "OPEN_DATA",
                                  "PUBLIC_ARCHIVE", "PUBLIC_SOCIAL", "USER_SUBMITTED",
                                  "ACCESS_UNCLEAR", "PRIVATE", "CONFIDENTIAL_MNPI",
                                  "STOLEN_UNAUTHORIZED")

#: WHETHER TO BELIEVE IT. `FRINGE` and `CONTRADICTED` are KEPT, never dropped.
CREDIBILITY: tuple[str, ...] = ("AUTHORITATIVE", "RELIABLE", "UNRELIABLE", "FRINGE",
                                "CONTRADICTED", "UNKNOWN")

#: WHETHER IT HAS EVER PREDICTED ANYTHING ON THIS BOX. Every row starts UNTESTED.
PREDICTIVE_STATES: tuple[str, ...] = ("UNTESTED", "PREDICTIVE", "NOT_PREDICTIVE",
                                      "NARRATIVE_FEATURE")


def _src(sid: str, label: str, *, layer: str, roots: Any, languages: Any, licence: str,
         access_label: str, credibility: str, predictive_state: str, queries: Any,
         machine_use_allowed: bool = True, notes: str = "") -> dict[str, Any]:
    """`source_class()` plus the principal's five labels, with the enums checked on the way in.

    A MISLABELLED SOURCE IS WORSE THAN AN UNLABELLED ONE, because a wrong label is read as a
    measurement. `queries` are NATIVE-LANGUAGE and are not translations: a Kenyan constituency
    does not discuss "staple food price inflation", it discusses "bei ya unga", and a farmer does
    not discuss "seasonal rainfall onset", he discusses "mvua za masika".
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
    _src("ke_official_cb", "The Central Bank of Kenya",
         layer="official",
         roots=("centralbank.go.ke",
                "centralbank.go.ke/rates/forex-exchange-rates/",
                "centralbank.go.ke/publications/weekly-bulletin/",
                "centralbank.go.ke/monetary-policy-committee/",
                "centralbank.go.ke/national-payments-system/mobile-payments/",
                "centralbank.go.ke/diaspora-remittances/"),
         languages=("en", "sw"),
         licence="free, public; the daily rates are served as a downloadable table",
         access_label="OPEN_DATA", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         queries=("CBK indicative exchange rate buy sell mean", "kiwango cha ubadilishaji leo",
                  "usable foreign exchange reserves months of import cover",
                  "riba ya benki kuu", "MPC press release Central Bank Rate",
                  "diaspora remittances monthly Kenya"),
         notes="THE DAILY BUY/SELL/MEAN TABLE IS THE PACK'S FLAGSHIP ROUTE. Free, daily, many "
               "currencies, and the SPREAD it publishes is the part that carries information -- "
               "which is why the plane computes it in basis points on every row rather than "
               "storing the mean everyone else stores."),
    _src("ke_official_stats", "KNBS, the National Treasury and Parliament",
         layer="official",
         roots=("knbs.or.ke", "knbs.or.ke/all-reports/", "treasury.go.ke",
                "parliament.go.ke (the Finance Bill and budget documents)",
                "epra.go.ke (the energy regulator's monthly pump-price determination)"),
         languages=("en",),
         licence="free, public",
         access_label="OPEN_DATA", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         queries=("KNBS CPI monthly release", "KNBS leading economic indicators",
                  "EPRA maximum retail petroleum prices", "Finance Bill 2024 schedule",
                  "Kenya public debt register external"),
         notes="EPRA IS THE UNDERRATED ROW. Kenya's pump price is set by a published monthly "
               "formula, so the pass-through from Brent and the shilling into the domestic fuel "
               "price is not estimated -- it is PUBLISHED, with its inputs. Very few countries "
               "hand a researcher the pass-through equation."),
    _src("ke_exchange", "The Nairobi Securities Exchange",
         layer="institutional",
         roots=("nse.co.ke", "nse.co.ke/market-statistics/", "nse.co.ke/dataservices/",
                "cma.or.ke (the Capital Markets Authority's quarterly statistical bulletin)"),
         languages=("en",),
         licence="free public summary tables; real-time data is a licensed product and is never "
                 "scraped or redistributed",
         access_label="PUBLIC_WITH_TERMS", credibility="AUTHORITATIVE",
         predictive_state="UNTESTED",
         queries=("NSE daily foreign investor participation", "NSE equity turnover daily",
                  "CMA quarterly statistical bulletin", "NSE 20 share index close"),
         notes="A free daily foreign-flow series in a frontier market, which is unusual. READ "
               "THE RATIO AND THE LEVEL TOGETHER: on a thin day a small absolute flow is a large "
               "participation share, and the ratio alone then says something it does not mean."),
    _src("ke_regional_bodies", "East African Community institutions and the corridor authority",
         layer="institutional",
         roots=("eac.int", "eabc.info", "ttcanc.org (the Northern Corridor observatory)",
                "afdb.org", "comesa.int", "icpac.net (the IGAD climate prediction centre)"),
         languages=("en", "sw", "fr"),
         licence="free, public",
         access_label="PUBLIC", credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("Northern Corridor transit time Mombasa Kampala", "EAC trade statistics "
                  "quarterly", "ICPAC seasonal rainfall forecast Greater Horn",
                  "container dwell time Mombasa port"),
         notes="THE NORTHERN CORRIDOR OBSERVATORY PUBLISHES TRANSIT TIMES AND VOLUMES for the "
               "Mombasa-Kampala-Kigali route, which is a REGIONAL trade observable that happens "
               "to be published in Kenya. ICPAC is the regional climate authority and its "
               "seasonal forecast is the forward-looking leg of the weather family."),
    _src("ke_academic", "Kenyan and East African academic and policy literature",
         layer="academic",
         roots=("kippra.or.ke", "centralbank.go.ke working papers", "aercafrica.org",
                "papers.ssrn.com (East African FX and agricultural price studies)",
                "repository.uonbi.ac.ke", "tegemeo.egerton.ac.ke (agricultural policy)"),
         languages=("en",),
         licence="mixed; institutional repositories open, journals often licensed. Never scrape "
                 "a paywall",
         access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("maize price transmission Kenya market integration",
                  "exchange rate pass-through Kenya inflation",
                  "tea auction price formation Mombasa", "drought impact household consumption "
                  "Kenya", "mobile money economic activity Kenya"),
         notes="TEGEMEO IS THE SPECIALIST ROW: an agricultural policy institute with decades of "
               "household and market-price panel work on Kenyan maize, which is the best "
               "external check on this pack's food-price mechanism. The AERC literature on East "
               "African commodity price transmission is the check on the auction mechanisms."),
    _src("ke_practitioner", "Kenyan professional market commentary and local research",
         layer="practitioner",
         roots=("kenyanwallstreet.com", "businessdailyafrica.com/bd/markets",
                "cytonn.com and comparable local weekly research notes",
                "genghis-capital and sterling-capital public market reports",
                "africanfinancials.com (public filings aggregation)"),
         languages=("en",),
         licence="public web; mined for VERBATIM CLAIMS only, never for advice",
         access_label="PUBLIC", credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("shilling outlook after MPC", "Kenya eurobond buyback analysis",
                  "T-bill auction subscription rate weekly", "interbank rate Kenya commentary",
                  "tea earnings outlook Kenya"),
         notes="The local weekly research notes are the routine publishers of the T-bill "
               "subscription rate and the interbank volume in a readable form, which makes them "
               "a practical cross-check on the CBK bulletin's shape after a site change."),
    _src("ke_retail_ecology", "Kenyan boards and the crowd, in Swahili and English",
         layer="retail_ecology",
         roots=("wazua.co.ke (the long-running Kenyan investment forum)",
                "reddit.com/r/Kenya (economy and cost-of-living threads)",
                "public X/Twitter threads on the shilling and the price of unga",
                "public Facebook group discussion of farm-gate and market prices, described "
                "generically"),
         languages=("sw", "en"),
         licence="public web; mined for VERBATIM CLAIMS only, never for personal data and never "
                 "for advice",
         access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
         predictive_state="NARRATIVE_FEATURE",
         queries=("bei ya unga leo", "shilingi imeshuka", "gharama ya maisha Kenya",
                  "mvua hazijanyesha", "bei ya mahindi sokoni", "dola ngapi leo"),
         notes="LOW WEIGHT, NEVER DROPPED. THE PRICE OF UNGA IS A POLITICAL VARIABLE IN KENYA "
               "and it is discussed in Swahili in the constituencies weeks before it reaches an "
               "English-language market note. A miner that reads only English learns about a "
               "food-price crisis from its consequences. This layer is also where the retail "
               "read on the shilling lives, which is the only retail FX observable Kenya has -- "
               "there is no parallel market to quote, because the wedge is small."),
    _src("ke_retail_fringe", "Fringe, contradicted and scam-adjacent public material",
         layer="retail_ecology",
         roots=("CBK and CMA public warnings on unlicensed forex and investment schemes",
                "pyramid and 'online forex' scheme collapse post-mortems",
                "public complaint threads about digital-lending apps and their rates",
                "'shilling to 200' and imminent-default prediction threads"),
         languages=("sw", "en"),
         licence="public web; verbatim claims only, no personal data, no re-publication",
         access_label="PUBLIC_SOCIAL", credibility="FRINGE",
         predictive_state="NARRATIVE_FEATURE",
         queries=("CBK warning unlicensed forex broker", "onyo kuhusu mtandao wa pesa",
                  "Kenya default eurobond prediction", "forex scam Kenya warning",
                  "digital lender interest complaint"),
         notes="KEPT ON PURPOSE AND WEIGHTED NEAR ZERO. The 2023-2024 default predictions are "
               "the canonical Kenyan case: the market priced a disorderly maturity, the crowd "
               "said so loudly, and the buyback proved them wrong -- WHICH DOES NOT MAKE THE "
               "RECORD WORTHLESS, it makes it a measurement of the expectation the buyback "
               "surprised. Scheme collapses and lending-app complaints are evidence about the "
               "plumbing: which channels retail actually uses and where the friction is."),
    _src("ke_app_ecosystem", "The apps Kenyans hold, move and price money in",
         layer="app_ecosystem",
         roots=("public mobile-money tariff and transaction-limit pages (the operators publish "
                "their charge schedules)",
                "hisa, ndovu, chumz and comparable retail investing apps and their public fee "
                "and rate pages",
                "tala, branch and comparable digital-lending apps' public terms and rates",
                "sendwave, worldremit and remitly public corridor rates for Kenya",
                "app store and play store listings and public release notes for the above"),
         languages=("en", "sw"),
         licence="public listings, tariff schedules and documentation; no account creation, no "
                 "scraping behind a login, no personal data",
         access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("M-Pesa tariff schedule charges", "viwango vya M-Pesa",
                  "Sendwave Kenya rate today", "WorldRemit KES rate", "Hisa app fees",
                  "Tala loan interest rate Kenya"),
         notes="A LAYER THAT MATTERS FAR MORE IN KENYA THAN ANYWHERE ELSE IN THIS CIVILIZATION. "
               "Mobile money carries a very large share of Kenyan transaction value, so the "
               "TARIFF SCHEDULE is a real cost-of-transacting series and a change to it is a "
               "dated shock to the payments rail. The remittance-corridor apps post the rate at "
               "which the diaspora actually converts, which is the retail leg of the pack's "
               "largest and most stable FX inflow. THE MOBILE-MONEY OPERATOR IS A LISTED SINGLE "
               "NAME: its statistics and tariffs are OBSERVABLES and it is never a docket symbol "
               "(two-lane order 2026-09-06)."),
    _src("ke_media", "Kenyan press, including the Swahili daily",
         layer="media",
         roots=("nation.africa/kenya/business", "standardmedia.co.ke/business",
                "the-star.co.ke/business", "citizen.digital/business", "kbc.co.ke",
                "taifaleo.nation.co.ke (the Swahili-language daily)",
                "bbc.com/swahili (economy coverage)"),
         languages=("sw", "en"),
         licence="public headlines and article text; respect robots and rate limits",
         access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("bei ya unga yapanda", "serikali yapunguza bei ya mafuta",
                  "mvua za masika zimechelewa", "mnada wa chai Mombasa bei",
                  "shilingi yaimarika dhidi ya dola", "ukame Kenya mifugo"),
         notes="TAIFA LEO IS THE ROW THAT JUSTIFIES THE BILINGUAL TERMINOLOGY TABLE. The Swahili "
               "daily and BBC Swahili carry the food-price, rainfall and livestock-condition "
               "coverage in the language it is reported in, and they carry it before the English "
               "business desks pick it up as a macro story."),
    _src("ke_terms_restricted", "Sources whose terms forbid machine extraction",
         layer="media",
         roots=("the NSE real-time market data feed and its redistribution licence",
                "subscription-only research portals covering East African fixed income whose "
                "terms of use forbid automated access",
                "paywalled international press archives covering Kenyan policy",
                "commercial tea and coffee price-reporting services"),
         languages=("en",),
         licence="LICENSED or PUBLIC_WITH_TERMS where the terms explicitly forbid automated "
                 "extraction",
         access_label="ACCESS_UNCLEAR", credibility="RELIABLE", predictive_state="UNTESTED",
         machine_use_allowed=True,
         queries=("(none -- this row is REGISTERED AND NEVER QUERIED)",),
         notes="REGISTERED, NEVER SCRAPED, NEVER OMITTED. machine_use_allowed=True is the whole "
               "content of this row. The commercial tea price-reporting services are the "
               "painful member of this class: THEY WOULD CLOSE THE PACK'S LARGEST DECLARED GAP "
               "and their terms do not permit it, so the gap stays open and is named. Omitting "
               "the row would make the refusal invisible and would let a later session "
               "'discover' the source and quietly breach the terms. ACCESS_UNCLEAR rather than "
               "LICENSED because the class is heterogeneous and some members' terms have not "
               "been individually read; AN UNREAD TERM IS NOT A PERMISSION."),
    _src("ke_archive", "Back editions, superseded bulletins and captures of moved pages",
         layer="archive",
         roots=("centralbank.go.ke weekly bulletin archive (back editions)",
                "knbs.or.ke statistical abstract and economic survey archive",
                "web.archive.org captures of the CBK forex-rates page",
                "fews.net archived outlooks by season",
                "treasury.go.ke budget policy statement archive"),
         languages=("en",),
         licence="free, public archives",
         access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         queries=("CBK weekly bulletin archive 2022", "KNBS economic survey archive",
                  "FEWS NET Kenya outlook archived season", "web archive centralbank.go.ke "
                  "forex rates", "Kenya budget policy statement historical"),
         notes="THE LAYER THAT MAKES THE 2022-2023 DIVERGENCE MEASURABLE AT ALL. The episode "
               "where the published rate and the transactable rate came apart is only visible "
               "by comparing what the CBK page said at the time against what the bulletin's "
               "interbank volume said in the same week -- and a live page shows neither. FEWS "
               "NET outlooks are SUPERSEDED rather than revised, so the archive is the only way "
               "to know what was FORECAST when, which is the whole point of a forward-looking "
               "series."),
    _src("ke_physical_economy", "Auctions, rainfall, ports and the physical crop",
         layer="physical_economy",
         roots=("eatta.co.ke (Mombasa tea auction weekly reports)",
                "nairobicoffeeexchange.co.ke", "afa.go.ke", "teaboard.or.ke", "ktdateas.com",
                "kpa.co.ke (Kenya Ports Authority throughput)",
                "meteo.go.ke", "chc.ucsb.edu (CHIRPS gridded rainfall)",
                "fews.net/east-africa", "ndma.go.ke (drought early warning bulletins)"),
         languages=("en", "sw"),
         licence="free, public; the auctions publish weekly reports and CHIRPS is open research "
                 "data",
         access_label="OPEN_DATA", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         queries=("Mombasa tea auction lots offered sold average price",
                  "mnada wa chai bei ya wastani", "Nairobi Coffee Exchange auction results",
                  "CHIRPS rainfall anomaly Kenya dekadal", "NDMA drought bulletin county",
                  "Mombasa port throughput TEUs"),
         notes="THE LAYER WITH THE CLEANEST IDENTIFICATION IN THE WHOLE CIVILIZATION. Rainfall "
               "cannot be affected by the market that trades on it, which removes the "
               "reverse-causality problem that contaminates every FX and production series here. "
               "THE TEA AUCTION'S UNSOLD PERCENTAGE is the most informative column and the one "
               "most often ignored: it is a demand signal the average price hides. The desk "
               "cannot trade tea and conditions on it anyway."),
    _src("ke_source_graph", "How new Kenyan sources are found, and what is refused",
         layer="source_graph",
         roots=("citation and data-annex trails in IMF Article IV Kenya staff reports",
                "World Bank Kenya Economic Update reference lists",
                "reference lists in KIPPRA and Tegemeo working papers",
                "outbound link graphs from centralbank.go.ke and knbs.or.ke",
                "opendata.go.ke", "the desk's own frontier map in desks/mt5/data/"),
         languages=("en",),
         licence="free, public",
         access_label="PUBLIC", credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("IMF Article IV Kenya statistical annex", "World Bank Kenya Economic Update",
                  "KIPPRA discussion paper references", "opendata.go.ke dataset catalogue"),
         notes="THE META-LAYER, AND THE ONE THAT KEEPS THE OTHER NINE FROM GOING STALE. IMF "
               "staff reports are the highest-yield entry point: for Kenya they routinely "
               "publish external-position and reserve detail the authorities do not, AND their "
               "review dates are themselves an event grid this pack trades off. THIS ROW ALSO "
               "CARRIES THE REFUSALS: (1) any crypto-exchange venue order book, API or native "
               "feed is REFUSED (universe mandate 2026-08-18) and the executable leg of any "
               "retail risk-appetite observable is the broker's own crypto CFD; (2) single-name "
               "NSE hypothesis mining is REFUSED (two-lane order 2026-09-06), AND THE "
               "MOBILE-MONEY OPERATOR IS NAMED EXPLICITLY because its statistics are the pack's "
               "best liquidity observable and it is also a listed company -- an OBSERVABLE, "
               "NEVER A SYMBOL; (3) redistribution of any licensed NSE real-time feed or "
               "commercial tea price service is REFUSED, and is registered as its own row above "
               "rather than omitted."),
)

#: EVERY LAYER ACCOUNTED FOR, BY NAME. Derived from the rows above rather than typed, so it
#: cannot drift from them.
SOURCE_LAYER_COVERAGE: dict[str, str] = {
    layer: (", ".join(s["id"] for s in SOURCE_CLASSES if s["layer"] == layer)
            or f"ABSENT: no {layer} source declared for {NAME}")
    for layer in LAYERS
}


# --------------------------------------------------------------------------- datasets

DATASETS: tuple[dict[str, Any], ...] = (
    dataset("ke_cbk_daily_fx",
            source="CBK daily indicative exchange rates (buy, sell and mean by currency)",
            coverage="daily buying, selling and mean rates across the major and regional "
                     "currencies",
            frequency="daily",
            publication_lag_days=1.0,
            revisions="a published daily rate is not revised; the EXPORT'S HEADER SPELLING HAS "
                      "VARIED between site versions, which is a shape change rather than a "
                      "revision and is what the plane's tolerant parser exists for",
            licence="free, public",
            history_from="the portal serves a selectable date range covering many years",
            pit_feasible=True,
            assets=("USDZAR", "USDTRY", "EURUSD"),
            mechanism_families=("fx_regime_sensor", "liquidity_stress"),
            how_to_fetch="the CBK forex page serves a date-ranged export; parse buy, sell and "
                         "mean per currency and compute the spread in basis points, which is "
                         "the observable the mean hides"),
    dataset("ke_cbk_weekly_bulletin",
            source="CBK Weekly Bulletin",
            coverage="usable reserves, months of import cover, interbank rates and volumes, "
                     "money market indicators, and the CBK's own commentary",
            frequency="weekly",
            publication_lag_days=7.0,
            revisions="restated occasionally as monthly data supersedes weekly estimates",
            licence="free, public",
            history_from="2000s",
            pit_feasible=True,
            assets=("USDZAR", "UST10Y", "XBRUSD"),
            mechanism_families=("fx_regime_sensor", "sovereign_stress"),
            how_to_fetch="the weekly PDF; vault each edition so the interbank-volume series "
                         "survives a site redesign"),
    dataset("ke_cbk_mpc",
            source="CBK Monetary Policy Committee press releases and meeting calendar",
            coverage="the Central Bank Rate decision, the CRR and the committee's reasoning",
            frequency="roughly bi-monthly",
            publication_lag_days=0.0,
            revisions="not revised",
            licence="free, public",
            history_from="2000s",
            pit_feasible=True,
            assets=("USDZAR", "UST10Y"),
            mechanism_families=("policy_reaction", "macro_surprise"),
            how_to_fetch="the MPC page; RECORD THE OBSERVED PUBLICATION TIMESTAMP -- the "
                         "calendar gives the date and the release minute is what an event study "
                         "needs"),
    dataset("ke_cbk_mobile_payments",
            source="CBK national payments system, mobile-money statistics",
            coverage="monthly transaction value and volume, agent and customer counts",
            frequency="monthly",
            publication_lag_days=30.0,
            revisions="occasionally restated",
            licence="free, public",
            history_from="2007, from the launch of mobile money",
            pit_feasible=True,
            assets=("USDZAR",),
            mechanism_families=("local_market_ecology", "activity_nowcast"),
            how_to_fetch="the CBK payments statistics tables. A REAL-ECONOMY ACTIVITY SERIES "
                         "rather than a payments footnote, because mobile money carries a very "
                         "large share of Kenyan transactions"),
    dataset("ke_knbs_cpi",
            source="KNBS consumer price index",
            coverage="headline, food and core inflation, monthly, with a basket breakdown",
            frequency="monthly",
            publication_lag_days=1.0,
            revisions="rarely revised; the basket is periodically rebased, which is a series "
                      "break declared as an era",
            licence="free, public",
            history_from="2009 for the current basket definition",
            pit_feasible=True,
            assets=("CORN", "WHEAT", "USDZAR"),
            mechanism_families=("macro_surprise", "policy_reaction", "weather_agriculture"),
            how_to_fetch="KNBS publishes CPI at the very end of the reference month, which is an "
                         "unusually short lag; record the release timestamp"),
    dataset("ke_knbs_trade",
            source="KNBS foreign trade and balance of payments statistics",
            coverage="exports and imports by product and partner, and the trade balance",
            frequency="monthly to quarterly",
            publication_lag_days=60.0,
            revisions="revised across editions",
            licence="free, public",
            history_from="2000s",
            pit_feasible=True,
            assets=("XBRUSD", "COFARA", "EURUSD"),
            mechanism_families=("trade_shipping_logistics", "terms_of_trade"),
            how_to_fetch="the KNBS leading economic indicators and the statistical abstract; the "
                         "OIL IMPORT LINE is the single most useful row for this pack"),
    dataset("ke_nse_daily",
            source="NSE daily market statistics and foreign participation",
            coverage="turnover, index levels and the foreign-investor share and net flow",
            frequency="daily",
            publication_lag_days=0.5,
            revisions="occasionally restated for late reporting",
            licence="free, public summary tables",
            history_from="2010s",
            pit_feasible=True,
            assets=("USDZAR",),
            mechanism_families=("local_market_ecology", "portfolio_flow"),
            how_to_fetch="the NSE market statistics page after the 12:00 UTC close; READ THE "
                         "RATIO AND THE LEVEL TOGETHER"),
    dataset("ke_tea_auction",
            source="East African Tea Trade Association, Mombasa auction weekly reports",
            coverage="lots offered, lots sold, the unsold percentage and average price by grade",
            frequency="weekly",
            publication_lag_days=3.0,
            revisions="not revised",
            licence="free, public weekly reports",
            history_from="2000s",
            pit_feasible=True,
            assets=("USDZAR", "COFARA"),
            mechanism_families=("weather_agriculture", "terms_of_trade"),
            how_to_fetch="the EATTA weekly auction report. THE DESK CANNOT TRADE TEA and this "
                         "series is a CONDITIONING OBSERVABLE for Kenyan export earnings and FX "
                         "supply, never a price leg. The UNSOLD PERCENTAGE is the most "
                         "informative column and the one most often ignored: it is a demand "
                         "signal that the average price hides."),
    dataset("ke_coffee_auction",
            source="Nairobi Coffee Exchange weekly auction",
            coverage="volumes and prices by grade at the weekly sale",
            frequency="weekly",
            publication_lag_days=3.0,
            revisions="not revised",
            licence="free, public",
            history_from="2010s",
            pit_feasible=True,
            assets=("COFARA",),
            mechanism_families=("weather_agriculture", "terms_of_trade"),
            how_to_fetch="the exchange's weekly market report. Kenya is a SMALL share of world "
                         "Arabica, so this informs the QUALITY PREMIUM and regional supply, not "
                         "the global price level, and the pack refuses to claim otherwise"),
    dataset("ke_fewsnet_east_africa",
            source="FEWS NET East Africa food security outlooks and rainfall monitoring",
            coverage="seasonal rainfall performance, crop condition, food-security phase "
                     "classification by region, and FORWARD-LOOKING outlooks",
            frequency="monthly, with seasonal outlooks",
            publication_lag_days=10.0,
            revisions="outlooks are superseded rather than revised, so a vintage store is the "
                      "only way to know what was forecast when",
            licence="free, public",
            history_from="2000s",
            pit_feasible=True,
            assets=("CORN", "WHEAT", "SUGAR", "COFARA"),
            mechanism_families=("weather_agriculture", "supply_shock"),
            how_to_fetch="fews.net East Africa; THE OUTLOOK IS FORWARD-LOOKING, which almost no "
                         "other agricultural data is, and that is what makes it worth a vintage "
                         "store"),
    dataset("ke_rainfall_chirps",
            source="CHIRPS gridded rainfall (Climate Hazards Center) and the Kenya "
                   "Meteorological Department seasonal forecasts",
            coverage="gridded rainfall estimates and official seasonal forecasts",
            frequency="dekadal (ten-day) and seasonal",
            publication_lag_days=10.0,
            revisions="preliminary estimates are replaced by final ones, which IS a revision and "
                      "needs a vintage",
            licence="free, public research data",
            history_from="1981 for CHIRPS",
            pit_feasible=True,
            assets=("CORN", "WHEAT", "COFARA"),
            mechanism_families=("weather_agriculture",),
            how_to_fetch="CHIRPS serves gridded files; the desk stores the regional aggregate "
                         "for the Kenyan and southern-African cropping zones and keeps the "
                         "preliminary and final vintages separately"),
    dataset("ke_northern_corridor",
            source="the Northern Corridor Transit and Transport Coordination Authority "
                   "observatory, plus Kenya Ports Authority statistics",
            coverage="transit times, container dwell time, port throughput and rail volumes on "
                     "the Mombasa-to-Kampala-to-Kigali route",
            frequency="monthly to quarterly",
            publication_lag_days=45.0,
            revisions="irregular publication is itself the problem; a missing month is NOT a "
                      "zero",
            licence="free, public",
            history_from="2010s",
            pit_feasible=False,
            assets=("XBRUSD", "CORN", "USDZAR"),
            mechanism_families=("trade_shipping_logistics",),
            how_to_fetch="the observatory's periodic reports; marked NOT_PIT_SAFE because "
                         "publication is irregular and the vintage cannot be reconstructed for "
                         "older periods"),
    dataset("ke_treasury_debt",
            source="National Treasury and CBK public debt register and issuance calendar",
            coverage="external and domestic debt stock, eurobond maturities and buybacks, "
                     "syndicated loans",
            frequency="monthly stock, weekly domestic auctions",
            publication_lag_days=30.0,
            revisions="restated across editions",
            licence="free, public",
            history_from="2010s",
            pit_feasible=True,
            assets=("UST10Y", "UKGILT", "USDZAR"),
            mechanism_families=("sovereign_stress", "frontier_transmission"),
            how_to_fetch="the Treasury's debt bulletins; THE EUROBOND MATURITY CALENDAR is the "
                         "scheduled-risk object and the 2024 buyback is its canonical episode"),
)


# --------------------------------------------------------------------------- actors
ACTORS: tuple[dict[str, Any], ...] = (
    actor("Central Bank of Kenya",
          holds="usable foreign exchange reserves, the Central Bank Rate and the indicative "
                "rate it publishes",
          forced_to=("hold reserves above a statutory months-of-import-cover floor",
                     "publish a daily indicative rate whether or not the interbank market is "
                     "clearing",
                     "choose between defending the shilling and preserving cover"),
          when="MPC roughly bi-monthly; the indicative rate every business day; the bulletin "
               "weekly",
          information=("import cover", "the interbank rate and volume", "inflation",
                       "the external funding calendar"),
          constraints=("the statutory cover floor, which is a PUBLISHED target and therefore "
                       "makes its reaction function observable",
                       "an import bill dominated by oil that does not fall when the currency "
                       "does",
                       "an IMF programme with review conditions"),
          instruments=("USDZAR", "UST10Y", "XBRUSD"),
          counterparties=("Kenyan commercial banks", "the National Treasury", "the IMF"),
          observables=("the daily buy/sell/mean and its spread", "weekly reserves and cover",
                       "interbank volume", "MPC statements"),
          impact="the published SPREAD widens before the mean moves, so the CBK's own daily "
                 "release carries a leading indicator of its own regime",
          persistence="structural; the cover floor has bound repeatedly",
          falsifier="if the published buy/sell spread has no predictive content for subsequent "
                    "moves in the mean, controlling for the global dollar, then the spread is a "
                    "posted convention rather than a price and the pack's flagship observable "
                    "is empty",
          notes="THE PACK'S MOST TESTABLE CLAIM, and the one that would most cleanly kill the "
                "pack's Tier ranking if it failed."),
    actor("The National Treasury and the external funding calendar",
          holds="the sovereign's eurobond maturities, syndicated loans and domestic issuance",
          forced_to=("refinance a known maturity on a known date",
                     "publish a budget in June for a July start",
                     "meet IMF review conditions to unlock disbursements"),
          when="the maturity calendar is known years ahead; reviews are scheduled",
          information=("market access and its price", "revenue collection", "the debt path"),
          constraints=("a maturity wall the market can see",
                       "IMF conditionality", "domestic political limits on taxation"),
          instruments=("UST10Y", "UKGILT", "USDZAR"),
          counterparties=("eurobond holders", "syndicated lenders", "the IMF"),
          observables=("the maturity calendar", "buyback and issuance announcements",
                       "IMF review outcomes", "the eurobond spread"),
          impact="THE 2024 BUYBACK IS THE CANONICAL EPISODE: a sovereign the market had priced "
                 "for a disorderly maturity bought back a large part of it, and the shilling "
                 "then appreciated sharply. Frontier FX is priced off the EXTERNAL FUNDING "
                 "CALENDAR far more than off the current account, and Kenya proved it on a date.",
          persistence="the calendar is structural; the market's reaction to it is regime-"
                      "dependent",
          falsifier="if Kenyan external funding events produce no measurable effect on frontier "
                    "credit carriers after controlling for the global EM factor, the funding-"
                    "calendar channel is a domestic story with no tradable expression",
          notes="One of very few genuinely exogenous, years-ahead-known date grids in frontier "
                "markets."),
    actor("Kenyan oil importers and the government-to-government arrangement",
          holds="the country's largest single import line and its dollar obligation",
          forced_to=("buy dollars for fuel whatever the exchange rate",
                     "settle on the extended credit terms the arrangement set"),
          when="continuous demand converted into LUMPY SCHEDULED payments under the arrangement",
          information=("the Brent price", "the pump price formula", "credit terms"),
          constraints=("an inelastic short-run demand for fuel",
                       "a regulated pump price that lags the input cost",
                       "the arrangement's own settlement schedule"),
          instruments=("XBRUSD", "XTIUSD", "USDZAR"),
          counterparties=("Gulf suppliers", "Kenyan banks", "the regulator"),
          observables=("the oil import bill in the trade data", "pump price announcements",
                       "the arrangement's terms and its changes"),
          impact="THE SAME BRENT MOVE IS INCOME FOR NIGERIA AND A COST FOR KENYA, and running "
                 "both is what makes the oil channel identifiable: a shock that moves both the "
                 "same way is risk appetite, one that moves them oppositely is oil",
          persistence="structural; Kenya has no domestic crude",
          falsifier="if Kenyan frontier-risk proxies show the same sign of response to a Brent "
                    "shock as Nigerian ones, after controlling for the global risk factor, the "
                    "importer-exporter distinction carries no information and the design "
                    "contrast this pack is built on is wrong",
          notes="THE DESIGN CONTRAST, stated as a falsifier so it can actually fail."),
    actor("Tea smallholders and the KTDA",
          holds="the world's largest source of black tea by export volume, grown by hundreds of "
                "thousands of smallholders",
          forced_to=("sell through the weekly Mombasa auction",
                     "accept the bonus payment structure the agency sets"),
          when="weekly auctions; the annual bonus is a political and economic event",
          information=("auction prices and the unsold percentage", "rainfall", "the shilling"),
          constraints=("a perishable crop with a short picking window",
                       "an auction that clears weekly whatever the price",
                       "a shilling-denominated cost base against dollar-denominated revenue"),
          instruments=("USDZAR", "COFARA"),
          counterparties=("Pakistani, Egyptian, UK and Russian buyers", "brokers",
                          "the agency"),
          observables=("weekly lots offered, lots sold and the UNSOLD PERCENTAGE",
                       "average price by grade", "export volumes"),
          impact="THE DESK CANNOT TRADE TEA, so this actor's impact is on Kenyan EXPORT EARNINGS "
                 "and therefore FX supply, and on the regional smallholder income that drives "
                 "food demand. It is a conditioning observable and the pack refuses to proxy it "
                 "into a coffee contract.",
          persistence="structural",
          falsifier="if Kenyan export earnings show no relationship to auction outcomes at a "
                    "one-to-two-month lag, the auction is not the transmission point it appears "
                    "to be and the tea channel is not measurable from public data",
          notes="THE UNSOLD PERCENTAGE IS THE INFORMATIVE COLUMN and the one most often "
                "ignored: it is a demand signal the average price hides."),
    actor("Coffee cooperatives and the Nairobi auction",
          holds="a premium Arabica origin sold at a weekly public auction",
          forced_to=("deliver cherry to a cooperative mill and wait for the auction",
                     "accept the reforms that have repeatedly restructured the marketing chain"),
          when="weekly auctions through the marketing year",
          information=("auction prices by grade", "the global Arabica price", "rainfall"),
          constraints=("a marketing chain that has been reformed repeatedly, which is a series "
                       "break in the price data",
                       "quality grading that determines the premium"),
          instruments=("COFARA",),
          counterparties=("specialty roasters", "exporters", "cooperatives"),
          observables=("weekly auction prices by grade", "volumes", "cherry prices to farmers"),
          impact="Kenya is a SMALL share of world Arabica, so the channel is about the QUALITY "
                 "PREMIUM and regional supply rather than the global price level. The pack says "
                 "this explicitly because the opposite claim is the obvious and wrong one.",
          persistence="structural, with repeated marketing-chain reforms as breaks",
          falsifier="if the Nairobi auction premium over the global Arabica benchmark shows no "
                    "response to Kenyan rainfall anomalies, the local supply channel does not "
                    "reach even the premium, let alone the level",
          notes="The honest version of a soft-commodity origin edge: premium, not level."),
    actor("Kenyan maize consumers and the price of unga",
          holds="the country's staple food at a price that is a political variable",
          forced_to=("buy maize flour at whatever the price is",
                     "and the government to intervene, by subsidy or import waiver, when it "
                     "rises far enough"),
          when="continuous, with acute episodes after a failed season",
          information=("the harvest", "import parity", "subsidy announcements"),
          constraints=("a staple with no substitute in the diet",
                       "a political economy in which the price is discussed in constituencies "
                       "before it is discussed in markets"),
          instruments=("CORN", "WHEAT", "USDZAR"),
          counterparties=("millers", "regional suppliers", "the government"),
          observables=("retail unga prices", "KNBS food inflation",
                       "subsidy and import-waiver announcements"),
          impact="a failed season becomes an IMPORT DEMAND and a fiscal intervention at the same "
                 "time, so the regional grain flow and the currency move together",
          persistence="structural; every failed season produces the same sequence",
          falsifier="if Kenyan food inflation shows no relationship to measured rainfall "
                    "anomalies at a three-to-six-month lag after controlling for world grain "
                    "prices and the shilling, the local weather channel is subsumed by the "
                    "global one",
          notes="SWAHILI-LANGUAGE COVERAGE CARRIES THIS FIRST, which is why the terminology "
                "table is bilingual rather than decorative."),
    actor("Horticulture and cut-flower exporters",
          holds="a high-value, air-freighted, Europe-facing export business",
          forced_to=("book air freight at whatever it costs",
                     "sell into euro-denominated contracts and auctions"),
          when="continuous, with a sharp seasonal peak into European holidays",
          information=("air freight rates and capacity", "European demand", "the euro"),
          constraints=("a perishable product that must fly",
                       "belly-hold capacity on passenger aircraft, which collapses when "
                       "passenger traffic does",
                       "European phytosanitary and carbon rules"),
          instruments=("EURUSD", "XBRUSD"),
          counterparties=("European auctions and supermarkets", "airlines", "freight forwarders"),
          observables=("horticulture export values in the trade data", "air freight rates",
                       "European demand indicators"),
          impact="AN UNDERRATED FX CHANNEL: this is a euro-denominated export earning from a "
                 "country everyone models against the dollar, so a EURUSD move changes Kenyan "
                 "export receipts in a direction the dollar model does not see",
          persistence="structural, with an acute disruption whenever air capacity is constrained",
          falsifier="if Kenyan horticulture export values show no sensitivity to EURUSD beyond "
                    "the mechanical translation effect, the euro-revenue channel adds nothing "
                    "to a dollar model",
          notes="Named because the obvious model -- frontier currency versus dollar -- misses it."),
    actor("The Mombasa port and the northern corridor",
          holds="the sea gate for Uganda, Rwanda, South Sudan and eastern DRC",
          forced_to=("clear transit cargo alongside domestic cargo",
                     "operate under whichever rail-versus-road policy is current"),
          when="continuous; measured in transit times and dwell times",
          information=("throughput", "dwell time", "transit times up the corridor"),
          constraints=("berth and yard capacity",
                       "the rail capacity that policy has repeatedly tried to mandate",
                       "border-post processing in three countries"),
          instruments=("XBRUSD", "CORN", "USDZAR"),
          counterparties=("landlocked neighbours", "shipping lines", "transporters"),
          observables=("port throughput", "container dwell time", "corridor transit times",
                       "rail volume share"),
          impact="A REGIONAL TRADE OBSERVABLE PUBLISHED IN ONE COUNTRY. Congestion here is a "
                 "supply constraint for four economies, so the corridor's throughput is a "
                 "better regional activity measure than any single country's trade data.",
          persistence="structural, with episodic acute congestion",
          falsifier="if corridor transit times show no relationship to regional import volumes "
                    "or to the regional price of imported staples, the corridor is a logistics "
                    "statistic with no economic content",
          notes="Publication is irregular and the dataset is marked pit_feasible=False; the gap "
                "is declared rather than papered over."),
    actor("The mobile-money payments rail",
          holds="a very large share of Kenyan transaction value, outside the traditional "
                "banking system",
          forced_to=("report transaction values and volumes to the central bank",
                     "maintain agent float and liquidity across the network"),
          when="continuous; reported monthly by the CBK",
          information=("transaction values and volumes", "agent counts", "float levels"),
          constraints=("regulatory caps on transaction sizes and charges",
                       "agent liquidity, which binds in rural areas"),
          instruments=("USDZAR",),
          counterparties=("households", "small businesses", "banks"),
          observables=("CBK monthly mobile-money statistics", "agent counts"),
          impact="THE CLOSEST THING KENYA HAS TO A HIGH-FREQUENCY ACTIVITY INDEX. A sharp fall "
                 "in transaction value is a real-economy liquidity event, and it shows up before "
                 "quarterly GDP does.",
          persistence="structural",
          falsifier="if mobile-money transaction value adds nothing to a nowcast of Kenyan "
                    "activity over and above CPI and trade data, it is a payments statistic and "
                    "not an activity index",
          notes="THE OPERATOR IS A LISTED SINGLE NAME AND IS REFUSED AS A DOCKET SYMBOL "
                "(two-lane order 2026-09-06). An observable, never a hypothesis."),
    actor("Diaspora remittance senders",
          holds="Kenya's most stable dollar inflow, larger than any single export line",
          forced_to=("send on a monthly and festival cycle regardless of the exchange rate",
                     "choose a channel and a provider"),
          when="continuous, with a December and mid-year seasonal peak",
          information=("the exchange rate", "transfer costs", "recipient need"),
          constraints=("transfer costs and compliance on the sending side",
                       "recipient access to the payout network"),
          instruments=("USDZAR",),
          counterparties=("money transfer operators", "banks", "mobile-money recipients"),
          observables=("CBK monthly diaspora remittance statistics"),
          impact="REMITTANCES ARE KENYA'S LARGEST AND MOST STABLE FX INFLOW, which means an "
                 "inflow surprise is a genuine relief of FX stress rather than a portfolio flow "
                 "that can reverse. The stability is the finding: it makes Kenya's FX position "
                 "structurally different from a portfolio-flow-dependent frontier sovereign.",
          persistence="structural and counter-cyclical, which is unusual and valuable",
          falsifier="if remittance surprises show no relationship to the CBK's published buy/"
                    "sell spread or to reserve accumulation, the inflow is not reaching the "
                    "market in a way the published data can see",
          notes="The stability contrast with Nigeria's channel-switching remittances is "
                "instructive: Kenya's wedge is small, so the official series measures the flow "
                "rather than measuring observability."),
    actor("Foreign holders of Kenyan government securities",
          holds="a SMALL share of Kenyan domestic debt by frontier standards",
          forced_to=("price a currency they cannot hedge",
                     "exit through a thin FX market when they exit at all"),
          when="continuous; auctions weekly",
          information=("the yield", "the reserve path", "the funding calendar"),
          constraints=("no deliverable hedge", "thin secondary liquidity",
                       "mandate limits on frontier exposure"),
          instruments=("UST10Y", "USDZAR"),
          counterparties=("the Treasury", "local banks"),
          observables=("auction results and bid-to-cover", "foreign holding statistics"),
          impact="THE SMALL SHARE IS THE FINDING. Kenya's currency is driven by the external "
                 "funding calendar and the trade account far more than by portfolio flow -- the "
                 "opposite of South Africa, and it means portfolio-flow mechanisms that work "
                 "there should NOT work here. That is a testable cross-country prediction.",
          persistence="structural",
          falsifier="if Kenyan FX stress responds to global portfolio-flow proxies as strongly "
                    "as South African FX stress does, the small-share claim is wrong and the "
                    "two countries are not the contrasting pair this civilization treats them as",
          notes="A cross-country falsifier, which is stronger than a single-country one."),
    actor("The IMF as an external constraint",
          holds="programme disbursements conditional on scheduled reviews",
          forced_to=("publish review outcomes and staff reports on a schedule",
                     "state conditions that the authorities must meet"),
          when="scheduled reviews, typically semi-annual",
          information=("fiscal performance", "reserve adequacy", "structural benchmarks"),
          constraints=("its own published methodology and board calendar"),
          instruments=("USDZAR", "UST10Y"),
          counterparties=("the Treasury", "the CBK", "other creditors"),
          observables=("review calendars", "staff reports and their data annexes",
                       "disbursement announcements"),
          impact="A SCHEDULED EXOGENOUS DATE GRID, and the staff reports contain reserve and "
                 "external-position detail the authorities do not otherwise publish -- so the "
                 "IMF is simultaneously an event and a data source",
          persistence="episodic but recurrent across programmes",
          falsifier="if frontier credit carriers show no abnormal behaviour around scheduled "
                    "review dates relative to matched dates, the review calendar carries no "
                    "information the market has not already priced",
          notes="Scheduled review dates are among the few exogenous grids available for a "
                "frontier sovereign."),
    actor("The East African drought and ENSO cycle",
          holds="the rainfall that determines two harvests a year across the region",
          forced_to=("follow a physical cycle that no policy affects",
                     "and to do so with a teleconnection to the Pacific that is forecastable "
                     "months ahead"),
          when="two seasons a year: long rains March-May, short rains October-December",
          information=("sea surface temperatures", "seasonal forecasts", "dekadal rainfall"),
          constraints=("physics; this is the one actor in the civilization that is genuinely "
                       "exogenous to every market"),
          instruments=("CORN", "WHEAT", "COFARA", "SUGAR"),
          counterparties=("every agricultural producer in the region"),
          observables=("CHIRPS rainfall", "FEWS NET outlooks", "KMD seasonal forecasts",
                       "ENSO indices"),
          impact="A GENUINELY EXOGENOUS SUPPLY SHOCK WITH A FORECASTABLE LEAD. Unlike almost "
                 "every other observable in this civilization, rainfall cannot be affected by "
                 "the market that trades on it -- which removes the reverse-causality problem "
                 "that contaminates FX and production data.",
          persistence="multi-year ENSO cycles with two seasons a year inside them",
          falsifier="if East African rainfall anomalies show no conditional effect on regional "
                    "grain prices or on the soft complex after controlling for global "
                    "production, the regional weather channel is too small to trade",
          notes="THE CLEANEST IDENTIFICATION IN THE PACK, and the reason the weather family "
                "exists in africa_interaction.py."),
)


# --------------------------------------------------------------------------- domains
DOMAINS: tuple[dict[str, Any], ...] = (
    domain("ke_fx_rate_and_spread", "The published buy/sell spread as the stress observable",
           objects=("the daily buy, sell and mean by currency", "the spread in basis points",
                    "the spread's own level and rate of change"),
           conditions=("the FX regime era", "reserve cover", "auction weeks", "holiday gaps"),
           instruments=("USDZAR", "USDTRY", "EURUSD"),
           controls=("the mean alone, which should carry LESS information than the spread if the "
                     "pack's central claim is right",
                     "matched days in the same era with a normal spread",
                     "randomised spread values"),
           notes="THE PACK'S FLAGSHIP. A missing CBK day is UNMEASURED, never a zero."),
    domain("ke_reserve_adequacy", "Import cover against a published statutory floor",
           objects=("usable reserves", "months of import cover", "the distance to the floor"),
           conditions=("the oil import bill", "the funding calendar", "IMF programme status"),
           instruments=("USDZAR", "UST10Y", "XBRUSD"),
           controls=("other frontier sovereigns with equal cover and no published floor",
                     "matched windows at equal oil prices",
                     "randomised floor breaches"),
           notes="A PUBLISHED TARGET MAKES A REACTION FUNCTION OBSERVABLE, which is rare."),
    domain("ke_external_debt_calendar", "Maturities, buybacks and the price of market access",
           objects=("the eurobond maturity calendar", "buyback and issuance announcements",
                    "IMF review outcomes"),
           conditions=("the global EM funding state", "reserve cover", "rating actions"),
           instruments=("UST10Y", "UKGILT", "USDZAR"),
           controls=("matched non-event windows",
                     "other frontier sovereigns with maturities the same month",
                     "randomised maturity dates"),
           notes="The 2024 buyback is the canonical episode and a genuinely clean dated test."),
    domain("ke_oil_import_bill", "Brent as a COST, and the Nigeria contrast that identifies it",
           objects=("the oil import line in the trade data", "pump price announcements",
                    "the scheduled payment cycle under the G2G arrangement"),
           conditions=("the Brent level", "the arrangement's terms", "the shilling"),
           instruments=("XBRUSD", "XTIUSD", "USDZAR"),
           controls=("NIGERIA, an oil exporter in the same region with the same frontier "
                     "classification -- the sign of the response is the test",
                     "matched windows at equal global risk appetite",
                     "randomised Brent shocks"),
           notes="The cross-country control is what makes the oil channel identifiable at all."),
    domain("ke_agricultural_export_cycle", "Weekly auctions as a calendar object",
           objects=("weekly tea and coffee auction prices and volumes",
                    "the tea UNSOLD PERCENTAGE", "export earnings"),
           conditions=("rainfall", "the season", "global soft prices", "auction-week holidays"),
           instruments=("COFARA", "USDZAR"),
           controls=("matched non-auction weeks",
                     "global soft prices, removed first, so what remains is the origin premium",
                     "randomised auction weeks"),
           notes="THE DESK CANNOT TRADE TEA. Every tea object here is a conditioning observable "
                 "and the pack refuses to proxy it into a coffee contract."),
    domain("ke_tea_auction", "The Mombasa auction as a regional demand gauge",
           objects=("lots offered and sold", "the unsold percentage",
                    "average price by grade"),
           conditions=("regional supply", "buyer-country demand", "the shilling"),
           instruments=("USDZAR", "COFARA"),
           controls=("weeks with equal volume and different unsold percentages",
                     "other origins' auctions",
                     "randomised unsold percentages"),
           notes="The unsold percentage is a demand signal that the average price hides."),
    domain("ke_coffee_auction", "The origin premium, not the global level",
           objects=("Nairobi auction prices by grade",
                    "the premium over the global Arabica benchmark"),
           conditions=("rainfall", "the marketing-chain regime", "global Arabica"),
           instruments=("COFARA",),
           controls=("the global Arabica benchmark, removed first",
                     "other premium origins",
                     "randomised premium values"),
           notes="Kenya is a small share of world Arabica; the pack claims the PREMIUM and "
                 "explicitly refuses to claim the level."),
    domain("ke_rainfall_and_drought", "Two seasons a year, and why consecutive failures differ",
           objects=("CHIRPS dekadal rainfall", "FEWS NET outlooks", "seasonal forecasts",
                    "the COUNT of consecutive failed seasons"),
           conditions=("the ENSO state", "which season", "the cropping zone"),
           instruments=("CORN", "WHEAT", "COFARA", "SUGAR"),
           controls=("the southern African maize belt, which shares the ENSO driver and has ONE "
                     "season in the opposite hemisphere's timing",
                     "years with normal rainfall in the same calendar window",
                     "randomised season labels"),
           notes="GENUINELY EXOGENOUS: rainfall cannot be affected by the market trading on it, "
                 "which removes the reverse-causality problem that contaminates FX data."),
    domain("ke_food_price_politics", "The staple price as a political and fiscal variable",
           objects=("retail unga prices", "KNBS food inflation",
                    "subsidy and import-waiver announcements"),
           conditions=("the harvest", "import parity", "the electoral cycle"),
           instruments=("CORN", "WHEAT", "USDZAR"),
           controls=("years with equal harvests and no intervention",
                     "neighbouring countries with the same harvest and different politics",
                     "randomised intervention dates"),
           notes="Swahili-language coverage carries this before the English financial press."),
    domain("ke_transit_corridor_logistics", "Mombasa as the sea gate for four economies",
           objects=("port throughput", "container dwell time", "corridor transit times",
                    "the rail volume share"),
           conditions=("regional demand", "policy on rail versus road", "border processing"),
           instruments=("XBRUSD", "CORN", "USDZAR"),
           controls=("periods of equal throughput with no congestion",
                     "other African corridors",
                     "randomised congestion dates"),
           notes="Marked NOT_PIT_SAFE at the dataset level: publication is irregular and a "
                 "missing month is not a zero."),
    domain("ke_mobile_money_liquidity", "A payments rail as a high-frequency activity index",
           objects=("monthly transaction value and volume", "agent counts",
                    "the value-per-transaction ratio"),
           conditions=("the season", "regulatory changes to caps and charges",
                       "the real economy"),
           instruments=("USDZAR",),
           controls=("CPI and trade data, which the series must beat to be an index rather than "
                     "a statistic",
                     "months with regulatory changes, which are breaks not signals",
                     "randomised months"),
           notes="THE OPERATOR IS AN OBSERVABLE, NEVER A SYMBOL (two-lane order 2026-09-06)."),
    domain("ke_frontier_stress_transmission", "Kenya as a frontier sensor for tradable carriers",
           objects=("the joint state of spread, cover and funding calendar",
                    "eurobond spread moves"),
           conditions=("the global EM risk state", "the dollar", "oil"),
           instruments=("USDZAR", "USDTRY", "UST10Y"),
           controls=("THE GLOBAL EM FACTOR, removed first -- no Kenya-specific claim survives "
                     "without it",
                     "matched EM stress episodes with no Kenyan component",
                     "randomised event dates"),
           notes="If Kenyan stress does not reach a tradable carrier, the satellite ranking is "
                 "right and the pack should stay small."),
    domain("ke_policy_reaction", "The MPC, the CBR and the cash reserve ratio",
           objects=("the CBR decision against expectation", "CRR changes",
                    "the statement's language"),
           conditions=("the inflation regime", "reserve cover", "the global rate cycle"),
           instruments=("USDZAR", "UST10Y"),
           controls=("matched non-MPC days",
                     "decisions with the same rate move and a different CRR move",
                     "other frontier central banks in the same week"),
           notes="EAT never moves against UTC, so the event anchor is clean -- unlike Egypt's."),
)


# --------------------------------------------------------------------------- transmission
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    edge("ke_failed_rains_to_regional_grain",
         source="CHIRPS rainfall anomalies and FEWS NET East Africa outlooks for the long and "
                "short rains",
         mechanism="a failed season turns a maize-growing region into an import region, raising "
                   "regional grain demand and the food-import bill at once; consecutive failures "
                   "compound because the second season is the first one's insurance",
         targets=("CORN", "WHEAT", "USDZAR"),
         sign="a severe rainfall deficit in a growing season -> regional grain demand UP and "
              "frontier FX stress UP over the following months",
         lag="the rainfall anomaly leads the harvest by about three months and the import "
             "response by three to six",
         horizon="one to three quarters",
         control="the southern African maize belt, which shares the ENSO driver and has one "
                 "season in the opposite hemisphere's timing; and years with normal rainfall in "
                 "the same calendar window",
         evidence="HYPOTHESIS",
         notes="THE PACK'S CLEANEST IDENTIFICATION: rainfall cannot be affected by the market "
               "that trades on it."),
    edge("ke_coffee_auction_to_arabica_premium",
         source="Nairobi Coffee Exchange weekly auction prices and volumes by grade",
         mechanism="Kenya is a premium Arabica origin whose weekly auction is public, so its "
                   "clearing price relative to the global benchmark is a read on specialty "
                   "demand and on East African supply",
         targets=("COFARA",),
         sign="auction premium over the benchmark WIDENS -> specialty demand or regional "
              "shortfall -> a small positive effect on the benchmark at longer horizons",
         lag="weekly auction publication, three days after the sale",
         horizon="five to forty sessions",
         control="THE GLOBAL ARABICA BENCHMARK, REMOVED FIRST -- what remains is the origin "
                 "premium, which is the only thing this edge claims; plus other premium origins "
                 "and randomised auction weeks",
         evidence="HYPOTHESIS",
         notes="The honest version of an origin edge. Claiming Kenya moves the global Arabica "
               "level would be the obvious and wrong claim."),
    edge("ke_oil_import_cost_inverts_nigeria",
         source="the Brent price joined to Kenya's oil import bill and to Nigeria's oil revenue",
         mechanism="Kenya imports all its crude and Nigeria exports it, so a Brent shock is a "
                   "cost for one and income for the other; the DIFFERENCE in their frontier-risk "
                   "response is the oil channel with the global risk factor differenced out",
         targets=("XBRUSD", "USDZAR", "XTIUSD"),
         sign="Brent UP -> Kenyan FX stress UP and Nigerian FX stress DOWN; a common-direction "
              "response is risk appetite and not oil",
         lag="the import bill responds within a quarter; the FX stress within weeks",
         horizon="ten to sixty sessions",
         control="THE CROSS-COUNTRY DIFFERENCE IS ITSELF THE CONTROL, which is why this edge is "
                 "stated as a pair rather than as a Kenyan claim",
         evidence="HYPOTHESIS",
         notes="The single best identification argument in the civilization and the reason both "
               "packs exist."),
    edge("ke_eurobond_calendar_to_frontier_credit",
         source="Kenyan eurobond maturities, buybacks and IMF review outcomes",
         mechanism="frontier FX is priced off the EXTERNAL FUNDING CALENDAR far more than off "
                   "the current account, and Kenya demonstrated this on a date in February 2024",
         targets=("UST10Y", "UKGILT", "USDZAR"),
         sign="a successful refinancing or buyback -> frontier credit stress DOWN; a failed or "
              "delayed one -> stress UP",
         lag="announcement timestamps; the maturity dates are known years ahead",
         horizon="five to sixty sessions",
         control="other frontier sovereigns with maturities the same month; matched windows at "
                 "the same global funding conditions; randomised maturity dates",
         evidence="HYPOTHESIS"),
    edge("ke_fx_spread_widening_to_stress",
         source="the CBK's published daily buy/sell spread in basis points",
         mechanism="the mean is a posted average and the spread is the price of immediacy; a "
                   "widening spread on a stable mean is a market clearing at a rate the mean "
                   "does not show",
         targets=("USDZAR", "USDTRY"),
         sign="spread widening beyond its trailing distribution -> frontier FX stress UP over "
              "the following sessions",
         lag="daily publication, late in the Nairobi afternoon",
         horizon="one to ten sessions",
         control="THE MEAN ALONE, which should carry less information than the spread if the "
                 "claim is right; plus matched days with a normal spread and randomised spreads",
         evidence="HYPOTHESIS",
         notes="The Kenyan analogue of a Nigerian turnover collapse, and the pack's most "
               "testable claim."),
    edge("ke_corridor_congestion_to_regional_trade",
         source="Mombasa port dwell times and northern-corridor transit times",
         mechanism="Mombasa is the sea gate for four economies, so congestion is a supply "
                   "constraint for a region rather than for a country, and it raises the "
                   "landed cost of every imported staple and fuel cargo upstream",
         targets=("CORN", "XBRUSD", "USDZAR"),
         sign="congestion UP -> regional landed costs UP and regional import volumes DOWN with "
              "a lag",
         lag="one to two months, limited by irregular publication",
         horizon="one to two quarters",
         control="periods of equal throughput with no congestion; other African corridors; "
                 "randomised congestion dates",
         evidence="HYPOTHESIS",
         notes="Marked NOT_PIT_SAFE at the dataset level. Declared so the gap is visible, not so "
               "it can be traded before the data supports it."),
    edge("ke_horticulture_euro_revenue",
         source="Kenyan horticulture and cut-flower export values and European demand",
         mechanism="this is a EURO-DENOMINATED export earning from a country everyone models "
                   "against the dollar, so a EURUSD move changes Kenyan receipts in a direction "
                   "the dollar model does not see",
         targets=("EURUSD", "USDZAR"),
         sign="EURUSD UP -> Kenyan export receipts UP in dollar terms -> frontier FX stress DOWN",
         lag="trade data arrives with a sixty-day lag; the freight and demand legs are faster",
         horizon="one to two quarters",
         control="the mechanical translation effect, which must be separated from a genuine "
                 "volume response; other African exporters with dollar-denominated revenue",
         evidence="HYPOTHESIS",
         notes="Named because the obvious frontier-versus-dollar model misses it entirely."),
    edge("ke_remittance_surprise_to_stress_relief",
         source="CBK monthly diaspora remittance statistics",
         mechanism="remittances are Kenya's largest and most stable FX inflow, so an inflow "
                   "surprise is a genuine relief of FX stress rather than a portfolio flow that "
                   "can reverse",
         targets=("USDZAR",),
         sign="a positive remittance surprise -> the published buy/sell spread NARROWS and "
              "reserve accumulation improves",
         lag="one month publication lag",
         horizon="one to two months",
         control="matched months with equal trade balances; the seasonal pattern, removed first; "
                 "randomised surprise values",
         evidence="HYPOTHESIS",
         notes="Kenya's wedge is small, so unlike Nigeria's the official series measures the "
               "FLOW rather than measuring observability. That contrast is the point."),
    edge("ke_mobile_money_collapse_to_activity",
         source="CBK monthly mobile-money transaction values and volumes",
         mechanism="mobile money carries a very large share of Kenyan transactions, so a sharp "
                   "fall in value is a real-economy liquidity event visible before quarterly GDP",
         targets=("USDZAR", "CORN"),
         sign="a sharp fall in transaction value -> domestic demand weakness -> frontier stress "
              "UP and staple import demand DOWN",
         lag="one month publication lag",
         horizon="one to two quarters",
         control="CPI and trade data, which the series must beat to be an index rather than a "
                 "statistic; months with regulatory changes, which are breaks not signals",
         evidence="HYPOTHESIS",
         notes="The operator is a listed single name and is an OBSERVABLE, NEVER A SYMBOL."),
    edge("ke_unga_intervention_to_grain_flow",
         source="Kenyan maize flour prices and government subsidy or import-waiver "
                "announcements",
         mechanism="when the staple price rises far enough the government intervenes by subsidy "
                   "or import waiver, which converts a domestic price problem into a REGIONAL "
                   "IMPORT ORDER on an announced date",
         targets=("CORN", "WHEAT", "USDZAR"),
         sign="an import waiver announced -> regional grain import demand UP within weeks",
         lag="the announcement timestamp; the import response within one to two months",
         horizon="one to two quarters",
         control="years with equal harvests and no intervention; neighbouring countries with "
                 "the same harvest and different politics; randomised intervention dates",
         evidence="HYPOTHESIS",
         notes="A rare case where a POLITICAL decision creates a dated, quantified commodity "
               "order."),
    edge("ke_portfolio_share_cross_country_test",
         source="foreign holdings of Kenyan versus South African domestic debt",
         mechanism="Kenya's foreign holding share is small and South Africa's is large, so "
                   "portfolio-flow mechanisms that work for the rand should NOT work for the "
                   "shilling -- a cross-country prediction rather than a within-country "
                   "correlation",
         targets=("USDZAR", "UST10Y"),
         sign="a global portfolio-flow shock -> a large USDZAR response and a small Kenyan one; "
              "equal responses would falsify the pair",
         lag="contemporaneous to five sessions",
         horizon="five to forty sessions",
         control="the shock itself is common to both; the test is the DIFFERENCE in magnitude",
         evidence="HYPOTHESIS",
         notes="A CROSS-COUNTRY FALSIFIER, which is stronger than a single-country one and is "
               "the kind of test a regional civilization exists to make possible."),
    edge("ke_holiday_observability_gap",
         source="the Kenyan statutory holiday table and the weekly auction calendar",
         mechanism="a Kenyan closure stops the DATA, not the price: no CBK rate, no NSE print, "
                   "and -- the sharper case -- a public holiday inside an auction week shifts or "
                   "cancels the sale, so the weekly export-price series has genuinely missing "
                   "weeks that are not low-volume weeks",
         targets=("COFARA", "USDZAR"),
         sign="the post-closure auction and the post-closure CBK print show elevated absolute "
              "changes relative to matched ordinary observations",
         lag="the closure itself; the effect is in the next published observation",
         horizon="one to three observations",
         control="matched non-holiday weeks; closures of different lengths; randomised closure "
                 "dates",
         evidence="HYPOTHESIS",
         notes="A MISSING CBK DAY OR AUCTION WEEK IS UNMEASURED, NEVER A ZERO. This edge makes "
               "that rule operational rather than decorative."),
)

#: Derived, never hand-maintained. With OWN_PRICE empty every target is a transmission target,
#: which is the arithmetic statement of this pack being transmission-only.
TRANSMISSION_TARGETS: tuple[str, ...] = tuple(sorted(
    {t for e in TRANSMISSION_EDGES_SEED for t in e["targets"]} - set(OWN_PRICE)))


# --------------------------------------------------------------------------- eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    era("ke_drought_2020_2023", start="2020-10-01", end="2023-05-31",
        label="Five consecutive failed rainy seasons",
        what_changed="the longest drought in decades across the Horn of Africa; the region moved "
                     "from marginal self-sufficiency to sustained import dependence",
        invalidates="ANY rainfall elasticity estimated on single-season failures does not apply "
                    "here: consecutive failures compound because each season is the previous "
                    "one's insurance, and an annual rainfall aggregate cannot represent that"),
    era("ke_stale_official_rate", start="2022-03-01", end="2023-03-31",
        label="The published rate and the transactable rate diverge",
        what_changed="the CBK's published indicative rate was stable while interbank volume "
                     "collapsed and banks quoted corporates materially away from it",
        invalidates="EVERY study using the official mean through this window is measuring a "
                    "policy choice rather than a price. This is the era that makes the SPREAD "
                    "and the VOLUME the informative series and the mean the misleading one."),
    era("ke_fx_market_reform", start="2023-03-01", end=None,
        label="Interbank market reform and the return of two-way pricing",
        what_changed="the CBK moved to restore interbank activity and the published rate "
                     "converged back toward transactable levels",
        invalidates="microstructure estimates from the divergence era do not transfer; the price "
                    "formation mechanism itself changed"),
    era("ke_eurobond_stress", start="2023-06-01", end="2024-02-13",
        label="The maturity wall and the default fear",
        what_changed="the market priced a material probability of a disorderly 2024 eurobond "
                     "maturity; the shilling depreciated sharply and the spread blew out",
        invalidates="frontier credit and FX estimates pooled across the buyback boundary are "
                    "averaging a distressed sovereign and a refinanced one"),
    era("ke_eurobond_buyback", start="2024-02-14", end=None,
        label="The buyback and the sharp appreciation",
        what_changed="a large part of the 2024 maturity was bought back and the shilling "
                     "appreciated sharply in the following weeks",
        invalidates="a CLEAN DATED DEMONSTRATION that frontier FX is priced off the external "
                    "funding calendar; any model that explains the shilling by the current "
                    "account alone cannot produce this move"),
    era("ke_fuel_import_arrangement", start="2023-04-01", end=None,
        label="The government-to-government fuel import arrangement",
        what_changed="continuous daily dollar demand for fuel became lumpy scheduled payments on "
                     "extended credit terms",
        invalidates="the SHAPE of Kenyan FX demand changed even where the annual total did not; "
                    "a study spanning the change is pooling two different demand processes"),
    era("ke_finance_bill_2024", start="2024-06-18", end="2024-08-31",
        label="The Finance Bill protests and the withdrawal",
        what_changed="a revenue package was withdrawn after nationwide protests, leaving a "
                     "funding gap and a changed political constraint on taxation",
        invalidates="fiscal-consolidation assumptions from before this window do not hold after "
                    "it; the political constraint on revenue is now an observable in its own "
                    "right"),
    era("ke_cbr_easing_cycle", start="2024-08-06", end=None,
        label="The easing cycle after the inflation peak",
        what_changed="the CBK began cutting the Central Bank Rate as inflation returned inside "
                     "the band and the shilling stabilised",
        invalidates="policy-surprise studies pooled across the turn are fitting one reaction "
                    "function to a tightening and an easing regime"),
)


# --------------------------------------------------------------------------- the pack
def spec() -> dict[str, Any]:
    """THIS PACK AS PLAIN DATA -- the twenty-one fields exactly as this department declares them.

    THE SOURCE OF TRUTH, and the thing the tests validate. The country lab's frozen `CountryPack`
    has row classes with their own field names and DROPS any row it cannot construct; that makes
    the typed object a LOSSY VIEW of a pack written in this package's richer vocabulary, so the
    plain data is kept and `pack()` adapts it explicitly.
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

    ONE EDGE BECOMES SEVERAL SEEDS because a `TransmissionSeed` is keyed on `(to_country, asset)`.
    Everything the typed row has no field for is preserved in `notes`. Open eras take a sentinel
    end date because the framework's `Era` requires one -- A FRAMEWORK REQUIREMENT, NEVER A CLAIM.
    `cot_currency` is empty: there is no CFTC shilling contract, and an invented ticker there
    would make the positioning miner report a number instead of UNMEASURED.
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
                    "expiry_rule": "", "open_utc": "", "close_utc": "",
                    "notes": "; ".join(f"{kk}={vv}" for kk, vv in v.items() if kk != "name")}
                   for k, v in EXCHANGES.items() if isinstance(v, dict))
    every_day = tuple(sorted(d for tbl in _KE_HOLIDAYS.values() for d in tbl))
    return {"transmission_edges_seed": tuple(seeds), "policy_eras": eras,
            "fixing_conventions": fixings, "settlement_conventions": settle,
            "exchanges": venues,
            "holidays_rule": {"dates": every_day, "notes": str(HOLIDAYS_RULE["rule"])},
            "fiscal_year_end": "06-30",
            "export_economy": "agricultural_exporter",
            "retail_leverage_regime": "UNMEASURED",
            "cot_currency": "",
            "positioning_sources": tuple(str(p["id"]) for p in POSITIONING_SOURCES),
            "source_classes": tuple(str(s["id"]) for s in SOURCE_CLASSES),
            "custom_miners": tuple(str(m["entry"]) for m in CUSTOM_MINERS),
            "miner_domains": {str(m["name"]): tuple(m["domain_ids"]) for m in CUSTOM_MINERS},
            "mission": "mine Kenya to exhaustion as an exogenous East African rainfall, "
                       "smallholder-export and frontier-funding sensor for the soft complex, "
                       "energy and African carriers the desk already trades; the shilling and "
                       "tea are both untradable here and every finding must land on a carrier"}


def pack() -> Any:
    """The Kenya country pack. `CountryPack` when the framework has landed, else a dict."""
    return build_pack(**{**spec(), **framework_rows()})


def priority_weight() -> float:
    """This pack's share of the opening African compute ladder. A PRIOR, replaced by survivors."""
    return PRIORITY_WEIGHT


def instrument_report(path: Any = None) -> dict[str, Any]:
    """What this pack can trade, what carries its economics and what is missing, MEASURED against
    the broker registry. `own_price` is empty and TEA has no carrier at all; both are
    measurements rather than oversights."""
    split = resolve(EXECUTABLE_INSTRUMENTS, path)
    return {"code": CODE, "own_price": OWN_PRICE, "executable": tuple(split["tradable"]),
            "equities_refused": tuple(split["equities"]),
            "absent_from_universe": tuple(split["absent"]),
            "transmission_targets": TRANSMISSION_TARGETS,
            "named_absent_instruments": ABSENT_INSTRUMENTS,
            "priority_weight": PRIORITY_WEIGHT,
            "transmission_only": not OWN_PRICE,
            "largest_declared_gap": "TEA -- Kenya's largest agricultural export has no contract "
                                    "in the broker registry and no adequate carrier",
            "dataset_fields": DATASET_FIELDS}
