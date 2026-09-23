"""THE MEKONG FRONTIER: Myanmar, Cambodia and Laos -- three economies upstream of larger ones.

WHY THESE THREE ARE ONE PACK AND NOT THREE ROWS IN `th`. They share a river, a mid-April new
year, a Chinese creditor and a Thai buyer, and every one of their significant mechanisms
terminates in a neighbour's grid, a neighbour's factory or a neighbour's customs table. Held
separately they would each be a thin pack of absences; held together they are one measurable
plane whose defining property is that IT IS UPSTREAM, and upstream is where a shock is dated
first. Thailand, Vietnam and China own the downstream legs and this pack names them rather than
re-deriving any of them.

FIVE MECHANISMS, AND EVERY ONE IS PUBLISHED, DATED AND PHYSICAL.

  1. MYANMAR GAS IS THAI ELECTRICITY. The Yadana field (Blocks M5/M6) and the Zawtika field
     (Block M9) deliver gas by pipeline across the Thai border at Ban I Tong and Ban Phu Nam
     Ron, and that gas has for years been a material share of the fuel Thailand burns for power.
     The pipelines have ANNUAL MAINTENANCE SHUTDOWNS that are announced in advance, and the Thai
     system operator has publicly warned about reserve margin in those windows. A scheduled,
     dated, physical interruption to a neighbour's power fuel is exactly the kind of event a
     desk can align on, and the Thai industrial cycle is the transmission leg.

  2. KACHIN STATE IS THE WORLD'S HEAVY RARE EARTH MINE. Most of the world's dysprosium and
     terbium feedstock is dug in the Chipwi and Pangwa zone of northern Myanmar and trucked into
     Yunnan, where it is counted in CHINESE CUSTOMS DATA BY ORIGIN -- which is the only reliable
     measurement of it, because the Myanmar side publishes nothing. In 2024-2025 the Kachin
     Independence Army took that zone and the border closed, and the heavy rare-earth price
     complex moved. There is no substitute source at scale, which makes this one of the very few
     genuinely unsubstitutable supply chains on the desk's whole book.

  3. CAMBODIA IS A NATURAL EXPERIMENT ON WHAT A CURRENCY IS FOR. The economy is dollarised to
     the point that the riel circulates mainly as small change below one dollar, and the
     National Bank publishes both the dollarisation share and its own riel-promotion operations.
     So the desk can ask, on real data, what a floating currency actually buys a small open
     economy -- with Laos (a floating currency that collapsed) and Vietnam (a managed one that
     did not) as the two controls in the same region, the same decade and the same shocks.

  4. LAOS IS A BATTERY WITH A DEBT PROBLEM. Hydroelectricity is exported to Thailand, Vietnam
     and Cambodia under long-term power purchase agreements, and the output is bounded by Mekong
     flow that the Mekong River Commission publishes DAILY, BY STATION. At the same time Laos
     carries the region's heaviest debt burden, mostly Chinese, on a kip that lost more than half
     its value in 2022-2023 while published inflation ran above forty per cent. A live
     small-open-economy debt-and-currency stress case with a daily physical output constraint is
     not a thing that comes along often.

  5. FOUR ECONOMIES SHUT AT ONCE IN MID-APRIL. Thingyan, Chaul Chnam Thmey, Pi Mai and Thai
     Songkran fall in the SAME WEEK, so the whole northern-Mekong industrial and logistics plane
     stops together for roughly a week every April. That simultaneity is this pack's
     distinguishing calendar fact: it is not three separate closures that happen to be near each
     other, it is one regional stoppage, and the Thai leg of it belongs to the `th` pack.

WHAT IS EXECUTABLE AND WHAT IS NOT. MMK, KHR AND LAK ARE ALL ABSENT from
`data/universe/universe.json` -- three currencies, none quoted -- and all three are carried in
`TRANSMISSION_TARGETS` with their regimes, their parallel-market spreads and their routes.
Heavy rare earths, hydroelectric energy, garments, jade and milled rice have no broker contract
either; each is routed with the control named. There is no single-name equity anywhere in this
pack: the region's listed companies are a handful of illiquid domestic listings and a few Thai
and Singaporean parents, and under the two-lane order (2026-09-06) they are EVENT LANE ONLY.

THREE SCRIPTS AND A MEASURED VACUUM. Burmese, Khmer and Lao are three different writing systems
and an English-only crawl reads none of them. And where a layer genuinely does not exist -- the
Myanmar statistical system has largely stopped publishing since 2021, the Yangon exchange has
effectively no tape, Laos has no domestic academic economics ground, and none of the three has a
retail trading ecology -- the pack DECLARES IT per jurisdiction in `NO_LAWFUL_GROUND` and names
the lawful substitute: mirror customs, the Mekong River Commission, the ADB and IMF, and the
exile press. A measured refusal with a substitute beside it is worth more than a padded row.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime
from typing import Any

# --------------------------------------------------------------------------- identity
CODE = "MEKONG"
NAME = "The Mekong frontier (Myanmar, Cambodia, Laos)"
#: THE PARITY FENCE COUNTS THIS (`scripts/check_regional_parity.py::jurisdictions_of`). All three
#: are on the `asean` forest's roster in `libs/research/forests.py` and all three were UNANSWERED
#: before this pack: `th`, `vn`, `my`, `sg`, `ph` and `idn` carried the region and none of them
#: answers for a country whose statistics office has stopped publishing.
JURISDICTIONS: tuple[str, ...] = ("mm", "kh", "la")
#: THE FRAMEWORK'S CANONICAL TOKEN. This pack's own grouping is "southeast_asia", which
#: `country_lab.REGION_COMMAND_ALIASES` maps onto `asia`; the canonical token is written here so
#: the framework never has to coerce it and no coercion note is produced.
REGION_COMMAND = "asia"
REGION_DESK = "MEKONG"
FOREST = "asean"
#: The framework carries ONE currency field. All three are declared here so no jurisdiction is
#: silently represented by another's money -- and NONE of the three is quoted by the broker.
CURRENCIES: dict[str, str] = {"mm": "MMK", "kh": "KHR", "la": "LAK"}
CURRENCY = "MMK"
#: MYANMAR MOVED ITS FISCAL YEAR TO 1 APRIL - 31 MARCH; Cambodia and Laos run the calendar year.
#: The framework carries one field, so the primary jurisdiction's is declared and all three are
#: held beside it -- a pack that published one date for three treasuries would mis-time every
#: budget release in two of them.
FISCAL_YEAR_END = "03-31"
FISCAL_YEAR_ENDS: dict[str, str] = {"mm": "03-31", "kh": "12-31", "la": "12-31"}
#: SIX LANGUAGES AND THE PACK MEANS ALL SIX. Burmese, Khmer and Lao are the three domestic
#: grounds and are three different scripts. THAI is not decoration: the Thai power regulator,
#: the Thai customs tables and the Thai labour ministry are where two of these three economies
#: are measured from the outside. CHINESE is the mirror for the rare-earth and railway legs.
#: English reaches the IFI documents and the exile press and nothing else.
NATIVE_LANGUAGES: tuple[str, ...] = ("my", "km", "lo", "th", "zh", "en")
COT_CURRENCY = ""                  # no CFTC contract exists for any of the three currencies
EXPORT_ECONOMY = "commodity_exporter"   # gas, rare earths, hydro, rice, cassava, garments
RETAIL_LEVERAGE_REGIME = "UNMEASURED"   # none of the three has a retail trading ecology at all
MISSION = ("mine the Mekong frontier as the upstream plane it is: Myanmar gas into Thai power "
           "generation, the Kachin heavy rare-earth zone read through Chinese customs by "
           "origin, the two-rate kyat and its parallel-market spread, Cambodia's dollarisation "
           "as a natural experiment against Laos and Vietnam, Cambodian garment exports and the "
           "dated EU and US trade-policy events, Sihanoukville throughput, Laos as the region's "
           "battery bounded by daily Mekong station levels, the Lao debt-and-currency stress "
           "case, the Laos-China Railway as a dated freight step, and the mid-April week in "
           "which four economies shut at once")

#: The instruments this pack may compile a cell against. Every one is in the broker registry and
#: none is a single-name equity. MMK, KHR and LAK are all absent (see TRANSMISSION_TARGETS).
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "USDTHB",                                  # THE primary leg: gas, power, labour, crops
    "USDSGD", "USDIDR", "USDINR",              # the regional funding and rice-competitor legs
    "USDCNH",                                  # the creditor, the rare-earth buyer, the railway
    "USDJPY",                                  # the regional funding and ODA leg
    "XAUUSD",                                  # the store of value in three currency collapses
    "XNGUSD", "XBRUSD",                        # the gas and energy complex Myanmar feeds
    "CORN", "SUGAR", "COTTON", "SOYBEAN",      # the crops that actually cross these borders
    "XCUUSD", "XNIUSD",                        # the industrial-metals complex rare earths sit in
    "US500",                                   # the garment buyer's own risk complex
)

TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "MMK (the Myanmar kyat) -- a TWO-RATE regime, official and parallel",
     "venue": "the Central Bank of Myanmar's administered reference rate and the Yangon money "
              "changers' parallel market",
     "why": "THE DEFINING MONETARY FACT OF POST-2021 MYANMAR IS THAT THERE ARE TWO PRICES. The "
            "central bank administers a reference rate and has at times compelled conversion of "
            "foreign currency held in local accounts at it, while the market that people and "
            "importers actually transact in trades far weaker. The SPREAD between the two is "
            "the observable and it is a capital-control intensity measure, not a price. Neither "
            "rate is quoted by this broker, so every domestic mechanism is routed into USDTHB "
            "(the border trade and the migrant labour channel), USDCNH (the northern border and "
            "the rare-earth buyer) and XAUUSD (the store of value a collapsing kyat drives into)",
     "proxies": ("USDTHB", "USDCNH", "XAUUSD")},
    {"name": "KHR (the Cambodian riel) -- a currency that circulates as small change",
     "venue": "the National Bank of Cambodia's daily official rate and the dollarised banking "
              "system around it",
     "why": "CAMBODIA IS DOLLARISED TO THE POINT THAT THE RIEL IS MOSTLY USED BELOW ONE DOLLAR. "
            "The NBC publishes the dollarisation share and runs riel-promotion operations "
            "including the withdrawal of small-denomination US notes and the Bakong payment "
            "system, so the de-dollarisation effort is DATED AND PUBLISHED. The riel is not "
            "quoted here and barely needs to be: the executable legs are the dollar itself "
            "through USDSGD and USDTHB, the garment buyer's risk complex through US500, and the "
            "regional funding tone through USDJPY",
     "proxies": ("USDSGD", "USDTHB", "US500")},
    {"name": "LAK (the Lao kip) -- a float that lost more than half its value",
     "venue": "the Bank of the Lao PDR's reference rate, the commercial bank rate and the "
              "parallel market between them",
     "why": "A THREE-RATE ECONOMY IN PRACTICE AND A DEBT CRISIS IN SUBSTANCE. The kip more than "
            "halved against the dollar across 2022-2023, published inflation ran above forty "
            "per cent, and the external debt is dominated by Chinese lending against "
            "hydropower and railway assets. The kip is not quoted here, so the mechanism is "
            "routed into USDTHB (the electricity buyer and the import source), USDCNH (the "
            "creditor and the railway) and XAUUSD",
     "proxies": ("USDTHB", "USDCNH", "XAUUSD")},
    {"name": "Heavy rare earth feedstock (dysprosium, terbium) from Kachin State",
     "venue": "the Chipwi and Pangwa mining zone and the Yunnan border crossings into China",
     "why": "NO BROKER CONTRACT EXISTS FOR ANY RARE EARTH AND THE PACK SAYS SO. Most of the "
            "world's heavy rare-earth feedstock comes out of northern Myanmar and is separated "
            "in China, and the ONLY reliable public measurement is Chinese customs imports by "
            "origin, because the Myanmar side publishes nothing. The flow is routed through "
            "USDCNH and through the industrial-metals complex (XCUUSD, XNIUSD) with the control "
            "stated plainly: a rare-earth disruption that moves base metals the same way a "
            "general China-risk headline does is a risk event, not a supply event, and the "
            "customs tonnage is the test that separates them",
     "proxies": ("USDCNH", "XCUUSD", "XNIUSD")},
    {"name": "Myanmar pipeline gas delivered into the Thai power system",
     "venue": "the Yadana and Zawtika fields and the cross-border pipelines at Ban I Tong and "
              "Ban Phu Nam Ron",
     "why": "GAS DELIVERED BY PIPELINE UNDER LONG-TERM CONTRACT HAS NO TRADED PRICE HERE. The "
            "quantity is what matters and it is published by the Thai side, which is why the "
            "executable legs are USDTHB (the Thai industrial cycle that burns it) and XNGUSD "
            "and XBRUSD (the marginal alternative fuel Thailand must buy when the pipeline is "
            "down). The `th` pack owns the Thai power system and this pack reads it",
     "proxies": ("USDTHB", "XNGUSD", "XBRUSD")},
    {"name": "Lao hydroelectricity sold under long-term power purchase agreements",
     "venue": "the Lao independent power producers, EDL-T and the Thai, Vietnamese and "
              "Cambodian offtakers",
     "why": "A CONTRACTED, NON-TRADED EXPORT WHOSE VOLUME IS BOUNDED BY RAINFALL. The PPAs fix "
            "the price for decades, so the variable is the water, and the water is published "
            "daily by station by the Mekong River Commission. The executable leg is USDTHB, "
            "because Thailand is the largest offtaker and the payment is a real cross-border "
            "flow, with XNGUSD as the substitute-fuel control: when Lao hydro is short, the "
            "Thai system burns gas instead",
     "proxies": ("USDTHB", "XNGUSD", "USDCNH")},
    {"name": "Cambodian garments and footwear sold into the EU and the United States",
     "venue": "the Phnom Penh and Sihanoukville industrial zones and the EU and US customs "
              "regimes that price their access",
     "why": "THE SINGLE LARGEST EMPLOYER IN CAMBODIA AND IT HAS NO TRADED CONTRACT. What it has "
            "instead is a DATED TRADE-POLICY CALENDAR: the partial withdrawal of Everything But "
            "Arms preferences in 2020, the US tariff schedule, and monthly customs data on both "
            "sides. The executable legs are COTTON (the input fibre), US500 (the buyer's own "
            "demand and risk) and USDSGD (the regional trade-finance leg)",
     "proxies": ("COTTON", "US500", "USDSGD")},
    {"name": "Milled rice, cassava and maize crossing the Thai and Vietnamese borders",
     "venue": "the Myanmar Rice Federation's export licensing, the Cambodian and Lao border "
              "trade, and the Thai and Vietnamese processing chain",
     "why": "MYANMAR AND CAMBODIAN RICE ARE REAL EXPORTS WITH NO BROKER CONTRACT -- the broker "
            "quotes no rice at all. The mechanism is routed through the grains and softs the "
            "broker DOES quote (CORN, SOYBEAN, SUGAR) as the substitute-calorie and "
            "cross-crop-acreage complex, and through USDTHB and USDINR because Thailand and "
            "India are the competing exporters whose policy moves the same world price. The "
            "control is stated: a Mekong rice-policy event that moves CORN the same way a US "
            "balance-sheet revision does is a grains event and not a Mekong one",
     "proxies": ("CORN", "SOYBEAN", "SUGAR", "USDINR")},
    {"name": "Jade, gemstones and the informal border trade",
     "venue": "the Hpakant mines, the Mandalay and border markets, and the Chinese buyer",
     "why": "A LARGE, LARGELY UNRECORDED EXPORT. The official emporium receipts are a small "
            "fraction of the trade and most of it is invisible in any statistic, which is the "
            "measurement: this row exists so a miner treats the OFFICIAL jade series as a lower "
            "bound and never as the flow. The only executable reading is the Chinese consumer "
            "and risk complex through USDCNH",
     "proxies": ("USDCNH", "XAUUSD")},
    {"name": "The domestic exchanges: YSX, CSX and LSX",
     "venue": "the Yangon, Cambodia and Lao securities exchanges",
     "why": "THREE EXCHANGES WITH EFFECTIVELY NO TAPE BETWEEN THEM. Each lists a handful of "
            "companies; the Yangon exchange in particular has days with essentially no trade. "
            "There is no derivative, no short interest, no margin series and no index a foreign "
            "desk can reach. They are registered here so a miner reports UNMEASURED by name "
            "rather than discovering the absence as a silent failure, and the executable equity "
            "leg for the whole region is US500 -- the buyer's market, not the seller's",
     "proxies": ("US500", "USDSGD")},
)

# --------------------------------------------------------------------------- the central banks
CENTRAL_BANK: dict[str, Any] = {
    "name": "Central Bank of Myanmar (CBM)",
    "short": "CBM",
    "framework": "peg",
    "committee": "the CBM Board; monetary policy since 2021 is administrative rather than "
                 "deliberative and is announced by directive",
    "policy_instrument": "an ADMINISTERED REFERENCE RATE plus direct controls: export-earning "
                         "surrender and conversion requirements, import licensing tied to FX "
                         "allocation, and directives to banks and money changers. The interest "
                         "rate is not the instrument here and treating it as one would be a "
                         "category error",
    "mandate": "price and exchange-rate stability under the Central Bank of Myanmar Law; in "
               "practice the operative objective since 2021 has been the administrative "
               "allocation of scarce foreign exchange",
    "decision_rule": "directives are issued when the authorities decide, not on a calendar; the "
                     "2022 order compelling conversion of foreign currency in local accounts at "
                     "the administered rate is the archetype and it arrived without notice",
    "decision_calendar_rule": "THERE IS NO SCHEDULED POLICY DECISION TO DATE. A directive is an "
                              "administrative act with no announced calendar, so the generic "
                              "central-bank miner reporting UNMEASURED is the correct answer "
                              "(L1.28a). Typing a guessed calendar would stamp unscheduled "
                              "events to invented dates and manufacture a clean-looking null",
    "decision_dates": (),
    "dates_status": "EMPTY ON PURPOSE: directives are unscheduled by construction. The dated "
                    "ones this pack knows are in POLICY_ERAS, which is where an unscheduled "
                    "regime change belongs",
    "decision_time_utc": "",
    "announce_local": "directives are published in the state press and on the CBM site, in "
                      "Burmese first",
    "dst_rule": "Asia/Yangon is UTC+6:30 all year with no daylight saving -- a HALF-HOUR offset, "
                "which is the single most common conversion error made about this jurisdiction. "
                "Cambodia and Laos are both UTC+7 all year",
    "minutes_lag_days": 0,
    "publication_classes": ("ညွှန်ကြားချက်", "ငွေလဲလှယ်နှုန်း", "သတင်းထုတ်ပြန်ချက်",
                            "နှစ်ပတ်လည်အစီရင်ခံစာ"),
    "policy_rate_series": "CBM:reference_rate_mmk_usd",
    "expected_rate_series": "UNMEASURED",
    "consensus_proxy": "the PARALLEL MARKET RATE is the only forward-looking price this economy "
                       "produces, and it is quoted by money changers and on messaging channels "
                       "rather than by any institution",
    "consensus_proxy_trap": "an event study on the ADMINISTERED rate is measuring an "
                            "administrative decision and not a market; the two rates must never "
                            "be spliced into one series, and the SPREAD between them is the "
                            "only object here with information in it",
    "reserves_clock": "reserves have not been published on a reliable public schedule since "
                      "2021; the IMF and the partner-country mirror statistics are the "
                      "substitute and the pack says so rather than carrying a stale series",
    "programme": "no IMF programme; the country has been in arrears-adjacent standing with "
                 "several creditors since 2021 and the Article IV process has been disrupted",
    "off_cycle": (),
    "root": "https://www.cbm.gov.mm",
}

#: ALL THREE CENTRAL BANKS, because the framework carries one and this pack answers for three.
#: A miner steered at Cambodia that read the Myanmar row would be reading a peg where there is a
#: dollarised economy, which is not a small error.
CENTRAL_BANKS: tuple[dict[str, Any], ...] = (
    {"jurisdiction": "mm", "name": "Central Bank of Myanmar", "framework": "peg",
     "regime": "an administered reference rate with conversion and surrender requirements, and "
               "a parallel market that carries the real price",
     "observable": "the spread between the administered and parallel rates",
     "root": "https://www.cbm.gov.mm"},
    {"jurisdiction": "kh", "name": "National Bank of Cambodia (NBC)", "framework": "managed_float",
     "regime": "a managed riel inside a heavily dollarised system; the NBC's real instruments "
               "are the dollarisation share, the withdrawal of small US notes and the Bakong "
               "payment system rather than an interest rate",
     "observable": "the published dollarisation share of deposits and the daily official rate",
     "root": "https://www.nbc.gov.kh"},
    {"jurisdiction": "la", "name": "Bank of the Lao PDR (BOL)", "framework": "managed_float",
     "regime": "a reference rate with a permitted commercial-bank band and a parallel market "
               "outside it; the binding constraint is external debt service, not inflation "
               "targeting",
     "observable": "the reference rate, the commercial band and the parallel spread, against "
                   "published inflation that exceeded forty per cent in 2023",
     "root": "https://www.bol.gov.la"},
)

# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "Central Bank of Myanmar administered reference rate",
     "local": "published each business day in Yangon", "time_utc": "03:00",
     "dst_rule": "none (Asia/Yangon is UTC+6:30 all year -- a HALF-HOUR offset)",
     "instruments": ("USDTHB", "USDCNH"), "window_minutes": 120,
     "why": "an administered price, not a market one. It is carried because the SPREAD to the "
            "parallel market is the pack's capital-control intensity measure, and a spread "
            "needs both legs"},
    {"name": "The Yangon parallel-market kyat rate",
     "local": "quoted continuously by money changers and on messaging channels; the reference "
              "quote of the day settles in the late morning",
     "time_utc": "04:00", "dst_rule": "none", "instruments": ("USDTHB", "XAUUSD"),
     "window_minutes": 180,
     "why": "THE ONLY FORWARD-LOOKING PRICE THIS ECONOMY PRODUCES. It is not published by any "
            "institution, it is USER_SUBMITTED ground, and the pack labels it accordingly rather "
            "than promoting it to an official series"},
    {"name": "National Bank of Cambodia daily official KHR/USD rate",
     "local": "published each business day in Phnom Penh", "time_utc": "01:30",
     "dst_rule": "none (Asia/Phnom_Penh is UTC+7 all year)",
     "instruments": ("USDSGD", "USDTHB"), "window_minutes": 60,
     "why": "the reference for a currency that circulates mainly as small change; its stability "
            "is the point rather than its level, and the dollarisation share is the real series"},
    {"name": "Bank of the Lao PDR reference rate and the commercial-bank band",
     "local": "published each business day in Vientiane", "time_utc": "01:30",
     "dst_rule": "none (Asia/Vientiane is UTC+7 all year)",
     "instruments": ("USDTHB", "USDCNH"), "window_minutes": 60,
     "why": "a three-rate economy in practice; the reference, the permitted band and the "
            "parallel market are three different prices and the gaps between them are the "
            "measurement"},
    {"name": "Bank of Thailand daily reference rate (the downstream leg)",
     "local": "around midday Asia/Bangkok", "time_utc": "04:00", "dst_rule": "none",
     "instruments": ("USDTHB",), "window_minutes": 60,
     "why": "OWNED BY THE `th` PACK. Named here because Thailand is the buyer of Myanmar's gas, "
            "Laos's electricity and the region's migrant labour, so USDTHB is the leg almost "
            "every mechanism in this pack terminates in"},
    {"name": "PBoC CNY central parity (the creditor and rare-earth buyer leg)",
     "local": "09:15 Asia/Shanghai", "time_utc": "01:15", "dst_rule": "none",
     "instruments": ("USDCNH",), "window_minutes": 30,
     "why": "China is the rare-earth buyer, the railway builder, the largest creditor to Laos "
            "and the northern border counterparty for Myanmar; the parity prices all of it"},
    {"name": "Mekong River Commission daily station water-level reading",
     "local": "the morning gauge reading at Chiang Saen, Luang Prabang, Vientiane, Pakse and "
              "the downstream stations",
     "time_utc": "00:00", "dst_rule": "none",
     "instruments": ("USDTHB", "XNGUSD"), "window_minutes": 360,
     "why": "THE PHYSICAL BOUND ON LAOS'S ONLY REAL EXPORT, published daily and by station. A "
            "reservoir level is a supply constraint with a public daily reading, which almost "
            "nothing else in the energy complex has"},
    {"name": "CBOT grain settlement (the substitute-calorie complex)",
     "local": "13:20 America/Chicago", "time_utc": "19:20", "dst_rule": "CST/CDT",
     "instruments": ("CORN", "SOYBEAN", "SUGAR"), "window_minutes": 30,
     "why": "the broker quotes no rice at all, so the executable leg for every Mekong rice and "
            "cassava mechanism is the grains and softs complex, and this is where it settles"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "Chinese customs detailed imports by origin (rare earths from Myanmar)",
     "kind": "day_of_month", "days": (18, 19, 20, 21, 22, 23, 24, 25), "roll": "next",
     "window_utc": ("01:00", "04:00"), "instruments": ("USDCNH", "XCUUSD", "XNIUSD"),
     "why": "THE ONLY RELIABLE MEASUREMENT OF THE KACHIN FLOW, because the seller publishes "
            "nothing; the detailed by-origin tables arrive a few days after the headline"},
    {"name": "Cambodian customs monthly trade (GDCE)", "kind": "day_of_month",
     "days": (10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20), "roll": "next",
     "window_utc": ("01:00", "05:00"), "instruments": ("COTTON", "US500", "USDSGD"),
     "why": "garment and footwear exports by destination -- the cleanest monthly series any of "
            "the three jurisdictions publishes about itself"},
    {"name": "Mekong River Commission daily station levels", "kind": "weekday",
     "days": (1, 2, 3, 4, 5), "roll": "next", "window_utc": ("00:00", "06:00"),
     "instruments": ("USDTHB", "XNGUSD"),
     "why": "a daily physical reading, by station, of the constraint on Lao generation"},
    {"name": "Lao Statistics Bureau monthly CPI", "kind": "day_of_month",
     "days": (5, 6, 7, 8, 9, 10), "roll": "next", "window_utc": ("02:00", "06:00"),
     "instruments": ("USDTHB", "USDCNH"),
     "why": "the inflation series that ran above forty per cent in 2023 and is the most "
            "informative macro print the Lao state produces"},
    {"name": "Thai energy statistics: gas supply by source (EPPO and the system operator)",
     "kind": "day_of_month", "days": (20, 21, 22, 23, 24, 25, 26, 27, 28), "roll": "next",
     "window_utc": ("02:00", "08:00"), "instruments": ("USDTHB", "XNGUSD", "XBRUSD"),
     "why": "THE BUYER'S OWN COUNT OF MYANMAR GAS. Thailand publishes gas supply by source, "
            "which is how the Myanmar delivery volume is measured at all"},
    {"name": "The mid-April simultaneous new year block", "kind": "day_of_month",
     "days": (13, 14, 15, 16, 17), "roll": "next", "window_utc": ("00:00", "23:59"),
     "instruments": ("USDTHB", "COTTON", "USDSGD"),
     "why": "Thingyan, Chaul Chnam Thmey, Pi Mai and Thai Songkran fall in the same week, so "
            "four economies stop together; the factories, the ports and the border crossings all "
            "shut, which is one regional stoppage and not four coincidences"},
    {"name": "The Myanmar fiscal year (1 April - 31 March)", "kind": "fiscal_year_end",
     "days": (), "roll": "prior", "window_utc": ("02:00", "06:00"),
     "instruments": ("USDTHB", "USDCNH"),
     "why": "Myanmar moved its fiscal year; Cambodia and Laos run the calendar year, so the "
            "three budget calendars in this pack do not line up and FISCAL_YEAR_ENDS says so"},
)

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Yangon Stock Exchange (YSX)", "index_symbols": (),
     "open_local": "09:30", "close_local": "12:30", "open_utc": "03:00", "close_utc": "06:00",
     "dst_rule": "none (Asia/Yangon is UTC+6:30 all year)",
     "auction": "a short matching session; on many days there is effectively no trade at all",
     "expiry_rule": "NO LISTED DERIVATIVES AND EFFECTIVELY NO TAPE. There is no domestic expiry "
                    "clock and the generic expiry miner correctly reports UNMEASURED",
     "holidays": "the Myanmar public calendar, including the full Thingyan block",
     "notes": "A HANDFUL OF LISTINGS AND A TURNOVER THAT ROUNDS TO NOTHING. It is registered so "
              "a miner reports the absence by name rather than discovering it as a silent "
              "failure; it is never an executable venue and never a price source"},
    {"name": "Cambodia Securities Exchange (CSX)", "index_symbols": (),
     "open_local": "09:00", "close_local": "15:00", "open_utc": "02:00", "close_utc": "08:00",
     "dst_rule": "none (Asia/Phnom_Penh is UTC+7)",
     "auction": "opening and closing calls around a thin continuous session",
     "expiry_rule": "no listed derivatives; no domestic expiry clock",
     "holidays": "the Cambodian public calendar, including Chaul Chnam Thmey and Pchum Ben",
     "notes": "a real exchange with a real regulator, listing the port, the water utility and a "
              "few banks. Its value to this pack is as an INFORMATION venue about state asset "
              "policy -- the Sihanoukville port listing in particular -- and never as a price"},
    {"name": "Lao Securities Exchange (LSX)", "index_symbols": (),
     "open_local": "09:00", "close_local": "11:30", "open_utc": "02:00", "close_utc": "04:30",
     "dst_rule": "none (Asia/Vientiane is UTC+7)",
     "auction": "a short call-and-continuous session",
     "expiry_rule": "no listed derivatives; no domestic expiry clock",
     "holidays": "the Lao public calendar, including Pi Mai and Boun Ok Phansa",
     "notes": "roughly a dozen listings dominated by the state bank and the power utility. The "
              "power utility's disclosures are the one genuinely useful thing here, because "
              "they are the only domestic public window onto the PPA economics"},
    {"name": "The US exchanges as the venue where this region's demand actually trades",
     "index_symbols": ("US500",),
     "open_local": "09:30 America/New_York", "close_local": "16:00",
     "open_utc": "14:30", "close_utc": "21:00", "dst_rule": "EST/EDT",
     "auction": "opening and closing auctions",
     "expiry_rule": "the US index expiry cycle belongs to the `us` pack and is read here",
     "holidays": "the US calendar, which shares nothing with the Mekong one",
     "notes": "THE REGION'S EQUITY LEG IS THE BUYER'S MARKET, NOT THE SELLER'S. Cambodian "
              "garments are cut for American and European retailers, so the demand-side "
              "information that reaches a tradable price reaches it here"},
)

SESSION_WINDOWS: tuple[dict[str, Any], ...] = (
    {"name": "mekong_morning", "start_utc": "00:00", "end_utc": "03:00",
     "notes": "07:00-10:00 Indochina time: the border crossings open, the river gauges are read "
              "and the Lao and Cambodian official rates are posted"},
    {"name": "mekong_release", "start_utc": "01:00", "end_utc": "06:00",
     "notes": "the window the three statistics offices, the two functioning central banks and "
              "Chinese customs all publish inside"},
    {"name": "th_session", "start_utc": "02:30", "end_utc": "09:30",
     "notes": "the Thai session, where almost every mechanism in this pack terminates; it "
              "belongs to the `th` pack and is read here, never re-derived"},
    {"name": "cn_customs_window", "start_utc": "01:00", "end_utc": "04:00",
     "notes": "the Chinese release window in which the rare-earth-by-origin and railway freight "
              "numbers become public"},
    {"name": "us_demand_window", "start_utc": "13:30", "end_utc": "20:00",
     "notes": "the New York session in which the garment buyer's demand and the region's risk "
              "premium actually reprice; the only executable equity leg the pack has"},
)

RELEASE_CLASSES: tuple[dict[str, Any], ...] = (
    {"name": "Chinese customs rare-earth imports by origin (Myanmar)",
     "cadence": "monthly", "time_utc": "02:00", "source": "中华人民共和国海关总署",
     "actual_series": "CNCUSTOMS:rare_earth_imports_myanmar", "expected_series": "UNMEASURED",
     "notes": "THE ONLY RELIABLE MEASUREMENT OF THE KACHIN FLOW; the seller publishes nothing"},
    {"name": "Thai gas supply by source, including Myanmar pipeline deliveries",
     "cadence": "monthly", "time_utc": "04:00", "source": "EPPO / the Thai system operator",
     "actual_series": "TH:gas_supply_by_source", "expected_series": "UNMEASURED",
     "notes": "the buyer's own count of the Myanmar delivery; the annual pipeline maintenance "
              "shutdown is visible here as a dated volume hole"},
    {"name": "Cambodian customs monthly exports by product and destination",
     "cadence": "monthly", "time_utc": "03:00", "source": "GDCE (customs.gov.kh)",
     "actual_series": "KH:exports_by_destination", "expected_series": "UNMEASURED",
     "notes": "garments, footwear, milled rice and cassava; the cleanest self-published monthly "
              "series in the pack"},
    {"name": "National Bank of Cambodia dollarisation and monetary statistics",
     "cadence": "monthly and annual", "time_utc": "03:00", "source": "NBC",
     "actual_series": "KH:dollarisation_share", "expected_series": "n/a",
     "notes": "THE NATURAL EXPERIMENT'S OWN SERIES: the share of deposits and circulation in US "
              "dollars, published by the institution trying to reduce it"},
    {"name": "Lao Statistics Bureau consumer price index",
     "cadence": "monthly", "time_utc": "04:00", "source": "LSB (lsb.gov.la)",
     "actual_series": "LA:cpi", "expected_series": "UNMEASURED",
     "notes": "the series that exceeded forty per cent year-on-year in 2023; the most "
              "informative macro print the Lao state produces"},
    {"name": "Bank of the Lao PDR reference rate and the commercial-bank band",
     "cadence": "daily", "time_utc": "01:30", "source": "BOL",
     "actual_series": "LA:reference_rate", "expected_series": "n/a",
     "notes": "read WITH the parallel rate: the gap between the three prices is the measurement"},
    {"name": "Mekong River Commission daily water levels by station",
     "cadence": "daily", "time_utc": "00:00", "source": "Mekong River Commission",
     "actual_series": "MRC:station_levels", "expected_series": "n/a",
     "notes": "Chiang Saen, Luang Prabang, Vientiane, Pakse and the downstream stations; the "
              "physical bound on Lao generation, published daily"},
    {"name": "Lao Ministry of Finance debt bulletin and the external amortisation schedule",
     "cadence": "annual with irregular updates", "time_utc": "UNMEASURED", "source": "Lao MoF",
     "actual_series": "LA:external_debt_schedule", "expected_series": "n/a",
     "notes": "the most debt-distressed schedule in the region, dominated by Chinese lending; "
              "the deferrals are dated events and the World Bank's debt statistics are the "
              "independent check"},
    {"name": "Myanmar official statistics (CSO) -- LARGELY SUSPENDED",
     "cadence": "irregular since 2021", "time_utc": "UNMEASURED",
     "source": "Central Statistical Organization", "actual_series": "MM:cso_series",
     "expected_series": "n/a",
     "notes": "DECLARED BROKEN RATHER THAN CARRIED AS IF IT WERE LIVE. Publication has been "
              "irregular or absent since 2021; the lawful substitutes are the partner-country "
              "mirror statistics, the IMF and ADB estimates and UN Comtrade"},
    {"name": "Myanmar Rice Federation export policy and volume announcements",
     "cadence": "irregular, announced", "time_utc": "UNMEASURED",
     "source": "Myanmar Rice Federation", "actual_series": "MM:rice_export_policy",
     "expected_series": "n/a",
     "notes": "licensing, reference prices and periodic restrictions; a policy act about supply "
              "and never a clearing price"},
    {"name": "Laos-China Railway freight and passenger volumes",
     "cadence": "monthly and milestone announcements", "time_utc": "02:00",
     "source": "the railway operator and Chinese state media",
     "actual_series": "LA:railway_freight_tonnes", "expected_series": "n/a",
     "notes": "a DATED STEP CHANGE in regional freight from December 2021; announcements come "
              "from the Chinese side first and are the faster ground"},
    {"name": "Sihanoukville Autonomous Port throughput",
     "cadence": "monthly and quarterly", "time_utc": "03:00", "source": "PAS, listed on the CSX",
     "actual_series": "KH:port_teu", "expected_series": "UNMEASURED",
     "notes": "a container count published by a listed state port -- the physical counterpart of "
              "the garment export series, and a rare case where a disclosure obligation makes a "
              "Mekong physical series reliable"},
)

# --------------------------------------------------------------------------- holidays
#: THE SOLAR HALF -- statutory public holidays across the three jurisdictions that recur on the
#: same date every year and are therefore COMPUTED rather than typed. The names carry the
#: jurisdiction tags, because a single union table for three countries that did not say which
#: country each day belongs to would be useless to a miner steered at one of them.
#:
#: 13-17 APRIL IS THE PACK'S DISTINGUISHING CALENDAR FACT: Thingyan, Chaul Chnam Thmey and Pi Mai
#: all fall in the same week, and so does Thai Songkran next door -- four economies stopping
#: together, which is ONE REGIONAL STOPPAGE and not four coincidences.
FIXED_GENERAL: tuple[tuple[int, int, str], ...] = (
    (1, 1, "[kh|la] International New Year's Day"),
    (1, 4, "[mm] Independence Day"),
    (1, 7, "[kh] Victory over Genocide Day"),
    (2, 12, "[mm] Union Day"),
    (3, 2, "[mm] Peasants' Day"),
    (3, 8, "[kh|la] International Women's Day"),
    (3, 27, "[mm] Armed Forces Day"),
    (4, 13, "[mm] Thingyan (သင်္ကြန်) day 1 -- THE SIMULTANEOUS WEEK OPENS"),
    (4, 14, "[mm|kh|la] Thingyan / Chaul Chnam Thmey (ចូលឆ្នាំថ្មី) / Pi Mai (ປີໃໝ່ລາວ) day 1"),
    (4, 15, "[mm|kh|la] Thingyan / Chaul Chnam Thmey / Pi Mai day 2"),
    (4, 16, "[mm|kh|la] Thingyan / Chaul Chnam Thmey / Pi Mai day 3"),
    (4, 17, "[mm] Myanmar New Year's Day -- the simultaneous week closes"),
    (5, 1, "[mm|kh|la] Labour Day"),
    (5, 14, "[kh] Birthday of King Norodom Sihamoni"),
    (6, 18, "[kh] Birthday of the Queen Mother"),
    (7, 19, "[mm] Martyrs' Day"),
    (9, 24, "[kh] Constitution Day"),
    (10, 15, "[kh] Commemoration Day of King Father Norodom Sihanouk"),
    (10, 29, "[kh] King's Coronation Day"),
    (11, 9, "[kh] Cambodian Independence Day"),
    (12, 2, "[la] Lao National Day"),
    (12, 25, "[mm] Christmas Day"),
    (12, 31, "[mm] New Year's Eve"),
)

#: THE LUNISOLAR HALF -- three Theravada Buddhist calendars that no weekday rule produces. The
#: Burmese, Khmer and Lao calendars share the same full moons for most of the year, which is why
#: several rows below close ALL THREE countries on one date, and that coincidence is itself the
#: measurement: a regional stoppage is a different object from a national one.
#:
#: Rows are (date, name, status). NOTIFIED is reserved for a row this desk has actually read in
#: the relevant government's annual holiday notification; TYPED is the date this pack holds from
#: the lunisolar calendar with the authority named and the notification NOT yet crawled;
#: PROJECTED is a forward computation. No row below claims NOTIFIED, and that is a measurement
#: rather than an omission -- the crawler has not reached the three gazettes yet (L1.28a).
LUNISOLAR: dict[int, tuple[tuple[date, str, str], ...]] = {
    2024: ((date(2024, 2, 24), "[kh|la] Meak Bochea / Makha Bousa (full moon)", "TYPED"),
           (date(2024, 3, 24), "[mm] Full Moon Day of Tabaung", "TYPED"),
           (date(2024, 5, 22),
            "[mm|kh|la] Kason full moon / Visak Bochea / Visakha Bousa -- ONE FULL MOON, "
            "THREE COUNTRIES CLOSED", "TYPED"),
           (date(2024, 5, 26), "[kh] Royal Ploughing Ceremony", "TYPED"),
           (date(2024, 7, 20),
            "[mm|la] Waso full moon / Boun Khao Phansa (start of Buddhist Lent)", "TYPED"),
           (date(2024, 10, 1), "[kh] Pchum Ben (ភ្ជុំបិណ្ឌ) day 1", "TYPED"),
           (date(2024, 10, 2), "[kh] Pchum Ben day 2", "TYPED"),
           (date(2024, 10, 3), "[kh] Pchum Ben day 3", "TYPED"),
           (date(2024, 10, 17),
            "[mm|la] Thadingyut / Boun Ok Phansa (ບຸນອອກພັນສາ, end of Lent)", "TYPED"),
           (date(2024, 11, 14), "[kh] Water Festival (Bon Om Touk) day 1", "TYPED"),
           (date(2024, 11, 15),
            "[mm|kh|la] Tazaungdaing / Water Festival day 2 / Boun That Luang", "TYPED"),
           (date(2024, 11, 16), "[kh] Water Festival day 3", "TYPED")),
    2025: ((date(2025, 2, 12), "[kh|la] Meak Bochea / Makha Bousa (full moon)", "TYPED"),
           (date(2025, 3, 13), "[mm] Full Moon Day of Tabaung", "TYPED"),
           (date(2025, 5, 11),
            "[mm|kh|la] Kason full moon / Visak Bochea / Visakha Bousa -- ONE FULL MOON, "
            "THREE COUNTRIES CLOSED", "TYPED"),
           (date(2025, 5, 13), "[kh] Royal Ploughing Ceremony", "TYPED"),
           (date(2025, 7, 10),
            "[mm|la] Waso full moon / Boun Khao Phansa (start of Buddhist Lent)", "TYPED"),
           (date(2025, 9, 21), "[kh] Pchum Ben day 1", "TYPED"),
           (date(2025, 9, 22), "[kh] Pchum Ben day 2", "TYPED"),
           (date(2025, 9, 23), "[kh] Pchum Ben day 3", "TYPED"),
           (date(2025, 10, 7), "[mm|la] Thadingyut / Boun Ok Phansa (end of Lent)", "TYPED"),
           (date(2025, 11, 4), "[kh] Water Festival (Bon Om Touk) day 1", "TYPED"),
           (date(2025, 11, 5),
            "[mm|kh|la] Tazaungdaing / Water Festival day 2 / Boun That Luang", "TYPED"),
           (date(2025, 11, 6), "[kh] Water Festival day 3", "TYPED")),
    2026: ((date(2026, 3, 3), "[kh|la] Meak Bochea / Makha Bousa (full moon)", "PROJECTED"),
           (date(2026, 3, 4), "[mm] Full Moon Day of Tabaung", "PROJECTED"),
           (date(2026, 5, 1),
            "[mm|kh|la] Kason full moon / Visak Bochea / Visakha Bousa -- ONE FULL MOON, "
            "THREE COUNTRIES CLOSED", "PROJECTED"),
           (date(2026, 5, 5), "[kh] Royal Ploughing Ceremony", "PROJECTED"),
           (date(2026, 6, 29),
            "[mm|la] Waso full moon / Boun Khao Phansa (start of Buddhist Lent)", "PROJECTED"),
           (date(2026, 10, 10), "[kh] Pchum Ben day 1", "PROJECTED"),
           (date(2026, 10, 11), "[kh] Pchum Ben day 2", "PROJECTED"),
           (date(2026, 10, 12), "[kh] Pchum Ben day 3", "PROJECTED"),
           (date(2026, 10, 26), "[mm|la] Thadingyut / Boun Ok Phansa (end of Lent)", "PROJECTED"),
           (date(2026, 11, 23), "[kh] Water Festival (Bon Om Touk) day 1", "PROJECTED"),
           (date(2026, 11, 24),
            "[mm|kh|la] Tazaungdaing / Water Festival day 2 / Boun That Luang", "PROJECTED"),
           (date(2026, 11, 25), "[kh] Water Festival day 3", "PROJECTED")),
}

#: One-off closures and dated clock facts that no recurring rule produces.
DECLARED_CLOSURES: dict[date, str] = {
    date(2024, 4, 15): "the 2024 simultaneous week: Thingyan, Chaul Chnam Thmey, Pi Mai AND "
                       "Thai Songkran all inside 13-17 April, so the Thai border crossings, the "
                       "Cambodian garment factories and the Lao logistics chain stopped together",
    date(2025, 4, 15): "the 2025 simultaneous week; the same four-economy stoppage, which is "
                       "why this pack treats mid-April as ONE regional event and not four",
    date(2026, 4, 15): "the 2026 simultaneous week, computed from the fixed statutory dates",
}

#: THE STATUS LABELS. NOTIFIED is reserved for a row read in the relevant government's annual
#: holiday notification; TYPED is this pack's own lunisolar date with the authority named and
#: the notification not yet crawled; PROJECTED is a forward computation. A cell compiled on a
#: TYPED or PROJECTED row is a hypothesis, never a promotion.
HOLIDAY_STATUSES: tuple[str, ...] = ("NOTIFIED", "TYPED", "PROJECTED")

#: WHICH JURISDICTIONS A CLOSURE ROW BELONGS TO, parsed from the row's own name tag. A union
#: table for three countries is only usable if each row says whose day it is.
_JURISDICTION_TAGS: tuple[str, ...] = ("mm", "kh", "la")


def jurisdictions_closed(name: str) -> tuple[str, ...]:
    """The jurisdictions a holiday row belongs to, read from its `[mm|kh|la]` tag.

    A miner steered at Cambodia must not treat a Burmese Martyrs' Day as a Cambodian closure,
    and a regional-stoppage study must be able to count HOW MANY of the three stopped on a day.
    Both need the tag, so the tag is parsed rather than assumed.
    """
    head = str(name).split("]", 1)[0].lstrip("[") if str(name).startswith("[") else ""
    got = tuple(t for t in _JURISDICTION_TAGS if t in head.split("|"))
    return got or ()


def national_holidays(year: int) -> dict[date, str]:
    """Every statutory closure in any of the three jurisdictions for a year: the fixed solar
    dates, the typed or projected lunisolar dates, and the one-off declarations.

    THIS IS A UNION AND IT SAYS SO. A date in this table is a day on which AT LEAST ONE of the
    three countries is shut, and the row's own tag says which; `jurisdictions_closed` reads it
    back. A caller that wants one country's calendar filters on the tag, and a caller that wants
    the regional stoppage counts the tags -- both are honest and neither is the default.
    """
    out: dict[str, str] = {}
    for m, d, name in FIXED_GENERAL:
        out[date(year, m, d).isoformat()] = name
    for day, name, status in LUNISOLAR.get(year, ()):
        iso = day.isoformat()
        prior = out.get(iso)
        row = f"{name} [{status}]"
        out[iso] = f"{prior} -- {row}" if prior else row
    for day, name in DECLARED_CLOSURES.items():
        # APPENDED, NEVER OVERWRITTEN: a one-off note about a day the recurring rules already
        # produce is extra information about that closure, and replacing the name would delete
        # the festival a study is trying to align on.
        if day.year == year:
            prior = out.get(day.isoformat())
            out[day.isoformat()] = f"{prior} -- {name}" if prior else name
    return {date.fromisoformat(k): v for k, v in sorted(out.items())}


def market_holidays(year: int) -> dict[date, str]:
    """The closures that cost a WEEKDAY. A weekend closure costs no factory shift and no customs
    session and must not enter a liquidity or throughput sample as if it did."""
    return {d: n for d, n in national_holidays(year).items() if d.weekday() < 5}


def is_market_holiday(day: date) -> bool:
    return day in market_holidays(day.year)


def holidays_for(jurisdiction: str, year: int) -> dict[date, str]:
    """One jurisdiction's own closures for a year, filtered out of the union table by tag."""
    key = str(jurisdiction).strip().lower()
    return {d: n for d, n in national_holidays(year).items()
            if key in jurisdictions_closed(n) or key in str(n)}


