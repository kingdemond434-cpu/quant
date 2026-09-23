"""SOUTHERN AFRICA -- Zimbabwe, Botswana, Mozambique, Angola and Namibia: the platinum dyke, the
diamond calendar, the newest LNG and oil provinces on earth, the only OPEC exit in a decade, and
a currency area whose smaller half is the only lawful third-party read on the rand.

WHY FIVE JURISDICTIONS IN ONE PACK, AND WHY THIS ONE IS `za`'S COMPLEMENT. South Africa is the
refining, port, power and financial hub of all five: Zimbabwean PGM concentrate is smelted and
refined through South African capacity, Botswana's pula carries a PUBLISHED 40% rand weight,
Namibia's dollar is pegged 1:1 to the rand inside the Common Monetary Area, Mozambican power
from Cahora Bassa is sold into Eskom, and Angolan and Mozambican risk is priced off the rand
because nothing else in the bloc is liquid. `za` has its own pack and owns the JSE, the SARB, the
Eskom load-shedding plane and the rand's own idiosyncratic risk. This pack owns what `za` cannot
see from the inside: five sovereign policy machines that ACT on the physical commodities the
broker quotes, and one currency area observed from the member that is not South Africa.

THE FIVE MECHANISMS THAT EARN THE TRIAL BUDGET. Each is published, dated, price-relevant, and a
domain of its own rather than a sentence inside a generic frontier domain:

  1. ZIMBABWE IS THE WORLD'S THIRD-LARGEST PGM PRODUCER AND IT LEGISLATES ON BENEFICIATION.
     Zimplats, Mimosa and Unki sit on the Great Dyke and the broker quotes XPTUSD and XPDUSD.
     Zimbabwe banned RAW LITHIUM ORE exports by statutory instrument in December 2022 and has
     legislated and re-legislated toward a ban on raw PGM concentrate exports -- dated, gazetted,
     sovereign policy that changes WHERE the metal is refined and therefore who holds the
     concentrate stock. SA-A and SA-B are built on those instruments and on the Veritas archive
     that publishes them.
  2. ZIMBABWE IS ALSO THE DESK'S BEST LIVE CASE OF MONETARY DESTRUCTION AS A DATED SERIES.
     Dollarisation in February 2009, the RTGS dollar of 2019-02-20, SI 142/2019's de-dollarisation
     and SI 85/2020's reversal, the ZiG introduced on 2024-04-05 against gold and FX reserves, and
     the ~43% ZiG devaluation of 2024-09-27. Every one is a NAMED POLICY ERA that invalidates any
     pooled Zimbabwean study, and the parallel-market premium is published daily by private
     trackers at a credibility this pack labels UNRELIABLE and keeps anyway.
  3. BOTSWANA IS THE LARGEST DIAMOND PRODUCER BY VALUE AND ITS DEMAND READ IS PUBLISHED TEN TIMES
     A YEAR. De Beers runs ten sales cycles a year on a fixed calendar and publishes a revenue
     number after each -- a high-frequency, dated, published read on global luxury demand that
     essentially no systematic desk uses. The 2023-2025 collapse in rough prices put Botswana's
     GDP into contraction. And the pula is pegged to an EXPLICITLY PUBLISHED basket, 60% SDR and
     40% ZAR with an annually announced crawl rate, which makes its rand beta MEASURABLE rather
     than estimated -- a rarity worth a domain on its own (SA-G).
  4. MOZAMBIQUE IS THE NEXT GREAT LNG PROVINCE AND ITS TIMETABLE IS A DATED SERIES. Coral South
     FLNG shipped its first cargo in November 2022 at roughly 3.4 mtpa; TotalEnergies' Mozambique
     LNG declared force majeure in April 2021 after the Palma attack and lifted it in 2025;
     Rovuma has not taken FID. Mozambique is also the Beira and Nacala corridor for Zimbabwean,
     Zambian and Malawian trade -- the direct interaction with `copperbelt` -- it smelts aluminium
     at Mozal on Cahora Bassa hydropower, and it defaulted on hidden "tuna bond" debt disclosed in
     April 2016 with a published court record.
  5. ANGOLA LEFT OPEC ON 2024-01-01, the first exit in over a decade and explicitly over a quota
     dispute. That is a dated, published, unambiguous change in the constraint on roughly 1.1
     mb/d of crude and a natural experiment on what an OPEC quota actually binds. The monthly
     export loading programmes, the ANPG concession record and the BNA's managed kwanza are all
     public, and the Lobito Corridor reopened for Copperbelt copper in 2024 under a published
     concession.

AND THE SIXTH, WHICH IS NOT A COUNTRY BUT A CURRENCY AREA. NAMIBIA IS THE NEWEST OIL PROVINCE ON
EARTH -- Venus and Graff in the Orange Basin, discovered in February 2022, with a published
appraisal and FID timetable -- and it is a top-five uranium producer. It is also a Common
Monetary Area member whose dollar is pegged ONE TO ONE to the rand, which makes USDZAR the
LITERAL, EXACT executable expression of Namibian FX and makes Namibia the only lawful
third-party read on the CMA the desk has. Lesotho's loti and Eswatini's lilangeni sit at the same
parity; Botswana left the rand area in 1976 and is in SACU but NOT in the CMA, and getting that
distinction wrong is how a regional study invents a peg that does not exist.

THE FIVE CURRENCIES ARE ALL ABSENT AND THE PACK SAYS SO FIVE TIMES. ZWG, BWP, MZN, AOA and NAD
are not in `data/universe/universe.json` and never will be. Every one is named in
`TRANSMISSION_TARGETS` with its regime and the broker symbols its economics route into. NAD is
labelled EXACT because a 1:1 peg is not a proxy; the other four are PROXIES with their controls
named, so an absent instrument produces a transmission hypothesis and never a cell that can never
be filled (L1.49).

THE GROUND IS THREE-LANGUAGE AND AN ENGLISH-ONLY CRAWL READS ONE THIRD OF IT. English is
official in Zimbabwe, Botswana and Namibia, which is the trap: an English crawl returns something
for every query and reads complete. PORTUGUESE is the whole of Mozambique and Angola -- the
Boletim da República and the Diário da República, the Banco de Moçambique and Banco Nacional de
Angola statistics, Notícias, Carta de Moçambique, Jornal de Angola, Expansão and Mercado -- and
none of it exists in English. Shona and Ndebele carry the Zimbabwean street and the parallel-rate
ecology; Setswana carries the Botswana ground; Afrikaans and Oshiwambo carry the Namibian one;
Changana and Umbundu carry what is left of the Mozambican and Angolan vernacular press, which is
mostly radio and is declared thin rather than padded.

THE TWO-LANE ORDER (2026-09-06) BINDS HARD HERE. The tempting names are all single companies --
the Great Dyke operators, Debswana, De Beers, Sonangol, ENH, Mozal, NAMCOR, Old Mutual -- and
every one appears in this pack as an ACTOR or an OBSERVABLE and never as an instrument. No share
CFD appears in any instrument tuple in this file, and no crypto-exchange ground is hunted
(mandate 2026-08-18).
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Any

# --------------------------------------------------------------------------- identity
CODE = "southern_africa"
NAME = "Southern Africa (Zimbabwe, Botswana, Mozambique, Angola, Namibia)"
REGION_COMMAND = "africa"
REGION_DESK = "AFRICA"
FOREST = "africa"

#: THE FIVE COUNTRIES THIS PACK ANSWERS FOR. `scripts/check_regional_parity.py::jurisdictions_of`
#: reads this tuple and nothing else, so a pack that answers five countries and declares one is
#: credited with one. None of the five was on any forest's roster before this pack landed.
JURISDICTIONS: tuple[str, ...] = ("zw", "bw", "mz", "ao", "na")

#: The pack-level currency is Zimbabwe's, because the ZiG is the largest live monetary experiment
#: in the five and because the framework carries ONE currency per pack. All five are declared here
#: and all five are absent from the broker (see TRANSMISSION_TARGETS).
CURRENCY = "ZWG"
CURRENCIES: dict[str, str] = {
    "zw": "ZWG",   # Zimbabwe Gold, introduced 2024-04-05; the sixth currency since 2008
    "bw": "BWP",   # Botswana pula -- a PUBLISHED basket, 60% SDR / 40% ZAR, with an annual crawl
    "mz": "MZN",   # Mozambican metical -- managed, with a long stable stretch since 2021
    "ao": "AOA",   # Angolan kwanza -- managed by the BNA with published FX auctions
    "na": "NAD",   # Namibia dollar -- pegged ONE TO ONE to the rand inside the CMA
}

#: Zimbabwe, Mozambique and Angola run a calendar fiscal year; Botswana and Namibia run 1 April
#: to 31 March. The framework carries one date, so the pack declares the calendar year-end that
#: three of the five share and names the other two beside it.
FISCAL_YEAR_END = "12-31"
FISCAL_YEAR_ENDS: dict[str, str] = {
    "zw": "12-31 (the National Budget Statement is presented to Parliament in November for a "
          "1 January start)",
    "bw": "03-31 (the Budget Speech is delivered in February for a 1 April start, and the SACU "
          "receipts for the year are known before it is written)",
    "mz": "12-31 (the Plano Económico e Social e Orçamento do Estado runs the calendar year)",
    "ao": "12-31 (the Orçamento Geral do Estado runs the calendar year and is revised in-year "
          "when the oil price assumption breaks)",
    "na": "03-31 (the Budget Statement is tabled in February or March for a 1 April start, with "
          "the SACU transfer the single largest revenue line)",
}

NATIVE_LANGUAGES: tuple[str, ...] = ("en", "pt", "sn", "nd", "tn", "af", "ng", "ts", "umb")
COT_CURRENCY = ""            # no CFTC contract exists for ZWG, BWP, MZN, AOA or NAD
EXPORT_ECONOMY = "commodity_exporter"
RETAIL_LEVERAGE_REGIME = "restricted"
MISSION = ("mine Southern Africa as the five-treasury, one-rand-shaped physical economy it is: "
           "the Great Dyke's platinum and palladium and Zimbabwe's gazetted beneficiation orders, "
           "the ZiG and the five currency regimes before it, the ten De Beers sales cycles a year "
           "and the published 60/40 pula basket, the Coral South and Mozambique LNG timetable and "
           "the Beira and Nacala corridors, Mozal on Cahora Bassa, Angola's OPEC exit of "
           "2024-01-01 and the Lobito Corridor, Namibia's Orange Basin appraisal clock and its "
           "uranium, and the Common Monetary Area read from the member that is not South Africa")

#: The instruments this pack may compile a cell against. Every one is in the broker registry,
#: none is a single-name equity, and each carries the mechanism that put it here.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "XPTUSD",                         # the Great Dyke: Zimplats, Mimosa, Unki -- world #3 in PGM
    "XPDUSD",                         # the same orebody; the Dyke's palladium-to-platinum ratio
    "XAUUSD",                         # Zimbabwean gold deliveries, the gold coins, the ZiG's cover
    "XALUSD",                         # Mozal on Cahora Bassa hydropower
    "XCUUSD",                         # Beira, Nacala and Lobito: three corridors for one orebody
    "XZNUSD",                         # Zambian and Namibian zinc through the same corridors
    "XBRUSD",                         # Angolan crude, Mozambican condensate, the Orange Basin
    "XTIUSD",                         # the light-sweet leg of the same barrels
    "XNGUSD",                         # Coral South, Mozambique LNG, Rovuma and Angola LNG
    "USDZAR",                         # the CMA peg, the pula basket, the bloc's only liquid FX
    "EURZAR", "GBPZAR", "ZARJPY",     # the rand crosses the basket and the peg also move
    "CORN", "WHEAT",                  # the regional import bill and the drought years
    "SUGAR",                          # Zimbabwean, Mozambican and Zambian cane on the same rails
    "COTTON",                         # Zimbabwean and Mozambican lint, both smallholder crops
    "US500", "UK100",                 # the luxury-demand and frontier-risk channels
)

#: WHAT THIS PACK CANNOT TRADE, NAMED. Five currencies, three commodities with no contract this
#: broker quotes, and six exchanges. Each row carries the broker symbols its economics route into.
#: A PROXY IS A CARRIER AND NEVER A SUBSTITUTE -- except NAD, which is not a proxy at all: a 1:1
#: peg inside a currency union makes USDZAR an EXACT expression of Namibian FX, and the row says
#: so in a field of its own so no reader has to infer it.
TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "ZWG -- Zimbabwe Gold, the sixth currency since 2008",
     "venue": "Reserve Bank of Zimbabwe willing-buyer-willing-seller interbank market",
     "exactness": "PROXY",
     "regime": "INTRODUCED 2024-04-05, structured as a currency backed by gold and foreign "
               "exchange reserves with a published reserve-cover statement; DEVALUED by roughly "
               "43% on 2024-09-27 and managed since. It replaced the RTGS dollar, which replaced "
               "the multi-currency regime of 2009-2019, which replaced the hyperinflated "
               "Zimbabwe dollar. Six regimes in sixteen years.",
     "parallel_market": "a daily street rate published by private trackers (ZimPriceCheck, "
                        "Marketwatch and the Telegram and X rate channels) at a premium that has "
                        "run from near parity to multiples of the official rate; the premium "
                        "itself IS the regime-stress state SA-C conditions on, and the pack "
                        "labels the trackers UNRELIABLE and keeps them rather than dropping them",
     "route": "the ZiG's gold and FX cover makes RBZ gold purchases official-sector demand on "
              "XAUUSD; a devaluation is a frontier-risk event on USDZAR; and the mining "
              "companies' surrender requirement is what turns a currency rule into a metal flow",
     "why": "absent from the broker, not deliverable offshore, and no forward market exists; "
            "every ZWG mechanism here terminates in XAUUSD, XPTUSD, XPDUSD or the rand carriers",
     "proxies": ("XAUUSD", "XPTUSD", "XPDUSD", "USDZAR")},
    {"name": "BWP -- the Botswana pula and its PUBLISHED currency basket",
     "venue": "Bank of Botswana; the pula is pegged to a basket, not traded on an open market",
     "exactness": "PROXY_WITH_A_PUBLISHED_WEIGHT",
     "regime": "A CRAWLING BASKET PEG WHOSE WEIGHTS ARE PUBLISHED: roughly 60% SDR and 40% ZAR, "
               "with a rate of crawl announced each year in the Monetary Policy Statement. This "
               "is the rarest thing in frontier FX -- an official, numeric, published currency "
               "weight -- and it means the pula's rand beta is MEASURABLE rather than estimated.",
     "parallel_market": "none of consequence: the pula is convertible and Botswana has run an "
                        "open capital account since 1999, so there is no premium to read",
     "route": "the published 40% ZAR weight means a rand move is mechanically ~40% of a pula "
              "move; the diamond revenue that funds the peg reaches US500 and UK100 through "
              "luxury demand and the Pula Fund's own reserve management",
     "why": "absent from the broker; the executable expression of a 40%-rand basket is the rand "
            "itself, and the pack says which 40% it is claiming",
     "proxies": ("USDZAR", "EURZAR", "GBPZAR", "ZARJPY")},
    {"name": "MZN -- the Mozambican metical",
     "venue": "Banco de Moçambique interbank market (MMI) with the MIMO policy rate",
     "exactness": "PROXY",
     "regime": "MANAGED, with a long administratively stable stretch against the dollar since "
               "2021 after the 2016 collapse that followed the hidden-debt disclosure. Stability "
               "here is a POLICY CHOICE and not a free-float outcome, so a low realised variance "
               "is evidence about the central bank and not about the economy.",
     "parallel_market": "a bureau and street market exists and widens when FX allocation to "
                        "importers is rationed; it is reported in the Portuguese-language press "
                        "and is not published by the central bank",
     "route": "the metical's economics are LNG receipts, megaproject imports, aluminium exports "
              "and corridor transit fees, so they terminate in XNGUSD, XALUSD and XCUUSD",
     "why": "absent from the broker and not deliverable; no cell is ever compiled on MZN",
     "proxies": ("XNGUSD", "XALUSD", "XCUUSD", "USDZAR")},
    {"name": "AOA -- the Angolan kwanza",
     "venue": "Banco Nacional de Angola; FX is allocated through published auctions to the banks",
     "exactness": "PROXY",
     "regime": "MANAGED WITH PUBLISHED INTERVENTION. The BNA abandoned the hard peg in 2018, and "
               "the kwanza depreciated by roughly half again in 2023 when the state stopped "
               "subsidising the rate out of oil receipts. Auctions and reserve statistics are "
               "published; the intervention rule is not.",
     "parallel_market": "the informal market (the 'kinguilas') runs a premium that widens when "
                        "auction allocation is short; it is reported in Expansão and Mercado and "
                        "is not published by the BNA",
     "route": "the kwanza is an OIL CURRENCY with an unusually direct transmission: the state's "
              "revenue, the FX supply and the import bill all move with the barrel, so every AOA "
              "mechanism terminates in XBRUSD and XTIUSD before it reaches anything else",
     "why": "absent from the broker; the executable expression of Angolan FX stress is the crude "
            "price and the frontier-risk carrier, and the pack never pretends otherwise",
     "proxies": ("XBRUSD", "XTIUSD", "USDZAR")},
    {"name": "NAD -- the Namibia dollar, pegged ONE TO ONE to the rand",
     "venue": "Bank of Namibia inside the Common Monetary Area; the rand is legal tender in "
              "Namibia and the two circulate side by side at par",
     "exactness": "EXACT",
     "regime": "A ONE-TO-ONE PEG SINCE THE CURRENCY WAS INTRODUCED IN 1993, under the Common "
               "Monetary Area agreement that also fixes Lesotho's loti and Eswatini's lilangeni "
               "at par. The Bank of Namibia holds rand reserves against the issue and follows the "
               "SARB's policy rate closely because it must.",
     "parallel_market": "NONE, and that is the point: at a 1:1 peg with the rand circulating as "
                        "legal tender there is no premium to arbitrage and none has ever existed",
     "route": "USDZAR IS NOT A PROXY FOR NAD, IT IS NAD. A Namibian FX exposure IS a rand "
              "exposure, exactly, and a Namibian mechanism that moves the demand for local "
              "currency moves the demand for rand. This is the only row in this file where the "
              "carrier and the thing carried are the same instrument.",
     "why": "absent from the broker as a separate symbol because it would be a duplicate quote; "
            "labelled EXACT rather than PROXY so no later reader adds a basis that does not exist",
     "proxies": ("USDZAR", "ZARJPY", "EURZAR")},
    {"name": "ROUGH DIAMONDS -- the commodity that is most of Botswana's exports",
     "venue": "De Beers Global Sightholder Sales (ten sales cycles a year), the Okavango Diamond "
              "Company auctions, and the Antwerp and Dubai secondary market",
     "exactness": "ROUTED_WITH_A_NAMED_CONTROL",
     "regime": "NOT A FUNGIBLE COMMODITY AND NOT EXCHANGE-TRADED ANYWHERE. Rough diamonds are "
               "sold by assortment at negotiated prices; the only public high-frequency number "
               "is the REVENUE of each De Beers sales cycle, published ten times a year.",
     "parallel_market": "the Rapaport polished price list and the secondary rough market are the "
                        "price discovery this market has; both forbid machine extraction and are "
                        "registered here machine_use_allowed=false rather than scraped",
     "route": "the sales-cycle revenue print is a READ ON GLOBAL LUXURY DEMAND, so it is tested "
              "against US500 and UK100 with the luxury-heavy European tape as the sign check, and "
              "against USDZAR as the regional fiscal channel. CONTROL: lab-grown diamond share, "
              "which has been taking the low end of the natural market and would produce the same "
              "revenue fall with no demand change at all",
     "why": "no diamond contract exists at this broker or at any liquid venue; the mechanism is "
            "routed and the confound is named on the face of the row",
     "proxies": ("US500", "UK100", "USDZAR")},
    {"name": "URANIUM (U3O8) -- Namibia is a top-five producer",
     "venue": "Rössing, Husab and Langer Heinrich sell under long-term contracts; the spot "
              "reference is the UxC and TradeTech weekly assessments",
     "exactness": "ROUTED_WITH_A_NAMED_CONTROL",
     "regime": "A CONTRACT MARKET WITH A THIN SPOT TAIL. Most Namibian output moves under "
               "multi-year utility contracts, so a spot move reaches Namibian revenue slowly and "
               "a spot move is mostly a financial-buyer flow rather than a utility one.",
     "parallel_market": "none; the price assessments are proprietary and are registered, never "
                        "scraped",
     "route": "uranium mining is POWER-HUNGRY and its Namibian expression is the NamPower import "
              "bill and the SACU-funded budget, so the executable leg is USDZAR and the energy "
              "complex rather than a uranium price. CONTROL: the Kazakh production guidance, "
              "which sets the world's marginal supply and would move the price with nothing "
              "Namibian changing at all",
     "why": "no uranium instrument exists at this broker; a cell compiled on one would never fill",
     "proxies": ("USDZAR", "XNGUSD", "US500")},
    {"name": "LNG CARGOES -- Coral South, Mozambique LNG and Rovuma",
     "venue": "long-term SPAs with the Area 1 and Area 4 offtakers; the spot reference is the "
              "JKM and TTF assessments, neither of which this broker quotes",
     "exactness": "ROUTED_WITH_A_NAMED_CONTROL",
     "regime": "A PROJECT TIMETABLE, NOT A PRICE. The tradable content of Mozambican LNG is the "
               "DATE a capacity tranche arrives and the date a force majeure is declared or "
               "lifted, because each is a step change in a supply schedule the market has "
               "already priced expectations for.",
     "parallel_market": "none",
     "route": "XNGUSD is Henry Hub and is NOT the price Mozambican cargoes realise; the pack says "
              "so rather than pretending otherwise, and the edge is tested as a GLOBAL SUPPLY "
              "SCHEDULE claim on XNGUSD and XBRUSD with oil-indexed contract pricing as the link. "
              "CONTROL: US Gulf Coast liquefaction start-ups and Qatari North Field expansion "
              "tranches over the same quarters, which dwarf Mozambique and would produce the same "
              "sign with nothing Mozambican happening",
     "why": "no JKM or TTF instrument exists at this broker; routing through XNGUSD with the "
            "basis named is honest, and claiming XNGUSD IS the Mozambican price would not be",
     "proxies": ("XNGUSD", "XBRUSD")},
    {"name": "HARD-ROCK LITHIUM -- Bikita, Arcadia, Sabi Star and Kamativi",
     "venue": "concentrate sold to Chinese converters; the reference is the Fastmarkets and "
              "Asian Metal spodumene assessments",
     "exactness": "ROUTED_WITH_A_NAMED_CONTROL",
     "regime": "AFRICA'S LARGEST HARD-ROCK LITHIUM RESOURCE UNDER A SOVEREIGN EXPORT BAN. The "
               "December 2022 statutory instrument banned the export of unbeneficiated lithium "
               "ore, which is a dated, gazetted change in where the material may be processed.",
     "parallel_market": "artisanal ore smuggling across the Mozambican and South African borders "
                        "is reported by the Zimbabwean press and is not measured anywhere",
     "route": "NO LITHIUM INSTRUMENT EXISTS HERE. The ban is tested as what it is -- a RESOURCE "
              "NATIONALISM EVENT -- on the metals the same sovereign also produces and the same "
              "ministry also regulates, which is XPTUSD, XPDUSD and XCUUSD, and on USDZAR as the "
              "regional policy-risk carrier. CONTROL: Indonesian nickel ore and Chilean lithium "
              "policy over the same quarters, which are the same class of event elsewhere",
     "why": "the lithium price is not quotable here and the pack refuses to substitute a related "
            "metal for it; what IS testable is the policy class, and the row says which",
     "proxies": ("XPTUSD", "XPDUSD", "XCUUSD", "USDZAR")},
)

# --------------------------------------------------------------------------- central banks
#: THE PACK CARRIES ONE `CENTRAL_BANK` BECAUSE THE FRAMEWORK DOES, and five is the truth. The
#: Reserve Bank of Zimbabwe is the primary because the ZiG is the largest live monetary
#: experiment in the five and because its instruments are gazetted and therefore datable. The
#: other four are declared beside it in `CENTRAL_BANKS`, and a study that pools the five is
#: pooling a gold-backed experiment, a published currency basket, a managed float, an oil-funded
#: auction regime and a 1:1 currency-union peg.
CENTRAL_BANK: dict[str, Any] = {
    "name": "Reserve Bank of Zimbabwe (RBZ)",
    "framework": "managed_float",
    "policy_instrument": "the Bank policy rate, set alongside a Monetary Policy Statement that "
                         "also carries the exchange-rate arrangement itself; in practice the "
                         "binding instruments have been the statutory ones -- surrender "
                         "requirements on exporters, the willing-buyer-willing-seller rate, the "
                         "reserve cover for the ZiG and the gold-backed instruments",
    "mandate": "price and financial stability under the Reserve Bank of Zimbabwe Act; the ZiG's "
               "own framing adds a published RESERVE COVER, which is a mandate no other central "
               "bank in this pack carries and the single most datable thing the RBZ publishes",
    "decision_rule": "Monetary Policy Statements are published in February and August with "
                     "mid-period statements when a regime changes; the February 2024 statement "
                     "that introduced the ZiG was dated 2024-04-05 and was itself off-cycle",
    "decision_calendar_rule": "twice-yearly Monetary Policy Statements plus off-cycle statements "
                              "and statutory instruments; the SI is the event, not the speech",
    "decision_dates": (),
    "dates_status": "NOT LISTED, deliberately. The RBZ's decision clock has moved repeatedly and "
                    "the binding acts arrive as statutory instruments with their own gazette "
                    "dates. This pack refuses to type a decision calendar it cannot cite "
                    "(L1.28a); the dated events SA-C is built on are the six regime boundaries, "
                    "each of which has a gazette number or a dated Monetary Policy Statement.",
    "decision_time_utc": "12:00",
    "announce_local": "Harare is UTC+2 all year (Central Africa Time) with NO daylight saving; "
                      "Maputo, Gaborone, Windhoek and Lusaka are the same offset, and Luanda is "
                      "UTC+1. Namibia abolished its winter-time switch in 2017, so every session "
                      "window in this pack is stable in UTC all year.",
    "dst_rule": "none: CAT is UTC+2 year-round in ZW, BW, MZ and NA; WAT is UTC+1 in AO",
    "minutes_lag_days": 0,
    "publication_classes": ("monetary_policy_statement", "statutory_instrument", "weekly_rate",
                            "reserve_cover_statement", "quarterly_economic_review",
                            "gold_deliveries"),
    "policy_rate_series": "RBZ:bank_policy_rate",
    "expected_rate_series": "UNMEASURED",
    "consensus_proxy": "the Treasury bill and RBZ savings-bond yields where they are published, "
                       "and the parallel-market premium as the market's own forward price for the "
                       "currency; there is NO published survey of economists for any of the five",
    "consensus_proxy_trap": "the premium is a survey of expectations AND of rationing at once, so "
                            "a widening premium is not evidence about policy expectations alone",
    "reserves_clock": "the ZiG's reserve cover is published in the RBZ's own statements at an "
                      "irregular cadence; gross reserves for all five are most reliably dated in "
                      "the IMF Article IV and programme documents",
    "programme": "Zimbabwe has had NO IMF financing programme since 1999 and is in arrears; the "
                 "Staff-Monitored Programme and the arrears-clearance process are the dated "
                 "milestones instead, which is the opposite of Mozambique's ECF",
    "off_cycle": ("2024-04-05 the ZiG is introduced with a published gold and FX reserve cover",
                  "2024-09-27 the ZiG is devalued by roughly 43% in a single step",
                  "2019-02-20 the RTGS dollar is created and the 1:1 fiction ends",
                  "2019-06-24 SI 142/2019 makes the Zimbabwe dollar sole legal tender",
                  "2020-03-26 SI 85/2020 restores the use of foreign currency"),
    "root": "https://www.rbz.co.zw",
}

#: The other four, declared rather than folded away. Botswana's is the one with a PUBLISHED
#: weight; Namibia's is the one that cannot choose.
CENTRAL_BANKS: dict[str, dict[str, Any]] = {
    "zw": {"name": "Reserve Bank of Zimbabwe", "framework": "managed_float",
           "rate": "the Bank policy rate, alongside the statutory instruments that actually bind",
           "root": "https://www.rbz.co.zw",
           "why": "six currency regimes since 2008 and a gold-and-FX-backed currency since "
                  "2024-04-05; the only central bank in the desk's roster publishing a reserve "
                  "COVER for its own money"},
    "bw": {"name": "Bank of Botswana", "framework": "basket_peg_with_a_published_crawl",
           "rate": "the Monetary Policy Rate, announced at scheduled MPC meetings; the exchange "
                   "rate is set by a PUBLISHED basket (about 60% SDR, 40% ZAR) with an annually "
                   "announced rate of crawl",
           "root": "https://www.bankofbotswana.bw",
           "why": "THE ONLY EXPLICITLY PUBLISHED CURRENCY BASKET IN THE DESK'S ROSTER, which "
                  "makes the pula's rand beta measurable rather than estimated -- the reason "
                  "SA-G is a domain and not a sentence"},
    "mz": {"name": "Banco de Moçambique", "framework": "managed_float_with_a_policy_rate",
           "rate": "the MIMO rate, announced by the Comité de Política Monetária on a published "
                   "calendar, with the statement issued in Portuguese",
           "root": "https://www.bancomoc.mz",
           "why": "the only one of the five with an IMF Extended Credit Facility and therefore "
                  "the only one with a DISBURSING review clock; the metical's stability since "
                  "2021 is an administered outcome and must be read as one"},
    "ao": {"name": "Banco Nacional de Angola (BNA)",
           "framework": "managed_float_with_published_auctions",
           "rate": "the BNA taxa básica de juro, announced by the Comité de Política Monetária; "
                   "the operative instrument is the FX auction allocation to the banks",
           "root": "https://www.bna.ao",
           "why": "an oil-funded FX supply with published auctions: when the barrel falls the "
                  "allocation falls and the informal premium widens, which is a cleaner "
                  "transmission than any interest-rate channel in this pack"},
    "na": {"name": "Bank of Namibia", "framework": "currency_union_peg",
           "rate": "the repo rate, announced at scheduled MPC meetings, and in practice tracking "
                   "the SARB's because a 1:1 peg with an open capital account leaves no room",
           "root": "https://www.bon.com.na",
           "why": "THE CONTROL FOR THE WHOLE PACK: a central bank with no independent exchange "
                  "rate at all, so anything that moves in Namibia and not in South Africa is "
                  "real and anything that moves in both is the rand"},
}

# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "RBZ willing-buyer-willing-seller interbank exchange rate",
     "local": "published each business day, Africa/Harare (UTC+2)",
     "time_utc": "08:00", "time_utc_dst": "08:00",
     "dst_rule": "none: CAT is UTC+2 year-round",
     "instruments": ("XAUUSD", "USDZAR"), "window_minutes": 60,
     "why": "the official rate the customs value and the surrender requirement are struck at; its "
            "gap to the private trackers' street rate is the regime-stress state SA-C conditions "
            "on, and the gap is the whole measurement"},
    {"name": "Bank of Botswana daily pula fixing against the published basket",
     "local": "published each business day, Africa/Gaborone (UTC+2)",
     "time_utc": "08:00", "time_utc_dst": "08:00", "dst_rule": "none",
     "instruments": ("USDZAR", "EURZAR"), "window_minutes": 60,
     "why": "THE ONLY FIXING IN THIS PACK WITH A PUBLISHED FORMULA BEHIND IT: the basket weights "
            "and the crawl are announced, so the pula's rand content is arithmetic and the "
            "residual is the measurement"},
    {"name": "Banco de Moçambique mercado monetário interbancário reference rate",
     "local": "published each business day, Africa/Maputo (UTC+2)",
     "time_utc": "08:00", "time_utc_dst": "08:00", "dst_rule": "none",
     "instruments": ("XALUSD", "XNGUSD"), "window_minutes": 60,
     "why": "an administered-stability rate: a long flat stretch here is evidence about the "
            "central bank's allocation and not about the balance of payments"},
    {"name": "Banco Nacional de Angola taxa de referência and the FX auction result",
     "local": "the auction is held and its allocation published on announced days, Africa/Luanda "
              "(UTC+1)",
     "time_utc": "11:00", "time_utc_dst": "11:00", "dst_rule": "none",
     "instruments": ("XBRUSD", "XTIUSD"), "window_minutes": 90,
     "why": "the auction ALLOCATION is the quantity read that a managed rate hides; it is the "
            "cleanest published measure of the oil-to-FX transmission anywhere in this pack"},
    {"name": "Bank of Namibia / SARB par value inside the Common Monetary Area",
     "local": "the peg is structural rather than fixed daily; the SARB's own rand reference is "
              "the operative fixing",
     "time_utc": "13:00", "time_utc_dst": "13:00", "dst_rule": "none",
     "instruments": ("USDZAR", "ZARJPY"), "window_minutes": 30,
     "why": "there is no separate Namibian fixing to strike: at 1:1 the rand fixing IS the "
            "Namibian one, which is exactly why NAD is labelled EXACT and not PROXY"},
    {"name": "LBMA platinum and palladium price auctions",
     "local": "09:45 and 14:00 Europe/London", "time_utc": "14:00", "time_utc_dst": "13:00",
     "dst_rule": "GMT/BST", "instruments": ("XPTUSD", "XPDUSD"), "window_minutes": 15,
     "why": "the benchmark Great Dyke concentrate is valued against, and the reference in every "
            "offtake and royalty calculation the Zimbabwean ministry publishes"},
    {"name": "LBMA gold price PM auction",
     "local": "15:00 Europe/London", "time_utc": "15:00", "time_utc_dst": "14:00",
     "dst_rule": "GMT/BST", "instruments": ("XAUUSD",), "window_minutes": 15,
     "why": "the price Fidelity Gold Refinery's deliveries and the RBZ's gold-backed instruments "
            "are referenced to; the small-scale miner's payout is a published discount to it"},
    {"name": "LME aluminium official settlement",
     "local": "the second ring, Europe/London", "time_utc": "12:55", "time_utc_dst": "11:55",
     "dst_rule": "GMT/BST", "instruments": ("XALUSD",), "window_minutes": 15,
     "why": "Mozal's output is LME-grade primary aluminium and its revenue is struck against this "
            "settlement, which is what makes a Cahora Bassa power interruption an XALUSD event"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "De Beers sales cycle close and the revenue publication", "kind": "day_of_month",
     "days": (1, 15), "months": (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12), "roll": "next",
     "window_utc": ("06:00", "16:00"), "instruments": ("US500", "UK100", "USDZAR"),
     "why": "TEN CYCLES A YEAR, each closing on a published date with a revenue number released "
            "within days: the highest-frequency read on global luxury demand that exists, and the "
            "dates are De Beers' own calendar rather than a rule this pack may invent"},
    {"name": "RBZ Monetary Policy Statement and the statutory-instrument gazette",
     "kind": "month_end", "roll": "previous", "window_utc": ("08:00", "16:00"),
     "instruments": ("XAUUSD", "XPTUSD", "USDZAR"),
     "why": "the Statements land in February and August but the BINDING acts are statutory "
            "instruments gazetted on Fridays; Veritas publishes the gazette within days and that "
            "is the datable event, not the speech"},
    {"name": "Bank of Botswana Monetary Policy Statement and the annual crawl announcement",
     "kind": "day_of_month", "days": (1,), "months": (2,), "roll": "next",
     "window_utc": ("08:00", "14:00"), "instruments": ("USDZAR", "EURZAR", "ZARJPY"),
     "why": "the year's rate of crawl and any basket reweighting are announced here; it is the "
            "one date in this pack on which a published FX parameter actually changes"},
    {"name": "Angolan monthly crude export loading programme", "kind": "day_of_month",
     "days": (10, 20), "months": (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12), "roll": "next",
     "window_utc": ("08:00", "16:00"), "instruments": ("XBRUSD", "XTIUSD"),
     "why": "Angola's loading programme for the month two months ahead circulates mid-month and "
            "is the physical counterpart of the OPEC quota argument that ended in the 2024 exit"},
    {"name": "OPEC Monthly Oil Market Report and the secondary-source production table",
     "kind": "day_of_month", "days": (12,),
     "months": (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12), "roll": "next",
     "window_utc": ("11:00", "14:00"), "instruments": ("XBRUSD", "XTIUSD"),
     "why": "the secondary-source estimate is the number Angola disputed on its way out; after "
            "2024-01-01 Angola appears there as a non-member and the series changes meaning"},
    {"name": "SACU revenue-share transfer to Botswana, Namibia, Lesotho and Eswatini",
     "kind": "quarter_end", "roll": "next", "window_utc": ("06:00", "14:00"),
     "instruments": ("USDZAR",),
     "why": "a PUBLISHED, FORMULA-DRIVEN fiscal transfer out of a common customs pool, paid "
            "quarterly, and large enough to be the single biggest revenue line in two of the "
            "five budgets; it is the most mechanical fiscal series in this pack"},
    {"name": "Fiscal year ends: 31 March for BW and NA, 31 December for ZW, MZ and AO",
     "kind": "fiscal_year_end", "roll": "previous", "window_utc": ("06:00", "16:00"),
     "instruments": ("XAUUSD", "XPTUSD", "USDZAR"),
     "why": "royalty rates, export levies, beneficiation deadlines and the surrender requirement "
            "are all BUDGET instruments and change on these boundaries -- and the boundary is not "
            "the same date in all five, which a pooled regional study gets wrong"},
    {"name": "Month-end importer FX demand under an auction or allocation regime",
     "kind": "month_end", "roll": "previous", "window_utc": ("06:00", "14:00"),
     "instruments": ("XBRUSD", "WHEAT", "CORN"),
     "why": "fuel, wheat and fertiliser letters of credit settle into the last business days; in "
            "Angola and Zimbabwe that is when the allocation queue is longest and the informal "
            "premium widest"},
)

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Zimbabwe Stock Exchange (ZSE) -- the ZiG-denominated board",
     "index_symbols": (),
     "open_local": "09:00", "close_local": "15:30", "open_utc": "07:00", "close_utc": "13:30",
     "dst_rule": "none: CAT is UTC+2 year-round",
     "auction": "a continuous session with opening and closing calls on a small board where a "
                "single block can set the day",
     "expiry_rule": "no listed derivatives; there is no expiry clock to mine",
     "holidays": "the Zimbabwean national calendar with the Sunday-to-Monday substitution",
     "notes": "NO CFD IS QUOTED ON THE ZSE and none of its listings is executable here. What is "
              "READABLE is the ZSE-versus-VFEX spread: the same economy priced in a collapsing "
              "local unit and in dollars at once. Old Mutual's dual listing was the classic "
              "implied-rate observable until its ZSE suspension in June 2020 switched it OFF -- "
              "a dated end to a series, which is itself the measurement"},
    {"name": "Victoria Falls Stock Exchange (VFEX) -- USD-denominated, opened 2020",
     "index_symbols": (),
     "open_local": "09:00", "close_local": "15:30", "open_utc": "07:00", "close_utc": "13:30",
     "dst_rule": "none",
     "auction": "a thin continuous board created explicitly to list and settle in US dollars",
     "expiry_rule": "none",
     "holidays": "the Zimbabwean national calendar",
     "notes": "THE DOLLARISATION OBSERVABLE OF SA-E. A migration of listings from the ZSE to the "
              "VFEX is a company choosing to be priced in dollars, which is a measurable, dated "
              "vote on the local currency by the people with the most at stake"},
    {"name": "Botswana Stock Exchange (BSE) -- domestic and foreign boards",
     "index_symbols": (),
     "open_local": "10:00", "close_local": "13:00", "open_utc": "08:00", "close_utc": "11:00",
     "dst_rule": "none",
     "auction": "a short call-and-continuous session on a board dominated by banks and the "
                "cross-listed mining names",
     "expiry_rule": "no listed derivatives",
     "holidays": "the Botswana national calendar including the two-day New Year and Botswana Day "
                 "pairs and the Sunday-to-Monday substitution",
     "notes": "the domestic company index versus the foreign company index is the local-versus-"
              "cross-listed split, and it moves when diamond revenue moves the domestic economy "
              "without touching the cross-listed miners"},
    {"name": "Bolsa de Valores de Moçambique (BVM) -- mostly a bond board",
     "index_symbols": (),
     "open_local": "09:00", "close_local": "14:00", "open_utc": "07:00", "close_utc": "12:00",
     "dst_rule": "none",
     "auction": "a thin board whose real content is government and corporate paper rather than "
                "equity",
     "expiry_rule": "none",
     "holidays": "the Mozambican national calendar, which has NO Good Friday and NO Monday "
                 "substitution -- two asymmetries a pooled regional calendar gets wrong",
     "notes": "REGISTERED AS A YIELD SOURCE, NOT A TAPE: the domestic bond yields are the only "
              "public Mozambican term structure, and there is no equity depth worth conditioning "
              "a week on. Saying so is the measurement (L1.28a)"},
    {"name": "BODIVA -- Bolsa de Dívida e Valores de Angola",
     "index_symbols": (),
     "open_local": "09:00", "close_local": "15:00", "open_utc": "08:00", "close_utc": "14:00",
     "dst_rule": "none: WAT is UTC+1 year-round",
     "auction": "an OTC debt board: Angolan treasury bonds and bills, with equity listings still "
                "a stated intention rather than a market",
     "expiry_rule": "none",
     "holidays": "the Angolan national calendar including Carnival Tuesday",
     "notes": "the kwanza-denominated yield curve is the only domestic Angolan price series that "
              "exists at all; there is no equity tape and the pack does not invent one"},
    {"name": "Namibian Stock Exchange (NSX) -- local board and JSE dual listings",
     "index_symbols": (),
     "open_local": "09:00", "close_local": "17:00", "open_utc": "07:00", "close_utc": "15:00",
     "dst_rule": "none: Namibia abolished its winter-time switch in 2017",
     "auction": "a board whose capitalisation is overwhelmingly South African dual listings; the "
                "LOCAL index is the Namibian half and the two must never be used interchangeably",
     "expiry_rule": "no local derivatives; the dual listings expire on the JSE's clock",
     "holidays": "the Namibian national calendar with the Sunday-to-Monday substitution",
     "notes": "THE OVERALL INDEX IS A JOHANNESBURG INDEX WEARING A NAMIBIAN FLAG. A study that "
              "uses it as a Namibian observable is measuring South Africa, which is the exact "
              "error the CMA makes easy and the reason SA-O uses the LOCAL index only"},
)

SESSION_WINDOWS: tuple[dict[str, Any], ...] = (
    {"name": "sa_cat_morning", "start_utc": "06:00", "end_utc": "09:00",
     "notes": "the Southern African business morning (08:00-11:00 CAT). The RBZ and BoB fixings, "
              "the Maputo interbank and the local boards' opens all sit here, and because NO "
              "country in this pack observes daylight saving the window is stable in UTC all year"},
    {"name": "sa_luanda_auction", "start_utc": "09:00", "end_utc": "13:00",
     "notes": "the Angolan business day (10:00-14:00 WAT, UTC+1), when the BNA's FX auction is "
              "held and allocated -- one hour behind the other four, which is a real offset and "
              "not a rounding"},
    {"name": "sa_london_overlap", "start_utc": "08:00", "end_utc": "15:00",
     "notes": "the overlap with London, when the PGM, gold, aluminium and energy complexes are "
              "liquid and a Southern African physical observable can actually reach a price; the "
              "LBMA platinum and palladium auctions and the LME rings are inside it"},
    {"name": "sa_jse_session", "start_utc": "07:00", "end_utc": "15:00",
     "notes": "the Johannesburg session, which is also the NSX's because of the dual listings and "
              "is the liquidity window for every rand cross in this pack"},
    {"name": "sa_announcement_afternoon", "start_utc": "11:00", "end_utc": "16:00",
     "notes": "the Monetary Policy Statements, the budget speeches, the De Beers cycle releases "
              "and the OPEC MOMR all land in this window; the Zimbabwean gazette is published on "
              "Fridays and is the one that arrives by document rather than by press conference"},
)

RELEASE_CLASSES: tuple[dict[str, Any], ...] = (
    {"name": "De Beers rough diamond sales cycle revenue", "cadence": "ten times a year",
     "time_utc": "12:00", "source": "De Beers Group / Anglo American",
     "actual_series": "DEBEERS:cycle_revenue_usd", "expected_series": "UNMEASURED",
     "notes": "THE HIGHEST-FREQUENCY LUXURY-DEMAND PRINT IN EXISTENCE and essentially unused by "
              "systematic desks: ten dated revenue numbers a year from the seller with the "
              "largest share of the world's rough supply"},
    {"name": "Reserve Bank of Zimbabwe Monetary Policy Statement and the ZiG reserve cover",
     "cadence": "semi-annual with off-cycle statements", "time_utc": "12:00",
     "source": "Reserve Bank of Zimbabwe", "actual_series": "RBZ:reserve_cover",
     "expected_series": "UNMEASURED",
     "notes": "the reserve cover is the ZiG's whole claim on credibility and the only number that "
              "can falsify it; the statements are irregular and the gazette is the hard date"},
    {"name": "ZIMSTAT consumer price index (blended, then ZiG-rebased)", "cadence": "monthly",
     "time_utc": "10:00", "source": "Zimbabwe National Statistics Agency",
     "actual_series": "ZIMSTAT:cpi", "expected_series": "UNMEASURED",
     "notes": "A SERIES WITH DOCUMENTED BREAKS, NOT A SERIES WITH NOISE: the year-on-year rate "
              "was suspended in 2019 and the index has been re-based more than once, including "
              "on the ZiG. ZIMSTAT documents each break and this pack refuses to splice them"},
    {"name": "Bank of Botswana Monetary Policy Statement, basket weights and crawl rate",
     "cadence": "annual statement plus scheduled MPC meetings", "time_utc": "10:00",
     "source": "Bank of Botswana", "actual_series": "BOB:crawl_rate",
     "expected_series": "UNMEASURED",
     "notes": "the one release in this pack that changes a PUBLISHED FX parameter; a reweighting "
              "of the basket is a step change in the pula's rand content and is datable to the day"},
    {"name": "Statistics Botswana international merchandise trade (diamond exports)",
     "cadence": "monthly", "time_utc": "10:00", "source": "Statistics Botswana",
     "actual_series": "STATSBOTS:diamond_exports", "expected_series": "n/a",
     "notes": "value and carats, which together give a realised price per carat -- the nearest "
              "thing to a diamond price index that a statistics office publishes anywhere"},
    {"name": "Banco de Moçambique MIMO rate decision and the Comité statement",
     "cadence": "roughly every six weeks", "time_utc": "14:00", "source": "Banco de Moçambique",
     "actual_series": "BM:mimo", "expected_series": "UNMEASURED",
     "notes": "published in PORTUGUESE first and sometimes only; an English-only crawl reads the "
              "summary a wire service wrote about it, hours later and shorter"},
    {"name": "Banco Nacional de Angola FX auction allocation and reserves",
     "cadence": "weekly to fortnightly", "time_utc": "12:00",
     "source": "Banco Nacional de Angola", "actual_series": "BNA:auction_allocation",
     "expected_series": "n/a",
     "notes": "THE QUANTITY READ: how many dollars the state actually sold to the banks, which is "
              "the oil-to-FX transmission made visible and is published in Portuguese"},
    {"name": "OPEC Monthly Oil Market Report secondary-source production",
     "cadence": "monthly", "time_utc": "12:00", "source": "OPEC Secretariat",
     "actual_series": "OPEC:momr_secondary", "expected_series": "n/a",
     "notes": "the table Angola disputed on the way out; from the January 2024 issue Angola is a "
              "non-member and the same series is measuring a different group"},
    {"name": "ANPG Angolan crude export loading programme and concession awards",
     "cadence": "monthly / irregular", "time_utc": "UNMEASURED",
     "source": "Agência Nacional de Petróleo, Gás e Biocombustíveis",
     "actual_series": "ANPG:loading_programme", "expected_series": "n/a",
     "notes": "the physical counterpart of the quota argument; circulated to traders and reported "
              "in the Portuguese press before it appears anywhere in English"},
    {"name": "Bank of Namibia Quarterly Bulletin: reserves, SACU receipts and the peg",
     "cadence": "quarterly", "time_utc": "10:00", "source": "Bank of Namibia",
     "actual_series": "BON:reserves", "expected_series": "n/a",
     "notes": "the reserve position is what BACKS the 1:1 peg, and the SACU receipts line is the "
              "largest single item in the national budget"},
    {"name": "Namibia Statistics Agency CPI and trade statistics", "cadence": "monthly",
     "time_utc": "10:00", "source": "Namibia Statistics Agency", "actual_series": "NSA:cpi",
     "expected_series": "UNMEASURED",
     "notes": "Namibian CPI tracks South African CPI closely BY CONSTRUCTION under the peg, so "
              "the informative quantity is the residual and never the level"},
    {"name": "Zambezi River Authority Kariba lake level bulletin", "cadence": "weekly",
     "time_utc": "08:00", "source": "Zambezi River Authority", "actual_series": "ZRA:kariba_level",
     "expected_series": "n/a",
     "notes": "a WEEKLY, PUBLISHED, PHYSICAL number that sets how much power Zimbabwe and Zambia "
              "can generate; it is the highest-frequency real-economy series in this pack"},
    {"name": "Mozambique LNG and Coral South project statements", "cadence": "irregular",
     "time_utc": "UNMEASURED", "source": "TotalEnergies / Eni / ENH / INP",
     "actual_series": "INP:lng_milestones", "expected_series": "n/a",
     "notes": "a project timetable is a release class in its own right here: force majeure, its "
              "lifting, FID and first cargo are each a dated step in a global supply schedule"},
    {"name": "National budget statements (November for ZW, February for BW and NA, December for "
             "MZ and AO)", "cadence": "annual", "time_utc": "12:00",
     "source": "the five ministries of finance", "actual_series": "MOF:budget",
     "expected_series": "n/a",
     "notes": "royalty rates, export levies, beneficiation deadlines and surrender requirements "
              "are BUDGET instruments; the speech is the event and the Finance Act or the "
              "gazetted statutory instrument is the citation"},
)
# ------------------------------------------------------------------- the five civil calendars
#: ALL FIVE ARE GREGORIAN, which makes them look easy and is exactly the trap. THREE OF THE FIVE
#: -- Zimbabwe, Botswana and Namibia -- carry a SUNDAY-TO-MONDAY SUBSTITUTION in their Public
#: Holidays Acts, and Mozambique and Angola do not. A regional study that applies one rule to all
#: five silently misaligns every event window that lands near a weekend holiday, which is the
#: single most common way an event study quietly loses its treatment days. The substitution is
#: DERIVED here from the weekday, never typed, so it cannot go stale.
#:
#: The movable feasts are WESTERN Easter, computed with the anonymous Gregorian algorithm: Good
#: Friday, Holy Saturday (Botswana), Easter Monday, Ascension Day (Easter + 39) and Carnival
#: Tuesday (Easter - 47, Angola). Mozambique has NO Good Friday and NO Easter Monday at all --
#: its 25 December is the Dia da Família rather than Christmas -- and that asymmetry is real.
def western_easter(year: int) -> date:
    """Easter Sunday in the Gregorian calendar, by the ANONYMOUS GREGORIAN ALGORITHM.

    Four of the five jurisdictions hang holidays off this date and the fifth hangs Carnival off
    it backwards. Typing the dates would work for three years and break in the fourth.
    """
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    lam = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * lam) // 451
    month, day = divmod(h + lam - 7 * m + 114, 31)
    return date(year, month, day + 1)


def good_friday(year: int) -> date:
    return western_easter(year) - timedelta(days=2)


def holy_saturday(year: int) -> date:
    """Botswana closes for Holy Saturday and none of the other four does."""
    return western_easter(year) - timedelta(days=1)


def easter_monday(year: int) -> date:
    return western_easter(year) + timedelta(days=1)


def ascension_day(year: int) -> date:
    """Botswana and Namibia close forty days after Easter; the other three do not."""
    return western_easter(year) + timedelta(days=39)


def carnival_tuesday(year: int) -> date:
    """Angola's Carnaval, the Tuesday before Ash Wednesday: forty-seven days before Easter."""
    return western_easter(year) - timedelta(days=47)


def nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """The n-th `weekday` (Mon=0) of a month. Zimbabwe's Heroes' Day is the SECOND MONDAY of
    August and Botswana's President's Day is the THIRD MONDAY of July, and both are commonly
    mis-typed as fixed dates because in any single year they look like one."""
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return date(year, month, 1 + offset + 7 * (n - 1))


#: WHICH JURISDICTIONS SUBSTITUTE. Zimbabwe's Public Holidays and Prohibition of Business Act,
#: Botswana's Public Holidays Act and Namibia's Public Holidays Act all provide that a public
#: holiday falling on a SUNDAY is observed on the following Monday. Mozambique and Angola have no
#: such provision, and Angola's separate "ponte" practice is NOT derived here because this pack
#: cannot cite the operative article -- an undeclared rule is worse than a declared absence.
MONDAY_SUBSTITUTION: frozenset[str] = frozenset({"zw", "bw", "na"})
SUBSTITUTION_STATUS: dict[str, str] = {
    "zw": "DERIVED from the Public Holidays and Prohibition of Business Act: a holiday falling "
          "on a Sunday is observed on the following Monday",
    "bw": "DERIVED from the Public Holidays Act: a holiday falling on a Sunday is observed on "
          "the following Monday, and because Botswana pairs its holidays (1-2 January, 30 "
          "September-1 October, President's Day Monday and Tuesday, 25-26 December) a Sunday in "
          "a pair pushes past the day already taken",
    "na": "DERIVED from the Public Holidays Act 1990: a holiday falling on a Sunday is observed "
          "on the following Monday",
    "mz": "NONE. Mozambique's holiday law carries no weekend substitution, so a Sunday holiday "
          "costs no session -- and applying the neighbours' rule invents a closure",
    "ao": "NONE DERIVED. Angola carries a 'ponte' practice around midweek holidays that this "
          "pack cannot cite to an article, so it is DECLARED UNMEASURED rather than guessed "
          "(L1.28a); the fixed dates and Carnaval are computed and the bridge days are not",
}


