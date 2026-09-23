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
              "of the basket is a step change in the pula's rand content, datable to the day"},
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
        "sa_zw_rate_ecology", "The Zimbabwean parallel-rate ecology: ZimPriceCheck and "
                              "Marketwatch, the rate-quoting Telegram, WhatsApp and X "
                              "channels, and the "
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
# --------------------------------------------------------------------------- actors
#: TWENTY-THREE ACTORS, AT LEAST FOUR PER JURISDICTION. The floor is twelve for a single country
#: and a five-country pack that stops at twelve has read one country and guessed four times.
#: Every row carries all eleven fields, and the FALSIFIER is the field that decides whether the
#: row is a research object or a story.
ACTORS: tuple[dict[str, Any], ...] = (
    # ---------------------------------------------------------------- Zimbabwe
    {"name": "The Reserve Bank of Zimbabwe and the ZiG's published reserve cover",
     "holds": "the currency itself, the gold and foreign-exchange reserves declared as its "
              "backing, the export surrender requirement on miners, and the willing-buyer-"
              "willing-seller rate",
     "forced_to": ("publish a reserve cover for a currency whose whole claim to credibility is "
                   "that it has one",
                   "take a surrendered share of every exporter's dollar receipts at the official "
                   "rate, which is a tax whose size is the parallel premium",
                   "choose, at every stress point, between defending the rate and defending the "
                   "reserve -- and it has chosen the reserve twice in two years"),
     "when": "weekly for the rate, semi-annually for the Monetary Policy Statement, and "
             "off-cycle whenever a regime changes -- 2024-04-05 and 2024-09-27 were both "
             "off-cycle",
     "information": ("the true reserve position before it is published",
                     "the size of the surrender pool arriving from PGM and gold exporters",
                     "the queue of unmet importer demand at the official rate"),
     "constraints": ("no IMF programme and unresolved arrears since 1999, so there is no external "
                     "anchor and no disbursement to defend a rate with",
                     "an economy that is already partly dollarised in practice, so a domestic "
                     "money the public can refuse is a weak instrument",
                     "a reserve cover that is itself mostly gold, which ties the currency's "
                     "credibility to a price the RBZ does not set"),
     "instruments": ("XAUUSD", "XPTUSD", "USDZAR"),
     "counterparties": ("the Great Dyke miners and the gold producers who surrender receipts",
                        "the commercial banks running the interbank market",
                        "the importers queuing for the official rate",
                        "the informal money changers who set the price that clears"),
     "observables": ("the willing-buyer-willing-seller rate and its gap to the trackers' street "
                     "rate", "the published reserve cover and its composition",
                     "monthly gold deliveries to Fidelity Gold Refinery",
                     "the money supply in ZiG"),
     "impact": "a currency backed by gold makes the RBZ a persistent official-sector BUYER of "
               "gold, which is XAUUSD demand; a devaluation is a dated frontier-risk event that "
               "reaches USDZAR on the day and the mining sector's realised revenue for quarters",
     "persistence": "regime-scale: each of the six currency eras since 2008 has lasted years and "
                    "partitions every Zimbabwean series; none decays",
     "falsifier": "the RBZ's published gold backing does not rise through periods it says it is "
                  "accumulating, and Zimbabwean gold deliveries show no diversion from export to "
                  "domestic purchase across the 2024-04-05 boundary once the gold price and "
                  "small-scale production are controlled for -- in which case the ZiG's gold "
                  "backing is an accounting label and SA-D's official-demand channel dies",
     "notes": "THE MOST DATABLE MONETARY ACTOR IN THE DESK'S ROSTER precisely because it acts by "
              "STATUTORY INSTRUMENT: every regime change has a gazette number and a commencement "
              "date, which Veritas publishes within days"},
    {"name": "The Great Dyke platinum-group miners and the beneficiation obligation",
     "holds": "the world's third-largest PGM production base, concentrate that must be smelted "
              "somewhere, and long-term offtake to South African refining capacity",
     "forced_to": ("surrender a share of export proceeds at the official rate, which is a "
                   "revenue haircut that moves with the parallel premium",
                   "invest in domestic smelting and refining capacity or face an export "
                   "restriction that has been legislated, deferred and re-legislated",
                   "sell a metal whose basket price is set by South African supply and by "
                   "autocatalyst demand neither they nor Harare influences"),
     "when": "quarterly production reporting, annual capital commitments, and an irregular "
             "policy clock set by the Ministry of Mines and the budget",
     "information": ("concentrate grades and the palladium-to-platinum ratio of the ore before "
                     "the market sees the volumes",
                     "the real state of smelter and refinery construction against the deadline",
                     "the surrender cost actually borne, which is not the published rate"),
     "constraints": ("power: the Dyke's smelters need firm supply and Kariba's level decides "
                     "whether they get it",
                     "the capital cost of a refinery in a country with no external financing",
                     "a metal price that has spent years below the marginal cost of new supply"),
     "instruments": ("XPTUSD", "XPDUSD", "XAUUSD"),
     "counterparties": ("the South African smelters and refiners who treat the concentrate",
                        "the Ministry of Mines and the Minerals Marketing Corporation",
                        "the Reserve Bank as the surrender counterparty",
                        "the autocatalyst buyers at the far end of the chain"),
     "observables": ("quarterly production and shipment volumes in the operators' reports",
                     "the Ministry's export tables and the mirror import statistics",
                     "the gazetted commencement or deferral of the concentrate export control",
                     "announced smelter and refinery capital commitments"),
     "impact": "an export restriction on concentrate does not destroy supply, it DELAYS and "
               "RELOCATES it: metal that would have reached the market as refined ounces sits as "
               "concentrate stock instead, which is a timing shock to XPTUSD and XPDUSD rather "
               "than a level one, and the pack tests it as a timing shock",
     "persistence": "quarters to years; a deferral resets the clock and the deferrals themselves "
                    "are the most informative events in the series",
     "falsifier": "PGM export volumes in the mirror statistics show no interruption across any "
                  "gazetted commencement date, and no concentrate stock build appears in the "
                  "operators' own reporting -- in which case the restriction was never enforced "
                  "and SA-A's timing channel is a press story",
     "notes": "ZIMPLATS, MIMOSA AND UNKI ARE ACTORS AND NEVER INSTRUMENTS. Their parents are "
              "listed elsewhere and none is hunted here (two-lane order, 2026-09-06)"},
    {"name": "Fidelity Gold Refinery and the small-scale gold delivery plane",
     "holds": "the statutory monopoly on buying Zimbabwean gold, the payment terms small-scale "
              "miners actually receive, and the physical metal behind the gold coins and tokens",
     "forced_to": ("pay producers a price that is a published DISCOUNT to the London benchmark, "
                   "partly in local currency, which is the whole reason side-selling exists",
                   "publish monthly delivery volumes split between primary and small-scale "
                   "producers",
                   "supply the metal for the gold coin and gold-backed token programmes"),
     "when": "monthly deliveries; payment-term changes arrive by circular and are irregular",
     "information": ("how much gold is being side-sold across the border, which it infers from "
                     "its own delivery shortfall",
                     "the real payment delay small-scale miners face",
                     "the metal actually committed to the coin and token programmes"),
     "constraints": ("a porous border with South Africa and Mozambique that gives every producer "
                     "an alternative buyer",
                     "a local-currency payment component whose value depends on the premium",
                     "refining capacity and assay throughput"),
     "instruments": ("XAUUSD",),
     "counterparties": ("tens of thousands of small-scale and artisanal miners",
                        "the primary gold producers", "the Reserve Bank as the ultimate buyer",
                        "the informal cross-border buyers who are its competition"),
     "observables": ("monthly delivery kilogrammes by producer class",
                     "the announced payment split between USD and local currency",
                     "the gap between Zimbabwean declared gold exports and the partner-reported "
                     "imports in the mirror statistics"),
     "impact": "a payment-term change switches a declared flow on or off within a quarter, which "
               "makes the delivery series a DATED TREATMENT on an informal physical flow into "
               "XAUUSD -- an unusually clean natural experiment on a market that normally offers "
               "none",
     "persistence": "one to three quarters after each payment-term change; the effect decays as "
                    "the informal channel re-prices",
     "falsifier": "a payment-term change produces no measurable move in declared deliveries "
                  "against matched months, and the mirror gap does not move in the opposite "
                  "direction -- in which case the delivery series is measuring production and "
                  "not a routing decision, and SA-D's window closes",
     "notes": "THE SAME MECHANISM THE `east_africa` PACK FOUND IN UGANDA, pointed the other way: "
              "there an export levy switched a declared re-export OFF, here a payment term "
              "switches a declared delivery ON. Each is the other's natural placebo"},
    {"name": "The Zimbabwean statutory-instrument machine and the Veritas archive",
     "holds": "the legal instrument through which every Zimbabwean economic policy actually "
              "happens -- the statutory instrument, gazetted on a Friday with a number and a "
              "commencement date",
     "forced_to": ("publish in the Government Gazette before an instrument binds",
                   "give each instrument a number and a commencement date, which is what makes "
                   "Zimbabwean policy uniquely datable",
                   "defer, amend or repeal in the same form, so a reversal is as datable as the "
                   "original"),
     "when": "Fridays, with Veritas publishing the text within days",
     "information": ("the text of an instrument before the market has read it, in the window "
                     "between gazette and press coverage",
                     "which instruments are drafted and not yet gazetted"),
     "constraints": ("an instrument that the economy simply refuses to comply with is a dead "
                     "letter, and several have been",
                     "the courts, which have struck down instruments before",
                     "the deferral pressure from the very industries an instrument binds"),
     "instruments": ("XPTUSD", "XPDUSD", "XAUUSD", "USDZAR"),
     "counterparties": ("the miners, exporters and banks each instrument binds",
                        "Veritas and the legal community that publishes and challenges them",
                        "the press that reports the announcement rather than the instrument"),
     "observables": ("the gazette number, the commencement date and the text itself",
                     "the gap between a ministerial announcement and the gazette, which is "
                     "frequently months and sometimes forever",
                     "the amendment and deferral notices"),
     "impact": "IT IS THE DATING MECHANISM FOR THIS ENTIRE JURISDICTION. Every SA-A, SA-B and "
               "SA-C event window is anchored to a gazette date rather than a press date, and "
               "the two differ often enough that anchoring to the press would misdate a large "
               "fraction of the sample",
     "persistence": "the instrument persists until amended; the announcement-to-gazette gap is "
                    "the short-lived part and is itself an observable",
     "falsifier": "event windows anchored to gazette dates and to press-announcement dates give "
                  "the same estimates across the pack's own event set -- in which case the "
                  "distinction costs nothing and the cheaper anchor is fine",
     "notes": "VERITAS IS THE REASON SA-B IS TESTABLE AT ALL, and the reason this pack's "
              "beneficiation claims carry instrument numbers rather than ministerial quotes"},
    {"name": "The Zimbabwean money changer and the ZSE-to-VFEX dollarisation arbitrage",
     "holds": "the price at which local currency actually changes hands, and the cheapest lawful "
              "route out of it -- a listing that settles in dollars",
     "forced_to": ("quote a two-way price every day in a currency with no forward market",
                   "price the risk that a statutory instrument criminalises the trade overnight, "
                   "which has happened",
                   "absorb the surrender-requirement distortion, because the official rate the "
                   "exporters surrender at is not the rate anybody else can get"),
     "when": "continuously, with the trackers aggregating a daily print",
     "information": ("the real clearing rate hours before any tracker publishes it",
                     "which corporates are converting and in what size",
                     "the direction of the next regulatory move, inferred from enforcement"),
     "constraints": ("periodic criminalisation and arrests",
                     "the mobile-money rails, whose freezing has been used as a policy tool",
                     "a local currency whose supply the central bank controls"),
     "instruments": ("XAUUSD", "USDZAR"),
     "counterparties": ("households and small businesses", "corporates needing to convert",
                        "the banks, at the official rate, for the trades that can go there",
                        "the listed companies choosing between the ZSE and the VFEX"),
     "observables": ("the daily tracked street rate and the official rate beside it",
                     "the ZSE-to-VFEX listing migrations and their dates",
                     "the ZSE index in local currency against the VFEX index in dollars",
                     "mobile-money transaction values when a freeze is imposed"),
     "impact": "the premium is the REGIME-STRESS STATE this pack conditions on, and the VFEX "
               "migration is a dated, public vote on the currency cast by the people with the "
               "most at stake; both reach the executable surface through the frontier-risk "
               "carrier and through gold demand",
     "persistence": "the premium mean-reverts within a regime and jumps across regime "
                    "boundaries; the migrations do not reverse",
     "falsifier": "the tracked premium has no relationship to the ZSE-VFEX index spread once "
                  "the gold price and the rand are controlled for -- in which case the trackers "
                  "are measuring noise rather than the currency, and SA-E loses its observable",
     "notes": "OLD MUTUAL'S DUAL LISTING WAS THE CLASSIC IMPLIED-RATE OBSERVABLE UNTIL ITS ZSE "
              "SUSPENSION IN JUNE 2020 SWITCHED IT OFF. It appears here as an observable and "
              "never as an instrument, and the DATE the series ended is itself the measurement"},
    # ---------------------------------------------------------------- Botswana
    {"name": "Debswana and the Government of Botswana's fifty-fifty diamond joint venture",
     "holds": "most of the world's highest-value rough diamond production, a 50/50 partnership "
              "with De Beers, and the state's single largest revenue source",
     "forced_to": ("sell through an agreed channel split between De Beers' sightholder sales and "
                   "the state's own Okavango Diamond Company, on terms renegotiated periodically",
                   "cut production when the market cannot absorb it, because rough diamonds "
                   "cannot be hedged and inventory is the only shock absorber",
                   "fund a budget in which diamonds are most of the export receipts"),
     "when": "quarterly production reporting inside Anglo American's results, with the sales "
             "channel running on the ten-cycle calendar",
     "information": ("the assortment quality of what is being offered before buyers see it",
                     "the production cut decision before it is announced",
                     "the state's own marketing channel's realised prices"),
     "constraints": ("a market with no futures, no hedge and no public price",
                     "lab-grown stones taking the low end of the natural market",
                     "the agreement with De Beers, which sets how much the state may sell itself"),
     "instruments": ("US500", "UK100", "USDZAR"),
     "counterparties": ("De Beers Global Sightholder Sales and the sightholders",
                        "the Okavango Diamond Company auction buyers",
                        "the Antwerp, Dubai, Mumbai and Surat trade",
                        "the Government of Botswana as shareholder and taxing authority"),
     "observables": ("production volume and carats in the parent's quarterly results",
                     "the sales-cycle revenue prints",
                     "Statistics Botswana's export value and carat series",
                     "announced production cuts and their dates"),
     "impact": "a production cut is a supply response to a DEMAND signal, so the cut itself dates "
               "a luxury-demand downturn with a lag; the revenue swing runs straight into the "
               "budget and therefore into the SACU-plus-diamonds fiscal channel",
     "persistence": "one to four quarters; the inventory cycle in rough diamonds is slow because "
                    "the stones do not perish and the sellers can wait",
     "falsifier": "sales-cycle revenue and Botswana's export value have no relationship to any "
                  "broad luxury-demand measure once the lab-grown share and the assortment mix "
                  "are controlled for -- in which case SA-F is measuring De Beers' channel "
                  "decisions and not world demand",
     "notes": "DEBSWANA AND DE BEERS ARE ACTORS. Neither their parent nor any listed "
              "intermediary appears as an instrument anywhere in this pack"},
    {"name": "De Beers Global Sightholder Sales and the ten-cycle calendar",
     "holds": "the largest share of the world's rough supply by value, a fixed calendar of ten "
              "sales cycles a year, and the decision of how much to offer at each",
     "forced_to": ("publish a revenue figure after every cycle, which is a rare voluntary "
                   "high-frequency disclosure by a dominant seller",
                   "choose between defending price by withholding supply and defending volume by "
                   "clearing it, and the choice is visible in the number",
                   "give sightholders flexibility in weak markets, which turns a price problem "
                   "into a volume number"),
     "when": "ten times a year on a published calendar, with the revenue figure days after each "
             "cycle closes",
     "information": ("the demand the sightholders actually expressed before the number is out",
                     "the extent of the refusals and deferrals granted",
                     "the assortment and price adjustments made inside the cycle"),
     "constraints": ("the polished market downstream, whose inventory it cannot see directly",
                     "the lab-grown substitute at the low end",
                     "its own agreement with Botswana, which caps how much it controls"),
     "instruments": ("US500", "UK100", "USDZAR"),
     "counterparties": ("the sightholders and the Indian cutting and polishing industry",
                        "Debswana and the Government of Botswana",
                        "the Namibian and South African production it also sells"),
     "observables": ("the cycle revenue figure and its two published comparisons",
                     "the cycle calendar itself, which is published in advance",
                     "the commentary accompanying each release"),
     "impact": "TEN DATED READS A YEAR ON GLOBAL LUXURY DEMAND, with a published calendar and "
               "essentially no systematic coverage: a revenue miss against its own trailing "
               "seasonal norm is an event study nobody has run",
     "persistence": "zero to ten sessions for the release effect; one to four quarters for what "
                    "the sequence says about the cycle",
     "falsifier": "cycle revenue surprises against the trailing seasonal norm have no measurable "
                  "relationship to luxury-heavy equity indices over any horizon out to a quarter, "
                  "controlling for the broad index -- in which case the print is a channel fact "
                  "and not a demand fact",
     "notes": "THE SINGLE STRONGEST REASON THIS PACK EXISTS. A published, dated, ten-times-a-year "
              "revenue number from the dominant seller in a luxury market, and the desk has "
              "never tested it"},
    {"name": "The Bank of Botswana's basket desk and the Pula Fund",
     "holds": "a currency pegged to a PUBLISHED basket, the rate of crawl announced each year, "
              "and a sovereign fund built from four decades of diamond revenue",
     "forced_to": ("publish the basket weights and the crawl rate, which almost no peg manager "
                   "anywhere does",
                   "defend a real effective rate rather than a nominal one, which is what the "
                   "crawl is for",
                   "run down reserves when diamond revenue falls, because the peg cannot absorb "
                   "the shock and the budget will not"),
     "when": "the annual Monetary Policy Statement for the parameters; daily for the fixing",
     "information": ("the intended reweighting before it is announced",
                     "the true reserve drawdown pace",
                     "the real effective rate misalignment it is targeting"),
     "constraints": ("a 40% rand weight that imports South African monetary conditions "
                     "mechanically",
                     "an export base that is one commodity with no hedge",
                     "an open capital account since 1999"),
     "instruments": ("USDZAR", "EURZAR", "GBPZAR", "ZARJPY"),
     "counterparties": ("the domestic banks that transact at the fixing",
                        "the South African Reserve Bank, indirectly, through the 40% weight",
                        "the importers and the diamond exporters",
                        "the Pula Fund's external managers"),
     "observables": ("the announced basket weights and rate of crawl",
                     "the daily fixing and the implied residual to a 60/40 replication",
                     "gross reserves and the Pula Fund's reported value",
                     "the nominal and real effective exchange rate indices"),
     "impact": "a PUBLISHED weight makes the pula's rand content arithmetic, so the residual "
               "between the observed fixing and a mechanical 60/40 replication is a clean "
               "measure of discretionary intervention -- and discretion is what a peg desk does "
               "when it is under pressure",
     "persistence": "the weights persist for years; the crawl is annual; the residual is a "
                    "weekly-to-monthly state",
     "falsifier": "the observed pula fixing is not replicable from the published basket and crawl "
                  "to within a small residual over a quiet period -- in which case the published "
                  "weights are not the operative rule and SA-G's whole premise is wrong",
     "notes": "THE CLEANEST TESTABLE FX MECHANISM IN THE PACK precisely because the authority "
              "published the answer key; the measurement is the RESIDUAL, not the level"},
    {"name": "The Botswana Ministry of Finance and the SACU receipts line",
     "holds": "a budget in which diamonds and a formula-driven customs transfer are most of the "
              "revenue, and a development spending plan sized off both",
     "forced_to": ("write a budget before the diamond year is known and after the SACU transfer "
                   "is known, which is an unusual information ordering",
                   "absorb the SACU stabilisation adjustment when the pool outturn differs from "
                   "the forecast, retrospectively",
                   "draw on reserves or borrow when diamonds fall, because the peg forbids the "
                   "usual adjustment"),
     "when": "the Budget Speech in February for a 1 April start; SACU transfers quarterly",
     "information": ("the diamond revenue outturn before the trade statistics publish it",
                     "the next year's SACU forecast before it is public"),
     "constraints": ("a revenue base with two items in it",
                     "a peg that removes the depreciation channel",
                     "a wage bill and development programme sized in better years"),
     "instruments": ("USDZAR", "US500"),
     "counterparties": ("Debswana and De Beers as the revenue source",
                        "the SACU Secretariat and South Africa as the pool's largest contributor",
                        "the Bank of Botswana as reserve manager",
                        "the domestic bond market"),
     "observables": ("the Budget Speech's revenue assumptions",
                     "the SACU receipts line and the stabilisation adjustment",
                     "quarterly government deposits at the central bank",
                     "domestic bond auction sizes and yields"),
     "impact": "a diamond downturn and a SACU shortfall are the same fiscal shock arriving "
               "through two channels, and because the peg blocks depreciation the adjustment "
               "shows up in reserves and issuance instead -- which is a measurable, published "
               "path that a floating-rate economy hides in its currency",
     "persistence": "one to three fiscal years; the SACU stabilisation adjustment lags by two "
                    "years by construction, which is the single most under-modelled feature",
     "falsifier": "diamond revenue falls do not show up in reserves, issuance or the SACU "
                  "adjustment within three years -- in which case there is a buffer this pack "
                  "has not found and the fiscal channel is not the adjustment mechanism",
     "notes": "THE SACU FORMULA IS A DATED, PUBLISHED, RETROSPECTIVELY ADJUSTED FISCAL TRANSFER "
              "and it binds Namibia as hard as Botswana, which is why SA-H is shared between them"},
    # ---------------------------------------------------------------- Mozambique
    {"name": "The Coral South floating LNG operator and the Area 4 partners",
     "holds": "the only producing LNG facility in Mozambique, roughly 3.4 mtpa of capacity "
              "offshore Cabo Delgado, and a full offtake contract for its output",
     "forced_to": ("produce against a contract rather than into the spot market, so its cargoes "
                   "are a SUPPLY SCHEDULE fact and not a price-taking one",
                   "operate offshore precisely because the onshore province is insecure, which "
                   "is why this project produced and the onshore one did not",
                   "report milestones to the Instituto Nacional de Petróleo"),
     "when": "first cargo in November 2022; continuous production since, with cargo liftings "
             "reported irregularly",
     "information": ("the lifting schedule before it is public",
                     "the real availability of the vessel",
                     "the state of the second floating unit's development decision"),
     "constraints": ("a single floating vessel with no redundancy",
                     "a security situation onshore that the offshore design routes around",
                     "a contract that leaves no spot optionality"),
     "instruments": ("XNGUSD", "XBRUSD"),
     "counterparties": ("the offtaker holding the full output contract",
                        "ENH as the national partner", "the Instituto Nacional de Petróleo",
                        "the Mozambican treasury, which taxes the production"),
     "observables": ("the dated milestone sequence: FID, sail-away, first gas, first cargo",
                     "cargo liftings as reported by the operator and the shipping press",
                     "the INP's project reporting"),
     "impact": "a capacity tranche arriving is a step change in a global supply schedule that the "
               "market has already priced expectations for, so the tradable content is the "
               "DEVIATION between the realised date and the expected one, not the tonnage",
     "persistence": "one to eight quarters per tranche",
     "falsifier": "no measurable move in the gas complex around any dated Mozambican milestone "
                  "once US and Qatari start-ups in the same quarters are controlled for -- in "
                  "which case 3.4 mtpa is too small to matter and SA-I's price leg dies while its "
                  "fiscal leg survives",
     "notes": "THE PACK TESTS THE FISCAL LEG FIRST because 3.4 mtpa is large for MOZAMBIQUE and "
              "small for the world; a mechanism that is large where it is measured and small "
              "where it is traded must be tested in that order"},
    {"name": "TotalEnergies' Mozambique LNG and the Cabo Delgado security constraint",
     "holds": "the largest sanctioned LNG project in the country, suspended under force majeure "
              "from April 2021 after the Palma attack and restarted after the 2025 lifting",
     "forced_to": ("declare force majeure when its onshore site became untenable, which is a "
                   "dated, published, unambiguous event",
                   "re-cost and re-schedule after four years of suspension",
                   "depend on a security situation it cannot control for the schedule it "
                   "publishes"),
     "when": "force majeure declared April 2021; lifted in 2025; the revised first-cargo date is "
             "a PROJECTION and is treated as one",
     "information": ("the real state of the site and the contractor mobilisation",
                     "the security assessment behind the lifting decision",
                     "the re-costed capital number before it is disclosed"),
     "constraints": ("an insurgency in the province the plant sits in",
                     "four years of cost inflation on a fixed-scope project",
                     "financiers who must re-approve"),
     "instruments": ("XNGUSD", "XBRUSD"),
     "counterparties": ("the Area 1 partners and the export-credit agencies",
                        "the Mozambican state and ENH",
                        "the offtakers whose contracts were suspended with the project",
                        "the contractors remobilising"),
     "observables": ("the force majeure declaration and the lifting, both dated",
                     "contractor mobilisation reported in the Portuguese press",
                     "the published revised schedule and its slippage"),
     "impact": "THIS IS THE CLEANEST SUPPLY-SCHEDULE NATURAL EXPERIMENT IN THE PACK: roughly 13 "
               "mtpa of expected supply was removed on a dated day in 2021 and restored on a "
               "dated day in 2025, with the expectation published on both sides",
     "persistence": "years: a force majeure on a project of this size moves the whole forward "
                    "supply curve, not a quarter of it",
     "falsifier": "the 2021 declaration and the 2025 lifting show no measurable effect in the gas "
                  "complex or in the forward supply commentary, controlling for the European "
                  "energy shock that dominated 2021-2022 -- and that control is severe enough "
                  "that the pack expects this edge to be hard to establish and says so",
     "notes": "THE 2021 CONFOUND IS ENORMOUS: the force majeure landed in the same year as the "
              "European gas crisis. The pack names the confound on the face of the edge rather "
              "than claiming the cleaner story"},
    {"name": "The Mozal aluminium smelter and Hidroeléctrica de Cahora Bassa",
     "holds": "a large primary aluminium smelter outside Maputo and the hydroelectric station "
              "that powers it through a dedicated transmission line",
     "forced_to": ("run the potlines continuously, because an aluminium smelter that loses power "
                   "for hours suffers damage measured in months",
                   "take power under a long-term arrangement whose price and availability are "
                   "political as well as commercial",
                   "export essentially all of its output, making it most of Mozambique's "
                   "manufactured exports"),
     "when": "continuous operation; power interruptions and tariff renegotiations are the events",
     "information": ("the real state of the potlines after an interruption",
                     "the terms of the power arrangement under negotiation",
                     "Cahora Bassa's own reservoir and availability outlook"),
     "constraints": ("a single power source and a single transmission corridor",
                     "an LME price it does not set",
                     "a reservoir whose inflows are the same Zambezi system as Kariba's"),
     "instruments": ("XALUSD", "XCUUSD"),
     "counterparties": ("Hidroeléctrica de Cahora Bassa and Electricidade de Moçambique",
                        "Eskom, which buys the rest of Cahora Bassa's output",
                        "the LME-referenced buyers of the metal",
                        "the Mozambican treasury"),
     "observables": ("Cahora Bassa generation and availability",
                     "reported smelter interruptions and restarts",
                     "Mozambican aluminium export volumes in the trade statistics",
                     "the Zambezi system's inflows, shared with Kariba"),
     "impact": "a power interruption at a smelter of this size is a REAL, DATED supply "
               "interruption in primary aluminium, and the same reservoir system that causes it "
               "also constrains Zimbabwean and Zambian smelting -- so one hydrological state "
               "moves three metals at once",
     "persistence": "weeks to quarters depending on potline damage; the hydrological state is "
                    "seasonal and persistent",
     "falsifier": "reported Mozal interruptions produce no measurable move in the aluminium "
                  "complex against matched non-event weeks, and Mozambican export volumes do not "
                  "fall -- in which case the interruptions are absorbed by inventory and the "
                  "edge is not there",
     "notes": "MOZAL IS AN ACTOR AND XALUSD IS THE INSTRUMENT. The smelter's owners are listed "
              "companies and none of them is hunted here"},
    {"name": "Portos e Caminhos de Ferro de Moçambique and the Beira and Nacala corridors",
     "holds": "the rail and port capacity through which Zimbabwean, Zambian and Malawian trade "
              "reaches the sea, and the concessions that operate it",
     "forced_to": ("compete with Durban, Dar es Salaam, Walvis Bay and now Lobito for the same "
                   "landlocked cargo",
                   "maintain a rail line through a cyclone-exposed corridor",
                   "publish throughput to its concession partners even when it publishes little "
                   "else"),
     "when": "monthly to annual throughput reporting, irregularly published; cyclone disruptions "
             "are event-driven and seasonal",
     "information": ("the real dwell time and berth availability",
                     "the forward booking position from the landlocked shippers",
                     "the state of the rail after a wet season"),
     "constraints": ("a corridor that floods and a cyclone season that closes it",
                     "rail capacity that is the binding constraint, not port capacity",
                     "four competing corridors for the same tonnes"),
     "instruments": ("XCUUSD", "XZNUSD", "SUGAR", "COTTON"),
     "counterparties": ("Zambian and Congolese copper shippers",
                        "Zimbabwean importers and exporters",
                        "the Malawian trade", "the concession operators at both ports"),
     "observables": ("cargo tonnage and the transit split by destination country",
                     "container dwell times", "cyclone landfalls and line closures",
                     "the competing corridors' own throughput"),
     "impact": "a corridor is only a chokepoint if the cargo cannot go another way, and here it "
               "usually can -- so a fall at Beira is a ROUTING EVENT until Durban, Dar es Salaam "
               "or Lobito says otherwise, and that is a joint measurement with `copperbelt` that "
               "neither pack can make alone",
     "persistence": "two to twelve weeks for a disruption; a routing shift can be permanent",
     "falsifier": "corridor throughput falls at Beira are matched one-for-one by rises elsewhere "
                  "in every episode -- in which case no supply information exists in the series "
                  "at all and only the routing question remains",
     "notes": "THE STRONGEST INTERACTION IN THIS FILE AFTER `za`: the Copperbelt's metal has five "
              "routes and this pack owns two of them"},
    # ---------------------------------------------------------------- Angola
    {"name": "Sonangol and the ANPG as separated operator and concessionaire",
     "holds": "the state's equity in the producing blocks, the marketing of the state's crude, "
              "and -- since the ANPG was separated out -- no longer the concessionaire role",
     "forced_to": ("produce from mature deepwater fields with steep natural decline, which is "
                   "the physical fact behind the whole OPEC quota argument",
                   "fund its own capital programme from a revenue stream the treasury also needs",
                   "sell cargoes on a published loading programme that the market reads"),
     "when": "monthly loading programmes; quarterly and annual reporting that is irregular",
     "information": ("the true decline rate field by field",
                     "the loading programme before it circulates",
                     "the state of the deferred capital programme"),
     "constraints": ("natural decline that requires continuous investment merely to hold flat",
                     "an oil-backed debt stack that pre-commits cargoes",
                     "a partner group that decides capital allocation globally"),
     "instruments": ("XBRUSD", "XTIUSD"),
     "counterparties": ("the international operators in the blocks",
                        "the crude buyers, overwhelmingly Chinese",
                        "the ANPG as concessionaire", "the lenders holding oil-backed facilities"),
     "observables": ("monthly loading programmes by grade",
                     "OPEC and IEA production estimates",
                     "the ANPG's licensing-round awards and farm-out approvals",
                     "the export destinations in the trade data"),
     "impact": "ANGOLAN PRODUCTION HAS BEEN DECLINING FOR A DECADE, which is why the quota bound: "
               "the country could not produce its allocation and a quota below capacity is not a "
               "constraint at all. That is the natural experiment SA-M is built on",
     "persistence": "years; a decline curve does not mean-revert",
     "falsifier": "Angolan production shows a discernible step at the 2024-01-01 exit rather "
                  "than continuing its pre-existing trend -- which would mean the quota HAD been "
                  "binding after all and would falsify the pack's reading of the exit",
     "notes": "THE FALSIFIER IS THE INTERESTING HALF. The pack's claim is that the quota did NOT "
              "bind and the exit was about the BASELINE the quota was struck from, and a "
              "measurable production step would kill that reading outright"},
    {"name": "The Banco Nacional de Angola's FX auction desk",
     "holds": "the dollars the oil sector generates and the allocation of them to the banks, "
              "through auctions whose results it publishes",
     "forced_to": ("allocate a supply that moves with the barrel to a demand that does not",
                   "publish the auction result, which makes the rationing visible as a quantity",
                   "choose between defending the kwanza and holding reserves, and it chose "
                   "reserves in 2023"),
     "when": "weekly to fortnightly auctions with published allocations",
     "information": ("the forward pipeline of oil receipts",
                     "the unmet bid at each auction",
                     "the intervention rule it does not publish"),
     "constraints": ("an FX supply that is essentially one commodity",
                     "an import bill dominated by food and refined fuel",
                     "a fuel-subsidy reform that raises the domestic price when it is executed"),
     "instruments": ("XBRUSD", "XTIUSD", "USDZAR"),
     "counterparties": ("the commercial banks bidding at auction",
                        "the importers behind them", "the treasury and Sonangol as FX suppliers",
                        "the informal market that clears the residual"),
     "observables": ("the auction date, allocated amount and reference rate",
                     "gross reserves", "the informal premium reported in Expansão and Mercado",
                     "the crude price and the loading programme feeding the supply"),
     "impact": "THE CLEANEST OIL-TO-FX TRANSMISSION IN THE DESK'S ROSTER because it is a "
               "PUBLISHED QUANTITY: the barrel moves the receipts, the receipts move the "
               "allocation, the allocation moves the premium, and three of those four are public",
     "persistence": "weeks to quarters; the premium responds within weeks of an allocation change",
     "falsifier": "auction allocation shows no relationship to the crude price at any lag out to "
                  "two quarters, and the informal premium shows no relationship to the allocation "
                  "-- in which case the chain is broken somewhere this pack has not looked",
     "notes": "THE SERIES IS PUBLISHED IN PORTUGUESE and an English-only collector never sees it; "
              "this is the single clearest cost of an English-only crawl in the whole pack"},
    {"name": "The Angolan Ministry of Finance and the oil-backed debt stack",
     "holds": "a budget built on an oil price assumption, a debt stack with oil-collateralised "
              "facilities in it, and a fuel subsidy it has been reforming",
     "forced_to": ("revise the budget in-year when the oil assumption breaks, which is a dated, "
                   "published event",
                   "service oil-backed facilities in cargoes rather than in cash, which "
                   "pre-commits production",
                   "reform a fuel subsidy that is politically costly and fiscally unavoidable"),
     "when": "the Orçamento Geral do Estado in December with in-year revisions; debt service on "
             "the facilities' own schedules",
     "information": ("how many cargoes are pre-committed",
                     "the true fiscal breakeven oil price",
                     "the subsidy reform timetable before it is announced"),
     "constraints": ("a debt stack whose largest creditor relationship is bilateral",
                     "an economy in which non-oil revenue is small",
                     "a currency whose depreciation raises the local-currency debt burden"),
     "instruments": ("XBRUSD", "USDZAR"),
     "counterparties": ("the bilateral and commercial creditors",
                        "Sonangol, whose cargoes service the facilities",
                        "the IMF, which has programmed Angola before",
                        "the domestic bond market at BODIVA"),
     "observables": ("the budget's oil price assumption and its in-year revisions",
                     "debt service published in the Ministry's tables",
                     "fuel price adjustments and their dates",
                     "the kwanza's level against the budget assumption"),
     "impact": "a country whose fiscal breakeven is above the market price is a FORCED SELLER of "
               "future production and a forced devaluer of its currency; both consequences are "
               "dated and both reach the executable surface through crude and the risk carrier",
     "persistence": "one to three fiscal years",
     "falsifier": "budget revisions and fuel-price adjustments cluster no more tightly around "
                  "crude-price moves than around arbitrary dates -- in which case the fiscal "
                  "channel is not responding to the barrel and the pack's causal ordering is wrong",
     "notes": "THE 2023 DEPRECIATION IS THE WORKED EXAMPLE: the state stopped subsidising the "
              "rate out of oil receipts and the currency moved by roughly half, which is a "
              "FISCAL decision showing up as a monetary event"},
    {"name": "The Lobito Atlantic Railway concession",
     "holds": "a thirty-year concession over the rail line from Lobito to the Congolese border "
              "and the capacity ramp published with it",
     "forced_to": ("invest against a published capacity target, which makes the ramp datable",
                   "compete with Durban, Dar es Salaam, Beira and Nacala for the same Copperbelt "
                   "tonnes",
                   "operate a line whose Congolese half it does not control"),
     "when": "the concession award and the first copper trains in 2024; capacity milestones "
             "announced irregularly",
     "information": ("the real tonnage railed before it is announced",
                     "the state of the rolling stock and the Congolese connection",
                     "the offtake commitments from the Copperbelt shippers"),
     "constraints": ("a single line with a border in the middle of it",
                     "port capacity at Lobito",
                     "shippers' incumbent relationships with the eastern corridors"),
     "instruments": ("XCUUSD", "XZNUSD"),
     "counterparties": ("the Copperbelt copper and cobalt producers",
                        "the Angolan state as grantor",
                        "the Congolese and Zambian rail authorities",
                        "the trading houses in the concession consortium"),
     "observables": ("announced and reported tonnage railed",
                     "the concession's published capacity targets",
                     "the competing corridors' throughput over the same months",
                     "Copperbelt production from the `copperbelt` pack's own ground"),
     "impact": "a NEW corridor does not change world copper supply, it changes the COST AND TIME "
               "of getting it out -- which is a basis and inventory effect rather than a supply "
               "one, and the pack tests it as such",
     "persistence": "years, as a ramp; the routing shift itself does not reverse",
     "falsifier": "Lobito tonnage rises with no offsetting fall at the eastern corridors and no "
                  "change in Copperbelt production -- which would mean the tonnage is new supply "
                  "rather than re-routed supply, and the pack's framing is wrong",
     "notes": "A SHORT SERIES IS UNMEASURED BEFORE IT IS A SIGNAL. The first trains ran in 2024 "
              "and no cell here is promoted on a series this young"},
    # ---------------------------------------------------------------- Namibia
    {"name": "The Bank of Namibia inside the Common Monetary Area",
     "holds": "a currency pegged one-to-one to the rand, rand reserves against the issue, and a "
              "policy rate it can move only within the space the peg leaves",
     "forced_to": ("hold rand reserves sufficient to back the Namibia dollar issue at par",
                   "follow the South African Reserve Bank's rate closely, because an open "
                   "capital account and a fixed parity leave no room",
                   "accept South African monetary conditions as its own"),
     "when": "scheduled MPC meetings, usually shortly after the SARB's; quarterly bulletins",
     "information": ("the reserve position before it is published",
                     "the capital-flow pressure at the peg before it appears anywhere"),
     "constraints": ("the peg itself, which is the binding constraint and the point",
                     "reserves that must cover the issue",
                     "a SACU transfer that is the largest budget item and is not its decision"),
     "instruments": ("USDZAR", "ZARJPY", "EURZAR"),
     "counterparties": ("the South African Reserve Bank",
                        "the domestic banks, which are largely South African subsidiaries",
                        "the SACU Secretariat", "the Namibian treasury"),
     "observables": ("the repo rate and its spread to the SARB's",
                     "gross reserves and import cover",
                     "the SACU receipts line in the Quarterly Bulletin",
                     "the NSX local index against the overall index"),
     "impact": "NAMIBIA IS THE DESK'S ONLY LAWFUL THIRD-PARTY READ ON THE RAND. Anything that "
               "moves in Namibia and not in South Africa is Namibian; anything that moves in both "
               "is the rand. That identification is worth more than a currency the desk could "
               "trade, because the desk can already trade the rand",
     "persistence": "the peg has held since 1993 and is structural; the repo spread is a "
                    "quarters-scale state",
     "falsifier": "the Namibian repo rate diverges persistently from the SARB's without a "
                  "reserve consequence, or the NSX local index tracks the overall index "
                  "one-for-one -- either would mean the peg's constraint is not binding the way "
                  "this pack models it",
     "notes": "THE 1:1 PEG IS WHY USDZAR IS LABELLED **EXACT** AND NOT PROXY IN "
              "TRANSMISSION_TARGETS: a Namibian FX exposure IS a rand exposure, with no basis"},
    {"name": "The Orange Basin operators and the Venus and Graff appraisal clock",
     "holds": "the two 2022 discoveries that made Namibia the newest oil province on earth, and "
              "an appraisal-and-FID timetable published well before any barrel exists",
     "forced_to": ("appraise before sanctioning, which is a multi-year sequence of dated wells "
                   "and flow tests",
                   "publish or disclose results because the operators are listed majors with "
                   "reporting obligations",
                   "decide on development in a world where long-cycle deepwater competes with "
                   "short-cycle shale for the same capital"),
     "when": "well-by-well through the appraisal campaign; FID is projected and is treated as a "
             "projection",
     "information": ("flow-test results before disclosure",
                     "the reservoir's true connectivity and gas-to-oil ratio",
                     "the internal development cost estimate"),
     "constraints": ("no existing infrastructure of any kind in the basin",
                     "a high gas-to-oil ratio in some discoveries, which is a development problem",
                     "partners who allocate capital globally and have written some of it down"),
     "instruments": ("XBRUSD", "XTIUSD"),
     "counterparties": ("the partner majors and the national oil company NAMCOR",
                        "the Ministry of Mines and Energy as licensor",
                        "the service contractors and rig owners",
                        "the future offtakers"),
     "observables": ("spud and result announcements well by well",
                     "the published licence register and its farm-ins",
                     "impairments and write-downs, which are dated negative milestones",
                     "the rig contracting in the basin"),
     "impact": "a NEW PROVINCE is a long-dated supply expectation, so the tradable content is the "
               "revision to that expectation on each dated well result -- and the negative "
               "milestones, like the 2025 write-down, are cleaner events than the positive ones "
               "because they are unambiguous",
     "persistence": "quarters per result; years for the province",
     "falsifier": "no measurable move in the crude complex or the deepwater service tape around "
                  "any dated Orange Basin result -- in which case the province is too far from "
                  "production to be priced and SA-O is a fiscal and FX story only",
     "notes": "THE OPERATORS ARE LISTED MAJORS AND NONE IS AN INSTRUMENT HERE. The basin is "
              "tested on crude, and the two-lane order is why the obvious equity expression is "
              "refused"},
    {"name": "The Namibian uranium mines and their long-term offtake",
     "holds": "a top-five share of world uranium production from Rössing, Husab and Langer "
              "Heinrich, sold overwhelmingly under multi-year utility contracts",
     "forced_to": ("sell under contract rather than into spot, so a spot move reaches Namibian "
                   "revenue slowly and partially",
                   "run on grid power in a country that imports much of its electricity",
                   "restart and idle with the price cycle, which is a dated, published decision"),
     "when": "quarterly production reporting by the parents; restart and curtailment decisions "
             "are event-driven",
     "information": ("the contract book's realised price, which is not the spot price",
                     "the true cost curve at each operation",
                     "the restart decision before it is announced"),
     "constraints": ("grid power and water in the Namib",
                     "a spot market thin enough that financial buyers set it",
                     "contract terms fixed years ago"),
     "instruments": ("USDZAR", "XNGUSD"),
     "counterparties": ("the utility offtakers", "the Chinese state owners of two of the mines",
                        "NamPower as the electricity supplier",
                        "the Namibian treasury as taxing authority"),
     "observables": ("quarterly production tonnage",
                     "restart and curtailment announcements",
                     "the NSA's uranium export value and volume line",
                     "NamPower's import and generation position"),
     "impact": "uranium reaches this pack's executable surface through the NAMIBIAN FISCAL AND FX "
               "channel rather than through a uranium price, because there is no uranium "
               "instrument here -- and the pack routes it that way explicitly rather than "
               "substituting a related metal",
     "persistence": "quarters to years; contract books turn over slowly by design",
     "falsifier": "Namibian uranium export values show no relationship to the spot assessment at "
                  "any lag out to two years -- which would be evidence that the contract book "
                  "fully insulates the revenue, and would close the channel entirely",
     "notes": "THE PRICE ASSESSMENTS ARE REGISTERED machine_use_allowed=false AND NEVER SCRAPED; "
              "the export value line from the statistics agency is the lawful substitute and is "
              "named as such"},
    {"name": "Namport and the Walvis Bay corridor",
     "holds": "a deepwater port on the Atlantic with corridor road links to Botswana, Zambia and "
              "the Copperbelt, and spare capacity it has spent a decade trying to fill",
     "forced_to": ("compete for landlocked cargo with Durban, Beira, Dar es Salaam and now "
                   "Lobito, on distance and reliability",
                   "justify an expansion built ahead of the demand",
                   "handle the uranium and salt exports that are its base load"),
     "when": "monthly to annual throughput reporting; corridor volumes are announced irregularly",
     "information": ("the forward booking position from the corridor shippers",
                     "the real utilisation of the expanded container terminal"),
     "constraints": ("road rather than rail for most of the corridor, which caps tonnage",
                     "distance to the Copperbelt compared with the eastern routes",
                     "a small domestic cargo base"),
     "instruments": ("XCUUSD", "XZNUSD", "USDZAR"),
     "counterparties": ("the Copperbelt and Botswana shippers",
                        "the uranium mines exporting through it",
                        "the shipping lines", "the Namibian state as owner"),
     "observables": ("container and bulk throughput",
                     "corridor tonnage by destination country",
                     "the competing corridors' volumes over the same months"),
     "impact": "the ATLANTIC alternative to the eastern corridors: it makes the routing question "
               "in this pack genuinely multi-way, which is what allows a routing event to be "
               "distinguished from a supply event at all",
     "persistence": "months to years; a routing relationship once established is sticky",
     "falsifier": "Walvis Bay corridor volumes show no relationship to disruption at Beira, "
                  "Durban or Dar es Salaam in any episode -- in which case the corridors are not "
                  "substitutes at the margin and the routing control this pack leans on is void",
     "notes": "THE ROUTING CONTROL IS ONLY AS GOOD AS THE ALTERNATIVES ARE REAL, and this actor "
              "is what makes the alternative real on the Atlantic side"},
    # ---------------------------------------------------------------- regional
    {"name": "The SACU Secretariat and the revenue-sharing formula",
     "holds": "a common external tariff, a common customs and excise pool, and a published "
              "formula that divides it among five members with a two-year lag and a "
              "retrospective adjustment",
     "forced_to": ("distribute the pool by a formula rather than by negotiation each year",
                   "adjust retrospectively when the pool outturn differs from the forecast, "
                   "which hands members a windfall or a clawback years later",
                   "publish the pool and the shares"),
     "when": "annual determination with quarterly payments; the adjustment arrives two years "
             "after the year it corrects",
     "information": ("the pool forecast before it is published",
                     "the size of the coming adjustment before members budget for it"),
     "constraints": ("a pool that depends overwhelmingly on South African imports",
                     "a formula that no member can change alone",
                     "members for whom the transfer is the largest single revenue line"),
     "instruments": ("USDZAR",),
     "counterparties": ("South Africa as the pool's largest contributor",
                        "Botswana, Namibia, Lesotho and Eswatini as net recipients",
                        "the five treasuries that budget against it"),
     "observables": ("the published pool size and member shares",
                     "the SACU receipts line in the Botswana and Namibian budgets",
                     "the stabilisation adjustment when it lands",
                     "South African import volumes, which drive the pool"),
     "impact": "SOUTH AFRICAN IMPORT DEMAND IS TRANSMITTED, BY FORMULA AND WITH A TWO-YEAR LAG, "
               "INTO TWO OTHER COUNTRIES' BUDGETS. That is a published, mechanical, dated fiscal "
               "transfer and it is the most under-modelled thing in Southern African macro",
     "persistence": "two to four years, by construction: the lag IS the mechanism",
     "falsifier": "the SACU receipts line shows no relationship to South African import volumes "
                  "at the formula's own lag -- which would mean the formula is not being applied "
                  "as published and would void SA-H entirely",
     "notes": "BOTSWANA AND NAMIBIA ARE IN SACU; ZIMBABWE, MOZAMBIQUE AND ANGOLA ARE NOT. And "
              "SACU is not the CMA: Botswana left the rand area in 1976 and is in the customs "
              "union only. Getting that wrong invents a peg that does not exist"},
    {"name": "The Zambezi River Authority and the Kariba water allocation",
     "holds": "the shared reservoir behind the Zimbabwean and Zambian power stations, the weekly "
              "published lake level, and the allocation decision between the two countries",
     "forced_to": ("publish the lake level and usable storage weekly",
                   "cut the allocation when inflows fail, which it has had to do",
                   "split a shortage between two sovereigns who both want the power"),
     "when": "weekly bulletins; allocation decisions are annual with in-year revisions",
     "information": ("the inflow forecast before it is published",
                     "the allocation revision before it is announced"),
     "constraints": ("hydrology, which is the whole constraint and is not negotiable",
                     "two governments with competing demands on one reservoir",
                     "a minimum operating level below which generation stops entirely"),
     "instruments": ("XPTUSD", "XCUUSD", "XALUSD"),
     "counterparties": ("the Zimbabwe Power Company and ZESCO in Zambia",
                        "the Zimbabwean smelters and the Zambian copper smelters downstream",
                        "the Southern African Power Pool"),
     "observables": ("the weekly lake level in metres above sea level and usable storage",
                     "the allocation in billion cubic metres to each country",
                     "load-shedding schedules in both countries",
                     "smelter curtailment announcements"),
     "impact": "ONE HYDROLOGICAL STATE CONSTRAINS THREE METALS AT ONCE: Zimbabwean PGM smelting, "
               "Zambian copper smelting and -- through the same Zambezi system at Cahora Bassa -- "
               "Mozambican aluminium. A weekly published number that binds a metals supply chain "
               "is rare enough to be a domain of its own",
     "persistence": "seasonal and persistent: a drawn-down reservoir takes a full wet season to "
                    "recover and the constraint lasts as long as the level does",
     "falsifier": "low lake levels produce no measurable curtailment in the region's smelters "
                  "against matched seasons -- in which case the smelters are insulated by "
                  "imported power or by their own generation and the channel is closed",
     "notes": "THE SHARED LEG WITH `copperbelt`: Zambia sits on the other side of the same "
              "reservoir, and neither pack can measure the smelting constraint alone"},
)

