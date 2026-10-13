"""MEXICO: the world's EM hedge proxy, a remittance book the size of an export book, and a date.

FOUR MECHANISMS, AND THE FIRST ONE IS ALSO THE WARNING:

  1. THE PESO IS THE WORLD'S EM LIQUIDITY PROXY. MXN is the most traded emerging-market currency,
     it quotes around the clock, and its CME contract is the deepest EM currency future in
     existence. The consequence is that USDMXN moves on things that have nothing to do with
     Mexico: when a fund cannot sell the asset it actually wants to hedge, it sells the peso. So
     the global risk factor DOMINATES this series, and any Mexican-fundamental claim tested on
     USDMXN without stripping that factor out is being tested against a much larger competing
     explanation. MXNJPY is in the executable set for exactly that purpose -- a Mexican move that
     survives in MXNJPY but not in USDMXN is carry, and one that survives in both is Mexican.

  2. REMITTANCES ARE AN EXPORT BOOK THAT DOES NOT RESPOND TO THE EXCHANGE RATE THE WAY EXPORTS DO.
     Roughly sixty billion dollars a year arrive from the United States, monthly, published by
     Banxico with a short lag, driven by US EMPLOYMENT rather than by Mexican competitiveness.
     A peso depreciation RAISES the peso value of a fixed dollar remittance, which makes the flow
     partly counter-cyclical -- the opposite sign to every other dollar inflow in this command.

  3. NEARSHORING IS A DATED POLICY QUESTION, NOT A TREND. The USMCA joint review falls in 2026,
     and it is the single largest scheduled Mexican risk event in the sample. Unlike a growth
     narrative, it has a DATE, which is what makes it tradable as an event rather than as a story.

  4. BANXICO ANNOUNCES AT A FIXED UTC MINUTE, ALL YEAR. Mexico abolished daylight saving in
     October 2022 (Decreto DOF 2022-10-30), so Mexico City has been UTC-6 year-round since. A
     13:00 local decision is 19:00 UTC in January and in July. Chile's moves twice a year and in
     antiphase; Mexico's does not move at all. A sample crossing 2022-10 does carry the shift and
     must be handled with the historical rule.

WHAT IS EXECUTABLE. USDMXN, EURMXN, GBPMXN and MXNJPY are all in the broker registry, which makes
Mexico the only country in this command besides Brazil whose own price trades here -- and the only
one whose POSITIONING the desk already holds, because `data/axes/cot.json` maps USDMXN.

THE TWO-LANE ORDER. Pemex, América Móvil, Cemex and Grupo México are the Mexican names every piece
of local research is about; none is in this broker's registry and none may mint a statistical
hypothesis. They appear here as ACTORS whose forced flows move FX and energy.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------- identity
CODE = "mx"
NAME = "Mexico"
REGION_COMMAND = "latam"
REGION_DESK = "LATAM_NORTH"
CURRENCY = "MXN"
NATIVE_LANGUAGES: tuple[str, ...] = ("es-MX",)
FISCAL_YEAR_END = "12-31"

OWN_PRICE: tuple[str, ...] = ("USDMXN", "EURMXN", "GBPMXN", "MXNJPY")

EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "USDMXN", "EURMXN", "GBPMXN", "MXNJPY",     # the peso complex, all four quoted here
    "USDBRL", "USDZAR", "USDTRY", "USDCNH",     # the EM peers the proxy role is measured against
    "AUDJPY", "USDJPY", "EURUSD", "AUDUSD",     # the carry and dollar-factor legs
    "XAUUSD", "XAGUSD",                         # Mexico is the world's largest silver producer
    "XTIUSD", "XBRUSD",                         # Maya crude and the Pemex decline
    "XCUUSD", "XZNUSD",                         # Grupo Mexico's copper and the base complex
    "CORN", "WHEAT", "SUGAR", "COFARA",         # the food-import bill and Mexican arabica
    "US500", "NAS100", "US2000", "US30",        # the US cycle Mexico is an appendix to
    "USDX", "UST10Y", "UST05Y",                 # the dollar and duration factors
)

COT_CURRENCY = "MXN"
COT_STATUS = ("USDMXN IS MAPPED in desks/mt5/data/axes/cot.json -- the only Latin American row in "
              "that axis. The CME peso contract is the deepest EM currency future in existence, "
              "so the speculative net here is a real measurement of the world's EM hedge rather "
              "than a thin proxy for it. This is the one country in this command where a "
              "positioning cell can be compiled today.")

TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "MexDer DEUA dollar futures and the CME 6M peso contract", "venue": "MexDer / CME",
     "why": "the peso's price formation is offshore and around the clock; the CME contract is "
            "where the speculative position actually sits",
     "proxies": ("USDMXN",),
     "basis_cost": "the CFD tracks spot; the future carries the rate differential, and in a "
                   "carry currency that differential is most of the holding cost"},
    {"name": "S&P/BMV IPC and the FTSE BIVA index", "venue": "BMV / BIVA",
     "why": "the domestic risk asset; neither index is quotable here",
     "proxies": ("US2000", "US500", "USDMXN"),
     "basis_cost": "the IPC is dominated by a handful of names with global revenue, so it is "
                   "closer to a US small-cap than to Mexican macro -- which is why US2000 is a "
                   "better carrier than a Mexican-macro proxy would be"},
    {"name": "TIIE de Fondeo, the Bonos M curve and the UDI-linked curve", "venue": "Banxico / "
                                                                                    "MexDer",
     "why": "the local rates expression; Banxico's surprise prices here first and reaches FX "
            "second",
     "proxies": ("USDMXN", "UST10Y", "UST05Y"),
     "basis_cost": "UST carries no Mexican term premium; the local real rate is UNMEASURED here"},
    {"name": "Maya crude posted prices and the Pemex hedge programme", "venue": "Pemex / OTC",
     "why": "Mexico runs the largest sovereign oil hedge in the world, bought annually in the "
            "options market, and the PURCHASE ITSELF moves the crude options surface",
     "proxies": ("XTIUSD", "XBRUSD"),
     "basis_cost": "Maya is a heavy sour grade and its differential to WTI is its own variable; "
                   "XTIUSD carries the flat price and not the differential"},
    {"name": "Banxico remittance series (remesas familiares)", "venue": "Banxico SIE",
     "why": "roughly sixty billion dollars a year, monthly, driven by US employment rather than "
            "by Mexican competitiveness",
     "proxies": ("USDMXN", "US500"),
     "basis_cost": "none; data rather than an instrument"},
    {"name": "AFORE (SIEFORE) portfolio and target-date glidepath data", "venue": "CONSAR",
     "why": "a mandatory pension system with a legislated foreign-asset limit and a target-date "
            "structure, so its rebalancing is RULE-BASED and datable",
     "proxies": ("USDMXN", "US500", "UST10Y"),
     "basis_cost": "none; data rather than an instrument"},
)

# --------------------------------------------------------------------------- central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "Banco de Mexico",
    "short": "Banxico",
    "framework": "inflation_targeter",
    "committee": "Junta de Gobierno -- the Governor and four Deputy Governors, with staggered "
                 "terms; individual votes ARE published in the minutes, which makes dissent a "
                 "measurable, dated variable rather than an inference",
    "policy_rate": "Tasa de interes interbancaria a un dia (the overnight target)",
    "meetings_per_year": 8,
    "schedule_rule": (
        "EIGHT scheduled decisions a year on a calendar published a year ahead. The announcement "
        "is at 13:00 Mexico City on a THURSDAY, which is 19:00 UTC year-round, and the minutes "
        "(minuta) follow two weeks later at 09:00 local. The quarterly Informe Trimestral is a "
        "separate event with its own date."),
    "announce_local": "13:00 America/Mexico_City", "announce_utc": "19:00",
    "announce_utc_dst": "19:00",
    "dst_rule": ("MEXICO ABOLISHED DAYLIGHT SAVING IN OCTOBER 2022 (the Ley de Husos Horarios, "
                 "DOF 2022-10-30), except for a narrow northern border strip that follows the US "
                 "calendar. America/Mexico_City has been UTC-6 all year since, so a Banxico "
                 "decision sits at the same UTC minute in January and in July. A SAMPLE CROSSING "
                 "2022-10 DOES carry the shift, and an event window built on the current rule "
                 "mis-bins every pre-2022 summer decision by an hour."),
    "minutes_rule": "the minuta lands two weeks after the decision at 09:00 local (15:00 UTC) and "
                    "names each member's vote; a split vote has moved the curve on release",
    "inflation_target": "3% with a +/-1pp variability interval",
    "fx_operations": (
        "The Comision de Cambios (Banxico plus the finance ministry) runs a NON-DELIVERABLE "
        "FORWARD programme settled in pesos rather than spot intervention, plus a swap line with "
        "the US Federal Reserve. The NDF programme's size and auctions are announced, which makes "
        "Mexican intervention observable in near real time like Brazil's and unlike Argentina's."),
    "policy_rate_series": "Banxico SIE SF61745 (objetivo de la tasa de interes interbancaria a "
                          "un dia) -- the id must be confirmed against the SIE catalogue",
    "expected_rate_series": "Encuesta Citibanamex de Expectativas (published every two weeks and "
                            "widely quoted as THE consensus) and the Banxico Encuesta sobre las "
                            "Expectativas de los Especialistas (monthly)",
    "decision_dates": {
        2024: ("2024-02-08", "2024-03-21", "2024-05-09", "2024-06-27", "2024-08-08",
               "2024-09-26", "2024-11-14", "2024-12-19"),
        2025: ("2025-02-06", "2025-03-27", "2025-05-15", "2025-06-26", "2025-08-07",
               "2025-09-25", "2025-11-06", "2025-12-18"),
        2026: ("2026-02-05", "2026-03-26", "2026-05-14", "2026-06-25", "2026-08-06",
               "2026-09-24", "2026-11-05", "2026-12-17"),
    },
    "decision_dates_status": ("2024 and 2025 follow the published calendars. 2026 is DERIVED from "
                              "Banxico's own Thursday cadence and must be replaced by the "
                              "published calendar before an event study is read as confirmatory"),
    "root": "https://www.banxico.org.mx",
}

# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "Tipo de cambio FIX",
     "publisher": "Banco de Mexico",
     "definition": "determined by Banxico from wholesale interbank transactions in a window "
                   "around midday Mexico City, published the SAME day and then in the Diario "
                   "Oficial for use on the FOLLOWING business day",
     "windows_local": ("11:45-12:15",), "windows_utc": ("17:45-18:15",),
     "published_local": "about 12:00 America/Mexico_City", "published_utc": "18:00",
     "dst_rule": "none since 2022-10; before that the UTC minute shifted with US DST",
     "instruments": ("USDMXN",),
     "why_it_matters": "the legal settlement reference for peso obligations, and the reference "
                       "MexDer contracts and most corporate hedges settle against",
     "trap": "the FIX is determined ONE DAY and applies the NEXT. A study that treats the "
             "published FIX as the same day's settlement rate is off by a business day, and the "
             "error is invisible because the two numbers are close"},
    {"name": "TIIE de Fondeo a un dia",
     "publisher": "Banco de Mexico",
     "definition": "the overnight funding reference computed from actual secured and unsecured "
                   "transactions, replacing the survey-based TIIE 28 as the reference rate",
     "windows_local": ("previous session",), "windows_utc": ("previous session",),
     "published_local": "each business day", "published_utc": "13:00",
     "dst_rule": "none since 2022-10",
     "instruments": ("USDMXN",),
     "why_it_matters": "the TRANSITION from a survey rate to a transaction rate is a structural "
                       "break in every Mexican carry series, and it is dated",
     "trap": "TIIE 28 and TIIE de Fondeo are different objects; splicing them into one carry "
             "series creates a level shift that looks like a policy move"},
    {"name": "UDI (Unidad de Inversion)",
     "publisher": "Banco de Mexico",
     "definition": "an inflation-indexed unit revalued daily from the previous fortnight's CPI, "
                   "published in advance",
     "windows_local": ("daily",), "windows_utc": ("daily",),
     "published_local": "10th and 25th for the following fortnight", "published_utc": "13:00",
     "dst_rule": "none since 2022-10",
     "instruments": (),
     "why_it_matters": "the real-rate leg of the local curve; like Chile's UF, the near-term path "
                       "is KNOWN in advance, so a CPI surprise cannot move the front of it",
     "trap": "an inflation event study dated to the print is looking at the wrong horizon for "
             "any UDI-linked instrument"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "FX spot", "kind": "weekday",
     "rule": "USD/MXN settles T+2 but the market quotes and clears around the clock; the peso is "
             "the only currency in this command with genuine 24-hour liquidity, which is what "
             "makes it usable as a hedge proxy at any hour",
     "window_utc": ("00:00", "23:59"), "instruments": ("USDMXN",)},
    {"name": "MexDer and CME expiry cycle", "kind": "week_of_month",
     "rule": "the peso derivative complex runs on a THIRD-WEDNESDAY cycle: MexDer's dollar "
             "future settles against the FIX around the third Wednesday of the contract month "
             "and the CME contract expires on the business day preceding it. The exact rule per "
             "venue must be confirmed from the venue's own contract specification before an "
             "expiry cell is compiled -- not from this line.",
     "weekday": 2, "week_of_month": 3, "roll": "previous",
     "window_utc": ("14:00", "20:00"), "instruments": ("USDMXN",)},
    {"name": "Remittance arrival", "kind": "month_end",
     "rule": "remesas concentrate at US pay periods and around Mexican holidays (Mother's Day in "
             "May and December are the two documented peaks); the monthly print lands about the "
             "first of the second following month",
     "months": (5, 12), "roll": "previous",
     "window_utc": ("14:00", "20:00"), "instruments": ("USDMXN",)},
    {"name": "AFORE monthly rebalancing", "kind": "month_end",
     "rule": "SIEFOREs are target-date funds with legislated foreign-asset limits; contributions "
             "arrive on a payroll cycle and are deployed to a glidepath, which makes a large "
             "share of Mexican institutional demand RULE-BASED and datable",
     "months": (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12), "roll": "previous",
     "window_utc": ("14:00", "20:00"), "instruments": ("USDMXN", "US500")},
    {"name": "Pemex sovereign hedge purchase", "kind": "quarter_end",
     "rule": "the federal government buys put options on Maya crude for the following fiscal "
             "year, historically executed over the northern summer and autumn. It is the largest "
             "single oil-options trade in the world and the PURCHASE moves the surface it is "
             "bought on.",
     "months": (6, 7, 8, 9, 10), "roll": "previous",
     "window_utc": ("14:00", "20:00"), "instruments": ("XTIUSD", "XBRUSD")},
)

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Bolsa Mexicana de Valores (BMV) and BIVA", "index_symbols": (),
     "index_symbols_absent": ("IPC", "FTSE BIVA"),
     "hours_local": "08:30-15:00 Mexico City", "hours_utc": "14:30-21:00",
     "expiry_rule": "index and single-stock derivatives trade at MexDer on a third-Wednesday "
                    "cycle; the equity market itself has a closing auction",
     "notes": "two competing exchanges share one order flow, which makes Mexican volume data "
              "harder to interpret than a single-venue market's"},
    {"name": "MexDer", "index_symbols": (), "index_symbols_absent": ("DEUA",),
     "hours_local": "07:30-14:00 Mexico City", "hours_utc": "13:30-20:00",
     "expiry_rule": "third-Wednesday cycle settling against the Banxico FIX; confirm the exact "
                    "rule from the contract specification before compiling an expiry cell",
     "notes": "thin against the CME contract, which is where the peso's real derivative liquidity "
              "sits -- an unusual case of a currency's own venue being the secondary one"},
    {"name": "CME peso complex (6M futures and options)", "index_symbols": (),
     "index_symbols_absent": ("6M",),
     "hours_local": "near-continuous", "hours_utc": "22:00-21:00 next day",
     "expiry_rule": "the business day immediately preceding the third Wednesday of the contract "
                    "month",
     "notes": "the deepest EM currency future in existence, and the reason the desk's COT axis "
              "carries USDMXN at all"},
)

# --------------------------------------------------------------------------- holidays
_MX_HOLIDAYS: dict[int, dict[str, str]] = {
    2024: {
        "2024-01-01": "Ano Nuevo", "2024-02-05": "Dia de la Constitucion (primer lunes)",
        "2024-03-18": "Natalicio de Benito Juarez (tercer lunes)",
        "2024-03-28": "Jueves Santo (feriado bancario)",
        "2024-03-29": "Viernes Santo (feriado bancario)",
        "2024-05-01": "Dia del Trabajo",
        "2024-09-16": "Dia de la Independencia",
        "2024-10-01": "Transmision del Poder Ejecutivo Federal (sexenal)",
        "2024-11-18": "Dia de la Revolucion (tercer lunes)",
        "2024-12-12": "Dia de la Virgen de Guadalupe (feriado bancario)",
        "2024-12-25": "Navidad",
    },
    2025: {
        "2025-01-01": "Ano Nuevo", "2025-02-03": "Dia de la Constitucion (primer lunes)",
        "2025-03-17": "Natalicio de Benito Juarez (tercer lunes)",
        "2025-04-17": "Jueves Santo (feriado bancario)",
        "2025-04-18": "Viernes Santo (feriado bancario)",
        "2025-05-01": "Dia del Trabajo",
        "2025-09-16": "Dia de la Independencia",
        "2025-11-17": "Dia de la Revolucion (tercer lunes)",
        "2025-12-12": "Dia de la Virgen de Guadalupe (feriado bancario)",
        "2025-12-25": "Navidad",
    },
    2026: {
        "2026-01-01": "Ano Nuevo", "2026-02-02": "Dia de la Constitucion (primer lunes)",
        "2026-03-16": "Natalicio de Benito Juarez (tercer lunes)",
        "2026-04-02": "Jueves Santo (feriado bancario)",
        "2026-04-03": "Viernes Santo (feriado bancario)",
        "2026-05-01": "Dia del Trabajo",
        "2026-09-16": "Dia de la Independencia",
        "2026-11-16": "Dia de la Revolucion (tercer lunes)",
        "2026-12-12": "Dia de la Virgen de Guadalupe (feriado bancario)",
        "2026-12-25": "Navidad",
    },
}

HOLIDAYS_RULE: dict[str, Any] = {
    "rule": (
        "Article 74 of the Ley Federal del Trabajo fixes the statutory days and MOVES three of "
        "them to a Monday: the Constitution day to the FIRST Monday of February, Juarez's "
        "birthday to the THIRD Monday of March, and the Revolution to the THIRD Monday of "
        "November. Independence Day (16 September) and Labour Day (1 May) are FIXED and never "
        "move. Article 74 also adds 1 October every SIX YEARS for the presidential transmission, "
        "which is why 2024 has a day 2025 and 2026 do not -- a recurring-rule generator that does "
        "not know about the sexenio will silently drop it.\n"
        "THE BANK CALENDAR IS NOT THE LABOUR CALENDAR and the FX market follows the BANK one. The "
        "CNBV calendar adds Jueves Santo, Viernes Santo and 12 December (Guadalupe), none of "
        "which is a statutory labour holiday. Those three are the days a Mexican FX study most "
        "often finds phantom sessions in. Weekends are Saturday and Sunday."),
    "table": _MX_HOLIDAYS,
    "years": (2024, 2025, 2026),
    "status": {2024: "CONFIRMED, including the sexenal 1 October",
               2025: "CONFIRMED",
               2026: "DERIVED from Article 74 plus the tabulated Easter and the CNBV bank days; "
                     "the CNBV publishes its calendar annually and that is the authority"},
    "weekly_closed": (5, 6),
    "note": "Mexico's market follows the US session more closely than any other in this command, "
            "so a US holiday with an open Mexican market is a THIN-LIQUIDITY day rather than a "
            "closure, and it belongs in a liquidity control rather than in this table",
}


def holidays(year: int) -> dict[str, str]:
    """The bank-calendar closure table for one year; `{}` for a year this pack does not declare."""
    return dict(_MX_HOLIDAYS.get(year) or {})


def is_closed(day: date) -> bool:
    """True when the Mexican bank and FX market is closed (weekends included)."""
    return day.weekday() >= 5 or day.isoformat() in holidays(day.year)


# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "CFTC Commitments of Traders -- CME Mexican peso (6M)",
     "publisher": "CFTC", "frequency": "weekly", "lag": "Friday 15:30 ET for Tuesday positions",
     "field": "non-commercial net, open interest",
     "why": "THE ONLY LATIN AMERICAN CURRENCY IN THE DESK'S COT AXIS. USDMXN is mapped in "
            "data/axes/cot.json, so a positioning cell here can be compiled TODAY -- and because "
            "the peso is the world's EM hedge proxy, this net is a measurement of global EM "
            "positioning rather than of Mexican opinion",
     "pit": True, "status": "AVAILABLE on this box"},
    {"name": "Banxico foreign holdings of Bonos M and Cetes",
     "publisher": "Banxico SIE", "frequency": "weekly", "lag": "about one week",
     "field": "non-resident holdings by instrument",
     "why": "the real-money leg of the Mexican carry trade; foreign ownership of Bonos M fell by "
            "more than half from its peak and that unwind is a dated, measured flow",
     "pit": True, "status": "declared; needs the Banxico token"},
    {"name": "CONSAR AFORE / SIEFORE portfolio reports",
     "publisher": "CONSAR", "frequency": "monthly", "lag": "about 30 days",
     "field": "assets by SIEFORE, foreign-asset share, instrument mix",
     "why": "the domestic institutional bid; its foreign-asset limit is legislated, so a change "
            "in the limit is a dated structural flow event rather than a preference shift",
     "pit": True, "status": "declared; public, not collected on this box"},
    {"name": "Banxico FX NDF programme auction results",
     "publisher": "Banxico", "frequency": "event", "lag": "same day",
     "field": "auction size, allotment, outstanding",
     "why": "peso-settled forwards rather than spot sales, so intervention does not spend "
            "reserves; the announcement is the observable and it is same-day",
     "pit": True, "status": "declared; public, not collected"},
)

# --------------------------------------------------------------------------- terminology
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "policy": ("Banxico", "Banco de Mexico", "Junta de Gobierno", "tasa objetivo",
               "tasa de referencia", "anuncio de politica monetaria", "minuta",
               "Informe Trimestral", "objetivo de inflacion", "INPC", "inflacion subyacente",
               "TIIE", "TIIE de Fondeo", "UDI", "Comision de Cambios", "subasta de coberturas"),
    "fx": ("tipo de cambio FIX", "peso mexicano", "superpeso", "depreciacion del peso",
           "carry trade en pesos", "operar dolar", "spot interbancario", "coberturas cambiarias",
           "NDF liquidable en pesos", "linea swap con la Fed", "volatilidad del peso"),
    "flows": ("remesas familiares", "remesas", "inversion extranjera directa", "IED",
              "nearshoring", "relocalizacion", "T-MEC", "USMCA", "revision del T-MEC",
              "exportaciones manufactureras", "maquiladora", "IMMEX", "balanza comercial"),
    "market": ("BMV", "BIVA", "IPC", "MexDer", "DEUA", "Bonos M", "Cetes", "Udibonos",
               "casa de bolsa", "AFORE", "SIEFORE", "CONSAR", "Indeval", "Asigna",
               "tenencia de extranjeros"),
    "energy": ("Pemex", "mezcla mexicana", "crudo Maya", "CNH", "Comision Nacional de "
               "Hidrocarburos", "plataforma de produccion", "cobertura petrolera",
               "Dos Bocas", "CFE", "reforma energetica", "huachicol"),
    "mining_agri": ("Grupo Mexico", "plata", "produccion de plata", "concentrados",
                    "maiz blanco", "importacion de maiz", "cafe mexicano", "azucar",
                    "cuota azucarera", "aguacate", "exportacion agroalimentaria"),
    "community": ("El Financiero", "El Economista", "Expansion", "Rankia Mexico",
                  "trader mexicano", "bolsa de valores foro", "inversionista minorista"),
}

# --------------------------------------------------------------------------- source classes
#: THE TEN LAYERS (principal's per-country depth rule, 2026-09-17). A country is never "covered"
#: by five obvious sources. A layer with no source must be NAMED ABSENT WITH A REASON in
#: `LAYER_ABSENCES`; blank is never an answer (L1.28a).
SOURCE_LAYERS: tuple[str, ...] = (
    "official", "institutional", "academic", "practitioner", "retail_ecology", "app_ecosystem",
    "media", "archive", "physical_economy", "source_graph")

#: Three INDEPENDENT labels per source: a PUBLIC source can be FRINGE and still PREDICTIVE, and an
#: AUTHORITATIVE one can be NOT_PREDICTIVE. Collapsing them into a single quality score is how a
#: desk discards the fringe material that works and privileges the official series that does not.
ACCESS_LABELS: tuple[str, ...] = (
    "PUBLIC", "PUBLIC_WITH_TERMS", "LICENSED", "OPEN_DATA", "PUBLIC_ARCHIVE", "PUBLIC_SOCIAL",
    "USER_SUBMITTED", "ACCESS_UNCLEAR", "PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")
CREDIBILITY: tuple[str, ...] = ("AUTHORITATIVE", "RELIABLE", "UNRELIABLE", "FRINGE",
                                "CONTRADICTED", "UNKNOWN")
PREDICTIVE_STATES: tuple[str, ...] = ("UNTESTED", "PREDICTIVE", "NOT_PREDICTIVE",
                                      "NARRATIVE_FEATURE")

SOURCE_CLASSES: tuple[dict[str, Any], ...] = (
    {"id": "mx_banxico_sie", "layer": "official",
     "label": "Banxico SIE (Sistema de Informacion Economica) REST API",
     "roots": ("https://www.banxico.org.mx/SieAPIRest/service/v1/series/",
               "https://www.banxico.org.mx/SieAPIRest/service/v1/doc/catalogoSeries"),
     "languages": ("es-MX", "en"),
     "licence": "free, but REQUIRES a registered token sent in the Bmx-Token header",
     "access_label": "PUBLIC_WITH_TERMS", "credibility": "AUTHORITATIVE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("serie tipo de cambio FIX SF43718 historico",
                 "remesas familiares serie mensual Banxico",
                 "tenencia de valores gubernamentales por residentes en el extranjero",
                 "objetivo de la tasa de interes interbancaria a un dia serie"),
     "notes": "the credential this command's shared secrets schema calls `banxico_token`. Until "
              "it exists every Banxico series is UNMEASURED BY NAME, which the Brazilian and "
              "Andean lanes already report -- a credential gap, never a data gap"},
    {"id": "mx_inegi", "layer": "official",
     "label": "INEGI (INPC, IGAE, trade, employment) and the DOF",
     "roots": ("https://www.inegi.org.mx/servicios/api_indicadores.html",
               "https://www.dof.gob.mx/"),
     "languages": ("es-MX",), "licence": "public open data; the INEGI API needs a free token",
     "access_label": "OPEN_DATA", "credibility": "AUTHORITATIVE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("INPC quincenal variacion", "IGAE indicador global de actividad economica",
                 "exportaciones manufactureras balanza comercial mensual",
                 "decreto husos horarios publicacion DOF"),
     "notes": "the FORTNIGHTLY CPI is unusual and useful: Mexico prints inflation twice a month, "
              "so the surprise term has roughly double the observations of a monthly economy"},
    {"id": "mx_shcp_cnh", "layer": "official",
     "label": "SHCP fiscal statistics, CNH hydrocarbon production and the oil hedge",
     "roots": ("https://www.finanzaspublicas.hacienda.gob.mx/", "https://www.cnh.gob.mx/",
               "https://sih.hidrocarburos.gob.mx/"),
     "languages": ("es-MX",), "licence": "public open data",
     "access_label": "OPEN_DATA", "credibility": "AUTHORITATIVE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("produccion de crudo por campo mensual CNH",
                 "cobertura petrolera costo primas ejercicio fiscal",
                 "precio de la mezcla mexicana de exportacion",
                 "ingresos petroleros presupuesto"),
     "notes": "the sovereign oil hedge's cost is published in the fiscal accounts, which means "
              "the world's largest oil-options trade leaves a public, dated footprint"},
    {"id": "mx_bmv_cnbv", "layer": "institutional",
     "label": "BMV, BIVA, MexDer, CNBV and CONSAR",
     "roots": ("https://www.bmv.com.mx/", "https://www.biva.mx/", "https://www.mexder.com.mx/",
               "https://www.gob.mx/cnbv", "https://www.gob.mx/consar"),
     "languages": ("es-MX",),
     "licence": "public summary data and public regulatory statistics; depth is licensed",
     "access_label": "PUBLIC_WITH_TERMS", "credibility": "AUTHORITATIVE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("calendario de dias inhabiles CNBV bancos",
                 "especificaciones del contrato DEUA MexDer vencimiento",
                 "informacion estadistica SIEFORE cartera por instrumento",
                 "limite de inversion en valores extranjeros SIEFORE"),
     "notes": "THE CNBV BANK CALENDAR IS THE ONE THE FX MARKET FOLLOWS, and it differs from the "
              "labour calendar on three days a year -- the days Mexican FX studies find phantom "
              "sessions"},
    {"id": "mx_academic", "layer": "academic",
     "label": "Mexican academic economics (Banxico working papers, El Colegio de Mexico, ITAM, "
              "CIDE)",
     "roots": ("https://www.banxico.org.mx/publicaciones-y-prensa/documentos-de-investigacion/",
               "https://cee.colmex.mx/", "https://ciep.itam.mx/", "https://www.cide.edu/"),
     "languages": ("es-MX", "en"), "licence": "open-access working papers",
     "access_label": "PUBLIC", "credibility": "RELIABLE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("determinantes del tipo de cambio peso dolar documento de investigacion",
                 "remesas y ciclo economico Mexico estimacion",
                 "traspaso del tipo de cambio a precios Mexico",
                 "el peso como moneda de cobertura liquidez"),
     "notes": "the 'peso as hedge proxy' claim is documented in this literature, which makes it a "
              "hypothesis with a citation rather than desk folklore -- and still a hypothesis"},
    {"id": "mx_practitioner", "layer": "practitioner",
     "label": "Mexican sell-side research and the Citibanamex expectations panel",
     "roots": ("https://www.banorte.com/wps/portal/gfb/Home/analisis-economico",
               "https://www.bbva.mx/personas/analisis-economico.html",
               "https://www.citibanamex.com/economia-finanzas/es/analisis/",
               "https://www.rankia.mx/foros/bolsa-mexico/"),
     "languages": ("es-MX",),
     "licence": "public web with terms; claims extracted only, nothing republished",
     "access_label": "PUBLIC_WITH_TERMS", "credibility": "RELIABLE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("encuesta Citibanamex expectativas tasa tipo de cambio",
                 "estrategia de carry en pesos recomendacion",
                 "cobertura cambiaria corporativa costo forward",
                 "revision del T-MEC escenarios impacto peso"),
     "notes": "the Citibanamex survey is quoted AS the consensus by the Mexican market, which "
              "makes it the surprise benchmark whether or not it is the best forecast"},
    {"id": "mx_retail_ecology", "layer": "retail_ecology",
     "label": "Mexican retail investor communities",
     "roots": ("https://www.rankia.mx/", "https://www.reddit.com/r/MexicoFinanciero/",
               "https://www.reddit.com/r/mexico/", "https://www.eleconomista.com.mx/foros/"),
     "languages": ("es-MX",),
     "licence": "public social; user-submitted content, nothing republished",
     "access_label": "PUBLIC_SOCIAL", "credibility": "UNRELIABLE",
     "predictive_state": "NARRATIVE_FEATURE", "machine_use_allowed": True,
     "queries": ("comprar dolares ahora o esperar foro",
                 "superpeso hasta cuando opiniones",
                 "invertir en Cetes o en dolares cual conviene",
                 "operar dolar en GBM+ comisiones"),
     "notes": "UNRELIABLE AND KEPT. Mexican retail dollar demand is procyclical and reflexive; "
              "the 'superpeso' narrative in 2023-24 is a documented case of a crowd belief that "
              "coincided with a real positioning extreme"},
    {"id": "mx_app_ecosystem", "layer": "app_ecosystem",
     "label": "Mexican retail brokerage apps and automation",
     "roots": ("https://gbm.com/", "https://www.kuspit.com/", "https://www.actinver.com/",
               "https://nu.com.mx/", "https://www.mql5.com/es/code"),
     "languages": ("es-MX",), "licence": "public web with terms; public code repositories",
     "access_label": "PUBLIC_WITH_TERMS", "credibility": "UNRELIABLE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("GBM+ comprar dolares cuenta de inversion",
                 "bot de trading peso dolar codigo",
                 "Cetes directo rendimiento aplicacion",
                 "Nu inversion cuenta rendimiento diario"),
     "notes": "the Mexican app layer changed WHO holds dollars: retail dollar accounts inside "
              "fintech apps are a new, growing, and datable source of domestic FX demand that no "
              "pre-2020 Mexican study can contain"},
    {"id": "mx_media", "layer": "media",
     "label": "Mexican financial press",
     "roots": ("https://www.elfinanciero.com.mx/", "https://www.eleconomista.com.mx/",
               "https://expansion.mx/", "https://www.reforma.com/negocios/"),
     "languages": ("es-MX",),
     "licence": "public web with terms; several paywalled, nothing republished",
     "access_label": "PUBLIC_WITH_TERMS", "credibility": "RELIABLE",
     "predictive_state": "NARRATIVE_FEATURE", "machine_use_allowed": True,
     "queries": ("peso cierra sesion tipo de cambio hoy",
                 "Banxico recorta tasa decision reaccion",
                 "remesas rompen record mes", "T-MEC revision aranceles Mexico"),
     "notes": "a dating source for the unscheduled trade-policy headlines that dominate this "
              "currency, which no official calendar carries"},
    {"id": "mx_archive", "layer": "archive",
     "label": "Historical archives: DOF, Hemeroteca Nacional Digital, Banxico historical series",
     "roots": ("https://www.dof.gob.mx/index_113.php", "https://hndm.iib.unam.mx/",
               "https://web.archive.org/web/*/banxico.org.mx/*"),
     "languages": ("es-MX",),
     "licence": "public archive; official gazette and digitised public-domain press",
     "access_label": "PUBLIC_ARCHIVE", "credibility": "AUTHORITATIVE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("decreto husos horarios 2022 texto DOF",
                 "reglas de la comision de cambios subasta coberturas publicacion",
                 "metodologia del tipo de cambio FIX circular Banxico",
                 "articulo 74 ley federal del trabajo reforma dias de descanso"),
     "notes": "THE DST ABOLITION AND THE ARTICLE 74 MONDAY RULE ARE BOTH GAZETTE FACTS, and both "
              "are silent breaks in every Mexican intraday and calendar study that does not "
              "date them"},
    {"id": "mx_physical_economy", "layer": "physical_economy",
     "label": "Physical flow: border crossings, ports, power, oil and remittance corridors",
     "roots": ("https://www.bts.gov/browse-statistical-products-and-data/border-crossing-data/"
               "border-crossingentry-data",
               "https://www.gob.mx/puertosymarinamercante",
               "https://www.cenace.gob.mx/", "https://sih.hidrocarburos.gob.mx/"),
     "languages": ("es-MX", "en"), "licence": "public open data (US and Mexican)",
     "access_label": "OPEN_DATA", "credibility": "AUTHORITATIVE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("cruces fronterizos camiones de carga mensual Laredo",
                 "movimiento de carga contenerizada Manzanillo estadistica",
                 "demanda electrica CENACE industrial",
                 "produccion de crudo por campo plataforma"),
     "notes": "TRUCK CROSSINGS ARE THE NEARSHORING CLAIM'S ONLY COUNTED QUANTITY. The narrative "
              "is everywhere and the number is here; a nearshoring cell that does not use it is "
              "testing a story"},
    {"id": "mx_source_graph", "layer": "source_graph",
     "label": "The graph that finds the NEXT Mexican source",
     "roots": ("https://datos.gob.mx/", "https://www.banxico.org.mx/SieAPIRest/service/v1/doc/",
               "https://github.com/topics/mexico-data",
               "https://www.inegi.org.mx/datosabiertos/"),
     "languages": ("es-MX", "en"),
     "licence": "public; open-data catalogues and API series catalogues",
     "access_label": "PUBLIC", "credibility": "RELIABLE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("catalogo de series SIE Banxico buscar identificador",
                 "datos abiertos Mexico conjunto economia finanzas",
                 "quien cita las series de remesas metodologia",
                 "repositorio github datos Banxico INEGI"),
     "notes": "the SIE CATALOGUE ENDPOINT is itself a discovery instrument -- it answers 'which "
              "series id carries this concept', which is the question that keeps a Mexican "
              "catalogue from being a list of four ids somebody memorised"},
)

LAYER_ABSENCES: dict[str, str] = {}

# --------------------------------------------------------------------------- datasets
DATASETS: tuple[dict[str, Any], ...] = (
    {"name": "Tipo de cambio FIX (Banxico SIE SF43718)", "source": "mx_banxico_sie",
     "coverage": "1991 to present", "frequency": "daily",
     "publication_lag_days": 1.0, "revisions": "none",
     "licence": "free with a token", "history_from": "1991-11-12", "pit_feasible": True,
     "assets": ("USDMXN",),
     "mechanism_families": ("calendar_settlement", "session_microstructure"),
     "how_to_fetch": "GET banxico.org.mx/SieAPIRest/service/v1/series/SF43718/datos with the "
                     "Bmx-Token header; determined one day and APPLIED the next"},
    {"name": "Tasa objetivo de Banxico", "source": "mx_banxico_sie",
     "coverage": "2008 to present", "frequency": "event",
     "publication_lag_days": 0.0, "revisions": "none",
     "licence": "free with a token", "history_from": "2008-01-21", "pit_feasible": True,
     "assets": ("USDMXN", "UST10Y", "MXNJPY"),
     "mechanism_families": ("central_bank_surprise", "carry_funding"),
     "how_to_fetch": "Banxico SIE; confirm the series id against the SIE catalogue endpoint"},
    {"name": "Remesas familiares (monthly)", "source": "mx_banxico_sie",
     "coverage": "1995 to present", "frequency": "monthly",
     "publication_lag_days": 32.0, "revisions": "revised one period back",
     "licence": "free with a token", "history_from": "1995-01-31", "pit_feasible": True,
     "assets": ("USDMXN", "US500"),
     "mechanism_families": ("corporate_flow", "release_surprise"),
     "how_to_fetch": "Banxico SIE remesas series; driven by US EMPLOYMENT, not by Mexican "
                     "competitiveness, which is why it is counter-cyclical to the peso"},
    {"name": "Tenencia de valores gubernamentales por extranjeros", "source": "mx_banxico_sie",
     "coverage": "2003 to present", "frequency": "weekly",
     "publication_lag_days": 7.0, "revisions": "none",
     "licence": "free with a token", "history_from": "2003-01-02", "pit_feasible": True,
     "assets": ("USDMXN", "UST10Y"),
     "mechanism_families": ("positioning", "institutional_flow"),
     "how_to_fetch": "Banxico SIE; the real-money carry leg, and its multi-year unwind is the "
                     "single largest measured Mexican flow of the sample"},
    {"name": "INPC quincenal y mensual", "source": "mx_inegi",
     "coverage": "1969 to present", "frequency": "fortnightly and monthly",
     "publication_lag_days": 9.0, "revisions": "none",
     "licence": "public open data", "history_from": "1969-01-31", "pit_feasible": True,
     "assets": ("USDMXN", "UST10Y"),
     "mechanism_families": ("release_surprise", "central_bank_surprise"),
     "how_to_fetch": "INEGI indicator API; the FORTNIGHTLY print roughly doubles the number of "
                     "inflation-surprise observations against a monthly economy"},
    {"name": "Balanza comercial y exportaciones manufactureras", "source": "mx_inegi",
     "coverage": "1993 to present", "frequency": "monthly",
     "publication_lag_days": 25.0, "revisions": "revised once",
     "licence": "public open data", "history_from": "1993-01-31", "pit_feasible": True,
     "assets": ("USDMXN", "US500", "US2000"),
     "mechanism_families": ("corporate_flow", "release_surprise"),
     "how_to_fetch": "INEGI indicator API; the manufacturing leg is the US cycle and the "
                     "petroleum leg is its own object"},
    {"name": "Produccion de crudo por campo (CNH)", "source": "mx_shcp_cnh",
     "coverage": "2000 to present", "frequency": "monthly",
     "publication_lag_days": 45.0, "revisions": "restated when a field reports late",
     "licence": "public open data", "history_from": "2000-01-31", "pit_feasible": True,
     "assets": ("XTIUSD", "XBRUSD", "USDMXN"),
     "mechanism_families": ("corporate_flow", "failure"),
     "how_to_fetch": "CNH SIH open data portal; the long production decline is a structural "
                     "change in Mexico's dollar supply and is separable from the crude price"},
    {"name": "Cobertura petrolera cost and strike (SHCP fiscal accounts)",
     "source": "mx_shcp_cnh",
     "coverage": "2001 to present", "frequency": "annual",
     "publication_lag_days": 90.0, "revisions": "none",
     "licence": "public", "history_from": "2001-12-31", "pit_feasible": True,
     "assets": ("XTIUSD", "XBRUSD"),
     "mechanism_families": ("institutional_flow", "positioning"),
     "how_to_fetch": "SHCP finanzas publicas reports; the world's largest single oil-options "
                     "trade, executed over the northern summer and autumn, with a published cost"},
    {"name": "SIEFORE portfolios and the foreign-asset limit", "source": "mx_bmv_cnbv",
     "coverage": "1997 to present", "frequency": "monthly",
     "publication_lag_days": 30.0, "revisions": "none",
     "licence": "public open statistics", "history_from": "1997-07-31", "pit_feasible": True,
     "assets": ("USDMXN", "US500", "UST10Y"),
     "mechanism_families": ("institutional_flow", "positioning"),
     "how_to_fetch": "CONSAR statistical series; a LEGISLATED limit change is a dated structural "
                     "flow event rather than a preference shift"},
    {"name": "US-Mexico border truck crossings", "source": "mx_physical_economy",
     "coverage": "1995 to present", "frequency": "monthly",
     "publication_lag_days": 60.0, "revisions": "none",
     "licence": "public open data (US BTS)", "history_from": "1995-01-31", "pit_feasible": True,
     "assets": ("USDMXN", "US2000", "US500"),
     "mechanism_families": ("corporate_flow", "transfer"),
     "how_to_fetch": "BTS border crossing data; THE NEARSHORING CLAIM'S ONLY COUNTED QUANTITY"},
    {"name": "CNBV bank-holiday calendar", "source": "mx_bmv_cnbv",
     "coverage": "annual", "frequency": "annual",
     "publication_lag_days": 0.0, "revisions": "none",
     "licence": "public", "history_from": "2000-01-01", "pit_feasible": True,
     "assets": ("USDMXN",),
     "mechanism_families": ("holiday_liquidity", "calendar_settlement"),
     "how_to_fetch": "CNBV dias inhabiles circular; THE FX MARKET FOLLOWS THIS AND NOT THE "
                     "LABOUR CALENDAR, and the two differ on three days a year"},
    {"name": "Mexican practitioner and retail mechanism claims (es-MX)",
     "source": "mx_retail_ecology",
     "coverage": "rolling", "frequency": "continuous",
     "publication_lag_days": 0.0, "revisions": "n/a -- dated at capture",
     "licence": "public social, claims only", "history_from": "2015-01-01", "pit_feasible": False,
     "assets": ("USDMXN",),
     "mechanism_families": ("scouts", "transfer"),
     "how_to_fetch": "deep_forest_miner grounds in es-MX; the 'superpeso' episode is the "
                     "documented case of a crowd belief coinciding with a positioning extreme"},
)

# --------------------------------------------------------------------------- actors
ACTORS: tuple[dict[str, Any], ...] = (
    {"name": "global macro fund using MXN as its EM hedge",
     "holds": "EM risk it cannot hedge directly, expressed as a short peso position",
     "forced_to": ("sell the peso when it needs to reduce EM risk in any country",
                   "cover when the risk passes, regardless of Mexican news"),
     "when": "whenever global risk appetite turns, at any hour",
     "information": ("global equity vol", "US rates", "EM credit spreads"),
     "constraints": ("the peso is the only EM currency liquid enough to trade in size at 03:00 "
                     "UTC",
                     "hedging a basket in its most liquid member is standard practice"),
     "instruments": ("USDMXN", "MXNJPY", "USDZAR", "USDBRL", "US500"),
     "counterparties": ("banks", "CME", "other macro funds"),
     "observables": ("CFTC 6M net", "USDMXN vol versus peer vol", "overnight range share"),
     "impact": "USDMXN carries a GLOBAL factor larger than its Mexican one; this is the pack's "
               "central research object and its central warning",
     "persistence": "episodic and fast; the proxy role is permanent",
     "falsifier": "USDMXN shows no excess sensitivity to global risk relative to USDBRL and "
                  "USDZAR after controlling for carry and vol -- which would mean the proxy role "
                  "is folklore",
     "notes": "MXNJPY is in the executable set to separate this from a Mexican move"},
    {"name": "Mexican migrant worker sending remittances",
     "holds": "US wages and a family in Mexico",
     "forced_to": ("send a broadly fixed peso amount, which means MORE dollars when the peso is "
                   "strong and fewer when it is weak",
                   "send around pay periods and family dates"),
     "when": "monthly, peaking around Mother's Day in May and in December",
     "information": ("US employment", "the exchange rate", "transfer costs"),
     "constraints": ("the recipient's needs are in pesos and are not price-elastic",
                     "US labour demand sets the income, not Mexican conditions"),
     "instruments": ("USDMXN", "US500"),
     "counterparties": ("remittance operators", "Mexican banks"),
     "observables": ("the monthly remesas print", "US Hispanic employment"),
     "impact": "a sixty-billion-dollar annual inflow driven by US EMPLOYMENT and partly "
               "counter-cyclical to the peso -- the opposite sign to every other dollar inflow "
               "in this command",
     "persistence": "structural; the seasonal is stable",
     "falsifier": "no measurable relationship between remittance surprises and USDMXN once US "
                  "employment surprises are controlled for, which would make remesas a "
                  "transmission of the US cycle and not an independent flow",
     "notes": "the counter-cyclicality is the testable part"},
    {"name": "Pemex and the sovereign oil hedge",
     "holds": "declining production, a heavy sour crude grade and the world's largest sovereign "
              "oil hedge",
     "forced_to": ("buy put options on Maya for the following fiscal year, every year",
                   "service a very large dollar debt stack"),
     "when": "the hedge is executed over the northern summer and autumn",
     "information": ("the fiscal budget's oil price assumption", "CNH production data",
                     "the Maya differential"),
     "constraints": ("the hedge is a budget requirement rather than a view",
                     "production decline is geological and is not a policy choice"),
     "instruments": ("XTIUSD", "XBRUSD", "USDMXN"),
     "counterparties": ("investment banks", "the crude options market"),
     "observables": ("the published hedge cost", "CNH production", "budget assumptions"),
     "impact": "THE PURCHASE MOVES THE SURFACE IT IS BOUGHT ON. A single buyer this size in crude "
               "puts is a dated, recurring, one-directional options flow",
     "persistence": "annual and reliable",
     "falsifier": "no measurable seasonality in crude put skew over the historical execution "
                  "window beyond what the level of crude explains",
     "notes": "named as an actor; Pemex is not in the broker registry and never a symbol here"},
    {"name": "maquiladora and nearshoring manufacturer",
     "holds": "export plants selling into the United States under USMCA rules",
     "forced_to": ("convert dollar receipts to pesos for local payroll",
                   "invest ahead of demand when a supply chain relocates"),
     "when": "continuous; investment decisions cluster around trade-policy dates",
     "information": ("truck crossings", "FDI flows", "USMCA review news"),
     "constraints": ("rules of origin are legal constraints with dated reviews",
                     "plant capacity takes years to build"),
     "instruments": ("USDMXN", "US2000", "US500"),
     "counterparties": ("US buyers", "Mexican banks", "the labour market"),
     "observables": ("BTS truck crossings", "manufacturing exports", "FDI"),
     "impact": "the structural dollar inflow behind the 'superpeso' era; it is a QUANTITY and it "
               "is counted at the border",
     "persistence": "years, and dependent on a dated policy review",
     "falsifier": "no relationship between truck-crossing growth and the peso's real appreciation "
                  "once the carry differential is controlled for",
     "notes": "the nearshoring claim's only counted quantity is in this actor's observables"},
    {"name": "AFORE / SIEFORE pension manager",
     "holds": "mandatory contributions in target-date funds with a legislated foreign limit",
     "forced_to": ("deploy payroll contributions on a glidepath every month",
                   "rebalance when the foreign-asset limit changes"),
     "when": "monthly contributions; limit changes are legislated and dated",
     "information": ("CONSAR reports", "the legislated limit", "the glidepath"),
     "constraints": ("investment limits are regulatory",
                     "contributions arrive whether or not the manager wants to buy"),
     "instruments": ("USDMXN", "US500", "UST10Y"),
     "counterparties": ("global managers", "the Treasury", "local banks"),
     "observables": ("SIEFORE portfolio reports", "the foreign share", "flows by fund"),
     "impact": "a rule-based, involuntary, monthly institutional bid; a LIMIT CHANGE is a dated "
               "structural flow event with a public date",
     "persistence": "permanent and growing with the contribution rate reform",
     "falsifier": "no measurable FX or asset-price effect around legislated limit changes",
     "notes": "the Mexican analogue of Chile's AFP without the newsletter-driven switching"},
    {"name": "foreign real-money holder of Bonos M",
     "holds": "a local-currency Mexican bond position, once the largest foreign share in EM",
     "forced_to": ("cut when the carry-to-vol ratio deteriorates",
                   "hedge the FX leg separately from the duration leg"),
     "when": "the unwind has run for years rather than days",
     "information": ("Banxico's weekly foreign-holdings series", "the carry differential",
                     "index inclusion rules"),
     "constraints": ("index weights are mechanical",
                     "a local-currency position is two risks and they can be hedged apart"),
     "instruments": ("USDMXN", "UST10Y", "MXNJPY"),
     "counterparties": ("local banks", "Banxico", "index funds"),
     "observables": ("the weekly foreign-holdings print", "CFTC positioning"),
     "impact": "the slowest and largest measured Mexican flow of the sample; foreign ownership "
               "fell by more than half from its peak and the series is weekly",
     "persistence": "multi-year",
     "falsifier": "no relationship between the foreign-holdings series and USDMXN once the "
                  "carry differential and global risk are controlled for",
     "notes": "a rare case where a large flow is published weekly rather than quarterly"},
    {"name": "Banxico as an FX intervenor through NDFs",
     "holds": "reserves, a Fed swap line, and a peso-settled forward programme",
     "forced_to": ("announce and auction NDFs when disorder is judged excessive",
                   "avoid spending reserves, which is why the programme is peso-settled"),
     "when": "announced, episodic",
     "information": ("realised vol", "the reserve level", "market functioning"),
     "constraints": ("a floating mandate means no level target may be admitted",
                     "peso settlement means intervention does not deplete reserves"),
     "instruments": ("USDMXN",),
     "counterparties": ("local banks", "offshore funds"),
     "observables": ("auction announcements and allotments", "outstanding NDF stock"),
     "impact": "a dated, sized, announced hedge supply -- the same observable shape as Brazil's "
               "swap book and the opposite of Argentina's opacity",
     "persistence": "episodic",
     "falsifier": "no USDMXN response to announced NDF auctions beyond what the vol level at "
                  "announcement predicts",
     "notes": "three intervention styles across BR, CL and MX is a natural experiment"},
    {"name": "Mexican corporate hedging its dollar debt",
     "holds": "dollar liabilities against peso revenue",
     "forced_to": ("hedge at the FIX because that is the contractual reference",
                   "roll hedges on a quarterly reporting cycle"),
     "when": "around the midday FIX window and at quarter ends",
     "information": ("the FIX", "the forward curve", "TIIE"),
     "constraints": ("hedge accounting fixes the tenor and the reference",
                     "covenants force a minimum hedge ratio"),
     "instruments": ("USDMXN",),
     "counterparties": ("local and international banks",),
     "observables": ("FIX-window volume", "corporate disclosure", "forward outstanding"),
     "impact": "the mechanical source of any FIX-window microstructure effect; the window is at a "
               "FIXED UTC minute year-round, which makes it unusually easy to test",
     "persistence": "permanent",
     "falsifier": "no excess volatility or volume in USDMXN in the minutes around the FIX window "
                  "relative to matched control minutes on the same days",
     "notes": "the one Mexican mechanism measurable on this box today with bars and a clock"},
    {"name": "silver and base-metals producer",
     "holds": "the world's largest silver output plus significant copper and zinc",
     "forced_to": ("sell into the market continuously",
                   "suspend when a strike or a community dispute closes a mine"),
     "when": "continuous, with episodic disruptions",
     "information": ("production reports", "the silver-gold ratio", "strike news"),
     "constraints": ("silver is largely a BY-PRODUCT of copper, lead and zinc mining, so its "
                     "supply responds to the base metals' economics rather than to its own price",),
     "instruments": ("XAGUSD", "XAUUSD", "XCUUSD", "XZNUSD"),
     "counterparties": ("refiners", "traders", "industrial buyers"),
     "observables": ("INEGI and company production data", "export volumes"),
     "impact": "silver's supply is price-INELASTIC to its own price because it is a by-product; "
               "Mexico is the largest single source of that inelastic supply",
     "persistence": "structural",
     "falsifier": "Mexican silver output responds to the silver price with the same elasticity as "
                  "to the base-metals complex, which would refute the by-product mechanism",
     "notes": "the reason silver's supply curve is the shape it is, and the reason XAGUSD belongs "
              "in this pack's executable set"},
    {"name": "Mexican retail saver holding dollars in a fintech app",
     "holds": "peso savings with one-tap access to dollar accounts and Cetes",
     "forced_to": ("switch when the narrative turns, in size, quickly",
                   "chase the highest advertised yield"),
     "when": "reflexive, clustered on media narratives",
     "information": ("app interfaces", "media headlines", "the 'superpeso' narrative"),
     "constraints": ("the switch costs nothing and takes seconds, which is new",
                     "deposit insurance and product limits"),
     "instruments": ("USDMXN",),
     "counterparties": ("fintechs", "banks"),
     "observables": ("bank dollar-deposit series", "app disclosures", "media volume"),
     "impact": "a NEW and growing source of domestic FX demand that can move within a day; no "
               "pre-2020 Mexican study contains it",
     "persistence": "structural and growing",
     "falsifier": "no measurable change in the speed of domestic dollar-deposit responses to "
                  "narrative shocks after the fintech expansion dates",
     "notes": "the app-ecosystem layer exists in this pack because of this actor"},
    {"name": "US importer and the USMCA review",
     "holds": "supply chains routed through Mexico under rules of origin",
     "forced_to": ("re-route if the rules change at the scheduled review",
                   "pre-position inventory ahead of a dated policy risk"),
     "when": "THE USMCA JOINT REVIEW FALLS IN 2026 -- a scheduled, dated risk event",
     "information": ("review documents", "tariff announcements", "rules-of-origin guidance"),
     "constraints": ("rules of origin are legal and the review date is treaty-set",
                     "re-routing a supply chain takes years"),
     "instruments": ("USDMXN", "US2000", "US500"),
     "counterparties": ("Mexican manufacturers", "US and Canadian governments"),
     "observables": ("truck crossings", "FDI announcements", "the review calendar"),
     "impact": "the largest SCHEDULED Mexican risk event in the sample, and scheduled risk "
               "behaves differently from a headline -- it can be pre-positioned for",
     "persistence": "the review is a date; its consequences are years",
     "falsifier": "no measurable USDMXN implied-vol term structure response to the review date as "
                  "it approaches, which would mean the market does not treat it as an event",
     "notes": "the vol term structure is the cleanest test of whether a DATE is priced"},
    {"name": "food importer and the maize balance",
     "holds": "a large and growing dependence on imported maize and grains",
     "forced_to": ("buy dollars and grain continuously",
                   "hedge when the peso or the grain price moves against the budget"),
     "when": "continuous, with a seasonal shape",
     "information": ("import statistics", "CBOT prices", "the peso"),
     "constraints": ("domestic white-maize production does not cover consumption",
                     "food prices are politically sensitive and are a CPI weight"),
     "instruments": ("CORN", "WHEAT", "USDMXN", "SUGAR"),
     "counterparties": ("US exporters", "millers"),
     "observables": ("INEGI import data", "CBOT prices", "the food CPI component"),
     "impact": "a grain price shock is a Mexican INFLATION shock with a currency multiplier, "
               "which links the softs complex to the Banxico reaction function",
     "persistence": "structural",
     "falsifier": "no relationship between grain-price shocks and the food component of the "
                  "Mexican CPI once the exchange rate is controlled for",
     "notes": "the link from the softs book to a central-bank reaction function, which is unusual "
              "and is what makes CORN and WHEAT executable instruments in a currency pack"},
    {"name": "Mexican bank running the FIX and the TIIE book",
     "holds": "the FX book the FIX is computed from and a TIIE-linked balance sheet",
     "forced_to": ("quote into the FIX window", "manage the TIIE-to-Fondeo transition"),
     "when": "the midday FIX window; continuously for funding",
     "information": ("client flow", "the FIX methodology", "the TIIE transition timetable"),
     "constraints": ("regulatory exposure limits",
                     "the reference-rate transition is a mandated timetable"),
     "instruments": ("USDMXN",),
     "counterparties": ("corporates", "Banxico", "offshore funds"),
     "observables": ("FIX-window volume", "TIIE versus Fondeo spread"),
     "impact": "the TIIE-to-Fondeo transition is a dated structural break in every Mexican carry "
               "series, and splicing the two into one series creates a level shift that reads "
               "like a policy move",
     "persistence": "the transition is once; the FIX role is permanent",
     "falsifier": "no discontinuity in measured carry or basis around the transition dates",
     "notes": "a measurement break disguised as a market move -- the class of error this desk "
              "has paid for before"},
)

# --------------------------------------------------------------------------- domains
_CONTROLS = ("a matched non-event day of the same weekday and month",
             "the global dollar factor (USDX) and US500 on the same session",
             "MXNJPY as the carry-stripped view of the same move")

DOMAINS: tuple[dict[str, Any], ...] = (
    {"id": "MX-A", "title": "Banxico surprise against the Citibanamex consensus",
     "objects": ("the decision against the published survey median",
                 "the 19:00 UTC announcement", "the minuta and its vote split"),
     "conditions": ("the announcement minute is FIXED in UTC since 2022-10 and was not before",
                    "the vote split is published, so dissent is a dated variable"),
     "instruments": ("USDMXN", "MXNJPY", "UST10Y", "US500"),
     "controls": (*_CONTROLS, "FOMC dates in the same weeks as the competing event"),
     "notes": "Banxico decisions frequently land in the same week as the Fed, and the Mexican "
              "effect cannot be identified without conditioning on that"},
    {"id": "MX-B", "title": "The peso as the world's EM hedge proxy",
     "objects": ("USDMXN sensitivity to global risk relative to peer EM currencies",
                 "the overnight share of the daily range", "CFTC positioning extremes"),
     "conditions": ("the global factor is LARGER than the Mexican one in this series, which "
                    "inverts the usual identification problem",),
     "instruments": ("USDMXN", "USDBRL", "USDZAR", "USDTRY", "MXNJPY", "US500"),
     "controls": (*_CONTROLS, "peer EM currencies with the same carry and less liquidity"),
     "notes": "the pack's central object and its central warning"},
    {"id": "MX-C", "title": "The FIX window and its one-day application lag",
     "objects": ("the midday determination window", "the next-day application",
                 "corporate hedge flow into it"),
     "conditions": ("the window is at a FIXED UTC minute all year since 2022-10",
                    "the published FIX applies the FOLLOWING business day"),
     "instruments": ("USDMXN",),
     "controls": (*_CONTROLS, "matched midday windows on days with no settlement obligation"),
     "notes": "measurable on this box today with nothing but bars and a clock"},
    {"id": "MX-D", "title": "Remittances as a counter-cyclical dollar inflow",
     "objects": ("the monthly remesas print and its surprise",
                 "the May and December seasonal", "US employment as the driver"),
     "conditions": ("the flow responds to US EMPLOYMENT, not to Mexican competitiveness",
                    "a weaker peso RAISES the peso value of a fixed dollar transfer"),
     "instruments": ("USDMXN", "US500"),
     "controls": (*_CONTROLS, "US payroll surprises in the same month"),
     "notes": "the only dollar inflow in this command with a counter-cyclical sign"},
    {"id": "MX-E", "title": "Nearshoring as a counted quantity",
     "objects": ("BTS truck crossings", "manufacturing exports", "FDI announcements"),
     "conditions": ("the narrative is everywhere and the QUANTITY is the test",
                    "crossings are published with a two-month lag, so this is a slow sensor"),
     "instruments": ("USDMXN", "US2000", "US500"),
     "controls": (*_CONTROLS, "US industrial production as the demand-side explanation"),
     "notes": "a nearshoring cell that does not use the crossing count is testing a story"},
    {"id": "MX-F", "title": "The USMCA review as a dated, pre-positionable risk",
     "objects": ("the 2026 joint review date", "implied-vol term structure around it",
                 "tariff headlines as the unscheduled comparison"),
     "conditions": ("a SCHEDULED risk can be pre-positioned for and an unscheduled one cannot, "
                    "so the two have different pre-drift and different impact profiles",),
     "instruments": ("USDMXN", "MXNJPY", "US2000"),
     "controls": (*_CONTROLS, "unscheduled trade headlines of comparable magnitude"),
     "notes": "the scheduled-versus-unscheduled pair, with Argentina supplying the other extreme"},
    {"id": "MX-G", "title": "The carry trade and the foreign Bonos M unwind",
     "objects": ("the weekly foreign-holdings series", "the carry-to-vol ratio",
                 "the multi-year unwind"),
     "conditions": ("a local-currency position is two risks that can be hedged separately, so "
                    "the holdings series and the FX flow are not the same object",),
     "instruments": ("USDMXN", "MXNJPY", "UST10Y", "AUDJPY"),
     "controls": (*_CONTROLS, "Brazilian carry with no comparable published holdings series"),
     "notes": "a rare case of a large flow published WEEKLY instead of quarterly"},
    {"id": "MX-H", "title": "Pemex, the Maya decline and the sovereign hedge",
     "objects": ("CNH monthly production by field", "the annual hedge execution window",
                 "crude put skew in that window"),
     "conditions": ("the hedge is a budget requirement rather than a view, so it is one-directional"
                    " and recurring",),
     "instruments": ("XTIUSD", "XBRUSD", "USDMXN"),
     "controls": (*_CONTROLS, "crude skew in the same months of years with a smaller programme"),
     "notes": "the largest single options trade in the world leaves a seasonal footprint or it "
              "does not, and that is testable"},
    {"id": "MX-I", "title": "Silver's by-product supply",
     "objects": ("Mexican silver output", "the base-metals cycle",
                 "the silver-gold and silver-copper ratios"),
     "conditions": ("silver is mostly a BY-PRODUCT, so its supply responds to copper, lead and "
                    "zinc economics rather than to its own price",),
     "instruments": ("XAGUSD", "XAUUSD", "XCUUSD", "XZNUSD"),
     "controls": (*_CONTROLS, "gold, whose supply is primary and price-responsive"),
     "notes": "explains silver's asymmetric supply response, which every silver cell inherits"},
    {"id": "MX-J", "title": "The bank calendar versus the labour calendar",
     "objects": ("the three CNBV-only closures", "the sexenal 1 October",
                 "US holidays with an open Mexican market"),
     "conditions": ("the FX market follows the BANK calendar",
                    "a US holiday with Mexico open is a thin-liquidity day, not a closure"),
     "instruments": ("USDMXN",),
     "controls": (*_CONTROLS, "matched full-liquidity sessions of the same weekday"),
     "notes": "the calendar domain that catches the phantom sessions"},
    {"id": "MX-K", "title": "The TIIE-to-Fondeo transition as a measurement break",
     "objects": ("TIIE 28 and TIIE de Fondeo across the transition",
                 "the implied carry from each"),
     "conditions": ("splicing the two creates a level shift that reads like a policy move",),
     "instruments": ("USDMXN", "MXNJPY"),
     "controls": (*_CONTROLS, "the policy target rate, which did not change at the transition"),
     "notes": "a measurement break disguised as a market move"},
    {"id": "MX-L", "title": "Retail dollarisation at fintech speed",
     "objects": ("bank and fintech dollar-deposit series", "narrative volume",
                 "the response speed before and after the app expansion"),
     "conditions": ("the switch now costs nothing and takes seconds, which is new and dated",),
     "instruments": ("USDMXN",),
     "controls": (*_CONTROLS, "the same narrative shocks before the fintech expansion"),
     "notes": "the app-ecosystem layer's own domain"},
)

# --------------------------------------------------------------------------- miners
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    {"name": "mx_fix_window", "domain_ids": ("MX-C",), "kind": "calendar",
     "entry": "research.countries.mx.pack:fix_window_utc", "cadence_s": 3600.0,
     "steerable": False,
     "notes": "the midday FIX determination window, fixed in UTC since 2022-10"},
    {"name": "mx_bank_calendar", "domain_ids": ("MX-J",), "kind": "calendar",
     "entry": "research.countries.mx.pack:is_closed", "cadence_s": 86400.0, "steerable": False,
     "notes": "the CNBV bank calendar, which is what the FX market follows"},
    {"name": "mx_proxy_beta", "domain_ids": ("MX-B", "MX-G"), "kind": "mechanism",
     "entry": "research.countries.mx.pack:proxy_control_set", "cadence_s": 21600.0,
     "steerable": True,
     "notes": "the peer set a Mexican claim must survive against before it is Mexican"},
)

#: The FIX determination window in UTC. Fixed year-round since the 2022 DST abolition; a pre-2022
#: sample shifts by an hour in the northern summer and must use the historical rule.
FIX_WINDOW_UTC: tuple[str, str] = ("17:45", "18:15")


def fix_window_utc() -> tuple[str, str]:
    """The FIX determination window in UTC, as (start, end)."""
    return FIX_WINDOW_UTC


def proxy_control_set() -> tuple[str, ...]:
    """The peers a Mexican claim must survive against before it may be called Mexican.

    MXNJPY strips the dollar; USDBRL and USDZAR are EM currencies with comparable carry and less
    liquidity, so a move present in all three is the global factor rather than Mexico.
    """
    return ("MXNJPY", "USDBRL", "USDZAR", "USDTRY", "USDX", "US500")


# --------------------------------------------------------------------------- the two vocabularies
def _lag_days(text: str) -> float:
    """The first whole number in a lag phrase. An unparseable lag is 0.0 and NOT one day."""
    digits = ""
    for ch in str(text or ""):
        if ch.isdigit():
            digits += ch
        elif digits:
            break
    return float(digits) if digits else 0.0


def _dual(rows: tuple[dict[str, Any], ...]) -> tuple[dict[str, Any], ...]:
    """Every seed in both vocabularies, DERIVED keys first so the framework's own aliases (which
    would put the string "1-10 sessions" into a float field) cannot win."""
    out: list[dict[str, Any]] = []
    for row in rows:
        targets = tuple(row.get("targets") or ())
        derived = {"to_country": str(row.get("to_country") or "global"),
                   "asset": targets[0] if targets else "",
                   "lag_days": _lag_days(row.get("lag", ""))}
        out.append({**derived, **row})
    return tuple(out)


def _named_eras(rows: tuple[dict[str, Any], ...]) -> tuple[dict[str, Any], ...]:
    """Policy eras with the readable LABEL as the framework's `name`, written first."""
    return tuple({"name": str(r.get("label") or r.get("id") or ""), **r} for r in rows)