def substitute_sundays(table: Mapping[date, str], jurisdiction: str) -> dict[date, str]:
    """Apply the Sunday-to-Monday substitution for the jurisdictions whose statute carries it.

    THE RULE IS DERIVED AND NOT TYPED, which is the whole point: whether 2025-05-25 costs Harare
    a Monday depends on the weekday that date happens to land on, and a typed table is right
    until the first year somebody forgets to extend it. When the following Monday is ALREADY a
    holiday -- which Botswana's paired holidays make common -- the substituted day moves on to
    the next day that is free, so a closure is never silently lost by collision.
    """
    out = dict(table)
    if str(jurisdiction).lower() not in MONDAY_SUBSTITUTION:
        return dict(sorted(out.items()))
    for day, name in sorted(table.items()):
        if day.weekday() != 6:               # Sunday is 6
            continue
        moved = day + timedelta(days=1)
        while moved in out:
            moved += timedelta(days=1)
        if moved.year == day.year:
            out[moved] = f"{name} (observed: Sunday substitution)"
    return dict(sorted(out.items()))


FIXED_ZW: tuple[tuple[int, int, str], ...] = (
    (1, 1, "New Year's Day"),
    (2, 21, "Robert Gabriel Mugabe National Youth Day"),
    (4, 18, "Independence Day"),
    (5, 1, "Workers' Day"),
    (5, 25, "Africa Day"),
    (12, 22, "Unity Day"),
    (12, 25, "Christmas Day"),
    (12, 26, "Boxing Day"),
)
FIXED_BW: tuple[tuple[int, int, str], ...] = (
    (1, 1, "New Year's Day"),
    (1, 2, "New Year's Holiday"),
    (5, 1, "Labour Day"),
    (7, 1, "Sir Seretse Khama Day"),
    (9, 30, "Botswana Day"),
    (10, 1, "Botswana Day Holiday"),
    (12, 25, "Christmas Day"),
    (12, 26, "Boxing Day"),
)
FIXED_MZ: tuple[tuple[int, int, str], ...] = (
    (1, 1, "Dia da Fraternidade Universal (Ano Novo)"),
    (2, 3, "Dia dos Heróis Moçambicanos"),
    (4, 7, "Dia da Mulher Moçambicana"),
    (5, 1, "Dia Internacional dos Trabalhadores"),
    (6, 25, "Dia da Independência Nacional"),
    (9, 7, "Dia da Vitória"),
    (9, 25, "Dia das Forças Armadas de Libertação Nacional"),
    (10, 4, "Dia da Paz e Reconciliação"),
    (12, 25, "Dia da Família"),
)
FIXED_AO: tuple[tuple[int, int, str], ...] = (
    (1, 1, "Dia de Ano Novo"),
    (1, 4, "Dia dos Mártires da Repressão Colonial"),
    (2, 4, "Dia do Início da Luta Armada de Libertação Nacional"),
    (3, 8, "Dia Internacional da Mulher"),
    (3, 23, "Dia da Libertação da África Austral"),
    (4, 4, "Dia da Paz e Reconciliação Nacional"),
    (5, 1, "Dia Internacional do Trabalhador"),
    (9, 17, "Dia do Fundador da Nação e do Herói Nacional"),
    (11, 2, "Dia dos Finados"),
    (11, 11, "Dia da Independência Nacional"),
    (12, 25, "Dia de Natal e da Família"),
)
FIXED_NA: tuple[tuple[int, int, str], ...] = (
    (1, 1, "New Year's Day"),
    (3, 21, "Independence Day"),
    (5, 1, "Workers' Day"),
    (5, 4, "Cassinga Day"),
    (5, 25, "Africa Day"),
    (8, 26, "Heroes' Day"),
    (12, 10, "International Human Rights Day"),
    (12, 25, "Christmas Day"),
    (12, 26, "Family Day"),
)

