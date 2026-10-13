"""THE GHANA + CFA ZONE COUNTRY PACK -- one border, two monetary regimes, most of the world's cocoa.

THE MECHANISM THIS PACK EXISTS FOR, STATED FIRST BECAUSE EVERYTHING ELSE IS SUPPORTING WORK:

    Ghana and Cote d'Ivoire grow the large majority of the world's cocoa between them, across a
    single land border. Cote d'Ivoire is in the CFA franc zone, HARD-PEGGED TO THE EURO at
    655.957 XOF, and sets a GUARANTEED FARMGATE PRICE in that pegged currency for a whole season.
    Ghana sets its own guaranteed farmgate price in cedis, and the cedi FLOATS. So when the cedi
    moves against the euro, the relative value of the identical bean on the two sides of one
    border changes -- with no change in the crop, the weather, or world demand -- and the
    incentive to carry beans across that border moves with it.

    That reallocates deliverable supply between two marketing boards, two export pipelines and
    two exchange contracts, both of which this desk trades (UKCOCOA and USCOCOA). IT IS A SUPPLY
    SHOCK CAUSED BY AN EXCHANGE RATE, it is publicly observable on both sides (both farmgate
    prices are announced; both boards publish purchases), and it is the most nearly clean natural
    experiment in African commodity markets.

WHY THE CFA ZONE IS A SECTION OF THIS PACK AND NOT A PACK OF ITS OWN. Two reasons, and the second
is the important one. (1) Neither XOF nor XAF is on this broker, and a currency hard-pegged to
the euro has no independent price to model -- EURUSD IS ITS PRICE, which is a fact rather than an
approximation. (2) THE ZONE IS THE CONTROL FOR EVERY WEST AFRICAN FX HYPOTHESIS. Same region,
same commodities, same weather, opposite monetary regime. When Nigeria or Ghana claims a currency
mechanism, the CFA zone says what would have happened without a currency of one's own -- which is
the counterfactual those claims otherwise have to assert.

THE OTHER TWO THINGS GHANA IS. It has been Africa's largest gold producer in recent years, and it
is the country that ran a sovereign default and domestic debt exchange in 2022-2023 and then a
gold-for-oil barter programme -- so it supplies both a physical gold-supply observable and the
most completely documented frontier debt-restructuring episode of the decade, with dated stages.

TRANSMISSION-ONLY. `OWN_PRICE` is empty: the cedi is not quoted here, and neither is the CFA
franc. Every actor's impact and every edge's targets land on cocoa, gold, oil, EURUSD or a
tradable African carrier, or they are not findings.

NO SINGLE-NAME EQUITY IS EVER A HYPOTHESIS (two-lane order, 2026-09-06): the listed gold miners
are observables. NO CRYPTO-EXCHANGE GROUND IS HUNTED (universe mandate, 2026-08-18).
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

CODE = "gh"
NAME = "Ghana and the CFA franc zone"
REGION_COMMAND = "AFRICA"
CURRENCY = "GHS"
#: English is Ghana's official language; Twi is the language of the cocoa-growing regions and of
#: the farmgate conversation; FRENCH is not optional here, because half this pack is the CFA zone
#: and the Conseil du Cafe-Cacao publishes in French only.
NATIVE_LANGUAGES = ("en", "tw", "fr")

#: COMPUTE PRIORITY. The smallest of the five opening packs: below ZA (1.00), NG (0.62),
#: EG (0.40) and KE (0.22). A PRIOR the source-ROI layer is expected to overwrite by measured
#: survivors -- and this is the pack most likely to be promoted by them, because its flagship
#: mechanism has both legs publicly observable and both targets executable.
PRIORITY_WEIGHT: float = 0.14

#: EMPTY ON PURPOSE. Neither the cedi nor the CFA franc is quoted on this account.
OWN_PRICE: tuple[str, ...] = ()

#: What the GH department may place an order in. Every one is in the broker registry and none is
#: a single-name equity. The two cocoa contracts are the flagship, gold is the second leg, and
#: EURUSD is the CFA zone's actual price.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "UKCOCOA", "USCOCOA", "XAUUSD", "XAGUSD", "EURUSD", "XBRUSD", "XTIUSD", "XALUSD", "XCUUSD",
    "COFROB", "USDZAR", "USDX", "GBPUSD", "UST10Y", "UKGILT")

#: The instruments an Accra or Abidjan desk reaches for that THIS broker does not quote.
ABSENT_INSTRUMENTS: tuple[dict[str, str], ...] = (
    {"instrument": "USDGHS -- the Ghanaian cedi",
     "why": "absent from the broker registry; not deliverable offshore",
     "carried_by": "USDZAR as the liquid African risk carrier, and -- for the cocoa mechanism "
                   "specifically -- the CEDI-EURO CROSS ITSELF IS THE DRIVER and enters as a "
                   "conditioning series from the Bank of Ghana's published rate, not as a "
                   "position. A CARRIER, NOT A SUBSTITUTE."},
    {"instrument": "XOF and XAF -- the two CFA francs",
     "why": "absent; and a currency HARD-PEGGED to the euro at 655.957 has no independent price "
            "to quote",
     "carried_by": "EURUSD, and this is a FACT RATHER THAN AN APPROXIMATION: the peg is fixed by "
                   "treaty, so the CFA zone's dollar terms of trade are EURUSD by construction. "
                   "The only residual risk is a devaluation of the peg itself, which happened "
                   "once in 1994 and is carried as a tail, not as a price."},
    {"instrument": "Ghanaian sovereign eurobonds and the restructured instruments",
     "why": "absent; the broker quotes UKGILT, UST05Y and UST10Y and no frontier credit",
     "carried_by": "UST10Y as the global duration leg, with the Ghana-specific credit spread "
                   "left UNMEASURED BY NAME"},
    {"instrument": "GSE Composite Index and the Abidjan BRVM Composite",
     "why": "absent; no West African equity index CFD is quoted",
     "carried_by": "nothing adequate; declared a GAP rather than proxied"},
    {"instrument": "Bauxite, manganese and the physical gold dore Ghana exports",
     "why": "no contract exists for the bulks; gold dore is a physical product, not a future",
     "carried_by": "XALUSD for the bauxite-to-aluminium chain with an explicit multi-stage "
                   "caveat, and XAUUSD for the gold leg where the volume is an observable and "
                   "the price is the tradable"},
)


# --------------------------------------------------------------------------- central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "Bank of Ghana (BoG)",
    "framework": "inflation_targeter",
    "committee": "Monetary Policy Committee; the Governor delivers the decision at a press "
                 "conference",
    "policy_rate": "the Monetary Policy Rate, with the Cash Reserve Ratio used alongside it",
    "target": "8% plus or minus 2 percentage points, a band Ghana spent most of 2022-2023 far "
              "outside -- inflation peaked above 50% -- so a reaction function fitted inside the "
              "band and one fitted outside it are two different models",
    "meetings_per_year": 6,
    "schedule_rule": (
        "Six scheduled MPC meetings a year, announced at a press conference on the final day, "
        "normally late in the month. GMT is UTC+0 ALL YEAR and Ghana observes no daylight "
        "saving, so a Ghanaian announcement's UTC time is its local time -- the simplest clock "
        "in this civilization, and worth stating because it is the exception."),
    "timezone": "GMT = UTC+0 all year, no DST. Ghana sits on the prime meridian and on the "
                "equator's doorstep; local time IS UTC.",
    "fx_operations": (
        "Reserve sales, FX forward auctions to banks and the bulk-oil-distributor window. THE "
        "DISTINCTIVE ONE IS THE DOMESTIC GOLD PURCHASE PROGRAMME: from 2021 the Bank of Ghana "
        "has bought gold from domestic producers in cedis and added it to reserves, which turns "
        "a DOMESTIC commodity into an EXTERNAL reserve without the cedi ever touching the FX "
        "market. That is a genuinely unusual reserve-accumulation channel and it makes the gold "
        "price a Ghanaian monetary variable rather than only a terms-of-trade one."),
    "gold_for_oil": (
        "From early 2023 Ghana ran a GOLD-FOR-OIL barter arrangement: gold bought domestically "
        "was used to pay for refined petroleum imports, removing the largest single source of "
        "dollar demand from the interbank market. Whether it worked is contested; WHAT MATTERS "
        "FOR THIS PACK IS THAT IT IS A DATED, ANNOUNCED, QUANTIFIED CHANGE IN THE SHAPE OF FX "
        "DEMAND, which is a regime boundary whatever one thinks of the policy."),
    "publication_classes": ("MPC press release and Monetary Policy Report",
                            "Summary of Economic and Financial Data (monthly)",
                            "interbank reference rate (daily)",
                            "Annual Report", "Banking Sector Report"),
    "decision_dates": {
        2024: ("2024-01-29", "2024-03-25", "2024-05-27", "2024-07-29", "2024-09-27",
               "2024-11-25"),
        2025: ("2025-01-27", "2025-03-28", "2025-05-23", "2025-07-30", "2025-09-17",
               "2025-11-24"),
        2026: ("2026-01-26", "2026-03-23", "2026-05-25", "2026-07-27", "2026-09-21",
               "2026-11-23"),
    },
    "decision_dates_status": {
        2024: "PUBLIC_RECORD",
        2025: "PUBLIC_RECORD",
        2026: "RULE_DERIVED_UNVERIFIED -- the six-meeting, late-in-alternate-month pattern "
              "projected forward. THE DATA PLANE MUST REPLACE THESE WITH THE PUBLISHED CALENDAR "
              "BEFORE ANY 2026 EVENT STUDY IS SCORED. Note that the projected 2026-09-21 falls "
              "on Kwame Nkrumah Memorial Day, which is a public holiday -- exactly the kind of "
              "collision a guessed calendar produces and a published one resolves.",
    },
    "decision_time_utc": "approximately 10:00-12:00; OBSERVED, not nominal",
    "cfa_zone": {
        "bceao": {
            "name": "Banque Centrale des Etats de l'Afrique de l'Ouest (BCEAO)",
            "union": "UEMOA / WAEMU",
            "currency": "XOF",
            "members": ("Cote d'Ivoire", "Senegal", "Mali", "Burkina Faso", "Benin", "Togo",
                        "Niger", "Guinea-Bissau"),
            "policy_rate": "the taux directeur, set by the Comite de Politique Monetaire",
            "framework": "peg",
            "note": "COTE D'IVOIRE IS THE ONE THAT MATTERS HERE: the world's largest cocoa "
                    "producer, and its guaranteed farmgate price is set in a euro-pegged "
                    "currency for a whole season.",
        },
        "beac": {
            "name": "Banque des Etats de l'Afrique Centrale (BEAC)",
            "union": "CEMAC",
            "currency": "XAF",
            "members": ("Cameroon", "Gabon", "Congo", "Chad", "Central African Republic",
                        "Equatorial Guinea"),
            "framework": "peg",
            "note": "The oil-exporting half of the CFA zone, and therefore the half whose "
                    "reserve position moves with Brent while its exchange rate cannot.",
        },
        "the_peg": (
            "655.957 CFA francs to the euro, FIXED. It descends from 1 EUR = 6.55957 French "
            "francs at the euro's creation and from the 1994 devaluation before that, when the "
            "rate went from 50 to 100 CFA per French franc in a single step. THE 1994 STEP IS "
            "THE WHOLE TAIL RISK OF THIS ZONE: the peg has held for three decades, it is "
            "treaty-backed, and it HAS been moved once. A model that treats it as riskless is "
            "wrong in the only state that matters; a model that treats it as a floating currency "
            "is wrong in every other state."),
        "the_2019_reform": (
            "The 2019-2020 UEMOA reform (the 'Eco' agreement): the operations account at the "
            "French Treasury was closed, French representation on the BCEAO's organs was "
            "removed, and the reserve-pooling requirement changed. THE PEG TO THE EURO WAS NOT "
            "CHANGED. This is repeatedly reported as though the currency had been replaced, and "
            "it was not -- a study that treats the reform as a regime change in the EXCHANGE "
            "RATE is measuring an institutional change in the GUARANTEE."),
        "the_political_tail": (
            "The Alliance of Sahel States (Mali, Burkina Faso, Niger) announced withdrawal from "
            "ECOWAS in 2024-2025 and has discussed leaving the monetary union. NONE OF THE THREE "
            "IS A MAJOR COCOA PRODUCER, so the direct commodity effect is small; the effect that "
            "matters is on the ZONE'S PERCEIVED PERMANENCE, which is what makes the peg's tail "
            "risk a live variable rather than a historical footnote."),
    },
    "notes": "Ghana defaulted on its external debt in December 2022, ran a Domestic Debt Exchange "
             "Programme in early 2023, entered an IMF programme in May 2023 and completed a "
             "eurobond restructuring in 2024. THE STAGES ARE ALL DATED AND ANNOUNCED, which "
             "makes this the most completely documented frontier restructuring of the decade and "
             "a rare clean event grid for frontier credit.",
}


# --------------------------------------------------------------------------- fixings
FIXING_CONVENTIONS: dict[str, Any] = {
    "bog_interbank_reference": {
        "name": "Bank of Ghana interbank reference exchange rate",
        "publisher": "Bank of Ghana",
        "definition": "the daily reference rate computed from interbank transactions",
        "published_local": "each business day",
        "published_utc": "GMT IS UTC, so the local publication time IS the UTC time -- the one "
                         "country in this civilization where no conversion is needed",
        "note": "The retail bank counter rate and the forex-bureau rate both sit away from this "
                "reference, and the GAP between the reference and the bureau rate is Ghana's "
                "version of a parallel premium -- smaller than Nigeria's and real.",
    },
    "cfa_peg": {
        "name": "the CFA franc's fixed parity",
        "rate": "655.957 XOF or XAF per EUR, fixed",
        "definition": "a treaty-backed hard peg, unchanged since the euro's creation",
        "why_it_matters": "THE CFA ZONE'S DOLLAR TERMS OF TRADE ARE EURUSD, BY CONSTRUCTION. A "
                          "cocoa farmer in Cote d'Ivoire paid a fixed XOF price receives a "
                          "dollar value that moves one-for-one with EURUSD and with nothing "
                          "else. That is not an approximation or a correlation; it is "
                          "arithmetic, and it is the cleanest FX-to-real-economy transmission "
                          "available anywhere in this civilization.",
        "tail": "the peg has been moved exactly once, in January 1994, by 50%. Carried as a TAIL, "
                "not as a price.",
    },
    "cocoa_farmgate": {
        "name": "the two guaranteed farmgate prices",
        "ghana": "COCOBOD announces a producer price in CEDIS for the season, normally at the "
                 "start of the main crop in September or October, and it is a political as well "
                 "as an economic announcement",
        "cote_divoire": "the Conseil du Cafe-Cacao announces a prix garanti au producteur in "
                        "XOF, per season, for the main crop (October) and the mid-crop (April)",
        "why_this_is_a_fixing": "BECAUSE IT IS ONE. Both are administratively SET prices, "
                                "announced on a date, fixed for a season, in two different "
                                "currencies -- one floating and one euro-pegged. Everything in "
                                "this pack's flagship mechanism follows from that asymmetry.",
    },
    "deliverability": "NEITHER CURRENCY IS QUOTED HERE. The cedi is not deliverable offshore and "
                      "the CFA franc has no independent price. Every mechanism must be carried.",
    "dst": "NONE anywhere in this pack. Ghana is GMT year-round and the CFA zone spans UTC+0 and "
           "UTC+1 with no daylight saving.",
}


# --------------------------------------------------------------------------- settlement
SETTLEMENT_CONVENTIONS: dict[str, Any] = {
    "spot": "T+2 in the Ghanaian interbank market; the CFA zone settles through the BCEAO and "
            "BEAC systems with no FX leg against the euro, since the parity is fixed",
    "equity_settlement": "T+3 at the Ghana Stock Exchange; T+3 at the BRVM in Abidjan",
    "cocoa_season": "THE COCOA CALENDAR IS THE PACK'S REAL SETTLEMENT CYCLE. The main crop runs "
                    "from October to about March and the mid-crop from April to September; the "
                    "farmgate prices are announced at the start of each. Purchases, exports and "
                    "the forward-sale programme all key off it, and any cocoa study that uses "
                    "calendar quarters instead of crop years is aggregating across the "
                    "announcement that drives the whole mechanism.",
    "cocobod_syndication": "THE ANNUAL PRE-EXPORT FINANCE FACILITY. COCOBOD has historically "
                           "raised a syndicated offshore loan each September or October against "
                           "forward cocoa sales, of the order of a billion dollars, to fund the "
                           "season's purchases. IT IS A SCHEDULED, ANNOUNCED, QUANTIFIED FX "
                           "INFLOW -- one of very few in frontier Africa -- and when it shrank "
                           "or was replaced by domestic financing in the 2022-2024 seasons, the "
                           "absence was itself the event.",
    "forward_sales": "COCOBOD and the Conseil du Cafe-Cacao both FORWARD-SELL a large share of "
                     "the coming crop before it is harvested, which means the farmgate price is "
                     "set against prices struck months earlier. A ROLL-FORWARD LAG SITS BETWEEN "
                     "the world price and the farmgate price, and the length of that lag is why "
                     "a farmgate announcement can look disconnected from the spot market on the "
                     "day it is made.",
    "month_end": "importer and corporate demand concentrates at month end as elsewhere; in "
                 "Ghana's thinner market that concentration is a larger share of total volume",
    "fiscal_cycle": "Ghana's budget year is the calendar year, with the Budget Statement "
                    "presented in November for the year ahead and a mid-year review in July",
}


# --------------------------------------------------------------------------- exchanges
EXCHANGES: dict[str, Any] = {
    "cash": {
        "name": "Ghana Stock Exchange (GSE)",
        "hours_local": "09:30-15:00 GMT",
        "hours_utc": "09:30-15:00 (GMT IS UTC)",
        "settlement": "T+3",
        "index_symbols": (),
        "index_symbols_note": "the GSE Composite is not quoted on this account and is named in "
                              "ABSENT_INSTRUMENTS with no carrier claimed",
    },
    "regional": {
        "name": "Bourse Regionale des Valeurs Mobilieres (BRVM), Abidjan",
        "covers": "the eight UEMOA member states on one exchange",
        "why_it_is_here": "a SINGLE exchange serving eight countries that share a currency is an "
                          "unusual object, and its composite is the only market-priced read on "
                          "the UEMOA bloc. Not quoted here; carried as an observable.",
    },
    "commodity_boards": {
        "name": "COCOBOD (Ghana) and the Conseil du Cafe-Cacao (Cote d'Ivoire)",
        "role": "state marketing boards that BUY the crop at an announced price, forward-sell it "
                "offshore, and publish their purchases",
        "why_they_matter": "THEY ARE NOT EXCHANGES AND THEY ARE THE PRICE-SETTING INSTITUTIONS "
                           "THAT MATTER. Between them they intermediate most of the world's "
                           "cocoa, they publish purchase volumes, and the two announced farmgate "
                           "prices in two different currencies are the pack's flagship "
                           "mechanism. An analysis that models cocoa supply as a competitive "
                           "market has modelled the wrong institution.",
    },
    "derivatives": {
        "status": "NO liquid domestic derivative reaches this desk in Ghana or the CFA zone. The "
                  "price discovery for both countries' output happens on ICE London and ICE New "
                  "York -- WHICH THE DESK DOES TRADE, as UKCOCOA and USCOCOA. That is the "
                  "unusual and fortunate part of this pack: the local institutions are opaque "
                  "and the instrument they feed is liquid and quoted here.",
    },
}


FISCAL_YEAR_END: dict[str, str] = {
    "government": "31 December. The Budget Statement is presented to Parliament in November for "
                  "the year ahead, with a mid-year fiscal policy review in July.",
    "corporate": "31 December for most listed companies",
    "cocoa_year": "THE ONE THAT ACTUALLY MATTERS: the cocoa year runs 1 October to 30 September, "
                  "and it is the cycle the farmgate announcement, the syndicated loan and the "
                  "forward-sale programme all key off. A fiscal-year seasonal in this pack is "
                  "almost always a COCOA-year seasonal wearing the wrong label.",
    "cfa_zone": "31 December across UEMOA and CEMAC",
}


# --------------------------------------------------------------------------- holidays
#: Ghana's Public Holidays Act with the substitution practice applied: unlike South Africa and
#: Kenya, GHANA SUBSTITUTES BOTH SATURDAY AND SUNDAY holidays to the following Monday, by
#: Presidential declaration. The Islamic days are declared and moon-dependent and say so in their
#: own name strings. Farmers' Day is the FIRST FRIDAY OF DECEMBER -- a computed date, and a
#: genuinely apt national holiday for a country whose main export is a crop.
_GH_HOLIDAYS: dict[int, dict[str, str]] = {
    2024: {
        "2024-01-01": "New Year's Day",
        "2024-01-08": "Constitution Day observed (7 January fell on a Sunday)",
        "2024-03-06": "Independence Day",
        "2024-03-29": "Good Friday",
        "2024-04-01": "Easter Monday",
        "2024-04-10": "Eid al-Fitr (moon-dependent; declared)",
        "2024-05-01": "May Day",
        "2024-06-17": "Eid al-Adha (moon-dependent; declared)",
        "2024-08-05": "Founders' Day observed (4 August fell on a Sunday)",
        "2024-09-23": "Kwame Nkrumah Memorial Day observed (21 September fell on a Saturday)",
        "2024-12-06": "Farmers' Day (the first Friday of December)",
        "2024-12-25": "Christmas Day",
        "2024-12-26": "Boxing Day",
    },
    2025: {
        "2025-01-01": "New Year's Day",
        "2025-01-07": "Constitution Day",
        "2025-03-06": "Independence Day",
        "2025-03-31": "Eid al-Fitr (moon-dependent; declared)",
        "2025-04-18": "Good Friday",
        "2025-04-21": "Easter Monday",
        "2025-05-01": "May Day",
        "2025-06-06": "Eid al-Adha (moon-dependent; declared)",
        "2025-08-04": "Founders' Day",
        "2025-09-22": "Kwame Nkrumah Memorial Day observed (21 September fell on a Sunday)",
        "2025-12-05": "Farmers' Day (the first Friday of December)",
        "2025-12-25": "Christmas Day",
        "2025-12-26": "Boxing Day",
    },
    2026: {
        "2026-01-01": "New Year's Day",
        "2026-01-07": "Constitution Day",
        "2026-03-06": "Independence Day",
        "2026-03-20": "Eid al-Fitr (moon-dependent; ESTIMATE, not gazetted)",
        "2026-04-03": "Good Friday",
        "2026-04-06": "Easter Monday",
        "2026-05-01": "May Day",
        "2026-05-27": "Eid al-Adha (moon-dependent; ESTIMATE, not gazetted)",
        "2026-08-04": "Founders' Day",
        "2026-09-21": "Kwame Nkrumah Memorial Day",
        "2026-12-04": "Farmers' Day (the first Friday of December)",
        "2026-12-25": "Christmas Day",
        "2026-12-28": "Boxing Day observed (26 December falls on a Saturday)",
    },
}

HOLIDAYS_RULE: dict[str, Any] = {
    "rule": (
        "The Public Holidays Act, as amended. THREE LAYERS PLUS A COMPUTED ONE. (1) FIXED "
        "GREGORIAN: 1 January, 7 January (Constitution Day), 6 March (INDEPENDENCE DAY -- the "
        "first African country south of the Sahara to gain independence, and the national day), "
        "1 May (May Day), 4 August (Founders' Day), 21 September (Kwame Nkrumah Memorial Day), "
        "25 December and 26 December. (2) MOVEABLE CHRISTIAN: Good Friday and Easter Monday. "
        "(3) MOVEABLE ISLAMIC, DECLARED AND MOON-DEPENDENT: Eid al-Fitr and Eid al-Adha. "
        "(4) COMPUTED: FARMERS' DAY, the FIRST FRIDAY OF DECEMBER -- a national holiday for "
        "agriculture, which for a cocoa economy is not ceremonial. SUBSTITUTION: unlike South "
        "Africa and Kenya, GHANA SUBSTITUTES BOTH SATURDAY AND SUNDAY holidays to the following "
        "Monday by Presidential declaration, which is why 2024-09-23, 2024-08-05, 2025-09-22 "
        "and 2026-12-28 appear in these tables. The declaration is DISCRETIONARY rather than "
        "automatic, so a substitution is recorded when it is declared and never assumed forward. "
        "THE CFA ZONE KEEPS ITS OWN CALENDARS: Cote d'Ivoire's is French-derived plus Islamic "
        "and Christian days, and a Ghanaian closure does not close Abidjan -- which matters, "
        "because the pack's flagship mechanism spans that border."),
    "authority": "the Public Holidays Act and Presidential declarations published in the Ghana "
                 "Gazette; the GSE publishes its own trading calendar",
    "table": _GH_HOLIDAYS,
    "status": {
        2024: "GAZETTED for the Gregorian, computed and Christian days; Islamic days as declared",
        2025: "GAZETTED for the Gregorian, computed and Christian days; Islamic days as declared",
        2026: "MIXED. The Gregorian days are statutory and certain; Farmers' Day is computed "
              "(the first Friday of December 2026 is 2026-12-04); the Christian days follow from "
              "Easter Sunday 2026-04-05. THE ISLAMIC DAYS ARE HIJRI ESTIMATES AND ARE NOT "
              "GAZETTED and may move a day either way. The 2026-12-28 substitution is the "
              "expected application of the Monday rule and is not yet declared.",
    },
    "market_effect": (
        "NOTHING GHANAIAN OR IVORIAN IS QUOTED ON THIS ACCOUNT, so a closure here is an "
        "OBSERVABILITY OUTAGE: no BoG reference rate, no GSE print, no COCOBOD purchase update. "
        "A MISSING DAY IS NOT A ZERO. But this pack has a sharper case than the others, and it "
        "is the reason the CFA calendars are named above: GHANA AND COTE D'IVOIRE DO NOT SHARE A "
        "HOLIDAY CALENDAR. When Accra is shut and Abidjan is open, the two sides of the pack's "
        "flagship border mechanism are observed on different days -- so a naive daily join of "
        "the two countries' data silently pairs an observation with a non-observation, and the "
        "apparent cross-border divergence that results is a calendar artefact rather than a "
        "supply signal. Meanwhile UKCOCOA and USCOCOA trade through both closures on the London "
        "and New York calendars, which are a third calendar again."),
    "callable": "countries.gh.pack:holidays",
}


def holidays(year: int) -> dict[str, str]:
    """Ghana's closure table for one year, `{"YYYY-MM-DD": name}`. `{}` if untabulated."""
    return holiday_table(HOLIDAYS_RULE, year)


