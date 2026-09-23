"""THE COPPERBELT -- DR Congo and Zambia: the marginal tonne of world copper, and a state that
turned the cobalt tap off on a published date.

WHY TWO JURISDICTIONS IN ONE PACK, AND WHY THESE TWO. They are not "two African mining countries".
They are ONE OREBODY with a border drawn across it. The Katangan copper arc runs from Kolwezi
through Likasi and Lubumbashi, crosses the frontier at KASUMBALESA, and continues through
Chililabombwe, Chingola, Kitwe and Ndola. The same rock, the same smelters buying each other's
concentrate, the same lorries, the same four roads to the sea, and the same Chinese buyer at the
end of all of them. Splitting them would split a mechanism, and a study that tests one without the
other is controlling for nothing.

THE SIZE OF THE THING, WHICH IS WHY IT IS ONE OF THE HIGHEST-VALUE PACKS ON THE BOARD:

  * THE DRC IS THE WORLD'S SECOND-LARGEST COPPER PRODUCER. It passed PERU in 2023-2024 -- roughly
    three million tonnes a year and still rising on Kamoa-Kakula's phased ramp and on CMOC's TFM
    and KFM expansions -- and it is the source of about SEVENTY TO SEVENTY-FIVE PER CENT OF WORLD
    COBALT. Zambia is Africa's second producer at roughly seven to eight hundred thousand tonnes
    with a published national target of three million.
  * BETWEEN THEM THEY ARE THE MARGINAL TONNE, and the broker quotes the instrument DIRECTLY as
    XCUUSD. This is not a pack that has to route a domestic mechanism through a proxy to reach a
    price: the physical series and the tradable contract are the same substance.
  * AND ESSENTIALLY NO SYSTEMATIC DESK MODELS THEM. Chile and Peru are covered by every copper
    analyst alive; the Copperbelt's published series -- a daily lake level, a border queue, a
    monthly royalty receipt, an export quota -- are read by specialists and by nobody with a
    statistical programme attached.

THE FIVE MECHANISMS THAT EARN THE TRIAL BUDGET. Each is published, dated and price-relevant, and
each is a DOMAIN of its own rather than a sentence inside a generic frontier domain:

  1. THE COBALT EXPORT BAN OF FEBRUARY 2025 AND THE QUOTA REGIME THAT REPLACED IT. ARECOMS, the
     DRC's strategic-minerals regulator, suspended cobalt exports outright with effect from
     2025-02-22 to defend a collapsed price, extended the suspension in June, and replaced it with
     an export QUOTA from 2025-10-16. That is a dated, published, SOVEREIGN SUPPLY INTERVENTION in
     a commodity whose price its own share of world output directly controls. It reaches XCUUSD
     because COBALT IS A BY-PRODUCT: it comes out of the same Katangan copper ore and out of
     nickel sulphide elsewhere, so a cobalt price collapse or a cobalt export ban changes the
     economics of a COPPER mine and the incentive to mine copper at all. CB-A is built on it.
  2. THE LOGISTICS ARE THE MECHANISM. Landlocked copper reaches the sea by exactly FOUR routes,
     each with published throughput and each with a distinct failure mode: the Durban corridor
     through Kasumbalesa, Chirundu and BEITBRIDGE (an interaction with `za`); the DAR ES SALAAM
     Central Corridor by road through Nakonde-Tunduma and by TAZARA rail (an interaction with
     `east_africa`, which owns the Tanzanian port end); BEIRA and NACALA through Mozambique; and
     the LOBITO CORRIDOR through Angola, whose Benguela railway was conceded in 2023 and carried
     Congolese copper to the Atlantic again in 2024 under a US-backed arrangement. That is a dated,
     published change in WHERE Central African copper physically goes, and queue lengths at
     Kasumbalesa are reported in kilometres. CB-K and CB-L are built on it.
  3. ZAMBIAN POWER IS COPPER SUPPLY. Copper smelting and electrowinning are electricity in
     physical form. ZESCO's Kariba hydro generation collapsed in the 2024 drought -- declared a
     national disaster on 2024-02-29 -- smelters were load-shed on a published schedule, and the
     ZAMBEZI RIVER AUTHORITY PUBLISHES THE LAKE LEVEL DAILY. A daily, public, physically causal
     input to a material share of world copper smelting, trading against a liquid contract, is
     exactly the kind of cell this desk exists to test. CB-F is built on it.
  4. THE FISCAL AND FX SEQUENCE, DATED ON BOTH SIDES. Zambia missed the coupon due 2020-10-14 and
     defaulted when the grace period expired on 2020-11-13 -- the first COVID-era sovereign
     default -- took an IMF Extended Credit Facility on 2022-08-31, reached an Official Creditor
     Committee agreement in June 2023 and exchanged its eurobonds in June 2024. The KWACHA is one
     of the most copper-correlated currencies on earth and the Bank of Zambia publishes its
     interventions and its STATUTORY RESERVE RATIO changes. The other half is Congolese: the CDF,
     a dollarisation above eighty per cent of deposits, and the BCC's taux directeur. CB-D, CB-H
     and CB-I are built on them.
  5. THE OWNERSHIP RESHUFFLE. Zambia's two largest legacy assets changed hands inside eighteen
     months -- ZCCM-IH sold 51% of Mopani to International Resources Holding in March 2024 and
     Vedanta regained control of Konkola Copper Mines after the liquidation was withdrawn -- while
     the DRC's 2018 Mining Code, its 10% strategic-substance royalty on cobalt, its subcontracting
     regulator ARSP and the renegotiated Sicomines infrastructure-for-minerals deal rewrote who
     keeps the rent. Those are dated legal facts with measurable output consequences. CB-C and
     CB-G are built on them.

THE CURRENCIES ARE BOTH ABSENT AND THE PACK SAYS SO TWICE. CDF and ZMW are not in
`data/universe/universe.json` and never will be. Each is named in `TRANSMISSION_TARGETS` with its
regime, its parallel or bureau spread and the broker symbols its economics route into, so an
absent instrument produces a transmission hypothesis and never a cell that can never be filled
(L1.49). THE ZAR COMPLEX IS A PROXY AND IS LABELLED ONE EVERYWHERE. USDZAR, EURZAR, GBPZAR and
ZARJPY are the executable carrier of Southern African risk; the rand contains South African
idiosyncratic risk that neither of these economies has, every edge that routes through it names
its control, and no row in this file calls the carrier "the currency".

COBALT IS NOT A BROKER SYMBOL EITHER, AND THE ROUTE IS EXPLICIT. There is no cobalt contract in
the registry. Cobalt enters this pack as a COPPER AND NICKEL BY-PRODUCT: a cobalt price collapse
removes a credit from the Katangan copper cost curve and removes the reason to mine some ore at
all, and it removes the same credit from nickel sulphide producers, so every cobalt mechanism here
terminates in XCUUSD and XNIUSD with the control named -- the Indonesian nickel-cobalt ramp, which
is the competing supply and the reason the price fell in the first place.

THE GROUND IS FRENCH AND AN ENGLISH-ONLY CRAWL READS A TRANSLATION OF IT. The DRC's official
language is FRENCH: its Journal Officiel, its Code minier, the Ministere des Mines and the Banque
Centrale du Congo all publish in French and only sometimes in English. KATANGA WORKS IN SWAHILI --
Congolese Swahili is the lingua franca of Haut-Katanga and Lualaba, which is where the copper is --
and Kinshasa argues in LINGALA. Zambia legislates in ENGLISH, which is the trap on the other side:
an English crawl returns something for every Zambian query and reads complete, while the Copperbelt
press and the farmgate and load-shedding vocabulary run in BEMBA and NYANJA. The terminology table
and every source class's queries are written in those languages for exactly that reason.

THE TWO-LANE ORDER (2026-09-06) BINDS HARD HERE. The tempting names are all single companies --
the Katangan operators, the Zambian mines, the state holding company, the listed cement and
brewing counters on the Lusaka exchange -- and every one appears in this pack as an ACTOR and
never as an instrument. No share CFD appears in any instrument tuple in this file.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Any

# --------------------------------------------------------------------------- identity
CODE = "copperbelt"
NAME = "The Central African Copperbelt (DR Congo, Zambia)"
REGION_COMMAND = "africa"
REGION_DESK = "AFRICA"
FOREST = "africa"

#: THE TWO COUNTRIES THIS PACK ANSWERS FOR. `scripts/check_regional_parity.py::jurisdictions_of`
#: reads this tuple and nothing else, so a pack that answers two countries and declares one is
#: credited with one. Neither CD nor ZM was on any forest's roster before this pack landed.
JURISDICTIONS: tuple[str, ...] = ("cd", "zm")

#: The pack-level currency is the Congolese franc, because the DRC is the larger producer and the
#: larger regime story; the framework carries ONE currency per pack, so both are declared here and
#: both are absent from the broker (see TRANSMISSION_TARGETS).
CURRENCY = "CDF"
CURRENCIES: dict[str, str] = {
    "cd": "CDF",   # Congolese franc -- managed float, dollarised above 80% of deposits
    "zm": "ZMW",   # Zambian kwacha -- free float, the most copper-correlated currency on earth
}

#: BOTH RUN A CALENDAR FISCAL YEAR, which is unusual enough in this desk's roster to be worth
#: saying: the DRC's Loi de finances is enacted in December for a 1 January start, and Zambia
#: moved to a calendar year in 2013 with the Budget Address delivered to the National Assembly at
#: the end of September. The mining royalty, the export levy and the power tariff are all BUDGET
#: instruments, so the September-to-December window is when this pack's rules change.
FISCAL_YEAR_END = "12-31"
FISCAL_YEAR_ENDS: dict[str, str] = {
    "cd": "12-31 (the Loi de finances is tabled in the autumn and promulgated in December for a "
          "1 January start; the Journal Officiel carries the enacted text)",
    "zm": "12-31 (the Budget Address is delivered to the National Assembly at the end of "
          "September for a 1 January start, and the Finance Act follows in December)",
}

NATIVE_LANGUAGES: tuple[str, ...] = ("fr", "sw", "ln", "en", "bem", "ny")
COT_CURRENCY = ""            # no CFTC contract exists for CDF or ZMW
EXPORT_ECONOMY = "commodity_exporter"
RETAIL_LEVERAGE_REGIME = "restricted"
MISSION = ("mine the Central African Copperbelt as the single orebody with two treasuries that it "
           "is: the DRC's February 2025 cobalt export suspension and the October 2025 quota "
           "regime that replaced it, the Kamoa-Kakula and TFM/KFM ramps that made the DRC the "
           "world's number two copper producer, the four export corridors and the Lobito "
           "reopening that changed where the metal physically goes, the Kasumbalesa border queue, "
           "the DAILY Kariba lake level and the ZESCO load-shedding schedule that is a smelter "
           "constraint in physical form, Zambia's 2020 default and Common Framework "
           "restructuring, the kwacha's copper beta and the Bank of Zambia's statutory reserve "
           "ratio, the DRC's 2018 Mining Code and its ARSP subcontracting regime, and the "
           "Chinese offtake that stands at the end of every one of those roads")

#: The instruments this pack may compile a cell against. Every one is in the broker registry, none
#: is a single-name equity, and each carries the mechanism that put it here. The ZAR crosses are
#: PROXIES and are labelled as such wherever they are used.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "XCUUSD",                         # THE instrument: these two countries are the marginal tonne
    "XAUUSD",                         # Kibali, Twangiza and the artisanal gold of the east
    "XZNUSD",                         # Kabwe and Kipushi: the Copperbelt's zinc-lead half
    "XPBUSD",                         # Kabwe lead, and the Kipushi restart's by-product
    "XNIUSD",                         # the OTHER cobalt host: the Indonesian control leg
    "XALUSD",                         # the power-intensive metals complex and smelter energy
    "USDZAR", "EURZAR", "GBPZAR",     # PROXY: the executable carrier of Southern African risk
    "ZARJPY",                         # PROXY: the same carrier's risk-appetite leg
    "USDCNH",                         # China is the buyer at the end of all four corridors
    "CORN", "WHEAT",                  # the drought that empties Kariba also empties the maize crop
    "SUGAR",                          # Nakambala and Kwilu: the irrigated-cane leg of the drought
    "XBRUSD",                         # the corridor's own diesel bill, 3,000 km each way
    "XNGUSD",                         # Lake Kivu methane and the gas-versus-hydro generation leg
    "US500",                          # the frontier risk-appetite channel
)

#: WHAT THIS PACK CANNOT TRADE, NAMED. Two currencies, one commodity that is the pack's headline
#: mechanism, one exchange, one sovereign credit and one power system. Each row carries the broker
#: symbols its economics route into; a proxy is a CARRIER and never a substitute, and every edge
#: that uses one says so on its face.
TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "CDF -- the Congolese franc under a dollarised managed float",
     "venue": "Banque Centrale du Congo and the commercial banks' interbank market, Kinshasa",
     "regime": "MANAGED FLOAT with heavy intervention. More than eighty per cent of bank deposits "
               "and the great majority of broad money are in FOREIGN CURRENCY, so the exchange "
               "rate is a price level and not only a price: the franc depreciated sharply through "
               "2023 and was steadied in 2024-2025 by sales of reserves and a high taux directeur",
     "parallel_market": "the street and bureau rate in Kinshasa and Lubumbashi runs at a visible "
                        "spread to the BCC's indicative rate; the spread widens with fuel and "
                        "import stress and is reported in the Kinshasa press rather than measured",
     "route": "the franc is NOT the mechanism and the pack refuses to pretend it is. Mining "
              "receipts are dollars, mining costs are largely dollars, and the domestic price "
              "level is a dollar price level; the CDF is a STATE that conditions fiscal and "
              "social stress in CB-D and never a cell of its own",
     "why": "absent from the broker and not deliverable offshore; every CDF mechanism here "
            "terminates in XCUUSD, XAUUSD or the ZAR carriers",
     "proxy_warning": "USDZAR IS A PROXY AND NOT THE CURRENCY. The rand carries South African "
                      "idiosyncratic risk -- Eskom, the SARB, the domestic bond market -- that "
                      "the Congolese franc does not, and every edge routing through it must "
                      "control for the SARB decision calendar and for South African data days",
     "proxies": ("XCUUSD", "XAUUSD", "USDZAR")},
    {"name": "ZMW -- the Zambian kwacha, the most copper-correlated currency on earth",
     "venue": "Bank of Zambia interbank market, Lusaka",
     "regime": "FREE FLOAT with published intervention. The Bank of Zambia runs a policy rate set "
               "quarterly by its Monetary Policy Committee and uses the STATUTORY RESERVE RATIO "
               "as a second, blunter instrument -- raising it drains kwacha liquidity and defends "
               "the currency, and the changes are announced by circular",
     "parallel_market": "no material parallel market: Zambia has had an open capital account "
                        "since the 1990s, which is exactly what makes it the CONTROL jurisdiction "
                        "for the DRC's dollarisation",
     "route": "the kwacha's copper beta is the cleanest published FX-commodity relation in "
              "sub-Saharan Africa, and it runs in the direction this pack cannot trade: copper "
              "moves the kwacha, not the reverse. The kwacha is therefore a CONFIRMING observable "
              "for a Zambian supply or fiscal shock and never the leg that carries it",
     "why": "absent from the broker; ZMW mechanisms terminate in XCUUSD and the ZAR carriers",
     "proxy_warning": "the ZAR complex is the CARRIER; the kwacha has a copper beta the rand does "
                      "not, and conflating them is how a copper story becomes a South African one",
     "proxies": ("XCUUSD", "USDZAR", "EURZAR")},
    {"name": "COBALT -- the pack's headline mechanism, and there is no contract for it",
     "venue": "the LME cobalt contract is thin and the traded price of record is a price-reporting "
              "agency assessment; neither is in the broker registry",
     "regime": "ADMINISTERED SUPPLY SINCE 2025-02-22. The DRC suspended exports outright, extended "
               "the suspension in June 2025, and replaced it with an export QUOTA from "
               "2025-10-16; roughly seventy to seventy-five per cent of world supply is Congolese",
     "parallel_market": "artisanal cobalt is bought at depots and through the state channel; the "
                        "depot price is reported by NGOs and the trade press, never published",
     "route": "COBALT IS A BY-PRODUCT AND THAT IS THE WHOLE ROUTE. Katangan cobalt comes out of "
              "COPPER ore and the rest of the world's comes out of NICKEL sulphide, so the cobalt "
              "price is a CREDIT on the copper and nickel cost curves. A cobalt collapse removes "
              "that credit, raises the effective cost of the copper tonne that carries it and "
              "makes some ore uneconomic; an export ban removes the revenue entirely while the "
              "copper keeps moving. Every cobalt mechanism here terminates in XCUUSD and XNIUSD",
     "why": "no cobalt CFD exists anywhere in data/universe/universe.json",
     "control": "THE INDONESIAN NICKEL-COBALT RAMP, which is the competing supply and the reason "
                "the price fell in the first place: a Congolese intervention that moves the price "
                "when Indonesian output is flat is a DRC event, and one that moves it when "
                "Indonesian output is also moving is a market event with a Congolese headline",
     "proxies": ("XCUUSD", "XNIUSD")},
    {"name": "The Lusaka Securities Exchange (LuSE all-share and its mining counters)",
     "venue": "LuSE, Lusaka",
     "regime": "a small frontier exchange, thin and dominated by a handful of counters; foreign "
               "participation is unrestricted but liquidity is not",
     "parallel_market": "n/a",
     "route": "no CFD is quoted; the index level and the turnover are a frontier risk STATE and "
              "the executable leg is the ZAR carrier and US500",
     "why": "absent from the broker registry",
     "proxy_warning": "an index that a single block can move is a sentiment reading, not a price",
     "proxies": ("USDZAR", "US500")},
    {"name": "THE DRC HAS NO SECURITIES EXCHANGE AT ALL, and that is the measurement",
     "venue": "none",
     "regime": "there is no Congolese stock exchange, no public bond curve and no domestic "
               "securities tape of any kind; the sovereign borrows from the BCC, from banks and "
               "from bilateral and multilateral creditors",
     "parallel_market": "n/a",
     "route": "the institutional layer for Congolese SECURITIES is declared absent by name in "
              "NO_LAWFUL_GROUND rather than filled with the Zambian exchange next door",
     "why": "nothing to quote and nothing to read",
     "proxy_warning": "USDZAR IS A PROXY FOR FRONTIER RISK APPETITE AND NOTHING MORE. It is not a "
                      "Congolese asset, there is no Congolese asset, and an edge that routes a "
                      "Congolese institutional event through the rand must control for the SARB "
                      "calendar and for South African data days or it is measuring South Africa",
     "proxies": ("USDZAR",)},
    {"name": "Zambian sovereign credit: the defaulted eurobonds and the restructured claim",
     "venue": "the international bond market",
     "regime": "DEFAULT from 2020-11-13, an IMF Extended Credit Facility from 2022-08-31, an "
               "Official Creditor Committee agreement in June 2023 and a completed eurobond "
               "exchange in June 2024; the restructured instruments trade offshore",
     "parallel_market": "n/a",
     "route": "the broker quotes UKGILT, UST05Y and UST10Y and no frontier credit; the default "
              "and the restructuring milestones are read as RISK-CHANNEL events on the carriers",
     "why": "absent from the broker registry",
     "proxy_warning": "THE CARRIER IS NOT THE CREDIT. The rand is a liquid, freely traded "
                      "currency and a restructured frontier claim is neither; every edge that "
                      "reads a Zambian milestone off USDZAR must control for the SARB calendar "
                      "and for US CPI and FOMC days, which is how 'the frontier repriced' is told "
                      "from 'the dollar repriced'",
     "proxies": ("USDZAR", "US500")},
    {"name": "ZESCO generation, the Kariba lake level and the Southern African Power Pool",
     "venue": "Zambezi River Authority (the lake), ZESCO (generation and load management), SAPP "
              "(the regional day-ahead and balancing markets)",
     "regime": "an administered tariff with published load-shedding schedules; the lake level is "
               "published DAILY and the usable storage above the minimum operating level is the "
               "binding constraint on generation",
     "parallel_market": "mines contract imported power through SAPP and through bilateral deals "
                        "at prices well above the domestic tariff; the premium is reported",
     "route": "power is COPPER SUPPLY in physical form -- smelting and electrowinning are "
              "electricity -- so the lake level and the load-shedding hours condition XCUUSD "
              "directly and condition XALUSD as the wider power-intensive-metals leg",
     "why": "no power or water-level contract exists in the broker registry",
     "proxies": ("XCUUSD", "XALUSD", "XNGUSD")},
    {"name": "MAIZE and the Zambian Food Reserve Agency floor price",
     "venue": "the FRA's announced purchase price and the Zambian Commodity Exchange",
     "regime": "an administered floor price announced each marketing season, with export "
               "restrictions imposed and lifted by statutory instrument",
     "parallel_market": "cross-border maize movement into the DRC's Katanga is continuous and "
                        "reported rather than measured; the Copperbelt eats Zambian maize",
     "route": "the same drought that empties Kariba empties the maize crop, so CORN is a WEAK "
              "carrier of the Zambian drought state and the pack labels it weak",
     "why": "no Zambian maize contract exists; CORN is the world price and not the local one",
     "proxies": ("CORN", "WHEAT")},
)

# --------------------------------------------------------------------------- central banks
#: THE PACK CARRIES ONE `CENTRAL_BANK` BECAUSE THE FRAMEWORK DOES, and two is the truth. The
#: Banque Centrale du Congo is the primary because the DRC is the larger producer and because its
#: dollarisation is the more distinctive regime; the Bank of Zambia is declared beside it in
#: `CENTRAL_BANKS` with its own framework, and a study that pools the two is pooling a dollarised
#: managed float with an open-capital-account free floater.
CENTRAL_BANK: dict[str, Any] = {
    "name": "Banque Centrale du Congo (BCC)",
    "framework": "managed_float",
    "policy_instrument": "the TAUX DIRECTEUR set by the Comite de Politique Monetaire, alongside "
                         "reserve requirements in both francs and foreign currency, BCC bill "
                         "issuance and direct sales of foreign exchange to the market",
    "mandate": "price stability and the stability of the franc under the 2018 loi organique on "
               "the Banque Centrale du Congo; there is no published numeric inflation target of "
               "the kind an inflation targeter would announce, so a 'surprise' measured against "
               "an invented target is a measurement of the invention",
    "decision_rule": "the Comite de Politique Monetaire meets on a published schedule and the "
                     "decision is announced with a communique on bcc.cd, in French",
    "decision_calendar_rule": "scheduled CPM meetings announced at bcc.cd, with off-cycle "
                              "decisions when the franc moves; the taux directeur was raised "
                              "sharply in 2023 to defend the currency and eased in steps after",
    "decision_dates": (),
    "dates_status": "NOT LISTED, deliberately. The CPM calendar is published in French on the "
                    "bank's own site and the communiques are posted without a pinned minute; this "
                    "pack refuses to type a date it cannot cite (L1.28a). The dated events CB-D "
                    "is built on are the taux directeur moves themselves and the IMF ECF review "
                    "Board dates, all of which are citable.",
    "decision_time_utc": "13:00",
    "announce_local": "Kinshasa is UTC+1 (WAT) and LUBUMBASHI IS UTC+2 (CAT) -- the DRC spans two "
                      "time zones, the central bank and the gazette sit in the western one and "
                      "THE COPPER SITS IN THE EASTERN ONE, which is a real and easily-missed "
                      "hour of slippage between a Kinshasa announcement and a Katangan operation",
    "dst_rule": "none: neither zone observes daylight saving, so every window here is stable in "
                "UTC all year",
    "minutes_lag_days": 0,
    "publication_classes": ("cpm_communique", "taux_directeur", "condensé_hebdomadaire",
                            "rapport_annuel", "taux_de_change_indicatif", "reserves"),
    "policy_rate_series": "BCC:taux_directeur",
    "expected_rate_series": "UNMEASURED",
    "consensus_proxy": "the BCC bill auction rate and the interbank franc rate; there is no "
                       "published survey of economists for the DRC",
    "consensus_proxy_trap": "the domestic franc market is small next to the dollarised economy "
                            "around it, so a franc rate is a price in a thin corner of a mostly "
                            "dollar system and is not the cost of capital of a Katangan mine",
    "reserves_clock": "gross reserves are published in the bank's weekly condense and in the IMF "
                      "programme documents; the programme reviews are the reliable dated stamp",
    "programme": "an IMF Extended Credit Facility ran from 2021 and a successor arrangement was "
                 "agreed in 2024-2025; the reviews are a DISBURSING clock and the staff reports "
                 "carry the reserve, arrears and mining-revenue numbers the state publishes late",
    "off_cycle": ("2023 the taux directeur is raised sharply to defend the franc",
                  "2025-02-22 ARECOMS suspends cobalt exports -- a MINING decision with a direct "
                  "consequence for the export receipts the BCC's reserves are built from"),
    "root": "https://www.bcc.cd",
}

#: The other one, declared rather than folded away. Zambia is the CONTROL jurisdiction for
#: everything monetary in this pack: an open capital account, a free float and a published policy
#: rate against a dollarised managed float next door.
CENTRAL_BANKS: dict[str, dict[str, Any]] = {
    "cd": {"name": "Banque Centrale du Congo", "framework": "managed_float",
           "rate": "the taux directeur, set by the Comite de Politique Monetaire",
           "root": "https://www.bcc.cd",
           "why": "a dollarised economy in which more than eighty per cent of deposits are in "
                  "foreign currency, so the policy rate steers a thin domestic franc market and "
                  "the exchange rate does the work a policy rate does elsewhere"},
    "zm": {"name": "Bank of Zambia (BoZ)", "framework": "managed_float",
           "rate": "the BoZ Policy Rate, announced quarterly by the Monetary Policy Committee, "
                   "with the STATUTORY RESERVE RATIO as a second and blunter instrument",
           "root": "https://www.boz.zm",
           "why": "an open capital account, a free float and a published quarterly decision -- "
                  "the CONTROL leg for the DRC's dollarisation, and the only one of the two with "
                  "a decision clock a surprise can be measured against"},
}

# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "Bank of Zambia interbank mid-rate and the daily intervention print",
     "local": "published each business day, Africa/Lusaka (UTC+2)",
     "time_utc": "08:00", "time_utc_dst": "08:00",
     "dst_rule": "none: Central Africa Time is UTC+2 year-round",
     "instruments": ("XCUUSD", "USDZAR"), "window_minutes": 60,
     "why": "the kwacha's daily mark, and the series whose copper beta is the cleanest published "
            "FX-commodity relation in sub-Saharan Africa"},
    {"name": "Banque Centrale du Congo taux de change indicatif",
     "local": "published each business day, Africa/Kinshasa (UTC+1)",
     "time_utc": "08:00", "time_utc_dst": "08:00", "dst_rule": "none",
     "instruments": ("XCUUSD", "XAUUSD"), "window_minutes": 60,
     "why": "the rate customs values against and the rate the street rate is quoted as a spread "
            "to; the gap between the two is the import-stress state CB-D conditions on"},
    {"name": "LME official settlement and the copper price of record",
     "local": "the second ring session, Europe/London", "time_utc": "12:45", "time_utc_dst":
        "11:45", "dst_rule": "GMT/BST", "instruments": ("XCUUSD", "XZNUSD", "XPBUSD", "XNIUSD"),
     "window_minutes": 20,
     "why": "every Congolese and Zambian offtake contract prices off the LME monthly average, so "
            "this is the price the physical contracts settle against and the one a producer "
            "country's intervention has to move to matter"},
    {"name": "Shanghai copper close and the bonded-premium reference",
     "local": "the SHFE afternoon session close, Asia/Shanghai", "time_utc": "07:00",
     "time_utc_dst": "07:00", "dst_rule": "none",
     "instruments": ("XCUUSD", "USDCNH"), "window_minutes": 30,
     "why": "China is the buyer at the end of all four corridors; the Shanghai close and the "
            "bonded premium are where Congolese and Zambian tonnes are actually absorbed, and the "
            "Asian session runs BEFORE the LME ring, which is the sequence any lead claim needs"},
    {"name": "Zambezi River Authority daily Kariba lake level reading",
     "local": "read at the dam wall and published the same day, Africa/Lusaka",
     "time_utc": "06:00", "time_utc_dst": "06:00", "dst_rule": "none",
     "instruments": ("XCUUSD", "XALUSD"), "window_minutes": 120,
     "why": "THE DAILY PHYSICAL SERIES OF THIS PACK. Usable storage above the minimum operating "
            "level is the binding constraint on Kariba generation, generation is smelter power, "
            "and smelter power is copper supply -- a daily public number on a liquid contract"},
    {"name": "LBMA gold price PM auction",
     "local": "15:00 Europe/London", "time_utc": "15:00", "time_utc_dst": "14:00",
     "dst_rule": "GMT/BST", "instruments": ("XAUUSD",), "window_minutes": 15,
     "why": "the reference for Congolese gold: Kibali and Twangiza are industrial, and the "
            "artisanal east's declared and undeclared exports are valued against the same fix"},
    {"name": "Lusaka Securities Exchange closing session",
     "local": "early afternoon, Africa/Lusaka", "time_utc": "11:00", "time_utc_dst": "11:00",
     "dst_rule": "none", "instruments": ("USDZAR", "US500"), "window_minutes": 30,
     "why": "the domestic close; no LuSE CFD exists, so the frontier carrier takes the leg and "
            "the index is registered as a risk STATE rather than as a price"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "Bank of Zambia Treasury bill and bond auctions", "kind": "weekday",
     "weekday": 3, "roll": "next", "window_utc": ("07:00", "13:00"),
     "instruments": ("XCUUSD", "USDZAR"),
     "why": "weekly bills on a Thursday and periodic bonds; the cut-off and the bid-to-cover are "
            "the domestic appetite for kwacha paper against dollars, and after the 2020 default "
            "the domestic market is where the sovereign actually funds itself"},
    {"name": "Bank of Zambia Monetary Policy Committee quarterly decision", "kind": "quarter_end",
     "roll": "next", "window_utc": ("09:00", "14:00"), "instruments": ("USDZAR", "XCUUSD"),
     "why": "the MPC meets quarterly and the statement carries the inflation forecast revision; "
            "it is the ONLY scheduled policy clock in this pack that a surprise can be measured "
            "against, which is why Zambia is the control leg for the DRC"},
    {"name": "Mining royalty and mineral-export duty payment dates", "kind": "day_of_month",
     "days": (14,), "roll": "next", "window_utc": ("06:00", "14:00"),
     "instruments": ("XCUUSD", "USDZAR"),
     "why": "royalty on mineral output is assessed monthly on the LME-referenced value and paid to "
            "the revenue authority in the following month; the receipts series is the state's own "
            "count of the tonnes that left, and it is published"},
    {"name": "LME monthly average pricing (MAMs) on offtake contracts", "kind": "month_end",
     "roll": "previous", "window_utc": ("11:00", "17:00"),
     "instruments": ("XCUUSD", "XZNUSD", "XPBUSD"),
     "why": "Katangan and Zambian offtake prices off the LME MONTHLY AVERAGE, so month-end is "
            "when a producer's realised price is fixed and when hedging pressure concentrates -- "
            "a settlement mechanic, not a story"},
    {"name": "Zambian Budget Address and the Finance Act commencement", "kind": "fiscal_year_end",
     "roll": "next", "window_utc": ("10:00", "18:00"),
     "instruments": ("XCUUSD", "USDZAR", "CORN"),
     "why": "the mineral royalty scale, its deductibility against corporate income tax, the "
            "export duties and the power tariff are all BUDGET instruments; the address is at the "
            "end of September, the Act follows in December and the change commences on 1 January"},
    {"name": "DRC Loi de finances promulgation and the January commencement",
     "kind": "fiscal_year_end", "roll": "next", "window_utc": ("09:00", "17:00"),
     "instruments": ("XCUUSD", "XAUUSD"),
     "why": "the Congolese fiscal year is the calendar year; the mining fiscal regime sits partly "
            "in the 2018 Code minier and partly in the annual finance law, and the Journal "
            "Officiel is the citation for both"},
    {"name": "Quarter-end IMF programme review and disbursement dates", "kind": "quarter_end",
     "roll": "previous", "window_utc": ("13:00", "20:00"), "instruments": ("USDZAR", "US500"),
     "why": "both countries run IMF arrangements; the Board dates are the risk-channel clock of "
            "CB-H and the only place several of their fiscal series are published on time"},
)

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Lusaka Securities Exchange (LuSE) -- the all-share index and its mining counters",
     "index_symbols": (),
     "open_local": "10:00", "close_local": "13:00", "open_utc": "08:00", "close_utc": "11:00",
     "dst_rule": "none: Africa/Lusaka is UTC+2 year-round",
     "session_status": "PRESS_REPORTED: the exchange publishes its own trading hours and this row "
                       "carries the commonly-reported late-morning continuous session; the bell "
                       "is to be confirmed against luse.co.zm before any intraday cell",
     "auction": "a thin continuous session; the exchange is small enough that a single block can "
                "set the day, which is why the index is a STATE here and never a price",
     "expiry_rule": "no listed derivatives of any kind; there is no expiry clock to mine",
     "holidays": "the Zambian national calendar including the Easter weekend and the declared "
                 "one-off closures",
     "notes": "NO CFD IS QUOTED on the LuSE all-share. The readable thing is TURNOVER and the "
              "foreign participation share, both of which turn with the frontier risk regime and "
              "with the copper price, and neither of which this desk can trade"},
    {"name": "THE DRC HAS NO SECURITIES EXCHANGE", "index_symbols": (),
     "open_local": "", "close_local": "", "open_utc": "", "close_utc": "",
     "dst_rule": "n/a",
     "auction": "none: there is no Congolese stock exchange, no public bond curve and no domestic "
                "securities tape",
     "expiry_rule": "none",
     "holidays": "n/a",
     "notes": "DECLARED, NOT OMITTED (L1.28a). The absence is itself the measurement and it is why "
              "NO_LAWFUL_GROUND carries an institutional-layer refusal for `cd` SECURITIES while "
              "the mining regulators fill that layer for minerals"},
    {"name": "The two interbank FX markets and the licensed bureaux de change",
     "index_symbols": (), "open_local": "08:00", "close_local": "16:00",
     "open_utc": "06:00", "close_utc": "14:00", "dst_rule": "none",
     "auction": "the BoZ and the BCC both intervene in their interbank markets and both publish a "
                "daily indicative rate; the BCC also sells dollars directly to the market",
     "expiry_rule": "forwards are thin and mostly bank-to-importer; there is no exchange clock",
     "notes": "the bureau-to-interbank spread is the published stress observable in both, and in "
              "the DRC it is the only high-frequency read on import rationing there is"},
    {"name": "The Southern African Power Pool day-ahead and balancing markets",
     "index_symbols": (), "open_local": "", "close_local": "", "open_utc": "06:00",
     "close_utc": "14:00", "dst_rule": "none",
     "auction": "a regional day-ahead market in which ZESCO and the mines buy imported power when "
                "Kariba cannot supply them, at prices well above the domestic tariff",
     "expiry_rule": "none",
     "notes": "registered as the PRICE OF THE CONSTRAINT: when the lake is low the mines pay the "
              "pool, and that cost is the transmission from a water level to a copper cost curve. "
              "No SAPP contract exists in the broker registry"},
    {"name": "The Katangan mineral depots, comptoirs and the state cobalt channel",
     "index_symbols": (), "open_local": "07:00", "close_local": "17:00", "open_utc": "05:00",
     "close_utc": "15:00", "dst_rule": "none",
     "auction": "artisanal ore is bought at depots against an assay and a dollar price; since 2019 "
                "the state has asserted a channel for artisanal cobalt and since 2024 ARECOMS "
                "regulates the strategic-minerals market",
     "expiry_rule": "none",
     "notes": "THIS IS A MARKET AND IT IS NOT A TAPE. Depot prices are reported by NGOs, by the "
              "trade press and in EITI reconciliation, never published as a series; it is "
              "registered as a CONDITIONING GROUND and no cell is compiled on an unpublished "
              "price. The desk records what is published about production, flows and policy and "
              "collects no personal data about any individual miner (see ACCESS_CONSTRAINTS)"},
)

SESSION_WINDOWS: tuple[dict[str, Any], ...] = (
    {"name": "cb_cat_morning", "start_utc": "06:00", "end_utc": "09:00",
     "notes": "the Central African business morning (08:00-11:00 CAT). The BoZ mark, the BCC "
              "indicative rate and the Kariba reading all land here, and because NEITHER country "
              "observes daylight saving the window is stable in UTC all year"},
    {"name": "cb_shanghai_close", "start_utc": "06:30", "end_utc": "07:30",
     "notes": "the SHFE afternoon close, which is where the Chinese buyer at the end of all four "
              "corridors actually marks the metal -- and it precedes the LME ring, which is the "
              "sequence a lead claim on XCUUSD needs"},
    {"name": "cb_lme_ring", "start_utc": "11:30", "end_utc": "13:30",
     "notes": "the London ring and the official settlement the offtake contracts price against; "
              "the window moves with British Summer Time and this pack's local windows do not"},
    {"name": "cb_lusaka_session", "start_utc": "08:00", "end_utc": "11:00",
     "notes": "the Lusaka equity session; registered as a frontier risk state"},
    {"name": "cb_announcement_afternoon", "start_utc": "09:00", "end_utc": "16:00",
     "notes": "the MPC statements, the Budget Address, the ministerial press conferences and the "
              "ARECOMS and Ministere des Mines communiques; the Zambian Budget Address runs into "
              "the evening CAT and is carried live"},
)

RELEASE_CLASSES: tuple[dict[str, Any], ...] = (
    {"name": "Bank of Zambia MPC decision and the Policy Rate", "cadence": "quarterly",
     "time_utc": "10:00", "source": "Bank of Zambia", "actual_series": "BOZ:policy_rate",
     "expected_series": "UNMEASURED",
     "notes": "the one scheduled, credible policy clock in this pack; the statement carries the "
              "inflation forecast revision and the copper-price assumption behind it"},
    {"name": "Bank of Zambia statutory reserve ratio circular", "cadence": "irregular",
     "time_utc": "12:00", "source": "Bank of Zambia", "actual_series": "BOZ:srr",
     "expected_series": "n/a",
     "notes": "the BLUNT instrument and the interesting one: raising the SRR drains kwacha "
              "liquidity and defends the currency, and the changes arrive by circular between "
              "scheduled meetings, which makes them genuine surprises"},
    {"name": "Banque Centrale du Congo CPM communique and the taux directeur",
     "cadence": "scheduled with off-cycle decisions", "time_utc": "13:00",
     "source": "Banque Centrale du Congo", "actual_series": "BCC:taux_directeur",
     "expected_series": "UNMEASURED",
     "notes": "published in French on bcc.cd; there is no survey of economists to measure a "
              "surprise against, so CB-D is built on the MOVES and not on a consensus gap"},
    {"name": "Zambezi River Authority daily Kariba lake level", "cadence": "daily",
     "time_utc": "06:00", "source": "Zambezi River Authority", "actual_series": "ZRA:kariba_level",
     "expected_series": "n/a",
     "notes": "THE DAILY SERIES. Level, usable storage and the same date a year earlier, published "
              "on the authority's own site; it is the highest-frequency physical input this pack "
              "has and it is causally upstream of a liquid contract"},
    {"name": "ZESCO load management schedule and its revisions", "cadence": "irregular",
     "time_utc": "14:00", "source": "ZESCO", "actual_series": "ZESCO:load_shedding_hours",
     "expected_series": "n/a",
     "notes": "the schedule is published and revised as inflows change; the MINES are on separate "
              "supply agreements and are shed differently from households, which is exactly the "
              "distinction a naive load-shedding study loses"},
    {"name": "ZamStats monthly consumer price index and the quarterly GDP release",
     "cadence": "monthly", "time_utc": "08:00", "source": "Zambia Statistics Agency",
     "actual_series": "ZAMSTATS:cpi", "expected_series": "UNMEASURED",
     "notes": "published mid-month for the prior month; the food line carries the drought and the "
              "mining line carries the output the ministry reports separately"},
    {"name": "Ministry of Mines and Minerals Development production statistics",
     "cadence": "monthly / quarterly", "time_utc": "12:00",
     "source": "MMMD Zambia", "actual_series": "MMMD:copper_output", "expected_series": "n/a",
     "notes": "the state's own count of Zambian copper production and the number the three-million "
              "tonne target is measured against; irregular and revised"},
    {"name": "Zambia Revenue Authority mineral royalty and mining tax receipts",
     "cadence": "monthly", "time_utc": "12:00", "source": "Zambia Revenue Authority",
     "actual_series": "ZRA_TAX:mineral_royalty", "expected_series": "n/a",
     "notes": "a RECEIPT is a counted tonne at a known price, which makes the royalty line an "
              "independent read on output that does not come from the producers"},
    {"name": "Ministere des Mines RDC production and export statistics", "cadence": "quarterly",
     "time_utc": "12:00", "source": "Ministere des Mines, RDC",
     "actual_series": "MINES_CD:production", "expected_series": "n/a",
     "notes": "copper and cobalt production and export tonnage by province and by operator, "
              "published in French and irregularly; the EITI reconciliation is the cross-check"},
    {"name": "ARECOMS and Ministere des Mines cobalt quota decisions", "cadence": "irregular",
     "time_utc": "13:00", "source": "ARECOMS / Ministere des Mines",
     "actual_series": "ARECOMS:cobalt_quota", "expected_series": "n/a",
     "notes": "THE EVENT OF CB-A. The suspension, the extension and the quota allocation each "
              "arrive as a dated decision; the quota volumes themselves are allocated per operator "
              "and are reported rather than published in full"},
    {"name": "ICSG monthly copper bulletin world balance", "cadence": "monthly",
     "time_utc": "10:00", "source": "International Copper Study Group",
     "actual_series": "ICSG:world_balance", "expected_series": "UNMEASURED",
     "notes": "the balance is what a Congolese or Zambian supply event has to show up IN; the "
              "headline press release is public and the bulletin itself is subscription, which is "
              "recorded on the source rather than worked around"},
    {"name": "USGS Mineral Commodity Summaries, copper and cobalt chapters", "cadence": "annual",
     "time_utc": "14:00", "source": "US Geological Survey", "actual_series": "USGS:mcs",
     "expected_series": "n/a",
     "notes": "the annual country-production table that dates the DRC's overtaking of Peru and "
              "sizes the Congolese share of world cobalt; open data and a stable citation"},
    {"name": "The two budget events (the Zambian Address in September, the Congolese finance law "
             "in December)", "cadence": "annual", "time_utc": "12:00",
     "source": "the two ministries of finance", "actual_series": "MOF:budget",
     "expected_series": "n/a",
     "notes": "the royalty scale, its deductibility, the export duties and the power tariff are "
              "BUDGET instruments; the speech is the event and the Act or the Loi de finances is "
              "the citation"},
)

# --------------------------------------------------------------------------- the two calendars
#: BOTH COUNTRIES RUN THE GREGORIAN CALENDAR AND THEY STILL DO NOT CLOSE ON THE SAME DAYS. The
#: Democratic Republic of the Congo keeps a SOLAR-ONLY statutory list -- the ordinance-law on
#: public holidays carries no Easter-derived day at all -- while Zambia closes for a FOUR-DAY
#: Easter weekend (Good Friday, Holy Saturday and Easter Monday), for three moveable days derived
#: from weekday rules, and for whatever the President declares by statutory instrument. Two
#: Christian-majority countries whose closure calendars disagree on Easter is exactly the kind of
#: asymmetry a pooled regional holiday study destroys, so the tables are computed per jurisdiction
#: and the union rows are TAGGED with the countries that actually close.
FIXED_CD: tuple[tuple[int, int, str], ...] = (
    (1, 1, "Nouvel An / New Year"),
    (1, 4, "Journee des Martyrs de l'Independance / Martyrs' Day"),
    (1, 16, "Journee des Heros nationaux: Laurent-Desire Kabila"),
    (1, 17, "Journee des Heros nationaux: Patrice-Emery Lumumba"),
    (5, 1, "Fete du Travail / Labour Day"),
    (5, 17, "Journee de la Liberation / Liberation Day"),
    (6, 30, "Fete de l'Independance / Independence Day"),
    (8, 1, "Fete des Parents / Parents' Day"),
    (12, 25, "Noel / Christmas"),
)
FIXED_ZM: tuple[tuple[int, int, str], ...] = (
    (1, 1, "New Year's Day"),
    (3, 12, "Youth Day"),
    (4, 28, "Kenneth Kaunda Day"),
    (5, 1, "Labour Day"),
    (5, 25, "Africa Freedom Day"),
    (10, 18, "National Day of Prayer, Fasting, Repentance and Reconciliation"),
    (10, 24, "Independence Day"),
    (12, 25, "Christmas Day"),
)

#: ONE-OFF CLOSURES DECLARED BY THE EXECUTIVE. Zambia's President can and does declare a public
#: holiday by statutory instrument, and a general election day is one: that is a REAL
#: market-calendar fact and not a curiosity, because it removes a session no recurring rule
#: predicts. Rows are (date, jurisdiction, what, status). SCHEDULED means a date the law itself
#: fixes and the instrument has not yet been signed.
DECLARED_CLOSURES: tuple[tuple[date, str, str, str], ...] = (
    (date(2021, 8, 12), "zm", "general election day, declared a public holiday", "DECLARED"),
    (date(2023, 12, 20), "cd", "general election polling day; a non-working day, and polling was "
                               "extended into the following day in places", "PRESS_REPORTED"),
    (date(2026, 8, 13), "zm", "the next general election day -- the second Thursday of August, "
                              "which the Constitution fixes and the instrument follows",
     "SCHEDULED"),
)

#: THE ZAMBIAN GENERAL ELECTION IS A WEEKDAY RULE, NOT A TYPED DATE. The Constitution sets the
#: poll on the SECOND THURSDAY OF AUGUST every fifth year, which is why 2016 fell on the 11th,
#: 2021 on the 12th and 2026 falls on the 13th. Deriving it is the difference between a calendar
#: that extends and a table somebody typed three entries into.
ZM_ELECTION_ANCHOR_YEAR = 2016
ZM_ELECTION_CYCLE_YEARS = 5


def easter(year: int) -> date:
    """Western (Gregorian) Easter Sunday by the ANONYMOUS GREGORIAN ALGORITHM.

    Zambia closes for Good Friday, Holy Saturday and Easter Monday, so three of its statutory
    days move with this one number and typing them is how a calendar stops extending.
    """
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    ell = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ell) // 451
    month, day = divmod(h + ell - 7 * m + 114, 31)
    return date(year, month, day + 1)


def nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """The n-th `weekday` (Mon=0) of a month -- the shape Heroes' Day, Unity Day, Farmers' Day and
    the Zambian general election all take."""
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return date(year, month, 1 + offset + 7 * (n - 1))


def heroes_day(year: int) -> date:
    """Zambian Heroes' Day: the FIRST MONDAY OF JULY, derived and never typed."""
    return nth_weekday(year, 7, 0, 1)


