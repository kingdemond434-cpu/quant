"""ECUADOR: the only economy on this desk with NO CURRENCY, and every shock must land somewhere.

WHY ECUADOR EARNS A PACK OF ITS OWN NEXT TO `pe` AND `co`. Ecuador has been FULLY DOLLARISED
SINCE 9 JANUARY 2000. There is no sucre, no exchange rate, no policy rate, no open-market
operation and NO LENDER OF LAST RESORT -- the Banco Central del Ecuador is a clearing house and a
reserve custodian, not a monetary authority. Peru and Colombia, its two neighbours, both float
with active and transparent central banks: the BCRP publishes its daily spot intervention and
BanRep runs an inflation target with its own auction book. THE SAME ANDEAN GEOGRAPHY, THE SAME
EL NINO, THE SAME OIL, THE SAME COCA CORRIDOR, AND ONE OF THE THREE HAS NO MONETARY CHANNEL AT
ALL. `pe` and `co` are this pack's controls and they are named as such in `INTERACTIONS`, first
and explicitly. That is not a framing device: it is the identification strategy, and it is the
reason this pack is not a paragraph inside either sibling.

WHAT DOLLARISATION MEANS FOR A CELL, SAID PLAINLY. In `pe` the question "did the political event
move the currency" has an answer, because there is a currency. HERE THERE IS NOTHING TO ROUTE.
Every domestic shock must be absorbed by the REAL economy (output, employment, imports, the power
supply) and by the FISCAL balance (the subsidy bill, the arrears, the spread on the Global bonds,
the IMF disbursement schedule). So this pack routes nothing through an FX pair of its own and
says so: `TRANSMISSION_TARGETS` opens with the statement that there is no Ecuadorian currency,
and every macro domain terminates in the sovereign-risk legs, the commodities the country
actually ships, and US500 as the global risk state. A pack that pretended otherwise would be
inventing the one channel this country deliberately removed.

SIX THINGS THAT BELONG TO THIS ECONOMY AND TO NO OTHER IN THE DESK'S BOOK.

  1. A SOVEREIGN ELECTORATE VOTED AN OIL FIELD SHUT. On 2023-08-20, on a ballot approved by the
     Corte Constitucional and counted by the Consejo Nacional Electoral, Ecuadorians voted YES to
     leaving the ITT crude of Block 43 in the ground -- roughly 50 kb/d of production, with a
     dated one-year compliance deadline that fell on 2024-08-31. A published, dated, sovereign
     decision to destroy supply is a genuinely unique event and there is nothing like it
     anywhere else in this desk's country book.

  2. THE PIPELINES ARE CUT BY A RIVER, AND THE CUTS ARE DATED. The San Rafael waterfall collapsed
     on 2020-02-02 and the Coca river has since eaten its own bed upstream -- REGRESSIVE EROSION,
     a named geomorphological process advancing kilometres a year toward the intakes. The SOTE
     (state) and OCP (private) pipelines carry essentially all of Ecuador's exportable crude
     across that erosion front. They have ruptured or been pre-emptively shut repeatedly, each
     time with a PUBLISHED FORCE-MAJEURE declaration to cargo buyers. That is a physical, dated,
     lawful supply interruption of a liquid crude grade, announced by the operator, in Spanish,
     which essentially no systematic desk reads.

  3. A PUBLISHED NATIONAL POWER-RATIONING SCHEDULE ON AN INDUSTRIAL ECONOMY. Ecuador's grid is
     roughly three-quarters hydro and its largest plant, Coca Codo Sinclair (1,500 MW), sits on
     the same river. Drought at Coca Codo and at the Paute-Mazar complex forced CENACE and the
     distributors to publish NATIONWIDE RATIONING TABLES -- by province, by feeder, by hour --
     in late 2023, for several days in April 2024, and again from September to December 2024 at
     up to fourteen hours a day. A quantified, scheduled, dated loss of load is an output shock
     with a timetable, and the government even decreed non-working days to save power.

  4. THE SOVEREIGN IS A DATED CREDIT EVENT SERIES. A 2008 default BY CHOICE, a 2009 buyback at
     roughly a third of face, a 2020 COVID restructuring of about US$17.4bn of Global bonds
     completed on 2020-08-31, the LARGEST DEBT-FOR-NATURE SWAP ON RECORD in May 2023 (the
     Galapagos Marine Bond, roughly US$1.6bn of old bonds retired for about US$644m) and a second
     Amazon swap in December 2024, plus an IMF Extended Fund Facility approved 2024-05-31. Every
     one of those is a timestamp with a published document behind it.

  5. THE WORLD'S LARGEST SHRIMP AND BANANA EXPORTER, WITH CHINA ON THE OTHER SIDE. The Camara
     Nacional de Acuacultura publishes MONTHLY export volumes by destination, and China takes the
     majority of the shrimp. Bananas run on an ADMINISTERED MINIMUM SUPPORT PRICE per 43-pound
     box, set annually by Acuerdo Ministerial and published in the Registro Oficial -- an
     administered price on a quarter of world banana trade. Cacao fino de aroma is the third leg
     and the only one with a liquid contract on the other side of it.

  6. THE SECURITY EMERGENCY IS A PORT MECHANISM. Guayaquil is the largest container port on the
     Pacific coast of South America AND the region's principal cocaine-export chokepoint. The
     2024 "internal armed conflict" decree of 2024-01-09, the prison escapes that preceded it and
     the interdiction seizures that follow it are all dated, and they land on container
     throughput -- which is how the cacao, the banana and the shrimp actually leave.

WHAT IS EXECUTABLE AND WHAT IS NOT. THE DOLLAR IS THE CURRENCY, so there is no currency pair to
trade and none is claimed. Absent and named in `TRANSMISSION_TARGETS`: the Oriente and Napo crude
differentials, Ecuadorian sovereign bonds and their spread, the Bolsa de Valores de Quito and
Guayaquil indices, shrimp FOB, the banana box price, and spot LNG. Each names the broker symbols
that carry its economics.

THE TWO-LANE ORDER (2026-09-06). EP Petroecuador, OCP Ecuador, CELEC, Banco Pichincha, Corporacion
Favorita, Lundin Gold and EcuaCorriente are ACTORS here and never instruments. No share CFD
appears in any instrument tuple in this file.

NATIVE GROUND. Spanish is the working language of the BCE, the ministries and the press. KICHWA
and SHUAR are official for intercultural use under article 2 of the 2008 constitution, and the
Amazonian oil-bloc consultations, the CONAIE strike calendars that shut the wellheads and the
community assemblies that decide them happen in them. An English- or Spanish-only crawl of
Ecuador reads Quito and misses the Oriente, which is where the supply is.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Any

# --------------------------------------------------------------------------- identity
CODE = "ec"
NAME = "Ecuador"
REGION_COMMAND = "latam"
REGION_DESK = "SOUTH_AMERICA"
FOREST = "latam"
#: THE CURRENCY IS THE UNITED STATES DOLLAR AND THAT IS THE POINT OF THE PACK. Ecuador adopted it
#: on 2000-01-09; the sucre ceased to be legal tender on 2000-09-11. The only domestic money it
#: issues is fractional coinage struck to US denominations.
CURRENCY = "USD"
#: THE PARITY FENCE COUNTS THIS (`scripts/check_regional_parity.py::jurisdictions_of`). Ecuador is
#: on the desk's own latam roster and no sibling pack answers for it: `pe` and `co` are each
#: written around a domestic central bank and a domestic currency, neither of which exists here.
JURISDICTIONS: tuple[str, ...] = ("ec",)
FISCAL_YEAR_END = "12-31"          # the Presupuesto General del Estado runs the calendar year
NATIVE_LANGUAGES: tuple[str, ...] = ("es", "qu", "jiv", "en")
COT_CURRENCY = ""                  # there is no Ecuadorian currency, so no contract can exist
EXPORT_ECONOMY = "commodity_exporter"
RETAIL_LEVERAGE_REGIME = "restricted"
#: The depth this pack CLAIMS, so a test can check the framework's own measurement against it
#: rather than against a number typed into a report. `regional_parity.pack_depth` computes the
#: real one; this is the floor the pack promises not to fall below.
DECLARED_DEPTH: float = 1.0
MISSION = ("mine Ecuador as the fully dollarised, physically interrupted commodity state it is: "
           "the SOTE and OCP force-majeure record against the Coca river's regressive erosion, "
           "the ITT/Yasuni referendum as a sovereign decision to shut a field, the CENACE "
           "rationing schedules of 2023 and 2024 as a dated industrial-load shock, the 2020 "
           "restructuring and the two debt-for-nature swaps as a credit-event series, the "
           "monthly shrimp and banana export volumes with China on the other side, the cacao "
           "fino de aroma share against West Africa, and Guayaquil throughput under the "
           "internal-armed-conflict decree -- all of it with `pe` and `co` as the floating "
           "controls that make dollarisation measurable")

#: The instruments this pack may compile a cell against. Every one is in the broker registry and
#: none is a single-name equity. THERE IS NO ECUADORIAN CURRENCY IN THIS LIST BECAUSE THERE IS NO
#: ECUADORIAN CURRENCY (see TRANSMISSION_TARGETS).
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "XBRUSD",                          # the export benchmark Oriente and Napo price against
    "XTIUSD",                          # the US Gulf leg: Ecuador's crude competes into PADD 3/5
    "XNGUSD",                          # the thermal fuel the grid burns when the reservoirs fail
    "XAUUSD",                          # Fruta del Norte, plus the informal Amazonian gold lane
    "XCUUSD",                          # Mirador: industrial copper in a country that votes on it
    "UKCOCOA",                         # cacao fino de aroma; Ecuador is a top-three exporter
    "USCOCOA",                         # the second cocoa contract, the first one's own control
    "COFARA",                          # the tropical-softs complex leg and the Colombian control
    "SUGAR",                           # the other tropical soft; the softs-complex beta control
    "CORN",                            # the shrimp and poultry feed ration, and the import bill
    "SOYBEAN",                         # the other half of the ration; the shrimp-meal substitute
    "USDCNH",                          # China buys the shrimp, owns Mirador and holds the debt
    "USDBRL",                          # the regional EM leg every dollarised shock is read against
    "USDMXN",                          # the deepest LatAm leg; the risk-on/risk-off control
    "US500",                           # the global risk state every Ecuadorian cell conditions on
)

#: WHAT ECUADOR TRADES THAT THIS BROKER DOES NOT QUOTE. Each row names the absent instrument, the
#: venue it lives on, WHY the pack needs it, and the broker symbols that carry its economics. The
#: FIRST ROW IS THE PACK'S THESIS: there is no currency, and saying so is the measurement.
TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "A DOMESTIC CURRENCY. There is none: Ecuador uses the USD and has since 2000-01-09",
     "venue": "none exists; the Banco Central del Ecuador issues fractional coinage only",
     "why": "THIS IS THE PACK'S WHOLE THESIS AND NOT AN OMISSION. Peru has USDPEN (absent from "
            "this broker but real), Colombia has USDCOP, Brazil has USDBRL. Ecuador has NO "
            "exchange rate at all, so the FX absorption channel that every sibling pack routes "
            "through simply does not exist. A shock that a floating neighbour takes in the "
            "currency must be taken here in output, in imports, in the fiscal balance or in the "
            "sovereign spread -- which is precisely the hypothesis this pack exists to test",
     "regime": "full official dollarisation, no monetary policy, no lender of last resort",
     "route": "there is nothing to route; every macro domain terminates in USDBRL and USDMXN as "
              "REGIONAL RISK legs (never as proxies for a currency Ecuador does not have), in "
              "the commodities the country actually ships, and in US500 as the risk state",
     "proxies": ("USDBRL", "USDMXN", "US500")},
    {"name": "Oriente (24 API) and Napo (19 API) crude, and their differentials to WTI",
     "venue": "EP Petroecuador export tenders and the US Gulf and Asian spot market",
     "why": "the two grades ARE the export economy's price, and the differential is where a "
            "force-majeure or a quality-bank change actually shows up; neither is a broker symbol",
     "regime": "spot cargo sales plus long-dated Chinese prepayment contracts",
     "route": "XBRUSD carries the benchmark and XTIUSD the US Gulf leg the grades compete into; "
              "the DIFFERENTIAL itself is UNMEASURED on this box and is named rather than proxied",
     "proxies": ("XBRUSD", "XTIUSD")},
    {"name": "The Republic of Ecuador Global bonds (2030, 2035, 2040) and the sovereign spread",
     "venue": "the international over-the-counter market; the MEF publishes the debt stock",
     "why": "the ONLY fast domestic risk price this country has. With no currency and no policy "
            "rate, the spread is the single continuous read on how a political or fiscal event "
            "is being taken, and it is what the debt-for-nature swaps repriced",
     "regime": "post-restructuring step-up coupons; PDI capitalisation; no CDS this box quotes",
     "route": "USDBRL and USDMXN as the regional risk legs and US500 as the global one; the "
              "Ecuadorian spread itself is a CONDITIONER supplied by the collector, never a cell",
     "proxies": ("USDBRL", "USDMXN", "US500")},
    {"name": "The Bolsa de Valores de Quito and Guayaquil indices (ECUINDEX)",
     "venue": "bolsadequito.com and the Guayaquil bourse",
     "why": "the domestic equity market is small, illiquid and dominated by fixed-income paper; "
            "no CFD exists on any Ecuadorian index and none is claimed",
     "regime": "a predominantly fixed-income bourse with a thin equity board",
     "route": "US500 carries the risk state; the domestic bourse enters as a transmission target "
              "and as an ACTOR observable, never as an instrument",
     "proxies": ("US500",)},
    {"name": "Shrimp FOB (vannamei, head-on shell-on) and the Chinese landed price",
     "venue": "the Camara Nacional de Acuacultura's export record and the private assessments",
     "why": "Ecuador is the world's largest farmed-shrimp exporter and China is the dominant "
            "buyer; the VOLUME is published monthly and free, the PRICE is assessed privately",
     "regime": "spot export sales with a heavily concentrated destination mix",
     "route": "USDCNH carries the Chinese demand state; CORN and SOYBEAN carry the feed-ration "
              "cost leg; the shrimp price itself is UNMEASURED and named rather than invented",
     "proxies": ("USDCNH", "CORN", "SOYBEAN")},
    {"name": "The banana box price (43 lb) and the official precio minimo de sustentacion",
     "venue": "the MAG Acuerdo Ministerial in the Registro Oficial, plus the spot market",
     "why": "an ADMINISTERED MINIMUM PRICE on roughly a quarter of world banana trade, set "
            "annually and published; there is no banana contract anywhere for it to price against",
     "regime": "administered floor with a spot market trading above and below it",
     "route": "SUGAR and COFARA carry the tropical-softs complex as the only lawful carrier, and "
              "the pack DECLARES that leg weak by construction rather than dressing it up",
     "proxies": ("SUGAR", "COFARA")},
    {"name": "Domestic regulated fuel prices and the subsidy bill (Extra, Ecopais, diesel, LPG)",
     "venue": "Decreto Ejecutivo in the Registro Oficial; the price bands of Decreto 1183 (2021)",
     "why": "the subsidy is the largest single discretionary line in the budget and every attempt "
            "to cut it since 2019 has produced a national strike that shut in production; the "
            "administered price is the trigger variable and it is not a broker symbol",
     "regime": "administered with monthly bands since 2021, repeatedly suspended and reset",
     "route": "XTIUSD carries the import cost the subsidy is computed against and XBRUSD the "
              "export revenue on the other side of the same budget line",
     "proxies": ("XTIUSD", "XBRUSD")},
    {"name": "Spot LNG and the emergency generation barges the grid leases in a drought",
     "venue": "international spot LNG and the CELEC emergency-generation tenders",
     "why": "when the reservoirs fail the country buys thermal fuel and leases generation at "
            "spot; the tender prices are published but the fuel is not a quoted symbol here",
     "regime": "emergency procurement under decreed exception",
     "route": "XNGUSD carries the molecule and XTIUSD the liquid fuels the barges actually burn",
     "proxies": ("XNGUSD", "XTIUSD")},
)

# --------------------------------------------------------------------------- the central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "Banco Central del Ecuador (BCE)",
    "framework": "peg",
    "policy_instrument": "NONE THAT MOVES A RATE. Under full dollarisation the BCE has no policy "
                         "rate, no open-market operation and no discount window. Its instruments "
                         "are the four-system reserve accounting (Sistema de Canje, Sistema de "
                         "Reserva Financiera, Sistema de Operaciones and Sistema de Reserva de "
                         "Inversion), the payment system it clears, and the statistics it "
                         "publishes. Interest rate CEILINGS are set by the Junta de Politica y "
                         "Regulacion Monetaria, which is a government body, not this bank",
    "mandate": "administer the dollarisation regime, run the national payment system and publish "
               "the monetary and balance-of-payments statistics; the Constitution of 2008 placed "
               "monetary policy formulation with the Executive, and the 2021 Ley de Defensa de la "
               "Dolarizacion restored a measure of BCE autonomy and PROHIBITED it from financing "
               "the Treasury -- the single most important institutional break in the modern series",
    "decision_rule": "THERE IS NO DECISION. No meeting sets a rate, so this pack mints NO "
                     "policy-surprise cells and says so rather than manufacturing an event from "
                     "a publication date (L1.28a). The nearest thing to a scheduled monetary "
                     "event is the MONTHLY Informacion Estadistica Mensual and the weekly "
                     "reserve print",
    "decision_calendar_rule": "not applicable: no rate-setting calendar exists. The pack's "
                              "scheduled-event lattice is the statistics calendar, the Registro "
                              "Oficial decree stream and the IMF review dates",
    "decision_dates": (),
    "dates_status": "NONE EXIST, DELIBERATELY (L1.28a). A dollarised economy has no policy "
                    "decision to be surprised by. Writing a decision calendar here would be "
                    "inventing the one institution this country abolished in 2000",
    "decision_time_utc": "00:00",
    "announce_local": "not applicable; the BCE's Informacion Estadistica Mensual and the weekly "
                      "reserve tables land inside the Quito business day",
    "dst_rule": "NONE. Continental Ecuador is UTC-5 all year and the Galapagos are UTC-6; the "
                "country has never observed daylight saving, so every session window in this "
                "pack has the same UTC boundary in January and in July",
    "minutes_lag_days": 0,
    "publication_classes": ("informacion_estadistica_mensual", "boletin_de_reservas_semanal",
                            "balanza_de_pagos_trimestral", "cuentas_nacionales_trimestrales",
                            "remesas_trimestrales", "estadisticas_monetarias_y_financieras",
                            "reporte_de_pobreza_y_desigualdad"),
    "policy_rate_series": "NONE: there is no policy rate",
    "expected_rate_series": "UNMEASURED and unmeasurable: there is no rate to expect",
    "consensus_proxy": "for the FISCAL and CREDIT questions the pack uses the MEF's own "
                       "Programacion Fiscal, the IMF EFF review documents and the local "
                       "consultancies (Analisis Semanal, CORDES) as the stated consensus",
    "consensus_proxy_trap": "NEVER read a US FOMC decision as Ecuador's policy event. The dollar "
                            "rate IS Ecuador's rate, but it is set for another country's cycle "
                            "and arrives here as an exogenous shock, not as a domestic surprise. "
                            "A study that treats FOMC days as Ecuadorian policy days is "
                            "measuring the dollar and labelling it Ecuador",
    "reserves_clock": "the BCE publishes Reservas Internacionales WEEKLY -- and under "
                      "dollarisation reserves are not a defence fund but the COVER FOR THE "
                      "BANKING SYSTEM'S OWN DEPOSITS, which is a solvency read rather than an "
                      "intervention read and is why this row matters more here than anywhere else",
    "programme": "IMF Extended Fund Facility: a 2019 EFF that collapsed, a 2020 EFF completed in "
                 "2022, and a NEW 48-month EFF of about US$4bn approved 2024-05-31. The IMF "
                 "REVIEW CALENDAR is this country's substitute for a policy calendar, and it is "
                 "published",
    "off_cycle": ("2021-05 the Ley de Defensa de la Dolarizacion reformed the BCE's governance "
                  "and barred Treasury financing -- a structural break, not a decision",
                  "the Junta de Politica y Regulacion Financiera changes interest-rate CEILINGS "
                  "by resolution, which is the nearest thing to an administered rate move and is "
                  "invisible to any study looking for a central-bank announcement"),
    "root": "https://www.bce.fin.ec",
}

# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "ICE Brent settlement -- the benchmark Oriente and Napo are formula-priced against",
     "local": "19:30 Europe/London", "time_utc": "19:30", "time_utc_dst": "18:30",
     "dst_rule": "GMT/BST",
     "instruments": ("XBRUSD", "XTIUSD"), "window_minutes": 30,
     "why": "Ecuadorian export cargoes are sold at a differential to a published benchmark; the "
            "differential is not quoted here, so the benchmark settlement is the executable leg"},
    {"name": "NYMEX WTI settlement -- the US Gulf leg Ecuadorian heavy sour competes into",
     "local": "14:30 America/New_York", "time_utc": "19:30", "time_utc_dst": "18:30",
     "dst_rule": "US Eastern", "instruments": ("XTIUSD", "XBRUSD"), "window_minutes": 30,
     "why": "PADD 3 and PADD 5 refiners are the marginal buyers of Oriente; when Venezuelan Merey "
            "returns or Canadian heavy arrives, this is the leg the substitution shows up in"},
    {"name": "EP Petroecuador export cargo award and the monthly export report",
     "local": "published inside the Quito business day", "time_utc": "20:00",
     "time_utc_dst": "20:00", "dst_rule": "none: Ecuador is UTC-5 all year",
     "instruments": ("XBRUSD", "XTIUSD"), "window_minutes": 120,
     "why": "the physical gate: awarded cargoes and the monthly exported volume are the count "
            "that a force-majeure declaration eventually shows up in"},
    {"name": "CENACE daily dispatch and the published rationing schedule",
     "local": "the schedule for the following day is posted in the afternoon",
     "time_utc": "21:00", "time_utc_dst": "21:00", "dst_rule": "none: UTC-5 all year",
     "instruments": ("XNGUSD", "XTIUSD", "XCUUSD"), "window_minutes": 180,
     "why": "during a rationing episode the NEXT DAY'S LOST LOAD is published the afternoon "
            "before, which makes it one of the few genuinely forward-looking physical series on "
            "this desk"},
    {"name": "LBMA gold price auction (the Fruta del Norte and informal-gold benchmark)",
     "local": "15:00 Europe/London", "time_utc": "15:00", "time_utc_dst": "14:00",
     "dst_rule": "GMT/BST", "instruments": ("XAUUSD",), "window_minutes": 15,
     "why": "Ecuadorian gold is sold against the benchmark; the informal Amazonian lane prices "
            "off the same number through the Peruvian and Colombian border markets"},
    {"name": "LME official settlement (copper) -- the price Mirador concentrate sells against",
     "local": "12:00-13:00 Europe/London ring", "time_utc": "12:00", "time_utc_dst": "11:00",
     "dst_rule": "GMT/BST", "instruments": ("XCUUSD",), "window_minutes": 60,
     "why": "Mirador ships concentrate to Chinese smelters on an exchange-linked formula; the "
            "mine-gate price is never quoted and the exchange settlement is"},
    {"name": "ICE London cocoa settlement -- the cacao fino de aroma reference",
     "local": "16:30 Europe/London", "time_utc": "16:30", "time_utc_dst": "15:30",
     "dst_rule": "GMT/BST", "instruments": ("UKCOCOA", "USCOCOA"), "window_minutes": 30,
     "why": "Ecuadorian cacao sells at a PREMIUM to the terminal market for the fino de aroma "
            "fraction and at a differential for the CCN-51 bulk; both are quoted off this number"},
    {"name": "Guayaquil container terminal gate and the APG monthly throughput bulletin",
     "local": "continuous; the port authority publishes monthly",
     "time_utc": "15:00", "time_utc_dst": "15:00", "dst_rule": "none: UTC-5 all year",
     "instruments": ("UKCOCOA", "USCOCOA", "SUGAR"), "window_minutes": 180,
     "why": "the banana, the shrimp and the cacao all leave through the same gate, so a security "
            "or labour event at Guayaquil is a simultaneous shock to three export series"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "BCE Informacion Estadistica Mensual release", "kind": "day_of_month",
     "days": (25, 26, 27, 28, 29, 30), "roll": "next", "window_utc": ("15:00", "22:00"),
     "instruments": ("USDBRL", "USDMXN", "US500"),
     "why": "the monthly statistical bulletin is the nearest thing this country has to a "
            "scheduled macro release, and it carries the remittance and deposit series"},
    {"name": "INEC indice de precios al consumidor", "kind": "day_of_month",
     "days": (5, 6, 7, 8), "roll": "next", "window_utc": ("15:00", "21:00"),
     "instruments": ("USDBRL", "US500"),
     "why": "a CPI in a dollarised economy is a RELATIVE-PRICE read, not a monetary one; it "
            "measures how far the real exchange rate has drifted, which is the competitiveness "
            "channel that replaces the nominal one"},
    {"name": "Camara Nacional de Acuacultura monthly shrimp export volume", "kind": "day_of_month",
     "days": (12, 13, 14, 15, 16, 17, 18), "roll": "next", "window_utc": ("15:00", "22:00"),
     "instruments": ("USDCNH", "CORN", "SOYBEAN"),
     "why": "volume by destination, monthly, free -- the demand read on the largest farmed-shrimp "
            "exporter in the world, with China's share as the conditioner"},
    {"name": "EP Petroecuador monthly production and export report", "kind": "day_of_month",
     "days": (20, 21, 22, 23, 24, 25), "roll": "next", "window_utc": ("15:00", "22:00"),
     "instruments": ("XBRUSD", "XTIUSD"),
     "why": "the physical count that a pipeline outage or a field shut-in eventually appears in; "
            "the fast half of the same mechanism is the force-majeure declaration itself"},
    {"name": "Month-end Petroecuador cargo lifting and the Treasury's oil receipts",
     "kind": "month_end", "roll": "previous", "window_utc": ("15:00", "21:00"),
     "instruments": ("XBRUSD", "US500"),
     "why": "the state's single largest revenue line settles on the lifting schedule; a missed "
            "cargo is a fiscal event in a country with no central bank to bridge it"},
    {"name": "Quarter-end IMF review and disbursement windows", "kind": "quarter_end",
     "roll": "previous", "window_utc": ("14:00", "21:00"),
     "instruments": ("USDBRL", "USDMXN", "US500"),
     "why": "with no policy calendar, the EFF review schedule IS the scheduled-event calendar of "
            "the Ecuadorian sovereign, and each review has a published staff report"},
    {"name": "Fiscal year end (31 December) and the Presupuesto General del Estado",
     "kind": "fiscal_year_end", "roll": "previous", "window_utc": ("15:00", "22:00"),
     "instruments": ("XBRUSD", "XAUUSD"),
     "why": "the budget year is the calendar year and it is built on an ASSUMED oil price; the "
            "gap between the assumption and the realised strip is the fiscal shock variable"},
    {"name": "Banana minimum-support-price Acuerdo Ministerial (annual, before the season)",
     "kind": "week_of_month", "weekday": 3, "week_of_month": 2, "roll": "next",
     "window_utc": ("15:00", "21:00"), "instruments": ("SUGAR", "COFARA"),
     "why": "an administered price on a quarter of world banana trade, set once a year by "
            "ministerial agreement and published in the Registro Oficial"},
)

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Bolsa de Valores de Quito and Bolsa de Valores de Guayaquil (ECUINDEX)",
     "index_symbols": (),
     "open_local": "09:30", "close_local": "16:00", "open_utc": "14:30", "close_utc": "21:00",
     "dst_rule": "none: America/Guayaquil is UTC-5 all year, so the session's UTC window is "
                 "identical in January and July -- rare on this desk and worth using",
     "auction": "continuous trading with a predominantly fixed-income order book",
     "expiry_rule": "there is no listed derivatives market and therefore no expiry clock to mine",
     "holidays": "the national feriado calendar with the traslado rule of the Codigo del Trabajo",
     "notes": "NO CFD IS QUOTED on any Ecuadorian index, so the bourse enters only as a "
              "transmission target and an actor observable. The board is dominated by corporate "
              "and titularizacion paper: the equity float is small enough that the exchange is a "
              "FUNDING venue rather than a price-discovery one, and the pack treats it as such"},
    {"name": "The dollarised banking and payment system cleared by the BCE",
     "index_symbols": (), "open_local": "09:00", "close_local": "16:00",
     "open_utc": "14:00", "close_utc": "21:00", "dst_rule": "none: UTC-5 all year",
     "auction": "none; the BCE clears the Sistema de Pagos Interbancarios and publishes the "
                "aggregate balances",
     "expiry_rule": "no expiry; the reserve and deposit prints are the clock",
     "holidays": "the banking calendar, which follows the feriado table",
     "notes": "THE VENUE THAT MATTERS MOST HERE AND IS LEAST LIKE A MARKET. With no lender of "
              "last resort, the deposit base and the reserve cover ARE the financial-stability "
              "state, and both are published -- weekly reserves, monthly deposits by bank"},
    {"name": "The physical export gate: Guayaquil, Posorja, Puerto Bolivar, Manta and Esmeraldas",
     "index_symbols": (), "open_local": "00:00", "close_local": "23:59",
     "open_utc": "05:00", "close_utc": "04:59", "dst_rule": "none: UTC-5 all year",
     "auction": "none; the Autoridad Portuaria and the concessionaires publish throughput",
     "expiry_rule": "no expiry; the sailing schedule and the OCP/SOTE pumping schedule are clocks",
     "holidays": "ports work through the national calendar; a strike or a raid is not a holiday",
     "notes": "POSORJA OPENED IN 2019 as a DP World deep-water terminal downstream of Guayaquil, "
              "a dated change in Ecuadorian container logistics. Esmeraldas is the CRUDE gate at "
              "the end of both pipelines and Puerto Bolivar is the BANANA gate: three different "
              "commodities, three different terminals, three different shock profiles"},
)

SESSION_WINDOWS: tuple[dict[str, Any], ...] = (
    {"name": "ec_quito_session", "start_utc": "14:30", "end_utc": "21:00",
     "notes": "the domestic business day, UTC-5 all year; the ministries, the BCE and the "
              "Registro Oficial all publish inside it"},
    {"name": "ec_crude_benchmark", "start_utc": "18:00", "end_utc": "20:00",
     "notes": "the Brent and WTI settlement band the export grades are formula-priced against"},
    {"name": "ec_cenace_schedule", "start_utc": "20:00", "end_utc": "22:00",
     "notes": "the afternoon in which the following day's rationing schedule is published "
              "during an electricity emergency -- a rare genuinely forward-looking physical print"},
    {"name": "ec_guayaquil_gate", "start_utc": "12:00", "end_utc": "23:00",
     "notes": "the container-terminal working window at the port that ships the bananas, the "
              "shrimp and the cacao, and through which the cocaine leaves"},
    {"name": "ec_london_softs", "start_utc": "09:30", "end_utc": "16:30",
     "notes": "the London cocoa and metals session, which prices an Ecuadorian headline hours "
              "before Quito opens -- the reason a Quito-session study measures the echo"},
)

RELEASE_CLASSES: tuple[dict[str, Any], ...] = (
    {"name": "BCE Informacion Estadistica Mensual", "cadence": "monthly", "time_utc": "20:00",
     "source": "Banco Central del Ecuador", "actual_series": "BCE:iem",
     "expected_series": "n/a",
     "notes": "the whole monetary and external account in one bulletin: deposits, credit, "
              "remittances, trade by product, and the oil export volume and value"},
    {"name": "BCE weekly international reserves", "cadence": "weekly", "time_utc": "20:00",
     "source": "Banco Central del Ecuador", "actual_series": "BCE:reservas_internacionales",
     "expected_series": "n/a",
     "notes": "under dollarisation this is the COVER FOR THE DEPOSIT BASE, not a war chest; it "
              "is the fastest solvency read the country publishes"},
    {"name": "INEC indice de precios al consumidor", "cadence": "monthly", "time_utc": "16:00",
     "source": "INEC", "actual_series": "INEC:ipc", "expected_series": "n/a",
     "notes": "a relative-price series in a dollarised economy: it measures real-exchange-rate "
              "drift against Colombia and Peru rather than a monetary impulse"},
    {"name": "EP Petroecuador monthly production and export volumes", "cadence": "monthly",
     "time_utc": "20:00", "source": "EP Petroecuador",
     "actual_series": "PETRO:produccion_y_exportacion", "expected_series": "n/a",
     "notes": "the counted barrels, by field and by grade; the force-majeure declarations are "
              "the fast half of the same mechanism and arrive weeks earlier"},
    {"name": "Camara Nacional de Acuacultura monthly shrimp exports", "cadence": "monthly",
     "time_utc": "20:00", "source": "Camara Nacional de Acuacultura",
     "actual_series": "CNA:exportaciones_camaron", "expected_series": "n/a",
     "notes": "volume and value by destination; China's share is the demand read and the "
              "single most informative export series in the country"},
    {"name": "ACORBANEC and AEBE weekly and monthly banana export boxes", "cadence": "weekly",
     "time_utc": "20:00", "source": "ACORBANEC / AEBE",
     "actual_series": "ACORBANEC:cajas_exportadas", "expected_series": "n/a",
     "notes": "box counts by destination against the official minimum price; one of the few "
              "WEEKLY physical export series on this desk"},
    {"name": "ANECACAO monthly cacao export volumes", "cadence": "monthly", "time_utc": "20:00",
     "source": "ANECACAO", "actual_series": "ANECACAO:exportaciones_cacao",
     "expected_series": "n/a",
     "notes": "tonnes by grade (fino de aroma versus CCN-51 bulk) and by destination, against a "
              "liquid terminal contract -- the cleanest soft-commodity link in the pack"},
    {"name": "CENACE rationing schedule and daily national demand", "cadence": "daily",
     "time_utc": "21:00", "source": "CENACE / ARCERNNR",
     "actual_series": "CENACE:demanda_y_racionamiento", "expected_series": "n/a",
     "notes": "during an emergency the FOLLOWING DAY'S cuts are published by province and hour; "
              "outside one, the daily demand and hydro dispatch still publish"},
    {"name": "SENAE customs export and import records", "cadence": "monthly", "time_utc": "20:00",
     "source": "Servicio Nacional de Aduana del Ecuador",
     "actual_series": "SENAE:comercio_exterior", "expected_series": "n/a",
     "notes": "the customs mirror for every physical claim in this pack; VOLUME is the field to "
              "use because declared VALUE re-prices the commodity and calls it supply"},
    {"name": "Registro Oficial decree stream (estados de excepcion, fuel decrees, tariffs)",
     "cadence": "daily", "time_utc": "22:00", "source": "Registro Oficial",
     "actual_series": "RO:decretos_ejecutivos", "expected_series": "n/a",
     "notes": "the gazette is this country's event tape: every state of exception, every fuel "
              "price change and every ministerial banana price arrives here with a number"},
    {"name": "Ministerio de Economia y Finanzas fiscal and debt bulletins", "cadence": "monthly",
     "time_utc": "21:00", "source": "MEF", "actual_series": "MEF:deuda_publica",
     "expected_series": "n/a",
     "notes": "the debt stock, the arrears and the oil-price assumption behind the budget"},
    {"name": "IMF EFF review and disbursement", "cadence": "quarterly", "time_utc": "19:00",
     "source": "International Monetary Fund", "actual_series": "IMF:eff_reviews",
     "expected_series": "n/a",
     "notes": "with no policy calendar, this is the Ecuadorian sovereign's scheduled-event clock"},
)
# --------------------------------------------------------------------------- the calendars
#: THE FIXED NATIONAL FERIADOS of article 65 of the Codigo del Trabajo. The fourth field is
#: whether the TRASLADO rule applies: the 2016 reform (Ley Organica para la Promocion del Trabajo
#: Juvenil) moves most feriados off midweek, but EXPRESSLY EXEMPTS 1 January, the two Carnaval
#: days, Viernes Santo and 25 December, which stay where the calendar puts them.
FIXED_NATIONAL: tuple[tuple[int, int, str, bool], ...] = (
    (1, 1, "Ano Nuevo", False),
    (5, 1, "Dia del Trabajo", True),
    (5, 24, "Batalla del Pichincha", True),
    (8, 10, "Primer Grito de Independencia", True),
    (10, 9, "Independencia de Guayaquil", True),
    (11, 2, "Dia de los Difuntos", True),
    (11, 3, "Independencia de Cuenca", True),
    (12, 25, "Navidad", False),
)
#: The movable national feriados, as OFFSETS FROM EASTER. None of the three is trasladable.
EASTER_NATIONAL: tuple[tuple[int, str], ...] = (
    (-48, "Lunes de Carnaval"),
    (-47, "Martes de Carnaval"),
    (-2, "Viernes Santo"),
)
#: THE REGIONAL AND INDIGENOUS CALENDAR. These are NOT national market closures: they are the days
#: a PROVINCE or a NATIONALITY stops. Quito closes on 6 December and Guayaquil on 24 July, and the
#: Kichwa sierra keeps the four solar raymis, which is the calendar the highland roads and the
#: flower and dairy labour force actually run on. The Shuar chonta festival is Amazonian and its
#: date follows the harvest rather than the solar calendar -- carried with that caveat.
REGIONAL_DAYS: tuple[tuple[int | None, int, int, str, str], ...] = (
    (None, 7, 24, "Guayaquil y Guayas", "Natalicio de Simon Bolivar"),
    (None, 12, 6, "Quito y Pichincha", "Fundacion de Quito"),
    (None, 3, 21, "sierra kichwa (Imbabura, Cotopaxi, Chimborazo)", "Pawkar Raymi (equinoccio)"),
    (None, 6, 21, "sierra kichwa (Otavalo, Cotacachi, Saraguro)", "Inti Raymi (solsticio)"),
    (None, 9, 21, "sierra kichwa (Imbabura, Canar)", "Kulla Raymi (equinoccio)"),
    (None, 12, 21, "sierra kichwa (Chimborazo, Canar)", "Kapak Raymi (solsticio)"),
    (None, 4, 15, "Amazonia shuar y achuar (Morona Santiago, Zamora Chinchipe)",
     "Uwi Nampesma, la fiesta de la chonta [DATE APPROXIMATE: it follows the uwi harvest, not "
     "the solar calendar -- confirm against the nationality's own convocatoria]"),
    (None, 2, 12, "Amazonia (Orellana, Sucumbios, Napo, Pastaza)", "Dia de la Amazonia"),
)
#: ONE-OFF CLOSURES DECREED BY THE EXECUTIVE. The April 2024 pair is the sharpest single fact in
#: this pack's power domain: the state declared two NATIONAL NON-WORKING DAYS to save electricity.
DECLARED_CLOSURES: dict[date, str] = {
    date(2024, 4, 18): "dia no laborable decreed nationally to reduce electricity demand during "
                       "the April 2024 rationing emergency [DECREE_REPORTED -- confirm the "
                       "decree number in registroficial.gob.ec before a cell is compiled on it]",
    date(2024, 4, 19): "second dia no laborable of the April 2024 power emergency "
                       "[DECREE_REPORTED -- same caveat]",
}

#: THE PIPELINE AND WELLHEAD INTERRUPTION RECORD. Every row is a DECLARED, DATED physical supply
#: interruption of Ecuadorian crude: a rupture, a pre-emptive shutdown against the advancing
#: erosion front, or a national strike that shut in the fields. `PRESS_REPORTED` on every row
#: means exactly that -- no Registro Oficial or operator hecho relevante citation is attached yet,
#: so these rows may MINT HYPOTHESES and may never promote a cell (see ACCESS_CONSTRAINTS).
PIPELINE_EPISODES: tuple[tuple[date, date, str, str, str], ...] = (
    (date(2019, 10, 3), date(2019, 10, 13), "Oriente wellheads and the Amazonian blocks",
     "paro nacional after Decreto 883 removed the fuel subsidy; fields occupied and shut in; "
     "force majeure declared on export cargoes", "PRESS_REPORTED"),
    (date(2020, 4, 7), date(2020, 5, 7), "SOTE and OCP at the Coca river crossing",
     "BOTH pipelines ruptured after the regressive erosion front reached the crossings two "
     "months after the San Rafael waterfall collapsed; pumping suspended and force majeure "
     "declared", "PRESS_REPORTED"),
    (date(2021, 12, 2), date(2021, 12, 22), "OCP at the Piedra Fina / Coca erosion front",
     "OCP suspended pumping as the erosion undercut the right of way; Petroecuador followed with "
     "a force-majeure declaration on exports", "PRESS_REPORTED"),
    (date(2022, 1, 28), date(2022, 2, 6), "SOTE at Piedra Fina (Cayambe-Coca reserve)",
     "a landslide ruptured the state pipeline and spilled crude into the Coca river; pumping "
     "suspended and the Amazonian communities downstream filed protective actions",
     "PRESS_REPORTED"),
    (date(2022, 6, 13), date(2022, 6, 30), "Amazonian blocks (Orellana, Sucumbios, Pastaza)",
     "the CONAIE paro nacional; wells occupied and shut in, national production fell by roughly "
     "two thirds at its worst and force majeure was declared", "PRESS_REPORTED"),
    (date(2023, 6, 20), date(2023, 7, 4), "SOTE and OCP at the Coca erosion front",
     "heavy rain advanced the erosion front again and both operators moved to the contingency "
     "bypass; exports curtailed", "PRESS_REPORTED"),
)
#: THE ELECTRICITY RATIONING EPISODES, with the published maximum daily cut. Drought at Coca Codo
#: Sinclair on the Coca river and at the Paute-Mazar complex forced CENACE and the distributors to
#: publish nationwide schedules by province and by hour. `max_hours` is the headline figure at the
#: episode's worst, which is what a load-loss cell conditions on.
RATIONING_EPISODES: tuple[tuple[date, date, float, str, str], ...] = (
    (date(2023, 10, 27), date(2023, 12, 20), 8.0,
     "the first national rationing round: low hydrology at Mazar and Coca Codo with the thermal "
     "park unavailable; published schedules by distributor", "PRESS_REPORTED"),
    (date(2024, 4, 15), date(2024, 4, 21), 12.0,
     "the April emergency: Mazar at minimum operating level, Colombian imports cut off, and TWO "
     "NATIONAL NON-WORKING DAYS decreed to shed demand", "PRESS_REPORTED"),
    (date(2024, 9, 23), date(2024, 12, 20), 14.0,
     "the long round: the worst drought in six decades, cuts of up to fourteen hours a day "
     "through October and November, emergency generation leased at spot", "PRESS_REPORTED"),
)
#: THE ITT / YASUNI RECORD. A sovereign electorate voted a producing field shut, on a published
#: ballot, with a dated compliance deadline. There is nothing like it anywhere else in this book.
ITT_EVENTS: tuple[tuple[date, str, str], ...] = (
    (date(2013, 8, 15), "the Yasuni-ITT trust initiative is abandoned and drilling authorised",
     "PRESS_REPORTED"),
    (date(2016, 9, 1), "first ITT production from the Tiputini field in Block 43",
     "PRESS_REPORTED"),
    (date(2023, 5, 9), "the Corte Constitucional clears the ITT question for the ballot",
     "PRESS_REPORTED"),
    (date(2023, 8, 20), "REFERENDUM: a majority votes YES to leave the ITT crude in the ground, "
                        "on the same day as the Choco Andino mining question in Quito and the "
                        "snap presidential first round", "PRESS_REPORTED"),
    (date(2024, 8, 31), "the one-year compliance deadline for the phased shutdown of Block 43",
     "PRESS_REPORTED"),
)
#: THE SOVEREIGN CREDIT AND PROGRAMME RECORD: default, restructuring, the two debt-for-nature
#: swaps and the IMF clock. Each row is a timestamp with a published document behind it.
SOVEREIGN_EVENTS: tuple[tuple[date, str, str], ...] = (
    (date(1999, 9, 28), "default on the Brady bonds -- the first sovereign to default on Bradys",
     "PRESS_REPORTED"),
    (date(2000, 1, 9), "dollarisation announced; the sucre is retired during 2000",
     "PRESS_REPORTED"),
    (date(2008, 12, 12), "default BY CHOICE on the 2012 and 2030 Global bonds after a debt audit "
                         "declared them illegitimate", "PRESS_REPORTED"),
    (date(2009, 6, 1), "buyback of the defaulted Globals at roughly a third of face value",
     "PRESS_REPORTED"),
    (date(2020, 8, 31), "restructuring of about US$17.4bn of Global bonds completed; new 2030, "
                        "2035 and 2040 step-up bonds issued", "PRESS_REPORTED"),
    (date(2023, 5, 9), "the Galapagos debt-for-nature swap: roughly US$1.6bn of old bonds retired "
                       "for about US$644m, the largest such transaction on record at the time",
     "PRESS_REPORTED"),
    (date(2024, 5, 31), "the IMF approves a new 48-month Extended Fund Facility of about US$4bn",
     "PRESS_REPORTED"),
    (date(2024, 12, 12), "a second, Amazon-focused debt-for-nature transaction of about US$1bn",
     "PRESS_REPORTED"),
)
#: THE POLITICAL AND SECURITY EVENT SERIES. Dated, published, and every one of them a candidate
#: conditioning state for the port, the crude and the sovereign legs.
POLITICAL_EVENTS: tuple[tuple[date, str, str], ...] = (
    (date(2019, 10, 1), "Decreto 883 removes the fuel subsidy", "PRESS_REPORTED"),
    (date(2019, 10, 13), "Decreto 883 is repealed after eleven days of national strike",
     "PRESS_REPORTED"),
    (date(2021, 5, 24), "Lasso takes office; the Ley de Defensa de la Dolarizacion follows",
     "PRESS_REPORTED"),
    (date(2022, 6, 30), "the June paro ends with a negotiated fuel-price cut", "PRESS_REPORTED"),
    (date(2023, 5, 17), "MUERTE CRUZADA: Lasso dissolves the Asamblea Nacional and calls snap "
                        "elections, governing by decree-law in the interval", "PRESS_REPORTED"),
    (date(2023, 8, 9), "the assassination of presidential candidate Fernando Villavicencio, "
                       "eleven days before the first round", "PRESS_REPORTED"),
    (date(2023, 11, 23), "Noboa takes office for the remainder of the dissolved term",
     "PRESS_REPORTED"),
    (date(2024, 1, 7), "the escape of a cartel leader from the Regional prison in Guayaquil",
     "PRESS_REPORTED"),
    (date(2024, 1, 9), "INTERNAL ARMED CONFLICT declared by decree after a live-television "
                       "studio assault; twenty-two groups named as terrorist organisations and "
                       "the armed forces deployed to the ports and prisons", "PRESS_REPORTED"),
    (date(2024, 4, 21), "referendum on security and arbitration: the security questions pass and "
                        "the two economic questions fail", "PRESS_REPORTED"),
    (date(2024, 5, 1), "the Ecuador-China free trade agreement enters into force",
     "PRESS_REPORTED"),
    (date(2025, 5, 24), "Noboa inaugurated for a full four-year term after the April run-off",
     "PRESS_REPORTED"),
)


def easter(year: int) -> date:
    """Easter Sunday by the ANONYMOUS GREGORIAN ALGORITHM. Every movable date in this pack --
    Viernes Santo and the two Carnaval days -- is an offset from it, COMPUTED rather than typed,
    so the table extends to any year without anybody editing this file."""
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


def carnaval(year: int) -> tuple[date, date]:
    """Lunes and Martes de Carnaval: Easter minus 48 and 47 days. Unlike Peru's, BOTH are national
    feriados in Ecuador, and neither is trasladable -- Carnaval is the one long weekend the
    statute refuses to move."""
    base = easter(year)
    return base - timedelta(days=48), base - timedelta(days=47)


def good_friday(year: int) -> date:
    """Viernes Santo: Easter minus two. Jueves Santo is NOT a national feriado in Ecuador, which
    is a real difference from Peru and from Paraguay and is worth a cell of its own."""
    return easter(year) - timedelta(days=2)


def traslado(day: date) -> date:
    """THE TRASLADO RULE of article 65 of the Codigo del Trabajo as reformed in 2016.

    A feriado that falls on a TUESDAY is observed on the preceding Monday; one that falls on a
    WEDNESDAY or a THURSDAY is observed on the following Friday; one that falls on a SATURDAY is
    observed on the preceding Friday and one on a SUNDAY on the following Monday. Monday and
    Friday stay where they are. The statute is explicit that the rule does NOT touch 1 January,
    Carnaval or 25 December, and this function is therefore only ever applied to the dates whose
    `FIXED_NATIONAL` flag says so.

    THIS IS A DERIVED TABLE AND THAT IS THE POINT: a pack that typed the 2024, 2025 and 2026
    observed dates by hand could not extend to 2027 and could not tell a reader WHY a Monday in
    May is closed.
    """
    weekday = day.weekday()
    if weekday == 1:                       # Tuesday -> the Monday before
        return day - timedelta(days=1)
    if weekday in (2, 3):                  # Wednesday or Thursday -> the Friday after
        return day + timedelta(days=4 - weekday)
    if weekday == 5:                       # Saturday -> the Friday before
        return day - timedelta(days=1)
    if weekday == 6:                       # Sunday -> the Monday after
        return day + timedelta(days=1)
    return day


def statutory_holidays(year: int) -> dict[date, str]:
    """The feriados AT THEIR STATUTORY DATES, before any traslado. Kept separately because the
    statutory date is what a law, a contract and a historical newspaper refer to, while the
    OBSERVED date is what closes a bank -- and a study that conflates the two mislabels several
    days a year in every year since 2016."""
    out: dict[date, str] = {date(year, m, d): name for m, d, name, _mv in FIXED_NATIONAL}
    base = easter(year)
    for off, name in EASTER_NATIONAL:
        out[base + timedelta(days=off)] = name
    return dict(sorted(out.items()))


def national_holidays(year: int) -> dict[date, str]:
    """The OBSERVED national feriado table for a year: the fixed days moved by `traslado` where
    the statute allows it, the three Easter-derived days left where they fall, and the declared
    one-off closures. Two feriados that land on the same observed day are MERGED rather than one
    silently overwriting the other -- 2 and 3 November collide often and the merge is the honest
    record of it."""
    out: dict[date, str] = {}
    for m, d, name, movable in FIXED_NATIONAL:
        statutory = date(year, m, d)
        observed = traslado(statutory) if movable else statutory
        label = name if observed == statutory else f"{name} (trasladado desde el {statutory:%d-%m})"
        out[observed] = f"{out[observed]} y {label}" if observed in out else label
    base = easter(year)
    for off, name in EASTER_NATIONAL:
        day = base + timedelta(days=off)
        out[day] = f"{out[day]} y {name}" if day in out else name
    for day, name in DECLARED_CLOSURES.items():
        if day.year == year:
            out[day] = f"{out[day]} y {name}" if day in out else name
    return dict(sorted(out.items()))


def bank_holidays(year: int) -> dict[date, str]:
    """The banking calendar. Ecuadorian banks close on the observed national feriados and on
    nothing the bourse does not also close on, so the two tables coincide on weekdays."""
    return national_holidays(year)


def market_holidays(year: int) -> dict[date, str]:
    """Bolsa de Valores closed days: the observed national table on WEEKDAYS only. After the
    traslado rule very few feriados land on a weekend at all, which is exactly what the 2016
    reform was for -- and it means Ecuador loses FEWER sessions to the calendar than Peru does."""
    return {d: n for d, n in bank_holidays(year).items() if d.weekday() < 5}


def regional_days(year: int) -> dict[date, str]:
    """The provincial and indigenous calendar for a year. These close ROADS, PLANTATIONS and
    PROVINCES rather than the bourse, which is why they are a separate table: Quito's 6 December
    and the sierra's four raymis are labour-supply facts in the flower, dairy and highland
    construction economies and have no effect on a Guayaquil container gate."""
    out: dict[date, str] = {}
    for off, month, day, region, name in REGIONAL_DAYS:
        got = easter(year) + timedelta(days=off) if off is not None else date(year, month, day)
        out[got] = f"{name} ({region})"
    return dict(sorted(out.items()))


def is_market_holiday(day: date) -> bool:
    return day in market_holidays(day.year)


def moved_holidays(year: int) -> tuple[tuple[date, date, str], ...]:
    """MECHANISM FUNCTION: every feriado whose OBSERVED date differs from its STATUTORY date in
    this year, as `(statutory, observed, name)`. This is the trasladable half of the calendar and
    it is where a bridge weekend -- a puente -- is manufactured by law."""
    out: list[tuple[date, date, str]] = []
    for m, d, name, movable in FIXED_NATIONAL:
        if not movable:
            continue
        statutory = date(year, m, d)
        observed = traslado(statutory)
        if observed != statutory:
            out.append((statutory, observed, name))
    return tuple(out)


def long_weekends(year: int) -> tuple[date, ...]:
    """The Mondays and Fridays the traslado rule creates. A three-day weekend is a real liquidity
    and logistics fact in an export economy: the banana and shrimp packing weeks shorten and the
    Guayaquil gate queues on the day either side."""
    return tuple(sorted(d for d in national_holidays(year)
                        if d.weekday() in (0, 4) and d.weekday() < 5))


def is_pipeline_outage(day: date) -> bool:
    """True when `day` falls inside a DECLARED pipeline rupture, pre-emptive shutdown or
    strike-driven wellhead shut-in. This is the conditioning state of EC-C and EC-B."""
    return any(lo <= day <= hi for lo, hi, _s, _w, _st in PIPELINE_EPISODES)


def pipeline_outage_days(start: date, end: date) -> list[date]:
    """Every day inside [start, end] that falls in a declared crude-interruption episode."""
    out: list[date] = []
    day = start
    while day <= end:
        if is_pipeline_outage(day):
            out.append(day)
        day += timedelta(days=1)
    return out


def pipeline_episodes(status: str = "PRESS_REPORTED") -> tuple[tuple[date, date, str, str], ...]:
    """The declared crude-interruption episodes at or above a confidence label. Nothing in this
    pack claims GAZETTE_VERIFIED, and `pipeline_episodes("GAZETTE_VERIFIED")` returning empty is
    the measurement of that, not a bug."""
    order = {"PRESS_REPORTED": 0, "OPERATOR_CONFIRMED": 1, "GAZETTE_VERIFIED": 2}
    floor = order.get(status, 0)
    return tuple((lo, hi, site, what) for lo, hi, site, what, st in PIPELINE_EPISODES
                 if order.get(st, 0) >= floor)


def rationing_state(day: date) -> tuple[float, str] | None:
    """MECHANISM FUNCTION: the published maximum daily outage hours in force on `day`, with the
    episode's description, or None when the grid was not rationing. A quantified, dated,
    SCHEDULED loss of industrial load is the rarest kind of real-economy shock there is."""
    for lo, hi, hours, what, _st in RATIONING_EPISODES:
        if lo <= day <= hi:
            return (hours, what)
    return None


def is_rationing_day(day: date) -> bool:
    return rationing_state(day) is not None


def rationing_days(year: int) -> int:
    """How many days of the year the grid was under a published rationing schedule."""
    lo, hi = date(year, 1, 1), date(year, 12, 31)
    total = 0
    day = lo
    while day <= hi:
        if is_rationing_day(day):
            total += 1
        day += timedelta(days=1)
    return total


def itt_regime(day: date) -> str:
    """Which side of the Yasuni referendum a date falls on: the production era, the post-ballot
    wind-down, or the post-deadline era. A cell on Ecuadorian crude supply that pools across
    2023-08-20 is measuring two different countries' supply decisions."""
    if day < date(2016, 9, 1):
        return "PRE_ITT_PRODUCTION"
    if day < date(2023, 8, 20):
        return "ITT_PRODUCING"
    if day < date(2024, 8, 31):
        return "POST_REFERENDUM_WIND_DOWN"
    return "POST_DEADLINE"