#: Which jurisdiction each actor belongs to, by POSITION in ACTORS. Five Zimbabwean, four each
#: for Botswana, Mozambique, Angola and Namibia, and two regional -- the floor the brief sets is
#: three actors per jurisdiction, and a pack that met it exactly would be one country wearing
#: five hats.
ACTOR_JURISDICTION: tuple[str, ...] = (
    "zw", "zw", "zw", "zw", "zw",
    "bw", "bw", "bw", "bw",
    "mz", "mz", "mz", "mz",
    "ao", "ao", "ao", "ao",
    "na", "na", "na", "na",
    "regional", "regional",
)
# --------------------------------------------------------------------------- domains
#: EIGHTEEN DOMAINS: five for Zimbabwe, three for Botswana, four for Mozambique, two for Angola,
#: two for Namibia, one shared between Botswana and Namibia, and two regional. Each jurisdiction
#: owes at least two of its OWN, and a domain with fewer than two negative controls is refused by
#: the validator because an effect with no control cannot be told from the desk's own selection.
DOMAINS: tuple[dict[str, Any], ...] = (
    {"id": "SA-A", "title": "ZIMBABWE: the Great Dyke and the PGM beneficiation clock",
     "objects": ("the gazetted and deferred export controls on unbeneficiated platinum-group "
                 "concentrate, with their statutory instrument numbers",
                 "Zimbabwean PGM export volumes in the Ministry's tables and in the partner "
                 "countries' mirror imports",
                 "announced smelter and refinery capital commitments and their slippage",
                 "the palladium-to-platinum ratio of Great Dyke ore against South African ore"),
     "conditions": ("whether a concentrate export control is GAZETTED, DEFERRED or merely "
                    "announced on the date in question",
                    "the Kariba lake level bucket, because Dyke smelting needs firm power",
                    "the PGM basket price relative to the marginal cost of Zimbabwean supply"),
     "instruments": ("XPTUSD", "XPDUSD", "XAUUSD"),
     "controls": ("South African PGM supply over the same months, which dwarfs Zimbabwe's and "
                  "would produce the same sign with nothing Zimbabwean happening",
                  "Russian palladium supply, the other half of world production and the "
                  "separating control for a platinum-versus-palladium claim",
                  "the matched-weekday control around each gazette date, because a Friday gazette "
                  "is a Friday like any other until it is shown not to be"),
     "notes": "AN EXPORT CONTROL ON CONCENTRATE DELAYS AND RELOCATES SUPPLY RATHER THAN DESTROYING "
              "IT, so the claim tested here is a TIMING claim; a level claim on a producer this "
              "size against South African supply would be swamped and the pack says so"},
    {"id": "SA-B", "title": "ZIMBABWE: resource nationalism as a dated, gazetted treatment",
     "objects": ("the December 2022 statutory instrument banning unbeneficiated lithium ore "
                 "exports, with its gazette number and commencement date",
                 "the sequence of announcement, gazette, deferral and amendment for each control",
                 "the gap between ministerial announcement and gazette, which is often months",
                 "the equivalent controls elsewhere: Indonesian nickel ore, Chilean and Mexican "
                 "lithium policy, Namibian and Zambian export rules"),
     "conditions": ("announcement-only versus GAZETTED versus commenced, which are three "
                    "different states and are routinely conflated",
                    "whether the same budget round changed other royalty or levy clauses, which "
                    "is the confound",
                    "whether the control was subsequently deferred, which resets the clock"),
     "instruments": ("XPTUSD", "XPDUSD", "XCUUSD", "USDZAR"),
     "controls": ("the other clauses commenced by the same instrument or budget, which separates "
                  "'this control' from 'a policy day'",
                  "Indonesian and Chilean resource-nationalism events over the same quarters, "
                  "which are the same class of event with no Zimbabwean content",
                  "matched non-event Fridays, because the gazette is published on Fridays and a "
                  "Friday effect would otherwise be attributed to the policy"),
     "notes": "LITHIUM IS NOT A BROKER SYMBOL AND THE PACK REFUSES TO SUBSTITUTE ONE. What is "
              "testable is the POLICY CLASS on the metals the same ministry also regulates, and "
              "the row says which claim is being made"},
    {"id": "SA-C", "title": "ZIMBABWE: six currency regimes and the parallel premium",
     "objects": ("the six dated currency eras since 2008 and the instrument that created each",
                 "the official willing-buyer-willing-seller rate and the tracked street rate",
                 "the premium between them as a continuous state variable",
                 "the ZiG's published gold and foreign-exchange reserve cover",
                 "ZIMSTAT's own documentation of its inflation-series breaks"),
     "conditions": ("the currency ERA, which partitions every Zimbabwean series and is never "
                    "pooled across",
                    "the premium bucket within an era (below 20%, 20-100%, above 100%)",
                    "whether a statutory instrument touching the currency was gazetted in the "
                    "same month"),
     "instruments": ("XAUUSD", "USDZAR", "XPTUSD"),
     "controls": ("Angola over the same months, which also manages its rate but with an oil "
                  "funding source and no dollarisation history",
                  "the Namibian peg as the zero-discretion control: a currency that CANNOT move "
                  "is the right null for a currency that moves by decree",
                  "matched windows in the 2019 RTGS transition, where the regime changed without "
                  "a gold backing claim attached"),
     "notes": "ZWG IS ABSENT FROM THE BROKER AND THE PACK NEVER PRETENDS OTHERWISE: every regime "
              "boundary is tested on the metal the currency claims to be backed by and on the "
              "frontier-risk carrier, never on a currency nobody can quote"},
    {"id": "SA-D", "title": "ZIMBABWE: the gold delivery plane and the gold-backed instruments",
     "objects": ("monthly gold deliveries to Fidelity Gold Refinery, split primary and "
                 "small-scale",
                 "the payment-term changes that switch declared deliveries on and off",
                 "the Mosi-oa-Tunya gold coins and the gold-backed digital tokens as dated "
                 "official demand",
                 "the mirror gap between declared Zimbabwean gold exports and partner-reported "
                 "imports"),
     "conditions": ("the payment split between hard and local currency at the time",
                    "the currency era, because the local-currency component's value depends on it",
                    "whether a coin or token issuance window was open"),
     "instruments": ("XAUUSD", "USDZAR"),
     "controls": ("Ghana's and Tanzania's own central-bank gold purchase programmes over the "
                  "same years, which decide whether this is about Zimbabwe or about African "
                  "central banks buying gold as a class",
                  "the gold price itself and the small-scale production trend, which would move "
                  "deliveries with no policy change at all",
                  "South African and Mozambican declared gold imports, the mirror half"),
     "notes": "THE SAME MECHANISM `east_africa` FOUND IN UGANDA POINTED THE OTHER WAY -- there an "
              "export levy switched a declared flow OFF, here a payment term switches one ON -- "
              "and each is the other's natural placebo"},
    {"id": "SA-E", "title": "ZIMBABWE: dollarisation as an observable, ZSE against VFEX",
     "objects": ("the ZSE index in local currency against the VFEX index in dollars",
                 "listing migrations from the ZSE to the VFEX, with their dates",
                 "the June 2020 ZSE suspension that ended the Old Mutual implied-rate series",
                 "mobile-money transaction values through each currency change"),
     "conditions": ("the premium bucket, which is the state this spread should respond to",
                    "whether a statutory instrument restricting fungibility or trading was in "
                    "force",
                    "the currency era"),
     "instruments": ("XAUUSD", "USDZAR", "US500"),
     "controls": ("the rand and the broad frontier equity tape, which would move a "
                  "dollar-denominated Zimbabwean board with nothing Zimbabwean happening",
                  "matched windows before the VFEX existed, when the same question had only one "
                  "observable",
                  "the gold price, because the ZSE has historically been a gold-miner-weighted "
                  "index and its local-currency level is partly a metals bet"),
     "notes": "NO LISTING ON EITHER BOARD IS AN INSTRUMENT HERE (two-lane order, 2026-09-06). "
              "The SPREAD and the MIGRATION are the observables; the executable leg is gold and "
              "the risk carrier"},
    {"id": "SA-F", "title": "BOTSWANA: the ten diamond sales cycles as a luxury-demand read",
     "objects": ("the De Beers sales cycle revenue series, ten dated prints a year",
                 "Statistics Botswana's diamond export value and carats, giving a realised price "
                 "per carat",
                 "Debswana production cuts and their announcement dates",
                 "the Kimberley Process annual production and average-price-per-carat table"),
     "conditions": ("the cycle's revenue surprise against its own trailing seasonal norm",
                    "the position in the calendar year, because the cycles are not evenly spaced "
                    "and the holiday-season cycles carry more information",
                    "whether a production cut had been announced in the preceding quarter"),
     "instruments": ("US500", "UK100", "USDZAR"),
     "controls": ("the lab-grown diamond share, which has been taking the low end of the natural "
                  "market and would produce the same revenue fall with no demand change at all",
                  "the broad index, so the claim is about the LUXURY component and not the market",
                  "matched non-release days around each cycle close, because a cycle close is an "
                  "ordinary weekday until it is shown not to be"),
     "notes": "THE HIGHEST-FREQUENCY PUBLISHED LUXURY-DEMAND SERIES IN EXISTENCE and essentially "
              "untested by systematic desks. Rough diamonds are not a broker symbol and the pack "
              "routes them with the lab-grown confound named on the face of the row"},
    {"id": "SA-G", "title": "BOTSWANA: the published currency basket and its measurable rand beta",
     "objects": ("the announced SDR and rand weights of the pula basket",
                 "the rate of crawl announced each year in the Monetary Policy Statement",
                 "the daily pula fixing and the residual to a mechanical replication of the "
                 "published basket",
                 "gross reserves and the Pula Fund's reported value"),
     "conditions": ("the sign and size of the residual to the published replication, which is "
                    "the discretionary intervention state",
                    "whether the year's crawl rate had just been announced or reweighted",
                    "the diamond revenue state, which is what puts the peg under pressure"),
     "instruments": ("USDZAR", "EURZAR", "GBPZAR", "ZARJPY"),
     "controls": ("a mechanical 60/40 SDR-and-rand replication as the null: if the published "
                  "rule explains the fixing there is no discretion to trade",
                  "the Namibian 1:1 peg as the zero-discretion control at the other extreme",
                  "the rand's own idiosyncratic moves, which pass into the pula by construction "
                  "and carry no Botswana information at all"),
     "notes": "THE AUTHORITY PUBLISHED THE ANSWER KEY, which is why this is the cleanest FX "
              "mechanism in the pack: the measurement is the RESIDUAL to a known rule, not a "
              "fitted beta, and a fitted beta here would be re-deriving something already public"},
    {"id": "SA-H", "title": "BOTSWANA AND NAMIBIA: the SACU transfer as a mechanical fiscal shock",
     "objects": ("the SACU common revenue pool and each member's published share",
                 "the SACU receipts line in the Botswana and Namibian budget documents",
                 "the stabilisation adjustment, which arrives two years after the year it "
                 "corrects",
                 "South African import volumes, which drive the pool"),
     "conditions": ("whether the year's transfer is an up-cycle or a clawback, which is known "
                    "two years ahead by construction",
                    "the size of the transfer relative to total revenue, which differs sharply "
                    "between the two members",
                    "whether a diamond or uranium revenue shock is landing in the same year"),
     "instruments": ("USDZAR", "US500"),
     "controls": ("South African import volumes as the pool's own driver, which separates 'the "
                  "formula paid out' from 'South Africa imported more'",
                  "Lesotho's and Eswatini's shares, which face the same formula with no diamonds "
                  "and no uranium behind them",
                  "the two members' own non-SACU revenue, which is the counterfactual budget"),
     "notes": "A PUBLISHED, MECHANICAL, TWO-YEAR-LAGGED FISCAL TRANSFER out of South African "
              "import demand into two other sovereigns' budgets. The LAG is the mechanism and it "
              "is the most under-modelled feature in Southern African macro"},
    {"id": "SA-I", "title": "MOZAMBIQUE: the LNG timetable as a dated global supply schedule",
     "objects": ("Coral South's milestone sequence through to first cargo in November 2022",
                 "the Area 1 force majeure of April 2021 and its 2025 lifting",
                 "Rovuma's undecided FID and the published capacity of each tranche",
                 "the INP's and operators' own dated statements"),
     "conditions": ("the milestone STATUS: gazetted, announced or projected, which are three "
                    "different things and only the first two may carry a cell",
                    "whether a US Gulf Coast or Qatari tranche landed in the same quarter",
                    "the European gas price regime, which dominated 2021-2022 and is the "
                    "confound"),
     "instruments": ("XNGUSD", "XBRUSD"),
     "controls": ("US liquefaction start-ups and Qatari North Field tranches over the same "
                  "quarters, each of which dwarfs Mozambique and would produce the same sign",
                  "the Mozambican fiscal and trade series, where a tranche of this size IS large "
                  "-- the pack tests the fiscal leg first because it is the one that can be seen",
                  "matched non-milestone quarters"),
     "notes": "XNGUSD IS HENRY HUB AND IS NOT THE PRICE MOZAMBICAN CARGOES REALISE. The pack "
              "states the basis rather than pretending otherwise, and expects this edge to be "
              "hard to establish on price and easy on the fiscal leg"},
    {"id": "SA-J", "title": "MOZAMBIQUE: Mozal, Cahora Bassa and aluminium on hydropower",
     "objects": ("Cahora Bassa generation, availability and export to South Africa",
                 "reported Mozal power interruptions, curtailments and restarts",
                 "Mozambican aluminium export volumes in the trade statistics",
                 "the Zambezi system's inflows, which are the same hydrology as Kariba's"),
     "conditions": ("the Zambezi system's hydrological state, shared with SA-Q",
                    "whether a power arrangement renegotiation was live",
                    "the LME aluminium price relative to the smelter's cost"),
     "instruments": ("XALUSD", "XCUUSD"),
     "controls": ("global primary aluminium supply, against which one smelter is small -- the "
                  "pack tests the Mozambican export series first and the price second",
                  "Chinese and Gulf smelter curtailments over the same months, which are the "
                  "same class of event at a size that does move the price",
                  "matched non-interruption weeks with the same hydrological state"),
     "notes": "ONE RESERVOIR SYSTEM CONSTRAINS ALUMINIUM IN MOZAMBIQUE, PLATINUM IN ZIMBABWE AND "
              "COPPER IN ZAMBIA, which is why SA-Q exists as a domain and this one shares its "
              "conditioning variable"},
    {"id": "SA-K", "title": "MOZAMBIQUE: Beira and Nacala as two of five corridors for one orebody",
     "objects": ("Beira and Nacala throughput and the transit split by destination country",
                 "cyclone landfalls and line closures in the corridor",
                 "the competing corridors' throughput: Durban, Dar es Salaam, Walvis Bay, Lobito",
                 "dwell times and berth availability at both ports"),
     "conditions": ("whether a disruption episode is under way at this corridor or at a "
                    "competing one",
                    "the cyclone season versus the dry season",
                    "the Copperbelt production state, which is `copperbelt`'s own series"),
     "instruments": ("XCUUSD", "XZNUSD", "SUGAR", "COTTON"),
     "controls": ("the competing corridors' volumes over the same months: a fall here that "
                  "appears as a rise there is a ROUTING event and carries NO supply information",
                  "Copperbelt production itself, which separates 'less metal was produced' from "
                  "'the metal used another route'",
                  "Chinese import demand over the same months, the demand-side confound"),
     "notes": "NEITHER THIS PACK NOR `copperbelt` CAN ESTABLISH THE ROUTING CONTROL ALONE, which "
              "is what makes it the strongest interaction in this file after `za`"},
    {"id": "SA-L", "title": "MOZAMBIQUE: the hidden debt, the default and the court record",
     "objects": ("the April 2016 disclosure of the undisclosed state-guaranteed borrowings",
                 "the missed payment and the 2019 restructuring, each with its date",
                 "the London court proceedings and settlements, which are a published record",
                 "the IMF programme suspension and its later resumption"),
     "conditions": ("whether the date sits inside the disclosure-to-restructuring window",
                    "whether an IMF review or a court milestone landed in the same quarter",
                    "the LNG timetable state, because the country's credit story and its gas "
                    "story are the same story after 2019"),
     "instruments": ("USDZAR", "US500"),
     "controls": ("the other African defaults of the cycle -- Zambia, Ghana, Ethiopia -- which "
                  "decide whether this is about Mozambique or about frontier default as a class",
                  "the broad emerging-market risk tape, so the claim is Mozambican and not global",
                  "matched non-milestone quarters inside the same era"),
     "notes": "A DATED SOVEREIGN EVENT WITH A PUBLISHED COURT RECORD is a rare thing: most "
              "sovereign credit events leave only market prices behind, and this one left "
              "testimony, judgments and settlement dates"},
    {"id": "SA-M", "title": "ANGOLA: the OPEC exit as a natural experiment on what a quota binds",
     "objects": ("the 2023-12-21 announcement and the 2024-01-01 effective date",
                 "Angolan production in the OPEC secondary-source table either side of it",
                 "the monthly export loading programmes across the boundary",
                 "the quota baseline dispute that preceded the exit"),
     "conditions": ("member versus non-member era, which is a clean dated partition",
                    "whether Angolan production was above or below its assigned quota in the "
                    "month, which is the whole question",
                    "whether an OPEC+ group decision landed in the same month",
                    "the natural-decline trend, which must be removed before any step is claimed"),
     "instruments": ("XBRUSD", "XTIUSD"),
     "controls": ("Nigeria and Congo-Brazzaville, which had the same baseline dispute and did "
                  "NOT leave -- the closest matched controls the world offers",
                  "Angola's own pre-exit decline trend, because a step must be shown against the "
                  "trend and not against a flat line",
                  "the OPEC+ group's own production over the same months"),
     "notes": "THE PACK'S READING IS THAT THE QUOTA DID NOT BIND and the exit was about the "
              "BASELINE it was struck from. A measurable production step at the boundary would "
              "falsify that reading outright, which is what makes this domain worth the trials"},
    {"id": "SA-N", "title": "ANGOLA: oil into FX, through a published auction allocation",
     "objects": ("the BNA's weekly to fortnightly auction dates, allocations and reference rates",
                 "gross reserves and their trajectory",
                 "the informal premium as reported in the Portuguese business press",
                 "the budget's oil price assumption and its in-year revisions",
                 "fuel subsidy reform steps and their dates"),
     "conditions": ("the crude price regime relative to the budget's own assumption",
                    "whether the auction allocation rose or fell against its trailing norm",
                    "whether a subsidy reform step had been taken in the preceding quarter"),
     "instruments": ("XBRUSD", "XTIUSD", "USDZAR"),
     "controls": ("Nigeria's own rate unification and FX reform over the same window, an oil "
                  "exporter running the same experiment with different institutions",
                  "the Angolan decline trend, which changes the receipts with no policy change",
                  "matched non-auction weeks"),
     "notes": "THE CHAIN IS BARREL -> RECEIPTS -> ALLOCATION -> PREMIUM and three of the four "
               "links are PUBLISHED, which makes this the most completely observable "
               "transmission in the pack. It is published in Portuguese and invisible to an "
               "English-only crawl"},
    {"id": "SA-O", "title": "NAMIBIA: the Orange Basin appraisal clock and the newest oil province",
     "objects": ("the 2022 Venus and Graff discovery announcements",
                 "each appraisal well's spud and result, with its date",
                 "the 2025 write-down as a dated NEGATIVE milestone",
                 "the published licence register, farm-ins and the projected FID timetable"),
     "conditions": ("the milestone type: discovery, appraisal result, write-down or FID, which "
                    "carry different information",
                    "whether the result was disclosed as a flow test or only as a presence",
                    "the crude price regime, which decides whether long-cycle deepwater competes"),
     "instruments": ("XBRUSD", "XTIUSD"),
     "controls": ("Guyanese and Brazilian pre-salt milestones over the same years, which are the "
                  "same class of long-dated deepwater news at a scale that has already been "
                  "priced",
                  "the deepwater rig and service tape, which moves on drilling activity "
                  "independently of any single basin",
                  "matched non-announcement weeks"),
     "notes": "NEGATIVE MILESTONES ARE THE CLEANER EVENTS HERE. A discovery announcement is "
              "ambiguous in size; a write-down is unambiguous, and the pack weights the sample "
              "accordingly rather than only collecting the good news"},
    {"id": "SA-P", "title": "NAMIBIA: the Common Monetary Area read from the member that is not "
                            "South Africa",
     "objects": ("the 1:1 peg and the rand's legal-tender status in Namibia",
                 "the Namibian repo rate and its spread to the South African one",
                 "Bank of Namibia reserves and import cover",
                 "the NSX LOCAL index against the overall index, which is Johannesburg",
                 "Namibian CPI as a residual to South African CPI"),
     "conditions": ("the repo spread state: zero, positive or negative to the SARB",
                    "whether a SARB decision landed in the window, which is the dominant event",
                    "whether a Namibian-specific shock -- uranium, SACU, Orange Basin -- landed "
                    "in the same window"),
     "instruments": ("USDZAR", "ZARJPY", "EURZAR"),
     "controls": ("South Africa itself, which is the whole identification: anything that moves in "
                  "both is the rand and only what moves in Namibia alone is Namibian",
                  "Lesotho and Eswatini, the other two CMA members at the same parity with "
                  "neither uranium nor an oil basin",
                  "the NSX overall index, which is a Johannesburg index wearing a Namibian flag "
                  "and is the wrong observable by construction"),
     "notes": "USDZAR IS LABELLED **EXACT** FOR NAD RATHER THAN A PROXY, and that is what makes "
              "this domain an IDENTIFICATION strategy rather than a currency bet: the desk can "
              "already trade the rand, so what Namibia adds is a third-party read on it"},
    {"id": "SA-Q", "title": "REGIONAL: one reservoir system, three metals",
     "objects": ("the weekly Kariba lake level and usable storage",
                 "the Zambezi River Authority's allocation split between Zimbabwe and Zambia",
                 "Cahora Bassa generation and availability on the same river system",
                 "load-shedding schedules and smelter curtailment announcements in all three "
                 "affected countries",
                 "Southern African Power Pool trades and Eskom's own availability"),
     "conditions": ("the lake level bucket against its own historical distribution",
                    "the wet season versus the dry season",
                    "whether an allocation cut had been announced",
                    "whether Eskom was itself load-shedding, which removes the import fallback"),
     "instruments": ("XPTUSD", "XCUUSD", "XALUSD"),
     "controls": ("global supply of each metal, against which the regional smelting affected here "
                  "is a small share -- the pack tests the regional PRODUCTION series first",
                  "Chinese and Gulf smelter curtailments, the same class of event at a size that "
                  "does move price",
                  "matched seasons with a high lake level, which separates 'dry season' from "
                  "'water shortage'",
                  "Zambian production from the `copperbelt` pack, which is the other half of the "
                  "same reservoir and cannot be measured from this side alone"),
     "notes": "A WEEKLY PUBLISHED PHYSICAL NUMBER THAT BINDS A METALS SUPPLY CHAIN is rare enough "
              "to justify a domain; the joint measurement with `copperbelt` is what makes it "
              "identifiable"},
    {"id": "SA-R", "title": "REGIONAL: five calendars and three weekend-substitution regimes",
     "objects": ("the five national holiday tables, computed rather than typed",
                 "the Sunday-to-Monday substitution in Zimbabwe, Botswana and Namibia and its "
                 "ABSENCE in Mozambique and Angola",
                 "the days on which all five close, which are very few",
                 "Zimbabwe's Heroes' Day on the second Monday of August and Botswana's "
                 "President's Day on the third Monday of July, both weekday rules"),
     "conditions": ("how many of the five closed on the day: one, some, or all",
                    "whether the closure is a SUBSTITUTED Monday rather than a statutory date",
                    "whether the day is also a South African closure, because the rand's "
                    "liquidity is what actually thins"),
     "instruments": ("USDZAR", "EURZAR", "XPTUSD", "XAUUSD"),
     "controls": ("the matched weekday twenty-six weeks away, which is the standard holiday "
                  "control and the one this domain exists to protect",
                  "days on which only ONE of the five closed, which separates a regional "
                  "liquidity effect from a national one",
                  "South African closures, which dominate rand liquidity and would produce the "
                  "same effect with nothing else happening"),
     "notes": "THE SUBSTITUTION RULE IS DERIVED RATHER THAN TYPED FOR EXACTLY THIS DOMAIN'S SAKE: "
              "a one-rule regional calendar invents closures in Mozambique and Angola and loses "
              "them in the other three, and that misalignment is invisible in a results table"},
)

