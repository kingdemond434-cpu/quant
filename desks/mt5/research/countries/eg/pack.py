"""THE EGYPT COUNTRY PACK -- a chokepoint, a wheat bill, and no price of its own.

THE DEFINING STRUCTURAL FACT, STATED FIRST BECAUSE IT CONSTRAINS EVERYTHING BELOW: **USDEGP IS
NOT ON THIS BROKER.** `OWN_PRICE` is empty. Egypt is a TRANSMISSION-ONLY country pack. There is
no Egyptian pound pair, no EGX index CFD, no Egyptian bill or eurobond, and the pound is not
deliverable offshore, so there is not even a clean NDF the desk could shadow. Every hypothesis
this department mints must terminate in an instrument somebody else's economy prices, or it does
not terminate at all. South Africa is tested against its own currency four ways; Egypt cannot be
tested against itself once, and a pack that forgot to say so would quietly compile cells against
a symbol that does not exist.

WHY A COUNTRY THE DESK CANNOT TRADE IS STILL TIER 2. Four exogenous sensors, each landing in a
symbol the desk already trades:

  * IT OWNS A CHOKEPOINT AND PUBLISHES ITS THROUGHPUT. The Suez Canal and the SUMED pipeline
    carry a material share of seaborne crude and product and a large share of Asia-Europe
    container traffic. The Suez Canal Authority publishes vessel counts, net tonnage and
    revenue, and the Red Sea diversion from December 2023 is VISIBLE IN THAT SERIES. A
    shipowner's route decision becomes an Egyptian government statistic before it becomes a
    freight print -- and freight is what sets XBRUSD against XTIUSD and what loads European
    industrial cost into GER40 and EUSTX50.
  * IT IS THE WORLD'S LARGEST WHEAT IMPORTER AND ITS BUYER IS THE STATE, IN PUBLIC TENDERS. The
    causality runs BOTH WAYS, which is rare and is the reason WHEAT is an anchor here: a world
    wheat shock is an Egyptian fiscal and FX shock, and an Egyptian tender is large enough to be
    a world wheat event. A study that assumes one direction is measuring the average of two.
  * ITS HOUSEHOLDS HEDGE DEVALUATION IN GOLD, AND THE HEDGE IS OBSERVABLE. The gold pound
    (jineih al-dhahab) and 21-carat jewellery trade at a LOCAL PREMIUM over the world price when
    the control binds. Egypt is a price-taker at global scale, so the edge is about the REGIONAL
    PREMIUM AND FLOW, never about the level of XAUUSD -- and this pack says that in the edge
    itself rather than hoping a reader infers it.
  * ITS DEVALUATION REGIME HAS A LEADING INDICATOR. The official-versus-parallel spread widens
    for MONTHS and then closes in ONE STEP. The step is the event; the spread is the forecast.
    That is Egypt's single most valuable published-adjacent observable and it is the closest
    thing in this civilization to a dated, watchable regime-change probability.

WHAT THIS PACK MAY NOT DO. No single-name equity is ever a hypothesis (two-lane order,
2026-09-06): the EGX-listed banks and developers are the loudest Egyptian market story and they
enter here as INDEX-FLOW and FX transmission only, with no ticker on any docket. No
crypto-exchange ground is hunted (universe mandate, 2026-08-18), and Egypt is the sharpest case
in the whole civilization for saying it out loud, because the informal peer-to-peer
dollar-stablecoin market IS a parallel FX channel: it is carried as PUBLIC COMMENTARY with
`pit_feasible=False`, no venue is named or crawled, and the executable leg is the broker's own
BTCUSD CFD.

THE MEASUREMENT TRAPS THIS PACK EXISTS TO STOP, all three declared rather than discovered:
(1) EGYPT OBSERVES DST AGAIN SINCE 2023, so the UTC time of a Cairo announcement MOVES TWICE A
YEAR -- unlike South Africa and Nigeria, whose local times are fixed against UTC. (2) THE
EGYPTIAN WEEK IS SUNDAY TO THURSDAY: the EGX prints its foreign-flow table on a Sunday, when
nothing else in the desk's universe is open, and is shut on Friday when the broker's week still
runs. (3) THE ISLAMIC HOLIDAYS ARE MOON-DEPENDENT AND DECLARED BY THE CABINET, so every Eid date
in this file is an ESTIMATE carrying that label, and the desk refuses to trade a guessed Eid
window.
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

CODE = "eg"
NAME = "Egypt"
REGION_COMMAND = "AFRICA"
CURRENCY = "EGP"
NATIVE_LANGUAGES = ("ar", "en")

#: COMPUTE PRIORITY. The principal's order of 2026-09-17 sets the opening African ladder
#: ZA > NG > EG > KE > GH/CFA, and the source-ROI layer reallocates it afterwards BY MEASURED
#: SURVIVORS. Egypt sits at 0.40: below ZA (1.00) and NG (0.62) because it has NO OWN PRICE and
#: every cell must survive a transmission hop, above KE (0.22) and GH (0.14) because the
#: chokepoint and the wheat bill are world-scale sensors rather than local ones. This is a PRIOR,
#: not a verdict, and it is expected to be overwritten by measurement rather than defended.
PRIORITY_WEIGHT: float = 0.40

#: EMPTY, AND THAT IS THE PACK'S DEFINING FACT. USDEGP is not in the broker registry, the pound
#: is not deliverable offshore, and no Egyptian instrument of any kind is quotable here. Every
#: symbol below is a CARRIER of Egyptian economics, never Egypt itself. Nothing in this file may
#: quietly treat a carrier as if it were the country's own price.
OWN_PRICE: tuple[str, ...] = ()

#: What the EG department may place an order in. Sixteen symbols, each in
#: `desks/mt5/data/universe/universe.json`, none a single name, and each one chosen because an
#: Egyptian mechanism genuinely terminates in it rather than because it is nearby on a screen.
#: The anchors are XBRUSD/XTIUSD (the chokepoint), WHEAT (the import bill, two-way), XAUUSD (the
#: household devaluation hedge), USDTRY/USDZAR (the devaluation-regime peers), UST10Y/UKGILT (the
#: eurobond duration leg) and GER40/EUSTX50 (European supply-chain exposure to a Red Sea event).
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "XBRUSD", "XTIUSD", "XNGUSD", "XAUUSD", "WHEAT", "CORN", "COTTON", "USDTRY", "USDZAR",
    "USDILS", "EURUSD", "GER40", "EUSTX50", "UST10Y", "UKGILT", "BTCUSD")

#: The instruments a Cairo desk reaches for that THIS broker does not quote. Named with what
#: carries them, because an instrument dropped in silence takes a mechanism with it -- and in a
#: transmission-only pack the FIRST of these is the country itself.
ABSENT_INSTRUMENTS: tuple[dict[str, str], ...] = (
    {"instrument": "USDEGP -- the Egyptian pound itself, spot or forward",
     "why": "NOT IN desks/mt5/data/universe/universe.json, and not deliverable offshore either: "
            "there is no offshore EGP clearing, so even a synthetic leg has no settlement. The "
            "only offshore exposure that exists anywhere is a non-deliverable forward quoted by "
            "a handful of banks and reported in commentary, which is a PRICE OPINION and not a "
            "series the desk can trade or reconstruct point-in-time.",
     "carried_by": "USDTRY and USDZAR as devaluation-regime and EM/frontier peers; XAUUSD as the "
                   "household hedge's global leg; UST10Y and UKGILT as the external-funding leg. "
                   "The Egypt-specific residual after those carriers is UNMEASURED BY NAME and "
                   "stays that way until an Egyptian price exists on this account."},
    {"instrument": "EGX30 (and EGX70, EGX100) -- the Egyptian Exchange indices",
     "why": "absent; no Egyptian equity index CFD is quoted on this account. The EGX30 is also "
            "a NOMINAL index in a currency that has halved twice, so its dollar return and its "
            "pound return are different stories and only the pound one is published as the "
            "headline -- a trap for anyone who imports the number without the deflator.",
     "carried_by": "EUSTX50 and GER40 for the European risk factor the EGX co-moves with, and "
                   "USDZAR for the EM-equity-flow factor. The EGX's OWN daily foreign/Arab/"
                   "Egyptian net-flow table is kept as an OBSERVABLE, never as a tradable."},
    {"instrument": "Egyptian treasury bills, bonds and USD/EUR eurobonds; the EMBI Egypt spread",
     "why": "absent; the broker quotes UST05Y, UST10Y and UKGILT and no frontier credit. The "
            "T-bill is the instrument the carry trade actually used and the eurobond is where "
            "the programme risk prices, and neither is reachable here.",
     "carried_by": "UST10Y and UKGILT as the global duration leg of the same position. THE "
                   "CREDIT SPREAD -- which is the whole Egypt-specific part -- is UNMEASURED BY "
                   "NAME and is carried only as an observable in the external-programme domain."},
    {"instrument": "The Suez Canal transit toll (SDR-denominated) and the SCA surcharge schedule",
     "why": "absent, and not an instrument at all: it is an ADMINISTERED PRICE set by a state "
            "authority in navigation circulars, with negotiated rebates that are not published "
            "per-vessel. It cannot be traded and its effective level cannot be reconstructed "
            "from public sources for any individual voyage.",
     "carried_by": "XBRUSD versus XTIUSD, whose spread absorbs the tonne-mile and voyage-length "
                   "consequence of the route decision the toll is one input to, plus GER40 and "
                   "EUSTX50 for the European landed-cost leg. The toll enters this pack as a "
                   "TERM IN A DETOUR ARITHMETIC (see eg_suez_detour) that is DECLARED UNMEASURED "
                   "rather than guessed."},
    {"instrument": "TTF and JKM natural gas benchmarks; Brent-linked LNG contract prices",
     "why": "absent; XNGUSD on this account is Henry Hub, a North American price. Egypt's LNG "
            "import and export economics are TTF- and Brent-linked, so the Egyptian gas "
            "mechanism reaches XNGUSD only through a transatlantic BASIS the desk cannot trade.",
     "carried_by": "XNGUSD with the basis declared as a named weakness inside the edge, and "
                   "XBRUSD for the Brent-linked contract leg. Any Egypt-to-XNGUSD cell that does "
                   "not carry the basis control is measuring the US gas market."},
    {"instrument": "Container and tanker freight rates (Baltic indices, WCI, Shanghai-Rotterdam)",
     "why": "absent; no freight contract is quoted on this account. Freight is the LITERAL "
            "transmission variable of the Suez mechanism and the desk has no leg in it.",
     "carried_by": "the XBRUSD-XTIUSD spread (tonne-miles and voyage length price into the "
                   "seaborne crude differential) and GER40/EUSTX50 (landed cost into European "
                   "industrial margin). The freight leg itself is an OBSERVABLE in the "
                   "eg_red_sea_diversion domain and is never a target."},
    {"instrument": "EGX-listed single names -- banks, developers, industrials",
     "why": "REFUSED, not absent. Some are quotable elsewhere; the two-lane order (2026-09-06) "
            "forbids hunting any single name for a statistical hypothesis, and every equity cell "
            "raises the deflated-Sharpe bar for the FX and commodity cells that suit the method.",
     "carried_by": "the EGX foreign-flow aggregate as an observable, and EUSTX50/GER40/USDZAR as "
                   "the factor legs. Single-name Egyptian news belongs in the EVENT lane."},
)

# --------------------------------------------------------------------------- central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "Central Bank of Egypt (CBE)",
    "native_name": "البنك المركزي "
                   "المصري",
    "framework": (
        "A DE FACTO PEG PUNCTUATED BY DISCRETE DEVALUATIONS, NOW A DECLARED FLOAT -- and the "
        "honest description is that sentence, not either half of it. For most of the modern "
        "period the CBE held the pound at an administered level against the dollar, defended it "
        "with reserves, Gulf deposits and rationed access to foreign exchange, and then moved it "
        "in ONE STEP when the defence became unaffordable: November 2016, March 2022, October "
        "2022, January 2023 and 6 March 2024. Between steps the pound is close to a constant and "
        "its measured volatility is near zero, which is a PROPERTY OF THE POLICY and not of the "
        "economy; the variance lives in the parallel rate and in the size of the next step. Since "
        "6 March 2024 the CBE has declared a flexible, market-determined rate and has, so far, "
        "let the pound move continuously. WHETHER THIS FLOAT IS STRUCTURALLY DIFFERENT FROM THE "
        "1994-2000 and 2016-2021 'floats' -- both of which reverted to a de facto peg within "
        "about a year and a half -- IS UNMEASURED, and is the single most important open question "
        "in this pack. No cell here may assume the float persists; the era table carries the "
        "boundary and a study pooling across it is pooling two different data-generating "
        "processes."),
    "committee": "Monetary Policy Committee (MPC). Votes are NOT disclosed as a count -- unlike "
                 "the SARB, which publishes the split. So Egypt gives ONE event per meeting "
                 "where South Africa gives two, and a vote-split channel cannot be tested here. "
                 "That absence is a design constraint, not an oversight.",
    "policy_rate": "the overnight deposit and overnight lending rates, which bracket a corridor; "
                   "the main operation rate and the discount rate sit inside it. The DEPOSIT "
                   "rate is the one the market quotes as 'the' policy rate.",
    "target": "an inflation target announced as a point with a tolerance band, restated by the "
              "CBE across programme reviews. THE TARGET HAS BEEN MISSED BY MULTIPLES, not by "
              "basis points -- headline inflation ran above 30% through much of 2023-2024 -- so "
              "a Taylor-type reaction function fitted on Egyptian data is fitting a bank that "
              "was managing a balance-of-payments crisis, not an inflation gap.",
    "meetings_per_year": 8,
    "schedule_rule": (
        "EIGHT scheduled MPC meetings a year, roughly every six to seven weeks, with the "
        "calendar for year N published on cbe.org.eg during year N-1. Announcements land in the "
        "LATE AFTERNOON CAIRO TIME, typically after the local market close and normally on a "
        "Thursday -- Thursday being the last business day of the Egyptian week, which is Sunday "
        "to Thursday. EXTRAORDINARY MEETINGS HAPPEN AND THEY ARE WHERE THE HISTORY IS: the 6 "
        "March 2024 emergency meeting delivered a 600bp hike and the float, and no rule predicts "
        "one. An event study restricted to the published calendar therefore MISSES THE LARGEST "
        "EGYPTIAN MONETARY OBSERVATION OF THE DECADE, which is the opposite of the usual "
        "small-sample problem and is worse, because the sample is not merely small but "
        "SELECTED AGAINST THE EVENT OF INTEREST."),
    "timezone": (
        "EET = UTC+2 in winter, EEST = UTC+3 in summer. **EGYPT REINSTATED DAYLIGHT SAVING TIME "
        "FROM 2023** (it had been abolished in 2014): DST begins on the LAST FRIDAY OF APRIL and "
        "ends on the LAST THURSDAY OF OCTOBER. SO THE UTC TIME OF AN EGYPTIAN ANNOUNCEMENT MOVES "
        "TWICE A YEAR. This is the pack's first measurement trap and it is stated as a trap: "
        "South Africa (SAST, no DST) and Nigeria (WAT, no DST) are fixed against UTC and their "
        "packs can hard-code an announcement hour; EGYPT CANNOT. A fixed-UTC event window "
        "anchored on a Cairo statement is off by one hour for roughly half the sample, which for "
        "a one-minute or five-minute bar study means measuring an entirely different session and "
        "reporting it confidently. Worse, it is off by one hour in a BLOCK -- summer versus "
        "winter -- so the error correlates with season and will not average out."),
    "dst_rule": {
        "statute": "Law 24 of 2023 reinstating summer time, applied from the last Friday of "
                   "April 2023 (2023-04-28)",
        "starts": "last Friday of April, at midnight local",
        "ends": "last Thursday of October, at midnight local",
        "derived_2024": ("2024-04-26", "2024-10-31"),
        "derived_2025": ("2025-04-25", "2025-10-30"),
        "derived_2026": ("2026-04-24", "2026-10-29"),
        "status": "RULE_DERIVED. The rule is statutory and stable; the Cabinet has in the past "
                  "moved the transition to avoid colliding with Ramadan, so a derived date is a "
                  "PREDICTION and the data plane must confirm it against the gazette before any "
                  "intraday study crosses one of these boundaries.",
        "ramadan_interaction": "Egypt suspended summer time during Ramadan in some earlier "
                               "years. If that practice returns, the offset changes THREE times "
                               "in a year on a LUNAR clock, which no fixed-UTC pipeline survives. "
                               "Declared here so it is checked rather than discovered.",
    },
    "fx_operations": (
        "THE CBE IS THE OPPOSITE OF THE SARB AND THE CONTRAST IS THE RESEARCH DESIGN. South "
        "Africa's central bank states it does not target the rand and does not defend it; Egypt's "
        "has, for most of its history, set the rate administratively and defended it with every "
        "instrument it had: reserves, Gulf central-bank deposits, a foreign-currency auction, "
        "rationed bank access, a priority list for imports, and -- the binding one -- the "
        "LETTER-OF-CREDIT REQUIREMENT that made an importer wait for an allocation. The "
        "consequence for measurement is severe: the OFFICIAL price is a policy variable with "
        "almost no information in it between steps, and the informative price is the PARALLEL "
        "one, which is not officially published. This is why the pack's central observable is a "
        "SPREAD rather than a rate."),
    "liquidity_absorption": (
        "HIGH-YIELD CERTIFICATES OF DEPOSIT ARE EGYPT'S DISTINCTIVE MONETARY INSTRUMENT. After "
        "each devaluation step the state banks issued one-year and three-year certificates at "
        "headline rates far above the policy corridor (the 2022 and 2023 issues at 18%, 22% and "
        "23.5%, and a 27%/23.5% pair around the 2024 float) specifically to absorb pound "
        "liquidity that would otherwise chase dollars or gold. THE MATURITY OF A LARGE "
        "CERTIFICATE TRANCHE IS THEREFORE A DATED, PRE-ANNOUNCED RELEASE OF POUND LIQUIDITY into "
        "an economy with a parallel dollar market -- one of the few genuinely SCHEDULED flow "
        "events in this pack, and the reason the certificate instruments are in the terminology "
        "table and the dataset catalogue rather than treated as retail banking trivia."),
    "reserves": (
        "Net international reserves are published MONTHLY, in the first week, for the prior "
        "month. They are the headline number Egyptian coverage watches. BUT THE DIAGNOSTIC "
        "SERIES IS A DIFFERENT ONE: NET FOREIGN ASSETS OF THE BANKING SYSTEM, which went deeply "
        "NEGATIVE before the 2022-2024 devaluation sequence as banks sold forward and borrowed "
        "abroad to hold the official rate. NIR can be supported by deposits and swaps that are "
        "liabilities; NFA nets them. A pack that watched only NIR would have seen the defence "
        "and not the cost of it."),
    "publication_classes": ("MPC press release", "Monthly Statistical Bulletin",
                            "monetary and banking developments release", "annual report",
                            "official daily exchange rate page", "net foreign assets series",
                            "balance of payments (quarterly, with remittances and tourism)"),
    "decision_dates": {
        2024: ("2024-02-01", "2024-03-06", "2024-03-28", "2024-05-23", "2024-07-18",
               "2024-09-05", "2024-10-17", "2024-11-21", "2024-12-26"),
        2025: ("2025-02-20", "2025-04-17", "2025-05-22", "2025-07-10", "2025-08-28",
               "2025-10-02", "2025-11-20", "2025-12-25"),
        2026: ("2026-02-19", "2026-04-02", "2026-05-21", "2026-07-09", "2026-08-27",
               "2026-10-01", "2026-11-19", "2026-12-24"),
    },
    "decision_dates_status": {
        2024: "PUBLIC_RECORD. NINE entries for an EIGHT-meeting year: 2024-03-06 was an "
              "EXTRAORDINARY meeting -- the 600bp hike and the float -- and is included because "
              "excluding it would delete the observation the whole pack is about. Any code that "
              "counts meetings per year off this tuple must handle the extra row.",
        2025: "PUBLIC_RECORD, eight scheduled meetings, no extraordinary meeting recorded.",
        2026: "RULE_DERIVED_UNVERIFIED -- eight meetings, the historical six-to-seven-week "
              "spacing, Thursday announcements. THE DATA PLANE MUST REPLACE THESE WITH THE "
              "PUBLISHED CALENDAR BEFORE ANY 2026 EVENT STUDY IS SCORED; an event study anchored "
              "on a guessed date measures the wrong session and reports it confidently. For "
              "Egypt this is compounded by the DST boundary: a guessed DATE plus a shifting UTC "
              "OFFSET is two independent ways to land on the wrong minute.",
    },
    "decision_time_utc": (
        "NOT A CONSTANT, AND THAT IS THE POINT. The statement lands in the late afternoon Cairo "
        "time, so the same local hour is 15:00-16:00 UTC in winter (EET, UTC+2) and 14:00-15:00 "
        "UTC in summer (EEST, UTC+3). The pack refuses to assert a minute it has not read from "
        "the payload: the data plane stamps the observed publication time per release and the "
        "event studies use the STAMP, never this description."),
    "decision_time_local": "late afternoon Cairo time, after the EGX close at 14:30 and normally "
                           "on a Thursday, the last business day of the Egyptian week",
    "notes": "cbe.org.eg serves the official daily rate, the monetary statistics and the MPC "
             "statements free of charge in Arabic and English, but as PAGES AND PDFs rather than "
             "a documented API -- the opposite of the SARB, whose swagger-described REST service "
             "is why the ZA data plane exists first. The EG lane is therefore a page-shape lane "
             "with vintage storage, and a shape change is a NAMED failure rather than a silently "
             "empty series.",
}


# --------------------------------------------------------------------------- fixings
FIXING_CONVENTIONS: dict[str, Any] = {
    "cbe_official_daily_rate": {
        "name": "CBE official daily exchange rate (the published buy/sell for the pound)",
        "publisher": "Central Bank of Egypt",
        "definition": "the official reference rate against the dollar and the other majors, "
                      "published each Egyptian business day",
        "published_local": "end of the Cairo business day, Sunday to Thursday",
        "published_utc": "approximately 14:00-16:00 UTC in winter and 13:00-15:00 UTC in summer; "
                         "the EXACT stamp is what the data plane records per vintage, because "
                         "the pack refuses to assert a minute it has not read from the payload",
        "note": "BETWEEN DEVALUATION STEPS THIS SERIES IS NEARLY A CONSTANT. Its realised "
                "volatility is a measure of the POLICY, not of the economy, and a GARCH or "
                "range model fitted to it is fitting an administered number. Under the peg "
                "regimes it is the least informative series in this pack; since the 2024 float "
                "it is informative again, which is itself an era boundary.",
    },
    "interbank_rate": {
        "name": "the onshore interbank USD/EGP rate",
        "publisher": "the banks, reported through CBE statistics and the local financial press",
        "definition": "the rate at which Egyptian banks actually deal with each other",
        "why_it_matters": "under the control regimes the interbank market was THIN TO ABSENT -- "
                          "banks had dollars rationed to them and could not sell freely -- so a "
                          "quoted interbank rate close to the official rate was evidence of a "
                          "DEAD MARKET, not of a credible one. VOLUME, NOT LEVEL, is the "
                          "observable here, and it is the harder one to obtain.",
        "status": "PARTIALLY PUBLISHED. Treated as an observable with irregular coverage and "
                  "marked NOT_PIT_SAFE where a continuous vintage cannot be reconstructed.",
    },
    "parallel_street_rate": {
        "name": "the parallel (street / black) market rate",
        "publisher": "NOBODY OFFICIAL -- and that is the entire point",
        "definition": "the rate at which a household or importer can actually obtain dollars "
                      "outside the banking system, quoted by exchange bureaux, informal dealers "
                      "and the Egyptian-language price pages and channels that aggregate them",
        "why_it_matters": "THIS IS THE INFORMATIVE PRICE. When access to the official rate is "
                          "rationed, the official rate stops clearing the market and the "
                          "parallel rate becomes the marginal price of a dollar in Egypt. Every "
                          "quantity that matters -- the importer's real cost, the remittance "
                          "sender's choice of channel, the household's decision to buy gold -- "
                          "is set against it.",
        "provenance": "PUBLIC WEB COMMENTARY, mined for VERBATIM CLAIMS with the source, the "
                      "timestamp and the quoted number preserved. It is not an official series, "
                      "it is not audited, its coverage is uneven, and quotes from different "
                      "aggregators disagree by more than a normal bid-ask. All of that is "
                      "recorded per observation rather than averaged away.",
        "pit_feasible": False,
    },
    "official_vs_parallel_spread": {
        "name": "THE SPREAD -- official rate versus parallel rate, in percent",
        "definition": "(parallel / official - 1), measured on the same day from the two sources "
                      "above",
        "why_it_matters": (
            "EGYPT'S SINGLE MOST VALUABLE PUBLISHED-ADJACENT OBSERVABLE, and the mechanism is "
            "specific and repeatable: THE SPREAD WIDENS FOR MONTHS, AND THEN CLOSES IN ONE STEP. "
            "It is not a noisy proxy for the exchange rate -- it is a measure of how far the "
            "administered price has drifted from the clearing price, which is exactly the "
            "quantity that determines when the administered price must move. It widened through "
            "2021 into March 2022, again through 2022 into October 2022 and January 2023, and "
            "most dramatically through 2023 into the 6 March 2024 float, where the parallel rate "
            "had reached far beyond the official one and the step closed almost the whole gap at "
            "once. A wide spread is therefore a DEVALUATION PROBABILITY, and the desk's edge is "
            "in the frontier-stress and peer-currency repricing around the step, never in the "
            "pound itself, which it cannot trade."),
        "hazard": "THE SPREAD IS ALSO THE MOST LIKELY THING IN THIS PACK TO BE FITTED TO NOISE. "
                  "There are FIVE steps in a decade: n is single digits, the observations are "
                  "serially dependent, and the parallel series is commentary-sourced. Any cell "
                  "built on it must carry that n explicitly and can never clear a gauntlet on "
                  "the strength of one episode.",
        "pit_feasible": False,
    },
    "gold_pound_local_premium": {
        "name": "the gold pound (jineih al-dhahab) and 21-carat local premium",
        "definition": "the local Cairo price of the 8g gold pound coin and of 21-carat jewellery, "
                      "converted at the official rate, expressed as a premium over the world "
                      "gold price converted at the same rate",
        "why_it_matters": "A HOUSEHOLD-LEVEL CAPITAL-CONTROL GAUGE. Egyptians cannot freely buy "
                          "dollars, but they can buy gold, and a gold purchase is a dollar "
                          "purchase with a metal wrapper. When the control binds, the local gold "
                          "price rises ABOVE the world price converted at the official rate, by "
                          "roughly the parallel premium plus a making charge. So the gold "
                          "premium is a SECOND, INDEPENDENT ESTIMATE OF THE SAME WEDGE the "
                          "parallel rate measures -- and two independent estimates of one latent "
                          "quantity is a far stronger research object than either alone.",
        "control": "the MAKING CHARGE (al-masnaeiyya) is a real, variable, non-monetary component "
                   "of the jewellery price and moves with local labour and demand. The COIN is "
                   "the cleaner instrument because its making charge is smaller and more stable. "
                   "A premium computed from jewellery without netting the making charge is "
                   "measuring the goldsmith, not the control.",
        "pit_feasible": False,
    },
    "no_offshore_fix": {
        "name": "THERE IS NO OFFSHORE EGP FIX AND THE POUND IS NOT DELIVERABLE OFFSHORE",
        "definition": "no WM/Refinitiv-style tradable fix in EGP that this desk can reach, no "
                      "offshore clearing, no listed future, and no NDF the desk can price",
        "why_it_matters": "the absence is structural and it is why OWN_PRICE is empty. There is "
                          "no fixing window to study, no rebalance flow to anticipate and no "
                          "settlement convention that generates a dated FX order. Every "
                          "microstructure mechanism that South Africa's pack gets for free is "
                          "simply not available here, and this key exists so that no future "
                          "session goes looking for it.",
        "carried_by": "USDTRY and USDZAR, whose fixes and rebalances DO exist and which share the "
                      "EM/frontier factor",
    },
    "dst": "EGYPT OBSERVES DST AGAIN SINCE 2023 (last Friday of April to last Thursday of "
           "October). London and New York move on DIFFERENT dates, so the Cairo-to-London offset "
           "is not constant even in the weeks when both observe summer time, and there are "
           "SHOULDER WEEKS each spring and autumn where the usual offset is wrong. Any EG session "
           "study that hard-codes a UTC offset is wrong for half the year plus the shoulders.",
}


# --------------------------------------------------------------------------- settlement
SETTLEMENT_CONVENTIONS: dict[str, Any] = {
    "spot": "T+2 for onshore USD/EGP between Egyptian banks. IRRELEVANT TO THIS DESK IN "
            "PRACTICE, because the desk has no EGP leg -- recorded so the asymmetry with the ZA "
            "pack is explicit rather than assumed.",
    "deliverability": (
        "THE POUND IS NOT DELIVERABLE OFFSHORE. There is no offshore EGP clearing, no 24-hour "
        "price, and no liquid NDF market the desk can reach. This is the structural opposite of "
        "the rand and it is the reason Egypt is transmission-only: South Africa offers a clean, "
        "liquid, globally traded price with physical production data behind it; Egypt offers a "
        "RATIONED price with a wedge, and the wedge is the research object."),
    "capital_control_in_practice": (
        "THE CONTROL WAS NEVER CALLED A CONTROL. From early 2022 the CBE required imports to be "
        "financed by LETTERS OF CREDIT rather than documentary collection, which converted a "
        "commercial decision into a QUEUE for a bank allocation of foreign exchange. The "
        "observable consequence was physical: billions of dollars of goods stranded at Egyptian "
        "ports for months, factories idled for want of inputs, and a backlog that was itself "
        "reported in the press with dated estimates. The LC requirement was formally lifted at "
        "the end of 2022 and the backlog cleared over 2023-2024. FOR RESEARCH THIS MATTERS "
        "TWICE: it is the mechanism that made the parallel premium persist, and it is a dated, "
        "announced, non-price policy change -- a natural experiment with a gazette behind it."),
    "repatriation_queue": (
        "THE CBE'S FX REPATRIATION MECHANISM guaranteed foreign portfolio investors conversion "
        "and exit at the official rate. When it was suspended under stress, exiting investors "
        "joined a QUEUE -- their pounds were real and their dollars were not available -- and the "
        "queue's length became a credibility observable in its own right. The 2024 float was "
        "accompanied by the clearing of that backlog. A carry study that treats the T-bill yield "
        "as the return ignores that the EXIT was rationed, which is where the actual loss lived."),
    "equity_settlement": "T+2 at the EGX through MCDR (Misr for Central Clearing, Depository and "
                         "Registry), with an intraday-trading list settling same-day. A foreign "
                         "net-buy print on day T therefore creates an FX obligation on T+2 -- "
                         "BUT with no EGP leg on this account the desk cannot trade that "
                         "conversion, so the flow enters as an OBSERVABLE about risk appetite "
                         "and not, as in the ZA pack, as a dated currency flow.",
    "trading_week": (
        "THE EGYPTIAN WEEK IS SUNDAY TO THURSDAY; THE WEEKEND IS FRIDAY AND SATURDAY. This is a "
        "real and repeatedly costly measurement trap. (1) The EGX prints its daily foreign/Arab/"
        "Egyptian net-flow table on a SUNDAY, when no other market in this desk's universe is "
        "open -- so an Egyptian risk-appetite observable exists BEFORE the global week starts, "
        "which is a genuine information-timing edge and not a nuisance. (2) The EGX and the "
        "Egyptian banks are SHUT ON FRIDAY, when the broker's week is still running, so a Friday "
        "shock reaches Egypt only on Sunday and arrives as a gap. (3) Any code that computes "
        "'previous business day' with a Monday-Friday calendar is wrong in Egypt on both ends of "
        "the week."),
    "ramadan_sessions": (
        "THE EGX SHORTENS ITS SESSION FOR RAMADAN -- typically to around 10:00-13:30 Cairo rather "
        "than 10:00-14:30 -- and Egyptian banking hours shorten with it. THE WINDOW IS LUNAR: it "
        "moves about eleven days EARLIER each Gregorian year, so a session-length regime "
        "boundary sweeps backwards through the calendar and cannot be captured by any fixed "
        "month-of-year control. A liquidity or intraday-seasonality study that does not carry a "
        "Ramadan indicator is mixing a shortened session into its baseline for roughly thirty "
        "days a year, at a different place in the year every year."),
    "month_end": "Importer dollar demand and the state's own import programme concentrate around "
                 "month-end and around the quarterly external-debt service dates. Under the "
                 "rationed regimes this showed up as a widening of the PARALLEL premium rather "
                 "than a move in the official rate -- the same demand, routed to the only price "
                 "allowed to move.",
    "fiscal_events": "The budget is presented to Parliament in the spring for a fiscal year "
                     "beginning 1 July, and IMF programme review completions are announced on "
                     "the Fund's own calendar. The review completions are the larger market "
                     "events, because they release a tranche and validate the policy path.",
}


# --------------------------------------------------------------------------- exchanges
EXCHANGES: dict[str, Any] = {
    "cash": {
        "name": "The Egyptian Exchange (EGX), Cairo and Alexandria",
        "trading_week": "SUNDAY TO THURSDAY. Closed Friday and Saturday.",
        "hours_local": "10:00-14:30 Cairo, continuous, with a pre-open call auction before 10:00",
        "hours_utc": "08:00-12:30 in winter (EET, UTC+2) and 07:00-11:30 in summer (EEST, "
                     "UTC+3). TWO DIFFERENT UTC WINDOWS FOR ONE LOCAL SESSION -- the DST trap "
                     "again, in the place it does the most damage, because a session-overlap "
                     "study is exactly the kind that hard-codes UTC hours.",
        "ramadan_hours_local": "shortened, typically to about 10:00-13:30 Cairo; the exact "
                               "schedule is an EGX notice each year and is DECLARED, NOT "
                               "RE-DERIVED here",
        "settlement": "T+2 for equities through MCDR, with a separate intraday-trading list "
                      "settling same-day",
        "indices": "EGX30 is the headline capitalisation-weighted index (EGX30 Capped, EGX70 EWI "
                   "and EGX100 EWI alongside it). It is quoted in POUNDS, so in a devaluation "
                   "year its pound return and its dollar return tell opposite stories and only "
                   "the pound one is the headline.",
        "index_symbols": (),
        "index_symbols_note": "EMPTY BY MEASUREMENT: no Egyptian equity index is quoted on this "
                              "account. EGX30 is named in ABSENT_INSTRUMENTS and carried by "
                              "EUSTX50, GER40 and USDZAR rather than silently dropped. Nothing "
                              "in this pack may place an order in an Egyptian index.",
        "public_data": (
            "THE ONE GENUINELY VALUABLE FREE SERIES THE EGX PUBLISHES: a DAILY NET-FLOW "
            "BREAKDOWN BY INVESTOR ORIGIN -- Egyptians, Arabs and Foreigners, each shown as "
            "buy, sell and net, and separately for institutions and individuals. Very few "
            "emerging markets publish a daily foreign-flow split for free, and Egypt's "
            "additionally separates ARAB money from other foreign money, which is a distinction "
            "that matters here: Gulf flow behaves like strategic and sovereign money and "
            "non-Arab foreign flow behaves like portfolio money, and mixing them averages two "
            "different actors. It prints on Sunday through Thursday, after the 14:30 close."),
    },
    "derivatives": {
        "name": "NONE MATERIAL. There is no deep listed Egyptian equity-index or currency "
                "futures market for this desk to read.",
        "status": "DECLARED ABSENT. The EGX has worked towards a futures market and short "
                  "selling has been permitted in limited form, but there is no liquid, publicly "
                  "reported open-interest series comparable to the JSE's currency futures. So "
                  "Egypt has NO DOMESTIC POSITIONING MIRROR -- the ZA pack's onshore-versus-"
                  "offshore positioning divergence has no Egyptian counterpart, and the "
                  "positioning sources below say so by name rather than substituting a proxy.",
        "expiry_rule": "n/a -- no quarterly close-out grid exists to anchor an expiry study on. "
                       "UNMEASURED is the verdict, and it is a verdict about the market's "
                       "structure, not about the desk's effort.",
    },
    "commodity": {
        "name": "The Egyptian Commodities Exchange and the state procurement channel",
        "status": "EARLY AND THIN. Egypt's agricultural trade is dominated by STATE PROCUREMENT "
                  "-- GASC tenders for wheat and the Ministry of Supply's domestic purchase "
                  "programme -- rather than by an exchange. So the price-forming Egyptian "
                  "agricultural event is a TENDER ANNOUNCEMENT, not a settlement print, and the "
                  "wheat domain is built on tenders accordingly.",
    },
    "note": "The EGX is a real exchange with a real free-float and a genuinely useful free "
            "foreign-flow table, and it is NOT reachable as a price on this account. Both halves "
            "of that sentence are load-bearing.",
}


FISCAL_YEAR_END: dict[str, str] = {
    "government": "30 JUNE. The Egyptian fiscal year runs 1 July to 30 June -- NOT the calendar "
                  "year and NOT South Africa's 31 March. The budget is presented to Parliament "
                  "in the spring and takes effect on 1 July, and the subsidy allocations inside "
                  "it (bread, fuel, electricity) are the line items that bind against the "
                  "wheat and energy import bills this pack tracks.",
    "corporate": "31 December is the dominant corporate year-end for EGX-listed companies, with "
                 "banks on the same calendar. There is therefore a genuine December reporting "
                 "cluster, but with no tradable Egyptian equity leg it is an OBSERVABLE about "
                 "flow and not a seasonal the desk can position for.",
    "cbe": "the Central Bank of Egypt's own financial year ends 30 June, with the government's",
    "imf_programme": "programme reviews run on the FUND'S calendar, not Egypt's fiscal one, and "
                     "the two do not align. A study that assumes fiscal-year seasonality drives "
                     "programme milestones is imposing the wrong clock on the larger event.",
}


# --------------------------------------------------------------------------- holidays
#: THREE INTERLEAVED CALENDARS IN ONE COUNTRY, and they do not commute.
#:
#:   1. GREGORIAN NATIONAL days, fixed to a solar date: the revolutions, the wars, Labour Day and
#:      Coptic Christmas (7 January, fixed on the Gregorian calendar since the Coptic Nativity
#:      currently falls there).
#:   2. COPTIC MOVEABLE: Sham El-Nessim, the Monday after Coptic (Orthodox) Easter. It follows
#:      the JULIAN computus, so it is usually a week or more after Western Easter and cannot be
#:      derived from the Western Easter rule that the ZA pack uses for Good Friday.
#:   3. ISLAMIC (HIJRI) days, which are MOON-DEPENDENT and are DECLARED BY THE CABINET. Every
#:      Islamic date in this table is an ESTIMATE and is labelled one, in the name string itself,
#:      for every year -- including the past ones, because a session reading only the table must
#:      see the uncertainty without going to look for it.
#:
#: THE OBSERVANCE AND BRIDGING CONVENTION IS NOT A RULE, IT IS A DECISION. Egypt's Cabinet
#: routinely MOVES a mid-week public holiday to the nearest Thursday to create a long weekend,
#: and routinely ADDS bridging days around Eid. Both are gazette decisions taken weeks in
#: advance, not statutory rules a calendar library can derive. And because the Egyptian weekend
#: is FRIDAY-SATURDAY, a holiday landing on a Friday costs no business day at all while one
#: landing on a Sunday costs a full session -- the exact inverse of a Western calendar's
#: intuition.
_EG_HOLIDAYS: dict[int, dict[str, str]] = {
    2024: {
        "2024-01-07": "Coptic Christmas (Eid al-Milad al-Magid)",
        "2024-01-25": "Revolution Day and Police Day (25 January)",
        "2024-04-10": "Eid al-Fitr, day 1 (MOON-DEPENDENT ESTIMATE)",
        "2024-04-11": "Eid al-Fitr, day 2 (MOON-DEPENDENT ESTIMATE)",
        "2024-04-12": "Eid al-Fitr, day 3 (MOON-DEPENDENT ESTIMATE)",
        "2024-04-25": "Sinai Liberation Day",
        "2024-05-01": "Labour Day",
        "2024-05-06": "Sham El-Nessim (Monday after Coptic Easter)",
        "2024-06-16": "Eid al-Adha, day 1 (MOON-DEPENDENT ESTIMATE)",
        "2024-06-17": "Eid al-Adha, day 2 (MOON-DEPENDENT ESTIMATE)",
        "2024-06-18": "Eid al-Adha, day 3 (MOON-DEPENDENT ESTIMATE)",
        "2024-06-19": "Eid al-Adha, day 4 (MOON-DEPENDENT ESTIMATE)",
        "2024-06-30": "June 30 Revolution Day",
        "2024-07-07": "Islamic New Year, 1 Muharram (MOON-DEPENDENT ESTIMATE)",
        "2024-07-23": "July 23 Revolution Day",
        "2024-09-15": "Prophet's Birthday, al-Mawlid al-Nabawi (MOON-DEPENDENT ESTIMATE)",
        "2024-10-06": "Armed Forces Day (6 October)",
    },
    2025: {
        "2025-01-07": "Coptic Christmas (Eid al-Milad al-Magid)",
        "2025-01-25": "Revolution Day and Police Day (25 January; falls on a Saturday, which is "
                      "part of the Egyptian weekend -- no business day is lost)",
        "2025-03-30": "Eid al-Fitr, day 1 (MOON-DEPENDENT ESTIMATE)",
        "2025-03-31": "Eid al-Fitr, day 2 (MOON-DEPENDENT ESTIMATE)",
        "2025-04-01": "Eid al-Fitr, day 3 (MOON-DEPENDENT ESTIMATE)",
        "2025-04-21": "Sham El-Nessim (Monday after Coptic Easter)",
        "2025-04-25": "Sinai Liberation Day (falls on a Friday, the Egyptian weekend)",
        "2025-05-01": "Labour Day",
        "2025-06-06": "Eid al-Adha, day 1 (MOON-DEPENDENT ESTIMATE)",
        "2025-06-07": "Eid al-Adha, day 2 (MOON-DEPENDENT ESTIMATE)",
        "2025-06-08": "Eid al-Adha, day 3 (MOON-DEPENDENT ESTIMATE)",
        "2025-06-09": "Eid al-Adha, day 4 (MOON-DEPENDENT ESTIMATE)",
        "2025-06-26": "Islamic New Year, 1 Muharram (MOON-DEPENDENT ESTIMATE)",
        "2025-06-30": "June 30 Revolution Day",
        "2025-07-23": "July 23 Revolution Day",
        "2025-09-04": "Prophet's Birthday, al-Mawlid al-Nabawi (MOON-DEPENDENT ESTIMATE)",
        "2025-10-06": "Armed Forces Day (6 October)",
    },
    2026: {
        "2026-01-07": "Coptic Christmas (Eid al-Milad al-Magid)",
        "2026-01-25": "Revolution Day and Police Day (25 January; falls on a SUNDAY, which in "
                      "Egypt is a full WORKING day -- the closure costs a whole session and "
                      "there is nothing to shift, the inverse of the Western intuition)",
        "2026-03-20": "Eid al-Fitr, day 1 (MOON-DEPENDENT ESTIMATE)",
        "2026-03-21": "Eid al-Fitr, day 2 (MOON-DEPENDENT ESTIMATE)",
        "2026-03-22": "Eid al-Fitr, day 3 (MOON-DEPENDENT ESTIMATE)",
        "2026-04-13": "Sham El-Nessim (Monday after Coptic Easter)",
        "2026-04-25": "Sinai Liberation Day (falls on a Saturday, the Egyptian weekend)",
        "2026-05-01": "Labour Day (falls on a Friday, the Egyptian weekend)",
        "2026-05-27": "Eid al-Adha, day 1 (MOON-DEPENDENT ESTIMATE)",
        "2026-05-28": "Eid al-Adha, day 2 (MOON-DEPENDENT ESTIMATE)",
        "2026-05-29": "Eid al-Adha, day 3 (MOON-DEPENDENT ESTIMATE)",
        "2026-05-30": "Eid al-Adha, day 4 (MOON-DEPENDENT ESTIMATE)",
        "2026-06-16": "Islamic New Year, 1 Muharram (MOON-DEPENDENT ESTIMATE)",
        "2026-06-30": "June 30 Revolution Day",
        "2026-07-23": "July 23 Revolution Day",
        "2026-08-25": "Prophet's Birthday, al-Mawlid al-Nabawi (MOON-DEPENDENT ESTIMATE)",
        "2026-10-06": "Armed Forces Day (6 October)",
    },
}

#: THE LUNAR ANCHORS, SEPARATED OUT ON PURPOSE. These are the dates the whole Islamic half of the
#: calendar hangs on, and every one of them is an ESTIMATE from the arithmetic Hijri calendar,
#: not an observation. The AUTHORITY is the Egyptian Cabinet's gazette decision, taken days
#: before the event on the report of the moon-sighting committee, and it has historically
#: differed from the arithmetic estimate by a day in either direction. The desk REFUSES TO TRADE
#: A GUESSED EID WINDOW: a cell whose window overlaps one of these dates is deferred until the
#: gazette is read, because being one day out on a four-day closure is not a rounding error, it
#: is a different event.
_EG_LUNAR_ANCHORS: dict[int, dict[str, Any]] = {
    2024: {
        "ramadan_start": "2024-03-11",
        "eid_al_fitr": ("2024-04-10", "2024-04-11", "2024-04-12"),
        "eid_al_adha": ("2024-06-16", "2024-06-17", "2024-06-18", "2024-06-19"),
        "islamic_new_year": ("2024-07-07",),
        "prophets_birthday": ("2024-09-15",),
        "status": "DECLARED_LUNAR_ESTIMATE",
    },
    2025: {
        "ramadan_start": "2025-03-01",
        "eid_al_fitr": ("2025-03-30", "2025-03-31", "2025-04-01"),
        "eid_al_adha": ("2025-06-06", "2025-06-07", "2025-06-08", "2025-06-09"),
        "islamic_new_year": ("2025-06-26",),
        "prophets_birthday": ("2025-09-04",),
        "status": "DECLARED_LUNAR_ESTIMATE",
    },
    2026: {
        "ramadan_start": "2026-02-18",
        "eid_al_fitr": ("2026-03-20", "2026-03-21", "2026-03-22"),
        "eid_al_adha": ("2026-05-27", "2026-05-28", "2026-05-29", "2026-05-30"),
        "islamic_new_year": ("2026-06-16",),
        "prophets_birthday": ("2026-08-25",),
        "status": "DECLARED_LUNAR_ESTIMATE",
    },
}

HOLIDAYS_RULE: dict[str, Any] = {
    "rule": (
        "EGYPT RUNS THREE CALENDARS AT ONCE AND A SINGLE-CALENDAR MODEL OF ITS CLOSURES IS WRONG "
        "ABOUT ROUGHLY HALF THE DAYS.\n"
        "(1) GREGORIAN NATIONAL, fixed to a solar date and stable year to year: 7 January "
        "(Coptic Christmas, Eid al-Milad al-Magid), 25 January (Revolution Day and Police Day), "
        "25 April (Sinai Liberation Day), 1 May (Labour Day), 30 June (June 30 Revolution), "
        "23 July (July 23 Revolution) and 6 October (Armed Forces Day).\n"
        "(2) COPTIC MOVEABLE: Sham El-Nessim, the Monday after Coptic (Orthodox) Easter, which "
        "follows the JULIAN computus and therefore normally falls a week or more after Western "
        "Easter. It CANNOT be derived from the Western Easter rule -- 2024-05-06, 2025-04-21 and "
        "2026-04-13 are the tabulated dates and each is a Monday after an Orthodox Easter "
        "Sunday, not after the Western one. Sham El-Nessim is a pharaonic spring festival "
        "observed by the whole country regardless of religion, which is why it closes the "
        "market while the Coptic Easter Sunday itself does not.\n"
        "(3) ISLAMIC (HIJRI), MOON-DEPENDENT AND DECLARED BY THE CABINET: Eid al-Fitr (three "
        "days at the end of Ramadan), Eid al-Adha (four days), the Islamic New Year (1 Muharram) "
        "and the Prophet's Birthday (al-Mawlid al-Nabawi, 12 Rabi al-Awwal). These move about "
        "eleven days EARLIER each Gregorian year, so over a decade they sweep backwards through "
        "the entire calendar -- which means a month-of-year seasonal control does not hold them "
        "fixed and a study that uses one is confounding the lunar cycle with the solar one.\n"
        "OBSERVANCE AND BRIDGING: the Egyptian weekend is FRIDAY AND SATURDAY, so a closure "
        "falling on a Friday costs no business day while one falling on a Sunday costs a full "
        "session -- the inverse of the Western convention, and the reason the ZA pack's "
        "Sunday-substitution logic cannot be reused here. The Cabinet routinely MOVES a mid-week "
        "public holiday to the nearest Thursday to create a long weekend, and routinely ADDS "
        "bridging days around Eid. Neither is a derivable rule: both are gazette decisions, "
        "usually published a few weeks ahead, and this table records what was decided rather "
        "than what a calendar library would compute."),
    "authority": "The Egyptian Cabinet's decisions published in the Official Gazette (al-Jarida "
                 "al-Rasmiyya), which fix both the Islamic dates and any bridging; the CBE "
                 "publishes the banking holiday schedule and the EGX publishes its own trading "
                 "calendar, and all three are read rather than derived. The moon-sighting "
                 "committee of Dar al-Ifta supplies the Hijri determination the Cabinet acts on.",
    "table": _EG_HOLIDAYS,
    "status": {
        2024: "MIXED. The Gregorian national days and Sham El-Nessim are GAZETTED and settled; "
              "every Islamic date carries DECLARED_LUNAR_ESTIMATE and is labelled MOON-DEPENDENT "
              "ESTIMATE in its own name string. Bridging days actually granted by the Cabinet "
              "are NOT in this table and can only be added when the gazette is read.",
        2025: "MIXED, same split as 2024. Gregorian and Coptic settled; Islamic dates are "
              "DECLARED_LUNAR_ESTIMATE.",
        2026: "MIXED AND FORWARD-LOOKING. The Gregorian national days are statutory and stable. "
              "Sham El-Nessim 2026-04-13 is DERIVED from the Orthodox Easter computus. EVERY "
              "ISLAMIC DATE IS DECLARED_LUNAR_ESTIMATE and none has been gazetted yet -- the "
              "Cabinet's decision typically arrives weeks to days before the event and has "
              "historically shifted the arithmetic estimate by a day in either direction. ANY "
              "2026 STUDY WHOSE WINDOW TOUCHES AN EID IS DEFERRED UNTIL THE GAZETTE IS READ.",
    },
    "eid": {
        "status": "DECLARED_LUNAR_ESTIMATE",
        "authority": "the Egyptian Cabinet's gazette decision on the report of the moon-sighting "
                     "committee; nothing else is authoritative and no arithmetic calendar is",
        "estimates": {year: {"eid_al_fitr": rows["eid_al_fitr"],
                             "eid_al_adha": rows["eid_al_adha"]}
                      for year, rows in _EG_LUNAR_ANCHORS.items()},
        "refusal": "THE DESK REFUSES TO TRADE A GUESSED EID WINDOW. Being one day out on a "
                   "three- or four-day national closure is not a rounding error: it silently "
                   "swaps a full trading session for a closed one at BOTH ends of the window, "
                   "which for an event study means the pre-window and post-window baselines are "
                   "each contaminated by the other side of the event. Any cell whose window "
                   "overlaps an estimate above is DEFERRED, not approximated.",
        "why_it_is_also_an_economic_event": "the Eid weeks are the single largest seasonal swing "
                                            "in Egyptian import demand (food, livestock for the "
                                            "Adha sacrifice, clothing, gold for weddings and "
                                            "gifts) and in remittance inflow from the diaspora. "
                                            "So the same dates are a DATA OUTAGE and a REAL "
                                            "ECONOMIC SEASONAL simultaneously, and the two "
                                            "must not be conflated: the outage is why the "
                                            "observation is missing, the seasonal is why it "
                                            "would have been interesting.",
    },
    "lunar_anchors": _EG_LUNAR_ANCHORS,
    "market_effect": (
        "AN EGYPTIAN CLOSURE IS A DATA OUTAGE, NOT A LIQUIDITY REGIME IN A TRADABLE PRICE -- and "
        "the distinction is the whole difference between this pack and the ZA one. South "
        "Africa's holidays are tradable because USDZAR keeps pricing offshore while the domestic "
        "bid is gone; NOTHING EGYPTIAN IS QUOTED HERE, so an Egyptian closure removes no bid "
        "from any instrument the desk can trade. What it removes is INFORMATION: no CBE official "
        "rate is published, no EGX foreign/Arab/Egyptian net-flow print exists, Suez "
        "administrative reporting thins, GASC does not tender, and the parallel-rate commentary "
        "channels go quiet or turn to stale quotes. Any Egyptian observable used as a conditioner "
        "is therefore MISSING on these dates, and a pipeline that forward-fills the last value "
        "across a four-day Eid is asserting a measurement nobody made -- UNMEASURED is the "
        "verdict and it must be carried as one.\n"
        "AND YET THE ECONOMY DOES NOT STOP. The Eid weeks are the largest seasonal swing in "
        "Egyptian import demand and remittance inflow of the year: food and livestock for the "
        "Adha sacrifice, gold for weddings and gifts, and a diaspora sending money home. So the "
        "REAL flow peaks exactly while the DATA stops, which is the least convenient possible "
        "arrangement and the reason the Eid seasonality domain exists as its own object rather "
        "than as a footnote to the calendar."),
    "callable": "countries.eg.pack:holidays",
}


def holidays(year: int) -> dict[str, str]:
    """The Egyptian closure table for one year, `{"YYYY-MM-DD": name}`. `{}` if untabulated.

    The Islamic entries carry MOON-DEPENDENT ESTIMATE inside the NAME STRING, deliberately: a
    caller that reads only the table and never opens `HOLIDAYS_RULE` must still see the
    uncertainty. Putting it only in a status key would hide it from exactly the code most likely
    to misuse it.
    """
    return holiday_table(HOLIDAYS_RULE, year)


# --------------------------------------------------------------------------- custom miners
#: THE EGYPTIAN WEEKEND, as weekday indices (Monday=0). Friday and Saturday. Every business-day
#: computation in this pack goes through this constant rather than through a Monday-Friday
#: assumption inherited from a Western calendar.
EG_WEEKEND: frozenset[int] = frozenset({4, 5})

#: ROUTE GEOMETRY, IN NAUTICAL MILES, SUEZ VERSUS THE CAPE OF GOOD HOPE. These are the only
#: numbers in the detour arithmetic that are FIXED AND KNOWABLE -- the earth does not revise
#: them -- which is precisely why they are separated from the price terms below, all of which are
#: declared UNMEASURED. Approximate great-circle-plus-routing distances for the three legs that
#: matter to this pack; a per-voyage number depends on load ports and is not asserted here.
_SUEZ_ROUTES: dict[str, dict[str, Any]] = {
    "gulf_europe": {
        "label": "Arabian Gulf (Ras Tanura) to North-West Europe (Rotterdam)",
        "via_suez_nm": 6400.0,
        "via_cape_nm": 11100.0,
        "cargo": "crude and refined product -- the leg that prices into XBRUSD against XTIUSD",
    },
    "asia_europe": {
        "label": "East Asia (Singapore) to North-West Europe (Rotterdam)",
        "via_suez_nm": 8300.0,
        "via_cape_nm": 11800.0,
        "cargo": "containerised manufactures -- the leg that prices into European landed cost "
                 "and therefore into GER40 and EUSTX50 industrial margin",
    },
    "gulf_usgulf": {
        "label": "Arabian Gulf to the US Gulf",
        "via_suez_nm": 11500.0,
        "via_cape_nm": 12400.0,
        "cargo": "crude -- included as the CONTROL LEG: the Suez advantage here is small, so a "
                 "diversion should barely move this route's economics. If a measured freight "
                 "response shows up on this leg as strongly as on gulf_europe, the mechanism "
                 "being measured is not the canal.",
    },
}


def eg_suez_detour(route: str = "gulf_europe", speed_knots: float = 14.0) -> dict[str, Any]:
    """The Cape-of-Good-Hope detour arithmetic for one route: geometry measured, prices declared.

    THIS IS THE MOST MECHANICALLY CLEAN OBJECT IN THE PACK and it is worth saying why. A
    shipowner facing the Red Sea chooses between two routes, and the choice is an ARBITRAGE with
    a small number of terms: the Suez toll plus the war-risk insurance premium plus the crew and
    charterer risk, against the extra bunker fuel, the extra charter days and the extra capital
    tied up in cargo afloat. Nothing about it is a mood. It is a cost comparison a broker writes
    down, and when the insurance term moves by an order of magnitude -- as it did after December
    2023 -- the comparison flips for a whole class of vessels at once.

    WHAT THIS FUNCTION COMPUTES AND WHAT IT REFUSES TO. The GEOMETRY is fixed and knowable: the
    distances, the extra days at a given speed, and the TONNE-MILE MULTIPLIER, which is the
    quantity that matters to the freight market because global tanker and container demand is
    measured in tonne-miles, not in cargoes. A diversion does not reduce the number of cargoes;
    it INCREASES the tonne-miles required to move them, which absorbs fleet capacity exactly as a
    demand increase would. That is the transmission channel, and it is arithmetic.

    THE PRICE TERMS ARE UNMEASURED, BY NAME. The Suez toll is an administered SDR-denominated
    price set in navigation circulars with unpublished per-vessel rebates; the war-risk premium
    is quoted per voyage by underwriters and is not a public series; bunker prices vary by port
    and grade. Inventing any of them would produce a confident wrong break-even, which is worse
    than no break-even at all -- so this function returns them as named absences and the caller
    must supply them from a source before the arbitrage can be closed.
    """
    key = str(route).strip().lower()
    row = _SUEZ_ROUTES.get(key)
    if row is None:
        return {"route": key, "status": "UNKNOWN_ROUTE",
                "known_routes": tuple(sorted(_SUEZ_ROUTES)),
                "note": "an unknown route returns a named absence rather than a default leg; a "
                        "silently substituted route would make every number below fiction"}
    speed = max(1.0, float(speed_knots))
    suez_nm = float(row["via_suez_nm"])
    cape_nm = float(row["via_cape_nm"])
    extra_nm = cape_nm - suez_nm
    extra_days_one_way = extra_nm / (speed * 24.0)
    return {
        "route": key,
        "label": row["label"],
        "cargo": row["cargo"],
        "speed_knots": speed,
        "via_suez_nm": suez_nm,
        "via_cape_nm": cape_nm,
        "extra_nm_one_way": round(extra_nm, 1),
        "extra_days_one_way": round(extra_days_one_way, 2),
        "extra_days_round_trip": round(2.0 * extra_days_one_way, 2),
        "tonne_mile_multiplier": round(cape_nm / suez_nm, 4),
        "capacity_absorbed_pct": round(100.0 * (cape_nm / suez_nm - 1.0), 2),
        "mechanism": (
            "the diversion does not remove cargoes, it lengthens voyages; global tanker and "
            "container demand is denominated in TONNE-MILES, so the multiplier above is the "
            "share by which effective fleet capacity is absorbed on this leg. A tightening of "
            "effective capacity raises freight, and freight is a cost inside both the seaborne "
            "crude differential and the European landed price of manufactures."),
        "unmeasured": (
            "SUEZ_TOLL_USD_PER_TRANSIT -- administered, SDR-denominated, set by SCA navigation "
            "circular with unpublished per-vessel rebates; not reconstructible per voyage",
            "WAR_RISK_PREMIUM_PCT_OF_HULL -- quoted per voyage by underwriters, not a public "
            "series; it is the term that ACTUALLY FLIPPED after December 2023 and it is the one "
            "the desk cannot see",
            "BUNKER_PRICE_USD_PER_TONNE -- varies by port and grade; the desk has no bunker leg",
            "CHARTER_RATE_USD_PER_DAY -- the opportunity cost of the extra days above",
        ),
        "status": "GEOMETRY_MEASURED_PRICES_UNMEASURED",
        "refusal": "this function will not return a break-even toll or a diversion threshold. "
                   "Three of the four terms are absent; a break-even computed from one of them "
                   "is a number with a confident shape and no content.",
    }


def eg_eid_windows(year: int) -> dict[str, Any]:
    """The Eid and Ramadan liquidity calendar for one year, with the lunar uncertainty attached.

    WHY THIS IS A MINER AND NOT A LOOKUP. Three things have to travel together or the calendar is
    dangerous: the estimated dates, the fact that they are ESTIMATES, and the EGYPTIAN WEEKEND,
    because the cost of a closure depends entirely on which weekday it lands on and Egypt's
    weekend is Friday-Saturday. A four-day Eid al-Adha that begins on a Wednesday costs two
    business days; the same Eid beginning on a Sunday costs four. A pipeline that counts closures
    rather than lost sessions will get that backwards.

    The function reports, per anchor, the weekday, whether it falls on the Egyptian weekend, and
    the resulting count of LOST BUSINESS DAYS -- and it carries the DECLARED_LUNAR_ESTIMATE
    status and the refusal into its own return value so that a caller cannot receive the dates
    without receiving the caveat.
    """
    anchors = _EG_LUNAR_ANCHORS.get(int(year))
    if anchors is None:
        return {"year": int(year), "status": "UNMEASURED",
                "note": "no lunar anchors tabulated for this year. UNMEASURED is the verdict "
                        "(L1.28a): an untabulated year is not a year with no Eid in it, and "
                        "this function will not extrapolate the Hijri calendar to invent one.",
                "tabulated_years": tuple(sorted(_EG_LUNAR_ANCHORS))}
    windows: list[dict[str, Any]] = []
    for name in ("eid_al_fitr", "eid_al_adha", "islamic_new_year", "prophets_birthday"):
        days: list[dict[str, Any]] = []
        for iso in anchors[name]:
            day = date.fromisoformat(str(iso))
            weekend = day.weekday() in EG_WEEKEND
            days.append({"date": iso, "weekday": day.strftime("%A"),
                         "egyptian_weekend": weekend,
                         "business_day_lost": not weekend})
        windows.append({
            "anchor": name,
            "label": {"eid_al_fitr": "Eid al-Fitr", "eid_al_adha": "Eid al-Adha",
                      "islamic_new_year": "Islamic New Year (1 Muharram)",
                      "prophets_birthday": "Prophet's Birthday (al-Mawlid al-Nabawi)"}[name],
            "days": tuple(days),
            "declared_days": len(days),
            "business_days_lost": sum(1 for d in days if d["business_day_lost"]),
        })
    return {
        "year": int(year),
        "status": str(anchors["status"]),
        "ramadan_start_estimate": anchors["ramadan_start"],
        "ramadan_session_effect": "the EGX shortens its session for Ramadan (typically to about "
                                  "10:00-13:30 Cairo from 10:00-14:30) and banking hours shorten "
                                  "with it. The window is LUNAR and moves about eleven days "
                                  "earlier each Gregorian year, so no month-of-year control "
                                  "holds it fixed.",
        "windows": tuple(windows),
        "egyptian_weekend": "Friday and Saturday. A closure landing there costs no business day; "
                            "one landing on Sunday costs a full session.",
        "economic_seasonal": "the Eid weeks are the largest annual swing in Egyptian import "
                             "demand (food, livestock for the Adha sacrifice, gold for weddings "
                             "and gifts) and in diaspora remittance inflow. The DATA stops "
                             "exactly while the FLOW peaks.",
        "authority": "the Egyptian Cabinet's gazette decision on the moon-sighting committee's "
                     "report; the dates above are arithmetic estimates and nothing more",
        "refusal": "THE DESK REFUSES TO TRADE A GUESSED EID WINDOW. Any cell whose window "
                   "overlaps a date above is DEFERRED until the gazette is read, because being "
                   "one day out swaps a trading session for a closed one at both ends of the "
                   "event and contaminates the pre- and post-windows with each other.",
    }


CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    miner("eg_suez_detour_arithmetic",
          domain_ids=("eg_suez_traffic", "eg_red_sea_diversion"),
          kind="mechanism",
          entry="countries.eg.pack:eg_suez_detour",
          cadence_s=3600.0,
          steerable=True,
          notes="Turns a route decision into a TONNE-MILE MULTIPLIER, which is the only form in "
                "which it can be joined to a freight or crude-differential series. It returns "
                "the geometry and names the four price terms it does not have, so a caller "
                "cannot accidentally receive a break-even that was invented."),
    miner("eg_eid_liquidity_calendar",
          domain_ids=("eg_eid_seasonality", "eg_remittance_channel_switch"),
          kind="calendar",
          entry="countries.eg.pack:eg_eid_windows",
          cadence_s=86400.0,
          steerable=False,
          notes="A FIXED COST, not a steerable one: the Eid grid must be read every pass whatever "
                "it yielded last month, because a miner conditioning on the wrong window "
                "produces a confident wrong number rather than nothing. It carries the "
                "DECLARED_LUNAR_ESTIMATE status and the deferral refusal in its return value so "
                "the caveat cannot be separated from the dates."),
)


# --------------------------------------------------------------------------- positioning
#: THE FIRST THING THIS TABLE DOES IS DECLARE AN ABSENCE. There is NO CFTC-reportable futures
#: contract on the Egyptian pound -- South Africa is the only country in this civilization whose
#: currency has one -- and there is no onshore Egyptian futures market with a published
#: open-interest series either. So Egypt has NEITHER an offshore speculative-positioning series
#: NOR a domestic mirror, and the ZA pack's onshore-versus-offshore divergence has no Egyptian
#: counterpart at all. UNMEASURED is the verdict for speculative positioning in this country, by
#: name (L1.28a). What follows is not a substitute for it; it is a different set of observables
#: that happen to carry information about who is exposed to Egypt and how badly.
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"id": "eg_no_cot_contract",
     "name": "CFTC Commitments of Traders -- THERE IS NO EGYPTIAN POUND CONTRACT",
     "covers": "nothing. Declared so no session goes looking for it and so no pipeline "
               "silently maps EGP onto a neighbouring currency's positioning series.",
     "frequency": "n/a", "lag": "n/a",
     "root": "cftc.gov Commitments of Traders (checked: no EGP contract)",
     "licence": "n/a",
     "availability": "NO. The pound is not deliverable offshore, has no CME contract, and no "
                     "exchange anywhere lists a liquid EGP future.",
     "desk_status": "UNMEASURED BY NAME. The positioning miner reports UNMEASURED for EGP "
                    "permanently, not pending a mapping -- this is a property of the market, "
                    "not a gap in desks/mt5/data/axes/cot.json."},
    {"id": "egx_investor_origin_flows",
     "name": "EGX daily net-flow breakdown -- Egyptians, Arabs and Foreigners",
     "covers": "daily buy, sell and net value by investor ORIGIN, split further into "
               "institutions and individuals",
     "frequency": "daily, Sunday to Thursday",
     "lag": "same day after the 14:30 Cairo close",
     "root": "egx.com.eg daily trading reports and market statistics",
     "licence": "free, public",
     "note": "THE BEST FREE POSITIONING-ADJACENT SERIES EGYPT HAS, and its distinctive feature "
             "is the ARAB row. Gulf money behaves like strategic and sovereign capital -- it "
             "arrives on deals and stays -- while non-Arab foreign money behaves like portfolio "
             "capital and leaves on the EM factor. A pipeline that sums them into 'foreign' is "
             "averaging two actors with opposite persistence. It also prints on SUNDAY, before "
             "any other market in this desk's universe opens."},
    {"id": "foreign_holdings_of_egyptian_tbills",
     "name": "Foreign holdings of Egyptian treasury bills -- the carry, or 'hot money', stock",
     "covers": "the outstanding stock of Egyptian local-currency bills held by non-residents",
     "frequency": "monthly, with the CBE's monetary and banking statistics",
     "lag": "roughly four to eight weeks",
     "root": "cbe.org.eg monthly statistical bulletin and external position tables",
     "licence": "free, public",
     "note": "A STOCK, NOT A FLOW, AND THAT IS WHY IT MATTERS: it measures how much money is "
             "queued to leave. The 2022 episode is the canonical case -- a large non-resident "
             "bill position met a suspended repatriation mechanism, and the exit became a QUEUE "
             "rather than a trade. The stock is the size of the potential forced flow; the "
             "spread and the reserves say whether it can be honoured."},
    {"id": "cbe_net_foreign_assets",
     "name": "CBE net foreign assets of the banking system (NFA)",
     "covers": "foreign assets minus foreign liabilities of the CBE and the commercial banks",
     "frequency": "monthly", "lag": "roughly four to six weeks",
     "root": "cbe.org.eg monetary and banking developments",
     "licence": "free, public",
     "note": "GENUINELY DIAGNOSTIC, AND THE SERIES THAT WOULD HAVE CALLED THE LAST TWO "
             "DEVALUATIONS. It went DEEPLY NEGATIVE before the 2022-2024 sequence as banks "
             "borrowed abroad and sold forward to hold the official rate: the defence was being "
             "financed by the banking system's own balance sheet, which headline net "
             "international reserves do not show because reserves can be propped by Gulf "
             "deposits and swaps that are LIABILITIES. NFA nets them. If this pack has one "
             "series a session should look at before forming any view on Egypt, it is this one."},
    {"id": "eg_eurobond_spread",
     "name": "Egyptian USD and EUR eurobond spreads (EMBI-style, as reported in commentary)",
     "covers": "the market's price of Egyptian sovereign credit risk",
     "frequency": "continuous in the market; observed here only where publicly reported",
     "lag": "same day to days, depending on the reporting source",
     "root": "IMF and World Bank programme documents, multilateral market monitors, and public "
             "financial-press reporting",
     "licence": "free where published; NEVER redistributed from a licensed vendor feed",
     "note": "NOT TRADABLE ON THIS ACCOUNT -- the broker quotes UST10Y, UST05Y and UKGILT and no "
             "frontier credit -- so this is an OBSERVABLE that conditions the duration leg, "
             "never a target. Its coverage is irregular and it is marked NOT_PIT_SAFE."},
    {"id": "eg_ndf_commentary",
     "name": "Non-deliverable forward pricing on the pound, as reported in commentary",
     "covers": "where a handful of banks would price forward EGP when they price it at all",
     "frequency": "irregular, episodic -- it is quoted when the market is stressed and not "
                  "otherwise, which is a SELECTION problem, not merely a coverage one",
     "lag": "days", "root": "public financial-press reporting and programme documents",
     "licence": "free where published",
     "note": "THE MOST TEMPTING AND MOST DANGEROUS ITEM IN THIS TABLE. An NDF quote looks like a "
             "market expectation of devaluation and would be the perfect observable if it "
             "existed continuously. It does not: it is quoted precisely in the episodes where a "
             "devaluation is already being discussed, so a study using it will find that NDFs "
             "predict devaluations and will have discovered its own sampling. Carried with "
             "pit_feasible False and a standing warning."},
)


# --------------------------------------------------------------------------- terminology
#: NATIVE TERMS, KEYED BY DOMAIN, IN ARABIC SCRIPT -- not transliteration.
#:
#: THE REASON IS SPECIFIC TO EGYPT AND IT IS THE MOST IMPORTANT DESIGN DECISION IN THIS FILE.
#: EGYPTIAN FINANCIAL VERNACULAR IS WHERE THE PARALLEL RATE IS ACTUALLY QUOTED. The official rate
#: appears in English on the CBE's page; the price a household or an importer can really get
#: appears as a number next to the words "سعر الدولار اليوم" on an Arabic price page, in an
#: Arabic-language channel, or in a gold shop's quote for "عيار 21". THE ENGLISH-LANGUAGE PRESS
#: REPORTS A DEVALUATION AFTER IT HAS HAPPENED; the Arabic price pages report the spread that
#: predicts it, daily, for months beforehand. A miner that searches only English therefore
#: arrives with the news instead of ahead of it -- which for the single most valuable observable
#: in this pack is the difference between a forecast and a post-mortem.
#:
#: The register matters too, not just the language. "خفض قيمة العملة" is what a ministry says;
#: "انهيار الجنيه" is what a trader says; "أزمة الدولار" is what the street says, and the street
#: said it in 2021 and 2022 before either of the others did. All three registers are carried.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "core": ("الجنيه", "الجنيه المصري", "الدولار", "سعر الصرف", "سعر الدولار",
             "سعر الدولار اليوم", "العملة", "العملات الأجنبية", "النقد الأجنبي",
             "the Egyptian pound", "exchange rate", "EGP"),
    "eg_parallel_premium": ("السوق السوداء", "السوق الموازية", "سعر السوق السوداء", "الصرافة",
                            "شركات الصرافة", "أزمة الدولار", "الفجوة", "تجار العملة",
                            "الدولار في السوق السوداء", "parallel market", "black market rate",
                            "premium", "spread"),
    "eg_fx_regime_state": ("التعويم", "تعويم الجنيه", "سعر الصرف المرن", "المرونة",
                           "التثبيت", "الربط بالدولار", "float", "managed peg", "flexible "
                           "exchange rate"),
    "eg_devaluation_timing": ("خفض قيمة العملة", "تخفيض الجنيه", "انهيار الجنيه",
                              "تراجع الجنيه", "قفزة الدولار", "devaluation", "step move",
                              "one-step adjustment"),
    "eg_policy_reaction": ("البنك المركزي المصري", "لجنة السياسة النقدية", "سعر الفائدة",
                           "رفع الفائدة", "خفض الفائدة", "الكوريدور", "السياسة النقدية",
                           "التضخم", "التضخم الأساسي", "MPC", "policy corridor", "hike", "cut"),
    "eg_reserves_and_nfa": ("الاحتياطي النقدي الأجنبي", "صافي الأصول الأجنبية",
                            "الالتزامات الأجنبية", "ودائع الخليج", "شهادات الادخار",
                            "الشهادات ذات العائد المرتفع", "net foreign assets",
                            "net international reserves", "certificates of deposit"),
    "eg_suez_traffic": ("قناة السويس", "هيئة قناة السويس", "الملاحة", "حمولة السفن",
                        "عدد السفن العابرة", "إيرادات القناة", "رسوم العبور", "خط سوميد",
                        "Suez Canal Authority", "transit", "net tonnage", "SUMED"),
    "eg_red_sea_diversion": ("البحر الأحمر", "باب المندب", "رأس الرجاء الصالح", "تحويل المسار",
                             "التأمين على السفن", "أسعار الشحن", "الحوثي", "سفن الحاويات",
                             "Cape of Good Hope", "war risk", "diversion", "freight rate"),
    "eg_wheat_import_dependence": ("القمح", "الرغيف", "الخبز المدعم", "الدعم",
                                   "الهيئة العامة للسلع التموينية", "مناقصة القمح",
                                   "وزارة التموين", "الذرة", "استيراد القمح",
                                   "GASC", "wheat tender", "bread subsidy"),
    "eg_gold_household_hedge": ("الذهب", "جنيه الذهب", "عيار 21", "عيار 24",
                                "سعر الذهب اليوم", "المصنعية", "السبائك", "محلات الصاغة",
                                "gold pound", "21 carat", "making charge", "local premium"),
    "eg_remittance_channel_switch": ("تحويلات المصريين بالخارج", "التحويلات",
                                     "المصريون في الخارج", "السوق الرسمية", "الحوالة",
                                     "التحويل البنكي", "remittances", "official channel",
                                     "informal channel"),
    "eg_external_programme_calendar": ("صندوق النقد الدولي", "برنامج الصندوق", "المراجعة",
                                       "القرض", "شريحة", "السندات الدولية", "أذون الخزانة",
                                       "الديون الخارجية", "IMF review", "tranche", "eurobond",
                                       "Article IV"),
    "eg_gulf_and_investment": ("رأس الحكمة", "صفقة رأس الحكمة", "الاستثمارات الخليجية",
                               "صندوق مصر السيادي", "الإمارات", "السعودية",
                               "Ras El Hekma", "ADQ", "sovereign wealth"),
    "eg_import_restrictions": ("الاعتمادات المستندية", "مستندات التحصيل", "البضائع بالموانئ",
                               "الإفراج الجمركي", "تكدس البضائع", "قوائم الاستيراد",
                               "letters of credit", "import backlog", "customs release"),
    "eg_exchange_and_flows": ("البورصة", "البورصة المصرية", "المؤشر", "صافي تعاملات الأجانب",
                              "المستثمرون الأجانب", "الأموال الساخنة", "المستثمرون العرب",
                              "EGX30", "foreign net", "Arab net", "hot money"),
    "eg_energy": ("الغاز الطبيعي", "الغاز المسال", "حقل ظهر", "استيراد الغاز",
                  "تصدير الغاز", "انقطاع الكهرباء", "أحمال الكهرباء",
                  "LNG", "Zohr", "load shedding", "regasification"),
    "eg_tourism": ("السياحة", "الإيرادات السياحية", "الحركة السياحية", "الفنادق",
                   "tourism receipts", "arrivals"),
    "eg_eid_seasonality": ("رمضان", "عيد الفطر", "عيد الأضحى", "الأضاحي", "موسم الأعياد",
                           "إجازة العيد", "Ramadan", "Eid al-Fitr", "Eid al-Adha"),
    "eg_risk_proxy_crypto_premium": ("العملات الرقمية", "تيثر", "التداول الند للند",
                                     "الدولار الرقمي", "stablecoin", "P2P", "premium"),
}


# --------------------------------------------------------------------------- source classes
#: THE TEN LAYERS (principal's per-country depth rule, 2026-09-17). A country is NEVER "covered"
#: by five obvious sources: the official portal, a statistics agency, a newspaper and two think
#: tanks is the shape of a country note, not of a department. Ten layers, each either populated
#: or DECLARED ABSENT WITH A REASON, is what stops a pack from stopping at the sources that were
#: easy to name.
LAYERS: tuple[str, ...] = ("official", "institutional", "academic", "practitioner",
                           "retail_ecology", "app_ecosystem", "media", "archive",
                           "physical_economy", "source_graph")

#: HOW THE DESK MAY USE A SOURCE, which is a different question from whether it is true.
#: `PUBLIC_WITH_TERMS` and `machine_use_allowed=True` are the pair that keeps a terms-restricted
#: page REGISTERED AND UNSCRAPED -- omitting it would hide a known source, scraping it would
#: breach its terms, and the desk does neither.
ACCESS_LABELS: tuple[str, ...] = ("PUBLIC", "PUBLIC_WITH_TERMS", "LICENSED", "OPEN_DATA",
                                  "PUBLIC_ARCHIVE", "PUBLIC_SOCIAL", "USER_SUBMITTED",
                                  "ACCESS_UNCLEAR", "PRIVATE", "CONFIDENTIAL_MNPI",
                                  "STOLEN_UNAUTHORIZED")

#: HOW MUCH THE DESK BELIEVES IT. `FRINGE` and `CONTRADICTED` are KEPT, never dropped: a
#: devaluation rumour that turned out wrong is still evidence about EXPECTATIONS, and in a
#: country whose defining event is a step move the market did not know the date of, the
#: distribution of wrong guesses is data about the distribution of beliefs.
CREDIBILITY: tuple[str, ...] = ("AUTHORITATIVE", "RELIABLE", "UNRELIABLE", "FRINGE",
                                "CONTRADICTED", "UNKNOWN")

#: WHETHER IT HAS EVER ACTUALLY PREDICTED ANYTHING HERE. Every row starts UNTESTED, which is the
#: honest state, and only a gauntlet moves it. `NARRATIVE_FEATURE` is the label for material kept
#: because it describes what people BELIEVED, not because it forecasts a price.
PREDICTIVE_STATES: tuple[str, ...] = ("UNTESTED", "PREDICTIVE", "NOT_PREDICTIVE",
                                      "NARRATIVE_FEATURE")


def _src(sid: str, label: str, *, layer: str, roots: tuple[str, ...],
         languages: tuple[str, ...], licence: str, access_label: str, credibility: str,
         predictive_state: str, queries: tuple[str, ...], machine_use_allowed: bool = True,
         notes: str = "") -> dict[str, Any]:
    """`source_class()` plus the principal's five labels, with the enums enforced at import.

    IT RAISES ON A TYPO'D ENUM ON PURPOSE. A mislabelled source is worse than an unlabelled one:
    an unlabelled source is visibly incomplete and gets triaged, while a source labelled
    `AUTHORITATIVE` by a misspelling of `UNRELIABLE` is silently promoted into the evidence
    weighting and never looked at again. Failing at import is the cheapest possible moment.
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
    if len(queries) < 4:
        raise ValueError(f"source {sid}: {len(queries)} queries, at least 4 required -- a source "
                         f"with no native-language query attached is a bookmark, not a lane")
    row = source_class(sid, label, roots=roots, languages=languages, licence=licence, notes=notes)
    row.update({"layer": layer, "access_label": access_label, "credibility": credibility,
                "predictive_state": predictive_state,
                "machine_use_allowed": bool(machine_use_allowed), "queries": tuple(queries)})
    return row


