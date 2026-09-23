"""BOLIVIA: a HARD PEG whose reserves ran out in public, on top of the world's largest lithium.

WHY BOLIVIA IS ITS OWN PACK AND NOT A FOOTNOTE TO PERU OR CHILE. Every other Andean pack on this
desk is a floating or managed currency with a metal underneath it. Bolivia is the opposite: a
FIXED exchange rate -- 6.96 bolivianos to the dollar, unchanged since 2 November 2011 -- carried
by a central bank whose usable reserves visibly exhausted between 2014 and 2024 while the
official rate did not move a centavo. That combination is rare, it is DATED, and it produced the
one thing a peg study almost never gets: a second, published price for the same currency.

SIX THINGS THAT BELONG TO THIS ECONOMY AND TO NO OTHER IN THE DESK'S BOOK:

  1. A PEG THAT DID NOT BREAK WHILE ITS RESERVES DID. Net international reserves fell from about
     US$15bn in 2014 to roughly US$1.7bn by early 2023, and the LIQUID dollar component fell to
     a few hundred million while most of what remained was GOLD. The official rate stayed at
     6.96. A pegged currency whose reserve backing is visibly exhausting, with the exhaustion
     itself published monthly by the central bank, is a state this desk has nowhere else.

  2. THE GOLD SALES HAVE A STATUTE AND A DATE. Ley 1503 of May 2023 -- the "Ley del Oro" --
     explicitly authorised the Banco Central to trade its gold reserves and to buy domestic
     gold. That turns a reserve-management decision into a DATED, LAWFUL, PUBLISHED supply
     observable on XAUUSD, which the broker quotes. Most sovereign gold sales are inferred from
     an IMF table months later; this one has a law with a number.

  3. A PARALLEL MARKET WITH A PUBLISHED PREMIUM. From 2023 the casas de cambio, the importers
     and eventually the press quoted a second boliviano rate well away from 6.96. The PREMIUM
     between the two -- pure arithmetic on two published numbers -- is the cleanest capital-
     control stress variable available to this desk, and `parallel_premium()` computes it.

  4. TIN, SILVER, ZINC AND LEAD OUT OF ONE MOUNTAIN COMPLEX. Bolivia is a top-five tin producer
     (Huanuni, Colquiri, the Vinto smelter) and a top-ten producer of silver, zinc and lead
     (San Cristobal, San Vicente, Cerro Rico). XZNUSD, XPBUSD and XAGUSD are executable; TIN IS
     NOT, so it is named in `TRANSMISSION_TARGETS` and routed through the co-produced base
     metals rather than pretended away.

  5. THE LITHIUM TRIANGLE'S LARGEST RESOURCE AND ITS LONGEST LIST OF CANCELLED DEALS. The Salar
     de Uyuni holds the largest identified lithium resource on earth and Bolivia has signed and
     then cancelled development agreements on dated, published timelines -- the 2019 ACISA
     cancellation, the 2023 and 2024 Chinese and Russian agreements. That is an interaction with
     the `cl` and `ar` packs, not a Bolivian story: the same molecule, three regulatory regimes.

  6. THE GAS EXPORT IS A MEASURED STRUCTURAL DECLINE AND THE PIPE HAS REVERSED. YPFB's exports
     to Brazil and Argentina peaked around 2014 and fell on a published schedule to a fraction
     of that, while the country went from gas exporter to FUEL IMPORTER -- and the diesel and
     petrol import bill, subsidised at the pump, is the mechanism that consumed the reserves in
     (1). The Argentine flow has since reversed direction: Vaca Muerta gas now moves NORTH
     through Bolivian pipe toward Brazil. A pipeline that changed direction on a dated
     agreement is a regime break, not a trend.

WHAT IS EXECUTABLE AND WHAT IS NOT. THE BOLIVIANO IS ABSENT from this broker and so is tin,
lithium, the BBV's bond curve and the Bolivian sovereign eurobond. Every one is named in
`TRANSMISSION_TARGETS` with the broker symbols that carry its economics, so an absent instrument
produces a transmission hypothesis and never a cell that can never be filled (L1.49).

WHAT THIS PACK IS NOT. It is not a second Peru pack. Peru's mechanism is a CONFLICT CALENDAR
against a floating, heavily-intervened currency with deep published statistics; Bolivia's is a
FIXED RATE against an exhausting reserve, with far thinner statistics and a parallel price. The
two share an altiplano, an Aymara-speaking border population, a blockade repertoire and a
polymetallic geology -- which is exactly why `INTERACTIONS` names `pe` and treats a simultaneous
Bolivian and Peruvian blockade as the same political weather and a lone one as country-specific.

THE TWO-LANE ORDER (2026-09-06). San Cristobal (Sumitomo), Manquiri, Petrobras, Banco Mercantil
Santa Cruz and the soy exporters are ACTORS here and never instruments. No share CFD appears in
any instrument tuple in this file.

NATIVE GROUND: Spanish, QUECHUA, AYMARA and GUARANI -- all four official under article 5 of the
2009 constitution, which recognises thirty-six. The cooperative miners of Potosi and Oruro
organise in Quechua and Aymara; the gas fields of the Chaco sit on Guarani territory and the
Asamblea del Pueblo Guarani negotiates the royalties that fund them. A Spanish-only crawl of
Bolivia misses the two constituencies that can stop a mine and a gas field respectively.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Any

# --------------------------------------------------------------------------- identity
CODE = "bo"
NAME = "Bolivia"
REGION_COMMAND = "latam"
REGION_DESK = "SOUTH_AMERICA"
FOREST = "latam"
CURRENCY = "BOB"
#: THE PARITY FENCE COUNTS THIS (`scripts/check_regional_parity.py::jurisdictions_of`).
JURISDICTIONS: tuple[str, ...] = ("bo",)
#: AND THIS IS THE HONEST STATE OF THAT COUNT (L1.28a). `libs/research/forests.py` lists the
#: Latin America forest as BR, MX, CL, CO, PE and AR -- Bolivia is NOT on the desk's own roster,
#: so the parity fence cannot yet credit any pack for it. This pack answers for `bo` AHEAD of the
#: roster rather than waiting for it, and says so here instead of quietly looking like a country
#: the fence already counted. The moment the roster names `bo`, this pack is what answers it.
ROSTER_STATE: dict[str, str] = {
    "bo": "NOT YET NAMED BY libs/research/forests.py: the 'latam' forest lists BR, MX, CL, CO, "
          "PE, AR. The fence counts only countries the roster names, so `bo` reads as neither "
          "answered nor unanswered until the roster moves. Written anyway because the mechanism "
          "-- a hard peg with exhausting reserves, a statutory gold-sale authority and a "
          "published parallel premium -- exists whether or not a list mentions it",
}
FISCAL_YEAR_END = "12-31"          # the Presupuesto General del Estado runs on the calendar year
NATIVE_LANGUAGES: tuple[str, ...] = ("es", "qu", "ay", "gn")
COT_CURRENCY = ""                  # no CFTC contract exists for the boliviano
EXPORT_ECONOMY = "commodity_exporter"
RETAIL_LEVERAGE_REGIME = "restricted"   # dollar access is rationed; offshore margin is unreachable
#: The depth this pack CLAIMS, checked against the framework's own measurement by the tests.
DECLARED_DEPTH: float = 1.0
MISSION = ("mine Bolivia as the hard-pegged, reserve-exhausted, gold-selling, gas-declining "
           "economy it is: the 6.96 bolsin rate unchanged since 2011 and the published parallel "
           "premium beside it, the BCB's reserve composition and the Ley 1503 gold authority, "
           "the tin-silver-zinc-lead complex out of Potosi and Oruro, the Salar de Uyuni's "
           "signed-and-cancelled lithium agreements, YPFB's measured export decline and the "
           "reversal of the Argentine flow, the subsidised diesel import bill that consumes the "
           "reserves, and the bloqueo as a national logistics shock with a political calendar")

#: The instruments this pack may compile a cell against. Every one is in the broker registry and
#: none is a single-name equity. THE BOLIVIANO ITSELF IS ABSENT (see TRANSMISSION_TARGETS).
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "XAUUSD",                          # the reserve asset Ley 1503 authorised the BCB to sell
    "XAGUSD",                          # San Cristobal, San Vicente and the Cerro Rico complex
    "XZNUSD",                          # co-produced with the silver and the lead
    "XPBUSD",                          # the third leg of the polymetallic concentrate
    "XNIUSD",                          # the only quoted battery metal: the lithium plane's proxy
    "XNGUSD",                          # the export that declined and the pipe that reversed
    "XBRUSD",                          # the import-parity anchor of the subsidised diesel bill
    "XTIUSD",                          # the second crude leg and the fuel-smuggling arbitrage
    "SOYBEAN",                         # Santa Cruz's export crop and the quota regime
    "CORN",                            # the other half of the quota and the biodiesel feedstock
    "SUGAR",                           # the Santa Cruz mills and the ethanol mandate
    "USDBRL",                          # Brazil: the gas offtaker, the soy rival, the EM leg
    "USDMXN",                          # the second EM leg and the risk-on/risk-off control
)

#: WHAT BOLIVIA TRADES THAT THIS BROKER DOES NOT QUOTE. Each row names the absent instrument, its
#: venue, WHY the pack needs it, the REGIME it lives under and the ROUTE into symbols that exist.
TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "BOB (the boliviano): the 6.96 official rate AND the parallel rate beside it",
     "venue": "the BCB's bolsin (official) and the casas de cambio and importers (parallel)",
     "why": "the variable this entire pack is about, absent from the broker. It has TWO prices "
            "and the SPREAD between them is the measurable state: the official one is a "
            "statutory constant and the parallel one is a market",
     "regime": "HARD DE FACTO PEG. The bolsin rate has been 6.96 BOB/USD on the sell side and "
               "6.86 on the buy side since 2011-11-02, unchanged through a reserve collapse, "
               "two governments and a parallel market. It is not a band, not a crawl and not a "
               "managed float: it is one number that has not moved in more than a decade",
     "route": "the peg means the OFFICIAL rate carries no information at all; the PREMIUM is "
              "the state variable and it conditions the regional EM legs, gold and the fuel "
              "complex rather than being a target itself",
     "proxies": ("XAUUSD", "USDBRL", "USDMXN")},
    {"name": "TIN (LME cash tin) -- Bolivia is a top-five producer and it is not quoted here",
     "venue": "the London Metal Exchange; the Vinto smelter's own sales",
     "why": "Huanuni, Colquiri and the cooperatives produce tin as the country's signature "
            "metal, and the desk cannot trade it -- so the tin mechanism must be routed through "
            "the metals that come out of the SAME concentrates and the SAME mines",
     "regime": "an LME contract with a small deliverable stock and a concentrated supply base "
               "(Bolivia, Indonesia, Myanmar, China), which makes it unusually disruption-prone",
     "route": "zinc, lead and silver are co-produced with Bolivian tin at the polymetallic "
              "units, so a Bolivian mining disruption reaches the executable metals directly; "
              "the tin-specific component is UNMEASURED and says so",
     "proxies": ("XZNUSD", "XPBUSD", "XAGUSD")},
    {"name": "LITHIUM carbonate and hydroxide (the Salar de Uyuni resource)",
     "venue": "contract and assessed markets; no broker symbol exists",
     "why": "Bolivia holds the largest identified lithium RESOURCE on earth and has produced "
            "almost none of it; the signed-and-cancelled agreements are dated events with no "
            "tradable leg of their own",
     "regime": "a state monopoly (YLB) under the 2017 law, with partners selected and dropped "
               "by decree; the resource is a RESOURCE and not a reserve until a plant runs",
     "route": "XNIUSD is the only battery metal this broker quotes and it is a WEAK proxy -- "
              "declared weak here rather than dressed up; the honest reading is that Bolivian "
              "lithium news moves the `cl` and `ar` lithium complexes, not nickel",
     "proxies": ("XNIUSD",)},
    {"name": "The Bolivian sovereign eurobond curve and the domestic TGN/BCB paper",
     "venue": "the offshore secondary market; the Bolsa Boliviana de Valores for local paper",
     "why": "the eurobond is the only continuously-priced market opinion on the peg's "
            "survival, and it repriced violently in 2023 while the official rate did not move",
     "regime": "no IMF programme, thin offshore liquidity, and a domestic market in which the "
               "BCB has sold bonds DIRECTLY TO HOUSEHOLDS to absorb bolivianos",
     "route": "the regional EM legs carry the credit state; UST duration is not the driver here",
     "proxies": ("USDBRL", "USDMXN", "XAUUSD")},
    {"name": "The Bolsa Boliviana de Valores equity and fixed-income tape",
     "venue": "Bolsa Boliviana de Valores (BBV), La Paz",
     "why": "an almost entirely fixed-income exchange with negligible equity turnover; it is "
            "registered so that a study does not look for an equity channel that is not there",
     "regime": "ASFI-supervised, dominated by bank and corporate paper, no derivatives",
     "route": "there is no executable equity leg for Bolivia at all, and that is the finding",
     "proxies": ("USDBRL",)},
    {"name": "Bolivian natural gas export prices under the Brazil and Argentina contracts",
     "venue": "bilateral GSA contracts indexed to fuel-oil baskets, not to Henry Hub",
     "why": "the export price is CONTRACTUAL and lagged, so XNGUSD is not the price Bolivia "
            "receives -- the pack says so rather than pretending the two are the same series",
     "regime": "long-term take-or-pay contracts with fuel-oil indexation and quarterly resets",
     "route": "XNGUSD carries the direction and the regime break; the Bolivian realisation is "
              "UNMEASURED and the Brazilian offtaker's own balance is the observable",
     "proxies": ("XNGUSD", "USDBRL")},
    {"name": "Bolivian domestic pump prices for diesel and petrol (the subsidy)",
     "venue": "administered by supreme decree; YPFB imports at market and sells at the decree",
     "why": "THE MECHANISM THAT CONSUMES THE RESERVES. The pump price has been frozen for years "
            "while import parity moved with crude, so the gap is a dollar outflow with a crude "
            "beta -- and an attempt to close it in 2010 (the 'gasolinazo') was reversed in five "
            "days by protest, which is the political constraint made explicit",
     "regime": "administered price, unchanged by decree; the fiscal cost is the residual",
     "route": "XBRUSD and XTIUSD are the import-parity legs; the subsidy bill is the transfer",
     "proxies": ("XBRUSD", "XTIUSD")},
)

# --------------------------------------------------------------------------- the central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "Banco Central de Bolivia (BCB)",
    "framework": "peg",
    "policy_instrument": "THE EXCHANGE RATE ITSELF, sold through the bolsin at a rate that has "
                         "not moved since 2011-11-02; plus the encaje legal, direct credit to "
                         "the public enterprises and the Tesoro, and retail bond issues sold "
                         "straight to households to absorb bolivianos",
    "mandate": "preserve the purchasing power of the boliviano under Ley 1670; in practice the "
               "operating target is the FIXED RATE, and the policy rate (the tasa de "
               "regulacion monetaria) is a residual rather than an instrument",
    "decision_rule": "THERE IS NO SCHEDULED POLICY-RATE MEETING CALENDAR. The exchange rate is "
                     "the instrument and it has one value; the dated decisions are the bolsin "
                     "rules, the reserve reports, the retail bond programmes and the statutory "
                     "gold authority under Ley 1503",
    "decision_calendar_rule": "none published; `reserve_report_months()` gives the monthly "
                              "reserve-publication rhythm the pack actually conditions on",
    "decision_dates": (),
    "dates_status": "DECLARED ABSENT, NOT MISSING (L1.28a). The BCB publishes no policy-meeting "
                    "calendar because the peg IS the policy. A pack that invented twelve "
                    "meeting dates a year here would be inventing an institution. The dated "
                    "events this country actually has are in POLICY_ERAS, GOLD_AUTHORITY and "
                    "GAS_MILESTONES, and every one of them carries its own status label",
    "decision_time_utc": "16:00",
    "announce_local": "the BCB publishes reserve and monetary statistics on its own schedule; "
                      "the bolsin rate is quoted every business day and has been the same "
                      "number since 2011",
    "dst_rule": "NONE. Bolivia is UTC-4 all year and has never observed daylight saving, so a "
                "La Paz event minute is the same in January and in July",
    "minutes_lag_days": 0,
    "publication_classes": ("reservas_internacionales_netas", "boletin_estadistico",
                            "memoria_anual", "informe_de_politica_monetaria",
                            "tipo_de_cambio_oficial", "bonos_bcb_directo",
                            "encaje_legal_resoluciones"),
    "policy_rate_series": "BCB:tasa_de_regulacion_monetaria",
    "expected_rate_series": "UNMEASURED",
    "consensus_proxy": "there is no analyst survey and no local sell-side consensus to measure "
                       "a surprise against; the closest thing is the PARALLEL RATE, which is a "
                       "market price for the same currency and therefore a better one",
    "consensus_proxy_trap": "the parallel rate is quoted by a fragmented set of casas de cambio "
                            "and reported second-hand, so two sources disagree by several per "
                            "cent on the same day; a premium computed from one quote is a "
                            "point estimate with an unstated error bar",
    "reserves_clock": "net international reserves are published by the BCB, and the COMPOSITION "
                      "-- how much is gold, how much is liquid dollars, how much is IMF assets "
                      "-- is the number that matters and the one that moved first",
    "programme": "NONE, AND THAT IS THE POINT. Bolivia has had no IMF programme in this era and "
                 "the government has repeatedly ruled one out, so there is no external "
                 "adjustment clock, no tranche calendar and no Article IV-driven reform "
                 "schedule -- the opposite of every other stressed sovereign on this desk",
    "off_cycle": ("2011-11-02 the last bolsin adjustment; the rate has not moved since",
                  "2023-05 Ley 1503 authorises the BCB to trade reserve gold and buy domestic "
                  "gold, a statutory change of instrument rather than of rate"),
    "root": "https://www.bcb.gob.bo",
}

# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "BCB bolsin official rate (6.96 venta / 6.86 compra)",
     "local": "quoted every business day; the same number since 2011-11-02",
     "time_utc": "13:00", "time_utc_dst": "13:00",
     "dst_rule": "none: Bolivia is UTC-4 all year",
     "instruments": ("USDBRL", "XAUUSD"), "window_minutes": 30,
     "why": "the statutory constant; it carries NO information by construction, which is "
            "exactly why the parallel quote beside it carries all of it"},
    {"name": "The parallel boliviano quote (casas de cambio and importer bids)",
     "local": "continuous, fragmented, reported rather than fixed",
     "time_utc": "14:00", "time_utc_dst": "14:00", "dst_rule": "none: UTC-4 all year",
     "instruments": ("XAUUSD", "USDBRL"), "window_minutes": 120,
     "why": "the second price of the same currency; the PREMIUM to 6.96 is the capital-control "
            "stress state BO-A and BO-C condition on"},
    {"name": "LME official settlement for zinc, lead and tin",
     "local": "12:00-13:00 Europe/London ring", "time_utc": "12:00", "time_utc_dst": "11:00",
     "dst_rule": "GMT/BST", "instruments": ("XZNUSD", "XPBUSD"), "window_minutes": 60,
     "why": "the exchange price Bolivian concentrate is sold against; TIN IS NOT QUOTED by this "
            "broker, so the tin leg is routed through the co-produced metals"},
    {"name": "LBMA gold price PM auction (the reserve asset's benchmark)",
     "local": "15:00 Europe/London", "time_utc": "15:00", "time_utc_dst": "14:00",
     "dst_rule": "GMT/BST", "instruments": ("XAUUSD",), "window_minutes": 15,
     "why": "the price the BCB's gold reserve is marked at and the price its Ley 1503 sales "
            "and purchases are struck against"},
    {"name": "Bolsa Boliviana de Valores close",
     "local": "15:00 America/La_Paz", "time_utc": "19:00", "time_utc_dst": "19:00",
     "dst_rule": "none: UTC-4 all year", "instruments": ("USDBRL",), "window_minutes": 30,
     "why": "an almost entirely fixed-income tape; registered so no study looks for a Bolivian "
            "equity channel that does not exist"},
    {"name": "YPFB nomination and the Brazil-Argentina gas delivery day",
     "local": "daily nominations against the contracts", "time_utc": "10:00",
     "time_utc_dst": "10:00", "dst_rule": "none: UTC-4 all year",
     "instruments": ("XNGUSD", "USDBRL"), "window_minutes": 120,
     "why": "the physical gas day; the contractual price is fuel-oil-indexed and lagged, so "
            "the executable leg carries the DIRECTION and never the realisation"},
    {"name": "Puerto Busch / Arica and Ilo transit windows for mineral concentrate",
     "local": "continuous; Bolivia is landlocked and ships through Chilean and Peruvian ports",
     "time_utc": "14:00", "time_utc_dst": "14:00", "dst_rule": "none: UTC-4 all year",
     "instruments": ("XZNUSD", "XPBUSD", "XAGUSD"), "window_minutes": 180,
     "why": "LANDLOCKED: every tonne of Bolivian concentrate crosses a foreign border, which "
            "makes a Chilean or Peruvian road closure a BOLIVIAN supply event too"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "BCB monthly reserve and monetary statistics", "kind": "month_end",
     "roll": "previous", "window_utc": ("13:00", "19:00"),
     "instruments": ("XAUUSD", "USDBRL"),
     "why": "the reserve level and its COMPOSITION are the peg's own balance sheet; the gold "
            "share is the line Ley 1503 acts on"},
    {"name": "INE monthly CPI and trade statistics", "kind": "day_of_month",
     "days": (5, 6, 7, 8, 9, 10), "roll": "next", "window_utc": ("13:00", "19:00"),
     "instruments": ("SOYBEAN", "USDBRL"),
     "why": "the inflation print that a pegged economy is supposed to import, and the trade "
            "balance that says how fast the dollars are leaving"},
    {"name": "Aduana Nacional monthly import and export detail", "kind": "month_end",
     "roll": "next", "window_utc": ("13:00", "19:00"),
     "instruments": ("XBRUSD", "XTIUSD", "SOYBEAN"),
     "why": "the FUEL IMPORT BILL by volume and value is the reserve drain, and it is a customs "
            "series rather than a central-bank one"},
    {"name": "Month-end YPFB fuel import settlement and the subsidy transfer",
     "kind": "month_end", "roll": "previous", "window_utc": ("13:00", "19:00"),
     "instruments": ("XBRUSD", "XTIUSD"),
     "why": "YPFB buys refined product at market in dollars and sells it at a decreed price in "
            "bolivianos; the settlement is the recurring dollar demand the peg must fund"},
    {"name": "Quarter-end concentrate provisional pricing and the Vinto smelter offtake",
     "kind": "quarter_end", "roll": "previous", "window_utc": ("11:00", "16:00"),
     "instruments": ("XZNUSD", "XPBUSD", "XAGUSD"),
     "why": "concentrate is sold provisionally and repriced at the quotational average; the "
            "quarter boundary concentrates the mark-to-market"},
    {"name": "Fiscal year end (31 December) and the Presupuesto General del Estado",
     "kind": "fiscal_year_end", "roll": "previous", "window_utc": ("13:00", "19:00"),
     "instruments": ("XAUUSD", "USDBRL"),
     "why": "the budget year is the calendar year; the fuel-subsidy line and the public-"
            "enterprise transfers are dated to it"},
    {"name": "The soy harvest and the export-quota (cupo) decision windows",
     "kind": "day_of_month", "days": (1, 15), "roll": "next", "window_utc": ("13:00", "19:00"),
     "instruments": ("SOYBEAN", "CORN", "SUGAR"),
     "why": "the verano harvest lands March-May and the invierno crop August-September; the "
            "government releases or withholds export permission around those boundaries"},
)

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Bolsa Boliviana de Valores (BBV)",
     "index_symbols": (),
     "open_local": "09:00", "close_local": "15:00", "open_utc": "13:00", "close_utc": "19:00",
     "dst_rule": "none: America/La_Paz is UTC-4 all year",
     "auction": "a call market for fixed income; equity turnover is negligible",
     "expiry_rule": "no listed derivatives of any kind; there is no expiry clock in this country",
     "holidays": "the national feriado calendar, including both Carnaval days and Todos Santos",
     "notes": "AN ALMOST PURELY FIXED-INCOME EXCHANGE. It is registered so that a study does not "
              "go looking for a Bolivian equity channel; the executable legs for this country "
              "are the metals, the energy complex, the softs and the regional EM pairs"},
    {"name": "The bolsin and the casas de cambio (the two boliviano markets)",
     "index_symbols": (), "open_local": "09:00", "close_local": "17:00",
     "open_utc": "13:00", "close_utc": "21:00", "dst_rule": "none: UTC-4 all year",
     "auction": "the BCB's bolsin sells dollars at the official rate to whoever is allocated "
                "them; the casas de cambio clear everyone else at the parallel rate",
     "expiry_rule": "no forwards, no options, no NDF market the desk can read",
     "holidays": "the banking calendar",
     "notes": "TWO PRICES FOR ONE CURRENCY, and the spread between them is the only continuously "
              "observable measure of how binding the exchange control has become"},
    {"name": "The landlocked export gate: Arica and Ilo, plus the Paraguay-Parana waterway",
     "index_symbols": (), "open_local": "00:00", "close_local": "23:59",
     "open_utc": "04:00", "close_utc": "03:59", "dst_rule": "none: UTC-4 all year",
     "auction": "none; the transit is governed by treaty and by the foreign port's schedule",
     "expiry_rule": "no expiry; the barge convoy and the sailing schedule are the clock",
     "holidays": "foreign ports keep foreign calendars, which is its own confound",
     "notes": "BOLIVIA HAS NO COAST. Mineral concentrate leaves through Arica (Chile) or Ilo "
              "(Peru) and soy leaves down the Paraguay-Parana waterway, whose LOW-WATER YEARS "
              "are a real, dated, published export constraint -- a physical mechanism the "
              "coastal packs in this command simply do not have"},
)

SESSION_WINDOWS: tuple[dict[str, Any], ...] = (
    {"name": "bo_bcb_publication", "start_utc": "15:00", "end_utc": "19:00",
     "notes": "the BCB's statistical publications land inside the La Paz business afternoon; "
              "UTC-4 all year, so the window never moves"},
    {"name": "bo_bbv_session", "start_utc": "13:00", "end_utc": "19:00",
     "notes": "the Bolsa Boliviana de Valores cash session"},
    {"name": "bo_parallel_market", "start_utc": "13:00", "end_utc": "21:00",
     "notes": "the casas de cambio and the street market, which run past the banking close and "
              "are where the second price is actually made"},
    {"name": "bo_gas_day", "start_utc": "10:00", "end_utc": "14:00",
     "notes": "the YPFB nomination window against the Brazil and Argentina contracts"},
    {"name": "bo_lme_overlap", "start_utc": "11:00", "end_utc": "13:00",
     "notes": "the LME ring, where a Bolivian tin or zinc headline is priced before La Paz opens"},
)

RELEASE_CLASSES: tuple[dict[str, Any], ...] = (
    {"name": "BCB reservas internacionales netas and their COMPOSITION", "cadence": "monthly",
     "time_utc": "16:00", "source": "Banco Central de Bolivia", "actual_series": "BCB:rin",
     "expected_series": "UNMEASURED",
     "notes": "the level matters less than the split: gold against liquid dollars against IMF "
              "assets. The liquid dollar line is the one that went first"},
    {"name": "INE indice de precios al consumidor", "cadence": "monthly", "time_utc": "15:00",
     "source": "Instituto Nacional de Estadistica", "actual_series": "INE:ipc",
     "expected_series": "UNMEASURED",
     "notes": "a pegged economy is supposed to import the anchor's inflation; when the parallel "
              "premium opened, the official CPI and the imported-goods price diverged"},
    {"name": "Aduana Nacional import and export detail by tariff line", "cadence": "monthly",
     "time_utc": "16:00", "source": "Aduana Nacional de Bolivia",
     "actual_series": "ADUANA:importaciones", "expected_series": "n/a",
     "notes": "THE FUEL IMPORT BILL LIVES HERE, by volume and by value; it is the reserve drain "
              "in a customs series rather than in a monetary one"},
    {"name": "YPFB gas export volumes to Brazil and Argentina", "cadence": "monthly",
     "time_utc": "16:00", "source": "YPFB and the Ministerio de Hidrocarburos",
     "actual_series": "YPFB:exportacion_gas", "expected_series": "n/a",
     "notes": "the measured structural decline; the Argentina line went to zero and then "
              "REVERSED direction as Vaca Muerta gas began transiting north"},
    {"name": "Ministerio de Mineria and SERGEOMIN production and export values",
     "cadence": "monthly", "time_utc": "16:00", "source": "Ministerio de Mineria y Metalurgia",
     "actual_series": "MIN:produccion_minera", "expected_series": "n/a",
     "notes": "tin, zinc, silver, lead and gold by mineral and by producer type -- state, "
              "medium and COOPERATIVE, which is the split that matters politically"},
    {"name": "The parallel boliviano quote as reported by the press and the casas de cambio",
     "cadence": "daily", "time_utc": "14:00", "source": "the financial press and the exchange "
                                                        "houses",
     "actual_series": "PRESS:tipo_de_cambio_paralelo", "expected_series": "n/a",
     "notes": "PRESS_REPORTED by construction: it is a fragmented market and two sources "
              "disagree on the same day, so every premium computed from it carries an error bar"},
    {"name": "Gaceta Oficial supreme decrees and laws", "cadence": "irregular",
     "time_utc": "UNMEASURED", "source": "Gaceta Oficial del Estado Plurinacional",
     "actual_series": "GACETA:normas", "expected_series": "n/a",
     "notes": "where Ley 1503, the fuel-price decrees and the export-quota resolutions become "
              "citable; the decree is the event and the press report is the same-day stamp"},
    {"name": "INE and ANAPO soy harvest and export statistics", "cadence": "seasonal",
     "time_utc": "16:00", "source": "INE, ANAPO and IBCE",
     "actual_series": "INE:exportacion_soya", "expected_series": "n/a",
     "notes": "the verano and invierno crops, the crushing margin and the export cupo; the "
              "waterway's water level is the physical constraint on all of it"},
)

# --------------------------------------------------------------------------- holidays
#: FIXED national feriados, each with the year it became one. TWO of them were created by the
#: 2009-2010 plurinational settlement -- the Estado Plurinacional day (22 January) and the Andean
#: new year, Willkakuti (21 June) -- so a study pooling 2005-2026 mislabels two closed days a
#: year for the early half of its sample. Rows are (month, day, name, first_year).
FIXED_NATIONAL: tuple[tuple[int, int, str, int], ...] = (
    (1, 1, "Ano Nuevo", 0),
    (1, 22, "Dia del Estado Plurinacional de Bolivia", 2010),
    (5, 1, "Dia del Trabajo", 0),
    (6, 21, "Ano Nuevo Andino Amazonico y del Chaco / Willkakuti", 2010),
    (8, 6, "Dia de la Independencia", 0),
    (11, 2, "Dia de Todos los Santos / Todos Santos", 0),
    (12, 25, "Navidad", 0),
)
#: THE EASTER-DERIVED NATIONAL FERIADOS, as offsets from Easter Sunday. Bolivia closes for BOTH
#: Carnaval days -- the Carnaval de Oruro is a UNESCO-listed event and the mining departments
#: stop for the whole week around it -- for Good Friday, and for Corpus Christi.
EASTER_NATIONAL: tuple[tuple[int, str], ...] = (
    (-48, "Lunes de Carnaval / Anata"),
    (-47, "Martes de Carnaval"),
    (-2, "Viernes Santo"),
    (60, "Corpus Christi"),
)
#: THE DEPARTMENTAL CALENDAR. Not national closures, and the two that matter most to this pack
#: are the MINING departments: Oruro (10 February, the week of the Carnaval de Oruro and the home
#: of Huanuni tin) and Potosi (10 November, Cerro Rico). A production study that does not carry
#: them will read a departmental holiday as a stoppage. Rows are (month, day, department, name).
DEPARTMENTAL_DAYS: tuple[tuple[int, int, str, str], ...] = (
    (2, 10, "Oruro", "Efemerides de Oruro"),
    (4, 15, "Tarija", "Efemerides de Tarija"),
    (5, 25, "Chuquisaca", "Efemerides de Chuquisaca (Sucre)"),
    (7, 16, "La Paz", "Efemerides de La Paz"),
    (9, 14, "Cochabamba", "Efemerides de Cochabamba"),
    (9, 24, "Santa Cruz y Pando", "Efemerides de Santa Cruz y de Pando"),
    (11, 10, "Potosi", "Efemerides de Potosi (Cerro Rico)"),
    (11, 18, "Beni", "Efemerides del Beni"),
)
#: ONE-OFF closures and national non-working days no recurring rule produces. Each carries its
#: own status inside the text: a census day and an election day are decreed, carry movement
#: restrictions and a dry law, and stop the country -- but this pack has not read the decree
#: number for them and says so rather than implying it has.
DECLARED_CLOSURES: dict[date, str] = {
    date(2024, 3, 23): "Censo Nacional de Poblacion y Vivienda: a decreed national non-working "
                       "day with movement restrictions [DECREE_REPORTED -- a Saturday, so no "
                       "session was lost; confirm the DS number in the Gaceta Oficial]",
    date(2025, 8, 17): "General election, first round: a decreed non-working day with movement "
                       "restrictions and a dry law [DECREE_REPORTED -- a Sunday, so no session "
                       "was lost]",
    date(2025, 10, 19): "General election, presidential run-off [DECREE_REPORTED -- a Sunday]",
}

#: THE PEG. One number, unchanged since 2011-11-02, through a reserve collapse and two
#: governments. `OFFICIAL_SELL` is the bolsin rate an importer pays when it is allocated dollars.
OFFICIAL_SELL: float = 6.96
OFFICIAL_BUY: float = 6.86
PEG_SINCE: date = date(2011, 11, 2)
#: THE STRESS BUCKETS the premium is read into. These are the pack's own thresholds, declared
#: rather than fitted, so a study that uses them is using a stated rule and not a tuned one.
PREMIUM_BUCKETS: tuple[tuple[float, str], ...] = (
    (0.02, "PEG_HOLDING"),        # under 2%: the parallel market is a convenience, not a signal
    (0.10, "RATIONING"),          # 2-10%: allocation is binding but the peg is not questioned
    (0.30, "STRESS"),             # 10-30%: importers price off the parallel rate
    (0.60, "SEVERE"),             # 30-60%: the official rate is an accounting fiction
)
PREMIUM_EXTREME = "DISLOCATED"    # above 60%: two economies with two price levels

#: THE PARALLEL-MARKET EPISODES, dated rather than quoted. Typing a precise parallel rate for a
#: given day would be a false precision: the market is fragmented and two sources disagree by
#: several per cent on the same afternoon. So the pack dates the EPISODES and computes the
#: premium from whatever quote the collector actually fetches. Rows are (date, what, status).
PARALLEL_EPISODES: tuple[tuple[date, str, str], ...] = (
    (date(2023, 2, 1), "queues form at the BCB's own counters and a visible parallel quote "
                       "appears for the first time in a decade", "PRESS_REPORTED"),
    (date(2023, 3, 1), "the BCB begins selling dollars directly to the public to defend the "
                       "official rate", "PRESS_REPORTED"),
    (date(2023, 5, 8), "Ley 1503 authorises the BCB to trade its reserve gold", "PRESS_REPORTED"),
    (date(2024, 3, 1), "the premium becomes a routinely published number in the business press",
     "PRESS_REPORTED"),
    (date(2024, 10, 1), "fuel queues and import-payment delays; the premium widens sharply",
     "PRESS_REPORTED"),
    (date(2025, 3, 1), "importers openly price off the parallel rate and the official rate "
                       "functions as an accounting convention", "PRESS_REPORTED"),
)

#: THE STATUTORY GOLD AUTHORITY. Ley 1503 is the reason a Bolivian reserve decision is a DATED
#: XAUUSD supply observable instead of an inference from an IMF table months later.
GOLD_AUTHORITY: tuple[tuple[date, str, str], ...] = (
    (date(2023, 5, 8), "Ley 1503 (the 'Ley del Oro') authorises the Banco Central to trade its "
                       "gold reserves and to buy domestic gold production", "PRESS_REPORTED"),
    (date(2023, 7, 1), "the BCB begins reporting gold operations under the new authority",
     "PRESS_REPORTED"),
    (date(2024, 1, 1), "domestic gold purchases become a stated route to rebuilding reserves, "
                       "with the cooperative sector as the counterparty", "PRESS_REPORTED"),
)

#: THE GAS MILESTONES. A structural decline with a published schedule, and a pipeline that
#: changed direction. Rows are (date, what, status).
GAS_MILESTONES: tuple[tuple[date, str, str], ...] = (
    (date(1999, 7, 1), "first deliveries under the twenty-year Gas Supply Agreement with "
                       "Brazil through the GASBOL pipeline", "PRESS_REPORTED"),
    (date(2006, 5, 1), "Decreto Supremo 28701 nationalises the hydrocarbons sector",
     "PRESS_REPORTED"),
    (date(2014, 12, 31), "gas export volumes peak; the structural decline begins and is visible "
                         "in the YPFB monthly series from here on", "PRESS_REPORTED"),
    (date(2019, 12, 31), "the original twenty-year Brazil GSA expires and is replaced by "
                         "shorter, more flexible arrangements", "PRESS_REPORTED"),
    (date(2023, 12, 31), "the Argentina export contract winds down as Vaca Muerta displaces "
                         "Bolivian gas in the Argentine north", "PRESS_REPORTED"),
    (date(2024, 10, 1), "THE REVERSAL: Argentine gas begins moving NORTH through Bolivian pipe "
                        "toward Brazil under transit agreements -- the same steel carrying the "
                        "opposite flow", "PRESS_REPORTED"),
)

#: THE LITHIUM AGREEMENTS, signed and cancelled on dated, published timelines. Rows are
#: (date, what, status). This table is the `cl` and `ar` interaction's own evidence.
LITHIUM_MILESTONES: tuple[tuple[date, str, str], ...] = (
    (date(2017, 4, 1), "Ley 928 creates Yacimientos de Litio Bolivianos (YLB) as the state "
                       "monopoly over the Uyuni resource", "PRESS_REPORTED"),
    (date(2019, 11, 4), "the ACISA joint venture for Uyuni is cancelled by decree amid the "
                        "Potosi protests", "PRESS_REPORTED"),
    (date(2023, 1, 20), "an agreement with a Chinese consortium for direct-extraction plants is "
                        "announced", "PRESS_REPORTED"),
    (date(2023, 6, 29), "a further agreement with a Russian counterparty is announced",
     "PRESS_REPORTED"),
    (date(2024, 9, 1), "the agreements are sent to the legislature and stall there; no "
                       "commercial-scale output follows", "PRESS_REPORTED"),
)

#: THE BLOQUEO. Road blockade is Bolivia's national political instrument, and it is a LOGISTICS
#: shock: a landlocked country with two export corridors and one highland trunk road. Rows are
#: (start, end, site, what, status). Every row is PRESS_REPORTED and hypothesis-grade.
BLOCKADE_EPISODES: tuple[tuple[date, date, str, str, str], ...] = (
    (date(2019, 10, 21), date(2019, 11, 12), "national",
     "the post-election crisis: blockades close La Paz, El Alto, Santa Cruz and the "
     "Senkata fuel plant", "PRESS_REPORTED"),
    (date(2020, 8, 1), date(2020, 8, 14), "national trunk roads",
     "blockades over the postponed election; oxygen and fuel convoys halted", "PRESS_REPORTED"),
    (date(2022, 10, 22), date(2022, 11, 26), "Santa Cruz",
     "the 36-day paro civico over the census date; the soy and export corridor stops",
     "PRESS_REPORTED"),
    (date(2024, 6, 26), date(2024, 6, 26), "La Paz",
     "an attempted military takeover of the Plaza Murillo, resolved within hours",
     "PRESS_REPORTED"),
    (date(2024, 10, 14), date(2024, 11, 8), "Cochabamba and the trunk road",
     "blockades by the Evo Morales faction close the Cochabamba axis; fuel and food shortages "
     "spread", "PRESS_REPORTED"),
    (date(2025, 1, 13), date(2025, 1, 24), "Cochabamba and Oruro",
     "renewed blockades on the highland trunk road", "PRESS_REPORTED"),
    (date(2025, 6, 2), date(2025, 6, 20), "national trunk roads",
     "pre-election blockades and fuel queues", "PRESS_REPORTED"),
)


def easter(year: int) -> date:
    """Easter Sunday by the ANONYMOUS GREGORIAN ALGORITHM. Bolivia's Carnaval (Easter minus 48
    and 47), Good Friday (minus 2) and Corpus Christi (plus 60) are ALL derived from it, so four
    of this country's national closures are computed rather than typed."""
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
    """Lunes and Martes de Carnaval -- Easter minus 48 and 47. BOTH are national feriados in
    Bolivia, and the mining department of Oruro effectively stops for the whole week."""
    base = easter(year)
    return base - timedelta(days=48), base - timedelta(days=47)