#: Which jurisdiction owns each domain, so a test can prove the pack owes each of the five at
#: least two domains of its OWN rather than five countries' worth of one country's mechanisms.
DOMAIN_JURISDICTION: dict[str, tuple[str, ...]] = {
    "SA-A": ("zw",), "SA-B": ("zw",), "SA-C": ("zw",), "SA-D": ("zw",), "SA-E": ("zw",),
    "SA-F": ("bw",), "SA-G": ("bw",), "SA-H": ("bw", "na"),
    "SA-I": ("mz",), "SA-J": ("mz",), "SA-K": ("mz",), "SA-L": ("mz",),
    "SA-M": ("ao",), "SA-N": ("ao",),
    "SA-O": ("na",), "SA-P": ("na",),
    "SA-Q": ("zw", "mz", "ao", "na", "bw"), "SA-R": ("zw", "bw", "mz", "ao", "na"),
}
#: The mechanism family and the horizon each domain mints its cells under.
DOMAIN_MECHANISM: dict[str, str] = {
    "SA-A": "administered_price", "SA-B": "policy_surprise", "SA-C": "regime_break",
    "SA-D": "official_demand", "SA-E": "capital_flight", "SA-F": "release_surprise",
    "SA-G": "carry_funding", "SA-H": "transfer", "SA-I": "capacity_ramp",
    "SA-J": "supply_shock", "SA-K": "chokepoint", "SA-L": "event_reaction",
    "SA-M": "regime_break", "SA-N": "physical_flow", "SA-O": "capacity_ramp",
    "SA-P": "peg_identification", "SA-Q": "supply_shock", "SA-R": "holiday_liquidity",
}
DOMAIN_HORIZON: dict[str, str] = {
    "SA-A": "1 to 4 quarters", "SA-B": "0 to 10 sessions", "SA-C": "1 to 3 quarters",
    "SA-D": "1 to 3 quarters", "SA-E": "2 to 8 weeks", "SA-F": "0 to 10 sessions",
    "SA-G": "1 to 8 weeks", "SA-H": "2 to 8 quarters", "SA-I": "1 to 8 quarters",
    "SA-J": "2 to 12 weeks", "SA-K": "2 to 8 weeks", "SA-L": "0 to 5 sessions",
    "SA-M": "1 to 4 quarters", "SA-N": "2 to 12 weeks", "SA-O": "0 to 10 sessions",
    "SA-P": "0 to 5 sessions and 1 to 4 quarters", "SA-Q": "4 to 26 weeks",
    "SA-R": "0 to 2 sessions",
}
# --------------------------------------------------------------------------- custom miners
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    {"name": "sa_beneficiation_orders", "domain_ids": ("SA-A", "SA-B"), "kind": "event",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.southern_africa.pack:mine_beneficiation_orders",
     "needs": ("BENEFICIATION_ORDERS", "XPTUSD and XPDUSD H1 bars",
               "Zimbabwean PGM export volumes", "the Veritas gazette index"),
     "notes": "the gazetted export controls as a dated treatment, anchored on the GAZETTE date "
              "and not the ministerial announcement -- the two differ by months and often by "
              "forever"},
    {"name": "sa_currency_regimes", "domain_ids": ("SA-C", "SA-E"), "kind": "macro",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.southern_africa.pack:mine_currency_regimes",
     "needs": ("CURRENCY_ERAS", "XAUUSD and USDZAR D1 bars", "the tracked parallel premium"),
     "notes": "six dated currency eras since 2008, each a partition rather than a sample; the "
              "Namibian 1:1 peg is the zero-discretion control the miner always carries"},
    {"name": "sa_gold_delivery_plane", "domain_ids": ("SA-D",), "kind": "physical",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.southern_africa.pack:mine_gold_delivery_plane",
     "needs": ("GOLD_POLICY_EVENTS", "Fidelity delivery kilogrammes", "XAUUSD H1 bars",
               "Comtrade mirror imports for HS7108"),
     "notes": "payment-term changes as an on/off switch on a declared physical flow, with the "
              "Ghanaian and Tanzanian purchase programmes as the class-level placebos"},
    {"name": "sa_diamond_cycle", "domain_ids": ("SA-F",), "kind": "release",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.southern_africa.pack:mine_diamond_cycle",
     "needs": ("DIAMOND_CYCLES_PER_YEAR", "De Beers cycle revenue prints", "US500 and UK100 bars",
               "the lab-grown share series"),
     "notes": "ten dated luxury-demand prints a year against their own trailing seasonal norm, "
              "with the lab-grown substitution named as the confound rather than assumed away"},
    {"name": "sa_pula_basket", "domain_ids": ("SA-G", "SA-H"), "kind": "carry",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.southern_africa.pack:mine_pula_basket",
     "needs": ("PULA_BASKET", "PULA_CRAWL", "USDZAR and the rand crosses", "SACU pool shares"),
     "notes": "the published basket is the NULL and the residual is the measurement; a fitted "
              "beta here would be re-deriving a number the Bank of Botswana already published"},
    {"name": "sa_energy_province", "domain_ids": ("SA-I", "SA-M", "SA-O"), "kind": "event",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.southern_africa.pack:mine_energy_province",
     "needs": ("ENERGY_MILESTONES", "XBRUSD, XTIUSD and XNGUSD H1 bars",
               "OPEC MOMR secondary-source production"),
     "notes": "three energy clocks in one miner because they are the same KIND of event -- a "
              "dated change in a long-dated supply schedule -- and each is the others' control"},
    {"name": "sa_corridor_and_water", "domain_ids": ("SA-K", "SA-J", "SA-Q"), "kind": "physical",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.southern_africa.pack:mine_corridor_and_water",
     "needs": ("Kariba weekly lake levels", "Beira, Nacala, Lobito and Walvis Bay throughput",
               "XCUUSD, XALUSD and XPTUSD D1 bars", "the `copperbelt` pack's production ground"),
     "notes": "a corridor fall is a ROUTING event until another corridor's series says otherwise, "
              "and the reservoir constrains three metals at once; neither claim can be "
              "established without the sibling pack"},
    {"name": "sa_calendar_plane", "domain_ids": ("SA-R",), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.southern_africa.pack:mine_calendar_plane",
     "needs": ("HOLIDAYS_RULE", "USDZAR, XPTUSD and XAUUSD H1 bars"),
     "notes": "five calendars and THREE substitution regimes, with the one-country-closed days "
              "and the substituted Mondays as the separating controls"},
    {"name": "sa_transmission_seeds",
     "domain_ids": ("SA-L", "SA-N", "SA-P"),
     "kind": "transfer", "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.southern_africa.pack:mine_transmission_seeds",
     "needs": ("TRANSMISSION_EDGES_SEED",),
     "notes": "the pack's own map as HYPOTHESIS discoveries, deduplicated by the registry"},
)
MINER_DOMAINS: dict[str, tuple[str, ...]] = {
    "central_bank_surprise": ("SA-C", "SA-G", "SA-N", "SA-P"),
    "release_surprise": ("SA-F", "SA-M", "SA-O"),
    "calendar_settlement": ("SA-R", "SA-H"), "holiday_liquidity": ("SA-R",),
    "positioning": ("SA-P",), "carry_funding": ("SA-G", "SA-C", "SA-N"),
    "corporate_flow": ("SA-A", "SA-F", "SA-J"), "institutional_flow": ("SA-H", "SA-L"),
    "equity_mechanics": ("SA-E",), "derivatives_expiry": ("SA-P",),
    "failure": ("SA-C", "SA-L"), "residual": ("SA-B", "SA-I"),
    "transfer": ("SA-H", "SA-K"), "scouts": ("SA-D", "SA-O"),
    "session_microstructure": ("SA-R", "SA-E"),
}