# --------------------------------------------------------------------------- custom miners
def gh_farmers_day(year: int) -> dict[str, Any]:
    """Farmers' Day: the first Friday of December, computed rather than tabulated.

    A COMPUTABLE RULE SHOULD BE CODE AND NOT A TABLE, because a table rots at the end of the
    years somebody typed. It is also the national holiday most specific to this pack's subject: a
    cocoa economy that closes for agriculture.
    """
    first = date(int(year), 12, 1)
    offset = (4 - first.weekday()) % 7  # Friday = 4
    day = date(int(year), 12, 1 + offset)
    return {"year": int(year), "date": day.isoformat(),
            "rule": "the first Friday of December",
            "in_table": day.isoformat() in holidays(int(year)),
            "note": "computed, not tabulated; the table is checked against it so a typo in one "
                    "shows up as a disagreement rather than as a silently wrong date"}


def gh_cocoa_border_incentive(gh_farmgate_per_tonne_usd: float | None,
                              ci_farmgate_per_tonne_usd: float | None) -> dict[str, Any]:
    """THE PACK'S FLAGSHIP CALCULATION: which side of the border pays more for the same bean.

    Both marketing boards announce a guaranteed farmgate price for the season -- Ghana's in
    floating cedis, Cote d'Ivoire's in euro-pegged CFA francs. Converted to a common currency the
    two are directly comparable, and the GAP is the incentive to carry beans across the border.
    When the cedi depreciates against the euro mid-season, Ghana's announced price falls in
    dollar terms while Cote d'Ivoire's does not -- so the gap moves WITHOUT EITHER BOARD
    ANNOUNCING ANYTHING, which is exactly what makes the mechanism testable: the driver is an
    exchange rate and the consequence is a physical supply reallocation.

    Returns the gap in per cent with the implied direction of flow. A missing leg is UNMEASURED
    by name -- a farmgate price that has not been announced is not a price of zero, and in a
    season where one board delays its announcement the gap is genuinely unknown.
    """
    try:
        gh = float(gh_farmgate_per_tonne_usd) if gh_farmgate_per_tonne_usd is not None else None
        ci = float(ci_farmgate_per_tonne_usd) if ci_farmgate_per_tonne_usd is not None else None
    except (TypeError, ValueError):
        return {"status": "UNMEASURED", "why": "NON_NUMERIC",
                "detail": "a farmgate price was not a number"}
    if gh is None or ci is None:
        missing = "Ghana" if gh is None else "Cote d'Ivoire"
        return {"status": "UNMEASURED", "why": "MISSING_FARMGATE",
                "detail": f"the {missing} farmgate price was not supplied; an unannounced "
                          f"season price is UNMEASURED and is never a zero"}
    if gh <= 0 or ci <= 0:
        return {"status": "UNMEASURED", "why": "NON_POSITIVE_PRICE",
                "detail": f"gh={gh} ci={ci}; a non-positive farmgate price cannot form a ratio"}
    gap = 100.0 * (gh - ci) / ci
    return {
        "status": "OK", "gh_usd_per_tonne": gh, "ci_usd_per_tonne": ci, "gap_pct": gap,
        "implied_flow": ("BEANS_TOWARD_GHANA" if gap > 0 else
                         "BEANS_TOWARD_COTE_DIVOIRE" if gap < 0 else "NEUTRAL"),
        "mechanism": "the higher-paying side attracts cross-border movement of the identical "
                     "crop, reallocating deliverable supply between two marketing boards and "
                     "two exchange contracts",
        "why_it_moves_without_news": "Cote d'Ivoire's price is fixed in a EURO-PEGGED currency "
                                     "for the season and Ghana's is fixed in a FLOATING one, so "
                                     "a cedi move against the euro changes the gap with no "
                                     "announcement from either board",
        "controls": ("seasons in which both boards announced at the same time and the cedi was "
                     "stable, which should show no gap movement",
                     "the world price itself, which moves both boards' economics together and "
                     "must be removed first",
                     "randomised assignment of the gap's sign"),
    }


CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    miner("gh_farmers_day_calendar",
          domain_ids=("gh_cocoa_season_calendar", "gh_holiday_observability"),
          kind="calendar",
          entry="countries.gh.pack:gh_farmers_day",
          cadence_s=86400.0,
          steerable=False,
          notes="A computable rule kept as code so it cannot rot past the years somebody typed, "
                "and cross-checked against the table so a typo shows up as a disagreement."),
    miner("gh_cocoa_border_incentive",
          domain_ids=("gh_cocoa_farmgate_asymmetry", "gh_cross_border_supply"),
          kind="mechanism",
          entry="countries.gh.pack:gh_cocoa_border_incentive",
          cadence_s=86400.0,
          steerable=True,
          notes="THE PACK'S FLAGSHIP. Two announced administrative prices in two currencies, one "
                "pegged and one floating, over one border, feeding two contracts the desk "
                "trades."),
)


# --------------------------------------------------------------------------- positioning
#: NEITHER GHANA NOR THE CFA ZONE HAS POSITIONING DATA, and this tuple says so by name. What
#: stands in is unusually good for a satellite pack, because the COCOA CONTRACTS THEMSELVES have
#: a CFTC report -- so the positioning that matters for this pack's flagship mechanism is
#: measurable even though neither country's currency is.
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"id": "cftc_cot_cocoa",
     "name": "CFTC Commitments of Traders -- cocoa (ICE US contract)",
     "covers": "non-commercial and commercial positioning in the cocoa future",
     "frequency": "weekly (Tuesday snapshot)",
     "lag": "published Friday 15:30 ET",
     "root": "cftc.gov Commitments of Traders",
     "licence": "free, public",
     "availability": "YES, AND IT IS THE POSITIONING THAT MATTERS HERE. The pack's flagship "
                     "mechanism terminates in UKCOCOA and USCOCOA, so the speculative "
                     "positioning in the TARGET is measurable even though neither producing "
                     "country's currency is. That is the reverse of the usual frontier problem.",
     "desk_status": "check desks/mt5/data/axes/cot.json for whether the cocoa contract is mapped "
                    "on this box; an unmapped contract is UNMEASURED by name, not absent"},
    {"id": "cftc_cot_ghs_xof",
     "name": "CFTC Commitments of Traders -- cedi or CFA franc",
     "availability": "DOES NOT EXIST for either currency. No CME contract, therefore no COT "
                     "report. South Africa remains the only country in this civilization with a "
                     "currency positioning series.",
     "covers": "n/a", "frequency": "n/a", "lag": "n/a",
     "root": "cftc.gov (checked; no cedi or CFA contract)",
     "licence": "n/a",
     "desk_status": "DECLARED ABSENT"},
    {"id": "cocobod_purchases",
     "name": "COCOBOD graded and sealed purchases",
     "covers": "cumulative cocoa purchases by the Ghanaian marketing board for the season",
     "frequency": "periodic during the season", "lag": "weeks",
     "root": "cocobod.gh and Ghanaian press reporting of board statements",
     "licence": "free, public but irregularly published",
     "desk_status": "THE PHYSICAL COUNTERPART TO THE FARMGATE PRICE. A season in which purchases "
                    "fall far short of the crop estimate is the direct evidence of beans leaving "
                    "by another route. Publication is irregular, so it is marked "
                    "pit_feasible=False rather than treated as a clean series."},
    {"id": "ccc_arrivals",
     "name": "Conseil du Cafe-Cacao port arrivals, Cote d'Ivoire",
     "covers": "cumulative cocoa arrivals at Abidjan and San Pedro",
     "frequency": "weekly during the season", "lag": "days",
     "root": "conseilcafecacao.ci and exporter estimates carried by the French-language press",
     "licence": "free, public; exporter estimates are commentary",
     "desk_status": "THE BEST HIGH-FREQUENCY PHYSICAL COCOA SERIES IN THE WORLD, and it is "
                    "published in French. Weekly port arrivals in the largest producing country "
                    "are the closest thing the cocoa market has to a supply nowcast -- and the "
                    "OTHER SIDE of the border mechanism: beans that left Ghana arrive here."},
    {"id": "icco_forecasts",
     "name": "International Cocoa Organization quarterly bulletin and supply-demand estimates",
     "covers": "world production, grindings and the surplus or deficit estimate",
     "frequency": "quarterly", "lag": "weeks",
     "root": "icco.org",
     "licence": "summary free; the full bulletin is a paid publication and is NOT redistributed",
     "desk_status": "the market's reference balance. Its revisions are events in themselves."},
    {"id": "bog_reserves_gold",
     "name": "Bank of Ghana reserves and the domestic gold purchase programme",
     "covers": "gross international reserves and the gold holding built from domestic purchases",
     "frequency": "monthly", "lag": "weeks",
     "root": "bog.gov.gh Summary of Economic and Financial Data",
     "licence": "free, public",
     "desk_status": "AN UNUSUAL RESERVE CHANNEL: gold bought domestically in cedis becomes an "
                    "external reserve without the cedi touching the FX market, which makes the "
                    "gold price a Ghanaian MONETARY variable and not only a terms-of-trade one."},
)


# --------------------------------------------------------------------------- terminology
#: NATIVE TERMS, KEYED BY DOMAIN. English is Ghana's official language; TWI is the language of
#: the cocoa-growing regions and of the farmgate conversation; and FRENCH IS NOT OPTIONAL, because
#: half this pack is the CFA zone and the Conseil du Cafe-Cacao, the BCEAO and the Ivorian press
#: publish in French only. An English-only miner covering West African cocoa is reading one side
#: of a two-sided mechanism.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "core": ("cedi", "sika", "dɔla", "boɔ", "adwadie", "franc CFA", "taux de change",
             "dollar", "exchange rate", "price"),
    "gh_cocoa_farmgate_asymmetry": ("kokoo", "kokoo boɔ", "akuafoɔ", "COCOBOD",
                                    "producer price", "farmgate price", "prix garanti au "
                                    "producteur", "campagne cacaoyère", "Conseil du Café-Cacao",
                                    "prix bord champ", "fèves de cacao"),
    "gh_cross_border_supply": ("smuggling", "cross-border", "kokoo a wɔfa kɔ", "contrebande",
                               "traversée de la frontière", "fuite du cacao", "beans diverted",
                               "Ivorian border", "Elubo", "Noé"),
    "gh_cocoa_season_calendar": ("main crop", "mid-crop", "light crop", "campagne principale",
                                 "campagne intermédiaire", "traite", "récolte", "otwa berɛ",
                                 "harvest", "forward sales", "vente à terme"),
    "gh_gold_production": ("sika futuro", "sikakɔkɔɔ", "galamsey", "small-scale mining",
                           "gold export", "PMMC", "Minerals Commission", "or", "orpaillage",
                           "gold dore", "domestic gold purchase programme"),
    "gh_fx_and_premium": ("cedi depreciation", "sika no aba fam", "forex bureau rate",
                          "interbank reference rate", "black market cedi", "dépréciation",
                          "taux du marché parallèle", "Bank of Ghana rate"),
    "gh_sovereign_restructuring": ("DDEP", "domestic debt exchange", "haircut", "default",
                                   "restructuring", "IMF programme", "bondholders",
                                   "restructuration de la dette", "Eurobond", "moratorium"),
    "gh_policy_reaction": ("Monetary Policy Committee", "policy rate", "Bank of Ghana",
                           "sikakorabea kɛseɛ", "inflation", "Cash Reserve Ratio",
                           "taux directeur", "BCEAO", "Comité de Politique Monétaire"),
    "cfa_peg_and_reform": ("franc CFA", "parité fixe", "655,957", "arrimage à l'euro", "l'Eco",
                           "compte d'opérations", "Trésor français", "UEMOA", "CEMAC",
                           "BCEAO", "BEAC", "dévaluation de 1994", "réserves de change"),
    "cfa_political_tail": ("Alliance des États du Sahel", "AES", "retrait de la CEDEAO",
                           "sortie du franc CFA", "souveraineté monétaire", "ECOWAS withdrawal",
                           "monetary sovereignty"),
    "gh_energy_and_barter": ("gold-for-oil", "sika ne ngo", "bulk oil distributors", "BOST",
                             "Jubilee field", "TEN field", "petroleum revenue",
                             "pétrole", "importation de carburant"),
    "gh_weather_and_crop": ("nsuo", "osuo", "harmattan", "black pod", "swollen shoot",
                            "pluie", "saison sèche", "maladie du cacaoyer", "rainfall",
                            "drought", "crop disease"),
    "gh_retail_and_apps": ("mobile money", "MoMo", "sika a ɛwɔ fon so", "forex bureau",
                           "Ghana Card", "e-levy", "remittance", "transfert d'argent"),
    "gh_food_and_inflation": ("aduane boɔ", "food inflation", "gari", "maize price",
                              "cost of living", "coût de la vie", "cherté de la vie"),
}


