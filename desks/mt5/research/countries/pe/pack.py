"""PERU: the world's second copper and second silver mine, read through its CONFLICT CALENDAR.

WHY PERU IS A PACK OF ITS OWN AND NOT A PARAGRAPH IN THE CHILE PACK. `countries/cl` is written
as "Chile (with Peru)" and treats the two as one Andean supply state against one Chinese demand
state. That framing is right about copper and wrong about everything else, and it leaves the
single best supply series in this desk's book unmined. Chile's supply risk is a LABOUR
NEGOTIATION on a published four-year contract cycle. Peru's supply risk is a ROAD, and the road
is watched, counted and published monthly by an ombudsman with a statutory mandate. Those are
different objects, they are dated by different institutions, and each is the other's negative
control -- which is the whole reason this pack exists next to `cl` instead of inside it.

SIX THINGS THAT BELONG TO THIS ECONOMY AND TO NO OTHER IN THE DESK'S BOOK:

  1. NEARLY EVERY DOMAIN LANDS ON A METAL THE BROKER QUOTES. Peru is the world's #2 copper
     producer (~2.6 Mt/yr), #2 silver, a top-10 gold producer, the largest ZINC producer in the
     Americas and a top-3 LEAD producer -- and XCUUSD, XAGUSD, XAUUSD, XZNUSD and XPBUSD are all
     in `data/universe/universe.json`. There is no other country on this desk where the physical
     production series and the tradable instrument line up five metals deep. That is why this
     pack's cell count is high: it is not a cartesian trick, it is the geology.

  2. THE MINISTRY PUBLISHES PRODUCTION BY MINE AND BY METAL, MONTHLY. The MINEM Boletin
     Estadistico Minero is a counted physical supply series at UNIT granularity -- Antamina's
     zinc, Cerro Verde's copper, Las Bambas' copper, Uchucchacua's silver -- against a liquid
     metal. Most countries publish a national total and call it a statistic. Peru publishes the
     mine.

  3. SOCIAL CONFLICT IS A PUBLISHED, DATED SUPPLY SERIES. The Defensoria del Pueblo publishes a
     MONTHLY Reporte de Conflictos Sociales naming every active socio-environmental conflict by
     province, by case, by state (dialogue / escalation / violence). Las Bambas alone is about 2%
     of world copper supply and its road -- the Corredor Vial Minero del Sur -- has been blocked
     for weeks at a time with dated starts and dated ends. A physical supply interruption of a
     liquid metal, announced by an ombudsman, in Spanish, Quechua and Aymara, that essentially no
     systematic desk reads. THIS IS THE SINGLE BEST REASON THIS PACK EXISTS.

  4. THE CENTRAL BANK PUBLISHES ITS OWN INTERVENTION. The BCRP is among the most interventionist
     FX authorities in the world and it is TRANSPARENT about it: daily spot purchases and sales,
     the Certificado de Deposito Reajustable (CDR) book and the swap cambiario book are all
     published. The sol is consequently the least volatile major EM currency in the region
     despite the region's most volatile politics. Sol volatility is therefore a POLICY variable,
     which makes Peru the cleanest available control for "does political risk move a currency".

  5. THE POLITICS ARE A DATED EVENT SERIES, NOT A MOOD. Six presidents since 2016, a dissolved
     Congress (2019-09-30), three vacancia votes, and a self-coup attempt at 11:40 Lima on
     2022-12-07 followed by an arrest the same afternoon. Every one of those is a timestamp, and
     the metal, the sol and the sovereign curve reacted inside the hour.

  6. THE ANCHOVETA IS A REAL CROSS-COMMODITY INPUT. Peru lands the world's largest single-species
     fishery and is the world's largest fishmeal exporter. Fishmeal and SOYBEAN meal are
     substitutes in the aquaculture and hog rations, IMARPE sets the biomass estimate and PRODUCE
     sets the quota by resolucion ministerial, and PRODUCE has CANCELLED a season outright (the
     first season of 2023). A cancelled season is a dated protein-supply shock with a soymeal
     substitution on the other side of it.

WHAT IS EXECUTABLE AND WHAT IS NOT. The SOL IS ABSENT from this broker: USDPEN, the BCRP's CDR
and swap books, the S&P/BVL Peru General index, the soberanos curve and the LME cash contracts
are every one of them named in `TRANSMISSION_TARGETS` with the broker symbols that carry their
economics. USDCLP is absent too, which matters here: the obvious "Chile versus Peru" control
trade cannot be executed as a currency pair and must be run on the metals.

THE `cl` PACK IS THIS PACK'S NEAREST NEIGHBOUR AND ITS SHARPEST CONTROL. Chile is #1 in copper
and Peru is #2/#3; together they are the marginal supplier. `INTERACTIONS` names the `cl` edge
FIRST and explicitly: a copper move with a Peruvian blockade and no Chilean event is Peruvian
supply, a copper move with both is Andean supply, and a copper move with neither is Chinese
demand. `cl` owns the AFP multifondo switch and the pre-announced BCCh intervention programme;
this pack owns the conflict calendar and the CDR/swap book. Neither duplicates the other.

THE TWO-LANE ORDER (2026-09-06). Southern Copper, Buenaventura, Credicorp, Intercorp, Volcan,
Nexa, Exalmar and TASA are all tempting and all forbidden as statistical hypotheses. They appear
here as ACTORS whose production, concentrate shipments and quota take move the metals, the
softs and the EM legs. No share CFD appears in any instrument tuple in this file.

NATIVE GROUND. Spanish is the working language; QUECHUA and AYMARA are OFFICIAL languages under
article 48 of the 1993 constitution wherever they predominate, and the conflict ground -- the
community assemblies, the prior-consultation (consulta previa) record under Ley 29785, the
Servindi indigenous-affairs wire -- is written and spoken in them. An English- or Spanish-only
crawl of Peru reads the Lima corner of the country and misses the actual source of the supply
shocks, which happen 4,000 metres up the Corredor Minero.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Any

# --------------------------------------------------------------------------- identity
CODE = "pe"
NAME = "Peru"
REGION_COMMAND = "latam"
REGION_DESK = "SOUTH_AMERICA"
FOREST = "latam"
CURRENCY = "PEN"
#: THE PARITY FENCE COUNTS THIS (`scripts/check_regional_parity.py::jurisdictions_of`). Peru is
#: one of the 26 countries on the desk's own forest roster that no pack answered for: `cl` is
#: titled "Chile (with Peru)" and declares no JURISDICTIONS, so it is credited with `cl` alone.
JURISDICTIONS: tuple[str, ...] = ("pe",)
FISCAL_YEAR_END = "12-31"          # the Ley de Presupuesto runs on the calendar year
NATIVE_LANGUAGES: tuple[str, ...] = ("es", "qu", "ay", "en")
COT_CURRENCY = ""                  # no CFTC contract exists for the sol
EXPORT_ECONOMY = "metals_exporter"
RETAIL_LEVERAGE_REGIME = "open"    # no exchange control; residents may hold FX and offshore
#: The depth this pack CLAIMS, so a test can check the framework's own measurement against it
#: rather than against a number typed into a report. `regional_parity.pack_depth` computes the
#: real one from the eight capped ratios; this is the floor the pack promises not to fall below.
DECLARED_DEPTH: float = 1.0
MISSION = ("mine Peru as the mine-by-mine, conflict-dated, intervention-transparent metals "
           "economy it is: the MINEM Boletin Estadistico Minero at unit granularity, the "
           "Defensoria del Pueblo's monthly conflict report as a physical copper-supply series, "
           "the Corredor Vial Minero del Sur blockades with their dated starts and ends, the "
           "BCRP's published spot intervention and its CDR and swap cambiario books, the "
           "vacancia and self-coup timestamps, the IMARPE anchoveta quota and its cancelled "
           "seasons against soymeal, and the Callao-Matarani-Chancay port plane")

#: The instruments this pack may compile a cell against. Every one is in the broker registry and
#: none is a single-name equity. The SOL ITSELF IS ABSENT (see TRANSMISSION_TARGETS).
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "XCUUSD",                          # #2 producer; Las Bambas alone is ~2% of world supply
    "XAGUSD",                          # #2 silver producer; mostly a by-product of the polymetals
    "XAUUSD",                          # top-10 gold producer, plus the informal Madre de Dios lane
    "XZNUSD",                          # the largest zinc producer in the Americas (Antamina)
    "XPBUSD",                          # top-3 lead producer, co-produced with the zinc and silver
    "XNIUSD",                          # not mined here: the base-metal complex control leg
    "SOYBEAN",                         # the fishmeal-to-soymeal substitution in the feed ration
    "CORN",                            # the other half of the feed ration and the import bill
    "COFARA",                          # a top-10 arabica origin and the largest organic exporter
    "XTIUSD",                          # the diesel that runs the mine fleet and the FEPC fund
    "USDCNH",                          # China takes over half of Peru's mineral exports
    "USDBRL",                          # the regional EM beta and the sol's nearest liquid proxy
    "USDMXN",                          # the deepest LatAm EM leg; the risk-on/risk-off control
    "US500",                           # the global risk state every Andean cell conditions on
)

#: WHAT PERU TRADES THAT THIS BROKER DOES NOT QUOTE. Each row names the absent instrument, the
#: venue it lives on, WHY the pack needs it, and the broker symbols that carry its economics.
#: An absent instrument produces a transmission hypothesis and never a cell that can never be
#: filled (L1.49).
TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "USD/PEN (the sol), the BCRP's interbank reference and the tipo de cambio SBS",
     "venue": "the Lima interbank market; Datatec; the SBS publishes the daily reference",
     "why": "PEN IS ABSENT from the broker registry and it is the variable half of this pack's "
            "macro domains; its realised volatility is a POLICY output (the CDR and swap books) "
            "rather than a market one, which is exactly what makes it a control",
     "regime": "managed float with heavy, published, discretionary spot intervention plus a "
               "derivatives leg (CDR and swap cambiario) used to absorb hedging demand without "
               "spending reserves; no band, no announced programme, no pre-commitment",
     "route": "the EM beta legs carry the risk state and the metals carry the terms of trade; "
              "a PEN-specific residual is UNMEASURED here by construction and says so",
     "proxies": ("USDBRL", "USDMXN", "XCUUSD", "US500")},
    {"name": "The BCRP CDR (Certificado de Deposito Reajustable) and swap cambiario books",
     "venue": "BCRP auctions, published daily",
     "why": "the instrument the BCRP uses INSTEAD of spot when it wants to absorb hedging "
            "demand; the outstanding balance is the cleanest published measure of how hard the "
            "sol is being held, and it has no analogue in the Chilean or Brazilian pack",
     "regime": "auctioned on demand; balances published daily in the BCRP's nota semanal",
     "route": "a state variable that CONDITIONS the EM legs and the metals, never a target",
     "proxies": ("USDBRL", "USDMXN")},
    {"name": "USD/CLP (the Chilean peso) -- the obvious control leg, also absent",
     "venue": "the Santiago interbank market",
     "why": "the natural 'Chile versus Peru' control is a currency pair this broker does not "
            "quote, so the Andean supply control MUST be run on the metals themselves; naming "
            "the absence is what stops a study from quietly substituting a different control",
     "regime": "free float with pre-announced intervention programmes (see the `cl` pack)",
     "route": "run the control on XCUUSD conditioned on the two countries' event calendars",
     "proxies": ("XCUUSD", "USDBRL")},
    {"name": "S&P/BVL Peru General and Peru Select (the Lima bourse indices)",
     "venue": "Bolsa de Valores de Lima",
     "why": "no CFD is quoted; the index is ~60% mining by weight, so it is a levered read on "
            "the same metals this pack already trades directly and adds no independent cell",
     "regime": "MSCI Emerging Markets, retained after the 2015-2016 frontier review; a "
               "reclassification is a dated forced-flow event",
     "route": "the metals carry the mining weight; US500 carries the global risk state",
     "proxies": ("XCUUSD", "XZNUSD", "US500")},
    {"name": "The soberanos curve (BTP) and the Peru USD global bonds",
     "venue": "MEF primary auctions; the offshore secondary market",
     "why": "foreign holdings of soberanos are among the highest in EM (roughly a third of the "
            "stock), which makes the curve a FOREIGN-POSITIONING observable and the fastest "
            "read on a political event -- but it is not quotable here",
     "regime": "local-currency issuance with a published auction calendar; the fiscal rule caps "
               "the deficit and has been suspended and reinstated on dated decrees",
     "route": "UST10Y is the global duration leg; the EM FX legs carry the credit state",
     "proxies": ("USDBRL", "USDMXN", "US500")},
    {"name": "LME copper, zinc and lead cash, the exchange stock reports and the TC/RC terms",
     "venue": "the London Metal Exchange and the annual concentrate benchmark negotiation",
     "why": "Peru ships CONCENTRATE, not refined metal, so the treatment and refining charge is "
            "the part of the price the producer actually receives; the benchmark is settled once "
            "a year between the miners and the Chinese smelters and is not a broker instrument",
     "regime": "an annual negotiated benchmark plus a spot TC/RC assessment",
     "route": "the refined metal CFDs are the executable leg; the TC/RC is a CONDITION on them",
     "proxies": ("XCUUSD", "XZNUSD", "XPBUSD")},
    {"name": "Fishmeal and fish-oil FOB assessments (Peru super-prime)",
     "venue": "private price reporting; the IFFO and trade-press assessments",
     "why": "the price leg of the anchoveta mechanism; the QUOTA and the LANDINGS are public and "
            "the PRICE is not, so this pack measures the substitute (soymeal) and never claims "
            "to measure fishmeal",
     "regime": "assessed, subscription-only, terms forbid machine extraction",
     "route": "SOYBEAN and CORN are the executable substitutes in the feed ration",
     "proxies": ("SOYBEAN", "CORN")},
    {"name": "The Peruvian natural gas and LNG complex (Camisea, Pampa Melchorita)",
     "venue": "Perupetro contracts; the Melchorita LNG offtake",
     "why": "Camisea is a domestic-price-regulated field with an export train; the domestic "
            "price is administered and the export cargo is a spot LNG flow, and neither is a "
            "broker symbol -- the honest executable is the crude leg the mine fleet burns",
     "regime": "administered domestic price plus a contracted export train",
     "route": "XTIUSD carries the diesel and fleet-cost leg; the gas leg is UNMEASURED",
     "proxies": ("XTIUSD",)},
)

# --------------------------------------------------------------------------- the central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "Banco Central de Reserva del Peru (BCRP)",
    "framework": "inflation_targeter",
    "policy_instrument": "the tasa de referencia, set monthly in the Programa Monetario, inside "
                         "a corridor bounded by the deposit and repo standing facilities; and "
                         "SEPARATELY the reserve requirement (encaje) in soles and in dollars, "
                         "which is a second, independent instrument this bank uses often",
    "mandate": "preserve monetary stability under article 84 of the constitution; the target is "
               "PUBLISHED AND NUMERIC -- 2% with a +/-1 point tolerance band, in force since "
               "2007 (the target was 2.5% from 2002 to 2006) -- which is what makes a Peruvian "
               "policy surprise measurable against a stated benchmark, unlike Morocco's",
    "decision_rule": "TWELVE scheduled decisions a year, one per month, announced on a THURSDAY "
                     "at 18:00 America/Lima (23:00 UTC, no DST anywhere in the country) and "
                     "effective the following day; the calendar is published a year ahead",
    "decision_calendar_rule": "monthly, on the first or second Thursday, on a calendar BCRP "
                              "publishes a year in advance at bcrp.gob.pe; "
                              "`policy_thursdays(year)` produces the 24-day CANDIDATE lattice "
                              "the collector intersects with that calendar",
    "decision_dates": (),
    "dates_status": "NOT LISTED, DELIBERATELY (L1.28a). The BCRP publishes the Programa "
                    "Monetario calendar a year ahead and this pack refuses to invent twelve "
                    "dates a year it has not read. The CADENCE is certain -- monthly, Thursday, "
                    "18:00 Lima -- and `policy_thursdays(year)` is the candidate lattice. A "
                    "cell compiled on an unverified date is UNMEASURED, not approximate",
    "decision_time_utc": "23:00",
    "announce_local": "18:00 America/Lima on the decision Thursday; the nota informativa carries "
                      "the vote and the forward language, and the Reporte de Inflacion (four a "
                      "year) carries the projection revision",
    "dst_rule": "NONE. Peru is UTC-5 all year and has not observed daylight saving since 1994, "
                "so 23:00 UTC is the announcement minute in every month of every year -- one of "
                "the few countries on this desk whose event minute never moves",
    "minutes_lag_days": 0,
    "publication_classes": ("nota_informativa_programa_monetario", "reporte_de_inflacion",
                            "nota_semanal", "resumen_informativo", "memoria_anual",
                            "intervencion_cambiaria_diaria", "saldo_cdr_y_swaps",
                            "encaje_en_soles_y_en_dolares"),
    "policy_rate_series": "BCRP:tasa_de_referencia",
    "expected_rate_series": "UNMEASURED",
    "consensus_proxy": "the BCRP's own Encuesta de Expectativas Macroeconomicas (a published "
                       "monthly survey of analysts, financial firms and non-financial firms) "
                       "and the Reuters/Bloomberg poll carried by Gestion the day before",
    "consensus_proxy_trap": "the Encuesta is published for the MONTH, not for the meeting, and "
                            "its cut-off precedes the decision by up to three weeks; using it as "
                            "the meeting-day consensus imports a three-week-old expectation and "
                            "manufactures surprises that nobody was surprised by",
    "reserves_clock": "reservas internacionales netas are published DAILY in the nota semanal's "
                      "companion table -- among the highest-frequency reserve series on this "
                      "desk -- alongside the spot intervention and the CDR and swap balances",
    "programme": "NONE and by choice: Peru holds an IMF Flexible Credit Line as a PRECAUTIONARY "
                 "arrangement and has never drawn on it. The IMF clock here is an Article IV and "
                 "FCL-review clock, never a tranche clock",
    "off_cycle": ("2020-03-19 emergency cut to 1.25% and 2020-04-09 to 0.25%, the lowest policy "
                  "rate in the bank's history, held for seventeen months",
                  "the encaje (reserve requirement) is moved BETWEEN meetings and is a second "
                  "instrument a rate-only study never sees"),
    "root": "https://www.bcrp.gob.pe",
}

# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "SBS tipo de cambio contable (the official daily sol reference)",
     "local": "published each business day at the close of the Lima interbank session",
     "time_utc": "22:00", "time_utc_dst": "22:00",
     "dst_rule": "none: Peru is UTC-5 all year",
     "instruments": ("USDBRL", "USDMXN"), "window_minutes": 30,
     "why": "the reference every contract, tax filing and customs declaration in the country is "
            "settled against; PEN is absent from the broker so the EM legs carry the state"},
    {"name": "BCRP daily FX intervention print (compras y ventas en mesa de negociacion)",
     "local": "published with the day's operations after the Lima close",
     "time_utc": "22:30", "time_utc_dst": "22:30", "dst_rule": "none: UTC-5 all year",
     "instruments": ("USDBRL", "USDMXN", "XCUUSD"), "window_minutes": 60,
     "why": "the central bank publishes what it did IN THE SPOT MARKET, by day and by amount; "
            "this is the reaction function, observed rather than inferred"},
    {"name": "BCRP CDR and swap cambiario auction results",
     "local": "auctioned intraday when hedging demand builds", "time_utc": "17:00",
     "time_utc_dst": "17:00", "dst_rule": "none: UTC-5 all year",
     "instruments": ("USDBRL", "USDMXN"), "window_minutes": 60,
     "why": "the derivatives leg of the intervention: the BCRP absorbs hedging demand here "
            "rather than selling reserves, which is why the sol's realised volatility is low"},
    {"name": "LME official settlement (copper, zinc, lead) -- the price Peru's concentrate sells "
             "against",
     "local": "12:00-13:00 Europe/London ring", "time_utc": "12:00", "time_utc_dst": "11:00",
     "dst_rule": "GMT/BST", "instruments": ("XCUUSD", "XZNUSD", "XPBUSD"), "window_minutes": 60,
     "why": "the concentrate contract prices off the exchange month less the TC/RC; the mine "
            "gate price is never quoted and the exchange settlement is"},
    {"name": "LBMA silver price auction (the by-product metal's benchmark)",
     "local": "12:00 Europe/London", "time_utc": "12:00", "time_utc_dst": "11:00",
     "dst_rule": "GMT/BST", "instruments": ("XAGUSD",), "window_minutes": 15,
     "why": "Peru's silver is a CO-PRODUCT of the zinc and lead concentrates, so a silver cell "
            "conditioned on a Peruvian event must control for the base-metal leg"},
    {"name": "BVL closing auction (S&P/BVL Peru General)",
     "local": "15:00 America/Lima", "time_utc": "20:00", "time_utc_dst": "20:00",
     "dst_rule": "none: UTC-5 all year", "instruments": ("XCUUSD", "US500"),
     "window_minutes": 30,
     "why": "the domestic close; no index CFD exists, and the index is ~60% mining, so the "
            "metals carry it and US500 carries the risk state"},
    {"name": "Callao and Matarani concentrate loading window",
     "local": "continuous; the APN publishes monthly throughput",
     "time_utc": "14:00", "time_utc_dst": "14:00", "dst_rule": "none: UTC-5 all year",
     "instruments": ("XCUUSD", "XZNUSD"), "window_minutes": 180,
     "why": "the physical gate: a blockade on the Corredor Minero shows up as a missing sailing "
            "from Matarani two to three weeks later, which dates the supply effect"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "BCRP Programa Monetario decision Thursday", "kind": "weekday", "weekday": 3,
     "roll": "next", "window_utc": ("22:00", "23:59"),
     "instruments": ("USDBRL", "USDMXN", "XCUUSD"),
     "why": "twelve a year, always a Thursday, always 23:00 UTC; the clock never moves because "
            "Peru has no daylight saving"},
    {"name": "MINEM Boletin Estadistico Minero monthly release", "kind": "day_of_month",
     "days": (25, 26, 27, 28), "roll": "next", "window_utc": ("14:00", "20:00"),
     "instruments": ("XCUUSD", "XZNUSD", "XAGUSD", "XPBUSD"),
     "why": "the mine-by-mine production count for the month two months back, published late in "
            "the following month"},
    {"name": "Defensoria del Pueblo Reporte de Conflictos Sociales", "kind": "day_of_month",
     "days": (10, 11, 12, 13, 14, 15), "roll": "next", "window_utc": ("14:00", "22:00"),
     "instruments": ("XCUUSD", "XZNUSD"),
     "why": "the monthly count of active conflicts by case and province; the escalation state "
            "is the leading half of the blockade mechanism"},
    {"name": "Month-end mining royalty, IEM and canon settlement", "kind": "month_end",
     "roll": "previous", "window_utc": ("14:00", "21:00"),
     "instruments": ("XCUUSD", "USDBRL"),
     "why": "the miners buy soles at the month end to pay royalties, the impuesto especial and "
            "the canon; a recurring, dated, involuntary domestic-currency demand"},
    {"name": "Quarter-end concentrate provisional pricing and final settlement",
     "kind": "quarter_end", "roll": "previous", "window_utc": ("12:00", "16:00"),
     "instruments": ("XCUUSD", "XZNUSD", "XPBUSD"),
     "why": "concentrate is sold provisionally and repriced at the quotational period's average; "
            "quarter boundaries concentrate the mark-to-market and the hedging"},
    {"name": "Fiscal year end (31 December) and the Ley de Presupuesto",
     "kind": "fiscal_year_end", "roll": "previous", "window_utc": ("14:00", "21:00"),
     "instruments": ("USDBRL", "XAUUSD"),
     "why": "the budget year is the calendar year; the canon minero transfer to the regions is "
            "computed on it, which is the fiscal half of the conflict mechanism"},
    {"name": "AFP contribution and the legislated withdrawal windows", "kind": "week_of_month",
     "weekday": 4, "week_of_month": 1, "roll": "next", "window_utc": ("15:00", "21:00"),
     "instruments": ("USDBRL", "USDMXN", "US500"),
     "why": "seven legislated pension withdrawals since 2020 forced the AFPs to unwind offshore "
            "assets on dated schedules -- the largest involuntary flow in the country"},
)

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Bolsa de Valores de Lima (BVL) -- S&P/BVL Peru General, Peru Select",
     "index_symbols": (),
     "open_local": "09:00", "close_local": "15:00", "open_utc": "14:00", "close_utc": "20:00",
     "dst_rule": "none: America/Lima is UTC-5 all year, so the BVL session's UTC window is the "
                 "same in January and in July -- rare on this desk and worth using",
     "auction": "opening call from 08:30, continuous trading, closing call at 15:00",
     "expiry_rule": "there is effectively no listed derivatives market: the BVL has launched "
                    "and withdrawn futures more than once and there is no expiry clock to mine",
     "holidays": "the national feriado calendar; Semana Santa closes Thursday and Friday",
     "notes": "NO CFD IS QUOTED on any BVL index, so the bourse enters only as a transmission "
              "target. The index is roughly 60% mining by weight and it is integrated into the "
              "MILA (Mercado Integrado Latinoamericano) with Chile, Colombia and Mexico, which "
              "means a Lima print can be a Santiago print arriving late"},
    {"name": "The Lima interbank FX market and the BCRP's mesa de negociacion",
     "index_symbols": (), "open_local": "09:00", "close_local": "13:30",
     "open_utc": "14:00", "close_utc": "18:30", "dst_rule": "none: UTC-5 all year",
     "auction": "BCRP spot intervention at the desk's discretion; CDR and swap auctions on "
                "demand, with the results published",
     "expiry_rule": "forwards and NDFs are dealt offshore and are not an exchange clock",
     "holidays": "the banking calendar",
     "notes": "the whole point of this venue for the desk is that the CENTRAL BANK PUBLISHES "
              "WHAT IT DID IN IT, daily, by amount -- an observed reaction function"},
    {"name": "The physical concentrate gate: Callao, Matarani, Ilo and Chancay",
     "index_symbols": (), "open_local": "00:00", "close_local": "23:59",
     "open_utc": "05:00", "close_utc": "04:59", "dst_rule": "none: UTC-5 all year",
     "auction": "none; the APN publishes throughput monthly and the terminals publish tariffs",
     "expiry_rule": "no expiry; the sailing schedule is the clock",
     "holidays": "ports work through the national calendar; a blockade is not a holiday",
     "notes": "CHANCAY OPENED 2024-11-14 as a deep-water Cosco terminal 80 km north of Callao "
              "with a direct Shanghai service -- a DATED change in Pacific copper logistics and "
              "the single most important physical regime break in this pack"},
)

SESSION_WINDOWS: tuple[dict[str, Any], ...] = (
    {"name": "pe_bcrp_decision", "start_utc": "22:30", "end_utc": "23:59",
     "notes": "the Programa Monetario announcement at 23:00 UTC on a decision Thursday; the "
              "minute never moves because Peru has no daylight saving"},
    {"name": "pe_bvl_session", "start_utc": "14:00", "end_utc": "20:00",
     "notes": "the Lima cash session, UTC-5 all year"},
    {"name": "pe_fx_interbank", "start_utc": "14:00", "end_utc": "18:30",
     "notes": "the interbank FX window inside which the BCRP's published spot intervention "
              "happens"},
    {"name": "pe_minem_release", "start_utc": "14:00", "end_utc": "20:00",
     "notes": "the Boletin Estadistico Minero and the Defensoria conflict report both land "
              "inside the Lima business day"},
    {"name": "pe_lme_overlap", "start_utc": "11:00", "end_utc": "13:00",
     "notes": "the LME ring, which is where a Peruvian supply headline is priced hours before "
              "Lima opens -- the reason a Lima-session study of copper measures the echo"},
)

RELEASE_CLASSES: tuple[dict[str, Any], ...] = (
    {"name": "BCRP Programa Monetario nota informativa (the policy rate)", "cadence": "monthly",
     "time_utc": "23:00", "source": "BCRP", "actual_series": "BCRP:tasa_de_referencia",
     "expected_series": "BCRP:encuesta_expectativas",
     "notes": "twelve a year on a Thursday; the encaje moves between meetings and is a second "
              "instrument"},
    {"name": "INEI indice de precios al consumidor de Lima Metropolitana", "cadence": "monthly",
     "time_utc": "15:00", "source": "INEI", "actual_series": "INEI:ipc_lima",
     "expected_series": "BCRP:encuesta_expectativas_inflacion",
     "notes": "published on the FIRST DAY of the following month -- among the fastest CPI prints "
              "in the world, and the reason the BCRP can react a week later"},
    {"name": "MINEM Boletin Estadistico Minero (production by mine and by metal)",
     "cadence": "monthly", "time_utc": "16:00", "source": "MINEM",
     "actual_series": "MINEM:produccion_por_unidad", "expected_series": "n/a",
     "notes": "the physical count: copper, zinc, silver, gold, lead, tin, iron and molybdenum, "
              "by mining unit, by company and by region"},
    {"name": "Defensoria del Pueblo Reporte Mensual de Conflictos Sociales", "cadence": "monthly",
     "time_utc": "18:00", "source": "Defensoria del Pueblo",
     "actual_series": "DP:conflictos_activos", "expected_series": "n/a",
     "notes": "every active and latent conflict by case, province, actors and state; the "
              "socio-environmental mining subset is the supply series"},
    {"name": "BCRP daily FX intervention and reserve print", "cadence": "daily",
     "time_utc": "22:30", "source": "BCRP", "actual_series": "BCRP:intervencion_cambiaria",
     "expected_series": "n/a",
     "notes": "spot purchases and sales by day and amount, with the CDR and swap balances"},
    {"name": "SUNAT / BCRP monthly trade balance and mineral export values",
     "cadence": "monthly", "time_utc": "16:00", "source": "SUNAT and BCRP",
     "actual_series": "BCRP:exportaciones_mineras", "expected_series": "n/a",
     "notes": "value and volume by product and destination; China's share is the demand read"},
    {"name": "PRODUCE anchoveta quota resolutions and daily landings",
     "cadence": "irregular, seasonal", "time_utc": "18:00",
     "source": "Ministerio de la Produccion and IMARPE",
     "actual_series": "PRODUCE:cuota_anchoveta", "expected_series": "n/a",
     "notes": "the resolucion ministerial that opens, sizes or CANCELS a season, plus the daily "
              "landing count against the quota"},
    {"name": "INEI monthly GDP (produccion nacional) and the mining sub-index",
     "cadence": "monthly", "time_utc": "15:00", "source": "INEI",
     "actual_series": "INEI:pbi_mensual", "expected_series": "n/a",
     "notes": "about 45 days late; the metalica sub-index is the official read on whether a "
              "blockade actually cost production"},
)

# --------------------------------------------------------------------------- holidays
#: FIXED national feriados, each with the YEAR IT BECAME ONE. Ley 31968 (2024) added FOUR new
#: national holidays at once -- 7 June, 23 July, 6 August and 9 December -- so a study that pools
#: 2019-2026 and treats the calendar as constant mislabels four closed days a year from 2024 on.
#: That is exactly the regime break a holiday-liquidity study silently eats.
#: Rows are (month, day, name, first_year); first_year 0 means "as far back as this pack reaches".
FIXED_NATIONAL: tuple[tuple[int, int, str, int], ...] = (
    (1, 1, "Ano Nuevo", 0),
    (5, 1, "Dia del Trabajo", 0),
    (6, 7, "Batalla de Arica y Dia de la Bandera [Ley 31968]", 2024),
    (6, 29, "San Pedro y San Pablo", 0),
    (7, 23, "Dia de la Fuerza Aerea del Peru [Ley 31968]", 2024),
    (7, 28, "Fiestas Patrias: Dia de la Independencia", 0),
    (7, 29, "Fiestas Patrias: Dia de las Fuerzas Armadas y la Policia Nacional", 0),
    (8, 6, "Batalla de Junin [Ley 31968]", 2024),
    (8, 30, "Santa Rosa de Lima", 0),
    (10, 8, "Combate de Angamos", 0),
    (11, 1, "Dia de Todos los Santos", 0),
    (12, 8, "Inmaculada Concepcion", 0),
    (12, 9, "Batalla de Ayacucho [Ley 31968]", 2024),
    (12, 25, "Navidad", 0),
)
#: The two Easter-derived NATIONAL feriados, as offsets from Easter Sunday.
EASTER_NATIONAL: tuple[tuple[int, str], ...] = (
    (-3, "Jueves Santo"),
    (-2, "Viernes Santo"),
)
#: THE REGIONAL AND ANDEAN CALENDAR. These are NOT national market closures and they are not in
#: the BVL table -- they are the days the SIERRA stops, which is where the mines and the roads
#: are. Carnaval empties the Corredor Minero for two days, Semana Santa empties Ayacucho for a
#: week, and Inti Raymi empties Cusco. A blockade study that does not carry them will read a
#: quiet road as a resolved conflict. Rows are (offset-from-Easter or None, month, day, region,
#: name).
REGIONAL_DAYS: tuple[tuple[int | None, int, int, str, str], ...] = (
    (-48, 0, 0, "sierra (Cajamarca, Puno, Apurimac, Cusco)", "Lunes de Carnaval"),
    (-47, 0, 0, "sierra (Cajamarca, Puno, Apurimac, Cusco)", "Martes de Carnaval"),
    (-6, 0, 0, "Ayacucho", "Semana Santa de Ayacucho (Domingo de Ramos)"),
    (None, 6, 24, "Cusco", "Inti Raymi / Dia del Campesino"),
    (None, 8, 15, "Arequipa", "Aniversario de Arequipa"),
    (None, 11, 5, "Puno", "Semana Jubilar de Puno / llegada de Manco Capac"),
)
#: ONE-OFF closures and clock facts no recurring rule produces. Each carries its own status: a
#: supreme decree that suspended work in Lima and Callao is a real closure, and this pack labels
#: the ones it has not read the decree number for.
DECLARED_CLOSURES: dict[date, str] = {
    date(2024, 11, 14): "APEC Lima summit: dias no laborables decreed for Lima and Callao "
                        "[DECREE_REPORTED -- confirm the DS number in El Peruano before a cell "
                        "is compiled on it]",
    date(2024, 11, 15): "APEC Lima summit, second day [DECREE_REPORTED -- same caveat]",
}

#: THE POLITICAL EVENT SERIES. Six presidents since 2016 and every transition has a MINUTE, not a
#: month. Rows are (date, event, status). PRESS_REPORTED is exactly what it says: the day as
#: carried by the record, to be confirmed against El Peruano or the Congress record before a
#: cell is promoted on it. Nothing here is presented as a verified gazette citation.
POLITICAL_EVENTS: tuple[tuple[date, str, str], ...] = (
    (date(2016, 7, 28), "Kuczynski takes office", "PRESS_REPORTED"),
    (date(2017, 12, 21), "first vacancia vote fails", "PRESS_REPORTED"),
    (date(2018, 3, 21), "Kuczynski resigns; Vizcarra takes office", "PRESS_REPORTED"),
    (date(2019, 9, 30), "Vizcarra dissolves Congress", "PRESS_REPORTED"),
    (date(2020, 11, 9), "Vizcarra vacated; Merino takes office", "PRESS_REPORTED"),
    (date(2020, 11, 15), "Merino resigns after the protests; Sagasti takes office 17 Nov",
     "PRESS_REPORTED"),
    (date(2021, 6, 6), "presidential run-off; the result contested for six weeks",
     "PRESS_REPORTED"),
    (date(2021, 7, 28), "Castillo takes office", "PRESS_REPORTED"),
    (date(2022, 12, 7), "SELF-COUP: Castillo announces the dissolution of Congress around 11:40 "
                        "Lima, is vacated the same afternoon and arrested; Boluarte sworn in",
     "PRESS_REPORTED"),
    (date(2022, 12, 14), "state of emergency declared as the protests spread to the south",
     "PRESS_REPORTED"),
    (date(2023, 1, 9), "Juliaca: the deadliest day of the protests; the Corredor Minero closes",
     "PRESS_REPORTED"),
    (date(2024, 11, 14), "Chancay megaport inaugurated with the Chinese head of state present",
     "PRESS_REPORTED"),
)

#: THE CONFLICT AND BLOCKADE EPISODES -- the pack's single most valuable table, and the one that
#: must be read with its status label attached. Rows are (start, end, site, what, status).
#: Las Bambas ships roughly 2% of world copper supply down ONE road, the Corredor Vial Minero del
#: Sur, through Chumbivilcas and Cotabambas. When that road closes the mine runs down its
#: stockpile and then halts, and both the closure and the halt are announced. PRESS_REPORTED
#: means the dates are as carried by the company statements, the Defensoria reports and the
#: trade press; they are hypothesis-grade and may not be promoted until each one is confirmed.
BLOCKADE_EPISODES: tuple[tuple[date, date, str, str, str], ...] = (
    (date(2019, 2, 8), date(2019, 3, 5), "Corredor Minero (Chumbivilcas)",
     "community blockade of the concentrate road", "PRESS_REPORTED"),
    (date(2020, 8, 3), date(2020, 8, 20), "Corredor Minero (Chumbivilcas)",
     "blockade over the road-use and compensation agreements", "PRESS_REPORTED"),
    (date(2021, 11, 20), date(2021, 12, 31), "Corredor Minero (Chumbivilcas)",
     "six-week blockade; Las Bambas warned of a production halt", "PRESS_REPORTED"),
    (date(2022, 4, 14), date(2022, 6, 11), "Las Bambas mine site (Fuerabamba, Huancuire)",
     "OCCUPATION OF THE MINE ITSELF: operations suspended around 20 April and restarted in "
     "June -- roughly fifty days of a ~2%-of-world-supply unit", "PRESS_REPORTED"),
    (date(2022, 7, 20), date(2022, 8, 15), "Corredor Minero (Chumbivilcas)",
     "renewed blockade weeks after the restart", "PRESS_REPORTED"),
    (date(2023, 1, 9), date(2023, 2, 20), "the southern corridor and the Cusco-Arequipa axis",
     "the post-self-coup protests close the corridor; Las Bambas, Antapaccay and Constancia all "
     "report restricted movement", "PRESS_REPORTED"),
    (date(2022, 2, 28), date(2022, 3, 31), "Cuajone (Southern Peru, Moquegua)",
     "the Tumilaca community seizes the water supply and the rail line; Cuajone halts",
     "PRESS_REPORTED"),
    (date(2023, 12, 1), date(2023, 12, 20), "Corredor Minero (Cotabambas)",
     "blockade over the community agreement review", "PRESS_REPORTED"),
    (date(2024, 4, 15), date(2024, 5, 6), "Corredor Minero (Chumbivilcas)",
     "blockade over the road classification and the compensation schedule", "PRESS_REPORTED"),
)

#: THE ANCHOVETA SEASONS. PRODUCE opens, sizes and closes each season by resolucion ministerial
#: on IMARPE's biomass estimate. The NORTH-CENTRE stock runs two seasons a year; the normal
#: windows are declared here as the SEASONAL RULE and the exceptional years are declared beside
#: them, because the exception is the tradable event. Rows are (year, season, start, end, status).
ANCHOVETA_SEASONS: tuple[tuple[int, int, date, date, str], ...] = (
    (2022, 1, date(2022, 4, 25), date(2022, 7, 31), "PRESS_REPORTED"),
    (2022, 2, date(2022, 11, 23), date(2023, 1, 15), "PRESS_REPORTED"),
    (2023, 1, date(2023, 6, 1), date(2023, 6, 1), "CANCELLED"),
    (2023, 2, date(2023, 11, 1), date(2024, 1, 18), "PRESS_REPORTED"),
    (2024, 1, date(2024, 4, 22), date(2024, 7, 31), "PRESS_REPORTED"),
    (2024, 2, date(2024, 11, 5), date(2025, 1, 15), "PRESS_REPORTED"),
    (2025, 1, date(2025, 4, 22), date(2025, 7, 31), "PROJECTED"),
    (2025, 2, date(2025, 11, 1), date(2026, 1, 15), "PROJECTED"),
)
#: The normal statutory windows the seasons are drawn from, kept separately so a projected row
#: can be told apart from an observed one.
ANCHOVETA_RULE_WINDOWS: tuple[tuple[int, int, int, int], ...] = (
    (4, 15, 7, 31),      # first season: opens in the second half of April, closes end July
    (11, 1, 1, 15),      # second season: opens in November, closes mid-January
)


def easter(year: int) -> date:
    """Easter Sunday by the ANONYMOUS GREGORIAN ALGORITHM. Every movable date in this pack --
    Jueves Santo, Viernes Santo and the two Carnaval days of the sierra -- is an offset from it,
    computed rather than typed, so the table extends to any year without anybody editing it."""
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


def holy_week(year: int) -> dict[date, str]:
    """Jueves Santo and Viernes Santo: the two national feriados Easter produces."""
    base = easter(year)
    return {base + timedelta(days=off): name for off, name in EASTER_NATIONAL}


def carnaval(year: int) -> tuple[date, date]:
    """Lunes and Martes de Carnaval: Easter minus 48 and 47 days. Not a national feriado in
    Peru, and the two days the Andean south actually stops."""
    base = easter(year)
    return base - timedelta(days=48), base - timedelta(days=47)


def national_holidays(year: int) -> dict[date, str]:
    """The national feriado table for a year: the fixed days that were in force IN THAT YEAR,
    the two Easter-derived days, and the declared one-off closures. NO WEEKEND SUBSTITUTION --
    a Peruvian feriado that falls on a Sunday is lost, which is itself a liquidity fact."""
    out: dict[date, str] = {}
    for m, d, name, since in FIXED_NATIONAL:
        if year >= since:
            out[date(year, m, d)] = name
    out.update(holy_week(year))
    for day, name in DECLARED_CLOSURES.items():
        if day.year == year:
            out[day] = name
    return dict(sorted(out.items()))


def bank_holidays(year: int) -> dict[date, str]:
    """The banking calendar. Peru's banks close on the national feriados and on nothing else
    the BVL does not also close on, so the two tables coincide on weekdays."""
    return national_holidays(year)


def market_holidays(year: int) -> dict[date, str]:
    """BVL closed days: the national calendar on WEEKDAYS only. A Sunday feriado costs no
    session and must never enter a holiday-liquidity sample as one."""
    return {d: n for d, n in bank_holidays(year).items() if d.weekday() < 5}


def regional_days(year: int) -> dict[date, str]:
    """The sierra's own calendar for a year: Carnaval, the Ayacucho Holy Week, Inti Raymi and
    the regional anniversaries. These close ROADS and MINES, not the BVL, which is why they are
    a separate table and not folded into the national one."""
    out: dict[date, str] = {}
    base = easter(year)
    for off, month, day, region, name in REGIONAL_DAYS:
        got = base + timedelta(days=off) if off is not None else date(year, month, day)
        out[got] = f"{name} ({region})"
    return dict(sorted(out.items()))


def is_market_holiday(day: date) -> bool:
    return day in market_holidays(day.year)


def new_holidays_since_2024() -> tuple[tuple[int, int, str], ...]:
    """The four feriados Ley 31968 created. A pooled study that misses this break mislabels
    four closed days a year from 2024 onward."""
    return tuple((m, d, name) for m, d, name, since in FIXED_NATIONAL if since == 2024)


def policy_thursdays(year: int) -> tuple[date, ...]:
    """THE BCRP ANNOUNCEMENT CANDIDATE LATTICE: the first and second Thursday of every month.

    The bank decides TWELVE times a year, always on a Thursday, always at 18:00 Lima (23:00 UTC,
    and Peru has no daylight saving so the minute never moves), on a calendar it publishes a year
    ahead. This pack refuses to invent that calendar (L1.28a) and produces the 24-day lattice the
    collector intersects with the published one instead -- every BCRP decision in the modern era
    falls on one of these two Thursdays.
    """
    out: list[date] = []
    for month in range(1, 13):
        first = date(year, month, 1)
        offset = (3 - first.weekday()) % 7          # Thursday is weekday 3
        thursday = first + timedelta(days=offset)
        out.append(thursday)
        out.append(thursday + timedelta(days=7))
    return tuple(out)


def blockade_episodes(status: str = "PRESS_REPORTED") -> tuple[tuple[date, date, str, str], ...]:
    """The declared supply-disruption episodes at or above a confidence label."""
    order = {"PRESS_REPORTED": 0, "COMPANY_CONFIRMED": 1, "GAZETTE_VERIFIED": 2}
    floor = order.get(status, 0)
    return tuple((lo, hi, site, what) for lo, hi, site, what, st in BLOCKADE_EPISODES
                 if order.get(st, 0) >= floor)


def is_blockade_day(day: date) -> bool:
    """True when `day` falls inside a DECLARED blockade or mine-occupation episode. This is the
    conditioning state of PE-D and the reason this pack exists."""
    return any(lo <= day <= hi for lo, hi, _s, _w, _st in BLOCKADE_EPISODES)


def blockade_days(start: date, end: date) -> list[date]:
    """Every day inside [start, end] that falls in a declared blockade episode."""
    out: list[date] = []
    day = start
    while day <= end:
        if is_blockade_day(day):
            out.append(day)
        day += timedelta(days=1)
    return out


def anchoveta_season(day: date) -> tuple[int, int, str] | None:
    """The (year, season, status) a date falls inside, or None when the fishery is closed.
    A CANCELLED row is zero-length by construction and can never contain a day, which is how a
    cancelled season reads as 'closed' rather than as missing data."""
    for year, season, lo, hi, status in ANCHOVETA_SEASONS:
        if status == "CANCELLED":
            continue
        if lo <= day <= hi:
            return (year, season, status)
    return None


def in_anchoveta_season(day: date) -> bool:
    return anchoveta_season(day) is not None


def cancelled_seasons() -> tuple[tuple[int, int], ...]:
    """The seasons PRODUCE cancelled outright. Each one is a dated protein-supply shock with a
    soymeal substitution on the other side of it -- the tradable half of PE-F."""
    return tuple((y, s) for y, s, _lo, _hi, st in ANCHOVETA_SEASONS if st == "CANCELLED")


HOLIDAYS_RULE: dict[str, Any] = {
    "kind": "computed_from_statute_plus_declared_table",
    "authority": "Decreto Legislativo 713 fixes the feriados nacionales; Ley 31968 (2024) added "
                 "7 June, 23 July, 6 August and 9 December; the Presidencia del Consejo de "
                 "Ministros decrees one-off dias no laborables by supreme decree in El Peruano",
    "rule": "FOURTEEN fixed national days -- 1 Jan, 1 May, 7 Jun, 29 Jun, 23 Jul, 28 Jul, "
            "29 Jul, 6 Aug, 30 Aug, 8 Oct, 1 Nov, 8 Dec, 9 Dec and 25 Dec, of which FOUR "
            "(7 Jun, 23 Jul, 6 Aug, 9 Dec) exist only from 2024 under Ley 31968 -- PLUS two "
            "EASTER-DERIVED days, Jueves Santo (Easter minus 3) and Viernes Santo (Easter minus "
            "2), computed with the anonymous Gregorian algorithm in `easter(year)` and never "
            "typed. NO WEEKEND SUBSTITUTION: a feriado on a Saturday or Sunday is lost. The "
            "SIERRA keeps a second calendar -- Lunes and Martes de Carnaval (Easter minus 48 "
            "and 47), the Ayacucho Holy Week, Inti Raymi on 24 June and the regional "
            "anniversaries -- which closes ROADS and MINES rather than the bourse and is "
            "carried separately in `regional_days(year)`.",
    "years": (2024, 2025, 2026),
    "weekend": "Saturday and Sunday",
    "national_rule": "see `rule`; `national_holidays(year)` is the computed form",
    "market_rule": "the national calendar on weekdays; the BVL keeps 09:00-15:00 America/Lima "
                   "in every month because Peru has no daylight saving",
    "regional_rule": "`regional_days(year)`: the Andean calendar, which is the one the Corredor "
                     "Minero runs on",
    "statute_break": "Ley 31968 (2024) is a REGIME BREAK in the closed-day series: four new "
                     "national holidays at once. A study pooling 2019-2026 without it "
                     "mislabels four days a year from 2024",
    "table": {y: {d.isoformat(): n for d, n in national_holidays(y).items()}
              for y in (2024, 2025, 2026)},
    "status": {2024: "STATUTORY for the fixed days, COMPUTED for Jueves and Viernes Santo, "
                     "DECREE_REPORTED for the two APEC non-working days",
               2025: "STATUTORY and COMPUTED; no one-off decree carried",
               2026: "STATUTORY and COMPUTED; the Easter dates are computed and certain, and "
                     "any dia no laborable the PCM decrees for 2026 is not yet published"},
    "known_dates": {
        "2024-03-28": "Jueves Santo (Easter 2024 is 31 March)",
        "2024-06-07": "the first Batalla de Arica observed as a national feriado under Ley 31968",
        "2025-04-17": "Jueves Santo (Easter 2025 is 20 April)",
        "2025-07-28": "Fiestas Patrias, a fixed solar date and certain in every year",
        "2026-04-02": "Jueves Santo (Easter 2026 is 5 April)",
        "2026-12-09": "Batalla de Ayacucho, a national feriado since 2024",
    },
    "fn": market_holidays,
    "national_fn": national_holidays,
    "bank_fn": bank_holidays,
    "regional_fn": regional_days,
    "easter_fn": easter,
    "carnaval_fn": carnaval,
}

# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "BCRP daily FX intervention: spot purchases and sales on the mesa de negociacion",
     "root": "https://www.bcrp.gob.pe/estadisticas/cuadros-de-la-nota-semanal.html",
     "fields": ("compras_spot_usd", "ventas_spot_usd", "tipo_de_cambio_interbancario",
                "reservas_internacionales_netas"),
     "frequency": "daily", "snapshot": "the trading day", "publish_utc": "22:30", "lag_days": 0,
     "licence": "free, public", "available": True,
     "why": "THE REACTION FUNCTION, OBSERVED. Most central banks leave the desk to infer whether "
            "they intervened; the BCRP publishes the amount by day. This is the conditioning "
            "variable of PE-B and there is no equivalent in the `cl`, `br` or `mx` packs",
     "pit_warning": "published after the Lima close, so it conditions the NEXT session and "
                    "never the one it describes"},
    {"name": "BCRP CDR and swap cambiario outstanding balances",
     "root": "https://www.bcrp.gob.pe/estadisticas.html",
     "fields": ("saldo_cdr_bcrp", "saldo_swaps_cambiarios", "vencimientos_programados"),
     "frequency": "daily", "snapshot": "end of day", "publish_utc": "22:30", "lag_days": 0,
     "licence": "free, public", "available": True,
     "why": "the derivatives leg: how much hedging demand the bank is warehousing instead of "
            "selling reserves. A rising balance with a flat spot print is the bank holding the "
            "sol without spending anything, which is the state that makes PEN volatility a "
            "policy output",
     "pit_warning": "balances are stocks; the FLOW must be differenced and the maturity schedule "
                    "read beside it or a roll looks like an intervention"},
    {"name": "Non-resident holdings of soberanos (the local-currency sovereign curve)",
     "root": "https://www.mef.gob.pe/es/portal-de-transparencia-economica",
     "fields": ("tenencia_no_residentes_pct", "saldo_btp", "plazo_promedio"),
     "frequency": "monthly", "snapshot": "month end", "publish_utc": "16:00", "lag_days": 20,
     "licence": "free, public", "available": True,
     "why": "among the highest foreign ownership shares of any local-currency EM curve, which "
            "makes the soberanos the fastest read on a political event and the channel through "
            "which a vacancia becomes an FX flow",
     "pit_warning": "MONTHLY and three weeks late; it conditions a regime, never a week"},
    {"name": "SBS AFP portfolio and the BCRP limite operativo for foreign investment",
     "root": "https://www.sbs.gob.pe/estadisticas-y-publicaciones",
     "fields": ("cartera_administrada", "inversion_en_el_exterior_pct", "limite_operativo_pct",
                "retiros_extraordinarios"),
     "frequency": "monthly", "snapshot": "month end", "publish_utc": "16:00", "lag_days": 25,
     "licence": "free, public", "available": True,
     "why": "the BCRP sets the AFPs' offshore limit and RAISES IT IN STEPS, each step a dated "
            "instruction to buy foreign assets; and Congress has legislated SEVEN extraordinary "
            "withdrawals since 2020, each a dated instruction to sell them",
     "pit_warning": "the withdrawal laws have a dated enactment and a LATER dated first payment "
                    "window; using the enactment as the flow date is off by weeks"},
    {"name": "CFTC Commitments of Traders, COMEX copper and silver",
     "root": "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm",
     "fields": ("managed_money_long", "managed_money_short", "producer_merchant", "open_interest"),
     "frequency": "weekly", "snapshot": "Tuesday", "publish_utc": "19:30", "lag_days": 3,
     "licence": "public domain (US government work)", "available": True,
     "why": "the executable metals' own positioning; a Peruvian supply shock into a crowded "
            "managed-money short is a different trade from the same shock into a flat book",
     "pit_warning": "Tuesday snapshot published Friday: a Wednesday blockade is invisible until "
                    "the following week's report"},
    {"name": "a CFTC or exchange-traded SOL positioning series",
     "root": "", "fields": (), "frequency": "n/a", "snapshot": "", "publish_utc": "",
     "lag_days": 0, "licence": "", "available": False,
     "why": "DECLARED ABSENT: no PEN future trades on any exchange the desk can read and no COT "
            "contract exists for the sol",
     "pit_warning": "DOES NOT EXIST: sol positioning is UNMEASURED and is never proxied by the "
                    "BRL or MXN COT legs, which are positions in other countries' politics"},
)

# --------------------------------------------------------------------------- terminology
#: THREE LANGUAGES, AND THE PACK MEANS IT. Spanish is the working language of the BCRP, the MEF,
#: the BVL and the whole business press. QUECHUA and AYMARA are OFFICIAL languages under article
#: 48 of the 1993 constitution wherever they predominate -- which is precisely where the mines
#: are. The prior-consultation record under Ley 29785 is conducted in them, the community
#: assemblies that vote a blockade are held in them, and Servindi and the regional radios report
#: them in them. A Spanish-only crawl of Peru reads Lima and misses the Corredor Minero.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "PE-A": ("Banco Central de Reserva del Perú", "tasa de referencia", "programa monetario",
             "política monetaria", "nota informativa", "reporte de inflación", "encaje",
             "meta de inflación", "expectativas de inflación", "directorio del BCRP",
             "tasa de interés interbancaria", "qullqi wasi (Quechua: the money house, the bank)"),
    "PE-B": ("tipo de cambio", "intervención cambiaria", "mesa de negociación",
             "swap cambiario", "certificado de depósito reajustable", "sol",
             "reservas internacionales netas", "dolarización", "cambistas", "casa de cambio",
             "tipo de cambio SBS", "volatilidad del sol",
             "qullqi (Quechua/Aymara: silver, and the word for money)"),
    "PE-C": ("producción minera", "boletín estadístico minero", "unidad minera",
             "concentrado de cobre", "cobre", "zinc", "plata", "plomo", "oro", "molibdeno",
             "cartera de proyectos mineros", "ley del mineral", "relaves", "planta concentradora",
             "anta (Quechua: copper)", "qullqi (Quechua: silver)", "quri (Quechua/Aymara: gold)",
             "titi (Quechua: lead)"),
    "PE-D": ("conflicto social", "Defensoría del Pueblo", "reporte de conflictos sociales",
             "bloqueo de vías", "paro", "Corredor Vial Minero del Sur", "comunidad campesina",
             "Las Bambas", "Chumbivilcas", "Cotabambas", "Espinar", "consulta previa",
             "licencia social", "mesa de diálogo", "estado de emergencia", "ronderos",
             "ayllu (Quechua/Aymara: the community that decides)",
             "llaqta (Quechua: the town, the people)", "Pachamama", "mink'a (Quechua: the "
             "collective work party a blockade is organised as)",
             "apu (Quechua: the mountain the mine is cut into)",
             "thakhi (Aymara: the road, and the thing a bloqueo closes)",
             "mallku (Aymara: the condor, and the community authority)",
             "ch'alla (Aymara: the offering made before work begins at a mine)"),
    "PE-E": ("vacancia presidencial", "incapacidad moral permanente", "disolución del Congreso",
             "golpe de Estado", "autogolpe", "cuestión de confianza", "moción de censura",
             "estado de emergencia", "toma de Lima", "elecciones generales", "JNE", "ONPE",
             "wañuy (Quechua: death, the word the protest counts were reported in)"),
    "PE-F": ("anchoveta", "IMARPE", "cuota de pesca", "veda", "temporada de pesca",
             "harina de pescado", "aceite de pescado", "desembarque", "biomasa",
             "juveniles", "resolución ministerial", "El Niño", "ENFEN", "PRODUCE",
             "uma (Aymara: water)", "yaku (Quechua: water)"),
    "PE-G": ("Autoridad Portuaria Nacional", "puerto del Callao", "Matarani", "Ilo", "Chancay",
             "megapuerto", "terminal portuario", "carga de concentrados", "embarque",
             "naviera", "Cosco Shipping", "flete marítimo", "cabotaje",
             "Qhapaq Ñan (Quechua: the royal road, the historical name of the corridor)"),
    "PE-H": ("canon minero", "regalía minera", "impuesto especial a la minería",
             "gravamen especial a la minería", "contrato de estabilidad tributaria",
             "SUNAT", "utilidad minera", "inversión minera", "MINEM",
             "certificación ambiental", "SENACE", "estudio de impacto ambiental",
             "allpa (Quechua: the earth the licence is over)"),
    "PE-I": ("Camisea", "gas natural", "Osinergmin", "FEPC", "fondo de estabilización",
             "precio de los combustibles", "diésel", "refinería de Talara", "Petroperú",
             "banda de precios", "Perupetro", "lote 88", "Pampa Melchorita", "GNL"),
    "PE-J": ("AFP", "retiro de fondos", "límite operativo", "inversión en el exterior",
             "remesas", "SBS", "cartera administrada", "ONP", "sistema privado de pensiones",
             "desdolarización", "depósitos en dólares", "crédito en soles"),
    "PE-K": ("café", "café orgánico", "cosecha", "acopio", "cooperativa cafetalera",
             "Junta Nacional del Café", "roya", "precio en chacra", "arábica",
             "agroexportación", "palta", "arándano", "uva de mesa", "SENASA",
             "chakra (Quechua: the cultivated plot)"),
    "PE-L": ("Bolsa de Valores de Lima", "S&P/BVL Perú General", "CAVALI", "SMV",
             "rueda de bolsa", "capitalización bursátil", "MILA", "MSCI mercados emergentes",
             "reclasificación", "bonos soberanos", "tenencia de no residentes",
             "qhatu (Quechua: the market)"),
    "PE-M": ("feriado", "día no laborable", "Fiestas Patrias", "Semana Santa", "Jueves Santo",
             "Viernes Santo", "carnaval", "Inti Raymi", "Día del Campesino", "El Peruano",
             "decreto supremo", "Ley 31968", "año nuevo andino",
             "Willkakuti (Aymara: the return of the sun, the Andean new year)",
             "anata (Aymara: carnival, the two days the sierra stops)",
             "jallu pacha (Aymara: the rainy season that closes the high roads)",
             "awti pacha (Aymara: the dry season the concentrate moves in)"),
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

#: Latin script is shared by all three of this country's languages, so "native script" cannot be
#: a codepoint test here the way Arabic or Hangul can. It is a VOCABULARY test instead, and the
#: tests assert on all three lists: Spanish is detected by its diacritics (an English glossary of
#: Peru has none), Quechua and Aymara by their own words.
_SPANISH_DIACRITICS = "áéíóúüñÁÉÍÓÚÜÑ¿¡"
#: Quechua working vocabulary the pack must carry. `anta`, `qullqi`, `quri` and `titi` are the
#: four metals this desk actually trades, named in the language the miners' communities speak.
QUECHUA_MARKERS: tuple[str, ...] = (
    "anta", "qullqi", "quri", "titi", "yaku", "allpa", "ayllu", "llaqta", "mink'a", "apu",
    "qhatu", "chakra", "wañuy", "Qhapaq Ñan")
#: Aymara working vocabulary. The altiplano -- Puno, the Bolivian border, the southern corridor
#: -- is Aymara-speaking, and `thakhi` (the road) is the object PE-D is about.
AYMARA_MARKERS: tuple[str, ...] = (
    "uma", "thakhi", "mallku", "ch'alla", "Willkakuti", "anata", "jallu pacha", "awti pacha")
#: Spanish working vocabulary the pack must carry: every institution in this country publishes
#: in it, and these are the exact strings a crawler needs.
SPANISH_MARKERS: tuple[str, ...] = (
    "tasa de referencia", "intervención cambiaria", "conflicto social", "bloqueo de vías",
    "comunidad campesina", "consulta previa", "boletín estadístico minero", "canon minero",
    "vacancia presidencial", "anchoveta", "veda", "concentrado de cobre", "Corredor Vial Minero",
    "Defensoría del Pueblo", "día no laborable")


def has_spanish_diacritic(text: str) -> bool:
    """True when the text carries a Spanish diacritic. An English translation of a Peruvian
    release has none, which is what makes this a usable native-language test on Latin script."""
    return any(ch in _SPANISH_DIACRITICS for ch in str(text))


def has_quechua(text: str) -> bool:
    """True when the text carries a declared Quechua term."""
    return any(m in str(text) for m in QUECHUA_MARKERS)


def has_aymara(text: str) -> bool:
    """True when the text carries a declared Aymara term."""
    return any(m in str(text) for m in AYMARA_MARKERS)


def _flat_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> set[str]:
    rows = TERMINOLOGY if terminology is None else terminology
    return {t for terms in rows.values() for t in terms}


def spanish_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    """Every declared Spanish marker actually present in the terminology table."""
    flat = _flat_terms(terminology)
    return [m for m in SPANISH_MARKERS if any(m in t for t in flat)]


def quechua_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    flat = _flat_terms(terminology)
    return [m for m in QUECHUA_MARKERS if any(m in t for t in flat)]


def aymara_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    flat = _flat_terms(terminology)
    return [m for m in AYMARA_MARKERS if any(m in t for t in flat)]


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
        "pe_bcrp", "Banco Central de Reserva del Peru: programa monetario, nota semanal, daily "
                   "FX intervention and reserves, BCRPData, the expectations survey",
        layer="official",
        roots=("https://www.bcrp.gob.pe/politica-monetaria.html",
               "https://www.bcrp.gob.pe/estadisticas/cuadros-de-la-nota-semanal.html",
               "https://estadisticas.bcrp.gob.pe/estadisticas/series/",
               "https://www.bcrp.gob.pe/publicaciones/reporte-de-inflacion.html"),
        queries=("programa monetario nota informativa", "tasa de referencia BCRP",
                 "intervención cambiaria mesa de negociación", "reporte de inflación",
                 "encuesta de expectativas macroeconómicas", "reservas internacionales netas",
                 "saldo de swaps cambiarios", "certificado de depósito reajustable",
                 "encaje en moneda extranjera", "qullqi wasi tasa"),
        languages=("es", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public (bcrp.gob.pe terms)",
        notes="BCRPData is a full time-series API with thousands of series and no key; the "
              "DAILY intervention table is the single most valuable row in this pack's macro "
              "half because it turns a reaction function from an inference into an observation"),
    source_class(
        "pe_minem", "Ministerio de Energia y Minas: the Boletin Estadistico Minero (production "
                    "by mining unit and by metal), the cartera de proyectos, mining investment",
        layer="official",
        roots=("https://www.minem.gob.pe/_estadistica.php?idSector=1",
               "https://www.minem.gob.pe/_publicacionesDetalle.php?idSector=1",
               "https://pad.minem.gob.pe/BigData_Mineria/"),
        queries=("boletín estadístico minero", "producción minera por unidad",
                 "producción de cobre por empresa", "cartera de proyectos mineros",
                 "inversión minera mensual", "producción de zinc", "producción de plata",
                 "anuario minero", "concentrado de cobre exportado", "anta mineral"),
        languages=("es",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="PRODUCTION BY MINE. Antamina's zinc, Cerro Verde's copper, Las Bambas' copper and "
              "Uchucchacua's silver are separate rows every month, so a blockade at one unit is "
              "measurable against the national total rather than hidden inside it"),
    source_class(
        "pe_defensoria", "Defensoria del Pueblo: the monthly Reporte de Conflictos Sociales, "
                         "the case files, the alerta temprana and the dialogue tables",
        layer="official",
        roots=("https://www.defensoria.gob.pe/areas_tematicas/conflictos-sociales/",
               "https://www.defensoria.gob.pe/documentos/",
               "https://www.gob.pe/institucion/defensoria/colecciones/"
               "1163-reporte-de-conflictos-sociales"),
        queries=("reporte de conflictos sociales", "conflicto socioambiental minero",
                 "bloqueo de vías", "Corredor Vial Minero del Sur", "comunidad campesina",
                 "mesa de diálogo", "estado de emergencia", "Las Bambas Chumbivilcas",
                 "Cotabambas conflicto", "ayllu asamblea comunal", "thakhi bloqueo"),
        languages=("es", "qu", "ay"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE REASON THIS PACK EXISTS. A constitutionally independent ombudsman publishes, "
              "every month, every active conflict by case, province, actor and state. The "
              "socio-environmental mining subset is a PHYSICAL SUPPLY SERIES on a metal the "
              "broker quotes, and essentially no systematic desk reads it"),
    source_class(
        "pe_inei", "Instituto Nacional de Estadistica e Informatica: the Lima CPI on the first "
                   "day of the month, monthly GDP, employment, the mining sub-index",
        layer="official",
        roots=("https://www.inei.gob.pe/estadisticas/indice-tematico/price-indexes/",
               "https://www.inei.gob.pe/biblioteca-virtual/boletines/",
               "https://m.inei.gob.pe/estadisticas/indice-tematico/economia/"),
        queries=("índice de precios al consumidor Lima Metropolitana", "inflación mensual",
                 "producción nacional informe técnico", "PBI minería metálica",
                 "empleo formal", "variación porcentual anual", "canasta familiar"),
        languages=("es",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the Lima CPI is published on the FIRST DAY of the following month -- among the "
              "fastest consumer-price prints anywhere -- which is why a BCRP meeting a week "
              "later has a genuinely current inflation number in front of it"),
    source_class(
        "pe_mef_sunat", "Ministerio de Economia y Finanzas, the Direccion General del Tesoro and "
                        "SUNAT: the BTP auction calendar, non-resident holdings, the fiscal "
                        "rule, customs statistics by product and destination",
        layer="official",
        roots=("https://www.mef.gob.pe/es/portal-de-transparencia-economica",
               "https://www.mef.gob.pe/es/?option=com_content&view=category&id=661",
               "http://www.sunat.gob.pe/estad-comExt/modulo_public/Bol_Aduanero/"),
        queries=("subasta de bonos soberanos", "tenencia de no residentes bonos soberanos",
                 "regla fiscal déficit", "marco macroeconómico multianual",
                 "exportaciones por partida arancelaria", "boletín aduanero",
                 "canon minero transferencia", "impuesto especial a la minería"),
        languages=("es",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the customs boletin is a PHYSICAL flow by product and destination, which is how "
              "the concentrate leaving Matarani is matched to the tonnes MINEM counted at the "
              "mine and to the cargo Chinese customs reported arriving"),
    source_class(
        "pe_osinergmin_produce", "Osinergmin (fuel prices, the FEPC stabilisation fund, gas), "
                                 "PRODUCE and IMARPE (the anchoveta quota, landings, biomass)",
        layer="official",
        roots=("https://www.osinergmin.gob.pe/seccion/institucional/regulacion-tarifas",
               "https://www.gob.pe/produce", "https://www.imarpe.gob.pe/imarpe/",
               "https://www.gob.pe/institucion/produce/colecciones/"),
        queries=("fondo de estabilización de precios de los combustibles", "banda de precios",
                 "precio del diésel", "cuota de pesca de anchoveta", "temporada de pesca",
                 "veda reproductiva", "desembarque de anchoveta", "biomasa crucero IMARPE",
                 "resolución ministerial cuota", "juveniles anchoveta"),
        languages=("es",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the FEPC is an administered fuel price with a published band, so a diesel shock "
              "reaches the Peruvian mine fleet on a DECREE clock rather than a market one; and "
              "the anchoveta quota is a resolucion ministerial with a number and a date"),
    source_class(
        "pe_elperuano", "El Peruano, the official gazette: the Normas Legales section where "
                        "every ley, decreto supremo, decreto de urgencia and resolucion "
                        "ministerial in this pack becomes citable", layer="official",
        roots=("https://busquedas.elperuano.pe/", "https://diariooficial.elperuano.pe/Normas",
               "https://www.gob.pe/normas-legales"),
        queries=("normas legales decreto supremo", "día no laborable Lima y Callao",
                 "estado de emergencia corredor minero", "Ley 31968 feriados",
                 "resolución ministerial cuota de anchoveta", "decreto de urgencia",
                 "retiro extraordinario AFP ley", "declaratoria de emergencia"),
        languages=("es",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE GAZETTE IS WHERE A DATE BECOMES A CITATION. Every PRESS_REPORTED row in this "
              "pack -- the blockade dates, the APEC closures, the anchoveta resolutions -- is "
              "promotable only once a busquedas.elperuano.pe number is attached to it"),
    source_class(
        "pe_sbs_smv", "Superintendencia de Banca, Seguros y AFP and the Superintendencia del "
                      "Mercado de Valores: the AFP portfolio, the offshore limit, the daily "
                      "tipo de cambio contable, issuer filings", layer="official",
        roots=("https://www.sbs.gob.pe/estadisticas-y-publicaciones",
               "https://www.sbs.gob.pe/app/pp/SISTIP_PORTAL/Paginas/Publicacion/"
               "TipoCambioPromedio.aspx", "https://www.smv.gob.pe/"),
        queries=("cartera administrada AFP", "inversión en el exterior límite operativo",
                 "retiro extraordinario de fondos", "tipo de cambio contable",
                 "hecho de importancia", "memoria anual emisor", "depósitos en moneda extranjera",
                 "dolarización del crédito"),
        languages=("es",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the AFPs' offshore limit is set by the BCRP and raised IN DATED STEPS, and the "
              "seven legislated withdrawals are dated laws: between them they are the largest "
              "involuntary cross-border flow this country produces"),
    # ---- institutional
    source_class(
        "pe_bvl_cavali", "Bolsa de Valores de Lima, CAVALI and the MILA: the daily bulletin, "
                         "index composition, foreign participation, settlement",
        layer="institutional",
        roots=("https://www.bvl.com.pe/", "https://www.bvl.com.pe/mercado/movimientos-diarios",
               "https://www.cavali.com.pe/", "https://mercadomila.com/"),
        queries=("boletín diario bolsa de valores de Lima", "S&P/BVL Perú General",
                 "rueda de bolsa cierre", "capitalización bursátil", "MILA mercado integrado",
                 "participación extranjera", "liquidación CAVALI", "índice minero"),
        languages=("es",), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="no BVL index CFD exists and the index is roughly 60% mining by weight, so the "
              "bourse adds no independent cell -- it is registered because its foreign "
              "participation and MILA cross-listing date the regional flow"),
    source_class(
        "pe_gremios", "The trade bodies: SNMPE (mining, oil and energy), Comex Peru (trade), "
                      "the Sociedad Nacional de Pesqueria, IPE, CONFIEP, the Junta Nacional del "
                      "Cafe and the regional mining chambers", layer="institutional",
        roots=("https://www.snmpe.org.pe/", "https://www.comexperu.org.pe/",
               "https://www.snp.org.pe/", "https://www.ipe.org.pe/"),
        queries=("SNMPE reporte estadístico mensual", "exportaciones mineras Comex",
                 "semanario Comex Perú", "Sociedad Nacional de Pesquería cuota",
                 "gremio minero comunicado", "Junta Nacional del Café cosecha",
                 "inversión minera proyectada", "conflictividad social gremio"),
        languages=("es",), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="SNMPE publishes a monthly statistical report that arrives BEFORE the MINEM "
              "boletin and lobbies in dated press releases when a blockade starts, which makes "
              "it the cheapest leading indicator of both halves of PE-C and PE-D"),
    source_class(
        "pe_bank_research", "Openly published bank and consultancy research: BBVA Research Peru, "
                            "Credicorp Capital, Scotiabank Peru's Reporte Semanal, Apoyo "
                            "Consultoria, Macroconsult", layer="institutional",
        roots=("https://www.bbvaresearch.com/en/countries/peru/",
               "https://www.credicorpcapital.com/", "https://scotiabankfiles.azureedge.net/"),
        queries=("proyección tasa de referencia", "reporte semanal Scotiabank Perú",
                 "perspectivas económicas Perú", "situación Perú BBVA Research",
                 "encuesta de expectativas analistas", "riesgo político mercado"),
        languages=("es", "en"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free notes; some behind registration",
        notes="the pre-meeting expectation these houses publish is the only stated consensus "
              "inside the month; it is kept as the EXPECTATION source PE-A measures a surprise "
              "against, never as a view the desk adopts"),
    # ---- academic
    source_class(
        "pe_academic", "Peruvian economics research: PUCP, Universidad del Pacifico (CIUP), "
                       "GRADE, IEP, CIES, plus the open aggregators",
        layer="academic",
        roots=("https://departamento.pucp.edu.pe/economia/publicaciones/",
               "https://www.up.edu.pe/investigacion/", "https://www.grade.org.pe/publicaciones/",
               "https://openalex.org/", "https://core.ac.uk/"),
        queries=("conflicto social y minería Perú", "maldición de los recursos naturales Perú",
                 "canon minero y gasto local", "intervención cambiaria efectividad BCRP",
                 "dolarización financiera Perú", "pass-through tipo de cambio Perú",
                 "consulta previa Ley 29785 evaluación"),
        languages=("es", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="open access / publisher terms",
        notes="the canon-minero literature is the mechanism source for PE-D: it says WHY a "
              "district next to a producing mine riots while the next district does not, which "
              "is the difference between a conflict variable and a conflict story"),
    source_class(
        "pe_geoscience", "INGEMMET, the mining cadastre, the geological survey and the "
                         "university mining schools (UNI, UNSAAC, UNSA)", layer="academic",
        roots=("https://www.ingemmet.gob.pe/", "https://geocatmin.ingemmet.gob.pe/geocatmin/",
               "https://portal.ingemmet.gob.pe/"),
        queries=("catastro minero GEOCATMIN", "concesión minera vigente",
                 "reservas y recursos minerales", "ley de cabeza mineral",
                 "estudio geológico yacimiento", "pórfido de cobre", "allpa concesión"),
        languages=("es",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="GEOCATMIN is a live, queryable cadastre: which concession is whose, where, and "
              "at what stage. It is how a project in the cartera is told apart from a press "
              "release, and how an informal-mining claim is told from a formal one"),
    # ---- practitioner
    source_class(
        "pe_practitioner", "The specialist desk and mining press: Semana Economica, Gestion's "
                           "mercados pages, Rumbo Minero, Energiminas, ProActivo, Mineria "
                           "Panamericana", layer="practitioner",
        roots=("https://semanaeconomica.com/", "https://gestion.pe/economia/mercados/",
               "https://www.rumbominero.com/", "https://energiminas.com/"),
        queries=("paralización de operaciones mina", "bloqueo corredor minero",
                 "producción de cobre cae", "tipo de cambio hoy Perú",
                 "subasta de bonos soberanos resultado", "proyecto minero puesta en marcha",
                 "precio del cobre y la bolsa de Lima", "conflicto Las Bambas"),
        languages=("es",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="Rumbo Minero and Energiminas carry the operational detail -- which unit stopped, "
              "how many days of stockpile it has, when the trucks moved -- days before it "
              "reaches the ministry's statistics, and that lag IS the edge in PE-D"),
    # ---- retail ecology
    source_class(
        "pe_retail_forums", "Peruvian retail communities: r/PERU and r/peruinversiones, the "
                            "Facebook and YouTube bolsa/forex groups in Spanish, and the street "
                            "cambista market that quotes the sol in cash",
        layer="retail_ecology",
        roots=("https://www.reddit.com/r/PERU/", "https://www.reddit.com/r/peruinversiones/",
               "https://www.youtube.com/results?search_query=bolsa+de+valores+de+lima+invertir"),
        queries=("en qué invertir Perú", "comprar dólares hoy", "cambista Jirón Ocoña",
                 "tipo de cambio paralelo", "bolsa de valores de Lima para principiantes",
                 "fondos mutuos Perú opiniones", "retiro AFP qué hacer con el dinero"),
        languages=("es",), access_label="PUBLIC_SOCIAL", credibility="FRINGE",
        predictive_state="UNTESTED", licence="platform terms; public posts only",
        notes="KEPT AT LOW WEIGHT and never a source of edge: single-name tips belong to the "
              "event lane. It is registered because the retail vocabulary around the AFP "
              "withdrawal windows and the cash-dollar counters dates the household FX episodes"),
    source_class(
        "pe_retail_brokers", "Spanish-language 'forex' and prop-firm affiliates targeting "
                             "Peruvian retail on YouTube, TikTok and Telegram, plus the local "
                             "SAB retail platforms", layer="retail_ecology",
        roots=("https://www.youtube.com/results?search_query=trading+forex+peru",
               "https://t.me/s/tradingperu"),
        queries=("trading Perú señales", "prop firm Perú", "cuenta demo forex",
                 "invertir en oro Perú", "apalancamiento broker", "estafa broker Perú"),
        languages=("es",), access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="platform terms; public posts only",
        notes="Peru has NO exchange control, so this retail base is legal and unregulated at "
              "once -- the SMV licenses the local SABs and does not reach an offshore CFD "
              "account. The XAUUSD stop clusters it advertises are a real microstructure "
              "observable and the only reason the ground is kept"),
    # ---- app ecosystem
    source_class(
        "pe_fx_apps", "The online casas de cambio -- Rextie, Kambista, TuCambista, Western -- "
                      "and the Yape/Plin instant-payment rails that settle them",
        layer="app_ecosystem",
        roots=("https://www.rextie.com/", "https://kambista.com/",
               "https://www.bcrp.gob.pe/sistema-de-pagos.html"),
        queries=("tipo de cambio Rextie hoy", "cambio de dólares online",
                 "Yape transferencia límite", "Plin interoperabilidad",
                 "casa de cambio digital comisión", "estadísticas de pagos BCRP"),
        languages=("es",), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free public quotes; app stores public",
        notes="THE ONE APP-LAYER SERIES IN THIS PACK WITH A REAL LEAD: the online casas de "
              "cambio publish a LIVE retail sol quote all day, free, while the SBS reference is "
              "a single end-of-day number. The retail spread widening ahead of a political "
              "event is a household-stress observable the interbank print never shows"),
    source_class(
        "pe_data_apps", "The public data apps and APIs a local analyst actually uses: BCRPData, "
                        "the gob.pe datasets portal, INEI's Sistema de Informacion Regional, "
                        "MINEM's BigData Mineria", layer="app_ecosystem",
        roots=("https://estadisticas.bcrp.gob.pe/estadisticas/series/api",
               "https://www.datosabiertos.gob.pe/", "https://pad.minem.gob.pe/BigData_Mineria/"),
        queries=("API BCRPData series", "datos abiertos Perú descarga",
                 "sistema de información regional INEI", "BigData minería MINEM",
                 "series estadísticas mensuales descarga"),
        languages=("es", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="BCRPData is a keyless time-series API over thousands of series, which makes Peru "
              "one of the cheapest macro grounds on this desk to keep point-in-time"),
    # ---- media
    source_class(
        "pe_media_national", "The national press and wires: Andina (the state wire), El "
                             "Comercio, Gestion, La Republica, RPP, Infobae Peru, Canal N",
        layer="media",
        roots=("https://andina.pe/agencia/seccion-economia-1.aspx", "https://gestion.pe/",
               "https://larepublica.pe/economia", "https://rpp.pe/economia"),
        queries=("BCRP mantiene la tasa de referencia", "paro en el corredor minero",
                 "Las Bambas suspende operaciones", "vacancia presidencial votación",
                 "estado de emergencia prorrogado", "exportaciones mineras récord",
                 "tipo de cambio cierra", "pesca de anchoveta suspendida"),
        languages=("es",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="Andina carries the official minute of a decree or a ministerial resolution when "
              "the institution's own page carries only the date, and Gestion's markets desk is "
              "the closest thing Lima has to a consensus tape"),
    source_class(
        "pe_indigenous_media", "The indigenous-affairs ground: Servindi, the regional Quechua "
                               "and Aymara radios, ONAMIAP, AIDESEP and the comunidad campesina "
                               "federations' own communiques", layer="media",
        roots=("https://www.servindi.org/", "https://onamiap.org/", "https://aidesep.org.pe/"),
        queries=("comunidad campesina asamblea acuerdo", "consulta previa proceso",
                 "territorio comunal minería", "ayllu resolución", "Pachamama defensa",
                 "llaqta paro", "mallku comunidad", "ch'alla ceremonia mina"),
        languages=("es", "qu", "ay"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="THIS IS WHERE A BLOCKADE IS DECIDED, and it is decided in Quechua and Aymara in a "
              "community assembly days before any Lima outlet reports it. A Spanish-only crawl "
              "of Peruvian conflict reads the reaction and never the decision"),
    source_class(
        "pe_licensed_assessments", "Licensed terminals and price reporting agencies: Bloomberg, "
                                   "Refinitiv, Fastmarkets and Argus for concentrate TC/RC, and "
                                   "the fishmeal FOB assessments", layer="media",
        roots=("https://www.fastmarkets.com/", "https://www.argusmedia.com/"),
        queries=("copper concentrate TC RC benchmark", "zinc treatment charge annual benchmark",
                 "Peru fishmeal super prime FOB", "spot TC RC assessment"),
        languages=("en",), access_label="LICENSED", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="subscription; terms forbid machine extraction",
        machine_use_allowed=False,
        notes="REGISTERED, NEVER SCRAPED. The TC/RC is the part of the copper price a Peruvian "
              "miner actually receives and the fishmeal FOB is the price leg of PE-F; both are "
              "paywalled, so those two mechanisms are measured on the EXCHANGE metal and on the "
              "SUBSTITUTE respectively, and the absence is named rather than worked around"),
    # ---- archive
    source_class(
        "pe_archive_official", "The long run: the El Peruano normas archive, BCRP memorias and "
                               "the full BCRPData history, INEI's statistical yearbooks, the "
                               "Biblioteca Nacional del Peru digital collections",
        layer="archive",
        roots=("https://busquedas.elperuano.pe/", "https://www.bcrp.gob.pe/publicaciones/"
               "memoria-anual.html", "https://bnp.gob.pe/", "https://repositorio.bcrp.gob.pe/"),
        queries=("memoria anual BCRP histórico", "normas legales archivo búsqueda",
                 "anuario estadístico INEI", "serie histórica tipo de cambio",
                 "biblioteca nacional colección digital", "boletín minero archivo"),
        languages=("es",), access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="busquedas.elperuano.pe is a full-text search over the gazette back to the 1990s, "
              "which is what turns this pack's PRESS_REPORTED blockade and closure dates into "
              "citable ones -- the single highest-value archive job in this country"),
    source_class(
        "pe_wayback", "web.archive.org snapshots of the MINEM statistics pages, the Defensoria "
                      "monthly reports and the ministry pages that overwrite in place",
        layer="archive",
        roots=("https://web.archive.org/web/*/minem.gob.pe*",
               "https://web.archive.org/web/*/defensoria.gob.pe*",
               "https://web.archive.org/web/*/bcrp.gob.pe*"),
        queries=("minem boletín estadístico archive", "defensoría reporte conflictos archive",
                 "bcrp nota semanal archive", "produce cuota anchoveta archive"),
        languages=("es", "en"), access_label="PUBLIC_ARCHIVE", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="Internet Archive terms",
        notes="MINISTRY PAGES ARE REPLACED, NOT VERSIONED: a Peruvian ministry posts the current "
              "month's PDF over the old link and the cartera de proyectos page shows TODAY's "
              "list. Without this layer the point-in-time vintage of PE-C and PE-H is whatever "
              "somebody crawled"),
    # ---- physical economy
    source_class(
        "pe_ports_logistics", "Autoridad Portuaria Nacional throughput, DP World Callao, APM "
                              "Terminals, Tisur Matarani, and the Cosco Shipping Chancay "
                              "terminal opened 2024-11-14", layer="physical_economy",
        roots=("https://www.apn.gob.pe/site/estadisticas.aspx", "https://www.tisur.com.pe/",
               "https://www.dpworldcallao.com.pe/", "https://www.cosco-chancay.com/"),
        queries=("estadísticas portuarias APN movimiento de carga",
                 "embarque de concentrados Matarani", "terminal portuario Chancay",
                 "nave recalada Callao", "granel sólido mineral", "flete y congestión portuaria",
                 "Qhapaq Ñan corredor logístico"),
        languages=("es", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="MATARANI IS THE PHYSICAL COUNTERPART OF THE BLOCKADE. Las Bambas, Antapaccay and "
              "Constancia all ship through it, so a closed corridor shows up as a missing "
              "sailing two to three weeks later -- which is how PE-D's supply claim is verified "
              "against a tonne rather than against a headline"),
    source_class(
        "pe_climate_enfen", "SENAMHI, IMARPE and the ENFEN multi-agency commission: the official "
                            "El Nino state, the coastal sea-surface anomaly, the rainfall and "
                            "the highland frost bulletins", layer="physical_economy",
        roots=("https://www.senamhi.gob.pe/", "https://www.gob.pe/institucion/imarpe/"
               "colecciones/1052-comunicados-oficiales-enfen",
               "https://www.gob.pe/enfen"),
        queries=("comunicado oficial ENFEN", "estado del sistema de alerta El Niño costero",
                 "anomalía de la temperatura superficial del mar", "pronóstico de lluvias",
                 "heladas y friaje", "El Niño impacto en la pesca",
                 "jallu pacha lluvias altiplano"),
        languages=("es",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="ENFEN'S OFFICIAL STATE IS A PUBLISHED, DATED CATEGORY, not a forecast the desk "
              "has to build: it drives the anchoveta biomass (and therefore the quota, and "
              "therefore the soymeal substitution) and it closes the northern roads. One "
              "bulletin conditions PE-F and PE-K at once"),
    source_class(
        "pe_world_metal_bodies", "USGS Mineral Commodity Summaries, the International Copper "
                                 "Study Group, the ILZSG for zinc and lead, the World Silver "
                                 "Survey and UN Comtrade", layer="physical_economy",
        roots=("https://www.usgs.gov/centers/national-minerals-information-center",
               "https://icsg.org/", "https://www.ilzsg.org/", "https://comtradeplus.un.org/"),
        queries=("USGS copper mine production by country", "ICSG copper market balance",
                 "ILZSG zinc lead supply and demand", "world silver survey mine production",
                 "Peru copper exports comtrade"),
        languages=("en",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="public domain (USGS) / body terms",
        notes="the INDEPENDENT read on whether a Peruvian disruption actually moved the world "
              "balance; USGS and ICSG are the only sources that let a national production "
              "series be turned into a SHARE OF WORLD SUPPLY, which is what a copper cell needs"),
    # ---- source graph
    source_class(
        "pe_source_graph", "Who cites whom: the Defensoria report -> Servindi and the regional "
                           "radios -> La Republica -> the wires; MINEM -> SNMPE -> Rumbo Minero; "
                           "BCRP -> the bank research -> Gestion; El Peruano -> everyone",
        layer="source_graph",
        roots=("https://www.defensoria.gob.pe/documentos/", "https://www.servindi.org/",
               "https://gestion.pe/", "https://www.snmpe.org.pe/"),
        queries=("según fuentes del sector", "de acuerdo con el reporte de la Defensoría",
                 "citando a la empresa", "fuentes cercanas a la negociación",
                 "según el boletín del MINEM", "trascendió que", "allegados a la comunidad"),
        languages=("es",), access_label="PUBLIC", credibility="UNKNOWN",
        predictive_state="UNTESTED", licence="derived from the public sources above",
        notes="'trascendio que' and 'fuentes cercanas' mark the unattributed leak that precedes "
              "a suspension announcement or a state of emergency by a day or two in this "
              "country; the graph is how a leak is told apart from a repost, and it is the only "
              "way to date a blockade's START before the company confirms it"),
)

#: ALL TEN LAYERS CARRY A REAL SOURCE FOR PERU and none is declared absent. That is a
#: MEASUREMENT, not a boast: Peru has an independent ombudsman publishing monthly, a keyless
#: central-bank API, a searchable gazette, a live mining cadastre, an open ports authority and a
#: native-language indigenous wire. The thin layer is `practitioner` (one row), because Peru's
#: sell-side is small and most of its operational detail arrives through the mining trade press.
LAYER_ABSENCES: dict[str, str] = {}


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
#: languages of the ground. Three or more for every one of the ten layers, and the conflict
#: layers carry Quechua and Aymara because that is the language the decision is taken in.
QUERY_TERRITORIES: dict[str, tuple[str, ...]] = {
    "official": ("programa monetario nota informativa BCRP", "boletín estadístico minero MINEM",
                 "reporte de conflictos sociales Defensoría del Pueblo",
                 "índice de precios al consumidor Lima Metropolitana INEI",
                 "resolución ministerial cuota de anchoveta PRODUCE",
                 "normas legales El Peruano decreto supremo"),
    "institutional": ("SNMPE reporte estadístico mensual minería",
                      "boletín diario Bolsa de Valores de Lima",
                      "Comex Perú semanario exportaciones",
                      "Sociedad Nacional de Pesquería comunicado cuota",
                      "Junta Nacional del Café estimación de cosecha"),
    "academic": ("conflicto socioambiental minería Perú investigación",
                 "canon minero y conflictividad evidencia",
                 "efectividad de la intervención cambiaria BCRP documento de trabajo",
                 "dolarización financiera y política monetaria Perú",
                 "consulta previa Ley 29785 evaluación GRADE"),
    "practitioner": ("Rumbo Minero paralización de operaciones",
                     "Energiminas bloqueo corredor minero sur",
                     "Semana Económica tipo de cambio proyección",
                     "Gestión mercados cierre de la bolsa",
                     "ProActivo producción de cobre mensual"),
    "retail_ecology": ("en qué invertir Perú foro", "comprar dólares hoy cambista",
                       "retiro AFP qué hacer con el dinero",
                       "bolsa de valores de Lima para principiantes",
                       "trading forex Perú señales grupo"),
    "app_ecosystem": ("tipo de cambio Rextie Kambista hoy", "API BCRPData series estadísticas",
                      "Yape Plin interoperabilidad estadísticas de pagos",
                      "datos abiertos Perú descarga dataset",
                      "BigData minería MINEM tablero"),
    "media": ("Las Bambas suspende operaciones Andina", "vacancia presidencial votación en vivo",
              "estado de emergencia corredor minero prorrogado",
              "Servindi comunidad campesina acuerdo asamblea",
              "ayllu llaqta paro minero", "mallku thakhi bloqueo altiplano"),
    "archive": ("busquedas El Peruano archivo decreto", "memoria anual BCRP serie histórica",
                "anuario estadístico INEI descarga",
                "defensoría reporte conflictos archivo mensual",
                "web archive minem boletín estadístico"),
    "physical_economy": ("estadísticas portuarias APN movimiento de carga concentrados",
                         "embarque de concentrados Matarani nave",
                         "terminal portuario Chancay operación Cosco",
                         "comunicado oficial ENFEN El Niño costero",
                         "USGS copper mine production Peru", "ICSG copper market balance"),
    "source_graph": ("trascendió que la empresa evalúa", "fuentes cercanas a la negociación mina",
                     "según el reporte de la Defensoría del Pueblo",
                     "de acuerdo con el boletín del MINEM",
                     "citando a dirigentes de la comunidad"),
}

# --------------------------------------------------------------------------- datasets
#: EIGHTEEN CATALOGUE ENTRIES, spread across the ten layers. Every row carries the twelve fields
#: the data-discovery swarm needs and a `how_to_fetch` a collector can act on without asking a
#: human. `pit_feasible` is the field the catalogue exists for: a series whose vintage cannot be
#: reconstructed can only ever produce NOT_PIT_SAFE cells, and saying so is the measurement.
DATASETS: tuple[dict[str, Any], ...] = (
    {"name": "BCRP tasa de referencia decisions and the Programa Monetario notas informativas",
     "source": "Banco Central de Reserva del Peru",
     "coverage": "2002 onward (inflation targeting adopted January 2002)",
     "frequency": "monthly (12 scheduled decisions a year)", "publication_lag_days": 0.0,
     "revisions": "never revised", "licence": "free, public", "history_from": "2002-01",
     "pit_feasible": True, "assets": ("USDBRL", "USDMXN", "XCUUSD", "US500"),
     "mechanism_families": ("policy_surprise", "event_reaction"),
     "how_to_fetch": "BCRPData series PN01108XM (tasa de referencia) through "
                     "estadisticas.bcrp.gob.pe/estadisticas/series/api, plus the nota "
                     "informativa PDFs at bcrp.gob.pe/politica-monetaria.html; the announcement "
                     "minute is 23:00 UTC on the decision Thursday and never moves"},
    {"name": "BCRP daily FX intervention: spot purchases, sales, and the CDR and swap balances",
     "source": "Banco Central de Reserva del Peru nota semanal",
     "coverage": "2000 onward for spot; CDR from 2010 and swaps cambiarios from 2014",
     "frequency": "daily", "publication_lag_days": 0.0,
     "revisions": "occasional same-week restatement of the daily amount",
     "licence": "free, public", "history_from": "2000-01", "pit_feasible": True,
     "assets": ("USDBRL", "USDMXN", "XCUUSD"),
     "mechanism_families": ("intervention", "policy_reaction_function"),
     "how_to_fetch": "the nota semanal cuadros at bcrp.gob.pe/estadisticas/"
                     "cuadros-de-la-nota-semanal.html plus the BCRPData daily series; published "
                     "after the Lima close, so it conditions the NEXT session"},
    {"name": "MINEM Boletin Estadistico Minero: production by mining unit and by metal",
     "source": "Ministerio de Energia y Minas", "coverage": "2000 onward",
     "frequency": "monthly", "publication_lag_days": 55.0,
     "revisions": "the prior month is restated when a unit reports late",
     "licence": "free, public", "history_from": "2000-01", "pit_feasible": False,
     "assets": ("XCUUSD", "XZNUSD", "XAGUSD", "XPBUSD", "XAUUSD"),
     "mechanism_families": ("physical_supply", "release_surprise"),
     "how_to_fetch": "the monthly PDF and XLS at minem.gob.pe/_estadistica.php?idSector=1 and "
                     "the BigData Mineria dashboard at pad.minem.gob.pe; NOT PIT-SAFE as "
                     "published because the page is overwritten -- the archive layer's crawls "
                     "are the only vintage"},
    {"name": "Defensoria del Pueblo Reporte Mensual de Conflictos Sociales",
     "source": "Defensoria del Pueblo", "coverage": "2004 onward, monthly and unbroken",
     "frequency": "monthly", "publication_lag_days": 12.0,
     "revisions": "cases are reclassified between states; the case identity is stable",
     "licence": "free, public", "history_from": "2004-04", "pit_feasible": False,
     "assets": ("XCUUSD", "XZNUSD", "XAGUSD"),
     "mechanism_families": ("physical_supply", "political_risk", "event_reaction"),
     "how_to_fetch": "the monthly PDF at gob.pe/institucion/defensoria/colecciones/"
                     "1163-reporte-de-conflictos-sociales; parse the socio-environmental mining "
                     "table by case, province and state, and JOIN it to the MINEM unit list -- "
                     "that join is what turns an ombudsman's report into a supply series"},
    {"name": "The declared blockade and mine-occupation episodes on the Corredor Vial Minero",
     "source": "this pack's BLOCKADE_EPISODES, built from company statements, the Defensoria "
               "reports and the mining trade press",
     "coverage": "2019 onward", "frequency": "irregular, dated", "publication_lag_days": 1.0,
     "revisions": "every row is PRESS_REPORTED and is rewritten when a gazette or company "
                  "statement pins the date",
     "licence": "derived from public sources", "history_from": "2019-02", "pit_feasible": True,
     "assets": ("XCUUSD", "XZNUSD"),
     "mechanism_families": ("physical_supply", "event_reaction"),
     "how_to_fetch": "`blockade_episodes()` in this module; confirm each start and end against "
                     "busquedas.elperuano.pe (the state-of-emergency decree) and the operator's "
                     "own hecho de importancia before any cell compiled on it is promoted"},
    {"name": "INEI indice de precios al consumidor de Lima Metropolitana",
     "source": "Instituto Nacional de Estadistica e Informatica",
     "coverage": "1991 onward; 2021 base", "frequency": "monthly",
     "publication_lag_days": 1.0, "revisions": "rebasing only", "licence": "free, public",
     "history_from": "1991-01", "pit_feasible": True,
     "assets": ("USDBRL", "USDMXN"), "mechanism_families": ("release_surprise",),
     "how_to_fetch": "the informe tecnico published on the FIRST DAY of the following month at "
                     "inei.gob.pe, and BCRPData series PN01270PM; one of the fastest CPI prints "
                     "in the world and the input the BCRP meeting a week later actually has"},
    {"name": "BCRP Encuesta de Expectativas Macroeconomicas",
     "source": "Banco Central de Reserva del Peru",
     "coverage": "2006 onward", "frequency": "monthly", "publication_lag_days": 10.0,
     "revisions": "never", "licence": "free, public", "history_from": "2006-01",
     "pit_feasible": True, "assets": ("USDBRL", "USDMXN"),
     "mechanism_families": ("expectations", "policy_surprise"),
     "how_to_fetch": "the monthly survey tables in the nota semanal; USE WITH CARE -- the "
                     "cut-off precedes the meeting by up to three weeks, so it is a MONTH's "
                     "expectation and not the meeting-day consensus"},
    {"name": "SUNAT customs: exports by partida arancelaria, volume, value and destination",
     "source": "SUNAT Superintendencia Nacional de Aduanas",
     "coverage": "1993 onward", "frequency": "monthly", "publication_lag_days": 30.0,
     "revisions": "minor, the following month", "licence": "free, public",
     "history_from": "1993-01", "pit_feasible": True,
     "assets": ("XCUUSD", "XZNUSD", "XAGUSD", "USDCNH"),
     "mechanism_families": ("trade_flow", "physical_supply"),
     "how_to_fetch": "the Boletin Aduanero at sunat.gob.pe/estad-comExt and the mirrored series "
                     "in BCRPData; cross-check against UN Comtrade and against Chinese customs' "
                     "reported arrivals from Peru, which is the independent read"},
    {"name": "SBS AFP cartera administrada, the offshore limit and the withdrawal laws",
     "source": "Superintendencia de Banca, Seguros y AFP, with the BCRP limite operativo",
     "coverage": "1993 onward; the seven extraordinary withdrawals from 2020",
     "frequency": "monthly", "publication_lag_days": 25.0,
     "revisions": "portfolio values are marked and restated", "licence": "free, public",
     "history_from": "1993-06", "pit_feasible": True,
     "assets": ("USDBRL", "USDMXN", "US500"),
     "mechanism_families": ("institutional_flow", "forced_flow"),
     "how_to_fetch": "sbs.gob.pe estadisticas for the portfolio and El Peruano for each "
                     "withdrawal law; the law's ENACTMENT date and its FIRST PAYMENT WINDOW are "
                     "weeks apart and the flow follows the second one"},
    {"name": "MEF non-resident holdings of soberanos and the BTP auction calendar",
     "source": "Ministerio de Economia y Finanzas, Direccion General del Tesoro",
     "coverage": "2006 onward", "frequency": "monthly (holdings), weekly (auctions)",
     "publication_lag_days": 20.0, "revisions": "rare", "licence": "free, public",
     "history_from": "2006-01", "pit_feasible": True,
     "assets": ("USDBRL", "USDMXN", "US500"),
     "mechanism_families": ("positioning", "political_risk"),
     "how_to_fetch": "the Portal de Transparencia Economica at mef.gob.pe; the non-resident "
                     "share is the fastest published read on how a political event landed"},
    {"name": "PRODUCE anchoveta quota resolutions, landings and the IMARPE biomass cruises",
     "source": "Ministerio de la Produccion and IMARPE",
     "coverage": "1990 onward for landings; the quota regime from 2009 (individual quotas)",
     "frequency": "seasonal, with daily landings inside a season",
     "publication_lag_days": 1.0, "revisions": "landings are restated as vessels report",
     "licence": "free, public", "history_from": "1990-01", "pit_feasible": True,
     "assets": ("SOYBEAN", "CORN"),
     "mechanism_families": ("physical_supply", "substitution", "event_reaction"),
     "how_to_fetch": "the resolucion ministerial in El Peruano for the quota and the PRODUCE "
                     "daily landing table inside a season; the CANCELLED seasons (2023 season "
                     "one) are the tradable rows and `cancelled_seasons()` lists them"},
    {"name": "ENFEN official El Nino state and the coastal sea-surface anomaly",
     "source": "Comision Multisectorial ENFEN (IMARPE, SENAMHI, IGP, DHN)",
     "coverage": "2012 onward for the formal alert states; the SST anomaly back to 1950",
     "frequency": "monthly, with extraordinary bulletins", "publication_lag_days": 3.0,
     "revisions": "the state is a judgement and is revised between bulletins",
     "licence": "free, public", "history_from": "2012-01", "pit_feasible": True,
     "assets": ("SOYBEAN", "CORN", "COFARA"),
     "mechanism_families": ("weather_state", "physical_supply"),
     "how_to_fetch": "gob.pe/enfen comunicados oficiales; the ALERT STATE is a published "
                     "category, not a forecast the desk has to build, and it conditions the "
                     "anchoveta quota and the northern agricultural campaign at once"},
    {"name": "APN port throughput and the Matarani, Callao and Chancay terminal statistics",
     "source": "Autoridad Portuaria Nacional and the terminal operators",
     "coverage": "2005 onward; Chancay from 2024-11",
     "frequency": "monthly", "publication_lag_days": 40.0,
     "revisions": "minor", "licence": "free, public", "history_from": "2005-01",
     "pit_feasible": False, "assets": ("XCUUSD", "XZNUSD", "USDCNH"),
     "mechanism_families": ("physical_supply", "logistics"),
     "how_to_fetch": "apn.gob.pe/site/estadisticas.aspx for national throughput and the "
                     "operators' own reports for terminal detail; NOT PIT-SAFE as published -- "
                     "the statistics page replaces the file in place"},
    {"name": "INGEMMET GEOCATMIN mining cadastre and the MINEM cartera de proyectos",
     "source": "INGEMMET and MINEM", "coverage": "the live cadastre plus the annual project list",
     "frequency": "continuous (cadastre) / annual (project portfolio)",
     "publication_lag_days": 0.0,
     "revisions": "the cadastre is a live state and keeps no history of its own",
     "licence": "free, public", "history_from": "2012-01", "pit_feasible": False,
     "assets": ("XCUUSD", "XZNUSD", "XAUUSD"),
     "mechanism_families": ("physical_supply", "investment_cycle"),
     "how_to_fetch": "geocatmin.ingemmet.gob.pe web services for the concession layer and the "
                     "annual cartera de proyectos PDF from MINEM; the cadastre has no vintage, "
                     "so a point-in-time study needs the archive layer's snapshots"},
    {"name": "CFTC Commitments of Traders for COMEX copper and silver",
     "source": "US Commodity Futures Trading Commission",
     "coverage": "1986 onward (disaggregated from 2006)", "frequency": "weekly",
     "publication_lag_days": 3.0, "revisions": "rare, corrected in place",
     "licence": "public domain (US government work)", "history_from": "2006-06",
     "pit_feasible": True, "assets": ("XCUUSD", "XAGUSD"),
     "mechanism_families": ("positioning",),
     "how_to_fetch": "cftc.gov Commitments of Traders weekly files; Tuesday snapshot published "
                     "Friday, so a Wednesday blockade is invisible for a week -- which is "
                     "itself the conditioning fact, not a defect"},
    {"name": "USGS, ICSG and ILZSG world supply balances for copper, zinc and lead",
     "source": "US Geological Survey, International Copper Study Group, ILZSG",
     "coverage": "1990 onward", "frequency": "monthly (ICSG, ILZSG) / annual (USGS)",
     "publication_lag_days": 75.0, "revisions": "heavily revised for two cycles",
     "licence": "public domain (USGS) / study-group terms", "history_from": "1990-01",
     "pit_feasible": False, "assets": ("XCUUSD", "XZNUSD", "XPBUSD"),
     "mechanism_families": ("physical_supply", "world_balance"),
     "how_to_fetch": "the USGS Mineral Commodity Summaries PDF and the ICSG and ILZSG monthly "
                     "bulletins; the ONLY way to turn a Peruvian tonnage into a share of world "
                     "supply, which is what a copper cell actually needs"},
    {"name": "Online casa de cambio retail sol quotes (Rextie, Kambista and peers)",
     "source": "the licensed online casas de cambio",
     "coverage": "2016 onward", "frequency": "intraday, continuous",
     "publication_lag_days": 0.0, "revisions": "none; a quote is a quote",
     "licence": "free public quotes; publisher terms", "history_from": "2016-01",
     "pit_feasible": True, "assets": ("USDBRL", "USDMXN"),
     "mechanism_families": ("retail_flow", "microstructure"),
     "how_to_fetch": "the public rate widgets on rextie.com and kambista.com, sampled on a "
                     "schedule; the RETAIL SPREAD is the household-stress observable and the "
                     "SBS end-of-day reference never shows it"},
    {"name": "El Peruano Normas Legales full-text archive",
     "source": "Diario Oficial El Peruano", "coverage": "the 1990s onward, full text",
     "frequency": "daily", "publication_lag_days": 0.0,
     "revisions": "none; a norm is amended by another norm", "licence": "free, public",
     "history_from": "1995-01", "pit_feasible": True,
     "assets": ("XCUUSD", "SOYBEAN", "USDBRL"),
     "mechanism_families": ("administered_event", "regime_break"),
     "how_to_fetch": "busquedas.elperuano.pe full-text search by norm type and date; this is the "
                     "dataset that turns every PRESS_REPORTED row in this pack -- the blockades, "
                     "the emergency decrees, the APEC closures, the fishing quotas -- into a "
                     "citation a cell may be promoted on"},
)

# --------------------------------------------------------------------------- actors
#: SIXTEEN ACTORS, each with all eleven fields. An actor whose FALSIFIER is blank is a story, and
#: a story is not a research object. Three of these -- the community assemblies, the ombudsman
#: and the operators of a single mine -- are the whole of the supply mechanism this pack exists
#: for, and the national champions that a two-lane violation would put on a docket (Southern
#: Copper, Buenaventura, Credicorp, Exalmar) appear HERE and nowhere else.
ACTORS: tuple[dict[str, Any], ...] = (
    {"name": "The BCRP Directorio",
     "holds": "the tasa de referencia, the encaje in soles and in dollars, and roughly US$75-80bn "
              "of net international reserves against a US$280bn economy -- one of the largest "
              "reserve-to-GDP ratios in the world",
     "forced_to": ("decide twelve times a year on a published Thursday calendar and announce at "
                   "18:00 Lima the same day",
                   "publish the Reporte de Inflacion four times a year with a projection path",
                   "publish the intervention it did, by day and by amount"),
     "when": "18:00 America/Lima (23:00 UTC) on the decision Thursday, in every month of every "
             "year -- Peru has no daylight saving, so the minute never moves",
     "information": ("the daily interbank FX flow and its own intervention book",
                     "the banking system's dollar deposit base in real time",
                     "the CPI a week before the meeting, because INEI prints on day one",
                     "the Encuesta de Expectativas it runs itself"),
     "constraints": ("a PUBLISHED numeric target -- 2% with a +/-1 point band -- which makes a "
                     "surprise measurable against a stated benchmark",
                     "a highly dollarised credit and deposit base that transmits an FX move "
                     "into balance sheets rather than only into prices",
                     "an independent board with staggered terms and a congress that has "
                     "repeatedly threatened its mandate without changing it"),
     "instruments": ("USDBRL", "USDMXN", "XCUUSD"),
     "counterparties": ("the commercial banks at the repo and CDR auctions",
                        "the AFPs, whose offshore limit it sets",
                        "the Ministry of Economy at the Treasury's deposit window",
                        "the IMF under the precautionary Flexible Credit Line"),
     "observables": ("the nota informativa and its forward language",
                     "the daily spot intervention amount", "the CDR and swap balances",
                     "the daily reserve print", "the encaje circulars between meetings"),
     "impact": "the sol's own move is administered, so the executable effect is on the regional "
               "EM legs and on the metals through the terms-of-trade channel; the SIZE of the "
               "intervention is the information, not the direction of the rate",
     "persistence": "a rate level persists a month by construction; an encaje change persists "
                    "until the next circular and is invisible to a rate-only study",
     "falsifier": "the same window on the four nearest non-meeting Thursdays; an effect that "
                  "survives there is a Thursday effect wearing the BCRP's hat, and a move that "
                  "matches an FOMC day is a dollar event",
     "notes": "THE PUBLISHED INTERVENTION IS THE ASSET. No other pack in this command can "
              "condition on what the central bank actually did in the spot market that day"},
    {"name": "The BCRP FX desk and its derivatives book",
     "holds": "the mesa de negociacion, the CDR programme and the swap cambiario book",
     "forced_to": ("publish every spot purchase and sale by day and amount",
                   "auction CDRs and swaps on demand and publish the results",
                   "keep the sol's realised volatility low enough that a dollarised balance "
                   "sheet does not break"),
     "when": "inside the 14:00-18:30 UTC interbank window; the print lands after the close",
     "information": ("the banks' end-of-day FX positions",
                     "the AFPs' offshore rebalancing intentions",
                     "the exporters' forward selling before it reaches spot"),
     "constraints": ("no band, no announced programme and no pre-commitment -- the opposite of "
                     "the Chilean case, which is why the two are each other's control",
                     "a reserve stock large enough that a market cannot exhaust it, which "
                     "removes the speculative-attack mechanism other EM packs have",
                     "a dollarised deposit base that makes a large depreciation a solvency "
                     "question rather than a competitiveness one"),
     "instruments": ("USDBRL", "USDMXN"),
     "counterparties": ("the commercial banks", "the AFPs and the mutual funds",
                        "the mining exporters selling dollars against a local cost base"),
     "observables": ("the daily intervention amount", "the CDR and swap outstanding balances",
                     "the reserve series", "the retail casa de cambio spread"),
     "impact": "the sol's realised volatility is a POLICY OUTPUT, which makes Peru the cleanest "
               "available control for 'does political risk move a currency' -- the politics are "
               "the region's most violent and the currency is its calmest",
     "persistence": "the intervention regime has persisted across every government since 2002",
     "falsifier": "the intervention state carries no information about the next week's regional "
                  "EM path beyond what USDBRL and USDMXN already carry, measured with the same "
                  "state built on a block-shuffled intervention series",
     "notes": "the state variable of PE-B; it is PUBLISHED, which is rare enough to be the "
              "reason this domain exists"},
    {"name": "MINEM and the Direccion General de Mineria",
     "holds": "the monthly production count by mining unit, the concession-to-construction "
              "pipeline and the environmental permitting queue",
     "forced_to": ("publish the Boletin Estadistico Minero every month with production by unit, "
                   "by company, by metal and by region",
                   "publish the cartera de proyectos annually",
                   "report the monthly mining investment figure"),
     "when": "late in the month, for the month two months back",
     "information": ("each unit's production before it is published",
                     "which permits are about to be granted",
                     "which operations have declared force majeure"),
     "constraints": ("units report to the ministry on their own schedule, so a late reporter "
                     "moves a national total two months later",
                     "the ministry counts CONTAINED metal in concentrate, not refined metal, "
                     "which is a different number from the one the exchange prices"),
     "instruments": ("XCUUSD", "XZNUSD", "XAGUSD", "XPBUSD", "XAUUSD"),
     "counterparties": ("the operators", "SUNAT for the royalty base",
                        "the regional governments that receive the canon"),
     "observables": ("the monthly boletin by unit", "the investment series",
                     "the cartera de proyectos and its slippage"),
     "impact": "a mine-level production miss is a world-supply number for copper, zinc and "
               "silver, and the boletin is where it becomes countable",
     "persistence": "monthly and cumulative; a lost month shows for a year in the annual total",
     "falsifier": "unit-level production misses carry no information about the metal beyond "
                  "what the ICSG world balance already carries, tested against the same months "
                  "in units that did not miss",
     "notes": "PRODUCTION BY MINE is the granularity almost no other country publishes"},
    {"name": "The Defensoria del Pueblo",
     "holds": "the national register of social conflicts: every active and latent case, by "
              "province, actor, subject and state",
     "forced_to": ("publish a monthly report under its constitutional mandate",
                   "classify each case as dialogue, escalation or violence",
                   "name the parties and the dates of each dialogue table"),
     "when": "mid-month, for the prior month",
     "information": ("the alerta temprana before a conflict escalates",
                     "which dialogue tables have collapsed",
                     "which communities have voted a measure of force"),
     "constraints": ("it is an OMBUDSMAN, not a police or mining authority: it reports and "
                     "mediates and cannot compel",
                     "a case's state is a judgement, so the series has a classification "
                     "boundary that must be respected in any study"),
     "instruments": ("XCUUSD", "XZNUSD", "XAGUSD"),
     "counterparties": ("the communities", "the mining operators", "the Consejo de Ministros",
                        "the regional governments"),
     "observables": ("the monthly case count by state and province",
                     "the socio-environmental mining subset",
                     "the alerta temprana notices"),
     "impact": "an escalating case in Apurimac, Cusco or Moquegua is the leading half of a "
               "physical copper-supply interruption; the count itself is the conditioning state",
     "persistence": "cases persist for years and escalate in weeks; the STATE change is the "
                    "event, never the level",
     "falsifier": "the escalation state carries no information about copper beyond what the "
                  "company's own production guidance already carries, tested on months with "
                  "escalation in NON-mining conflicts as the placebo",
     "notes": "A CONSTITUTIONALLY INDEPENDENT BODY PUBLISHES A SUPPLY SERIES MONTHLY. That "
              "sentence is the reason this pack exists"},
    {"name": "The comunidades campesinas of the Corredor Vial Minero del Sur",
     "holds": "the land the concentrate road crosses -- Chumbivilcas, Cotabambas, Espinar, "
              "Velille, Ccapacmarca -- and the legal standing to negotiate its use",
     "forced_to": ("decide in a comunal assembly, in Quechua, with a quorum and an acta",
                   "renegotiate road-use and compensation agreements on their own expiry dates",
                   "be consulted under Ley 29785 before a new project affecting them proceeds"),
     "when": "assemblies cluster after the harvest and around the Carnaval and Inti Raymi "
             "calendars; a blockade typically begins within days of a failed dialogue table",
     "information": ("their own assembly's decision days before any Lima outlet reports it",
                     "the compensation payments actually received",
                     "the truck counts on the road"),
     "constraints": ("the road is the ONLY route from Las Bambas to Matarani, which makes a "
                     "blockade a total interruption rather than a partial one",
                     "the canon minero reaches the REGION and not necessarily the district the "
                     "road crosses, which is the structural grievance",
                     "an acta commits the community and is enforceable in its own eyes"),
     "instruments": ("XCUUSD", "XZNUSD"),
     "counterparties": ("MMG Las Bambas and the other corridor operators",
                        "the Presidencia del Consejo de Ministros' dialogue tables",
                        "the transport contractors"),
     "observables": ("the assembly actas and the federation communiques",
                     "the Defensoria case state", "Servindi and the regional radios",
                     "the truck and sailing counts at Matarani"),
     "impact": "a closed corridor removes roughly 2% of world copper supply from the market "
               "within weeks of the stockpile running down",
     "persistence": "episodes have run from two weeks to fifty days; the grievance persists "
                    "across every episode and the agreements expire on a schedule",
     "falsifier": "blockade windows show no copper effect once Chilean supply events, Chinese "
                  "demand prints and the exchange inventory state are controlled for",
     "notes": "THE DECISION IS TAKEN IN QUECHUA AND AYMARA. A Spanish-only crawl reads the "
              "reaction and never the decision, which is the whole native-language argument"},
    {"name": "MMG Las Bambas as a single-mine swing supplier",
     "holds": "a copper operation producing roughly 250-300 kt a year -- about 2% of world mine "
              "supply -- with ONE road to the sea",
     "forced_to": ("truck every tonne of concentrate 450 km down the Corredor Minero",
                   "disclose a suspension as a material event to its listed parent",
                   "negotiate road-use agreements with every community the route crosses"),
     "when": "continuous; suspensions are announced within days of the stockpile limit",
     "information": ("its own stockpile cover in days",
                     "the state of every community negotiation",
                     "the trucking contractor's movement counts"),
     "constraints": ("NO ALTERNATIVE ROUTE: the mine has no rail, no pipeline and no second road",
                     "a finite concentrate stockpile at the mine and at Matarani",
                     "Chinese ownership, which makes the dispute a diplomatic object as well as "
                     "a commercial one"),
     "instruments": ("XCUUSD",),
     "counterparties": ("the corridor communities", "Tisur Matarani", "the Chinese smelters",
                        "the Peruvian state's dialogue tables"),
     "observables": ("the suspension and restart announcements",
                     "the MINEM unit-level production line",
                     "the Matarani sailing schedule", "the trucking counts"),
     "impact": "a fifty-day halt is roughly 40 kt of contained copper withheld, which is a real "
               "share of the visible market balance in that quarter",
     "persistence": "the halt lasts as long as the road is closed plus the restart ramp",
     "falsifier": "announced suspensions produce no abnormal copper return once the LME "
                  "inventory state and the Chinese import print are controlled for",
     "notes": "AN ACTOR, NEVER AN INSTRUMENT. Its listed parent is a single name and the "
              "two-lane order (2026-09-06) forbids hunting it statistically"},
    {"name": "Southern Copper's Peruvian division (Cuajone and Toquepala)",
     "holds": "two large open pits in Moquegua and Tacna with their own rail line, smelter and "
              "port at Ilo -- the one Peruvian copper complex that does NOT depend on the "
              "southern corridor",
     "forced_to": ("draw water under a permit the highland communities contest",
                   "run the Ilo smelter, which is a domestic refining constraint",
                   "disclose interruptions to its listed parent"),
     "when": "continuous; the 2022 Cuajone interruption ran roughly 55 days from late February",
     "information": ("its own water balance and reservoir state",
                     "the community negotiations at Tumilaca and Torata"),
     "constraints": ("WATER, not road: the 2022 halt came when a community seized the water "
                     "supply and the rail, which is a DIFFERENT mechanism from the corridor's "
                     "and therefore the corridor's natural control",
                     "a smelter that must be kept hot, which raises the cost of a short stop"),
     "instruments": ("XCUUSD", "XAGUSD"),
     "counterparties": ("the Moquegua and Tacna communities", "the ANA water authority",
                        "the Ilo port and the Asian smelters"),
     "observables": ("the halt and restart announcements", "the MINEM unit lines for both pits",
                     "the ANA water-permit record", "Ilo sailings"),
     "impact": "a Cuajone stop is a second, independent Peruvian copper interruption that lets a "
               "study separate 'a Peruvian shock' from 'a corridor shock'",
     "persistence": "the water grievance is structural and recurs in drought years",
     "falsifier": "the two mechanisms are indistinguishable in the copper tape, which would mean "
                  "the market prices 'Peru' rather than the tonnes",
     "notes": "AN ACTOR, NEVER AN INSTRUMENT (two-lane order)"},
    {"name": "Antamina",
     "holds": "the largest copper-zinc polymetallic operation in the country and the single "
              "largest zinc unit in the Americas, in Ancash, shipping through its own "
              "concentrate pipeline to Punta Lobitos",
     "forced_to": ("ship through a slurry PIPELINE rather than a road",
                   "publish production through the MINEM unit lines",
                   "renegotiate community agreements in the Callejon de Huaylas"),
     "when": "continuous; the pipeline removes the trucking exposure the corridor mines have",
     "information": ("its own grade schedule, which swings the copper-to-zinc mix year to year",
                     "the pipeline's throughput"),
     "constraints": ("a POLYMETALLIC ore body: the copper and the zinc come out together, so a "
                     "disruption here is a joint shock and cannot be attributed to one metal",
                     "a mine plan that alternates copper-rich and zinc-rich phases"),
     "instruments": ("XZNUSD", "XCUUSD", "XAGUSD"),
     "counterparties": ("the Ancash communities", "the Chinese and Korean smelters",
                        "the Punta Lobitos port"),
     "observables": ("the MINEM unit lines for copper, zinc and silver",
                     "the pipeline and port throughput", "the Ancash conflict cases"),
     "impact": "the joint copper-zinc shock is the cleanest available test of whether the market "
               "prices a METAL or a COUNTRY: a corridor blockade hits copper alone, an Antamina "
               "event hits both",
     "persistence": "grade phases persist for quarters and are disclosed in advance",
     "falsifier": "copper and zinc responses to Antamina events are indistinguishable from their "
                  "responses to any other supply headline of the same size",
     "notes": "AN ACTOR, NEVER AN INSTRUMENT. The joint-shock property is why it is here"},
    {"name": "The Ministerio de Economia y Finanzas and the Direccion General del Tesoro",
     "holds": "the soberanos programme, the global bond curve, the fiscal rule and the canon "
              "minero transfer formula",
     "forced_to": ("auction BTPs on a published calendar",
                   "transfer the canon to the producing regions on a statutory formula",
                   "publish the Marco Macroeconomico Multianual and the fiscal outturn"),
     "when": "weekly auctions; the canon transfer is computed annually on the prior year's "
             "mining income tax",
     "information": ("the tax take from the mining sector before it is published",
                     "the auction book before the result", "the cash position"),
     "constraints": ("a fiscal rule that has been suspended and reinstated by decree",
                     "the CANON FORMULA: half the mining income tax goes back to the producing "
                     "region, which makes a metal price a LOCAL FISCAL variable and is the "
                     "structural link between PE-C and PE-D",
                     "the highest non-resident ownership of local debt in the region"),
     "instruments": ("USDBRL", "USDMXN", "US500"),
     "counterparties": ("the AFPs and the banks at the auctions",
                        "the foreign holders of soberanos", "the regional governments"),
     "observables": ("the auction results and the non-resident holding share",
                     "the monthly fiscal outturn", "the canon transfer amounts by region"),
     "impact": "the curve is the fastest domestic read on a political event; the canon is the "
               "slow channel through which a copper price becomes a conflict variable",
     "persistence": "the canon effect persists a full year by construction, because it is "
                    "computed on the PRIOR year's tax",
     "falsifier": "canon transfer size carries no information about the following year's "
                  "conflict count in the receiving region, controlling for the mine's own "
                  "production and for the national conflict level",
     "notes": "the canon is the mechanism that makes a metal price a political variable here"},
    {"name": "The AFPs and the Congress that legislates their withdrawals",
     "holds": "the private pension system's portfolio, a large share of it invested offshore "
              "under a limit the BCRP sets",
     "forced_to": ("liquidate assets to fund each legislated extraordinary withdrawal",
                   "stay within the offshore limit, and buy offshore when it is raised",
                   "publish the portfolio monthly to the SBS"),
     "when": "each withdrawal law has an enactment date and a LATER payment window; the flow "
             "follows the second",
     "information": ("its own redemption queue", "the composition of what must be sold"),
     "constraints": ("SEVEN legislated withdrawals since 2020 -- a political instrument, not a "
                     "market decision, and therefore exogenous to the asset prices it moves",
                     "a limit set by the central bank and raised in dated steps",
                     "a shrinking asset base that makes each successive withdrawal a larger "
                     "share of the remainder"),
     "instruments": ("USDBRL", "USDMXN", "US500"),
     "counterparties": ("the members withdrawing", "the offshore managers being redeemed",
                        "the BCRP, which has provided FX to smooth the unwinds"),
     "observables": ("the withdrawal laws in El Peruano", "the SBS monthly portfolio",
                     "the offshore share against the limit", "the BCRP's matching operations"),
     "impact": "the largest involuntary cross-border flow the country produces, with a dated "
               "start and a known direction -- the Peruvian sibling of Chile's multifondo switch",
     "persistence": "each episode runs weeks; the structural effect is permanent",
     "falsifier": "withdrawal payment windows show no abnormal move in the regional EM legs once "
                  "the global risk state and the BCRP's own operations are controlled for",
     "notes": "the Chilean pack owns the multifondo SWITCH; this pack owns the legislated "
              "WITHDRAWAL, and the two are different mechanisms with a shared asset class"},
    {"name": "IMARPE and the Ministerio de la Produccion",
     "holds": "the anchoveta biomass estimate and the statutory power to open, size or cancel a "
              "season",
     "forced_to": ("run the biomass cruise before each season",
                   "publish a resolucion ministerial setting the quota",
                   "close a season when the juvenile share exceeds the threshold"),
     "when": "the first season opens in the second half of April, the second in November; the "
             "decision follows the cruise by days",
     "information": ("the cruise result before the quota is published",
                     "the daily juvenile share inside a season",
                     "the ENFEN state before it is formally declared"),
     "constraints": ("a JUVENILE RULE that can close a season early regardless of biomass",
                     "El Nino, which moves the stock deeper and colder and has forced outright "
                     "cancellation",
                     "an individual-quota regime since 2009 that removed the race to fish and "
                     "changed the intra-season landing profile permanently"),
     "instruments": ("SOYBEAN", "CORN"),
     "counterparties": ("the fishing fleet and the fishmeal plants",
                        "the Chinese aquaculture buyers who take most of the meal"),
     "observables": ("the resolucion ministerial", "the daily landings against quota",
                     "the ENFEN bulletin", "the cruise reports"),
     "impact": "a cancelled season removes the world's largest single source of fishmeal, and "
               "the ration substitutes toward soymeal -- an executable cross-commodity effect",
     "persistence": "a season is three months; a cancellation is a one-off shock with a "
                    "substitution that persists through the feeding cycle",
     "falsifier": "quota cancellations show no abnormal soybean or corn move once the USDA "
                  "supply-demand cycle and the South American weather state are controlled for",
     "notes": "the price leg (fishmeal FOB) is LICENSED and unreadable, so this pack measures "
              "the SUBSTITUTE and says so"},
    {"name": "The fishmeal exporters and the fleet",
     "holds": "individual vessel quotas, plant capacity on the north-central coast and the "
               "export book to Chinese aquaculture",
     "forced_to": ("fish inside the season window and stop at the quota",
                   "sell forward against a quota they may not fill",
                   "shut plants when a season is cancelled"),
     "when": "inside the declared seasons only",
     "information": ("the daily catch rate and the juvenile share before PRODUCE publishes it",
                     "the Chinese buying interest"),
     "constraints": ("the quota is a hard cap and the season is a hard window",
                     "plants are fixed on the coast and cannot follow the stock"),
     "instruments": ("SOYBEAN", "CORN"),
     "counterparties": ("the Chinese and Japanese feed buyers", "PRODUCE", "the banks financing "
                        "the campaign"),
     "observables": ("landings against quota", "export volumes in the SUNAT boletin",
                     "plant utilisation in company disclosures"),
     "impact": "the physical fishmeal tonnage that does or does not reach the feed ration",
     "persistence": "one season",
     "falsifier": "export tonnage carries no information about the soymeal complex beyond what "
                  "the quota announcement already carried",
     "notes": "AN ACTOR, NEVER AN INSTRUMENT: the listed processors are single names"},
    {"name": "The port operators: DP World and APM at Callao, Tisur at Matarani, Cosco at "
             "Chancay",
     "holds": "the physical export gate for every tonne of Peruvian concentrate and the new "
              "deep-water Pacific terminal at Chancay",
     "forced_to": ("publish throughput to the APN",
                   "berth ships on a published schedule",
                   "operate through the national holiday calendar"),
     "when": "continuous; APN publishes monthly",
     "information": ("the berthing queue and the stockpile at the terminal",
                     "the sailings that did not happen"),
     "constraints": ("Matarani is the corridor's ONLY outlet, so a blockade empties it",
                     "Chancay opened 2024-11-14 and changes the Asia leg's transit time, which "
                     "is a DATED regime break in the freight half of every copper cell"),
     "instruments": ("XCUUSD", "XZNUSD", "USDCNH"),
     "counterparties": ("the miners", "the shipping lines", "the Chinese smelters"),
     "observables": ("APN monthly throughput", "terminal reports", "the sailing schedule"),
     "impact": "the port is where a blockade becomes a missing tonne, two to three weeks after "
               "the road closed -- which is how the supply claim is verified against physics",
     "persistence": "a missed sailing is made up within a quarter unless the mine also stopped",
     "falsifier": "blockade windows show no subsequent shortfall in Matarani concentrate "
                  "throughput, which would mean the stockpiles absorbed the whole event",
     "notes": "CHANCAY IS THE DATED CHANGE: the 2024-11-14 opening is the single most important "
              "physical regime break in this pack and the direct interaction with the `cn` pack"},
    {"name": "SUNAT customs",
     "holds": "the declared export record by partida, volume, value and destination, and the "
              "mining tax base",
     "forced_to": ("publish the customs boletin monthly",
                   "assess the royalty and the impuesto especial on declared value"),
     "when": "monthly, about thirty days after the month",
     "information": ("the declarations before they are aggregated",
                     "the transfer-pricing adjustments on concentrate sales"),
     "constraints": ("declared value uses a PROVISIONAL price that is later settled, so the "
                     "value series is revised while the VOLUME series is not",
                     "concentrate is declared as gross weight with an assay, not as metal"),
     "instruments": ("XCUUSD", "XZNUSD", "USDCNH"),
     "counterparties": ("the exporters", "the MEF", "Chinese customs on the other side"),
     "observables": ("the monthly boletin", "volume and value by destination",
                     "the mirror statistics from China"),
     "impact": "the independent physical read: a tonne that left Peru must arrive somewhere, and "
               "the mirror comparison is how a production claim is audited",
     "persistence": "monthly; the volume series is the reliable half",
     "falsifier": "Peruvian declared export volumes and Chinese declared imports from Peru "
                  "diverge systematically, which would mean neither is a usable physical series",
     "notes": "VOLUME NOT VALUE: provisional pricing makes the value line a price series in "
              "disguise, and a study that uses it is measuring the metal twice"},
    {"name": "Congress, the presidency and the vacancia mechanism",
     "holds": "the power to remove a president by a vote on 'permanent moral incapacity', and it "
              "has used or attempted it repeatedly since 2017",
     "forced_to": ("vote in public with a recorded count",
                   "publish every law and decree in El Peruano the next morning"),
     "when": "vacancia motions are debated and voted within days of being admitted; the "
             "2022-12-07 sequence ran from about 11:40 to the evening of the same day",
     "information": ("the vote count before the vote", "the cabinet's position"),
     "constraints": ("a fragmented chamber with no stable majority",
                     "a constitutional clause whose threshold is a political judgement",
                     "a succession rule that puts the vice-president in office immediately, "
                     "which is why Peru changes presidents without changing institutions"),
     "instruments": ("USDBRL", "USDMXN", "XCUUSD", "US500"),
     "counterparties": ("the executive", "the regional movements", "the armed forces at the "
                        "moment of a succession"),
     "observables": ("the admitted motion and the scheduled vote",
                     "the recorded count", "the El Peruano publication the next morning",
                     "the soberanos curve and the retail dollar quote inside the hour"),
     "impact": "the sol barely moves because the BCRP holds it; the CURVE and the equity move, "
               "and the metals move only when the succession threatens the mining regime",
     "persistence": "hours to days for the price, years for the investment cycle",
     "falsifier": "vacancia and succession timestamps show no abnormal move in the regional EM "
                  "legs or in copper once the global risk state is controlled for -- which, "
                  "given how much the BCRP absorbs, is a live possibility and the honest null",
     "notes": "THE DATED-EVENT SERIES IS IN POLITICAL_EVENTS, every row PRESS_REPORTED"},
    {"name": "The informal and artisanal gold economy (Madre de Dios and the REINFO register)",
     "holds": "a gold output large enough to matter in the national export line and almost "
              "entirely outside the formal mining statistics",
     "forced_to": ("register under REINFO to sell legally, on a deadline Congress keeps "
                   "extending by law",
                   "sell through licensed buyers whose exports appear in the customs record"),
     "when": "continuous; the REINFO extension is a dated legislative act each time",
     "information": ("the real output, which nobody measures",
                     "the buying price at the informal counters"),
     "constraints": ("an output that is UNMEASURED by construction, so the formal production "
                     "series understates the country's gold",
                     "a legal status that changes by decree and by extension law",
                     "enforcement operations that are dated and publicised"),
     "instruments": ("XAUUSD",),
     "counterparties": ("the licensed exporters", "the refiners abroad",
                        "the enforcement operations"),
     "observables": ("the REINFO register count and its extension laws",
                     "gold export volume against declared formal production",
                     "the enforcement operations in the press"),
     "impact": "a weak XAUUSD edge and a strong measurement warning: Peru's gold export line "
               "exceeds its counted mine production, and the gap is the informal sector",
     "persistence": "structural; the extensions have run for a decade",
     "falsifier": "the export-minus-production gap carries no information about anything "
                  "tradable, which would make this an accounting fact rather than a mechanism",
     "notes": "DECLARED WEAK ON PURPOSE. It is carried because it explains why the MINEM gold "
              "series and the customs gold series disagree, which a careless cell would read "
              "as a data error"},
)

# --------------------------------------------------------------------------- domains
#: THIRTEEN DOMAINS. Each names its research objects, the STATES it conditions on (these are the
#: `condition` half of every cell `cells()` mints), the executable instruments it may touch and
#: at least two negative controls -- without which an effect cannot be told apart from the
#: desk's own sampling.
DOMAINS: tuple[dict[str, Any], ...] = (
    {"id": "PE-A", "title": "The monthly BCRP decision and the published inflation target",
     "objects": ("the twelve scheduled tasa de referencia decisions a year",
                 "the Reporte de Inflacion projection revision, four times a year",
                 "the encaje circulars that move policy BETWEEN meetings",
                 "the Encuesta de Expectativas as the stated consensus"),
     "conditions": ("the era: the 0.25% pandemic floor, the 2021-2023 hiking cycle to 7.75%, "
                    "the easing since 2023-09",
                    "whether inflation sat inside the published 1-3% tolerance band",
                    "whether an encaje change landed in the same month"),
     "instruments": ("USDBRL", "USDMXN", "XCUUSD", "US500"),
     "controls": ("the same 23:00 UTC window on the four nearest NON-meeting Thursdays",
                  "the same window on FOMC decision days, separating 'the dollar moved' from "
                  "'the BCRP decided'",
                  "a matched-weekday placebo on the regional EM legs"),
     "notes": "the target is PUBLISHED and NUMERIC (2% +/-1), unlike Morocco's, so a surprise "
              "here has a stated benchmark; the encaje is a second instrument a rate-only study "
              "never sees"},
    {"id": "PE-B", "title": "The BCRP's PUBLISHED intervention and the sol's administered "
                            "volatility",
     "objects": ("the daily spot purchase and sale amounts",
                 "the CDR and swap cambiario outstanding balances",
                 "the reserve series against the intervention flow",
                 "the retail casa de cambio spread as the household-stress leg"),
     "conditions": ("the intervention-intensity bucket (no print, small, large)",
                    "whether the bank used SPOT or the DERIVATIVES book that day",
                    "the global risk state, read off US500 and the dollar",
                    "whether a political event fell in the same week"),
     "instruments": ("USDBRL", "USDMXN", "XCUUSD", "US500"),
     "controls": ("the same state built on a BLOCK-SHUFFLED intervention series, which is the "
                  "null for a state variable",
                  "the Chilean and Colombian pesos over the same days -- the neighbours with a "
                  "different intervention regime, separating 'Andes' from 'Peru'",
                  "days with a large regional EM move and NO Peruvian intervention"),
     "notes": "PEN is absent from the broker, so this domain is a CONDITIONER: it says when the "
              "regional legs should be read as carrying Peru and when they should not"},
    {"id": "PE-C", "title": "MINEM production by mine and by metal",
     "objects": ("the monthly Boletin Estadistico Minero unit lines",
                 "Antamina's copper-to-zinc grade phase",
                 "the national totals against the ICSG and ILZSG world balances",
                 "the cartera de proyectos and its slippage"),
     "conditions": ("the metal (copper, zinc, silver, lead, gold), each a separate cell",
                    "whether the month contained a declared blockade episode",
                    "the grade phase at the polymetallic units",
                    "the ENFEN state, which closes highland roads in a wet year"),
     "instruments": ("XCUUSD", "XZNUSD", "XAGUSD", "XPBUSD", "XAUUSD", "XNIUSD"),
     "controls": ("the SAME month in Chilean copper production (the `cl` pack's series), "
                  "separating 'Andean supply' from 'Peruvian supply'",
                  "units in the same metal that did NOT report a disruption",
                  "a randomised-month null on the unit-level series"),
     "notes": "PUBLICATION IS 55 DAYS LATE, which bounds this domain to a slow conditioner; the "
              "fast half of the same mechanism is PE-D. XNIUSD IS THE PLACEBO LEG AND IS IN THE "
              "INSTRUMENT TUPLE ON PURPOSE: Peru mines no nickel, so a Peruvian production "
              "condition that moves nickel is measuring the base-metal complex and not this "
              "country, and the cells that say so are worth testing"},
    {"id": "PE-D", "title": "Social conflict as a physical copper-supply series",
     "objects": ("the Defensoria monthly case count by state and province",
                 "the declared blockade and mine-occupation episodes",
                 "the Matarani sailing shortfall two to three weeks later",
                 "the operators' own suspension and restart announcements"),
     "conditions": ("whether the day falls inside a declared blockade (`is_blockade_day`)",
                    "the episode's site: the southern corridor, the mine itself, or a water "
                    "dispute at a different complex",
                    "the conflict's Defensoria state (dialogue, escalation, violence)",
                    "the LME inventory state when the episode began"),
     "instruments": ("XCUUSD", "XZNUSD", "XAGUSD", "USDBRL"),
     "controls": ("the same windows in Chile, where the supply risk is a LABOUR calendar and "
                  "not a road (the `cl` pack owns that series)",
                  "escalating NON-mining conflicts in the same months, as the placebo that "
                  "separates 'Peru is unstable' from 'the road is closed'",
                  "matched windows with an equivalent Chinese demand print and no Peruvian "
                  "event"),
     "notes": "THE PACK'S REASON TO EXIST. A published, dated, lawful supply-interruption series "
              "on a liquid metal. Every episode row is PRESS_REPORTED and may generate "
              "hypotheses; none may be promoted until an El Peruano or company citation is "
              "attached to its start and end"},
    {"id": "PE-E", "title": "Political instability as a dated event series",
     "objects": ("the vacancia motions and votes", "the 2019-09-30 dissolution of Congress",
                 "the 2022-12-07 self-coup, vacancia and arrest inside one afternoon",
                 "the state-of-emergency decrees and their prorogations"),
     "conditions": ("the event class: motion, vote, succession, dissolution, self-coup",
                    "whether the southern corridor closed in the same window",
                    "the non-resident share of soberanos at the time"),
     "instruments": ("USDBRL", "USDMXN", "XCUUSD", "US500"),
     "controls": ("Brazilian and Colombian political events in the same months",
                  "the same windows with an equivalent global risk move and no Peruvian event",
                  "a randomised-date null over the same calendar"),
     "notes": "THE HONEST NULL IS LIVE HERE: the BCRP absorbs so much that Peru may be the "
              "country where politics genuinely does not move the currency, and that finding "
              "would be worth more than a weak positive"},
    {"id": "PE-F", "title": "The anchoveta quota and the fishmeal-to-soymeal substitution",
     "objects": ("the resolucion ministerial that opens, sizes or cancels a season",
                 "the daily landings against quota",
                 "the IMARPE biomass cruise and the juvenile rule",
                 "the ENFEN official El Nino state"),
     "conditions": ("season open, season closed, or season CANCELLED",
                    "the ENFEN alert state at the decision",
                    "the quota size against the prior season",
                    "whether the juvenile rule closed the season early"),
     "instruments": ("SOYBEAN", "CORN", "COFARA"),
     "controls": ("the same calendar windows in years with a normal season",
                  "the USDA supply-demand report dates, separating 'the ration substituted' "
                  "from 'the US crop changed'",
                  "South American weather episodes with no Peruvian fishery event"),
     "notes": "the PRICE leg (fishmeal FOB) is LICENSED and unreadable, so the claim is made on "
              "the SUBSTITUTE and says so on its face"},
    {"id": "PE-G", "title": "The ports, the corridor and the Chancay regime break",
     "objects": ("APN monthly throughput at Callao, Matarani and Ilo",
                 "the Chancay terminal from its 2024-11-14 opening",
                 "the sailing schedule against the blockade calendar",
                 "the freight and transit time on the Asia leg"),
     "conditions": ("before or after 2024-11-14 (the Chancay break)",
                    "whether the month contained a declared blockade",
                    "the destination mix, China against the rest"),
     "instruments": ("XCUUSD", "XZNUSD", "USDCNH", "US500"),
     "controls": ("Chilean port throughput over the same months",
                  "the same months in the prior year, before Chancay existed",
                  "months with a shipping-rate shock and no Peruvian event"),
     "notes": "THE DIRECT `cn` INTERACTION: a Cosco-operated deep-water terminal with a direct "
              "Shanghai service changes the Pacific copper leg's transit time on a DATED day"},
    {"id": "PE-H", "title": "The mining fiscal regime: canon, royalty and the investment cycle",
     "objects": ("the canon minero transfer by region, computed on the prior year's tax",
                 "the impuesto especial and the gravamen especial",
                 "the stability contracts and their expiry",
                 "MINEM monthly mining investment and the permitting queue"),
     "conditions": ("the canon year (a high-price year funds the next year's transfers)",
                    "whether the receiving region has an active conflict case",
                    "the stage of the permitting queue at the affected project"),
     "instruments": ("XCUUSD", "XZNUSD", "USDBRL"),
     "controls": ("regions receiving canon with NO producing mine of their own",
                  "the same years in Chile's very different royalty regime",
                  "a randomised-region null on the transfer series"),
     "notes": "THE CANON IS THE STRUCTURAL LINK between the metal price and the conflict count, "
              "and it runs with a ONE-YEAR LAG by construction"},
    {"id": "PE-I", "title": "Energy: Camisea, the FEPC fuel band and the mine fleet's diesel",
     "objects": ("the Osinergmin FEPC band and its activations",
                 "the domestic diesel price against import parity",
                 "the Camisea domestic price and the Melchorita export train",
                 "the Talara refinery's restart and its cost overruns"),
     "conditions": ("whether the FEPC band was active in the month",
                    "the crude level relative to the band's trigger",
                    "whether a fuel-price protest was under way"),
     "instruments": ("XTIUSD", "XCUUSD", "USDBRL"),
     "controls": ("Chilean and Colombian fuel-price regimes over the same months",
                  "months with an equivalent crude move and no band activation",
                  "a matched-weekday placebo on the crude leg"),
     "notes": "an ADMINISTERED price with a published band: the diesel that runs the mine fleet "
              "reaches Peru on a decree clock, and fuel protests are a conflict input"},
    {"id": "PE-J", "title": "The AFP withdrawals, the offshore limit and the dollarised "
                            "deposit base",
     "objects": ("the seven legislated extraordinary withdrawals since 2020",
                 "the BCRP's offshore-limit steps",
                 "the SBS monthly portfolio and its offshore share",
                 "the dollarisation ratio of deposits and credit"),
     "conditions": ("inside a withdrawal PAYMENT window against inside the enactment week",
                    "whether the offshore limit was raised in the same quarter",
                    "the deposit dollarisation level at the time"),
     "instruments": ("USDBRL", "USDMXN", "US500"),
     "controls": ("the Chilean multifondo switch episodes -- the same asset class, a different "
                  "mechanism (the `cl` pack owns them)",
                  "quarters with an offshore-limit step and no withdrawal",
                  "a randomised-date null over the same windows"),
     "notes": "the enactment date and the first payment window are WEEKS apart and the flow "
              "follows the second; using the first is the standard way this study goes wrong"},
    {"id": "PE-K", "title": "Coffee, the agro-export campaign and the ENFEN weather state",
     "objects": ("the arabica harvest and the cooperative acopio",
                 "the organic and fair-trade differential Peru is the largest supplier of",
                 "the roya (leaf rust) outbreaks",
                 "the SENASA export certifications and the northern flood years"),
     "conditions": ("the harvest window (April to September in the main growing regions)",
                    "the ENFEN alert state during flowering",
                    "whether a roya outbreak was declared"),
     "instruments": ("COFARA", "SOYBEAN", "CORN"),
     "controls": ("Colombian and Brazilian harvest windows over the same months",
                  "the same windows in a neutral ENFEN year",
                  "a randomised-date null on the harvest calendar"),
     "notes": "a genuinely SECOND-ORDER edge, declared as such: Peru is a top-ten arabica origin "
              "and the largest organic exporter, which is a differential story more than a "
              "flat-price one"},
    {"id": "PE-L", "title": "The Lima market plane: the BVL, the soberanos and the MILA",
     "objects": ("the S&P/BVL Peru General and its ~60% mining weight",
                 "the non-resident share of soberanos",
                 "the MILA cross-listing with Chile, Colombia and Mexico",
                 "the MSCI emerging-market classification and its review dates"),
     "conditions": ("the non-resident holding bucket",
                    "whether a political event fell in the window",
                    "whether the same day carried a large copper move"),
     "instruments": ("XCUUSD", "US500", "USDBRL"),
     "controls": ("the MILA peers on the same days, separating 'Lima' from 'the region'",
                  "copper-matched days with no Peruvian domestic event",
                  "a matched-weekday placebo"),
     "notes": "NO BVL CFD EXISTS and the index is a levered copper proxy, so this domain mints "
              "CONDITIONERS rather than independent cells and says so"},
    {"id": "PE-M", "title": "The two calendars: the national feriado table and the Andean one",
     "objects": ("the fourteen fixed national feriados and the Ley 31968 break in 2024",
                 "Jueves and Viernes Santo, computed from Easter",
                 "the sierra's Carnaval, Inti Raymi and regional anniversaries",
                 "the decreed dias no laborables (the 2024 APEC days)"),
     "conditions": ("a national feriado against an ordinary weekday",
                    "a SIERRA day (Carnaval, Inti Raymi) against an ordinary weekday, which is "
                    "about the ROAD and not the bourse",
                    "before or after the Ley 31968 break"),
     "instruments": ("XCUUSD", "XZNUSD", "USDBRL", "US500"),
     "controls": ("the matched weekday 26 weeks away, the standard holiday-liquidity control",
                  "the same dates in years before Ley 31968 created the day",
                  "Chilean and Colombian holidays that do not coincide"),
     "notes": "Peru has NO daylight saving, so a session study here never has to carry a clock "
              "change -- and the SIERRA calendar is the one that matters for the corridor"},
)

# --------------------------------------------------------------------------- miners
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    {"name": "pe_bcrp_decision_windows", "domain_ids": ("PE-A",), "kind": "event",
     "cadence_s": 86400.0, "steerable": False, "wired": False,
     "entry": "countries.pe.pack:bcrp_decision_windows",
     "needs": ("the published BCRP calendar intersected with `policy_thursdays`",
               "USDBRL, USDMXN, XCUUSD, US500 H1 bars"),
     "notes": "the candidate lattice is produced here; the PUBLISHED calendar must be joined "
              "before a cell is compiled, and the miner reports UNMEASURED when it is absent"},
    {"name": "pe_intervention_state", "domain_ids": ("PE-B",), "kind": "macro",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.pe.pack:intervention_state",
     "needs": ("BCRP:intervencion_cambiaria daily series", "USDBRL, USDMXN D1 bars"),
     "notes": "the intervention-intensity bucket with the block-shuffled null beside it"},
    {"name": "pe_conflict_supply_windows", "domain_ids": ("PE-D", "PE-C"), "kind": "event",
     "cadence_s": 43200.0, "steerable": True, "wired": False,
     "entry": "countries.pe.pack:conflict_supply_windows",
     "needs": ("BLOCKADE_EPISODES", "the Defensoria monthly case table",
               "XCUUSD, XZNUSD, XAGUSD H1 bars", "Matarani throughput"),
     "notes": "THE PACK'S PRIMARY MINER: the declared episodes with the Chilean-event control "
              "and the non-mining-conflict placebo built in"},
    {"name": "pe_anchoveta_substitution", "domain_ids": ("PE-F",), "kind": "transfer",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.pe.pack:anchoveta_substitution",
     "needs": ("ANCHOVETA_SEASONS and `cancelled_seasons()`", "SOYBEAN, CORN D1 bars",
               "the ENFEN state"),
     "notes": "the cancelled seasons are the tradable rows; the USDA report dates are the "
              "control that separates the ration from the crop"},
    {"name": "pe_political_timestamps", "domain_ids": ("PE-E", "PE-L"), "kind": "event",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.pe.pack:political_timestamps",
     "needs": ("POLITICAL_EVENTS", "USDBRL, USDMXN, XCUUSD, US500 H1 bars"),
     "notes": "every row PRESS_REPORTED; the honest null (the BCRP absorbs it) is the stated "
              "alternative hypothesis"},
    {"name": "pe_andean_calendar", "domain_ids": ("PE-M",), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.pe.pack:andean_calendar",
     "needs": ("`national_holidays`, `regional_days`, `carnaval`", "XCUUSD, XZNUSD H1 bars"),
     "notes": "two calendars, one country: the bourse's and the corridor's"},
    {"name": "pe_transmission_seeds",
     "domain_ids": ("PE-C", "PE-D", "PE-F", "PE-G", "PE-H", "PE-I", "PE-J", "PE-K"),
     "kind": "transfer", "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.pe.pack:transmission_seeds",
     "needs": ("TRANSMISSION_EDGES_SEED", "INTERACTIONS"),
     "notes": "the pack's map as HYPOTHESIS discoveries, deduplicated by the registry"},
)
MINER_DOMAINS: dict[str, tuple[str, ...]] = {
    "central_bank_surprise": ("PE-A",), "release_surprise": ("PE-C", "PE-A"),
    "calendar_settlement": ("PE-M", "PE-H"), "holiday_liquidity": ("PE-M",),
    "positioning": ("PE-L", "PE-J"), "carry_funding": ("PE-B", "PE-J"),
    "corporate_flow": ("PE-C", "PE-G"), "institutional_flow": ("PE-J", "PE-L"),
    "equity_mechanics": ("PE-L",), "derivatives_expiry": ("PE-L",),
    "failure": ("PE-D", "PE-I"), "residual": ("PE-B", "PE-E"),
    "transfer": ("PE-F", "PE-K"), "scouts": ("PE-D", "PE-G"),
    "session_microstructure": ("PE-L", "PE-M"),
}

# --------------------------------------------------------------------------- transmission
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    {"id": "PE-E1", "source": "A declared blockade of the Corredor Vial Minero del Sur",
     "target": "XCUUSD", "targets": ("XCUUSD",), "to_country": "global", "sign": "+",
     "mechanism": "Las Bambas trucks roughly 2% of world mine supply 450 km down ONE road; when "
                  "the road closes the mine runs its stockpile down and then halts, and the "
                  "withheld tonnes are a real share of the quarter's visible balance",
     "horizon": "0 to 20 sessions", "horizon_class": "multi_day", "lag_days": 3.0,
     "actor": "the corridor communities and MMG Las Bambas",
     "constraint": "no alternative route: no rail, no pipeline, no second road",
     "flow": "physical concentrate withheld from the seaborne market",
     "condition": "a declared episode (`is_blockade_day`) with the LME inventory state below "
                  "its median",
     "control": "Chilean supply events in the same windows; escalating NON-mining Peruvian "
                "conflicts as the placebo",
     "falsifier": "declared blockade windows match the matched-weekday control on XCUUSD once "
                  "Chinese demand prints and exchange inventories are conditioned on",
     "evidence": "HYPOTHESIS"},
    {"id": "PE-E2", "source": "A mine-site occupation or water seizure that halts an operation",
     "target": "XCUUSD", "targets": ("XCUUSD", "XAGUSD"), "to_country": "global", "sign": "+",
     "mechanism": "an occupation stops the MINE rather than the road, so there is no stockpile "
                  "buffer and the supply effect starts immediately -- a different lag profile "
                  "from a blockade and therefore the blockade's own control",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "the affected community and the operator",
     "constraint": "a smelter or concentrator that is expensive to stop and restart",
     "flow": "immediate production loss",
     "condition": "an episode whose site is the mine itself, not the road",
     "control": "road-only episodes over the same period; the same windows at unaffected units",
     "falsifier": "site occupations and road blockades produce statistically identical copper "
                  "responses, which would mean the market prices the headline and not the tonnes",
     "evidence": "HYPOTHESIS"},
    {"id": "PE-E3", "source": "The MINEM unit-level zinc production line (Antamina and the "
                              "polymetallic units)",
     "target": "XZNUSD", "targets": ("XZNUSD", "XPBUSD"), "to_country": "global", "sign": "+",
     "mechanism": "Peru is the largest zinc producer in the Americas and its zinc comes out with "
                  "its lead and silver, so a unit-level miss is a JOINT supply shock across "
                  "three metals and can be told apart from a single-metal demand move",
     "horizon": "1 to 3 months", "horizon_class": "multi_day", "lag_days": 55.0,
     "actor": "Antamina and the Ancash and Pasco polymetallic operators",
     "constraint": "the grade phase, which is disclosed in advance and swings the metal mix",
     "flow": "contained metal in concentrate",
     "condition": "a unit-level miss larger than its own trailing dispersion",
     "control": "the ILZSG world balance in the same months; units with no reported disruption",
     "falsifier": "unit-level misses carry no information about zinc beyond the ILZSG balance",
     "evidence": "HYPOTHESIS"},
    {"id": "PE-E4", "source": "A cancelled or severely cut anchoveta season",
     "target": "SOYBEAN", "targets": ("SOYBEAN", "CORN"), "to_country": "global", "sign": "+",
     "mechanism": "Peru is the world's largest fishmeal exporter and fishmeal and soymeal are "
                  "substitutes in the aquaculture and hog rations; a cancelled season removes "
                  "the protein and the ration reformulates toward soy",
     "horizon": "1 to 3 months", "horizon_class": "multi_day", "lag_days": 20.0,
     "actor": "PRODUCE and IMARPE, and the Chinese aquaculture buyers on the other side",
     "constraint": "the feeding cycle: the substitution takes weeks, not days",
     "flow": "protein substitution in the compound feed ration",
     "condition": "a season CANCELLED or cut by more than a third against the prior year",
     "control": "the USDA report dates; normal-season years in the same calendar windows",
     "falsifier": "cancellation announcements show no abnormal soybean move once the USDA "
                  "supply-demand cycle and South American weather are controlled for",
     "evidence": "HYPOTHESIS"},
    {"id": "PE-E5", "source": "The ENFEN official El Nino alert state",
     "target": "SOYBEAN", "targets": ("SOYBEAN", "CORN", "COFARA"), "to_country": "global",
     "sign": "+",
     "mechanism": "one published, dated, multi-agency category conditions the anchoveta biomass, "
                  "the northern Peruvian agricultural campaign and the highland road state at "
                  "once -- three mechanisms off one bulletin",
     "horizon": "1 to 2 quarters", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "the ENFEN commission",
     "constraint": "the state is a JUDGEMENT and is revised between bulletins",
     "flow": "weather state into fishery quota and crop campaign",
     "condition": "a state change into or out of 'alerta de El Nino costero'",
     "control": "global ENSO indices, separating 'the Pacific warmed' from 'ENFEN declared'",
     "falsifier": "ENFEN state changes carry nothing beyond the published global ENSO indices",
     "evidence": "MEASURED_ELSEWHERE"},
    {"id": "PE-E6", "source": "The Chancay deep-water terminal opening (2024-11-14) and its "
                              "direct Shanghai service",
     "target": "XCUUSD", "targets": ("XCUUSD", "USDCNH"), "to_country": "cn", "sign": "+",
     "mechanism": "a dated, permanent change in the Pacific copper leg's transit time and cost; "
                  "it shortens the South America-to-Asia voyage and re-routes part of the "
                  "concentrate flow away from Callao and the Panama route",
     "horizon": "a structural break, measured as a level shift",
     "horizon_class": "regime", "lag_days": 0.0,
     "actor": "Cosco Shipping and the Peruvian port authority",
     "constraint": "the terminal's ramp, and the road connection to the corridor that still "
                   "does not exist",
     "flow": "seaborne concentrate logistics",
     "condition": "before against after 2024-11-14",
     "control": "Chilean port throughput over the same months; the same months a year earlier",
     "falsifier": "no measurable change in the Peru-to-China concentrate transit or in the "
                  "freight differential after the opening",
     "evidence": "HYPOTHESIS"},
    {"id": "PE-E7", "source": "A BCRP intervention print in the top decile of its own history",
     "target": "USDBRL", "targets": ("USDBRL", "USDMXN"), "to_country": "global", "sign": "-",
     "mechanism": "a large published intervention marks a stress day the regional legs are also "
                  "living through; the Peruvian print is an OBSERVED marker of regional dollar "
                  "demand rather than a cause of it, and the edge, if any, is in the marker",
     "horizon": "0 to 3 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "the BCRP FX desk",
     "constraint": "the print lands after the Lima close, so it can only condition the next day",
     "flow": "central-bank dollar supply into a stressed regional market",
     "condition": "an intervention amount above the 90th percentile of the trailing year",
     "control": "the same state on a block-shuffled intervention series; days with equivalent "
                "regional moves and no Peruvian print",
     "falsifier": "top-decile intervention days carry no information about the next session in "
                  "USDBRL or USDMXN beyond the global risk state",
     "evidence": "HYPOTHESIS"},
    {"id": "PE-E8", "source": "An AFP extraordinary-withdrawal payment window",
     "target": "US500", "targets": ("US500", "USDBRL", "USDMXN"), "to_country": "global",
     "sign": "-",
     "mechanism": "the funds must liquidate offshore assets to pay, which is a dated, "
                  "involuntary, politically-caused sale into a known window",
     "horizon": "the payment window plus 10 sessions", "horizon_class": "multi_day",
     "lag_days": 0.0,
     "actor": "the AFPs and the Congress that legislated the withdrawal",
     "constraint": "the enactment date and the payment window are weeks apart and the flow "
                   "follows the second",
     "flow": "forced liquidation of offshore holdings",
     "condition": "inside a payment window, sized by the estimated withdrawal amount",
     "control": "the Chilean multifondo switch episodes; windows with an offshore-limit step "
                "and no withdrawal",
     "falsifier": "payment windows match the matched-weekday control once the global risk state "
                  "and the BCRP's own smoothing operations are conditioned on",
     "evidence": "HYPOTHESIS"},
    {"id": "PE-E9", "source": "A Peruvian political timestamp (vacancia, succession, self-coup)",
     "target": "USDBRL", "targets": ("USDBRL", "USDMXN", "XCUUSD"), "to_country": "global",
     "sign": "+",
     "mechanism": "the sol barely moves because the BCRP holds it, so the effect -- if there is "
                  "one -- shows in the regional legs and in the metal, through the mining-regime "
                  "channel rather than the currency channel",
     "horizon": "0 to 5 sessions", "horizon_class": "intraday", "lag_days": 0.0,
     "actor": "Congress and the presidency",
     "constraint": "an immediate constitutional succession, which caps the institutional risk",
     "flow": "political risk into the mining investment expectation",
     "condition": "an event whose class threatens the mining regime, not merely the office",
     "control": "Brazilian and Colombian political events; equivalent global risk days",
     "falsifier": "no abnormal move in any executable leg once the global risk state is "
                  "controlled for -- the honest null, and a genuinely likely one here",
     "evidence": "HYPOTHESIS"},
    {"id": "PE-E10", "source": "The FEPC fuel band activation and the mine fleet's diesel cost",
     "target": "XTIUSD", "targets": ("XTIUSD", "XCUUSD"), "to_country": "global", "sign": "+",
     "mechanism": "Peru administers the pump price through a stabilisation fund with a published "
                  "band, so a crude move reaches the Peruvian mine fleet's cost base on a DECREE "
                  "clock and the fiscal cost lands on the Treasury instead",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 7.0,
     "actor": "Osinergmin and the MEF",
     "constraint": "the band's trigger, and the fund's balance",
     "flow": "administered fuel price into mining operating cost and into the fiscal account",
     "condition": "a band activation or suspension month",
     "control": "months with an equivalent crude move and no band activation; the Chilean and "
                "Colombian fuel-price regimes",
     "falsifier": "band activations carry no information about the crude leg or about the "
                  "metals beyond the crude move that triggered them",
     "evidence": "HYPOTHESIS"},
    {"id": "PE-E11", "source": "The canon minero transfer to a producing region",
     "target": "XCUUSD", "targets": ("XCUUSD", "XZNUSD"), "to_country": "global", "sign": "-",
     "mechanism": "half the mining income tax returns to the producing region a YEAR later, so a "
                  "high copper year funds the following year's local budgets -- and a LOW canon "
                  "year is the conflict-risk year, which makes the metal price a lagged input "
                  "to its own future supply risk",
     "horizon": "1 year", "horizon_class": "regime", "lag_days": 365.0,
     "actor": "the MEF and the regional governments",
     "constraint": "the statutory formula and the one-year computation lag",
     "flow": "mining tax into local fiscal capacity into conflict propensity",
     "condition": "a canon transfer in the bottom tercile of the region's own history",
     "control": "regions receiving canon with no producing mine; the national conflict level",
     "falsifier": "canon size carries no information about the following year's conflict count, "
                  "controlling for production and for the national conflict level",
     "evidence": "HYPOTHESIS"},
    {"id": "PE-E12", "source": "The Andean calendar: Carnaval and Inti Raymi on the corridor",
     "target": "XCUUSD", "targets": ("XCUUSD", "XZNUSD"), "to_country": "global", "sign": "+",
     "mechanism": "the sierra stops for two days at Carnaval and for the Inti Raymi week, so "
                  "trucking counts fall for reasons that are NOT a blockade -- which is the "
                  "confound a conflict study must remove before it claims anything",
     "horizon": "0 to 5 sessions", "horizon_class": "multi_day", "lag_days": 0.0,
     "actor": "the corridor communities and the trucking contractors",
     "constraint": "the calendar is Easter-derived and therefore known years in advance",
     "flow": "seasonal logistics interruption",
     "condition": "a Carnaval or Inti Raymi window with NO declared blockade",
     "control": "the matched weekday 26 weeks away; the same windows in a blockade year",
     "falsifier": "no measurable difference between corridor throughput in a Carnaval week and "
                  "in a matched ordinary week, which would retire the confound",
     "evidence": "HYPOTHESIS"},
)

#: INTERACTIONS -- the packs this one has a MEASURABLE relationship with, so the desk stops
#: testing each country in isolation. The `cl` row is first and is the sharpest: Chile and Peru
#: are the world's first and second copper producers and each is the other's negative control.
INTERACTIONS: tuple[dict[str, Any], ...] = (
    {"with": "cl",
     "mechanism": "THE ANDEAN SUPPLY PAIR. Chile mines roughly a quarter of world copper and "
                  "Peru roughly a tenth; together they are the marginal supplier. Their supply "
                  "risks are STRUCTURALLY DIFFERENT -- Chile's is a labour contract on a "
                  "published four-year cycle, Peru's is a road closed by a community assembly -- "
                  "which is precisely what makes each the other's control. The `cl` pack owns "
                  "the union calendar, the AFP multifondo switch and the pre-announced BCCh "
                  "intervention programme; this pack owns the conflict calendar, the CDR and "
                  "swap book and the mine-level production count. Neither duplicates the other",
     "observable": "a Peruvian blockade window with NO Chilean labour event, against a Chilean "
                   "strike window with no Peruvian event, against a window with both",
     "targets": ("XCUUSD", "XAGUSD", "XZNUSD"),
     "control": "windows with a Chinese demand print and neither country's event -- the third "
                "cell that separates Andean supply from Chinese demand"},
    {"with": "cn",
     "mechanism": "China takes more than half of Peru's mineral exports, owns Las Bambas "
                  "(MMG), Toromocho (Chinalco) and Marcona (Shougang), and OPENED CHANCAY on "
                  "2024-11-14 as a Cosco-operated deep-water terminal with a direct Shanghai "
                  "service. The demand side, the ownership side and now the logistics side of "
                  "Peruvian copper are all Chinese, and each is separately dated",
     "observable": "Chinese refined and concentrate import prints against the Peruvian export "
                   "record (the mirror comparison), and Chancay throughput from 2024-11",
     "targets": ("XCUUSD", "USDCNH", "CHINAH"),
     "control": "Chilean exports to China over the same months; the Chinese import print with "
                "no Peruvian supply event"},
    {"with": "br",
     "mechanism": "Brazil is the regional EM benchmark this pack's macro domains are routed "
                  "through, because PEN is absent and USDBRL is the deepest liquid leg. It is "
                  "ALSO the other side of PE-F: Brazilian soymeal is the substitute the world "
                  "reaches for when the anchoveta quota is cut, and the two countries' feed "
                  "complexes clear against each other",
     "observable": "the Peruvian political and intervention timestamps against USDBRL's own "
                   "calendar, and the Brazilian soymeal crush against Peruvian fishmeal supply",
     "targets": ("USDBRL", "SOYBEAN", "CORN"),
     "control": "USDMXN as the second regional leg, separating 'LatAm risk' from 'Brazil'"},
    {"with": "mx",
     "mechanism": "Mexico is the world's #1 SILVER producer and Peru is #2; between them they "
                  "are most of the primary and by-product supply. Peruvian silver is a "
                  "CO-PRODUCT of zinc and lead concentrate while Mexican silver includes "
                  "primary mines, so a joint move separates 'silver' from 'base metals'. "
                  "USDMXN is also this pack's second EM routing leg",
     "observable": "the two countries' monthly silver production lines against the metal, with "
                   "the Peruvian base-metal by-product share as the conditioner",
     "targets": ("XAGUSD", "USDMXN", "XZNUSD"),
     "control": "windows with a gold move and no silver-specific supply event"},
    {"with": "bo",
     "mechanism": "Bolivia is Peru's altiplano neighbour and its sibling polymetallic producer "
                  "(zinc, silver, lead, tin) with an Aymara-speaking border population, shared "
                  "conflict repertoires and a shared smuggling economy in fuel and gold. A "
                  "Bolivian blockade and a Peruvian blockade in the same window are the same "
                  "political weather; one without the other is a country-specific shock",
     "observable": "the two countries' road-blockade calendars side by side, and their combined "
                   "zinc, lead and silver production against the metals",
     "targets": ("XZNUSD", "XPBUSD", "XAGUSD", "XAUUSD"),
     "control": "Chilean supply over the same windows, which shares the geography and not the "
                "conflict repertoire"},
)

# --------------------------------------------------------------------------- eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    {"name": "inflation targeting adopted, the commodity supercycle begins",
     "start": "2002-01-01", "end": "2011-07-27",
     "regime": "the BCRP adopts an explicit inflation target in January 2002 (2.5% until 2006, "
               "2% with a +/-1 band from 2007) and begins publishing a monthly decision; the "
               "copper supercycle turns Peru into a mining economy and the canon minero starts "
               "transferring real money to the producing regions",
     "markers": ("2002-01 the inflation target is adopted",
                 "2007-01 the target is lowered to 2%",
                 "2008-2009 the global crisis and the first large intervention episode"),
     "why_it_matters": "before 2002 there is no policy-surprise object at all; pooling across "
                       "this boundary measures two different central banks",
     "status": "SETTLED"},
    {"name": "the windfall-tax settlement and the conflict regime's construction",
     "start": "2011-07-28", "end": "2016-07-27",
     "regime": "the Humala government negotiates the gravamen especial and the impuesto especial "
               "a la mineria instead of a windfall tax (2011-09), passes the prior-consultation "
               "law Ley 29785 (2011-09) and then loses Conga and Tia Maria to community "
               "opposition; the mining fiscal regime and the conflict regime are both SET here",
     "markers": ("2011-09 Ley 29785 consulta previa enacted",
                 "2011-09 the IEM/GEM mining tax package",
                 "2011-11 Conga suspended after the Cajamarca protests",
                 "2015-05 Tia Maria suspended after the Islay protests"),
     "why_it_matters": "both halves of PE-D and PE-H are legislated in this era; a conflict "
                       "study that pools across 2011 is pooling two different legal regimes",
     "status": "SETTLED"},
    {"name": "the instability begins: four presidents and a dissolved Congress",
     "start": "2016-07-28", "end": "2020-03-15",
     "regime": "Kuczynski takes office, survives one vacancia vote and resigns in March 2018; "
               "Vizcarra dissolves Congress on 2019-09-30; the mining investment cycle stalls "
               "while the copper price recovers -- the first era in which POLITICS and METAL "
               "visibly decouple because the BCRP absorbs the currency channel",
     "markers": ("2017-12-21 the first vacancia vote fails",
                 "2018-03-21 Kuczynski resigns", "2019-09-30 Congress dissolved"),
     "why_it_matters": "PE-E's sample starts here, and its honest null (the BCRP absorbs it) is "
                       "first visible in this era",
     "status": "SETTLED"},
    {"name": "the pandemic, the 0.25% floor and the AFP withdrawals",
     "start": "2020-03-16", "end": "2021-07-27",
     "regime": "the policy rate cut to 1.25% on 2020-03-19 and to 0.25% on 2020-04-09 and held "
               "there for seventeen months; Congress legislates the first extraordinary AFP "
               "withdrawals; two presidents in a week in November 2020; a contested run-off in "
               "June 2021 leaves the result unresolved for six weeks",
     "markers": ("2020-04-09 the 0.25% floor", "2020-11-09 to 11-17 three presidents in nine "
                 "days", "2021-06-06 the contested run-off"),
     "why_it_matters": "the rate is at a floor and cannot surprise, so PE-A has no variation "
                       "here; PE-J has its largest sample",
     "status": "SETTLED"},
    {"name": "the Castillo government, the hiking cycle and the corridor's worst year",
     "start": "2021-07-28", "end": "2022-12-06",
     "regime": "the BCRP hikes from 0.25% to 7.50% across eighteen consecutive meetings; Las "
               "Bambas is blockaded repeatedly and then occupied for about fifty days in "
               "April-June 2022; Cuajone is halted by a water seizure in February-March 2022; "
               "the sol stays among the calmest EM currencies throughout",
     "markers": ("2021-08-12 the first hike", "2022-02-28 the Cuajone water seizure",
                 "2022-04-14 the Las Bambas occupation begins",
                 "2022-08-11 the rate reaches 6.75%"),
     "why_it_matters": "the richest conflict sample and the only full hiking cycle at once; the "
                       "two must be conditioned on each other or each contaminates the other",
     "status": "SETTLED"},
    {"name": "the self-coup, the protests and the easing cycle",
     "start": "2022-12-07", "end": "2024-11-13",
     "regime": "Castillo's dissolution attempt, vacancia and arrest on one afternoon; Boluarte "
               "sworn in; the southern protests close the corridor through January and February "
               "2023; the rate peaks at 7.75% and the easing begins 2023-09; the 2023 first "
               "anchoveta season is CANCELLED on an El Nino biomass call",
     "markers": ("2022-12-07 the self-coup", "2023-01-09 the Juliaca deaths",
                 "2023-06 the first anchoveta season cancelled",
                 "2023-09-14 the first cut"),
     "why_it_matters": "the largest single political timestamp this pack has and a cancelled "
                       "fishing season in the same era; both are clean events",
     "status": "SETTLED"},
    {"name": "the Chancay era: a Chinese deep-water port on the Pacific",
     "start": "2024-11-14", "end": "2026-12-31",
     "regime": "the Cosco-operated Chancay terminal opens with a direct Shanghai service, "
               "changing the Peru-to-Asia transit; the easing cycle continues toward a neutral "
               "rate; the REINFO informal-mining deadline is extended again; copper production "
               "grows without a new large mine",
     "markers": ("2024-11-14 Chancay inaugurated",
                 "2024 Ley 31968 adds four national feriados",
                 "2025 the corridor's agreements come up for renegotiation"),
     "why_it_matters": "the current regime, and a PHYSICAL one: every freight-sensitive copper "
                       "cell has a level shift at this date",
     "status": "OPEN"},
)

ACCESS_CONSTRAINTS: tuple[dict[str, Any], ...] = (
    {"constraint": "the sol is not quoted by this broker",
     "measured": "data/universe/universe.json holds no PEN symbol",
     "consequence": "every domestic macro mechanism terminates in the regional EM legs, the "
                    "metals, the softs or US500; PEN is an INPUT and a CONDITIONER, never a cell"},
    {"constraint": "the BCRP does not publish its decision calendar inside this pack",
     "measured": "CENTRAL_BANK.decision_dates is EMPTY on purpose and dates_status says why",
     "consequence": "PE-A compiles a cell only after the published calendar is joined to "
                    "`policy_thursdays()`; an unjoined date is UNMEASURED, not approximate"},
    {"constraint": "the blockade and political dates are PRESS_REPORTED",
     "measured": "every BLOCKADE_EPISODES and POLITICAL_EVENTS row carries that label and no "
                 "El Peruano citation",
     "consequence": "PE-D and PE-E may generate hypotheses and may not promote any cell until "
                    "a busquedas.elperuano.pe norm or a company hecho de importancia is "
                    "attached to the exact date the cell was compiled on"},
    {"constraint": "the MINEM statistics and the APN throughput pages are overwritten in place",
     "measured": "both publish the current file over the same link and keep no vintage",
     "consequence": "PE-C's and PE-G's point-in-time history exists only in the archive layer's "
                    "crawls; a cell compiled on an un-archived month is UNMEASURED, not assumed"},
    {"constraint": "the concentrate TC/RC and the fishmeal FOB assessments forbid machine "
                   "extraction",
     "measured": "Fastmarkets and Argus terms; registered machine_use_allowed=false",
     "consequence": "the miner's REALISED copper price and the fishmeal price leg are both "
                    "UNMEASURED; PE-C is tested on the exchange metal and PE-F on the "
                    "SUBSTITUTE, and the absence is named rather than worked around"},
    {"constraint": "the customs VALUE series is a price series in disguise",
     "measured": "concentrate is declared at a provisional price and settled later",
     "consequence": "every physical claim in this pack uses VOLUME; a study that uses declared "
                    "value is measuring the metal price twice and calling it supply"},
    {"constraint": "informal gold output is unmeasured by construction",
     "measured": "the gold export line exceeds counted mine production and the REINFO register "
                 "is a legalisation queue rather than a production count",
     "consequence": "XAUUSD cells from this pack are declared WEAK; the export-minus-production "
                    "gap is carried as a measurement warning, never as a supply signal"},
    {"constraint": "Peru has no listed derivatives market and no sol positioning series",
     "measured": "no BVL futures expiry clock exists and no COT contract covers PEN",
     "consequence": "PE-L mints conditioners rather than independent cells, and sol positioning "
                    "is UNMEASURED and is never proxied by the BRL or MXN COT legs"},
)
INSTITUTIONAL_FLOW_SOURCES: tuple[str, ...] = (
    "BCRP daily spot intervention and the CDR and swap balances",
    "MEF non-resident holdings of soberanos",
    "SBS AFP cartera administrada and the BCRP offshore limit",
    "SUNAT customs export volumes by product and destination",
    "APN port throughput at Callao, Matarani, Ilo and Chancay")
SERIES: dict[str, str] = {
    "PE_POLICY": "BCRP:tasa_de_referencia", "PE_FX_INTERVENTION": "BCRP:intervencion_cambiaria",
    "PE_CDR_SWAPS": "BCRP:saldo_cdr_y_swaps", "PE_RESERVES": "BCRP:rin",
    "PE_CPI": "INEI:ipc_lima", "PE_GDP": "INEI:pbi_mensual",
    "PE_MINE_PRODUCTION": "MINEM:produccion_por_unidad",
    "PE_CONFLICTS": "DP:conflictos_activos", "PE_EXPORTS": "SUNAT:exportaciones_por_partida",
    "PE_ANCHOVETA": "PRODUCE:cuota_y_desembarque", "PE_ENFEN": "ENFEN:estado_alerta",
    "PE_PORTS": "APN:movimiento_de_carga", "PE_AFP": "SBS:cartera_administrada",
    "PE_SOBERANOS": "MEF:tenencia_no_residentes", "PE_FUEL_BAND": "OSINERGMIN:fepc_banda",
}

# --------------------------------------------------------------------------- the cells
#: WHAT EACH DOMAIN MINTS: its mechanism family, its horizon class, and the one-line control
#: every cell from it inherits. `cells()` is the cross product of a domain's INSTRUMENTS and its
#: CONDITIONS -- both of which are real, named, evaluable states of this pack's own data plane.
#: It is not a cartesian blow-up: a condition that cannot be evaluated from a declared dataset
#: does not appear in a domain's `conditions` tuple in the first place.
DOMAIN_CELL_SPEC: dict[str, tuple[str, str, str]] = {
    "PE-A": ("policy_surprise", "intraday_to_3d",
             "the four nearest non-meeting Thursdays and the FOMC-day overlap"),
    "PE-B": ("intervention_state", "1d_to_5d",
             "a block-shuffled intervention series and the Andean neighbours"),
    "PE-C": ("physical_supply", "1m_to_3m",
             "Chilean production in the same month and undisrupted units"),
    "PE-D": ("supply_disruption", "0d_to_20d",
             "Chilean labour events and non-mining Peruvian conflicts"),
    "PE-E": ("political_event", "intraday_to_5d",
             "Brazilian and Colombian political events and matched risk days"),
    "PE-F": ("substitution", "20d_to_60d",
             "normal-season years and the USDA report calendar"),
    "PE-G": ("logistics_regime", "regime_level_shift",
             "Chilean port throughput and the same months a year earlier"),
    "PE-H": ("fiscal_transfer", "1y",
             "canon-receiving regions with no mine and the national conflict level"),
    "PE-I": ("administered_price", "0d_to_10d",
             "months with an equivalent crude move and no band activation"),
    "PE-J": ("forced_flow", "the payment window plus 10 sessions",
             "the Chilean multifondo episodes and limit-step-only quarters"),
    "PE-K": ("seasonal_crop", "1m_to_1q",
             "Colombian and Brazilian harvest windows in a neutral ENFEN year"),
    "PE-L": ("positioning", "1d_to_10d",
             "the MILA peers and copper-matched days with no domestic event"),
    "PE-M": ("holiday_liquidity", "0d_to_3d",
             "the matched weekday 26 weeks away and pre-Ley-31968 years"),
}


def cells() -> tuple[dict[str, Any], ...]:
    """Every testable cell this pack mints: domain x executable instrument x named condition.

    A cell is a triple the gauntlet can actually evaluate -- an instrument the broker quotes, a
    condition this pack's own declared datasets can compute, and a control that is not the
    instrument's own history. The cross product is taken over the domain's OWN instrument tuple
    rather than over the whole executable list, which is what keeps the count honest: PE-F never
    mints a copper cell and PE-D never mints a coffee one.
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
    """How many cells each executable instrument carries. A symbol with none is an instrument
    the pack declared and never used, which is a defect the tests catch."""
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