# --------------------------------------------------------------------------- transmission
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    {"id": "SA-E1", "source": "Zimbabwean gazetted export control on unbeneficiated "
                              "platinum-group concentrate",
     "target": "XPTUSD", "targets": ("XPTUSD", "XPDUSD"), "to_country": "global", "sign": "+",
     "mechanism": "the world's third-largest PGM producer restricts the export of concentrate "
                  "until it is refined at home; the ounces do not disappear, they arrive LATER "
                  "and from a different point in the chain, which is a timing shock to refined "
                  "supply and a stock build in concentrate",
     "horizon": "1 to 4 quarters for the diversion; 0 to 5 sessions for the gazette",
     "horizon_class": "multi_day", "lag_days": 45.0,
     "actor": "the Great Dyke operators and the Ministry of Mines",
     "constraint": "domestic smelting and refining capacity, which is the binding physical limit "
                   "and the reason the control has been deferred more than once",
     "flow": "concentrate exported for South African refining, or held as stock at home",
     "condition": "a statutory instrument gazetted, commenced or deferred",
     "control": "South African PGM supply over the same months, which dwarfs Zimbabwe's; Russian "
                "palladium, the separating control for a platinum-versus-palladium claim; the "
                "matched-weekday control around each Friday gazette",
     "falsifier": "no interruption appears in Zimbabwean PGM export volumes or in the partner "
                  "countries' mirror imports across any gazetted commencement date, and no "
                  "concentrate stock build appears in the operators' reporting -- in which case "
                  "the control was never enforced and this is a press story",
     "evidence": "HYPOTHESIS"},
    {"id": "SA-E2", "source": "Zimbabwe's December 2022 ban on unbeneficiated lithium ore exports "
                              "as a RESOURCE-NATIONALISM event",
     "target": "XPTUSD", "targets": ("XPTUSD", "XCUUSD", "USDZAR"), "to_country": "global",
     "sign": "+",
     "mechanism": "a sovereign with Africa's largest hard-rock lithium resource bans the export "
                  "of raw ore by statutory instrument. Lithium is not quotable here, so the "
                  "testable claim is the POLICY CLASS: that a gazetted resource-nationalist act "
                  "raises the perceived policy risk on every OTHER mineral the same ministry "
                  "regulates, and on the regional risk carrier",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 0.0,
     "actor": "the Ministry of Mines, the lithium operators and their Chinese converter buyers",
     "constraint": "domestic processing capacity that did not exist when the order commenced",
     "flow": "raw ore exported, or concentrated domestically before export",
     "condition": "a gazetted export control on ANY mineral",
     "control": "the other clauses commenced by the same instrument or budget; Indonesian nickel "
                "ore and Chilean lithium policy over the same quarters, which are the same class "
                "of event with no Zimbabwean content; matched non-event Fridays",
     "falsifier": "gazetted Zimbabwean export controls produce no measurable move in the regional "
                  "risk carrier or in the other metals the same ministry regulates, against "
                  "matched Fridays -- in which case resource nationalism here is priced as noise",
     "evidence": "HYPOTHESIS"},
    {"id": "SA-E3", "source": "the ZiG's published gold and foreign-exchange reserve cover",
     "target": "XAUUSD", "targets": ("XAUUSD", "USDZAR"), "to_country": "global", "sign": "+",
     "mechanism": "a central bank that has structured its currency against gold is a PERSISTENT "
                  "OFFICIAL-SECTOR BUYER of the metal, and it must keep buying to hold the cover "
                  "as the money supply grows. That is official demand with a published "
                  "constraint behind it, which is rarer than official demand with a target",
     "horizon": "1 to 4 quarters", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "the Reserve Bank of Zimbabwe and Fidelity Gold Refinery",
     "constraint": "domestic gold deliveries, which are the only source the RBZ can buy from "
                   "without spending foreign exchange it does not have",
     "flow": "domestically refined gold into reserves instead of into export",
     "condition": "a monetary policy statement or instrument changing the cover or the surrender "
                  "requirement",
     "control": "Ghana's and Tanzania's own domestic gold purchase programmes over the same "
                "years, which decide whether this is about Zimbabwe or about African central "
                "banks as a class; the gold price itself; small-scale production trend",
     "falsifier": "the published gold backing does not rise through periods the RBZ says it is "
                  "accumulating, and deliveries show no diversion from export to domestic "
                  "purchase across the 2024-04-05 boundary -- in which case the backing is a "
                  "label",
     "evidence": "HYPOTHESIS"},
    {"id": "SA-E4", "source": "Zimbabwean gold payment-term changes as an on/off switch on a "
                              "declared physical flow",
     "target": "XAUUSD", "targets": ("XAUUSD",), "to_country": "global", "sign": "-",
     "mechanism": "small-scale producers choose between the statutory buyer's discounted, "
                  "partly-local-currency price and an informal cross-border buyer paying dollars. "
                  "A payment-term change switches the declared route on or off within a quarter, "
                  "which makes the delivery series a dated treatment on an informal flow",
     "horizon": "1 to 3 quarters", "horizon_class": "multi_day", "lag_days": 60.0,
     "actor": "Fidelity Gold Refinery and tens of thousands of small-scale miners",
     "constraint": "a porous border that gives every producer an alternative buyer",
     "flow": "declared delivery to the statutory buyer, or undeclared export",
     "condition": "a circular or instrument changing the payment split or the price discount",
     "control": "the partner countries' mirror imports over the same quarters, which must move "
                "in the OPPOSITE direction if this is routing and not production; the gold price; "
                "the Ugandan 2021 levy episode as the same mechanism pointed the other way",
     "falsifier": "a payment-term change produces no move in declared deliveries against matched "
                  "months and the mirror gap does not move oppositely -- in which case the series "
                  "measures production, not a routing decision",
     "evidence": "MEASURED_ELSEWHERE"},
    {"id": "SA-E5", "source": "De Beers sales cycle revenue against its own trailing seasonal norm",
     "target": "US500", "targets": ("US500", "UK100", "USDZAR"), "to_country": "global",
     "sign": "+",
     "mechanism": "ten times a year the dominant seller of rough diamonds publishes what the "
                  "trade actually paid. Rough demand is derived from polished demand, which is "
                  "derived from discretionary luxury spending, so the print is a dated, "
                  "high-frequency read on the luxury consumer with a published calendar",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 3.0,
     "actor": "De Beers Global Sightholder Sales and the sightholders",
     "constraint": "the sightholders' own polished inventory and the deferrals they are granted",
     "flow": "rough diamonds from the producer to the cutting centres, priced by assortment",
     "condition": "a cycle close, with the revenue surprise against the trailing seasonal norm",
     "control": "the lab-grown share, which takes the low end and would produce the same revenue "
                "fall with no demand change; the broad index, so the claim is about the LUXURY "
                "component; matched non-release weekdays around each close",
     "falsifier": "cycle revenue surprises have no measurable relationship to luxury-heavy "
                  "indices at any horizon out to a quarter, controlling for the broad index -- "
                  "in which case the print is a channel fact and not a demand fact",
     "evidence": "HYPOTHESIS"},
    {"id": "SA-E6", "source": "the Bank of Botswana's PUBLISHED 40% rand weight and annual crawl",
     "target": "USDZAR", "targets": ("USDZAR", "EURZAR", "ZARJPY"), "to_country": "bw",
     "sign": "+",
     "mechanism": "a peg whose weights are published is a peg whose behaviour is arithmetic. "
                  "A rand move passes mechanically into the pula at the published weight, and "
                  "everything that does NOT is discretionary intervention -- which is the only "
                  "part worth testing and is measurable only because the rule is public",
     "horizon": "1 to 8 weeks", "horizon_class": "multi_day", "lag_days": 0.0,
     "actor": "the Bank of Botswana's basket desk",
     "constraint": "reserves, and a diamond revenue base that is the peg's only funding",
     "flow": "the daily fixing against the published basket",
     "condition": "the residual to a mechanical replication of the published basket and crawl",
     "control": "the mechanical 60/40 replication itself as the null; the Namibian 1:1 peg as "
                "the zero-discretion extreme; the rand's own idiosyncratic moves, which pass "
                "through by construction and carry no Botswana information",
     "falsifier": "the observed fixing is not replicable from the published basket and crawl to "
                  "within a small residual over a quiet period -- in which case the published "
                  "weights are not the operative rule and the whole premise is wrong",
     "evidence": "MEASURED_ELSEWHERE"},
    {"id": "SA-E7", "source": "the SACU revenue-sharing formula and its two-year retrospective "
                              "adjustment",
     "target": "USDZAR", "targets": ("USDZAR", "US500"), "to_country": "global", "sign": "-",
     "mechanism": "South African import demand fills a common customs pool; a published formula "
                  "divides it among five members with a lag and a retrospective adjustment. Two "
                  "sovereign budgets therefore move on SOUTH AFRICAN import volumes from two "
                  "years earlier, mechanically and with no discretion at all",
     "horizon": "2 to 8 quarters", "horizon_class": "multi_day", "lag_days": 180.0,
     "actor": "the SACU Secretariat and the Botswana and Namibian treasuries",
     "constraint": "a pool that depends overwhelmingly on one member's imports",
     "flow": "customs and excise revenue from the pool to the member states, quarterly",
     "condition": "an up-cycle or clawback year for the transfer, known two years ahead",
     "control": "South African import volumes as the pool's own driver; Lesotho's and Eswatini's "
                "shares, which face the same formula with no diamonds and no uranium; the "
                "members' own non-SACU revenue",
     "falsifier": "the SACU receipts line shows no relationship to South African import volumes "
                  "at the formula's own lag -- which would mean the formula is not being applied "
                  "as published",
     "evidence": "MEASURED_ELSEWHERE"},
    {"id": "SA-E8", "source": "the Mozambican LNG timetable: Coral South, Area 1 force majeure "
                              "and its lifting",
     "target": "XNGUSD", "targets": ("XNGUSD", "XBRUSD"), "to_country": "global", "sign": "-",
     "mechanism": "a dated milestone on a sanctioned LNG project is a step change in a FORWARD "
                  "SUPPLY SCHEDULE the market has already priced expectations for. The tradable "
                  "content is the deviation between the realised date and the expected one, not "
                  "the tonnage",
     "horizon": "1 to 8 quarters", "horizon_class": "multi_day", "lag_days": 0.0,
     "actor": "the Area 1 and Area 4 operators, ENH and the Instituto Nacional de Petróleo",
     "constraint": "security in Cabo Delgado, which is why the offshore project produced and the "
                   "onshore one did not",
     "flow": "LNG cargoes under long-term contracts into the Asian and European markets",
     "condition": "a dated milestone with status GAZETTED or ANNOUNCED, never PROJECTED",
     "control": "US Gulf Coast and Qatari tranches over the same quarters, each of which dwarfs "
                "Mozambique; the European gas price regime, which dominated 2021-2022; the "
                "Mozambican fiscal and trade series, where the tranche IS large",
     "falsifier": "no measurable move in the gas complex around any dated Mozambican milestone "
                  "once the US, Qatari and European confounds are controlled -- in which case "
                  "the price leg dies and only the fiscal leg survives",
     "evidence": "HYPOTHESIS"},
    {"id": "SA-E9", "source": "Cahora Bassa availability and the Mozal smelter's power",
     "target": "XALUSD", "targets": ("XALUSD",), "to_country": "global", "sign": "+",
     "mechanism": "an aluminium smelter cannot be interrupted without damage measured in months, "
                  "so a hydropower interruption on its dedicated line is a REAL, DATED supply "
                  "interruption in primary aluminium rather than a demand response",
     "horizon": "2 to 12 weeks", "horizon_class": "multi_day", "lag_days": 7.0,
     "actor": "Hidroeléctrica de Cahora Bassa, Electricidade de Moçambique and the smelter",
     "constraint": "a single power source and a single transmission corridor",
     "flow": "LME-grade primary aluminium exported, or not produced at all",
     "condition": "a reported interruption, curtailment or restart",
     "control": "Chinese and Gulf smelter curtailments over the same months, the same class of "
                "event at a size that does move price; Mozambican export volumes, where the "
                "effect is large; matched non-interruption weeks at the same reservoir level",
     "falsifier": "reported interruptions produce no move in the aluminium complex against "
                  "matched weeks and Mozambican export volumes do not fall -- in which case "
                  "inventory absorbs it and the edge is not there",
     "evidence": "HYPOTHESIS"},
    {"id": "SA-E10", "source": "Beira and Nacala corridor throughput and the transit split",
     "target": "XCUUSD", "targets": ("XCUUSD", "XZNUSD"), "to_country": "global", "sign": "+",
     "mechanism": "landlocked Copperbelt metal has five routes to the sea. A fall at one corridor "
                  "is a supply interruption ONLY if the others do not absorb it, so the claim "
                  "tested here is explicitly conditional on the other four corridors' series",
     "horizon": "2 to 8 weeks", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "Portos e Caminhos de Ferro de Moçambique and the Beira and Nacala concessions",
     "constraint": "rail capacity rather than port capacity, and a cyclone season that closes "
                   "the line",
     "flow": "Copperbelt copper and cobalt, Malawian and Zimbabwean trade, to and from the sea",
     "condition": "a month in which Beira or Nacala transit fell more than its own interquartile "
                  "range",
     "needs_sibling_pack": "copperbelt",
     "control": "Durban, Dar es Salaam, Walvis Bay and Lobito throughput over the same months: a "
                "fall here that appears as a rise there is a ROUTING event and carries no supply "
                "information; Copperbelt production itself; Chinese import demand",
     "falsifier": "corridor falls at Beira are matched one-for-one by rises elsewhere in every "
                  "episode -- in which case no supply information exists in the series at all",
     "evidence": "HYPOTHESIS"},
    {"id": "SA-E11", "source": "Angola's OPEC withdrawal, effective 2024-01-01",
     "target": "XBRUSD", "targets": ("XBRUSD", "XTIUSD"), "to_country": "global", "sign": "-",
     "mechanism": "a quota binds only if the member could otherwise produce more. Angola's "
                  "production had been declining for a decade and sat below its allocation, so "
                  "the exit is a natural experiment on whether an OPEC quota constrains output "
                  "or merely constrains the BASELINE the next quota is struck from",
     "horizon": "1 to 4 quarters", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "Sonangol, the ANPG, the operators in the blocks and the OPEC Secretariat",
     "constraint": "natural decline in mature deepwater fields, which no quota decision changes",
     "flow": "roughly 1.1 mb/d of crude, overwhelmingly to Asia",
     "condition": "member versus non-member era, and production above or below the assigned quota",
     "control": "Nigeria and Congo-Brazzaville, which had the same baseline dispute and did NOT "
                "leave; Angola's own pre-exit decline trend, against which any step must be "
                "shown; the OPEC+ group's own production",
     "falsifier": "Angolan production shows a discernible step at the boundary rather than "
                  "continuing its pre-existing trend -- which would mean the quota HAD been "
                  "binding and would falsify this pack's whole reading of the exit",
     "evidence": "MEASURED_ELSEWHERE"},
    {"id": "SA-E12", "source": "the Banco Nacional de Angola's published FX auction allocation",
     "target": "XBRUSD", "targets": ("XBRUSD", "USDZAR"), "to_country": "ao", "sign": "+",
     "mechanism": "an oil state's FX supply IS its oil receipts. The barrel moves the receipts, "
                  "the receipts move the auction allocation, the allocation moves the informal "
                  "premium and the import bill -- and three of those four links are published, "
                  "which makes this the most completely observable transmission in the pack",
     "horizon": "2 to 12 weeks", "horizon_class": "multi_day", "lag_days": 14.0,
     "actor": "the BNA auction desk, the commercial banks and the importers behind them",
     "constraint": "an import bill dominated by food and refined fuel that does not fall when "
                   "the barrel does",
     "flow": "dollars from crude sales through the central bank to the banks to the importers",
     "condition": "an auction allocation above or below its trailing norm",
     "control": "Nigeria's own rate unification and FX reform, an oil exporter running the same "
                "experiment with different institutions; the Angolan decline trend, which changes "
                "receipts with no policy change; matched non-auction weeks",
     "falsifier": "auction allocation shows no relationship to the crude price at any lag out to "
                  "two quarters, and the informal premium none to the allocation -- in which "
                  "case the chain is broken somewhere this pack has not looked",
     "evidence": "HYPOTHESIS"},
    {"id": "SA-E13", "source": "the Lobito Atlantic Railway concession and its capacity ramp",
     "target": "XCUUSD", "targets": ("XCUUSD", "XZNUSD"), "to_country": "global", "sign": "-",
     "mechanism": "a new corridor does not create copper, it lowers the cost and time of getting "
                  "existing copper out. The effect is on BASIS and INVENTORY -- where the metal "
                  "sits and how fast it arrives -- rather than on supply, and the pack tests it "
                  "as the basis claim it is",
     "horizon": "1 to 8 quarters", "horizon_class": "multi_day", "lag_days": 60.0,
     "actor": "the concession consortium, the Copperbelt producers and the Angolan state",
     "constraint": "a single line with an international border in the middle of it",
     "flow": "Copperbelt copper and cobalt to the Atlantic instead of to the Indian Ocean",
     "condition": "a published capacity milestone or a reported tonnage step",
     "needs_sibling_pack": "copperbelt",
     "control": "the eastern corridors' volumes over the same months, which must FALL if this is "
                "re-routing rather than new supply; Copperbelt production itself; the freight "
                "rate differential between the routes",
     "falsifier": "Lobito tonnage rises with no offsetting fall at the eastern corridors and no "
                  "change in Copperbelt production -- which would mean it is new supply and this "
                  "framing is wrong",
     "evidence": "HYPOTHESIS"},
    {"id": "SA-E14", "source": "Orange Basin appraisal results and the 2025 write-down",
     "target": "XBRUSD", "targets": ("XBRUSD", "XTIUSD"), "to_country": "global", "sign": "-",
     "mechanism": "a new deepwater province is a long-dated supply EXPECTATION, so each dated "
                  "well result is a revision to that expectation. Negative milestones -- a "
                  "write-down, a dry hole, a deferred FID -- are the cleaner events because they "
                  "are unambiguous in sign, which positive ones are not",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 0.0,
     "actor": "the Orange Basin operators, NAMCOR and the Ministry of Mines and Energy",
     "constraint": "no infrastructure in the basin and a high gas-to-oil ratio in some finds",
     "flow": "an expectation of future barrels, revised well by well",
     "condition": "a dated discovery, appraisal result, write-down or FID milestone",
     "control": "Guyanese and Brazilian pre-salt milestones over the same years, the same class "
                "of long-dated deepwater news already priced; the deepwater rig and service "
                "tape; matched non-announcement weeks",
     "falsifier": "no measurable move in the crude complex around any dated Orange Basin result "
                  "-- in which case the province is too far from production to be priced and "
                  "only the Namibian fiscal and FX legs survive",
     "evidence": "HYPOTHESIS"},
    {"id": "SA-E15", "source": "the Common Monetary Area's 1:1 parity between the Namibia dollar "
                               "and the rand",
     "target": "USDZAR", "targets": ("USDZAR", "ZARJPY"), "to_country": "za", "sign": "+",
     "mechanism": "at a one-to-one peg with the rand circulating as legal tender, Namibian demand "
                  "for local currency IS demand for rand. The edge is not a currency bet -- the "
                  "desk can already trade the rand -- it is an IDENTIFICATION: anything that "
                  "moves in Namibia and not in South Africa is Namibian, and anything that moves "
                  "in both is the rand",
     "horizon": "0 to 5 sessions and 1 to 4 quarters", "horizon_class": "multi_day",
     "lag_days": 0.0,
     "actor": "the Bank of Namibia and the South African Reserve Bank",
     "constraint": "the peg itself, plus rand reserves that must cover the Namibian issue",
     "flow": "rand and Namibia dollars circulating at par across an open border",
     "condition": "a Namibian-specific shock -- uranium, SACU, Orange Basin -- landing without a "
                  "South African one",
     "control": "South Africa itself, which IS the identification; Lesotho and Eswatini, the "
                "other two CMA members at the same parity with no uranium and no oil basin; the "
                "NSX overall index, which is a Johannesburg index and is the wrong observable",
     "falsifier": "the Namibian repo rate diverges persistently from the SARB's with no reserve "
                  "consequence, or the NSX local index tracks the overall index one-for-one -- "
                  "either would mean the peg does not bind the way this pack models it",
     "evidence": "MEASURED_ELSEWHERE"},
    {"id": "SA-E16", "source": "the Kariba lake level and the Zambezi River Authority's allocation",
     "target": "XPTUSD", "targets": ("XPTUSD", "XCUUSD", "XALUSD"), "to_country": "global",
     "sign": "+",
     "mechanism": "one reservoir system powers Zimbabwean PGM smelting, Zambian copper smelting "
                  "and -- through Cahora Bassa on the same river -- Mozambican aluminium. A "
                  "weekly published water level therefore constrains three metals' processing "
                  "capacity at once, which is a physical constraint on REFINED output rather "
                  "than on mined output",
     "horizon": "4 to 26 weeks", "horizon_class": "multi_day", "lag_days": 21.0,
     "actor": "the Zambezi River Authority, ZESA, ZESCO and Hidroeléctrica de Cahora Bassa",
     "constraint": "hydrology, and a minimum operating level below which generation stops",
     "flow": "electricity to smelters, or curtailment and imported metal instead",
     "condition": "the lake level bucket against its own historical distribution",
     "needs_sibling_pack": "copperbelt",
     "control": "global supply of each metal, against which the affected smelting is a small "
                "share -- the regional PRODUCTION series is tested first; Chinese and Gulf "
                "curtailments; matched seasons with a high lake level, which separates 'dry "
                "season' from 'water shortage'",
     "falsifier": "low lake levels produce no measurable curtailment in the region's smelters "
                  "against matched seasons -- in which case they are insulated by imported power "
                  "or their own generation and the channel is closed",
     "evidence": "HYPOTHESIS"},
)
# --------------------------------------------------------------------------- policy eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    {"name": "ZIMBABWE: the multi-currency dollarisation", "start": "2009-02-02",
     "end": "2019-02-19",
     "regime": "the Zimbabwe dollar was abandoned after hyperinflation and the economy "
               "transacted in US dollars, rand and pula; there was no domestic monetary policy "
               "at all, because there was no domestic money",
     "markers": ("2009-01-29 foreign-currency trading is legalised in the budget statement",
                 "2016 bond notes are introduced at a claimed 1:1 to the dollar",
                 "2018 the 1:1 fiction becomes untenable as RTGS balances diverge"),
     "why_it_matters": "there was no exchange rate, no policy rate and no domestic inflation "
                       "mechanism; every Zimbabwean series from this decade is measuring a "
                       "DOLLARISED economy and cannot be pooled with anything after it",
     "status": "SETTLED"},
    {"name": "ZIMBABWE: the RTGS dollar and the de-dollarisation attempt", "start": "2019-02-20",
     "end": "2024-04-04",
     "regime": "the Monetary Policy Statement of 2019-02-20 created the RTGS dollar and a "
               "managed float; SI 142/2019 made it sole legal tender on 2019-06-24 and SI "
               "85/2020 restored the use of foreign currency on 2020-03-26, so the era contains "
               "a de-dollarisation and its reversal",
     "markers": ("2019-02-20 the RTGS dollar is created",
                 "2019-06-24 SI 142/2019 makes it sole legal tender",
                 "2020-03-26 SI 85/2020 restores foreign currency use",
                 "2020-06 the ZSE is suspended and the Old Mutual implied-rate series ends",
                 "2022-07-25 the Mosi-oa-Tunya gold coins are launched"),
     "why_it_matters": "a currency that was sole legal tender for nine months and then not is "
                       "two regimes inside one era; the pack marks both boundaries and never "
                       "treats the period as homogeneous",
     "status": "SETTLED"},
    {"name": "ZIMBABWE: the ZiG and its first devaluation", "start": "2024-04-05",
     "end": "2026-12-31",
     "regime": "the ZiG was introduced on 2024-04-05 structured against gold and foreign exchange "
               "reserves with a published cover, and was devalued by roughly 43% on 2024-09-27 "
               "-- five months into the life of a currency whose design claim was stability",
     "markers": ("2024-04-05 the ZiG is introduced with a published reserve cover",
                 "2024-09-27 the ZiG is devalued by roughly 43% in one step"),
     "why_it_matters": "THE DEVALUATION IS THE TEST OF THE DESIGN. A reserve-backed currency that "
                       "devalues by 43% within six months tells the desk what the cover was "
                       "actually worth, and the pack partitions the ZiG era at that date",
     "status": "OPEN"},
    {"name": "ZIMBABWE: the beneficiation orders", "start": "2022-12-20", "end": "2026-12-31",
     "regime": "from the December 2022 statutory instrument banning unbeneficiated lithium ore "
               "exports, Zimbabwe has pursued export restriction as an industrial policy across "
               "lithium, platinum-group concentrate and chrome, with commencements, deferrals "
               "and amendments each gazetted",
     "markers": ("2022-12-20 the unbeneficiated lithium ore export order is gazetted",
                 "2023-2025 the raw PGM concentrate restriction is legislated, deferred and "
                 "re-stated more than once"),
     "why_it_matters": "the ANNOUNCEMENT-TO-GAZETTE-TO-COMMENCEMENT sequence means a policy can "
                       "be reported, real and inoperative at the same time; anchoring an event "
                       "window to the press date rather than the gazette misdates a large part "
                       "of the sample",
     "status": "OPEN"},
    {"name": "BOTSWANA: the diamond downturn and the renegotiated sales agreement",
     "start": "2023-01-01", "end": "2026-12-31",
     "regime": "rough diamond prices fell hard from 2023 as lab-grown stones took the low end "
               "and Chinese luxury demand weakened; Botswana's growth turned negative, Debswana "
               "cut production, and the sales agreement with De Beers was renegotiated to raise "
               "the state's own marketing share over time",
     "markers": ("2023 the agreement in principle raising the state's sales share",
                 "2024-2025 production cuts and a contraction in Botswana's GDP"),
     "why_it_matters": "a country whose exports are one commodity, whose currency is pegged and "
                       "whose budget is that commodity plus a customs transfer has no shock "
                       "absorber except reserves; the whole adjustment is visible in published "
                       "fiscal and reserve series rather than hidden in a currency",
     "status": "OPEN"},
    {"name": "MOZAMBIQUE: the hidden debt, the default and the restructuring",
     "start": "2016-04-01", "end": "2019-10-31",
     "regime": "roughly two billion dollars of undisclosed state-guaranteed borrowing surfaced in "
               "April 2016; donors suspended support, the IMF programme lapsed, the metical "
               "collapsed, the sovereign defaulted and the eurobond was restructured in 2019 "
               "with a London court record following for years afterwards",
     "markers": ("2016-04 the undisclosed borrowings are disclosed",
                 "2017-01 the sovereign misses a payment",
                 "2019-10 the restructured bond is issued"),
     "why_it_matters": "every Mozambican macro series from this window carries a credit event, a "
                       "donor suspension and a currency collapse at once; pooling it with the "
                       "administered-stability years after 2021 measures two different countries",
     "status": "SETTLED"},
    {"name": "MOZAMBIQUE: the Cabo Delgado force majeure", "start": "2021-04-26",
     "end": "2025-10-31",
     "regime": "TotalEnergies declared force majeure on the onshore Area 1 LNG project after the "
               "Palma attack, suspending roughly 13 mtpa of sanctioned capacity for four years; "
               "the offshore Coral South project continued and shipped its first cargo in "
               "November 2022",
     "markers": ("2021-03-24 the Palma attack",
                 "2021-04-26 force majeure is declared on Mozambique LNG",
                 "2022-11 Coral South ships its first cargo",
                 "2025 force majeure is lifted"),
     "why_it_matters": "THE LARGEST DATED SUPPLY-SCHEDULE REMOVAL AND RESTORATION IN THE PACK, "
                       "and it happened alongside the European gas crisis -- which is the "
                       "confound the pack names rather than the story it would prefer",
     "status": "SETTLED"},
    {"name": "MOZAMBIQUE: administered stability and the ECF", "start": "2021-01-01",
     "end": "2026-12-31",
     "regime": "the metical has been held administratively stable against the dollar since 2021 "
               "while an IMF Extended Credit Facility has run with periodic reviews; low "
               "realised currency variance in this era is a POLICY outcome and not a market one",
     "markers": ("2022 the ECF is approved", "2021-2025 the metical is held broadly flat"),
     "why_it_matters": "a study that treats post-2021 metical stability as evidence about the "
                       "Mozambican economy is measuring the central bank's allocation policy; "
                       "the informative series in this era are the reserves and the premium",
     "status": "OPEN"},
    {"name": "ANGOLA: the managed float and the 2023 step depreciation", "start": "2018-01-01",
     "end": "2023-12-31",
     "regime": "the BNA abandoned the hard peg in 2018 and moved to auction-based allocation; in "
               "2023 the state stopped supporting the rate out of oil receipts and the kwanza "
               "depreciated by roughly half in a matter of weeks",
     "markers": ("2018 the peg is abandoned for auction allocation",
                 "2023 the kwanza loses roughly half its value as support is withdrawn"),
     "why_it_matters": "the 2023 move was a FISCAL decision showing up as a monetary event, "
                       "which is the general shape of Angolan currency history and the reason "
                       "SA-N conditions on the budget's oil assumption and not on the policy rate",
     "status": "SETTLED"},
    {"name": "ANGOLA: outside OPEC", "start": "2024-01-01", "end": "2026-12-31",
     "regime": "Angola announced its withdrawal on 2023-12-21 over a quota baseline dispute and "
               "left with effect from 2024-01-01, the first exit in more than a decade; roughly "
               "1.1 mb/d moved from inside the quota framework to outside it",
     "markers": ("2023-12-21 the withdrawal is announced",
                 "2024-01-01 the withdrawal takes effect",
                 "2024-01 the MOMR reports Angola as a non-member for the first time"),
     "why_it_matters": "the OPEC production table changes MEANING at this boundary: the same "
                       "series is measuring a different group of countries, and any study that "
                       "pools the member aggregate across 2024-01-01 is adding and removing a "
                       "producer mid-sample",
     "status": "OPEN"},
    {"name": "NAMIBIA: the Orange Basin era", "start": "2022-02-01", "end": "2026-12-31",
     "regime": "the Venus and Graff discoveries of February 2022 made Namibia the newest oil "
               "province on earth; an appraisal campaign has run since, with farm-ins, flow "
               "tests, a 2025 write-down by one operator and a projected FID that has not "
               "arrived",
     "markers": ("2022-02 Venus and Graff are announced",
                 "2023-2025 the appraisal campaign and its farm-ins",
                 "2025-01 an operator writes down its interest"),
     "why_it_matters": "before 2022 Namibia was a mining and fishing economy with a peg; after "
                       "it, every Namibian fiscal and FX projection carries an oil option, and "
                       "the projections either side of the boundary are not comparable",
     "status": "OPEN"},
    {"name": "REGIONAL: the Common Monetary Area and SACU as the standing institutional frame",
     "start": "1993-01-01", "end": "2026-12-31",
     "regime": "the Namibia dollar has been pegged 1:1 to the rand since 1993 inside the CMA, "
               "alongside Lesotho's loti and Eswatini's lilangeni; SACU has run a common "
               "external tariff and a formula-shared revenue pool for Botswana, Namibia, "
               "Lesotho, Eswatini and South Africa since the 2002 agreement",
     "markers": ("1976 Botswana leaves the rand area and is in SACU only",
                 "1993 the Namibia dollar is introduced at par",
                 "2002 the revenue-sharing formula agreement"),
     "why_it_matters": "SACU IS NOT THE CMA and the membership lists differ. Botswana is in the "
                       "customs union and not the currency area; Zimbabwe, Mozambique and Angola "
                       "are in neither. A regional study that conflates them invents a peg where "
                       "there is none and misses one where there is",
     "status": "OPEN"},
)