# --------------------------------------------------------------------------- source classes
#: THE TEN LAYERS (principal's per-country depth rule, 2026-09-17). Exactly one per source, and
#: every layer either covered or DECLARED ABSENT WITH A REASON -- never blank. This pack is the
#: one where the rule most obviously changes the answer: the official layer is Anglophone and the
#: mechanism is bilingual, so a Ghana "covered" by Bank of Ghana and COCOBOD is a Ghana with only
#: one side of its own border in view.
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
    measurement. `queries` are NATIVE-LANGUAGE and are not translations: the Ivorian farmgate
    announcement is a "prix garanti au producteur" and no amount of English searching finds it.
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
    _src("gh_official_cb", "The Bank of Ghana and the Ministry of Finance",
         layer="official",
         roots=("bog.gov.gh", "bog.gov.gh/economic-data/",
                "bog.gov.gh/monetary-policy/mpc-press-releases/",
                "mofep.gov.gh", "ghanastatistics-gss.org"),
         languages=("en",),
         licence="free, public",
         access_label="OPEN_DATA", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         queries=("Bank of Ghana interbank reference rate daily", "MPC press release policy "
                  "rate Ghana", "Summary of Economic and Financial Data", "gross international "
                  "reserves Ghana monthly", "domestic gold purchase programme reserves"),
         notes="GMT IS UTC, so the publication time needs no conversion -- the one country in "
               "this civilization where that is true. The reserves series is where the DOMESTIC "
               "GOLD PURCHASE PROGRAMME shows up, which is the channel that makes the gold price "
               "a Ghanaian monetary variable."),
    _src("cfa_official_cb", "BCEAO and BEAC -- the two CFA central banks",
         layer="official",
         roots=("bceao.int", "bceao.int/fr/statistiques", "beac.int",
                "uemoa.int", "cemac.int"),
         languages=("fr",),
         licence="free, public; the statistical portals are open",
         access_label="OPEN_DATA", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         queries=("BCEAO taux directeur décision", "BCEAO statistiques réserves de change",
                  "avoirs extérieurs nets UEMOA", "BEAC politique monétaire CEMAC",
                  "parité franc CFA euro 655,957"),
         notes="PUBLISHED IN FRENCH ONLY, which is the whole reason French is in "
               "NATIVE_LANGUAGES. The BCEAO's reserve and net-foreign-asset series are the "
               "measurable part of the peg's credibility -- the parity itself never moves, so "
               "ALL the information is in the reserve position behind it."),
    _src("gh_cocoa_boards", "COCOBOD and the Conseil du Cafe-Cacao",
         layer="institutional",
         roots=("cocobod.gh", "conseilcafecacao.ci", "icco.org",
                "ghanacocoaboard announcements carried by the national press",
                "Ivorian exporter arrival estimates carried by the French-language wires"),
         languages=("en", "fr", "tw"),
         licence="free, public announcements; the ICCO's full quarterly bulletin is PAID and is "
                 "not redistributed",
         access_label="PUBLIC", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         queries=("prix garanti au producteur campagne cacaoyère", "COCOBOD producer price "
                  "announcement season", "arrivées de cacao aux ports ivoiriens",
                  "kokoo boɔ foforɔ", "graded and sealed purchases COCOBOD",
                  "syndicated pre-export finance facility cocoa"),
         notes="THE TWO PRICE-SETTING INSTITUTIONS THAT ACTUALLY MATTER, and neither is an "
               "exchange. Between them they intermediate most of the world's cocoa at "
               "administratively announced prices. An analysis that models cocoa supply as a "
               "competitive market has modelled the wrong institution."),
    _src("gh_exchange_and_regulators", "GSE, BRVM and the sector regulators",
         layer="institutional",
         roots=("gse.com.gh", "brvm.org", "sec.gov.gh", "petroleumcommission.gov.gh",
                "mincom.gov.gh (the Minerals Commission)", "npa.gov.gh"),
         languages=("en", "fr"),
         licence="free public summary tables",
         access_label="PUBLIC_WITH_TERMS", credibility="AUTHORITATIVE",
         predictive_state="UNTESTED",
         queries=("GSE Composite Index daily", "BRVM composite cours", "Minerals Commission "
                  "gold output quarterly", "Petroleum Commission Jubilee production",
                  "NPA petroleum price window"),
         notes="THE NPA ROW IS THE UNDERRATED ONE: Ghana's pump price is set in published "
               "fortnightly windows, so the pass-through from Brent and the cedi into the "
               "domestic fuel price is PUBLISHED with its inputs rather than estimated. A single "
               "regional exchange serving eight UEMOA states is also an unusual object and the "
               "only market-priced read on that bloc."),
    _src("gh_academic", "West African academic and policy literature, in both languages",
         layer="academic",
         roots=("isser.ug.edu.gh", "aercafrica.org", "papers.ssrn.com (cocoa marketing and West "
                "African FX)", "cires-ci.org (Cote d'Ivoire)",
                "ferdi.fr and cerdi.uca.fr (French research on the CFA zone)",
                "bog.gov.gh working papers"),
         languages=("en", "fr"),
         licence="mixed; institutional repositories open, journals often licensed. Never scrape "
                 "a paywall",
         access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("cocoa smuggling Ghana Cote d'Ivoire price differential",
                  "contrebande cacao frontière ivoiro-ghanéenne",
                  "zone franc CFA évaluation économique", "cocoa producer price pass-through",
                  "Ghana domestic debt exchange welfare effects"),
         notes="CERDI AND FERDI ARE THE SPECIALIST ROWS: decades of French academic work on the "
               "CFA zone that has no English equivalent, and which has already tested most of "
               "the obvious versions of this pack's peg mechanisms. THE CROSS-BORDER SMUGGLING "
               "LITERATURE IS THE DIRECT EXTERNAL CHECK on the pack's flagship claim."),
    _src("gh_practitioner", "West African professional market commentary",
         layer="practitioner",
         roots=("citinewsroom.com/business", "myjoyonline.com/business",
                "norvanreports.com", "sikaofficial.com",
                "Ivorian and regional commodity commentary carried by the French-language wires"),
         languages=("en", "fr"),
         licence="public web; mined for VERBATIM CLAIMS only, never for advice",
         access_label="PUBLIC", credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("cedi outlook after MPC Ghana", "cocoa syndicated loan season financing",
                  "perspectives campagne cacaoyère", "Ghana eurobond restructuring progress",
                  "gold export earnings Ghana monthly"),
         notes="The local business desks are where the COCOBOD syndication and the farmgate "
               "announcement are reported in a form with numbers in it, which the board's own "
               "site often does not carry promptly."),
    _src("gh_retail_ecology", "Ghanaian and Ivorian boards, in English, Twi and French",
         layer="retail_ecology",
         roots=("ghanaweb.com business and forum sections",
                "reddit.com/r/ghana (economy and cost-of-living threads)",
                "public X/Twitter threads on the cedi and the forex bureau rate",
                "public francophone forums and comment threads on the franc CFA",
                "farmer-facing Facebook groups discussing farmgate prices, described generically"),
         languages=("en", "tw", "fr"),
         licence="public web; mined for VERBATIM CLAIMS only, never for personal data and never "
                 "for advice",
         access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
         predictive_state="NARRATIVE_FEATURE",
         queries=("cedi rate forex bureau today", "sika no aba fam", "kokoo boɔ nnɛ",
                  "prix du cacao bord champ aujourd'hui", "franc CFA sortie débat",
                  "dollar rate Ghana black market"),
         notes="LOW WEIGHT, NEVER DROPPED. THE FARMGATE CONVERSATION HAPPENS IN TWI AND FRENCH, "
               "not in English, and farmers discussing whether the announced price is worth "
               "selling at is the leading edge of the cross-border mechanism -- the decision "
               "that produces the supply reallocation is made at that level, months before it "
               "shows up in a board's purchase statistics."),
    _src("gh_retail_fringe", "Fringe, contradicted and scam-adjacent public material",
         layer="retail_ecology",
         roots=("'CFA franc abolished next month' and imminent-devaluation claims",
                "Ghanaian Ponzi and forex-scheme collapse post-mortems",
                "SEC Ghana and Bank of Ghana public warnings on unlicensed operators",
                "galamsey and illegal-mining rumour threads"),
         languages=("en", "tw", "fr"),
         licence="public web; verbatim claims only, no personal data, no re-publication",
         access_label="PUBLIC_SOCIAL", credibility="FRINGE",
         predictive_state="NARRATIVE_FEATURE",
         queries=("franc CFA supprimé bientôt", "CFA devaluation rumour 2026",
                  "SEC Ghana warning unlicensed investment", "cedi to collapse prediction",
                  "galamsey gold smuggling report"),
         notes="KEPT ON PURPOSE AND WEIGHTED NEAR ZERO, AND FOR THIS PACK IT IS SUBSTANTIVE. "
               "'The CFA franc is about to be abolished' has been a recurring public claim for "
               "years and has been wrong every time -- WHICH IS PRECISELY WHAT MAKES THE RECORD "
               "VALUABLE: it is a continuous measurement of how much devaluation risk the "
               "region's own population perceives in a peg the market treats as riskless, and "
               "the peg HAS been moved once. Illegal-mining rumour threads are the only "
               "high-frequency read on gold output that never reaches an official statistic."),
    _src("gh_app_ecosystem", "Mobile money, forex-bureau apps and the remittance corridors",
         layer="app_ecosystem",
         roots=("public mobile-money tariff and transaction-limit pages for the Ghanaian "
                "operators", "public e-levy and transfer-charge documentation",
                "cedirates.com and comparable public rate-aggregator pages",
                "wave, sendwave and worldremit public corridor rates for Ghana and the UEMOA "
                "states",
                "app store and play store listings and public release notes for the above"),
         languages=("en", "fr"),
         licence="public listings, tariff schedules and documentation; no account creation, no "
                 "scraping behind a login, no personal data",
         access_label="PUBLIC_WITH_TERMS", credibility="UNRELIABLE", predictive_state="UNTESTED",
         queries=("cedi rates today forex bureau app", "MoMo transfer charges Ghana e-levy",
                  "Wave transfert Côte d'Ivoire tarif", "Sendwave Ghana rate today",
                  "taux de transfert franc CFA euro"),
         notes="THE REMITTANCE CORRIDOR APPS ARE THE INTERESTING ROW AND THEY MAKE A COMPARISON "
               "POSSIBLE THAT NOTHING ELSE DOES: the same operators post a Ghana corridor rate "
               "and a UEMOA corridor rate. One is into a floating currency and one into a "
               "euro-pegged one, from the same senders, at the same moment -- so the SPREAD "
               "BETWEEN THE TWO CORRIDORS is a retail-level measurement of exactly the monetary "
               "asymmetry this pack's flagship mechanism runs on. Credibility is UNRELIABLE "
               "because aggregator pages quote rather than transact."),
    _src("gh_media", "Ghanaian and Ivorian press, in three languages",
         layer="media",
         roots=("graphic.com.gh", "citinewsroom.com", "myjoyonline.com", "ghanaweb.com",
                "fratmat.info and abidjan.net (Cote d'Ivoire)",
                "rfi.fr/fr/afrique and jeuneafrique.com",
                "bbc.com/africa and Twi-language radio summaries"),
         languages=("en", "fr", "tw"),
         licence="public headlines and article text; respect robots and rate limits",
         access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("COCOBOD announces producer price", "le Conseil Café-Cacao fixe le prix bord "
                  "champ", "cedi depreciation news Ghana", "campagne cacao ouverture",
                  "Ghana IMF programme review disbursement", "galamsey crackdown gold"),
         notes="RFI AND JEUNE AFRIQUE ARE THE REGIONAL PAIR and they cover the CFA zone as a "
               "single subject, which no Anglophone outlet does. Abidjan.net and Fratmat carry "
               "the Ivorian farmgate and arrivals coverage the same day it is announced."),
    _src("gh_terms_restricted", "Sources whose terms forbid machine extraction",
         layer="media",
         roots=("the ICCO Quarterly Bulletin of Cocoa Statistics (a PAID publication)",
                "commercial cocoa and gold price-reporting services",
                "subscription-only West African research portals whose terms forbid automated "
                "access",
                "paywalled francophone press archives"),
         languages=("en", "fr"),
         licence="LICENSED or PUBLIC_WITH_TERMS where the terms explicitly forbid automated "
                 "extraction",
         access_label="ACCESS_UNCLEAR", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         machine_use_allowed=True,
         queries=("(none -- this row is REGISTERED AND NEVER QUERIED)",),
         notes="REGISTERED, NEVER SCRAPED, NEVER OMITTED. machine_use_allowed=True is the whole "
               "content of this row, and the ICCO bulletin is its painful member: it is the "
               "market's reference supply-demand balance and its terms do not permit machine "
               "use, so the desk works from the free summary and NAMES the gap rather than "
               "closing it improperly. Omitting the row would make the refusal invisible and "
               "would let a later session 'discover' the source and quietly breach the terms. "
               "ACCESS_UNCLEAR rather than LICENSED because the class is heterogeneous and some "
               "members' terms have not been individually read; AN UNREAD TERM IS NOT A "
               "PERMISSION."),
    _src("gh_archive", "Back editions, historical parities and captures of moved pages",
         layer="archive",
         roots=("bog.gov.gh annual report and statistical bulletin archive",
                "bceao.int archives des rapports annuels et notes d'information",
                "web.archive.org captures of cocobod.gh and conseilcafecacao.ci",
                "imf.org Ghana and Cote d'Ivoire Article IV archive",
                "historical CFA parity documentation including the January 1994 devaluation"),
         languages=("en", "fr"),
         licence="free, public archives",
         access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         queries=("dévaluation du franc CFA janvier 1994 documents",
                  "BCEAO rapport annuel archive", "COCOBOD producer price history by season",
                  "Ghana IMF Article IV archive", "web archive conseilcafecacao prix"),
         notes="THE LAYER THE PEG'S TAIL RISK LIVES IN. The CFA parity has moved exactly once "
               "and the only record of what that looked like -- the decision process, the "
               "magnitude, the aftermath -- is archival. A model of a thirty-year-stable peg "
               "fitted only on the stable period has no observations of the event it should be "
               "pricing, and this is the only place those observations exist. The farmgate price "
               "history by season is likewise archival: the boards publish the current season, "
               "not the series."),
    _src("gh_physical_economy", "Beans, ounces, barrels and rain",
         layer="physical_economy",
         roots=("conseilcafecacao.ci weekly port arrivals at Abidjan and San Pedro",
                "cocobod.gh graded and sealed purchases",
                "mincom.gov.gh and pmmc gold output and export statistics",
                "petroleumcommission.gov.gh Jubilee and TEN field production",
                "fews.net/west-africa", "chc.ucsb.edu (CHIRPS rainfall for the cocoa belt)",
                "ghanaports.gov.gh and Abidjan port authority throughput"),
         languages=("en", "fr"),
         licence="free, public; CHIRPS is open research data",
         access_label="OPEN_DATA", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         queries=("arrivées cacao ports ivoiriens cumul hebdomadaire",
                  "COCOBOD purchases season to date tonnes", "Ghana gold export ounces monthly",
                  "Jubilee field production barrels per day",
                  "CHIRPS rainfall anomaly cocoa belt West Africa",
                  "harmattan forecast cocoa West Africa"),
         notes="IVORIAN WEEKLY PORT ARRIVALS ARE THE BEST HIGH-FREQUENCY PHYSICAL COCOA SERIES "
               "IN THE WORLD, published in French, and they are also the OTHER SIDE of the "
               "border mechanism: beans that left Ghana arrive here. Pairing arrivals against "
               "COCOBOD purchases against the combined crop estimate is the direct measurement "
               "of the reallocation this pack exists to detect. The harmattan -- the dry "
               "Saharan wind -- is the region's characteristic crop risk and is forecastable."),
    _src("gh_source_graph", "How new West African sources are found, and what is refused",
         layer="source_graph",
         roots=("citation and data-annex trails in IMF Article IV reports for Ghana, Cote "
                "d'Ivoire, and the WAEMU and CEMAC regional consultations",
                "World Bank Ghana Economic Update and Cote d'Ivoire Economic Update references",
                "reference lists in CERDI, FERDI and AERC working papers",
                "outbound link graphs from bceao.int and bog.gov.gh",
                "ecowas.int and uemoa.int publication indexes",
                "the desk's own frontier map in desks/mt5/data/"),
         languages=("en", "fr"),
         licence="free, public",
         access_label="PUBLIC", credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("IMF WAEMU regional consultation staff report",
                  "IMF Article IV Côte d'Ivoire annexe statistique",
                  "World Bank Ghana Economic Update", "CERDI zone franc working paper"),
         notes="THE META-LAYER, AND THE ONE THAT KEEPS THE OTHER NINE FROM GOING STALE. THE "
               "WAEMU AND CEMAC REGIONAL CONSULTATIONS ARE THE HIGH-VALUE ENTRY POINT and have "
               "no national equivalent: the IMF assesses the monetary UNION as a unit, so its "
               "reserve-adequacy and peg-sustainability analysis is the closest thing to a "
               "published assessment of the parity's credibility. THIS ROW ALSO CARRIES THE "
               "REFUSALS: (1) any crypto-exchange venue order book, API or native feed is "
               "REFUSED (universe mandate 2026-08-18); (2) single-name GSE or BRVM hypothesis "
               "mining is REFUSED (two-lane order 2026-09-06) -- the listed gold miners are "
               "observables and never docket symbols; (3) redistribution of the ICCO bulletin or "
               "any commercial cocoa price-reporting service is REFUSED and is registered as its "
               "own row above rather than omitted."),
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
    dataset("gh_cocobod_producer_price",
            source="COCOBOD announced producer (farmgate) price, Ghana",
            coverage="the guaranteed price per tonne paid to Ghanaian farmers, per season, in "
                     "cedis",
            frequency="per season, with occasional mid-season revisions",
            publication_lag_days=0.0,
            revisions="a mid-season revision is a NEW ANNOUNCEMENT and a separate event, not a "
                      "restatement; both must be kept with their dates",
            licence="free, public announcement",
            history_from="the modern series covers several decades of seasons",
            pit_feasible=True,
            assets=("UKCOCOA", "USCOCOA"),
            mechanism_families=("commodity_production_sensor", "fx_regime_sensor",
                                "cross_border_arbitrage"),
            how_to_fetch="the announcement is made at the season opening in September or October "
                         "and is carried by the Ghanaian press the same day; record the "
                         "announcement timestamp, which is what was knowable"),
    dataset("ci_ccc_producer_price",
            source="Conseil du Cafe-Cacao prix garanti au producteur, Cote d'Ivoire",
            coverage="the guaranteed farmgate price per kilogram, per campaign, in XOF",
            frequency="twice per season (main crop October, mid-crop April)",
            publication_lag_days=0.0,
            revisions="each campaign's price is a separate announcement",
            licence="free, public announcement, IN FRENCH",
            history_from="the modern series covers several decades of campaigns",
            pit_feasible=True,
            assets=("UKCOCOA", "USCOCOA", "EURUSD"),
            mechanism_families=("commodity_production_sensor", "fx_regime_sensor",
                                "cross_border_arbitrage"),
            how_to_fetch="conseilcafecacao.ci and the French-language regional press; THE PRICE "
                         "IS IN A EURO-PEGGED CURRENCY, so its dollar value moves with EURUSD "
                         "and with nothing else between announcements -- which is the half of "
                         "the flagship mechanism that requires no local data at all"),
    dataset("ci_port_arrivals",
            source="Conseil du Cafe-Cacao and exporter estimates of cocoa arrivals at Abidjan "
                   "and San Pedro",
            coverage="cumulative weekly arrivals for the season, in tonnes",
            frequency="weekly during the season",
            publication_lag_days=3.0,
            revisions="exporter estimates are revised as official figures arrive; both are kept",
            licence="free, public; exporter estimates are commentary rather than official",
            history_from="2000s",
            pit_feasible=True,
            assets=("UKCOCOA", "USCOCOA"),
            mechanism_families=("commodity_production_sensor", "supply_shock"),
            how_to_fetch="the French-language wires carry the weekly cumulative figure; THIS IS "
                         "THE BEST HIGH-FREQUENCY PHYSICAL COCOA SERIES IN THE WORLD and it is "
                         "also the receiving end of any cross-border reallocation"),
    dataset("gh_cocobod_purchases",
            source="COCOBOD graded and sealed purchases",
            coverage="cumulative purchases by the Ghanaian board for the season, in tonnes",
            frequency="periodic during the season, irregular",
            publication_lag_days=21.0,
            revisions="restated as grading completes",
            licence="free, public but irregularly published",
            history_from="patchy",
            pit_feasible=False,
            assets=("UKCOCOA", "USCOCOA"),
            mechanism_families=("commodity_production_sensor", "cross_border_arbitrage"),
            how_to_fetch="board statements and press coverage. MARKED NOT_PIT_SAFE: publication "
                         "is irregular and a missing period is not a zero purchase. The GAP "
                         "between purchases and the crop estimate is the direct evidence of "
                         "beans leaving by another route, and it is exactly the series whose "
                         "irregularity limits the flagship test's frequency"),
    dataset("gh_bog_reference_rate",
            source="Bank of Ghana interbank reference exchange rate",
            coverage="the daily cedi reference rate against the majors",
            frequency="daily",
            publication_lag_days=1.0,
            revisions="not revised",
            licence="free, public",
            history_from="2000s",
            pit_feasible=True,
            assets=("UKCOCOA", "EURUSD", "USDZAR"),
            mechanism_families=("fx_regime_sensor", "cross_border_arbitrage"),
            how_to_fetch="bog.gov.gh economic data. THE CEDI-EURO CROSS IS THE DRIVER OF THE "
                         "FLAGSHIP MECHANISM and is computed from this rate and EURUSD rather "
                         "than quoted anywhere directly"),
    dataset("gh_bog_reserves_and_gold",
            source="Bank of Ghana gross international reserves and gold holdings",
            coverage="the reserve stock and the gold accumulated through the domestic purchase "
                     "programme",
            frequency="monthly",
            publication_lag_days=30.0,
            revisions="occasionally restated",
            licence="free, public",
            history_from="2000s",
            pit_feasible=True,
            assets=("XAUUSD", "USDZAR", "UST10Y"),
            mechanism_families=("commodity_production_sensor", "sovereign_stress"),
            how_to_fetch="the Summary of Economic and Financial Data. THE GOLD LINE IS THE "
                         "UNUSUAL ONE: domestic gold bought in cedis becomes an external reserve "
                         "without the cedi touching the FX market"),
    dataset("cfa_bceao_statistics",
            source="BCEAO statistical portal -- reserves, net foreign assets, policy rate",
            coverage="UEMOA-wide monetary statistics and the reserve position behind the peg",
            frequency="monthly to quarterly",
            publication_lag_days=45.0,
            revisions="restated across editions",
            licence="free, public, IN FRENCH",
            history_from="1990s",
            pit_feasible=True,
            assets=("EURUSD", "UKCOCOA"),
            mechanism_families=("fx_regime_sensor", "sovereign_stress"),
            how_to_fetch="bceao.int/fr/statistiques. THE PARITY NEVER MOVES, SO ALL THE "
                         "INFORMATION ABOUT THE PEG IS IN THE RESERVE POSITION BEHIND IT -- "
                         "which is why this row exists at all for a currency with a fixed price"),
    dataset("gh_gold_production",
            source="Minerals Commission and PMMC gold output and export statistics",
            coverage="large-scale and small-scale gold production and export volumes",
            frequency="quarterly, with monthly export figures",
            publication_lag_days=60.0,
            revisions="revised; SMALL-SCALE (galamsey) OUTPUT IS SYSTEMATICALLY UNDER-CAPTURED "
                      "and the gap is acknowledged rather than corrected",
            licence="free, public",
            history_from="2010s",
            pit_feasible=True,
            assets=("XAUUSD",),
            mechanism_families=("commodity_production_sensor", "supply_shock"),
            how_to_fetch="mincom.gov.gh and PMMC reports. Ghana has been Africa's largest gold "
                         "producer in recent years, so this is a genuine world-supply "
                         "observable -- with the caveat that the informal share is large and "
                         "unmeasured, which is stated rather than modelled away"),
    dataset("gh_petroleum_production",
            source="Petroleum Commission and GNPC field production reports",
            coverage="Jubilee, TEN and Sankofa field output",
            frequency="quarterly",
            publication_lag_days=60.0,
            revisions="revised",
            licence="free, public",
            history_from="2011, from first oil",
            pit_feasible=True,
            assets=("XBRUSD", "XTIUSD"),
            mechanism_families=("commodity_production_sensor",),
            how_to_fetch="petroleumcommission.gov.gh. Ghana is a small producer and the edge is "
                         "about the FISCAL and FX consequence rather than about world supply; "
                         "the pack does not claim a Brent signal from it"),
    dataset("gh_npa_fuel_windows",
            source="National Petroleum Authority indicative pricing windows",
            coverage="the fortnightly maximum indicative petroleum prices and their inputs",
            frequency="fortnightly",
            publication_lag_days=0.0,
            revisions="each window is a new determination, not a revision",
            licence="free, public",
            history_from="2010s",
            pit_feasible=True,
            assets=("XBRUSD", "XTIUSD"),
            mechanism_families=("macro_surprise", "fx_regime_sensor"),
            how_to_fetch="npa.gov.gh. THE PASS-THROUGH IS PUBLISHED WITH ITS INPUTS rather than "
                         "estimated, which is a rare gift: the window formula makes the Brent "
                         "and cedi contribution to the domestic fuel price an identity"),
    dataset("gh_ghana_statistical_cpi",
            source="Ghana Statistical Service consumer price index",
            coverage="headline and food inflation, monthly",
            frequency="monthly",
            publication_lag_days=12.0,
            revisions="rebased periodically, which is a series break declared as an era",
            licence="free, public",
            history_from="2010s for the current basket",
            pit_feasible=True,
            assets=("UKCOCOA", "USDZAR"),
            mechanism_families=("macro_surprise", "policy_reaction"),
            how_to_fetch="the GSS release calendar; Ghanaian inflation exceeded 50% in 2022-2023, "
                         "so any model fitted on the band period has no observations of the "
                         "regime that actually broke the currency"),
    dataset("gh_debt_restructuring_timeline",
            source="Ministry of Finance, IMF programme documents and bondholder committee "
                   "statements",
            coverage="the dated stages of the 2022-2024 default, domestic debt exchange, IMF "
                     "programme and eurobond restructuring",
            frequency="event-driven",
            publication_lag_days=0.0,
            revisions="not revised; each stage is its own announcement",
            licence="free, public",
            history_from="2022-12",
            pit_feasible=True,
            assets=("UST10Y", "UKGILT", "USDZAR"),
            mechanism_families=("sovereign_stress", "frontier_transmission"),
            how_to_fetch="mofep.gov.gh, imf.org country page and public bondholder statements. "
                         "THE MOST COMPLETELY DOCUMENTED FRONTIER RESTRUCTURING OF THE DECADE, "
                         "with every stage dated -- a rare clean event grid for frontier credit"),
    dataset("gh_rainfall_cocoa_belt",
            source="CHIRPS gridded rainfall and FEWS NET West Africa for the cocoa belt",
            coverage="rainfall anomalies and harmattan intensity over the Ghanaian and Ivorian "
                     "growing regions",
            frequency="dekadal (ten-day), with seasonal outlooks",
            publication_lag_days=10.0,
            revisions="preliminary estimates are replaced by final ones, which IS a revision",
            licence="free, public research data",
            history_from="1981 for CHIRPS",
            pit_feasible=True,
            assets=("UKCOCOA", "USCOCOA"),
            mechanism_families=("weather_agriculture", "supply_shock"),
            how_to_fetch="CHIRPS gridded files aggregated over the cocoa belt, plus FEWS NET "
                         "West Africa. THE HARMATTAN -- the dry Saharan wind -- is the region's "
                         "characteristic crop risk, it is forecastable, and IT DOES NOT RESPECT "
                         "THE BORDER, which makes it the natural common-shock control for the "
                         "cross-border mechanism: weather hits both sides, currency hits one"),
)