def corpus_christi(year: int) -> date:
    """Corpus Christi: Easter plus 60 days, a national feriado."""
    return easter(year) + timedelta(days=60)


def easter_holidays(year: int) -> dict[date, str]:
    """The four Easter-derived national closures for a year."""
    base = easter(year)
    return {base + timedelta(days=off): name for off, name in EASTER_NATIONAL}


def national_holidays(year: int) -> dict[date, str]:
    """The national feriado table: the fixed days in force IN THAT YEAR, the four Easter-derived
    days, and the declared one-off non-working days. NO GENERAL WEEKEND SUBSTITUTION -- a
    Bolivian feriado on a Sunday is lost; the government occasionally decrees a puente by supreme
    decree, which is a DECLARED closure and never a rule."""
    out: dict[date, str] = {}
    for m, d, name, since in FIXED_NATIONAL:
        if year >= since:
            out[date(year, m, d)] = name
    out.update(easter_holidays(year))
    for day, name in DECLARED_CLOSURES.items():
        if day.year == year:
            out[day] = name
    return dict(sorted(out.items()))


def bank_holidays(year: int) -> dict[date, str]:
    """The banking calendar; it coincides with the national one."""
    return national_holidays(year)


def market_holidays(year: int) -> dict[date, str]:
    """BBV closed days: the national calendar on WEEKDAYS only. A Sunday feriado costs no
    session and must never enter a holiday-liquidity sample as one."""
    return {d: n for d, n in bank_holidays(year).items() if d.weekday() < 5}


def departmental_days(year: int) -> dict[date, str]:
    """The departmental calendar for a year. Oruro (10 February) and Potosi (10 November) are the
    two that matter here: they are the tin and silver departments, and a production series that
    does not carry them reads a holiday as a stoppage."""
    return {date(year, m, d): f"{name} ({dept})"
            for m, d, dept, name in DEPARTMENTAL_DAYS}


def mining_department_days(year: int) -> dict[date, str]:
    """Only Oruro's and Potosi's days -- the subset that touches tin, silver, zinc and lead."""
    return {day: name for day, name in departmental_days(year).items()
            if "Oruro" in name or "Potosi" in name}


def is_market_holiday(day: date) -> bool:
    return day in market_holidays(day.year)


def new_holidays_since_2010() -> tuple[tuple[int, int, str], ...]:
    """The two feriados the plurinational settlement created: 22 January and 21 June."""
    return tuple((m, d, name) for m, d, name, since in FIXED_NATIONAL if since == 2010)


def parallel_premium(official: float = OFFICIAL_SELL, parallel: float = OFFICIAL_SELL) -> float:
    """THE STATE VARIABLE OF THIS PACK: how far the second price of the boliviano sits from the
    first. Pure arithmetic on two published numbers -- `parallel / official - 1` -- so it carries
    no model and no fitted parameter, and a premium of 0.0 means the peg is doing its job.

    A ZeroDivisionError is impossible on a real quote and would be a corrupt input, so an
    official rate of zero returns 0.0 and the caller's UNMEASURED path handles it.
    """
    if not official:
        return 0.0
    return float(parallel) / float(official) - 1.0


def peg_stress_state(premium: float) -> str:
    """The premium read into a DECLARED bucket. The thresholds are stated in PREMIUM_BUCKETS
    rather than fitted, so a study using them is using a rule somebody wrote down in advance."""
    for edge, label in PREMIUM_BUCKETS:
        if premium < edge:
            return label
    return PREMIUM_EXTREME