ACCESS_CONSTRAINTS: tuple[dict[str, Any], ...] = (
    {"constraint": "none of the five currencies is quoted by this broker",
     "measured": "data/universe/universe.json holds no ZWG, BWP, MZN, AOA or NAD symbol",
     "consequence": "every domestic mechanism terminates in the metals, the energy legs, the "
                    "softs or the rand carriers; the five currencies are INPUTS, never cells, "
                    "and each is named in TRANSMISSION_TARGETS with its route. NAD is the one "
                    "exception and is labelled EXACT rather than PROXY, because a 1:1 peg with "
                    "the rand circulating as legal tender is not an approximation"},
    {"constraint": "diamonds, uranium and LNG have no instrument at this broker and their price "
                   "assessments forbid machine extraction",
     "measured": "Rapaport, Fastmarkets, UxC and TradeTech terms; registered "
                 "machine_use_allowed=false",
     "consequence": "SA-F is measured on the De Beers REVENUE print and the Botswana export "
                    "value-and-carats series rather than on a diamond price; uranium is routed "
                    "through the Namibian fiscal and FX channel; LNG is routed through XNGUSD "
                    "with the Henry Hub basis stated on the face of the edge"},
    {"constraint": "Zimbabwe has no continuous inflation series and its own agency says so",
     "measured": "the year-on-year rate was suspended in 2019 and the index has been re-based "
                 "more than once, including onto a blended basket and onto the ZiG",
     "consequence": "no SA-C cell conditions on a spliced Zimbabwean inflation rate; the "
                    "conditioning variables are the currency ERA and the tracked PREMIUM, and "
                    "the IMF Article IV reconstructions are the named substitute for the level"},
    {"constraint": "no retail margin or client-flow statistic exists in any of the five",
     "measured": "Zimbabwean exchange control forbids residents an offshore margin account, "
                 "Angola licenses no retail margin broker, and NBFIRA, the CMC, NAMFISA and the "
                 "Mozambican regulator publish no aggregate retail positioning",
     "consequence": "no microstructure claim in this pack may rest on a retail-flow number; the "
                    "retail ecology is read from public communities at UNRELIABLE and FRINGE "
                    "credibility and is declared per jurisdiction in NO_LAWFUL_GROUND"},
    {"constraint": "five central banks and three statistics offices publish on pages that "
                   "overwrite in place",
     "measured": "the RBZ rate page, the parallel-rate trackers, the BNA auction notices and "
                 "the Kariba bulletin all publish TODAY and keep no history",
     "consequence": "their point-in-time history exists only in the archive layer's crawls; a "
                    "cell compiled on an un-archived session is UNMEASURED rather than assumed, "
                    "and the affected datasets carry pit_feasible=False for exactly that reason"},
    {"constraint": "two of the five publish everything of consequence in Portuguese only",
     "measured": "the Boletim da República, the Diário da República, the BNA auction notices, "
                 "the Banco de Moçambique MIMO statements and the entire Mozambican and Angolan "
                 "business press",
     "consequence": "an English-only collector reads a wire summary days later or nothing at "
                    "all; every Mozambican and Angolan source class in this pack carries "
                    "Portuguese queries and the terminology table is written in Portuguese for "
                    "those domains"},
    {"constraint": "the corridor and reservoir claims cannot be established from this pack alone",
     "measured": "SA-K, SA-Q, SA-E10, SA-E13 and SA-E16 all name `copperbelt` as the sibling "
                 "whose production and Zambian smelting series supply the control",
     "consequence": "those edges carry `needs_sibling_pack` and are NOT promoted on this pack's "
                    "ground alone; an edge whose control lives in a pack nobody runs is an edge "
                    "nobody can falsify"},
    {"constraint": "the Lobito Corridor series began in 2024 and the Orange Basin has no "
                   "production at all",
     "measured": "first Lobito copper trains in 2024; no Namibian barrel has been produced",
     "consequence": "a short series is UNMEASURED before it is a signal; no cell in SA-O or on "
                    "SA-E13 is promoted on a series this young, and the projected milestones are "
                    "carried as PROJECTED and never as arrived"},
)

