"""CENTRAL AMERICA: the world's only maritime chokepoint whose operator publishes its constraint.

WHY SIX COUNTRIES ARE ONE PACK AND NOT SIX PARAGRAPHS. Panama, Guatemala, Honduras, Costa Rica,
Nicaragua and El Salvador share one isthmus, one trade structure, one harvest calendar, one
drought and one migration corridor -- and they run FOUR DIFFERENT MONETARY REGIMES on top of it.
Splitting them into six packs would split every mechanism in this file down the middle and would
charge the desk's shared trial budget six times for one question. Holding them together is what
turns the differences BETWEEN them into controls.

THE FIVE THINGS THAT BELONG TO THIS ISTHMUS AND TO NO OTHER GROUND IN THE DESK'S BOOK:

  1. THE PANAMA CANAL IS ONE OF THE THREE GREAT MARITIME CHOKEPOINTS AND THE ONLY ONE WHOSE
     OPERATOR PUBLISHES ITS OWN CONSTRAINT DAILY. The Autoridad del Canal de Panama publishes
     booking slots by segment, transits per day, the MAXIMUM AUTHORISED DRAFT, its auction
     results and the level of Gatun Lake -- dated, daily, in advisories to shipping. In 2023-2024
     the Gatun drought cut bookable transits from about 36 a day to about 22 and drove a single
     slot at auction to nearly four million dollars. That is a measurable PHYSICAL constraint on
     world trade, published by the constraining party, against liquid contracts: US Gulf grain to
     Asia (CORN, WHEAT, SOYBEAN), LPG and refined product (XNGUSD, XTIUSD, XBRUSD) and container
     freight into US retail. Suez and Bab el-Mandeb are its explicit CONTROL: when one chokepoint
     closes the other's traffic is the counterfactual, and 2023-2024 obliged the desk by closing
     both at once for different reasons.

  2. THIS IS THE WORLD'S HIGH-GRADE WASHED-ARABICA BELT AND EVERY COUNTRY IN IT COUNTS ITS OWN
     BAGS. Guatemala, Honduras, Nicaragua, Costa Rica and El Salvador each publish MONTHLY export
     volumes through a national coffee institute -- ANACAFE, IHCAFE, CONACAFE, ICAFE and the
     Consejo Salvadoreno del Cafe -- on a harvest calendar that runs October to September. The
     broker quotes COFARA with COFROB beside it as the robusta control. Coffee leaf rust (la
     roya) and the Brazilian frost and drought shocks make this a genuine TWO-ORIGIN
     SUBSTITUTION mechanism against the `br` pack rather than a narrative about weather.

  3. DOLLARISATION AS A CONTROLLED EXPERIMENT. Panama has used the US dollar since 1904 and has
     NO CENTRAL BANK AT ALL. El Salvador dollarised on 2001-01-01 and its central bank kept its
     building and lost its instrument. Guatemala runs a managed float with a published
     participation rule, Costa Rica floats through MONEX, Honduras runs a band with a published
     auction, and Nicaragua crawled at a published rate that was cut to zero in 2024. Six
     neighbours, one trade structure, four monetary regimes: the cleanest natural experiment
     available anywhere on what a monetary regime actually does to a small open economy, and
     every input to it is published.

  4. REMITTANCES ARE A FIFTH TO A QUARTER OF GDP IN FOUR OF THE SIX and every one of those
     central banks publishes them MONTHLY. That is a high-frequency, published, US-labour-market
     linked flow series with a dated policy variable on the sending end: US immigration
     enforcement changes are administrative acts with dates on them.

  5. EL SALVADOR'S 2021 BITCOIN LAW AND ITS 2023-2024 EUROBOND RALLY are a dated sovereign-credit
     sequence. THE MANDATE BOUNDARY IS STATED IN `ACCESS_CONSTRAINTS` AND HELD HERE: this is a
     SOVEREIGN POLICY and fiscal observable routed into the broker's own BTCUSD CFD and into the
     country's credit story. No crypto-exchange universe is hunted, no venue order book or
     exchange feed is named as a source, and no exchange-native ground is touched.

WHAT ELSE THIS PACK CARRIES. Cobre Panama -- about 1.5% of world copper -- was ORDERED CLOSED by
the Panamanian Supreme Court in November 2023 after nationwide protests, which is a dated,
published, JUDICIAL shutdown of a top-twenty mine against XCUUSD, with its 2025 restart
negotiations published too. Panama is the world's largest flag state and a dollar banking centre.
Guatemala is a top-five sugar exporter and Honduras and Guatemala are large banana chains.
Costa Rica runs a medical-device and semiconductor nearshoring cluster and completed an unusually
successful 2018-2024 fiscal consolidation. Nicaragua granted and then repealed an interoceanic
canal concession and exports gold. CAFTA-DR is the trade frame over all of it, and the dry
corridor drought is a published agricultural-risk series across four of the six.

WHAT IS EXECUTABLE AND WHAT IS NOT. PAB AND SVC ARE THE UNITED STATES DOLLAR -- the balboa is
pegged one to one and circulates as US banknotes, and the colon was withdrawn from circulation in
2001 -- so they are labelled as the dollar and never as proxies for it. GTQ, HNL, CRC and NIO are
ABSENT from the broker and each is named in `TRANSMISSION_TARGETS` with its regime and its route.
Container freight, canal slots and LPG are not broker symbols either; each is routed with its
control named.

NATIVE GROUND: SPANISH FOR ALL SIX, PLUS THE MAYAN LANGUAGES OF GUATEMALA'S HIGHLANDS. K'iche',
Q'eqchi' and Kaqchikel are the languages of the departments where the coffee actually grows and
where the land-and-labour disputes that interrupt a harvest are argued and reported. A
Spanish-only crawl of Guatemala reads the capital and misses the altiplano, which is where the
supply is.

WHAT THIS PACK DOES NOT DUPLICATE. `mx`, `br`, `cl`, `co`, `ar`, `pe`, `bo` and `atlantic_energy`
are siblings on the same forest and each is written around a domestic policy object none of these
six has. `INTERACTIONS` names `mx` and `us` first and explicitly, because the maquila, remittance
and nearshoring chains run straight into both.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Any

# --------------------------------------------------------------------------- identity
CODE = "central_america"
NAME = "Central America and the Panama Canal"
REGION_COMMAND = "latam"
REGION_DESK = "CENTRAL_AMERICA"
FOREST = "latam"
#: The pack's nominal currency. PAB IS THE UNITED STATES DOLLAR: pegged one to one since the 1904
#: Convenio Monetario, with no balboa banknote in existence and US notes in every till. All six
#: currencies are declared in `CURRENCIES` and not one of them is a broker symbol.
CURRENCY = "PAB"
#: THE PARITY FENCE COUNTS THIS TUPLE (`scripts/check_regional_parity.py::jurisdictions_of`).
#: Six countries on the desk's own latam roster that no sibling pack answers for.
JURISDICTIONS: tuple[str, ...] = ("pa", "gt", "hn", "cr", "ni", "sv")
#: WHAT EACH JURISDICTION'S MONEY ACTUALLY IS, AND WHO DECIDES IT. Two of the six ARE the dollar
#: and the other four run four different regimes -- which is the natural experiment this pack
#: exists to run. `broker_quoted` is False on every row: none of the six is in the registry.
CURRENCIES: dict[str, dict[str, Any]] = {
    "pa": {"code": "PAB", "name": "balboa", "regime": "THE US DOLLAR",
           "authority": "NONE. Panama has no central bank and no monetary authority at all",
           "fact": "the balboa is pegged 1:1 to the dollar by the 1904 Convenio Monetario and "
                   "exists only as COINAGE -- there is no balboa banknote and the circulating "
                   "paper money of Panama is the United States dollar. Panama therefore imports "
                   "the Federal Reserve's policy rate with no transmission mechanism, no "
                   "sterilisation and no lender of last resort. This is NOT a peg that can "
                   "break; it is the dollar with a local name on the coins",
           "broker_quoted": False,
           "status": "STRUCTURAL: the 1:1 parity is a statutory fact, not a market observable"},
    "sv": {"code": "SVC", "name": "colon (withdrawn)", "regime": "THE US DOLLAR",
           "authority": "Banco Central de Reserva de El Salvador -- WITH NO MONETARY INSTRUMENT",
           "fact": "the Ley de Integracion Monetaria fixed the colon at 8.75 per dollar and made "
                   "the dollar legal tender from 2001-01-01; the colon was withdrawn from "
                   "circulation and El Salvador has had no domestic monetary policy since. The "
                   "BCR still supervises, still publishes and cannot set a rate. The 2021 "
                   "Bitcoin Law added a second legal tender and the 2025 amendment removed that "
                   "status again, leaving the dollar where it was",
           "broker_quoted": False,
           "status": "STRUCTURAL since 2001-01-01; the colon is a historical unit of account"},
    "gt": {"code": "GTQ", "name": "quetzal", "regime": "managed float with a published rule",
           "authority": "Banco de Guatemala and its Junta Monetaria",
           "fact": "Banguat operates a PUBLISHED, RULE-BASED participation mechanism: it buys or "
                   "sells when the daily reference rate deviates from a moving average by more "
                   "than a stated margin, in stated amounts. The rule is the observable, and it "
                   "makes Guatemalan FX intervention a computable reaction function rather than "
                   "a discretionary one -- the opposite of the Peruvian case and its control",
           "broker_quoted": False,
           "status": "the rule's exact margin and amounts are revised by JM resolution; "
                     "PRESS_REPORTED until the resolution is read"},
    "hn": {"code": "HNL", "name": "lempira", "regime": "crawling band with a published auction",
           "authority": "Banco Central de Honduras",
           "fact": "the BCH allocates foreign exchange through a daily auction (subasta) with a "
                   "base price and a permitted deviation band; the band has been widened, frozen "
                   "and re-opened on dated resolutions, and the queue at the auction is the real "
                   "observable rather than the posted rate",
           "broker_quoted": False,
           "status": "PRESS_REPORTED band parameters; confirm against the BCH resolutions"},
    "cr": {"code": "CRC", "name": "colon costarricense", "regime": "managed float through MONEX",
           "authority": "Banco Central de Costa Rica",
           "fact": "Costa Rica left its crawling band in 2015 and floats through MONEX, the "
                   "wholesale FX market the BCCR both operates and participates in; the BCCR "
                   "publishes the MONEX rate daily and its own participation separately, and it "
                   "runs a genuine inflation-targeting policy rate (the TPM) -- the only fully "
                   "instrumented inflation targeter on this isthmus",
           "broker_quoted": False,
           "status": "STRUCTURAL float since 2015-02; the TPM decisions are published"},
    "ni": {"code": "NIO", "name": "cordoba", "regime": "crawling peg, crawl cut to zero",
           "authority": "Banco Central de Nicaragua",
           "fact": "the cordoba slid against the dollar at a PUBLISHED daily rate for decades -- "
                   "5% a year for most of the modern era -- and the BCN cut that rate in steps "
                   "to 3%, then 2%, and then to ZERO in 2024. A published devaluation rate that "
                   "is administratively set to nothing is a regime break with a date on it, and "
                   "it is the sharpest monetary event in this pack's window",
           "broker_quoted": False,
           "status": "PRESS_REPORTED step sequence; confirm each step against the BCN resolution"},
}
#: MM-DD, five characters, as the framework wants it. All six national budgets run the calendar
#: year -- and the pack's most important fiscal clock DOES NOT, which `FISCAL_YEARS` is for.
FISCAL_YEAR_END = "12-31"
FISCAL_YEARS: dict[str, str] = {
    "pa": "12-31 for the Republic. THE AUTORIDAD DEL CANAL DE PANAMA DOES NOT: the ACP's fiscal "
          "year runs 1 OCTOBER TO 30 SEPTEMBER, and its transit counts, toll revenue and "
          "contribution to the Treasury are reported on that basis. A study that reads ACP "
          "annual figures on a calendar year is off by a quarter on the single most important "
          "series in this pack",
    "gt": "12-31: the Presupuesto General runs the calendar year; the COFFEE year does not, and "
          "runs 1 October to 30 September like every origin in this belt",
    "hn": "12-31 for the budget; the coffee year is 1 October to 30 September",
    "cr": "12-31 since the 2000 reform; the coffee year is 1 October to 30 September",
    "ni": "12-31; the coffee year is 1 October to 30 September",
    "sv": "12-31; the coffee year is 1 October to 30 September",
}
NATIVE_LANGUAGES: tuple[str, ...] = ("es", "quc", "kek", "cak", "en")
COT_CURRENCY = ""                  # no CFTC contract exists for any of the six currencies
EXPORT_ECONOMY = "logistics_and_agricultural_exporter"
RETAIL_LEVERAGE_REGIME = "open"    # no exchange control in the dollarised pair; Panama is a hub
#: The depth this pack CLAIMS, so a test can check the FRAMEWORK'S own measurement against it
#: rather than against a number typed into a report. `regional_parity.pack_depth` computes the
#: real one from the eight capped ratios; this is the floor the pack promises not to fall below.
DECLARED_DEPTH: float = 1.0
MISSION = ("mine the isthmus as ONE physical system with six sovereigns on it: the ACP's daily "
           "draft, transit, slot and auction series as a published constraint on world trade, "
           "with Suez and Bab el-Mandeb named as the substitution control; Gatun Lake's level "
           "and the ENSO clock behind it; the five national coffee institutes' monthly export "
           "counts on the October-September harvest year against COFARA with COFROB as the "
           "control and the Brazilian frost and drought as the two-origin substitution; four "
           "monetary regimes and two dollarised economies as a controlled experiment; the "
           "monthly remittance prints of four countries where they are a fifth to a quarter of "
           "GDP; Cobre Panama's judicial shutdown and its restart; the Guatemalan zafra and the "
           "CAFTA-DR yarn-forward cotton chain; and the dry corridor drought as a published "
           "agricultural-risk series")

#: The instruments this pack may compile a cell against. Every one is in the broker registry and
#: none is a single-name equity. NOT ONE OF THE SIX CURRENCIES IS HERE: two of them ARE the
#: dollar and four are absent, and all six are named in `TRANSMISSION_TARGETS`.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "CORN",                            # US Gulf corn to Asia is a canal cargo, and an import here
    "WHEAT",                           # the other US Gulf grain leg and the region's import bill
    "SOYBEAN",                         # the largest US Gulf-to-Asia canal cargo of them all
    "SUGAR",                           # Guatemala is a top-five raw sugar exporter on a dated zafra
    "COFARA",                          # the belt's own contract: washed arabica
    "COFROB",                          # the robusta control leg: this belt grows almost none of it
    "COTTON",                          # the CAFTA-DR yarn-forward rule makes US cotton the input
    "XCUUSD",                          # Cobre Panama, ~1.5% of world supply, closed by a court
    "XAUUSD",                          # Nicaraguan gold is its largest export; Honduras has it too
    "XBRUSD",                          # the crude leg that routes through the canal or around it
    "XTIUSD",                          # US Gulf refined product to the Pacific coast, via the canal
    "XNGUSD",                          # US LPG and LNG to Asia: the cargo that bids at the auction
    "USDMXN",                          # the nearshoring competitor and the migration corridor
    "USDBRL",                          # the other arabica origin and the regional EM leg
    "USDCNH",                          # the Asia end of every canal cargo and of the ports question
    "US500",                           # the global risk state and the US retail demand leg
    "US30",                            # the industrial leg the maquila chain terminates in
    "BTCUSD",                          # El Salvador's sovereign policy object, routed as a CFD
)

#: WHAT THIS ISTHMUS TRADES THAT THE BROKER DOES NOT QUOTE. Each row names the absent instrument,
#: the venue it lives on, WHY the pack needs it, the regime it runs under and the broker symbols
#: that carry its economics. An absent instrument produces a transmission hypothesis and never a
#: cell that can never be filled (L1.49). THE FIRST TWO ROWS ARE NOT PROXIES FOR THE DOLLAR --
#: THEY ARE THE DOLLAR, and saying so is the difference between a fact and a modelling error.
TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "PAB, the Panamanian balboa -- THE UNITED STATES DOLLAR, not a proxy for it",
     "venue": "none; there is no balboa FX market because there is nothing to exchange",
     "why": "a desk that treats PAB as an EM currency will look for a devaluation risk premium "
            "that cannot exist. The balboa is 1:1 by the 1904 Convenio Monetario, exists only as "
            "coin, and the circulating notes are US dollars. Panama's POLICY RATE IS THE FEDERAL "
            "FUNDS RATE, imported whole, with no central bank to soften it",
     "regime": "statutory parity since 1904; no central bank, no reserves, no lender of last "
               "resort, no sterilisation and no capital control",
     "route": "the US legs carry Panama's monetary state directly -- US500 and US30 for the "
              "risk and demand channel, XAUUSD as the dollar's own negative leg",
     "proxies": ("US500", "US30", "XAUUSD")},
    {"name": "SVC, the Salvadoran colon -- ALSO THE UNITED STATES DOLLAR since 2001-01-01",
     "venue": "none; the colon was withdrawn from circulation",
     "why": "El Salvador fixed at 8.75 and dollarised under the Ley de Integracion Monetaria. "
            "The BCR exists, publishes and supervises, and has NO monetary instrument. Every "
            "Salvadoran cell in this pack is therefore a FISCAL or CREDIT cell, never a "
            "monetary one, and that is the whole reason sv and pa are each other's replicate",
     "regime": "statutory dollarisation from 2001-01-01; the 2021 Bitcoin Law added a second "
               "legal tender and the 2025 amendment removed that status",
     "route": "US500 and US30 for the imported monetary state; BTCUSD for the sovereign policy "
              "object; XAUUSD as the dollar leg",
     "proxies": ("US500", "US30", "BTCUSD", "XAUUSD")},
    {"name": "USD/GTQ, the Guatemalan quetzal and Banguat's published participation rule",
     "venue": "the Guatemalan interbank market; Banguat publishes the daily reference",
     "why": "the rule is the asset. Banguat states the deviation from a moving average that "
            "triggers its participation and the amount it will transact, which makes this the "
            "one FX reaction function on the isthmus that can be computed rather than inferred. "
            "GTQ is not in the broker registry, so the rule is a CONDITIONER and never a cell",
     "regime": "managed float with a published, rule-based participation mechanism revised by "
               "Junta Monetaria resolution",
     "route": "USDMXN and USDBRL carry the regional EM state; COFARA and SUGAR carry the terms "
              "of trade that actually move the quetzal",
     "proxies": ("USDMXN", "USDBRL", "COFARA", "SUGAR")},
    {"name": "USD/HNL, the Honduran lempira and the BCH allocation auction",
     "venue": "the BCH daily subasta and the authorised dealers",
     "why": "the lempira is allocated rather than cleared: the BCH auctions dollars within a "
            "band, so a shortage shows up as a QUEUE and an informal premium rather than as a "
            "rate move. The queue is the observable and it is not in the posted series",
     "regime": "crawling band with a base price and a permitted deviation, frozen and re-opened "
               "on dated resolutions",
     "route": "USDMXN as the regional leg; COFARA for the coffee terms of trade; COTTON and "
              "US30 for the maquila chain that earns the dollars",
     "proxies": ("USDMXN", "COFARA", "COTTON", "US30")},
    {"name": "USD/CRC, the Costa Rican colon and the MONEX wholesale market",
     "venue": "MONEX, operated by the BCCR, with the BCCR itself a participant",
     "why": "the only genuine inflation targeter on the isthmus, with a published policy rate "
            "(the TPM) and a published daily MONEX rate and volume. It is the CONTROL for every "
            "dollarised claim in this pack: same isthmus, same coffee, same drought, own money",
     "regime": "managed float since 2015-02 after the crawling band was abandoned; inflation "
               "targeting with a published TPM and BCCR participation disclosed separately",
     "route": "USDMXN and USDBRL for the EM state; US500 for the nearshoring demand leg",
     "proxies": ("USDMXN", "USDBRL", "US500")},
    {"name": "USD/NIO, the Nicaraguan cordoba and the deslizamiento cut to zero",
     "venue": "the BCN's published daily table of official rates",
     "why": "the crawl was a PUBLISHED NUMBER, set administratively, for decades -- and it was "
            "stepped down to zero in 2024. A regime that is a number in a table and then is not "
            "is the cleanest monetary break in this pack, and it happened in the country whose "
            "statistics are hardest to read, which is why it is worth the effort",
     "regime": "crawling peg at a published daily rate, stepped 5% -> 3% -> 2% -> 0%",
     "route": "XAUUSD carries the country's largest export; USDMXN carries the regional state; "
              "SUGAR and COFARA carry the rest of the export basket",
     "proxies": ("XAUUSD", "USDMXN", "SUGAR", "COFARA")},
    {"name": "The ACP transit booking slot and its auction clearing price",
     "venue": "the Autoridad del Canal de Panama transit reservation system",
     "why": "THE SINGLE MOST VALUABLE ABSENT INSTRUMENT IN THIS PACK. The ACP auctions unbooked "
            "slots and the clearing price is reported; in late 2023 one Neopanamax slot cleared "
            "near four million dollars. It is a priced option on a physical constraint and no "
            "broker quotes it, so it is a CONDITION on the cargoes that bid for it",
     "regime": "administered booking by segment with a periodic auction of released slots; the "
               "number of slots is set by the ACP and published in advisories to shipping",
     "route": "XNGUSD for the LPG and LNG carriers that bid highest, XTIUSD and XBRUSD for the "
              "product and crude legs, CORN and SOYBEAN for the US Gulf grain that pays freight",
     "proxies": ("XNGUSD", "XTIUSD", "XBRUSD", "CORN", "SOYBEAN")},
    {"name": "Container freight rate indices (Shanghai-to-US-East-Coast and Panama surcharges)",
     "venue": "commercial price-reporting agencies and the liner tariffs",
     "why": "the canal constraint reaches the US consumer through the box rate and the Panama "
            "Canal surcharge, and the indices that measure it are LICENSED and forbid machine "
            "extraction. Registered here, never scraped, and never omitted either",
     "regime": "assessed weekly, subscription-only, terms forbid machine extraction",
     "route": "US500 and US30 carry the retail and industrial demand side; the physical leg is "
              "the ACP's own transit count, which is public",
     "proxies": ("US500", "US30")},
    {"name": "Mont Belvieu propane and US Gulf LPG freight to Asia",
     "venue": "US NGL hubs and the VLGC freight market",
     "why": "the LPG carrier is the vessel class that bid the record canal slot prices, because "
            "a missed loading window costs more than the slot. The NGL price itself is not a "
            "broker symbol and the gas leg that is, is XNGUSD -- a DIFFERENT contract with its "
            "own basis, and this pack says so rather than pretending otherwise",
     "regime": "spot assessments plus term contracts; the freight leg is a private market",
     "route": "XNGUSD with the basis risk stated in full; XTIUSD as the wider energy leg",
     "proxies": ("XNGUSD", "XTIUSD")},
    {"name": "El Salvador USD global bonds and the EMBI spread",
     "venue": "the offshore secondary market",
     "why": "the 2023-2024 rally from distressed levels after the January 2023 maturity was paid "
            "in full is the credit half of the Bitcoin story, and it is not quotable here. The "
            "sovereign spread is the observable that tells a policy stunt from a solvency event",
     "regime": "external USD issuance with buybacks; an IMF programme from 2024-12",
     "route": "BTCUSD carries the policy object, US500 the risk state; the spread is a "
              "CONDITION on both and never a target",
     "proxies": ("BTCUSD", "US500")},
    {"name": "Panama sovereign bonds and the investment-grade boundary",
     "venue": "the offshore secondary market and the rating agencies",
     "why": "Cobre Panama was roughly a twentieth of Panamanian GDP and the court closed it; the "
            "rating consequences are dated agency acts. Panama's credit is the fiscal echo of "
            "the mine cell and is not a broker instrument",
     "regime": "external USD issuance by a fully dollarised sovereign with no printing option",
     "route": "XCUUSD carries the physical mine leg; US500 carries the risk state",
     "proxies": ("XCUUSD", "US500")},
    {"name": "The Central American bourses: BVNSA, BNV Costa Rica, BVES and the BCIE issues",
     "venue": "Bolsa de Valores Nacional (Guatemala), Bolsa Nacional de Valores (Costa Rica), "
              "Bolsa de Valores de El Salvador",
     "why": "these are overwhelmingly REPO AND SHORT-PAPER markets rather than equity markets -- "
            "BVNSA's turnover is mostly government paper -- so there is no index worth quoting "
            "and no equity mechanism to mine. Naming that is the measurement",
     "regime": "fixed-income and repo dominated; no listed derivatives market on the isthmus",
     "route": "nothing is routed: the domestic rate state reaches this pack through the central "
              "banks' own published series, and US500 carries the risk state",
     "proxies": ("US500",)},
    {"name": "Coffee origin differentials (Guatemala SHB, Honduras HG/SHG, Costa Rica SHB)",
     "venue": "price-reporting agencies and the exporters' term contracts",
     "why": "the belt sells at a DIFFERENTIAL to the exchange, and the differential is where "
            "origin-specific supply shows up first. The assessments are licensed and forbid "
            "machine extraction, so the differential is UNMEASURED and the claim is made on the "
            "exchange contract with the robusta leg as its control",
     "regime": "assessed, subscription-only, terms forbid machine extraction",
     "route": "COFARA is the executable leg and COFROB is the control that separates 'arabica' "
              "from 'this belt'",
     "proxies": ("COFARA", "COFROB")},
    {"name": "LME and COMEX copper concentrate terms and the TC/RC benchmark",
     "venue": "the London Metal Exchange and the annual concentrate negotiation",
     "why": "Cobre Panama shipped CONCENTRATE, and the treatment and refining charge is the part "
            "of the price a miner actually receives. Its removal tightened the concentrate "
            "market far more than the refined one, which is a distinction the refined CFD cannot "
            "express and this row exists to record",
     "regime": "an annual negotiated benchmark plus spot assessments",
     "route": "XCUUSD is the executable leg; the TC/RC is a CONDITION on it",
     "proxies": ("XCUUSD",)},
)

# --------------------------------------------------------------------------- the central banks
#: THE PACK'S NOMINAL MONETARY AUTHORITY, and the first thing it has to say is that the pack's
#: NAMESAKE JURISDICTION HAS NONE. `CENTRAL_BANKS` carries all six; this row is the framework's
#: single slot and it is filled with Banco de Guatemala, the largest and most instrumented of the
#: four that actually have an instrument.
CENTRAL_BANK: dict[str, Any] = {
    "name": "Banco de Guatemala (Banguat) -- the pack's reference authority; see CENTRAL_BANKS",
    "framework": "inflation_targeter",
    "policy_instrument": "the tasa de interes lider de politica monetaria, set by the Junta "
                         "Monetaria; and SEPARATELY the PUBLISHED FX PARTICIPATION RULE, under "
                         "which Banguat buys or sells when the daily reference rate deviates "
                         "from a moving average by more than a stated margin -- a second "
                         "instrument, with a stated trigger, that a rate-only study never sees",
    "mandate": "price stability under the Ley Organica del Banco de Guatemala; the Junta "
               "Monetaria is the decision body and its resolutions are published",
    "decision_rule": "the Junta Monetaria decides on a PUBLISHED calendar, roughly every six to "
                     "eight weeks, and the resolution is published the same day; Guatemala is "
                     "UTC-6 all year and observes no daylight saving, so the announcement hour "
                     "does not move between January and July",
    "decision_calendar_rule": "published a year ahead at banguat.gob.gt; this pack refuses to "
                              "invent it and produces a CANDIDATE lattice instead "
                              "(`policy_candidate_days`), which the collector intersects with "
                              "the published calendar before any cell is compiled",
    "decision_dates": (),
    "dates_status": "NOT LISTED, DELIBERATELY (L1.28a). Four of the six jurisdictions have a "
                    "policy rate and each publishes its own calendar; none of the four "
                    "calendars is typed into this pack. The CADENCE is known and the DATES are "
                    "UNMEASURED until the published calendar is joined. A cell compiled on an "
                    "unverified decision date is UNMEASURED, not approximate",
    "decision_time_utc": "20:00",
    "announce_local": "14:00 America/Guatemala on the decision day, with the resolution text; "
                      "the BCCR's TPM decision and the BCH's and BCN's own announcements each "
                      "have their own hour and are carried in CENTRAL_BANKS",
    "dst_rule": "NONE ANYWHERE ON THE ISTHMUS. Guatemala, Honduras, El Salvador, Nicaragua and "
                "Costa Rica are UTC-6 all year and Panama is UTC-5 all year, and not one of the "
                "six observes daylight saving. Every UTC window in this pack is the same minute "
                "in January and in July -- which is rare and worth using",
    "minutes_lag_days": 0,
    "publication_classes": ("resolucion_junta_monetaria", "informe_de_politica_monetaria",
                            "tipo_de_cambio_de_referencia_diario", "regla_de_participacion",
                            "remesas_familiares_mensuales", "comercio_exterior_mensual",
                            "indice_mensual_de_actividad_economica"),
    "policy_rate_series": "BANGUAT:tasa_lider",
    "expected_rate_series": "UNMEASURED",
    "consensus_proxy": "the Banguat Encuesta de Expectativas Economicas al Panel de Analistas "
                       "Privados, published monthly, plus the regional bank research that the "
                       "practitioner layer carries",
    "consensus_proxy_trap": "the panel is surveyed for the MONTH and not for the meeting, and "
                            "its cut-off precedes the resolution by weeks; used as a meeting-day "
                            "consensus it manufactures surprises that nobody was surprised by",
    "reserves_clock": "Banguat, BCH, BCCR and BCN each publish reserves weekly or monthly. "
                      "PANAMA PUBLISHES NONE AND HAS NONE TO PUBLISH: there is no monetary "
                      "authority, so there is no reserve series, and the lawful substitute is "
                      "the Superintendencia de Bancos' banking-system liquidity statistics",
    "programme": "the region's IMF relationship is the real policy clock for three of the six: "
                 "El Salvador signed a 2024-12 Extended Fund Facility, Costa Rica completed an "
                 "EFF and an RSF, and Honduras has run successive arrangements. Panama's clock "
                 "is the FOMC's, imported whole",
    "off_cycle": ("Banguat's FX participation is triggered by its own published rule and "
                  "happens BETWEEN meetings, which is where most of the monetary information on "
                  "this isthmus actually is",
                  "the BCN's deslizamiento steps were administrative acts taken outside any "
                  "rate-setting meeting and changed the regime without changing a policy rate"),
    "root": "https://www.banguat.gob.gt",
}

#: ALL SIX, INCLUDING THE ONE THAT DOES NOT EXIST. The `pa` row is the pack's most important
#: single declaration: an absence that is a FACT ABOUT THE COUNTRY rather than a hole in the
#: data, with the lawful substitute named beside it.
CENTRAL_BANKS: dict[str, dict[str, Any]] = {
    "pa": {"name": "NONE -- PANAMA HAS NO CENTRAL BANK", "exists": False,
           "framework": "imported: the Federal Reserve sets Panama's policy rate",
           "instrument": "none. No policy rate, no open-market operations, no reserve "
                         "requirement set by a monetary authority, no FX reserves, no lender of "
                         "last resort. This is not an omission in this pack: it is the defining "
                         "institutional fact of the country and it has held since 1904",
           "substitute": "the Superintendencia de Bancos de Panama publishes the Centro Bancario "
                         "Internacional's balance sheet, liquidity ratio and deposit base "
                         "monthly -- which IS Panama's monetary statistics; the Contraloria "
                         "General (INEC) publishes prices and activity; and the FOMC's own "
                         "decisions are the policy series",
           "root": "https://www.superbancos.gob.pa",
           "status": "STRUCTURAL ABSENCE, declared; see NO_LAWFUL_GROUND"},
    "gt": {"name": "Banco de Guatemala", "exists": True, "framework": "inflation_targeter",
           "instrument": "the tasa lider plus the published FX participation rule",
           "substitute": "", "root": "https://www.banguat.gob.gt",
           "status": "full instrument set; the participation rule is the distinguishing asset"},
    "hn": {"name": "Banco Central de Honduras", "exists": True,
           "framework": "band_with_allocation_auction",
           "instrument": "the TPM plus the daily FX allocation auction inside a published band",
           "substitute": "", "root": "https://www.bch.hn",
           "status": "the auction QUEUE is the real observable and is not in the posted rate"},
    "cr": {"name": "Banco Central de Costa Rica", "exists": True,
           "framework": "inflation_targeter",
           "instrument": "the TPM plus disclosed participation in MONEX",
           "substitute": "", "root": "https://www.bccr.fi.cr",
           "status": "the isthmus's only fully instrumented floater; the control for every "
                     "dollarisation claim in this pack"},
    "ni": {"name": "Banco Central de Nicaragua", "exists": True,
           "framework": "crawling_peg_at_zero_crawl",
           "instrument": "the published daily slide rate (now zero) plus reserve requirements",
           "substitute": "IMF Article IV and mirror customs where the domestic series has "
                         "narrowed; see NO_LAWFUL_GROUND",
           "root": "https://www.bcn.gob.ni",
           "status": "publishes remittances and the FX table monthly; the surrounding "
                     "statistical and press ecology has narrowed and is declared"},
    "sv": {"name": "Banco Central de Reserva de El Salvador", "exists": True,
           "framework": "dollarised: NO MONETARY INSTRUMENT",
           "instrument": "none. The BCR supervises, compiles and publishes. It cannot set a "
                         "rate, cannot intervene and cannot lend of last resort in its own "
                         "money, because it has no own money",
           "substitute": "the FOMC is El Salvador's monetary policy; the fiscal and credit "
                         "series (debt, EMBI, the IMF programme) carry everything else",
           "root": "https://www.bcr.gob.sv",
           "status": "A CENTRAL BANK WITHOUT MONETARY POLICY -- declared in NO_LAWFUL_GROUND as "
                     "an OBJECT absence, because the institution exists and the instrument "
                     "does not"},
}

# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "ACP advisory to shipping: maximum authorised draft and booking slots",
     "local": "issued from Balboa when the constraint changes, and effective on a stated future "
              "date -- which is what makes it a scheduled, anticipable shock",
     "time_utc": "21:00", "time_utc_dst": "21:00",
     "dst_rule": "none: America/Panama is UTC-5 all year",
     "instruments": ("CORN", "SOYBEAN", "WHEAT", "XNGUSD", "XTIUSD"), "window_minutes": 120,
     "why": "THE PACK'S PRIMARY EVENT. The operator of a global chokepoint publishes its own "
            "constraint, in advance, with an effective date. Almost nothing else in commodity "
            "logistics is announced by the constraining party before it binds"},
    {"name": "ACP transit reservation auction result",
     "local": "the auction for released slots clears and the price is reported",
     "time_utc": "20:00", "time_utc_dst": "20:00", "dst_rule": "none: UTC-5 all year",
     "instruments": ("XNGUSD", "XTIUSD", "CORN", "SOYBEAN"), "window_minutes": 120,
     "why": "a priced option on the constraint. When a single slot clears near four million "
            "dollars the market has told the desk what a missed loading window is worth"},
    {"name": "ACP daily Gatun and Alhajuela lake level publication",
     "local": "the level in feet PLD is published each day", "time_utc": "14:00",
     "time_utc_dst": "14:00", "dst_rule": "none: UTC-5 all year",
     "instruments": ("CORN", "SOYBEAN", "XNGUSD"), "window_minutes": 60,
     "why": "the LEADING half of the draft mechanism: the lake falls for months before the "
            "draft is cut, so the level is the forecastable input and the advisory is the event"},
    {"name": "Banguat tipo de cambio de referencia and the participation-rule trigger",
     "local": "published each business day after the interbank session",
     "time_utc": "22:00", "time_utc_dst": "22:00", "dst_rule": "none: UTC-6 all year",
     "instruments": ("USDMXN", "USDBRL", "COFARA"), "window_minutes": 30,
     "why": "the reference that the published participation rule is computed against; the "
            "trigger is arithmetic on a public series, which is what makes it a usable state"},
    {"name": "BCCR MONEX daily weighted rate and volume",
     "local": "published at the close of the MONEX session", "time_utc": "22:00",
     "time_utc_dst": "22:00", "dst_rule": "none: UTC-6 all year",
     "instruments": ("USDMXN", "USDBRL", "US500"), "window_minutes": 30,
     "why": "the isthmus's only market-cleared exchange rate, with the central bank's own "
            "participation published separately -- the control for the administered five"},
    {"name": "BCH subasta de divisas allocation and base price",
     "local": "the daily auction allocates dollars to the authorised dealers",
     "time_utc": "19:00", "time_utc_dst": "19:00", "dst_rule": "none: UTC-6 all year",
     "instruments": ("USDMXN", "COFARA", "COTTON"), "window_minutes": 60,
     "why": "the lempira is allocated, not cleared; the amount offered against the amount bid "
            "is the shortage measure the posted rate hides"},
    {"name": "ICE Coffee C settlement -- the contract this whole belt prices against",
     "local": "the New York afternoon settlement", "time_utc": "18:30", "time_utc_dst": "17:30",
     "dst_rule": "US EST/EDT -- and note that NONE of the six origins changes clock, so the "
                 "origin-to-exchange hour gap moves twice a year while the origins stand still",
     "instruments": ("COFARA", "COFROB"), "window_minutes": 30,
     "why": "every institute's export number is denominated against this settlement, and the "
            "DST asymmetry between a non-DST origin and a DST exchange is a real, dated, "
            "twice-yearly shift in when the origin's news meets the price"},
    {"name": "US Gulf grain export inspections and the Panama routing share",
     "local": "the weekly USDA inspections report", "time_utc": "15:00", "time_utc_dst": "15:00",
     "dst_rule": "published on a fixed US weekday clock",
     "instruments": ("CORN", "SOYBEAN", "WHEAT"), "window_minutes": 60,
     "why": "the physical gate on the other side of the canal cell: a draft restriction should "
            "show up as a US Gulf-to-PNW routing shift before it shows up in a price"},
    {"name": "COMEX and LME copper settlement against the Cobre Panama outage",
     "local": "the London ring and the New York settlement", "time_utc": "18:00",
     "time_utc_dst": "17:00", "dst_rule": "GMT/BST and EST/EDT",
     "instruments": ("XCUUSD",), "window_minutes": 60,
     "why": "the mine was ordered closed by a court on a dated afternoon in Panama City; the "
            "metal repriced in London and New York, not in Panama, and the hour matters"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "ACP fiscal year end, 30 September", "kind": "fiscal_year_end",
     "months": (9,), "roll": "previous", "window_utc": ("14:00", "21:00"),
     "instruments": ("CORN", "SOYBEAN", "XNGUSD"),
     "why": "THE CANAL'S YEAR IS NOT THE REPUBLIC'S. Transit counts, toll revenue and the "
            "Treasury contribution are all reported on an October-September year, and a study "
            "that reads them on a calendar year is a quarter out on the pack's main series"},
    {"name": "Coffee harvest year boundary, 1 October", "kind": "day_of_month",
     "days": (1,), "months": (10,), "roll": "next", "window_utc": ("13:00", "21:00"),
     "instruments": ("COFARA", "COFROB"),
     "why": "all five origins run 1 October to 30 September; the first export month of a new "
            "crop is the month in which an origin's yield finally becomes countable"},
    {"name": "Monthly remittance print, the four high-share economies", "kind": "day_of_month",
     "days": (5, 6, 7, 8, 9, 10), "roll": "next", "window_utc": ("14:00", "22:00"),
     "instruments": ("USDMXN", "US500", "US30"),
     "why": "Banguat, BCH, BCR and BCN each publish the prior month's family remittances early "
            "in the following month; in four of the six this is a fifth to a quarter of GDP"},
    {"name": "Guatemalan zafra boundary, November to May", "kind": "day_of_month",
     "days": (15,), "months": (11, 5), "roll": "next", "window_utc": ("14:00", "21:00"),
     "instruments": ("SUGAR", "CORN"),
     "why": "the cane harvest opens in November and closes in May; the mills' weekly grind is "
            "the physical series and its boundaries are the sampling frame"},
    {"name": "Month-end maquila payroll and the CAFTA-DR shipment cycle", "kind": "month_end",
     "roll": "previous", "window_utc": ("14:00", "21:00"),
     "instruments": ("COTTON", "US30", "USDMXN"),
     "why": "apparel ships to US distribution centres on a month-end cycle and the yarn-forward "
            "rule of origin means the fabric was bought upstream two months earlier"},
    {"name": "Quarter-end BCIE and IMF review calendar", "kind": "quarter_end",
     "roll": "previous", "window_utc": ("14:00", "21:00"),
     "instruments": ("US500", "USDMXN"),
     "why": "three of the six run an IMF arrangement and the regional development bank is a "
            "material creditor to two; a review is a dated fiscal event with a published note"},
    {"name": "Panamanian Treasury transfer from the ACP", "kind": "fiscal_year_end",
     "months": (9,), "roll": "previous", "window_utc": ("14:00", "21:00"),
     "instruments": ("US500", "XCUUSD"),
     "why": "the canal's contribution is a large share of central-government revenue in a "
            "sovereign that cannot print, which is why a transit shortfall is a FISCAL event in "
            "Panama and only a freight event everywhere else"},
)

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "The Panama Canal transit reservation system and the auction",
     "index_symbols": (), "open_local": "00:00", "close_local": "23:59",
     "open_utc": "05:00", "close_utc": "04:59", "dst_rule": "none: UTC-5 all year",
     "auction": "released slots are auctioned by segment and vessel class; the clearing price "
                "is reported and in late 2023 reached nearly four million dollars for one slot",
     "expiry_rule": "a booked slot is a dated transit right with a stated arrival window; a "
                    "missed window forfeits it, which is the whole source of the auction's bid",
     "holidays": "the canal operates 365 days a year and does not close for a feriado; the "
                 "ADMINISTRATIVE offices do, which delays paperwork and not transits",
     "notes": "THE ONLY EXCHANGE-LIKE VENUE ON THIS ISTHMUS THAT MATTERS, and it trades a "
              "physical right rather than a security. No CFD exists on it, so it enters as a "
              "TRANSMISSION TARGET and a CONDITION"},
    {"name": "Bolsa de Valores Nacional (Guatemala), Bolsa Nacional de Valores (Costa Rica), "
             "Bolsa de Valores de El Salvador",
     "index_symbols": (), "open_local": "09:00", "close_local": "15:00",
     "open_utc": "15:00", "close_utc": "21:00", "dst_rule": "none: UTC-6 all year",
     "auction": "continuous with a closing call; turnover is overwhelmingly repo and government "
                "paper rather than equity",
     "expiry_rule": "there is no listed derivatives market anywhere on the isthmus and "
                    "therefore no expiry clock to mine",
     "holidays": "each national feriado calendar; Semana Santa closes all three",
     "notes": "NO CFD IS QUOTED on any of them and there is no equity mechanism worth hunting. "
              "Naming that is the measurement rather than a gap"},
    {"name": "The physical gate: Balboa and Cristobal, the Colon Free Zone, Puerto Quetzal, "
             "Puerto Cortes, Acajutla, Corinto and Moin",
     "index_symbols": (), "open_local": "00:00", "close_local": "23:59",
     "open_utc": "05:00", "close_utc": "04:59",
     "dst_rule": "none: UTC-5 in Panama and UTC-6 in the other five, all year",
     "auction": "none; the port authorities and the terminal operators publish throughput",
     "expiry_rule": "no expiry; the sailing schedule is the clock",
     "holidays": "ports work through the national calendars",
     "notes": "COLON IS THE LARGEST FREE ZONE IN THE AMERICAS and its re-export series is a "
              "read on regional import demand that no other pack on this desk carries. Puerto "
              "Cortes is the Honduran maquila's gate and Moin is Costa Rica's"},
)

SESSION_WINDOWS: tuple[dict[str, Any], ...] = (
    {"name": "ca_acp_advisory", "start_utc": "20:00", "end_utc": "23:00",
     "notes": "the hours in which an ACP advisory to shipping normally lands; Panama is UTC-5 "
              "all year so the window never moves"},
    {"name": "ca_isthmus_business", "start_utc": "14:00", "end_utc": "22:00",
     "notes": "the working day across all six: UTC-6 for five of them and UTC-5 for Panama, "
              "with no daylight saving anywhere"},
    {"name": "ca_coffee_ny_overlap", "start_utc": "13:30", "end_utc": "18:30",
     "notes": "the ICE Coffee C session, inside which every origin's news is priced; the origins "
              "do not change clock and New York does, so this overlap shifts twice a year"},
    {"name": "ca_remittance_print", "start_utc": "14:00", "end_utc": "20:00",
     "notes": "the hours in which Banguat, BCH, BCR and BCN publish the monthly family "
              "remittance series"},
    {"name": "ca_us_gulf_export", "start_utc": "14:00", "end_utc": "20:00",
     "notes": "the US Gulf loading and inspection day on the other side of the canal cell"},
)

RELEASE_CLASSES: tuple[dict[str, Any], ...] = (
    {"name": "ACP advisory to shipping: draft, transits and booking slots", "cadence": "irregular",
     "time_utc": "21:00", "source": "Autoridad del Canal de Panama",
     "actual_series": "ACP:calado_maximo_autorizado", "expected_series": "n/a",
     "notes": "the constraint announced by the constraining party, with an EFFECTIVE DATE in "
              "the future -- the rarest shape a commodity-logistics event can take"},
    {"name": "ACP daily transits and Gatun Lake level", "cadence": "daily", "time_utc": "14:00",
     "source": "Autoridad del Canal de Panama", "actual_series": "ACP:transitos_diarios",
     "expected_series": "ACP:nivel_lago_gatun",
     "notes": "the count and the cause, published together and daily"},
    {"name": "ACP transit auction clearing price", "cadence": "irregular", "time_utc": "20:00",
     "source": "Autoridad del Canal de Panama and the shipping trade press",
     "actual_series": "ACP:subasta_precio_de_cierre", "expected_series": "n/a",
     "notes": "reported rather than published as a clean series; PRESS_REPORTED and assembled"},
    {"name": "National coffee institute monthly export volume, five origins",
     "cadence": "monthly", "time_utc": "16:00",
     "source": "ANACAFE, IHCAFE, ICAFE, CONACAFE and the Consejo Salvadoreno del Cafe",
     "actual_series": "CAFE:exportaciones_mensuales", "expected_series": "ICO:indicador_compuesto",
     "notes": "five separate national counts on ONE harvest calendar; summing them is a "
              "washed-arabica supply series with no equivalent anywhere else"},
    {"name": "Monthly family remittances", "cadence": "monthly", "time_utc": "16:00",
     "source": "Banguat, BCH, BCR and BCN",
     "actual_series": "CA:remesas_familiares", "expected_series": "n/a",
     "notes": "a fifth to a quarter of GDP in four of the six, published monthly with a lag of "
              "one to three weeks, and driven by a US labour market with dated policy acts"},
    {"name": "Junta Monetaria and TPM decisions", "cadence": "irregular, published calendar",
     "time_utc": "20:00", "source": "Banguat, BCCR, BCH and BCN",
     "actual_series": "CA:tasa_de_politica", "expected_series": "BANGUAT:encuesta_panel",
     "notes": "four decisions bodies, four calendars, two dollarised neighbours with none -- "
              "which is the experiment"},
    {"name": "Monthly trade and customs statistics", "cadence": "monthly", "time_utc": "16:00",
     "source": "SIECA, the national customs authorities and the central banks",
     "actual_series": "SIECA:comercio_intrarregional", "expected_series": "n/a",
     "notes": "SIECA publishes intra-regional trade for all six on one definition, which is "
              "what makes a mirror comparison possible where a national series has narrowed"},
    {"name": "Colon Free Zone re-exports and Panamanian port throughput", "cadence": "monthly",
     "time_utc": "16:00", "source": "Contraloria General de la Republica (INEC) and the AMP",
     "actual_series": "INEC:zona_libre_reexportaciones", "expected_series": "n/a",
     "notes": "the largest free zone in the Americas is a read on regional import demand that "
              "leads the national trade prints of its customers"},
    {"name": "MICI and Gaceta Oficial mining and concession acts", "cadence": "irregular",
     "time_utc": "20:00", "source": "Ministerio de Comercio e Industrias and the gazette",
     "actual_series": "GACETA:actos_mineros", "expected_series": "n/a",
     "notes": "Ley 406, the Supreme Court ruling and the closure order are all gazetted acts "
              "with dates; this is how a copper supply shock becomes citable rather than "
              "PRESS_REPORTED"},
)

# --------------------------------------------------------------------------- holidays
#: SIX GREGORIAN, CATHOLIC CALENDARS THAT AGREE ON EXACTLY TWO THINGS AND DISAGREE ON THE REST.
#: Rows are (month, day, name) per jurisdiction. Everything movable is DERIVED below and nothing
#: movable is typed: Semana Santa and Carnaval come out of `easter(year)`, the Honduran Feriado
#: Morazanico out of the October week rule, Costa Rica's moved days out of the Ley de Traslado,
#: and the Honduran Mother's Day out of the second-Sunday rule.
FIXED_HOLIDAYS: dict[str, tuple[tuple[int, int, str], ...]] = {
    "pa": ((1, 1, "Ano Nuevo"),
           (1, 9, "Dia de los Martires (1964)"),
           (5, 1, "Dia del Trabajador"),
           (11, 3, "Separacion de Panama de Colombia"),
           (11, 4, "Dia de la Bandera"),
           (11, 10, "Primer Grito de Independencia de la Villa de Los Santos"),
           (11, 28, "Independencia de Panama de Espana"),
           (12, 8, "Dia de la Madre"),
           (12, 25, "Navidad")),
    "gt": ((1, 1, "Ano Nuevo"),
           (5, 1, "Dia del Trabajo"),
           (6, 30, "Dia del Ejercito"),
           (9, 15, "Dia de la Independencia"),
           (10, 20, "Dia de la Revolucion de 1944"),
           (11, 1, "Dia de Todos los Santos"),
           (12, 25, "Navidad")),
    "hn": ((1, 1, "Ano Nuevo"),
           (4, 14, "Dia de las Americas"),
           (5, 1, "Dia del Trabajo"),
           (9, 15, "Dia de la Independencia"),
           (12, 25, "Navidad")),
    "cr": ((1, 1, "Ano Nuevo"),
           (4, 11, "Batalla de Rivas / Juan Santamaria"),
           (5, 1, "Dia del Trabajo"),
           (7, 25, "Anexion del Partido de Nicoya"),
           (8, 2, "Virgen de los Angeles"),
           (8, 15, "Dia de la Madre"),
           (9, 15, "Dia de la Independencia"),
           (12, 1, "Abolicion del Ejercito"),
           (12, 25, "Navidad")),
    "ni": ((1, 1, "Ano Nuevo"),
           (5, 1, "Dia del Trabajo"),
           (7, 19, "Triunfo de la Revolucion"),
           (9, 14, "Batalla de San Jacinto"),
           (9, 15, "Dia de la Independencia"),
           (12, 8, "La Purisima"),
           (12, 25, "Navidad")),
    "sv": ((1, 1, "Ano Nuevo"),
           (5, 1, "Dia del Trabajo"),
           (5, 10, "Dia de la Madre"),
           (6, 17, "Dia del Padre"),
           (8, 6, "Dia del Divino Salvador del Mundo"),
           (9, 15, "Dia de la Independencia"),
           (11, 2, "Dia de los Difuntos"),
           (12, 25, "Navidad")),
}
#: THE ONE THING ALL SIX SHARE, and it is Easter-derived. Offsets are from Easter Sunday.
#: Holy Thursday and Good Friday shut every jurisdiction on this isthmus at the same hour, which
#: is the single largest simultaneous liquidity event in the region and the only one that moves.
EASTER_OFFSETS: dict[str, tuple[tuple[int, str], ...]] = {
    "pa": ((-47, "Martes de Carnaval"), (-3, "Jueves Santo"), (-2, "Viernes Santo")),
    "gt": ((-3, "Jueves Santo"), (-2, "Viernes Santo"), (-1, "Sabado de Gloria")),
    "hn": ((-3, "Jueves Santo"), (-2, "Viernes Santo"), (-1, "Sabado de Gloria")),
    "cr": ((-3, "Jueves Santo"), (-2, "Viernes Santo")),
    "ni": ((-3, "Jueves Santo"), (-2, "Viernes Santo")),
    "sv": ((-3, "Jueves Santo"), (-2, "Viernes Santo"), (-1, "Sabado Santo")),
}
#: COSTA RICA'S LEY DE TRASLADO DE FERIADOS moves several national days to a Monday so the
#: country gets a long weekend and its tourism sector gets the receipts. The RULE is derived in
#: `monday_shift`; these are the dates it is applied to. STATUS: the statute is Ley 9875 (2020)
#: and the exact membership of the moved set has been amended; 15 August and 12 October are
#: UNRESOLVED here and are deliberately NOT claimed. A wrong rule is worse than a named gap.
MONDAY_MOVED: dict[str, tuple[tuple[int, int], ...]] = {
    "cr": ((4, 11), (7, 25), (12, 1)),
}
#: Half-days that are not closures and are not nothing either. A half session is a liquidity
#: state a closure table cannot express, so it is carried separately rather than rounded.
HALF_DAYS: dict[str, tuple[tuple[int, int, str], ...]] = {
    "gt": ((12, 24, "Nochebuena: the public sector works a half day"),
           (12, 31, "fin de ano: the public sector works a half day")),
    "sv": ((12, 24, "Nochebuena: half day"), (12, 31, "fin de ano: half day")),
    "hn": ((12, 24, "Nochebuena: half day"), (12, 31, "fin de ano: half day")),
}
#: REGIONAL DAYS THAT ARE NOT NATIONAL CLOSURES and still stop the thing the desk cares about.
#: Rows are (offset-from-Easter or None, month, day, jurisdiction, region, name).
REGIONAL_DAYS: tuple[tuple[int | None, int, int, str, str, str], ...] = (
    (-48, 0, 0, "pa", "nationwide", "Lunes de Carnaval (not statutory; the country stops)"),
    (None, 11, 5, "pa", "Colon", "Dia de Colon"),
    (None, 8, 15, "gt", "Guatemala City", "Virgen de la Asuncion (capital only)"),
    (None, 8, 1, "ni", "Managua", "Santo Domingo: bajada"),
    (None, 8, 10, "ni", "Managua", "Santo Domingo: subida"),
    (None, 8, 3, "sv", "San Salvador", "Fiestas Agostinas (capital)"),
    (None, 8, 5, "sv", "San Salvador", "Fiestas Agostinas (capital)"),
    (None, 3, 19, "gt", "Antigua and the highlands", "San Jose; the coffee towns stop"),
)


def easter(year: int) -> date:
    """Easter Sunday by the ANONYMOUS GREGORIAN ALGORITHM.

    Every movable date on this isthmus is an offset from it -- Jueves Santo and Viernes Santo in
    all six jurisdictions, Sabado de Gloria in three, and the Panamanian Carnaval Monday and
    Tuesday -- so the tables extend to any year without anybody editing them. SEMANA SANTA IS THE
    ONLY DAY THE WHOLE ISTHMUS IS SHUT AT ONCE and it is computed, never typed.
    """
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    lu = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * lu) // 451
    month, day = divmod(h + lu - 7 * m + 114, 31)
    return date(year, month, day + 1)


def semana_santa(year: int) -> dict[date, str]:
    """Jueves Santo and Viernes Santo: THE TWO DAYS ALL SIX JURISDICTIONS CLOSE TOGETHER."""
    base = easter(year)
    return {base - timedelta(days=3): "Jueves Santo", base - timedelta(days=2): "Viernes Santo"}


def carnaval(year: int) -> tuple[date, date]:
    """Carnaval Monday and Tuesday: Easter minus 48 and 47. TUESDAY IS STATUTORY IN PANAMA and
    Monday is not, and Panama stops for both -- two facts that are true at once, and a liquidity
    study that reads only the statute gets Panama's February exactly backwards."""
    base = easter(year)
    return base - timedelta(days=48), base - timedelta(days=47)