# --------------------------------------------------------------------------- actors
ACTORS: tuple[dict[str, Any], ...] = (
    actor("COCOBOD, the Ghana Cocoa Board",
          holds="a monopsony over Ghanaian cocoa purchasing and the season's forward sales",
          forced_to=("announce a guaranteed producer price in CEDIS at the season opening and "
                     "hold it for the season",
                     "fund the season's purchases, historically through an announced offshore "
                     "syndicated loan",
                     "buy whatever the farmers deliver at the announced price"),
          when="the price is announced in September or October; purchases run through the season",
          information=("the world price", "the cedi", "the crop estimate",
                       "the Ivorian announcement"),
          constraints=("a price fixed in a DEPRECIATING currency for a whole season",
                       "forward sales struck months before the season at prices that may now be "
                       "far from spot",
                       "a land border with a higher-paying neighbour"),
          instruments=("UKCOCOA", "USCOCOA"),
          counterparties=("farmers", "offshore syndicate lenders", "exporters",
                          "the Conseil du Cafe-Cacao as a de facto competitor for the same crop"),
          observables=("the announced producer price", "graded and sealed purchases",
                       "the syndication announcement or its absence",
                       "the gap between purchases and the crop estimate"),
          impact="when the cedi falls mid-season the announced price falls in dollar terms "
                 "against a neighbour whose price is euro-pegged, and the crop reallocates "
                 "across the border -- changing the deliverable supply behind two contracts the "
                 "desk trades",
          persistence="structural; the monopsony and the announced-price convention are decades "
                      "old and the cedi's depreciation is chronic",
          falsifier="if the gap between COCOBOD purchases and the Ghanaian crop estimate shows "
                    "no relationship to the cedi-euro farmgate differential, controlling for the "
                    "crop itself, the cross-border mechanism is not present in the physical data "
                    "and this pack's flagship claim is dead",
          notes="THE PACK'S CENTRAL ACTOR. Its falsifier is deliberately the strictest one here."),
    actor("The Conseil du Cafe-Cacao, Cote d'Ivoire",
          holds="the administered price and marketing of the world's largest cocoa crop",
          forced_to=("announce a prix garanti au producteur in XOF for each campaign",
                     "forward-sell a large share of the crop before harvest",
                     "absorb the consequences of a price fixed in a currency it does not control"),
          when="main-crop announcement in October, mid-crop in April; weekly arrivals through "
               "the season",
          information=("the world price", "EURUSD", "arrivals", "the Ghanaian announcement"),
          constraints=("A EURO-PEGGED CURRENCY, so the dollar value of its announced price is "
                       "determined by EURUSD and by nothing local",
                       "forward sales struck months earlier",
                       "a porous land border"),
          instruments=("UKCOCOA", "USCOCOA", "EURUSD"),
          counterparties=("farmers", "exporters and grinders", "COCOBOD across the border"),
          observables=("the announced prix garanti", "weekly port arrivals at Abidjan and San "
                       "Pedro", "the campaign calendar"),
          impact="THE HALF OF THE MECHANISM THAT NEEDS NO LOCAL DATA: with the parity fixed, a "
                 "EURUSD move changes Ivorian farmers' dollar receipts one-for-one, mechanically, "
                 "between announcements",
          persistence="structural; the peg is treaty-backed and three decades old",
          falsifier="if Ivorian port arrivals show no response to the cedi-euro farmgate "
                    "differential after controlling for the crop and the world price, the "
                    "receiving end of the border mechanism is absent",
          notes="Publishes in French only. Its weekly arrivals series is the best "
                "high-frequency physical cocoa observable in existence."),
    actor("The Bank of Ghana",
          holds="reserves, the policy rate and the domestic gold purchase programme",
          forced_to=("defend an inflation band it spent two years far outside",
                     "rebuild reserves after a default",
                     "buy domestic gold in cedis to accumulate external reserves"),
          when="MPC six times a year; reserves monthly; gold purchases continuous",
          information=("inflation", "reserves", "the cedi", "IMF programme conditions"),
          constraints=("an IMF programme with review conditions",
                       "a post-default credit standing",
                       "an import bill dominated by fuel"),
          instruments=("XAUUSD", "USDZAR", "UST10Y"),
          counterparties=("domestic gold producers", "commercial banks", "the IMF"),
          observables=("MPC decisions", "monthly reserves and the gold line",
                       "gold-for-oil programme announcements"),
          impact="THE DOMESTIC GOLD PURCHASE PROGRAMME MAKES THE GOLD PRICE A GHANAIAN MONETARY "
                 "VARIABLE: a higher gold price accumulates reserves faster without the cedi ever "
                 "touching the FX market, which is an unusual and directly testable channel",
          persistence="the programme has run since 2021 and is policy rather than convention",
          falsifier="if Ghanaian reserve accumulation shows no differential sensitivity to the "
                    "gold price after the programme's start relative to before it, the channel "
                    "is not operating at a measurable scale",
          notes="GMT is UTC, so every Ghanaian announcement time in this pack needs no "
                "conversion -- the only such country here."),
    actor("BCEAO and the UEMOA reserve pool",
          holds="the reserves backing a treaty-fixed parity for eight countries",
          forced_to=("maintain 655.957 to the euro whatever the terms of trade",
                     "pool member reserves and publish the position",
                     "set a single policy rate for eight different economies"),
          when="continuous; statistics monthly to quarterly; policy meetings quarterly",
          information=("the reserve position", "euro-area policy", "member fiscal positions"),
          constraints=("a FIXED parity, which removes the exchange rate as an adjustment "
                       "variable entirely, so ALL adjustment happens in reserves and in the real "
                       "economy",
                       "eight members with divergent shocks and one instrument",
                       "the post-2019 arrangement, which changed the guarantee without changing "
                       "the parity"),
          instruments=("EURUSD", "UKCOCOA", "XBRUSD"),
          counterparties=("member states", "the euro area", "commodity buyers"),
          observables=("reserves and net foreign assets", "the taux directeur",
                       "IMF WAEMU regional consultations"),
          impact="THE PARITY NEVER MOVES, SO ALL THE INFORMATION IS IN THE RESERVE POSITION. For "
                 "the desk the consequence is simpler: the zone's dollar terms of trade ARE "
                 "EURUSD, by arithmetic, which is the cleanest FX-to-real-economy transmission "
                 "anywhere in this civilization",
          persistence="three decades of the current parity, with one devaluation in 1994",
          falsifier="if Ivorian cocoa export receipts and farmer behaviour show no measurable "
                    "sensitivity to EURUSD at the horizon the peg arithmetic implies, then "
                    "either the peg is not binding at the farm level or the transmission is "
                    "absorbed somewhere this pack has not modelled",
          notes="Published in French only. The IMF's WAEMU REGIONAL CONSULTATION is the closest "
                "thing to a published assessment of the parity's credibility."),
    actor("Ghanaian and Ivorian cocoa farmers",
          holds="the crop, and the decision of which side of the border to sell it on",
          forced_to=("sell at an administered price, or carry the crop to the other side",
                     "harvest within a biological window that does not wait"),
          when="continuously through the main crop and mid-crop",
          information=("the two announced farmgate prices", "the exchange rates implicit in "
                       "them", "local buying-agent behaviour"),
          constraints=("an administered price they cannot negotiate",
                       "transport cost and risk across the border",
                       "credit needs that force sale at harvest regardless of price"),
          instruments=("UKCOCOA", "USCOCOA"),
          counterparties=("the two marketing boards", "licensed buying companies",
                          "cross-border traders"),
          observables=("the price gap in a common currency", "board purchases versus arrivals",
                       "press and farmer-community reporting of diversion"),
          impact="THE DECISION THAT PRODUCES THE SUPPLY REALLOCATION IS MADE HERE, months before "
                 "it appears in a board's statistics -- which is why the Twi and French retail "
                 "layers matter for a commodity mechanism",
          persistence="structural while two administered prices exist across one border",
          falsifier="if farmer-level reporting of cross-border selling shows no correlation with "
                    "the measured price gap, the mechanism's microfoundation is wrong even if "
                    "the aggregate correlation survives",
          notes="Named as a CLASS. The falsifier tests the MICROFOUNDATION separately from the "
                "aggregate, which is the right way to avoid a spurious aggregate relationship."),
    actor("Ghanaian gold producers, large-scale and informal",
          holds="Africa's largest gold output in recent years, a material share of it informal",
          forced_to=("sell to licensed buyers or to the central bank's programme",
                     "operate under a licensing and environmental regime that is episodically "
                     "enforced"),
          when="continuous; official statistics quarterly",
          information=("the gold price", "the cedi", "enforcement intensity"),
          constraints=("licensing and environmental enforcement against informal mining",
                       "a cedi-denominated cost base against dollar-denominated revenue, which "
                       "makes a weaker cedi a margin subsidy"),
          instruments=("XAUUSD",),
          counterparties=("PMMC and licensed buyers", "the Bank of Ghana's purchase programme",
                          "refiners"),
          observables=("Minerals Commission output", "export volumes",
                       "the central bank's gold accumulation", "enforcement announcements"),
          impact="a genuine world-supply observable from the continent's largest producer, with "
                 "the honest caveat that the INFORMAL SHARE IS LARGE AND SYSTEMATICALLY "
                 "UNDER-CAPTURED -- so the official series understates both the level and, more "
                 "importantly, the VARIANCE",
          persistence="structural",
          falsifier="if Ghanaian reported output surprises show no conditional effect on XAUUSD "
                    "after controlling for the dollar and global mine supply, the production "
                    "sensor is too small or too noisy to trade",
          notes="Named as a class; no producer is ever a symbol on a docket."),
    actor("The Ghanaian fiscal authority and its creditors",
          holds="a sovereign balance sheet that defaulted in December 2022 and has been "
                "restructured since",
          forced_to=("meet IMF programme review conditions to unlock disbursements",
                     "execute a domestic debt exchange on its own banks and pension funds",
                     "negotiate with official and private external creditors"),
          when="scheduled IMF reviews; restructuring stages as announced",
          information=("revenue", "the debt path", "creditor positions"),
          constraints=("post-default market access", "IMF conditionality",
                       "domestic financial-sector damage from the debt exchange"),
          instruments=("UST10Y", "UKGILT", "USDZAR"),
          counterparties=("the IMF", "bondholder committees", "official creditors",
                          "domestic banks and pension funds"),
          observables=("programme review outcomes", "restructuring stage announcements",
                       "the eurobond price and its restructured successors"),
          impact="THE MOST COMPLETELY DOCUMENTED FRONTIER RESTRUCTURING OF THE DECADE, every "
                 "stage dated and announced -- which makes it a rare clean event grid for "
                 "frontier credit rather than only a Ghanaian story",
          persistence="the programme and the restructuring run for years",
          falsifier="if frontier credit carriers show no abnormal behaviour around Ghana's dated "
                    "restructuring stages relative to matched windows, the episode carries no "
                    "information beyond the country itself",
          notes="n is small by construction -- a handful of stages -- so this exists to be SIZED "
                "honestly and can never clear a gauntlet alone."),
    actor("Bulk oil distributors and the fuel import chain",
          holds="Ghana's largest single source of dollar demand",
          forced_to=("buy dollars for refined product imports at whatever the rate",
                     "price at the NPA's published fortnightly window"),
          when="continuous demand; prices reset fortnightly on a published schedule",
          information=("Brent", "the cedi", "the window formula"),
          constraints=("an inelastic short-run demand for fuel",
                       "a published pricing formula that removes discretion",
                       "the gold-for-oil arrangement, which changed the currency of settlement"),
          instruments=("XBRUSD", "XTIUSD", "XAUUSD"),
          counterparties=("international suppliers", "banks", "the NPA", "the Bank of Ghana"),
          observables=("NPA window determinations", "import volumes",
                       "gold-for-oil programme announcements"),
          impact="THE PASS-THROUGH IS PUBLISHED WITH ITS INPUTS, so the Brent and cedi "
                 "contribution to the Ghanaian pump price is an IDENTITY rather than an "
                 "estimate -- and the gold-for-oil programme changed which currency paid for "
                 "the barrels, which is a dated shock to the shape of FX demand",
          persistence="structural, with the barter arrangement as a dated regime",
          falsifier="if the NPA window's realised prices deviate systematically from the "
                    "published formula's inputs, the formula is not binding and the identity is "
                    "not one",
          notes="The published formula is a rare gift: most pass-through work has to estimate "
                "what this country publishes."),
    actor("The harmattan and the West African cocoa-belt climate",
          holds="the dry Saharan wind and the rainfall that determine the crop across both "
                "countries",
          forced_to=("follow a physical cycle no policy affects",
                     "and to ignore the Ghana-Cote d'Ivoire border entirely"),
          when="the harmattan season runs roughly December to February; rainfall through the "
               "growing season",
          information=("CHIRPS rainfall", "FEWS NET West Africa", "seasonal forecasts"),
          constraints=("physics"),
          instruments=("UKCOCOA", "USCOCOA"),
          counterparties=("every cocoa farmer in West Africa"),
          observables=("rainfall anomalies over the belt", "harmattan intensity and duration",
                       "crop disease reports -- black pod and swollen shoot"),
          impact="A GENUINELY EXOGENOUS SUPPLY SHOCK, AND -- CRUCIALLY FOR THIS PACK -- ONE THAT "
                 "DOES NOT RESPECT THE BORDER. Weather hits both sides; currency hits one. That "
                 "asymmetry is what makes the cross-border mechanism identifiable: a common "
                 "weather shock should move both boards' purchases together, and only the "
                 "currency channel should move them apart.",
          persistence="seasonal, with multi-year climate variation",
          falsifier="if Ghanaian and Ivorian purchases and arrivals move apart in ways unrelated "
                    "to both weather and the farmgate differential, some third mechanism is "
                    "operating that this pack has not named",
          notes="THE NATURAL COMMON-SHOCK CONTROL FOR THE FLAGSHIP MECHANISM, which is the most "
                "valuable thing an exogenous variable can be."),
    actor("Cross-border cocoa traders",
          holds="the arbitrage between two administered prices",
          forced_to=("move beans toward the higher-paying side when the gap is wide enough to "
                     "cover transport and risk",
                     "operate outside both boards' licensed channels by construction"),
          when="whenever the gap exceeds the cost, which is a threshold rather than a continuum",
          information=("both announced prices", "the exchange rates", "enforcement intensity"),
          constraints=("transport cost and confiscation risk, which create a THRESHOLD: small "
                       "gaps produce no flow at all and large ones produce a lot, so the "
                       "relationship is NON-LINEAR and a linear regression on the gap will "
                       "understate it"),
          instruments=("UKCOCOA", "USCOCOA"),
          counterparties=("farmers on both sides", "licensed buying companies", "enforcement"),
          observables=("the price gap", "enforcement and seizure reports",
                       "the divergence between purchases and arrivals"),
          impact="the physical mechanism by which an exchange-rate move becomes a reallocation of "
                 "deliverable supply between two exchange contracts",
          persistence="structural while two administered prices exist across one porous border",
          falsifier="if the purchases-versus-arrivals divergence shows no THRESHOLD behaviour in "
                    "the price gap -- if it is linear, or absent -- the trader's cost structure "
                    "is not what this actor assumes and the mechanism should be re-specified",
          notes="THE NON-LINEARITY IS THE TESTABLE PREDICTION and it is stated in the falsifier "
                "so a linear null cannot quietly pass for a confirmation."),
    actor("The IMF as an external constraint on both sides",
          holds="programme conditions for Ghana and regional consultations for the CFA unions",
          forced_to=("publish review outcomes and staff reports on a schedule",
                     "assess the monetary union as a unit, not only its members"),
          when="scheduled reviews, typically semi-annual; regional consultations annually",
          information=("fiscal performance", "reserve adequacy", "peg sustainability"),
          constraints=("its own published methodology and board calendar"),
          instruments=("UST10Y", "USDZAR", "EURUSD"),
          counterparties=("the Ghanaian authorities", "BCEAO and BEAC", "other creditors"),
          observables=("review calendars and outcomes",
                       "WAEMU and CEMAC regional consultation staff reports and their annexes"),
          impact="A SCHEDULED EXOGENOUS DATE GRID, and the regional consultations are the only "
                 "published assessment of the CFA parity's credibility -- so the IMF is both an "
                 "event and the pack's best data source on its own tail risk",
          persistence="episodic but recurrent",
          falsifier="if frontier carriers show no abnormal behaviour around scheduled review "
                    "dates relative to matched dates, the review calendar carries no information "
                    "the market has not priced",
          notes="The WAEMU regional consultation has no national equivalent and is the highest-"
                "yield single document in this pack's source graph."),
    actor("Ghanaian and Ivorian households as remittance recipients",
          holds="the receiving end of two remittance corridors into two different monetary "
                "regimes",
          forced_to=("accept whatever corridor rate the operator posts",
                     "choose between formal and informal channels"),
          when="continuous, with festival and year-end seasonality",
          information=("the posted corridor rate", "transfer fees", "the local rate"),
          constraints=("corridor competition and fees",
                       "payout network access"),
          instruments=("EURUSD", "USDZAR"),
          counterparties=("diaspora senders", "money transfer operators", "mobile-money agents"),
          observables=("posted corridor rates for Ghana and for the UEMOA states",
                       "official remittance statistics"),
          impact="THE SAME OPERATORS POST A GHANA RATE AND A UEMOA RATE, from the same senders, "
                 "at the same moment -- one into a floating currency and one into a euro-pegged "
                 "one. THE SPREAD BETWEEN THE TWO CORRIDORS IS A RETAIL-LEVEL MEASUREMENT OF THE "
                 "EXACT MONETARY ASYMMETRY the flagship mechanism runs on, at daily frequency, "
                 "from a public page.",
          persistence="structural while the two regimes coexist",
          falsifier="if the corridor spread shows no relationship to the cedi-euro cross after "
                    "controlling for operator fee changes, the corridor pages are quoting a "
                    "stale or administered rate and are not a measurement",
          notes="The most creative observable in the pack and the one most likely to be "
                "dismissed as trivia. It is a daily, public, retail-level read on a monetary "
                "asymmetry that is otherwise only observable at seasonal frequency."),
    actor("The Alliance of Sahel States and the zone's political tail",
          holds="the credibility of the CFA arrangement's permanence",
          forced_to=("act on stated intentions to leave ECOWAS and to question the monetary "
                     "union",
                     "and the remaining members to respond"),
          when="episodic; announcements are dated",
          information=("political developments", "member commitments", "French policy"),
          constraints=("the practical difficulty of leaving a currency union",
                       "trade dependence on remaining members"),
          instruments=("EURUSD", "UKCOCOA", "USDZAR"),
          counterparties=("BCEAO", "ECOWAS", "France", "the remaining members"),
          observables=("withdrawal announcements and their dates",
                       "public commentary on monetary sovereignty",
                       "BCEAO reserve position"),
          impact="NONE OF THE THREE AES STATES IS A MAJOR COCOA PRODUCER, so the direct commodity "
                 "effect is small. The effect that matters is on the ZONE'S PERCEIVED "
                 "PERMANENCE, which is what converts the peg's tail risk from a historical "
                 "footnote into a live variable",
          persistence="a multi-year political process with no clear terminal date",
          falsifier="if no measurable risk premium appears in any CFA-linked observable around "
                    "AES announcements, the political tail is not being priced anywhere the desk "
                    "can see, and the pack should carry the peg as riskless until it is",
          notes="The pack's honest position: a thirty-year-stable, treaty-backed peg that has "
                "moved exactly once. Neither riskless nor floating, and modelled as neither."),
)