def bcrp_decision_windows(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """PE-A: the BCRP announcement CANDIDATE lattice, with the published-calendar join declared
    as the missing input. Twenty-four Thursdays a year, of which twelve are decisions."""
    year = datetime.now(tz=UTC).year
    lattice = policy_thursdays(year)
    n = _emit(ctx, "policy_surprise", payload={"domain": "PE-A", "lattice": len(lattice),
                                               "year": year})
    return {"miner": "bcrp_decision_windows", "domain": "PE-A", "candidates": len(lattice),
            "emitted": n,
            "unmeasured": [f"PE-A/published_calendar: the BCRP calendar for {year} is not in "
                           f"this pack (L1.28a); the lattice is candidates, not decisions"]}


def intervention_state(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """PE-B: the intervention-intensity state. The series itself is a collector input, so with
    no series loader this miner reports UNMEASURED by name rather than inventing a bucket."""
    n = _emit(ctx, "intervention_state", payload={"domain": "PE-B",
                                                  "series": SERIES["PE_FX_INTERVENTION"]})
    return {"miner": "intervention_state", "domain": "PE-B", "emitted": n,
            "unmeasured": ["PE-B/BCRP:intervencion_cambiaria: the daily intervention series is "
                           "not loaded on this box; the state cannot be bucketed"]}


def conflict_supply_windows(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """PE-D: the pack's primary miner. The declared blockade episodes, their lengths and their
    sites, every one of them PRESS_REPORTED and therefore hypothesis-grade."""
    episodes = blockade_episodes()
    total_days = sum((hi - lo).days + 1 for lo, hi, _s, _w in episodes)
    n = 0
    for lo, hi, site, what in episodes:
        n += _emit(ctx, "supply_disruption",
                   payload={"domain": "PE-D", "start": lo.isoformat(), "end": hi.isoformat(),
                            "site": site, "what": what, "status": "PRESS_REPORTED"})
    return {"miner": "conflict_supply_windows", "domain": "PE-D", "episodes": len(episodes),
            "disrupted_days": total_days, "emitted": n,
            "unmeasured": ["PE-D/elperuano_citation: no episode carries a gazette or company "
                           "citation yet, so none may be promoted"]}


def anchoveta_substitution(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """PE-F: the fishery seasons and the cancelled ones, which are the tradable rows."""
    cancelled = cancelled_seasons()
    n = 0
    for year, season in cancelled:
        n += _emit(ctx, "substitution",
                   payload={"domain": "PE-F", "year": year, "season": season,
                            "targets": ("SOYBEAN", "CORN")})
    return {"miner": "anchoveta_substitution", "domain": "PE-F",
            "seasons": len(ANCHOVETA_SEASONS), "cancelled": len(cancelled), "emitted": n,
            "unmeasured": ["PE-F/fishmeal_fob: the price leg is LICENSED and machine extraction "
                           "is forbidden, so the claim is made on the substitute"]}


def political_timestamps(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """PE-E: the dated political event series, with the honest null stated on every row."""
    n = 0
    for day, what, status in POLITICAL_EVENTS:
        n += _emit(ctx, "political_event",
                   payload={"domain": "PE-E", "date": day.isoformat(), "what": what,
                            "status": status,
                            "null": "the BCRP absorbs the currency channel, so no effect in the "
                                    "executable legs is a genuinely likely outcome"})
    return {"miner": "political_timestamps", "domain": "PE-E", "events": len(POLITICAL_EVENTS),
            "emitted": n,
            "unmeasured": ["PE-E/intraday_minute: only 2022-12-07 has a published minute; the "
                           "rest are day-resolution and cannot carry an intraday cell"]}


def andean_calendar(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """PE-M: the two calendars -- the bourse's national table and the sierra's Easter-derived
    one, which is the calendar the concentrate corridor actually runs on."""
    year = datetime.now(tz=UTC).year
    national = national_holidays(year)
    regional = regional_days(year)
    n = _emit(ctx, "holiday_liquidity",
              payload={"domain": "PE-M", "year": year, "national": len(national),
                       "regional": len(regional),
                       "statute_break": [f"{m:02d}-{d:02d}" for m, d, _ in
                                         new_holidays_since_2024()]})
    return {"miner": "andean_calendar", "domain": "PE-M", "national": len(national),
            "regional": len(regional), "emitted": n, "unmeasured": []}


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
    "bcrp_decision_windows": bcrp_decision_windows,
    "intervention_state": intervention_state,
    "conflict_supply_windows": conflict_supply_windows,
    "anchoveta_substitution": anchoveta_substitution,
    "political_timestamps": political_timestamps,
    "andean_calendar": andean_calendar,
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
            "jurisdictions": JURISDICTIONS, "interactions": tuple(r["with"]
                                                                 for r in INTERACTIONS)}


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
        "blockade_episodes": BLOCKADE_EPISODES, "political_events": POLITICAL_EVENTS,
        "anchoveta_seasons": ANCHOVETA_SEASONS,
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
            "fixed_md": tuple(f"{m:02d}-{d:02d}" for m, d, _n, _since in FIXED_NATIONAL),
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
