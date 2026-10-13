"""THE ATLANTIC HYDROCARBON PROVINCE -- Guyana, Trinidad, Venezuela, Suriname as ONE pack.

WHY THESE FOUR ARE ONE PACK AND NOT FOUR, AND WHY NEITHER `br`, `co`, `mx`, `cl`, `ar`, `pe` NOR
`bo` ALREADY ANSWERS FOR THEM. The Latin-American siblings on this desk are written around a
central bank and a domestic asset market: `br` and `mx` around a policy rate and a deep local
curve, `cl` and `pe` around copper and a conflict calendar, `co` around its own oil and its peso,
`ar` around a capital control, `bo` around gas and an altiplano. NONE of those objects exists
here. Guyana has no meaningful domestic capital market and a currency this broker does not quote;
Trinidad's rate is administered and its FX is RATIONED; Venezuela's central bank stopped being a
readable policy object years ago; Suriname defaulted and restructured. What these four have
instead is ONE PHYSICAL BARREL AND ONE PHYSICAL MOLECULE, shared across a single basin, priced
against contracts the box already trades. The unit of analysis here is the PROVINCE, not the
country, and the four jurisdictions are each other's controls by construction.

SIX THINGS THAT BELONG TO THIS PROVINCE AND TO NO OTHER PACK ON THIS DESK.

  1. THE FASTEST SUPPLY RAMP IN THE HISTORY OF THE INDUSTRY, ON A PUBLISHED TIMETABLE. Guyana
     produced NOTHING before 20 December 2019 and roughly 650,000 b/d six years later, with
     ~1.7 mb/d of sanctioned nameplate targeted by 2030. Every vessel -- Liza Destiny, Liza
     Unity, Prosperity, ONE GUYANA, Errea Wittu, Jaguar -- has a PUBLISHED sanction date, a
     PUBLISHED nameplate capacity and a PUBLISHED first-oil target. That is a dated, multi-year,
     non-OPEC supply curve against XBRUSD and XTIUSD, and almost nobody models it as a scheduled
     series. `sanctioned_capacity_on(day)` is the series; AE-A mints the per-vessel cells. THIS
     IS THE PRIMARY REASON THE PACK EXISTS.

  2. A SOVEREIGN WHOSE REVENUE FUNCTION IS A PUBLISHED FORMULA. The 2016 Stabroek PSA recovers
     costs up to a 75% CEILING, splits the residual profit oil 50/50 and adds a 2% royalty, so
     the government's take is computable from the oil price and the cost stack --
     `government_take(revenue, recoverable_costs)` does it in four lines. The Natural Resource
     Fund publishes monthly receipts, its withdrawal ceiling is STATUTORY under the 2021 NRF Act,
     and the Guyanese lifting entitlement is announced CARGO BY CARGO. No other pack here can
     compute a sovereign's oil take from a published formula.

  3. A GAS PROVINCE IN STRUCTURAL DECLINE THAT PRICES FERTILISER. Trinidad is the western
     hemisphere's LNG and ammonia/methanol hub, its gas is declining, and the consequences are
     published: Atlantic LNG train utilisation, the cross-border Dragon licence that the United
     States granted, revoked and re-granted on DATED days, and the monthly field-level gas
     production bulletin the Ministry of Energy actually publishes. Trinidadian ammonia is a real
     share of Atlantic-basin nitrogen, and nitrogen cost enters CORN and WHEAT acreage economics.
     AE-E carries that chain with the control named, because ammonia is NOT a broker symbol.

  4. THE LARGEST PROVEN RESERVE BASE ON EARTH, RUNNING AS A FUNCTION OF A FOREIGN LICENCE.
     Venezuelan output moves on dated, published, lawful-to-read administrative acts: General
     Licence 44 (18 October 2023), its non-renewal and replacement by GL 44A (17 April 2024), the
     individual Chevron and Repsol/Eni authorisations, and the 2025 changes. `sanctions_state`
     returns the regime in force on any day. And OPEC publishes Venezuelan production in TWO
     SERIES THAT DISAGREE -- direct communication and secondary sources -- so the GAP is itself
     an observable (`opec_gap`) and the sign of the gap is a statement about who is counting.

  5. A DATED TERRITORIAL RISK SERIES WITH AN OIL PREMIUM ATTACHED. The Essequibo dispute is not a
     mood: the Venezuelan referendum of 3 December 2023, the Argyle Declaration of 14 December
     2023 and the ICJ's own published procedural calendar are timestamps, and the territory they
     concern contains the block that produces the barrels in point 1.

  6. THE FORWARD CONTROL NOBODY ELSE HAS. Suriname sanctioned Block 58 (GranMorgu) in October
     2024 with first oil targeted 2028, in the SAME geological trend, on a LATER clock, under a
     DIFFERENT fiscal regime and a different sovereign credit history. A second ramp with a
     different date is the negative control the Guyanese series has never had.

WHAT IS EXECUTABLE AND WHAT IS NOT. GYD, TTD, VES and SRD are ALL ABSENT from this broker, and so
are ammonia, methanol, LNG, the Merey and Liza crude grades, the Trinidadian and Guyanese bourses
and every local bond. Each is named in `TRANSMISSION_TARGETS` with the broker symbols that carry
its economics AND with its basis risk written down. The LNG case is the one that bites: HENRY HUB
IS NOT ATLANTIC LNG. XNGUSD is a US pipeline-gas contract; a Trinidadian train outage moves the
Atlantic basin LNG spread and the ammonia netback, and a study that swapped one for the other
would measure the arbitrage rather than the shock. That sentence is in the edge, in the domain
and in `ACCESS_CONSTRAINTS`, deliberately three times.

LAWFULNESS, STATED PLAINLY. Venezuela is under a sanctions regime. NOTHING in this pack touches a
sanctioned entity's private systems and nothing bypasses an access control. Everything here is
PUBLIC: OFAC's own published licences and FAQs, OPEC's Monthly Oil Market Report, EIA, the US
Federal Register, published court dockets, national statistics and public press. Sanctions
constrain TRANSACTIONS, not the reading of published administrative acts -- and the desk executes
only broker symbols, never a Venezuelan, Guyanese, Trinidadian or Surinamese instrument.

THE TWO-LANE ORDER (2026-09-06) IS ENFORCED HERE. The operators, the state oil companies, the
petrochemical producers and the gold miners of this province are ACTORS and never instruments. No
share CFD appears in any instrument tuple in this file.

NATIVE GROUND. English is the OFFICIAL language of Guyana and of Trinidad and Tobago, so an
English query here reads the ground rather than an English corner of it -- which is true in this
pack and false in most. The non-English half is real and is carried: SPANISH for Venezuela
(Efecto Cocuyo, Prodavinci, Banca y Negocios, the Gaceta Oficial), DUTCH and SRANAN TONGO for
Suriname (Starnieuws, de Ware Tijd, the CBvS and Staatsolie), and GUYANESE CREOLESE, the language
of the backdam gold economy and of the most-read column in the Guyanese press.

WHERE A LAYER DOES NOT EXIST, IT IS DECLARED. Venezuela's statistics office stopped publishing
most series for years and PDVSA has published no audited accounts since 2016. `NO_LAWFUL_GROUND`
names each such hole by (jurisdiction, layer) with the reason AND the lawful substitute, because
the honest unit of absence in a four-country pack is the jurisdiction, never the province: a
layer another jurisdiction covers is not absent, it is just absent THERE.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Any

# --------------------------------------------------------------------------- identity
CODE = "ATLANTIC_ENERGY"
NAME = "The Atlantic hydrocarbon province (Guyana, Trinidad, Venezuela, Suriname)"
REGION_COMMAND = "latam"
REGION_DESK = "ATLANTIC_ENERGY"
FOREST = "latam"
#: The pack's nominal currency. All FOUR are declared in `CURRENCIES` and NONE of the four is
#: quoted by this broker; see `TRANSMISSION_TARGETS`.
CURRENCY = "GYD"
#: THE PARITY FENCE COUNTS THIS TUPLE (`scripts/check_regional_parity.py::jurisdictions_of`).
#: Four countries on the desk's own latam roster that no sibling pack answers for: `br`, `co`,
#: `mx`, `cl`, `ar`, `pe` and `bo` are each written around a domestic policy object that none of
#: these four has.
JURISDICTIONS: tuple[str, ...] = ("gy", "tt", "ve", "sr")
#: WHAT EACH JURISDICTION'S MONEY ACTUALLY IS. Not one of the four is a broker symbol, and the
#: four regimes are as different as four regimes get: a de facto stabilised rate, a rationed
#: managed rate, a thrice-redenominated hyperinflation, and a post-default float.
CURRENCIES: dict[str, dict[str, Any]] = {
    "gy": {"code": "GYD", "name": "Guyana dollar", "regime": "de facto stabilised",
           "authority": "Bank of Guyana",
           "fact": "the Bank of Guyana publishes a daily weighted mid from the bank and cambio "
                   "market and it has sat in a narrow band for years THROUGH the largest "
                   "per-capita oil boom in history -- the rent lands in the NRF and in the "
                   "import bill, not in the rate, which is exactly why the rate carries almost "
                   "no information and the FUND does",
           "broker_quoted": False,
           "status": "PRESS_REPORTED band; confirm against bankofguyana.org.gy"},
    "tt": {"code": "TTD", "name": "Trinidad and Tobago dollar", "regime": "managed, rationed",
           "authority": "Central Bank of Trinidad and Tobago",
           "fact": "quasi-pegged since 2016 and RATIONED: the central bank distributes foreign "
                   "exchange to authorised dealers, which creates a queue, a waiting time and an "
                   "informal premium. The premium -- not the posted rate -- is the observable",
           "broker_quoted": False,
           "status": "PRESS_REPORTED; confirm against central-bank.org.tt"},
    "ve": {"code": "VES", "name": "bolivar (digital)", "regime": "hyperinflation, dollarised",
           "authority": "Banco Central de Venezuela",
           "fact": "THREE REDENOMINATIONS -- 2008 (1,000:1), 2018 (100,000:1) and 2021 "
                   "(1,000,000:1) -- each of which invalidates any study pooled across it, plus "
                   "de facto dollarisation of retail transactions and a persistent official and "
                   "parallel spread",
           "broker_quoted": False, "status": "the redenomination dates are PRESS_REPORTED"},
    "sr": {"code": "SRD", "name": "Surinamese dollar", "regime": "post-default float",
           "authority": "Centrale Bank van Suriname",
           "fact": "devalued and then floated after the 2021 sovereign default; the 2023-2024 "
                   "bondholder settlement attached an OIL-LINKED value recovery instrument, "
                   "which makes the sovereign's credit a direct function of Block 58",
           "broker_quoted": False, "status": "PRESS_REPORTED; confirm against cbvs.sr"},
}
#: MM-DD, and the framework wants exactly five characters. Three of the four run the calendar
#: year; TRINIDAD DOES NOT -- see `FISCAL_YEARS`, where that difference is the point.
FISCAL_YEAR_END = "12-31"
FISCAL_YEARS: dict[str, str] = {
    "gy": "12-31: the Guyanese budget is presented in January for the calendar year, and the NRF "
          "withdrawal ceiling is set inside the Appropriation Act",
    "tt": "09-30: THE TRINIDADIAN FISCAL YEAR RUNS 1 OCTOBER TO 30 SEPTEMBER. The budget is read "
          "in late September or early October against an ASSUMED oil and gas price, and the gap "
          "between the assumption and the realised strip is a dated fiscal observable that a "
          "calendar-year assumption silently destroys",
    "ve": "12-31: nominal; the budget has not been a readable fiscal object for years",
    "sr": "12-31: the IMF programme reviews and the restructured bond coupons are the real clock",
}
NATIVE_LANGUAGES: tuple[str, ...] = ("en", "es", "nl", "srn", "gyn")
COT_CURRENCY = ""                  # no CFTC contract exists for any of the four currencies
EXPORT_ECONOMY = "energy_exporter"
RETAIL_LEVERAGE_REGIME = "restricted"
#: The depth this pack CLAIMS so a test can check the FRAMEWORK'S measurement against it rather
#: than against a number typed into a report. `regional_parity.pack_depth` computes the real one.
DECLARED_DEPTH: float = 1.0
MISSION = ("mine the Atlantic hydrocarbon province as ONE physical basin with four sovereigns "
           "on it: the Stabroek FPSO ramp as a dated, published, per-vessel supply curve; the "
           "Guyanese NRF receipts and the 75%-ceiling profit-oil formula as a computable "
           "sovereign take; Atlantic LNG train utilisation and the Point Lisas ammonia and "
           "methanol chain into the CORN and WHEAT nitrogen cost; the OFAC licence calendar and "
           "the OPEC two-series gap as the Venezuelan supply switch; the Essequibo referendum, "
           "Argyle and ICJ timestamps as a dated territorial-risk premium; Block 58 GranMorgu as "
           "the forward control; and the Caribbean tanker, bunkering and ship-to-ship plane that "
           "every barrel in the province physically crosses")

#: The instruments this pack may compile a cell against. Every one is in the broker registry and
#: none is a single-name equity. NONE OF THE FOUR LOCAL CURRENCIES IS HERE -- see
#: `TRANSMISSION_TARGETS`, where each is named with the route that carries its economics.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "XBRUSD",                          # the province's own barrel: Liza and Merey price off Brent
    "XTIUSD",                          # the US Gulf refinery gate every heavy-sour cargo aims at
    "XNGUSD",                          # the gas leg, carried WITH its basis risk stated in full
    "XAUUSD",                          # Guyanese and Surinamese gold, declared and undeclared
    "XALUSD",                          # Guyanese bauxite, the aluminium ore at the head of it
    "CORN",                            # the nitrogen-cost chain out of Point Lisas ammonia
    "WHEAT",                           # the second half of that chain and the acreage swing
    "SOYBEAN",                         # the third leg of the fertiliser-cost acreage decision
    "SUGAR",                           # GuySuCo and the Caricom and EU quota history
    "USDBRL",                          # the adjacent producer, the Roraima grid and the EM leg
    "USDMXN",                          # Maya against Merey: the competing heavy-sour grade
    "USDCNH",                          # the buyer of discounted barrels and of the methanol
    "US500",                           # the global risk state every province cell conditions on
    "XCUUSD",                          # THE DEMAND CONTROL: an oil move that also moves copper
)

#: WHAT THIS PROVINCE TRADES THAT THIS BROKER DOES NOT QUOTE. Each row names the absent object,
#: where it lives, WHY the pack needs it, the broker symbols that carry its economics, the ROUTE,
#: and -- the field that matters most here -- the BASIS RISK the route introduces. An absent
#: instrument produces a transmission hypothesis and never a cell that can never be filled
#: (L1.49).
TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "GYD (the Guyana dollar), the Bank of Guyana daily mid and the cambio market",
     "venue": "the licensed bank and cambio windows; the Bank of Guyana publishes the mid",
     "regime": "de facto stabilised against the dollar",
     "why": "GYD IS ABSENT from the broker registry. It is also, unusually, the LEAST informative "
            "variable in its own economy: the oil rent is sterilised into the Natural Resource "
            "Fund rather than passed into the rate, so the fiscal series carries what the "
            "currency does not",
     "proxies": ("USDBRL", "USDMXN", "XBRUSD"),
     "route": "the Guyanese macro state conditions the EM legs and the barrel; the NRF receipt "
              "series is the real dependent variable and it is a FISCAL series, not an FX one",
     "basis_risk": "USDBRL is a floating EM currency and GYD is stabilised; they share a risk "
                   "factor and not a mechanism, so the EM legs may be used as a CONDITIONER and "
                   "never as a proxy for the Guyanese rate itself"},
    {"name": "TTD (the Trinidad and Tobago dollar) and the RATIONED FX allocation",
     "venue": "the authorised dealers, to whom the CBTT distributes foreign exchange",
     "regime": "managed, quasi-pegged since 2016, with quantity rationing",
     "why": "TTD IS ABSENT. More importantly the posted rate is NOT the price: when a currency is "
            "rationed the adjustment happens in the QUEUE and in the informal premium, so the "
            "observable is the waiting time and the premium, both of which are reported in the "
            "Trinidadian press and neither of which is a broker symbol",
     "proxies": ("USDBRL", "USDMXN", "US500"),
     "route": "the FX-rationing state is a CONDITIONER on the gas and petrochemical domains: a "
              "shortfall that coincides with a rationing episode is a different object from one "
              "that does not",
     "basis_risk": "a rationed rate has no volatility by construction; using its stability as "
                   "evidence of calm is the classic peg fallacy and this pack refuses it"},
    {"name": "VES (the bolivar) and the official and parallel spread",
     "venue": "the BCV official rate and the widely quoted parallel references",
     "regime": "hyperinflation with three redenominations and de facto dollarisation",
     "why": "VES IS ABSENT, and any series through it is broken THREE TIMES by redenomination "
            "(2008, 2018, 2021). Venezuelan economic activity is better read in PHYSICAL units "
            "-- barrels, cargoes, tankers -- than in its own currency, which is the single most "
            "useful methodological fact in this pack",
     "proxies": ("XBRUSD", "XTIUSD", "USDMXN"),
     "route": "Venezuelan mechanisms terminate in the BARREL and in the heavy-sour competitor, "
              "never in a currency; the bolivar enters only as a regime label",
     "basis_risk": "none introduced, because no VES series is used: the refusal IS the method"},
    {"name": "SRD (the Surinamese dollar) and the restructured sovereign curve",
     "venue": "the CBvS auctions and the restructured bond with its oil-linked instrument",
     "regime": "post-default float",
     "why": "SRD IS ABSENT and so is the bond. The bond matters anyway: the 2023-2024 settlement "
            "attached a VALUE RECOVERY INSTRUMENT tied to Block 58 royalties, which makes "
            "Surinamese credit an explicit derivative of a dated oil development -- a rare, "
            "clean, published link between a sovereign and a barrel",
     "proxies": ("XBRUSD", "XAUUSD", "USDBRL"),
     "route": "the Surinamese fiscal state conditions the GranMorgu schedule cells and the gold "
              "cells; the credit leg is an INPUT and never a target",
     "basis_risk": "USDBRL carries LatAm risk appetite, not Surinamese credit; the two decouple "
                   "precisely on the days that matter, which is why the route is a conditioner"},
    {"name": "Atlantic LNG cargoes and the Atlantic-basin LNG netback",
     "venue": "the LNG spot market; assessments are published by price reporting agencies",
     "regime": "spot-and-term, with a netback that decides where a cargo sails",
     "why": "LNG IS NOT A BROKER SYMBOL. Trinidad's trains are the western hemisphere's oldest "
            "large LNG complex and their utilisation is the cleanest read on Trinidadian gas",
     "proxies": ("XNGUSD", "XBRUSD"),
     "route": "XNGUSD carries the GAS COMPLEX and is used only with the basis stated",
     "basis_risk": "HENRY HUB IS NOT ATLANTIC LNG. XNGUSD is a US pipeline-gas contract set by "
                   "US production, US storage and US weather. A Trinidadian train outage moves "
                   "the Atlantic LNG spread and the ammonia netback, and can move Henry Hub in "
                   "the OPPOSITE direction by freeing US cargoes. A study that swaps one for the "
                   "other measures the ARBITRAGE, not the shock. Every XNGUSD cell in this pack "
                   "carries a US-supply-and-weather control for exactly this reason"},
    {"name": "Ammonia (the Tampa CFR and Caribbean FOB assessments)",
     "venue": "price reporting agency assessments; the contract itself is bilateral",
     "regime": "monthly settled reference plus spot",
     "why": "AMMONIA IS NOT A BROKER SYMBOL and Point Lisas is one of the largest export ammonia "
            "complexes in the world. Nitrogen cost is a real input to the acreage decision",
     "proxies": ("CORN", "WHEAT", "SOYBEAN", "XNGUSD"),
     "route": "Trinidadian gas curtailment -> ammonia output and netback -> Atlantic nitrogen "
              "cost -> the CORN, WHEAT and SOYBEAN acreage and margin decision at the planting "
              "window; the control is the EUROPEAN gas-driven ammonia curtailment episodes, "
              "which move the same nitrogen price with NO Trinidadian event",
     "basis_risk": "nitrogen is a cost share and not a price driver; the effect is a MARGIN and "
                   "ACREAGE effect at seasonal horizons, never an intraday one, and any cell "
                   "that claims a same-day ammonia-to-corn response is measuring something else"},
    {"name": "Methanol (the posted Caribbean and US Gulf contract references)",
     "venue": "bilateral contracts against published posted references",
     "regime": "monthly posted price plus spot",
     "why": "METHANOL IS NOT A BROKER SYMBOL. Trinidad is among the largest methanol exporters "
            "on earth and methanol competes for the SAME molecule as ammonia and LNG, so the "
            "gas allocation between the three is itself a dated commercial decision",
     "proxies": ("XNGUSD", "USDCNH"),
     "route": "methanol demand is substantially Chinese (olefins and fuel blending), so the "
              "demand leg routes through USDCNH as a China-activity conditioner",
     "basis_risk": "USDCNH is a currency and methanol demand is a volume; the route is a weak "
                   "conditioner and is labelled WEAK wherever it is used"},
    {"name": "Merey 16 and the Venezuelan heavy-sour export grade",
     "venue": "term and spot sales, substantially to Asian buyers, at undisclosed discounts",
     "regime": "discounted, intermediated, and deliberately opaque",
     "why": "MEREY IS NOT A BROKER SYMBOL and its DISCOUNT is the whole point: when Venezuelan "
            "barrels are licensed they reach the US Gulf at a narrower discount, and when they "
            "are not they reach Asia at a wider one. The discount is the sanctions effect",
     "proxies": ("XBRUSD", "XTIUSD", "USDMXN"),
     "route": "the heavy-sour balance is read through the Brent-WTI relationship and through "
              "Mexican Maya as the competing grade; USDMXN is the Mexican leg",
     "basis_risk": "the Brent-WTI spread is driven overwhelmingly by US logistics, so a "
                   "heavy-sour claim must condition on US crude stocks and Cushing, or it is "
                   "measuring a pipeline"},
    {"name": "Liza, Unity Gold and the Guyanese crude grades",
     "venue": "term liftings and spot cargoes priced against dated Brent",
     "regime": "a medium-sweet grade sold on a Brent-linked formula",
     "why": "THE GUYANESE GRADE IS NOT A BROKER SYMBOL, but it prices against Brent by contract, "
            "which makes XBRUSD the correct and non-arbitrary carrier for the ramp",
     "proxies": ("XBRUSD",),
     "route": "the sanctioned-capacity series is a NON-OPEC SUPPLY series against XBRUSD",
     "basis_risk": "a medium-sweet grade's differential to dated Brent moves with the European "
                   "and Asian refining margin; the ramp cells use VOLUME and never a price "
                   "differential the pack cannot read"},
    {"name": "The Trinidad and Tobago Stock Exchange and the Guyana securities market",
     "venue": "stockex.co.tt; the Guyana market trades on a weekly-to-fortnightly cadence",
     "regime": "small, illiquid, no derivatives, no CFD",
     "why": "NO CFD IS QUOTED on either bourse and the two-lane order forbids hunting single "
            "names in any case. They are named so that a future session does not rediscover "
            "them and mistake their absence for an oversight",
     "proxies": ("US500", "USDBRL"),
     "route": "risk appetite only, as a conditioner",
     "basis_risk": "a market that trades a handful of times a week has a price path made of its "
                   "own trading calendar; it cannot carry a daily mechanism at all"},
)

# --------------------------------------------------------------------------- the central banks
#: THE FRAMEWORK TAKES ONE CENTRAL BANK. This pack's nominal one is the Bank of Guyana, because
#: Guyana is the jurisdiction whose mechanism the pack is built around; the other three are in
#: `CENTRAL_BANKS` with their own regimes, and NOT ONE of the four is a policy-surprise object of
#: the kind `br`, `mx` or `pe` carries. That is a measurement, not a gap: there is no scheduled
#: rate decision in this province that a liquid instrument reacts to, which is exactly why every
#: macro domain here terminates in a PHYSICAL series instead of a rate.
CENTRAL_BANK: dict[str, Any] = {
    "name": "Bank of Guyana (BoG)",
    "framework": "managed_float",
    "policy_instrument": "the reserve requirement, the Treasury bill auction and -- the real "
                         "instrument -- the sale of foreign exchange into the bank and cambio "
                         "market out of the oil receipts the government converts",
    "mandate": "monetary stability and the soundness of the financial system under the Bank of "
               "Guyana Act; there is NO published numeric inflation target, so there is no "
               "stated benchmark a surprise could be measured against (L1.28a)",
    "decision_rule": "NO SCHEDULED POLICY-RATE DECISION of the kind this desk mines elsewhere. "
                     "The Monetary Policy Committee meets and the Bank publishes a quarterly "
                     "and an annual report; the tradable clock in Guyana is the NRF RECEIPT and "
                     "the LIFTING, not a rate",
    "decision_calendar_rule": "quarterly reporting cadence; no dated rate announcement lattice "
                              "this pack is willing to invent",
    "decision_dates": (),
    "dates_status": "NOT LISTED, DELIBERATELY (L1.28a). There is no published decision calendar "
                    "with a market-moving announcement minute in Guyana, and inventing one would "
                    "manufacture an event series out of nothing. The pack's dated clocks are the "
                    "FPSO first-oil dates, the NRF monthly receipt and the cargo liftings",
    "decision_time_utc": "17:00",
    "announce_local": "13:00 America/Guyana (UTC-4 all year) for the Bank's own publications; "
                      "the number that matters is published by the Ministry of Finance, not here",
    "dst_rule": "NONE anywhere in this province. Guyana is UTC-4, Trinidad UTC-4, Venezuela "
                "UTC-4 (it moved back from UTC-4:30 on 2016-05-01) and Suriname UTC-3, and not "
                "one of the four observes daylight saving -- so every UTC window in this pack is "
                "the same minute in January and in July. That is rare on this desk and it is "
                "worth using: a session study here has no summer-winter regime at all",
    "minutes_lag_days": 0,
    "publication_classes": ("bog_quarterly_report", "bog_annual_report",
                            "bog_weekly_statistical_bulletin", "mof_nrf_quarterly_report",
                            "mof_mid_year_report", "bog_market_exchange_rates"),
    "policy_rate_series": "BOG:bank_rate",
    "expected_rate_series": "UNMEASURED",
    "consensus_proxy": "NONE EXISTS. No analyst survey covers Guyanese monetary policy and the "
                       "pack refuses to substitute the IMF Article IV projection for one",
    "consensus_proxy_trap": "an Article IV projection is annual, published with a long lag and "
                            "negotiated with the authorities; using it as a market expectation "
                            "would manufacture surprises nobody could have been surprised by",
    "reserves_clock": "the Bank publishes reserves in its statistical bulletin; the NRF balance "
                      "is published SEPARATELY by the Ministry of Finance and is the larger and "
                      "more informative of the two",
    "programme": "no IMF programme; Article IV consultation only",
    "root": "https://www.bankofguyana.org.gy",
}
#: THE OTHER THREE, each a different kind of object. The point of this table is that FOUR
#: NEIGHBOURING SOVEREIGNS RUN FOUR INCOMPATIBLE MONETARY REGIMES over one physical basin, which
#: makes the province its own natural experiment in what a currency regime does to an oil rent.
CENTRAL_BANKS: dict[str, dict[str, Any]] = {
    "gy": {"name": "Bank of Guyana", "framework": "managed_float", "root": "bankofguyana.org.gy",
           "instrument": "FX sales out of converted oil receipts; reserve requirements",
           "why": "the oil rent is sterilised into the NRF, so the exchange rate barely moves "
                  "and the FISCAL series carries the information"},
    "tt": {"name": "Central Bank of Trinidad and Tobago", "framework": "managed_float",
           "root": "central-bank.org.tt",
           "instrument": "the repo rate, plus the ALLOCATION of foreign exchange to authorised "
                         "dealers -- a QUANTITY instrument, which is the unusual part",
           "why": "when FX is rationed the adjustment is a queue rather than a price, so the "
                  "observable is the premium and the waiting time, neither of which is a rate"},
    "ve": {"name": "Banco Central de Venezuela", "framework": "UNMEASURED",
           "root": "bcv.org.ve",
           "instrument": "an official reference rate, periodic FX interventions into the banking "
                         "system, and reserve requirements that have been extreme by any standard",
           "why": "DECLARED UNMEASURED, not guessed: the publication record is broken, the "
                  "official and parallel rates diverge, and three redenominations mean no "
                  "continuous series exists at all"},
    "sr": {"name": "Centrale Bank van Suriname (CBvS)", "framework": "monetary_aggregate",
           "root": "cbvs.sr",
           "instrument": "reserve money targets under the IMF programme, FX auctions and an "
                         "open-market operations facility",
           "why": "the post-default regime is an IMF-monitored reserve-money target, so the "
                  "REVIEW CALENDAR is the clock rather than a policy meeting"},
}

# --------------------------------------------------------------------------- conventions
#: EVERY UTC WINDOW IN THIS PACK IS THE SAME MINUTE ALL YEAR. Guyana, Trinidad and Venezuela are
#: UTC-4 and Suriname is UTC-3, and none of the four observes daylight saving. The DST-bearing
#: benchmarks in this table are the LONDON and NEW YORK ones the province's barrels price
#: against, not the province's own clocks.
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "Dated Brent and the North Sea window -- the formula every Guyanese cargo settles on",
     "local": "16:30 Europe/London assessment window",
     "time_utc": "16:30", "time_utc_dst": "15:30", "dst_rule": "GMT/BST",
     "instruments": ("XBRUSD", "XTIUSD"), "window_minutes": 30,
     "why": "Liza and the other Guyanese grades sell on a dated-Brent-linked formula, which is "
            "what makes XBRUSD the contractually correct carrier for the ramp rather than a "
            "convenient one"},
    {"name": "NYMEX WTI settlement -- the US Gulf refinery gate the heavy-sour cargoes aim at",
     "local": "14:30 America/New_York", "time_utc": "19:30", "time_utc_dst": "18:30",
     "dst_rule": "EST/EDT", "instruments": ("XTIUSD", "XBRUSD"), "window_minutes": 2,
     "why": "the Venezuelan and Mexican heavy-sour balance clears at the US Gulf; WTI is the "
            "reference the refinery economics are quoted against"},
    {"name": "Henry Hub settlement -- carried ONLY with its basis risk stated",
     "local": "14:30 America/New_York", "time_utc": "19:30", "time_utc_dst": "18:30",
     "dst_rule": "EST/EDT", "instruments": ("XNGUSD",), "window_minutes": 2,
     "why": "the only gas contract the box quotes. It is a US PIPELINE contract and Trinidad "
            "exports LNG; the basis is stated in every gas row in this pack because a study that "
            "forgets it measures the arbitrage instead of the shock"},
    {"name": "LBMA Gold Price PM auction -- the Guyanese and Surinamese gold benchmark",
     "local": "15:00 Europe/London", "time_utc": "15:00", "time_utc_dst": "14:00",
     "dst_rule": "GMT/BST", "instruments": ("XAUUSD",), "window_minutes": 15,
     "why": "the Guyana Gold Board and the Surinamese exporters settle against the London "
            "benchmark; declared production is a counted physical series against a liquid metal"},
    {"name": "LME official settlement (aluminium) -- the bauxite chain's far end",
     "local": "12:00-13:00 Europe/London ring", "time_utc": "12:00", "time_utc_dst": "11:00",
     "dst_rule": "GMT/BST", "instruments": ("XALUSD", "XCUUSD"), "window_minutes": 60,
     "why": "Guyanese bauxite is an ORE two steps from the metal; the exchange contract is the "
            "only priced point on the chain and the distance is stated rather than hidden"},
    {"name": "The Guyana NRF monthly receipt and the cargo-lifting announcement",
     "local": "published by the Ministry of Finance during the Georgetown business day",
     "time_utc": "17:00", "time_utc_dst": "17:00",
     "dst_rule": "none: America/Guyana is UTC-4 all year",
     "instruments": ("XBRUSD", "XTIUSD"), "window_minutes": 120,
     "why": "THE PROVINCE'S OWN FIXING. A sovereign's oil receipt, by month, by cargo, published "
            "-- the nearest thing Guyana has to a scheduled macro release"},
    {"name": "The Trinidad Ministry of Energy monthly bulletin (field-level gas production)",
     "local": "published during the Port of Spain business day",
     "time_utc": "16:00", "time_utc_dst": "16:00",
     "dst_rule": "none: America/Port_of_Spain is UTC-4 all year",
     "instruments": ("XNGUSD", "CORN", "WHEAT"), "window_minutes": 120,
     "why": "gas production BY FIELD, monthly, published by the ministry: the decline is not an "
            "opinion here, it is a counted series with the operator's name on each line"},
    {"name": "The OPEC Monthly Oil Market Report -- and its TWO Venezuelan series",
     "local": "published mid-month by the OPEC Secretariat in Vienna",
     "time_utc": "11:00", "time_utc_dst": "10:00", "dst_rule": "CET/CEST",
     "instruments": ("XBRUSD", "XTIUSD"), "window_minutes": 60,
     "why": "the MOMR carries Venezuelan production twice -- direct communication and secondary "
            "sources -- and the two disagree. The GAP is the observable and it is published"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "Guyana NRF monthly receipt and the quarterly NRF report", "kind": "day_of_month",
     "days": (10, 11, 12, 13, 14, 15), "roll": "next", "window_utc": ("14:00", "21:00"),
     "instruments": ("XBRUSD", "XTIUSD"),
     "why": "the Ministry of Finance publishes what the fund received; a cargo-lifting month and "
            "a no-lifting month are different objects and the table says which is which"},
    {"name": "Trinidad Ministry of Energy monthly production bulletin", "kind": "day_of_month",
     "days": (20, 21, 22, 23, 24, 25), "roll": "next", "window_utc": ("14:00", "21:00"),
     "instruments": ("XNGUSD", "CORN"),
     "why": "field-level gas, crude and petrochemical output for the month two months back"},
    {"name": "OPEC MOMR and the Venezuelan two-series print", "kind": "day_of_month",
     "days": (11, 12, 13, 14, 15, 16, 17), "roll": "next", "window_utc": ("09:00", "13:00"),
     "instruments": ("XBRUSD", "XTIUSD"),
     "why": "mid-month; the direct-communication and secondary-source lines land together and "
            "the difference between them is the pack's cleanest sanctions observable"},
    {"name": "Month-end crude lifting and tanker fixing cycle", "kind": "month_end",
     "roll": "previous", "window_utc": ("12:00", "20:00"),
     "instruments": ("XBRUSD", "XTIUSD", "USDMXN"),
     "why": "cargo programmes for the following month are fixed around the month end; a lifting "
            "schedule is a physical commitment made weeks before the barrel moves"},
    {"name": "Quarter-end LNG and petrochemical contract repricing", "kind": "quarter_end",
     "roll": "previous", "window_utc": ("12:00", "20:00"),
     "instruments": ("XNGUSD", "CORN", "WHEAT"),
     "why": "posted ammonia and methanol references and term LNG formulas reset at quarter "
            "boundaries, which concentrates the netback decision into a few days"},
    {"name": "The TRINIDADIAN fiscal year end (30 September) and the budget statement",
     "kind": "fiscal_quarter_end", "roll": "previous", "window_utc": ("14:00", "22:00"),
     "instruments": ("XNGUSD", "XBRUSD", "USDBRL"),
     "why": "TRINIDAD'S BUDGET YEAR IS NOT THE CALENDAR YEAR. The budget is read in late "
            "September or early October against an ASSUMED oil and gas price, and the gap "
            "between that assumption and the realised strip is a dated fiscal observable"},
    {"name": "The Guyanese fiscal year end (31 December) and the January budget",
     "kind": "fiscal_year_end", "roll": "previous", "window_utc": ("14:00", "21:00"),
     "instruments": ("XBRUSD", "SUGAR"),
     "why": "the Appropriation Act sets the NRF withdrawal ceiling for the year, which is the "
            "one number that converts an oil price into domestic spending"},
    {"name": "Restructured Surinamese bond coupon and value-recovery observation dates",
     "kind": "weekday", "weekday": 2, "roll": "next", "window_utc": ("13:00", "20:00"),
     "instruments": ("XBRUSD", "XAUUSD"),
     "why": "the 2023-2024 settlement attached an oil-linked instrument, so a Surinamese credit "
            "date is a barrel date; the exact schedule is PRESS_REPORTED and must be confirmed"},
)

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Trinidad and Tobago Stock Exchange (TTSE)",
     "index_symbols": (), "open_local": "09:30", "close_local": "12:00",
     "open_utc": "13:30", "close_utc": "16:00",
     "dst_rule": "none: America/Port_of_Spain is UTC-4 all year",
     "auction": "a short continuous session; the market is small and thinly traded",
     "expiry_rule": "NO listed derivatives market and therefore no expiry clock to mine",
     "holidays": "the Trinidadian public-holiday calendar, including Carnival, which shuts the "
                 "entire country for two days that are not on the statutory list",
     "notes": "NO CFD IS QUOTED on any TTSE index, so the bourse enters this pack only as a "
              "transmission target. Its constituents are banks, conglomerates and the "
              "petrochemical chain, all of which are ACTORS here and never instruments"},
    {"name": "The Guyana securities market (GASCI)",
     "index_symbols": (), "open_local": "09:00", "close_local": "12:00",
     "open_utc": "13:00", "close_utc": "16:00",
     "dst_rule": "none: America/Guyana is UTC-4 all year",
     "auction": "a call market trading on a weekly to fortnightly cadence",
     "expiry_rule": "none; there is no derivatives market",
     "holidays": "the Guyanese four-faith public-holiday calendar",
     "notes": "a market that trades a handful of times a week has a price path made of its own "
              "trading calendar. It cannot carry a daily mechanism and this pack does not ask "
              "it to; it is registered so that its absence is a measurement rather than a gap"},
    {"name": "The PHYSICAL EXPORT GATE: the Demerara and Berbice anchorages, Point Lisas, Point "
             "Fortin, Jose and Amuay, and the Paramaribo river ports",
     "index_symbols": (), "open_local": "00:00", "close_local": "23:59",
     "open_utc": "04:00", "close_utc": "03:59",
     "dst_rule": "none anywhere in the province",
     "auction": "none; the clock is the SAILING SCHEDULE and the ship-to-ship transfer",
     "expiry_rule": "no expiry; a cargo is fixed, loaded and sails",
     "holidays": "terminals work through the national calendars; Carnival does not stop a tanker",
     "notes": "THE ONLY VENUE IN THIS PACK THAT ACTUALLY CLEARS ANYTHING. Guyanese crude loads "
              "at offshore anchorages with no jetty at all, Trinidadian LNG loads at Point "
              "Fortin, and Venezuelan heavy sour leaves Jose -- increasingly via ship-to-ship "
              "transfer, which is why tanker-tracking press reports are the lawful substitute "
              "for a statistics office that stopped publishing"},
)

SESSION_WINDOWS: tuple[dict[str, Any], ...] = (
    {"name": "ae_province_business_day", "start_utc": "12:00", "end_utc": "21:00",
     "notes": "Georgetown, Port of Spain, Caracas and Paramaribo all inside one window, and the "
              "window NEVER MOVES because no jurisdiction in the province observes daylight "
              "saving -- the rarest convenience on this desk"},
    {"name": "ae_brent_window", "start_utc": "15:30", "end_utc": "16:30",
     "notes": "the dated-Brent assessment window the province's crude contracts settle against; "
              "this one DOES move with London's clocks and the pack says so"},
    {"name": "ae_us_gulf_afternoon", "start_utc": "18:30", "end_utc": "19:30",
     "notes": "the WTI and Henry Hub settlement window, where the heavy-sour and gas legs price"},
    {"name": "ae_opec_momr", "start_utc": "10:00", "end_utc": "12:00",
     "notes": "the mid-month OPEC release window that carries the Venezuelan two-series gap"},
    {"name": "ae_ofac_publication", "start_utc": "14:00", "end_utc": "22:00",
     "notes": "US Treasury and Federal Register publications land inside the Washington business "
              "day; a licence issued, revoked or amended is a supply event with a timestamp"},
)

RELEASE_CLASSES: tuple[dict[str, Any], ...] = (
    {"name": "Guyana Natural Resource Fund monthly receipt and quarterly report",
     "cadence": "monthly", "time_utc": "17:00", "source": "Ministry of Finance, Guyana",
     "actual_series": "MOF_GY:nrf_receipts", "expected_series": "n/a",
     "notes": "profit oil plus royalty, by month, with the cargo liftings named; the withdrawal "
              "ceiling is statutory under the 2021 NRF Act and is set in the Appropriation Act"},
    {"name": "Trinidad Ministry of Energy monthly bulletin (gas and crude by field)",
     "cadence": "monthly", "time_utc": "16:00",
     "source": "Ministry of Energy and Energy Industries, Trinidad and Tobago",
     "actual_series": "MEEI:gas_production_by_field", "expected_series": "n/a",
     "notes": "FIELD-LEVEL gas production with the operator named, plus LNG, ammonia and "
              "methanol output -- one of the most granular energy statistics published anywhere"},
    {"name": "OPEC Monthly Oil Market Report: Venezuela, direct and secondary",
     "cadence": "monthly", "time_utc": "11:00", "source": "OPEC Secretariat",
     "actual_series": "OPEC:ve_production_secondary",
     "expected_series": "OPEC:ve_production_direct",
     "notes": "TWO SERIES THAT DISAGREE, published side by side, and the gap is the observable"},
    {"name": "EIA Short-Term Energy Outlook and Weekly Petroleum Status Report",
     "cadence": "monthly and weekly", "time_utc": "15:00",
     "source": "US Energy Information Administration",
     "actual_series": "EIA:crude_imports_by_origin", "expected_series": "EIA:steo_forecast",
     "notes": "US crude imports BY COUNTRY OF ORIGIN is the cleanest published read on whether "
              "Venezuelan and Guyanese barrels are actually reaching the US Gulf"},
    {"name": "OFAC licence, FAQ and Federal Register publication",
     "cadence": "irregular, event-driven", "time_utc": "18:00",
     "source": "US Department of the Treasury and the Federal Register",
     "actual_series": "OFAC:venezuela_licences", "expected_series": "n/a",
     "notes": "a general or specific licence issued, amended, revoked or allowed to expire is a "
              "DATED SUPPLY EVENT. It is a published administrative act and reading it is lawful"},
    {"name": "Bank of Guyana statistical bulletin and market exchange rates",
     "cadence": "weekly and quarterly", "time_utc": "17:00", "source": "Bank of Guyana",
     "actual_series": "BOG:market_rates", "expected_series": "n/a",
     "notes": "the bank and cambio mid, reserves and monetary aggregates; the rate itself is "
              "nearly constant, which is the finding rather than a data problem"},
    {"name": "Central Bank of Trinidad and Tobago monetary policy announcement",
     "cadence": "quarterly", "time_utc": "18:00",
     "source": "Central Bank of Trinidad and Tobago",
     "actual_series": "CBTT:repo_rate", "expected_series": "n/a",
     "notes": "the repo rate moves rarely; the FX ALLOCATION is the instrument that matters and "
              "it is reported as a quantity, not announced as a price"},
    {"name": "Bureau of Statistics Guyana national accounts and trade",
     "cadence": "quarterly", "time_utc": "17:00", "source": "Bureau of Statistics, Guyana",
     "actual_series": "BOS_GY:gdp_oil_and_nonoil", "expected_series": "n/a",
     "notes": "the oil and non-oil split is published separately, which is what makes Guyana a "
              "readable natural experiment in what an oil rent does to a small economy"},
    {"name": "Centrale Bank van Suriname and the IMF programme review",
     "cadence": "monthly and semi-annual", "time_utc": "16:00",
     "source": "Centrale Bank van Suriname and the IMF",
     "actual_series": "CBVS:reserve_money", "expected_series": "IMF:programme_target",
     "notes": "a reserve-money target with a published review calendar; the review dates are the "
              "Surinamese macro clock and they are announced in advance"},
    {"name": "ICJ procedural orders in Guyana v. Venezuela",
     "cadence": "irregular, court-scheduled", "time_utc": "13:00",
     "source": "International Court of Justice",
     "actual_series": "ICJ:guyana_v_venezuela_docket", "expected_series": "n/a",
     "notes": "a published court calendar: memorials, counter-memorials, hearings and orders, "
              "each with a date fixed in advance and announced by the Court"},
)

# --------------------------------------------------------------------------- holidays
#: FOUR GREGORIAN CALENDARS THAT DO NOT AGREE, AND ONE OF THEM HAS FOUR FAITHS IN IT.
#: Rows are (month, day, name). Everything Easter-derived is COMPUTED in `easter(year)` and
#: everything lunar is TYPED PER YEAR with the authority that gazettes it named in
#: `LUNAR_AUTHORITY` -- because an Islamic or Hindu date that cannot be computed from a rule is
#: honest when it is typed with its authority and a lie when it is guessed from a formula.
FIXED_HOLIDAYS: dict[str, tuple[tuple[int, int, str], ...]] = {
    "gy": ((1, 1, "New Year's Day"),
           (2, 23, "Republic Day (Mashramani)"),
           (5, 1, "Labour Day"),
           (5, 5, "Arrival Day"),
           (5, 26, "Independence Day"),
           (8, 1, "Emancipation Day"),
           (12, 25, "Christmas Day"),
           (12, 26, "Boxing Day")),
    "tt": ((1, 1, "New Year's Day"),
           (3, 30, "Spiritual (Shouter) Baptist Liberation Day"),
           (5, 30, "Indian Arrival Day"),
           (6, 19, "Labour Day"),
           (8, 1, "Emancipation Day"),
           (8, 31, "Independence Day"),
           (9, 24, "Republic Day"),
           (12, 25, "Christmas Day"),
           (12, 26, "Boxing Day")),
    "ve": ((1, 1, "Ano Nuevo"),
           (4, 19, "Declaracion de la Independencia (19 de abril)"),
           (5, 1, "Dia del Trabajador"),
           (6, 24, "Batalla de Carabobo"),
           (7, 5, "Dia de la Independencia (5 de julio)"),
           (7, 24, "Natalicio de Simon Bolivar"),
           (10, 12, "Dia de la Resistencia Indigena"),
           (12, 25, "Navidad")),
    "sr": ((1, 1, "Nieuwjaar"),
           (5, 1, "Dag van de Arbeid"),
           (7, 1, "Keti Koti (Dag der Vrijheden)"),
           (8, 9, "Dag der Inheemsen"),
           (10, 10, "Dag der Marrons"),
           (11, 25, "Onafhankelijkheidsdag"),
           (12, 25, "Eerste Kerstdag"),
           (12, 26, "Tweede Kerstdag")),
}
#: EASTER OFFSETS, in days from Easter Sunday. Venezuela keeps Carnival as a STATUTORY holiday
#: and Trinidad does not -- yet Trinidad is the country Carnival actually shuts. That asymmetry
#: is carried deliberately: `CARNIVAL_SHUTDOWN` holds the Trinidadian days, which are not on the
#: statutory list and close the country anyway, and a liquidity study that reads only the
#: gazette will treat the two loudest days of the Trinidadian year as ordinary ones.
EASTER_OFFSETS: dict[str, tuple[tuple[int, str], ...]] = {
    "gy": ((-2, "Good Friday"), (1, "Easter Monday")),
    "tt": ((-2, "Good Friday"), (1, "Easter Monday"), (60, "Corpus Christi")),
    "ve": ((-48, "Lunes de Carnaval"), (-47, "Martes de Carnaval"),
           (-3, "Jueves Santo"), (-2, "Viernes Santo")),
    "sr": ((-2, "Goede Vrijdag"), (1, "Tweede Paasdag")),
}
#: THE TWO DAYS TRINIDAD STOPS AND THE GAZETTE DOES NOT SAY SO. Carnival Monday and Tuesday are
#: Easter minus 48 and 47, they are DERIVABLE, they are not statutory public holidays in Trinidad
#: and Tobago, and the country -- offices, banks, the exchange, the ports' paperwork -- shuts for
#: them. This pack carries them as a SEPARATE closure table for exactly that reason.
CARNIVAL_SHUTDOWN_CC: tuple[str, ...] = ("tt",)
#: LUNAR DATES, TYPED PER YEAR WITH THEIR AUTHORITY. Guyana is the reason this table exists: it
#: is the only jurisdiction on this desk that carries CHRISTIAN, HINDU AND ISLAMIC national
#: holidays at once, because roughly two fifths of Guyanese are of Indian descent and the
#: Indo-Guyanese population is itself split between Hindu and Muslim. Phagwah and Diwali move
#: with the Hindu luni-solar calendar; Eid-ul-Adha and Youman Nabi move with the Islamic lunar
#: calendar and are gazetted each year after the sighting. NONE of these can be computed from a
#: weekday rule, so they are typed, and their status says so.
LUNAR_HOLIDAYS: dict[str, dict[int, tuple[tuple[str, str], ...]]] = {
    "gy": {2024: (("2024-03-25", "Phagwah (Holi)"),
                  ("2024-06-17", "Eid-ul-Adha"),
                  ("2024-09-16", "Youman Nabi (Mawlid an-Nabi)"),
                  ("2024-10-31", "Diwali")),
           2025: (("2025-03-14", "Phagwah (Holi)"),
                  ("2025-06-07", "Eid-ul-Adha"),
                  ("2025-09-05", "Youman Nabi (Mawlid an-Nabi)"),
                  ("2025-10-20", "Diwali")),
           2026: (("2026-03-04", "Phagwah (Holi)"),
                  ("2026-05-27", "Eid-ul-Adha"),
                  ("2026-08-25", "Youman Nabi (Mawlid an-Nabi)"),
                  ("2026-11-08", "Diwali"))},
    "tt": {2024: (("2024-04-10", "Eid-ul-Fitr"), ("2024-10-31", "Divali")),
           2025: (("2025-03-31", "Eid-ul-Fitr"), ("2025-10-20", "Divali")),
           2026: (("2026-03-20", "Eid-ul-Fitr"), ("2026-11-08", "Divali"))},
    "ve": {2024: (), 2025: (), 2026: ()},
    "sr": {2024: (("2024-03-25", "Holi Phagwa"), ("2024-04-10", "Id-ul-Fitr"),
                  ("2024-10-31", "Divali")),
           2025: (("2025-03-14", "Holi Phagwa"), ("2025-03-31", "Id-ul-Fitr"),
                  ("2025-10-20", "Divali")),
           2026: (("2026-03-04", "Holi Phagwa"), ("2026-03-20", "Id-ul-Fitr"),
                  ("2026-11-08", "Divali"))},
}
#: WHO GAZETTES THE LUNAR DATE, per jurisdiction. This is the field that makes a typed date
#: honest: the pack is not claiming to have computed these, it is naming who publishes them.
LUNAR_AUTHORITY: dict[str, str] = {
    "gy": "the Ministry of Home Affairs of Guyana gazettes the public holidays each year; the "
          "Islamic dates follow the local sighting announcement and the Hindu dates follow the "
          "panchang used by the Guyana Hindu Dharmic Sabha. TYPED HERE, NOT COMPUTED, and any "
          "cell compiled on one of these dates is UNMEASURED until the gazette is joined",
    "tt": "the Office of the Prime Minister of Trinidad and Tobago publishes the public-holiday "
          "list; Eid-ul-Fitr follows the local sighting. TYPED, NOT COMPUTED",
    "ve": "not applicable: the Venezuelan calendar carries no lunar national holiday",
    "sr": "the Surinamese government publishes the vrije dagen by resolution; Holi Phagwa, "
          "Id-ul-Fitr and Divali follow the same religious calendars as Guyana's. TYPED",
}


def easter(year: int) -> date:
    """Easter Sunday by the ANONYMOUS GREGORIAN ALGORITHM.

    Every movable Christian date in this pack -- Good Friday and Easter Monday in Guyana,
    Trinidad and Suriname, Jueves and Viernes Santo and the two Carnival days in Venezuela,
    Corpus Christi in Trinidad, and the Trinidadian Carnival shutdown -- is an offset from it,
    COMPUTED rather than typed, so the tables extend to any year without anybody editing them.
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