# --------------------------------------------------------------------------- domains
DOMAINS: tuple[dict[str, Any], ...] = (
    domain("gh_cocoa_farmgate_asymmetry", "Two administered prices, two currencies, one border",
           objects=("the Ghanaian producer price in cedis",
                    "the Ivorian prix garanti in XOF",
                    "both converted to a common currency", "the gap and its sign"),
           conditions=("the cedi-euro cross", "EURUSD", "the announcement calendar",
                       "the crop year"),
           instruments=("UKCOCOA", "USCOCOA", "EURUSD"),
           controls=("seasons with both announcements at the same time and a stable cedi, which "
                     "should show no gap movement",
                     "the world price itself, which moves both boards' economics together and "
                     "must be removed first",
                     "the harmattan and rainfall, which hit both sides and are the natural "
                     "common-shock control",
                     "randomised assignment of the gap's sign"),
           notes="THE PACK'S FLAGSHIP DOMAIN. An exchange rate causing a physical supply "
                 "reallocation, with both legs publicly announced and both targets executable."),
    domain("gh_cross_border_supply", "Purchases versus arrivals, and the threshold in between",
           objects=("COCOBOD graded and sealed purchases",
                    "Ivorian weekly port arrivals",
                    "the divergence between them and the combined crop estimate"),
           conditions=("the farmgate gap", "enforcement intensity", "transport cost",
                       "the crop"),
           instruments=("UKCOCOA", "USCOCOA"),
           controls=("the combined crop estimate, which nets out the reallocation and isolates "
                     "it",
                     "weather shocks, which move both sides together",
                     "seasons with a near-zero gap",
                     "randomised divergence values"),
           notes="THE PREDICTION IS NON-LINEAR: transport cost and confiscation risk create a "
                 "THRESHOLD, so a linear regression on the gap will understate the effect and a "
                 "linear null must not pass for a confirmation."),
    domain("cfa_peg_transmission", "A euro peg as a mechanical dollar terms-of-trade channel",
           objects=("the fixed parity", "EURUSD",
                    "the implied dollar value of XOF-denominated receipts"),
           conditions=("EURUSD", "the commodity price", "the announcement calendar"),
           instruments=("EURUSD", "UKCOCOA", "XBRUSD"),
           controls=("Ghana, which has the same crop, the same region and a floating currency",
                     "periods with a stable EURUSD and a moving commodity price",
                     "randomised EURUSD paths"),
           notes="THE TRANSMISSION IS ARITHMETIC, NOT CORRELATION: with the parity fixed, the "
                 "dollar value of a fixed XOF price moves one-for-one with EURUSD."),
    domain("cfa_peg_credibility", "The reserve position behind a price that never moves",
           objects=("BCEAO and BEAC reserves and net foreign assets",
                    "IMF regional consultation assessments",
                    "AES political announcements"),
           conditions=("the commodity cycle", "euro-area policy", "the political process"),
           instruments=("EURUSD", "UKCOCOA", "USDZAR"),
           controls=("other hard pegs with published reserve positions",
                     "periods of equal reserve cover and no political news",
                     "randomised announcement dates"),
           notes="ALL THE INFORMATION ABOUT A FIXED PRICE IS IN THE RESERVES BEHIND IT. The peg "
                 "has moved once, in 1994, which is neither riskless nor floating."),
    domain("gh_cocoa_season_calendar", "The crop year as the pack's real calendar",
           objects=("main-crop and mid-crop windows", "announcement dates",
                    "the COCOBOD syndication window", "forward-sale coverage"),
           conditions=("the crop estimate", "the world price at the time of forward selling"),
           instruments=("UKCOCOA", "USCOCOA"),
           controls=("calendar quarters, which should show LESS structure than crop years if the "
                     "seasonal is real",
                     "seasons with no syndication",
                     "randomised season boundaries"),
           notes="A cocoa study using calendar quarters is aggregating across the announcement "
                 "that drives the whole mechanism."),
    domain("gh_gold_production", "Africa's largest gold output, with a large informal share",
           objects=("Minerals Commission output and exports",
                    "the Bank of Ghana's domestic purchases",
                    "the acknowledged informal gap"),
           conditions=("the gold price", "the cedi", "enforcement intensity"),
           instruments=("XAUUSD",),
           controls=("global mine supply, removed first",
                     "other African producers with no domestic purchase programme",
                     "randomised output surprises"),
           notes="The informal share is large and systematically under-captured, which "
                 "understates the VARIANCE more than the level -- stated rather than modelled "
                 "away."),
    domain("gh_monetary_gold_channel", "Gold as a Ghanaian monetary variable",
           objects=("the domestic gold purchase programme",
                    "reserve accumulation against the gold price",
                    "the gold-for-oil barter arrangement"),
           conditions=("the gold price", "the programme's activity", "the fuel import bill"),
           instruments=("XAUUSD", "XBRUSD", "USDZAR"),
           controls=("the pre-2021 period, before the programme existed",
                     "other gold-producing sovereigns with no such programme",
                     "randomised programme dates"),
           notes="An unusual channel: a domestic commodity becoming an external reserve without "
                 "the currency touching the FX market."),
    domain("gh_sovereign_restructuring", "A fully dated frontier default and its stages",
           objects=("the December 2022 default", "the 2023 domestic debt exchange",
                    "the IMF programme and its reviews", "the 2024 eurobond restructuring"),
           conditions=("the global frontier funding state", "programme compliance"),
           instruments=("UST10Y", "UKGILT", "USDZAR"),
           controls=("other frontier restructurings in the same window",
                     "matched non-event windows",
                     "randomised stage dates"),
           notes="n is a handful of stages. This domain exists to be SIZED honestly."),
    domain("gh_fx_and_premium", "The cedi, the forex bureau gap and the corridor spread",
           objects=("the BoG interbank reference rate",
                    "the forex-bureau gap",
                    "the Ghana-versus-UEMOA remittance corridor spread"),
           conditions=("reserve adequacy", "the programme", "seasonality"),
           instruments=("EURUSD", "USDZAR", "UKCOCOA"),
           controls=("the UEMOA corridor, which is the same operators into a pegged currency",
                     "operator fee changes, which are breaks not signals",
                     "randomised corridor spreads"),
           notes="THE CORRIDOR SPREAD IS THE CREATIVE OBSERVABLE: a daily public retail read on "
                 "the exact monetary asymmetry the flagship mechanism runs on."),
    domain("gh_energy_and_barter", "Fuel imports, the published price window and gold-for-oil",
           objects=("NPA fortnightly window determinations and their inputs",
                    "import volumes", "the barter arrangement's announcements"),
           conditions=("Brent", "the cedi", "the arrangement's status"),
           instruments=("XBRUSD", "XTIUSD", "XAUUSD"),
           controls=("the published formula itself, which makes the pass-through an identity",
                     "the pre-barter period",
                     "randomised window dates"),
           notes="THE PASS-THROUGH IS PUBLISHED WITH ITS INPUTS, which most pass-through work "
                 "has to estimate."),
    domain("gh_weather_and_crop", "The harmattan, the rains and a shock that ignores the border",
           objects=("CHIRPS rainfall anomalies over the cocoa belt",
                    "harmattan intensity and duration",
                    "black pod and swollen shoot disease reports"),
           conditions=("the season", "the climate cycle", "the growing region"),
           instruments=("UKCOCOA", "USCOCOA"),
           controls=("THE BORDER ITSELF: weather hits both sides and currency hits one, so a "
                     "common weather shock should move both boards' purchases TOGETHER",
                     "years with normal rainfall in the same window",
                     "randomised anomaly assignment"),
           notes="GENUINELY EXOGENOUS and, crucially, BORDER-BLIND -- which is what makes the "
                 "cross-border currency mechanism identifiable at all."),
    domain("gh_holiday_observability", "Three calendars over one mechanism",
           objects=("the Ghanaian holiday table", "the Ivorian holiday calendar",
                    "the London and New York cocoa trading calendars"),
           conditions=("which of the three is closed", "the season"),
           instruments=("UKCOCOA", "USCOCOA"),
           controls=("days when all three are open",
                     "closures of different lengths",
                     "randomised closure dates"),
           notes="GHANA AND COTE D'IVOIRE DO NOT SHARE A HOLIDAY CALENDAR, so a naive daily join "
                 "of the two sides pairs an observation with a non-observation and produces an "
                 "apparent divergence that is a calendar artefact."),
    domain("gh_frontier_stress_transmission", "West Africa as a sensor for tradable carriers",
           objects=("the joint state of cedi, reserves, restructuring stage and cocoa earnings",
                    "CFA reserve position and political news"),
           conditions=("the global EM risk state", "the dollar", "commodity prices"),
           instruments=("USDZAR", "UST10Y", "EURUSD"),
           controls=("THE GLOBAL EM FACTOR, removed first",
                     "matched EM stress episodes with no West African component",
                     "randomised event dates"),
           notes="If West African stress does not reach a tradable carrier, the satellite "
                 "ranking is right and this pack should stay small -- except for the cocoa "
                 "mechanism, which reaches its targets directly and does not depend on it."),
)