HOLIDAYS_RULE: dict[str, Any] = {
    "kind": "computed_from_statute_plus_decreed_table",
    "authority": "article 65 of the Codigo del Trabajo as reformed in 2016 by the Ley Organica "
                 "para la Promocion del Trabajo Juvenil, which introduced the traslado; one-off "
                 "dias no laborables are decreed by the Presidencia and published in the "
                 "Registro Oficial (registroficial.gob.ec)",
    "rule": "EIGHT fixed national days -- 1 Jan, 1 May, 24 May, 10 Aug, 9 Oct, 2 Nov, 3 Nov and "
            "25 Dec -- PLUS three EASTER-DERIVED days: Lunes and Martes de Carnaval (Easter minus "
            "48 and 47) and Viernes Santo (Easter minus 2), computed with the anonymous Gregorian "
            "algorithm in `easter(year)` and never typed. JUEVES SANTO IS NOT A FERIADO HERE, "
            "which is a real difference from Peru and Paraguay. THE TRASLADO RULE then moves the "
            "SIX trasladable days off midweek: Tuesday to the Monday before, Wednesday or "
            "Thursday to the Friday after, Saturday to the Friday before, Sunday to the Monday "
            "after -- and the statute EXEMPTS 1 January, both Carnaval days and 25 December, "
            "which never move. `traslado(day)` is that rule and `moved_holidays(year)` names "
            "every date it shifted. 2 and 3 November frequently collide after the move and the "
            "table MERGES the two names rather than losing one.",
    "years": (2024, 2025, 2026),
    "weekend": "Saturday and Sunday",
    "national_rule": "see `rule`; `national_holidays(year)` is the OBSERVED table and "
                     "`statutory_holidays(year)` the pre-traslado one",
    "market_rule": "the observed national table on weekdays; the Quito and Guayaquil bourses keep "
                   "the same UTC session in January and July because Ecuador has no daylight "
                   "saving and has never had it",
    "regional_rule": "`regional_days(year)`: Quito's 6 December, Guayaquil's 24 July and the four "
                     "Kichwa raymis, which close provinces and plantations rather than the bourse",
    "statute_break": "THE 2016 TRASLADO REFORM IS A REGIME BREAK in the closed-day series. Before "
                     "it a feriado stayed where the calendar put it; after it six of the eight "
                     "fixed days move, so the observed closure dates from 2017 onward are not "
                     "comparable with the earlier ones and a pooled holiday-liquidity study "
                     "mislabels several days a year on each side of the boundary",
    "table": {y: {d.isoformat(): n for d, n in national_holidays(y).items()}
              for y in (2024, 2025, 2026)},
    "status": {2024: "STATUTORY for the fixed days, COMPUTED for Carnaval and Viernes Santo, "
                     "DECREE_REPORTED for the two April power-emergency non-working days",
               2025: "STATUTORY and COMPUTED; no one-off decree carried",
               2026: "STATUTORY and COMPUTED; the Easter dates are computed and certain, and any "
                     "dia no laborable decreed for 2026 is not yet published"},
    "known_dates": {
        "2024-02-12": "Lunes de Carnaval (Easter 2024 is 31 March); never trasladable",
        "2024-11-01": "Dia de los Difuntos trasladado from Saturday 2 November to the Friday",
        "2025-03-03": "Lunes de Carnaval (Easter 2025 is 20 April)",
        "2025-05-02": "Dia del Trabajo trasladado from Thursday 1 May to the Friday",
        "2026-02-16": "Lunes de Carnaval (Easter 2026 is 5 April)",
        "2026-12-25": "Navidad, exempt from the traslado and fixed in every year",
    },
    "fn": market_holidays,
    "national_fn": national_holidays,
    "statutory_fn": statutory_holidays,
    "bank_fn": bank_holidays,
    "regional_fn": regional_days,
    "easter_fn": easter,
    "carnaval_fn": carnaval,
    "traslado_fn": traslado,
}
# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "BCE weekly international reserves and the four-system balance sheet",
     "root": "https://www.bce.fin.ec/informacioneconomica",
     "fields": ("reservas_internacionales", "sistema_de_canje", "sistema_de_reserva_financiera",
                "depositos_del_sector_publico"),
     "frequency": "weekly", "snapshot": "Friday", "publish_utc": "20:00", "lag_days": 5,
     "licence": "free, public", "available": True,
     "why": "UNDER DOLLARISATION RESERVES ARE COVER, NOT A WAR CHEST. There is no currency to "
            "defend; the number says how much of the banking system's and the Treasury's own "
            "dollar liabilities are actually backed. It is the closest thing this country has to "
            "a continuously published solvency state and no sibling pack has an analogue",
     "pit_warning": "the four-system presentation was REDEFINED by the 2021 Ley de Defensa de la "
                    "Dolarizacion; a level compared across that date is comparing two definitions"},
    {"name": "ASOBANCA and Superintendencia de Bancos deposit and liquidity series",
     "root": "https://www.superbancos.gob.ec/estadisticas/",
     "fields": ("depositos_a_la_vista", "depositos_a_plazo", "liquidez_estructural",
                "morosidad_por_segmento"),
     "frequency": "monthly", "snapshot": "month end", "publish_utc": "21:00", "lag_days": 30,
     "licence": "free, public", "available": True,
     "why": "with NO LENDER OF LAST RESORT a deposit outflow is not a liquidity event, it is a "
            "solvency event -- 1999 is the reference case. The monthly deposit series by bank is "
            "the only forward read on that, and the pack conditions its stress cells on it",
     "pit_warning": "MONTHLY and a month late, so it conditions a regime and never a week"},
    {"name": "MEF public debt stock, arrears and the oil-price budget assumption",
     "root": "https://www.finanzas.gob.ec/estadisticas-fiscales/",
     "fields": ("deuda_externa", "deuda_interna", "atrasos", "precio_del_petroleo_presupuestado"),
     "frequency": "monthly", "snapshot": "month end", "publish_utc": "21:00", "lag_days": 45,
     "licence": "free, public", "available": True,
     "why": "the budget is built on an assumed crude price and the gap to the realised strip is "
            "the fiscal shock; the ARREARS line is the honest measure of stress in an economy "
            "that cannot print, because it is what a government does instead of printing",
     "pit_warning": "arrears are restated frequently and the definition has changed; use the "
                    "vintage from the archive layer, never the current page"},
    {"name": "Camara Nacional de Acuacultura shrimp export volume by destination",
     "root": "https://www.cna-ecuador.com/estadisticas/",
     "fields": ("libras_exportadas", "valor_fob", "participacion_china", "participacion_ue"),
     "frequency": "monthly", "snapshot": "calendar month", "publish_utc": "20:00", "lag_days": 15,
     "licence": "free, public", "available": True,
     "why": "the demand read on the world's largest farmed-shrimp exporter, with the Chinese "
            "share broken out -- a monthly, free, counted physical series on a trade flow that "
            "is more than half concentrated in one buyer",
     "pit_warning": "the association restates the prior month when late declarations arrive; the "
                    "SENAE customs mirror is the reconciliation"},
    {"name": "CFTC Commitments of Traders: cocoa, sugar, coffee, corn and soybeans",
     "root": "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm",
     "fields": ("managed_money_long", "managed_money_short", "commercial_net", "open_interest"),
     "frequency": "weekly", "snapshot": "Tuesday", "publish_utc": "19:30", "lag_days": 3,
     "licence": "public domain (US government work)", "available": True,
     "why": "the executable softs' own positioning. An Ecuadorian cacao or banana supply event "
            "into a crowded managed-money long is a different trade from the same event into a "
            "flat book, and this is the only positioning series any leg of this pack has",
     "pit_warning": "Tuesday snapshot published Friday: a Wednesday port closure is invisible "
                    "until the following week's report"},
    {"name": "A CFTC or exchange-traded ECUADORIAN CURRENCY positioning series",
     "root": "", "fields": (), "frequency": "n/a", "snapshot": "", "publish_utc": "",
     "lag_days": 0, "licence": "", "available": False,
     "why": "DECLARED ABSENT AND UNCREATABLE: Ecuador has no currency. There is no forward, no "
            "future, no NDF and no COT contract, and there never will be while dollarisation "
            "holds. This is not a gap in the data, it is a property of the country",
     "pit_warning": "DOES NOT EXIST AND CANNOT. Ecuadorian currency positioning is not UNMEASURED, "
                    "it is UNDEFINED, and it is never proxied by the BRL or MXN COT legs, which "
                    "are positions in other countries' monetary policy"},
    {"name": "Ecuadorian sovereign bond holder composition and the local pension holdings",
     "root": "https://www.iess.gob.ec/",
     "fields": ("tenencia_biess_deuda_interna", "inversiones_del_iess",
                "certificados_de_tesoreria"),
     "frequency": "quarterly", "snapshot": "quarter end", "publish_utc": "21:00", "lag_days": 60,
     "licence": "free, public", "available": True,
     "why": "the IESS and its bank hold a large share of the domestic sovereign's paper, which "
            "makes the pension system and the Treasury the same balance sheet in a stress -- a "
            "captive-buyer structure a foreign-flow study would never see",
     "pit_warning": "quarterly, two months late and presented inconsistently across years"},
)

