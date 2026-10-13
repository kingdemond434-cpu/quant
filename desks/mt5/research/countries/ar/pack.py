"""ARGENTINA: four exchange rates at once, and a soybean supply that answers to a tax rate.

WHY ARGENTINA EARNS A PACK IN A UNIVERSE THAT CANNOT TRADE ITS CURRENCY. Three mechanisms, none
of which exists anywhere else in the desk's book:

  1. THE BRECHA IS A PUBLISHED, DAILY, FREE MEASUREMENT OF HOW BINDING A CAPITAL CONTROL IS.
     Argentina quotes an official wholesale rate (BCRA Comunicacion "A" 3500) and three parallel
     rates simultaneously -- blue (informal cash), MEP (bought by buying a bond in pesos and
     selling it in dollars onshore) and contado con liqui (the same trade settled offshore). The
     ratio of parallel to official has ranged from near zero to above 160% inside this sample.
     Capital-control intensity is normally a dummy variable in a cross-country panel; here it is
     a continuous daily series, and a continuous daily series of a variable everyone else proxies
     with a dummy is worth more than most price data.

  2. THE MEP-CCL SPREAD IS A PRICED MEASURE OF THE COST OF GETTING MONEY OUT. Both legs are the
     same bond trade; the only difference is where the dollars settle. The spread between them is
     therefore the pure price of cross-border settlement under a control regime, stripped of the
     peso's level entirely. When it widens, capital flight is being rationed rather than merely
     taxed.

  3. SOYBEAN SUPPLY IS SET BY A TAX RATE AND AN FX WINDOW, NOT BY AGRONOMY. Argentina is the
     world's largest exporter of soybean meal and oil. Its farmers store beans as an inflation
     hedge and sell when the effective export price improves -- which happens when retenciones
     are cut or when the government opens a preferential "dolar soja" window. Those are DATED
     POLICY ANNOUNCEMENTS that move world supply within days. No other agricultural exporter's
     shipment timing is this policy-driven, and the events are public and datable.

WHAT IS EXECUTABLE: NOTHING ARGENTINE. `OWN_PRICE` is empty. USDARS is not in this broker's
registry, nor is the Merval, nor are the AL30 and GD30 bonds the MEP and CCL trades are built
from. Every mechanism here is TRANSMISSION-ONLY and names its carrier: the soy complex, the EM
peer currencies, gold, and crude for the Vaca Muerta leg. A pack that let "Argentina" quietly
mean "USDBRL" would be laundering an unmeasured basis into a measured edge.

WHAT THIS PACK MUST NOT DO. Argentine official statistics have a documented period of political
interference (the INDEC intervention of 2007-2015, during which published inflation was
implausible and private estimates were legally suppressed). Every INDEC series in this pack
therefore carries an era boundary at 2016-01, and any study pooling across it is measuring a
change in the MEASUREMENT rather than in the economy. That is not a caveat, it is the reason the
era table exists.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------- identity
CODE = "ar"
NAME = "Argentina"
REGION_COMMAND = "latam"
REGION_DESK = "SOUTH_AMERICA"
CURRENCY = "ARS"
NATIVE_LANGUAGES: tuple[str, ...] = ("es-AR",)
FISCAL_YEAR_END = "12-31"

#: EMPTY. USDARS is absent from this broker's registry and so is every Argentine asset.
OWN_PRICE: tuple[str, ...] = ()

EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "SOYBEAN", "CORN", "WHEAT", "SUGAR",        # the export book, and the world's meal supply
    "USDBRL", "USDMXN", "USDZAR", "USDTRY",     # the EM-stress peers the brecha is a sensor for
    "XAUUSD", "XAGUSD",                         # the store-of-value leg a control regime creates
    "XTIUSD", "XBRUSD", "XNGUSD",               # Vaca Muerta and the energy-import swing
    "XCUUSD",                                   # lithium and mining are the next export cycle
    "US500", "US2000", "USDX", "UST10Y",        # the global risk, dollar and duration factors
    "EURUSD",                                   # the dollar-factor control
)

COT_CURRENCY = ""
COT_STATUS = ("There is no CME peso contract of consequence and no ARS row in the desk's "
              "cot.json axis. The tradable positioning that matters for this pack is the SOYBEAN "
              "and CORN speculative net, both of which the axis DOES carry -- so Argentine "
              "positioning is read in the crop the country exports, not in the currency it "
              "cannot sell.")

TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "USD/ARS official wholesale (A3500) and the three parallel rates",
     "venue": "BCRA / interbank / informal / bond market",
     "why": "the brecha between them is this pack's central state variable; none of the four legs "
            "is quotable here",
     "proxies": ("USDBRL", "USDMXN", "XAUUSD", "SOYBEAN"),
     "basis_cost": "no carrier reproduces a controlled currency. The brecha is used as a STATE to "
                   "condition other instruments on, never as something to trade"},
    {"name": "AL30 and GD30 sovereign bonds (the MEP and CCL legs)", "venue": "BYMA / MAE",
     "why": "MEP and CCL are executed by buying a bond in pesos and selling it in dollars; the "
            "bond pair IS the mechanism",
     "proxies": ("USDBRL", "US2000"),
     "basis_cost": "a distressed sovereign bond's own credit move contaminates the implied FX "
                   "rate, which is why MEP and CCL disagree with each other and with the blue"},
    {"name": "S&P Merval and the Argentine ADR complex", "venue": "BYMA / NYSE",
     "why": "the local risk asset and the second CCL route",
     "proxies": ("US2000", "USDBRL"),
     "basis_cost": "the Merval in pesos is an inflation index as much as an equity index; in CCL "
                   "dollars it is a different series entirely, and the two must never be mixed"},
    {"name": "Rosario (ROFEX/MATba) soybean, corn and wheat contracts", "venue": "Matba Rofex",
     "why": "the domestic crop price net of retenciones -- the number the farmer actually "
            "responds to, which the Chicago price is not",
     "proxies": ("SOYBEAN", "CORN", "WHEAT"),
     "basis_cost": "Chicago is the world price and Rosario is the world price minus the export "
                   "tax minus the FX distortion; the GAP is the Argentine policy variable"},
    {"name": "BCRA international reserves, gross and NET", "venue": "BCRA",
     "why": "gross reserves include swap lines and bank dollar deposits; the NET figure is the "
            "solvency variable and it has been negative in this sample",
     "proxies": ("USDBRL", "USDTRY", "XAUUSD"),
     "basis_cost": "none; data rather than an instrument, and the gross/net distinction is the "
                   "entire content of the series"},
    {"name": "Retenciones schedule and the dolar soja / dolar agro windows", "venue": "Ministerio "
                                                                                     "de Economia",
     "why": "the policy variables that set the TIMING of world soybean meal supply",
     "proxies": ("SOYBEAN", "CORN"),
     "basis_cost": "none; these are dated announcements and the mechanism is their effect on "
                   "shipment timing"},
)

# --------------------------------------------------------------------------- central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "Banco Central de la Republica Argentina",
    "short": "BCRA",
    "framework": "managed_float",
    "committee": "Directorio -- the President of the BCRA and the board; decisions are taken by "
                 "RESOLUTION and communicated as a Comunicado, not by a scheduled committee vote",
    "policy_rate": "tasa de politica monetaria. The INSTRUMENT has changed repeatedly: LEBAC, "
                   "then LELIQ, then pases pasivos, then LEFI. A single 'policy rate' series "
                   "across this sample is four different instruments wearing one label.",
    "meetings_per_year": 0,
    "schedule_rule": (
        "THERE IS NO PUBLISHED DECISION CALENDAR, and that absence is the mechanism rather than "
        "a gap in this pack. The BCRA changes the rate by board resolution whenever it chooses, "
        "announces it in a Comunicado (often on a Thursday after the close), and gives no "
        "advance notice. So Argentina has NO scheduled-event class at all: every rate change is "
        "an unscheduled event, which makes it the natural control group for every scheduled "
        "central-bank event study in this command. A country with no calendar is not a country "
        "with missing data -- it is the comparison case."),
    "announce_local": "unscheduled; typically after the 17:00 Buenos Aires close",
    "announce_utc": "20:00", "announce_utc_dst": "20:00",
    "dst_rule": "ARGENTINA HAS NO DST. America/Argentina/Buenos_Aires is UTC-3 all year, so every "
                "Argentine UTC time in this pack is fixed while the broker's clock still shifts.",
    "inflation_target": "NONE in the current framework. The BCRA has run a monetary-aggregate "
                        "and exchange-rate-anchor framework rather than an inflation target "
                        "since 2019; the 2016-2018 inflation-targeting episode is its own era.",
    "fx_operations": (
        "The regime has changed four times inside this sample: hard cepo with a crawling peg "
        "(2019-09 to 2023-12), the December 2023 step devaluation followed by a 2% monthly crawl, "
        "a 1% crawl from 2024-12, and a BAND regime from 2025-04 in which the official rate "
        "floats between announced limits that themselves crawl. Under every one of them the "
        "parallel rates continued to quote publicly, which is what makes the brecha measurable "
        "across regime changes rather than only within one."),
    "policy_rate_series": "BCRA estadisticas monetarias -- tasa de politica monetaria",
    "expected_rate_series": "BCRA Relevamiento de Expectativas de Mercado (REM), monthly, "
                            "published around the 7th for the previous month's survey",
    "decision_dates": (),
    "decision_dates_status": ("EMPTY AND CORRECT. There is no published calendar to tabulate. "
                              "An event study here builds its own dated list from the "
                              "Comunicados, and that list is of UNSCHEDULED events by "
                              "construction."),
    "root": "https://www.bcra.gob.ar",
}

# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "Tipo de Cambio de Referencia -- Comunicacion A 3500 (mayorista)",
     "publisher": "BCRA",
     "definition": "a survey-based wholesale reference rate: the BCRA polls a panel of entities "
                   "in Buenos Aires and CABA and publishes a transaction-weighted reference for "
                   "the day. It is the legal reference for export settlement and for most "
                   "contracts.",
     "windows_local": ("10:00-15:00",), "windows_utc": ("13:00-18:00",),
     "published_local": "about 16:00 America/Argentina/Buenos_Aires",
     "published_utc": "19:00", "published_utc_dst": "19:00",
     "dst_rule": "none -- Argentina is UTC-3 year round",
     "instruments": (),
     "why_it_matters": "A3500 is the OFFICIAL leg of the brecha. Every gap measured in this pack "
                       "is measured against this number and not against a retail board rate.",
     "trap": "A3500 is the WHOLESALE rate. The retail 'dolar oficial' quoted by banks carries "
             "taxes and perceptions that have reached 65% on top, and the two are routinely "
             "confused in public data. A brecha computed against a retail rate is a different "
             "and much smaller number."},
    {"name": "Dolar blue (informal cash)", "publisher": "public trackers (ambito, dolarhoy)",
     "definition": "the informal street rate for physical dollars, surveyed by financial media "
                   "and published continuously through the day",
     "windows_local": ("11:00-17:00",), "windows_utc": ("14:00-20:00",),
     "published_local": "continuous", "published_utc": "continuous", "dst_rule": "none",
     "instruments": (),
     "why_it_matters": "the purest measure of retail demand for dollars under rationing; it "
                       "responds to CASH demand, so it carries a seasonal (the December aguinaldo "
                       "and the January holiday season) the financial rates do not",
     "trap": "it is a SURVEY of an informal market, not a transaction print. Different trackers "
             "disagree by a percent or more and the series must be sourced consistently"},
    {"name": "Dolar MEP (Mercado Electronico de Pagos, onshore bond route)",
     "publisher": "implicit, from bond prices",
     "definition": "buy a sovereign bond in pesos, sell the same bond in dollars for LOCAL "
                   "settlement; the implied rate is the MEP",
     "windows_local": ("11:00-17:00",), "windows_utc": ("14:00-20:00",),
     "published_local": "continuous", "published_utc": "continuous", "dst_rule": "none",
     "instruments": (),
     "why_it_matters": "a LEGAL route out of pesos for onshore dollars; its gap to the official "
                       "rate is the taxed cost of leaving the peso without leaving the country",
     "trap": "the implied rate contains the bond's own credit move; a sovereign spread widening "
             "moves MEP without any FX event at all"},
    {"name": "Contado con liquidacion (CCL, offshore settlement)",
     "publisher": "implicit, from bond and ADR prices",
     "definition": "the same bond trade with the dollar leg settled OFFSHORE; it is the price of "
                   "getting money out of the country, not merely out of the currency",
     "windows_local": ("11:00-17:00",), "windows_utc": ("14:00-20:00",),
     "published_local": "continuous", "published_utc": "continuous", "dst_rule": "none",
     "instruments": (),
     "why_it_matters": "THE MEP-CCL SPREAD IS THE PRICE OF CROSS-BORDER SETTLEMENT UNDER A "
                       "CONTROL REGIME, with the peso's level divided out on both legs. It is the "
                       "single cleanest capital-flight measurement this desk can obtain anywhere.",
     "trap": "the ADR route and the bond route give slightly different CCLs and the cheaper one "
             "is the real one; a single published series may be either"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "Export settlement obligation (liquidacion de divisas)", "kind": "day_of_month",
     "rule": "Exporters must settle foreign-currency proceeds through the official market within "
             "a deadline set by decree, at the A3500 rate. The deadline and the share settled "
             "officially versus through a blend have both been policy variables. This is the "
             "mechanism that makes the brecha a TAX on exporters rather than an inconvenience.",
     "days": (1, 15), "roll": "following",
     "window_utc": ("13:00", "19:00"), "instruments": ("SOYBEAN", "CORN")},
    {"name": "Dolar soja / dolar agro preferential windows", "kind": "day_of_month",
     "rule": "Time-limited windows in which soy exporters settle at a preferential rate or at a "
             "blend of official and CCL. Each window has an announced start, an announced end and "
             "an announced target volume, and each produced a measurable BURST of shipments "
             "followed by a lull -- a dated supply shock with a published size.",
     "days": (1,), "roll": "following",
     "window_utc": ("13:00", "19:00"), "instruments": ("SOYBEAN", "CORN")},
    {"name": "Crawling peg and the band", "kind": "weekday",
     "rule": "From 2023-12 the official rate crawled 2% monthly, from 2024-12 1% monthly, and "
             "from 2025-04 it floats inside announced bands that themselves crawl. The crawl is a "
             "DAILY administered move: the official rate's own volatility is near zero by "
             "construction and any volatility model fitted to it is modelling a policy rule.",
     "weekday": -1, "roll": "none",
     "window_utc": ("13:00", "19:00"), "instruments": ()},
    {"name": "BCRA reserve reporting", "kind": "weekday",
     "rule": "Gross reserves are published daily with a one-day lag. NET reserves -- gross less "
             "swap lines, bank dollar deposits (encajes) and other liabilities -- are not an "
             "official series and are estimated by analysts, which means the headline number and "
             "the solvency number can move in opposite directions on the same day.",
     "weekday": -1, "roll": "none",
     "window_utc": ("13:00", "22:00"), "instruments": ("USDBRL", "XAUUSD")},
)

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "BYMA (Bolsas y Mercados Argentinos)", "index_symbols": (),
     "index_symbols_absent": ("MERVAL",),
     "hours_local": "11:00-17:00 cash equities and bonds",
     "hours_utc": "14:00-20:00",
     "expiry_rule": "index and single-stock options expire on the third Friday of even months; "
                    "the market is small enough that expiry is not the dominant flow and no "
                    "expiry domain is claimed here",
     "notes": "the MEP and CCL routes execute HERE, which is why a bond-market disruption is an "
              "FX event in Argentina and nowhere else"},
    {"name": "Matba Rofex (Rosario)", "index_symbols": (), "index_symbols_absent": ("ROFEX DLR",),
     "hours_local": "agricultural and FX futures, roughly 10:00-17:00",
     "hours_utc": "13:00-20:00",
     "expiry_rule": "the ROFEX dollar future settles to the A3500 of the last business day of the "
                    "contract month -- so the future is a bet on the ADMINISTERED rate, and its "
                    "implied yield is the market's estimate of the next devaluation step",
     "notes": "the implied ROFEX curve is the best available forward-looking measure of "
              "devaluation expectations and it is not on this box"},
    {"name": "MAE (Mercado Abierto Electronico)", "index_symbols": (), "index_symbols_absent": (),
     "hours_local": "10:00-15:00 for the wholesale FX segment",
     "hours_utc": "13:00-18:00",
     "expiry_rule": "not applicable",
     "notes": "the wholesale FX venue A3500 is surveyed from; the BCRA intervenes here"},
)

# --------------------------------------------------------------------------- holidays
_AR_HOLIDAYS: dict[int, dict[str, str]] = {
    2024: {
        "2024-01-01": "Ano Nuevo", "2024-02-12": "Carnaval", "2024-02-13": "Carnaval",
        "2024-03-24": "Dia Nacional de la Memoria por la Verdad y la Justicia",
        "2024-03-29": "Viernes Santo", "2024-04-02": "Dia del Veterano y de los Caidos en "
                                                     "Malvinas",
        "2024-05-01": "Dia del Trabajador", "2024-05-25": "Dia de la Revolucion de Mayo",
        "2024-06-17": "Paso a la Inmortalidad del General Guemes",
        "2024-06-20": "Paso a la Inmortalidad del General Belgrano",
        "2024-07-09": "Dia de la Independencia",
        "2024-08-19": "Paso a la Inmortalidad del General San Martin (trasladado)",
        "2024-10-12": "Dia del Respeto a la Diversidad Cultural",
        "2024-11-18": "Dia de la Soberania Nacional (trasladado)",
        "2024-12-08": "Inmaculada Concepcion de Maria", "2024-12-25": "Navidad",
    },
    2025: {
        "2025-01-01": "Ano Nuevo", "2025-03-03": "Carnaval", "2025-03-04": "Carnaval",
        "2025-03-24": "Dia Nacional de la Memoria por la Verdad y la Justicia",
        "2025-04-02": "Dia del Veterano y de los Caidos en Malvinas",
        "2025-04-18": "Viernes Santo", "2025-05-01": "Dia del Trabajador",
        "2025-05-25": "Dia de la Revolucion de Mayo",
        "2025-06-16": "Paso a la Inmortalidad del General Guemes (trasladado)",
        "2025-06-20": "Paso a la Inmortalidad del General Belgrano",
        "2025-07-09": "Dia de la Independencia",
        "2025-08-18": "Paso a la Inmortalidad del General San Martin (trasladado)",
        "2025-10-13": "Dia del Respeto a la Diversidad Cultural (trasladado)",
        "2025-11-24": "Dia de la Soberania Nacional (trasladado)",
        "2025-12-08": "Inmaculada Concepcion de Maria", "2025-12-25": "Navidad",
    },
    2026: {
        "2026-01-01": "Ano Nuevo", "2026-02-16": "Carnaval", "2026-02-17": "Carnaval",
        "2026-03-24": "Dia Nacional de la Memoria por la Verdad y la Justicia",
        "2026-04-02": "Dia del Veterano y de los Caidos en Malvinas",
        "2026-04-03": "Viernes Santo", "2026-05-01": "Dia del Trabajador",
        "2026-05-25": "Dia de la Revolucion de Mayo",
        "2026-06-15": "Paso a la Inmortalidad del General Guemes (trasladado)",
        "2026-06-20": "Paso a la Inmortalidad del General Belgrano",
        "2026-07-09": "Dia de la Independencia",
        "2026-08-17": "Paso a la Inmortalidad del General San Martin",
        "2026-10-12": "Dia del Respeto a la Diversidad Cultural",
        "2026-11-23": "Dia de la Soberania Nacional (trasladado)",
        "2026-12-08": "Inmaculada Concepcion de Maria", "2026-12-25": "Navidad",
    },
}

HOLIDAYS_RULE: dict[str, Any] = {
    "rule": (
        "Ley 27.399 fixes the Argentine feriados in three classes and the classes behave "
        "differently, which is why this table cannot be computed from a weekday rule. "
        "INAMOVIBLES (1 January, Carnaval Monday and Tuesday, 24 March, 2 April, 1 May, 25 May, "
        "20 June, 9 July, 8 December, 25 December, and Viernes Santo) never move. TRASLADABLES "
        "(17 June Guemes, 17 August San Martin, 12 October Diversidad Cultural, 20 November "
        "Soberania) move to the preceding Monday when they fall on a Tuesday or Wednesday and to "
        "the following Monday when they fall on a Thursday or Friday. On top of both, the "
        "executive declares FERIADOS CON FINES TURISTICOS by decree each year -- up to three "
        "bridge days that are NOT predictable from any rule and that DO close the bank and FX "
        "markets. Carnaval is Easter-48 and Easter-47 and Viernes Santo is Easter-2. Jueves Santo "
        "is a DIA NO LABORABLE, not a feriado: banks may close while the exchange trades, and "
        "treating it as a closure creates a phantom gap. Weekends are Saturday and Sunday."),
    "table": _AR_HOLIDAYS,
    "years": (2024, 2025, 2026),
    "status": {2024: "CONFIRMED for the statutory days; the tourism bridge days of that year are "
                     "NOT in this table and must be taken from the decree",
               2025: "CONFIRMED for the statutory days, same caveat",
               2026: "DERIVED from Ley 27.399 plus the tabulated Easter; the bridge days are "
                     "unknowable until the decree is published"},
    "weekly_closed": (5, 6),
    "note": "the FX and bond markets follow the BANK calendar (BCRA), which adds days the "
            "exchange calendar does not; when the two disagree the brecha series has a hole in "
            "one leg and not the other, and that hole must not be interpolated",
}


def holidays(year: int) -> dict[str, str]:
    """The statutory closure table for one year; `{}` for a year this pack does not declare."""
    return dict(_AR_HOLIDAYS.get(year) or {})


def is_closed(day: date) -> bool:
    """True when the Argentine market is closed by the statutory table (weekends included).

    BRIDGE DAYS ARE NOT IN HERE and cannot be: they are declared by decree each year. A caller
    that needs certainty for a specific date must read the decree, and this function returning
    False is not a claim that the market was open.
    """
    return day.weekday() >= 5 or day.isoformat() in holidays(day.year)


# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "CFTC Commitments of Traders -- CBOT soybeans and corn",
     "publisher": "CFTC", "frequency": "weekly", "lag": "Friday 15:30 ET for Tuesday positions",
     "field": "non-commercial net, open interest",
     "why": "the tradable positioning for Argentine policy shocks is in the CROP, not the "
            "currency, and the desk's cot.json axis already maps SOYBEAN and CORN",
     "pit": True, "status": "AVAILABLE on this box"},
    {"name": "BCRA reserve series, gross and estimated net",
     "publisher": "BCRA (gross) / analysts (net)", "frequency": "daily",
     "lag": "one business day",
     "field": "gross international reserves; net is an ESTIMATE and not an official series",
     "why": "the solvency variable behind every devaluation-risk claim here",
     "pit": True,
     "status": "gross is fetchable from the BCRA API; NET is an estimate and is declared as one, "
               "never presented as published data"},
    {"name": "Grain export registrations (DJVE) and shipment declarations",
     "publisher": "Ministerio de Economia / Agricultura", "frequency": "weekly",
     "lag": "one week", "field": "declared export volume by crop",
     "why": "the DJVE registration is how a dolar-soja window's effect becomes VISIBLE within "
            "days rather than months -- it is the earliest hard read on the supply burst",
     "pit": True, "status": "declared; not collected on this box"},
    {"name": "Bond-implied MEP and CCL from public trackers",
     "publisher": "ambito.com, dolarhoy, dolarapi and similar", "frequency": "continuous",
     "lag": "none", "field": "implied rate per route",
     "why": "the parallel legs of the brecha; they are the only continuous public measurement of "
            "control intensity",
     "pit": True,
     "status": "trackers differ by up to a percent; the lane pins ONE source per leg and records "
               "which, because a series stitched from several trackers has jumps that are "
               "sourcing artefacts and look exactly like regime changes"},
)

# --------------------------------------------------------------------------- terminology
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "fx_regime": ("cepo", "cepo cambiario", "brecha", "brecha cambiaria", "dolar oficial",
                  "dolar mayorista", "A3500", "Comunicacion A 3500", "dolar blue", "dolar MEP",
                  "dolar bolsa", "contado con liqui", "CCL", "liqui", "dolar tarjeta",
                  "dolar solidario", "impuesto PAIS", "percepcion", "crawling peg",
                  "banda cambiaria", "devaluacion", "salto devaluatorio", "desdoblamiento",
                  "rulo", "puré", "canje MEP-CCL"),
    "policy": ("BCRA", "Banco Central", "tasa de politica monetaria", "LELIQ", "LEBAC", "pases",
               "LEFI", "REM", "Relevamiento de Expectativas de Mercado", "emision monetaria",
               "base monetaria", "deficit fiscal", "superavit financiero", "motosierra",
               "licuadora", "blanqueo", "acuerdo con el FMI", "FMI", "reservas netas",
               "reservas brutas", "encajes"),
    "agro": ("soja", "poroto de soja", "harina de soja", "aceite de soja", "maiz", "trigo",
             "retenciones", "derechos de exportacion", "dolar soja", "dolar agro",
             "liquidacion del agro", "DJVE", "campana", "cosecha gruesa", "cosecha fina",
             "siembra", "Rosario", "Bolsa de Cereales", "BCR", "silobolsa", "acopio",
             "sequia", "La Nina", "Nina", "exportador de aceite"),
    "market": ("Merval", "BYMA", "AL30", "GD30", "bonos en dolares", "riesgo pais",
               "acciones argentinas", "ADR", "Matba Rofex", "ROFEX", "futuro de dolar",
               "tasa implicita", "carry en pesos", "plazo fijo", "UVA"),
    "inflation": ("INDEC", "IPC", "inflacion mensual", "inflacion interanual", "indexacion",
                  "UVA", "CER", "ajuste por inflacion", "paritarias", "salario real",
                  "canasta basica", "pobreza"),
    "energy": ("Vaca Muerta", "shale", "YPF", "gasoducto", "Nestor Kirchner",
               "balanza energetica", "importacion de gas", "subsidios energeticos", "tarifas"),
    "community": ("Ambito Financiero", "El Cronista", "Infobae Economia", "La Nacion Economia",
                  "Rankia Argentina", "Bolsar", "IOL invertironline", "Rava",
                  "analista financiero", "consultora economica"),
}

# --------------------------------------------------------------------------- source classes
#: THE TEN LAYERS (principal's per-country depth rule, 2026-09-17). A country is never "covered"
#: by five obvious sources: the official statistics everyone quotes are ONE layer of ten, and the
#: layers that actually differentiate a country -- its retail ecology, its app ecosystem, its
#: physical economy, and the citation graph that finds the next source -- are the ones a lazy
#: pack omits. A layer with no source must be NAMED ABSENT WITH A REASON in `LAYER_ABSENCES`;
#: blank is never an answer (L1.28a).
SOURCE_LAYERS: tuple[str, ...] = (
    "official", "institutional", "academic", "practitioner", "retail_ecology", "app_ecosystem",
    "media", "archive", "physical_economy", "source_graph")

#: Three INDEPENDENT labels per source. Independent on purpose: a PUBLIC source can be FRINGE and
#: still PREDICTIVE, and an AUTHORITATIVE one can be NOT_PREDICTIVE. Collapsing them into one
#: "quality" score is how a desk throws away the fringe material that turns out to work, and how
#: it lends authority to an official series that has never predicted anything.
ACCESS_LABELS: tuple[str, ...] = (
    "PUBLIC", "PUBLIC_WITH_TERMS", "LICENSED", "OPEN_DATA", "PUBLIC_ARCHIVE", "PUBLIC_SOCIAL",
    "USER_SUBMITTED", "ACCESS_UNCLEAR", "PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")
CREDIBILITY: tuple[str, ...] = ("AUTHORITATIVE", "RELIABLE", "UNRELIABLE", "FRINGE",
                                "CONTRADICTED", "UNKNOWN")
PREDICTIVE_STATES: tuple[str, ...] = ("UNTESTED", "PREDICTIVE", "NOT_PREDICTIVE",
                                      "NARRATIVE_FEATURE")
SOURCE_CLASSES: tuple[dict[str, Any], ...] = (
    {"id": "ar_bcra_api", "layer": "official",
     "label": "BCRA public APIs (estadisticas monetarias y cambiarias)",
     "roots": ("https://api.bcra.gob.ar/estadisticas/v3.0/monetarias",
               "https://api.bcra.gob.ar/estadisticascambiarias/v1.0/Cotizaciones",
               "https://www.bcra.gob.ar/PublicacionesEstadisticas/"),
     "languages": ("es-AR",), "licence": "public, no key; JSON {status, results:[...]}",
     "access_label": "OPEN_DATA", "credibility": "AUTHORITATIVE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("tipo de cambio de referencia comunicacion A 3500 serie",
                 "reservas internacionales brutas serie diaria",
                 "pasivos remunerados del BCRA stock",
                 "comunicado del BCRA tasa de politica monetaria"),
     "notes": "the OFFICIAL leg of every brecha in this pack. The variable LIST is itself an "
              "endpoint, so the ids are discoverable rather than guessed"},
    {"id": "ar_indec", "layer": "official",
     "label": "INDEC national statistics and the datos.gob.ar series API",
     "roots": ("https://www.indec.gob.ar/", "https://apis.datos.gob.ar/series/api/"),
     "languages": ("es-AR",), "licence": "public open data; unauthenticated JSON/CSV",
     "access_label": "OPEN_DATA", "credibility": "AUTHORITATIVE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("IPC nacional variacion mensual INDEC",
                 "intercambio comercial argentino ICA mensual",
                 "estimador mensual de actividad economica EMAE"),
     "notes": "CARRIES AN ERA BOUNDARY AT 2016-01. The 2007-2015 intervention makes earlier "
              "inflation a measurement of politics rather than of prices, and the pack refuses "
              "to serve that history rather than serving it with a footnote"},
    {"id": "ar_economia_boletin", "layer": "official",
     "label": "Ministerio de Economia, MAGyP and the Boletin Oficial",
     "roots": ("https://www.argentina.gob.ar/economia", "https://www.boletinoficial.gob.ar/",
               "https://datos.magyp.gob.ar/",
               "https://www.magyp.gob.ar/sitio/areas/estimaciones/"),
     "languages": ("es-AR",), "licence": "public open data and the official gazette",
     "access_label": "OPEN_DATA", "credibility": "AUTHORITATIVE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("decreto derechos de exportacion soja alicuota",
                 "programa de incremento exportador dolar soja resolucion",
                 "declaraciones juradas de venta al exterior DJVE trigo maiz",
                 "estimaciones agricolas siembra cosecha"),
     "notes": "THE BOLETIN OFICIAL IS THE PRIMARY DATE for every policy event in AR-D. A press "
              "report of the same decree can be a day early and dating the event to it puts the "
              "whole event study in the wrong session"},
    {"id": "ar_byma_rofex_cnv", "layer": "institutional",
     "label": "BYMA, Matba Rofex, MAE and the CNV",
     "roots": ("https://www.byma.com.ar/", "https://matbarofex.com.ar/",
               "https://www.mae.com.ar/", "https://www.argentina.gob.ar/cnv"),
     "languages": ("es-AR",),
     "licence": "public summary data; depth and historical tick are licensed",
     "access_label": "PUBLIC_WITH_TERMS", "credibility": "AUTHORITATIVE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("futuro de dolar ROFEX tasa implicita curva",
                 "volumen operado AL30 GD30 especie D y C",
                 "parking plazo de permanencia normativa CNV",
                 "calendario de feriados bursatiles BYMA"),
     "notes": "the MEP and CCL routes EXECUTE here, which is why a bond-market disruption is an "
              "FX event in Argentina and nowhere else. The ROFEX implied curve is the best "
              "forward-looking devaluation measure and it is not on this box"},
    {"id": "ar_bcr_cereales", "layer": "institutional",
     "label": "Bolsa de Comercio de Rosario and Bolsa de Cereales",
     "roots": ("https://www.bcr.com.ar/es/mercados/", "https://www.bolsadecereales.com/",
               "https://www.bcr.com.ar/es/mercados/gea"),
     "languages": ("es-AR",), "licence": "public bulletins and public statistics",
     "access_label": "PUBLIC", "credibility": "AUTHORITATIVE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("guia estrategica para el agro GEA condicion de cultivos",
                 "panorama agricola semanal bolsa de cereales",
                 "precio camara Rosario soja disponible",
                 "molienda de soja mensual"),
     "notes": "the Rosario price NET of retenciones is the number the farmer actually responds "
              "to; Chicago is the world price and the GAP between them is the Argentine policy "
              "variable rather than a basis"},
    {"id": "ar_academic", "layer": "academic",
     "label": "Argentine academic economics (UTDT, UCEMA, UdeSA, AAEP, SciELO)",
     "roots": ("https://www.utdt.edu/ver_contenido.php?id_contenido=1980",
               "https://ucema.edu.ar/publicaciones/doc_trabajo.php",
               "https://www.udesa.edu.ar/departamento-de-economia",
               "https://www.scielo.org.ar/"),
     "languages": ("es-AR", "en"), "licence": "open access working papers and journals",
     "access_label": "PUBLIC", "credibility": "RELIABLE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("relevamiento de expectativas de inflacion UTDT serie",
                 "brecha cambiaria determinantes documento de trabajo",
                 "control de capitales y fuga determinantes Argentina",
                 "pass-through devaluacion precios Argentina estimacion"),
     "notes": "UTDT's inflation-expectations survey is an ACADEMIC series that continued through "
              "the INDEC intervention, which makes it the bridge across the 2016 era boundary "
              "that AR-K is about"},
    {"id": "ar_consultoras", "layer": "practitioner",
     "label": "Argentine consultoras and broker research",
     "roots": ("https://www.ecogo.com.ar/", "https://www.lcgsa.com.ar/",
               "https://www.equilibra.com.ar/", "https://iol.invertironline.com/aprende",
               "https://research.ppi.com.ar/"),
     "languages": ("es-AR",),
     "licence": "public web with terms; claims extracted only, nothing republished",
     "access_label": "PUBLIC_WITH_TERMS", "credibility": "RELIABLE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("reservas netas estimacion consultora hoy",
                 "brecha cambiaria proyeccion informe semanal",
                 "rolleo de deuda en pesos licitacion resultado analisis",
                 "canje MEP CCL conveniencia operatoria"),
     "notes": "NET RESERVES ARE A CONSULTORA ESTIMATE AND NOT AN OFFICIAL SERIES. This layer is "
              "where that number comes from, which is exactly why every net-reserve figure in "
              "this pack is labelled an estimate and reported as a range"},
    {"id": "ar_retail_ecology", "layer": "retail_ecology",
     "label": "Argentine retail investor communities and cueva culture",
     "roots": ("https://www.reddit.com/r/merval/", "https://www.rankia.com.ar/",
               "https://www.reddit.com/r/Argentina/", "https://www.bolsar.info/"),
     "languages": ("es-AR",),
     "licence": "public social; user-submitted content, nothing republished",
     "access_label": "PUBLIC_SOCIAL", "credibility": "UNRELIABLE",
     "predictive_state": "NARRATIVE_FEATURE", "machine_use_allowed": True,
     "queries": ("como hacer el rulo con dolar MEP paso a paso",
                 "conviene comprar dolar blue en la cueva hoy",
                 "pure con bonos AL30 cuanto deja",
                 "plazo fijo UVA o dolar que conviene",
                 "parking de dolar bolsa cuantos dias"),
     "notes": "UNRELIABLE AND IRREPLACEABLE. 'Rulo', 'pure' and 'cueva' describe real arbitrages "
              "with real regulatory constraints, and AR-L's control is the same claim tested in "
              "the window BEFORE it was posted -- the cleanest crowding test in this command"},
    {"id": "ar_app_ecosystem", "layer": "app_ecosystem",
     "label": "Argentine trading apps, dollar trackers and their public APIs",
     "roots": ("https://dolarapi.com/v1/dolares", "https://iol.invertironline.com/",
               "https://cocos.capital/", "https://balanz.com/",
               "https://github.com/search?q=dolar+blue+api"),
     "languages": ("es-AR",),
     "licence": "public JSON endpoints and public web with terms",
     "access_label": "PUBLIC_WITH_TERMS", "credibility": "UNRELIABLE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("api dolar blue mep ccl json historico",
                 "app para operar dolar MEP comisiones",
                 "bot de alerta cotizacion dolar telegram",
                 "cocos capital rendimiento cuenta remunerada"),
     "notes": "ONE TRACKER PER LEG, PINNED AND RECORDED. These APIs ARE the parallel-rate series; "
              "trackers disagree by up to a percent and a stitched series has sourcing jumps that "
              "look exactly like the regime transitions this pack exists to detect"},
    {"id": "ar_media", "layer": "media",
     "label": "Argentine financial press",
     "roots": ("https://www.ambito.com/", "https://www.cronista.com/",
               "https://www.infobae.com/economia/", "https://www.lanacion.com.ar/economia/"),
     "languages": ("es-AR",),
     "licence": "public web with terms; several paywalled, nothing republished",
     "access_label": "PUBLIC_WITH_TERMS", "credibility": "RELIABLE",
     "predictive_state": "NARRATIVE_FEATURE", "machine_use_allowed": True,
     "queries": ("dolar blue hoy cotizacion cierre",
                 "el BCRA vendio reservas en el mercado oficial",
                 "liquidacion del agro semanal CIARA CEC",
                 "nuevas restricciones para comprar dolares comunicacion"),
     "notes": "Ambito's own dollar page is simultaneously a media source and one of the pinned "
              "trackers; the two ROLES are separated here because one is a narrative feature and "
              "the other is a measurement, and confusing them is how a quote becomes data"},
    {"id": "ar_archive", "layer": "archive",
     "label": "Historical archives: BCRA Comunicaciones, Boletin Oficial, press hemerotecas",
     "roots": ("https://www.bcra.gob.ar/Pdfs/comytexord/",
               "https://www.boletinoficial.gob.ar/busquedaAvanzada",
               "https://web.archive.org/web/*/bcra.gob.ar/*"),
     "languages": ("es-AR",),
     "licence": "public archive; official gazettes and institutional circulars",
     "access_label": "PUBLIC_ARCHIVE", "credibility": "AUTHORITATIVE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("comunicacion A BCRA restriccion acceso mercado unico y libre de cambios",
                 "comunicacion A parking titulos valores plazo",
                 "decreto impuesto PAIS alicuota texto",
                 "resolucion derechos de exportacion historico"),
     "notes": "AR-I LIVES HERE. A brecha jump must be attributed to a dated Comunicacion before "
              "it is attributed to sentiment, and this archive is the only place those dates are "
              "authoritative"},
    {"id": "ar_physical_economy", "layer": "physical_economy",
     "label": "Physical flow: up-river ports, energy, power and rig activity",
     "roots": ("https://www.argentina.gob.ar/transporte/puertos",
               "https://www.se.gob.ar/datosupstream/",
               "https://cammesaweb.cammesa.com/", "https://www.enargas.gob.ar/"),
     "languages": ("es-AR",), "licence": "public open data",
     "access_label": "OPEN_DATA", "credibility": "AUTHORITATIVE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("embarques de harina de soja puertos up river estadistica",
                 "produccion de petroleo y gas no convencional Vaca Muerta mensual",
                 "importacion de GNL barcos invierno",
                 "demanda de energia electrica CAMMESA"),
     "notes": "THE ENERGY BALANCE FLIP IS MEASURED HERE, not inferred. Pipeline commissioning "
              "dates are step changes in Argentina's dollar supply, and the winter LNG import "
              "season either shows up in these series or the claim in AR-J is wrong"},
    {"id": "ar_source_graph", "layer": "source_graph",
     "label": "The graph that finds the NEXT Argentine source",
     "roots": ("https://datos.gob.ar/", "https://www.bcra.gob.ar/PublicacionesEstadisticas/",
               "https://github.com/topics/argentina-data",
               "https://apis.datos.gob.ar/series/api/search/"),
     "languages": ("es-AR", "en"),
     "licence": "public; open-data catalogues and reference sections",
     "access_label": "PUBLIC", "credibility": "RELIABLE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("catalogo datos abiertos series de tiempo economia buscar",
                 "quien publica la serie de reservas netas metodologia",
                 "repositorio github series argentinas economia quien usa",
                 "fuentes citadas informe monetario BCRA"),
     "notes": "the datos.gob.ar SERIES SEARCH endpoint is itself a discovery instrument: it "
              "answers 'which published series contain this concept', which is the question a "
              "frozen source list can never answer"},
)

#: A layer with no source is named here WITH A REASON. All ten are currently reached. The entry
#: most likely to appear here is an Argentine LICENSED tick archive: BYMA historical depth is a
#: commercial product and if the desk ever needs it, it belongs here as LICENSED and unbought
#: rather than as a silence.
LAYER_ABSENCES: dict[str, str] = {}
def source_layer_coverage() -> dict[str, Any]:
    """Sources per layer, with every empty layer named. Blank is never an answer (L1.28a).

    `unexplained_missing` is the number that must stay at zero: a layer with no source AND no
    reason is the exact shape of a pack that stopped at the five obvious official feeds.
    """
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


# --------------------------------------------------------------------------- datasets
DATASETS: tuple[dict[str, Any], ...] = (
    {"name": "A3500 reference exchange rate", "source": "ar_bcra_api",
     "coverage": "2002 to present", "frequency": "daily",
     "publication_lag_days": 0.0, "revisions": "none",
     "licence": "public, no key", "history_from": "2002-01-11", "pit_feasible": True,
     "assets": ("SOYBEAN", "USDBRL"),
     "mechanism_families": ("calendar_settlement", "carry_funding"),
     "how_to_fetch": "GET api.bcra.gob.ar/estadisticas/v3.0/monetarias/{id} for the reference "
                     "rate variable, or the estadisticascambiarias Cotizaciones endpoint"},
    {"name": "Dolar blue (informal)", "source": "ar_parallel_trackers",
     "coverage": "2011 to present", "frequency": "continuous",
     "publication_lag_days": 0.0, "revisions": "trackers restate intraday",
     "licence": "public web", "history_from": "2011-11-01", "pit_feasible": True,
     "assets": ("USDBRL", "XAUUSD"),
     "mechanism_families": ("positioning", "scouts"),
     "how_to_fetch": "GET dolarapi.com/v1/dolares/blue -- ONE tracker, pinned and recorded"},
    {"name": "Dolar MEP and contado con liquidacion", "source": "ar_parallel_trackers",
     "coverage": "2012 to present", "frequency": "continuous",
     "publication_lag_days": 0.0, "revisions": "intraday restatement",
     "licence": "public web", "history_from": "2012-01-02", "pit_feasible": True,
     "assets": ("USDBRL", "US2000", "XAUUSD"),
     "mechanism_families": ("institutional_flow", "positioning"),
     "how_to_fetch": "GET dolarapi.com/v1/dolares/bolsa and /contadoconliqui"},
    {"name": "BCRA international reserves (gross)", "source": "ar_bcra_api",
     "coverage": "1996 to present", "frequency": "daily",
     "publication_lag_days": 1.0, "revisions": "none",
     "licence": "public, no key", "history_from": "1996-01-02", "pit_feasible": True,
     "assets": ("USDBRL", "USDTRY", "XAUUSD"),
     "mechanism_families": ("institutional_flow", "failure"),
     "how_to_fetch": "GET api.bcra.gob.ar/estadisticas/v3.0/monetarias/{id} for reservas"},
    {"name": "BCRA monetary aggregates and the policy rate", "source": "ar_bcra_api",
     "coverage": "1996 to present", "frequency": "daily and monthly",
     "publication_lag_days": 1.0, "revisions": "occasional restatement",
     "licence": "public, no key", "history_from": "1996-01-02", "pit_feasible": True,
     "assets": ("USDBRL", "SOYBEAN"),
     "mechanism_families": ("carry_funding", "central_bank_surprise"),
     "how_to_fetch": "GET api.bcra.gob.ar/estadisticas/v3.0/monetarias -- the variable LIST is "
                     "itself an endpoint, so the ids are discoverable rather than guessed"},
    {"name": "INDEC IPC (consumer prices)", "source": "ar_indec",
     "coverage": "2016 to present as a trustworthy series", "frequency": "monthly",
     "publication_lag_days": 13.0, "revisions": "none",
     "licence": "public open data", "history_from": "2016-04-30", "pit_feasible": True,
     "assets": ("USDBRL",),
     "mechanism_families": ("release_surprise",),
     "how_to_fetch": "GET apis.datos.gob.ar/series/api/series?ids=... -- HISTORY BEFORE 2016 IS "
                     "NOT USABLE and the row says so rather than serving it"},
    {"name": "REM -- market expectations survey", "source": "ar_bcra_api",
     "coverage": "2016 to present", "frequency": "monthly",
     "publication_lag_days": 7.0, "revisions": "none; each publication is a new survey",
     "licence": "public", "history_from": "2016-06-30", "pit_feasible": True,
     "assets": ("USDBRL", "SOYBEAN"),
     "mechanism_families": ("release_surprise", "central_bank_surprise"),
     "how_to_fetch": "BCRA REM publication (XLS); the survey DATE is what makes it point-in-time"},
    {"name": "DJVE grain export registrations", "source": "ar_agro",
     "coverage": "2010 to present", "frequency": "weekly",
     "publication_lag_days": 7.0, "revisions": "registrations can be cancelled",
     "licence": "public open data", "history_from": "2010-01-01", "pit_feasible": True,
     "assets": ("SOYBEAN", "CORN", "WHEAT"),
     "mechanism_families": ("corporate_flow", "release_surprise"),
     "how_to_fetch": "datos.magyp.gob.ar export registration datasets"},
    {"name": "Rosario domestic crop prices and the retenciones wedge", "source": "ar_agro",
     "coverage": "2005 to present", "frequency": "daily",
     "publication_lag_days": 1.0, "revisions": "none",
     "licence": "public", "history_from": "2005-01-03", "pit_feasible": True,
     "assets": ("SOYBEAN", "CORN", "WHEAT"),
     "mechanism_families": ("corporate_flow", "transfer"),
     "how_to_fetch": "BCR daily price bulletins; the GAP to Chicago net of the export tax is the "
                     "measurement, not the level"},
    {"name": "Crop condition and drought bulletins (BCR, Bolsa de Cereales)", "source": "ar_agro",
     "coverage": "2010 to present", "frequency": "weekly",
     "publication_lag_days": 2.0, "revisions": "each bulletin revises the running estimate",
     "licence": "public", "history_from": "2010-01-01", "pit_feasible": True,
     "assets": ("SOYBEAN", "CORN", "WHEAT"),
     "mechanism_families": ("release_surprise", "failure"),
     "how_to_fetch": "BCR weekly Guia Estrategica para el Agro and the Bolsa de Cereales "
                     "Panorama Agricola Semanal"},
    {"name": "Boletin Oficial policy events (retenciones, FX decrees, dolar soja windows)",
     "source": "ar_economia",
     "coverage": "1990 to present", "frequency": "event",
     "publication_lag_days": 0.0, "revisions": "none; a decree is dated at publication",
     "licence": "public", "history_from": "2002-01-01", "pit_feasible": True,
     "assets": ("SOYBEAN", "CORN", "USDBRL"),
     "mechanism_families": ("release_surprise", "corporate_flow"),
     "how_to_fetch": "boletinoficial.gob.ar search; the PRIMARY date for every policy event here, "
                     "and a press report of the same event can be a day early"},
    {"name": "Argentine practitioner claims on control-regime arbitrage (es-AR)",
     "source": "ar_press_forest",
     "coverage": "rolling", "frequency": "continuous",
     "publication_lag_days": 0.0, "revisions": "n/a -- dated at capture",
     "licence": "public web, claims only", "history_from": "2015-01-01", "pit_feasible": False,
     "assets": ("USDBRL", "SOYBEAN"),
     "mechanism_families": ("scouts", "transfer"),
     "how_to_fetch": "deep_forest_miner grounds in es-AR; the 'rulo' and 'canje MEP-CCL' "
                     "vocabulary describes real arbitrages that exist in no English source"},
)

# --------------------------------------------------------------------------- actors
ACTORS: tuple[dict[str, Any], ...] = (
    {"name": "soybean farmer holding grain as an inflation hedge",
     "holds": "harvested beans in silobolsas rather than pesos in a bank",
     "forced_to": ("sell when the effective peso price improves -- a retenciones cut, a "
                   "preferential FX window, or a devaluation step",
                   "sell something to fund the next planting regardless of price"),
     "when": "the April-July harvest window, and within days of any policy announcement",
     "information": ("retenciones rate", "the official-vs-parallel gap", "Rosario prices",
                     "Boletin Oficial decrees"),
     "constraints": ("storing beans is the cheapest available inflation hedge, so selling is "
                     "postponed rather than forced by the calendar",
                     "planting costs are dollar-linked and must be funded"),
     "instruments": ("SOYBEAN", "CORN"),
     "counterparties": ("crushers", "exporters", "the state as tax collector"),
     "observables": ("DJVE registrations", "Rosario volume", "crush data"),
     "impact": "world soybean MEAL supply is timed by Argentine tax policy; a window opens and "
               "shipments burst, then fall away",
     "persistence": "each window produces a burst of weeks and a lull of months",
     "falsifier": "no abnormal soybean or meal price behaviour in the weeks after announced "
                  "retenciones changes or dolar-soja windows, relative to matched non-event weeks",
     "notes": "the single most tradable Argentine mechanism, because both legs -- the event and "
              "the instrument -- exist"},
    {"name": "soybean crusher and oilseed exporter",
     "holds": "crushing capacity and an obligation to settle export proceeds officially",
     "forced_to": ("settle dollars at the official rate within the decreed deadline",
                   "buy beans when the crush margin is positive in pesos"),
     "when": "continuous; concentrated in harvest and in preferential windows",
     "information": ("the brecha (which taxes them)", "crush margins", "DJVE registrations"),
     "constraints": ("the settlement obligation converts the brecha into an export tax",
                     "capacity is fixed and idle capacity is expensive"),
     "instruments": ("SOYBEAN", "CORN"),
     "counterparties": ("farmers", "Chinese and EU buyers", "the BCRA"),
     "observables": ("DJVE", "crush volume", "official settlement statistics"),
     "impact": "Argentina supplies most of the world's traded soybean meal; the crusher's margin "
               "is where the tax and the brecha actually bite",
     "persistence": "structural, with policy-driven episodes",
     "falsifier": "no relationship between the measured brecha and Argentine crush or export "
                  "volumes once the Chicago price and the harvest calendar are controlled for",
     "notes": "the brecha as an export tax is the cleanest testable statement in this pack"},
    {"name": "Argentine saver buying dollars under rationing",
     "holds": "pesos that lose value at a measured monthly rate",
     "forced_to": ("convert to dollars by whichever route is open and cheapest",
                   "use the informal market when the legal quota is exhausted"),
     "when": "continuous, with a December-January peak on the aguinaldo and the holiday season",
     "information": ("the four published rates", "the monthly quota", "inflation prints"),
     "constraints": ("a monthly legal quota measured in hundreds of dollars",
                     "taxes and perceptions on the legal retail route"),
     "instruments": ("XAUUSD", "USDBRL"),
     "counterparties": ("informal dealers (cuevas)", "banks", "brokers"),
     "observables": ("the blue rate", "the blue-MEP spread", "retail quota usage"),
     "impact": "the blue rate carries a CASH seasonal the financial rates do not, which is the "
               "identifying variation separating retail dollarisation from capital flight",
     "persistence": "structural while the control holds",
     "falsifier": "no December-January seasonal in the blue-MEP spread once the level of the "
                  "brecha is controlled for",
     "notes": "the seasonal is what makes the two parallel legs distinguishable at all"},
    {"name": "corporate treasurer moving money out through MEP and CCL",
     "holds": "peso balances that cannot legally be remitted",
     "forced_to": ("execute the bond round trip to move dollars offshore",
                   "accept whatever discount the bond leg imposes"),
     "when": "continuous, with spikes before expected devaluations",
     "information": ("the MEP-CCL spread", "bond prices", "regulatory changes"),
     "constraints": ("access to the bond routes is itself regulated and has been restricted",
                     "a parking period (parking) has at times been imposed between the legs"),
     "instruments": ("USDBRL", "US2000", "XAUUSD"),
     "counterparties": ("brokers", "offshore counterparties"),
     "observables": ("MEP and CCL rates", "the spread between them", "bond volumes"),
     "impact": "THE MEP-CCL SPREAD IS THE PRICE OF GETTING MONEY OUT, with the peso level divided "
               "out on both legs -- the cleanest capital-flight observable available anywhere",
     "persistence": "continuous under a control regime; collapses when controls lift",
     "falsifier": "the MEP-CCL spread shows no relationship to measured capital outflow or to "
                  "regulatory tightening events",
     "notes": "this is the measurement the whole pack is built around"},
    {"name": "BCRA as reserve manager under stress",
     "holds": "gross reserves that include swap lines and bank dollar deposits",
     "forced_to": ("sell dollars into the official market when demand exceeds supply",
                   "ration access when reserves fall",
                   "meet IMF programme targets on published dates"),
     "when": "daily; the IMF review dates are scheduled and public",
     "information": ("the reserve series", "the brecha", "the import-payment queue"),
     "constraints": ("net reserves have been NEGATIVE in this sample",
                     "IMF programme targets are contractual and dated"),
     "instruments": ("USDBRL", "USDTRY", "XAUUSD", "SOYBEAN"),
     "counterparties": ("importers", "exporters", "the IMF", "China via the swap line"),
     "observables": ("daily gross reserves", "the brecha", "import-payment deferral schemes"),
     "impact": "reserve stress is the leading indicator of a regime change; every discrete "
               "devaluation in this sample was preceded by a measurable reserve drawdown",
     "persistence": "builds over months and resolves in a day",
     "falsifier": "no relationship between measured reserve depletion and the probability of a "
                  "brecha regime transition in the following quarter",
     "notes": "this actor connects directly to the interaction miner's EM-stress family"},
    {"name": "importer queuing for official dollars",
     "holds": "goods ordered abroad and an unpaid dollar invoice",
     "forced_to": ("wait in an administered queue (SIRA, then SEDI) for access",
                   "finance the gap with supplier credit or buy at the parallel rate"),
     "when": "continuous; the queue length is the policy variable",
     "information": ("import-licence approvals", "the payment schedule", "the brecha"),
     "constraints": ("access is administratively rationed rather than priced",
                     "commercial debt accumulates as an unrecorded liability"),
     "instruments": ("USDBRL", "XAUUSD"),
     "counterparties": ("foreign suppliers", "the BCRA", "banks"),
     "observables": ("the stock of commercial debt", "approval statistics", "the brecha"),
     "impact": "the import queue is a HIDDEN short dollar position of the whole economy; when it "
               "is unwound the FX demand arrives all at once",
     "persistence": "accumulates over quarters, releases in a regime change",
     "falsifier": "no relationship between the estimated commercial-debt stock and the size of "
                  "the FX move at a regime transition",
     "notes": "the reason an Argentine devaluation is larger than the brecha alone predicts"},
    {"name": "Vaca Muerta producer and the energy balance",
     "holds": "shale oil and gas production that has turned the energy balance positive",
     "forced_to": ("export crude when domestic demand is met",
                   "import LNG in winter when the pipeline is short"),
     "when": "seasonal: LNG imports in the southern winter, crude exports year-round and growing",
     "information": ("production statistics", "pipeline capacity", "the energy trade balance"),
     "constraints": ("pipeline capacity is the binding constraint, not geology",
                     "domestic price regulation caps the local realisation"),
     "instruments": ("XTIUSD", "XBRUSD", "XNGUSD"),
     "counterparties": ("Chile and Brazil as buyers", "LNG suppliers"),
     "observables": ("monthly production", "the energy trade balance", "pipeline commissioning"),
     "impact": "the energy balance flipped from a large deficit to a surplus inside this sample, "
               "which is a structural change in Argentina's dollar supply that has nothing to do "
               "with agriculture",
     "persistence": "structural, years",
     "falsifier": "no measurable change in the seasonal pattern of Argentine FX pressure after "
                  "the pipeline commissioning dates",
     "notes": "the second export cycle, and the reason this pack names energy instruments"},
    {"name": "provincial and sovereign debt issuer",
     "holds": "restructured dollar bonds with step-up coupons and a scheduled payment calendar",
     "forced_to": ("pay coupons on dated schedules in dollars",
                   "roll peso debt at auctions that can fail"),
     "when": "January and July coupon dates for the restructured bonds; monthly peso auctions",
     "information": ("riesgo pais", "auction rollover ratios", "reserve levels"),
     "constraints": ("coupon dates are contractual",
                     "a failed peso rollover forces monetisation, which feeds the brecha"),
     "instruments": ("USDBRL", "US2000", "XAUUSD"),
     "counterparties": ("bondholders", "local banks", "the BCRA"),
     "observables": ("rollover ratios", "riesgo pais", "auction results"),
     "impact": "a failed peso auction is a monetary event within days: the shortfall is monetised "
               "and the brecha widens, which is a DATED causal chain with observable links",
     "persistence": "monthly auctions; coupon dates twice a year",
     "falsifier": "no brecha response to measured auction rollover shortfalls within the "
                  "following weeks",
     "notes": "the clearest internal causal chain in the pack and therefore the best test of "
              "whether the brecha responds to fundamentals at all"},
    {"name": "IMF as a conditional creditor",
     "holds": "the largest exposure in its portfolio, with dated reviews and targets",
     "forced_to": ("assess programme compliance on scheduled review dates",
                   "disburse or withhold against reserve and fiscal targets"),
     "when": "scheduled reviews, published in advance",
     "information": ("reserve accumulation targets", "the fiscal result", "programme documents"),
     "constraints": ("targets are contractual and quantitative",
                     "a waiver is possible but is itself an observable event"),
     "instruments": ("USDBRL", "USDTRY", "US2000"),
     "counterparties": ("the Treasury", "the BCRA"),
     "observables": ("review dates", "staff-level agreements", "disbursement announcements"),
     "impact": "the ONLY scheduled Argentine event class in this pack; everything else here is "
               "unscheduled, which makes the IMF calendar the internal control for 'does a "
               "scheduled event behave differently from an unscheduled one'",
     "persistence": "programme-length",
     "falsifier": "IMF review dates produce no measurable effect on the brecha or on Argentine "
                  "risk relative to matched non-review dates",
     "notes": "scheduled versus unscheduled is the identification, and Argentina supplies both"},
    {"name": "arbitrageur running the rulo and the MEP-CCL canje",
     "holds": "peso and dollar balances across several regulated routes",
     "forced_to": ("close a round trip within the regulatory parking window",
                   "stop when a rule change closes the route"),
     "when": "continuous while the route is open; each closure is a dated regulatory event",
     "information": ("the spread between every pair of the four rates",
                     "BCRA communications closing routes"),
     "constraints": ("parking periods, per-person limits and cross-restrictions between routes",
                     "a regulation can close a route overnight"),
     "instruments": ("USDBRL",),
     "counterparties": ("brokers", "banks", "other arbitrageurs"),
     "observables": ("the spreads themselves", "BCRA Comunicaciones"),
     "impact": "the arbitrage KEEPS the four rates in a relationship; when a regulatory change "
               "breaks it, the spreads jump and the jump is a measurement of the new constraint "
               "rather than of a new expectation",
     "persistence": "route-by-route; each closure is permanent until reversed",
     "falsifier": "spreads between the parallel routes show no discontinuity at dated BCRA "
                  "regulatory changes",
     "notes": "this actor is why a brecha jump must be attributed to a regulation before it is "
              "attributed to sentiment -- and the pack's regime detector says which"},
    {"name": "Chinese counterparty via the currency swap line",
     "holds": "a yuan swap line with the BCRA, activated and partly repaid in this sample",
     "forced_to": ("negotiate activation and renewal on political terms",
                   "accept yuan settlement of Argentine imports"),
     "when": "episodic; each activation and repayment is announced",
     "information": ("swap-line announcements", "the gross-vs-net reserve gap",
                     "yuan settlement volumes"),
     "constraints": ("the swap is a liability inside GROSS reserves, which is why gross and net "
                     "diverge",
                     "activation is a diplomatic decision"),
     "instruments": ("USDCNH", "USDBRL", "SOYBEAN"),
     "counterparties": ("the PBoC", "the BCRA"),
     "observables": ("announced activations", "the gross-net gap", "yuan import settlement"),
     "impact": "the swap line is the single largest reason gross reserves overstate Argentine "
               "solvency, and its activation dates are public",
     "persistence": "episodic, months",
     "falsifier": "no change in the gross-net reserve gap around announced swap activations",
     "notes": "a China leg inside an Argentine pack -- and the reason the interaction miner reads "
              "the Chinese demand state for the Argentine family too"},
    {"name": "domestic bank holding sovereign paper against peso deposits",
     "holds": "a balance sheet that is mostly government debt funded by short peso deposits",
     "forced_to": ("roll central-bank paper as it matures",
                   "absorb whatever the Treasury cannot place elsewhere"),
     "when": "continuous; maturities are dense and short",
     "information": ("the policy rate", "auction results", "deposit flows"),
     "constraints": ("regulatory requirements to hold the paper",
                     "a deposit run would force liquidation into a market that cannot absorb it"),
     "instruments": ("USDBRL", "XAUUSD"),
     "counterparties": ("the BCRA", "the Treasury", "depositors"),
     "observables": ("the stock of remunerated liabilities", "deposit series", "auction results"),
     "impact": "the stock of short central-bank liabilities is the 'monetary overhang' that every "
               "devaluation-risk argument in Argentina rests on, and it is a published number",
     "persistence": "structural",
     "falsifier": "no relationship between the measured overhang and the size of subsequent "
                  "brecha moves",
     "notes": "the overhang is the quantity the brecha is supposed to be pricing; testing that "
              "link is the most fundamental test in the pack"},
    {"name": "provincial economy dependent on a single commodity",
     "holds": "regional output concentrated in soy, wine, lithium or hydrocarbons",
     "forced_to": ("lobby against retenciones when the crop price falls",
                   "cut provincial spending when the transfer shrinks"),
     "when": "the annual budget cycle and the harvest",
     "information": ("crop prices", "federal transfers", "provincial accounts"),
     "constraints": ("provincial revenue depends on federal transfers that themselves depend "
                     "on export taxes",),
     "instruments": ("SOYBEAN", "CORN", "XCUUSD"),
     "counterparties": ("the federal government", "exporters"),
     "observables": ("provincial fiscal accounts", "transfer statistics"),
     "impact": "the political feasibility of a retenciones change is a function of the crop price, "
               "which makes the POLICY partly predictable from the price -- a feedback loop that "
               "any naive event study will mistake for causation running the other way",
     "persistence": "annual",
     "falsifier": "retenciones changes show no relationship to the preceding crop price path, "
                  "which would make them exogenous and the event study clean",
     "notes": "the endogeneity warning that AR-D exists to handle"},
)

# --------------------------------------------------------------------------- domains
_CONTROLS = ("a matched non-event day of the same weekday and month",
             "the global dollar factor (USDX) and US500 on the same session",
             "Brazil (USDBRL) as the LatAm peer with no capital control")

DOMAINS: tuple[dict[str, Any], ...] = (
    {"id": "AR-A", "title": "The brecha as a measured capital-control state",
     "objects": ("official A3500 against blue, MEP and CCL",
                 "the level, the change and the regime", "regime transitions with dates"),
     "conditions": ("the four legs are quoted by different mechanisms and disagree for real "
                    "reasons, so the brecha is a SET of gaps and not one number",
                    "a tracker change looks exactly like a regime change and must be excluded"),
     "instruments": ("USDBRL", "USDMXN", "USDTRY", "XAUUSD", "SOYBEAN"),
     "controls": (*_CONTROLS, "the 2015-12 to 2019-09 window, when the brecha was near zero"),
     "notes": "the state variable the whole pack contributes to the desk"},
    {"id": "AR-B", "title": "MEP-CCL as the price of cross-border settlement",
     "objects": ("the spread between the two bond routes",
                 "its behaviour around regulatory changes"),
     "conditions": ("the peso level divides out on both legs, so the spread is a pure "
                    "cross-border cost",
                    "the bond's own credit move is common to both legs and also divides out"),
     "instruments": ("USDBRL", "US2000", "XAUUSD"),
     "controls": (*_CONTROLS, "the blue-MEP spread, which is a cash-versus-financial spread and "
                              "not a cross-border one"),
     "notes": "the cleanest capital-flight measurement available to this desk anywhere"},
    {"id": "AR-C", "title": "Reserve stress and the probability of a regime transition",
     "objects": ("daily gross reserves", "the estimated gross-net gap",
                 "the dated transitions themselves"),
     "conditions": ("net reserves are an ESTIMATE and never an official series",
                    "the swap line sits inside gross and not inside net"),
     "instruments": ("USDBRL", "USDTRY", "USDZAR", "XAUUSD"),
     "controls": (*_CONTROLS, "Turkey and South Africa as EM reserve-stress comparisons"),
     "notes": "a hazard model, not a level regression: the object is a transition probability"},
    {"id": "AR-D", "title": "Retenciones, dolar soja and the timing of world meal supply",
     "objects": ("Boletin Oficial policy dates", "DJVE registrations", "crush volume",
                 "the Rosario-Chicago wedge"),
     "conditions": ("the policy is partly ENDOGENOUS to the crop price, which a naive event "
                    "study will read backwards",
                    "the Boletin Oficial date is the primary date and a press report may precede "
                    "it by a day"),
     "instruments": ("SOYBEAN", "CORN", "WHEAT"),
     "controls": (*_CONTROLS, "Brazilian and US export windows in the same weeks",
                  "USDA WASDE dates as the competing information event"),
     "notes": "the most tradable domain here because both the event and the instrument exist"},
    {"id": "AR-E", "title": "Drought, La Nina and Argentine crop failure",
     "objects": ("weekly crop-condition bulletins", "the 2017-18 and 2022-23 failures",
                 "planting-area decisions"),
     "conditions": ("an Argentine crop failure is a GLOBAL meal supply event",
                    "the bulletins revise a running estimate, so only the first print is PIT"),
     "instruments": ("SOYBEAN", "CORN", "WHEAT"),
     "controls": (*_CONTROLS, "Brazilian crop conditions in the same season, which is the "
                              "competing southern-hemisphere supply"),
     "notes": "Brazil and Argentina as substitutes is the identification for a supply claim"},
    {"id": "AR-F", "title": "Unscheduled policy as the control class for scheduled policy",
     "objects": ("BCRA rate changes with no calendar", "IMF reviews with a calendar",
                 "the difference between the two response profiles"),
     "conditions": ("Argentina is the only country in this command with NO central-bank "
                    "calendar, which makes it the natural control rather than a data gap",),
     "instruments": ("USDBRL", "USDTRY", "US2000"),
     "controls": (*_CONTROLS, "Brazilian Copom and Chilean RPM dates as the scheduled class"),
     "notes": "the absence of a calendar is the research asset"},
    {"id": "AR-G", "title": "Argentina as an EM-stress leading or lagging indicator",
     "objects": ("brecha widening episodes", "joint moves with TRY, ZAR and BRL",
                 "gold's behaviour in those windows"),
     "conditions": ("Argentina is small enough to be idiosyncratic and extreme enough to be a "
                    "leading indicator; which of the two it is should be regime-dependent",),
     "instruments": ("USDBRL", "USDTRY", "USDZAR", "USDMXN", "XAUUSD", "US2000"),
     "controls": (*_CONTROLS, "episodes with a global dollar move and no Argentine event"),
     "notes": "the principal's 'local state as a SENSOR' instruction, on the EM-stress leg"},
    {"id": "AR-H", "title": "The monetary overhang and what the brecha is pricing",
     "objects": ("the stock of remunerated central-bank liabilities",
                 "peso auction rollover ratios", "the brecha's response to both"),
     "conditions": ("a failed auction is monetised within days, which is a dated causal chain "
                    "with observable links rather than a correlation",),
     "instruments": ("USDBRL", "XAUUSD", "SOYBEAN"),
     "controls": (*_CONTROLS, "auctions that cleared fully as the matched non-event"),
     "notes": "the most fundamental test here: does the brecha price the quantity it is supposed "
              "to price"},
    {"id": "AR-I", "title": "Regulatory route closures and spread discontinuities",
     "objects": ("BCRA Comunicaciones that close an arbitrage route",
                 "the parking periods", "the spread jumps at each"),
     "conditions": ("a regulation-driven jump must be ATTRIBUTED before any sentiment reading; "
                    "the two look identical in the series and are different events",),
     "instruments": ("USDBRL",),
     "controls": (*_CONTROLS, "spread moves of the same size with no regulatory change"),
     "notes": "the attribution step that keeps AR-A honest"},
    {"id": "AR-J", "title": "Vaca Muerta and the energy balance flip",
     "objects": ("monthly shale production", "the energy trade balance",
                 "pipeline commissioning dates"),
     "conditions": ("the constraint is pipeline capacity, so commissioning dates are step "
                    "changes rather than a trend",),
     "instruments": ("XTIUSD", "XBRUSD", "XNGUSD"),
     "controls": (*_CONTROLS, "the southern-winter LNG import season before the flip"),
     "notes": "the second export cycle, and the one that will matter more each year"},
    {"id": "AR-K", "title": "INDEC credibility as an era boundary",
     "objects": ("the 2007-2015 intervention", "published versus private inflation estimates",
                 "the 2016 re-basing"),
     "conditions": ("a study pooling across 2016-01 is measuring a change in the MEASUREMENT "
                    "rather than in the economy",),
     "instruments": ("USDBRL",),
     "controls": (*_CONTROLS, "provincial price indices, which continued through the "
                              "intervention"),
     "notes": "not a caveat; the reason the era table exists"},
    {"id": "AR-L", "title": "Argentine practitioner claims, converted and falsified",
     "objects": ("'rulo', 'pure' and 'canje MEP-CCL' as named local arbitrages",
                 "consultora estimates of net reserves", "harvest-lore claims"),
     "conditions": ("a claim is a hypothesis with a falsifier and never evidence",
                    "an arbitrage described in public is an arbitrage that is already crowded"),
     "instruments": ("USDBRL", "SOYBEAN"),
     "controls": (*_CONTROLS, "the same claim tested in the window BEFORE it was published"),
     "notes": "the before-publication window is the cleanest crowding test in this command"},
)

# --------------------------------------------------------------------------- miners
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    {"name": "ar_brecha_state", "domain_ids": ("AR-A", "AR-B", "AR-I"), "kind": "mechanism",
     "entry": "research.countries.ar.data_plane:brecha_state", "cadence_s": 3600.0,
     "steerable": True,
     "notes": "the official-versus-parallel gap as a regime state with dated transitions"},
    {"name": "ar_bcra_lane", "domain_ids": ("AR-C", "AR-F", "AR-H"), "kind": "mechanism",
     "entry": "research.countries.ar.data_plane:fetch", "cadence_s": 21600.0, "steerable": True,
     "notes": "the BCRA lane with its vintage store"},
    {"name": "ar_holiday_liquidity", "domain_ids": ("AR-A",), "kind": "calendar",
     "entry": "research.countries.ar.pack:is_closed", "cadence_s": 86400.0, "steerable": False,
     "notes": "the statutory table only; bridge days are decreed and are not predictable"},
)

# --------------------------------------------------------------------------- the two vocabularies
# THE FRAMEWORK AND THIS PACKAGE NAME THE SAME ROW DIFFERENTLY, AND BOTH CONSUMERS ARE REAL.
# `countries.check_pack` validates an edge written as {id, source, mechanism, targets, sign,
# horizon, lag, control, evidence}; `libs.research.country_lab.TransmissionSeed` coerces a row
# into {to_country, asset, actor, constraint, flow, source_series, source_symbol, lag_days, era}
# and DROPS every key it does not know. So every seed here carries BOTH sets: the desk's own
# vocabulary is authored and the framework's is DERIVED from it, once, here.


def _lag_days(text: str) -> float:
    """The first whole number in a lag phrase (`"1-10 sessions"` -> 1.0). An unparseable lag is
    0.0 and NOT one day: inventing a lag measures the transmission at the wrong horizon."""
    digits = ""
    for ch in str(text or ""):
        if ch.isdigit():
            digits += ch
        elif digits:
            break
    return float(digits) if digits else 0.0


def _dual(rows: tuple[dict[str, Any], ...]) -> tuple[dict[str, Any], ...]:
    """Every transmission seed in both vocabularies, with the DERIVED keys written FIRST.

    Order is load-bearing: the framework keeps the FIRST key that maps to a field, so its own
    alias (`lag`->lag_days) would otherwise put the STRING "1-10 sessions" into a float field.
    """
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
    {"id": "ar_brecha_to_em_stress",
     "source": "the official-versus-parallel gap and its regime",
     "mechanism": "a widening brecha is capital flight being rationed; it is the earliest and "
                  "most extreme expression of EM capital-account stress and should lead the "
                  "milder cases",
     "targets": ("USDBRL", "USDMXN", "USDZAR", "USDTRY"), "sign": "same",
     "horizon": "5-40 sessions", "lag": "1-10 sessions",
     "control": "episodes with a global dollar move and no Argentine event; the 2016-2019 "
                "window when the brecha was near zero",
     "evidence": "HYPOTHESIS",
     "notes": "the pack's headline seed and the one the interaction miner consumes"},
    {"id": "ar_brecha_to_gold",
     "source": "the brecha level and its acceleration",
     "mechanism": "a control regime makes gold the only unrationed store of value available to a "
                  "domestic saver; the demand is small globally but the SIGNAL about capital-"
                  "control intensity is not",
     "targets": ("XAUUSD", "XAGUSD"), "sign": "same",
     "horizon": "5-40 sessions", "lag": "1-10 sessions",
     "control": "gold moves driven by US real rates with no EM capital-account component",
     "evidence": "HYPOTHESIS",
     "notes": "gold as the sensor's readout, exactly as the principal's order describes"},
    {"id": "ar_reserve_stress_to_transition",
     "source": "BCRA gross reserves and the estimated gross-net gap",
     "mechanism": "reserve depletion raises the hazard of a discrete regime change; every "
                  "devaluation step in this sample was preceded by a measurable drawdown",
     "targets": ("USDBRL", "USDTRY", "XAUUSD"), "sign": "same",
     "horizon": "20-120 sessions", "lag": "5-30 sessions",
     "control": "reserve drawdowns in EM peers with no control regime",
     "evidence": "HYPOTHESIS",
     "notes": "a hazard model; the target is the transition, not the level"},
    {"id": "ar_retenciones_to_softs",
     "source": "Boletin Oficial retenciones changes and dolar-soja windows",
     "mechanism": "a tax or FX window changes the farmer's effective price and releases stored "
                  "beans; world meal supply moves on a POLICY date",
     "targets": ("SOYBEAN", "CORN"), "sign": "opposite",
     "horizon": "5-40 sessions", "lag": "0-10 sessions",
     "control": "Brazilian and US export windows in the same weeks; WASDE dates",
     "evidence": "HYPOTHESIS",
     "notes": "the most tradable seed in the pack; the endogeneity of the policy to the price is "
              "the thing that must be handled and AR-D says how"},
    {"id": "ar_crop_failure_to_softs",
     "source": "weekly crop-condition bulletins and La Nina episodes",
     "mechanism": "Argentina is the world's largest exporter of soybean meal and oil; a crop "
                  "failure is a global supply event and the meal leg moves more than the bean",
     "targets": ("SOYBEAN", "CORN", "WHEAT"), "sign": "opposite",
     "horizon": "20-120 sessions", "lag": "5-30 sessions",
     "control": "Brazilian crop conditions in the same season as the competing supply",
     "evidence": "HYPOTHESIS",
     "notes": "the substitution with Brazil is the identification"},
    {"id": "ar_soy_liquidation_to_brecha",
     "source": "DJVE registrations and crush volume",
     "mechanism": "export settlement is the economy's dollar supply; a liquidation burst narrows "
                  "the brecha and its exhaustion widens it again",
     "targets": ("SOYBEAN", "USDBRL"), "sign": "opposite",
     "horizon": "5-30 sessions", "lag": "0-5 sessions",
     "control": "harvest weeks with no policy window",
     "evidence": "HYPOTHESIS",
     "notes": "the internal loop: agriculture IS Argentine FX policy"},
    {"id": "ar_unscheduled_policy_to_risk",
     "source": "BCRA Comunicados with no calendar",
     "mechanism": "an unscheduled decision cannot be pre-positioned for, so its price impact "
                  "should be larger and its pre-drift zero",
     "targets": ("USDBRL", "USDTRY", "US2000"), "sign": "same",
     "horizon": "1-10 sessions", "lag": "0-2 sessions",
     "control": "Brazilian Copom and Chilean RPM decisions as the scheduled class",
     "evidence": "HYPOTHESIS",
     "notes": "the absence of a calendar as a research asset rather than a gap"},
    {"id": "ar_energy_flip_to_crude",
     "source": "Vaca Muerta production and pipeline commissioning",
     "mechanism": "the energy balance flipped from deficit to surplus inside this sample, which "
                  "removes a seasonal import bid and adds a structural export offer",
     "targets": ("XTIUSD", "XBRUSD", "XNGUSD"), "sign": "opposite",
     "horizon": "20-250 sessions", "lag": "10-60 sessions",
     "control": "the southern-winter LNG import season before the flip",
     "evidence": "HYPOTHESIS",
     "notes": "small in world terms and large in Argentine terms; the seed is about the SEASONAL "
              "changing shape, not about the level of crude"},
    {"id": "ar_regulatory_closure_to_spreads",
     "source": "BCRA Comunicaciones closing an arbitrage route",
     "mechanism": "a closed route breaks the arbitrage that held the four rates together; the "
                  "resulting jump measures the new constraint and not a new expectation",
     "targets": ("USDBRL",), "sign": "same",
     "horizon": "1-20 sessions", "lag": "0-1 sessions",
     "control": "spread moves of the same size with no regulatory change",
     "evidence": "HYPOTHESIS",
     "notes": "the attribution step; without it every brecha study confuses rules with sentiment"},
    {"id": "ar_overhang_to_brecha",
     "source": "the stock of remunerated central-bank liabilities and auction rollover ratios",
     "mechanism": "a failed peso auction is monetised within days and the brecha is supposed to "
                  "price exactly that quantity",
     "targets": ("USDBRL", "XAUUSD"), "sign": "same",
     "horizon": "5-40 sessions", "lag": "1-10 sessions",
     "control": "auctions that cleared fully",
     "evidence": "HYPOTHESIS",
     "notes": "the most fundamental test in the pack"},
)

#: Authored in the desk's vocabulary; `_dual` adds the framework's.
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = _dual(_EDGE_ROWS)


# --------------------------------------------------------------------------- eras
_ERA_ROWS: tuple[dict[str, Any], ...] = (
    {"id": "ar_indec_intervention", "start": "2007-01-01", "end": "2015-12-31",
     "label": "The INDEC intervention",
     "what_changed": "published inflation and poverty statistics were politically managed and "
                     "private estimates were legally suppressed",
     "invalidates": "EVERY real-variable study crossing 2016-01 is measuring a change in the "
                    "MEASUREMENT rather than in the economy"},
    {"id": "ar_cepo_1", "start": "2011-10-31", "end": "2015-12-16",
     "label": "The first cepo",
     "what_changed": "retail dollar access was rationed and the blue market became the marginal "
                     "price; the brecha reached about 60%",
     "invalidates": "FX-volatility and pass-through estimates from a controlled regime do not "
                    "transfer to a floating one"},
    {"id": "ar_open_capital_account", "start": "2015-12-17", "end": "2019-09-01",
     "label": "Controls lifted; the brecha near zero",
     "what_changed": "a genuine float with an open capital account, then an inflation-targeting "
                     "attempt, then a currency crisis in 2018",
     "invalidates": "this is the only window where the brecha is uninformative -- and it is "
                    "therefore the NEGATIVE CONTROL for every brecha claim in this pack"},
    {"id": "ar_cepo_2", "start": "2019-09-01", "end": "2023-12-12",
     "label": "The second cepo, hardened through 2020-2021",
     "what_changed": "controls returned, the PAIS tax and perceptions were layered onto the "
                     "retail rate, and the brecha exceeded 100% repeatedly",
     "invalidates": "the retail 'official' rate is no longer comparable to A3500 inside this "
                    "window; a brecha computed against the retail board rate is a different "
                    "series"},
    {"id": "ar_devaluation_2023", "start": "2023-12-13", "end": "2024-11-30",
     "label": "The December 2023 step devaluation and the 2% crawl",
     "what_changed": "the official rate moved by more than 100% in a day and then crawled at 2% "
                     "a month; the brecha collapsed and rebuilt",
     "invalidates": "any unconditional Argentine FX volatility estimate that includes this date "
                    "without conditioning on it"},
    {"id": "ar_crawl_1pct", "start": "2024-12-01", "end": "2025-04-11",
     "label": "The crawl cut to 1% a month",
     "what_changed": "the administered rate's drift halved, which changes the carry of every "
                     "peso position and the implied ROFEX curve",
     "invalidates": "carry estimates from the 2% window do not transfer"},
    {"id": "ar_band_regime", "start": "2025-04-14", "end": None,
     "label": "The band regime and the lifting of the cepo for individuals",
     "what_changed": "the official rate floats inside announced crawling bands and retail access "
                     "was freed, which changed WHAT the brecha measures -- it is now a spread "
                     "inside a band rather than the price of a rationed good",
     "invalidates": "a brecha series pooled across this date is two different quantities under "
                    "one name, and the regime detector must treat it as a break rather than as a "
                    "level change"},
)

POLICY_ERAS: tuple[dict[str, Any], ...] = _named_eras(_ERA_ROWS)


# --------------------------------------------------------------------------- access constraints
ACCESS_CONSTRAINTS: tuple[dict[str, Any], ...] = (
    {"constraint": "USDARS is not quoted on this broker and neither is any Argentine asset",
     "measured": "universe.json holds USDBRL and USDMXN and no ARS pair",
     "consequence": "this pack is TRANSMISSION-ONLY. The brecha is a STATE to condition other "
                    "instruments on, never something to trade"},
    {"constraint": "the parallel rates are tracker surveys, not transaction prints",
     "measured": "public trackers disagree by up to a percent on the same day",
     "consequence": "the lane pins ONE source per leg and records which; a stitched series has "
                    "sourcing jumps that are indistinguishable from the regime transitions this "
                    "pack exists to detect"},
    {"constraint": "net reserves are an analyst estimate and not an official series",
     "measured": "the BCRA publishes GROSS reserves only",
     "consequence": "every net-reserve number in this pack is labelled an estimate; the "
                    "gross-net gap is reported as a range, never as a published figure"},
)

# --------------------------------------------------------------------------- assembly
_PACK_FIELDS: tuple[str, ...] = (
    "code", "name", "region_command", "currency", "executable_instruments", "central_bank",
    "fixing_conventions", "settlement_conventions", "exchanges", "holidays_rule",
    "fiscal_year_end", "positioning_sources", "native_languages", "terminology", "source_classes",
    "datasets", "actors", "domains", "custom_miners", "transmission_edges_seed", "policy_eras")

MISSION = ("mine Argentina as the desk's capital-control laboratory: a daily, free, published "
           "measurement of how binding a capital control is, a priced measure of the cost of "
           "getting money out, and a soybean supply whose TIMING is set by a tax rate -- used as "
           "a SENSOR for EM stress, gold and the softs, because none of the four Argentine "
           "exchange rates is tradable here and this pack never pretends otherwise")


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