# --------------------------------------------------------------------------- transmission
_EDGE_ROWS: tuple[dict[str, Any], ...] = (
    {"id": "mx_proxy_to_em_risk",
     "source": "global risk appetite and the peso's role as its EM expression",
     "mechanism": "when a fund cannot sell the asset it wants to hedge it sells the peso, so "
                  "USDMXN moves FIRST and by more than peers on a global risk turn",
     "targets": ("USDMXN", "USDBRL", "USDZAR", "US500"), "sign": "same",
     "horizon": "1-10 sessions", "lag": "0-1 sessions",
     "control": "MXNJPY to strip the dollar; peer EM currencies with the same carry",
     "evidence": "HYPOTHESIS",
     "notes": "if this is real, Mexico is a SENSOR for global risk rather than a bet on Mexico"},
    {"id": "mx_banxico_to_carry",
     "source": "the Banxico target against the Citibanamex consensus",
     "mechanism": "a policy surprise moves the carry differential, which is the whole thesis of "
                  "the largest foreign position in the local bond market",
     "targets": ("USDMXN", "MXNJPY", "UST10Y"), "sign": "opposite",
     "horizon": "1-20 sessions", "lag": "0-3 sessions",
     "control": "FOMC decisions in the same week; EURUSD as the zero-Mexico comparison",
     "evidence": "HYPOTHESIS",
     "notes": "the Fed's calendar is the confound and must be conditioned on, not averaged over"},
    {"id": "mx_remesas_to_peso",
     "source": "the monthly remittance print and its surprise",
     "mechanism": "sixty billion dollars a year arriving on a US-employment clock, partly "
                  "counter-cyclical to the peso because a fixed peso need buys more dollars",
     "targets": ("USDMXN",), "sign": "opposite",
     "horizon": "5-30 sessions", "lag": "1-10 sessions",
     "control": "US payroll surprises in the same month",
     "evidence": "HYPOTHESIS",
     "notes": "the counter-cyclical sign is what makes this distinguishable from the US cycle"},
    {"id": "mx_nearshoring_to_us_smallcap",
     "source": "border truck crossings and manufacturing exports",
     "mechanism": "a relocating supply chain is a US industrial-capex story as much as a Mexican "
                  "one; the small-cap industrial complex is where it should show first",
     "targets": ("US2000", "USDMXN", "US500"), "sign": "same",
     "horizon": "20-120 sessions", "lag": "10-60 sessions",
     "control": "US industrial production as the demand-side explanation",
     "evidence": "HYPOTHESIS",
     "notes": "a slow sensor with a two-month publication lag; never a daily-horizon cell"},
    {"id": "mx_usmca_review_to_vol",
     "source": "the scheduled 2026 USMCA joint review",
     "mechanism": "a DATED policy risk should appear in the implied-vol term structure before it "
                  "appears in spot, because a date can be pre-positioned for",
     "targets": ("USDMXN", "MXNJPY", "US2000"), "sign": "same",
     "horizon": "20-120 sessions", "lag": "0-20 sessions",
     "control": "unscheduled tariff headlines of comparable magnitude",
     "evidence": "HYPOTHESIS",
     "notes": "the vol term structure is the cleanest available test of whether a DATE is priced"},
    {"id": "mx_pemex_hedge_to_crude_skew",
     "source": "the annual sovereign oil hedge execution window",
     "mechanism": "the world's largest single oil-put purchase is one-directional and recurring; "
                  "a buyer that size leaves a seasonal footprint in the surface or does not exist",
     "targets": ("XTIUSD", "XBRUSD"), "sign": "same",
     "horizon": "20-90 sessions", "lag": "0-30 sessions",
     "control": "the same months in years with a materially smaller programme",
     "evidence": "HYPOTHESIS",
     "notes": "the skew is not on this box; the flat-price leg is the testable half today"},
    {"id": "mx_silver_byproduct_to_metals",
     "source": "Mexican silver output and the base-metals cycle",
     "mechanism": "silver's supply is a by-product of base-metals mining, so it is inelastic to "
                  "its own price and elastic to copper and zinc",
     "targets": ("XAGUSD", "XCUUSD", "XZNUSD", "XAUUSD"), "sign": "same",
     "horizon": "20-120 sessions", "lag": "5-30 sessions",
     "control": "gold, whose supply is primary and price-responsive",
     "evidence": "HYPOTHESIS",
     "notes": "the mechanism behind silver's asymmetric supply curve, and Mexico is the largest "
              "single source of it"},
    {"id": "mx_grain_import_to_cpi_and_peso",
     "source": "imported maize and wheat prices",
     "mechanism": "Mexico's food basket is import-dependent, so a grain shock is a Mexican "
                  "inflation shock with a currency multiplier and feeds the Banxico reaction",
     "targets": ("CORN", "WHEAT", "USDMXN"), "sign": "same",
     "horizon": "20-120 sessions", "lag": "10-60 sessions",
     "control": "the same grain shocks in an economy with domestic grain self-sufficiency",
     "evidence": "HYPOTHESIS",
     "notes": "the link from the softs book to a central-bank reaction function"},
    {"id": "mx_fix_window_to_usdmxn",
     "source": "the midday FIX determination window",
     "mechanism": "corporate hedges settle against the FIX, so the determination window carries a "
                  "dated, mechanical flow at a FIXED UTC minute all year",
     "targets": ("USDMXN",), "sign": "same",
     "horizon": "intraday", "lag": "0",
     "control": "matched midday windows on days with no settlement obligation",
     "evidence": "HYPOTHESIS",
     "notes": "the only edge here that needs no external data at all"},
    {"id": "mx_foreign_bonos_to_peso",
     "source": "the weekly foreign-holdings series for Bonos M and Cetes",
     "mechanism": "a multi-year real-money unwind is a slow, measured, published FX flow and the "
                  "series is weekly rather than quarterly",
     "targets": ("USDMXN", "MXNJPY", "UST10Y"), "sign": "same",
     "horizon": "20-250 sessions", "lag": "5-30 sessions",
     "control": "the carry differential and global risk over the same window",
     "evidence": "HYPOTHESIS",
     "notes": "a rare case where the flow itself, not a proxy for it, is published"},
)

TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = _dual(_EDGE_ROWS)


# --------------------------------------------------------------------------- eras
_ERA_ROWS: tuple[dict[str, Any], ...] = (
    {"id": "mx_fix_methodology", "start": "2016-01-01", "end": None,
     "label": "The FIX methodology and the Comision de Cambios NDF programme",
     "what_changed": "intervention moved decisively to peso-settled forwards announced in advance",
     "invalidates": "intervention-response estimates from the spot-auction era do not transfer: "
                    "the instrument and its reserve consequence are both different"},
    {"id": "mx_tiie_transition", "start": "2020-01-01", "end": None,
     "label": "TIIE de Fondeo replaces the survey-based TIIE 28 as the reference",
     "what_changed": "the reference rate became a TRANSACTION rate rather than a survey",
     "invalidates": "a carry series spliced across this transition carries a level shift that "
                    "reads like a policy move and is a measurement change"},
    {"id": "mx_no_dst", "start": "2022-10-30", "end": None,
     "label": "Mexico abolishes daylight saving (Ley de Husos Horarios)",
     "what_changed": "America/Mexico_City became UTC-6 all year, so every Mexican event sits at a "
                     "fixed UTC minute",
     "invalidates": "ANY intraday Mexican study pooled across this date misaligns every pre-2022 "
                    "northern-summer session by an hour, and the FIX window is the exact object "
                    "that misaligns"},
    {"id": "mx_superpeso", "start": "2022-06-01", "end": "2024-04-30",
     "label": "The 'superpeso': a multi-year real appreciation on carry and nearshoring",
     "what_changed": "the highest real carry in EM combined with a structural dollar inflow "
                     "produced an appreciation trend that reversed violently",
     "invalidates": "an unconditional USDMXN drift or carry estimate that includes this window "
                    "without conditioning on it is fitting a regime, not a mechanism"},
    {"id": "mx_carry_unwind_2024", "start": "2024-07-01", "end": "2024-12-31",
     "label": "The 2024 carry unwind and the election-plus-yen shock",
     "what_changed": "a domestic political shock coincided with a global yen-funded carry unwind, "
                     "and the peso fell more than any EM peer",
     "invalidates": "attributing that move to Mexican politics alone is the identification error "
                    "this pack's MXNJPY control exists to prevent"},
    {"id": "mx_judicial_reform", "start": "2024-09-15", "end": None,
     "label": "The judicial reform and the institutional-risk repricing",
     "what_changed": "a constitutional change to judicial selection produced a persistent "
                     "institutional risk premium distinct from the cyclical one",
     "invalidates": "a Mexican risk-premium estimate fitted before this date understates the "
                    "level and mis-attributes the change to the cycle"},
    {"id": "mx_usmca_review", "start": "2026-01-01", "end": None,
     "label": "The USMCA joint-review year",
     "what_changed": "a treaty-set review date makes trade risk SCHEDULED for the first time in "
                     "the sample",
     "invalidates": "pre-2026 trade-risk estimates are all estimates of UNSCHEDULED risk and do "
                    "not describe how a dated review prices"},
)