#: INTERACTION MINERS -- the other country packs this one has a MEASURABLE interaction with.
#: `za` IS FIRST AND MUST STAY FIRST: South Africa is the refining, port, power and financial hub
#: of all five and the ZAR is the executable proxy for the whole bloc, so this pack is `za`'s
#: COMPLEMENT by construction and a reader who takes it for a repeat has misread it.
INTERACTIONS: tuple[dict[str, Any], ...] = (
    {"with": "za",
     "mechanism": "SOUTH AFRICA IS THE HUB OF ALL FIVE AND THIS PACK IS ITS COMPLEMENT. Zimbabwean "
                  "PGM concentrate is smelted and refined through South African capacity; the "
                  "pula carries a PUBLISHED 40% rand weight; the Namibia dollar is pegged 1:1 to "
                  "the rand inside the CMA and the NSX's capitalisation is mostly Johannesburg "
                  "dual listings; Cahora Bassa sells into Eskom; and Angolan and Mozambican risk "
                  "is priced off the rand because nothing else in the bloc is liquid. `za` owns "
                  "the JSE, the SARB, Eskom and the rand's own idiosyncratic risk; THIS pack "
                  "owns the five sovereign policy machines that act on the physical commodities, "
                  "and the CMA seen from the member that is not South Africa",
     "observable": "South African PGM supply beside Zimbabwean concentrate exports; the SARB "
                   "repo beside the Bank of Namibia's and the Bank of Botswana's; Eskom "
                   "availability beside Cahora Bassa generation and the Kariba level; South "
                   "African import volumes beside the SACU pool two years later; the NSX local "
                   "index beside the NSX overall index, which IS the JSE",
     "targets": ("USDZAR", "EURZAR", "ZARJPY", "XPTUSD", "XPDUSD"),
     "control": "THE CARRIER IS NOT THE THING CARRIED -- except once. The rand contains South "
                "African idiosyncratic risk that none of these five economies has, and every "
                "edge that routes through it says so on its face. The exception is NAD: at 1:1 "
                "with the rand as legal tender there is no basis at all, which is why SA-E15 is "
                "an IDENTIFICATION strategy rather than a currency bet and why this interaction "
                "is the strongest in the file"},
    {"with": "copperbelt",
     "mechanism": "the Katangan and Zambian orebody has FIVE routes to the sea and this pack owns "
                  "three of them -- Beira, Nacala and now Lobito -- while Kariba's reservoir "
                  "powers the Zambian copper smelters on one side and the Zimbabwean PGM "
                  "smelters on the other. Neither pack can establish a routing or a smelting "
                  "constraint alone",
     "observable": "Beira, Nacala and Lobito throughput with the transit split by destination, "
                   "against Dar es Salaam and Durban; the weekly Kariba lake level against "
                   "Zambian smelter curtailments; Copperbelt production itself as the separating "
                   "series",
     "targets": ("XCUUSD", "XZNUSD", "XPTUSD", "XALUSD"),
     "control": "Copperbelt production separates 'less metal was produced' from 'the metal used "
                "another route'; the competing corridors separate a chokepoint from a routing "
                "event. A fall at Beira that appears as a rise at Dar es Salaam carries NO supply "
                "information, and NEITHER PACK CAN ESTABLISH THAT ALONE"},
    {"with": "ru",
     "mechanism": "Russia is the world's largest palladium producer and Zimbabwe is the third "
                  "PGM producer; together with South Africa they are essentially the whole "
                  "market. A Zimbabwean beneficiation event and a Russian supply event are the "
                  "same KIND of shock to the same metal, and each is the other's placebo",
     "observable": "Russian palladium and platinum export volumes and sanction milestones "
                   "against Zimbabwean concentrate export restrictions, on the same XPTUSD and "
                   "XPDUSD tape",
     "targets": ("XPTUSD", "XPDUSD"),
     "control": "the platinum-to-palladium ratio separates a Russian event from a Zimbabwean "
                "one, because the two orebodies have different ratios; a shock to the ratio is "
                "source-identifying in a way a shock to either price alone is not"},
    {"with": "ng",
     "mechanism": "Nigeria is the other large African oil exporter that had the SAME OPEC quota "
                  "baseline dispute as Angola and did NOT leave, and it unified its exchange "
                  "rate in June 2023 six months before Angola's own step depreciation. It is the "
                  "matched control for both Angolan mechanisms at once",
     "observable": "Nigerian production against its quota beside Angola's across the 2024-01-01 "
                   "boundary; the Nigerian rate unification of June 2023 beside the Angolan "
                   "depreciation of 2023, with the informal premium published on both sides",
     "targets": ("XBRUSD", "XTIUSD", "USDZAR"),
     "control": "Nigeria is the counterfactual Angola: same dispute, same decade, same commodity, "
                "and it stayed. If the exit had an effect that Nigeria does not show, the effect "
                "is the exit; if both show it, the effect is the oil market"},
    {"with": "cn",
     "mechanism": "China is the marginal buyer of Angolan crude, the destination of the "
                  "Copperbelt metal leaving through these corridors, the owner of two of the "
                  "Namibian uranium mines, the buyer of Zimbabwean lithium concentrate and the "
                  "swing consumer of polished diamonds. Every demand-side confound in this pack "
                  "is Chinese",
     "observable": "Chinese crude import volumes by origin, refined copper and concentrate "
                   "imports, and luxury retail against the De Beers sales cycle prints",
     "targets": ("XBRUSD", "XCUUSD", "US500", "UK100"),
     "control": "Chinese demand must be controlled from the `cn` pack's own series: a corridor "
                "fall during a Chinese demand slump is not a chokepoint, and a diamond cycle "
                "miss during a Chinese luxury slump is not a global luxury signal"},
    {"with": "au",
     "mechanism": "Australia is the comparison producer for three of this pack's commodities at "
                  "once -- uranium, lithium and the diamond market it exited -- and it is a "
                  "rule-of-law jurisdiction with the same geology and none of the policy risk, "
                  "which makes it the natural control for a resource-nationalism claim",
     "observable": "Australian uranium and spodumene production and policy against Namibian and "
                   "Zimbabwean volumes and gazetted orders",
     "targets": ("XPTUSD", "XCUUSD", "USDZAR"),
     "control": "Australia is the no-policy-risk counterfactual: a price move that appears "
                "against Australian and Zimbabwean supply alike is a market move, and only a "
                "move that discriminates between them is about the policy"},
)

