"""SAHEL COAST -- Niger's uranium and crude, Liberia's flag, the Sahel's ports, and the coastal
margin: NE, TG, BJ, SL, LR, GM, GW, CV.

WHY EIGHT JURISDICTIONS IN ONE PACK, AND WHY THESE EIGHT. They are the COMPLEMENT of
`west_africa` (ci, gn, ml, bf, sn), which owns the BCEAO's monetary seat, the cocoa complex and
the Sahel gold of Mali and Burkina. What is left over is not a remainder: it is one physical
system with four mechanisms nothing else on the desk's roster carries. Niger's uranium and its
new crude line leave through Benin and Togo; the landlocked Sahel's entire import bill crosses
the quays at Lome and Cotonou; Liberia's registry is the flag on a sixth of world deadweight
tonnage; and the small coastal states are the mineral and fishery margin of the same coast.

THE FOUR MECHANISMS THAT EARN THE TRIAL BUDGET. Each is published, dated and price-relevant, and
each is a domain of its own rather than a sentence inside a generic frontier domain:

  1. NIGER IS A TOP-SEVEN WORLD URANIUM PRODUCER AND A MUCH LARGER SHARE OF EUROPEAN REACTOR
     FUEL. Somair and Cominak at Arlit have run since the 1970s; Niger has been roughly 4-5% of
     world mine supply and, in several years, a fifth to a quarter of the natural uranium
     delivered to EU utilities as reported by the Euratom Supply Agency. The COUP OF 2023-07-26
     was followed by dated, published consequences: ECOWAS sanctions and border closures from
     2023-07-30, the withdrawal of Orano's Imouraren operating permit in June 2024, the loss of
     operational control and then the announced nationalisation of Somair, and Niger's exit from
     ECOWAS with Mali and Burkina announced 2024-01-28 and effective 2025-01-29. URANIUM IS NOT A
     BROKER SYMBOL and this pack never pretends it is: the transmission is routed EXPLICITLY
     through European and French nuclear generation into power and gas substitution (XNGUSD,
     FRA40, EUSTX50, GER40) with the control named, and the uranium spot price is a REPORTED
     ASSESSMENT by a price-reporting agency, not a Fusion instrument.
  2. NIGER ALSO EXPORTS CRUDE THROUGH BENIN NOW. The Agadem-Seme line -- about 1,980 km and a
     nameplate near 90,000 b/d -- loaded its first export cargo in May 2024, and its
     commissioning was interrupted on dated, published days by the Niger-Benin border dispute.
     A new supply line of that size switching on and off for political reasons is a physical
     event on XBRUSD with a published on/off clock, which is rare.
  3. LIBERIA IS THE WORLD'S SECOND-LARGEST SHIP REGISTRY. Roughly 15-16% of world deadweight
     tonnage flies the Liberian flag, and on GROSS TONNAGE the registry passed Panama on some
     published measures in 2022-2024. The registry publishes its own size and composition. A
     flag state's register is a lawful, published window onto world merchant-fleet growth and
     onto where sanctioned or grey-fleet tonnage re-flags -- which is tanker CAPACITY and
     therefore crude freight. Liberia is also a significant iron-ore exporter through the Yekepa
     concession and the Buchanan rail, and a rubber producer.
  4. TOGO AND BENIN ARE THE SAHEL'S PORTS AND THE REGION'S COTTON AND CASHEW BELT. Lome is the
     deepest container port on the West African coast and the transit route for Burkina and
     Niger; Cotonou is Niger's outlet and the terminus of the crude line. Both publish
     throughput. Benin is a top-three world cashew exporter and both are significant COTTON
     producers whose ginning campaigns run on a dated, published calendar, and Benin's GDIZ
     industrial zone shifted cashew and cotton from raw export to domestic processing on a
     published policy timetable.

AND THE MARGIN, WHICH IS WHERE THE CONTROLS LIVE. Sierra Leone is a top world producer of RUTILE
(titanium feedstock) and ilmenite and a Kimberley Process diamond reporter; Guinea-Bissau is
overwhelmingly a CASHEW monocrop whose single annual campaign price is set by decree on a dated
day; The Gambia and Cabo Verde are fishery, remittance and tourism economies. Sierra Leone
REDENOMINATED its leone 1000:1 on 2022-07-01, which is a dated break no pooled series may cross.

THREE EXCHANGE-RATE REGIMES INSIDE ONE PACK. Four of the eight use the XOF at 655.957 to the
euro under the same guarantee `west_africa` documents; CABO VERDE'S ESCUDO IS PEGGED TO THE EURO
AT 110.265 under a formal Exchange Cooperation Agreement with Portugal, which makes it a clean
THIRD control beside the XOF peg; and The Gambia, Sierra Leone and Liberia float. None of the
six currencies is quoted by this broker. EURUSD is the EXACT expression of the two euro pegs --
not a proxy -- and the three floaters are proxied with their controls named on the face of every
edge that uses one.

THE NATIVE GROUND IS FOUR LANGUAGES DEEP AND A FRENCH-AND-ENGLISH CRAWL READS NEITHER BISSAU NOR
THE NIGERIEN INTERIOR. French is the administrative language of Niger, Togo and Benin; PORTUGUESE
is the language of Guinea-Bissau and Cabo Verde and of their Boletins Oficiais, with Crioulo the
spoken ground; HAUSA and ZARMA are the languages the Nigerien interior actually trades and argues
in, and a Hausa query reaches a market report a French one never sees; Sierra Leone works in
English and KRIO, Liberia in Liberian English; Togo adds Ewe and Kabiye, Benin adds Fon and
Yoruba, The Gambia adds Mandinka and Wolof. The terminology table and every source class's
queries are written in those languages for exactly that reason.

THE TWO-LANE ORDER (2026-09-06) BINDS HARD HERE. The tempting names are all single companies --
the uranium operator, the registry administrator, the iron-ore concessionaire, the rutile miner,
the rubber concession, the terminal operators. Every one appears in this pack as an ACTOR and
never as an instrument. No share CFD appears in any instrument tuple in this file, and no
crypto-exchange ground is hunted (mandate 2026-08-18).
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Any

# --------------------------------------------------------------------------- identity
CODE = "sahel_coast"
NAME = "The Sahel interior and the West African coast"
REGION_COMMAND = "africa"
REGION_DESK = "AFRICA"
FOREST = "africa"

#: THE EIGHT COUNTRIES THIS PACK ANSWERS FOR. `scripts/check_regional_parity.py::jurisdictions_of`
#: reads this tuple and nothing else, so a pack that answers eight countries and declares one is
#: credited with one. None of the eight was on any forest's roster before this pack; the pack
#: does NOT edit `libs/research/forests.py` (nine builders share that file today) and asks the
#: coordinator to register `sahel_coast` on the AFRICA forest with these eight codes.
JURISDICTIONS: tuple[str, ...] = ("ne", "tg", "bj", "sl", "lr", "gm", "gw", "cv")

#: The pack-level currency is the one the PLURALITY share and the framework carries ONE per pack.
#: FOUR of the eight are WAEMU members using the XOF -- Niger, Togo, Benin and Guinea-Bissau --
#: and the other four WAEMU states (CI, ML, BF, SN) belong to `west_africa`, which is why a
#: reader counting "five CFA members here" is counting Senegal twice. Four is the measured
#: number and the pack says four (L1.28a).
CURRENCY = "XOF"
CURRENCIES: dict[str, str] = {
    "ne": "XOF",   # West African CFA franc -- hard euro peg at 655.957, French Treasury guarantee
    "tg": "XOF",   # the same currency, the same peg, a different treasury
    "bj": "XOF",   # the same again; BJ, TG and NE are one monetary area with three budgets
    "gw": "XOF",   # Guinea-Bissau joined WAEMU on 1997-05-02 and abandoned the Bissau-Guinean peso
    "sl": "SLE",   # Sierra Leonean leone -- FLOAT, REDENOMINATED 1000:1 on 2022-07-01 (SLL -> SLE)
    "lr": "LRD",   # Liberian dollar -- float, in a DUAL-CURRENCY economy with the US dollar
    "gm": "GMD",   # Gambian dalasi -- the cleanest managed float of the three
    "cv": "CVE",   # Cabo Verdean escudo -- pegged to the EURO at 110.265 by agreement with Portugal
}

#: All eight run a CALENDAR fiscal year, which is unusual enough in Africa to be worth the line:
#: the four WAEMU members run it under the UEMOA convergence framework, and LIBERIA MOVED TO IT,
#: from a 1 July - 30 June year to a calendar year, with a transitional six-month budget covering
#: July to December 2021. A Liberian fiscal series pooled across that transition is pooling a
#: six-month budget with twelve-month ones.
FISCAL_YEAR_END = "12-31"
FISCAL_YEAR_ENDS: dict[str, str] = {
    "ne": "12-31 (UEMOA convergence framework; the budget law is voted in December)",
    "tg": "12-31 (loi de finances voted in December for a 1 January start)",
    "bj": "12-31 (loi de finances voted in December for a 1 January start)",
    "gw": "12-31 (UEMOA framework; execution is routinely disrupted by arrears)",
    "sl": "12-31 (the Finance Act is passed in November-December)",
    "lr": "12-31 SINCE FY2022; before that 07-01 to 06-30, with a TRANSITIONAL six-month budget "
          "for July-December 2021 that no annual series may treat as a year",
    "gm": "12-31 (the Appropriation Act is passed in December)",
    "cv": "12-31 (Orcamento do Estado approved in December)",
}

NATIVE_LANGUAGES: tuple[str, ...] = (
    "fr", "pt", "en", "ha", "dje", "ee", "kbp", "fon", "yo", "kri", "mnk", "wo", "kea", "pov")
COT_CURRENCY = ""            # no CFTC contract exists for XOF, SLE, LRD, GMD, CVE or GNF
EXPORT_ECONOMY = "commodity_exporter"
RETAIL_LEVERAGE_REGIME = "absent"
MISSION = ("mine the Sahel interior and the West African coast as `west_africa`'s complement: "
           "Niger's uranium at Arlit and the European reactor fuel it feeds, the Agadem-Seme "
           "crude line switching on and off with the Benin border dispute, the ECOWAS/AES "
           "rupture as a dated trade-bloc break, Liberia's flag registry as a published window "
           "onto world tanker tonnage and its Yekepa iron ore, Lome and Cotonou as the Sahel's "
           "quays, the Benin and Togo cotton ginning campaigns and the GDIZ processing mandate, "
           "Sierra Leone's rutile and its 2022 redenomination, Guinea-Bissau's decreed cashew "
           "price, Cabo Verde's 110.265 euro peg as a third monetary control, the Gulf of Guinea "
           "piracy plane, the EU and Chinese fishery licences, and the Sahel rainfall and "
           "Harmattan cycle as the shared agronomic clock")

#: The instruments this pack may compile a cell against. Every one is in the broker registry,
#: none is a single-name equity, and each carries the mechanism that put it here.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "XAUUSD",                         # Sahel artisanal gold, the reserve leg and the risk carrier
    "COTTON",                         # Benin and Togo lint: a real, executable ginning campaign
    "UKCOCOA", "USCOCOA",             # Togolese and Nigerian cocoa re-exported through Lome
    "COFROB",                         # the robusta the same corridor and the same ports carry
    "SUGAR",                          # the Sahel import bill and the Nigerian border trade
    "CORN", "WHEAT", "SOYBEAN",       # the cereal import bill, the rains, and the oilseed complex
    "XBRUSD", "XTIUSD",               # the Agadem line, Gulf of Guinea freight and bunkering
    "XNGUSD",                         # THE URANIUM ROUTE: European nuclear-for-gas substitution
    "XALUSD", "XCUUSD", "XZNUSD",     # the mineral-sands, bauxite and seaborne-ore complex
    "EURUSD",                         # the EXACT expression of the XOF and CVE euro pegs
    "FRA40", "EUSTX50", "GER40",      # French and European nuclear generation and utilities
    "UK100",                          # the London-listed mining and shipping complex
    "USDZAR",                         # the liquid African risk carrier for six absent currencies
    "USDCNH",                         # China as the marginal buyer of ore, cashew and fish
)

#: WHAT THIS PACK CANNOT TRADE, NAMED. Six currencies, one commodity with no contract anywhere,
#: and five physical goods that are real, large and unquoted. Each row carries the broker symbols
#: its economics route into; a proxy is a CARRIER and never a substitute, and every edge that uses
#: one says so on its face. Where the honest answer is "nothing adequate", the row says that too.
TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "XOF -- the West African CFA franc of Niger, Togo, Benin and Guinea-Bissau",
     "venue": "BCEAO, Dakar, for eight member states; there is no independent national rate",
     "regime": "HARD PEG to the euro at 655.957 XOF = 1 EUR, unchanged since the euro replaced "
               "the French franc on 1999-01-01 and derived from the 1994-01-12 devaluation that "
               "set 100 XOF = 1 FRF; convertibility is guaranteed by the French Treasury through "
               "an operations account, and reserve-pooling and the guarantee survived the 2019 "
               "reform that renamed the currency and ended the centralisation of reserves",
     "parallel_market": "NONE WORTH READING inside the zone: the peg is hard and convertibility "
                        "is guaranteed, so the informative spread is at the NIGERIA BORDER, "
                        "where XOF/NGN is a street rate and the 2023-2024 naira devaluations "
                        "moved it violently",
     "route": "EXACT, NOT PROXIED. A hard peg to the euro makes EURUSD the exact dollar "
              "expression of every XOF price; a Nigerien or Beninese dollar receipt is a EURUSD "
              "position with a commodity attached, and that is the only currency claim this pack "
              "makes about four of its eight countries",
     "why": "absent from the broker registry and it does not matter: the peg means the exposure "
            "is EURUSD and the pack states the identity rather than inventing a carrier",
     "proxies": ("EURUSD", "USDZAR")},
    {"name": "CVE -- the Cabo Verdean escudo, pegged to the euro at 110.265",
     "venue": "Banco de Cabo Verde; the rate is administered, not traded",
     "regime": "HARD PEG at 110.265 CVE = 1 EUR under the Acordo de Cooperacao Cambial with "
               "PORTUGAL, signed in 1998 and carried over from the escudo peg when the euro "
               "arrived; Portugal maintains a credit facility behind it",
     "parallel_market": "none: the peg holds and the economy is small, tourism-funded and "
                        "euro-invoiced in practice",
     "route": "EXACT, like the XOF, and that is the point of carrying it. CVE and XOF are TWO "
              "INDEPENDENT hard euro pegs with DIFFERENT guarantors -- the French Treasury and "
              "the Banco de Portugal -- which makes them each other's control on any claim that "
              "a peg itself, rather than a guarantor, is doing the work",
     "why": "absent from the broker registry; the exposure is EURUSD by construction",
     "proxies": ("EURUSD", "UK100")},
    {"name": "SLE -- the Sierra Leonean leone, REDENOMINATED 1000:1 on 2022-07-01",
     "venue": "Bank of Sierra Leone FX auctions and the commercial-bank market",
     "regime": "FLOAT with heavy depreciation; the redenomination of 2022-07-01 dropped three "
               "zeroes and changed the ISO code from SLL to SLE, with a dual-circulation period "
               "through the second half of 2022",
     "parallel_market": "a visible bureau and street market; the gap to the auction rate is the "
                        "published stress observable and it widened through 2022-2023",
     "route": "the leone is an IMPORT-COST state for a country that imports its rice and its "
              "fuel; it reaches price through the mineral export side (rutile, ilmenite, bauxite "
              "and diamonds) and through the risk carrier, never as a quote",
     "why": "absent from the broker; ANY series crossing 2022-07-01 is a 1000x step that is not "
            "a price move, and SC-O exists to stop a pooled study reading one as the other",
     "proxies": ("XAUUSD", "USDZAR", "XZNUSD")},
    {"name": "LRD -- the Liberian dollar in a dual-currency economy",
     "venue": "Central Bank of Liberia; the US dollar circulates as legal tender beside it",
     "regime": "FLOAT, but the economy is partially DOLLARISED -- a large share of deposits, "
               "wages and prices are quoted in USD, so the LRD/USD rate prices only the domestic "
               "half of the economy and the CBL publishes both legs",
     "parallel_market": "the bureau rate and the bank rate diverge episodically; both are "
                        "published, which makes the spread readable rather than inferred",
     "route": "dollarisation is why Liberia is the ODD FLOATER of the three: an LRD move changes "
              "less of the real economy than a dalasi or leone move does, which makes Liberia "
              "the control that separates 'a currency fell' from 'an economy tightened'",
     "why": "absent from the broker; the executable legs are the ore complex and crude freight",
     "proxies": ("XCUUSD", "XBRUSD", "USDZAR")},
    {"name": "GMD -- the Gambian dalasi",
     "venue": "Central Bank of The Gambia; a thin interbank market and licensed bureaux",
     "regime": "MANAGED FLOAT in a remittance-and-tourism economy; remittances are a very large "
               "share of GDP and the CBG publishes them monthly, which makes the dalasi one of "
               "the few African currencies with a published high-frequency INFLOW series",
     "parallel_market": "bureau rates are published and the spread is small in normal seasons "
                        "and widens in the pre-Tobaski import season",
     "route": "the dalasi is a REMITTANCE-SEASON instrument: its stress is seasonal, not "
              "monetary, and the seasonality is the testable part",
     "why": "absent from the broker; the transmission runs through the groundnut and oilseed "
            "complex and through the euro leg the remittances arrive in",
     "proxies": ("SOYBEAN", "EURUSD", "USDZAR")},
    {"name": "GNF-adjacent exposure -- the Guinean franc at the Sierra Leone and Bissau borders",
     "venue": "Guinea's own market, which belongs to the `west_africa` pack",
     "regime": "MANAGED FLOAT; named here only because the SL and GW border trade prices in it "
               "and a bauxite or diamond flow that crosses at Pamelap is measured in GNF",
     "parallel_market": "the border street rate is the operative one for the cross-border trade",
     "route": "DEFERRED TO `west_africa` BY DESIGN. This pack names the exposure so it is not "
              "lost and does not model it: an edge whose currency belongs to another pack is "
              "that pack's edge, and duplicating it spends the same trial budget twice",
     "why": "absent from the broker, and out of this pack's scope by the sibling-pack boundary",
     "proxies": ("XALUSD", "XAUUSD")},
    {"name": "URANIUM -- the single most important price in this pack and it is NOT AN INSTRUMENT",
     "venue": "there is no exchange tape a retail broker quotes; the reference is a REPORTED "
              "ASSESSMENT published by price-reporting agencies (the U3O8 spot and long-term "
              "assessments) alongside the Euratom Supply Agency's own average contract prices",
     "regime": "a term-contract market: most volume moves under multi-year utility contracts, so "
               "the spot assessment is a THIN residual and a spot move is not a revenue move for "
               "a producer whose output is already contracted",
     "parallel_market": "n/a; the opacity is the term-contract structure, not an illegal market",
     "route": "EXPLICIT AND STATED WEAK. Nigerien supply reaches a broker symbol only through "
              "EUROPEAN NUCLEAR GENERATION: a fuel-supply scare raises the perceived cost or "
              "risk of the nuclear leg of the French and German-adjacent grids, which is priced "
              "in POWER and therefore in gas substitution (XNGUSD) and in the utility-heavy "
              "European indices (FRA40, EUSTX50, GER40). Inventories at utilities are measured "
              "in YEARS, so the pack predicts a small, slow and possibly absent effect and says "
              "so BEFORE the test rather than after it",
     "why": "no uranium contract exists in data/universe/universe.json and none ever will for a "
            "retail CFD book; a pack that quietly proxied it with XALUSD would be inventing a "
            "series",
     "proxies": ("XNGUSD", "FRA40", "EUSTX50", "GER40")},
    {"name": "IRON ORE and the seaborne bulk trade out of Buchanan",
     "venue": "the seaborne iron-ore market; the published references are the 62% Fe index "
              "assessments and the Singapore-cleared swap, neither of which this broker quotes",
     "regime": "an index-linked physical market dominated by four exporters; Liberia is a small "
               "but growing supplier whose expansion has a published timetable",
     "parallel_market": "n/a",
     "route": "WEAK AND NAMED WEAK. Liberian tonnage is small against Australia and Brazil, so "
              "the honest transmission is not the ore price: it is the FREIGHT leg (Capesize "
              "tonne-miles out of the Gulf of Guinea) and the industrial-metals complex beta "
              "(XCUUSD, XZNUSD) plus the London-listed mining and shipping index",
     "why": "no iron-ore contract exists in the broker registry",
     "proxies": ("XCUUSD", "XZNUSD", "UK100")},
    {"name": "RUTILE, ILMENITE and the titanium feedstock chain",
     "venue": "mineral-sands contracts are negotiated bilaterally against price-reporting-agency "
              "assessments; there is no exchange",
     "regime": "a concentrated producer base and a pigment-producer buyer base; Sierra Leone is a "
               "top world producer of NATURAL rutile, which is the highest-grade feedstock",
     "parallel_market": "n/a; the assessments are licensed and forbid machine extraction",
     "route": "WEAK AND NAMED WEAK. The buyers are pigment and titanium-metal producers, and "
              "every one of them is a SINGLE NAME this desk may not hunt (two-lane order). What "
              "is left is the European chemical-and-industrial index leg and the industrial "
              "metals complex, and the pack expects little",
     "why": "no mineral-sands contract exists anywhere in the broker registry",
     "proxies": ("EUSTX50", "GER40", "XZNUSD")},
    {"name": "CASHEW (raw cashew nut) -- Benin, Guinea-Bissau, and the decreed campaign price",
     "venue": "the Guinea-Bissau campanha de comercializacao at a DECREED reference price; the "
              "Beninese and Togolese campaigns under their own interprofessions",
     "regime": "an annual single-campaign market: the government of Guinea-Bissau fixes a "
               "reference farmgate price by decree before the campaign opens, and the buyers are "
               "Indian and Vietnamese processors",
     "parallel_market": "cross-border leakage into Senegal and Guinea when the decreed price is "
                        "below the neighbouring one -- reported, not measured",
     "route": "NOTHING ADEQUATE ON THE PRICE. There is no cashew contract anywhere. What IS "
              "testable is the MACRO consequence: cashew is roughly nine tenths of Guinea-Bissau's "
              "export earnings, so the campaign price sets the country's grain-import capacity, "
              "which reaches WHEAT and CORN at the margin and USDCNH through the Asian buyer",
     "why": "no cashew contract exists in the broker registry and the pack refuses to proxy a "
            "tree nut with a grain futures price as if they were the same crop",
     "proxies": ("WHEAT", "CORN", "USDCNH")},
    {"name": "NATURAL RUBBER -- the Firestone/Harbel concession and the Liberian smallholders",
     "venue": "the Singapore and Tokyo rubber contracts, neither of which this broker quotes",
     "regime": "a plantation crop with a long replanting cycle; Liberia's output is small on a "
               "world scale and its history is dominated by one concession",
     "parallel_market": "n/a",
     "route": "WEAK. Natural rubber substitutes against SYNTHETIC rubber, whose feedstock is "
              "butadiene from the naphtha chain, so the honest carrier is the crude complex, and "
              "China is the marginal buyer of both",
     "why": "no rubber contract exists in the broker registry",
     "proxies": ("XBRUSD", "USDCNH")},
    {"name": "REGISTRY TONNAGE -- the Liberian flag's own published statistics",
     "venue": "the Liberian International Ship and Corporate Registry's published fleet figures "
              "and the UNCTAD and IMO aggregates that cite them",
     "regime": "an OPEN registry competing with Panama and the Marshall Islands; a shipowner may "
               "re-flag in weeks, which is what makes the series informative about intent",
     "parallel_market": "n/a -- the interesting variable is the OTHER registries' tonnage, "
                        "because re-flagging is a zero-sum move between them",
     "route": "a QUANTITY series, never a price. Deadweight tonnage under a flag is a capacity "
              "and composition reading: growth in tanker DWT on an open register is future "
              "freight supply, and a surge in older tanker tonnage moving onto a register is the "
              "published footprint of grey-fleet formation. It conditions XBRUSD and XTIUSD "
              "through freight and never quotes them",
     "why": "tonnage is not an instrument; it is an observable, and this pack uses it as one",
     "proxies": ("XBRUSD", "XTIUSD", "UK100")},
    {"name": "The BRVM and the WAEMU regional bond market",
     "venue": "Bourse Regionale des Valeurs Mobilieres, Abidjan; UMOA-Titres for the sovereign "
              "auctions",
     "regime": "ONE regional exchange for all eight WAEMU states, so Niger, Togo, Benin and "
               "Guinea-Bissau have no national tape of their own; the sovereign auctions ARE "
               "national and are published per issuer by UMOA-Titres",
     "parallel_market": "n/a",
     "route": "DEFERRED TO `west_africa` FOR THE EQUITY TAPE, which is its object; this pack "
              "reads the UMOA-Titres AUCTION leg, because a failed or expensive Nigerien or "
              "Bissau-Guinean bill auction is a fiscal-stress observable that belongs here",
     "why": "no BRVM index or BRVM security is in the broker registry",
     "proxies": ("EURUSD", "USDZAR")},
    {"name": "Domestic equity markets of SL, LR, GM, GW and CV",
     "venue": "Bolsa de Valores de Cabo Verde (Praia) is the ONLY one that exists; Sierra Leone, "
              "Liberia, The Gambia and Guinea-Bissau have no securities exchange at all",
     "regime": "the BVC lists a small number of bonds and a handful of equities with very thin "
               "turnover; the others have none",
     "parallel_market": "n/a",
     "route": "registered as a STATE and never as a price; the BVC's existence is what stops the "
              "institutional layer being declared absent for Cabo Verde, and the other four are "
              "declared absent BY NAME in NO_LAWFUL_GROUND",
     "why": "absent from the broker registry",
     "proxies": ("EURUSD", "UK100")},
)

# --------------------------------------------------------------------------- central banks
#: THE PACK CARRIES ONE `CENTRAL_BANK` BECAUSE THE FRAMEWORK DOES, AND FIVE IS THE TRUTH. The
#: BCEAO is the primary because it issues the currency of four of the eight and because its peg
#: is the one monetary fact in this pack that is not in question. The other four are declared
#: beside it in `CENTRAL_BANKS`, and a study that pools the five is pooling two hard euro pegs
#: with three floats, one of which redenominated in the middle of the sample.
CENTRAL_BANK: dict[str, Any] = {
    "name": "Banque Centrale des Etats de l'Afrique de l'Ouest (BCEAO)",
    "framework": "hard_peg",
    "policy_instrument": "the taux d'interet minimum de soumission aux appels d'offres (the "
                         "weekly tender's minimum bid rate) and the marginal lending window, set "
                         "for all eight member states at once by a single Monetary Policy "
                         "Committee -- so NIGER, TOGO, BENIN AND GUINEA-BISSAU HAVE NO NATIONAL "
                         "MONETARY POLICY AT ALL, which is the most important single fact about "
                         "four of this pack's eight jurisdictions",
    "mandate": "price stability with the fixed parity to the euro as the anchor, under the WAEMU "
               "treaty; the French Treasury guarantees convertibility through an operations "
               "account, and the 2019 reform ended the obligation to centralise reserves there "
               "and removed the French representative from the governance bodies WITHOUT "
               "touching the parity or the guarantee",
    "decision_rule": "the Comite de Politique Monetaire meets QUARTERLY on a published calendar, "
                     "in principle on the first Wednesday of March, June, September and December, "
                     "and the communique is published the same day",
    "decision_calendar_rule": "quarterly CPM meetings announced at bceao.int; the schedule is "
                              "published a year ahead and slips occasionally, so the pack carries "
                              "the RULE and refuses to type dates it has not cited",
    "decision_dates": (),
    "dates_status": "NOT LISTED, deliberately. The CPM calendar is published but this pack has "
                    "not cited a specific year's dates from the primary source, and typing a "
                    "plausible first-Wednesday table would be a rule masquerading as a citation "
                    "(L1.28a). The dated events the domains are built on -- the coup, the "
                    "sanctions, the permit withdrawals, the pipeline loadings, the "
                    "redenomination, the ECOWAS exit -- are all citable.",
    "decision_time_utc": "14:00",
    "announce_local": "Dakar and all four WAEMU members in this pack are UTC+0 year-round with "
                      "NO daylight saving; Sierra Leone, Liberia, The Gambia and Guinea-Bissau "
                      "are UTC+0 too, and CABO VERDE ALONE IS UTC-1. Seven of the eight sit on "
                      "GMT, which makes every session window in this pack stable in UTC",
    "dst_rule": "none anywhere in the eight",
    "minutes_lag_days": 0,
    "publication_classes": ("cpm_communique", "rapport_politique_monetaire", "bulletin_mensuel",
                            "balance_des_paiements", "annuaire_statistique", "umoa_titres_auction"),
    "policy_rate_series": "BCEAO:taux_minimum_soumission",
    "expected_rate_series": "UNMEASURED",
    "consensus_proxy": "the UMOA-Titres weekly bill and bond auction cut-offs by issuer, which "
                       "are published per country and are the only national-level rate signal "
                       "four of these eight produce",
    "consensus_proxy_trap": "the auction is REGIONAL in its buyer base: a Nigerien bill is bought "
                            "mostly by Ivorian and Senegalese banks, so a cut-off move can be a "
                            "regional liquidity event rather than a Nigerien fiscal one, and the "
                            "cross-issuer spread is the part that is national",
    "reserves_clock": "the WAEMU reserve position is published for the UNION and not per country; "
                      "a national reserve number for Niger, Togo, Benin or Guinea-Bissau DOES "
                      "NOT EXIST, and the IMF Article IV is the only country-level substitute",
    "programme": "IMF programmes run country by country inside the union: Benin and Senegal have "
                 "had large Extended Fund Facility arrangements, Niger's was disrupted by the "
                 "2023 coup and the sanctions, and Guinea-Bissau runs a small ECF",
    "off_cycle": ("1994-01-12 the 50% devaluation that set 100 XOF = 1 FRF, the only parity "
                  "change in the zone's history",
                  "2019-12-21 the Eco reform announcement: the name, the reserve centralisation "
                  "and the governance changed and the PARITY did not"),
    "root": "https://www.bceao.int",
}

#: The other four, declared rather than folded away. Two of them are the pack's own controls.
CENTRAL_BANKS: dict[str, dict[str, Any]] = {
    "ne": {"name": "BCEAO Agence Nationale du Niger (Niamey)", "framework": "hard_peg",
           "rate": "none of its own: the BCEAO's regional rate applies",
           "root": "https://www.bceao.int",
           "why": "Niger has NO national monetary instrument. Its only national financial lever "
                  "is the budget and the UMOA-Titres auction, which is why the 2023 sanctions "
                  "bit through the AUCTION and the payments system rather than through a rate"},
    "tg": {"name": "BCEAO Agence Nationale du Togo (Lome)", "framework": "hard_peg",
           "rate": "the BCEAO regional rate", "root": "https://www.bceao.int",
           "why": "Lome hosts the BOAD (the WAEMU development bank) and Ecobank's group "
                  "headquarters, so Togo is the union's banking seat without a monetary lever"},
    "bj": {"name": "BCEAO Agence Nationale du Benin (Cotonou)", "framework": "hard_peg",
           "rate": "the BCEAO regional rate", "root": "https://www.bceao.int",
           "why": "Benin is the WAEMU issuer with the best market access -- the first in the "
                  "zone to sell a euro-denominated eurobond and a dollar one -- so its auction "
                  "cut-off is the union's low-risk benchmark and Niger's is measured against it"},
    "sl": {"name": "Bank of Sierra Leone", "framework": "float",
           "rate": "the Monetary Policy Rate, announced at scheduled quarterly MPC meetings",
           "root": "https://www.bsl.gov.sl",
           "why": "a real national policy rate, a real float and a REDENOMINATION on 2022-07-01 "
                  "-- the only monetary regime break inside this pack's own sample window"},
    "lr": {"name": "Central Bank of Liberia", "framework": "float_dollarised",
           "rate": "the CBL policy rate, in an economy where the US dollar is legal tender "
                   "alongside the Liberian dollar",
           "root": "https://www.cbl.org.lr",
           "why": "PARTIAL DOLLARISATION is the control: a currency move here changes less of "
                  "the real economy than the same move in Freetown or Banjul does"},
    "gm": {"name": "Central Bank of The Gambia", "framework": "managed_float",
           "rate": "the Monetary Policy Rate, announced at quarterly MPC meetings",
           "root": "https://www.cbg.gm",
           "why": "the cleanest float of the three and the one with a published MONTHLY "
                  "remittance inflow series behind it"},
    "gw": {"name": "BCEAO Agence Nationale de Guinee-Bissau (Bissau)", "framework": "hard_peg",
           "rate": "the BCEAO regional rate", "root": "https://www.bceao.int",
           "why": "Guinea-Bissau abandoned the peso and joined WAEMU on 1997-05-02; the peg is "
                  "the only macroeconomic institution in the country that has never failed, and "
                  "it is why a cashew-price shock shows up in ARREARS rather than in inflation"},
    "cv": {"name": "Banco de Cabo Verde", "framework": "hard_peg",
           "rate": "the taxa directora, set to defend the 110.265 parity",
           "root": "https://www.bcv.cv",
           "why": "THE THIRD MONETARY CONTROL: a hard euro peg with a DIFFERENT guarantor "
                  "(Portugal, not the French Treasury) and a different economy behind it, which "
                  "is what lets a study ask whether the XOF's behaviour is about the peg or "
                  "about the guarantee"},
}

# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "BCEAO fixed parity 655.957 XOF = 1 EUR",
     "local": "not a fixing at all: an administered parity that does not move",
     "time_utc": "00:00", "time_utc_dst": "00:00", "dst_rule": "none",
     "instruments": ("EURUSD",), "window_minutes": 1440,
     "why": "the most important 'fixing' in this pack is a CONSTANT. Every XOF price in Niger, "
            "Togo, Benin and Guinea-Bissau is a euro price divided by 655.957, so the dollar "
            "exposure of four of these eight economies IS EURUSD and nothing else"},
    {"name": "Banco de Cabo Verde parity 110.265 CVE = 1 EUR",
     "local": "administered under the Acordo de Cooperacao Cambial with Portugal",
     "time_utc": "00:00", "time_utc_dst": "00:00", "dst_rule": "none",
     "instruments": ("EURUSD",), "window_minutes": 1440,
     "why": "the second constant, and the reason the two pegs are each other's control: same "
            "anchor currency, different guarantor, different economy"},
    {"name": "Bank of Sierra Leone wholesale FX auction and the published reference rate",
     "local": "auctions are held on a published weekday schedule, Africa/Freetown (UTC+0)",
     "time_utc": "12:00", "time_utc_dst": "12:00", "dst_rule": "none",
     "instruments": ("XAUUSD", "USDZAR"), "window_minutes": 90,
     "why": "the auction clearing rate against the bureau rate is the published stress spread of "
            "the only genuine float in the pack with a policy rate behind it"},
    {"name": "Central Bank of Liberia daily buying and selling rate, both currencies",
     "local": "published each business day, Africa/Monrovia (UTC+0)",
     "time_utc": "13:00", "time_utc_dst": "13:00", "dst_rule": "none",
     "instruments": ("XBRUSD", "USDZAR"), "window_minutes": 60,
     "why": "in a dual-currency economy the CBL publishes BOTH legs, so the LRD rate and the "
            "degree of dollarisation are separately readable -- which no other country here can "
            "say"},
    {"name": "Central Bank of The Gambia indicative mid-rate and the bureau survey",
     "local": "published each business day, Africa/Banjul (UTC+0)",
     "time_utc": "13:00", "time_utc_dst": "13:00", "dst_rule": "none",
     "instruments": ("SOYBEAN", "EURUSD"), "window_minutes": 60,
     "why": "the dalasi's seasonality is a REMITTANCE seasonality and the bureau survey is where "
            "the pre-Tobaski and Christmas inflow peaks are visible"},
    {"name": "UMOA-Titres weekly sovereign auction cut-off by issuer",
     "local": "auctions run on published days, settled T+1, Abidjan (UTC+0)",
     "time_utc": "11:00", "time_utc_dst": "11:00", "dst_rule": "none",
     "instruments": ("EURUSD", "USDZAR"), "window_minutes": 120,
     "why": "the only NATIONAL rate signal Niger, Togo, Benin and Guinea-Bissau produce; the "
            "Niger-minus-Benin cut-off spread is the fiscal stress reading SC-C is built on"},
    {"name": "LBMA gold price PM auction",
     "local": "15:00 Europe/London", "time_utc": "15:00", "time_utc_dst": "14:00",
     "dst_rule": "GMT/BST", "instruments": ("XAUUSD",), "window_minutes": 15,
     "why": "the reference the Sahel's artisanal gold circuit and the Sierra Leonean and Liberian "
            "buying houses price against; the gate price is a published discount to it"},
    {"name": "ICE and NYBOT cotton settlement against the West African ginning calendar",
     "local": "New York close", "time_utc": "19:20", "time_utc_dst": "18:20",
     "dst_rule": "EST/EDT", "instruments": ("COTTON",), "window_minutes": 20,
     "why": "the Beninese and Togolese interprofessions announce the campaign's guaranteed "
            "farmgate price BEFORE sowing, against a forward view of this settlement; the "
            "announcement is the event and the settlement is the benchmark"},
    {"name": "Euratom Supply Agency average contract price and the uranium spot assessment",
     "local": "the ESA average is annual, in the Agency's report; the spot assessment is daily "
              "and LICENSED",
     "time_utc": "16:00", "time_utc_dst": "16:00", "dst_rule": "none",
     "instruments": ("XNGUSD", "FRA40", "EUSTX50"), "window_minutes": 60,
     "why": "THE PRICE THIS PACK CANNOT TRADE, registered so that a Nigerien supply event is "
            "measured against the right benchmark before it is routed into power and gas"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "UMOA-Titres weekly bill and bond auctions for the four WAEMU issuers",
     "kind": "weekday", "weekday": 4, "roll": "next", "window_utc": ("09:00", "13:00"),
     "instruments": ("EURUSD", "USDZAR"),
     "why": "the regional auction window; settlement is T+1 and the results are published per "
            "issuer, which is what makes a Nigerien fiscal stress readable at weekly frequency"},
    {"name": "Bank of Sierra Leone and Central Bank of The Gambia Treasury bill auctions",
     "kind": "weekday", "weekday": 2, "roll": "next", "window_utc": ("10:00", "14:00"),
     "instruments": ("XAUUSD", "USDZAR"),
     "why": "both run midweek bill auctions; the cut-off and the bid-to-cover are the banks' "
            "appetite for local paper against dollars in two floating-rate economies"},
    {"name": "The West African cotton ginning campaign and the interprofession price notice",
     "kind": "day_of_month", "days": (1,), "months": (4, 5), "roll": "next",
     "window_utc": ("09:00", "16:00"), "instruments": ("COTTON",),
     "why": "the guaranteed farmgate price for the coming campaign is announced before sowing, "
            "in April or May; it is a DATED administered price on a crop the desk can trade"},
    {"name": "The Guinea-Bissau cashew campaign opening decree",
     "kind": "day_of_month", "days": (1,), "months": (4, 5), "roll": "next",
     "window_utc": ("09:00", "16:00"), "instruments": ("WHEAT", "CORN"),
     "why": "the campanha is opened by decree with a reference farmgate price; it is the single "
            "most important annual economic act of the country and it has a date on it"},
    {"name": "Month-end importer dollar demand at the Sahel quays",
     "kind": "month_end", "roll": "previous", "window_utc": ("08:00", "16:00"),
     "instruments": ("WHEAT", "CORN", "XBRUSD"),
     "why": "rice, wheat and fuel letters of credit settle into the last business days at Lome "
            "and Cotonou; under a corridor disruption this is when the queue is longest"},
    {"name": "Calendar fiscal year end and the eight budget laws", "kind": "fiscal_year_end",
     "roll": "previous", "window_utc": ("09:00", "18:00"),
     "instruments": ("COTTON", "XBRUSD", "EURUSD"),
     "why": "all eight run a calendar year; the mining royalty rates, the export levies and the "
            "cashew and cotton campaign frameworks are BUDGET instruments and turn on 1 January"},
    {"name": "Quarter-end IMF Article IV and programme review board dates",
     "kind": "quarter_end", "roll": "previous", "window_utc": ("14:00", "21:00"),
     "instruments": ("USDZAR", "EURUSD"),
     "why": "for six of the eight the Article IV is the ONLY published country-level "
            "macroeconomic aggregate there is, so its board date is the data release"},
    {"name": "The ECOWAS and AES summit calendar", "kind": "quarter_end", "roll": "next",
     "window_utc": ("10:00", "20:00"), "instruments": ("CORN", "WHEAT", "XBRUSD"),
     "why": "the sanctions of 2023-07-30, their lifting on 2024-02-24 and the withdrawal "
            "effective 2025-01-29 were all SUMMIT decisions with dates; the corridor cost "
            "changes on the communique and not on the market"},
)

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Bourse Regionale des Valeurs Mobilieres (BRVM), Abidjan -- the WAEMU's ONE exchange",
     "index_symbols": (),
     "open_local": "09:00", "close_local": "15:00", "open_utc": "09:00", "close_utc": "15:00",
     "dst_rule": "none: Abidjan is UTC+0 year-round",
     "auction": "a central order book with an opening call; a single regional tape serves all "
                "eight member states",
     "expiry_rule": "no listed derivatives of any kind",
     "holidays": "the Ivorian calendar plus the WAEMU-wide closures",
     "notes": "NIGER, TOGO, BENIN AND GUINEA-BISSAU HAVE NO NATIONAL EXCHANGE. The tape belongs "
              "to `west_africa` and this pack reads the UMOA-Titres AUCTION leg instead, because "
              "the auction is per-issuer and therefore national while the equity tape is not"},
    {"name": "Bolsa de Valores de Cabo Verde (BVC), Praia",
     "index_symbols": (),
     "open_local": "09:00", "close_local": "13:00", "open_utc": "10:00", "close_utc": "14:00",
     "dst_rule": "none: Cabo Verde is UTC-1 year-round, the ONLY one of the eight that is not GMT",
     "auction": "a very thin order book dominated by government and bank bonds with a handful of "
                "listed equities",
     "expiry_rule": "none",
     "holidays": "the Cabo Verdean national calendar including Carnival",
     "notes": "THE ONLY DOMESTIC EXCHANGE IN THE SEVEN NON-WAEMU-TAPE JURISDICTIONS, and the "
              "reason the institutional layer is not declared absent for Cabo Verde. No CFD is "
              "quoted on it; it is a STATE, not a price"},
    {"name": "The Liberian International Ship and Corporate Registry -- a register, not a bourse",
     "index_symbols": (),
     "open_local": "09:00", "close_local": "17:00", "open_utc": "14:00", "close_utc": "22:00",
     "dst_rule": "the registry is administered from Virginia, USA, so its business day is "
                 "EST/EDT and NOT Monrovia's",
     "auction": "n/a: vessels are registered continuously and the fleet statistics are published",
     "expiry_rule": "n/a",
     "holidays": "US federal holidays for the administrator; Liberian holidays for the maritime "
                 "authority in Monrovia",
     "notes": "LISTED HERE BECAUSE IT IS THE MOST MARKET-RELEVANT INSTITUTION IN LIBERIA and "
              "because its clock is a US one, which a pack that assumed Monrovia's would get "
              "wrong by five hours"},
    {"name": "The interbank FX markets and licensed bureaux of SL, LR and GM",
     "index_symbols": (), "open_local": "08:30", "close_local": "16:30",
     "open_utc": "08:30", "close_utc": "16:30", "dst_rule": "none",
     "auction": "the Bank of Sierra Leone runs a wholesale auction; the CBL and CBG publish "
                "indicative rates and intervene thinly",
     "expiry_rule": "no forwards market worth the name; there is no exchange clock",
     "holidays": "each country's banking calendar",
     "notes": "the bureau-to-official spread is the published stress observable in all three and "
              "is the only one that survives the Sierra Leonean redenomination intact, because "
              "it is a RATIO"},
    {"name": "The Sahel corridor's physical 'exchanges': Lome, Cotonou, Freetown and Buchanan",
     "index_symbols": (), "open_local": "00:00", "close_local": "23:59",
     "open_utc": "00:00", "close_utc": "23:59", "dst_rule": "none",
     "auction": "continuous vessel operations; throughput is published monthly or quarterly",
     "expiry_rule": "n/a",
     "holidays": "the ports work through most national holidays; the CUSTOMS offices do not, "
                 "which is the binding constraint on clearance and therefore on the corridor",
     "notes": "the real price-forming venues in this pack are QUAYS. Lome is the deepest "
              "container port on the coast and Cotonou is Niger's outlet, and both publish "
              "tonnage -- which is a better weekly observable than any equity tape here"},
)

SESSION_WINDOWS: tuple[dict[str, Any], ...] = (
    {"name": "sc_gmt_morning", "start_utc": "08:00", "end_utc": "12:00",
     "notes": "the West African business morning. Seven of the eight jurisdictions are UTC+0 "
              "year-round, so this window is stable in UTC all year and coincides exactly with "
              "the London morning -- which is genuinely convenient and rare"},
    {"name": "sc_umoa_auction", "start_utc": "09:00", "end_utc": "13:00",
     "notes": "the UMOA-Titres auction window and the BRVM session; the only regular financial "
              "clock four of these eight countries have"},
    {"name": "sc_london_overlap", "start_utc": "08:00", "end_utc": "16:30",
     "notes": "the whole West African day sits inside London's, so a Sahel physical observable "
              "reaches a liquid gold, softs or energy price the same session it is published"},
    {"name": "sc_cv_session", "start_utc": "10:00", "end_utc": "14:00",
     "notes": "Cabo Verde alone is UTC-1, so the Praia business day runs an hour behind the "
              "mainland's; a pack that assumed one African offset would mis-stamp every CV row"},
    {"name": "sc_lr_registry_session", "start_utc": "14:00", "end_utc": "22:00",
     "notes": "the Liberian ship registry is administered from the United States on EST/EDT, so "
              "registry announcements land in the NEW YORK afternoon and not the Monrovia one"},
    {"name": "sc_announcement_afternoon", "start_utc": "12:00", "end_utc": "18:00",
     "notes": "the BCEAO communiques, the ECOWAS and AES summit statements, the ministerial "
              "press conferences and the campaign-price decrees"},
)

RELEASE_CLASSES: tuple[dict[str, Any], ...] = (
    {"name": "BCEAO Comite de Politique Monetaire communique", "cadence": "quarterly",
     "time_utc": "14:00", "source": "BCEAO", "actual_series": "BCEAO:taux_minimum_soumission",
     "expected_series": "UNMEASURED",
     "notes": "one decision for eight countries; a Nigerien or Bissau-Guinean 'policy surprise' "
              "does not exist as a national event and the pack refuses to manufacture one"},
    {"name": "UMOA-Titres auction results by issuer", "cadence": "weekly", "time_utc": "13:00",
     "source": "UMOA-Titres", "actual_series": "UMOATITRES:cutoff_by_issuer",
     "expected_series": "UNMEASURED",
     "notes": "THE NATIONAL RATE SIGNAL. Amount sought, amount raised, cut-off and bid-to-cover "
              "per country -- the series that measured the bite of the 2023 Niger sanctions"},
    {"name": "Bank of Sierra Leone Monetary Policy Committee decision", "cadence": "quarterly",
     "time_utc": "15:00", "source": "Bank of Sierra Leone", "actual_series": "BSL:mpr",
     "expected_series": "UNMEASURED",
     "notes": "a real national policy rate in a real float; the only scheduled monetary clock in "
              "the pack that can produce a surprise at all"},
    {"name": "Central Bank of The Gambia MPC decision and the monthly remittance print",
     "cadence": "quarterly", "time_utc": "15:00", "source": "Central Bank of The Gambia",
     "actual_series": "CBG:mpr", "expected_series": "UNMEASURED",
     "notes": "the remittance series published alongside it is the more useful half: a monthly "
              "counted inflow in an economy where remittances are a very large share of GDP"},
    {"name": "Central Bank of Liberia monthly statistical bulletin and the dual-currency split",
     "cadence": "monthly", "time_utc": "14:00", "source": "Central Bank of Liberia",
     "actual_series": "CBL:lrd_usd_rate", "expected_series": "n/a",
     "notes": "publishes BOTH currency legs, the dollarisation share and the bureau spread"},
    {"name": "Port of Lome and Port of Cotonou throughput and transit split", "cadence": "monthly",
     "time_utc": "12:00", "source": "Port Autonome de Lome / Port Autonome de Cotonou",
     "actual_series": "PAL_PAC:tonnage_transit", "expected_series": "n/a",
     "notes": "THE SERIES SC-H AND SC-K ARE BUILT ON: tonnage with the TRANSIT split by "
              "destination country, which is what turns a national port statistic into a "
              "landlocked-Sahel supply observable"},
    {"name": "Liberian registry fleet statistics (vessel count, gross and deadweight tonnage)",
     "cadence": "quarterly", "time_utc": "16:00", "source": "LISCR / Liberian Registry",
     "actual_series": "LISCR:fleet_dwt", "expected_series": "n/a",
     "notes": "the registry publishes its own size and composition; UNCTAD and the IMO republish "
              "it annually, which gives the series an independent cross-check"},
    {"name": "Euratom Supply Agency annual report: origin shares of EU natural uranium supply",
     "cadence": "annual", "time_utc": "10:00", "source": "Euratom Supply Agency",
     "actual_series": "ESA:origin_share_ne", "expected_series": "n/a",
     "notes": "THE ONLY AUTHORITATIVE PUBLIC MEASURE of how much European reactor fuel comes "
              "from Niger; it is ANNUAL and a year late, so it can date an era and can never "
              "condition a week -- which is stated here rather than discovered later"},
    {"name": "Kimberley Process annual statistics: Sierra Leone and Liberia rough diamond "
             "production and exports", "cadence": "annual", "time_utc": "12:00",
     "source": "Kimberley Process Certification Scheme", "actual_series": "KPCS:sl_lr_carats",
     "expected_series": "n/a",
     "notes": "carats and value by participant, with the importers' own figures beside them; a "
              "MIRROR statistic in a trade whose whole point is that it is hard to track"},
    {"name": "The cotton interprofessions' campaign price notices (Benin and Togo)",
     "cadence": "annual", "time_utc": "12:00", "source": "AIC Benin / NSCT Togo",
     "actual_series": "AIC_NSCT:farmgate_price", "expected_series": "n/a",
     "notes": "a guaranteed farmgate price announced BEFORE sowing; a dated administered price "
              "on a crop the desk can actually trade, which is rare enough to be a domain"},
    {"name": "Guinea-Bissau cashew campaign decree and reference price", "cadence": "annual",
     "time_utc": "12:00", "source": "Government of Guinea-Bissau / Boletim Oficial",
     "actual_series": "GW:preco_referencia_caju", "expected_series": "n/a",
     "notes": "the single most consequential annual economic act in the country: it sets the "
              "farmgate price of roughly nine tenths of its export earnings"},
    {"name": "IMB Piracy Reporting Centre quarterly and annual piracy report", "cadence": "quarterly",
     "time_utc": "10:00", "source": "ICC International Maritime Bureau",
     "actual_series": "IMB:gog_incidents", "expected_series": "n/a",
     "notes": "incidents, kidnappings and locations for the Gulf of Guinea; the series that "
              "recorded the region's share of world crew kidnapping rising to a peak and then "
              "falling sharply, which is a WAR-RISK PREMIUM observable"},
    {"name": "IMF Article IV staff reports for the eight", "cadence": "annual",
     "time_utc": "15:00", "source": "International Monetary Fund",
     "actual_series": "IMF:artiv_selected_issues", "expected_series": "n/a",
     "notes": "FOR SIX OF THE EIGHT THIS IS THE MACRO DATA PLANE. It is annual, revised and "
              "negotiated, so it dates eras and never conditions a week -- and saying that is "
              "the measurement, not an apology"},
)

# --------------------------------------------------------------------------- the calendars
#: ALL EIGHT ARE GREGORIAN, which after Ethiopia's Ge'ez calendar is a relief and still not
#: simple: the pack carries EIGHT national tables, two Christian traditions (the francophone
#: Catholic feasts of Togo and Benin, the Portuguese Catholic feasts of Cabo Verde and
#: Guinea-Bissau, and the Good Friday/Easter Monday pair of anglophone Sierra Leone, Liberia and
#: The Gambia), and FIVE INDEPENDENT ISLAMIC SIGHTING AUTHORITIES. Easter is COMPUTED by the
#: anonymous Gregorian algorithm and everything that hangs off it -- Good Friday, Easter Monday,
#: Ascension, Whit Monday and the Cabo Verdean Carnival -- falls out of that one function.
def western_easter(year: int) -> date:
    """Easter Sunday in the Gregorian calendar, by the ANONYMOUS GREGORIAN ALGORITHM.

    Typed Easter tables are the classic country-pack defect: they are right for the three years
    somebody checked and silently wrong afterwards. This is arithmetic and extends forever.
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
    month = (h + ell - 7 * m + 114) // 31
    day = ((h + ell - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def good_friday(year: int) -> date:
    """Two days before Easter. Closed in SL, LR, GM, GW and CV; NOT a public holiday in the
    three francophone WAEMU members here, which is a real per-country asymmetry."""
    return western_easter(year) - timedelta(days=2)


def easter_monday(year: int) -> date:
    return western_easter(year) + timedelta(days=1)


def ascension(year: int) -> date:
    """Thirty-nine days after Easter: a Thursday, and a closure in Togo and Benin."""
    return western_easter(year) + timedelta(days=39)


def whit_monday(year: int) -> date:
    """Fifty days after Easter: Lundi de Pentecote, closed in Togo and Benin."""
    return western_easter(year) + timedelta(days=50)


def carnival_tuesday(year: int) -> date:
    """Shrove Tuesday, forty-seven days before Easter. THE Cabo Verdean closure: the Mindelo
    Carnival is the country's largest annual event and the tourism season peaks around it."""
    return western_easter(year) - timedelta(days=47)


def nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """The n-th `weekday` (Mon=0) of a month. THREE Liberian holidays are defined this way and
    not by a fixed date, which is the single most common error in a typed Liberian calendar."""
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return date(year, month, 1 + offset + 7 * (n - 1))


#: FIXED SOLAR NATIONAL DAYS, per jurisdiction. Rows are (month, day, name). None of the eight
#: has a general weekend-substitution statute, so a Saturday holiday costs no session and
#: `market_holidays` drops it.
FIXED_NE: tuple[tuple[int, int, str], ...] = (
    (1, 1, "Jour de l'An / Sabuwar Shekara"),
    (4, 24, "Journee de la Concorde / Ranar Sulhu"),
    (5, 1, "Fete du Travail / Ranar Ma'aikata"),
    (8, 3, "Fete de l'Independance et Journee de l'Arbre / Ranar 'Yancin Kai"),
    (12, 18, "Proclamation de la Republique / Ranar Jamhuriya"),
    (12, 25, "Noel"),
)
FIXED_TG: tuple[tuple[int, int, str], ...] = (
    (1, 1, "Jour de l'An"),
    (1, 13, "Fete de la Liberation nationale"),
    (4, 27, "Fete de l'Independance"),
    (5, 1, "Fete du Travail"),
    (6, 21, "Journee des Martyrs"),
    (8, 15, "Assomption"),
    (11, 1, "Toussaint"),
    (12, 25, "Noel"),
)
FIXED_BJ: tuple[tuple[int, int, str], ...] = (
    (1, 1, "Jour de l'An"),
    (1, 10, "Fete des Religions Traditionnelles / Vodun"),
    (5, 1, "Fete du Travail"),
    (8, 1, "Fete de l'Independance"),
    (8, 15, "Assomption"),
    (11, 1, "Toussaint"),
    (12, 25, "Noel"),
)
FIXED_SL: tuple[tuple[int, int, str], ...] = (
    (1, 1, "New Year's Day"),
    (4, 27, "Independence Day"),
    (5, 1, "Workers' Day"),
    (12, 25, "Christmas Day"),
    (12, 26, "Boxing Day"),
)
FIXED_LR: tuple[tuple[int, int, str], ...] = (
    (1, 1, "New Year's Day"),
    (2, 11, "Armed Forces Day"),
    (3, 15, "J. J. Roberts Birthday"),
    (7, 26, "Independence Day"),
    (8, 24, "National Flag Day"),
    (11, 29, "President William V. S. Tubman's Birthday"),
    (12, 25, "Christmas Day"),
)
FIXED_GM: tuple[tuple[int, int, str], ...] = (
    (1, 1, "New Year's Day"),
    (2, 18, "Independence Day"),
    (5, 1, "Workers' Day"),
    (7, 22, "Revolution Day"),
    (8, 15, "Assumption"),
    (12, 25, "Christmas Day"),
)
FIXED_GW: tuple[tuple[int, int, str], ...] = (
    (1, 1, "Ano Novo"),
    (1, 20, "Dia dos Heroies Nacionais / assassinato de Amilcar Cabral"),
    (3, 8, "Dia Internacional da Mulher"),
    (5, 1, "Dia do Trabalhador"),
    (8, 3, "Dia dos Martires da Colonizacao / Pidjiguiti"),
    (9, 24, "Dia da Independencia"),
    (11, 14, "Dia do Movimento Reajustador"),
    (12, 25, "Natal"),
)
FIXED_CV: tuple[tuple[int, int, str], ...] = (
    (1, 1, "Ano Novo"),
    (1, 13, "Dia da Democracia"),
    (1, 20, "Dia dos Heroies Nacionais / Amilcar Cabral"),
    (5, 1, "Dia do Trabalhador"),
    (6, 1, "Dia da Crianca"),
    (7, 5, "Dia da Independencia Nacional"),
    (8, 15, "Assuncao de Nossa Senhora"),
    (11, 1, "Dia de Todos os Santos"),
    (12, 25, "Natal"),
)

#: THE ISLAMIC FEASTS ARE TYPED, WITH THE AUTHORITY THAT SIGHTS THEM IN EACH COUNTRY. Five
#: independent bodies announce in the six jurisdictions that observe them -- the Association
#: Islamique du Niger with the Ministry of the Interior's commission, the Union Musulmane du
#: Togo, the Union Islamique du Benin, the Sierra Leone Supreme Islamic Council, the Gambia
#: Supreme Islamic Council, the National Muslim Council of Liberia, and the mosque councils of
#: Bafata and Gabu for Guinea-Bissau -- and WEST AFRICAN OBSERVANCE ROUTINELY RUNS A DAY LATER
#: THAN THE GULF'S. A rule would be a wrong rule, so each row carries (date, name, status) and
#: every 2026 row is PROJECTED. Cabo Verde does not observe them at all.
LUNAR_HOLIDAYS: dict[int, tuple[tuple[date, str, str], ...]] = {
    2024: ((date(2024, 4, 10), "Aid el-Fitr / Karamar Sallah / Korite", "ANNOUNCED"),
           (date(2024, 6, 16), "Aid el-Kebir / Babbar Sallah / Tabaski", "ANNOUNCED"),
           (date(2024, 9, 16), "Mouloud / Maulidi / Gani", "ANNOUNCED")),
    2025: ((date(2025, 3, 31), "Aid el-Fitr / Karamar Sallah / Korite", "ANNOUNCED"),
           (date(2025, 6, 7), "Aid el-Kebir / Babbar Sallah / Tabaski", "ANNOUNCED"),
           (date(2025, 9, 5), "Mouloud / Maulidi / Gani", "PROJECTED")),
    2026: ((date(2026, 3, 20), "Aid el-Fitr / Karamar Sallah / Korite", "PROJECTED"),
           (date(2026, 5, 27), "Aid el-Kebir / Babbar Sallah / Tabaski", "PROJECTED"),
           (date(2026, 8, 25), "Mouloud / Maulidi / Gani", "PROJECTED")),
}
#: Who announces, per jurisdiction. The status of a row is only as good as the body behind it.
SIGHTING_AUTHORITIES: dict[str, str] = {
    "ne": "Association Islamique du Niger with the Ministry of the Interior's sighting "
          "commission; Niamey has announced a day later than Saudi Arabia in several years",
    "tg": "Union Musulmane du Togo",
    "bj": "Union Islamique du Benin",
    "sl": "the Sierra Leone Supreme Islamic Council; Freetown and the provinces have differed by "
          "a day",
    "lr": "the National Muslim Council of Liberia; only the two Eids are public holidays and the "
          "country's calendar is dominated by its Christian and civic days",
    "gm": "the Gambia Supreme Islamic Council, whose announcement is broadcast on GRTS",
    "gw": "the mosque councils of Bafata and Gabu; the state gazettes the day afterwards rather "
          "than before it",
    "cv": "NONE: Cabo Verde has no Islamic public holiday and the pack does not invent one",
}
#: Which jurisdictions close for MOULOUD as well as the two Eids. Liberia and Cabo Verde do not,
#: and Sierra Leone does -- a genuine per-country asymmetry a pooled 'West African Islamic
#: holiday' dummy would erase.
MAWLID_OBSERVERS: frozenset[str] = frozenset({"ne", "tg", "bj", "sl", "gm", "gw"})
EID_OBSERVERS: frozenset[str] = frozenset({"ne", "tg", "bj", "sl", "lr", "gm", "gw"})

#: One-off dated facts no recurring rule produces. Not all are closures; they are carried here
#: because they are the days the domains condition on and a reader needs them in one place.
DECLARED_CLOSURES: dict[date, str] = {
    date(2024, 5, 15): "the first export cargo of Nigerien crude loads at Seme-Kpodji, Benin -- "
                       "not a closure, carried as the dated institutional fact SC-B conditions "
                       "on [PRESS_REPORTED]",
    date(2025, 1, 29): "the ECOWAS withdrawal of Niger, Mali and Burkina Faso takes effect, one "
                       "year after the 2024-01-28 announcement, with a transition period that "
                       "ran into July 2025 -- SC-C's boundary",
    date(2022, 7, 1): "the Sierra Leonean leone is redenominated 1000:1 (SLL -> SLE): a 1000x "
                      "step in every leone series that is NOT a price move",
}


def nigerien_holidays(year: int) -> dict[date, str]:
    """Niger's closed days: six fixed solar dates, Easter Monday, and the three Islamic feasts
    announced by the Association Islamique du Niger."""
    out: dict[date, str] = {}
    for m, d, name in FIXED_NE:
        out[date(year, m, d)] = name
    out[easter_monday(year)] = "Lundi de Paques"
    for day, name, status in LUNAR_HOLIDAYS.get(year, ()):
        if "Mouloud" in name and "ne" not in MAWLID_OBSERVERS:
            continue
        out[day] = f"{name} [{status}]"
    return dict(sorted(out.items()))


def togolese_holidays(year: int) -> dict[date, str]:
    """Togo: eight fixed solar dates, the full Catholic movable set (Easter Monday, Ascension,
    Whit Monday) and the two Eids with Mouloud."""
    out: dict[date, str] = {}
    for m, d, name in FIXED_TG:
        out[date(year, m, d)] = name
    out[easter_monday(year)] = "Lundi de Paques"
    out[ascension(year)] = "Ascension"
    out[whit_monday(year)] = "Lundi de Pentecote"
    for day, name, status in LUNAR_HOLIDAYS.get(year, ()):
        out[day] = f"{name} [{status}]"
    return dict(sorted(out.items()))


def beninese_holidays(year: int) -> dict[date, str]:
    """Benin: seven fixed solar dates including the Fete des Religions Traditionnelles on 10
    January -- a public holiday for VODUN, which exists nowhere else on the desk's roster -- the
    Catholic movable set and the three Islamic feasts."""
    out: dict[date, str] = {}
    for m, d, name in FIXED_BJ:
        out[date(year, m, d)] = name
    out[easter_monday(year)] = "Lundi de Paques"
    out[ascension(year)] = "Ascension"
    out[whit_monday(year)] = "Lundi de Pentecote"
    for day, name, status in LUNAR_HOLIDAYS.get(year, ()):
        out[day] = f"{name} [{status}]"
    return dict(sorted(out.items()))


def sierra_leonean_holidays(year: int) -> dict[date, str]:
    """Sierra Leone: five fixed solar dates, the anglophone Good Friday/Easter Monday pair, and
    the three Islamic feasts announced by the Supreme Islamic Council."""
    out: dict[date, str] = {}
    for m, d, name in FIXED_SL:
        out[date(year, m, d)] = name
    out[good_friday(year)] = "Good Friday"
    out[easter_monday(year)] = "Easter Monday"
    for day, name, status in LUNAR_HOLIDAYS.get(year, ()):
        out[day] = f"{name} [{status}]"
    return dict(sorted(out.items()))


def liberian_holidays(year: int) -> dict[date, str]:
    """Liberia: seven fixed solar dates, THREE WEEKDAY-RULE holidays that a typed table gets
    wrong -- Decoration Day on the second Wednesday of March, National Fast and Prayer Day on the
    second Friday of April and Thanksgiving on the first Thursday of November -- the anglophone
    Easter pair, and the two Eids only."""
    out: dict[date, str] = {}
    for m, d, name in FIXED_LR:
        out[date(year, m, d)] = name
    out[nth_weekday(year, 3, 2, 2)] = "Decoration Day"
    out[nth_weekday(year, 4, 4, 2)] = "National Fast and Prayer Day"
    out[nth_weekday(year, 11, 3, 1)] = "National Thanksgiving Day"
    out[good_friday(year)] = "Good Friday"
    out[easter_monday(year)] = "Easter Monday"
    for day, name, status in LUNAR_HOLIDAYS.get(year, ()):
        if "Mouloud" in name:
            continue
        out[day] = f"{name} [{status}]"
    return dict(sorted(out.items()))


def gambian_holidays(year: int) -> dict[date, str]:
    """The Gambia: six fixed solar dates, the anglophone Easter pair, and the three Islamic
    feasts announced by the Gambia Supreme Islamic Council. The Gambia is the clearest case in
    the pack of a country that closes for BOTH traditions."""
    out: dict[date, str] = {}
    for m, d, name in FIXED_GM:
        out[date(year, m, d)] = name
    out[good_friday(year)] = "Good Friday"
    out[easter_monday(year)] = "Easter Monday"
    for day, name, status in LUNAR_HOLIDAYS.get(year, ()):
        out[day] = f"{name} [{status}]"
    return dict(sorted(out.items()))


def bissau_guinean_holidays(year: int) -> dict[date, str]:
    """Guinea-Bissau: eight fixed solar dates including two that are unique to it -- 20 January
    for Amilcar Cabral's assassination and 3 August for the Pidjiguiti dock massacre of 1959 --
    Good Friday, and the two Eids with Mouloud."""
    out: dict[date, str] = {}
    for m, d, name in FIXED_GW:
        out[date(year, m, d)] = name
    out[good_friday(year)] = "Sexta-Feira Santa"
    for day, name, status in LUNAR_HOLIDAYS.get(year, ()):
        out[day] = f"{name} [{status}]"
    return dict(sorted(out.items()))


def cabo_verdean_holidays(year: int) -> dict[date, str]:
    """Cabo Verde: nine fixed solar dates, the Catholic movable pair and CARNIVAL TUESDAY, which
    is the country's largest annual event. NO Islamic feast is observed and the pack does not
    invent one -- the honest asymmetry is the point of carrying eight tables."""
    out: dict[date, str] = {}
    for m, d, name in FIXED_CV:
        out[date(year, m, d)] = name
    out[carnival_tuesday(year)] = "Terca-Feira de Carnaval"
    out[good_friday(year)] = "Sexta-Feira Santa"
    out[western_easter(year)] = "Domingo de Pascoa"
    return dict(sorted(out.items()))


JURISDICTION_HOLIDAY_FN: dict[str, Any] = {
    "ne": nigerien_holidays, "tg": togolese_holidays, "bj": beninese_holidays,
    "sl": sierra_leonean_holidays, "lr": liberian_holidays, "gm": gambian_holidays,
    "gw": bissau_guinean_holidays, "cv": cabo_verdean_holidays,
}


def national_holidays(year: int) -> dict[date, str]:
    """EVERY closed day across the eight, TAGGED with the countries that actually close.

    A union table, because this pack answers for eight countries at once and a day that closes
    Niamey is a normal session in Praia. The tag is what stops a study treating a one-country
    closure as a regional one -- and with eight calendars, most days are one-country days.
    """
    tagged: dict[date, list[str]] = {}
    names: dict[date, str] = {}
    for code, fn in JURISDICTION_HOLIDAY_FN.items():
        for day, name in fn(year).items():
            tagged.setdefault(day, []).append(code.upper())
            names.setdefault(day, name)
    out = {day: f"{names[day]} [{'+'.join(sorted(codes))}]" for day, codes in tagged.items()}
    for day, name in DECLARED_CLOSURES.items():
        if day.year == year:
            out[day] = f"{out.get(day, '')} {name}".strip()
    return dict(sorted(out.items()))


def market_holidays(year: int) -> dict[date, str]:
    """The weekday closures only. A Saturday holiday costs no session and must not enter a
    holiday-liquidity sample as one; none of the eight has a general substitution statute."""
    return {d: n for d, n in national_holidays(year).items() if d.weekday() < 5}


def is_market_holiday(day: date) -> bool:
    return day in market_holidays(day.year)


def closed_in(code: str, day: date) -> bool:
    """True when THIS jurisdiction's cash market and banks are closed on this day."""
    fn = JURISDICTION_HOLIDAY_FN.get(str(code).lower())
    return day in fn(day.year) if fn is not None else False


def closures_on(day: date) -> tuple[str, ...]:
    """Which of the eight close on a given day. A regional day closes most of them; the
    interesting days are the ones that close exactly one."""
    return tuple(sorted(c for c in JURISDICTIONS if closed_in(c, day)))


def announced_dates(year: int) -> dict[date, str]:
    """Only the Islamic feasts that were ANNOUNCED. PROJECTED rows can be a day off in any of the
    seven observing jurisdictions, and West African observance routinely runs a day behind the
    Gulf's -- so a projected date is a projection twice over."""
    return {d: n for d, n, st in LUNAR_HOLIDAYS.get(year, ()) if st == "ANNOUNCED"}


HOLIDAYS_RULE: dict[str, Any] = {
    "kind": "eight_gregorian_calendars_plus_a_declared_lunar_table",
    "authority": "eight labour ministries for the solar days; the Catholic and anglophone "
                 "Christian movable feasts are arithmetic; five independent Islamic sighting "
                 "bodies for the Eids and Mouloud (see SIGHTING_AUTHORITIES)",
    "rule": "ALL EIGHT RUN THE GREGORIAN CALENDAR. EASTER IS COMPUTED by the ANONYMOUS GREGORIAN "
            "ALGORITHM and everything hanging off it falls out of that one function: Good Friday "
            "(Easter minus two days, closed in SL, LR, GM, GW and CV), Easter Monday (closed "
            "everywhere except Guinea-Bissau), Ascension (Easter plus 39 days) and Lundi de "
            "Pentecote (Easter plus 50 days) in TOGO and BENIN only, and CARNIVAL TUESDAY "
            "(Easter minus 47 days) in CABO VERDE, where it is the largest annual event. "
            "LIBERIA CARRIES THREE WEEKDAY-RULE HOLIDAYS a typed table gets wrong: Decoration "
            "Day on the SECOND WEDNESDAY OF MARCH, National Fast and Prayer Day on the SECOND "
            "FRIDAY OF APRIL and Thanksgiving on the FIRST THURSDAY OF NOVEMBER. The fixed "
            "national days are Niger 3 August and 18 December, Togo 27 April, Benin 1 August, "
            "Sierra Leone 27 April, Liberia 26 July, The Gambia 18 February, Guinea-Bissau 24 "
            "September and Cabo Verde 5 July. Benin closes for VODUN on 10 January, which exists "
            "on no other pack's calendar. THE ISLAMIC FEASTS ARE TYPED WITH THEIR SIGHTING "
            "AUTHORITY because no rule computes them: Aid el-Fitr and Aid el-Kebir in seven of "
            "the eight (not Cabo Verde), and Mouloud in six (not Liberia, not Cabo Verde). West "
            "African sighting routinely announces a day LATER than the Gulf. NO WEEKEND "
            "SUBSTITUTION statute in any of the eight, and NO DAYLIGHT SAVING anywhere: seven of "
            "the eight are UTC+0 year-round and CABO VERDE ALONE IS UTC-1.",
    "years": (2024, 2025, 2026),
    "weekend": "Saturday and Sunday",
    "national_rule": "see `rule`; `national_holidays(year)` is the computed union and the eight "
                     "per-jurisdiction functions are in JURISDICTION_HOLIDAY_FN",
    "market_rule": "the union calendar on weekdays; there is no regional exchange in this pack "
                   "except the BRVM, which keeps the IVORIAN calendar and belongs to "
                   "`west_africa`, so the union rows are TAGGED with the countries that close",
    "moon_sighting_rule": "DECLARED, not inferred: five authorities, five announcements, and a "
                          "PROJECTED row may be a day off in any of the seven observers",
    "moving_feasts": "the Islamic feasts drift about eleven days earlier each solar year; Easter "
                     "moves on the Gregorian computus, so Tabaski and Easter cross each other "
                     "every few decades and a naive 'the Muslim holiday is in summer' rule is "
                     "wrong for half this pack's history",
    "timezone_rule": "UTC+0 year-round in NE, TG, BJ, SL, LR, GM and GW; UTC-1 year-round in CV",
    "table": {y: {d.isoformat(): n for d, n in national_holidays(y).items()}
              for y in (2024, 2025, 2026)},
    "status": {2024: "COMPUTED for every Christian movable feast and for the three Liberian "
                     "weekday rules; ANNOUNCED for all three Islamic feasts",
               2025: "COMPUTED for the movable feasts; ANNOUNCED for the two Eids and PROJECTED "
                     "for Mouloud",
               2026: "COMPUTED for the movable feasts (they are arithmetic, not a sighting); "
                     "PROJECTED for every Islamic row",
               },
    "known_dates": {
        "2024-03-31": "Easter Sunday 2024; Good Friday 2024-03-29 closed SL, LR, GM, GW and CV "
                      "and did NOT close Niger, Togo or Benin",
        "2025-04-20": "Easter Sunday 2025, three weeks later than 2024's -- the movable feast "
                      "that a fixed-date 'spring holiday' dummy gets wrong every year",
        "2026-04-05": "Easter Sunday 2026",
        "2025-03-31": "Aid el-Fitr 2025, ANNOUNCED; it fell eleven days earlier than in 2024",
        "2025-06-07": "Aid el-Kebir (Tabaski) 2025, the largest household-spending event of the "
                      "year in Niger and The Gambia and the peak of the remittance season",
        "2024-12-18": "Niger's Republic Day, the first since the ECOWAS withdrawal announcement",
        "2022-07-01": "the Sierra Leonean redenomination: not a holiday, the era boundary",
    },
    "fn": market_holidays,
    "national_fn": national_holidays,
    "announced_fn": announced_dates,
    "easter_fn": western_easter,
    "carnival_fn": carnival_tuesday,
    "closures_fn": closures_on,
}

# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "UMOA-Titres auction results by issuer (amount sought, raised, cut-off, cover)",
     "root": "https://www.umoatitres.org",
     "fields": ("issuer_country", "amount_sought_xof", "amount_raised_xof", "cutoff_yield",
                "bid_to_cover", "tenor_days", "auction_date"),
     "frequency": "weekly", "snapshot": "auction", "publish_utc": "13:00",
     "lag_days": 0, "licence": "free, public", "available": True,
     "why": "THE ONLY NATIONAL FINANCIAL SERIES four of these eight countries produce. Niger's "
            "cut-off against Benin's over 2023-2024 is the published measure of what the ECOWAS "
            "sanctions actually cost -- a real, dated, weekly fiscal-stress reading",
     "pit_warning": "results are published per auction and not revised, but the historical "
                    "archive is a portal and not a file; the point-in-time vintage is the crawl"},
    {"name": "Liberian Registry published fleet statistics (count, GT, DWT, type mix)",
     "root": "https://www.liscr.com",
     "fields": ("vessel_count", "gross_tonnage", "deadweight_tonnage", "tanker_share",
                "bulker_share", "average_age_years"),
     "frequency": "quarterly / annual", "snapshot": "register", "publish_utc": "16:00",
     "lag_days": 30, "licence": "free, public (registry terms)", "available": True,
     "why": "a FLAG STATE'S OWN CENSUS of a sixth of world deadweight tonnage, with the type mix "
            "that turns it into a tanker-capacity reading; UNCTAD and the IMO republish it "
            "annually, which is an independent cross-check no other series here has",
     "pit_warning": "the registry's own page shows TODAY's fleet and keeps no history, so the "
                    "only point-in-time vintage is a crawl or the UNCTAD annual"},
    {"name": "Central Bank of The Gambia monthly remittance inflows",
     "root": "https://www.cbg.gm",
     "fields": ("remittance_inflows_usd", "remittance_inflows_gmd", "source_country_split",
                "bureau_rate", "official_rate", "reserves_months_of_imports"),
     "frequency": "monthly", "snapshot": "calendar month", "publish_utc": "14:00",
     "lag_days": 40, "licence": "free, public", "available": True,
     "why": "a COUNTED monthly inflow in an economy where remittances are a very large share of "
            "GDP; the seasonal peaks around Tobaski and Christmas are the testable part and the "
            "dalasi's stress is seasonal rather than monetary",
     "pit_warning": "revised for two to three months after first publication; a cell compiled on "
                    "the first print is a different number from the same month a year later"},
    {"name": "Euratom Supply Agency annual report: natural uranium origin shares for EU utilities",
     "root": "https://euratom-supply.ec.europa.eu",
     "fields": ("origin_country", "share_of_eu_deliveries", "average_contract_price",
                "inventory_years_of_cover"),
     "frequency": "annual", "snapshot": "calendar year", "publish_utc": "10:00",
     "lag_days": 180, "licence": "free, public (EU open data)", "available": True,
     "why": "THE AUTHORITATIVE PUBLIC MEASURE of Niger's weight in European reactor fuel, and "
            "the one that also publishes the INVENTORY COVER -- which is why this pack predicts "
            "a small and slow price effect rather than a large and fast one",
     "pit_warning": "annual and half a year late; it dates an era and can never condition a "
                    "week, and SC-A says so on its face"},
    {"name": "Kimberley Process annual statistics for Sierra Leone and Liberia",
     "root": "https://kimberleyprocess.com/en/kp-statistics",
     "fields": ("participant", "production_carats", "production_usd", "exports_carats",
                "exports_usd", "importing_participant"),
     "frequency": "annual", "snapshot": "calendar year", "publish_utc": "12:00",
     "lag_days": 270, "licence": "free, public", "available": True,
     "why": "a MIRROR statistic in a trade designed to be hard to track: what Freetown and "
            "Monrovia say they exported against what Antwerp, Dubai and Ramat Gan say they "
            "imported from them, and the gap is the measurement",
     "pit_warning": "published with a long and irregular lag and restated; an absent participant "
                    "year is UNMEASURED and is never interpolated"},
    {"name": "Port of Lome and Port of Cotonou monthly throughput with the transit split",
     "root": "https://www.togoport.tg",
     "fields": ("total_tonnage", "container_teu", "transshipment_teu", "transit_tonnage",
                "transit_by_country", "vessel_calls"),
     "frequency": "monthly / quarterly", "snapshot": "calendar month", "publish_utc": "12:00",
     "lag_days": 45, "licence": "free, public", "available": True,
     "why": "the TRANSIT-BY-COUNTRY split is what turns a national port statistic into a "
            "landlocked-Sahel supply observable: Burkina's and Niger's import bill crosses these "
            "two quays and nowhere else once the Algerian and Libyan routes are discounted",
     "pit_warning": "published irregularly and sometimes only in an annual report; a missing "
                    "month is UNMEASURED and this pack refuses to interpolate it"},
    {"name": "UN Comtrade MIRROR statistics for uranium, cashew, rutile and iron ore",
     "root": "https://comtradeplus.un.org",
     "fields": ("reporter", "partner", "hs_code", "reported_exports", "partner_reported_imports",
                "mirror_gap"),
     "frequency": "annual, monthly for some reporters", "snapshot": "calendar year",
     "publish_utc": "12:00", "lag_days": 365, "licence": "free, public (UN terms)",
     "available": True,
     "why": "for six of these eight the PARTNER's customs data is better than the country's own: "
            "French, EU, Indian, Vietnamese and Chinese import statistics are the lawful "
            "substitute for national trade series that are late, partial or suspended",
     "pit_warning": "a year late and heavily revised; it can date an era and can never condition "
                    "a week"},
    {"name": "a CFTC, exchange or dealer positioning series in XOF, SLE, LRD, GMD or CVE",
     "root": "", "fields": (), "frequency": "n/a", "snapshot": "", "publish_utc": "",
     "lag_days": 0, "licence": "", "available": False,
     "why": "DECLARED ABSENT: no future, no option and no COT contract exists anywhere for any "
            "of the six currencies in this pack. XOF and CVE are administered parities with no "
            "market to position in, and SLE, LRD and GMD are not deliverable offshore",
     "pit_warning": "DOES NOT EXIST: positioning in these currencies is UNMEASURED and is never "
                    "proxied by the EUR or ZAR COT leg, which are positions in other economies"},
    {"name": "retail margin or client-flow statistics for any of the eight",
     "root": "", "fields": (), "frequency": "n/a", "snapshot": "", "publish_utc": "",
     "lag_days": 0, "licence": "", "available": False,
     "why": "DECLARED ABSENT: none of the eight has a domestic retail margin-trading ecology. "
            "The WAEMU's CREPMF licenses intermediaries for the BRVM and publishes no retail "
            "positioning at all; Sierra Leone, Liberia, The Gambia and Guinea-Bissau have no "
            "securities regulator with a retail mandate; Cabo Verde's AGMVM oversees a bond "
            "market with negligible retail turnover",
     "pit_warning": "DOES NOT EXIST: no microstructure claim in this pack may rest on a retail "
                    "flow number, and the retail layer is read from PUBLIC COMMUNITIES at FRINGE "
                    "credibility instead"},
    {"name": "a national reserve or balance-of-payments series for NE, TG, BJ or GW",
     "root": "", "fields": (), "frequency": "n/a", "snapshot": "", "publish_utc": "",
     "lag_days": 0, "licence": "", "available": False,
     "why": "DECLARED ABSENT BY CONSTRUCTION: WAEMU reserves are POOLED and published for the "
            "UNION, so a national reserve number for Niger, Togo, Benin or Guinea-Bissau does "
            "not exist and cannot be derived. The lawful substitutes are the BCEAO's union "
            "aggregates, the country's IMF Article IV, and the partner mirror customs data",
     "pit_warning": "DOES NOT EXIST: any 'Nigerien reserves' figure a source quotes is an IMF "
                    "staff estimate with a review date on it, and it is treated as one"},
)