SOURCE_CLASSES: tuple[dict[str, Any], ...] = (
    # ---- official ------------------------------------------------------------------------
    _src("eg_official_cb", "Central Bank of Egypt -- rates, monetary statistics, MPC statements",
         layer="official",
         roots=("cbe.org.eg", "cbe.org.eg/en/economic-research/statistics",
                "cbe.org.eg/ar/economic-research/publications",
                "cbe.org.eg/en/news-publications/press-releases (MPC statements)"),
         languages=("ar", "en"),
         licence="free, public; PAGES AND PDFs, not a documented API",
         access_label="PUBLIC", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         queries=("سعر الصرف البنك المركزي", "صافي الأصول الأجنبية البنك المركزي",
                  "قرار لجنة السياسة النقدية", "الاحتياطي النقدي الأجنبي مصر",
                  "بيان المركزي المصري سعر الفائدة"),
         notes="THE OFFICIAL RATE AND THE NFA SERIES LIVE HERE, and the contrast with the SARB "
               "is instructive: South Africa serves a swagger-described REST API and Egypt "
               "serves PDFs off pages that move. So the EG lane is a page-shape lane with "
               "vintage storage, and a moved page is a NAMED failure rather than an empty "
               "series. The NFA table is the highest-value object on this root."),
    _src("eg_official_stats", "CAPMAS -- the Central Agency for Public Mobilization and "
                              "Statistics",
         layer="official",
         roots=("capmas.gov.eg", "capmas.gov.eg/Pages/IndicatorsPage.aspx (CPI)",
                "capmas.gov.eg/Pages/StaticPages.aspx (foreign trade bulletins)"),
         languages=("ar", "en"),
         licence="free, public; releases are PDF and XLSX, mostly Arabic-first",
         access_label="PUBLIC", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         queries=("التضخم في مصر الجهاز المركزي للتعبئة العامة والإحصاء",
                  "الرقم القياسي لأسعار المستهلكين", "الميزان التجاري مصر",
                  "واردات القمح مصر إحصاء", "معدل التضخم السنوي مصر"),
         notes="CPI prints monthly around the 10th and the trade balance quarterly with a long "
               "lag. ARABIC-FIRST IS THE OPERATIVE DETAIL: the Arabic bulletin is frequently "
               "published before the English one, so an English-only crawler is systematically "
               "late on the single most policy-relevant Egyptian statistic."),
    _src("eg_official_suez", "Suez Canal Authority -- transit statistics and navigation circulars",
         layer="official",
         roots=("suezcanal.gov.eg", "suezcanal.gov.eg/English/Navigation/Pages/"
                "NavigationStatistics.aspx", "suezcanal.gov.eg/English/Rules/Pages/"
                "CircularsAndNotices.aspx"),
         languages=("ar", "en"),
         licence="free, public; monthly tables plus circulars, publication cadence irregular",
         access_label="PUBLIC", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         queries=("حركة الملاحة في قناة السويس", "عدد السفن العابرة قناة السويس",
                  "إيرادات قناة السويس", "الحمولة الصافية قناة السويس",
                  "منشور ملاحي هيئة قناة السويس", "رسوم عبور قناة السويس"),
         notes="THE CHOKEPOINT'S OWN METER. Vessel COUNT and NET TONNAGE are the observables -- "
               "revenue mixes them with the toll and with the SDR rate and is therefore the "
               "worst of the three for research despite being the headline. THE RED SEA "
               "DIVERSION FROM DECEMBER 2023 IS VISIBLE IN THIS SERIES, which is the single "
               "cleanest natural experiment this pack has. Publication is irregular and "
               "occasionally restated; that is declared at the dataset level, not smoothed."),
    _src("eg_official_fiscal_supply", "Ministry of Finance, Ministry of Supply and GASC tenders",
         layer="official",
         roots=("mof.gov.eg", "mof.gov.eg/ar/publications (budget and monthly fiscal bulletins)",
                "msit.gov.eg (Ministry of Supply and Internal Trade)",
                "GASC -- the General Authority for Supply Commodities tender announcements"),
         languages=("ar", "en"),
         licence="free, public; tenders are announced and their results reported publicly",
         access_label="PUBLIC", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         queries=("مناقصة القمح الهيئة العامة للسلع التموينية", "نتيجة مناقصة القمح",
                  "وزارة التموين استيراد القمح", "الموازنة العامة للدولة دعم الخبز",
                  "احتياطي القمح الاستراتيجي مصر"),
         notes="THE STATE WHEAT BUYER'S TENDERS ARE PUBLIC AND MARKET-MOVING, and the ABSENCE of "
               "a tender when one was expected is as informative as a large one -- it usually "
               "means the foreign exchange was not available. A tender-size series that treats "
               "a skipped month as missing rather than as a zero is discarding the observation "
               "that carries the FX information."),
    _src("eg_official_exchange", "The Egyptian Exchange -- daily reports and investor-origin flows",
         layer="official",
         roots=("egx.com.eg", "egx.com.eg/ar/DailyTradingReports.aspx",
                "egx.com.eg/en/MarketWatch.aspx", "mcdr.com.eg (clearing and settlement)"),
         languages=("ar", "en"),
         licence="free, public summary tables; any real-time feed is LICENSED and never scraped",
         access_label="PUBLIC", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         queries=("صافي تعاملات الأجانب البورصة المصرية", "تعاملات العرب البورصة",
                  "التقرير اليومي للبورصة المصرية", "مؤشر إيجي إكس 30",
                  "المستثمرون الأجانب شراء البورصة"),
         notes="The daily Egyptians / Arabs / Foreigners net-flow split, free, printed SUNDAY "
               "through THURSDAY. NO EGYPTIAN INDEX IS TRADABLE ON THIS ACCOUNT, so every row "
               "here is an OBSERVABLE and never a target (two-lane order, 2026-09-06)."),

    # ---- institutional -------------------------------------------------------------------
    _src("eg_institutional_imf_wb", "IMF and World Bank Egypt programme documents",
         layer="institutional",
         roots=("imf.org/en/Countries/EGY", "imf.org Article IV consultations and programme "
                "reviews for Egypt", "worldbank.org/en/country/egypt",
                "IMF Extended Fund Facility review staff reports"),
         languages=("en", "ar"),
         licence="free, public; staff reports and review documents are published in full",
         access_label="PUBLIC", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         queries=("صندوق النقد الدولي مراجعة برنامج مصر", "تقرير المادة الرابعة مصر",
                  "شريحة قرض صندوق النقد مصر", "التزامات مصر مع صندوق النقد",
                  "الفجوة التمويلية مصر"),
         notes="THE SINGLE BEST SOURCE ON EGYPT'S TRUE FX POSITION, and it is free. A staff "
               "report states the external financing gap, the arrears, the true reserve "
               "composition and the programme's own conditionality -- quantities the domestic "
               "official sources present more favourably. It also carries SCHEDULED REVIEW "
               "DATES, which is one of very few exogenous date grids available for this country."),
    _src("eg_institutional_multilateral", "Regional and multilateral development institutions",
         layer="institutional",
         roots=("afdb.org (African Development Bank Egypt country data)",
                "amf.org.ae (Arab Monetary Fund statistics)",
                "ebrd.com (EBRD Egypt transition reports)",
                "unctad.org (seaborne trade and maritime transport review)"),
         languages=("en", "ar"),
         licence="free, public",
         access_label="OPEN_DATA", credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("صندوق النقد العربي إحصاءات مصر", "البنك الأفريقي للتنمية مصر",
                  "تقرير النقل البحري الأونكتاد", "التجارة البحرية العالمية إحصاءات",
                  "الديون الخارجية مصر تقرير"),
         notes="UNCTAD's maritime review is the one that matters most here and it is the least "
               "obvious: it carries seaborne trade volumes and tonne-mile context that turn the "
               "Suez transit count into a SHARE OF WORLD TRAFFIC rather than a raw number. A "
               "transit count with no denominator cannot distinguish a diversion from a global "
               "trade slowdown."),

    # ---- academic ------------------------------------------------------------------------
    _src("eg_academic", "Egyptian and Arab-language economic research",
         layer="academic",
         roots=("eces.org.eg (Egyptian Center for Economic Studies)",
                "erf.org.eg (Economic Research Forum, Cairo)",
                "papers.ssrn.com (Egyptian FX, parallel-market and subsidy literature)",
                "aucegypt.edu and cu.edu.eg institutional repositories"),
         languages=("ar", "en"),
         licence="institutional repositories and working papers are open; journals are often "
                 "licensed and a paywall is NEVER scraped",
         access_label="PUBLIC", credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("السوق الموازية للعملة في مصر دراسة", "أثر خفض قيمة الجنيه على التضخم",
                  "تمرير سعر الصرف إلى الأسعار مصر", "اقتصاديات دعم الخبز في مصر",
                  "تحويلات المصريين بالخارج محددات"),
         notes="THE ARABIC-LANGUAGE PARALLEL-MARKET LITERATURE HAS NO ENGLISH EQUIVALENT. Egypt "
               "has been studied by Egyptian economists through four devaluation cycles, and "
               "the exchange-rate pass-through and parallel-premium estimates in that literature "
               "are the closest thing this pack has to a prior. ERF in particular publishes "
               "household-survey work on remittance channel choice that bears directly on the "
               "best actor in this department."),

    # ---- practitioner --------------------------------------------------------------------
    _src("eg_practitioner_finance", "Cairo buy-side and sell-side practitioner publications",
         layer="practitioner",
         roots=("enterprise.press (Enterprise, the Cairo morning business brief)",
                "hapijournal.com", "EFG Hermes and CI Capital public research notes",
                "zawya.com Egypt coverage"),
         languages=("en", "ar"),
         licence="PUBLIC_WITH_TERMS -- some of this is free-to-read but terms-restricted for "
                 "machine extraction; the restricted parts are registered and NOT scraped",
         access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
         predictive_state="UNTESTED", machine_use_allowed=True,
         queries=("توقعات خفض الفائدة مصر بنوك الاستثمار", "تقرير بحثي عن الجنيه المصري",
                  "نظرة المحللين على التعويم", "تقديرات التضخم مصر بنك استثمار",
                  "توصيات أذون الخزانة مصر"),
         notes="REGISTERED, READ BY HUMANS, NEVER MACHINE-EXTRACTED. `machine_use_allowed=True`: "
               "these pages' terms restrict automated extraction, so the crawler is forbidden "
               "them and the row exists so that a future session knows the source EXISTS and why "
               "the desk does not hold its text. Omitting the row would look like the source was "
               "never found; scraping it would breach its terms. The desk does neither."),
    _src("eg_practitioner_shipping", "Shipping brokers, P&I clubs and maritime trade press",
         layer="practitioner",
         roots=("lloydslist.com and tradewinds (headline and free-tier only)",
                "splash247.com", "gcaptain.com",
                "joint war committee and P&I club public circulars on Red Sea listed areas"),
         languages=("en", "ar"),
         licence="mixed; free tiers and public circulars only, paywalled content never scraped",
         access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("تحويل مسار السفن رأس الرجاء الصالح", "أقساط التأمين على السفن البحر الأحمر",
                  "شركات الشحن تتجنب البحر الأحمر", "ارتفاع أسعار الشحن بسبب الحوثيين",
                  "عودة السفن إلى قناة السويس"),
         notes="THE PEOPLE WHO ACTUALLY MAKE THE DIVERSION DECISION. A P&I club circular adding "
               "the southern Red Sea to a listed area is the administrative act that changes the "
               "war-risk premium -- the exact term `eg_suez_detour` declares UNMEASURED. These "
               "circulars are public even where the trade press is not, so the observable is "
               "reachable without touching a paywall."),

    # ---- retail_ecology ------------------------------------------------------------------
    _src("eg_retail_price_channels", "Egyptian public dollar-and-gold price channels and boards",
         layer="retail_ecology",
         roots=("public Arabic-language daily price pages aggregating bureau and street quotes",
                "public Facebook and Telegram-adjacent price channels, described GENERICALLY",
                "Egyptian consumer and investing forums and comment threads"),
         languages=("ar",),
         licence="public web and public social; mined for VERBATIM CLAIMS ONLY -- the quote, the "
                 "number and the timestamp. NEVER personal data, never account identities, "
                 "never private groups, never a member list",
         access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
         predictive_state="NARRATIVE_FEATURE",
         queries=("سعر الدولار اليوم في السوق السوداء", "الدولار اليوم في مصر",
                  "سعر الدولار في شركات الصرافة", "جنيه الذهب عيار 21 سعر اليوم",
                  "الدولار هيوصل كام", "شائعات تعويم جديد"),
         notes="THIS IS WHERE THE PARALLEL RATE IS ACTUALLY QUOTED, and it is UNRELIABLE by "
               "construction: aggregators disagree by more than a normal bid-ask, some are "
               "stale, some are talking their own book. KEPT ANYWAY, AT LOW WEIGHT, because the "
               "alternative is having no observation of the single most valuable quantity in "
               "this pack. Every quote is stored with its source and timestamp and the "
               "DISAGREEMENT ACROSS AGGREGATORS IS ITSELF A FEATURE -- it widens before a step."),
    _src("eg_retail_rumour_and_failure", "Devaluation rumours, scam reports and failure stories",
         layer="retail_ecology",
         roots=("public Arabic-language threads predicting or denying an imminent devaluation",
                "public consumer-protection and fraud complaint threads about currency dealers",
                "public commentary on failed remittance and import-payment attempts"),
         languages=("ar",),
         licence="public social; verbatim claims only, no personal data, no identities",
         access_label="PUBLIC_SOCIAL", credibility="FRINGE",
         predictive_state="NARRATIVE_FEATURE",
         queries=("تعويم جديد للجنيه قريبا", "شائعة خفض الجنيه", "نصب تجار العملة",
                  "مشاكل تحويل الأموال إلى مصر", "البنك رفض فتح اعتماد مستندي"),
         notes="KEPT DELIBERATELY, AT LOW WEIGHT, AND NEVER DROPPED. A devaluation rumour that "
               "turned out WRONG is still evidence about EXPECTATIONS, and in a country whose "
               "defining event is a step move nobody knew the date of, the distribution of wrong "
               "guesses is data about the distribution of beliefs -- which is the quantity the "
               "spread is supposed to proxy. The failure stories are better still: 'the bank "
               "refused to open my letter of credit' is a DIRECT observation of the control "
               "binding, reported by the person it bound, weeks before any statistic shows it. "
               "credibility=FRINGE and predictive_state=NARRATIVE_FEATURE are the honest labels "
               "and they are what keeps this material from being weighted like a statistic."),

    # ---- app_ecosystem -------------------------------------------------------------------
    _src("eg_app_ecosystem", "The apps Egyptians actually price the dollar and gold in",
         layer="app_ecosystem",
         roots=("public app-store listing pages and their public review text for Egyptian "
                "dollar-rate and gold-price aggregator apps",
                "public listing and help pages for Egyptian bank apps and e-wallets, including "
                "the InstaPay instant-payment network and Meeza-linked wallets",
                "public listing and fee pages for remittance apps used on the Egypt corridor",
                "public help-centre pages describing transfer limits and FX conversion terms"),
         languages=("ar", "en"),
         licence="public listing metadata and public review text only. NO app is installed, no "
                 "private API is called, no account is created, and no user data is collected",
         access_label="PUBLIC", credibility="UNRELIABLE", predictive_state="UNTESTED",
         queries=("تطبيق سعر الدولار اليوم", "تطبيق أسعار الذهب في مصر",
                  "انستا باي تحويل من الخارج", "تطبيق تحويل الأموال إلى مصر رسوم",
                  "محفظة إلكترونية سعر الصرف"),
         notes="A LAYER THAT LOOKS TRIVIAL AND IS NOT. Egypt's dollar price is consumed through "
               "APPS, and two things leak out of that ecosystem for free: (1) the FX CONVERSION "
               "RATE AND FEE a remittance app publishes on its own help page, which is the "
               "EFFECTIVE OFFICIAL-CHANNEL RATE a diaspora sender actually faces -- the exact "
               "quantity that determines the channel switch; and (2) PUBLIC REVIEW TEXT, which "
               "fills with complaints in the specific weeks when transfers are delayed or "
               "limits are cut, i.e. exactly when the control is binding. Review sentiment is "
               "UNRELIABLE as a level and potentially informative as a CHANGE, which is why the "
               "credibility and predictive labels differ here."),

    # ---- media ---------------------------------------------------------------------------
    _src("eg_media_business", "Egyptian business and general press, Arabic-first",
         layer="media",
         roots=("almalnews.com (Al Mal)", "amwalalghad.com (Amwal Al Ghad)",
                "masrawy.com/business", "youm7.com/Economy", "ahram.org.eg economy pages",
                "egyptianstreets.com", "dailynewsegypt.com"),
         languages=("ar", "en"),
         licence="public web; mined for VERBATIM CLAIMS and dated statements, never "
                 "redistributed and never scraped past a paywall",
         access_label="PUBLIC", credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("أزمة الدولار في مصر", "قرار المركزي بشأن سعر الصرف",
                  "أسعار الذهب في مصر اليوم", "تكدس البضائع في الموانئ المصرية",
                  "شهادات الادخار 27%", "صفقة رأس الحكمة تفاصيل"),
         notes="THE ARABIC OUTLETS RUN THE STORY FIRST AND IN MORE DETAIL. Al Mal and Amwal Al "
               "Ghad carry the certificate-of-deposit terms, the port-backlog estimates and the "
               "tender chatter days before an English summary exists, and Youm7's economy desk "
               "is where the street register appears in print. An English-only media lane in "
               "this country is a lane that reads its own translations."),

    # ---- archive -------------------------------------------------------------------------
    _src("eg_archive", "Historical bulletins, superseded pages and web captures",
         layer="archive",
         roots=("web.archive.org captures of cbe.org.eg rate and statistics pages",
                "cbe.org.eg monthly statistical bulletin back issues (PDF archive)",
                "capmas.gov.eg historical bulletin archive",
                "suezcanal.gov.eg historical navigation statistics and superseded circulars"),
         languages=("ar", "en"),
         licence="free, public archives and captures",
         access_label="PUBLIC_ARCHIVE", credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("النشرة الإحصائية الشهرية البنك المركزي أرشيف",
                  "إحصاءات قناة السويس السنوات السابقة", "سعر الصرف الرسمي أرشيف",
                  "منشورات ملاحية سابقة قناة السويس", "بيانات التضخم مصر سنوات سابقة"),
         notes="LOAD-BEARING IN EGYPT IN A WAY IT IS NOT IN SOUTH AFRICA. The CBE serves a PAGE "
               "showing the CURRENT rate, not an API serving history; when the page moves or is "
               "restyled the old vintages exist ONLY as captures. So for several Egyptian series "
               "the ARCHIVE IS THE POINT-IN-TIME SOURCE -- the only way to know what was "
               "knowable on a past date is to read what the page said on that date. A pack "
               "without this layer would be forced to use the current vintage and would silently "
               "produce NOT_PIT_SAFE cells that looked clean."),

    # ---- physical_economy ----------------------------------------------------------------
    _src("eg_physical_economy", "Ships, cargoes, terminals and the things that physically move",
         layer="physical_economy",
         roots=("Suez Canal Authority vessel counts and net tonnage (the physical meter)",
                "public port and terminal reporting for Damietta and Idku LNG, Alexandria, "
                "Sokhna and Port Said",
                "publicly reported wheat vessel arrivals and discharge at Egyptian grain ports",
                "public AIS-derived commentary on Bab el-Mandeb and Suez transits"),
         languages=("ar", "en"),
         licence="free where published; no licensed AIS feed is subscribed or redistributed",
         access_label="PUBLIC", credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("وصول سفن القمح إلى ميناء الإسكندرية", "تصدير الغاز المسال من إدكو",
                  "حركة السفن في باب المندب", "ميناء دمياط شحنات",
                  "تفريغ شحنة قمح ميناء سفاجا"),
         notes="THE LAYER WHERE EGYPT IS STRONGEST, because its economics ARE physical: a canal, "
               "a pipeline, two LNG trains and a grain import programme. A vessel count is not a "
               "sentiment index -- it is a count of hulls, and it cannot be revised into a "
               "different reality. Where a licensed AIS feed would be the natural source the "
               "desk uses PUBLICLY REPORTED derivatives of it only, and says so."),

    # ---- source_graph --------------------------------------------------------------------
    _src("eg_source_graph", "How the next Egyptian source is found -- citation and link graphs",
         layer="source_graph",
         roots=("citation and footnote trails in IMF and World Bank Egypt staff reports, which "
                "name the domestic series they used and therefore name sources the desk has not "
                "catalogued",
                "outbound link graphs from capmas.gov.eg and cbe.org.eg statistics pages",
                "reference lists of ERF and ECES working papers",
                "desks/mt5/data/deep_forest_sources.json -- the desk's own grounds registry, "
                "where new Egyptian grounds are ADDED rather than hard-coded"),
         languages=("ar", "en"),
         licence="free, public; this layer produces SOURCE CANDIDATES, never observations",
         access_label="PUBLIC", credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("المصادر الإحصائية المستخدمة تقرير صندوق النقد مصر",
                  "قاعدة بيانات وزارة التخطيط مصر", "الجهات المصدرة للبيانات الاقتصادية مصر",
                  "مراجع دراسة السوق الموازية مصر", "بوابة البيانات المفتوحة مصر"),
         notes="THE LAYER THAT STOPS THE PACK FROM FREEZING AT THE SOURCES SOMEBODY HAPPENED TO "
               "KNOW. A staff report's footnotes are the cheapest source-discovery mechanism in "
               "existence: the Fund had to name the series it used, and several of those series "
               "are Egyptian publications nobody outside the ministry cites. This layer's OUTPUT "
               "is a candidate list for the other nine, and its REFUSAL RECORD -- what was found "
               "and deliberately not crawled -- is kept with it so a future session does not "
               "re-find and re-reject the same ground."),

    # ---- refusals (recorded, not crawled) -------------------------------------------------
    _src("eg_refused", "Sources this pack refuses on purpose",
         layer="source_graph",
         roots=("(none -- this row records refusals, not crawl targets)",),
         languages=("ar", "en"),
         licence="n/a",
         access_label="ACCESS_UNCLEAR", credibility="UNKNOWN", predictive_state="UNTESTED",
         machine_use_allowed=True,
         queries=("تداول العملات الرقمية في مصر", "بيع الدولار عبر التطبيقات",
                  "شركات وساطة غير مرخصة مصر", "أسهم البورصة المصرية توصيات"),
         notes="REFUSED, EACH FOR A NAMED REASON. (1) ANY CRYPTO-EXCHANGE VENUE order book, API "
               "or native feed (universe mandate, 2026-08-18). EGYPT IS THE SHARPEST CASE IN "
               "THIS CIVILIZATION FOR STATING THAT REFUSAL EXPLICITLY, because the country has a "
               "large informal peer-to-peer dollar-stablecoin market that functions as a "
               "PARALLEL FX CHANNEL -- it is genuinely the thing an unconstrained researcher "
               "would reach for, and it is exactly what the mandate forbids. It is carried as "
               "PUBLIC COMMENTARY ONLY, pit_feasible=False, no venue named or crawled, and the "
               "executable leg is the broker's own BTCUSD CFD. (2) SINGLE-NAME EGX HYPOTHESIS "
               "MINING (two-lane order, 2026-09-06) -- disclosures are read for EVENT context "
               "and never mint a statistical hypothesis. (3) Redistribution of any licensed "
               "real-time EGX feed, vendor terminal, or licensed AIS service. (4) Any private "
               "group, member list, or personal data from the social layers above."),
)