def reserve_report_months(year: int) -> tuple[date, ...]:
    """The monthly rhythm this pack conditions on in place of a policy calendar: the last day of
    each month, when the BCB's reserve and monetary statistics are stamped. The BCB publishes no
    meeting calendar because the peg IS the policy, and inventing one would be inventing an
    institution (L1.28a)."""
    out: list[date] = []
    for month in range(1, 13):
        nxt = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
        out.append(nxt - timedelta(days=1))
    return tuple(out)


def blockade_episodes(status: str = "PRESS_REPORTED") -> tuple[tuple[date, date, str, str], ...]:
    """The declared blockade episodes at or above a confidence label."""
    order = {"PRESS_REPORTED": 0, "GAZETTE_VERIFIED": 1}
    floor = order.get(status, 0)
    return tuple((lo, hi, site, what) for lo, hi, site, what, st in BLOCKADE_EPISODES
                 if order.get(st, 0) >= floor)


def is_blockade_day(day: date) -> bool:
    """True when `day` falls inside a DECLARED bloqueo episode. In a landlocked country with two
    export corridors this is a LOGISTICS state, not only a political one."""
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


HOLIDAYS_RULE: dict[str, Any] = {
    "kind": "computed_from_statute_plus_declared_table",
    "authority": "Decreto Supremo 14260 and its successors fix the feriados nacionales "
                 "inexcusables; the Estado Plurinacional day (22 January) and the Andean new "
                 "year (21 June) were added under the 2009-2010 plurinational settlement; the "
                 "government decrees one-off non-working days (a census, an election) by "
                 "supreme decree in the Gaceta Oficial",
    "rule": "SEVEN fixed national days -- 1 Jan, 22 Jan (Estado Plurinacional, from 2010), "
            "1 May, 21 Jun (Ano Nuevo Andino / Willkakuti, from 2010), 6 Aug (Independencia), "
            "2 Nov (Todos Santos) and 25 Dec -- PLUS FOUR EASTER-DERIVED days computed with the "
            "anonymous Gregorian algorithm in `easter(year)`: Lunes de Carnaval (Easter minus "
            "48), Martes de Carnaval (minus 47), Viernes Santo (minus 2) and Corpus Christi "
            "(plus 60). NO GENERAL WEEKEND SUBSTITUTION: a feriado on a Sunday is lost, and a "
            "puente is a decreed one-off rather than a rule. The NINE DEPARTMENTS keep their "
            "own efemerides, and the two that matter to this pack are the MINING ones -- Oruro "
            "on 10 February and Potosi on 10 November -- carried separately in "
            "`departmental_days(year)` because they close mines and not the bourse.",
    "years": (2024, 2025, 2026),
    "weekend": "Saturday and Sunday",
    "national_rule": "see `rule`; `national_holidays(year)` is the computed form",
    "market_rule": "the national calendar on weekdays; the BBV keeps 09:00-15:00 "
                   "America/La_Paz in every month because Bolivia has no daylight saving",
    "departmental_rule": "`departmental_days(year)`; `mining_department_days(year)` is the "
                         "Oruro and Potosi subset",
    "statute_break": "22 January and 21 June became national holidays with the plurinational "
                     "settlement of 2009-2010; a study pooling back past that mislabels two "
                     "closed days a year",
    "table": {y: {d.isoformat(): n for d, n in national_holidays(y).items()}
              for y in (2024, 2025, 2026)},
    "status": {2024: "STATUTORY for the fixed days, COMPUTED for the four Easter-derived days, "
                     "DECREE_REPORTED for the census non-working day",
               2025: "STATUTORY and COMPUTED; the two election days are DECREE_REPORTED and "
                     "both fell on a Sunday, so no session was lost to either",
               2026: "STATUTORY and COMPUTED; the Easter dates are computed and certain, and "
                     "no one-off decree for 2026 is published yet"},
    "known_dates": {
        "2024-02-12": "Lunes de Carnaval (Easter 2024 is 31 March)",
        "2024-05-30": "Corpus Christi 2024",
        "2025-03-03": "Lunes de Carnaval (Easter 2025 is 20 April)",
        "2025-06-21": "Willkakuti, the Andean new year, a national feriado since 2010",
        "2026-02-16": "Lunes de Carnaval (Easter 2026 is 5 April)",
        "2026-11-02": "Todos Santos, fixed and certain in every year",
    },
    "fn": market_holidays,
    "national_fn": national_holidays,
    "bank_fn": bank_holidays,
    "departmental_fn": departmental_days,
    "easter_fn": easter,
    "carnaval_fn": carnaval,
}

# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "BCB reservas internacionales netas and their composition",
     "root": "https://www.bcb.gob.bo/?q=indicadores_reservas",
     "fields": ("rin_total_usd", "oro_usd", "divisas_liquidas_usd", "deg_fmi_usd"),
     "frequency": "monthly", "snapshot": "month end", "publish_utc": "16:00", "lag_days": 15,
     "licence": "free, public", "available": True,
     "why": "THE PEG'S OWN BALANCE SHEET. The headline level understates the stress; the SPLIT "
            "is the signal, because the liquid dollar component fell to a few hundred million "
            "while the gold line carried most of what remained",
     "pit_warning": "the composition disclosure has changed format more than once, so a long "
                    "series must be reconciled by hand before it is used as a state"},
    {"name": "The parallel boliviano quote as reported by the press and the casas de cambio",
     "root": "https://www.eldeber.com.bo/economia",
     "fields": ("tipo_de_cambio_paralelo_compra", "tipo_de_cambio_paralelo_venta", "fuente"),
     "frequency": "daily", "snapshot": "intraday", "publish_utc": "14:00", "lag_days": 0,
     "licence": "publisher terms", "available": True,
     "why": "the second price of the same currency; the only continuously observable measure of "
            "how binding the exchange control has become, and the input to `parallel_premium()`",
     "pit_warning": "PRESS_REPORTED AND FRAGMENTED: two sources disagree by several per cent on "
                    "the same afternoon, so a premium from one quote is a point estimate with "
                    "an unstated error bar and must never be promoted as a precise level"},
    {"name": "Aduana Nacional fuel import volumes and values",
     "root": "https://www.aduana.gob.bo/aduana7/estadisticas",
     "fields": ("importacion_diesel_volumen", "importacion_gasolina_volumen", "valor_cif_usd"),
     "frequency": "monthly", "snapshot": "calendar month", "publish_utc": "16:00",
     "lag_days": 35, "licence": "free, public", "available": True,
     "why": "the reserve drain as a physical series: how many litres of subsidised diesel the "
            "country bought in dollars and sold in bolivianos at a decreed price",
     "pit_warning": "monthly and five weeks late; it explains a quarter, never a week"},
    {"name": "YPFB gas export volumes to Brazil and Argentina",
     "root": "https://www.ypfb.gob.bo/",
     "fields": ("exportacion_brasil_mmm3d", "exportacion_argentina_mmm3d", "ingresos_usd"),
     "frequency": "monthly", "snapshot": "calendar month", "publish_utc": "16:00",
     "lag_days": 40, "licence": "free, public", "available": True,
     "why": "the dollar income side of the same balance the fuel import bill drains; the "
            "Argentina line went to zero and then reversed direction",
     "pit_warning": "the contractual price is fuel-oil-indexed and lagged, so revenue and "
                    "volume tell different stories and only the VOLUME is a physical series"},
    {"name": "CFTC Commitments of Traders, COMEX gold and silver",
     "root": "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm",
     "fields": ("managed_money_long", "managed_money_short", "open_interest"),
     "frequency": "weekly", "snapshot": "Tuesday", "publish_utc": "19:30", "lag_days": 3,
     "licence": "public domain (US government work)", "available": True,
     "why": "the executable metals' own positioning; a sovereign gold sale into a crowded "
            "managed-money long is a different trade from the same sale into a flat book",
     "pit_warning": "Tuesday snapshot published Friday, so a mid-week sovereign operation is "
                    "invisible for a week"},
    {"name": "a CFTC or exchange-traded BOLIVIANO positioning series",
     "root": "", "fields": (), "frequency": "n/a", "snapshot": "", "publish_utc": "",
     "lag_days": 0, "licence": "", "available": False,
     "why": "DECLARED ABSENT: no BOB future, forward or NDF trades on any venue the desk can "
            "read, and no COT contract exists for the boliviano",
     "pit_warning": "DOES NOT EXIST: boliviano positioning is UNMEASURED and is never proxied "
                    "by the BRL or MXN COT legs, which are positions in floating currencies and "
                    "say nothing about a pegged one"},
    {"name": "a foreign-holdings series for Bolivian local debt",
     "root": "", "fields": (), "frequency": "n/a", "snapshot": "", "publish_utc": "",
     "lag_days": 0, "licence": "", "available": False,
     "why": "DECLARED ABSENT: the domestic market is bank- and pension-held with negligible "
            "foreign participation, and no non-resident holding series is published",
     "pit_warning": "DOES NOT EXIST: the Peruvian and Brazilian 'foreign share of the local "
                    "curve' observable has no Bolivian counterpart, and a study that reaches "
                    "for one is importing another country's mechanism"},
)

# --------------------------------------------------------------------------- terminology
#: FOUR LANGUAGES, AND THE CONSTITUTION MEANS IT. Article 5 of the 2009 constitution makes
#: Spanish and THIRTY-SIX indigenous languages official; the three that carry economic weight
#: here are Quechua (Potosi, Cochabamba, the cooperative mining belt), Aymara (La Paz, El Alto,
#: Oruro, the altiplano and the blockade repertoire) and Guarani (the Chaco, which is where the
#: gas is and where the Asamblea del Pueblo Guarani negotiates the royalties). A Spanish-only
#: crawl of Bolivia misses the two constituencies that can stop a mine and a gas field.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "BO-A": ("Banco Central de Bolivia", "tipo de cambio oficial", "bolsín", "tipo de cambio "
             "fijo", "6,96 bolivianos", "encaje legal", "política cambiaria",
             "devaluación", "anclaje cambiario", "regulación monetaria",
             "qullqi (Quechua/Aymara: silver, and the word for money)"),
    "BO-B": ("reservas internacionales netas", "RIN", "oro monetario", "divisas líquidas",
             "Ley 1503", "Ley del Oro", "venta de oro", "reservas de oro",
             "derechos especiales de giro", "respaldo de la moneda",
             "quri (Quechua/Aymara: gold)"),
    "BO-C": ("dólar paralelo", "mercado paralelo", "brecha cambiaria", "casa de cambio",
             "cambistas", "escasez de dólares", "racionamiento de divisas", "cupo de dólares",
             "importadores", "cotización libre", "qhathu (Aymara: the market)"),
    "BO-D": ("estaño", "COMIBOL", "Huanuni", "Colquiri", "Vinto", "cooperativas mineras",
             "FENCOMIN", "concentrado", "zinc", "plata", "plomo", "Cerro Rico",
             "San Cristóbal", "regalía minera", "ingenio minero",
             "titi (Quechua: lead)", "qullqi (Quechua: silver)",
             "ayllu (Quechua/Aymara: the community that decides)",
             "ch'alla (Aymara: the offering made before work begins at a mine)",
             "mink'a (Quechua: the collective work party)"),
    "BO-E": ("oro", "minería aurífera", "cooperativas auríferas", "mercurio",
             "exportación de oro", "compra de oro", "oro amonedado", "río Madre de Dios",
             "barranquillas", "Pachamama", "quri (Quechua: gold)",
             "yatiri (Aymara: the ritual specialist who blesses the working)"),
    "BO-F": ("litio", "Salar de Uyuni", "YLB", "Yacimientos de Litio Bolivianos",
             "carbonato de litio", "extracción directa", "salmuera", "convenio",
             "planta industrial", "Potosí", "COMCIPO",
             "jach'a qhathu (Aymara: the great market)",
             "allpa (Quechua: the earth the concession is over)"),
    "BO-G": ("gas natural", "YPFB", "exportación de gas", "GSA", "contrato de suministro",
             "GASBOL", "Petrobras", "ENARSA", "Vaca Muerta", "reversión del flujo",
             "declinación de reservas", "certificación de reservas", "megacampo",
             "Ñande Reko (Guaraní: our way of being, the APG's own political concept)",
             "ñemboati (Guaraní: the assembly that decides)",
             "Itika Guasu (Guaraní: the territory the gas fields sit on)",
             "yvy (Guaraní: land)", "Kuruyuki (Guaraní: the battle the APG dates itself from)"),
    "BO-H": ("subvención", "subsidio a los combustibles", "diésel", "gasolina",
             "importación de carburantes", "ANH", "gasolinazo", "precio congelado",
             "contrabando de combustible", "surtidor", "cola de combustible",
             "factura dolarizada"),
    "BO-I": ("soya", "ANAPO", "cupo de exportación", "certificado de abastecimiento interno",
             "biodiésel", "etanol", "Santa Cruz", "campaña de verano", "campaña de invierno",
             "hidrovía Paraguay-Paraná", "bajante del río", "torta de soya", "aceite crudo",
             "chakra (Quechua: the cultivated plot)"),
    "BO-J": ("crédito del BCB", "empresas públicas", "TGN", "déficit fiscal",
             "bonos BCB directo", "deuda interna", "emisión monetaria", "Tesoro General",
             "presupuesto general del estado", "transferencias condicionadas"),
    "BO-K": ("bloqueo de caminos", "paro cívico", "marcha", "conflicto social",
             "Defensoría del Pueblo", "COB", "Central Obrera Boliviana", "comité cívico",
             "estado de emergencia", "desabastecimiento", "corte de ruta",
             "thakhi (Aymara: the road, and the thing a bloqueo closes)",
             "mallku (Aymara: the condor, and the community authority)",
             "llaqta (Quechua: the town, the people)",
             "wañuy (Quechua: death, the word the casualty counts were reported in)"),
    "BO-L": ("feriado", "Carnaval de Oruro", "Anata Andino", "Todos Santos", "Corpus Christi",
             "Año Nuevo Andino", "efemérides departamental", "Gaceta Oficial",
             "decreto supremo", "día no laborable", "censo", "elecciones generales",
             "Willkakuti (Aymara: the return of the sun, 21 June)",
             "anata (Aymara: carnival)",
             "jallu pacha (Aymara: the rainy season that closes the altiplano roads)",
             "awti pacha (Aymara: the dry season the concentrate moves in)"),
    "BO-M": ("Bolsa Boliviana de Valores", "ASFI", "agencia de bolsa", "bono soberano",
             "riesgo país", "calificación crediticia", "FMI", "artículo IV",
             "CAF", "FONPLATA", "financiamiento externo", "servicio de la deuda"),
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

#: All four of this country's working languages use Latin script, so "native script" is a
#: VOCABULARY test rather than a codepoint one. Spanish is detected by its diacritics -- an
#: English glossary of Bolivia has none -- and the three indigenous languages by their own words.
_SPANISH_DIACRITICS = "áéíóúüñÁÉÍÓÚÜÑ¿¡"
QUECHUA_MARKERS: tuple[str, ...] = (
    "qullqi", "quri", "titi", "ayllu", "llaqta", "mink'a", "allpa", "chakra", "wañuy",
    "Pachamama")
AYMARA_MARKERS: tuple[str, ...] = (
    "thakhi", "mallku", "ch'alla", "Willkakuti", "anata", "qhathu", "jach'a", "yatiri",
    "jallu pacha", "awti pacha")
GUARANI_MARKERS: tuple[str, ...] = (
    "Ñande Reko", "ñemboati", "Itika Guasu", "yvy", "Kuruyuki")
SPANISH_MARKERS: tuple[str, ...] = (
    "tipo de cambio oficial", "dólar paralelo", "brecha cambiaria", "reservas internacionales",
    "Ley del Oro", "cooperativas mineras", "Salar de Uyuni", "exportación de gas",
    "subvención", "cupo de exportación", "bloqueo de caminos", "paro cívico",
    "Carnaval de Oruro", "hidrovía Paraguay-Paraná", "Gaceta Oficial")


def has_spanish_diacritic(text: str) -> bool:
    """True when the text carries a Spanish diacritic. An English translation of a Bolivian
    release has none, which is what makes this a usable native-language test on Latin script."""
    return any(ch in _SPANISH_DIACRITICS for ch in str(text))


def has_quechua(text: str) -> bool:
    return any(m in str(text) for m in QUECHUA_MARKERS)


def has_aymara(text: str) -> bool:
    return any(m in str(text) for m in AYMARA_MARKERS)


def has_guarani(text: str) -> bool:
    """True when the text carries a declared Guarani term. The Chaco gas fields sit on Guarani
    territory and the APG negotiates the royalties, so this is not decoration."""
    return any(m in str(text) for m in GUARANI_MARKERS)


def _flat_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> set[str]:
    rows = TERMINOLOGY if terminology is None else terminology
    return {t for terms in rows.values() for t in terms}


def spanish_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    flat = _flat_terms(terminology)
    return [m for m in SPANISH_MARKERS if any(m in t for t in flat)]


def quechua_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    flat = _flat_terms(terminology)
    return [m for m in QUECHUA_MARKERS if any(m in t for t in flat)]


def aymara_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    flat = _flat_terms(terminology)
    return [m for m in AYMARA_MARKERS if any(m in t for t in flat)]


def guarani_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    flat = _flat_terms(terminology)
    return [m for m in GUARANI_MARKERS if any(m in t for t in flat)]