# --------------------------------------------------------------------------- terminology
#: FOUR GROUNDS AND THE PACK MEANS ALL FOUR. FRENCH is the administrative language of Niger, Togo
#: and Benin and of the BCEAO, the UMOA-Titres auction notices and every campaign decree.
#: PORTUGUESE is the language of Guinea-Bissau and Cabo Verde, of the two Boletins Oficiais and
#: of the cashew campaign decree that sets nine tenths of Bissau's export earnings -- and a
#: French-and-English crawl reads NEITHER of those two countries at all. HAUSA and ZARMA are what
#: the Nigerien interior actually trades in: the Arlit and Agadez markets, the cross-border
#: cattle and onion trade with Nigeria and the radio that reports both. ENGLISH is co-official in
#: Sierra Leone, Liberia and The Gambia, and KRIO is the Freetown street's own language, which is
#: why an English query there returns the export edition and not the market.
#:
#: The minor grounds are carried in their own orthographies rather than transliterated: EWE and
#: KABIYE (Togo), FON and YORUBA (Benin), MANDINKA and WOLOF (The Gambia) and the two CRIOULOS.
#: Those orthographies use Latin-Extended letters -- ɖ ƒ ŋ ɔ ɛ ʋ ɣ ẹ ọ ṣ ɓ ɗ -- which is a
#: codepoint test a crawl can actually run, and `has_african_script` is that test.
FRENCH_MARKERS: tuple[str, ...] = (
    "banque centrale", "taux de change", "campagne cotonniere", "prix plancher", "egrenage",
    "uranium", "permis minier", "oleoduc", "redevance", "port autonome", "corridor",
    "transit", "douane", "arrete", "decret", "journal officiel", "appel d'offres",
    "bons du tresor", "hivernage", "soudure", "secheresse", "harmattan", "niebe", "mil",
    "sorgho", "oignon", "betail", "noix de cajou", "anacarde", "phosphate", "clinker",
    "peche artisanale", "licence de peche", "envois de fonds", "sanctions", "frontiere",
    "filiere coton", "trafic portuaire", "guichet unique", "sources concordantes", "piraterie",
    "golfe de Guinee", "registre maritime", "pavillon de complaisance", "marche obligataire",
    "coton")