#: THE TEN-LAYER COVERAGE LEDGER. Every layer is either NAMED WITH ITS SOURCES or declared
#: ABSENT WITH A REASON -- never blank, because a blank reads as "not thought about" and an
#: absence with a reason reads as a measurement. Egypt covers all ten, which is itself worth
#: recording: the layers that are hardest elsewhere (app_ecosystem, physical_economy) are two of
#: this country's strongest, because its dollar is priced in apps and its economy is a canal.
SOURCE_LAYER_COVERAGE: dict[str, str] = {
    layer: (", ".join(str(s["id"]) for s in SOURCE_CLASSES if s["layer"] == layer)
            or f"ABSENT: no source catalogued for the {layer} layer in Egypt")
    for layer in LAYERS
}


def source_layer_report() -> dict[str, Any]:
    """Per-layer source counts, the restricted rows and the low-credibility rows, MEASURED.

    Three things a reviewer should be able to read in one call without opening the table: how
    many sources each of the ten layers actually has (a layer with one row is thin and says so),
    which rows are REGISTERED BUT FORBIDDEN TO THE CRAWLER, and which rows are deliberately kept
    at low credibility. The last of these is the one most likely to be quietly deleted by a
    future tidy-up, so it is published rather than buried.
    """
    counts = {layer: sum(1 for s in SOURCE_CLASSES if s["layer"] == layer) for layer in LAYERS}
    return {
        "code": CODE,
        "layers": LAYERS,
        "counts": counts,
        "total_sources": len(SOURCE_CLASSES),
        "absent_layers": tuple(k for k, v in SOURCE_LAYER_COVERAGE.items()
                               if v.startswith("ABSENT:")),
        "coverage": SOURCE_LAYER_COVERAGE,
        "machine_use_forbidden": tuple(str(s["id"]) for s in SOURCE_CLASSES
                                       if not s["machine_use_allowed"]),
        "low_credibility_kept": tuple(str(s["id"]) for s in SOURCE_CLASSES
                                      if s["credibility"] in ("UNRELIABLE", "FRINGE",
                                                              "CONTRADICTED")),
        "native_query_total": sum(len(s["queries"]) for s in SOURCE_CLASSES),
        "note": "a FRINGE row is kept at low weight, never dropped: a devaluation rumour that "
                "turned out wrong is still evidence about expectations. A "
                "machine_use_forbidden row is registered and never fetched: omitting it would "
                "hide a known source, scraping it would breach its terms.",
    }