def monday_shift(day: date) -> date:
    """COSTA RICA'S LEY DE TRASLADO DE FERIADOS, DERIVED RATHER THAN TYPED.

    A moved feriado that falls on a Tuesday or a Wednesday is observed on the PRECEDING Monday;
    one that falls on a Thursday, Friday, Saturday or Sunday is observed on the FOLLOWING Monday;
    one that already falls on a Monday does not move. The point of deriving it is that the
    observed closure is then computable for any year, including the ones nobody has typed --
    and that a Costa Rican long weekend is a THREE-DAY liquidity hole whose position in the week
    is a function of the calendar rather than of the holiday.
    """
    weekday = day.weekday()          # Monday is 0
    if weekday == 0:
        return day
    if weekday in (1, 2):            # Tuesday, Wednesday -> back to Monday
        return day - timedelta(days=weekday)
    return day + timedelta(days=7 - weekday)    # Thursday..Sunday -> forward to Monday


def morazanico(year: int) -> tuple[date, ...]:
    """THE HONDURAN FERIADO MORAZANICO, DERIVED.

    Honduras consolidated its three October national days -- 3, 12 and 21 October -- into ONE
    movable four-day block running Wednesday to Saturday of the week that contains 3 October.
    The country, its banks, its customs posts and its maquila shut for the block, so a study
    that keeps 3, 12 and 21 October as fixed closures mislabels every October since the reform.
    Derived here so it extends to any year; the enabling decree is named in `HOLIDAYS_RULE`.
    """
    anchor = date(year, 10, 3)
    monday = anchor - timedelta(days=anchor.weekday())
    wednesday = monday + timedelta(days=2)
    return tuple(wednesday + timedelta(days=n) for n in range(4))


def national_holidays(cc: str, year: int) -> dict[date, str]:
    """One jurisdiction's statutory closure table for a year: the fixed days, the Easter-derived
    days, the derived rule days, and Costa Rica's Monday shift applied where the statute applies
    it. Keys are dates inside `year` by construction -- a shift that would leave the year is
    dropped rather than invented."""
    code = str(cc).lower()
    moved = set(MONDAY_MOVED.get(code, ()))
    out: dict[date, str] = {}
    for month, day, name in FIXED_HOLIDAYS.get(code, ()):
        got = date(year, month, day)
        if (month, day) in moved:
            shifted = monday_shift(got)
            if shifted.year != year:
                continue
            out[shifted] = f"{name} [trasladado al lunes]"
        else:
            out[got] = name
    base = easter(year)
    for offset, name in EASTER_OFFSETS.get(code, ()):
        got = base + timedelta(days=offset)
        if got.year == year:
            out[got] = name
    if code == "hn":
        for i, day_of in enumerate(morazanico(year)):
            if day_of.year == year:
                out[day_of] = f"Feriado Morazanico ({i + 1} de 4)"
    return dict(sorted(out.items()))


def independence_day_closures(year: int) -> dict[str, date]:
    """FIVE COUNTRIES, ONE DATE. Guatemala, Honduras, El Salvador, Nicaragua and Costa Rica all
    celebrate independence on 15 SEPTEMBER, because all five left Spain in one act in 1821.
    PANAMA DOES NOT: Panama was part of Colombia until 1903 and its national days are in
    November. So 15 September is a five-country simultaneous closure with a sixth neighbour
    open beside it -- a genuinely distinctive regional calendar fact and a built-in control."""
    return {cc: date(year, 9, 15) for cc in JURISDICTIONS
            if any((m, d) == (9, 15) for m, d, _n in FIXED_HOLIDAYS.get(cc, ()))}


def region_holidays(year: int) -> dict[date, str]:
    """THE UNION TABLE: every day on which at least one jurisdiction is closed, tagged with which
    ones. A date several countries share carries every name, because the entire point of an
    isthmus-level calendar is telling a shared closure from a single-country one."""
    tagged: dict[date, list[str]] = {}
    for cc in JURISDICTIONS:
        for day, name in national_holidays(cc, year).items():
            tagged.setdefault(day, []).append(f"{cc}: {name}")
    return {day: " | ".join(names) for day, names in sorted(tagged.items())}


def market_holidays(year: int) -> dict[date, str]:
    """The isthmus's closed WEEKDAYS. A feriado on a Saturday or a Sunday costs no session in any
    of the six -- none of them substitutes a weekend holiday onto the Monday as a general rule,
    and the one Monday rule that does exist is Costa Rica's and is already applied -- so a
    weekend feriado must never enter a liquidity sample."""
    return {d: n for d, n in region_holidays(year).items() if d.weekday() < 5}


def shared_closures(year: int, minimum: int = 4) -> dict[date, int]:
    """Dates on which `minimum` or more of the six are shut at once.

    THE ONLY DAYS THE WHOLE ISTHMUS IS ILLIQUID TOGETHER. Everything else is one country's
    holiday against five working neighbours, which is a completely different object: a
    single-jurisdiction closure is a NATURAL CONTROL and a shared one is a liquidity regime.
    """
    counts: dict[date, int] = {}
    for cc in JURISDICTIONS:
        for day in national_holidays(cc, year):
            counts[day] = counts.get(day, 0) + 1
    return {d: n for d, n in sorted(counts.items()) if n >= minimum}


def is_closed_in(cc: str, day: date) -> bool:
    """True when that one jurisdiction is statutorily closed on that day."""
    return day in national_holidays(cc, day.year)


def mothers_day(cc: str, year: int) -> date | None:
    """SIX COUNTRIES, FIVE DIFFERENT MOTHER'S DAYS, AND EVERY ONE OF THEM IS A REMITTANCE SPIKE.

    Guatemala and El Salvador keep 10 May, Nicaragua keeps 30 May, Costa Rica keeps 15 August,
    Panama keeps 8 December -- and HONDURAS USES THE SECOND SUNDAY IN MAY, which is a rule and
    is derived here rather than typed. The sending end of the remittance corridor is a US
    payday calendar and the receiving end is these five dates, so a remittance-seasonality
    study that uses one date for the region is averaging five different weeks together.
    """
    code = str(cc).lower()
    fixed = {"gt": (5, 10), "sv": (5, 10), "ni": (5, 30), "cr": (8, 15), "pa": (12, 8)}
    if code in fixed:
        month, day = fixed[code]
        return date(year, month, day)
    if code == "hn":
        first = date(year, 5, 1)
        first_sunday = first + timedelta(days=(6 - first.weekday()) % 7)
        return first_sunday + timedelta(days=7)
    return None


def remittance_peaks(year: int) -> dict[date, str]:
    """The dated receiving-end spikes: five Mother's Days plus the December corridor."""
    out: dict[date, str] = {}
    for cc in JURISDICTIONS:
        got = mothers_day(cc, year)
        if got is not None:
            out[got] = f"{cc}: Dia de la Madre -- the largest single-day remittance spike"
    out[date(year, 12, 20)] = "the December corridor: the heaviest remittance fortnight"
    return dict(sorted(out.items()))


HOLIDAYS_RULE: dict[str, Any] = {
    "kind": "six_gregorian_catholic_calendars_computed_from_statute",
    "authority": "Panama's feriados sit in the Codigo de Trabajo and the Gaceta Oficial; "
                 "Guatemala's in the Codigo de Trabajo article 127 and the Diario de Centro "
                 "America; Honduras's in the Codigo de Trabajo as amended by the Feriado "
                 "Morazanico decree; Costa Rica's in the Codigo de Trabajo as amended by the "
                 "Ley de Traslado de Feriados (Ley 9875, 2020); Nicaragua's in the Codigo del "
                 "Trabajo and La Gaceta; El Salvador's in the Codigo de Trabajo and the Diario "
                 "Oficial",
    "rule": "SIX CALENDARS, ALL GREGORIAN AND ALL CATHOLIC, sharing exactly one movable block. "
            "SEMANA SANTA -- Jueves Santo (Easter minus 3) and Viernes Santo (Easter minus 2) -- "
            "CLOSES ALL SIX SIMULTANEOUSLY and is computed with the anonymous Gregorian "
            "algorithm in `easter(year)`, never typed; Guatemala, Honduras and El Salvador add "
            "Sabado de Gloria (Easter minus 1). PANAMA adds Martes de Carnaval (Easter minus "
            "47) as a statutory day and stops for Carnaval Monday (minus 48) without one. "
            "FIFTEEN SEPTEMBER IS ONE DATE AND FIVE CLOSURES: Guatemala, Honduras, El Salvador, "
            "Nicaragua and Costa Rica all celebrate the 1821 independence on it and PANAMA DOES "
            "NOT, because Panama left Colombia in 1903 and keeps 3 and 28 November plus the "
            "9 January Martyrs' Day instead -- which makes Panama the built-in control for "
            "every regional closure cell. HONDURAS derives its FERIADO MORAZANICO from the "
            "October week rule in `morazanico(year)`: Wednesday to Saturday of the week "
            "containing 3 October, replacing the old fixed 3, 12 and 21 October. COSTA RICA "
            "moves several days to the nearest Monday under the Ley de Traslado, DERIVED in "
            "`monday_shift`: Tuesday and Wednesday go back to the preceding Monday, Thursday "
            "through Sunday go forward to the following one. NO WEEKEND SUBSTITUTION is applied "
            "anywhere else: a feriado on a Sunday is simply lost, which is itself a liquidity "
            "fact a pooled sample will otherwise smear.",
    "years": (2024, 2025, 2026),
    "weekend": "Saturday and Sunday",
    "national_rule": "`national_holidays(cc, year)` per jurisdiction",
    "market_rule": "`market_holidays(year)`: the six-country union on weekdays only",
    "shared_rule": "`shared_closures(year, minimum)`: the days four or more of the six are shut "
                   "at once -- Semana Santa, New Year, 1 May and 25 December, and 15 September "
                   "for five of the six",
    "dst": "NONE ANYWHERE. Panama is UTC-5 all year and the other five are UTC-6 all year; not "
           "one of the six observes daylight saving. Every UTC window in this pack is the same "
           "minute in January and in July, while the exchanges these cells settle against (ICE "
           "Coffee C, COMEX, the LME) all move twice a year -- so the ORIGIN-TO-EXCHANGE HOUR "
           "GAP shifts twice a year even though nothing on the isthmus changed",
    "statute_break": "the Honduran Feriado Morazanico replaced three fixed October days with one "
                     "movable four-day block; a pooled October sample that does not carry the "
                     "break mislabels four days a year on one side of it and three on the other",
    "table": {y: {d.isoformat(): n for d, n in region_holidays(y).items()}
              for y in (2024, 2025, 2026)},
    "status": {2024: "STATUTORY for the fixed days, COMPUTED for Semana Santa, Carnaval, the "
                     "Morazanico and the Costa Rican Monday shift",
               2025: "STATUTORY and COMPUTED; no one-off decree is carried",
               2026: "STATUTORY and COMPUTED; any asueto a government decrees for 2026 is not "
                     "yet published and is therefore UNMEASURED rather than absent"},
    "unresolved": "the exact membership of Costa Rica's moved set has been amended since Ley "
                  "9875: 15 August and 12 October are NOT claimed here in either direction and "
                  "must be confirmed against La Gaceta before a Costa Rican August or October "
                  "closure cell is compiled",
    "known_dates": {
        "2024-03-28": "Jueves Santo in all six (Easter 2024 is 31 March)",
        "2024-09-15": "Independence in FIVE of the six; Panama is open",
        "2024-11-28": "Independencia de Panama de Espana -- Panama alone",
        "2025-04-17": "Jueves Santo in all six (Easter 2025 is 20 April)",
        "2025-10-01": "Feriado Morazanico day one 2025 (3 October 2025 is a Friday)",
        "2026-04-02": "Jueves Santo in all six (Easter 2026 is 5 April)",
        "2026-01-09": "Dia de los Martires -- Panama alone",
    },
    "fn": market_holidays,
    "national_fn": national_holidays,
    "region_fn": region_holidays,
    "easter_fn": easter,
    "carnaval_fn": carnaval,
    "morazanico_fn": morazanico,
    "monday_shift_fn": monday_shift,
}

# --------------------------------------------------------------------------- the canal
#: THE BASELINE the constraint is measured against: the ACP books about 36 transits a day when
#: the lake allows it, across the Panamax and Neopanamax booking segments together.
TRANSIT_BASELINE: int = 36
#: The Neopanamax design maximum draft in feet TFW, and the observed drought floor. Both are
#: PRESS_REPORTED: the ACP publishes them in advisories that are superseded in place, so the
#: archive layer's crawls are the only vintage (see ACCESS_CONSTRAINTS).
DRAFT_DESIGN_MAX_FT: float = 50.0
#: Gatun Lake's operating band in feet PLD. The maximum operating level is about 87.5 ft and the
#: 2023 drought took it near 79.5 ft -- the level that produced the draft cuts below.
GATUN_BAND_FT_PLD: tuple[float, float] = (79.5, 87.5)

#: THE MAXIMUM AUTHORISED DRAFT, AS A STEP FUNCTION. Rows are (effective date, feet TFW, status).
#: The ACP announces a change IN ADVANCE with an effective date, which is what makes this an
#: anticipable shock rather than a surprise -- and what makes the announcement date and the
#: effective date two DIFFERENT events with two different cells.
DRAFT_STEPS: tuple[tuple[date, float, str], ...] = (
    (date(2016, 6, 26), 50.0, "DESIGN: the Neopanamax locks open at the 50 ft design maximum"),
    (date(2023, 5, 24), 44.5, "PRESS_REPORTED"),
    (date(2023, 6, 25), 44.0, "PRESS_REPORTED"),
    (date(2024, 6, 15), 45.0, "PRESS_REPORTED"),
    (date(2024, 8, 5), 47.0, "PRESS_REPORTED"),
    (date(2025, 1, 6), 50.0, "PRESS_REPORTED"),
)
#: BOOKABLE TRANSIT SLOTS PER DAY, AS A STEP FUNCTION. Rows are (effective date, slots, status).
#: This is the series that went from 36 to 22 and back, and it is the pack's primary conditioner.
SLOT_STEPS: tuple[tuple[date, int, str], ...] = (
    (date(2016, 6, 26), 36, "DESIGN: the normal bookable capacity of the two-lane canal"),
    (date(2023, 7, 30), 32, "PRESS_REPORTED"),
    (date(2023, 11, 3), 25, "PRESS_REPORTED"),
    (date(2023, 12, 1), 22, "PRESS_REPORTED"),
    (date(2024, 1, 16), 24, "PRESS_REPORTED"),
    (date(2024, 3, 18), 27, "PRESS_REPORTED"),
    (date(2024, 6, 1), 32, "PRESS_REPORTED"),
    (date(2024, 8, 5), 35, "PRESS_REPORTED"),
    (date(2024, 9, 2), 36, "PRESS_REPORTED"),
)
#: THE AUCTION PRINTS. A slot is an option on a loading window and these are the strikes the
#: market paid for it. Rows are (date, US dollars, what, status). The November 2023 print is the
#: reported record and it was paid by an LPG carrier, which is exactly the cargo whose charter
#: economics make a missed window cost more than four million dollars.
AUCTION_PRINTS: tuple[tuple[date, float, str, str], ...] = (
    (date(2023, 8, 21), 2_400_000.0,
     "a released slot auctioned while the queue outside the breakwater was at its longest",
     "PRESS_REPORTED"),
    (date(2023, 11, 8), 3_975_000.0,
     "the reported record for a single Neopanamax slot; the winner was an LPG carrier",
     "PRESS_REPORTED"),
    (date(2023, 12, 19), 2_800_000.0,
     "a December slot, with the booked capacity at its 22-a-day floor", "PRESS_REPORTED"),
)
#: THE SUBSTITUTION CONTROL, NAMED EXPLICITLY. When one chokepoint closes the other's traffic is
#: the counterfactual, and 2023-2024 supplied a natural experiment by constraining BOTH at once
#: for unrelated reasons -- Panama by drought and the Red Sea by attack. A canal cell that does
#: not carry this control is measuring 'global freight' and calling it 'Panama'.
CHOKEPOINT_CONTROLS: tuple[dict[str, Any], ...] = (
    {"name": "Suez Canal", "operator": "the Suez Canal Authority",
     "observable": "daily transits and net tonnage, published by the SCA and mirrored by the "
                   "IMF PortWatch and UNCTAD chokepoint trackers",
     "why": "the alternative for Asia-to-US-East-Coast and Asia-to-Europe box traffic; a cargo "
            "that cannot buy a Panama slot can route Suez or the Cape, and the split between "
            "the three is the counterfactual this pack's canal cells need",
     "status": "PRESS_REPORTED transit counts; the SCA's own series is the authority"},
    {"name": "Bab el-Mandeb and the Red Sea", "operator": "no operator: a strait, not a canal",
     "observable": "transit counts through the strait, which collapsed from late 2023 as "
                   "carriers diverted around the Cape of Good Hope",
     "why": "THE REASON THE 2023-2024 EXPERIMENT IS CLEAN AND DIRTY AT THE SAME TIME. Both "
            "chokepoints constricted in the same months for entirely unrelated reasons, so a "
            "freight move in that window is NOT attributable to Panama without the Red Sea "
            "series beside it -- and that is precisely what makes the pair a control rather "
            "than a confound, provided both are carried",
     "status": "PRESS_REPORTED; the IMF PortWatch daily series is the usable machine-readable "
               "form"},
    {"name": "The Cape of Good Hope routing share",
     "operator": "none; the residual route when both chokepoints are expensive",
     "observable": "the Asia-Europe and Asia-US-East-Coast voyage days and the implied fleet "
                   "absorption",
     "why": "the cost of the substitution: an extra ten to fourteen days at sea absorbs vessel "
            "capacity and is the mechanism by which a canal constraint becomes a freight rate",
     "status": "PRESS_REPORTED"},
)


def _step_value(steps: tuple[tuple[date, Any, str], ...], day: date, default: Any) -> Any:
    """The value in force on `day` in a dated step series. A date before the first step returns
    the default rather than the first value: a constraint had not been announced yet."""
    got = default
    for effective, value, _status in steps:
        if effective <= day:
            got = value
    return got


def authorised_draft(day: date) -> float:
    """THE MAXIMUM AUTHORISED DRAFT IN FEET on a date, from the declared step series.

    MECHANISM FUNCTION. This is a published physical constraint on how much cargo a ship may
    carry through the canal: every foot of draft is thousands of tonnes, and a grain or LPG
    carrier that cannot load to its marks either sails light or does not sail. The series is
    PRESS_REPORTED and each step must be joined to its Advisory to Shipping number before any
    cell compiled on it is promoted.
    """
    return float(_step_value(DRAFT_STEPS, day, DRAFT_DESIGN_MAX_FT))


def bookable_slots(day: date) -> int:
    """THE NUMBER OF TRANSIT SLOTS THE ACP WAS BOOKING on a date. Thirty-six is the unconstrained
    baseline and twenty-two was the 2023 floor -- a 39% cut in the throughput of a chokepoint
    that carries roughly a twentieth of world seaborne trade."""
    return int(_step_value(SLOT_STEPS, day, TRANSIT_BASELINE))


def is_canal_constrained(day: date) -> bool:
    """True when the ACP was booking FEWER than the baseline transits on that day. This is the
    conditioning state of the pack's primary domain and it is computed from a published series
    rather than from a narrative about a drought."""
    return bookable_slots(day) < TRANSIT_BASELINE


def constraint_days(start: date, end: date) -> list[date]:
    """Every day in [start, end] on which the canal was booking below baseline."""
    out: list[date] = []
    day = start
    while day <= end:
        if is_canal_constrained(day):
            out.append(day)
        day += timedelta(days=1)
    return out


def constraint_severity(day: date) -> str:
    """The constraint bucket a cell conditions on: NONE, MILD, SEVERE or EXTREME. Buckets are
    cut on the published slot count so the state is reproducible from the series alone."""
    slots = bookable_slots(day)
    if slots >= TRANSIT_BASELINE:
        return "NONE"
    if slots >= 30:
        return "MILD"
    if slots >= 24:
        return "SEVERE"
    return "EXTREME"