# --------------------------------------------------------------------------- transmission
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    edge("gh_farmgate_gap_to_cocoa_supply",
         source="the Ghanaian and Ivorian announced farmgate prices converted to a common "
                "currency, and the cedi-euro cross that moves the gap between announcements",
         mechanism="Cote d'Ivoire's price is fixed in a euro-pegged currency for a season and "
                   "Ghana's in a floating one, so a cedi depreciation lowers the Ghanaian price "
                   "in dollar terms relative to its neighbour's WITH NO ANNOUNCEMENT FROM EITHER "
                   "BOARD, moving beans across the border and reallocating deliverable supply "
                   "between the two export pipelines",
         targets=("UKCOCOA", "USCOCOA"),
         sign="Ghanaian farmgate falling relative to Ivorian -> Ghanaian purchases UNDERSHOOT "
              "the crop estimate and Ivorian arrivals OVERSHOOT -> the ICE deliverable supply "
              "picture shifts between the two contracts",
         lag="the exchange-rate move is continuous; purchases and arrivals respond over weeks to "
             "months within the season",
         horizon="twenty to one hundred and twenty sessions",
         control="the world price, which moves both boards' economics together and must be "
                 "removed first; the harmattan and rainfall, which hit BOTH sides and are the "
                 "natural common-shock control; and seasons with a near-zero gap",
         evidence="HYPOTHESIS",
         notes="THE PACK'S FLAGSHIP EDGE AND THE REASON IT EXISTS. An exchange rate causing a "
               "physical supply reallocation, both legs publicly announced, both targets "
               "executable on this account. THE PREDICTED RELATIONSHIP IS NON-LINEAR -- "
               "transport cost and confiscation risk create a threshold -- so a linear null must "
               "not be read as a refutation."),
    edge("cfa_eurusd_to_ivorian_receipts",
         source="EURUSD, joined to the fixed 655.957 parity and the announced XOF farmgate price",
         mechanism="with the parity fixed by treaty, the dollar value of a fixed XOF price moves "
                   "one-for-one with EURUSD -- this is arithmetic rather than correlation, and "
                   "it changes Ivorian farmers' dollar receipts with no local news whatsoever",
         targets=("EURUSD", "UKCOCOA", "USCOCOA"),
         sign="EURUSD UP -> Ivorian dollar receipts UP at an unchanged local price -> greater "
              "willingness to deliver, and the Ghana-side gap widens against Ghana",
         lag="contemporaneous in arithmetic; the behavioural response is weeks",
         horizon="ten to sixty sessions",
         control="Ghana, which has the same crop, the same region and a floating currency -- the "
                 "cleanest available counterfactual; and periods of stable EURUSD with a moving "
                 "commodity price",
         evidence="HYPOTHESIS",
         notes="THE CLEANEST FX-TO-REAL-ECONOMY TRANSMISSION IN THE CIVILIZATION, because the "
               "first leg is a treaty rather than an estimate."),
    edge("ci_arrivals_to_cocoa_price",
         source="Conseil du Cafe-Cacao weekly cumulative port arrivals at Abidjan and San Pedro",
         mechanism="the largest producing country's weekly physical arrivals are the closest "
                   "thing the cocoa market has to a supply nowcast, and they lead the official "
                   "production statistics by months",
         targets=("UKCOCOA", "USCOCOA"),
         sign="cumulative arrivals running below the prior season's pace -> cocoa UP over the "
              "following weeks",
         lag="the weekly publication, about three days after the week",
         horizon="five to forty sessions",
         control="the prior season's pace at the same point in the crop year, which is the "
                 "natural baseline; the crop estimate; and randomised arrival figures",
         evidence="HYPOTHESIS",
         notes="Published in French. THE BEST HIGH-FREQUENCY PHYSICAL COCOA SERIES IN THE "
               "WORLD, and an Anglophone-only source list does not contain it."),
    edge("gh_cocobod_syndication_to_cedi",
         source="the annual COCOBOD pre-export syndicated finance facility, or its absence",
         mechanism="a billion-dollar scheduled offshore inflow each September or October is one "
                   "of very few dated, announced, quantified FX inflows in frontier Africa; when "
                   "it shrank or was replaced by domestic financing, the ABSENCE was the event",
         targets=("USDZAR", "UKCOCOA"),
         sign="a full syndication announced -> Ghanaian FX pressure relieved into the season; a "
              "failed or shrunken one -> cedi pressure and a weaker season financing position",
         lag="the announcement timestamp, at the season opening",
         horizon="twenty to eighty sessions",
         control="seasons with a full syndication at the same world price; matched windows in "
                 "the calendar with no syndication; and randomised announcement dates",
         evidence="HYPOTHESIS",
         notes="n is one per year, so the sample is a decade at best. SIZED HONESTLY."),
    edge("gh_gold_output_to_metal",
         source="Ghanaian gold production and export statistics",
         mechanism="Africa's largest producer's output is a genuine world-supply observable, "
                   "with the honest caveat that the informal share is large and systematically "
                   "under-captured",
         targets=("XAUUSD",),
         sign="a reported output shortfall -> XAUUSD UP over the following weeks",
         lag="quarterly statistics with a sixty-day lag; monthly export figures are faster",
         horizon="twenty to ninety sessions",
         control="global mine supply, removed first; other African producers with no domestic "
                 "purchase programme; and randomised output surprises",
         evidence="HYPOTHESIS",
         notes="The under-capture understates the VARIANCE more than the level, which biases a "
               "surprise measure toward finding nothing -- so a null here is weak evidence."),
    edge("gh_gold_purchase_programme_to_reserves",
         source="the Bank of Ghana's domestic gold purchase programme and the gold price",
         mechanism="gold bought domestically in cedis becomes an external reserve without the "
                   "cedi ever touching the FX market, so a higher gold price accumulates "
                   "reserves faster -- making the gold price a Ghanaian MONETARY variable",
         targets=("XAUUSD", "USDZAR"),
         sign="XAUUSD UP -> Ghanaian reserve accumulation faster -> frontier stress DOWN for "
              "Ghana specifically",
         lag="monthly reserve publication with a thirty-day lag",
         horizon="one to three quarters",
         control="THE PRE-2021 PERIOD, before the programme existed, is the regime control; "
                 "other gold-producing sovereigns with no such programme; randomised dates",
         evidence="HYPOTHESIS"),
    edge("gh_restructuring_stages_to_frontier_credit",
         source="the dated stages of Ghana's default, domestic debt exchange, IMF programme and "
                "eurobond restructuring",
         mechanism="the most completely documented frontier restructuring of the decade provides "
                   "a clean event grid for how frontier credit reprices around restructuring "
                   "milestones generally",
         targets=("UST10Y", "UKGILT", "USDZAR"),
         sign="a successful stage -> frontier credit stress DOWN; a delayed or failed one -> "
              "stress UP",
         lag="announcement timestamps",
         horizon="five to sixty sessions",
         control="other frontier restructurings in the same window; matched non-event windows; "
                 "randomised stage dates",
         evidence="HYPOTHESIS",
         notes="A handful of stages. Exists to be SIZED honestly and can never clear a gauntlet "
               "alone."),
    edge("gh_harmattan_to_cocoa",
         source="harmattan intensity and rainfall anomalies over the West African cocoa belt",
         mechanism="the dry Saharan wind is the region's characteristic crop risk, it is "
                   "forecastable, and it affects the pod set and bean size across BOTH producing "
                   "countries",
         targets=("UKCOCOA", "USCOCOA"),
         sign="a severe or prolonged harmattan -> lower crop -> cocoa UP over the following "
              "months",
         lag="the weather leads the harvest consequence by two to four months",
         horizon="forty to one hundred and twenty sessions",
         control="years with normal harmattan intensity in the same window; THE BORDER ITSELF, "
                 "since a weather shock should move BOTH boards' purchases together while a "
                 "currency shock moves them apart; randomised anomaly assignment",
         evidence="HYPOTHESIS",
         notes="THE COMMON-SHOCK CONTROL FOR THE FLAGSHIP EDGE, which is the most valuable role "
               "an exogenous variable can play."),
    edge("gh_npa_window_to_fuel_passthrough",
         source="the NPA's fortnightly indicative pricing windows and their published inputs",
         mechanism="Ghana publishes the pass-through formula with its inputs, so the Brent and "
                   "cedi contribution to the domestic fuel price is an IDENTITY rather than an "
                   "estimate -- and a deviation from it is a measurable policy intervention",
         targets=("XBRUSD", "XTIUSD"),
         sign="Brent UP -> the next window's indicative price UP by the formula; a DEVIATION "
              "from the formula is an intervention and is the actual event",
         lag="the fortnightly window schedule",
         horizon="five to twenty sessions",
         control="the published formula itself, which is the null; the gold-for-oil period, "
                 "which changed the settlement currency; randomised window dates",
         evidence="HYPOTHESIS",
         notes="Unusual shape: THE NULL IS AN IDENTITY and the finding is a deviation from it."),
    edge("cfa_political_tail_to_risk_premium",
         source="Alliance of Sahel States withdrawal announcements and monetary-sovereignty "
                "commentary",
         mechanism="none of the three states is a major cocoa producer, so the direct commodity "
                   "effect is small; what moves is the ZONE'S PERCEIVED PERMANENCE, which is "
                   "what converts the peg's one-in-thirty-years tail into a live variable",
         targets=("EURUSD", "UKCOCOA", "USDZAR"),
         sign="an escalation -> a measurable risk premium in CFA-linked observables, if one is "
              "priced anywhere at all",
         lag="the announcement timestamp",
         horizon="five to sixty sessions",
         control="matched windows with no political news; the BCEAO reserve position, which "
                 "should move if the risk is real; randomised announcement dates",
         evidence="HYPOTHESIS",
         notes="A DELIBERATELY NULL-SHAPED EDGE. If no premium appears anywhere, the honest "
               "conclusion is that the tail is not priced where the desk can see it -- and the "
               "pack then carries the peg as riskless UNTIL IT IS, which is a decision the "
               "measurement makes rather than an assumption."),
    edge("gh_ci_corridor_spread_to_cedi",
         source="the same remittance operators' posted Ghana corridor rate and UEMOA corridor "
                "rate",
         mechanism="one corridor pays into a floating currency and the other into a euro-pegged "
                   "one, from the same senders at the same moment, so the SPREAD between them is "
                   "a daily retail-level measurement of the monetary asymmetry the flagship "
                   "mechanism runs on",
         targets=("EURUSD", "USDZAR", "UKCOCOA"),
         sign="the Ghana corridor deteriorating relative to the UEMOA corridor -> cedi pressure "
              "-> a widening farmgate gap against Ghana later in the season",
         lag="daily posted rates; the farmgate consequence is seasonal",
         horizon="ten to sixty sessions",
         control="operator fee changes, which are breaks and not signals; the BoG reference rate, "
                 "which the corridor should track if it is a measurement rather than an "
                 "administered quote; randomised corridor spreads",
         evidence="HYPOTHESIS",
         notes="THE PACK'S MOST CREATIVE OBSERVABLE and the one most likely to be dismissed as "
               "trivia. Its falsifier is whether the corridor tracks the reference rate at all."),
    edge("gh_holiday_calendar_artefact",
         source="the three non-overlapping calendars: Ghana's, Cote d'Ivoire's, and the ICE "
                "London and New York trading calendars",
         mechanism="Ghana and Cote d'Ivoire do not share a holiday calendar, so a naive daily "
                   "join of the two sides of the border mechanism pairs an observation with a "
                   "non-observation, and the apparent cross-border divergence that results is a "
                   "CALENDAR ARTEFACT rather than a supply signal",
         targets=("UKCOCOA", "USCOCOA"),
         sign="apparent divergence concentrated on days when exactly one side is closed, and "
              "absent on days when both are open",
         lag="the closure itself",
         horizon="one to five sessions",
         control="days when both sides are open, which is the only valid comparison set; "
                 "closures of different lengths; randomised closure dates",
         evidence="HYPOTHESIS",
         notes="A DEFECT-DETECTION EDGE rather than a trading edge. It exists so that the "
               "flagship mechanism's measurement cannot be contaminated by the artefact, and "
               "finding the artefact is a success for this edge and a warning for that one."),
)