# --------------------------------------------------------------------------- terminology
#: THREE LANGUAGES, AND THE PACK MEANS IT. Spanish is the working language of the BCE, the
#: ministries, the bourse and the press. KICHWA and SHUAR are official for intercultural use under
#: article 2 of the 2008 constitution -- and the Amazonian oil-bloc consultations, the community
#: assemblies that vote a paro and the strike calendars that shut the wellheads happen in them.
#: `sumak kawsay` is in the constitution itself. A Spanish-only crawl of Ecuador reads Quito.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "EC-A": ("dolarización", "Banco Central del Ecuador", "reservas internacionales",
             "sistema de canje", "prestamista de última instancia", "Ley de Defensa de la "
             "Dolarización", "liquidez estructural", "coeficiente de liquidez doméstica",
             "Junta de Política y Regulación Financiera", "sucre", "feriado bancario",
             "kullki (kichwa: el dinero)", "encaje bancario"),
    "EC-B": ("crudo Oriente", "crudo Napo", "barriles por día", "Petroecuador",
             "exportación de crudo", "diferencial del crudo", "OPEP", "cuota de producción",
             "campo petrolero", "bloque petrolero", "canasta de crudo", "producción nacional",
             "yaku ukupi (kichwa: bajo el agua/la tierra)"),
    "EC-C": ("SOTE", "Oleoducto de Crudos Pesados", "OCP", "erosión regresiva",
             "río Coca", "cascada de San Rafael", "fuerza mayor", "rotura del oleoducto",
             "variante emergente", "bombeo suspendido", "derrame de petróleo",
             "Piedra Fina", "yaku (kichwa: el agua)", "entsa (shuar: el río)"),
    "EC-D": ("Yasuní", "bloque 43", "ITT", "Ishpingo Tambococha Tiputini", "consulta popular",
             "Corte Constitucional", "Consejo Nacional Electoral", "papeleta",
             "dejar el crudo bajo tierra", "pueblos en aislamiento voluntario", "Tagaeri",
             "Taromenane", "sacha (kichwa: la selva)", "sumak kawsay"),
    "EC-E": ("racionamiento eléctrico", "apagón", "cortes de energía", "CENACE",
             "Coca Codo Sinclair", "embalse de Mazar", "estiaje", "hidrología",
             "generación térmica", "barcazas de generación", "ARCERNNR", "CELEC EP",
             "demanda no abastecida", "horario de cortes"),
    "EC-F": ("deuda externa", "reestructuración", "bonos globales", "canje de deuda por "
             "naturaleza", "bono Galápagos", "riesgo país", "EMBI", "Fondo Monetario "
             "Internacional", "servicio ampliado del FMI", "atrasos", "default", "recompra de "
             "deuda", "cupón escalonado"),
    "EC-G": ("camarón", "acuacultura", "Cámara Nacional de Acuacultura", "libras exportadas",
             "vannamei", "piscina camaronera", "exportación a China", "precio en playa",
             "balanceado", "harina de pescado", "mancha blanca", "larva de camarón"),
    "EC-H": ("banano", "caja de banano", "precio mínimo de sustentación", "Acuerdo Ministerial",
             "ACORBANEC", "AEBE", "contrato de compraventa", "fruta de rechazo",
             "sigatoka negra", "Fusarium raza 4", "Puerto Bolívar", "El Oro",
             "hectáreas sembradas"),
    "EC-I": ("cacao", "cacao fino de aroma", "cacao nacional", "CCN-51", "ANECACAO",
             "premio de calidad", "grano seco", "quintales exportados", "monilla",
             "escoba de bruja", "molienda", "cacao arriba"),
    "EC-J": ("estado de excepción", "conflicto armado interno", "Guayaquil",
             "Autoridad Portuaria de Guayaquil", "contenedores movilizados", "incautación de "
             "droga", "narcotráfico", "toque de queda", "Posorja", "Contecon",
             "puerto de aguas profundas", "fuerzas armadas en el puerto"),
    "EC-K": ("subsidio a los combustibles", "Decreto 883", "bandas de precios",
             "diesel premium", "gasolina extra", "ecopaís", "gas licuado de petróleo",
             "paro nacional", "CONAIE", "levantamiento indígena", "mesa de diálogo",
             "minka (kichwa: el trabajo colectivo)", "paro de transportistas"),
    "EC-L": ("muerte cruzada", "Asamblea Nacional", "decreto ley", "consulta popular",
             "referéndum", "elecciones anticipadas", "segunda vuelta", "juicio político",
             "Registro Oficial", "decreto ejecutivo", "Tribunal Contencioso Electoral"),
    "EC-M": ("minería a gran escala", "Mirador", "Fruta del Norte", "concentrado de cobre",
             "concesión minera", "catastro minero", "minería ilegal", "Chocó Andino",
             "consulta previa libre e informada", "Zaruma", "Buenos Aires Imbabura",
             "quri (kichwa: el oro)", "anta (kichwa: el cobre)", "nunka (shuar: la tierra)"),
    "EC-N": ("feriado nacional", "traslado de feriados", "Código del Trabajo",
             "Lunes de Carnaval", "Viernes Santo", "Día de los Difuntos",
             "Independencia de Guayaquil", "Batalla del Pichincha", "Fundación de Quito",
             "Inti Raymi", "Pawkar Raymi", "Kulla Raymi", "Kapak Raymi",
             "Uwi Nampesma (shuar: la fiesta de la chonta)", "día no laborable"),
    "EC-X": ("remesas", "migración", "índice de precios al consumidor", "INEC",
             "balanza comercial", "SENAE", "partida arancelaria", "salvaguardia",
             "tratado de libre comercio con China", "inversión extranjera directa",
             "aents (shuar: la persona)", "arutam (shuar: el espíritu de la visión)",
             "ayllu (kichwa: la familia extensa)", "runa (kichwa: la gente)",
             "allpa (kichwa: la tierra)", "wasi (kichwa: la casa)"),
}

#: Latin script is shared by all three of this country's languages, so "native script" cannot be
#: a codepoint test here the way Arabic or Hangul can. It is a VOCABULARY test instead: Spanish is
#: detected by its diacritics (an English glossary of Ecuador has none), Kichwa and Shuar by their
#: own words.
_SPANISH_DIACRITICS = "áéíóúüñÁÉÍÓÚÜÑ¿¡"
#: Kichwa working vocabulary. `quri` and `anta` are two of the metals this desk trades, named in
#: the language of the communities the concessions sit on; `sumak kawsay` is in the constitution.
KICHWA_MARKERS: tuple[str, ...] = (
    "quri", "anta", "kullki", "yaku", "allpa", "sacha", "ayllu", "runa", "wasi", "minka",
    "sumak kawsay", "Inti Raymi", "Pawkar Raymi", "Kulla Raymi", "Kapak Raymi")
#: Shuar working vocabulary. The Amazonian oil and mining blocs sit on Shuar and Achuar land and
#: the consultation record, the assemblies and the federation's own wire are in these words.
SHUAR_MARKERS: tuple[str, ...] = (
    "nunka", "entsa", "aents", "arutam", "Uwi Nampesma", "shuar", "achuar")
#: Spanish working vocabulary the pack must carry, checked by name so the glossary cannot drift
#: into English while still looking full.
SPANISH_MARKERS: tuple[str, ...] = (
    "dolarización", "erosión regresiva", "fuerza mayor", "racionamiento eléctrico",
    "consulta popular", "muerte cruzada", "estado de excepción", "paro nacional",
    "precio mínimo de sustentación", "cacao fino de aroma", "camarón",
    "canje de deuda por naturaleza", "Registro Oficial", "subsidio a los combustibles",
    "conflicto armado interno", "minería ilegal", "feriado nacional")


def has_spanish_diacritic(text: str) -> bool:
    """True when the text carries a Spanish diacritic. An English translation of an Ecuadorian
    release has none, which is what makes this a usable native-language test on Latin script."""
    return any(ch in _SPANISH_DIACRITICS for ch in str(text))


def has_kichwa(text: str) -> bool:
    """True when the text carries a declared Kichwa term."""
    return any(m in str(text) for m in KICHWA_MARKERS)


def has_shuar(text: str) -> bool:
    """True when the text carries a declared Shuar term."""
    return any(m in str(text) for m in SHUAR_MARKERS)


def _flat_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> set[str]:
    rows = TERMINOLOGY if terminology is None else terminology
    return {t for terms in rows.values() for t in terms}


def spanish_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    """Every declared Spanish marker actually present in the terminology table."""
    flat = _flat_terms(terminology)
    return [m for m in SPANISH_MARKERS if any(m in t for t in flat)]


def kichwa_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    flat = _flat_terms(terminology)
    return [m for m in KICHWA_MARKERS if any(m in t for t in flat)]


def shuar_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    flat = _flat_terms(terminology)
    return [m for m in SHUAR_MARKERS if any(m in t for t in flat)]