def unity_day(year: int) -> date:
    """Zambian Unity Day: the Tuesday immediately after Heroes' Day, so the two together are a
    guaranteed two-session closure in the first week of July."""
    return heroes_day(year) + timedelta(days=1)


def farmers_day(year: int) -> date:
    """Zambian Farmers' Day: the FIRST MONDAY OF AUGUST -- the start of the marketing season the
    Food Reserve Agency's floor price is announced for."""
    return nth_weekday(year, 8, 0, 1)


def zambian_election_day(year: int) -> date | None:
    """The Zambian general election day in a year, or None when that year holds no general poll.

    The Constitution fixes the poll on the SECOND THURSDAY OF AUGUST every fifth year from 2016,
    which gives 2016-08-11, 2021-08-12 and 2026-08-13. The day is declared a public holiday, so
    an election year loses a session that no recurring holiday rule predicts.
    """
    if year < ZM_ELECTION_ANCHOR_YEAR:
        return None
    if (year - ZM_ELECTION_ANCHOR_YEAR) % ZM_ELECTION_CYCLE_YEARS:
        return None
    return nth_weekday(year, 8, 3, 2)


def congolese_holidays(year: int) -> dict[date, str]:
    """The DRC's closed days in a Gregorian year.

    NINE FIXED SOLAR DATES AND NOTHING MOVEABLE. The statutory list carries no Easter-derived day,
    which is a real asymmetry against Zambia's four-day Easter weekend and is declared here rather
    than assumed away: two Christian-majority neighbours do not close alike.
    """
    out: dict[date, str] = {date(year, m, d): name for m, d, name in FIXED_CD}
    for day, code, what, status in DECLARED_CLOSURES:
        if code == "cd" and day.year == year:
            out[day] = f"{what} [{status}]"
    return dict(sorted(out.items()))


def zambian_holidays(year: int) -> dict[date, str]:
    """Zambia's closed days: eight fixed solar dates, the three Easter-derived days, the three
    weekday-rule days, any declared one-off, and the SUNDAY SUBSTITUTION the Public Holidays Act
    provides -- a holiday falling on a Sunday is kept on the following Monday, and a Saturday one
    is not moved at all. The substitution is what makes a Zambian holiday table a SESSION count
    rather than a list of dates.
    """
    out: dict[date, str] = {}
    for m, d, name in FIXED_ZM:
        out[date(year, m, d)] = name
    sunday = easter(year)
    out[sunday - timedelta(days=2)] = "Good Friday"
    out[sunday - timedelta(days=1)] = "Holy Saturday"
    out[sunday + timedelta(days=1)] = "Easter Monday"
    out[heroes_day(year)] = "Heroes' Day"
    out[unity_day(year)] = "Unity Day"
    out[farmers_day(year)] = "Farmers' Day"
    poll = zambian_election_day(year)
    if poll is not None:
        out[poll] = "General election day (declared by statutory instrument)"
    for day, code, what, status in DECLARED_CLOSURES:
        if code == "zm" and day.year == year:
            out[day] = f"{what} [{status}]"
    for day in sorted(out):
        if day.weekday() == 6:
            moved = day + timedelta(days=1)
            if moved.year == year and moved not in out:
                out[moved] = f"{out[day]} (observed, Sunday substitution)"
    return dict(sorted(out.items()))


JURISDICTION_HOLIDAY_FN: dict[str, Any] = {"cd": congolese_holidays, "zm": zambian_holidays}


def national_holidays(year: int) -> dict[date, str]:
    """EVERY closed day in the two jurisdictions, TAGGED with the countries that close.

    A union table, because this pack answers for two countries at once and a day that closes
    Lubumbashi is a normal session in Kitwe an hour up the road. The tag is what keeps a study
    from treating a one-country closure as a Copperbelt-wide one -- and this is the one place on
    the desk's roster where that error has a physical consequence, because the lorries have to
    clear a border with two different calendars on the two sides of it.
    """
    tagged: dict[date, list[str]] = {}
    names: dict[date, str] = {}
    for code, fn in JURISDICTION_HOLIDAY_FN.items():
        for day, name in fn(year).items():
            tagged.setdefault(day, []).append(code.upper())
            names.setdefault(day, name)
    return dict(sorted((day, f"{names[day]} [{'+'.join(sorted(codes))}]")
                       for day, codes in tagged.items()))


def market_holidays(year: int) -> dict[date, str]:
    """The weekday closures only. A Saturday holiday costs no session, and Zambia's Sunday
    substitution has already moved the Sunday ones onto the Monday where they do."""
    return {d: n for d, n in national_holidays(year).items() if d.weekday() < 5}


def is_market_holiday(day: date) -> bool:
    return day in market_holidays(day.year)


def closed_in(code: str, day: date) -> bool:
    """True when THIS jurisdiction's market is closed on this day."""
    fn = JURISDICTION_HOLIDAY_FN.get(str(code).lower())
    return day in fn(day.year) if fn is not None else False


def both_closed(day: date) -> bool:
    """True only when BOTH sides of the border are shut -- which is when the Kasumbalesa crossing
    actually stops rather than merely slowing, and it is a different event from either alone."""
    return closed_in("cd", day) and closed_in("zm", day)


def declared_closures(year: int) -> dict[date, str]:
    """Only the executive-declared one-off closures, with their status. A SCHEDULED row is a date
    the law fixes and the instrument has not yet been signed, and no cell is promoted on one."""
    return {d: f"{what} [{status}]" for d, _c, what, status in DECLARED_CLOSURES if d.year == year}


HOLIDAYS_RULE: dict[str, Any] = {
    "kind": "computed_from_two_gregorian_calendars_plus_a_declared_instrument_table",
    "authority": "the DRC's ordinance-law on public holidays for the Congolese list; Zambia's "
                 "Public Holidays Act and the statutory instruments the President signs under it "
                 "for the Zambian list",
    "rule": "BOTH COUNTRIES ARE GREGORIAN AND THEIR CALENDARS STILL DISAGREE. THE DRC keeps a "
            "SOLAR-ONLY statutory list of nine fixed dates -- 1 January, 4 January (Martyrs of "
            "Independence), 16 January (L.-D. Kabila), 17 January (Lumumba), 1 May, 17 May "
            "(Liberation), 30 JUNE (INDEPENDENCE), 1 August (Parents' Day) and 25 December -- "
            "with NO Easter-derived day at all and NO weekend substitution, so a Congolese "
            "holiday that falls on a Saturday or a Sunday simply costs no session. ZAMBIA keeps "
            "eight fixed dates (1 January, 12 March Youth Day, 28 April Kenneth Kaunda Day, 1 "
            "May, 25 May Africa Freedom Day, 18 October National Day of Prayer, 24 OCTOBER "
            "INDEPENDENCE and 25 December), three EASTER-DERIVED days computed with the anonymous "
            "Gregorian algorithm (Good Friday, HOLY SATURDAY and Easter Monday -- a four-day "
            "weekend), and three days DERIVED FROM WEEKDAY RULES rather than typed: HEROES' DAY "
            "is the first Monday of July, UNITY DAY is the Tuesday after it, and FARMERS' DAY is "
            "the first Monday of August. Zambia also applies a SUNDAY SUBSTITUTION -- a holiday "
            "falling on a Sunday is observed on the following Monday, a Saturday one is not moved "
            "-- and its President DECLARES ONE-OFF PUBLIC HOLIDAYS BY STATUTORY INSTRUMENT, of "
            "which a general election day is the recurring case: the Constitution fixes the poll "
            "on the SECOND THURSDAY OF AUGUST every fifth year from 2016, so 2016-08-11, "
            "2021-08-12 and 2026-08-13 are derived and not typed. Declared one-offs are carried "
            "in DECLARED_CLOSURES with a status, because a closure no recurring rule predicts is "
            "exactly the session a backtest silently fills. NO DAYLIGHT SAVING anywhere: Zambia "
            "and Haut-Katanga are UTC+2 all year and Kinshasa is UTC+1 all year, so every window "
            "in this pack is stable in UTC -- and the DRC's own two-zone split puts the central "
            "bank an hour behind the copper.",
    "years": (2024, 2025, 2026),
    "weekend": "Saturday and Sunday",
    "national_rule": "see `rule`; `national_holidays(year)` is the tagged union and "
                     "`congolese_holidays` and `zambian_holidays` are the per-jurisdiction tables",
    "market_rule": "the union calendar on weekdays; each market keeps its own country's table, "
                   "which is why the union rows are TAGGED with the countries that close",
    "substitution_rule": "ZAMBIA ONLY: a Sunday holiday is observed on the following Monday. The "
                         "DRC substitutes nothing, which is a real asymmetry in the session count",
    "declared_rule": "the Zambian President may declare a public holiday by statutory instrument; "
                     "DECLARED_CLOSURES carries each with its status and a SCHEDULED row is never "
                     "promoted on",
    "moving_feasts": "the three Easter-derived Zambian days move with the anonymous Gregorian "
                     "algorithm; the DRC has none",
    "table": {y: {d.isoformat(): n for d, n in national_holidays(y).items()}
              for y in (2024, 2025, 2026)},
    "status": {2024: "COMPUTED throughout; no executive one-off is recorded for either country",
               2025: "COMPUTED throughout; no executive one-off is recorded for either country",
               2026: "COMPUTED throughout, with the 2026-08-13 Zambian general election day "
                     "carried as SCHEDULED -- the Constitution fixes the date and the statutory "
                     "instrument follows, so it is derived rather than assumed",
               },
    "known_dates": {
        "2024-06-30": "Congolese Independence Day fell on a SUNDAY in 2024 and the DRC "
                      "substitutes nothing, so it cost no session at all",
        "2025-10-24": "Zambian Independence Day, a Friday -- a long weekend on one side of the "
                      "border and a normal Friday on the other",
        "2025-04-18": "Good Friday: Zambia shut for four days and the DRC worked through it",
        "2024-04-29": "Kenneth Kaunda Day OBSERVED -- 28 April 2024 was a Sunday and the Public "
                      "Holidays Act moved it to the Monday, which a typed table misses",
        "2026-08-13": "the next Zambian general election day, the second Thursday of August",
        "2026-10-19": "National Day of Prayer OBSERVED -- 18 October 2026 is a Sunday",
    },
    "fn": market_holidays,
    "national_fn": national_holidays,
    "cd_fn": congolese_holidays,
    "zm_fn": zambian_holidays,
    "declared_fn": declared_closures,
    "easter_fn": easter,
    "election_fn": zambian_election_day,
}

# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "Zambezi River Authority daily Kariba lake level and usable storage",
     "root": "https://www.zambezira.org",
     "fields": ("lake_level_m", "usable_storage_pct", "level_same_day_last_year",
                "inflow_at_victoria_falls", "allocation_to_each_utility"),
     "frequency": "daily", "snapshot": "the day's reading", "publish_utc": "06:00",
     "lag_days": 0, "licence": "free, public", "available": True,
     "why": "THE HIGHEST-FREQUENCY PHYSICAL SERIES IN THIS PACK and one of the few daily public "
            "numbers anywhere that is causally upstream of a liquid metal: usable storage above "
            "the minimum operating level binds Kariba generation, generation is smelter power, "
            "and smelter power is copper supply",
     "pit_warning": "the page shows TODAY and a comparison date; the archive is not complete, so "
                    "a day nobody crawled is UNMEASURED and is never interpolated"},
    {"name": "Bank of Zambia daily interbank exchange rate and intervention",
     "root": "https://www.boz.zm/financial-markets.htm",
     "fields": ("interbank_mid", "bureau_spread", "intervention_usd", "reserves_usd",
                "months_of_import_cover"),
     "frequency": "daily for the rate, monthly for reserves", "snapshot": "business day",
     "publish_utc": "08:00", "lag_days": 0, "licence": "free, public", "available": True,
     "why": "the kwacha is the most copper-correlated currency on earth and the BoZ publishes "
            "both the mark and, in its statistics, the size of its own hand on the scale",
     "pit_warning": "the daily page overwrites; the monthly bulletin restates reserves, so a "
                    "first print and a later vintage are different numbers"},
    {"name": "Bank of Zambia MPC statement, Policy Rate and statutory reserve ratio circulars",
     "root": "https://www.boz.zm/monetary-policy.htm",
     "fields": ("policy_rate", "statutory_reserve_ratio", "inflation_forecast",
                "copper_price_assumption", "decision_date"),
     "frequency": "quarterly for the rate, irregular for the SRR", "snapshot": "decision",
     "publish_utc": "10:00", "lag_days": 0, "licence": "free, public", "available": True,
     "why": "the only scheduled policy clock in this pack, and the statement carries the bank's "
            "own COPPER PRICE ASSUMPTION -- a central bank publishing its commodity forecast is a "
            "free expectation series for the instrument this pack trades",
     "pit_warning": "the SRR changes arrive by circular between meetings; a calendar built from "
                    "MPC dates alone misses the instrument that actually moved the kwacha"},
    {"name": "Banque Centrale du Congo condense hebdomadaire and the taux directeur",
     "root": "https://www.bcc.cd",
     "fields": ("taux_directeur", "taux_de_change_indicatif", "reserves_usd", "base_monetaire",
                "adjudication_bons_bcc"),
     "frequency": "weekly for the condense, irregular for the rate", "snapshot": "week",
     "publish_utc": "13:00", "lag_days": 7, "licence": "free, public", "available": True,
     "why": "the only regular macro publication the Congolese state makes, and it is in FRENCH; "
            "the reserve line is where the mining export receipts show up as a number",
     "pit_warning": "PDFs posted irregularly and sometimes replaced; the vintage is the crawl"},
    {"name": "Zambia Revenue Authority mineral royalty and mining tax receipts",
     "root": "https://www.zra.org.zm",
     "fields": ("mineral_royalty_zmw", "company_income_tax_mining", "export_duty",
                "vat_refunds_outstanding_mining"),
     "frequency": "monthly and in the annual report", "snapshot": "calendar month",
     "publish_utc": "12:00", "lag_days": 45, "licence": "free, public", "available": True,
     "why": "A RECEIPT IS A COUNTED TONNE AT A KNOWN PRICE. The royalty line is an independent "
            "read on Zambian output that does not come from the producers and does not depend on "
            "the ministry's own production estimate",
     "pit_warning": "revised and reclassified between the monthly release and the annual report; "
                    "the VAT refund arrears line is a separate and politically live number"},
    {"name": "Ministere des Mines RDC and the EITI-RDC reconciliation reports",
     "root": "https://www.mines.gouv.cd",
     "fields": ("copper_production_t", "cobalt_production_t", "exports_by_province",
                "royalties_paid", "operator_split"),
     "frequency": "quarterly and annual", "snapshot": "quarter", "publish_utc": "12:00",
     "lag_days": 120, "licence": "free, public", "available": True,
     "why": "the state's own count of the world's second-largest copper output and of about "
            "seventy per cent of world cobalt; the EITI reconciliation is the cross-check that "
            "makes the ministry's number checkable rather than merely official",
     "pit_warning": "published late and irregularly and restated in the EITI cycle; a missing "
                    "quarter is UNMEASURED and this pack refuses to interpolate it"},
    {"name": "a CFTC, exchange or dealer positioning series in CDF or ZMW",
     "root": "", "fields": (), "frequency": "n/a", "snapshot": "", "publish_utc": "",
     "lag_days": 0, "licence": "", "available": False,
     "why": "DECLARED ABSENT: no future, no option and no COT contract exists anywhere for the "
            "Congolese franc or the Zambian kwacha, and neither is deliverable offshore",
     "pit_warning": "DOES NOT EXIST: positioning in these currencies is UNMEASURED and is never "
                    "proxied by the ZAR COT leg, which is a position in SOUTH AFRICA and carries "
                    "South African idiosyncratic risk this pack's economies do not have"},
    {"name": "retail margin or client-flow statistics for either jurisdiction",
     "root": "", "fields": (), "frequency": "n/a", "snapshot": "", "publish_utc": "",
     "lag_days": 0, "licence": "", "available": False,
     "why": "DECLARED ABSENT: the DRC licenses no retail margin broker and publishes no retail "
            "flow of any kind; Zambia's Securities and Exchange Commission licenses a handful of "
            "dealers and publishes NO aggregate retail positioning, exposure or margin statistic",
     "pit_warning": "DOES NOT EXIST: no microstructure claim in this pack may rest on a retail "
                    "positioning number, and the retail ecology is read from public communities "
                    "at FRINGE credibility instead"},
)

# --------------------------------------------------------------------------- terminology
#: SIX LANGUAGES AND THE PACK MEANS ALL SIX. The DRC's official language is FRENCH and its
#: Journal Officiel, its Code minier, the Ministere des Mines and the Banque Centrale du Congo
#: publish in it; an English crawl of the DRC reads a translation of the ground, when it reads
#: anything at all. KATANGA -- which is where the copper is -- works in Congolese SWAHILI, and
#: Kinshasa argues in LINGALA. Zambia is the opposite trap: it legislates in ENGLISH, so an
#: English crawl returns something for every Zambian query and reads complete, while the
#: Copperbelt's own press, its load-shedding vocabulary and its farmgate reporting run in BEMBA
#: and NYANJA. Fourteen groups, one per domain.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "CB-A": ("cobalt", "hydroxyde de cobalt", "suspension des exportations", "quota "
             "d'exportation", "substance stratégique", "ARECOMS", "sous-produit du cuivre",
             "cours du cobalt", "madini ya kobalti", "kusimamisha usafirishaji nje",
             "mbongo ya cobalt", "cobalt export ban", "export quota allocation"),
    "CB-B": ("cuivre", "production de cuivre", "concentré de cuivre", "cathodes",
             "montée en puissance", "Kamoa-Kakula", "Tenke Fungurume", "shaba",
             "uzalishaji wa shaba", "umukuba", "copper cathode output", "mine expansion"),
    "CB-C": ("code minier", "redevance minière", "arrêté ministériel", "Journal Officiel",
             "cadastre minier", "sous-traitance", "ARSP", "Gécamines", "partenariat minier",
             "sheria ya madini", "kodi ya madini", "mining code amendment"),
    "CB-D": ("franc congolais", "taux directeur", "taux de change indicatif", "dollarisation",
             "réserves de change", "inflation", "banque centrale", "mbongo", "zando", "talo",
             "bei ya dola", "exchange rate pass-through"),
    "CB-E": ("creuseur artisanal", "exploitation artisanale", "comptoir", "coopérative minière",
             "Entreprise Générale du Cobalt", "zone d'exploitation artisanale", "wachimbaji",
             "madini", "mosala ya mabanga", "artisanal cobalt depot", "traceability scheme",
             "due diligence supply chain"),
    "CB-F": ("Kariba", "niveau du lac", "barrage", "délestage", "électricité", "sécheresse",
             "magetsi", "madzi", "amenshi", "umeme", "ukame", "load shedding schedule",
             "usable storage", "smelter power supply"),
    "CB-G": ("Konkola", "Mopani", "ZCCM-IH", "production minière", "objectif trois millions",
             "mgodi", "umukuba", "malonda", "indalama", "copper output target",
             "mine ownership change", "concentrate treatment charge"),
    "CB-H": ("défaut souverain", "restructuration de la dette", "Cadre Commun", "eurobond",
             "Fonds monétaire international", "comité des créanciers", "ndalama",
             "mtengo", "debt restructuring memorandum", "official creditor committee",
             "extended credit facility"),
    "CB-I": ("kwacha", "taux interbancaire", "intervention de change", "réserves obligatoires",
             "comité de politique monétaire", "indalama", "ndalama", "malonda",
             "statutory reserve ratio", "copper beta of the currency", "policy rate decision"),
    "CB-J": ("redevance minière", "déductibilité", "impôt sur les sociétés", "droits d'exportation",
             "remboursement de TVA", "budget", "loi de finances", "kodi", "malonda",
             "mineral royalty deductibility", "VAT refund arrears", "export duty on concentrate"),
    "CB-K": ("corridor", "Lobito", "Beira", "Nacala", "Dar es Salaam", "chemin de fer",
             "Benguela", "TAZARA", "bandari", "barabara", "mizigo", "reli",
             "export corridor throughput", "rail concession"),
    "CB-L": ("Kasumbalesa", "frontière", "douane", "poste frontalier", "camions", "embouteillage",
             "mpaka", "barabara", "mizigo ya shaba", "border queue kilometres",
             "customs clearance time", "one-stop border post"),
    "CB-M": ("jour férié", "fête de l'indépendance", "Journée des Martyrs", "calendrier",
             "sango", "mboka", "Heroes Day", "Unity Day", "Farmers Day",
             "statutory instrument holiday", "general election day", "Pâques"),
    "CB-N": ("Sicomines", "infrastructure contre minerais", "investissement chinois", "offtake",
             "raffinerie", "biloko", "mosala", "shaba", "bei ya shaba nchini China",
             "Chinese offtake agreement", "refined copper import", "bonded premium"),
}