#: Derived, never hand-maintained. With OWN_PRICE empty every target is a transmission target.
TRANSMISSION_TARGETS: tuple[str, ...] = tuple(sorted(
    {t for e in TRANSMISSION_EDGES_SEED for t in e["targets"]} - set(OWN_PRICE)))


# --------------------------------------------------------------------------- eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    era("cfa_post_1994_parity", start="1999-01-01", end=None,
        label="The current CFA parity at 655.957 to the euro",
        what_changed="the CFA franc's peg was redenominated from the French franc to the euro at "
                     "the euro's creation, at the arithmetically equivalent rate",
        invalidates="any CFA study pooling across January 1994 is pooling a 50% devaluation and "
                    "a three-decade fixed parity; the 1994 step is the zone's entire tail and "
                    "must be treated as a separate regime rather than as an outlier"),
    era("cfa_2019_reform", start="2019-12-21", end=None,
        label="The UEMOA reform: the operations account closed and the Eco agreed",
        what_changed="the operations account at the French Treasury was closed, French "
                     "representation on the BCEAO's organs was removed, and the reserve-pooling "
                     "requirement changed. THE PEG TO THE EURO WAS NOT CHANGED.",
        invalidates="this is widely reported as though the currency had been replaced, and it "
                    "was not. A study treating the reform as an EXCHANGE-RATE regime change is "
                    "measuring an institutional change in the GUARANTEE, which is a different "
                    "variable with a different observable"),
    era("gh_inflation_crisis", start="2022-01-01", end="2023-12-31",
        label="The inflation crisis and the currency collapse",
        what_changed="Ghanaian inflation exceeded 50% and the cedi lost a large fraction of its "
                     "value; the inflation band ceased to describe the economy at all",
        invalidates="a reaction function or pass-through estimate fitted inside the band has no "
                    "observations of the regime that actually broke the currency, and one fitted "
                    "across the boundary averages two different monetary economies"),
    era("gh_default_and_ddep", start="2022-12-19", end="2023-05-16",
        label="External default and the Domestic Debt Exchange Programme",
        what_changed="Ghana suspended external debt service and then restructured its domestic "
                     "debt on its own banks and pension funds",
        invalidates="domestic financial-sector series are not comparable across the debt "
                    "exchange: the banks' balance sheets were restructured by policy, so any "
                    "credit or deposit series spanning it is measuring the exchange"),
    era("gh_imf_programme", start="2023-05-17", end=None,
        label="The IMF programme and the restructuring path",
        what_changed="an IMF programme began, with scheduled reviews and disbursements, and the "
                     "external restructuring proceeded through dated stages to the 2024 "
                     "eurobond exchange",
        invalidates="frontier credit behaviour before and after programme entry is not "
                    "comparable; the funding constraint, the policy reaction function and the "
                    "publication schedule all changed at once"),
    era("gh_gold_for_oil", start="2023-01-01", end=None,
        label="The gold-for-oil barter arrangement",
        what_changed="gold bought domestically was used to pay for refined petroleum imports, "
                     "removing the largest single source of dollar demand from the interbank "
                     "market",
        invalidates="THE SHAPE OF GHANAIAN FX DEMAND CHANGED even where the annual total did "
                    "not; a study spanning the change is pooling two different demand processes, "
                    "and whether the policy worked is a separate question from whether it is a "
                    "regime boundary -- it is"),
    era("gh_gold_purchase_programme", start="2021-06-01", end=None,
        label="The Bank of Ghana's domestic gold purchase programme",
        what_changed="the central bank began buying gold from domestic producers in cedis and "
                     "adding it to reserves",
        invalidates="reserve-accumulation studies pooled across this date are fitting one "
                    "process to two: before it, reserves came from FX-market transactions; "
                    "after, partly from a domestic commodity purchase"),
    era("cfa_aes_political", start="2024-01-28", end=None,
        label="The Alliance of Sahel States' withdrawal from ECOWAS",
        what_changed="three member states announced withdrawal from ECOWAS and raised the "
                     "question of leaving the monetary union",
        invalidates="peg-permanence assumptions from the pre-2024 period do not carry forward "
                    "unexamined; the tail is not necessarily larger, but it is now a subject on "
                    "which there is public information and therefore possibly a price"),
    era("gh_cocoa_price_shock", start="2023-10-01", end=None,
        label="The cocoa price shock and the widening farmgate gap",
        what_changed="world cocoa prices rose to multiples of their historical range while both "
                     "boards' announced farmgate prices lagged far behind, widening the gap "
                     "between world and farmgate prices on both sides of the border",
        invalidates="THE FLAGSHIP MECHANISM'S OWN PARAMETERS ARE DIFFERENT HERE. When the world "
                    "price is many times the farmgate price, the incentive to divert beans away "
                    "from BOTH boards toward any other outlet dominates the cross-border "
                    "differential between them -- a third channel the pre-2023 sample contains "
                    "no observations of, and one this pack must condition on rather than pool"),
)


# --------------------------------------------------------------------------- the pack
def spec() -> dict[str, Any]:
    """THIS PACK AS PLAIN DATA -- the twenty-one fields exactly as this department declares them.

    THE SOURCE OF TRUTH, and the thing the tests validate. The country lab's frozen `CountryPack`
    has row classes with their own field names and DROPS any row it cannot construct, which makes
    the typed object a LOSSY VIEW of a pack written in this package's richer vocabulary. The
    plain data is therefore kept and `pack()` adapts it explicitly.
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
    `cot_currency` is empty: there is no CFTC cedi or CFA contract, and an invented ticker would
    make the positioning miner report a number instead of UNMEASURED -- although note that the
    COCOA contract this pack's flagship edge terminates in DOES have a COT report, which is the
    reverse of the usual frontier problem.
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
    every_day = tuple(sorted(d for tbl in _GH_HOLIDAYS.values() for d in tbl))
    return {"transmission_edges_seed": tuple(seeds), "policy_eras": eras,
            "fixing_conventions": fixings, "settlement_conventions": settle,
            "exchanges": venues,
            "holidays_rule": {"dates": every_day, "notes": str(HOLIDAYS_RULE["rule"])},
            "fiscal_year_end": "12-31",
            "export_economy": "agricultural_exporter",
            "retail_leverage_regime": "UNMEASURED",
            "cot_currency": "",
            "positioning_sources": tuple(str(p["id"]) for p in POSITIONING_SOURCES),
            "source_classes": tuple(str(s["id"]) for s in SOURCE_CLASSES),
            "custom_miners": tuple(str(m["entry"]) for m in CUSTOM_MINERS),
            "miner_domains": {str(m["name"]): tuple(m["domain_ids"]) for m in CUSTOM_MINERS},
            "mission": "mine Ghana and the CFA franc zone to exhaustion as an exogenous cocoa, "
                       "gold and euro-peg sensor for the soft complex and metals the desk "
                       "already trades; two administered prices in two currencies over one "
                       "border is the mechanism, and neither currency is tradable here"}


def pack() -> Any:
    """The Ghana + CFA zone country pack. `CountryPack` when the framework has landed, else a
    dict."""
    return build_pack(**{**spec(), **framework_rows()})


def priority_weight() -> float:
    """This pack's share of the opening African compute ladder. A PRIOR, replaced by survivors."""
    return PRIORITY_WEIGHT


def instrument_report(path: Any = None) -> dict[str, Any]:
    """What this pack can trade, what carries its economics and what is missing, MEASURED against
    the broker registry. `own_price` is empty for both currencies and that is the measurement."""
    split = resolve(EXECUTABLE_INSTRUMENTS, path)
    return {"code": CODE, "own_price": OWN_PRICE, "executable": tuple(split["tradable"]),
            "equities_refused": tuple(split["equities"]),
            "absent_from_universe": tuple(split["absent"]),
            "transmission_targets": TRANSMISSION_TARGETS,
            "named_absent_instruments": ABSENT_INSTRUMENTS,
            "priority_weight": PRIORITY_WEIGHT,
            "transmission_only": not OWN_PRICE,
            "flagship": "two administered farmgate prices in two currencies -- one floating, one "
                        "euro-pegged -- across one border, feeding UKCOCOA and USCOCOA",
            "dataset_fields": DATASET_FIELDS}