# --------------------------------------------------------------------------- the coffee belt
#: FIVE ORIGINS, FIVE NATIONAL INSTITUTES, ONE HARVEST YEAR. Each of these bodies issues the
#: EXPORT PERMIT, which is why each one counts every bag that leaves the country rather than
#: estimating it -- a counted physical series on a liquid contract.
COFFEE_INSTITUTES: dict[str, dict[str, str]] = {
    "gt": {"name": "Asociacion Nacional del Cafe (ANACAFE)", "root": "https://www.anacafe.org",
           "series": "ANACAFE:exportaciones_mensuales",
           "note": "ANACAFE issues the export permit for every shipment, so its monthly volume "
                   "is a count and not a survey; it also publishes the regional origin split "
                   "across Huehuetenango, Antigua, Coban, Atitlan and the Oriente"},
    "hn": {"name": "Instituto Hondureno del Cafe (IHCAFE)", "root": "https://www.ihcafe.hn",
           "series": "IHCAFE:exportaciones_mensuales",
           "note": "Honduras is the largest producer of the five and IHCAFE publishes both the "
                   "monthly export volume and the accumulated harvest-year total"},
    "cr": {"name": "Instituto del Cafe de Costa Rica (ICAFE)", "root": "https://www.icafe.cr",
           "series": "ICAFE:exportaciones_y_liquidacion",
           "note": "COSTA RICA IS UNIQUE: by law the exporter's price is LIQUIDATED back to the "
                   "producer on a formula ICAFE administers and publishes, so the pass-through "
                   "from the exchange price to the farm gate is a PUBLISHED NUMBER here and an "
                   "inference everywhere else"},
    "ni": {"name": "Comision Nacional del Cafe (CONACAFE) and the BCN export series",
           "root": "https://www.bcn.gob.ni",
           "series": "BCN:exportaciones_de_cafe",
           "note": "Nicaragua's institutional coffee reporting is thinner than its neighbours' "
                   "and the BCN's own export series is the reliable monthly count; see "
                   "NO_LAWFUL_GROUND for what has narrowed and what substitutes for it"},
    "sv": {"name": "Consejo Salvadoreno del Cafe", "root": "https://www.consejocafe.org",
           "series": "CSC:exportaciones_mensuales",
           "note": "the smallest of the five by volume and the one whose output collapsed most "
                   "after the roya; its series is the cleanest illustration of what an epidemic "
                   "does to an origin over a decade"},
}
#: The harvest year every one of the five runs on.
HARVEST_YEAR_START: tuple[int, int] = (10, 1)
#: THE DATED SHOCKS TO THIS BELT, and the two Brazilian ones that are its substitution control.
#: Rows are (start, end, scope, what, status).
COFFEE_SHOCKS: tuple[tuple[date, date, str, str, str], ...] = (
    (date(2012, 10, 1), date(2014, 9, 30), "gt/hn/ni/sv/cr",
     "LA ROYA: the coffee leaf rust epidemic crosses the whole belt. Guatemala, Honduras and "
     "Costa Rica each declare a national emergency and the belt loses a large share of output "
     "for two consecutive crop years -- an origin-specific biological supply shock with no "
     "Brazilian counterpart in the same window", "PRESS_REPORTED"),
    (date(2020, 11, 3), date(2020, 11, 18), "hn/ni/gt",
     "Hurricanes Eta and Iota make landfall two weeks apart on the same coast, flooding the "
     "Honduran and Nicaraguan coffee and banana zones at the start of the harvest",
     "PRESS_REPORTED"),
    (date(2021, 7, 20), date(2021, 8, 31), "br (CONTROL)",
     "THE BRAZILIAN FROST. The arabica benchmark repriced on a Brazilian supply event with "
     "nothing wrong in Central America -- which is the control that separates 'arabica moved' "
     "from 'this belt moved'", "PRESS_REPORTED"),
    (date(2024, 8, 1), date(2024, 10, 31), "br (CONTROL)",
     "the Brazilian drought and fire season; again a benchmark move with no isthmus event",
     "PRESS_REPORTED"),
    (date(2023, 6, 1), date(2024, 3, 31), "gt/hn/sv/ni",
     "the El Nino dry corridor season: a rainfall deficit across the Corredor Seco through the "
     "flowering and filling window", "PRESS_REPORTED"),
)


def coffee_harvest_year(day: date) -> int:
    """The crop year a date belongs to, labelled by its OPENING year: 1 October 2024 to
    30 September 2025 is harvest year 2024. MECHANISM FUNCTION, and the sampling frame for every
    coffee cell in this pack -- an export volume compared across calendar years compares the
    back half of one crop with the front half of another and calls the difference a signal."""
    return day.year if (day.month, day.day) >= HARVEST_YEAR_START else day.year - 1


def harvest_phase(day: date) -> str:
    """Where in the crop year a date sits. The belt flowers in the spring rains, picks from
    November, ships hardest from January to May and runs lean from July: an export print in
    March and an export print in August are not the same measurement."""
    month = day.month
    if month in (10, 11, 12):
        return "harvest_opening"
    if month in (1, 2, 3, 4, 5):
        return "export_peak"
    if month in (6, 7):
        return "lean"
    return "flowering_and_filling"


def coffee_shocks_in(start: date, end: date) -> tuple[tuple[date, date, str, str, str], ...]:
    """Every declared shock episode overlapping a window, origin shocks and Brazilian controls
    together, so a study cannot accidentally sample one without the other."""
    return tuple(row for row in COFFEE_SHOCKS if row[0] <= end and row[1] >= start)


def origin_shock_days(start: date, end: date) -> list[date]:
    """Days inside a declared ISTHMUS shock window -- the Brazilian control rows excluded, which
    is the whole point of separating them in the table."""
    out: list[date] = []
    day = start
    while day <= end:
        if any(lo <= day <= hi and "CONTROL" not in scope
               for lo, hi, scope, _w, _s in COFFEE_SHOCKS):
            out.append(day)
        day += timedelta(days=1)
    return out


# --------------------------------------------------------------------------- remittances
#: A FIFTH TO A QUARTER OF GDP IN FOUR OF THE SIX, PUBLISHED MONTHLY BY THE CENTRAL BANK.
#: `gdp_share_pct` rows are PRESS_REPORTED orders of magnitude from the published national
#: accounts and are used for BUCKETING only -- never as a level in a cell.
REMITTANCE_SHARE: dict[str, dict[str, Any]] = {
    "hn": {"gdp_share_pct": 26.0, "publisher": "Banco Central de Honduras", "lag_days": 12.0,
           "status": "PRESS_REPORTED order of magnitude; the BCH monthly series is the number"},
    "ni": {"gdp_share_pct": 26.0, "publisher": "Banco Central de Nicaragua", "lag_days": 25.0,
           "status": "PRESS_REPORTED; the BCN still publishes this series monthly"},
    "sv": {"gdp_share_pct": 24.0, "publisher": "Banco Central de Reserva de El Salvador",
           "lag_days": 15.0, "status": "PRESS_REPORTED"},
    "gt": {"gdp_share_pct": 19.5, "publisher": "Banco de Guatemala", "lag_days": 3.0,
           "status": "PRESS_REPORTED; Banguat publishes within days, the fastest of the four"},
    "cr": {"gdp_share_pct": 1.5, "publisher": "Banco Central de Costa Rica", "lag_days": 60.0,
           "status": "PRESS_REPORTED; Costa Rica RECEIVES little and SENDS to Nicaragua, which "
                     "makes it the natural control inside the same isthmus"},
    "pa": {"gdp_share_pct": 1.0, "publisher": "Contraloria General (INEC)", "lag_days": 60.0,
           "status": "PRESS_REPORTED; Panama is a net SENDER and a transit economy, so it is "
                     "the second control"},
}
#: The dated US-side acts that move the sending end. Each is an ADMINISTRATIVE act with a date,
#: which is what makes the remittance series a policy-event series rather than a macro series.
US_POLICY_ACTS: tuple[tuple[date, str, str], ...] = (
    (date(2019, 7, 15), "the third-country asylum rule and the regional transit agreements",
     "PRESS_REPORTED"),
    (date(2020, 3, 20), "the pandemic border expulsion order; remittances FELL for one month "
                        "and then rose for two years, which is the pattern a naive model misses",
     "PRESS_REPORTED"),
    (date(2021, 6, 7), "the Root Causes Strategy announced for the three northern-triangle "
                       "countries", "PRESS_REPORTED"),
    (date(2023, 5, 11), "the expiry of the pandemic expulsion authority and the new parole and "
                        "appointment regime", "PRESS_REPORTED"),
    (date(2025, 1, 20), "the change of US administration and the announced enforcement posture; "
                        "the sending end of four countries' largest foreign-exchange earner",
     "PRESS_REPORTED"),
)


def remittance_regime(cc: str) -> str:
    """RECEIVER, MARGINAL or SENDER. Four of the six live on this flow and two do not, which is
    why the two that do not are the cleanest available control for every claim about it."""
    row = REMITTANCE_SHARE.get(str(cc).lower())
    if row is None:
        return "UNMEASURED"
    share = float(row["gdp_share_pct"])
    if share >= 15.0:
        return "RECEIVER"
    if share >= 5.0:
        return "MARGINAL"
    return "SENDER_OR_TRANSIT"


# --------------------------------------------------------------------------- the dated events
#: THE POLICY, JUDICIAL AND CREDIT EVENT SERIES. Rows are (date, jurisdiction, what, status).
#: Every row is PRESS_REPORTED: these are days as carried by the record, to be confirmed against
#: the Gaceta Oficial, the Diario de Centro America, La Gaceta or the Diario Oficial before a
#: cell compiled on one is promoted. Nothing here is presented as a verified gazette citation.
POLICY_EVENTS: tuple[tuple[date, str, str, str], ...] = (
    (date(1999, 12, 31), "pa", "the canal transfers from the United States to the Republic of "
                               "Panama and the ACP takes over as operator", "PRESS_REPORTED"),
    (date(2001, 1, 1), "sv", "the Ley de Integracion Monetaria takes effect: the colon is fixed "
                             "at 8.75 and the dollar becomes legal tender", "PRESS_REPORTED"),
    (date(2006, 10, 22), "pa", "the canal expansion is approved by national referendum",
     "PRESS_REPORTED"),
    (date(2016, 6, 26), "pa", "the Neopanamax locks open; US LNG and LPG gain a Pacific route "
                              "and the canal's cargo mix changes permanently", "PRESS_REPORTED"),
    (date(2013, 6, 13), "ni", "Ley 840 grants a 50-year interoceanic canal concession to HKND",
     "PRESS_REPORTED"),
    (date(2014, 12, 22), "ni", "groundbreaking on the Nicaraguan canal; no channel was ever cut",
     "PRESS_REPORTED"),
    (date(2024, 5, 8), "ni", "the National Assembly REPEALS the canal concession law, ending a "
                             "decade-long claim on a second isthmus crossing", "PRESS_REPORTED"),
    (date(2021, 6, 9), "sv", "the Legislative Assembly approves the Bitcoin Law", "PRESS_REPORTED"),
    (date(2021, 9, 7), "sv", "the Bitcoin Law takes effect", "PRESS_REPORTED"),
    (date(2023, 1, 23), "sv", "the 800 million dollar eurobond matures and is paid in full; the "
                              "distressed spread begins its rally", "PRESS_REPORTED"),
    (date(2024, 12, 18), "sv", "an IMF staff-level agreement on an Extended Fund Facility, with "
                               "the bitcoin programme narrowed as a condition", "PRESS_REPORTED"),
    (date(2025, 1, 29), "sv", "the Assembly amends the Bitcoin Law: acceptance becomes voluntary "
                              "and the legal-tender status is removed", "PRESS_REPORTED"),
    (date(2023, 10, 20), "pa", "Ley 406 approves the new Cobre Panama concession contract and "
                               "nationwide protests begin", "PRESS_REPORTED"),
    (date(2023, 11, 28), "pa", "THE SUPREME COURT DECLARES LEY 406 UNCONSTITUTIONAL: a top-twenty "
                               "copper mine is closed by a judicial act", "PRESS_REPORTED"),
    (date(2024, 3, 28), "pa", "a rating agency cuts Panama below investment grade, citing the "
                              "mine's closure and the fiscal hole it leaves", "PRESS_REPORTED"),
    (date(2025, 6, 1), "pa", "the government permits the export of the concentrate stockpiled on "
                             "site and opens a process on the mine's future", "PRESS_REPORTED"),
    (date(2023, 5, 24), "pa", "the ACP announces the first drought draft restriction of the "
                              "2023-2024 constraint", "PRESS_REPORTED"),
    (date(2023, 12, 1), "pa", "bookable transits reach their 22-a-day floor", "PRESS_REPORTED"),
    (date(2024, 9, 2), "pa", "bookable transits return to 36 a day", "PRESS_REPORTED"),
    (date(2015, 2, 2), "cr", "the BCCR abandons the crawling band and moves to a managed float",
     "PRESS_REPORTED"),
    (date(2018, 12, 4), "cr", "the Ley de Fortalecimiento de las Finanzas Publicas is enacted, "
                              "opening the 2018-2024 fiscal consolidation", "PRESS_REPORTED"),
    (date(2023, 11, 1), "ni", "the BCN cuts the published cordoba slide from 5% to 3%",
     "PRESS_REPORTED"),
    (date(2024, 1, 1), "ni", "the published slide is cut again and reaches ZERO: a crawling peg "
                             "stops crawling by administrative act", "PRESS_REPORTED"),
    (date(2006, 3, 1), "sv", "CAFTA-DR enters into force for El Salvador, the first of the six",
     "PRESS_REPORTED"),
    (date(2017, 6, 13), "pa", "Panama switches diplomatic recognition to the People's Republic "
                              "of China; the ports and logistics question follows from it",
     "PRESS_REPORTED"),
    (date(2018, 5, 1), "cr", "Costa Rica had switched in 2007; the regional pattern of "
                             "recognition changes becomes a dated trade-policy series",
     "PRESS_REPORTED"),
    (date(2023, 5, 15), "gt", "elPeriodico closes after its founder's imprisonment: a dated "
                              "press-freedom break that turns a live media ground into an "
                              "archive-only one", "PRESS_REPORTED"),
)

# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "ACP transit bookings, the waiting queue and the auction result",
     "root": "https://www.pancanal.com/en/advisories-to-shipping/",
     "fields": ("cupos_reservados", "buques_en_espera", "precio_subasta",
                "calado_maximo_autorizado"),
     "frequency": "daily and on every advisory", "snapshot": "the transit day",
     "publish_utc": "21:00", "lag_days": 0, "licence": "free, public", "available": True,
     "why": "THE CONSTRAINT, PUBLISHED BY THE CONSTRAINING PARTY. No other chokepoint on earth "
            "tells the market in advance how many ships it will take tomorrow and what the "
            "queue is paying to jump it. This is the conditioning variable of CA-A, CA-B and "
            "CA-D and no sibling pack has anything like it",
     "pit_warning": "advisories SUPERSEDE each other at the same URL, so the live page is the "
                    "current state and never the vintage; only the archive layer's crawls give "
                    "a point-in-time series"},
    {"name": "ACP daily Gatun and Alhajuela lake levels",
     "root": "https://pancanal.com/en/lake-levels/",
     "fields": ("nivel_lago_gatun_ft_pld", "nivel_lago_alhajuela", "precipitacion_cuenca"),
     "frequency": "daily", "snapshot": "the calendar day", "publish_utc": "14:00", "lag_days": 0,
     "licence": "free, public", "available": True,
     "why": "the LEADING half of the draft mechanism: the lake falls for months before an "
            "advisory cuts the draft, so this series is forecastable where the advisory is not",
     "pit_warning": "published as a current reading; the historical file is republished and the "
                    "archive layer is again the only vintage"},
    {"name": "Banguat FX reference rate and the published participation-rule trigger",
     "root": "https://www.banguat.gob.gt/es/page/tipo-de-cambio",
     "fields": ("tipo_de_cambio_referencia", "promedio_movil", "participacion_banguat_usd"),
     "frequency": "daily", "snapshot": "the business day", "publish_utc": "22:00", "lag_days": 0,
     "licence": "free, public", "available": True,
     "why": "the only FX reaction function on this isthmus that is ARITHMETIC ON A PUBLIC SERIES "
            "rather than a discretionary decision; the trigger can be recomputed exactly",
     "pit_warning": "the rule's margin and amounts are revised by Junta Monetaria resolution, so "
                    "a recomputed trigger is only valid inside the resolution's own window"},
    {"name": "BCH daily FX allocation auction: amount offered against amount bid",
     "root": "https://www.bch.hn/estadisticos-y-financieros/sector-externo",
     "fields": ("monto_ofertado", "monto_demandado", "precio_base", "tipo_de_cambio_promedio"),
     "frequency": "daily", "snapshot": "the auction", "publish_utc": "19:00", "lag_days": 1,
     "licence": "free, public", "available": True,
     "why": "the lempira is ALLOCATED, not cleared: the gap between offered and bid is the "
            "shortage, and it is invisible in the posted rate that most studies use",
     "pit_warning": "the published series is the settled auction; the QUEUE of unfilled demand "
                    "carries into the following days and must be cumulated, not differenced"},
    {"name": "Monthly family remittances, four central banks on one definition",
     "root": "https://www.banguat.gob.gt/es/page/remesas-familiares",
     "fields": ("remesas_mensuales_usd", "variacion_interanual", "remesas_acumuladas"),
     "frequency": "monthly", "snapshot": "the calendar month", "publish_utc": "16:00",
     "lag_days": 12, "licence": "free, public", "available": True,
     "why": "a fifth to a quarter of GDP in four of the six, published monthly, driven by a US "
            "labour market whose policy acts are dated -- the highest-frequency link between "
            "the US cycle and this isthmus that exists",
     "pit_warning": "the four banks publish on DIFFERENT lags (Banguat within days, the BCN "
                    "within weeks); summing them at a single date mixes vintages"},
    {"name": "The five coffee institutes' monthly export volumes",
     "root": "https://www.anacafe.org/estadisticas/",
     "fields": ("quintales_exportados", "acumulado_ano_cosecha", "destino"),
     "frequency": "monthly", "snapshot": "the calendar month within the harvest year",
     "publish_utc": "16:00", "lag_days": 20, "licence": "free, public", "available": True,
     "why": "five counted national series -- not surveys, because each institute issues the "
            "export permit -- summing to a washed-arabica supply number with no equivalent",
     "pit_warning": "each institute restates the prior month when late permits clear; and the "
                    "HARVEST YEAR is not the calendar year, so a naive year-on-year comparison "
                    "compares two different crops"},
    {"name": "CFTC Commitments of Traders: Coffee C, Sugar No. 11, copper and cotton",
     "root": "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm",
     "fields": ("managed_money_long", "managed_money_short", "producer_merchant",
                "open_interest"),
     "frequency": "weekly", "snapshot": "Tuesday", "publish_utc": "19:30", "lag_days": 3,
     "licence": "public domain (US government work)", "available": True,
     "why": "the executable contracts' own positioning. An isthmus supply shock into a crowded "
            "managed-money short is a different trade from the same shock into a flat book",
     "pit_warning": "a Tuesday snapshot published Friday: a Wednesday advisory or a Thursday "
                    "court ruling is invisible until the following week's report"},
    {"name": "IMF PortWatch daily chokepoint transit counts",
     "root": "https://portwatch.imf.org",
     "fields": ("transits_panama", "transits_suez", "transits_bab_el_mandeb", "cape_reroutes"),
     "frequency": "daily", "snapshot": "the calendar day", "publish_utc": "12:00", "lag_days": 2,
     "licence": "free, public (IMF open data)", "available": True,
     "why": "THE SUBSTITUTION CONTROL IN MACHINE-READABLE FORM. The counterfactual for a Panama "
            "constraint is what Suez and the Cape did in the same days, and this is the one "
            "public daily series that carries all three on one definition",
     "pit_warning": "derived from vessel tracking rather than from the canal authorities, so it "
                    "is an ESTIMATE of transits and the ACP's own count is the authority"},
    {"name": "a CFTC or exchange-traded positioning series for ANY of the six currencies",
     "root": "", "fields": (), "frequency": "n/a", "snapshot": "", "publish_utc": "",
     "lag_days": 0, "licence": "", "available": False,
     "why": "DECLARED ABSENT: no PAB, GTQ, HNL, CRC, NIO or SVC future trades on any exchange "
            "the desk can read, no COT contract covers any of them, and two of the six are the "
            "dollar and therefore cannot have one by construction",
     "pit_warning": "DOES NOT EXIST: isthmus currency positioning is UNMEASURED and is never "
                    "proxied by the MXN or BRL COT legs, which are positions in other "
                    "countries' politics"},
)

# --------------------------------------------------------------------------- terminology
#: FOUR LANGUAGES AND THE PACK MEANS IT. Spanish is the working language of every institution on
#: this isthmus. K'ICHE', Q'EQCHI' AND KAQCHIKEL are the languages of Guatemala's highland
#: departments -- Huehuetenango, Quiche, Alta Verapaz, Solola, Totonicapan -- which is exactly
#: where the coffee grows and where the land, labour and road disputes that interrupt a harvest
#: are argued, decided and reported. A Spanish-only crawl of Guatemala reads the capital's
#: account of the altiplano and calls it the altiplano.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "CA-A": ("Canal de Panamá", "Autoridad del Canal de Panamá", "calado máximo autorizado",
             "aviso a la navegación", "tránsitos diarios", "esclusas de Agua Clara",
             "esclusas de Cocolí", "Neopanamax", "restricción de calado", "buques en espera",
             "cuenca hidrográfica del Canal", "tonelada CP/SUAB"),
    "CA-B": ("subasta de cupos", "sistema de reservación de tránsito", "cupo de tránsito",
             "peaje", "estructura de peajes", "precio de cierre de la subasta",
             "cargo por sobrecosto", "segmento de reservación", "buque gasero",
             "ventana de carga"),
    "CA-C": ("lago Gatún", "lago Alhajuela", "río Chagres", "nivel del lago",
             "sequía", "estación seca", "El Niño", "La Niña", "embalse", "río Indio",
             "precipitación en la cuenca", "ja' (K'iche': water, and the thing that ran out)"),
    "CA-D": ("canal de Suez", "Bab el-Mandeb", "cabo de Buena Esperanza", "ruta alterna",
             "desvío marítimo", "flete marítimo", "días de navegación", "punto de "
             "estrangulamiento", "recargo por el Canal de Panamá", "tránsito de buques"),
    "CA-E": ("café", "café lavado", "arábica", "exportaciones de café", "año cosecha",
             "quintal oro", "ANACAFE", "IHCAFE", "ICAFE", "Consejo Salvadoreño del Café",
             "permiso de exportación", "beneficio húmedo", "beneficio seco", "pergamino",
             "Huehuetenango", "Antigua", "Cobán", "Atitlán", "liquidación del café",
             "kape (K'iche'/Q'eqchi': coffee, the loanword the pickers use)",
             "k'anjel (Q'eqchi': the work, and the word a harvest labour dispute is about)",
             "samaj (Kaqchikel: work)"),
    "CA-F": ("roya del café", "la roya", "broca del café", "hongo", "renovación de cafetales",
             "emergencia fitosanitaria", "helada en Brasil", "sequía en Brasil",
             "diferencial de origen", "sustitución de origen", "robusta", "cosecha reducida",
             "ixim (K'iche'/Q'eqchi'/Kaqchikel: maize -- what a farmer plants when the coffee "
             "fails)"),
    "CA-G": ("dolarización", "Convenio Monetario de 1904", "balboa", "colón salvadoreño",
             "Ley de Integración Monetaria", "curso legal", "sin banco central",
             "señoreaje", "prestamista de última instancia", "tasa de la Reserva Federal",
             "trilema monetario", "régimen cambiario"),
    "CA-H": ("tasa de interés líder", "Junta Monetaria", "tasa de política monetaria",
             "regla de participación cambiaria", "tipo de cambio de referencia",
             "deslizamiento cambiario", "banda cambiaria", "subasta de divisas",
             "MONEX", "encaje legal", "meta de inflación", "reservas internacionales netas",
             "córdoba", "quetzal", "lempira", "colón costarricense"),
    "CA-I": ("remesas familiares", "remesas mensuales", "migrante", "corredor migratorio",
             "Día de la Madre", "envío de dinero", "casa de remesas", "TPS",
             "deportación", "Corredor Seco y migración", "ingreso de divisas",
             "tinamit (K'iche': the town the money is sent back to)"),
    "CA-J": ("Ley Bitcoin", "bitcóin de curso legal", "Chivo", "Oficina Nacional del Bitcoin",
             "bono volcán", "eurobono", "riesgo país", "recompra de deuda",
             "acuerdo con el FMI", "servicio ampliado del FMI", "calificación soberana",
             "reserva estratégica"),
    "CA-K": ("Cobre Panamá", "Minera Panamá", "Ley 406", "contrato minero",
             "Corte Suprema de Justicia", "inconstitucional", "cierre de la mina",
             "concentrado de cobre", "mantenimiento seguro", "moratoria minera",
             "protesta nacional", "cierre de vías", "regalía minera"),
    "CA-L": ("abanderamiento", "registro de buques", "bandera de conveniencia",
             "Autoridad Marítima de Panamá", "Centro Bancario Internacional",
             "Superintendencia de Bancos", "Zona Libre de Colón", "reexportaciones",
             "lista gris", "GAFI", "sociedad anónima", "puerto de Balboa", "puerto de Cristóbal"),
    "CA-M": ("zafra", "ingenio azucarero", "caña de azúcar", "molienda", "azúcar crudo",
             "ASAZGUA", "banano", "plátano", "fusarium raza 4", "finca bananera",
             "exportación agrícola", "Puerto Quetzal",
             "ulew (K'iche': the land the cane and the coffee are grown on)",
             "ch'och' (Q'eqchi': land -- the object of every agrarian dispute in the Verapaces)"),
    "CA-N": ("maquila", "CAFTA-DR", "regla de origen", "hilado en adelante", "zona franca",
             "confección textil", "algodón", "prenda de vestir", "arancel",
             "nearshoring", "cadena de suministro", "Puerto Cortés",
             "ch'ich' (K'iche': metal, and the word used for the machines and the trucks)"),
    "CA-O": ("dispositivos médicos", "semiconductores", "régimen de zona franca", "PROCOMER",
             "CINDE", "inversión extranjera directa", "regla fiscal",
             "Ley de Fortalecimiento de las Finanzas Públicas", "consolidación fiscal",
             "superávit primario", "OCDE", "encadenamiento productivo",
             "ruwach'ulew (Kaqchikel: the world/the land, the register a land title is argued in)"),
    "CA-P": ("Ley 840", "canal interoceánico de Nicaragua", "concesión", "derogación",
             "oro", "concesión minera", "exportaciones de oro", "minería artesanal",
             "güirisero", "INIDE", "estadísticas oficiales", "prensa en el exilio",
             "ya' (Kaqchikel: water, the lake the canal route was drawn across)"),
    "CA-Q": ("Corredor Seco", "sequía", "canícula", "pérdida de cosecha",
             "granos básicos", "maíz", "frijol", "seguridad alimentaria", "INSIVUMEH",
             "Instituto Meteorológico Nacional", "COPECO", "alerta agroclimática",
             "ha' (Q'eqchi': water)", "kutan (Q'eqchi': day, the unit a drought is counted in)",
             "ulef (Kaqchikel: land)"),
    "CA-R": ("feriado", "asueto", "Semana Santa", "Jueves Santo", "Viernes Santo",
             "Sábado de Gloria", "Carnaval", "Martes de Carnaval", "Día de la Independencia",
             "quince de septiembre", "Feriado Morazánico", "traslado de feriados",
             "día de los Mártires", "Gaceta Oficial", "Diario de Centro América",
             "La Gaceta", "Diario Oficial",
             "q'ij (K'iche': day, sun -- the unit the highland calendar counts in)",
             "ajq'ij (K'iche': the daykeeper who keeps the 260-day count)",
             "q'atb'al tzij (K'iche': the court, the authority that rules on a land claim)",
             "k'ayb'al (K'iche': the market, the weekly one the towns run on)",
             "komon (K'iche': the community that takes the decision)",
             "tenamit (Q'eqchi': the town)"),
}

# --------------------------------------------------------------------------- the ten layers
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

#: Latin script is shared by Spanish and by all three Mayan languages here, so "native script"
#: cannot be a codepoint test the way Arabic or Hangul can. It is a VOCABULARY test instead, and
#: the tests assert on all four lists: Spanish is detected by its diacritics (an English glossary
#: of this isthmus has none) and the three Mayan languages by their own words.
_SPANISH_DIACRITICS = "áéíóúüñÁÉÍÓÚÜÑ¿¡"
#: K'ICHE' working vocabulary -- the largest Mayan language, spoken across Quiche, Totonicapan,
#: Solola and Quetzaltenango, which is the western coffee belt. `ixim` (maize) and `ulew` (land)
#: are the two objects every highland dispute is actually about.
KICHE_MARKERS: tuple[str, ...] = (
    "ixim", "ulew", "ja'", "tinamit", "q'ij", "ajq'ij", "q'atb'al tzij", "k'ayb'al", "komon",
    "ch'ich'", "kape")
#: Q'EQCHI' working vocabulary -- Alta Verapaz and the Peten, the Coban coffee and cardamom
#: country and the ground of the longest-running land conflicts in Guatemala.
QEQCHI_MARKERS: tuple[str, ...] = ("ch'och'", "ha'", "tenamit", "k'anjel", "kutan")
#: KAQCHIKEL working vocabulary -- Chimaltenango, Solola and the Atitlan basin.
KAQCHIKEL_MARKERS: tuple[str, ...] = ("ya'", "ulef", "samaj", "ruwach'ulew")
#: SPANISH working vocabulary the pack must carry: every institution on this isthmus publishes in
#: it, and these are the exact strings a crawler needs.
SPANISH_MARKERS: tuple[str, ...] = (
    "calado máximo autorizado", "subasta de cupos", "lago Gatún", "aviso a la navegación",
    "exportaciones de café", "año cosecha", "roya del café", "remesas familiares",
    "deslizamiento cambiario", "regla de participación cambiaria", "dolarización",
    "Corredor Seco", "zafra", "maquila", "Zona Libre de Colón", "Feriado Morazánico",
    "Cobre Panamá", "bandera de conveniencia", "Ley Bitcoin", "Semana Santa")


def has_spanish_diacritic(text: str) -> bool:
    """True when the text carries a Spanish diacritic. An English translation of a Central
    American release has none, which is what makes this a usable native-language test on a
    Latin-script ground."""
    return any(ch in _SPANISH_DIACRITICS for ch in str(text))


def has_kiche(text: str) -> bool:
    """True when the text carries a declared K'iche' term."""
    return any(m in str(text) for m in KICHE_MARKERS)


def has_qeqchi(text: str) -> bool:
    """True when the text carries a declared Q'eqchi' term."""
    return any(m in str(text) for m in QEQCHI_MARKERS)


def has_kaqchikel(text: str) -> bool:
    """True when the text carries a declared Kaqchikel term."""
    return any(m in str(text) for m in KAQCHIKEL_MARKERS)


def has_mayan(text: str) -> bool:
    """True when the text carries any of the three declared Mayan vocabularies."""
    return has_kiche(text) or has_qeqchi(text) or has_kaqchikel(text)


def _flat_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> set[str]:
    rows = TERMINOLOGY if terminology is None else terminology
    return {t for terms in rows.values() for t in terms}


def spanish_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    """Every declared Spanish marker actually present in the terminology table."""
    flat = _flat_terms(terminology)
    return [m for m in SPANISH_MARKERS if any(m in t for t in flat)]


def kiche_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    flat = _flat_terms(terminology)
    return [m for m in KICHE_MARKERS if any(m in t for t in flat)]


def qeqchi_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    flat = _flat_terms(terminology)
    return [m for m in QEQCHI_MARKERS if any(m in t for t in flat)]


def kaqchikel_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    flat = _flat_terms(terminology)
    return [m for m in KAQCHIKEL_MARKERS if any(m in t for t in flat)]


def accented_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    """Every term carrying a Spanish diacritic -- the Latin-script equivalent of the Arabic
    codepoint test the `ma` pack uses."""
    return sorted(t for t in _flat_terms(terminology) if has_spanish_diacritic(t))