PORTUGUESE_MARKERS: tuple[str, ...] = (
    "banco central", "taxa de cambio", "escudo", "castanha de caju", "preco de referencia",
    "campanha de comercializacao", "boletim oficial", "decreto", "orcamento do estado",
    "importacao", "exportacao", "pescas", "licenca de pesca", "turismo", "remessas dos "
    "emigrantes", "combustivel", "porto", "ilhas", "safra", "inflacao", "juros", "alfandega",
    "estatistica", "arroz", "caju", "divida publica", "bolsa de valores", "obrigacoes",
    "relatorio", "movimento", "fontes", "dormidas", "tonelagem")
HAUSA_MARKERS: tuple[str, ...] = (
    "farashin", "kasuwa", "zinariya", "auduga", "gwamnati", "banki", "kudi", "hatsi",
    "shinkafa", "gero", "dawa", "albasa", "wake", "shanu", "iyaka", "ciniki", "haraji",
    "man fetur", "ruwan sama", "yunwa", "ma'adinai", "makamashi", "sanarwa", "jarida",
    "kayayyaki", "kasuwanci", "tallafi", "kungiyar", "majiyoyi", "binciken", "tattalin arziki",
    "takardar", "adadin", "hasashen", "yanayin", "noma", "matakin", "babban banki",
    "kasuwannin")
ZARMA_MARKERS: tuple[str, ...] = ("habu", "nooru", "wura", "hawru", "hari")
KRIO_MARKERS: tuple[str, ...] = (
    "makit", "moni", "prays", "dayamon", "gomɛnt", "biznɛs", "wetin", "tiday", "kɔntri",
    "bɔku", "rays")
MANDE_MARKERS: tuple[str, ...] = (
    "gerte", "xaalis", "wurus", "jaay", "jënd", "mbay", "luumo", "tiyo", "sanoo", "kodoo",
    "jula")

#: The Latin-Extended letters the Ewe, Kabiye, Fon, Yoruba and Krio orthographies use and that
#: no English or French text contains. A codepoint test, which is what a crawler can run.
_AFRICAN_LETTERS: frozenset[str] = frozenset(
    "ɖƒŋɔɛʋɣɓɗẹọṣƆƐŊƁƊỌẸṢǐɛ̀ɔ̀")

TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "SC-A": ("uranium", "permis minier", "societe des mines de l'Air", "Arlit", "yellowcake",
             "combustible nucleaire", "Euratom", "retrait du permis", "nationalisation",
             "ma'adinai", "sanarwa", "makamashi"),
    "SC-B": ("oleoduc", "brut d'Agadem", "terminal de Seme", "chargement", "exportation de "
             "petrole", "differend frontalier", "man fetur", "iyaka", "reprise des "
             "chargements", "barils par jour"),
    "SC-C": ("sanctions", "CEDEAO", "AES", "Alliance des Etats du Sahel", "retrait",
             "fermeture des frontieres", "corridor", "frontiere", "kasuwanci", "haraji",
             "kayayyaki", "bons du tresor"),
    "SC-D": ("hivernage", "soudure", "secheresse", "harmattan", "mil", "sorgho", "niebe",
             "betail", "ruwan sama", "hatsi", "gero", "dawa", "wake", "yunwa", "shanu"),
    "SC-E": ("pavillon de complaisance", "registre maritime", "tonnage brut", "port en lourd",
             "immatriculation", "flotte petroliere", "re-immatriculation", "shipping register",
             "flag state", "Liberian registry"),
    "SC-F": ("minerai de fer", "Yekepa", "chemin de fer de Buchanan", "concession miniere",
             "expedition de minerai", "iron ore concession", "rail corridor", "Buchanan port"),
    "SC-G": ("caoutchouc naturel", "hevea", "Harbel", "saigneurs", "plantation", "rubber "
             "concession", "dual currency", "dollarisation", "moni", "prays"),
    "SC-H": ("port autonome de Lome", "tirant d'eau", "transbordement", "conteneurs",
             "transit", "corridor Lome-Ouagadougou", "camions en attente", "trafic portuaire",
             "kayayyaki", "ciniki"),
    "SC-I": ("campagne cotonniere", "egrenage", "prix plancher", "coton graine", "fibre de "
             "coton", "NSCT", "producteurs de coton", "auduga", "intrants", "engrais"),
    "SC-J": ("phosphate", "clinker", "ciment", "extraction de phosphate", "engrais",
             "Hahotoe", "Kpeme", "exportation de phosphate"),
    "SC-K": ("port autonome de Cotonou", "corridor Cotonou-Niamey", "transit nigerien",
             "terminal petrolier", "Seme-Kpodji", "guichet unique", "douane", "camions"),
    "SC-L": ("noix de cajou", "anacarde", "transformation locale", "zone industrielle",
             "GDIZ", "Glo-Djigbe", "interdiction d'exportation", "noix brutes", "caju"),
    "SC-M": ("coton", "AIC", "interprofession", "prix d'achat aux producteurs", "campagne",
             "egrenage", "frontiere nigeriane", "contrebande", "auduga", "farashin"),
    "SC-N": ("rutile", "ilmenite", "sables mineralises", "titane", "bauxite", "Sherbro",
             "mineral sands", "mining lease", "makit", "gomɛnt"),
    "SC-O": ("redenomination", "nouveau leone", "trois zeros", "taux de change", "enchere de "
             "devises", "bureau de change", "inflation", "moni", "prays", "bɔku"),
    "SC-P": ("diamants", "processus de Kimberley", "certificat d'origine", "exploitation "
             "artisanale", "Kono", "Tonkolili", "dayamon", "carats", "licence minière"),
    "SC-Q": ("arachide", "gerte", "campagne arachidiere", "reexportation", "envois de fonds",
             "tourisme", "xaalis", "jaay", "jënd", "luumo", "mbay", "tiyo"),
    "SC-R": ("castanha de caju", "campanha de comercializacao", "preco de referencia",
             "decreto", "safra", "arroz", "exportacao", "alfandega", "divida publica"),
    "SC-S": ("escudo", "paridade", "Banco de Cabo Verde", "turismo", "remessas dos emigrantes",
             "pescas", "combustivel", "ilhas", "porto", "inflacao", "orcamento do estado"),
    "SC-T": ("piraterie", "golfe de Guinee", "enlevement d'equipage", "prime de risque de "
             "guerre", "escorte navale", "petroliers", "assurance maritime", "iyaka"),
    "SC-U": ("parite fixe", "franc CFA", "garantie du Tresor", "compte d'operations",
             "taxa de cambio", "paridade fixa", "flottement", "devaluation", "xaalis"),
    "SC-V": ("accord de peche", "licence de pesca", "thoniers", "peche artisanale",
             "pescas", "licenca de pesca", "chalutiers", "farine de poisson", "zone economique "
             "exclusive"),
    "SC-W": ("jour ferie", "Tabaski", "Korite", "Aid el-Kebir", "Mouloud", "carnaval",
             "feriado", "Sexta-Feira Santa", "Babbar Sallah", "Karamar Sallah", "sanarwa",
             "vodun"),
}


def _words(text: str) -> list[str]:
    return ["".join(ch for ch in w if ch.isalpha() or ch == "'").lower()
            for w in str(text).split()]


def _has_marker(text: str, markers: Iterable[str]) -> bool:
    """True when a multi-word marker appears as a substring, or a single-word marker appears as
    a WHOLE WORD. The word test matters: 'Niger' must not read as the Zarma 'hari' fragment and
    'Mali' must not read as a French particle."""
    low = str(text).lower()
    words = set(_words(text))
    for m in markers:
        marker = m.lower()
        if " " in marker or "'" in marker:
            if marker in low:
                return True
        elif marker in words:
            return True
    return False


def has_french(text: str) -> bool:
    """True when the text carries French administrative or trade vocabulary this pack queries in.
    French is the language of the BCEAO, the auction notices and every campaign decree in NE, TG
    and BJ."""
    return _has_marker(text, FRENCH_MARKERS)


def has_portuguese(text: str) -> bool:
    """True when the text carries Portuguese vocabulary. GUINEA-BISSAU AND CABO VERDE ARE
    INVISIBLE TO A FRENCH-AND-ENGLISH CRAWL, which is the single strongest reason this pack
    exists as a multi-jurisdiction one rather than as a francophone one."""
    return _has_marker(text, PORTUGUESE_MARKERS)


def has_hausa(text: str) -> bool:
    """True when the text carries Hausa (or Zarma) vocabulary. The Nigerien interior trades,
    broadcasts and argues in these; the French corner of Niamey is not the Nigerien ground."""
    return _has_marker(text, HAUSA_MARKERS) or _has_marker(text, ZARMA_MARKERS)


def has_krio(text: str) -> bool:
    """True when the text carries Krio vocabulary. Freetown's market talk is Krio and its
    English-language press is the export edition."""
    return _has_marker(text, KRIO_MARKERS)


def has_mande(text: str) -> bool:
    """True when the text carries Mandinka, Wolof or Zarma vocabulary -- the Gambian and Nigerien
    rural grounds, where the groundnut and cattle trade is actually discussed."""
    return _has_marker(text, MANDE_MARKERS) or _has_marker(text, ZARMA_MARKERS)


def has_african_script(text: str) -> bool:
    """True when the text uses the Latin-Extended letters of the Ewe, Kabiye, Fon, Yoruba or
    Krio orthographies. No English or French string contains one, which makes it a clean test."""
    return any(ch in _AFRICAN_LETTERS for ch in str(text))


def has_native(text: str) -> bool:
    """True when a query is written in ANY of this pack's native grounds rather than in plain
    English. Four of the six tests are WORD tests because French, Portuguese, Hausa and Wolof are
    Latin-script languages and a substring test on them produces nonsense."""
    return (has_french(text) or has_portuguese(text) or has_hausa(text) or has_krio(text)
            or has_mande(text) or has_african_script(text))


def french_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    rows = TERMINOLOGY if terminology is None else terminology
    flat = {t for terms in rows.values() for t in terms}
    return [m for m in FRENCH_MARKERS if any(m in t.lower() for t in flat)]


def portuguese_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    rows = TERMINOLOGY if terminology is None else terminology
    flat = {t for terms in rows.values() for t in terms}
    return [m for m in PORTUGUESE_MARKERS if any(m in t.lower() for t in flat)]


def hausa_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    rows = TERMINOLOGY if terminology is None else terminology
    flat = {t for terms in rows.values() for t in terms}
    return [m for m in HAUSA_MARKERS if any(m in t.lower() for t in flat)]


def term_count(terminology: Mapping[str, Iterable[str]] | None = None) -> int:
    rows = TERMINOLOGY if terminology is None else terminology
    return len({t for terms in rows.values() for t in terms})