# --------------------------------------------------------------------------- datasets
DATASETS: tuple[dict[str, Any], ...] = (
    dataset("eg_cbe_official_daily_rate",
            source="Central Bank of Egypt, official daily exchange rate page (cbe.org.eg)",
            coverage="the official buy/sell reference rate for the pound against the dollar and "
                     "the other majors, each Egyptian business day (Sunday to Thursday)",
            frequency="daily on Egyptian business days -- NOT Monday to Friday, and a pipeline "
                      "that assumes a Western week will read Sunday as missing and Friday as "
                      "late",
            publication_lag_days=0.5,
            revisions="the published rate for a past date is not revised. THE PAGE IS, and that "
                      "is the real failure mode: the CBE serves the CURRENT rate on a page "
                      "rather than a history through an API, so a moved or restyled page loses "
                      "the series rather than corrupting it, and the archive layer is the only "
                      "point-in-time reader",
            licence="free, public, no key",
            history_from="the live page serves the current value only; usable history exists as "
                         "the desk's stored vintages and as public web captures",
            pit_feasible=True,
            assets=("USDTRY", "USDZAR", "XAUUSD"),
            mechanism_families=("fx_reference", "regime_state", "policy_reaction"),
            how_to_fetch="GET the CBE rate page, store the response bytes with the fetch "
                         "timestamp and a content hash as one vintage; a shape change is a NAMED "
                         "failure, never a silently empty series"),
    dataset("eg_cbe_net_foreign_assets",
            source="Central Bank of Egypt, monetary and banking developments (NFA of the "
                   "banking system)",
            coverage="foreign assets minus foreign liabilities of the CBE and the commercial "
                     "banks, monthly",
            frequency="monthly",
            publication_lag_days=42.0,
            revisions="revised as bank returns are restated; the revisions are material in "
                      "stress months, which are exactly the months of interest, so vintage "
                      "storage is not optional here",
            licence="free, public",
            history_from="the modern monthly series runs back over two decades in the bulletin "
                         "archive",
            pit_feasible=True,
            assets=("USDTRY", "USDZAR", "XAUUSD", "UST10Y"),
            mechanism_families=("balance_of_payments_stress", "regime_state",
                                "devaluation_probability"),
            how_to_fetch="the monthly statistical bulletin PDF and the monetary developments "
                         "tables; parse to a typed series and keep the source PDF as the vintage "
                         "artefact. THIS IS THE SERIES THAT WENT DEEPLY NEGATIVE BEFORE THE "
                         "2022-2024 DEVALUATIONS and it is the first thing to read about Egypt"),
    dataset("eg_cbe_net_international_reserves",
            source="Central Bank of Egypt, net international reserves release",
            coverage="headline NIR in USD, monthly, with the gold tranche valued at market",
            frequency="monthly, published in the first week for the prior month",
            publication_lag_days=7.0,
            revisions="occasionally restated; the COMPOSITION is not disclosed at the level "
                      "needed to separate owned reserves from Gulf deposits and swap lines",
            licence="free, public",
            history_from="1990s in the bulletin archive",
            pit_feasible=True,
            assets=("USDTRY", "USDZAR", "XAUUSD"),
            mechanism_families=("balance_of_payments_stress", "regime_state"),
            how_to_fetch="the CBE press release and the bulletin. READ IT ALONGSIDE NFA, NEVER "
                         "ALONE: reserves can be supported by deposits and swaps that are "
                         "LIABILITIES, so a rising NIR with a falling NFA is a defence being "
                         "financed rather than a position improving"),
    dataset("eg_cbe_mpc_decisions",
            source="Central Bank of Egypt, MPC press releases and the policy corridor",
            coverage="the overnight deposit and lending rates, the decision text, and the "
                     "announcement timestamp",
            frequency="eight scheduled meetings a year, plus unscheduled extraordinary meetings",
            publication_lag_days=0.0,
            revisions="a decision is not revised; the STATEMENT LANGUAGE is the object that "
                      "changes and is stored verbatim in both Arabic and English",
            licence="free, public",
            history_from="2005, when the corridor system was introduced",
            pit_feasible=True,
            assets=("USDTRY", "USDZAR", "UST10Y", "XAUUSD"),
            mechanism_families=("policy_reaction", "macro_surprise", "regime_state"),
            how_to_fetch="the CBE press-release page, stamped with the OBSERVED publication time "
                         "-- never a hard-coded UTC hour, because Cairo observes DST and the "
                         "same local announcement is two different UTC hours across the year. "
                         "THE EXTRAORDINARY MEETINGS MUST BE CAPTURED: 2024-03-06 is the largest "
                         "observation in the series and it is not on any published calendar"),
    dataset("eg_capmas_cpi",
            source="CAPMAS consumer price index",
            coverage="headline and core urban CPI, monthly and annual",
            frequency="monthly, released around the 10th for the prior month",
            publication_lag_days=10.0,
            revisions="rarely revised; the BASKET IS RE-BASED periodically, which is a series "
                      "break rather than a revision and is declared as an era boundary",
            licence="free, public",
            history_from="the current basket definition from the 2010s; earlier series in the "
                         "archive under different weights",
            pit_feasible=True,
            assets=("USDTRY", "USDZAR", "UST10Y"),
            mechanism_families=("macro_surprise", "policy_reaction"),
            how_to_fetch="the CAPMAS indicators page and the monthly bulletin. THE ARABIC "
                         "BULLETIN OFTEN PUBLISHES FIRST -- an English-only crawler is "
                         "systematically late on this release"),
    dataset("eg_capmas_trade_balance",
            source="CAPMAS foreign trade bulletin",
            coverage="imports and exports by commodity group and partner, including the wheat "
                     "and fuel import bills",
            frequency="monthly to quarterly, with an irregular cadence",
            publication_lag_days=75.0,
            revisions="revised across releases as customs returns settle",
            licence="free, public",
            history_from="2000s in the bulletin archive",
            pit_feasible=True,
            assets=("WHEAT", "CORN", "XBRUSD", "XNGUSD"),
            mechanism_families=("terms_of_trade", "import_dependence",
                                "balance_of_payments_stress"),
            how_to_fetch="the CAPMAS trade bulletin PDFs; the long and irregular lag means this "
                         "series is a CONDITIONER and never an event -- treating a 75-day-old "
                         "print as news is the standard error with Egyptian trade data"),
    dataset("eg_sca_transit_statistics",
            source="Suez Canal Authority navigation statistics",
            coverage="vessel COUNT, NET TONNAGE and revenue through the canal, by vessel type "
                     "where published",
            frequency="monthly, with some daily and weekly figures in announcements",
            publication_lag_days=30.0,
            revisions="RESTATED AND IRREGULARLY PUBLISHED, and this is declared rather than "
                      "papered over: a missing month is NOT a zero, and the publication cadence "
                      "itself thinned during the period of greatest interest, which is a "
                      "selection problem on top of a coverage one",
            licence="free, public",
            history_from="long history in the SCA archive, with the modern tabular form from "
                         "the 2010s",
            pit_feasible=False,
            assets=("XBRUSD", "XTIUSD", "GER40", "EUSTX50"),
            mechanism_families=("trade_shipping_logistics", "chokepoint_throughput",
                                "supply_shock"),
            how_to_fetch="the SCA navigation statistics pages and monthly tables, with the "
                         "archive layer for superseded pages. USE COUNT AND NET TONNAGE, NOT "
                         "REVENUE: revenue mixes throughput with the administered toll and the "
                         "SDR rate, so it is the worst of the three for research despite being "
                         "the headline number everyone quotes"),
    dataset("eg_sca_toll_and_circulars",
            source="Suez Canal Authority navigation circulars, toll schedules and surcharges",
            coverage="the administered transit toll in SDR, surcharges, discounts and the "
                     "rebate announcements aimed at winning traffic back from the Cape",
            frequency="irregular -- issued when the Authority decides, which is itself the "
                      "observable",
            publication_lag_days=1.0,
            revisions="superseded rather than revised; an old circular is replaced and the "
                      "archive layer is the only way to know what was in force on a past date",
            licence="free, public",
            history_from="the circular archive",
            pit_feasible=False,
            assets=("XBRUSD", "XTIUSD"),
            mechanism_families=("chokepoint_throughput", "administered_price",
                                "trade_shipping_logistics"),
            how_to_fetch="the circulars-and-notices pages plus captures. THE EFFECTIVE TOLL PER "
                         "VESSEL IS NOT RECONSTRUCTIBLE -- negotiated rebates are not published "
                         "per vessel -- so this dataset supports a DIRECTION and a DATE, never a "
                         "break-even, and `eg_suez_detour` declares the toll UNMEASURED for "
                         "exactly this reason"),
    dataset("eg_egx_investor_origin_flows",
            source="The Egyptian Exchange daily trading report, net flows by investor origin",
            coverage="daily buy, sell and net value for Egyptians, Arabs and Foreigners, split "
                     "into institutions and individuals",
            frequency="daily, Sunday to Thursday",
            publication_lag_days=0.3,
            revisions="occasionally restated for late trade reporting",
            licence="free, public summary tables",
            history_from="2000s",
            pit_feasible=True,
            assets=("EUSTX50", "GER40", "USDZAR"),
            mechanism_families=("portfolio_flow", "local_market_ecology", "risk_appetite"),
            how_to_fetch="the EGX daily trading report tables after the 14:30 Cairo close. KEEP "
                         "THE ARAB ROW SEPARATE FROM THE FOREIGN ROW -- Gulf money is strategic "
                         "and sticky, other foreign money is portfolio and leaves on the EM "
                         "factor, and summing them averages two actors with opposite "
                         "persistence. Note the SUNDAY print, which lands before any other "
                         "market in the desk's universe opens"),
    dataset("eg_gasc_wheat_tenders",
            source="GASC (General Authority for Supply Commodities) international wheat tenders",
            coverage="tender announcements, quantities sought, origins offered, prices awarded "
                     "and the payment terms",
            frequency="episodic -- historically frequent, and the FREQUENCY ITSELF IS THE SIGNAL",
            publication_lag_days=0.5,
            revisions="results are announced once and not revised; tenders are sometimes "
                      "CANCELLED after the fact, which is recorded as its own event",
            licence="free, public; announced publicly and reported in the trade and local press",
            history_from="long, though the procurement structure has changed and the era table "
                         "carries the boundary",
            pit_feasible=True,
            assets=("WHEAT", "CORN"),
            mechanism_families=("state_procurement", "import_dependence", "supply_shock"),
            how_to_fetch="the Ministry of Supply and GASC announcements plus Arabic trade press. "
                         "A SKIPPED TENDER IS AN OBSERVATION, NOT A MISSING VALUE: when the "
                         "state buyer of the world's largest wheat import programme does not "
                         "come to market in a month it normally would, the usual reason is that "
                         "the foreign exchange was not available -- which makes the ABSENCE an "
                         "FX observable"),
    dataset("eg_cbe_bop_remittances",
            source="Central Bank of Egypt balance of payments, workers' remittances",
            coverage="remittance inflows through the OFFICIAL banking channel, quarterly",
            frequency="quarterly",
            publication_lag_days=100.0,
            revisions="revised across releases",
            licence="free, public",
            history_from="1990s",
            pit_feasible=True,
            assets=("XAUUSD", "USDTRY"),
            mechanism_families=("capital_control_wedge", "channel_switch",
                                "balance_of_payments_stress"),
            how_to_fetch="the CBE BOP tables. READ THE FALL AS A CHANNEL SWITCH, NOT AS A FALL: "
                         "official remittances dropped sharply while the parallel premium was "
                         "wide and rebounded after the 2024 float, because the diaspora moved "
                         "money through informal channels rather than sending less. A study that "
                         "reads the official series as 'remittances' rather than as 'remittances "
                         "THROUGH THIS CHANNEL' has mismeasured the sign of the underlying flow"),
    dataset("eg_cbe_bop_tourism",
            source="Central Bank of Egypt balance of payments and Ministry of Tourism statistics",
            coverage="tourism receipts and arrivals, quarterly and monthly respectively",
            frequency="quarterly for receipts, monthly for arrivals",
            publication_lag_days=90.0,
            revisions="revised; arrivals and receipts are published by different bodies on "
                      "different clocks and do not always agree",
            licence="free, public",
            history_from="1990s",
            pit_feasible=True,
            assets=("USDILS", "XBRUSD"),
            mechanism_families=("fx_earnings", "regional_security_shock"),
            how_to_fetch="the CBE BOP tables and the Ministry of Tourism releases. Tourism is "
                         "one of Egypt's four hard-currency earners alongside the canal, "
                         "remittances and gas, and it is the one most exposed to a REGIONAL "
                         "SECURITY shock that has nothing to do with Egypt itself"),
    dataset("eg_imf_programme_documents",
            source="IMF Egypt country page -- Article IV consultations and EFF review staff "
                   "reports",
            coverage="the external financing gap, arrears, reserve composition, programme "
                     "conditionality, review dates and disbursement schedules",
            frequency="per review, typically two or more a year, plus the Article IV cycle",
            publication_lag_days=21.0,
            revisions="a staff report is not revised; a SUBSEQUENT review supersedes its "
                      "projections, which makes the sequence of reports a vintage series in "
                      "itself and a genuinely rare one",
            licence="free, public",
            history_from="the Fund's Egypt document archive",
            pit_feasible=True,
            assets=("UST10Y", "UKGILT", "USDTRY"),
            mechanism_families=("external_programme", "sovereign_credit", "regime_state"),
            how_to_fetch="the IMF country page document list. THE SINGLE BEST SOURCE ON EGYPT'S "
                         "TRUE FX POSITION, free, and it carries SCHEDULED REVIEW DATES -- one "
                         "of very few exogenous date grids this country offers"),
    dataset("eg_parallel_and_gold_premium_commentary",
            source="Egyptian Arabic-language price pages, bureau quotes and gold-shop quotes, "
                   "mined as public web commentary",
            coverage="daily parallel dollar quotes and local gold-pound and 21-carat prices, "
                     "with the source and timestamp of every quote preserved",
            frequency="daily, with uneven coverage and disagreement between aggregators",
            publication_lag_days=0.2,
            revisions="not revised; SUPERSEDED continuously, so a quote exists only as the "
                      "vintage the desk stored at the moment it read it",
            licence="public web; VERBATIM CLAIMS ONLY, never personal data, never private groups",
            history_from="only as far back as the desk's own vintages -- there is no official "
                         "history of an unofficial price, which is the defining limitation of "
                         "the whole parallel-market research programme",
            pit_feasible=False,
            assets=("XAUUSD", "USDTRY", "USDZAR", "BTCUSD"),
            mechanism_families=("capital_control_wedge", "devaluation_probability",
                                "household_hedging"),
            how_to_fetch="the retail_ecology and media source classes, stored one vintage per "
                         "fetch with the quoting source attached. NOT_PIT_SAFE AND SAID SO: "
                         "aggregators disagree by more than a bid-ask and some are stale, but "
                         "the DISAGREEMENT IS ITSELF A FEATURE -- it widens before a step -- and "
                         "having no observation of the most valuable quantity in this pack would "
                         "be the worse error"),
)