def term_count(terminology: Mapping[str, Iterable[str]] | None = None) -> int:
    return len(_flat_terms(terminology))


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
        "pa_acp", "Autoridad del Canal de Panama: advisories to shipping, maximum authorised "
                  "draft, booking slots, transit counts, auction results and daily lake levels",
        layer="official",
        roots=("https://www.pancanal.com/en/advisories-to-shipping/",
               "https://pancanal.com/en/lake-levels/",
               "https://pancanal.com/en/transit-reservation-system/",
               "https://pancanal.com/en/canal-statistics/"),
        queries=("aviso a la navegación calado máximo autorizado",
                 "restricción de calado Canal de Panamá",
                 "subasta de cupos de tránsito resultado",
                 "tránsitos diarios reservados Neopanamax",
                 "nivel del lago Gatún pies PLD", "estadísticas de tránsito del Canal",
                 "sistema de reservación de tránsito condiciones",
                 "peajes del Canal de Panamá tarifa"),
        languages=("es", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public (pancanal.com terms)",
        notes="THE SINGLE MOST VALUABLE ROOT IN THIS PACK. A global chokepoint operator that "
              "publishes its own binding constraint, in advance, with an effective date -- the "
              "supply half of CA-A, CA-B, CA-C and CA-D lives entirely here"),
    source_class(
        "pa_state", "The Panamanian state: Contraloria General (INEC) for prices, activity and "
                    "the Colon Free Zone; MICI for mining and commerce; the Superintendencia de "
                    "Bancos for what Panama has instead of monetary statistics; the Autoridad "
                    "Maritima for the ship registry; and the Gaceta Oficial for the acts",
        layer="official",
        roots=("https://www.contraloria.gob.pa/inec/",
               "https://www.mici.gob.pa",
               "https://www.superbancos.gob.pa/es/estadisticas/",
               "https://amp.gob.pa",
               "https://www.gacetaoficial.gob.pa"),
        queries=("índice de precios al consumidor Panamá INEC",
                 "reexportaciones Zona Libre de Colón estadística",
                 "Centro Bancario Internacional balance liquidez",
                 "registro de buques abanderamiento Panamá",
                 "Gaceta Oficial contrato minero Ley 406",
                 "concesión minera MICI resolución",
                 "índice mensual de actividad económica Panamá"),
        languages=("es", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE SUPERINTENDENCIA ROW IS THE SUBSTITUTE FOR A CENTRAL BANK THAT DOES NOT "
              "EXIST: the banking-system balance sheet, liquidity ratio and deposit base ARE "
              "Panama's monetary statistics, and NO_LAWFUL_GROUND says so by name"),
    source_class(
        "gt_official", "Banco de Guatemala (rate, reference FX, the participation rule, "
                       "remittances and trade), the Instituto Nacional de Estadistica, and the "
                       "SAT customs record",
        layer="official",
        roots=("https://www.banguat.gob.gt/es/page/estadisticas",
               "https://www.banguat.gob.gt/es/page/remesas-familiares",
               "https://www.ine.gob.gt",
               "https://portal.sat.gob.gt"),
        queries=("tasa de interés líder Junta Monetaria resolución",
                 "regla de participación cambiaria Banguat",
                 "remesas familiares Guatemala mensual",
                 "tipo de cambio de referencia quetzal",
                 "índice de precios al consumidor INE Guatemala",
                 "comercio exterior partida arancelaria SAT",
                 "encuesta de expectativas económicas panel de analistas"),
        languages=("es",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="Banguat publishes remittances within days of month end -- the fastest of the four "
              "publishers -- and its participation RULE is stated, which is what makes Guatemala "
              "the computable FX reaction function on this isthmus"),
    source_class(
        "hn_official", "Banco Central de Honduras (the allocation auction, the band, remittances "
                       "and reserves) and the Instituto Nacional de Estadistica",
        layer="official",
        roots=("https://www.bch.hn/estadisticos-y-financieros/sector-externo",
               "https://www.bch.hn/politica-monetaria",
               "https://www.ine.gob.hn"),
        queries=("subasta de divisas monto ofertado demandado BCH",
                 "banda cambiaria lempira precio base",
                 "remesas familiares Honduras mensual",
                 "tasa de política monetaria BCH resolución",
                 "índice mensual de actividad económica Honduras",
                 "exportaciones de café Honduras INE"),
        languages=("es",), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the auction series is the one that matters: the lempira is allocated rather than "
              "cleared, so the unfilled demand is the observable and the posted rate is not"),
    source_class(
        "cr_official", "Banco Central de Costa Rica (the TPM, MONEX and the full indicator "
                       "service), INEC, PROCOMER for the free-zone export record and Hacienda "
                       "for the fiscal rule",
        layer="official",
        roots=("https://www.bccr.fi.cr/indicadores-economicos",
               "https://www.bccr.fi.cr/seccion-indicadores-economicos/mercado-cambiario",
               "https://www.inec.cr",
               "https://www.procomer.com/estadisticas/",
               "https://www.hacienda.go.cr"),
        queries=("tasa de política monetaria BCCR comunicado",
                 "tipo de cambio MONEX promedio ponderado",
                 "participación del BCCR en el mercado cambiario",
                 "exportaciones de zona franca dispositivos médicos PROCOMER",
                 "regla fiscal gasto corriente Hacienda",
                 "índice mensual de actividad económica Costa Rica"),
        languages=("es", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE CONTROL JURISDICTION. Same isthmus, same coffee, same drought, its own money "
              "and a real policy rate -- which is what every dollarisation claim in this pack is "
              "measured against"),
    source_class(
        "ni_official", "Banco Central de Nicaragua (the FX table, the slide rate, remittances, "
                       "gold and coffee exports) and INIDE",
        layer="official",
        roots=("https://www.bcn.gob.ni/estadisticas",
               "https://www.bcn.gob.ni/sector-externo",
               "https://www.inide.gob.ni"),
        queries=("deslizamiento cambiario córdoba resolución BCN",
                 "tabla de tipo de cambio oficial Nicaragua",
                 "remesas familiares Nicaragua mensual",
                 "exportaciones de oro Nicaragua BCN",
                 "exportaciones de café Nicaragua quintales",
                 "índice mensual de actividad económica INIDE"),
        languages=("es",), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE BCN STILL PUBLISHES and its monthly external-sector series is usable; the "
              "surrounding statistical and press ecology has narrowed, which NO_LAWFUL_GROUND "
              "declares by name with the mirror-customs and Article IV substitutes"),
    source_class(
        "sv_official", "Banco Central de Reserva de El Salvador, the Oficina Nacional de "
                       "Estadistica y Censos and the Ministerio de Hacienda",
        layer="official",
        roots=("https://www.bcr.gob.sv/bcrsite/?cdr=36",
               "https://onec.bcr.gob.sv",
               "https://www.mh.gob.sv"),
        queries=("remesas familiares El Salvador mensual BCR",
                 "índice de precios al consumidor ONEC",
                 "deuda pública El Salvador Ministerio de Hacienda",
                 "exportaciones de maquila El Salvador",
                 "acuerdo con el FMI servicio ampliado El Salvador",
                 "Ley Bitcoin reforma curso legal"),
        languages=("es",), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="A CENTRAL BANK THAT PUBLISHES AND CANNOT DECIDE. Every Salvadoran cell here is a "
              "fiscal or credit cell, because dollarisation removed the monetary one"),
    # ---- institutional
    source_class(
        "ca_coffee_institutes", "ANACAFE, IHCAFE, ICAFE, the Consejo Salvadoreno del Cafe and "
                                "the International Coffee Organization: five national export "
                                "counts and the world composite indicator",
        layer="institutional",
        roots=("https://www.anacafe.org/estadisticas/",
               "https://www.ihcafe.hn",
               "https://www.icafe.cr/sector-cafetalero/estadisticas/",
               "https://www.consejocafe.org",
               "https://www.ico.org/prices/po-production.pdf"),
        queries=("exportaciones de café mensual quintales ANACAFE",
                 "año cosecha café 2024 2025 acumulado",
                 "liquidación del café ICAFE precio al productor",
                 "permiso de exportación de café IHCAFE",
                 "indicador compuesto OIC precio del café",
                 "café lavado arábica centroamericano diferencial",
                 "kape ruk'a'm ri kape (K'iche': the coffee and its picking)"),
        languages=("es", "en", "quc"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="each institute ISSUES THE EXPORT PERMIT, so its monthly number is a count rather "
              "than a survey -- five counted national supply series against one liquid contract"),
    source_class(
        "ca_sieca_bcie", "SIECA, the Central American economic integration secretariat, and the "
                         "Banco Centroamericano de Integracion Economica",
        layer="institutional",
        roots=("https://www.sieca.int/estadisticas/",
               "https://www.bcie.org",
               "https://estadisticas.sieca.int"),
        queries=("comercio intrarregional centroamericano SIECA",
                 "unión aduanera Guatemala Honduras El Salvador",
                 "arancel centroamericano de importación",
                 "BCIE préstamo soberano aprobación",
                 "estadísticas de comercio exterior Centroamérica"),
        languages=("es",), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="SIECA publishes all six on ONE definition, which is what makes a mirror "
              "comparison possible where a national series has narrowed; the BCIE is a material "
              "creditor to two of the six and its approvals are dated fiscal events"),
    source_class(
        "ca_bourses", "Bolsa de Valores Nacional (Guatemala), Bolsa Nacional de Valores (Costa "
                      "Rica) and Bolsa de Valores de El Salvador",
        layer="institutional",
        roots=("https://www.bvnsa.com.gt",
               "https://www.bolsacr.com",
               "https://www.bolsadevalores.com.sv"),
        queries=("boletín diario Bolsa de Valores Nacional",
                 "reportos tasa promedio bolsa Guatemala",
                 "subasta de valores del Gobierno Costa Rica",
                 "mercado de valores El Salvador emisiones"),
        languages=("es",), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="NOT_PREDICTIVE", licence="free, public",
        notes="REGISTERED AND NOT MINED FOR PRICES. These venues are repo and government-paper "
              "markets rather than equity markets and no CFD exists on any of them; the reason "
              "they are here is the SHORT-RATE series their repo turnover produces"),
    source_class(
        "ca_industry", "The industry bodies: ASAZGUA for the Guatemalan sugar mills, the "
                       "Asociacion Hondurena de Maquiladores for the apparel chain, and CINDE "
                       "for the Costa Rican free-zone cluster",
        layer="institutional",
        roots=("https://www.asazgua.org",
               "https://www.ahm-honduras.com",
               "https://www.cinde.org"),
        queries=("zafra caña de azúcar molienda ingenio",
                 "producción de azúcar Guatemala quintales",
                 "maquila textil Honduras empleo exportación",
                 "regla de origen hilado en adelante CAFTA-DR",
                 "inversión en zona franca dispositivos médicos Costa Rica"),
        languages=("es", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the zafra's weekly grind and the maquila's employment count are the physical "
              "series behind the SUGAR and COTTON cells, and neither is in a central bank's "
              "publication schedule"),
    # ---- academic
    source_class(
        "cr_gt_academic", "INCAE, the Universidad de Costa Rica, the Universidad de San Carlos "
                          "and the Universidad Rafael Landivar, plus ASIES on Guatemalan "
                          "political economy",
        layer="academic",
        roots=("https://www.incae.edu/es/investigacion",
               "https://www.ucr.ac.cr",
               "https://www.usac.edu.gt",
               "https://www.url.edu.gt/publicaciones",
               "https://www.asies.org.gt"),
        queries=("dolarización y crecimiento economía pequeña abierta",
                 "efecto de las remesas sobre el consumo Centroamérica",
                 "conflictividad agraria tierra Alta Verapaz investigación",
                 "roya del café impacto en el empleo rural estudio",
                 "regla fiscal Costa Rica evaluación",
                 "ch'och' rub'anik li k'anjel (Q'eqchi': land and the work on it)"),
        languages=("es", "en", "kek"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public / institutional repositories",
        notes="the agrarian-conflict literature is the one that matters for supply: a highland "
              "harvest is interrupted by a land or labour dispute far more often than by weather"),
    source_class(
        "ca_open_scholarship", "OpenAlex, CORE, SciELO and Redalyc as the open citation and "
                               "full-text index for Central American scholarship",
        layer="academic",
        roots=("https://openalex.org", "https://core.ac.uk", "https://www.scielo.org",
               "https://www.redalyc.org"),
        queries=("Canal de Panamá sequía comercio mundial artículo",
                 "dolarización El Salvador Panamá comparación",
                 "café y cambio climático Corredor Seco publicación",
                 "remesas y tipo de cambio real Centroamérica"),
        languages=("es", "en", "pt"), access_label="OPEN_DATA", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="open access indexes",
        notes="the expansion edge into the academic ground: SciELO and Redalyc carry the "
              "Spanish-language journals that the English indexes do not"),
    # ---- practitioner
    source_class(
        "pa_maritime_practitioner", "The maritime operating press and the canal brokerage "
                                    "commentary: gCaptain, The Maritime Executive and Splash",
        layer="practitioner",
        roots=("https://gcaptain.com", "https://www.maritime-executive.com",
               "https://splash247.com"),
        queries=("Panama Canal transit slots auction price",
                 "restricción de calado buques en espera Canal",
                 "cola de buques fondeados Balboa Cristóbal",
                 "desvío por el cabo de Buena Esperanza días adicionales",
                 "recargo por el Canal de Panamá línea naviera"),
        languages=("en", "es"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the operating detail the ACP's own advisories do not carry: which vessel classes "
              "are waiting, what the charterers are paying and where the cargo re-routed to"),
    source_class(
        "gt_coffee_practitioner", "The coffee trade practitioner press and the regional business "
                                  "press: Perfect Daily Grind, Daily Coffee News and Revista "
                                  "Summa",
        layer="practitioner",
        roots=("https://perfectdailygrind.com/es/", "https://dailycoffeenews.com",
               "https://revistasumma.com"),
        queries=("diferencial de origen café guatemalteco SHB",
                 "cosecha de café Huehuetenango estimación",
                 "escasez de mano de obra cortadores de café",
                 "roya del café renovación de cafetales financiamiento",
                 "precio en finca quintal pergamino"),
        languages=("es", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the DIFFERENTIAL and the LABOUR constraint are where an origin's supply shows up "
              "first, and neither is in an institute's monthly export table"),
    source_class(
        "cr_practitioner", "El Financiero and the Costa Rican and Panamanian business analyst "
                           "ecology",
        layer="practitioner",
        roots=("https://www.elfinancierocr.com", "https://www.capital.com.pa"),
        queries=("proyección tipo de cambio colón MONEX analistas",
                 "tasa de política monetaria expectativa Costa Rica",
                 "inversión en zona franca perspectivas nearshoring",
                 "Centro Bancario Internacional liquidez panorama"),
        languages=("es",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free with registration for some articles",
        notes="the only genuine sell-side-adjacent commentary layer on the isthmus; it covers "
              "Costa Rica and Panama and it does NOT cover Nicaragua, which is declared"),
    source_class(
        "ca_freight_pra", "The container-freight and commodity price-reporting agencies: Drewry, "
                          "Xeneta and Freightos",
        layer="practitioner",
        roots=("https://www.drewry.co.uk/supply-chain-advisors/world-container-index",
               "https://www.xeneta.com", "https://www.freightos.com/freight-resources/"),
        queries=("índice de flete de contenedores Shanghái costa este",
                 "recargo por el Canal de Panamá tarifa naviera",
                 "world container index semanal"),
        languages=("en", "es"), access_label="LICENSED", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="subscription; terms forbid machine extraction",
        machine_use_allowed=False,
        notes="REGISTERED, NEVER SCRAPED AND NEVER OMITTED. The box rate is the channel through "
              "which the canal constraint reaches the US consumer and it is behind a paywall, so "
              "the freight leg is UNMEASURED and the physical transit count carries the claim"),
    # ---- retail_ecology
    source_class(
        "ca_retail_investor", "The retail and diaspora discussion ecology: the national "
                              "subreddits and the open expatriate and investor boards for "
                              "Panama, Costa Rica, Guatemala and El Salvador",
        layer="retail_ecology",
        roots=("https://www.reddit.com/r/Panama/", "https://www.reddit.com/r/Costa_Rica/",
               "https://www.reddit.com/r/Guatemala/", "https://www.reddit.com/r/ElSalvador/"),
        queries=("dónde cambiar dólares mejor tipo de cambio",
                 "invertir en bolsa desde Costa Rica cómo",
                 "cuenta en dólares banco panameño requisitos",
                 "qué pasó con el bitcóin en El Salvador opiniones",
                 "cómo afecta la sequía del Canal a los precios"),
        languages=("es", "en"), access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="platform terms; public threads",
        notes="KEPT AT LOW WEIGHT AND NEVER DROPPED. A retail board is where a dollarised "
              "household's inflation perception and a diaspora's remittance intention are "
              "written down before any statistic records them"),
    source_class(
        "ca_remittance_retail", "The remittance corridor as a retail market: the World Bank "
                                "Remittance Prices Worldwide series and the diaspora boards that "
                                "argue about fees",
        layer="retail_ecology",
        roots=("https://remittanceprices.worldbank.org",
               "https://www.reddit.com/r/immigration/",
               "https://www.reddit.com/r/Honduras/"),
        queries=("costo de enviar remesas a Guatemala comisión",
                 "mejor forma de mandar dinero a Honduras",
                 "remesas a Nicaragua comisión tipo de cambio",
                 "envío de dinero a El Salvador comparación"),
        languages=("es", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public (World Bank open data)",
        notes="the CORRIDOR COST is the wedge between what the US sender pays and what the "
              "isthmus receives, and it is published quarterly by corridor -- which turns a "
              "remittance series into a price series with a spread"),
    # ---- app_ecosystem
    source_class(
        "cr_bccr_api", "The BCCR's own indicator web service -- the one genuinely machine-"
                       "readable central-bank API on this isthmus",
        layer="app_ecosystem",
        roots=("https://gee.bccr.fi.cr/indicadoreseconomicos/WebServices/"
               "wsindicadoreseconomicos.asmx",
               "https://www.bccr.fi.cr/indicadores-economicos/servicio-web"),
        queries=("servicio web indicadores económicos BCCR código",
                 "API tipo de cambio MONEX consulta",
                 "descarga serie histórica tasa de política monetaria"),
        languages=("es",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public; registration for a token",
        notes="a keyed but free SOAP service over thousands of series; this is the reason Costa "
              "Rica is the pack's control jurisdiction in practice as well as in principle"),
    source_class(
        "gt_banguat_api", "Banguat's tipo de cambio and variables web services",
        layer="app_ecosystem",
        roots=("https://www.banguat.gob.gt/variables/ws/TipoCambio.asmx",
               "https://www.banguat.gob.gt/es/page/servicios-web"),
        queries=("servicio web tipo de cambio Banguat consulta",
                 "API variables económicas Banguat",
                 "descarga tipo de cambio de referencia histórico"),
        languages=("es",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the daily reference rate and its moving average come out of here, which is what "
              "makes the published participation rule exactly recomputable"),
    source_class(
        "pa_digital", "The Panamanian digital plane: the ACP's advisory feed and the Yappy "
                      "instant-payment rails that a dollarised retail economy clears on",
        layer="app_ecosystem",
        roots=("https://pancanal.com/en/advisories-to-shipping/",
               "https://www.yappy.com.pa",
               "https://www.superbancos.gob.pa/es/estadisticas/"),
        queries=("avisos a la navegación suscripción actualización",
                 "Yappy pagos instantáneos Panamá estadísticas",
                 "sistema de pagos de Panamá compensación"),
        languages=("es", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="a dollarised economy has no monetary aggregate of its own, so the PAYMENT rails "
              "are the closest thing to a velocity observable Panama has"),
    # ---- media
    source_class(
        "pa_media", "La Prensa, La Estrella de Panama and TVN: the canal, the mine and the "
                    "banking centre as they are reported at home",
        layer="media",
        roots=("https://www.prensa.com", "https://www.laestrella.com.pa",
               "https://www.tvn-2.com"),
        queries=("Canal de Panamá restricción de calado noticia",
                 "Cobre Panamá cierre de la mina protesta",
                 "Corte Suprema Ley 406 inconstitucional fallo",
                 "Zona Libre de Colón reexportaciones caída",
                 "Centro Bancario Internacional lista gris GAFI"),
        languages=("es",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free with limits; some articles metered",
        notes="the domestic account of the two events that define this pack's Panamanian half: "
              "the drought and the mine"),
    source_class(
        "gt_media", "Prensa Libre, Soy502, Plaza Publica and elPeriodico -- the last of which is "
                    "an ARCHIVE and no longer a live ground",
        layer="media",
        roots=("https://www.prensalibre.com", "https://www.soy502.com",
               "https://www.plazapublica.com.gt", "https://elperiodico.com.gt"),
        queries=("exportaciones de café Guatemala temporada noticia",
                 "zafra ingenios azucareros molienda récord",
                 "Junta Monetaria tasa líder decisión",
                 "bloqueo de carretera comunidades Totonicapán",
                 "remesas familiares récord Guatemala"),
        languages=("es",), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="ELPERIODICO CLOSED IN MAY 2023 after its founder's imprisonment. It is kept here "
              "because its archive is a decade of investigative record on exactly the "
              "concessions and customs cases this pack cares about -- see NO_LAWFUL_GROUND, "
              "which declares the live ground gone and names the archive as the substitute"),
    source_class(
        "gt_mayan_media", "The Mayan-language and community press of the Guatemalan highlands: "
                          "Prensa Comunitaria, the Centro de Medios Independientes and Nomada",
        layer="media",
        roots=("https://www.prensacomunitaria.org", "https://cmiguate.org",
               "https://nomada.gt"),
        queries=("comunidad k'iche' asamblea tierra conflicto",
                 "48 Cantones Totonicapán paro comunitario",
                 "ulew ri komon (K'iche': the community's land)",
                 "ch'och' li tenamit (Q'eqchi': the town's land)",
                 "samaj pa ruwach'ulew (Kaqchikel: work on the land)",
                 "despojo de tierras Alta Verapaz denuncia",
                 "cortadores de café salario protesta finca"),
        languages=("es", "quc", "kek", "cak"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public / Creative Commons on some items",
        notes="THE GROUND THE SPANISH PRESS REPORTS SECOND-HAND. A highland harvest is "
              "interrupted by a land or labour dispute decided in a community assembly held in "
              "K'iche' or Q'eqchi', and this is where that decision is written down first"),
    source_class(
        "hn_media", "La Prensa, El Heraldo and Criterio: the maquila, the coffee and the "
                    "lempira auction at home",
        layer="media",
        roots=("https://www.laprensa.hn", "https://www.elheraldo.hn", "https://criterio.hn"),
        queries=("subasta de divisas BCH escasez de dólares",
                 "exportaciones de café Honduras IHCAFE cierre de cosecha",
                 "maquila empleo Puerto Cortés exportación",
                 "Feriado Morazánico fechas asueto",
                 "remesas familiares Honduras récord mensual"),
        languages=("es",), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the dollar QUEUE is reported here long before it appears in a published series, "
              "which is the fast half of the lempira mechanism"),
    source_class(
        "cr_media", "La Nacion, Semanario Universidad and Delfino: the control jurisdiction's "
                    "own record",
        layer="media",
        roots=("https://www.nacion.com", "https://semanariouniversidad.com",
               "https://delfino.cr"),
        queries=("tipo de cambio MONEX colón apreciación",
                 "regla fiscal recorte presupuesto discusión",
                 "zona franca dispositivos médicos nueva inversión",
                 "exportaciones de café ICAFE liquidación",
                 "traslado de feriados al lunes ley"),
        languages=("es",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free with limits; Semanario is open",
        notes="Semanario Universidad is the investigative half and Delfino carries the "
              "legislative record; together they date the fiscal-consolidation steps"),
    source_class(
        "ni_media", "The Nicaraguan independent press IN EXILE: Confidencial, La Prensa, "
                    "Divergentes and Articulo 66",
        layer="media",
        roots=("https://confidencial.digital", "https://www.laprensani.com",
               "https://www.divergentes.com", "https://www.articulo66.com"),
        queries=("deslizamiento cambiario cero córdoba análisis",
                 "exportaciones de oro Nicaragua concesión minera",
                 "remesas Nicaragua récord migración",
                 "estadísticas oficiales Nicaragua opacidad",
                 "cosecha de café Nicaragua exportación"),
        languages=("es",), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="EVERY ONE OF THESE OUTLETS OPERATES FROM OUTSIDE THE COUNTRY. They are kept, "
              "labelled RELIABLE and read with the exile condition attached: their access to "
              "domestic primary documents is worse than a domestic outlet's would be and their "
              "independence is better. NO_LAWFUL_GROUND declares the domestic ground gone"),
    source_class(
        "sv_media", "El Faro, La Prensa Grafica and El Diario de Hoy: the bitcoin, the fiscal "
                    "programme and the credit story",
        layer="media",
        roots=("https://elfaro.net", "https://www.laprensagrafica.com",
               "https://www.elsalvador.com"),
        queries=("Ley Bitcoin reforma curso legal voluntario",
                 "acuerdo con el FMI condiciones bitcóin",
                 "eurobono recompra riesgo país El Salvador",
                 "remesas El Salvador mensual récord",
                 "exportaciones de maquila El Salvador"),
        languages=("es", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="EL FARO RELOCATED ITS ADMINISTRATIVE OPERATION OUT OF THE COUNTRY in 2023, which "
              "is a press-condition fact carried with the source rather than a credibility one"),
    # ---- archive
    source_class(
        "ca_gazettes", "The six gazettes of record: Gaceta Oficial de Panama, Diario de Centro "
                       "America, La Gaceta (Honduras), La Gaceta (Costa Rica), La Gaceta "
                       "(Nicaragua) and the Diario Oficial de El Salvador",
        layer="archive",
        roots=("https://www.gacetaoficial.gob.pa", "https://dca.gob.gt",
               "https://www.imprentanacional.go.cr", "https://www.diariooficial.gob.sv",
               "http://www.lagaceta.gob.ni"),
        queries=("Gaceta Oficial decreto ejecutivo búsqueda",
                 "Diario de Centro América acuerdo gubernativo",
                 "La Gaceta ley de traslado de feriados",
                 "Diario Oficial decreto legislativo El Salvador",
                 "publicación de la resolución contrato de concesión"),
        languages=("es",), access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE ONLY WAY A PRESS_REPORTED DATE IN THIS PACK BECOMES PROMOTABLE. Ley 406, the "
              "Supreme Court ruling, the Feriado Morazanico decree, the Ley de Traslado and the "
              "Bitcoin Law amendments are all gazetted acts with numbers and dates"),
    source_class(
        "ca_web_archive", "The Internet Archive as the only vintage of the pages that overwrite "
                          "themselves -- the ACP advisories, the ministries' statistics pages "
                          "and the closed elPeriodico",
        layer="archive",
        roots=("https://web.archive.org/web/*/pancanal.com/*",
               "https://web.archive.org/web/*/elperiodico.com.gt/*",
               "https://web.archive.org/web/*/banguat.gob.gt/*"),
        queries=("archivo aviso a la navegación calado histórico",
                 "elPeriódico archivo investigación aduanas",
                 "nivel del lago Gatún serie histórica archivada",
                 "boletín estadístico archivado ministerio"),
        languages=("es", "en"), access_label="PUBLIC_ARCHIVE", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="Internet Archive terms",
        notes="ACCESS_CONSTRAINTS says the ACP supersedes advisories in place; this row is the "
              "consequence, and without it every canal cell is NOT_PIT_SAFE by construction"),
    # ---- physical_economy
    source_class(
        "pa_ports_physical", "The physical isthmus: ACP lake levels and transit counts, the "
                             "Autoridad Maritima's registry, the Colon Free Zone and the "
                             "Balboa and Cristobal terminals",
        layer="physical_economy",
        roots=("https://pancanal.com/en/lake-levels/", "https://amp.gob.pa",
               "https://www.zonalibredecolon.com.pa",
               "https://www.contraloria.gob.pa/inec/"),
        queries=("movimiento de carga puerto de Balboa contenedores",
                 "reexportaciones Zona Libre de Colón mensual",
                 "flota abanderada en Panamá tonelaje registrado",
                 "nivel del lago Gatún precipitación cuenca",
                 "buques en espera fondeadero Cristóbal"),
        languages=("es", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE LARGEST FLAG STATE AND THE LARGEST FREE ZONE IN THE AMERICAS, both publishing "
              "monthly. The free zone's re-exports lead its customers' own import prints"),
    source_class(
        "ca_agroclimate", "The meteorological and agro-climatic services: INSIVUMEH, the "
                          "Instituto Meteorologico Nacional, INETER, COPECO, MARN and FEWS NET "
                          "for the dry corridor",
        layer="physical_economy",
        roots=("https://insivumeh.gob.gt", "https://www.imn.ac.cr", "https://www.ineter.gob.ni",
               "https://www.copeco.gob.hn", "https://fews.net/es/central-america"),
        queries=("pronóstico de lluvia Corredor Seco boletín",
                 "canícula prolongada pérdida de granos básicos",
                 "alerta agroclimática café floración",
                 "temporada de huracanes alerta Honduras",
                 "déficit de precipitación cuenca del Canal",
                 "ha' xaq maak' (Q'eqchi': there is little water)"),
        languages=("es", "en", "kek"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="FEWS NET publishes a dated, machine-readable food-security and rainfall "
              "assessment for the dry corridor; it is the closest thing to a published "
              "agricultural-risk series this region has and it leads the harvest by months"),
    source_class(
        "ca_commodity_physical", "The world physical counters the isthmus reports into: the ICO "
                                 "certified stocks, USDA FAS, the World Bank Pink Sheet, UN "
                                 "Comtrade and the USGS copper record",
        layer="physical_economy",
        roots=("https://www.ico.org/trade_statistics.asp", "https://fas.usda.gov/data",
               "https://www.worldbank.org/en/research/commodity-markets",
               "https://comtradeplus.un.org",
               "https://www.usgs.gov/centers/national-minerals-information-center"),
        queries=("USDA FAS GAIN report coffee semi-annual Guatemala",
                 "exportaciones de azúcar Centroamérica Comtrade",
                 "producción mundial de cobre mina estadística",
                 "Pink Sheet precios mensuales de materias primas",
                 "certified stocks arabica warehouses"),
        languages=("en", "es"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public / public domain (US government work)",
        notes="MIRROR CUSTOMS LIVES HERE. Where a national series has narrowed, the PARTNERS' "
              "import declarations in Comtrade reconstruct the export the origin did not "
              "publish -- which is the lawful substitute NO_LAWFUL_GROUND names for Nicaragua"),
    # ---- source_graph
    source_class(
        "ca_citation_graph", "What the other nine layers cite, follow and argue with: the "
                             "attribution phrases that name a primary source inside a secondary "
                             "one, indexed through EFE, Google News and OpenAlex",
        layer="source_graph",
        roots=("https://www.efe.com/efe/america/", "https://news.google.com",
               "https://openalex.org"),
        queries=("según la ACP el calado máximo autorizado",
                 "de acuerdo con ANACAFE las exportaciones",
                 "cifras del Banco Central de Honduras muestran",
                 "según la Defensoría el bloqueo continúa",
                 "trascendió que la minera evalúa",
                 "komon xkib'ij chi (K'iche': the community said that)"),
        languages=("es", "en", "quc"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the expansion edge: an attribution phrase is how a crawler finds the primary "
              "series a story was built on, which is how this pack's source list grows without "
              "anybody typing a new root"),
    source_class(
        "ca_wire_licensed", "The international wires that carry the isthmus to the market: "
                            "Reuters, Bloomberg and the Associated Press",
        layer="source_graph",
        roots=("https://www.reuters.com/world/americas/",
               "https://www.bloomberg.com/latin-america", "https://apnews.com/hub/panama"),
        queries=("Panama Canal drought transits Reuters",
                 "Cobre Panama mine closure copper supply",
                 "El Salvador bond rally bitcoin IMF"),
        languages=("en", "es"), access_label="LICENSED", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="subscription; terms forbid machine extraction",
        machine_use_allowed=False,
        notes="REGISTERED, NEVER SCRAPED AND NEVER OMITTED. The wires are how the market LEARNS "
              "an isthmus fact and their timestamps are the honest event minute; the desk reads "
              "the primary source instead and records that the wire is the transmission"),
)

#: ALL TEN LAYERS CARRY A REAL SOURCE FOR THIS ISTHMUS and none is declared absent at the PACK
#: level. That is a MEASUREMENT and not a boast: six countries between them have a chokepoint
#: operator that publishes daily, five coffee institutes that count every bag, four central
#: banks, six gazettes, a Mayan-language community press and an open citation graph. THE
#: ABSENCES HERE ARE PER-JURISDICTION AND PER-OBJECT, and they are declared in
#: `NO_LAWFUL_GROUND` -- which is the sharper measurement, because "the pack has a practitioner
#: layer" and "Nicaragua has a practitioner layer" are different claims and only one is true.
LAYER_ABSENCES: dict[str, str] = {}

#: THE LAYERS EVERY JURISDICTION OWES. The pack does not claim to have swept all sixty
#: jurisdiction-by-layer cells; it claims to have swept these two for each of the six, and
#: `jurisdiction_gaps()` is the check that says so.
REQUIRED_PER_JURISDICTION: tuple[str, ...] = ("official", "media")

#: WHERE A LAYER OR AN OBJECT GENUINELY DOES NOT EXIST, DECLARED WITH ITS LAWFUL SUBSTITUTE.
#: This is the measured refusal the depth rule asks for, and it is worth more than a padded row:
#: PANAMA HAS NO CENTRAL BANK, which is not a gap in the data but a fact about the country; EL
#: SALVADOR HAS A CENTRAL BANK WITH NO INSTRUMENT; NICARAGUA'S INDEPENDENT PRESS OPERATES FROM
#: OUTSIDE THE COUNTRY and its statistical publication has narrowed. Rows are
#: {jurisdiction, kind, what, reason, substitute, status} and `kind` is "layer" or "object".
#: Every "layer" row is CHECKED by the tests against the actual source count, so a declaration
#: here cannot be decorative.
NO_LAWFUL_GROUND: tuple[dict[str, str], ...] = (
    {"jurisdiction": "pa", "kind": "object", "what": "a central bank, and therefore a policy "
                                                     "rate, monetary aggregates and FX reserves",
     "reason": "PANAMA HAS NO CENTRAL BANK AND HAS NOT HAD ONE SINCE 1904. There is no monetary "
               "authority to publish a policy rate, no reserve series because there are no "
               "reserves to hold, no open-market operation and no lender of last resort. This "
               "is the defining institutional fact of the country and it is recorded here as a "
               "FACT ABOUT THE COUNTRY rather than as a hole in the pack's coverage",
     "substitute": "the Superintendencia de Bancos publishes the Centro Bancario "
                   "Internacional's balance sheet, liquidity ratio and deposit base monthly, "
                   "which IS Panama's monetary statistics; the Contraloria General (INEC) "
                   "publishes prices and activity; and the FEDERAL OPEN MARKET COMMITTEE'S OWN "
                   "DECISIONS are Panama's policy-rate series, imported whole",
     "status": "STRUCTURAL, declared"},
    {"jurisdiction": "sv", "kind": "object",
     "what": "a monetary policy instrument of any kind",
     "reason": "the Banco Central de Reserva exists, supervises and publishes, and has had NO "
               "monetary instrument since the Ley de Integracion Monetaria took effect on "
               "2001-01-01. A study that looks for a Salvadoran policy surprise is looking for "
               "an object that was legislated out of existence",
     "substitute": "the FOMC is El Salvador's monetary policy; the fiscal and credit series -- "
                   "the Ministerio de Hacienda's debt record, the eurobond spread and the IMF "
                   "programme reviews -- carry everything a rate series would have carried",
     "status": "STRUCTURAL since 2001-01-01, declared"},
    {"jurisdiction": "ni", "kind": "object",
     "what": "a domestic independent press operating inside the country",
     "reason": "the independent outlets were closed, confiscated or forced out and every one of "
               "them now publishes FROM EXILE; domestic statistical publication has narrowed "
               "alongside it, with INIDE's series thinner and less frequent than its "
               "neighbours'. Declaring this is the measurement: a crawl that finds Nicaraguan "
               "coverage and does not know it was written from San Jose or Madrid will "
               "mis-weight both its independence and its access",
     "substitute": "Confidencial, La Prensa, Divergentes and Articulo 66 are KEPT and labelled "
                   "with the exile condition; the BCN's own monthly external-sector series is "
                   "still published and still usable; the IMF Article IV is the outside audit; "
                   "and MIRROR CUSTOMS through UN Comtrade and SIECA reconstructs the trade the "
                   "country does not publish, from what its partners declare",
     "status": "MEASURED and declared"},
    {"jurisdiction": "ni", "kind": "layer", "what": "practitioner",
     "reason": "no domestic sell-side, analyst or trade-practitioner layer survives inside "
               "Nicaragua; the regional business press that covers Costa Rica and Panama does "
               "not cover it, and what commentary exists is written by the exile outlets' "
               "economics desks and is already carried under `media`",
     "substitute": "the exile outlets' economics coverage, the IMF Article IV staff report, "
                   "BCIE and SIECA reporting, and the regional coffee and gold trade press",
     "status": "MEASURED: zero practitioner sources for ni, and declared"},
    {"jurisdiction": "hn", "kind": "layer", "what": "app_ecosystem",
     "reason": "neither the Banco Central de Honduras nor the Instituto Nacional de Estadistica "
               "exposes a machine-readable API; both publish XLS and PDF over links that are "
               "overwritten, so there is no application ecosystem to crawl",
     "substitute": "the BCH's own XLS endpoints fetched and versioned by the collector, plus "
                   "the World Bank and IMF mirrors of the same series where a vintage matters",
     "status": "MEASURED: zero app_ecosystem sources for hn, and declared"},
    {"jurisdiction": "sv", "kind": "layer", "what": "app_ecosystem",
     "reason": "the BCR publishes through a portal rather than an API and the ONEC's series "
               "come as spreadsheets; there is no Salvadoran data-application layer to read",
     "substitute": "the BCR portal's own download endpoints, plus the IMF and World Bank "
                   "mirrors; the remittance series is the one that matters and it is published "
                   "on a fixed monthly schedule",
     "status": "MEASURED: zero app_ecosystem sources for sv, and declared"},
    {"jurisdiction": "ni", "kind": "layer", "what": "app_ecosystem",
     "reason": "the BCN publishes PDFs and spreadsheets and exposes no API; this compounds the "
               "narrowing already declared above",
     "substitute": "the BCN's own published files, mirror customs through Comtrade and SIECA, "
                   "and the IMF Article IV",
     "status": "MEASURED: zero app_ecosystem sources for ni, and declared"},
    {"jurisdiction": "gt", "kind": "object",
     "what": "elPeriodico as a LIVE investigative ground",
     "reason": "the outlet closed in May 2023 after its founder's imprisonment. Its decade of "
               "investigative record on customs, concessions and public contracting is exactly "
               "the material this pack's Guatemalan half needs, and it stops on a date",
     "substitute": "the elPeriodico archive through the Internet Archive, plus Plaza Publica, "
                   "Prensa Comunitaria and the Centro de Medios Independientes as the live "
                   "investigative grounds that continue",
     "status": "DATED BREAK, declared: live ground gone from 2023-05, archive retained"},
)


def layer_counts(classes: Iterable[Mapping[str, Any]] | None = None) -> dict[str, int]:
    rows = SOURCE_CLASSES if classes is None else classes
    out = dict.fromkeys(SOURCE_LAYERS, 0)
    for sc in rows:
        layer = str(sc.get("layer") or "")
        if layer in out and not str(sc.get("id") or "").startswith("absent_"):
            out[layer] += 1
    return out


def jurisdiction_of(sid: str) -> str:
    """Which jurisdiction a source id belongs to, from its prefix. A source that is not prefixed
    with one of the six ISO-2 codes is REGIONAL and is filed under `ca` -- which is a real
    category here rather than a fallback, because SIECA, the BCIE and the coffee institutes'
    joint record genuinely belong to the isthmus and not to any one country."""
    head = str(sid).split("_", 1)[0].lower()
    return head if head in JURISDICTIONS else "ca"


def jurisdiction_layer_counts(cc: str) -> dict[str, int]:
    """One jurisdiction's own source count per layer. Regional sources are NOT counted into a
    country: a claim that Nicaragua has a practitioner layer must be supported by a Nicaraguan
    source, not by a regional one that happens to mention it."""
    code = str(cc).lower()
    out = dict.fromkeys(SOURCE_LAYERS, 0)
    for sc in SOURCE_CLASSES:
        sid = str(sc.get("id") or "")
        if sid.startswith("absent_") or jurisdiction_of(sid) != code:
            continue
        layer = str(sc.get("layer") or "")
        if layer in out:
            out[layer] += 1
    return out


def declared_absent_layers(cc: str) -> tuple[str, ...]:
    """The layers this pack has DECLARED absent for one jurisdiction, with a reason on file."""
    code = str(cc).lower()
    return tuple(str(row["what"]) for row in NO_LAWFUL_GROUND
                 if row["kind"] == "layer" and row["jurisdiction"] == code)


def jurisdiction_gaps() -> list[tuple[str, str]]:
    """Every (jurisdiction, layer) pair in `REQUIRED_PER_JURISDICTION` with no source of its own
    and no declared absence. This list must be EMPTY: the pack owes every one of its six
    countries an official ground and a media ground in that country's own press."""
    out: list[tuple[str, str]] = []
    for cc in JURISDICTIONS:
        counts = jurisdiction_layer_counts(cc)
        declared = set(declared_absent_layers(cc))
        for layer in REQUIRED_PER_JURISDICTION:
            if not counts[layer] and layer not in declared:
                out.append((cc, layer))
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
    return {k: tuple(v) for k, v in out.items()}


def source_layer_coverage() -> dict[str, Any]:
    counts = layer_counts()
    missing = {layer: str(LAYER_ABSENCES.get(layer, "")) for layer, n in counts.items() if not n}
    return {"code": CODE, "layer_counts": counts,
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
            "jurisdiction_gaps": jurisdiction_gaps(),
            "declared_absences": len(NO_LAWFUL_GROUND),
            "rule": "ten layers, each carrying a source or named ABSENT with a reason; every "
                    "jurisdiction owes an official and a media ground OF ITS OWN or a declared "
                    "absence with a lawful substitute; fringe and contradicted PUBLIC material "
                    "is kept as a low-weight evidence object and never dropped; a page whose "
                    "terms forbid machine extraction is registered machine_use_allowed=false, "
                    "never scraped and never omitted"}


#: NATIVE QUERY TERRITORIES -- what the deep-forest miner actually types, per layer, in the
#: languages of the ground. Three or more for every one of the ten layers, and the layers that
#: touch the Guatemalan highlands carry K'iche', Q'eqchi' and Kaqchikel because that is the
#: language the harvest-interrupting decision is taken in.
QUERY_TERRITORIES: dict[str, tuple[str, ...]] = {
    "official": ("aviso a la navegación calado máximo autorizado ACP",
                 "subasta de cupos de tránsito precio de cierre",
                 "nivel del lago Gatún pies PLD histórico",
                 "regla de participación cambiaria Banguat resolución",
                 "subasta de divisas BCH monto ofertado demandado",
                 "deslizamiento cambiario córdoba BCN resolución",
                 "remesas familiares mensual banco central",
                 "Centro Bancario Internacional Superintendencia estadísticas"),
    "institutional": ("exportaciones de café mensual quintales ANACAFE IHCAFE",
                      "liquidación del café ICAFE precio al productor",
                      "zafra molienda ingenios ASAZGUA informe",
                      "comercio intrarregional SIECA estadísticas",
                      "BCIE aprobación de préstamo soberano",
                      "indicador compuesto OIC precio del café"),
    "academic": ("dolarización economía pequeña abierta evidencia Centroamérica",
                 "remesas y consumo elasticidad Guatemala Honduras estudio",
                 "roya del café impacto productividad investigación",
                 "conflictividad agraria tierra Alta Verapaz tesis",
                 "regla fiscal Costa Rica evaluación empírica",
                 "ch'och' ut k'anjel (Q'eqchi': land and work, the two words a "
                 "highland labour study is written around)"),
    "practitioner": ("cola de buques fondeados Canal de Panamá análisis",
                     "diferencial de origen café guatemalteco SHB comentario",
                     "proyección del tipo de cambio colón MONEX analistas",
                     "recargo por el Canal de Panamá línea naviera tarifa",
                     "escasez de mano de obra cortadores de café finca"),
    "retail_ecology": ("dónde cambiar dólares mejor tipo de cambio hoy",
                       "cómo mandar remesas más barato comisión",
                       "invertir desde Centroamérica foro principiantes",
                       "qué pasó con el bitcóin en El Salvador opiniones",
                       "cuenta en dólares banco panameño requisitos"),
    "app_ecosystem": ("servicio web indicadores económicos BCCR código",
                      "API tipo de cambio Banguat consulta",
                      "Yappy SINPE Móvil pagos instantáneos estadísticas",
                      "suscripción avisos a la navegación ACP",
                      "descarga serie histórica tasa de política monetaria"),
    "media": ("Cobre Panamá cierre de la mina fallo de la Corte",
              "restricción de calado del Canal noticia",
              "Feriado Morazánico fechas asueto Honduras",
              "48 Cantones Totonicapán paro comunitario",
              "ulew ri komon (K'iche': the community's land)",
              "ch'och' li tenamit (Q'eqchi': the town's land)",
              "samaj pa ruwach'ulew (Kaqchikel: work on the land)",
              "deslizamiento cero córdoba análisis exilio"),
    "archive": ("Gaceta Oficial Ley 406 contrato minero publicación",
                "Diario de Centro América acuerdo gubernativo asueto",
                "La Gaceta ley de traslado de feriados texto",
                "archivo elPeriódico investigación aduanas",
                "aviso a la navegación archivado calado histórico"),
    "physical_economy": ("movimiento de carga puerto de Balboa contenedores",
                         "reexportaciones Zona Libre de Colón mensual",
                         "pronóstico de lluvia Corredor Seco boletín FEWS",
                         "canícula prolongada pérdida de granos básicos",
                         "flota abanderada en Panamá tonelaje registrado",
                         "ha' xaq maak' (Q'eqchi': there is little water)",
                         "USDA FAS GAIN coffee semi-annual Guatemala Honduras"),
    "source_graph": ("según la ACP el calado máximo autorizado será",
                     "de acuerdo con ANACAFE las exportaciones de café",
                     "cifras del Banco Central de Honduras muestran que",
                     "citando a dirigentes comunitarios de Totonicapán",
                     "komon xkib'ij chi (K'iche': the community said that)"),
}

# --------------------------------------------------------------------------- datasets
#: TWENTY-TWO CATALOGUE ENTRIES spread across the ten layers and the six jurisdictions. Every row
#: carries the twelve fields the data-discovery swarm needs and a `how_to_fetch` a collector can
#: act on without asking a human. `pit_feasible` is the field the catalogue exists for: a series
#: whose vintage cannot be reconstructed can only ever produce NOT_PIT_SAFE cells, and saying so
#: is the measurement. THE ACP ROWS ARE NOT PIT-FEASIBLE AS PUBLISHED, which is why the archive
#: layer is not decoration in this pack.
DATASETS: tuple[dict[str, Any], ...] = (
    {"name": "ACP advisories to shipping: maximum authorised draft and booking-slot changes",
     "source": "Autoridad del Canal de Panama",
     "coverage": "the advisory series runs for decades; the drought episode is 2023-05 onward",
     "frequency": "irregular, on every change, with a stated effective date",
     "publication_lag_days": 0.0,
     "revisions": "an advisory is superseded by the next one at the same URL and the old text is "
                  "removed; there is no revision record",
     "licence": "free, public", "history_from": "2023-05", "pit_feasible": False,
     "assets": ("CORN", "SOYBEAN", "WHEAT", "XNGUSD", "XTIUSD"),
     "mechanism_families": ("physical_supply", "logistics_regime", "release_surprise"),
     "how_to_fetch": "crawl pancanal.com/en/advisories-to-shipping/ on a daily cadence and diff "
                     "the list; parse the advisory number, the issue date, the EFFECTIVE date "
                     "and the draft in feet TFW. NOT PIT-SAFE as published because advisories "
                     "supersede in place -- the Internet Archive crawls are the only vintage"},
    {"name": "ACP daily Gatun and Alhajuela lake levels",
     "source": "Autoridad del Canal de Panama",
     "coverage": "daily, multi-decade", "frequency": "daily", "publication_lag_days": 0.0,
     "revisions": "readings are not revised; the historical file is republished whole",
     "licence": "free, public", "history_from": "2000-01", "pit_feasible": False,
     "assets": ("CORN", "SOYBEAN", "XNGUSD"),
     "mechanism_families": ("physical_supply", "weather_state"),
     "how_to_fetch": "pancanal.com/en/lake-levels/ daily; the level is published in feet PLD "
                     "against the 87.5 ft operating maximum. THE LEADING INPUT: the lake falls "
                     "for months before an advisory cuts the draft"},
    {"name": "ACP bookable transit slots and daily transit counts",
     "source": "Autoridad del Canal de Panama canal statistics and advisories",
     "coverage": "2016-06 onward at Neopanamax granularity", "frequency": "daily and monthly",
     "publication_lag_days": 1.0,
     "revisions": "the monthly statistical tables restate provisional daily counts",
     "licence": "free, public", "history_from": "2016-06", "pit_feasible": False,
     "assets": ("CORN", "SOYBEAN", "WHEAT", "XTIUSD", "XBRUSD", "XNGUSD"),
     "mechanism_families": ("physical_supply", "logistics_regime"),
     "how_to_fetch": "join the advisory series to pancanal.com/en/canal-statistics/; this pack's "
                     "`SLOT_STEPS` is the assembled step function and every step is "
                     "PRESS_REPORTED until its advisory number is attached"},
    {"name": "ACP transit reservation auction clearing prices",
     "source": "Autoridad del Canal de Panama and the maritime trade press",
     "coverage": "2023-08 onward for the episode this pack carries",
     "frequency": "irregular, per auction", "publication_lag_days": 2.0,
     "revisions": "assembled from reporting rather than published as a series",
     "licence": "free, public", "history_from": "2023-08", "pit_feasible": False,
     "assets": ("XNGUSD", "XTIUSD", "CORN", "SOYBEAN"),
     "mechanism_families": ("scarcity_price", "logistics_regime"),
     "how_to_fetch": "the ACP reservation pages plus gcaptain, Splash and The Maritime "
                     "Executive; every row in `AUCTION_PRINTS` is PRESS_REPORTED and none may "
                     "be promoted until the ACP's own result notice is attached"},
    {"name": "IMF PortWatch daily chokepoint transit counts: Panama, Suez and Bab el-Mandeb",
     "source": "International Monetary Fund PortWatch",
     "coverage": "2019 onward, daily, all three chokepoints on one definition",
     "frequency": "daily", "publication_lag_days": 2.0,
     "revisions": "vessel-tracking estimates are revised as tracks are resolved",
     "licence": "free, public (IMF open data)", "history_from": "2019-01", "pit_feasible": True,
     "assets": ("XBRUSD", "XTIUSD", "XNGUSD", "US500", "CORN"),
     "mechanism_families": ("logistics_regime", "substitution"),
     "how_to_fetch": "portwatch.imf.org exposes the chokepoint daily transit layers as a "
                     "downloadable series; THIS IS THE CONTROL DATASET -- a Panama constraint "
                     "cell without the Suez and Bab el-Mandeb series beside it is measuring "
                     "global freight and calling it Panama"},
    {"name": "ANACAFE monthly coffee export volumes with the regional origin split",
     "source": "Asociacion Nacional del Cafe (Guatemala)",
     "coverage": "multi-decade on the October-September harvest year",
     "frequency": "monthly", "publication_lag_days": 20.0,
     "revisions": "the prior month is restated when late export permits clear",
     "licence": "free, public", "history_from": "2000-10", "pit_feasible": False,
     "assets": ("COFARA", "COFROB"),
     "mechanism_families": ("physical_supply", "seasonal_crop", "release_surprise"),
     "how_to_fetch": "anacafe.org/estadisticas/ monthly bulletins; ANACAFE ISSUES THE EXPORT "
                     "PERMIT so the number is a count, not a survey. Key the series on the "
                     "HARVEST YEAR (`coffee_harvest_year`), never on the calendar year"},
    {"name": "IHCAFE monthly export volumes and harvest-year accumulation (Honduras)",
     "source": "Instituto Hondureno del Cafe",
     "coverage": "multi-decade", "frequency": "monthly", "publication_lag_days": 20.0,
     "revisions": "restated as permits clear", "licence": "free, public",
     "history_from": "2000-10", "pit_feasible": False,
     "assets": ("COFARA", "COFROB"),
     "mechanism_families": ("physical_supply", "seasonal_crop"),
     "how_to_fetch": "ihcafe.hn statistics section plus the BCH's external-sector tables as a "
                     "cross-check; Honduras is the largest of the five origins by volume"},
    {"name": "ICAFE monthly exports AND the administered liquidation price (Costa Rica)",
     "source": "Instituto del Cafe de Costa Rica",
     "coverage": "multi-decade", "frequency": "monthly, with an annual liquidation",
     "publication_lag_days": 25.0,
     "revisions": "the liquidation is settled after the crop year closes",
     "licence": "free, public", "history_from": "2000-10", "pit_feasible": False,
     "assets": ("COFARA",),
     "mechanism_families": ("physical_supply", "administered_price", "seasonal_crop"),
     "how_to_fetch": "icafe.cr statistics; COSTA RICA IS UNIQUE -- the pass-through from the "
                     "exchange price to the farm gate is PUBLISHED here as a legally "
                     "administered liquidation formula and is an inference everywhere else"},
    {"name": "BCN coffee and gold export volumes and values (Nicaragua)",
     "source": "Banco Central de Nicaragua external-sector statistics",
     "coverage": "multi-decade", "frequency": "monthly", "publication_lag_days": 30.0,
     "revisions": "quarterly restatement", "licence": "free, public",
     "history_from": "2000-01", "pit_feasible": False,
     "assets": ("COFARA", "XAUUSD"),
     "mechanism_families": ("physical_supply", "seasonal_crop"),
     "how_to_fetch": "bcn.gob.ni/sector-externo monthly tables; where the domestic series is "
                     "thin, RECONSTRUCT FROM MIRROR CUSTOMS -- the partners' import "
                     "declarations in UN Comtrade -- and say which of the two was used"},
    {"name": "Consejo Salvadoreno del Cafe monthly exports",
     "source": "Consejo Salvadoreno del Cafe",
     "coverage": "multi-decade", "frequency": "monthly", "publication_lag_days": 25.0,
     "revisions": "restated as permits clear", "licence": "free, public",
     "history_from": "2000-10", "pit_feasible": False,
     "assets": ("COFARA",),
     "mechanism_families": ("physical_supply", "seasonal_crop"),
     "how_to_fetch": "consejocafe.org statistics; the smallest of the five and the cleanest "
                     "illustration of what a rust epidemic does to an origin over a decade"},
    {"name": "ICO composite indicator, group indicators and certified stocks",
     "source": "International Coffee Organization",
     "coverage": "1990 onward", "frequency": "daily indicator, monthly report",
     "publication_lag_days": 1.0,
     "revisions": "monthly report revises the prior month's trade estimates",
     "licence": "free, public", "history_from": "1990-01", "pit_feasible": True,
     "assets": ("COFARA", "COFROB"),
     "mechanism_families": ("price_benchmark", "substitution"),
     "how_to_fetch": "ico.org trade statistics and the daily composite; the OTHER MILDS group "
                     "indicator is the one that tracks this belt, and the difference between it "
                     "and the Brazilian naturals indicator IS the substitution observable"},
    {"name": "Monthly family remittances for Guatemala, Honduras, El Salvador and Nicaragua",
     "source": "Banco de Guatemala, Banco Central de Honduras, Banco Central de Reserva and "
               "Banco Central de Nicaragua",
     "coverage": "2000 onward for all four", "frequency": "monthly",
     "publication_lag_days": 12.0,
     "revisions": "small monthly restatements; the annual total is revised once",
     "licence": "free, public", "history_from": "2000-01", "pit_feasible": True,
     "assets": ("USDMXN", "US500", "US30"),
     "mechanism_families": ("cross_border_flow", "release_surprise", "policy_reaction_function"),
     "how_to_fetch": "each bank's own remittance page (Banguat publishes within days, the BCN "
                     "within weeks); THE FOUR LAGS DIFFER, so a regional aggregate built at one "
                     "date mixes vintages and must be assembled per country with its own lag"},
    {"name": "Banguat daily reference rate, moving average and FX participation",
     "source": "Banco de Guatemala", "coverage": "2000 onward", "frequency": "daily",
     "publication_lag_days": 0.0, "revisions": "never revised", "licence": "free, public",
     "history_from": "2000-01", "pit_feasible": True,
     "assets": ("USDMXN", "USDBRL", "COFARA"),
     "mechanism_families": ("intervention", "policy_reaction_function"),
     "how_to_fetch": "the Banguat TipoCambio web service at banguat.gob.gt/variables/ws/; the "
                     "PARTICIPATION RULE is arithmetic on this series, so the trigger can be "
                     "recomputed exactly for any historical day inside the rule's own window"},
    {"name": "BCH daily FX allocation auction: amount offered, amount bid and the base price",
     "source": "Banco Central de Honduras", "coverage": "2010 onward", "frequency": "daily",
     "publication_lag_days": 1.0, "revisions": "settled auctions are not revised",
     "licence": "free, public", "history_from": "2010-01", "pit_feasible": True,
     "assets": ("USDMXN", "COFARA", "COTTON"),
     "mechanism_families": ("rationing", "policy_reaction_function"),
     "how_to_fetch": "bch.hn external-sector tables; the SHORTAGE is amount bid minus amount "
                     "offered and it CUMULATES into the following days -- differencing it "
                     "destroys the only variable in the series worth having"},
    {"name": "BCCR indicator web service: the TPM, MONEX rate and volume, and participation",
     "source": "Banco Central de Costa Rica", "coverage": "1990 onward for many series",
     "frequency": "daily and monthly", "publication_lag_days": 0.0,
     "revisions": "macro aggregates are revised; the FX and rate series are not",
     "licence": "free, public with a registration token", "history_from": "1990-01",
     "pit_feasible": True,
     "assets": ("USDMXN", "USDBRL", "US500"),
     "mechanism_families": ("policy_surprise", "intervention"),
     "how_to_fetch": "the SOAP service at gee.bccr.fi.cr/indicadoreseconomicos/WebServices/; "
                     "this is the only genuinely machine-readable central-bank API on the "
                     "isthmus and it is why Costa Rica is the working control jurisdiction"},
    {"name": "BCN official exchange-rate table and the published slide rate",
     "source": "Banco Central de Nicaragua", "coverage": "1990 onward", "frequency": "daily",
     "publication_lag_days": 0.0, "revisions": "never revised", "licence": "free, public",
     "history_from": "1993-01", "pit_feasible": True,
     "assets": ("XAUUSD", "USDMXN"),
     "mechanism_families": ("administered_price", "regime_break"),
     "how_to_fetch": "bcn.gob.ni publishes the daily official rate table a month ahead because "
                     "the slide is administrative; THE SERIES' OWN FIRST DIFFERENCE IS THE "
                     "POLICY and its step to zero in 2024 is the regime break"},
    {"name": "Superintendencia de Bancos de Panama monthly banking-system statistics",
     "source": "Superintendencia de Bancos de Panama", "coverage": "2000 onward",
     "frequency": "monthly", "publication_lag_days": 45.0,
     "revisions": "restated as institutions report", "licence": "free, public",
     "history_from": "2000-01", "pit_feasible": False,
     "assets": ("US500", "XCUUSD"),
     "mechanism_families": ("credit_state", "liquidity"),
     "how_to_fetch": "superbancos.gob.pa statistics; THIS IS PANAMA'S MONETARY STATISTICS -- "
                     "the Centro Bancario Internacional's liquidity ratio and deposit base are "
                     "the substitute for the aggregates a central bank would publish, and "
                     "NO_LAWFUL_GROUND names the absence this fills"},
    {"name": "Colon Free Zone re-exports and Panamanian port throughput",
     "source": "Contraloria General de la Republica (INEC) and the Autoridad Maritima",
     "coverage": "2000 onward", "frequency": "monthly", "publication_lag_days": 60.0,
     "revisions": "routinely restated two months back", "licence": "free, public",
     "history_from": "2000-01", "pit_feasible": False,
     "assets": ("US500", "USDCNH", "XCUUSD"),
     "mechanism_families": ("trade_flow", "logistics_regime"),
     "how_to_fetch": "contraloria.gob.pa/inec/ trade and transport tables; the free zone's "
                     "re-exports LEAD its customers' own import prints, which makes this a "
                     "regional demand nowcast nobody else on this desk carries"},
    {"name": "SIECA intra-regional trade and the common external tariff",
     "source": "Secretaria de Integracion Economica Centroamericana",
     "coverage": "2000 onward for all six on one definition", "frequency": "monthly",
     "publication_lag_days": 60.0, "revisions": "restated as national customs data arrives",
     "licence": "free, public", "history_from": "2000-01", "pit_feasible": False,
     "assets": ("CORN", "SUGAR", "COTTON", "USDMXN"),
     "mechanism_families": ("trade_flow", "substitution"),
     "how_to_fetch": "estadisticas.sieca.int; ONE DEFINITION ACROSS SIX COUNTRIES is what makes "
                     "a mirror comparison possible where a national series has narrowed"},
    {"name": "UN Comtrade mirror customs for the narrowed series",
     "source": "United Nations Comtrade", "coverage": "1990 onward",
     "frequency": "monthly and annual", "publication_lag_days": 120.0,
     "revisions": "partners restate; the mirror and the direct series disagree by construction",
     "licence": "free, public", "history_from": "1990-01", "pit_feasible": False,
     "assets": ("XAUUSD", "COFARA", "SUGAR", "COTTON"),
     "mechanism_families": ("trade_flow", "measurement_substitute"),
     "how_to_fetch": "comtradeplus.un.org by reporter and partner; THE LAWFUL SUBSTITUTE for "
                     "Nicaraguan trade the country does not publish -- reconstruct the export "
                     "from what its partners declare importing, and label the series MIRROR so "
                     "no study silently mixes the two"},
    {"name": "FEWS NET dry corridor food-security and rainfall assessments",
     "source": "Famine Early Warning Systems Network and the national meteorological services",
     "coverage": "2010 onward", "frequency": "monthly with seasonal updates",
     "publication_lag_days": 10.0, "revisions": "scenarios are updated rather than revised",
     "licence": "free, public (US government work)", "history_from": "2010-01",
     "pit_feasible": True,
     "assets": ("CORN", "COFARA", "SUGAR", "WHEAT"),
     "mechanism_families": ("weather_state", "seasonal_crop", "physical_supply"),
     "how_to_fetch": "fews.net/es/central-america plus INSIVUMEH, IMN, INETER and COPECO "
                     "bulletins; a DATED, PUBLISHED agricultural-risk series for the Corredor "
                     "Seco that leads the harvest by months"},
    {"name": "Gaceta and Diario Oficial acts: Ley 406, the Supreme Court ruling, the holiday "
             "decrees and the Bitcoin Law amendments",
     "source": "the six national gazettes of record",
     "coverage": "digitised back a decade or more for most of the six",
     "frequency": "daily, irregular in content", "publication_lag_days": 1.0,
     "revisions": "a gazetted act is not revised; it is repealed by another gazetted act",
     "licence": "free, public", "history_from": "2010-01", "pit_feasible": True,
     "assets": ("XCUUSD", "BTCUSD", "US500"),
     "mechanism_families": ("legal_event", "political_event"),
     "how_to_fetch": "gacetaoficial.gob.pa, dca.gob.gt, imprentanacional.go.cr, "
                     "diariooficial.gob.sv and lagaceta.gob.ni by date and by act number; THIS "
                     "IS THE ONLY ROUTE FROM PRESS_REPORTED TO PROMOTABLE for every dated event "
                     "in this pack"},
)

# --------------------------------------------------------------------------- actors
#: TWENTY-FIVE ACTORS, each with all eleven fields, and EVERY JURISDICTION OWES AT LEAST THREE
#: OF ITS OWN (`ACTOR_JURISDICTIONS` is the map and the tests count it). An actor whose FALSIFIER
#: is blank is a story, and a story is not a research object. The national champions a two-lane
#: violation would put on a docket -- First Quantum, the sugar mills, the apparel groups, the
#: banks of the Centro Bancario Internacional -- appear HERE and in no instrument tuple anywhere.
ACTORS: tuple[dict[str, Any], ...] = (
    {"name": "The Autoridad del Canal de Panama board and administrator",
     "holds": "the operating rule of a waterway that carries roughly a twentieth of world "
              "seaborne trade, the water of Gatun and Alhajuela that floats it, and the "
              "constitutional autonomy to set draft, slots and tolls without a ministry",
     "forced_to": ("publish an advisory to shipping BEFORE a constraint takes effect, with a "
                   "stated effective date",
                   "publish the lake levels daily and the transit statistics monthly",
                   "transfer a contribution to the national Treasury each fiscal year",
                   "keep enough water for Panama City's drinking supply, which competes with "
                   "the locks for the same reservoir"),
     "when": "advisories land in the Panamanian business day and take effect days or weeks "
             "later; Panama is UTC-5 all year so the hour never moves",
     "information": ("the basin's rainfall and the reservoir trajectory weeks ahead of the "
                     "market",
                     "the forward booking book and who is waiting",
                     "the vessel mix arriving at each end"),
     "constraints": ("a lake that is both the lock water and the capital's drinking water",
                     "a lock cycle that spends fresh water per transit and cannot be run dry",
                     "a competitor route -- Suez, the Cape, and the US land bridge -- that "
                     "caps how much the toll can rise before cargo leaves for good"),
     "instruments": ("CORN", "SOYBEAN", "WHEAT", "XNGUSD", "XTIUSD"),
     "counterparties": ("the liner operators and the dry-bulk and gas charterers",
                        "the US Gulf grain shippers on one side and the Asian buyers on the "
                        "other",
                        "the Panamanian Treasury, which receives the contribution"),
     "observables": ("the advisory series and its effective dates",
                     "the daily lake level", "the bookable slot count",
                     "the monthly transit and tonnage statistics"),
     "impact": "a published cut in draft or slots is a withheld physical route for cargo that "
               "has no near substitute at the same freight cost; the effect shows up in the "
               "grain and gas legs and in the freight the equity market pays for",
     "persistence": "a drought constraint persists for quarters because a reservoir refills on "
                    "a season's rainfall and not on a week's",
     "falsifier": "constraint windows match the matched-period control on the grain and energy "
                  "legs once the Suez and Bab el-Mandeb transit series and the US Gulf-to-PNW "
                  "routing share are conditioned on -- which would mean the market prices global "
                  "freight and not this chokepoint",
     "notes": "THE PACK'S REASON TO EXIST. No other chokepoint operator publishes its own "
              "binding constraint in advance with an effective date"},
    {"name": "The ACP transit reservation and auction desk",
     "holds": "the booking book: how many slots exist, which segment each belongs to, and which "
              "released slots go to auction",
     "forced_to": ("allocate a finite number of slots under a published rule",
                   "run an auction for released slots and let the price be reported",
                   "publish changes to the reservation conditions in advance"),
     "when": "auctions clear inside the Panamanian business day; the result reaches the trade "
             "press within a day",
     "information": ("the unfilled demand behind each auction",
                     "which vessel classes are bidding and how badly"),
     "constraints": ("slots cannot be created: the constraint is physical water",
                     "a bidder that misses its loading window loses far more than the slot, "
                     "which is exactly why the clearing price can reach millions"),
     "instruments": ("XNGUSD", "XTIUSD", "CORN", "SOYBEAN"),
     "counterparties": ("the LPG and LNG charterers who bid highest",
                        "the container lines with fixed schedules to protect",
                        "the dry-bulk operators who usually wait instead of bidding"),
     "observables": ("the auction clearing price", "the number of slots released",
                     "the queue of ships at anchor at each end"),
     "impact": "the clearing price is a PRICED OPTION on the constraint: it says what a missed "
               "loading window is worth, in dollars, on a dated day",
     "persistence": "an auction price is a spot observation; the CONSTRAINT behind it persists",
     "falsifier": "auction prints carry no information about the gas and grain legs beyond what "
                  "the slot count already carries, measured with the slot count held fixed",
     "notes": "the cleanest scarcity price in this pack, and the one with the fewest "
              "observations -- which is a sample-size problem and not a design problem"},
    {"name": "The Autoridad Maritima de Panama and the world's largest ship registry",
     "holds": "the flag of a larger share of world tonnage than any other state, and the "
              "registry fees that come with it",
     "forced_to": ("maintain an open registry that competes with Liberia and the Marshall "
                   "Islands on price and paperwork speed",
                   "respond to sanctions designations on vessels flying its flag",
                   "publish the registered fleet and its tonnage"),
     "when": "continuously; de-flagging actions cluster after sanctions designations",
     "information": ("which vessels are being de-flagged and why",
                     "the registry's own revenue trajectory"),
     "constraints": ("a flag state carries reputational and enforcement liability for a fleet "
                     "it does not operate",
                     "registry revenue is fiscal revenue in a sovereign that cannot print"),
     "instruments": ("XBRUSD", "XTIUSD", "US500"),
     "counterparties": ("the shipowners and managers", "the sanctioning authorities",
                        "the classification societies"),
     "observables": ("the registered fleet and tonnage", "de-flagging announcements",
                     "registry revenue in the fiscal accounts"),
     "impact": "a mass de-flagging reshuffles which hulls can lawfully lift sanctioned crude, "
               "which is a real constraint on the grey tanker fleet and therefore on the "
               "discount that crude trades at",
     "persistence": "registry shares move over years; a sanctions-driven de-flagging is a "
                    "dated step",
     "falsifier": "de-flagging episodes carry no information about the crude legs beyond what "
                  "the sanctions designations themselves already carry",
     "notes": "Panama is a MARITIME SOVEREIGN as much as a territorial one, and the registry is "
              "the half of that most desks never look at"},
    {"name": "The Superintendencia de Bancos de Panama and the Centro Bancario Internacional",
     "holds": "the supervision of a dollar banking centre in a country with no central bank and "
              "therefore no lender of last resort",
     "forced_to": ("publish the system's balance sheet, liquidity ratio and deposit base "
                   "monthly, because there is no monetary authority to publish aggregates",
                   "respond to international listing processes on financial transparency",
                   "supervise without the ability to create liquidity"),
     "when": "monthly, about forty-five days after the reference month",
     "information": ("the deposit base's direction before it is published",
                     "which institutions are under stress"),
     "constraints": ("NO LENDER OF LAST RESORT EXISTS: a Panamanian bank run can only be met "
                     "with the dollars already in the country, which is the sharpest "
                     "institutional difference between this economy and every other on the desk",
                     "a listing or de-listing by an international transparency body moves "
                     "correspondent-banking access, which is existential for an offshore centre"),
     "instruments": ("US500", "XCUUSD", "XAUUSD"),
     "counterparties": ("the correspondent banks in New York",
                        "the depositors of the region and beyond",
                        "the transparency and rating bodies"),
     "observables": ("the monthly liquidity ratio", "the deposit base",
                     "listing and de-listing announcements"),
     "impact": "a liquidity squeeze in a dollarised centre with no backstop transmits to "
               "regional credit rather than to an exchange rate, which is why every Panamanian "
               "macro cell in this pack terminates in the US legs",
     "persistence": "deposit-base trends persist for quarters; a listing event is a step",
     "falsifier": "the banking-system liquidity series carries no information about the US legs "
                  "beyond what US financial conditions already carry -- a genuinely likely null",
     "notes": "THE LAWFUL SUBSTITUTE for the monetary statistics Panama cannot have"},
    {"name": "Minera Panama, its workforce and the concentrate stockpile",
     "holds": "an orebody producing roughly 1.5% of world mined copper, a port of its own at "
              "Punta Rincon, a power plant, and a concentrate stockpile that has sat on site "
              "since the closure",
     "forced_to": ("maintain the site in preservation and safe management while closed, which "
                   "costs money with no revenue",
                   "seek permission to move the stockpiled concentrate",
                   "negotiate with a state whose Supreme Court voided its contract"),
     "when": "the closure order was executive and followed a court ruling on a dated afternoon; "
             "the restart process is a published negotiation",
     "information": ("the true cost of preservation and the restart timeline",
                     "the condition of the plant after years idle"),
     "constraints": ("a voided concession cannot be revived by the company alone",
                     "a plant kept idle degrades and a restart is not instantaneous",
                     "a workforce dispersed is not reassembled on demand"),
     "instruments": ("XCUUSD",),
     "counterparties": ("the Panamanian state and its courts",
                        "the Chinese and other smelters that took the concentrate",
                        "its own creditors and arbitration counterparties"),
     "observables": ("the gazetted acts", "the export permits for the stockpile",
                     "the restart negotiation milestones"),
     "impact": "about 350,000 tonnes a year of contained copper removed from the seaborne "
               "concentrate market by a judicial act, with no substitute mine able to replace it "
               "inside a year",
     "persistence": "years: a closed mine of this size does not restart in a quarter",
     "falsifier": "the closure and restart timestamps carry no information about XCUUSD beyond "
                  "what the Chilean and Peruvian supply calendars and the Chinese demand prints "
                  "already carry, measured with those conditioned on",
     "notes": "TWO-LANE ORDER: the parent company is a listed miner and appears HERE and in no "
              "instrument tuple in this file"},
    {"name": "The Corte Suprema de Justicia de Panama and the Asamblea Nacional",
     "holds": "the power to void a concession contract that the executive had signed and the "
              "legislature had passed, and to do it while the streets were blockaded",
     "forced_to": ("rule on the constitutional challenges actually filed",
                   "publish the ruling in the Gaceta Oficial",
                   "legislate a mining moratorium if the political moment demands one"),
     "when": "the unconstitutionality ruling landed on a dated afternoon in November 2023",
     "information": ("the direction of the ruling before it is published",
                     "the political tolerance for a restart"),
     "constraints": ("a court cannot write a replacement contract",
                     "a moratorium that stops the mine also stops the fiscal revenue in a "
                     "sovereign that cannot print"),
     "instruments": ("XCUUSD", "US500"),
     "counterparties": ("the company and its arbitration counsel",
                        "the protest movement and the unions",
                        "the rating agencies that priced the fiscal consequence"),
     "observables": ("the gazetted ruling", "the closure order",
                     "the moratorium legislation", "the rating actions that followed"),
     "impact": "A JUDICIAL SUPPLY SHOCK: a court ruling removed a top-twenty copper mine, which "
               "is a category of event this desk has almost no other example of",
     "persistence": "the ruling is permanent until a new contract is lawfully made",
     "falsifier": "judicial and legislative timestamps produce no copper response distinguishable "
                  "from the matched-window control once the concurrent Chinese demand prints are "
                  "conditioned on",
     "notes": "the event class matters: a strike is negotiable, a drought ends, and a "
              "constitutional ruling is neither"},
    {"name": "The Junta Monetaria del Banco de Guatemala",
     "holds": "the tasa lider, the reserve requirement, and a PUBLISHED FX participation rule "
              "that states its own trigger",
     "forced_to": ("decide on a published calendar and publish the resolution the same day",
                   "participate in the FX market when its own stated rule is triggered, in "
                   "stated amounts",
                   "publish the reference rate and its moving average daily"),
     "when": "resolution days on a published calendar; participation happens BETWEEN meetings "
             "whenever the rule fires",
     "information": ("the remittance inflow before it is published, because it clears through "
                     "the banking system it supervises",
                     "the banks' end-of-day FX positions"),
     "constraints": ("a stated rule constrains discretion, which is the point of it",
                     "a quetzal that has appreciated on remittance inflow hurts the exporters "
                     "the same inflow's country lives on"),
     "instruments": ("USDMXN", "USDBRL", "COFARA", "SUGAR"),
     "counterparties": ("the commercial banks at the participation window",
                        "the coffee and sugar exporters selling dollars",
                        "the remittance operators bringing them in"),
     "observables": ("the resolution and the tasa lider",
                     "the reference rate and its moving average",
                     "the participation amounts", "the monthly remittance print"),
     "impact": "GTQ is absent from the broker, so this actor is a CONDITIONER: it says when the "
               "regional legs should be read as carrying Guatemala and when they should not",
     "persistence": "a rate level persists between meetings; a rule change persists until the "
                    "next resolution amends it",
     "falsifier": "rule-triggered participation days carry no information about the regional EM "
                  "legs beyond a matched-day placebo once the US risk state is conditioned on",
     "notes": "THE COMPUTABLE REACTION FUNCTION. Peru's is published after the fact; "
              "Guatemala's is stated in advance as arithmetic on a public series"},
    {"name": "ANACAFE and the Guatemalan coffee exporters",
     "holds": "the export permit for every bag of Guatemalan coffee, and therefore the count",
     "forced_to": ("issue a permit for each shipment and publish the monthly aggregate",
                   "publish the regional origin split across the growing zones",
                   "report the harvest-year accumulation against the prior year"),
     "when": "monthly, about twenty days after the reference month, on the October-September "
             "harvest year",
     "information": ("the permit flow in real time, weeks before the aggregate is published",
                     "the exporters' forward sales against an unharvested crop"),
     "constraints": ("a permit counts what LEAVES, not what was grown: a crop held back is "
                     "invisible until it ships",
                     "the differential the exporter actually receives is assessed privately and "
                     "is not in any published series"),
     "instruments": ("COFARA", "COFROB"),
     "counterparties": ("the importers and roasters in the United States and Europe",
                        "the cooperatives and smallholders who deliver the cherry",
                        "the banks that finance the pre-harvest"),
     "observables": ("the monthly export volume", "the origin split",
                     "the harvest-year accumulation"),
     "impact": "a counted washed-arabica supply number against a liquid contract, published "
               "monthly by the body that had to authorise every shipment in it",
     "persistence": "a crop year: an origin shock shows for twelve months and a rust epidemic "
                    "for three",
     "falsifier": "monthly export surprises carry no information about COFARA beyond what the "
                  "ICO group indicators and the Brazilian crop already carry, tested with "
                  "COFROB as the non-belt control",
     "notes": "the count is the asset; the DIFFERENTIAL is licensed and is declared UNMEASURED"},
    {"name": "ASAZGUA and the Guatemalan sugar mills",
     "holds": "a cane crush that makes Guatemala one of the world's largest raw sugar exporters, "
              "with its own port terminal at Quetzal and its own cogeneration into the grid",
     "forced_to": ("run the zafra inside a harvest window that opens in November and closes in "
                   "May, because cane cannot wait",
                   "publish the season's grind and export programme",
                   "sell into a world market whose price is set elsewhere"),
     "when": "the zafra is a seasonal block; the export programme follows the grind by weeks",
     "information": ("the cane yield and sucrose content before anyone else",
                     "the forward sales book against an unharvested crop"),
     "constraints": ("cane must be crushed within a day or two of cutting",
                     "a drought or an excess-rain year changes sucrose content and not only "
                     "tonnage, which a volume-only study will miss"),
     "instruments": ("SUGAR", "CORN"),
     "counterparties": ("the world refiners and traders",
                        "the cane growers and the seasonal cutting labour",
                        "the national grid, which buys the mills' cogenerated power"),
     "observables": ("the weekly grind", "the season's export programme",
                     "the cogeneration output"),
     "impact": "a top-five raw sugar exporter's season is a real share of the exportable "
               "surplus, and it is dated by a harvest window rather than by a calendar quarter",
     "persistence": "one season, with a carry-out into the next",
     "falsifier": "zafra volumes carry no information about SUGAR beyond what the Brazilian "
                  "and Indian crops already carry, tested on the same weeks in neutral years",
     "notes": "TWO-LANE ORDER: the mills are private groups and appear only here"},
    {"name": "The highland communities of Totonicapan, Huehuetenango and Alta Verapaz",
     "holds": "the land the coffee grows on, the labour that picks it, and the roads it leaves "
               "on -- and the community assemblies that decide whether any of the three moves",
     "forced_to": ("decide in assembly, in K'iche', Q'eqchi' or Kaqchikel, because that is how "
                   "the authority is constituted",
                   "defend land titles in a court system that works in Spanish",
                   "supply the seasonal cutting labour a harvest cannot happen without"),
     "when": "assemblies and road actions cluster around the harvest and around land rulings",
     "information": ("a land ruling's local consequence before the capital hears of it",
                     "whether the cutting labour will show up this season"),
     "constraints": ("a community authority is not a company and cannot be bargained with as "
                     "one",
                     "seasonal labour migrates between the coast and the highlands on its own "
                     "calendar, which is not the exporter's"),
     "instruments": ("COFARA", "SUGAR", "CORN"),
     "counterparties": ("the finca owners and the exporters",
                        "the state land registry and the courts",
                        "the community press that reports the assembly's decision"),
     "observables": ("the community press reports of assemblies and road actions",
                     "land-registry and court rulings",
                     "the cutting-labour availability the trade press reports"),
     "impact": "a harvest that is not picked or not moved is an export volume that does not "
               "appear, and it appears nowhere in a weather model",
     "persistence": "a land dispute persists for years; a road action for days to weeks",
     "falsifier": "reported highland disputes carry no information about COFARA beyond the "
                  "weather and the Brazilian crop, tested against harvest windows with no "
                  "reported dispute",
     "notes": "THE GROUND THE SPANISH-ONLY CRAWL MISSES. This actor exists because the decision "
              "that interrupts a Guatemalan harvest is taken in a Mayan language and reported "
              "first in the community press"},
    {"name": "The Banco Central de Honduras FX allocation desk",
     "holds": "the daily auction through which the country's dollars are rationed, and a band "
              "with a base price it sets",
     "forced_to": ("hold an auction each business day and publish what was offered and bid",
                   "defend a band that has been frozen and re-opened on dated resolutions",
                   "publish reserves and remittances monthly"),
     "when": "daily, inside the Honduran business day; UTC-6 all year",
     "information": ("the true unfilled demand, because it queues at its own window",
                     "the importers' letter-of-credit backlog"),
     "constraints": ("a rationed market clears in a queue rather than in a price, so the "
                     "shortage is a quantity and not a rate",
                     "a maquila sector paid in dollars and a food import bill paid in dollars "
                     "pull in opposite directions on the same reserve stock"),
     "instruments": ("USDMXN", "COFARA", "COTTON"),
     "counterparties": ("the authorised dealer banks", "the importers in the queue",
                        "the coffee and maquila exporters supplying the dollars"),
     "observables": ("the amount offered and the amount bid at each auction",
                     "the base price and the permitted deviation",
                     "the monthly reserve and remittance prints"),
     "impact": "the queue is a leading indicator of an import compression that shows up in "
               "activity months later; the posted rate shows almost nothing",
     "persistence": "a shortage cumulates across days and unwinds slowly",
     "falsifier": "the offered-minus-bid series carries no information about the regional legs "
                  "beyond what the remittance print already carries",
     "notes": "the one FX market on this isthmus that is explicitly RATIONED, which makes it "
              "the natural control for the two that are not"},
    {"name": "IHCAFE and the Honduran coffee cooperatives",
     "holds": "the export record of the largest producer of the five origins and the "
              "cooperative structure that most of its smallholders sell through",
     "forced_to": ("publish the monthly export volume and the harvest-year accumulation",
                   "administer the levy and the replanting programmes after a rust epidemic",
                   "certify shipments"),
     "when": "monthly, about twenty days after the reference month",
     "information": ("the cooperative delivery flow before the aggregate is published",
                     "the replanting programme's real coverage"),
     "constraints": ("a smallholder base means credit, not price, is often the binding "
                     "constraint on a harvest",
                     "the rust-driven replanting cycle changes the varietal mix and therefore "
                     "the yield profile for a decade"),
     "instruments": ("COFARA", "COFROB"),
     "counterparties": ("the exporters and the importers",
                        "the cooperatives and their members",
                        "the development banks financing replanting"),
     "observables": ("monthly exports", "the harvest-year accumulation",
                     "replanting and rust-incidence reporting"),
     "impact": "the largest single volume in the belt; a Honduran shortfall moves the belt's "
               "total more than any other origin's",
     "persistence": "a replanting cycle persists for years and changes the trend, not the level",
     "falsifier": "Honduran export surprises carry no COFARA information beyond the ICO Other "
                  "Milds indicator and the Brazilian crop",
     "notes": "Honduras overtook its neighbours by volume in the post-rust decade, which is "
              "itself a regime change inside the belt's composition"},
    {"name": "The Honduran maquila operators and the CAFTA-DR apparel chain",
     "holds": "an apparel and textile complex that ships to US distribution centres under a "
              "rule of origin that requires US or regional yarn",
     "forced_to": ("buy yarn and fabric that satisfy the yarn-forward rule or lose the "
                   "preference",
                   "ship on a US retail replenishment calendar",
                   "pay a dollar wage bill out of dollar revenue in a lempira economy"),
     "when": "continuous, with a month-end shipment cycle and a pre-season build",
     "information": ("the US order book one to two seasons ahead",
                     "which programmes are being re-sourced to Asia or to Mexico"),
     "constraints": ("YARN FORWARD: the preference is conditional on the input's origin, which "
                     "is what ties this chain to US cotton rather than to the cheapest cotton",
                     "a nearshoring decision is made by a US buyer and not by the plant"),
     "instruments": ("COTTON", "US30", "US500", "USDMXN"),
     "counterparties": ("the US brands and retailers",
                        "the US and regional yarn spinners",
                        "the Honduran, Salvadoran and Guatemalan workforces"),
     "observables": ("monthly maquila export values",
                     "US apparel import statistics by partner",
                     "employment in the free zones"),
     "impact": "a rule of origin turns a US retail cycle into a demand series for a specific "
               "fibre, which is the mechanism that makes COTTON an isthmus instrument at all",
     "persistence": "sourcing decisions persist for seasons and re-sourcing for years",
     "falsifier": "CAFTA-DR apparel volumes carry no information about COTTON beyond what US "
                  "mill use and the Chinese import prints already carry",
     "notes": "TWO-LANE ORDER: the brands and the plant operators are companies and appear "
              "only here"},
    {"name": "The Banco Central de Costa Rica and the MONEX participants",
     "holds": "a real policy rate, a wholesale FX market it both operates and trades in, and "
              "the only machine-readable indicator service on the isthmus",
     "forced_to": ("decide the TPM on a published calendar and explain it",
                   "publish the MONEX weighted rate and volume daily",
                   "disclose its own participation separately from the market's"),
     "when": "TPM decisions on a published calendar; MONEX closes each business day",
     "information": ("the free zones' dollar conversion flow, which is large relative to the "
                     "market and lumpy",
                     "the Treasury's own FX requirement"),
     "constraints": ("a small market in which one free-zone conversion can move the rate",
                     "a fiscal rule that binds spending and therefore binds the policy mix"),
     "instruments": ("USDMXN", "USDBRL", "US500"),
     "counterparties": ("the banks and the free-zone exporters",
                        "the Treasury", "the IMF under the completed arrangements"),
     "observables": ("the TPM and its communique", "the MONEX rate and volume",
                     "the BCCR's own participation"),
     "impact": "THE CONTROL. Every dollarisation claim in this pack is measured against a "
               "neighbour with the same coffee, the same drought and its own money",
     "persistence": "a policy stance persists across meetings; the float is structural",
     "falsifier": "Costa Rican policy surprises produce no regional-leg response distinguishable "
                  "from a matched-day placebo, which would mean the isthmus's monetary "
                  "differences do not reach any executable instrument at all",
     "notes": "the pack's most important NEGATIVE control and the only fully instrumented "
              "central bank on the isthmus"},
    {"name": "ICAFE and the Costa Rican coffee liquidation",
     "holds": "the administered formula by which an exporter's realised price is liquidated "
              "back to the producer, published by law",
     "forced_to": ("publish the liquidation and administer the formula",
                   "publish monthly exports on the harvest year",
                   "arbitrate between mills and producers under the statute"),
     "when": "monthly for exports; the liquidation settles after the crop year closes",
     "information": ("the realised export prices before the liquidation is published",
                     "the mills' cost structure"),
     "constraints": ("a statutory price-sharing formula removes the mill's ability to keep a "
                     "windfall, which changes the whole chain's incentives",
                     "Costa Rica is the smallest of the five by volume and cannot move the "
                     "world price on its own"),
     "instruments": ("COFARA",),
     "counterparties": ("the producers and the mills", "the exporters and importers"),
     "observables": ("the published liquidation price", "monthly exports",
                     "the mills' declared realised prices"),
     "impact": "THE PASS-THROUGH IS PUBLISHED HERE AND INFERRED EVERYWHERE ELSE: this is the "
               "one origin where the link from the exchange price to the farm gate is a legal "
               "number rather than an econometric estimate",
     "persistence": "one crop year per liquidation",
     "falsifier": "the liquidation series adds nothing to COFARA beyond the exchange price it "
                  "is computed from -- which is the likely null and worth measuring anyway, "
                  "because the RESIDUAL is the origin's own differential",
     "notes": "the pack's cleanest natural experiment on commodity price pass-through"},
    {"name": "PROCOMER, CINDE and the Costa Rican free-zone cluster",
     "holds": "the export record and the investment pipeline of a medical-device and "
              "semiconductor cluster that is now larger than the country's agricultural exports",
     "forced_to": ("publish the free-zone export record by sector",
                   "compete for each new plant against Mexico and Asia on a dated decision",
                   "operate under a free-zone regime whose tax treatment is periodically "
                   "renegotiated with the OECD framework"),
     "when": "monthly export statistics; investment announcements are dated events",
     "information": ("the pipeline of investment decisions before they are announced",
                     "the cluster's dollar conversion needs"),
     "constraints": ("a free-zone regime's tax treatment is constrained by international "
                     "minimum-tax rules the country does not write",
                     "a cluster this concentrated is exposed to one or two global buyers"),
     "instruments": ("US500", "US30", "USDMXN", "USDCNH"),
     "counterparties": ("the US and European device and chip firms",
                        "the Costa Rican Treasury under the fiscal rule",
                        "the workforce the cluster competes for"),
     "observables": ("monthly free-zone exports by sector",
                     "announced investments", "free-zone employment"),
     "impact": "THE NEARSHORING OBSERVABLE. A small country's device and chip exports are a "
               "high-frequency read on whether supply chains are actually moving to the Americas "
               "or only being talked about",
     "persistence": "an investment decision persists for a decade",
     "falsifier": "Costa Rican free-zone export surprises carry no information about the US "
                  "legs beyond what US industrial production already carries",
     "notes": "the nearshoring cell's home, and the direct `mx` interaction"},
    {"name": "The Banco Central de Nicaragua and the deslizamiento",
     "holds": "a published daily table of official exchange rates set administratively, and the "
              "decision of what rate of slide to put in it",
     "forced_to": ("publish the official rate table in advance, because the slide is "
                   "administrative and therefore knowable",
                   "publish remittances, reserves and external trade monthly",
                   "defend a fixed rate with reserves built on remittances and gold"),
     "when": "the table is published ahead; the slide-rate changes are resolutions with dates",
     "information": ("the reserve trajectory and the remittance flow before publication",
                     "which exporters are surrendering dollars and at what pace"),
     "constraints": ("a zero slide with domestic inflation above the United States' is a real "
                     "appreciation that has to be paid for somewhere",
                     "reserves built on remittances depend on a migration flow the country does "
                     "not control"),
     "instruments": ("XAUUSD", "USDMXN", "COFARA", "SUGAR"),
     "counterparties": ("the domestic banks", "the remittance senders abroad",
                        "the gold and coffee exporters"),
     "observables": ("the published rate table and its first difference",
                     "the slide-rate resolutions", "monthly remittances and reserves"),
     "impact": "THE SERIES' OWN FIRST DIFFERENCE IS THE POLICY, which makes the step to zero in "
               "2024 a regime break with a date and a magnitude and no inference required",
     "persistence": "a slide rate persists until a resolution changes it",
     "falsifier": "the slide-rate steps carry no information about the export legs beyond what "
                  "the gold and coffee prices already carry",
     "notes": "the cleanest administered-price series in the pack, in the jurisdiction whose "
              "surrounding ecology is the hardest to read"},
    {"name": "The Nicaraguan gold concessionaires and the artisanal miners",
     "holds": "the concessions behind what has become the country's largest single export, and "
              "an artisanal sector whose output enters the same export line",
     "forced_to": ("declare exports through the customs and central-bank record",
                   "operate under a concession regime the state grants and can revoke",
                   "sell into a refining chain outside the country"),
     "when": "continuous; the export value is published monthly",
     "information": ("the true artisanal output, which is not separately counted",
                     "concession grants before they are gazetted"),
     "constraints": ("an artisanal sector cannot be metered, so the export line mixes two very "
                     "different production functions",
                     "the refining and sanctions environment determines who may buy"),
     "instruments": ("XAUUSD",),
     "counterparties": ("the international refiners and buyers",
                        "the state as concession grantor",
                        "the artisanal communities"),
     "observables": ("the monthly gold export value and volume",
                     "concession gazettes", "mirror customs from the importing partners"),
     "impact": "gold is a fifth or more of Nicaraguan exports and the dollar earnings behind the "
               "zero-slide regime; the world price channel is the reverse direction and is the "
               "one this pack can execute",
     "persistence": "concession-driven output persists for years",
     "falsifier": "Nicaraguan export volumes carry no information about XAUUSD -- a near-certain "
                  "null on the world price, which is why the cell runs the other way, from the "
                  "GOLD PRICE to the country's reserve and FX capacity",
     "notes": "an honest small-producer cell: the country is a price taker and the pack says so"},
    {"name": "The Nicaraguan state as canal concessionaire and statistical publisher",
     "holds": "the power it granted and then repealed over an interoceanic canal route, and the "
              "decision of what economic statistics to publish",
     "forced_to": ("publish enough for the IMF Article IV to be written",
                   "gazette the concession and its repeal",
                   "maintain the central bank's external-sector series, which it has"),
     "when": "the concession was granted in 2013 and repealed in 2024; both are gazetted",
     "information": ("the real state of any canal project, which was never independently "
                     "verifiable",
                     "the statistics it chooses not to publish"),
     "constraints": ("a canal concession without financing is a legal instrument and not a "
                     "construction project",
                     "an economy dependent on remittances and gold cannot afford opacity in the "
                     "series its creditors read"),
     "instruments": ("XAUUSD", "USDMXN"),
     "counterparties": ("the concessionaire and its backers",
                        "the IMF and the multilateral creditors",
                        "the exile press that reports what the state does not publish"),
     "observables": ("the gazetted concession and repeal",
                     "what INIDE and the BCN do and do not publish",
                     "the Article IV staff reports", "mirror customs"),
     "impact": "A REPEALED CONCESSION IS A REMOVED OPTION on a second isthmus crossing, which is "
               "a permanent change to the Panama Canal's competitive position and is worth "
               "exactly one dated cell",
     "persistence": "permanent until another concession is granted",
     "falsifier": "the concession and repeal dates produce no measurable response anywhere, "
                  "which is the likely outcome and is worth recording as a measured null",
     "notes": "the statistical-narrowing half of this actor is declared in NO_LAWFUL_GROUND "
              "with its lawful substitutes named"},
    {"name": "The Banco Central de Reserva de El Salvador",
     "holds": "the supervision, the statistics and the payment system of a dollarised economy, "
              "and NO monetary instrument of any kind",
     "forced_to": ("publish remittances, prices and the external accounts monthly",
                   "operate the payment system in a currency it cannot issue",
                   "implement an IMF programme it did not design the monetary half of, because "
                   "there is no monetary half"),
     "when": "monthly publication on a fixed schedule",
     "information": ("the remittance flow before publication",
                     "the banking system's dollar liquidity"),
     "constraints": ("NO LENDER OF LAST RESORT IN ITS OWN MONEY, because there is no own money",
                     "a fiscal shock cannot be monetised, so it must be financed or defaulted"),
     "instruments": ("US500", "US30", "BTCUSD"),
     "counterparties": ("the Ministerio de Hacienda", "the IMF", "the commercial banks"),
     "observables": ("the monthly remittance print", "the banking-system liquidity",
                     "the debt record"),
     "impact": "a central bank with no instrument makes El Salvador PANAMA'S REPLICATE: two "
               "dollarised economies, one with a central bank and one without, on the same "
               "isthmus -- which is the second layer of this pack's natural experiment",
     "persistence": "structural since 2001",
     "falsifier": "Salvadoran and Panamanian macro surprises produce identical responses in the "
                  "US legs, which would mean the presence or absence of a toothless central bank "
                  "carries no information at all -- a genuinely informative null",
     "notes": "declared in NO_LAWFUL_GROUND as an OBJECT absence: the institution exists and the "
              "instrument does not"},
    {"name": "The Salvadoran state as bitcoin holder and sovereign debtor",
     "holds": "a legislated bitcoin programme, a publicly tracked holding, and an external debt "
              "stock that went from distressed to performing across a dated sequence",
     "forced_to": ("pay or default on dated maturities, with no ability to print the currency "
                   "they are owed in",
                   "legislate the bitcoin programme's status, and amend it when a programme "
                   "requires it",
                   "publish the fiscal accounts under an IMF arrangement"),
     "when": "the law, the maturity, the staff-level agreement and the amendment are each dated",
     "information": ("the buyback intentions before they are executed",
                     "the programme negotiation's direction"),
     "constraints": ("a dollarised sovereign cannot inflate away a dollar debt",
                     "a programme condition that narrows a flagship policy is a political cost "
                     "with a fiscal benefit"),
     "instruments": ("BTCUSD", "US500", "XAUUSD"),
     "counterparties": ("the bondholders", "the IMF", "the domestic pension system"),
     "observables": ("the gazetted laws and amendments", "the dated maturities and buybacks",
                     "the programme reviews", "the publicly reported holding"),
     "impact": "A SOVEREIGN POLICY OBSERVABLE ROUTED INTO A BROKER CFD. The mandate boundary is "
               "explicit: this is a fiscal and legal event series, executed on BTCUSD and on the "
               "risk legs, and NO exchange venue, order book or feed is named anywhere",
     "persistence": "the credit sequence persists for years; each legal act is a step",
     "falsifier": "the Salvadoran legal and credit timestamps produce no BTCUSD response "
                  "distinguishable from a matched-window placebo -- the likely null, and the one "
                  "that would settle whether a small sovereign's policy moves a global asset",
     "notes": "the pack's single most mandate-sensitive actor, and the reason ACCESS_CONSTRAINTS "
              "states the crypto boundary in full"},
    {"name": "The Salvadoran, Guatemalan and Honduran remittance households",
     "holds": "the receiving end of a flow worth a fifth to a quarter of GDP, and the spending "
              "decision that turns it into imports, construction or dollar deposits",
     "forced_to": ("receive in dollars and spend in an economy that is either dollarised or "
                   "managed",
                   "absorb the corridor fee, which is published by corridor",
                   "time receipts around the sender's payday and the family calendar"),
     "when": "monthly in aggregate, with spikes at each country's own Mother's Day and in "
             "December",
     "information": ("the sender's employment state, months before any statistic records it",
                     "whether the household is saving the transfer or spending it on imports"),
     "constraints": ("the flow depends on a US labour market and a US enforcement posture, "
                     "neither of which the receiving country influences",
                     "a spike is consumption and a trend is investment, and a monthly series "
                     "mixes them"),
     "instruments": ("USDMXN", "US500", "US30"),
     "counterparties": ("the migrant senders", "the remittance operators and banks",
                        "the importers the money is ultimately spent with"),
     "observables": ("the monthly remittance print per country",
                     "the corridor cost series", "the dated US policy acts"),
     "impact": "the highest-frequency link between the US cycle and this isthmus, published "
               "monthly by four central banks with four different lags",
     "persistence": "trend persists for years; the dated policy shocks are steps",
     "falsifier": "remittance surprises carry no information about the US legs beyond what US "
                  "payrolls already carry -- likely, and the interesting question is the REVERSE "
                  "direction, from a dated enforcement act to the flow",
     "notes": "the pack's four RECEIVER jurisdictions against its two SENDER ones, which is the "
              "control built into the same isthmus"},
    {"name": "SIECA and the Central American customs union",
     "holds": "the common external tariff, the intra-regional trade record on one definition, "
              "and the customs integration of Guatemala, Honduras and El Salvador",
     "forced_to": ("publish trade statistics for all six on a single definition",
                   "administer the common tariff and its exceptions",
                   "arbitrate the customs-union frictions between members"),
     "when": "monthly statistics with a long lag; tariff acts are dated",
     "information": ("the customs flow before the national series publish it",
                     "where the intra-regional frictions are binding this quarter"),
     "constraints": ("a secretariat cannot compel a member state",
                     "a partial customs union creates as many frictions as it removes"),
     "instruments": ("CORN", "SUGAR", "COTTON", "USDMXN"),
     "counterparties": ("the six member governments", "the regional business chambers",
                        "the external partners under CAFTA-DR and the EU agreement"),
     "observables": ("intra-regional trade statistics", "the common tariff schedule",
                     "customs-union integration milestones"),
     "impact": "ONE DEFINITION ACROSS SIX COUNTRIES is what makes a mirror comparison possible "
               "when a national series narrows, which is the measurement substitute this pack "
               "relies on for Nicaragua",
     "persistence": "structural; integration milestones are steps",
     "falsifier": "SIECA's aggregates add nothing the national series do not already carry, "
                  "measured where both exist -- which is the test that validates the mirror",
     "notes": "the regional actor the measurement substitutes depend on"},
    {"name": "The Banco Centroamericano de Integracion Economica as regional creditor",
     "holds": "a lending book that is material to the fiscal position of the smaller members and "
              "an approval calendar that is published",
     "forced_to": ("publish its approvals and disbursements",
                   "lend into sovereigns whose access to markets is intermittent",
                   "manage its own rating, which depends on the members'"),
     "when": "approvals are dated board acts",
     "information": ("the members' financing gaps before the market sees them",
                     "which approvals are about to reach the board"),
     "constraints": ("a regional bank's rating is hostage to its weakest large borrower",
                     "lending to a member under sanctions or opacity carries reputational cost"),
     "instruments": ("US500", "USDMXN"),
     "counterparties": ("the member sovereigns", "the international capital markets",
                        "the other multilaterals"),
     "observables": ("board approvals and disbursements", "its own issuance and spreads",
                     "the members' financing gaps"),
     "impact": "a dated disbursement into a small sovereign is a financing event that changes "
               "the probability of a fiscal accident, which is the credit channel this pack "
               "can only reach through the risk legs",
     "persistence": "loan-driven financing persists for the life of the programme",
     "falsifier": "BCIE approvals produce no measurable response in any executable leg, which is "
                  "likely and is worth one measured null",
     "notes": "the region's own lender, and the reason a small-sovereign financing squeeze here "
              "does not look like one elsewhere"},
    {"name": "The liner operators, gas charterers and dry-bulk shippers who buy canal slots",
     "holds": "the schedules, the charters and the loading windows that make a transit slot "
              "worth what it clears at",
     "forced_to": ("protect a fixed liner schedule or pay demurrage and lose the service",
                   "meet a loading window under a charter with a laycan that does not move",
                   "choose between the auction, the queue, Suez and the Cape"),
     "when": "continuously, and acutely in any constrained window",
     "information": ("their own cargo economics, which determine the auction bid",
                     "the re-routing decisions before they are visible in tracking data"),
     "constraints": ("a gas carrier's charter economics make a missed window catastrophically "
                     "expensive, which is why that class outbids everyone",
                     "a dry-bulk operator can usually wait, which is why grain queues instead "
                     "of bidding"),
     "instruments": ("XNGUSD", "CORN", "SOYBEAN", "XTIUSD", "US500"),
     "counterparties": ("the ACP auction desk", "the cargo owners and traders",
                        "the alternative routes' operators"),
     "observables": ("the auction clearing prices", "the anchorage queue",
                     "the chokepoint transit counts at Panama, Suez and Bab el-Mandeb"),
     "impact": "THE SUBSTITUTION DECISION IS MADE HERE, ship by ship, and the three chokepoint "
               "transit series are its record -- which is what turns a Panamanian water level "
               "into a global freight observable",
     "persistence": "a re-routing decision persists for the voyage and often for the season",
     "falsifier": "re-routing volumes carry no information about the energy and grain legs "
                  "beyond what the bunker price and the vessel supply already carry",
     "notes": "TWO-LANE ORDER: the liner and gas operators are listed companies and appear only "
              "here; the executable legs are the cargoes, never the carriers"},
)

#: WHICH JURISDICTION EACH ACTOR BELONGS TO. The brief's floor is three actors of its own per
#: jurisdiction and the tests COUNT this map rather than trusting the prose. `ca` is the regional
#: bucket and is a real category: SIECA, the BCIE and the shipping market belong to the isthmus
#: and to no single country in it.
ACTOR_JURISDICTIONS: dict[str, tuple[str, ...]] = {
    "The Autoridad del Canal de Panama board and administrator": ("pa",),
    "The ACP transit reservation and auction desk": ("pa",),
    "The Autoridad Maritima de Panama and the world's largest ship registry": ("pa",),
    "The Superintendencia de Bancos de Panama and the Centro Bancario Internacional": ("pa",),
    "Minera Panama, its workforce and the concentrate stockpile": ("pa",),
    "The Corte Suprema de Justicia de Panama and the Asamblea Nacional": ("pa",),
    "The Junta Monetaria del Banco de Guatemala": ("gt",),
    "ANACAFE and the Guatemalan coffee exporters": ("gt",),
    "ASAZGUA and the Guatemalan sugar mills": ("gt",),
    "The highland communities of Totonicapan, Huehuetenango and Alta Verapaz": ("gt",),
    "The Banco Central de Honduras FX allocation desk": ("hn",),
    "IHCAFE and the Honduran coffee cooperatives": ("hn",),
    "The Honduran maquila operators and the CAFTA-DR apparel chain": ("hn", "gt", "sv"),
    "The Banco Central de Costa Rica and the MONEX participants": ("cr",),
    "ICAFE and the Costa Rican coffee liquidation": ("cr",),
    "PROCOMER, CINDE and the Costa Rican free-zone cluster": ("cr",),
    "The Banco Central de Nicaragua and the deslizamiento": ("ni",),
    "The Nicaraguan gold concessionaires and the artisanal miners": ("ni",),
    "The Nicaraguan state as canal concessionaire and statistical publisher": ("ni",),
    "The Banco Central de Reserva de El Salvador": ("sv",),
    "The Salvadoran state as bitcoin holder and sovereign debtor": ("sv",),
    "The Salvadoran, Guatemalan and Honduran remittance households": ("sv", "gt", "hn", "ni"),
    "SIECA and the Central American customs union": ("ca",),
    "The Banco Centroamericano de Integracion Economica as regional creditor": ("ca",),
    "The liner operators, gas charterers and dry-bulk shippers who buy canal slots": ("ca",),
}


def actors_of(cc: str) -> tuple[str, ...]:
    """Every actor this pack files under one jurisdiction. The floor is three per jurisdiction
    and the tests count it here rather than reading the prose."""
    code = str(cc).lower()
    return tuple(name for name, codes in ACTOR_JURISDICTIONS.items() if code in codes)

# --------------------------------------------------------------------------- domains
#: EIGHTEEN DOMAINS. Each names its research objects, the STATES it conditions on (these are the
#: `condition` half of every cell `cells()` mints), the executable instruments it may touch and
#: at least two negative controls -- without which an effect cannot be told apart from the desk's
#: own sampling. EVERY JURISDICTION OWNS AT LEAST TWO (`DOMAIN_JURISDICTIONS` is the map and the
#: tests count it), and the canal owns four because it is the reason the pack exists.
DOMAINS: tuple[dict[str, Any], ...] = (
    {"id": "CA-A", "title": "The Panama Canal constraint: draft, transits and the advisory clock",
     "objects": ("the advisories to shipping and their stated EFFECTIVE dates",
                 "the maximum authorised draft as a dated step series",
                 "the bookable transit slots per day",
                 "the anchorage queue at Balboa and Cristobal"),
     "conditions": ("the constraint severity bucket from the published slot count "
                    "(`constraint_severity`: NONE, MILD, SEVERE, EXTREME)",
                    "whether the day is the ANNOUNCEMENT or the EFFECTIVE date, which are "
                    "different events with different information",
                    "the direction of the step: a tightening or a restoration",
                    "the season: the December-to-April dry season against the wet half"),
     "instruments": ("CORN", "WHEAT", "SOYBEAN", "XNGUSD", "XTIUSD"),
     "controls": ("the Suez and Bab el-Mandeb daily transit series over the same days, which is "
                  "the substitution counterfactual and the reason this domain is not measuring "
                  "global freight",
                  "the US Gulf-to-Pacific-Northwest export routing share, which does not use "
                  "the canal at all",
                  "matched calendar windows in unconstrained years with the same ENSO state"),
     "notes": "THE PACK'S PRIMARY DOMAIN. A global chokepoint operator publishing its own "
              "binding constraint in advance, with an effective date, against cargoes the "
              "broker quotes"},
    {"id": "CA-B", "title": "The transit slot auction and the toll structure",
     "objects": ("the auction clearing prints", "the number of slots released to auction",
                 "the booking-segment rules and their changes",
                 "the toll tariff revisions"),
     "conditions": ("whether an auction cleared above or below its own trailing median",
                    "the vessel class that won: a gas carrier, a container ship or a bulker",
                    "the bookable slot count in force that week"),
     "instruments": ("XNGUSD", "XTIUSD", "XBRUSD", "CORN", "SOYBEAN"),
     "controls": ("weeks with the same slot count and no auction, which separates the SCARCITY "
                  "PRICE from the scarcity",
                  "the Suez transit fee and the Red Sea diversion window in the same weeks",
                  "a randomised-week null over the same constrained period"),
     "notes": "the clearing price is a PRICED OPTION on the constraint and the sample is small; "
              "the cells say so rather than pretending to a long history"},
    {"id": "CA-C", "title": "Gatun Lake hydrology and the ENSO clock behind the constraint",
     "objects": ("the daily Gatun and Alhajuela levels in feet PLD",
                 "basin rainfall and the Rio Chagres inflow",
                 "the competing municipal water draw",
                 "the Rio Indio reservoir project as the structural answer"),
     "conditions": ("the lake level relative to the 87.5 ft operating maximum",
                    "the ENSO phase: El Nino, La Nina or neutral",
                    "the dry season (December to April) against the wet half",
                    "whether the level is falling through a threshold or recovering through it"),
     "instruments": ("CORN", "SOYBEAN", "WHEAT", "XNGUSD"),
     "controls": ("the same ENSO phases in years with no draft restriction, which separates the "
                  "WEATHER from the CONSTRAINT",
                  "Suez transits over the same months",
                  "a matched-month null on the grain legs"),
     "notes": "THE LEADING HALF of CA-A: the lake falls for months before an advisory binds, so "
              "this domain is forecastable where the advisory domain is an event study"},
    {"id": "CA-D", "title": "Chokepoint substitution: Panama against Suez and Bab el-Mandeb",
     "objects": ("the three chokepoints' daily transit counts on one definition",
                 "the Cape of Good Hope routing share and the voyage days it adds",
                 "the vessel-class composition of each route",
                 "the liner surcharges announced for each"),
     "conditions": ("which chokepoints were constrained: Panama only, the Red Sea only, or both",
                    "the vessel class the substitution applies to",
                    "the direction of trade: Asia-to-US-East-Coast against US-Gulf-to-Asia"),
     "instruments": ("XBRUSD", "XTIUSD", "XNGUSD", "US500", "CORN", "USDCNH"),
     "controls": ("the BOTH-CONSTRAINED window of 2023-2024, which is the confound and is "
                  "carried explicitly so no cell can quietly attribute it to Panama",
                  "periods with neither constrained and the same bunker price",
                  "the Cape routing share as the residual route"),
     "notes": "THE CONTROL DOMAIN, NAMED AS THE BRIEF REQUIRES: when one chokepoint closes, the "
              "other's traffic is the counterfactual. 2023-2024 constrained both at once for "
              "unrelated reasons, which makes the pair a control only if BOTH series are "
              "carried -- and a confound if either is dropped"},
    {"id": "CA-E", "title": "The washed-arabica belt: five national export counts on one "
                            "harvest year",
     "objects": ("the five institutes' monthly export volumes",
                 "the harvest-year accumulation against the prior crop",
                 "the ICO Other Milds group indicator",
                 "the regional origin split within Guatemala"),
     "conditions": ("the harvest phase (`harvest_phase`: opening, export peak, lean, flowering)",
                    "whether the month's belt total beat or missed its own trailing dispersion",
                    "which origins drove it: Honduras alone, or the belt together",
                    "the crop year's position: first year after a shock, or a normal year"),
     "instruments": ("COFARA", "COFROB", "USDBRL"),
     "controls": ("COFROB as the non-belt control, because this belt grows almost no robusta -- "
                  "a move in both is 'coffee' and a move in arabica alone is 'this belt'",
                  "the Brazilian crop and the ICO Brazilian Naturals indicator over the same "
                  "months",
                  "the same harvest months in years with no declared shock"),
     "notes": "FIVE COUNTED SERIES ON ONE CALENDAR. Every institute issues the export permit, so "
              "the number is a count and not a survey"},
    {"id": "CA-F", "title": "Roya, hurricanes and the two-origin substitution against Brazil",
     "objects": ("the declared rust, hurricane and drought episodes",
                 "the replanting cycles that follow an epidemic",
                 "the Brazilian frost and drought windows as the control",
                 "the arabica differential structure the shocks move"),
     "conditions": ("whether the window is an ISTHMUS shock or a BRAZILIAN one -- the tables "
                    "keep them apart on purpose",
                    "the shock type: biological, meteorological or labour",
                    "the harvest phase the shock landed in",
                    "whether both origins were shocked in the same crop year"),
     "instruments": ("COFARA", "COFROB", "SUGAR"),
     "controls": ("the Brazilian shock windows with no isthmus event, which is the two-origin "
                  "substitution's negative leg",
                  "SUGAR as a same-region, same-weather, different-crop placebo",
                  "matched crop-year windows with neither origin shocked"),
     "notes": "THE `br` INTERACTION MADE TESTABLE: an origin shock here and an origin shock "
              "there move the same contract from opposite ends of the substitution, and the "
              "tables separate them so a study cannot pool the two"},
    {"id": "CA-G", "title": "Dollarisation as a controlled experiment",
     "objects": ("Panama's 1904 parity with no central bank at all",
                 "El Salvador's 2001 dollarisation with a central bank and no instrument",
                 "the four neighbours with their own money and four different regimes",
                 "the FOMC decisions that are the policy rate of two of the six"),
     "conditions": ("the jurisdiction's regime class: DOLLAR_NO_CENTRAL_BANK, "
                    "DOLLAR_WITH_TOOTHLESS_BANK, MANAGED_FLOAT, BAND, CRAWL_AT_ZERO or FLOAT",
                    "whether the day carries an FOMC decision, which IS the policy event for "
                    "the two dollarised economies",
                    "the global risk state read off US500",
                    "whether a domestic fiscal or credit event landed in the same week"),
     "instruments": ("USDMXN", "USDBRL", "US500", "XAUUSD"),
     "controls": ("Costa Rica, the fully instrumented floater on the same isthmus with the same "
                  "coffee and the same drought -- the closest thing to a matched control a "
                  "monetary study will ever get",
                  "the four non-dollarised neighbours as a group against the two dollarised",
                  "FOMC days with no isthmus event at all"),
     "notes": "SIX NEIGHBOURS, ONE TRADE STRUCTURE, FOUR MONETARY REGIMES. The executable legs "
              "are regional and US, because not one of the six currencies is quoted"},
    {"id": "CA-H", "title": "Four monetary regimes and their published rules",
     "objects": ("Banguat's stated FX participation rule and its trigger arithmetic",
                 "the BCH allocation auction's offered-minus-bid shortage",
                 "the BCCR's TPM and its disclosed MONEX participation",
                 "the BCN's published slide rate and its step to zero"),
     "conditions": ("whether the Guatemalan participation rule was triggered that day",
                    "the Honduran auction shortage bucket",
                    "the Nicaraguan slide-rate regime: 5%, 3%, 2% or ZERO",
                    "whether a policy decision landed in the same week"),
     "instruments": ("USDMXN", "USDBRL", "US500"),
     "controls": ("the same states built on BLOCK-SHUFFLED rule-trigger and auction series, "
                  "which is the null for a state variable",
                  "Costa Rica's float over the same days",
                  "regional EM days with no isthmus monetary event"),
     "notes": "none of the four currencies is executable, so this domain mints CONDITIONERS: it "
              "says when the regional legs should be read as carrying the isthmus"},
    {"id": "CA-I", "title": "Remittances as a US labour-market flow with dated policy shocks",
     "objects": ("the four monthly remittance prints and their four different lags",
                 "the corridor cost series by corridor",
                 "the five Mother's Days and the December corridor",
                 "the dated US enforcement and immigration acts"),
     "conditions": ("the receiving jurisdiction's regime (`remittance_regime`: RECEIVER, "
                    "MARGINAL or SENDER_OR_TRANSIT)",
                    "whether the month contains a dated US policy act",
                    "whether the month contains that country's own Mother's Day",
                    "the surprise against the trailing twelve-month path"),
     "instruments": ("USDMXN", "US500", "US30"),
     "controls": ("Costa Rica and Panama, the two SENDER or transit economies on the same "
                  "isthmus, which is the within-region control for every receiver claim",
                  "Mexican remittances over the same months, separating 'the US labour market' "
                  "from 'this isthmus'",
                  "matched months with no policy act and no Mother's Day"),
     "notes": "the highest-frequency link between the US cycle and this region, and the one with "
              "a dated policy variable on the sending end"},
    {"id": "CA-J", "title": "El Salvador: the Bitcoin Law and the sovereign-credit sequence",
     "objects": ("the gazetted Bitcoin Law, its effective date and its 2025 amendment",
                 "the January 2023 maturity paid in full and the buybacks after it",
                 "the IMF staff-level agreement and the programme conditions",
                 "the publicly reported sovereign holding"),
     "conditions": ("the event class: legislation, maturity, programme milestone or amendment",
                    "whether the act EXPANDED or NARROWED the bitcoin programme",
                    "the sovereign's credit state at the time: distressed or performing",
                    "the global risk state on the day"),
     "instruments": ("BTCUSD", "US500", "XAUUSD"),
     "controls": ("matched windows with an equivalent global risk move and no Salvadoran act",
                  "the other five jurisdictions' credit events in the same months",
                  "a randomised-date null over the same calendar"),
     "notes": "MANDATE BOUNDARY, STATED AND HELD: this is a SOVEREIGN POLICY and FISCAL event "
              "series routed into the broker's own BTCUSD CFD and the risk legs. No "
              "crypto-exchange universe is hunted, no venue order book or feed is a source, and "
              "ACCESS_CONSTRAINTS says so in full"},
    {"id": "CA-K", "title": "Cobre Panama: a judicial shutdown of a top-twenty copper mine",
     "objects": ("Ley 406, the constitutional challenge and the Supreme Court ruling",
                 "the executive closure order and the preservation regime",
                 "the concentrate stockpile and its export permits",
                 "the 2025 restart process and the rating actions that bracket it"),
     "conditions": ("the event class: legislative, judicial, executive or negotiated",
                    "whether the act REMOVED or RESTORED supply",
                    "the LME and COMEX inventory state when the act landed",
                    "whether a Chilean or Peruvian supply event fell in the same window"),
     "instruments": ("XCUUSD", "US500"),
     "controls": ("Chilean and Peruvian supply events in the same windows, which separate "
                  "'a mine closed' from 'Andean supply'",
                  "Chinese demand prints in the same months with no Panamanian act",
                  "matched windows with an equivalent copper move and no judicial event"),
     "notes": "A JUDICIAL SUPPLY SHOCK is a category this desk has almost no other instance of: "
              "not a strike, not a drought, not a blockade, but a constitutional ruling"},
    {"id": "CA-L", "title": "Panama as flag state, banking centre and free zone",
     "objects": ("the registered fleet and the de-flagging actions",
                 "the Centro Bancario Internacional's liquidity and deposit base",
                 "the Colon Free Zone's monthly re-exports",
                 "the transparency listing and de-listing acts"),
     "conditions": ("whether the month contains a de-flagging or a listing act",
                    "the banking system's liquidity ratio relative to its own trailing band",
                    "the free zone's re-export growth against its own trailing path"),
     "instruments": ("XBRUSD", "XTIUSD", "US500", "XAUUSD", "USDCNH"),
     "controls": ("the other open registries' fleet moves over the same months",
                  "regional credit conditions with no Panamanian banking event",
                  "matched months with an equivalent US financial-conditions move"),
     "notes": "THE FREE ZONE'S RE-EXPORTS LEAD ITS CUSTOMERS' OWN IMPORT PRINTS, which makes "
              "this domain a regional demand nowcast that no sibling pack carries"},
    {"id": "CA-M", "title": "The zafra and the banana chain",
     "objects": ("the Guatemalan cane grind and the season's export programme",
                 "the November-to-May harvest window and its boundaries",
                 "the Honduran and Guatemalan banana volumes",
                 "the mills' cogeneration into the national grid"),
     "conditions": ("whether the month is inside the zafra window",
                    "the sucrose content signal in a dry or an excessively wet year",
                    "the ENSO phase during cane growth",
                    "whether the world market was in surplus or deficit that season"),
     "instruments": ("SUGAR", "CORN", "COTTON"),
     "controls": ("the Brazilian and Indian crops over the same seasons, which set the world "
                  "price this origin takes",
                  "CORN as the same-farm-economics, different-market placebo",
                  "the same harvest months in neutral ENSO years"),
     "notes": "a top-five raw sugar exporter with a dated harvest window; the season, not the "
              "quarter, is the sampling frame"},
    {"id": "CA-N", "title": "CAFTA-DR, the maquila and the yarn-forward cotton chain",
     "objects": ("the yarn-forward rule of origin and its administration",
                 "monthly maquila export values from Honduras, Guatemala and El Salvador",
                 "US apparel import statistics by partner",
                 "the free-zone employment series"),
     "conditions": ("the US retail cycle state read off US30 and US500",
                    "whether the season is a pre-season build or a replenishment month",
                    "whether a re-sourcing announcement landed in the window",
                    "the Mexican share of the same US import line"),
     "instruments": ("COTTON", "US500", "US30", "USDMXN"),
     "controls": ("the Asian share of the same US apparel import line, which is what the "
                  "isthmus is actually competing against",
                  "US mill use and the Chinese cotton import prints",
                  "matched months with an equivalent US retail print and no isthmus event"),
     "notes": "THE RULE OF ORIGIN IS THE MECHANISM: yarn-forward is what ties a Honduran plant's "
              "order book to US cotton rather than to the cheapest cotton in the world"},
    {"id": "CA-O", "title": "Costa Rica: nearshoring, medical devices and the fiscal "
                            "consolidation",
     "objects": ("monthly free-zone exports by sector",
                 "the announced investment pipeline",
                 "the fiscal rule and the primary-balance path from 2018",
                 "the TPM and the MONEX rate as the policy half"),
     "conditions": ("whether the month contains a dated investment announcement",
                    "the free-zone export surprise against its trailing path",
                    "the fiscal rule's binding state that year"),
     "instruments": ("US500", "US30", "USDMXN", "USDCNH"),
     "controls": ("Mexican manufacturing exports over the same months, which is the nearshoring "
                  "competitor and the direct `mx` interaction",
                  "US industrial production with no Costa Rican event",
                  "the same months before the 2018 fiscal reform"),
     "notes": "the isthmus's one successful fiscal consolidation and its one advanced "
              "manufacturing cluster, in the jurisdiction that is also the monetary control"},
    {"id": "CA-P", "title": "Nicaragua: the repealed canal, the gold and the narrowed statistics",
     "objects": ("the 2013 concession and its 2024 repeal as gazetted acts",
                 "the monthly gold export volume and value",
                 "the published rate table and its step to zero",
                 "the mirror-customs reconstruction of what is not published"),
     "conditions": ("whether the month contains a gazetted concession or monetary act",
                    "the slide-rate regime in force",
                    "whether the direct series and the mirror-customs series agree"),
     "instruments": ("XAUUSD", "SUGAR", "CORN"),
     "controls": ("the other five jurisdictions' export series over the same months, where "
                  "publication has not narrowed",
                  "the world gold price with no Nicaraguan act",
                  "the direct-versus-mirror discrepancy as its own measurement control"),
     "notes": "AN HONEST SMALL-PRODUCER DOMAIN: Nicaragua is a price taker, so the cells run "
              "from the world price to the country's capacity and not the other way, and the "
              "measurement substitutes are declared in NO_LAWFUL_GROUND"},
    {"id": "CA-Q", "title": "The dry corridor drought as a published agricultural-risk series",
     "objects": ("the FEWS NET seasonal assessments and the national meteorological bulletins",
                 "the canicula (the mid-season dry spell) and its length",
                 "basic-grain loss estimates across the Corredor Seco",
                 "the coffee flowering and filling window the deficit lands in"),
     "conditions": ("the ENSO phase in the growing season",
                    "whether a FEWS NET assessment moved a phase classification that month",
                    "the crop stage the deficit landed in: flowering, filling or harvest",
                    "how many of the four dry-corridor jurisdictions were affected at once"),
     "instruments": ("CORN", "COFARA", "SUGAR", "WHEAT"),
     "controls": ("WHEAT as the not-grown-here placebo: the isthmus imports it and grows none, "
                  "so a dry-corridor condition that moves wheat is measuring global weather",
                  "the same ENSO phases in years with no phase-classification move",
                  "South American weather windows with no Central American deficit"),
     "notes": "A PUBLISHED, DATED AGRICULTURAL-RISK SERIES that leads the harvest by months and "
              "that essentially no systematic desk reads"},
    {"id": "CA-R", "title": "The isthmus calendar: Semana Santa, five independence days and the "
                            "Monday shift",
     "objects": ("Semana Santa, the one block that closes all six at once",
                 "15 September as ONE date and FIVE closures with Panama open beside it",
                 "the Honduran Feriado Morazanico as a derived four-day block",
                 "Costa Rica's Ley de Traslado Monday shift"),
     "conditions": ("how many of the six are closed that day (`shared_closures`)",
                    "whether the closure is SHARED or single-jurisdiction",
                    "whether it is a derived block (Morazanico, Monday shift) or a fixed date",
                    "the harvest phase the closure lands in, because a closed customs post in "
                    "the export peak is not the same as one in the lean months"),
     "instruments": ("CORN", "COFARA", "SUGAR", "US500"),
     "controls": ("PANAMA, which is open on 15 September while five neighbours are shut -- a "
                  "built-in same-region control that no calendar study of this isthmus should "
                  "ever have to construct",
                  "the matched weekday twenty-six weeks away",
                  "the same dates in years before the Morazanico and the Monday shift existed"),
     "notes": "the only region on this desk where one date closes five countries and leaves the "
              "sixth open, which makes the control free"},
)

#: WHICH JURISDICTIONS EACH DOMAIN BELONGS TO. The brief's floor is two domains of its own per
#: jurisdiction and the tests COUNT this map.
DOMAIN_JURISDICTIONS: dict[str, tuple[str, ...]] = {
    "CA-A": ("pa",), "CA-B": ("pa",), "CA-C": ("pa",), "CA-D": ("pa",),
    "CA-E": ("gt", "hn", "cr", "ni", "sv"), "CA-F": ("gt", "hn", "ni", "sv", "cr"),
    "CA-G": ("pa", "sv", "cr", "gt", "hn", "ni"), "CA-H": ("gt", "hn", "cr", "ni"),
    "CA-I": ("gt", "hn", "sv", "ni"), "CA-J": ("sv",), "CA-K": ("pa",), "CA-L": ("pa",),
    "CA-M": ("gt", "hn", "ni", "sv"), "CA-N": ("hn", "gt", "sv"), "CA-O": ("cr",),
    "CA-P": ("ni",), "CA-Q": ("gt", "hn", "sv", "ni"),
    "CA-R": ("pa", "gt", "hn", "cr", "ni", "sv"),
}


def domains_of(cc: str) -> tuple[str, ...]:
    """Every domain this pack files under one jurisdiction. The floor is two per jurisdiction."""
    code = str(cc).lower()
    return tuple(did for did, codes in DOMAIN_JURISDICTIONS.items() if code in codes)


# --------------------------------------------------------------------------- miners
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    {"name": "ca_canal_constraint_windows", "domain_ids": ("CA-A", "CA-C"), "kind": "event",
     "cadence_s": 21600.0, "steerable": True, "wired": False,
     "entry": "countries.central_america.pack:canal_constraint_windows",
     "needs": ("DRAFT_STEPS and SLOT_STEPS joined to their advisory numbers",
               "the ACP daily lake level series",
               "CORN, SOYBEAN, WHEAT, XNGUSD, XTIUSD D1 bars"),
     "notes": "THE PACK'S PRIMARY MINER: the published constraint as a dated step function, "
              "with the announcement and effective dates kept apart"},
    {"name": "ca_canal_auction_prints", "domain_ids": ("CA-B",), "kind": "event",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.central_america.pack:canal_auction_prints",
     "needs": ("AUCTION_PRINTS with each result notice attached",
               "XNGUSD, XTIUSD, CORN, SOYBEAN D1 bars"),
     "notes": "the scarcity price; the sample is small and the miner reports that rather than "
              "padding it"},
    {"name": "ca_chokepoint_substitution", "domain_ids": ("CA-D",), "kind": "transfer",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.central_america.pack:chokepoint_substitution",
     "needs": ("the IMF PortWatch daily transit series for all three chokepoints",
               "XBRUSD, XTIUSD, XNGUSD, US500 D1 bars"),
     "notes": "the control miner: it refuses to attribute a freight move to Panama without the "
              "Suez and Bab el-Mandeb series and says UNMEASURED when they are absent"},
    {"name": "ca_coffee_export_calendar", "domain_ids": ("CA-E", "CA-F"), "kind": "release",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.central_america.pack:coffee_export_calendar",
     "needs": ("the five institutes' monthly export series keyed on the harvest year",
               "the ICO group indicators", "COFARA, COFROB D1 bars"),
     "notes": "the harvest-year frame and the declared shock windows, with the Brazilian rows "
              "kept separate so a study cannot pool the two origins"},
    {"name": "ca_monetary_regime_experiment", "domain_ids": ("CA-G", "CA-H"), "kind": "macro",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.central_america.pack:monetary_regime_experiment",
     "needs": ("the four policy-rate calendars once published",
               "the Banguat rule trigger and the BCH auction series",
               "USDMXN, USDBRL, US500 D1 bars"),
     "notes": "the six-jurisdiction regime table as a conditioning state; the currencies "
              "themselves are absent and the miner never pretends otherwise"},
    {"name": "ca_remittance_season", "domain_ids": ("CA-I",), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.central_america.pack:remittance_season",
     "needs": ("the four monthly remittance series with their four different lags",
               "US_POLICY_ACTS", "USDMXN, US500, US30 D1 bars"),
     "notes": "five Mother's Days and a December corridor, derived rather than typed for "
              "Honduras, plus the dated US acts on the sending end"},
    {"name": "ca_sovereign_policy_timestamps", "domain_ids": ("CA-J", "CA-K", "CA-P"),
     "kind": "event", "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.central_america.pack:sovereign_policy_timestamps",
     "needs": ("POLICY_EVENTS with gazette citations attached",
               "BTCUSD, XCUUSD, XAUUSD, US500 H1 bars"),
     "notes": "every row PRESS_REPORTED until a gazette citation is joined; the mandate boundary "
              "on the Salvadoran rows is stated in the payload itself"},
    {"name": "ca_drought_risk_windows", "domain_ids": ("CA-Q", "CA-M"), "kind": "macro",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.central_america.pack:drought_risk_windows",
     "needs": ("FEWS NET phase classifications and the national bulletins",
               "the ENSO state", "CORN, COFARA, SUGAR, WHEAT D1 bars"),
     "notes": "the dry corridor as a published risk series, with WHEAT carried as the "
              "not-grown-here placebo"},
    {"name": "ca_isthmus_calendar", "domain_ids": ("CA-R",), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": False, "wired": False,
     "entry": "countries.central_america.pack:isthmus_calendar",
     "needs": ("`region_holidays`, `shared_closures`, `morazanico`, `monday_shift`",
               "CORN, COFARA, SUGAR, US500 D1 bars"),
     "notes": "six calendars, one Easter block, five independence closures and one neighbour "
              "open beside them"},
    {"name": "ca_transmission_seeds",
     "domain_ids": ("CA-A", "CA-D", "CA-E", "CA-I", "CA-K", "CA-N", "CA-Q"),
     "kind": "transfer", "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.central_america.pack:transmission_seeds",
     "needs": ("TRANSMISSION_EDGES_SEED", "INTERACTIONS"),
     "notes": "the pack's own map as HYPOTHESIS discoveries, deduplicated by the registry"},
)
MINER_DOMAINS: dict[str, tuple[str, ...]] = {
    "central_bank_surprise": ("CA-H", "CA-G"), "release_surprise": ("CA-E", "CA-I"),
    "calendar_settlement": ("CA-R", "CA-M"), "holiday_liquidity": ("CA-R",),
    "positioning": ("CA-E", "CA-M"), "carry_funding": ("CA-G", "CA-L"),
    "corporate_flow": ("CA-N", "CA-O"), "institutional_flow": ("CA-L", "CA-J"),
    "equity_mechanics": ("CA-O",), "derivatives_expiry": ("CA-B",),
    "failure": ("CA-K", "CA-P"), "residual": ("CA-G", "CA-L"),
    "transfer": ("CA-D", "CA-F"), "scouts": ("CA-A", "CA-C", "CA-Q"),
    "session_microstructure": ("CA-R", "CA-A"),
}

# --------------------------------------------------------------------------- transmission
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    {"id": "CA-E1", "source": "An ACP advisory cutting the maximum authorised draft",
     "target": "SOYBEAN", "targets": ("SOYBEAN", "CORN", "WHEAT"), "to_country": "global",
     "sign": "+",
     "mechanism": "a draft cut is a load restriction: a Panamax bulker that cannot load to its "
                  "marks carries thousands of tonnes less for the same voyage cost, so the "
                  "freight per tonne of US Gulf grain to Asia rises and the delivered basis in "
                  "Asia widens against the Pacific Northwest alternative",
     "horizon": "0 to 20 sessions", "horizon_class": "multi_day", "lag_days": 2.0,
     "actor": "the ACP and the dry-bulk operators lifting US Gulf grain",
     "constraint": "the Pacific Northwest route is the only near substitute and its rail and "
                   "elevator capacity is finite",
     "condition": "an advisory with an effective date, conditioned on the severity bucket",
     "control": "the Suez and Bab el-Mandeb transit series in the same days; the US Gulf-to-PNW "
                "export inspection share",
     "falsifier": "draft-cut windows match the matched-period control on the grain legs once "
                  "the routing share and the global freight state are conditioned on",
     "evidence": "HYPOTHESIS"},
    {"id": "CA-E2", "source": "A cut in the ACP's bookable transit slots per day",
     "target": "XNGUSD", "targets": ("XNGUSD", "XTIUSD", "XBRUSD"), "to_country": "global",
     "sign": "+",
     "mechanism": "US Gulf LPG and LNG to Asia is the cargo with the least route flexibility "
                  "and the highest cost of a missed loading window; when slots are rationed "
                  "that trade either pays the auction or sails the Cape, and both raise the "
                  "delivered cost of the US molecule against its competitors",
     "horizon": "0 to 20 sessions", "horizon_class": "multi_day", "lag_days": 3.0,
     "actor": "the gas charterers and the US Gulf export terminals",
     "constraint": "no pipeline, no alternative canal, and a Cape voyage that adds ten to "
                   "fourteen days",
     "condition": "the slot count below baseline (`is_canal_constrained`) with the severity "
                  "bucket as the intensity",
     "control": "the Suez transit series; the same slot counts in the recovery phase, when the "
                "direction of the step is the opposite",
     "falsifier": "slot-count windows carry no information about the gas leg beyond what US "
                  "storage and the Asian-to-European spread already carry",
     "evidence": "HYPOTHESIS"},
    {"id": "CA-E3", "source": "A transit auction clearing far above its trailing median",
     "target": "XNGUSD", "targets": ("XNGUSD", "XTIUSD"), "to_country": "global", "sign": "+",
     "mechanism": "the clearing price is what the marginal cargo will pay to avoid the queue; a "
                  "print near four million dollars is the market pricing a loading window, and "
                  "it is a scarcity signal that leads the physical effect rather than lagging it",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "the LPG and LNG charterers who win these auctions",
     "constraint": "a laycan that does not move and a charter that penalises a miss",
     "condition": "an auction print above its trailing median with the slot count held fixed",
     "control": "weeks with the same slot count and no auction, which separates the price from "
                "the scarcity it prices",
     "falsifier": "auction prints add nothing to the gas leg beyond the slot count itself",
     "evidence": "HYPOTHESIS"},
    {"id": "CA-E4", "source": "A Red Sea or Suez constriction with Panama unconstrained",
     "target": "XBRUSD", "targets": ("XBRUSD", "XTIUSD", "US500", "USDCNH"),
     "to_country": "global", "sign": "+",
     "mechanism": "THE SUBSTITUTION CONTROL AS ITS OWN EDGE. When one chokepoint constricts and "
                  "the other does not, traffic and freight reallocate in a measurable "
                  "direction; running this edge is what makes the Panama edges attributable "
                  "rather than a reading of global freight",
     "horizon": "0 to 30 sessions", "horizon_class": "multi_day", "lag_days": 5.0,
     "actor": "the liner operators and tanker charterers choosing a route",
     "constraint": "the Cape adds voyage days and absorbs fleet capacity, which is the price of "
                   "the substitution",
     "condition": "one chokepoint constrained and the other not, from the PortWatch series",
     "control": "the BOTH-CONSTRAINED window of 2023-2024, carried explicitly as the confound",
     "falsifier": "single-chokepoint constrictions produce no reallocation distinguishable from "
                  "the neither-constrained baseline",
     "evidence": "MEASURED_ELSEWHERE"},
    {"id": "CA-E5", "source": "The five institutes' combined monthly washed-arabica exports",
     "target": "COFARA", "targets": ("COFARA", "COFROB"), "to_country": "global", "sign": "-",
     "mechanism": "the belt is a large share of world washed arabica and each institute counts "
                  "what it permitted to leave; a combined monthly total below its own trailing "
                  "dispersion is a real shortfall in the exportable supply of the grade the "
                  "contract is written on",
     "horizon": "1 to 3 months", "horizon_class": "multi_day", "lag_days": 20.0,
     "actor": "ANACAFE, IHCAFE, ICAFE, CONACAFE and the Consejo Salvadoreno del Cafe",
     "constraint": "an export permit counts what SHIPS, so a crop held back is invisible until "
                   "it moves",
     "condition": "the belt total against its trailing dispersion, keyed on the harvest year",
     "control": "COFROB, which this belt barely grows, as the non-belt leg; the ICO Brazilian "
                "Naturals indicator in the same months",
     "falsifier": "belt export surprises carry no COFARA information beyond the ICO group "
                  "indicators and the Brazilian crop",
     "evidence": "HYPOTHESIS"},
    {"id": "CA-E6", "source": "A declared rust, hurricane or drought episode in the belt",
     "target": "COFARA", "targets": ("COFARA", "COFROB"), "to_country": "global", "sign": "+",
     "mechanism": "a biological or meteorological shock to a washed-arabica origin removes "
                  "supply of a specific grade for one to three crop years, and the replanting "
                  "that follows changes the varietal mix and the yield profile for a decade",
     "horizon": "1 to 12 months", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "the growers, the cooperatives and the institutes that administer replanting",
     "constraint": "a coffee tree takes three to four years to bear, so the recovery is slow "
                   "and the shock is persistent",
     "condition": "a declared isthmus shock window (`origin_shock_days`), excluding the "
                  "Brazilian control rows",
     "control": "the Brazilian frost and drought windows with no isthmus event; SUGAR as the "
                "same-region, different-crop placebo",
     "falsifier": "isthmus shock windows produce no arabica response distinguishable from the "
                  "same windows' global weather state",
     "evidence": "HYPOTHESIS"},
    {"id": "CA-E7", "source": "A Brazilian frost or drought with the isthmus crop intact",
     "target": "COFARA", "targets": ("COFARA", "USDBRL", "COFROB"), "to_country": "global",
     "sign": "+",
     "mechanism": "THE TWO-ORIGIN SUBSTITUTION, RUN FROM THE OTHER END. A Brazilian natural "
                  "shortfall pushes roasters toward washed origins, which widens the Central "
                  "American differential even when the belt's own volume is unchanged -- the "
                  "half of the mechanism a single-origin study cannot see",
     "horizon": "1 to 6 months", "horizon_class": "multi_day", "lag_days": 5.0,
     "actor": "the roasters reformulating blends and the Brazilian producers",
     "constraint": "washed and natural coffees are imperfect substitutes in a blend, so the "
                   "substitution is partial and shows in the DIFFERENTIAL more than in the level",
     "condition": "a declared Brazilian shock row with no concurrent isthmus row",
     "control": "windows with both origins shocked, and windows with neither",
     "falsifier": "Brazilian shocks move the contract identically whether or not the isthmus "
                  "crop is intact, which would mean the substitution is not priced",
     "evidence": "HYPOTHESIS"},
    {"id": "CA-E8", "source": "A judicial or executive act removing or restoring Cobre Panama",
     "target": "XCUUSD", "targets": ("XCUUSD",), "to_country": "global", "sign": "+",
     "mechanism": "roughly 1.5% of world mined copper, in CONCENTRATE, removed by a "
                  "constitutional ruling with no substitute mine able to replace it inside a "
                  "year; the concentrate market tightened far more than the refined one, which "
                  "the refined CFD expresses only partially and this edge says so",
     "horizon": "0 to 60 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "the Panamanian Supreme Court, the executive and Minera Panama",
     "constraint": "a voided concession cannot be revived by the company alone and an idled "
                   "plant does not restart in a quarter",
     "condition": "a gazetted act, conditioned on whether it REMOVED or RESTORED supply",
     "control": "Chilean and Peruvian supply events in the same windows; Chinese demand prints "
                "with no Panamanian act",
     "falsifier": "the judicial timestamps produce no copper response distinguishable from the "
                  "matched-window control once Andean supply and Chinese demand are conditioned",
     "evidence": "HYPOTHESIS"},
    {"id": "CA-E9", "source": "The Guatemalan zafra's grind and export programme",
     "target": "SUGAR", "targets": ("SUGAR",), "to_country": "global", "sign": "-",
     "mechanism": "Guatemala is one of the largest raw sugar exporters and its season runs "
                  "November to May; a grind that disappoints on tonnage or on sucrose content "
                  "is a real reduction in the exportable surplus inside a dated window",
     "horizon": "1 to 3 months", "horizon_class": "multi_day", "lag_days": 15.0,
     "actor": "ASAZGUA and the mills",
     "constraint": "cane must be crushed within days of cutting, so the season cannot be "
                   "extended or deferred",
     "condition": "inside the zafra window, conditioned on the ENSO state during cane growth",
     "control": "the Brazilian and Indian crops over the same seasons; CORN as the "
                "same-farm-economics placebo",
     "falsifier": "zafra outcomes carry no SUGAR information beyond the Brazilian and Indian "
                  "crops and the world balance",
     "evidence": "HYPOTHESIS"},
    {"id": "CA-E10", "source": "A monthly remittance print against its trailing path, or a "
                               "dated US enforcement act",
     "target": "USDMXN", "targets": ("USDMXN", "US500", "US30"), "to_country": "global",
     "sign": "+",
     "mechanism": "remittances are a fifth to a quarter of GDP in four of the six and they are "
                  "a direct function of a US labour market and a US enforcement posture; a "
                  "dated administrative act on the sending end is a dated shock to four "
                  "countries' largest foreign-exchange earner at once",
     "horizon": "1 to 3 months", "horizon_class": "multi_day", "lag_days": 12.0,
     "actor": "the migrant senders, the operators and the four receiving central banks",
     "constraint": "the receiving countries influence neither the US labour market nor the "
                   "enforcement posture",
     "condition": "a print surprise against the trailing twelve months, or a month containing a "
                  "dated US act",
     "control": "Mexican remittances over the same months, separating 'the US labour market' "
                "from 'this isthmus'; Costa Rica and Panama as the sender-side control",
     "falsifier": "remittance surprises add nothing to the US legs beyond US payrolls, which is "
                  "likely -- the informative direction is from the ACT to the FLOW",
     "evidence": "HYPOTHESIS"},
    {"id": "CA-E11", "source": "A gazetted Salvadoran act expanding or narrowing the bitcoin "
                               "programme, or an IMF programme milestone",
     "target": "BTCUSD", "targets": ("BTCUSD", "US500"), "to_country": "global", "sign": "+",
     "mechanism": "a sovereign adopting or abandoning legal-tender status for an asset is a "
                  "policy fact about that asset's institutional acceptance; it is routed here "
                  "through the broker's own CFD and through the risk legs, and it is a FISCAL "
                  "and LEGAL event series in every other respect",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 0.0,
     "actor": "the Salvadoran legislature and executive, and the IMF",
     "constraint": "a dollarised sovereign under a programme trades policy latitude for "
                   "financing, which is what made the 2025 amendment possible",
     "condition": "a gazetted act, conditioned on whether it expanded or narrowed the programme",
     "control": "matched windows with an equivalent global risk move and no Salvadoran act",
     "falsifier": "Salvadoran legal acts produce no BTCUSD response distinguishable from a "
                  "matched-window placebo -- the likely null and the one worth settling",
     "evidence": "HYPOTHESIS",
     "notes": "MANDATE BOUNDARY: sovereign policy observable, broker CFD execution, NO "
              "crypto-exchange venue, order book or feed named anywhere in this pack"},
    {"id": "CA-E12", "source": "CAFTA-DR apparel volumes under the yarn-forward rule of origin",
     "target": "COTTON", "targets": ("COTTON", "US30"), "to_country": "global", "sign": "+",
     "mechanism": "the preference requires US or regional yarn, so an isthmus apparel order is "
                  "a derived demand for a specific fibre rather than for the cheapest fibre; a "
                  "re-sourcing decision away from the isthmus is a reduction in that derived "
                  "demand with a two-season lead",
     "horizon": "1 to 6 months", "horizon_class": "multi_day", "lag_days": 45.0,
     "actor": "the US brands, the regional spinners and the maquila operators",
     "constraint": "yarn forward: the preference is conditional on the input's origin",
     "condition": "the monthly maquila export value against its trailing path, conditioned on "
                  "the US retail cycle state",
     "control": "the Asian share of the same US apparel import line; US mill use and the "
                "Chinese cotton import prints",
     "falsifier": "CAFTA-DR apparel volumes add nothing to COTTON beyond US mill use and "
                  "Chinese imports",
     "evidence": "HYPOTHESIS"},
    {"id": "CA-E13", "source": "A FEWS NET phase move or a prolonged canicula in the Corredor "
                               "Seco",
     "target": "CORN", "targets": ("CORN", "COFARA", "SUGAR"), "to_country": "regional",
     "sign": "+",
     "mechanism": "a rainfall deficit in the dry corridor hits basic grains directly and the "
                  "coffee flowering and cane growth indirectly; the isthmus is a net CORN "
                  "IMPORTER, so a domestic loss is an import requirement rather than an export "
                  "shortfall -- the sign runs through the import bill and the regional demand",
     "horizon": "1 to 6 months", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "the smallholders of the corridor and the national grain importers",
     "constraint": "a lost planting cannot be replanted inside the same rainy season",
     "condition": "a FEWS NET phase move, conditioned on the crop stage it landed in",
     "control": "WHEAT, which the isthmus grows none of and imports all of -- the "
                "not-grown-here placebo that separates a local deficit from global weather",
     "falsifier": "dry-corridor phase moves produce no response in the grain legs "
                  "distinguishable from the global weather state in the same months",
     "evidence": "HYPOTHESIS"},
    {"id": "CA-E14", "source": "Nicaraguan gold export volumes and the concession record",
     "target": "XAUUSD", "targets": ("XAUUSD",), "to_country": "global", "sign": "-",
     "mechanism": "gold is Nicaragua's largest single export and the dollar earnings behind a "
                  "zero-slide exchange-rate regime; the country is a PRICE TAKER, so the "
                  "informative direction runs from the world price to the country's reserve and "
                  "FX capacity and this edge records the reverse as the likely null",
     "horizon": "1 to 6 months", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "the concessionaires, the artisanal miners and the BCN",
     "constraint": "an artisanal sector cannot be metered, so the export line mixes two "
                   "production functions",
     "condition": "the monthly export volume against its trailing path, cross-checked against "
                  "mirror customs",
     "control": "the world gold price with no Nicaraguan act; the other five jurisdictions' "
                "export series where publication has not narrowed",
     "falsifier": "Nicaraguan export volumes carry no XAUUSD information at all, which is the "
                  "near-certain outcome and is recorded as a measured null rather than omitted",
     "evidence": "HYPOTHESIS"},
    {"id": "CA-E15", "source": "Panamanian banking-system liquidity, a transparency listing or a "
                               "mass de-flagging",
     "target": "US500", "targets": ("US500", "XAUUSD", "XBRUSD"), "to_country": "regional",
     "sign": "+",
     "mechanism": "a dollarised banking centre with NO LENDER OF LAST RESORT transmits a "
                  "liquidity squeeze into regional credit rather than into an exchange rate; a "
                  "de-flagging reshuffles which hulls may lawfully lift sanctioned crude, which "
                  "is a real constraint on the grey fleet",
     "horizon": "0 to 30 sessions", "horizon_class": "multi_day", "lag_days": 45.0,
     "actor": "the Superintendencia, the correspondent banks and the Autoridad Maritima",
     "constraint": "no central bank means no domestic liquidity can be created at all",
     "condition": "a liquidity ratio outside its trailing band, or a dated listing or "
                  "de-flagging act",
     "control": "regional credit conditions with no Panamanian event; the other open registries "
                "over the same months",
     "falsifier": "Panamanian banking and registry events carry no information about the risk "
                  "legs beyond US financial conditions",
     "evidence": "HYPOTHESIS"},
)

#: INTERACTIONS WITH SIBLING PACKS. `mx` and `us` come FIRST and explicitly, because the maquila,
#: remittance and nearshoring chains run straight into both and because this isthmus imports its
#: monetary policy from one of them. Every target is a broker symbol and the tests check it.
INTERACTIONS: tuple[dict[str, Any], ...] = (
    {"with": "us",
     "mechanism": "THE DEEPEST INTERACTION ON THIS DESK, AND IT RUNS IN FOUR DIRECTIONS AT ONCE. "
                  "The canal's headline cargo is US GULF GRAIN AND US GULF GAS, so a Panamanian "
                  "water level is a US export-basis variable. CAFTA-DR and its yarn-forward rule "
                  "make US cotton the input to the isthmus's apparel chain and US retail its "
                  "demand. US immigration enforcement is the sending-end policy variable for a "
                  "flow worth a quarter of GDP in three countries. And THE FOMC IS THE CENTRAL "
                  "BANK OF PANAMA AND EL SALVADOR -- not an influence on it, the actual "
                  "rate-setter, with no transmission mechanism in between",
     "observable": "US Gulf export inspections and the Gulf-to-PNW routing share against the "
                   "ACP draft and slot series; US apparel imports by partner against the "
                   "maquila export series; dated US enforcement acts against the four monthly "
                   "remittance prints; FOMC decision days against the two dollarised economies",
     "targets": ("CORN", "SOYBEAN", "WHEAT", "COTTON", "US500", "US30", "XNGUSD"),
     "control": "the same US variables in windows with no isthmus event at all, which is what "
                "separates 'the US moved' from 'the isthmus transmitted it'"},
    {"with": "mx",
     "mechanism": "MEXICO IS THE ISTHMUS'S COMPETITOR, ITS CORRIDOR AND ITS BENCHMARK AT ONCE. "
                  "Nearshoring investment that goes to Monterrey does not go to San Jose or San "
                  "Pedro Sula, and the two compete for the same US apparel and device "
                  "programmes under the same trade architecture. Mexican remittances are the "
                  "far larger sibling series driven by the same US labour market, which makes "
                  "them the control that separates a US shock from an isthmus one. And the "
                  "migration corridor from the northern triangle runs THROUGH Mexico, so a "
                  "Mexican enforcement act is an isthmus remittance variable too",
     "observable": "Mexican manufacturing and apparel exports to the US against the isthmus's "
                   "own; Mexican monthly remittances against the four isthmus prints; USDMXN as "
                   "the regional routing leg for every currency this pack cannot trade",
     "targets": ("USDMXN", "COTTON", "US500", "US30"),
     "control": "Asian apparel share of the same US import line, which is what BOTH regions are "
                "losing to or winning from"},
    {"with": "br",
     "mechanism": "THE TWO-ORIGIN COFFEE SUBSTITUTION, TESTABLE RATHER THAN NARRATIVE. Brazil is "
                  "the natural-process origin and this belt is the washed one; they are "
                  "imperfect substitutes in a blend, so a Brazilian frost or drought widens the "
                  "Central American differential without touching the belt's own volume, and a "
                  "rust epidemic here does the reverse. The `br` pack owns the Brazilian crop, "
                  "the frost calendar and the real; this pack owns five counted export series "
                  "and a rust history. Neither duplicates the other",
     "observable": "the ICO Brazilian Naturals indicator against the Other Milds indicator, and "
                   "the declared shock tables of both packs side by side",
     "targets": ("COFARA", "COFROB", "USDBRL", "SUGAR"),
     "control": "crop years with neither origin shocked, and years with both -- the third cell "
                "that separates substitution from a common global shock"},
    {"with": "cl",
     "mechanism": "CHILE IS THE CONTROL FOR THE COPPER CELL. Cobre Panama's removal was a "
                  "JUDICIAL act with no labour, weather or demand component, which makes it the "
                  "cleanest possible supply instrument -- provided the Chilean supply calendar "
                  "is conditioned on, because a copper move with a Chilean strike in the same "
                  "week is not a Panamanian event",
     "observable": "the Chilean production and labour calendar against the Panamanian gazette "
                   "dates, with the LME and COMEX inventory state as the conditioner",
     "targets": ("XCUUSD", "US500"),
     "control": "Chinese demand prints in months with neither country's event"},
    {"with": "pe",
     "mechanism": "TWO PACIFIC ROUTING QUESTIONS THAT ARE THE SAME QUESTION. Peru's Chancay "
                  "terminal opened in 2024 as a deep-water Pacific gateway with a direct "
                  "Shanghai service, at exactly the moment the canal was rationing transits. "
                  "Cargo that can reach Asia from the South American Pacific coast does not need "
                  "the canal at all, so Chancay is a structural competitor to a constrained "
                  "Panama and the two packs' logistics domains are each other's counterfactual. "
                  "Peru is also the world's second copper producer and therefore the second "
                  "control on the Cobre Panama cell",
     "observable": "Chancay throughput and the Peruvian export routing against the ACP transit "
                   "series; the two countries' copper supply calendars",
     "targets": ("XCUUSD", "USDCNH", "CORN", "SOYBEAN"),
     "control": "Chilean port throughput over the same months, which shares the geography and "
                "not the Chinese terminal"},
    {"with": "co",
     "mechanism": "COLOMBIA IS THE THIRD WASHED-ARABICA ORIGIN AND PANAMA'S FORMER SOVEREIGN. "
                  "Colombian Milds sit alongside the Other Milds group in the same substitution "
                  "structure, so a Colombian shock and an isthmus shock are the same kind of "
                  "event on the same contract and each is the other's replicate. The Darien Gap "
                  "migration route also runs between the two, which links Colombian and "
                  "Panamanian migration data to the remittance corridor",
     "observable": "the ICO Colombian Milds indicator against Other Milds; Darien crossing "
                   "counts against the northern-triangle remittance prints",
     "targets": ("COFARA", "USDMXN", "US500"),
     "control": "crop years with a Colombian shock and no isthmus shock"},
    {"with": "atlantic_energy",
     "mechanism": "THE CARIBBEAN BASIN IS ONE LOGISTICS SYSTEM. Venezuelan and Trinidadian "
                  "hydrocarbons move through the same Caribbean tanker plane that feeds the "
                  "canal's Atlantic approach, and Panama is the largest FLAG STATE for the "
                  "vessels that lift them -- so a sanctions designation or a de-flagging is a "
                  "shared variable between the two packs. The `atlantic_energy` pack owns the "
                  "barrels and the OFAC calendar; this pack owns the registry and the transit",
     "observable": "the Panamanian registry's de-flagging actions against the Venezuelan export "
                   "record; Caribbean tanker movements against the canal's Atlantic queue",
     "targets": ("XBRUSD", "XTIUSD", "XNGUSD"),
     "control": "the other open registries' fleets over the same months, which face the same "
                "designations without the canal"},
)

# --------------------------------------------------------------------------- eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    {"name": "the Canal Zone and the dollar isthmus", "start": "1904-01-01", "end": "1999-12-30",
     "regime": "the canal is built and operated by the United States; Panama adopts the dollar "
               "by the 1904 Convenio Monetario and never creates a central bank; the rest of "
               "the isthmus runs its own currencies and its own crises",
     "markers": ("1904 the Convenio Monetario and the balboa's 1:1 parity",
                 "1914 the canal opens",
                 "1977 the Torrijos-Carter treaties set the transfer date"),
     "why_it_matters": "Panama's institutional absence of a central bank starts here and has "
                       "never been interrupted; any study of Panamanian monetary transmission "
                       "is a study of the Federal Reserve's",
     "status": "SETTLED"},
    {"name": "the handover and the Panamanian canal", "start": "1999-12-31", "end": "2005-12-31",
     "regime": "the ACP takes over as an autonomous operator with constitutional standing, a "
               "board and a Treasury contribution; the canal becomes a Panamanian fiscal asset "
               "as well as a global chokepoint",
     "markers": ("1999-12-31 the transfer",
                 "2000-2005 the ACP establishes its advisory, toll and reservation regime"),
     "why_it_matters": "every advisory, slot and auction series this pack uses is an ACP "
                       "artefact and therefore starts here; there is no comparable pre-1999 "
                       "series",
     "status": "SETTLED"},
    {"name": "dollarisation, CAFTA-DR and the expansion referendum",
     "start": "2001-01-01", "end": "2016-06-25",
     "regime": "El Salvador dollarises on 2001-01-01; CAFTA-DR is negotiated and enters into "
               "force country by country from 2006; Panama approves the canal expansion by "
               "referendum in 2006 and builds it for a decade",
     "markers": ("2001-01-01 the Ley de Integracion Monetaria",
                 "2006-03-01 CAFTA-DR in force for El Salvador",
                 "2006-10-22 the expansion referendum",
                 "2012-2014 the roya epidemic crosses the belt"),
     "why_it_matters": "the dollarisation experiment's second arm and the trade architecture "
                       "both begin here; a coffee study that pools across the roya is pooling "
                       "two different belts",
     "status": "SETTLED"},
    {"name": "the Neopanamax era", "start": "2016-06-26", "end": "2020-03-15",
     "regime": "the expanded locks open and the canal's cargo mix changes permanently: US LNG "
               "and LPG gain a Pacific route, larger container ships take the Asia-to-US-East-"
               "Coast service, and the booking system is rebuilt around two lock sizes",
     "markers": ("2016-06-26 the Neopanamax locks open",
                 "2017-06-13 Panama recognises the People's Republic of China",
                 "2018-12-04 Costa Rica enacts the fiscal-reform law"),
     "why_it_matters": "THE GAS LEG OF THIS PACK DOES NOT EXIST BEFORE THIS DATE. Every XNGUSD "
                       "cell is bounded below by 2016-06-26 and a pooled study that crosses it "
                       "is mixing two different waterways",
     "status": "SETTLED"},
    {"name": "the pandemic, the hurricanes and the Bitcoin Law",
     "start": "2020-03-16", "end": "2023-05-23",
     "regime": "borders close and remittances fall for one month and then rise for two years; "
               "Eta and Iota hit the coffee and banana zones two weeks apart in November 2020; "
               "El Salvador legislates bitcoin as legal tender in 2021 and its bonds trade at "
               "distressed levels into 2022",
     "markers": ("2020-03-20 the US border expulsion order",
                 "2020-11-03 and 2020-11-18 Hurricanes Eta and Iota",
                 "2021-09-07 the Bitcoin Law takes effect",
                 "2021-07-20 the Brazilian frost"),
     "why_it_matters": "the remittance series has its largest structural break here and the "
                       "Salvadoran credit sequence starts here; neither can be pooled across "
                       "2020-03",
     "status": "SETTLED"},
    {"name": "THE CONSTRAINT: the Gatun drought and the judicial mine closure",
     "start": "2023-05-24", "end": "2024-09-01",
     "regime": "the ACP cuts draft in May 2023 and bookable transits fall from about 36 a day to "
               "22 by December; a single slot clears near four million dollars at auction; the "
               "Red Sea constricts for unrelated reasons in the same months; the Panamanian "
               "Supreme Court voids the Cobre Panama contract in November 2023 and the mine "
               "closes; Nicaragua steps its published slide to zero",
     "markers": ("2023-05-24 the first draft restriction",
                 "2023-11-08 the reported record auction print",
                 "2023-11-28 the Supreme Court ruling",
                 "2023-12-01 the 22-transit floor",
                 "2024-01-01 the Nicaraguan slide reaches zero",
                 "2024-03-28 Panama loses investment grade"),
     "why_it_matters": "THE PACK'S RICHEST SAMPLE AND ITS WORST CONFOUND AT ONCE: two "
                       "chokepoints constricted together for unrelated reasons, and a copper "
                       "shock landed in the middle of it. Every cell in this window needs both "
                       "control series or it is measuring the other event",
     "status": "SETTLED"},
    {"name": "the restoration and the programme era", "start": "2024-09-02", "end": "2026-12-31",
     "regime": "bookable transits return to 36 a day and the draft is restored; El Salvador "
               "signs an IMF arrangement and amends the Bitcoin Law; Nicaragua repeals its canal "
               "concession; Panama opens a process on the mine's future and permits the "
               "stockpiled concentrate to move; the Rio Indio reservoir becomes the structural "
               "answer to the next drought",
     "markers": ("2024-09-02 transits back to 36",
                 "2024-05-08 the Nicaraguan canal concession repealed",
                 "2024-12-18 the Salvadoran staff-level agreement",
                 "2025-01-29 the Bitcoin Law amendment",
                 "2025-06 the concentrate export permission"),
     "why_it_matters": "the current regime; every constraint cell has a level shift at the "
                       "restoration date and the copper cell has an open option on the restart",
     "status": "OPEN"},
    {"name": "the structural water question", "start": "2025-01-01", "end": None,
     "regime": "the canal's long-run capacity depends on a reservoir decision that competes with "
               "a capital city's drinking water; the Rio Indio project, the municipal draw and "
               "the ENSO cycle together determine whether 2023-2024 was an episode or the first "
               "of a series",
     "markers": ("the Rio Indio reservoir process",
                 "the municipal water demand trajectory",
                 "the ENSO cycle's next El Nino"),
     "why_it_matters": "if the constraint recurs, CA-A stops being an event study and becomes a "
                       "regime; the pack carries the question OPEN rather than assuming either "
                       "answer",
     "status": "OPEN"},
)

ACCESS_CONSTRAINTS: tuple[dict[str, Any], ...] = (
    {"constraint": "not one of the six currencies is quoted by this broker, and TWO OF THEM ARE "
                   "THE UNITED STATES DOLLAR",
     "measured": "data/universe/universe.json holds no PAB, GTQ, HNL, CRC, NIO or SVC symbol; "
                 "PAB is 1:1 by the 1904 Convenio Monetario with no banknote of its own and SVC "
                 "was withdrawn from circulation in 2001",
     "consequence": "every domestic macro mechanism terminates in the regional EM legs, the US "
                    "indices or the commodities. PAB AND SVC ARE LABELLED AS THE DOLLAR AND "
                    "NEVER AS PROXIES FOR IT, because a proxy carries basis risk and an "
                    "identity does not -- and a study that treats Panama as an EM currency will "
                    "hunt a devaluation premium that cannot exist"},
    {"constraint": "THE CRYPTO-EXCHANGE BOUNDARY, STATED IN FULL (mandate 2026-08-18)",
     "measured": "El Salvador's Bitcoin Law, its 2025 amendment, the IMF programme conditions "
                 "and the publicly reported sovereign holding are SOVEREIGN POLICY AND FISCAL "
                 "observables, published in the Diario Oficial and in programme documents",
     "consequence": "they are routed into the broker's own BTCUSD CFD and into the country's "
                    "credit story, and NOTHING ELSE. No crypto-exchange universe is hunted, no "
                    "venue order book, exchange feed, venue API or exchange-published statistic "
                    "is named as a source class anywhere in this pack, and no "
                    "crypto-exchange-native ground may be mined from it. The executable leg is "
                    "inside the MT5 universe by the same order that forbids the venue"},
    {"constraint": "the ACP supersedes its advisories in place",
     "measured": "an advisory to shipping replaces the previous one at the same URL and the old "
                 "text is removed; the statistics pages are republished whole",
     "consequence": "CA-A, CA-B and CA-C are NOT PIT-SAFE as published and their "
                    "point-in-time history exists only in the archive layer's crawls; a cell "
                    "compiled on an un-archived advisory is UNMEASURED, not assumed"},
    {"constraint": "every canal step, auction print and political date in this pack is "
                   "PRESS_REPORTED",
     "measured": "DRAFT_STEPS, SLOT_STEPS, AUCTION_PRINTS, COFFEE_SHOCKS and POLICY_EVENTS all "
                 "carry that label and none carries an advisory number or a gazette citation",
     "consequence": "these tables may GENERATE hypotheses and may not PROMOTE a cell until the "
                    "ACP advisory number or the Gaceta, Diario de Centro America, La Gaceta or "
                    "Diario Oficial citation is attached to the exact date the cell was "
                    "compiled on"},
    {"constraint": "the container-freight indices and the coffee origin differentials forbid "
                   "machine extraction",
     "measured": "Drewry, Xeneta and Freightos terms, and the coffee price-reporting agencies'; "
                 "both are registered machine_use_allowed=false",
     "consequence": "the FREIGHT leg of the canal mechanism and the DIFFERENTIAL leg of the "
                    "coffee mechanism are both UNMEASURED. The canal claim is made on the "
                    "PHYSICAL transit count, which is public, and the coffee claim is made on "
                    "the exchange contract with COFROB as the non-belt control -- and the "
                    "absence is named rather than worked around"},
    {"constraint": "PANAMA HAS NO CENTRAL BANK, SO THERE IS NO MONETARY DATA TO BE MISSING",
     "measured": "no policy rate, no monetary aggregate from a monetary authority, no FX "
                 "reserve series; the country has had none since 1904",
     "consequence": "this is a FACT ABOUT THE COUNTRY and not a gap in this pack's coverage. "
                    "NO_LAWFUL_GROUND declares it and names the lawful substitutes: the "
                    "Superintendencia de Bancos' banking-system statistics, the Contraloria's "
                    "INEC series, and the FOMC's own decisions as Panama's policy-rate series"},
    {"constraint": "Nicaragua's independent press operates from exile and its statistical "
                   "publication has narrowed",
     "measured": "every independent outlet publishes from outside the country; INIDE's series "
                 "are thinner and less frequent than its neighbours'",
     "consequence": "the exile outlets are KEPT with the condition attached, the BCN's own "
                    "monthly external-sector series is still used, the IMF Article IV is the "
                    "outside audit, and MIRROR CUSTOMS through UN Comtrade and SIECA "
                    "reconstructs the trade the country does not publish. Every reconstructed "
                    "series is labelled MIRROR so no study silently mixes the two"},
    {"constraint": "there is no listed derivatives market anywhere on the isthmus and no COT "
                   "contract for any of the six currencies",
     "measured": "the three bourses are repo and government-paper venues with no expiry clock; "
                 "the CFTC lists no contract for PAB, GTQ, HNL, CRC, NIO or SVC",
     "consequence": "positioning cells run on the COMMODITY contracts this pack executes -- "
                    "Coffee C, Sugar No. 11, copper and cotton -- and isthmus currency "
                    "positioning is UNMEASURED and is never proxied by the MXN or BRL COT legs"},
    {"constraint": "elPeriodico closed in May 2023",
     "measured": "the outlet ceased publication after its founder's imprisonment; the site is "
                 "an archive",
     "consequence": "Guatemalan investigative coverage of customs, concessions and public "
                    "contracting has a DATED BREAK; the archive is retained through the "
                    "Internet Archive and Plaza Publica, Prensa Comunitaria and the Centro de "
                    "Medios Independientes carry the live ground forward"},
)
INSTITUTIONAL_FLOW_SOURCES: tuple[str, ...] = (
    "ACP transit bookings, the anchorage queue and the auction clearing prices",
    "IMF PortWatch daily transit counts for Panama, Suez and Bab el-Mandeb",
    "the five coffee institutes' monthly export permits and volumes",
    "the four central banks' monthly family remittance prints",
    "Superintendencia de Bancos de Panama banking-system liquidity and deposits",
    "Colon Free Zone monthly re-exports and Panamanian port throughput",
    "SIECA intra-regional trade and UN Comtrade mirror customs")
SERIES: dict[str, str] = {
    "CA_CANAL_DRAFT": "ACP:calado_maximo_autorizado",
    "CA_CANAL_SLOTS": "ACP:cupos_reservables_diarios",
    "CA_CANAL_TRANSITS": "ACP:transitos_diarios",
    "CA_CANAL_AUCTION": "ACP:subasta_precio_de_cierre",
    "CA_GATUN_LEVEL": "ACP:nivel_lago_gatun",
    "CA_CHOKEPOINTS": "PORTWATCH:transitos_por_paso",
    "CA_COFFEE_EXPORTS": "CAFE:exportaciones_mensuales",
    "CA_COFFEE_ICO": "ICO:indicador_otros_suaves",
    "CA_REMITTANCES": "CA:remesas_familiares",
    "CA_GT_POLICY": "BANGUAT:tasa_lider",
    "CA_GT_FX_RULE": "BANGUAT:regla_de_participacion",
    "CA_HN_AUCTION": "BCH:subasta_ofertado_demandado",
    "CA_CR_POLICY": "BCCR:tasa_de_politica_monetaria",
    "CA_CR_MONEX": "BCCR:monex_promedio_ponderado",
    "CA_NI_SLIDE": "BCN:deslizamiento_cambiario",
    "CA_NI_GOLD": "BCN:exportaciones_de_oro",
    "CA_SV_DEBT": "MH:deuda_publica",
    "CA_PA_BANKING": "SBP:liquidez_centro_bancario",
    "CA_PA_FREEZONE": "INEC:zona_libre_reexportaciones",
    "CA_SUGAR_ZAFRA": "ASAZGUA:molienda_semanal",
    "CA_MAQUILA": "SIECA:exportaciones_de_maquila",
    "CA_DROUGHT": "FEWSNET:clasificacion_de_fase",
}


# --------------------------------------------------------------------------- the regimes
#: THE EXPERIMENT, AS A TABLE. Six neighbours on one isthmus with one trade structure and SIX
#: different monetary arrangements between them -- two of which are the same arrangement (the
#: dollar) with and without a central bank attached, which is the cleanest pair in the set.
FX_REGIMES: dict[str, str] = {
    "pa": "DOLLAR_NO_CENTRAL_BANK",
    "sv": "DOLLAR_WITH_TOOTHLESS_BANK",
    "gt": "MANAGED_FLOAT_PUBLISHED_RULE",
    "hn": "BAND_WITH_ALLOCATION_AUCTION",
    "cr": "FLOAT_INFLATION_TARGETING",
    "ni": "CRAWL_AT_ZERO",
}


def fx_regime(cc: str) -> str:
    """MECHANISM FUNCTION. The monetary regime class a jurisdiction is in, which is the
    conditioning state of CA-G and CA-H. `pa` and `sv` differ by ONE institution and nothing
    else, which is what makes them each other's replicate rather than two observations."""
    return FX_REGIMES.get(str(cc).lower(), "UNMEASURED")


def dollarised(cc: str) -> bool:
    """True when the jurisdiction's legal tender IS the United States dollar. Two of the six
    are, and neither of them is 'pegged': the balboa is a coin denomination of the dollar and
    the colon was withdrawn from circulation."""
    return fx_regime(cc).startswith("DOLLAR")


def regime_groups() -> dict[str, tuple[str, ...]]:
    """The experiment's arms: which jurisdictions sit in which regime class."""
    out: dict[str, list[str]] = {}
    for cc in JURISDICTIONS:
        out.setdefault(fx_regime(cc), []).append(cc)
    return {k: tuple(v) for k, v in out.items()}


# --------------------------------------------------------------------------- the cells
#: WHAT EACH DOMAIN MINTS: its mechanism family, its horizon class, and the one-line control
#: every cell from it inherits. `cells()` is the cross product of a domain's INSTRUMENTS and its
#: CONDITIONS -- both of which are real, named, evaluable states of this pack's own data plane.
#: It is not a cartesian blow-up: a condition that cannot be evaluated from a declared dataset
#: does not appear in a domain's `conditions` tuple in the first place. SIX JURISDICTIONS MINT
#: MORE CELLS THAN ONE DOES, and that is the arithmetic rather than an inflation.
DOMAIN_CELL_SPEC: dict[str, tuple[str, str, str]] = {
    "CA-A": ("physical_supply", "0d_to_20d",
             "the Suez and Bab el-Mandeb transit series and the US Gulf-to-PNW routing share"),
    "CA-B": ("scarcity_price", "0d_to_10d",
             "weeks with the same slot count and no auction"),
    "CA-C": ("weather_state", "1m_to_6m",
             "the same ENSO phases in years with no draft restriction"),
    "CA-D": ("substitution", "0d_to_30d",
             "the both-constrained window of 2023-2024, carried as the confound"),
    "CA-E": ("release_surprise", "1m_to_3m",
             "COFROB as the non-belt leg and the ICO Brazilian Naturals indicator"),
    "CA-F": ("physical_supply", "1m_to_12m",
             "the Brazilian shock windows with no isthmus event"),
    "CA-G": ("monetary_regime", "intraday_to_5d",
             "Costa Rica, the instrumented floater on the same isthmus"),
    "CA-H": ("policy_reaction_function", "1d_to_10d",
             "block-shuffled rule-trigger and auction series"),
    "CA-I": ("cross_border_flow", "1m_to_3m",
             "Mexican remittances and the two sender-side isthmus economies"),
    "CA-J": ("sovereign_policy", "intraday_to_10d",
             "matched windows with an equivalent risk move and no Salvadoran act"),
    "CA-K": ("supply_disruption", "0d_to_60d",
             "Chilean and Peruvian supply events in the same windows"),
    "CA-L": ("credit_state", "0d_to_30d",
             "regional credit conditions with no Panamanian event"),
    "CA-M": ("seasonal_crop", "1m_to_3m",
             "the Brazilian and Indian crops over the same seasons"),
    "CA-N": ("derived_demand", "1m_to_6m",
             "the Asian share of the same US apparel import line"),
    "CA-O": ("nearshoring_flow", "1m_to_6m",
             "Mexican manufacturing exports over the same months"),
    "CA-P": ("small_producer", "1m_to_6m",
             "the world price with no Nicaraguan act, and the mirror-customs discrepancy"),
    "CA-Q": ("weather_state", "1m_to_6m",
             "WHEAT as the not-grown-here placebo"),
    "CA-R": ("holiday_liquidity", "0d_to_3d",
             "Panama, open on 15 September while five neighbours are shut"),
}


def cells() -> tuple[dict[str, Any], ...]:
    """Every testable cell this pack mints: domain x executable instrument x named condition.

    A cell is a triple the gauntlet can actually evaluate -- an instrument the broker quotes, a
    condition this pack's own declared datasets can compute, and a control that is not the
    instrument's own history. The cross product is taken over the domain's OWN instrument tuple
    rather than over the whole executable list, which is what keeps the count honest: CA-E never
    mints a copper cell and CA-K never mints a coffee one.
    """
    out: list[dict[str, Any]] = []
    for dom in DOMAINS:
        did = str(dom["id"])
        family, horizon, control = DOMAIN_CELL_SPEC.get(did, ("residual", "1d_to_5d",
                                                              "a matched-weekday placebo"))
        owners = DOMAIN_JURISDICTIONS.get(did, ())
        for symbol in dom["instruments"]:
            for i, condition in enumerate(dom["conditions"]):
                out.append({
                    "cell_id": f"{CODE}:{did}:{symbol}:c{i + 1}",
                    "domain": did, "symbol": str(symbol), "condition": str(condition),
                    "mechanism_family": family, "horizon": horizon, "control": control,
                    "jurisdictions": owners,
                    "why": f"{dom['title']} -- conditioned on {condition}",
                })
    return tuple(out)


CELLS: tuple[dict[str, Any], ...] = cells()


def cells_by_symbol() -> dict[str, int]:
    """How many cells each executable instrument carries. A symbol with none is an instrument
    the pack declared and never used, which is a defect the tests catch."""
    out: dict[str, int] = dict.fromkeys(EXECUTABLE_INSTRUMENTS, 0)
    for row in CELLS:
        out[str(row["symbol"])] = out.get(str(row["symbol"]), 0) + 1
    return out


def cells_by_jurisdiction() -> dict[str, int]:
    """How many cells each of the six jurisdictions is named in. A jurisdiction with none is a
    country this pack claimed and never tested, which is exactly what the parity fence exists to
    catch -- so the tests check it here too."""
    out: dict[str, int] = dict.fromkeys(JURISDICTIONS, 0)
    for row in CELLS:
        for cc in row["jurisdictions"]:
            if cc in out:
                out[cc] += 1
    return out


# --------------------------------------------------------------------------- the miners
def _emit(ctx: Any, mechanism: str, **fields: Any) -> int:
    """Record one row through the department Ctx when there is one, and count it either way.
    With `ctx=None` nothing is written anywhere: `mine(None)` is a pure report."""
    if ctx is None:
        return 1
    record = getattr(ctx, "record", None)
    if not callable(record):
        return 1
    try:
        record(mechanism=mechanism, source_id=f"{CODE}:pack", source_type="claim", **fields)
    except Exception:
        return 0
    return 1


def canal_constraint_windows(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """CA-A and CA-C: THE PACK'S PRIMARY MINER. The published draft and slot step series as a
    dated constraint, with the announcement and effective dates kept apart."""
    n = 0
    for effective, feet, status in DRAFT_STEPS:
        n += _emit(ctx, "physical_supply",
                   payload={"domain": "CA-A", "kind": "draft", "effective": effective.isoformat(),
                            "feet_tfw": feet, "status": status})
    for effective, slots, status in SLOT_STEPS:
        n += _emit(ctx, "physical_supply",
                   payload={"domain": "CA-A", "kind": "slots", "effective": effective.isoformat(),
                            "slots": slots, "severity": constraint_severity(effective),
                            "status": status})
    constrained = constraint_days(date(2023, 1, 1), date(2025, 6, 30))
    return {"miner": "canal_constraint_windows", "domain": "CA-A",
            "draft_steps": len(DRAFT_STEPS), "slot_steps": len(SLOT_STEPS),
            "constrained_days": len(constrained), "emitted": n,
            "unmeasured": ["CA-A/advisory_number: no step carries its ACP Advisory to Shipping "
                           "number yet, so every row is PRESS_REPORTED and none may be promoted",
                           "CA-C/gatun_series: the daily lake level series is not loaded on this "
                           "box, so the LEADING half of the mechanism is UNMEASURED"]}


def canal_auction_prints(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """CA-B: the auction clearing prints -- a priced option on the constraint, with a small
    sample that the miner reports rather than pads."""
    n = 0
    for day, price, what, status in AUCTION_PRINTS:
        n += _emit(ctx, "scarcity_price",
                   payload={"domain": "CA-B", "date": day.isoformat(), "usd": price,
                            "what": what, "slots_that_day": bookable_slots(day),
                            "status": status})
    return {"miner": "canal_auction_prints", "domain": "CA-B", "prints": len(AUCTION_PRINTS),
            "max_usd": max((p for _d, p, _w, _s in AUCTION_PRINTS), default=0.0), "emitted": n,
            "unmeasured": ["CA-B/auction_series: only the reported prints are carried; the ACP's "
                           "own full result series is not on this box, so the sample is three "
                           "observations and is declared as such (L1.28a)"]}


def chokepoint_substitution(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """CA-D: THE CONTROL MINER. It refuses to attribute a freight move to Panama without the
    Suez and Bab el-Mandeb series beside it, and says UNMEASURED by name when they are absent."""
    n = 0
    for row in CHOKEPOINT_CONTROLS:
        n += _emit(ctx, "substitution",
                   payload={"domain": "CA-D", "control": row["name"],
                            "observable": row["observable"], "status": row["status"]})
    return {"miner": "chokepoint_substitution", "domain": "CA-D",
            "controls": len(CHOKEPOINT_CONTROLS), "emitted": n,
            "unmeasured": ["CA-D/portwatch_series: the IMF PortWatch daily transit counts for "
                           "Panama, Suez and Bab el-Mandeb are not loaded on this box; without "
                           "them a Panama constraint cell is measuring global freight and the "
                           "miner refuses to claim otherwise"]}


def coffee_export_calendar(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """CA-E and CA-F: the five origins on one harvest year, and the declared shocks with the
    Brazilian control rows kept separate so a study cannot pool the two origins."""
    today = datetime.now(tz=UTC).date()
    n = 0
    for cc, row in COFFEE_INSTITUTES.items():
        n += _emit(ctx, "release_surprise",
                   payload={"domain": "CA-E", "jurisdiction": cc, "institute": row["name"],
                            "series": row["series"], "harvest_year": coffee_harvest_year(today),
                            "phase": harvest_phase(today)})
    for lo, hi, scope, what, status in COFFEE_SHOCKS:
        n += _emit(ctx, "physical_supply",
                   payload={"domain": "CA-F", "start": lo.isoformat(), "end": hi.isoformat(),
                            "scope": scope, "what": what, "status": status,
                            "is_control": "CONTROL" in scope})
    return {"miner": "coffee_export_calendar", "domain": "CA-E",
            "origins": len(COFFEE_INSTITUTES), "shocks": len(COFFEE_SHOCKS),
            "harvest_year": coffee_harvest_year(today), "phase": harvest_phase(today),
            "emitted": n,
            "unmeasured": ["CA-E/institute_series: none of the five monthly export series is "
                           "loaded on this box, so the belt total cannot be computed",
                           "CA-F/origin_differential: the differential is LICENSED and machine "
                           "extraction is forbidden, so the claim is made on the exchange "
                           "contract with COFROB as the control"]}


def monetary_regime_experiment(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """CA-G and CA-H: six jurisdictions, six regime classes, two of them the dollar with and
    without a central bank attached. The arms of the experiment, emitted as a table."""
    n = 0
    for cc in JURISDICTIONS:
        bank = CENTRAL_BANKS[cc]
        n += _emit(ctx, "monetary_regime",
                   payload={"domain": "CA-G", "jurisdiction": cc, "regime": fx_regime(cc),
                            "dollarised": dollarised(cc), "central_bank_exists": bank["exists"],
                            "instrument": bank["instrument"][:120]})
    return {"miner": "monetary_regime_experiment", "domain": "CA-G",
            "jurisdictions": len(JURISDICTIONS), "arms": regime_groups(), "emitted": n,
            "unmeasured": ["CA-H/policy_calendars: none of the four published decision calendars "
                           "is in this pack (L1.28a); the candidate lattice is candidates and "
                           "not decisions",
                           "CA-H/rule_trigger: the Banguat reference and moving-average series "
                           "are not loaded, so the participation trigger cannot be recomputed"]}


def remittance_season(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """CA-I: five Mother's Days and a December corridor -- Honduras's derived from the
    second-Sunday rule -- plus the dated US acts on the sending end."""
    year = datetime.now(tz=UTC).year
    peaks = remittance_peaks(year)
    n = 0
    for cc in JURISDICTIONS:
        got = mothers_day(cc, year)
        n += _emit(ctx, "cross_border_flow",
                   payload={"domain": "CA-I", "jurisdiction": cc,
                            "regime": remittance_regime(cc),
                            "mothers_day": got.isoformat() if got is not None else "UNMEASURED",
                            "gdp_share_pct": REMITTANCE_SHARE[cc]["gdp_share_pct"]})
    for day, what, status in US_POLICY_ACTS:
        n += _emit(ctx, "policy_event",
                   payload={"domain": "CA-I", "date": day.isoformat(), "what": what,
                            "status": status, "side": "sending"})
    return {"miner": "remittance_season", "domain": "CA-I", "peaks": len(peaks),
            "us_acts": len(US_POLICY_ACTS),
            "receivers": [cc for cc in JURISDICTIONS if remittance_regime(cc) == "RECEIVER"],
            "emitted": n,
            "unmeasured": ["CA-I/monthly_series: the four monthly remittance series are not "
                           "loaded on this box and they publish on FOUR DIFFERENT LAGS, so an "
                           "aggregate built at one date would mix vintages"]}


def sovereign_policy_timestamps(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """CA-J, CA-K and CA-P: the dated legal, judicial and credit events, every row
    PRESS_REPORTED, with the mandate boundary stated in the Salvadoran payloads themselves."""
    n = 0
    for day, cc, what, status in POLICY_EVENTS:
        boundary = ("SOVEREIGN POLICY OBSERVABLE ROUTED TO BTCUSD; no crypto-exchange venue, "
                    "order book or feed is a source" if cc == "sv" and "Bitcoin" in what else "")
        n += _emit(ctx, "political_event",
                   payload={"domain": "CA-J" if cc == "sv" else "CA-K",
                            "date": day.isoformat(), "jurisdiction": cc, "what": what,
                            "status": status, "mandate_note": boundary})
    return {"miner": "sovereign_policy_timestamps", "events": len(POLICY_EVENTS),
            "jurisdictions": sorted({cc for _d, cc, _w, _s in POLICY_EVENTS}), "emitted": n,
            "unmeasured": ["CA-K/gazette_citation: no event carries its Gaceta, Diario de Centro "
                           "America, La Gaceta or Diario Oficial citation yet, so none may be "
                           "promoted",
                           "CA-J/intraday_minute: the Salvadoran and Panamanian acts are "
                           "day-resolution here and cannot carry an intraday cell"]}


def drought_risk_windows(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """CA-Q and CA-M: the dry corridor as a published risk series, with WHEAT carried as the
    not-grown-here placebo and the zafra window as the cane sampling frame."""
    n = 0
    for lo, hi, scope, what, status in COFFEE_SHOCKS:
        if "CONTROL" in scope:
            continue
        n += _emit(ctx, "weather_state",
                   payload={"domain": "CA-Q", "start": lo.isoformat(), "end": hi.isoformat(),
                            "scope": scope, "what": what, "status": status,
                            "placebo": "WHEAT is imported and not grown here"})
    return {"miner": "drought_risk_windows", "domain": "CA-Q",
            "isthmus_shock_windows": len([r for r in COFFEE_SHOCKS if "CONTROL" not in r[2]]),
            "emitted": n,
            "unmeasured": ["CA-Q/fewsnet_phases: the FEWS NET phase classifications are not "
                           "loaded on this box, so the dated risk series cannot be differenced",
                           "CA-M/zafra_grind: the weekly mill grind is not loaded, so the cane "
                           "cell runs on the season window alone"]}


def isthmus_calendar(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """CA-R: six calendars, one Easter block that closes all six, five independence closures on
    one date, and Panama open beside them."""
    year = datetime.now(tz=UTC).year
    union = region_holidays(year)
    shared = shared_closures(year, 4)
    independence = independence_day_closures(year)
    n = _emit(ctx, "holiday_liquidity",
              payload={"domain": "CA-R", "year": year, "union_days": len(union),
                       "shared_days": len(shared),
                       "independence_closures": sorted(independence),
                       "semana_santa": [d.isoformat() for d in semana_santa(year)],
                       "morazanico": [d.isoformat() for d in morazanico(year)]})
    return {"miner": "isthmus_calendar", "domain": "CA-R", "union_days": len(union),
            "shared_days": len(shared), "independence_closures": len(independence),
            "emitted": n, "unmeasured": []}


def transmission_seeds(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """The pack's own map as HYPOTHESIS rows: the transmission edges and the interactions."""
    n = 0
    for e in TRANSMISSION_EDGES_SEED:
        n += _emit(ctx, "transfer",
                   payload={"edge": e["id"], "targets": e["targets"], "sign": e["sign"],
                            "evidence": e["evidence"], "control": e["control"]})
    for row in INTERACTIONS:
        n += _emit(ctx, "transfer",
                   payload={"interaction_with": row["with"], "targets": row["targets"],
                            "observable": row["observable"], "control": row["control"]})
    return {"miner": "transmission_seeds", "edges": len(TRANSMISSION_EDGES_SEED),
            "interactions": len(INTERACTIONS), "emitted": n, "unmeasured": []}


MINERS: dict[str, Any] = {
    "canal_constraint_windows": canal_constraint_windows,
    "canal_auction_prints": canal_auction_prints,
    "chokepoint_substitution": chokepoint_substitution,
    "coffee_export_calendar": coffee_export_calendar,
    "monetary_regime_experiment": monetary_regime_experiment,
    "remittance_season": remittance_season,
    "sovereign_policy_timestamps": sovereign_policy_timestamps,
    "drought_risk_windows": drought_risk_windows,
    "isthmus_calendar": isthmus_calendar,
    "transmission_seeds": transmission_seeds,
}


def mine(ctx: Any = None) -> dict[str, Any]:
    """THE DEPARTMENT ENTRY. Pure python, no network, no LLM, no heavy import.

    Runs every miner this pack owns, emits through the department Ctx when one is given, and
    returns a plain report when it is not -- so `mine(None)` is a measurement of what the pack
    WOULD emit and writes nothing anywhere.
    """
    rows: list[dict[str, Any]] = []
    unmeasured: list[str] = []
    emitted = 0
    for name, fn in MINERS.items():
        got = fn(None, ctx)
        rows.append({"miner": name, **{k: v for k, v in got.items() if k != "unmeasured"}})
        unmeasured.extend(str(u) for u in got.get("unmeasured", ()))
        emitted += int(got.get("emitted", 0))
    return {"code": CODE, "at": datetime.now(tz=UTC).date().isoformat(), "emitted": emitted,
            "cells_emitted": len(CELLS), "rows": rows, "unmeasured": unmeasured,
            "jurisdictions": JURISDICTIONS,
            "cells_by_jurisdiction": cells_by_jurisdiction(),
            "interactions": tuple(r["with"] for r in INTERACTIONS)}


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
        "executable_instruments": EXECUTABLE_INSTRUMENTS, "central_bank": CENTRAL_BANK,
        "fixing_conventions": FIXING_CONVENTIONS,
        "settlement_conventions": SETTLEMENT_CONVENTIONS, "exchanges": EXCHANGES,
        "release_classes": RELEASE_CLASSES, "session_windows": SESSION_WINDOWS,
        "holidays_rule": HOLIDAYS_RULE, "fiscal_year_end": FISCAL_YEAR_END,
        "positioning_sources": POSITIONING_SOURCES, "native_languages": NATIVE_LANGUAGES,
        "terminology": TERMINOLOGY, "source_classes": SOURCE_CLASSES,
        "source_layers": SOURCE_LAYERS, "layer_absences": LAYER_ABSENCES,
        "layer_terms": layer_terms(), "source_layer_coverage": source_layer_coverage(),
        "datasets": DATASETS, "actors": ACTORS, "domains": DOMAINS,
        "custom_miners": CUSTOM_MINERS, "miner_domains": MINER_DOMAINS,
        "transmission_edges_seed": TRANSMISSION_EDGES_SEED, "policy_eras": POLICY_ERAS,
        "transmission_targets": TRANSMISSION_TARGETS, "access_constraints": ACCESS_CONSTRAINTS,
        "region_desk": REGION_DESK, "forest": FOREST, "cot_currency": COT_CURRENCY,
        "export_economy": EXPORT_ECONOMY, "retail_leverage_regime": RETAIL_LEVERAGE_REGIME,
        "institutional_flow_sources": INSTITUTIONAL_FLOW_SOURCES, "series": SERIES,
        "mission": MISSION, "jurisdictions": JURISDICTIONS, "currencies": CURRENCIES,
        "fiscal_years": FISCAL_YEARS, "central_banks": CENTRAL_BANKS,
        "interactions": INTERACTIONS, "query_territories": QUERY_TERRITORIES, "cells": CELLS,
        "no_lawful_ground": NO_LAWFUL_GROUND, "fx_regimes": FX_REGIMES,
        "domain_jurisdictions": DOMAIN_JURISDICTIONS,
        "actor_jurisdictions": ACTOR_JURISDICTIONS,
        "draft_steps": DRAFT_STEPS, "slot_steps": SLOT_STEPS, "auction_prints": AUCTION_PRINTS,
        "chokepoint_controls": CHOKEPOINT_CONTROLS, "coffee_institutes": COFFEE_INSTITUTES,
        "coffee_shocks": COFFEE_SHOCKS, "remittance_share": REMITTANCE_SHARE,
        "policy_events": POLICY_EVENTS, "us_policy_acts": US_POLICY_ACTS,
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
    """The framework's HolidayRule shape: every closed date the rule produces for 2024-2026,
    and the fixed month-days of all six jurisdictions together."""
    dates = sorted({d.isoformat() for y in HOLIDAYS_RULE["years"] for d in market_holidays(y)})
    fixed = sorted({f"{m:02d}-{d:02d}"
                    for rows in FIXED_HOLIDAYS.values() for m, d, _n in rows})
    return {"dates": tuple(dates), "fixed_md": tuple(fixed),
            "weekly_closed": (5, 6), "notes": HOLIDAYS_RULE["authority"]}


def lab_kwargs() -> dict[str, Any]:
    """The keyword set `country_lab.CountryPack` is built from, in the shapes its coercion
    reads best: sources as rows AND as tagged lines, positioning and miners as strings, the
    holiday rule as dates, absent layers as a mapping."""
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