#: The working vocabulary the pack must carry in each of its four non-English grounds, asserted by
#: the tests so this file cannot quietly become an English glossary of a French-language state and
#: a Bemba-speaking mining province.
FRENCH_MARKERS: tuple[str, ...] = (
    "cuivre", "cobalt", "redevance minière", "code minier", "taux directeur", "Journal Officiel",
    "sous-traitance", "creuseur artisanal", "barrage", "délestage", "corridor", "douane",
    "franc congolais", "arrêté ministériel", "comptoir", "sécheresse", "frontière", "jour férié")
SWAHILI_MARKERS: tuple[str, ...] = (
    "shaba", "madini", "mgodi", "umeme", "mpaka", "barabara", "wachimbaji", "bandari", "ukame",
    "mizigo", "reli", "kodi")
LINGALA_MARKERS: tuple[str, ...] = ("mbongo", "zando", "talo", "mosala", "sango", "mboka",
                                    "biloko")
BEMBA_NYANJA_MARKERS: tuple[str, ...] = (
    "umukuba", "indalama", "ndalama", "magetsi", "madzi", "amenshi", "malonda", "mtengo")

SOURCE_LAYERS: tuple[str, ...] = (
    "official", "institutional", "academic", "practitioner", "retail_ecology", "app_ecosystem",
    "media", "archive", "physical_economy", "source_graph")
ACCESS_LABELS: tuple[str, ...] = (
    "PUBLIC", "PUBLIC_WITH_TERMS", "LICENSED", "OPEN_DATA", "PUBLIC_ARCHIVE", "PUBLIC_SOCIAL",
    "USER_SUBMITTED", "ACCESS_UNCLEAR", "PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")
CREDIBILITY_LABELS: tuple[str, ...] = (
    "AUTHORITATIVE", "RELIABLE", "UNRELIABLE", "FRINGE", "CONTRADICTED", "UNKNOWN")
PREDICTIVE_STATES: tuple[str, ...] = (
    "UNTESTED", "PREDICTIVE", "NOT_PREDICTIVE", "NARRATIVE_FEATURE")


#: ALL FOUR OF THIS PACK'S NATIVE GROUNDS ARE WRITTEN IN LATIN SCRIPT, so a codepoint test cannot
#: find any of them and a WORD test is the only honest one. These are closed-class and
#: high-frequency tokens -- grammatical particles and the trade vocabulary this pack actually
#: queries in -- matched as whole words so that an English sentence cannot accidentally read as
#: French because it happens to contain the letters.
_FRENCH_WORDS: frozenset[str] = frozenset({
    "le", "la", "les", "des", "du", "de", "et", "au", "aux", "sur", "dans", "par", "pour", "une",
    "un", "est", "sont", "cette", "cours", "banque", "centrale", "taux", "change", "marché",
    "marche", "prix", "cuivre", "cobalt", "minier", "minière", "miniere", "mines", "minerais",
    "exportation", "exportations", "production", "arrêté", "arrete", "décret", "decret", "loi",
    "journal", "officiel", "douane", "redevance", "quota", "suspension", "interdiction",
    "frontière", "frontiere", "corridor", "fret", "transport", "énergie", "energie",
    "électricité", "electricite", "délestage", "delestage", "barrage", "niveau", "lac", "pluie",
    "sécheresse", "secheresse", "artisanal", "artisanale", "creuseur", "creuseurs", "comptoir",
    "sous", "traitance", "budget", "finances", "recettes", "inflation", "franc", "congolais",
    "réserves", "reserves", "port", "chemin", "fer", "route", "camions", "embouteillage",
    "stratégique", "strategique", "substance", "cadastre", "coopérative", "cooperative",
    "partenariat", "société", "societe", "défaut", "defaut", "dette", "restructuration",
    "créanciers", "creanciers", "souverain", "intervention", "obligatoires", "politique",
    "monétaire", "monetaire", "déductibilité", "deductibilite", "impôt", "impot", "droits",
    "remboursement", "jour", "férié", "ferie", "fête", "fete", "indépendance", "independance",
    "journée", "journee", "martyrs", "calendrier", "pâques", "paques", "infrastructure",
    "contre", "investissement", "chinois", "raffinerie", "montée", "montee", "puissance",
    "concentré", "concentre", "cathodes", "hydroxyde", "dollarisation", "indicatif",
    "hebdomadaire", "condensé", "condense", "ministériel", "ministeriel", "zone", "exploitation"})
_SWAHILI_WORDS: frozenset[str] = frozenset({
    "ya", "wa", "za", "kwa", "cha", "kwenye", "bei", "soko", "sokoni", "benki", "kuu", "shaba",
    "dhahabu", "madini", "mizigo", "bandari", "umeme", "mvua", "ukame", "mpaka", "barabara",
    "reli", "mgodi", "migodi", "uzalishaji", "kodi", "serikali", "taarifa", "fedha", "mafuta",
    "gesi", "maji", "bwawa", "wachimbaji", "kusafirisha", "usafirishaji", "nje", "takwimu",
    "dola", "habari", "tani", "kusimamisha", "kobalti", "biashara", "mkataba", "bandarini",
    "nchini", "uchumi", "mgao", "leo"})
_LINGALA_WORDS: frozenset[str] = frozenset({
    "mbongo", "zando", "talo", "mosala", "sango", "nsango", "bato", "mboka", "makuta", "kosomba",
    "koteka", "libanga", "mabanga", "mingi", "biloko", "mokili"})
_BEMBA_NYANJA_WORDS: frozenset[str] = frozenset({
    "umukuba", "indalama", "ndalama", "magetsi", "madzi", "amenshi", "chimanga", "malonda",
    "mtengo", "golide", "icalo", "ubuteko", "boma", "mgodi"})


def _words(text: str) -> list[str]:
    return ["".join(ch for ch in w if ch.isalpha() or ch == "'").lower()
            for w in str(text).replace("-", " ").split()]


def has_french(text: str) -> bool:
    """True when the text carries at least one French word. A WORD test, not a substring one:
    the DRC's whole official ground is French and an English query dressed in a French flag is
    how a crawl reads a translation of a country and reports it as the country."""
    return any(w in _FRENCH_WORDS for w in _words(text))


def has_swahili(text: str) -> bool:
    """True when the text carries at least one Congolese-Swahili word. Katanga -- which is where
    the copper is -- works in Swahili, not in French and not in Lingala."""
    return any(w in _SWAHILI_WORDS for w in _words(text))


def has_lingala(text: str) -> bool:
    """True when the text carries at least one Lingala word. Kinshasa's popular press and its
    street-rate talk run in Lingala and a French-only crawl never sees them."""
    return any(w in _LINGALA_WORDS for w in _words(text))


def has_bemba_nyanja(text: str) -> bool:
    """True when the text carries at least one Bemba or Nyanja word. Zambia legislates in English,
    which is exactly why its own Copperbelt vocabulary has to be queried for on purpose."""
    return any(w in _BEMBA_NYANJA_WORDS for w in _words(text))


def has_native(text: str) -> bool:
    """True when a query is written in ANY of this pack's four native grounds rather than in the
    English that both states will happily give a foreigner."""
    return (has_french(text) or has_swahili(text) or has_lingala(text)
            or has_bemba_nyanja(text))