# --------------------------------------------------------------------------- actors
ACTORS: tuple[dict[str, Any], ...] = (
    actor("The Central Bank of Egypt as devaluation-timing actor",
          holds="the official exchange rate, the policy corridor, the reserves and the "
                "administrative access to foreign exchange",
          forced_to=("hold an administered rate until the defence becomes unaffordable, then "
                     "move it in ONE STEP rather than continuously",
                     "ration access to dollars while the rate is held, which creates the "
                     "parallel market it then has to close",
                     "meet programme conditionality on the exchange-rate regime to unlock "
                     "external financing"),
          when="eight scheduled MPC meetings a year plus EXTRAORDINARY meetings, which is where "
               "the history actually happened -- 2024-03-06 delivered a 600bp hike and the float "
               "at an unscheduled meeting",
          information=("the parallel premium", "net foreign assets and reserves",
                       "the import backlog and the LC queue", "IMF review milestones",
                       "committed Gulf inflows"),
          constraints=("a finite reserve stock and a banking system whose NFA can go negative",
                       "an import bill that does not compress on command",
                       "programme conditionality that names the regime as a condition",
                       "a political economy in which the bread and fuel subsidies bind"),
          instruments=("USDTRY", "USDZAR", "XAUUSD", "UST10Y"),
          counterparties=("the IMF", "Gulf sovereign investors", "Egyptian banks and importers",
                          "foreign holders of Egyptian bills"),
          observables=("the official rate page", "net foreign assets", "MPC statements and "
                       "their observed timestamps", "certificate-of-deposit issuance",
                       "the parallel premium closing in one step"),
          impact="the step move is the event: it reprices Egyptian risk, the frontier "
                 "devaluation complex and the regional EM peers within the session, and it "
                 "resolves months of accumulated expectation at once",
          persistence="structural, with FIVE steps in a decade -- so the mechanism is durable "
                      "and the SAMPLE IS SINGLE DIGIT, which is the binding constraint on every "
                      "cell built on it",
          falsifier="if USDTRY and USDZAR show no abnormal move in the sessions following an "
                    "Egyptian step devaluation relative to matched non-event sessions with the "
                    "same global EM beta, the peer-repricing channel does not exist and this "
                    "actor reaches no instrument the desk can trade",
          notes="THE MIRROR IMAGE OF THE SARB, and the contrast is the research design: South "
                "Africa's bank refuses to defend its currency and its FX has no intervention "
                "reaction function; Egypt's defends administratively until it cannot. Neither "
                "pack is complete without the other as its control."),
    actor("The Suez Canal Authority as a toll-setting monopolist facing a competing route",
          holds="the canal, the transit toll schedule in SDR, and a rebate power it uses "
                "selectively",
          forced_to=("price a transit against a FREE ALTERNATIVE -- the Cape of Good Hope -- "
                     "which no other chokepoint operator faces so directly",
                     "publish navigation circulars when it changes tolls or grants rebates",
                     "defend traffic share when diversion becomes cheaper than transit"),
          when="circulars are issued irregularly and are dated; transit statistics are monthly",
          information=("transit counts and net tonnage in real time",
                       "war-risk premia quoted to its customers", "competitor voyage economics",
                       "the state's own hard-currency needs"),
          constraints=("the Cape route, which is always available and cannot be blockaded",
                       "a toll denominated in SDR against costs in pounds",
                       "the Egyptian state's dependence on canal receipts as a hard-currency "
                       "earner, which pushes toward RAISING tolls exactly when traffic is "
                       "falling -- the most self-defeating incentive in this pack"),
          instruments=("XBRUSD", "XTIUSD", "GER40", "EUSTX50"),
          counterparties=("tanker and container operators", "charterers and cargo owners",
                          "marine underwriters", "the Egyptian treasury"),
          observables=("monthly vessel count and net tonnage", "navigation circulars and toll "
                       "notices", "publicly announced rebates", "canal revenue"),
          impact="a toll or rebate change alters the arbitrage between Suez and the Cape at the "
                 "margin; the TRAFFIC it wins or loses changes global tonne-miles, which is a "
                 "freight-capacity shock with a crude-differential and European-cost leg",
          persistence="structural -- the geography is permanent and the alternative route is "
                      "permanent, so the arbitrage recurs whenever the risk term moves",
          falsifier="if the XBRUSD-XTIUSD differential shows no conditional response to measured "
                    "changes in Suez net tonnage after controlling for global crude inventories "
                    "and the dollar, the chokepoint-to-differential channel is absent and this "
                    "pack's flagship mechanism is dead",
          notes="THE MOST MECHANICALLY CLEAN ACTOR IN THE PACK. The diversion decision is a cost "
                "comparison a shipbroker writes down, not a sentiment: toll plus war risk "
                "against bunkers plus charter days. `eg_suez_detour` computes the half of it "
                "that is geometry and declares the other half UNMEASURED."),
    actor("Global container and tanker operators choosing Suez versus the Cape",
          holds="the fleet, the charters, and the routing decision itself",
          forced_to=("re-route when the war-risk premium and crew risk exceed the cost of the "
                     "longer voyage, and re-route BACK when it falls",
                     "honour charterparty and insurance terms that may exclude listed areas",
                     "absorb the extra bunkers and days, or pass them through as surcharges"),
          when="continuously, in decisions announced by individual lines and visible in "
               "aggregate in the SCA statistics a month later",
          information=("underwriters' quotes and listed-area designations",
                       "incident reports in the southern Red Sea", "bunker prices",
                       "charter rates and the value of cargo afloat"),
          constraints=("insurance terms, which can make a route uninsurable rather than "
                       "expensive", "schedule integrity promised to customers",
                       "vessel availability, because longer voyages absorb capacity"),
          instruments=("XBRUSD", "XTIUSD", "GER40", "EUSTX50", "EURUSD"),
          counterparties=("marine underwriters and P&I clubs", "charterers and cargo owners",
                          "the Suez Canal Authority", "European importers"),
          observables=("individual carriers' public routing announcements",
                       "P&I and joint war committee listed-area circulars",
                       "SCA transit counts", "publicly reported freight rate indices"),
          impact="the diversion does not remove cargoes, it LENGTHENS VOYAGES -- so it absorbs "
                 "effective fleet capacity exactly as a demand increase would, which raises "
                 "freight and loads cost into the seaborne crude differential and European "
                 "landed prices",
          persistence="episodic and fast-reversing: the decision flips back when the risk term "
                      "falls, so this is a REGIME that switches rather than a trend",
          falsifier="if European industrial indices show no differential response to measured "
                    "diversion episodes after controlling for energy prices and the global "
                    "equity factor, the supply-chain-cost channel is not measurable at this "
                    "frequency and only the crude leg survives",
          notes="Named as a CLASS. No shipping line is ever a symbol on a docket (two-lane "
                "order, 2026-09-06)."),
    actor("GASC and the Egyptian state as the world's largest wheat buyer",
          holds="the strategic wheat reserve, the subsidised bread programme and the import "
                "tender programme",
          forced_to=("buy wheat in size on a recurring schedule because the bread subsidy is "
                     "politically non-negotiable",
                     "pay in hard currency it may not have, which is why tenders get skipped",
                     "accept a higher price rather than not buy, when the reserve runs low"),
          when="tenders are announced publicly and episodically; the domestic harvest "
               "procurement season runs in the spring",
          information=("the strategic reserve in months of cover", "world wheat prices and "
                       "freight", "the FX position", "the domestic harvest"),
          constraints=("hard-currency availability, the binding one",
                       "storage and port discharge capacity",
                       "a subsidy bill inside a budget under IMF review"),
          instruments=("WHEAT", "CORN"),
          counterparties=("international grain traders", "Black Sea and European origins",
                          "the Ministry of Finance"),
          observables=("tender announcements and awarded prices",
                       "TENDER ABSENCE when one was expected",
                       "reserve-cover statements", "vessel arrivals at grain ports"),
          impact="an unusually large tender is a world wheat demand event; a SKIPPED tender is an "
                 "Egyptian FX event. The causality runs BOTH WAYS and that is what makes WHEAT "
                 "an anchor instrument for this pack rather than a decoration",
          persistence="structural -- the import dependence is a function of population and "
                      "arable land and does not change on a research horizon",
          falsifier="if WHEAT shows no abnormal return in the sessions around large Egyptian "
                    "tender announcements relative to matched non-tender sessions with the same "
                    "Black Sea supply state, the state-buyer channel carries no information the "
                    "market has not already priced",
          notes="THE ABSENCE IS THE OBSERVATION. A pipeline that treats a skipped month as "
                "missing rather than as a zero throws away the FX signal, which is the more "
                "valuable of the two."),
    actor("Egyptian households as gold buyers",
          holds="a large stock of household gold -- coins, the gold pound, and 21-carat "
                "jewellery held as savings rather than as ornament",
          forced_to=("hedge an expected devaluation through the only hard asset they can legally "
                     "and easily buy, because dollars are rationed and gold shops are not",
                     "pay a LOCAL PREMIUM over the world price when the control binds",
                     "sell back into the same shops when they need pounds, which is why the "
                     "premium can invert"),
          when="continuously, with a documented surge in the weeks before and after each "
               "devaluation step and a seasonal peak in the wedding and Eid windows",
          information=("the parallel dollar rate", "the local gold quote and the making charge",
                       "rumours of an imminent step", "certificate-of-deposit rates as the "
                       "competing pound asset"),
          constraints=("no legal access to dollars at the official rate in size",
                       "the making charge, a real non-monetary cost of the jewellery form",
                       "the resale spread at the shop"),
          instruments=("XAUUSD", "USDTRY"),
          counterparties=("gold shops and the domestic bullion trade", "importers of bullion",
                          "state banks selling high-yield certificates"),
          observables=("the local gold-pound and 21-carat quote",
                       "the premium over the world price converted at the OFFICIAL rate",
                       "the same premium converted at the PARALLEL rate, which should be near "
                       "zero if the wedge explanation is right -- THAT COMPARISON IS THE TEST"),
          impact="a SECOND INDEPENDENT ESTIMATE of the same capital-control wedge the parallel "
                 "rate measures, from an entirely different market with different participants. "
                 "Two independent estimates of one latent quantity is a far stronger research "
                 "object than either alone",
          persistence="structural while the control exists; it disappears when the pound floats "
                      "freely, which makes the 2024 boundary a live test of the mechanism",
          falsifier="if the local gold premium converted at the PARALLEL rate is not "
                    "statistically closer to zero than the same premium converted at the "
                    "OFFICIAL rate, the premium is not measuring the FX wedge at all and is "
                    "measuring local bullion-market frictions -- in which case the gold channel "
                    "is a domestic microstructure story with no FX content",
          notes="EGYPT IS A PRICE-TAKER AT GLOBAL SCALE. This actor says nothing about the LEVEL "
                "of XAUUSD and the edges that touch gold say so explicitly. The object is the "
                "REGIONAL PREMIUM AND FLOW, never the world price."),
    actor("Egyptian importers under letter-of-credit restriction",
          holds="import contracts, cargoes stranded at port, and a queue position for a bank FX "
                "allocation",
          forced_to=("finance imports by letter of credit rather than documentary collection "
                     "once the 2022 rule bound, which converted a commercial decision into a "
                     "bureaucratic queue",
                     "pay demurrage on cargo they cannot clear",
                     "buy dollars in the parallel market at a premium, or stop importing"),
          when="continuously through the 2022-2023 restriction period; the rule change dates "
               "themselves are gazetted and dated",
          information=("their queue position", "the parallel rate", "the priority list for "
                       "essential goods", "their own inventory runway"),
          constraints=("the LC requirement and the bank's FX allocation",
                       "port storage and demurrage costs",
                       "input dependence -- a factory without imported inputs stops"),
          instruments=("USDTRY", "USDZAR", "WHEAT", "CORN"),
          counterparties=("Egyptian banks", "foreign suppliers", "the customs authority"),
          observables=("publicly reported estimates of the value of goods stranded at ports",
                       "the gazetted rule change dates", "complaint threads describing a "
                       "refused LC, which are the earliest human-level signal the control binds",
                       "import volumes in the CAPMAS trade bulletin, with a long lag"),
          impact="THE MECHANISM THAT MADE THE PARALLEL PREMIUM PERSIST. Rationing at the official "
                 "rate pushes marginal demand to the parallel market, which is exactly why the "
                 "official rate stopped clearing and the spread became informative",
          persistence="dated and bounded: the LC requirement was imposed in early 2022 and "
                      "formally lifted at the end of 2022, with the backlog clearing over "
                      "2023-2024. A NATURAL EXPERIMENT WITH A GAZETTE BEHIND IT",
          falsifier="if the parallel premium shows no level shift around the imposition and "
                    "removal of the LC requirement after controlling for reserves and the global "
                    "EM factor, the rationing mechanism is not what drove the premium and the "
                    "pack's account of the wedge is wrong",
          notes="The clearest policy-dated natural experiment in this pack, and the reason the "
                "import-restriction era is carried as its own boundary."),
    actor("Foreign holders of Egyptian treasury bills -- the carry, or hot-money, stock",
          holds="a stock of local-currency Egyptian bills bought for a very high nominal yield "
                "against an administratively stable exchange rate",
          forced_to=("roll or exit at maturity",
                     "convert pounds to dollars to repatriate, which requires the CBE's "
                     "repatriation mechanism to be functioning",
                     "JOIN A QUEUE when it is not, which converts a liquid position into an "
                     "illiquid one without any price ever printing"),
          when="continuously, with stress concentrated at the moments the global carry trade "
               "turns -- which is exogenous to Egypt entirely",
          information=("the bill yield against the expected devaluation",
                       "the repatriation mechanism's status", "reserves and NFA",
                       "the global risk appetite for frontier carry"),
          constraints=("the repatriation mechanism, which is a POLICY and not a market",
                       "mandate limits on frontier exposure",
                       "the fact that the exit is rationed, not priced"),
          instruments=("UST10Y", "UKGILT", "USDTRY", "USDZAR"),
          counterparties=("the Egyptian treasury", "the CBE", "local banks as intermediaries"),
          observables=("the monthly stock of non-resident bill holdings",
                       "the eurobond spread", "publicly reported repatriation backlogs",
                       "programme documents stating the arrears"),
          impact="the STOCK is the size of a potential forced flow, and the reserves and NFA say "
                 "whether it can be honoured. When it cannot, the loss is realised as a QUEUE "
                 "and then as a devaluation, not as a mark-to-market",
          persistence="cyclical: the stock rebuilds whenever the yield is high enough and the "
                      "rate looks stable, which is the same condition that makes the next exit "
                      "crowded",
          falsifier="if the size of the non-resident bill stock has no predictive content for "
                    "the subsequent widening of the parallel premium after controlling for "
                    "reserves and the global carry factor, the crowded-exit mechanism is not "
                    "measurable at monthly frequency",
          notes="THE CARRY LOOKED LIKE A YIELD AND WAS ACTUALLY AN OPTION SOLD ON THE PEG. A "
                "study that treats the bill yield as the return has mismeasured the position by "
                "leaving out the rationed exit, which is where the loss lived."),
    actor("The diaspora remittance sender choosing between the official and parallel channel",
          holds="a monthly hard-currency income earned abroad and an obligation to support a "
                "household in Egypt",
          forced_to=("choose a channel EVERY MONTH: a bank or app transfer converted at the "
                     "official rate, or an informal transfer settled at the parallel rate",
                     "take the better rate, because the difference is a large fraction of a "
                     "family's income and the decision is not marginal",
                     "switch BACK to the official channel the moment the wedge closes"),
          when="monthly, with a pronounced seasonal peak in the Ramadan and Eid windows and "
               "around the start of the school year",
          information=("the official rate offered by the bank or remittance app",
                       "the parallel rate quoted in Egypt today",
                       "the fee, which the app publishes on its own help page",
                       "how fast each channel actually delivers"),
          constraints=("compliance and limits on the formal channel",
                       "trust and counterparty risk on the informal one",
                       "the recipient's need for cash pounds rather than a bank balance"),
          instruments=("XAUUSD", "USDTRY", "USDZAR"),
          counterparties=("Egyptian banks and remittance operators", "informal transfer networks",
                          "the receiving household"),
          observables=("official remittance inflows in the CBE balance of payments",
                       "the official-versus-parallel spread",
                       "publicly published app conversion rates and fees, which are the "
                       "EFFECTIVE official-channel rate the sender actually faces",
                       "public review text complaining about delays and limits"),
          impact="THE REMITTANCE CHANNEL SWITCH IS A DIRECT, MEASURABLE CONSEQUENCE OF THE "
                 "CAPITAL-CONTROL WEDGE -- one of the very few places in any of these packs "
                 "where a published official series moves because of a WEDGE rather than "
                 "because of the underlying activity. Official remittances fell sharply while "
                 "the premium was wide and rebounded after the 2024 float, and the diaspora did "
                 "not send less; it sent differently",
          persistence="structural while the wedge exists, and it closes with the wedge -- which "
                      "makes the 2024 float a clean before-and-after on the same population",
          falsifier="if the official remittance series shows no relationship to the "
                    "official-versus-parallel spread after controlling for the diaspora's own "
                    "income cycle, oil-state employment and the Eid seasonal, the channel-switch "
                    "interpretation is wrong and the series is simply measuring remittances",
          notes="ONE OF THE BEST ACTORS IN THIS WHOLE CIVILIZATION: a household-level decision, "
                "taken monthly by millions of people, with a published quantity on one side and "
                "a mined quantity on the other, and a dated policy change that switches it."),
    actor("The IMF as an external constraint with scheduled review dates",
          holds="the programme, the conditionality and the disbursement schedule",
          forced_to=("complete or delay reviews on published dates",
                     "publish staff reports that state Egypt's true external position",
                     "make the exchange-rate regime a condition, which is why the float is a "
                     "programme event as much as a monetary one"),
          when="per review, typically two or more a year, plus the Article IV cycle",
          information=("reserves, arrears and the financing gap",
                       "fiscal performance against targets", "the state's role in the economy",
                       "committed Gulf and bilateral financing"),
          constraints=("its own board process and lending rules",
                       "the size of the financing gap relative to what it can lend",
                       "the political limits on what Egypt will actually implement"),
          instruments=("UST10Y", "UKGILT", "USDTRY"),
          counterparties=("the Egyptian authorities", "Gulf bilateral financiers",
                          "eurobond holders"),
          observables=("review completion announcements and their dates",
                       "staff reports and their stated financing gaps",
                       "programme augmentation announcements"),
          impact="a review completion releases a tranche AND validates the policy path, so it "
                 "compresses the eurobond spread and, through the global duration leg, reaches "
                 "the only fixed-income instruments the desk can trade here",
          persistence="programme-length, several years, with a dated review grid throughout",
          falsifier="if the Egyptian eurobond spread shows no abnormal move around scheduled "
                    "review completion dates relative to matched non-review windows, the "
                    "scheduled-milestone channel is absent and only unscheduled programme news "
                    "matters",
          notes="ONE OF VERY FEW EXOGENOUS DATE GRIDS THIS COUNTRY OFFERS. Egypt has no "
                "close-out calendar, no index rebalance and no domestic expiry -- the Fund's "
                "review calendar is the substitute, and it is published."),
    actor("Gulf sovereign investors and the Ras El Hekma class of transaction",
          holds="sovereign capital deployed into Egyptian assets, land and deposits at the CBE",
          forced_to=("recycle hydrocarbon surpluses into regional assets",
                     "convert existing central-bank deposits into equity or land when that is "
                     "the negotiated form, which is a BALANCE-SHEET transformation and not new "
                     "money in the amount headlined",
                     "act on a political timetable as much as a commercial one"),
          when="episodic and lumpy -- a single transaction can exceed a year of any other "
               "hard-currency inflow, which makes this the highest-variance item in Egypt's "
               "external accounts",
          information=("Egypt's financing gap", "asset valuations after a devaluation",
                       "the political relationship", "their own fiscal position and the oil "
                       "price"),
          constraints=("their own budgets, which move with crude",
                       "a stated shift from open-ended deposits towards investment with a "
                       "return", "the availability of assets Egypt is willing to sell"),
          instruments=("XBRUSD", "XTIUSD", "USDTRY", "EUSTX50"),
          counterparties=("the Egyptian state and its sovereign fund", "the CBE",
                          "the IMF, whose programme arithmetic depends on these inflows"),
          observables=("announced transaction values and their structure",
                       "the split between NEW money and CONVERTED deposits, which is the number "
                       "that matters and is usually buried",
                       "CBE foreign liabilities falling when a deposit is converted",
                       "Gulf fiscal positions and the crude price"),
          impact="the February 2024 Ras El Hekma agreement with ADQ, together with the IMF "
                 "programme augmentation, is what FINANCED the 6 March 2024 float: a step "
                 "devaluation is only survivable if there are dollars to clear the backlog with, "
                 "and this actor supplied them",
          persistence="episodic, politically driven, and NOT forecastable from Egyptian data "
                      "alone -- it is partly a function of the crude price, which is why XBRUSD "
                      "is in this actor's instruments",
          falsifier="if the timing of large Gulf commitments shows no relationship to the crude "
                    "price and to Egypt's measured financing gap, the recycling mechanism is not "
                    "the driver and these transactions are purely political -- in which case "
                    "they are unforecastable and must be treated as pure event risk",
          notes="THE HEADLINE VALUE IS NOT THE CASH. A large part of these transactions has been "
                "the conversion of EXISTING central-bank deposits, which changes the composition "
                "of Egypt's liabilities without adding the headline amount of new money. Any "
                "cell using announced values as an inflow series must net that out."),
    actor("The Egyptian gas complex and the LNG import-export swing",
          holds="domestic production including the Zohr field, two LNG liquefaction plants at "
                "Idku and Damietta, and a pipeline connection to Israeli gas",
          forced_to=("supply domestic power demand first, which peaks in the Egyptian summer",
                     "EXPORT the surplus as LNG when there is one and IMPORT when there is not, "
                     "having flipped between the two within a few years",
                     "curtail industry or shed load when the balance goes the wrong way"),
          when="seasonally, with the summer power peak; and structurally as field decline and "
               "import contracts change the balance",
          information=("field output and decline rates", "domestic demand and the weather",
                       "TTF and JKM prices against Brent-linked contract terms",
                       "Israeli pipeline availability"),
          constraints=("field decline at Zohr against original expectations",
                       "hard currency to pay for imported cargoes",
                       "liquefaction capacity that is worthless without feed gas",
                       "regional pipeline supply that can be interrupted for reasons that are "
                       "not Egyptian"),
          instruments=("XNGUSD", "XBRUSD"),
          counterparties=("European LNG buyers", "Israeli producers", "the domestic power sector",
                          "cargo traders"),
          observables=("LNG loadings and cancellations at Idku and Damietta",
                       "publicly reported import tenders for cargoes",
                       "domestic load-shedding announcements in the summer",
                       "pipeline flow interruptions"),
          impact="EGYPT HAS FLIPPED BETWEEN NET LNG EXPORTER AND NET IMPORTER, which is a real "
                 "swing in Mediterranean gas balance and an XNGUSD-relevant observable -- with "
                 "the honest caveat that XNGUSD is Henry Hub and the Egyptian trade prices off "
                 "TTF and Brent-linked terms, so the edge runs through a basis the desk cannot "
                 "trade",
          persistence="multi-year and directional as the field declines, with a sharp seasonal "
                      "overlay",
          falsifier="if XNGUSD shows no measurable response to Egyptian import-tender "
                    "announcements after controlling for European gas prices and the US storage "
                    "cycle, the transatlantic basis has absorbed the whole signal and the "
                    "Egyptian gas channel does not reach this desk's instruments",
          notes="The basis is declared as a named weakness rather than hidden, and the edge "
                "carries a control for it. An Egypt-to-XNGUSD cell without that control is "
                "measuring the US gas market."),
    actor("The Egyptian tourism sector as a hard-currency earner exposed to regional security",
          holds="hotel and Red Sea resort capacity, Nile cruise capacity and the antiquities "
                "circuit",
          forced_to=("sell capacity forward through European and Gulf tour operators",
                     "absorb cancellations when a regional security event occurs anywhere "
                     "nearby, whether or not it touches Egypt",
                     "discount into a weak season rather than leave rooms empty"),
          when="seasonally, with a European winter-sun peak in the Red Sea resorts and a spring "
               "and autumn peak on the Nile circuit",
          information=("forward bookings from operators", "regional security news",
                       "European consumer demand and the euro",
                       "airline capacity on the charter routes"),
          constraints=("perishable capacity -- an unsold room-night is gone",
                       "dependence on foreign tour operators' risk committees",
                       "the currency, which makes Egypt cheap after a devaluation and is the "
                       "one automatic stabiliser in this actor's favour"),
          instruments=("USDILS", "XBRUSD", "EUSTX50"),
          counterparties=("European and Gulf tour operators", "charter airlines",
                          "the CBE, which books the receipts"),
          observables=("monthly arrivals from the Ministry of Tourism",
                       "quarterly receipts in the CBE balance of payments",
                       "publicly reported operator cancellations after a regional event"),
          impact="one of Egypt's four hard-currency earners alongside the canal, remittances and "
                 "gas, and the one most exposed to an event that has NOTHING TO DO WITH EGYPT -- "
                 "which makes regional security a direct input to the Egyptian FX position",
          persistence="structural with a strong seasonal and sharp episodic drawdowns that "
                      "recover over quarters rather than months",
          falsifier="if Egyptian tourism arrivals show no measurable drawdown following regional "
                    "security escalations after controlling for European consumer demand and the "
                    "season, the contagion-by-geography channel does not exist and tourism is "
                    "simply a European demand series",
          notes="The cleanest case in the pack of Egypt being repriced for someone else's event, "
                "which is why USDILS is in the executable set."),
    actor("Egyptian state banks issuing high-yield certificates of deposit",
          holds="the retail pound deposit base and the certificate programmes issued against it",
          forced_to=("issue very high-rate certificates after each devaluation step to absorb "
                     "pound liquidity that would otherwise chase dollars or gold",
                     "honour those rates for the certificate's full term, which loads the "
                     "banks' margin for a year or three",
                     "manage the MATURITY, which returns that liquidity to the public on a "
                     "known date"),
          when="issuance is announced within days of each step move; maturity is contractual and "
               "therefore SCHEDULED",
          information=("deposit flight into dollars and gold", "the policy corridor",
                       "the parallel premium", "their own funding costs"),
          constraints=("the margin cost of paying far above the corridor",
                       "the state's interest in not letting the retail depositor be destroyed",
                       "the fact that absorbing liquidity does not create dollars"),
          instruments=("XAUUSD", "USDTRY"),
          counterparties=("Egyptian retail depositors", "the CBE", "the treasury"),
          observables=("certificate issuance announcements and their headline rates",
                       "the tranche sizes where reported",
                       "the maturity dates, which are derivable from the issue date and term",
                       "deposit dollarisation statistics in the CBE bulletin"),
          impact="A DATED, PRE-ANNOUNCED RELEASE OF POUND LIQUIDITY at maturity, into an economy "
                 "with a parallel dollar market and a household gold bid -- one of the very few "
                 "genuinely SCHEDULED flow events this pack has, in a country that otherwise "
                 "offers almost no exogenous date grid",
          persistence="episodic but mechanical: each step produces an issuance, each issuance "
                      "produces a maturity one or three years later",
          falsifier="if the local gold premium and the parallel spread show no abnormal "
                    "behaviour in the weeks around large certificate MATURITY dates relative to "
                    "matched non-maturity weeks, the liquidity-release channel carries no "
                    "measurable information and the certificates are a retail banking story only",
          notes="EASY TO DISMISS AS RETAIL BANKING TRIVIA AND IT IS NOT: it is the only Egyptian "
                "flow event whose date is known years in advance."),
)