# --------------------------------------------------------------------------- sources
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
        "sc_bceao", "BCEAO and UMOA-Titres: the CPM communique, the monthly bulletin, the "
                    "balance of payments for the union, and the WEEKLY sovereign auction "
                    "results BY ISSUER for Niger, Togo, Benin and Guinea-Bissau",
        layer="official",
        roots=("https://www.bceao.int", "https://www.bceao.int/fr/publications",
               "https://www.umoatitres.org", "https://edenpub.bceao.int"),
        queries=("communique comite de politique monetaire", "taux de change parite fixe",
                 "bons du tresor adjudication resultats", "appel d'offres emission Niger",
                 "balance des paiements UEMOA", "banque centrale bulletin mensuel",
                 "reserves de change zone UEMOA"),
        languages=("fr",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public (BCEAO terms)",
        notes="THE AUCTION PAGE IS THE ONE THAT MATTERS. A single monetary policy serves eight "
              "countries, so the only NATIONAL financial signal Niger, Togo, Benin and "
              "Guinea-Bissau emit is their own cut-off and bid-to-cover, week by week, and the "
              "Niger-minus-Benin spread is what measured the 2023 sanctions"),
    source_class(
        "sc_ne_state", "Niger: Institut National de la Statistique, the Ministere des Mines, the "
                       "Ministere des Finances budget documents and the Ministere du Petrole",
        layer="official",
        roots=("https://www.stat-niger.org", "https://www.mines.gouv.ne",
               "https://www.finances.gouv.ne", "https://www.ins.ne"),
        queries=("permis minier uranium retrait", "production d'uranium Niger",
                 "loi de finances Niger", "indice des prix a la consommation Niamey",
                 "exportation de petrole brut Agadem", "redevance miniere",
                 "ma'adinai a Nijar", "sanarwa daga ma'aikatar ma'adinai"),
        languages=("fr", "ha"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="NIGER'S STATISTICAL PLANE NARROWED SHARPLY AFTER JULY 2023: publication slipped, "
              "several series stopped and ministry sites went intermittently dark. That is a "
              "MEASURED constraint, not a reason to stop reading -- the lawful substitutes are "
              "the BCEAO regional aggregates, the IMF Article IV, Euratom and partner mirror "
              "customs, and every one of them is named in NO_LAWFUL_GROUND"),
    source_class(
        "sc_tg_state", "Togo: INSEED (CPI, national accounts), the Ministere de l'Economie et "
                       "des Finances, the OTR customs and revenue authority and the Ministere "
                       "des Mines et de l'Energie",
        layer="official",
        roots=("https://inseed.tg", "https://finances.gouv.tg", "https://www.otr.tg",
               "https://mines.gouv.tg"),
        queries=("indice harmonise des prix a la consommation Togo", "loi de finances Togo",
                 "recettes douanieres OTR", "production de phosphate Togo",
                 "campagne cotonniere prix plancher", "commerce exterieur Togo"),
        languages=("fr", "ee"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the OTR customs receipts are the highest-frequency fiscal series Togo publishes "
              "and they move with the PORT, which is the mechanism SC-H is built on"),
    source_class(
        "sc_bj_state", "Benin: INStaD (the statistics institute), the Secretariat General du "
                       "Gouvernement for decrees, the Ministere de l'Economie et des Finances "
                       "and the Agence de Developpement de la Zone Industrielle (GDIZ)",
        layer="official",
        roots=("https://instad.bj", "https://sgg.gouv.bj", "https://finances.bj",
               "https://gdiz.bj"),
        queries=("decret interdiction exportation noix de cajou brutes",
                 "zone industrielle Glo-Djigbe transformation", "loi de finances Benin",
                 "indice des prix Benin", "campagne cotonniere Benin prix d'achat",
                 "statistiques du commerce exterieur Benin"),
        languages=("fr", "fon", "yo"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE DECREE IS THE EVENT of SC-L: the raw-cashew export restriction and the GDIZ "
              "processing mandate are gazetted acts with commencement dates, and the SGG posts "
              "the text rather than a summary of it"),
    source_class(
        "sc_sl_state", "Sierra Leone: Bank of Sierra Leone (MPC, auctions, reserves), Statistics "
                       "Sierra Leone (CPI, trade), the National Minerals Agency and the Ministry "
                       "of Finance",
        layer="official",
        roots=("https://www.bsl.gov.sl", "https://www.statistics.sl", "https://nmalr.gov.sl",
               "https://mof.gov.sl"),
        queries=("monetary policy rate Sierra Leone", "redenomination new leone",
                 "foreign exchange auction results", "rutile production licence",
                 "consumer price index Freetown", "makit prays tiday",
                 "gomɛnt sɛl mayn laysɛns"),
        languages=("en", "kri"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the BSL is the only central bank in the pack with a real policy rate AND a real "
              "float; its 2022 redenomination circulars are the primary citation for SC-O's "
              "boundary, and reading them is what stops a 1000x step being read as a crash"),
    source_class(
        "sc_lr_state", "Liberia: Central Bank of Liberia (dual-currency statistics), LISGIS "
                       "(CPI, national accounts), the Ministry of Finance and Development "
                       "Planning and the National Port Authority",
        layer="official",
        roots=("https://www.cbl.org.lr", "https://www.lisgis.gov.lr", "https://mfdp.gov.lr",
               "https://www.npa.gov.lr"),
        queries=("Central Bank of Liberia monthly statistical bulletin",
                 "Liberian dollar exchange rate buying selling", "dollarization deposits share",
                 "iron ore shipments Buchanan", "national budget Liberia calendar year",
                 "consumer price index Monrovia"),
        languages=("en",), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE CBL PUBLISHES BOTH CURRENCY LEGS, which is unusual and useful: the LRD rate "
              "and the dollarisation share are separately readable, so 'the currency fell' and "
              "'the economy tightened' can be told apart here and in no other jurisdiction here"),
    source_class(
        "sc_gm_state", "The Gambia: Central Bank of The Gambia (MPC, the MONTHLY remittance "
                       "series, bureau survey), the Gambia Bureau of Statistics and the Ministry "
                       "of Finance and Economic Affairs",
        layer="official",
        roots=("https://www.cbg.gm", "https://www.gbosdata.org", "https://www.mofea.gm",
               "https://www.gbos.gov.gm"),
        queries=("Central Bank of The Gambia monetary policy committee statement",
                 "remittance inflows monthly Gambia", "dalasi exchange rate bureau",
                 "groundnut trade season producer price", "gerte jaay xaalis",
                 "luumo mbay tiyo"),
        languages=("en", "mnk", "wo"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the monthly remittance print is the best single series in this pack for a small "
              "economy: a COUNTED inflow, published monthly, in a country where it is a very "
              "large share of GDP, with a seasonal shape anybody can falsify"),
    source_class(
        "sc_lusophone_state", "Cabo Verde and Guinea-Bissau: Banco de Cabo Verde, INE Cabo "
                              "Verde, the Ministerio das Financas, the Boletim Oficial, and "
                              "Guinea-Bissau's INE and Ministerio da Economia e Financas",
        layer="official",
        roots=("https://www.bcv.cv", "https://ine.cv", "https://www.mf.gov.cv",
               "https://www.stat-guinebissau.com"),
        queries=("taxa de cambio escudo paridade euro", "boletim oficial decreto",
                 "orcamento do estado Cabo Verde", "remessas dos emigrantes",
                 "preco de referencia castanha de caju", "campanha de comercializacao caju",
                 "estatisticas do comercio externo", "inflacao indice de precos"),
        languages=("pt", "kea", "pov"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE PORTUGUESE HALF OF THE PACK, AND THE HALF A FRANCOPHONE CRAWL NEVER REACHES. "
              "The Banco de Cabo Verde publishes a real statistical series; Guinea-Bissau's INE "
              "publishes very little, which is declared per layer in NO_LAWFUL_GROUND rather "
              "than hidden behind Cabo Verde's fuller plane"),
    # ---- institutional
    source_class(
        "sc_registry", "The Liberian Registry (LISCR): published fleet statistics, marine "
                       "notices, flag-state circulars and the registry's own tonnage releases",
        layer="institutional",
        roots=("https://www.liscr.com", "https://www.liberianregistry.com",
               "https://www.liscr.com/marine-notices"),
        queries=("Liberian registry fleet statistics deadweight tonnage",
                 "flag state marine notice sanctions compliance", "registre maritime tonnage",
                 "vessel registration gross tonnage ranking", "pavillon de complaisance flotte"),
        languages=("en", "fr"), access_label="PUBLIC_WITH_TERMS", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free to read; the registry's terms govern reuse",
        notes="THE MOST MARKET-RELEVANT INSTITUTION IN LIBERIA and the reason SC-E exists. A "
              "flag state's own census of a sixth of world deadweight tonnage, with the type mix "
              "that makes it a tanker-capacity reading and the marine notices that record when "
              "the registry de-flags sanctioned tonnage -- which is grey-fleet formation, dated"),
    source_class(
        "sc_bvc_brvm", "Bolsa de Valores de Cabo Verde, the BRVM and CREPMF for the WAEMU, and "
                       "the BOAD development bank in Lome",
        layer="institutional",
        roots=("https://www.bvc.cv", "https://www.brvm.org", "https://www.crepmf.org",
               "https://www.boad.org"),
        queries=("bolsa de valores de Cabo Verde cotacoes", "obrigacoes do tesouro Cabo Verde",
                 "BRVM capitalisation emprunt obligataire", "CREPMF visa emission",
                 "BOAD financement projet"),
        languages=("pt", "fr"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the BVC is the ONLY domestic exchange in the seven non-BRVM jurisdictions here "
              "and it is tiny; it is registered as a STATE and never as a price, and it is what "
              "stops the institutional layer being declared absent for Cabo Verde"),
    source_class(
        "sc_kp_wna_esa", "The Kimberley Process statistics, the World Nuclear Association's "
                         "public country profiles and the Euratom Supply Agency's annual report",
        layer="institutional",
        roots=("https://kimberleyprocess.com/en/kp-statistics", "https://world-nuclear.org",
               "https://euratom-supply.ec.europa.eu", "https://www.iaea.org/resources/databases"),
        queries=("Kimberley Process annual statistics Sierra Leone Liberia carats",
                 "world nuclear association Niger uranium country profile",
                 "Euratom supply agency annual report origin of natural uranium",
                 "approvisionnement en uranium naturel origine", "uranium production Niger"),
        languages=("en", "fr"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE THREE LAWFUL SUBSTITUTES FOR SERIES THE COUNTRIES THEMSELVES NO LONGER "
              "PUBLISH. Euratom answers 'how much European fuel is Nigerien' when Niamey does "
              "not; Kimberley answers 'how many carats left Freetown' with the importers' "
              "figures beside it; the WNA profile carries the mine-by-mine history"),
    source_class(
        "sc_regional_bodies", "UEMOA, ECOWAS/CEDEAO and the AES, the Port Management "
                              "Association of West and Central Africa, and the EITI country "
                              "reports for Niger, Liberia, Sierra Leone and Togo",
        layer="institutional",
        roots=("https://www.uemoa.int", "https://www.ecowas.int",
               "https://www.agpaoc-pmawca.org", "https://eiti.org/countries"),
        queries=("communique final sommet CEDEAO sanctions", "retrait Alliance des Etats du "
                 "Sahel", "tarif exterieur commun UEMOA", "statistiques portuaires AGPAOC",
                 "ITIE rapport Niger uranium recettes", "EITI report Liberia iron ore revenue"),
        languages=("fr", "en", "pt"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE COMMUNIQUE IS THE EVENT of SC-C: the sanctions of 2023-07-30, their lifting "
              "on 2024-02-24 and the withdrawal effective 2025-01-29 were summit decisions, so "
              "the corridor's cost changed on a communique and not on a market"),
    # ---- academic
    source_class(
        "sc_openalex", "OpenAlex, CORE, SSRN, RePEc and theses.fr for the francophone doctorate "
                       "corpus, and RCAAP for the lusophone one",
        layer="academic",
        roots=("https://openalex.org", "https://core.ac.uk", "https://www.theses.fr",
               "https://www.rcaap.pt", "https://ideas.repec.org"),
        queries=("franc CFA parite fixe croissance these", "economie du Niger uranium rente",
                 "filiere coton Benin Togo productivite", "castanha de caju Guine-Bissau "
                 "economia", "remessas dos emigrantes Cabo Verde crescimento",
                 "corridor portuaire Sahel couts de transport"),
        languages=("fr", "pt", "en"), access_label="OPEN_DATA", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="open access aggregators; per-item licences vary",
        notes="the francophone thesis corpus is where the CFA and cotton literature actually "
              "lives, and theses.fr indexes it; RCAAP does the same for the lusophone work on "
              "Bissau and Praia that an anglophone search engine never surfaces"),
    source_class(
        "sc_universities", "Universite Abdou Moumouni (Niamey), Universite de Lome, Universite "
                           "d'Abomey-Calavi, Fourah Bay College, the University of Liberia, the "
                           "University of The Gambia and Uni-CV",
        layer="academic",
        roots=("https://www.uam.edu.ne", "https://univ-lome.tg", "https://www.uac.bj",
               "https://usl.edu.sl", "https://www.unicv.edu.cv"),
        queries=("laboratoire d'analyse et de recherche economique", "memoire de master "
                 "economie rurale", "revue de l'universite de Lome economie",
                 "recherche agronomique mil sorgho niebe", "economia e gestao tese Cabo Verde"),
        languages=("fr", "pt", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free to read; per-item licences vary",
        notes="thin and real. The Beninese LARES tradition and the Lome and Abomey-Calavi "
              "economics faculties do publish on cotton and the ports; Liberia's and "
              "Guinea-Bissau's academic economics output is close to nil and is declared absent "
              "per jurisdiction rather than papered over with a regional average"),
    source_class(
        "sc_agrhymet", "CILSS/AGRHYMET in Niamey, ICRISAT's Sahelian Center at Sadore, FEWS NET "
                       "and the FAO GIEWS country briefs",
        layer="academic",
        roots=("https://agrhymet.cilss.int", "https://fews.net", "https://www.fao.org/giews",
               "https://www.icrisat.org"),
        queries=("bulletin agrohydrometeorologique decadaire Sahel", "previsions saisonnieres "
                 "hivernage", "situation alimentaire soudure Niger", "bilan cerealier mil "
                 "sorgho", "ruwan sama da noma a Nijar", "cadre harmonise insecurite "
                 "alimentaire"),
        languages=("fr", "en", "ha"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="AGRHYMET IS IN NIAMEY, which is not a coincidence: the Sahel's agro-climatic "
              "science plane is headquartered in the country this pack's hardest domain is "
              "about, and its dekadal bulletins are the published clock SC-D runs on"),
    # ---- practitioner
    source_class(
        "sc_ecofin", "Agence Ecofin, Financial Afrik, Sika Finance, Togo First and the "
                     "francophone business press that actually covers the WAEMU auctions",
        layer="practitioner",
        roots=("https://www.agenceecofin.com", "https://financialafrik.com",
               "https://www.sikafinance.com", "https://www.togofirst.com"),
        queries=("adjudication bons du tresor Niger taux", "campagne cotonniere prix "
                 "producteurs", "trafic du port autonome de Lome conteneurs",
                 "exportation uranium Niger Orano", "noix de cajou transformation Benin GDIZ",
                 "marche obligataire UEMOA emission"),
        languages=("fr", "en"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free to read; reuse governed by the publishers",
        notes="the francophone business wires carry the auction results, the campaign prices and "
              "the port numbers DAYS before the institutional pages update, and they name the "
              "decree numbers, which is what makes a press date checkable against a gazette"),
    source_class(
        "sc_pra_assessments", "The price-reporting agencies whose assessments ARE the prices "
                              "this pack cannot trade: the uranium spot and long-term "
                              "assessments, the mineral-sands and cashew kernel assessments, "
                              "and the seaborne iron-ore indices",
        layer="practitioner",
        roots=("https://www.uxc.com", "https://www.fastmarkets.com",
               "https://www.public-ledger.com"),
        queries=("uranium spot price assessment U3O8", "rutile bulk price assessment",
                 "cashew kernel W320 price", "iron ore 62% Fe index"),
        languages=("en",), access_label="LICENSED", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="subscription; terms FORBID machine extraction",
        machine_use_allowed=False,
        notes="REGISTERED AND NEVER SCRAPED. These assessments are the honest benchmark for four "
              "of this pack's physical mechanisms and the desk may not fetch them, so the "
              "domains that need them are measured on the EXECUTABLE carriers with the weakness "
              "stated -- which is the difference between a declared limit and a silent one"),
    # ---- retail ecology
    source_class(
        "sc_retail_public", "The PUBLIC community ground: Hausa-, French-, Krio- and "
                            "Portuguese-language market and money pages, diaspora remittance "
                            "groups, and the YouTube channels that report street rates",
        layer="retail_ecology",
        roots=("https://www.youtube.com", "https://www.facebook.com", "https://www.reddit.com"),
        queries=("farashin kayayyaki a kasuwa yau", "taux de change parallele naira franc CFA",
                 "dalasi black market rate today", "prays fɔ dɔla tiday na Fritɔŋ",
                 "cambio paralelo escudo remessas", "cours du naira a la frontiere"),
        languages=("ha", "fr", "kri", "pt"), access_label="PUBLIC_SOCIAL", credibility="FRINGE",
        predictive_state="UNTESTED", licence="platform terms; public posts only",
        notes="KEPT AT LOW WEIGHT AND NEVER DROPPED. There is no lawful retail MARGIN ecology in "
              "any of the eight, so this layer is not a trading community at all -- it is the "
              "STREET RATE at the Niger-Nigeria border and the Freetown and Banjul bureaux, "
              "which is a real observable that no official series publishes daily"),
    # ---- app ecosystem
    source_class(
        "sc_mobile_money", "MOBILE MONEY AND PAYMENT RAILS, which ARE the app layer here: Orange "
                           "Money and Moov Africa in NE, TG and BJ, Wave, Africell Money and "
                           "Orange Money in SL, MTN MoMo and Orange Money in LR, Wave and QMoney "
                           "in GM, and the Vinti4 national card network in CV",
        layer="app_ecosystem",
        roots=("https://www.bceao.int/fr/publications/rapport-annuel-sur-les-services-financiers-"
               "numeriques", "https://www.gsma.com/mobilemoneymetrics",
               "https://www.sisp.cv", "https://www.arcep.bj"),
        queries=("services financiers numeriques rapport annuel UEMOA",
                 "transactions mobile money volume valeur", "Vinti4 rede de pagamentos "
                 "movimento", "kudi ta wayar hannu", "agents de transfert d'argent",
                 "remessas por telemovel"),
        languages=("fr", "pt", "ha", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public; GSMA metrics under its own terms",
        notes="DECLARING THIS LAYER ABSENT BECAUSE THERE IS NO METATRADER ECOLOGY WOULD BE "
              "READING THE WRONG COUNTRY. The BCEAO publishes an annual digital financial "
              "services report with transaction values for all eight WAEMU states, and Cabo "
              "Verde's SISP publishes Vinti4 volumes -- these are the only high-frequency "
              "NOMINAL series several of these economies produce"),
    source_class(
        "sc_port_customs_apps", "The ports' and customs' own single-window systems and tracking "
                                "portals: SEGUCE in Benin and Togo, the ASYCUDA/SYDONIA customs "
                                "deployments, and the corridor truck-tracking dashboards",
        layer="app_ecosystem",
        roots=("https://www.seguce.bj", "https://www.togoport.tg", "https://asycuda.org",
               "https://www.douanes.bj"),
        queries=("guichet unique du commerce exterieur declaration", "suivi des camions "
                 "corridor", "SYDONIA declaration en douane", "delais de passage portuaire",
                 "manifeste navire transit Niger"),
        languages=("fr", "en"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="portal terms; aggregate pages are public",
        notes="the single-window portals publish AGGREGATE clearance times and manifest counts "
              "even where the per-declaration data is closed, and clearance time is the corridor "
              "cost that SC-H and SC-K actually turn on"),
    # ---- media
    source_class(
        "sc_ne_media", "Niger: Le Sahel and ONEP, ActuNiger, Sahelien.com, Studio Kalangou "
                       "(Hausa and Zarma radio) and Tamtaminfo",
        layer="media",
        roots=("https://www.lesahel.org", "https://www.actuniger.com", "https://sahelien.com",
               "https://www.studiokalangou.org", "https://www.tamtaminfo.com"),
        queries=("Orano permis Imouraren retrait", "exportation de brut pipeline Benin Niger",
                 "sanctions CEDEAO levee frontiere", "farashin hatsi a kasuwa",
                 "sanarwa daga gwamnati", "habu nooru hari", "prix du mil a Niamey"),
        languages=("fr", "ha", "dje"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free to read; publishers' terms govern reuse",
        notes="STUDIO KALANGOU IS THE REASON THE HAUSA GROUND IS NOT OPTIONAL: it broadcasts and "
              "publishes in Hausa and Zarma across the interior, and its market and border "
              "reporting has no French equivalent. Several Nigerien outlets were suspended or "
              "restricted after July 2023, which is an ACCESS constraint and is recorded as one"),
    source_class(
        "sc_tg_bj_media", "Togo and Benin: Togo First, Republic of Togo, Togo Presse, La Nation, "
                          "Banouto and 24 Heures au Benin",
        layer="media",
        roots=("https://www.togofirst.com", "https://www.republicoftogo.com",
               "https://www.lanationbenin.info", "https://www.banouto.info",
               "https://24haubenin.info"),
        queries=("prix d'achat du coton graine campagne", "trafic conteneurs port de Lome",
                 "decret cajou transformation GDIZ", "corridor Cotonou Niamey camions",
                 "phosphate Kpeme exportation", "budget de l'Etat exercice"),
        languages=("fr", "ee", "fon"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free to read; publishers' terms govern reuse",
        notes="Togo First carries the port and cotton numbers earliest and names the decree; La "
              "Nation is the Beninese state paper and therefore the fastest route to the text "
              "of a gazetted act before the SGG posts the PDF"),
    source_class(
        "sc_anglophone_media", "Sierra Leone, Liberia and The Gambia: Awoko, Politico SL, "
                               "FrontPage Africa, the Daily Observer, The Point and Foroyaa",
        layer="media",
        roots=("https://awokonewspaper.sl", "https://www.politicosl.com",
               "https://frontpageafricaonline.com", "https://www.liberianobserver.com",
               "https://thepoint.gm", "https://foroyaa.net"),
        queries=("rutile mining lease community", "leone redenomination three zeros",
                 "iron ore shipment Buchanan rail", "groundnut season producer price Gambia",
                 "remittance inflows dalasi", "wetin de apin na makit", "gomɛnt sɛl laysɛns"),
        languages=("en", "kri", "mnk"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free to read; publishers' terms govern reuse",
        notes="Foroyaa and The Point carry the Gambian groundnut campaign and the remittance "
              "season from the villages rather than from the ministry, and Krio-language market "
              "reporting in Freetown reaches prices the English edition summarises away"),
    source_class(
        "sc_lusophone_media", "Cabo Verde and Guinea-Bissau: Expresso das Ilhas, A Nacao, "
                              "Inforpress, O Democrata and the Lusa and RTP Africa wires",
        layer="media",
        roots=("https://expressodasilhas.cv", "https://www.anacao.cv",
               "https://inforpress.cv", "https://odemocratagb.com", "https://www.lusa.pt"),
        queries=("preco de referencia da castanha de caju campanha",
                 "remessas dos emigrantes aumentaram", "turismo dormidas hoteis Cabo Verde",
                 "orcamento do estado aprovado", "exportacao de caju Guine-Bissau",
                 "taxa de cambio escudo euro"),
        languages=("pt", "kea", "pov"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free to read; publishers' terms govern reuse",
        notes="FOR GUINEA-BISSAU THE PRESS IS OFTEN THE ONLY DATA PLANE: the campaign price, the "
              "arrears and the cashew tonnage are reported by O Democrata and Lusa when no "
              "statistical office publishes them, and that is a measured substitution, not a "
              "shortcut"),
    # ---- archive
    source_class(
        "sc_journaux_officiels", "The eight gazettes: the Journal Officiel de la Republique du "
                                 "Niger, the JO de la Republique Togolaise, the JO de la "
                                 "Republique du Benin, the Sierra Leone Gazette, the Liberian "
                                 "acts of legislature, the Gambia Gazette and the two Boletins "
                                 "Oficiais",
        layer="archive",
        roots=("https://sgg.gouv.bj/doc/journal-officiel/", "https://www.imprensanacional.cv",
               "https://www.jo.gouv.ne", "https://www.sierra-leone.gov.sl"),
        queries=("journal officiel decret numero", "arrete interministeriel campagne",
                 "boletim oficial I serie decreto-lei", "gazette supplement act",
                 "loi de finances rectificative publication"),
        languages=("fr", "pt", "en"), access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="public acts; national printing-office terms",
        notes="THE GAZETTE IS THE CITATION and the press date is the lead. Every dated policy "
              "event in this pack -- the permit withdrawals, the cashew ban, the redenomination, "
              "the campaign prices -- has a gazette number behind it, and a cell is promoted on "
              "the gazette rather than on the report of it"),
    source_class(
        "sc_gallica_anom", "Gallica/BnF and the Archives nationales d'outre-mer: the Journal "
                           "officiel de l'Afrique occidentale francaise, the colonial-era "
                           "commodity bulletins and the pre-independence trade series",
        layer="archive",
        roots=("https://gallica.bnf.fr", "https://www.archivesnationales.culture.gouv.fr",
               "https://anom.archivesnationales.culture.gouv.fr"),
        queries=("journal officiel de l'Afrique occidentale francaise",
                 "bulletin economique arachide coton AOF", "statistiques du commerce colonial",
                 "rapport annuel territoire du Niger"),
        languages=("fr",), access_label="PUBLIC_ARCHIVE", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public (BnF terms)",
        notes="the cotton, groundnut and phosphate series of this coast run back to the 1900s in "
              "the AOF bulletins, digitised and searchable; that is the only place a "
              "century-long West African commodity series exists at all"),
    source_class(
        "sc_wayback", "The Internet Archive's Wayback Machine, as the POINT-IN-TIME vintage for "
                      "every page in this pack that overwrites itself",
        layer="archive",
        roots=("https://web.archive.org",),
        queries=("umoatitres.org resultats adjudication archive",
                 "liscr.com fleet statistics snapshot", "togoport.tg trafic archive",
                 "bcv.cv taxa de cambio historico"),
        languages=("fr", "en", "pt"), access_label="PUBLIC_ARCHIVE", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="Internet Archive terms",
        notes="THE AUCTION PORTAL, THE REGISTRY'S FLEET PAGE AND THE PORT DASHBOARDS ALL "
              "OVERWRITE IN PLACE. Their point-in-time history exists only here, which is why "
              "three of this pack's datasets carry pit_feasible=False and say so by name"),
    # ---- physical economy
    source_class(
        "sc_ports_physical", "The quays: Port Autonome de Lome, Port Autonome de Cotonou, the "
                             "Liberian National Port Authority (Monrovia and Buchanan), the "
                             "Freetown terminal and the Praia and Mindelo ports",
        layer="physical_economy",
        roots=("https://www.togoport.tg", "https://portdecotonou.bj", "https://www.npa.gov.lr",
               "https://www.enapor.cv"),
        queries=("trafic portuaire tonnage transit par pays", "escales de navires conteneurs",
                 "tirant d'eau quai a conteneurs", "movimento de carga porto",
                 "terminal petrolier chargement", "delais d'attente en rade"),
        languages=("fr", "pt", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE PHYSICAL LAYER IS THE POINT OF THIS PACK. Lome is the deepest container quay "
              "on the coast and Cotonou is Niger's outlet; the TRANSIT-BY-COUNTRY split is what "
              "turns a port statistic into a landlocked-Sahel supply observable, and both "
              "publish it"),
    source_class(
        "sc_agro_physical", "The agronomic plane: FEWS NET, AGRHYMET dekadal bulletins, USDA FAS "
                            "PSD and GAIN reports, FAO GIEWS and the Cadre Harmonise",
        layer="physical_economy",
        roots=("https://fews.net", "https://agrhymet.cilss.int", "https://apps.fas.usda.gov/psdonline",
               "https://www.fao.org/giews"),
        queries=("cadre harmonise analyse insecurite alimentaire Sahel",
                 "bulletin decadaire pluviometrie", "production cotonniere previsions campagne",
                 "cashew production forecast West Africa", "bilan cerealier deficit",
                 "ruwan sama hasashen noma"),
        languages=("fr", "en", "ha"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public (US and UN open data)",
        notes="the Sahel's rainfall, sowing and harvest clock is published by three independent "
              "bodies at dekadal frequency, which is a rare thing: an agronomic observable with "
              "a real lead and three sources that can contradict each other"),
    source_class(
        "sc_maritime_risk", "The Gulf of Guinea risk plane: the ICC International Maritime "
                            "Bureau Piracy Reporting Centre, MDAT-GoG, UKMTO and the Yaounde "
                            "Architecture's own reporting",
        layer="physical_economy",
        roots=("https://www.icc-ccs.org/piracy-reporting-centre",
               "https://www.mdat-gog.org", "https://www.ukmto.org"),
        queries=("piracy report Gulf of Guinea incidents kidnapping",
                 "piraterie golfe de Guinee enlevement equipage",
                 "war risk premium West Africa tanker", "alerte navire attaque au large",
                 "zone de risque assurance maritime"),
        languages=("en", "fr"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public (IMB terms on reuse)",
        notes="a counted incident series with locations and dates, which is what a war-risk "
              "premium is actually priced off; the region's share of world crew kidnapping rose "
              "to a peak and then fell sharply, and BOTH halves are in the same series"),
    # ---- source graph
    source_class(
        "sc_wire_graph", "The wire and aggregator graph: APA News, Agence Ecofin, AFP Afrique, "
                         "Lusa and RTP Africa for the lusophone half, and the aggregators that "
                         "republish all of them",
        layer="source_graph",
        roots=("https://www.apanews.net", "https://www.agenceecofin.com", "https://www.lusa.pt",
               "https://allafrica.com"),
        queries=("selon des sources concordantes", "de acordo com fontes oficiais",
                 "a rapporte l'agence", "citando o boletim oficial",
                 "kamar yadda majiyoyi suka ce", "communique repris par"),
        languages=("fr", "pt", "ha"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free to read; agency terms govern reuse",
        notes="THE GRAPH IS HOW A LEAK IS TOLD FROM A REPOST. Most 'news' in these eight "
              "countries is one agency item republished twelve times; following the citation "
              "back to the gazette or the communique is the only way to DATE an event before "
              "the official text appears"),
    source_class(
        "sc_cite_graph", "The institutional citation chain: which IMF, World Bank, AfDB and EU "
                         "documents cite which national statistic, and the ECOWAS/UEMOA "
                         "communique chain that the national press quotes",
        layer="source_graph",
        roots=("https://www.imf.org/en/Publications/CR", "https://data.worldbank.org",
               "https://www.afdb.org/en/documents", "https://eur-lex.europa.eu"),
        queries=("Article IV consultation staff report selected issues",
                 "rapport pays FMI Niger consultation", "relatorio do FMI Guine-Bissau",
                 "accord de partenariat dans le domaine de la peche protocole",
                 "sustainable fisheries partnership agreement protocol"),
        languages=("en", "fr", "pt"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public (institutional terms)",
        notes="EUR-Lex is the load-bearing root here: the EU fisheries protocols with Cabo "
              "Verde, The Gambia, Guinea-Bissau and Liberia are PUBLISHED LEGAL ACTS with "
              "reference tonnages, licence counts and financial contributions in the text, and "
              "they are the only hard numbers the fisheries domain has"),
)

#: NO LAYER IS BLANK FOR THE REGION AS A WHOLE, and that is the measurement rather than a claim
#: of completeness. The refusals that ARE real here are per-jurisdiction and per-layer, and with
#: eight jurisdictions of very different statistical capacity they are the most informative rows
#: in the file: Cabo Verde publishes a real macro plane and Guinea-Bissau publishes almost none,
#: and a regional average hides exactly that.
LAYER_ABSENCES: dict[str, str] = {}

#: THE MEASURED REFUSALS (L1.28a). Each row names the jurisdiction, the layer, what does not
#: exist, WHY, and THE NAMED LAWFUL SUBSTITUTE. A row with no substitute would be a shrug; a row
#: with one is a route.
NO_LAWFUL_GROUND: tuple[dict[str, str], ...] = (
    {"jurisdiction": "ne", "layer": "institutional",
     "reason": "NIGER HAS NO SECURITIES MARKET OF ITS OWN AND NO LISTED NIGERIEN COMPANY. The "
               "WAEMU's single exchange is the BRVM in Abidjan, which belongs to `west_africa`, "
               "and no Nigerien issuer trades on it. There is no national bond curve, no "
               "interbank yield series and no national reserve figure, because WAEMU reserves "
               "are pooled. LAWFUL SUBSTITUTE: the UMOA-Titres auction results BY ISSUER, which "
               "are national and weekly; the BCEAO's union aggregates; the IMF Article IV."},
    {"jurisdiction": "ne", "layer": "practitioner",
     "reason": "NO DOMESTIC SELL-SIDE RESEARCH EXISTS. Niger has no brokerage publishing "
               "research, no local rating agency coverage and no independent economic "
               "consultancy with a public output; what circulates is the francophone regional "
               "wire's coverage FROM Abidjan and Dakar. LAWFUL SUBSTITUTE: Agence Ecofin, "
               "Financial Afrik and Sika Finance, sourced above and labelled RELIABLE rather "
               "than AUTHORITATIVE precisely because they report Niger from outside it."},
    {"jurisdiction": "ne", "layer": "retail_ecology",
     "reason": "NO LAWFUL RETAIL MARGIN MARKET EXISTS. No broker is licensed to offer leverage "
               "to residents, the CREPMF's mandate covers the BRVM and not margin FX, and no "
               "regulator publishes a retail flow, exposure or margin statistic. LAWFUL "
               "SUBSTITUTE: the PUBLIC Hausa- and French-language street-rate ground at the "
               "Niger-Nigeria border, sourced above at FRINGE credibility -- it is a real "
               "observable and it is all there is."},
    {"jurisdiction": "gw", "layer": "institutional",
     "reason": "GUINEA-BISSAU HAS NO SECURITIES MARKET, NO EXCHANGE, NO DOMESTIC BOND MARKET AND "
               "NO CREDIT-RATING COVERAGE. It has no national reserve figure either, for the "
               "same pooling reason as Niger. LAWFUL SUBSTITUTE: the UMOA-Titres auctions where "
               "Bissau issues at all, the BCEAO union aggregates, and the IMF's small ECF "
               "programme documents, which are the only audited macro numbers the country has."},
    {"jurisdiction": "gw", "layer": "academic",
     "reason": "THERE IS NO INDEPENDENT DOMESTIC ACADEMIC ECONOMICS LITERATURE. Guinea-Bissau "
               "has no economics faculty producing a public research output and no domestic "
               "journal; decades of instability are the reason and it is not going to change "
               "inside this pack's horizon. LAWFUL SUBSTITUTE: the LUSOPHONE corpus -- RCAAP, "
               "Portuguese and Brazilian university theses on Bissau's cashew economy -- plus "
               "the IMF and World Bank country work, all sourced above."},
    {"jurisdiction": "gw", "layer": "practitioner",
     "reason": "NO SELL-SIDE, NO CONSULTANCY, NO NEWSLETTER. Nobody writes market commentary on "
               "Guinea-Bissau for money because there is no market to comment on. LAWFUL "
               "SUBSTITUTE: the lusophone press (O Democrata, Lusa) and the FAO/USDA cashew "
               "trade reporting, which is where the campaign price is actually discussed."},
    {"jurisdiction": "gw", "layer": "retail_ecology",
     "reason": "NO RETAIL FINANCIAL ECOLOGY OF ANY KIND: no brokerage, no margin, no published "
               "flow, and mobile-money penetration is the lowest of the eight. LAWFUL "
               "SUBSTITUTE: NONE THAT IS HONEST. The pack records this as a genuine hole rather "
               "than promoting the Crioulo social ground to a data plane it is not."},
    {"jurisdiction": "lr", "layer": "academic",
     "reason": "LIBERIA'S DOMESTIC ACADEMIC ECONOMICS OUTPUT IS CLOSE TO NIL. Two civil wars and "
               "the Ebola epidemic broke the university's research capacity and it has not been "
               "rebuilt; there is no domestic economics journal. LAWFUL SUBSTITUTE: the IMF "
               "Article IV and the World Bank's Liberia economic updates, the EITI reports on "
               "the iron-ore and rubber concessions, and the substantial ENGLISH-LANGUAGE "
               "MARITIME literature on open registries, which is where the flag-state mechanism "
               "is actually studied."},
    {"jurisdiction": "lr", "layer": "retail_ecology",
     "reason": "NO RETAIL MARGIN ECOLOGY AND NO SECURITIES MARKET. Liberia has no stock "
               "exchange and no licensed retail leverage. LAWFUL SUBSTITUTE: the CBL's published "
               "bureau and bank rates for BOTH currencies, which capture the only retail "
               "financial decision most Liberians make -- whether to hold LRD or USD."},
    {"jurisdiction": "sl", "layer": "retail_ecology",
     "reason": "NO AGGREGATE RETAIL POSITIONING EXISTS. There is no securities exchange in "
               "Sierra Leone and no licensed margin broker; the Bank of Sierra Leone publishes "
               "auction and bureau rates and no client flow. LAWFUL SUBSTITUTE: the published "
               "auction-minus-bureau spread, and the Krio-language street ground at FRINGE "
               "credibility."},
    {"jurisdiction": "gm", "layer": "institutional",
     "reason": "THE GAMBIA HAS NO STOCK EXCHANGE AND NO CORPORATE BOND MARKET. The institutional "
               "layer for this jurisdiction is the Treasury bill auction and the banking system, "
               "nothing more. LAWFUL SUBSTITUTE: the CBG's weekly auction results and its "
               "MONTHLY remittance series, which is the most useful high-frequency series any "
               "of the small jurisdictions here produces."},
    {"jurisdiction": "gm", "layer": "retail_ecology",
     "reason": "NO RETAIL MARGIN MARKET AND NO PUBLISHED CLIENT FLOW. LAWFUL SUBSTITUTE: the "
               "bureau survey the CBG publishes, whose seasonal widening around Tobaski and "
               "Christmas IS the retail signal in a remittance economy."},
    {"jurisdiction": "tg", "layer": "retail_ecology",
     "reason": "NO DOMESTIC RETAIL MARGIN ECOLOGY. The CREPMF licenses BRVM intermediaries and "
               "publishes no retail positioning, and the hard euro peg removes the FX "
               "speculation that would create one. LAWFUL SUBSTITUTE: the BCEAO's digital "
               "financial services report, whose mobile-money transaction values are the only "
               "high-frequency household-level nominal series Togo has."},
    {"jurisdiction": "bj", "layer": "retail_ecology",
     "reason": "THE SAME, AND FOR THE SAME REASON: a hard peg and no licensed margin. LAWFUL "
               "SUBSTITUTE: the BCEAO digital financial services report and the Beninese "
               "mobile-money and agent statistics, plus the NIGERIA-BORDER street market in "
               "naira, which is a real and violently moving price the official plane never "
               "quotes."},
    {"jurisdiction": "cv", "layer": "retail_ecology",
     "reason": "NEGLIGIBLE RETAIL SECURITIES TURNOVER AND NO MARGIN MARKET. The BVC exists but "
               "is overwhelmingly a bond market held by banks and the state, and the AGMVM "
               "publishes no retail flow. LAWFUL SUBSTITUTE: the Vinti4 national card network's "
               "published transaction volumes, which are a genuine high-frequency household "
               "consumption series and move with the TOURIST SEASON, which is the mechanism."},
    {"jurisdiction": "cv", "layer": "physical_economy",
     "reason": "CABO VERDE HAS NO EXTRACTIVE OR AGRICULTURAL PHYSICAL PLANE WORTH MINING: it is "
               "an archipelago with almost no arable land, no minerals and no pipeline. LAWFUL "
               "SUBSTITUTE: the physical economy that DOES exist and is published -- air and sea "
               "ARRIVALS, hotel bed-nights, the Mindelo BUNKERING volumes and the EU fisheries "
               "protocol's licensed tonnage. Declaring the layer absent because there is no mine "
               "would be reading the wrong country."},
)

#: NATIVE QUERY TERRITORIES -- what the deep-forest miner actually types, per layer. Every layer
#: carries at least one FRENCH, one PORTUGUESE and one HAUSA phrase, because those are the three
#: grounds a default crawl misses in this pack: French because the desk's crawl is anglophone,
#: Portuguese because two whole countries live in it, and Hausa because the Nigerien interior
#: does not argue in French.
QUERY_TERRITORIES: dict[str, tuple[str, ...]] = {
    "official": ("resultats des adjudications de bons du tresor", "taux de change parite fixe",
                 "preco de referencia da castanha de caju decreto",
                 "orcamento do estado receitas fiscais", "sanarwa daga babban banki",
                 "farashin hatsi a kasuwannin Nijar", "production d'uranium et redevance"),
    "institutional": ("registre maritime tonnage de la flotte",
                      "Kimberley Process statistics participant carats",
                      "bolsa de valores obrigacoes do tesouro",
                      "communique final du sommet de la CEDEAO",
                      "kungiyar tattalin arzikin yammacin Afirka",
                      "approvisionnement en uranium naturel Euratom"),
    "academic": ("these de doctorat economie du coton Afrique de l'Ouest",
                 "tese sobre a economia do caju na Guine-Bissau",
                 "franc CFA parite fixe croissance article",
                 "binciken tattalin arziki a Nijar", "recherche agronomique mil et niebe"),
    "practitioner": ("analyse du marche obligataire UEMOA", "note de conjoncture filiere coton",
                     "analise do sector do turismo Cabo Verde",
                     "hasashen farashin kayayyaki", "perspectives du trafic portuaire"),
    "retail_ecology": ("taux du naira au marche parallele frontiere",
                       "farashin dala a kasuwar bayan fage", "cambio paralelo escudo hoje",
                       "prays fɔ dɔla tiday", "cours du franc CFA a Lagos"),
    "app_ecosystem": ("transactions mobile money valeur rapport annuel",
                      "movimento da rede Vinti4 pagamentos",
                      "kudi ta wayar hannu adadin ma'amaloli",
                      "guichet unique du commerce exterieur delais",
                      "agents de mobile money par region"),
    "media": ("retrait du permis minier annonce", "reprise des chargements de brut",
              "campanha de comercializacao do caju arranca",
              "gwamnati ta sanar da matakin", "prix du sac de mil au marche",
              "kontena na tonelagem do porto"),
    "archive": ("journal officiel decret numero annee", "boletim oficial I serie decreto-lei",
                "bulletin economique de l'Afrique occidentale francaise",
                "takardar gwamnati ta hukuma", "gazette supplement mining act"),
    "physical_economy": ("trafic portuaire transit par pays de destination",
                         "movimento de carga e descarga no porto",
                         "bulletin decadaire pluviometrie Sahel",
                         "ruwan sama da yanayin noma", "expedition de minerai de fer Buchanan",
                         "piraterie golfe de Guinee incident"),
    "source_graph": ("selon des sources concordantes a Niamey",
                     "de acordo com fontes do ministerio",
                     "kamar yadda majiyoyi suka shaida", "communique repris par l'agence",
                     "citando o relatorio do FMI"),
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


def jurisdiction_layer_gaps() -> dict[str, tuple[str, ...]]:
    """THE PER-JURISDICTION REFUSAL TABLE, derived from `NO_LAWFUL_GROUND` and never typed twice.

    Eight jurisdictions of very different statistical capacity share ten layers here. A regional
    layer count says all ten are covered and is true; it hides that Guinea-Bissau fills four of
    them and Cabo Verde fills nine. This is the honest shape of that asymmetry.
    """
    out: dict[str, list[str]] = {code: [] for code in JURISDICTIONS}
    for row in NO_LAWFUL_GROUND:
        code = str(row["jurisdiction"])
        if code in out and row["layer"] not in out[code]:
            out[code].append(str(row["layer"]))
    return {k: tuple(v) for k, v in out.items()}


JURISDICTION_LAYER_GAPS: dict[str, tuple[str, ...]] = jurisdiction_layer_gaps()


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
            "jurisdiction_layer_gaps": JURISDICTION_LAYER_GAPS,
            "query_territory_counts": {k: len(v) for k, v in QUERY_TERRITORIES.items()},
            "rule": "ten layers, each carrying a source or named ABSENT with a reason; with "
                    "eight jurisdictions the real refusals are PER JURISDICTION and every one is "
                    "declared in NO_LAWFUL_GROUND WITH A NAMED LAWFUL SUBSTITUTE, because a "
                    "regional layer count that reads ten-of-ten hides the fact that Cabo Verde "
                    "fills nine layers and Guinea-Bissau fills four; fringe and unreliable "
                    "PUBLIC material is kept at low weight and never dropped; a page whose terms "
                    "forbid machine extraction is registered machine_use_allowed=false, never "
                    "scraped and never omitted"}


# --------------------------------------------------------------------------- datasets
#: TWENTY-TWO ROWS, SPREAD ACROSS THE TEN LAYERS, each with a `how_to_fetch` a collector can act
#: on. Only the twelve DATASET_FIELDS appear here: the framework's `DatasetRow` has no notes slot,
#: so a thirteenth key would arrive as a coercion note rather than as information.
DATASETS: tuple[dict[str, Any], ...] = (
    {"name": "UMOA-Titres auction results by issuer (NE, TG, BJ, GW)", "source": "UMOA-Titres",
     "coverage": "every WAEMU sovereign bill and bond auction, per issuer", "frequency": "weekly",
     "publication_lag_days": 0.0,
     "revisions": "never revised; each auction is a separate published result",
     "licence": "free, public", "history_from": "2013-01", "pit_feasible": False,
     "assets": ("EURUSD", "USDZAR"),
     "mechanism_families": ("fiscal_stress", "auction", "sanctions_regime"),
     "how_to_fetch": "umoatitres.org auction results section, one page per adjudication; the "
                     "portal SHOWS THE CURRENT SEASON and its archive is paginated rather than "
                     "downloadable, so the point-in-time vintage is a weekly crawl or the "
                     "Wayback snapshot -- pit_feasible is False for exactly that reason"},
    {"name": "BCEAO monetary and balance-of-payments statistics for the union",
     "source": "BCEAO", "coverage": "union-level monetary survey, reserves, BoP; NO national "
                                    "reserve series exists",
     "frequency": "monthly and annual", "publication_lag_days": 60.0,
     "revisions": "revised at each annual report", "licence": "free, public",
     "history_from": "1999-01", "pit_feasible": False,
     "assets": ("EURUSD", "USDZAR"),
     "mechanism_families": ("peg_regime", "reserve_adequacy", "carry_funding"),
     "how_to_fetch": "bceao.int publications and the EDEN statistical portal; the union "
                     "aggregate is the ONLY reserve series, and a request for a Nigerien or "
                     "Bissau-Guinean national number returns nothing because none exists"},
    {"name": "Port of Lome monthly traffic with the transit split by destination country",
     "source": "Port Autonome de Lome", "coverage": "tonnage, TEU, transshipment and transit by "
                                                    "landlocked destination",
     "frequency": "monthly, sometimes quarterly", "publication_lag_days": 45.0,
     "revisions": "restated in the annual report", "licence": "free, public",
     "history_from": "2010-01", "pit_feasible": False,
     "assets": ("CORN", "WHEAT", "SUGAR", "COTTON"),
     "mechanism_families": ("chokepoint", "physical_flow", "corridor_cost"),
     "how_to_fetch": "togoport.tg statistics pages and the annual report PDF; the dashboard "
                     "OVERWRITES, so archive each month's page -- the transit-by-country table "
                     "is the load-bearing part and it is the one most often omitted"},
    {"name": "Port of Cotonou monthly traffic and the Niger transit corridor volume",
     "source": "Port Autonome de Cotonou", "coverage": "tonnage, TEU, vehicles and the Niger "
                                                       "transit share",
     "frequency": "monthly / quarterly", "publication_lag_days": 60.0,
     "revisions": "restated annually", "licence": "free, public", "history_from": "2010-01",
     "pit_feasible": False, "assets": ("CORN", "WHEAT", "XBRUSD"),
     "mechanism_families": ("chokepoint", "physical_flow", "sanctions_regime"),
     "how_to_fetch": "portdecotonou.bj statistics section plus the Beninese customs (douanes.bj) "
                     "transit declarations; the 2023-2024 border closure appears in BOTH and "
                     "the difference between them is the informal half of the trade"},
    {"name": "Liberian Registry fleet statistics (count, GT, DWT, type mix, average age)",
     "source": "LISCR / Liberian Registry", "coverage": "the whole register, updated "
                                                        "continuously and published periodically",
     "frequency": "quarterly / annual", "publication_lag_days": 30.0,
     "revisions": "not revised; each release is a new snapshot", "licence": "free, public "
                                                                           "(registry terms)",
     "history_from": "2000-01", "pit_feasible": False,
     "assets": ("XBRUSD", "XTIUSD", "UK100"),
     "mechanism_families": ("capacity", "freight", "sanctions_regime"),
     "how_to_fetch": "liscr.com fleet pages for the current snapshot, the registry's press "
                     "releases for the dated announcements, and the UNCTAD Review of Maritime "
                     "Transport annex plus the IMO GISIS aggregates as the independent "
                     "cross-check; the registry page keeps no history, so archive it"},
    {"name": "Euratom Supply Agency annual report: origin shares and inventory cover",
     "source": "Euratom Supply Agency", "coverage": "natural uranium delivered to EU utilities "
                                                    "by country of origin, and years of cover",
     "frequency": "annual", "publication_lag_days": 180.0,
     "revisions": "occasionally restated in the following year's report",
     "licence": "free, public (EU open data)", "history_from": "2000", "pit_feasible": True,
     "assets": ("XNGUSD", "FRA40", "EUSTX50", "GER40"),
     "mechanism_families": ("supply_shock", "substitution", "inventory"),
     "how_to_fetch": "euratom-supply.ec.europa.eu annual report PDFs; the origin table and the "
                     "average contract price are in the statistics annex. THE INVENTORY-COVER "
                     "FIGURE IS THE ONE THAT MATTERS: it is why a Nigerien supply event is "
                     "predicted to move a price slowly and slightly, if at all"},
    {"name": "World Nuclear Association country profile: Niger mine production history",
     "source": "World Nuclear Association", "coverage": "tonnes U per mine per year, with the "
                                                        "permit and ownership history",
     "frequency": "annual, revised continuously", "publication_lag_days": 120.0,
     "revisions": "the page is edited in place as events occur",
     "licence": "free to read; WNA terms govern reuse", "history_from": "1971",
     "pit_feasible": False, "assets": ("XNGUSD", "FRA40", "EUSTX50"),
     "mechanism_families": ("supply_shock", "regime_break", "capacity"),
     "how_to_fetch": "world-nuclear.org country profile for Niger plus the OECD-NEA/IAEA Red "
                     "Book biennial for the reserve and production series; the WNA page is "
                     "EDITED IN PLACE, so the Wayback snapshot is the only vintage"},
    {"name": "Kimberley Process annual statistics for Sierra Leone and Liberia",
     "source": "Kimberley Process Certification Scheme",
     "coverage": "production and export carats and value per participant, with importing "
                 "participant detail",
     "frequency": "annual", "publication_lag_days": 270.0,
     "revisions": "participants restate; some years are missing entirely",
     "licence": "free, public", "history_from": "2004", "pit_feasible": True,
     "assets": ("XAUUSD", "USDZAR"),
     "mechanism_families": ("mirror_statistic", "informal_flow", "administered_price"),
     "how_to_fetch": "kimberleyprocess.com/en/kp-statistics, the public statistics tables by "
                     "participant and year; download both the exporter and the importer sides "
                     "and take the GAP -- a missing participant year is UNMEASURED and is "
                     "never interpolated"},
    {"name": "Central Bank of The Gambia monthly remittance inflows and the bureau survey",
     "source": "Central Bank of The Gambia",
     "coverage": "remittance inflows by month with source-country split, bureau and official "
                 "rates, reserves",
     "frequency": "monthly", "publication_lag_days": 40.0,
     "revisions": "revised for two to three months after the first print",
     "licence": "free, public", "history_from": "2010-01", "pit_feasible": False,
     "assets": ("SOYBEAN", "EURUSD", "USDZAR"),
     "mechanism_families": ("seasonal_flow", "transfer", "carry_funding"),
     "how_to_fetch": "cbg.gm statistics and MPC-statement annexes, plus gbosdata.org for the "
                     "matching trade series; the FIRST print is what a point-in-time cell must "
                     "use and the revision is large enough to change a sign"},
    {"name": "Central Bank of Liberia dual-currency statistics and the dollarisation share",
     "source": "Central Bank of Liberia",
     "coverage": "LRD and USD rates (buying and selling, bank and bureau), deposit and currency "
                 "shares by denomination, reserves",
     "frequency": "monthly", "publication_lag_days": 45.0,
     "revisions": "revised at the annual report", "licence": "free, public",
     "history_from": "2008-01", "pit_feasible": False,
     "assets": ("XBRUSD", "XCUUSD", "USDZAR"),
     "mechanism_families": ("dollarisation", "carry_funding", "regime_control"),
     "how_to_fetch": "cbl.org.lr monthly and annual statistical bulletins (PDF); the "
                     "dollarisation share is in the monetary survey tables and is the field that "
                     "makes Liberia the CONTROL for the other two floats"},
    {"name": "Bank of Sierra Leone FX auction results and the redenomination circulars",
     "source": "Bank of Sierra Leone",
     "coverage": "wholesale auction volumes and clearing rates, bureau survey, MPC decisions, "
                 "and the 2022 redenomination circulars",
     "frequency": "weekly auctions; quarterly MPC", "publication_lag_days": 3.0,
     "revisions": "auction results are not revised", "licence": "free, public",
     "history_from": "2015-01", "pit_feasible": False,
     "assets": ("XAUUSD", "XZNUSD", "USDZAR"),
     "mechanism_families": ("regime_break", "auction", "redenomination"),
     "how_to_fetch": "bsl.gov.sl publications: the auction results page and the 2022 "
                     "redenomination circulars. ANY SERIES CROSSING 2022-07-01 MUST BE RESCALED "
                     "BY 1000 and the circular is the citation that says so"},
    {"name": "Benin and Togo cotton campaign farmgate prices and ginned output",
     "source": "AIC Benin / NSCT Togo / ICAC", "coverage": "announced farmgate price per kg, "
                                                           "seed cotton collected, lint produced",
     "frequency": "annual (campaign)", "publication_lag_days": 30.0,
     "revisions": "provisional output is restated at the campaign close",
     "licence": "free, public", "history_from": "2000", "pit_feasible": True,
     "assets": ("COTTON",),
     "mechanism_families": ("administered_price", "supply_response", "campaign_calendar"),
     "how_to_fetch": "the interprofessions' price notices reported by Togo First, La Nation and "
                     "Agence Ecofin with the arrete number, cross-checked against the ICAC and "
                     "USDA FAS cotton production estimates for the same campaign"},
    {"name": "Guinea-Bissau cashew campaign reference price and exported tonnage",
     "source": "Government of Guinea-Bissau / Boletim Oficial / FAO",
     "coverage": "the decreed reference farmgate price, the campaign opening date, and raw "
                 "cashew export tonnage and value",
     "frequency": "annual (campaign)", "publication_lag_days": 60.0,
     "revisions": "tonnage is restated; the decreed price is not",
     "licence": "free, public", "history_from": "2005", "pit_feasible": True,
     "assets": ("WHEAT", "CORN", "USDCNH"),
     "mechanism_families": ("administered_price", "terms_of_trade", "monocrop"),
     "how_to_fetch": "the Boletim Oficial for the decree, O Democrata and Lusa for the date, and "
                     "UN Comtrade's INDIAN and VIETNAMESE import statistics as the mirror -- "
                     "the buyers count better than the seller does here"},
    {"name": "Nigerien crude export loadings at Seme-Kpodji",
     "source": "trade press, Beninese customs and partner customs mirrors",
     "coverage": "cargo loadings and their dates from first export in May 2024",
     "frequency": "irregular (per cargo)", "publication_lag_days": 7.0,
     "revisions": "press reports are corrected; customs data is restated",
     "licence": "free to read; publishers' terms govern reuse", "history_from": "2024-05",
     "pit_feasible": False, "assets": ("XBRUSD", "XTIUSD"),
     "mechanism_families": ("capacity_ramp", "supply_shock", "political_interruption"),
     "how_to_fetch": "Agence Ecofin, ActuNiger and Reuters cargo reports for the dates, then UN "
                     "Comtrade and the CHINESE customs mirror for the tonnage; the series is "
                     "SHORT -- it begins in May 2024 -- and no cell may pretend otherwise"},
    {"name": "IMB Piracy Reporting Centre incidents in the Gulf of Guinea",
     "source": "ICC International Maritime Bureau",
     "coverage": "incident type, position, vessel type and crew kidnapping, quarterly and annual",
     "frequency": "quarterly", "publication_lag_days": 21.0,
     "revisions": "late reports are added to the following quarter", "licence": "free, public",
     "history_from": "1992", "pit_feasible": True,
     "assets": ("XBRUSD", "XTIUSD", "USDCNH"),
     "mechanism_families": ("risk_premium", "freight", "event_reaction"),
     "how_to_fetch": "icc-ccs.org piracy reporting centre quarterly PDFs plus the MDAT-GoG "
                     "advisories for the intra-quarter dates; the series records BOTH the rise "
                     "to a regional peak in crew kidnapping and the sharp fall after it, which "
                     "is what makes it a two-sided test rather than a scare"},
    {"name": "EU Sustainable Fisheries Partnership Agreement protocols (CV, GM, GW, LR)",
     "source": "EUR-Lex / European Commission DG MARE",
     "coverage": "reference tonnage, vessel categories, licence counts and financial "
                 "contributions, per protocol and per year",
     "frequency": "per protocol (typically four to six years)", "publication_lag_days": 0.0,
     "revisions": "amended by Council decision", "licence": "free, public (EU open data)",
     "history_from": "1990", "pit_feasible": True,
     "assets": ("SOYBEAN", "CORN", "USDCNH"),
     "mechanism_families": ("licence_regime", "physical_flow", "policy_timetable"),
     "how_to_fetch": "eur-lex.europa.eu search for the fisheries partnership protocols by "
                     "country; the reference tonnage and the licence table are IN THE LEGAL TEXT "
                     "-- hard numbers in a domain that otherwise has almost none"},
    {"name": "AGRHYMET and FEWS NET dekadal rainfall, sowing and Cadre Harmonise phases",
     "source": "CILSS/AGRHYMET, FEWS NET, FAO GIEWS",
     "coverage": "dekadal rainfall and vegetation indices, sowing dates, and the Cadre Harmonise "
                 "food-insecurity phase by region",
     "frequency": "dekadal (ten-day) and seasonal", "publication_lag_days": 5.0,
     "revisions": "the seasonal outlook is revised through the campaign", "licence": "free, public",
     "history_from": "1998", "pit_feasible": True,
     "assets": ("CORN", "WHEAT", "COTTON", "SUGAR"),
     "mechanism_families": ("weather", "supply_response", "seasonal_flow"),
     "how_to_fetch": "agrhymet.cilss.int bulletins and fews.net country pages with the Cadre "
                     "Harmonise maps; THREE INDEPENDENT BODIES publish overlapping series, which "
                     "is the rare case where a weather claim has its own cross-check"},
    {"name": "USDA FAS PSD and GAIN: West African cotton, cashew and grain balances",
     "source": "USDA Foreign Agricultural Service",
     "coverage": "area, yield, production, exports and stocks by country and marketing year",
     "frequency": "monthly (PSD) and irregular (GAIN)", "publication_lag_days": 0.0,
     "revisions": "revised monthly; the marketing-year definition matters more than the revision",
     "licence": "free, public (US open data)", "history_from": "1960",
     "pit_feasible": True, "assets": ("COTTON", "CORN", "WHEAT", "SOYBEAN"),
     "mechanism_families": ("balance_sheet", "supply_response", "release_surprise"),
     "how_to_fetch": "apps.fas.usda.gov/psdonline bulk download, filtered to BJ, TG, NE, SL, LR, "
                     "GM, GW and CV, plus the GAIN attache reports for the campaign narrative; "
                     "PSD carries a full vintage archive, which is why this row is pit_feasible"},
    {"name": "UN Comtrade mirror statistics: uranium, cashew, rutile, iron ore and rubber",
     "source": "UN Comtrade", "coverage": "reporter and partner trade by HS code for all eight",
     "frequency": "annual, monthly for some reporters", "publication_lag_days": 365.0,
     "revisions": "heavily revised", "licence": "free, public (UN terms)",
     "history_from": "1995", "pit_feasible": True,
     "assets": ("XCUUSD", "XZNUSD", "USDCNH", "WHEAT"),
     "mechanism_families": ("mirror_statistic", "physical_flow", "informal_flow"),
     "how_to_fetch": "comtradeplus.un.org API with the reporter set to the PARTNERS (FR, EU27, "
                     "IN, VN, CN, AE) rather than to these eight, because the partner's customs "
                     "service is the better counter in six of the eight cases"},
    {"name": "BCEAO annual digital financial services report: mobile money by member state",
     "source": "BCEAO", "coverage": "accounts, active users, transaction volume and value, agent "
                                    "networks, per WAEMU member state",
     "frequency": "annual", "publication_lag_days": 180.0,
     "revisions": "restated in the following year's report", "licence": "free, public",
     "history_from": "2015", "pit_feasible": True,
     "assets": ("EURUSD", "CORN", "SUGAR"),
     "mechanism_families": ("nominal_demand", "transfer", "financial_deepening"),
     "how_to_fetch": "bceao.int annual report on digital financial services in WAEMU; the "
                     "per-country transaction VALUE table is the only high-frequency "
                     "household-level nominal series Niger, Togo, Benin and Guinea-Bissau have"},
    {"name": "IMF Article IV staff reports and programme documents for the eight",
     "source": "International Monetary Fund",
     "coverage": "the full macro framework: fiscal, external, reserves, arrears and debt, with "
                 "a selected-issues paper per country",
     "frequency": "annual (irregular for NE since 2023)", "publication_lag_days": 30.0,
     "revisions": "each consultation restates the previous vintage", "licence": "free, public",
     "history_from": "2000", "pit_feasible": True,
     "assets": ("EURUSD", "USDZAR"),
     "mechanism_families": ("macro_framework", "regime_break", "programme_clock"),
     "how_to_fetch": "imf.org country pages, the CR series PDFs and the accompanying data "
                     "annexes. FOR SIX OF THESE EIGHT THIS IS THE MACRO DATA PLANE, and the "
                     "consultation DATE is the release -- a fact SC-U conditions on"},
    {"name": "Cabo Verde tourism arrivals, bed-nights and Mindelo bunkering volumes",
     "source": "INE Cabo Verde / ENAPOR / Banco de Cabo Verde",
     "coverage": "arrivals by source market, hotel bed-nights, port calls and bunker fuel "
                 "volumes",
     "frequency": "monthly and quarterly", "publication_lag_days": 60.0,
     "revisions": "quarterly series are revised once", "licence": "free, public",
     "history_from": "2005-01", "pit_feasible": True,
     "assets": ("XBRUSD", "EURUSD", "UK100"),
     "mechanism_families": ("seasonal_flow", "nominal_demand", "bunkering"),
     "how_to_fetch": "ine.cv statistics portal (Turismo) and the Banco de Cabo Verde bulletin "
                     "for the FX side; the arrivals series is the physical economy of an "
                     "archipelago with no mines and no farmland, which is why the physical layer "
                     "for CV is declared absent in its extractive sense and sourced in this one"},
)

# --------------------------------------------------------------------------- actors
#: TWENTY-SEVEN ACTORS. The floor is twelve for ONE country; a pack answering for eight that
#: stopped at twelve would have read two countries and guessed six times. Every row carries all
#: eleven fields and the FALSIFIER is the one that decides whether the row is a research object
#: or a story. Every national champion here -- the uranium operator, the registry administrator,
#: the iron-ore concessionaire, the rutile miner, the rubber concession, the terminal operators
#: -- appears HERE and never as an instrument (two-lane order, 2026-09-06).
ACTORS: tuple[dict[str, Any], ...] = (
    # ---------------------------------------------------------------- Niger
    {"name": "The Nigerien state's mining authority and the CNSP after 26 July 2023",
     "holds": "the uranium permits themselves -- Somair, Cominak and the undeveloped Imouraren "
              "deposit -- plus the state's carried equity in the operating companies and the "
              "royalty regime that prices them",
     "forced_to": ("fund a budget that lost its external financing when ECOWAS sanctions closed "
                   "the borders and froze the accounts on 2023-07-30",
                   "renegotiate or revoke concessions to demonstrate sovereignty to a domestic "
                   "audience that the previous arrangements had not served",
                   "keep the mines physically producing, because a stopped mine earns nothing "
                   "for anybody and restarting one takes years"),
     "when": "the coup is a single dated event (2023-07-26); the permit actions are dated "
             "administrative acts through 2024 and 2025",
     "information": ("the true state of the treasury during the sanctions window",
                     "which buyers are still lifting yellowcake and on what terms",
                     "what the alternative operators and financiers will actually pay"),
     "constraints": ("a landlocked country whose exports must cross a border it has quarrelled "
                     "with, and whose only practical routes are Cotonou and Lome",
                     "no national monetary instrument at all: the BCEAO sets the rate",
                     "uranium sold under multi-year contracts, so a revocation changes ownership "
                     "far faster than it changes deliveries",
                     "a security situation that has closed districts to mining before"),
     "instruments": ("XNGUSD", "FRA40", "EUSTX50", "GER40"),
     "counterparties": ("the French state-owned operator and its Nigerien subsidiaries",
                        "European utilities buying through Euratom-notified contracts",
                        "the Beninese and Togolese ports and customs services",
                        "ECOWAS, and after January 2024 the AES partners Mali and Burkina"),
     "observables": ("the gazetted permit decisions and their dates",
                     "the Euratom Supply Agency's annual origin table",
                     "Nigerien export tonnage in the FRENCH and EU customs mirrors",
                     "the UMOA-Titres cut-off Niger pays against Benin's"),
     "impact": "a supply story on a commodity this desk cannot trade, whose executable "
               "consequence is a small, slow revision to the perceived cost of the European "
               "nuclear leg -- so the pack tests power and gas substitution and says on its face "
               "that it expects little",
     "persistence": "a regime, not an event: the post-2023 arrangements are a new ownership era "
                    "and do not decay",
     "falsifier": "the Euratom origin table shows no fall in the Nigerien share of EU deliveries "
                  "across 2023-2025 and European utility inventory cover is unchanged -- in "
                  "which case the permit actions moved ownership and not fuel, and SC-A's whole "
                  "price leg dies while the fiscal leg survives",
     "notes": "THE ACTOR THE WHOLE PACK'S HARDEST DOMAIN TURNS ON, and the one most likely to be "
              "over-read: sovereignty acts make headlines and utility inventories are measured "
              "in years"},
    {"name": "Orano's Nigerien operating companies (Somair, Cominak, Imouraren)",
     "holds": "the mining and processing assets at Arlit, the accumulated yellowcake stock on "
              "site, and the technical capacity to run them",
     "forced_to": ("keep care-and-maintenance obligations on a depleted Cominak and a "
                   "never-built Imouraren",
                   "move product out through a border that has been closed and reopened",
                   "answer to a European parent whose own customers are utilities with "
                   "contractual delivery obligations"),
     "when": "continuously, with dated inflection points at each permit action",
     "information": ("the true on-site stock and the state of the plant",
                     "the delivery schedules it owes European utilities",
                     "the cost of the alternative routes out of Arlit"),
     "constraints": ("no export route that does not cross another state",
                     "a depleting orebody at Somair and a deposit at Imouraren that has never "
                     "been economic at prevailing prices",
                     "a parent that cannot be seen to abandon European supply security"),
     "instruments": ("XNGUSD", "FRA40", "EUSTX50"),
     "counterparties": ("the Nigerien state as licensor and shareholder",
                        "European utilities and the Euratom Supply Agency as contract witness",
                        "the Beninese and Togolese transit corridors"),
     "observables": ("the parent's own dated statements on permits and operations",
                     "French and EU customs imports of uranium ores and concentrates from Niger",
                     "the Euratom average contract price"),
     "impact": "the physical half of SC-A: whether metal actually moves, as distinct from who "
               "owns the licence to move it",
     "persistence": "quarters to years; a mine restart is slow in both directions",
     "falsifier": "French and EU customs show Nigerien uranium imports continuing at trend "
                  "through the permit disputes, which would mean the dispute is a corporate one "
                  "and not a supply one",
     "notes": "AN ACTOR AND NEVER AN INSTRUMENT. The parent is a single name and the two-lane "
              "order forbids hunting it; what is tradable is the power and gas leg its customers "
              "sit on"},
    {"name": "The Euratom Supply Agency and the European utility fuel buyers",
     "holds": "the contract portfolio for EU reactor fuel and the legal right of co-signature on "
              "every supply contract, plus the published inventory-cover statistic",
     "forced_to": ("diversify origins by policy after 2022, away from Russian enrichment and "
                   "conversion as well as away from single-origin natural uranium",
                   "maintain multi-year cover so that no single origin can interrupt generation",
                   "publish the origin shares and the average contract price annually"),
     "when": "contracts are struck continuously; the disclosure is ANNUAL and roughly half a "
             "year late",
     "information": ("the forward contract book years before it is disclosed",
                     "which utilities are short and which are covered",
                     "the substitution options across Kazakh, Canadian, Australian and Namibian "
                     "supply"),
     "constraints": ("reactors that cannot be refuelled on short notice and inventories measured "
                     "in years, which is exactly what BLUNTS a supply scare",
                     "a conversion and enrichment bottleneck that matters more than the ore"),
     "instruments": ("XNGUSD", "FRA40", "EUSTX50", "GER40"),
     "counterparties": ("the French, Belgian, Czech, Finnish, Spanish and Swedish utilities",
                        "Kazakh, Canadian, Australian, Namibian and Nigerien producers",
                        "the conversion and enrichment operators"),
     "observables": ("the annual origin-share table and the inventory-cover years",
                     "the average contract price against the reported spot assessment",
                     "EU customs imports of natural uranium by origin"),
     "impact": "THE BUFFER THAT DECIDES SC-A'S SIGN. If cover is long, a Nigerien interruption is "
               "a headline; if cover is short, it is a cost. The pack reads the buffer before it "
               "reads the headline",
     "persistence": "structural; the buffer changes over years",
     "falsifier": "a Nigerien interruption coincides with a measurable fall in EU inventory cover "
                  "and a rise in the average contract price, which would UPGRADE this channel "
                  "from weak to real -- the falsifier here runs in the pack's favour and is "
                  "stated in that direction on purpose",
     "notes": "the one actor in this pack whose disclosure is genuinely authoritative, annual and "
              "slow -- which is why SC-A's horizon is quarters and not sessions"},
    {"name": "The CNPC-operated Agadem field, the Zinder refinery and the Seme-Kpodji terminal",
     "holds": "the Agadem oilfield, the roughly 1,980 km export line to the Beninese coast, the "
              "loading terminal, and the domestic refinery at Zinder that serves the home market",
     "forced_to": ("load cargoes on a schedule the lender and offtaker set",
                   "cross Benin, whose government has its own dispute with Niamey",
                   "supply the domestic market at administered pump prices, which is a separate "
                   "and competing obligation"),
     "when": "per cargo, from the first export loading in May 2024",
     "information": ("the loading schedule and the field's actual deliverability",
                     "the financing terms against which cargoes are pledged",
                     "the state of the line's pumping stations and its security"),
     "constraints": ("a single export route through a single foreign terminal",
                     "a line that has been physically attacked and politically interrupted",
                     "a field whose deliverability has never been tested at plateau"),
     "instruments": ("XBRUSD", "XTIUSD"),
     "counterparties": ("the Chinese national oil company as operator and lender",
                        "the Beninese state, customs and port authority",
                        "the buyers lifting at Seme-Kpodji"),
     "observables": ("cargo loading dates reported by the trade press and the customs mirrors",
                     "Beninese transit declarations",
                     "Chinese crude import statistics by origin"),
     "impact": "roughly 90,000 b/d is small against world supply and LARGE against Niger's "
               "external accounts, so the pack tests the fiscal and corridor legs first and the "
               "XBRUSD leg second, with matched non-event days",
     "persistence": "the interruptions are episodic and the ramp is structural",
     "falsifier": "the loading interruptions of 2024 show no measurable effect on Chinese import "
                  "volumes from Niger in the following quarter, which would mean the "
                  "interruptions were a negotiation and not a supply event",
     "notes": "the newest physical flow in the whole African roster and the only one with a "
              "published political on/off switch"},
    {"name": "The Nigerien cross-border traders: onions, cowpeas and cattle into Nigeria",
     "holds": "the informal trade that is a very large share of Niger's real external economy "
              "and appears in nobody's customs data",
     "forced_to": ("move livestock and produce to the Nigerian market on a seasonal calendar "
                   "that peaks around Tabaski",
                   "price in naira at the border and settle in CFA at home, absorbing a cross "
                   "rate that moved violently through the 2023-2024 naira devaluations",
                   "route around border closures rather than stop trading"),
     "when": "continuous, with a sharp seasonal peak in the weeks before Aid el-Kebir",
     "information": ("the real border cross rate and the real volumes, neither of which any "
                     "state publishes",
                     "which crossings are open on a given week"),
     "constraints": ("two currency regimes meeting at one border: a hard euro peg on one side "
                     "and a devaluing float on the other",
                     "closures that are political and announced, and closures that are neither"),
     "instruments": ("SUGAR", "CORN", "SOYBEAN"),
     "counterparties": ("Nigerian wholesale buyers in Kano, Katsina and Sokoto",
                        "Nigerien pastoralists and market cooperatives",
                        "the customs services on both sides, formally and otherwise"),
     "observables": ("the street XOF/NGN rate reported in the Hausa-language ground",
                     "Nigerian market price series for onions, cowpeas and cattle",
                     "the Cadre Harmonise food-security phase for the Nigerien regions"),
     "impact": "the transmission channel from a Nigerian macro event into Nigerien household "
               "income; it reaches this pack's instruments only through the food and feed "
               "complex and is labelled WEAK there",
     "persistence": "seasonal within a year; structural across years",
     "falsifier": "Nigerien border-market prices show no response to the naira devaluations of "
                  "2023-2024 once the harvest season is controlled for, which would mean the "
                  "border cross rate is not a real transmission channel",
     "notes": "THE INTERACTION WITH `ng` LIVES HERE, and it is the reason a Nigerien pack that "
              "read only French sources would miss half its own economy"},
    # ---------------------------------------------------------------- Liberia
    {"name": "The Liberian International Ship and Corporate Registry (LISCR)",
     "holds": "the world's second-largest ship register by tonnage -- roughly a sixth of world "
              "deadweight -- administered from the United States under a concession from the "
              "Liberian state, plus the flag-state authority that goes with it",
     "forced_to": ("compete continuously with Panama and the Marshall Islands, because "
                   "re-flagging takes weeks and owners move",
                   "enforce IMO and sanctions obligations or lose standing with port states",
                   "publish its own fleet size and composition, because size is its marketing"),
     "when": "registrations are continuous; the statistics are published quarterly and annually",
     "information": ("which owners are moving tonnage onto and off the flag, before the "
                     "aggregate is published",
                     "which vessels are being de-flagged for sanctions or detention reasons"),
     "constraints": ("port-state control regimes that punish a flag with a poor detention record",
                     "sanctions enforcement obligations that conflict with registry revenue",
                     "a Liberian state that receives a share of the revenue and sets none of the "
                     "policy"),
     "instruments": ("XBRUSD", "XTIUSD", "UK100"),
     "counterparties": ("shipowners and managers worldwide, especially tanker owners",
                        "the IMO, port-state control regimes and the sanctions authorities",
                        "the Liberian Maritime Authority in Monrovia"),
     "observables": ("the registry's own published vessel count, gross and deadweight tonnage "
                     "and type mix",
                     "UNCTAD's Review of Maritime Transport annex and the IMO GISIS aggregates",
                     "the registry's marine notices and de-flagging announcements"),
     "impact": "a QUANTITY reading on future freight supply and on grey-fleet formation: growth "
               "in tanker deadweight on an open register is capacity, and a surge of older "
               "tanker tonnage arriving is the published footprint of a shadow fleet forming",
     "persistence": "structural, with episodic jumps when a sanctions regime pushes tonnage "
                    "between registers",
     "falsifier": "changes in Liberian-flag tanker tonnage show no relationship to subsequent "
                  "dirty-tanker freight rates or to the age profile of the world tanker fleet "
                  "once total fleet growth is controlled for -- which would make the register a "
                  "commercial statistic and not a capacity one",
     "notes": "THE MOST UNDER-USED PUBLIC SERIES IN THIS PACK. A flag state publishes a census of "
              "a sixth of world tonnage and almost nobody reads it as an economic series"},
    {"name": "The Yekepa iron-ore concession and the Buchanan rail and port",
     "holds": "the Nimba iron-ore deposits, the 240 km rail to Buchanan and the port's ore "
              "handling capacity, under a long-term mineral development agreement with the state",
     "forced_to": ("ship on a published expansion timetable it has committed to with the "
                   "government and its lenders",
                   "share or not share the rail with third-party users, which has been the "
                   "central political argument over the concession",
                   "meet community and county-level obligations written into the agreement"),
     "when": "shipments are continuous; the expansion milestones and the agreement "
             "renegotiations are dated",
     "information": ("the true ramp schedule and the rail's real throughput ceiling",
                     "the grade and blend of the concentrate against the index specification"),
     "constraints": ("one rail line and one port for the whole concession",
                     "a seaborne market dominated by four far larger exporters, so Liberia is a "
                     "price taker at every volume it can reach",
                     "a rail-access dispute that has repeatedly reached the legislature"),
     "instruments": ("XCUUSD", "XZNUSD", "UK100"),
     "counterparties": ("the Liberian state as licensor", "Chinese and European steel buyers",
                        "the Guinean Nimba deposits' developers, who want the same rail",
                        "the National Port Authority at Buchanan"),
     "observables": ("shipment counts and tonnage from the port and the customs data",
                     "the EITI Liberia report's production and revenue tables",
                     "the dated milestones of the expansion and the rail-access decisions"),
     "impact": "WEAK ON THE ORE PRICE AND REAL ON THE CORRIDOR: the tonnage is small against "
               "world seaborne supply, and the rail-access decision is a large event for GUINEAN "
               "ore, which is why this actor's most important edge points at a neighbour",
     "persistence": "years; a rail decision changes a decade of flows",
     "falsifier": "Liberian shipment tonnage shows no relationship to the seaborne index or to "
                  "West African Capesize rates at any lag, which would confine this actor to the "
                  "fiscal and corridor legs -- where it would still belong",
     "notes": "the honest expectation is that the CORRIDOR matters and the PRICE does not, and "
              "saying so before the test is what stops a weak result being written up as a "
              "strong one"},
    {"name": "The Central Bank of Liberia in a dual-currency economy",
     "holds": "the Liberian dollar issue, the reserve position, and the policy of a country "
              "where the US dollar is legal tender alongside it",
     "forced_to": ("publish both currency legs and the dollarisation share, because both "
                   "circulate",
                   "manage a note supply that has been the subject of its own public scandals",
                   "defend a float with reserves that are small against a partially dollarised "
                   "deposit base"),
     "when": "monthly statistical publication; policy decisions are irregular",
     "information": ("the true currency-in-circulation split and the banks' dollar positions",
                     "the size of the informal dollar economy around the concessions"),
     "constraints": ("partial dollarisation, which removes most of the monetary transmission a "
                     "float is supposed to provide",
                     "an economy whose foreign earnings come from three concessions and a "
                     "registry"),
     "instruments": ("XBRUSD", "XCUUSD", "USDZAR"),
     "counterparties": ("commercial banks and the bureaux",
                        "the IMF under successive programmes",
                        "the concessions, which pay in dollars and are the main FX source"),
     "observables": ("the published LRD and USD buying and selling rates",
                     "the dollarisation share in the monetary survey",
                     "reserves in months of imports"),
     "impact": "the CONTROL LEG of SC-U: a float whose currency prices only half the economy is "
               "the case that separates 'the currency moved' from 'the economy tightened'",
     "persistence": "structural; dollarisation changes over decades",
     "falsifier": "Liberian inflation responds to the LRD rate exactly as Sierra Leone's does to "
                  "the leone, which would mean dollarisation is not doing the work this pack "
                  "assigns it and Liberia is not a control at all",
     "notes": "the whole value of this actor is as a CONTROL, and a control that turns out to "
              "behave like the treatment is a finding, not a failure"},
    {"name": "The Harbel rubber concession and the Liberian smallholder tappers",
     "holds": "the largest contiguous rubber plantation in the world by some measures, the "
               "processing capacity beside it, and a smallholder outgrower network",
     "forced_to": ("tap and process on a biological calendar that does not care about prices",
                   "replant on a seven-year cycle that fixes supply years ahead",
                   "sell into a market where synthetic rubber is the marginal substitute"),
     "when": "continuous production with a wintering period of reduced tapping",
     "information": ("the replanting profile, which is forward supply",
                     "the smallholder gate price against the world price"),
     "constraints": ("a tree crop with a multi-year lag between price and supply",
                     "a history of labour and civil-conflict disruption",
                     "no rubber contract the desk can trade"),
     "instruments": ("XBRUSD", "USDCNH"),
     "counterparties": ("tyre manufacturers and traders",
                        "the smallholder outgrowers", "the Liberian state as licensor"),
     "observables": ("Liberian rubber export tonnage in the customs mirrors",
                     "the EITI report's rubber revenue line",
                     "Chinese natural-rubber import volumes as the demand side"),
     "impact": "WEAK and named weak: natural rubber substitutes against synthetic, whose "
               "feedstock is in the crude chain, and China is the marginal buyer of both",
     "persistence": "years, because the supply response is a tree",
     "falsifier": "Liberian rubber export volumes show no co-movement with the crude complex or "
                  "with Chinese import volumes at any lag, which would retire this actor's edge "
                  "and leave it as a fiscal observable",
     "notes": "carried because it is a real, large, published flow and because saying 'this one "
              "is weak' about a famous name is how a pack keeps its strong claims credible"},
    # ---------------------------------------------------------------- Togo
    {"name": "The Port Autonome de Lome and its container and transshipment operators",
     "holds": "the deepest container quay on the West African coast, the region's largest "
              "transshipment hub, and the northern corridor to Burkina Faso and Niger",
     "forced_to": ("keep draught and crane capacity ahead of vessel size, or lose transshipment "
                   "to Abidjan and Tema",
                   "clear landlocked cargo under transit regimes it does not control",
                   "publish traffic statistics, because volume is its argument for investment"),
     "when": "continuous operations; monthly and annual statistical publication",
     "information": ("the transit split by destination country before it is published",
                     "berth congestion and dwell times in real time",
                     "which shipping lines are shifting transshipment calls"),
     "constraints": ("a single corridor road north that is long, and increasingly insecure in "
                     "its northern reaches",
                     "customs clearance times it does not set",
                     "competition from Abidjan, Tema and Cotonou for the same landlocked cargo"),
     "instruments": ("CORN", "WHEAT", "SUGAR", "COTTON"),
     "counterparties": ("the Burkinabe and Nigerien importers and their transit agents",
                        "the container lines using Lome as a hub",
                        "the OTR customs and revenue authority"),
     "observables": ("monthly tonnage and TEU with the transshipment and transit split",
                     "OTR customs receipts, which move with the port",
                     "corridor truck-tracking and clearance-time dashboards"),
     "impact": "the physical cost of everything the Sahel imports; a corridor disruption raises "
               "the landed price of grain, fuel and fertiliser for three landlocked countries at "
               "once",
     "persistence": "weeks to months for a disruption; years for a capacity change",
     "falsifier": "Lome's transit tonnage to Burkina and Niger shows no fall during the 2023-2024 "
                  "sanctions window and no rise when Cotonou's route closed, which would mean "
                  "the corridors are not substitutes and the chokepoint story is wrong",
     "notes": "THE SINGLE BEST PHYSICAL OBSERVABLE IN THE PACK: monthly, published, split by "
              "destination, and covering the whole import bill of three landlocked economies"},
    {"name": "La Nouvelle Societe Cotonniere du Togo and the cotton producers' unions",
     "holds": "the ginning capacity, the seed and input distribution, and the announced farmgate "
              "price for the campaign",
     "forced_to": ("announce a guaranteed purchase price BEFORE sowing, which fixes the "
                   "state's exposure to the world price for a whole season",
                   "supply inputs on credit against a harvest that has not happened",
                   "gin and ship within a season, because seed cotton does not store well"),
     "when": "the price notice is an annual dated act in April or May; ginning runs from "
             "December into April",
     "information": ("the area actually sown, months before any official estimate",
                     "the input credit position of the producers' unions",
                     "the real gin-out ratio of the campaign"),
     "constraints": ("a price announced before the rains and honoured after them",
                     "input credit that fails when the world price falls",
                     "competition for land with maize and soybean"),
     "instruments": ("COTTON",),
     "counterparties": ("the producers' unions and their village cooperatives",
                        "international lint traders and the Asian spinning mills",
                        "the state, which underwrites the price"),
     "observables": ("the announced farmgate price and its arrete number",
                     "seed cotton collected and lint produced, published at campaign close",
                     "USDA FAS and ICAC production estimates for the same campaign"),
     "impact": "an ADMINISTERED PRICE announced ahead of a world price, which is a supply-"
               "response experiment with a date on it",
     "persistence": "one campaign, repeated annually, which gives a panel of roughly twenty "
                    "treatment years across Benin and Togo together",
     "falsifier": "area sown in the following campaign shows no relationship to the announced "
                  "price relative to the previous year's world price once rainfall is controlled "
                  "for, which would make the announcement an accounting act rather than a "
                  "supply signal",
     "notes": "the mechanism is shared with Benin's AIC, which is why SC-I and SC-M are separate "
              "domains with a common test and each other's placebo"},
    {"name": "The Togolese phosphate operator and the clinker and cement importers at Lome",
     "holds": "the Hahotoe phosphate deposits, the Kpeme loading wharf, and the coastal grinding "
              "plants that make Lome a regional cement and clinker hub",
     "forced_to": ("ship phosphate rock through a dedicated wharf with limited capacity",
                   "import clinker continuously to feed the grinding plants",
                   "compete with Moroccan and Senegalese phosphate on both grade and freight"),
     "when": "continuous; the shipment counts are monthly",
     "information": ("the real grade profile of the remaining deposits",
                     "the clinker import schedule and the grinders' inventory"),
     "constraints": ("a declining grade and long-deferred investment",
                     "a fertiliser market where the marginal supplier is Morocco",
                     "the same corridor congestion every other Lome cargo faces"),
     "instruments": ("CORN", "WHEAT", "COTTON"),
     "counterparties": ("fertiliser blenders and importers across the Sahel",
                        "Moroccan and other phosphate suppliers as competitors",
                        "the port and the OTR"),
     "observables": ("phosphate export tonnage in the port and customs statistics",
                     "clinker import volumes at Lome",
                     "Sahelian fertiliser prices reported by the agricultural bulletins"),
     "impact": "the FERTILISER COST leg of the cotton and cereal campaigns: an input price shock "
               "in the Sahel is a yield story the following season, which is a slow and testable "
               "channel into COTTON and the grains",
     "persistence": "one to two campaigns",
     "falsifier": "Sahelian fertiliser prices show no relationship to Lome clinker and phosphate "
                  "flows, which would mean the regional input market is set entirely offshore "
                  "and this actor is a fiscal observable only",
     "notes": "THE INTERACTION WITH `ma` LIVES HERE: Morocco is the world's phosphate marginal "
              "supplier and the Sahel is one of its markets, so SC-J's control is another pack's "
              "object"},
    # ---------------------------------------------------------------- Benin
    {"name": "The Port Autonome de Cotonou and the Niger transit corridor",
     "holds": "Niger's principal maritime outlet, the terminal that loads the Agadem crude, and "
              "the customs transit regime that governs both",
     "forced_to": ("handle landlocked transit under a treaty regime while its government is in "
                   "dispute with the landlocked state",
                   "keep the corridor competitive against Lome, which is deeper",
                   "publish traffic, because the concession agreements require it"),
     "when": "continuous; the border closures and reopenings are DATED political acts",
     "information": ("transit declarations by destination before publication",
                     "which consignments are being held and why"),
     "constraints": ("a border that has been closed by ECOWAS decision and then by bilateral "
                     "quarrel",
                     "a crude terminal whose operation is entangled in the same quarrel",
                     "competition from Lome for the same Nigerien and Burkinabe cargo"),
     "instruments": ("CORN", "WHEAT", "XBRUSD"),
     "counterparties": ("Nigerien importers and their transit agents",
                        "the Chinese operator of the pipeline and terminal",
                        "the Beninese customs administration"),
     "observables": ("monthly port traffic with the transit split",
                     "Beninese customs transit declarations to Niger",
                     "the dated loading interruptions at Seme-Kpodji"),
     "impact": "the corridor cost of Niger's entire import bill AND the on/off switch on a "
               "90,000 b/d crude flow, in one institution",
     "persistence": "episodic; each closure is a dated window of weeks to months",
     "falsifier": "Cotonou's Niger transit tonnage shows no fall during the closure windows and "
                  "Lome's shows no matching rise, which would mean the trade found routes "
                  "neither port records and both series are measuring the wrong thing",
     "notes": "the substitution with Lome is the test: a fall here that appears as a rise there "
              "is ROUTING and carries no supply information, and neither port's series can "
              "establish that alone"},
    {"name": "The Glo-Djigbe Industrial Zone (GDIZ) and Benin's processing mandate",
     "holds": "the industrial zone's ginning, cashew-processing and textile capacity, and the "
              "policy commitment that raw exports of cashew, cotton and soybean be processed "
              "domestically",
     "forced_to": ("fill the zone's capacity, which is what justifies the restriction on raw "
                   "exports",
                   "commence the restrictions on gazetted dates, which makes them measurable",
                   "buy raw material from the same farmers who could otherwise sell across a "
                   "border"),
     "when": "the restrictions are DATED policy acts from 2024 onward; the capacity ramp is "
             "continuous",
     "information": ("the zone's real utilisation against its announced capacity",
                     "the enforcement intensity at the borders"),
     "constraints": ("processing capacity that must exist before a raw-export ban can hold",
                     "neighbours who will buy the raw nut if Benin will not",
                     "Indian and Vietnamese processors who are the incumbent buyers"),
     "instruments": ("COTTON", "SOYBEAN", "USDCNH"),
     "counterparties": ("Beninese cashew, cotton and soybean farmers",
                        "Indian and Vietnamese cashew processors, who lose the raw nut",
                        "the neighbouring buyers who absorb the leakage"),
     "observables": ("the gazetted commencement dates of each restriction",
                     "Beninese raw versus processed export volumes in the customs mirrors",
                     "INDIAN AND VIETNAMESE import statistics from Benin, which is the mirror "
                     "that shows whether the ban bound"),
     "impact": "a dated policy treatment on a real export flow, measured on the BUYERS' customs "
               "data because the seller's is the thing in question",
     "persistence": "structural if the capacity is real; reversible if it is not",
     "falsifier": "Indian and Vietnamese raw cashew imports from Benin are unchanged across the "
                  "restriction's commencement while imports from its neighbours rise, which "
                  "would mean the ban re-routed the nut rather than processing it",
     "notes": "THE CLEANEST POLICY EXPERIMENT IN THE PACK: a dated ban, a mirror statistic on the "
              "other side, and two neighbours as the leakage control"},
    {"name": "The Association Interprofessionnelle du Coton (AIC) and Benin's cotton campaign",
     "holds": "the campaign framework, the input credit, the ginning capacity and the announced "
              "farmgate price for the largest cotton crop in Africa in several recent seasons",
     "forced_to": ("announce a guaranteed price before sowing, as Togo's NSCT does",
                   "distribute inputs on credit ahead of the harvest",
                   "deliver lint to Asian spinners against contracts struck before the crop "
                   "exists"),
     "when": "the price notice is an annual dated act; the campaign runs from sowing in May-June "
             "to ginning through April",
     "information": ("area sown and input uptake before any official estimate",
                     "the smuggling differential against Nigeria and Togo"),
     "constraints": ("a price fixed before the world price is known",
                     "a Nigerian border across which seed cotton and inputs both leak",
                     "the same rainfall risk as every other Sahelian crop"),
     "instruments": ("COTTON", "SOYBEAN"),
     "counterparties": ("the producers' cooperatives", "the ginners and lint exporters",
                        "Asian spinning mills", "the Beninese state, which underwrites"),
     "observables": ("the announced farmgate price with its arrete number",
                     "seed cotton collected and lint output at campaign close",
                     "USDA FAS and ICAC estimates for the same marketing year"),
     "impact": "the second half of the administered-price experiment, with a much larger crop "
               "than Togo's and a border that leaks -- which makes Benin the treatment and Togo "
               "the cleaner control",
     "persistence": "one campaign, repeated annually",
     "falsifier": "Beninese sown area responds to the announced price no differently from Togo's "
                  "despite the much larger Nigerian smuggling margin, which would mean the "
                  "border differential does not bind and the two are one experiment and not two",
     "notes": "the pair with SC-I is the point: two neighbours running the SAME administered "
              "mechanism with different border conditions is a natural experiment the desk can "
              "actually identify"},
    # ---------------------------------------------------------------- Sierra Leone
    {"name": "The Sierra Rutile mineral-sands operation and the titanium feedstock buyers",
     "holds": "one of the world's largest natural rutile operations, its ilmenite and zircon "
              "by-products, and the dredging and mining leases on the Sherbro coast",
     "forced_to": ("mine to a dredge path fixed years in advance",
                   "negotiate lease and royalty terms with a state that has renegotiated before",
                   "sell into a concentrated pigment-producer buyer base on annual contracts"),
     "when": "continuous production; the lease and expansion decisions are dated",
     "information": ("the grade profile ahead of the dredge",
                     "the contract price it has actually achieved, which is not public"),
     "constraints": ("a buyer base of a handful of pigment producers, every one a single name "
                     "this desk may not hunt",
                     "power and fuel costs in a country with neither",
                     "an assessment-priced market with no exchange"),
     "instruments": ("XZNUSD", "EUSTX50", "GER40"),
     "counterparties": ("pigment and titanium-metal producers in Europe, the US and China",
                        "the Government of Sierra Leone as licensor",
                        "the National Minerals Agency"),
     "observables": ("export tonnage in the NMA and customs statistics and the partner mirrors",
                     "the EITI Sierra Leone report's production and revenue tables",
                     "the dated lease and expansion decisions"),
     "impact": "STATED WEAK on price: the buyers are single names and the assessments are "
               "licensed, so what is left is a European industrial index leg and the industrial "
               "metals complex, and the pack expects little",
     "persistence": "years",
     "falsifier": "Sierra Leonean rutile export tonnage shows no relationship to any executable "
                  "instrument at any lag, which is the OUTCOME THIS PACK EXPECTS -- and which "
                  "still leaves the fiscal and terms-of-trade legs of SC-N standing",
     "notes": "carried honestly. A top world producer of a feedstock nobody can trade is a "
              "reminder that a real mechanism and a tradable one are different things"},
    {"name": "The Bank of Sierra Leone and the redenomination of 1 July 2022",
     "holds": "the leone issue, the FX auction, the reserve position and the redenomination "
              "itself",
     "forced_to": ("run the changeover with a dual-circulation period and a public education "
                   "campaign",
                   "defend a float with thin reserves through an inflation shock",
                   "publish auction results, which is where the stress is visible"),
     "when": "the redenomination is a single dated act (2022-07-01); auctions are weekly and MPC "
             "decisions quarterly",
     "information": ("the true reserve position between publications",
                     "the banks' unmet FX demand at each auction"),
     "constraints": ("an import-dependent economy with a narrow export base",
                     "a redenomination that changes the unit and not the inflation",
                     "an IMF programme with reserve targets"),
     "instruments": ("XAUUSD", "XZNUSD", "USDZAR"),
     "counterparties": ("commercial banks and bureaux", "the IMF under its ECF arrangement",
                        "importers of rice and fuel, who are the FX demand"),
     "observables": ("auction clearing rates and volumes against the bureau survey",
                     "the redenomination circulars and the dual-circulation dates",
                     "CPI and reserves in the BSL publications"),
     "impact": "THE PACK'S OWN ERA BOUNDARY: any leone series crossing 2022-07-01 is a 1000x "
               "step that is not a price move, and SC-O exists so no pooled study reads one as "
               "the other",
     "persistence": "the redenomination is permanent; the inflation it did not cure continued",
     "falsifier": "the auction-minus-bureau spread -- a RATIO, so redenomination-invariant -- "
                  "shows no discontinuity at 2022-07-01, which is exactly what this actor "
                  "predicts and is the test that the boundary is a UNIT change and not a "
                  "monetary one",
     "notes": "a rare case where the pack's own falsifier is a NULL result it expects and wants: "
              "the ratio must be continuous across a unit change or something else happened"},
    {"name": "The National Minerals Agency and the Kono artisanal diamond licensing chain",
     "holds": "the alluvial diamond licensing regime, the Kimberley certification authority, and "
              "the Tonkolili iron-ore lease history",
     "forced_to": ("certify every rough parcel for export under the Kimberley Process",
                   "license artisanal miners whose output it cannot count directly",
                   "report production and export statistics to the Process annually"),
     "when": "licensing is continuous; certification is per parcel; the statistics are annual",
     "information": ("the real artisanal output against the certified figure",
                     "which parcels are being valued low for export"),
     "constraints": ("an artisanal sector that is mobile, cross-border and hard to count",
                     "a valuation step that is discretionary",
                     "an iron-ore lease that has changed hands after each price cycle"),
     "instruments": ("XAUUSD", "XCUUSD", "USDZAR"),
     "counterparties": ("Antwerp, Dubai and Ramat Gan importers",
                        "the artisanal diggers and the licensed dealers",
                        "Guinean and Liberian cross-border traders"),
     "observables": ("Kimberley Process production and export carats and value",
                     "the IMPORTING participants' own reported figures for the same year",
                     "the EITI report's mineral revenue line"),
     "impact": "a MIRROR-STATISTIC window on an informal physical flow, in the same family as "
               "the gold re-export gaps other packs measure -- the gap between exporter and "
               "importer is the measurement",
     "persistence": "structural",
     "falsifier": "the exporter-importer gap for Sierra Leonean rough shows no relationship to "
                  "the licensing regime's changes or to the Liberian and Guinean figures, which "
                  "would mean the gap is a valuation artefact and not a flow",
     "notes": "the Kimberley data is annual and late, so this actor dates eras and never "
              "conditions a week, and SC-P says so"},
    # ---------------------------------------------------------------- The Gambia
    {"name": "The Central Bank of The Gambia and the remittance corridor",
     "holds": "the dalasi float, the reserve position, and the monthly remittance series that is "
              "the best high-frequency observable any small jurisdiction here produces",
     "forced_to": ("publish remittance inflows monthly",
                   "smooth a currency whose inflows are seasonal and whose outflows are not",
                   "hold reserves against an import bill dominated by rice and fuel"),
     "when": "monthly publication; quarterly MPC decisions",
     "information": ("the bureau market's real turnover",
                     "the informal remittance share that never reaches the official series"),
     "constraints": ("a very small economy with a very large remittance share of GDP",
                     "a tourist season and a Tobaski season that both concentrate inflows",
                     "a re-export trade with Senegal that moves with Senegalese tariff policy"),
     "instruments": ("SOYBEAN", "EURUSD", "USDZAR"),
     "counterparties": ("the diaspora in Europe, the UK and the US",
                        "money transfer operators and the mobile-money providers",
                        "importers of rice and fuel"),
     "observables": ("monthly remittance inflows with the source-country split",
                     "the bureau-minus-official spread",
                     "tourist arrivals and the seasonal reserve path"),
     "impact": "a COUNTED SEASONAL INFLOW: the dalasi's stress is a calendar phenomenon rather "
               "than a monetary one, which makes it testable with a matched-season control",
     "persistence": "seasonal within the year; structural across years",
     "falsifier": "the bureau spread shows no seasonal pattern aligned with the remittance peaks "
                  "around Tobaski and Christmas, which would mean the inflows are smoothed away "
                  "and the seasonality is not a market event",
     "notes": "THE ISLAMIC CALENDAR IS AN ECONOMIC CALENDAR HERE: Tabaski is the largest "
              "household-spending event of the Gambian year and it moves eleven days earlier "
              "annually, which is a clean identification the pack's holiday table supplies"},
    {"name": "The Gambian groundnut trade season and the Senegal re-export commerce",
     "holds": "the groundnut crop, the licensed buying points, and the entrepot trade that "
              "re-exports imported goods into Senegal and beyond",
     "forced_to": ("buy the crop at an announced producer price within a short trade season",
                   "compete with Senegalese buyers across an open border for the same nuts",
                   "finance the season, which has repeatedly failed for want of credit"),
     "when": "the trade season runs from December into March; the producer price is announced "
             "before it opens",
     "information": ("the real crop size before any survey",
                     "the cross-border price differential week by week"),
     "constraints": ("a single annual crop on rain-fed land",
                     "a border across which nuts move to whichever side pays more",
                     "a re-export trade that depends entirely on Senegalese tariff policy"),
     "instruments": ("SOYBEAN", "CORN", "WHEAT"),
     "counterparties": ("Senegalese and Chinese buyers of groundnuts",
                        "the farmers and the village cooperatives",
                        "Senegalese consumers of the re-exported goods"),
     "observables": ("the announced producer price and the season's purchases",
                     "Chinese and EU import statistics for Gambian and Senegalese groundnuts",
                     "the re-export line in the trade statistics"),
     "impact": "groundnut oil competes in the same vegetable-oil complex as soybean oil, which "
               "is the one genuine executable link a country this small has; it is labelled WEAK "
               "and tested with the whole West African crop as the aggregate",
     "persistence": "one season",
     "falsifier": "Gambian and Senegalese groundnut purchases show no response to the announced "
                  "price differential across the border, which would mean the open border does "
                  "not arbitrage and the trade-season mechanism is administrative only",
     "notes": "THE INTERACTION WITH `west_africa` LIVES HERE: Senegal is the other side of every "
              "Gambian groundnut and re-export transaction and belongs to that pack"},
    # ---------------------------------------------------------------- Guinea-Bissau
    {"name": "The Guinea-Bissau cashew campaign committee and the decreed reference price",
     "holds": "the annual decision that sets the farmgate reference price for roughly nine "
              "tenths of the country's export earnings, and the campaign opening date",
     "forced_to": ("fix a price by decree before the buyers commit, in a year whose world price "
                   "it does not know",
                   "open the campaign at a date that determines whether the crop is bought at "
                   "all",
                   "collect the export levy that is the state's main non-aid revenue"),
     "when": "an annual dated decree, normally in April or May, published in the Boletim Oficial",
     "information": ("the buyers' real bid before the decree",
                     "the stock held by traders from the previous campaign"),
     "constraints": ("a monocrop economy with no alternative export",
                     "Indian and Vietnamese processors who can simply not buy at a price set too "
                     "high",
                     "porous borders with Senegal and Guinea through which the nut leaves if the "
                     "decreed price is uncompetitive",
                     "a state with chronic salary arrears that needs the levy immediately"),
     "instruments": ("WHEAT", "CORN", "USDCNH"),
     "counterparties": ("Indian and Vietnamese processors and their agents",
                        "the farmers, who are most of the population",
                        "Senegalese and Guinean cross-border buyers"),
     "observables": ("the decree, its date and the reference price, in the Boletim Oficial",
                     "INDIAN AND VIETNAMESE import statistics from Guinea-Bissau, which count "
                     "better than Bissau does",
                     "the campaign's reported tonnage and the state's levy receipts"),
     "impact": "an ADMINISTERED PRICE that sets a whole country's terms of trade in one act, "
               "whose measurable consequence is the country's GRAIN IMPORT CAPACITY -- so the "
               "test is on WHEAT and CORN import volumes and never on a cashew price nobody "
               "quotes",
     "persistence": "one campaign; the arrears it causes persist longer",
     "falsifier": "years in which the decreed price was set far above the regional market show no "
                  "fall in Bissau's recorded exports and no rise in Senegal's and Guinea's, "
                  "which would mean the decree does not bind and the campaign is a formality",
     "notes": "THE MOST CONSEQUENTIAL SINGLE ANNUAL ECONOMIC ACT IN THE PACK, in the "
              "jurisdiction with the least data -- which is why the lawful substitute is the "
              "buyers' customs service and it is named in NO_LAWFUL_GROUND"},
    {"name": "The Bissau treasury, its salary arrears and the WAEMU discipline that bounds them",
     "holds": "a budget that depends on the cashew levy and on external support, inside a "
              "monetary union that will not finance it",
     "forced_to": ("pay salaries from a revenue stream that arrives in one season",
                   "borrow on the regional market at a spread it does not control",
                   "meet WAEMU convergence criteria it has rarely met"),
     "when": "continuous; the arrears build between campaigns",
     "information": ("the true arrears stock, which is disclosed only in programme documents",
                     "the campaign's levy yield before it is collected"),
     "constraints": ("no monetary financing: the BCEAO will not print for a member state",
                     "a regional auction market that prices its paper against Benin's and "
                     "Senegal's",
                     "a history of instability that raises every spread it pays"),
     "instruments": ("EURUSD", "USDZAR"),
     "counterparties": ("regional banks buying its bills at UMOA-Titres",
                        "the IMF under a small ECF", "its own civil servants"),
     "observables": ("UMOA-Titres results for Bissau issues: amount raised, cut-off, cover",
                     "the IMF programme documents' arrears tables",
                     "the campaign levy receipts reported in the press"),
     "impact": "THE CLEANEST DEMONSTRATION OF WHAT A HARD PEG DOES TO A COMMODITY SHOCK: with no "
               "devaluation available, a bad cashew campaign becomes ARREARS rather than "
               "inflation, and arrears are observable",
     "persistence": "years; arrears compound",
     "falsifier": "Bissau's auction cut-off and cover show no deterioration after a poor cashew "
                  "campaign once the regional rate level is controlled for, which would mean the "
                  "monocrop shock is absorbed elsewhere and the fiscal channel is not the one",
     "notes": "this actor is why SC-U can ask what a peg DOES rather than only what it IS: four "
              "pegged economies, three floating ones, and one commodity shock a year"},
    # ---------------------------------------------------------------- Cabo Verde
    {"name": "The Banco de Cabo Verde and the 110.265 parity with Portugal",
     "holds": "the escudo's peg, the reserve position behind it, and the credit facility the "
              "Portuguese agreement provides",
     "forced_to": ("hold reserves sufficient to defend a fixed parity in a tourism economy",
                   "import essentially everything, including most food and all fuel",
                   "publish a real statistical plane, which it does"),
     "when": "continuous; the statistical bulletin is monthly and quarterly",
     "information": ("the seasonal reserve path against the tourist calendar",
                     "the banking system's external position"),
     "constraints": ("an archipelago with no arable land to speak of and no minerals",
                     "a tourism season concentrated in the European winter",
                     "a peg whose guarantor is a single European state"),
     "instruments": ("EURUSD", "XBRUSD", "UK100"),
     "counterparties": ("the Banco de Portugal under the exchange agreement",
                        "the tour operators and airlines that bring the season",
                        "the emigrant diaspora in Portugal, the US and the Netherlands"),
     "observables": ("the reserve path and the months of import cover",
                     "tourist arrivals and bed-nights from INE",
                     "remittance inflows in the balance of payments"),
     "impact": "the THIRD MONETARY CONTROL of the pack: a hard euro peg with a different "
               "guarantor and a completely different real economy, which is what lets a study "
               "ask whether the XOF's behaviour is about pegs or about France",
     "persistence": "structural; the peg has held since 1998",
     "falsifier": "Cabo Verdean and WAEMU inflation and real-exchange-rate paths diverge "
                  "systematically despite the same euro anchor, which would mean the guarantor "
                  "and the real economy dominate the anchor and the 'peg' variable is not the "
                  "one doing the work",
     "notes": "carried because a CONTROL is worth as much as a treatment and this one was "
              "available and unused"},
    {"name": "Cabo Verde's tourism, aviation and Mindelo bunkering complex",
     "holds": "the hotel capacity, the island airports and the bunkering and transshipment "
              "facilities at Mindelo and Praia",
     "forced_to": ("fill beds in a season set by European winter demand",
                   "import all its fuel, including what it sells as bunkers",
                   "compete with Las Palmas and Dakar for mid-Atlantic bunkering calls"),
     "when": "the season runs from November to April; port calls are continuous",
     "information": ("forward bookings, months before the arrivals statistic",
                     "the bunker volumes and the margin against Las Palmas"),
     "constraints": ("a small, concentrated source-market base in a handful of European "
                     "countries",
                     "fuel that must be imported to be re-sold",
                     "an airport network that is the only access"),
     "instruments": ("XBRUSD", "EURUSD", "UK100"),
     "counterparties": ("European tour operators and airlines",
                        "shipping lines taking bunkers mid-Atlantic",
                        "the fuel importers"),
     "observables": ("monthly arrivals and bed-nights by source market from INE",
                     "port calls and bunker volumes from ENAPOR",
                     "the seasonal reserve and remittance path at the BCV"),
     "impact": "THE PHYSICAL ECONOMY OF AN ARCHIPELAGO WITH NO MINES: arrivals and bunkers are "
               "the real activity series, and they make Cabo Verde a EUROPEAN DEMAND reading "
               "rather than an African supply one",
     "persistence": "seasonal within the year",
     "falsifier": "Cabo Verdean arrivals show no relationship to European discretionary-spending "
                  "conditions once the season is controlled for, which would sever the one "
                  "genuine macro link this jurisdiction has",
     "notes": "the reason the physical layer is declared absent for CV in its extractive sense "
              "and sourced in this one -- declaring a layer absent because there is no mine "
              "would be reading the wrong country"},
    # ---------------------------------------------------------------- regional
    {"name": "The BCEAO as the shared central bank of four of the eight",
     "holds": "the currency, the parity, the pooled reserves and the single monetary policy of "
              "Niger, Togo, Benin and Guinea-Bissau -- and of four more states that belong to "
              "`west_africa`",
     "forced_to": ("set one rate for eight economies with very different shocks",
                   "defend a parity that has moved once in sixty years",
                   "publish union aggregates and never national reserve figures"),
     "when": "quarterly policy meetings; monthly statistical publication",
     "information": ("each member's real fiscal position through the payments system",
                     "the union's reserve path between publications"),
     "constraints": ("a hard peg that removes the exchange rate as an adjustment instrument for "
                     "every member",
                     "a French Treasury guarantee that is politically contested in the Sahel",
                     "members under sanctions whose accounts it was asked to freeze in 2023"),
     "instruments": ("EURUSD", "USDZAR"),
     "counterparties": ("the eight member treasuries", "the French Treasury",
                        "the regional banks that buy the members' paper"),
     "observables": ("the CPM communique and the minimum bid rate",
                     "union reserves and the balance of payments",
                     "UMOA-Titres results by issuer, which is the national dimension"),
     "impact": "the reason four of this pack's eight have NO national monetary policy, no "
               "national reserve series and no exchange-rate adjustment -- so their shocks show "
               "up in AUCTIONS, ARREARS and TRADE and nowhere else",
     "persistence": "structural",
     "falsifier": "the cross-issuer auction spread within WAEMU shows no response to "
                  "country-specific shocks, which would mean even the auction is a regional "
                  "liquidity series and the pack has NO national financial observable for four "
                  "jurisdictions -- a result the pack would have to publish as a hole",
     "notes": "SHARED WITH `west_africa` BY CONSTRUCTION AND NOT DUPLICATED: that pack owns the "
              "BCEAO's monetary seat and the peg's history, this one owns the four issuers' own "
              "auction lines and what the peg does to a monocrop and a uranium exporter"},
    {"name": "ECOWAS/CEDEAO and the Alliance des Etats du Sahel (AES)",
     "holds": "the free-trade and free-movement regime of West Africa, the common external "
              "tariff, and -- since January 2024 -- a rival bloc that three of its members have "
              "announced they are leaving for",
     "forced_to": ("enforce sanctions when a member's government changes by force, which it did "
                   "on 2023-07-30 against Niger",
                   "lift them when enforcement became untenable, which it did on 2024-02-24",
                   "manage a withdrawal that takes effect on 2025-01-29 without severing the "
                   "corridors its landlocked members depend on"),
     "when": "summit decisions, each with a communique and a date",
     "information": ("the internal positions before a summit communique",
                     "the real degree of border enforcement, which differs from the announcement"),
     "constraints": ("landlocked members whose trade must cross coastal members' territory",
                     "a common tariff that a departing member must eventually leave",
                     "national interests that diverge from the bloc's declarations"),
     "instruments": ("CORN", "WHEAT", "SUGAR", "XBRUSD"),
     "counterparties": ("the eight WAEMU treasuries and the fifteen ECOWAS members",
                        "the coastal ports through which the sanctions bit",
                        "the AES partners Mali and Burkina Faso"),
     "observables": ("the summit communiques and their dates",
                     "port transit tonnage to the sanctioned country before, during and after",
                     "the UMOA-Titres cut-off the sanctioned issuer paid"),
     "impact": "A DATED TRADE-BLOC RUPTURE WITH A MEASURABLE CORRIDOR EFFECT, which is rare: "
               "most trade-policy events are gradual and this one has three dates on it",
     "persistence": "the sanctions window is bounded; the withdrawal is structural",
     "falsifier": "port transit tonnage to Niger, the Nigerien auction cut-off and Sahelian "
                  "consumer prices show no discontinuity at 2023-07-30, 2024-02-24 or "
                  "2025-01-29, which would mean the bloc's decisions were declaratory and the "
                  "trade found other routes immediately",
     "notes": "THE EVENT SC-C IS BUILT ON, and the one whose evidence quality is best: three "
              "dated communiques, two published corridor series and a weekly auction"},
    {"name": "The Gulf of Guinea naval, insurance and war-risk complex",
     "holds": "the war-risk underwriting of a sea lane that carries West African crude, the "
              "naval presence that patrols it, and the reporting that prices both",
     "forced_to": ("price a risk from a counted incident series that is published quarterly",
                   "redraw the listed high-risk area when the incident count changes",
                   "escort or decline to escort on commercial terms"),
     "when": "incidents are continuous and reported; the risk-area designations are dated acts",
     "information": ("incidents that are never reported, which is a known and large fraction",
                     "the naval deployment schedule"),
     "constraints": ("a very large sea area with limited regional naval capacity",
                     "insurers who respond to designations rather than to incidents",
                     "crew nationality and flag, which change the response"),
     "instruments": ("XBRUSD", "XTIUSD"),
     "counterparties": ("tanker owners and their P&I clubs and war-risk underwriters",
                        "the Yaounde Architecture's regional navies and the European deployments",
                        "the IMB and the reporting centres"),
     "observables": ("IMB quarterly incident and kidnapping counts by location",
                     "the listed-areas designations and their dates",
                     "MDAT-GoG advisories between reports"),
     "impact": "a freight and insurance cost on a producing region's exports; the series records "
               "BOTH a rise to a regional peak in crew kidnapping and a sharp subsequent fall, "
               "which makes it a two-sided test rather than a scare story",
     "persistence": "the risk regime changes over years; individual incidents decay in days",
     "falsifier": "West African crude freight differentials show no response to the designation "
                  "changes or to the incident count at any lag once global tanker rates are "
                  "controlled for, which would mean the premium is a fixed cost and not a "
                  "state-dependent one",
     "notes": "a rare mechanism with a counted series, a two-sided history and a dated "
              "administrative act attached to it"},
)

#: Which jurisdiction each actor belongs to, by POSITION in ACTORS. Five Nigerien, five Liberian,
#: three Togolese, three Beninese, three Sierra Leonean, two Gambian, two Bissau-Guinean, two
#: Cabo Verdean and three regional -- the floor the brief sets is two per jurisdiction and three
#: for each of NE, LR, TG, BJ and SL.
ACTOR_JURISDICTION: tuple[str, ...] = (
    "ne", "ne", "ne", "ne", "ne",
    "lr", "lr", "lr", "lr",
    "tg", "tg", "tg",
    "bj", "bj", "bj",
    "sl", "sl", "sl",
    "gm", "gm",
    "gw", "gw",
    "cv", "cv",
    "regional", "regional", "regional",
)

# --------------------------------------------------------------------------- domains
#: TWENTY-THREE DOMAINS: four for Niger, three each for Liberia, Togo, Benin and Sierra Leone,
#: one each for The Gambia, Guinea-Bissau and Cabo Verde, and four regional. Every jurisdiction
#: owes at least one of its own and the five that carry the pack's mechanisms owe three or more.
#: A domain with fewer than two negative controls is refused by the validator.
DOMAINS: tuple[dict[str, Any], ...] = (
    {"id": "SC-A", "title": "NIGER: uranium at Arlit, the permits, and European reactor fuel",
     "objects": ("the gazetted permit actions of 2023-2025 and their dates",
                 "Nigerien mine production by year from the WNA profile",
                 "the Euratom origin table and the EU inventory-cover years",
                 "French and EU customs imports of uranium ores and concentrates from Niger"),
     "conditions": ("the era: pre-coup, sanctions window, post-sanctions AES era",
                    "whether EU inventory cover was above or below its own median that year",
                    "whether the event was a permit action or an operational interruption"),
     "instruments": ("XNGUSD", "FRA40", "EUSTX50", "GER40"),
     "controls": ("Kazakh and Canadian supply events in the same years, which separate "
                  "'uranium supply' from 'Nigerien supply'",
                  "matched non-event days on the European power and gas complex",
                  "the same windows in 2015-2019, when Niger produced more and nothing happened"),
     "notes": "URANIUM IS NOT AN INSTRUMENT and this domain never pretends it is. The route is "
              "European nuclear generation into gas substitution, inventory cover is measured in "
              "YEARS, and the pack predicts a small and possibly absent effect BEFORE the test"},
    {"id": "SC-B", "title": "NIGER: the Agadem-Seme crude line and the Benin border dispute",
     "objects": ("the first export loading of May 2024 and every subsequent cargo date",
                 "the dated interruptions and resumptions of loading",
                 "Beninese transit declarations and Chinese crude import statistics by origin"),
     "conditions": ("the line's state: pre-export, flowing, interrupted, resumed",
                    "whether the interruption was bilateral-political or technical",
                    "the Brent term structure at the interruption date"),
     "instruments": ("XBRUSD", "XTIUSD"),
     "controls": ("matched non-event days on the crude complex",
                  "Chinese import volumes from Niger in the following quarter, which separate a "
                  "negotiation from a supply loss",
                  "other West African export interruptions of similar size in the same years"),
     "notes": "about 90,000 b/d is SMALL against world supply and LARGE against Niger's external "
              "accounts, so the trade-balance leg is tested first and the price leg second"},
    {"id": "SC-C", "title": "NIGER: ECOWAS sanctions, the AES exit and the corridor",
     "objects": ("the summit communiques of 2023-07-30, 2024-02-24 and the 2025-01-29 exit",
                 "port transit tonnage to Niger at Cotonou and Lome, month by month",
                 "the Nigerien UMOA-Titres cut-off and cover against Benin's",
                 "Sahelian consumer prices for grain and fuel in the sanctions window"),
     "conditions": ("the bloc state: pre-sanctions, sanctioned, lifted, withdrawn",
                    "which corridor the cargo used",
                    "whether the month was in the lean season or after harvest"),
     "instruments": ("CORN", "WHEAT", "SUGAR", "XBRUSD"),
     "controls": ("Burkina Faso's and Mali's corridors over the same months, which separate "
                  "'sanctions on Niger' from 'Sahel corridor conditions'",
                  "total ECOWAS import volumes, which separate a routing event from a trade one",
                  "the Benin auction cut-off as the regional rate control"),
     "notes": "A DATED TRADE-BLOC RUPTURE with three communiques, two corridor series and a "
              "weekly auction -- the best-evidenced domain in the pack"},
    {"id": "SC-D", "title": "NIGER: the rains, the Harmattan and the soudure",
     "objects": ("AGRHYMET dekadal rainfall and sowing dates",
                 "the Cadre Harmonise food-insecurity phase by region",
                 "millet, sorghum and cowpea prices in the Nigerien markets",
                 "the Harmattan window and its effect on transport and harvest quality"),
     "conditions": ("the season: Harmattan, hot-dry, rainy, harvest",
                    "whether the seasonal forecast was for a deficit or a surplus",
                    "whether the lean season overlapped a corridor disruption"),
     "instruments": ("CORN", "WHEAT", "SUGAR", "COTTON"),
     "controls": ("the same calendar windows in years with normal rainfall",
                  "the Burkinabe and Malian rainfall series, which separate a Nigerien shock "
                  "from a Sahelian one",
                  "world grain prices, which separate a local supply story from an import one"),
     "notes": "the shared agronomic clock of the whole pack: the same rains set the cotton, "
              "cashew and cereal campaigns from Niamey to Bissau"},
    {"id": "SC-E", "title": "LIBERIA: the flag state and world tanker tonnage",
     "objects": ("the registry's published vessel count, gross and deadweight tonnage and mix",
                 "the UNCTAD and IMO aggregates that republish it",
                 "the registry's marine notices and de-flagging announcements",
                 "the age profile of tanker tonnage arriving on the register"),
     "conditions": ("whether tanker DWT on the flag grew faster or slower than world fleet DWT",
                    "whether a sanctions regime was newly in force that quarter",
                    "whether the arriving tonnage was above or below the fleet's median age"),
     "instruments": ("XBRUSD", "XTIUSD", "UK100"),
     "controls": ("Panama's and the Marshall Islands' tonnage over the same quarters, because "
                  "re-flagging is ZERO SUM between registers",
                  "total world fleet growth, which separates capacity from market share",
                  "dirty-tanker rates with global fleet growth controlled for"),
     "notes": "a flag state publishes a census of a sixth of world deadweight tonnage and almost "
              "nobody reads it as an economic series; that is the whole reason SC-E exists"},
    {"id": "SC-F", "title": "LIBERIA: Yekepa iron ore, the Buchanan rail and third-party access",
     "objects": ("shipment counts and tonnage from Buchanan",
                 "the dated expansion milestones and the rail-access decisions",
                 "the EITI Liberia production and revenue tables"),
     "conditions": ("the expansion phase against the published timetable",
                    "whether a rail-access decision was live in the same quarter",
                    "whether Guinean Nimba ore was seeking the same route"),
     "instruments": ("XCUUSD", "XZNUSD", "UK100"),
     "controls": ("Australian and Brazilian seaborne volumes, against which Liberia is tiny",
                  "West African Capesize freight, which is the channel that could actually bind",
                  "matched quarters with no milestone"),
     "notes": "STATED WEAK ON PRICE AND REAL ON THE CORRIDOR: the rail-access decision matters "
              "more for GUINEAN ore than for Liberian, which is why this domain's strongest edge "
              "points at a neighbour that belongs to `west_africa`"},
    {"id": "SC-G", "title": "LIBERIA: rubber, dollarisation and the concession economy",
     "objects": ("Liberian rubber export tonnage in the customs mirrors",
                 "the CBL's published LRD and USD rates and the dollarisation share",
                 "the EITI rubber and iron-ore revenue lines"),
     "conditions": ("whether the LRD moved while the dollarisation share was stable",
                    "the tapping calendar: wintering or full tapping",
                    "whether Chinese natural-rubber imports were rising or falling"),
     "instruments": ("XBRUSD", "USDCNH"),
     "controls": ("Sierra Leone's and The Gambia's currencies over the same months, which are "
                  "floats WITHOUT dollarisation",
                  "world natural-rubber production, against which Liberia is small",
                  "synthetic-rubber feedstock costs in the crude chain"),
     "notes": "the dollarisation leg is the valuable half: it is the control that separates 'the "
              "currency moved' from 'the economy tightened' in SC-U"},
    {"id": "SC-H", "title": "TOGO: Lome, the deepest quay on the coast, and the Sahel transit",
     "objects": ("monthly tonnage, TEU, transshipment and transit split by destination",
                 "OTR customs receipts, which move with the port",
                 "corridor clearance times and truck-tracking dashboards"),
     "conditions": ("whether the month fell inside a Niger sanctions or border-closure window",
                    "whether transshipment or direct transit drove the change",
                    "the season: lean season, harvest, or the pre-campaign input import peak"),
     "instruments": ("CORN", "WHEAT", "SUGAR", "COTTON"),
     "controls": ("Cotonou's and Abidjan's throughput over the same months, which separate a "
                  "chokepoint from a ROUTING event",
                  "total West African container volumes",
                  "matched months with no political event"),
     "notes": "THE SINGLE BEST PHYSICAL OBSERVABLE IN THE PACK: monthly, published, split by "
              "destination, covering the import bill of three landlocked economies"},
    {"id": "SC-I", "title": "TOGO: the cotton ginning campaign and the announced farmgate price",
     "objects": ("the announced farmgate price and its arrete number",
                 "seed cotton collected and lint produced at campaign close",
                 "USDA FAS and ICAC estimates for the same marketing year"),
     "conditions": ("whether the announced price was above or below the prior year's world price",
                    "the campaign phase: sowing, growing, harvest, ginning",
                    "whether the preceding rainy season was a deficit year"),
     "instruments": ("COTTON",),
     "controls": ("Benin's announced price in the same campaign, which is the same mechanism "
                  "under a different border condition",
                  "Ivorian and Malian area, which separate 'West African cotton' from 'Togolese'",
                  "matched campaigns with no price change"),
     "notes": "an ADMINISTERED PRICE announced BEFORE the world price is known: a supply-response "
              "experiment with a date on it, repeated about twenty times across TG and BJ"},
    {"id": "SC-J", "title": "TOGO: phosphate, clinker and the Sahelian fertiliser cost",
     "objects": ("phosphate export tonnage from Kpeme in the port and customs statistics",
                 "clinker import volumes at Lome",
                 "Sahelian fertiliser prices in the agricultural bulletins"),
     "conditions": ("whether world phosphate prices were above or below their own median",
                    "the pre-campaign input import window versus the rest of the year",
                    "whether a corridor disruption overlapped the input import season"),
     "instruments": ("COTTON", "CORN", "WHEAT"),
     "controls": ("Moroccan phosphate export volumes and prices, which are the marginal supply "
                  "and belong to the `ma` pack",
                  "Sahelian fertiliser prices in years with no Lome disruption",
                  "matched seasons with normal rainfall"),
     "notes": "the input-cost leg of the cotton and cereal campaigns: a fertiliser shock is a "
              "yield story the FOLLOWING season, which is slow, testable and rarely modelled"},
    {"id": "SC-K", "title": "BENIN: Cotonou, the Niger corridor and the pipeline terminus",
     "objects": ("monthly port traffic with the Niger transit split",
                 "Beninese customs transit declarations to Niger",
                 "the dated loading interruptions at Seme-Kpodji"),
     "conditions": ("whether the border was open, closed by ECOWAS, or closed bilaterally",
                    "whether a crude cargo loaded that month",
                    "the season: lean season or post-harvest"),
     "instruments": ("CORN", "WHEAT", "XBRUSD"),
     "controls": ("Lome's transit over the same months, because a fall here that appears as a "
                  "rise there is ROUTING and carries no supply information",
                  "total Beninese non-transit traffic, which separates a corridor event from a "
                  "port event",
                  "matched months with no political act"),
     "notes": "the corridor cost of Niger's whole import bill AND the on/off switch on a 90,000 "
              "b/d crude flow, in one institution -- and NEITHER PACK CAN ESTABLISH THE ROUTING "
              "CONTROL ALONE"},
    {"id": "SC-L", "title": "BENIN: cashew, the GDIZ and the raw-export restriction timetable",
     "objects": ("the gazetted commencement dates of each raw-export restriction",
                 "Beninese raw versus processed export volumes",
                 "INDIAN AND VIETNAMESE import statistics from Benin, the mirror that decides it"),
     "conditions": ("whether the restriction was in force that campaign",
                    "whether the zone's processing capacity was above or below the crop",
                    "whether the neighbouring countries' raw exports rose in the same season"),
     "instruments": ("COTTON", "SOYBEAN", "USDCNH"),
     "controls": ("Ivorian and Ghanaian raw cashew exports in the same campaigns, which are the "
                  "LEAKAGE control",
                  "Indian and Vietnamese total raw imports, which separate a Beninese policy "
                  "from an Asian demand cycle",
                  "matched campaigns before the restriction"),
     "notes": "THE CLEANEST POLICY EXPERIMENT IN THE PACK: a dated ban, a mirror statistic on the "
              "buyers' side and two neighbours as the leakage control"},
    {"id": "SC-M", "title": "BENIN: cotton, the AIC campaign price and the Nigeria border",
     "objects": ("the announced farmgate price with its arrete number",
                 "seed cotton collected and lint output at campaign close",
                 "the naira cross rate at the border during the buying season"),
     "conditions": ("whether the naira devalued during the buying season",
                    "whether the announced price was above or below the prior world price",
                    "the campaign phase"),
     "instruments": ("COTTON", "SOYBEAN"),
     "controls": ("Togo's campaign in the same year, the same mechanism with a smaller smuggling "
                  "margin",
                  "Burkinabe and Malian area, which separate the regional crop from the Beninese",
                  "campaigns with a stable naira"),
     "notes": "Benin is the TREATMENT and Togo the cleaner CONTROL: the same administered "
              "mechanism, two border conditions, about twenty paired campaigns"},
    {"id": "SC-N", "title": "SIERRA LEONE: rutile, ilmenite and the mineral-sands margin",
     "objects": ("export tonnage in the NMA, customs and partner-mirror statistics",
                 "the EITI Sierra Leone production and revenue tables",
                 "the dated lease and expansion decisions"),
     "conditions": ("whether a lease or royalty decision was live that quarter",
                    "whether European pigment demand was expanding or contracting",
                    "whether the operation was in a dredge-transition phase"),
     "instruments": ("XZNUSD", "EUSTX50", "GER40"),
     "controls": ("Australian and South African mineral-sands volumes over the same quarters",
                  "matched quarters with no lease event",
                  "the broader industrial-metals complex, which carries the same global cycle"),
     "notes": "STATED WEAK AND CARRIED HONESTLY: the buyers are single names this desk may not "
              "hunt and the assessments forbid machine extraction, so the expected outcome is a "
              "null on price and a real result on the fiscal and terms-of-trade legs"},
    {"id": "SC-O", "title": "SIERRA LEONE: the 2022 redenomination and the floating-rate plane",
     "objects": ("the redenomination circulars and the dual-circulation dates",
                 "auction clearing rates and volumes against the bureau survey",
                 "CPI and reserves across the 2022-07-01 boundary"),
     "conditions": ("the side of 2022-07-01 the observation sits on",
                    "whether the auction was oversubscribed",
                    "whether an IMF review disbursed in the same quarter"),
     "instruments": ("XAUUSD", "XZNUSD", "USDZAR"),
     "controls": ("THE SPREAD AS A RATIO, which is redenomination-invariant and MUST be "
                  "continuous across the boundary if the break is a unit change",
                  "The Gambia's and Liberia's floats over the same months",
                  "matched quarters with no programme review"),
     "notes": "the boundary is a 1000x STEP THAT IS NOT A PRICE MOVE; this domain exists so no "
              "pooled leone series in this desk ever reads one as the other"},
    {"id": "SC-P", "title": "SIERRA LEONE: diamonds, the Kimberley mirror and Tonkolili iron ore",
     "objects": ("Kimberley production and export carats and value by participant and year",
                 "the IMPORTING participants' own figures for the same years",
                 "the Tonkolili lease history and its restarts"),
     "conditions": ("whether the licensing regime changed that year",
                    "whether the exporter-importer gap widened or narrowed",
                    "whether Liberian and Guinean declared exports moved in the same direction"),
     "instruments": ("XAUUSD", "XCUUSD", "USDZAR"),
     "controls": ("Liberia's and Guinea's Kimberley figures, which separate a Sierra Leonean "
                  "flow from a regional one",
                  "world rough diamond production, which carries the global cycle",
                  "years with no licensing change"),
     "notes": "ANNUAL AND LATE: this domain dates eras and never conditions a week, and saying so "
              "is the measurement rather than an apology"},
    {"id": "SC-Q", "title": "THE GAMBIA: groundnuts, re-exports and the remittance season",
     "objects": ("monthly remittance inflows with the source-country split",
                 "the bureau-minus-official spread",
                 "the announced groundnut producer price and the season's purchases",
                 "tourist arrivals and the seasonal reserve path"),
     "conditions": ("the distance in days to the next Aid el-Kebir, which moves eleven days "
                    "earlier each solar year",
                    "whether the month falls in the tourist season",
                    "whether the groundnut trade season was financed on time"),
     "instruments": ("SOYBEAN", "CORN", "EURUSD"),
     "controls": ("Senegal's groundnut purchases and producer price across the open border",
                  "matched calendar months in years when Tabaski fell in a different month, "
                  "which is the identification the Islamic calendar supplies for free",
                  "world vegetable-oil prices"),
     "notes": "THE ISLAMIC CALENDAR IS AN ECONOMIC CALENDAR HERE and its drift is a natural "
              "experiment: the same household event lands in a different solar month every year"},
    {"id": "SC-R", "title": "GUINEA-BISSAU: the cashew monocrop and the decreed campaign price",
     "objects": ("the decree, its date and the reference price in the Boletim Oficial",
                 "Indian and Vietnamese import statistics from Guinea-Bissau",
                 "the campaign tonnage and the state's levy receipts",
                 "UMOA-Titres results for Bissau issues and the arrears tables"),
     "conditions": ("whether the decreed price was above or below the regional market",
                    "whether the campaign opened on time",
                    "whether the previous campaign left arrears"),
     "instruments": ("WHEAT", "CORN", "USDCNH"),
     "controls": ("Senegalese and Guinean recorded cashew exports in the same season, which are "
                  "the leakage control",
                  "Indian and Vietnamese total raw imports, the demand-cycle control",
                  "campaigns whose decreed price tracked the market"),
     "notes": "the TEST IS ON GRAIN IMPORT CAPACITY and never on a cashew price nobody quotes: "
              "with no devaluation available, a monocrop shock becomes ARREARS, which is "
              "observable"},
    {"id": "SC-S", "title": "CABO VERDE: the 110.265 peg, tourism, bunkering and the diaspora",
     "objects": ("the reserve path and months of import cover at the BCV",
                 "monthly arrivals and bed-nights by source market",
                 "port calls and bunker volumes at Mindelo and Praia",
                 "remittance inflows in the balance of payments"),
     "conditions": ("the tourist season versus the rest of the year",
                    "whether European discretionary-spending conditions were tightening",
                    "whether fuel costs were above or below their own median"),
     "instruments": ("EURUSD", "XBRUSD", "UK100"),
     "controls": ("the WAEMU peg over the same months, a hard euro peg with a DIFFERENT "
                  "guarantor, which is what makes this a control rather than a copy",
                  "Canary Islands arrivals as the competing mid-Atlantic destination",
                  "matched seasons"),
     "notes": "an archipelago with no mines and no farmland is a EUROPEAN DEMAND reading rather "
              "than an African supply one, which is exactly why it is the third control"},
    {"id": "SC-T", "title": "REGIONAL: the Gulf of Guinea piracy plane and the war-risk premium",
     "objects": ("IMB quarterly incident and crew-kidnapping counts by location",
                 "the listed-area designations and their dates",
                 "MDAT-GoG advisories between reports"),
     "conditions": ("whether the incident count was above or below its own trailing median",
                    "whether a listed-area designation changed that quarter",
                    "whether the incident involved a tanker"),
     "instruments": ("XBRUSD", "XTIUSD"),
     "controls": ("global tanker rates, which must be controlled before any differential claim",
                  "Somali-basin incident counts in the same quarters, which separate 'piracy' "
                  "from 'Gulf of Guinea piracy'",
                  "matched quarters with no designation change"),
     "notes": "a two-sided series: it records both the rise to a regional peak in crew "
              "kidnapping and the sharp fall afterwards, so it is a test and not a scare"},
    {"id": "SC-U", "title": "REGIONAL: three exchange-rate regimes as one natural experiment",
     "objects": ("the XOF parity at 655.957 and the CVE parity at 110.265, both unmoving",
                 "the SLE, LRD and GMD paths and their bureau spreads",
                 "the inflation and terms-of-trade paths of all eight",
                 "the IMF Article IV consultation dates, which are the data releases"),
     "conditions": ("the regime: XOF peg, CVE peg, or float",
                    "whether the jurisdiction had a commodity shock that year",
                    "whether the float was dollarised (Liberia) or not"),
     "instruments": ("EURUSD", "USDZAR", "XAUUSD"),
     "controls": ("Cabo Verde against WAEMU, which holds the anchor fixed and varies the "
                  "GUARANTOR",
                  "Liberia against Sierra Leone and The Gambia, which holds the float fixed and "
                  "varies DOLLARISATION",
                  "the same years in Guinea, which floats and belongs to `west_africa`"),
     "notes": "EIGHT JURISDICTIONS, THREE REGIMES, ONE PACK. This is the reason the eight are "
              "carried together rather than as eight thin country files"},
    {"id": "SC-V", "title": "REGIONAL: the EU and Chinese fisheries licences",
     "objects": ("the EU SFPA protocols' reference tonnages, licence counts and financial "
                 "contributions, in the published legal texts",
                 "Chinese distant-water fleet licence reporting and port calls",
                 "the fishmeal and fish-oil trade flows out of the region"),
     "conditions": ("whether a protocol was in force, lapsed or under renegotiation",
                    "whether the tuna season was in its peak months",
                    "whether the Chinese fleet's licensed capacity rose that year"),
     "instruments": ("SOYBEAN", "CORN", "USDCNH"),
     "controls": ("Mauritanian and Senegalese protocols in the same years, which belong to "
                  "sibling packs and separate a regional policy from a national one",
                  "world fishmeal prices and soybean-meal substitution",
                  "years with no protocol change"),
     "notes": "a LICENCE REGIME with hard numbers inside a published legal act, in a domain that "
              "otherwise has almost none; the executable link is fishmeal-for-soymeal and it is "
              "labelled weak"},
    {"id": "SC-W", "title": "REGIONAL: eight calendars, two Christian traditions, five sightings",
     "objects": ("the eight national holiday tables and the days on which they coincide",
                 "the Islamic feasts and their drift of about eleven days a year",
                 "Carnival in Cabo Verde and the three Liberian weekday-rule holidays"),
     "conditions": ("how many of the eight closed that day",
                    "whether the closure was Christian, Islamic or civic",
                    "whether the day fell inside a campaign or trade season"),
     "instruments": ("XAUUSD", "COTTON", "EURUSD"),
     "controls": ("the matched weekday twenty-six weeks away",
                  "days on which exactly ONE of the eight closed, which is the separating case",
                  "the same feast in a year when it fell in a different solar month"),
     "notes": "with eight calendars most days are one-country days; the union table is TAGGED for "
              "exactly that reason, and the Islamic drift is free identification"},
)

#: Which jurisdiction owns each domain. A regional domain names all eight.
DOMAIN_JURISDICTION: dict[str, tuple[str, ...]] = {
    "SC-A": ("ne",), "SC-B": ("ne", "bj"), "SC-C": ("ne",), "SC-D": ("ne",),
    "SC-E": ("lr",), "SC-F": ("lr",), "SC-G": ("lr",),
    "SC-H": ("tg",), "SC-I": ("tg",), "SC-J": ("tg",),
    "SC-K": ("bj",), "SC-L": ("bj",), "SC-M": ("bj",),
    "SC-N": ("sl",), "SC-O": ("sl",), "SC-P": ("sl",),
    "SC-Q": ("gm",), "SC-R": ("gw",), "SC-S": ("cv",),
    "SC-T": JURISDICTIONS, "SC-U": JURISDICTIONS, "SC-V": ("gm", "gw", "cv", "lr"),
    "SC-W": JURISDICTIONS,
}
DOMAIN_MECHANISM: dict[str, str] = {
    "SC-A": "supply_shock", "SC-B": "capacity_ramp", "SC-C": "sanctions_regime",
    "SC-D": "weather", "SC-E": "capacity", "SC-F": "physical_flow", "SC-G": "dollarisation",
    "SC-H": "chokepoint", "SC-I": "administered_price", "SC-J": "input_cost",
    "SC-K": "chokepoint", "SC-L": "policy_timetable", "SC-M": "administered_price",
    "SC-N": "physical_flow", "SC-O": "regime_break", "SC-P": "mirror_statistic",
    "SC-Q": "seasonal_flow", "SC-R": "administered_price", "SC-S": "nominal_demand",
    "SC-T": "risk_premium", "SC-U": "peg_regime", "SC-V": "licence_regime",
    "SC-W": "holiday_liquidity",
}
DOMAIN_HORIZON: dict[str, str] = {
    "SC-A": "1 to 4 quarters", "SC-B": "0 to 10 sessions", "SC-C": "2 to 12 weeks",
    "SC-D": "1 to 2 quarters", "SC-E": "1 to 4 quarters", "SC-F": "1 to 3 quarters",
    "SC-G": "1 to 2 quarters", "SC-H": "2 to 8 weeks", "SC-I": "1 to 3 quarters",
    "SC-J": "1 to 2 campaigns", "SC-K": "2 to 8 weeks", "SC-L": "1 to 2 campaigns",
    "SC-M": "1 to 3 quarters", "SC-N": "1 to 3 quarters", "SC-O": "1 to 2 quarters",
    "SC-P": "1 to 4 quarters", "SC-Q": "0 to 8 weeks", "SC-R": "1 to 3 quarters",
    "SC-S": "0 to 2 quarters", "SC-T": "0 to 10 sessions", "SC-U": "1 to 4 quarters",
    "SC-V": "1 to 4 quarters", "SC-W": "0 to 2 sessions",
}

# --------------------------------------------------------------------------- custom miners
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    {"name": "sc_uranium_permits", "domain_ids": ("SC-A",), "kind": "event",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.sahel_coast.pack:mine_uranium_permits",
     "needs": ("URANIUM_EVENTS", "Euratom origin and cover table", "XNGUSD and FRA40 H1 bars"),
     "notes": "the permit actions as dated events, routed through European power and gas with "
              "the inventory-cover state as the conditioning variable"},
    {"name": "sc_pipeline_switch", "domain_ids": ("SC-B", "SC-K"), "kind": "event",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.sahel_coast.pack:mine_pipeline_switch",
     "needs": ("PIPELINE_EVENTS", "XBRUSD H1 bars", "Beninese transit declarations"),
     "notes": "a 90,000 b/d line with a political on/off switch; the trade-balance leg is tested "
              "before the price leg"},
    {"name": "sc_bloc_rupture", "domain_ids": ("SC-C", "SC-H"), "kind": "macro",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.sahel_coast.pack:mine_bloc_rupture",
     "needs": ("ECOWAS_EVENTS", "Lome and Cotonou transit tonnage", "UMOA-Titres cut-offs"),
     "notes": "three dated communiques against two corridor series and a weekly auction"},
    {"name": "sc_registry_tonnage", "domain_ids": ("SC-E",), "kind": "physical",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.sahel_coast.pack:mine_registry_tonnage",
     "needs": ("LISCR fleet statistics", "UNCTAD maritime annex", "XBRUSD and XTIUSD D1 bars"),
     "notes": "re-flagging is ZERO SUM, so this miner cannot run without the competing "
              "registers' tonnage as the control"},
    {"name": "sc_campaign_prices", "domain_ids": ("SC-I", "SC-M", "SC-R"), "kind": "release",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.sahel_coast.pack:mine_campaign_prices",
     "needs": ("CAMPAIGN_EVENTS", "COTTON D1 bars", "USDA FAS area and production"),
     "notes": "three administered prices -- Togolese cotton, Beninese cotton and Bissau-Guinean "
              "cashew -- announced before the world price is known, each other's placebo"},
    {"name": "sc_redenomination_boundary", "domain_ids": ("SC-O", "SC-U"), "kind": "macro",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.sahel_coast.pack:mine_redenomination_boundary",
     "needs": ("POLICY_ERAS", "BSL auction and bureau series"),
     "notes": "the 1000:1 step of 2022-07-01 as a UNIT change: the ratio must be continuous "
              "across it or something else happened"},
    {"name": "sc_calendar_plane", "domain_ids": ("SC-W", "SC-Q"), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.sahel_coast.pack:mine_calendar_plane",
     "needs": ("HOLIDAYS_RULE", "XAUUSD, COTTON and EURUSD H1 bars"),
     "notes": "eight calendars, two Christian traditions and five sighting authorities, with the "
              "one-country-closed days as the separating control"},
    {"name": "sc_transmission_seeds",
     "domain_ids": ("SC-D", "SC-F", "SC-G", "SC-J", "SC-L", "SC-N", "SC-P", "SC-S", "SC-T",
                    "SC-V"),
     "kind": "transfer", "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.sahel_coast.pack:mine_transmission_seeds",
     "needs": ("TRANSMISSION_EDGES_SEED",),
     "notes": "the pack's map as HYPOTHESIS discoveries, deduplicated by the registry"},
)
MINER_DOMAINS: dict[str, tuple[str, ...]] = {
    "central_bank_surprise": ("SC-O", "SC-U"), "release_surprise": ("SC-I", "SC-M", "SC-R"),
    "calendar_settlement": ("SC-W", "SC-Q"), "holiday_liquidity": ("SC-W",),
    "positioning": ("SC-E",), "carry_funding": ("SC-U", "SC-G"),
    "corporate_flow": ("SC-A", "SC-F"), "institutional_flow": ("SC-C", "SC-S"),
    "equity_mechanics": ("SC-S",), "derivatives_expiry": ("SC-T",),
    "failure": ("SC-B", "SC-K"), "residual": ("SC-D", "SC-J"),
    "transfer": ("SC-Q", "SC-V"), "scouts": ("SC-N", "SC-P"),
    "session_microstructure": ("SC-W", "SC-H"),
}

# --------------------------------------------------------------------------- transmission
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    {"id": "SC-E1", "source": "Nigerien uranium permit actions and operational interruptions",
     "target": "XNGUSD", "targets": ("XNGUSD", "FRA40", "EUSTX50", "GER40"),
     "to_country": "europe", "sign": "+",
     "mechanism": "a top-seven producer and a large share of EU utility supply loses or changes "
                  "operator; the perceived cost and risk of the European nuclear leg rises, "
                  "which is priced in POWER and therefore in gas substitution and in the "
                  "utility-heavy indices. URANIUM IS NOT AN INSTRUMENT and the route is stated "
                  "explicitly rather than proxied",
     "horizon": "1 to 4 quarters", "horizon_class": "multi_day", "lag_days": 60.0,
     "actor": "the Nigerien mining authority, the operator and the EU utilities",
     "constraint": "EU inventory cover is measured in YEARS, which is what blunts the channel",
     "flow": "natural uranium deliveries to EU utilities, by origin",
     "condition": "a gazetted permit action or a reported operational interruption",
     "control": "Kazakh and Canadian supply events in the same years; matched non-event days on "
                "the European power and gas complex; the same windows in 2015-2019",
     "falsifier": "the Euratom origin table shows no fall in the Nigerien share across 2023-2025 "
                  "and inventory cover is unchanged, which kills the price leg outright",
     "evidence": "HYPOTHESIS"},
    {"id": "SC-E2", "source": "Agadem-Seme crude loadings and their political interruptions",
     "target": "XBRUSD", "targets": ("XBRUSD", "XTIUSD"), "to_country": "global", "sign": "-",
     "mechanism": "a new ~90,000 b/d supply line switching on and off for political reasons is a "
                  "dated physical event with a published on/off clock",
     "horizon": "0 to 10 sessions", "horizon_class": "intraday_to_multi_day", "lag_days": 2.0,
     "actor": "the pipeline operator, the Beninese state and the lifting buyers",
     "constraint": "one export route through one foreign terminal",
     "flow": "cargo loadings at Seme-Kpodji",
     "condition": "an interruption or resumption announcement",
     "control": "matched non-event days; Chinese import volumes from Niger in the following "
                "quarter; other West African interruptions of similar size",
     "falsifier": "the 2024 interruptions show no effect on Chinese imports from Niger in the "
                  "following quarter, making them a negotiation rather than a supply event",
     "evidence": "HYPOTHESIS"},
    {"id": "SC-E3", "source": "ECOWAS sanctions and the AES withdrawal",
     "target": "CORN", "targets": ("CORN", "WHEAT", "SUGAR"), "to_country": "sahel", "sign": "+",
     "mechanism": "a closed border raises the landed cost of everything three landlocked "
                  "economies import, which is a corridor-cost shock with three dated communiques",
     "horizon": "2 to 12 weeks", "horizon_class": "multi_day", "lag_days": 21.0,
     "actor": "ECOWAS, the AES states and the coastal ports",
     "constraint": "landlocked members whose trade must cross coastal members' territory",
     "flow": "port transit tonnage to Niger at Cotonou and Lome",
     "condition": "a summit communique imposing, lifting or effecting a withdrawal",
     "control": "Burkina's and Mali's corridors over the same months; total ECOWAS import "
                "volumes; the Benin auction cut-off as the regional rate control",
     "falsifier": "transit tonnage, the Nigerien cut-off and Sahelian prices show no "
                  "discontinuity at any of the three dates",
     "evidence": "MEASURED_ELSEWHERE"},
    {"id": "SC-E4", "source": "Liberian-flag tanker deadweight tonnage and its age profile",
     "target": "XBRUSD", "targets": ("XBRUSD", "XTIUSD", "UK100"), "to_country": "global",
     "sign": "-",
     "mechanism": "growth in tanker DWT on the world's second register is future freight "
                  "SUPPLY, and a surge of OLDER tanker tonnage arriving is the published "
                  "footprint of grey-fleet formation -- both of which change effective capacity "
                  "and therefore the freight cost inside a delivered crude price",
     "horizon": "1 to 4 quarters", "horizon_class": "multi_day", "lag_days": 90.0,
     "actor": "the registry and the shipowners who re-flag",
     "constraint": "re-flagging is ZERO SUM between open registers",
     "flow": "vessels and tonnage joining and leaving the register",
     "condition": "a quarter in which tanker DWT grew faster than world fleet DWT, or in which "
                  "arriving tonnage was older than the fleet median",
     "control": "Panama's and the Marshall Islands' tonnage; total world fleet growth; "
                "dirty-tanker rates with fleet growth controlled for",
     "falsifier": "Liberian-flag tanker tonnage has no relationship to subsequent freight rates "
                  "or to world fleet age once total growth is controlled for",
     "evidence": "HYPOTHESIS"},
    {"id": "SC-E5", "source": "Lome and Cotonou transit throughput to the landlocked Sahel",
     "target": "WHEAT", "targets": ("WHEAT", "CORN", "SUGAR", "COTTON"), "to_country": "sahel",
     "sign": "+",
     "mechanism": "two quays carry the entire import bill of three landlocked economies; a "
                  "throughput or clearance-time shock is a delivered-price shock inland",
     "horizon": "2 to 8 weeks", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "the two port authorities, the customs services and the transit agents",
     "constraint": "one long road north, increasingly insecure",
     "flow": "monthly transit tonnage by destination country",
     "condition": "a month in which transit fell more than its own interquartile range",
     "control": "THE OTHER PORT over the same months, because a fall here that appears as a rise "
                "there is ROUTING and carries no supply information; Abidjan and Tema; total "
                "West African container volumes",
     "falsifier": "the two ports' transit series move together rather than as substitutes, which "
                  "would mean the corridors are not alternatives and the chokepoint story fails",
     "evidence": "HYPOTHESIS"},
    {"id": "SC-E6", "source": "The Benin and Togo cotton campaign farmgate price announcements",
     "target": "COTTON", "targets": ("COTTON",), "to_country": "global", "sign": "+",
     "mechanism": "a guaranteed price announced BEFORE sowing fixes the producers' incentive "
                  "for a whole season; the supply response appears in area and then in lint from "
                  "Africa's largest cotton producer in several recent seasons",
     "horizon": "1 to 3 quarters", "horizon_class": "multi_day", "lag_days": 180.0,
     "actor": "the AIC and the NSCT and their producers' unions",
     "constraint": "a price announced before the world price is known, and input credit that "
                   "fails when the world price falls",
     "flow": "area sown, seed cotton collected, lint exported",
     "condition": "an announced price above or below the previous year's world price",
     "control": "the neighbouring country's announcement in the same campaign; Ivorian, Malian "
                "and Burkinabe area; campaigns with no price change",
     "falsifier": "area responds to rainfall and not to the announced price differential in "
                  "either country, making the announcement an accounting act",
     "evidence": "HYPOTHESIS"},
    {"id": "SC-E7", "source": "Benin's raw-export restrictions and the GDIZ processing mandate",
     "target": "USDCNH", "targets": ("USDCNH", "COTTON", "SOYBEAN"), "to_country": "asia",
     "sign": "-",
     "mechanism": "a dated ban on raw exports removes supply from Indian and Vietnamese "
                  "processors unless the nut leaks across a border; the BUYERS' customs data "
                  "decides which happened",
     "horizon": "1 to 2 campaigns", "horizon_class": "multi_day", "lag_days": 120.0,
     "actor": "the Beninese state, the zone's processors and the Asian buyers",
     "constraint": "processing capacity must exist before a ban can bind",
     "flow": "raw versus processed exports, measured on the importers' side",
     "condition": "a gazetted commencement or amendment date",
     "control": "Ivorian and Ghanaian raw exports in the same campaigns as the leakage control; "
                "Indian and Vietnamese TOTAL raw imports as the demand-cycle control",
     "falsifier": "Asian imports from Benin are unchanged while imports from its neighbours "
                  "rise, which would mean the ban re-routed rather than processed the nut",
     "evidence": "HYPOTHESIS"},
    {"id": "SC-E8", "source": "The Guinea-Bissau decreed cashew reference price",
     "target": "WHEAT", "targets": ("WHEAT", "CORN"), "to_country": "gw", "sign": "-",
     "mechanism": "an administered price on nine tenths of a country's export earnings sets its "
                  "grain-import CAPACITY; with a hard peg and no devaluation available the shock "
                  "shows up in import volumes and in arrears",
     "horizon": "1 to 3 quarters", "horizon_class": "multi_day", "lag_days": 120.0,
     "actor": "the campaign committee, the farmers and the Asian buyers",
     "constraint": "porous borders with Senegal and Guinea",
     "flow": "campaign tonnage, levy receipts and cereal imports",
     "condition": "a decreed price materially above or below the regional market",
     "control": "Senegalese and Guinean recorded exports as leakage; Asian total raw imports; "
                "campaigns whose decreed price tracked the market",
     "falsifier": "years with an over-set decreed price show no fall in Bissau's recorded "
                  "exports and no rise in its neighbours', meaning the decree does not bind",
     "evidence": "HYPOTHESIS"},
    {"id": "SC-E9", "source": "Sierra Leonean rutile and ilmenite export tonnage",
     "target": "XZNUSD", "targets": ("XZNUSD", "EUSTX50", "GER40"), "to_country": "europe",
     "sign": "-",
     "mechanism": "a top world producer of the highest-grade titanium feedstock changes "
                  "delivered volume into a concentrated European pigment buyer base. STATED WEAK: "
                  "the buyers are single names the two-lane order forbids hunting and the "
                  "assessments forbid machine extraction",
     "horizon": "1 to 3 quarters", "horizon_class": "multi_day", "lag_days": 90.0,
     "actor": "the mineral-sands operator, the NMA and the pigment producers",
     "constraint": "an assessment-priced market with no exchange and no executable contract",
     "flow": "export tonnage in the partner mirrors",
     "condition": "a lease or royalty decision, or a dredge-transition quarter",
     "control": "Australian and South African mineral-sands volumes; matched quarters with no "
                "lease event; the industrial-metals complex as the global-cycle control",
     "falsifier": "no relationship to any executable instrument at any lag -- WHICH IS THE "
                  "OUTCOME THIS PACK EXPECTS, and the fiscal leg of SC-N survives it",
     "evidence": "HYPOTHESIS"},
    {"id": "SC-E10", "source": "The Sierra Leonean redenomination of 2022-07-01",
     "target": "USDZAR", "targets": ("USDZAR", "XAUUSD"), "to_country": "sl", "sign": "+",
     "mechanism": "a 1000:1 unit change that is NOT a price move; the auction-minus-bureau "
                  "SPREAD is a ratio and must be continuous across it if the break is what it "
                  "claims to be",
     "horizon": "1 to 2 quarters", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "the Bank of Sierra Leone and the bureaux",
     "constraint": "a redenomination that changes the unit and not the inflation",
     "flow": "auction volumes and clearing rates against the bureau survey",
     "condition": "the side of 2022-07-01 the observation sits on",
     "control": "THE RATIO ITSELF as the invariance test; The Gambia's and Liberia's floats over "
                "the same months; quarters with no programme review",
     "falsifier": "the ratio is discontinuous at the boundary, which would mean something other "
                  "than a unit change happened and the era table is wrong",
     "evidence": "DESK_MEASURED"},
    {"id": "SC-E11", "source": "The XOF and CVE hard euro pegs",
     "target": "EURUSD", "targets": ("EURUSD",), "to_country": "global", "sign": "+",
     "mechanism": "AN IDENTITY, NOT A PROXY. A hard peg at 655.957 and at 110.265 makes every "
                  "XOF and CVE price a euro price divided by a constant, so the dollar exposure "
                  "of five of these eight economies IS EURUSD",
     "horizon": "1 to 4 quarters", "horizon_class": "multi_day", "lag_days": 0.0,
     "actor": "the BCEAO, the Banco de Cabo Verde and their two guarantors",
     "constraint": "the parity has moved once in sixty years in the XOF's case and never in the "
                   "CVE's since 1998",
     "flow": "every euro-invoiced trade and transfer of the five pegged jurisdictions",
     "condition": "any dollar-denominated commodity receipt in a pegged jurisdiction",
     "control": "the three floaters over the same months; Guinea's float, which belongs to "
                "`west_africa`; the two pegs against EACH OTHER, which varies the guarantor",
     "falsifier": "pegged and floating jurisdictions show the same real-exchange-rate and "
                  "inflation response to a commodity shock, which would mean the regime variable "
                  "is not doing the work SC-U assigns it",
     "evidence": "MEASURED_ELSEWHERE"},
    {"id": "SC-E12", "source": "The SLE, LRD and GMD floats and their bureau spreads",
     "target": "USDZAR", "targets": ("USDZAR", "XAUUSD"), "to_country": "global", "sign": "+",
     "mechanism": "three frontier floats with published official-versus-bureau spreads; the "
                  "spread is the stress state, and USDZAR is the LIQUID CARRIER the desk can "
                  "actually trade -- a carrier and never a substitute",
     "horizon": "1 to 2 quarters", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "the three central banks and their bureaux",
     "constraint": "the rand carries South African idiosyncratic risk none of the three has",
     "flow": "auction and bureau turnover, reserves, import cover",
     "condition": "a spread above its own trailing median",
     "control": "the rand's own domestic drivers, which must be removed first; the two pegged "
                "jurisdictions over the same months; matched quarters",
     "falsifier": "the three spreads have no common component once the rand's domestic drivers "
                  "are removed, which would mean there is no 'frontier West African stress' "
                  "factor to carry at all",
     "evidence": "HYPOTHESIS"},
    {"id": "SC-E13", "source": "Gulf of Guinea piracy incidents and listed-area designations",
     "target": "XBRUSD", "targets": ("XBRUSD", "XTIUSD"), "to_country": "global", "sign": "+",
     "mechanism": "a war-risk premium priced off a counted incident series; the designation "
                  "changes are dated administrative acts and insurers respond to designations "
                  "rather than to incidents",
     "horizon": "0 to 10 sessions", "horizon_class": "intraday_to_multi_day", "lag_days": 5.0,
     "actor": "the underwriters, the reporting centres and the regional navies",
     "constraint": "a large sea area, limited naval capacity and heavy under-reporting",
     "flow": "incident and kidnapping counts, and the resulting freight differential",
     "condition": "an incident count above its trailing median, or a designation change",
     "control": "global tanker rates; Somali-basin counts in the same quarters, which separate "
                "'piracy' from 'Gulf of Guinea piracy'; quarters with no designation change",
     "falsifier": "West African crude freight differentials do not respond to designations or "
                  "counts once global rates are controlled for, making the premium a fixed cost",
     "evidence": "HYPOTHESIS"},
    {"id": "SC-E14", "source": "EU and Chinese fisheries licences off West Africa",
     "target": "SOYBEAN", "targets": ("SOYBEAN", "CORN", "USDCNH"), "to_country": "global",
     "sign": "-",
     "mechanism": "licensed tonnage and reference tonnages in published legal acts change the "
                  "landed catch, which reaches the FEED complex through fishmeal, whose "
                  "substitute is soybean meal. WEAK and labelled weak",
     "horizon": "1 to 4 quarters", "horizon_class": "multi_day", "lag_days": 120.0,
     "actor": "DG MARE, the Chinese distant-water fleet and the four coastal states",
     "constraint": "the fishmeal share of the feed complex is small",
     "flow": "licensed vessels, reference tonnage, fishmeal and fish-oil exports",
     "condition": "a protocol in force, lapsed or under renegotiation",
     "control": "Mauritanian and Senegalese protocols, which belong to sibling packs; world "
                "fishmeal prices; years with no protocol change",
     "falsifier": "fishmeal volumes out of the region show no relationship to protocol status, "
                  "which would leave this edge as a fiscal observable for four small states",
     "evidence": "HYPOTHESIS"},
    {"id": "SC-E15", "source": "Sahel rainfall, the Harmattan and the Cadre Harmonise phase",
     "target": "CORN", "targets": ("CORN", "WHEAT", "COTTON", "SUGAR"), "to_country": "sahel",
     "sign": "+",
     "mechanism": "one rainy season sets the cotton, cereal and cashew campaigns from Niamey to "
                  "Bissau; a deficit raises the region's import demand for grain and lowers the "
                  "following campaign's cotton area",
     "horizon": "1 to 2 quarters", "horizon_class": "multi_day", "lag_days": 90.0,
     "actor": "the farmers, the interprofessions and the import traders",
     "constraint": "rain-fed agriculture with almost no irrigation",
     "flow": "sown area, harvested output, cereal import volumes",
     "condition": "a seasonal forecast or realised rainfall below its own historical band",
     "control": "the same calendar windows in normal-rainfall years; the Ivorian and Ghanaian "
                "forest zone, which has a different climate; world grain prices",
     "falsifier": "regional cereal import volumes and cotton area show no response to the "
                  "dekadal rainfall series once world prices are controlled for",
     "evidence": "MEASURED_ELSEWHERE"},
    {"id": "SC-E16", "source": "Gambian, Cabo Verdean and Sierra Leonean remittance inflows",
     "target": "EURUSD", "targets": ("EURUSD", "UK100"), "to_country": "global", "sign": "+",
     "mechanism": "remittances are a very large share of GDP in three of these eight and are "
                  "published monthly for two; they arrive in euros and sterling and are spent on "
                  "imports, with a seasonal peak around Tabaski and Christmas",
     "horizon": "0 to 8 weeks", "horizon_class": "multi_day", "lag_days": 40.0,
     "actor": "the diaspora, the transfer operators and the three central banks",
     "constraint": "a large informal share that never reaches the official series",
     "flow": "monthly inflows by source country",
     "condition": "the distance in days to the next Aid el-Kebir, which drifts eleven days a year",
     "control": "matched calendar months in years when Tabaski fell in a different solar month; "
                "European labour-market conditions; the tourist season",
     "falsifier": "the bureau spread and import volumes show no seasonal pattern aligned with "
                  "the drifting feast, which would mean the inflows are smoothed away",
     "evidence": "HYPOTHESIS"},
)

# --------------------------------------------------------------------------- policy eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    {"name": "REGIONAL: the XOF hard peg to the euro", "start": "1999-01-01", "end": "2026-12-31",
     "regime": "655.957 XOF = 1 EUR, unchanged since the euro replaced the French franc and "
               "derived from the 1994-01-12 devaluation; the French Treasury guarantee survived "
               "the 2019 reform that renamed the currency and ended reserve centralisation",
     "markers": ("1994-01-12 the 50% devaluation", "1999-01-01 the euro conversion",
                 "2019-12-21 the Eco reform announcement, which changed everything but the "
                 "parity"),
     "why_it_matters": "four of this pack's eight have NO exchange-rate adjustment, so their "
                       "shocks appear in auctions, arrears and trade and never in a currency",
     "status": "OPEN"},
    {"name": "CABO VERDE: the escudo peg under the Portuguese agreement", "start": "1998-07-01",
     "end": "2026-12-31",
     "regime": "110.265 CVE = 1 EUR under the Acordo de Cooperacao Cambial with Portugal, with a "
               "Portuguese credit facility behind it",
     "markers": ("1998 the agreement is signed", "1999 the anchor converts to the euro"),
     "why_it_matters": "a SECOND hard euro peg with a DIFFERENT guarantor, which is the control "
                       "that lets SC-U ask whether the XOF's behaviour is about pegs or France",
     "status": "OPEN"},
    {"name": "NIGER: the coup, the sanctions and the AES", "start": "2023-07-26",
     "end": "2026-12-31",
     "regime": "the CNSP takes power on 2023-07-26; ECOWAS imposes sanctions and closes borders "
               "on 2023-07-30 and lifts most of them on 2024-02-24; Niger, Mali and Burkina "
               "announce withdrawal from ECOWAS on 2024-01-28 and sign the AES confederation "
               "treaty in July 2024; the withdrawal takes effect 2025-01-29",
     "markers": ("2023-07-26 the coup", "2023-07-30 sanctions and border closures",
                 "2024-01-28 the withdrawal announcement", "2024-02-24 sanctions lifted",
                 "2025-01-29 the withdrawal takes effect"),
     "why_it_matters": "THE BOUNDARY THAT PARTITIONS EVERY NIGERIEN SERIES IN THIS PACK, and one "
                       "with five citable dates rather than a vague 'since the coup'",
     "status": "OPEN"},
    {"name": "NIGER: the uranium concession reset", "start": "2024-06-01", "end": "2026-12-31",
     "regime": "the Imouraren operating permit is withdrawn in June 2024; operational control of "
               "Somair is lost to the operator through late 2024 and nationalisation is "
               "announced in 2025; the export route and the buyers change with it",
     "markers": ("2024-06 the Imouraren permit withdrawal",
                 "2024-12 loss of operational control of Somair [PRESS_REPORTED]",
                 "2025-06 the announced nationalisation of Somair [PRESS_REPORTED]"),
     "why_it_matters": "ownership and deliveries are DIFFERENT SERIES and this era is the reason "
                       "SC-A tests the Euratom origin table rather than the headlines",
     "status": "OPEN"},
    {"name": "NIGER AND BENIN: the crude era begins", "start": "2024-05-01", "end": "2026-12-31",
     "regime": "the Agadem-Seme line loads its first export cargo in May 2024; loadings are "
               "interrupted and resumed repeatedly through 2024 as the Niger-Benin border "
               "dispute plays out",
     "markers": ("2024-05 the first export loading [PRESS_REPORTED]",
                 "2024-06 loadings interrupted amid the border dispute [PRESS_REPORTED]",
                 "2024-2025 resumptions and further interruptions"),
     "why_it_matters": "any pre-2024 Nigerien external series is from a different economy, and "
                       "the series that measures this one is SHORT -- no cell may pretend "
                       "otherwise",
     "status": "OPEN"},
    {"name": "SIERRA LEONE: the leone redenomination", "start": "2022-07-01", "end": "2022-12-31",
     "regime": "1000:1 redenomination with a dual-circulation period; the ISO code changes from "
               "SLL to SLE",
     "markers": ("2022-07-01 the changeover", "2022-H2 the dual-circulation period"),
     "why_it_matters": "A 1000x STEP THAT IS NOT A PRICE MOVE. Any leone series pooled across "
                       "this boundary is measuring a unit change; the auction-minus-bureau RATIO "
                       "is the invariant that must be continuous",
     "status": "SETTLED"},
    {"name": "LIBERIA: the fiscal year moves to a calendar year", "start": "2021-07-01",
     "end": "2021-12-31",
     "regime": "a TRANSITIONAL SIX-MONTH BUDGET covering July to December 2021, after which the "
               "fiscal year runs January to December",
     "markers": ("2021-07 the transitional budget", "2022-01 the first calendar fiscal year"),
     "why_it_matters": "an annual Liberian fiscal series pooled across this window is treating a "
                       "six-month budget as a year, which is a 2x error nobody notices",
     "status": "SETTLED"},
    {"name": "LIBERIA: the registry passes Panama on gross tonnage", "start": "2022-01-01",
     "end": "2026-12-31",
     "regime": "the Liberian register overtakes Panama on gross tonnage on some published "
               "measures during 2022-2024, while remaining second on several others; the "
               "composition shifts as sanctions regimes push tonnage between open registers",
     "markers": ("2022 the registry announces passing Panama on gross tonnage",
                 "2022-2024 sanctions-driven re-flagging between open registers"),
     "why_it_matters": "the level matters less than the COMPOSITION: which tonnage arrived, how "
                       "old it was and what it carries is what makes SC-E an economic series",
     "status": "OPEN"},
    {"name": "BENIN: the GDIZ and the raw-export restrictions", "start": "2024-01-01",
     "end": "2026-12-31",
     "regime": "restrictions on raw cashew and soybean exports commence on gazetted dates from "
               "2024 as the industrial zone's processing capacity ramps",
     "markers": ("2024 the raw cashew export restriction takes effect [PRESS_REPORTED]",
                 "2024-2025 the zone's processing capacity ramp"),
     "why_it_matters": "the dated commencement is the treatment and the ASIAN IMPORT MIRROR is "
                       "the outcome; a study using Beninese export data alone measures the "
                       "policy's paperwork",
     "status": "OPEN"},
    {"name": "GUINEA-BISSAU: WAEMU membership", "start": "1997-05-02", "end": "2026-12-31",
     "regime": "the peso is abandoned and the XOF adopted; monetary financing ends and a "
               "monocrop shock becomes arrears rather than inflation",
     "markers": ("1997-05-02 accession", "the annual cashew campaign decree ever since"),
     "why_it_matters": "the cleanest demonstration in the pack of what a hard peg DOES to a "
                       "commodity shock, and the reason SC-R tests arrears and import capacity",
     "status": "OPEN"},
    {"name": "REGIONAL: the Gulf of Guinea piracy peak and its collapse", "start": "2018-01-01",
     "end": "2026-12-31",
     "regime": "the region accounts for the large majority of world crew kidnapping through "
               "2018-2021 and then the incident count falls sharply from 2022 as naval presence "
               "and industry measures increase",
     "markers": ("2018-2021 the kidnapping peak", "2022 onward the sharp decline"),
     "why_it_matters": "a TWO-SIDED series: the rise and the fall are both in it, which is what "
                       "makes SC-T a test rather than a scare",
     "status": "OPEN"},
    {"name": "REGIONAL: the EU Deforestation Regulation's compliance clock",
     "start": "2023-06-29", "end": "2026-12-31",
     "regime": "the EUDR enters into force covering cocoa, rubber and other commodities, with an "
               "application date for large operators that has been set and then delayed",
     "markers": ("2023-06-29 entry into force", "the announced application date and its delays"),
     "why_it_matters": "Liberian rubber and the region's cocoa re-exports are smallholder and "
                       "traceability-poor, so the predicted signature is a DESTINATION "
                       "re-routing rather than a flat price move",
     "status": "OPEN"},
)

ACCESS_CONSTRAINTS: tuple[dict[str, Any], ...] = (
    {"constraint": "none of the six currencies is quoted by this broker",
     "measured": "data/universe/universe.json holds no XOF, SLE, LRD, GMD, CVE or GNF symbol",
     "consequence": "the two euro pegs are expressed EXACTLY as EURUSD and the three floats are "
                    "carried as proxies with their controls named; each is in "
                    "TRANSMISSION_TARGETS with its regime"},
    {"constraint": "uranium, iron ore, rutile, cashew, rubber and registry tonnage have no "
                   "broker contract",
     "measured": "none appears in the broker registry, and the price-reporting agencies' terms "
                 "forbid machine extraction",
     "consequence": "each is routed EXPLICITLY with its control named and its weakness stated "
                    "before the test; sc_pra_assessments is registered machine_use_allowed=false"},
    {"constraint": "Niger's statistical publication narrowed sharply after July 2023",
     "measured": "series slipped or stopped and ministry sites went intermittently dark",
     "consequence": "the lawful substitutes are the BCEAO union aggregates, the UMOA-Titres "
                    "auction results by issuer, Euratom, the WNA profile and the PARTNER mirror "
                    "customs -- every one named in NO_LAWFUL_GROUND with its jurisdiction"},
    {"constraint": "WAEMU reserves are POOLED and published for the union only",
     "measured": "no national reserve or BoP series exists for NE, TG, BJ or GW",
     "consequence": "any 'Nigerien reserves' number is an IMF staff estimate with a review date "
                    "on it and is treated as one; the national signal is the auction"},
    {"constraint": "the UMOA-Titres portal, the LISCR fleet page and the port dashboards "
                   "overwrite in place",
     "measured": "each shows the current state and keeps no downloadable history",
     "consequence": "their point-in-time history exists only in the archive layer's crawls, and "
                    "the corresponding datasets carry pit_feasible=False by name"},
    {"constraint": "no retail margin or client-flow statistic exists in any of the eight",
     "measured": "no licensed retail leverage anywhere; CREPMF and the national regulators "
                 "publish no retail positioning",
     "consequence": "no microstructure claim may rest on a retail-flow number; the retail layer "
                    "is the STREET RATE ground at FRINGE credibility, declared per jurisdiction"},
    {"constraint": "Guinea-Bissau publishes almost no macroeconomic statistics",
     "measured": "no securities market, no domestic academic economics literature, and an INE "
                 "whose output is sparse and irregular",
     "consequence": "four layers are declared absent for `gw` WITH NAMED SUBSTITUTES -- the "
                    "lusophone corpus, the IMF ECF documents, the buyers' customs mirrors and "
                    "the lusophone press, which for this country IS the data plane"},
    {"constraint": "Cabo Verde alone is UTC-1 and the Liberian registry runs on US hours",
     "measured": "seven of the eight are UTC+0 year-round; the registry is administered from "
                 "Virginia on EST/EDT",
     "consequence": "a pack that assumed one African offset would mis-stamp every CV row by an "
                    "hour and every registry announcement by five"},
)

#: INTERACTION MINERS -- the other country packs this one has a MEASURABLE interaction with.
#: `west_africa` is FIRST and named as the owner of the BCEAO, the cocoa complex and the Sahel
#: gold of Mali and Burkina; this pack is its declared complement and not a second copy.
INTERACTIONS: tuple[dict[str, Any], ...] = (
    {"with": "west_africa",
     "mechanism": "THE OWNER OF THE OTHER HALF OF THIS SYSTEM. `west_africa` (ci, gn, ml, bf, "
                  "sn) holds the BCEAO's monetary seat and the peg's history, the BRVM tape, the "
                  "cocoa complex and the Sahel gold of Mali and Burkina. This pack is its "
                  "COMPLEMENT: the uranium, the crude line, the ports, the flag state and the "
                  "coastal remainder. Mali and Burkina are the OTHER TWO AES states, so the "
                  "ECOWAS rupture is jointly owned; Senegal is the other side of every Gambian "
                  "groundnut and re-export transaction; Guinea's Nimba ore wants Liberia's rail",
     "observable": "the UMOA-Titres cut-off of NE, TG, BJ and GW against CI's, SN's, ML's and "
                   "BF's, week by week; Lome's and Cotonou's transit against Abidjan's and "
                   "Dakar's; Gambian and Senegalese groundnut purchases across the open border",
     "targets": ("EURUSD", "COTTON", "CORN", "WHEAT", "XAUUSD"),
     "control": "the cross-issuer auction spread within one currency union is the only clean way "
                "to separate a national fiscal shock from a regional liquidity one, and NEITHER "
                "PACK CAN COMPUTE IT ALONE -- the strongest interaction in this file"},
    {"with": "ng",
     "mechanism": "Nigeria is Niger's and Benin's largest neighbour and the other side of the "
                  "informal trade that is a very large share of Niger's real external economy. "
                  "The naira devaluations of 2023-2024 moved the border cross rate violently, "
                  "and Beninese and Nigerien seed cotton, fuel and staples cross that border in "
                  "both directions depending on which way the rate has moved",
     "observable": "the street XOF/NGN rate in the Hausa-language ground against Nigerian market "
                   "prices for onions, cowpeas, cattle and fuel; Beninese re-export volumes",
     "targets": ("SUGAR", "CORN", "SOYBEAN", "COTTON"),
     "control": "Nigerian domestic conditions belong to `ng` and must be taken from that pack: a "
                "border-price move during a Nigerian fuel-subsidy shock is a Nigerian event"},
    {"with": "gh",
     "mechanism": "Ghana is the Gulf of Guinea's other coastal transit state and the sibling "
                  "case on cashew leakage: when Benin restricts raw exports, the nut can leave "
                  "through Ghana and Cote d'Ivoire instead. Tema competes with Lome and Cotonou "
                  "for the same landlocked Burkinabe cargo",
     "observable": "Ghanaian and Ivorian raw cashew exports against Benin's in the same "
                   "campaigns; Tema's transit tonnage against Lome's and Cotonou's",
     "targets": ("USCOCOA", "UKCOCOA", "COTTON", "USDCNH"),
     "control": "Ghana is the LEAKAGE CONTROL for SC-L: a Beninese ban that shows up as a "
                "Ghanaian export rise re-routed the nut rather than processing it"},
    {"with": "ma",
     "mechanism": "Morocco is the world's marginal phosphate supplier and the Sahel is one of "
                  "its markets, so Togolese phosphate and Sahelian fertiliser cost are priced "
                  "against Moroccan supply. Morocco's Atlantic Initiative also offers the "
                  "landlocked AES states an alternative ocean access, which is a direct "
                  "competitor to the Lome and Cotonou corridors",
     "observable": "Moroccan phosphate and fertiliser export volumes and prices against Togolese "
                   "shipments and Sahelian fertiliser prices; the Atlantic Initiative's dated "
                   "milestones against corridor transit volumes",
     "targets": ("COTTON", "CORN", "WHEAT"),
     "control": "the Moroccan half of the fertiliser edge belongs to `ma` and this pack must not "
                "measure it alone: a Sahelian input-price move during a Moroccan supply event is "
                "a Moroccan event"},
    {"with": "eg",
     "mechanism": "Egypt owns the Suez transit, and the Red Sea diversions that pushed tanker "
                  "and container traffic onto the Cape route in 2024 raised tonne-miles and "
                  "changed effective fleet capacity -- which is the same variable the Liberian "
                  "registry's tonnage measures from the supply side",
     "observable": "Suez transit counts and Cape-route diversions against Liberian-flag tanker "
                   "tonnage and West African freight differentials",
     "targets": ("XBRUSD", "XTIUSD", "UK100"),
     "control": "the Suez half belongs to `eg`; a freight move during a Red Sea disruption is a "
                "tonne-mile event and not a registry one, and only both packs together can say "
                "which"},
    {"with": "za",
     "mechanism": "USDZAR is the liquid African risk carrier that three unquotable frontier "
                  "floats route through, and South Africa's own cycle is the confound",
     "observable": "USDZAR and the SARB calendar as the risk-channel leg for the SLE, LRD and "
                   "GMD spreads",
     "targets": ("USDZAR", "XAUUSD"),
     "control": "A CARRIER IS NOT A SUBSTITUTE: the rand contains South African idiosyncratic "
                "risk none of these eight has, and every edge that routes through it says so on "
                "its face"},
)

INSTITUTIONAL_FLOW_SOURCES: tuple[str, ...] = (
    "UMOA-Titres weekly auction results by issuer for Niger, Togo, Benin and Guinea-Bissau",
    "Liberian Registry published fleet statistics (count, gross and deadweight tonnage, mix)",
    "Port of Lome and Port of Cotonou monthly throughput with the transit split by country",
    "Central Bank of The Gambia monthly remittance inflows with the source-country split",
    "Central Bank of Liberia dual-currency statistics and the dollarisation share",
    "Euratom Supply Agency annual origin shares and EU utility inventory cover",
    "Kimberley Process annual production and export statistics for Sierra Leone and Liberia",
    "BCEAO annual digital financial services report: mobile money value by member state",
    "UN Comtrade partner mirrors for uranium, cashew, rutile, iron ore and rubber",
)
SERIES: dict[str, str] = {
    "NE_AUCTION": "UMOATITRES:cutoff_ne", "NE_URANIUM": "WNA:production_ne",
    "NE_EU_SHARE": "ESA:origin_share_ne", "NE_CRUDE": "CUSTOMS:agadem_loadings",
    "NE_TRANSIT": "PAC_PAL:transit_ne", "NE_RAIN": "AGRHYMET:dekadal_ne",
    "TG_PORT": "PAL:tonnage_transit", "TG_COTTON": "NSCT:farmgate_price",
    "TG_PHOSPHATE": "PAL:phosphate_exports", "TG_CUSTOMS": "OTR:receipts",
    "BJ_PORT": "PAC:tonnage_transit", "BJ_COTTON": "AIC:farmgate_price",
    "BJ_CASHEW": "COMTRADE:in_vn_imports_bj", "BJ_GDIZ": "SGG:restriction_dates",
    "LR_FLEET": "LISCR:fleet_dwt", "LR_IRON": "NPA:buchanan_shipments",
    "LR_FX": "CBL:lrd_usd_rate", "LR_DOLLARISATION": "CBL:usd_deposit_share",
    "SL_FX": "BSL:auction_rate", "SL_SPREAD": "BSL:bureau_minus_auction",
    "SL_RUTILE": "NMA:rutile_exports", "SL_DIAMONDS": "KPCS:sl_carats",
    "GM_REMIT": "CBG:remittances_monthly", "GM_GROUNDNUT": "GBOS:groundnut_purchases",
    "GW_CASHEW_PRICE": "BO:preco_referencia_caju", "GW_AUCTION": "UMOATITRES:cutoff_gw",
    "CV_TOURISM": "INE:arrivals_bednights", "CV_RESERVES": "BCV:reserves",
    "REGIONAL_PIRACY": "IMB:gog_incidents", "REGIONAL_FISH": "EURLEX:sfpa_tonnage",
    "REGIONAL_MOMO": "BCEAO:mobile_money_value",
}

# --------------------------------------------------------------------------- mechanisms
#: THE DATED NIGERIEN URANIUM EVENTS. Rows are (date, what, status). PRESS_REPORTED means exactly
#: that: a date carried by the trade press, to be confirmed against a gazette before any cell is
#: promoted on it.
URANIUM_EVENTS: tuple[tuple[date, str, str], ...] = (
    (date(2023, 7, 26), "the CNSP takes power in Niamey", "ANNOUNCED"),
    (date(2023, 7, 30), "ECOWAS imposes sanctions and closes the borders", "ANNOUNCED"),
    (date(2024, 2, 24), "ECOWAS lifts most of the sanctions", "ANNOUNCED"),
    (date(2024, 6, 20), "the Imouraren operating permit is withdrawn from the operator",
     "PRESS_REPORTED"),
    (date(2024, 12, 4), "the operator loses operational control of Somair", "PRESS_REPORTED"),
    (date(2025, 6, 19), "the nationalisation of Somair is announced", "PRESS_REPORTED"),
)
#: The Agadem-Seme line's dated milestones. Rows are (date, what, status).
PIPELINE_EVENTS: tuple[tuple[date, str, str], ...] = (
    (date(2024, 5, 15), "the first export cargo loads at Seme-Kpodji", "PRESS_REPORTED"),
    (date(2024, 6, 6), "loadings are interrupted amid the Niger-Benin border dispute",
     "PRESS_REPORTED"),
    (date(2024, 7, 1), "loadings resume after mediation", "PRESS_REPORTED"),
    (date(2025, 1, 1), "the ramp toward the nameplate of roughly 90,000 b/d", "PROJECTED"),
)
#: The ECOWAS/AES rupture. Rows are (date, what, status).
ECOWAS_EVENTS: tuple[tuple[date, str, str], ...] = (
    (date(2023, 7, 30), "sanctions imposed and borders closed against Niger", "ANNOUNCED"),
    (date(2024, 1, 28), "Niger, Mali and Burkina Faso announce withdrawal from ECOWAS",
     "ANNOUNCED"),
    (date(2024, 2, 24), "most sanctions lifted", "ANNOUNCED"),
    (date(2024, 7, 6), "the AES confederation treaty is signed at Niamey", "ANNOUNCED"),
    (date(2025, 1, 29), "the withdrawal takes effect", "ANNOUNCED"),
)
#: The administered campaign prices that are announced before the world price is known. Rows are
#: (jurisdiction, crop, month the notice normally falls in).
CAMPAIGN_EVENTS: tuple[tuple[str, str, int], ...] = (
    ("tg", "cotton", 4), ("bj", "cotton", 4), ("gw", "cashew", 4), ("gm", "groundnut", 12),
)
#: The two euro parities, which are constants and not fixings.
XOF_PER_EUR = 655.957
CVE_PER_EUR = 110.265
#: The dated boundaries this pack's eras turn on.
COUP_DATE = date(2023, 7, 26)
SANCTIONS_START = date(2023, 7, 30)
SANCTIONS_LIFTED = date(2024, 2, 24)
ECOWAS_EXIT_ANNOUNCED = date(2024, 1, 28)
ECOWAS_EXIT_EFFECTIVE = date(2025, 1, 29)
FIRST_CRUDE_EXPORT = date(2024, 5, 15)
LEONE_REDENOMINATION = date(2022, 7, 1)


def niger_bloc_state(day: date) -> str:
    """Which side of the ECOWAS rupture a day sits on. Four states, five citable dates."""
    if day < SANCTIONS_START:
        return "PRE_SANCTIONS"
    if day < SANCTIONS_LIFTED:
        return "SANCTIONED"
    if day < ECOWAS_EXIT_EFFECTIVE:
        return "LIFTED_WITHDRAWAL_ANNOUNCED"
    return "WITHDRAWN_AES"


def uranium_regime(day: date) -> str:
    """The Nigerien uranium ownership regime on a day. OWNERSHIP, not deliveries -- the two are
    different series and SC-A tests the second, not the first."""
    if day < COUP_DATE:
        return "OPERATOR_RUN"
    if day < date(2024, 6, 20):
        return "POST_COUP_UNCHANGED"
    if day < date(2024, 12, 4):
        return "IMOURAREN_PERMIT_WITHDRAWN"
    if day < date(2025, 6, 19):
        return "SOMAIR_CONTROL_LOST"
    return "SOMAIR_NATIONALISED"


def pipeline_state(day: date) -> str:
    """The Agadem-Seme line's state on a day: a 90,000 b/d supply line with a POLITICAL on/off
    switch, which is rare enough to be a domain of its own."""
    if day < FIRST_CRUDE_EXPORT:
        return "PRE_FIRST_EXPORT"
    if day < date(2024, 6, 6):
        return "FLOWING"
    if day < date(2024, 7, 1):
        return "INTERRUPTED"
    return "RESUMED"


def leone_scale(day: date) -> float:
    """The multiplier that converts a leone figure to POST-redenomination units. 1000.0 before
    2022-07-01 and 1.0 after it. ANY pooled leone series that omits this is measuring a 1000x
    step as a price move."""
    return 1000.0 if day < LEONE_REDENOMINATION else 1.0


def fx_regime(code: str) -> str:
    """The exchange-rate regime of one jurisdiction. THREE regimes in eight countries is the
    natural experiment SC-U is built on, and `lr` is deliberately its own case."""
    key = str(code).lower()
    if CURRENCIES.get(key) == "XOF":
        return "EURO_PEG_XOF"
    if key == "cv":
        return "EURO_PEG_CVE"
    if key == "lr":
        return "FLOAT_DOLLARISED"
    return "FLOAT"


def eur_parity(code: str) -> float:
    """The fixed parity to the euro, or 0.0 for a floater. A CONSTANT, not a fixing."""
    regime = fx_regime(code)
    if regime == "EURO_PEG_XOF":
        return XOF_PER_EUR
    if regime == "EURO_PEG_CVE":
        return CVE_PER_EUR
    return 0.0


def sahel_season(day: date) -> str:
    """The shared agronomic clock of the whole pack. HARMATTAN (November-February), HOT_DRY
    (March-May), RAINY/hivernage (June-September) and HARVEST (October). The SOUDURE -- the lean
    season -- sits inside the rains, which is the part a temperate intuition gets backwards."""
    month = day.month
    if month in (11, 12, 1, 2):
        return "HARMATTAN"
    if month in (3, 4, 5):
        return "HOT_DRY"
    if month in (6, 7, 8, 9):
        return "RAINY_SOUDURE"
    return "HARVEST"


def cotton_campaign_phase(day: date) -> str:
    """The Beninese and Togolese cotton campaign phase. SOWING (May-July), GROWING
    (August-September), HARVEST (October-December) and GINNING (January-April). The price notice
    lands BEFORE sowing, which is the whole mechanism."""
    month = day.month
    if month in (5, 6, 7):
        return "SOWING"
    if month in (8, 9):
        return "GROWING"
    if month in (10, 11, 12):
        return "HARVEST"
    return "GINNING"


def cashew_campaign_phase(day: date) -> str:
    """The Guinea-Bissau cashew campaign. The decree normally opens it in April; buying runs to
    about August and the rest of the year is CLOSED. One campaign sets a whole country's terms of
    trade."""
    month = day.month
    if month in (4, 5):
        return "OPENING"
    if month in (6, 7, 8):
        return "BUYING"
    return "CLOSED"


def days_to_tabaski(day: date) -> int:
    """Days from `day` to the next Aid el-Kebir in the declared table, or -1 when the table does
    not reach that far. THE ISLAMIC CALENDAR IS AN ECONOMIC CALENDAR in Niger and The Gambia:
    Tabaski is the largest household-spending event of the year and it drifts about eleven days
    earlier each solar year, which is free identification."""
    feasts = sorted(d for rows in LUNAR_HOLIDAYS.values() for d, name, _st in rows
                    if "Aid el-Kebir" in name)
    for feast in feasts:
        if feast >= day:
            return (feast - day).days
    return -1


def jurisdiction_of_domain(domain_id: str) -> tuple[str, ...]:
    """Which of the eight a domain belongs to. A regional domain names all eight."""
    return DOMAIN_JURISDICTION.get(str(domain_id), JURISDICTIONS)


def cells() -> tuple[dict[str, Any], ...]:
    """THE TESTABLE CELLS THIS PACK MINTS: every domain crossed with its OWN instruments and its
    OWN named conditions, and nothing else.

    Deliberately NOT a cartesian product of every domain against every executable instrument. A
    cell is worth a trial only if this pack's own data plane can evaluate its CONDITION on that
    SYMBOL, so the cross product is taken INSIDE each domain. A blown-up grid spends the
    program's shared family-wise error budget on cells nobody can fill, and every FX and metals
    cell on the desk pays for it (two-lane order, 2026-09-06).
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
    """Hand rows to the department Ctx when one is given, and count what was taken. `mine()` must
    work with NO context at all -- that is how a test calls it and how a fresh session checks the
    pack with nothing wired -- so an absent ctx is a normal return and never an error."""
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


def mine_uranium_permits(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """SC-A: the Nigerien permit actions as dated events, routed through European power."""
    rows = [{"kind": "hypothesis", "pack": CODE, "domain": "SC-A", "jurisdiction": "ne",
             "at": day.isoformat(), "what": what, "status": status,
             "regime": uranium_regime(day), "bloc_state": niger_bloc_state(day),
             "symbols": ["XNGUSD", "FRA40", "EUSTX50", "GER40"], "family": "supply_shock",
             "horizon": "1 to 4 quarters",
             "control": "Kazakh and Canadian supply events in the same years; matched non-event "
                        "days on the European power and gas complex"}
            for day, what, status in URANIUM_EVENTS]
    return {"miner": "sc_uranium_permits", "code": CODE, "at": _now(), "rows": rows,
            "emitted": _emit(ctx, rows),
            "unmeasured": ["the uranium spot assessment is LICENSED and forbids machine "
                           "extraction, so the benchmark this mechanism should be measured "
                           "against is UNMEASURED and the routing through power is stated weak"]}


def mine_pipeline_switch(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """SC-B and SC-K: a 90,000 b/d line with a political on/off switch."""
    rows = [{"kind": "hypothesis", "pack": CODE, "domain": "SC-B", "jurisdiction": "ne",
             "at": day.isoformat(), "what": what, "status": status,
             "phase": pipeline_state(day), "symbols": ["XBRUSD", "XTIUSD"],
             "family": "capacity_ramp", "horizon": "0 to 10 sessions",
             "control": "matched non-event days; Chinese import volumes from Niger in the "
                        "following quarter, which separate a negotiation from a supply loss"}
            for day, what, status in PIPELINE_EVENTS]
    return {"miner": "sc_pipeline_switch", "code": CODE, "at": _now(), "rows": rows,
            "emitted": _emit(ctx, rows),
            "unmeasured": ["one of the four milestones is PROJECTED; a projected date may not "
                           "arrive at all and no cell is promoted on one"]}


def mine_bloc_rupture(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """SC-C and SC-H: three dated communiques against two corridor series and a weekly auction."""
    rows = [{"kind": "hypothesis", "pack": CODE, "domain": "SC-C", "jurisdiction": "ne",
             "at": day.isoformat(), "what": what, "status": status,
             "bloc_state": niger_bloc_state(day), "season": sahel_season(day),
             "symbols": ["CORN", "WHEAT", "SUGAR", "XBRUSD"], "family": "sanctions_regime",
             "horizon": "2 to 12 weeks", "needs_sibling_pack": "west_africa",
             "control": "Burkina's and Mali's corridors over the same months; the Benin auction "
                        "cut-off as the regional rate control"}
            for day, what, status in ECOWAS_EVENTS]
    return {"miner": "sc_bloc_rupture", "code": CODE, "at": _now(), "rows": rows,
            "emitted": _emit(ctx, rows),
            "unmeasured": ["Mali's and Burkina's corridor series belong to `west_africa`; "
                           "without that pack's ground the AES control is UNMEASURED"]}


def mine_registry_tonnage(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """SC-E: the flag state's own census as a tanker-capacity reading, WITH the zero-sum control."""
    rows = [{"kind": "hypothesis", "pack": CODE, "domain": "SC-E", "jurisdiction": "lr",
             "at": _now(),
             "what": "a quarter in which Liberian-flag tanker deadweight grew faster than world "
                     "fleet deadweight, or in which arriving tonnage was older than the fleet "
                     "median -- the published footprint of grey-fleet formation",
             "symbols": ["XBRUSD", "XTIUSD", "UK100"], "family": "capacity",
             "horizon": "1 to 4 quarters",
             "control": "Panama's and the Marshall Islands' tonnage over the same quarters, "
                        "because re-flagging is ZERO SUM between open registers"}]
    return {"miner": "sc_registry_tonnage", "code": CODE, "at": _now(), "rows": rows,
            "emitted": _emit(ctx, rows),
            "unmeasured": ["the registry page OVERWRITES and keeps no history, so any quarter "
                           "the archive layer did not crawl is UNMEASURED and never interpolated"]}


def mine_campaign_prices(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """SC-I, SC-M and SC-R: three administered prices announced before the world price is known,
    each one the others' natural placebo."""
    rows: list[dict[str, Any]] = []
    for juris, crop, month in CAMPAIGN_EVENTS:
        domain = {"cotton": "SC-I" if juris == "tg" else "SC-M",
                  "cashew": "SC-R", "groundnut": "SC-Q"}[crop]
        rows.append({
            "kind": "hypothesis", "pack": CODE, "domain": domain, "jurisdiction": juris,
            "at": _now(),
            "what": f"the {juris.upper()} {crop} campaign price notice, normally announced in "
                    f"month {month}, against the previous year's world price",
            "symbols": ["COTTON"] if crop == "cotton" else ["WHEAT", "CORN", "SOYBEAN"],
            "family": "administered_price", "horizon": "1 to 3 quarters",
            "phase": cotton_campaign_phase(date(2025, month, 1)) if crop == "cotton"
                     else cashew_campaign_phase(date(2025, month, 1)),
            "control": "the neighbouring country's announcement in the same campaign, which is "
                       "the same mechanism under a different border condition"})
    return {"miner": "sc_campaign_prices", "code": CODE, "at": _now(), "rows": rows,
            "emitted": _emit(ctx, rows),
            "unmeasured": ["the campaign notices are reported by the press with an arrete "
                           "number; until the gazette is fetched the exact DATE is "
                           "PRESS_REPORTED and no cell is promoted on it"]}


def mine_redenomination_boundary(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """SC-O and SC-U: the 1000:1 unit change of 2022-07-01 and the ratio that must survive it."""
    rows = [{"kind": "hypothesis", "pack": CODE, "domain": "SC-O", "jurisdiction": "sl",
             "at": LEONE_REDENOMINATION.isoformat(),
             "what": "a 1000:1 redenomination that is a UNIT change and not a price move; the "
                     "auction-minus-bureau SPREAD is a ratio and must be continuous across it",
             "scale_before": leone_scale(LEONE_REDENOMINATION - timedelta(days=1)),
             "scale_after": leone_scale(LEONE_REDENOMINATION),
             "symbols": ["XAUUSD", "XZNUSD", "USDZAR"], "family": "regime_break",
             "horizon": "1 to 2 quarters",
             "control": "THE RATIO ITSELF as the invariance test; The Gambia's and Liberia's "
                        "floats over the same months"},
            {"kind": "hypothesis", "pack": CODE, "domain": "SC-U", "jurisdiction": "regional",
             "at": _now(),
             "what": "three regimes in eight jurisdictions: two hard euro pegs with DIFFERENT "
                     "guarantors, one dollarised float and two clean floats",
             "regimes": {code: fx_regime(code) for code in JURISDICTIONS},
             "parities": {code: eur_parity(code) for code in JURISDICTIONS},
             "symbols": ["EURUSD", "USDZAR", "XAUUSD"], "family": "peg_regime",
             "horizon": "1 to 4 quarters",
             "control": "Cabo Verde against WAEMU holds the anchor and varies the GUARANTOR; "
                        "Liberia against Sierra Leone and The Gambia holds the float and varies "
                        "DOLLARISATION"}]
    return {"miner": "sc_redenomination_boundary", "code": CODE, "at": _now(), "rows": rows,
            "emitted": _emit(ctx, rows),
            "unmeasured": ["no national reserve or BoP series exists for NE, TG, BJ or GW "
                           "because WAEMU reserves are POOLED; that half of SC-U is UNMEASURED "
                           "by construction and the IMF Article IV is the named substitute"]}


def mine_calendar_plane(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """SC-W and SC-Q: eight calendars, two Christian traditions and five sighting authorities."""
    rows: list[dict[str, Any]] = []
    for year in HOLIDAYS_RULE["years"]:
        for day in sorted(market_holidays(year)):
            closed = closures_on(day)
            if not closed:
                continue
            rows.append({"kind": "hypothesis", "pack": CODE, "domain": "SC-W",
                         "at": day.isoformat(), "closed": closed,
                         "regional": len(closed) == len(JURISDICTIONS),
                         "days_to_tabaski": days_to_tabaski(day),
                         "symbols": ["XAUUSD", "COTTON", "EURUSD"],
                         "family": "holiday_liquidity", "horizon": "0 to 2 sessions",
                         "control": "the matched weekday twenty-six weeks away; days on which "
                                    "exactly ONE of the eight closed"})
    return {"miner": "sc_calendar_plane", "code": CODE, "at": _now(), "rows": rows,
            "emitted": _emit(ctx, rows),
            "unmeasured": ["every Islamic row for 2026 is PROJECTED, five authorities announce "
                           "independently, and West African sighting routinely runs a day later "
                           "than the Gulf -- so a projected date is a projection twice over"]}


def mine_transmission_seeds(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """The pack's own transmission map, as HYPOTHESIS discoveries the registry deduplicates."""
    rows = [{"kind": "hypothesis", "pack": CODE, "domain": "transmission", "at": _now(),
             "edge": str(seed["id"]), "what": str(seed["mechanism"]),
             "symbols": list(seed["targets"]), "family": "transfer",
             "horizon": str(seed["horizon"]), "evidence": str(seed["evidence"]),
             "control": str(seed["control"]), "falsifier": str(seed["falsifier"])}
            for seed in TRANSMISSION_EDGES_SEED]
    return {"miner": "sc_transmission_seeds", "code": CODE, "at": _now(), "rows": rows,
            "emitted": _emit(ctx, rows), "unmeasured": []}


MINERS: dict[str, Any] = {
    "mine_uranium_permits": mine_uranium_permits,
    "mine_pipeline_switch": mine_pipeline_switch,
    "mine_bloc_rupture": mine_bloc_rupture,
    "mine_registry_tonnage": mine_registry_tonnage,
    "mine_campaign_prices": mine_campaign_prices,
    "mine_redenomination_boundary": mine_redenomination_boundary,
    "mine_calendar_plane": mine_calendar_plane,
    "mine_transmission_seeds": mine_transmission_seeds,
}


def mine(ctx: Any = None) -> dict[str, Any]:
    """THE DEPARTMENT ENTRY. Pure Python, no network, no LLM and no heavy import.

    It runs the pack's own eight miners over the pack's own tables, emits through the department
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
            "jurisdiction_layer_gaps": JURISDICTION_LAYER_GAPS,
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
        "jurisdiction_layer_gaps": JURISDICTION_LAYER_GAPS,
        "layer_terms": layer_terms(), "source_layer_coverage": source_layer_coverage(),
        "datasets": DATASETS, "actors": ACTORS, "domains": DOMAINS,
        "custom_miners": CUSTOM_MINERS, "miner_domains": MINER_DOMAINS,
        "transmission_edges_seed": TRANSMISSION_EDGES_SEED, "policy_eras": POLICY_ERAS,
        "transmission_targets": TRANSMISSION_TARGETS, "access_constraints": ACCESS_CONSTRAINTS,
        "interactions": INTERACTIONS, "cells": CELLS,
        "region_desk": REGION_DESK, "forest": FOREST, "cot_currency": COT_CURRENCY,
        "export_economy": EXPORT_ECONOMY, "retail_leverage_regime": RETAIL_LEVERAGE_REGIME,
        "institutional_flow_sources": INSTITUTIONAL_FLOW_SOURCES, "series": SERIES,
        "mission": MISSION, "uranium_events": URANIUM_EVENTS,
        "pipeline_events": PIPELINE_EVENTS, "ecowas_events": ECOWAS_EVENTS,
        "sighting_authorities": SIGHTING_AUTHORITIES,
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
    """The framework's HolidayRule shape: every closed weekday the eight calendars produce."""
    dates = sorted({d.isoformat() for y in HOLIDAYS_RULE["years"] for d in market_holidays(y)})
    fixed = sorted({f"{m:02d}-{d:02d}"
                    for rows in (FIXED_NE, FIXED_TG, FIXED_BJ, FIXED_SL, FIXED_LR, FIXED_GM,
                                 FIXED_GW, FIXED_CV)
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