def _markers_present(markers: Iterable[str],
                     terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    rows = TERMINOLOGY if terminology is None else terminology
    flat = {t for terms in rows.values() for t in terms}
    return [m for m in markers if any(m in t for t in flat)]


def french_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    """Every declared French marker actually present in the terminology table."""
    return _markers_present(FRENCH_MARKERS, terminology)


def swahili_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    return _markers_present(SWAHILI_MARKERS, terminology)


def lingala_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    return _markers_present(LINGALA_MARKERS, terminology)


def bemba_nyanja_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    return _markers_present(BEMBA_NYANJA_MARKERS, terminology)


def term_count(terminology: Mapping[str, Iterable[str]] | None = None) -> int:
    rows = TERMINOLOGY if terminology is None else terminology
    return len({t for terms in rows.values() for t in terms})


def _seq(values: Iterable[Any]) -> tuple[str, ...]:
    return tuple(str(v) for v in values)


def source_class(sid: str, label: str, *, layer: str, roots: Iterable[str],
                 queries: Iterable[str], languages: Iterable[str], access_label: str,
                 credibility: str, predictive_state: str, licence: str,
                 machine_use_allowed: bool = True, notes: str = "") -> dict[str, Any]:
    """One class of source with the roots a crawler starts from and its three INDEPENDENT labels.
    `queries` are native-language terms, never translations. `machine_use_allowed=False` registers
    ground whose terms forbid extraction: never scraped, never omitted."""
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
    """A layer this region has nothing in, declared BY NAME with the reason (L1.28a)."""
    if layer not in SOURCE_LAYERS:
        raise ValueError(f"absent layer {layer!r}")
    return {"id": f"absent_{layer}", "label": f"NO SOURCE IN THIS LAYER: {layer}", "layer": layer,
            "roots": (), "queries": (), "languages": (), "access_label": "ACCESS_UNCLEAR",
            "credibility": "UNKNOWN", "predictive_state": "UNTESTED",
            "machine_use_allowed": False, "licence": "n/a",
            "notes": f"DECLARED ABSENT, NOT BLANK: {reason}"}


SOURCE_CLASSES: tuple[dict[str, Any], ...] = (
    # ---- official
    source_class(
        "cb_bcc", "Banque Centrale du Congo: the taux directeur and the CPM communiques, the "
                  "condense hebdomadaire, the daily indicative exchange rate, reserves and the "
                  "BCC bill auctions -- all in French",
        layer="official",
        roots=("https://www.bcc.cd", "https://www.bcc.cd/publications",
               "https://www.bcc.cd/statistiques"),
        queries=("taux directeur Banque Centrale du Congo", "condensé hebdomadaire BCC",
                 "taux de change indicatif du franc congolais", "réserves de change RDC",
                 "adjudication des bons BCC", "comité de politique monétaire communiqué",
                 "dollarisation de l'économie congolaise", "inflation en RDC"),
        languages=("fr",), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public (bcc.cd terms)",
        notes="THE ONLY REGULAR MACRO PUBLICATION THE CONGOLESE STATE MAKES, and it is in French. "
              "The condense is where the reserve line and the base monetaire appear weekly, which "
              "is faster than anything the statistics office publishes"),
    source_class(
        "cb_cd_state", "Institut National de la Statistique (INS-RDC), Ministere des Mines, "
                       "Ministere des Finances, the DGDA customs administration and the Cadastre "
                       "Minier -- production, exports, the fiscal regime and the licence map",
        layer="official",
        roots=("https://www.ins-rdc.org", "https://www.mines.gouv.cd", "https://www.cami.cd",
               "https://www.dgda.gouv.cd"),
        queries=("production de cuivre et de cobalt en RDC", "exportations minières statistiques",
                 "cadastre minier permis d'exploitation", "droits de douane à l'exportation",
                 "redevance minière recettes", "indice des prix à la consommation RDC",
                 "arrêté ministériel mines", "statistiques du commerce extérieur"),
        languages=("fr",), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the ministry's production table is the state's own count of the world's number-two "
              "copper output and of about seventy per cent of world cobalt; it is late, "
              "irregular and restated, and the EITI reconciliation is what makes it checkable"),
    source_class(
        "cb_arecoms", "ARECOMS (the strategic-minerals regulator), the Entreprise Generale du "
                      "Cobalt and ARSP (the subcontracting regulator): the decisions that "
                      "suspended, extended and then quota'd cobalt exports",
        layer="official",
        roots=("https://arsp.cd", "https://www.mines.gouv.cd", "https://www.primature.cd"),
        queries=("suspension des exportations de cobalt", "quota d'exportation de cobalt ARECOMS",
                 "substance stratégique arrêté", "Entreprise Générale du Cobalt monopole",
                 "sous-traitance dans le secteur privé ARSP", "décision ARECOMS communiqué",
                 "kusimamisha usafirishaji wa kobalti"),
        languages=("fr", "sw"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE EVENT SOURCE OF CB-A. ARECOMS decisions are published as communiques rather "
              "than as gazetted instruments in the first instance, so the press and the ministry "
              "site carry them days before the Journal Officiel does -- which is exactly the "
              "window the source-graph layer exists to measure"),
    source_class(
        "cb_boz", "Bank of Zambia: the MPC statement and Policy Rate, the STATUTORY RESERVE RATIO "
                  "circulars, daily interbank rates, intervention, reserves and the National "
                  "Payment Systems report",
        layer="official",
        roots=("https://www.boz.zm", "https://www.boz.zm/monetary-policy.htm",
               "https://www.boz.zm/financial-markets.htm", "https://www.boz.zm/statistics.htm"),
        queries=("Bank of Zambia monetary policy statement", "statutory reserve ratio circular",
                 "kwacha interbank rate", "indalama za kwacha", "ndalama zamalonda",
                 "copper price assumption inflation forecast", "gross international reserves"),
        languages=("en", "bem", "ny"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE ONLY SCHEDULED POLICY CLOCK IN THIS PACK, and the statement publishes the "
              "bank's own COPPER PRICE ASSUMPTION -- a central bank handing the desk a free "
              "expectation series for the instrument it trades"),
    source_class(
        "cb_zm_state", "Zambia Statistics Agency (CPI, GDP, trade), the Ministry of Mines and "
                       "Minerals Development (production), the Zambia Revenue Authority (royalty "
                       "receipts and customs) and the Ministry of Finance budget documents",
        layer="official",
        roots=("https://www.zamstats.gov.zm", "https://www.mmmd.gov.zm", "https://www.zra.org.zm",
               "https://www.mof.gov.zm"),
        queries=("Zambia copper production statistics", "mineral royalty receipts",
                 "ndalama za boma", "malonda a mgodi", "consumer price index Zambia",
                 "budget address mining tax", "VAT refund arrears mining", "export duty"),
        languages=("en", "bem", "ny"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the ROYALTY RECEIPT is the interesting series: it is a counted tonne at a known "
              "LME-referenced price, published by the tax authority rather than by the producers, "
              "and it is therefore an independent read on output"),
    source_class(
        "cb_zm_law", "The National Assembly of Zambia, the Government Gazette and the statutory "
                     "instruments the President signs -- including the one-off public holidays "
                     "and the export restrictions",
        layer="official",
        roots=("https://www.parliament.gov.zm", "https://zambialii.org",
               "https://www.mof.gov.zm/?page_id=3001"),
        queries=("statutory instrument public holiday Zambia", "Finance Act mineral royalty",
                 "Mines and Minerals Development Act amendment", "ndalama za msonkho",
                 "export restriction statutory instrument", "Public Holidays Act substitution"),
        languages=("en", "ny"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE INSTRUMENT IS WHERE A DECLARED HOLIDAY AND AN EXPORT BAN BOTH LIVE. Zambia "
              "governs the marginal decisions of this pack by statutory instrument, which is a "
              "faster and less-read channel than an Act of Parliament"),
    # ---- institutional
    source_class(
        "cb_luse", "The Lusaka Securities Exchange and the Securities and Exchange Commission of "
                   "Zambia: the all-share index, turnover, the investor split and the listings",
        layer="institutional",
        roots=("https://www.luse.co.zm", "https://www.seczambia.org.zm"),
        queries=("LuSE all share index turnover", "Lusaka Securities Exchange market report",
                 "ndalama za hisa", "foreign participation Zambian equities",
                 "securities commission licensed dealers"),
        languages=("en", "ny"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="NO CFD IS QUOTED on the LuSE. The index is registered as a frontier-risk STATE and "
              "never as a price, and a single block can set the day, which is the reason"),
    source_class(
        "cb_power_institutions", "ZESCO, the ZAMBEZI RIVER AUTHORITY, the Energy Regulation Board "
                                 "and SNEL on the Congolese side: generation, the DAILY lake "
                                 "level, the tariff and the load-management schedules",
        layer="institutional",
        roots=("https://www.zesco.co.zm", "https://www.zambezira.org", "https://www.erb.org.zm",
               "https://www.snel.cd"),
        queries=("Kariba lake level daily", "ZESCO load management schedule", "magetsi ku Zambia",
                 "amenshi ya Kariba", "délestage électricité Katanga", "niveau du lac Kariba",
                 "energy regulation board tariff determination", "umeme mgao"),
        languages=("en", "ny", "bem", "fr", "sw"), access_label="PUBLIC",
        credibility="AUTHORITATIVE", predictive_state="UNTESTED", licence="free, public",
        notes="THE ZAMBEZI RIVER AUTHORITY PUBLISHES THE LAKE LEVEL DAILY and it is the single "
              "most valuable series in this pack: a public daily number that is causally upstream "
              "of smelter power and therefore of copper supply"),
    source_class(
        "cb_state_miners", "Gecamines and the Congolese state portfolio; ZCCM-IH and the Zambian "
                           "state holding: annual reports, partnership disputes and the "
                           "ownership changes at Mopani and Konkola",
        layer="institutional",
        roots=("https://www.gecamines.cd", "https://www.zccm-ih.com.zm"),
        queries=("Gécamines rapport annuel partenariat", "ZCCM-IH Mopani stake announcement",
                 "Konkola Copper Mines ownership", "redevance Gécamines contentieux",
                 "umukuba wa Mopani", "state mining portfolio dividend"),
        languages=("fr", "en", "bem"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="TWO STATE HOLDING COMPANIES ARE ACTORS AND NOT INSTRUMENTS (two-lane order, "
              "2026-09-06). Their disclosures are read for the OWNERSHIP and OUTPUT facts, never "
              "for an equity claim, and ZCCM-IH's own listing is registered and never traded"),
    # ---- academic
    source_class(
        "cb_academic", "The scholarly ground: OpenAlex and CORE for the indexed literature, the "
                       "University of Zambia and the Universite de Lubumbashi for the domestic "
                       "work, and the mining-economics and hydrology literature on the Zambezi",
        layer="academic",
        roots=("https://openalex.org", "https://core.ac.uk", "https://www.unza.zm",
               "https://www.unilu.ac.cd"),
        queries=("économie minière Katanga étude", "hydrologie du Zambèze étude",
                 "artisanal mining livelihoods Copperbelt", "copper price pass-through kwacha",
                 "utafiti wa uchumi wa madini", "resource curse Zambia empirical"),
        languages=("fr", "en", "sw"), access_label="OPEN_DATA", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="open access where indexed",
        notes="THE DOMESTIC HALF OF THIS LAYER IS THIN AND THE PACK SAYS SO in NO_LAWFUL_GROUND: "
              "what an index returns for the DRC is overwhelmingly FOREIGN-authored work about "
              "the DRC, which is a different ground from the Congolese academic ground"),
    source_class(
        "cb_academic_hydrology", "The Zambezi basin hydrology and drought literature, the "
                                 "regional climate outlook forums and the famine-early-warning "
                                 "analyses that predict the inflow the lake level realises",
        layer="academic",
        roots=("https://fews.net", "https://www.icpac.net", "https://iri.columbia.edu"),
        queries=("Zambezi basin inflow forecast", "SARCOF seasonal rainfall outlook",
                 "El Nino southern Africa drought", "mvua na ukame kusini mwa Afrika",
                 "prévision des pluies bassin du Zambèze", "crop and drought monitoring Zambia"),
        languages=("en", "sw", "fr"), access_label="OPEN_DATA", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE ONLY FORWARD-LOOKING GROUND IN THE PACK. The lake level is a state; the "
              "seasonal rainfall outlook is a forecast of the state, published months ahead, and "
              "a cell that conditions on the outlook rather than on the level is testing a "
              "genuinely ex-ante claim"),
    # ---- practitioner
    source_class(
        "cb_metals_practitioner", "The metals-market practitioners: the International Copper "
                                  "Study Group, the Cobalt Institute, the Zambia Chamber of Mines "
                                  "and the Federation des Entreprises du Congo",
        layer="practitioner",
        roots=("https://icsg.org", "https://www.cobaltinstitute.org", "https://mines.org.zm",
               "https://www.fec.cd"),
        queries=("copper world balance monthly bulletin", "cobalt market report supply",
                 "chambre des mines RDC communiqué", "Zambia Chamber of Mines position paper",
                 "coût de production du cuivre", "gharama za uzalishaji wa shaba"),
        languages=("en", "fr", "sw"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="press releases free; the bulletins are subscription",
        machine_use_allowed=False,
        notes="REGISTERED, NOT SCRAPED. The ICSG bulletin and the Cobalt Institute's detailed "
              "series are subscription products whose terms forbid machine extraction; the "
              "headline press releases are public and are what this pack reads. Omitting the "
              "source would lose the knowledge that the balance exists at all"),
    source_class(
        "cb_market_weeklies", "The domestic bank and broker market commentary: the Zambian banks' "
                              "weekly treasury notes, the Lusaka brokers' research and the "
                              "Congolese business-association bulletins",
        layer="practitioner",
        roots=("https://www.boz.zm/financial-markets.htm", "https://mines.org.zm",
               "https://www.fec.cd"),
        queries=("weekly treasury market report kwacha", "yield curve Zambia government bond",
                 "ndalama za banki lipoti", "note hebdomadaire marché des changes Kinshasa",
                 "taarifa ya kila wiki ya soko", "bond auction bid to cover Zambia"),
        languages=("en", "fr", "sw", "ny"), access_label="ACCESS_UNCLEAR", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="mixed; several are e-mail circulars",
        notes="KEPT AT LOW WEIGHT AND NOT DROPPED. A bank's weekly view is a dated, falsifiable "
              "claim about the same kwacha this pack models, and the desk's rule is that fringe "
              "and unreliable PUBLIC material is weighted down, never deleted"),
    # ---- retail ecology
    source_class(
        "cb_retail_rates", "The street-rate and commodity-price retail ground: the public "
                           "Congolese and Zambian rate-watching pages, the price-of-the-day "
                           "posts and the diaspora remittance forums",
        layer="retail_ecology",
        roots=("https://www.reddit.com/r/Zambia", "https://www.facebook.com",
               "https://www.youtube.com"),
        queries=("taux du dollar aujourd'hui Kinshasa", "bei ya dola leo Lubumbashi",
                 "mtengo wa dollar lero", "talo ya dollar lelo", "kwacha exchange rate today",
                 "prix du cuivre aujourd'hui"),
        languages=("fr", "sw", "ln", "ny", "en"), access_label="PUBLIC_SOCIAL",
        credibility="FRINGE", predictive_state="UNTESTED",
        licence="platform terms forbid bulk extraction", machine_use_allowed=False,
        notes="REGISTERED AND NEVER SCRAPED. This is the ONLY high-frequency read on the "
              "Congolese street rate that exists, which is precisely why it is kept at FRINGE "
              "credibility rather than dropped: a number nobody publishes and everybody quotes is "
              "a measurement problem, not an absence"),
    source_class(
        "cb_retail_mining", "The artisanal-mining and Copperbelt community ground: the local "
                            "Facebook and WhatsApp-adjacent public pages where depot prices, "
                            "shift changes and load-shedding are discussed first",
        layer="retail_ecology",
        roots=("https://www.facebook.com", "https://www.youtube.com", "https://www.tiktok.com"),
        queries=("bei ya madini leo Kolwezi", "wachimbaji habari", "magetsi ku Copperbelt lero",
                 "prix du cobalt au comptoir", "mgodi ntchito", "délestage Lubumbashi"),
        languages=("sw", "fr", "ny", "bem"), access_label="PUBLIC_SOCIAL", credibility="FRINGE",
        predictive_state="UNTESTED", licence="platform terms forbid bulk extraction",
        machine_use_allowed=False,
        notes="READ FOR PUBLISHED FACTS ABOUT PRICES, SHIFTS AND POWER, AND FOR NOTHING ELSE. The "
              "desk records what is published about production, flows and policy and neither "
              "collects nor seeks personal data about any individual miner (ACCESS_CONSTRAINTS)"),
    # ---- app ecosystem
    source_class(
        "cb_mobile_money", "MOBILE MONEY IS THE APP LAYER HERE: Airtel Money, MTN MoMo, Vodacom "
                           "M-Pesa, Orange Money and Zamtel Kwacha, whose transaction values the "
                           "Bank of Zambia, ZICTA and the Congolese regulator ARPTC publish",
        layer="app_ecosystem",
        roots=("https://www.boz.zm/statistics.htm", "https://www.zicta.zm", "https://arptc.cd"),
        queries=("mobile money transaction value Zambia", "ndalama za pa foni",
                 "monnaie électronique RDC statistiques", "pesa za simu takwimu",
                 "agent float mobile money", "abonnés mobile money RDC"),
        languages=("en", "fr", "sw", "ny"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="DECLARING THIS LAYER ABSENT BECAUSE THERE IS NO METATRADER ECOLOGY WOULD BE READING "
              "THE WRONG COUNTRY. In both of these economies the app people actually use is a "
              "payment rail, and its transaction value is the only high-frequency NOMINAL series "
              "either state publishes"),
    source_class(
        "cb_app_logistics", "The logistics and border apps: the corridor transit-time dashboards, "
                            "the port community systems and the customs single windows that a "
                            "Katangan transporter actually opens",
        layer="app_ecosystem",
        roots=("https://centralcorridor-ttfa.org", "https://www.dgda.gouv.cd",
               "https://www.zra.org.zm"),
        queries=("guichet unique du commerce extérieur", "transit time corridor dashboard",
                 "mizigo ya transit takwimu", "customs single window declaration",
                 "poste frontalier à arrêt unique", "barabara ya mizigo"),
        languages=("fr", "sw", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the corridor dashboards publish TRANSIT TIMES and sometimes queue lengths, which "
              "is the observable of CB-L; coverage is patchy and a missing week is UNMEASURED"),
    # ---- media
    source_class(
        "cb_media_cd", "The Congolese press: Radio Okapi, Actualite.cd, Mediacongo, 7sur7 and "
                       "Politico.cd -- in French, with Swahili and Lingala service for Okapi",
        layer="media",
        roots=("https://www.radiookapi.net", "https://actualite.cd", "https://www.mediacongo.net",
               "https://7sur7.cd"),
        queries=("exportations de cobalt suspension", "Gécamines actualité", "délestage Katanga",
                 "frontière de Kasumbalesa camions", "habari za madini Katanga",
                 "sango ya mbongo", "arrêté sur les substances stratégiques"),
        languages=("fr", "sw", "ln"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="RADIO OKAPI IS THE ONE OUTLET WITH NATIONAL REACH AND FOUR LANGUAGES, which makes "
              "it the cheapest place to learn this ground's vocabulary and the earliest place a "
              "ministerial decision is reported before the Journal Officiel carries it"),
    source_class(
        "cb_media_zm", "The Zambian press: the Zambian Business Times, News Diggers, The Mast, "
                       "Lusaka Times and the Mining for Zambia industry outlet",
        layer="media",
        roots=("https://zambianbusinesstimes.com", "https://diggers.news",
               "https://www.themastonline.com", "https://www.lusakatimes.com"),
        queries=("copper production Zambia output", "load shedding hours announcement",
                 "mineral royalty budget debate", "ndalama za boma malonda",
                 "magetsi ndi mgodi", "Mopani Konkola stake", "kwacha exchange rate pressure"),
        languages=("en", "ny", "bem"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the Zambian press argues in ENGLISH about a Bemba- and Nyanja-speaking Copperbelt, "
              "so the English half is real and the local-language half is where load-shedding, "
              "maize and depot prices are actually discussed"),
    source_class(
        "cb_media_trade", "The international mining and metals trade press, and the wires that "
                          "date a Congolese or Zambian decision before either state publishes it",
        layer="media",
        roots=("https://www.miningweekly.com", "https://www.mining.com",
               "https://www.mining-journal.com"),
        queries=("DRC cobalt export quota", "Zambia copper output target",
                 "Lobito corridor first shipment", "Kamoa Kakula phase ramp",
                 "cobalt price collapse oversupply", "TAZARA concession agreement"),
        languages=("en",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="mixed; several titles are subscription",
        machine_use_allowed=False,
        notes="REGISTERED, NOT SCRAPED. The trade press is frequently the FIRST dated record of an "
              "ARECOMS decision or a corridor milestone, and several of these titles forbid "
              "machine extraction in terms; the pack records the ground and reads the headline"),
    # ---- archive
    source_class(
        "cb_archive_cd", "The Congolese legal archive: LEGANET and the Journal Officiel for the "
                         "Code minier, the ordinances and the finance laws, plus the colonial-era "
                         "and Union Miniere record in the French and Belgian digital libraries",
        layer="archive",
        roots=("https://www.leganet.cd", "https://gallica.bnf.fr", "https://archive.org"),
        queries=("code minier loi 18/001 texte", "Journal Officiel de la RDC numéro spécial",
                 "ordonnance-loi jours fériés", "Union Minière du Haut-Katanga archives",
                 "arrêté substances stratégiques 2018", "loi de finances RDC texte"),
        languages=("fr",), access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="LEGANET IS THE PRACTICAL JOURNAL OFFICIEL. The official gazette is not reliably "
              "online in a machine-readable form, and the legal-archive site is where the dated "
              "text of the Code minier and its amending arretes can actually be read"),
    source_class(
        "cb_archive_zm", "The Zambian legal and historical archive: ZambiaLII for the Acts and "
                         "statutory instruments, the National Assembly's own record, and the "
                         "colonial Northern Rhodesia and ZCCM record in the digital libraries",
        layer="archive",
        roots=("https://zambialii.org", "https://www.parliament.gov.zm", "https://archive.org"),
        queries=("Mines and Minerals Development Act text", "statutory instrument gazette notice",
                 "Public Holidays Act Zambia chapter", "Northern Rhodesia copper archives",
                 "Hansard mining royalty debate", "ndalama za msonkho wa mgodi"),
        languages=("en", "ny"), access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the Hansard record is the underused half: a royalty change is debated on the floor "
              "weeks before the Finance Act commences, and the debate is dated and public"),
    # ---- physical economy
    source_class(
        "cb_corridors", "THE FOUR ROADS TO THE SEA: Tanzania Ports Authority and the Central "
                        "Corridor TTFA for Dar es Salaam, Transnet for Durban, the Beira and "
                        "Nacala corridor operators, TAZARA, and the Lobito Atlantic Railway "
                        "reporting through the Angolan ministry and the trade press",
        layer="physical_economy",
        roots=("https://www.tanzaniaports.go.tz", "https://centralcorridor-ttfa.org",
               "https://www.transnet.net", "https://www.tazarasite.com"),
        queries=("mizigo ya transit bandari ya Dar es Salaam", "corridor de Lobito trafic",
                 "Beitbridge border delay trucks", "TAZARA freight tonnage",
                 "chemin de fer de Benguela cuivre", "reli ya mizigo takwimu",
                 "Nacala corridor throughput"),
        languages=("sw", "fr", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE TRANSIT-BY-COUNTRY SPLIT IS WHAT MAKES THIS A CHOKEPOINT OBSERVABLE rather "
              "than a national trade statistic, and it is exactly the series the `east_africa` "
              "pack owns at the Tanzanian end -- neither pack can tell a chokepoint from a "
              "re-routing without the other's numbers"),
    source_class(
        "cb_power_physical", "THE POWER SYSTEM AS PHYSICS: the Zambezi River Authority's daily "
                             "lake level and inflow, ZESCO and SNEL generation, the Southern "
                             "African Power Pool's traded volumes and the mines' own imported "
                             "power arrangements",
        layer="physical_economy",
        roots=("https://www.zambezira.org", "https://www.zesco.co.zm", "https://www.sapp.co.zw"),
        queries=("Kariba usable storage percentage", "niveau du lac et production hydroélectrique",
                 "amenshi ya Kariba lero", "madzi a Kariba", "power pool traded volume",
                 "mgao wa umeme migodini", "smelter power import agreement"),
        languages=("en", "fr", "sw", "bem", "ny"), access_label="PUBLIC",
        credibility="AUTHORITATIVE", predictive_state="UNTESTED", licence="free, public",
        notes="A DAILY PUBLIC NUMBER CAUSALLY UPSTREAM OF A LIQUID METAL is rare enough to be "
              "worth saying twice: the lake level binds generation, generation is smelter power, "
              "and smelter power is copper supply"),
    source_class(
        "cb_trade_physical", "The counted flows: UN Comtrade mirror statistics for refined copper "
                             "and cobalt, the USGS Mineral Commodity Summaries, and the customs "
                             "declarations on both sides of Kasumbalesa",
        layer="physical_economy",
        roots=("https://comtradeplus.un.org", "https://www.usgs.gov/centers/national-minerals-"
               "information-center", "https://www.dgda.gouv.cd", "https://www.zra.org.zm"),
        queries=("refined copper exports mirror statistics", "cobalt hydroxide export tonnage",
                 "exportations minières déclarations douanières", "mizigo ya shaba forodha",
                 "mineral commodity summaries copper cobalt", "kodi ya forodha madini"),
        languages=("en", "fr", "sw"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public (UN and USGS terms)",
        notes="THE MIRROR IS THE MEASUREMENT: what the DRC and Zambia say they exported against "
              "what China, South Africa and the transit countries say they imported. The gap is "
              "informative in both directions and is the only independent check on a state's own "
              "production table"),
    # ---- source graph
    source_class(
        "cb_source_graph", "What the other nine cite: EITI reconciliation for both countries, the "
                           "IMF Article IV and programme documents, the World Bank and AfDB "
                           "country data, and the citation graph that links a ministry number to "
                           "an operator's own disclosure",
        layer="source_graph",
        roots=("https://eiti.org", "https://www.imf.org", "https://data.worldbank.org",
               "https://openalex.org"),
        queries=("rapport de conciliation ITIE RDC", "EITI Zambia reconciliation report",
                 "Article IV consultation staff report", "selon le ministère des mines",
                 "kwa mujibu wa wizara ya madini", "monga momwe boma linanenera",
                 "extended credit facility review board date"),
        languages=("fr", "en", "sw", "ny"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="EITI IS THE RECONCILIATION LAYER: it takes what the companies say they paid and "
              "what the state says it received and prints the difference. That is a source graph "
              "with an arithmetic check attached, which almost no other ground in this pack has"),
    source_class(
        "cb_civil_society", "The civil-society and investigative ground that dates a Congolese "
                            "decision before the gazette prints it: Resource Matters, Global "
                            "Witness, the Carter Center's RDC programme, AFREWATCH and Publish "
                            "What You Pay",
        layer="source_graph",
        roots=("https://resourcematters.org", "https://www.globalwitness.org",
               "https://www.cartercenter.org", "https://www.pwyp.org"),
        queries=("contrats miniers RDC analyse", "transparence des revenus miniers",
                 "chaîne d'approvisionnement du cobalt diligence", "wachimbaji haki",
                 "mining contract review Zambia", "beneficial ownership mining licence"),
        languages=("fr", "en", "sw"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public (CC in several cases)",
        notes="THE EXPANSION EDGES. These organisations read the contracts and the gazette for a "
              "living and publish dated summaries of decisions the state announces late; the "
              "pack reads them for DATES AND TEXTS and forms no view on their advocacy"),
)

#: NO LAYER IS BLANK FOR THE REGION AS A WHOLE, and that is the measurement rather than a claim of
#: completeness. The refusals that ARE real here are per-jurisdiction and per-layer and are
#: declared by name below, because a layer that Zambia fills and the DRC does not is a real
#: asymmetry and pooling the two without it is how a pack claims coverage of a ground it has
#: never read.
LAYER_ABSENCES: dict[str, str] = {}

#: THE MEASURED REFUSALS (L1.28a).
NO_LAWFUL_GROUND: tuple[dict[str, str], ...] = (
    {"jurisdiction": "cd", "layer": "institutional",
     "reason": "THERE IS NO CONGOLESE SECURITIES MARKET AT ALL. The DRC has no stock exchange, no "
               "public domestic bond curve and no securities tape of any kind; the sovereign "
               "borrows from the central bank, from banks and from bilateral and multilateral "
               "creditors. The mining regulators and the state miner fill this layer for "
               "MINERALS and nothing fills it for securities, which is why no Congolese "
               "equity-mechanics or expiry mechanism appears anywhere in this pack."},
    {"jurisdiction": "cd", "layer": "retail_ecology",
     "reason": "NO LAWFUL RETAIL MARGIN MARKET EXISTS. No Congolese broker is licensed to offer "
               "leverage, no regulator publishes a retail flow, exposure or margin statistic, and "
               "exchange-control practice does not contemplate a resident funding an offshore "
               "margin account. The public social ground IS sourced above at FRINGE credibility "
               "and registered machine_use_allowed=false, and it is all there is."},
    {"jurisdiction": "zm", "layer": "retail_ecology",
     "reason": "the Securities and Exchange Commission licenses a handful of dealing members and "
               "publishes NO aggregate retail positioning, client exposure or margin statistic; "
               "the LuSE reports its investor split only in periodic reviews, which cannot "
               "condition a week. No microstructure claim in this pack may rest on a retail "
               "flow number."},
    {"jurisdiction": "cd", "layer": "app_ecosystem",
     "reason": "THERE IS NO DOMESTIC TRADING-APP ECOSYSTEM. No Congolese intermediary publishes "
               "an API and no retail platform reports flow. The app layer here is the PAYMENT "
               "RAIL -- Airtel Money, Orange Money, Vodacom M-Pesa -- whose subscriber and "
               "transaction statistics ARPTC and the central bank do publish and which is sourced "
               "above. Declaring the layer absent because there is no MetaTrader ecology would be "
               "reading the wrong country."},
    {"jurisdiction": "zm", "layer": "app_ecosystem",
     "reason": "the same: MTN MoMo, Airtel Money and Zamtel Kwacha ARE the app layer and the Bank "
               "of Zambia and ZICTA publish their transaction value; there is no domestic "
               "trading-app ecosystem and no brokerage API to read."},
    {"jurisdiction": "cd", "layer": "academic",
     "reason": "THE DOMESTIC ACADEMIC GROUND IS LARGELY NOT INDEXED. Congolese university output "
               "circulates in print and in French-language local journals that no international "
               "index carries, so what OpenAlex and CORE return for the DRC is overwhelmingly "
               "FOREIGN-AUTHORED WORK ABOUT the DRC. That is a legitimate ground and it is a "
               "DIFFERENT ground, and the pack labels it rather than counting foreign scholarship "
               "as Congolese academic coverage."},
)

#: NATIVE QUERY TERRITORIES -- what the deep-forest miner actually types, per layer. At least
#: three per layer, and every layer carries a FRENCH phrase because the DRC half of this pack is a
#: francophone state, plus Swahili, Lingala, Bemba or Nyanja where the ground is local.
QUERY_TERRITORIES: dict[str, tuple[str, ...]] = {
    "official": ("suspension des exportations de cobalt arrêté", "taux directeur BCC communiqué",
                 "redevance minière recettes RDC", "statutory instrument public holiday Zambia",
                 "ndalama za msonkho wa mgodi", "kusimamisha usafirishaji wa madini",
                 "production de cuivre statistiques officielles"),
    "institutional": ("niveau du lac Kariba aujourd'hui", "amenshi ya Kariba lero",
                      "LuSE market report turnover", "Gécamines rapport annuel",
                      "magetsi mgao ZESCO", "ZCCM-IH umukuba wa Mopani"),
    "academic": ("économie minière du Katanga étude", "hydrologie du bassin du Zambèze",
                 "utafiti wa uchumi wa madini Katanga", "copper price pass-through kwacha study",
                 "prévision saisonnière des pluies Afrique australe"),
    "practitioner": ("coût de production du cuivre RDC", "gharama za uzalishaji wa shaba",
                     "note hebdomadaire marché des changes", "chambre des mines communiqué",
                     "ndalama za banki lipoti la sabata"),
    "retail_ecology": ("taux du dollar aujourd'hui Kinshasa", "bei ya dola leo Lubumbashi",
                       "mtengo wa dollar lero", "talo ya dollar lelo",
                       "prix du cobalt au comptoir Kolwezi", "magetsi lero ku Copperbelt"),
    "app_ecosystem": ("monnaie électronique RDC statistiques", "pesa za simu takwimu",
                      "ndalama za pa foni Zambia", "guichet unique du commerce extérieur",
                      "mizigo ya transit dashboard"),
    "media": ("frontière de Kasumbalesa camions bloqués", "habari za madini Katanga",
              "sango ya mbongo na Kinshasa", "délestage Lubumbashi actualité",
              "magetsi ndi mgodi nkhani", "exportations de cuivre actualité"),
    "archive": ("code minier loi 18/001 texte intégral", "Journal Officiel numéro spécial mines",
                "ordonnance-loi sur les jours fériés", "Hansard mining royalty debate Zambia",
                "Union Minière du Haut-Katanga archives"),
    "physical_economy": ("mizigo ya transit bandari ya Dar es Salaam",
                         "corridor de Lobito premier train de cuivre",
                         "barabara ya Kasumbalesa foleni", "amenshi ya Kariba mita",
                         "chemin de fer de Benguela tonnage", "madzi a Kariba masiku ano",
                         "reli ya TAZARA mizigo"),
    "source_graph": ("selon le ministère des mines", "kwa mujibu wa wizara ya madini",
                     "rapport de conciliation ITIE RDC", "monga momwe boma linanenera",
                     "d'après les sources officielles congolaises"),
}


def layer_counts(classes: Iterable[Mapping[str, Any]] | None = None) -> dict[str, int]:
    rows = SOURCE_CLASSES if classes is None else classes
    out = dict.fromkeys(SOURCE_LAYERS, 0)
    for sc in rows:
        layer = str(sc.get("layer") or "")
        if layer in out and not str(sc.get("id") or "").startswith("absent_"):
            out[layer] += 1
    return out


def layer_terms() -> dict[str, tuple[str, ...]]:
    """Every query this pack declares, by layer: the source classes' own queries plus the
    deep-forest territories, deduplicated and order-preserving."""
    out: dict[str, list[str]] = {layer: [] for layer in SOURCE_LAYERS}
    for sc in SOURCE_CLASSES:
        layer = str(sc.get("layer") or "")
        if layer not in out:
            continue
        for q in sc.get("queries", ()):
            if q not in out[layer]:
                out[layer].append(q)
    for layer, terms in QUERY_TERRITORIES.items():
        if layer not in out:
            continue
        for q in terms:
            if q not in out[layer]:
                out[layer].append(q)
    return {k: tuple(v) for k, v in out.items()}


def source_layer_coverage() -> dict[str, Any]:
    counts = layer_counts()
    missing = {layer: str(LAYER_ABSENCES.get(layer, "")) for layer, n in counts.items() if not n}
    return {"code": CODE, "jurisdictions": JURISDICTIONS, "layer_counts": counts,
            "n_layers_covered": sum(1 for n in counts.values() if n),
            "n_sources": len([s for s in SOURCE_CLASSES
                              if not str(s["id"]).startswith("absent_")]),
            "missing": missing,
            "unexplained_missing": sorted(k for k, why in missing.items() if not why.strip()),
            "machine_use_forbidden": [str(s["id"]) for s in SOURCE_CLASSES
                                      if not s.get("machine_use_allowed", True)],
            "low_weight_kept": [str(s["id"]) for s in SOURCE_CLASSES
                                if s.get("credibility") in ("FRINGE", "UNRELIABLE",
                                                            "CONTRADICTED")],
            "no_lawful_ground": tuple(dict(r) for r in NO_LAWFUL_GROUND),
            "query_territory_counts": {k: len(v) for k, v in QUERY_TERRITORIES.items()},
            "rule": "ten layers, each carrying a source or named ABSENT with a reason; a layer "
                    "one jurisdiction fills and the other does not is declared per jurisdiction "
                    "in NO_LAWFUL_GROUND rather than hidden behind the one that fills it; fringe "
                    "and unreliable PUBLIC material is kept at low weight and never dropped; a "
                    "page whose terms forbid machine extraction is registered "
                    "machine_use_allowed=false, never scraped and never omitted"}


# --------------------------------------------------------------------------- datasets
#: NINETEEN ROWS, SPREAD ACROSS THE TEN LAYERS, each with a `how_to_fetch` a collector can act on.
#: Only the twelve DATASET_FIELDS appear here: the framework's `DatasetRow` has no notes slot, so
#: a thirteenth key would arrive as a coercion note rather than as information.
DATASETS: tuple[dict[str, Any], ...] = (
    {"name": "Zambezi River Authority daily Kariba lake level and usable storage",
     "source": "Zambezi River Authority",
     "coverage": "the daily reading, with the same date a year earlier for comparison; the "
                 "authority's bulletins carry longer history",
     "frequency": "daily", "publication_lag_days": 0.0,
     "revisions": "none; a reading is a reading", "licence": "free, public",
     "history_from": "2000-01", "pit_feasible": False,
     "assets": ("XCUUSD", "XALUSD", "CORN"),
     "mechanism_families": ("physical_flow", "supply_shock", "seasonal_flow"),
     "how_to_fetch": "zambezira.org lake-level page: level in metres above sea level, usable "
                     "storage as a percentage, and the year-earlier comparison. The page shows "
                     "TODAY and keeps no complete archive, so the only point-in-time vintage is a "
                     "daily crawl or a Wayback snapshot -- pit_feasible is False for that reason"},
    {"name": "ZESCO load management schedules and the published shedding hours",
     "source": "ZESCO", "coverage": "2015 onward for the published schedules; 2024-2025 is the "
                                    "deep drought window",
     "frequency": "irregular, revised as inflows change", "publication_lag_days": 0.0,
     "revisions": "reissued rather than revised", "licence": "free, public",
     "history_from": "2015-06", "pit_feasible": False,
     "assets": ("XCUUSD", "XALUSD", "XNGUSD"),
     "mechanism_families": ("supply_shock", "capacity_ramp", "administered_price"),
     "how_to_fetch": "zesco.co.zm announcements and the customer-service notices; the MINES are "
                     "on separate bulk-supply agreements and are shed differently from "
                     "households, which is exactly the split a naive load-shedding series loses"},
    {"name": "Bank of Zambia policy rate, statutory reserve ratio and MPC statements",
     "source": "Bank of Zambia", "coverage": "2012 onward for the policy rate",
     "frequency": "quarterly for the rate, irregular for the reserve ratio",
     "publication_lag_days": 0.0, "revisions": "none", "licence": "free, public",
     "history_from": "2012-04", "pit_feasible": True,
     "assets": ("XCUUSD", "USDZAR", "EURZAR"),
     "mechanism_families": ("policy_surprise", "carry_funding", "liquidity"),
     "how_to_fetch": "boz.zm monetary-policy page: the statement PDF carries the decision, the "
                     "inflation forecast and the bank's own COPPER PRICE ASSUMPTION; the reserve "
                     "ratio arrives separately by circular between meetings and must be collected "
                     "from the circulars list, not from the MPC calendar"},
    {"name": "Bank of Zambia daily interbank exchange rate, intervention and reserves",
     "source": "Bank of Zambia", "coverage": "daily rates from the 1990s; intervention and "
                                             "reserves in the monthly statistics",
     "frequency": "daily for the rate, monthly for the rest", "publication_lag_days": 0.0,
     "revisions": "reserves restated in the monthly bulletin", "licence": "free, public",
     "history_from": "1995-01", "pit_feasible": False,
     "assets": ("XCUUSD", "USDZAR", "ZARJPY"),
     "mechanism_families": ("fixing", "carry_funding", "external_balance"),
     "how_to_fetch": "boz.zm financial-markets daily rate table and the monthly statistics "
                     "bulletin; the daily page overwrites in place, so the vintage is the crawl"},
    {"name": "Zambia Statistics Agency consumer price index and quarterly GDP",
     "source": "ZamStats", "coverage": "2009 base onward", "frequency": "monthly and quarterly",
     "publication_lag_days": 15.0, "revisions": "rebasing and routine restatement",
     "licence": "free, public", "history_from": "2009-01", "pit_feasible": True,
     "assets": ("CORN", "WHEAT", "USDZAR"),
     "mechanism_families": ("release_surprise", "pass_through", "nominal_demand"),
     "how_to_fetch": "zamstats.gov.zm monthly bulletin; the FOOD line carries the drought and the "
                     "mining line is the statistics agency's own output estimate, which is a "
                     "different number from the ministry's and from the royalty receipt"},
    {"name": "Zambian copper production by mine and the national output series",
     "source": "Ministry of Mines and Minerals Development",
     "coverage": "2000 onward at the national level; the by-mine split is patchier",
     "frequency": "monthly and quarterly, irregular in practice", "publication_lag_days": 60.0,
     "revisions": "restated at the year close", "licence": "free, public",
     "history_from": "2000-01", "pit_feasible": False,
     "assets": ("XCUUSD", "XZNUSD", "XPBUSD"),
     "mechanism_families": ("physical_flow", "capacity_ramp", "supply_shock"),
     "how_to_fetch": "mmmd.gov.zm statistics and the annual reports, cross-checked against the "
                     "Chamber of Mines and the operators' own quarterly disclosures; a missing "
                     "month is UNMEASURED and is never interpolated"},
    {"name": "Zambia Revenue Authority mineral royalty and mining tax receipts",
     "source": "Zambia Revenue Authority", "coverage": "2015 onward in the published reports",
     "frequency": "monthly and annual", "publication_lag_days": 45.0,
     "revisions": "reclassified between the monthly release and the annual report",
     "licence": "free, public", "history_from": "2015-01", "pit_feasible": True,
     "assets": ("XCUUSD", "USDZAR"),
     "mechanism_families": ("fiscal_flow", "physical_flow", "external_balance"),
     "how_to_fetch": "zra.org.zm revenue bulletins and the annual report; the royalty line is a "
                     "COUNTED TONNE AT AN LME-REFERENCED PRICE and is therefore an independent "
                     "read on output, and the VAT refund arrears line beside it is the mines' own "
                     "working-capital constraint"},
    {"name": "Banque Centrale du Congo condense hebdomadaire: taux directeur, FX rate, reserves",
     "source": "Banque Centrale du Congo", "coverage": "2010 onward in the posted PDFs",
     "frequency": "weekly", "publication_lag_days": 7.0,
     "revisions": "restated between issues", "licence": "free, public",
     "history_from": "2010-01", "pit_feasible": False,
     "assets": ("XCUUSD", "XAUUSD", "USDZAR"),
     "mechanism_families": ("liquidity", "fixing", "capital_control_stress"),
     "how_to_fetch": "bcc.cd publications: the condense PDFs carry the taux directeur, the "
                     "indicative rate, the monetary base and the reserve line. In FRENCH, posted "
                     "irregularly and sometimes replaced in place, so the vintage is the crawl"},
    {"name": "Congolese copper and cobalt production and export tonnage by province",
     "source": "Ministere des Mines RDC and the EITI-RDC reconciliation",
     "coverage": "2010 onward, with the EITI reports reconciling from 2007",
     "frequency": "quarterly and annual", "publication_lag_days": 120.0,
     "revisions": "restated in the EITI cycle", "licence": "free, public",
     "history_from": "2010-01", "pit_feasible": False,
     "assets": ("XCUUSD", "XNIUSD", "XAUUSD"),
     "mechanism_families": ("physical_flow", "capacity_ramp", "supply_shock"),
     "how_to_fetch": "mines.gouv.cd statistics plus the EITI-RDC reconciliation reports on "
                     "eiti.org; the EITI report is the only version with an arithmetic check "
                     "against what the companies say they paid"},
    {"name": "ARECOMS cobalt export decisions: the suspension, the extension and the quotas",
     "source": "ARECOMS, the Ministere des Mines and the trade press",
     "coverage": "2024 onward, when ARECOMS was created; the underlying strategic-substance "
                 "regime dates from the 2018 Code minier and its arretes",
     "frequency": "irregular, dated decisions", "publication_lag_days": 0.0,
     "revisions": "superseded rather than revised", "licence": "free, public",
     "history_from": "2024-01", "pit_feasible": True,
     "assets": ("XCUUSD", "XNIUSD"),
     "mechanism_families": ("administered_price", "supply_shock", "regime_break"),
     "how_to_fetch": "the ARECOMS and ministry communiques carried on mines.gouv.cd and "
                     "primature.cd, stamped against Radio Okapi and Actualite.cd and confirmed "
                     "against the Journal Officiel text on leganet.cd; the press date and the "
                     "gazette date are DIFFERENT and the gap is itself an observable"},
    {"name": "DRC Journal Officiel and the Code minier text with its amending arretes",
     "source": "Journal Officiel de la RDC via leganet.cd",
     "coverage": "the 2002 Code minier, the 2018 amending law and the arretes since",
     "frequency": "irregular", "publication_lag_days": 30.0, "revisions": "none once gazetted",
     "licence": "free, public", "history_from": "2002-07", "pit_feasible": True,
     "assets": ("XCUUSD", "XNIUSD", "XAUUSD"),
     "mechanism_families": ("regime_break", "administered_price", "fiscal_flow"),
     "how_to_fetch": "leganet.cd carries the dated text of the Code minier, the 2018 amendment "
                     "and the arrete that declared cobalt a strategic substance at a 10% royalty; "
                     "the official gazette is not reliably machine-readable and this is the "
                     "practical citation"},
    {"name": "Corridor throughput and transit tonnage by destination country",
     "source": "Tanzania Ports Authority, the Central Corridor TTFA, Transnet, TAZARA and the "
               "Beira and Nacala operators",
     "coverage": "2015 onward where published; the Lobito series begins in 2024",
     "frequency": "monthly and quarterly, irregular", "publication_lag_days": 60.0,
     "revisions": "restated in annual reports", "licence": "free, public",
     "history_from": "2015-01", "pit_feasible": False,
     "assets": ("XCUUSD", "XBRUSD", "USDZAR"),
     "mechanism_families": ("chokepoint", "transfer", "physical_flow"),
     "how_to_fetch": "tanzaniaports.go.tz and centralcorridor-ttfa.org for Dar es Salaam, "
                     "transnet.net for Durban, tazarasite.com for the rail; the Lobito tonnage is "
                     "reported through the Angolan ministry and the trade press. THE "
                     "TRANSIT-BY-COUNTRY SPLIT is what makes this a chokepoint observable, and "
                     "`east_africa` owns the Tanzanian end of the same series"},
    {"name": "Kasumbalesa border queue length and customs clearance time",
     "source": "the corridor dashboards, the DGDA and ZRA customs postings and the local press",
     "coverage": "reported episodically from 2018; there is no continuous official series",
     "frequency": "irregular", "publication_lag_days": 3.0,
     "revisions": "none", "licence": "free, public", "history_from": "2018-01",
     "pit_feasible": False, "assets": ("XCUUSD", "XBRUSD"),
     "mechanism_families": ("chokepoint", "failure", "physical_flow"),
     "how_to_fetch": "centralcorridor-ttfa.org transit-time postings, the DGDA and ZRA notices, "
                     "and the Congolese and Zambian press reporting of queue lengths in "
                     "kilometres. THIS IS AN EPISODIC SERIES AND THE PACK SAYS SO: a week with no "
                     "report is UNMEASURED, not a week with no queue"},
    {"name": "UN Comtrade mirror statistics for refined copper, concentrate and cobalt",
     "source": "UN Comtrade", "coverage": "2000 onward for both reporters and their partners",
     "frequency": "annual, monthly for some partners", "publication_lag_days": 300.0,
     "revisions": "heavily revised", "licence": "free, public (UN terms)",
     "history_from": "2000-01", "pit_feasible": True,
     "assets": ("XCUUSD", "XNIUSD", "USDCNH"),
     "mechanism_families": ("external_balance", "physical_flow", "transfer"),
     "how_to_fetch": "comtradeplus.un.org for HS 7403 (refined copper), 2603 (copper ore and "
                     "concentrate) and 8105 (cobalt); read BOTH the Congolese and Zambian "
                     "declarations and the Chinese, South African and transit-country mirrors -- "
                     "the gap is the measurement and it is informative in both directions"},
    {"name": "ICSG monthly copper world balance and the USGS country production table",
     "source": "International Copper Study Group and the US Geological Survey",
     "coverage": "the ICSG balance monthly from the 1990s; the USGS summaries annually",
     "frequency": "monthly and annual", "publication_lag_days": 60.0,
     "revisions": "the balance is revised every month", "licence": "ICSG press release free and "
                                                                  "the bulletin subscription; "
                                                                  "USGS open data",
     "history_from": "1995-01", "pit_feasible": True,
     "assets": ("XCUUSD", "XNIUSD", "XZNUSD"),
     "mechanism_families": ("inventory", "external_balance", "physical_flow"),
     "how_to_fetch": "the ICSG press release on icsg.org gives the headline balance and the "
                     "bulletin itself is subscription and REGISTERED rather than scraped; the "
                     "USGS Mineral Commodity Summaries chapter is open data and is the citation "
                     "that dates the DRC's overtaking of Peru"},
    {"name": "Cobalt supply, demand and the Congolese share of world output",
     "source": "Cobalt Institute and the USGS cobalt chapter",
     "coverage": "2010 onward", "frequency": "annual with periodic market updates",
     "publication_lag_days": 120.0, "revisions": "restated annually",
     "licence": "summary public; the detailed series are members-only",
     "history_from": "2010-01", "pit_feasible": True,
     "assets": ("XCUUSD", "XNIUSD"),
     "mechanism_families": ("supply_shock", "administered_price", "inventory"),
     "how_to_fetch": "cobaltinstitute.org public market reports and the USGS chapter; the "
                     "members-only detail is REGISTERED and not extracted. THE ROUTE TO A CELL IS "
                     "ALWAYS THROUGH COPPER OR NICKEL: cobalt is a by-product and there is no "
                     "cobalt contract in the broker registry"},
    {"name": "IMF Article IV and programme documents for both countries",
     "source": "International Monetary Fund",
     "coverage": "2019 onward for the Zambian programme; the Congolese ECF from 2021",
     "frequency": "per review, roughly semi-annual", "publication_lag_days": 30.0,
     "revisions": "restated between reviews", "licence": "free, public",
     "history_from": "2019-01", "pit_feasible": True,
     "assets": ("USDZAR", "US500", "XCUUSD"),
     "mechanism_families": ("regime_break", "fiscal_flow", "external_balance"),
     "how_to_fetch": "imf.org country pages for ZMB and COD: the staff reports carry reserve, "
                     "arrears, mining-revenue and debt-restructuring numbers that both states "
                     "publish late or not at all, and the Board dates are the dated clock"},
    {"name": "Zambian sovereign restructuring milestones and the Common Framework record",
     "source": "the Ministry of Finance, the Official Creditor Committee communiques and the "
               "bondholder committee statements",
     "coverage": "2020-11 onward", "frequency": "irregular, dated events",
     "publication_lag_days": 1.0, "revisions": "superseded rather than revised",
     "licence": "free, public", "history_from": "2020-10", "pit_feasible": True,
     "assets": ("USDZAR", "US500", "EURZAR"),
     "mechanism_families": ("regime_break", "fiscal_flow", "positioning"),
     "how_to_fetch": "mof.gov.zm announcements, the IMF and French Treasury co-chair communiques "
                     "for the Official Creditor Committee, and the bondholder committee "
                     "statements; every milestone is a dated press release and the sequence is "
                     "the era table of CB-H"},
    {"name": "Mobile-money transaction value and the National Payment Systems statistics",
     "source": "Bank of Zambia, ZICTA and ARPTC",
     "coverage": "2016 onward for Zambia; the Congolese series is thinner",
     "frequency": "monthly and quarterly", "publication_lag_days": 45.0,
     "revisions": "restated", "licence": "free, public", "history_from": "2016-01",
     "pit_feasible": True, "assets": ("USDZAR", "CORN", "SUGAR"),
     "mechanism_families": ("nominal_demand", "liquidity", "transfer"),
     "how_to_fetch": "boz.zm National Payment Systems reports, zicta.zm and arptc.cd; this is the "
                     "only HIGH-FREQUENCY NOMINAL SERIES either economy publishes and it is the "
                     "app layer of this pack, not a trading-platform statistic"},
)


# --------------------------------------------------------------------------- actors
#: EIGHTEEN ACTORS, EIGHT PER JURISDICTION AND TWO REGIONAL. The floor is twelve for a single
#: country and a two-country pack that stops at twelve has read one country and guessed once.
#: Every row carries all eleven fields, and the FALSIFIER is the one that decides whether the row
#: is a research object or a story. Every national champion in this region -- the Katangan
#: operators, the Zambian mines, the two state holding companies -- appears HERE and never as an
#: instrument (two-lane order, 2026-09-06).
ACTORS: tuple[dict[str, Any], ...] = (
    # ---------------------------------------------------------------- DR Congo
    {"name": "ARECOMS, the Congolese strategic-minerals regulator that turned the cobalt tap off",
     "holds": "the legal power to suspend, quota and allocate the export of a substance the "
              "country supplies roughly seventy per cent of, and the register of who may ship it",
     "forced_to": ("defend a cobalt price that had collapsed under its own country's supply "
                   "growth, because the fiscal receipts depend on it",
                   "publish each decision as a dated communique before the Journal Officiel "
                   "carries the instrument",
                   "allocate quota volumes operator by operator once an outright ban became "
                   "politically and commercially unsustainable"),
     "when": "irregular and dated: the suspension took effect 2025-02-22, was extended in June "
             "2025 and was replaced by a quota regime from 2025-10-16",
     "information": ("the stock of hydroxide already at the ports and in transit, which decides "
                     "how long a ban binds before it bites",
                     "the operators' own shipment plans, filed with the regulator",
                     "the fiscal cost of the suspension to the treasury it answers to"),
     "constraints": ("a copper business that keeps running whatever happens to cobalt, so the "
                     "ban cannot stop the mine, only the by-product shipment",
                     "storage capacity for a hydroxide that keeps being produced",
                     "the Indonesian nickel-cobalt supply that grows whether the DRC ships or not",
                     "a treasury that needs the export duty it has just suspended"),
     "instruments": ("XCUUSD", "XNIUSD"),
     "counterparties": ("the Katangan copper-cobalt operators and their Chinese parents",
                        "the Chinese refiners who buy the hydroxide",
                        "the battery and superalloy buyers at the end of the chain",
                        "the treasury and the customs administration"),
     "observables": ("the dated communiques and the gazetted arretes that follow them",
                     "Congolese cobalt export tonnage in the customs and mirror statistics",
                     "the price-reporting agencies' hydroxide assessment, registered and not read "
                     "by machine",
                     "the quota allocations as reported operator by operator"),
     "impact": "a sovereign supply intervention in a by-product, which reaches COPPER through the "
               "cost curve: remove the cobalt credit from a Katangan copper tonne and the tonne "
               "costs more, and remove it from a nickel sulphide tonne and the same thing happens "
               "at the other end of the chain",
     "persistence": "a regime, not an event: the suspension and the quota partition every "
                    "Congolese cobalt series from 2025-02-22 and the boundary does not decay",
     "falsifier": "Congolese cobalt EXPORT tonnage in the mirror statistics shows no break at "
                  "2025-02-22 or at 2025-10-16 once the pre-ban shipment surge is controlled for, "
                  "which would make the intervention an announcement and not a flow event",
     "notes": "THE EVENT THAT MAKES CB-A A DOMAIN. A state that controls three quarters of a "
              "commodity and publishes the date it stops selling it is as close to a clean "
              "supply treatment as a commodity market ever offers"},
    {"name": "Gecamines, the Congolese state miner and the landlord of the Katangan joint ventures",
     "holds": "the historic Katangan concessions, minority stakes and royalty entitlements in the "
              "joint ventures that mine them, and a seat at every renegotiation",
     "forced_to": ("collect royalties and entry premia from partners whose disclosures it "
                   "disputes", "publish an annual report that dates the disputes",
                   "fund a state portfolio out of a share of output it does not operate"),
     "when": "annually for the report; continuously for the disputes, which surface as dated "
             "letters, audits and renegotiation announcements",
     "information": ("the joint ventures' cost and transfer-pricing arrangements, which it audits",
                     "the true entitlement position before a partner discloses it",
                     "the state's own fiscal need in any given quarter"),
     "constraints": ("no operating capacity of its own at scale, so a dispute cannot become "
                     "production",
                     "partners who are among the largest mining companies in the world",
                     "a debt position that makes an immediate cash settlement attractive"),
     "instruments": ("XCUUSD", "XNIUSD"),
     "counterparties": ("the Chinese and Western operators of the joint ventures",
                        "the Ministere des Mines and the treasury",
                        "the EITI reconciliation process", "the international arbitration forums"),
     "observables": ("the annual report and the dated dispute announcements",
                     "the EITI reconciliation gap between declared payments and declared receipts",
                     "royalty and entry-premium receipts in the ministry's own statistics"),
     "impact": "a renegotiation raises the Congolese state's take on a mine that produces a "
               "measurable share of world copper; it changes incentives to expand and it changes "
               "the cost curve, both slowly and both measurably",
     "persistence": "slow and structural; the disputes run for years and resolve in dated "
                    "settlements",
     "falsifier": "settlement and renegotiation dates show no change in the affected operations' "
                  "output or capital plans over the following four quarters against matched "
                  "Congolese mines with no dispute, which would make the dispute fiscal theatre",
     "notes": "A STATE HOLDING COMPANY IS AN ACTOR AND NEVER AN INSTRUMENT. Its disclosures are "
              "read for ownership and output facts and for nothing else"},
    {"name": "The large Katangan copper-cobalt operators, as a class",
     "holds": "the Kolwezi and Fungurume orebodies and the concentrators, leach plants and "
              "hydroxide circuits that turn them into shipped tonnes",
     "forced_to": ("ramp on published schedules once the capital is committed, because an idle "
                   "plant is the most expensive thing in mining",
                   "ship through one of exactly four corridors, none of which they control",
                   "sell cobalt hydroxide into whatever regime the regulator declares that quarter",
                   "disclose quarterly production to their own listing regulators abroad"),
     "when": "quarterly for the production disclosures; continuously for the physical shipments",
     "information": ("the actual grade and recovery of the month, before anyone else",
                     "the stock of hydroxide and cathode at the mine and at the port",
                     "the corridor that is working this week"),
     "constraints": ("power availability and cost in a region with a chronic deficit",
                     "acid and reagent supply, which arrives by the same four roads",
                     "the export regime for the by-product",
                     "a grade profile that is exceptional and finite"),
     "instruments": ("XCUUSD", "XNIUSD", "XBRUSD"),
     "counterparties": ("the Chinese refiners and traders who take the offtake",
                        "Gecamines as joint-venture partner and landlord",
                        "the transporters and the corridor operators",
                        "the power utilities and the regional power pool"),
     "observables": ("quarterly production and shipment disclosures",
                     "the ministry's provincial production table",
                     "customs export tonnage and the importing countries' mirror statistics",
                     "announced expansion milestones and their slippage"),
     "impact": "THIS IS THE MARGINAL TONNE OF WORLD COPPER SUPPLY. A phased ramp here is a "
               "measurable share of global growth, and the desk can trade the metal directly",
     "persistence": "multi-quarter; a ramp is a schedule and a schedule slips in public",
     "falsifier": "announced ramp milestones carry no information about XCUUSD returns over any "
                  "horizon once the ICSG world balance and the Chinese import series are "
                  "controlled for, which would mean the expansion was already in the price",
     "notes": "NAMED AS A CLASS ON PURPOSE. Each of these operations belongs to a listed parent "
              "and the two-lane order forbids hunting any of them statistically; what is testable "
              "is the TONNAGE, and the tonnage is public"},
    {"name": "The Banque Centrale du Congo FX desk in a dollarised economy",
     "holds": "the indicative rate, the reserve position, the taux directeur and the franc "
              "liquidity of a country where most deposits are in somebody else's currency",
     "forced_to": ("sell dollars to steady a franc whose depreciation is a price level and not "
                   "only a price",
                   "publish a weekly condense and a daily indicative rate",
                   "meet the reserve and arrears targets of an IMF arrangement"),
     "when": "daily for the rate, weekly for the condense, irregular for the taux directeur",
     "information": ("the mining export receipts arriving in the banking system before they are "
                     "published", "the size of its own next intervention",
                     "the programme's disbursement calendar before it is public"),
     "constraints": ("a reserve position thin against the import bill",
                     "an economy in which raising a franc policy rate steers a small corner of a "
                     "mostly dollar system",
                     "a fiscal deficit that has historically been monetised",
                     "mining receipts that arrive in dollars and often stay offshore"),
     "instruments": ("XCUUSD", "XAUUSD", "USDZAR"),
     "counterparties": ("the commercial banks and their importer clients",
                        "the mining companies whose receipts are the reserve base",
                        "the treasury", "the IMF and the bilateral creditors"),
     "observables": ("the daily indicative rate and its gap to the street rate",
                     "the weekly reserve and monetary-base lines",
                     "the taux directeur decisions and the bill auction results"),
     "impact": "the franc is a CONDITIONING STATE for fiscal and social stress in the copper "
               "provinces, not a leg the desk can trade; its stress shows up as import rationing "
               "and as pressure on the mining fiscal regime",
     "persistence": "quarters; a dollarised economy's exchange rate moves in steps and settles",
     "falsifier": "the franc's depreciation episodes carry no measurable relation to Congolese "
                  "mining policy announcements or to export tonnage in the following two "
                  "quarters, which would make CB-D a macro domain with no copper content at all",
     "notes": "THE PACK REFUSES TO PRETEND THE FRANC IS THE MECHANISM. Mining receipts are "
              "dollars and mining costs are largely dollars; the franc matters where the state's "
              "fiscal stress meets the mining fiscal regime, and that is where CB-D tests it"},
    {"name": "The Katangan artisanal mining sector and the depot and comptoir chain",
     "holds": "a material share of Congolese cobalt output and a smaller share of copper, moved "
              "through depots and comptoirs that buy against an assay and a dollar price",
     "forced_to": ("sell at the depot price of the day, because there is no storage and no credit",
                   "move into and out of the sector as the price moves, which makes the supply "
                   "response fast and visible in the aggregate",
                   "operate inside whatever channel the state declares for the strategic "
                   "substance"),
     "when": "daily at the depot; the aggregate shows up in the ministry's and EITI's annual "
             "reconciliation and in the NGO reporting in between",
     "information": ("the depot price of the day, which no one publishes as a series",
                     "which pits are working and which are flooded",
                     "the buying appetite of the comptoirs, who see the export price first"),
     "constraints": ("no capital, no storage and no ability to wait for a better price",
                     "the rainy season, which floods workings from November to April",
                     "a state channel that has been asserted, relaxed and asserted again"),
     "instruments": ("XCUUSD", "XNIUSD"),
     "counterparties": ("the comptoirs and the depots", "the industrial operators who buy "
                        "artisanal feed into their circuits", "the state channel and its agents",
                        "the downstream buyers running supply-chain due diligence"),
     "observables": ("the artisanal share in the ministry's and EITI's production reconciliation",
                     "the export tonnage that industrial output alone cannot account for",
                     "the depot-price reporting in the NGO and trade literature, which is "
                     "episodic and is treated as episodic"),
     "impact": "THE FASTEST SUPPLY RESPONSE IN THE COBALT MARKET. Artisanal output rises and "
               "falls with the price within months, which makes it the mechanism by which a "
               "cobalt price move becomes a cobalt supply move -- and therefore a change in the "
               "by-product credit on the copper cost curve",
     "persistence": "months; the response is fast and it is reversible",
     "falsifier": "the reconciled artisanal share shows no relation to the lagged cobalt price "
                  "once the industrial ramp and the export regime are controlled for, which would "
                  "mean the sector is price-inelastic and CB-E has no supply channel",
     "notes": "THE DESK RECORDS WHAT IS PUBLISHED ABOUT PRODUCTION, FLOWS AND POLICY AND NOTHING "
              "ELSE. The human-rights concerns in this supply chain are well documented and they "
              "are not this pack's subject: no personal data about any individual miner is "
              "collected or sought, and no source here is accessed other than as published "
              "(ACCESS_CONSTRAINTS)"},
    {"name": "The DGDA customs administration and the Congolese side of Kasumbalesa",
     "holds": "the export declarations, the duty assessment and the physical clearance of every "
              "lorry that leaves Katanga by road",
     "forced_to": ("clear or hold each consignment against a documentary and fiscal check",
                   "collect export duties that are a material share of state revenue",
                   "operate a border post whose throughput is the corridor's binding constraint"),
     "when": "continuously, with published notices when procedures or duties change",
     "information": ("the true export tonnage before the ministry publishes it",
                     "the queue at the post today",
                     "the duty changes coming in the next finance law"),
     "constraints": ("physical capacity at a single road crossing",
                     "two national calendars on the two sides of it",
                     "a revenue target that makes releasing a lorry and taxing it competing aims"),
     "instruments": ("XCUUSD", "XBRUSD"),
     "counterparties": ("the Zambian Revenue Authority on the other side of the post",
                        "the transporters and the clearing agents",
                        "the mining operators and their logistics contractors"),
     "observables": ("customs export declarations and the duty receipts",
                     "the published procedural notices",
                     "the reported queue length and clearance time at Kasumbalesa"),
     "impact": "a clearance slowdown at one road post delays a measurable share of world copper "
               "by days to weeks, which is an inventory-timing effect and not a supply effect -- "
               "and the pack insists on that distinction",
     "persistence": "days to weeks; queues clear",
     "falsifier": "reported Kasumbalesa queue episodes carry no measurable relation to XCUUSD "
                  "over the following two to eight weeks once corridor substitution and Chinese "
                  "import volumes are controlled for, which would mean the queue is absorbed by "
                  "inventory and never reaches a price",
     "notes": "the honest prior is that it does NOT reach the price, because inventory exists "
              "precisely to absorb this; the point of CB-L is to measure that rather than assume "
              "it either way"},
    {"name": "The Congolese and Zambian long-haul transporters and clearing agents",
     "holds": "the trucks that carry cathode and hydroxide three thousand kilometres to a port "
              "and bring acid, reagents and fuel back",
     "forced_to": ("choose a corridor each week on price, queue and reliability",
                   "carry the fuel cost of a three-thousand-kilometre round trip",
                   "wait at whichever border is slow"),
     "when": "continuously; the corridor choice is a weekly commercial decision",
     "information": ("which border is moving today, before any dashboard says so",
                     "the freight rate on each of the four routes",
                     "where the empty backhaul is"),
     "constraints": ("fuel price and availability", "road and rail condition in the rainy season",
                     "the capacity of each port at the far end",
                     "the rates the mines will pay"),
     "instruments": ("XCUUSD", "XBRUSD"),
     "counterparties": ("the mining operators and their logistics contractors",
                        "the ports and the rail concessionaires",
                        "the two customs administrations", "the fuel suppliers"),
     "observables": ("the corridor freight rates where reported",
                     "transit times on the corridor dashboards",
                     "the transit-tonnage split by port, which is the revealed choice"),
     "impact": "the corridor SHARE is the observable that separates a chokepoint from a "
               "re-routing: tonnage that leaves Dar es Salaam and appears at Lobito carries no "
               "supply information at all, and neither pack can see that alone",
     "persistence": "weeks; a re-route is a decision and it reverses",
     "falsifier": "corridor share shifts show no relation to the relative transit times and "
                  "freight rates that supposedly drive them, which would mean the split is "
                  "contractual rather than economic and CB-K's mechanism is not a mechanism",
     "notes": "THE STRONGEST REASON `east_africa` IS NAMED FIRST IN INTERACTIONS: the Dar es "
              "Salaam end of this series belongs to that pack and the Katangan end belongs here"},
    {"name": "ARSP, the Congolese subcontracting regulator, and the localisation regime",
     "holds": "the power to enforce the law reserving subcontracting in the private sector to "
              "Congolese-majority companies, across an industry that runs on contractors",
     "forced_to": ("apply a statutory localisation requirement to mining service contracts",
                   "publish decisions and sanctions that name the contracts affected",
                   "balance enforcement against the risk of stopping a mine"),
     "when": "irregular; enforcement intensified through 2023 and 2024 and arrives as dated "
             "decisions and public statements",
     "information": ("the contract register of who subcontracts what to whom",
                     "the enforcement timetable before it is announced"),
     "constraints": ("a domestic contracting sector that cannot absorb the whole requirement at "
                     "once", "operators who can slow capital spending in response",
                     "a government that wants both the localisation and the investment"),
     "instruments": ("XCUUSD",),
     "counterparties": ("the mining operators and their international service contractors",
                        "the Congolese contracting companies the law favours",
                        "the Ministere des Mines and the Primature"),
     "observables": ("the published decisions and sanction announcements",
                     "capital spending and contractor changes at the affected operations",
                     "the industry association's public responses"),
     "impact": "a cost and schedule effect on Congolese mining capital projects, which is a slow "
               "channel into the supply ramp and therefore into XCUUSD over quarters",
     "persistence": "quarters to years; a regulatory regime, not an event",
     "falsifier": "enforcement episodes show no measurable effect on the affected operations' "
                  "capital spending or ramp schedules against matched Congolese operations, which "
                  "would make the regime a compliance cost and not a supply variable",
     "notes": "kept small and declared small; it is a real dated regime and its price channel is "
              "weak, and saying so is better than inflating it"},
    # ---------------------------------------------------------------- Zambia
    {"name": "ZESCO and the load-management desk that rations power to the smelters",
     "holds": "the Zambian generation fleet, the bulk-supply agreements with the mines and the "
              "schedule that decides who is shed and for how many hours",
     "forced_to": ("ration a deficit when the lake is low, on a published schedule",
                   "buy imported power through the regional pool at prices well above the "
                   "domestic tariff", "keep the mines supplied under contracts it cannot simply "
                   "abandon, while shedding households first"),
     "when": "the schedule is published and revised as inflows change; the 2024-2025 drought is "
             "the deep case",
     "information": ("the true generation position hour by hour",
                     "the allocation the river authority will grant next",
                     "which mines have their own import arrangements"),
     "constraints": ("Kariba usable storage above the minimum operating level",
                     "a tariff below cost, which limits what it can buy",
                     "transmission capacity to import",
                     "a political cost to shedding households and an economic cost to shedding "
                     "mines"),
     "instruments": ("XCUUSD", "XALUSD", "XNGUSD"),
     "counterparties": ("the Zambezi River Authority, which allocates the water",
                        "the mining operators on bulk-supply agreements",
                        "the Southern African Power Pool and its members",
                        "the Energy Regulation Board"),
     "observables": ("the published load-management schedule and the shedding hours",
                     "generation against installed capacity",
                     "imported power volumes and the pool price",
                     "the mines' own disclosures of power curtailment"),
     "impact": "SMELTING AND ELECTROWINNING ARE ELECTRICITY IN PHYSICAL FORM. Curtailed power is "
               "curtailed copper, and it is curtailed on a published schedule that a desk can "
               "read the same week",
     "persistence": "seasons; the constraint follows the hydrological year and the drought cycle",
     "falsifier": "published mine curtailment episodes show no measurable relation to Zambian "
                  "copper output in the following quarter, which would mean the mines' own "
                  "generation and import arrangements fully insulate them and CB-F's channel is "
                  "closed at the plant gate",
     "notes": "THE DISTINCTION THAT MATTERS is between household shedding and MINE curtailment: "
              "the headline hours are mostly the former and only the latter is copper"},
    {"name": "The Zambezi River Authority, which allocates the water before anyone generates it",
     "holds": "the Kariba reservoir jointly for Zambia and Zimbabwe, the daily lake-level reading "
              "and the water allocation each utility may draw",
     "forced_to": ("publish the lake level daily and the allocation decisions as they are made",
                   "hold the lake above its minimum operating level or lose the plant",
                   "split a scarce resource between two sovereign utilities"),
     "when": "daily for the reading; the allocation is set and revised through the hydrological "
             "year, which runs from the November-April rains to the September-November minimum",
     "information": ("the inflow at Victoria Falls before it reaches the lake",
                     "the allocation decision before it is announced",
                     "the seasonal forecast it plans against"),
     "constraints": ("rainfall in a catchment that spans several countries",
                     "a minimum operating level that is a hard physical floor",
                     "two governments with the same shortage"),
     "instruments": ("XCUUSD", "XALUSD", "CORN"),
     "counterparties": ("ZESCO and the Zimbabwean utility",
                        "the two governments", "the regional power pool"),
     "observables": ("THE DAILY LAKE LEVEL AND USABLE STORAGE, published",
                     "the inflow readings at Victoria Falls",
                     "the announced allocations to each utility",
                     "the seasonal rainfall outlooks that precede all of it"),
     "impact": "the single most valuable series in this pack: a daily public number that is "
               "causally upstream of smelter power and therefore of a material share of world "
               "copper smelting, trading against a liquid contract",
     "persistence": "seasonal and slow-moving; the lake fills and draws down on an annual cycle "
                    "and a drought persists across years",
     "falsifier": "the lake level and its seasonal anomaly carry no information about Zambian "
                  "copper output or about XCUUSD at any horizon once the global balance and the "
                  "Chinese import series are controlled for, which would mean the power "
                  "constraint never binds hard enough to reach a price",
     "notes": "THE FORECAST LEG IS THE EX-ANTE ONE. The level is a state; the seasonal rainfall "
              "outlook published months earlier is a forecast OF the state, and a cell "
              "conditioned on the outlook is testing something genuinely ex-ante"},
    {"name": "The Bank of Zambia's Monetary Policy Committee and its FX desk",
     "holds": "the policy rate, the STATUTORY RESERVE RATIO, the reserve position and a daily "
              "interbank mark on the most copper-correlated currency on earth",
     "forced_to": ("decide quarterly on a published calendar and publish the statement",
                   "use the reserve ratio between meetings when the kwacha moves faster than the "
                   "calendar", "publish its own copper price assumption inside the inflation "
                   "forecast", "rebuild reserves under an IMF arrangement"),
     "when": "quarterly for the rate; the reserve ratio changes arrive by circular at any time",
     "information": ("the intervention it is about to make",
                     "the mining sector's dollar conversion flow through the banking system",
                     "the programme review calendar"),
     "constraints": ("an open capital account, so the rate has to do the work",
                     "a fiscal position still normalising after a default",
                     "an inflation rate driven by food and fuel more than by demand"),
     "instruments": ("USDZAR", "EURZAR", "ZARJPY", "XCUUSD"),
     "counterparties": ("the commercial banks", "the mining companies converting dollars",
                        "the treasury and its bond auctions", "the IMF"),
     "observables": ("the policy rate and the reserve-ratio circulars",
                     "the daily interbank rate and the intervention amounts",
                     "THE BANK'S OWN PUBLISHED COPPER PRICE ASSUMPTION"),
     "impact": "the kwacha confirms a copper or fiscal shock rather than causing one; the "
               "executable consequence sits on the ZAR carriers, and the carrier is labelled a "
               "carrier everywhere it is used",
     "persistence": "quarters for the rate cycle; days for an intervention",
     "falsifier": "reserve-ratio changes show no measurable effect on the kwacha or on the "
                  "carriers beyond what the policy rate and the copper price already explain, "
                  "which would make the instrument a liquidity operation with no price content",
     "notes": "A CENTRAL BANK THAT PUBLISHES ITS COMMODITY FORECAST is handing this desk a free "
              "expectation series for the instrument it trades, and almost nobody reads it"},
    {"name": "ZCCM-IH, the Zambian state holding company and the seller of the legacy assets",
     "holds": "minority stakes across the Zambian mining industry and the state's negotiating "
              "position in every ownership change",
     "forced_to": ("dispose of, restructure or recapitalise assets the state cannot run",
                   "announce each transaction publicly because it is itself listed",
                   "balance a dividend expectation against a capital need"),
     "when": "irregular; the Mopani disposal completed in 2024 and the Konkola resolution ran "
             "through the same window",
     "information": ("the transaction terms before they are announced",
                     "the assets' true operating position",
                     "the government's own intentions"),
     "constraints": ("assets that need capital it does not have",
                     "a government with a production target that requires those assets to run",
                     "counterparties with far deeper balance sheets"),
     "instruments": ("XCUUSD", "USDZAR"),
     "counterparties": ("the international buyers of the stakes",
                        "the government as shareholder", "the creditors of the assets",
                        "the Zambian exchange, where it is itself listed"),
     "observables": ("the dated transaction announcements",
                     "the assets' subsequent production and capital plans",
                     "the ministry's own output statistics for the affected mines"),
     "impact": "ownership changes at two of the country's largest assets are a dated treatment on "
               "a measurable share of Zambian output, which is the cleanest natural experiment on "
               "whether ownership changes production",
     "persistence": "quarters to years; a recapitalisation takes time to show up in tonnes",
     "falsifier": "the affected mines' output over the eight quarters after each transaction is "
                  "indistinguishable from matched Zambian operations with no ownership change "
                  "once the copper price and the power constraint are controlled for",
     "notes": "ZCCM-IH IS ITSELF LISTED and is an ACTOR here and never an instrument; its listing "
              "is registered and never traded (two-lane order, 2026-09-06)"},
    {"name": "The large Zambian mine operators, as a class",
     "holds": "the Kansanshi, Lumwana, Kalumbila, Mopani and Konkola operations and the smelters "
              "and refineries attached to them",
     "forced_to": ("run through a power deficit on a schedule somebody else sets",
                   "pay royalty on an LME-referenced value whether or not the mine is profitable",
                   "carry VAT refund arrears as working capital",
                   "disclose quarterly production to listing regulators abroad"),
     "when": "quarterly for disclosures; continuously for the physical operation",
     "information": ("the month's grade, recovery and stockpile position",
                     "the power curtailment they are actually taking",
                     "the refund arrears they are actually carrying"),
     "constraints": ("power availability and its cost",
                     "a royalty on revenue rather than on profit",
                     "an acid and reagent supply chain that runs on the same four roads",
                     "declining grades at the legacy operations"),
     "instruments": ("XCUUSD", "XALUSD", "XBRUSD"),
     "counterparties": ("ZESCO and the power pool", "the revenue authority",
                        "the Chinese and international offtakers",
                        "the transporters and the corridor operators",
                        "the Congolese concentrate sellers who feed the Zambian smelters"),
     "observables": ("quarterly production and cost disclosures",
                     "the ministry's national output series",
                     "royalty receipts at the revenue authority",
                     "imported concentrate volumes in the customs data"),
     "impact": "roughly three quarters of a million tonnes a year against a published national "
               "target of three million: the gap between the two is the most-watched supply "
               "question in African copper and it is measurable every quarter",
     "persistence": "quarters; output is a capital and power story and both move slowly",
     "falsifier": "the quarterly production surprise against the ministry's own trailing trend "
                  "carries no information about XCUUSD once the ICSG balance is controlled for, "
                  "which would make Zambian output a price-taker with no price content",
     "notes": "NAMED AS A CLASS. Each of these belongs to a listed parent and the two-lane order "
              "forbids hunting any of them; the TONNAGE is what is testable"},
    {"name": "The Zambia Revenue Authority, the royalty scale and the VAT refund arrears",
     "holds": "the mineral royalty assessment on an LME-referenced value, the corporate income "
              "tax on the mines, and the VAT refunds it owes them",
     "forced_to": ("collect a royalty on revenue regardless of profitability",
                   "publish receipts that are, in effect, a counted tonne at a known price",
                   "settle or carry refund arrears that are the mines' working capital"),
     "when": "monthly for the receipts; the scale and its deductibility change on the 1 January "
             "commencement of each Finance Act",
     "information": ("the true assessed tonnage and value before the ministry publishes output",
                     "the arrears position it is carrying",
                     "the coming changes in the finance bill"),
     "constraints": ("a revenue target the treasury depends on",
                     "mines whose investment decisions respond to the fiscal regime",
                     "a refund obligation that competes with the revenue target"),
     "instruments": ("XCUUSD", "USDZAR"),
     "counterparties": ("the mining operators", "the treasury", "the IMF programme's targets"),
     "observables": ("monthly royalty and mining tax receipts",
                     "the published arrears position",
                     "the Finance Act text and its commencement date"),
     "impact": "THE RECEIPT IS AN INDEPENDENT READ ON OUTPUT that does not come from the "
               "producers, and the fiscal regime itself is a dated treatment on investment",
     "persistence": "monthly for the receipts; the regime changes are annual and dated",
     "falsifier": "royalty receipts deflated by the LME price carry no information about the "
                  "output the ministry later reports, which would mean the receipt measures "
                  "collection effort rather than tonnage and CB-J's observable is not an "
                  "observable",
     "notes": "the deductibility of the royalty against corporate income tax is the clause that "
              "moved most: non-deductible from the 2019 commencement and deductible again from "
              "the 2022 one, which is a dated, published change in the after-tax cost of a tonne"},
    {"name": "The Zambian Ministry of Finance and the sovereign restructuring team",
     "holds": "the defaulted and restructured external debt, the IMF programme targets and the "
              "budget that sets the mining fiscal regime",
     "forced_to": ("negotiate comparability of treatment between bondholders and the official "
                   "creditor committee",
                   "meet programme targets at each review",
                   "deliver a Budget Address at the end of September that sets the next year's "
                   "mining regime"),
     "when": "the default sequence is dated: 2020-10-14 the missed coupon, 2020-11-13 the grace "
             "expiry, 2022-08-31 the IMF arrangement, June 2023 the official creditor agreement "
             "and June 2024 the bond exchange",
     "information": ("the negotiating position of each creditor class",
                     "the review's likely outcome before the Board meets"),
     "constraints": ("a debt stock that has to be comparable across creditor classes",
                     "a domestic market that is now the main funding source",
                     "a mining sector it needs to invest and also to tax"),
     "instruments": ("USDZAR", "US500", "EURZAR"),
     "counterparties": ("the bondholder committee", "the official creditor committee and its "
                        "co-chairs", "the IMF", "the mining industry it taxes"),
     "observables": ("the dated milestone announcements",
                     "the IMF review Board dates and the staff reports",
                     "the Budget Address and the Finance Act"),
     "impact": "the restructuring sequence is the cleanest dated frontier-credit experiment on "
               "the desk's African roster, and its executable leg is the risk carrier rather than "
               "a credit the broker does not quote",
     "persistence": "years; the sequence ran from 2020 to 2024 and its fiscal consequences persist",
     "falsifier": "the restructuring milestones show no measurable move in the carriers beyond "
                  "what a US data day or a global risk move explains, which is the honest prior "
                  "and which CB-H exists to MEASURE rather than to assume",
     "notes": "the honest prior is that a single frontier restructuring has no global spillover; "
              "the point of the domain is to measure it, and Ghana is the matched sibling case"},
    {"name": "The Zambian smelters that treat CONGOLESE concentrate",
     "holds": "smelting and refining capacity on the Copperbelt that is fed partly from across "
              "the border, which is what makes the two countries one processing system",
     "forced_to": ("keep a smelter hot, because cooling one is ruinous",
                   "buy feed wherever it is available, including from Katanga",
                   "negotiate treatment and refining charges against a world market"),
     "when": "continuously; the feed mix changes with relative availability and with the Congolese "
             "export regime",
     "information": ("the true feed position and the treatment charges actually agreed",
                     "the Congolese sellers' alternatives this month"),
     "constraints": ("power, which is the same constraint as everything else here",
                     "a Congolese export regime that can favour domestic processing",
                     "acid supply and the by-product economics"),
     "instruments": ("XCUUSD", "XALUSD"),
     "counterparties": ("the Congolese concentrate sellers",
                        "the Zambian mines whose concentrate they also treat",
                        "ZESCO", "the international offtakers"),
     "observables": ("imported concentrate volumes in the Zambian customs data",
                     "treatment and refining charge benchmarks where reported",
                     "smelter maintenance and curtailment announcements"),
     "impact": "a cross-border processing link that makes a Congolese export-policy change a "
               "ZAMBIAN operating variable, which is the mechanism most likely to be missed by "
               "anyone modelling either country alone",
     "persistence": "quarters; a feed arrangement is contractual and changes slowly",
     "falsifier": "Zambian imported-concentrate volumes show no relation to Congolese export "
                  "policy changes or to relative treatment charges, which would mean the "
                  "processing link is fixed by contract and carries no information",
     "notes": "THE SINGLE BEST ARGUMENT FOR ONE PACK RATHER THAN TWO: the smelters do not respect "
              "the border and neither does the orebody"},
    # ---------------------------------------------------------------- regional
    {"name": "The Chinese offtakers, refiners and the infrastructure-for-minerals channel",
     "holds": "the offtake contracts, the refining capacity and, through the Sicomines "
              "arrangement and its successors, a claim on Congolese output against infrastructure",
     "forced_to": ("keep refineries fed, which makes them a reliable buyer of Congolese "
                   "hydroxide and Zambian cathode",
                   "fund infrastructure whose repayment is in minerals",
                   "respond to a Congolese export regime they did not set"),
     "when": "continuously for the offtake; the infrastructure arrangement was renegotiated in "
             "2024 and its terms are dated",
     "information": ("the true import and stock position before the customs data publishes it",
                     "the refining margin on hydroxide",
                     "the contracted volumes under each arrangement"),
     "constraints": ("a battery-chemistry mix that has shifted away from cobalt",
                     "competing Indonesian nickel-cobalt supply",
                     "a domestic demand cycle that is the dominant term in the copper balance"),
     "instruments": ("XCUUSD", "XNIUSD", "USDCNH"),
     "counterparties": ("the Katangan and Zambian operators",
                        "the Congolese state under the infrastructure arrangement",
                        "the corridor operators", "the domestic Chinese refiners and users"),
     "observables": ("Chinese customs imports of refined copper, concentrate and cobalt hydroxide",
                     "the Shanghai close and the bonded premium",
                     "the renegotiated infrastructure terms as published"),
     "impact": "CHINA IS THE CONFOUND IN EVERY DOMAIN IN THIS PACK. A Congolese or Zambian supply "
               "event that coincides with a Chinese demand move is not a supply event, and the "
               "control has to come from the `cn` pack's own series",
     "persistence": "structural; the offtake and the infrastructure claims run for decades",
     "falsifier": "Chinese import volumes from these two countries show no relation to the "
                  "corridor and export-regime events this pack dates, which would mean the "
                  "offtake is contractual and insensitive and CB-N is not a channel",
     "notes": "NAMED AS A CLASS AND CONTROLLED FOR EVERYWHERE. This is the reason `cn` is in "
              "INTERACTIONS and the reason no chokepoint cell in this pack is compiled without a "
              "Chinese demand control"},
    {"name": "The four corridor operators and the concessionaires who own the roads to the sea",
     "holds": "the Benguela railway to Lobito, the TAZARA line to Dar es Salaam, the road and "
              "rail to Durban through Beitbridge, and the Beira and Nacala corridors",
     "forced_to": ("compete for the same Katangan and Zambian cargo on price and reliability",
                   "invest under concessions with published commitments",
                   "publish throughput to the authorities that granted the concessions"),
     "when": "continuously; the Lobito concession was signed in 2023 and the first Congolese "
             "copper moved on it in 2024, and the TAZARA rehabilitation was agreed in 2024-2025",
     "information": ("the contracted tonnage on each route",
                     "the real transit time this week",
                     "the investment schedule against the concession commitment"),
     "constraints": ("track and road condition and the rainy season",
                     "port capacity at the far end",
                     "the volume a single mine can commit to a single route"),
     "instruments": ("XCUUSD", "XBRUSD", "USDZAR"),
     "counterparties": ("the mining operators and their logistics contractors",
                        "the transporters", "the four coastal states and their port authorities",
                        "the development-finance institutions behind the Lobito arrangement"),
     "observables": ("throughput and transit tonnage by route where published",
                     "the dated concession and first-shipment milestones",
                     "transit times on the corridor dashboards"),
     "impact": "THE CORRIDOR SHARE IS A DATED, PUBLISHED CHANGE IN WHERE CENTRAL AFRICAN COPPER "
               "PHYSICALLY GOES, and the reopening of the Atlantic route is the largest such "
               "change in decades",
     "persistence": "years; a rail concession is a structural change and it ramps slowly",
     "falsifier": "the Lobito milestones show no measurable shift in the corridor share out of "
                  "Katanga against the other three routes, which would mean the reopening is "
                  "capacity on paper and the physical flow never moved",
     "notes": "the Dar es Salaam end of this belongs to `east_africa` and the Durban end to `za`; "
              "neither of those packs and neither half of this one can establish a routing claim "
              "alone, which is what INTERACTIONS is for"},
)


# --------------------------------------------------------------------------- domains
#: FOURTEEN DOMAINS: five for the DRC, five for Zambia and four regional. Each jurisdiction owes
#: at least four of its own, and a domain with fewer than two negative controls is refused by the
#: validator because an effect with no control cannot be told from the desk's own selection.
DOMAINS: tuple[dict[str, Any], ...] = (
    {"id": "CB-A", "title": "DRC: the cobalt export suspension of 2025-02-22 and the quota regime",
     "objects": ("the ARECOMS decision suspending all cobalt exports and its commencement date",
                 "the June 2025 extension and the October 2025 replacement by an export quota",
                 "Congolese cobalt export tonnage in the customs and mirror statistics",
                 "the stock of hydroxide at the mines, in transit and at the ports",
                 "the by-product credit a cobalt price carries on the Katangan copper cost curve"),
     "conditions": ("the export regime in force: FREE before 2025-02-22, SUSPENDED after, QUOTA "
                    "from 2025-10-16",
                    "whether the window is the first month after a decision or a later one, "
                    "because a ban binds only once the pipeline stock runs down",
                    "whether Indonesian nickel-cobalt output was also moving in the same quarter"),
     "instruments": ("XCUUSD", "XNIUSD", "USDCNH"),
     "controls": ("THE INDONESIAN NICKEL-COBALT RAMP, which is the competing supply and the "
                  "reason the price fell at all: a Congolese intervention that moves the price "
                  "when Indonesian output is flat is a DRC event, and one that moves it when "
                  "Indonesian output is also moving is a market event with a Congolese headline",
                  "the matched-weekday control on XCUUSD around each decision date, because a "
                  "decision day is a weekday like any other until it is shown not to be",
                  "Chinese refined-cobalt and hydroxide import volumes over the same months, "
                  "which separate 'the DRC stopped selling' from 'China stopped buying'"),
     "notes": "THERE IS NO COBALT CONTRACT IN THE BROKER REGISTRY and the pack never pretends "
              "otherwise: the intervention is tested on the COPPER and NICKEL it is a by-product "
              "of, with the route stated explicitly in TRANSMISSION_TARGETS"},
    {"id": "CB-B", "title": "DRC: the copper ramp that passed Peru -- Kamoa-Kakula, TFM and KFM",
     "objects": ("the phased expansion milestones at the largest Katangan operations",
                 "quarterly production disclosures against the ministry's provincial table",
                 "Congolese export tonnage in the customs and Comtrade mirror data",
                 "the USGS country table that dates the overtaking of Peru",
                 "the acid, reagent and power constraints that decide whether a ramp lands"),
     "conditions": ("whether a published expansion milestone fell in the window",
                    "whether the quarter's disclosed output beat or missed the operator's own "
                    "prior guidance",
                    "the ICSG world balance state: surplus, deficit or near-balance"),
     "instruments": ("XCUUSD", "XNIUSD", "XZNUSD"),
     "controls": ("Chilean and Peruvian quarterly output over the same quarters, which separates "
                  "'copper supply grew' from 'CONGOLESE copper supply grew' -- and both are "
                  "sibling packs on this desk",
                  "the ICSG world balance itself, because a ramp inside a balance that was "
                  "already in surplus is a different event from the same ramp into a deficit",
                  "matched non-milestone quarters at the same operations"),
     "notes": "THE MARGINAL TONNE OF WORLD SUPPLY, AND THE BROKER QUOTES IT DIRECTLY. Every named "
              "operation belongs to a listed parent and appears in this pack as an ACTOR only"},
    {"id": "CB-C", "title": "DRC: the 2018 Code minier, the strategic-substance royalty and ARSP",
     "objects": ("the 2018 amending law and the arrete that declared cobalt a strategic substance "
                 "at a ten per cent royalty",
                 "the removal of the stability clause and the operators' response to it",
                 "the ARSP subcontracting enforcement decisions and the contracts they touched",
                 "the Gecamines renegotiations and their dated settlements",
                 "the annual finance law's own mining clauses"),
     "conditions": ("whether a gazetted mining-fiscal instrument commenced in the window",
                    "whether the instrument raised the state's take or only its administration",
                    "the era: pre-2018 Code, post-2018 Code, post-ARECOMS"),
     "instruments": ("XCUUSD", "XNIUSD"),
     "controls": ("Zambian fiscal changes over the same years as the matched frontier case -- two "
                  "resource states raising their take in the same cycle, which separates 'the DRC "
                  "changed the rules' from 'resource nationalism happened'",
                  "the affected operations' capital spending against matched Congolese operations "
                  "with no instrument touching them",
                  "a randomised-date null drawn from the same quarters"),
     "notes": "a fiscal regime is a SLOW channel into supply and the pack declares it slow; the "
              "value of the domain is the dated, gazetted text and not a same-week price claim"},
    {"id": "CB-D", "title": "DRC: the franc, dollarisation above eighty per cent, and the BCC",
     "objects": ("the taux directeur decisions and the bill auction results",
                 "the daily indicative rate and its gap to the reported street rate",
                 "the weekly reserve and monetary-base lines in the condense",
                 "the IMF programme reviews and their reserve and arrears targets",
                 "the import bill for fuel, wheat and reagents that the franc prices"),
     "conditions": ("whether the franc depreciated more than its own trailing interquartile range "
                    "in the quarter",
                    "whether an IMF review disbursed in the same quarter",
                    "the mining export receipt trend, which is the reserve base"),
     "instruments": ("XCUUSD", "XAUUSD", "USDZAR", "WHEAT"),
     "controls": ("ZAMBIA OVER THE SAME MONTHS: an open capital account and a free float next "
                  "door, which is what separates 'a Congolese dollarisation stress' from 'a "
                  "frontier-currency episode'",
                  "USDZAR as the CARRIER with its own control -- the SARB decision calendar and "
                  "South African data days, because the rand carries idiosyncratic risk the "
                  "Congolese franc does not",
                  "the same windows on days with a US CPI or FOMC print, which separate 'the "
                  "frontier repriced' from 'the dollar repriced'"),
     "notes": "THE PACK REFUSES TO PRETEND THE FRANC IS THE MECHANISM. Mining receipts and most "
              "mining costs are dollars; what this domain tests is where fiscal stress meets the "
              "mining fiscal regime, and the currency is the state it conditions on"},
    {"id": "CB-E", "title": "DRC: artisanal output, the state channel and the fastest supply "
                            "response in the cobalt market",
     "objects": ("the artisanal share in the ministry's and EITI's production reconciliation",
                 "the export tonnage that industrial output alone cannot account for",
                 "the state channel for artisanal cobalt as asserted, relaxed and reasserted",
                 "the rainy season that floods workings from November to April",
                 "the downstream due-diligence requirements that shape who may buy the output"),
     "conditions": ("the season: the November-April rains against the dry-season working window",
                    "the cobalt price regime of the preceding two quarters, because the response "
                    "is fast but not instant",
                    "the export regime in force, which decides whether the output can leave"),
     "instruments": ("XCUUSD", "XNIUSD", "XAUUSD"),
     "controls": ("Congolese INDUSTRIAL output over the same quarters, which is the direct "
                  "separator: an artisanal supply response is only a response if the industrial "
                  "series did not do the same thing",
                  "the same seasons in years with no policy change at all",
                  "the eastern Congolese artisanal GOLD flow as an independent second artisanal "
                  "leg -- one commodity is a story, two moving together is a mechanism"),
     "notes": "THE DESK RECORDS WHAT IS PUBLISHED ABOUT PRODUCTION, FLOWS AND POLICY. The "
              "well-documented human-rights concerns in this supply chain are not this pack's "
              "subject and no personal data about any individual miner is collected or sought"},
    {"id": "CB-F", "title": "ZAMBIA: the Kariba lake level, ZESCO load-shedding and the smelters",
     "objects": ("THE DAILY LAKE LEVEL AND USABLE STORAGE published by the Zambezi River Authority",
                 "the inflow readings at Victoria Falls and the seasonal rainfall outlooks",
                 "the published ZESCO load-management schedule and the shedding hours",
                 "the mines' own disclosures of power curtailment and imported power",
                 "the Southern African Power Pool volumes and price when Kariba cannot supply"),
     "conditions": ("the hydrological phase: RAINS_INFLOW December-April, PEAK_STORAGE May-August, "
                    "DRAWDOWN_MINIMUM September-November",
                    "whether usable storage is below its own trailing five-year seasonal band",
                    "the load-shedding phase: normal, declared disaster, deep or easing",
                    "whether the seasonal rainfall outlook published before the season was "
                    "already below normal, which is the EX-ANTE leg"),
     "instruments": ("XCUUSD", "XALUSD", "XNGUSD", "CORN", "SUGAR"),
     "controls": ("the same calendar weeks in years with normal storage, which is the only way to "
                  "tell a drought from a season",
                  "Zambian copper output in the same quarters, because the claim is about "
                  "SMELTER power and not about household shedding -- if output did not move, the "
                  "price should not have",
                  "South African and regional power-pool conditions over the same weeks, which "
                  "separate 'Kariba' from 'southern African power' and are the `za` pack's ground",
                  "a block-permuted lake-level series as the null for any daily-lead claim"),
     "notes": "THE HIGHEST-VALUE DOMAIN IN THE PACK BY DATA FREQUENCY: a daily, public, physically "
              "causal input to a material share of world copper smelting, against a liquid "
              "contract, with a published FORECAST of the input months ahead of the input itself"},
    {"id": "CB-G", "title": "ZAMBIA: output against the three-million-tonne target, and the "
                            "Mopani and Konkola ownership reshuffle",
     "objects": ("the ministry's national and by-mine output series",
                 "the published national target and the annual distance from it",
                 "the 2024 disposal of the Mopani stake and the Konkola resolution",
                 "the operators' quarterly production and cost disclosures",
                 "imported Congolese concentrate feeding the Zambian smelters"),
     "conditions": ("whether an ownership transaction completed in the preceding four quarters",
                    "the quarter's output surprise against the ministry's own trailing trend",
                    "the power state, because output here is a power story before it is anything "
                    "else"),
     "instruments": ("XCUUSD", "XZNUSD", "XPBUSD"),
     "controls": ("matched Zambian operations with no ownership change over the same quarters, "
                  "which is the direct counterfactual for a recapitalisation claim",
                  "the copper price itself, because output responds to price and a naive "
                  "regression reads the response as a cause",
                  "the power constraint, which is the confound that explains most Zambian output "
                  "variance and belongs in every specification in this domain"),
     "notes": "TWO STATE-BROKERED OWNERSHIP CHANGES AT TWO OF THE COUNTRY'S LARGEST ASSETS inside "
              "eighteen months is as close to a dated treatment on ownership as mining offers, "
              "and both counterparties are ACTORS here and never instruments"},
    {"id": "CB-H", "title": "ZAMBIA: the 2020 default and the Common Framework restructuring",
     "objects": ("the coupon missed on 2020-10-14 and the grace expiry on 2020-11-13",
                 "the IMF Extended Credit Facility approved on 2022-08-31 and each review",
                 "the Official Creditor Committee agreement of June 2023",
                 "the eurobond exchange completed in June 2024",
                 "the domestic bond auctions that became the sovereign's main funding source"),
     "conditions": ("the restructuring phase: pre-default, default, IMF programme, bonds exchanged",
                    "whether a Ghanaian or Ethiopian Common Framework milestone fell in the same "
                    "window, because three African restructurings ran in the same cycle",
                    "the risk regime measured on the carriers themselves"),
     "instruments": ("USDZAR", "EURZAR", "US500"),
     "controls": ("GHANA'S AND ETHIOPIA'S OWN default and restructuring dates as matched frontier "
                  "events -- Ghana is a sibling pack and Ethiopia is inside `east_africa`",
                  "the same windows on days with a US CPI or FOMC print, which separate 'the "
                  "frontier repriced' from 'the dollar repriced'",
                  "a randomised-date null drawn from the same quarters"),
     "notes": "THE HONEST PRIOR IS THAT A SINGLE FRONTIER RESTRUCTURING HAS NO GLOBAL SPILLOVER. "
              "The point of the domain is to MEASURE that rather than to assume it, and the "
              "carriers are labelled carriers"},
    {"id": "CB-I", "title": "ZAMBIA: the kwacha's copper beta, BoZ intervention and the statutory "
                            "reserve ratio",
     "objects": ("the daily interbank rate and the published intervention amounts",
                 "the quarterly policy rate decisions and the statements that carry them",
                 "THE STATUTORY RESERVE RATIO CIRCULARS, which arrive between meetings",
                 "the bank's own published COPPER PRICE ASSUMPTION inside its inflation forecast",
                 "the Treasury bill and bond auction cut-offs and bid-to-cover"),
     "conditions": ("whether a reserve-ratio change was announced in the window, which is the "
                    "surprise instrument as opposed to the scheduled one",
                    "whether the copper price moved more than its own trailing band in the same "
                    "window, because the kwacha's beta is the thing being conditioned on",
                    "the restructuring phase, because a defaulted sovereign's currency is a "
                    "different asset from a restructured one"),
     "instruments": ("USDZAR", "EURZAR", "GBPZAR", "ZARJPY"),
     "controls": ("THE ZAR COMPLEX IS THE CARRIER AND NOT THE CURRENCY: the SARB decision "
                  "calendar and South African data days must be controlled for in every "
                  "specification, because the rand carries idiosyncratic risk the kwacha does not",
                  "the copper price itself, because the kwacha's copper beta means a naive test "
                  "of 'Zambian policy moves the rand' is mostly a test of copper",
                  "matched non-announcement windows drawn from the same quarters"),
     "notes": "THE DIRECTION IS THE POINT AND IT RUNS THE WRONG WAY FOR A TRADE: copper moves the "
              "kwacha, not the reverse. The kwacha is therefore a CONFIRMING observable and the "
              "cells here test the carrier's reaction to the policy instrument, not to the metal"},
    {"id": "CB-J", "title": "ZAMBIA: the mining fiscal regime -- royalty scale, deductibility and "
                            "the VAT refund arrears",
     "objects": ("the sliding-scale mineral royalty and its LME-referenced assessment",
                 "the deductibility of the royalty against corporate income tax: withdrawn at the "
                 "2019 commencement and restored at the 2022 one",
                 "the VAT refund arrears the mines carry as working capital",
                 "the monthly royalty receipts, which are a counted tonne at a known price",
                 "each Budget Address at the end of September and the Finance Act that follows"),
     "conditions": ("whether the royalty was deductible in the window, which is a dated, "
                    "published change in the after-tax cost of a tonne",
                    "whether a Budget Address or a Finance Act commencement fell in the window",
                    "the copper price level, because a revenue royalty bites hardest at low "
                    "prices and that is exactly when it changes behaviour"),
     "instruments": ("XCUUSD", "USDZAR"),
     "controls": ("Congolese fiscal changes over the same years as the matched frontier case, "
                  "which is CB-C's own ground and is the direct separator",
                  "matched budget rounds that changed other clauses and left the mining royalty "
                  "alone, which separates 'the budget' from 'the royalty'",
                  "the affected operations' capital spending against the world copper capital "
                  "cycle"),
     "notes": "the royalty RECEIPT is the underused half of this domain: it is published by the "
              "tax authority, it is an LME-referenced value, and it is therefore an independent "
              "read on output that does not come from the producers"},
    {"id": "CB-K", "title": "REGIONAL: the four roads to the sea, and the Lobito reopening",
     "objects": ("the Durban route through Kasumbalesa, Chirundu and Beitbridge",
                 "the Dar es Salaam Central Corridor by road and the TAZARA rail",
                 "the Beira and Nacala corridors through Mozambique",
                 "THE LOBITO CORRIDOR: the 2023 Benguela railway concession and the first "
                 "Congolese copper to the Atlantic in 2024",
                 "transit tonnage by destination country and the revealed corridor share"),
     "conditions": ("the Lobito phase: closed to copper, concession signed, first copper, ramp",
                    "whether a month's corridor share moved more than its own trailing "
                    "interquartile range",
                    "the season, because the rains close roads on three of the four routes",
                    "whether the shift is a SUBSTITUTION -- a fall on one route matched by a rise "
                    "on another -- or a net fall in total tonnage"),
     "instruments": ("XCUUSD", "XBRUSD", "USDZAR"),
     "controls": ("THE OTHER THREE CORRIDORS' OWN THROUGHPUT, which is the whole control: a fall "
                  "at Dar es Salaam that appears at Lobito is a ROUTING event and carries no "
                  "supply information at all, and `east_africa` owns the Tanzanian series while "
                  "`za` owns the Durban one",
                  "total Congolese and Zambian export tonnage, which separates 'the metal took "
                  "another road' from 'less metal left'",
                  "Chinese import volumes over the same months, which separate a corridor event "
                  "from a demand event",
                  "the same months in years with no concession or capacity change"),
     "notes": "A DATED, PUBLISHED CHANGE IN WHERE CENTRAL AFRICAN COPPER PHYSICALLY GOES is rare "
              "and this is one; `east_africa` is named FIRST in INTERACTIONS for exactly this "
              "reason, because neither pack can establish a routing claim alone"},
    {"id": "CB-L", "title": "REGIONAL: Kasumbalesa, the border queue and the two-calendar crossing",
     "objects": ("the reported queue length in kilometres and the customs clearance time",
                 "the two customs administrations' procedural notices",
                 "the one-stop border post arrangements and their implementation",
                 "the two national holiday calendars, which do not close on the same days",
                 "the fuel and reagent backhaul that uses the same crossing"),
     "conditions": ("whether a queue episode was reported in the window, which is an EPISODIC "
                    "series and is treated as one",
                    "whether the window contains a day on which only ONE side of the border was "
                    "closed, which is the two-calendar effect",
                    "the season, because the rains and the crop-marketing peak both add traffic"),
     "instruments": ("XCUUSD", "XBRUSD"),
     "controls": ("corridor substitution, because a queue at Kasumbalesa that pushes cargo to "
                  "Lobito is an inventory-timing event and not a supply event",
                  "matched weeks with no reported queue, drawn from the same seasons",
                  "exchange and bonded inventory changes over the same weeks, because inventory "
                  "exists precisely to absorb a two-week delay"),
     "notes": "THE HONEST PRIOR IS THAT THIS DOES NOT REACH THE PRICE. A queue is a days-to-weeks "
              "delay in a market with visible inventories, and the point of the domain is to "
              "measure whether it ever does rather than to assume it either way (L1.28a)"},
    {"id": "CB-M", "title": "REGIONAL: two calendars, one orebody, and the session that only one "
                            "side keeps",
     "objects": ("the Congolese solar-only statutory list with no Easter and no substitution",
                 "the Zambian four-day Easter weekend, the weekday-rule days and the Sunday "
                 "substitution",
                 "THE DECLARED ONE-OFF HOLIDAYS the Zambian President signs by statutory "
                 "instrument, of which a general election day is the recurring case",
                 "the days on which one side of the border is shut and the other is working",
                 "the two budget clocks: September in Lusaka and December in Kinshasa"),
     "conditions": ("whether BOTH jurisdictions were closed, which is when the crossing stops "
                    "rather than merely slows",
                    "whether only ONE was closed, which is the separating control and the "
                    "interesting case",
                    "whether the closure was a DECLARED one-off rather than a recurring statutory "
                    "day, because a declared day is unpredictable by construction"),
     "instruments": ("XCUUSD", "XAUUSD", "USDZAR"),
     "controls": ("the matched weekday twenty-six weeks away, which is the standard holiday "
                  "control and the one this desk has always used",
                  "days on which only one of the two closed, which is the within-region control "
                  "that no single-country pack can construct",
                  "the same dates in years when the movable days fell in a different week"),
     "notes": "A SESSION A BACKTEST SILENTLY FILLS IS A SESSION THAT DID NOT EXIST. The two "
              "calendars disagree on Easter, on substitution and on declared days, and a pooled "
              "regional holiday study gets all three wrong at once"},
    {"id": "CB-N", "title": "REGIONAL: the Chinese offtake and the infrastructure-for-minerals "
                            "channel",
     "objects": ("Chinese customs imports of refined copper, concentrate and cobalt hydroxide",
                 "the Shanghai close and the bonded premium against the LME",
                 "the Sicomines infrastructure-for-minerals arrangement and its 2024 "
                 "renegotiation",
                 "Chinese ownership and offtake across the Katangan and Zambian operations",
                 "the TAZARA rehabilitation concession and the corridor financing behind it"),
     "conditions": ("whether Chinese import volumes moved more than their own trailing band",
                    "whether a Congolese or Zambian supply event fell in the same month, which is "
                    "the confounding case the domain exists to separate",
                    "the Chinese domestic demand state as the `cn` pack measures it"),
     "instruments": ("XCUUSD", "XNIUSD", "USDCNH"),
     "controls": ("THE `cn` PACK'S OWN DEMAND SERIES, because Chinese demand is the confound in "
                  "every other domain in this file and a control that lives in another pack is "
                  "the reason INTERACTIONS exists",
                  "Chilean and Peruvian export volumes to China over the same months, which "
                  "separate 'China bought less' from 'China bought less FROM HERE'",
                  "the bonded premium, which separates a physical tightness from a price move"),
     "notes": "CHINA IS THE CONFOUND IN EVERY DOMAIN IN THIS PACK and this is the domain that "
              "measures it directly, so that the other thirteen can control for it honestly"},
)

# --------------------------------------------------------------------------- custom miners
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    {"name": "cb_cobalt_regime", "domain_ids": ("CB-A", "CB-E"), "kind": "event",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.copperbelt.pack:mine_cobalt_regime",
     "needs": ("COBALT_POLICY_EVENTS", "XCUUSD and XNIUSD H1 bars",
               "Congolese customs cobalt export tonnage", "Indonesian nickel-cobalt output"),
     "notes": "the suspension, the extension and the quota in one clock, with the Indonesian ramp "
              "as the control that decides whether a price move is Congolese or market-wide"},
    {"name": "cb_kariba_power", "domain_ids": ("CB-F",), "kind": "physical",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.copperbelt.pack:mine_kariba_power",
     "needs": ("DROUGHT_EVENTS", "Zambezi River Authority daily lake level",
               "ZESCO load-management schedules", "XCUUSD and XALUSD D1 bars"),
     "notes": "the daily lake level and the load-shedding phase as one state; the mine "
              "curtailment leg is tested separately from the household shedding headline"},
    {"name": "cb_corridor_share", "domain_ids": ("CB-K", "CB-L"), "kind": "physical",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.copperbelt.pack:mine_corridor_share",
     "needs": ("EXPORT_ROUTES", "corridor throughput with the transit split",
               "Dar es Salaam throughput from the east_africa ground", "XCUUSD D1 bars"),
     "notes": "a corridor fall is a ROUTING event until the other three corridors' series say it "
              "is not, which is why this miner cannot run without the sibling packs' ground"},
    {"name": "cb_output_ramp", "domain_ids": ("CB-B", "CB-G"), "kind": "release",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.copperbelt.pack:mine_output_ramp",
     "needs": ("PRODUCTION_MILESTONES", "ministry production series for both countries",
               "ICSG world balance", "XCUUSD D1 bars"),
     "notes": "the two countries' output surprises against their own trailing trend, with the "
              "Chilean and Peruvian series as the separating control"},
    {"name": "cb_fiscal_sequence", "domain_ids": ("CB-H", "CB-J", "CB-C"), "kind": "macro",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.copperbelt.pack:mine_fiscal_sequence",
     "needs": ("ZM_DEFAULT_EVENTS", "ZM_ROYALTY_REGIME", "POLICY_ERAS", "USDZAR D1 bars"),
     "notes": "the default-to-exchange sequence and the royalty deductibility boundaries as dated "
              "treatments, with Ghana and Ethiopia as the matched frontier cases"},
    {"name": "cb_calendar_plane", "domain_ids": ("CB-M",), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.copperbelt.pack:mine_calendar_plane",
     "needs": ("HOLIDAYS_RULE", "XCUUSD, XAUUSD and USDZAR H1 bars"),
     "notes": "two calendars that disagree on Easter, on substitution and on declared days, with "
              "the one-country-closed days as the separating control"},
    {"name": "cb_transmission_seeds",
     "domain_ids": ("CB-D", "CB-I", "CB-N", "CB-A", "CB-F"),
     "kind": "transfer", "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.copperbelt.pack:mine_transmission_seeds",
     "needs": ("TRANSMISSION_EDGES_SEED",),
     "notes": "the pack's map as HYPOTHESIS discoveries, deduplicated by the registry"},
)
MINER_DOMAINS: dict[str, tuple[str, ...]] = {
    "central_bank_surprise": ("CB-I", "CB-D"), "release_surprise": ("CB-B", "CB-G", "CB-I"),
    "calendar_settlement": ("CB-M", "CB-J"), "holiday_liquidity": ("CB-M",),
    "positioning": ("CB-H",), "carry_funding": ("CB-I", "CB-D"),
    "corporate_flow": ("CB-B", "CB-G"), "institutional_flow": ("CB-H", "CB-N"),
    "equity_mechanics": ("CB-H",), "derivatives_expiry": ("CB-N",),
    "failure": ("CB-F", "CB-L"), "residual": ("CB-C", "CB-E"),
    "transfer": ("CB-K", "CB-N"), "scouts": ("CB-E", "CB-A"),
    "session_microstructure": ("CB-M", "CB-L"),
}


# --------------------------------------------------------------------------- transmission
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    {"id": "CB-E1", "source": "ARECOMS cobalt export suspension of 2025-02-22 and the quota "
                              "regime that replaced it on 2025-10-16",
     "target": "XCUUSD", "targets": ("XCUUSD", "XNIUSD"), "to_country": "global", "sign": "+",
     "mechanism": "a state supplying roughly seventy per cent of world cobalt stops its export "
                  "and then rations it. COBALT IS A BY-PRODUCT of Katangan COPPER and of nickel "
                  "sulphide elsewhere, so its price is a CREDIT on both cost curves: a cobalt "
                  "price that rises on a sovereign supply cut restores that credit, lowers the "
                  "effective cost of the copper tonne carrying it and makes marginal ore "
                  "economic again -- while a cobalt collapse does the reverse",
     "horizon": "0 to 5 sessions for the announcement; 1 to 3 quarters for the flow",
     "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "ARECOMS, the Ministere des Mines and the Katangan operators",
     "constraint": "hydroxide storage capacity and the pipeline stock already in transit, which "
                   "is why a ban binds with a lag rather than on the day",
     "flow": "cobalt hydroxide shipments stopped, then rationed by operator quota",
     "condition": "an ARECOMS decision date, and which side of 2025-10-16 the window sits on",
     "control": "THE INDONESIAN NICKEL-COBALT RAMP over the same quarters, which is the competing "
                "supply and the reason the price fell at all; Chinese hydroxide import volumes, "
                "which separate 'the DRC stopped selling' from 'China stopped buying'; the "
                "matched-weekday control on XCUUSD around each decision date",
     "falsifier": "Congolese cobalt export tonnage in the importers' mirror statistics shows no "
                  "break at 2025-02-22 or 2025-10-16 once the pre-ban shipment surge is "
                  "controlled for, which would make the intervention an announcement and not a "
                  "flow event and would close the by-product channel entirely",
     "evidence": "HYPOTHESIS"},
    {"id": "CB-E2", "source": "Kariba usable storage and the ZESCO load-management schedule",
     "target": "XCUUSD", "targets": ("XCUUSD", "XALUSD"), "to_country": "global", "sign": "+",
     "mechanism": "smelting and electrowinning ARE electricity. When usable storage above the "
                  "minimum operating level falls, Kariba generation falls, the utility rations, "
                  "and the mines on bulk-supply agreements are curtailed or forced to buy "
                  "imported power at several times the domestic tariff -- which is a supply "
                  "reduction and a cost increase on a material share of African copper at once",
     "horizon": "1 to 3 quarters for output; 0 to 10 sessions for a curtailment announcement",
     "horizon_class": "multi_day", "lag_days": 45.0,
     "actor": "the Zambezi River Authority, ZESCO and the mines' own power desks",
     "constraint": "the minimum operating level, which is a hard physical floor, and the "
                   "transmission capacity available to import",
     "flow": "generation rationed, mine curtailment, imported power bought through the pool",
     "condition": "usable storage below its own trailing five-year seasonal band, and the "
                  "load-shedding phase in force",
     "control": "the same calendar weeks in years with normal storage; Zambian copper OUTPUT in "
                "the same quarters, because the claim is about smelter power and not about "
                "household shedding; regional power-pool conditions, which are `za`'s ground and "
                "separate 'Kariba' from 'southern African power'",
     "falsifier": "published mine curtailment episodes show no measurable relation to Zambian "
                  "copper output in the following quarter, which would mean the mines' own "
                  "generation and import arrangements insulate them and the channel closes at the "
                  "plant gate",
     "evidence": "HYPOTHESIS"},
    {"id": "CB-E3", "source": "The Lobito Corridor concession and the first Congolese copper to "
                              "the Atlantic in 2024",
     "target": "XCUUSD", "targets": ("XCUUSD", "XBRUSD"), "to_country": "global", "sign": "-",
     "mechanism": "a route roughly half the distance of the Durban one reopens for copper. Lower "
                  "freight cost and shorter transit reduce the working capital tied up in metal "
                  "in transit, bring Katangan tonnes to market sooner and cut the diesel burnt "
                  "per tonne -- a logistics change that is a supply-timing and a cost event at "
                  "once, and the first such change on this scale in decades",
     "horizon": "1 to 8 quarters", "horizon_class": "multi_day", "lag_days": 90.0,
     "actor": "the Lobito Atlantic Railway concessionaire, the Angolan state and the Katangan "
              "operators who commit volume to it",
     "constraint": "track capacity, the rolling stock actually delivered and the port's own "
                   "handling capacity at the Atlantic end",
     "flow": "cathode and hydroxide re-routed from Durban, Dar es Salaam and Beira to Lobito",
     "condition": "the Lobito phase: closed to copper, concession signed, first copper, or ramp",
     "control": "THE OTHER THREE CORRIDORS' OWN THROUGHPUT, because a rise here matched by a fall "
                "there is a ROUTING event with no supply content at all; total Congolese export "
                "tonnage, which separates 'the metal took another road' from 'more metal left'; "
                "`east_africa` owns the Dar es Salaam series and `za` owns the Durban one",
     "falsifier": "the Lobito milestones show no measurable shift in the corridor share out of "
                  "Katanga, which would mean the reopening is capacity on paper and the physical "
                  "flow never moved",
     "evidence": "HYPOTHESIS"},
    {"id": "CB-E4", "source": "Reported Kasumbalesa queue length and customs clearance time",
     "target": "XCUUSD", "targets": ("XCUUSD", "XBRUSD"), "to_country": "global", "sign": "+",
     "mechanism": "a single road crossing carries a measurable share of world copper. A "
                  "multi-kilometre queue delays tonnes by days to weeks, which is an INVENTORY "
                  "TIMING effect: it changes when metal arrives at a warehouse and not how much "
                  "was mined, and the honest prior is that visible inventory absorbs it",
     "horizon": "2 to 8 weeks", "horizon_class": "multi_day", "lag_days": 14.0,
     "actor": "the DGDA and ZRA customs administrations and the long-haul transporters",
     "constraint": "the physical throughput of one road post, and two national calendars on the "
                   "two sides of it",
     "flow": "lorries held, then released; arrival timing shifts and mine-gate stocks build",
     "condition": "a reported queue episode, and whether the window contains a day on which only "
                  "one side of the border was closed",
     "control": "corridor substitution, because a queue that pushes cargo to another route is not "
                "a supply event; exchange and bonded inventory changes over the same weeks, which "
                "is what inventory is FOR; matched weeks with no reported queue in the same season",
     "falsifier": "reported queue episodes carry no measurable relation to XCUUSD over two to "
                  "eight weeks once substitution and inventory are controlled for -- which is the "
                  "honest prior and which this edge exists to measure rather than to assume",
     "evidence": "HYPOTHESIS"},
    {"id": "CB-E5", "source": "Congolese copper expansion milestones and the quarterly production "
                              "disclosures that follow them",
     "target": "XCUUSD", "targets": ("XCUUSD", "XZNUSD"), "to_country": "global", "sign": "-",
     "mechanism": "the world's second-largest producer ramping on a published schedule is the "
                  "largest single source of copper supply growth. A milestone landing on time "
                  "adds tonnes to a balance the ICSG measures monthly; a milestone slipping "
                  "removes them, and both are dated and public before the balance is",
     "horizon": "1 to 4 quarters", "horizon_class": "multi_day", "lag_days": 60.0,
     "actor": "the Katangan operators and their listed parents' disclosure calendars",
     "constraint": "power, acid, reagent supply and the four corridors, each of which can hold a "
                   "ramp back independently of the orebody",
     "flow": "concentrate, cathode and hydroxide tonnage into the world balance",
     "condition": "whether a published milestone fell in the window and whether the quarter beat "
                  "or missed the operator's own prior guidance",
     "control": "Chilean and Peruvian quarterly output over the same quarters, which separates "
                "'copper supply grew' from 'CONGOLESE copper supply grew' -- and both are sibling "
                "packs; the ICSG balance state itself; matched non-milestone quarters",
     "falsifier": "announced ramp milestones carry no information about XCUUSD at any horizon "
                  "once the ICSG world balance and Chinese imports are controlled for, which "
                  "would mean the expansion was fully in the price before it was announced",
     "evidence": "MEASURED_ELSEWHERE"},
    {"id": "CB-E6", "source": "The Zambian mineral royalty scale and its deductibility against "
                              "corporate income tax",
     "target": "XCUUSD", "targets": ("XCUUSD", "USDZAR"), "to_country": "global", "sign": "+",
     "mechanism": "a royalty assessed on REVENUE rather than on profit bites hardest at low "
                  "prices, and whether it is deductible against corporate income tax changes the "
                  "after-tax cost of a tonne by several percentage points. The deductibility was "
                  "withdrawn at the 2019 commencement and restored at the 2022 one, which makes "
                  "the clause a dated, published treatment on investment in a producer that "
                  "matters",
     "horizon": "2 to 8 quarters", "horizon_class": "multi_day", "lag_days": 180.0,
     "actor": "the Zambia Revenue Authority, the Ministry of Finance and the mine operators",
     "constraint": "a treasury revenue target that competes with the investment the same "
                   "government wants",
     "flow": "capital spending and mine-life decisions, and the royalty receipts themselves",
     "condition": "whether the royalty was deductible in the window, and whether a Budget Address "
                  "or Finance Act commencement fell in it",
     "control": "Congolese fiscal changes over the same years as the matched frontier case; "
                "budget rounds that changed other clauses and left the royalty alone; the world "
                "copper capital cycle, because investment moves with the price everywhere; and "
                "on the USDZAR leg the SARB decision calendar and South African data days, "
                "because the rand is the CARRIER and never the kwacha",
     "falsifier": "capital spending at Zambian operations shows no change across the 2019 and "
                  "2022 deductibility boundaries against matched Congolese and global operations, "
                  "which would make the clause a transfer with no behavioural content",
     "evidence": "HYPOTHESIS"},
    {"id": "CB-E7", "source": "Bank of Zambia statutory reserve ratio changes, announced by "
                              "circular between scheduled meetings",
     "target": "USDZAR", "targets": ("USDZAR", "EURZAR", "ZARJPY"), "to_country": "za",
     "sign": "-",
     "mechanism": "the reserve ratio is the BLUNT instrument and the unscheduled one: raising it "
                  "drains kwacha liquidity and defends the currency between MPC dates, which "
                  "makes it a genuine surprise in a way the quarterly policy rate is not. The "
                  "kwacha itself is unquotable, so the measurable leg is the SOUTHERN AFRICAN "
                  "RISK CARRIER and the claim is about the carrier and not about the kwacha",
     "horizon": "0 to 5 sessions", "horizon_class": "intraday_to_days", "lag_days": 0.0,
     "actor": "the Bank of Zambia's MPC and its FX desk",
     "constraint": "an open capital account, which means the instrument works through the banks' "
                   "balance sheets and not through a control",
     "flow": "kwacha liquidity drained, interbank rates up, depreciation pressure relieved",
     "condition": "a reserve-ratio circular in the window, and whether the copper price moved "
                  "more than its own trailing band in the same window",
     "control": "THE CARRIER IS NOT THE CURRENCY: the SARB decision calendar and South African "
                "data days must be in every specification, because the rand carries idiosyncratic "
                "risk the kwacha does not; the copper price itself, because the kwacha's copper "
                "beta makes a naive test mostly a test of copper; matched non-announcement windows",
     "falsifier": "reserve-ratio changes show no measurable move in the carriers beyond what the "
                  "policy rate and the copper price already explain, which would make the "
                  "instrument a liquidity operation with no price content outside Zambia",
     "evidence": "HYPOTHESIS"},
    {"id": "CB-E8", "source": "The Zambian default of 2020-11-13 and the Common Framework "
                              "restructuring milestones through June 2024",
     "target": "USDZAR", "targets": ("USDZAR", "US500", "EURZAR"), "to_country": "global",
     "sign": "+",
     "mechanism": "the first COVID-era sovereign default, restructured under a framework that was "
                  "being invented as it was applied. Each milestone -- the grace expiry, the IMF "
                  "arrangement, the official creditor agreement, the bond exchange -- is a dated "
                  "public event in a class of credit that three African sovereigns were in at "
                  "once, and the executable leg is the risk carrier",
     "horizon": "0 to 5 sessions", "horizon_class": "intraday_to_days", "lag_days": 0.0,
     "actor": "the Zambian Ministry of Finance, the official creditor committee and the "
              "bondholder committee",
     "constraint": "comparability of treatment between creditor classes, which is what made the "
                   "sequence slow and therefore datable",
     "flow": "frontier credit repriced; the carriers move with the risk regime",
     "condition": "the restructuring phase in force, and whether a Ghanaian or Ethiopian "
                  "milestone fell in the same window",
     "control": "GHANA'S AND ETHIOPIA'S own milestone dates as matched frontier events -- Ghana "
                "is a sibling pack and Ethiopia sits inside `east_africa`; US CPI and FOMC days, "
                "which separate 'the frontier repriced' from 'the dollar repriced'; the SARB "
                "decision calendar, because the carrier is a South African asset before it is an "
                "African-risk one; a randomised-date null drawn from the same quarters",
     "falsifier": "the milestones show no measurable move in the carriers beyond what a US data "
                  "day or a global risk move explains -- which is the honest prior, and the "
                  "reason this edge is a measurement and not a claim",
     "evidence": "HYPOTHESIS"},
    {"id": "CB-E9", "source": "Chinese customs imports of refined copper, concentrate and cobalt "
                              "hydroxide from these two countries",
     "target": "XCUUSD", "targets": ("XCUUSD", "USDCNH", "XNIUSD"), "to_country": "cn",
     "sign": "-",
     "mechanism": "China is the buyer at the end of all four corridors and the owner or offtaker "
                  "of much of the production. Its import volumes are the demand-side counterpart "
                  "of every supply event this pack dates, and the bonded premium separates a "
                  "physical tightness from a price move",
     "horizon": "1 to 2 quarters", "horizon_class": "multi_day", "lag_days": 40.0,
     "actor": "the Chinese refiners, traders and the offtake counterparties",
     "constraint": "a battery chemistry mix that has moved away from cobalt, and a domestic "
                   "demand cycle that dominates the copper balance",
     "flow": "imports of cathode, concentrate and hydroxide, and the bonded stock behind them",
     "condition": "whether Chinese imports moved more than their own trailing band and whether a "
                  "Congolese or Zambian supply event fell in the same month",
     "control": "THE `cn` PACK'S OWN DEMAND SERIES, because Chinese demand is the confound in "
                "every other domain here; Chilean and Peruvian exports to China over the same "
                "months, which separate 'China bought less' from 'China bought less FROM HERE'; "
                "the bonded premium itself",
     "falsifier": "Chinese import volumes from these two countries show no relation to the "
                  "corridor and export-regime events this pack dates, which would mean the "
                  "offtake is contractual and insensitive and the channel is not a channel",
     "evidence": "MEASURED_ELSEWHERE"},
    {"id": "CB-E10", "source": "Congolese concentrate imported into the Zambian smelters",
     "target": "XCUUSD", "targets": ("XCUUSD", "XALUSD"), "to_country": "global", "sign": "+",
     "mechanism": "the Zambian Copperbelt smelters are fed partly from Katanga, which makes the "
                  "two countries ONE PROCESSING SYSTEM. A Congolese export-policy change that "
                  "favours domestic processing, or a border delay, becomes a ZAMBIAN smelter feed "
                  "problem -- and a smelter short of feed is a refined-metal supply event that "
                  "neither country's own statistics attribute correctly",
     "horizon": "1 to 3 quarters", "horizon_class": "multi_day", "lag_days": 60.0,
     "actor": "the Zambian smelters and the Congolese concentrate sellers",
     "constraint": "a smelter cannot be run cold and cannot be idled cheaply, so feed is bought "
                   "at almost any treatment charge",
     "flow": "concentrate across the border, into Zambian refined output",
     "condition": "whether a Congolese processing or export instrument commenced in the window, "
                  "and whether treatment and refining charges moved with it",
     "control": "Zambian domestic concentrate availability over the same quarters, which "
                "separates 'the Congolese feed stopped' from 'Zambian mines produced less'; world "
                "treatment and refining charge benchmarks; matched quarters with no instrument",
     "falsifier": "Zambian imported-concentrate volumes show no relation to Congolese export "
                  "policy or to relative treatment charges, which would mean the processing link "
                  "is fixed by contract and carries no information",
     "evidence": "HYPOTHESIS"},
    {"id": "CB-E11", "source": "The Zambian drought that emptied Kariba and the maize crop at the "
                               "same time",
     "target": "CORN", "targets": ("CORN", "WHEAT", "SUGAR"), "to_country": "global", "sign": "+",
     "mechanism": "one rainfall failure hits two things at once: the reservoir that powers the "
                  "smelters and the rain-fed maize crop that feeds the Copperbelt. The second "
                  "channel is WEAK against a world grain price and the pack labels it weak -- "
                  "Zambia is a small producer globally -- but the two moving together is what "
                  "makes the drought state readable in more than one series",
     "horizon": "1 to 3 quarters", "horizon_class": "multi_day", "lag_days": 90.0,
     "actor": "the Zambian smallholders, the Food Reserve Agency and the irrigated cane estates",
     "constraint": "a rain-fed crop and a floor price announced each marketing season",
     "flow": "harvest, the FRA purchase programme, and the export restrictions imposed by "
             "statutory instrument when the crop fails",
     "condition": "the load-shedding phase and whether the season's rainfall outlook was below "
                  "normal before the season began",
     "control": "SOUTHERN AFRICAN REGIONAL production over the same seasons, which is the "
                "separator: a Zambian failure inside a regional failure is a regional event, and "
                "South Africa's crop is `za`'s own series; world maize and wheat balances, "
                "because Zambia is small in both; the same seasons in normal-rainfall years",
     "falsifier": "Zambian drought seasons show no measurable relation to CORN beyond what the "
                  "regional and world balances already carry -- the likely outcome, and the "
                  "reason this edge is labelled a WEAK carrier on its face",
     "evidence": "HYPOTHESIS"},
    {"id": "CB-E12", "source": "The two national holiday calendars and the days on which only one "
                               "side of the Copperbelt is closed",
     "target": "XCUUSD", "targets": ("XCUUSD", "XAUUSD", "USDZAR"), "to_country": "global",
     "sign": "+",
     "mechanism": "one orebody, two calendars. The DRC closes for nine solar days and nothing "
                  "moveable; Zambia closes for a four-day Easter, three weekday-rule days, a "
                  "Sunday substitution and whatever the President declares. A day on which only "
                  "one side closes halves the crossing's throughput without stopping it, and a "
                  "day on which both close stops it -- and those are different events that a "
                  "pooled regional calendar treats as one",
     "horizon": "0 to 2 sessions", "horizon_class": "intraday_to_days", "lag_days": 0.0,
     "actor": "the two customs administrations, the transporters and the mine logistics desks",
     "constraint": "a border post that needs both sides staffed to clear a lorry",
     "flow": "clearance throughput, and the arrival timing of metal at the ports",
     "condition": "whether both jurisdictions closed, only one closed, or the closure was a "
                  "DECLARED one-off rather than a recurring statutory day",
     "control": "the matched weekday twenty-six weeks away; days on which only one of the two "
                "closed, which is the within-region control no single-country pack can build; "
                "the same dates in years when the moveable days fell in a different week; and on "
                "the USDZAR leg the SARB calendar and the South African public holidays, because "
                "the carrier brings a third calendar of its own",
     "falsifier": "neither the both-closed days nor the one-closed days show any measurable "
                  "difference against the matched-weekday control, which would mean the border "
                  "calendar is absorbed entirely by inventory and scheduling",
     "evidence": "HYPOTHESIS"},
)

# --------------------------------------------------------------------------- policy eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    {"name": "DRC: the 2002 Code minier and the liberalisation era", "start": "2002-07-11",
     "end": "2018-03-08",
     "regime": "a code written to attract foreign capital after the wars: moderate royalties, "
               "stability clauses that froze the fiscal terms for a decade, and the joint-venture "
               "structures with Gecamines that the later disputes are about",
     "markers": ("2002-07-11 the Code minier is promulgated",
                 "2008 the Sicomines infrastructure-for-minerals arrangement is signed",
                 "2015-2017 the first large Katangan expansions reach nameplate"),
     "why_it_matters": "every Congolese fiscal, production and ownership series from this era was "
                       "generated under stability clauses that no longer exist; pooling it with "
                       "the post-2018 data measures two fiscal regimes and calls it one",
     "status": "SETTLED"},
    {"name": "DRC: the 2018 Code minier and the strategic-substance royalty",
     "start": "2018-03-09", "end": "2026-12-31",
     "regime": "the amending law raised royalties, removed the stability clause and created the "
               "category of STRATEGIC SUBSTANCE, under which cobalt was declared subject to a ten "
               "per cent royalty later the same year; a windfall-profit provision was added "
               "alongside it",
     "markers": ("2018-03-09 the amending law is promulgated",
                 "2018-12 cobalt is declared a strategic substance at a 10% royalty",
                 "2023-2024 ARSP subcontracting enforcement intensifies"),
     "why_it_matters": "the after-tax economics of a Katangan tonne changed on a dated boundary, "
                       "and the operators' capital decisions from this era answer a different "
                       "question from the ones before it",
     "status": "OPEN"},
    {"name": "DRC: the cobalt export intervention", "start": "2025-02-22", "end": "2026-12-31",
     "regime": "an outright export suspension from 2025-02-22, extended in June 2025 and replaced "
               "by an operator-level export QUOTA from 2025-10-16; the state acting directly on "
               "the world supply of a commodity it dominates",
     "markers": ("2025-02-22 ARECOMS suspends cobalt exports",
                 "2025-06-21 the suspension is extended",
                 "2025-10-16 the quota regime commences"),
     "why_it_matters": "THE BOUNDARY THAT PARTITIONS EVERY CONGOLESE COBALT SERIES. A tonnage "
                       "series pooled across it is measuring a free export regime and an "
                       "administered one at the same time, and the by-product credit on the "
                       "copper cost curve is different on the two sides",
     "status": "OPEN"},
    {"name": "DRC: the Sicomines infrastructure-for-minerals arrangement and its renegotiation",
     "start": "2008-04-22", "end": "2026-12-31",
     "regime": "infrastructure built by Chinese state contractors against a claim on Congolese "
               "copper and cobalt output, renegotiated in 2024 on terms the government published "
               "as substantially improved for the Congolese side",
     "markers": ("2008 the original convention is signed",
                 "2024 the renegotiated terms are announced",
                 "2024-2025 the corridor and rail financing that follows it"),
     "why_it_matters": "a share of Congolese output is contracted against infrastructure rather "
                       "than sold, which is why Chinese import volumes and Congolese export "
                       "volumes do not move together the way a spot market would imply",
     "status": "OPEN"},
    {"name": "ZAMBIA: the 2019 fiscal reset and the non-deductible royalty", "start": "2019-01-01",
     "end": "2021-12-31",
     "regime": "the royalty scale was raised, a new top band added, an import duty placed on "
               "copper concentrate and the royalty made NON-DEDUCTIBLE against corporate income "
               "tax -- so a mine paid tax on revenue it had already paid royalty on",
     "markers": ("2019-01-01 the non-deductibility and the raised scale commence",
                 "2019-2020 the Konkola liquidation dispute",
                 "2021-08 the general election that changed the government"),
     "why_it_matters": "the after-tax cost of a Zambian tonne was materially higher in this "
                       "window than on either side of it, and the capital spending of the era "
                       "reflects it; a study pooling 2019-2021 with 2022 onward is pooling two "
                       "fiscal regimes",
     "status": "SETTLED"},
    {"name": "ZAMBIA: default and the Common Framework restructuring", "start": "2020-11-13",
     "end": "2024-06-30",
     "regime": "the coupon due 2020-10-14 was missed and the grace period expired on 2020-11-13, "
               "making Zambia the first COVID-era sovereign default; an IMF Extended Credit "
               "Facility followed on 2022-08-31, an Official Creditor Committee agreement in June "
               "2023 and the eurobond exchange in June 2024",
     "markers": ("2020-11-13 the grace period expires and Zambia defaults",
                 "2022-08-31 the IMF arrangement is approved",
                 "2023-06 the official creditor agreement",
                 "2024-06 the eurobond exchange completes"),
     "why_it_matters": "the sovereign's external financing was in negotiation for four years, so "
                       "a Zambian risk event in this window is a RESTRUCTURING event and not a "
                       "market one, and the domestic bond market is where the state actually "
                       "funded itself",
     "status": "SETTLED"},
    {"name": "ZAMBIA: the investment reset -- deductibility restored and the assets change hands",
     "start": "2022-01-01", "end": "2026-12-31",
     "regime": "the mineral royalty was made deductible against corporate income tax again from "
               "the 2022 commencement and the scale was made incremental rather than a cliff; the "
               "state then brokered the two large ownership changes -- the Mopani stake sale "
               "completed in 2024 and the Konkola resolution in the same window -- around a "
               "published national target of three million tonnes",
     "markers": ("2022-01-01 deductibility is restored",
                 "2024-03 the Mopani stake disposal completes",
                 "2024 the Konkola resolution and the operator's return"),
     "why_it_matters": "the fiscal terms, the ownership and the stated national ambition all "
                       "changed inside two years, which is why a Zambian output study that "
                       "crosses 2021-2022 is measuring three treatments at once",
     "status": "OPEN"},
    {"name": "ZAMBIA: the 2024-2025 drought and the power emergency", "start": "2024-02-29",
     "end": "2025-12-31",
     "regime": "the rainfall failure was declared a national disaster on 2024-02-29; Kariba "
               "generation fell to a small fraction of installed capacity, load-shedding "
               "deepened through 2024 to schedules measured in most of a day, and the mines "
               "bought imported power through the regional pool at a large premium",
     "markers": ("2024-02-29 the drought is declared a national disaster",
                 "2024-03 nationwide load management begins in earnest",
                 "2024-12 the deepest shedding schedules",
                 "2025 the following season's inflows ease the constraint"),
     "why_it_matters": "THE LARGEST SUPPLY CONSTRAINT IN RECENT ZAMBIAN COPPER HISTORY and it is "
                       "a WEATHER event with a published daily input; output, cost and the "
                       "maize crop all carry it at once and a study that pools this window with "
                       "normal years attributes a drought to a business cycle",
     "status": "SETTLED"},
    {"name": "REGIONAL: the Lobito reopening and the corridor re-shuffle", "start": "2023-07-01",
     "end": "2026-12-31",
     "regime": "the Benguela railway to the Atlantic was conceded to a private consortium in 2023 "
               "with development-finance backing, carried Congolese copper in 2024 and began a "
               "ramp thereafter, while the TAZARA line to Dar es Salaam was put under a "
               "rehabilitation concession in the same period",
     "markers": ("2023-07 the Lobito Atlantic Railway concession is signed",
                 "2024 the first Congolese copper reaches Lobito",
                 "2024-2025 the TAZARA rehabilitation concession is agreed"),
     "why_it_matters": "a dated, published change in WHERE Central African copper physically "
                       "goes; corridor-share series before and after the boundary are measuring "
                       "different route sets and the substitution has to be modelled explicitly",
     "status": "OPEN"},
    {"name": "REGIONAL: the two-lane order's own boundary for this pack", "start": "2026-09-06",
     "end": "2026-12-31",
     "regime": "single-name equities are traded on news and earnings and are never hunted for "
               "statistical hypotheses; every mining company in this region is therefore an ACTOR "
               "in this pack and never an instrument, and the hypothesis-discovery universe here "
               "is metals, FX, softs, energy and indices only",
     "markers": ("2026-09-06 the principal's two-lane order",
                 "2026-08-18 the MT5 universe mandate that fixes the broker registry as the "
                 "only source of executable symbols"),
     "why_it_matters": "the trial budget is shared across the whole programme, so an equity cell "
                       "compiled here would raise the bar for every FX and metals cell on the "
                       "desk; this era row exists so the boundary is dated inside the pack rather "
                       "than remembered",
     "status": "OPEN"},
)

ACCESS_CONSTRAINTS: tuple[dict[str, Any], ...] = (
    {"constraint": "THIS PACK READS PUBLIC OFFICIAL STATISTICS, PUBLIC INTERNATIONAL-ORGANISATION "
                   "DATA AND PUBLIC PRESS, AND NOTHING ELSE",
     "measured": "every source class carries an ACCESS_LABEL drawn from the public set; no row "
                 "here is PRIVATE, CONFIDENTIAL_MNPI or STOLEN_UNAUTHORIZED",
     "consequence": "NOTHING IN THIS PACK BYPASSES AN ACCESS CONTROL. Nothing is logged into, no "
                    "paywall is circumvented, no rate limit is evaded and no terms-of-service "
                    "restriction on machine extraction is worked around -- a source whose terms "
                    "forbid extraction is REGISTERED with machine_use_allowed=false and read as a "
                    "human reads it, never scraped and never omitted"},
    {"constraint": "ARTISANAL MINING AND THE COBALT SUPPLY CHAIN CARRY WELL-DOCUMENTED "
                   "HUMAN-RIGHTS CONCERNS, AND THEY ARE NOT THIS PACK'S SUBJECT",
     "measured": "CB-E and the artisanal actor row are written entirely from PUBLISHED "
                 "production, flow and policy material: the ministry's reconciliation, the EITI "
                 "reports, the customs and mirror statistics, and the public NGO and trade "
                 "literature",
     "consequence": "THE DESK RECORDS WHAT IS PUBLISHED ABOUT PRODUCTION, FLOWS AND POLICY AND "
                    "NEITHER COLLECTS NOR SEEKS PERSONAL DATA ABOUT ANY INDIVIDUAL MINER. No "
                    "source in this pack is read for personal information, no individual is "
                    "identified anywhere in it, and no cell is conditioned on anything about a "
                    "person. The public social ground is registered machine_use_allowed=false and "
                    "is read for prices, shifts and power outages only"},
    {"constraint": "neither currency is quoted by this broker",
     "measured": "data/universe/universe.json holds no CDF or ZMW symbol",
     "consequence": "every domestic monetary mechanism terminates in the metals, the softs, the "
                    "energy legs or the ZAR carriers; both currencies are INPUTS, never cells, "
                    "and each is named in TRANSMISSION_TARGETS with its route"},
    {"constraint": "THE ZAR COMPLEX IS A PROXY AND IS NEVER THE CURRENCY IT CARRIES",
     "measured": "USDZAR, EURZAR, GBPZAR and ZARJPY are the only liquid Southern African risk "
                 "instruments in the registry, and the rand carries South African idiosyncratic "
                 "risk -- its own power utility, its own central bank, its own bond market -- "
                 "that neither of this pack's economies has",
     "consequence": "every edge and every domain that routes through the ZAR complex names the "
                    "SARB decision calendar and South African data days as a required control, "
                    "and no row in this file calls the carrier the kwacha or the franc"},
    {"constraint": "THERE IS NO COBALT CONTRACT IN THE BROKER REGISTRY",
     "measured": "the registry holds no cobalt symbol of any kind, and the traded price of record "
                 "for hydroxide is a price-reporting agency assessment whose terms forbid machine "
                 "extraction",
     "consequence": "cobalt is routed EXPLICITLY as a copper and nickel BY-PRODUCT: a cobalt "
                    "price or export-regime change moves the by-product credit on the Katangan "
                    "copper cost curve and on the nickel sulphide cost curve, and every cobalt "
                    "mechanism here terminates in XCUUSD and XNIUSD with the Indonesian "
                    "nickel-cobalt ramp named as the control"},
    {"constraint": "the Kariba lake-level page, the BoZ daily rate page and the BCC condense all "
                   "overwrite or replace in place",
     "measured": "each publishes the current reading and keeps no complete archive",
     "consequence": "their point-in-time history exists only in the archive layer's crawls; a "
                    "cell compiled on an un-archived day is UNMEASURED rather than assumed, and "
                    "those datasets carry pit_feasible=False for exactly that reason"},
    {"constraint": "the Kasumbalesa queue is an EPISODIC report and not a series",
     "measured": "there is no continuous official queue-length or clearance-time series on either "
                 "side of the crossing; the corridor dashboards and the press report episodes",
     "consequence": "a week with no report is UNMEASURED and is never treated as a week with no "
                    "queue; CB-L's sample is the reported episodes and the domain says so"},
    {"constraint": "no retail margin or client-flow statistic exists in either jurisdiction",
     "measured": "the DRC licenses no retail margin broker at all and Zambia's securities "
                 "regulator publishes no aggregate retail positioning",
     "consequence": "no microstructure claim in this pack may rest on a retail-flow number; the "
                    "retail ecology is read from public communities at FRINGE credibility and the "
                    "refusal is declared per jurisdiction in NO_LAWFUL_GROUND"},
    {"constraint": "the DRC has no securities market of any kind",
     "measured": "no stock exchange, no public domestic bond curve, no securities tape",
     "consequence": "no Congolese equity-mechanics, expiry or positioning mechanism appears "
                    "anywhere in this pack, and the institutional layer is declared absent for "
                    "Congolese SECURITIES in NO_LAWFUL_GROUND while the mining regulators fill it "
                    "for minerals"},
)

#: INTERACTION MINERS -- the other country packs this one has a MEASURABLE interaction with. The
#: point is to stop the desk testing each country in isolation: most of the controls in this file
#: are another pack's series, and an edge whose control lives in a pack nobody runs is an edge
#: nobody can falsify.
INTERACTIONS: tuple[dict[str, Any], ...] = (
    {"with": "east_africa",
     "mechanism": "THE DAR ES SALAAM CENTRAL CORRIDOR IS THIS PACK'S EXPORT ROUTE AND THAT PACK'S "
                  "PORT. Congolese and Zambian copper and cobalt leave through Dar es Salaam by "
                  "road through Nakonde-Tunduma and by TAZARA rail, and `east_africa` owns the "
                  "Tanzanian end of exactly the series this pack needs -- its own CB-G domain is "
                  "built on the Central Corridor as a copper and cobalt chokepoint whose CARGO "
                  "originates here. THE TWO PACKS ARE ONE PHYSICAL SYSTEM and neither can tell a "
                  "chokepoint from a re-routing alone",
     "observable": "Tanzania Ports Authority transit tonnage BY DESTINATION COUNTRY beside this "
                   "pack's corridor-share series; Central Corridor transit times beside the "
                   "Kasumbalesa clearance reports; TAZARA freight tonnage on both sides of the "
                   "rehabilitation concession",
     "targets": ("XCUUSD", "XNIUSD", "XBRUSD", "USDZAR"),
     "control": "total Congolese and Zambian export tonnage, which separates 'the metal took "
                "another road' from 'less metal left'. A fall in Central Corridor transit that "
                "appears as a rise at Lobito or Durban is a ROUTING event and carries no supply "
                "information at all -- AND NEITHER PACK CAN ESTABLISH THAT ALONE, which is the "
                "strongest interaction in this file and the reason it is named first"},
    {"with": "za",
     "mechanism": "SOUTH AFRICA IS BOTH THE OTHER END OF THE DURBAN CORRIDOR AND THE CARRIER OF "
                  "EVERY UNQUOTABLE CURRENCY HERE. The historic export route runs through "
                  "Kasumbalesa, Chirundu and BEITBRIDGE to Durban, whose delays are `za`'s own "
                  "ground; and USDZAR, EURZAR, GBPZAR and ZARJPY are the executable carrier this "
                  "pack routes the franc and the kwacha through",
     "observable": "Beitbridge border delays and Transnet rail and port performance beside this "
                   "pack's corridor share; the SARB decision calendar and South African data days "
                   "as the required control on every carrier leg; regional power-pool conditions "
                   "beside the Kariba state",
     "targets": ("USDZAR", "EURZAR", "GBPZAR", "ZARJPY", "XCUUSD"),
     "control": "A CARRIER IS NOT A SUBSTITUTE. The rand contains South African idiosyncratic "
                "risk -- its own utility, its own central bank, its own bond market -- that "
                "neither of these economies has, and every edge that routes through it must "
                "control for the SARB calendar or it is measuring South Africa"},
    {"with": "cl",
     "mechanism": "CHILE IS THE WORLD'S LARGEST COPPER PRODUCER AND THEREFORE THIS PACK'S "
                  "PRIMARY CONTROL. Every supply claim here -- a ramp, a power cut, an export "
                  "ban, a border queue -- has to survive the question 'did Chilean output do the "
                  "same thing?', and Chile has its own water and power constraints that look "
                  "superficially like Zambia's and arise from a completely different cause",
     "observable": "Chilean monthly output and export volumes beside Congolese and Zambian "
                   "production; Chilean desalination and water-rights constraints beside the "
                   "Kariba state; Chilean fiscal and royalty changes beside CB-C and CB-J",
     "targets": ("XCUUSD", "XZNUSD", "USDCNH"),
     "control": "Chile is the SEPARATOR that decides whether a Copperbelt supply event is about "
                "the Copperbelt or about copper: a price move on a Congolese announcement that "
                "coincides with a Chilean disruption is a copper event with a Congolese headline"},
    {"with": "pe",
     "mechanism": "PERU IS THE COUNTRY THE DRC OVERTOOK, and that overtaking is a dated, "
                  "published fact in the USGS country table. Peru is also the desk's other "
                  "example of mining supply interrupted by things that are not geology -- "
                  "community blockades on its own mining corridor -- which is the closest "
                  "available analogue to a Kasumbalesa queue or a corridor failure",
     "observable": "Peruvian monthly output beside Congolese output across the 2023-2024 "
                   "crossover; Peruvian road-blockade episodes beside Kasumbalesa queue episodes, "
                   "as two independent tests of whether a logistics interruption reaches a price",
     "targets": ("XCUUSD", "XZNUSD", "XPBUSD"),
     "control": "THE BLOCKADE ANALOGUE IS THE VALUABLE HALF: if a Peruvian blockade moves the "
                "price and a Congolese border queue does not, the difference is the tonnage and "
                "the inventory, and that is a testable statement rather than a story"},
    {"with": "cn",
     "mechanism": "CHINA IS THE BUYER AT THE END OF ALL FOUR CORRIDORS, the owner or offtaker of "
                  "much of the production, the financier of the corridor infrastructure and the "
                  "refiner of the cobalt hydroxide. Chinese demand is the CONFOUND in every "
                  "domain in this pack",
     "observable": "Chinese customs imports of refined copper, concentrate and cobalt hydroxide "
                   "against corridor tonnage and against the export-regime dates; the Shanghai "
                   "close and the bonded premium against the LME",
     "targets": ("XCUUSD", "XNIUSD", "USDCNH"),
     "control": "the `cn` pack's own demand series is a REQUIRED control and not an optional one: "
                "a Copperbelt supply event during a Chinese demand move is not a supply event, "
                "and no chokepoint cell here is compiled without it"},
    {"with": "gh",
     "mechanism": "GHANA IS THE MATCHED FRONTIER CASE FOR THE FISCAL HALF: it defaulted in the "
                  "same cycle as Zambia and restructured under the same G20 Common Framework, "
                  "with its own resource-revenue dependence and its own IMF programme clock",
     "observable": "Ghana's default and restructuring milestone dates against Zambia's; the two "
                   "programmes' review Board dates; the two currencies' behaviour around the same "
                   "global risk events",
     "targets": ("USDZAR", "US500", "XAUUSD"),
     "control": "Ghana is the PLACEBO that decides whether CB-H is about ZAMBIA or about frontier "
                "default as a class; Ethiopia, inside `east_africa`, is the third case in the "
                "same cycle and makes the comparison a panel rather than a pair"},
)


INSTITUTIONAL_FLOW_SOURCES: tuple[str, ...] = (
    "Zambezi River Authority daily Kariba lake level and usable storage",
    "ZESCO load-management schedules and the published shedding hours",
    "Zambia Revenue Authority monthly mineral royalty and mining tax receipts",
    "Ministry of Mines and Minerals Development Zambian production statistics",
    "Ministere des Mines RDC production and export tonnage by province",
    "ARECOMS cobalt export decisions and the quota allocations",
    "Corridor throughput and transit tonnage by destination country, all four routes",
    "UN Comtrade mirror statistics for refined copper, concentrate and cobalt",
    "Bank of Zambia interbank rate, intervention, reserves and the reserve-ratio circulars",
    "Banque Centrale du Congo condense hebdomadaire and the taux directeur",
)
SERIES: dict[str, str] = {
    "CD_FX": "BCC:taux_de_change_indicatif", "CD_RATE": "BCC:taux_directeur",
    "CD_RESERVES": "BCC:reserves", "CD_CU": "MINES_CD:copper_production",
    "CD_CO": "MINES_CD:cobalt_production", "CD_COBALT_REGIME": "ARECOMS:export_regime",
    "CD_EXPORTS": "DGDA:mineral_exports", "CD_EITI": "EITI_CD:reconciliation_gap",
    "ZM_FX": "BOZ:interbank_mid", "ZM_RATE": "BOZ:policy_rate", "ZM_SRR": "BOZ:statutory_reserve",
    "ZM_RESERVES": "BOZ:gross_reserves", "ZM_CU": "MMMD:copper_output",
    "ZM_ROYALTY": "ZRA_TAX:mineral_royalty", "ZM_CPI": "ZAMSTATS:cpi",
    "ZM_KARIBA": "ZRA_WATER:kariba_level", "ZM_SHEDDING": "ZESCO:load_shedding_hours",
    "ZM_DEBT": "MOF_ZM:restructuring_milestones",
    "CB_CORRIDOR": "CORRIDORS:transit_by_route", "CB_QUEUE": "BORDER:kasumbalesa_queue",
    "CB_MIRROR": "COMTRADE:hs7403_7108_gap", "CB_BALANCE": "ICSG:world_balance",
    "CB_MOBILE_MONEY": "BOZ_ARPTC:mobile_money_value",
}


# --------------------------------------------------------------------------- mechanisms
#: THE DATED COBALT-POLICY EVENTS. Rows are (date, jurisdiction, what, status). GAZETTED means the
#: instrument itself is citable; PRESS_REPORTED means a date carried by the trade press or a
#: ministerial communique, to be confirmed against the Journal Officiel before any cell is
#: promoted on it. Saying which is which is the difference between a citation and a claim.
COBALT_POLICY_EVENTS: tuple[tuple[date, str, str, str], ...] = (
    (date(2018, 12, 1), "cd", "cobalt is declared a strategic substance and the royalty is set at "
                              "ten per cent under the 2018 Code minier", "GAZETTED"),
    (date(2025, 2, 22), "cd", "ARECOMS suspends all cobalt exports to defend a collapsed price",
     "GAZETTED"),
    (date(2025, 6, 21), "cd", "the export suspension is extended for a further period",
     "PRESS_REPORTED"),
    (date(2025, 10, 16), "cd", "the outright suspension is replaced by an operator-level export "
                               "QUOTA regime", "PRESS_REPORTED"),
)
#: The export regime in force from each date. A cell in CB-A is conditioned on which of these it
#: sits in, because a free export regime and an administered one are different economies.
COBALT_EXPORT_REGIME: tuple[tuple[date, str], ...] = (
    (date(2025, 2, 22), "SUSPENDED"),
    (date(2025, 10, 16), "QUOTA"),
)

#: THE ZAMBIAN DROUGHT AND POWER EMERGENCY, dated. Rows are (date, what, status).
DROUGHT_EVENTS: tuple[tuple[date, str, str], ...] = (
    (date(2024, 2, 29), "the rainfall failure is declared a national disaster", "GAZETTED"),
    (date(2024, 3, 11), "nationwide load management deepens as Kariba generation falls",
     "PRESS_REPORTED"),
    (date(2024, 12, 1), "the deepest published shedding schedules of the emergency",
     "PRESS_REPORTED"),
    (date(2025, 4, 1), "the following season's inflows ease the constraint", "PRESS_REPORTED"),
)

#: THE FOUR ROADS TO THE SEA. Each row names the route, the port, the approximate road distance
#: from the Katangan mining centres, the mode and the failure mode that is distinctly ITS OWN.
#: Distances are approximate and are labelled approximate: they are here to rank the routes, not
#: to be regressed on.
EXPORT_ROUTES: tuple[dict[str, Any], ...] = (
    {"route": "durban", "port": "Durban", "countries": ("zm", "zw", "za"),
     "approx_km": 3000, "mode": "road, with rail on the South African leg",
     "chokepoint": "Kasumbalesa, then Chirundu, then BEITBRIDGE",
     "failure_mode": "border congestion at two crossings and South African rail and port "
                     "performance at the far end -- the `za` pack's own ground",
     "sibling_pack": "za"},
    {"route": "dar_es_salaam", "port": "Dar es Salaam", "countries": ("zm", "tz"),
     "approx_km": 2100, "mode": "road through Nakonde-Tunduma and TAZARA rail",
     "chokepoint": "the Nakonde-Tunduma crossing and the TAZARA line's condition",
     "failure_mode": "rail capacity and port dwell time; the corridor is the Central Corridor and "
                     "its Tanzanian end belongs to `east_africa`",
     "sibling_pack": "east_africa"},
    {"route": "beira_nacala", "port": "Beira and Nacala", "countries": ("zm", "mw", "mz"),
     "approx_km": 2000, "mode": "road to Beira; the Nacala corridor railway through Malawi",
     "chokepoint": "the Mozambican port capacity and the Malawian rail leg",
     "failure_mode": "cyclone season at the ports and a rail line with limited capacity",
     "sibling_pack": ""},
    {"route": "lobito", "port": "Lobito", "countries": ("cd", "ao"),
     "approx_km": 1500, "mode": "the Benguela railway under a 2023 concession",
     "chokepoint": "rolling stock and track capacity, and the Atlantic port's handling",
     "failure_mode": "a ramp that is capacity on paper until the rolling stock arrives",
     "sibling_pack": ""},
)
#: The Lobito reopening, dated. Rows are (date, what, status).
LOBITO_EVENTS: tuple[tuple[date, str, str], ...] = (
    (date(2023, 7, 1), "the Benguela railway is conceded to a private consortium with "
                       "development-finance backing", "PRESS_REPORTED"),
    (date(2024, 1, 1), "Congolese copper reaches the Atlantic through Lobito", "PRESS_REPORTED"),
    (date(2025, 1, 1), "the corridor ramps and the TAZARA rehabilitation concession is agreed on "
                       "the other side of the continent", "PRESS_REPORTED"),
)

#: ZAMBIA'S SOVEREIGN SEQUENCE, dated. Rows are (date, what, status).
ZM_DEFAULT_EVENTS: tuple[tuple[date, str, str], ...] = (
    (date(2020, 10, 14), "the eurobond coupon is missed and the grace period begins", "GAZETTED"),
    (date(2020, 11, 13), "the grace period expires: the first COVID-era sovereign default",
     "GAZETTED"),
    (date(2022, 8, 31), "the IMF Extended Credit Facility is approved", "GAZETTED"),
    (date(2023, 6, 22), "the Official Creditor Committee agreement is announced",
     "PRESS_REPORTED"),
    (date(2024, 6, 13), "the eurobond exchange completes", "PRESS_REPORTED"),
)
#: The Zambian mineral-royalty deductibility boundaries. Rows are (date, deductible, note).
ZM_ROYALTY_REGIME: tuple[tuple[date, bool, str], ...] = (
    (date(2019, 1, 1), False, "the 2019 commencement raises the scale, adds a top band and makes "
                              "the royalty NON-DEDUCTIBLE against corporate income tax"),
    (date(2022, 1, 1), True, "deductibility is restored and the scale is made incremental rather "
                             "than a cliff"),
)
#: PRODUCTION MILESTONES on both sides of the border, dated and labelled. Rows are
#: (date, jurisdiction, what, status).
PRODUCTION_MILESTONES: tuple[tuple[date, str, str, str], ...] = (
    (date(2021, 5, 1), "cd", "the first phase of the Kolwezi-area greenfield project reaches "
                             "first concentrate", "PRESS_REPORTED"),
    (date(2023, 1, 1), "cd", "the Katangan expansions carry Congolese output past Peru's into "
                             "second place worldwide", "PRESS_REPORTED"),
    (date(2024, 1, 1), "cd", "a further phased expansion lifts Congolese output toward three "
                             "million tonnes a year", "PRESS_REPORTED"),
    (date(2024, 3, 1), "zm", "the Mopani stake disposal completes and the recapitalisation begins",
     "PRESS_REPORTED"),
    (date(2024, 6, 1), "zm", "the Konkola resolution returns the asset to its operator",
     "PRESS_REPORTED"),
    (date(2025, 1, 1), "zm", "Zambian output recovers past eight hundred thousand tonnes against "
                             "the published three-million-tonne national target", "PRESS_REPORTED"),
)

COBALT_BAN_DATE = date(2025, 2, 22)
COBALT_QUOTA_DATE = date(2025, 10, 16)
ZM_DEFAULT_DATE = date(2020, 11, 13)
DROUGHT_DISASTER_DATE = date(2024, 2, 29)


def cobalt_export_regime(day: date) -> str:
    """The Congolese cobalt export regime on a date: FREE, SUSPENDED or QUOTA.

    This is the boundary that partitions every Congolese cobalt series, and a study that pools
    across it is measuring a free export regime and an administered one at the same time.
    """
    regime = "FREE"
    for start, name in COBALT_EXPORT_REGIME:
        if day >= start:
            regime = name
    return regime


def kariba_season(day: date) -> str:
    """The Zambezi hydrological phase a date sits in.

    RAINS_INFLOW runs December to April when the catchment fills; PEAK_STORAGE runs May to August
    when the lake is at its fullest; DRAWDOWN_MINIMUM runs September to November, which is when
    the constraint binds and when a load-shedding emergency actually bites. Bucketing by calendar
    year splits every hydrological year in half, which is the standard error in this ground.
    """
    month = day.month
    if month >= 12 or month <= 4:
        return "RAINS_INFLOW"
    if 5 <= month <= 8:
        return "PEAK_STORAGE"
    return "DRAWDOWN_MINIMUM"


def load_shedding_phase(day: date) -> str:
    """Zambia's power-emergency phase on a date: NORMAL, DECLARED_DISASTER, DEEP or EASING."""
    phases = ("DECLARED_DISASTER", "DEEP", "DEEP", "EASING")
    phase = "NORMAL"
    for (start, _what, _status), name in zip(DROUGHT_EVENTS, phases, strict=True):
        if day >= start:
            phase = name
    return phase


def lobito_phase(day: date) -> str:
    """The Lobito corridor's phase on a date: CLOSED_TO_COPPER, CONCESSION_SIGNED, FIRST_COPPER or
    RAMP. A corridor-share series pooled across these boundaries is measuring different route
    sets and calling them one."""
    phases = ("CONCESSION_SIGNED", "FIRST_COPPER", "RAMP")
    phase = "CLOSED_TO_COPPER"
    for (start, _what, _status), name in zip(LOBITO_EVENTS, phases, strict=True):
        if day >= start:
            phase = name
    return phase


def zambia_debt_phase(day: date) -> str:
    """Zambia's sovereign phase on a date: PRE_DEFAULT, GRACE_PERIOD, DEFAULT, IMF_PROGRAMME,
    OCC_AGREEMENT or BONDS_EXCHANGED. Six states, five dated boundaries, and a risk event in one
    of them is not the same object as the same event in another."""
    phases = ("GRACE_PERIOD", "DEFAULT", "IMF_PROGRAMME", "OCC_AGREEMENT", "BONDS_EXCHANGED")
    phase = "PRE_DEFAULT"
    for (start, _what, _status), name in zip(ZM_DEFAULT_EVENTS, phases, strict=True):
        if day >= start:
            phase = name
    return phase


def royalty_deductible(day: date) -> bool:
    """Whether the Zambian mineral royalty was deductible against corporate income tax on a date.

    Deductible before the 2019 commencement, NOT deductible from 2019-01-01, and deductible again
    from 2022-01-01. It is a dated, published change in the after-tax cost of a tonne, and it is
    the clause that moved most in the Zambian fiscal regime.
    """
    deductible = True
    for start, value, _note in ZM_ROYALTY_REGIME:
        if day >= start:
            deductible = value
    return deductible


def corridor_state(day: date) -> dict[str, str]:
    """Every export route's availability on a date, as a mapping. Three of the four have been
    continuously available; the Atlantic route is the one with a dated reopening, which is what
    makes the corridor share a measurable treatment rather than a constant."""
    lobito = lobito_phase(day)
    return {row["route"]: ("OPEN" if row["route"] != "lobito" else lobito)
            for row in EXPORT_ROUTES}


def jurisdiction_of_domain(domain_id: str) -> tuple[str, ...]:
    """Which of the two countries a domain belongs to. A regional domain names both."""
    return DOMAIN_JURISDICTION.get(str(domain_id), JURISDICTIONS)


#: Which jurisdiction owns each domain, so a test can prove the pack owes each of the two at
#: least four domains of its own rather than two countries' worth of one country's mechanisms.
DOMAIN_JURISDICTION: dict[str, tuple[str, ...]] = {
    "CB-A": ("cd",), "CB-B": ("cd",), "CB-C": ("cd",), "CB-D": ("cd",), "CB-E": ("cd",),
    "CB-F": ("zm",), "CB-G": ("zm",), "CB-H": ("zm",), "CB-I": ("zm",), "CB-J": ("zm",),
    "CB-K": ("cd", "zm"), "CB-L": ("cd", "zm"), "CB-M": ("cd", "zm"), "CB-N": ("cd", "zm"),
}
#: Which jurisdiction each actor belongs to, by position in ACTORS. Eight Congolese, eight Zambian
#: and two regional -- the brief's floor is six per jurisdiction.
ACTOR_JURISDICTION: tuple[str, ...] = (
    "cd", "cd", "cd", "cd", "cd", "cd", "cd", "cd",
    "zm", "zm", "zm", "zm", "zm", "zm", "zm", "zm",
    "regional", "regional",
)
#: The mechanism family and the horizon each domain mints its cells under.
DOMAIN_MECHANISM: dict[str, str] = {
    "CB-A": "administered_price", "CB-B": "capacity_ramp", "CB-C": "regime_break",
    "CB-D": "capital_control_stress", "CB-E": "supply_shock", "CB-F": "supply_shock",
    "CB-G": "capacity_ramp", "CB-H": "event_reaction", "CB-I": "policy_surprise",
    "CB-J": "fiscal_flow", "CB-K": "chokepoint", "CB-L": "chokepoint",
    "CB-M": "holiday_liquidity", "CB-N": "nominal_demand",
}
DOMAIN_HORIZON: dict[str, str] = {
    "CB-A": "0 to 5 sessions and 1 to 3 quarters", "CB-B": "1 to 4 quarters",
    "CB-C": "2 to 8 quarters", "CB-D": "1 to 2 quarters", "CB-E": "1 to 3 quarters",
    "CB-F": "0 to 10 sessions and 1 to 3 quarters", "CB-G": "1 to 4 quarters",
    "CB-H": "0 to 5 sessions", "CB-I": "0 to 5 sessions", "CB-J": "2 to 8 quarters",
    "CB-K": "1 to 8 quarters", "CB-L": "2 to 8 weeks", "CB-M": "0 to 2 sessions",
    "CB-N": "1 to 2 quarters",
}


def cells() -> tuple[dict[str, Any], ...]:
    """THE TESTABLE CELLS THIS PACK MINTS: every domain crossed with its own instruments and its
    own named conditions, and nothing else.

    This is deliberately NOT a cartesian product of every domain against every executable
    instrument. A cell is only worth a trial if the pack's own data plane can evaluate its
    CONDITION on that SYMBOL, so the cross product is taken inside each domain, where the
    instruments were chosen for the mechanism and the conditions are states the pack's own series
    can resolve. That is the difference between maximising cells and maximising noise: a blown-up
    grid spends the programme's shared family-wise error budget on cells nobody can fill, and
    every FX and metals cell on the desk pays for it (two-lane order, 2026-09-06).
    """
    out: list[dict[str, Any]] = []
    for dom in DOMAINS:
        did = str(dom["id"])
        controls = tuple(dom["controls"])
        for symbol in dom["instruments"]:
            for i, condition in enumerate(dom["conditions"]):
                out.append({
                    "cell_id": f"{CODE}:{did}:{symbol}:c{i}",
                    "domain": did,
                    "jurisdictions": DOMAIN_JURISDICTION.get(did, JURISDICTIONS),
                    "symbol": str(symbol),
                    "condition": str(condition),
                    "mechanism_family": DOMAIN_MECHANISM.get(did, "residual"),
                    "horizon": DOMAIN_HORIZON.get(did, "1 to 2 quarters"),
                    "control": controls[i % len(controls)] if controls else "",
                    "why": f"{dom['title']} -- conditioned on {condition}",
                })
    return tuple(out)


CELLS: tuple[dict[str, Any], ...] = cells()


# --------------------------------------------------------------------------- the department
def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _emit(ctx: Any, rows: list[dict[str, Any]]) -> int:
    """Hand rows to the department Ctx when one is given, and count what was taken.

    `mine()` must work with NO context at all -- that is how a test calls it, and how a fresh
    session checks the pack without wiring anything -- so an absent ctx is a normal return and
    never an error.
    """
    if ctx is None:
        return 0
    record = getattr(ctx, "record", None)
    if not callable(record):
        return 0
    taken = 0
    for row in rows:
        try:
            record(row)
        except Exception:                      # a ctx that refuses a row is the ctx's business
            continue
        taken += 1
    return taken


def mine_cobalt_regime(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """CB-A and CB-E: the cobalt export regime as a dated clock, routed through copper and nickel.

    There is no cobalt contract in the broker registry, so every row here terminates in XCUUSD
    and XNIUSD with the by-product route stated and the Indonesian ramp named as the control.
    """
    rows = [{"kind": "hypothesis", "pack": CODE, "domain": "CB-A", "jurisdiction": juris,
             "at": day.isoformat(), "what": what, "status": status,
             "symbols": ["XCUUSD", "XNIUSD"],
             "regime_after": cobalt_export_regime(day),
             "regime_before": cobalt_export_regime(day - timedelta(days=1)),
             "family": "administered_price", "horizon": "0 to 5 sessions and 1 to 3 quarters",
             "route": "cobalt is a copper and nickel BY-PRODUCT: the price is a credit on both "
                      "cost curves, and that credit is the whole transmission",
             "control": "the Indonesian nickel-cobalt ramp; Chinese hydroxide import volumes; "
                        "the matched-weekday control on XCUUSD around each decision date"}
            for day, juris, what, status in COBALT_POLICY_EVENTS]
    rows.append({"kind": "hypothesis", "pack": CODE, "domain": "CB-E", "jurisdiction": "cd",
                 "at": _now(), "what": "the artisanal share of Congolese cobalt output as the "
                                       "fastest supply response in the market, conditioned on the "
                                       "November-April rains and on the export regime in force",
                 "symbols": ["XCUUSD", "XNIUSD", "XAUUSD"], "family": "supply_shock",
                 "horizon": "1 to 3 quarters",
                 "control": "Congolese INDUSTRIAL output over the same quarters, which is the "
                            "direct separator; the eastern artisanal gold flow as an independent "
                            "second artisanal leg"})
    return {"miner": "cb_cobalt_regime", "code": CODE, "at": _now(), "rows": rows,
            "emitted": _emit(ctx, rows),
            "unmeasured": ["the quota volumes are allocated operator by operator and are reported "
                           "rather than published in full; an unpublished allocation is "
                           "UNMEASURED and no cell is compiled on a reported number alone",
                           "the hydroxide price of record is a price-reporting agency assessment "
                           "whose terms forbid machine extraction: registered, never read by "
                           "machine, and the route to a cell is always through copper or nickel"]}


def mine_kariba_power(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """CB-F: the daily lake level and the load-shedding phase as one physical state."""
    rows = [{"kind": "hypothesis", "pack": CODE, "domain": "CB-F", "jurisdiction": "zm",
             "at": day.isoformat(), "what": what, "status": status,
             "phase": load_shedding_phase(day), "season": kariba_season(day),
             "symbols": ["XCUUSD", "XALUSD", "XNGUSD"], "family": "supply_shock",
             "horizon": "0 to 10 sessions and 1 to 3 quarters",
             "control": "the same calendar weeks in years with normal storage; Zambian copper "
                        "OUTPUT in the same quarters, because the claim is about SMELTER power "
                        "and not about household shedding; regional power-pool conditions"}
            for day, what, status in DROUGHT_EVENTS]
    rows.append({"kind": "hypothesis", "pack": CODE, "domain": "CB-F", "jurisdiction": "zm",
                 "at": _now(),
                 "what": "the EX-ANTE leg: the seasonal rainfall outlook published months before "
                         "the season, against the usable storage the season actually delivers",
                 "symbols": ["XCUUSD", "CORN", "SUGAR"], "family": "supply_shock",
                 "horizon": "1 to 3 quarters",
                 "control": "southern African regional production over the same seasons, which "
                            "separates a Zambian failure from a regional one; a block-permuted "
                            "lake-level series as the null for any daily-lead claim"})
    return {"miner": "cb_kariba_power", "code": CODE, "at": _now(), "rows": rows,
            "emitted": _emit(ctx, rows),
            "unmeasured": ["the lake-level page shows TODAY and keeps no complete archive, so any "
                           "day the archive layer did not crawl is UNMEASURED and is never "
                           "interpolated",
                           "MINE curtailment is disclosed by the operators and not by the "
                           "utility; the published shedding hours are mostly the household "
                           "schedule and the two must never be used interchangeably"]}


def mine_corridor_share(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """CB-K and CB-L: the four roads to the sea, WITH the routing control that makes them
    interpretable. This miner cannot run honestly without `east_africa`'s Tanzanian series and
    `za`'s Durban one, and it says so on every row."""
    rows: list[dict[str, Any]] = [
        {"kind": "hypothesis", "pack": CODE, "domain": "CB-K", "jurisdiction": "cd",
         "at": day.isoformat(), "what": what, "status": status, "phase": lobito_phase(day),
         "symbols": ["XCUUSD", "XBRUSD"], "family": "chokepoint", "horizon": "1 to 8 quarters",
         "needs_sibling_pack": "east_africa",
         "control": "the other three corridors' own throughput: a rise at Lobito matched by a "
                    "fall at Dar es Salaam or Durban is a ROUTING event with no supply content"}
        for day, what, status in LOBITO_EVENTS]
    rows.append({"kind": "hypothesis", "pack": CODE, "domain": "CB-L", "jurisdiction": "zm",
                 "at": _now(),
                 "what": "a reported Kasumbalesa queue episode as an inventory-timing event, "
                         "tested against the honest prior that visible inventory absorbs it",
                 "symbols": ["XCUUSD", "XBRUSD"], "family": "chokepoint", "horizon": "2 to 8 weeks",
                 "needs_sibling_pack": "east_africa",
                 "control": "corridor substitution; exchange and bonded inventory changes over "
                            "the same weeks, which is what inventory is FOR; matched weeks with "
                            "no reported queue in the same season"})
    return {"miner": "cb_corridor_share", "code": CODE, "at": _now(), "rows": rows,
            "emitted": _emit(ctx, rows),
            "unmeasured": ["corridor throughput is published irregularly and the Lobito tonnage "
                           "comes through the trade press; a missing month is UNMEASURED and this "
                           "miner refuses to interpolate it",
                           "the Kasumbalesa queue is an EPISODIC report and not a series: a week "
                           "with no report is not a week with no queue"]}


def mine_output_ramp(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """CB-B and CB-G: the two countries' production milestones against the world balance."""
    rows = [{"kind": "hypothesis", "pack": CODE,
             "domain": "CB-B" if juris == "cd" else "CB-G", "jurisdiction": juris,
             "at": day.isoformat(), "what": what, "status": status,
             "symbols": ["XCUUSD", "XZNUSD"] if juris == "zm" else ["XCUUSD", "XNIUSD"],
             "family": "capacity_ramp", "horizon": "1 to 4 quarters",
             "control": "Chilean and Peruvian quarterly output over the same quarters, which "
                        "separates 'copper supply grew' from 'THIS copper supply grew'; the ICSG "
                        "world balance state; matched non-milestone quarters"}
            for day, juris, what, status in PRODUCTION_MILESTONES]
    return {"miner": "cb_output_ramp", "code": CODE, "at": _now(), "rows": rows,
            "emitted": _emit(ctx, rows),
            "unmeasured": ["the ministries' production tables are published late and restated; "
                           "the royalty receipt is the independent cross-check and it measures "
                           "assessed value rather than tonnage",
                           "most of these milestones are PRESS_REPORTED rather than gazetted and "
                           "no cell is promoted on one until the disclosure confirms it"]}


def mine_fiscal_sequence(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """CB-H, CB-J and CB-C: the sovereign sequence and the two fiscal regimes as dated clocks."""
    rows: list[dict[str, Any]] = [
        {"kind": "hypothesis", "pack": CODE, "domain": "CB-H", "jurisdiction": "zm",
         "at": day.isoformat(), "what": what, "status": status,
         "phase_after": zambia_debt_phase(day),
         "phase_before": zambia_debt_phase(day - timedelta(days=1)),
         "symbols": ["USDZAR", "US500", "EURZAR"], "family": "event_reaction",
         "horizon": "0 to 5 sessions",
         "control": "Ghana's and Ethiopia's own milestone dates as matched frontier events; US "
                    "CPI and FOMC days, which separate 'the frontier repriced' from 'the dollar "
                    "repriced'; a randomised-date null from the same quarters"}
        for day, what, status in ZM_DEFAULT_EVENTS]
    rows.extend({"kind": "hypothesis", "pack": CODE, "domain": "CB-J", "jurisdiction": "zm",
                 "at": day.isoformat(), "what": note, "status": "GAZETTED",
                 "deductible": deductible, "symbols": ["XCUUSD", "USDZAR"],
                 "family": "fiscal_flow", "horizon": "2 to 8 quarters",
                 "control": "Congolese fiscal changes over the same years as the matched frontier "
                            "case; budget rounds that changed other clauses and left the royalty "
                            "alone; the world copper capital cycle"}
                for day, deductible, note in ZM_ROYALTY_REGIME)
    rows.append({"kind": "hypothesis", "pack": CODE, "domain": "CB-C", "jurisdiction": "cd",
                 "at": date(2018, 3, 9).isoformat(),
                 "what": "the 2018 Code minier removes the stability clause and creates the "
                         "strategic-substance category the cobalt royalty was set under",
                 "status": "GAZETTED", "symbols": ["XCUUSD", "XNIUSD"], "family": "regime_break",
                 "horizon": "2 to 8 quarters",
                 "control": "Zambian fiscal changes over the same years as the matched frontier "
                            "case; the affected operations' capital spending against matched "
                            "Congolese operations with no instrument touching them"})
    return {"miner": "cb_fiscal_sequence", "code": CODE, "at": _now(), "rows": rows,
            "emitted": _emit(ctx, rows),
            "unmeasured": ["the honest prior is that a single frontier restructuring has NO "
                           "measurable global spillover; CB-H exists to measure that rather than "
                           "to assume it, and an unmeasured spillover is a result",
                           "the VAT refund arrears position is published irregularly and is a "
                           "politically live number; an absent print is UNMEASURED, never a zero"]}


def mine_calendar_plane(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """CB-M: two calendars over one orebody, with the one-country-closed days as the control."""
    rows: list[dict[str, Any]] = []
    for year in HOLIDAYS_RULE["years"]:
        closures = {code: fn(year) for code, fn in JURISDICTION_HOLIDAY_FN.items()}
        for day in sorted(set().union(*(set(c) for c in closures.values()))):
            if day.weekday() >= 5:
                continue
            closed = tuple(sorted(c for c, tbl in closures.items() if day in tbl))
            rows.append({"kind": "hypothesis", "pack": CODE, "domain": "CB-M",
                         "at": day.isoformat(), "closed": closed,
                         "both": len(closed) == len(JURISDICTIONS),
                         "declared": day in declared_closures(year),
                         "symbols": ["XCUUSD", "XAUUSD", "USDZAR"],
                         "family": "holiday_liquidity", "horizon": "0 to 2 sessions",
                         "control": "the matched weekday twenty-six weeks away; days on which "
                                    "only ONE of the two closed, which is the within-region "
                                    "control no single-country pack can construct"})
    return {"miner": "cb_calendar_plane", "code": CODE, "at": _now(), "rows": rows,
            "emitted": _emit(ctx, rows),
            "unmeasured": ["the Zambian President may declare a public holiday by statutory "
                           "instrument at any time, so a future closure is SCHEDULED at best and "
                           "unknowable at worst; no cell is promoted on a SCHEDULED row"]}


def mine_transmission_seeds(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """The pack's own transmission map, as HYPOTHESIS discoveries the registry deduplicates."""
    rows = [{"kind": "hypothesis", "pack": CODE, "domain": "transmission", "at": _now(),
             "edge": str(seed["id"]), "what": str(seed["mechanism"]),
             "symbols": list(seed["targets"]), "family": "transfer",
             "horizon": str(seed["horizon"]), "evidence": str(seed["evidence"]),
             "control": str(seed["control"]), "falsifier": str(seed["falsifier"])}
            for seed in TRANSMISSION_EDGES_SEED]
    return {"miner": "cb_transmission_seeds", "code": CODE, "at": _now(), "rows": rows,
            "emitted": _emit(ctx, rows), "unmeasured": []}


MINERS: dict[str, Any] = {
    "mine_cobalt_regime": mine_cobalt_regime,
    "mine_kariba_power": mine_kariba_power,
    "mine_corridor_share": mine_corridor_share,
    "mine_output_ramp": mine_output_ramp,
    "mine_fiscal_sequence": mine_fiscal_sequence,
    "mine_calendar_plane": mine_calendar_plane,
    "mine_transmission_seeds": mine_transmission_seeds,
}


def mine(ctx: Any = None) -> dict[str, Any]:
    """THE DEPARTMENT ENTRY. Pure Python, no network, no LLM and no heavy import.

    It runs the pack's own seven miners over the pack's own tables, emits through the department
    Ctx when one is given, and returns a plain report when one is not -- which is how a test calls
    it and how a fresh session checks the pack with nothing wired.
    """
    rows: list[dict[str, Any]] = []
    unmeasured: list[str] = []
    emitted = 0
    for name, fn in MINERS.items():
        try:
            got = fn(None, ctx)
        except Exception as exc:               # a broken miner is NAMED, never silently skipped
            unmeasured.append(f"{name}: raised {type(exc).__name__}: {exc}")
            continue
        rows.extend(got.get("rows", ()))
        unmeasured.extend(got.get("unmeasured", ()))
        emitted += int(got.get("emitted", 0))
    coverage = source_layer_coverage()
    return {"code": CODE, "jurisdictions": JURISDICTIONS, "at": _now(), "emitted": emitted,
            "rows": rows, "unmeasured": unmeasured,
            "cells_emitted": len(cells()),
            "miners": tuple(MINERS),
            "layers_covered": coverage["n_layers_covered"],
            "sources": coverage["n_sources"],
            "datasets": len(DATASETS), "actors": len(ACTORS), "domains": len(DOMAINS),
            "edges": len(TRANSMISSION_EDGES_SEED), "eras": len(POLICY_ERAS),
            "interactions": tuple(str(r["with"]) for r in INTERACTIONS),
            "no_lawful_ground": tuple(f"{r['jurisdiction']}:{r['layer']}"
                                      for r in NO_LAWFUL_GROUND)}


# --------------------------------------------------------------------------- assembly
_PACK_FIELDS: tuple[str, ...] = (
    "code", "name", "region_command", "currency", "executable_instruments", "central_bank",
    "fixing_conventions", "settlement_conventions", "exchanges", "holidays_rule",
    "fiscal_year_end", "positioning_sources", "native_languages", "terminology", "source_classes",
    "datasets", "actors", "domains", "custom_miners", "transmission_edges_seed", "policy_eras")


def as_dict() -> dict[str, Any]:
    """The pack as a plain mapping: the framework fields plus everything the framework has no slot
    for, carried beside them so nothing is silently dropped."""
    return {
        "code": CODE, "name": NAME, "region_command": REGION_COMMAND, "currency": CURRENCY,
        "currencies": CURRENCIES, "jurisdictions": JURISDICTIONS,
        "executable_instruments": EXECUTABLE_INSTRUMENTS, "central_bank": CENTRAL_BANK,
        "central_banks": CENTRAL_BANKS,
        "fixing_conventions": FIXING_CONVENTIONS,
        "settlement_conventions": SETTLEMENT_CONVENTIONS, "exchanges": EXCHANGES,
        "release_classes": RELEASE_CLASSES, "session_windows": SESSION_WINDOWS,
        "holidays_rule": HOLIDAYS_RULE, "fiscal_year_end": FISCAL_YEAR_END,
        "fiscal_year_ends": FISCAL_YEAR_ENDS,
        "positioning_sources": POSITIONING_SOURCES, "native_languages": NATIVE_LANGUAGES,
        "terminology": TERMINOLOGY, "source_classes": SOURCE_CLASSES,
        "source_layers": SOURCE_LAYERS, "layer_absences": LAYER_ABSENCES,
        "no_lawful_ground": NO_LAWFUL_GROUND, "query_territories": QUERY_TERRITORIES,
        "layer_terms": layer_terms(), "source_layer_coverage": source_layer_coverage(),
        "datasets": DATASETS, "actors": ACTORS, "domains": DOMAINS,
        "custom_miners": CUSTOM_MINERS, "miner_domains": MINER_DOMAINS,
        "transmission_edges_seed": TRANSMISSION_EDGES_SEED, "policy_eras": POLICY_ERAS,
        "transmission_targets": TRANSMISSION_TARGETS, "access_constraints": ACCESS_CONSTRAINTS,
        "interactions": INTERACTIONS, "cells": CELLS,
        "region_desk": REGION_DESK, "forest": FOREST, "cot_currency": COT_CURRENCY,
        "export_economy": EXPORT_ECONOMY, "retail_leverage_regime": RETAIL_LEVERAGE_REGIME,
        "institutional_flow_sources": INSTITUTIONAL_FLOW_SOURCES, "series": SERIES,
        "mission": MISSION, "cobalt_policy_events": COBALT_POLICY_EVENTS,
        "drought_events": DROUGHT_EVENTS, "export_routes": EXPORT_ROUTES,
        "zm_default_events": ZM_DEFAULT_EVENTS, "production_milestones": PRODUCTION_MILESTONES,
        "domain_jurisdiction": DOMAIN_JURISDICTION,
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
    """The framework's HolidayRule shape: every closed weekday the two calendars produce."""
    dates = sorted({d.isoformat() for y in HOLIDAYS_RULE["years"] for d in market_holidays(y)})
    fixed = sorted({f"{m:02d}-{d:02d}" for rows in (FIXED_CD, FIXED_ZM) for m, d, _ in rows})
    return {"dates": tuple(dates), "fixed_md": tuple(fixed), "weekly_closed": (5, 6),
            "notes": HOLIDAYS_RULE["authority"]}


def lab_kwargs() -> dict[str, Any]:
    """The keyword set `country_lab.CountryPack` is built from, in the shapes its coercion reads
    best: sources as rows AND as tagged lines, positioning and miners as strings, the holiday rule
    as dates, absent layers as a mapping."""
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
    """`country_lab.CountryPack` when the framework is present, else the mapping. Imported lazily
    so this department stays importable on a tree where the framework is not."""
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