INSTITUTIONAL_FLOW_SOURCES: tuple[str, ...] = (
    "De Beers rough diamond sales cycle revenue, ten dated prints a year",
    "Statistics Botswana diamond export value and carats, giving a realised price per carat",
    "Reserve Bank of Zimbabwe gold deliveries and the ZiG reserve cover",
    "Banco Nacional de Angola FX auction allocation and reserves",
    "SACU common revenue pool and the member shares with the two-year adjustment",
    "Bank of Namibia Quarterly Bulletin reserves and SACU receipts",
    "Zambezi River Authority weekly Kariba lake level and allocation",
    "Beira, Nacala, Lobito and Walvis Bay corridor throughput with the transit split",
    "OPEC Monthly Oil Market Report secondary-source production across the Angolan boundary",
    "UN Comtrade mirror statistics for PGM, gold, diamonds and crude",
)
SERIES: dict[str, str] = {
    "ZW_FX": "RBZ:wbws_rate", "ZW_PREMIUM": "TRACKERS:street_premium",
    "ZW_COVER": "RBZ:reserve_cover", "ZW_GOLD": "RBZ:gold_deliveries_kg",
    "ZW_PGM": "MMCZ:pgm_export_volume", "ZW_CPI": "ZIMSTAT:cpi_broken",
    "ZW_BOARDS": "ZSE_VFEX:index_spread",
    "BW_BASKET": "BOB:basket_weights", "BW_CRAWL": "BOB:rate_of_crawl",
    "BW_DIAMOND": "STATSBOTS:diamond_exports", "BW_CYCLE": "DEBEERS:cycle_revenue_usd",
    "BW_RESERVES": "BOB:gross_reserves",
    "MZ_FX": "BM:reference_rate", "MZ_MIMO": "BM:mimo", "MZ_LNG": "INP:lng_milestones",
    "MZ_POWER": "HCB:generation", "MZ_CORRIDOR": "CFM:transit_by_country",
    "AO_AUCTION": "BNA:auction_allocation", "AO_FX": "BNA:reference_rate",
    "AO_OIL": "OPEC:momr_secondary_ao", "AO_LOBITO": "LAR:tonnage",
    "NA_REPO": "BON:repo_spread_sarb", "NA_SACU": "BON:sacu_receipts",
    "NA_URANIUM": "NSA:uranium_exports", "NA_ORANGE": "MME:orange_basin_milestones",
    "SA_KARIBA": "ZRA:kariba_level", "SA_SACU_POOL": "SACU:common_revenue_pool",
    "SA_PINK": "WORLDBANK:pink_sheet", "SA_MIRROR": "COMTRADE:mirror_gap",
}
# --------------------------------------------------------------------------- mechanisms
#: THE SIX ZIMBABWEAN CURRENCY ERAS, as (start, label, status). This is the pack's single most
#: important partition: pooling a Zimbabwean series across any of these boundaries measures two
#: different monetary systems and calls the difference volatility.
CURRENCY_ERAS: tuple[tuple[date, str, str], ...] = (
    (date(1980, 4, 18), "ZWD_HYPERINFLATION", "SETTLED"),
    (date(2009, 2, 2), "MULTICURRENCY_DOLLARISED", "SETTLED"),
    (date(2019, 2, 20), "RTGS_DOLLAR", "SETTLED"),
    (date(2024, 4, 5), "ZIG", "OPEN"),
)
ZIG_LAUNCH = date(2024, 4, 5)
ZIG_DEVALUATION = date(2024, 9, 27)
DE_DOLLARISATION = date(2019, 6, 24)          # SI 142/2019: local currency sole legal tender
RE_DOLLARISATION = date(2020, 3, 26)          # SI 85/2020: foreign currency restored

#: THE GAZETTED AND PRESS-REPORTED BENEFICIATION ORDERS, as (date, mineral, what, status).
#: GAZETTED means a statutory instrument with a number; PRESS_REPORTED means exactly that -- a
#: ministerial statement or budget line to be confirmed against the gazette before any cell is
#: promoted on it. The distinction is the whole discipline of SA-B.
BENEFICIATION_ORDERS: tuple[tuple[date, str, str, str], ...] = (
    (date(2022, 12, 20), "lithium",
     "the Base Minerals Export Control order bans the export of unbeneficiated lithium ore",
     "GAZETTED"),
    (date(2023, 1, 1), "pgm",
     "the government states that raw platinum-group concentrate exports will be prohibited",
     "PRESS_REPORTED"),
    (date(2024, 1, 1), "pgm",
     "the announced concentrate restriction is DEFERRED rather than commenced, which resets the "
     "clock and is itself the most informative event in the series",
     "PRESS_REPORTED"),
    (date(2025, 1, 1), "pgm",
     "the restriction is re-stated with a later horizon and the deferral pattern repeats",
     "PRESS_REPORTED"),
)

#: The dated gold-policy events. Zimbabwe's are the mirror image of Uganda's export levy in the
#: `east_africa` pack: there a levy switched a declared flow OFF, here a payment term and a
#: gold-backed instrument switch one ON.
GOLD_POLICY_EVENTS: tuple[tuple[date, str, str, str], ...] = (
    (date(2022, 7, 25), "zw", "the Mosi-oa-Tunya gold coins are launched as a store of value "
                              "and a sterilisation instrument", "PRESS_REPORTED"),
    (date(2023, 5, 8), "zw", "gold-backed digital tokens are issued against the same reserve",
     "PRESS_REPORTED"),
    (date(2024, 4, 5), "zw", "the ZiG is introduced with a published gold and foreign-exchange "
                             "reserve cover, making the central bank a standing gold buyer",
     "GAZETTED"),
    (date(2024, 9, 27), "zw", "the ZiG is devalued by roughly 43%, which is the test of what the "
                              "cover was actually worth", "GAZETTED"),
)

#: The energy province milestones across three countries, as (date, jurisdiction, what, status).
#: A PROJECTED row may never arrive and no cell is promoted on one.
ENERGY_MILESTONES: tuple[tuple[date, str, str, str], ...] = (
    (date(2021, 3, 24), "mz", "the Palma attack", "ANNOUNCED"),
    (date(2021, 4, 26), "mz", "TotalEnergies declares force majeure on Mozambique LNG, "
                              "suspending roughly 13 mtpa of sanctioned capacity", "ANNOUNCED"),
    (date(2022, 2, 1), "na", "the Venus and Graff discoveries are announced in the Orange Basin",
     "ANNOUNCED"),
    (date(2022, 11, 13), "mz", "Coral South FLNG ships its first cargo at roughly 3.4 mtpa",
     "ANNOUNCED"),
    (date(2023, 12, 21), "ao", "Angola announces its withdrawal from OPEC", "ANNOUNCED"),
    (date(2024, 1, 1), "ao", "the withdrawal takes effect and the MOMR reports Angola as a "
                             "non-member", "GAZETTED"),
    (date(2025, 1, 15), "na", "an operator writes down its Orange Basin interest -- a dated "
                              "NEGATIVE milestone, which is unambiguous in sign where a "
                              "discovery announcement is not", "PRESS_REPORTED"),
    (date(2025, 10, 24), "mz", "the Mozambique LNG force majeure is lifted after four years",
     "PRESS_REPORTED"),
)

OPEC_EXIT_ANNOUNCED = date(2023, 12, 21)
OPEC_EXIT_EFFECTIVE = date(2024, 1, 1)
MZ_FORCE_MAJEURE = date(2021, 4, 26)
MZ_CORAL_FIRST_CARGO = date(2022, 11, 13)
MZ_FORCE_MAJEURE_LIFTED = date(2025, 10, 24)
NA_DISCOVERY = date(2022, 2, 1)
NA_WRITEDOWN = date(2025, 1, 15)

#: THE PUBLISHED PULA BASKET. This is the rarest thing in frontier FX: an official, numeric,
#: published currency weight. The measurement in SA-G is the RESIDUAL to this rule, never a
#: fitted beta -- fitting one would be re-deriving a number the authority already gave away.
PULA_BASKET: dict[str, float] = {"SDR": 0.60, "ZAR": 0.40}
#: The annual rate of crawl, announced each year in the Monetary Policy Statement. A year this
#: pack cannot cite is UNMEASURED and returns None rather than a plausible number (L1.28a).
PULA_CRAWL: dict[int, tuple[float | None, str]] = {
    2023: (-1.51, "PUBLISHED: a downward crawl of 1.51% announced for 2023"),
    2024: (None, "UNMEASURED: read the rate of crawl off the year's Monetary Policy Statement "
                 "before compiling any cell that conditions on it"),
    2025: (None, "UNMEASURED: read the rate of crawl off the year's Monetary Policy Statement"),
    2026: (None, "UNMEASURED: read the rate of crawl off the year's Monetary Policy Statement"),
}
#: De Beers holds TEN sales cycles a year on a calendar it publishes in advance. The windows this
#: pack derives are EVENLY SPACED AND APPROXIMATE, and they are labelled so: the real calendar is
#: published and must be read before a cell is promoted on a specific cycle.
DIAMOND_CYCLES_PER_YEAR = 10
DIAMOND_CYCLE_STATUS = ("APPROXIMATE_DERIVED: ten evenly spaced windows as a scheduling "
                        "scaffold; the operative calendar is published by De Beers in advance "
                        "and must be read before any cell is promoted on a named cycle")

#: THE TWO REGIONAL INSTITUTIONS, AND THEY ARE NOT THE SAME INSTITUTION. Conflating them invents
#: a peg where there is none (Botswana) and misses one where there is (Lesotho and Eswatini).
CMA_MEMBERS: tuple[str, ...] = ("za", "na", "ls", "sz")
SACU_MEMBERS: tuple[str, ...] = ("za", "bw", "na", "ls", "sz")


def zim_currency_era(day: date) -> str:
    """Which of Zimbabwe's currency regimes a date sits in. Six regimes in sixteen years, and
    each one is a partition rather than a sample: a study that pools across 2019-02-20 or
    2024-04-05 is measuring two monetary systems and calling the difference volatility."""
    label = CURRENCY_ERAS[0][1]
    for start, name, _status in CURRENCY_ERAS:
        if day >= start:
            label = name
    return label


def zig_state(day: date) -> str:
    """PRE_ZIG, ZIG_AS_LAUNCHED or ZIG_POST_DEVALUATION.

    The devaluation of 2024-09-27 is what makes the ZiG two regimes rather than one: a currency
    whose design claim was a published reserve cover lost roughly 43% of its value five months
    into its life, and the pack refuses to pool the two halves.
    """
    if day < ZIG_LAUNCH:
        return "PRE_ZIG"
    return "ZIG_AS_LAUNCHED" if day < ZIG_DEVALUATION else "ZIG_POST_DEVALUATION"


def beneficiation_state(day: date, mineral: str) -> str:
    """The most recent gazetted or press-reported export-control state for a mineral on a date.

    Returns NONE, GAZETTED or PRESS_REPORTED. The distinction is the discipline: a policy can be
    reported, real and inoperative at the same time, and anchoring an event window to a press
    date rather than a gazette date misdates a large part of the sample.
    """
    key = str(mineral).lower()
    state = "NONE"
    for when, which, _what, status in BENEFICIATION_ORDERS:
        if which == key and day >= when:
            state = status
    return state


def opec_membership(day: date) -> str:
    """Angola's OPEC state: MEMBER, WITHDRAWAL_ANNOUNCED or NON_MEMBER.

    The announcement and the effect are eleven days apart and they are different events: the
    announcement is the information, the effective date is when the OPEC production table stops
    counting Angola and therefore starts measuring a different group of countries.
    """
    if day < OPEC_EXIT_ANNOUNCED:
        return "MEMBER"
    return "WITHDRAWAL_ANNOUNCED" if day < OPEC_EXIT_EFFECTIVE else "NON_MEMBER"


def pula_zar_beta() -> float:
    """The PUBLISHED rand weight of the pula basket. Not estimated -- published."""
    return float(PULA_BASKET["ZAR"])


def pula_crawl_rate(year: int) -> tuple[float | None, str]:
    """The announced rate of crawl for a year, with its status. None is UNMEASURED, not zero: a
    crawl rate this pack cannot cite is read off the Monetary Policy Statement before any cell
    conditions on it, and inventing a plausible number would be the worse error (L1.28a)."""
    return PULA_CRAWL.get(int(year), (None, "UNMEASURED: no Monetary Policy Statement read for "
                                            "this year"))