def carnival(year: int) -> tuple[date, date]:
    """Carnival Monday and Tuesday: Easter minus 48 and 47.

    STATUTORY in Venezuela, NOT statutory in Trinidad, and the two days on which Trinidad --
    offices, banks, the exchange, the ministries -- actually stops. Both facts are true at once
    and a liquidity study that reads only the gazette gets Trinidad exactly backwards.
    """
    base = easter(year)
    return base - timedelta(days=48), base - timedelta(days=47)


def ash_wednesday(year: int) -> date:
    """The day after Carnival Tuesday, and the day Trinidad goes back to work."""
    return easter(year) - timedelta(days=46)


def corpus_christi(year: int) -> date:
    """Easter plus 60 days -- a Trinidadian public holiday and nobody else's in this province."""
    return easter(year) + timedelta(days=60)


def caricom_day(year: int) -> date:
    """The first Monday of July: a Guyanese public holiday, derived and never typed."""
    first = date(year, 7, 1)
    return first + timedelta(days=(0 - first.weekday()) % 7)


def national_holidays(cc: str, year: int) -> dict[date, str]:
    """One jurisdiction's statutory closure table for a year: fixed days, Easter-derived days,
    the derived rule days and the typed lunar days. Keys are dates inside `year` by construction.
    """
    code = str(cc).lower()
    out: dict[date, str] = {}
    for month, day, name in FIXED_HOLIDAYS.get(code, ()):
        out[date(year, month, day)] = name
    base = easter(year)
    for offset, name in EASTER_OFFSETS.get(code, ()):
        out[base + timedelta(days=offset)] = name
    if code == "gy":
        out[caricom_day(year)] = "CARICOM Day"
    for iso, name in LUNAR_HOLIDAYS.get(code, {}).get(year, ()):
        got = date.fromisoformat(iso)
        if got.year == year:
            out[got] = name
    return dict(sorted(out.items()))


def carnival_shutdown(year: int) -> dict[date, str]:
    """The Trinidadian Carnival closure -- NOT a statutory holiday, and the country shuts."""
    monday, tuesday = carnival(year)
    return {monday: "Carnival Monday (tt: NOT a statutory holiday; the country shuts)",
            tuesday: "Carnival Tuesday (tt: NOT a statutory holiday; the country shuts)"}


def province_holidays(year: int) -> dict[date, str]:
    """THE UNION TABLE: every day on which at least one jurisdiction of this province is closed,
    tagged with which ones. A date two countries share carries both names, because the whole
    point of a province-level calendar is telling a shared closure from a national one."""
    tagged: dict[date, list[str]] = {}
    for cc in JURISDICTIONS:
        for day, name in national_holidays(cc, year).items():
            tagged.setdefault(day, []).append(f"{cc}: {name}")
    for day, name in carnival_shutdown(year).items():
        tagged.setdefault(day, []).append(name)
    return {day: " | ".join(names) for day, names in sorted(tagged.items())}


def market_holidays(year: int) -> dict[date, str]:
    """The province's closed WEEKDAYS. A holiday that lands on a Saturday or a Sunday costs no
    session in any of the four jurisdictions -- none of them substitutes a weekend holiday onto
    the following Monday as a general rule -- so it must never enter a liquidity sample."""
    return {d: n for d, n in province_holidays(year).items() if d.weekday() < 5}


def shared_closures(year: int, minimum: int = 3) -> dict[date, int]:
    """Dates on which `minimum` or more of the four jurisdictions are closed at once.

    THE ONLY DAYS ON WHICH THE WHOLE PROVINCE IS ILLIQUID TOGETHER. Everything else is one
    country's holiday against three working neighbours, which is a completely different object:
    a single-jurisdiction closure is a NATURAL CONTROL, and a shared one is a liquidity regime.
    """
    counts: dict[date, int] = {}
    for cc in JURISDICTIONS:
        for day in national_holidays(cc, year):
            counts[day] = counts.get(day, 0) + 1
    return {d: n for d, n in sorted(counts.items()) if n >= minimum}


def is_closed_in(cc: str, day: date) -> bool:
    """True when that one jurisdiction is statutorily closed on that day."""
    return day in national_holidays(cc, day.year)


HOLIDAYS_RULE: dict[str, Any] = {
    "kind": "four_gregorian_calendars_computed_plus_typed_lunar",
    "authority": "the Guyanese public holidays are gazetted by the Ministry of Home Affairs; the "
                 "Trinidadian list is published by the Office of the Prime Minister; the "
                 "Venezuelan feriados sit in the Ley Organica del Trabajo and the Gaceta "
                 "Oficial; the Surinamese vrije dagen are set by government resolution",
    "rule": "FOUR GREGORIAN CALENDARS, none of which agrees with the others. The fixed national "
            "days are in `FIXED_HOLIDAYS` per jurisdiction. Everything Christian and movable is "
            "COMPUTED from `easter(year)` with the anonymous Gregorian algorithm -- Good Friday "
            "(Easter minus 2) and Easter Monday (Easter plus 1) in Guyana, Trinidad and "
            "Suriname, Jueves Santo (minus 3), Viernes Santo (minus 2) and the two CARNIVAL days "
            "(minus 48 and minus 47) in Venezuela, and Corpus Christi (Easter plus 60) in "
            "Trinidad. Guyana's CARICOM Day is the FIRST MONDAY OF JULY and is derived, never "
            "typed. GUYANA'S FOUR-FAITH CALENDAR is the distinguishing fact of this table: it "
            "carries Christian, HINDU (Phagwah and Diwali) and ISLAMIC (Eid-ul-Adha and Youman "
            "Nabi) national holidays at once, none of which can be computed from a weekday rule, "
            "so all of them are TYPED per year in `LUNAR_HOLIDAYS` with the gazetting authority "
            "named in `LUNAR_AUTHORITY`. TRINIDAD'S CARNIVAL MONDAY AND TUESDAY ARE NOT ON THE "
            "STATUTORY LIST AND SHUT THE COUNTRY, and are carried separately in "
            "`carnival_shutdown(year)` for exactly that reason. NO WEEKEND SUBSTITUTION is "
            "applied anywhere: a feriado on a Sunday is lost, which is itself a liquidity fact",
    "years": (2024, 2025, 2026),
    "weekend": "Saturday and Sunday",
    "national_rule": "`national_holidays(cc, year)` per jurisdiction",
    "market_rule": "`market_holidays(year)`: the province union on weekdays only",
    "shared_rule": "`shared_closures(year, minimum)`: the days on which three or four of the "
                   "four are shut at once -- the only days the whole province is illiquid "
                   "together, and the reason a single-country holiday is a natural CONTROL",
    "dst": "NONE. Guyana, Trinidad and Venezuela are UTC-4 and Suriname is UTC-3, and not one of "
           "the four observes daylight saving, so every UTC window in this pack is the same "
           "minute in January and in July",
    "table": {y: {d.isoformat(): n for d, n in province_holidays(y).items()}
              for y in (2024, 2025, 2026)},
    "status": {2024: "STATUTORY for the fixed days, COMPUTED for the Easter-derived days, TYPED "
                     "with authority for the lunar days",
               2025: "STATUTORY and COMPUTED; the lunar days are TYPED with authority",
               2026: "STATUTORY and COMPUTED; the 2026 lunar days are TYPED and are the least "
                     "certain rows in this pack -- Phagwah, Eid-ul-Adha, Youman Nabi, Eid-ul-Fitr "
                     "and Diwali 2026 must be confirmed against the gazette before promotion"},
    "known_dates": {
        "2024-02-12": "Carnival Monday, Trinidad -- not statutory, and the country is shut",
        "2024-02-23": "Republic Day (Mashramani), Guyana, a fixed solar date",
        "2024-10-31": "Diwali in Guyana, Trinidad AND Suriname on the same day -- a three-country "
                      "closure the province-level table is built to show",
        "2025-03-03": "Carnival Monday 2025, computed from Easter on 20 April",
        "2025-11-25": "Onafhankelijkheidsdag, Suriname, a fixed solar date",
        "2026-02-16": "Carnival Monday 2026, computed from Easter on 5 April",
        "2026-09-24": "Republic Day, Trinidad and Tobago, a fixed solar date",
    },
    "repealed": "Suriname's 25 February (Dag van de Revolutie) has been amended out of the "
                "national list in the recent past; it is NOT carried in the table because the "
                "pack has not read the resolution, and a closure claimed without its instrument "
                "is worse than an absence declared (L1.28a)",
    "fn": market_holidays,
    "national_fn": national_holidays,
    "province_fn": province_holidays,
    "shared_fn": shared_closures,
    "easter_fn": easter,
    "carnival_fn": carnival,
}

# ------------------------------------------------------------------- the ramp: the pack's spine
#: THE PUBLISHED, DATED, SANCTIONED SUPPLY CURVE. Rows are
#: (vessel, project, block, jurisdiction, sanction_date, first_oil, nameplate_bpd, status,
#:  date_status). `status` is PRODUCING / SANCTIONED_TARGETED. `date_status` is the confidence
#: label on the DATE, and it is separate on purpose: a first-oil date the operator has announced
#: in a press release is not the same object as one taken from a trade-press report.
#:
#: WHY THIS TABLE IS THE POINT OF THE PACK. Every row was publicly announced YEARS before the
#: barrels arrived: the final investment decision, the vessel's name, its nameplate capacity and
#: the target month. That is a dated multi-year NON-OPEC SUPPLY CURVE against a liquid contract,
#: and it is nearly unique -- almost every other supply forecast on this desk is somebody's
#: model output rather than a sanctioned engineering schedule with a hull already in a shipyard.
FPSO_SCHEDULE: tuple[tuple[str, str, str, str, str, str, int, str, str], ...] = (
    ("Liza Destiny", "Liza Phase 1", "Stabroek", "gy", "2017-06-16", "2019-12-20", 120_000,
     "PRODUCING", "OPERATOR_ANNOUNCED"),
    ("Liza Unity", "Liza Phase 2", "Stabroek", "gy", "2019-05-10", "2022-02-11", 220_000,
     "PRODUCING", "OPERATOR_ANNOUNCED"),
    ("Prosperity", "Payara", "Stabroek", "gy", "2020-09-30", "2023-11-14", 220_000,
     "PRODUCING", "OPERATOR_ANNOUNCED"),
    ("ONE GUYANA", "Yellowtail", "Stabroek", "gy", "2022-04-01", "2025-08-15", 250_000,
     "PRODUCING", "PRESS_REPORTED"),
    ("Errea Wittu", "Uaru", "Stabroek", "gy", "2023-04-01", "2026-12-31", 250_000,
     "SANCTIONED_TARGETED", "TARGET_ANNOUNCED"),
    ("Jaguar", "Whiptail", "Stabroek", "gy", "2024-04-12", "2027-12-31", 250_000,
     "SANCTIONED_TARGETED", "TARGET_ANNOUNCED"),
    ("Hammerhead", "Hammerhead", "Stabroek", "gy", "2025-06-30", "2029-12-31", 150_000,
     "SANCTIONED_TARGETED", "PRESS_REPORTED"),
    ("GranMorgu", "Block 58", "Block 58", "sr", "2024-10-01", "2028-12-31", 220_000,
     "SANCTIONED_TARGETED", "OPERATOR_ANNOUNCED"),
)
#: NAMEPLATE IS NOT OUTPUT, AND THE DIFFERENCE IS A MECHANISM. Every vessel in this basin has run
#: ABOVE its design capacity after debottlenecking, which is how a nameplate stack of roughly
#: 1.46 mb/d becomes the ~1.7 mb/d the operator projects for 2030. A study that uses nameplate as
#: production is systematically SHORT the supply, and one that uses the projection as nameplate
#: has imported a forecast into a schedule. The pack keeps them apart by name.
DEBOTTLENECK_NOTE = ("measured output per vessel has run 10-25% above nameplate after "
                     "debottlenecking; `sanctioned_capacity_on` returns NAMEPLATE ONLY and the "
                     "uplift is an estimated parameter a cell must declare, never a constant "
                     "folded silently into the series")


def fpso_rows(jurisdiction: str = "") -> tuple[dict[str, Any], ...]:
    """The schedule as rows, optionally for one jurisdiction."""
    want = str(jurisdiction).lower()
    out: list[dict[str, Any]] = []
    for vessel, project, block, cc, fid, first, cap, status, dstat in FPSO_SCHEDULE:
        if want and cc != want:
            continue
        out.append({"vessel": vessel, "project": project, "block": block, "jurisdiction": cc,
                    "sanction_date": fid, "first_oil": first, "nameplate_bpd": cap,
                    "status": status, "date_status": dstat})
    return tuple(out)


def sanctioned_capacity_on(day: date, jurisdiction: str = "gy") -> int:
    """THE MECHANISM. Cumulative NAMEPLATE capacity actually producing on `day`, in barrels/day.

    Only vessels whose status is PRODUCING and whose first oil is on or before `day` count: a
    sanctioned vessel that has not started is a FORWARD schedule, not supply, and folding the two
    together is the single easiest way to turn this series into a forecast and then test the
    forecast instead of the fact. The forward half is `scheduled_capacity_on`.
    """
    total = 0
    for _v, _p, _b, cc, _fid, first, cap, status, _ds in FPSO_SCHEDULE:
        if jurisdiction and cc != str(jurisdiction).lower():
            continue
        if status == "PRODUCING" and date.fromisoformat(first) <= day:
            total += cap
    return total


def scheduled_capacity_on(day: date, jurisdiction: str = "gy") -> int:
    """Cumulative nameplate of every vessel -- producing OR sanctioned-and-targeted -- whose
    first-oil date is on or before `day`. This is the FORWARD curve the market is pricing, and
    it differs from `sanctioned_capacity_on` exactly on the dates that carry information."""
    total = 0
    for _v, _p, _b, cc, _fid, first, cap, _status, _ds in FPSO_SCHEDULE:
        if jurisdiction and cc != str(jurisdiction).lower():
            continue
        if date.fromisoformat(first) <= day:
            total += cap
    return total