# --------------------------------------------------------------------------- domains
DOMAINS: tuple[dict[str, Any], ...] = (
    domain("eg_fx_regime_state", "Which exchange-rate regime is actually in force, as a state "
                                 "variable rather than an assumption",
           objects=("the official rate's realised volatility, which is near zero under a peg and "
                    "positive under a float -- so the VOLATILITY IS THE REGIME INDICATOR",
                    "the official-versus-parallel spread as the peg's stress gauge",
                    "the dated regime announcements themselves",
                    "the CBE's own language about flexibility in MPC statements"),
           conditions=("reserves and net foreign assets", "IMF programme status",
                       "committed Gulf inflows", "the global dollar cycle"),
           instruments=("USDTRY", "USDZAR", "XAUUSD"),
           controls=("USDTRY as a matched managed-then-floated EM currency with a different "
                     "central bank and the same shape of history",
                     "USDZAR as a genuinely floating EM currency, which is the NEGATIVE control: "
                     "whatever is regime-specific to Egypt must not appear in it",
                     "the same calendar windows in periods with no regime change"),
           notes="THE DOMAIN EVERY OTHER ONE CONDITIONS ON. Pooling a peg period with a float "
                 "period measures the average of two data-generating processes and describes "
                 "neither. The 2024 float is a live boundary -- the two previous Egyptian "
                 "'floats' reverted to a de facto peg within about eighteen months, so whether "
                 "this one persists is UNMEASURED and is the pack's central open question."),
    domain("eg_parallel_premium", "The official-versus-parallel spread as a measured wedge",
           objects=("the daily spread between the official rate and mined parallel quotes",
                    "DISAGREEMENT ACROSS AGGREGATORS, which is itself a feature and widens "
                    "before a step",
                    "the gold-derived premium as a second independent estimate of the same wedge",
                    "the duration of a widening episode, not just its level"),
           conditions=("the import-restriction regime", "reserves and NFA",
                       "the season, because Eid import demand widens it mechanically",
                       "whether a programme review is pending"),
           instruments=("USDTRY", "USDZAR", "XAUUSD"),
           controls=("the gold-derived premium, which should move WITH the quote-derived one if "
                     "both measure the wedge and should diverge if either is an artefact",
                     "periods of equal reserve cover with no premium",
                     "randomised assignment of premium dates, which must destroy the effect",
                     "Turkey's own parallel-market episodes as a matched frontier case"),
           notes="NOT_PIT_SAFE at the dataset level and mined from commentary. The strength of "
                 "this domain is that TWO INDEPENDENT MARKETS -- currency dealers and gold shops "
                 "-- price the same latent quantity, so each is the other's control."),
    domain("eg_devaluation_timing", "The step move as an event, and what it reprices elsewhere",
           objects=("the dated step devaluations and their sizes",
                    "the spread's trajectory in the months before each",
                    "the session and week returns of the EM/frontier peer complex around them",
                    "extraordinary MPC meetings, which is where the steps actually happened"),
           conditions=("the global EM risk state", "the dollar cycle",
                       "whether external financing had just been secured"),
           instruments=("USDTRY", "USDZAR", "XAUUSD", "UST10Y"),
           controls=("matched non-event sessions with the same global EM beta",
                     "other frontier devaluations in the same period, which share the global "
                     "factor and not the Egyptian one",
                     "randomised event dates within the same quarter"),
           notes="n IS SINGLE DIGIT -- five steps in a decade -- and the observations are "
                 "serially dependent. This domain exists to be SIZED HONESTLY and can never "
                 "clear a gauntlet on one episode. Saying so here is cheaper than discovering it "
                 "after a hundred cells."),
    domain("eg_reserves_and_nfa", "The balance-of-payments position as a leading state",
           objects=("net foreign assets of the banking system, the diagnostic series",
                    "net international reserves, the headline one",
                    "THE GAP BETWEEN THEM, which is the part financed by liabilities",
                    "external arrears as stated in programme documents"),
           conditions=("the import bill", "canal, tourism, remittance and gas receipts",
                       "committed bilateral financing"),
           instruments=("USDTRY", "USDZAR", "UST10Y", "XAUUSD"),
           controls=("NIR alone, as the deliberately WEAKER measure -- if it predicts as well as "
                     "NFA the pack's claim about liabilities is wrong",
                     "matched months with equal reserve cover and different NFA",
                     "other frontier sovereigns' reserve paths over the same window"),
           notes="NFA WENT DEEPLY NEGATIVE BEFORE THE 2022-2024 SEQUENCE. If this pack has one "
                 "series a session should read before forming any Egyptian view, it is this."),
    domain("eg_suez_traffic", "Chokepoint throughput as a measured physical quantity",
           objects=("monthly vessel count and net tonnage through the canal",
                    "the share of world seaborne traffic that represents, using UNCTAD's "
                    "denominator -- a raw count cannot tell a diversion from a trade slowdown",
                    "toll and rebate circulars as dated administered-price events",
                    "the tonne-mile multiplier implied by the alternative route"),
           conditions=("the war-risk state", "the global trade cycle",
                       "crude and bunker prices", "vessel class, because the arbitrage differs "
                       "sharply between a tanker and a container ship"),
           instruments=("XBRUSD", "XTIUSD", "GER40", "EUSTX50"),
           controls=("the Gulf-to-US-Gulf route, where the Suez advantage is small and a "
                     "diversion should barely move the economics -- if freight responds equally "
                     "there, the mechanism being measured is not the canal",
                     "global crude inventories and the dollar as explicit regressors",
                     "the same months in years with no security event"),
           notes="THE PACK'S FLAGSHIP DOMAIN. A vessel count is a count of hulls; it cannot be "
                 "revised into a different reality. Publication is irregular and the dataset is "
                 "marked pit_feasible=False for exactly that reason."),
    domain("eg_red_sea_diversion", "The route decision as an insurance-driven regime switch",
           objects=("P&I and joint war committee listed-area designations, which are the "
                    "administrative act that moves the premium",
                    "carriers' public routing announcements",
                    "publicly reported freight rate indices",
                    "the diversion's tonne-mile consequence on each route"),
           conditions=("the incident rate in the southern Red Sea", "bunker prices",
                       "charter rates and fleet utilisation", "the toll and rebate schedule"),
           instruments=("GER40", "EUSTX50", "EURUSD", "XBRUSD", "XTIUSD", "USDILS"),
           controls=("EURUSD against the European indices, to separate the dollar leg from the "
                     "European cost leg -- the same trick the ZA pack uses with EURZAR",
                     "matched weeks with equal energy prices and no diversion",
                     "US indices, which face the same global factor and far less Suez exposure",
                     "randomised escalation dates within the same quarter"),
           notes="A REGIME THAT SWITCHES RATHER THAN A TREND: the decision flips back when the "
                 "risk term falls. The freight leg itself is NOT TRADABLE on this account and is "
                 "carried as an observable only."),
    domain("eg_wheat_import_dependence", "The state wheat buyer, in both causal directions",
           objects=("GASC tender announcements, quantities and awarded prices",
                    "TENDER ABSENCE in a month one was expected",
                    "the strategic reserve cover in months",
                    "vessel arrivals and discharge at Egyptian grain ports"),
           conditions=("Black Sea supply and export policy",
                       "Egypt's FX availability, which is why absences happen",
                       "the domestic harvest and procurement season",
                       "freight, which is itself a Suez variable"),
           instruments=("WHEAT", "CORN"),
           controls=("matched non-tender sessions with the same Black Sea supply state",
                     "other large importers' tenders, which share the world demand factor and "
                     "not the Egyptian FX one",
                     "randomised tender dates within the season",
                     "CORN as the feed-grain leg, which shares the import-dependence mechanism "
                     "and not the bread-subsidy politics"),
           notes="THE CAUSALITY RUNS BOTH WAYS and the domain is built to separate them: a large "
                 "tender is a world demand event, a SKIPPED tender is an Egyptian FX event, and "
                 "a model that treats the absence as missing data throws away the better half."),
    domain("eg_gold_household_hedge", "Household gold as a rationed-arbitrage capital-control "
                                      "gauge",
           objects=("the local gold-pound and 21-carat quote",
                    "the premium over the world price converted at the OFFICIAL rate",
                    "the same premium converted at the PARALLEL rate",
                    "the making charge as the non-monetary component to be netted out"),
           conditions=("the parallel premium", "certificate-of-deposit rates as the competing "
                       "pound asset", "the wedding and Eid seasonal", "devaluation rumours"),
           instruments=("XAUUSD", "USDTRY"),
           controls=("the parallel-rate-converted premium, which should be NEAR ZERO if the "
                     "wedge explanation is right -- that comparison is the whole test",
                     "world gold moves on days with no Egyptian premium change",
                     "other gold-buying EM households with no comparable control"),
           notes="EGYPT IS A PRICE-TAKER AT GLOBAL SCALE. Nothing in this domain is about the "
                 "LEVEL of XAUUSD; the object is the REGIONAL PREMIUM AND FLOW. Any cell that "
                 "drifts into predicting the world gold price from Egyptian demand has left the "
                 "domain and must be rejected on those grounds alone."),
    domain("eg_remittance_channel_switch", "A published official series that moves because of a "
                                           "wedge rather than because of activity",
           objects=("official remittance inflows in the CBE balance of payments",
                    "the official-versus-parallel spread",
                    "publicly published remittance-app conversion rates and fees, which are the "
                    "EFFECTIVE official-channel rate the sender faces",
                    "public review text complaining about delays and limits"),
           conditions=("the wedge", "the Eid and Ramadan seasonal",
                       "Gulf employment and the oil price, which set the diaspora's income",
                       "the 2024 float as a dated switch"),
           instruments=("XAUUSD", "USDTRY", "USDZAR"),
           controls=("the diaspora's own income cycle proxied by Gulf employment and crude",
                     "the Eid seasonal, which must be removed before the wedge term is read",
                     "other remittance corridors with no parallel market, which share the "
                     "income cycle and not the wedge",
                     "randomised assignment of spread values to quarters"),
           notes="ONE OF THE BEST DOMAINS IN THE CIVILIZATION: a monthly household decision taken "
                 "by millions, a published quantity on one side, a mined quantity on the other, "
                 "and a dated policy change that switches it. The quarterly frequency and the "
                 "100-day lag are the binding limitations and are declared."),
    domain("eg_external_programme_calendar", "Scheduled multilateral milestones as the country's "
                                             "only exogenous date grid",
           objects=("IMF review completion dates and their announcements",
                    "staff reports and their stated financing gaps",
                    "programme augmentation events",
                    "the eurobond spread as the transmission variable"),
           conditions=("the global duration and credit cycle",
                       "whether Gulf financing had just been committed",
                       "the fiscal path and arrears"),
           instruments=("UST10Y", "UKGILT", "USDTRY"),
           controls=("matched non-review windows with the same global credit factor",
                     "reviews that were DELAYED rather than completed, which share the "
                     "anticipation and not the outcome",
                     "other programme countries reviewed the same month"),
           notes="Egypt has no close-out calendar, no index rebalance and no domestic expiry. "
                 "This grid is the substitute and it is published -- which is the only reason "
                 "any dated Egyptian event study is possible at all."),
    domain("eg_eid_seasonality", "The lunar calendar as a demand seasonal and a data outage at "
                                 "the same time",
           objects=("the Eid al-Fitr and Eid al-Adha windows and the Ramadan month",
                    "import demand for food, livestock, clothing and gold in those windows",
                    "remittance inflow concentration",
                    "the EGX's shortened Ramadan session as a microstructure regime"),
           conditions=("which weekday the window lands on, because the Egyptian weekend is "
                       "Friday-Saturday and that determines the business days actually lost",
                       "the wedge, because Eid demand widens it mechanically",
                       "the Gregorian position, which drifts eleven days earlier each year"),
           instruments=("WHEAT", "CORN", "XAUUSD"),
           controls=("the same Gregorian weeks in years where Eid falls elsewhere -- THE LUNAR "
                     "DRIFT IS THE CONTROL, and it is a genuinely clean one because the solar "
                     "seasonal stays put while the lunar one moves",
                     "matched non-Eid weeks with the same wedge",
                     "randomised window placement within the year"),
           notes="THE DATA STOPS EXACTLY WHILE THE FLOW PEAKS, which is the least convenient "
                 "possible arrangement. A pipeline that forward-fills an Egyptian observable "
                 "across a four-day Eid is asserting a measurement nobody made -- UNMEASURED is "
                 "the verdict and must be carried as one."),
    domain("eg_risk_proxy_crypto_premium", "The informal stablecoin channel as a rationed-"
                                           "arbitrage risk gauge",
           objects=("publicly discussed local premium or discount on dollar stablecoins",
                    "the same wedge the parallel rate and the gold premium measure, from a THIRD "
                    "independent market"),
           conditions=("the parallel premium", "capital-control tightness",
                       "global crypto risk appetite, which is the main confound"),
           instruments=("BTCUSD", "XAUUSD"),
           controls=("the global crypto factor, as an explicit regressor -- without it this "
                     "domain measures BTCUSD and not Egypt",
                     "the gold and quote-derived premiums, which should co-move if all three "
                     "measure one wedge",
                     "periods of equal global crypto volatility with no local premium"),
           notes="PUBLIC COMMENTARY ONLY, pit_feasible=False, NO VENUE NAMED OR CRAWLED (universe "
                 "mandate, 2026-08-18). Egypt is the sharpest case in this civilization for "
                 "stating that refusal, because the P2P stablecoin market genuinely IS a "
                 "parallel FX channel and is exactly what an unconstrained researcher would "
                 "reach for. The executable leg is the broker's own BTCUSD CFD."),
)