POLICY_ERAS: tuple[dict[str, Any], ...] = _named_eras(_ERA_ROWS)


# --------------------------------------------------------------------------- access constraints
ACCESS_CONSTRAINTS: tuple[dict[str, Any], ...] = (
    {"constraint": "Banxico's SIE API needs a free registered token",
     "measured": "the API requires a Bmx-Token header",
     "consequence": "without `banxico_token` in data/secrets/latam_apis.json every Banxico series "
                    "is UNMEASURED BY NAME. The Brazilian and Andean lanes already report that "
                    "provider's status, so the silence has a named cause"},
    {"constraint": "no Mexican rates or index instrument is quoted on this broker",
     "measured": "universe.json holds four MXN pairs and no Mexican index or bond",
     "consequence": "every rates and equity mechanism routes through USDMXN with the local term "
                    "premium declared UNMEASURED; US2000 carries the small-cap industrial leg"},
    {"constraint": "USDMXN option surfaces and the crude skew are not on this box",
     "measured": "the desk holds bars, not surfaces",
     "consequence": "MX-F and MX-H's cleanest tests -- the implied-vol term structure around the "
                    "USMCA review and the put skew in the Pemex hedge window -- are "
                    "BLOCKED_ON_DATA and counted as blocked rather than reported as nulls"},
)