#: Dated facts no recurring rule produces. Not closures -- events the era table conditions on.
DECLARED_EVENTS: dict[date, str] = {
    date(2024, 4, 5): "the ZiG is introduced by the Reserve Bank of Zimbabwe, structured against "
                      "gold and foreign exchange reserves with a published cover",
    date(2024, 9, 27): "the ZiG is devalued by roughly 43% in a single step, five months after "
                       "its introduction",
    date(2024, 1, 1): "Angola's withdrawal from OPEC takes effect, announced 2023-12-21",
    date(2025, 1, 15): "Shell writes down its Orange Basin PEL 39 interest, the first negative "
                       "dated milestone in the Namibian appraisal clock",
}


def _apply(out: dict[date, str], day: date, name: str) -> None:
    """Record a closure, joining names when two holidays land on the same day.

    In 2025 Zimbabwe's Independence Day fell on Good Friday, so one date carried two statutory
    holidays and the country lost ONE session, not two. A dict that silently overwrites loses the
    fact that it was a double; a naive count that adds them invents a session that never existed.
    """
    out[day] = f"{out[day]} + {name}" if day in out else name


def zimbabwean_holidays(year: int) -> dict[date, str]:
    """Zimbabwe's closed days: eight fixed solar dates, the Western Easter triple, HEROES' DAY on
    the SECOND MONDAY OF AUGUST with Defence Forces Day the following Tuesday, and the Sunday
    substitution. The second-Monday rule is why 11-12 August is a 2025 fact and not a date."""
    out: dict[date, str] = {}
    for m, d, name in FIXED_ZW:
        _apply(out, date(year, m, d), name)
    _apply(out, good_friday(year), "Good Friday")
    _apply(out, holy_saturday(year), "Easter Saturday")
    _apply(out, easter_monday(year), "Easter Monday")
    heroes = nth_weekday(year, 8, 0, 2)
    _apply(out, heroes, "Heroes' Day")
    _apply(out, heroes + timedelta(days=1), "Defence Forces Day")
    return substitute_sundays(out, "zw")


def botswanan_holidays(year: int) -> dict[date, str]:
    """Botswana's closed days: four PAIRED fixed holidays, the Western Easter triple plus
    Ascension Day, PRESIDENT'S DAY on the third Monday of July with the following Tuesday, and
    the Sunday substitution that has to step past a day already taken."""
    out: dict[date, str] = {}
    for m, d, name in FIXED_BW:
        _apply(out, date(year, m, d), name)
    _apply(out, good_friday(year), "Good Friday")
    _apply(out, holy_saturday(year), "Holy Saturday")
    _apply(out, easter_monday(year), "Easter Monday")
    _apply(out, ascension_day(year), "Ascension Day")
    president = nth_weekday(year, 7, 0, 3)
    _apply(out, president, "President's Day")
    _apply(out, president + timedelta(days=1), "President's Day Holiday")
    return substitute_sundays(out, "bw")


def mozambican_holidays(year: int) -> dict[date, str]:
    """Mozambique's closed days: NINE FIXED SOLAR DATES AND NOTHING ELSE. No Good Friday, no
    Easter Monday, no Ascension, and NO SUNDAY SUBSTITUTION. Carnaval is observed in Maputo and
    some municipalities as a tolerância de ponto and is NOT a statutory national closure, so it
    is named in the rule and kept out of the table."""
    out: dict[date, str] = {}
    for m, d, name in FIXED_MZ:
        _apply(out, date(year, m, d), name)
    return dict(sorted(out.items()))


def angolan_holidays(year: int) -> dict[date, str]:
    """Angola's closed days: eleven fixed solar dates, CARNAVAL on the Tuesday before Ash
    Wednesday and Sexta-Feira Santa. The 'ponte' bridge practice around midweek holidays is
    DECLARED UNMEASURED rather than derived, because this pack cannot cite the article."""
    out: dict[date, str] = {}
    for m, d, name in FIXED_AO:
        _apply(out, date(year, m, d), name)
    _apply(out, carnival_tuesday(year), "Carnaval")
    _apply(out, good_friday(year), "Sexta-Feira Santa")
    return dict(sorted(out.items()))


def namibian_holidays(year: int) -> dict[date, str]:
    """Namibia's closed days: nine fixed solar dates, Good Friday, Easter Monday, Ascension Day
    and the Sunday substitution. Namibia abolished its winter-time switch in 2017, so unlike
    every pre-2018 Namibian series the session clock no longer moves in April and September."""
    out: dict[date, str] = {}
    for m, d, name in FIXED_NA:
        _apply(out, date(year, m, d), name)
    _apply(out, good_friday(year), "Good Friday")
    _apply(out, easter_monday(year), "Easter Monday")
    _apply(out, ascension_day(year), "Ascension Day")
    return substitute_sundays(out, "na")


JURISDICTION_HOLIDAY_FN: dict[str, Any] = {
    "zw": zimbabwean_holidays, "bw": botswanan_holidays, "mz": mozambican_holidays,
    "ao": angolan_holidays, "na": namibian_holidays,
}


def national_holidays(year: int) -> dict[date, str]:
    """EVERY closed day in the five jurisdictions, TAGGED with the countries that close.

    A union table, because this pack answers for five countries at once and a day that closes
    Gaborone is an ordinary session in Luanda. The tag is what keeps a study from treating a
    one-country closure as a regional one -- and in this pack only 1 January and 1 May close all
    five, which is worth knowing before anybody builds a "Southern African holiday" sample.
    """
    tagged: dict[date, list[str]] = {}
    names: dict[date, str] = {}
    for code, fn in JURISDICTION_HOLIDAY_FN.items():
        for day, name in fn(year).items():
            tagged.setdefault(day, []).append(code.upper())
            names.setdefault(day, name)
    return {day: f"{names[day]} [{'+'.join(sorted(codes))}]"
            for day, codes in sorted(tagged.items())}


def market_holidays(year: int) -> dict[date, str]:
    """The weekday closures only. A Saturday holiday costs no session, and because three of the
    five substitute a SUNDAY onto the Monday the substituted Monday IS in this table while the
    Sunday itself is not -- which is exactly the behaviour a typed table gets wrong."""
    return {d: n for d, n in national_holidays(year).items() if d.weekday() < 5}


def is_market_holiday(day: date) -> bool:
    return day in market_holidays(day.year)


def closed_in(code: str, day: date) -> bool:
    """True when THIS jurisdiction's cash market is closed on this day."""
    fn = JURISDICTION_HOLIDAY_FN.get(str(code).lower())
    return day in fn(day.year) if fn is not None else False


def all_five_closed(year: int) -> tuple[date, ...]:
    """The days on which ALL FIVE close. There are very few, and a regional holiday study that
    does not start here is pooling four ordinary sessions with one closure."""
    tables = [set(fn(year)) for fn in JURISDICTION_HOLIDAY_FN.values()]
    return tuple(sorted(set.intersection(*tables)))


def substituted_mondays(year: int) -> dict[date, tuple[str, ...]]:
    """Every Monday in a year that is a closure ONLY because a Sunday holiday moved onto it,
    with the jurisdictions it closes. These are the days an event study loses if it applies one
    weekend rule to all five: real closures in ZW, BW and NA with nothing on the statute."""
    out: dict[date, list[str]] = {}
    for code in sorted(MONDAY_SUBSTITUTION):
        for day, name in JURISDICTION_HOLIDAY_FN[code](year).items():
            if "Sunday substitution" in name:
                out.setdefault(day, []).append(code)
    return {d: tuple(v) for d, v in sorted(out.items())}


HOLIDAYS_RULE: dict[str, Any] = {
    "kind": "computed_from_five_gregorian_calendars_with_three_substitution_regimes",
    "authority": "the Public Holidays and Prohibition of Business Act (Zimbabwe), the Public "
                 "Holidays Act (Botswana), Lei dos Feriados Nacionais (Mozambique), the Angolan "
                 "feriados nacionais law published in the Diário da República, and the Public "
                 "Holidays Act 1990 (Namibia)",
    "rule": "ALL FIVE RUN THE GREGORIAN CALENDAR and every movable date here is COMPUTED. Western "
            "Easter comes from the ANONYMOUS GREGORIAN ALGORITHM; Good Friday is two days before "
            "it, Easter Monday one day after, Ascension Day thirty-nine days after, and Angola's "
            "Carnaval forty-seven days before. ZIMBABWE adds eight fixed solar days (1 Jan, 21 "
            "Feb, 18 Apr, 1 May, 25 May, 22 Dec, 25 Dec, 26 Dec) plus HEROES' DAY ON THE SECOND "
            "MONDAY OF AUGUST with Defence Forces Day the following Tuesday -- which is why '11-12 "
            "August' is a 2025 fact and not a date. BOTSWANA adds four PAIRS (1-2 Jan, 30 Sep-1 "
            "Oct, President's Day on the third Monday of July with the Tuesday after, 25-26 Dec) "
            "plus Holy Saturday and Ascension Day. NAMIBIA adds nine fixed days including Cassinga "
            "Day (4 May) and Heroes' Day (26 Aug). MOZAMBIQUE has NINE FIXED DAYS AND NOTHING "
            "MOVABLE AT ALL -- no Good Friday, no Easter Monday, and 25 December is the Dia da "
            "Família rather than Christmas. ANGOLA has eleven fixed days plus Carnaval and "
            "Sexta-Feira Santa. THE SUNDAY-TO-MONDAY SUBSTITUTION IS DERIVED, NOT TYPED, and it "
            "applies in ZIMBABWE, BOTSWANA AND NAMIBIA ONLY: a holiday falling on a Sunday is "
            "observed on the following Monday, stepping past a Monday already taken. Mozambique "
            "and Angola carry no such rule, and applying one to them invents closures. NO "
            "DAYLIGHT SAVING anywhere: CAT is UTC+2 year-round in ZW, BW, MZ and NA and WAT is "
            "UTC+1 in AO, and Namibia abolished its winter-time switch in 2017.",
    "years": (2024, 2025, 2026),
    "weekend": "Saturday and Sunday",
    "substitution_rule": "Sunday to the following Monday in ZW, BW and NA; NONE in MZ; "
                         "UNMEASURED for Angola's midweek 'ponte' practice",
    "substitution_status": SUBSTITUTION_STATUS,
    "national_rule": "see `rule`; `national_holidays(year)` is the computed union and the five "
                     "per-jurisdiction tables are `zimbabwean_holidays`, `botswanan_holidays`, "
                     "`mozambican_holidays`, `angolan_holidays` and `namibian_holidays`",
    "market_rule": "the union calendar on weekdays; each exchange keeps its own country's table, "
                   "which is why every union row is TAGGED with the countries that close",
    "carnival_rule": "Mozambique's Carnaval is a municipal tolerância de ponto rather than a "
                     "statutory national closure and is DELIBERATELY ABSENT from the table; "
                     "Angola's Carnaval IS statutory and is computed",
    "moving_feasts": "Easter and everything hung off it; Heroes' Day (2nd Monday of August, ZW) "
                     "and President's Day (3rd Monday of July, BW) are weekday rules and move "
                     "by up to six days a year",
    "table": {y: {d.isoformat(): n for d, n in national_holidays(y).items()}
              for y in (2024, 2025, 2026)},
    "status": {2024: "COMPUTED throughout; no typed date in any of the five",
               2025: "COMPUTED throughout",
               2026: "COMPUTED throughout -- these calendars are arithmetic, not a sighting, so "
                     "a 2026 row is as firm as a 2024 one",
               },
    "known_dates": {
        "2024-12-23": "ZIMBABWE: Unity Day 2024-12-22 fell on a SUNDAY, so the Monday was the "
                      "closure. A typed table that carries 22 December loses the session.",
        "2025-04-18": "ZIMBABWE: Independence Day and Good Friday fell on the SAME DAY, so the "
                      "country lost one session to two statutory holidays; a naive count of the "
                      "holiday list double-counts it",
        "2025-05-26": "ZIMBABWE: Africa Day 2025-05-25 fell on a Sunday, so the Monday closed",
        "2025-05-05": "NAMIBIA: Cassinga Day 2025-05-04 fell on a Sunday, so the Monday closed",
        "2025-08-11": "ZIMBABWE: Heroes' Day, the second Monday of August in 2025; in 2024 it "
                      "was the 12th and in 2026 it is the 10th",
        "2026-10-05": "MOZAMBIQUE: NOT a holiday. Peace Day 2026-10-04 falls on a Sunday and "
                      "Mozambique has no substitution, so the session is ordinary -- the exact "
                      "day a one-rule regional calendar invents a closure",
    },
    "fn": market_holidays,
    "national_fn": national_holidays,
    "zw_fn": zimbabwean_holidays,
    "bw_fn": botswanan_holidays,
    "mz_fn": mozambican_holidays,
    "ao_fn": angolan_holidays,
    "na_fn": namibian_holidays,
    "easter_fn": western_easter,
    "substitution_fn": substitute_sundays,
}

# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "De Beers rough diamond sales cycle results (ten cycles a year)",
     "root": "https://www.debeersgroup.com/media/company-news",
     "fields": ("cycle_number", "cycle_close_date", "sales_value_usd", "prior_cycle_value_usd",
                "prior_year_cycle_value_usd", "commentary"),
     "frequency": "ten times a year", "snapshot": "one sales cycle", "publish_utc": "12:00",
     "lag_days": 3, "licence": "free, public (company terms)", "available": True,
     "why": "THE HIGHEST-FREQUENCY PUBLISHED READ ON GLOBAL LUXURY DEMAND, from the seller with "
            "the largest share of the world's rough supply, on a dated calendar -- and it is "
            "essentially unused by systematic desks, which is the whole argument for SA-F",
     "pit_warning": "the release is a press statement rather than a statistical series; the "
                    "comparison figures are restated between releases and the FIRST print is "
                    "what a point-in-time cell must use"},
    {"name": "Statistics Botswana international merchandise trade: diamond value and carats",
     "root": "https://www.statsbots.org.bw",
     "fields": ("diamond_exports_value_bwp", "diamond_exports_carats", "total_exports",
                "imports_by_category", "trade_balance"),
     "frequency": "monthly", "snapshot": "calendar month", "publish_utc": "10:00",
     "lag_days": 60, "licence": "free, public", "available": True,
     "why": "value AND carats in the same table gives a realised price per carat -- the closest "
            "thing to a published diamond price index that any statistics office produces",
     "pit_warning": "revised for several months; the carat series is revised more than the value "
                    "series, so the derived price moves after the fact"},
    {"name": "Reserve Bank of Zimbabwe weekly exchange rate, gold deliveries and reserve cover",
     "root": "https://www.rbz.co.zw/index.php/research/markets/exchange-rates",
     "fields": ("wbws_rate", "reserve_cover_usd", "gold_backing_kg", "gold_deliveries_kg",
                "money_supply_zig"),
     "frequency": "weekly to monthly", "snapshot": "week or month", "publish_utc": "08:00",
     "lag_days": 7, "licence": "free, public", "available": True,
     "why": "the ZiG's reserve cover is the only number that can falsify its own design claim, "
            "and the gold delivery series is the physical flow behind the gold-backed instruments",
     "pit_warning": "the page OVERWRITES IN PLACE and the historical series is not always "
                    "downloadable; an un-archived week is UNMEASURED and is never interpolated"},
    {"name": "Private Zimbabwean parallel-market rate trackers",
     "root": "https://www.zimpricecheck.com",
     "fields": ("street_rate_usd", "official_rate_usd", "premium_pct", "observation_time"),
     "frequency": "daily", "snapshot": "same day", "publish_utc": "10:00", "lag_days": 0,
     "licence": "free, public (site terms)", "available": True,
     "why": "the ONLY daily high-frequency Zimbabwean nominal series that exists, and the "
            "regime-stress state SA-C conditions on. It is crowd-sourced, unaudited and "
            "labelled UNRELIABLE here, and kept at low weight rather than dropped -- a claim "
            "that looks unreliable is still a dated, testable claim",
     "pit_warning": "crowd-sourced, self-reported and re-stated; treat a single day's print as "
                    "an observation with error, never as a fixing"},
    {"name": "Banco Nacional de Angola FX auction allocation and reserves",
     "root": "https://www.bna.ao/estatisticas",
     "fields": ("auction_date", "allocated_usd", "reference_rate_aoa", "gross_reserves_usd",
                "banks_participating"),
     "frequency": "weekly to fortnightly", "snapshot": "one auction", "publish_utc": "12:00",
     "lag_days": 1, "licence": "free, public", "available": True,
     "why": "THE QUANTITY READ that a managed rate hides: how many dollars the state actually "
            "sold, which is the oil-to-FX transmission made visible on a weekly clock",
     "pit_warning": "published in Portuguese and sometimes only as a PDF; an English-only "
                    "collector sees a wire summary days later, if at all"},
    {"name": "Bank of Namibia Quarterly Bulletin: reserves, SACU receipts and the peg",
     "root": "https://www.bon.com.na/Publications",
     "fields": ("gross_reserves_nad", "import_cover_months", "sacu_receipts_nad",
                "repo_rate", "sarb_repo_spread"),
     "frequency": "quarterly", "snapshot": "calendar quarter", "publish_utc": "10:00",
     "lag_days": 75, "licence": "free, public", "available": True,
     "why": "the reserves BACK the 1:1 peg and the SACU line is the biggest revenue item in the "
            "budget; the repo spread to the SARB is the measure of how little room the peg leaves",
     "pit_warning": "quarterly and revised; it can date a regime and can never condition a week"},
    {"name": "Zambezi River Authority Kariba lake level and allocation bulletin",
     "root": "https://www.zambezira.org/hydrology/lake-levels",
     "fields": ("lake_level_masl", "usable_storage_pct", "allocation_bcm_zw",
                "allocation_bcm_zm", "inflow_forecast"),
     "frequency": "weekly", "snapshot": "same week", "publish_utc": "08:00", "lag_days": 3,
     "licence": "free, public", "available": True,
     "why": "a WEEKLY published physical number that decides how much power Zimbabwe and Zambia "
            "can generate, and therefore how much smelting and refining can actually run -- the "
            "highest-frequency real-economy series in this pack and the shared leg with "
            "`copperbelt`",
     "pit_warning": "the bulletin is published as a PDF and the archive is incomplete; a missing "
                    "week is UNMEASURED and this pack refuses to interpolate a reservoir"},
    {"name": "a CFTC, exchange or dealer positioning series in ZWG, BWP, MZN, AOA or NAD",
     "root": "", "fields": (), "frequency": "n/a", "snapshot": "", "publish_utc": "",
     "lag_days": 0, "licence": "", "available": False,
     "why": "DECLARED ABSENT: no future, no option and no COT contract exists anywhere for any of "
            "the five, and none is deliverable offshore. NAD is the one case where a positioning "
            "read EXISTS -- the ZAR COT -- and it is a position in SOUTH AFRICA that happens to "
            "be exactly convertible, which the pack states rather than quietly borrowing",
     "pit_warning": "DOES NOT EXIST for four of the five; for NAD the ZAR COT is an EXACT "
                    "substitute by the 1:1 peg and is `za`'s series, never this pack's"},
    {"name": "retail margin or client-flow statistics for any of the five",
     "root": "", "fields": (), "frequency": "n/a", "snapshot": "", "publish_utc": "",
     "lag_days": 0, "licence": "", "available": False,
     "why": "DECLARED ABSENT: Zimbabwean exchange control makes an offshore margin account "
            "unlawful for residents, Angola licenses no retail margin broker at all, and "
            "NBFIRA, the CMC, NAMFISA and the Mozambican regulator publish NO aggregate retail "
            "positioning, exposure or flow. Namibian retail flow is South African retail flow "
            "and belongs to `za`",
     "pit_warning": "DOES NOT EXIST: no microstructure claim in this pack may rest on a "
                    "retail-flow number, and the retail ecology is read from public communities "
                    "at FRINGE credibility instead"},
)
# --------------------------------------------------------------------------- terminology
#: NINE LANGUAGES AND THE PACK MEANS ALL NINE. English is official in Zimbabwe, Botswana and
#: Namibia, which is the trap: an English crawl returns something for every query in three of the
#: five and reads complete. PORTUGUESE IS THE POINT -- Mozambique and Angola publish their
#: gazettes (Boletim da República, Diário da República), their central-bank statistics and their
#: entire press in Portuguese, and an English-only crawl reads NONE of it and reports the silence
#: as an absence. SHONA and NDEBELE carry the Zimbabwean street and the parallel-rate ecology;
#: SETSWANA carries the Botswana ground; AFRIKAANS and OSHIWAMBO carry the Namibian one; CHANGANA
#: and UMBUNDU are carried thin on purpose, because the vernacular press in MZ and AO is mostly
#: radio and padding the table would claim a ground this desk cannot read.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "SA-A": ("migodhi", "goridhe", "mutengo", "platinum concentrate", "Great Dyke",
             "smelter capacity", "converter matte", "PGM basket price", "chrome seam",
             "izimbiwa", "letlotlo", "royalty schedule"),
    "SA-B": ("mugodhi", "hurumende", "kutengesa", "chikwereti", "statutory instrument",
             "unbeneficiated ore", "export ban", "beneficiation", "spodumene concentrate",
             "uhulumende", "lithium export levy", "gazette number"),
    "SA-C": ("mari", "mitengo", "bhangi", "musika", "imali", "ibhange", "black market rate",
             "parallel premium", "willing buyer willing seller", "reserve cover",
             "de-dollarisation", "surrender requirement", "ndarama"),
    "SA-D": ("goridhe", "igolide", "ndarama", "Fidelity Gold Refinery", "small-scale miner",
             "gold coin", "gold-backed token", "delivery kilogrammes", "payout discount",
             "amanzi", "smuggled dore"),
    "SA-E": ("musika", "intengo", "izimali", "dollarisation", "USD-denominated board",
             "implied rate", "migration to VFEX", "suspension of trading", "free funds",
             "fungibility", "capital flight"),
    "SA-F": ("diamane", "madi", "thekiso", "dipalopalo", "sales cycle", "sightholder",
             "rough diamond", "price per carat", "lab-grown share", "assortment", "kgwebo",
             "Kimberley Process certificate"),
    "SA-G": ("madi", "banka", "tlhwatlhwa", "dipalopalo", "currency basket", "rate of crawl",
             "SDR weight", "rand weight", "Pula Fund", "real effective exchange rate",
             "Monetary Policy Statement", "reserve adequacy"),
    "SA-H": ("puso", "madi", "kgwebo", "SACU revenue pool", "revenue-sharing formula",
             "customs component", "excise component", "development component",
             "stabilisation adjustment", "budget transfer", "common external tariff"),
    "SA-I": ("gás natural", "produção", "exportação", "concessão", "gasoduto", "cargas de GNL",
             "força maior", "decisão final de investimento", "Bacia do Rovuma",
             "reservas provadas", "receita fiscal", "tiko"),
    "SA-J": ("alumínio", "energia", "electricidade", "barragem", "fundição", "produção",
             "interrupção", "tarifa de energia", "exportação de energia", "linha de transporte",
             "olombongo"),
    "SA-K": ("corredor", "porto", "carga", "caminho de ferro", "trânsito", "capacidade",
             "taxa portuária", "carvão", "congestionamento", "desalfandegamento", "ntirho"),
    "SA-L": ("dívida", "incumprimento", "reestruturação", "obrigações", "boletim",
             "dívida oculta", "garantia soberana", "tribunal", "juros vencidos",
             "programa do FMI", "auditoria"),
    "SA-M": ("petróleo", "produção", "quota", "exportação", "OPEP", "barris por dia",
             "programa de carregamento", "campo maduro", "declínio natural", "concessão",
             "ofeka"),
    "SA-N": ("kwanza", "câmbio", "leilão", "divisas", "reservas", "banco central",
             "taxa de referência", "inflação", "combustível", "subsídio", "importação",
             "kinguila"),
    "SA-O": ("uraan", "myn", "prys", "olie", "produksie", "Orange Basin", "appraisal well",
             "final investment decision", "oshimaliwa", "epangelo", "licence round",
             "flow test"),
    "SA-P": ("geld", "regering", "begroting", "uitvoer", "handel", "oshilongo", "aantu",
             "Common Monetary Area", "one-to-one peg", "rand legal tender", "repo spread",
             "local index"),
    "SA-Q": ("krag", "magetsi", "ugesi", "mvura", "metsi", "motlakase", "barragem",
             "lake level", "load shedding", "Southern African Power Pool", "wheeling",
             "generation allocation"),
    "SA-R": ("feriado", "tolerância de ponto", "public holiday", "Sunday substitution",
             "Heroes' Day", "President's Day", "Carnaval", "Sexta-Feira Santa",
             "Dia da Família", "mmereko", "trading calendar"),
}

#: The marker vocabularies the tests assert against. They are deliberately SMALL and confident:
#: a long list of half-remembered words would make the language checks pass while teaching the
#: crawler nothing. Where a ground is genuinely thin -- Changana and Umbundu in the printed press
#: -- the list is short ON PURPOSE and `NO_LAWFUL_GROUND` says why.
SHONA_MARKERS: tuple[str, ...] = (
    "mari", "goridhe", "mutengo", "hurumende", "musika", "kutengesa", "bhangi", "mitengo",
    "chikwereti", "ndarama", "mugodhi", "migodhi", "magetsi", "chibage", "mvura")
NDEBELE_MARKERS: tuple[str, ...] = (
    "imali", "igolide", "intengo", "uhulumende", "ibhange", "izimbiwa", "amanzi", "ugesi",
    "izimali")
SETSWANA_MARKERS: tuple[str, ...] = (
    "madi", "diamane", "puso", "banka", "thekiso", "metsi", "motlakase", "kgwebo", "dipalopalo",
    "tlhwatlhwa", "letlotlo", "mmereko")
AFRIKAANS_MARKERS: tuple[str, ...] = (
    "geld", "goud", "regering", "uitvoer", "verslag", "prys", "ekonomie", "krag", "myn",
    "handel", "begroting", "uraan", "olie", "produksie")
OSHIWAMBO_MARKERS: tuple[str, ...] = ("oshimaliwa", "epangelo", "oshilongo", "aantu")
CHANGANA_MARKERS: tuple[str, ...] = ("tiko", "ntirho", "vanhu", "nkarhi")
UMBUNDU_MARKERS: tuple[str, ...] = ("olombongo", "ofeka", "omanu")
#: Portuguese is detected two ways because both matter: the DIACRITICS catch a phrase this pack
#: never anticipated, and the word list catches the unaccented vocabulary of the gazettes.
PORTUGUESE_DIACRITICS: frozenset[str] = frozenset("ãõçáéíóúâêôàü")
PORTUGUESE_MARKERS: tuple[str, ...] = (
    "banco", "cambio", "petroleo", "producao", "governo", "divida", "diamante", "mercado",
    "taxa", "moeda", "exportacao", "importacao", "relatorio", "estatistica", "carvao",
    "energia", "combustivel", "kwanza", "metical", "meticais", "orcamento", "imposto",
    "decreto", "boletim", "republica", "reservas", "leilao", "divisas", "juros", "inflacao",
    "corredor", "porto", "carga", "barragem", "gasoduto", "concessao", "producao", "quota",
    "obrigacoes", "tribunal", "auditoria", "feriado", "kinguila", "eletricidade")

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

_PUNCT = " \t\n\r,.;:!?()[]{}\"'«»-/\\|"


def _words(text: str) -> list[str]:
    """Lower-cased word tokens, stripped of punctuation. Every Southern African language in this
    pack is written in the LATIN script, so the codepoint-range trick that works for Ge'ez,
    Hangul or Han is useless here and a word-level test is the only honest one."""
    return [w.strip(_PUNCT).lower() for w in str(text).split() if w.strip(_PUNCT)]


def _strip_accents(word: str) -> str:
    table = {"ã": "a", "á": "a", "à": "a", "â": "a", "é": "e", "ê": "e", "í": "i", "ó": "o",
             "ô": "o", "õ": "o", "ú": "u", "ü": "u", "ç": "c"}
    return "".join(table.get(ch, ch) for ch in word)


def has_portuguese(text: str) -> bool:
    """True when a phrase carries Portuguese diacritics or Portuguese gazette vocabulary.

    MOZAMBIQUE AND ANGOLA PUBLISH NOTHING OF CONSEQUENCE IN ENGLISH. The Boletim da República,
    the Diário da República, the Banco de Moçambique and BNA statistics, Notícias, Carta de
    Moçambique, Jornal de Angola, Expansão and Mercado are all Portuguese, and a crawler pointed
    at English queries reads a wire summary written days later by somebody who was not there.
    """
    lowered = str(text).lower()
    if any(ch in PORTUGUESE_DIACRITICS for ch in lowered):
        return True
    markers = set(PORTUGUESE_MARKERS)
    return any(_strip_accents(w) in markers for w in _words(lowered))


def _marker_hit(text: str, markers: tuple[str, ...]) -> bool:
    return bool(set(_words(text)) & set(markers))


def has_shona(text: str) -> bool:
    return _marker_hit(text, SHONA_MARKERS)


def has_ndebele(text: str) -> bool:
    return _marker_hit(text, NDEBELE_MARKERS)


def has_setswana(text: str) -> bool:
    return _marker_hit(text, SETSWANA_MARKERS)


def has_afrikaans(text: str) -> bool:
    return _marker_hit(text, AFRIKAANS_MARKERS)


def has_oshiwambo(text: str) -> bool:
    return _marker_hit(text, OSHIWAMBO_MARKERS)


def has_changana(text: str) -> bool:
    return _marker_hit(text, CHANGANA_MARKERS)


def has_umbundu(text: str) -> bool:
    return _marker_hit(text, UMBUNDU_MARKERS)


def has_native(text: str) -> bool:
    """True when a phrase is in ANY of this pack's eight non-English grounds."""
    return (has_portuguese(text) or has_shona(text) or has_ndebele(text) or has_setswana(text)
            or has_afrikaans(text) or has_oshiwambo(text) or has_changana(text)
            or has_umbundu(text))


def _terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    table = TERMINOLOGY if terminology is None else terminology
    return [t for group in table.values() for t in group]


def portuguese_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    return [t for t in _terms(terminology) if has_portuguese(t)]


def shona_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    return [t for t in _terms(terminology) if has_shona(t)]


def ndebele_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    return [t for t in _terms(terminology) if has_ndebele(t)]


def setswana_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    return [t for t in _terms(terminology) if has_setswana(t)]


def afrikaans_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    return [t for t in _terms(terminology) if has_afrikaans(t)]


def term_count(terminology: Mapping[str, Iterable[str]] | None = None) -> int:
    return len(set(_terms(terminology)))


def _seq(values: Iterable[Any]) -> tuple[str, ...]:
    return tuple(str(v) for v in values)