def accented_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    """Every term carrying a Spanish diacritic -- the Latin-script equivalent of the Arabic
    codepoint test the `ma` pack uses."""
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
    """One class of source with the roots a crawler starts from and its three INDEPENDENT labels.
    `queries` are native-language terms, never translations. `machine_use_allowed=True` registers
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
    """A layer this country has nothing in, declared BY NAME with the reason (L1.28a)."""
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
        "ec_bce", "Banco Central del Ecuador: Informacion Estadistica Mensual, weekly reserves, "
                  "balance of payments, remittances, the monetary survey and the trade tables",
        layer="official",
        roots=("https://www.bce.fin.ec/informacioneconomica",
               "https://contenido.bce.fin.ec/home1/estadisticas/bolmensual/IEMensual.jsp",
               "https://www.bce.fin.ec/index.php/informacioneconomica/sector-externo"),
        queries=("información estadística mensual BCE", "reservas internacionales semanales",
                 "remesas recibidas por provincia", "balanza de pagos trimestral Ecuador",
                 "depósitos del sistema financiero", "exportaciones de petróleo valor y volumen",
                 "sistema de canje dolarización", "kullki tantachina"),
        languages=("es", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public (bce.fin.ec terms)",
        notes="A CENTRAL BANK WITH NO MONETARY POLICY IS A STATISTICS AGENCY WITH A VAULT, and "
              "that is exactly what makes it useful: the WEEKLY reserve print is a solvency read "
              "rather than an intervention read, and no other pack on this desk has one"),
    source_class(
        "ec_inec", "Instituto Nacional de Estadistica y Censos: CPI, employment, national "
                   "accounts, poverty and the business register",
        layer="official",
        roots=("https://www.ecuadorencifras.gob.ec/estadisticas/",
               "https://www.ecuadorencifras.gob.ec/indice-de-precios-al-consumidor/",
               "https://www.ecuadorencifras.gob.ec/empleo-encuesta-nacional-de-empleo-desempleo-"
               "y-subempleo-enemdu/"),
        queries=("índice de precios al consumidor Ecuador", "ENEMDU empleo adecuado",
                 "canasta familiar básica", "inflación anual por ciudad",
                 "encuesta nacional de empleo desempleo y subempleo",
                 "pobreza por ingresos Ecuador"),
        languages=("es",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="A CPI IN A DOLLARISED ECONOMY MEANS SOMETHING DIFFERENT: it cannot be a monetary "
              "impulse, so it measures relative-price and real-exchange-rate drift against "
              "Colombia and Peru. That is the competitiveness channel that replaced devaluation"),
    source_class(
        "ec_energia", "Ministerio de Energia y Minas / Recursos y Energia No Renovables: crude "
                      "production by field and block, the mining cadastre, electricity statistics",
        layer="official",
        roots=("https://www.recursosyenergia.gob.ec/estadisticas/",
               "https://www.controlhidrocarburos.gob.ec/estadisticas-de-hidrocarburos/",
               "https://www.recursosyenergia.gob.ec/mineria/"),
        queries=("producción nacional de petróleo por campo", "estadística hidrocarburífera",
                 "catastro minero Ecuador", "balance energético nacional",
                 "producción de crudo Oriente y Napo", "bloque petrolero contrato",
                 "minería a gran escala Mirador Fruta del Norte"),
        languages=("es",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="PRODUCTION BY FIELD AND BY BLOCK, which is what makes the ITT question measurable: "
              "Block 43's own barrels are a separate line, so a referendum that shuts one field "
              "can be counted against the national total rather than guessed at"),
    source_class(
        "ec_petroecuador", "EP Petroecuador: monthly production and export reports, cargo tender "
                           "awards, the SOTE pumping record and the force-majeure notices",
        layer="official",
        roots=("https://www.eppetroecuador.ec/",
               "https://www.eppetroecuador.ec/?page_id=1573",
               "https://www.eppetroecuador.ec/?cat=contrataciones"),
        queries=("Petroecuador informe mensual de exportaciones", "declaratoria de fuerza mayor",
                 "bombeo SOTE suspendido", "adjudicación de carga de crudo Oriente",
                 "producción de crudo estatal mensual", "variante emergente oleoducto"),
        languages=("es",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE FORCE-MAJEURE NOTICE IS THE FASTEST ROW IN THIS PACK. The monthly production "
              "count arrives weeks later; the declaration arrives the day the pipeline stops, "
              "and it is an operator's own statement rather than a press inference"),
    source_class(
        "ec_aduana", "Servicio Nacional de Aduana del Ecuador (SENAE): export and import records "
                     "by tariff heading, by destination and by port",
        layer="official",
        roots=("https://www.aduana.gob.ec/boletines-estadisticos/",
               "https://www.aduana.gob.ec/estadisticas/"),
        queries=("boletín estadístico de comercio exterior SENAE",
                 "exportaciones por partida arancelaria", "importaciones por distrito aduanero",
                 "exportación de camarón partida 030617", "exportación de banano por destino",
                 "exportación de cacao en grano"),
        languages=("es",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE CUSTOMS MIRROR for every physical claim in this pack. VOLUME is the field to "
              "use: the declared VALUE re-prices the commodity, so a value-based supply study is "
              "measuring the price twice and calling the second one supply"),
    source_class(
        "ec_finanzas", "Ministerio de Economia y Finanzas: the budget, the oil-price assumption, "
                       "the debt stock, arrears and the debt-for-nature transaction documents",
        layer="official",
        roots=("https://www.finanzas.gob.ec/estadisticas-fiscales/",
               "https://www.finanzas.gob.ec/presupuesto-general-del-estado/",
               "https://www.finanzas.gob.ec/deuda-publica/"),
        queries=("proforma del presupuesto general del estado", "deuda pública consolidada",
                 "atrasos de pago del estado", "canje de deuda por naturaleza Galápagos",
                 "precio del petróleo presupuestado", "programación fiscal cuatrienal"),
        languages=("es", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="WITH NO CENTRAL BANK TO BRIDGE A GAP, THE ARREARS LINE IS THE STRESS VARIABLE. A "
              "government that cannot print pays late instead, and the lateness is published"),
    source_class(
        "ec_cne", "Consejo Nacional Electoral and the Tribunal Contencioso Electoral: the "
                  "referendum questions, the results by parish, and the electoral calendar",
        layer="official",
        roots=("https://www.cne.gob.ec/", "https://resultados.cne.gob.ec/",
               "https://www.cne.gob.ec/estadisticas-electorales/"),
        queries=("resultados consulta popular por parroquia", "pregunta del referéndum Yasuní",
                 "consulta popular Chocó Andino resultados",
                 "calendario electoral elecciones anticipadas",
                 "padrón electoral y participación", "segunda vuelta presidencial resultados"),
        languages=("es",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE RECORD OF AN ELECTORATE SHUTTING AN OIL FIELD. The 2023-08-20 ITT question and "
              "the same-day Choco Andino mining question are both counted here by parish, which "
              "is the only place a supply decision taken by ballot is documented as a supply fact"),
    source_class(
        "ec_registro_oficial", "Registro Oficial: executive decrees, states of exception, fuel "
                               "price decrees, the banana minimum-price Acuerdo and every tariff",
        layer="official",
        roots=("https://www.registroficial.gob.ec/",
               "https://www.registroficial.gob.ec/index.php/registro-oficial-web/publicaciones/"
               "registro-oficial.html"),
        queries=("decreto ejecutivo estado de excepción", "acuerdo ministerial precio mínimo de "
                 "sustentación banano", "decreto de bandas de precios de combustibles",
                 "declaratoria de emergencia del sector eléctrico",
                 "día no laborable decreto", "registro oficial suplemento"),
        languages=("es",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE GAZETTE IS THIS COUNTRY'S EVENT TAPE and the promotion gate for every dated "
              "claim in this pack: nothing here may be promoted from PRESS_REPORTED without a "
              "decree number from this root attached to the exact date the cell was compiled on"),
    source_class(
        "ec_cenace", "CENACE (the grid operator) and ARCERNNR (the regulator): daily national "
                     "demand, hydro dispatch, reservoir levels and the published rationing tables",
        layer="official",
        roots=("https://www.cenace.gob.ec/informacion-operativa/",
               "https://www.controlrecursosyenergia.gob.ec/estadistica-del-sector-electrico/"),
        queries=("informe de operación diaria CENACE", "horarios de racionamiento por provincia",
                 "cota del embalse Mazar", "demanda nacional de energía MW",
                 "generación hidráulica y térmica despacho", "déficit de generación",
                 "Coca Codo Sinclair producción"),
        languages=("es",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="A RARE GENUINELY FORWARD-LOOKING PHYSICAL SERIES: during an emergency the NEXT "
              "DAY'S cuts are published the afternoon before, by province and by hour, so the "
              "load loss is known before it happens rather than measured after"),
    # ---- institutional
    source_class(
        "ec_bolsa", "Bolsa de Valores de Quito and Bolsa de Valores de Guayaquil: the daily "
                    "bulletin, the ECUINDEX and the corporate and titularizacion issuance record",
        layer="institutional",
        roots=("https://www.bolsadequito.com/", "https://www.bolsadequito.com/index.php/"
               "informacion-bursatil/boletines", "https://www.mundobvg.com/"),
        queries=("boletín diario bolsa de valores de Quito", "ECUINDEX cierre",
                 "emisión de obligaciones aprobada", "titularización de flujos",
                 "papel comercial inscrito", "negociaciones de renta fija bursátil"),
        languages=("es",), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="A BOURSE THAT IS A FUNDING VENUE AND NOT A PRICE-DISCOVERY ONE. The board is "
              "dominated by fixed income; no CFD exists on it; it enters this pack as a "
              "transmission target and as a corporate-funding observable, never as an instrument"),
    source_class(
        "ec_acuacultura", "Camara Nacional de Acuacultura: monthly shrimp export volume and value "
                          "by destination, the farm-gate price commentary and the sector bulletins",
        layer="institutional",
        roots=("https://www.cna-ecuador.com/estadisticas/",
               "https://www.cna-ecuador.com/publicaciones/"),
        queries=("exportaciones de camarón por destino", "libras exportadas de camarón mensual",
                 "precio en playa del camarón", "participación de China en el camarón "
                 "ecuatoriano", "revista aquacultura CNA", "balanceado camaronero costo"),
        languages=("es", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE SINGLE MOST INFORMATIVE EXPORT SERIES IN THE COUNTRY: monthly, free, counted, "
              "by destination, on the world's largest farmed-shrimp exporter, with more than "
              "half the volume going to one buyer whose own import prints can be mirrored"),
    source_class(
        "ec_banano", "ACORBANEC and AEBE: weekly and monthly banana export box counts by "
                     "destination, the contract-price commentary and the sector position papers",
        layer="institutional",
        roots=("https://acorbanec.com/", "https://www.aebe.com.ec/",
               "https://www.aebe.com.ec/estadisticas/"),
        queries=("cajas de banano exportadas semanal", "exportación de banano por destino",
                 "precio de la caja de banano spot", "precio mínimo de sustentación banano",
                 "AEBE estadísticas de exportación", "banano ecuatoriano a Rusia y la UE"),
        languages=("es",), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="ONE OF THE FEW WEEKLY PHYSICAL EXPORT SERIES ON THIS DESK, against an administered "
              "minimum price set once a year. The gap between the spot box price and the decreed "
              "floor is the sector's own stress gauge and it is discussed publicly every week"),
    source_class(
        "ec_cacao", "ANECACAO and the cacao exporter associations: monthly export tonnage by "
                    "grade and destination, the fino de aroma premium and the harvest commentary",
        layer="institutional",
        roots=("https://www.anecacao.com/estadisticas/", "https://www.anecacao.com/"),
        queries=("exportaciones de cacao en grano mensual", "cacao fino de aroma premio",
                 "CCN-51 versus cacao nacional", "quintales de cacao exportados",
                 "cosecha de cacao estimación", "molienda de cacao Ecuador"),
        languages=("es", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE CLEANEST SOFT-COMMODITY LINK IN THE PACK because the contract on the other "
              "side is liquid and the grade split is published: fino de aroma and CCN-51 bulk "
              "price differently off the same terminal market, which is a testable spread"),
    source_class(
        "ec_asobanca", "ASOBANCA and the Superintendencia de Bancos: deposits, credit, structural "
                       "liquidity, delinquency by segment and the individual bank returns",
        layer="institutional",
        roots=("https://www.superbancos.gob.ec/estadisticas/", "https://asobanca.org.ec/"),
        queries=("depósitos a la vista y a plazo del sistema", "liquidez estructural bancaria",
                 "morosidad de la cartera por segmento", "boletín financiero mensual bancos",
                 "informe de coyuntura ASOBANCA", "ranking de depósitos por entidad"),
        languages=("es",), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="WITH NO LENDER OF LAST RESORT THIS IS THE STABILITY SERIES. 1999 is the reference "
              "case and it is why the pack conditions on deposits rather than on a policy rate "
              "that does not exist"),
    source_class(
        "ec_multilateral", "The foreign-official layer: OPEC's historical statistical bulletin "
                           "(Ecuador was a member until 2020), EIA, USDA FAS GAIN, the FAO banana "
                           "market review, UN Comtrade and the IMF country page",
        layer="institutional",
        roots=("https://www.opec.org/opec_web/en/publications/202.htm",
               "https://www.eia.gov/international/data/country/ECU",
               "https://fas.usda.gov/regions/ecuador", "https://comtrade.un.org/",
               "https://www.imf.org/en/Countries/ECU",
               "https://www.fao.org/markets-and-trade/commodities/bananas/en/"),
        queries=("OPEC annual statistical bulletin Ecuador production",
                 "EIA Ecuador crude oil exports", "USDA FAS Ecuador shrimp annual",
                 "FAO banana market review", "UN Comtrade Ecuador cocoa exports",
                 "IMF Ecuador Extended Fund Facility staff report"),
        languages=("en", "es"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public / public domain",
        notes="THE MIRROR AND THE HISTORY. OPEC's series covers the membership years and stops, "
              "which is itself the dated regime break of 2020-01-01; Comtrade gives the buyers' "
              "own declarations against Ecuador's, and the gap between them is a real observable"),
    # ---- academic
    source_class(
        "ec_academia", "The Ecuadorian and Andean academic ground: FLACSO Ecuador, Universidad "
                       "Andina Simon Bolivar, PUCE, ESPOL, plus OpenAlex and CORE for the rest",
        layer="academic",
        roots=("https://repositorio.flacsoandes.edu.ec/", "https://repositorio.uasb.edu.ec/",
               "https://www.puce.edu.ec/investigacion/", "https://openalex.org/",
               "https://core.ac.uk/"),
        queries=("dolarización y ciclo económico Ecuador tesis",
                 "erosión regresiva río Coca estudio geomorfológico",
                 "consulta previa pueblos indígenas Ecuador evaluación",
                 "impacto fiscal del subsidio a los combustibles Ecuador",
                 "remesas y consumo de los hogares Ecuador",
                 "sumak kawsay derechos de la naturaleza análisis"),
        languages=("es", "en"), access_label="OPEN_DATA", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="open access repositories",
        notes="THE GEOMORPHOLOGY LITERATURE IS THE ONE THAT MATTERS HERE and it is not economics: "
              "the rate of advance of the Coca erosion front is a published scientific quantity "
              "and it is the physical prior on when the next pipeline interruption happens"),
    # ---- practitioner
    source_class(
        "ec_consultoras", "The domestic analyst ground: Analisis Semanal, CORDES, Primicias' "
                          "economic desk and the sector consultancies",
        layer="practitioner",
        roots=("https://www.analisissemanal.com/", "https://www.cordes.org/",
               "https://www.primicias.ec/economia/"),
        queries=("Análisis Semanal coyuntura económica", "CORDES informe de coyuntura",
                 "proyección de crecimiento del PIB Ecuador",
                 "riesgo país y financiamiento externo", "escenario fiscal del presupuesto"),
        languages=("es",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="mixed: some issues are subscriber-only",
        notes="A SMALL BUT OLD SELL-SIDE-EQUIVALENT. Ecuador has no investment-bank research "
              "industry, so the long-running independent weeklies ARE the practitioner layer, "
              "and their consensus is the only stated benchmark a fiscal surprise has"),
    source_class(
        "ec_sector_press", "The sector trade press and the operator communications: the oil and "
                           "mining trade wires, the aquaculture and banana industry magazines",
        layer="practitioner",
        roots=("https://www.revistalideres.ec/", "https://www.mundoacuicola.cl/",
               "https://www.ekosnegocios.com/"),
        queries=("paralización de operaciones petroleras", "bombeo de crudo reanudado",
                 "camaroneras costos de producción", "exportadores de banano coyuntura",
                 "minería industrial Ecuador avance de proyecto"),
        languages=("es",), access_label="PUBLIC_WITH_TERMS", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="publisher terms; registered, not scraped",
        machine_use_allowed=True,
        notes="KEPT AT LOW WEIGHT AND NEVER DROPPED. Trade-press restart and shut-in claims are "
              "often the first public date for an outage and often wrong; registering the ground "
              "keeps the knowledge that it exists while the gazette remains the promotion gate"),
    # ---- retail_ecology: DECLARED ABSENT, with the lawful substitute named
    absent_layer(
        "retail_ecology",
        "THERE IS NO DOMESTIC SPECULATIVE RETAIL ECOLOGY TO READ, and the reason is the pack's "
        "own thesis. A retail_ecology row in this desk's vocabulary means forums, chat groups, "
        "margin and retail-flow statistics and brokers' own data. Ecuador has NO DOMESTIC "
        "CURRENCY to speculate on, no onshore retail margin-FX or CFD industry, no local broker "
        "that publishes client positioning, and a bourse with no retail derivatives and a "
        "predominantly institutional fixed-income book. What retail speculation exists is "
        "offshore, unregistered and unmeasurable, and inventing a proxy for it would be padding. "
        "THE LAWFUL SUBSTITUTE, and it is registered in other layers rather than dressed up as "
        "this one: the HOUSEHOLD dollar channel is the BCE's quarterly remittance series by "
        "province and the Superintendencia's deposit-by-size tables, both of which measure what "
        "households actually do with dollars in an economy where holding them needs no broker"),
    # ---- app_ecosystem
    source_class(
        "ec_datos_abiertos", "The state's machine-readable surface: datosabiertos.gob.ec, the "
                             "BCE's series downloads, the SENAE bulletins and the CNE results API",
        layer="app_ecosystem",
        roots=("https://www.datosabiertos.gob.ec/", "https://resultados.cne.gob.ec/",
               "https://contenido.bce.fin.ec/documentos/Estadisticas/SectorReal/Previsiones/"
               "IndCoyuntura/"),
        queries=("datos abiertos Ecuador descargar dataset", "series estadísticas BCE descarga",
                 "API resultados electorales CNE", "catastro minero geoportal descarga",
                 "geoportal del sector eléctrico capas"),
        languages=("es",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="open data",
        notes="THE COLLECTOR'S ACTUAL ENTRY POINT. Most Ecuadorian official data is published as "
              "XLS behind a page rather than as an API, so the open-data portal and the series "
              "downloads are what a crawler can act on without a human in the loop"),
    source_class(
        "ec_fintech", "The domestic payment and money-movement apps: DeUna, Peigo, the bank "
                      "wallets and the remittance corridors' own rails",
        layer="app_ecosystem",
        roots=("https://www.bce.fin.ec/index.php/component/k2/item/324-sistema-de-pagos",
               "https://www.superbancos.gob.ec/estadisticas/"),
        queries=("sistema de pagos interbancario estadísticas", "billetera móvil transacciones",
                 "DeUna pagos con código QR", "remesas por canal de envío",
                 "dinero electrónico Ecuador historia"),
        languages=("es",), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="ECUADOR RAN AND KILLED A CENTRAL-BANK DIGITAL CURRENCY (dinero electronico, 2014 "
              "to 2018), which is a dated natural experiment in a dollarised economy and a "
              "genuinely unusual object to have a public record of"),
    # ---- media
    source_class(
        "ec_prensa", "The national financial and general press: El Universo, El Comercio, "
                     "Primicias, Expreso and Revista Gestion",
        layer="media",
        roots=("https://www.eluniverso.com/", "https://www.elcomercio.com/",
               "https://www.primicias.ec/", "https://www.expreso.ec/",
               "https://revistagestion.ec/"),
        queries=("Petroecuador declara fuerza mayor", "cortes de luz horarios hoy",
                 "precio de la caja de banano esta semana",
                 "exportaciones de camarón caen a China", "riesgo país Ecuador hoy",
                 "estado de excepción prorrogado decreto"),
        languages=("es",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="publisher terms",
        notes="THE FIRST PUBLIC DATE for most of this pack's episodes. Every one of them is "
              "labelled PRESS_REPORTED for exactly that reason and none may be promoted on a "
              "newspaper alone"),
    source_class(
        "ec_investigativa", "The investigative and long-form ground: GK, Plan V, La Barra "
                            "Espaciadora and the environmental and security desks",
        layer="media",
        roots=("https://gk.city/", "https://www.planv.com.ec/",
               "https://labarraespaciadora.com/"),
        queries=("investigación sobre el bloque 43 y el Yasuní",
                 "minería ilegal en Buenos Aires Imbabura reportaje",
                 "puerto de Guayaquil y el narcotráfico investigación",
                 "contratos de generación eléctrica emergente",
                 "erosión del río Coca reportaje comunidades"),
        languages=("es",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="publisher terms",
        notes="THE LAYER THAT DATES THINGS THE OFFICIAL RECORD DOES NOT: illegal-mining fronts, "
              "port corruption cases and emergency-generation contracts are documented here "
              "first and in detail, months before a ministry publishes anything about them"),
    source_class(
        "ec_wambra_kichwa", "The indigenous and Amazonian wire in KICHWA and SHUAR: Wambra Medio "
                            "Digital, the CONAIE and CONFENIAE channels and the community radios",
        layer="media",
        roots=("https://wambra.ec/", "https://conaie.org/", "https://confeniae.net/"),
        queries=("CONAIE convocatoria al paro nacional", "asamblea comunitaria resolución minka",
                 "consulta previa territorio shuar arutam",
                 "levantamiento indígena Inti Raymi movilización",
                 "CONFENIAE bloque petrolero nunka entsa", "runa llakta yaku defensa"),
        languages=("qu", "jiv", "es"), access_label="PUBLIC_SOCIAL", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE REASON THIS PACK CARRIES TWO INDIGENOUS LANGUAGES. The decision to shut a "
              "wellhead is taken in a community assembly and announced on this ground days "
              "before it reaches the Spanish press and weeks before it reaches a production "
              "statistic. A Spanish-only crawl reads the reaction, never the decision"),
    # ---- archive
    source_class(
        "ec_archivo_oficial", "The historical official record: the Registro Oficial archive, the "
                              "BCE Memoria Anual and the INEC yearbooks",
        layer="archive",
        roots=("https://www.registroficial.gob.ec/index.php/registro-oficial-web/publicaciones/"
               "suplementos.html",
               "https://www.bce.fin.ec/index.php/component/k2/item/293-memoria-anual",
               "https://www.ecuadorencifras.gob.ec/biblioteca/"),
        queries=("registro oficial archivo por año", "memoria anual BCE serie histórica",
                 "anuario de estadísticas INEC descarga",
                 "decreto ejecutivo derogado texto original",
                 "estadísticas históricas de la dolarización"),
        languages=("es",), access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE ONLY VINTAGE THIS PACK HAS for several series, because the ministries overwrite "
              "their statistics pages in place; a point-in-time claim on an un-archived month is "
              "UNMEASURED and the pack says so rather than assuming the current file"),
    source_class(
        "ec_crawl_archive", "General web archives for the overwritten pages: the Wayback Machine "
                            "and the national library's digital collections",
        layer="archive",
        roots=("https://web.archive.org/", "https://www.bibliotecanacional.gob.ec/"),
        queries=("web archive recursosyenergia estadísticas hidrocarburos",
                 "archive.org cenace informe de operación",
                 "captura histórica acorbanec cajas exportadas",
                 "hemeroteca El Universo edición impresa",
                 "biblioteca nacional Eugenio Espejo colección digital"),
        languages=("es", "en"), access_label="PUBLIC_ARCHIVE", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="archive terms",
        notes="THE PIT MACHINE. Several of this pack's most valuable series -- CENACE's rationing "
              "tables above all -- exist only as a page that was replaced the next day, so the "
              "crawl is the vintage and the crawl date is the vintage date"),
    # ---- physical_economy
    source_class(
        "ec_oleoductos", "The pipeline plane: OCP Ecuador's own operational notices, the SOTE "
                         "pumping record and the erosion-front monitoring reports",
        layer="physical_economy",
        roots=("https://www.ocpecuador.com/", "https://www.ambiente.gob.ec/",
               "https://www.eppetroecuador.ec/?page_id=1573"),
        queries=("OCP suspende el bombeo comunicado", "avance de la erosión regresiva informe",
                 "variante emergente OCP SOTE kilómetro",
                 "monitoreo del río Coca socavamiento", "plan de contingencia oleoducto"),
        languages=("es", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="A PRIVATE OPERATOR AND A STATE OPERATOR ON THE SAME ERODING RIVER, each publishing "
              "its own notices. Their disagreements about the erosion front's position are the "
              "most informative rows in this layer and neither can be checked against the other "
              "without reading both"),
    source_class(
        "ec_puertos", "The port plane: the Autoridad Portuaria de Guayaquil, the Contecon and DP "
                      "World Posorja terminals, and the Puerto Bolivar banana gate",
        layer="physical_economy",
        roots=("https://www.apg.gob.ec/estadisticas", "https://www.cgsa.com.ec/",
               "https://www.dpworldposorja.com/"),
        queries=("movimiento de contenedores TEU Guayaquil", "estadísticas portuarias mensuales",
                 "Puerto Bolívar embarque de banano", "Posorja calado y recaladas",
                 "incautación de droga en contenedores puerto"),
        languages=("es",), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="ONE GATE, THREE COMMODITIES. Banana, shrimp and cacao all leave through the same "
              "terminals, so a security or labour event at Guayaquil is a simultaneous shock to "
              "three export series -- which is a joint test, and a much harder one to fake"),
    source_class(
        "ec_hidrologia", "The hydrology and climate plane: INAMHI, the reservoir levels and the "
                         "ENSO bulletins that drive the power crisis and the crops alike",
        layer="physical_economy",
        roots=("https://www.inamhi.gob.ec/", "https://www.serviciometeorologico.gob.ec/",
               "https://origin.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/"),
        queries=("boletín hidrológico INAMHI caudales", "cota y volumen del embalse Mazar",
                 "pronóstico estacional de lluvias sierra oriente",
                 "alerta de El Niño costero Ecuador", "ENSO advisory sea surface temperature"),
        languages=("es", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public / public domain",
        notes="THE SAME WATER DRIVES FOUR DOMAINS: the reservoirs that ration the grid, the river "
              "that cuts the pipelines, the rainfall that sets the banana and cacao harvest and "
              "the sea temperature that sets the shrimp growth cycle. That shared driver is a "
              "CONFOUND before it is a mechanism and every cell here must control for it"),
    # ---- source_graph
    source_class(
        "ec_citas", "The expansion edges: what the other nine layers cite, attribute and argue "
                    "with -- the attribution phrases that lead to the next unmined source",
        layer="source_graph",
        roots=("https://www.google.com/search?q=", "https://scholar.google.com/",
               "https://openalex.org/"),
        queries=("según el boletín del Banco Central del Ecuador",
                 "de acuerdo con la Cámara Nacional de Acuacultura",
                 "fuentes del sector petrolero indicaron", "trascendió que la operadora evalúa",
                 "citando el informe de CENACE", "documento al que tuvo acceso este medio"),
        languages=("es",), access_label="PUBLIC", credibility="UNKNOWN",
        predictive_state="UNTESTED", licence="search terms apply",
        notes="THE LAYER A DESK THAT ONLY READS PRESS RELEASES NEVER REACHES. Attribution phrases "
              "are how an unnamed but real series -- an internal CENACE table, an operator's "
              "circular to buyers -- becomes visible before anybody publishes it"),
)

#: THE ONE LAYER ECUADOR GENUINELY DOES NOT HAVE, with the reason and the lawful substitute. This
#: is a MEASUREMENT, not a gap: a country with no currency has no domestic speculative retail.
LAYER_ABSENCES: dict[str, str] = {
    "retail_ecology": "no domestic currency to speculate on, no onshore retail margin-FX or CFD "
                      "industry, no broker publishing client positioning, and a bourse with no "
                      "retail derivatives. The lawful substitute -- the BCE remittance series by "
                      "province and the Superintendencia's deposit-by-size tables -- is "
                      "registered under `official` and `institutional` rather than padded in here",
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
            "rule": "ten layers, each carrying a source or named ABSENT with a reason; fringe "
                    "and contradicted PUBLIC material is kept as a low-weight evidence object "
                    "and never dropped; a page whose terms forbid machine extraction is "
                    "registered machine_use_allowed=false, never scraped and never omitted"}


#: NATIVE QUERY TERRITORIES -- what the deep-forest miner actually types, per layer, in the
#: languages of the ground. Three or more for every layer that is not declared absent, and the
#: media and physical layers carry Kichwa and Shuar because that is where the decision is taken.
QUERY_TERRITORIES: dict[str, tuple[str, ...]] = {
    "official": ("información estadística mensual Banco Central del Ecuador",
                 "producción de petróleo por campo estadística hidrocarburífera",
                 "horarios de racionamiento eléctrico CENACE por provincia",
                 "decreto ejecutivo estado de excepción Registro Oficial",
                 "resultados de la consulta popular por parroquia CNE",
                 "boletín de comercio exterior SENAE exportaciones"),
    "institutional": ("exportaciones de camarón por destino Cámara Nacional de Acuacultura",
                      "cajas de banano exportadas ACORBANEC semanal",
                      "exportaciones de cacao fino de aroma ANECACAO",
                      "boletín diario bolsa de valores de Quito",
                      "liquidez estructural del sistema financiero ASOBANCA"),
    "academic": ("dolarización sin prestamista de última instancia análisis",
                 "erosión regresiva del río Coca estudio",
                 "consulta previa libre e informada Ecuador evaluación",
                 "impacto del subsidio a los combustibles en el presupuesto",
                 "sumak kawsay y derechos de la naturaleza jurisprudencia"),
    "practitioner": ("Análisis Semanal coyuntura petrolera",
                     "CORDES informe fiscal trimestral",
                     "costos de producción camaronera balanceado",
                     "paralización de operaciones petroleras reanudación",
                     "proyección del riesgo país Ecuador"),
    "retail_ecology": (),
    "app_ecosystem": ("datos abiertos Ecuador descargar dataset",
                      "series estadísticas BCE descarga XLS",
                      "API de resultados electorales CNE",
                      "geoportal del catastro minero capas",
                      "sistema de pagos interbancario estadísticas"),
    "media": ("Petroecuador declara fuerza mayor oleoducto",
              "cortes de luz horarios hoy por provincia",
              "CONAIE convocatoria al paro nacional minka",
              "asamblea del pueblo shuar arutam nunka consulta",
              "runa llakta yaku defensa comunitaria",
              "incautación de droga en el puerto de Guayaquil"),
    "archive": ("registro oficial archivo decreto derogado",
                "memoria anual BCE serie histórica descarga",
                "web archive CENACE informe de operación diaria",
                "hemeroteca El Universo edición impresa",
                "anuario estadístico INEC histórico"),
    "physical_economy": ("avance de la erosión regresiva informe de monitoreo",
                         "cota del embalse Mazar hoy",
                         "movimiento de contenedores TEU Autoridad Portuaria de Guayaquil",
                         "boletín hidrológico INAMHI caudales",
                         "alerta de El Niño costero ENFEN ENSO",
                         "Puerto Bolívar embarque de banano naves"),
    "source_graph": ("según el boletín del Banco Central del Ecuador",
                     "de acuerdo con la Cámara Nacional de Acuacultura",
                     "fuentes del sector petrolero indicaron que",
                     "citando el informe de CENACE",
                     "documento al que tuvo acceso este medio"),
}
# --------------------------------------------------------------------------- datasets
#: SIXTEEN CATALOGUE ENTRIES, spread across the ten layers. Every row carries the twelve fields
#: the data-discovery swarm needs and a `how_to_fetch` a collector can act on without asking a
#: human. `pit_feasible` is the field the catalogue exists for: a series whose vintage cannot be
#: reconstructed can only ever produce NOT_PIT_SAFE cells, and saying so is the measurement.
DATASETS: tuple[dict[str, Any], ...] = (
    {"name": "BCE weekly international reserves and the four-system balance sheet",
     "source": "Banco Central del Ecuador",
     "coverage": "2000 onward under dollarisation; the four-system presentation from 2008",
     "frequency": "weekly", "publication_lag_days": 5.0,
     "revisions": "occasional restatement of the prior week", "licence": "free, public",
     "history_from": "2000-01", "pit_feasible": False,
     "assets": ("USDBRL", "USDMXN", "US500"),
     "mechanism_families": ("solvency_state", "event_reaction"),
     "how_to_fetch": "the weekly cuadros under bce.fin.ec/informacioneconomica; NOT PIT-SAFE as "
                     "published because the page carries only the current table -- the archive "
                     "layer's crawls are the only vintage, and the 2021 Ley de Defensa de la "
                     "Dolarizacion redefined the presentation, which is a break not a revision"},
    {"name": "BCE Informacion Estadistica Mensual: deposits, credit, remittances and trade",
     "source": "Banco Central del Ecuador",
     "coverage": "1990 onward for most tables; the dollarised series from 2000",
     "frequency": "monthly", "publication_lag_days": 45.0,
     "revisions": "the two prior months are routinely restated", "licence": "free, public",
     "history_from": "2000-01", "pit_feasible": False,
     "assets": ("USDBRL", "USDMXN", "US500", "CORN"),
     "mechanism_families": ("macro_state", "release_surprise"),
     "how_to_fetch": "the IEMensual PDF and XLS at contenido.bce.fin.ec/home1/estadisticas/"
                     "bolmensual/IEMensual.jsp; parse the external-sector and monetary tables "
                     "and join the remittance series by province to the migration corridors"},
    {"name": "EP Petroecuador production and export volumes by field and grade",
     "source": "EP Petroecuador and the Ministerio de Energia y Minas",
     "coverage": "2000 onward by field; Block 43 (ITT) separately identified from 2016",
     "frequency": "monthly", "publication_lag_days": 35.0,
     "revisions": "late field declarations restate the prior month", "licence": "free, public",
     "history_from": "2000-01", "pit_feasible": False,
     "assets": ("XBRUSD", "XTIUSD"),
     "mechanism_families": ("physical_supply", "release_surprise"),
     "how_to_fetch": "the monthly reports at eppetroecuador.ec and the hydrocarbon statistics at "
                     "controlhidrocarburos.gob.ec; BLOCK 43 IS A SEPARATE LINE, which is what "
                     "makes the referendum's effect countable rather than inferred"},
    {"name": "The declared pipeline and wellhead interruption episodes",
     "source": "this pack's PIPELINE_EPISODES, built from operator notices, Petroecuador "
               "force-majeure declarations and the national press",
     "coverage": "2019 onward", "frequency": "irregular, dated", "publication_lag_days": 1.0,
     "revisions": "every row is PRESS_REPORTED and is rewritten when a gazette or operator "
                  "citation pins the date",
     "licence": "derived from public sources", "history_from": "2019-10", "pit_feasible": True,
     "assets": ("XBRUSD", "XTIUSD"),
     "mechanism_families": ("physical_supply", "event_reaction"),
     "how_to_fetch": "`pipeline_episodes()` in this module; confirm each start and end against "
                     "registroficial.gob.ec (the emergency decree) and the operator's own "
                     "comunicado at ocpecuador.com or eppetroecuador.ec before promoting a cell"},
    {"name": "CENACE daily demand, hydro dispatch and the published rationing schedules",
     "source": "CENACE and ARCERNNR", "coverage": "2015 onward for dispatch; the rationing "
                                                  "tables exist only for the emergency windows",
     "frequency": "daily", "publication_lag_days": 0.0,
     "revisions": "the schedule is republished intraday when the deficit changes",
     "licence": "free, public", "history_from": "2015-01", "pit_feasible": False,
     "assets": ("XNGUSD", "XTIUSD", "XCUUSD", "US500"),
     "mechanism_families": ("physical_supply", "output_shock"),
     "how_to_fetch": "the daily operation reports at cenace.gob.ec/informacion-operativa; the "
                     "RATIONING TABLES ARE REPLACED EVERY DAY AND KEPT NOWHERE, so the archive "
                     "layer's crawl is the only vintage and an un-crawled day is UNMEASURED"},
    {"name": "The declared electricity rationing episodes and their maximum daily outage hours",
     "source": "this pack's RATIONING_EPISODES, built from CENACE and distributor schedules and "
               "the national press",
     "coverage": "2023 onward", "frequency": "irregular, dated", "publication_lag_days": 0.0,
     "revisions": "PRESS_REPORTED; the hour counts are headline maxima, not daily averages",
     "licence": "derived from public sources", "history_from": "2023-10", "pit_feasible": True,
     "assets": ("XNGUSD", "XTIUSD", "XCUUSD", "US500"),
     "mechanism_families": ("output_shock", "event_reaction"),
     "how_to_fetch": "`rationing_state(day)` and `rationing_days(year)` in this module; the "
                     "distributor-level schedules must be recovered from the archive layer "
                     "before any hour-weighted cell is compiled"},
    {"name": "Camara Nacional de Acuacultura shrimp exports by volume, value and destination",
     "source": "Camara Nacional de Acuacultura", "coverage": "2010 onward, monthly and unbroken",
     "frequency": "monthly", "publication_lag_days": 15.0,
     "revisions": "the prior month is restated as late declarations arrive",
     "licence": "free, public", "history_from": "2010-01", "pit_feasible": False,
     "assets": ("USDCNH", "CORN", "SOYBEAN"),
     "mechanism_families": ("export_demand", "release_surprise"),
     "how_to_fetch": "the statistics page at cna-ecuador.com/estadisticas and the SENAE mirror "
                     "under heading 0306.17; the CHINA SHARE is the conditioner and the Chinese "
                     "customs import print is the mirror that validates it"},
    {"name": "ACORBANEC and AEBE banana export box counts by destination",
     "source": "ACORBANEC and AEBE", "coverage": "2015 onward weekly; monthly further back",
     "frequency": "weekly", "publication_lag_days": 7.0,
     "revisions": "weekly counts are provisional and reconciled monthly against SENAE",
     "licence": "free, public", "history_from": "2015-01", "pit_feasible": False,
     "assets": ("SUGAR", "COFARA"),
     "mechanism_families": ("export_supply", "administered_price"),
     "how_to_fetch": "the weekly bulletins at acorbanec.com and aebe.com.ec, joined to the "
                     "official minimum price from the MAG Acuerdo Ministerial in the Registro "
                     "Oficial; the SPREAD between the spot box price and the decreed floor is "
                     "the sector-stress variable and it is what the cell conditions on"},
    {"name": "ANECACAO cacao exports by grade (fino de aroma versus CCN-51) and destination",
     "source": "ANECACAO and SENAE", "coverage": "2010 onward", "frequency": "monthly",
     "publication_lag_days": 20.0,
     "revisions": "grade classification is restated when exporters reclassify",
     "licence": "free, public", "history_from": "2010-01", "pit_feasible": False,
     "assets": ("UKCOCOA", "USCOCOA"),
     "mechanism_families": ("physical_supply", "quality_spread"),
     "how_to_fetch": "anecacao.com/estadisticas plus the SENAE heading 1801.00 series; the GRADE "
                     "SPLIT is the point -- fino de aroma prices at a premium to the terminal "
                     "market and CCN-51 bulk at a differential, so the mix shift is a spread"},
    {"name": "SENAE customs export and import records by tariff heading and destination",
     "source": "Servicio Nacional de Aduana del Ecuador", "coverage": "2007 onward",
     "frequency": "monthly", "publication_lag_days": 30.0,
     "revisions": "routine restatement for two months", "licence": "free, public",
     "history_from": "2007-01", "pit_feasible": False,
     "assets": ("USDCNH", "UKCOCOA", "USCOCOA", "SUGAR", "CORN"),
     "mechanism_families": ("trade_flow", "mirror_comparison"),
     "how_to_fetch": "the boletines at aduana.gob.ec/boletines-estadisticos; use VOLUME, never "
                     "declared value -- the value series re-prices the commodity and a study "
                     "built on it is measuring the price twice and calling one of them supply"},
    {"name": "MEF public debt, arrears and the budget's assumed oil price",
     "source": "Ministerio de Economia y Finanzas", "coverage": "2000 onward",
     "frequency": "monthly", "publication_lag_days": 45.0,
     "revisions": "arrears are restated frequently and the definition has changed",
     "licence": "free, public", "history_from": "2000-01", "pit_feasible": False,
     "assets": ("XBRUSD", "USDBRL", "US500"),
     "mechanism_families": ("fiscal_state", "sovereign_risk"),
     "how_to_fetch": "finanzas.gob.ec/estadisticas-fiscales and the Proforma documents; the "
                     "ASSUMED oil price in the Proforma against the realised strip is the fiscal "
                     "shock variable and it is computable from this pack's own XBRUSD history"},
    {"name": "The sovereign credit and programme event record",
     "source": "this pack's SOVEREIGN_EVENTS, built from the exchange offers, the swap "
               "transaction documents and the IMF press releases",
     "coverage": "1999 onward", "frequency": "irregular, dated", "publication_lag_days": 0.0,
     "revisions": "PRESS_REPORTED on the dates; the documents themselves are authoritative",
     "licence": "derived from public sources", "history_from": "1999-09", "pit_feasible": True,
     "assets": ("USDBRL", "USDMXN", "US500", "XAUUSD"),
     "mechanism_families": ("sovereign_risk", "event_reaction"),
     "how_to_fetch": "`SOVEREIGN_EVENTS` in this module, confirmed against imf.org/en/Countries/"
                     "ECU and the MEF's own transaction announcements; the spread itself is a "
                     "collector input this box does not carry and is named UNMEASURED"},
    {"name": "Consejo Nacional Electoral referendum questions and results by parish",
     "source": "Consejo Nacional Electoral", "coverage": "2006 onward for digital results",
     "frequency": "irregular, by ballot", "publication_lag_days": 1.0,
     "revisions": "provisional counts are superseded by the final act",
     "licence": "free, public", "history_from": "2006-01", "pit_feasible": True,
     "assets": ("XBRUSD", "XTIUSD", "XCUUSD"),
     "mechanism_families": ("political_event", "physical_supply"),
     "how_to_fetch": "resultados.cne.gob.ec plus the Corte Constitucional dictamen that cleared "
                     "the question; THE 2023-08-20 ITT RESULT IS A SUPPLY DECISION with a dated "
                     "compliance deadline and belongs in the crude supply model, not in a "
                     "political-risk footnote"},
    {"name": "Autoridad Portuaria de Guayaquil and terminal container throughput",
     "source": "APG, Contecon and DP World Posorja", "coverage": "2010 onward",
     "frequency": "monthly", "publication_lag_days": 25.0,
     "revisions": "terminal-level figures are occasionally reclassified between berths",
     "licence": "free, public", "history_from": "2010-01", "pit_feasible": False,
     "assets": ("UKCOCOA", "USCOCOA", "SUGAR", "USDBRL"),
     "mechanism_families": ("logistics_regime", "physical_supply"),
     "how_to_fetch": "apg.gob.ec/estadisticas and the concessionaires' own bulletins; POSORJA "
                     "OPENED IN 2019 and re-routed part of the volume, which is a level shift "
                     "every throughput cell must carry as a break rather than as a trend"},
    {"name": "INAMHI hydrology, reservoir levels and the ENSO advisory state",
     "source": "INAMHI and the NOAA Climate Prediction Center",
     "coverage": "1980 onward for ENSO; 2010 onward for the published reservoir series",
     "frequency": "daily to monthly", "publication_lag_days": 2.0,
     "revisions": "the ENSO index is revised; the reservoir cota is not",
     "licence": "free, public / public domain", "history_from": "1980-01", "pit_feasible": True,
     "assets": ("XNGUSD", "SUGAR", "UKCOCOA", "USDCNH"),
     "mechanism_families": ("weather_state", "confound_control"),
     "how_to_fetch": "inamhi.gob.ec for the domestic hydrology and the CPC ENSO advisory for the "
                     "state; THIS IS A CONFOUND BEFORE IT IS A MECHANISM -- the same water drives "
                     "the grid, the pipelines, the banana and cacao harvests and the shrimp "
                     "cycle, and every cell in this pack must condition on it"},
    {"name": "Registro Oficial decree stream: exceptions, fuel prices and the banana floor",
     "source": "Registro Oficial", "coverage": "2003 onward digitised", "frequency": "daily",
     "publication_lag_days": 1.0, "revisions": "none; a decree is amended by another decree",
     "licence": "free, public", "history_from": "2003-01", "pit_feasible": True,
     "assets": ("XTIUSD", "XBRUSD", "SUGAR"),
     "mechanism_families": ("administered_price", "political_event"),
     "how_to_fetch": "registroficial.gob.ec; index by decree number and date and extract the "
                     "fuel band parameters and the banana precio minimo; THIS IS THE PROMOTION "
                     "GATE for every PRESS_REPORTED row in this pack"},
)
# --------------------------------------------------------------------------- actors
#: FIFTEEN ACTORS, each with all eleven fields. The two-lane order (2026-09-06) is why the
#: national champions are HERE and nowhere else: Petroecuador, OCP, CELEC, Banco Pichincha,
#: Lundin and EcuaCorriente move the metals, the crude and the softs, and none of them is ever
#: an instrument in this file.
ACTORS: tuple[dict[str, Any], ...] = (
    {"name": "The Ministerio de Economia y Finanzas (the fiscal authority that IS the macro "
             "authority)",
     "holds": "the Presupuesto General del Estado, the external debt stock, the arrears book and "
              "the oil-revenue account -- and, because there is no central bank with instruments, "
              "every macro lever the state actually possesses",
     "forced_to": ("present a budget built on an ASSUMED crude price and live with the gap",
                   "meet the IMF EFF structural benchmarks on a published review calendar",
                   "pay suppliers, subnational governments and the pension system in DOLLARS it "
                   "must first earn, borrow or not pay"),
     "when": "the Proforma in the last quarter for the calendar year; the debt and arrears "
             "bulletins monthly; the IMF reviews quarterly",
     "information": ("the daily oil lifting schedule and the realised export price",
                     "the tax collection run-rate from the SRI",
                     "the cash position at the Cuenta Unica del Tesoro",
                     "the IMF's own projections before they are published"),
     "constraints": ("NO MONETARY FINANCING: the 2021 Ley de Defensa de la Dolarizacion bars the "
                     "BCE from lending to the Treasury, which removes the escape valve every "
                     "other sovereign in this command has",
                     "a market that has defaulted twice in living memory and prices it",
                     "a fuel subsidy that cannot be cut without a national strike"),
     "instruments": ("XBRUSD", "XTIUSD", "USDBRL", "US500"),
     "counterparties": ("the holders of the 2030, 2035 and 2040 Global bonds",
                        "the IMF, CAF, IDB and the World Bank",
                        "the Chinese policy banks under the oil-prepayment contracts",
                        "the IESS and the Biess as captive domestic buyers"),
     "observables": ("the monthly debt stock and the arrears line",
                     "the Proforma's assumed oil price against the realised strip",
                     "the IMF review outcomes and their disbursement dates",
                     "the Certificados de Tesoreria issuance and its rate"),
     "impact": "a fiscal shock here cannot be absorbed by a currency, so it shows up as arrears, "
               "as an import compression, as a sovereign-spread move and eventually as an "
               "output loss -- which is the REAL-CHANNEL hypothesis this whole pack tests",
     "persistence": "an arrears build persists quarters and unwinds only with an oil rally or a "
                    "disbursement; a budget assumption persists the whole fiscal year",
     "falsifier": "the same windows in Peru and Colombia, where a comparable fiscal shock lands "
                  "in the currency first; if the Ecuadorian real variables move no more than "
                  "theirs, dollarisation is not doing the thing this pack says it does",
     "notes": "THE PACK'S CENTRAL ACTOR. In `pe` the central bank is the first actor; here the "
              "finance ministry is, because the finance ministry is the only one with levers"},
    {"name": "The Banco Central del Ecuador (a central bank with no monetary policy)",
     "holds": "the international reserves, the four-system balance sheet, the national payment "
              "system and the statistical apparatus",
     "forced_to": ("publish the reserve position weekly and the monetary survey monthly",
                   "clear the interbank payment system every business day",
                   "hold reserve cover against the banking system's own deposits rather than "
                   "against a currency it does not issue"),
     "when": "weekly for reserves, monthly for the Informacion Estadistica Mensual",
     "information": ("the banking system's settlement flows in real time",
                     "the public sector's deposit position",
                     "the trade and remittance data before it is published"),
     "constraints": ("NO POLICY RATE, NO OPEN-MARKET OPERATION AND NO DISCOUNT WINDOW: under "
                     "dollarisation the instrument set is empty by construction",
                     "a statutory bar on financing the Treasury since 2021",
                     "governance that was politicised between 2008 and 2021 and partly "
                     "de-politicised after"),
     "instruments": ("USDBRL", "USDMXN", "US500"),
     "counterparties": ("the commercial banks in the payment system",
                        "the Treasury as a depositor rather than a borrower",
                        "the correspondent banks holding the reserves abroad"),
     "observables": ("the weekly reserve print", "the four-system composition",
                     "the monthly deposit and credit aggregates",
                     "the quarterly remittance series by province"),
     "impact": "nothing this bank does moves a price directly; its PUBLICATIONS are the state "
               "variables every other domain conditions on, which is a different and quieter "
               "kind of importance",
     "persistence": "a reserve level persists weeks; a definitional change persists forever and "
                    "is the thing a pooled study will trip over",
     "falsifier": "if reserve prints move the executable legs at all after controlling for the "
                  "global dollar and the oil strip, this bank is doing something a dollarised "
                  "central bank is not supposed to be able to do, and that is worth knowing",
     "notes": "THE HONEST NULL LIVES HERE: a central bank with no instruments is a central bank "
              "whose announcements should have no announcement effect, and testing that is "
              "worth more than assuming it"},
    {"name": "EP Petroecuador and the state's Amazonian blocks",
     "holds": "roughly three quarters of national crude production, the SOTE pipeline, the "
              "Esmeraldas refinery and the export cargo book",
     "forced_to": ("declare FORCE MAJEURE to cargo buyers when the pipelines stop",
                   "supply the domestic market at an administered price whatever the export "
                   "price is",
                   "deliver the contracted barrels under the Chinese oil-prepayment agreements "
                   "before it can sell a cargo on the open market"),
     "when": "continuously; the monthly production and export report lands three to five weeks "
             "after the month it describes",
     "information": ("the pipeline's real-time pumping state and the erosion monitoring",
                     "the field-level production before anyone else sees it",
                     "the tender bids for its cargoes"),
     "constraints": ("ONE EROSION FRONT ACROSS BOTH PIPELINES: there is no third route out of "
                     "the Oriente and no rail, so a cut at the Coca crossing stops everything",
                     "a domestic subsidy obligation that consumes the refinery's output",
                     "prepaid Chinese barrels that are committed before they are produced"),
     "instruments": ("XBRUSD", "XTIUSD"),
     "counterparties": ("the Chinese state trading houses under the prepayment contracts",
                        "the US Gulf and Asian refiners buying spot cargoes",
                        "OCP Ecuador for the heavy-crude capacity it does not own",
                        "the Ministry of Finance, whose budget its receipts fund"),
     "observables": ("the force-majeure declarations themselves",
                     "the monthly production by field and by grade",
                     "the cargo tender awards", "the SOTE pumping bulletins"),
     "impact": "a shut-in removes real barrels from the seaborne market on a dated schedule; the "
               "share is small against world supply, so the testable claim is about the GRADE "
               "and the differential rather than about the benchmark",
     "persistence": "a rupture persists two to five weeks; a strike-driven shut-in persists as "
                    "long as the fields are occupied and restarts slowly",
     "falsifier": "declared outage windows match a matched-weekday control on XBRUSD and XTIUSD "
                  "once OPEC+ decisions, US inventories and the dollar are conditioned on -- in "
                  "which case the barrels were too few to matter and the pack says so",
     "notes": "AN ACTOR, NEVER AN INSTRUMENT. The two-lane order forbids hunting a single name "
              "and this one is a state enterprise with no listed equity anyway"},
    {"name": "OCP Ecuador (the private heavy-crude pipeline)",
     "holds": "the Oleoducto de Crudos Pesados, the second and newer of the two routes across "
              "the same eroding river",
     "forced_to": ("publish operational notices when it suspends pumping",
                   "build and rebuild emergency variants around the advancing erosion front",
                   "keep the private operators' barrels moving under ship-or-pay contracts"),
     "when": "continuously; notices are published the day a decision is taken",
     "information": ("its own erosion monitoring, which is independent of the state's",
                     "the shippers' nomination book",
                     "the right-of-way's geotechnical condition"),
     "constraints": ("the SAME erosion front as the state pipeline, which destroys the "
                     "diversification the second route was built for",
                     "ship-or-pay obligations that make a shutdown expensive on both sides",
                     "an environmental-liability record that constrains how fast it can move"),
     "instruments": ("XBRUSD", "XTIUSD"),
     "counterparties": ("the private consortium producers in the Oriente",
                        "EP Petroecuador, with which it swaps capacity in an emergency",
                        "the downstream terminal at Esmeraldas"),
     "observables": ("the operational comunicados", "the variante emergente construction reports",
                     "the shippers' nominations where published",
                     "the environment ministry's spill notifications"),
     "impact": "a private operator's notice is often the FIRST public date of an interruption, "
               "ahead of the state's force-majeure declaration by days",
     "persistence": "days to weeks per event; the erosion itself is a permanent, advancing state",
     "falsifier": "if OCP notices and Petroecuador declarations never disagree on a date, one of "
                  "the two is copying the other and the earlier-date claim is worthless",
     "notes": "THE VALUE IS THE DISAGREEMENT between two operators reading the same river, and "
              "no desk sees it without reading both grounds"},
    {"name": "CELEC EP and the hydro complex (Coca Codo Sinclair, Paute-Mazar)",
     "holds": "roughly three quarters of national generation capacity, concentrated in hydro on "
              "two river systems, including a 1,500 MW plant on the SAME river that cuts the "
              "pipelines",
     "forced_to": ("dispatch to meet demand or publish a rationing schedule when it cannot",
                   "lease emergency thermal generation at spot prices in a drought",
                   "import from Colombia when Colombia has surplus, which it did not in 2024"),
     "when": "daily dispatch; the rationing schedule for the following day is published in the "
             "afternoon during an emergency",
     "information": ("reservoir levels and inflows before the market sees them",
                     "the thermal park's true availability",
                     "the Colombian interconnection's offered capacity"),
     "constraints": ("hydrology it cannot control and a reservoir at Mazar with days rather than "
                     "months of storage",
                     "a thermal park with a long history of unavailability",
                     "a plant with documented construction defects on the same eroding river"),
     "instruments": ("XNGUSD", "XTIUSD", "XCUUSD"),
     "counterparties": ("the distributors that implement the cuts",
                        "the emergency-generation lessors",
                        "XM and the Colombian interconnection",
                        "the industrial consumers that lose load first"),
     "observables": ("the published rationing schedule by province and hour",
                     "the Mazar reservoir cota", "daily national demand served",
                     "the emergency generation tenders and their prices"),
     "impact": "a scheduled loss of industrial load is a dated, quantified output shock, and "
               "because the schedule is published the DAY BEFORE it is one of the few physical "
               "shocks on this desk that is knowable in advance",
     "persistence": "an episode persists as long as the hydrology does -- weeks to three months",
     "falsifier": "if Ecuadorian rationing windows show no effect on the copper, gas or crude "
                  "legs after conditioning on the global cycle, the economy is too small to "
                  "register and the mechanism is domestic-only, which is a real finding",
     "notes": "THE SINGLE BEST FORWARD-LOOKING PHYSICAL SERIES IN THE PACK"},
    {"name": "The CONAIE and the indigenous federations (CONFENIAE, ECUARUNARI)",
     "holds": "the mobilisation capacity that has removed three presidents and reversed two fuel "
              "decrees, and the territorial presence on top of the Amazonian oil blocks",
     "forced_to": ("convene and announce a paro publicly before it begins, in Kichwa and "
                   "Spanish, because legitimacy requires an assembly",
                   "negotiate at a published mesa de dialogo once the state concedes one",
                   "defend prior-consultation rights case by case in the courts"),
     "when": "the announcement precedes the action by days; the assemblies are dated and public",
     "information": ("the state of negotiation with the government before it is public",
                     "the mobilisation capacity of each provincial federation",
                     "the local grievance state around each block and mine"),
     "constraints": ("a membership that bears the cost of a long strike directly",
                     "an internal politics that can split a mobilisation",
                     "a legal framework that recognises consultation but not veto"),
     "instruments": ("XBRUSD", "XTIUSD", "XCUUSD"),
     "counterparties": ("the Presidencia at the dialogue table",
                        "the oil and mining operators on their territories",
                        "the transport federations that join or do not join"),
     "observables": ("the public convocatoria and its date",
                     "the provincial federations' own announcements in Kichwa and Shuar",
                     "the mesa de dialogo agenda and its published agreements",
                     "the road-closure maps the federations themselves circulate"),
     "impact": "a national paro shuts in wellheads and closes highways; the 2019 and 2022 "
               "episodes each removed a large fraction of national production for days to weeks",
     "persistence": "eleven days in 2019, eighteen in 2022; restarts are slow and partial",
     "falsifier": "paro windows with NO production effect -- which happens, because a transport "
                  "strike is not an oilfield occupation -- separate 'the country stopped' from "
                  "'the barrels stopped', and only the second is a supply claim",
     "notes": "THE ANNOUNCEMENT IS IN KICHWA FIRST. This is the concrete reason the pack carries "
              "two indigenous languages rather than listing them for form"},
    {"name": "The Consejo Nacional Electoral and the referendum machinery",
     "holds": "the ballot, the count by parish and the electoral calendar; and in 2023 it held "
              "the question of whether an oil field would keep producing",
     "forced_to": ("publish the question as cleared by the Corte Constitucional",
                   "count and publish by parish within days",
                   "run a snap election within a fixed period after a muerte cruzada"),
     "when": "by ballot; the 2023-08-20 and 2024-04-21 dates are the recent ones",
     "information": ("the padron and the turnout in real time",
                     "the provisional count hours before the final act"),
     "constraints": ("a constitutional court that can and does reject questions",
                     "a fixed statutory timetable once a dissolution is declared"),
     "instruments": ("XBRUSD", "XTIUSD", "XCUUSD", "US500"),
     "counterparties": ("the Presidencia that calls the consulta",
                        "the Corte Constitucional that clears the question",
                        "the operators whose concessions the answer binds"),
     "observables": ("the cleared question text", "the result by parish",
                     "the compliance deadline the result sets",
                     "the Tribunal Contencioso Electoral's challenges"),
     "impact": "THE ONLY PLACE ON THIS DESK WHERE AN ELECTORATE SETS PHYSICAL SUPPLY. The ITT "
               "result binds roughly 50 kb/d and the Choco Andino result binds a mining district",
     "persistence": "permanent unless another ballot reverses it; the compliance path is phased",
     "falsifier": "if the crude legs show nothing across 2023-08-20 and nothing across the "
                  "2024-08-31 deadline, the market had already priced the polls -- which is a "
                  "testable alternative, not an absence of mechanism",
     "notes": "the referendum is filed as a SUPPLY OBJECT here, not as political colour"},
    {"name": "The shrimp farmers and the Camara Nacional de Acuacultura",
     "holds": "the world's largest farmed-shrimp export industry, concentrated on the Guayas "
              "estuary and in El Oro, with a single dominant buyer",
     "forced_to": ("harvest on a biological cycle that does not wait for a price",
                   "buy feed whose cost is a soymeal and fishmeal function",
                   "ship through Guayaquil and Posorja whatever the security situation is"),
     "when": "continuous harvest cycles; the export volume prints monthly",
     "information": ("the pond-side price and the stocking decisions weeks ahead of the export "
                     "print",
                     "the Chinese buyers' order flow",
                     "the water temperature and disease state on their own farms"),
     "constraints": ("A SINGLE DOMINANT BUYER: more than half the volume goes to China, so a "
                     "Chinese demand or inspection decision is an Ecuadorian industry event",
                     "an energy-intensive aeration process that the 2024 rationing hit directly",
                     "feed costs set in Chicago rather than in Guayaquil"),
     "instruments": ("USDCNH", "CORN", "SOYBEAN"),
     "counterparties": ("the Chinese importers and their customs authority",
                        "the European and US buyers who take the value-added fraction",
                        "the feed mills and their soymeal suppliers",
                        "the container lines out of Guayaquil and Posorja"),
     "observables": ("the monthly export volume by destination",
                     "the pond-side price commentary", "the feed-cost index",
                     "Chinese customs import prints as the mirror"),
     "impact": "the industry is a price-taker on its output and a price-taker on its inputs, so "
               "the testable claim runs from CORN and SOYBEAN into margin and from USDCNH into "
               "demand, never the other way round",
     "persistence": "a stocking decision persists a growing cycle -- roughly three to four months",
     "falsifier": "if Ecuadorian export volumes lead Chinese import prints by no more than the "
                  "shipping time, the series carries no information the mirror does not",
     "notes": "THE ENERGY LINK IS THE UNDERRATED ONE: aeration is electricity, and the 2024 "
              "rationing episode is a natural experiment on an export industry's power input"},
    {"name": "The banana exporters (ACORBANEC, AEBE) under the official minimum price",
     "holds": "roughly a quarter of world banana trade, grown mostly in El Oro, Guayas and Los "
              "Rios and shipped mostly through Puerto Bolivar and Guayaquil",
     "forced_to": ("contract at or above the precio minimo de sustentacion set by ministerial "
                   "agreement, whatever the spot market does",
                   "harvest weekly on a fixed cutting cycle",
                   "ship in reefer containers whose freight rate they do not set"),
     "when": "weekly box counts; the official price is set annually before the season",
     "information": ("the spot box price against the decreed floor, week by week",
                     "the Russian, European and Middle Eastern buyers' order books",
                     "the black-sigatoka and Fusarium pressure on their own farms"),
     "constraints": ("AN ADMINISTERED FLOOR that makes the observable a SPREAD rather than a "
                     "price: when spot trades below the decree the contract system strains "
                     "publicly and the strain is reported",
                     "reefer freight and fuel costs that move with the crude complex",
                     "a Russian destination share that makes the trade geopolitically exposed"),
     "instruments": ("SUGAR", "COFARA"),
     "counterparties": ("the Russian, EU and Middle Eastern importers",
                        "the container lines and the reefer operators",
                        "the Ministry of Agriculture that sets the floor"),
     "observables": ("weekly exported boxes by destination",
                     "the decreed minimum price in the Registro Oficial",
                     "the spot-versus-floor spread as reported by the associations",
                     "Puerto Bolivar vessel calls"),
     "impact": "THERE IS NO BANANA CONTRACT ANYWHERE, so this actor's executable reach is weak "
               "by construction and the pack SAYS SO rather than dressing a soft-complex beta "
               "up as a banana trade",
     "persistence": "the decreed floor persists a season; a freight shock persists a quarter",
     "falsifier": "the softs-complex legs move identically in weeks with and without an "
                  "Ecuadorian banana event, which is the expected result and must be measured "
                  "rather than assumed",
     "notes": "AN ADMINISTERED PRICE ON A QUARTER OF WORLD TRADE is worth carrying even when the "
              "executable leg is weak, because the DECREE is a dated, published policy event"},
    {"name": "The cacao exporters and ANECACAO (fino de aroma and CCN-51)",
     "holds": "a top-three world cacao export position and the dominant share of the world's "
              "fine-flavour fraction, grown on the coastal plain and shipped from Guayaquil",
     "forced_to": ("sell against a liquid terminal market they do not influence",
                   "declare the grade split at customs",
                   "harvest on a main and mid-crop cycle set by rainfall"),
     "when": "monthly export tonnage; the main crop peaks between roughly March and June",
     "information": ("the farm-gate price and the arrivals at the coastal buying stations",
                     "the grade mix before it is declared",
                     "the pod-count and disease state in the field"),
     "constraints": ("a terminal market dominated by West African supply, which means an "
                     "Ecuadorian volume change is a SHARE story rather than a price story",
                     "a quality premium that depends on fermentation practice and can be lost",
                     "port and security frictions at the one gate"),
     "instruments": ("UKCOCOA", "USCOCOA"),
     "counterparties": ("the international grinders and traders",
                        "the domestic buying stations and intermediaries",
                        "the shipping lines out of Guayaquil"),
     "observables": ("monthly export tonnage by grade and destination",
                     "the fino de aroma premium where quoted",
                     "the customs heading 1801.00 volume series",
                     "the main-crop arrivals commentary"),
     "impact": "THE CLEANEST SOFT LINK IN THE PACK: a liquid contract on the other side, a "
               "published grade split and a supply share that grew precisely as West Africa "
               "failed, which is a dated substitution rather than a correlation",
     "persistence": "a harvest quarter; a grade-mix shift persists years",
     "falsifier": "Ecuadorian arrivals explain nothing in UKCOCOA once Ivorian and Ghanaian "
                  "arrivals are conditioned on, which is the null and is likely to be true in "
                  "most windows",
     "notes": "THE FINO DE AROMA / CCN-51 SPLIT IS A SPREAD, not one series, and treating it as "
              "one is how a real mechanism gets averaged away"},
    {"name": "The Guayaquil port complex, Contecon and DP World Posorja",
     "holds": "the largest container gate on South America's Pacific coast and the single "
              "chokepoint through which the banana, the shrimp and the cacao all leave",
     "forced_to": ("publish monthly throughput",
                   "operate through states of exception and military deployment",
                   "submit to interdiction inspection regimes imposed by destination customs"),
     "when": "continuous; the throughput bulletin is monthly and roughly a month late",
     "information": ("the booking and yard state days before a volume print",
                     "the inspection intensity at the gate",
                     "the vessel schedule and the blank sailings"),
     "constraints": ("A SECOND FUNCTION IT DID NOT CHOOSE: the same containers carry the "
                     "region's cocaine exports, so interdiction and violence are operational "
                     "variables rather than background",
                     "a draft and channel constraint that Posorja was built to relieve",
                     "labour and security risk concentrated in one city"),
     "instruments": ("UKCOCOA", "USCOCOA", "SUGAR", "USDBRL"),
     "counterparties": ("the exporters of all three commodities",
                        "the container lines and their alliances",
                        "the destination customs authorities running the inspections",
                        "the armed forces deployed under the 2024 decree"),
     "observables": ("monthly TEU throughput by terminal",
                     "the seizure announcements and their tonnages",
                     "vessel calls and blank sailings",
                     "the states of exception covering Guayas"),
     "impact": "a gate event is a SIMULTANEOUS shock to three export series, which makes it a "
               "joint test rather than three separate weak ones",
     "persistence": "an acute security episode persists days; an inspection regime persists "
                    "quarters and is the more damaging of the two",
     "falsifier": "throughput windows after a security event match the same months in prior "
                  "years once the harvest cycle and Posorja's 2019 opening are conditioned on",
     "notes": "POSORJA'S 2019 OPENING IS A LEVEL SHIFT and must be carried as a break"},
    {"name": "The dollarised commercial banks and ASOBANCA",
     "holds": "the deposit base of an economy that cannot print, and therefore the entire "
              "domestic liquidity mechanism",
     "forced_to": ("hold liquidity against deposits with NO lender of last resort behind them",
                   "report to the Superintendencia monthly",
                   "fund a loan book in an economy whose income is commodity-cyclical"),
     "when": "monthly returns; the liquidity and delinquency series with a month's lag",
     "information": ("their own deposit flows in real time",
                     "the corporate sector's working-capital stress before it is reported",
                     "the informal dollar flows through their own remittance channels"),
     "constraints": ("NO LENDER OF LAST RESORT. 1999 is the reference case: a deposit run in a "
                     "dollarised system is a solvency event with no monetary backstop",
                     "interest-rate CEILINGS set by a government board, which cap risk pricing",
                     "a concentrated economy whose shocks hit every borrower at once"),
     "instruments": ("USDBRL", "US500", "XAUUSD"),
     "counterparties": ("depositors, who can move dollars offshore with no capital control",
                        "the BCE as a payment-system operator and not as a backstop",
                        "the correspondent banks abroad"),
     "observables": ("monthly deposits by type and by bank",
                     "structural liquidity ratios", "delinquency by segment",
                     "the spread between deposit and lending rates against the ceilings"),
     "impact": "a banking stress here has no monetary absorption, so it transmits to output "
               "quickly; this is the channel that makes the 1999 case the pack's standing prior",
     "persistence": "a deposit trend persists quarters; a run would be days",
     "falsifier": "deposit-stress months show no effect on the executable legs, which is likely "
                  "and would say the economy is too small to register globally even in stress",
     "notes": "AN ACTOR CLASS, NEVER AN INSTRUMENT. No Ecuadorian bank is a broker symbol and "
              "the two-lane order would forbid hunting one if it were"},
    {"name": "The Ecuadorian diaspora and the remittance corridor",
     "holds": "the second-largest source of foreign exchange after oil in most years, sent from "
              "the United States, Spain and Italy to households in Azuay, Canar and Guayas",
     "forced_to": ("send on a seasonal and event-driven calendar -- school terms, festivals, "
                   "emergencies -- rather than on a price",
                   "use formal channels that report, because the destination is dollarised and "
                   "there is no black-market rate to beat"),
     "when": "continuous; the BCE publishes quarterly by province and by sending country",
     "information": ("household need at the receiving end",
                     "the labour market in the sending country"),
     "constraints": ("a US immigration policy cycle that can change the flow abruptly",
                     "a Spanish and Italian labour market with its own cycle",
                     "sending costs that vary by corridor"),
     "instruments": ("USDBRL", "US500", "CORN"),
     "counterparties": ("the receiving households", "the money-transfer operators and the banks",
                        "the retail and construction sectors the money is spent in"),
     "observables": ("the quarterly remittance series by province and sending country",
                     "the US and Spanish employment prints as the leading half",
                     "the domestic retail and construction activity indices"),
     "impact": "THIS IS THE ONE INFLOW THAT IS COUNTER-CYCLICAL TO THE DOMESTIC ECONOMY: it "
               "rises when Ecuador is in trouble and its senders are not, which partly replaces "
               "the stabilising role a floating currency would play",
     "persistence": "a labour-market driven shift persists quarters",
     "falsifier": "remittance growth that tracks Ecuadorian conditions rather than the sending "
                  "countries' labour markets would mean the counter-cyclical story is backwards",
     "notes": "NO SIBLING PACK HAS A DOLLAR INFLOW WITH NO EXCHANGE-RATE STEP IN IT: elsewhere "
              "remittances are an FX supply, here they are simply money arriving"},
    {"name": "The industrial miners: EcuaCorriente at Mirador and Lundin at Fruta del Norte",
     "holds": "the country's only two large-scale producing mines -- a Chinese-owned copper "
              "operation and a Canadian-owned gold one -- in a country whose electorate has "
              "voted to ban mining in two districts",
     "forced_to": ("ship concentrate and dore on a schedule against exchange-linked formulas",
                   "obtain and defend consultation and environmental permits case by case",
                   "operate through states of exception and illegal-mining incursions"),
     "when": "continuous production; quarterly and annual operational reporting",
     "information": ("their own grade and throughput before it is reported",
                     "the local consultation and conflict state",
                     "the concentrate buyers' terms"),
     "constraints": ("A LEGAL SYSTEM THAT HAS HALTED PROJECTS BY CONSULTATION RULING, which is "
                     "a genuinely different risk from a labour negotiation or a road blockade",
                     "power supply that was rationed nationally in 2024",
                     "illegal mining encroaching on formal concessions"),
     "instruments": ("XCUUSD", "XAUUSD"),
     "counterparties": ("the Chinese smelters buying the copper concentrate",
                        "the refiners and banks taking the gold",
                        "the communities and courts adjudicating consultation",
                        "the state as concession grantor and royalty collector"),
     "observables": ("reported production and shipments",
                     "the mining cadastre and its suspensions",
                     "the consultation rulings and referendum results",
                     "the export volumes under the customs headings"),
     "impact": "small against world supply, so the testable claim is about the CONSULTATION "
               "MECHANISM -- a court or a ballot stopping a mine -- rather than about tonnes",
     "persistence": "a ruling persists indefinitely; a power outage persists an episode",
     "falsifier": "consultation and referendum events with no effect on XCUUSD or XAUUSD, which "
                  "is the expected outcome given the scale and must be shown, not assumed",
     "notes": "ACTORS, NEVER INSTRUMENTS. The listed parents are single names and the two-lane "
              "order forbids hunting them"},
    {"name": "The illicit export chain through Guayaquil and the interdiction authorities",
     "holds": "the region's principal cocaine-export chokepoint, embedded in the same container "
              "flow that carries the bananas, the shrimp and the cacao",
     "forced_to": ("move product through a gate that is inspected, seized from and publicised",
                   "respond to interdiction with violence that is itself dated and reported",
                   "corrupt or coerce the same port labour the legal exporters depend on"),
     "when": "continuous; the seizures and the security decrees are dated",
     "information": ("the inspection regime's actual intensity",
                     "the port labour and customs relationships"),
     "constraints": ("destination customs regimes that tighten after a large seizure",
                     "a state that declared an internal armed conflict in January 2024",
                     "rival groups whose conflict closes the port city itself"),
     "instruments": ("UKCOCOA", "USCOCOA", "USDBRL", "US500"),
     "counterparties": ("the destination customs and police authorities",
                        "the container lines whose boxes are used",
                        "the legal exporters who bear the inspection cost"),
     "observables": ("seizure announcements and tonnages",
                     "states of exception and curfews covering Guayas",
                     "destination-market inspection-rate changes",
                     "port throughput in the weeks after a major event"),
     "impact": "the MEASURABLE effect is on the legal exporters' cost and lead time through "
               "inspection intensity, which is how a security story becomes a supply-chain "
               "variable rather than a headline",
     "persistence": "an acute episode persists days; a tightened inspection regime persists "
                    "quarters and is the expensive one",
     "falsifier": "throughput and export lead times unchanged after major seizure and violence "
                  "events once seasonality and the Posorja break are conditioned on",
     "notes": "CARRIED AS AN ACTOR BECAUSE IT IS ONE. Leaving it out would mean modelling "
              "Guayaquil's container flow while ignoring the thing that most often stops it"},
)
# --------------------------------------------------------------------------- domains
DOMAINS: tuple[dict[str, Any], ...] = (
    {"id": "EC-A", "title": "Full dollarisation as the absorbing constraint",
     "objects": ("the weekly reserve print and the four-system composition",
                 "the monthly deposit base and the structural liquidity ratio",
                 "the quarterly remittance inflow by province and sending country",
                 "the CPI read as real-exchange-rate drift against Peru and Colombia"),
     "conditions": ("the era: pre-2021 politicised BCE versus the post-Ley de Defensa regime",
                    "whether the month carried a deposit contraction",
                    "the global dollar state, read off the executable legs and US500",
                    "whether a fiscal arrears build was reported in the same month"),
     "instruments": ("USDBRL", "USDMXN", "US500", "XAUUSD"),
     "controls": ("THE SAME WINDOWS IN `pe` AND `co`, which float: the whole point of the domain "
                  "is that a shock they take in the currency this one must take elsewhere",
                  "months with an equivalent global dollar move and no Ecuadorian event",
                  "a block-shuffled deposit series, which is the null for a state variable"),
     "notes": "THERE IS NO CURRENCY CELL HERE AND THERE CANNOT BE. This domain mints CONDITIONER "
              "cells: it says when the regional legs should be read as carrying Ecuador and when "
              "they should not, and its positive result would be an effect in the REAL legs"},
    {"id": "EC-B", "title": "Ecuadorian crude: Oriente, Napo, the OPEC history and the cargo book",
     "objects": ("monthly production by field and by grade",
                 "the export volume and the cargo tender awards",
                 "the Block 43 line as a separate, referendum-bound series",
                 "the OPEC membership years and the 2020-01-01 exit as a reporting break"),
     "conditions": ("the ITT regime (`itt_regime`): producing, winding down, or post-deadline",
                    "whether the month contained a declared pipeline outage",
                    "the OPEC+ decision state in the same window",
                    "the US Gulf heavy-sour supply state, which is the substitution leg"),
     "instruments": ("XBRUSD", "XTIUSD", "XNGUSD", "US500"),
     "controls": ("Colombian crude production in the same months (the `co` pack's series), "
                  "separating 'Andean supply' from 'Ecuadorian supply'",
                  "months with an equivalent OPEC+ decision and no Ecuadorian event",
                  "a randomised-month null on the field-level series"),
     "notes": "THE VOLUMES ARE SMALL AGAINST WORLD SUPPLY and the pack says so: the honest claim "
              "is about the GRADE and the differential rather than about the benchmark, and "
              "XNGUSD is in the tuple as the ENERGY-COMPLEX PLACEBO -- Ecuador exports no gas, "
              "so an Ecuadorian crude condition that moves gas is measuring the complex"},
    {"id": "EC-C", "title": "The pipeline plane: SOTE, OCP and the Coca river's regressive erosion",
     "objects": ("the declared rupture, pre-emptive shutdown and shut-in episodes",
                 "the force-majeure declarations and their dates",
                 "the erosion front's published position and rate of advance",
                 "the variante emergente construction record"),
     "conditions": ("whether the day falls inside a declared outage (`is_pipeline_outage`)",
                    "the cause: rupture, pre-emptive shutdown, or strike-driven shut-in",
                    "the rainy-season state, which is when the front advances fastest",
                    "whether BOTH pipelines were down or only one"),
     "instruments": ("XBRUSD", "XTIUSD", "US500"),
     "controls": ("the same windows in Colombia, where the pipeline risk is SABOTAGE rather than "
                  "geomorphology -- a different generating process on the same benchmark",
                  "matched windows with an equivalent global supply headline and no Ecuadorian "
                  "event",
                  "pre-2020 windows, before the waterfall collapsed and the front began"),
     "notes": "THE PACK'S PRIMARY PHYSICAL MECHANISM. A published, dated, lawful supply "
              "interruption announced by the operator. Every episode row is PRESS_REPORTED and "
              "may generate hypotheses; none may be promoted until a Registro Oficial decree or "
              "an operator comunicado is attached to its start and end"},
    {"id": "EC-D", "title": "The ITT/Yasuni referendum: a field shut by ballot",
     "objects": ("the 2023-08-20 result and the parish-level vote",
                 "the 2024-08-31 compliance deadline and the phased shutdown timetable",
                 "the Block 43 production line before and after",
                 "the same-day Choco Andino mining question as the mining analogue"),
     "conditions": ("the regime returned by `itt_regime(day)`",
                    "whether the window contains a court ruling on compliance",
                    "the global crude supply state at the time"),
     "instruments": ("XBRUSD", "XTIUSD", "XCUUSD"),
     "controls": ("the same windows in `co` and `pe`, neither of which has ever voted on a field",
                  "matched windows with an equivalent OPEC+ supply decision",
                  "a randomised-date null over the same election calendar"),
     "notes": "UNIQUE IN THIS BOOK and the honest null is live: the market may have priced the "
              "polls weeks earlier, in which case the ballot day shows nothing and the "
              "COMPLIANCE DEADLINE is the tradable date instead. Both are testable"},
    {"id": "EC-E",
     "title": "The electricity crisis: hydrology, rationing hours and industrial load",
     "objects": ("the published rationing schedules by province and hour",
                 "the Mazar reservoir cota and the Coca Codo output",
                 "the emergency generation tenders and their prices",
                 "the two decreed national non-working days of April 2024"),
     "conditions": ("the rationing state returned by `rationing_state(day)` and its hour count",
                    "the ENSO state, which is the shared driver and the confound",
                    "whether Colombian interconnection imports were available",
                    "the export industries' own exposure: shrimp aeration and mine power"),
     "instruments": ("XNGUSD", "XTIUSD", "XCUUSD", "US500"),
     "controls": ("the same ENSO state in years with no rationing, which separates the WATER "
                  "from the OUTAGE",
                  "Colombian and Peruvian hydrology in the same months",
                  "matched weeks with an equivalent global energy move and no Ecuadorian cuts"),
     "notes": "THE FORWARD-LOOKING ONE: the following day's cuts are published the afternoon "
              "before, which is the rarest property a physical series can have. The confound is "
              "severe and named -- the same drought drives the crops and the pipelines"},
    {"id": "EC-F", "title": "The sovereign: default, restructuring, debt-for-nature and the IMF",
     "objects": ("the 1999, 2008 and 2020 credit events and the 2009 buyback",
                 "the 2023 Galapagos swap and the 2024 Amazon transaction",
                 "the IMF EFF approval, review and disbursement dates",
                 "the monthly arrears line as the between-events stress gauge"),
     "conditions": ("the event class: default, exchange, swap, programme approval or review",
                    "the oil price regime at the time, since the fiscal path is an oil function",
                    "whether an election or a muerte cruzada fell in the same window"),
     "instruments": ("USDBRL", "USDMXN", "US500", "XAUUSD"),
     "controls": ("Argentine and Brazilian sovereign events in the same months",
                  "matched windows with an equivalent EM risk move and no Ecuadorian event",
                  "a randomised-date null over the same calendar"),
     "notes": "THE SPREAD ITSELF IS ABSENT from this broker, so this domain mints CONDITIONER "
              "cells on the regional legs and states plainly that the direct instrument is "
              "UNMEASURED rather than proxying an Ecuadorian spread with a Brazilian one"},
    {"id": "EC-G", "title": "Shrimp: the world's largest farmed exporter and its Chinese buyer",
     "objects": ("monthly export volume and value by destination",
                 "the Chinese share and the Chinese customs mirror",
                 "the feed-cost leg in corn and soymeal",
                 "the 2024 rationing episode as a power-input natural experiment"),
     "conditions": ("the China share bucket: rising, flat or falling against its own trend",
                    "whether the month fell inside a declared rationing episode",
                    "the feed-cost state read off CORN and SOYBEAN"),
     "instruments": ("USDCNH", "CORN", "SOYBEAN", "US500"),
     "controls": ("Indian and Vietnamese shrimp export months, the competing origins",
                  "months with an equivalent Chinese import print and no Ecuadorian event",
                  "the same feed-cost moves in months with no shrimp-volume change"),
     "notes": "THE DIRECTION OF THE CLAIM MATTERS: the industry is a price-taker on both sides, "
              "so the testable flows run from CORN and SOYBEAN into margin and from USDCNH into "
              "demand. A cell claiming Ecuadorian shrimp moves corn would be backwards"},
    {"id": "EC-H", "title": "Bananas: the world's largest exporter and its administered floor",
     "objects": ("the weekly exported box counts by destination",
                 "the annual precio minimo de sustentacion in the Registro Oficial",
                 "the spot-versus-floor spread as the sector-stress variable",
                 "Puerto Bolivar vessel calls as the physical gate"),
     "conditions": ("whether spot traded below the decreed floor that week",
                    "the destination mix, with the Russian share as the geopolitical leg",
                    "the reefer freight and fuel state read off the crude legs"),
     "instruments": ("SUGAR", "COFARA", "XBRUSD"),
     "controls": ("the softs complex in weeks with no Ecuadorian banana event, which is the "
                  "expected null and the whole reason this domain is declared weak",
                  "the same weeks in the Colombian and Costa Rican banana seasons",
                  "a matched-week placebo on the tropical softs"),
     "notes": "DECLARED WEAK BY CONSTRUCTION AND KEPT ANYWAY. There is no banana contract "
              "anywhere; what is real here is the DECREE -- a dated, published administered "
              "price on a quarter of world trade -- and XBRUSD carries the reefer-fuel leg"},
    {"id": "EC-I", "title": "Cacao fino de aroma against the West African supply shock",
     "objects": ("monthly export tonnage by grade and destination",
                 "the fino de aroma versus CCN-51 mix as a spread object",
                 "the main and mid-crop arrivals cycle",
                 "the share gain against Ivorian and Ghanaian arrivals"),
     "conditions": ("the crop phase: main crop, mid crop or between",
                    "the West African arrivals state, which is the dominant term",
                    "whether the window contains a Guayaquil port disruption"),
     "instruments": ("UKCOCOA", "USCOCOA", "SUGAR", "COFARA"),
     "controls": ("Ivorian and Ghanaian arrivals in the same weeks, which must be conditioned on "
                  "before any Ecuadorian claim is even stated",
                  "the two cocoa contracts against each other, which separates a global cocoa "
                  "move from a London-versus-New-York basis move",
                  "SUGAR and COFARA as the tropical-softs complex placebo"),
     "notes": "THE CLEANEST SOFT LINK IN THE PACK and still a hard one: Ecuador is a share story "
              "against a West African price story, so the honest test is a SUBSTITUTION test "
              "conditioned on the dominant origin, not a supply test on its own"},
    {"id": "EC-J", "title": "Security, Guayaquil throughput and the interdiction calendar",
     "objects": ("the 2024-01-09 internal-armed-conflict decree and the states of exception",
                 "monthly TEU throughput by terminal",
                 "the seizure announcements and the destination inspection regimes",
                 "the 2019 Posorja opening as a routing level shift"),
     "conditions": ("whether the month contained a declared state of exception over Guayas",
                    "the acute-versus-chronic split: a violence episode or an inspection regime",
                    "the harvest cycle of the three commodities that share the gate"),
     "instruments": ("UKCOCOA", "USCOCOA", "SUGAR", "USDBRL"),
     "controls": ("Colombian and Peruvian port throughput in the same months",
                  "the same months in years before the 2024 decree",
                  "a matched-month placebo that holds the harvest cycle fixed"),
     "notes": "ONE GATE, THREE COMMODITIES, so this is a JOINT test and much harder to fake than "
              "three separate weak ones. Posorja's 2019 opening is a break and not a trend"},
    {"id": "EC-K", "title": "The fuel subsidy, the price bands and the paro reaction function",
     "objects": ("the subsidy decrees and the 2021 price-band parameters",
                 "Decreto 883 of 2019 and its repeal eleven days later",
                 "the 2022 paro and its negotiated price cut",
                 "the subsidy line in the budget against the realised crude strip"),
     "conditions": ("whether a decree changed an administered price in the window",
                    "whether a paro followed within thirty days",
                    "the crude price regime, since the subsidy cost is a crude function"),
     "instruments": ("XTIUSD", "XBRUSD", "US500", "USDBRL"),
     "controls": ("Colombian and Peruvian fuel-price adjustments in the same months, neither of "
                  "which produced a comparable national strike",
                  "decrees that did NOT produce a paro, which is the placebo that separates "
                  "'the price changed' from 'the country stopped'",
                  "matched windows with an equivalent crude move and no decree"),
     "notes": "A REACTION FUNCTION WITH A HISTORY OF BEING REVERSED. The interesting object is "
              "not the decree but the CONDITIONAL PROBABILITY OF REVERSAL, which two episodes "
              "have now pinned and which a third would test out of sample"},
    {"id": "EC-L",
     "title": "The electoral and constitutional calendar: muerte cruzada and consultas",
     "objects": ("the 2023-05-17 dissolution and the snap election that followed",
                 "the 2023-08-09 assassination of a presidential candidate",
                 "the 2023-08-20 and 2024-04-21 referendum days",
                 "the decree-law window in which the executive legislated alone"),
     "conditions": ("the event class: dissolution, assassination, ballot or inauguration",
                    "whether a crude or power event fell in the same window",
                    "the sovereign-programme state at the time"),
     "instruments": ("USDBRL", "USDMXN", "US500", "XAUUSD"),
     "controls": ("Peruvian and Colombian political events in the same months, where the "
                  "currency absorbs the news",
                  "matched windows with an equivalent global risk move and no Ecuadorian event",
                  "a randomised-date null over the same calendar"),
     "notes": "THE HONEST NULL IS LIVE AND IMPORTANT: with no currency and a small bond float, "
               "Ecuadorian politics may genuinely not reach a global instrument at all -- and "
               "that finding, measured against `pe` and `co`, is worth more than a weak positive"},
    {"id": "EC-M", "title": "Industrial mining in a country that votes on it",
     "objects": ("Mirador copper concentrate shipments and Fruta del Norte gold output",
                 "the mining cadastre, its suspensions and the consultation rulings",
                 "the 2023 Choco Andino result and the district bans",
                 "the illegal-mining fronts and the gold export-minus-production gap"),
     "conditions": ("whether a consultation ruling or ballot fell in the window",
                    "whether the month fell inside a rationing episode, which cuts mine power",
                    "the Chinese smelter demand state for the concentrate",
                    "the formal-versus-informal split in the gold export line"),
     "instruments": ("XCUUSD", "XAUUSD", "USDCNH"),
     "controls": ("Peruvian and Chilean copper supply events in the same months, where the "
                  "stoppage mechanism is a road or a union rather than a court",
                  "matched windows with an equivalent Chinese demand print and no Ecuadorian "
                  "ruling",
                  "gold months with no mining-consultation event at all"),
     "notes": "THE MECHANISM IS THE CONSULTATION, NOT THE TONNES. Ecuador's mine output is small; "
              "what is genuinely different is a legal system that has halted projects by "
              "consultation ruling and an electorate that has banned mining by ballot. GOLD "
              "CELLS ARE DECLARED WEAK because the informal lane makes the export line unreliable"},
    {"id": "EC-N", "title": "The two calendars: the traslado statute and the raymi cycle",
     "objects": ("the eight fixed feriados and the three Easter-derived ones",
                 "the traslado rule of 2016 and the puentes it manufactures",
                 "the Kichwa raymi cycle and the provincial days the bourse ignores",
                 "the two decreed national non-working days of the April 2024 power emergency"),
     "conditions": ("an observed feriado against an ordinary weekday",
                    "a TRASLADADO day against a statutory one, which is the 2016 break",
                    "a SIERRA raymi against an ordinary weekday, which is about the plantation "
                    "and the road rather than the bourse"),
     "instruments": ("UKCOCOA", "SUGAR", "USDBRL", "US500"),
     "controls": ("the matched weekday 26 weeks away, the standard holiday-liquidity control",
                  "the same statutory dates in years before the 2016 traslado reform",
                  "Colombian and Peruvian holidays that do not coincide"),
     "notes": "Ecuador has NO daylight saving, so a session study here never carries a clock "
              "change -- and the traslado rule means it loses FEWER sessions to weekends than "
              "Peru does, which is a measurable difference between two neighbours' calendars"},
)

# --------------------------------------------------------------------------- miners
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    {"name": "ec_dollarisation_state", "domain_ids": ("EC-A", "EC-F"), "kind": "macro",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.ec.pack:dollarisation_state",
     "needs": ("BCE:reservas_internacionales weekly series", "SB:depositos monthly series",
               "USDBRL, USDMXN, US500 D1 bars"),
     "notes": "the conditioner this pack's macro half is built on; with no series loaded it "
              "reports UNMEASURED by name rather than inventing a bucket"},
    {"name": "ec_pipeline_outages", "domain_ids": ("EC-C", "EC-B"), "kind": "event",
     "cadence_s": 43200.0, "steerable": True, "wired": False,
     "entry": "countries.ec.pack:pipeline_outage_windows",
     "needs": ("PIPELINE_EPISODES", "the Petroecuador force-majeure notices",
               "XBRUSD, XTIUSD H1 bars"),
     "notes": "THE PACK'S PRIMARY MINER: the declared episodes with the Colombian-sabotage "
              "control and the pre-2020 window built in"},
    {"name": "ec_power_rationing", "domain_ids": ("EC-E", "EC-G", "EC-M"), "kind": "event",
     "cadence_s": 43200.0, "steerable": True, "wired": False,
     "entry": "countries.ec.pack:power_rationing_windows",
     "needs": ("RATIONING_EPISODES", "the CENACE daily schedules from the archive layer",
               "XNGUSD, XTIUSD, XCUUSD D1 bars"),
     "notes": "the hour-weighted load-loss state; the ENSO control is what separates the water "
              "from the outage and the miner names it as a required join"},
    {"name": "ec_itt_referendum", "domain_ids": ("EC-D", "EC-L"), "kind": "event",
     "cadence_s": 86400.0, "steerable": False, "wired": False,
     "entry": "countries.ec.pack:itt_referendum_windows",
     "needs": ("ITT_EVENTS", "the Block 43 production line", "XBRUSD, XTIUSD H1 bars"),
     "notes": "the ballot day and the compliance deadline are two separate candidate dates and "
              "the miner emits both rather than choosing one"},
    {"name": "ec_export_complex", "domain_ids": ("EC-G", "EC-H", "EC-I", "EC-J"),
     "kind": "transfer", "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.ec.pack:export_complex",
     "needs": ("the CNA, ACORBANEC and ANECACAO monthly series", "the APG throughput series",
               "UKCOCOA, USCOCOA, SUGAR, USDCNH D1 bars"),
     "notes": "one gate and three commodities, emitted as a JOINT claim with the shared "
              "harvest-cycle and Posorja-break controls attached"},
    {"name": "ec_sovereign_timestamps", "domain_ids": ("EC-F", "EC-L"), "kind": "event",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.ec.pack:sovereign_timestamps",
     "needs": ("SOVEREIGN_EVENTS and POLITICAL_EVENTS", "USDBRL, USDMXN, US500 H1 bars"),
     "notes": "every row PRESS_REPORTED; the honest null (a small float that global instruments "
              "never see) is the stated alternative hypothesis"},
    {"name": "ec_calendar", "domain_ids": ("EC-N",), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.ec.pack:ecuadorian_calendar",
     "needs": ("`national_holidays`, `statutory_holidays`, `moved_holidays`, `regional_days`",
               "UKCOCOA, SUGAR, USDBRL H1 bars"),
     "notes": "two calendars, one country: the traslado statute's and the sierra's"},
    {"name": "ec_transmission_seeds",
     "domain_ids": ("EC-B", "EC-C", "EC-D", "EC-E", "EC-G", "EC-H", "EC-I", "EC-J", "EC-K",
                    "EC-M"),
     "kind": "transfer", "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.ec.pack:transmission_seeds",
     "needs": ("TRANSMISSION_EDGES_SEED", "INTERACTIONS"),
     "notes": "the pack's map as HYPOTHESIS discoveries, deduplicated by the registry"},
)
MINER_DOMAINS: dict[str, tuple[str, ...]] = {
    "central_bank_surprise": (), "release_surprise": ("EC-B", "EC-G"),
    "calendar_settlement": ("EC-N", "EC-H"), "holiday_liquidity": ("EC-N",),
    "positioning": ("EC-I", "EC-H"), "carry_funding": ("EC-A", "EC-F"),
    "corporate_flow": ("EC-B", "EC-M"), "institutional_flow": ("EC-A", "EC-F"),
    "equity_mechanics": (), "derivatives_expiry": (),
    "failure": ("EC-C", "EC-E"), "residual": ("EC-A", "EC-L"),
    "transfer": ("EC-G", "EC-I", "EC-J"), "scouts": ("EC-C", "EC-K"),
    "session_microstructure": ("EC-N",),
}
# --------------------------------------------------------------------------- transmission
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    {"id": "EC-E1", "source": "A declared SOTE or OCP rupture or pre-emptive shutdown",
     "target": "XBRUSD", "targets": ("XBRUSD", "XTIUSD"), "to_country": "global", "sign": "+",
     "mechanism": "both pipelines cross ONE advancing erosion front and there is no third route "
                  "out of the Oriente; when the front cuts them the country's exportable barrels "
                  "stop at the wellhead and a force majeure is declared to cargo buyers",
     "horizon": "0 to 15 sessions", "horizon_class": "multi_day", "lag_days": 2.0,
     "actor": "EP Petroecuador and OCP Ecuador",
     "constraint": "no rail, no alternative pipeline and a refinery that cannot absorb the crude",
     "flow": "physical barrels withheld from the seaborne market on a dated schedule",
     "condition": "a declared episode (`is_pipeline_outage`) with the global supply state tight",
     "control": "Colombian pipeline sabotage windows, which are a different generating process "
                "on the same benchmark; and pre-2020 windows before the erosion front existed",
     "falsifier": "declared outage windows match a matched-weekday control on XBRUSD and XTIUSD "
                  "once OPEC+ decisions, US inventories and the dollar are conditioned on",
     "evidence": "HYPOTHESIS"},
    {"id": "EC-E2", "source": "The ITT/Yasuni referendum result and its compliance deadline",
     "target": "XBRUSD", "targets": ("XBRUSD", "XTIUSD"), "to_country": "global", "sign": "+",
     "mechanism": "a sovereign electorate voted a producing field shut on a published ballot "
                  "with a dated compliance path; the barrels are removed by law rather than by "
                  "geology, price or policy, which is a supply mechanism with no analogue",
     "horizon": "0 to 60 sessions", "horizon_class": "regime_level_shift", "lag_days": 1.0,
     "actor": "the Ecuadorian electorate and the Consejo Nacional Electoral",
     "constraint": "a constitutional result the state must implement on a phased timetable",
     "flow": "a permanent reduction in national production capacity",
     "condition": "the regime returned by `itt_regime(day)` at the ballot and at the deadline",
     "control": "the same windows in `co` and `pe`, neither of which votes on its fields; and "
                "matched windows with an equivalent OPEC+ supply decision",
     "falsifier": "nothing at the ballot and nothing at the deadline, which would mean the polls "
                  "were priced weeks earlier -- a testable alternative, not an absence",
     "evidence": "HYPOTHESIS"},
    {"id": "EC-E3", "source": "A CONAIE paro nacional that occupies the Amazonian wellheads",
     "target": "XBRUSD", "targets": ("XBRUSD", "XTIUSD", "US500"), "to_country": "global",
     "sign": "+",
     "mechanism": "an occupation stops the FIELD rather than the pipeline, so there is no "
                  "stockpile buffer and the supply effect starts immediately -- a different lag "
                  "profile from a rupture and therefore the rupture's own control",
     "horizon": "0 to 20 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "the CONAIE and the provincial federations",
     "constraint": "wells and pumping stations that are slow and expensive to restart",
     "flow": "immediate production loss plus a slow, partial restart",
     "condition": "a paro whose published convocatoria named the oil blocks, not merely the roads",
     "control": "paros that closed roads but NOT wellheads, which separates 'the country stopped' "
                "from 'the barrels stopped'; and Peruvian and Bolivian strike windows",
     "falsifier": "road-only paros and wellhead occupations produce statistically identical crude "
                  "responses, which would mean the market prices the headline and not the barrels",
     "evidence": "HYPOTHESIS"},
    {"id": "EC-E4", "source": "A published CENACE national rationing schedule",
     "target": "XTIUSD", "targets": ("XTIUSD", "XNGUSD", "XCUUSD"), "to_country": "global",
     "sign": "+",
     "mechanism": "when hydro fails the country buys liquid fuel and leases emergency thermal "
                  "generation at spot while industrial load is cut on a published timetable; the "
                  "import substitution is a real, dated demand event and the load loss a real, "
                  "dated output event",
     "horizon": "0 to 40 sessions", "horizon_class": "multi_day", "lag_days": 3.0,
     "actor": "CELEC EP, CENACE and the distributors",
     "constraint": "reservoirs with days of storage and a thermal park with a poor availability "
                   "record",
     "flow": "emergency fuel and generation procurement against lost industrial output",
     "condition": "the hour count returned by `rationing_state(day)` above its episode median",
     "control": "the same ENSO state in years with NO rationing, which separates the water from "
                "the outage; and Colombian and Peruvian hydrology in the same months",
     "falsifier": "Ecuadorian rationing windows show nothing in the energy or metals legs after "
                  "conditioning on the global cycle -- likely, and it would say the economy is "
                  "too small to register, which is a real and publishable finding",
     "evidence": "HYPOTHESIS"},
    {"id": "EC-E5", "source": "The monthly shrimp export volume to China",
     "target": "USDCNH", "targets": ("USDCNH", "CORN", "SOYBEAN"), "to_country": "cn",
     "sign": "?",
     "mechanism": "the world's largest farmed-shrimp exporter sends the majority of its volume "
                  "to one buyer, so the series is a read on CHINESE demand rather than on "
                  "Ecuadorian supply, and the feed leg runs the other way: corn and soymeal set "
                  "the farm margin and therefore the next cycle's stocking",
     "horizon": "1 to 3 months", "horizon_class": "monthly", "lag_days": 15.0,
     "actor": "the shrimp farmers and the Chinese importers",
     "constraint": "a biological growth cycle that cannot respond to price inside a quarter",
     "flow": "export volume as a demand observable and feed cost as a margin input",
     "condition": "the China-share bucket against its own trend, with the mirror print joined",
     "control": "Indian and Vietnamese export months as the competing origins; months with an "
                "equivalent Chinese import print and no Ecuadorian volume change",
     "falsifier": "Ecuadorian export volumes lead Chinese import prints by no more than the "
                  "shipping time, in which case the series carries nothing the mirror does not",
     "evidence": "HYPOTHESIS"},
    {"id": "EC-E6", "source": "The banana minimum-support-price decree and the spot-floor spread",
     "target": "SUGAR", "targets": ("SUGAR", "COFARA", "XBRUSD"), "to_country": "global",
     "sign": "?",
     "mechanism": "an administered floor on a quarter of world banana trade, set annually by "
                  "ministerial agreement; when spot trades below the decree the contract system "
                  "strains publicly, and the reefer-fuel cost on the other side moves with crude",
     "horizon": "1 to 3 months", "horizon_class": "monthly", "lag_days": 7.0,
     "actor": "the Ministry of Agriculture and the banana exporter associations",
     "constraint": "no banana contract exists anywhere, so the executable leg is a proxy",
     "flow": "an administered price and a weekly exported-box count with no direct instrument",
     "condition": "weeks in which the reported spot box price sat below the decreed floor",
     "control": "the softs complex in weeks with no Ecuadorian banana event at all, which is the "
                "expected null and the reason this edge is declared weak in the pack itself",
     "falsifier": "SUGAR and COFARA move identically with and without an Ecuadorian banana "
                  "event, which is the likely result and must be measured rather than assumed",
     "evidence": "HYPOTHESIS"},
    {"id": "EC-E7", "source": "Ecuadorian cacao export tonnage and the fino de aroma grade mix",
     "target": "UKCOCOA", "targets": ("UKCOCOA", "USCOCOA"), "to_country": "global", "sign": "-",
     "mechanism": "Ecuador's share of world cacao grew precisely as West African arrivals "
                  "collapsed, so the series is a SUBSTITUTION observable: incremental Ecuadorian "
                  "tonnes are the market's only elastic supply and the grade mix prices as a "
                  "spread against the terminal market rather than as a level",
     "horizon": "1 to 2 quarters", "horizon_class": "monthly", "lag_days": 20.0,
     "actor": "the cacao exporters and ANECACAO",
     "constraint": "a terminal market dominated by Ivorian and Ghanaian supply",
     "flow": "incremental export tonnes into a short market, split by grade",
     "condition": "main-crop arrivals months with West African arrivals below their own trend",
     "control": "Ivorian and Ghanaian arrivals in the same weeks, conditioned on FIRST; and the "
                "two cocoa contracts against each other to isolate a basis move",
     "falsifier": "Ecuadorian arrivals explain nothing in UKCOCOA once the dominant origins are "
                  "conditioned on, which is the null this edge must beat",
     "evidence": "HYPOTHESIS"},
    {"id": "EC-E8", "source": "An Ecuadorian sovereign credit or programme event",
     "target": "USDBRL", "targets": ("USDBRL", "USDMXN", "US500"), "to_country": "global",
     "sign": "+",
     "mechanism": "a default, an exchange, a debt-for-nature swap or an IMF approval reprices "
                  "the frontier-sovereign complex and, because Ecuador has no currency, the only "
                  "domestic price that can move is the bond; the spillover, if any, is into the "
                  "regional risk legs",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 0.0,
     "actor": "the Ministry of Finance, the bondholders and the IMF",
     "constraint": "a small float and an investor base that overlaps with the rest of frontier EM",
     "flow": "a repricing of frontier sovereign risk with a possible regional spillover",
     "condition": "the event class, with the oil regime at the time as the conditioner",
     "control": "Argentine and Brazilian sovereign events in the same months; matched windows "
                "with an equivalent EM risk move and no Ecuadorian event",
     "falsifier": "no measurable effect in the regional legs, which is entirely plausible for a "
                  "float this size and would be a clean negative worth recording",
     "evidence": "HYPOTHESIS"},
    {"id": "EC-E9", "source": "A Guayaquil port disruption under a state of exception",
     "target": "UKCOCOA", "targets": ("UKCOCOA", "USCOCOA", "SUGAR", "USDBRL"),
     "to_country": "global", "sign": "+",
     "mechanism": "one container gate ships the banana, the shrimp and the cacao, so a security "
                  "episode or a tightened inspection regime is a SIMULTANEOUS delay to three "
                  "export series -- which is a joint claim and much harder to fake than three "
                  "separate weak ones",
     "horizon": "0 to 30 sessions", "horizon_class": "multi_day", "lag_days": 5.0,
     "actor": "the port terminals, the exporters and the interdiction authorities",
     "constraint": "a single chokepoint with a draft constraint and a concentrated labour force",
     "flow": "delayed and inspected containers, raising lead time and cost on three commodities",
     "condition": "months with a declared state of exception over Guayas and an acute episode",
     "control": "Colombian and Peruvian port throughput in the same months; the same months in "
                "years before the 2024 decree; the Posorja 2019 break held fixed",
     "falsifier": "throughput and export lead times unchanged after major security events once "
                  "seasonality and the Posorja opening are conditioned on",
     "evidence": "HYPOTHESIS"},
    {"id": "EC-E10", "source": "A fuel-subsidy decree and the probability it is reversed",
     "target": "XTIUSD", "targets": ("XTIUSD", "XBRUSD", "US500"), "to_country": "global",
     "sign": "?",
     "mechanism": "removing the subsidy cuts domestic demand and repairs the budget, and has "
                  "twice produced a national strike that shut in production instead; the object "
                  "is the CONDITIONAL PROBABILITY OF REVERSAL, which 2019 and 2022 have pinned",
     "horizon": "0 to 30 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "the Presidencia and the CONAIE",
     "constraint": "a fiscal position that needs the cut and a street that has twice undone it",
     "flow": "an administered price change, a possible strike and a possible shut-in",
     "condition": "a decree that changed a regulated price, split by whether a paro followed",
     "control": "Colombian and Peruvian fuel adjustments in the same months, neither of which "
                "produced a comparable strike; decrees that did NOT produce a paro",
     "falsifier": "decrees with and without a following paro produce identical crude responses, "
                  "which would mean the market never priced the reversal risk at all",
     "evidence": "HYPOTHESIS"},
    {"id": "EC-E11", "source": "A deposit contraction in a system with no lender of last resort",
     "target": "US500", "targets": ("US500", "USDBRL", "XAUUSD"), "to_country": "global",
     "sign": "+",
     "mechanism": "1999 is the reference case: in a dollarised system a deposit run is a "
                  "solvency event with no monetary backstop, so stress transmits to output "
                  "immediately and there is no currency step to absorb any of it",
     "horizon": "1 to 3 months", "horizon_class": "monthly", "lag_days": 30.0,
     "actor": "the commercial banks and their depositors",
     "constraint": "no discount window, no deposit insurance of meaningful size and no capital "
                   "control to slow an outflow",
     "flow": "deposits leaving the system, credit contracting and imports compressing",
     "condition": "months with a reported deposit contraction and a falling liquidity ratio",
     "control": "the same windows in `pe` and `co`, where a central bank can and does lend; and "
                "months with an equivalent EM risk move and no Ecuadorian deposit event",
     "falsifier": "no effect in any executable leg, which is likely and would say that the "
                  "mechanism is real but domestic-only -- itself the answer to the pack's "
                  "central question about where a dollarised shock actually goes",
     "evidence": "HYPOTHESIS"},
    {"id": "EC-E12", "source": "A Chinese demand or trade-policy event under the 2024 FTA",
     "target": "USDCNH", "targets": ("USDCNH", "XCUUSD", "SOYBEAN"), "to_country": "cn",
     "sign": "?",
     "mechanism": "China is simultaneously the dominant shrimp buyer, the owner of the country's "
                  "only large copper mine, a major creditor through oil prepayments and, since "
                  "2024-05-01, an FTA partner; a Chinese decision reaches Ecuador through four "
                  "channels at once and the channels are separately dated",
     "horizon": "1 to 3 months", "horizon_class": "monthly", "lag_days": 20.0,
     "actor": "the Chinese importers, smelters and policy banks",
     "constraint": "an Ecuadorian export base concentrated in one destination",
     "flow": "demand for shrimp and concentrate, and credit under the prepayment contracts",
     "condition": "months after the FTA entered into force against comparable months before it",
     "control": "Peruvian and Chilean exports to China over the same months; Chinese import "
                "prints with no Ecuadorian event",
     "falsifier": "the FTA's entry into force produces no measurable level shift in the shrimp "
                  "or concentrate series, which would make it a diplomatic rather than an "
                  "economic event",
     "evidence": "HYPOTHESIS"},
)

#: HOW THIS COUNTRY IS TESTED AGAINST ITS NEIGHBOURS RATHER THAN IN ISOLATION. The first two rows
#: are the pack's identification strategy and they are stated, not implied: `pe` and `co` float,
#: this one does not, and everything else about the three is similar enough to make the comparison
#: mean something.
INTERACTIONS: tuple[dict[str, Any], ...] = (
    {"with": "pe",
     "mechanism": "THE DOLLARISATION CONTROL PAIR, AND THE REASON THIS PACK EXISTS. Peru floats "
                  "with one of the world's most interventionist and most TRANSPARENT central "
                  "banks -- the BCRP publishes its daily spot intervention by amount. Ecuador "
                  "has no currency and no central bank instrument at all. The two share the "
                  "Andes, the El Nino cycle, a Pacific export coast, gold and copper geology, a "
                  "Quechuan-speaking highland population and a history of presidential crises. "
                  "They differ in EXACTLY ONE INSTITUTION, which is the cleanest natural "
                  "experiment on 'what does a monetary channel actually absorb' this desk has",
     "observable": "matched shock windows -- a political crisis, an El Nino, a commodity move -- "
                   "with the Peruvian response read in the currency and the BCRP's intervention "
                   "book, and the Ecuadorian one read in output, imports, arrears and the spread",
     "targets": ("XAUUSD", "XCUUSD", "USDBRL", "US500"),
     "control": "windows with a global commodity or dollar move and no domestic event in either "
                "country, which is the third cell that separates the regime from the shock"},
    {"with": "co",
     "mechanism": "THE SECOND FLOATING CONTROL AND THE SHARED PHYSICAL BORDER. Colombia is an "
                  "oil exporter with a floating peso, an inflation-targeting central bank and "
                  "the same Putumayo coca economy on the other side of the same frontier. Its "
                  "pipeline risk is SABOTAGE and Ecuador's is GEOMORPHOLOGY -- two different "
                  "generating processes producing the same observable, which makes each the "
                  "other's control for 'does a pipeline outage move the benchmark'. Colombia is "
                  "also the interconnection Ecuador imports power from, and in 2024 could not",
     "observable": "Colombian and Ecuadorian pipeline-outage windows side by side, and the "
                   "electricity interconnection flow in the 2023-2024 drought",
     "targets": ("XBRUSD", "XTIUSD", "USDBRL", "XNGUSD"),
     "control": "windows with an OPEC+ decision and no outage in either country"},
    {"with": "cn",
     "mechanism": "CHINA REACHES ECUADOR THROUGH FOUR SEPARATELY DATED CHANNELS: it buys the "
                  "majority of the shrimp, it owns Mirador through EcuaCorriente, it built and "
                  "financed Coca Codo Sinclair, it holds oil-prepayment claims on future "
                  "barrels, and since 2024-05-01 it has an FTA. No other relationship in this "
                  "command is simultaneously demand, ownership, credit and infrastructure",
     "observable": "Chinese shrimp and concentrate import prints against the Ecuadorian export "
                   "record (the mirror comparison), and the FTA entry-into-force level shift",
     "targets": ("USDCNH", "XCUUSD", "SOYBEAN"),
     "control": "Peruvian and Chilean exports to China over the same months; Chinese import "
                "prints with no Ecuadorian supply event"},
    {"with": "br",
     "mechanism": "Brazil is the regional EM routing leg this pack's macro domains terminate in, "
                  "because Ecuador has no currency and USDBRL is the deepest liquid proxy for "
                  "LatAm risk. It is ALSO the competing origin on two of the three export "
                  "commodities -- Brazilian cacao and Brazilian soy-based feed -- so the same "
                  "symbol carries a risk channel and a substitution channel and the two must be "
                  "separated rather than pooled",
     "observable": "the Ecuadorian sovereign and political timestamps against USDBRL's own "
                   "calendar, and Brazilian cacao and soymeal against the Ecuadorian series",
     "targets": ("USDBRL", "SOYBEAN", "UKCOCOA"),
     "control": "USDMXN as the second regional leg, separating 'LatAm risk' from 'Brazil'"},
    {"with": "atlantic_energy",
     "mechanism": "ECUADOR AND VENEZUELA ARE THE TWO EX-OPEC HEAVY-SOUR EXPORTERS OF THIS "
                  "COMMAND and they compete into the same US Gulf refineries. Ecuador left OPEC "
                  "on 2020-01-01 and Venezuela's output collapsed under sanction; Guyana's ramp "
                  "then added light sweet supply to the same Atlantic basin. When Merey returns "
                  "or Stabroek adds a vessel, Oriente's differential is where it shows up, and "
                  "the `atlantic_energy` pack owns both of those dated timetables",
     "observable": "Ecuadorian export volumes and grade differentials against Venezuelan liftings "
                   "and the Guyanese FPSO start dates, into the same PADD 3 demand",
     "targets": ("XBRUSD", "XTIUSD", "US500"),
     "control": "Canadian heavy arrivals into PADD 3 over the same months, the third competing "
                "heavy barrel, which separates 'Latin heavy' from 'heavy'"},
)

# --------------------------------------------------------------------------- eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    {"name": "the sucre's last years, the banking collapse and the Brady default",
     "start": "1998-01-01", "end": "2000-01-08",
     "regime": "a floating and then collapsing sucre, a systemic banking crisis, the feriado "
               "bancario of March 1999 with deposits frozen, and the first sovereign default on "
               "Brady bonds in September 1999",
     "markers": ("1999-03-08 the feriado bancario freezes deposits",
                 "1999-09-28 default on the Brady bonds",
                 "1999 El Nino compounds the collapse"),
     "why_it_matters": "THE REFERENCE CASE FOR EVERY STRESS CELL IN THIS PACK. It is also a "
                       "different country statistically: there was a currency, so no series "
                       "spanning this boundary measures one regime",
     "status": "SETTLED"},
    {"name": "dollarisation adopted and consolidated",
     "start": "2000-01-09", "end": "2006-12-31",
     "regime": "the dollar is adopted at 25,000 sucres, the sucre is withdrawn during 2000, the "
               "BCE loses its instruments, and the OCP pipeline is built to carry heavy crude "
               "the SOTE could not",
     "markers": ("2000-01-09 dollarisation announced", "2000-09-11 the sucre ceases to circulate",
                 "2003-09 OCP begins operations"),
     "why_it_matters": "the monetary regime break that defines the pack; no monetary study may "
                       "pool across 2000-01-09 and every one of this pack's series starts after",
     "status": "SETTLED"},
    {"name": "the Correa decade: default by choice, Chinese credit and state-led investment",
     "start": "2007-01-15", "end": "2017-05-23",
     "regime": "a debt audit declares the Global bonds illegitimate and the state defaults BY "
               "CHOICE in December 2008 and buys the paper back at roughly a third of face; "
               "Chinese policy banks replace the market with oil-prepayment contracts; Coca Codo "
               "Sinclair and the hydro programme are contracted; the 2013 decision to drill the "
               "ITT reverses the Yasuni trust initiative",
     "markers": ("2008-12-12 default on the 2012 and 2030 Globals",
                 "2009-06 buyback at about a third of face",
                 "2013-08-15 the Yasuni-ITT initiative abandoned and drilling authorised",
                 "2016-09 first ITT production"),
     "why_it_matters": "a sovereign that defaults when it CAN pay has a different reaction "
                       "function from one that defaults when it cannot, and the Chinese "
                       "prepayment contracts mean a share of future barrels is already sold",
     "status": "SETTLED"},
    {"name": "the Moreno adjustment: the IMF, Decreto 883, the waterfall and the restructuring",
     "start": "2017-05-24", "end": "2021-05-23",
     "regime": "an IMF programme, an attempt to remove the fuel subsidy that was reversed in "
               "eleven days, EXIT FROM OPEC on 2020-01-01, the San Rafael waterfall collapse in "
               "February 2020 that began the regressive erosion, the COVID shock and the "
               "restructuring of about US$17.4bn of Global bonds completed in August 2020",
     "markers": ("2019-10-01 Decreto 883 and the paro that repealed it on 2019-10-13",
                 "2020-01-01 Ecuador leaves OPEC",
                 "2020-02-02 the San Rafael waterfall collapses",
                 "2020-04-07 both pipelines rupture",
                 "2020-08-31 the Global bond restructuring completes"),
     "why_it_matters": "THREE REGIME BREAKS IN ONE ERA: the OPEC reporting break, the start of "
                       "the erosion front, and a new bond stack. A study pooling across any of "
                       "the three is measuring two different objects",
     "status": "SETTLED"},
    {"name": "the Lasso years: price bands, the 2022 paro and the muerte cruzada",
     "start": "2021-05-24", "end": "2023-11-22",
     "regime": "the Ley de Defensa de la Dolarizacion reforms the BCE and bars Treasury "
               "financing; fuel prices move to published bands; the June 2022 paro shuts in two "
               "thirds of production; the erosion cuts the pipelines twice more; the president "
               "dissolves the Assembly by muerte cruzada in May 2023; the ITT referendum is held "
               "on 2023-08-20 and the first national power rationing follows in October",
     "markers": ("2022-01-28 the SOTE ruptures at Piedra Fina",
                 "2022-06-13 the CONAIE paro begins",
                 "2023-05-09 the Galapagos debt-for-nature swap",
                 "2023-05-17 muerte cruzada", "2023-08-20 the ITT referendum",
                 "2023-10-27 the first national rationing round"),
     "why_it_matters": "the richest event sample in the pack and the era in which four of its "
                       "mechanisms first appear together; each must be conditioned on the others",
     "status": "SETTLED"},
    {"name": "the Noboa emergency: internal armed conflict, the blackouts and the new programme",
     "start": "2023-11-23", "end": "2025-05-23",
     "regime": "an internal armed conflict declared by decree in January 2024 with the armed "
                "forces deployed to the ports; the April and the September-to-December 2024 "
                "rationing rounds with cuts of up to fourteen hours; the China FTA in force from "
                "2024-05-01; a new IMF EFF approved 2024-05-31; the ITT compliance deadline on "
                "2024-08-31; a second debt-for-nature transaction in December 2024",
     "markers": ("2024-01-09 internal armed conflict declared",
                 "2024-04-18 two national non-working days decreed to save power",
                 "2024-05-01 the China FTA enters into force",
                 "2024-05-31 the IMF approves the EFF",
                 "2024-08-31 the ITT compliance deadline",
                 "2024-09-23 the long rationing round begins"),
     "why_it_matters": "FIVE OF THIS PACK'S MECHANISMS FIRE INSIDE ONE ERA, which is a gift for "
                       "sample size and a trap for identification: nothing here may be tested "
                       "without conditioning on the others",
     "status": "SETTLED"},
    {"name": "the second Noboa term: the current regime",
     "start": "2025-05-24", "end": "2026-12-31",
     "regime": "a full four-year term with an IMF programme in place, the ITT shutdown path in "
               "litigation and implementation, a security emergency that has become structural, "
               "and a grid that has added thermal and solar capacity against the next drought",
     "markers": ("2025-05-24 inauguration for a full term",
                 "the EFF review calendar as the scheduled-event clock",
                 "the erosion front's continued advance toward the pipeline intakes"),
     "why_it_matters": "the current regime and the one every live cell is compiled in; the ITT "
                       "implementation path and the next hydrological year are its open "
                       "questions and both are dated",
     "status": "OPEN"},
)

ACCESS_CONSTRAINTS: tuple[dict[str, Any], ...] = (
    {"constraint": "there is no Ecuadorian currency, so there is no currency cell",
     "measured": "the country adopted the USD on 2000-01-09; data/universe/universe.json holds "
                 "no Ecuadorian symbol and could not",
     "consequence": "every macro domain terminates in the regional risk legs, the commodities "
                    "the country ships or US500. USDBRL and USDMXN are REGIONAL RISK legs here "
                    "and are NEVER read as proxies for an Ecuadorian exchange rate"},
    {"constraint": "there is no policy rate and therefore no policy-surprise object",
     "measured": "CENTRAL_BANK.decision_dates is EMPTY and dates_status says why",
     "consequence": "this pack mints NO central-bank-surprise cells at all and "
                    "MINER_DOMAINS['central_bank_surprise'] is deliberately empty; an FOMC day "
                    "is never labelled an Ecuadorian policy day"},
    {"constraint": "the pipeline, rationing, political and sovereign dates are PRESS_REPORTED",
     "measured": "every PIPELINE_EPISODES, RATIONING_EPISODES, POLITICAL_EVENTS and "
                 "SOVEREIGN_EVENTS row carries that label and no Registro Oficial citation",
     "consequence": "EC-C, EC-E, EC-F and EC-L may generate hypotheses and may not promote any "
                    "cell until a registroficial.gob.ec decree number or an operator comunicado "
                    "is attached to the exact date the cell was compiled on"},
    {"constraint": "the CENACE rationing tables are replaced every day and archived nowhere",
     "measured": "the operator publishes the next day's schedule over the previous one",
     "consequence": "the hour-weighted load-loss series exists only in the archive layer's "
                    "crawls; an un-crawled day is UNMEASURED and the episode's headline maximum "
                    "is used instead, which is a coarser variable and is labelled as one"},
    {"constraint": "the ministries overwrite their statistics pages in place",
     "measured": "recursosyenergia.gob.ec, apg.gob.ec and the BCE weekly tables all publish the "
                 "current file over the same link and keep no vintage",
     "consequence": "EC-B's and EC-J's point-in-time history exists only in the archive layer's "
                    "crawls; a cell compiled on an un-archived month is UNMEASURED, not assumed"},
    {"constraint": "the shrimp FOB, the crude differential and the fino de aroma premium are "
                   "private assessments whose terms forbid machine extraction",
     "measured": "the price reporting agencies' terms; the sector trade press is registered "
                 "machine_use_allowed=false for the same reason",
     "consequence": "the shrimp price leg, the Oriente differential and the cacao quality premium "
                    "are all UNMEASURED. EC-G is tested on VOLUME and the feed leg, EC-B on the "
                    "benchmark, and EC-I on the grade MIX -- and the absence is named each time"},
    {"constraint": "the customs VALUE series is a price series in disguise",
     "measured": "commodity exports are declared at contract prices that move with the market",
     "consequence": "every physical claim in this pack uses VOLUME; a study built on declared "
                    "value is measuring the commodity price twice and calling one of them supply"},
    {"constraint": "informal gold output is unmeasured by construction",
     "measured": "the gold export line exceeds counted formal mine production and the illegal "
                 "fronts are policed rather than counted",
     "consequence": "XAUUSD cells from EC-M are declared WEAK; the export-minus-production gap "
                    "is carried as a measurement warning and never as a supply signal"},
    {"constraint": "there is no domestic speculative retail ecology to read",
     "measured": "LAYER_ABSENCES declares `retail_ecology` absent with the reason",
     "consequence": "no positioning or sentiment cell may be compiled from a domestic retail "
                    "source, and the lawful substitutes -- remittances by province and deposits "
                    "by size -- are used as HOUSEHOLD state variables rather than as positioning"},
)
INSTITUTIONAL_FLOW_SOURCES: tuple[str, ...] = (
    "BCE weekly international reserves and the four-system balance sheet",
    "Superintendencia de Bancos monthly deposits, liquidity and delinquency",
    "MEF public debt stock, arrears and the budget's oil-price assumption",
    "SENAE customs export volumes by tariff heading and destination",
    "Autoridad Portuaria de Guayaquil and terminal container throughput",
    "BCE quarterly remittances by province and sending country")
SERIES: dict[str, str] = {
    "EC_RESERVES": "BCE:reservas_internacionales", "EC_DEPOSITS": "SB:depositos_del_sistema",
    "EC_LIQUIDITY": "SB:liquidez_estructural", "EC_CPI": "INEC:ipc",
    "EC_REMITTANCES": "BCE:remesas_por_provincia", "EC_DEBT": "MEF:deuda_publica",
    "EC_ARREARS": "MEF:atrasos", "EC_OIL_PRODUCTION": "MEM:produccion_por_campo",
    "EC_OIL_EXPORTS": "PETRO:exportacion_de_crudo", "EC_ITT": "MEM:produccion_bloque_43",
    "EC_POWER_DEMAND": "CENACE:demanda_nacional", "EC_RATIONING": "CENACE:horarios_de_corte",
    "EC_RESERVOIR": "CENACE:cota_mazar", "EC_SHRIMP": "CNA:exportaciones_camaron",
    "EC_BANANA": "ACORBANEC:cajas_exportadas", "EC_BANANA_FLOOR": "MAG:precio_minimo_sustentacion",
    "EC_CACAO": "ANECACAO:exportaciones_por_grado", "EC_PORT": "APG:contenedores_teu",
    "EC_ENSO": "NOAA:enso_advisory", "EC_FUEL_BAND": "RO:banda_de_precios_combustibles",
}

# --------------------------------------------------------------------------- the cells
#: WHAT EACH DOMAIN MINTS: its mechanism family, its horizon class, and the one-line control every
#: cell from it inherits. `cells()` is the cross product of a domain's INSTRUMENTS and its
#: CONDITIONS -- both of which are real, named, evaluable states of this pack's own data plane. It
#: is not a cartesian blow-up: a condition that cannot be evaluated from a declared dataset does
#: not appear in a domain's `conditions` tuple in the first place.
DOMAIN_CELL_SPEC: dict[str, tuple[str, str, str]] = {
    "EC-A": ("dollarisation_state", "1m_to_3m",
             "the same windows in floating Peru and Colombia, and a block-shuffled deposit null"),
    "EC-B": ("physical_supply", "1m_to_3m",
             "Colombian production in the same months and OPEC+-matched windows"),
    "EC-C": ("supply_disruption", "0d_to_15d",
             "Colombian sabotage windows and pre-2020 months before the erosion front"),
    "EC-D": ("referendum_supply", "regime_level_shift",
             "neighbours that never vote on a field, and OPEC+-matched supply windows"),
    "EC-E": ("output_shock", "0d_to_40d",
             "the same ENSO state in non-rationing years and the Andean hydrology peers"),
    "EC-F": ("sovereign_risk", "0d_to_10d",
             "Argentine and Brazilian sovereign events and EM-risk-matched windows"),
    "EC-G": ("export_demand", "1m_to_3m",
             "Indian and Vietnamese origins and China-print-matched months"),
    "EC-H": ("administered_price", "1m_to_3m",
             "the softs complex in weeks with no Ecuadorian banana event"),
    "EC-I": ("substitution", "1q_to_2q",
             "Ivorian and Ghanaian arrivals conditioned on first, and the cocoa basis"),
    "EC-J": ("logistics_regime", "0d_to_30d",
             "Andean port peers, pre-2024 months and the Posorja break held fixed"),
    "EC-K": ("administered_price", "0d_to_30d",
             "neighbours' fuel adjustments and decrees that produced no paro"),
    "EC-L": ("political_event", "intraday_to_5d",
             "Peruvian and Colombian political events and matched risk days"),
    "EC-M": ("consultation_risk", "1m_to_1q",
             "Andean supply peers whose stoppage mechanism is a road or a union"),
    "EC-N": ("holiday_liquidity", "0d_to_3d",
             "the matched weekday 26 weeks away and pre-2016 statutory dates"),
}


def cells() -> tuple[dict[str, Any], ...]:
    """Every testable cell this pack mints: domain x executable instrument x named condition.

    A cell is a triple the gauntlet can actually evaluate -- an instrument the broker quotes, a
    condition this pack's own declared datasets can compute, and a control that is not the
    instrument's own history. The cross product is taken over the domain's OWN instrument tuple
    rather than over the whole executable list, which is what keeps the count honest: EC-I never
    mints a crude cell and EC-C never mints a cocoa one.
    """
    out: list[dict[str, Any]] = []
    for dom in DOMAINS:
        did = str(dom["id"])
        family, horizon, control = DOMAIN_CELL_SPEC.get(did, ("residual", "1d_to_5d",
                                                              "a matched-weekday placebo"))
        for symbol in dom["instruments"]:
            for i, condition in enumerate(dom["conditions"]):
                out.append({
                    "cell_id": f"{CODE}:{did}:{symbol}:c{i + 1}",
                    "domain": did, "symbol": str(symbol), "condition": str(condition),
                    "mechanism_family": family, "horizon": horizon, "control": control,
                    "why": f"{dom['title']} -- conditioned on {condition}",
                })
    return tuple(out)


CELLS: tuple[dict[str, Any], ...] = cells()


def cells_by_symbol() -> dict[str, int]:
    """How many cells each executable instrument carries. A symbol with none is an instrument the
    pack declared and never used, which is a defect the tests catch."""
    out: dict[str, int] = dict.fromkeys(EXECUTABLE_INSTRUMENTS, 0)
    for row in CELLS:
        out[str(row["symbol"])] = out.get(str(row["symbol"]), 0) + 1
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


def dollarisation_state(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """EC-A: the dollarisation conditioner. The reserve and deposit series are collector inputs,
    so with no loader this miner reports UNMEASURED by name rather than inventing a bucket."""
    n = _emit(ctx, "dollarisation_state",
              payload={"domain": "EC-A", "reserves": SERIES["EC_RESERVES"],
                       "deposits": SERIES["EC_DEPOSITS"], "currency": CURRENCY,
                       "no_policy_rate": True})
    return {"miner": "dollarisation_state", "domain": "EC-A", "emitted": n,
            "unmeasured": ["EC-A/BCE:reservas_internacionales: the weekly reserve series is not "
                           "loaded on this box; the cover state cannot be bucketed",
                           "EC-A/no_policy_rate: there is no rate to be surprised by, so no "
                           "policy-surprise cell exists here by construction"]}


def pipeline_outage_windows(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """EC-C: the pack's primary miner. The declared crude-interruption episodes, their lengths
    and their causes, every one PRESS_REPORTED and therefore hypothesis-grade."""
    episodes = pipeline_episodes()
    total_days = sum((hi - lo).days + 1 for lo, hi, _s, _w in episodes)
    n = 0
    for lo, hi, site, what in episodes:
        n += _emit(ctx, "supply_disruption",
                   payload={"domain": "EC-C", "start": lo.isoformat(), "end": hi.isoformat(),
                            "site": site, "what": what, "status": "PRESS_REPORTED",
                            "targets": ("XBRUSD", "XTIUSD")})
    return {"miner": "pipeline_outage_windows", "domain": "EC-C", "episodes": len(episodes),
            "disrupted_days": total_days, "emitted": n,
            "unmeasured": ["EC-C/registro_oficial_citation: no episode carries a gazette or "
                           "operator citation yet, so none may be promoted"]}


def power_rationing_windows(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """EC-E: the published rationing episodes and their headline maximum outage hours. The
    day-level distributor schedules are an archive-layer input and are named as missing."""
    n = 0
    for lo, hi, hours, what, _st in RATIONING_EPISODES:
        n += _emit(ctx, "output_shock",
                   payload={"domain": "EC-E", "start": lo.isoformat(), "end": hi.isoformat(),
                            "max_hours": hours, "what": what,
                            "targets": ("XTIUSD", "XNGUSD", "XCUUSD")})
    return {"miner": "power_rationing_windows", "domain": "EC-E",
            "episodes": len(RATIONING_EPISODES), "days_2024": rationing_days(2024), "emitted": n,
            "unmeasured": ["EC-E/CENACE:horarios_de_corte: the daily province-level schedules "
                           "are overwritten in place and exist only in archive crawls; the "
                           "hour-weighted series is UNMEASURED and the episode maximum is a "
                           "coarser substitute",
                           "EC-E/NOAA:enso_advisory: the ENSO control is not loaded, and without "
                           "it the water and the outage cannot be told apart"]}


def itt_referendum_windows(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """EC-D: the ITT record. The ballot day and the compliance deadline are TWO candidate event
    dates and this miner emits both rather than choosing one for the gauntlet."""
    n = 0
    for day, what, status in ITT_EVENTS:
        n += _emit(ctx, "referendum_supply",
                   payload={"domain": "EC-D", "date": day.isoformat(), "what": what,
                            "status": status, "regime": itt_regime(day),
                            "targets": ("XBRUSD", "XTIUSD")})
    return {"miner": "itt_referendum_windows", "domain": "EC-D", "events": len(ITT_EVENTS),
            "regime_today": itt_regime(datetime.now(tz=UTC).date()), "emitted": n,
            "unmeasured": ["EC-D/MEM:produccion_bloque_43: the Block 43 production line is not "
                           "loaded, so the size of the shut-in is a published claim rather than "
                           "a counted one"]}


def export_complex(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """EC-G, EC-H, EC-I and EC-J: one gate and three commodities, emitted as a JOINT claim with
    the shared harvest-cycle and Posorja-break controls attached to every row."""
    rows = (("EC-G", "shrimp export volume by destination", ("USDCNH", "CORN", "SOYBEAN")),
            ("EC-H", "banana boxes against the decreed minimum price", ("SUGAR", "COFARA")),
            ("EC-I", "cacao tonnage by grade against West African arrivals",
             ("UKCOCOA", "USCOCOA")),
            ("EC-J", "Guayaquil container throughput under a state of exception",
             ("UKCOCOA", "USCOCOA", "SUGAR")))
    n = 0
    for domain, what, targets in rows:
        n += _emit(ctx, "transfer",
                   payload={"domain": domain, "what": what, "targets": targets,
                            "shared_gate": "Guayaquil and Posorja",
                            "control": "the harvest cycle held fixed and the 2019 Posorja break"})
    return {"miner": "export_complex", "domains": [r[0] for r in rows], "claims": len(rows),
            "emitted": n,
            "unmeasured": ["EC-G/shrimp_fob: the price leg is a private assessment whose terms "
                           "forbid machine extraction, so the claim is made on VOLUME",
                           "EC-H/banana_spot_price: no banana contract exists anywhere and the "
                           "spot box price is a reported figure, so EC-H is declared WEAK"]}


def sovereign_timestamps(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """EC-F and EC-L: the dated sovereign and political event series, with the honest null stated
    on every row -- a float this size may simply never reach a global instrument."""
    n = 0
    for day, what, status in SOVEREIGN_EVENTS + POLITICAL_EVENTS:
        n += _emit(ctx, "political_event",
                   payload={"domain": "EC-F", "date": day.isoformat(), "what": what,
                            "status": status,
                            "null": "with no currency and a small bond float, no effect in the "
                                    "executable legs is a genuinely likely outcome and is the "
                                    "measurement this pack is most interested in"})
    return {"miner": "sovereign_timestamps", "domain": "EC-F",
            "events": len(SOVEREIGN_EVENTS) + len(POLITICAL_EVENTS), "emitted": n,
            "unmeasured": ["EC-F/sovereign_spread: the Ecuadorian spread is absent from this "
                           "broker and is a collector input; without it the domain conditions "
                           "the regional legs and mints no direct cell"]}


def ecuadorian_calendar(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """EC-N: the two calendars -- the traslado statute's observed table and the sierra's raymi
    cycle, which is the calendar the plantations and the highland roads actually run on."""
    year = datetime.now(tz=UTC).year
    national = national_holidays(year)
    regional = regional_days(year)
    moved = moved_holidays(year)
    n = _emit(ctx, "holiday_liquidity",
              payload={"domain": "EC-N", "year": year, "national": len(national),
                       "regional": len(regional),
                       "moved": [f"{s.isoformat()}->{o.isoformat()}" for s, o, _n in moved]})
    return {"miner": "ecuadorian_calendar", "domain": "EC-N", "national": len(national),
            "regional": len(regional), "moved": len(moved), "emitted": n, "unmeasured": []}


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
    "dollarisation_state": dollarisation_state,
    "pipeline_outage_windows": pipeline_outage_windows,
    "power_rationing_windows": power_rationing_windows,
    "itt_referendum_windows": itt_referendum_windows,
    "export_complex": export_complex,
    "sovereign_timestamps": sovereign_timestamps,
    "ecuadorian_calendar": ecuadorian_calendar,
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
        "mission": MISSION, "jurisdictions": JURISDICTIONS, "interactions": INTERACTIONS,
        "query_territories": QUERY_TERRITORIES, "cells": CELLS,
        "pipeline_episodes": PIPELINE_EPISODES, "rationing_episodes": RATIONING_EPISODES,
        "itt_events": ITT_EVENTS, "sovereign_events": SOVEREIGN_EVENTS,
        "political_events": POLITICAL_EVENTS,
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
    """The framework's HolidayRule shape: every closed date the rule produces for 2024-2026."""
    dates = sorted({d.isoformat() for y in HOLIDAYS_RULE["years"] for d in market_holidays(y)})
    return {"dates": tuple(dates),
            "fixed_md": tuple(f"{m:02d}-{d:02d}" for m, d, _n, _mv in FIXED_NATIONAL),
            "weekly_closed": (5, 6), "notes": HOLIDAYS_RULE["authority"]}


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