# --------------------------------------------------------------------------- transmission
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    edge("eg_suez_transit_collapse_to_tonne_miles",
         source="Suez Canal Authority monthly vessel count and net tonnage",
         mechanism="a collapse in transits does not remove cargoes, it lengthens voyages round "
                   "the Cape of Good Hope -- roughly 4,700 extra nautical miles on the "
                   "Gulf-to-Europe crude leg and about 3,500 on the Asia-to-Europe container "
                   "leg. Global tanker and container demand is denominated in TONNE-MILES, so "
                   "the lengthening ABSORBS EFFECTIVE FLEET CAPACITY exactly as a demand "
                   "increase would, tightens freight, and loads cost into the seaborne crude "
                   "differential",
         targets=("XBRUSD", "XTIUSD"),
         sign="Suez net tonnage DOWN -> tonne-miles UP -> freight UP -> the Brent-WTI "
              "differential WIDENS, because the waterborne Atlantic-to-Europe barrel carries the "
              "freight and the inland US barrel does not",
         lag="the SCA publishes monthly with roughly a thirty-day lag; carrier announcements and "
             "war-risk circulars lead the statistic by weeks",
         horizon="ten to sixty sessions",
         control="the Gulf-to-US-Gulf route, where the Suez advantage is small and the economics "
                 "should barely move -- if freight responds equally there, the mechanism is not "
                 "the canal; plus global crude inventories and the dollar as explicit regressors",
         evidence="HYPOTHESIS",
         notes="THE PACK'S FLAGSHIP EDGE and the reason Egypt earns a department despite having "
               "no price. It must be measured against the SCA vintage that existed at the time, "
               "not the restated series -- publication is irregular and a missing month is not a "
               "zero."),
    edge("eg_red_sea_security_to_european_industry",
         source="joint war committee and P&I listed-area designations, carrier routing "
                "announcements, and publicly reported freight indices",
         mechanism="a security escalation raises the war-risk premium by an order of magnitude "
                   "and flips the route arbitrage for a whole class of vessels at once; the "
                   "resulting diversion adds ten to twelve days to the Asia-Europe leg and "
                   "raises the landed cost of imported inputs into European industry, "
                   "compressing margin in exactly the sectors that dominate GER40 and EUSTX50",
         targets=("GER40", "EUSTX50", "EURUSD"),
         sign="escalation and diversion -> European industrial landed cost UP -> GER40 and "
              "EUSTX50 DOWN relative to matched global-factor weeks; EURUSD is the CONTROL LEG "
              "and should carry the dollar component, not the cost component",
         lag="the insurance designation leads the routing announcement by days and the freight "
             "print by one to three weeks",
         horizon="five to forty sessions",
         control="EURUSD against the European indices to separate the dollar leg from the "
                 "European cost leg; US indices, which face the same global factor and far less "
                 "Suez exposure; and matched weeks with equal energy prices and no diversion",
         evidence="HYPOTHESIS",
         notes="The freight leg is NOT TRADABLE on this account, so this edge is a two-hop claim "
               "with an unobservable middle. That is a real weakness and it is stated here "
               "rather than discovered after the cells are compiled."),
    edge("eg_red_sea_escalation_to_regional_risk",
         source="incident reports and listed-area designations in the southern Red Sea and Bab "
                "el-Mandeb",
         mechanism="a regional security escalation reprices the whole eastern Mediterranean and "
                   "Red Sea risk complex, and the nearest liquid instrument to that risk on this "
                   "account is the shekel; Egyptian tourism and canal receipts are hit by the "
                   "same event without Egypt being party to it",
         targets=("USDILS", "XBRUSD"),
         sign="escalation -> USDILS UP and a crude risk premium UP in the sessions following",
         lag="intraday to days from the incident report",
         horizon="one to twenty sessions",
         control="matched sessions with equal global risk and no regional incident; and "
                 "escalations elsewhere in the world, which carry the global risk factor and not "
                 "the regional geography",
         evidence="HYPOTHESIS",
         notes="THE CLEANEST CASE OF EGYPT BEING REPRICED FOR SOMEBODY ELSE'S EVENT, which is "
               "why USDILS is in the executable set at all."),
    edge("eg_devaluation_step_to_em_peers",
         source="the dated Egyptian step devaluations and the extraordinary MPC meetings that "
                "delivered them",
         mechanism="a frontier devaluation of this size is read by allocators as information "
                   "about the whole managed-to-floating EM cohort -- who is next, and on what "
                   "terms -- so the peer currencies reprice on an Egyptian event they have no "
                   "direct exposure to",
         targets=("USDTRY", "USDZAR"),
         sign="Egyptian step devaluation -> USDTRY and USDZAR UP in the sessions following, with "
              "the effect LARGER in USDTRY (a regime peer) than in USDZAR (a free float), and "
              "that ORDERING IS THE TEST",
         lag="the announcement itself; Egyptian statements land in the late Cairo afternoon, "
             "whose UTC hour moves with Egyptian DST",
         horizon="intraday to ten sessions",
         control="matched non-event sessions with the same global EM beta; other frontier "
                 "devaluations in the same period, which share the global factor and not the "
                 "Egyptian one; and randomised event dates within the same quarter",
         evidence="HYPOTHESIS",
         notes="n IS SINGLE DIGIT -- five steps in a decade, serially dependent. This edge "
               "exists to be SIZED HONESTLY and can never clear a gauntlet on one episode."),
    edge("eg_parallel_spread_to_frontier_stress",
         source="the official-versus-parallel spread, mined daily, with the gold-derived premium "
                "as its independent replicate",
         mechanism="the spread measures how far the administered price has drifted from the "
                   "clearing price, which is exactly the quantity that determines when the "
                   "administered price must move; a widening spread is therefore a rising "
                   "DEVALUATION PROBABILITY, and a rising frontier-devaluation probability is a "
                   "frontier stress regime that the peer currencies price before the step",
         targets=("USDTRY", "USDZAR", "XAUUSD"),
         sign="spread WIDENING sustained over weeks -> frontier stress regime -> USDTRY and "
              "USDZAR drift UP and the regional gold bid strengthens, ahead of any step",
         lag="the spread is observable daily; the step it anticipates arrives months later, so "
             "this is a SLOW conditioner and never an event trigger",
         horizon="one to two quarters",
         control="the gold-derived premium, which must move WITH the quote-derived one if both "
                 "measure the wedge; periods of equal reserve cover with no premium; randomised "
                 "premium dates, which must destroy the effect; and Turkey's own parallel "
                 "episodes as a matched frontier case",
         evidence="HYPOTHESIS",
         notes="NOT_PIT_SAFE: the parallel series is commentary-mined, aggregators disagree, and "
               "history exists only as the desk's own vintages. Declared so the gap is visible, "
               "not so it can be traded before the data supports it."),
    edge("eg_household_gold_demand_to_regional_premium",
         source="the local gold-pound and 21-carat quote, and the premium over the world price "
                "converted at the official rate",
         mechanism="rationed access to dollars pushes household hedging demand into gold, which "
                   "is legally and easily purchasable; the resulting LOCAL premium is the wedge "
                   "plus a making charge. The flow is real physical demand in a regional bullion "
                   "market, and it concentrates in the devaluation-scare and Eid windows",
         targets=("XAUUSD",),
         sign="Egyptian devaluation scare -> local premium UP and regional physical demand UP. "
              "THE CLAIM IS ABOUT THE PREMIUM AND THE FLOW, NOT ABOUT THE LEVEL OF XAUUSD",
         lag="the premium responds within days of a rumour; the physical flow follows over weeks",
         horizon="five to forty sessions",
         control="the parallel-rate-converted premium, which must be NEAR ZERO if the wedge "
                 "explanation is right -- that comparison is the whole test; world gold moves on "
                 "days with no Egyptian premium change; and the making charge netted out by "
                 "using the COIN rather than jewellery",
         evidence="HYPOTHESIS",
         notes="EGYPT IS A PRICE-TAKER AT GLOBAL SCALE AND THIS EDGE SAYS SO IN ITS OWN SIGN "
               "FIELD. Any cell derived from it that drifts into predicting the world gold price "
               "from Egyptian demand has left the mechanism and must be rejected on those "
               "grounds alone, however well it fits."),
    edge("eg_wheat_tender_to_grain",
         source="GASC tender announcements, awarded quantities and prices -- AND tender ABSENCE "
                "in a month one was expected",
         mechanism="the world's largest wheat import programme is executed by a single state "
                   "buyer in public tenders, so its size is a demand event in the world market; "
                   "and because the constraint on buying is hard currency, its ABSENCE is an "
                   "Egyptian FX event. The causality runs in both directions through the same "
                   "announcement",
         targets=("WHEAT", "CORN"),
         sign="unusually LARGE tender -> WHEAT UP in the following sessions; SKIPPED tender "
              "where one was expected -> a signal about Egyptian FX availability rather than "
              "about wheat, and the two must be modelled as different events",
         lag="tenders are announced and awarded within days; the FX interpretation of an absence "
             "requires waiting out the month",
         horizon="one to twenty sessions for the demand leg; one to two quarters for the FX leg",
         control="matched non-tender sessions with the same Black Sea supply state; other large "
                 "importers' tenders, which share the world demand factor and not the Egyptian "
                 "FX one; CORN as the feed-grain leg with the same import dependence and none of "
                 "the bread-subsidy politics; and randomised tender dates within the season",
         evidence="HYPOTHESIS",
         notes="THE ABSENCE IS THE OBSERVATION. A pipeline that treats a skipped month as "
               "missing rather than as a zero throws away the more valuable half of this edge."),
    edge("eg_imf_review_to_duration_leg",
         source="IMF Egypt review completion dates, staff reports and programme augmentations",
         mechanism="a review completion releases a tranche and validates the policy path, "
                   "compressing the Egyptian eurobond spread; the eurobond is not tradable on "
                   "this account, so the reachable leg is the GLOBAL DURATION component of the "
                   "same position -- the part of a frontier bond that is a Treasury and a Gilt",
         targets=("UST10Y", "UKGILT"),
         sign="review COMPLETED -> Egyptian spread compresses -> the duration leg of frontier "
              "positioning is added back, a small bid in UST10Y and UKGILT in the window",
         lag="the completion announcement is dated and published on the Fund's calendar",
         horizon="one to fifteen sessions",
         control="matched non-review windows with the same global credit factor; reviews that "
                 "were DELAYED rather than completed, which share the anticipation and not the "
                 "outcome; and other programme countries reviewed the same month",
         evidence="HYPOTHESIS",
         notes="HONESTLY A WEAK EDGE AND SAID SO: Egypt is small relative to the global duration "
               "market, and the credit spread -- the whole Egypt-specific part -- is UNMEASURED "
               "on this account. It is seeded because the DATE GRID is exogenous and published, "
               "which is rare enough here to be worth testing even at low prior."),
    edge("eg_lng_flip_to_gas",
         source="Egyptian LNG loadings and cancellations at Idku and Damietta, and publicly "
                "reported import-cargo tenders",
         mechanism="Egypt has flipped between net LNG exporter and net importer as field output "
                   "declined and summer power demand grew; a flip changes the Mediterranean gas "
                   "balance by cargoes and reaches the desk's gas instrument through the "
                   "transatlantic basis",
         targets=("XNGUSD", "XBRUSD"),
         sign="Egypt shifting from exporter to IMPORTER -> tighter Atlantic-basin LNG -> upward "
              "pressure on the global gas complex, reaching XNGUSD only through the basis",
         lag="import tenders and loading cancellations are reported within days to weeks",
         horizon="ten to sixty sessions",
         control="THE BASIS ITSELF -- European gas prices and the US storage cycle as explicit "
                 "regressors. Without them this edge measures the US gas market and nothing "
                 "else; plus matched summers with equal Egyptian power demand",
         evidence="HYPOTHESIS",
         notes="XNGUSD IS HENRY HUB AND EGYPT PRICES OFF TTF AND BRENT-LINKED TERMS. The basis "
               "is a named weakness, carried in the control, and an Egypt-to-XNGUSD cell without "
               "it is measuring North America."),
    edge("eg_eid_import_surge_to_seasonal_demand",
         source="the Eid al-Fitr and Eid al-Adha windows, from `eg_eid_windows`, with their "
                "DECLARED_LUNAR_ESTIMATE status attached",
         mechanism="the Eid weeks are the largest annual swing in Egyptian import demand -- food "
                   "and livestock for the Adha sacrifice, gold for weddings and gifts -- and in "
                   "diaspora remittance inflow; the resulting FX demand widens the parallel "
                   "premium mechanically and the physical demand lands in grain and regional gold",
         targets=("WHEAT", "CORN", "XAUUSD"),
         sign="the four to six weeks running into an Eid window -> Egyptian import and gold "
              "demand UP and the parallel premium WIDER, with the grain leg concentrated ahead "
              "of Ramadan",
         lag="the buying precedes the window by weeks; the DATA STOPS during it",
         horizon="ten to forty sessions",
         control="THE LUNAR DRIFT IS THE CONTROL and it is a genuinely clean one: the same "
                 "Gregorian weeks in years where Eid falls elsewhere hold the solar seasonal "
                 "fixed while moving the lunar one; plus matched non-Eid weeks with the same "
                 "wedge, and randomised window placement within the year",
         evidence="HYPOTHESIS",
         notes="EVERY DATE IN THIS EDGE IS A DECLARED_LUNAR_ESTIMATE. A cell whose window "
               "overlaps one is DEFERRED until the Cabinet's gazette is read -- the desk refuses "
               "to trade a guessed Eid window, because being one day out swaps a session for a "
               "closure at both ends of the event."),
    edge("eg_egyptian_cotton_crop_to_cotton",
         source="Egyptian cotton planted area, crop reports and export volumes",
         mechanism="Egypt grows extra-long-staple cotton, a distinct quality tier whose supply "
                   "shifts the premium the ELS tier commands over upland -- and a large enough "
                   "shift in the premium changes substitution at the mill margin",
         targets=("COTTON",),
         sign="Egyptian ELS crop shortfall -> ELS premium UP -> some substitution demand into "
              "upland -> a WEAK upward pressure on the ICE upland contract",
         lag="planting decisions lead the crop by a season; export data lags by months",
         horizon="one to two quarters",
         control="world upland supply and Chinese mill demand as explicit regressors; and "
                 "matched seasons with the same upland balance and a normal Egyptian crop",
         evidence="HYPOTHESIS",
         notes="THE WEAKEST EDGE IN THE PACK AND LABELLED AS SUCH. The broker quotes UPLAND "
               "cotton and Egypt grows EXTRA-LONG-STAPLE: these are different fibres in "
               "different quality tiers, so the edge runs through a substitution link that may "
               "carry no signal at all, and Egypt's share of world cotton is small. Seeded "
               "because the mechanism is real and cheap to falsify, not because the prior is "
               "high -- and the control is written so that a null is informative."),
    edge("eg_stablecoin_premium_as_wedge_replicate",
         source="publicly discussed local premium on dollar stablecoins in Egypt, as PUBLIC "
                "COMMENTARY only",
         mechanism="a THIRD independent market pricing the same capital-control wedge that the "
                   "parallel quote and the gold premium price; three independent estimates of "
                   "one latent quantity is a far stronger object than any of them alone",
         targets=("BTCUSD", "XAUUSD"),
         sign="local stablecoin premium WIDENING alongside the parallel and gold premiums -> a "
              "confirmed wedge state; a premium that moves ALONE is a global crypto move and not "
              "an Egyptian one",
         lag="daily where commentary exists; coverage is uneven and episodic",
         horizon="five to thirty sessions",
         control="THE GLOBAL CRYPTO FACTOR AS AN EXPLICIT REGRESSOR -- without it this edge "
                 "measures BTCUSD; plus the gold and quote-derived premiums as the co-movement "
                 "test, and periods of equal global crypto volatility with no local premium",
         evidence="HYPOTHESIS",
         notes="PUBLIC COMMENTARY ONLY, pit_feasible=False, NO VENUE NAMED, SUBSCRIBED OR "
               "CRAWLED anywhere in this pack (universe mandate, 2026-08-18). The executable leg "
               "is the broker's own BTCUSD CFD. Egypt is the sharpest case in this civilization "
               "for stating that refusal explicitly, because the P2P stablecoin market genuinely "
               "IS a parallel FX channel and is exactly what an unconstrained researcher would "
               "reach for first."),
)