def source_class(sid: str, label: str, *, layer: str, roots: Iterable[str],
                 queries: Iterable[str], languages: Iterable[str], access_label: str,
                 credibility: str, predictive_state: str, licence: str,
                 machine_use_allowed: bool = True, notes: str = "") -> dict[str, Any]:
    """One class of source with the roots a crawler starts from and its three INDEPENDENT
    labels. `queries` are native-language terms, never translations. `machine_use_allowed=False`
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
        "sa_zw_state", "Zimbabwe's state plane: the Reserve Bank's Monetary Policy Statements and "
                       "weekly rates, ZIMSTAT's CPI and trade statistics, the Ministry of "
                       "Finance's budget, ZIMRA's revenue performance and the Ministry of Mines' "
                       "export and royalty tables", layer="official",
        roots=("https://www.rbz.co.zw", "https://www.zimstat.co.zw", "https://www.zimra.co.zw",
               "http://www.zimtreasury.gov.zw"),
        queries=("bhangi guru reZimbabwe", "mutengo wegoridhe nhasi", "mitengo yezvinhu",
                 "ibhange elikhulu leZimbabwe", "intengo yegolide", "migodhi yeplatinum",
                 "monetary policy statement ZiG reserve cover", "willing buyer willing seller",
                 "gold deliveries Fidelity", "mineral export receipts"),
        languages=("sn", "nd", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE STATISTICS ARE AUTHORITATIVE AND DISCONTINUOUS AT THE SAME TIME, which is a "
              "state most packs have no vocabulary for. ZIMSTAT's own documentation names the "
              "breaks -- the suspension of the year-on-year rate in 2019, the blended index, the "
              "ZiG re-basing -- and this pack reads the breaks as data rather than splicing "
              "across them"),
    source_class(
        "sa_bw_state", "Botswana's state plane: the Bank of Botswana's Monetary Policy Statement "
                       "with the PUBLISHED basket weights and rate of crawl, Botswana Financial "
                       "Statistics, Statistics Botswana's trade and diamond series, and the "
                       "Ministry of Finance's Budget Speech", layer="official",
        roots=("https://www.bankofbotswana.bw", "https://www.statsbots.org.bw",
               "https://www.finance.gov.bw"),
        queries=("banka ya puso dipalopalo", "tlhwatlhwa ya diamane", "thekiso ya diamane",
                 "madi a puso", "dipalopalo tsa kgwebo",
                 "monetary policy statement rate of crawl", "currency basket weights SDR rand",
                 "international merchandise trade diamonds carats", "Pula Fund"),
        languages=("tn", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE ONE PLACE IN THE DESK'S WHOLE ROSTER WHERE A CURRENCY'S WEIGHTS ARE PUBLISHED. "
              "The Monetary Policy Statement names the basket composition and the year's rate of "
              "crawl, so the pula's rand content is arithmetic and SA-G measures a residual "
              "rather than fitting a beta"),
    source_class(
        "sa_mz_state", "Mozambique's state plane, ALL OF IT IN PORTUGUESE: Banco de Moçambique's "
                       "MIMO decisions, exchange rate and reserves, INE's CPI and national "
                       "accounts, the Instituto Nacional de Petróleo's project reporting, and the "
                       "Portal do Governo's decrees", layer="official",
        roots=("https://www.bancomoc.mz", "https://www.ine.gov.mz", "https://www.inp.gov.mz",
               "https://www.portaldogoverno.gov.mz"),
        queries=("taxa de câmbio banco central", "comité de política monetária MIMO",
                 "índice de preços no consumidor", "produção de gás natural",
                 "concessão petrolífera Rovuma", "reservas internacionais",
                 "orçamento geral do estado", "inflação mensal Moçambique",
                 "ntirho wa tiko"),
        languages=("pt", "ts", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="AN ENGLISH-ONLY CRAWL READS NOTHING HERE. The MIMO statement, the reserve table "
              "and the INP's project notes are published in Portuguese and often only as PDFs; "
              "what reaches English is a wire paragraph written later by somebody who read the "
              "PDF"),
    source_class(
        "sa_ao_state", "Angola's state plane, ALL OF IT IN PORTUGUESE: the Banco Nacional de "
                       "Angola's FX auctions, reference rate and reserves, INE's CPI, the ANPG's "
                       "concession and production reporting, and the Ministério das Finanças' "
                       "budget and debt tables", layer="official",
        roots=("https://www.bna.ao", "https://www.ine.gov.ao", "https://www.anpg.co.ao",
               "https://www.minfin.gov.ao"),
        queries=("leilão de divisas resultado", "taxa de referência kwanza",
                 "produção de petróleo barris", "reservas internacionais líquidas",
                 "orçamento geral do estado revisão", "dívida pública angolana",
                 "concessão petrolífera licitação", "inflação homóloga", "olombongo ofeka"),
        languages=("pt", "umb", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE AUCTION ALLOCATION IS THE POINT. The BNA publishes how many dollars it sold "
              "and to whom, which is the oil-to-FX transmission as a quantity rather than as a "
              "price, and it is the series SA-N is built on"),
    source_class(
        "sa_na_state", "Namibia's state plane: the Bank of Namibia's Quarterly Bulletin, repo "
                       "decisions and reserve position, the Namibia Statistics Agency's CPI and "
                       "trade series, the Ministry of Mines and Energy's licence register and "
                       "NamRA's customs data", layer="official",
        roots=("https://www.bon.com.na", "https://www.nsa.org.na", "https://www.mme.gov.na",
               "https://www.namra.org.na"),
        queries=("regering begroting Namibië", "uraan myn produksie", "goud prys",
                 "ekonomie verslag", "oshimaliwa shoshilongo", "epangelo lya popya",
                 "petroleum exploration licence register", "SACU receipts quarterly bulletin",
                 "repo rate decision"),
        languages=("af", "ng", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE RESERVE POSITION IS WHAT BACKS THE 1:1 PEG and the SACU receipts line is the "
              "largest revenue item in the budget; both are quarterly, which is the binding "
              "constraint on how fast any Namibian fiscal claim can be tested"),
    # ---- institutional
    source_class(
        "sa_exchanges", "The six boards: the Zimbabwe Stock Exchange and the USD-denominated "
                        "Victoria Falls Stock Exchange, the Botswana Stock Exchange's domestic "
                        "and foreign indices, the Bolsa de Valores de Moçambique, Angola's "
                        "BODIVA debt board and the Namibian Stock Exchange's LOCAL index",
        layer="institutional",
        roots=("https://www.zse.co.zw", "https://www.vfex.exchange", "https://www.bse.co.bw",
               "https://www.bvm.co.mz", "https://www.bodiva.ao", "https://nsx.com.na"),
        queries=("musika wemasheya", "intengo yamasheya", "dipalopalo tsa BSE",
                 "bolsa de valores cotações", "obrigações do tesouro taxa",
                 "VFEX listing migration", "NSX local index", "ZSE market capitalisation"),
        languages=("sn", "nd", "tn", "pt", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public (exchange terms)",
        notes="NO CFD IS QUOTED ON ANY OF THE SIX and no listing on any of them is executable "
              "here. They are read for SPREADS and MIGRATIONS -- ZSE against VFEX, the NSX local "
              "index against the overall index that is really Johannesburg -- never for a price "
              "this desk could trade (two-lane order, 2026-09-06)"),
    source_class(
        "sa_producers", "The operators and utilities as DOCUMENT SOURCES, never as instruments: "
                        "Debswana and De Beers on the diamond cycle, the Great Dyke miners' "
                        "quarterlies, Hidroeléctrica de Cahora Bassa, Sonangol and ENH, NAMCOR, "
                        "NamPower, ZESA and Botswana Power Corporation", layer="institutional",
        roots=("https://www.debswana.com", "https://www.debeersgroup.com", "https://www.hcb.co.mz",
               "https://www.namcor.com.na", "https://www.nampower.com.na",
               "https://www.sonangol.co.ao"),
        queries=("produção de energia barragem", "capacidade instalada megawatts",
                 "produção de petróleo blocos", "thekiso ya diamane ka ngwaga",
                 "migodhi yeplatinum kubudirira", "rough diamond sales cycle results",
                 "smelter maintenance shutdown", "generation availability"),
        languages=("pt", "tn", "sn", "en"), access_label="PUBLIC_WITH_TERMS",
        credibility="RELIABLE", predictive_state="UNTESTED", licence="company terms, public pages",
        notes="EVERY NAME HERE IS AN ACTOR AND NONE IS AN INSTRUMENT. The quarterlies are read "
              "for TONNES, CARATS, MEGAWATTS AND BARRELS; the shares, where they are listed at "
              "all, are never hunted (two-lane order, 2026-09-06)"),
    source_class(
        "sa_multilateral", "The multilateral plane: IMF Article IV reports and the Mozambican "
                           "ECF reviews, World Bank data and the Pink Sheet, the SACU "
                           "Secretariat's revenue-pool figures, SADC, EITI Mozambique and the "
                           "Kimberley Process production and trade statistics",
        layer="institutional",
        roots=("https://www.imf.org/en/Countries", "https://www.sacu.int", "https://www.sadc.int",
               "https://kimberleyprocess.com", "https://eiti.org/mozambique",
               "https://www.worldbank.org/en/research/commodity-markets"),
        queries=("relatório do FMI artigo IV", "receita aduaneira partilha",
                 "estatísticas de produção de diamantes", "revenue sharing formula SACU",
                 "Kimberley Process annual statistics", "Pink Sheet monthly prices",
                 "EITI reconciliation report"),
        languages=("pt", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public (IMF/World Bank/UN terms)",
        notes="THE IMF ARTICLE IV IS THE LAWFUL SUBSTITUTE for the national series this region "
              "does not publish continuously -- Zimbabwe's inflation across its re-basings, the "
              "Angolan and Mozambican parallel premia, and the Zimbabwean arrears position. "
              "MOZAMBIQUE IS THE ONLY EITI IMPLEMENTER OF THE FIVE, and the other four not being "
              "implementers is itself a measured asymmetry rather than a gap to paper over"),
    source_class(
        "sa_trade_mirror", "The mirror plane: UN Comtrade's partner-reported imports against each "
                           "country's own declared exports, and the USGS Mineral Commodity "
                           "Summaries for PGM, diamond, uranium and copper production",
        layer="institutional",
        roots=("https://comtradeplus.un.org", "https://www.usgs.gov/centers/national-minerals-"
               "information-center", "https://www.opec.org/opec_web/en/publications/338.htm"),
        queries=("comtrade HS7110 partner imports", "comtrade HS7102 rough diamonds",
                 "USGS platinum group metals summary", "OPEC monthly oil market report Angola",
                 "exportação de diamantes estatística", "mineral commodity summaries uranium"),
        languages=("pt", "en"), access_label="OPEN_DATA", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public (UN and US government terms)",
        notes="THE MIRROR IS HOW AN UNDER-DECLARED FLOW BECOMES MEASURABLE: Zimbabwean gold and "
              "PGM concentrate leaving as something else, Angolan crude destinations, and the "
              "Botswana-to-Antwerp diamond leg all have a partner-reported half"),
    # ---- academic
    source_class(
        "sa_universities", "The university plane: the University of Zimbabwe, the University of "
                           "Botswana, the University of Namibia, Universidade Eduardo Mondlane "
                           "and Universidade Católica de Angola, reached through OpenAlex and "
                           "CORE rather than through five separate repositories",
        layer="academic",
        roots=("https://openalex.org", "https://core.ac.uk", "https://www.uz.ac.zw",
               "https://www.ub.bw", "https://www.unam.edu.na"),
        queries=("dollarisation Zimbabwe exchange rate pass-through", "pula basket peg study",
                 "resource curse Botswana diamonds", "estudo sobre a dívida pública moçambicana",
                 "análise económica da produção petrolífera angolana",
                 "Common Monetary Area monetary independence", "mari nemitengo ongororo"),
        languages=("pt", "sn", "en"), access_label="OPEN_DATA", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="mixed open access; per-paper terms",
        notes="THE DEPTH IS WILDLY UNEVEN AND THE PACK SAYS SO PER COUNTRY. Botswana and Namibia "
              "have a real policy literature; Zimbabwe's is large and heavily diaspora-authored; "
              "Mozambique's domestic economics literature is thin enough to be declared in "
              "NO_LAWFUL_GROUND with its substitute named"),
    source_class(
        "sa_policy_institutes", "The think-tank plane: ZEPARU in Harare, BIDPA in Gaborone, the "
                                "Institute for Public Policy Research in Windhoek, the Centro de "
                                "Integridade Pública in Maputo, and SAIIA and Chatham House from "
                                "outside", layer="academic",
        roots=("https://www.bidpa.bw", "https://ippr.org.na", "https://www.cipmoz.org",
               "https://saiia.org.za", "https://www.chathamhouse.org"),
        queries=("relatório sobre dívida oculta", "transparência na indústria extractiva",
                 "SACU revenue volatility fiscal", "diamond dependence diversification",
                 "hidden debt court record", "madi a SACU puso"),
        languages=("pt", "tn", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public (institute terms)",
        notes="THE CENTRO DE INTEGRIDADE PÚBLICA IS THE NAMED SUBSTITUTE for the Mozambican "
              "academic literature that does not exist: it publishes dated, sourced, "
              "Portuguese-language work on the hidden debt, the LNG fiscal terms and the "
              "corridor concessions, which is exactly the ground SA-L and SA-K need"),
    # ---- practitioner
    source_class(
        "sa_brokers", "The domestic sell-side that does exist: IJG Securities, Cirrus Capital and "
                      "Simonis Storm in Windhoek, IH Securities and Morgan & Co in Harare, Kgori "
                      "Capital and the bank research desks in Gaborone, and BFA's Portuguese "
                      "weekly in Luanda", layer="practitioner",
        roots=("https://www.ijg.net", "https://cirrus.com.na", "https://www.bfa.ao",
               "https://www.sss.com.na"),
        queries=("análise económica semanal kwanza", "perspectivas do câmbio",
                 "ekonomie verslag Namibië", "weekly market commentary Namibia",
                 "equity strategy note Zimbabwe inflation", "mari yemusika tarisiro"),
        languages=("pt", "af", "sn", "en"), access_label="PUBLIC_WITH_TERMS",
        credibility="RELIABLE", predictive_state="UNTESTED", licence="publisher terms",
        notes="NAMIBIA HAS A REAL DOMESTIC SELL SIDE and Angola has one Portuguese-language bank "
              "research letter that is genuinely useful; Zimbabwe's is small and cyclical, "
              "Botswana's is inside the banks, and Mozambique's barely exists. The asymmetry is "
              "the reason `na` is not declared absent in this layer and `na`'s app layer is"),
    source_class(
        "sa_price_reporting", "The price-reporting agencies that cover what no exchange quotes: "
                              "Rapaport's polished list and the rough assessments, Fastmarkets "
                              "for spodumene and chrome, and UxC and TradeTech for uranium",
        layer="practitioner",
        roots=("https://www.rapaport.com", "https://www.fastmarkets.com", "https://www.uxc.com"),
        queries=("rough diamond price index", "spodumene concentrate assessment",
                 "uranium spot price weekly", "chrome ore price South Africa"),
        languages=("en",), access_label="LICENSED", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="proprietary; machine extraction forbidden",
        machine_use_allowed=False,
        notes="REGISTERED AND NEVER SCRAPED. These are the price series for diamonds, lithium "
              "and uranium -- the three commodities this pack routes rather than trades -- and "
              "their terms forbid machine extraction. Omitting them would lose the knowledge "
              "that the ground exists, so the row stays with machine_use_allowed=false and the "
              "mechanisms that would have used them are routed with their controls named"),
    # ---- retail ecology
    source_class(
        "sa_zw_rate_ecology", "The Zimbabwean parallel-rate ecology: ZimPriceCheck and Marketwatch, "
                              "the rate-quoting Telegram, WhatsApp and X channels, and the "
                              "Bulawayo and Harare street quotes they aggregate",
        layer="retail_ecology",
        roots=("https://www.zimpricecheck.com", "https://www.marketwatch.co.zw"),
        queries=("mari yemusika mutema nhasi", "mutengo wemadhora nhasi", "imali yemakethe",
                 "black market rate today", "rate yekutenga nekutengesa", "mitengo yemadhora"),
        languages=("sn", "nd", "en"), access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="site terms; user-submitted content",
        notes="KEPT AT LOW WEIGHT AND NEVER DROPPED. This is the ONLY daily high-frequency "
              "nominal series Zimbabwe has, it is crowd-sourced and unaudited, and it is the "
              "regime-stress state SA-C conditions on. A claim that looks unreliable is still a "
              "dated, testable claim, and the alternative here is no daily series at all"),
    source_class(
        "sa_regional_retail", "The public investor ecology of the anglophone three: Botswana and "
                              "Namibian personal-finance and BSE/NSX discussion groups, the "
                              "Zimbabwean diaspora investment communities, and the Afrikaans "
                              "personal-finance ground that spans the CMA",
        layer="retail_ecology",
        roots=("https://www.reddit.com/r/Namibia", "https://www.facebook.com",
               "https://www.mmegi.bw/business"),
        queries=("hoe om te belê aandele", "geld spaar Namibië", "madi a peeletso",
                 "how to buy NSX shares", "kutenga masheya", "beleggings advies"),
        languages=("af", "tn", "sn", "en"), access_label="PUBLIC_SOCIAL", credibility="FRINGE",
        predictive_state="UNTESTED", licence="platform terms; public posts only",
        notes="FRINGE AND KEPT. There is no aggregate retail-positioning statistic anywhere in "
              "the five, so this ground is all the retail sentiment that exists -- and no "
              "microstructure claim in this pack is allowed to rest on it, which is why "
              "NO_LAWFUL_GROUND declares the retail layer absent for three of the five anyway"),
    # ---- app ecosystem
    source_class(
        "sa_mobile_money", "THE APP LAYER HERE IS MOBILE MONEY AND THE PAYMENT RAIL, not a "
                           "trading ecology: EcoCash, InnBucks and OneMoney in Zimbabwe, M-Pesa, "
                           "e-Mola and mKesh in Mozambique, Multicaixa Express and EMIS in "
                           "Angola, Orange Money and MyZaka in Botswana, and the Namibian banks' "
                           "instant-payment rails", layer="app_ecosystem",
        roots=("https://www.ecocash.co.zw", "https://www.emis.co.ao",
               "https://www.bancomoc.mz/pt/publicacoes/relatorio-dos-sistemas-de-pagamento/",
               "https://www.bankofbotswana.bw/payments-and-settlement"),
        queries=("relatório dos sistemas de pagamento", "transacções por telemóvel valor",
                 "mari yemuchina", "ecocash miamala", "mobile money transaction value",
                 "Multicaixa Express estatísticas", "dipalopalo tsa dipatelo"),
        languages=("pt", "sn", "tn", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public (central bank reports)",
        notes="DECLARING THIS LAYER ABSENT BECAUSE THERE IS NO METATRADER ECOLOGY WOULD BE "
              "READING THE WRONG COUNTRIES. The payment rails ARE the app layer, four of the "
              "five central banks publish their transaction value and volume, and in Zimbabwe "
              "the mobile-money aggregate is one of the few nominal series that survived every "
              "currency change"),
    source_class(
        "sa_market_data_apps", "The market-data and terminal ecology that actually exists: the "
                               "exchanges' own market-data pages and feeds, the JSE terminals "
                               "the NSX dual listings trade through, and the De Beers and OPEC "
                               "release feeds a collector can subscribe to",
        layer="app_ecosystem",
        roots=("https://www.zse.co.zw/market-data/", "https://nsx.com.na/market-data",
               "https://www.bse.co.bw/market-statistics"),
        queries=("market data daily price list", "dipalopalo tsa letsatsi",
                 "cotações diárias bolsa", "musika wezuva nhasi", "closing prices download"),
        languages=("pt", "tn", "sn", "en"), access_label="PUBLIC_WITH_TERMS",
        credibility="RELIABLE", predictive_state="UNTESTED", licence="exchange terms",
        notes="NO DOMESTIC BROKERAGE IN ANY OF THE FIVE PUBLISHES AN API. What exists is the "
              "exchanges' own daily price lists, mostly as PDFs that overwrite in place, which "
              "is why the archive layer carries the point-in-time half of this ground"),
    # ---- media
    source_class(
        "sa_zw_media", "The Zimbabwean press: The Herald and Chronicle (state), NewsDay and the "
                       "Zimbabwe Independent (private), Business Weekly, and ZimLive and "
                       "NewZimbabwe for the diaspora tape", layer="media",
        roots=("https://www.herald.co.zw", "https://www.newsday.co.zw", "https://www.zimlive.com",
               "https://www.chronicle.co.zw"),
        queries=("hurumende yakazivisa mitengo", "mari nemusika mutema", "migodhi nemitemo mitsva",
                 "uhulumende ukhulumile ngemali", "statutory instrument gazetted mining",
                 "ZiG exchange rate news", "izimbiwa zelizwe"),
        languages=("sn", "nd", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="publisher terms; public pages",
        notes="THE STATE AND PRIVATE PAPERS DISAGREE ON PURPOSE and the disagreement is "
              "informative: The Herald carries the official framing of a statutory instrument "
              "within a day of the gazette, NewsDay carries the compliance cost, and ZimLive "
              "carries what the diaspora is told. Reading only one reads a position, not a fact"),
    source_class(
        "sa_lusophone_media", "THE PORTUGUESE-LANGUAGE PRESS, WHICH IS THE ENTIRE MOZAMBICAN AND "
                              "ANGOLAN TAPE: Jornal Notícias and Rádio Moçambique (state), Carta "
                              "de Moçambique and @Verdade (private), Jornal de Angola (state), "
                              "and Expansão and Mercado (business)", layer="media",
        roots=("https://www.jornalnoticias.co.mz", "https://cartamz.com", "https://verdade.co.mz",
               "https://www.jornaldeangola.ao", "https://expansao.co.ao", "https://mercado.co.ao"),
        queries=("banco central anuncia taxa", "leilão de divisas resultado",
                 "produção de gás natural cargas", "dívida oculta julgamento",
                 "corredor da Beira congestionamento", "preço dos combustíveis subsídio",
                 "barragem de Cahora Bassa energia", "kinguila mercado informal"),
        languages=("pt",), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="publisher terms; public pages",
        notes="THIS ROW IS WHY THE PACK CARRIES PORTUGUESE AT ALL. Expansão and Mercado carry the "
              "informal kwanza rate and the auction commentary; Carta de Moçambique carries the "
              "corridor and hidden-debt reporting; and NONE of it exists in English until a wire "
              "service summarises a fraction of it a day later"),
    source_class(
        "sa_bw_na_media", "The Botswana and Namibian press: Mmegi and the Sunday Standard in "
                          "Gaborone, The Namibian, New Era and the Windhoek Observer in "
                          "Windhoek, and Republikein for the Afrikaans ground", layer="media",
        roots=("https://www.mmegi.bw", "https://www.sundaystandard.info",
               "https://www.namibian.com.na", "https://www.observer24.com.na"),
        queries=("tlhwatlhwa ya diamane e wela", "puso le madi a SACU", "kgwebo ya diamane",
                 "regering begroting tekort", "uraan myn nuus", "goud prys Namibië",
                 "diamond sales cycle Botswana revenue", "Orange Basin drilling news"),
        languages=("tn", "af", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="publisher terms; public pages",
        notes="MMEGI IS THE FIRST PLACE A DEBSWANA OR DE BEERS NUMBER IS ARGUED ABOUT DOMESTICALLY "
              "and the Sunday Standard carries the fiscal consequence; Republikein's Afrikaans "
              "business pages reach a readership the English Namibian titles do not"),
    # ---- archive
    source_class(
        "sa_gazettes", "The gazette plane, which is where the DATES live: Veritas' archive of "
                       "Zimbabwean statutory instruments and Acts, the Botswana Government "
                       "Gazette, the Boletim da República from Imprensa Nacional de Moçambique, "
                       "Angola's Diário da República, and the Namibian Government Gazette",
        layer="archive",
        roots=("https://www.veritaszim.net/node/", "https://www.gov.bw/government-gazette",
               "https://www.imprensanac.gov.mz", "https://www.lac.org.na/laws/gazette.html"),
        queries=("statutory instrument base minerals export control",
                 "boletim da república decreto", "diário da república feriados",
                 "government gazette public holidays act", "mitemo mitsva yemigodhi",
                 "lei dos feriados nacionais", "molao o mosha wa puso"),
        languages=("pt", "sn", "tn", "en"), access_label="PUBLIC_ARCHIVE",
        credibility="AUTHORITATIVE", predictive_state="UNTESTED", licence="free, public",
        notes="VERITAS IS THE REASON SA-B IS TESTABLE AT ALL. The Zimbabwean lithium and PGM "
              "export controls are statutory instruments with gazette numbers and commencement "
              "dates, and Veritas publishes them within days; a press report of a ministerial "
              "announcement is not the same event and often not the same date"),
    source_class(
        "sa_discontinued", "The discontinued and overwritten series: ZIMSTAT's pre-break CPI "
                           "vintages, the Old Mutual implied-rate observable that ended with the "
                           "June 2020 ZSE suspension, the pre-2019 ZSE tape, and every central "
                           "bank page in this pack that overwrites in place, recovered through "
                           "the Internet Archive", layer="archive",
        roots=("https://web.archive.org/web/*/rbz.co.zw/*", "https://web.archive.org/web/*/"
               "zimstat.co.zw/*", "https://web.archive.org/web/*/bna.ao/*"),
        queries=("ZIMSTAT consumer price index archived", "RBZ exchange rate archived page",
                 "old mutual implied rate", "taxa de câmbio arquivada",
                 "mitengo yakare yemadhora"),
        languages=("pt", "sn", "en"), access_label="PUBLIC_ARCHIVE", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="Internet Archive terms",
        notes="THE POINT-IN-TIME HALF OF THIS WHOLE PACK. Five central banks and three statistics "
              "offices publish TODAY'S number on a page that overwrites; a cell compiled on a "
              "session nobody archived is UNMEASURED, never assumed, and that is why three "
              "datasets in this file carry pit_feasible=False"),
    # ---- physical economy
    source_class(
        "sa_corridors", "The corridor plane: Portos e Caminhos de Ferro de Moçambique and "
                        "Cornelder at Beira, the Nacala Logistics Corridor, Namport at Walvis "
                        "Bay, the Lobito Atlantic Railway concession, and the Beitbridge and "
                        "Chirundu border posts", layer="physical_economy",
        roots=("https://www.cfm.co.mz", "https://www.cornelder.co.mz", "https://www.namport.com.na",
               "https://lobitocorridor.com"),
        queries=("movimento de carga no porto", "corredor de Nacala carvão",
                 "caminho de ferro tonelagem", "congestionamento no porto da Beira",
                 "Walvis Bay corridor cargo volumes", "mizigo ya bandari",
                 "tonnage transited copper Lobito"),
        languages=("pt", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public (operator terms)",
        notes="THREE CORRIDORS FOR ONE OREBODY, which is what makes any of them measurable: "
              "Copperbelt metal can leave through Beira, Nacala, Dar es Salaam, Durban or Lobito, "
              "so a fall at one is a ROUTING event until another's series says otherwise -- and "
              "that is a joint measurement with `copperbelt` that neither pack can make alone"),
    source_class(
        "sa_power", "The regional power plane: the Zambezi River Authority's Kariba lake levels "
                    "and allocations, Hidroeléctrica de Cahora Bassa's generation, ZESA and the "
                    "Zimbabwe Power Company, NamPower, Botswana Power Corporation, "
                    "Electricidade de Moçambique and the Southern African Power Pool",
        layer="physical_economy",
        roots=("https://www.zambezira.org", "https://www.hcb.co.mz", "https://www.zesa.co.zw",
               "https://www.nampower.com.na", "https://www.sapp.co.zw"),
        queries=("nível da albufeira produção de energia", "mgao wa umeme",
                 "magetsi kudzimwa nyika", "ugesi umbuso", "krag tekort beurtkrag",
                 "Kariba lake level weekly bulletin", "motlakase o o seng teng",
                 "energia exportada para a África do Sul"),
        languages=("pt", "sn", "nd", "af", "tn", "en"), access_label="PUBLIC",
        credibility="RELIABLE", predictive_state="UNTESTED", licence="free, public",
        notes="THE LAKE LEVEL IS THE HIGHEST-FREQUENCY REAL-ECONOMY NUMBER IN THIS PACK: weekly, "
              "published, physical, and it decides how much smelting and refining Zimbabwe and "
              "Zambia can actually run. Cahora Bassa is the same mechanism in Mozambique with an "
              "aluminium smelter on the end of it"),
    source_class(
        "sa_mining_physical", "The mining plane: Zimbabwe's Ministry of Mines and the Minerals "
                              "Marketing Corporation export tables, the Chamber of Mines' state "
                              "of the industry survey, Debswana's production, the Namibian "
                              "licence register and the uranium mines' output",
        layer="physical_economy",
        roots=("http://www.mines.gov.zw", "https://www.mmcz.co.zw", "https://www.debswana.com",
               "https://www.mme.gov.na/directorates/mining/"),
        queries=("migodhi kubudirira kwegore", "goridhe rakatengeswa makirogiramu",
                 "izimbiwa ezithunyelwe phandle", "thekiso ya diamane dikarati",
                 "uraan produksie ton", "platinum concentrate export volume",
                 "royalty paid mineral exports"),
        languages=("sn", "nd", "tn", "af", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE OPERATORS ARE ACTORS AND NEVER INSTRUMENTS. Production and export TONNAGE is "
              "the read; the Minerals Marketing Corporation's export tables are the Zimbabwean "
              "half of the mirror comparison and the small-scale gold delivery series is the "
              "only published measure of an informal flow in this pack"),
    # ---- source graph
    source_class(
        "sa_source_graph", "Who cites whom in the anglophone three: the Zimbabwean gazette to The "
                           "Herald to NewsDay to ZimLive; the Bank of Botswana Monetary Policy "
                           "Statement to Mmegi to the Sunday Standard; the Bank of Namibia "
                           "bulletin to The Namibian and Republikein", layer="source_graph",
        roots=("https://www.veritaszim.net", "https://www.herald.co.zw", "https://www.mmegi.bw",
               "https://www.namibian.com.na"),
        queries=("according to the gazette notice", "sources close to the central bank",
                 "nhau dzinoti hurumende", "uhulumende uthi abantu", "volgens die regering",
                 "go ya ka dipego tsa puso"),
        languages=("sn", "nd", "af", "tn", "en"), access_label="PUBLIC", credibility="UNKNOWN",
        predictive_state="UNTESTED", licence="derived from the public sources above",
        notes="'nhau dzinoti' and 'sources close to' mark the unattributed leak that precedes a "
              "Zimbabwean statutory instrument by a day or two; the graph is how a leak is told "
              "from a repost, and it is the only way to date a measure before the gazette prints "
              "it"),
    source_class(
        "sa_lusophone_graph", "Who cites whom in Portuguese: the Diário da República to Jornal de "
                              "Angola to Expansão and Mercado; the Boletim da República to "
                              "Notícias to Carta de Moçambique and the CIP; and the BNA auction "
                              "note to the Luanda trade letters", layer="source_graph",
        roots=("https://www.jornaldeangola.ao", "https://expansao.co.ao", "https://cartamz.com",
               "https://www.cipmoz.org"),
        queries=("segundo fontes do banco central", "de acordo com o diário da república",
                 "fontes ligadas ao processo", "analistas afirmam que o kwanza",
                 "documento a que tivemos acesso"),
        languages=("pt",), access_label="PUBLIC", credibility="UNKNOWN",
        predictive_state="UNTESTED", licence="derived from the public sources above",
        notes="'segundo fontes' and 'documento a que tivemos acesso' are the Portuguese markers "
              "for the same leak pattern, and they matter more here than in the anglophone three "
              "because Angola and Mozambique publish decrees AFTER they take effect more often "
              "than before"),
)

#: NO LAYER IS BLANK FOR THE REGION AS A WHOLE, and that is the measurement rather than a claim
#: of completeness. The refusals that ARE real here are per-jurisdiction and per-layer -- and in
#: one case per SERIES -- and each is declared by name below rather than hidden inside a layer
#: that another of the five happens to fill.
LAYER_ABSENCES: dict[str, str] = {}

#: THE MEASURED REFUSALS (L1.28a). Each row names the jurisdiction, the layer, the SCOPE of the
#: refusal, what does not exist, why, and THE LAWFUL SUBSTITUTE. A refusal with no substitute is
#: a hole; a refusal with a substitute is a routing decision, and that is worth more than a
#: padded row. A layer one of the five fills and another does not is a real asymmetry, and
#: pooling the five without it is how a pack claims coverage of a ground it has never read.
NO_LAWFUL_GROUND: tuple[dict[str, str], ...] = (
    {"jurisdiction": "zw", "layer": "official",
     "scope": "the official year-on-year inflation SERIES, not the official layer",
     "reason": "ZIMBABWE'S OFFICIAL INFLATION SERIES IS DISCONTINUOUS BY ITS OWN AGENCY'S "
               "ACCOUNT. The year-on-year rate was suspended in 2019 while the currency was "
               "re-denominated, the index has been re-based more than once including onto a "
               "blended local-and-foreign-currency basket and again onto the ZiG in 2024, and "
               "ZIMSTAT documents each break. There is therefore NO continuous Zimbabwean price "
               "series to condition on and this pack refuses to splice one.",
     "substitute": "the private parallel-rate trackers at UNRELIABLE credibility for the daily "
                   "nominal signal, the IMF Article IV reconstructions for the level across the "
                   "breaks, and the RBZ's own willing-buyer-willing-seller rate for the official "
                   "half of the premium. Every SA-C cell conditions on a REGIME and a PREMIUM, "
                   "never on a spliced inflation rate."},
    {"jurisdiction": "zw", "layer": "retail_ecology",
     "scope": "aggregate retail positioning and margin statistics",
     "reason": "NO LAWFUL RETAIL MARGIN MARKET EXISTS. Zimbabwean exchange control makes funding "
               "an offshore margin account unlawful for residents, no domestic broker is "
               "licensed to offer leverage, and no regulator publishes a retail flow, exposure "
               "or margin number of any kind.",
     "substitute": "the public parallel-rate channels and the diaspora investment communities, "
                   "sourced above at UNRELIABLE and FRINGE credibility. No microstructure claim "
                   "in this pack may rest on a retail-flow number, because there is none."},
    {"jurisdiction": "bw", "layer": "retail_ecology",
     "scope": "aggregate retail positioning and margin statistics",
     "reason": "NBFIRA licenses no retail margin broker that publishes flow and the Botswana "
               "Stock Exchange reports its investor split only in the annual report, which "
               "cannot condition a week. Botswana's household financial ecology runs through "
               "the banks and the pension funds, neither of which publishes a position.",
     "substitute": "the BSE's annual investor-category split for a slow-moving state variable "
                   "and the domestic-versus-foreign company index spread for the fast one; "
                   "both are named in SA-F's controls rather than used as flow."},
    {"jurisdiction": "mz", "layer": "academic",
     "scope": "the domestic academic economics literature",
     "reason": "MOZAMBIQUE HAS NO DOMESTIC ACADEMIC ECONOMICS LITERATURE OF ANY DEPTH. "
               "Universidade Eduardo Mondlane publishes little economics and almost none of it "
               "machine-readable; there is no working-paper series a crawler can follow and no "
               "domestic journal with a citation graph worth walking.",
     "substitute": "the IMF Article IV and Extended Credit Facility reviews for the macro "
                   "series, the Centro de Integridade Pública for dated, sourced, "
                   "Portuguese-language work on the hidden debt, the LNG fiscal terms and the "
                   "corridor concessions, and the South African and Portuguese universities that "
                   "publish ON Mozambique. All three are sourced above."},
    {"jurisdiction": "mz", "layer": "retail_ecology",
     "scope": "aggregate retail positioning and any retail market at all",
     "reason": "there is no retail margin market and the Bolsa de Valores de Moçambique is "
               "effectively a bond board with no public depth; household savings are in bank "
               "deposits and mobile-money wallets, neither of which is a position.",
     "substitute": "the Banco de Moçambique's payment-systems report for the mobile-money "
                   "aggregate, which is a REAL high-frequency nominal series and is the app "
                   "layer for this country, sourced above."},
    {"jurisdiction": "ao", "layer": "retail_ecology",
     "scope": "the retail trading ecology in its entirety",
     "reason": "ANGOLA'S RETAIL TRADING ECOLOGY DOES NOT EXIST. The Comissão do Mercado de "
               "Capitais licenses no retail margin broker, BODIVA is an over-the-counter debt "
               "board with no equity listings, residents face exchange control on moving "
               "currency offshore, and no regulator publishes retail participation of any kind.",
     "substitute": "the informal FX market ('kinguilas') as reported in Expansão and Mercado is "
                   "the only retail price ecology Angola has, and it is a CURRENCY ground rather "
                   "than a trading one; it is sourced in the Portuguese media class above and is "
                   "never treated as positioning."},
    {"jurisdiction": "ao", "layer": "academic",
     "scope": "the domestic academic economics literature",
     "reason": "Angolan domestic economics output is minimal, mostly institutional rather than "
               "peer-reviewed, and almost entirely absent from the indexing services a crawler "
               "can walk; Universidade Católica de Angola's output is the exception and is thin.",
     "substitute": "the IMF Article IV, the World Bank's Angola economic updates, the "
                   "Portuguese-language institutional research from the Lisbon universities and "
                   "BFA's own weekly letter, all sourced above at RELIABLE credibility."},
    {"jurisdiction": "na", "layer": "app_ecosystem",
     "scope": "a domestic trading-app and brokerage-API ecology",
     "reason": "NAMIBIA HAS NO DOMESTIC TRADING-APP ECOSYSTEM. No Namibian brokerage publishes "
               "an API, the NSX's dual listings are traded through Johannesburg terminals, and "
               "the Namibian app layer is the banking and instant-payment rail rather than a "
               "market one.",
     "substitute": "the South African app ecology, which is `za`'s ground and not this pack's, "
                   "plus the NSX's own market-data pages and the Bank of Namibia's payment "
                   "statistics for the rail itself. Declaring this layer absent because there is "
                   "no MetaTrader ecology in Windhoek would be reading the wrong country; "
                   "declaring it absent because the terminals are in Sandton is the truth."},
)

#: NATIVE QUERY TERRITORIES -- what the deep-forest miner actually types, per layer. At least
#: three per layer, and at least one native phrase in every layer. PORTUGUESE CARRIES TWO OF THE
#: FIVE COUNTRIES ENTIRELY, so it appears in every layer; Shona, Ndebele, Setswana, Afrikaans and
#: Oshiwambo carry the anglophone three's domestic half, which an English query never reaches.
QUERY_TERRITORIES: dict[str, tuple[str, ...]] = {
    "official": ("bhangi guru reZimbabwe chirevo", "mutengo wemadhora nhasi",
                 "banka ya puso dipalopalo tsa ngwaga", "taxa de câmbio de referência",
                 "leilão de divisas alocação", "reservas internacionais líquidas",
                 "regering begroting verslag", "oshimaliwa shoshilongo",
                 "produção de petróleo mensal"),
    "institutional": ("bolsa de valores cotações diárias", "obrigações do tesouro leilão",
                      "musika wemasheya mitengo", "thekiso ya diamane ka kgwedi",
                      "relatório do FMI artigo IV", "estatísticas do processo de Kimberley"),
    "academic": ("estudo sobre a dívida pública", "análise económica do sector petrolífero",
                 "ongororo yemari nemitengo", "patlisiso ka ga ikonomi ya diamane",
                 "navorsing oor die ekonomie", "resource curse diamond dependence"),
    "practitioner": ("análise semanal do câmbio", "perspectivas económicas trimestrais",
                     "ekonomie vooruitsigte verslag", "tarisiro yemusika wemari",
                     "weekly market commentary"),
    "retail_ecology": ("mari yemusika mutema nhasi", "mutengo wemadhora kumusika",
                       "imali yemakethe namuhla", "geld belê in aandele",
                       "mercado informal kinguila taxa", "madi a peeletso"),
    "app_ecosystem": ("relatório dos sistemas de pagamento", "transacções por telemóvel valor",
                      "ecocash miamala mari", "Multicaixa Express estatísticas",
                      "dipalopalo tsa dipatelo"),
    "media": ("hurumende yakazivisa mitemo mitsva", "uhulumende uthi ngezimbiwa",
              "banco central anuncia nova taxa", "dívida oculta julgamento",
              "tlhwatlhwa ya diamane e wela", "regering se begroting tekort",
              "produção de gás natural primeira carga"),
    "archive": ("statutory instrument gazetted export control", "boletim da república decreto",
                "diário da república feriados nacionais", "mitemo yakare yemigodhi",
                "molao wa maloba wa puso", "taxa de câmbio arquivada"),
    "physical_economy": ("nível da albufeira de Cahora Bassa", "movimento de carga no porto",
                         "magetsi kudzimwa munyika", "ugesi awukho elizweni",
                         "krag tekort beurtkrag", "corredor de Nacala tonelagem",
                         "uraan produksie ton", "goridhe rakatengeswa makirogiramu"),
    "source_graph": ("segundo fontes do banco central", "documento a que tivemos acesso",
                     "nhau dzinoti hurumende", "volgens die regering se verslag",
                     "go ya ka dipego tsa puso"),
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
                    "one jurisdiction fills and another does not is declared per jurisdiction in "
                    "NO_LAWFUL_GROUND with its LAWFUL SUBSTITUTE named, rather than hidden "
                    "behind the one that fills it; fringe and unreliable PUBLIC material is kept "
                    "at low weight and never dropped; a page whose terms forbid machine "
                    "extraction is registered machine_use_allowed=false, never scraped and never "
                    "omitted"}
# --------------------------------------------------------------------------- datasets
#: TWENTY-TWO ROWS, SPREAD ACROSS THE TEN LAYERS, each with a `how_to_fetch` a collector can act
#: on. Only the twelve DATASET_FIELDS appear here: the framework's `DatasetRow` has no notes slot,
#: so a thirteenth key would arrive as a coercion note rather than as information.
DATASETS: tuple[dict[str, Any], ...] = (
    {"name": "De Beers rough diamond sales cycle revenue (ten cycles a year)",
     "source": "De Beers Group / Anglo American company news",
     "coverage": "every sales cycle since the cycle-reporting regime began, with the prior cycle "
                 "and prior-year comparison in the same release",
     "frequency": "ten times a year", "publication_lag_days": 3.0,
     "revisions": "the headline is not revised; the comparison figures are restated between "
                  "releases, so the FIRST print is the point-in-time number",
     "licence": "free, public (company terms)", "history_from": "2016", "pit_feasible": True,
     "assets": ("US500", "UK100", "USDZAR"),
     "mechanism_families": ("release_surprise", "nominal_demand", "corporate_flow"),
     "how_to_fetch": "poll debeersgroup.com/media/company-news for the 'Sales Value' release "
                     "after each cycle close, parse the USD figure and the cycle number, and "
                     "stamp the release timestamp; the calendar of cycle dates is published "
                     "annually in the same section"},
    {"name": "Statistics Botswana international merchandise trade: diamond value and carats",
     "source": "Statistics Botswana",
     "coverage": "monthly exports and imports by commodity group, with diamonds split by value "
                 "and carat volume",
     "frequency": "monthly", "publication_lag_days": 60.0,
     "revisions": "revised for several months; the carat series is revised more than the value "
                  "series, so the implied price per carat moves after the fact",
     "licence": "free, public", "history_from": "2006", "pit_feasible": False,
     "assets": ("USDZAR", "US500", "UK100"),
     "mechanism_families": ("release_surprise", "physical_flow", "nominal_demand"),
     "how_to_fetch": "download the International Merchandise Trade Statistics monthly digest PDF "
                     "or the Excel annex from statsbots.org.bw, take the diamond export value "
                     "and carat rows, and divide for a realised price per carat"},
    {"name": "Reserve Bank of Zimbabwe willing-buyer-willing-seller rate and ZiG reserve cover",
     "source": "Reserve Bank of Zimbabwe",
     "coverage": "the official interbank rate, the money supply in ZiG and the published gold "
                 "and foreign-exchange cover for the currency",
     "frequency": "weekly for the rate, irregular for the cover", "publication_lag_days": 7.0,
     "revisions": "the rate is not revised; the reserve cover is restated when the RBZ changes "
                  "what it counts, which has happened",
     "licence": "free, public", "history_from": "2024-04-05 for the ZiG series; earlier series "
                                                "exist for each prior currency and are NOT the "
                                                "same measurement",
     "pit_feasible": False,
     "assets": ("XAUUSD", "USDZAR"),
     "mechanism_families": ("central_bank_surprise", "regime_break", "carry_funding"),
     "how_to_fetch": "scrape the rbz.co.zw exchange-rate and Monetary Policy Statement pages "
                     "weekly AND archive each fetch, because the page overwrites in place and "
                     "the historical series is not consistently downloadable"},
    {"name": "Zimbabwe private parallel-market rate trackers",
     "source": "ZimPriceCheck and Marketwatch (crowd-sourced)",
     "coverage": "the daily street rate for US dollars against the local unit, quoted buy and "
                 "sell, for Harare and Bulawayo",
     "frequency": "daily", "publication_lag_days": 0.0,
     "revisions": "re-stated intraday as contributors report; there is no final vintage",
     "licence": "free, public (site terms); user-submitted content",
     "history_from": "2019", "pit_feasible": False,
     "assets": ("XAUUSD", "USDZAR"),
     "mechanism_families": ("regime_break", "carry_funding", "failure"),
     "how_to_fetch": "fetch zimpricecheck.com and marketwatch.co.zw daily, take the quoted "
                     "buy/sell pair with its observation time, compute the premium to the RBZ "
                     "rate, and store the vintage -- these pages do not keep history either"},
    {"name": "ZIMSTAT consumer price index with its documented breaks",
     "source": "Zimbabwe National Statistics Agency",
     "coverage": "the monthly index and its re-basings, including the blended basket and the "
                 "ZiG re-basing, each documented by the agency",
     "frequency": "monthly", "publication_lag_days": 15.0,
     "revisions": "re-based rather than revised, which is a different and worse problem: the "
                  "index after a break is not a continuation of the index before it",
     "licence": "free, public", "history_from": "2009 with breaks in 2019, 2023 and 2024",
     "pit_feasible": False,
     "assets": ("XAUUSD", "USDZAR"),
     "mechanism_families": ("release_surprise", "regime_break"),
     "how_to_fetch": "download the monthly CPI release from zimstat.co.zw and ALSO capture the "
                     "methodology note that accompanies each re-basing; store each vintage "
                     "separately and never splice across a documented break"},
    {"name": "Bank of Botswana currency basket weights and annual rate of crawl",
     "source": "Bank of Botswana Monetary Policy Statement and Botswana Financial Statistics",
     "coverage": "the SDR and rand weights of the pula basket and the rate of crawl announced "
                 "for each year, with the nominal and real effective exchange rate series",
     "frequency": "annual announcement with monthly statistics", "publication_lag_days": 30.0,
     "revisions": "the announced parameters are not revised; the effective exchange rate indices "
                  "are re-based periodically",
     "licence": "free, public", "history_from": "2005, when the crawling band was adopted",
     "pit_feasible": True,
     "assets": ("USDZAR", "EURZAR", "GBPZAR", "ZARJPY"),
     "mechanism_families": ("central_bank_surprise", "carry_funding", "transfer"),
     "how_to_fetch": "parse the annual Monetary Policy Statement PDF from bankofbotswana.bw for "
                     "the basket composition and the rate of crawl, and take the monthly "
                     "effective-rate series from Botswana Financial Statistics"},
    {"name": "Banco Nacional de Angola FX auction allocation and reference rate",
     "source": "Banco Nacional de Angola",
     "coverage": "each auction's date, the dollars allocated, the reference rate struck and the "
                 "participating banks, with the reserve position beside it",
     "frequency": "weekly to fortnightly", "publication_lag_days": 1.0,
     "revisions": "auction results are not revised; the reserve series is",
     "licence": "free, public", "history_from": "2018, when the hard peg was abandoned",
     "pit_feasible": True,
     "assets": ("XBRUSD", "XTIUSD", "USDZAR"),
     "mechanism_families": ("central_bank_surprise", "carry_funding", "physical_flow"),
     "how_to_fetch": "fetch the estatísticas and mercados sections of bna.ao, parse the "
                     "Portuguese auction notices for date, montante alocado and taxa de "
                     "referência, and join to the monthly reserve table"},
    {"name": "OPEC Monthly Oil Market Report secondary-source production estimates",
     "source": "OPEC Secretariat",
     "coverage": "monthly crude production by country from secondary sources and from direct "
                 "communication, with Angola inside the table to December 2023 and outside it "
                 "from January 2024",
     "frequency": "monthly", "publication_lag_days": 12.0,
     "revisions": "prior months are revised in every issue, which is why the FIRST print and the "
                  "settled print are different quantities and both matter",
     "licence": "free, public (OPEC terms)", "history_from": "2003", "pit_feasible": True,
     "assets": ("XBRUSD", "XTIUSD"),
     "mechanism_families": ("release_surprise", "physical_flow", "regime_break"),
     "how_to_fetch": "download the MOMR PDF from opec.org on its published release date, parse "
                     "Table 5-1 (secondary sources) and the direct-communication table, and "
                     "store the vintage: the Angolan row moves between the member and non-member "
                     "blocks at the 2024-01 boundary"},
    {"name": "ANPG Angolan crude export loading programmes and concession awards",
     "source": "Agência Nacional de Petróleo, Gás e Biocombustíveis",
     "coverage": "the monthly loading programme by grade and the licensing-round awards and "
                 "farm-out approvals",
     "frequency": "monthly with irregular award notices", "publication_lag_days": 10.0,
     "revisions": "the programme is re-cut as cargoes slip; the award notices are final",
     "licence": "free, public", "history_from": "2019, when the ANPG took over as concessionaire",
     "pit_feasible": False,
     "assets": ("XBRUSD", "XTIUSD"),
     "mechanism_families": ("physical_flow", "capacity_ramp", "corporate_flow"),
     "how_to_fetch": "crawl anpg.co.ao's Portuguese notices and the Diário da República award "
                     "publications; the loading programme circulates to traders before it is "
                     "posted, so the press-reported date and the published date are both kept"},
    {"name": "Banco de Moçambique MIMO decisions, exchange rate and reserves",
     "source": "Banco de Moçambique",
     "coverage": "the policy rate decisions with their Portuguese statements, the daily "
                 "reference rate and the monthly reserve position",
     "frequency": "roughly every six weeks for the rate, daily for the FX reference",
     "publication_lag_days": 1.0,
     "revisions": "decisions are not revised; the reserve series is restated",
     "licence": "free, public", "history_from": "2017, when MIMO replaced the aggregate target",
     "pit_feasible": True,
     "assets": ("XALUSD", "XNGUSD", "USDZAR"),
     "mechanism_families": ("central_bank_surprise", "carry_funding"),
     "how_to_fetch": "fetch bancomoc.mz's comunicados do Comité de Política Monetária and the "
                     "daily taxas de câmbio page; the statement is Portuguese and is the primary "
                     "document, not the English wire summary"},
    {"name": "Mozambique LNG project timetable: FID, force majeure, lifting and first cargo",
     "source": "Instituto Nacional de Petróleo, ENH, TotalEnergies and Eni statements",
     "coverage": "every dated milestone of Coral South, Mozambique LNG (Area 1) and Rovuma "
                 "(Area 4), with the capacity each tranche adds",
     "frequency": "irregular, event-driven", "publication_lag_days": 0.0,
     "revisions": "projected dates move and several have moved by years; a projected milestone "
                  "is never treated as an arrived one",
     "licence": "free, public (operator and regulator terms)", "history_from": "2010",
     "pit_feasible": True,
     "assets": ("XNGUSD", "XBRUSD"),
     "mechanism_families": ("capacity_ramp", "event_reaction", "physical_flow"),
     "how_to_fetch": "watch inp.gov.mz, the operators' press pages and the Portuguese press for "
                     "dated statements; record each as (date, milestone, status) where status is "
                     "GAZETTED, ANNOUNCED or PROJECTED, and promote no cell on a PROJECTED row"},
    {"name": "Mozambican corridor throughput: Beira, Nacala and Maputo",
     "source": "Portos e Caminhos de Ferro de Moçambique, Cornelder de Moçambique and the "
               "Nacala Logistics Corridor",
     "coverage": "cargo tonnage, container volumes and the transit split by destination country "
                 "for the three corridors that serve Zimbabwe, Zambia and Malawi",
     "frequency": "monthly to annual, irregularly published", "publication_lag_days": 60.0,
     "revisions": "restated in the annual report; the monthly series is incomplete in some years",
     "licence": "free, public (operator terms)", "history_from": "2012", "pit_feasible": False,
     "assets": ("XCUUSD", "XZNUSD", "SUGAR"),
     "mechanism_families": ("chokepoint", "physical_flow", "transfer"),
     "how_to_fetch": "crawl cfm.co.mz and cornelder.co.mz for the Portuguese throughput bulletins "
                     "and the annual reports, and join the transit-by-country split to the "
                     "`copperbelt` pack's own production series -- a fall here is a ROUTING "
                     "event until another corridor's series says otherwise"},
    {"name": "Lobito Atlantic Railway copper and cobalt transit volumes",
     "source": "Lobito Atlantic Railway concession and the Angolan Ministry of Transport",
     "coverage": "tonnage railed from the Copperbelt to Lobito since the concession's first "
                 "trains, with the concession's own capacity ramp targets",
     "frequency": "irregular, with milestone announcements", "publication_lag_days": 30.0,
     "revisions": "announced volumes are press-reported before they are official",
     "licence": "free, public", "history_from": "2024", "pit_feasible": False,
     "assets": ("XCUUSD", "XZNUSD"),
     "mechanism_families": ("chokepoint", "capacity_ramp", "physical_flow"),
     "how_to_fetch": "watch lobitocorridor.com, the Angolan Portuguese press and the DRC and "
                     "Zambian mining press for tonnage statements; this is a NEW series with "
                     "little history and a short series is UNMEASURED before it is a signal"},
    {"name": "Zambezi River Authority Kariba lake level and water allocation",
     "source": "Zambezi River Authority",
     "coverage": "the weekly lake level in metres above sea level, usable storage, the water "
                 "allocation to the Zimbabwean and Zambian power stations, and the inflow outlook",
     "frequency": "weekly", "publication_lag_days": 3.0,
     "revisions": "levels are not revised; the allocation is re-cut in-year when inflows fail",
     "licence": "free, public", "history_from": "2015 for the machine-readable bulletins",
     "pit_feasible": True,
     "assets": ("XPTUSD", "XCUUSD", "XALUSD"),
     "mechanism_families": ("physical_flow", "supply_shock", "chokepoint"),
     "how_to_fetch": "fetch the weekly lake-level bulletin PDF from zambezira.org, parse the "
                     "level and usable-storage figures, and archive each issue -- the archive is "
                     "incomplete and a missing week is UNMEASURED, never interpolated"},
    {"name": "Hidroeléctrica de Cahora Bassa generation and export",
     "source": "Hidroeléctrica de Cahora Bassa and Electricidade de Moçambique",
     "coverage": "generation, availability and energy exported to South Africa and Zimbabwe, "
                 "with the Motraco line's delivery to the Mozal smelter",
     "frequency": "monthly to annual", "publication_lag_days": 45.0,
     "revisions": "restated in the annual report", "licence": "free, public (company terms)",
     "history_from": "2010", "pit_feasible": False,
     "assets": ("XALUSD", "XCUUSD"),
     "mechanism_families": ("supply_shock", "physical_flow", "corporate_flow"),
     "how_to_fetch": "crawl hcb.co.mz's Portuguese relatórios and the EDM annual report for the "
                     "generation and export tables; the smelter's power interruptions are "
                     "reported in the Mozambican press before they reach a statistic"},
    {"name": "Zimbabwe mineral export receipts and gold deliveries",
     "source": "Minerals Marketing Corporation of Zimbabwe, the Ministry of Mines and Fidelity "
               "Gold Refinery",
     "coverage": "export receipts by mineral, platinum-group and chrome volumes, and monthly "
                 "gold deliveries split between primary producers and small-scale miners",
     "frequency": "monthly to annual", "publication_lag_days": 45.0,
     "revisions": "restated as late deliveries are registered",
     "licence": "free, public", "history_from": "2016", "pit_feasible": False,
     "assets": ("XPTUSD", "XPDUSD", "XAUUSD"),
     "mechanism_families": ("physical_flow", "official_demand", "administered_price"),
     "how_to_fetch": "collect the MMCZ and Ministry of Mines tables and the RBZ's monthly gold "
                     "delivery figure; cross-check against UN Comtrade partner-reported imports, "
                     "because the split between declared and mirror volumes IS the measurement"},
    {"name": "Kimberley Process annual rough diamond production and trade statistics",
     "source": "Kimberley Process Certification Scheme",
     "coverage": "production volume, value and average price per carat by participant country, "
                 "with imports and exports by partner",
     "frequency": "annual", "publication_lag_days": 300.0,
     "revisions": "participants restate submissions for years afterwards",
     "licence": "free, public", "history_from": "2004", "pit_feasible": False,
     "assets": ("US500", "UK100", "USDZAR"),
     "mechanism_families": ("physical_flow", "nominal_demand"),
     "how_to_fetch": "download the annual global summary tables from kimberleyprocess.com, take "
                     "the Botswana production value and carats, and use it ONLY to date an era: "
                     "a series a year late can never condition a week"},
    {"name": "Bank of Namibia reserves, SACU receipts and the repo spread to the SARB",
     "source": "Bank of Namibia Quarterly Bulletin",
     "coverage": "gross reserves, import cover, the quarterly SACU transfer and the Namibian "
                 "repo rate against the South African one",
     "frequency": "quarterly", "publication_lag_days": 75.0,
     "revisions": "reserve and balance-of-payments lines are revised for several quarters",
     "licence": "free, public", "history_from": "2000", "pit_feasible": False,
     "assets": ("USDZAR", "ZARJPY"),
     "mechanism_families": ("transfer", "carry_funding", "central_bank_surprise"),
     "how_to_fetch": "download the Quarterly Bulletin PDF and the statistical annex from "
                     "bon.com.na, take the reserves, SACU receipts and repo series, and compute "
                     "the spread to the SARB repo -- the spread is the measure of how little "
                     "room the 1:1 peg leaves"},
    {"name": "SACU common revenue pool and member shares",
     "source": "SACU Secretariat and the member states' budget documents",
     "coverage": "the size of the common customs and excise pool and each member's share under "
                 "the revenue-sharing formula, with the stabilisation adjustment",
     "frequency": "annual with quarterly payments", "publication_lag_days": 90.0,
     "revisions": "adjusted retrospectively when the pool outturn differs from the forecast, "
                  "which is the mechanism's most under-appreciated feature",
     "licence": "free, public", "history_from": "2002 agreement", "pit_feasible": True,
     "assets": ("USDZAR",),
     "mechanism_families": ("transfer", "institutional_flow"),
     "how_to_fetch": "take the pool and share figures from sacu.int and cross-check against the "
                     "Botswana and Namibian budget statements, which publish the transfer as a "
                     "named revenue line and therefore date it precisely"},
    {"name": "Namibia Statistics Agency CPI, trade and uranium export volumes",
     "source": "Namibia Statistics Agency",
     "coverage": "the monthly consumer price index, merchandise trade by commodity and the "
                 "uranium export volume and value line",
     "frequency": "monthly", "publication_lag_days": 20.0,
     "revisions": "trade lines are revised for several months; the CPI is not",
     "licence": "free, public", "history_from": "2010", "pit_feasible": True,
     "assets": ("USDZAR", "XNGUSD"),
     "mechanism_families": ("release_surprise", "physical_flow"),
     "how_to_fetch": "download the monthly CPI and trade bulletins from nsa.org.na and take the "
                     "uranium row from the commodity annex; the informative Namibian CPI quantity "
                     "is the RESIDUAL to South African CPI, never the level, because the peg "
                     "makes the level mostly imported"},
    {"name": "World Bank Pink Sheet monthly commodity prices",
     "source": "World Bank Commodity Markets",
     "coverage": "monthly nominal prices for platinum, aluminium, copper, zinc, crude, natural "
                 "gas, maize, wheat, sugar and cotton -- the whole executable surface of this "
                 "pack in one table",
     "frequency": "monthly", "publication_lag_days": 2.0,
     "revisions": "occasionally restated; the historical workbook is re-issued each month",
     "licence": "free, public (World Bank terms)", "history_from": "1960", "pit_feasible": True,
     "assets": ("XPTUSD", "XALUSD", "XCUUSD", "XZNUSD", "XBRUSD", "CORN", "WHEAT", "SUGAR",
                "COTTON"),
     "mechanism_families": ("physical_flow", "nominal_demand", "residual"),
     "how_to_fetch": "download the monthly CMO-Pink-Sheet.xlsx from the World Bank commodity "
                     "markets page and keep each vintage; it is the common price spine every "
                     "physical claim in this pack is normalised against"},
    {"name": "UN Comtrade mirror statistics for PGM, gold, diamonds and crude",
     "source": "UN Comtrade",
     "coverage": "each country's declared exports against the partner countries' declared "
                 "imports, by HS code and partner",
     "frequency": "annual, with monthly for some reporters", "publication_lag_days": 365.0,
     "revisions": "heavily revised for years", "licence": "free, public (UN terms)",
     "history_from": "2000", "pit_feasible": False,
     "assets": ("XPTUSD", "XAUUSD", "XCUUSD"),
     "mechanism_families": ("physical_flow", "scouts"),
     "how_to_fetch": "query comtradeplus.un.org for HS 7110 (PGM), 7108 (gold), 7102 (diamonds) "
                     "and 2709 (crude) for each of the five as reporter AND as partner; the GAP "
                     "between the two is the measurement and a year's lag means it dates an era "
                     "and never a week"},
)
# __CHUNK_E_END__