def ramp_steps(jurisdiction: str = "gy") -> tuple[tuple[date, int, str], ...]:
    """Every dated STEP in the capacity curve: (first oil date, new cumulative nameplate, vessel).

    The steps are the events. A continuous ramp has no event structure a study can condition on;
    a step function announced years in advance has one step per vessel, and each step is the
    cell that `AE-A` mints.
    """
    rows = sorted(fpso_rows(jurisdiction), key=lambda r: str(r["first_oil"]))
    out: list[tuple[date, int, str]] = []
    running = 0
    for row in rows:
        running += int(row["nameplate_bpd"])
        out.append((date.fromisoformat(str(row["first_oil"])), running, str(row["vessel"])))
    return tuple(out)


# ------------------------------------------------- the sovereign take: a published formula
#: THE 2016 STABROEK PRODUCTION SHARING AGREEMENT, as published. Cost recovery is capped at 75%
#: of revenue, the residual profit oil is split 50/50 between the contractor group and the state,
#: and a 2% royalty is paid on gross revenue. THE 2023 MODEL PSA IS A DIFFERENT CONTRACT --
#: 10% royalty, a 65% cost ceiling and a 10% corporate tax -- and it applies to NEWLY AWARDED
#: blocks, not to Stabroek. Pooling a fiscal study across the two measures two contracts.
PSA_TERMS: dict[str, dict[str, float | str]] = {
    "stabroek_2016": {"cost_ceiling": 0.75, "profit_split_government": 0.50, "royalty": 0.02,
                      "corporate_tax": 0.0,
                      "note": "the contractor's income tax is paid on its behalf by the state "
                              "out of the state's profit-oil share, which is why the headline "
                              "50/50 and the effective take are different numbers"},
    "model_2023": {"cost_ceiling": 0.65, "profit_split_government": 0.50, "royalty": 0.10,
                   "corporate_tax": 0.10,
                   "note": "applies to blocks awarded in and after the 2022-2023 licensing "
                           "round; NOT to Stabroek. A fiscal cell must declare which regime it "
                           "is computed under or it is comparing two contracts"},
}


def government_take(revenue: float, recoverable_costs: float,
                    regime: str = "stabroek_2016") -> dict[str, float]:
    """THE SECOND MECHANISM: a sovereign's oil take, computed from a PUBLISHED formula.

    Cost oil is the lesser of the recoverable cost stack and the ceiling share of revenue; the
    residual is profit oil, split by the agreed share; the royalty is charged on gross revenue
    and is paid out of the contractor's entitlement. Everything here is arithmetic on published
    contract terms -- which is why Guyana, alone in this desk's book, has a revenue function a
    cell can evaluate from the oil price instead of waiting for a budget outturn.
    """
    terms = PSA_TERMS.get(regime, PSA_TERMS["stabroek_2016"])
    ceiling = float(terms["cost_ceiling"])
    gov_share = float(terms["profit_split_government"])
    royalty_rate = float(terms["royalty"])
    rev = max(0.0, float(revenue))
    cost_oil = min(max(0.0, float(recoverable_costs)), ceiling * rev)
    profit_oil = rev - cost_oil
    royalty = royalty_rate * rev
    government = gov_share * profit_oil + royalty
    contractor = cost_oil + (1.0 - gov_share) * profit_oil - royalty
    return {"revenue": rev, "cost_oil": cost_oil, "profit_oil": profit_oil, "royalty": royalty,
            "government": government, "contractor": contractor,
            "government_share_of_revenue": (government / rev) if rev else 0.0}


# ----------------------------------------------- the licence calendar: supply as administration
#: DATED, PUBLISHED, LAWFUL-TO-READ ADMINISTRATIVE ACTS. Rows are (date, act, effect, status).
#: Reading a published licence is not a sanctioned transaction; see `ACCESS_CONSTRAINTS`.
SANCTIONS_ACTS: tuple[tuple[str, str, str, str], ...] = (
    ("2017-08-24", "Executive Order 13808",
     "US financial sanctions: new Venezuelan sovereign and PDVSA debt and dividend flows "
     "prohibited to US persons; production is not yet directly restricted", "PUBLISHED_ACT"),
    ("2019-01-28", "OFAC designates PDVSA under Executive Order 13850",
     "the state oil company is BLOCKED; US refiners stop lifting and the export destination mix "
     "turns toward Asia at a wider discount -- the single largest step in the series",
     "PUBLISHED_ACT"),
    ("2019-08-05", "Executive Order 13884",
     "the property of the Government of Venezuela is blocked, broadening the regime",
     "PUBLISHED_ACT"),
    ("2022-11-26", "Chevron General Licence 41",
     "one company is authorised to resume limited production and export to the United States; a "
     "NAMED, DATED, SINGLE-COUNTERPARTY supply channel reopens", "PUBLISHED_ACT"),
    ("2023-01-24", "the Dragon field authorisation for Trinidad and Tobago",
     "Trinidad is authorised to develop a cross-border Venezuelan gas field -- the one act in "
     "this table that is a TRINIDADIAN gas event and a Venezuelan sanctions event at once",
     "PRESS_REPORTED"),
    ("2023-10-18", "General Licence 44",
     "broad authorisation for oil and gas transactions with Venezuela for six months; the "
     "widest opening of the whole series and the cleanest single event in the pack",
     "PUBLISHED_ACT"),
    ("2024-04-17", "GL 44 is not renewed; General Licence 44A is issued",
     "a wind-down authorisation replaces the broad licence and the regime reverts to "
     "case-by-case specific licences", "PUBLISHED_ACT"),
    ("2025-04-02", "the Dragon authorisation is revoked",
     "the Trinidadian cross-border gas project loses its authorisation, which is a TRINIDADIAN "
     "gas-supply event with a Venezuelan cause", "PRESS_REPORTED"),
    ("2025-07-24", "the Chevron authorisation is restored in amended form",
     "the named-counterparty channel reopens; PRESS_REPORTED and must be confirmed against the "
     "Federal Register or OFAC's own publication before any cell is promoted on it",
     "PRESS_REPORTED"),
)
#: The regime labels `sanctions_state` returns, in force order.
SANCTIONS_REGIMES: tuple[str, ...] = (
    "PRE_SANCTIONS", "FINANCIAL_SANCTIONS", "PDVSA_BLOCKED", "NAMED_COUNTERPARTY",
    "GL44_OPEN", "GL44A_WINDDOWN", "SPECIFIC_LICENCES")


def sanctions_state(day: date) -> str:
    """THE THIRD MECHANISM: which US licensing regime was in force over Venezuelan oil on `day`.

    This is the conditioning variable of AE-G. It is built from dated, published administrative
    acts and nothing else, and it is the reason a Venezuelan production series can be studied at
    all: the supply is a step function of a foreign agency's calendar, and the calendar is public.
    """
    if day < date(2017, 8, 24):
        return "PRE_SANCTIONS"
    if day < date(2019, 1, 28):
        return "FINANCIAL_SANCTIONS"
    if day < date(2022, 11, 26):
        return "PDVSA_BLOCKED"
    if day < date(2023, 10, 18):
        return "NAMED_COUNTERPARTY"
    if day < date(2024, 4, 17):
        return "GL44_OPEN"
    if day < date(2024, 6, 1):
        return "GL44A_WINDDOWN"
    return "SPECIFIC_LICENCES"


def licence_events(status: str = "") -> tuple[tuple[date, str, str], ...]:
    """The dated acts, optionally filtered to one confidence label."""
    return tuple((date.fromisoformat(iso), act, effect)
                 for iso, act, effect, st in SANCTIONS_ACTS if not status or st == status)


def opec_gap(direct: float, secondary: float) -> dict[str, float | str]:
    """THE FOURTH MECHANISM: the disagreement between OPEC's two Venezuelan production series.

    OPEC publishes Venezuelan crude output twice in the same document -- as reported by the
    member (direct communication) and as estimated by the secretariat's independent sources
    (secondary sources) -- and the two do not agree. The GAP is an observable with a sign: a
    positive gap means the member reports more than the independent estimate, which is the state
    a supply claim should be discounted in. Almost nobody carries the gap as a series.
    """
    gap = float(direct) - float(secondary)
    base = float(secondary) if secondary else 0.0
    return {"direct": float(direct), "secondary": float(secondary), "gap": gap,
            "gap_share": (gap / base) if base else 0.0,
            "reading": ("the member reports ABOVE the independent estimate" if gap > 0 else
                        "the member reports BELOW the independent estimate" if gap < 0 else
                        "the two series agree, which is itself rare"),
            "rule": "the SECONDARY series is the one the secretariat uses for compliance, so a "
                    "supply cell is built on secondary sources and the gap is a CONDITIONER"}


def parallel_premium(official: float, parallel: float) -> float:
    """The fractional premium of a parallel rate over the official one.

    The observable for BOTH Trinidad and Venezuela, for opposite reasons: Trinidad rations a
    quasi-peg, so the premium measures the queue; Venezuela runs an official reference beside a
    freely quoted one, so the premium measures the distance between the two. A zero premium in a
    rationed market means the rationing is binding, never that the market is clearing.
    """
    base = float(official)
    if base <= 0:
        return 0.0
    return (float(parallel) - base) / base

# --------------------------------------------------- the territorial-risk series and the gas
#: THE ESSEQUIBO DISPUTE AS A DATED EVENT SERIES. Rows are (date, event, status). This is a
#: POLITICAL RISK series with an oil premium attached, because the territory in dispute contains
#: the waters in which the barrels of `FPSO_SCHEDULE` are produced. Every row is a public act --
#: a referendum, a declaration signed in front of guarantors, an order of the International Court
#: of Justice -- and the ICJ half of it has a PUBLISHED FORWARD CALENDAR, which is the rare
#: thing: a political-risk series with scheduled future dates on it.
ESSEQUIBO_EVENTS: tuple[tuple[str, str, str], ...] = (
    ("2018-03-29", "Guyana files its application at the International Court of Justice",
     "COURT_RECORD"),
    ("2020-12-18", "the ICJ finds it has jurisdiction over the validity of the 1899 award",
     "COURT_RECORD"),
    ("2023-12-01", "the ICJ orders provisional measures against altering the status quo",
     "COURT_RECORD"),
    ("2023-12-03", "VENEZUELA HOLDS A CONSULTATIVE REFERENDUM ON THE ESSEQUIBO -- the single "
                   "largest dated escalation in the series", "PRESS_REPORTED"),
    ("2023-12-14", "the Argyle Declaration is signed in St Vincent before CARICOM, CELAC and "
                   "Brazilian guarantors: both states commit not to use force", "PRESS_REPORTED"),
    ("2024-03-21", "Venezuela legislates a Guayana Esequiba administrative entity",
     "PRESS_REPORTED"),
    ("2025-03-01", "a naval incident is reported near the Stabroek block operations area",
     "PRESS_REPORTED"),
    ("2025-05-01", "the ICJ issues further provisional measures concerning elections in the "
                   "disputed territory", "PRESS_REPORTED"),
)
#: TRINIDAD'S GAS COMPLEX, as facts a cell can condition on rather than as a narrative. Rows are
#: (label, what, status). The DECLINE is the object: it is why the LNG trains run below
#: nameplate, why ammonia and methanol plants have been idled or mothballed, and why a
#: cross-border gas licence with Venezuela became a national economic priority.
TRINIDAD_GAS_FACTS: tuple[tuple[str, str, str], ...] = (
    ("atlantic_lng", "a four-train liquefaction complex at Point Fortin, the first large LNG "
                     "plant in the western hemisphere, restructured into a single unitised "
                     "entity; train utilisation is the cleanest published read on upstream gas",
     "PRESS_REPORTED"),
    ("gas_curtailment", "upstream gas has been insufficient to run the LNG trains and the Point "
                        "Lisas petrochemical estate at full rate for years, so the NGC allocates "
                        "a short molecule between LNG, ammonia, methanol, power and steel -- an "
                        "ADMINISTERED ALLOCATION that is a dated commercial decision",
     "PRESS_REPORTED"),
    ("point_lisas", "one of the world's largest export ammonia complexes plus a large methanol "
                    "cluster, all of it gas-fed; plant idling is announced and dated",
     "PRESS_REPORTED"),
    ("dragon", "a cross-border Venezuelan gas field licensed to Trinidad by the United States in "
               "2023, revoked in 2025 and subsequently renegotiated -- a TRINIDADIAN gas-supply "
               "variable whose driver is an American administrative act", "PRESS_REPORTED"),
    ("manatee", "a wholly Trinidadian field on the same cross-border structure, sanctioned and "
                "under development, and the control for Dragon: same geology, no licence risk",
     "PRESS_REPORTED"),
    ("ministry_bulletin", "the Ministry of Energy publishes gas and crude production BY FIELD "
                          "monthly with the operator named -- among the most granular energy "
                          "statistics published by any state", "OFFICIAL"),
)
#: THE GOLD PLANE. Guyana and Suriname are both real gold producers with a LARGE artisanal and
#: small-scale sector beside the declared mines, and the gap between declared exports and counted
#: production is the measurement problem that makes every gold cell here WEAK by construction.
GOLD_FACTS: tuple[tuple[str, str, str], ...] = (
    ("gy_gold_board", "the Guyana Gold Board is the statutory buyer and publishes declared "
                      "gold declarations; the small-scale sector is the majority of output",
     "OFFICIAL"),
    ("gy_backdam", "the artisanal dredge economy of the interior -- the backdam -- is counted "
                   "only when it declares, and it declares when the differential between the "
                   "Board's price and the informal price says it should", "PRESS_REPORTED"),
    ("sr_mines", "two large-scale mines dominate declared Surinamese production and the "
                 "small-scale sector is comparably large and far less measured",
     "PRESS_REPORTED"),
    ("leakage", "gold walks across borders in this province. An export series that exceeds "
                "counted production, or a neighbour's imports that exceed its neighbour's "
                "exports, is the signature -- and it means a gold SUPPLY claim from this pack "
                "must be labelled WEAK and never promoted on the declared series alone",
     "MEASUREMENT_WARNING"),
)

# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "CFTC Commitments of Traders: WTI, Brent and natural gas",
     "root": "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm",
     "fields": ("managed_money_long", "managed_money_short", "producer_merchant",
                "open_interest"),
     "frequency": "weekly", "snapshot": "Tuesday", "publish_utc": "19:30", "lag_days": 3,
     "licence": "public domain (US government work)", "available": True,
     "why": "the executable legs' own positioning. A Guyanese capacity step or a Venezuelan "
            "licence change into a crowded managed-money short is a different trade from the "
            "same event into a flat book, and this is the only positioning series in the pack "
            "that measures the instrument rather than the economy",
     "pit_warning": "Tuesday snapshot published Friday: a Wednesday licence announcement is "
                    "invisible until the following week's report"},
    {"name": "EIA weekly petroleum status: US crude imports BY COUNTRY OF ORIGIN",
     "root": "https://www.eia.gov/petroleum/supply/weekly/",
     "fields": ("imports_from_venezuela", "imports_from_guyana", "imports_from_mexico",
                "gulf_coast_refinery_runs", "crude_stocks_cushing"),
     "frequency": "weekly", "snapshot": "Friday week-ending", "publish_utc": "15:30",
     "lag_days": 5, "licence": "public domain (US government work)", "available": True,
     "why": "THE PHYSICAL CONFIRMATION. A licence is an authorisation; an import line is a "
            "barrel that actually arrived. The gap between the two is the enforcement question "
            "and it is published weekly by origin",
     "pit_warning": "weekly imports are noisy and revised; a four-week average is the honest "
                    "resolution and anything faster is reading cargo timing as policy"},
    {"name": "Guyana NRF balance, receipts and withdrawals",
     "root": "https://www.finance.gov.gy",
     "fields": ("nrf_opening_balance", "profit_oil_receipts", "royalty_receipts",
                "withdrawals_to_budget", "cargoes_lifted"),
     "frequency": "monthly and quarterly", "snapshot": "month end", "publish_utc": "17:00",
     "lag_days": 20, "licence": "free, public", "available": True,
     "why": "the sovereign's own oil flow, by month, with the cargo count beside it. The "
            "WITHDRAWAL is the fiscal impulse and its ceiling is statutory, so the fiscal "
            "reaction function is legislated rather than discretionary",
     "pit_warning": "receipts are recognised when the cargo is PAID, not when it is lifted, so "
                    "the series lags the physical event by a settlement cycle"},
    {"name": "OPEC MOMR Venezuelan production, both series",
     "root": "https://momr.opec.org/",
     "fields": ("ve_direct_communication", "ve_secondary_sources", "opec_crude_total",
                "opec_spare_capacity"),
     "frequency": "monthly", "snapshot": "the previous month", "publish_utc": "11:00",
     "lag_days": 14, "licence": "free, public (OPEC terms)", "available": True,
     "why": "the only monthly production series for Venezuela that is published at all, and it "
            "is published TWICE with two different numbers -- which makes the disagreement "
            "itself an observable (`opec_gap`)",
     "pit_warning": "both series are revised, and the DIRECT series is revised more; a study "
                    "that uses the latest vintage is using information nobody had at the time"},
    {"name": "IMF Article IV and programme documents for Guyana, Trinidad and Suriname",
     "root": "https://www.imf.org/en/Publications/SPROLLs/Article-IV-Staff-Reports",
     "fields": ("fiscal_balance", "reserves_months_of_imports", "external_debt",
                "programme_review_dates"),
     "frequency": "annual and semi-annual", "snapshot": "the review period",
     "publish_utc": "15:00", "lag_days": 45, "licence": "free, public", "available": True,
     "why": "for Suriname this is the MACRO CLOCK: the reserve-money target and the published "
            "review calendar are what the post-default regime actually runs on",
     "pit_warning": "an Article IV is negotiated with the authorities and published weeks after "
                    "the mission; it is a regime description, never a weekly signal"},
    {"name": "A positioning series for GYD, TTD, VES or SRD",
     "root": "", "fields": (), "frequency": "n/a", "snapshot": "", "publish_utc": "",
     "lag_days": 0, "licence": "", "available": False,
     "why": "DECLARED ABSENT. No futures contract, no COT report and no offshore forward market "
            "with published volumes exists for any of the four currencies of this province",
     "pit_warning": "NO SUCH SERIES DOES NOT EXIST ANYWHERE. It is named here so that a future "
                    "session does not look for it, and so that no cell is ever built on a "
                    "BRL or MXN positioning leg pretending to be a local one"},
)

# --------------------------------------------------------------------------- terminology
#: FOUR LANGUAGE GROUNDS AND ONE HONEST ADMISSION. English is the OFFICIAL language of Guyana and
#: of Trinidad and Tobago, so an English query on those two grounds reads the ground itself --
#: which is true here and false on most of this desk's packs, and saying so is more useful than
#: pretending otherwise. The non-English half is real and is carried in full: SPANISH for
#: Venezuela, DUTCH and SRANAN TONGO for Suriname, and GUYANESE CREOLESE, which is the language
#: the interior gold economy and the most-read columns of the Guyanese press are actually
#: written in. A crawl that reads only the Georgetown and Port of Spain English press gets three
#: quarters of the official plane and almost none of the physical one.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "AE-A": ("floating production storage and offloading", "FPSO", "Stabroek block",
             "Liza Destiny", "Liza Unity", "Prosperity FPSO", "ONE GUYANA FPSO", "Errea Wittu",
             "Jaguar FPSO", "first oil", "final investment decision", "nameplate capacity",
             "debottlenecking", "producción de petróleo", "petróleo crudo", "barriles por día",
             "development plan approval", "olieproductie"),
    "AE-B": ("Natural Resource Fund", "NRF Act", "profit oil", "cost oil", "cost recovery "
             "ceiling", "royalty", "production sharing agreement", "lifting entitlement",
             "cargo lifting", "Appropriation Act", "withdrawal rule", "Ministry of Finance "
             "Guyana", "oil revenue", "sovereign wealth fund", "petroleum agreement",
             "empresa mixta", "begroting"),
    "AE-C": ("Guyana Gold Board", "gold declaration", "backdam", "porknocker", "pork-knocker",
             "dredge", "bauxite", "calcined bauxite", "Linden", "Berbice", "GuySuCo",
             "Demerara sugar", "sugar estate", "Caricom quota", "gowtu", "wuk", "mattie",
             "dem boys", "goudsector"),
    "AE-D": ("Atlantic LNG", "Point Fortin", "liquefaction train", "train utilisation",
             "gas curtailment", "National Gas Company", "NGC", "upstream gas", "Dragon field",
             "Manatee field", "cross-border gas", "gas supply agreement", "bpTT", "aardgas",
             "monthly energy bulletin", "field-level production"),
    "AE-E": ("Point Lisas", "ammonia", "anhydrous ammonia", "methanol", "urea", "petrochemical "
             "estate", "plant turnaround", "mothballed plant", "nitrogen fertiliser",
             "Tampa CFR ammonia", "gas allocation", "netback", "fertiliser cost",
             "acreage decision", "planting intentions", "kunstmest"),
    "AE-F": ("Central Bank of Trinidad and Tobago", "authorised dealer", "foreign exchange "
             "allocation", "FX rationing", "repo rate", "TT dollar", "quasi-peg",
             "Heritage and Stabilisation Fund", "budget statement", "fiscal year 1 October",
             "oil price assumption", "wisselkoers", "parallel premium", "queue for foreign "
             "exchange"),
    "AE-G": ("Office of Foreign Assets Control", "general licence", "specific licence",
             "General Licence 44", "wind-down authorisation", "Federal Register", "sanción",
             "licencia", "PDVSA", "empresa mixta petrolera", "Faja del Orinoco",
             "crudo pesado", "Merey", "diluente", "mejorador", "exportación de crudo",
             "buque tanquero", "transferencia de buque a buque"),
    "AE-H": ("OPEC Monthly Oil Market Report", "direct communication", "secondary sources",
             "production estimate gap", "OPEC quota", "compliance", "cesta venezolana",
             "producción de crudo", "informe mensual", "Ministerio de Petróleo",
             "rig count", "declino de producción", "capacidad instalada"),
    "AE-I": ("hiperinflación", "reconversión monetaria", "bolívar fuerte", "bolívar soberano",
             "bolívar digital", "dólar paralelo", "tasa oficial BCV", "dolarización",
             "Banco Central de Venezuela", "Gaceta Oficial", "control de cambio",
             "Observatorio Venezolano de Finanzas", "índice de precios", "remesas",
             "encaje legal"),
    "AE-J": ("Block 58", "GranMorgu", "Staatsolie", "Suriname offshore", "appraisal well",
             "final investment decision Suriname", "first oil 2028", "Sapakara", "Krabdagu",
             "olie", "boorplatform", "productiedeling", "De Nationale Assemblée",
             "Centrale Bank van Suriname", "jaarverslag"),
    "AE-K": ("sovereign default", "debt restructuring", "value recovery instrument",
             "oil-linked payment", "Paris Club", "IMF programme review", "reserve money target",
             "staatsschuld", "herstructurering", "Rosebel", "Merian", "goudmijn",
             "kleinschalige goudwinning", "porknocker", "kondre", "wroko", "sranan"),
    "AE-L": ("Essequibo", "Esequibo", "Guayana Esequiba", "International Court of Justice",
             "provisional measures", "1899 arbitral award", "Argyle Declaration", "referendum "
             "consultivo", "CARICOM", "CELAC", "territorial dispute", "border controversy",
             "naval incident", "reclamación", "libisma"),
    "AE-M": ("ship-to-ship transfer", "Aframax", "Suezmax", "bunkering", "anchorage",
             "Demerara anchorage", "Berbice river", "Port of Spain", "Chaguaramas",
             "José terminal", "Amuay", "tanker tracking", "freight rate", "lightering",
             "draft restriction", "watra", "transbordo", "flete"),
}
#: NATIVE-LANGUAGE MARKERS, by ground. A test asserts that every marker in each tuple actually
#: appears somewhere in `TERMINOLOGY`, so the vocabulary cannot quietly become an English
#: glossary of four countries while claiming four languages.
SPANISH_MARKERS: tuple[str, ...] = (
    "producción", "petróleo", "sanción", "licencia", "Gaceta Oficial", "hiperinflación",
    "reconversión monetaria", "dólar paralelo", "Faja del Orinoco", "cesta venezolana",
    "Esequibo", "empresa mixta", "exportación de crudo", "índice de precios", "reclamación",
    "buque tanquero", "crudo pesado", "flete")
DUTCH_MARKERS: tuple[str, ...] = (
    "aardgas", "olieproductie", "wisselkoers", "begroting", "goudsector", "staatsschuld",
    "herstructurering", "jaarverslag", "goudmijn", "boorplatform", "productiedeling",
    "Centrale Bank van Suriname", "De Nationale Assemblée", "kunstmest", "kleinschalige")
SRANAN_MARKERS: tuple[str, ...] = ("gowtu", "kondre", "wroko", "sranan", "watra", "libisma")
CREOLESE_MARKERS: tuple[str, ...] = (
    "backdam", "porknocker", "pork-knocker", "dem boys", "mattie", "wuk")
#: The Spanish diacritics that tell a Venezuelan release from an English article about one.
_SPANISH_DIACRITICS = "áéíóúüñÁÉÍÓÚÜÑ¿¡"
#: The Dutch and Sranan orthographic signatures. Dutch shares Latin script with English, so the
#: test is a VOCABULARY test, exactly as it is for Spanish in the `pe` pack.
_DUTCH_DIGRAPHS = ("ij", "oe", "aa", "uu", "sch")


def has_spanish_diacritic(text: str) -> bool:
    """True when the text carries a Spanish diacritic. An English article ABOUT a Venezuelan
    release has none, which is what makes this a usable native-language test on Latin script."""
    return any(ch in _SPANISH_DIACRITICS for ch in str(text))


def has_dutch(text: str) -> bool:
    """True when the text carries a declared Dutch term. Dutch and English share the Latin
    alphabet, so this is a VOCABULARY test rather than a codepoint one -- the same shape the
    `pe` pack uses for Spanish and for exactly the same reason."""
    return any(m.lower() in str(text).lower() for m in DUTCH_MARKERS)


def has_sranan(text: str) -> bool:
    """True when the text carries a declared Sranan Tongo term. Sranan is the lingua franca of
    Suriname: the language of the market, the mine camp and half the radio, and it is not what
    the ministries publish in -- which is exactly why a Dutch-only crawl reads the state and
    misses the economy."""
    return any(m.lower() in str(text).lower() for m in SRANAN_MARKERS)


def has_creolese(text: str) -> bool:
    """True when the text carries a declared Guyanese Creolese term. The backdam gold economy
    and the most-read columns of the Guyanese press are written in it, and standard-English
    search terms do not reach either."""
    return any(m.lower() in str(text).lower() for m in CREOLESE_MARKERS)


def _flat_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> set[str]:
    rows = TERMINOLOGY if terminology is None else terminology
    return {t for terms in rows.values() for t in terms}


def spanish_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    """Every declared Spanish marker actually present in the terminology table."""
    flat = _flat_terms(terminology)
    return [m for m in SPANISH_MARKERS if any(m in t for t in flat)]


def dutch_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    flat = _flat_terms(terminology)
    return [m for m in DUTCH_MARKERS if any(m in t for t in flat)]


def sranan_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    flat = _flat_terms(terminology)
    return [m for m in SRANAN_MARKERS if any(m in t for t in flat)]


def creolese_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    flat = _flat_terms(terminology)
    return [m for m in CREOLESE_MARKERS if any(m in t for t in flat)]


def accented_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    """Every term carrying a Spanish diacritic."""
    return sorted(t for t in _flat_terms(terminology) if has_spanish_diacritic(t))


def term_count(terminology: Mapping[str, Iterable[str]] | None = None) -> int:
    return len(_flat_terms(terminology))


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


def _seq(values: Iterable[Any]) -> tuple[str, ...]:
    return tuple(str(v) for v in values)