def diamond_cycle_window(year: int, cycle: int) -> tuple[date, date]:
    """The approximate window of one of the ten De Beers sales cycles in a year.

    EVENLY SPACED AND LABELLED APPROXIMATE. De Beers publishes the real calendar in advance and
    it is not evenly spaced; this is a scheduling scaffold for the collector, not a claim about
    a date. A cell named against a specific cycle must use the published calendar.
    """
    if not 1 <= int(cycle) <= DIAMOND_CYCLES_PER_YEAR:
        raise ValueError(f"cycle {cycle!r} is not one of 1..{DIAMOND_CYCLES_PER_YEAR}")
    start = date(year, 1, 1) + timedelta(days=(int(cycle) - 1) * 35)
    end = min(start + timedelta(days=34), date(year, 12, 31))
    return start, end


def diamond_cycle_index(day: date) -> int:
    """Which approximate sales cycle a date falls in, or 0 for the tail of the year that no
    evenly spaced cycle covers -- which is an honest 'between cycles' rather than a forced 10."""
    index = (day - date(day.year, 1, 1)).days // 35 + 1
    return index if index <= DIAMOND_CYCLES_PER_YEAR else 0


def lng_phase(day: date) -> str:
    """Mozambique's LNG supply phase: PRE_FORCE_MAJEURE, FORCE_MAJEURE_NO_PRODUCTION,
    CORAL_SOUTH_ONLY or FORCE_MAJEURE_LIFTED. It is a SUPPLY SCHEDULE, not a price."""
    if day < MZ_FORCE_MAJEURE:
        return "PRE_FORCE_MAJEURE"
    if day < MZ_CORAL_FIRST_CARGO:
        return "FORCE_MAJEURE_NO_PRODUCTION"
    return "CORAL_SOUTH_ONLY" if day < MZ_FORCE_MAJEURE_LIFTED else "FORCE_MAJEURE_LIFTED"


def orange_basin_phase(day: date) -> str:
    """Namibia's oil province phase: PRE_DISCOVERY, APPRAISAL or APPRAISAL_WITH_IMPAIRMENT.

    There is no PRODUCTION phase and there will not be one for years; saying so is the
    measurement, and it is why SA-O's fiscal and FX legs are tested before its price leg.
    """
    if day < NA_DISCOVERY:
        return "PRE_DISCOVERY"
    return "APPRAISAL" if day < NA_WRITEDOWN else "APPRAISAL_WITH_IMPAIRMENT"


def cma_parity(jurisdiction: str) -> str:
    """What a jurisdiction's currency arrangement is against the rand, by name.

    EXACT_1_1 for the Common Monetary Area members, PUBLISHED_BASKET_40_PCT_ZAR for Botswana --
    which is in SACU and NOT in the CMA -- and NONE for the other three. Getting this wrong
    invents a peg where there is none and misses one where there is.
    """
    code = str(jurisdiction).lower()
    if code in CMA_MEMBERS:
        return "EXACT_1_1"
    if code == "bw":
        return "PUBLISHED_BASKET_40_PCT_ZAR"
    return "NONE"


def is_exact_expression(jurisdiction: str) -> bool:
    """True when USDZAR is an EXACT expression of that jurisdiction's FX rather than a proxy.
    True for Namibia and for nothing else in this pack -- which is why SA-P is an identification
    strategy and every other currency row is labelled PROXY."""
    return cma_parity(jurisdiction) == "EXACT_1_1"


def jurisdiction_of_domain(domain_id: str) -> tuple[str, ...]:
    """Which of the five countries a domain belongs to. A regional domain names all five."""
    return DOMAIN_JURISDICTION.get(str(domain_id), JURISDICTIONS)


def cells() -> tuple[dict[str, Any], ...]:
    """THE TESTABLE CELLS THIS PACK MINTS: every domain crossed with its OWN instruments and its
    OWN named conditions, and nothing else.

    This is deliberately NOT a cartesian product of every domain against every executable
    instrument. A cell is only worth a trial if the pack's own data plane can evaluate its
    CONDITION on that SYMBOL, so the cross product is taken inside each domain, where the
    instruments were chosen for the mechanism and the conditions are states the pack's own
    series can resolve. That is the difference between maximising cells and maximising noise: a
    blown-up grid spends the program's shared family-wise error budget on cells nobody can fill,
    and every FX and metals cell on the desk pays for it (two-lane order, 2026-09-06).
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


def mine_beneficiation_orders(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """SA-A and SA-B: the gazetted and press-reported export controls as one dated clock."""
    rows = [{"kind": "hypothesis", "pack": CODE,
             "domain": "SA-B" if mineral == "lithium" else "SA-A",
             "jurisdiction": "zw", "at": day.isoformat(), "what": what, "status": status,
             "mineral": mineral,
             "symbols": ["XPTUSD", "XPDUSD"] if mineral == "pgm"
                        else ["XPTUSD", "XCUUSD", "USDZAR"],
             "family": "administered_price" if mineral == "pgm" else "policy_surprise",
             "control": "South African and Russian supply over the same months; the other "
                        "clauses commenced by the same instrument; matched non-event Fridays"}
            for day, mineral, what, status in BENEFICIATION_ORDERS]
    return {"miner": "sa_beneficiation_orders", "code": CODE, "at": _now(), "rows": rows,
            "emitted": _emit(ctx, rows),
            "unmeasured": ["three of the four PGM rows are PRESS_REPORTED and not gazetted; a "
                           "press-reported date is confirmed against the gazette before any cell "
                           "is promoted on it, and a deferral is not a commencement"]}


def mine_currency_regimes(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """SA-C and SA-E: six Zimbabwean currency eras as partitions, with the peg as the control."""
    rows = [{"kind": "hypothesis", "pack": CODE, "domain": "SA-C", "jurisdiction": "zw",
             "at": start.isoformat(), "what": f"currency regime boundary into {label}",
             "status": status, "era": label, "zig_state": zig_state(start),
             "symbols": ["XAUUSD", "USDZAR", "XPTUSD"], "family": "regime_break",
             "control": "the Namibian 1:1 peg as the zero-discretion control; Angola over the "
                        "same months; matched windows in the 2019 RTGS transition"}
            for start, label, status in CURRENCY_ERAS]
    rows.append({"kind": "hypothesis", "pack": CODE, "domain": "SA-E", "jurisdiction": "zw",
                 "at": ZIG_DEVALUATION.isoformat(),
                 "what": "the ZiG devaluation as a test of the published reserve cover, read "
                         "through the ZSE-versus-VFEX spread rather than through a price",
                 "status": "GAZETTED", "era": zim_currency_era(ZIG_DEVALUATION),
                 "symbols": ["XAUUSD", "USDZAR", "US500"], "family": "capital_flight",
                 "control": "the rand and the broad frontier equity tape; the gold price, "
                            "because the ZSE is gold-miner-weighted"})
    return {"miner": "sa_currency_regimes", "code": CODE, "at": _now(), "rows": rows,
            "emitted": _emit(ctx, rows),
            "unmeasured": ["Zimbabwe has NO continuous inflation series across these boundaries "
                           "and ZIMSTAT documents the breaks; the level across them is "
                           "UNMEASURED and is taken from the IMF Article IV or not at all"]}


def mine_gold_delivery_plane(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """SA-D: the gold-backed instruments and the delivery plane as official demand."""
    rows = [{"kind": "hypothesis", "pack": CODE, "domain": "SA-D", "jurisdiction": juris,
             "at": day.isoformat(), "what": what, "status": status,
             "era": zim_currency_era(day), "symbols": ["XAUUSD", "USDZAR"],
             "family": "official_demand",
             "control": "Ghana's and Tanzania's own domestic gold purchase programmes over the "
                        "same years; the gold price and the small-scale production trend; the "
                        "partner countries' mirror imports"}
            for day, juris, what, status in GOLD_POLICY_EVENTS]
    return {"miner": "sa_gold_delivery_plane", "code": CODE, "at": _now(), "rows": rows,
            "emitted": _emit(ctx, rows),
            "unmeasured": ["the ZiG's gold backing is published irregularly and the composition "
                           "is not always split out; an absent split is UNMEASURED, never a zero"]}


def mine_diamond_cycle(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """SA-F: ten dated luxury-demand prints a year, with the lab-grown confound named."""
    rows: list[dict[str, Any]] = []
    for year in HOLIDAYS_RULE["years"]:
        for cycle in range(1, DIAMOND_CYCLES_PER_YEAR + 1):
            start, end = diamond_cycle_window(year, cycle)
            rows.append({"kind": "hypothesis", "pack": CODE, "domain": "SA-F",
                         "jurisdiction": "bw", "at": end.isoformat(), "cycle": cycle,
                         "window": (start.isoformat(), end.isoformat()),
                         "what": "De Beers sales cycle revenue against its own trailing seasonal "
                                 "norm, as a dated read on global luxury demand",
                         "status": "APPROXIMATE_DERIVED",
                         "symbols": ["US500", "UK100", "USDZAR"], "family": "release_surprise",
                         "horizon": "0 to 10 sessions",
                         "control": "the lab-grown diamond share, which takes the low end and "
                                    "would produce the same revenue fall with no demand change; "
                                    "the broad index; matched non-release weekdays"})
    return {"miner": "sa_diamond_cycle", "code": CODE, "at": _now(), "rows": rows,
            "emitted": _emit(ctx, rows),
            "unmeasured": [DIAMOND_CYCLE_STATUS,
                           "the lab-grown share is a trade estimate rather than a published "
                           "statistic; the confound is named and its magnitude is UNMEASURED"]}


def mine_pula_basket(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """SA-G and SA-H: the published basket as the NULL, and the SACU transfer beside it."""
    rows: list[dict[str, Any]] = [
        {"kind": "hypothesis", "pack": CODE, "domain": "SA-G", "jurisdiction": "bw",
         "at": _now(), "what": "the residual between the observed pula fixing and a mechanical "
                               "replication of the PUBLISHED 60% SDR / 40% ZAR basket and crawl",
         "zar_weight": pula_zar_beta(), "symbols": ["USDZAR", "EURZAR", "GBPZAR", "ZARJPY"],
         "family": "carry_funding", "horizon": "1 to 8 weeks",
         "control": "the mechanical replication itself as the null; the Namibian 1:1 peg as the "
                    "zero-discretion extreme; the rand's own idiosyncratic moves"}]
    for year, (rate, status) in sorted(PULA_CRAWL.items()):
        rows.append({"kind": "hypothesis", "pack": CODE, "domain": "SA-G", "jurisdiction": "bw",
                     "at": date(year, 2, 1).isoformat(),
                     "what": f"the announced rate of crawl for {year}", "crawl_rate": rate,
                     "status": status, "symbols": ["USDZAR", "EURZAR"],
                     "family": "central_bank_surprise", "horizon": "1 to 8 weeks",
                     "control": "the prior year's crawl and the effective-rate indices"})
    rows.append({"kind": "hypothesis", "pack": CODE, "domain": "SA-H", "jurisdiction": "bw",
                 "at": _now(),
                 "what": "the SACU transfer as a two-year-lagged, formula-driven fiscal shock "
                         "out of South African import demand into two other budgets",
                 "symbols": ["USDZAR", "US500"], "family": "transfer", "horizon": "2 to 8 quarters",
                 "control": "South African import volumes as the pool's own driver; Lesotho's "
                            "and Eswatini's shares, which face the same formula with no diamonds "
                            "and no uranium"})
    return {"miner": "sa_pula_basket", "code": CODE, "at": _now(), "rows": rows,
            "emitted": _emit(ctx, rows),
            "unmeasured": [f"the rate of crawl is UNMEASURED for {y}" for y, (r, _s)
                           in sorted(PULA_CRAWL.items()) if r is None]}


def mine_energy_province(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """SA-I, SA-M and SA-O: three energy clocks, each the others' control."""
    family = {"mz": "capacity_ramp", "ao": "regime_break", "na": "capacity_ramp"}
    domain = {"mz": "SA-I", "ao": "SA-M", "na": "SA-O"}
    symbols = {"mz": ["XNGUSD", "XBRUSD"], "ao": ["XBRUSD", "XTIUSD"],
               "na": ["XBRUSD", "XTIUSD"]}
    rows = [{"kind": "hypothesis", "pack": CODE, "domain": domain[juris], "jurisdiction": juris,
             "at": day.isoformat(), "what": what, "status": status,
             "lng_phase": lng_phase(day) if juris == "mz" else None,
             "opec_state": opec_membership(day) if juris == "ao" else None,
             "basin_phase": orange_basin_phase(day) if juris == "na" else None,
             "symbols": symbols[juris], "family": family[juris],
             "control": "US Gulf Coast and Qatari LNG tranches for the Mozambican rows; Nigeria "
                        "and Congo-Brazzaville, which had the same quota dispute and did not "
                        "leave, for the Angolan rows; Guyanese and Brazilian pre-salt milestones "
                        "for the Namibian rows"}
            for day, juris, what, status in ENERGY_MILESTONES]
    return {"miner": "sa_energy_province", "code": CODE, "at": _now(), "rows": rows,
            "emitted": _emit(ctx, rows),
            "unmeasured": ["the Mozambique LNG restart schedule and the Orange Basin FID are "
                           "PROJECTED; a projected date may never arrive and no cell is promoted "
                           "on one",
                           "XNGUSD is Henry Hub and is NOT the price Mozambican cargoes realise; "
                           "the basis is UNMEASURED and is stated rather than assumed away"]}


def mine_corridor_and_water(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """SA-K, SA-J and SA-Q: five corridors for one orebody, and one reservoir for three metals."""
    rows: list[dict[str, Any]] = [
        {"kind": "hypothesis", "pack": CODE, "domain": "SA-K", "jurisdiction": "mz",
         "at": _now(),
         "what": "a month in which Beira or Nacala transit tonnage fell more than its own "
                 "interquartile range",
         "symbols": ["XCUUSD", "XZNUSD"], "family": "chokepoint", "horizon": "2 to 8 weeks",
         "needs_sibling_pack": "copperbelt",
         "control": "Durban, Dar es Salaam, Walvis Bay and Lobito throughput over the same "
                    "months: a fall here that appears as a rise there is a ROUTING event and "
                    "carries no supply information at all"},
        {"kind": "hypothesis", "pack": CODE, "domain": "SA-J", "jurisdiction": "mz",
         "at": _now(),
         "what": "a reported Mozal power interruption on the Cahora Bassa line",
         "symbols": ["XALUSD"], "family": "supply_shock", "horizon": "2 to 12 weeks",
         "control": "Chinese and Gulf smelter curtailments over the same months; Mozambican "
                    "aluminium export volumes, where the effect is large"},
        {"kind": "hypothesis", "pack": CODE, "domain": "SA-Q", "jurisdiction": "regional",
         "at": _now(),
         "what": "a Kariba lake level in the lowest bucket of its own historical distribution, "
                 "constraining Zimbabwean PGM, Zambian copper and Mozambican aluminium smelting "
                 "at once",
         "symbols": ["XPTUSD", "XCUUSD", "XALUSD"], "family": "supply_shock",
         "horizon": "4 to 26 weeks", "needs_sibling_pack": "copperbelt",
         "control": "matched seasons with a high lake level, which separates 'dry season' from "
                    "'water shortage'; global supply of each metal; Eskom availability, which is "
                    "the import fallback"}]
    return {"miner": "sa_corridor_and_water", "code": CODE, "at": _now(), "rows": rows,
            "emitted": _emit(ctx, rows),
            "unmeasured": ["corridor throughput is published irregularly and the Kariba archive "
                           "is incomplete; a missing month or week is UNMEASURED and this miner "
                           "refuses to interpolate a corridor or a reservoir"]}


def mine_calendar_plane(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """SA-R: five calendars, three substitution regimes and the Mondays a one-rule study loses."""
    rows: list[dict[str, Any]] = []
    for year in HOLIDAYS_RULE["years"]:
        tables = {code: fn(year) for code, fn in JURISDICTION_HOLIDAY_FN.items()}
        substituted = substituted_mondays(year)
        for day in sorted(set().union(*(set(t) for t in tables.values()))):
            if day.weekday() >= 5:
                continue
            closed = tuple(sorted(c for c, tbl in tables.items() if day in tbl))
            rows.append({"kind": "hypothesis", "pack": CODE, "domain": "SA-R",
                         "at": day.isoformat(), "closed": closed,
                         "regional": len(closed) == len(JURISDICTIONS),
                         "substituted_in": substituted.get(day, ()),
                         "what": "a closure day in one or more of the five, with the "
                                 "substitution regime that produced it",
                         "symbols": ["USDZAR", "EURZAR", "XPTUSD", "XAUUSD"],
                         "family": "holiday_liquidity", "horizon": "0 to 2 sessions",
                         "control": "the matched weekday twenty-six weeks away; days on which "
                                    "only ONE of the five closed; South African closures, which "
                                    "dominate rand liquidity"})
    return {"miner": "sa_calendar_plane", "code": CODE, "at": _now(), "rows": rows,
            "emitted": _emit(ctx, rows),
            "unmeasured": ["Angola's midweek 'ponte' bridge practice is NOT derived here because "
                           "this pack cannot cite the operative article; those days are "
                           "UNMEASURED rather than guessed"]}


def mine_transmission_seeds(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """The pack's own transmission map, as HYPOTHESIS discoveries the registry deduplicates."""
    rows = [{"kind": "hypothesis", "pack": CODE, "domain": "transmission", "at": _now(),
             "edge": str(seed["id"]), "what": str(seed["mechanism"]),
             "symbols": list(seed["targets"]), "family": "transfer",
             "horizon": str(seed["horizon"]), "evidence": str(seed["evidence"]),
             "control": str(seed["control"]), "falsifier": str(seed["falsifier"])}
            for seed in TRANSMISSION_EDGES_SEED]
    return {"miner": "sa_transmission_seeds", "code": CODE, "at": _now(), "rows": rows,
            "emitted": _emit(ctx, rows), "unmeasured": []}


MINERS: dict[str, Any] = {
    "mine_beneficiation_orders": mine_beneficiation_orders,
    "mine_currency_regimes": mine_currency_regimes,
    "mine_gold_delivery_plane": mine_gold_delivery_plane,
    "mine_diamond_cycle": mine_diamond_cycle,
    "mine_pula_basket": mine_pula_basket,
    "mine_energy_province": mine_energy_province,
    "mine_corridor_and_water": mine_corridor_and_water,
    "mine_calendar_plane": mine_calendar_plane,
    "mine_transmission_seeds": mine_transmission_seeds,
}


def mine(ctx: Any = None) -> dict[str, Any]:
    """THE DEPARTMENT ENTRY. Pure Python, no network, no LLM and no heavy import.

    It runs the pack's own nine miners over the pack's own tables, emits through the department
    Ctx when one is given, and returns a plain report when one is not -- which is how a test
    calls it and how a fresh session checks the pack with nothing wired.
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
    """The pack as a plain mapping: the framework fields plus everything the framework has no
    slot for, carried beside them so nothing is silently dropped."""
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
        "mission": MISSION, "currency_eras": CURRENCY_ERAS,
        "beneficiation_orders": BENEFICIATION_ORDERS, "energy_milestones": ENERGY_MILESTONES,
        "pula_basket": PULA_BASKET, "pula_crawl": PULA_CRAWL,
        "cma_members": CMA_MEMBERS, "sacu_members": SACU_MEMBERS,
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
    """The framework's HolidayRule shape: every closed weekday the five calendars produce."""
    dates = sorted({d.isoformat() for y in HOLIDAYS_RULE["years"] for d in market_holidays(y)})
    fixed = sorted({f"{m:02d}-{d:02d}"
                    for rows in (FIXED_ZW, FIXED_BW, FIXED_MZ, FIXED_AO, FIXED_NA)
                    for m, d, _ in rows})
    return {"dates": tuple(dates), "fixed_md": tuple(fixed), "weekly_closed": (5, 6),
            "notes": HOLIDAYS_RULE["authority"]}


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