#: Derived, never hand-maintained. IN THIS PACK IT IS THE WHOLE TARGET SET: `OWN_PRICE` is empty,
#: so EVERY executable symbol any Egyptian mechanism reaches is a transmission target by
#: construction. The invariant restates the pack's defining fact as code -- if this tuple ever
#: shrinks by the size of an own-price set, somebody has quietly added an Egyptian instrument the
#: broker does not quote.
TRANSMISSION_TARGETS: tuple[str, ...] = tuple(sorted(
    {t for e in TRANSMISSION_EDGES_SEED for t in e["targets"]} - set(OWN_PRICE)))


# --------------------------------------------------------------------------- eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    era("eg_managed_peg", start="2017-01-01", end="2022-03-20",
        label="The post-2016 managed rate, stable to the eye and administered in fact",
        what_changed="after the November 2016 devaluation the pound settled into a narrow "
                     "administered range; measured volatility was near zero, the carry trade "
                     "into Egyptian bills rebuilt, and the CBE's repatriation mechanism made the "
                     "exit look guaranteed",
        invalidates="ANY volatility, drift or risk estimate for the pound from this window is "
                    "measuring a POLICY and not a market. A carry study that annualises this "
                    "period's realised volatility is pricing an option that the state was short "
                    "and the researcher did not know existed",
        notes="The era that makes every naive Egyptian backtest look excellent."),
    era("eg_devaluation_sequence", start="2022-03-21", end="2024-03-05",
        label="The step sequence -- March 2022, October 2022, January 2023",
        what_changed="three discrete devaluations in under a year as reserves, NFA and the "
                     "import queue made the defence unaffordable; the parallel premium widened "
                     "between each step and closed at each one",
        invalidates="a study pooling this window with the preceding peg is averaging a near-"
                    "constant with a series of jumps and will report a volatility that describes "
                    "neither; and an event study that treats the three steps as independent is "
                    "ignoring that each one failed to clear the market, which is why the next "
                    "was needed",
        notes="THE WINDOW IN WHICH THE SPREAD MECHANISM IS MOST VISIBLE."),
    era("eg_import_restrictions", start="2022-02-13", end="2022-12-29",
        label="The letter-of-credit regime -- the capital control that was never called one",
        what_changed="imports were required to be financed by letters of credit rather than "
                     "documentary collection, converting a commercial decision into a queue for "
                     "a bank FX allocation; billions of dollars of goods were stranded at ports "
                     "and the backlog persisted well past the rule's formal removal",
        invalidates="trade, import-volume and inflation studies that pool across these dates are "
                    "pooling a rationed economy with an unrationed one. The rule's imposition "
                    "and removal are GAZETTED AND DATED, which makes this the cleanest natural "
                    "experiment in the pack and a terrible thing to average over",
        notes="The backlog cleared over 2023-2024, so the ECONOMIC era outlasts the LEGAL one "
              "and the two boundaries are not the same date."),
    era("eg_float_2024", start="2024-03-06", end=None,
        label="The float, the 600bp hike, Ras El Hekma and the programme augmentation",
        what_changed="at an EXTRAORDINARY MPC meeting the CBE raised rates by 600bp and let the "
                     "pound move from roughly 30.9 to around 50 per dollar, closing almost the "
                     "whole parallel gap in one step. It was financed: the Ras El Hekma "
                     "agreement with ADQ in late February and the IMF programme augmentation "
                     "supplied the dollars to clear the backlog and the repatriation queue, "
                     "which is why this step held where earlier ones had not",
        invalidates="EVERYTHING. Volatility, the reaction function, the remittance channel, the "
                    "gold premium and the parallel spread are all different objects on either "
                    "side of this date. WHETHER THE FLOAT PERSISTS IS UNMEASURED -- the 1994 and "
                    "2016 'floats' both reverted to a de facto peg within about eighteen months, "
                    "so an open era here is a question and not a conclusion",
        notes="THE SENTINEL END DATE IN THE FRAMEWORK VIEW IS A FRAMEWORK REQUIREMENT AND NEVER "
              "A CLAIM. The pack's central open question lives in this row."),
    era("eg_red_sea_diversion", start="2023-12-01", end=None,
        label="The Red Sea diversion -- traffic leaves the canal for the Cape",
        what_changed="attacks on shipping in the southern Red Sea raised war-risk premia by an "
                     "order of magnitude; carriers re-routed round the Cape of Good Hope, Suez "
                     "transits and net tonnage fell sharply, and Egypt lost a large share of one "
                     "of its four hard-currency earners at the worst possible moment",
        invalidates="any Suez throughput, canal-revenue or freight relationship estimated across "
                    "this boundary is averaging a working chokepoint with a bypassed one. It is "
                    "also a shock to the EGYPTIAN EXTERNAL POSITION and therefore contaminates "
                    "reserve and devaluation studies that think they are about monetary policy",
        notes="The single cleanest natural experiment this pack has, and it is still open."),
    era("eg_dst_reinstated", start="2023-04-28", end=None,
        label="Daylight saving time reinstated -- a PURE MEASUREMENT-REGIME BREAK",
        what_changed="Law 24 of 2023 restored summer time from the last Friday of April 2023, "
                     "after DST had been abolished in 2014. Cairo now runs UTC+2 in winter and "
                     "UTC+3 in summer, so THE UTC TIME OF EVERY EGYPTIAN ANNOUNCEMENT, EGX "
                     "SESSION AND PUBLICATION MOVES TWICE A YEAR",
        invalidates="NOTHING ABOUT THE ECONOMY AND EVERYTHING ABOUT THE DATA. Any intraday or "
                    "session study that hard-codes a UTC offset is wrong for half of each year "
                    "after this date and right before it -- and the error is BLOCK-STRUCTURED by "
                    "season, so it correlates with everything seasonal and will not average out. "
                    "This is the only era in the pack that changes no behaviour and invalidates "
                    "results anyway, which is exactly why it is carried as an era",
        notes="Included so that a future session finds the boundary in the table instead of in a "
              "confusing result."),
    era("eg_imf_programme", start="2022-12-16", end=None,
        label="The Extended Fund Facility programme and its augmentation",
        what_changed="an IMF programme with exchange-rate flexibility as a condition, augmented "
                     "in March 2024 alongside the float; it imposed a published review calendar "
                     "and made Egypt's external position a matter of public staff reports",
        invalidates="policy-reaction estimates from the pre-programme period do not transfer: "
                    "the CBE is optimising against a conditionality it did not previously face. "
                    "It also CREATES the only exogenous date grid the pack has, so a study that "
                    "uses review dates outside this era has no events to use",
        notes="The programme's own documents are the single best source on Egypt's true FX "
              "position, which makes this era a data regime as much as a policy one."),
    era("eg_high_yield_certificates", start="2022-03-21", end=None,
        label="The high-yield certificate programmes as the standing liquidity-absorption tool",
        what_changed="after each step, state banks issued one- and three-year certificates far "
                     "above the policy corridor -- 18%, 22%, 23.5% and a 27%/23.5% pair around "
                     "the float -- to absorb pound liquidity that would otherwise chase dollars "
                     "or gold. Each issuance creates a DATED MATURITY that returns that "
                     "liquidity years later",
        invalidates="household hedging and gold-premium studies that ignore the competing pound "
                    "asset are missing the other side of the decision: the gold bid competes "
                    "with a 27% certificate, and the premium's behaviour around ISSUANCE and "
                    "around MATURITY should differ in sign",
        notes="The only Egyptian flow event whose date is known years in advance."),
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

    WHAT IT COST TO LEARN, in the neighbouring packs before this one was written: with no
    adapter, `build_pack(...)` returned a pack whose `fixing_conventions`, `settlement_"
    conventions`, `exchanges`, `policy_eras` and `transmission_edges_seed` were ALL EMPTY, and
    `check_pack` reported nine problems that looked like authoring mistakes and were not. The
    fields had been written correctly and then dropped in translation.
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

    WHY AN EXPLICIT ADAPTER RATHER THAN A CONVENIENT COINCIDENCE. `actors`, `domains` and
    `datasets` already match the lab's `ActorRow`, `DomainRow` and `DatasetRow` field for field,
    so they need nothing. `edge()`, `era()` and the convention dictionaries do NOT: a
    `TransmissionSeed` is keyed on `(to_country, asset)` and a single edge here names several
    targets, so ONE EDGE BECOMES SEVERAL SEEDS, and an `Era` carries only a name, a start, an end
    and free notes where `era()` carries the label, what changed and what a pooled study would be
    measuring. Everything the typed row has no field for is preserved in `notes` rather than
    dropped, and the open-ended eras take a sentinel end date because the framework's `Era`
    requires one -- THE SENTINEL IS A FRAMEWORK REQUIREMENT AND NEVER A CLAIM ABOUT WHEN THE ERA
    ENDS. That distinction matters more in this pack than in any other: `eg_float_2024` is open
    because whether the float persists is the department's central UNMEASURED question, and a
    sentinel read as a forecast would answer it by accident.

    TWO EGYPT-SPECIFIC TRANSLATIONS WORTH NAMING. `instruments` on the lab's Fixing and
    SettlementRule rows is fed from `OWN_PRICE`, WHICH IS EMPTY HERE -- correctly, because none of
    these conventions governs an instrument this desk can trade, and an empty tuple is the honest
    encoding of that rather than a bug. And `cot_currency` is the empty string because THERE IS
    NO CFTC CONTRACT ON THE EGYPTIAN POUND; the empty string is a measurement (L1.28a), not a
    placeholder waiting to be filled in.
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
                     "dst_rule": "egypt_dst_last_friday_april_to_last_thursday_october",
                     "instruments": OWN_PRICE,
                     "notes": "; ".join(f"{kk}={vv}" for kk, vv in v.items() if kk != "name")}
                    for k, v in FIXING_CONVENTIONS.items() if isinstance(v, dict))
    settle = tuple({"name": k, "kind": "month_end", "instruments": OWN_PRICE, "notes": str(v)}
                   for k, v in SETTLEMENT_CONVENTIONS.items())
    venues = tuple({"name": str(v.get("name") or k), "index_symbols": (),
                    "expiry_rule": str(v.get("expiry_rule") or ""),
                    "open_utc": "", "close_utc": "",
                    "notes": "; ".join(f"{kk}={vv}" for kk, vv in v.items() if kk != "name")}
                   for k, v in EXCHANGES.items() if isinstance(v, dict))
    every_day = tuple(sorted(d for tbl in _EG_HOLIDAYS.values() for d in tbl))
    return {"transmission_edges_seed": tuple(seeds), "policy_eras": eras,
            "fixing_conventions": fixings, "settlement_conventions": settle,
            "exchanges": venues,
            "holidays_rule": {"dates": every_day, "notes": str(HOLIDAYS_RULE["rule"])},
            "fiscal_year_end": "06-30",
            "export_economy": "chokepoint_and_services_exporter",
            "retail_leverage_regime": "not_applicable_no_local_instrument",
            "cot_currency": "",
            "positioning_sources": tuple(str(p["id"]) for p in POSITIONING_SOURCES),
            "source_classes": tuple(str(s["id"]) for s in SOURCE_CLASSES),
            "custom_miners": tuple(str(m["entry"]) for m in CUSTOM_MINERS),
            "miner_domains": {str(m["name"]): tuple(m["domain_ids"]) for m in CUSTOM_MINERS},
            "mission": "mine Egypt to exhaustion as an exogenous CHOKEPOINT, IMPORT-BILL and "
                       "CAPITAL-CONTROL sensor for the crude, grain, gold and frontier-FX "
                       "instruments the desk already trades -- a country with no price of its "
                       "own, measured entirely through what it does to other people's prices"}


def pack() -> Any:
    """The Egypt country pack. `CountryPack` when the framework has landed, else a dict."""
    return build_pack(**{**spec(), **framework_rows()})


def priority_weight() -> float:
    """This pack's share of the opening African compute ladder. A PRIOR, replaced by survivors."""
    return PRIORITY_WEIGHT


def instrument_report(path: Any = None) -> dict[str, Any]:
    """What this pack can trade, what carries its economics and what is missing, MEASURED against
    the broker registry rather than asserted.

    `own_price` IS EMPTY AND `transmission_only` IS TRUE, and both are computed rather than
    asserted so that the pack's defining fact survives a future edit. If somebody adds an
    Egyptian instrument to `OWN_PRICE` that the broker does not quote, `absent_from_universe`
    names it and the flag flips -- which is the point of measuring instead of declaring.
    """
    split = resolve(EXECUTABLE_INSTRUMENTS, path)
    return {"code": CODE, "own_price": OWN_PRICE, "executable": tuple(split["tradable"]),
            "equities_refused": tuple(split["equities"]),
            "absent_from_universe": tuple(split["absent"]),
            "transmission_only": not OWN_PRICE,
            "transmission_targets": TRANSMISSION_TARGETS,
            "named_absent_instruments": ABSENT_INSTRUMENTS,
            "priority_weight": PRIORITY_WEIGHT,
            "source_layers": source_layer_report(),
            "dataset_fields": DATASET_FIELDS}