def accented_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
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
        "bo_bcb", "Banco Central de Bolivia: reserves and their composition, the official "
                  "exchange rate, the boletin estadistico, the monetary policy report, the "
                  "retail bond programmes", layer="official",
        roots=("https://www.bcb.gob.bo/?q=indicadores_reservas",
               "https://www.bcb.gob.bo/?q=publicaciones_estadisticas",
               "https://www.bcb.gob.bo/?q=politica_monetaria"),
        queries=("reservas internacionales netas Bolivia", "tipo de cambio oficial bolsín",
                 "oro monetario reservas", "boletín estadístico BCB",
                 "informe de política monetaria", "bonos BCB directo",
                 "encaje legal resolución", "crédito del BCB a las empresas públicas",
                 "qullqi wasi reservas"),
        languages=("es",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public (bcb.gob.bo terms)",
        notes="THE COMPOSITION OF THE RESERVES IS THE SIGNAL, not the level: the liquid dollar "
              "component fell to a few hundred million while gold carried the rest, and the "
              "official rate did not move a centavo through any of it"),
    source_class(
        "bo_ine", "Instituto Nacional de Estadistica: the CPI, national accounts, foreign trade, "
                  "the census and the departmental series", layer="official",
        roots=("https://www.ine.gob.bo/index.php/estadisticas-economicas/",
               "https://www.ine.gob.bo/index.php/publicaciones/",
               "https://www.ine.gob.bo/index.php/comercio-exterior/"),
        queries=("índice de precios al consumidor Bolivia", "inflación mensual INE",
                 "producto interno bruto trimestral", "exportaciones e importaciones",
                 "balanza comercial", "censo de población y vivienda",
                 "estadísticas departamentales"),
        languages=("es",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="a pegged economy is supposed to import the anchor's inflation; when the parallel "
              "premium opened, the official CPI and the price of imported goods diverged, and "
              "the gap between them is one of this pack's few purely domestic observables"),
    source_class(
        "bo_mineria", "Ministerio de Mineria y Metalurgia, COMIBOL, SERGEOMIN and AJAM: "
                      "production by mineral and by producer type, the mining cadastre, "
                      "royalties and the cooperative sector", layer="official",
        roots=("https://mineria.gob.bo/", "https://www.comibol.gob.bo/",
               "https://www.sergeomin.gob.bo/", "https://www.ajam.gob.bo/"),
        queries=("producción minera por mineral", "estaño producción Huanuni",
                 "cooperativas mineras producción", "regalía minera departamental",
                 "exportación de concentrados", "padrón minero AJAM",
                 "fundición Vinto", "zinc plata plomo producción"),
        languages=("es",), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE PRODUCER-TYPE SPLIT IS THE POLITICS. State, medium-scale and COOPERATIVE are "
              "reported separately, and the cooperatives are both a large share of gold output "
              "and the most organised political bloc in the country"),
    source_class(
        "bo_ypfb_anh", "YPFB, the Ministerio de Hidrocarburos y Energias and the ANH: gas "
                       "export volumes, reserve certifications, fuel imports and the "
                       "administered pump price", layer="official",
        roots=("https://www.ypfb.gob.bo/", "https://www.hidrocarburos.gob.bo/",
               "https://www.anh.gob.bo/"),
        queries=("exportación de gas natural a Brasil", "exportación de gas a Argentina",
                 "certificación de reservas de gas", "importación de diésel volumen",
                 "precio del diésel surtidor", "subvención a los combustibles",
                 "reversión del flujo de gas", "contrato GSA Petrobras"),
        languages=("es",), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the two halves of the same balance sit here: the gas export income that is "
              "declining on a published schedule, and the subsidised fuel import bill that "
              "replaced it as the largest single use of dollars"),
    source_class(
        "bo_aduana", "Aduana Nacional de Bolivia: import and export detail by tariff line, "
                     "volume, value and origin", layer="official",
        roots=("https://www.aduana.gob.bo/aduana7/estadisticas",
               "https://www.aduana.gob.bo/aduana7/"),
        queries=("estadísticas de importación por partida", "importación de carburantes",
                 "exportación de minerales valor", "contrabando decomiso",
                 "importaciones por país de origen", "valor CIF importaciones"),
        languages=("es",), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE RESERVE DRAIN AS A PHYSICAL SERIES: litres of subsidised diesel bought in "
              "dollars and sold in bolivianos at a decreed price, counted at the border rather "
              "than inferred from a monetary aggregate"),
    source_class(
        "bo_gaceta", "Gaceta Oficial del Estado Plurinacional: every ley, decreto supremo and "
                     "resolucion in this pack becomes citable here", layer="official",
        roots=("http://www.gacetaoficialdebolivia.gob.bo/",
               "http://www.gacetaoficialdebolivia.gob.bo/normas/listado/"),
        queries=("Ley 1503 oro reservas", "decreto supremo subvención combustibles",
                 "decreto supremo día no laborable", "resolución cupo de exportación",
                 "decreto supremo nacionalización hidrocarburos", "ley de minería",
                 "normas legales listado"),
        languages=("es",), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE GAZETTE IS WHERE A DATE BECOMES A CITATION. Every PRESS_REPORTED row in this "
              "pack -- the gold authority, the fuel decrees, the census and election non-working "
              "days -- is promotable only once a Gaceta number is attached to it"),
    source_class(
        "bo_defensoria_conflictos", "Defensoria del Pueblo de Bolivia and the Ministerio de "
                                    "Gobierno: conflict reporting, states of emergency and the "
                                    "road-blockade record", layer="official",
        roots=("https://www.defensoria.gob.bo/", "https://www.abi.bo/",
               "https://www.mingobierno.gob.bo/"),
        queries=("conflictividad social informe", "bloqueo de caminos reporte",
                 "estado de emergencia decreto", "vías interrumpidas Bolivia",
                 "paro cívico movilización", "thakhi bloqueo", "mallku dirigencia"),
        languages=("es", "ay", "qu"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THINNER THAN PERU'S, AND THE DIFFERENCE MATTERS. Bolivia's ombudsman does not "
              "publish the same monthly case register the Peruvian one does, so the blockade "
              "series here must be assembled from the roads authority, the press and the civic "
              "committees -- which is why every episode row is PRESS_REPORTED"),
    # ---- institutional
    source_class(
        "bo_bbv_asfi", "Bolsa Boliviana de Valores and ASFI: the daily bulletin, issuer "
                       "filings, bank and pension statistics", layer="institutional",
        roots=("https://www.bbv.com.bo/", "https://www.asfi.gob.bo/",
               "https://www.bbv.com.bo/Boletines"),
        queries=("boletín diario bolsa boliviana de valores", "emisión de bonos corporativos",
                 "estadísticas del sistema financiero ASFI", "depósitos en dólares",
                 "cartera del sistema bancario", "agencia de bolsa informe"),
        languages=("es",), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="AN ALMOST PURELY FIXED-INCOME EXCHANGE with negligible equity turnover; "
              "registered so that a study does not look for a Bolivian equity channel. The ASFI "
              "deposit series IS useful: the dollar share of deposits is the household's own "
              "vote on the peg"),
    source_class(
        "bo_gremios", "The trade bodies: ANAPO and IBCE (soy and trade), CAINCO and the Santa "
                      "Cruz chambers, FENCOMIN (the mining cooperatives), the Camara Nacional "
                      "de Mineria and the Camara Boliviana de Hidrocarburos",
        layer="institutional",
        roots=("https://www.anapobolivia.org/", "https://ibce.org.bo/",
               "https://www.cainco.org.bo/", "https://www.cbhe.org.bo/"),
        queries=("ANAPO campaña de soya estimación", "IBCE comercio exterior boletín",
                 "cupo de exportación soya gremio", "FENCOMIN cooperativas pronunciamiento",
                 "cámara de hidrocarburos declinación", "CAINCO paro cívico comunicado"),
        languages=("es",), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="IBCE publishes trade data faster and more legibly than the state does, and ANAPO "
              "publishes the harvest estimate the export-quota fight is argued over; FENCOMIN "
              "is a political actor whose communiques precede a mining decree"),
    source_class(
        "bo_policy_institutes", "The policy institutes that publish openly: Fundacion Milenio, "
                                "INESAD, CEDLA and the Fundacion Jubileo", layer="institutional",
        roots=("https://fundacion-milenio.org/", "https://inesad.edu.bo/",
               "https://cedla.org/", "https://jubileobolivia.org.bo/"),
        queries=("informe de milenio economía boliviana", "déficit fiscal análisis Bolivia",
                 "reservas internacionales análisis", "renta petrolera Jubileo",
                 "subvención a los hidrocarburos costo fiscal", "CEDLA minería cooperativa"),
        languages=("es",), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="IN A COUNTRY WITH NO SELL-SIDE AND NO IMF PROGRAMME, these institutes are the "
              "only sustained independent analysis of the fiscal and reserve position; Fundacion "
              "Jubileo's hydrocarbon-rent series is the best public reconstruction of the gas "
              "income decline"),
    # ---- academic
    source_class(
        "bo_academic", "Bolivian economics research: UMSA's CIDES, the Universidad Catolica "
                       "Boliviana's IISEC, the Revista Latinoamericana de Desarrollo Economico, "
                       "plus the open aggregators", layer="academic",
        roots=("https://www.ucb.edu.bo/investigacion/", "https://cides.edu.bo/",
               "https://openalex.org/", "https://core.ac.uk/"),
        queries=("dolarización y desdolarización Bolivia", "tipo de cambio fijo Bolivia "
                 "evidencia", "renta de los hidrocarburos y crecimiento",
                 "economía informal Bolivia estimación", "minería cooperativa y empleo",
                 "bolivianización del sistema financiero"),
        languages=("es", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="open access / publisher terms",
        notes="the bolivianizacion literature is the mechanism source for BO-A: it documents how "
              "deliberately the deposit base was de-dollarised after 2006, which is exactly why "
              "a 2023 dollar shortage transmitted differently from a 1985 one"),
    source_class(
        "bo_geoscience", "SERGEOMIN's geological survey, the Uyuni brine studies and the "
                         "university mining schools (UTO Oruro, UATF Potosi)", layer="academic",
        roots=("https://www.sergeomin.gob.bo/", "https://www.uto.edu.bo/",
               "https://www.uatf.edu.bo/"),
        queries=("salmuera del Salar de Uyuni composición", "recursos de litio evaluación",
                 "yacimiento polimetálico Bolivia", "ley de cabeza estaño",
                 "geología del Cerro Rico", "extracción directa de litio piloto"),
        languages=("es",), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="open access",
        notes="the brine chemistry is why Uyuni is a RESOURCE and not a reserve: a high "
              "magnesium-to-lithium ratio and a rainy season over the salar are the two "
              "engineering facts that every cancelled agreement ran into"),
    # ---- practitioner
    source_class(
        "bo_practitioner", "The specialist desk press and the agencias de bolsa: Energy Press "
                           "Bolivia, Reporte Energia, Hidrocarburos Bolivia, Nueva Economia, "
                           "and the BISA / Panamerican / Sudaval research notes",
        layer="practitioner",
        roots=("https://www.energypress.com.bo/", "https://reporteenergia.com/",
               "https://nuevaeconomia.com.bo/", "https://www.hidrocarburosbolivia.com/"),
        queries=("producción de gas campos declinación", "importación de diésel cargamento",
                 "cotización del dólar paralelo hoy", "emisión de bonos empresa boliviana",
                 "exportación de estaño precio", "análisis del mercado de valores boliviano"),
        languages=("es",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="the energy trade press carries the cargo-level detail -- which tanker arrived, "
              "which field declined, which station ran dry -- weeks before the ministry's "
              "monthly series shows it, and that lag is the edge in BO-H"),
    # ---- retail ecology
    source_class(
        "bo_retail_dollar", "The household dollar market: r/BOLIVIA, the Facebook and WhatsApp "
                            "casa-de-cambio groups, the street cambistas of the Miamicito and "
                            "the Eloy Salmon", layer="retail_ecology",
        roots=("https://www.reddit.com/r/BOLIVIA/",
               "https://www.facebook.com/search/top?q=d%C3%B3lar%20paralelo%20bolivia"),
        queries=("dólar paralelo hoy Bolivia", "dónde comprar dólares La Paz",
                 "cambistas Santa Cruz cotización", "banco no da dólares",
                 "cómo pagar importación sin dólares", "ahorrar en dólares Bolivia"),
        languages=("es",), access_label="PUBLIC_SOCIAL", credibility="FRINGE",
        predictive_state="UNTESTED", licence="platform terms; public posts only",
        notes="KEPT AT LOW WEIGHT AND NEVER A SOURCE OF EDGE, but this is where the parallel "
              "rate is actually quoted first: the household ground leads the press by days when "
              "the premium moves, and the vocabulary dates each rationing episode"),
    source_class(
        "bo_retail_brokers", "Spanish-language 'forex' and prop-firm affiliates targeting "
                             "Bolivian retail on YouTube, TikTok and Telegram",
        layer="retail_ecology",
        roots=("https://www.youtube.com/results?search_query=trading+forex+bolivia",
               "https://t.me/s/tradingbolivia"),
        queries=("trading Bolivia señales", "invertir en oro desde Bolivia",
                 "cómo abrir cuenta en broker internacional", "prop firm Bolivia",
                 "apalancamiento riesgo advertencia"),
        languages=("es",), access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="platform terms; public posts only",
        notes="STRUCTURALLY BLOCKED AND ADVERTISED ANYWAY: a Bolivian resident cannot readily "
              "fund an offshore margin account at the official rate, so this ground measures "
              "demand for capital flight rather than a regulated retail flow -- which makes its "
              "activity level a stress observable in its own right"),
    # ---- app ecosystem
    source_class(
        "bo_payment_rails", "The payment rails: Tigo Money, the ASFI/BCB electronic payment "
                            "statistics, the Bolivia QR interoperable rail and the bank apps",
        layer="app_ecosystem",
        roots=("https://www.bcb.gob.bo/?q=sistema_pagos", "https://www.tigomoney.com.bo/",
               "https://www.asfi.gob.bo/"),
        queries=("estadísticas de pagos electrónicos BCB", "billetera móvil Bolivia usuarios",
                 "QR interoperable transacciones", "transferencias electrónicas volumen",
                 "remesas del exterior Bolivia", "pago con tarjeta en el exterior límite"),
        languages=("es",), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the CARD-ABROAD limits and the remittance series are the two places a dollar "
              "shortage becomes visible in a household statistic: when the banks capped foreign "
              "card spending, that cap was a dated administrative event with a published rule"),
    source_class(
        "bo_data_portals", "The open data and series portals a local analyst actually uses: the "
                           "BCB's statistical annexes, INE's downloadable series, the Aduana "
                           "query tool and the CEPAL/CEPALSTAT mirrors", layer="app_ecosystem",
        roots=("https://www.bcb.gob.bo/?q=publicaciones_estadisticas",
               "https://www.ine.gob.bo/index.php/estadisticas-economicas/",
               "https://statistics.cepal.org/portal/cepalstat/"),
        queries=("series estadísticas descarga Bolivia", "anexo estadístico BCB excel",
                 "CEPALSTAT Bolivia indicadores", "base de datos comercio exterior consulta",
                 "estadísticas económicas descarga"),
        languages=("es", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THERE IS NO API. Bolivia publishes spreadsheets and PDFs, not endpoints, which "
              "makes it materially more expensive to keep point-in-time than Peru and is the "
              "honest reason several datasets here are marked pit_feasible=False"),
    # ---- media
    source_class(
        "bo_media_national", "The national press and wires: El Deber (Santa Cruz), Los Tiempos "
                             "(Cochabamba), La Razon and Brujula Digital (La Paz), Opinion, ANF "
                             "and the state agency ABI", layer="media",
        roots=("https://eldeber.com.bo/economia", "https://www.lostiempos.com/economia",
               "https://brujuladigital.net/economia", "https://www.noticiasfides.com/"),
        queries=("dólar paralelo cotización", "reservas internacionales caen",
                 "bloqueo de caminos vías", "escasez de diésel surtidores",
                 "exportación de gas disminuye", "venta de oro del Banco Central",
                 "paro cívico Santa Cruz", "cupo de exportación de soya"),
        languages=("es",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="THE PRESS IS THE PARALLEL-RATE TAPE. There is no official series for the second "
              "price of the boliviano, so the business pages ARE the data source -- which is "
              "why every premium in this pack is PRESS_REPORTED and carries an error bar"),
    source_class(
        "bo_indigenous_media", "The indigenous and campesino ground: Erbol's radio network "
                               "broadcasting in Aymara and Quechua, the CIDOB and CONAMAQ "
                               "communiques, and the Asamblea del Pueblo Guarani in the Chaco",
        layer="media",
        roots=("https://erbol.com.bo/", "https://www.cidob-bo.org/",
               "https://www.apgnacional.org/"),
        queries=("asamblea comunal resolución", "consulta previa territorio indígena",
                 "regalías hidrocarburíferas comunidad", "ayllu pronunciamiento",
                 "mallku thakhi bloqueo", "ñemboati Ñande Reko", "Itika Guasu regalías",
                 "ch'alla mina cooperativa"),
        languages=("es", "ay", "qu", "gn"), access_label="PUBLIC_WITH_TERMS",
        credibility="RELIABLE", predictive_state="NARRATIVE_FEATURE",
        licence="publisher terms",
        notes="ERBOL BROADCASTS IN AYMARA AND QUECHUA and the APG negotiates in Guarani. A "
              "blockade is decided in a community assembly and a gas royalty is negotiated in "
              "the Chaco; a Spanish-only crawl reads the announcement and never the decision"),
    source_class(
        "bo_licensed_assessments", "Licensed terminals and price reporting agencies: Bloomberg, "
                                   "Refinitiv, Fastmarkets and the International Tin "
                                   "Association's paid series", layer="media",
        roots=("https://www.fastmarkets.com/", "https://www.internationaltin.org/"),
        queries=("tin concentrate treatment charge", "tin market balance report",
                 "Bolivia tin production estimate", "zinc concentrate spot TC"),
        languages=("en",), access_label="LICENSED", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="subscription; terms forbid machine extraction",
        machine_use_allowed=True,
        notes="REGISTERED, NEVER SCRAPED. Tin is Bolivia's signature metal, the broker does not "
              "quote it and the good tin data is paywalled -- so the tin mechanism is measured "
              "on the CO-PRODUCED metals and the absence is named rather than worked around"),
    # ---- archive
    source_class(
        "bo_archive_official", "The long run: the Gaceta Oficial archive, BCB memorias anuales, "
                               "INE anuarios estadisticos and the Archivo y Biblioteca "
                               "Nacionales de Bolivia in Sucre", layer="archive",
        roots=("http://www.gacetaoficialdebolivia.gob.bo/normas/listado/",
               "https://www.bcb.gob.bo/?q=publicaciones_institucionales",
               "https://www.ine.gob.bo/index.php/publicaciones/", "https://www.abnb.online/"),
        queries=("memoria anual BCB histórico", "anuario estadístico INE Bolivia",
                 "gaceta oficial normas archivo", "serie histórica tipo de cambio Bolivia",
                 "archivo nacional Sucre colección", "boletín minero histórico"),
        languages=("es",), access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the Gaceta's norm listing is what turns this pack's PRESS_REPORTED rows -- the "
              "gold authority, the fuel decrees, the election and census closures -- into "
              "citations a cell may be promoted on; the ABNB in Sucre holds the Potosi mining "
              "record back four centuries, which is the deepest archive in this command"),
    source_class(
        "bo_wayback", "web.archive.org snapshots of the BCB reserve page, the YPFB statistics "
                      "and the press parallel-rate quotes, all of which overwrite in place",
        layer="archive",
        roots=("https://web.archive.org/web/*/bcb.gob.bo*",
               "https://web.archive.org/web/*/ypfb.gob.bo*",
               "https://web.archive.org/web/*/eldeber.com.bo*"),
        queries=("bcb reservas internacionales archive", "ypfb exportación gas archive",
                 "dólar paralelo bolivia archive", "aduana estadísticas archive"),
        languages=("es", "en"), access_label="PUBLIC_ARCHIVE", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="Internet Archive terms",
        notes="THE SINGLE MOST LOAD-BEARING LAYER IN THIS PACK. The parallel rate has no "
              "official series at all, the BCB reserve page shows only the current month, and "
              "the press quotes are overwritten -- so without a crawl history, the entire "
              "premium series of 2023-2025 is unreconstructible after the fact"),
    # ---- physical economy
    source_class(
        "bo_transit_waterway", "The landlocked export gate: the Arica and Ilo transit regimes, "
                               "ASP-B, the Hidrovia Paraguay-Parana and Puerto Busch",
        layer="physical_economy",
        roots=("https://www.aspb.gob.bo/", "https://www.puertoarica.cl/",
               "https://www.tisur.com.pe/"),
        queries=("tránsito de carga boliviana por Arica", "ASP-B carga en tránsito",
                 "hidrovía Paraguay-Paraná bajante", "convoy de barcazas soya",
                 "Puerto Busch proyecto", "exportación por Ilo acuerdo"),
        languages=("es",), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="BOLIVIA HAS NO COAST, and that is a physical mechanism the coastal packs do not "
              "have: concentrate leaves through Chile or Peru and soy leaves down a river whose "
              "LOW-WATER YEARS are a dated, published constraint on how much can physically "
              "move -- so a Chilean or Peruvian road closure is a Bolivian supply event too"),
    source_class(
        "bo_energy_physical", "The physical energy plane: ANH fuel import cargoes, the "
                              "Gualberto Villarroel and Guillermo Elder Bell refineries, the "
                              "Vinto tin smelter and the GASBOL and Argentine pipelines",
        layer="physical_economy",
        roots=("https://www.anh.gob.bo/", "https://www.ypfbrefinacion.com.bo/",
               "https://www.vinto.gob.bo/"),
        queries=("importación de diésel buque cargamento", "refinería capacidad procesamiento",
                 "fundición Vinto producción de estaño", "gasoducto Bolivia Brasil capacidad",
                 "gasoducto Juana Azurduy flujo", "cola de camiones cisterna"),
        languages=("es",), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE FUEL QUEUE IS THE MOST HONEST SINGLE INDICATOR IN THIS COUNTRY: when the "
              "dollars are short the cargoes are late and the queues form, and the queues are "
              "photographed and dated by the press days before any statistic reports it"),
    source_class(
        "bo_world_metal_bodies", "USGS Mineral Commodity Summaries, the International Tin "
                                 "Association's public releases, the ILZSG and UN Comtrade",
        layer="physical_economy",
        roots=("https://www.usgs.gov/centers/national-minerals-information-center",
               "https://www.internationaltin.org/", "https://www.ilzsg.org/",
               "https://comtradeplus.un.org/"),
        queries=("USGS tin mine production by country", "Bolivia silver mine production",
                 "ILZSG zinc lead supply", "Bolivia exports comtrade mirror",
                 "world tin supply concentration"),
        languages=("en",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="public domain (USGS) / body terms",
        notes="the INDEPENDENT read, and the only way to turn Bolivian tonnage into a share of "
              "world supply; the Comtrade MIRROR (what Bolivia's counterparties say they "
              "received) is also the only public check on gold exports, which the domestic "
              "series systematically understates"),
    source_class(
        "bo_climate", "SENAMHI Bolivia, the Parana basin water-level bulletins and the "
                      "Chiquitania fire season", layer="physical_economy",
        roots=("https://senamhi.gob.bo/", "https://www.ina.gob.ar/alerta/",
               "https://www.senamhi.gob.bo/index.php/pronostico"),
        queries=("pronóstico de lluvias altiplano", "bajante del río Paraguay nivel",
                 "sequía Santa Cruz campaña", "incendios forestales Chiquitania hectáreas",
                 "heladas altiplano", "jallu pacha temporada de lluvias"),
        languages=("es",), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="TWO CLIMATE MECHANISMS AT ONCE: the rainy season floods the Salar de Uyuni (which "
              "is why lithium extraction there is seasonal and hard) and closes the altiplano "
              "roads, while the Parana's low-water years physically cap how much soy can leave"),
    # ---- source graph
    source_class(
        "bo_source_graph", "Who cites whom: the BCB's own tables -> Fundacion Milenio and "
                           "Jubileo -> Brujula Digital and El Deber -> the household groups; "
                           "the Gaceta decree -> the gremio communique -> the wires; Erbol -> "
                           "the national press", layer="source_graph",
        roots=("https://brujuladigital.net/", "https://erbol.com.bo/",
               "https://fundacion-milenio.org/", "https://eldeber.com.bo/"),
        queries=("según fuentes del sector", "de acuerdo con datos del Banco Central",
                 "trascendió que el Gobierno evalúa", "fuentes cercanas a YPFB",
                 "citando el informe de Milenio", "dirigentes confirmaron a este medio"),
        languages=("es",), access_label="PUBLIC", credibility="UNKNOWN",
        predictive_state="UNTESTED", licence="derived from the public sources above",
        notes="'trascendio que' and 'fuentes cercanas' mark the unattributed leak that precedes "
              "a fuel decree, a gold operation or an export-quota change by a day or two here; "
              "the graph is how a leak is told apart from a repost, and in a country with no "
              "official parallel-rate series it is also how two conflicting quotes are ranked"),
)

#: ALL TEN LAYERS CARRY A REAL SOURCE FOR BOLIVIA and none is declared absent. Two are THIN and
#: the pack says which: `practitioner` has no sell-side to speak of (the agencias de bolsa write
#: about local corporate paper, not about macro), and `app_ecosystem` has portals rather than
#: APIs -- Bolivia publishes spreadsheets, not endpoints, which is why several datasets here are
#: honestly marked pit_feasible=False. What is ABSENT in this country is not a LAYER but two
#: specific SERIES, and both are named in POSITIONING_SOURCES with `available=False`: there is no
#: boliviano positioning series anywhere, and no foreign-holdings series for the local curve.
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


#: NATIVE QUERY TERRITORIES -- what the deep-forest miner types, per layer, in the languages of
#: the ground. Three or more for every one of the ten layers; the media and official territories
#: carry Aymara, Quechua and Guarani because that is where a blockade and a gas royalty are
#: actually decided.
QUERY_TERRITORIES: dict[str, tuple[str, ...]] = {
    "official": ("reservas internacionales netas composición oro",
                 "tipo de cambio oficial bolsín 6,96",
                 "Ley 1503 oro Banco Central", "importación de diésel volumen aduana",
                 "exportación de gas natural a Brasil YPFB",
                 "producción minera cooperativas estaño", "gaceta oficial decreto supremo"),
    "institutional": ("boletín diario bolsa boliviana de valores",
                      "ANAPO estimación de campaña soya", "IBCE comercio exterior boletín",
                      "informe de Milenio economía boliviana",
                      "Jubileo renta de los hidrocarburos"),
    "academic": ("bolivianización del sistema financiero evidencia",
                 "tipo de cambio fijo Bolivia sostenibilidad",
                 "salmuera Salar de Uyuni relación magnesio litio",
                 "minería cooperativa empleo e ingresos",
                 "economía informal y contrabando Bolivia"),
    "practitioner": ("Energy Press declinación de campos gas",
                     "Reporte Energía importación de carburantes",
                     "cotización del dólar paralelo análisis",
                     "Nueva Economía mercado de valores",
                     "exportación de estaño Vinto precio"),
    "retail_ecology": ("dólar paralelo hoy Bolivia cuánto está",
                       "dónde comprar dólares sin recargo",
                       "el banco no me da dólares qué hago",
                       "cómo pagar una importación desde Bolivia",
                       "ahorro en dólares o en bolivianos"),
    "app_ecosystem": ("estadísticas de pagos electrónicos BCB",
                      "límite de compras con tarjeta en el exterior",
                      "billetera móvil Tigo Money transacciones",
                      "anexo estadístico BCB descarga excel",
                      "CEPALSTAT Bolivia serie"),
    "media": ("reservas internacionales caen informe",
              "bloqueo de caminos rutas interrumpidas",
              "escasez de diésel colas surtidores",
              "venta de oro del Banco Central cuánto",
              "asamblea comunal ayllu resolución", "mallku thakhi bloqueo altiplano",
              "ñemboati Ñande Reko regalías Itika Guasu"),
    "archive": ("memoria anual BCB serie histórica",
                "gaceta oficial normas listado archivo",
                "anuario estadístico INE descarga",
                "web archive bcb reservas internacionales",
                "archivo nacional Sucre minería Potosí"),
    "physical_economy": ("tránsito de carga boliviana por Arica ASP-B",
                         "hidrovía Paraguay-Paraná bajante convoy",
                         "fundición Vinto producción estaño",
                         "gasoducto Juana Azurduy reversión del flujo",
                         "USGS tin mine production Bolivia",
                         "incendios Chiquitania hectáreas quemadas"),
    "source_graph": ("trascendió que el Gobierno evalúa",
                     "fuentes cercanas a YPFB confirmaron",
                     "según datos del Banco Central citados por",
                     "dirigentes confirmaron a este medio",
                     "citando el informe de la Fundación Milenio"),
}

# --------------------------------------------------------------------------- datasets
#: SIXTEEN CATALOGUE ENTRIES across the ten layers, each with the twelve fields the discovery
#: swarm needs and a `how_to_fetch` a collector can act on. `pit_feasible` is the field this
#: catalogue exists for, and Bolivia fails it more often than Peru does for a concrete reason:
#: this country publishes SPREADSHEETS AND PDFS, not endpoints, and its most important series --
#: the parallel exchange rate -- has no official publisher at all.
DATASETS: tuple[dict[str, Any], ...] = (
    {"name": "BCB net international reserves and their composition (gold, liquid FX, SDRs)",
     "source": "Banco Central de Bolivia",
     "coverage": "1990 onward for the level; the composition detail from the 2000s",
     "frequency": "monthly (weekly indicators for the headline)",
     "publication_lag_days": 15.0,
     "revisions": "restated when the valuation basis or the disclosure format changes",
     "licence": "free, public", "history_from": "1990-01", "pit_feasible": False,
     "assets": ("XAUUSD", "USDBRL", "USDMXN"),
     "mechanism_families": ("reserve_adequacy", "regime_break"),
     "how_to_fetch": "bcb.gob.bo indicadores de reservas plus the statistical annexes of the "
                     "boletin estadistico; NOT PIT-SAFE as published because the page shows the "
                     "current period and the disclosure format has changed more than once -- "
                     "the archive layer's crawls are the only vintage"},
    {"name": "The official bolsin exchange rate (6.96 sell / 6.86 buy)",
     "source": "Banco Central de Bolivia",
     "coverage": "the current value has been unchanged since 2011-11-02",
     "frequency": "daily (business days)", "publication_lag_days": 0.0,
     "revisions": "never", "licence": "free, public", "history_from": "1985-08",
     "pit_feasible": True, "assets": ("USDBRL", "XAUUSD"),
     "mechanism_families": ("administered_price", "regime_break"),
     "how_to_fetch": "bcb.gob.bo tipo de cambio; the series is a CONSTANT over the whole modern "
                     "sample, which is not a defect -- it is the fact the pack is built on, and "
                     "the only informative dates in it are the regime breaks before 2011"},
    {"name": "The parallel boliviano quote as reported by the press and the exchange houses",
     "source": "El Deber, Los Tiempos, Brujula Digital and the casas de cambio",
     "coverage": "a visible quote from early 2023; sporadic before that",
     "frequency": "daily, fragmented", "publication_lag_days": 0.0,
     "revisions": "none; each quote is a separate observation and sources disagree",
     "licence": "publisher terms", "history_from": "2023-02", "pit_feasible": False,
     "assets": ("XAUUSD", "USDBRL", "USDMXN"),
     "mechanism_families": ("capital_control_stress", "parallel_market"),
     "how_to_fetch": "the business pages of eldeber.com.bo, lostiempos.com and "
                     "brujuladigital.net, sampled daily, plus the household groups in the "
                     "retail layer which lead them by days; THE MOST IMPORTANT SERIES IN THIS "
                     "PACK AND THE LEAST OFFICIAL -- record the source with every quote and "
                     "never present a single quote as the rate"},
    {"name": "INE consumer price index and the imported-goods sub-index",
     "source": "Instituto Nacional de Estadistica",
     "coverage": "1990 onward; current base from 2016", "frequency": "monthly",
     "publication_lag_days": 7.0, "revisions": "rebasing only", "licence": "free, public",
     "history_from": "1990-01", "pit_feasible": True,
     "assets": ("SOYBEAN", "SUGAR", "USDBRL"),
     "mechanism_families": ("release_surprise", "pass_through"),
     "how_to_fetch": "ine.gob.bo estadisticas economicas, published in the first days of the "
                     "following month; the IMPORTED-GOODS sub-index against the official CPI is "
                     "the domestic footprint of the parallel premium"},
    {"name": "Aduana Nacional fuel import volumes and values",
     "source": "Aduana Nacional de Bolivia", "coverage": "2005 onward",
     "frequency": "monthly", "publication_lag_days": 35.0,
     "revisions": "minor, the following month", "licence": "free, public",
     "history_from": "2005-01", "pit_feasible": False,
     "assets": ("XBRUSD", "XTIUSD", "USDBRL"),
     "mechanism_families": ("import_bill", "administered_price"),
     "how_to_fetch": "aduana.gob.bo estadisticas query tool by tariff line for diesel and "
                     "gasoline; use VOLUME, because the value line moves with crude and double-"
                     "counts the price the study is trying to condition on"},
    {"name": "YPFB gas export volumes to Brazil and Argentina",
     "source": "YPFB and the Ministerio de Hidrocarburos",
     "coverage": "1999 onward (Brazil), 2007 onward (Argentina)", "frequency": "monthly",
     "publication_lag_days": 40.0, "revisions": "occasional restatement",
     "licence": "free, public", "history_from": "1999-07", "pit_feasible": False,
     "assets": ("XNGUSD", "USDBRL"),
     "mechanism_families": ("physical_supply", "structural_decline"),
     "how_to_fetch": "ypfb.gob.bo and hidrocarburos.gob.bo monthly bulletins, cross-checked "
                     "against the Brazilian and Argentine import series from the other side; "
                     "the MIRROR is the reliable half, because the offtakers publish faster"},
    {"name": "Ministerio de Mineria production by mineral and by producer type",
     "source": "Ministerio de Mineria y Metalurgia and SERGEOMIN",
     "coverage": "2000 onward", "frequency": "monthly and annual",
     "publication_lag_days": 60.0, "revisions": "the cooperative line is restated heavily",
     "licence": "free, public", "history_from": "2000-01", "pit_feasible": False,
     "assets": ("XZNUSD", "XPBUSD", "XAGUSD", "XAUUSD"),
     "mechanism_families": ("physical_supply",),
     "how_to_fetch": "mineria.gob.bo statistical bulletins; the STATE / MEDIUM / COOPERATIVE "
                     "split is the politically load-bearing field and the cooperative line is "
                     "the least reliable and the fastest growing, especially for gold"},
    {"name": "The declared blockade episodes (bloqueos and paros civicos)",
     "source": "this pack's BLOCKADE_EPISODES, built from the roads authority, the civic "
               "committees and the national press",
     "coverage": "2019 onward", "frequency": "irregular, dated", "publication_lag_days": 1.0,
     "revisions": "every row is PRESS_REPORTED and is rewritten when a Gaceta decree or a "
                  "roads-authority bulletin pins the date",
     "licence": "derived from public sources", "history_from": "2019-10", "pit_feasible": True,
     "assets": ("XZNUSD", "XAGUSD", "SOYBEAN", "XBRUSD"),
     "mechanism_families": ("logistics_shock", "political_event"),
     "how_to_fetch": "`blockade_episodes()` in this module; confirm each start and end against "
                     "the Gaceta Oficial state-of-emergency decrees and the ABC roads bulletins "
                     "before any cell compiled on it is promoted"},
    {"name": "Ley 1503 and the BCB gold operations authority",
     "source": "Gaceta Oficial del Estado Plurinacional and the BCB",
     "coverage": "from May 2023", "frequency": "irregular, dated",
     "publication_lag_days": 0.0, "revisions": "none; a law is amended by another law",
     "licence": "free, public", "history_from": "2023-05", "pit_feasible": True,
     "assets": ("XAUUSD",), "mechanism_families": ("sovereign_flow", "regime_break"),
     "how_to_fetch": "gacetaoficialdebolivia.gob.bo for the law itself and the BCB's reserve "
                     "composition series for the resulting gold line; A SOVEREIGN GOLD SALE "
                     "WITH A STATUTE AND A DATE is rare -- most are inferred from an IMF table "
                     "months after the fact"},
    {"name": "ASFI banking statistics: the dollar share of deposits and credit",
     "source": "Autoridad de Supervision del Sistema Financiero",
     "coverage": "2000 onward", "frequency": "monthly", "publication_lag_days": 25.0,
     "revisions": "minor", "licence": "free, public", "history_from": "2000-01",
     "pit_feasible": True, "assets": ("XAUUSD", "USDBRL"),
     "mechanism_families": ("dollarisation", "capital_control_stress"),
     "how_to_fetch": "asfi.gob.bo estadisticas del sistema financiero; the dollar share of "
                     "deposits is the HOUSEHOLD'S OWN VOTE on the peg and it is the series that "
                     "moved before the press noticed the parallel market"},
    {"name": "ANAPO and INE soy campaign, crush and export statistics",
     "source": "ANAPO, IBCE and INE", "coverage": "2000 onward",
     "frequency": "seasonal (verano and invierno campaigns) with monthly exports",
     "publication_lag_days": 30.0, "revisions": "the campaign estimate is revised twice",
     "licence": "free, public / association terms", "history_from": "2000-01",
     "pit_feasible": True, "assets": ("SOYBEAN", "CORN", "SUGAR"),
     "mechanism_families": ("seasonal_crop", "administered_export"),
     "how_to_fetch": "anapobolivia.org campaign reports and ibce.org.bo trade bulletins; the "
                     "EXPORT CUPO decisions are in the Gaceta and the two must be joined -- the "
                     "harvest is the supply and the permit is whether it may leave"},
    {"name": "Hidrovia Paraguay-Parana water levels",
     "source": "the Argentine INA alert service and the Paraguayan and Brazilian gauges",
     "coverage": "1990 onward, daily gauge readings", "frequency": "daily",
     "publication_lag_days": 1.0, "revisions": "none", "licence": "free, public",
     "history_from": "1990-01", "pit_feasible": True,
     "assets": ("SOYBEAN", "CORN"), "mechanism_families": ("logistics_shock", "weather_state"),
     "how_to_fetch": "ina.gob.ar alerta hidrologica gauge series for Rosario and the upper "
                     "river; A LANDLOCKED COUNTRY'S SOY LEAVES ON A BARGE, and a low-water year "
                     "physically caps the tonnage regardless of the harvest -- a constraint the "
                     "coastal packs in this command do not have"},
    {"name": "USGS, ITA and ILZSG world supply balances for tin, silver, zinc and lead",
     "source": "US Geological Survey, International Tin Association, ILZSG",
     "coverage": "1990 onward", "frequency": "annual (USGS) / monthly (ILZSG)",
     "publication_lag_days": 90.0, "revisions": "heavily revised for two cycles",
     "licence": "public domain (USGS) / body terms", "history_from": "1990-01",
     "pit_feasible": False, "assets": ("XZNUSD", "XPBUSD", "XAGUSD"),
     "mechanism_families": ("physical_supply", "world_balance"),
     "how_to_fetch": "the USGS Mineral Commodity Summaries PDF and the ILZSG monthly bulletin; "
                     "the ONLY way to turn a Bolivian tonnage into a share of world supply, and "
                     "the only public check on a tin market the broker does not quote"},
    {"name": "UN Comtrade mirror statistics for Bolivian gold and mineral exports",
     "source": "UN Comtrade", "coverage": "1990 onward", "frequency": "annual and monthly",
     "publication_lag_days": 120.0, "revisions": "reporters restate for years",
     "licence": "UN terms, free tier", "history_from": "1990-01", "pit_feasible": True,
     "assets": ("XAUUSD", "XZNUSD", "XAGUSD"),
     "mechanism_families": ("trade_flow", "measurement_check"),
     "how_to_fetch": "comtradeplus.un.org, querying what Bolivia's COUNTERPARTIES report "
                     "receiving; THE MIRROR IS THE ONLY PUBLIC CHECK ON BOLIVIAN GOLD, whose "
                     "domestic series systematically understates a large cooperative and "
                     "informal output"},
    {"name": "BCB electronic payment and remittance statistics",
     "source": "Banco Central de Bolivia and ASFI", "coverage": "2010 onward",
     "frequency": "monthly and quarterly", "publication_lag_days": 45.0,
     "revisions": "minor", "licence": "free, public", "history_from": "2010-01",
     "pit_feasible": True, "assets": ("USDBRL", "USDMXN"),
     "mechanism_families": ("household_flow", "capital_control_stress"),
     "how_to_fetch": "bcb.gob.bo sistema de pagos and the ASFI bulletins; the FOREIGN-CARD "
                     "SPENDING CAP episodes are administrative events with published rules and "
                     "are where a dollar shortage first becomes a household statistic"},
    {"name": "Gaceta Oficial full norm listing",
     "source": "Gaceta Oficial del Estado Plurinacional de Bolivia",
     "coverage": "the modern run, searchable by norm type and date", "frequency": "daily",
     "publication_lag_days": 0.0, "revisions": "none; a norm is amended by another norm",
     "licence": "free, public", "history_from": "2006-01", "pit_feasible": True,
     "assets": ("XAUUSD", "XBRUSD", "SOYBEAN"),
     "mechanism_families": ("administered_event", "regime_break"),
     "how_to_fetch": "gacetaoficialdebolivia.gob.bo normas listado, filtered by decreto supremo "
                     "and ley; this is the dataset that turns every PRESS_REPORTED row in this "
                     "pack -- the gold authority, the fuel decrees, the export cupos, the "
                     "census and election closures -- into a citation a cell may be promoted on"},
)

# --------------------------------------------------------------------------- actors
#: FIFTEEN ACTORS, each with all eleven fields. An actor whose FALSIFIER is blank is a story.
#: The national champions a two-lane violation would put on a docket -- San Cristobal's Japanese
#: parent, Petrobras, the Santa Cruz agro-exporters -- appear HERE and nowhere else.
ACTORS: tuple[dict[str, Any], ...] = (
    {"name": "The Banco Central de Bolivia board",
     "holds": "the official exchange rate, the encaje, direct credit to the Tesoro and the "
              "public enterprises, and a reserve stock whose liquid dollar component fell to a "
              "few hundred million while gold carried the rest",
     "forced_to": ("quote and defend 6.96 bolivianos to the dollar every business day",
                   "publish reserves and their composition monthly",
                   "fund the public enterprises and the Treasury when no one else will"),
     "when": "continuously; the reserve statistics are stamped at the month end",
     "information": ("the true liquid reserve position in real time",
                     "the allocation queue at the bolsin",
                     "the fuel import payments YPFB must make next month"),
     "constraints": ("A PEG IT HAS NOT MOVED SINCE 2011-11-02, which is a political commitment "
                     "before it is a monetary one",
                     "no IMF programme and no intention of one, so there is no external "
                     "adjustment clock and no tranche calendar",
                     "a bolivianised deposit base built deliberately after 2006, which changed "
                     "how a dollar shortage transmits",
                     "a statutory gold authority (Ley 1503) that is now an instrument"),
     "instruments": ("XAUUSD", "USDBRL", "USDMXN"),
     "counterparties": ("the importers allocated dollars at the bolsin",
                        "the commercial banks", "YPFB, whose fuel bill it must fund",
                        "the gold cooperatives it now buys from"),
     "observables": ("the official rate, which does not move",
                     "the reserve level AND its composition",
                     "the parallel premium beside the official rate",
                     "the retail bond programmes it sells to households"),
     "impact": "the boliviano cannot move, so the entire effect shows in the PREMIUM, in the "
               "gold line of the reserves, and in the regional EM legs as a risk marker",
     "persistence": "the peg has persisted more than a decade and through a reserve collapse; "
                    "the premium regime has persisted since 2023",
     "falsifier": "the reserve composition and the premium carry no information about XAUUSD or "
                  "the regional EM legs beyond the global risk state -- the honest null, and a "
                  "live one for a country this small",
     "notes": "NO MEETING CALENDAR EXISTS because the rate IS the policy; inventing one would "
              "be inventing an institution (L1.28a)"},
    {"name": "The BCB's reserve manager under Ley 1503",
     "holds": "the gold reserve, and since May 2023 the statutory power to trade it and to buy "
              "domestic production",
     "forced_to": ("keep the peg funded without an external programme",
                   "report the gold line in the reserve composition",
                   "buy from a domestic gold sector that is largely cooperative"),
     "when": "irregular, and dated by the law rather than by a calendar",
     "information": ("its own trading programme before it is disclosed",
                     "the domestic gold offer at the purchase price it sets"),
     "constraints": ("a law with a number, which makes the authority public and dated",
                     "a domestic gold sector whose true output is unmeasured",
                     "the fact that selling the gold removes the last unencumbered asset"),
     "instruments": ("XAUUSD",),
     "counterparties": ("the bullion market", "the gold cooperatives",
                        "the counterparties to its swaps and repos"),
     "observables": ("the gold line in the reserve composition",
                     "the purchase price offered domestically",
                     "the Comtrade mirror for gold exports"),
     "impact": "a DATED, LAWFUL, PUBLISHED sovereign gold flow on an instrument the broker "
               "quotes -- small in world terms and unusually well documented",
     "persistence": "the authority is permanent until repealed; the operations are episodic",
     "falsifier": "Ley 1503 operation windows show no abnormal XAUUSD behaviour once the dollar "
                  "and real-rate state are controlled for, which is the likely outcome given "
                  "the size and would still be worth knowing",
     "notes": "DECLARED SMALL ON PURPOSE: Bolivia's gold reserve is tens of tonnes, not "
              "hundreds, so this is a MECHANISM with a clean date rather than a big flow"},
    {"name": "YPFB",
     "holds": "the gas export contracts, the domestic fuel supply and the import bill for the "
              "diesel and petrol the country no longer refines enough of",
     "forced_to": ("buy refined product at market prices in dollars",
                   "sell it domestically at a price fixed by decree in bolivianos",
                   "nominate and deliver gas under take-or-pay contracts it can no longer fill"),
     "when": "continuously; the import settlements cluster at the month end",
     "information": ("the cargo schedule and the payment queue",
                     "field decline rates before they are certified",
                     "which stations will run dry next"),
     "constraints": ("A DECREED PUMP PRICE it cannot change, and a 2010 attempt to change it "
                     "that was reversed in five days by protest",
                     "declining reserves and no large new discovery",
                     "dollars it must obtain from the BCB at the official rate"),
     "instruments": ("XNGUSD", "XBRUSD", "XTIUSD"),
     "counterparties": ("Petrobras and the Brazilian offtakers", "the Argentine counterparty",
                        "the international product traders it buys from",
                        "the BCB, which funds it"),
     "observables": ("monthly export volumes by destination",
                     "the fuel import volume and value in the customs series",
                     "the fuel queues, which the press photographs and dates",
                     "the pipeline flow direction"),
     "impact": "the largest single recurring dollar demand in the country, with a crude beta "
               "and an administered domestic price -- the mechanism that drained the reserves",
     "persistence": "structural; the decline and the subsidy have both run for a decade",
     "falsifier": "fuel import volume carries no information about the crude legs or about the "
                  "regional EM legs beyond the crude move that caused it",
     "notes": "AN ACTOR, NEVER AN INSTRUMENT: it is a state company and not a listed one"},
    {"name": "The Ministerio de Economia y Finanzas Publicas and the TGN",
     "holds": "the budget, the fuel-subsidy line, the domestic debt programme and the "
              "sovereign bond curve",
     "forced_to": ("publish the Presupuesto General del Estado annually",
                   "fund a persistent deficit without an IMF programme",
                   "service a eurobond curve that repriced hard in 2023"),
     "when": "the budget is annual; the domestic issuance is continuous",
     "information": ("the true subsidy cost before it is reported",
                     "the cash position and the BCB's willingness to lend"),
     "constraints": ("NO IMF PROGRAMME, by choice, so no external adjustment schedule exists",
                     "a domestic market that is bank- and pension-held, with the BCB selling "
                     "bonds directly to households to absorb bolivianos",
                     "a fuel subsidy that is politically immovable"),
     "instruments": ("USDBRL", "USDMXN", "XAUUSD"),
     "counterparties": ("the BCB", "the domestic banks and pension funds",
                        "the offshore eurobond holders", "CAF and FONPLATA"),
     "observables": ("the budget's subsidy line", "the domestic issuance and its yields",
                     "the eurobond spread", "the retail bond programmes"),
     "impact": "the fiscal deficit is the ultimate source of the boliviano supply the peg has "
               "to absorb; the bond curve is the only continuous market opinion on it",
     "persistence": "the deficit has persisted since 2014",
     "falsifier": "fiscal releases carry no information about the executable legs beyond the "
                  "global EM risk state",
     "notes": "the absence of an IMF programme is the single biggest structural difference "
              "between this pack and every other stressed sovereign on the desk"},
    {"name": "COMIBOL and the state mining companies (Huanuni, Colquiri, Vinto)",
     "holds": "the state's tin, zinc and lead operations and the Vinto smelter",
     "forced_to": ("employ a workforce that is politically organised and protected",
                   "sell concentrate and refined tin at exchange-linked prices",
                   "report production monthly to the ministry"),
     "when": "continuous; production is reported with a two-month lag",
     "information": ("its own grade and cost position",
                     "the union's intentions before a stoppage"),
     "constraints": ("declining grades at Huanuni and a high-cost labour structure",
                     "a smelter that must be kept hot",
                     "a political obligation to employ rather than to optimise"),
     "instruments": ("XZNUSD", "XPBUSD", "XAGUSD"),
     "counterparties": ("the Asian smelters and traders", "the mining unions",
                        "the cooperatives it shares deposits with"),
     "observables": ("the ministry's production-by-producer-type series",
                     "Vinto's refined tin output", "the union's public positions"),
     "impact": "tin is not quoted by this broker, so the executable effect is through the "
               "CO-PRODUCED zinc, lead and silver from the same concentrates",
     "persistence": "structural decline with episodic stoppages",
     "falsifier": "state-sector production changes carry no information about the executable "
                  "metals once the ILZSG world balance is conditioned on",
     "notes": "AN ACTOR, NEVER AN INSTRUMENT. Tin's absence from the registry is named in "
              "TRANSMISSION_TARGETS and routed, never pretended away"},
    {"name": "The mining cooperatives and FENCOMIN",
     "holds": "a large and growing share of Bolivian gold output and a decisive political "
              "position; roughly a hundred thousand members organised in federations",
     "forced_to": ("work deposits the state and the private sector have left",
                   "sell through licensed buyers to reach the export market",
                   "defend a tax and royalty treatment that is repeatedly legislated"),
     "when": "continuous; the political mobilisations cluster around mining-law debates",
     "information": ("the true gold output, which nobody measures",
                     "their own mobilisation plans"),
     "constraints": ("an output that is UNMEASURED by construction and understated in the "
                     "official series",
                     "mercury use and the environmental fights it triggers",
                     "a legal status defended by the ability to blockade"),
     "instruments": ("XAUUSD", "XZNUSD"),
     "counterparties": ("the licensed gold buyers and exporters",
                        "the BCB, which now buys domestic gold under Ley 1503",
                        "the state, which legislates their treatment"),
     "observables": ("the cooperative line in the production series",
                     "the Comtrade mirror against declared exports",
                     "the FENCOMIN communiques that precede a mining decree",
                     "the blockades they call"),
     "impact": "a weak XAUUSD edge and a strong measurement warning: Bolivia's gold exports "
               "exceed its counted production, and the gap is this sector",
     "persistence": "structural and growing",
     "falsifier": "the export-minus-production gap carries no tradable information at all, "
                  "which would make it an accounting fact rather than a mechanism",
     "notes": "DECLARED WEAK ON PURPOSE, and carried because it explains why two official gold "
              "series for the same country disagree -- which a careless cell reads as a bug"},
    {"name": "San Cristobal (the country's largest single mine)",
     "holds": "a large open-pit silver-zinc-lead operation in Potosi, shipping concentrate out "
              "through Chilean ports",
     "forced_to": ("truck and rail concentrate across an international border",
                   "negotiate water use with the surrounding communities",
                   "report production through the ministry's series"),
     "when": "continuous; interruptions follow blockades and water disputes",
     "information": ("its own grade schedule and stockpile position",
                     "the community negotiations before they become public"),
     "constraints": ("LANDLOCKED LOGISTICS: every tonne crosses into Chile, so a Chilean or "
                     "Bolivian road closure stops it equally",
                     "a water-intensive process on an arid altiplano",
                     "a single-asset dependence on the zinc and silver prices"),
     "instruments": ("XZNUSD", "XAGUSD", "XPBUSD"),
     "counterparties": ("the Asian smelters", "the Potosi communities",
                        "the Chilean port and rail operators"),
     "observables": ("the ministry's medium-scale production line",
                     "port and rail transit statistics",
                     "the local conflict reporting"),
     "impact": "a JOINT silver-zinc-lead shock, which is the cleanest available test of whether "
               "the market prices a metal or a headline",
     "persistence": "grade phases persist for quarters",
     "falsifier": "interruptions at this unit are indistinguishable in the metals from any "
                  "other supply headline of the same size",
     "notes": "AN ACTOR, NEVER AN INSTRUMENT: its parent is a single name"},
    {"name": "YLB and the Uyuni lithium programme",
     "holds": "the state monopoly over the largest identified lithium resource on earth, and a "
              "commercial output close to zero",
     "forced_to": ("select partners by decree and submit the agreements to the legislature",
                   "evaporate or process brine on a salar that floods every rainy season",
                   "answer to Potosi's civic committee, which has cancelled a deal before"),
     "when": "irregular; every agreement and cancellation is a dated, published event",
     "information": ("the pilot plants' actual recovery rates",
                     "which agreement is about to be signed or dropped"),
     "constraints": ("a high magnesium-to-lithium brine that makes conventional evaporation "
                     "hard, which is the engineering fact behind every stalled deal",
                     "a rainy season over the salar",
                     "a political veto held by Potosi"),
     "instruments": ("XNIUSD",),
     "counterparties": ("the Chinese and Russian consortia", "the legislature",
                        "the Potosi civic committee"),
     "observables": ("the signed and cancelled agreements in LITHIUM_MILESTONES",
                     "the legislative calendar", "the pilot plant output, which is near zero"),
     "impact": "DECLARED WEAK: XNIUSD is the only battery metal this broker quotes and it is a "
               "poor proxy; the honest reading is that Bolivian lithium news moves the Chilean "
               "and Argentine complexes, which is why this is an INTERACTION and not a cell",
     "persistence": "the resource is permanent; the programme has produced nothing for a decade",
     "falsifier": "lithium agreement and cancellation dates carry no information about any "
                  "instrument this broker quotes -- the likely outcome, and worth pinning",
     "notes": "AN ACTOR, NEVER AN INSTRUMENT, and the honest weak edge in this pack"},
    {"name": "ANAPO and the Santa Cruz soy complex",
     "holds": "the country's export agriculture: soy, sunflower, sorghum, maize and sugar, "
               "concentrated in one department",
     "forced_to": ("sell part of the crop into the domestic market before exporting any",
                   "obtain an export permit (cupo) that the government grants or withholds",
                   "move the crop down a river whose depth it does not control"),
     "when": "the verano harvest lands March to May and the invierno crop August to September",
     "information": ("the real harvest before the official estimate",
                     "the crushing margin and the stock position"),
     "constraints": ("AN ADMINISTERED EXPORT REGIME: the cupo is a permission, not a price",
                     "a biodiesel mandate that competes for the same beans",
                     "the Paraguay-Parana waterway's low-water years, which physically cap "
                     "tonnage regardless of the harvest",
                     "a diesel supply it needs at harvest and that has run short"),
     "instruments": ("SOYBEAN", "CORN", "SUGAR"),
     "counterparties": ("the crushers and exporters", "the government that grants the cupo",
                        "the Brazilian and Argentine rivals it clears against"),
     "observables": ("the ANAPO campaign estimate", "the export cupo resolutions in the Gaceta",
                     "the waterway gauge readings", "monthly export volumes"),
     "impact": "a small share of world soy, so the honest claim is about the MARGINAL "
               "South American exportable surplus and about the administered permission, not "
               "about Chicago",
     "persistence": "seasonal; the cupo regime persists",
     "falsifier": "cupo decisions and campaign revisions carry no information about the soy "
                  "complex once Brazilian and Argentine supply is conditioned on",
     "notes": "AN ACTOR, NEVER AN INSTRUMENT: the exporters are private companies"},
    {"name": "The Santa Cruz civic committee and the paro civico",
     "holds": "the ability to stop the country's richest department, and it has used it for "
              "more than a month at a time",
     "forced_to": ("call and sustain a paro through assemblies and neighbourhood committees",
                   "negotiate an end with a central government it opposes"),
     "when": "the 2022 paro ran 36 days from late October; the calls cluster around census, "
             "election and autonomy disputes",
     "information": ("its own mobilisation capacity and the business sector's tolerance",
                     "which export cargoes are stranded and for how long"),
     "constraints": ("a paro costs its own constituency the most, which bounds its length",
                     "the harvest and export calendar, which sets when a paro bites hardest"),
     "instruments": ("SOYBEAN", "CORN", "SUGAR", "USDBRL"),
     "counterparties": ("the central government", "CAINCO and the business chambers",
                        "the transport unions"),
     "observables": ("the paro's declared start and end",
                     "export volumes through the affected month",
                     "the waterway loadings"),
     "impact": "a dated, bounded interruption of the country's export agriculture, and a "
               "national political event at the same time",
     "persistence": "days to weeks; the grievance persists",
     "falsifier": "paro windows show no measurable effect on soy exports or on the executable "
                  "softs once the harvest calendar and the Brazilian crop are conditioned on",
     "notes": "the Bolivian analogue of the Peruvian blockade, with a DIFFERENT actor: a "
              "business-backed regional movement rather than a highland community"},
    {"name": "The Central Obrera Boliviana and the highland blockade repertoire",
     "holds": "the national labour confederation and, with the campesino federations, the "
              "ability to close the altiplano trunk roads",
     "forced_to": ("negotiate the annual wage decree with the government",
                   "respond to fuel and food shortages with mobilisation"),
     "when": "the wage negotiation runs to 1 May; blockades cluster with political ruptures",
     "information": ("its own base's tolerance and the government's fiscal room",
                     "which federations will join a call and which will not"),
     "constraints": ("a wage decree that raises costs in a pegged economy",
                     "a membership that is itself hurt by a long blockade"),
     "instruments": ("XZNUSD", "XAGUSD", "USDBRL"),
     "counterparties": ("the government", "the mining and transport federations",
                        "the campesino confederations"),
     "observables": ("the wage decree in the Gaceta", "the declared blockades",
                     "road-authority bulletins"),
     "impact": "a closed trunk road in a landlocked country stops concentrate, fuel and food at "
               "the same time, which is why the Bolivian blockade is a LOGISTICS shock and not "
               "only a political one",
     "persistence": "days to weeks",
     "falsifier": "blockade windows show no effect in the executable metals once Peruvian and "
                  "Chilean supply events are conditioned on",
     "notes": "the altiplano repertoire is shared with southern Peru, which is exactly why "
              "INTERACTIONS treats a simultaneous Bolivian and Peruvian blockade as one weather "
              "system and a lone one as a country-specific shock"},
    {"name": "The casas de cambio and the parallel-market makers",
     "holds": "the second price of the boliviano and most of the country's actual dollar "
              "liquidity",
     "forced_to": ("quote a two-way price without access to the bolsin",
                   "source dollars from remittances, tourism, contraband and exporters"),
     "when": "continuously, past the banking close",
     "information": ("the true clearing price hours before the press reports it",
                     "who is buying size and why"),
     "constraints": ("a fragmented market with no central quote, so two houses differ by "
                     "several per cent on the same afternoon",
                     "a legal grey zone that widens and narrows with enforcement"),
     "instruments": ("XAUUSD", "USDBRL"),
     "counterparties": ("importers who cannot get an allocation", "households",
                        "the exporters and remittance recipients who supply them"),
     "observables": ("the quoted parallel rate", "the spread between houses",
                     "the household groups that quote it first"),
     "impact": "the premium to 6.96 is this pack's state variable, and these are the people who "
               "set it",
     "persistence": "the premium regime has persisted since 2023",
     "falsifier": "the premium carries no information about XAUUSD or the regional EM legs "
                  "beyond the global risk state",
     "notes": "PRESS_REPORTED AND FRAGMENTED: every premium computed from a single quote is a "
              "point estimate with an unstated error bar, and the pack says so on every row"},
    {"name": "The Aduana Nacional and the contraband economy",
     "holds": "the customs record, and an enforcement problem the size of a sector: subsidised "
              "Bolivian fuel is worth several times more across the Peruvian, Brazilian, "
              "Argentine and Paraguayan borders",
     "forced_to": ("publish import and export detail monthly",
                   "interdict a flow that the subsidy itself creates"),
     "when": "monthly publication; the interdictions are dated and publicised",
     "information": ("the declarations before they are aggregated",
                     "which border is leaking"),
     "constraints": ("A PRICE GAP IT CANNOT CLOSE: as long as the pump price is decreed below "
                     "every neighbour's, the arbitrage is structural",
                     "five long and thin borders"),
     "instruments": ("XBRUSD", "XTIUSD", "USDBRL"),
     "counterparties": ("the importers", "the neighbouring customs services",
                        "the smuggling networks"),
     "observables": ("the monthly import and export detail",
                     "the seizure statistics", "the Comtrade mirror"),
     "impact": "the fuel subsidy's true cost is larger than the domestic consumption implies, "
               "because part of the subsidised litre is consumed abroad -- which is why the "
               "import bill grows faster than the economy",
     "persistence": "structural, and it scales with the price gap",
     "falsifier": "fuel import volume tracks domestic activity closely enough that no leakage "
                  "term is needed, which would retire the mechanism",
     "notes": "the smuggling arbitrage is the reason BO-H's import bill has a CRUDE beta larger "
              "than domestic demand alone can explain"},
    {"name": "Petrobras and the Brazilian and Argentine offtakers",
     "holds": "the demand side of Bolivia's gas, and now the transit demand for Argentine gas "
              "moving north through Bolivian pipe",
     "forced_to": ("nominate under contracts whose volumes Bolivia can no longer fill",
                   "replace Bolivian molecules with domestic pre-salt and Vaca Muerta supply"),
     "when": "daily nominations; the contract milestones are dated",
     "information": ("its own alternative supply cost",
                     "the Bolivian delivery capability before it is public"),
     "constraints": ("a pipeline that physically exists and is cheaper to reuse than to replace",
                     "Brazilian and Argentine domestic supply growth that displaces Bolivia"),
     "instruments": ("XNGUSD", "USDBRL"),
     "counterparties": ("YPFB", "the Argentine transporter", "the Brazilian distributors"),
     "observables": ("the nominated and delivered volumes on both sides",
                     "the transit agreements", "the flow direction"),
     "impact": "the offtaker's own published series is the FASTER and more reliable half of the "
               "Bolivian export number, which is how the mirror check is built",
     "persistence": "structural displacement, with a dated reversal in 2024",
     "falsifier": "the Brazilian and Bolivian reported volumes diverge systematically, which "
                  "would mean neither is usable as a physical series",
     "notes": "AN ACTOR, NEVER AN INSTRUMENT: it is a listed single name and the two-lane order "
              "forbids hunting it"},
    {"name": "The Asamblea del Pueblo Guarani and the Chaco gas territories",
     "holds": "collective title over territory the producing gas fields sit on, and the legal "
              "standing to be consulted and compensated",
     "forced_to": ("decide in assembly (nemboati) with its own authorities",
                   "negotiate royalties and compensation field by field",
                   "be consulted before new operations on its territory"),
     "when": "assemblies and negotiations cluster around new field approvals and royalty "
             "disputes",
     "information": ("its own assembly's decision before it is announced",
                     "the compensation actually received"),
     "constraints": ("a territory (Itika Guasu among others) whose boundaries are titled and "
                     "contested at once",
                     "a state that needs the gas revenue more every year",
                     "a small population against a national fiscal interest"),
     "instruments": ("XNGUSD", "USDBRL"),
     "counterparties": ("YPFB and the field operators", "the departmental government of Tarija",
                        "the central state"),
     "observables": ("the APG communiques, in Guarani and Spanish",
                     "the consultation records", "the royalty distribution to Tarija"),
     "impact": "a veto point on new gas development in the one region that still has gas, which "
               "is why the production decline is a POLITICAL as well as a geological series",
     "persistence": "structural; the territorial claims are permanent",
     "falsifier": "consultation and royalty disputes carry no information about Bolivian gas "
                  "volumes beyond the field decline rates themselves",
     "notes": "THE GUARANI LANGUAGE IS NOT DECORATION HERE: the assembly that can delay a gas "
              "field sits in it, and an English- or Spanish-only crawl misses the decision"},
)

# --------------------------------------------------------------------------- domains
#: THIRTEEN DOMAINS. Each names its research objects, the STATES it conditions on (these are the
#: `condition` half of every cell `cells()` mints), the executable instruments it may touch and
#: at least two negative controls -- without which an effect cannot be told from the sampling.
DOMAINS: tuple[dict[str, Any], ...] = (
    {"id": "BO-A", "title": "The 6.96 peg and the premium that opened beside it",
     "objects": ("the official rate, unchanged since 2011-11-02",
                 "the parallel quote and the premium between the two",
                 "the ASFI dollar share of deposits, which is the household's own vote",
                 "the BCB's retail bond programmes, which absorb bolivianos"),
     "conditions": ("the premium bucket: PEG_HOLDING, RATIONING, STRESS, SEVERE, DISLOCATED",
                    "the reserve composition -- how much of what is left is gold",
                    "whether a fuel-queue or import-payment episode was under way",
                    "the global EM risk state, read off the regional legs"),
     "instruments": ("XAUUSD", "USDBRL", "USDMXN", "XBRUSD"),
     "controls": ("the same state built on a block-SHUFFLED premium series, which is the null "
                  "for a state variable",
                  "the Argentine peso's own parallel-premium episodes (the `ar` pack owns "
                  "them), separating 'a Latin American dollar shortage' from 'Bolivia'",
                  "days with a large regional EM move and no Bolivian premium change"),
     "notes": "BOB IS ABSENT from the broker, so this domain is a CONDITIONER: it says when the "
              "regional legs and gold should be read as carrying Bolivia and when they should "
              "not. The official rate carries ZERO information by construction"},
    {"id": "BO-B", "title": "Reserve exhaustion and the Ley 1503 gold authority",
     "objects": ("the RIN level and, more importantly, its composition",
                 "Ley 1503 of May 2023 and the operations it authorised",
                 "the domestic gold purchase programme and its cooperative counterparty",
                 "the Comtrade mirror for gold exports against the domestic series"),
     "conditions": ("before against after the May 2023 statutory authority",
                    "the gold share of remaining reserves",
                    "whether the month carried a reported gold operation",
                    "the dollar and real-rate state XAUUSD is actually driven by"),
     "instruments": ("XAUUSD", "USDBRL", "XAGUSD"),
     "controls": ("other small sovereign gold sellers over the same months",
                  "months with an equivalent dollar or real-rate move and no Bolivian operation",
                  "a randomised-month null over the post-2023 window"),
     "notes": "DECLARED SMALL: tens of tonnes, not hundreds. The value here is the CLEAN DATE "
              "and the STATUTE, not the size -- most sovereign gold flows are inferred from an "
              "IMF table months later and this one has a law with a number"},
    {"id": "BO-C", "title": "The parallel market as a capital-control stress series",
     "objects": ("the daily press and casa-de-cambio quotes",
                 "the spread between quoting houses on the same day",
                 "the household groups that quote it first",
                 "the foreign-card spending caps and the import-payment delays"),
     "conditions": ("the premium bucket from `peg_stress_state`",
                    "whether an administrative measure (a card cap, an allocation rule) landed "
                    "in the same week",
                    "the dollar deposit share at the time",
                    "whether the quote dispersion between sources was wide or narrow"),
     "instruments": ("XAUUSD", "USDBRL", "USDMXN", "XTIUSD"),
     "controls": ("the Argentine blue-dollar episodes over the same months",
                  "weeks with a wide quote dispersion, where the premium is least measurable",
                  "a matched-weekday placebo on the regional legs"),
     "notes": "THE SERIES HAS NO OFFICIAL PUBLISHER. Every premium here is PRESS_REPORTED and "
              "carries an error bar; a cell may be compiled on the BUCKET and never promoted on "
              "a precise level"},
    {"id": "BO-D", "title": "The polymetallic complex: tin, silver, zinc and lead",
     "objects": ("production by mineral and by producer type (state, medium, cooperative)",
                 "Huanuni, Colquiri, San Cristobal, San Vicente and the Vinto smelter",
                 "the Cerro Rico cooperative workings",
                 "concentrate transit through Arica and Ilo"),
     "conditions": ("the metal, each a separate cell",
                    "whether the month contained a declared blockade",
                    "whether an Oruro or Potosi departmental day fell in the window",
                    "the ILZSG world-balance state for the metal"),
     "instruments": ("XZNUSD", "XPBUSD", "XAGUSD", "XAUUSD"),
     "controls": ("Peruvian production in the same month (the `pe` pack's series), separating "
                  "'the altiplano' from 'Bolivia'",
                  "months with no reported disruption at any Bolivian unit",
                  "a randomised-month null on the production series"),
     "notes": "TIN IS THE SIGNATURE METAL AND IS NOT QUOTED. It is routed through the "
              "co-produced zinc, lead and silver from the same concentrates, and the "
              "tin-specific component is UNMEASURED and says so"},
    {"id": "BO-E", "title": "Gold: the cooperative boom and the measurement gap",
     "objects": ("the cooperative line in the production series",
                 "declared gold exports against counted production",
                 "the Comtrade mirror from the receiving countries",
                 "the BCB's domestic purchase programme under Ley 1503"),
     "conditions": ("the size of the export-minus-production gap",
                    "whether a mining-law or royalty debate was live",
                    "the gold price level relative to the cooperatives' cost"),
     "instruments": ("XAUUSD", "USDBRL", "XAGUSD"),
     "controls": ("Peruvian informal gold over the same months, which has the same shape",
                  "months with an equivalent gold move and no Bolivian policy event",
                  "the mirror against the declared series as its own internal control"),
     "notes": "A WEAK EDGE AND A STRONG MEASUREMENT WARNING, declared as such: two official "
              "Bolivian gold series disagree, and a careless cell reads that as a data bug"},
    {"id": "BO-F", "title": "The Uyuni lithium programme: signed, cancelled, repeated",
     "objects": ("the YLB monopoly and the 2017 law that created it",
                 "the 2019 ACISA cancellation and the Potosi protests behind it",
                 "the 2023 Chinese and Russian agreements and their legislative stall",
                 "the brine chemistry that every one of them ran into"),
     "conditions": ("an agreement signing against a cancellation against a legislative stall",
                    "whether Potosi's civic committee was mobilised",
                    "the lithium price cycle at the time of the announcement"),
     "instruments": ("XNIUSD", "USDBRL", "USDMXN"),
     "controls": ("Chilean and Argentine lithium events over the same months (the `cl` and `ar` "
                  "packs own them), which is the only comparison that means anything here",
                  "months with an equivalent battery-metal move and no Bolivian announcement",
                  "a randomised-date null over the announcement calendar"),
     "notes": "THE HONEST WEAK EDGE IN THIS PACK. XNIUSD is the only battery metal the broker "
              "quotes and it is a poor proxy for lithium; the real value of this domain is the "
              "INTERACTION with `cl` and `ar`, where the same molecule meets three regimes"},
    {"id": "BO-G", "title": "Gas: a measured structural decline and a reversed pipeline",
     "objects": ("monthly export volumes to Brazil and to Argentina",
                 "the 1999 GSA, the 2006 nationalisation, the 2019 expiry",
                 "the 2024 reversal, with Argentine gas moving north through Bolivian pipe",
                 "the reserve certifications and the absence of a large new discovery"),
     "conditions": ("before against after the 2014 export peak",
                    "before against after the 2024 flow reversal",
                    "whether the destination is Brazil, Argentina or transit",
                    "the Brazilian and Argentine domestic supply state"),
     "instruments": ("XNGUSD", "USDBRL", "XBRUSD"),
     "controls": ("the offtakers' own import series as the mirror (the `br` and `ar` packs)",
                  "months with an equivalent global gas move and no Bolivian contract event",
                  "the pre-2014 sample, where the direction of the trend is opposite"),
     "notes": "THE EXPORT PRICE IS CONTRACTUAL AND FUEL-OIL-INDEXED, so XNGUSD is not the price "
              "Bolivia receives; this domain carries the VOLUME and the REGIME BREAKS and says "
              "the realisation is UNMEASURED"},
    {"id": "BO-H", "title": "The fuel subsidy and the diesel import bill that ate the reserves",
     "objects": ("the decreed pump price, frozen for years",
                 "the customs fuel import volume and value",
                 "the 2010 gasolinazo, decreed and reversed in five days",
                 "the fuel queues and the cargo delays the press dates"),
     "conditions": ("the crude level against the frozen domestic price (the parity gap)",
                    "whether a queue or shortage episode was under way",
                    "the premium bucket, because the import is paid in dollars",
                    "whether a price-change attempt was on the table"),
     "instruments": ("XBRUSD", "XTIUSD", "USDBRL", "XAUUSD"),
     "controls": ("the Argentine and Ecuadorean administered-fuel regimes over the same months",
                  "months with an equivalent crude move and no Bolivian shortage",
                  "a matched-weekday placebo on the crude legs"),
     "notes": "THE MECHANISM THAT CONNECTS EVERY OTHER DOMAIN: crude moves the import bill, the "
              "import bill drains the reserves, the reserves back the peg, and the peg's "
              "premium is BO-A's state variable"},
    {"id": "BO-I", "title": "Soy, the export cupo and the river that carries it",
     "objects": ("the verano and invierno campaigns and the ANAPO estimate",
                 "the export cupo resolutions and the domestic-supply certificates",
                 "the biodiesel and ethanol mandates that compete for the crop",
                 "the Hidrovia Paraguay-Parana water level"),
     "conditions": ("the campaign (verano or invierno)",
                    "whether the export cupo was open or withheld",
                    "the waterway's water-level state at loading",
                    "whether the harvest window carried a diesel shortage"),
     "instruments": ("SOYBEAN", "CORN", "SUGAR", "USDBRL"),
     "controls": ("Brazilian and Argentine supply over the same windows, which dominate the "
                  "world balance and must be removed first",
                  "campaigns with a normal water level and an open cupo",
                  "a randomised-date null on the cupo calendar"),
     "notes": "A SMALL SHARE OF WORLD SOY, declared: the honest claim is about the MARGINAL "
              "South American exportable surplus and about an administered permission, not "
              "about Chicago"},
    {"id": "BO-J", "title": "The fiscal-monetary loop: BCB credit, TGN issuance and the "
                            "household bond",
     "objects": ("BCB credit to the public enterprises and the Treasury",
                 "the domestic issuance and the retail bond programmes",
                 "the eurobond curve and its 2023 repricing",
                 "the absence of an IMF programme and the financing that replaces one"),
     "conditions": ("the deficit's size relative to the prior year",
                    "whether a retail bond programme was open",
                    "the eurobond spread bucket"),
     "instruments": ("USDBRL", "USDMXN", "XAUUSD"),
     "controls": ("other frontier sovereigns' spread moves in the same months",
                  "months with an equivalent EM credit move and no Bolivian fiscal event",
                  "a matched-weekday placebo on the EM legs"),
     "notes": "NO IMF PROGRAMME, BY CHOICE, and that is the structural difference from every "
              "other stressed sovereign on this desk: there is no adjustment clock to trade"},
    {"id": "BO-K", "title": "The bloqueo as a national logistics shock",
     "objects": ("the declared blockade and paro episodes",
                 "the 2022 Santa Cruz paro (36 days) and the 2024 Cochabamba blockades",
                 "concentrate transit to Arica and Ilo during a closure",
                 "the fuel and food shortages a closure produces"),
     "conditions": ("whether the day falls inside a declared episode (`is_blockade_day`)",
                    "the site: the highland trunk road, Santa Cruz, or a national closure",
                    "whether a Peruvian corridor blockade was running at the same time",
                    "the harvest or export calendar position when the closure began"),
     "instruments": ("XZNUSD", "XPBUSD", "XAGUSD", "SOYBEAN", "XBRUSD"),
     "controls": ("Peruvian blockade windows in the same months (the `pe` pack owns them), "
                  "which separates 'the altiplano' from 'Bolivia'",
                  "Chilean supply events over the same windows, which share the geography and "
                  "not the repertoire",
                  "matched windows with equivalent global moves and no Bolivian closure"),
     "notes": "LANDLOCKED MAKES THIS DIFFERENT FROM PERU'S. A closed trunk road here stops "
              "concentrate OUT and fuel and food IN at the same time, which is why the shock is "
              "logistical before it is political"},
    {"id": "BO-L", "title": "The calendars: national, Easter-derived and departmental",
     "objects": ("the seven fixed national feriados and the 2010 plurinational break",
                 "the four Easter-derived closures, computed from `easter(year)`",
                 "the mining departments' own days: Oruro 10 February, Potosi 10 November",
                 "the decreed one-off non-working days (a census, an election)"),
     "conditions": ("a national feriado against an ordinary weekday",
                    "a MINING departmental day against an ordinary weekday, which is about the "
                    "mine and not the bourse",
                    "before against after the 2010 statutory break"),
     "instruments": ("XZNUSD", "XAGUSD", "SOYBEAN", "USDBRL"),
     "controls": ("the matched weekday 26 weeks away, the standard holiday-liquidity control",
                  "the same dates in years before the 2010 additions existed",
                  "Peruvian and Chilean holidays that do not coincide"),
     "notes": "BOTH CARNAVAL DAYS ARE NATIONAL HERE and Oruro effectively stops for the week; "
              "Bolivia has no daylight saving, so a session study never carries a clock change"},
    {"id": "BO-M", "title": "External finance without a programme: the curve, CAF and the "
                            "rating",
     "objects": ("the eurobond curve and its repricing episodes",
                 "the CAF and FONPLATA disbursements that substitute for an IMF programme",
                 "the rating actions and their dates",
                 "the Article IV consultations that happen without a programme following"),
     "conditions": ("a rating action month against an ordinary month",
                    "whether a multilateral disbursement landed in the quarter",
                    "the global EM credit state"),
     "instruments": ("USDBRL", "USDMXN", "XAUUSD"),
     "controls": ("other frontier sovereign rating actions in the same months",
                  "quarters with a disbursement and no rating action",
                  "a randomised-date null over the rating calendar"),
     "notes": "THE BOLIVIAN CURVE IS NOT QUOTABLE HERE, so this domain mints CONDITIONERS "
              "rather than independent cells and says so on its face"},
)

# --------------------------------------------------------------------------- miners
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    {"name": "bo_peg_premium_state", "domain_ids": ("BO-A", "BO-C"), "kind": "macro",
     "cadence_s": 43200.0, "steerable": True, "wired": False,
     "entry": "countries.bo.pack:peg_premium_state",
     "needs": ("a parallel-rate quote with its source", "XAUUSD, USDBRL D1 bars"),
     "notes": "the premium bucket with the block-shuffled null beside it; the quote itself is a "
              "collector input and its absence is reported UNMEASURED by name"},
    {"name": "bo_gold_authority_windows", "domain_ids": ("BO-B", "BO-E"), "kind": "event",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.bo.pack:gold_authority_windows",
     "needs": ("GOLD_AUTHORITY", "BCB:rin composition", "XAUUSD H1 bars"),
     "notes": "a sovereign gold flow with a statute and a date; declared SMALL, which is why "
              "the control set is other small sellers rather than the dollar alone"},
    {"name": "bo_bloqueo_windows", "domain_ids": ("BO-K", "BO-D", "BO-I"), "kind": "event",
     "cadence_s": 43200.0, "steerable": True, "wired": False,
     "entry": "countries.bo.pack:bloqueo_windows",
     "needs": ("BLOCKADE_EPISODES", "XZNUSD, XAGUSD, SOYBEAN H1 bars",
               "the Peruvian corridor calendar for the joint control"),
     "notes": "the landlocked logistics shock, with the Peruvian simultaneity control built in"},
    {"name": "bo_gas_milestones", "domain_ids": ("BO-G",), "kind": "transfer",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.bo.pack:gas_milestones",
     "needs": ("GAS_MILESTONES", "YPFB:exportacion_gas", "XNGUSD D1 bars"),
     "notes": "a structural decline plus a DATED pipeline reversal; the contractual price is "
              "not XNGUSD and the miner says so"},
    {"name": "bo_fuel_subsidy_gap", "domain_ids": ("BO-H",), "kind": "macro",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.bo.pack:fuel_subsidy_gap",
     "needs": ("ADUANA:importaciones fuel volumes", "XBRUSD, XTIUSD D1 bars"),
     "notes": "the parity gap between a frozen decreed price and a moving crude leg, which is "
              "the reserve drain expressed as a crude beta"},
    {"name": "bo_andean_calendar", "domain_ids": ("BO-L",), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.bo.pack:andean_calendar",
     "needs": ("`national_holidays`, `departmental_days`, `carnaval`",
               "XZNUSD, XAGUSD H1 bars"),
     "notes": "three calendars in one country: national, Easter-derived and departmental, and "
              "the mining departments are the ones that move metal"},
    {"name": "bo_transmission_seeds",
     "domain_ids": ("BO-A", "BO-B", "BO-D", "BO-F", "BO-G", "BO-H", "BO-I", "BO-M"),
     "kind": "transfer", "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.bo.pack:transmission_seeds",
     "needs": ("TRANSMISSION_EDGES_SEED", "INTERACTIONS"),
     "notes": "the pack's map as HYPOTHESIS discoveries, deduplicated by the registry"},
)
MINER_DOMAINS: dict[str, tuple[str, ...]] = {
    "central_bank_surprise": ("BO-A",), "release_surprise": ("BO-B", "BO-D"),
    "calendar_settlement": ("BO-L", "BO-I"), "holiday_liquidity": ("BO-L",),
    "positioning": ("BO-M", "BO-B"), "carry_funding": ("BO-A", "BO-J"),
    "corporate_flow": ("BO-D", "BO-G"), "institutional_flow": ("BO-J", "BO-M"),
    "equity_mechanics": ("BO-M",), "derivatives_expiry": ("BO-M",),
    "failure": ("BO-H", "BO-K"), "residual": ("BO-C", "BO-E"),
    "transfer": ("BO-F", "BO-G"), "scouts": ("BO-K", "BO-I"),
    "session_microstructure": ("BO-C", "BO-L"),
}

# --------------------------------------------------------------------------- transmission
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    {"id": "BO-E1", "source": "The parallel premium to the 6.96 official rate",
     "target": "XAUUSD", "targets": ("XAUUSD", "USDBRL"), "to_country": "global", "sign": "+",
     "mechanism": "when a pegged currency's second price runs far above its first, domestic "
                  "savers buy the only store of value that is not the currency; and the same "
                  "premium marks the weeks in which the central bank is most likely to be "
                  "selling reserve gold to fund imports",
     "horizon": "0 to 20 sessions", "horizon_class": "multi_day", "lag_days": 2.0,
     "actor": "the BCB and the casas de cambio",
     "constraint": "the premium is PRESS_REPORTED and fragmented; a cell conditions on the "
                   "BUCKET, never on a precise level",
     "flow": "domestic savings into gold and out of the currency",
     "condition": "a premium bucket of STRESS or worse",
     "control": "the Argentine blue-dollar episodes; a block-shuffled premium series",
     "falsifier": "premium buckets carry no information about XAUUSD once the dollar and "
                  "real-rate state are controlled for",
     "evidence": "HYPOTHESIS"},
    {"id": "BO-E2", "source": "A reported BCB gold operation under Ley 1503",
     "target": "XAUUSD", "targets": ("XAUUSD",), "to_country": "global", "sign": "-",
     "mechanism": "a sovereign seller with a statutory mandate and a funding need is a "
                  "price-insensitive supplier; the authority is public and dated, which is rare",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "the BCB reserve manager",
     "constraint": "the reserve is tens of tonnes, so the flow is SMALL in world terms and the "
                   "edge, if any, is informational rather than mechanical",
     "flow": "sovereign gold sales into the bullion market",
     "condition": "a month with a reported operation after 2023-05",
     "control": "other small sovereign sellers; months with an equivalent dollar move and no "
                "Bolivian operation",
     "falsifier": "reported operation months are indistinguishable from matched control months "
                  "in XAUUSD, which is the likely and still-useful outcome",
     "evidence": "HYPOTHESIS"},
    {"id": "BO-E3", "source": "A declared bloqueo closing the highland trunk road",
     "target": "XZNUSD", "targets": ("XZNUSD", "XPBUSD", "XAGUSD"), "to_country": "global",
     "sign": "+",
     "mechanism": "a landlocked producer's concentrate reaches the sea only by road across a "
                  "foreign border; a closure stops the export physically and stops the fuel and "
                  "reagents coming the other way, so the mines wind down as well",
     "horizon": "0 to 15 sessions", "horizon_class": "multi_day", "lag_days": 3.0,
     "actor": "the COB, the campesino federations and the civic committees",
     "constraint": "Bolivian tonnage is a modest share of world zinc and lead, so the honest "
                   "claim is conditional and small",
     "flow": "physical concentrate withheld from the seaborne market",
     "condition": "a declared episode of more than a week, with no simultaneous Peruvian "
                  "corridor closure",
     "control": "Peruvian blockade windows (the `pe` pack); Chilean supply events",
     "falsifier": "Bolivian closure windows show no abnormal move in the base metals once "
                  "Peruvian and Chilean events and the ILZSG balance are conditioned on",
     "evidence": "HYPOTHESIS"},
    {"id": "BO-E4", "source": "A SIMULTANEOUS Bolivian and Peruvian altiplano blockade",
     "target": "XZNUSD", "targets": ("XZNUSD", "XAGUSD", "XPBUSD"), "to_country": "pe",
     "sign": "+",
     "mechanism": "the two countries share a border, a language, a blockade repertoire and a "
                  "polymetallic geology; when both close at once the withheld tonnage is the "
                  "sum, and the event is a regional supply shock rather than a national one",
     "horizon": "0 to 20 sessions", "horizon_class": "multi_day", "lag_days": 3.0,
     "actor": "the Aymara and Quechua federations on both sides of the border",
     "constraint": "simultaneity is rare, so the sample is small and must be reported as such",
     "flow": "joint physical interruption of altiplano concentrate",
     "condition": "an overlapping window in both countries' declared episode tables",
     "control": "lone Bolivian episodes and lone Peruvian episodes as the two single-country "
                "cells the joint one must beat",
     "falsifier": "joint windows are no different from the larger of the two single-country "
                  "effects, which would mean the market prices one country and ignores the other",
     "evidence": "HYPOTHESIS"},
    {"id": "BO-E5", "source": "The frozen pump price against import parity (the subsidy gap)",
     "target": "XBRUSD", "targets": ("XBRUSD", "XTIUSD"), "to_country": "global", "sign": "+",
     "mechanism": "a decreed domestic price and a market import price means the fiscal cost is "
                  "the gap times the volume, and the volume itself RISES with the gap because "
                  "the smuggling arbitrage across five borders scales with it",
     "horizon": "1 to 3 months", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "YPFB, the ANH and the contraband networks",
     "constraint": "the pump price is politically immovable; the 2010 attempt lasted five days",
     "flow": "subsidised fuel out and dollars out at the same time",
     "condition": "a crude level in the top tercile of the trailing two years",
     "control": "the Argentine and Ecuadorean administered-fuel regimes; months with an "
                "equivalent crude move and no shortage episode",
     "falsifier": "fuel import volume tracks domestic activity closely enough that no leakage "
                  "term is needed",
     "evidence": "HYPOTHESIS"},
    {"id": "BO-E6", "source": "The 2024 reversal of the Argentina-Bolivia gas flow",
     "target": "XNGUSD", "targets": ("XNGUSD", "USDBRL"), "to_country": "ar", "sign": "-",
     "mechanism": "the same steel now carries gas NORTH from Vaca Muerta toward Brazil instead "
                  "of south from Bolivia; that is a permanent change in the Southern Cone's "
                  "supply map and a level shift in every Bolivian gas-revenue series",
     "horizon": "a structural break, measured as a level shift",
     "horizon_class": "regime", "lag_days": 0.0,
     "actor": "YPFB, the Argentine transporter and the Brazilian offtakers",
     "constraint": "transit fees replace export revenue at a fraction of the value",
     "flow": "pipeline transit replacing pipeline export",
     "condition": "before against after the 2024 transit agreements",
     "control": "the Brazilian and Argentine domestic supply series over the same months",
     "falsifier": "no measurable level shift in the regional gas balance attributable to the "
                  "reversal once Vaca Muerta's own growth is conditioned on",
     "evidence": "HYPOTHESIS"},
    {"id": "BO-E7", "source": "A soy export cupo decision (granted or withheld)",
     "target": "SOYBEAN", "targets": ("SOYBEAN", "CORN", "SUGAR"), "to_country": "global",
     "sign": "+",
     "mechanism": "an administered permission, not a price: the crop exists and the state "
                  "decides whether it may leave, which is a supply event with a decree date",
     "horizon": "0 to 20 sessions", "horizon_class": "multi_day", "lag_days": 5.0,
     "actor": "the government, ANAPO and the Santa Cruz exporters",
     "constraint": "Bolivia is a small share of the world balance, so the claim is about the "
                   "MARGINAL South American surplus and says so",
     "flow": "administered export permission",
     "condition": "a cupo resolution in the Gaceta during a harvest window",
     "control": "Brazilian and Argentine supply in the same windows; campaigns with an open "
                "cupo and a normal river",
     "falsifier": "cupo decisions carry no information about the soy complex once Brazilian and "
                  "Argentine supply is conditioned on",
     "evidence": "HYPOTHESIS"},
    {"id": "BO-E8", "source": "A low-water year on the Hidrovia Paraguay-Parana",
     "target": "SOYBEAN", "targets": ("SOYBEAN", "CORN"), "to_country": "ar", "sign": "+",
     "mechanism": "a landlocked exporter's soy leaves on a barge; when the river is low the "
                  "convoys load lighter and the tonnage that can physically move falls "
                  "regardless of the harvest -- and the same river constrains Paraguay and "
                  "upriver Argentina at the same time",
     "horizon": "1 to 2 quarters", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "the barge operators and the exporters",
     "constraint": "the gauge is published daily and the constraint is physical, not commercial",
     "flow": "logistics capacity into exportable tonnage",
     "condition": "a gauge reading in the bottom decile of its own history during a loading "
                  "window",
     "control": "normal-water years in the same months; the Brazilian rail and port alternative",
     "falsifier": "low-water windows show no shortfall in the region's loaded tonnage, which "
                  "would mean the constraint is absorbed by storage",
     "evidence": "MEASURED_ELSEWHERE"},
    {"id": "BO-E9", "source": "The Bolivian gold export-minus-production gap",
     "target": "XAUUSD", "targets": ("XAUUSD",), "to_country": "global", "sign": "+",
     "mechanism": "a large cooperative and informal sector produces gold the official series "
                  "does not count; the gap between declared exports and counted production is a "
                  "published measure of a supply nobody is measuring",
     "horizon": "1 to 2 quarters", "horizon_class": "multi_day", "lag_days": 90.0,
     "actor": "the mining cooperatives and the licensed exporters",
     "constraint": "the gap is a residual of two imperfect series and is UNMEASURED as a level",
     "flow": "uncounted artisanal gold into the export record",
     "condition": "a gap in the top tercile of its own history",
     "control": "the Peruvian informal-gold gap over the same months; the Comtrade mirror",
     "falsifier": "the gap carries no tradable information at all, making it an accounting fact",
     "evidence": "HYPOTHESIS"},
    {"id": "BO-E10", "source": "A Uyuni lithium agreement signing or cancellation",
     "target": "XNIUSD", "targets": ("XNIUSD", "USDBRL"), "to_country": "cl", "sign": "-",
     "mechanism": "the world's largest identified lithium resource periodically announces that "
                  "it will or will not be developed; the tradable consequence, if any, is in "
                  "the BATTERY-METAL EXPECTATION rather than in any Bolivian output",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "YLB, the foreign consortia and the Potosi civic committee",
     "constraint": "no commercial output has followed any agreement in a decade, which is "
                   "itself the strongest prior",
     "flow": "expectation of future supply",
     "condition": "an announcement or cancellation date in LITHIUM_MILESTONES",
     "control": "Chilean and Argentine lithium events in the same months; battery-metal moves "
                "with no Bolivian announcement",
     "falsifier": "announcement dates carry no information about any quoted instrument -- the "
                  "likely outcome, and worth pinning so the desk stops wondering",
     "evidence": "HYPOTHESIS"},
    {"id": "BO-E11", "source": "A national feriado or a mining-department efemerides",
     "target": "XZNUSD", "targets": ("XZNUSD", "XAGUSD"), "to_country": "global", "sign": "+",
     "mechanism": "Oruro on 10 February and Potosi on 10 November stop the tin and silver "
                  "departments, and both Carnaval days are national; a production or logistics "
                  "study that does not carry them reads a holiday as a stoppage",
     "horizon": "0 to 5 sessions", "horizon_class": "multi_day", "lag_days": 0.0,
     "actor": "the departmental governments and the mining communities",
     "constraint": "the Easter-derived dates are computable years in advance",
     "flow": "seasonal logistics and production interruption",
     "condition": "a mining departmental day or a Carnaval window with no declared blockade",
     "control": "the matched weekday 26 weeks away; the same windows in a blockade year",
     "falsifier": "no measurable difference between a Carnaval week and a matched ordinary "
                  "week, which would retire the confound and simplify BO-K",
     "evidence": "HYPOTHESIS"},
)

#: INTERACTIONS -- the packs this one has a MEASURABLE relationship with. Bolivia is the hinge
#: between the Andean metals belt and the Southern Cone energy plane, which is why five packs
#: appear here and not the usual three.
INTERACTIONS: tuple[dict[str, Any], ...] = (
    {"with": "pe",
     "mechanism": "THE SHARED ALTIPLANO. Bolivia and Peru share a border, an Aymara- and "
                  "Quechua-speaking population, a road-blockade repertoire and a polymetallic "
                  "geology that produces the same four metals. A blockade on both sides in the "
                  "same window is one political weather system and the withheld tonnage is the "
                  "sum; a blockade on one side alone is a country-specific shock and the other "
                  "side is its control. The `pe` pack owns the Corredor Minero and the "
                  "Defensoria's monthly conflict register; this pack owns the national bloqueo "
                  "and the landlocked transit that runs THROUGH Peru's own ports",
     "observable": "the two countries' declared blockade tables overlaid, plus Bolivian "
                   "concentrate transiting Ilo during a Peruvian corridor closure",
     "targets": ("XZNUSD", "XPBUSD", "XAGUSD", "XAUUSD"),
     "control": "Chilean supply events in the same windows, which share the geography and not "
                "the blockade repertoire"},
    {"with": "cl",
     "mechanism": "TWO SEPARATE LINKS. First, LITHIUM: Chile is the world's second producer "
                  "with a functioning regime and Bolivia has the largest resource and no "
                  "output, so the pair is the cleanest natural experiment in resource "
                  "governance available. Second, LOGISTICS: Bolivian concentrate leaves through "
                  "Arica, so a Chilean port or road event is a Bolivian supply event, which the "
                  "Chilean pack has no reason to notice",
     "observable": "Chilean lithium production and regulatory milestones against Bolivia's "
                   "signed-and-cancelled table; Arica transit tonnage during Chilean events",
     "targets": ("XNIUSD", "XZNUSD", "XAGUSD"),
     "control": "Argentine lithium milestones as the third regime in the same triangle"},
    {"with": "ar",
     "mechanism": "THE REVERSED PIPE AND THE PARALLEL DOLLAR. Argentina displaced Bolivian gas "
                  "with Vaca Muerta and then began sending gas NORTH through Bolivian pipe "
                  "toward Brazil -- the same steel, the opposite flow, on a dated agreement. "
                  "Separately, Argentina is the only other economy in this command with a large "
                  "published parallel-dollar premium, which makes its episodes the natural "
                  "control for BO-A and BO-C",
     "observable": "the Argentine import and transit series against YPFB's export series, and "
                   "the blue-dollar premium against the boliviano premium",
     "targets": ("XNGUSD", "XAUUSD", "USDBRL", "SOYBEAN"),
     "control": "the Brazilian offtaker's own balance, which is the demand side of both"},
    {"with": "br",
     "mechanism": "THE OFFTAKER AND THE MIRROR. Brazil has been the destination of Bolivian gas "
                  "since 1999 and publishes its import series faster and more reliably than "
                  "Bolivia publishes its export series, which makes the Brazilian number the "
                  "usable half of the pair. Brazil is also the soy rival Bolivia clears "
                  "against, the EM leg this pack routes its macro through, and the destination "
                  "of the reversed Argentine flow",
     "observable": "Brazilian gas imports from Bolivia against YPFB's declared exports; the "
                   "Brazilian crush and export calendar against the Bolivian cupo decisions",
     "targets": ("XNGUSD", "SOYBEAN", "USDBRL"),
     "control": "USDMXN as the second regional leg, separating 'LatAm risk' from 'Brazil'"},
    {"with": "cn",
     "mechanism": "THE BUYER AND THE PARTNER. China is the destination for much of the region's "
                  "concentrate, the counterparty on the 2023 Uyuni lithium agreement, and the "
                  "marginal bid for the tin, zinc and lead this country ships. Chinese demand "
                  "prints are the third cell that separates 'Andean supply moved' from 'Chinese "
                  "demand moved' in every metals claim this pack makes",
     "observable": "Chinese refined and concentrate import prints against Bolivian and Peruvian "
                   "export records, and the legislative fate of the Chinese lithium agreement",
     "targets": ("XZNUSD", "XPBUSD", "XNIUSD"),
     "control": "Peruvian and Chilean exports to China over the same months"},
)

# --------------------------------------------------------------------------- eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    {"name": "the crawling peg and the gas boom", "start": "2000-01-01", "end": "2011-11-01",
     "regime": "a crawling peg that was allowed to appreciate through the commodity boom; the "
               "2006 nationalisation of hydrocarbons multiplies the state's gas revenue and "
               "the deliberate 'bolivianizacion' of the deposit base begins",
     "markers": ("2005-10 the Ley de Hidrocarburos raises the state take",
                 "2006-05-01 Decreto Supremo 28701 nationalises the sector",
                 "2010-12-26 the gasolinazo: a fuel-price decree reversed in five days"),
     "why_it_matters": "the exchange rate MOVED in this era, so a study that pools it with the "
                       "peg era is measuring two different currency regimes; and the gasolinazo "
                       "is the dated proof that the fuel subsidy is politically immovable",
     "status": "SETTLED"},
    {"name": "the peg and the reserve peak", "start": "2011-11-02", "end": "2014-12-31",
     "regime": "the exchange rate is fixed at 6.96 on 2011-11-02 and never moves again; "
               "reserves peak near US$15bn on record gas export volumes and the country runs "
               "twin surpluses",
     "markers": ("2011-11-02 the last bolsin adjustment",
                 "2014 gas export volumes and reserves both peak"),
     "why_it_matters": "the BASELINE era: the peg exists and is comfortably funded, so the "
                       "premium is zero and BO-A's state variable cannot vary at all",
     "status": "SETTLED"},
    {"name": "the long drawdown", "start": "2015-01-01", "end": "2019-10-20",
     "regime": "gas volumes and prices fall together; the fiscal deficit becomes structural; "
               "reserves decline every year while the official rate holds; the fuel import bill "
               "begins to grow as domestic refining falls behind demand",
     "markers": ("2015-2019 reserves fall every single year",
                 "2017-04 Ley 928 creates YLB and the lithium monopoly",
                 "2019-11-04 the ACISA lithium venture is cancelled amid the Potosi protests"),
     "why_it_matters": "the mechanism of BO-H is assembled here in plain sight and nothing in "
                       "the price of the currency reflects it, which is the whole point",
     "status": "SETTLED"},
    {"name": "the political rupture and the pandemic", "start": "2019-10-21",
     "end": "2021-12-31",
     "regime": "the disputed election, the blockades of October-November 2019 and the change of "
               "government; then the pandemic, a collapse in gas demand and the first large "
               "external borrowing; the peg holds through all of it",
     "markers": ("2019-10-21 the post-election blockades begin",
                 "2020-08 blockades over the postponed election",
                 "2020-10 the election that returns the MAS to office"),
     "why_it_matters": "BO-K's sample starts here, and the 2019 episode is the largest "
                       "nationwide logistics closure in the modern record",
     "status": "SETTLED"},
    {"name": "the reserve crisis and the parallel market", "start": "2022-01-01",
     "end": "2024-09-30",
     "regime": "usable reserves fall to a fraction of the remaining total, most of what is left "
               "is gold, queues form at the BCB, a parallel quote appears and widens, Ley 1503 "
               "authorises gold operations, and the Santa Cruz paro closes the export "
               "department for 36 days",
     "markers": ("2022-10-22 to 2022-11-26 the Santa Cruz paro civico",
                 "2023-02 queues at the BCB and the first visible parallel quote",
                 "2023-05 Ley 1503 authorises trading the reserve gold",
                 "2024-06-26 an attempted military takeover, resolved in hours"),
     "why_it_matters": "EVERY STATE VARIABLE IN THIS PACK IS BORN HERE. Before 2023 the premium "
                       "is zero and the gold authority does not exist, so the whole of BO-A, "
                       "BO-B and BO-C has a sample that starts in this era and not before",
     "status": "SETTLED"},
    {"name": "the reversed pipe and the election cycle", "start": "2024-10-01",
     "end": "2026-12-31",
     "regime": "Argentine gas begins transiting north through Bolivian pipe toward Brazil; the "
               "fuel queues become chronic; blockades by the Evo Morales faction close the "
               "Cochabamba axis; the 2025 general election runs its course with the peg still "
               "at 6.96 and the premium wide",
     "markers": ("2024-10 the first northbound transit agreements",
                 "2024-10-14 to 2024-11-08 the Cochabamba blockades",
                 "2025-08-17 the general election, first round",
                 "2025-10-19 the presidential run-off"),
     "why_it_matters": "the current regime, and the one in which a devaluation or a regime "
                       "change is a live possibility -- which is why every cell in this pack "
                       "must be dated rather than pooled",
     "status": "OPEN"},
)

ACCESS_CONSTRAINTS: tuple[dict[str, Any], ...] = (
    {"constraint": "the boliviano is not quoted by this broker",
     "measured": "data/universe/universe.json holds no BOB symbol",
     "consequence": "every domestic mechanism terminates in gold, the base metals, the energy "
                    "legs, the softs or the regional EM pairs; BOB is an INPUT and a "
                    "CONDITIONER, never a cell"},
    {"constraint": "the OFFICIAL rate carries no information at all",
     "measured": "6.96 BOB/USD on every business day since 2011-11-02",
     "consequence": "a study that uses the official rate as a currency series is regressing on "
                    "a constant; the PREMIUM to the parallel quote is the only variable half"},
    {"constraint": "the parallel rate has NO OFFICIAL PUBLISHER",
     "measured": "the series exists only in the business press and the casas de cambio, and two "
                 "sources disagree by several per cent on the same afternoon",
     "consequence": "BO-A and BO-C compile cells on the declared BUCKET from "
                    "`peg_stress_state`, never on a precise level, and every premium row is "
                    "PRESS_REPORTED with its source recorded beside it"},
    {"constraint": "tin is not quoted by this broker and the good tin data is paywalled",
     "measured": "no LME tin symbol in the registry; the International Tin Association and "
                 "Fastmarkets series are registered machine_use_allowed=false",
     "consequence": "Bolivia's signature metal is routed through the CO-PRODUCED zinc, lead and "
                    "silver, and the tin-specific component is UNMEASURED by name"},
    {"constraint": "Bolivia publishes spreadsheets and PDFs, not endpoints",
     "measured": "no public time-series API exists at the BCB, INE, YPFB or the mining ministry",
     "consequence": "several datasets here are honestly marked pit_feasible=False; keeping this "
                    "country point-in-time costs a crawl schedule rather than an API key, and "
                    "the archive layer is load-bearing rather than decorative"},
    {"constraint": "the blockade, gold, gas and lithium dates are PRESS_REPORTED",
     "measured": "every BLOCKADE_EPISODES, GOLD_AUTHORITY, GAS_MILESTONES and "
                 "LITHIUM_MILESTONES row carries that label and no Gaceta citation",
     "consequence": "those domains may generate hypotheses and may not promote any cell until a "
                    "gacetaoficialdebolivia.gob.bo norm number is attached to the exact date"},
    {"constraint": "cooperative and informal gold output is unmeasured by construction",
     "measured": "declared gold exports exceed counted production and the cooperative line is "
                 "the most heavily restated series the ministry publishes",
     "consequence": "XAUUSD cells from BO-E are declared WEAK; the export-minus-production gap "
                    "is carried as a measurement warning and as a hypothesis, never as a fact"},
    {"constraint": "there is no boliviano positioning series and no foreign-holdings series",
     "measured": "no COT contract, no NDF tape the desk can read, and a domestic curve held by "
                 "banks and pension funds with negligible foreign participation",
     "consequence": "the Peruvian and Brazilian 'foreign share of the local curve' observable "
                    "has NO Bolivian counterpart; reaching for one imports another country's "
                    "mechanism, and both absences are declared in POSITIONING_SOURCES"},
    {"constraint": "there is no IMF programme and no external adjustment clock",
     "measured": "Bolivia has had no Fund arrangement in this era and the government has ruled "
                 "one out repeatedly",
     "consequence": "every other stressed sovereign on this desk has a review calendar to trade "
                    "around; this one does not, and BO-M mints conditioners rather than events"},
)
INSTITUTIONAL_FLOW_SOURCES: tuple[str, ...] = (
    "BCB reserve composition and the Ley 1503 gold operations",
    "ASFI dollar share of deposits and credit",
    "Aduana Nacional fuel import volumes",
    "YPFB gas export volumes by destination, mirrored against the offtakers",
    "the press and casa-de-cambio parallel boliviano quotes")
SERIES: dict[str, str] = {
    "BO_OFFICIAL_FX": "BCB:tipo_de_cambio_oficial", "BO_PARALLEL_FX": "PRESS:dolar_paralelo",
    "BO_RESERVES": "BCB:rin", "BO_RESERVE_GOLD": "BCB:oro_monetario",
    "BO_CPI": "INE:ipc", "BO_TRADE": "INE:balanza_comercial",
    "BO_FUEL_IMPORTS": "ADUANA:importacion_carburantes",
    "BO_GAS_EXPORTS": "YPFB:exportacion_gas",
    "BO_MINING": "MIN:produccion_minera", "BO_GOLD_EXPORTS": "ADUANA:exportacion_oro",
    "BO_DEPOSIT_DOLLARISATION": "ASFI:deposito_en_dolares",
    "BO_SOY": "INE:exportacion_soya", "BO_WATERWAY": "INA:nivel_hidrovia",
    "BO_PAYMENTS": "BCB:pagos_electronicos",
}

# --------------------------------------------------------------------------- the cells
#: WHAT EACH DOMAIN MINTS: its mechanism family, its horizon class and the control every cell
#: from it inherits. `cells()` crosses a domain's OWN instruments with its OWN conditions, so a
#: gas domain never mints a silver cell and the count stays honest.
DOMAIN_CELL_SPEC: dict[str, tuple[str, str, str]] = {
    "BO-A": ("peg_stress", "1d_to_20d",
             "a block-shuffled premium series and the Argentine parallel episodes"),
    "BO-B": ("sovereign_flow", "0d_to_10d",
             "other small sovereign gold sellers and matched dollar-move months"),
    "BO-C": ("capital_control_stress", "1d_to_10d",
             "the Argentine blue-dollar episodes and wide-dispersion weeks"),
    "BO-D": ("physical_supply", "1m_to_3m",
             "Peruvian production in the same month and undisrupted Bolivian units"),
    "BO-E": ("measurement_gap", "1q",
             "the Peruvian informal-gold gap and the Comtrade mirror"),
    "BO-F": ("expectation_event", "0d_to_10d",
             "Chilean and Argentine lithium milestones in the same months"),
    "BO-G": ("structural_decline", "regime_level_shift",
             "the offtakers' own import series as the mirror"),
    "BO-H": ("administered_price", "1m_to_3m",
             "the Argentine and Ecuadorean fuel regimes and matched crude months"),
    "BO-I": ("administered_export", "0d_to_20d",
             "Brazilian and Argentine supply and normal-water campaigns"),
    "BO-J": ("fiscal_credit", "1m_to_1q",
             "other frontier sovereigns' spreads in the same months"),
    "BO-K": ("logistics_shock", "0d_to_15d",
             "Peruvian blockade windows and Chilean supply events"),
    "BO-L": ("holiday_liquidity", "0d_to_5d",
             "the matched weekday 26 weeks away and pre-2010 years"),
    "BO-M": ("sovereign_credit", "0d_to_10d",
             "other frontier rating actions and disbursement-only quarters"),
}


def cells() -> tuple[dict[str, Any], ...]:
    """Every testable cell this pack mints: domain x executable instrument x named condition.

    The cross product is taken over each domain's OWN instrument tuple, never over the whole
    executable list, which is what keeps the count honest: BO-G never mints a silver cell and
    BO-D never mints a gas one. A condition that this pack's declared datasets cannot evaluate
    does not appear in a domain's `conditions` tuple in the first place.
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


def peg_premium_state(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """BO-A and BO-C: the premium bucket. The quote itself is a collector input, so with no
    parallel-rate series this miner reports UNMEASURED by name rather than inventing a level."""
    buckets = [label for _edge, label in PREMIUM_BUCKETS] + [PREMIUM_EXTREME]
    n = _emit(ctx, "peg_stress", payload={"domain": "BO-A", "official": OFFICIAL_SELL,
                                          "peg_since": PEG_SINCE.isoformat(),
                                          "buckets": buckets})
    return {"miner": "peg_premium_state", "domain": "BO-A", "buckets": len(buckets),
            "episodes": len(PARALLEL_EPISODES), "emitted": n,
            "unmeasured": ["BO-A/PRESS:dolar_paralelo: the parallel quote has NO OFFICIAL "
                           "PUBLISHER and is not loaded on this box; the premium cannot be "
                           "bucketed without it"]}


def gold_authority_windows(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """BO-B and BO-E: the Ley 1503 dates -- a sovereign gold flow with a statute and a date."""
    n = 0
    for day, what, status in GOLD_AUTHORITY:
        n += _emit(ctx, "sovereign_flow",
                   payload={"domain": "BO-B", "date": day.isoformat(), "what": what,
                            "status": status, "targets": ("XAUUSD",),
                            "size_warning": "tens of tonnes, not hundreds: the value is the "
                                            "clean date, not the flow"})
    return {"miner": "gold_authority_windows", "domain": "BO-B", "events": len(GOLD_AUTHORITY),
            "emitted": n,
            "unmeasured": ["BO-B/gaceta_citation: no row carries a Gaceta Oficial norm number "
                           "yet, so none may be promoted"]}


def bloqueo_windows(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """BO-K: the landlocked logistics shock. Every episode PRESS_REPORTED and hypothesis-grade,
    with the Peruvian simultaneity question stated on every row."""
    episodes = blockade_episodes()
    total_days = sum((hi - lo).days + 1 for lo, hi, _s, _w in episodes)
    n = 0
    for lo, hi, site, what in episodes:
        n += _emit(ctx, "logistics_shock",
                   payload={"domain": "BO-K", "start": lo.isoformat(), "end": hi.isoformat(),
                            "site": site, "what": what, "status": "PRESS_REPORTED",
                            "joint_control": "check the `pe` pack's corridor table for the same "
                                             "window before attributing anything to Bolivia"})
    return {"miner": "bloqueo_windows", "domain": "BO-K", "episodes": len(episodes),
            "disrupted_days": total_days, "emitted": n,
            "unmeasured": ["BO-K/gaceta_citation: no episode carries a state-of-emergency "
                           "decree number yet, so none may be promoted"]}


def gas_milestones(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """BO-G: the structural decline and the 2024 flow reversal."""
    n = 0
    for day, what, status in GAS_MILESTONES:
        n += _emit(ctx, "structural_decline",
                   payload={"domain": "BO-G", "date": day.isoformat(), "what": what,
                            "status": status, "targets": ("XNGUSD", "USDBRL")})
    return {"miner": "gas_milestones", "domain": "BO-G", "events": len(GAS_MILESTONES),
            "emitted": n,
            "unmeasured": ["BO-G/contract_price: the export price is fuel-oil-indexed and "
                           "contractual, so XNGUSD is not the realisation and the Bolivian "
                           "revenue leg is UNMEASURED"]}


def fuel_subsidy_gap(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """BO-H: the parity gap between a frozen decreed pump price and a moving crude leg."""
    n = _emit(ctx, "administered_price",
              payload={"domain": "BO-H", "series": SERIES["BO_FUEL_IMPORTS"],
                       "targets": ("XBRUSD", "XTIUSD"),
                       "note": "use VOLUME, not value: the value line moves with crude and "
                               "double-counts the variable the study conditions on"})
    return {"miner": "fuel_subsidy_gap", "domain": "BO-H", "emitted": n,
            "unmeasured": ["BO-H/ADUANA:importacion_carburantes: the customs fuel volume series "
                           "is not loaded on this box; the parity gap cannot be sized"]}


def andean_calendar(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """BO-L: three calendars -- national, Easter-derived and departmental. The mining
    departments (Oruro, Potosi) are the ones that move metal."""
    year = datetime.now(tz=UTC).year
    national = national_holidays(year)
    mining = mining_department_days(year)
    n = _emit(ctx, "holiday_liquidity",
              payload={"domain": "BO-L", "year": year, "national": len(national),
                       "mining_department_days": sorted(d.isoformat() for d in mining),
                       "statute_break": [f"{m:02d}-{d:02d}"
                                         for m, d, _ in new_holidays_since_2010()]})
    return {"miner": "andean_calendar", "domain": "BO-L", "national": len(national),
            "mining_days": len(mining), "emitted": n, "unmeasured": []}


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
    "peg_premium_state": peg_premium_state,
    "gold_authority_windows": gold_authority_windows,
    "bloqueo_windows": bloqueo_windows,
    "gas_milestones": gas_milestones,
    "fuel_subsidy_gap": fuel_subsidy_gap,
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
            "jurisdictions": JURISDICTIONS, "roster_state": dict(ROSTER_STATE),
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
        "mission": MISSION, "jurisdictions": JURISDICTIONS, "roster_state": ROSTER_STATE,
        "interactions": INTERACTIONS, "query_territories": QUERY_TERRITORIES, "cells": CELLS,
        "blockade_episodes": BLOCKADE_EPISODES, "gold_authority": GOLD_AUTHORITY,
        "gas_milestones": GAS_MILESTONES, "lithium_milestones": LITHIUM_MILESTONES,
        "parallel_episodes": PARALLEL_EPISODES, "premium_buckets": PREMIUM_BUCKETS,
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
