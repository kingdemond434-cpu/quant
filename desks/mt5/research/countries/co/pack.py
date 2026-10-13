"""COLOMBIA: a farm-gate price that is a published formula in the exchange rate, and a pipeline.

THREE MECHANISMS, AND THE FIRST ONE IS NOT AVAILABLE ANYWHERE ELSE IN THIS COMMAND:

  1. THE COFFEE FORMULA MAKES THE EXCHANGE RATE AN ARITHMETIC TERM IN A PRODUCER'S PRICE. The
     Federacion Nacional de Cafeteros publishes a DAILY precio interno de referencia computed
     openly from the ICE 'C' contract, the Colombian mild quality differential and the TRM. Every
     other terms-of-trade channel in this desk's book has to be ESTIMATED from prices and
     volumes; this one is published as an equation. That makes Colombia the natural place to ask
     whether a currency move reaches a producer through PRICE or through QUANTITY, because the
     price leg is mechanical and known and only the quantity leg is in question.

  2. FX INTERVENTION IS A RULE WITH A PUBLISHED TRIGGER. BanRep's volatility-control mechanism
     auctions options when the rate deviates from its own 20-day moving average by a stated
     percentage. That is a DISCONTINUITY DESIGN with a public threshold -- the same shape as
     Chile's fiscal reference price and rarer than either. Most central banks intervene at
     discretion; this one publishes the trigger.

  3. SUPPLY INTERRUPTION IS A COUNTED EVENT CLASS. The Cano Limon-Covenas pipeline is attacked
     repeatedly, and the interruptions are recorded with dates and durations. An oil supply
     disruption that is dated, counted and repeated is a far better event class than a single
     famous outage, because it has an n.

WHAT IS EXECUTABLE: NOTHING COLOMBIAN. `OWN_PRICE` is empty -- USDCOP, the COLCAP and the TES
curve are all absent from this broker's registry. Every mechanism here is carried by crude,
arabica and the EM peer currencies, and each substitution is named with the basis it costs.

THE TWO-LANE ORDER. Ecopetrol, Bancolombia, Grupo Sura and Cerrejon are what Colombian research
is about; none is in this broker's registry and none may mint a statistical hypothesis. They are
ACTORS here whose forced flows move crude, coffee and the peer currencies.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------- identity
CODE = "co"
NAME = "Colombia"
REGION_COMMAND = "latam"
REGION_DESK = "SOUTH_AMERICA"
CURRENCY = "COP"
NATIVE_LANGUAGES: tuple[str, ...] = ("es-CO",)
FISCAL_YEAR_END = "12-31"

#: EMPTY. USDCOP is not quoted here, so this pack is TRANSMISSION-ONLY and says so first.
OWN_PRICE: tuple[str, ...] = ()

EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "XBRUSD", "XTIUSD", "XNGUSD",               # crude is about a third of exports; Brent is the
                                                # right reference for Colombian grades
    "COFARA", "COFROB",                         # Colombian mild is an arabica; robusta is the
                                                # control for a Colombia-specific claim
    "USDBRL", "USDMXN", "USDZAR", "USDTRY",     # the EM peers a COP-less claim must run in
    "XAUUSD", "XAGUSD",                         # informal gold mining is a real export and a real
                                                # capital-flight channel
    "XCUUSD",                                   # the base-metals control for a commodity claim
    "SUGAR", "USCOCOA", "CORN",                 # the rest of the agricultural complex
    "US500", "US2000", "USDX", "UST10Y",        # the global risk, dollar and duration factors
    "EURUSD", "AUDUSD",                         # the dollar-factor and commodity-FX controls
)

COT_CURRENCY = ""
COT_STATUS = ("There is no COP contract in the desk's cot.json axis and no liquid CME peso "
              "future. The positioning that matters here is in the COMMODITIES Colombia sells: "
              "the axis maps XTIUSD and XAUUSD, and a Colombian supply claim is read in those "
              "nets rather than in a currency this desk cannot see.")

TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "USD/COP spot and the TRM", "venue": "interbank / Superfinanciera",
     "why": "the peso is one of the highest-beta oil currencies in EM and is the natural "
            "expression of every domestic mechanism here",
     "proxies": ("XBRUSD", "USDBRL", "USDMXN", "USDX"),
     "basis_cost": "USDBRL carries a fiscal term COP does not and USDMXN carries a US-cycle term; "
                   "neither substitution is clean and both are declared"},
    {"name": "COLCAP index and the Colombian equity market", "venue": "BVC",
     "why": "the domestic risk asset; heavily financial and energy weighted",
     "proxies": ("US2000", "XBRUSD"),
     "basis_cost": "the index is dominated by a few names with oil and credit exposure, so the "
                   "crude leg carries more of it than a broad-market proxy would"},
    {"name": "TES peso curve and the local real rate", "venue": "BanRep / BVC",
     "why": "the rates expression; BanRep's surprise prices here first",
     "proxies": ("UST10Y", "USDBRL"),
     "basis_cost": "UST10Y carries no Colombian term premium at all; the local one is UNMEASURED"},
    {"name": "ICE Coffee 'C' and the Colombian mild differential", "venue": "ICE / physical",
     "why": "COFARA is the flat arabica price; the Colombian MILD differential is a separate, "
            "published quality premium and it is the Colombia-specific half",
     "proxies": ("COFARA", "COFROB"),
     "basis_cost": "the flat price is global and the differential is Colombian; a claim tested on "
                   "the flat price alone is testing Brazil's weather more than Colombia's"},
    {"name": "FNC precio interno de referencia (daily farm-gate reference)", "venue": "FNC",
     "why": "THE PUBLISHED FORMULA: ICE 'C' plus the mild differential, converted at the TRM. The "
            "exchange rate is an arithmetic term in a producer's price, in public.",
     "proxies": ("COFARA",),
     "basis_cost": "none; data rather than an instrument, and it is the pack's best mechanism"},
    {"name": "Cerrejon and Drummond thermal coal exports", "venue": "physical / API2",
     "why": "Colombia is a top-five thermal coal exporter and the European demand shift of 2022 "
            "was a step change in its export receipts",
     "proxies": ("XNGUSD", "XTIUSD", "XBRUSD"),
     "basis_cost": "no coal instrument is quoted here; gas carries the European power-fuel "
                   "substitution and the substitution is declared, not assumed away"},
)

# --------------------------------------------------------------------------- central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "Banco de la Republica",
    "short": "BanRep",
    "framework": "inflation_targeter",
    "committee": "Junta Directiva -- seven members INCLUDING THE FINANCE MINISTER, who chairs. "
                 "That composition is itself a mechanism: the fiscal authority sits on the "
                 "monetary board, so a fiscal-monetary conflict is INTERNAL to the committee and "
                 "shows up as a split vote rather than as a public dispute.",
    "policy_rate": "tasa de intervencion de politica monetaria (the overnight expansion rate)",
    "meetings_per_year": 8,
    "schedule_rule": (
        "EIGHT monetary-policy meetings a year on a calendar published in advance, usually on the "
        "LAST FRIDAY of the meeting month. The decision and the vote split are announced the same "
        "afternoon with a press conference; the minutes follow about a week later."),
    "announce_local": "about 14:00 America/Bogota", "announce_utc": "19:00",
    "announce_utc_dst": "19:00",
    "dst_rule": "COLOMBIA HAS NO DST. America/Bogota is UTC-5 all year, so every Colombian time "
                "in this pack is fixed while the broker's own clock still shifts twice a year.",
    "minutes_rule": "minutes about a week after the decision; the VOTE SPLIT is published on the "
                    "day, which makes dissent a same-session variable rather than a later one",
    "inflation_target": "3% with a +/-1pp range",
    "fx_operations": (
        "A RULE WITH A PUBLISHED TRIGGER. BanRep's volatility-control mechanism auctions put or "
        "call options when the exchange rate deviates from its own 20-day moving average by a "
        "stated percentage, and it runs reserve-accumulation auctions when conditions allow. "
        "Most central banks intervene at discretion; publishing the trigger turns intervention "
        "into a DISCONTINUITY DESIGN with a public threshold -- the same rare shape as Chile's "
        "fiscal reference price."),
    "policy_rate_series": "BanRep series -- tasa de politica monetaria",
    "expected_rate_series": "BanRep Encuesta mensual de expectativas de analistas economicos, and "
                            "the Citi/Fedesarrollo surveys; the BanRep survey is the one the "
                            "board itself cites",
    "decision_dates": {
        2024: ("2024-01-31", "2024-03-22", "2024-04-30", "2024-06-28", "2024-07-31",
               "2024-09-30", "2024-10-31", "2024-12-20"),
        2025: ("2025-01-31", "2025-03-31", "2025-04-30", "2025-06-30", "2025-07-31",
               "2025-09-30", "2025-10-31", "2025-12-19"),
        2026: ("2026-01-30", "2026-03-31", "2026-04-30", "2026-06-30", "2026-07-31",
               "2026-09-30", "2026-10-30", "2026-12-18"),
    },
    "decision_dates_status": ("DERIVED from BanRep's last-Friday/month-end cadence for all three "
                              "years and NOT copied from the published calendars. Treat every "
                              "date here as provisional: an event study run on a derived "
                              "calendar reports a null about the dating, not about the "
                              "mechanism, and the published calendar must replace this before "
                              "any verdict is read as confirmatory."),
    "root": "https://www.banrep.gov.co",
}

# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "TRM (Tasa Representativa del Mercado)",
     "publisher": "Superintendencia Financiera de Colombia",
     "definition": "the weighted average of the PREVIOUS business day's interbank and wholesale "
                   "spot transactions, certified by the Superfinanciera and VALID for the "
                   "following business day",
     "windows_local": ("previous session",), "windows_utc": ("13:00-19:00",),
     "published_local": "evening, for use the next business day",
     "published_utc": "23:00", "published_utc_dst": "23:00",
     "dst_rule": "none -- Colombia is UTC-5 year round",
     "instruments": (),
     "why_it_matters": "A TWO-DAY CHAIN: transactions on day D produce a rate published that "
                       "evening and APPLIED on day D+1. Every contract, tariff, tax and -- "
                       "critically -- the coffee farm-gate formula settles on it, so a two-day-old "
                       "market is embedded in today's producer economics by law.",
     "trap": "aligning the TRM with the same day's market rate is off by two business days, not "
             "one; the Chilean dolar observado is off by one, and the two conventions are "
             "routinely confused with each other"},
    {"name": "FNC precio interno de referencia (coffee farm-gate reference)",
     "publisher": "Federacion Nacional de Cafeteros",
     "definition": "a DAILY published price per 125kg load, computed from the ICE 'C' second "
                   "position, the Colombian mild differential and the TRM",
     "windows_local": ("morning",), "windows_utc": ("13:00",),
     "published_local": "each business morning", "published_utc": "13:00",
     "dst_rule": "none",
     "instruments": ("COFARA",),
     "why_it_matters": "THE PACK'S BEST MECHANISM. The exchange rate is an ARITHMETIC TERM in a "
                       "producer's price and the formula is public, so the price leg of the "
                       "terms-of-trade channel is mechanical and only the QUANTITY leg is in "
                       "question -- which is exactly the decomposition every other country in "
                       "this command has to estimate.",
     "trap": "the formula uses the TRM, which is two days old, so a same-day FX move reaches the "
             "farmer with a two-day lag BY CONSTRUCTION and any faster response is somebody "
             "anticipating the formula rather than the formula working"},
    {"name": "IBR (Indicador Bancario de Referencia)",
     "publisher": "Banco de la Republica / Asobancaria",
     "definition": "the overnight and term interbank reference computed from quotes of a panel "
                   "of banks",
     "windows_local": ("morning",), "windows_utc": ("13:00",),
     "published_local": "each business day", "published_utc": "13:00", "dst_rule": "none",
     "instruments": (),
     "why_it_matters": "the local funding reference behind every Colombian carry calculation",
     "trap": "IBR is a QUOTE-based reference on a small panel; it is not a transaction rate and "
             "it is not comparable to Mexico's TIIE de Fondeo without saying so"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "FX spot", "kind": "weekday",
     "rule": "USD/COP settles T+2 onshore; the market is deliverable and onshore, and the "
             "offshore NDF book is small relative to Brazil's or Chile's",
     "window_utc": ("13:00", "19:00"), "instruments": ()},
    {"name": "Coffee harvest and internal purchase", "kind": "month_end",
     "rule": "the main crop (cosecha principal) runs roughly October to December with a mitaca "
             "in April-June; FNC cooperatives buy at the published reference, so the export "
             "receipt and the farm-gate payment are separated by the formula rather than by a "
             "negotiation",
     "months": (4, 5, 6, 10, 11, 12), "roll": "previous",
     "window_utc": ("13:00", "19:00"), "instruments": ("COFARA",)},
    {"name": "Ecopetrol dividend and the fiscal transfer", "kind": "quarter_end",
     "rule": "the state is the majority holder, so the dividend is a FISCAL item; a large "
             "dividend year and a large oil year are the same year, which makes Colombian "
             "fiscal risk pro-cyclical with crude",
     "months": (3, 6, 9, 12), "roll": "previous",
     "window_utc": ("13:00", "19:00"), "instruments": ("XBRUSD", "XTIUSD")},
    {"name": "BanRep option auction trigger", "kind": "weekday",
     "rule": "the volatility-control mechanism auctions options when the rate deviates from its "
             "own 20-day moving average by a published percentage -- a THRESHOLD, not a calendar",
     "weekday": -1, "roll": "none",
     "window_utc": ("13:00", "19:00"), "instruments": ()},
    {"name": "Remittance arrival", "kind": "month_end",
     "rule": "roughly ten billion dollars a year, concentrated around US and Spanish pay periods "
             "and at year end; the December peak is the largest",
     "months": (12,), "roll": "previous",
     "window_utc": ("13:00", "19:00"), "instruments": ()},
)

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Bolsa de Valores de Colombia (BVC)", "index_symbols": (),
     "index_symbols_absent": ("COLCAP",),
     "hours_local": "09:30-15:55 Bogota with a closing auction",
     "hours_utc": "14:30-20:55",
     "expiry_rule": "the listed derivative market is thin; TES and USD futures exist but the "
                    "open interest is small enough that no expiry mechanism is claimed here -- "
                    "which is itself the finding",
     "notes": "the BVC is merging its operations with the Chilean and Peruvian exchanges into a "
              "regional market, which is a dated structural change to Andean equity liquidity"},
    {"name": "ICE Futures US (Coffee 'C')", "index_symbols": (),
     "index_symbols_absent": ("KC",),
     "hours_local": "04:15-13:30 New York", "hours_utc": "08:15-17:30",
     "expiry_rule": "the 'C' contract's notice and expiry cycle governs the FNC reference's "
                    "second-position input, so the ROLL changes the farm-gate formula's input "
                    "even when no price moves",
     "notes": "the roll effect on the published formula is a mechanical, dated artefact and is "
              "the sort of thing that looks like a signal and is not"},
)

# --------------------------------------------------------------------------- holidays
_CO_HOLIDAYS: dict[int, dict[str, str]] = {
    2024: {
        "2024-01-01": "Ano Nuevo", "2024-01-08": "Reyes Magos (Emiliani)",
        "2024-03-25": "San Jose (Emiliani)", "2024-03-28": "Jueves Santo",
        "2024-03-29": "Viernes Santo", "2024-05-01": "Dia del Trabajo",
        "2024-05-13": "Ascension del Senor (Emiliani)",
        "2024-06-03": "Corpus Christi (Emiliani)",
        "2024-06-10": "Sagrado Corazon de Jesus (Emiliani)",
        "2024-07-01": "San Pedro y San Pablo (Emiliani)",
        "2024-07-20": "Dia de la Independencia", "2024-08-07": "Batalla de Boyaca",
        "2024-08-19": "Asuncion de la Virgen (Emiliani)",
        "2024-10-14": "Dia de la Raza (Emiliani)",
        "2024-11-04": "Todos los Santos (Emiliani)",
        "2024-11-11": "Independencia de Cartagena (Emiliani)",
        "2024-12-08": "Inmaculada Concepcion", "2024-12-25": "Navidad",
    },
    2025: {
        "2025-01-01": "Ano Nuevo", "2025-01-06": "Reyes Magos",
        "2025-03-24": "San Jose (Emiliani)", "2025-04-17": "Jueves Santo",
        "2025-04-18": "Viernes Santo", "2025-05-01": "Dia del Trabajo",
        "2025-06-02": "Ascension del Senor (Emiliani)",
        "2025-06-23": "Corpus Christi (Emiliani)",
        "2025-06-30": "Sagrado Corazon y San Pedro y San Pablo (Emiliani)",
        "2025-07-20": "Dia de la Independencia", "2025-08-07": "Batalla de Boyaca",
        "2025-08-18": "Asuncion de la Virgen (Emiliani)",
        "2025-10-13": "Dia de la Raza (Emiliani)",
        "2025-11-03": "Todos los Santos (Emiliani)",
        "2025-11-17": "Independencia de Cartagena (Emiliani)",
        "2025-12-08": "Inmaculada Concepcion", "2025-12-25": "Navidad",
    },
    2026: {
        "2026-01-01": "Ano Nuevo", "2026-01-12": "Reyes Magos (Emiliani)",
        "2026-03-23": "San Jose (Emiliani)", "2026-04-02": "Jueves Santo",
        "2026-04-03": "Viernes Santo", "2026-05-01": "Dia del Trabajo",
        "2026-05-18": "Ascension del Senor (Emiliani)",
        "2026-06-08": "Corpus Christi (Emiliani)",
        "2026-06-15": "Sagrado Corazon de Jesus (Emiliani)",
        "2026-06-29": "San Pedro y San Pablo",
        "2026-07-20": "Dia de la Independencia", "2026-08-07": "Batalla de Boyaca",
        "2026-08-17": "Asuncion de la Virgen (Emiliani)",
        "2026-10-12": "Dia de la Raza",
        "2026-11-02": "Todos los Santos (Emiliani)",
        "2026-11-16": "Independencia de Cartagena (Emiliani)",
        "2026-12-08": "Inmaculada Concepcion", "2026-12-25": "Navidad",
    },
}

HOLIDAYS_RULE: dict[str, Any] = {
    "rule": (
        "LEY EMILIANI (Ley 51 de 1983) IS THE REASON THIS TABLE CANNOT BE COMPUTED FROM A DATE "
        "LIST. Twelve of Colombia's eighteen holidays MOVE to the following Monday when they do "
        "not already fall on one -- Reyes (6 January), San Jose (19 March), San Pedro y San Pablo "
        "(29 June), Asuncion (15 August), Dia de la Raza (12 October), Todos los Santos (1 "
        "November), Independencia de Cartagena (11 November), and the three Easter-relative "
        "feasts Ascension (Easter+39), Corpus Christi (Easter+60) and Sagrado Corazon "
        "(Easter+68). The six IMMOVABLE ones are 1 January, 1 May, 20 July, 7 August, 8 December "
        "and 25 December, plus Jueves Santo and Viernes Santo which follow Easter exactly. "
        "Colombia therefore has EIGHTEEN public holidays, among the most of any market, and the "
        "great majority of them fall on a MONDAY -- which makes 'Monday' a structurally "
        "different session in Colombia from anywhere else in this command and makes any "
        "day-of-week study here about the holiday law rather than about behaviour. Two "
        "Emiliani feasts can also LAND ON THE SAME MONDAY (Sagrado Corazon and San Pedro in "
        "2025), which a naive generator double-counts. Weekends are Saturday and Sunday."),
    "table": _CO_HOLIDAYS,
    "years": (2024, 2025, 2026),
    "status": {2024: "DERIVED from Ley 51 de 1983 plus the tabulated Easter",
               2025: "DERIVED, including the Sagrado Corazon / San Pedro collision on 30 June",
               2026: "DERIVED; the BVC publishes its own trading calendar annually and that "
                     "circular is the authority"},
    "weekly_closed": (5, 6),
    "note": "the FX market follows the BANK calendar; the BVC calendar can add days, and a US "
            "holiday with Colombia open is a thin-liquidity session rather than a closure",
}


def holidays(year: int) -> dict[str, str]:
    """The closure table for one year; `{}` for a year this pack does not declare."""
    return dict(_CO_HOLIDAYS.get(year) or {})


def is_closed(day: date) -> bool:
    """True when the Colombian market is closed on `day` (weekends included)."""
    return day.weekday() >= 5 or day.isoformat() in holidays(day.year)


def monday_share(year: int) -> float:
    """The share of this year's holidays that fall on a Monday.

    Reported as a number because the Emiliani law's consequence -- that Colombian Mondays are
    structurally different sessions -- is the sort of claim that should be measured rather than
    asserted, and it is the reason CO-J exists.
    """
    table = holidays(year)
    if not table:
        return 0.0
    mondays = sum(1 for iso in table if date.fromisoformat(iso).weekday() == 0)
    return mondays / len(table)


# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "CFTC Commitments of Traders -- WTI crude and ICE coffee",
     "publisher": "CFTC", "frequency": "weekly", "lag": "Friday 15:30 ET for Tuesday positions",
     "field": "non-commercial net, open interest",
     "why": "there is no COP contract, so Colombian positioning is read in the COMMODITIES the "
            "country sells; the desk's cot.json axis maps XTIUSD and XAUUSD",
     "pit": True, "status": "AVAILABLE on this box for the crude leg"},
    {"name": "BanRep foreign holdings of TES",
     "publisher": "BanRep / Ministerio de Hacienda", "frequency": "monthly",
     "lag": "about 20 days", "field": "non-resident holdings of local-currency government debt",
     "why": "the real-money carry leg; Colombian local debt had one of the highest foreign shares "
            "in EM and its unwind is a measured flow",
     "pit": True, "status": "declared; public, not collected on this box"},
    {"name": "Superfinanciera FX derivative positions by counterparty sector",
     "publisher": "Superintendencia Financiera", "frequency": "weekly",
     "lag": "one to two weeks", "field": "forward and option positions by sector",
     "why": "the only Colombian positioning series that separates the exporter hedge from the "
            "offshore carry book",
     "pit": True, "status": "declared; not collected"},
    {"name": "FNC coffee purchase and export registry",
     "publisher": "Federacion Nacional de Cafeteros", "frequency": "monthly",
     "lag": "about 10 days", "field": "production, internal purchases and exports in 60kg bags",
     "why": "the QUANTITY leg of the coffee formula -- the half the published price equation "
            "does not give you, and therefore the half worth measuring",
     "pit": True, "status": "declared; public monthly bulletins"},
)

# --------------------------------------------------------------------------- terminology
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "policy": ("Banco de la Republica", "BanRep", "Junta Directiva", "tasa de intervencion",
               "tasa de politica monetaria", "minutas", "informe de politica monetaria",
               "meta de inflacion", "IPC", "inflacion basica", "IBR", "encaje",
               "regla fiscal", "CARF", "marco fiscal de mediano plazo"),
    "fx": ("TRM", "tasa representativa del mercado", "dolar", "peso colombiano",
           "devaluacion", "revaluacion", "subasta de opciones", "control de volatilidad",
           "acumulacion de reservas", "forward peso dolar", "cobertura cambiaria",
           "spot interbancario", "Set-FX"),
    "coffee": ("cafe", "precio interno de referencia", "carga de 125 kilos", "FNC",
               "Federacion Nacional de Cafeteros", "cafe suave colombiano", "diferencial",
               "cosecha principal", "mitaca", "broca", "roya", "trilla", "excelso",
               "comite de cafeteros", "cooperativa de caficultores"),
    "energy_mining": ("Ecopetrol", "ANH", "Agencia Nacional de Hidrocarburos", "crudo Castilla",
                      "crudo Vasconia", "Cano Limon", "Covenas", "voladura del oleoducto",
                      "atentado al oleoducto", "Cerrejon", "Drummond", "carbon termico",
                      "mineria ilegal", "oro de aluvion", "regalias"),
    "market": ("BVC", "Bolsa de Valores de Colombia", "COLCAP", "TES", "TES tasa fija",
               "TES UVR", "deuda publica interna", "comisionista de bolsa", "fondo de pensiones",
               "AFP Colombia", "Porvenir", "Proteccion", "calificacion soberana"),
    "flows": ("remesas", "inversion extranjera directa", "balanza comercial",
              "deficit de cuenta corriente", "exportaciones no tradicionales", "flores",
              "banano", "aguacate hass"),
    "community": ("La Republica", "Portafolio", "Semana Economia", "Rankia Colombia",
                  "inversionista colombiano", "foro bolsa Colombia"),
}

# --------------------------------------------------------------------------- source classes
#: THE TEN LAYERS (principal's per-country depth rule, 2026-09-17). A country is never "covered"
#: by five obvious sources. A layer with no source must be NAMED ABSENT WITH A REASON in
#: `LAYER_ABSENCES`; blank is never an answer (L1.28a).
SOURCE_LAYERS: tuple[str, ...] = (
    "official", "institutional", "academic", "practitioner", "retail_ecology", "app_ecosystem",
    "media", "archive", "physical_economy", "source_graph")

#: Three INDEPENDENT labels per source: a PUBLIC source can be FRINGE and still PREDICTIVE, and an
#: AUTHORITATIVE one can be NOT_PREDICTIVE. Collapsing them into one quality score discards the
#: fringe material that works and privileges the official series that does not.
ACCESS_LABELS: tuple[str, ...] = (
    "PUBLIC", "PUBLIC_WITH_TERMS", "LICENSED", "OPEN_DATA", "PUBLIC_ARCHIVE", "PUBLIC_SOCIAL",
    "USER_SUBMITTED", "ACCESS_UNCLEAR", "PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")
CREDIBILITY: tuple[str, ...] = ("AUTHORITATIVE", "RELIABLE", "UNRELIABLE", "FRINGE",
                                "CONTRADICTED", "UNKNOWN")
PREDICTIVE_STATES: tuple[str, ...] = ("UNTESTED", "PREDICTIVE", "NOT_PREDICTIVE",
                                      "NARRATIVE_FEATURE")

SOURCE_CLASSES: tuple[dict[str, Any], ...] = (
    {"id": "co_banrep", "layer": "official",
     "label": "Banco de la Republica statistics and the TRM series",
     "roots": ("https://www.banrep.gov.co/es/estadisticas",
               "https://totoro.banrep.gov.co/estadisticas-economicas/",
               "https://www.banrep.gov.co/es/estadisticas/trm"),
     "languages": ("es-CO", "en"), "licence": "public open data, no key",
     "access_label": "OPEN_DATA", "credibility": "AUTHORITATIVE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("serie historica TRM tasa representativa del mercado",
                 "tasa de intervencion de politica monetaria serie",
                 "reservas internacionales netas Colombia serie",
                 "subastas de opciones control de volatilidad resultados"),
     "notes": "the TRM is a TWO-DAY CHAIN: transactions on day D, certified that evening, applied "
              "on D+1. Two business days, not one -- the Chilean convention is one and the two "
              "are routinely confused"},
    {"id": "co_dane", "layer": "official",
     "label": "DANE national statistics (IPC, PIB, comercio exterior, ISE)",
     "roots": ("https://www.dane.gov.co/index.php/estadisticas-por-tema",
               "https://microdatos.dane.gov.co/"),
     "languages": ("es-CO",), "licence": "public open data",
     "access_label": "OPEN_DATA", "credibility": "AUTHORITATIVE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("IPC variacion mensual DANE", "exportaciones de cafe y petroleo mensual",
                 "indicador de seguimiento a la economia ISE",
                 "balanza comercial deficit de cuenta corriente"),
     "notes": "Colombia's current-account deficit is among the largest in the region relative to "
              "GDP, which is what makes its currency an EM-stress instrument rather than only a "
              "commodity one"},
    {"id": "co_anh_minenergia", "layer": "official",
     "label": "ANH hydrocarbon statistics and the energy ministry",
     "roots": ("https://www.anh.gov.co/es/operaciones-y-regal%C3%ADas/",
               "https://www.minenergia.gov.co/es/servicio-al-ciudadano/estadisticas/"),
     "languages": ("es-CO",), "licence": "public open data",
     "access_label": "OPEN_DATA", "credibility": "AUTHORITATIVE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("produccion de petroleo por campo mensual ANH",
                 "reservas probadas de crudo Colombia anos",
                 "regalias por hidrocarburos distribucion",
                 "produccion de gas natural Colombia"),
     "notes": "Colombian proved reserves are short-lived by world standards, which makes the "
              "RESERVE LIFE a structural fiscal variable rather than an industry footnote"},
    {"id": "co_bvc_superfin", "layer": "institutional",
     "label": "BVC, Superintendencia Financiera and Asobancaria",
     "roots": ("https://www.bvc.com.co/", "https://www.superfinanciera.gov.co/",
               "https://www.asobancaria.com/", "https://www.set-fx.com/"),
     "languages": ("es-CO",),
     "licence": "public summary data; intraday and Set-FX depth are licensed products",
     "access_label": "PUBLIC_WITH_TERMS", "credibility": "AUTHORITATIVE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("calendario bursatil BVC dias no habiles",
                 "posiciones en derivados por sector Superfinanciera",
                 "certificacion de la TRM metodologia",
                 "integracion regional BVC Chile Peru nuam"),
     "notes": "the BVC's merger with the Chilean and Peruvian exchanges is a DATED structural "
              "change to Andean equity liquidity and therefore an era boundary for three packs "
              "in this command at once"},
    {"id": "co_fnc", "layer": "institutional",
     "label": "Federacion Nacional de Cafeteros -- the price formula and the crop registry",
     "roots": ("https://federaciondecafeteros.org/wp/estadisticas-cafeteras/",
               "https://federaciondecafeteros.org/wp/precio-cafe-hoy/"),
     "languages": ("es-CO",), "licence": "public statistics and a public daily price",
     "access_label": "PUBLIC", "credibility": "AUTHORITATIVE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("precio interno de referencia carga 125 kilos hoy",
                 "produccion de cafe mensual sacos de 60 kilos",
                 "exportaciones de cafe colombiano mensual",
                 "diferencial del cafe suave colombiano"),
     "notes": "THE PACK'S BEST SOURCE. A published DAILY equation linking ICE 'C', the Colombian "
              "mild differential and the TRM to a farm-gate price -- the price leg of a "
              "terms-of-trade channel, given rather than estimated"},
    {"id": "co_academic", "layer": "academic",
     "label": "Colombian economics research (BanRep Borradores, Fedesarrollo, Uniandes CEDE)",
     "roots": ("https://www.banrep.gov.co/es/publicaciones-investigaciones/borradores-economia",
               "https://www.fedesarrollo.org.co/publicaciones",
               "https://economia.uniandes.edu.co/cede/documentos-cede",
               "https://www.scielo.org.co/"),
     "languages": ("es-CO", "en"), "licence": "open-access working papers and journals",
     "access_label": "PUBLIC", "credibility": "RELIABLE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("efectividad de las subastas de opciones del Banco de la Republica",
                 "traspaso del precio del petroleo a la tasa de cambio Colombia",
                 "transmision del precio internacional al precio interno del cafe",
                 "regla fiscal sostenibilidad de la deuda Colombia"),
     "notes": "the Borradores de Economia series contains the desk's best available prior on "
              "whether the OPTION TRIGGER works, written by the institution that pulls it -- a "
              "hypothesis with a citation, still a hypothesis"},
    {"id": "co_practitioner", "layer": "practitioner",
     "label": "Colombian sell-side and buy-side research",
     "roots": ("https://www.corficolombiana.com/investigaciones-economicas",
               "https://www.grupobancolombia.com/investigaciones-economicas",
               "https://www.credicorpcapital.com/", "https://www.rankia.co/foros/"),
     "languages": ("es-CO",),
     "licence": "public web with terms; claims extracted only, nothing republished",
     "access_label": "PUBLIC_WITH_TERMS", "credibility": "RELIABLE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("proyeccion TRM fin de ano informe",
                 "estrategia en TES tasa fija recomendacion",
                 "impacto de la produccion de crudo en la cuenta corriente",
                 "cobertura cambiaria exportadores de cafe"),
     "notes": "the Colombian sell-side is unusually explicit about the TRM's two-day lag because "
              "their own corporate clients settle on it, which makes this the layer that "
              "documents the convention rather than the official one"},
    {"id": "co_retail_ecology", "layer": "retail_ecology",
     "label": "Colombian retail investor communities",
     "roots": ("https://www.rankia.co/", "https://www.reddit.com/r/Colombia/",
               "https://www.reddit.com/r/FinanzasColombia/"),
     "languages": ("es-CO",),
     "licence": "public social; user-submitted content, nothing republished",
     "access_label": "PUBLIC_SOCIAL", "credibility": "UNRELIABLE",
     "predictive_state": "NARRATIVE_FEATURE", "machine_use_allowed": True,
     "queries": ("comprar dolares ahora o esperar Colombia foro",
                 "invertir en TES o en CDT cual rinde mas",
                 "operar forex desde Colombia broker regulado",
                 "cuanto vale la carga de cafe hoy foro cafetero"),
     "notes": "UNRELIABLE AND KEPT. The coffee-grower forums discuss the FNC reference price "
               "daily, which makes them a real-time read on whether producers are selling into "
               "the published price or holding -- the QUANTITY leg the formula does not give"},
    {"id": "co_app_ecosystem", "layer": "app_ecosystem",
     "label": "Colombian retail brokerage and fintech apps",
     "roots": ("https://www.trii.com.co/", "https://www.tyba.com.co/",
               "https://nu.com.co/", "https://www.mql5.com/es/code"),
     "languages": ("es-CO",), "licence": "public web with terms; public code repositories",
     "access_label": "PUBLIC_WITH_TERMS", "credibility": "UNRELIABLE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("Trii comprar acciones colombianas comision",
                 "invertir en dolares desde Colombia app",
                 "bot de trading forex peso colombiano",
                 "cuenta de ahorro en dolares fintech Colombia"),
     "notes": "the Colombian app layer is young and thin, and that THINNESS is the finding: "
              "domestic retail FX demand here is far smaller and slower than Mexico's, which is "
              "the cross-country contrast MX-L needs to be identifiable"},
    {"id": "co_media", "layer": "media",
     "label": "Colombian financial press",
     "roots": ("https://www.larepublica.co/", "https://www.portafolio.co/",
               "https://www.semana.com/economia/", "https://www.eltiempo.com/economia"),
     "languages": ("es-CO",),
     "licence": "public web with terms; several paywalled, nothing republished",
     "access_label": "PUBLIC_WITH_TERMS", "credibility": "RELIABLE",
     "predictive_state": "NARRATIVE_FEATURE", "machine_use_allowed": True,
     "queries": ("atentado contra el oleoducto Cano Limon Covenas",
                 "dolar hoy en Colombia cierre TRM manana",
                 "Banco de la Republica baja tasas decision",
                 "precio interno del cafe alcanza maximo"),
     "notes": "THE PIPELINE ATTACKS ARE DATED HERE FIRST. A supply interruption reaches the press "
              "within hours and the official statistics a month later, which is the entire reason "
              "this layer earns its multiple-testing charge in Colombia"},
    {"id": "co_archive", "layer": "archive",
     "label": "Historical archives: Biblioteca Luis Angel Arango, Diario Oficial, BanRep series",
     "roots": ("https://babel.banrepcultural.org/", "https://www.suin-juriscol.gov.co/",
               "https://web.archive.org/web/*/banrep.gov.co/*"),
     "languages": ("es-CO",),
     "licence": "public archive; digitised public-domain material and the legal gazette",
     "access_label": "PUBLIC_ARCHIVE", "credibility": "AUTHORITATIVE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("ley 51 de 1983 Emiliani texto traslado de festivos",
                 "resolucion externa control de volatilidad opciones Banco de la Republica",
                 "metodologia de certificacion de la TRM resolucion",
                 "pacto cafetero internacional cuotas historia"),
     "notes": "LEY 51 DE 1983 IS THE PRIMARY SOURCE FOR THE HOLIDAY TABLE and the option-auction "
              "resolutions are the primary source for the intervention trigger; both are legal "
              "texts and neither is safely taken from a summary"},
    {"id": "co_physical_economy", "layer": "physical_economy",
     "label": "Physical flow: pipelines, ports, power and the coffee crop",
     "roots": ("https://www.cenit-transporte.com/", "https://www.puertodecartagena.com/",
               "https://www.xm.com.co/", "https://agronet.gov.co/"),
     "languages": ("es-CO",), "licence": "public open data and public operator statistics",
     "access_label": "OPEN_DATA", "credibility": "AUTHORITATIVE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("interrupciones del oleoducto por atentado registro",
                 "carga movilizada puerto de Cartagena Buenaventura estadistica",
                 "generacion hidraulica embalses XM nivel",
                 "area sembrada y produccion de cafe por departamento"),
     "notes": "COUNTED QUANTITIES, and two of them are unusual. The pipeline interruption register "
              "gives the oil-supply event class an n; the reservoir level is an El Nino sensor "
              "that reaches the CPI through electricity prices and the coffee crop at once"},
    {"id": "co_source_graph", "layer": "source_graph",
     "label": "The graph that finds the NEXT Colombian source",
     "roots": ("https://www.datos.gov.co/", "https://agronet.gov.co/estadistica/",
               "https://www.banrep.gov.co/es/publicaciones-investigaciones",
               "https://github.com/topics/colombia-data"),
     "languages": ("es-CO", "en"),
     "licence": "public; open-data catalogues and reference sections",
     "access_label": "PUBLIC", "credibility": "RELIABLE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("datos abiertos Colombia conjunto economia petroleo cafe",
                 "quien cita la metodologia del precio interno del cafe",
                 "bibliografia borradores de economia fuente de datos",
                 "repositorio github datos DANE BanRep quien usa"),
     "notes": "datos.gov.co is unusually complete for a country this size and is the instrument "
              "that finds the Colombian series this pack has not heard of; without it the other "
              "nine layers are a list that stops growing"},
)

LAYER_ABSENCES: dict[str, str] = {}

# --------------------------------------------------------------------------- datasets
DATASETS: tuple[dict[str, Any], ...] = (
    {"name": "TRM daily series", "source": "co_banrep",
     "coverage": "1991 to present", "frequency": "daily",
     "publication_lag_days": 1.0, "revisions": "none",
     "licence": "public open data", "history_from": "1991-12-02", "pit_feasible": True,
     "assets": ("XBRUSD", "COFARA", "USDBRL"),
     "mechanism_families": ("calendar_settlement", "session_microstructure"),
     "how_to_fetch": "BanRep statistics portal TRM series; carry the TWO-BUSINESS-DAY chain into "
                     "every alignment or the whole series is misdated"},
    {"name": "BanRep policy rate", "source": "co_banrep",
     "coverage": "1999 to present", "frequency": "event",
     "publication_lag_days": 0.0, "revisions": "none",
     "licence": "public open data", "history_from": "1999-09-30", "pit_feasible": True,
     "assets": ("XBRUSD", "UST10Y", "USDBRL"),
     "mechanism_families": ("central_bank_surprise", "carry_funding"),
     "how_to_fetch": "BanRep statistics portal; the VOTE SPLIT is announced the same day"},
    {"name": "BanRep option-auction results and reserve accumulation", "source": "co_banrep",
     "coverage": "1999 to present", "frequency": "event",
     "publication_lag_days": 0.0, "revisions": "none",
     "licence": "public open data", "history_from": "1999-09-30", "pit_feasible": True,
     "assets": ("XBRUSD", "USDBRL"),
     "mechanism_families": ("institutional_flow", "central_bank_surprise"),
     "how_to_fetch": "BanRep auction results; the 20-day moving-average TRIGGER makes this a "
                     "discontinuity design with a published threshold"},
    {"name": "FNC precio interno de referencia (daily)", "source": "co_fnc",
     "coverage": "2000 to present", "frequency": "daily",
     "publication_lag_days": 0.0, "revisions": "none",
     "licence": "public", "history_from": "2000-01-03", "pit_feasible": True,
     "assets": ("COFARA", "COFROB"),
     "mechanism_families": ("transfer", "corporate_flow"),
     "how_to_fetch": "FNC price page and statistical bulletins; the FORMULA is published, so the "
                     "price leg of the terms-of-trade channel is given rather than estimated"},
    {"name": "FNC coffee production, internal purchases and exports", "source": "co_fnc",
     "coverage": "1956 to present", "frequency": "monthly",
     "publication_lag_days": 10.0, "revisions": "restated when cooperatives report late",
     "licence": "public", "history_from": "1956-01-31", "pit_feasible": True,
     "assets": ("COFARA", "COFROB"),
     "mechanism_families": ("corporate_flow", "release_surprise"),
     "how_to_fetch": "FNC estadisticas cafeteras; the QUANTITY leg the formula does not give"},
    {"name": "ANH crude production by field", "source": "co_anh_minenergia",
     "coverage": "2000 to present", "frequency": "monthly",
     "publication_lag_days": 45.0, "revisions": "restated when a field reports late",
     "licence": "public open data", "history_from": "2000-01-31", "pit_feasible": True,
     "assets": ("XBRUSD", "XTIUSD"),
     "mechanism_families": ("corporate_flow", "failure"),
     "how_to_fetch": "ANH operations and royalties statistics; the by-field detail is what makes "
                     "a pipeline interruption attributable to lost barrels"},
    {"name": "DANE IPC and the food and energy components", "source": "co_dane",
     "coverage": "1954 to present", "frequency": "monthly",
     "publication_lag_days": 5.0, "revisions": "none",
     "licence": "public open data", "history_from": "1954-07-31", "pit_feasible": True,
     "assets": ("XBRUSD", "UST10Y"),
     "mechanism_families": ("release_surprise", "central_bank_surprise"),
     "how_to_fetch": "DANE IPC bulletins; the ENERGY component carries the reservoir level, which "
                     "makes El Nino a monetary variable here"},
    {"name": "DANE trade balance and the current-account deficit", "source": "co_dane",
     "coverage": "1980 to present", "frequency": "monthly and quarterly",
     "publication_lag_days": 40.0, "revisions": "revised once",
     "licence": "public open data", "history_from": "1980-01-31", "pit_feasible": True,
     "assets": ("XBRUSD", "USDBRL", "USDZAR"),
     "mechanism_families": ("release_surprise", "corporate_flow"),
     "how_to_fetch": "DANE comercio exterior; one of the largest current-account deficits in the "
                     "region relative to GDP, which is why COP behaves as an EM-stress currency"},
    {"name": "Cenit pipeline interruption register", "source": "co_physical_economy",
     "coverage": "2010 to present", "frequency": "event",
     "publication_lag_days": 1.0, "revisions": "none",
     "licence": "public operator disclosure", "history_from": "2010-01-01", "pit_feasible": True,
     "assets": ("XBRUSD", "XTIUSD"),
     "mechanism_families": ("failure", "release_surprise"),
     "how_to_fetch": "Cenit operational notices plus the press; a REPEATED dated disruption class "
                     "has an n, which one famous outage never does"},
    {"name": "XM reservoir levels and hydro generation", "source": "co_physical_economy",
     "coverage": "1995 to present", "frequency": "daily",
     "publication_lag_days": 1.0, "revisions": "none",
     "licence": "public open data", "history_from": "1995-01-02", "pit_feasible": True,
     "assets": ("XBRUSD", "XNGUSD", "COFARA"),
     "mechanism_families": ("release_surprise", "transfer"),
     "how_to_fetch": "XM market operator data; an El Nino sensor that reaches the CPI through "
                     "electricity and the coffee crop through rainfall at the same time"},
    {"name": "Superfinanciera FX derivative positions by sector", "source": "co_bvc_superfin",
     "coverage": "2010 to present", "frequency": "weekly",
     "publication_lag_days": 10.0, "revisions": "occasional restatement",
     "licence": "public regulatory statistics", "history_from": "2010-01-08",
     "pit_feasible": True,
     "assets": ("XBRUSD", "USDBRL"),
     "mechanism_families": ("positioning", "institutional_flow"),
     "how_to_fetch": "Superfinanciera statistical releases; separates the exporter hedge from the "
                     "offshore carry book, which no price series can do"},
    {"name": "Colombian practitioner and grower claims (es-CO)", "source": "co_retail_ecology",
     "coverage": "rolling", "frequency": "continuous",
     "publication_lag_days": 0.0, "revisions": "n/a -- dated at capture",
     "licence": "public social, claims only", "history_from": "2015-01-01", "pit_feasible": False,
     "assets": ("COFARA", "XBRUSD"),
     "mechanism_families": ("scouts", "transfer"),
     "how_to_fetch": "deep_forest_miner grounds in es-CO; the grower forums are a real-time read "
                     "on whether producers are selling into the published price or holding"},
)

# --------------------------------------------------------------------------- actors
ACTORS: tuple[dict[str, Any], ...] = (
    {"name": "coffee grower selling at the published reference",
     "holds": "parchment coffee and a decision about when to deliver it",
     "forced_to": ("sell to fund the harvest labour bill regardless of price",
                   "deliver at the FNC reference, which is an equation, not a negotiation"),
     "when": "the main crop October-December and the mitaca April-June",
     "information": ("the daily FNC reference price", "the TRM", "the ICE 'C' second position"),
     "constraints": ("the price is FORMULAIC and published, so the only decision is timing",
                     "labour must be paid in pesos during the harvest"),
     "instruments": ("COFARA", "COFROB"),
     "counterparties": ("FNC cooperatives", "private exporters"),
     "observables": ("FNC internal purchases", "the published reference", "export volumes"),
     "impact": "the QUANTITY leg of a channel whose price leg is given by an equation -- the "
               "cleanest available separation of price from quantity in this desk's book",
     "persistence": "seasonal and recurring",
     "falsifier": "internal purchase volumes show no relationship to the published reference "
                  "price once the harvest calendar is controlled for, which would mean the "
                  "grower's timing is agronomic rather than economic",
     "notes": "the formula makes this actor uniquely legible: everywhere else the producer's "
              "price has to be estimated"},
    {"name": "FNC as a price administrator",
     "holds": "the reference formula, cooperative buying capacity and a stabilisation fund",
     "forced_to": ("publish the reference every business day",
                   "buy at the reference through cooperatives when private demand is absent"),
     "when": "daily",
     "information": ("ICE 'C'", "the mild differential", "the TRM", "crop conditions"),
     "constraints": ("the formula is public and its inputs are observable",
                     "the guarantee of purchase is an institutional commitment"),
     "instruments": ("COFARA",),
     "counterparties": ("growers", "exporters", "the government"),
     "observables": ("the published price", "purchase volumes", "fund balances"),
     "impact": "a public, daily, mechanical transmission from a world price and an exchange rate "
               "to a producer's income -- a rare case where a transmission channel is LEGISLATED",
     "persistence": "permanent under the current institutional arrangement",
     "falsifier": "the published reference departs from its own stated formula in a way that "
                  "cannot be explained by the differential, which would mean the administration "
                  "is discretionary and the mechanism is not what it says it is",
     "notes": "testing the formula against its own inputs is the first, cheapest check"},
    {"name": "Ecopetrol as a state-controlled exporter",
     "holds": "most Colombian crude production and a short reserve life",
     "forced_to": ("pay a dividend that is a FISCAL item because the state is the majority holder",
                   "invest to arrest a production decline with a politically constrained mandate"),
     "when": "quarterly dividends; continuous production",
     "information": ("ANH production data", "Brent and the Colombian grade differentials",
                     "the fiscal framework"),
     "constraints": ("state control makes capex a political variable",
                     "reserve life is short by world standards"),
     "instruments": ("XBRUSD", "XTIUSD"),
     "counterparties": ("the Treasury", "international buyers", "refiners"),
     "observables": ("production by field", "the dividend", "royalties"),
     "impact": "Colombian FISCAL risk is pro-cyclical with crude because the sovereign's dividend "
               "and its royalty income are the same cycle; a low oil year is a fiscal year",
     "persistence": "structural, years",
     "falsifier": "no relationship between crude and measured Colombian fiscal outcomes once the "
                  "global growth cycle is controlled for",
     "notes": "named as an ACTOR; Ecopetrol is not in the broker registry and is never a symbol"},
    {"name": "pipeline saboteur and the interruption class",
     "holds": "the ability to close a single corridor carrying a large share of exported crude",
     "forced_to": ("act around political and negotiation cycles",),
     "when": "repeatedly, clustering with political events",
     "information": ("operator notices", "press reports", "ANH volumes"),
     "constraints": ("one pipeline carries a large share of eastern production",
                     "repairs take days to weeks"),
     "instruments": ("XBRUSD", "XTIUSD"),
     "counterparties": ("the operator", "the state"),
     "observables": ("the interruption register", "press reports", "monthly output"),
     "impact": "a REPEATED, dated, counted supply-interruption class -- far better as an event "
               "class than one famous outage, because it has an n and a distribution",
     "persistence": "each episode is days to weeks; the class is permanent",
     "falsifier": "no measurable crude or differential response to interruptions large enough to "
                  "show in monthly ANH output",
     "notes": "the press dates these within hours and the statistics a month later, which is what "
              "makes the media layer earn its charge here"},
    {"name": "BanRep running the option trigger",
     "holds": "reserves and a rule-based volatility-control mechanism",
     "forced_to": ("auction options when the published deviation threshold is crossed",
                   "accumulate reserves when conditions permit"),
     "when": "THRESHOLD-driven, not calendar-driven",
     "information": ("the 20-day moving average", "realised volatility", "the reserve level"),
     "constraints": ("the trigger is published, so the intervention is predictable in timing "
                     "though not in size",),
     "instruments": ("XBRUSD", "USDBRL"),
     "counterparties": ("local banks", "offshore funds"),
     "observables": ("auction announcements and allotments", "the deviation from the average"),
     "impact": "A DISCONTINUITY DESIGN WITH A PUBLIC THRESHOLD, which is rarer than either "
               "Chile's pre-announced programme or Brazil's auction book and is the sharpest "
               "identification of an intervention effect available in this command",
     "persistence": "permanent while the mechanism stands",
     "falsifier": "no discontinuity in the behaviour of the exchange rate at the published "
                  "deviation threshold",
     "notes": "the threshold, not the level, is the research object"},
    {"name": "foreign holder of TES",
     "holds": "local-currency Colombian government debt with a large foreign share",
     "forced_to": ("cut when the carry-to-vol ratio deteriorates or the rating changes",
                   "follow index weights mechanically"),
     "when": "episodic; the sovereign downgrade to sub-investment grade was the largest event",
     "information": ("foreign-holdings statistics", "rating actions", "the fiscal rule"),
     "constraints": ("index inclusion rules are mechanical and mandate-driven",),
     "instruments": ("XBRUSD", "UST10Y", "USDBRL"),
     "counterparties": ("local banks", "pension funds", "index funds"),
     "observables": ("monthly foreign-holdings data", "rating announcements"),
     "impact": "a rating action here forced MECHANICAL index-driven selling, which is a flow with "
               "a known trigger and a known direction -- the cleanest kind of forced flow",
     "persistence": "the unwind runs for quarters",
     "falsifier": "no measurable flow or price effect around index-relevant rating actions "
                  "beyond what the global EM factor explains",
     "notes": "mechanical index selling is forced flow in its purest form"},
    {"name": "Colombian pension fund (AFP) and the offshore mandate",
     "holds": "peso liabilities against a portfolio with a large and regulated foreign share",
     "forced_to": ("deploy monthly contributions", "rebalance when limits or mandates change"),
     "when": "monthly, with episodic regulatory changes",
     "information": ("Superfinanciera reports", "regulatory limits", "the pension reform"),
     "constraints": ("investment limits are regulatory",
                     "a pension reform changes who manages the flow and therefore where it goes"),
     "instruments": ("XBRUSD", "US500", "UST10Y"),
     "counterparties": ("global managers", "the Treasury"),
     "observables": ("AFP portfolio reports", "the foreign share"),
     "impact": "the pension reform debate is a DATED policy risk to a large institutional flow; "
               "the flow is regular and the regime change to it is not",
     "persistence": "structural, with dated regime risk",
     "falsifier": "no measurable FX or asset effect around the pension-reform milestones",
     "notes": "the Chilean and Mexican analogues make this a three-country comparison"},
    {"name": "thermal coal exporter",
     "holds": "Cerrejon and Drummond output sold mostly into Europe and Asia",
     "forced_to": ("ship on contract regardless of the spot price",
                   "suspend when a labour dispute or a rail blockade closes the corridor"),
     "when": "continuous, with episodic disruptions",
     "information": ("API2 prices", "European gas prices", "export statistics"),
     "constraints": ("rail and port capacity are the binding constraints",
                     "European buyers' demand shifted sharply with the gas crisis"),
     "instruments": ("XNGUSD", "XBRUSD", "XTIUSD"),
     "counterparties": ("European utilities", "Asian buyers"),
     "observables": ("export volumes", "port throughput", "API2"),
     "impact": "the 2022 European demand shift was a step change in Colombian export receipts "
               "with no Colombian cause at all -- a clean external shock to the terms of trade",
     "persistence": "the shift was a step; the level is cyclical",
     "falsifier": "no measurable Colombian terms-of-trade or FX response to the European gas "
                  "shock beyond what crude explains",
     "notes": "no coal instrument is quoted here; XNGUSD carries the substitution and it is "
              "declared rather than assumed away"},
    {"name": "illegal gold miner and the informal export channel",
     "holds": "alluvial gold produced outside the formal registry",
     "forced_to": ("monetise in dollars through informal channels",
                   "shift activity with the gold price and with enforcement"),
     "when": "continuous, responding to the gold price",
     "information": ("the gold price", "enforcement actions", "export statistics"),
     "constraints": ("informality is a response to royalties and enforcement, both policy "
                     "variables",),
     "instruments": ("XAUUSD", "XBRUSD"),
     "counterparties": ("informal buyers", "refiners abroad"),
     "observables": ("the gap between reported production and reported exports",
                     "enforcement actions"),
     "impact": "a gold-price-elastic informal dollar inflow and capital-flight channel that "
               "appears in the balance of payments as an unexplained residual",
     "persistence": "structural",
     "falsifier": "no relationship between the gold price and the measured discrepancy between "
                  "reported production and reported exports",
     "notes": "an unusual case where the OBSERVABLE is the inconsistency between two official "
              "series rather than either one of them"},
    {"name": "El Nino and the reservoir level",
     "holds": "the hydro system that generates most Colombian electricity",
     "forced_to": ("switch to thermal generation when reservoirs fall",
                   "raise regulated tariffs, which enter the CPI"),
     "when": "El Nino episodes, irregular and multi-year",
     "information": ("XM reservoir levels", "rainfall", "generation mix"),
     "constraints": ("hydro dependence is structural",
                     "tariff pass-through is regulated and lagged"),
     "instruments": ("XNGUSD", "XBRUSD", "COFARA"),
     "counterparties": ("generators", "regulated consumers"),
     "observables": ("daily reservoir levels", "the CPI energy component",
                     "coffee crop bulletins"),
     "impact": "ONE WEATHER STATE REACHES THE CENTRAL BANK THROUGH ELECTRICITY AND THE COFFEE CROP "
               "AT THE SAME TIME, which makes El Nino a monetary variable in Colombia and not "
               "only an agricultural one",
     "persistence": "episodes run for quarters",
     "falsifier": "no relationship between reservoir levels and the energy component of the CPI "
                  "after controlling for the international fuel price",
     "notes": "the two-channel property is what makes this worth a domain of its own"},
    {"name": "Colombian exporter hedging the peso",
     "holds": "dollar receipts against peso costs",
     "forced_to": ("sell dollars forward to cover local costs",
                   "roll hedges on a quarterly cycle"),
     "when": "monthly, concentrated at quarter ends",
     "information": ("the forward curve", "the TRM", "shipment schedules"),
     "constraints": ("cost bases are peso and non-negotiable",
                     "hedge accounting fixes the tenor"),
     "instruments": ("XBRUSD", "COFARA"),
     "counterparties": ("local banks", "BanRep as residual"),
     "observables": ("Superfinanciera derivative positions by sector",),
     "impact": "the structural forward supply of dollars the option mechanism sits opposite; when "
               "it thins, the trigger is what replaces it",
     "persistence": "continuous, with a quarter-end shape",
     "falsifier": "no relationship between measured exporter forward positions and the frequency "
                  "of option-auction triggers",
     "notes": "links the positioning layer to the intervention rule, which is the pack's two "
              "best observables joined"},
    {"name": "remittance sender in the United States and Spain",
     "holds": "foreign wages and a family in Colombia",
     "forced_to": ("send on a pay cycle regardless of the exchange rate",),
     "when": "monthly with a December peak",
     "information": ("US and Spanish employment", "transfer costs", "the TRM"),
     "constraints": ("the recipient's needs are in pesos and are not price-elastic",),
     "instruments": ("XBRUSD", "US500"),
     "counterparties": ("remittance operators", "Colombian banks"),
     "observables": ("the BanRep remittance series", "US and Spanish employment"),
     "impact": "roughly ten billion dollars a year on a foreign-employment clock -- the same "
               "counter-cyclical sign as Mexico's and an order of magnitude smaller, which makes "
               "the pair a size test of the mechanism",
     "persistence": "structural",
     "falsifier": "the Colombian remittance channel shows a measurable FX effect at a size where "
                  "the Mexican one does not, or vice versa, with no institutional difference to "
                  "explain it",
     "notes": "Mexico and Colombia together are a SIZE experiment on the same mechanism"},
    {"name": "fiscal authority under the regla fiscal and the CARF",
     "holds": "a legislated fiscal rule with an independent committee watching it",
     "forced_to": ("meet the rule's path or explain a deviation publicly",
                   "absorb the oil cycle through royalties and the Ecopetrol dividend"),
     "when": "the annual budget and the medium-term framework, with CARF opinions in between",
     "information": ("the fiscal framework", "CARF opinions", "oil revenue"),
     "constraints": ("the rule is law and the committee is independent and vocal",),
     "instruments": ("XBRUSD", "UST10Y", "USDBRL"),
     "counterparties": ("bondholders", "rating agencies", "Congress"),
     "observables": ("CARF opinions", "the fiscal result", "rating actions"),
     "impact": "an INDEPENDENT committee publicly disagreeing with the government is a dated risk "
               "event with no counterpart elsewhere in this command",
     "persistence": "the rule is structural; the disagreements are episodic",
     "falsifier": "no measurable Colombian risk-premium response to CARF opinions once the global "
                  "EM factor and the oil price are controlled for",
     "notes": "a dated, public, institutional disagreement is an unusually clean event class"},
)

# --------------------------------------------------------------------------- domains
_CONTROLS = ("a matched non-event day of the same weekday and month",
             "the global dollar factor (USDX) and US500 on the same session",
             "USDBRL and USDMXN as the LatAm peers with no Colombian exposure")

DOMAINS: tuple[dict[str, Any], ...] = (
    {"id": "CO-A", "title": "The coffee formula: price given, quantity in question",
     "objects": ("the daily FNC reference against its own stated inputs",
                 "internal purchase volumes", "the Colombian mild differential"),
     "conditions": ("the price leg is MECHANICAL and published, so only the quantity leg is a "
                    "research question",
                    "the formula uses the TRM, which is two business days old, so the FX response "
                    "is lagged by construction"),
     "instruments": ("COFARA", "COFROB"),
     "controls": (*_CONTROLS, "robusta, which shares the global price and not the Colombian "
                              "formula"),
     "notes": "the pack's best domain and the cleanest price/quantity separation in the book"},
    {"id": "CO-B", "title": "The TRM's two-business-day chain",
     "objects": ("transactions on D", "certification that evening", "application on D+1"),
     "conditions": ("the lag is TWO business days, not one",
                    "a holiday in the chain stretches it further and the stretch is datable"),
     "instruments": ("XBRUSD", "COFARA"),
     "controls": (*_CONTROLS, "the Chilean dolar observado, which is a ONE-day chain"),
     "notes": "the Chile/Colombia contrast is the control: two conventions, two lags, one "
              "mechanism class"},
    {"id": "CO-C", "title": "The option trigger as a discontinuity",
     "objects": ("the 20-day moving average", "the published deviation threshold",
                 "auction announcements"),
     "conditions": ("the threshold is PUBLIC, so the timing is predictable and the size is not",
                    "a discontinuity design needs observations either side of the threshold"),
     "instruments": ("XBRUSD", "USDBRL"),
     "controls": (*_CONTROLS, "Chile's pre-announced programmes and Brazil's auction book as the "
                              "other two intervention styles"),
     "notes": "three intervention styles in one command, and this is the only one with a number"},
    {"id": "CO-D", "title": "Pipeline interruptions as a counted supply-event class",
     "objects": ("the interruption register", "durations", "monthly ANH output"),
     "conditions": ("the class is REPEATED, which gives it an n and a distribution",
                    "the press dates it within hours and the statistics a month later"),
     "instruments": ("XBRUSD", "XTIUSD"),
     "controls": (*_CONTROLS, "global supply disruptions of comparable size elsewhere"),
     "notes": "an event class with an n beats one famous outage every time"},
    {"id": "CO-E", "title": "Oil, the current account and the peso's EM-stress beta",
     "objects": ("crude exports", "the current-account deficit", "joint moves with EM peers"),
     "conditions": ("Colombia runs one of the region's largest current-account deficits relative "
                    "to GDP, which makes it a FINANCING story as well as a commodity one",),
     "instruments": ("XBRUSD", "USDBRL", "USDMXN", "USDZAR", "US500"),
     "controls": (*_CONTROLS, "oil exporters with a current-account surplus"),
     "notes": "the financing leg is what separates COP from a pure oil currency"},
    {"id": "CO-F", "title": "El Nino as a two-channel monetary variable",
     "objects": ("XM reservoir levels", "the CPI energy component", "coffee crop bulletins"),
     "conditions": ("one weather state reaches the central bank through electricity AND the crop, "
                    "which makes the two channels hard to separate and worth separating",),
     "instruments": ("XNGUSD", "COFARA", "XBRUSD"),
     "controls": (*_CONTROLS, "El Nino episodes in countries with no hydro dependence"),
     "notes": "the two-channel property is the reason this is a domain and not a footnote"},
    {"id": "CO-G", "title": "Index-driven forced selling around rating actions",
     "objects": ("foreign TES holdings", "index-relevant rating actions", "the flow after them"),
     "conditions": ("index rules are MECHANICAL, so the direction and approximate size of the "
                    "flow are known before it happens",),
     "instruments": ("XBRUSD", "UST10Y", "USDBRL"),
     "controls": (*_CONTROLS, "rating actions that did NOT change index eligibility"),
     "notes": "the eligibility-changing versus non-changing pair is the identification"},
    {"id": "CO-H", "title": "BanRep with the finance minister on the board",
     "objects": ("the decision", "the published vote split", "fiscal-monetary disagreement"),
     "conditions": ("the fiscal authority CHAIRS the monetary board, so a conflict is internal "
                    "and appears as a split vote rather than as a public dispute",),
     "instruments": ("XBRUSD", "UST10Y", "USDBRL"),
     "controls": (*_CONTROLS, "Brazilian and Chilean boards with no fiscal member"),
     "notes": "an institutional design difference that is directly observable in the vote count"},
    {"id": "CO-I", "title": "Informal gold as a balance-of-payments residual",
     "objects": ("reported production versus reported exports", "the gold price",
                 "enforcement actions"),
     "conditions": ("the observable is the INCONSISTENCY between two official series rather than "
                    "either one of them",),
     "instruments": ("XAUUSD", "XBRUSD"),
     "controls": (*_CONTROLS, "the same discrepancy in a country with no informal mining"),
     "notes": "an unusual observable and a genuinely Colombian one"},
    {"id": "CO-J", "title": "The Emiliani Monday and the eighteen-holiday year",
     "objects": ("the share of holidays falling on a Monday", "the Tuesday after",
                 "the session either side"),
     "conditions": ("Colombia has eighteen holidays and most fall on a MONDAY by law, which makes "
                    "any Colombian day-of-week result a statement about the holiday statute "
                    "rather than about behaviour",),
     "instruments": ("XBRUSD", "COFARA"),
     "controls": (*_CONTROLS, "the same weekday in countries with no Monday-shifting law"),
     "notes": "measured by `monday_share`, because this is the kind of claim that should be a "
              "number rather than an assertion"},
    {"id": "CO-K", "title": "Remittances at one tenth of Mexico's size",
     "objects": ("the monthly remittance series", "the December peak",
                 "US and Spanish employment"),
     "conditions": ("the same mechanism as Mexico's at an order of magnitude smaller, which makes "
                    "the pair a SIZE test rather than a replication",),
     "instruments": ("XBRUSD", "US500"),
     "controls": (*_CONTROLS, "the Mexican remittance channel over the same months"),
     "notes": "two countries, one mechanism, different sizes -- the cheapest external validity "
              "test available in this command"},
    {"id": "CO-L", "title": "The fiscal rule and an independent committee that disagrees",
     "objects": ("CARF opinions", "the fiscal result", "risk-premium responses"),
     "conditions": ("a dated, public, institutional disagreement is a clean event class and has "
                    "no counterpart elsewhere in this command",),
     "instruments": ("XBRUSD", "UST10Y", "USDBRL"),
     "controls": (*_CONTROLS, "government fiscal announcements with no CARF opinion"),
     "notes": "the committee, not the government, is the event"},
)

# --------------------------------------------------------------------------- miners
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    {"name": "co_coffee_formula", "domain_ids": ("CO-A", "CO-B"), "kind": "mechanism",
     "entry": "research.countries.co.pack:coffee_reference", "cadence_s": 86400.0,
     "steerable": True,
     "notes": "the published farm-gate equation, checked against its own inputs"},
    {"name": "co_monday_law", "domain_ids": ("CO-J",), "kind": "calendar",
     "entry": "research.countries.co.pack:monday_share", "cadence_s": 86400.0,
     "steerable": False,
     "notes": "the Emiliani law's consequence, measured rather than asserted"},
    {"name": "co_holiday_liquidity", "domain_ids": ("CO-J", "CO-B"), "kind": "calendar",
     "entry": "research.countries.co.pack:is_closed", "cadence_s": 86400.0, "steerable": False,
     "notes": "eighteen holidays a year, most of them Mondays"},
)


def coffee_reference(ice_c_usd_lb: float, differential_usd_lb: float, trm: float, *,
                     load_kg: float = 125.0, yield_factor: float = 0.94) -> dict[str, Any]:
    """The FNC farm-gate reference as an EQUATION, so it can be checked against the published one.

    The published price is per 125kg load of parchment coffee and is derived from the ICE 'C'
    price per pound of green coffee plus the Colombian mild differential, converted at the TRM and
    adjusted for the parchment-to-green yield. The constants here are DECLARED rather than fitted:
    this function exists so a miner can ask whether the published number matches its own stated
    formula, and a persistent residual is either a differential this desk has mis-stated or an
    administration that is not doing what it says. Both are findings.
    """
    if trm <= 0 or load_kg <= 0:
        return {"outcome": "UNMEASURED", "price": None,
                "why": "the reference needs a positive TRM and load size"}
    pounds_green = load_kg * yield_factor * 2.20462
    price_cop = (float(ice_c_usd_lb) + float(differential_usd_lb)) * pounds_green * float(trm)
    return {"outcome": "ok", "price_cop_per_load": price_cop,
            "inputs": {"ice_c_usd_lb": ice_c_usd_lb, "differential_usd_lb": differential_usd_lb,
                       "trm": trm, "load_kg": load_kg, "yield_factor": yield_factor},
            "rule": "the constants are DECLARED, not fitted; a persistent residual against the "
                    "published price is either a mis-stated differential or a discretionary "
                    "administration, and both are findings rather than noise"}


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
    """Every seed in both vocabularies, DERIVED keys first so the framework's own aliases cannot
    put the string "1-10 sessions" into a float field."""
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
    {"id": "co_oil_to_brent",
     "source": "ANH production, pipeline interruptions and export volumes",
     "mechanism": "Colombian crude is a third of exports and its supply is interrupted by a "
                  "repeated, dated event class; Brent is the right reference for the grades",
     "targets": ("XBRUSD", "XTIUSD"), "sign": "opposite",
     "horizon": "1-20 sessions", "lag": "0-5 sessions",
     "control": "global supply disruptions of comparable size in the same weeks",
     "evidence": "HYPOTHESIS",
     "notes": "the supply sign is opposite: less Colombian crude, higher world price"},
    {"id": "co_coffee_formula_to_arabica",
     "source": "the FNC published reference and internal purchase volumes",
     "mechanism": "the farm-gate price is an equation in ICE 'C', the mild differential and the "
                  "TRM, so grower SELLING responds to a published number with a known lag",
     "targets": ("COFARA", "COFROB"), "sign": "same",
     "horizon": "5-60 sessions", "lag": "2-10 sessions",
     "control": "robusta, which shares the global price and not the Colombian formula",
     "evidence": "HYPOTHESIS",
     "notes": "the two-business-day TRM lag is structural; a faster response is anticipation"},
    {"id": "co_elnino_to_softs_and_energy",
     "source": "XM reservoir levels and rainfall",
     "mechanism": "one weather state reaches electricity prices and the coffee crop at the same "
                  "time, which makes El Nino a Colombian monetary variable",
     "targets": ("COFARA", "XNGUSD", "XBRUSD"), "sign": "same",
     "horizon": "20-120 sessions", "lag": "10-60 sessions",
     "control": "El Nino episodes in countries with no hydro dependence",
     "evidence": "HYPOTHESIS",
     "notes": "two channels from one shock; separating them is the domain's whole job"},
    {"id": "co_current_account_to_em_stress",
     "source": "the trade balance and the current-account deficit",
     "mechanism": "one of the largest deficits in the region relative to GDP makes Colombia a "
                  "FINANCING story; a global funding squeeze hits it before it hits a surplus "
                  "country",
     "targets": ("USDBRL", "USDMXN", "USDZAR", "US2000"), "sign": "same",
     "horizon": "5-60 sessions", "lag": "1-20 sessions",
     "control": "oil exporters with a current-account surplus",
     "evidence": "HYPOTHESIS",
     "notes": "the financing leg is what separates COP from a pure oil currency"},
    {"id": "co_option_trigger_to_vol",
     "source": "the published 20-day-average deviation threshold",
     "mechanism": "a rule-based intervention with a public trigger should produce a DISCONTINUITY "
                  "in behaviour at the threshold rather than a gradual response",
     "targets": ("XBRUSD", "USDBRL"), "sign": "opposite",
     "horizon": "1-20 sessions", "lag": "0-2 sessions",
     "control": "Chile's pre-announced programmes and Brazil's auction book",
     "evidence": "HYPOTHESIS",
     "notes": "the sharpest identification of an intervention effect available in this command"},
    {"id": "co_rating_to_forced_selling",
     "source": "index-relevant sovereign rating actions and foreign TES holdings",
     "mechanism": "index rules are mechanical, so an eligibility change forces selling of a known "
                  "direction and approximate size",
     "targets": ("XBRUSD", "UST10Y", "USDBRL"), "sign": "same",
     "horizon": "5-60 sessions", "lag": "0-20 sessions",
     "control": "rating actions that did NOT change index eligibility",
     "evidence": "HYPOTHESIS",
     "notes": "forced flow in its purest form: a rule, a date and a direction"},
    {"id": "co_coal_to_gas",
     "source": "Colombian thermal coal exports and European demand",
     "mechanism": "the 2022 European gas crisis shifted coal demand with no Colombian cause, "
                  "which is a clean EXTERNAL shock to the terms of trade",
     "targets": ("XNGUSD", "XBRUSD"), "sign": "same",
     "horizon": "20-120 sessions", "lag": "5-40 sessions",
     "control": "the same window for coal exporters with no European exposure",
     "evidence": "HYPOTHESIS",
     "notes": "no coal instrument is quoted here; gas carries the power-fuel substitution and the "
              "substitution is declared"},
    {"id": "co_gold_informal_to_bop",
     "source": "the discrepancy between reported gold production and reported exports",
     "mechanism": "informal production is gold-price elastic and monetises through informal "
                  "dollar channels, appearing as an unexplained balance-of-payments residual",
     "targets": ("XAUUSD", "XBRUSD"), "sign": "same",
     "horizon": "20-250 sessions", "lag": "10-60 sessions",
     "control": "the same discrepancy in a country with no informal mining",
     "evidence": "HYPOTHESIS",
     "notes": "the observable is an inconsistency between two official series, not either one"},
    {"id": "co_remesas_size_test",
     "source": "the Colombian remittance series against the Mexican one",
     "mechanism": "the same counter-cyclical mechanism at an order of magnitude smaller size; if "
                  "the effect scales, the mechanism is real, and if it does not, it is Mexican",
     "targets": ("USDMXN", "US500"), "sign": "opposite",
     "horizon": "5-60 sessions", "lag": "1-20 sessions",
     "control": "the Mexican remittance channel over the same months",
     "evidence": "HYPOTHESIS",
     "notes": "the cheapest external-validity test in this command"},
    {"id": "co_carf_to_risk_premium",
     "source": "CARF opinions and the fiscal rule's path",
     "mechanism": "an independent committee publicly disagreeing with the government is a dated "
                  "institutional risk event with no counterpart elsewhere here",
     "targets": ("XBRUSD", "USDBRL", "UST10Y"), "sign": "same",
     "horizon": "1-20 sessions", "lag": "0-5 sessions",
     "control": "government fiscal announcements with no CARF opinion attached",
     "evidence": "HYPOTHESIS",
     "notes": "the committee is the event, not the government"},
)

TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = _dual(_EDGE_ROWS)


# --------------------------------------------------------------------------- eras
_ERA_ROWS: tuple[dict[str, Any], ...] = (
    {"id": "co_option_mechanism", "start": "1999-09-25", "end": None,
     "label": "The float with a rule-based option intervention mechanism",
     "what_changed": "Colombia floated and adopted a volatility-control mechanism with a "
                     "PUBLISHED deviation trigger rather than discretionary intervention",
     "invalidates": "pre-1999 FX studies describe a crawling band and transfer to nothing after"},
    {"id": "co_oil_boom_bust", "start": "2014-07-01", "end": "2016-02-29",
     "label": "The oil collapse and the current-account shock",
     "what_changed": "crude halved, the current-account deficit reached a record, and the peso "
                     "depreciated more than any major EM currency",
     "invalidates": "an oil-to-FX elasticity fitted outside this window understates the tail; "
                    "fitted inside it, it overstates the typical case"},
    {"id": "co_downgrade_2021", "start": "2021-05-19", "end": "2021-07-31",
     "label": "The loss of investment grade and index-driven forced selling",
     "what_changed": "sovereign downgrades removed index eligibility and forced mechanical "
                     "selling of local debt by mandate-constrained holders",
     "invalidates": "foreign-holdings estimates that pool this window with discretionary flows "
                    "are averaging a forced sale with a decision"},
    {"id": "co_european_coal_shift", "start": "2022-03-01", "end": "2023-06-30",
     "label": "The European gas crisis and the thermal-coal demand shift",
     "what_changed": "European utilities bid for Colombian thermal coal at prices with no "
                     "Colombian cause, a clean external terms-of-trade shock",
     "invalidates": "a terms-of-trade estimate fitted here is fitted on an exogenous demand shock "
                    "and does not describe the normal supply-driven case"},
    {"id": "co_pension_reform_debate", "start": "2023-01-01", "end": None,
     "label": "The pension reform and the institutional flow's regime risk",
     "what_changed": "the destination of a large, regular institutional flow became a legislative "
                     "question with dated milestones",
     "invalidates": "AFP-flow estimates from before the debate assume a stable mandate that is "
                    "now itself the variable"},
    {"id": "co_fiscal_rule_carf", "start": "2021-09-14", "end": None,
     "label": "The reformed fiscal rule and the independent CARF",
     "what_changed": "an independent committee was created with a mandate to opine publicly on "
                     "compliance, creating a dated institutional event class",
     "invalidates": "fiscal-risk event studies from before the committee have no comparable "
                    "event to date on"},
)

POLICY_ERAS: tuple[dict[str, Any], ...] = _named_eras(_ERA_ROWS)


# --------------------------------------------------------------------------- access constraints
ACCESS_CONSTRAINTS: tuple[dict[str, Any], ...] = (
    {"constraint": "USDCOP, the COLCAP and the TES curve are all absent from this broker",
     "measured": "universe.json holds USDBRL and USDMXN and no other LatAm currency",
     "consequence": "this pack is TRANSMISSION-ONLY. Every mechanism names its carrier and the "
                    "basis the substitution costs; no cell here claims to trade a Colombian asset"},
    {"constraint": "no thermal coal instrument is quoted",
     "measured": "the energy rows of universe.json are XTIUSD, XBRUSD and XNGUSD",
     "consequence": "the coal channel routes through XNGUSD as the European power-fuel "
                    "substitution, and the substitution is stated as a cost rather than assumed"},
    {"constraint": "the BanRep decision calendar in this pack is DERIVED, not published",
     "measured": "the dates here follow the board's last-Friday cadence and were not copied from "
                 "the published calendar",
     "consequence": "every Colombian central-bank event study is PROVISIONAL until the published "
                    "calendar replaces these dates; a null on a derived calendar is a statement "
                    "about the dating and not about the mechanism"},
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

MISSION = ("mine Colombia for the mechanisms that are PUBLISHED rather than estimated: a "
           "farm-gate price that is an equation in the exchange rate, an intervention rule with "
           "a numeric trigger, a supply-interruption class with an n, and a weather state that "
           "reaches the central bank through two channels at once -- all expressed in crude, "
           "arabica and the EM peers, because no Colombian instrument trades here")


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