def typed_dates(year: int) -> dict[date, str]:
    """Only the lunisolar rows this pack has TYPED from the calendar (as opposed to projected).
    A study that pools PROJECTED rows into a typed sample must say so."""
    return {d: n for d, n, st in LUNISOLAR.get(year, ()) if st == "TYPED"}


def new_year_week(year: int) -> dict[str, Any]:
    """THE PACK'S DISTINGUISHING CALENDAR MEASUREMENT: the mid-April week in which Myanmar,
    Cambodia and Laos all stop -- and Thailand next door with them.

    Thingyan, Chaul Chnam Thmey, Pi Mai and Thai Songkran are four different festivals on three
    different calendars that all land on 13-17 April, because all four are anchored to the same
    solar new year of the old Indic calendar rather than to a lunar month. That makes them
    LARGELY FIXED and therefore derivable, which is why they are computed here and not typed --
    and it makes the resulting stoppage REGIONAL rather than national, which is the whole point:
    the factories, the ports, the border crossings and the power demand of four economies fall
    together, and a study that models one of them alone is modelling a quarter of the event.
    """
    days = [date(year, 4, d) for d in (13, 14, 15, 16, 17)]
    table = national_holidays(year)
    rows = []
    for day in days:
        name = table.get(day, "")
        closed = jurisdictions_closed(name)
        rows.append({"date": day.isoformat(), "name": name,
                     "jurisdictions_closed": closed, "n_closed": len(closed),
                     "weekday": day.weekday(), "costs_a_session": day.weekday() < 5})
    return {"year": year, "window": (days[0].isoformat(), days[-1].isoformat()),
            "days": tuple(rows),
            "max_simultaneous": max((int(r["n_closed"]) for r in rows), default=0),
            "weekday_sessions_lost": sum(1 for r in rows if r["costs_a_session"]),
            "thai_songkran": "13-15 April, owned by the `th` pack and read here -- the fourth "
                             "economy in the same window",
            "why": "ONE REGIONAL STOPPAGE, NOT FOUR COINCIDENCES; a single-country closure study "
                   "on this window is measuring a quarter of the event"}