# --------------------------------------------------------------------------- layer coverage
def source_layer_coverage() -> dict[str, Any]:
    """Sources per layer, with every empty layer named. Blank is never an answer (L1.28a)."""
    by_layer: dict[str, list[str]] = {layer: [] for layer in SOURCE_LAYERS}
    unknown: list[str] = []
    for row in SOURCE_CLASSES:
        layer = str(row.get("layer") or "")
        if layer in by_layer:
            by_layer[layer].append(str(row["id"]))
        else:
            unknown.append(f"{row.get('id')}:{layer!r}")
    missing = {layer: LAYER_ABSENCES.get(layer, "")
               for layer, ids in by_layer.items() if not ids}
    return {"code": CODE,
            "layers": {k: {"n": len(v), "sources": v} for k, v in by_layer.items()},
            "n_layers_covered": sum(1 for v in by_layer.values() if v),
            "missing": missing,
            "unexplained_missing": sorted(k for k, why in missing.items() if not why.strip()),
            "unknown_layer_tags": unknown,
            "machine_use_forbidden": [str(r["id"]) for r in SOURCE_CLASSES
                                      if not r.get("machine_use_allowed", True)],
            "rule": "ten layers, each carrying a source or named ABSENT with a reason; a page "
                    "whose terms forbid machine extraction is registered "
                    "machine_use_allowed=false, never scraped and never omitted"}