def source_class(sid: str, label: str, *, layer: str, roots: Iterable[str],
                 queries: Iterable[str], languages: Iterable[str], access_label: str,
                 credibility: str, predictive_state: str, licence: str,
                 machine_use_allowed: bool = True, notes: str = "") -> dict[str, Any]:
    """One class of source with the roots a crawler starts from and its three INDEPENDENT
    labels. `queries` are native-language terms, never translations. `machine_use_allowed=True`
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
    """A layer this province has nothing in, declared BY NAME with the reason (L1.28a)."""
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
        "ae_gy_official", "Guyana: the Bank of Guyana, the Bureau of Statistics, the Ministry of "
                          "Natural Resources, the Ministry of Finance (the NRF reports) and the "
                          "Guyana Oil and Gas regulator",
        layer="official",
        roots=("https://www.bankofguyana.org.gy", "https://statisticsguyana.gov.gy",
               "https://nre.gov.gy", "https://finance.gov.gy", "https://ogrg.gov.gy"),
        queries=("Natural Resource Fund monthly report receipts",
                 "petroleum production monthly Guyana Ministry of Natural Resources",
                 "Bank of Guyana statistical bulletin market exchange rates",
                 "Bureau of Statistics Guyana oil and non-oil GDP",
                 "cargo lifting entitlement Guyana profit oil",
                 "production sharing agreement Stabroek cost recovery",
                 "Guyana Gold Board gold declaration backdam dredge",
                 "budget speech Appropriation Act NRF withdrawal ceiling"),
        languages=("en", "gyn"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE NRF REPORT IS THE PACK'S BEST OFFICIAL ROW: a sovereign's oil receipt, by "
              "month, with the cargoes named, published by the finance ministry of a country "
              "whose fiscal formula is itself public. There is no equivalent in any sibling pack"),
    source_class(
        "ae_tt_official", "Trinidad and Tobago: the Central Bank, the Central Statistical Office "
                          "and the Ministry of Energy's monthly bulletin with FIELD-LEVEL gas",
        layer="official",
        roots=("https://www.central-bank.org.tt", "https://cso.gov.tt",
               "https://www.energy.gov.tt", "https://www.finance.gov.tt"),
        queries=("Ministry of Energy monthly bulletin natural gas production by field",
                 "Atlantic LNG train utilisation Trinidad",
                 "Central Bank of Trinidad and Tobago monetary policy announcement repo rate",
                 "foreign exchange allocation authorised dealers Trinidad",
                 "Heritage and Stabilisation Fund quarterly report",
                 "budget statement fiscal year oil price assumption Trinidad",
                 "ammonia methanol production Point Lisas monthly"),
        languages=("en",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="FIELD-LEVEL GAS PRODUCTION WITH THE OPERATOR NAMED, MONTHLY. Most states publish "
              "a national total; Trinidad publishes the field, which turns 'the gas is "
              "declining' from an opinion into a counted series with a decline rate per asset"),
    source_class(
        "ae_ve_official", "Venezuela: the Banco Central, the statistics institute, the state oil "
                          "company's own publications and the Gaceta Oficial -- ALL OF THEM "
                          "INTERMITTENT, and the intermittency is the finding",
        layer="official",
        roots=("http://www.bcv.org.ve", "http://www.ine.gov.ve", "http://www.pdvsa.com",
               "http://spgoin.imprentanacional.gob.ve"),
        queries=("producción de crudo PDVSA informe",
                 "Gaceta Oficial decreto petrolero empresa mixta",
                 "Banco Central de Venezuela tipo de cambio oficial",
                 "índice nacional de precios al consumidor BCV",
                 "reconversión monetaria bolívar digital",
                 "exportación de crudo Faja del Orinoco mejorador",
                 "reservas internacionales Venezuela publicación"),
        languages=("es",), access_label="PUBLIC", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="REGISTERED WITH A LOW CREDIBILITY LABEL RATHER THAN DROPPED. The publication "
              "record is broken -- see `NO_LAWFUL_GROUND` for the jurisdiction-and-layer rows "
              "and the LAWFUL SUBSTITUTES -- but a series that resumes is a dated event in "
              "itself, and a desk that stops looking never sees the resumption"),
    source_class(
        "ae_sr_official", "Suriname: the Centrale Bank van Suriname, the Algemeen Bureau voor de "
                          "Statistiek and the government portal",
        layer="official",
        roots=("https://www.cbvs.sr", "https://statistics-suriname.org", "https://gov.sr"),
        queries=("Centrale Bank van Suriname wisselkoers jaarverslag",
                 "olieproductie Staatsolie kwartaalcijfers",
                 "staatsschuld herstructurering obligatie Suriname",
                 "goudsector export kleinschalige goudwinning",
                 "begroting De Nationale Assemblée financiële nota",
                 "monetaire basis reservegeld doelstelling IMF"),
        languages=("nl", "srn", "en"), access_label="OPEN_DATA", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="DUTCH IS THE LANGUAGE OF THE SURINAMESE STATE and Sranan Tongo is the language of "
              "the economy the state is describing; an English-only crawl of Suriname reaches "
              "neither and finds the IMF's summary of both"),
    source_class(
        "ae_us_official", "The United States as the province's LICENSING AUTHORITY: OFAC's "
                          "published licences and FAQs, the Federal Register and its API, and "
                          "the EIA's import-by-origin and petroleum statistics",
        layer="official",
        roots=("https://ofac.treasury.gov/sanctions-programs-and-country-information",
               "https://www.federalregister.gov/api/v1/documents.json",
               "https://www.eia.gov/petroleum/supply/weekly/",
               "https://www.eia.gov/opendata/"),
        queries=("OFAC Venezuela general license 44 wind-down",
                 "Federal Register Venezuela sanctions notice",
                 "OFAC FAQ Venezuela oil sector authorization",
                 "EIA US crude oil imports by country of origin weekly",
                 "EIA short-term energy outlook Guyana production",
                 "specific license Chevron Venezuela authorization"),
        languages=("en",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="public domain (US government work)",
        notes="THE SUPPLY SWITCH IS A FOREIGN ADMINISTRATIVE DOCUMENT and it is published with a "
              "date, a number and a machine-readable API. Reading a published licence is lawful; "
              "see `ACCESS_CONSTRAINTS`, where the distinction between reading an act and "
              "transacting with a sanctioned party is stated in full"),
    # ---- institutional
    source_class(
        "ae_opec_iea", "OPEC's Monthly Oil Market Report -- carrying the TWO Venezuelan series -- "
                       "and the IEA's public releases",
        layer="institutional",
        roots=("https://momr.opec.org/", "https://www.opec.org/opec_web/en/publications/338.htm",
               "https://www.iea.org/news"),
        queries=("OPEC monthly oil market report Venezuela direct communication",
                 "OPEC secondary sources crude production table",
                 "informe mensual OPEP producción venezolana",
                 "OPEC crude oil production by country monthly",
                 "IEA oil market report non-OPEC supply Guyana"),
        languages=("en", "es"), access_label="PUBLIC_WITH_TERMS", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free to read, redistribution restricted",
        notes="THE TWO-SERIES DISAGREEMENT IS THE ASSET. No other producer on this desk is "
              "published twice in the same document with two different numbers by the same "
              "institution, and the gap between them is `opec_gap()`"),
    source_class(
        "ae_multilateral", "The IMF, the World Bank, the Inter-American Development Bank and UN "
                           "Comtrade -- the mirror-trade ground that substitutes for a "
                           "statistics office that stopped publishing",
        layer="institutional",
        roots=("https://www.imf.org/en/Countries", "https://comtradeplus.un.org/",
               "https://data.worldbank.org", "https://www.iadb.org/en/countries"),
        queries=("IMF Article IV Guyana staff report oil",
                 "IMF programme review Suriname reserve money",
                 "UN Comtrade Venezuela crude oil exports mirror",
                 "World Bank Guyana economic update non-oil growth",
                 "IDB Caribbean energy report Trinidad gas"),
        languages=("en", "es", "nl"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="MIRROR DATA IS THE LAWFUL SUBSTITUTE for the Venezuelan trade series: what "
              "Venezuela does not publish, its counterparties do, and Comtrade holds both sides"),
    source_class(
        "ae_courts", "The International Court of Justice docket in Guyana v. Venezuela and the "
                     "published United States court dockets in the PDV Holding and Citgo "
                     "proceedings",
        layer="institutional",
        roots=("https://www.icj-cij.org/case/171",
               "https://www.courtlistener.com/",
               "https://ecf.ded.uscourts.gov/"),
        queries=("ICJ Guyana Venezuela provisional measures order",
                 "Arbitral Award of 3 October 1899 case pleadings",
                 "PDV Holding Citgo sale process docket order",
                 "alter ego judgment Venezuela attachment Delaware",
                 "reclamación del Esequibo Corte Internacional de Justicia"),
        languages=("en", "es", "fr"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public court record",
        notes="A COURT CALENDAR IS A FORWARD-DATED RISK SERIES. Memorials, hearings and orders "
              "are scheduled in advance and announced, which makes this the only political-risk "
              "ground in the pack with KNOWN FUTURE DATES on it"),
    source_class(
        "ae_industry", "Industry bodies and the state companies' own disclosures: the Energy "
                       "Chamber of Trinidad and Tobago, the Guyana energy chamber, Staatsolie "
                       "and the Trinidad and Tobago Stock Exchange",
        layer="institutional",
        roots=("https://energynow.tt", "https://www.staatsolie.com",
               "https://www.stockex.co.tt", "https://gceci.org"),
        queries=("Energy Chamber Trinidad gas curtailment statement",
                 "Staatsolie jaarverslag Block 58 GranMorgu",
                 "Trinidad and Tobago Stock Exchange market report",
                 "local content Guyana oil and gas suppliers register",
                 "energy conference Trinidad presentation gas supply"),
        languages=("en", "nl"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="Staatsolie publishes an annual report in Dutch and English and it is the only "
              "PRIMARY disclosure on the Surinamese side of Block 58 that is not the operator's"),
    # ---- academic
    source_class(
        "ae_academic", "The scholarly ground: OpenAlex and CORE, the University of the West "
                       "Indies at St Augustine, the University of Guyana and the Anton de Kom "
                       "University of Suriname",
        layer="academic",
        roots=("https://api.openalex.org/works", "https://core.ac.uk/search",
               "https://sta.uwi.edu", "https://www.uog.edu.gy", "https://www.uvs.edu"),
        queries=("resource curse Guyana oil revenue management research",
                 "Trinidad natural gas depletion economics paper",
                 "Dutch disease small open economy oil windfall Caribbean",
                 "hiperinflación venezolana dolarización estudio",
                 "petroleum fiscal regime production sharing Guyana analysis",
                 "kleinschalige goudwinning kwik Suriname onderzoek"),
        languages=("en", "es", "nl"), access_label="OPEN_DATA", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="mostly open access",
        notes="THE CARIBBEAN ECONOMICS LITERATURE IS SMALL AND CONCENTRATED at UWI, and it is "
              "where the gas-depletion and resource-curse arguments this pack tests were made "
              "first -- usually a decade before the trade press noticed them"),
    source_class(
        "ae_thinktank", "Policy institutes that publish dated, sourced work on this province: "
                        "the Venezuelan Finance Observatory, the Inter-American Dialogue, "
                        "Chatham House and the Caribbean policy research institutes",
        layer="academic",
        roots=("https://observatoriodefinanzas.com", "https://www.thedialogue.org",
               "https://www.chathamhouse.org/regions/americas"),
        queries=("Observatorio Venezolano de Finanzas índice de precios mensual",
                 "Venezuela oil production estimate independent analysis",
                 "Caribbean energy transition policy brief Trinidad",
                 "Guyana oil governance civil society analysis"),
        languages=("es", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE VENEZUELAN FINANCE OBSERVATORY IS THE NAMED LAWFUL SUBSTITUTE for the "
              "inflation series the statistics office stopped publishing; it computes a monthly "
              "CPI from its own basket and publishes the method"),
    # ---- practitioner
    source_class(
        "ae_energy_practitioner", "The specialist energy trade press and the practitioner blogs "
                                  "that actually track this basin: OilNOW, Energy Now TT, the "
                                  "Guyana Standard's energy desk and the independent analysts "
                                  "who publish their tanker counts",
        layer="practitioner",
        roots=("https://oilnow.gy", "https://energynow.tt", "https://www.guyanastandard.com",
               "https://www.offshore-energy.biz"),
        queries=("Yellowtail first oil ahead of schedule ExxonMobil Guyana",
                 "FPSO arrival Guyana commissioning schedule",
                 "gas curtailment Point Lisas plant shutdown announcement",
                 "Dragon gas licence Trinidad Venezuela negotiation update",
                 "GranMorgu Suriname construction milestone",
                 "tanker loading Guyana cargo schedule monthly",
                 "análisis del sector petrolero venezolano consultora",
                 "olie- en gassector Suriname analyse boorplatform"),
        languages=("en",), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free to read",
        notes="OilNOW and its siblings publish FPSO commissioning detail weeks before it reaches "
              "any statistical series, which is precisely the lead this pack's ramp domain needs"),
    source_class(
        "ae_price_reporting", "The price reporting agencies that assess ammonia, methanol, LNG "
                              "and the crude differentials this pack cannot otherwise see",
        layer="practitioner",
        roots=("https://www.argusmedia.com", "https://www.fastmarkets.com",
               "https://www.icis.com"),
        queries=("Tampa ammonia contract settlement monthly",
                 "Caribbean ammonia FOB assessment",
                 "methanol contract price posted Caribbean",
                 "Atlantic LNG spot assessment netback"),
        languages=("en",), access_label="LICENSED", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="subscription; terms forbid machine extraction",
        machine_use_allowed=True,
        notes="REGISTERED AND NEVER SCRAPED. The ammonia and LNG assessments are the exact "
              "series the fertiliser and gas chains would be cleanest on, and their terms forbid "
              "machine extraction -- so those legs are UNMEASURED by name, the cells are built "
              "on the PHYSICAL volume series instead, and the absence is carried rather than "
              "worked around. Omitting the row would lose the knowledge that the ground exists"),
    # ---- retail_ecology
    source_class(
        "ae_ve_retail", "The Venezuelan parallel-rate ecology: the widely followed dollar "
                        "trackers, the cambista channels and the price-in-dollars culture that "
                        "replaced a currency",
        layer="retail_ecology",
        roots=("https://monitordolarvenezuela.com", "https://www.bancaynegocios.com",
               "https://dolartoday.com"),
        queries=("dólar paralelo hoy precio",
                 "tasa BCV vs paralelo brecha",
                 "precios en dólares Venezuela comercio",
                 "remesas a Venezuela tasa de cambio",
                 "cambista tasa del día Caracas"),
        languages=("es",), access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="free, public",
        notes="KEPT AT LOW WEIGHT, NEVER DROPPED. These references are self-published, "
              "unaudited and have been politically contested for a decade -- and they are also "
              "the price at which Venezuelans actually transact. A claim that looks unreliable "
              "is still a dated, testable claim, and the ONLY high-frequency Venezuelan price "
              "series that exists at all lives here"),
    source_class(
        "ae_anglo_retail", "The Guyanese and Trinidadian retail ecology: the FX-queue "
                           "discussion, the remittance and diaspora boards, and the local "
                           "investment forums",
        layer="retail_ecology",
        roots=("https://www.facebook.com/groups", "https://www.reddit.com/r/TrinidadandTobago",
               "https://www.guyanachronicle.com"),
        queries=("foreign exchange shortage Trinidad bank limit US dollar",
                 "wire transfer US dollars Trinidad waiting",
                 "sending money to Guyana rate remittance",
                 "dem boys seh column Guyana",
                 "backdam gold price dredge buying"),
        languages=("en", "gyn"), access_label="USER_SUBMITTED", credibility="UNRELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="platform terms; registered, not archived",
        notes="THE FX QUEUE IS REPORTED HERE BEFORE IT IS REPORTED ANYWHERE. A rationed currency "
              "produces no price signal, so the retail complaint IS the measurement: when "
              "cardholders report limits and importers report waiting weeks, the ration is "
              "binding. Low weight, kept, never treated as authoritative"),
    # ---- app_ecosystem
    source_class(
        "ae_data_apis", "The machine-readable endpoints this province is actually reachable "
                        "through: the Federal Register API, the EIA open-data API, UN Comtrade "
                        "and the World Bank indicators API",
        layer="app_ecosystem",
        roots=("https://www.federalregister.gov/api/v1/documents.json",
               "https://api.eia.gov/v2/", "https://comtradeapi.un.org/",
               "https://api.worldbank.org/v2/country/GUY"),
        queries=("federal register api search venezuela sanctions documents",
                 "EIA API petroleum imports series id",
                 "Comtrade API commodity 2709 crude petroleum reporter",
                 "World Bank API Guyana GDP indicator",
                 "open data portal Trinidad and Tobago dataset"),
        languages=("en",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public APIs",
        notes="THE FEDERAL REGISTER API IS THE PACK'S BEST COLLECTOR TARGET: every sanctions "
              "notice is a dated, typed, queryable document with a publication timestamp, which "
              "turns the Venezuelan supply switch into a machine-readable event series"),
    source_class(
        "ae_local_apps", "The apps and payment rails locals use: the Guyanese mobile-money "
                         "services, the Trinidadian bank apps and their FX limits, and the "
                         "rate-tracking apps of the Venezuelan diaspora",
        layer="app_ecosystem",
        roots=("https://www.mmg.gy", "https://www.republictt.com", "https://www.gtbank.com.gy"),
        queries=("mobile money Guyana MMG transaction limit",
                 "Trinidad bank credit card US dollar limit online",
                 "aplicación tasa de cambio Venezuela actualizada",
                 "online banking foreign currency account Guyana"),
        languages=("en", "es", "gyn"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="public product pages",
        notes="A BANK'S PUBLISHED FX CARD LIMIT IS A RATIONING INSTRUMENT IN DISGUISE. When "
              "Trinidadian banks change the monthly US-dollar limit on a card, that is the "
              "allocation regime moving, announced on a product page rather than in a bulletin"),
    # ---- media
    source_class(
        "ae_gy_media", "The Guyanese press: Stabroek News, Kaieteur News, Demerara Waves, the "
                       "News Room and the Guyana Chronicle",
        layer="media",
        roots=("https://www.stabroeknews.com", "https://www.kaieteurnewsonline.com",
               "https://demerarawaves.com", "https://newsroom.gy"),
        queries=("Stabroek News oil production monthly figures",
                 "Kaieteur News production sharing agreement cost oil audit",
                 "dem boys seh oil money",
                 "Demerara Waves NRF withdrawal parliament",
                 "backdam dredge gold declaration news",
                 "Essequibo border controversy statement Georgetown"),
        languages=("en", "gyn"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free to read; archives partial",
        notes="KAIETEUR NEWS HAS RUN THE MOST PERSISTENT PUBLIC AUDIT OF THE COST-OIL STACK of "
              "any outlet in the province, in a mix of standard English and Creolese. Its "
              "adversarial framing is a known bias and its NUMBERS are frequently first"),
    source_class(
        "ae_tt_media", "The Trinidadian press: the Trinidad Guardian, Newsday, the Trinidad "
                       "Express and the business weeklies",
        layer="media",
        roots=("https://www.guardian.co.tt", "https://newsday.co.tt",
               "https://trinidadexpress.com", "https://tt.loopnews.com"),
        queries=("gas curtailment Point Lisas plant closure Newsday",
                 "Atlantic LNG train shutdown Trinidad Guardian",
                 "foreign exchange distribution authorised dealers central bank",
                 "budget fiscal year oil price assumption Trinidad Express",
                 "Dragon gas field licence news Trinidad"),
        languages=("en",), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free to read",
        notes="A PLANT IDLING AT POINT LISAS IS ANNOUNCED IN THE NEWSPAPER, not in a bulletin, "
              "and it is a dated physical-supply event for the ammonia chain"),
    source_class(
        "ae_ve_sr_media", "The Venezuelan and Surinamese press: Efecto Cocuyo, Banca y Negocios "
                          "and Prodavinci in Spanish; Starnieuws, de Ware Tijd and Dagblad "
                          "Suriname in Dutch and Sranan Tongo",
        layer="media",
        roots=("https://efectococuyo.com", "https://www.bancaynegocios.com",
               "https://prodavinci.com", "https://www.starnieuws.com", "https://dwtonline.com"),
        queries=("producción petrolera venezolana cifras mensuales",
                 "exportación de crudo buque tanquero transbordo",
                 "hiperinflación índice de precios canasta",
                 "Staatsolie olieproductie nieuws Starnieuws",
                 "wisselkoers SRD koers van de dag",
                 "gowtu prijs kondre wroko goudsector"),
        languages=("es", "nl", "srn"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free to read",
        notes="EFECTO COCUYO AND PRODAVINCI ARE THE SURVIVING INDEPENDENT VENEZUELAN OUTLETS and "
              "they carry the tanker and production reporting the state stopped publishing; "
              "Starnieuws is the fastest Surinamese wire and publishes in Dutch with Sranan "
              "headlines, which is why both languages are declared on this row"),
    # ---- archive
    source_class(
        "ae_gazettes", "The four official gazettes and the web archive that preserves what they "
                       "overwrite: the Gaceta Oficial de Venezuela, the Guyana Official Gazette, "
                       "the Trinidad and Tobago Gazette and the Surinamese Staatsblad",
        layer="archive",
        roots=("http://spgoin.imprentanacional.gob.ve", "https://officialgazette.gov.gy",
               "http://www.ttparliament.org", "https://web.archive.org/web/*/nre.gov.gy*"),
        queries=("Gaceta Oficial decreto empresa mixta petrolera número",
                 "Official Gazette Guyana public holidays order",
                 "Staatsblad van de Republiek Suriname resolutie",
                 "web archive ministry of energy monthly bulletin Trinidad",
                 "archived NRF report quarterly Guyana"),
        languages=("es", "en", "nl"), access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE MINISTRY PAGES IN THIS PROVINCE ARE OVERWRITTEN IN PLACE. The Trinidadian "
              "bulletin and the Guyanese NRF report publish the current file over the same link "
              "and keep no vintage, so the POINT-IN-TIME history of both exists only in the web "
              "archive -- and a cell compiled on an un-archived month is UNMEASURED, not assumed"),
    source_class(
        "ae_caribbean_archive", "The Digital Library of the Caribbean and the national library "
                                "and university collections that hold the pre-oil record",
        layer="archive",
        roots=("https://dloc.com", "https://uwispace.sta.uwi.edu",
               "https://www.nationallibrary.gov.gy"),
        queries=("Digital Library of the Caribbean Guyana annual report",
                 "bauxite industry Guyana historical record",
                 "sugar industry Demerara archive",
                 "Trinidad oil industry history collection"),
        languages=("en", "nl", "es"), access_label="PUBLIC_ARCHIVE", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public archive",
        notes="THE PRE-OIL BASELINE. Guyana's economy before December 2019 is the counterfactual "
              "every oil-boom claim in this pack is measured against, and its statistical record "
              "is in these collections rather than on a live ministry page"),
    # ---- physical_economy
    source_class(
        "ae_tanker_plane", "The physical crude plane: port and maritime authorities, the "
                           "published anchorage and terminal notices, and the tanker-movement "
                           "reporting the press carries",
        layer="physical_economy",
        roots=("https://www.marad.gov.gy", "https://www.patnt.com",
               "https://www.reuters.com/business/energy/", "https://www.eia.gov/petroleum/"),
        queries=("ship to ship transfer Venezuelan crude tanker report",
                 "Guyana crude cargo loading schedule anchorage",
                 "Point Fortin LNG cargo departure",
                 "transbordo de crudo buque a buque, exportación venezolana",
                 "port authority Trinidad vessel arrival notice",
                 "lightering Demerara anchorage draft restriction"),
        languages=("en", "es"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free to read; vessel data via public reporting",
        notes="TANKER-TRACKING PRESS REPORTS ARE THE NAMED LAWFUL SUBSTITUTE for the Venezuelan "
              "export series nobody publishes. The desk reads the REPORTS, which are public; it "
              "does not acquire a commercial vessel feed and it does not need one to date an "
              "event"),
    source_class(
        "ae_gas_physical", "The physical gas and petrochemical plane: the Trinidadian ministry "
                           "bulletin by field, the LNG train status, and the plant turnaround "
                           "and idling announcements",
        layer="physical_economy",
        roots=("https://www.energy.gov.tt/statistics", "https://www.natgas.co.tt",
               "https://energynow.tt"),
        queries=("natural gas production by field monthly Trinidad statistics",
                 "LNG train outage maintenance Point Fortin",
                 "ammonia plant turnaround schedule Point Lisas",
                 "methanol plant shutdown announcement Trinidad",
                 "NGC gas sales agreement volume allocation"),
        languages=("en",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="A TURNAROUND IS SCHEDULED MONTHS AHEAD AND ANNOUNCED, which makes plant downtime "
              "in this province a FORWARD-DATED physical supply series rather than a surprise"),
    source_class(
        "ae_gold_physical", "The physical gold plane: the Guyana Gold Board declarations, the "
                            "Surinamese export record and the MIRROR data that catches what "
                            "neither declares",
        layer="physical_economy",
        roots=("https://ggmc.gov.gy", "https://statistics-suriname.org",
               "https://comtradeplus.un.org/"),
        queries=("Guyana Gold Board declaration ounces monthly",
                 "gold export Suriname statistics goudsector",
                 "Comtrade gold imports from Guyana mirror",
                 "small scale mining mercury dredge licence",
                 "gowtu wroko kleinschalige goudwinning"),
        languages=("en", "nl", "srn", "gyn"), access_label="OPEN_DATA", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE MIRROR COMPARISON IS THE MEASUREMENT. Declared production and declared "
              "exports do not reconcile in either country, and the counterparties' import "
              "records are the only lawful way to see the difference"),
    # ---- source_graph
    source_class(
        "ae_citation_graph", "What the other nine layers cite: the attribution phrases that "
                             "reveal which number a story came from, and therefore which source "
                             "leads and which follows",
        layer="source_graph",
        roots=("https://news.google.com/search", "https://efectococuyo.com",
               "https://oilnow.gy", "https://www.starnieuws.com"),
        queries=("according to the OPEC monthly report Venezuela production",
                 "según fuentes de la industria petrolera",
                 "de acuerdo con el informe de la OPEP",
                 "citing tanker tracking data sources said",
                 "volgens Staatsolie in een verklaring",
                 "data from the Ministry of Energy showed"),
        languages=("en", "es", "nl"), access_label="PUBLIC", credibility="UNKNOWN",
        predictive_state="UNTESTED", licence="free to read",
        notes="IN THIS PROVINCE THE CITATION GRAPH IS UNUSUALLY SHORT AND THEREFORE UNUSUALLY "
              "USEFUL: almost every Venezuelan production number in the world press traces to "
              "one of three originals, so identifying which one a story used tells the desk "
              "whether it has new information or an echo"),
    source_class(
        "ae_mirror_graph", "The MIRROR GRAPH: the counterparties whose published statistics "
                           "reconstruct what this province stopped publishing -- US import "
                           "records, Chinese customs, Indian refinery disclosures and Comtrade",
        layer="source_graph",
        roots=("https://www.eia.gov/petroleum/supply/weekly/",
               "http://english.customs.gov.cn/statics/report/monthly.html",
               "https://comtradeplus.un.org/"),
        queries=("China customs crude oil imports by origin monthly",
                 "US crude imports from Venezuela weekly EIA",
                 "refinery crude slate heavy sour import disclosure",
                 "importaciones de crudo venezolano datos espejo"),
        languages=("en", "es"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE SINGLE MOST IMPORTANT METHODOLOGICAL ROW IN THE PACK. When a state stops "
              "publishing, its counterparties do not, and the sum of what everyone else reports "
              "receiving is a lawful reconstruction of what it exported. This is the substitute "
              "named against every Venezuelan absence in `NO_LAWFUL_GROUND`"),
)

#: PACK-LEVEL LAYER ABSENCES: NONE. All ten layers carry at least one real source somewhere in
#: this province, so declaring a layer absent at PROVINCE level would be false -- a layer that
#: Guyana covers is not absent because Venezuela does not. THE HONEST UNIT OF ABSENCE HERE IS
#: (JURISDICTION, LAYER), and that is `NO_LAWFUL_GROUND` below, which is where the real refusals
#: live and where each one names its LAWFUL SUBSTITUTE.
LAYER_ABSENCES: dict[str, str] = {}

#: THE MEASURED REFUSALS. Each row is a (jurisdiction, layer) pair for which the ground genuinely
#: does not exist, WHY it does not, and the LAWFUL SUBSTITUTE the desk uses instead. This table
#: is worth more than a padded source row: a declared absence with a named substitute is a
#: measurement and a blank is work not done (L1.28a).
NO_LAWFUL_GROUND: tuple[dict[str, str], ...] = (
    {"jurisdiction": "ve", "layer": "official",
     "reason": "THE STATISTICS STOPPED. Venezuela's national statistics institute ceased "
               "publishing most macroeconomic series for years, the central bank suspended and "
               "then only partially resumed its own publication, and PDVSA has released no "
               "audited financial statements since 2016. There is no Venezuelan CPI, GDP, trade "
               "or corporate-accounts series a point-in-time study can use at all",
     "substitute": "OPEC's SECONDARY SOURCES series for production; the Venezuelan Finance "
                   "Observatory's independently computed CPI with its published method; MIRROR "
                   "CUSTOMS data from the United States (EIA imports by origin, US Census) and "
                   "from China's customs administration via UN Comtrade; and tanker-movement "
                   "press reports for cargo counts. Every one is public and none of them is the "
                   "thing itself, so a Venezuelan cell is labelled with the substitute it used",
     "status": "DECLARED_ABSENT_WITH_SUBSTITUTE"},
    {"jurisdiction": "ve", "layer": "institutional",
     "reason": "no exchange tape, no clearing statistics and no corporate disclosure regime a "
               "desk can read; the Caracas bourse's prices are dominated by the currency regime "
               "rather than by the companies, and PDVSA's joint-venture accounts are unpublished",
     "substitute": "the OPEC secretariat and the IMF as the institutional readers of last "
                   "resort, plus the PUBLISHED US COURT DOCKETS in the PDV Holding and Citgo "
                   "proceedings, which have put more audited Venezuelan corporate detail on the "
                   "public record than any Venezuelan institution has",
     "status": "DECLARED_ABSENT_WITH_SUBSTITUTE"},
    {"jurisdiction": "gy", "layer": "retail_ecology",
     "reason": "there is NO domestic retail FX or CFD ecology in Guyana. Residents transact "
               "through licensed banks and cambios at a rate that barely moves; there is no "
               "margin industry, no retail positioning statistic and no trading forum of any size",
     "substitute": "the DIASPORA remittance boards and the interior gold-buying discussion, "
                   "which is where the only retail-level price signal in the country lives: the "
                   "spread between the Gold Board's price and the backdam buyer's price",
     "status": "DECLARED_ABSENT_WITH_SUBSTITUTE"},
    {"jurisdiction": "sr", "layer": "app_ecosystem",
     "reason": "Suriname has no meaningful trading-app or public-API ecosystem; the central "
               "bank and the statistics office publish PDFs and the banks publish product pages",
     "substitute": "the IMF and World Bank APIs, which carry the Surinamese programme series in "
                   "machine-readable form, and the CBvS PDF series read as documents",
     "status": "DECLARED_ABSENT_WITH_SUBSTITUTE"},
    {"jurisdiction": "sr", "layer": "academic",
     "reason": "the Surinamese scholarly output on its own economy is very small and only "
               "partly digitised; there is no domestic finance literature to speak of",
     "substitute": "OpenAlex and CORE for the Dutch-language and international literature on "
                   "Suriname, plus the IMF staff reports, which are the most detailed public "
                   "analysis of the Surinamese economy that exists",
     "status": "DECLARED_ABSENT_WITH_SUBSTITUTE"},
    {"jurisdiction": "tt", "layer": "physical_economy",
     "reason": "PARTIAL, AND THE PART THAT IS MISSING IS THE ONE THAT MATTERS: Trinidad "
               "publishes gas production by field, and it does NOT publish LNG train-level "
               "utilisation, cargo-by-cargo loadings or the NGC's allocation between LNG, "
               "ammonia, methanol and power. The allocation is the decision and it is private",
     "substitute": "the ministry's aggregate LNG and petrochemical output series as the "
                   "downstream read, the operators' own announcements of turnarounds and "
                   "idlings, and the shipping press for departures. The allocation itself stays "
                   "UNMEASURED and is never inferred from an output total",
     "status": "DECLARED_ABSENT_WITH_SUBSTITUTE"},
)


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
    return {k: tuple(v) for k, v in out.items()}


def no_lawful_ground(jurisdiction: str = "") -> tuple[dict[str, str], ...]:
    """The declared (jurisdiction, layer) absences, optionally for one jurisdiction. Every row
    carries a substitute; a row without one would be a hole wearing a label."""
    want = str(jurisdiction).lower()
    return tuple(r for r in NO_LAWFUL_GROUND if not want or r["jurisdiction"] == want)


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
            "jurisdiction_absences": {f"{r['jurisdiction']}:{r['layer']}": r["substitute"]
                                      for r in NO_LAWFUL_GROUND},
            "rule": "ten layers, each carrying a source or named ABSENT with a reason; in a "
                    "multi-jurisdiction pack the honest unit of absence is (jurisdiction, "
                    "layer) and every such absence names its LAWFUL SUBSTITUTE; fringe and "
                    "unreliable PUBLIC material is kept as a low-weight evidence object and "
                    "never dropped; a source whose terms forbid machine extraction is "
                    "registered machine_use_allowed=false, never scraped and never omitted"}


#: NATIVE QUERY TERRITORIES -- what the deep-forest miner actually types, per layer, in the
#: languages of the ground. Three or more for every one of the ten layers. English is native on
#: two of the four grounds here and is used as such; Spanish, Dutch, Sranan Tongo and Guyanese
#: Creolese carry the other two and the physical economy of all four.
QUERY_TERRITORIES: dict[str, tuple[str, ...]] = {
    "official": ("Natural Resource Fund report Guyana receipts profit oil",
                 "Ministry of Energy Trinidad monthly bulletin gas production by field",
                 "producción de crudo PDVSA Gaceta Oficial decreto",
                 "Centrale Bank van Suriname wisselkoers jaarverslag",
                 "OFAC general license Venezuela Federal Register notice",
                 "Bank of Guyana statistical bulletin market exchange rates"),
    "institutional": ("OPEC monthly oil market report secondary sources Venezuela",
                      "IMF Article IV Guyana oil revenue staff report",
                      "Staatsolie jaarverslag Block 58 productiedeling",
                      "ICJ Guyana Venezuela provisional measures order",
                      "UN Comtrade crude petroleum mirror exports Venezuela"),
    "academic": ("resource curse oil windfall small economy Guyana research",
                 "hiperinflación venezolana dolarización estudio económico",
                 "natural gas depletion Trinidad economic modelling paper",
                 "kleinschalige goudwinning Suriname onderzoek kwik",
                 "petroleum fiscal regime cost recovery ceiling analysis"),
    "practitioner": ("FPSO commissioning schedule Guyana first oil update",
                     "Point Lisas ammonia plant idled gas curtailment",
                     "Dragon gas licence Trinidad Venezuela negotiation",
                     "GranMorgu Suriname project milestone update",
                     "tanker loading programme Guyana cargoes per month",
                     "análisis del sector petrolero venezolano consultora",
                     "olie- en gassector Suriname analyse"),
    "retail_ecology": ("dólar paralelo hoy tasa BCV brecha",
                       "foreign exchange shortage Trinidad credit card limit",
                       "sending money to Guyana best rate remittance",
                       "dem boys seh oil contract",
                       "backdam gold buying price dredge",
                       "gowtu prijs kondre wroko koopman"),
    "app_ecosystem": ("federal register api venezuela sanctions documents json",
                      "EIA API crude imports by country series",
                      "Comtrade API 2709 reporter partner crude",
                      "mobile money Guyana MMG limits",
                      "aplicación tasa de cambio Venezuela actualizada hoy"),
    "media": ("Stabroek News oil production figures monthly",
              "Newsday Trinidad gas curtailment plant closure",
              "Efecto Cocuyo producción petrolera cifras",
              "Starnieuws Staatsolie olieproductie nieuws",
              "gowtu prijs kondre wroko goudsector",
              "Kaieteur News cost oil audit dem boys"),
    "archive": ("Gaceta Oficial archivo decreto petrolero número",
                "web archive energy.gov.tt monthly bulletin",
                "Staatsblad van de Republiek Suriname resolutie archief",
                "Digital Library of the Caribbean Guyana annual report",
                "archived NRF quarterly report Guyana ministry of finance",
                "jaarverslag Centrale Bank van Suriname historisch archief"),
    "physical_economy": ("ship to ship transfer Venezuelan crude tanker press report",
                         "Point Fortin LNG cargo departure schedule",
                         "transbordo de crudo buque a buque, exportación venezolana",
                         "Guyana Gold Board declaration ounces monthly backdam",
                         "gowtu wroko kleinschalige goudwinning Suriname",
                         "port authority Trinidad vessel arrival notice",
                         "lightering Demerara anchorage draft restriction"),
    "source_graph": ("according to the OPEC monthly report Venezuela production",
                     "según fuentes de la industria petrolera venezolana",
                     "volgens Staatsolie in een verklaring",
                     "citing tanker tracking data sources said",
                     "data from the Ministry of Energy showed Trinidad"),
}

# --------------------------------------------------------------------------- datasets
#: TWENTY CATALOGUE ENTRIES, spread across the ten layers, each carrying the twelve fields the
#: data-discovery swarm needs. `pit_feasible` is the field the catalogue exists for: in this
#: province the ministry pages are OVERWRITTEN IN PLACE, so several of the best series have no
#: vintage at all and can only ever produce NOT_PIT_SAFE cells unless the archive layer caught
#: them. Saying so here is the difference between a cell that is wrong and a cell that is refused.
def dataset(name: str, *, source: str, coverage: str, frequency: str,
            publication_lag_days: float, revisions: str, licence: str, history_from: str,
            pit_feasible: bool, assets: Iterable[str], mechanism_families: Iterable[str],
            how_to_fetch: str) -> dict[str, Any]:
    """One catalogue entry of the data-discovery swarm, with exactly the twelve fields the
    framework's `DatasetRow` declares -- no extras, because `DatasetRow` has no `notes` field
    and a thirteenth key would reach the framework as a coercion note."""
    return {"name": name, "source": source, "coverage": coverage, "frequency": frequency,
            "publication_lag_days": float(publication_lag_days), "revisions": revisions,
            "licence": licence, "history_from": history_from, "pit_feasible": bool(pit_feasible),
            "assets": _seq(assets), "mechanism_families": _seq(mechanism_families),
            "how_to_fetch": how_to_fetch}


DATASETS: tuple[dict[str, Any], ...] = (
    dataset("Guyana Natural Resource Fund receipts, balance and withdrawals",
            source="Ministry of Finance, Guyana (finance.gov.gy)",
            coverage="every month since the fund's first receipt in 2020; profit oil, royalty, "
                     "cargoes lifted, withdrawals to the budget",
            frequency="monthly, with a fuller quarterly report", publication_lag_days=20.0,
            revisions="restated when a cargo settles in a later month",
            licence="free, public", history_from="2020-01", pit_feasible=False,
            assets=("XBRUSD", "XTIUSD", "USDBRL"),
            mechanism_families=("institutional_flow", "calendar_settlement", "transfer"),
            how_to_fetch="finance.gov.gy publications section: the monthly NRF report and the "
                         "quarterly report PDFs; the pages are OVERWRITTEN so the vintage must "
                         "be taken from the web archive, not from the live link"),
    dataset("Guyana petroleum production and lifting schedule",
            source="Ministry of Natural Resources, Guyana (nre.gov.gy) and the operator's "
                   "public releases",
            coverage="monthly production by project and the government's lifting entitlement "
                     "cargo by cargo since December 2019",
            frequency="monthly", publication_lag_days=25.0,
            revisions="occasional restatement when a cargo slips a month",
            licence="free, public", history_from="2019-12", pit_feasible=False,
            assets=("XBRUSD", "XTIUSD"),
            mechanism_families=("corporate_flow", "release_surprise", "transfer"),
            how_to_fetch="nre.gov.gy petroleum division pages plus the operator's project "
                         "announcements; join to FPSO_SCHEDULE on the project name to convert "
                         "a production print into a per-vessel ramp observation"),
    dataset("Bank of Guyana market exchange rates and statistical bulletin",
            source="Bank of Guyana (bankofguyana.org.gy)",
            coverage="bank and cambio buying and selling rates, reserves, monetary aggregates",
            frequency="weekly and quarterly", publication_lag_days=10.0,
            revisions="rare", licence="free, public", history_from="2005-01", pit_feasible=True,
            assets=("USDBRL", "USDMXN"),
            mechanism_families=("carry_funding", "residual"),
            how_to_fetch="bankofguyana.org.gy statistics section: the weekly market rates table "
                         "and the quarterly statistical bulletin PDFs, parsed to a rate series"),
    dataset("Guyana Bureau of Statistics oil and non-oil national accounts and trade",
            source="Bureau of Statistics, Guyana (statisticsguyana.gov.gy)",
            coverage="GDP split into oil and non-oil, merchandise trade by commodity",
            frequency="quarterly and annual", publication_lag_days=75.0,
            revisions="routinely revised for two vintages",
            licence="free, public", history_from="2015-01", pit_feasible=False,
            assets=("XBRUSD", "XAUUSD", "SUGAR", "XALUSD"),
            mechanism_families=("release_surprise", "transfer"),
            how_to_fetch="statisticsguyana.gov.gy national accounts and external trade pages; "
                         "the oil and non-oil split is the series that makes Guyana a readable "
                         "natural experiment and it is published as a separate table"),
    dataset("Trinidad Ministry of Energy monthly bulletin: gas and crude BY FIELD",
            source="Ministry of Energy and Energy Industries, Trinidad and Tobago "
                   "(energy.gov.tt)",
            coverage="natural gas and crude production by field with the operator named, plus "
                     "LNG, ammonia, methanol and urea output",
            frequency="monthly", publication_lag_days=60.0,
            revisions="prior months revised as operators finalise",
            licence="free, public", history_from="2000-01", pit_feasible=False,
            assets=("XNGUSD", "CORN", "WHEAT", "SOYBEAN"),
            mechanism_families=("corporate_flow", "release_surprise", "failure"),
            how_to_fetch="energy.gov.tt statistics pages: the monthly bulletin spreadsheets; "
                         "the live link is overwritten each month, so the point-in-time series "
                         "must come from the web archive snapshots of the same URL"),
    dataset("Trinidad Central Statistical Office prices and trade",
            source="Central Statistical Office, Trinidad and Tobago (cso.gov.tt)",
            coverage="consumer prices, merchandise trade, national accounts",
            frequency="monthly and quarterly", publication_lag_days=45.0,
            revisions="standard national-accounts revision cycle",
            licence="free, public", history_from="2000-01", pit_feasible=False,
            assets=("USDBRL", "USDMXN"),
            mechanism_families=("release_surprise", "residual"),
            how_to_fetch="cso.gov.tt publications: the CPI and trade releases as PDF and Excel"),
    dataset("Central Bank of Trinidad and Tobago FX sales to authorised dealers",
            source="Central Bank of Trinidad and Tobago (central-bank.org.tt)",
            coverage="the central bank's foreign-exchange sales into the market, reserves and "
                     "the repo rate",
            frequency="monthly and quarterly", publication_lag_days=30.0,
            revisions="rare", licence="free, public", history_from="2010-01", pit_feasible=True,
            assets=("USDBRL", "USDMXN", "US500"),
            mechanism_families=("carry_funding", "institutional_flow"),
            how_to_fetch="central-bank.org.tt statistics: the monetary and financial statistics "
                         "tables; the FX SALES series is the rationing instrument and it is "
                         "published as a quantity, which is the point"),
    dataset("OPEC Monthly Oil Market Report: Venezuela, direct AND secondary",
            source="OPEC Secretariat (momr.opec.org)",
            coverage="crude production by member country, twice, in two disagreeing series",
            frequency="monthly", publication_lag_days=14.0,
            revisions="both series revised; the direct series more heavily",
            licence="free to read; redistribution restricted",
            history_from="2003-01", pit_feasible=False,
            assets=("XBRUSD", "XTIUSD"),
            mechanism_families=("release_surprise", "failure", "transfer"),
            how_to_fetch="momr.opec.org monthly PDF; extract the crude production tables and "
                         "keep BOTH columns -- the gap between them is `opec_gap()` and the "
                         "archive of past issues is the only way to get a vintage"),
    dataset("EIA weekly US crude imports by country of origin",
            source="US Energy Information Administration (eia.gov)",
            coverage="weekly US crude imports by origin country, refinery runs, Cushing stocks",
            frequency="weekly", publication_lag_days=5.0,
            revisions="weekly figures revised into the monthly series",
            licence="public domain (US government work)",
            history_from="2010-01", pit_feasible=True,
            assets=("XTIUSD", "XBRUSD", "USDMXN"),
            mechanism_families=("corporate_flow", "positioning", "transfer"),
            how_to_fetch="api.eia.gov v2 petroleum/move/wkly series by origin country; the "
                         "Venezuela and Guyana origin lines are the physical confirmation that "
                         "a licence or a ramp actually produced barrels at the US Gulf"),
    dataset("OFAC and Federal Register Venezuela document stream",
            source="US Treasury OFAC and the Federal Register (federalregister.gov)",
            coverage="every published licence, amendment, revocation, FAQ and notice",
            frequency="event-driven", publication_lag_days=0.0,
            revisions="none; a published act is a published act",
            licence="public domain (US government work)",
            history_from="2015-01", pit_feasible=True,
            assets=("XBRUSD", "XTIUSD", "USDMXN", "USDCNH"),
            mechanism_families=("failure", "release_surprise", "transfer"),
            how_to_fetch="federalregister.gov/api/v1/documents.json with a Venezuela and OFAC "
                         "term filter plus the OFAC recent-actions page; each hit is a dated, "
                         "typed event row and this is the pack's cleanest machine-readable feed"),
    dataset("UN Comtrade mirror trade for the province",
            source="UN Comtrade (comtradeplus.un.org)",
            coverage="reported imports and exports of crude, gas, gold, bauxite, ammonia and "
                     "methanol by every reporting partner",
            frequency="monthly and annual", publication_lag_days=90.0,
            revisions="heavily revised as reporters file late",
            licence="free with attribution; API rate-limited",
            history_from="2000-01", pit_feasible=False,
            assets=("XBRUSD", "XAUUSD", "XALUSD", "CORN"),
            mechanism_families=("transfer", "scouts"),
            how_to_fetch="comtradeapi.un.org with HS 2709 (crude), 2711 (gas), 7108 (gold) and "
                         "2814 (ammonia); read the PARTNERS' reports rather than the province's "
                         "own, which is the lawful substitute for what Venezuela stopped filing"),
    dataset("Centrale Bank van Suriname monetary and exchange-rate statistics",
            source="Centrale Bank van Suriname (cbvs.sr)",
            coverage="the exchange rate, reserve money, reserves and the auction results",
            frequency="weekly and monthly", publication_lag_days=15.0,
            revisions="occasional", licence="free, public",
            history_from="2015-01", pit_feasible=False,
            assets=("USDBRL", "XAUUSD"),
            mechanism_families=("carry_funding", "institutional_flow"),
            how_to_fetch="cbvs.sr statistics section: the weekly exchange-rate table and the "
                         "monthly monetary survey PDFs; read the Dutch column headers"),
    dataset("Suriname Algemeen Bureau voor de Statistiek prices and trade",
            source="Algemeen Bureau voor de Statistiek (statistics-suriname.org)",
            coverage="consumer prices, trade by commodity including gold and oil",
            frequency="monthly and annual", publication_lag_days=40.0,
            revisions="standard", licence="free, public",
            history_from="2010-01", pit_feasible=False,
            assets=("XAUUSD", "XBRUSD"),
            mechanism_families=("release_surprise", "transfer"),
            how_to_fetch="statistics-suriname.org publicaties: the prijsindexcijfers and the "
                         "handelsstatistiek releases, in Dutch"),
    dataset("Staatsolie annual and interim reporting on Block 58",
            source="Staatsolie Maatschappij Suriname (staatsolie.com)",
            coverage="the state company's production, its carried interest in Block 58 and the "
                     "GranMorgu development milestones",
            frequency="annual with interim releases", publication_lag_days=120.0,
            revisions="rare", licence="free, public",
            history_from="2015-01", pit_feasible=True,
            assets=("XBRUSD", "XTIUSD"),
            mechanism_families=("corporate_flow", "transfer"),
            how_to_fetch="staatsolie.com investor and news pages: the jaarverslag PDFs and the "
                         "project updates; this is the PRIMARY Surinamese-side disclosure on "
                         "the development that is this pack's forward control"),
    dataset("ICJ docket: Guyana v. Venezuela",
            source="International Court of Justice (icj-cij.org, case 171)",
            coverage="every filing, order, hearing and scheduled future date in the case",
            frequency="event-driven with a PUBLISHED FORWARD CALENDAR",
            publication_lag_days=0.0,
            revisions="none; the court record is the record",
            licence="free, public court record",
            history_from="2018-03", pit_feasible=True,
            assets=("XBRUSD", "XTIUSD", "XAUUSD", "US500"),
            mechanism_families=("failure", "calendar_settlement", "residual"),
            how_to_fetch="icj-cij.org/case/171: the case page lists orders and press releases "
                         "with dates, and the procedural orders name FUTURE deadlines -- the "
                         "only forward-dated political-risk calendar in this pack"),
    dataset("Guyana Gold Board and GGMC declarations",
            source="Guyana Geology and Mines Commission and the Gold Board (ggmc.gov.gy)",
            coverage="declared gold production and exports, by month, with the small-scale "
                     "sector separated where it is separated at all",
            frequency="monthly and annual", publication_lag_days=45.0,
            revisions="frequent; late declarations are common",
            licence="free, public", history_from="2010-01", pit_feasible=False,
            assets=("XAUUSD",),
            mechanism_families=("corporate_flow", "scouts"),
            how_to_fetch="ggmc.gov.gy statistics and the Bank of Guyana's export tables; "
                         "reconcile against Comtrade mirror imports, because the two do not "
                         "agree and the DIFFERENCE is the measurement"),
    dataset("Venezuelan Finance Observatory independent CPI and activity indicators",
            source="Observatorio Venezolano de Finanzas (observatoriodefinanzas.com)",
            coverage="an independently computed monthly CPI with a published basket and method, "
                     "plus activity indicators, for the years the state published nothing",
            frequency="monthly", publication_lag_days=5.0,
            revisions="occasional", licence="free, public",
            history_from="2019-01", pit_feasible=True,
            assets=("USDBRL", "USDMXN"),
            mechanism_families=("release_surprise", "residual"),
            how_to_fetch="observatoriodefinanzas.com monthly publication; THE NAMED LAWFUL "
                         "SUBSTITUTE for the Venezuelan price series, and it is used as a "
                         "substitute by label, never presented as the official series"),
    dataset("CFTC Commitments of Traders: crude and natural gas",
            source="US Commodity Futures Trading Commission (cftc.gov)",
            coverage="managed money and commercial positioning in WTI, Brent and Henry Hub",
            frequency="weekly", publication_lag_days=3.0,
            revisions="rare", licence="public domain (US government work)",
            history_from="2006-01", pit_feasible=True,
            assets=("XTIUSD", "XBRUSD", "XNGUSD"),
            mechanism_families=("positioning", "derivatives_expiry"),
            how_to_fetch="cftc.gov Commitments of Traders disaggregated futures-and-options "
                         "reports, downloaded as the weekly CSV and joined on the Tuesday "
                         "snapshot date, never on the Friday publication date"),
    dataset("Web archive snapshots of the overwritten ministry pages",
            source="the Internet Archive (web.archive.org)",
            coverage="the historical vintages of energy.gov.tt, nre.gov.gy and finance.gov.gy "
                     "pages that publish the current file over the same link",
            frequency="irregular, crawl-dependent", publication_lag_days=0.0,
            revisions="none; a snapshot is a snapshot",
            licence="free, public archive", history_from="2010-01", pit_feasible=True,
            assets=("XNGUSD", "XBRUSD", "CORN"),
            mechanism_families=("scouts", "release_surprise"),
            how_to_fetch="web.archive.org CDX API over the ministry URLs to enumerate "
                         "snapshots, then fetch the dated captures; THIS IS THE ONLY SOURCE OF "
                         "POINT-IN-TIME VINTAGES for the pack's two best physical series"),
    dataset("Tanker-movement and cargo reporting in the public press",
            source="the wire services and the specialist energy press",
            coverage="reported loadings, ship-to-ship transfers and destination changes for "
                     "Venezuelan and Guyanese cargoes",
            frequency="irregular, several times a week", publication_lag_days=2.0,
            revisions="frequently corrected as cargoes are reassigned",
            licence="free to read", history_from="2019-01", pit_feasible=False,
            assets=("XBRUSD", "XTIUSD", "USDCNH"),
            mechanism_families=("corporate_flow", "scouts", "failure"),
            how_to_fetch="the energy desks of the wire services plus oilnow.gy and "
                         "efectococuyo.com; THE NAMED LAWFUL SUBSTITUTE for the export series "
                         "Venezuela does not publish, read as REPORTS and never as a purchased "
                         "vessel feed -- every row is PRESS_REPORTED and promotes nothing alone"),
)

# --------------------------------------------------------------------------- actors
#: TWENTY-ONE ACTORS, each with all eleven fields, and AT LEAST FOUR FOR EVERY JURISDICTION --
#: five Guyanese, five Trinidadian, five Venezuelan, four Surinamese and two that belong to the
#: province rather than to any one state. An actor whose FALSIFIER is blank is a story, and a
#: story is not a research object. The operators, the state oil companies, the petrochemical
#: producers and the miners appear HERE and in no instrument tuple anywhere in this file, which
#: is the two-lane order (2026-09-06) as it applies to a province made of national champions.
ACTORS: tuple[dict[str, Any], ...] = (
    # ---------------------------------------------------------------- Guyana
    {"name": "The Stabroek block co-venturers (the operating consortium)",
     "jurisdiction": "gy",
     "holds": "the operatorship and the joint-venture interests in the block that has taken "
              "Guyana from zero to roughly 650,000 b/d in six years, plus a sanctioned "
              "development queue with hulls already under construction",
     "forced_to": ("announce each final investment decision, each vessel name and each nameplate "
                   "capacity publicly, years before first oil",
                   "seek and publish government approval of every field development plan",
                   "commission each vessel on an engineering schedule that cannot be hurried "
                   "materially and whose slippage is therefore informative"),
     "when": "at each FID announcement, each vessel sail-away, each first-oil announcement and "
             "each quarterly operational update",
     "information": ("the true commissioning state of every vessel months before any statistic",
                     "the reservoir performance that decides whether a vessel runs above "
                     "nameplate after debottlenecking",
                     "the lifting schedule and the cargo programme",
                     "its own cost stack, which sets the cost-oil claim and therefore the "
                     "government's take"),
     "constraints": ("a published production-sharing agreement whose cost-recovery ceiling is "
                     "75% and whose profit split is 50/50",
                     "an engineering supply chain for hulls, topsides and subsea equipment that "
                     "is globally capacity-constrained",
                     "a host government with an election cycle and a territorial dispute"),
     "instruments": ("XBRUSD", "XTIUSD"),
     "counterparties": ("the Government of Guyana at the approval and the lifting",
                        "the shipyards and topsides contractors building each vessel",
                        "the term buyers who take the cargoes on Brent-linked formulas",
                        "its own joint-venture partners, who publish separately"),
     "observables": ("the FID announcements with nameplate capacity",
                     "the vessel sail-away and arrival dates",
                     "the first-oil announcements", "the quarterly production updates",
                     "the published field development plan approvals"),
     "impact": "the largest single non-OPEC supply addition of the decade, arriving in DATED "
               "STEPS rather than continuously; each step is an announced, anticipated, "
               "schedulable event and the tradable question is whether the anticipation is "
               "complete",
     "persistence": "a vessel that starts stays started: the capacity step is permanent, which "
                    "makes this a LEVEL series rather than a shock series and means a study "
                    "must test the step, not the day",
     "falsifier": "if capacity steps carry no information beyond the EIA and OPEC non-OPEC "
                  "supply forecasts published before them, the ramp is fully anticipated and "
                  "the domain is dead; the test is the announcement-to-first-oil window against "
                  "matched windows with no step",
     "notes": "THE TWO-LANE ORDER APPLIES IN FULL. The co-venturers are listed companies and "
              "none of them is an instrument in this pack. Their SCHEDULE is the object"},
    {"name": "The Government of Guyana as licensor and lifting party",
     "jurisdiction": "gy",
     "holds": "the licence, the approval of every field development plan, a 2% royalty, 50% of "
              "profit oil and the physical entitlement cargoes that follow from it",
     "forced_to": ("publish the production sharing agreement, which it did, making its own "
                   "revenue function computable by anybody",
                   "pay the receipts into the Natural Resource Fund under the 2021 NRF Act",
                   "market its entitlement cargoes and announce the liftings"),
     "when": "at each development plan approval, each cargo lifting and each monthly NRF report",
     "information": ("the cargo programme and the marketing outcome before it is reported",
                     "the audit position on the contractor's recoverable cost stack",
                     "its own budget execution and the withdrawal it intends"),
     "constraints": ("the 75% cost-recovery ceiling, which bounds how fast costs can be "
                     "recovered and therefore how fast profit oil grows",
                     "a statutory withdrawal rule that limits what can be spent in a year",
                     "an electorate that can see the fund balance and the state of the roads"),
     "instruments": ("XBRUSD", "XTIUSD", "USDBRL"),
     "counterparties": ("the Stabroek co-venturers", "the buyers of its entitlement cargoes",
                        "the multilateral lenders and the IMF at Article IV",
                        "the Venezuelan state, in a territorial dispute before the ICJ"),
     "observables": ("the NRF monthly receipts and balance", "the cargo count per month",
                     "the withdrawal to the budget", "the Appropriation Act ceiling",
                     "the published development plan approvals"),
     "impact": "a sovereign whose oil income is computable from the oil price and whose spending "
               "is capped by statute -- so the FISCAL IMPULSE is legislated and visible rather "
               "than discretionary and hidden",
     "persistence": "the fiscal regime persists until the law changes; the 2023 model agreement "
                    "shows it can and that the change applies forward, not backward",
     "falsifier": "if NRF receipts are fully explained by lagged Brent times a constant, the "
                  "fiscal series adds nothing to the price and the domain collapses into the "
                  "barrel; the test is the residual after the published formula is applied",
     "notes": "THE ONLY SOVEREIGN IN THIS DESK'S BOOK WHOSE TAKE IS A PUBLISHED FORMULA"},
    {"name": "The Bank of Guyana and the licensed cambio market",
     "jurisdiction": "gy",
     "holds": "the reserves, the banking supervision and the sale of the government's converted "
              "oil dollars into a small domestic market",
     "forced_to": ("publish a daily bank and cambio market rate",
                   "absorb or release the foreign exchange the oil rent brings in",
                   "keep a small, dollarised-adjacent banking system stable"),
     "when": "continuously, with a weekly statistical publication",
     "information": ("the true supply of foreign exchange in the market that week",
                     "the banks' open positions and the queue for dollars, if there is one",
                     "the government's conversion schedule"),
     "constraints": ("a very small market in which a single large conversion moves everything",
                     "no published target and no policy-rate instrument that matters",
                     "an economy growing at rates that make every ratio unstable"),
     "instruments": ("USDBRL", "USDMXN"),
     "counterparties": ("the commercial banks and licensed cambios",
                        "the Ministry of Finance at the conversion",
                        "the importers whose demand is growing with the construction boom"),
     "observables": ("the published bank and cambio buying and selling rates",
                     "the reserve series", "the monetary aggregates",
                     "the reported availability of foreign exchange at the banks"),
     "impact": "ALMOST NONE, AND THAT IS THE FINDING. The rate barely moves through the largest "
               "per-capita oil boom in history, which means the rent is being sterilised into "
               "the fund and the adjustment is happening in the import bill and in prices",
     "persistence": "the stabilised regime has persisted for years and there is no announced "
                    "intention to change it",
     "falsifier": "if the Guyanese rate ever starts to carry information, this actor becomes a "
                  "macro object; until then, a cell conditioned on the GYD rate is conditioned "
                  "on a constant and must be refused",
     "notes": "carried because a NEGATIVE actor is still an actor: the reason this pack routes "
              "every Guyanese mechanism through the barrel and the fund is measured here"},
    {"name": "The Guyana Gold Board and the backdam dredge economy",
     "jurisdiction": "gy",
     "holds": "the statutory purchase of declared gold, against a small-scale mining sector that "
              "produces most of the country's gold and declares what it chooses to declare",
     "forced_to": ("publish the declared production and export series",
                   "price gold to the dredge operators against the London benchmark less its "
                   "own margin, which is what decides whether they declare at all"),
     "when": "monthly, at the declaration, and continuously at the buying window",
     "information": ("the real spread between its price and the informal buyer's price",
                     "which districts are producing and which are flooded out",
                     "the mercury and fuel logistics of the interior"),
     "constraints": ("a border with two neighbours across which gold walks freely",
                     "an interior reachable only by river and airstrip",
                     "a price it does not set"),
     "instruments": ("XAUUSD",),
     "counterparties": ("the small-scale miners and dredge owners -- the porknockers",
                        "the licensed exporters and refiners abroad",
                        "the informal buyers who are its real competition"),
     "observables": ("the monthly declaration series", "the export line in the trade statistics",
                     "the Comtrade mirror comparison with importing countries",
                     "the reported interior fuel price"),
     "impact": "a real but BADLY MEASURED gold supply series: declared output responds to the "
               "declaration incentive as much as to geology, which is why every gold cell in "
               "this pack is labelled WEAK",
     "persistence": "the measurement problem is structural and has persisted for decades",
     "falsifier": "if declared production and mirror imports reconcile within their own "
                  "dispersion, the leakage story is wrong and the declared series can be used "
                  "directly; the reconciliation is computable from Comtrade and is the test",
     "notes": "the Creolese vocabulary in `TERMINOLOGY['AE-C']` exists for this actor: the "
              "backdam economy is not discussed in standard English anywhere"},
    {"name": "GuySuCo and the Guyanese bauxite operators",
     "jurisdiction": "gy",
     "holds": "the sugar estates and the bauxite mines that WERE the Guyanese export economy "
              "before December 2019 and are now a small fraction of it",
     "forced_to": ("keep loss-making estates open for employment and political reasons",
                   "ship ore and sugar through river ports with draft restrictions",
                   "sell into quota and contract arrangements they do not set"),
     "when": "at the crop cycles, the shipment schedule and each budget subvention",
     "information": ("their own cost position and the true state of the estates",
                     "the shipping and draft constraints of the Demerara and Berbice rivers"),
     "constraints": ("river ports with real draft limits that cap vessel size",
                     "a sugar price they do not influence and a bauxite market dominated by "
                     "much larger producers",
                     "an oil economy bidding away their labour"),
     "instruments": ("SUGAR", "XALUSD"),
     "counterparties": ("the Caricom and European buyers of the sugar",
                        "the alumina refiners who take the bauxite",
                        "the Treasury, which funds the deficits"),
     "observables": ("the export volume lines in the trade statistics",
                     "the budget subvention to the sugar corporation",
                     "the shipment counts at the river terminals"),
     "impact": "SMALL AND SHRINKING, and that is exactly what makes it useful: this is the "
               "control group for the oil economy. Guyanese sugar and bauxite are what the "
               "country's exports did BEFORE the barrel and what they do without it",
     "persistence": "structural decline with political floors under it",
     "falsifier": "if the sugar and bauxite export series move with the oil-era Guyanese macro "
                  "data as closely as they did before 2019, then the oil boom did not change "
                  "the non-oil economy and the natural experiment has no treatment effect",
     "notes": "the non-oil half of the Bureau of Statistics GDP split is this actor, which is "
              "why that split is a declared dataset"},
    # ---------------------------------------------------------------- Trinidad and Tobago
    {"name": "The Atlantic LNG trains and their shareholders",
     "jurisdiction": "tt",
     "holds": "a four-train liquefaction complex at Point Fortin, restructured into a unitised "
              "entity, running below nameplate because the gas upstream of it is short",
     "forced_to": ("run the trains at whatever rate the upstream gas allows",
                   "schedule and announce turnarounds months in advance",
                   "send each cargo wherever the netback says, which is a published-price "
                   "decision made vessel by vessel"),
     "when": "continuously, with dated turnarounds and dated cargo departures",
     "information": ("the true gas nomination for each train each day",
                     "the netback ranking of every destination that week",
                     "the maintenance state of each train"),
     "constraints": ("a DECLINING upstream resource base that no commercial decision can fix "
                     "quickly",
                     "an allocation of short gas between LNG, ammonia, methanol, power and steel",
                     "long-term contracts that bind some cargoes regardless of netback"),
     "instruments": ("XNGUSD", "XBRUSD"),
     "counterparties": ("the upstream producers who nominate the gas",
                        "the national gas company as aggregator and allocator",
                        "the buyers in Europe, Asia and Latin America"),
     "observables": ("the ministry's monthly LNG output series",
                     "announced turnarounds and outages", "reported cargo departures",
                     "the field-level gas production the trains draw on"),
     "impact": "a real Atlantic-basin LNG supply variable whose direction of effect on the ONE "
               "gas contract the box quotes is AMBIGUOUS: a Trinidadian outage tightens the "
               "Atlantic basin and can LOOSEN Henry Hub by freeing US cargoes",
     "persistence": "the decline is structural and multi-year; an outage is weeks",
     "falsifier": "if Trinidadian LNG output changes have no measurable effect on XNGUSD once "
                  "US production, US storage and heating-degree-days are conditioned on, then "
                  "the gas leg of this pack routes only through ammonia and the domain says so",
     "notes": "THE BASIS RISK IS THE POINT. This actor is the reason the LNG row in "
              "`TRANSMISSION_TARGETS` spends a paragraph on Henry Hub not being Atlantic LNG"},
    {"name": "The Trinidadian upstream gas producers",
     "jurisdiction": "tt",
     "holds": "the producing gas fields offshore Trinidad and the nomination decisions that "
              "decide how much molecule reaches the trains and the petrochemical estate",
     "forced_to": ("report production to the ministry, which publishes it BY FIELD monthly",
                   "invest in infill and compression against a declining base",
                   "negotiate gas sales agreements with a single national aggregator"),
     "when": "monthly at the ministry bulletin, and at each project sanction announcement",
     "information": ("the real decline rate of each field, years before it shows in the series",
                     "the economics of each infill project at the current gas price",
                     "the cross-border resource position"),
     "constraints": ("geology: a mature basin with a real decline rate",
                     "a regulated gas price that has repeatedly been the subject of dispute",
                     "a cross-border field whose development needs a FOREIGN GOVERNMENT'S "
                     "LICENCE"),
     "instruments": ("XNGUSD", "CORN", "WHEAT"),
     "counterparties": ("the national gas company, the single buyer",
                        "the LNG trains and the Point Lisas plants downstream",
                        "the Venezuelan state, across the maritime boundary"),
     "observables": ("the ministry's field-level monthly gas production",
                     "project sanction announcements", "rig activity reports",
                     "the reported gas curtailment to specific plants"),
     "impact": "the ROOT of every Trinidadian mechanism in this pack: LNG, ammonia, methanol, "
               "power and the fiscal position all descend from this one series",
     "persistence": "a decline rate is a multi-year object; a single infill project shifts it "
                    "by a step",
     "falsifier": "if field-level production adds nothing over the national total in explaining "
                  "downstream output, the granularity is decoration and the domain should use "
                  "the total; the test is a horse race between the two series",
     "notes": "the field-level bulletin is the single most granular energy statistic in this "
              "pack and it is published by a ministry that owes nobody the detail"},
    {"name": "The Point Lisas ammonia and methanol producers",
     "jurisdiction": "tt",
     "holds": "one of the world's largest export ammonia complexes and a large methanol cluster, "
              "all of it gas-fed, some of it idled when the gas is short",
     "forced_to": ("idle or mothball a plant when the gas allocation or the netback says so, "
                   "and announce it when they do",
                   "sell into a global nitrogen market whose price they do not set",
                   "schedule turnarounds and announce them"),
     "when": "at each idling, restart, turnaround and contract reset",
     "information": ("their own gas allocation and its price",
                     "the netback ranking between ammonia, methanol and doing nothing",
                     "the real global nitrogen balance from their own order book"),
     "constraints": ("a short molecule allocated by an aggregator they do not control",
                     "competition from gas that is far cheaper elsewhere",
                     "plants that are expensive to stop and expensive to restart"),
     "instruments": ("CORN", "WHEAT", "SOYBEAN", "XNGUSD"),
     "counterparties": ("the national gas company at the allocation",
                        "the global fertiliser distributors and traders",
                        "the Chinese and US methanol buyers"),
     "observables": ("announced plant idlings and restarts",
                     "the ministry's monthly ammonia and methanol output",
                     "the published Tampa and Caribbean ammonia references",
                     "export volumes in the trade statistics"),
     "impact": "THE PROVINCE'S ONE GENUINE CROSS-COMMODITY CHAIN: Trinidadian gas shortfall "
               "raises Atlantic nitrogen cost, and nitrogen cost enters the acreage and margin "
               "decision for CORN, WHEAT and SOYBEAN at the planting window",
     "persistence": "an idling lasts months; the structural gas shortage lasts years",
     "falsifier": "if Trinidadian ammonia outages have no measurable effect on the nitrogen "
                  "reference once European gas-driven curtailments are conditioned on, the "
                  "chain runs through Europe and not through Trinidad, and AE-E is refuted",
     "notes": "the ammonia price itself is a LICENSED assessment this desk may not machine-read "
              "(`ae_price_reporting`, machine_use_allowed=false), so the chain is tested on "
              "PHYSICAL output volume and the price leg is declared UNMEASURED"},
    {"name": "The Central Bank of Trinidad and Tobago as an FX RATIONER",
     "jurisdiction": "tt",
     "holds": "the reserves, the repo rate that rarely moves, and -- the instrument that "
              "matters -- the allocation of foreign exchange to the authorised dealers",
     "forced_to": ("distribute a quantity of foreign exchange it does not earn",
                   "hold a quasi-peg it has not formally announced",
                   "publish its sales to the market and its reserve position"),
     "when": "at each distribution to the dealers and each quarterly announcement",
     "information": ("the real size of the unmet demand queue",
                     "which dealers are rationing which customers",
                     "the energy sector's conversion schedule, which is the supply side"),
     "constraints": ("energy export receipts that fall with gas production",
                     "a political economy in which a devaluation is extremely costly",
                     "a sovereign fund it can draw on only under conditions"),
     "instruments": ("USDBRL", "USDMXN", "US500"),
     "counterparties": ("the authorised dealer banks", "the importers and card users at the end "
                        "of the queue", "the energy companies who are the source of the dollars",
                        "the Ministry of Finance and the sovereign fund"),
     "observables": ("the published FX sales to the market", "the reserve series",
                     "the reported card and wire limits at the commercial banks",
                     "the informal premium reported in the press"),
     "impact": "a currency with almost no measured volatility and a large unmeasured shortage "
               "behind it. The observable is the QUEUE, not the rate, and a study that reads "
               "the rate's stability as calm has the country exactly backwards",
     "persistence": "the rationing regime has persisted for years and tightens with gas",
     "falsifier": "if reported FX shortage episodes do not coincide with the published decline "
                  "in central bank sales and in energy receipts, the shortage narrative is not "
                  "measuring the allocation and the conditioner is worthless",
     "notes": "`parallel_premium()` is written for this actor and for the Venezuelan one, which "
              "run the same arithmetic for opposite reasons"},
    {"name": "The Trinidadian Ministry of Finance and the Heritage and Stabilisation Fund",
     "jurisdiction": "tt",
     "holds": "a budget written on an ASSUMED oil and gas price, a sovereign fund, and a fiscal "
              "year that runs from October to September",
     "forced_to": ("publish a budget statement with its price assumption stated",
                   "draw on the sovereign fund when the assumption is wrong in the bad "
                   "direction, under published rules",
                   "report the fund's position quarterly"),
     "when": "at the budget statement in late September or early October, and quarterly",
     "information": ("the true revenue run-rate against the assumption, months before anybody",
                     "the energy companies' tax instalment schedule"),
     "constraints": ("a revenue base that is a direct function of gas volume times price",
                     "withdrawal rules on the fund",
                     "an electorate and a debt market both watching the same numbers"),
     "instruments": ("XNGUSD", "XBRUSD", "USDBRL"),
     "counterparties": ("the energy companies at the tax window",
                        "the domestic and external bondholders",
                        "the central bank at the FX window"),
     "observables": ("the budget statement and its stated price assumption",
                     "the quarterly fund reports and drawdowns",
                     "the revenue outturn against the assumption"),
     "impact": "THE FISCAL YEAR IS THE TRADABLE FACT. A budget read in October against an "
               "assumed price creates a dated, published, quantified gap between assumption and "
               "strip that nobody else on this desk carries",
     "persistence": "one fiscal year, by construction, with a mid-year review inside it",
     "falsifier": "if the assumption-to-strip gap has no measurable relationship to the fund "
                  "drawdown or to the subsequent fiscal measures, the budget assumption is "
                  "theatre and the mechanism is refuted",
     "notes": "this is why `FISCAL_YEARS` exists as a separate table: three of the four "
              "jurisdictions run the calendar year and Trinidad does not"},
    # ---------------------------------------------------------------- Venezuela
    {"name": "PDVSA and the joint ventures",
     "jurisdiction": "ve",
     "holds": "the licences over the largest proven reserve base on earth, an ageing upgrader "
              "and refining estate, and a production level a fraction of its historic peak",
     "forced_to": ("report production to OPEC by direct communication, which produces one of "
                   "the two disagreeing series",
                   "blend or upgrade extra-heavy crude, which requires diluent it must import "
                   "or produce",
                   "sell at a discount through intermediaries when the licensing regime forbids "
                   "direct sales to the obvious buyers"),
     "when": "monthly at the OPEC report; continuously in the physical market",
     "information": ("its own true wellhead production and the state of each upgrader",
                     "the diluent inventory that bounds how much extra-heavy it can move",
                     "the real discount it is receiving, cargo by cargo"),
     "constraints": ("a sanctions regime that determines who may lawfully buy",
                     "an upgrader and refinery estate with chronic availability problems",
                     "DILUENT: extra-heavy crude cannot move without it, and the import of it "
                     "is itself constrained",
                     "a creditor stack with judgments attached to its foreign assets"),
     "instruments": ("XBRUSD", "XTIUSD", "USDCNH"),
     "counterparties": ("the joint-venture partners still authorised to operate",
                        "the intermediaries and the Asian refiners who take the discounted "
                        "barrels",
                        "the US Gulf refiners when a licence permits them",
                        "OPEC, to which it reports directly"),
     "observables": ("the two OPEC series and the gap between them",
                     "US and Chinese import records by origin",
                     "reported ship-to-ship transfers and cargo counts",
                     "reported diluent imports", "reported upgrader outages"),
     "impact": "a supply variable of real size whose LEVEL is a function of a foreign licence "
               "and whose MEASUREMENT is a function of who is counting",
     "persistence": "the production level is persistent and slow-moving; the licensing state "
                    "changes in a single published day",
     "falsifier": "if the difference between the two OPEC series has no relationship to the "
                  "licensing state or to the mirror import records, then the gap is noise "
                  "rather than a measurement artefact of the regime, and AE-H is refuted",
     "notes": "NOTHING IN THIS PACK TOUCHES THIS ACTOR'S SYSTEMS. Every observable listed here "
              "is published by somebody else -- OPEC, the EIA, Chinese customs, the press"},
    {"name": "The United States Office of Foreign Assets Control as the supply switch",
     "jurisdiction": "ve",
     "holds": "the authority to permit or forbid transactions in Venezuelan oil by US persons, "
              "exercised through published general and specific licences",
     "forced_to": ("publish every licence, amendment and revocation, with a date and a number",
                   "publish interpretive FAQs that materially change what is permitted",
                   "operate through the Federal Register, which is machine-readable"),
     "when": "at each publication, inside the Washington business day",
     "information": ("the policy intention before the act is published",
                     "the compliance behaviour of the licensed parties"),
     "constraints": ("an administrative-law process that requires publication",
                     "a foreign policy that changes with administrations and with negotiations",
                     "the practical fact that third-country buyers are outside its reach"),
     "instruments": ("XBRUSD", "XTIUSD", "USDMXN", "USDCNH"),
     "counterparties": ("the licensed companies", "the Venezuelan state",
                        "the US Gulf refiners", "the Government of Trinidad and Tobago, whose "
                        "cross-border gas project needed one of these licences"),
     "observables": ("the published licence documents and their dates",
                     "the Federal Register notices", "the FAQ updates",
                     "the subsequent US import-by-origin record, which is the enforcement read"),
     "impact": "THE CLEANEST EVENT SERIES IN THE PACK: dated, published, unambiguous, and "
               "affecting a real share of heavy-sour supply. It is also the one event series "
               "here that a desk can lawfully read in full and in advance of its effects",
     "persistence": "a general licence lasts as long as it lasts; the six-month window of the "
                    "broadest one is itself a natural experiment with a start and an end date",
     "falsifier": "if US crude imports from Venezuela do not respond to licence changes within "
                  "the shipping lag, then the licences are not binding on the physical flow and "
                  "the whole Venezuelan supply mechanism is a narrative",
     "notes": "READING A PUBLISHED LICENCE IS NOT A SANCTIONED TRANSACTION. See "
              "`ACCESS_CONSTRAINTS`, where the distinction is stated in full and where the "
              "desk's own execution boundary -- broker symbols only -- is restated"},
    {"name": "The Banco Central de Venezuela and the parallel market",
     "jurisdiction": "ve",
     "holds": "an official reference rate, an intermittent publication record, and a currency "
              "that has been redenominated three times in fifteen years",
     "forced_to": ("intervene periodically to slow the official rate's depreciation",
                   "operate alongside a de facto dollarised retail economy it did not choose"),
     "when": "at each intervention and each publication, both irregular",
     "information": ("its own reserve position and the size of each intervention",
                     "the banking system's foreign-currency deposit base"),
     "constraints": ("reserves that are small relative to the demand",
                     "an economy that transacts in dollars regardless of policy",
                     "a publication record the institution itself broke"),
     "instruments": ("USDBRL", "USDMXN", "US500"),
     "counterparties": ("the domestic banks at the intervention",
                        "the parallel market, which sets the price people actually use",
                        "the importers with foreign-currency needs"),
     "observables": ("the official rate when it is published",
                     "the widely followed parallel references",
                     "the premium between them", "the Finance Observatory's independent CPI"),
     "impact": "NONE THAT IS EXECUTABLE, and the pack says so plainly: VES is absent from the "
               "broker, the series are broken by three redenominations, and the honest use of "
               "this actor is as a REGIME LABEL on the Venezuelan supply cells",
     "persistence": "the regime has persisted through three currencies",
     "falsifier": "there is no falsifiable executable claim here, which is why this actor mints "
                  "no cell of its own; if a Venezuelan monetary series ever becomes continuous "
                  "and published, that is the event that changes this row",
     "notes": "carried because the REDENOMINATION DATES are the era boundaries that invalidate "
              "any pooled Venezuelan study, and an era table needs the actor that made them"},
    {"name": "The licensed foreign operator in Venezuela",
     "jurisdiction": "ve",
     "holds": "a specific authorisation to produce and lift Venezuelan crude, granted, amended "
              "and withdrawn by a foreign treasury on published days",
     "forced_to": ("operate strictly inside the terms of a licence that can change",
                   "disclose its Venezuelan position to its own investors and regulators",
                   "wind down within a stated period when an authorisation lapses"),
     "when": "at each licence change and at each corporate disclosure",
     "information": ("the true production and lifting rate of its joint ventures",
                     "the state of the negotiation over its own authorisation"),
     "constraints": ("an authorisation that is not a property right",
                     "a counterparty with a debt position toward it",
                     "the wind-down clock when a licence lapses"),
     "instruments": ("XBRUSD", "XTIUSD"),
     "counterparties": ("the Venezuelan state and its joint ventures",
                        "the US Treasury as licensor",
                        "the US Gulf refineries that take the barrels"),
     "observables": ("the licence documents", "the US import-by-origin record",
                     "reported lifting counts", "corporate disclosures of Venezuelan volumes"),
     "impact": "a NAMED, SINGLE-COUNTERPARTY supply channel whose volume is reported by the "
               "importing country -- the cleanest way to see whether a licence became barrels",
     "persistence": "as long as the authorisation lasts, plus the wind-down period",
     "falsifier": "if the named channel's reported volumes do not move with its licence status, "
                  "then either the volumes are being replaced from elsewhere or the licence is "
                  "not the binding constraint; the US import line settles it",
     "notes": "THE TWO-LANE ORDER APPLIES: the operator is an actor, its shares are not an "
              "instrument, and no cell in this pack targets a single name"},
    {"name": "The PDV Holding and Citgo litigation estate",
     "jurisdiction": "ve",
     "holds": "the foreign refining assets against which a large creditor stack holds judgments, "
              "and a sale process administered by a court that publishes its calendar",
     "forced_to": ("litigate in public, on a published docket, with dated hearings and orders",
                   "run a sale process whose milestones are announced",
                   "respond to claims from bondholders, expropriated companies and arbitration "
                   "award holders"),
     "when": "at each docket entry, each hearing and each order",
     "information": ("the real bid landscape in the sale process",
                     "the settlement positions of the creditor classes"),
     "constraints": ("a court calendar it does not set",
                     "a sanctions regime that constrains who may bid and how",
                     "a claim stack larger than the asset"),
     "instruments": ("XTIUSD", "XBRUSD"),
     "counterparties": ("the creditor classes", "the court", "the Venezuelan state",
                        "the bidders for the refining assets"),
     "observables": ("the published docket", "the dated hearings and orders",
                     "the announced bid and sale milestones"),
     "impact": "the US GULF REFINING position of Venezuelan-owned assets is a real heavy-sour "
               "demand node, and its ownership is being decided on a PUBLISHED COURT CALENDAR "
               "with future dates on it",
     "persistence": "years, with dated procedural steps inside them",
     "falsifier": "if refining-asset ownership events have no measurable effect on the "
                  "heavy-sour differential or on US import patterns, the estate is a legal "
                  "story and not a market mechanism, and the pack should carry it only as "
                  "context",
     "notes": "a PUBLIC COURT RECORD is one of the lawful substitutes named in "
              "`NO_LAWFUL_GROUND` for Venezuelan corporate disclosure, and it has put more "
              "audited detail on the record than any Venezuelan institution has"},
    # ---------------------------------------------------------------- Suriname
    {"name": "Staatsolie, the Surinamese state oil company",
     "jurisdiction": "sr",
     "holds": "the state's participating interest in Block 58 and the onshore production and "
              "refining that predate it",
     "forced_to": ("finance its carried interest in a multi-billion-dollar development",
                   "publish an annual report in Dutch and English",
                   "deliver the state's side of a development whose first oil is a public target"),
     "when": "at the annual report, the project milestones and each financing",
     "information": ("the real construction progress on the development",
                     "its own financing capacity against the carry"),
     "constraints": ("a balance sheet far smaller than the development it is carried into",
                     "a sovereign that has just restructured its debt",
                     "an engineering schedule it does not control"),
     "instruments": ("XBRUSD", "XTIUSD"),
     "counterparties": ("the Block 58 operator and its partners",
                        "the lenders financing the carry",
                        "the Surinamese state as owner"),
     "observables": ("the annual report and its production and financing tables",
                     "project milestone announcements", "financing announcements"),
     "impact": "THE FORWARD CONTROL. A second deepwater ramp in the same geological trend, on a "
               "later clock, under a different fiscal regime -- which is exactly what the "
               "Guyanese series has never had to be tested against",
     "persistence": "the development is a multi-year object with dated milestones",
     "falsifier": "if Surinamese milestones move the barrel the way Guyanese ones do despite "
                  "being a fraction of the volume, the effect is NEWS about the basin rather "
                  "than SUPPLY, which would reinterpret the Guyanese result too",
     "notes": "the reason this pack is a province and not a Guyana pack: the control lives in a "
              "different country and it has to be carried to be used"},
    {"name": "The Centrale Bank van Suriname after the default",
     "jurisdiction": "sr",
     "holds": "a reserve-money target under an IMF programme, the FX auctions and a currency "
              "that was devalued and then floated",
     "forced_to": ("hit a monetary target on a published review calendar",
                   "auction foreign exchange rather than administer a rate",
                   "publish for the programme even where it did not publish before"),
     "when": "weekly at the auctions, monthly in the statistics, semi-annually at the reviews",
     "information": ("its own reserve position and the auction demand",
                     "the fiscal position feeding the monetary target"),
     "constraints": ("a programme with conditions and a published review calendar",
                     "an economy in which gold and oil are the only real export earners",
                     "a recent default that constrains external financing"),
     "instruments": ("USDBRL", "XAUUSD"),
     "counterparties": ("the IMF at the review", "the domestic banks at the auction",
                        "the gold exporters who are the main source of foreign exchange"),
     "observables": ("the weekly exchange rate and auction results",
                     "the reserve money series", "the published review dates and outcomes"),
     "impact": "a macro clock with PUBLISHED FUTURE DATES on it -- the review calendar -- which "
               "is unusual for a small frontier economy and is why the Surinamese conditioner "
               "is schedulable at all",
     "persistence": "the programme runs for years with reviews inside it",
     "falsifier": "if the review dates carry no measurable information for the gold or oil legs "
                  "once the commodity price is conditioned on, the calendar is administrative "
                  "and the conditioner is dropped",
     "notes": "carried in Dutch and Sranan in `TERMINOLOGY['AE-K']` because that is what the "
              "bank and the country publish and speak in"},
    {"name": "The Surinamese sovereign and its restructured creditors",
     "jurisdiction": "sr",
     "holds": "a restructured external debt with an OIL-LINKED value recovery instrument "
              "attached to future Block 58 royalties",
     "forced_to": ("service the restructured instruments on published dates",
                   "meet programme conditions to keep financing",
                   "deliver the oil development on which the recovery instrument depends"),
     "when": "at each coupon, each programme review and each project milestone",
     "information": ("the fiscal outturn before it is published",
                     "the project's real progress through its state shareholding"),
     "constraints": ("a recent default that prices its access to capital",
                     "a recovery instrument that explicitly ties creditor payoff to the barrel",
                     "a small revenue base until first oil"),
     "instruments": ("XBRUSD", "XAUUSD", "USDBRL"),
     "counterparties": ("the bondholder committee", "the Paris Club and bilateral creditors",
                        "the IMF", "Staatsolie and the Block 58 partners"),
     "observables": ("the restructuring terms and the recovery instrument's published triggers",
                     "coupon and observation dates", "the programme review outcomes"),
     "impact": "A SOVEREIGN CREDIT THAT IS AN EXPLICIT DERIVATIVE OF A DATED OIL DEVELOPMENT. "
               "That link is written into the instrument and published, which is rare enough "
               "that it is worth carrying even though the bond itself is not executable here",
     "persistence": "the instrument runs for years and its triggers are dated",
     "falsifier": "if Surinamese credit does not respond to Block 58 milestones, the recovery "
                  "instrument is not the binding link and the sovereign is trading on LatAm "
                  "risk appetite alone -- which the USDBRL control is there to detect",
     "notes": "carried as an INPUT: the credit leg conditions the Surinamese cells and is never "
              "itself a target, because no Surinamese instrument is quoted by this broker"},
    {"name": "The Surinamese gold mines and the small-scale sector",
     "jurisdiction": "sr",
     "holds": "two large-scale mines that dominate declared production and a small-scale sector "
              "that is comparably large and far less measured",
     "forced_to": ("declare and export through channels the state can see, or not",
                   "operate against a gold price they do not set",
                   "move mercury, fuel and people through a forested interior"),
     "when": "monthly at the export statistics and annually at the mine reports",
     "information": ("the real small-scale output and where it leaves the country",
                     "the interior fuel and mercury logistics"),
     "constraints": ("a porous forested border with two neighbours",
                     "a state that needs the foreign exchange and therefore the declarations",
                     "a price set in London"),
     "instruments": ("XAUUSD",),
     "counterparties": ("the state at the royalty and the export permit",
                        "the refiners abroad", "the informal buyers"),
     "observables": ("the export statistics", "the mine operators' production reports",
                     "the Comtrade mirror comparison", "the central bank's FX receipts"),
     "impact": "gold is the Surinamese economy's main foreign-exchange earner until first oil, "
               "so the gold series is also the FX series -- two mechanisms in one observable",
     "persistence": "structural; the small-scale sector does not go away",
     "falsifier": "if declared Surinamese gold exports and the central bank's foreign-exchange "
                  "receipts do not move together, the gold-is-the-FX claim is wrong and the two "
                  "must be modelled separately",
     "notes": "the same measurement problem as Guyana's backdam and for the same reason: gold "
              "walks across this province's borders, which is why every gold cell is WEAK"},
    # ---------------------------------------------------------------- the province
    {"name": "The Caribbean tanker, lightering and bunkering plane",
     "jurisdiction": "province",
     "holds": "the vessels, the anchorages and the ship-to-ship transfer capability through "
              "which every barrel and every cargo of this province physically leaves it",
     "forced_to": ("fix vessels against a freight market it does not control",
                   "work around real draft restrictions at river ports and offshore anchorages",
                   "declare arrivals and departures to port authorities that publish notices"),
     "when": "continuously; fixtures and departures are reported within days",
     "information": ("the real loading programme weeks ahead of any statistic",
                     "where a cargo is actually going, which is often not its declared "
                     "destination"),
     "constraints": ("draft limits on the Demerara and Berbice rivers that cap vessel size",
                     "a freight market whose rates move with global tonne-miles",
                     "insurance and flag constraints on sanctioned trades"),
     "instruments": ("XBRUSD", "XTIUSD", "XNGUSD", "USDCNH"),
     "counterparties": ("the producers and the state marketing arms",
                        "the refiners at the destination", "the port authorities",
                        "the shipowners and charterers"),
     "observables": ("reported loadings and departures",
                     "reported ship-to-ship transfers",
                     "port authority arrival notices",
                     "freight rate reporting on the Caribbean-to-Gulf and Caribbean-to-Asia runs"),
     "impact": "THE PHYSICAL CONFIRMATION LAYER. A licence is an authorisation and a production "
               "figure is a claim; a loaded tanker is a fact, and in this province it is often "
               "the FIRST fact available",
     "persistence": "a voyage is weeks; a route change is a regime",
     "falsifier": "if reported cargo counts add nothing over the EIA import-by-origin series at "
                  "the same horizon, the tanker layer is a slower version of a published "
                  "statistic and should be dropped in its favour",
     "notes": "READ AS PUBLIC REPORTING. The desk reads the press and the port notices; it does "
              "not acquire a commercial vessel feed and does not need one to date an event"},
    {"name": "The ICJ and the Argyle guarantors in the Essequibo controversy",
     "jurisdiction": "province",
     "holds": "the jurisdiction over the validity of the 1899 award, the provisional-measures "
               "power, and -- on the guarantors' side -- the political commitments of a signed "
               "declaration",
     "forced_to": ("publish every order and fix every deadline on a public calendar",
                   "hold hearings that are announced in advance",
                   "respond to incidents with dated statements"),
     "when": "at each filing deadline, each hearing and each order, all scheduled in advance",
     "information": ("the procedural posture of the case ahead of each step",
                     "the filing deadlines fixed by the previous order",
                     "the parties' own public statements before each hearing"),
     "constraints": ("a court that moves at the pace of international litigation",
                     "guarantors with their own interests, including a neighbour with its own "
                     "equatorial-margin ambitions",
                     "no enforcement mechanism of its own"),
     "instruments": ("XBRUSD", "XTIUSD", "XAUUSD", "US500"),
     "counterparties": ("the two states party to the case",
                        "the regional guarantors who witnessed the declaration",
                        "the operators whose licences sit in the affected waters"),
     "observables": ("the published docket and its future dates",
                     "the orders and press releases",
                     "the dated declarations and the reported incidents"),
     "impact": "a POLITICAL RISK SERIES WITH FUTURE DATES ON IT. Most political risk is only "
               "datable after the fact; a court calendar is datable before it, which is what "
               "makes AE-L testable as an event study rather than as a narrative",
     "persistence": "the case is a multi-year object; an incident is days",
     "falsifier": "if scheduled ICJ dates show no abnormal behaviour in the barrel relative to "
                  "matched windows, then the dispute is priced as a tail nobody trades and the "
                  "domain mints conditioners rather than cells",
     "notes": "the incidents are PRESS_REPORTED and the court steps are COURT_RECORD, and the "
              "two confidence labels are kept apart in `ESSEQUIBO_EVENTS` for that reason"},
)

# --------------------------------------------------------------------------- domains
#: THIRTEEN DOMAINS, AND EVERY JURISDICTION OWNS AT LEAST TWO OF ITS OWN: Guyana A-B-C, Trinidad
#: D-E-F, Venezuela G-H-I, Suriname J-K, and the province itself L-M. Each names its research
#: objects, the STATES it conditions on (these are the `condition` half of every cell `cells()`
#: mints), the executable instruments it may touch and at least two negative controls -- without
#: which an effect cannot be told apart from the desk's own sampling.
DOMAINS: tuple[dict[str, Any], ...] = (
    {"id": "AE-A", "title": "The Stabroek FPSO ramp as a dated, published, per-vessel supply "
                            "schedule (gy)",
     "objects": ("every row of `FPSO_SCHEDULE`: the vessel, its sanction date, its nameplate "
                 "capacity and its first-oil date",
                 "the capacity STEPS that `ramp_steps()` produces",
                 "the announcement-to-first-oil window for each vessel",
                 "the published non-OPEC supply forecasts the step was supposed to be in"),
     "conditions": ("the vessel: each FPSO is its own named step, never a pooled ramp",
                    "the event class: final investment decision, vessel sail-away, or first oil",
                    "whether the step landed in a month with a published non-OPEC supply "
                    "forecast revision",
                    "the OPEC spare-capacity state at the step, which decides whether a "
                    "non-OPEC barrel is absorbed or priced"),
     "instruments": ("XBRUSD", "XTIUSD"),
     "controls": ("the SURINAMESE schedule (AE-J), which is the same geology on a later clock "
                  "-- the only true forward control this series has",
                  "matched windows with no capacity step and the same OPEC spare-capacity state",
                  "the announced-but-not-yet-delivered steps, which test whether the market "
                  "prices the announcement or the barrel"),
     "notes": "THE PACK'S PRIMARY DOMAIN. Nameplate is not output: `sanctioned_capacity_on` "
              "returns nameplate only and the debottlenecking uplift is a declared parameter "
              "(see DEBOTTLENECK_NOTE), never a constant folded silently into the series"},
    {"id": "AE-B", "title": "The Natural Resource Fund and the profit-oil formula: a sovereign "
                            "revenue function that is published arithmetic (gy)",
     "objects": ("the monthly NRF receipts and the fund balance",
                 "the 75% cost-recovery ceiling and whether it BOUND in a given month",
                 "the cargo liftings and the entitlement marketing",
                 "the statutory withdrawal ceiling in the Appropriation Act"),
     "conditions": ("the number of entitlement cargoes lifted in the month: none, one, or more "
                    "than one -- a lumpy series that a monthly average destroys",
                    "whether the cost-recovery ceiling bound that month under `government_take`",
                    "the fiscal-year phase: the January budget, the mid-year report, or neither"),
     "instruments": ("XBRUSD", "XTIUSD", "USDBRL"),
     "controls": ("the published formula itself: the residual after `government_take` is "
                  "applied to lagged Brent is the only part that can carry new information",
                  "Trinidad's fiscal calendar (AE-F), a second oil sovereign on a different "
                  "fiscal year, which separates 'oil fiscal' from 'this fiscal year'",
                  "months with a Brent move and no cargo lifted"),
     "notes": "the lumpiness is the mechanism: receipts arrive cargo by cargo and a study that "
              "smooths them is testing its own filter"},
    {"id": "AE-C", "title": "Guyanese gold, bauxite and sugar: the non-oil export economy as "
                            "the oil boom's own control group (gy)",
     "objects": ("the Gold Board declaration series against the Comtrade mirror",
                 "the bauxite export volumes and the river-draft constraint on them",
                 "the sugar export volumes and the quota arrangements",
                 "the Bureau of Statistics oil and non-oil GDP split"),
     "conditions": ("the commodity: gold, bauxite into aluminium, or sugar, each its own cell",
                    "whether declared production and the mirror import record reconcile in "
                    "that quarter -- the leakage state",
                    "the oil-era phase: before first oil on 2019-12-20, or after it"),
     "instruments": ("XAUUSD", "XALUSD", "SUGAR", "XCUUSD"),
     "controls": ("XCUUSD as the BASE-METAL DEMAND CONTROL: a bauxite-to-aluminium move that "
                  "also moves copper is a global demand event and not a Guyanese supply one",
                  "the Surinamese gold series (AE-K), the same geology and the same leakage "
                  "problem in a different sovereign",
                  "the pre-2019 Guyanese export series as the untreated period"),
     "notes": "EVERY GOLD CELL FROM THIS DOMAIN IS LABELLED WEAK by construction: declared "
              "output responds to the declaration incentive as much as to geology"},
    {"id": "AE-D", "title": "Atlantic LNG train utilisation and the structural Trinidadian gas "
                            "decline (tt)",
     "objects": ("the ministry's field-level monthly gas production",
                 "LNG output and the announced turnarounds and outages",
                 "the cross-border licence state for the Venezuelan gas field",
                 "the national aggregator's allocation between LNG, ammonia and methanol -- "
                 "DECLARED UNMEASURED and never inferred from an output total"),
     "conditions": ("whether a train turnaround or an unplanned outage was announced in the "
                    "window",
                    "the field-level decline state: faster or slower than its own trailing rate",
                    "the US SUPPLY AND WEATHER CONTROL STATE -- US storage against its "
                    "five-year band and the heating-degree-day anomaly -- without which XNGUSD "
                    "is measuring America and not Trinidad",
                    "whether the cross-border gas licence was in force, from `sanctions_state`"),
     "instruments": ("XNGUSD", "XBRUSD"),
     "controls": ("US storage, US production and weather, which drive XNGUSD and have nothing "
                  "to do with Trinidad -- this is the control the domain exists to impose",
                  "European gas-driven LNG demand episodes with no Trinidadian event",
                  "matched windows with a Trinidadian turnaround already anticipated because it "
                  "was announced months ahead"),
     "notes": "HENRY HUB IS NOT ATLANTIC LNG. A Trinidadian outage tightens the Atlantic basin "
              "and can LOOSEN Henry Hub by freeing US cargoes, so the sign is not assumed and "
              "the US control is mandatory on every cell this domain mints"},
    {"id": "AE-E", "title": "Point Lisas ammonia and methanol: Trinidadian gas into Atlantic "
                            "nitrogen cost and the acreage decision (tt)",
     "objects": ("announced plant idlings, restarts and turnarounds at the petrochemical estate",
                 "the ministry's monthly ammonia and methanol output",
                 "the published Atlantic nitrogen references (registered, not machine-read)",
                 "the northern-hemisphere planting calendar and the acreage reports"),
     "conditions": ("whether an ammonia or methanol idling was announced in the window",
                    "the crop-calendar phase: inside the northern planting and input-purchase "
                    "window, or outside it",
                    "whether a EUROPEAN gas-driven ammonia curtailment was running at the same "
                    "time -- the control that decides whose nitrogen shock it is"),
     "instruments": ("CORN", "WHEAT", "SOYBEAN", "XNGUSD"),
     "controls": ("the European curtailment episodes, which move the same nitrogen price with "
                  "NO Trinidadian event and are the cleanest available placebo",
                  "the USDA report calendar, which moves the crops for reasons that have "
                  "nothing to do with fertiliser cost",
                  "SOYBEAN as the low-nitrogen crop: a legume fixes its own nitrogen, so a "
                  "nitrogen shock should move corn and wheat MORE than soybeans, and a common "
                  "move across all three is a macro event wearing a fertiliser hat"),
     "notes": "THE SOYBEAN CONTROL IS THE SHARP ONE and it is the reason SOYBEAN is in this "
              "domain at all. The price leg is UNMEASURED because the assessments forbid "
              "machine extraction, so the chain is tested on PHYSICAL output volume"},
    {"id": "AE-F", "title": "The rationed Trinidadian dollar and a budget written on an assumed "
                            "oil price (tt)",
     "objects": ("the central bank's published FX sales to the authorised dealers",
                 "the reported shortage episodes, card limits and waiting times",
                 "the budget statement and its stated oil and gas price assumption",
                 "the sovereign fund's drawdowns"),
     "conditions": ("the rationing state: a reported shortage episode in the window, or not",
                    "the fiscal-year phase: the late-September budget window, the mid-year "
                    "review, or neither -- and TRINIDAD'S YEAR IS NOT THE CALENDAR YEAR",
                    "whether realised energy prices ran above or below the budget's stated "
                    "assumption in that fiscal year"),
     "instruments": ("USDBRL", "USDMXN", "US500"),
     "controls": ("Guyana over the same windows (AE-B): a second small oil sovereign with a "
                  "stabilised currency and NO rationing, which separates 'oil sovereign' from "
                  "'rationed currency'",
                  "the regional EM legs on matched risk days with no Trinidadian event",
                  "calendar-year fiscal sovereigns, which is every other pack in this command"),
     "notes": "TTD is absent from the broker, so this domain is a CONDITIONER: it says when the "
              "regional legs should be read as carrying Trinidad and when they should not"},
    {"id": "AE-G", "title": "The OFAC licence calendar as the Venezuelan supply switch (ve)",
     "objects": ("every dated act in `SANCTIONS_ACTS` and the regime `sanctions_state` returns",
                 "the US import-by-origin record as the enforcement read",
                 "the heavy-sour differential and the Mexican competing grade",
                 "reported cargo counts and ship-to-ship transfers"),
     "conditions": ("the regime in force: each label in `SANCTIONS_REGIMES` is its own state, "
                    "and the six-month GL44 window is a natural experiment with two dates",
                    "the act class: a grant, an amendment, a revocation, or a lapse",
                    "whether US imports from Venezuela actually responded inside the shipping "
                    "lag -- the difference between an authorisation and a barrel",
                    "the heavy-sour control state: Mexican export volumes in the same month"),
     "instruments": ("XBRUSD", "XTIUSD", "USDMXN", "USDCNH"),
     "controls": ("Mexican Maya, the competing heavy-sour grade, whose volumes move for "
                  "entirely Mexican reasons and are the natural placebo",
                  "OPEC production changes in the same month with no Venezuelan act",
                  "the US logistics control: Cushing stocks and US crude inventories, without "
                  "which the Brent-WTI leg is measuring a pipeline"),
     "notes": "NOTHING HERE TOUCHES A SANCTIONED PARTY'S SYSTEMS. Every object is a published "
              "administrative act or a foreign government's own statistic; see "
              "`ACCESS_CONSTRAINTS`"},
    {"id": "AE-H", "title": "The OPEC two-series disagreement as a measurable observable (ve)",
     "objects": ("the direct-communication and secondary-source Venezuelan production lines",
                 "the gap between them, computed by `opec_gap()`",
                 "the revision behaviour of each series across MOMR vintages"),
     "conditions": ("the sign of the gap: the member reporting above, below, or in line with "
                    "the independent estimate",
                    "whether the gap widened or narrowed against its own trailing dispersion",
                    "the licensing regime in force that month, which is the reason a member "
                    "might report differently from an independent counter"),
     "instruments": ("XBRUSD", "XTIUSD"),
     "controls": ("the same two-series gap for OTHER OPEC members, which is the placebo: if "
                  "every member's gap moves together it is a secretariat methodology change "
                  "and not a Venezuelan fact",
                  "the mirror import records, which are a third independent count",
                  "months with a licence change and no gap change"),
     "notes": "the SECONDARY series is the one the secretariat uses, so a supply cell is built "
              "on secondary sources and the gap is a CONDITIONER, never the dependent variable"},
    {"id": "AE-I", "title": "Hyperinflation, three redenominations and dollarisation as ERA "
                            "BOUNDARIES that invalidate pooling (ve)",
     "objects": ("the three redenominations of 2008, 2018 and 2021",
                 "the official and parallel references and the premium between them",
                 "the Finance Observatory's independently computed CPI",
                 "the de facto dollarisation of retail transactions"),
     "conditions": ("the currency era: bolivar fuerte, bolivar soberano, or bolivar digital",
                    "whether the estimation window CROSSES a redenomination date, in which case "
                    "the cell is refused rather than adjusted",
                    "the regional risk state read off the EM legs and US500"),
     "instruments": ("USDBRL", "USDMXN", "US500"),
     "controls": ("the regional EM legs on matched risk days, which carry LatAm risk and no "
                  "Venezuelan monetary content at all",
                  "the other three jurisdictions of this province over the same windows",
                  "the pre-2017 period, before the sanctions regime confounds everything"),
     "notes": "THIS DOMAIN MOSTLY MINTS REFUSALS, AND THAT IS ITS JOB. Its output is the era "
              "label that tells every other Venezuelan cell which windows it may not pool"},
    {"id": "AE-J", "title": "Block 58 and GranMorgu: the next dated ramp and the Guyanese "
                            "series' forward control (sr)",
     "objects": ("the Block 58 sanction date and the published first-oil target",
                 "the construction and contract-award milestones",
                 "Staatsolie's carried interest and its financing",
                 "the same-trend geology that makes this a control and not a coincidence"),
     "conditions": ("the milestone class: final investment decision, contract award, "
                    "construction milestone, or a move in the published first-oil target",
                    "whether a GUYANESE step fell in the same window -- the joint-basin cell",
                    "the schedule state: on the published target, or slipped against it"),
     "instruments": ("XBRUSD", "XTIUSD"),
     "controls": ("the Guyanese steps in AE-A, which are the same basin with far larger volume: "
                  "if a small Surinamese milestone moves the barrel as much as a large Guyanese "
                  "one, the effect is NEWS about the basin and not SUPPLY",
                  "matched windows with no milestone in either country",
                  "other non-OPEC sanction announcements worldwide in the same window"),
     "notes": "the reason this is a PROVINCE pack: the control for the Guyanese ramp lives in "
              "another country and cannot be carried without carrying that country"},
    {"id": "AE-K", "title": "The Surinamese default, the oil-linked restructuring and the gold "
                            "that pays for everything until first oil (sr)",
     "objects": ("the 2021 default and the 2023-2024 bondholder settlement",
                 "the value recovery instrument tied to Block 58 royalties",
                 "the IMF programme reviews and their published calendar",
                 "declared gold exports against the central bank's foreign-exchange receipts"),
     "conditions": ("the credit phase: pre-default, default, restructuring, or post-settlement",
                    "whether a published IMF review date fell inside the window",
                    "whether declared gold exports and the central bank's FX receipts moved "
                    "together that quarter -- the test of the gold-is-the-FX claim"),
     "instruments": ("XAUUSD", "USDBRL"),
     "controls": ("Guyanese gold over the same windows (AE-C), which shares the geology and the "
                  "leakage problem and has NO sovereign credit event attached",
                  "USDBRL as the LatAm risk-appetite leg, which separates 'Suriname' from "
                  "'frontier credit had a good week'",
                  "review dates in other IMF programmes with no gold or oil content"),
     "notes": "the sovereign credit is an INPUT here and never a target: no Surinamese "
              "instrument is quoted by this broker"},
    {"id": "AE-L", "title": "The Essequibo controversy as a dated territorial-risk series with "
                            "FUTURE DATES on it (gy and ve)",
     "objects": ("every row of `ESSEQUIBO_EVENTS`, split by confidence label",
                 "the ICJ's own published procedural calendar and its forward deadlines",
                 "the Argyle Declaration and the guarantors' subsequent statements",
                 "the producing capacity sitting in the affected waters on each date"),
     "conditions": ("the event class: a COURT_RECORD procedural step, or a PRESS_REPORTED "
                    "incident -- two different objects with two different confidence labels",
                    "whether the date was SCHEDULED IN ADVANCE on the court calendar or arrived "
                    "as a surprise, which is the difference between an event study and a shock",
                    "the global risk state read off US500, because a tail event in a risk-off "
                    "week is not the same observation",
                    "the capacity at risk on the date, from `sanctioned_capacity_on` -- the "
                    "stake has grown by a factor of five since the case was filed"),
     "instruments": ("XBRUSD", "XTIUSD", "XAUUSD", "US500"),
     "controls": ("matched windows on the court calendar where nothing was decided",
                  "other territorial disputes with scheduled hearings and no oil",
                  "days with a comparable global risk move and no Essequibo event"),
     "notes": "MOST POLITICAL RISK IS DATABLE ONLY AFTER THE FACT. A court calendar is datable "
              "before it, which is what makes this domain an event study rather than a story"},
    {"id": "AE-M", "title": "The Caribbean tanker, lightering and bunkering plane: the physical "
                            "gate every barrel in the province crosses (province)",
     "objects": ("reported loadings, departures and ship-to-ship transfers",
                 "the port authority arrival notices and the anchorage and draft constraints",
                 "the Caribbean-to-Gulf and Caribbean-to-Asia freight legs",
                 "the LNG cargo departures from the liquefaction terminal"),
     "conditions": ("the route: Caribbean into the US Gulf, Caribbean into Asia, or Atlantic LNG "
                    "-- three different economics on one physical plane",
                    "whether a ship-to-ship transfer surge was reported in the window, which is "
                    "the signature of a sanctioned trade rerouting",
                    "the draft and anchorage constraint state at the loading point, which caps "
                    "vessel size and therefore the cargo economics"),
     "instruments": ("XBRUSD", "XTIUSD", "XNGUSD", "USDCNH"),
     "controls": ("the EIA import-by-origin series at the same horizon: if the tanker layer "
                  "adds nothing over it, the tanker layer is a slower published statistic",
                  "global freight rates on unrelated routes, which separate 'Caribbean' from "
                  "'tonne-miles got expensive everywhere'",
                  "windows with a route change and no production change"),
     "notes": "READ AS PUBLIC REPORTING ONLY. Every row here comes from the press and from port "
              "authority notices; no commercial vessel feed is acquired and none is needed to "
              "date an event"},
)

# --------------------------------------------------------------------------- miners
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    {"name": "ae_ramp_schedule", "domain_ids": ("AE-A", "AE-J"), "kind": "event",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.atlantic_energy.pack:ramp_schedule",
     "needs": ("FPSO_SCHEDULE and `ramp_steps()`", "XBRUSD, XTIUSD H1 bars",
               "the published non-OPEC supply forecast vintages"),
     "notes": "THE PACK'S PRIMARY MINER: the dated capacity steps of both jurisdictions, with "
              "the Surinamese schedule carried as the Guyanese series' forward control"},
    {"name": "ae_fiscal_formula", "domain_ids": ("AE-B", "AE-F"), "kind": "macro",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.atlantic_energy.pack:fiscal_formula",
     "needs": ("PSA_TERMS and `government_take()`", "the NRF monthly receipt series",
               "XBRUSD D1 bars", "the Trinidadian budget price assumption"),
     "notes": "computes the published sovereign take from the price and reports the RESIDUAL, "
              "which is the only part of the receipt series that can carry new information"},
    {"name": "ae_licence_calendar", "domain_ids": ("AE-G", "AE-H"), "kind": "event",
     "cadence_s": 43200.0, "steerable": True, "wired": False,
     "entry": "countries.atlantic_energy.pack:licence_calendar",
     "needs": ("SANCTIONS_ACTS and `sanctions_state()`",
               "the EIA import-by-origin series", "XBRUSD, XTIUSD H1 bars"),
     "notes": "the dated administrative acts with the enforcement read beside them; every row "
              "is a published document and the two PRESS_REPORTED rows say so"},
    {"name": "ae_gas_chain", "domain_ids": ("AE-D", "AE-E"), "kind": "transfer",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.atlantic_energy.pack:gas_chain",
     "needs": ("TRINIDAD_GAS_FACTS and the ministry field-level series",
               "CORN, WHEAT, SOYBEAN, XNGUSD D1 bars",
               "the US storage and heating-degree-day control", "the European curtailment dates"),
     "notes": "carries the Henry Hub basis warning as an UNMEASURED row on every pass: the gas "
              "leg may not be compiled without the US supply-and-weather control attached"},
    {"name": "ae_territorial_risk", "domain_ids": ("AE-L",), "kind": "event",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.atlantic_energy.pack:territorial_risk",
     "needs": ("ESSEQUIBO_EVENTS and the ICJ forward calendar",
               "XBRUSD, XTIUSD, XAUUSD, US500 H1 bars", "`sanctioned_capacity_on()`"),
     "notes": "splits COURT_RECORD scheduled steps from PRESS_REPORTED incidents, because the "
              "first is an event study and the second is a shock"},
    {"name": "ae_province_calendar", "domain_ids": ("AE-C", "AE-K", "AE-M"), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.atlantic_energy.pack:province_calendar",
     "needs": ("`province_holidays`, `shared_closures`, `carnival_shutdown`",
               "XAUUSD, XBRUSD D1 bars"),
     "notes": "four calendars that do not agree; the SHARED closures are a liquidity regime and "
              "the single-country ones are natural controls"},
    {"name": "ae_currency_regimes", "domain_ids": ("AE-I", "AE-F"), "kind": "macro",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.atlantic_energy.pack:currency_regimes",
     "needs": ("CURRENCIES and POLICY_ERAS", "`parallel_premium()`",
               "USDBRL, USDMXN, US500 D1 bars"),
     "notes": "mostly mints REFUSALS: its output is the era label that tells the Venezuelan "
              "cells which windows they may not pool across"},
    {"name": "ae_transmission_seeds",
     "domain_ids": ("AE-A", "AE-B", "AE-D", "AE-E", "AE-G", "AE-J", "AE-L", "AE-M"),
     "kind": "transfer", "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.atlantic_energy.pack:transmission_seeds",
     "needs": ("TRANSMISSION_EDGES_SEED", "INTERACTIONS"),
     "notes": "the pack's map as HYPOTHESIS discoveries, deduplicated by the registry"},
)
MINER_DOMAINS: dict[str, tuple[str, ...]] = {
    "central_bank_surprise": ("AE-F",), "release_surprise": ("AE-A", "AE-D", "AE-H"),
    "calendar_settlement": ("AE-B", "AE-F"), "holiday_liquidity": ("AE-C", "AE-M"),
    "positioning": ("AE-A", "AE-G"), "carry_funding": ("AE-F", "AE-I"),
    "corporate_flow": ("AE-A", "AE-D", "AE-E"), "institutional_flow": ("AE-B", "AE-K"),
    "equity_mechanics": (), "derivatives_expiry": ("AE-G",),
    "failure": ("AE-G", "AE-L", "AE-D"), "residual": ("AE-H", "AE-I"),
    "transfer": ("AE-E", "AE-J", "AE-M"), "scouts": ("AE-C", "AE-M"),
    "session_microstructure": ("AE-M",),
}

# --------------------------------------------------------------------------- transmission
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    {"id": "AE-E1", "source": "A dated Guyanese FPSO first-oil step in `FPSO_SCHEDULE`",
     "target": "XBRUSD", "targets": ("XBRUSD", "XTIUSD"), "to_country": "global", "sign": "-",
     "mechanism": "a named vessel with a published nameplate capacity starts producing on a "
                  "known date, adding a permanent non-OPEC supply step. The step is announced "
                  "years ahead, so the tradable question is whether the anticipation is "
                  "COMPLETE -- and the cumulative series has gone from zero to roughly 650,000 "
                  "b/d in six years, which is a real share of the annual balance",
     "horizon": "0 to 20 sessions around the step", "horizon_class": "multi_day",
     "lag_days": 0.0,
     "actor": "the Stabroek co-venturers and the Government of Guyana",
     "constraint": "an engineering schedule that cannot be hurried and a nameplate that is "
                   "published in advance",
     "flow": "a permanent addition to seaborne medium-sweet supply",
     "condition": "the OPEC spare-capacity state at the step: a non-OPEC barrel into tight "
                  "spare capacity is a different object from one into slack",
     "control": "the SURINAMESE schedule on a later clock; matched windows with no step and the "
                "same spare-capacity state",
     "falsifier": "capacity steps show no abnormal behaviour once the published non-OPEC supply "
                  "forecasts and the OPEC spare-capacity state are conditioned on, which would "
                  "mean the ramp is fully priced at announcement",
     "evidence": "HYPOTHESIS"},
    {"id": "AE-E2", "source": "The Guyanese NRF monthly receipt and the cargo-lifting count",
     "target": "USDBRL", "targets": ("USDBRL", "XBRUSD"), "to_country": "gy", "sign": "+",
     "mechanism": "the sovereign's oil income is computable from the published formula, so the "
                  "RESIDUAL after `government_take()` is applied to lagged Brent is the only "
                  "part that can carry information -- an audit outcome, a cost-recovery dispute "
                  "or a marketing result. Lumpiness matters: receipts arrive cargo by cargo",
     "horizon": "the publication day plus 10 sessions", "horizon_class": "multi_day",
     "lag_days": 20.0,
     "actor": "the Government of Guyana and the Ministry of Finance",
     "constraint": "the 75% cost-recovery ceiling and the statutory withdrawal rule",
     "flow": "sovereign receipts, sterilised into a fund rather than converted into the domestic "
             "market",
     "condition": "whether the cost-recovery ceiling bound that month",
     "control": "the published formula itself applied to lagged Brent; Trinidad's fiscal "
                "calendar as a second oil sovereign on a different fiscal year",
     "falsifier": "NRF receipts are fully explained by lagged Brent times a constant, so the "
                  "fiscal series adds nothing to the price",
     "evidence": "HYPOTHESIS"},
    {"id": "AE-E3", "source": "An announced Atlantic LNG train outage or turnaround",
     "target": "XNGUSD", "targets": ("XNGUSD", "XBRUSD"), "to_country": "global", "sign": "?",
     "mechanism": "a train outage removes Atlantic-basin liquefaction and tightens the LNG "
                  "market -- AND CAN LOOSEN HENRY HUB by freeing US cargoes for the same "
                  "buyers. The sign is genuinely ambiguous and the edge declares it so rather "
                  "than assuming the convenient direction",
     "horizon": "0 to 15 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "the liquefaction complex and the upstream gas producers",
     "constraint": "a declining upstream resource base and a short molecule allocated between "
                   "LNG, ammonia, methanol and power",
     "flow": "Atlantic-basin liquefaction capacity withdrawn from the market",
     "condition": "the US storage state against its five-year band and the heating-degree-day "
                  "anomaly, WITHOUT WHICH THE CELL IS MEASURING AMERICA",
     "control": "US supply, US storage and weather; European demand episodes with no "
                "Trinidadian event; announced turnarounds, which were already priced",
     "falsifier": "Trinidadian LNG output changes have no measurable effect on XNGUSD once US "
                  "production, storage and weather are conditioned on -- in which case the gas "
                  "leg routes only through the ammonia chain",
     "evidence": "HYPOTHESIS"},
    {"id": "AE-E4", "source": "An announced ammonia or methanol plant idling at Point Lisas",
     "target": "CORN", "targets": ("CORN", "WHEAT", "SOYBEAN"), "to_country": "global",
     "sign": "+",
     "mechanism": "Point Lisas is one of the largest export ammonia complexes in the world. A "
                  "gas-driven idling removes Atlantic-basin nitrogen supply, raising the "
                  "nitrogen cost that enters the acreage and margin decision for the "
                  "nitrogen-hungry crops at the planting window",
     "horizon": "20 to 60 sessions", "horizon_class": "multi_day", "lag_days": 15.0,
     "actor": "the Point Lisas producers and the national gas aggregator",
     "constraint": "a short molecule and plants that are expensive to stop and restart",
     "flow": "export ammonia tonnes withdrawn from the Atlantic basin",
     "condition": "whether the window falls inside the northern-hemisphere planting and "
                  "input-purchase season",
     "control": "SOYBEAN, which fixes its own nitrogen: a nitrogen shock should move corn and "
                "wheat MORE than soybeans, and a common move across all three is a macro event "
                "wearing a fertiliser hat. Plus the European gas-driven curtailments and the "
                "USDA report calendar",
     "falsifier": "Trinidadian idlings move all three crops identically, or move none of them "
                  "once European curtailments are conditioned on",
     "evidence": "HYPOTHESIS"},
    {"id": "AE-E5", "source": "A published OFAC licence grant, amendment, revocation or lapse",
     "target": "XTIUSD", "targets": ("XTIUSD", "XBRUSD", "USDMXN"), "to_country": "global",
     "sign": "?",
     "mechanism": "the licensing regime decides who may lawfully buy Venezuelan crude, which "
                  "decides whether the barrels go to the US Gulf at a narrow discount or to "
                  "Asia at a wide one. The volume barely changes; the DESTINATION and the "
                  "DISCOUNT do, and the US Gulf heavy-sour balance moves with them",
     "horizon": "0 to 30 sessions", "horizon_class": "multi_day", "lag_days": 2.0,
     "actor": "the US Treasury as licensor and the licensed operators",
     "constraint": "an administrative process that requires publication, and a shipping lag "
                   "between an authorisation and a delivered barrel",
     "flow": "heavy-sour crude redirected between the US Gulf and Asia",
     "condition": "the regime label from `sanctions_state` and the act class",
     "control": "Mexican Maya volumes as the competing heavy-sour grade; US crude stocks and "
                "Cushing, without which the Brent-WTI leg is measuring a pipeline",
     "falsifier": "US imports from Venezuela do not respond to licence changes within the "
                  "shipping lag, which would mean the licences are not binding on the flow",
     "evidence": "HYPOTHESIS"},
    {"id": "AE-E6", "source": "The OPEC direct-versus-secondary gap for Venezuela",
     "target": "XBRUSD", "targets": ("XBRUSD", "XTIUSD"), "to_country": "global", "sign": "?",
     "mechanism": "when a member reports materially above the secretariat's independent "
                  "estimate, the difference is information about the reporting incentive rather "
                  "than about the geology -- and the incentive changes with the licensing "
                  "regime. The gap is therefore a CONDITIONER on every Venezuelan supply claim",
     "horizon": "the MOMR publication day plus 10 sessions", "horizon_class": "multi_day",
     "lag_days": 14.0,
     "actor": "the state oil company as reporter and the OPEC secretariat as counter",
     "constraint": "a reporting relationship with no audit and an independent estimate with no "
                   "access",
     "flow": "no physical flow: this is a MEASUREMENT edge and it is labelled as one",
     "condition": "the sign and the direction of change of the gap",
     "control": "the same two-series gap for other OPEC members, which is the placebo for a "
                "secretariat methodology change; the mirror import records as a third count",
     "falsifier": "the gap has no relationship to the licensing state or to the mirror records, "
                  "making it noise rather than a regime artefact",
     "evidence": "HYPOTHESIS"},
    {"id": "AE-E7", "source": "A scheduled ICJ step or a reported incident in the Essequibo "
                              "controversy",
     "target": "XBRUSD", "targets": ("XBRUSD", "US500", "XAUUSD"), "to_country": "global",
     "sign": "+",
     "mechanism": "the disputed territory contains the waters in which the fastest-growing "
                  "non-OPEC supply on earth is produced, and the stake has grown fivefold since "
                  "the case was filed. A scheduled court step is an anticipated date; a naval "
                  "incident is not, and the two must be tested separately",
     "horizon": "intraday to 5 sessions", "horizon_class": "intraday",
     "lag_days": 0.0,
     "actor": "the two states, the court and the regional guarantors",
     "constraint": "a court with no enforcement mechanism and guarantors with their own "
                   "interests",
     "flow": "a risk premium on the barrels produced in the affected waters",
     "condition": "whether the date was SCHEDULED IN ADVANCE or arrived as a surprise",
     "control": "matched windows on the court calendar where nothing was decided; days with a "
                "comparable global risk move and no Essequibo event; other territorial disputes "
                "with scheduled hearings and no oil",
     "falsifier": "scheduled ICJ dates show no abnormal behaviour relative to matched windows, "
                  "which would mean the dispute is a tail nobody trades",
     "evidence": "HYPOTHESIS"},
    {"id": "AE-E8", "source": "A Surinamese Block 58 milestone against the Guyanese schedule",
     "target": "XBRUSD", "targets": ("XBRUSD", "XTIUSD"), "to_country": "global", "sign": "-",
     "mechanism": "the same geological trend, the same operator community, a later clock and a "
                  "different sovereign. If a small Surinamese milestone moves the barrel as "
                  "much as a large Guyanese one, then the market is trading NEWS ABOUT THE "
                  "BASIN rather than supply -- which would reinterpret the Guyanese result too",
     "horizon": "0 to 15 sessions", "horizon_class": "multi_day", "lag_days": 0.0,
     "actor": "Staatsolie and the Block 58 partners",
     "constraint": "a state company carried into a development far larger than its balance sheet",
     "flow": "an expectation of future supply, not present supply",
     "condition": "whether a Guyanese step fell in the same window",
     "control": "the Guyanese steps themselves, scaled by volume; other non-OPEC sanction "
                "announcements worldwide in the same window",
     "falsifier": "Surinamese milestones move the barrel proportionally to their volume, which "
                  "would make this an ordinary supply announcement and no control at all",
     "evidence": "HYPOTHESIS"},
    {"id": "AE-E9", "source": "The Trinidadian budget's stated oil and gas price assumption "
                              "against the realised strip",
     "target": "USDBRL", "targets": ("USDBRL", "USDMXN"), "to_country": "tt", "sign": "+",
     "mechanism": "Trinidad writes its budget in late September or early October on a PUBLISHED "
                  "price assumption for a fiscal year that is not the calendar year. When the "
                  "realised strip runs below the assumption, the sovereign fund is drawn on and "
                  "the FX allocation tightens, which is the rationing state the EM legs carry",
     "horizon": "the fiscal quarter", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "the Ministry of Finance and the central bank",
     "constraint": "a revenue base that is gas volume times price, and a currency it will not "
                   "devalue",
     "flow": "a fiscal shortfall transmitted into a tighter foreign-exchange ration",
     "condition": "the fiscal-year phase and the sign of the assumption-to-strip gap",
     "control": "Guyana, a second small oil sovereign with no rationing; calendar-year fiscal "
                "sovereigns, which is every other pack in this command",
     "falsifier": "the assumption-to-strip gap has no relationship to fund drawdowns or to "
                  "reported shortage episodes, making the budget assumption theatre",
     "evidence": "HYPOTHESIS"},
    {"id": "AE-E10", "source": "Declared Guyanese and Surinamese gold against the mirror import "
                               "record",
     "target": "XAUUSD", "targets": ("XAUUSD",), "to_country": "global", "sign": "+",
     "mechanism": "both countries produce real gold and both have large small-scale sectors "
                  "that declare when the declaration incentive says so. The DIFFERENCE between "
                  "declared exports and the counterparties' reported imports is a measurement "
                  "of the leakage, and the leakage moves with the gold price and the local "
                  "buying spread",
     "horizon": "1 to 3 months", "horizon_class": "multi_day", "lag_days": 45.0,
     "actor": "the gold boards, the large mines and the small-scale sector",
     "constraint": "porous forested borders and a price set in London",
     "flow": "declared versus undeclared physical gold",
     "condition": "whether declared production and mirror imports reconcile that quarter",
     "control": "the two countries against each other, which share the geology and the leakage "
                "and differ in their sovereign situation; the London benchmark itself",
     "falsifier": "declared production and mirror imports reconcile within their own dispersion, "
                  "in which case the leakage story is wrong and the declared series is usable",
     "evidence": "HYPOTHESIS"},
    {"id": "AE-E11", "source": "A reported ship-to-ship transfer surge in the Caribbean",
     "target": "XTIUSD", "targets": ("XTIUSD", "XBRUSD", "USDCNH"), "to_country": "global",
     "sign": "?",
     "mechanism": "ship-to-ship transfer is the physical signature of a cargo changing its "
                  "declared destination, and in this province it is the observable that "
                  "distinguishes 'the barrels stopped' from 'the barrels went somewhere else'. "
                  "The second is not a supply shock and the market frequently prices it as one",
     "horizon": "0 to 20 sessions", "horizon_class": "multi_day", "lag_days": 5.0,
     "actor": "the shipowners, the charterers and the state marketing arms",
     "constraint": "insurance, flag and port-state constraints on sanctioned trades",
     "flow": "a redirection of physical crude rather than a change in its quantity",
     "condition": "the route and the licensing regime in force",
     "control": "the EIA import-by-origin series at the same horizon; global freight rates on "
                "unrelated routes",
     "falsifier": "the reported transfer counts add nothing over the published import-by-origin "
                  "series, making the tanker layer a slower version of a statistic",
     "evidence": "HYPOTHESIS"},
    {"id": "AE-E12", "source": "Guyanese bauxite and sugar export volumes as the oil boom's "
                               "untreated control",
     "target": "XALUSD", "targets": ("XALUSD", "SUGAR", "XCUUSD"), "to_country": "global",
     "sign": "+",
     "mechanism": "the non-oil export economy of a country experiencing the largest per-capita "
                  "oil boom in history is a natural experiment with a treatment date of "
                  "2019-12-20. Bauxite and sugar are small in world terms and the point is not "
                  "their supply effect but the DUTCH-DISEASE READ they provide on the treatment",
     "horizon": "1 quarter to 1 year", "horizon_class": "multi_day", "lag_days": 75.0,
     "actor": "the sugar corporation and the bauxite operators",
     "constraint": "river-draft limits, quota arrangements and an oil economy bidding away "
                   "their labour",
     "flow": "small physical export volumes with a large informational content about the host",
     "condition": "the oil-era phase: before first oil or after it",
     "control": "XCUUSD as the base-metal demand control -- a move in both is a global demand "
                "event; the neighbouring economies' non-oil exports over the same period",
     "falsifier": "the non-oil export series behaves identically before and after first oil, "
                  "which would mean the boom had no measurable effect on the rest of the "
                  "economy and the natural experiment has no treatment",
     "evidence": "HYPOTHESIS"},
    {"id": "AE-E13", "source": "A shared province-wide closure from `shared_closures`",
     "target": "XBRUSD", "targets": ("XBRUSD", "XAUUSD"), "to_country": "global", "sign": "?",
     "mechanism": "four jurisdictions with four different calendars are illiquid together only "
                  "on a handful of days a year -- New Year, Christmas, Easter and, remarkably, "
                  "Diwali, which closes Guyana, Trinidad AND Suriname on the same date. On "
                  "those days the physical documentation plane of the whole province stops even "
                  "though the terminals keep loading",
     "horizon": "0 to 3 sessions", "horizon_class": "intraday", "lag_days": 0.0,
     "actor": "the ministries, banks and agents who document every cargo",
     "constraint": "four statutory calendars that only rarely coincide",
     "flow": "documentation and settlement, not barrels",
     "condition": "the number of jurisdictions closed at once, from `shared_closures`",
     "control": "the SINGLE-JURISDICTION closures, which are the natural control: one country "
                "shut against three working neighbours is a completely different object",
     "falsifier": "shared closures show no difference from single-country ones, which would "
                  "mean the documentation plane does not bind at all",
     "evidence": "HYPOTHESIS"},
)

# --------------------------------------------------------------------------- interactions
#: THE PACKS THIS ONE HAS A MEASURABLE INTERACTION WITH. Six rows, and `co` and `br` are named
#: FIRST because both are real PHYSICAL connections and not analogies: Colombia shares a land
#: border across which fuel, gold and gas move, and Brazil shares both a transmission path into
#: Roraima and the same equatorial geological margin. This is how the desk stops testing each
#: country in isolation.
INTERACTIONS: tuple[dict[str, Any], ...] = (
    {"with": "co",
     "mechanism": "THE COLOMBIAN BORDER IS A REAL PHYSICAL CONNECTION, not a comparison. Fuel, "
                  "gold and goods have moved across the Cucuta frontier through every phase of "
                  "its closure and reopening; the cross-border gas pipeline between the two "
                  "countries exists and has run in BOTH DIRECTIONS at different times; and "
                  "Colombia's own gas is declining into import dependence at exactly the moment "
                  "Venezuelan gas is a licensing question. The `co` pack owns the Colombian "
                  "peso, Ecopetrol's own production and the Colombian fiscal rule; this pack "
                  "owns the Venezuelan licensing switch and the Trinidadian gas chain. Neither "
                  "duplicates the other and the border is the edge between them",
     "observable": "the reported cross-border fuel and gold flows, the pipeline's declared "
                   "direction of flow, and Colombian gas import announcements against the "
                   "Venezuelan licensing regime from `sanctions_state`",
     "targets": ("XBRUSD", "XTIUSD", "XNGUSD"),
     "control": "Colombian production changes with NO Venezuelan licensing event in the same "
                "window, which separates 'the Andes had a supply event' from 'the licence "
                "changed'"},
    {"with": "br",
     "mechanism": "TWO REAL PATHS. First, TRANSMISSION: the Brazilian state of Roraima was "
                  "supplied with Venezuelan hydro power over a cross-border line until that "
                  "supply failed, and Brazil then connected Roraima to its own national grid -- "
                  "a dated, physical, published change in who powers a region, with thermal and "
                  "fuel-import consequences on both sides. Second, GEOLOGY: Petrobras drills "
                  "the equatorial margin at the Foz do Amazonas, which is the SAME trend as "
                  "Guyana and Suriname, so a Brazilian equatorial result is direct information "
                  "about the province's remaining running room. `br` owns the real, the Selic "
                  "and the crush; this pack owns the basin",
     "observable": "the Roraima supply arrangement and its dated changes, and Brazilian "
                   "equatorial-margin licensing and drilling results against the Guyanese and "
                   "Surinamese schedules",
     "targets": ("USDBRL", "XBRUSD", "XNGUSD"),
     "control": "Brazilian pre-salt results in the same windows, which are the same company and "
                "a completely different basin -- the cleanest way to separate 'Petrobras news' "
                "from 'equatorial margin news'"},
    {"with": "mx",
     "mechanism": "THE COMPETING HEAVY-SOUR GRADE. Mexican Maya and Venezuelan Merey compete "
                  "for the same US Gulf coking capacity, and Mexico has been REDUCING its crude "
                  "exports to feed its own new refining -- which tightens the same barrel the "
                  "Venezuelan licensing regime loosens or tightens. The two supplies are "
                  "substitutes at the refinery gate and their policy drivers are completely "
                  "unrelated, which makes each a clean instrument for the other",
     "observable": "Mexican crude export volumes and the US Gulf import mix against the "
                   "Venezuelan licensing regime and the reported Merey discount",
     "targets": ("XTIUSD", "XBRUSD", "USDMXN"),
     "control": "US Gulf refinery runs and Cushing stocks, without which a heavy-sour claim is "
                "measuring US logistics"},
    {"with": "us",
     "mechanism": "THE UNITED STATES IS SIMULTANEOUSLY THIS PROVINCE'S LICENSOR, ITS LARGEST "
                  "PHYSICAL BUYER AND ITS STATISTICAL RECORD. OFAC decides who may lawfully buy "
                  "Venezuelan crude, the Gulf refinery complex is the destination the heavy "
                  "grades are configured for, and the EIA publishes imports BY ORIGIN weekly -- "
                  "which is how the desk sees whether a licence became a barrel. The `us` pack "
                  "owns the Fed, the Treasury and the COT; this pack owns what the American "
                  "administrative state does to four other countries' supply",
     "observable": "the Federal Register and OFAC document stream against EIA imports by origin "
                   "and US Gulf refinery runs",
     "targets": ("XTIUSD", "XBRUSD", "XNGUSD", "US500"),
     "control": "US domestic supply events -- hurricanes, refinery outages, SPR actions -- in "
                "the same windows, which move the same instruments for entirely US reasons"},
    {"with": "cn",
     "mechanism": "CHINA IS THE BUYER OF LAST RESORT FOR DISCOUNTED BARRELS AND THE MARGINAL "
                  "BUYER OF THE METHANOL. When the licensing regime forbids the US Gulf, the "
                  "cargoes go east at a wider discount, frequently via ship-to-ship transfer; "
                  "and Chinese olefin and fuel-blending demand is a real part of the Trinidadian "
                  "methanol netback. `cn` owns the parity fix and the domestic demand prints; "
                  "this pack owns the cargoes arriving at them",
     "observable": "Chinese customs crude imports by origin and the reported ship-to-ship "
                   "transfer counts, against the licensing regime",
     "targets": ("USDCNH", "XBRUSD", "XTIUSD"),
     "control": "Chinese imports from OTHER discounted origins in the same months, which "
                "separates 'China bought discounted crude' from 'China bought Venezuelan crude'"},
    {"with": "sa",
     "mechanism": "THE OPEC ACCOUNTING FRAME. Venezuela is an OPEC member whose production sits "
                  "in the same monthly table as the Gulf producers' and is counted by the same "
                  "secretariat in the same two ways. A Venezuelan supply change is absorbed or "
                  "amplified by the group's spare capacity, and the `sa` pack owns that spare "
                  "capacity and the quota mechanics. THE GUYANESE RAMP IS THE MIRROR IMAGE: "
                  "non-OPEC supply arriving on a published schedule into whatever spare capacity "
                  "the group is holding",
     "observable": "the OPEC monthly production table, the spare-capacity estimate and the "
                   "two-series gap, against both the Venezuelan licensing regime and the "
                   "Guyanese capacity steps",
     "targets": ("XBRUSD", "XTIUSD"),
     "control": "OPEC decisions in months with no Venezuelan act and no Guyanese step, which is "
                "the group's own policy moving on its own"},
)

# --------------------------------------------------------------------------- eras
#: ELEVEN ERAS. Three of them are CURRENCY redenominations that mechanically invalidate any
#: Venezuelan series pooled across them, and the rest are licensing and production regimes. An
#: era table earns its place through `invalidates`: it says what a study that ignores the
#: boundary is actually measuring.
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    {"name": "the pre-sanctions province: Venezuelan volume, Trinidadian gas at its peak, no "
             "Guyanese oil at all",
     "start": "2003-01-01", "end": "2017-08-23",
     "regime": "Venezuela produces at multiples of its later level and sells freely into the US "
               "Gulf; Trinidad's gas peaks and its LNG trains run full; Guyana and Suriname "
               "produce essentially no oil",
     "markers": ("the Trinidadian gas peak and the start of the decline",
                 "the Venezuelan nationalisations and the joint-venture conversions",
                 "the 2015 Stabroek discovery announcement"),
     "why_it_matters": "the province's supply map is upside down relative to today: Venezuela "
                       "is the producer and Guyana is nothing",
     "invalidates": "any study pooling this era with the present is averaging a Venezuelan "
                    "supply state that no longer exists with a Guyanese one that did not yet",
     "status": "SETTLED"},
    {"name": "US financial sanctions: the debt channel closes, the barrels still move",
     "start": "2017-08-24", "end": "2019-01-27",
     "regime": "Executive Order 13808 prohibits new Venezuelan sovereign and PDVSA debt to US "
               "persons; production continues to decline for operational reasons and the export "
               "channel to the US Gulf is still open",
     "markers": ("2017-08-24 the financial sanctions order",
                 "the accelerating production decline through 2018"),
     "why_it_matters": "the FINANCING constraint and the TRANSACTION constraint are different "
                       "objects with different effects and eighteen months apart",
     "invalidates": "treating 'sanctions' as one event pools a financing restriction with a "
                    "trade prohibition and measures the average of two mechanisms",
     "status": "SETTLED"},
    {"name": "the blocking regime: PDVSA designated and the US Gulf channel closes",
     "start": "2019-01-28", "end": "2019-12-19",
     "regime": "the state oil company is designated and blocked; US refiners stop lifting; the "
               "export mix turns toward Asia through intermediaries at a wider discount; "
               "Guyana has still not produced a barrel",
     "markers": ("2019-01-28 the PDVSA designation",
                 "2019-08-05 the broader blocking order",
                 "the collapse in US imports by origin"),
     "why_it_matters": "this is the single largest step in the Venezuelan supply series and it "
                       "is a policy date, not a geological one",
     "invalidates": "a pooled Venezuelan production study that spans this date is measuring a "
                    "sanctions event and calling it a decline rate",
     "status": "SETTLED"},
    {"name": "the Guyanese era opens: first oil, and the ramp begins",
     "start": "2019-12-20", "end": "2022-11-25",
     "regime": "Guyana produces for the first time and adds a second vessel; Venezuela runs at "
               "its lowest level under the blocking regime; Trinidad's gas shortfall becomes "
               "structural and plants begin to idle",
     "markers": ("2019-12-20 Guyanese first oil",
                 "2022-02-11 the second Guyanese vessel starts",
                 "the pandemic demand collapse and the 2022 price spike inside the window"),
     "why_it_matters": "the province's supply map inverts here: the new producer starts and the "
                       "old one bottoms",
     "invalidates": "any Guyanese series that starts before 2019-12-20 is a series of zeros, "
                    "and a growth rate computed from zero is not a growth rate",
     "status": "SETTLED"},
    {"name": "the named-counterparty channel: one company authorised, the rest not",
     "start": "2022-11-26", "end": "2023-10-17",
     "regime": "a single company is authorised to resume limited production and export to the "
               "United States; the cross-border Trinidadian gas licence is granted inside this "
               "window; the third Guyanese vessel is sanctioned and built",
     "markers": ("2022-11-26 the company-specific authorisation",
                 "2023-01-24 the cross-border gas authorisation for Trinidad"),
     "why_it_matters": "a single-counterparty channel is a DIFFERENT object from a general "
                       "opening: the volume is bounded by one company's capacity",
     "invalidates": "pooling this era with the general-licence window measures a bounded channel "
                    "and an open one as if they were the same policy",
     "status": "SETTLED"},
    {"name": "THE GENERAL LICENCE WINDOW: six months of a broadly open regime",
     "start": "2023-10-18", "end": "2024-04-16",
     "regime": "a broad authorisation for oil and gas transactions with Venezuela, granted for "
               "six months; the widest opening of the whole series, with a start date and an "
               "end date both published in advance",
     "markers": ("2023-10-18 the general licence is issued",
                 "2023-11-14 the third Guyanese vessel starts producing",
                 "2023-12-03 the Venezuelan referendum on the Essequibo",
                 "2023-12-14 the Argyle Declaration"),
     "why_it_matters": "A NATURAL EXPERIMENT WITH TWO KNOWN DATES. The cleanest single window in "
                       "this pack and the one every Venezuelan supply claim should be tested on",
     "invalidates": "a study that averages across the whole sanctions period never sees this "
                    "window at all, which is the one period in which the counterfactual is "
                    "actually observable",
     "status": "SETTLED"},
    {"name": "the wind-down and the return to case-by-case licensing",
     "start": "2024-04-17", "end": "2026-12-31",
     "regime": "the general licence is not renewed and is replaced by a wind-down "
               "authorisation; the regime reverts to specific licences, with the Trinidadian "
               "cross-border authorisation revoked and subsequently renegotiated; the fourth "
               "Guyanese vessel starts and the fifth is under construction",
     "markers": ("2024-04-17 the general licence lapses",
                 "2025-04-02 the cross-border gas authorisation is revoked",
                 "2025-08-15 the fourth Guyanese vessel is reported producing"),
     "why_it_matters": "the CURRENT regime, and the one every live cell is compiled under",
     "invalidates": "the 2025 rows here are PRESS_REPORTED; a cell promoted on one of them "
                    "without a Federal Register citation is promoted on a newspaper",
     "status": "LIVE"},
    {"name": "the bolivar fuerte: the first redenomination",
     "start": "2008-01-01", "end": "2018-08-19",
     "regime": "the currency is redenominated at 1,000 to 1 and the exchange-control apparatus "
               "is progressively tightened into a multi-rate system",
     "markers": ("2008-01-01 the redenomination takes effect",
                 "the progressive collapse of the official rate system"),
     "why_it_matters": "a redenomination is a UNIT CHANGE, and every nominal series crosses it "
                       "with a factor of a thousand in it",
     "invalidates": "ANY Venezuelan nominal series pooled across this date is measuring a "
                    "redenomination and reporting it as inflation or as growth",
     "status": "SETTLED"},
    {"name": "the bolivar soberano: the second redenomination",
     "start": "2018-08-20", "end": "2021-09-30",
     "regime": "the currency is redenominated at 100,000 to 1 in the middle of a hyperinflation; "
               "de facto dollarisation of retail transactions accelerates",
     "markers": ("2018-08-20 the redenomination takes effect",
                 "the spread of dollar pricing through the retail economy"),
     "why_it_matters": "the second unit change in a decade, and the one that coincides with the "
                       "blocking sanctions",
     "invalidates": "a study crossing this date is pooling two currencies AND two sanctions "
                    "regimes, which is two confounds in one boundary",
     "status": "SETTLED"},
    {"name": "the bolivar digital: the third redenomination",
     "start": "2021-10-01", "end": "2026-12-31",
     "regime": "the currency is redenominated at 1,000,000 to 1; the retail economy is "
               "substantially dollarised and the official and parallel references coexist",
     "markers": ("2021-10-01 the redenomination takes effect",
                 "the partial resumption of official statistical publication"),
     "why_it_matters": "the CURRENT currency, and the third unit change since 2008",
     "invalidates": "three redenominations in fifteen years means there is NO continuous "
                    "Venezuelan nominal series at all, which is why this pack reads Venezuela "
                    "in barrels and cargoes and never in bolivars",
     "status": "LIVE"},
    {"name": "the Surinamese default and the oil-linked restructuring",
     "start": "2021-04-01", "end": "2026-12-31",
     "regime": "Suriname defaults on its external debt, agrees an IMF programme with a "
               "reserve-money target, and settles with bondholders on terms that attach a value "
               "recovery instrument to future Block 58 royalties; Block 58 is sanctioned inside "
               "this window",
     "markers": ("the 2021 default and the start of the IMF programme",
                 "the 2023-2024 bondholder settlement with the oil-linked instrument",
                 "2024-10 the Block 58 final investment decision"),
     "why_it_matters": "the sovereign's credit becomes an explicit derivative of a dated oil "
                       "development, which is the link AE-K tests",
     "invalidates": "a Surinamese macro series pooled across the default and the float is "
                    "measuring a currency regime change and calling it a macro relationship",
     "status": "LIVE"},
)

# --------------------------------------------------------------------------- access
ACCESS_CONSTRAINTS: tuple[dict[str, Any], ...] = (
    {"constraint": "VENEZUELA IS UNDER A SANCTIONS REGIME, and this pack states its boundary "
                   "explicitly rather than leaving it to be inferred",
     "measured": "every Venezuelan object in this pack is a PUBLIC document or a foreign "
                 "government's own statistic: OFAC's published licences and FAQs, OPEC's "
                 "Monthly Oil Market Report, the EIA, the US Federal Register, published court "
                 "dockets, national statistics and public press",
     "consequence": "NOTHING IN THIS PACK TOUCHES A SANCTIONED ENTITY'S PRIVATE SYSTEMS AND "
                    "NOTHING BYPASSES AN ACCESS CONTROL. Sanctions constrain TRANSACTIONS, not "
                    "the reading of published administrative acts -- and the desk executes only "
                    "broker symbols, never a Venezuelan, Guyanese, Trinidadian or Surinamese "
                    "instrument. The research is reading; the execution is XBRUSD and its "
                    "siblings; the two never meet in a sanctioned counterparty"},
    {"constraint": "none of the four currencies is quoted by this broker",
     "measured": "data/universe/universe.json holds no GYD, TTD, VES or SRD symbol",
     "consequence": "every domestic macro mechanism terminates in the regional EM legs, the "
                    "barrel, the metals, the softs or US500; the four currencies are INPUTS and "
                    "CONDITIONERS and never cells"},
    {"constraint": "HENRY HUB IS NOT ATLANTIC LNG, and this is the pack's most dangerous "
                   "substitution",
     "measured": "XNGUSD is a US pipeline-gas contract; Trinidad exports liquefied gas into the "
                 "Atlantic basin, and a Trinidadian outage can move the two in OPPOSITE "
                 "directions by freeing US cargoes",
     "consequence": "every XNGUSD cell in this pack carries a mandatory US supply, storage and "
                    "weather control, and any cell that drops it is refused. A study that swaps "
                    "one for the other measures the ARBITRAGE, not the shock"},
    {"constraint": "the ammonia, methanol and LNG price assessments forbid machine extraction",
     "measured": "the price reporting agencies' terms; the row is registered with "
                 "machine_use_allowed=false in `SOURCE_CLASSES`",
     "consequence": "the PRICE leg of the fertiliser and gas chains is UNMEASURED by name. AE-E "
                    "is tested on PHYSICAL OUTPUT VOLUME from the ministry bulletin and the "
                    "absence is carried rather than worked around; the source is registered so "
                    "the desk does not lose the knowledge that the ground exists"},
    {"constraint": "the ministry pages that carry the two best physical series are OVERWRITTEN "
                   "IN PLACE",
     "measured": "the Trinidadian monthly bulletin and the Guyanese NRF report both publish the "
                 "current file over the same link and keep no vintage",
     "consequence": "the point-in-time history of AE-B and AE-D exists ONLY in the archive "
                    "layer's crawls; a cell compiled on an un-archived month is UNMEASURED, not "
                    "assumed, and `pit_feasible` is false on both dataset rows"},
    {"constraint": "Venezuela's own statistical record is broken and PDVSA publishes no audited "
                   "accounts",
     "measured": "`NO_LAWFUL_GROUND` carries the (jurisdiction, layer) rows with the years and "
                 "the reasons",
     "consequence": "every Venezuelan cell declares WHICH LAWFUL SUBSTITUTE it used -- OPEC "
                    "secondary sources, the Finance Observatory's CPI, mirror customs from the "
                    "United States and China, or tanker-tracking press reports -- and a cell "
                    "that cannot name its substitute is refused"},
    {"constraint": "the blockade of measurement in the gold sector is structural",
     "measured": "declared production and mirror imports do not reconcile in either Guyana or "
                 "Suriname, and the small-scale sector declares on an incentive",
     "consequence": "every XAUUSD cell from this pack is labelled WEAK; the declared series is "
                    "never used alone and the export-minus-mirror gap is carried as a "
                    "measurement warning rather than as a supply signal"},
    {"constraint": "the Venezuelan and Surinamese event dates are substantially PRESS_REPORTED",
     "measured": "the 2025 rows of `SANCTIONS_ACTS`, the incident rows of `ESSEQUIBO_EVENTS` "
                 "and the Surinamese restructuring dates all carry that label",
     "consequence": "those rows may generate hypotheses and may promote NOTHING until a Federal "
                    "Register citation, a court docket entry or an official announcement is "
                    "attached to the exact date the cell was compiled on"},
    {"constraint": "there is no positioning series for any currency in this province and no "
                   "listed derivatives market in any of the four",
     "measured": "no futures contract, no COT report and no exchange with an expiry clock",
     "consequence": "positioning is read on the EXECUTABLE legs only -- the crude and gas COT -- "
                    "and local positioning is UNMEASURED and is never proxied by a BRL or MXN "
                    "leg pretending to be a local one"},
    {"constraint": "the Trinidadian gas allocation between LNG, ammonia, methanol and power is "
                   "a private commercial decision",
     "measured": "the ministry publishes production and output; it does not publish the "
                 "aggregator's allocation",
     "consequence": "the allocation stays UNMEASURED and is NEVER inferred from an output "
                    "total; AE-D conditions on the published field-level production and reports "
                    "the allocation as the missing input on every pass"},
)
INSTITUTIONAL_FLOW_SOURCES: tuple[str, ...] = (
    "Guyana NRF monthly receipts, balance and withdrawals to the budget",
    "EIA weekly US crude imports by country of origin",
    "OPEC MOMR production, direct communication and secondary sources",
    "Central Bank of Trinidad and Tobago foreign-exchange sales to authorised dealers",
    "Trinidad Ministry of Energy field-level gas, LNG, ammonia and methanol output",
    "Centrale Bank van Suriname auction results and reserve money",
    "UN Comtrade mirror trade for crude, gas, gold, bauxite and ammonia")
SERIES: dict[str, str] = {
    "AE_GY_NRF": "MOF_GY:nrf_receipts", "AE_GY_PRODUCTION": "MNR_GY:crude_production",
    "AE_GY_FX": "BOG:market_rates", "AE_GY_GDP": "BOS_GY:gdp_oil_and_nonoil",
    "AE_GY_GOLD": "GGMC:gold_declaration",
    "AE_TT_GAS": "MEEI:gas_production_by_field", "AE_TT_LNG": "MEEI:lng_output",
    "AE_TT_AMMONIA": "MEEI:ammonia_output", "AE_TT_METHANOL": "MEEI:methanol_output",
    "AE_TT_FX_SALES": "CBTT:fx_sales_to_dealers", "AE_TT_HSF": "MOF_TT:hsf_balance",
    "AE_VE_OPEC_DIRECT": "OPEC:ve_production_direct",
    "AE_VE_OPEC_SECONDARY": "OPEC:ve_production_secondary",
    "AE_VE_LICENCES": "OFAC:venezuela_licences", "AE_VE_CPI": "OVF:cpi_monthly",
    "AE_SR_FX": "CBVS:exchange_rate", "AE_SR_RESERVE_MONEY": "CBVS:reserve_money",
    "AE_SR_GOLD": "ABS_SR:gold_exports",
    "AE_US_IMPORTS": "EIA:crude_imports_by_origin", "AE_ICJ": "ICJ:guyana_v_venezuela_docket",
    "AE_MIRROR": "COMTRADE:mirror_trade",
}

# --------------------------------------------------------------------------- the cells
#: WHAT EACH DOMAIN MINTS: its mechanism family, its horizon class, and the one-line control
#: every cell from it inherits. `cells()` is the cross product of a domain's INSTRUMENTS and its
#: CONDITIONS -- both of which are real, named, evaluable states of this pack's own data plane.
#: It is not a cartesian blow-up: a condition that cannot be evaluated from a declared dataset
#: does not appear in a domain's `conditions` tuple in the first place, and a domain's
#: instrument tuple is its own rather than the pack's whole executable list.
DOMAIN_CELL_SPEC: dict[str, tuple[str, str, str]] = {
    "AE-A": ("scheduled_supply_step", "0d_to_20d",
             "the Surinamese schedule on a later clock, and matched windows with the same OPEC "
             "spare-capacity state and no step"),
    "AE-B": ("fiscal_formula", "the publication day plus 10 sessions",
             "the published `government_take` formula on lagged Brent, and Trinidad's "
             "differently-dated fiscal year"),
    "AE-C": ("physical_supply", "1q_to_1y",
             "XCUUSD as the base-metal demand control and the pre-2019 untreated period"),
    "AE-D": ("gas_supply", "0d_to_15d",
             "US storage, US production and heating-degree-days -- mandatory on every cell"),
    "AE-E": ("input_cost_chain", "20d_to_60d",
             "SOYBEAN as the nitrogen-fixing crop, the European curtailments and the USDA "
             "report calendar"),
    "AE-F": ("rationed_currency", "the fiscal quarter",
             "Guyana as a second oil sovereign with no rationing, and matched EM risk days"),
    "AE-G": ("administrative_supply_switch", "0d_to_30d",
             "Mexican Maya as the competing heavy-sour grade, plus US crude stocks and Cushing"),
    "AE-H": ("measurement_gap", "the MOMR day plus 10 sessions",
             "the same two-series gap for other OPEC members, and the mirror import records"),
    "AE-I": ("regime_boundary", "regime_level_shift",
             "the regional EM legs on matched risk days, and the other three jurisdictions"),
    "AE-J": ("forward_schedule", "0d_to_15d",
             "the Guyanese steps scaled by volume, and other non-OPEC sanction announcements"),
    "AE-K": ("sovereign_credit", "1m_to_1q",
             "Guyanese gold over the same windows, and USDBRL as the risk-appetite leg"),
    "AE-L": ("territorial_risk", "intraday_to_5d",
             "matched court-calendar windows where nothing was decided, and comparable global "
             "risk days with no Essequibo event"),
    "AE-M": ("logistics_regime", "0d_to_20d",
             "the EIA import-by-origin series at the same horizon, and unrelated freight routes"),
}


def cells() -> tuple[dict[str, Any], ...]:
    """Every testable cell this pack mints: domain x executable instrument x named condition.

    A cell is a triple the gauntlet can actually evaluate -- an instrument the broker quotes, a
    condition this pack's own declared datasets can compute, and a control that is not the
    instrument's own history. The cross product is taken over the domain's OWN instrument tuple
    rather than over the whole executable list, which is what keeps the count honest: AE-E never
    mints a crude cell and AE-A never mints a corn one.
    """
    out: list[dict[str, Any]] = []
    for dom in DOMAINS:
        did = str(dom["id"])
        family, horizon, control = DOMAIN_CELL_SPEC.get(did, ("residual", "1d_to_5d",
                                                              "a matched-weekday placebo"))
        for symbol in dom["instruments"]:
            for i, condition in enumerate(dom["conditions"]):
                out.append({
                    "cell_id": f"{CODE.lower()}:{did}:{symbol}:c{i + 1}",
                    "domain": did, "symbol": str(symbol), "condition": str(condition),
                    "mechanism_family": family, "horizon": horizon, "control": control,
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


def actors_by_jurisdiction() -> dict[str, int]:
    """How many actors each jurisdiction owns, from each actor's DECLARED `jurisdiction` key.

    Declared rather than inferred on purpose: a Surinamese actor whose falsifier names Guyana as
    its control would be mis-attributed by any text scan, and a four-country pack that cannot say
    which country an actor belongs to cannot prove it is four countries deep.
    """
    out: dict[str, int] = dict.fromkeys((*JURISDICTIONS, "province"), 0)
    for row in ACTORS:
        key = str(row.get("jurisdiction") or "province")
        out[key] = out.get(key, 0) + 1
    return out


def cells_by_jurisdiction() -> dict[str, int]:
    """How many cells each jurisdiction's domains mint. A four-country pack that mints all its
    cells in one country is a one-country pack wearing four flags, and this counts it."""
    owner = {"AE-A": "gy", "AE-B": "gy", "AE-C": "gy", "AE-D": "tt", "AE-E": "tt", "AE-F": "tt",
             "AE-G": "ve", "AE-H": "ve", "AE-I": "ve", "AE-J": "sr", "AE-K": "sr",
             "AE-L": "province", "AE-M": "province"}
    out: dict[str, int] = {}
    for row in CELLS:
        key = owner.get(str(row["domain"]), "province")
        out[key] = out.get(key, 0) + 1
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
        record(mechanism=mechanism, source_id=f"{CODE.lower()}:pack", source_type="claim",
               **fields)
    except Exception:
        return 0
    return 1


def ramp_schedule(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """AE-A and AE-J: the dated capacity steps of both ramps, with the forward half kept apart
    from the producing half so a schedule never becomes a forecast by accident."""
    today = datetime.now(tz=UTC).date()
    steps = ramp_steps("gy")
    producing = sanctioned_capacity_on(today, "gy")
    scheduled = scheduled_capacity_on(date(2030, 12, 31), "gy")
    n = 0
    for when, cumulative, vessel in steps:
        n += _emit(ctx, "scheduled_supply_step",
                   payload={"domain": "AE-A", "vessel": vessel, "first_oil": when.isoformat(),
                            "cumulative_nameplate_bpd": cumulative})
    for row in fpso_rows("sr"):
        n += _emit(ctx, "forward_schedule",
                   payload={"domain": "AE-J", "vessel": row["vessel"],
                            "first_oil_target": row["first_oil"],
                            "nameplate_bpd": row["nameplate_bpd"]})
    return {"miner": "ramp_schedule", "domain": "AE-A", "steps": len(steps),
            "producing_nameplate_bpd": producing, "scheduled_2030_nameplate_bpd": scheduled,
            "emitted": n,
            "unmeasured": ["AE-A/debottlenecking: the uplift of measured output over nameplate "
                           "is NOT in this pack (L1.28a); `sanctioned_capacity_on` returns "
                           "nameplate only and a cell that needs output must declare the uplift",
                           "AE-A/forecast_vintages: the published non-OPEC supply forecasts the "
                           "steps should be compared against are not loaded"]}


def fiscal_formula(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """AE-B and AE-F: the published sovereign take, computed, with the residual named as the
    only part of the receipt series that can carry new information."""
    probe = government_take(1000.0, 800.0)
    n = _emit(ctx, "fiscal_formula",
              payload={"domain": "AE-B", "regime": "stabroek_2016",
                       "government_share_of_revenue": probe["government_share_of_revenue"],
                       "ceiling_bound": probe["cost_oil"] < 800.0})
    n += _emit(ctx, "rationed_currency",
               payload={"domain": "AE-F", "fiscal_year_end_tt": FISCAL_YEARS["tt"][:5]})
    return {"miner": "fiscal_formula", "domain": "AE-B", "regimes": len(PSA_TERMS),
            "emitted": n,
            "unmeasured": ["AE-B/nrf_receipts: the NRF monthly series is not loaded on this "
                           "box, so the RESIDUAL after the formula is UNMEASURED and the "
                           "formula alone mints no cell",
                           "AE-F/budget_assumption: the Trinidadian budget price assumption is "
                           "not in this pack and must be read from the budget statement"]}


def licence_calendar(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """AE-G and AE-H: the dated administrative acts and the regime they put in force."""
    n = 0
    for when, act, effect in licence_events():
        n += _emit(ctx, "administrative_supply_switch",
                   payload={"domain": "AE-G", "date": when.isoformat(), "act": act,
                            "regime_after": sanctions_state(when), "effect": effect})
    published = len(licence_events("PUBLISHED_ACT"))
    return {"miner": "licence_calendar", "domain": "AE-G", "acts": len(SANCTIONS_ACTS),
            "published_acts": published, "press_reported": len(SANCTIONS_ACTS) - published,
            "regimes": len(SANCTIONS_REGIMES), "emitted": n,
            "unmeasured": ["AE-G/enforcement: the EIA import-by-origin series is not loaded, so "
                           "whether a licence became a BARREL is UNMEASURED here",
                           "AE-H/opec_series: neither OPEC series is loaded on this box, so "
                           "`opec_gap` has no inputs and mints a conditioner, not a cell"]}


def gas_chain(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """AE-D and AE-E: the Trinidadian gas facts and the nitrogen chain, with the Henry Hub basis
    warning emitted on every pass because it is the substitution most likely to be made."""
    n = 0
    for label, what, status in TRINIDAD_GAS_FACTS:
        n += _emit(ctx, "gas_supply",
                   payload={"domain": "AE-D", "fact": label, "what": what, "status": status})
    n += _emit(ctx, "input_cost_chain",
               payload={"domain": "AE-E", "chain": "gas curtailment -> ammonia -> nitrogen cost "
                                                   "-> CORN/WHEAT acreage",
                        "control": "SOYBEAN fixes its own nitrogen"})
    return {"miner": "gas_chain", "domain": "AE-D", "facts": len(TRINIDAD_GAS_FACTS),
            "emitted": n,
            "unmeasured": ["AE-D/HENRY_HUB_BASIS: XNGUSD is a US pipeline contract and Trinidad "
                           "exports LNG; no cell may be compiled without the US storage, "
                           "production and heating-degree-day control, which is not loaded here",
                           "AE-E/ammonia_price: the nitrogen assessments forbid machine "
                           "extraction (machine_use_allowed=false), so the price leg is "
                           "UNMEASURED and the chain is tested on physical output volume"]}


def territorial_risk(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """AE-L: the Essequibo series, split by confidence label, with the capacity at risk on each
    date attached -- the stake has grown by a factor of five since the case was filed."""
    n = 0
    for iso, event, status in ESSEQUIBO_EVENTS:
        when = date.fromisoformat(iso)
        n += _emit(ctx, "territorial_risk",
                   payload={"domain": "AE-L", "date": iso, "event": event, "status": status,
                            "capacity_at_risk_bpd": sanctioned_capacity_on(when, "gy")})
    court = sum(1 for _i, _e, st in ESSEQUIBO_EVENTS if st == "COURT_RECORD")
    return {"miner": "territorial_risk", "domain": "AE-L", "events": len(ESSEQUIBO_EVENTS),
            "court_record": court, "press_reported": len(ESSEQUIBO_EVENTS) - court,
            "emitted": n,
            "unmeasured": ["AE-L/forward_calendar: the ICJ's scheduled FUTURE dates are the "
                           "most valuable half of this series and they are not in this pack; "
                           "they must be read from the court's own case page"]}


def province_calendar(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """AE-C, AE-K and AE-M: four calendars that do not agree. The SHARED closures are a
    liquidity regime; the single-jurisdiction ones are natural controls."""
    year = datetime.now(tz=UTC).year
    if year not in HOLIDAYS_RULE["years"]:
        year = int(max(HOLIDAYS_RULE["years"]))
    shared = shared_closures(year, 3)
    n = _emit(ctx, "logistics_regime",
              payload={"domain": "AE-M", "year": year, "shared_closures": len(shared),
                       "province_closures": len(province_holidays(year))})
    monday, tuesday = carnival(year)
    n += _emit(ctx, "logistics_regime",
               payload={"domain": "AE-M", "carnival_monday": monday.isoformat(),
                        "carnival_tuesday": tuesday.isoformat(),
                        "note": "not statutory in Trinidad and the country shuts"})
    return {"miner": "province_calendar", "domain": "AE-M", "year": year,
            "shared_closures": len(shared), "emitted": n,
            "unmeasured": [f"AE-M/lunar_{year}: the Hindu and Islamic dates in "
                           f"`LUNAR_HOLIDAYS` are TYPED with their gazetting authority and not "
                           f"computed; a cell on one of them is UNMEASURED until the gazette "
                           f"is joined"]}


def currency_regimes(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """AE-I and AE-F: four incompatible monetary regimes over one basin, and the three
    redenominations that forbid pooling. This miner mostly mints REFUSALS, which is its job."""
    n = 0
    for cc, row in CURRENCIES.items():
        n += _emit(ctx, "regime_boundary",
                   payload={"domain": "AE-I", "jurisdiction": cc, "code": row["code"],
                            "regime": row["regime"], "broker_quoted": row["broker_quoted"]})
    breaks = [e["name"] for e in POLICY_ERAS if "redenomination" in str(e["name"])]
    return {"miner": "currency_regimes", "domain": "AE-I", "currencies": len(CURRENCIES),
            "redenomination_eras": len(breaks), "emitted": n,
            "unmeasured": ["AE-I/ves_series: there is NO continuous Venezuelan nominal series "
                           "at all across three redenominations, so every bolivar series is "
                           "UNMEASURED by construction and Venezuela is read in barrels",
                           "AE-F/parallel_premium: no TTD parallel quote is loaded on this box, "
                           "so `parallel_premium` has no inputs and the ration state is read "
                           "from reported episodes instead"]}


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
    "ramp_schedule": ramp_schedule,
    "fiscal_formula": fiscal_formula,
    "licence_calendar": licence_calendar,
    "gas_chain": gas_chain,
    "territorial_risk": territorial_risk,
    "province_calendar": province_calendar,
    "currency_regimes": currency_regimes,
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
    return {"code": CODE.lower(), "at": datetime.now(tz=UTC).date().isoformat(),
            "emitted": emitted, "cells_emitted": len(CELLS), "rows": rows,
            "unmeasured": unmeasured, "jurisdictions": JURISDICTIONS,
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
        "interactions": INTERACTIONS, "query_territories": QUERY_TERRITORIES,
        "no_lawful_ground": NO_LAWFUL_GROUND, "cells": CELLS,
        "fpso_schedule": FPSO_SCHEDULE, "psa_terms": PSA_TERMS,
        "sanctions_acts": SANCTIONS_ACTS, "essequibo_events": ESSEQUIBO_EVENTS,
        "trinidad_gas_facts": TRINIDAD_GAS_FACTS, "gold_facts": GOLD_FACTS,
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
    """The framework's HolidayRule shape: every closed WEEKDAY the province rule produces for
    2024-2026, plus the fixed month-day pairs of all four national calendars."""
    dates = sorted({d.isoformat() for y in HOLIDAYS_RULE["years"] for d in market_holidays(y)})
    fixed = sorted({f"{m:02d}-{d:02d}"
                    for rows in FIXED_HOLIDAYS.values() for m, d, _name in rows})
    return {"dates": tuple(dates), "fixed_md": tuple(fixed), "weekly_closed": (5, 6),
            "notes": HOLIDAYS_RULE["authority"]}


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