HOLIDAYS_RULE: dict[str, Any] = {
    "kind": "computed_solar_union_plus_typed_theravada_lunisolar_table",
    "authority": "each jurisdiction's own annual public-holiday notification: the Myanmar "
                 "Presidential Office / Union Government notification and the Myanmar Gazette; "
                 "the Cambodian Royal Government sub-decree published each year; and the Lao "
                 "Prime Minister's Office notice. The lunisolar dates are fixed in those "
                 "notifications from the Theravada Buddhist calendar and are typed here with "
                 "their status, because no weekday rule produces them",
    "rule": "TWO GENERATORS ACROSS THREE COUNTRIES. (1) TWENTY-THREE FIXED SOLAR DAYS computed "
            "from the three statutes, tagged by jurisdiction, including the MID-APRIL BLOCK: "
            "Thingyan 13-17 April in Myanmar, Chaul Chnam Thmey 14-16 April in Cambodia and Pi "
            "Mai 14-16 April in Laos. Those four festivals -- Thai Songkran is the fourth -- are "
            "anchored to the same Indic solar new year rather than to a lunar month, which is "
            "why they are LARGELY FIXED and are therefore DERIVED rather than typed. "
            "(2) TWELVE THERAVADA LUNISOLAR DAYS a year that no weekday rule produces and that "
            "are TYPED with their status: Meak Bochea / Makha Bousa, the Tabaung full moon, the "
            "Kason / Visak / Visakha full moon, the Royal Ploughing Ceremony, Waso / Khao "
            "Phansa, Pchum Ben, Thadingyut / Ok Phansa, Tazaungdaing / That Luang and the "
            "Cambodian Water Festival. SEVERAL OF THESE ARE ONE FULL MOON CLOSING ALL THREE "
            "COUNTRIES, and the table combines those rows rather than letting one overwrite "
            "another. THE TABLE IS A UNION: a date in it is a day at least one of the three is "
            "shut, and every row carries an [mm|kh|la] tag that `jurisdictions_closed` reads "
            "back. THE CLOCKS DIFFER: Asia/Yangon is UTC+6:30 -- a HALF-HOUR offset and the "
            "commonest conversion error about this jurisdiction -- while Phnom Penh and "
            "Vientiane are UTC+7; none of the three observes daylight saving.",
    "years": (2024, 2025, 2026),
    "weekend": "Saturday and Sunday",
    "national_rule": "see `rule`; `national_holidays(year)` is the computed union and "
                     "`holidays_for(jurisdiction, year)` is one country's own",
    "market_rule": "there is effectively no domestic securities session to close in any of the "
                   "three, so the calendar's market meaning is the FACTORY SHIFT, the CUSTOMS "
                   "SESSION and the BORDER CROSSING, not an exchange -- which is why "
                   "`market_holidays` filters weekdays and a weekend closure is discarded",
    "lunisolar_rule": "TYPED, not inferred, and NOT NOTIFIED either: the three governments' "
                      "annual notifications are the authority and this desk's crawler has not "
                      "reached them, so every lunisolar row carries TYPED or PROJECTED and none "
                      "claims NOTIFIED. That is a measurement of the desk's own coverage",
    "simultaneity": "the distinguishing calendar fact of this jurisdiction group: FOUR economies "
                    "shut in the same mid-April week, and several Theravada full moons close all "
                    "three of this pack's countries on one date -- a regional stoppage that a "
                    "single-country holiday study cannot see",
    "table": {y: {d.isoformat(): n for d, n in national_holidays(y).items()}
              for y in (2024, 2025, 2026)},
    "status": {2024: "TYPED for every lunisolar row; the fixed solar rows are computed",
               2025: "TYPED for every lunisolar row; the fixed solar rows are computed",
               2026: "PROJECTED for every lunisolar row until the three notifications are read"},
    "known_dates": {
        "2024-05-22": "ONE FULL MOON, THREE COUNTRIES CLOSED -- Kason, Visak Bochea and "
                      "Visakha Bousa on the same date",
        "2025-04-15": "the simultaneous week: Myanmar, Cambodia, Laos and Thailand together",
        "2025-11-05": "Tazaungdaing, the Cambodian Water Festival and Boun That Luang on one day",
        "2026-04-14": "the 2026 simultaneous week, computed from the fixed statutory dates",
    },
    "fn": market_holidays,
    "national_fn": national_holidays,
    "typed_fn": typed_dates,
    "jurisdiction_fn": holidays_for,
    "new_year_fn": new_year_week,
}

# ------------------------------------------------- the two-rate regimes, as arithmetic
#: THE PARALLEL-SPREAD BUCKETS. A gap between an administered rate and the rate people actually
#: transact at is a CAPITAL-CONTROL INTENSITY MEASURE, not a price. Two of this pack's three
#: currencies have run wide spreads in the last five years and the third is dollarised, which is
#: the same question answered a different way.
SPREAD_BUCKETS: tuple[tuple[float, float, str], ...] = (
    (0.0, 0.05, "EFFECTIVELY_UNIFIED"),
    (0.05, 0.20, "MILD_RATIONING"),
    (0.20, 0.60, "WIDE_RATIONING"),
    (0.60, 100.0, "REGIME_STRESS"),
)


def parallel_spread(official: float, parallel: float) -> dict[str, Any]:
    """THE TWO-RATE MEASUREMENT. Given an administered rate and a parallel-market rate in the
    same units (local currency per US dollar), the proportional gap and the rationing bucket.

    This function exists because the single commonest error in a two-rate economy is to SPLICE
    the two series into one and study the result. They are not one price at different times;
    they are two different objects that coexist, and the informative variable is the distance
    between them. A spread that widens is the state rationing harder, whatever the level does.
    """
    o = float(official)
    p = float(parallel)
    if o <= 0.0 or p <= 0.0:
        return {"official": o, "parallel": p, "spread": None, "bucket": "UNMEASURED",
                "why": "a non-positive rate is not a quote; UNMEASURED rather than a zero"}
    spread = (p - o) / o
    bucket = "UNCLASSIFIED"
    for lo, hi, label in SPREAD_BUCKETS:
        if lo <= abs(spread) < hi:
            bucket = label
            break
    return {"official": o, "parallel": p, "spread": round(spread, 6),
            "spread_pct": round(spread * 100.0, 3), "bucket": bucket,
            "control": "the same bucket measured in a neighbouring floating economy with no "
                       "administered rate, which is what separates 'the currency fell' from "
                       "'the state rationed'",
            "why": "the two rates are two objects that coexist and must never be spliced into "
                   "one series; the GAP is the capital-control intensity measure"}


#: HYDRO OUTPUT BOUNDS as a fraction of the seasonal median flow at a station. Expressed as a
#: RATIO rather than in metres on purpose: a metre reading means nothing without that station's
#: own datum and rating curve, and this pack holds neither, so a dimensionless ratio against the
#: station's own seasonal median is the honest form of the constraint.
HYDRO_BUCKETS: tuple[tuple[float, float, str], ...] = (
    (0.0, 0.55, "SEVERE_DROUGHT"),
    (0.55, 0.80, "BELOW_MEDIAN"),
    (0.80, 1.20, "NORMAL"),
    (1.20, 1.60, "ABOVE_MEDIAN"),
    (1.60, 100.0, "FLOOD"),
)


def hydro_bound(level_ratio: float, station: str = "Vientiane") -> dict[str, Any]:
    """The Lao generation constraint implied by a Mekong station level, as a bucket.

    `level_ratio` is the station's reading as a FRACTION OF ITS OWN SEASONAL MEDIAN, which is
    the only form in which a river gauge is comparable across stations and across months. The
    output claim is deliberately one-sided: low water bounds generation from above, high water
    does not raise a contracted PPA volume beyond plant capacity, so the drought buckets carry
    information about export revenue and the flood buckets mostly carry spill.
    """
    r = max(0.0, float(level_ratio))
    bucket = "UNCLASSIFIED"
    for lo, hi, label in HYDRO_BUCKETS:
        if lo <= r < hi:
            bucket = label
            break
    binds = bucket in ("SEVERE_DROUGHT", "BELOW_MEDIAN")
    return {"station": str(station), "level_ratio": r, "bucket": bucket,
            "binds_generation": binds,
            "asymmetry": "low water bounds output from above; high water does not raise a "
                         "contracted PPA volume beyond plant capacity, so the two tails carry "
                         "different information and must not be modelled symmetrically",
            "control": "the Thai system's own gas burn over the same weeks, because when Lao "
                       "hydro is short Thailand substitutes gas -- that substitution is the "
                       "transmission and XNGUSD is where it lands",
            "why": "a daily, public, station-level physical bound on a country's only real "
                   "export is a rarity, and the ratio form is what makes it comparable"}


#: CAMBODIA'S DOLLARISATION BUCKETS, as the share of broad money or deposits held in US dollars.
DOLLARISATION_BUCKETS: tuple[tuple[float, float, str], ...] = (
    (0.0, 0.30, "MOSTLY_LOCAL"),
    (0.30, 0.60, "PARTIALLY_DOLLARISED"),
    (0.60, 0.85, "HEAVILY_DOLLARISED"),
    (0.85, 1.01, "EFFECTIVELY_DOLLARISED"),
)


def dollarisation_state(share: float) -> dict[str, Any]:
    """Cambodia's dollarisation bucket, and what it implies about which policy tools exist.

    THE POINT IS THE NATURAL EXPERIMENT. At the top bucket the central bank has no meaningful
    independent monetary policy and no exchange-rate channel, so Cambodia answers the question
    "what does a national currency actually buy a small open economy?" against two neighbours
    that kept theirs -- Laos, whose float collapsed, and Vietnam, whose managed rate did not.
    """
    s = float(share)
    if not 0.0 <= s <= 1.0:
        return {"share": s, "bucket": "UNMEASURED",
                "why": "a share outside [0,1] is not a measurement"}
    bucket = "UNCLASSIFIED"
    for lo, hi, label in DOLLARISATION_BUCKETS:
        if lo <= s < hi:
            bucket = label
            break
    return {"share": round(s, 4), "bucket": bucket,
            "policy_tools": ("no independent interest-rate channel", "no exchange-rate channel",
                             "reserve requirements by currency", "payment-system promotion"),
            "controls": ("la -- a float that lost more than half its value in 2022-2023",
                         "vn -- a managed rate over the same shocks that did not"),
            "why": "the cleanest available natural experiment on what a floating currency buys "
                   "a small open economy, with two same-region controls over the same decade"}


# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "National Bank of Cambodia monetary statistics and the dollarisation share",
     "root": "https://www.nbc.gov.kh/english/economic_research/statistics.php",
     "fields": ("deposits_usd_share", "deposits_khr", "riel_in_circulation", "official_rate",
                "reserves_usd", "bakong_volume"),
     "frequency": "monthly and annual", "snapshot": "month end", "publish_utc": "03:00",
     "lag_days": 45, "licence": "free, public", "available": True,
     "why": "THE NATURAL EXPERIMENT'S OWN SERIES, published by the institution trying to change "
            "it. The dollarisation share is the closest thing any of these three economies has "
            "to a positioning series: it is the private sector's standing vote on the currency",
     "pit_warning": "about six weeks late and month-end stamped; it conditions a quarter and "
                    "never a week"},
    {"name": "Bank of the Lao PDR reference rate, commercial band and the parallel quote",
     "root": "https://www.bol.gov.la/en/exchangeRate",
     "fields": ("reference_rate", "commercial_band_high", "commercial_band_low",
                "parallel_quote", "reserves_usd"),
     "frequency": "daily for the rates, irregular for reserves", "snapshot": "business day",
     "publish_utc": "01:30", "lag_days": 0, "licence": "free, public", "available": True,
     "why": "THREE PRICES FOR ONE CURRENCY. The reference, the permitted commercial band and "
            "the parallel quote diverged sharply through 2022-2023, and the gaps between them "
            "are the rationing measure `parallel_spread` computes",
     "pit_warning": "the reference archive is overwritten in place and the parallel quote is "
                    "not published by anyone at all -- it is USER_SUBMITTED ground"},
    {"name": "Chinese customs imports by origin (rare earths, and the general mirror)",
     "root": "http://stats.customs.gov.cn/",
     "fields": ("hs_code", "origin_country", "quantity", "value", "month"),
     "frequency": "monthly", "snapshot": "calendar month", "publish_utc": "02:00",
     "lag_days": 22, "licence": "free, public", "available": True,
     "why": "THE BUYER'S BOOKS ARE THE ONLY BOOKS. For the Kachin rare-earth flow and for much "
            "of the northern Myanmar border trade this is not a cross-check, it is the primary "
            "measurement, because the seller's statistical system has stopped publishing",
     "pit_warning": "the detailed by-origin tables arrive days after the headline and are "
                    "occasionally restated in the annual yearbook"},
    {"name": "a CFTC, exchange or dealer positioning series for MMK, KHR or LAK",
     "root": "", "fields": (), "frequency": "n/a", "snapshot": "", "publish_utc": "",
     "lag_days": 0, "licence": "", "available": False,
     "why": "DECLARED ABSENT FOR ALL THREE: no future, forward or option on any of these "
            "currencies trades on an exchange the desk can read, and no COT contract exists",
     "pit_warning": "DOES NOT EXIST: positioning in all three currencies is UNMEASURED and is "
                    "never proxied by USDTHB or USDCNH, which are positions in the currencies "
                    "of the NEIGHBOURS these economies transmit through"},
    {"name": "a domestic equity, derivatives or retail-margin series in any of the three",
     "root": "", "fields": (), "frequency": "n/a", "snapshot": "", "publish_utc": "",
     "lag_days": 0, "licence": "", "available": False,
     "why": "DECLARED ABSENT FOR ALL THREE: YSX, CSX and LSX between them list a few dozen "
            "companies with effectively no turnover, none of the three has a listed derivative, "
            "and no regulator in the group publishes margin or short-interest statistics",
     "pit_warning": "DOES NOT EXIST: there is no order book, no expiry clock and no leverage "
                    "series to condition on, and `retail_leverage_regime` is UNMEASURED because "
                    "there is no retail trading ecology to measure, not because nobody looked"},
)

# --------------------------------------------------------------------------- terminology
#: THREE SCRIPTS AND TWO MIRROR LANGUAGES. Burmese, Khmer and Lao are three different writing
#: systems with three different Unicode blocks, and an English-only crawl reads none of them.
#: THAI AND CHINESE ARE NOT DECORATION HERE: for Myanmar and Laos the buyer's statistics are
#: better than the seller's, so the Thai power and customs vocabulary and the Chinese customs
#: and railway vocabulary are part of this pack's working ground rather than a courtesy.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "mm_monetary": ("ကျပ်", "ငွေလဲလှယ်နှုန်း", "ဗဟိုဘဏ်", "ဒေါ်လာ", "ငွေကြေးဖောင်းပွမှု",
                    "ငွေလဲကောင်တာ", "နိုင်ငံခြားငွေ"),
    "mm_energy": ("သဘာဝဓာတ်ငွေ့", "လျှပ်စစ်", "မီးပြတ်တောက်", "စက်သုံးဆီ", "ရေနံ"),
    "mm_trade": ("ပို့ကုန်", "သွင်းကုန်", "ကုန်သွယ်မှု", "နယ်စပ်ကုန်သွယ်ရေး", "ရန်ကုန်",
                 "ဈေးနှုန်း", "စီးပွားရေး"),
    "mm_resources": ("ရှားပါးမြေသတ္တု", "ကျောက်စိမ်း", "ကချင်ပြည်နယ်", "သတ္တုတွင်း", "ဆန်",
                     "ဆန်တင်ပို့မှု", "အထည်ချုပ်စက်ရုံ", "အလုပ်သမား"),
    "mm_calendar": ("သင်္ကြန်", "ရုံးပိတ်ရက်", "နှစ်သစ်ကူး"),
    "kh_monetary": ("រៀល", "ធនាគារជាតិ", "អត្រាប្តូរប្រាក់", "ដុល្លារ", "អតិផរណា",
                    "ប្រាក់បញ្ញើ", "ប្រព័ន្ធបាគង"),
    "kh_trade": ("នាំចេញ", "នាំចូល", "ពាណិជ្ជកម្ម", "គយ", "សេដ្ឋកិច្ច", "កំពង់ផែ",
                 "ក្រុងព្រះសីហនុ"),
    "kh_industry": ("វាយនភណ្ឌ", "រោងចក្រ", "ពលករ", "អង្ករ", "ដំឡូងមី", "កសិកម្ម"),
    "kh_market": ("ភាគហ៊ុន", "ផ្សារមូលបត្រ", "វិនិយោគ"),
    "kh_calendar": ("ចូលឆ្នាំថ្មី", "ភ្ជុំបិណ្ឌ", "វិសាខបូជា", "ពិធីបុណ្យអុំទូក"),
    "la_monetary": ("ກີບ", "ທະນາຄານແຫ່ງ ສປປ ລາວ", "ອັດຕາແລກປ່ຽນ", "ເງິນເຟີ້", "ລາຄາ",
                    "ໜີ້ສິນ", "ໜີ້ຕ່າງປະເທດ"),
    "la_energy": ("ໄຟຟ້າ", "ເຂື່ອນ", "ພະລັງງານ", "ແມ່ນ້ຳຂອງ", "ນ້ຳມັນ"),
    "la_trade": ("ສົ່ງອອກ", "ນຳເຂົ້າ", "ເສດຖະກິດ", "ພາສີ", "ລົດໄຟ ລາວ-ຈີນ", "ກະສິກຳ",
                 "ກາເຟ"),
    "la_market": ("ຕະຫຼາດຫຼັກຊັບ", "ການລົງທຶນ", "ງົບປະມານ"),
    "la_calendar": ("ປີໃໝ່ລາວ", "ບຸນອອກພັນສາ", "ວັນພັກ"),
    "th_mirror": ("ก๊าซธรรมชาติ", "ไฟฟ้า", "แรงงานข้ามชาติ", "ข้าว", "ชายแดน",
                  "นำเข้าไฟฟ้าจากลาว"),
    "cn_mirror": ("稀土 缅甸 进口", "克钦邦", "中老铁路", "柬埔寨 大米", "海关总署",
                  "镝 铽 价格"),
}

# --------------------------------------------------------------------------- script detection
#: THREE UNICODE BLOCKS, ONE PER JURISDICTION, PLUS THE TWO MIRROR SCRIPTS. The Lao block sits
#: immediately after the Thai one and the two look alike to a careless matcher, which is exactly
#: why they are separated here: a crawler that treats Lao as Thai will read Vientiane's ground
#: with Bangkok's vocabulary and find nothing.
_BURMESE_RANGES = ((0x1000, 0x109F), (0xA9E0, 0xA9FF), (0xAA60, 0xAA7F))
_KHMER_RANGES = ((0x1780, 0x17FF), (0x19E0, 0x19FF))
_LAO_RANGES = ((0x0E80, 0x0EFF),)
_THAI_RANGES = ((0x0E00, 0x0E7F),)
_HAN_RANGES = ((0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF))
_SCRIPT_RANGES: dict[str, tuple[tuple[int, int], ...]] = {
    "burmese": _BURMESE_RANGES, "khmer": _KHMER_RANGES, "lao": _LAO_RANGES,
    "thai": _THAI_RANGES, "han": _HAN_RANGES,
}
#: Which script each jurisdiction is READ IN. The parity fence counts jurisdictions; this is how
#: a test checks that each one has ground written in its own hand.
JURISDICTION_SCRIPTS: dict[str, str] = {"mm": "burmese", "kh": "khmer", "la": "lao"}


def has_script(text: str, script: str) -> bool:
    """True when `text` contains at least one codepoint of the named script."""
    ranges = _SCRIPT_RANGES.get(str(script))
    if not ranges:
        raise ValueError(f"unknown script {script!r}; known: {sorted(_SCRIPT_RANGES)}")
    return any(any(lo <= ord(ch) <= hi for lo, hi in ranges) for ch in str(text))