# --------------------------------------------------------------------------- assembly
_PACK_FIELDS: tuple[str, ...] = (
    "code", "name", "region_command", "currency", "executable_instruments", "central_bank",
    "fixing_conventions", "settlement_conventions", "exchanges", "holidays_rule",
    "fiscal_year_end", "positioning_sources", "native_languages", "terminology", "source_classes",
    "datasets", "actors", "domains", "custom_miners", "transmission_edges_seed", "policy_eras")

MISSION = ("mine Mexico as the LIQUID end of this command: the world's EM hedge proxy, the only "
           "Latin American currency in the desk's COT axis, a sixty-billion-dollar "
           "counter-cyclical remittance inflow, the largest sovereign oil hedge on earth, and a "
           "treaty-set 2026 review date -- and use the peso as a SENSOR for global risk while "
           "insisting that every Mexican claim survive MXNJPY before it is called Mexican")


def as_dict() -> dict[str, Any]:
    """The pack as a plain mapping, extras carried alongside the twenty-one frozen fields."""
    return {
        "code": CODE, "name": NAME, "region_command": REGION_COMMAND, "currency": CURRENCY,
        "executable_instruments": EXECUTABLE_INSTRUMENTS, "central_bank": CENTRAL_BANK,
        "fixing_conventions": FIXING_CONVENTIONS,
        "settlement_conventions": SETTLEMENT_CONVENTIONS, "exchanges": EXCHANGES,
        "holidays_rule": HOLIDAYS_RULE, "fiscal_year_end": FISCAL_YEAR_END,
        "positioning_sources": POSITIONING_SOURCES, "native_languages": NATIVE_LANGUAGES,
        "terminology": TERMINOLOGY, "source_classes": SOURCE_CLASSES, "datasets": DATASETS,
        "actors": ACTORS, "domains": DOMAINS, "custom_miners": CUSTOM_MINERS,
        "transmission_edges_seed": TRANSMISSION_EDGES_SEED, "policy_eras": POLICY_ERAS,
        "transmission_targets": TRANSMISSION_TARGETS, "access_constraints": ACCESS_CONSTRAINTS,
        "region_desk": REGION_DESK, "cot_currency": COT_CURRENCY, "cot_status": COT_STATUS,
        "own_price": OWN_PRICE, "mission": MISSION,
    }


def _ensure_root_on_path() -> None:
    root = str(Path(__file__).resolve().parents[5])
    if root not in sys.path:
        sys.path.insert(0, root)


def pack() -> Any:
    """`libs.research.country_lab.CountryPack` when that module has landed, else this mapping."""
    data = as_dict()
    _ensure_root_on_path()
    try:
        from libs.research import country_lab
    except Exception:
        return data
    cls = getattr(country_lab, "CountryPack", None)
    if cls is None:
        return data
    try:
        return cls(**{k: v for k, v in data.items() if k in _PACK_FIELDS})
    except (TypeError, ValueError):
        return data


PACK = pack()