def script_terms(script: str, terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    """Every term in the terminology table written in one of the five scripts."""
    rows = TERMINOLOGY if terminology is None else terminology
    return [t for terms in rows.values() for t in terms if has_script(t, script)]


def script_coverage(terminology: Mapping[str, Iterable[str]] | None = None) -> dict[str, int]:
    """How many terms the pack carries in each script. A zero for any of the three domestic
    scripts means one of this pack's jurisdictions is being read in somebody else's hand."""
    return {s: len(script_terms(s, terminology)) for s in _SCRIPT_RANGES}


def term_count(terminology: Mapping[str, Iterable[str]] | None = None) -> int:
    rows = TERMINOLOGY if terminology is None else terminology
    return len({t for terms in rows.values() for t in terms})


def _seq(values: Iterable[Any]) -> tuple[str, ...]:
    return tuple(str(v) for v in values)


# --------------------------------------------------------------------------- source layers
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


def source_class(sid: str, label: str, *, layer: str, roots: Iterable[str],
                 queries: Iterable[str], languages: Iterable[str], access_label: str,
                 credibility: str, predictive_state: str, licence: str,
                 machine_use_allowed: bool = True, notes: str = "") -> dict[str, Any]:
    """One class of source with the roots a crawler starts from and its three INDEPENDENT
    labels. `queries` are native-script terms, never translations. `machine_use_allowed=False`
    registers ground whose terms forbid extraction: never scraped, never omitted."""
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
    """A layer this pack has nothing in, declared BY NAME with the reason (L1.28a)."""
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
        "mk_cbm", "Central Bank of Myanmar: the administered reference rate, the FX directives, "
                  "the bank and money-changer licensing notices and what remains of the "
                  "monetary statistics", layer="official",
        roots=("https://www.cbm.gov.mm/", "https://www.cbm.gov.mm/content/exchange-rate",
               "https://www.cbm.gov.mm/announcement"),
        queries=("ငွေလဲလှယ်နှုန်း", "ဗဟိုဘဏ် ညွှန်ကြားချက်", "နိုင်ငံခြားငွေ ထိန်းချုပ်မှု",
                 "ဘဏ် သတင်းထုတ်ပြန်ချက်", "ကျပ် ဒေါ်လာ နှုန်း"),
        languages=("my", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="AUTHORITATIVE FOR WHAT IT DECIDES AND NOT FOR WHAT THE ECONOMY PAYS. The "
              "reference rate is an administrative decision; the price at which foreign "
              "currency actually changes hands is in the retail_ecology layer, and the SPREAD "
              "between them is the observable `parallel_spread` computes"),
    source_class(
        "mk_mm_trade_gazette", "Myanmar Ministry of Commerce, the Myanmar Gazette and the state "
                               "notification stream: trade policy, export licensing, the rice "
                               "reference price and the annual holiday notification",
        layer="official",
        roots=("https://www.commerce.gov.mm/", "https://www.myanmargazette.gov.mm/",
               "https://www.president-office.gov.mm/"),
        queries=("ပို့ကုန် လိုင်စင်", "ဆန်တင်ပို့မှု မူဝါဒ", "ကုန်သွယ်မှု ညွှန်ကြားချက်",
                 "ရုံးပိတ်ရက် ကြေညာချက်", "နယ်စပ်ကုန်သွယ်ရေး"),
        languages=("my", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the policy stream still publishes even though the statistical stream has largely "
              "stopped; a directive is a dated event and this is where its date comes from"),
    source_class(
        "mk_nbc", "National Bank of Cambodia: the daily official rate, the monetary and "
                  "dollarisation statistics, the Bakong payment system and the banking "
                  "supervision file", layer="official",
        roots=("https://www.nbc.gov.kh/", "https://www.nbc.gov.kh/english/economic_research/"
               "statistics.php", "https://bakong.nbc.gov.kh/"),
        queries=("អត្រាប្តូរប្រាក់ ផ្លូវការ", "ស្ថិតិរូបិយវត្ថុ", "ប្រាក់បញ្ញើ ដុល្លារ",
                 "ប្រព័ន្ធបាគង", "ធនាគារជាតិ សេចក្តីប្រកាស"),
        languages=("km", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE NATURAL EXPERIMENT'S OWN PUBLISHER. The dollarisation share is published by "
              "the institution trying to reduce it, which makes both the number and the "
              "policy effort dated and public at the same time"),
    source_class(
        "mk_kh_stats_customs", "Cambodia's National Institute of Statistics and the General "
                               "Department of Customs and Excise: national accounts, CPI and "
                               "monthly trade by product and destination", layer="official",
        roots=("https://www.nis.gov.kh/", "https://www.customs.gov.kh/",
               "https://www.customs.gov.kh/en/trade-statistics"),
        queries=("ស្ថិតិ ពាណិជ្ជកម្ម", "នាំចេញ វាយនភណ្ឌ", "សន្ទស្សន៍ថ្លៃទំនិញ",
                 "គយ របាយការណ៍ ប្រចាំខែ", "នាំចេញ អង្ករ"),
        languages=("km", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the cleanest self-published monthly series any of the three jurisdictions "
              "produces, and the one that carries the EU and US trade-policy events"),
    source_class(
        "mk_bol_lsb", "Bank of the Lao PDR and the Lao Statistics Bureau: the reference rate and "
                      "commercial band, monetary statistics, CPI and the national accounts",
        layer="official",
        roots=("https://www.bol.gov.la/", "https://www.bol.gov.la/en/exchangeRate",
               "https://www.lsb.gov.la/"),
        queries=("ອັດຕາແລກປ່ຽນ", "ເງິນເຟີ້ ລາຍເດືອນ", "ສະຖິຕິ ເສດຖະກິດ",
                 "ທະນາຄານແຫ່ງ ສປປ ລາວ ແຈ້ງການ", "ດັດຊະນີລາຄາ"),
        languages=("lo", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the Lao CPI series that exceeded forty per cent year-on-year in 2023 is the most "
              "informative macro print in this pack, and the three-rate exchange table beside "
              "it is where the rationing shows"),
    source_class(
        "mk_la_mof_gazette", "Lao Ministry of Finance, the official gazette and the National "
                             "Assembly record: the budget, the external debt bulletin, the "
                             "concession approvals and the annual holiday notice",
        layer="official",
        roots=("https://www.mof.gov.la/", "https://laoofficialgazette.gov.la/",
               "https://www.na.gov.la/"),
        queries=("ງົບປະມານ ແຫ່ງລັດ", "ໜີ້ຕ່າງປະເທດ", "ລັດຖະບານ ຂໍ້ຕົກລົງ", "ວັນພັກ ລັດຖະການ",
                 "ສັນຍາ ສຳປະທານ"),
        languages=("lo",), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE LEGAL LAYER, READ IN LAO. The hydropower concessions, the debt deferrals and "
              "the railway agreements become citable only here, and the gazette is the "
              "authority for the holiday table this pack types"),
    source_class(
        "mk_cn_customs", "China's General Administration of Customs: imports by origin, "
                         "including the rare-earth lines from Myanmar and the Laos border trade",
        layer="official",
        roots=("http://stats.customs.gov.cn/", "http://www.customs.gov.cn/"),
        queries=("稀土 缅甸 进口", "海关总署 统计 月度", "老挝 进口 商品", "镝 铽 进口量",
                 "边境贸易 云南"),
        languages=("zh", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="FOR THE KACHIN FLOW THIS IS NOT A CROSS-CHECK, IT IS THE PRIMARY MEASUREMENT. "
              "The seller publishes nothing, so the buyer's customs table by origin is the only "
              "public count of the world's main heavy rare-earth supply chain"),
    source_class(
        "mk_th_energy_customs", "Thailand's energy and customs authorities: gas supply by "
                                "source including Myanmar pipeline deliveries, electricity "
                                "imported from Laos, and border trade by crossing",
        layer="official",
        roots=("https://www.eppo.go.th/", "https://www.egat.co.th/", "http://www.customs.go.th/"),
        queries=("ก๊าซธรรมชาติ จากเมียนมา", "นำเข้าไฟฟ้าจากลาว", "การค้าชายแดน",
                 "สถิติพลังงาน รายเดือน", "แรงงานข้ามชาติ"),
        languages=("th", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE BUYER'S BOOKS AGAIN, AND THE SAME LOGIC. Thailand counts the gas it receives "
              "and the electricity it imports, so the Myanmar and Lao export volumes are "
              "measured from Bangkok. The `th` pack owns these series and this pack reads them"),
    # ---- institutional
    source_class(
        "mk_exchanges", "The three domestic exchanges and their regulators: YSX and the "
                        "Securities and Exchange Commission of Myanmar, CSX and the Securities "
                        "and Exchange Regulator of Cambodia, LSX and the Lao securities office",
        layer="institutional",
        roots=("https://ysx-mm.com/", "https://www.csx.com.kh/", "https://www.lsx.com.la/"),
        queries=("ផ្សារមូលបត្រ កម្ពុជា", "ភាគហ៊ុន ចុះបញ្ជី", "ຕະຫຼາດຫຼັກຊັບ ລາວ",
                 "ရှယ်ယာ ဈေးကွက်", "ການລົງທຶນ ຫຼັກຊັບ"),
        languages=("km", "lo", "my", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THREE EXCHANGES WITH ALMOST NO TAPE. Registered so a miner reports the absence by "
              "name; the one genuinely useful disclosure in the group is the Lao power "
              "utility's, which is the only domestic public window onto the PPA economics"),
    source_class(
        "mk_ifi", "The multilateral institutions that now do these countries' statistics for "
                  "them: the ADB, the IMF, the World Bank and the ASEAN secretariat",
        layer="institutional",
        roots=("https://www.adb.org/countries/myanmar/main",
               "https://www.adb.org/countries/lao-pdr/main",
               "https://www.imf.org/en/Countries/KHM", "https://data.worldbank.org/"),
        queries=("ADB Asian Development Outlook Lao PDR", "IMF Article IV Cambodia",
                 "World Bank Myanmar economic monitor", "Lao PDR debt sustainability",
                 "ASEAN statistics trade"),
        languages=("en",), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE DECLARED SUBSTITUTE FOR THE MYANMAR STATISTICAL VACUUM AND FOR THE LAO "
              "ACADEMIC ONE. The World Bank Myanmar Economic Monitor and the ADB outlooks are "
              "estimates rather than measurements and the pack labels them as such, but an "
              "estimate with a published method beats a series that stopped in 2021"),
    source_class(
        "mk_energy_industry", "The energy and power institutions: the pipeline operators, EDL "
                              "and EDL-Generation in Laos, the Thai offtaker, and the industry "
                              "bodies that publish PPA and grid data",
        layer="institutional",
        roots=("https://www.edl.com.la/", "https://www.edlgen.com.la/", "https://www.egat.co.th/",
               "https://www.eria.org/"),
        queries=("ໄຟຟ້າ ສົ່ງອອກ ສັນຍາ", "ເຂື່ອນ ກຳລັງຜະລິດ", "นำเข้าไฟฟ้าจากลาว",
                 "ERIA Mekong energy", "ໂຄງການ ໄຟຟ້າ ນ້ຳຕົກ"),
        languages=("lo", "th", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the listed Lao generator's disclosures are the one place the PPA economics -- "
              "contracted volume, tariff structure, hydrology risk -- are visible from outside"),
    source_class(
        "mk_industry_bodies", "The industry associations: the Myanmar Rice Federation, the "
                              "Garment Manufacturers Association in Cambodia, the Cambodia Rice "
                              "Federation and the chambers of commerce",
        layer="institutional",
        roots=("https://www.mrf.com.mm/", "https://www.gmac-cambodia.org/",
               "https://www.crf.org.kh/"),
        queries=("ဆန် တင်ပို့ ပမာណ", "វាយនភណ្ឌ នាំចេញ ស្ថិតិ", "អង្ករ នាំចេញ ប្រចាំខែ",
                 "ကုန်သည်များအသင်း", "រោងចក្រ សមាគម"),
        languages=("my", "km", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="in two of these three countries the INDUSTRY BODY publishes more usable export "
              "data than the ministry does, which is a fact about the state rather than about "
              "the industry and is recorded as such"),
    # ---- academic
    source_class(
        "mk_academic", "The regional research institutions that actually study these economies: "
                       "CDRI in Phnom Penh, ISEAS in Singapore, the Thai and Japanese Mekong "
                       "programmes, and the open indices where their work is findable",
        layer="academic",
        roots=("https://cdri.org.kh/", "https://www.iseas.edu.sg/", "https://openalex.org/",
               "https://core.ac.uk/"),
        queries=("CDRI Cambodia working paper dollarization", "ISEAS Myanmar economy",
                 "Mekong hydropower economics paper", "សេដ្ឋកិច្ច ស្រាវជ្រាវ",
                 "Lao PDR debt distress working paper"),
        languages=("en", "km"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="mixed; per-paper",
        notes="CAMBODIA HAS A REAL DOMESTIC RESEARCH INSTITUTION AND THE OTHER TWO DO NOT. The "
              "dollarisation literature in particular is substantial, dated and testable, which "
              "is why MK-E is a research domain and not a story"),
    source_class(
        "mk_mrc_technical", "The Mekong River Commission's technical and scientific programme: "
                            "hydrology reports, the state-of-basin studies and the joint "
                            "environmental monitoring", layer="academic",
        roots=("https://www.mrcmekong.org/", "https://portal.mrcmekong.org/",
               "https://www.mrcmekong.org/publications/"),
        queries=("Mekong hydrological conditions report", "MRC state of the basin",
                 "reservoir operation Mekong mainstream", "ແມ່ນ້ຳຂອງ ລະດັບນ້ຳ",
                 "Mekong flow alteration study"),
        languages=("en", "lo", "th", "km"), access_label="OPEN_DATA",
        credibility="AUTHORITATIVE", predictive_state="UNTESTED", licence="free, public",
        notes="THE DECLARED SUBSTITUTE FOR LAOS'S MISSING ACADEMIC LAYER. An intergovernmental "
              "body with a published method, a daily station network and a technical archive is "
              "a better ground than a domestic economics faculty that does not exist"),
    # ---- practitioner
    source_class(
        "mk_practitioner", "The regional sell-side and advisory ground that covers these "
                           "economies from outside: the Thai and Singaporean banks' ASEAN "
                           "research, the Cambodian commercial banks and the frontier advisory "
                           "shops", layer="practitioner",
        roots=("https://www.acledabank.com.kh/", "https://www.mekongstrategic.com/",
               "https://www.iseas.edu.sg/"),
        queries=("Cambodia economic outlook bank research", "Mekong frontier market note",
                 "Lao kip outlook analysis", "វិនិយោគ វិភាគ", "ASEAN frontier research"),
        languages=("en", "km"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free with registration in places",
        notes="THIN BY MEASUREMENT AND NOT BY OVERSIGHT. Almost all practitioner coverage of "
              "these three economies is written in Bangkok, Singapore or Hong Kong, which is "
              "itself the finding: the forward view on the Mekong is a foreign view"),
    source_class(
        "mk_price_assessors", "The commercial assessments that price what these countries "
                              "actually sell: the rare-earth oxide assessments, the rice export "
                              "quotes and the seaborne freight indices", layer="practitioner",
        roots=("https://www.fastmarkets.com/", "https://www.spglobal.com/commodityinsights/"),
        queries=("dysprosium oxide price assessment", "terbium oxide price China",
                 "Thai 5% broken rice quote", "rare earth feedstock Myanmar assessment"),
        languages=("en", "zh"), access_label="LICENSED", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="commercial licence; machine extraction prohibited",
        machine_use_allowed=False,
        notes="REGISTERED AND NEVER SCRAPED. These are the prices the physical rare-earth and "
              "rice trades are struck against and their terms forbid automated collection; "
              "omitting the row would lose the knowledge that the ground exists, so it is "
              "recorded with machine_use_allowed=false and the customs tonnage is used instead"),
    # ---- retail_ecology
    source_class(
        "mk_parallel_fx_boards", "The money-changer and parallel-rate channels: the Yangon and "
                                 "Mandalay changer quotes circulated on messaging platforms, "
                                 "the Vientiane parallel quote and the Cambodian remittance "
                                 "counters", layer="retail_ecology",
        roots=("https://t.me/", "https://www.facebook.com/"),
        queries=("ငွေလဲနှုန်း ယနေ့", "ကျပ် ဒေါ်လာ ဈေး", "ອັດຕາແລກປ່ຽນ ນອກລະບົບ",
                 "ដុល្លារ ប្តូរ ថ្ងៃនេះ", "ဈေးကွက် ငွေလဲ"),
        languages=("my", "lo", "km"), access_label="USER_SUBMITTED", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="platform terms apply",
        notes="KEPT AT LOW WEIGHT AND NEVER DROPPED, AND IT IS THE ONLY PLACE THE REAL PRICE "
              "LIVES. In a two-rate economy the transactable rate is quoted by changers and "
              "circulated on messaging channels, not published by any institution. It is "
              "UNRELIABLE as a label and indispensable as a ground, and the pack says both"),
    source_class(
        "mk_worker_trader_forums", "The cross-border worker, trucker and trader communities: "
                                   "Myanmar migrant groups in Thailand, the Cambodian garment "
                                   "worker channels and the Lao border-trade pages",
        layer="retail_ecology",
        roots=("https://www.facebook.com/", "https://t.me/"),
        queries=("ထိုင်း အလုပ်သမား ငွေလွှဲ", "ពលករ រោងចក្រ ប្រាក់ខែ", "ຊາຍແດນ ການຄ້າ ກຸ່ມ",
                 "နယ်စပ် ကုန်တင်ကား", "แรงงานเมียนมา กลุ่ม"),
        languages=("my", "km", "lo", "th"), access_label="PUBLIC_SOCIAL",
        credibility="UNRELIABLE", predictive_state="UNTESTED", licence="platform terms apply",
        notes="the remittance and border-labour channels are large real flows that no statistic "
              "in this pack captures; the social ground is used to TIME a hypothesis about them "
              "and never to evidence one"),
    # ---- app_ecosystem
    source_class(
        "mk_payment_apps", "The payment rails people actually use: Bakong and the Cambodian bank "
                           "apps, Wave and the Myanmar mobile wallets, BCEL One and the Lao "
                           "bank apps", layer="app_ecosystem",
        roots=("https://bakong.nbc.gov.kh/", "https://www.wavemoney.com.mm/",
               "https://www.bcel.com.la/"),
        queries=("ប្រព័ន្ធបាគង ប្រតិបត្តិការ", "ငွေလွှဲ အက်ပလီကေးရှင်း", "ແອັບ ທະນາຄານ ໂອນເງິນ",
                 "mobile wallet Myanmar transfer", "ប្រាក់ផ្ទេរ ឆ្លងដែន"),
        languages=("km", "my", "lo", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="platform terms apply",
        notes="BAKONG IS A POLICY INSTRUMENT, NOT JUST AN APP: the NBC built it and publishes "
              "its volumes, and riel-denominated transaction growth on it is the measurable "
              "half of the de-dollarisation effort"),
    source_class(
        "mk_logistics_apps", "The customs single-window and logistics systems: the Cambodian and "
                             "Lao national single windows, the ASEAN customs transit system and "
                             "the border permit portals", layer="app_ecosystem",
        roots=("https://www.customs.gov.kh/", "https://www.laotradeportal.gov.la/",
               "https://asw.asean.org/"),
        queries=("ការិយាល័យ គយ ប្រព័ន្ធ អេឡិចត្រូនិច", "ລະບົບ ພາສີ ອອນລາຍ",
                 "Lao trade portal tariff", "ASEAN single window transit", "គយ ប្រកាស អនឡាញ"),
        languages=("km", "lo", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="a single window is a MEASUREMENT INSTRUMENT for border flow and a rationing "
              "device at once; a step in a throughput series at a portal's launch date is an "
              "administrative artefact and a study must control for it"),
    # ---- media
    source_class(
        "mk_mm_media", "The Myanmar press, domestic and in exile: the state papers, and "
                       "Irrawaddy, Myanmar Now, Frontier Myanmar and the successors to the "
                       "outlets closed after 2021", layer="media",
        roots=("https://www.irrawaddy.com/", "https://myanmar-now.org/", "https://frontiermyanmar"
               ".net/", "https://www.gnlm.com.mm/"),
        queries=("ငွေလဲနှုန်း သတင်း", "ကချင်ပြည်နယ် သတ္တုတွင်း", "ဆန်ဈေး", "လျှပ်စစ်မီး ပြတ်တောက်",
                 "နယ်စပ် ကုန်သွယ်ရေး သတင်း"),
        languages=("my", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE DECLARED SUBSTITUTE FOR A STATISTICAL SYSTEM THAT STOPPED. The exile outlets "
              "report fuel prices, changer rates, power cuts and mine closures with dates, "
              "which is the only high-frequency Myanmar ground that exists. RELIABLE rather "
              "than AUTHORITATIVE, and the state papers beside them are the other side"),
    source_class(
        "mk_kh_la_media", "The Cambodian and Lao press: Khmer Times, the Phnom Penh Post and the "
                          "Khmer-language outlets; Vientiane Times, the Laotian Times and the "
                          "Lao state media", layer="media",
        roots=("https://www.khmertimeskh.com/", "https://www.phnompenhpost.com/",
               "https://www.vientianetimes.org.la/", "https://laotiantimes.com/"),
        queries=("នាំចេញ វាយនភណ្ឌ ព័ត៌មាន", "កំពង់ផែ ព្រះសីហនុ", "ເງິນເຟີ້ ຂ່າວ",
                 "ລາຄາ ນ້ຳມັນ ຂຶ້ນ", "ອັດຕາແລກປ່ຽນ ກີບ ຂ່າວ"),
        languages=("km", "lo", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the Lao press in particular is the fastest public read on fuel shortages and "
              "parallel-rate moves, both of which precede the monthly statistics by weeks"),
    source_class(
        "mk_rfa_regional", "The regional broadcasters and wire services in the three languages: "
                           "the Burmese, Khmer and Lao services, and the Thai and Chinese trade "
                           "press covering the same borders", layer="media",
        roots=("https://www.rfa.org/burmese/", "https://www.rfa.org/khmer/",
               "https://www.rfa.org/lao/", "https://www.bbc.com/burmese"),
        queries=("ကချင် တိုက်ပွဲ သတ္တုတွင်း", "ព័ត៌មាន សេដ្ឋកិច្ច កម្ពុជា", "ຂ່າວ ເສດຖະກິດ ລາວ",
                 "稀土 缅甸 边境 关闭", "ชายแดน เมียนมา การค้า"),
        languages=("my", "km", "lo", "zh", "th"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the only ground that reports a Kachin border closure the week it happens, in a "
              "language the participants use; the Chinese trade press carries the same event "
              "from the buyer's side and often a few days earlier"),
    # ---- archive
    source_class(
        "mk_archive", "The archives that hold what is no longer published: the Myanmar Gazette "
                      "back-runs, the Cambodian and Lao gazette archives, and the web archives "
                      "holding the overwritten rate and statistics pages", layer="archive",
        roots=("https://www.myanmargazette.gov.mm/", "https://laoofficialgazette.gov.la/",
               "https://web.archive.org/"),
        queries=("ပြည်ထောင်စု သမ္မတ ပြန်တမ်း", "រាជកិច្ច ប្រកាស", "ລັດຖະບານ ຈົດໝາຍເຫດ",
                 "archive exchange rate Myanmar 2021", "gazette archive Lao PDR"),
        languages=("my", "km", "lo", "en"), access_label="PUBLIC_ARCHIVE",
        credibility="AUTHORITATIVE", predictive_state="UNTESTED", licence="free, public",
        notes="THE ONLY ROUTE TO A POINT-IN-TIME VINTAGE IN ALL THREE COUNTRIES. Every rate "
              "page here is overwritten daily and several statistical series simply stopped, so "
              "a web-archive snapshot is not a convenience, it is the data"),
    source_class(
        "mk_comtrade_mirror", "UN Comtrade and the partner-country mirror archive: the historical "
                              "reconstruction of trade flows for countries that no longer report",
        layer="archive",
        roots=("https://comtradeplus.un.org/", "https://wits.worldbank.org/"),
        queries=("Comtrade Myanmar partner reported imports", "mirror statistics Lao PDR trade",
                 "Cambodia garment exports historical series", "HS 2805 rare earth trade data"),
        languages=("en",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="PARTNER-REPORTED DATA IS THE LAWFUL SUBSTITUTE FOR A REPORTER THAT STOPPED. It "
              "reconstructs Myanmar's trade from what everyone else declares, which is a real "
              "measurement with a known bias rather than an absence"),
    # ---- physical_economy
    source_class(
        "mk_mrc_stations", "The Mekong River Commission's daily station network: water levels "
                           "and flow at Chiang Saen, Luang Prabang, Vientiane, Pakse, Stung "
                           "Treng and the downstream gauges", layer="physical_economy",
        roots=("https://portal.mrcmekong.org/", "https://www.mrcmekong.org/",
               "https://portal.mrcmekong.org/time-series/water-level"),
        queries=("Mekong water level Vientiane daily", "ແມ່ນ້ຳຂອງ ລະດັບນ້ຳ", "ระดับน้ำโขง",
                 "MRC time series station water level", "Mekong flow Pakse"),
        languages=("en", "lo", "th", "km"), access_label="OPEN_DATA",
        credibility="AUTHORITATIVE", predictive_state="UNTESTED", licence="free, public",
        notes="THE PACK'S ONLY DAILY PHYSICAL SERIES AND THE REASON LAOS IS TESTABLE AT ALL. A "
              "public, daily, station-level reading of the constraint on a country's principal "
              "export is something almost no other energy exporter provides"),
    source_class(
        "mk_borders_ports", "The physical chokepoints: the Myanmar-Thailand and Myanmar-China "
                            "border crossings, Sihanoukville and Phnom Penh ports, the "
                            "Laos-China Railway terminals and the Thai border checkpoints",
        layer="physical_economy",
        roots=("https://www.pas.gov.kh/", "https://www.laotradeportal.gov.la/",
               "http://www.customs.go.th/"),
        queries=("កំពង់ផែ ស្វយ័ត ព្រះសីហនុ ចរាចរ", "ລົດໄຟ ລາວ-ຈີນ ຂົນສົ່ງ ສິນຄ້າ",
                 "နယ်စပ် ဂိတ် ပိတ်", "ด่านชายแดน แม่สอด", "中老铁路 货运量"),
        languages=("km", "lo", "my", "th", "zh"), access_label="PUBLIC",
        credibility="RELIABLE", predictive_state="UNTESTED", licence="free, public",
        notes="the Sihanoukville port count is published by a LISTED entity, which is the one "
              "place in this pack where a disclosure obligation makes a physical series "
              "reliable; the border crossings are reported by the neighbours"),
    source_class(
        "mk_power_pipelines", "The pipelines and the grid: the Yadana and Zawtika delivery "
                              "points, the cross-border transmission lines from Laos, and the "
                              "Thai system's own reserve-margin reporting",
        layer="physical_economy",
        roots=("https://www.eppo.go.th/", "https://www.egat.co.th/", "https://www.edl.com.la/"),
        queries=("ก๊าซ ยาดานา หยุดซ่อม", "แผนหยุดจ่ายก๊าซ เมียนมา", "ໄຟຟ້າ ສົ່ງອອກ ໄທ",
                 "သဘာဝဓာတ်ငွေ့ ပိုက်လိုင်း", "กำลังผลิตสำรอง ไฟฟ้า"),
        languages=("th", "lo", "my", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE ANNUAL PIPELINE MAINTENANCE SHUTDOWN IS ANNOUNCED IN ADVANCE and the Thai "
              "system operator has warned publicly about reserve margin in those windows -- a "
              "scheduled, dated, physical interruption to a neighbour's power fuel"),
    # ---- source_graph
    source_class(
        "mk_attribution", "The attribution phrases the region's reporting uses when it is "
                          "repeating a number rather than measuring one, in all five languages "
                          "-- the expansion edges the deep-forest miner follows",
        layer="source_graph",
        roots=("https://www.irrawaddy.com/", "https://www.khmertimeskh.com/",
               "https://www.vientianetimes.org.la/"),
        queries=("အရင်းအမြစ် ပြောကြားချက်", "យោងតាម ក្រសួង", "ອີງຕາມ ຂໍ້ມູນ ຂອງ", "据海关数据",
                 "ตามข้อมูลของ"),
        languages=("my", "km", "lo", "zh", "th"), access_label="PUBLIC", credibility="UNKNOWN",
        predictive_state="UNTESTED", licence="free, public",
        notes="IN A REGION WHOSE OWN STATISTICS HAVE GAPS, THE SAME FOREIGN ESTIMATE GETS QUOTED "
              "BACK AS IF IT WERE A DOMESTIC MEASUREMENT. Following the attribution is how the "
              "desk tells three independent readings apart from one reading quoted three times"),
    source_class(
        "mk_aggregator_mirrors", "Aggregators, mirrors and diaspora channels that republish "
                                 "Mekong data: the trade aggregators, the Telegram forwarding "
                                 "chains and the frontier-market newsletters",
        layer="source_graph",
        roots=("https://t.me/", "https://web.archive.org/", "https://comtradeplus.un.org/"),
        queries=("Myanmar economy data mirror", "ကျပ်ငွေ နှုန်း စုစည်း", "ລວມ ຂ່າວ ເສດຖະກິດ",
                 "Cambodia trade data aggregator"),
        languages=("en", "my", "lo"), access_label="PUBLIC", credibility="FRINGE",
        predictive_state="UNTESTED", licence="mixed",
        notes="KEPT AT LOW WEIGHT AND NEVER DROPPED. A channel that posts a changer rate before "
              "any outlet does is either the fastest ground in the pack or wrong, and both are "
              "dated, testable claims; FRINGE is the weight, not a reason to delete it"),
)

#: NO LAYER IS BLANK FOR THE PACK AS A WHOLE, because where one jurisdiction has nothing another
#: does. The measured refusals are PER JURISDICTION and live in `NO_LAWFUL_GROUND` below, which
#: is the honest shape for a three-country pack: a layer covered by Cambodia is not coverage of
#: Myanmar, and a miner steered at one country must be told so by name rather than quietly
#: reading another country's ground and reporting it as that country's.
LAYER_ABSENCES: dict[str, str] = {}

#: THE MEASURED REFUSALS, ONE ROW PER JURISDICTION AND LAYER, EACH WITH ITS LAWFUL SUBSTITUTE.
#: This is the pack's most valuable table and the reason it is honest: three frontier economies
#: have real, nameable holes, and a padded row claiming otherwise would be worth less than
#: nothing because a miner would trust it.
NO_LAWFUL_GROUND: tuple[dict[str, str], ...] = (
    {"jurisdiction": "mm", "layer": "official",
     "reason": "MYANMAR'S STATISTICAL SYSTEM HAS LARGELY STOPPED PUBLISHING SINCE 2021. The "
               "Central Statistical Organization's series are irregular or absent, reserves are "
               "not published on a reliable schedule, and the national accounts are estimates "
               "made elsewhere. The policy and directive stream still publishes, which is why "
               "the layer is not blank -- but the MEASUREMENT half of it is gone",
     "substitute": "partner-country MIRROR customs (China and Thailand above all), UN Comtrade "
                   "partner-reported data, and the World Bank Myanmar Economic Monitor and IMF "
                   "and ADB estimates, each labelled an estimate rather than a measurement"},
    {"jurisdiction": "mm", "layer": "institutional",
     "reason": "THE YANGON STOCK EXCHANGE HAS EFFECTIVELY NO TAPE. A handful of listings, days "
               "with no trade at all, no derivative, no index a foreign desk can reach and no "
               "published margin or short-interest series",
     "substitute": "the Thai and Chinese institutional counterparties that transact with "
                   "Myanmar -- the gas offtaker's own reporting and the Chinese customs "
                   "tables -- plus the industry bodies, which publish more than the ministry"},
    {"jurisdiction": "mm", "layer": "retail_ecology",
     "reason": "there is no retail TRADING ecology at all: no domestic brokerage industry of "
               "consequence, no margin product, no retail investor base and no leverage "
               "statistics of any kind",
     "substitute": "the money-changer and parallel-rate channels, which are a retail ecology of "
                   "a different sort -- the place the transactable exchange rate is actually "
                   "quoted -- registered as USER_SUBMITTED and UNRELIABLE and used to time a "
                   "hypothesis, never to evidence one"},
    {"jurisdiction": "la", "layer": "academic",
     "reason": "LAOS HAS NO DOMESTIC ACADEMIC ECONOMICS GROUND to speak of: no research "
               "institution publishing empirical macroeconomics on the country, no working "
               "paper series and no domestic journal a miner can crawl",
     "substitute": "the Mekong River Commission's technical programme (an intergovernmental "
                   "body with a published method and a daily station network), the ADB and IMF "
                   "country work, and the Thai and Japanese Mekong research programmes"},
    {"jurisdiction": "la", "layer": "practitioner",
     "reason": "there is no domestic brokerage or advisory research industry; the Lao "
               "Securities Exchange's few listings are not covered by anybody domestically",
     "substitute": "the Thai and Singaporean sell-side that covers the Lao independent power "
                   "producers as counterparties of Thai offtakers, and the listed Lao "
                   "generator's own disclosures"},
    {"jurisdiction": "la", "layer": "retail_ecology",
     "reason": "no retail trading ecology: no margin product, no retail base, no statistics",
     "substitute": "the parallel-rate and border-trade channels, and the bank app ecosystem, "
                   "both registered at low weight"},
    {"jurisdiction": "kh", "layer": "practitioner",
     "reason": "the domestic practitioner layer is THIN: a small number of bank research desks "
               "and advisory shops, most of the forward view written in Bangkok or Singapore",
     "substitute": "the regional ASEAN sell-side, CDRI's applied work, and the industry "
                   "associations' own export statistics"},
    {"jurisdiction": "kh", "layer": "retail_ecology",
     "reason": "no retail trading ecology: the CSX has a handful of listings and no derivative, "
               "and no regulator publishes margin or leverage data",
     "substitute": "the Bakong payment-system volumes and the remittance counters, which "
                   "measure household financial behaviour even though no one is trading"},
)

#: NATIVE QUERY TERRITORIES: what the deep-forest miner actually runs, per layer, in Burmese,
#: Khmer and Lao -- with the Thai and Chinese mirror terms where the buyer's ground is faster.
#: Three or more per layer for every layer that is not declared absent.
QUERY_TERRITORIES: dict[str, tuple[str, ...]] = {
    "official": ("ငွေလဲလှယ်နှုန်း ဗဟိုဘဏ်", "អត្រាប្តូរប្រាក់ ផ្លូវការ", "ອັດຕາແລກປ່ຽນ ທາງການ",
                 "ស្ថិតិ នាំចេញ ប្រចាំខែ", "ເງິນເຟີ້ ລາຍເດືອນ", "稀土 缅甸 进口",
                 "ก๊าซธรรมชาติ จากเมียนมา"),
    "institutional": ("ផ្សារមូលបត្រ កម្ពុជា ភាគហ៊ុន", "ຕະຫຼາດຫຼັກຊັບ ລາວ ບໍລິສັດ",
                      "ဆန် တင်ပို့ အသင်း", "ໄຟຟ້າ ລາວ ສົ່ງອອກ ສັນຍາ", "វាយនភណ្ឌ សមាគម"),
    "academic": ("CDRI dollarization Cambodia study", "Mekong hydropower economics paper",
                 "Lao PDR debt sustainability analysis", "សេដ្ឋកិច្ច ស្រាវជ្រាវ ការសិក្សា",
                 "Myanmar economy working paper 2024"),
    "practitioner": ("Cambodia macro outlook note", "Lao kip forecast analysis",
                     "Mekong frontier investment research", "វិភាគ ទីផ្សារ",
                     "rare earth supply chain Myanmar analysis"),
    "retail_ecology": ("ငွေလဲနှုန်း ယနေ့ ဈေး", "ដុល្លារ ប្តូរ ថ្ងៃនេះ", "ອັດຕາແລກປ່ຽນ ນອກລະບົບ",
                       "ពលករ រោងចក្រ ប្រាក់ខែ", "ထိုင်း အလုပ်သမား ငွေလွှဲ"),
    "app_ecosystem": ("ប្រព័ន្ធបាគង ប្រតិបត្តិការ", "ແອັບ ທະນາຄານ ໂອນເງິນ",
                      "ငွေလွှဲ အက်ပလီကေးရှင်း", "ລະບົບ ພາສີ ອອນລາຍ", "គយ ប្រកាស អនឡាញ"),
    "media": ("ကချင်ပြည်နယ် သတ္တုတွင်း သတင်း", "កំពង់ផែ ព្រះសីហនុ ព័ត៌មាន", "ລາຄາ ນ້ຳມັນ ຂຶ້ນ ຂ່າວ",
              "ဆန်ဈေး တက်", "稀土 缅甸 边境 关闭"),
    "archive": ("ပြည်ထောင်စု သမ္မတ ပြန်တမ်း", "រាជកិច្ច ប្រកាស បណ្ណសារ", "ລັດຖະບານ ຈົດໝາຍເຫດ",
                "Comtrade partner reported Myanmar", "archive exchange rate page snapshot"),
    "physical_economy": ("ระดับน้ำโขง สถานี", "ແມ່ນ້ຳຂອງ ລະດັບນ້ຳ", "中老铁路 货运量",
                         "កំពង់ផែ ចរាចរ កុងតឺន័រ", "แผนหยุดจ่ายก๊าซ เมียนมา",
                         "နယ်စပ် ဂိတ် ပိတ်"),
    "source_graph": ("យោងតាម ក្រសួង", "ອີງຕາມ ຂໍ້ມູນ ຂອງ", "အရင်းအမြစ် ပြောကြားချက်",
                     "据海关数据 缅甸", "ตามข้อมูลของ กระทรวง"),
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
    out: dict[str, list[str]] = {layer: [] for layer in SOURCE_LAYERS}
    for sc in SOURCE_CLASSES:
        layer = str(sc.get("layer") or "")
        if layer not in out:
            continue
        for q in sc.get("queries", ()):
            if q not in out[layer]:
                out[layer].append(q)
    for layer, extra in QUERY_TERRITORIES.items():
        if layer not in out:
            continue
        for q in extra:
            if q not in out[layer]:
                out[layer].append(q)
    return {k: tuple(v) for k, v in out.items()}


def jurisdiction_gaps(jurisdiction: str = "") -> tuple[dict[str, str], ...]:
    """The measured refusals, optionally for one jurisdiction. A miner steered at Myanmar reads
    this before it reports a Cambodian source as Myanmar coverage."""
    key = str(jurisdiction).strip().lower()
    if not key:
        return NO_LAWFUL_GROUND
    return tuple(r for r in NO_LAWFUL_GROUND if r["jurisdiction"] == key)


def source_layer_coverage() -> dict[str, Any]:
    counts = layer_counts()
    missing = {layer: str(LAYER_ABSENCES.get(layer, "")) for layer, n in counts.items() if not n}
    return {"code": CODE, "layer_counts": counts,
            "n_layers_covered": sum(1 for n in counts.values() if n),
            "n_sources": len([s for s in SOURCE_CLASSES
                              if not str(s["id"]).startswith("absent_")]),
            "missing": missing,
            "unexplained_missing": sorted(k for k, why in missing.items() if not why.strip()),
            "jurisdiction_gaps": {j: len(jurisdiction_gaps(j)) for j in JURISDICTIONS},
            "machine_use_forbidden": [str(s["id"]) for s in SOURCE_CLASSES
                                      if not s.get("machine_use_allowed", True)],
            "low_weight_kept": [str(s["id"]) for s in SOURCE_CLASSES
                                if s.get("credibility") in ("FRINGE", "UNRELIABLE",
                                                            "CONTRADICTED")],
            "query_territories": {k: len(v) for k, v in QUERY_TERRITORIES.items()},
            "script_coverage": script_coverage(),
            "rule": "ten layers, each carrying a source or named ABSENT with a reason, AND a "
                    "per-jurisdiction gap table because a layer covered by one of three "
                    "countries is not coverage of the other two; fringe and unreliable PUBLIC "
                    "material is kept at low weight and never dropped; a page whose terms "
                    "forbid machine extraction is registered machine_use_allowed=false, never "
                    "scraped and never omitted"}


# --------------------------------------------------------------------------- datasets
DATASETS: tuple[dict[str, Any], ...] = (
    {"name": "Chinese customs rare-earth imports from Myanmar by HS code",
     "source": "中华人民共和国海关总署 (China customs)",
     "coverage": "2010 onward, monthly, quantity and value by origin",
     "frequency": "monthly", "publication_lag_days": 22.0,
     "revisions": "occasionally restated in the annual yearbook", "licence": "free, public",
     "history_from": "2010-01", "pit_feasible": False,
     "assets": ("USDCNH", "XCUUSD", "XNIUSD"),
     "mechanism_families": ("supply_disruption", "mirror_statistics", "critical_minerals"),
     "how_to_fetch": "stats.customs.gov.cn online query -- origin Myanmar, HS 2530/2805/2846 "
                     "(rare-earth ores, metals and compounds), monthly quantity and value; THE "
                     "ONLY PUBLIC COUNT OF THIS FLOW, because the seller publishes nothing"},
    {"name": "Thai gas supply by source, including Myanmar pipeline deliveries",
     "source": "EPPO / the Thai energy ministry",
     "coverage": "2000 onward, monthly, by field and by import source",
     "frequency": "monthly", "publication_lag_days": 30.0, "revisions": "revised routinely",
     "licence": "free, public", "history_from": "2000-01", "pit_feasible": False,
     "assets": ("USDTHB", "XNGUSD", "XBRUSD"),
     "mechanism_families": ("energy_supply", "cross_border_flow", "supply_disruption"),
     "how_to_fetch": "eppo.go.th monthly energy statistics tables -- natural gas supply by "
                     "source, with the Myanmar import line separated; the ANNUAL PIPELINE "
                     "MAINTENANCE SHUTDOWN shows here as a dated volume hole"},
    {"name": "Thai announced pipeline maintenance shutdown calendar",
     "source": "the Thai system operator and the energy regulator",
     "coverage": "the announced outage windows for the Myanmar pipelines, by year",
     "frequency": "annual with updates", "publication_lag_days": 0.0,
     "revisions": "rescheduled rather than revised", "licence": "free, public",
     "history_from": "2010-01", "pit_feasible": True,
     "assets": ("USDTHB", "XNGUSD"),
     "mechanism_families": ("scheduled_event", "energy_supply", "reserve_margin"),
     "how_to_fetch": "egat.co.th and eppo.go.th announcements plus the Thai press; the window is "
                     "ANNOUNCED IN ADVANCE, which makes it one of the very few scheduled "
                     "physical supply interruptions the desk can align on ex ante"},
    {"name": "Cambodian customs monthly exports by product and destination",
     "source": "GDCE (customs.gov.kh)",
     "coverage": "2010 onward, monthly, garments, footwear, rice, cassava by partner",
     "frequency": "monthly", "publication_lag_days": 25.0, "revisions": "minor",
     "licence": "free, public", "history_from": "2010-01", "pit_feasible": False,
     "assets": ("COTTON", "US500", "USDSGD"),
     "mechanism_families": ("trade_flow", "trade_policy_event", "release_surprise"),
     "how_to_fetch": "customs.gov.kh trade-statistics bulletins, monthly PDFs and workbooks; "
                     "split exports by destination so the EU and US legs can be separated, "
                     "which is what the 2020 EBA partial withdrawal actually acts on"},
    {"name": "National Bank of Cambodia dollarisation share and monetary statistics",
     "source": "NBC", "coverage": "1990s onward; the USD share of deposits and of circulation",
     "frequency": "monthly and annual", "publication_lag_days": 45.0,
     "revisions": "restated in the annual report", "licence": "free, public",
     "history_from": "2000-01", "pit_feasible": False,
     "assets": ("USDSGD", "USDTHB", "US500"),
     "mechanism_families": ("monetary_regime", "natural_experiment", "policy_proxy"),
     "how_to_fetch": "nbc.gov.kh economic research statistics -- the monetary survey and the "
                     "annual report's dollarisation tables; pair with the Bakong volumes, which "
                     "are the measurable half of the de-dollarisation effort"},
    {"name": "Bakong payment-system transaction volumes by currency",
     "source": "NBC / Bakong", "coverage": "2020 onward, riel and dollar legs",
     "frequency": "annual with periodic updates", "publication_lag_days": 60.0,
     "revisions": "none published", "licence": "free, public", "history_from": "2020-10",
     "pit_feasible": False, "assets": ("USDSGD", "US500"),
     "mechanism_families": ("policy_effort", "payments", "natural_experiment"),
     "how_to_fetch": "bakong.nbc.gov.kh and the NBC annual report; the RIEL-DENOMINATED share "
                     "of transactions is the dated measure of whether a central bank can talk a "
                     "dollarised economy back into its own money"},
    {"name": "Mekong River Commission daily water levels by station",
     "source": "Mekong River Commission",
     "coverage": "1960s onward at the long stations; daily readings at Chiang Saen, Luang "
                 "Prabang, Vientiane, Pakse, Stung Treng and downstream",
     "frequency": "daily", "publication_lag_days": 1.0,
     "revisions": "provisional readings are corrected", "licence": "free, public",
     "history_from": "1960-01", "pit_feasible": False,
     "assets": ("USDTHB", "XNGUSD", "USDCNH"),
     "mechanism_families": ("physical_constraint", "high_frequency_proxy", "energy_supply"),
     "how_to_fetch": "portal.mrcmekong.org time-series water-level API by station and date; "
                     "convert each station to a RATIO of its own seasonal median before use -- "
                     "a metre reading is meaningless without that station's datum"},
    {"name": "Lao electricity exports and installed hydro capacity",
     "source": "EDL, EDL-Generation and the Thai offtaker's own import series",
     "coverage": "2010 onward; GWh exported by destination and by project",
     "frequency": "monthly and annual", "publication_lag_days": 45.0,
     "revisions": "restated in annual reports", "licence": "free, public",
     "history_from": "2010-01", "pit_feasible": False,
     "assets": ("USDTHB", "XNGUSD"),
     "mechanism_families": ("energy_supply", "contracted_export", "cross_border_flow"),
     "how_to_fetch": "edlgen.com.la annual and quarterly disclosures plus the Thai import series "
                     "at eppo.go.th; READ BOTH, because the listed generator reports what it "
                     "sold and the buyer reports what it received"},
    {"name": "Lao Statistics Bureau consumer price index",
     "source": "LSB", "coverage": "2000 onward, monthly, by category",
     "frequency": "monthly", "publication_lag_days": 8.0, "revisions": "minor",
     "licence": "free, public", "history_from": "2000-01", "pit_feasible": False,
     "assets": ("USDTHB", "USDCNH", "XAUUSD"),
     "mechanism_families": ("inflation", "currency_passthrough", "macro_release"),
     "how_to_fetch": "lsb.gov.la monthly CPI release; the series exceeded forty per cent "
                     "year-on-year in 2023 and the imported-goods sub-index is where the kip's "
                     "collapse shows first"},
    {"name": "Bank of the Lao PDR reference rate, commercial band and parallel quote",
     "source": "BOL for the first two; the money-changer market for the third",
     "coverage": "the official series from 2010; the parallel quote only where captured",
     "frequency": "daily", "publication_lag_days": 0.0, "revisions": "none",
     "licence": "free, public for the official legs", "history_from": "2010-01",
     "pit_feasible": False, "assets": ("USDTHB", "USDCNH", "XAUUSD"),
     "mechanism_families": ("fx_regime", "rationing", "parallel_market"),
     "how_to_fetch": "bol.gov.la exchange-rate page crawled DAILY (it is overwritten in place) "
                     "for the reference and band; the parallel quote must be captured from the "
                     "changer channels and is USER_SUBMITTED, which the row says rather than "
                     "pretending it is official"},
    {"name": "Lao external debt stock and the amortisation schedule",
     "source": "Lao Ministry of Finance debt bulletin and the World Bank debt statistics",
     "coverage": "2010 onward; the stock by creditor and the forward repayment schedule",
     "frequency": "annual with irregular updates", "publication_lag_days": 180.0,
     "revisions": "restated after each deferral agreement", "licence": "free, public",
     "history_from": "2010-01", "pit_feasible": False,
     "assets": ("USDTHB", "USDCNH", "XAUUSD"),
     "mechanism_families": ("sovereign_credit", "refinancing_event", "external_stress"),
     "how_to_fetch": "mof.gov.la debt bulletins plus the World Bank International Debt "
                     "Statistics tables for the independent check; THE DEFERRALS ARE THE DATED "
                     "EVENTS and the creditor concentration is the mechanism"},
    {"name": "Laos-China Railway freight tonnage and milestones",
     "source": "the railway operator and Chinese state media",
     "coverage": "December 2021 onward, monthly and cumulative",
     "frequency": "monthly and milestone", "publication_lag_days": 10.0,
     "revisions": "cumulative figures restated", "licence": "free, public",
     "history_from": "2021-12", "pit_feasible": False,
     "assets": ("USDCNH", "USDTHB", "CORN"),
     "mechanism_families": ("capacity_step", "logistics", "trade_flow"),
     "how_to_fetch": "the operator's announcements and the Chinese rail bureau releases, "
                     "cross-read with the Lao trade portal; a DATED STEP CHANGE in regional "
                     "freight from 2021-12-03, which is the structural break a study needs"},
    {"name": "Sihanoukville Autonomous Port container throughput",
     "source": "PAS (listed on the CSX)",
     "coverage": "2015 onward, monthly and quarterly TEU and tonnage",
     "frequency": "monthly and quarterly", "publication_lag_days": 30.0,
     "revisions": "restated in the annual report", "licence": "free, public",
     "history_from": "2015-01", "pit_feasible": True,
     "assets": ("COTTON", "US500", "USDSGD"),
     "mechanism_families": ("physical_flow", "trade_flow", "high_frequency_proxy"),
     "how_to_fetch": "pas.gov.kh operational statistics and the CSX disclosure filings; THE "
                     "LISTING IS WHAT MAKES THIS RELIABLE -- a disclosure obligation on a state "
                     "port is the only thing in this pack that audits a physical count"},
    {"name": "Myanmar administered reference rate and the parallel-market quote",
     "source": "CBM for the first; the Yangon changer market for the second",
     "coverage": "the administered rate continuously; the parallel quote only where captured",
     "frequency": "daily", "publication_lag_days": 0.0, "revisions": "none",
     "licence": "free, public for the administered leg", "history_from": "2012-04",
     "pit_feasible": False, "assets": ("USDTHB", "USDCNH", "XAUUSD"),
     "mechanism_families": ("fx_regime", "capital_controls", "parallel_market"),
     "how_to_fetch": "cbm.gov.mm exchange-rate page crawled DAILY for the administered leg; the "
                     "parallel quote from the changer channels, labelled USER_SUBMITTED. NEVER "
                     "SPLICE THE TWO INTO ONE SERIES -- the SPREAD is the object"},
    {"name": "Myanmar rice and agricultural export policy announcements",
     "source": "Myanmar Rice Federation and the Ministry of Commerce",
     "coverage": "2015 onward; licensing changes, reference prices and restrictions",
     "frequency": "irregular, announced", "publication_lag_days": 0.0,
     "revisions": "superseded rather than revised", "licence": "free, public",
     "history_from": "2015-01", "pit_feasible": False,
     "assets": ("CORN", "SOYBEAN", "USDINR"),
     "mechanism_families": ("trade_policy_event", "commodity_supply", "administered_price"),
     "how_to_fetch": "mrf.com.mm and commerce.gov.mm announcement pages plus the exile press, "
                     "which reports restrictions the ministry does not post; the broker quotes "
                     "no rice, so the executable legs are the substitute-calorie complex"},
    {"name": "UN Comtrade partner-reported trade for Myanmar, Cambodia and Laos",
     "source": "UN Comtrade / WITS",
     "coverage": "1990s onward; what every partner declares it traded with each of the three",
     "frequency": "annual with monthly where reported", "publication_lag_days": 300.0,
     "revisions": "restated as reporters file", "licence": "free, public",
     "history_from": "1995-01", "pit_feasible": False,
     "assets": ("USDCNH", "USDTHB", "COTTON"),
     "mechanism_families": ("mirror_statistics", "trade_flow", "reconstruction"),
     "how_to_fetch": "comtradeplus.un.org partner-reported queries with the three as PARTNER "
                     "rather than reporter; THE LAWFUL SUBSTITUTE for a reporter that stopped, "
                     "with a known bias rather than an absence"},
    {"name": "Thai border trade and migrant-labour statistics",
     "source": "Thai customs and the Thai labour ministry",
     "coverage": "2010 onward; border trade by checkpoint and registered migrant workers by "
                 "nationality",
     "frequency": "monthly and quarterly", "publication_lag_days": 40.0,
     "revisions": "minor", "licence": "free, public", "history_from": "2010-01",
     "pit_feasible": False, "assets": ("USDTHB", "USDSGD"),
     "mechanism_families": ("cross_border_flow", "remittance", "labour"),
     "how_to_fetch": "customs.go.th border-trade tables by checkpoint and the labour ministry's "
                     "registered-worker series by nationality; the migrant stock is the "
                     "remittance channel and it is measured in Bangkok, not in Yangon"},
    {"name": "ADB, IMF and World Bank country estimates for the three economies",
     "source": "ADB Asian Development Outlook, IMF Article IV where available, World Bank "
               "Myanmar Economic Monitor and Lao economic updates",
     "coverage": "GDP, inflation, fiscal and external estimates for all three",
     "frequency": "semi-annual and annual", "publication_lag_days": 90.0,
     "revisions": "revised at every publication", "licence": "free, public",
     "history_from": "2000-01", "pit_feasible": True,
     "assets": ("USDTHB", "USDCNH", "XAUUSD"),
     "mechanism_families": ("macro_estimate", "substitute_ground", "sovereign_credit"),
     "how_to_fetch": "adb.org, imf.org and worldbank.org country pages; ESTIMATES WITH A "
                     "PUBLISHED METHOD, labelled as such -- the declared substitute for "
                     "Myanmar's suspended national accounts and vintage-dated because each "
                     "publication is a point-in-time view that can be reconstructed"},
)

# --------------------------------------------------------------------------- actors
#: SIX PER JURISDICTION. A three-country pack that carried twelve actors would be carrying four
#: each, which is not enough to walk the chain Actor -> Constraint -> Observable -> Flow ->
#: MarketImpact -> Candidate in any one of them.
ACTORS: tuple[dict[str, Any], ...] = (
    # ------------------------------------------------------------------ Myanmar
    {"name": "The Yadana and Zawtika gas operators as Thailand's pipeline supplier",
     "holds": "two offshore fields and the cross-border pipelines that deliver their gas into "
              "the Thai power system under long-term contracts",
     "forced_to": ("deliver contracted volumes to the Thai offtaker",
                   "shut the pipeline for maintenance on an announced annual schedule",
                   "pay the Myanmar state its share whatever else is happening onshore",
                   "operate through a partner structure that international sanctions "
                   "repeatedly reshaped"),
     "when": "continuous delivery, with an ANNOUNCED annual maintenance outage window",
     "information": ("the true field decline rate before any regulator sees it",
                     "the outage schedule before it is announced",
                     "the deliverability of the system in a given month"),
     "constraints": ("A PIPELINE HAS NO ALTERNATIVE BUYER: the gas goes to Thailand or it stays "
                     "in the ground, which makes this a bilateral relationship priced by "
                     "contract rather than by a market",
                     "mature fields on a declining production profile",
                     "a sanctions environment that has changed the operator set twice",
                     "an onshore counterparty the international partners cannot always pay"),
     "instruments": ("USDTHB", "XNGUSD", "XBRUSD"),
     "counterparties": ("the Thai offtaker and the Thai power system",
                        "the Myanmar state as resource owner and revenue claimant",
                        "the international partners and their sanctions compliance"),
     "observables": ("Thai gas supply by source, monthly",
                     "the announced maintenance outage windows",
                     "the Thai system operator's reserve-margin statements",
                     "Myanmar's gas export receipts in the partner-reported data"),
     "impact": "a material share of the fuel Thailand burns for power, interrupted on a "
               "SCHEDULE THAT IS PUBLISHED IN ADVANCE -- one of the few physical supply events "
               "on this desk's book that can be aligned on ex ante",
     "persistence": "structural for the life of the fields; the decline profile is slow and the "
                    "contracts are long",
     "falsifier": "the Thai system shows no differential gas or power behaviour in the announced "
                  "outage windows relative to matched weeks, which would mean the reserve margin "
                  "absorbs the outage entirely and the event is fully anticipated",
     "notes": "THE OUTAGE IS SCHEDULED, WHICH CUTS BOTH WAYS: everyone knows it is coming, so "
              "the tradable object is the deviation from the expected replacement cost, not the "
              "outage itself, and MK-A's controls say so"},
    {"name": "The Kachin heavy rare-earth mining zone and the armed group that controls it",
     "holds": "the Chipwi and Pangwa in-situ leaching operations that produce most of the "
               "world's dysprosium and terbium feedstock, and the border crossings into Yunnan "
               "they must pass through",
     "forced_to": ("sell into China, because the separation capacity is there and nowhere else",
                   "cross a border that can be closed by either side",
                   "operate through whichever armed authority holds the ground",
                   "accept a price set in the Chinese domestic market"),
     "when": "continuous truck shipments, punctuated by dated conflict and border-closure events",
     "information": ("the actual stock at the border and in transit",
                     "the state of the leaching operations after a change of control",
                     "the terms the Chinese buyers are offering this week"),
     "constraints": ("THERE IS NO SUBSTITUTE SOURCE AT SCALE, which is what makes a disruption "
                     "here a genuine supply shock rather than a re-routing",
                     "a single buyer country with the only separation capacity",
                     "control of the ground that has changed hands by force",
                     "no domestic statistics of any kind covering the flow"),
     "instruments": ("USDCNH", "XCUUSD", "XNIUSD"),
     "counterparties": ("the Chinese separators and traders in Yunnan",
                        "whichever authority holds the mining zone",
                        "the downstream magnet manufacturers"),
     "observables": ("Chinese customs imports by origin and HS code, monthly",
                     "the dysprosium and terbium oxide price assessments",
                     "dated reports of border closures and changes of control",
                     "Chinese magnet and separator utilisation"),
     "impact": "a supply chain with no substitute, disrupted by dated, reported events; the "
               "2024-2025 change of control and border closure is the natural experiment",
     "persistence": "the geology is permanent and the political control is not; disruptions have "
                    "run from weeks to quarters",
     "falsifier": "the rare-earth price complex shows no differential behaviour around the dated "
                  "closure events once general China-risk and industrial-metals moves are "
                  "controlled for, which would make it a risk story and not a supply story",
     "notes": "NO BROKER CONTRACT EXISTS FOR ANY RARE EARTH. The cells terminate in USDCNH and "
              "the industrial-metals complex with the customs tonnage as the test that "
              "separates a supply event from a sentiment event"},
    {"name": "The Central Bank of Myanmar as the administrator of a two-rate regime",
     "holds": "an administered reference rate, the authority to compel conversion of foreign "
              "currency held onshore, and the licensing of banks and money changers",
     "forced_to": ("allocate scarce foreign exchange administratively rather than by price",
                   "publish a reference rate the market does not transact at",
                   "answer for an import bill it cannot fund at the administered rate",
                   "police a parallel market it has repeatedly tried to close"),
     "when": "directives arrive unscheduled; the reference rate is posted each business day",
     "information": ("the true reserve position, which is not published",
                     "the import-licence queue and who is at the front of it",
                     "the directive before it is issued"),
     "constraints": ("AN ADMINISTERED RATE CREATES THE PARALLEL MARKET IT THEN POLICES, which is "
                     "the central mechanical fact of this jurisdiction",
                     "export earnings that increasingly bypass the formal system",
                     "a banking system under sanctions pressure on its correspondent lines",
                     "no credible tool for expectations at all"),
     "instruments": ("USDTHB", "USDCNH", "XAUUSD"),
     "counterparties": ("the licensed banks and money changers",
                        "importers queuing for allocation",
                        "exporters subject to surrender requirements",
                        "the Chinese and Thai counterparties of the border trade"),
     "observables": ("the administered rate", "the parallel-market quote",
                     "the SPREAD between them, which is the rationing intensity",
                     "each dated directive"),
     "impact": "sets which importers get dollars and at what price, which is the single most "
               "consequential economic decision taken in the country each week",
     "persistence": "the two-rate regime has persisted since 2021 and shows no sign of unifying",
     "falsifier": "the spread adds nothing to a model of Thai border-trade volumes or of "
                  "Myanmar's partner-reported imports once the level of the parallel rate is "
                  "included, which would mean rationing intensity carries no separate signal",
     "notes": "NEVER SPLICE THE TWO RATES INTO ONE SERIES. They coexist and are different "
              "objects; `parallel_spread` computes the only variable with information in it"},
    {"name": "The Myanmar Rice Federation as the export-licence gatekeeper",
     "holds": "the licensing and reference-price machinery for rice exports, and the membership "
              "of the millers and traders who actually ship",
     "forced_to": ("balance domestic price stability against export earnings",
                   "impose restrictions when the domestic price rises",
                   "publish reference prices and volume guidance",
                   "operate inside an FX regime that makes export receipts hard to repatriate"),
     "when": "announcements are irregular and cluster around domestic price spikes and harvests",
     "information": ("mill stocks and the coming harvest before anyone else",
                     "the licence queue", "the domestic price path ahead of the statistics"),
     "constraints": ("DOMESTIC FOOD PRICE IS A POLITICAL VARIABLE and export policy is the "
                     "lever, so an export restriction is a domestic political act that lands on "
                     "a world market",
                     "a two-rate FX regime that taxes the export receipt implicitly",
                     "competition from Thailand, Vietnam and India on the same grades",
                     "border trade that routes around the formal licence system"),
     "instruments": ("CORN", "SOYBEAN", "USDINR"),
     "counterparties": ("Chinese and African buyers", "the domestic millers",
                        "the Ministry of Commerce", "the border traders"),
     "observables": ("announced restrictions and reference prices with dates",
                     "partner-reported import volumes",
                     "the Thai and Indian export quotes as the competing price",
                     "domestic rice prices reported by the press"),
     "impact": "a marginal but real supplier to the world rice market whose policy acts land at "
               "the same moments India's and Thailand's do, which is exactly why the control "
               "matters more than the event",
     "persistence": "episodes last a season; the policy tendency recurs with every price spike",
     "falsifier": "a Myanmar restriction shows no differential effect on the grains and softs "
                  "complex relative to matched weeks once Indian and Thai policy is controlled "
                  "for, which would mean the country is a price taker with no influence at all",
     "notes": "THE BROKER QUOTES NO RICE. The executable legs are the substitute-calorie complex "
              "and USDINR, and the pack states that this weakens the claim rather than hiding it"},
    {"name": "The Yangon money changer as the price the economy actually uses",
     "holds": "the transactable dollar quote, the physical notes, and the messaging channels on "
              "which the day's rate is circulated",
     "forced_to": ("quote continuously against a rate the state says is different",
                   "carry inventory risk in a currency that has fallen a long way",
                   "operate under periodic enforcement campaigns",
                   "serve importers who cannot get an official allocation"),
     "when": "continuously through the Yangon day, with a reference quote settling late morning",
     "information": ("the real order flow hours before any statistic exists",
                     "which importers are desperate this week",
                     "the physical note supply and its condition"),
     "constraints": ("ILLEGAL OR SEMI-LEGAL BY PERIODS, and therefore quoted on channels rather "
                     "than screens, which makes the series capturable only by crawling",
                     "note supply and condition, which creates its own spread",
                     "enforcement raids that clear the market temporarily",
                     "no institution publishes any of it"),
     "instruments": ("USDTHB", "XAUUSD", "USDCNH"),
     "counterparties": ("importers", "households converting savings",
                        "the gold shops, which are the other store of value",
                        "cross-border traders"),
     "observables": ("the daily changer quote on the channels",
                     "the gold price in kyat, which moves with it",
                     "enforcement announcements", "the spread to the administered rate"),
     "impact": "this is the price at which the Myanmar economy actually clears, and the official "
               "one is an administrative statement about a different transaction",
     "persistence": "structural for as long as the two-rate regime lasts",
     "falsifier": "the channel-quoted rate adds nothing to a model of partner-reported Myanmar "
                  "trade once the administered rate and the gold price in kyat are included, "
                  "which would make the channels narrative rather than data",
     "notes": "USER_SUBMITTED AND UNRELIABLE BY LABEL, INDISPENSABLE BY FUNCTION. The pack "
              "carries both judgements because both are true"},
    {"name": "The jade and gemstone trader at the Chinese border",
     "holds": "the Hpakant production, the border stock and the relationships that move it",
     "forced_to": ("sell into China, which is effectively the only market",
                   "move goods across a border that closes",
                   "operate largely outside the formal export statistics",
                   "pay whichever authority controls the mine and the road"),
     "when": "continuous, with seasonal mining and periodic official emporium events",
     "information": ("the real volume crossing, which no statistic captures",
                     "the quality of the season's production",
                     "the Chinese buyer's appetite before it shows in any price"),
     "constraints": ("MOST OF THE TRADE IS INVISIBLE IN EVERY OFFICIAL SERIES, which is the "
                     "measurement: the published emporium receipts are a LOWER BOUND and must "
                     "never be treated as the flow",
                     "one buyer country",
                     "mine control that changes with the conflict",
                     "a currency regime that discourages formal repatriation"),
     "instruments": ("USDCNH", "XAUUSD"),
     "counterparties": ("Chinese buyers and the Ruili border trade",
                        "the mine operators and the armed groups taxing them",
                        "the state emporium when it runs"),
     "observables": ("official emporium receipts, as a lower bound",
                     "Chinese customs gemstone lines",
                     "reported mine closures and landslides",
                     "the Chinese luxury and consumer cycle"),
     "impact": "a large source of foreign exchange that the balance of payments does not see, "
               "which is a first-order caveat on every Myanmar external statistic",
     "persistence": "structural; the informality is the regime, not a phase",
     "falsifier": "the official jade series tracks the Chinese consumer cycle as closely as the "
                  "formal export series do, which would mean the informality is proportional "
                  "and the published number is a usable scaled proxy after all",
     "notes": "carried mainly as a CAVEAT ACTOR: it exists so a miner never reads Myanmar's "
              "official external accounts as complete"},
    # ------------------------------------------------------------------ Cambodia
    {"name": "The National Bank of Cambodia as a central bank without a currency channel",
     "holds": "the riel issue, the official rate, the reserve requirements by currency, the "
              "Bakong payment system and the dollarisation statistics",
     "forced_to": ("publish the dollarisation share it is trying to reduce",
                   "hold the riel stable, because a devaluation in a dollarised economy is a "
                   "redistribution and not a stimulus",
                   "withdraw small-denomination US notes to make room for riel circulation",
                   "supervise a banking system whose deposits are mostly not in its currency"),
     "when": "the official rate daily; the statistics monthly and annually",
     "information": ("the true currency composition of deposits before publication",
                     "the Bakong transaction split before it is reported",
                     "bank FX positions"),
     "constraints": ("AT THIS LEVEL OF DOLLARISATION THERE IS NO INTEREST-RATE CHANNEL AND NO "
                     "EXCHANGE-RATE CHANNEL, so the central bank's real instruments are "
                     "plumbing: note denominations, reserve ratios by currency and a payment "
                     "system",
                     "a public that has chosen the dollar for good historical reasons",
                     "reserves that must back a riel almost nobody saves in",
                     "no domestic bond market of consequence"),
     "instruments": ("USDSGD", "USDTHB", "US500"),
     "counterparties": ("the commercial banks and microfinance institutions",
                        "households holding dollars", "the garment sector's payroll",
                        "the regional correspondent banks"),
     "observables": ("the dollarisation share of deposits and circulation",
                     "Bakong transaction volumes by currency",
                     "the daily official rate and its stability",
                     "reserve requirements by currency"),
     "impact": "runs the cleanest natural experiment in monetary economics available on this "
               "desk's book: what a national currency actually buys a small open economy",
     "persistence": "dollarisation has persisted for three decades and moves slowly in either "
                    "direction; this is a structural object, not a cyclical one",
     "falsifier": "Cambodia's macro volatility is indistinguishable from Laos's and Vietnam's "
                  "over the same shocks once terms of trade and external demand are controlled "
                  "for, which would mean the currency regime bought nothing either way",
     "notes": "THE CONTROLS ARE NAMED AND THEY ARE NEIGHBOURS: Laos, whose float collapsed, and "
              "Vietnam, whose managed rate did not, over the same decade and the same shocks"},
    {"name": "The Cambodian garment factory as the tariff-exposed employer",
     "holds": "the cutting and sewing capacity, the workforce, and the duty-free access to the "
              "EU and US markets that the whole business model rests on",
     "forced_to": ("take orders priced against competitors in Bangladesh and Vietnam",
                   "absorb a minimum-wage negotiation that is annual and political",
                   "import fabric and trim before it can export anything",
                   "live with trade preferences that a foreign government can withdraw"),
     "when": "continuous production with a pronounced order season and an annual wage round",
     "information": ("the order book two quarters ahead of any statistic",
                     "the buyer's sourcing intentions",
                     "the real utilisation of the sector"),
     "constraints": ("PREFERENCE ACCESS IS A FOREIGN POLICY DECISION: the 2020 partial "
                     "withdrawal of Everything But Arms removed duty-free treatment from part "
                     "of the export basket on a DATE, which is a clean policy event",
                     "thin margins that cannot absorb a tariff",
                     "imported inputs, so a China disruption is a Cambodian one",
                     "a dollarised wage bill"),
     "instruments": ("COTTON", "US500", "USDSGD"),
     "counterparties": ("European and American retail buyers",
                        "Chinese and Vietnamese fabric suppliers",
                        "the trade unions and the wage council",
                        "the EU and US trade authorities"),
     "observables": ("monthly customs exports by destination",
                     "the dated EBA and tariff decisions",
                     "the annual minimum-wage settlement",
                     "Sihanoukville container throughput as the physical counterpart"),
     "impact": "the largest formal employer in the country and its single largest source of "
               "foreign exchange; a tariff decision taken in Brussels lands on it directly",
     "persistence": "the sector is structural; each policy episode is dated and bounded",
     "falsifier": "Cambodian export volumes show no differential path after the dated preference "
                  "changes relative to Bangladesh and Vietnam over the same window, which would "
                  "mean the preferences were not binding at the margin",
     "notes": "NO SINGLE NAME APPEARS HERE. The sector is the actor; the executable legs are the "
              "input fibre and the buyer's own market"},
    {"name": "The Sihanoukville Autonomous Port as a listed physical chokepoint",
     "holds": "the country's main deep-water container terminal and, unusually for this region, "
              "a stock-exchange listing that obliges it to disclose",
     "forced_to": ("publish throughput because it is listed",
                   "handle whatever the garment sector ships",
                   "invest ahead of demand under a state development plan",
                   "compete with the Vietnamese ports for transhipment"),
     "when": "continuous operation; monthly and quarterly disclosure",
     "information": ("bookings ahead of the published throughput",
                     "the real berth utilisation",
                     "the mix between transhipment and domestic cargo"),
     "constraints": ("A PORT CANNOT GROW FASTER THAN ITS BERTHS, so throughput is capacity as "
                     "much as demand and the two must be separated",
                     "a road and rail hinterland that is thin",
                     "competition from the Vietnamese deep-water ports",
                     "a listing that makes the numbers public but also makes them managed"),
     "instruments": ("COTTON", "US500", "USDSGD"),
     "counterparties": ("the shipping lines", "the garment exporters",
                        "the state as majority owner", "the CSX and its investors"),
     "observables": ("monthly and quarterly TEU and tonnage",
                     "the CSX disclosure filings",
                     "capacity expansion milestones",
                     "the customs export series it should track"),
     "impact": "the physical counterpart of Cambodia's export statistics, and the one series in "
               "this pack audited by a disclosure obligation",
     "persistence": "structural; the capacity steps are dated and permanent",
     "falsifier": "port throughput adds nothing to a nowcast of the monthly customs export value "
                  "once the prior month's exports are known, which would make it a lagging "
                  "confirmation rather than a leading physical read",
     "notes": "THE LISTING IS WHY THIS IS RELIABLE. It is the only place in the pack where a "
              "legal obligation audits a physical count"},
    {"name": "The Cambodian rice and cassava farmer as a cross-border crop seller",
     "holds": "paddy and cassava grown on smallholdings within a day's truck ride of the Thai "
              "and Vietnamese borders",
     "forced_to": ("sell wet paddy at harvest because storage and drying capacity are short",
                   "accept whatever the cross-border buyer offers on the day",
                   "borrow against the next crop from microfinance lenders",
                   "compete with Thai and Vietnamese farmers with better milling behind them"),
     "when": "the wet-season harvest concentrates the selling into a few weeks",
     "information": ("the local crop condition months before any statistic",
                     "the price the Thai and Vietnamese buyers are paying at the border today",
                     "the state of the household's debt"),
     "constraints": ("MILLING AND DRYING CAPACITY IS THE BINDING CONSTRAINT, not the crop: "
                     "unmilled paddy leaves the country and is milled and exported by a "
                     "neighbour, so Cambodian production shows up in somebody else's exports",
                     "microfinance debt that forces selling at the worst moment",
                     "border measures the neighbours impose on informal crop flows",
                     "a dollarised input cost against a riel-priced local sale"),
     "instruments": ("CORN", "SUGAR", "SOYBEAN"),
     "counterparties": ("Thai and Vietnamese millers and starch factories",
                        "the domestic millers and the Cambodia Rice Federation",
                        "the microfinance lenders"),
     "observables": ("customs exports of milled rice and cassava by destination",
                     "Thai and Vietnamese import statistics for the same crops",
                     "the border price reported in the press",
                     "the wet-season rainfall and the Mekong flood pulse"),
     "impact": "moves real volumes of starch and calories into the Thai and Vietnamese "
               "processing chain, and is the rural income channel the domestic economy runs on",
     "persistence": "seasonal within a year and structural across years",
     "falsifier": "Cambodian crop flows add nothing to Thai and Vietnamese milling or starch "
                  "output once their own domestic harvests are controlled for, which would mean "
                  "the cross-border volume is immaterial to the buyer",
     "notes": "the broker quotes no rice and no cassava; the cells terminate in the "
              "substitute-calorie and starch complex with the acreage-competition control named"},
    {"name": "The Cambodian and Burmese migrant worker in Thailand as the remittance channel",
     "holds": "the labour that staffs Thai construction, fishing, agriculture and food "
              "processing, and a remittance flow that is large relative to both home economies",
     "forced_to": ("remit in Thai baht through formal and informal channels",
                   "renew work permits on a Thai administrative cycle",
                   "return home for the mid-April new year, en masse",
                   "absorb whatever the baht does against a home currency they cannot hedge"),
     "when": "continuous, with a very large seasonal return around the simultaneous April week",
     "information": ("their own employment prospects before any statistic",
                     "the informal transfer rate available this week",
                     "the state of the Thai labour demand they serve"),
     "constraints": ("THE REMITTANCE IS PRICED IN BAHT AND SPENT IN A CURRENCY THAT MOVES, so "
                     "the home-currency value of the same work changes with USDTHB and with the "
                     "home parallel rate at the same time",
                     "Thai permit policy, which has tightened and loosened repeatedly",
                     "informal channels that no statistic captures",
                     "a home labour market that cannot absorb a return"),
     "instruments": ("USDTHB", "XAUUSD", "USDSGD"),
     "counterparties": ("Thai employers", "the informal transfer networks",
                        "the home households receiving", "the Thai labour ministry"),
     "observables": ("registered migrant workers by nationality, quarterly",
                     "Thai border crossing counts around the April week",
                     "formal remittance series where they exist",
                     "the baht against the home parallel rates"),
     "impact": "one of the largest external income flows into both Myanmar and Cambodia and "
               "almost entirely invisible in either country's own statistics",
     "persistence": "structural; the wage gap that drives it has not narrowed",
     "falsifier": "home-country consumption and import series show no differential response to "
                  "large baht moves once commodity terms of trade are controlled for, which "
                  "would mean the remittance channel is too small or too smoothed to measure",
     "notes": "MEASURED FROM BANGKOK, NOT FROM YANGON OR PHNOM PENH -- another case where the "
              "counterparty's statistics are the only ones that exist"},
    {"name": "The Cambodia Securities Exchange and the state asset programme",
     "holds": "a handful of listings dominated by state infrastructure -- the port, the water "
               "utility, a telecom -- and the disclosure obligations that come with them",
     "forced_to": ("require periodic disclosure from its listed state entities",
                   "operate a market too thin to price anything",
                   "list what the government decides to list"),
     "when": "daily sessions; listings when the state announces them",
     "information": ("the listing pipeline before announcement",
                     "the order book, which nobody outside sees",
                     "the disclosure filings before publication"),
     "constraints": ("TURNOVER TOO SMALL TO PRICE ANYTHING, so a listing here is a DISCLOSURE "
                     "EVENT rather than a valuation event",
                     "no derivatives and no hedging",
                     "a domestic investor base that is small and dollarised",
                     "foreign participation that is negligible"),
     "instruments": ("US500", "USDSGD"),
     "counterparties": ("the listed state entities", "domestic retail and institutional buyers",
                        "the securities regulator"),
     "observables": ("the port's throughput disclosures",
                     "listing announcements and their terms",
                     "daily turnover, for completeness",
                     "the regulator's filings"),
     "impact": "ZERO AS A PRICE AND REAL AS AN INFORMATION SOURCE: the port's numbers exist "
               "because of this exchange, and that is its entire value to the pack",
     "persistence": "the venue is permanent and the listing programme is episodic",
     "falsifier": "CSX turnover or the index adds anything at all to a model of the executable "
                  "legs, which would be a genuine surprise given the size and would need "
                  "replication before it was believed",
     "notes": "declared non-executable IN ADVANCE so a miner reports the absence by name rather "
              "than discovering it as a silent failure (L1.28a)"},
    # ------------------------------------------------------------------ Laos
    {"name": "The Lao hydropower concessionaire as a contracted exporter of electricity",
     "holds": "a dam, a concession agreement and a long-term power purchase agreement with a "
              "foreign utility that fixes the tariff for decades",
     "forced_to": ("generate whatever the water allows and sell it at a contracted tariff",
                   "service project debt denominated in a currency it does not earn its costs in",
                   "meet availability obligations in the PPA",
                   "spill water it cannot sell when the offtaker does not dispatch"),
     "when": "continuous generation with a pronounced wet and dry season",
     "information": ("reservoir storage and inflow before any public reading",
                     "the dispatch instruction from the offtaker",
                     "its own debt service coverage"),
     "constraints": ("A CONTRACTED PRICE MEANS THE ONLY VARIABLE IS THE WATER, and the water is "
                     "published daily by station, which is an unusually clean setup",
                     "project debt on a fixed schedule against a variable resource",
                     "an offtaker whose dispatch decisions it does not control",
                     "an upstream cascade whose operation it does not control either"),
     "instruments": ("USDTHB", "XNGUSD", "USDCNH"),
     "counterparties": ("the Thai, Vietnamese and Cambodian offtakers",
                        "the project lenders, largely Chinese and Thai",
                        "the Lao state as concession grantor and shareholder"),
     "observables": ("MRC daily station levels and the seasonal median",
                     "the Thai import-of-electricity series",
                     "the listed generator's quarterly disclosures",
                     "announced commissioning and outage events"),
     "impact": "Laos's principal export, contracted and non-traded, with a daily published "
               "physical bound on its volume",
     "persistence": "the concessions run for decades; the hydrology varies year to year",
     "falsifier": "Thai electricity imports from Laos show no differential response to Mekong "
                  "station levels once seasonality is removed, which would mean storage and "
                  "cascade operation fully buffer the flow and the daily series is not binding",
     "notes": "THE ASYMMETRY MATTERS: low water bounds output from above, high water does not "
              "raise a contracted volume beyond capacity, so `hydro_bound` models the two tails "
              "differently and a symmetric specification would be wrong"},
    {"name": "The Mekong River Commission as the publisher of the physical constraint",
     "holds": "an intergovernmental monitoring network and the daily water-level and flow "
              "readings at stations from Chiang Saen down to the delta",
     "forced_to": ("publish daily station readings under its own agreements",
                   "report basin conditions without enforcement power over any member",
                   "reconcile upstream operation it does not control with downstream impact"),
     "when": "daily readings; periodic technical and state-of-basin reports",
     "information": ("the basin's condition before any government comments on it",
                     "the discrepancy between expected and observed flow, which is upstream "
                     "operation made visible",
                     "the quality flags on each provisional reading"),
     "constraints": ("A MONITOR WITH NO AUTHORITY: it measures and publishes and cannot direct "
                     "a single reservoir, which is why its data is credible and its influence "
                     "is not",
                     "gauge networks with gaps and provisional readings",
                     "upstream operation outside its membership"),
     "instruments": ("USDTHB", "XNGUSD", "USDCNH"),
     "counterparties": ("the member governments", "the dam operators",
                        "the downstream fisheries and agriculture", "the research community"),
     "observables": ("daily levels and flows by station",
                     "the deviation from each station's seasonal median",
                     "the technical reports on flow alteration",
                     "flood and drought declarations"),
     "impact": "produces the only daily physical series in this pack, and the one that makes "
               "Lao generation a measurable rather than a narrative object",
     "persistence": "permanent as an institution; the network has been running for decades",
     "falsifier": "station levels add nothing to a model of Lao electricity exports or of Thai "
                  "hydro imports beyond calendar seasonality, which would make the daily series "
                  "redundant with a seasonal dummy",
     "notes": "THE DECLARED SUBSTITUTE for Laos's absent academic layer: an intergovernmental "
              "body with a published method and a daily network beats a faculty that does not "
              "exist"},
    {"name": "The Bank of the Lao PDR as a central bank in a currency crisis",
     "holds": "the reference rate, the permitted commercial-bank band, the reserve requirements "
              "and a reserve stock that is small against the import bill",
     "forced_to": ("publish a reference rate the parallel market does not respect",
                   "ration foreign exchange to fuel and essential imports",
                   "fund an external debt service it cannot decline",
                   "watch imported inflation run through a halved currency"),
     "when": "the rates daily; policy actions when the pressure forces them",
     "information": ("the true reserve position and its usable share",
                     "the FX allocation queue, especially for fuel importers",
                     "bank FX positions before they are reported"),
     "constraints": ("EXTERNAL DEBT SERVICE IS THE BINDING CONSTRAINT AND NOT INFLATION, which "
                     "inverts the usual policy reaction function and is the single most "
                     "important thing to know before modelling this central bank",
                     "a dollarised and baht-ised domestic economy alongside the kip",
                     "reserves measured in weeks of imports at the worst moments",
                     "a creditor concentration that makes bilateral deferral the main tool"),
     "instruments": ("USDTHB", "USDCNH", "XAUUSD"),
     "counterparties": ("the commercial banks", "the fuel importers",
                        "the Chinese creditors", "the Thai baht economy next door"),
     "observables": ("the reference rate, the commercial band and the parallel quote",
                     "the CPI, which exceeded forty per cent year-on-year in 2023",
                     "fuel shortages reported in the press",
                     "announced deferral agreements"),
     "impact": "determines whether the country can import fuel, which is upstream of everything "
               "else in the domestic economy",
     "persistence": "the stress has run for years and the structural cause -- the debt -- has "
                    "not been resolved, only deferred",
     "falsifier": "the three Lao rates and the CPI add nothing to a model of the executable legs "
                  "beyond what the regional dollar cycle explains, which is the honest prior for "
                  "a currency nobody can trade and is what MK-I is there to measure",
     "notes": "THE HONEST PRIOR IS A NULL AT THE EXECUTABLE LEG and a first-order fact "
              "domestically; the pack says so in advance so a null is not reported as news"},
    {"name": "The Lao Ministry of Finance as the region's most debt-distressed sovereign",
     "holds": "a budget dominated by debt service, an external debt stock concentrated in "
              "Chinese lending, and the concession agreements that created both",
     "forced_to": ("service or defer a schedule it cannot fund from revenue",
                   "publish a debt bulletin the multilaterals will check",
                   "negotiate bilateral deferrals rather than a market restructuring",
                   "fund a state whose tax base is small and largely informal"),
     "when": "the budget annually; deferral agreements when they are reached",
     "information": ("the real terms of each bilateral deferral, which are not fully published",
                     "the cash position ahead of a payment date",
                     "the state enterprises' contingent liabilities"),
     "constraints": ("BILATERAL CONCENTRATION MEANS THERE IS NO MARKET RESTRUCTURING AVAILABLE: "
                     "the outcome is negotiated with one creditor, which makes the process "
                     "opaque and the dates irregular",
                     "assets pledged against the debt that created them",
                     "a revenue base that hydropower royalties dominate",
                     "an exchange rate that raises the local-currency cost of every payment"),
     "instruments": ("USDTHB", "USDCNH", "XAUUSD"),
     "counterparties": ("the Chinese policy banks", "the multilateral lenders",
                        "the state power utility", "the domestic banking system"),
     "observables": ("the debt bulletin and the World Bank debt statistics",
                     "announced deferrals with dates",
                     "the budget's debt-service line",
                     "the kip's path around payment dates"),
     "impact": "the clearest live small-open-economy debt-and-currency stress case in the region, "
               "with a published schedule and dated interventions",
     "persistence": "years; the deferrals move the problem rather than resolving it",
     "falsifier": "the executable legs show no differential behaviour around announced deferral "
                  "dates relative to matched windows, which would mean the sovereign is too "
                  "small and too bilateral for any market to price",
     "notes": "there is no tradable Lao instrument of any kind; this actor's cells terminate in "
              "the regional legs and the pack states that as a weakened claim"},
    {"name": "The Laos-China Railway as a dated freight step change",
     "holds": "a standard-gauge line from the Chinese border to Vientiane, opened in December "
              "2021, and the cross-border freight interchange that came with it",
     "forced_to": ("publish freight and passenger milestones",
                   "interchange with the Thai network at a break of gauge",
                   "earn a return on debt that the Lao state partly guaranteed",
                   "compete with road haulage and with the sea route"),
     "when": "continuous operation since 2021-12-03, with monthly and milestone reporting",
     "information": ("real wagon availability and cycle times",
                     "the commodity mix actually moving",
                     "the tariff being charged against the road alternative"),
     "constraints": ("A GAUGE BREAK AT THE SOUTHERN END limits the through-route to Thailand and "
                     "caps how much of the promised transit actually materialises",
                     "capital cost carried by a sovereign that cannot service it",
                     "a road industry it displaces",
                     "freight volumes that must be built rather than assumed"),
     "instruments": ("USDCNH", "USDTHB", "CORN"),
     "counterparties": ("Chinese shippers and the Chinese rail network",
                        "Lao and Thai exporters", "the Lao state as part-owner and guarantor"),
     "observables": ("monthly freight tonnage and cumulative milestones",
                     "the commodity mix of what moves",
                     "Thai and Lao border trade over the same months",
                     "the Chinese border-station throughput"),
     "impact": "a permanent, dated step in regional freight capacity between China and the "
               "northern Mekong -- the cleanest structural break in this pack",
     "persistence": "permanent; a capacity step does not reverse",
     "falsifier": "regional trade volumes show no level shift at the 2021-12-03 opening once the "
                  "pandemic reopening path is controlled for, which would mean the line "
                  "substituted for road and sea freight without adding any",
     "notes": "THE CONTROL PROBLEM IS THE OPENING DATE: it sits inside the pandemic window, so "
              "any naive level-shift test is measuring reopening and calling it rail"},
    {"name": "The Lao mining and agricultural exporter as the second export leg",
     "holds": "copper and gold mines, potash projects, coffee plantations and the banana and "
               "cassava plantations that Chinese and Vietnamese buyers contract",
     "forced_to": ("export nearly everything, because the domestic market is tiny",
                   "sell into China, Thailand and Vietnam",
                   "operate under concession terms the state can revisit",
                   "pay costs in a currency that has halved while earning in dollars"),
     "when": "continuous for mining; seasonal for the crops",
     "information": ("mine grades and production before any publication",
                     "the contracted offtake terms",
                     "the crop condition ahead of the harvest"),
     "constraints": ("A LANDLOCKED EXPORTER PAYS FOR EVERY KILOMETRE, so the transport cost -- "
                     "road, and now rail -- is a first-order determinant of what is worth "
                     "digging or growing at all",
                     "a small number of buyers across two borders",
                     "concession terms that are periodically renegotiated",
                     "environmental and land-use constraints on plantation expansion"),
     "instruments": ("XCUUSD", "USDCNH", "SUGAR"),
     "counterparties": ("Chinese, Thai and Vietnamese buyers",
                        "the state as concession grantor and royalty claimant",
                        "the rail and road hauliers"),
     "observables": ("partner-reported imports from Laos by commodity",
                     "the Lao trade portal's own export tables",
                     "mine production announcements",
                     "rail freight commodity mix"),
     "impact": "the country's second export leg after electricity, and the one that gives the "
               "industrial-metals complex a Lao reading at all",
     "persistence": "structural; the deposits and the plantations are long-lived",
     "falsifier": "Lao mineral and crop volumes add nothing to the industrial-metals or softs "
                  "complex beyond what the Chinese import cycle already explains, which is the "
                  "expected result at this scale and is declared in advance",
     "notes": "SMALL AT WORLD SCALE AND FIRST-ORDER DOMESTICALLY -- the same shape as the "
              "Mongolian gold programme, and treated with the same honest prior"},
)

# --------------------------------------------------------------------------- domains
DOMAINS: tuple[dict[str, Any], ...] = (
    {"id": "MK-A", "title": "Myanmar pipeline gas inside the Thai power system",
     "objects": ("Thai gas supply by source with the Myanmar import line separated",
                 "the ANNOUNCED annual pipeline maintenance outage windows",
                 "the Thai system operator's reserve-margin statements in those windows",
                 "the substitute fuel Thailand burns when the pipeline is down"),
     "conditions": ("whether the window contains an announced pipeline outage",
                    "the Thai reserve margin bucket going into the window",
                    "whether the outage was extended beyond its announced length"),
     "instruments": ("USDTHB", "XNGUSD", "XBRUSD"),
     "controls": ("matched weeks with no announced outage and the same seasonal power demand, "
                  "which is the base rate",
                  "the `th` pack's own power and gas study over the identical window, so a "
                  "Myanmar claim must beat Thailand's own measurement of its own system",
                  "outages of Thai domestic fields of comparable size, which separates 'a gas "
                  "supply interruption' from 'a MYANMAR gas supply interruption'"),
     "notes": "THE OUTAGE IS ANNOUNCED IN ADVANCE, so the level is known and only the DEVIATION "
              "can carry information: an unplanned extension or a reserve margin that turns out "
              "tighter than expected. A study on the scheduled window alone is testing whether "
              "the market can read a published calendar"},
    {"id": "MK-B", "title": "Kachin heavy rare earths read through Chinese customs",
     "objects": ("Chinese customs rare-earth imports from Myanmar by HS code and month",
                 "the dated changes of control and border closures in the Chipwi and Pangwa zone",
                 "the dysprosium and terbium oxide price assessments (registered, not scraped)",
                 "Chinese separator and magnet utilisation as the downstream demand check"),
     "conditions": ("whether the month contained a reported border closure or change of control",
                    "the import tonnage relative to its trailing twelve-month mean",
                    "whether the Chinese downstream was expanding or contracting at the time"),
     "instruments": ("USDCNH", "XCUUSD", "XNIUSD"),
     "controls": ("matched months with no reported disruption, which is the base rate",
                  "the general China-risk complex over the same days, because a rare-earth "
                  "headline arrives inside a news environment that moves everything",
                  "THE CUSTOMS TONNAGE ITSELF as the physical test: a disruption that never "
                  "shows up as a fall in imports is a sentiment event and must be labelled one"),
     "notes": "NO SUBSTITUTE SOURCE AT SCALE, which is what makes this a real supply mechanism "
              "rather than a re-routing story -- and NO BROKER CONTRACT, which is what makes "
              "every cell here a weakened claim routed through the metals complex"},
    {"id": "MK-C", "title": "The two-rate kyat and the parallel-market spread",
     "objects": ("the administered reference rate",
                 "the parallel-market quote from the changer channels",
                 "the proportional spread and its rationing bucket from `parallel_spread`",
                 "the dated directives -- forced conversion, surrender requirements, licensing"),
     "conditions": ("the rationing bucket the spread sits in",
                    "whether a new directive was issued in the window",
                    "the direction of the spread's change over the prior month"),
     "instruments": ("USDTHB", "USDCNH", "XAUUSD"),
     "controls": ("the same buckets measured in a neighbouring FLOATING economy with no "
                  "administered rate, which separates 'the currency fell' from 'the state "
                  "rationed harder'",
                  "matched windows with no directive at all",
                  "the gold price in kyat, which is the domestic store-of-value channel and "
                  "must be removed before any external claim is made"),
     "notes": "NEVER SPLICE THE TWO RATES. They are two objects that coexist, not one series "
              "over time, and the only variable with information in it is the distance between "
              "them; a level study on either leg alone is measuring the wrong thing"},
    {"id": "MK-D", "title": "Myanmar rice policy inside the world grain complex",
     "objects": ("announced export restrictions, licensing changes and reference prices",
                 "partner-reported import volumes as the only reliable quantity",
                 "the Thai and Indian export quotes as the competing price",
                 "domestic rice prices reported by the press"),
     "conditions": ("whether a restriction was announced or lifted in the window",
                    "whether India or Thailand acted in the same window",
                    "the domestic price's deviation from its trailing year"),
     "instruments": ("CORN", "SOYBEAN", "USDINR"),
     "controls": ("INDIAN AND THAI POLICY OVER THE SAME WINDOW, which is the control that "
                  "matters most: these acts cluster, and a naive event study attributes the "
                  "largest exporter's decision to the smallest one",
                  "matched windows with no policy action anywhere",
                  "the broader grains complex, which must be removed before any rice-specific "
                  "claim is made at all"),
     "notes": "THE BROKER QUOTES NO RICE. Every cell here terminates in a substitute crop, "
              "which is a materially weaker claim and is stated rather than disguised"},
    {"id": "MK-E", "title": "Cambodian dollarisation as a natural experiment",
     "objects": ("the published USD share of deposits and of circulation",
                 "the NBC's riel-promotion operations, including the small-note withdrawal",
                 "Bakong transaction volumes by currency",
                 "Cambodian macro volatility against Laos's and Vietnam's over the same shocks"),
     "conditions": ("the dollarisation bucket from `dollarisation_state`",
                    "whether a riel-promotion measure was active in the window",
                    "whether the window contained a regional external shock all three faced"),
     "instruments": ("USDSGD", "USDTHB", "US500"),
     "controls": ("LAOS, whose float lost more than half its value over the same years",
                  "VIETNAM, whose managed rate did not, over the same shocks",
                  "the terms of trade and external demand common to all three, which must be "
                  "removed before any currency-regime claim is made"),
     "notes": "THE CLEANEST NATURAL EXPERIMENT ON THIS DESK'S BOOK about what a national "
              "currency buys a small open economy -- three neighbours, three regimes, one "
              "decade, the same shocks, and all three published"},
    {"id": "MK-F", "title": "Cambodian garment exports and the dated trade-policy calendar",
     "objects": ("monthly customs exports by destination, EU and US separated",
                 "the dated preference and tariff decisions, including the 2020 EBA partial "
                 "withdrawal",
                 "the annual minimum-wage settlement",
                 "the competing exporters' volumes over the same months"),
     "conditions": ("whether a preference or tariff decision took effect in the window",
                    "the EU share of the export basket going in",
                    "whether the window contained the annual wage settlement"),
     "instruments": ("COTTON", "US500", "USDSGD"),
     "controls": ("BANGLADESH AND VIETNAM over the same window, which separates 'Cambodian "
                  "access changed' from 'global apparel demand changed'",
                  "matched windows with no policy decision",
                  "the buyer's own demand, read through US500, which must be removed before any "
                  "supply-side access claim is made"),
     "notes": "A FOREIGN GOVERNMENT'S DECISION WITH A PUBLISHED EFFECTIVE DATE acting on a "
              "single country's export basket is about as clean a policy event as trade data "
              "offers, and the competitor control is what makes it interpretable"},
    {"id": "MK-G", "title": "Sihanoukville throughput as the audited physical series",
     "objects": ("monthly and quarterly TEU and tonnage from the listed port",
                 "the CSX disclosure filings behind them",
                 "the customs export series the throughput should track",
                 "dated capacity expansion milestones"),
     "conditions": ("the throughput's deviation from its trailing twelve-month path",
                    "whether a capacity milestone fell in the window",
                    "the sign of the wedge between throughput and the customs export value"),
     "instruments": ("COTTON", "US500", "USDSGD"),
     "controls": ("the Vietnamese deep-water ports over the same months, which separates 'trade "
                  "moved' from 'this port moved it'",
                  "the capacity milestones themselves, because throughput is capacity as much "
                  "as demand",
                  "the prior month's customs exports, which any leading claim must beat"),
     "notes": "THE ONLY SERIES IN THIS PACK AUDITED BY A DISCLOSURE OBLIGATION. That is worth "
              "saying because everywhere else in the Mekong the physical count is somebody's "
              "unverified statement"},
    {"id": "MK-H", "title": "Laos as the region's battery, bounded by the river",
     "objects": ("MRC daily station levels expressed as a ratio of each station's seasonal "
                 "median",
                 "Lao electricity exports by destination and the Thai import series beside them",
                 "the listed generator's quarterly disclosures",
                 "the Thai system's substitute gas burn when hydro is short"),
     "conditions": ("the hydro bucket from `hydro_bound` at the reference station",
                    "whether the constraint BINDS -- the drought tail, not the flood tail",
                    "the season: wet, dry or the transition"),
     "instruments": ("USDTHB", "XNGUSD", "USDCNH"),
     "controls": ("the same season in years with normal flow, which is the base rate",
                  "the Thai system's own gas burn, which is where the substitution lands and "
                  "which must move in the opposite direction for the mechanism to be real",
                  "upstream reservoir operation, which can buffer or amplify a natural flow and "
                  "is not the same object as rainfall"),
     "notes": "THE ASYMMETRY IS THE MODELLING CLAIM: low water bounds output from above and "
              "high water does not raise a contracted volume beyond capacity, so a symmetric "
              "specification is wrong by construction"},
    {"id": "MK-I", "title": "Lao debt distress, the kip and forty per cent inflation",
     "objects": ("the reference rate, the commercial band and the parallel quote",
                 "the CPI, which exceeded forty per cent year-on-year in 2023",
                 "the external debt stock by creditor and the amortisation schedule",
                 "announced bilateral deferrals with their dates"),
     "conditions": ("the parallel spread's rationing bucket",
                    "the distance in weeks to a known external payment date",
                    "whether a deferral was announced in the window"),
     "instruments": ("USDTHB", "USDCNH", "XAUUSD"),
     "controls": ("matched windows with no payment date approaching",
                  "the regional dollar cycle, which must be removed before any Lao-specific "
                  "claim is made",
                  "CAMBODIA as the dollarised control and VIETNAM as the managed-rate control "
                  "over the same external shocks"),
     "notes": "THE HONEST PRIOR IS A NULL AT THE EXECUTABLE LEG. A currency nobody can trade in "
              "an economy this size should not move USDTHB, and this domain exists to MEASURE "
              "that rather than assume it; a positive result would be the surprise"},
    {"id": "MK-J", "title": "The Laos-China Railway as a dated freight step",
     "objects": ("monthly freight tonnage and the cumulative milestones since 2021-12-03",
                 "the commodity mix actually moving",
                 "Thai and Lao border trade over the same months",
                 "the Chinese border-station throughput"),
     "conditions": ("pre-opening, the opening year, or the post-2023 operating era",
                    "the rail share of the Laos-China trade in the month",
                    "whether the commodity mix shifted toward agricultural or mineral cargo"),
     "instruments": ("USDCNH", "USDTHB", "CORN"),
     "controls": ("THE PANDEMIC REOPENING PATH, because the line opened inside that window and "
                  "a naive level-shift test is measuring reopening and calling it rail",
                  "the road and sea freight volumes over the same months",
                  "a placebo step placed at a random date in the same period"),
     "notes": "the cleanest structural break in the pack and the one most at risk of being "
              "measured wrong, because its date sits inside a much larger regional shock"},
    {"id": "MK-K", "title": "The mid-April week in which four economies stop together",
     "objects": ("Thingyan, Chaul Chnam Thmey and Pi Mai, computed by `new_year_week`",
                 "Thai Songkran in the same window, owned by the `th` pack",
                 "the number of jurisdictions closed on each day of the block",
                 "the Theravada full moons that close all three of this pack's countries at once"),
     "conditions": ("the maximum number of jurisdictions simultaneously closed in the window",
                    "how many of the block's days cost a weekday session",
                    "whether the window is the April block or a shared full-moon closure"),
     "instruments": ("USDTHB", "COTTON", "USDSGD"),
     "controls": ("matched weeks in the same month with no closure",
                  "a SINGLE-COUNTRY closure elsewhere in the year, which is the placebo that "
                  "separates a regional stoppage from a national one",
                  "the Thai leg measured on its own by the `th` pack, which any regional claim "
                  "must beat"),
     "notes": "THE SIMULTANEITY IS THE MECHANISM. Four economies stopping in one week is a "
              "different object from four separate holidays, and a single-country study on this "
              "window is measuring a quarter of the event"},
    {"id": "MK-L", "title": "The measured statistical vacuum and its lawful substitutes",
     "objects": ("the per-jurisdiction gap table in `NO_LAWFUL_GROUND`",
                 "partner-reported mirror statistics as the declared substitute",
                 "the ADB, IMF and World Bank estimates and their published methods",
                 "the divergence between an estimate and the mirror data it is built from"),
     "conditions": ("whether the jurisdiction's own official series exists for the window",
                    "whether the substitute is a MIRROR MEASUREMENT or a MODELLED ESTIMATE",
                    "the size of the gap between the substitute and any surviving domestic print"),
     "instruments": ("USDTHB", "USDCNH", "XAUUSD"),
     "controls": ("a jurisdiction in the same region whose own statistics DO exist, which "
                  "calibrates how large a mirror-versus-domestic gap normally is",
                  "the same substitute applied to a period when the domestic series still "
                  "existed, which is the only way to measure the substitute's bias",
                  "matched windows with no data event at all"),
     "notes": "THIS DOMAIN IS THE MEASURED REFUSAL MADE TESTABLE. It exists because the correct "
              "answer to 'what was Myanmar's GDP last quarter' is UNMEASURED with a named "
              "substitute, and the substitute's BIAS is itself a research object (L1.28a)"},
    {"id": "MK-M", "title": "Cross-border crops into the Thai and Vietnamese processing chain",
     "objects": ("Cambodian and Lao rice, cassava, maize and sugar exports by destination",
                 "Thai and Vietnamese import and milling statistics for the same crops",
                 "the Mekong flood pulse that sets the wet-season crop",
                 "the border price reported in the press ahead of any statistic"),
     "conditions": ("the harvest phase: pre-harvest, the concentrated selling weeks, or "
                    "post-harvest",
                    "the flood-pulse condition from the MRC stations that season",
                    "whether a neighbour imposed a border measure on informal crop flows"),
     "instruments": ("CORN", "SUGAR", "SOYBEAN"),
     "controls": ("the neighbours' own domestic harvests, which must be removed before any "
                  "cross-border volume claim is made",
                  "matched seasons with normal flood pulse",
                  "the world grains complex, because a Mekong crop event that moves CORN the "
                  "same way a US balance-sheet revision does is a grains event, not a Mekong one"),
     "notes": "UNMILLED PADDY LEAVES THE COUNTRY AND IS EXPORTED BY A NEIGHBOUR, so a Cambodian "
              "crop can appear in Vietnamese or Thai export statistics; the mirror pair is the "
              "only way to see the real flow"},
)

# --------------------------------------------------------------------------- cells
#: WHAT EACH DOMAIN MINTS. The horizon and mechanism family a cell inherits from its domain, so
#: a cell is never a cartesian product of nothing: every row below is one real condition this
#: pack's own data plane can evaluate against one symbol the box can actually trade.
DOMAIN_CELL_SPEC: dict[str, tuple[str, str]] = {
    "MK-A": ("energy_supply", "0 to 10 sessions"),
    "MK-B": ("supply_disruption", "1 to 3 months"),
    "MK-C": ("capital_controls", "1 to 20 sessions"),
    "MK-D": ("trade_policy_event", "1 to 2 quarters"),
    "MK-E": ("monetary_regime", "1 to 4 quarters"),
    "MK-F": ("trade_policy_event", "1 to 3 months"),
    "MK-G": ("physical_flow", "1 to 3 months"),
    "MK-H": ("physical_constraint", "1 to 20 sessions"),
    "MK-I": ("sovereign_credit", "1 to 2 quarters"),
    "MK-J": ("capacity_step", "1 to 4 quarters"),
    "MK-K": ("calendar_event", "0 to 5 sessions"),
    "MK-L": ("measured_absence", "1 to 4 quarters"),
    "MK-M": ("commodity_supply", "1 to 3 months"),
}


def cells() -> tuple[dict[str, Any], ...]:
    """THE TESTABLE CELLS THIS PACK MINTS, for the one gauntlet.

    The cross product of each domain's own conditions with each domain's own EXECUTABLE
    instruments. It is a product and not a blow-up because both factors are already the pack's
    measured claims: a condition is a state this pack's data plane can evaluate, and an
    instrument is a symbol the broker registry carries. A domain that names three conditions and
    three instruments is claiming nine testable statements, and the pack writes all nine down
    rather than testing one and calling three countries covered.
    """
    execs = set(EXECUTABLE_INSTRUMENTS)
    out: list[dict[str, Any]] = []
    for dom in DOMAINS:
        did = str(dom["id"])
        family, horizon = DOMAIN_CELL_SPEC.get(did, ("mechanism", "1 to 10 sessions"))
        controls = tuple(dom["controls"])
        for symbol in dom["instruments"]:
            if symbol not in execs:
                continue
            for i, condition in enumerate(dom["conditions"]):
                out.append({
                    "cell_id": f"{did}:{symbol}:C{i + 1}",
                    "domain": did, "symbol": symbol, "condition": condition,
                    "mechanism_family": family, "horizon": horizon,
                    "control": controls[i % len(controls)],
                    "why": str(dom["title"]),
                })
    return tuple(out)


CELLS: tuple[dict[str, Any], ...] = cells()

# --------------------------------------------------------------------------- interactions
#: HOW THESE THREE ARE NOT TESTED ALONE -- which for this pack is not a nicety but the whole
#: premise: every significant mechanism here terminates in a neighbour's grid, factory or
#: customs table, so a Mekong finding that is not measured against its downstream owner is not a
#: finding at all.
INTERACTIONS: tuple[dict[str, Any], ...] = (
    {"with": "th",
     "mechanism": "THAILAND IS THE DOWNSTREAM OF ALL THREE. It burns Myanmar's gas in its power "
                  "stations, imports Laos's electricity under long-term PPAs, employs the "
                  "migrant labour that both countries remit from, buys Cambodian and Lao crops "
                  "for its mills, and shuts for Songkran in the same April week. The `th` pack "
                  "owns the Thai power system, the baht and the border-trade tables; this pack "
                  "reads them and measures the upstream side against them rather than "
                  "re-deriving a single one of Thailand's mechanics",
     "observable": "Thai gas supply by source, Thai electricity imports from Laos, Thai border "
                   "trade by checkpoint and registered migrant workers by nationality",
     "targets": ("USDTHB", "XNGUSD", "COTTON"),
     "control": "the `th` pack's own power and trade study over the identical window; an "
                "upstream claim must beat Thailand's own measurement of its own system"},
    {"with": "cn",
     "mechanism": "CHINA IS THE BUYER, THE CREDITOR AND THE BUILDER. It takes essentially all "
                  "the Kachin heavy rare-earth feedstock and is the only place with separation "
                  "capacity; it is the dominant external creditor to Laos and the owner of the "
                  "railway that reshaped northern Mekong freight; and its customs administration "
                  "publishes the MIRROR that is the only public measurement of the Myanmar flow. "
                  "The `cn` pack owns the customs release, the renminbi and the industrial "
                  "cycle; this pack reads all three",
     "observable": "Chinese customs imports by origin and HS code, the railway freight series, "
                   "and the Chinese separator and magnet utilisation downstream",
     "targets": ("USDCNH", "XCUUSD", "XNIUSD"),
     "control": "the general China-risk complex over the same days, which is what separates a "
                "rare-earth SUPPLY event from a China-risk SENTIMENT event"},
    {"with": "vn",
     "mechanism": "VIETNAM IS THE CONTROL AND THE COMPETITOR AT ONCE. Its managed exchange rate "
                  "over the same decade and the same shocks is the counterfactual for "
                  "Cambodia's dollarisation and Laos's collapsed float -- the third arm of the "
                  "natural experiment. It also buys Lao electricity and Cambodian crops, and it "
                  "competes with Cambodia for exactly the same garment orders, which makes its "
                  "export volumes the control for every Cambodian trade-policy event",
     "observable": "Vietnamese garment exports and the dong's path over the same windows as the "
                   "Cambodian series, and Vietnamese imports of Lao power and Cambodian crops",
     "targets": ("USDTHB", "COTTON", "USDCNH"),
     "control": "Vietnam's own series as the placebo: a mechanism that fires in both is regional "
                "and belongs to neither pack alone"},
    {"with": "sg",
     "mechanism": "SINGAPORE IS THE FINANCIAL AND TRADE-FINANCE DOWNSTREAM. The region's trade "
                  "finance, the commodity trading houses that buy its crops and the frontier "
                  "research that covers it are all written and booked there, and the Singapore "
                  "dollar is the cleanest regional risk-appetite leg the broker quotes for "
                  "ASEAN. The `sg` pack owns that venue and this pack reads it",
     "observable": "regional trade-finance conditions and the Singapore dollar's behaviour "
                   "against the dated Mekong policy events",
     "targets": ("USDSGD", "US500"),
     "control": "the ASEAN risk complex as a whole; a Mekong claim that is indistinguishable "
                "from regional risk appetite is regional risk appetite"},
    {"with": "idn",
     "mechanism": "INDONESIA IS THE SIZE CONTROL. It is a large ASEAN commodity exporter with "
                  "its own currency, its own dollarisation-free monetary policy and exposure to "
                  "the same external dollar cycle, which makes USDIDR the benchmark against "
                  "which a Mekong currency or commodity finding must show that it is about the "
                  "Mekong and not about emerging-Asia dollar funding",
     "observable": "USDIDR and Indonesian commodity export volumes over the same windows as the "
                   "Mekong series",
     "targets": ("USDIDR", "USDSGD"),
     "control": "the emerging-Asia dollar cycle, which must be removed before any "
                "Mekong-specific currency claim survives"},
    {"with": "ind",
     "mechanism": "INDIA IS THE RICE POLICY THAT ACTUALLY MOVES THE WORLD PRICE. Indian export "
                  "restrictions and their reversals dominate the world rice market, and Myanmar "
                  "and Cambodian policy acts cluster in the same windows -- which means a naive "
                  "event study on a Mekong restriction attributes the largest exporter's "
                  "decision to one of the smallest. The `ind` pack owns the Indian side",
     "observable": "Indian export-policy announcements and volumes against the Myanmar and "
                   "Cambodian rice series over the same windows",
     "targets": ("USDINR", "CORN", "SOYBEAN"),
     "control": "Indian policy itself, which is the single most important control any Mekong "
                "rice claim has to survive"},
)

# --------------------------------------------------------------------------- transmission
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    {"id": "MK-T1",
     "source": "Announced Myanmar pipeline maintenance outage windows",
     "target": "XNGUSD", "targets": ("XNGUSD", "USDTHB"), "to_country": "th", "sign": "+",
     "mechanism": "a material share of Thailand's power-generation gas stops arriving on an "
                  "announced schedule, and the Thai system must burn something else; the "
                  "substitution is the transmission and the reserve margin is the amplifier",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 0.0,
     "actor": "the Yadana and Zawtika operators",
     "constraint": "a pipeline with no alternative buyer and a scheduled outage",
     "flow": "pipeline gas into Thai power generation",
     "condition": "whether the outage ran longer than announced, and the reserve margin bucket",
     "control": "matched weeks with no outage and the same seasonal demand; Thai domestic field "
                "outages of comparable size; the `th` pack's own power study",
     "falsifier": "no differential Thai gas or power behaviour in the announced windows, which "
                  "would mean the reserve margin absorbs the outage and it is fully anticipated",
     "evidence": "HYPOTHESIS"},
    {"id": "MK-T2",
     "source": "Chinese customs rare-earth imports from Myanmar by origin",
     "target": "USDCNH", "targets": ("USDCNH", "XNIUSD"), "to_country": "cn", "sign": "+",
     "mechanism": "most of the world's heavy rare-earth feedstock crosses one border into one "
                  "country's separation capacity; a dated closure or change of control at the "
                  "mine is a supply shock with NO SUBSTITUTE SOURCE at scale, and the customs "
                  "tonnage is the only public measurement of it",
     "horizon": "1 to 3 months", "horizon_class": "monthly", "lag_days": 22.0,
     "actor": "the Kachin mining zone and whoever controls it",
     "constraint": "one buyer country with the only separation capacity",
     "flow": "rare-earth feedstock into Chinese separators and magnet makers",
     "condition": "whether the month contained a reported closure, and the tonnage against its "
                  "trailing twelve-month mean",
     "control": "the general China-risk complex over the same days; THE CUSTOMS TONNAGE ITSELF "
                "as the physical test that separates supply from sentiment",
     "falsifier": "the metals complex moves on the reported closure but the customs tonnage does "
                  "not fall, which proves the event was sentiment and not supply",
     "evidence": "MEASURED_ELSEWHERE"},
    {"id": "MK-T3",
     "source": "The Myanmar administered-to-parallel exchange-rate spread",
     "target": "USDTHB", "targets": ("USDTHB", "XAUUSD"), "to_country": "th", "sign": "+",
     "mechanism": "a widening spread is the state rationing foreign exchange harder, which "
                  "pushes import demand and store-of-value demand into the border economy: into "
                  "baht-denominated cross-border trade and into physical gold",
     "horizon": "1 to 20 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "the Central Bank of Myanmar and the money changers",
     "constraint": "an administered rate that creates the market it then polices",
     "flow": "rationed official FX into parallel and cross-border channels",
     "condition": "the rationing bucket from `parallel_spread` and its direction of change",
     "control": "the same buckets in a neighbouring floating economy with no administered rate; "
                "the gold price in kyat as the domestic channel that must be removed first",
     "falsifier": "the spread adds nothing to Thai border-trade volumes or to partner-reported "
                  "Myanmar imports once the parallel LEVEL is included",
     "evidence": "HYPOTHESIS"},
    {"id": "MK-T4",
     "source": "Myanmar rice export restrictions and licensing changes",
     "target": "CORN", "targets": ("CORN", "SOYBEAN", "USDINR"), "to_country": "global",
     "sign": "+",
     "mechanism": "a marginal exporter restricting shipments tightens the world calorie balance "
                  "at the margin; the broker quotes no rice, so the claim is routed through the "
                  "substitute-calorie complex and through the currency of the exporter whose "
                  "policy actually sets the price",
     "horizon": "1 to 2 quarters", "horizon_class": "quarterly", "lag_days": 2.0,
     "actor": "the Myanmar Rice Federation and the Ministry of Commerce",
     "constraint": "domestic food price as a political variable",
     "flow": "withheld export volume into the world grain balance",
     "condition": "whether a restriction was announced or lifted, and whether India or Thailand "
                  "acted in the same window",
     "control": "INDIAN AND THAI POLICY OVER THE SAME WINDOW, which is the control that matters "
                "most; the broader grains complex, which must be removed first",
     "falsifier": "the effect disappears entirely once Indian policy dates are controlled for, "
                  "which would mean the study was attributing India's decision to Myanmar",
     "evidence": "HYPOTHESIS"},
    {"id": "MK-T5",
     "source": "Cambodia's published dollarisation share and riel-promotion operations",
     "target": "USDSGD", "targets": ("USDSGD", "US500"), "to_country": "global", "sign": "+",
     "mechanism": "a dollarised economy transmits an external dollar shock directly into "
                  "domestic conditions with no exchange-rate buffer at all, which makes "
                  "Cambodia a pure-play read on dollar tightness in frontier Asia and the two "
                  "neighbours the counterfactual",
     "horizon": "1 to 4 quarters", "horizon_class": "quarterly", "lag_days": 45.0,
     "actor": "the National Bank of Cambodia and the dollarised private sector",
     "constraint": "no interest-rate channel and no exchange-rate channel",
     "flow": "external dollar conditions straight into domestic credit and demand",
     "condition": "the dollarisation bucket and whether a riel-promotion measure was active",
     "control": "LAOS, whose float collapsed, and VIETNAM, whose managed rate did not, over the "
                "same shocks; the common terms of trade, removed first",
     "falsifier": "Cambodian macro volatility is indistinguishable from the two controls' once "
                  "terms of trade and external demand are removed, which would mean the "
                  "currency regime bought nothing either way",
     "evidence": "HYPOTHESIS"},
    {"id": "MK-T6",
     "source": "Dated EU and US trade-preference decisions on Cambodian exports",
     "target": "COTTON", "targets": ("COTTON", "US500", "USDSGD"), "to_country": "global",
     "sign": "-",
     "mechanism": "a foreign government's decision with a published effective date removes "
                  "duty-free access from part of one country's export basket; the orders move "
                  "to competitors, the input fibre demand moves with them, and the whole thing "
                  "is measurable in monthly customs data on both sides",
     "horizon": "1 to 3 months", "horizon_class": "monthly", "lag_days": 25.0,
     "actor": "the Cambodian garment sector and the EU and US trade authorities",
     "constraint": "thin margins that cannot absorb a tariff",
     "flow": "garment orders re-routing between competing exporters",
     "condition": "whether a preference or tariff decision took effect in the window",
     "control": "BANGLADESH AND VIETNAM over the same window; the buyer's own demand read "
                "through US500, which must be removed before any access claim is made",
     "falsifier": "Cambodian volumes show no differential path against the competitor control, "
                  "which would mean the preference was not binding at the margin",
     "evidence": "HYPOTHESIS"},
    {"id": "MK-T7",
     "source": "Mekong station levels as a ratio of each station's seasonal median",
     "target": "USDTHB", "targets": ("USDTHB", "XNGUSD"), "to_country": "th", "sign": "+",
     "mechanism": "low water bounds Lao generation from above, the Thai offtaker receives less "
                  "contracted hydro and substitutes gas; the substitution is the transmission "
                  "and the gas burn is where it lands",
     "horizon": "1 to 20 sessions", "horizon_class": "multi_day", "lag_days": 2.0,
     "actor": "the Lao hydropower concessionaires and the Thai offtaker",
     "constraint": "a contracted tariff, so the only variable is the water",
     "flow": "hydro generation into the Thai grid, and gas in its place when it is short",
     "condition": "the `hydro_bound` bucket, and WHETHER THE CONSTRAINT BINDS -- the drought "
                  "tail only, because the flood tail does not raise a contracted volume",
     "control": "the same season in normal-flow years; the Thai gas burn, which must move the "
                "OPPOSITE WAY for the mechanism to be real; upstream reservoir operation, which "
                "is not the same object as rainfall",
     "falsifier": "Thai electricity imports from Laos show no response to station levels once "
                  "seasonality is removed, which would mean storage fully buffers the flow",
     "evidence": "HYPOTHESIS"},
    {"id": "MK-T8",
     "source": "The Lao external payment schedule and announced bilateral deferrals",
     "target": "USDTHB", "targets": ("USDTHB", "USDCNH", "XAUUSD"), "to_country": "cn",
     "sign": "+",
     "mechanism": "the region's most debt-distressed sovereign meets a concentrated bilateral "
                  "schedule out of hydropower royalties; the weeks around a payment date are "
                  "when the currency and the fuel-import rationing tighten together",
     "horizon": "1 to 2 quarters", "horizon_class": "quarterly", "lag_days": 5.0,
     "actor": "the Lao Ministry of Finance and its Chinese creditors",
     "constraint": "bilateral concentration, so no market restructuring is available",
     "flow": "export receipts into external debt service, and rationing into everything else",
     "condition": "the distance in weeks to a known payment date and whether a deferral was "
                  "announced",
     "control": "matched windows with no payment date; the regional dollar cycle, removed first; "
                "Cambodia and Vietnam as the two currency-regime controls",
     "falsifier": "no differential behaviour in the executable legs around announced deferral "
                  "dates, which is the EXPECTED result for an economy this small and is "
                  "declared in advance so a null is not reported as news",
     "evidence": "HYPOTHESIS"},
    {"id": "MK-T9",
     "source": "Laos-China Railway freight tonnage and the 2021-12-03 opening",
     "target": "USDCNH", "targets": ("USDCNH", "CORN"), "to_country": "cn", "sign": "+",
     "mechanism": "a permanent, dated step in freight capacity between China and the northern "
                  "Mekong lowers the delivered cost of Lao and Thai agricultural and mineral "
                  "cargo into China, which is a structural claim about volumes rather than a "
                  "cyclical one about prices",
     "horizon": "1 to 4 quarters", "horizon_class": "quarterly", "lag_days": 10.0,
     "actor": "the railway operator and the Chinese and Lao shippers",
     "constraint": "a gauge break at the southern end that caps the through-route",
     "flow": "cargo shifting from road and sea onto rail, and new volume behind it",
     "condition": "pre-opening, the opening year, or the post-2023 operating era",
     "control": "THE PANDEMIC REOPENING PATH, because the opening date sits inside it; road and "
                "sea freight over the same months; a placebo step at a random date",
     "falsifier": "regional volumes show no level shift at the opening once the reopening path "
                  "is controlled for, which would mean the line only re-routed existing freight",
     "evidence": "HYPOTHESIS"},
    {"id": "MK-T10",
     "source": "The mid-April simultaneous closure of four economies",
     "target": "USDTHB", "targets": ("USDTHB", "COTTON"), "to_country": "th", "sign": "-",
     "mechanism": "factories, ports, customs posts and border crossings across Myanmar, "
                  "Cambodia, Laos and Thailand stop in the same week, so regional production "
                  "and logistics fall together rather than one at a time; the migrant labour "
                  "force travels home in the same window",
     "horizon": "0 to 5 sessions", "horizon_class": "intraday", "lag_days": 0.0,
     "actor": "four states, through four holiday statutes that coincide",
     "constraint": "a statutory closure unrelated to demand",
     "flow": "a scheduled regional interruption in production and freight",
     "condition": "the maximum number of jurisdictions simultaneously closed, and how many days "
                  "cost a weekday session",
     "control": "matched weeks in the same month with no closure; a SINGLE-COUNTRY closure "
                "elsewhere in the year as the placebo; the Thai leg measured alone by `th`",
     "falsifier": "the regional window behaves no differently from a single-country closure of "
                  "the same length, which would mean simultaneity adds nothing",
     "evidence": "HYPOTHESIS"},
    {"id": "MK-T11",
     "source": "Sihanoukville container throughput against the customs export value",
     "target": "US500", "targets": ("US500", "COTTON", "USDSGD"), "to_country": "global",
     "sign": "+",
     "mechanism": "an audited physical count of containers leaving a single-sector export "
                  "economy is a nowcast of that economy's export value, and the wedge between "
                  "the two is either mix, transhipment or a valuation change -- each testable",
     "horizon": "1 to 3 months", "horizon_class": "monthly", "lag_days": 30.0,
     "actor": "the Sihanoukville Autonomous Port and the garment exporters",
     "constraint": "berth capacity, so throughput is capacity as much as demand",
     "flow": "containers of garments and footwear into the EU and US markets",
     "condition": "the throughput's deviation from its trailing path and the sign of the wedge",
     "control": "the Vietnamese deep-water ports over the same months; the capacity milestones "
                "themselves; the PRIOR MONTH'S customs exports, which any leading claim must beat",
     "falsifier": "throughput adds nothing to a nowcast of the monthly export value once the "
                  "prior month is known, making it a lagging confirmation rather than a lead",
     "evidence": "HYPOTHESIS"},
    {"id": "MK-T12",
     "source": "The gap between a modelled IFI estimate and the mirror data behind it",
     "target": "USDTHB", "targets": ("USDTHB", "USDCNH"), "to_country": "global", "sign": "+",
     "mechanism": "where a country's own statistics have stopped, the desk trades a SUBSTITUTE, "
                  "and the substitute's bias is a research object in its own right: the "
                  "divergence between a modelled estimate and the partner-reported measurement "
                  "it is built from is a dated, testable statement about how wrong the pack's "
                  "own inputs are",
     "horizon": "1 to 4 quarters", "horizon_class": "quarterly", "lag_days": 90.0,
     "actor": "the multilateral institutions and the partner customs administrations",
     "constraint": "a reporter that stopped reporting",
     "flow": "a measurement gap into every downstream cell that uses the substitute",
     "condition": "whether the substitute is a MIRROR MEASUREMENT or a MODELLED ESTIMATE, and "
                  "the size of the gap between them",
     "control": "a regional jurisdiction whose own statistics DO exist, which calibrates the "
                "normal mirror-versus-domestic gap; the same substitute applied to a period "
                "when the domestic series still existed, which measures the bias directly",
     "falsifier": "the substitute's gap is stable and uninformative, which would be the best "
                  "possible outcome: it would mean the substitute can be used without "
                  "correction and MK-L's caveat can be retired",
     "evidence": "HYPOTHESIS"},
)

# --------------------------------------------------------------------------- policy eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    {"name": "sanctions, reconstruction and the pre-dam Mekong",
     "start": "1990-01-01", "end": "2011-03-29",
     "regime": "Myanmar under military rule and broad sanctions with almost no formal foreign "
               "investment; Cambodia rebuilding from conflict with dollarisation setting in as "
               "the post-UNTAC default; Laos a small closed economy before the mainstream dam "
               "build-out",
     "markers": ("1997 the three joined ASEAN in stages",
                 "the post-UNTAC dollarisation of Cambodia",
                 "2010 the pre-reform Myanmar exchange regime"),
     "why_it_matters": "none of the pack's five mechanisms exists in a testable form here: no "
                       "rare-earth trade at scale, no garment sector of consequence, no Lao "
                       "export hydropower fleet. Pooling this era with the modern one averages "
                       "three different economies",
     "status": "SETTLED"},
    {"name": "the opening decade",
     "start": "2011-03-30", "end": "2020-01-31",
     "regime": "Myanmar's reform period with a managed float from 2012 and foreign investment "
               "returning; Cambodia's garment sector growing under duty-free EU and US access; "
               "the Lao dam build-out and the PPAs that came with it",
     "markers": ("2012 the Myanmar managed float replaces the official peg",
                 "the Cambodian garment sector's expansion under Everything But Arms",
                 "the commissioning of the large Lao mainstream and tributary projects"),
     "why_it_matters": "THE ONLY ERA IN WHICH ALL THREE ECONOMIES HAD FUNCTIONING PUBLIC "
                       "STATISTICS AT ONCE, which makes it the calibration window for every "
                       "substitute this pack later has to rely on",
     "status": "SETTLED"},
    {"name": "the pandemic and the preference withdrawal",
     "start": "2020-02-01", "end": "2021-01-31",
     "regime": "borders closed, garment orders collapsed and recovered, tourism stopped, and the "
               "European Union withdrew duty-free treatment from part of Cambodia's export "
               "basket on a published effective date",
     "markers": ("2020-08-12 the partial withdrawal of Everything But Arms takes effect",
                 "2020 the border closures across all three",
                 "2020-10 the launch of the Bakong payment system"),
     "why_it_matters": "the EBA event is the pack's cleanest trade-policy experiment and it sits "
                       "inside the pandemic, so the competitor control is not optional -- "
                       "without Bangladesh and Vietnam the study measures the pandemic",
     "status": "SETTLED"},
    {"name": "the Myanmar rupture",
     "start": "2021-02-01", "end": "2021-12-31",
     "regime": "the Myanmar coup and its first year: the kyat collapsed, the statistical system "
               "stopped publishing, the independent press was closed or exiled, and the formal "
               "banking system lost correspondent access. The Laos-China Railway opened in "
               "December of the same year",
     "markers": ("2021-02-01 the coup",
                 "2021 the suspension of most Myanmar official statistical publication",
                 "2021-12-03 the Laos-China Railway opens"),
     "why_it_matters": "THE DATE THE MYANMAR DATA STOPS. Every Myanmar series in this pack is "
                       "either pre-2021 or a substitute, and a study that runs across this "
                       "boundary without saying so is splicing two different measurement "
                       "systems and calling the join a trend",
     "status": "SETTLED"},
    {"name": "the two-rate kyat and the Lao currency crisis",
     "start": "2022-01-01", "end": "2023-12-31",
     "regime": "Myanmar's forced-conversion directive and the administered reference rate against "
               "a far weaker parallel market; the kip losing more than half its value with "
               "published inflation above forty per cent; Cambodia recovering on garment demand "
               "while its dollarisation insulated it from both",
     "markers": ("2022-04 the directive compelling conversion of onshore foreign currency",
                 "2022-08 the administered reference rate reset",
                 "2023 Lao inflation peaking above forty per cent year-on-year"),
     "why_it_matters": "THE THREE-REGIME NATURAL EXPERIMENT RUNS HERE. One economy with an "
                       "administered rate, one with a collapsing float and one dollarised, "
                       "facing the same external dollar cycle at the same time -- which is why "
                       "MK-E and MK-I are fitted inside this window and not across it",
     "status": "SETTLED"},
    {"name": "the rare-earth disruption and the deferral years",
     "start": "2024-01-01", "end": "2026-12-31",
     "regime": "the Kachin mining zone changing hands and the border closing, with the heavy "
               "rare-earth price complex reacting; Lao debt service met by successive bilateral "
               "deferrals rather than resolution; Cambodia's garment exports recovering into a "
               "shifting US tariff landscape",
     "markers": ("2024 the capture of the Chipwi and Pangwa mining zone and the border closure",
                 "2024-2025 the heavy rare-earth price response",
                 "the successive Lao bilateral debt deferrals"),
     "why_it_matters": "the current regime and the only one whose data the desk can actually "
                       "trade; it is short, which bounds every cell fitted inside it, and that "
                       "is stated rather than worked around",
     "status": "OPEN"},
    {"name": "the Lao amortisation wall and the rare-earth substitution programmes",
     "start": "2027-01-01", "end": "2030-12-31",
     "regime": "the deferred Lao external payments come due in a concentrated window, and the "
               "non-Chinese heavy rare-earth separation capacity announced in several "
               "jurisdictions is scheduled to begin operating -- the first real test of whether "
               "the Kachin supply chain has a substitute",
     "markers": ("the deferred Lao amortisation schedule",
                 "the announced non-Chinese heavy rare-earth separation capacity"),
     "why_it_matters": "DECLARED IN ADVANCE BECAUSE IT IS SCHEDULED IN ADVANCE. A forward regime "
                       "boundary is exactly as important as a historical one: MK-B's central "
                       "claim is that there is no substitute at scale, and this is the window "
                       "in which that claim becomes falsifiable",
     "status": "SCHEDULED"},
)
