"""CHILE AND PERU: a third of the world's copper, two absent currencies, one transmission set.

WHY THESE TWO ARE ONE PACK. Chile mines roughly a quarter of world copper and Peru roughly a
tenth; between them they are the marginal supplier of the metal that prices global industrial
demand. Both run inflation-targeting central banks with published meeting calendars. Both
currencies -- CLP and PEN -- are ABSENT from this broker's registry. So the two economies reach
this desk through the SAME three instruments (XCUUSD, AUDUSD and the China proxies), and the
useful research object is not "Chile" or "Peru" but the ANDEAN SUPPLY STATE against the Chinese
DEMAND STATE, with each country's idiosyncratic shocks serving as the other's negative control.

FOUR MECHANISMS THAT EXIST HERE AND NOWHERE ELSE IN THIS COMMAND:

  1. A SUPPLY SIDE THAT IS STRIKE-DATED AND CONFLICT-DATED. Escondida, Collahuasi, Las Bambas and
     Antamina are individually large enough that one labour contract or one blocked road moves
     the world price. Chilean union contracts run on a PUBLISHED four-year cycle and Peruvian
     road blockades cluster with the political calendar. This is the only commodity supply in the
     desk's book whose disruptions are announced in advance by a negotiation timetable.

  2. THE AFP MULTIFONDO SWITCH -- a forced flow with no counterpart anywhere else. Chilean workers
     may move their whole pension balance between five funds (A to E) with days of notice, and an
     advisory industry (Felices y Forrados and its successors) has repeatedly triggered MASS
     simultaneous switches. The AFPs then have to rebalance offshore assets, which is a large,
     dated, involuntary FX flow driven by a newsletter rather than by a macro variable.

  3. AN INTERVENTION REGIME THAT IS PRE-ANNOUNCED WITH A SIZE AND AN END DATE. The BCCh announces
     a programme (USD 20bn from 2019-11-28, USD 25bn from 2022-07-18) with dates and daily
     amounts published up front. Brazil announces auctions one at a time, Argentina announces
     nothing. Chile is the pre-committed case, and comparing the three IS a research object.

  4. A PERUVIAN CENTRAL BANK THAT MANAGES THE SOL THROUGH SWAPS RATHER THAN SPOT. The BCRP's CDR
     and swap cambiario books let it absorb hedging demand without spending reserves, which is why
     the sol has the lowest realised volatility in Latin America despite the country having the
     region's most volatile politics. Sol volatility is therefore a POLICY variable, not a market
     one, and it is the cleanest available control for "does political risk move a currency".

WHAT IS EXECUTABLE: NOTHING LOCAL. `OWN_PRICE` is empty on purpose. USDCLP, USDPEN, the Santiago
IPSA, the Lima S&P/BVL and the Chilean UF-linked curve are all absent from
`desks/mt5/data/universe/universe.json`, and each is named in `TRANSMISSION_TARGETS` with the
carrier that stands in for it and the basis that substitution costs. Copper itself IS quoted
(XCUUSD), which is the whole reason this pack can be tested at all.

THE TWO-LANE ORDER. Codelco is state-owned and unlisted; BHP, Antofagasta, Southern Copper and
Buenaventura are listed and are NOT in this broker's registry. They appear here only as ACTORS
whose production and strike calendars move the metal. No single name is ever a symbol here.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------- identity
CODE = "cl"
NAME = "Chile (with Peru)"
REGION_COMMAND = "latam"
REGION_DESK = "SOUTH_AMERICA"
CURRENCY = "CLP"
SECONDARY_CURRENCY = "PEN"
NATIVE_LANGUAGES: tuple[str, ...] = ("es-CL", "es-PE")
FISCAL_YEAR_END = "12-31"

#: EMPTY, AND THAT IS THE PACK'S FIRST FACT. Neither CLP nor PEN is quoted on this broker, so
#: every mechanism here is TRANSMISSION-ONLY and must name its carrier.
OWN_PRICE: tuple[str, ...] = ()

#: The carriers. Copper is the one instrument that IS the Chilean and Peruvian economy rather than
#: a proxy for it; everything else is a declared substitution.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "XCUUSD",                                   # the metal itself -- the only direct expression
    "XALUSD", "XZNUSD", "XNIUSD", "XPBUSD",     # the base complex, the within-metals control
    "XAUUSD", "XAGUSD", "XPTUSD", "XPDUSD",     # Peru is a top-three silver and gold producer too
    "AUDUSD", "AUDJPY", "NZDUSD",               # the liquid copper-beta currencies
    "USDCNH", "CHINAH", "HK50",                 # the demand state
    "USDBRL", "USDMXN", "USDZAR",               # the LatAm and EM-stress peers
    "US500", "NAS100", "USDX", "UST10Y",        # the global risk, dollar and duration factors
    "XTIUSD",                                   # mining energy cost and the global cycle
)

#: Neither currency is in the desk's COT axis and neither has a CME contract of consequence. The
#: MEASUREMENT is that positioning here must come from the metal, not the currency.
COT_CURRENCY = ""
COT_STATUS = ("CFTC publishes COPPER (HG) positioning and the desk's cot.json axis MAPS XCUUSD. "
              "There is no CLP or PEN contract in that axis and no liquid CME peso or sol future, "
              "so Andean positioning is read from the METAL's speculative net rather than from a "
              "currency -- which is a different object and is labelled as one, not substituted "
              "silently.")

TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "USD/CLP spot and the Chilean onshore forward curve", "venue": "interbank / CCLV",
     "why": "the Chilean peso is the highest-beta copper currency in the world and the natural "
            "expression of every domestic mechanism in this pack",
     "proxies": ("XCUUSD", "AUDUSD", "USDBRL", "USDX"),
     "basis_cost": "AUD carries an iron-ore and RBA term CLP does not; USDBRL carries a fiscal "
                   "term CLP does not. Neither substitution is clean and both are declared."},
    {"name": "USD/PEN spot and the BCRP CDR book", "venue": "interbank / BCRP",
     "why": "the sol's realised volatility is a POLICY output, which makes it the control case "
            "for political-risk-moves-currency claims",
     "proxies": ("XCUUSD", "USDBRL", "USDMXN"),
     "basis_cost": "no carrier reproduces a managed-vol currency; the Peruvian FX leg is largely "
                   "UNMEASURABLE on this box and is declared so rather than approximated"},
    {"name": "S&P IPSA (Santiago) and S&P/BVL Peru General (Lima)", "venue": "Bolsa de Santiago "
                                                                            "/ BVL",
     "why": "the domestic risk assets; both are mining-heavy and both are absent here",
     "proxies": ("XCUUSD", "CHINAH", "US500"),
     "basis_cost": "a mining-heavy local index is closer to the metal than to its own country's "
                   "macro, which is why the metal is the better carrier and the index is not "
                   "missed as much as its absence suggests"},
    {"name": "COMEX HG and LME copper, and the LME warehouse stock series", "venue": "CME / LME",
     "why": "XCUUSD is a CFD on the COMEX price; the LME stock and cash-3m spread are the "
            "physical-tightness observables that the CFD price does not carry",
     "proxies": ("XCUUSD",),
     "basis_cost": "the CFD gives the price and not the inventory; every physical-tightness claim "
                   "in this pack is BLOCKED_ON_DATA until the stock series is collected"},
    {"name": "Cochilco and Codelco production and cost reports", "venue": "Cochilco / Codelco",
     "why": "monthly Chilean mine output and the C1 cash-cost curve -- the supply half of every "
            "copper claim, published free",
     "proxies": ("XCUUSD", "AUDUSD"),
     "basis_cost": "none; this is data rather than an instrument, and the lane fetches it"},
    {"name": "Chilean UF (Unidad de Fomento) and the inflation-linked curve", "venue": "BCCh",
     "why": "essentially all Chilean long-term contracts are UF-denominated, so the real rate is "
            "the country's actual discount rate and the nominal one is a derived quantity",
     "proxies": ("UST10Y",),
     "basis_cost": "UST10Y carries no Chilean term premium at all; the substitution measures the "
                   "global factor and declares the local one UNMEASURED"},
    {"name": "AFP multifondo balances and monthly switch volumes", "venue": "Superintendencia "
                                                                           "de Pensiones",
     "why": "the switch series IS the forced flow of CL-D, published monthly by fund and by AFP",
     "proxies": ("XCUUSD", "US500", "AUDUSD"),
     "basis_cost": "none; data rather than an instrument"},
)

# --------------------------------------------------------------------------- central banks
CENTRAL_BANK: dict[str, Any] = {
    "name": "Banco Central de Chile",
    "short": "BCCh",
    "framework": "inflation_targeter",
    "committee": "Consejo -- five members, Governor plus four, with staggered ten-year terms; "
                 "one of the longest-tenured boards of any inflation targeter",
    "policy_rate": "Tasa de Politica Monetaria (TPM), the overnight interbank target",
    "meetings_per_year": 8,
    "schedule_rule": (
        "EIGHT Reuniones de Politica Monetaria a year since 2018 (twelve before that). The "
        "calendar for the following year is published in advance. The decision is announced at "
        "18:00 Santiago on the SECOND day of the meeting, after the local market close, and the "
        "minutes follow about two weeks later."),
    "announce_local": "18:00 America/Santiago",
    "announce_utc": "21:00",
    "announce_utc_dst": "22:00",
    "dst_rule": ("CHILE OBSERVES DST AND MOVES IN THE OPPOSITE DIRECTION TO THE NORTHERN "
                 "HEMISPHERE: America/Santiago is UTC-3 from early September to early April and "
                 "UTC-4 otherwise. So the UTC minute of a Chilean announcement moves twice a "
                 "year, IN ANTIPHASE with the broker's own UTC+2/UTC+3 shift -- for part of the "
                 "year both clocks move and the bar offset changes by two hours, not one. This "
                 "is the single most common Chilean timestamp error and it is why every time in "
                 "this pack carries both a standard and a DST value. The Magallanes region stays "
                 "UTC-3 all year and is irrelevant to the market but appears in some data feeds."),
    "minutes_rule": "Minuta de la RPM about two weeks after the meeting; the IPoM (Informe de "
                    "Politica Monetaria) is quarterly -- March, June, September and December -- "
                    "and is presented to the Senate the following day, which is a SECOND event.",
    "inflation_target": "3% with a +/-1pp tolerance, over a two-year horizon",
    "fx_operations": (
        "Free float with PRE-ANNOUNCED, SIZED, DATED intervention programmes. The 2019-11-28 "
        "programme was USD 20bn (spot plus NDF) after the estallido social; the 2022-07-18 "
        "programme was USD 25bn. Both published daily amounts and an end date in advance, which "
        "makes Chile the pre-committed intervention case against Brazil's auction-by-auction "
        "approach and Argentina's opacity. The BCCh also runs a reserve ACCUMULATION programme "
        "when conditions allow, which is the same mechanism with the opposite sign."),
    "policy_rate_series": "BCCh BDE -- TPM daily series",
    "expected_rate_series": "BCCh Encuesta de Expectativas Economicas (EEE, monthly) and Encuesta "
                            "de Operadores Financieros (EOF, twice per meeting cycle). The EOF is "
                            "the closer object to a traded consensus and is published DAYS before "
                            "the meeting, which is what makes a surprise measurable at all.",
    "decision_dates": {
        2024: ("2024-01-31", "2024-04-02", "2024-05-24", "2024-06-18", "2024-07-31",
               "2024-09-03", "2024-10-17", "2024-12-17"),
        2025: ("2025-01-28", "2025-03-28", "2025-04-29", "2025-06-17", "2025-07-29",
               "2025-09-09", "2025-10-28", "2025-12-16"),
        2026: ("2026-01-27", "2026-03-24", "2026-04-28", "2026-06-16", "2026-07-28",
               "2026-09-08", "2026-10-27", "2026-12-15"),
    },
    "decision_dates_status": ("2024 and 2025 follow the published calendars. 2026 is DERIVED from "
                              "the BCCh's own eight-meeting rule and must be replaced by the "
                              "published calendar before any event study is read as confirmatory"),
    "root": "https://www.bcentral.cl",
}

#: PERU'S CENTRAL BANK, carried as a first-class section of this pack rather than a footnote.
CENTRAL_BANK_PE: dict[str, Any] = {
    "name": "Banco Central de Reserva del Peru",
    "short": "BCRP",
    "framework": "inflation_targeter",
    "committee": "Directorio -- seven members; the Governor has served across multiple political "
                 "regimes, which is itself the mechanism in PE-A",
    "policy_rate": "Tasa de interes de referencia",
    "meetings_per_year": 12,
    "schedule_rule": (
        "TWELVE meetings a year, monthly, on a calendar published a year ahead -- the highest "
        "meeting frequency in this command. The decision is announced at 18:00 Lima (23:00 UTC) "
        "on the THURSDAY, after the local close."),
    "announce_local": "18:00 America/Lima", "announce_utc": "23:00", "announce_utc_dst": "23:00",
    "dst_rule": "PERU HAS NO DST. America/Lima is UTC-5 all year, so 23:00 UTC is fixed -- the "
                "opposite of Chile, and the two decisions therefore drift apart by an hour twice "
                "a year even though both are announced at 18:00 local.",
    "inflation_target": "2% with a +/-1pp band -- the LOWEST target in Latin America, and the "
                        "reason Peruvian inflation expectations are the region's best anchored",
    "fx_operations": (
        "The BCRP intervenes CONTINUOUSLY and in DERIVATIVES: Certificados de Deposito Reajustable "
        "(CDR) and swaps cambiarios absorb hedging demand without spending reserves, plus spot "
        "sales in stress. Reserves have run near 30% of GDP, among the highest in the world for "
        "an economy this size. The consequence is that USD/PEN realised volatility is a POLICY "
        "OUTPUT, and any study reading sol stability as evidence of low political risk has the "
        "causality backwards."),
    "policy_rate_series": "BCRP series API -- tasa de referencia",
    "expected_rate_series": "BCRP Encuesta de Expectativas Macroeconomicas (monthly)",
    "meeting_rule_note": "monthly cadence means twelve events a year against Chile's eight, so a "
                         "pooled Andean policy-surprise study is unbalanced by construction and "
                         "must weight by country rather than by event",
    "root": "https://www.bcrp.gob.pe",
}

# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "Dolar observado (Chile)",
     "publisher": "Banco Central de Chile",
     "definition": "the weighted average of the PREVIOUS business day's interbank spot "
                   "transactions, published each business day and used as the legal reference "
                   "for contracts, tariffs and accounting",
     "windows_local": ("full previous session",), "windows_utc": ("12:00-21:00",),
     "published_local": "early morning, before the local open",
     "published_utc": "11:00", "published_utc_dst": "12:00",
     "dst_rule": "Chile shifts UTC-4/UTC-3 in antiphase with the northern hemisphere",
     "instruments": (),
     "why_it_matters": "it is BACKWARD-LOOKING by one full session and is nonetheless the legal "
                       "reference price, so Chilean contractual FX exposure is settled at a rate "
                       "the market has already moved away from -- a structural, dated basis",
     "trap": "a study that aligns dolar observado with the same day's market rate is off by one "
             "session, in the same way Korea's MAR is"},
    {"name": "Unidad de Fomento (UF)",
     "publisher": "Banco Central de Chile",
     "definition": "an inflation-indexed unit of account revalued DAILY from the previous month's "
                   "CPI print, published a month in advance",
     "windows_local": ("daily",), "windows_utc": ("daily",),
     "published_local": "the ninth of each month for the following month",
     "published_utc": "11:00", "published_utc_dst": "12:00", "dst_rule": "as above",
     "instruments": (),
     "why_it_matters": "essentially every Chilean long-dated contract is UF-denominated, so the "
                       "real rate is the economy's actual discount rate; the UF path for the "
                       "coming month is KNOWN, which makes near-term Chilean inflation carry "
                       "riskless within that window",
     "trap": "the known-in-advance window means a Chilean inflation surprise cannot move the "
             "front UF at all -- the surprise lives one month out, and an event study on the "
             "print date is looking at the wrong horizon"},
    {"name": "Tipo de cambio interbancario (Peru)",
     "publisher": "BCRP / SBS",
     "definition": "the SBS publishes a daily compra/venta reference from interbank transactions; "
                   "the BCRP publishes the interbank average",
     "windows_local": ("09:00-13:30",), "windows_utc": ("14:00-18:30",),
     "published_local": "end of session", "published_utc": "19:00", "published_utc_dst": "19:00",
     "dst_rule": "none -- Peru is UTC-5 year round",
     "instruments": (),
     "why_it_matters": "the level is a policy output; the INTERVENTION (spot sales, CDR and swap "
                       "auctions) is announced the same day and is the observable",
     "trap": "reading sol stability as market calm inverts the causality"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "Chilean FX spot", "kind": "weekday",
     "rule": "T+1 for CLP interbank (unusually short), T+2 for cross-border. The short cycle is "
             "why Chilean month-end flows are compressed into fewer sessions than Brazil's.",
     "window_utc": ("12:00", "21:00"), "instruments": ()},
    {"name": "AFP multifondo switch", "kind": "week_of_month",
     "rule": "A member switch request takes effect within days and the AFP must rebalance to the "
             "new mandate, including its offshore leg. Mass switches triggered by advisory "
             "newsletters have moved CLP and local rates within the same week.",
     "weekday": 2, "week_of_month": 0, "roll": "following",
     "window_utc": ("12:00", "21:00"), "instruments": ("US500", "XCUUSD")},
    {"name": "Copper export receipt", "kind": "month_end",
     "rule": "Concentrate and cathode shipments settle on provisional pricing with a final "
             "quotational period (usually M+3), so an export receipt is a LAGGED and REVISED "
             "function of the price -- the cash flow is not the spot price on the shipment date.",
     "months": (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12), "roll": "previous",
     "window_utc": ("12:00", "21:00"), "instruments": ("XCUUSD",)},
    {"name": "Codelco copper-law transfer and the fiscal rule", "kind": "quarter_end",
     "rule": "Chile runs a structural balance rule with two sovereign funds (FEES and FRP) fed by "
             "copper revenue above the reference price set by an independent committee. The "
             "reference price is published annually and IS the fiscal trigger level.",
     "months": (3, 6, 9, 12), "roll": "previous",
     "window_utc": ("12:00", "21:00"), "instruments": ("XCUUSD",)},
    {"name": "Peruvian canon minero transfer", "kind": "month_end",
     "rule": "Mining tax revenue is transferred to producing regions on a published schedule; the "
             "transfer is a regional fiscal event and a recurring trigger for local conflict when "
             "it disappoints, which is the PE-D mechanism.",
     "months": (6, 7), "roll": "following",
     "window_utc": ("14:00", "19:00"), "instruments": ("XCUUSD",)},
)

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Bolsa de Santiago", "index_symbols": (), "index_symbols_absent": ("IPSA",),
     "hours_local": "09:30-17:00 (continuous), with opening and closing auctions",
     "hours_utc": "12:30-20:00 (UTC-3 southern summer) / 13:30-21:00 (UTC-4)",
     "expiry_rule": "no liquid listed index derivative; the Chilean derivative market is OTC and "
                    "bank-intermediated, so there is NO expiry mechanism to mine here -- which is "
                    "itself the finding, and it is why CL has no expiry domain",
     "notes": "mining-heavy index; its beta to copper exceeds its beta to Chilean macro"},
    {"name": "Bolsa de Valores de Lima (BVL)", "index_symbols": (),
     "index_symbols_absent": ("SPBLPGPT",),
     "hours_local": "09:00-13:30", "hours_utc": "14:00-18:30",
     "expiry_rule": "no liquid listed derivatives; same finding as Santiago",
     "notes": "one of the smallest liquid equity markets in the Americas; its information content "
              "is dominated by two mining names and by the metal"},
    {"name": "COMEX and LME as the actual copper venues", "index_symbols": (),
     "index_symbols_absent": ("HG", "LME CA"),
     "hours_local": "COMEX 18:00-17:00 ET next day; LME rings plus 24h electronic",
     "hours_utc": "near-continuous",
     "expiry_rule": "COMEX HG expires on the third-last business day of the delivery month; LME "
                    "prompt dates are DAILY out to three months and then weekly and monthly -- an "
                    "entirely different structure from any other metal on this desk",
     "notes": "XCUUSD is a CFD on the COMEX price; the LME's daily prompt structure is where "
              "physical tightness prices, and it is not on this box"},
)

# --------------------------------------------------------------------------- holidays
_CL_HOLIDAYS: dict[int, dict[str, str]] = {
    2024: {
        "2024-01-01": "Ano Nuevo", "2024-03-29": "Viernes Santo",
        "2024-03-30": "Sabado Santo", "2024-05-01": "Dia del Trabajo",
        "2024-05-21": "Dia de las Glorias Navales",
        "2024-06-20": "Dia Nacional de los Pueblos Indigenas",
        "2024-06-29": "San Pedro y San Pablo", "2024-07-16": "Virgen del Carmen",
        "2024-08-15": "Asuncion de la Virgen", "2024-09-18": "Independencia Nacional",
        "2024-09-19": "Dia de las Glorias del Ejercito",
        "2024-09-20": "Feriado adicional de Fiestas Patrias",
        "2024-10-12": "Encuentro de Dos Mundos",
        "2024-10-31": "Dia de las Iglesias Evangelicas y Protestantes",
        "2024-11-01": "Dia de Todos los Santos", "2024-12-08": "Inmaculada Concepcion",
        "2024-12-25": "Navidad", "2024-12-31": "Feriado bancario",
    },
    2025: {
        "2025-01-01": "Ano Nuevo", "2025-04-18": "Viernes Santo",
        "2025-04-19": "Sabado Santo", "2025-05-01": "Dia del Trabajo",
        "2025-05-21": "Dia de las Glorias Navales",
        "2025-06-20": "Dia Nacional de los Pueblos Indigenas",
        "2025-06-29": "San Pedro y San Pablo", "2025-07-16": "Virgen del Carmen",
        "2025-08-15": "Asuncion de la Virgen", "2025-09-18": "Independencia Nacional",
        "2025-09-19": "Dia de las Glorias del Ejercito",
        "2025-10-12": "Encuentro de Dos Mundos",
        "2025-10-31": "Dia de las Iglesias Evangelicas y Protestantes",
        "2025-11-01": "Dia de Todos los Santos", "2025-12-08": "Inmaculada Concepcion",
        "2025-12-25": "Navidad", "2025-12-31": "Feriado bancario",
    },
    2026: {
        "2026-01-01": "Ano Nuevo", "2026-04-03": "Viernes Santo",
        "2026-04-04": "Sabado Santo", "2026-05-01": "Dia del Trabajo",
        "2026-05-21": "Dia de las Glorias Navales",
        "2026-06-20": "Dia Nacional de los Pueblos Indigenas",
        "2026-06-29": "San Pedro y San Pablo", "2026-07-16": "Virgen del Carmen",
        "2026-08-15": "Asuncion de la Virgen", "2026-09-18": "Independencia Nacional",
        "2026-09-19": "Dia de las Glorias del Ejercito",
        "2026-10-12": "Encuentro de Dos Mundos",
        "2026-10-31": "Dia de las Iglesias Evangelicas y Protestantes",
        "2026-11-01": "Dia de Todos los Santos", "2026-12-08": "Inmaculada Concepcion",
        "2026-12-25": "Navidad", "2026-12-31": "Feriado bancario",
    },
}

_PE_HOLIDAYS: dict[int, dict[str, str]] = {
    2024: {
        "2024-01-01": "Ano Nuevo", "2024-03-28": "Jueves Santo", "2024-03-29": "Viernes Santo",
        "2024-05-01": "Dia del Trabajo", "2024-06-07": "Batalla de Arica",
        "2024-06-29": "San Pedro y San Pablo", "2024-07-23": "Dia de las FFAA y PNP",
        "2024-07-28": "Fiestas Patrias", "2024-07-29": "Fiestas Patrias",
        "2024-08-06": "Batalla de Junin", "2024-08-30": "Santa Rosa de Lima",
        "2024-10-08": "Combate de Angamos", "2024-11-01": "Todos los Santos",
        "2024-12-08": "Inmaculada Concepcion", "2024-12-09": "Batalla de Ayacucho",
        "2024-12-25": "Navidad",
    },
    2025: {
        "2025-01-01": "Ano Nuevo", "2025-04-17": "Jueves Santo", "2025-04-18": "Viernes Santo",
        "2025-05-01": "Dia del Trabajo", "2025-06-07": "Batalla de Arica",
        "2025-06-29": "San Pedro y San Pablo", "2025-07-23": "Dia de las FFAA y PNP",
        "2025-07-28": "Fiestas Patrias", "2025-07-29": "Fiestas Patrias",
        "2025-08-06": "Batalla de Junin", "2025-08-30": "Santa Rosa de Lima",
        "2025-10-08": "Combate de Angamos", "2025-11-01": "Todos los Santos",
        "2025-12-08": "Inmaculada Concepcion", "2025-12-09": "Batalla de Ayacucho",
        "2025-12-25": "Navidad",
    },
    2026: {
        "2026-01-01": "Ano Nuevo", "2026-04-02": "Jueves Santo", "2026-04-03": "Viernes Santo",
        "2026-05-01": "Dia del Trabajo", "2026-06-07": "Batalla de Arica",
        "2026-06-29": "San Pedro y San Pablo", "2026-07-23": "Dia de las FFAA y PNP",
        "2026-07-28": "Fiestas Patrias", "2026-07-29": "Fiestas Patrias",
        "2026-08-06": "Batalla de Junin", "2026-08-30": "Santa Rosa de Lima",
        "2026-10-08": "Combate de Angamos", "2026-11-01": "Todos los Santos",
        "2026-12-08": "Inmaculada Concepcion", "2026-12-09": "Batalla de Ayacucho",
        "2026-12-25": "Navidad",
    },
}

HOLIDAYS_RULE: dict[str, Any] = {
    "rule": (
        "CHILE: Ley 19.973 fixes the national feriados; Viernes Santo and Sabado Santo are the "
        "Easter anchors (Chile closes on SATURDAY of Holy Week, which most Catholic countries do "
        "not, and it matters only for a Saturday-trading study). San Pedro y San Pablo (29 June), "
        "Encuentro de Dos Mundos (12 October) and the Iglesias Evangelicas day (31 October) MOVE "
        "to an adjacent Monday or Friday under the sandwich rules when they fall mid-week, so "
        "those three dates must be TABULATED from the official calendar and never computed. "
        "Fiestas Patrias (18-19 September) is the immovable anchor of the Chilean year and "
        "regularly gains a third bridging day by decree -- 20 September 2024 is an example and "
        "such decrees are not predictable. 31 December is a BANK holiday, not a national one, and "
        "the distinction matters because the FX market follows the bank calendar.\n"
        "PERU: the national feriados are fixed-date with no substitution law at all; Jueves Santo "
        "and Viernes Santo are the only movable ones. 7 June (Batalla de Arica) became a national "
        "holiday in 2021 and must not appear in an earlier sample. Peru adds ad-hoc 'dias no "
        "laborables' by decree for tourism, which close the public sector but NOT the exchange, "
        "and confusing the two produces phantom closures.\n"
        "Weekends are Saturday and Sunday in both countries."),
    "table": _CL_HOLIDAYS,
    "table_pe": _PE_HOLIDAYS,
    "years": (2024, 2025, 2026),
    "status": {2024: "CONFIRMED", 2025: "CONFIRMED",
               2026: "DERIVED from the statute; the official Chilean feriados list and any "
                     "bridging decree are the authority and neither is knowable in advance"},
    "weekly_closed": (5, 6),
    "note": "the Chilean and Peruvian tables OVERLAP on only four dates a year, which makes each "
            "country's closures a natural liquidity control for the other's mining flow",
}


def holidays(year: int, *, country: str = "cl") -> dict[str, str]:
    """One year of closures for `cl` or `pe`; `{}` for a year this pack does not declare."""
    table = _PE_HOLIDAYS if str(country).lower() in ("pe", "peru") else _CL_HOLIDAYS
    return dict(table.get(year) or {})


def is_closed(day: date, *, country: str = "cl") -> bool:
    """True when the named country's market is closed on `day` (weekends included)."""
    return day.weekday() >= 5 or day.isoformat() in holidays(day.year, country=country)


# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "CFTC Commitments of Traders -- COMEX copper (HG)",
     "publisher": "CFTC", "frequency": "weekly", "lag": "Friday 15:30 ET for Tuesday positions",
     "field": "non-commercial net, open interest",
     "why": "the only positioning series in this pack that the desk ALREADY HOLDS: "
            "data/axes/cot.json maps XCUUSD. It is the speculative copper position, which is the "
            "closest available proxy for the Andean risk position.",
     "pit": True, "status": "AVAILABLE on this box"},
    {"name": "LME Commitments of Traders and warehouse stock",
     "publisher": "LME", "frequency": "weekly (COT) and daily (stock)",
     "lag": "one session", "field": "investment-fund net; on-warrant and off-warrant tonnage",
     "why": "physical tightness is an LME object; the COMEX price does not carry it",
     "pit": True, "status": "declared; not collected -- every physical-tightness claim here is "
                            "BLOCKED_ON_DATA and says so"},
    {"name": "AFP multifondo balances and switch volumes",
     "publisher": "Superintendencia de Pensiones (Chile)", "frequency": "monthly",
     "lag": "about 20 days", "field": "assets by fund A-E, by AFP, and transfer counts",
     "why": "the switch series is the direct observable of Chile's unique forced flow",
     "pit": True, "status": "declared; free monthly series, not yet collected"},
    {"name": "BCRP CDR and swap cambiario outstanding",
     "publisher": "BCRP", "frequency": "daily", "lag": "same day",
     "field": "outstanding balance of CDR and swaps",
     "why": "the Peruvian intervention observable; it is how the sol's volatility is suppressed "
            "without spending reserves",
     "pit": True, "status": "declared; BCRP series API, code not yet resolved"},
)

# --------------------------------------------------------------------------- terminology
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "policy_cl": ("TPM", "Tasa de Politica Monetaria", "Consejo", "RPM",
                  "Reunion de Politica Monetaria", "IPoM", "Informe de Politica Monetaria",
                  "Banco Central de Chile", "BCCh", "meta de inflacion", "IPC", "UF",
                  "Unidad de Fomento", "encaje", "expansiva", "contractiva", "sesgo"),
    "policy_pe": ("BCRP", "tasa de referencia", "Directorio", "Reporte de Inflacion",
                  "encuesta de expectativas", "MEF", "SBS", "encaje en soles",
                  "encaje en dolares", "certificado de deposito", "CDR", "swap cambiario"),
    "fx": ("dolar observado", "dolar acuerdo", "tipo de cambio nominal", "brecha cambiaria",
           "intervencion cambiaria", "programa de intervencion", "acumulacion de reservas",
           "forward cambiario", "NDF", "peso chileno", "sol", "nuevo sol", "tipo de cambio "
           "interbancario", "posicion de cambio", "carry"),
    "copper": ("cobre", "cobre refinado", "catodo", "concentrado", "libra de cobre",
               "precio del cobre", "Cochilco", "Codelco", "Escondida", "Collahuasi",
               "Antofagasta Minerals", "Las Bambas", "Antamina", "Cerro Verde", "Toquepala",
               "ley del mineral", "huelga", "negociacion colectiva", "paralizacion",
               "bloqueo de carretera", "corredor minero", "canon minero", "royalty minero",
               "precio de referencia del cobre", "molibdeno"),
    "pensions": ("AFP", "multifondos", "fondo A", "fondo E", "cambio de fondo",
                 "Felices y Forrados", "retiro de fondos", "retiro del 10%",
                 "Superintendencia de Pensiones", "rentabilidad del fondo", "inversion en el "
                 "exterior", "limite de inversion"),
    "politics": ("estallido social", "proceso constituyente", "plebiscito", "rechazo",
                 "apruebo", "regla fiscal", "balance estructural", "FEES", "FRP",
                 "conflicto social", "protesta", "estado de emergencia", "vacancia "
                 "presidencial", "Congreso"),
    "community": ("Rankia Chile", "Rankia Peru", "Diario Financiero", "El Mercurio Inversiones",
                  "Pulso", "Gestion", "Semana Economica", "trader chileno", "inversionista "
                  "peruano"),
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
    {"id": "cl_bcch_bde", "layer": "official",
     "label": "BCCh Base de Datos Estadisticos (SieteRestWS)",
     "roots": ("https://si3.bcentral.cl/SieteRestWS/SieteRestWS.ashx",
               "https://si3.bcentral.cl/Siete/",
               "https://www.bcentral.cl/web/banco-central/areas/estadisticas"),
     "languages": ("es-CL", "en"),
     "licence": "free, but REQUIRES a registered user and password as query parameters",
     "access_label": "PUBLIC_WITH_TERMS", "credibility": "AUTHORITATIVE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("serie historica TPM tasa de politica monetaria diaria",
                 "tipo de cambio nominal dolar observado serie",
                 "IMACEC minero y no minero serie mensual",
                 "estadisticas del repositorio de derivados forwards vigentes"),
     "notes": "the only credentialed source in this command besides Banxico. GetSeries returns "
              "an Obs list with a statusCode that distinguishes provisional from published -- "
              "and a PROVISIONAL value is the point-in-time value, so it is kept"},
    {"id": "pe_bcrp_api", "layer": "official",
     "label": "BCRP estadisticas series API",
     "roots": ("https://estadisticas.bcrp.gob.pe/estadisticas/series/api/",
               "https://estadisticas.bcrp.gob.pe/estadisticas/series/"),
     "languages": ("es-PE", "en"),
     "licence": "public, no key: /api/{series}/{json|csv|xml}/{start}/{end}/{lang}",
     "access_label": "OPEN_DATA", "credibility": "AUTHORITATIVE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("tasa de interes de referencia BCRP serie mensual",
                 "tipo de cambio interbancario promedio venta",
                 "reservas internacionales netas serie",
                 "terminos de intercambio indice exportaciones importaciones"),
     "notes": "one of the cleanest free central-bank APIs anywhere: three formats, no "
              "registration, a browsable catalogue, Spanish or English labels"},
    {"id": "cl_pe_stats_offices", "layer": "official",
     "label": "INE Chile, INEI Peru and the two finance ministries",
     "roots": ("https://www.ine.gob.cl/estadisticas", "https://www.inei.gob.pe/",
               "https://www.dipres.gob.cl/", "https://www.mef.gob.pe/"),
     "languages": ("es-CL", "es-PE"), "licence": "public open data",
     "access_label": "OPEN_DATA", "credibility": "AUTHORITATIVE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("IPC mensual variacion INE Chile",
                 "balance estructural informe de finanzas publicas",
                 "precio de referencia del cobre comite de expertos",
                 "canon minero transferencias por region"),
     "notes": "the fiscal side. The Chilean structural-balance rule's REFERENCE COPPER PRICE is "
              "published here and it is the only explicit policy threshold in this command"},
    {"id": "cl_cochilco_minem", "layer": "institutional",
     "label": "Cochilco (Chilean state copper commission) and MINEM Peru",
     "roots": ("https://www.cochilco.cl/", "https://www.minem.gob.pe/estadisticas",
               "https://www.codelco.com/memoria/"),
     "languages": ("es-CL", "es-PE"),
     "licence": "public statistics; bulletins as XLS and PDF",
     "access_label": "OPEN_DATA", "credibility": "AUTHORITATIVE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("produccion de cobre por empresa y por mina mensual",
                 "costo C1 cash cost mineria del cobre",
                 "produccion minera por region y por mineral Peru",
                 "ley del mineral caida de leyes cobre"),
     "notes": "the SUPPLY half of every copper claim. The regional split in Peru is what makes a "
              "corredor-minero blockade attributable to an output loss rather than a headline"},
    {"id": "cl_pe_exchanges_regulators", "layer": "institutional",
     "label": "Bolsa de Santiago, BVL, CMF, SMV and the Superintendencia de Pensiones",
     "roots": ("https://www.bolsadesantiago.com/", "https://www.bvl.com.pe/",
               "https://www.cmfchile.cl/", "https://www.smv.gob.pe/",
               "https://www.spensiones.cl/apps/loadEstadisticas/"),
     "languages": ("es-CL", "es-PE"),
     "licence": "public summary data and public statistics; depth is licensed",
     "access_label": "PUBLIC_WITH_TERMS", "credibility": "AUTHORITATIVE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("traspasos entre fondos A y E multifondos estadisticas",
                 "inversion en el exterior AFP limite",
                 "feriados bursatiles bolsa de santiago calendario",
                 "hecho esencial CMF mineras"),
     "notes": "the AFP multifondo transfer series is here and it is the direct observable of "
              "CL-D: the only forced flow in this command whose trigger is a newsletter"},
    {"id": "cl_pe_academic", "layer": "academic",
     "label": "Andean economics research (BCCh and BCRP working papers, SciELO, CEP, PUC)",
     "roots": ("https://www.bcentral.cl/web/banco-central/areas/investigacion",
               "https://www.bcrp.gob.pe/publicaciones/documentos-de-trabajo.html",
               "https://scielo.conicyt.cl/", "https://www.cepchile.cl/"),
     "languages": ("es-CL", "es-PE", "en"),
     "licence": "open access working papers and open-access journals",
     "access_label": "PUBLIC", "credibility": "RELIABLE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("traspaso del precio del cobre al tipo de cambio Chile",
                 "efecto de los retiros de fondos de pensiones sobre tasas",
                 "dolarizacion e intervencion cambiaria Peru documento de trabajo",
                 "regla fiscal estructural cobre evaluacion"),
     "notes": "the BCCh and BCRP working-paper series are where the intervention mechanisms are "
              "documented by the institutions that run them -- a claim, still, not a privilege"},
    {"id": "cl_pe_practitioner", "layer": "practitioner",
     "label": "Andean sell-side and fund-manager research",
     "roots": ("https://www.larrainvial.com/estudios", "https://www.credicorpcapital.com/",
               "https://www.btgpactual.cl/research", "https://www.rankia.cl/foros/bolsa/"),
     "languages": ("es-CL", "es-PE"),
     "licence": "public web with terms; claims extracted only, nothing republished",
     "access_label": "PUBLIC_WITH_TERMS", "credibility": "RELIABLE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("informe de mercado cobre proyeccion precio",
                 "recomendacion cambio de fondo AFP estrategia",
                 "carry en pesos chilenos y forward cambiario",
                 "riesgo de huelga mineria negociacion colectiva informe"),
     "notes": "the professional half. Strike-risk notes from Chilean sell-side desks carry the "
              "collective-bargaining calendar that CL-C needs and that no English source lists"},
    {"id": "cl_pe_retail_ecology", "layer": "retail_ecology",
     "label": "Andean retail investor communities and the AFP advisory culture",
     "roots": ("https://www.rankia.cl/", "https://www.rankia.pe/",
               "https://www.reddit.com/r/chile/", "https://www.reddit.com/r/PERU/",
               "https://www.facebook.com/groups/inversionistaschile/"),
     "languages": ("es-CL", "es-PE"),
     "licence": "public social; user-submitted content, nothing republished",
     "access_label": "PUBLIC_SOCIAL", "credibility": "UNRELIABLE",
     "predictive_state": "NARRATIVE_FEATURE", "machine_use_allowed": True,
     "queries": ("cambio de fondo E a A recomendacion hoy",
                 "Felices y Forrados senal cambio de fondo",
                 "invertir dolares en Chile como comprar",
                 "retiro de fondos AFP proyecto de ley foro",
                 "cuanto rinde el fondo A este mes"),
     "notes": "UNRELIABLE AND THE MECHANISM ITSELF. CL-D is a flow triggered by advisory calls "
              "made in exactly these venues; the advice being wrong is irrelevant to whether the "
              "AFPs then have to rebalance an offshore book"},
    {"id": "cl_pe_app_ecosystem", "layer": "app_ecosystem",
     "label": "Andean retail platforms, robo-advisers and automation",
     "roots": ("https://fintual.cl/", "https://www.racional.cl/", "https://www.vectorcapital.cl/",
               "https://www.mql5.com/es/code", "https://www.renta4.cl/"),
     "languages": ("es-CL", "es-PE"),
     "licence": "public web with terms; public code repositories",
     "access_label": "PUBLIC_WITH_TERMS", "credibility": "UNRELIABLE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("bot de trading cobre estrategia automatizada",
                 "roboadvisor chileno perfil de riesgo cartera",
                 "operar futuros de cobre desde Chile broker",
                 "traspaso automatico de fondos AFP aplicacion"),
     "notes": "the Chilean roboadviser layer matters because it INTERMEDIATES the multifondo "
              "switch: when an app makes the switch one tap away, the flow's speed changes, and "
              "that is a datable structural break in CL-D rather than a product detail"},
    {"id": "cl_pe_media", "layer": "media",
     "label": "Andean financial press",
     "roots": ("https://www.df.cl/", "https://www.elmercurio.com/inversiones/",
               "https://gestion.pe/", "https://semanaeconomica.com/", "https://www.latercera.com/"),
     "languages": ("es-CL", "es-PE"),
     "licence": "public web with terms; several paywalled, nothing republished",
     "access_label": "PUBLIC_WITH_TERMS", "credibility": "RELIABLE",
     "predictive_state": "NARRATIVE_FEATURE", "machine_use_allowed": True,
     "queries": ("huelga en Escondida sindicato negociacion",
                 "bloqueo corredor minero Las Bambas comunidades",
                 "intervencion cambiaria banco central anuncio programa",
                 "vacancia presidencial mercados reaccion"),
     "notes": "THE SPANISH LEAD TIME IS THE REASON THIS LAYER EARNS ITS TRIAL CHARGE. Strike "
              "notices and blockade reports appear here days before the English wire, and CL-K's "
              "control is the same claim dated to its English publication instead"},
    {"id": "cl_pe_archive", "layer": "archive",
     "label": "Historical archives: Memoria Chilena, BCCh bulletins, Diario Oficial, El Peruano",
     "roots": ("https://www.memoriachilena.gob.cl/", "https://www.diariooficial.interior.gob.cl/",
               "https://diariooficial.elperuano.pe/",
               "https://web.archive.org/web/*/bcentral.cl/*"),
     "languages": ("es-CL", "es-PE"),
     "licence": "public archive; digitised public-domain and official gazettes",
     "access_label": "PUBLIC_ARCHIVE", "credibility": "AUTHORITATIVE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("ley de feriados 19973 texto traslado feriados",
                 "anuncio programa de intervencion cambiaria 2019 comunicado",
                 "reforma royalty minero texto publicado",
                 "ley de retiro de fondos de pensiones publicacion"),
     "notes": "the era table's PRIMARY evidence. Every intervention programme, royalty reform and "
              "withdrawal law in POLICY_ERAS is dated by its gazette entry, not by a press report"},
    {"id": "cl_pe_physical_economy", "layer": "physical_economy",
     "label": "Physical flow: ports, power, labour registries and conflict counts",
     "roots": ("https://www.directemar.cl/", "https://www.apn.gob.pe/estadisticas/",
               "https://www.coordinador.cl/mercados/", "https://www.dt.gob.cl/portal/1626/w3-"
                                                       "propertyvalue-22271.html",
               "https://www.defensoria.gob.pe/areas_tematicas/conflictos-sociales/"),
     "languages": ("es-CL", "es-PE"),
     "licence": "public open data and public institutional reports",
     "access_label": "OPEN_DATA", "credibility": "AUTHORITATIVE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("embarques de concentrado de cobre puerto estadistica",
                 "consumo electrico mineria sistema electrico nacional",
                 "negociacion colectiva registro direccion del trabajo mineria",
                 "reporte mensual de conflictos sociales defensoria del pueblo"),
     "notes": "COUNTED PHYSICAL QUANTITIES. Mine electricity draw is a near-real-time proxy for "
              "whether a stoppage is actually stopping anything, and the Defensoria's monthly "
              "conflict count is the only systematic series for Peruvian blockade risk"},
    {"id": "cl_pe_source_graph", "layer": "source_graph",
     "label": "The graph that finds the NEXT Andean source",
     "roots": ("https://www.bcentral.cl/web/banco-central/areas/investigacion",
               "https://datos.gob.cl/", "https://www.datosabiertos.gob.pe/",
               "https://www.cesco.cl/publicaciones/"),
     "languages": ("es-CL", "es-PE", "en"),
     "licence": "public; open-data catalogues, reference sections and conference proceedings",
     "access_label": "PUBLIC", "credibility": "RELIABLE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("catalogo de datos abiertos cobre mineria conjunto",
                 "quien cita las estadisticas de Cochilco fuente",
                 "actas seminario CESCO cobre referencias",
                 "documentos de trabajo BCRP bibliografia fuente de datos"),
     "notes": "THE PROCEDURE, NOT A LIST. The two national open-data catalogues and the copper "
              "conference proceedings are where a source this pack has not heard of is found, "
              "and following them is what keeps the other nine layers from freezing"},
)

#: A layer with no source is named here WITH A REASON. All ten are currently reached for the
#: Andean pair; the entry that would appear here first is a Peruvian app ecosystem thin enough to
#: be indistinguishable from the Chilean one, which is a judgement to record rather than assume.
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
    {"name": "TPM -- Chilean policy rate (BCCh BDE)", "source": "cl_bcch_bde",
     "coverage": "1995 to present", "frequency": "daily step",
     "publication_lag_days": 0.0, "revisions": "none", "licence": "free with registration",
     "history_from": "1995-01-02", "pit_feasible": True,
     "assets": ("XCUUSD", "AUDUSD", "UST10Y"),
     "mechanism_families": ("central_bank_surprise", "carry_funding"),
     "how_to_fetch": "SieteRestWS GetSeries with user and pass from latam_apis.json"},
    {"name": "Dolar observado (BCCh BDE)", "source": "cl_bcch_bde",
     "coverage": "1977 to present", "frequency": "daily",
     "publication_lag_days": 1.0, "revisions": "none",
     "licence": "free with registration", "history_from": "1977-01-03", "pit_feasible": True,
     "assets": ("XCUUSD", "AUDUSD", "USDBRL"),
     "mechanism_families": ("calendar_settlement", "session_microstructure"),
     "how_to_fetch": "SieteRestWS GetSeries; the value is the PREVIOUS session's average and the "
                     "one-session offset must be carried into every alignment"},
    {"name": "IMACEC -- monthly activity index (BCCh)", "source": "cl_bcch_bde",
     "coverage": "1986 to present", "frequency": "monthly",
     "publication_lag_days": 32.0, "revisions": "revised for two months then annually",
     "licence": "free with registration", "history_from": "1986-01-31", "pit_feasible": True,
     "assets": ("XCUUSD", "AUDUSD"),
     "mechanism_families": ("release_surprise",),
     "how_to_fetch": "SieteRestWS GetSeries; the mining and non-mining split is the useful pair"},
    {"name": "Chilean copper exports and the copper price series (BCCh / Cochilco)",
     "source": "cl_cochilco",
     "coverage": "1990 to present", "frequency": "monthly",
     "publication_lag_days": 20.0, "revisions": "revised once", "licence": "public",
     "history_from": "1990-01-31", "pit_feasible": True,
     "assets": ("XCUUSD", "AUDUSD", "USDCNH"),
     "mechanism_families": ("corporate_flow", "release_surprise"),
     "how_to_fetch": "Cochilco statistical bulletins (XLS) and the BCCh external-sector series"},
    {"name": "Chilean derivatives-repository statistics (BCCh)", "source": "cl_bcch_bde",
     "coverage": "2013 to present", "frequency": "monthly",
     "publication_lag_days": 30.0, "revisions": "occasional restatement",
     "licence": "free with registration", "history_from": "2013-01-31", "pit_feasible": True,
     "assets": ("XCUUSD", "AUDUSD"),
     "mechanism_families": ("positioning", "institutional_flow"),
     "how_to_fetch": "SieteRestWS; the NDF and forward outstanding by counterparty sector is the "
                     "closest thing to a Chilean positioning series that exists"},
    {"name": "AFP multifondo balances and transfers", "source": "cl_pensiones",
     "coverage": "2002 to present", "frequency": "monthly",
     "publication_lag_days": 20.0, "revisions": "none", "licence": "public open statistics",
     "history_from": "2002-09-30", "pit_feasible": True,
     "assets": ("US500", "XCUUSD", "AUDUSD"),
     "mechanism_families": ("institutional_flow", "positioning"),
     "how_to_fetch": "spensiones.cl statistical series; monthly XLS"},
    {"name": "BCRP reference rate and monetary statistics", "source": "pe_bcrp_api",
     "coverage": "1994 to present", "frequency": "monthly and daily",
     "publication_lag_days": 0.0, "revisions": "none for the rate", "licence": "public, no key",
     "history_from": "1994-01-03", "pit_feasible": True,
     "assets": ("XCUUSD", "USDBRL"),
     "mechanism_families": ("central_bank_surprise", "carry_funding"),
     "how_to_fetch": "GET estadisticas.bcrp.gob.pe/estadisticas/series/api/{series}/json/"
                     "{start}/{end}/ing"},
    {"name": "Peruvian copper, gold and silver exports (BCRP / MINEM)", "source": "pe_bcrp_api",
     "coverage": "1990 to present", "frequency": "monthly",
     "publication_lag_days": 30.0, "revisions": "revised once",
     "licence": "public, no key", "history_from": "1990-01-31", "pit_feasible": True,
     "assets": ("XCUUSD", "XAUUSD", "XAGUSD"),
     "mechanism_families": ("corporate_flow", "release_surprise"),
     "how_to_fetch": "BCRP series API; MINEM publishes the by-mine and by-region detail"},
    {"name": "Peruvian international reserves and the BCRP intervention book",
     "source": "pe_bcrp_api",
     "coverage": "1990 to present", "frequency": "daily and monthly",
     "publication_lag_days": 1.0, "revisions": "none", "licence": "public, no key",
     "history_from": "1990-01-02", "pit_feasible": True,
     "assets": ("XCUUSD", "XAUUSD"),
     "mechanism_families": ("institutional_flow", "carry_funding"),
     "how_to_fetch": "BCRP series API; reserves, CDR outstanding and swap balances"},
    {"name": "Peruvian terms of trade index (BCRP)", "source": "pe_bcrp_api",
     "coverage": "1991 to present", "frequency": "monthly",
     "publication_lag_days": 30.0, "revisions": "rebased periodically",
     "licence": "public, no key", "history_from": "1991-01-31", "pit_feasible": True,
     "assets": ("XCUUSD", "XAUUSD", "AUDUSD"),
     "mechanism_families": ("release_surprise", "transfer"),
     "how_to_fetch": "BCRP series API; export and import price indices separately, because the "
                     "RATIO hides which leg moved"},
    {"name": "Chilean and Peruvian mine-level production and strike calendar",
     "source": "pe_minem_inei",
     "coverage": "2005 to present", "frequency": "monthly",
     "publication_lag_days": 45.0,
     "revisions": "restated when a mine reports late",
     "licence": "public open data", "history_from": "2005-01-31", "pit_feasible": True,
     "assets": ("XCUUSD", "XAUUSD", "XAGUSD", "XZNUSD"),
     "mechanism_families": ("corporate_flow", "failure"),
     "how_to_fetch": "MINEM monthly mining statistics and Cochilco's Chilean equivalent; the "
                     "STRIKE dates come from the collective-bargaining registry and the press"},
    {"name": "Andean practitioner and press mechanism claims (es-CL, es-PE)",
     "source": "andean_press",
     "coverage": "rolling", "frequency": "continuous",
     "publication_lag_days": 0.0, "revisions": "n/a -- dated at capture",
     "licence": "public web, claims only", "history_from": "2015-01-01", "pit_feasible": False,
     "assets": ("XCUUSD", "AUDUSD"),
     "mechanism_families": ("scouts", "transfer"),
     "how_to_fetch": "deep_forest_miner grounds in Spanish; strike notices and blockade reports "
                     "appear here days before the English wire"},
)

# --------------------------------------------------------------------------- actors
ACTORS: tuple[dict[str, Any], ...] = (
    {"name": "Codelco (state copper producer)",
     "holds": "the world's largest copper reserve base and a declining ore grade",
     "forced_to": ("transfer copper revenue to the Chilean fisc under the copper law",
                   "sustain output through a large capital programme regardless of price",
                   "sell forward a share of production to fund capex"),
     "when": "continuous production; quarterly fiscal transfers; annual capex commitments",
     "information": ("Cochilco production data", "the C1 cost curve", "grade decline reports"),
     "constraints": ("state ownership makes output a political variable, not a margin decision",
                     "falling ore grade raises unit cost every year regardless of price"),
     "instruments": ("XCUUSD",),
     "counterparties": ("Chinese smelters", "traders", "the Chilean Treasury"),
     "observables": ("monthly production", "cash cost", "announced capex"),
     "impact": "a supply floor that does NOT respond to price the way a private producer's does; "
               "the grade decline is a slow structural tightening",
     "persistence": "structural, years",
     "falsifier": "Chilean output shows the same price elasticity as private producers' once "
                  "grade decline is controlled for, which would remove the state-ownership term",
     "notes": "state-owned and unlisted, so no two-lane conflict can arise"},
    {"name": "private Chilean mine operator (Escondida, Collahuasi, Los Pelambres)",
     "holds": "large concentrating operations with unionised workforces on fixed contract cycles",
     "forced_to": ("renegotiate collective contracts on a published schedule, typically every "
                   "three to four years",
                   "run at capacity when the price clears cash cost"),
     "when": "contract expiry dates are KNOWN YEARS AHEAD; the strike risk window is datable",
     "information": ("union statements", "the collective-bargaining registry", "press"),
     "constraints": ("labour law fixes the negotiation timetable",
                     "a strike at a single mine can remove one to two percent of world supply"),
     "instruments": ("XCUUSD", "AUDUSD"),
     "counterparties": ("unions", "Chinese smelters", "the government as mediator"),
     "observables": ("contract expiry calendar", "strike votes", "production guidance cuts"),
     "impact": "the only commodity supply disruption on this desk whose RISK WINDOW is announced "
               "in advance by a negotiation timetable",
     "persistence": "an actual stoppage lasts weeks; the anticipation window lasts months",
     "falsifier": "no copper price or term-structure response in the weeks around known contract "
                  "expiries relative to matched control windows",
     "notes": "the datable-risk-window property is what makes CL-C worth a trial charge"},
    {"name": "Peruvian mine operator facing social conflict",
     "holds": "operations along the corredor minero del sur, dependent on one road",
     "forced_to": ("halt or slow shipments when a community blockade closes the corridor",
                   "negotiate local agreements that are renegotiated after each election"),
     "when": "clusters with the political calendar, the canon minero transfer and the rainy season",
     "information": ("Defensoria del Pueblo conflict reports", "regional press", "MINEM output"),
     "constraints": ("a single road carries the concentrate from several mines",
                     "the state's ability to clear a blockade is politically bounded"),
     "instruments": ("XCUUSD", "XAUUSD", "XZNUSD"),
     "counterparties": ("local communities", "regional governments", "Chinese owners"),
     "observables": ("Defensoria monthly conflict count", "MINEM regional output",
                     "blockade reports"),
     "impact": "a supply interruption with a LOCAL political trigger rather than a price one; "
               "unlike a Chilean strike it is not on a calendar, which makes it the natural "
               "control for 'is the effect the disruption or the anticipation of it'",
     "persistence": "days to weeks per episode; the conflict COUNT is persistent",
     "falsifier": "copper shows no response to Peruvian conflict episodes of a size that moves "
                  "MINEM regional output, which would mean the market prices only Chilean supply",
     "notes": "Chile and Peru as each other's controls is the reason the two share a pack"},
    {"name": "Chilean AFP pension manager",
     "holds": "member balances across five funds with a legally capped foreign-investment share",
     "forced_to": ("rebalance the offshore leg within days when members switch funds en masse",
                   "liquidate assets on the statutory schedule when a withdrawal law passes"),
     "when": "switch-driven and irregular; the 2020-2021 withdrawal laws were the extreme case",
     "information": ("switch volumes", "the advisory newsletters that trigger them",
                     "legislated withdrawal windows"),
     "constraints": ("the member's switch right is statutory and cannot be refused",
                     "foreign-investment limits are regulatory",
                     "a withdrawal law forces asset sales on a legislated timetable"),
     "instruments": ("US500", "XCUUSD", "AUDUSD", "UST10Y"),
     "counterparties": ("global asset managers", "local banks", "the sovereign"),
     "observables": ("monthly transfers between funds", "the foreign share", "fund assets"),
     "impact": "a large, dated, INVOLUNTARY cross-border flow triggered by a newsletter rather "
               "than by a macro variable -- the cleanest example of reflexive retail coordination "
               "moving an institutional book anywhere in this command",
     "persistence": "episodic, days to weeks; the 2020-21 withdrawals were a regime of their own",
     "falsifier": "no CLP, local-rate or offshore-asset response around large measured switch "
                  "months once the copper price and the global risk factor are controlled for",
     "notes": "Chile's genuinely unique mechanism; nothing else in this command has it"},
    {"name": "Chinese smelter and the treatment-charge negotiation",
     "holds": "smelting capacity that must be fed with Andean concentrate",
     "forced_to": ("contract annual benchmark treatment and refining charges each autumn",
                   "bid for spot concentrate when the benchmark is tight"),
     "when": "the benchmark round runs September to December each year",
     "information": ("spot TC/RC indices", "Andean production guidance", "smelter utilisation"),
     "constraints": ("capacity is fixed in the short run and heavily expanded in the long run",
                     "a negative spot TC means smelters pay for the right to smelt"),
     "instruments": ("XCUUSD", "USDCNH", "CHINAH"),
     "counterparties": ("Codelco", "Antofagasta", "Peruvian producers", "traders"),
     "observables": ("the annual TC/RC benchmark", "spot TC indices", "Chinese imports"),
     "impact": "the TC/RC benchmark is a direct, dated, annual read on whether the CONCENTRATE "
               "market is tight -- a supply-side signal independent of the refined price",
     "persistence": "annual contract, quarterly spot drift",
     "falsifier": "the benchmark round carries no information for the refined price beyond what "
                  "mine production guidance already carries",
     "notes": "the Chinese leg of the copper cross-region triple"},
    {"name": "Chilean fiscal authority under the structural balance rule",
     "holds": "a budget calibrated to a REFERENCE copper price set by an independent committee",
     "forced_to": ("save copper revenue above the reference price into the sovereign funds",
                   "adjust spending when the structural balance target is missed"),
     "when": "the reference price is set annually; the fiscal reports are quarterly",
     "information": ("the committee's reference price", "actual copper revenue",
                     "the structural balance"),
     "constraints": ("the fiscal rule is law and the reference price is set by outside experts, "
                     "not by the government",),
     "instruments": ("XCUUSD", "UST10Y"),
     "counterparties": ("sovereign funds", "bondholders", "Codelco"),
     "observables": ("the reference price", "FEES and FRP balances", "the structural balance"),
     "impact": "an explicit, published THRESHOLD on the copper price at which Chilean fiscal "
               "behaviour changes -- a rare case of a policy discontinuity with a public number",
     "persistence": "annual, with the threshold re-set each year",
     "falsifier": "no discontinuity in Chilean spreads, the peso proxy set or sovereign-fund "
                  "flows around the published reference price",
     "notes": "the threshold is the research object; the level of the copper price is not"},
    {"name": "BCRP as a continuous FX intervenor",
     "holds": "reserves near 30% of GDP plus a CDR and swap book",
     "forced_to": ("absorb hedging demand through derivatives rather than spot",
                   "announce and roll CDR and swap auctions"),
     "when": "continuous; auctions are announced intraday",
     "information": ("the interbank rate", "hedging demand from pension funds and corporates",
                     "the dollarisation ratio"),
     "constraints": ("a partially dollarised economy makes FX depreciation a balance-sheet event, "
                     "not just a competitiveness one",
                     "the derivative route avoids spending reserves"),
     "instruments": ("XCUUSD", "XAUUSD"),
     "counterparties": ("local banks", "AFPs", "corporates"),
     "observables": ("CDR and swap outstanding", "reserves", "announced auctions"),
     "impact": "sol volatility is SUPPRESSED as policy, which makes Peru the control case for "
               "'does political risk move a currency' -- the answer there is 'not if the central "
               "bank does not let it'",
     "persistence": "permanent under the current framework",
     "falsifier": "USD/PEN realised volatility shows no relationship to the CDR and swap "
                  "outstanding once copper and the dollar factor are controlled for",
     "notes": "the Peruvian FX leg is largely unmeasurable here and the pack says so"},
    {"name": "Peruvian pension fund (AFP Peru) and the dollarised saver",
     "holds": "soles liabilities against a portfolio with a large and rising offshore share",
     "forced_to": ("hedge or not hedge the offshore leg depending on the CDR's price",
                   "liquidate on legislated withdrawal windows, as in 2020-2022"),
     "when": "monthly rebalancing; withdrawal laws are episodic and legislated",
     "information": ("the BCRP's hedging cost", "the offshore limit", "withdrawal legislation"),
     "constraints": ("SBS investment limits", "congressional withdrawal laws that arrive with "
                     "weeks of notice"),
     "instruments": ("XCUUSD", "US500", "XAUUSD"),
     "counterparties": ("the BCRP", "global managers", "local banks"),
     "observables": ("AFP portfolio reports", "CDR outstanding", "withdrawal volumes"),
     "impact": "the Peruvian analogue of the Chilean AFP flow, with the same legislated-withdrawal "
               "shock and a different hedging mechanism -- so the pair identifies which half of "
               "the Chilean effect is the withdrawal and which half is the hedge",
     "persistence": "episodic",
     "falsifier": "Peruvian withdrawal windows produce no measurable offshore-asset or FX effect "
                  "while Chilean ones do, with no institutional difference to explain it",
     "notes": "the cross-country pair is the identification strategy"},
    {"name": "copper concentrate trader",
     "holds": "cargoes priced on a provisional basis with a quotational period months ahead",
     "forced_to": ("hedge the provisional pricing exposure on COMEX or the LME",
                   "re-hedge when the quotational period rolls"),
     "when": "shipment-linked; the quotational period is typically M+3",
     "information": ("shipment schedules", "TC/RC", "the LME cash-3m spread"),
     "constraints": ("provisional pricing creates a mechanical mark-to-market exposure",
                     "the hedge must roll with the quotational period"),
     "instruments": ("XCUUSD",),
     "counterparties": ("miners", "smelters", "exchanges"),
     "observables": ("export volumes", "LME spreads", "COMEX open interest"),
     "impact": "a mechanical, dated hedging flow three months after every shipment -- a "
               "predictable component of copper open interest that has nothing to do with a view",
     "persistence": "continuous and structural",
     "falsifier": "no measurable lag structure between Andean export volumes and COMEX open "
                  "interest at the quotational-period horizon",
     "notes": "the one copper mechanism here that is measurable with COT plus export data alone"},
    {"name": "global macro investor using CLP as the copper expression",
     "holds": "short USD/CLP as a levered long-copper position",
     "forced_to": ("cut on a China growth scare", "cut on a Chilean political shock"),
     "when": "clustered exits on risk events",
     "information": ("copper", "Chinese data", "Chilean politics"),
     "constraints": ("CLP is the highest-beta liquid copper currency and therefore the crowded "
                     "expression",
                     "liquidity thins fast in stress"),
     "instruments": ("XCUUSD", "AUDUSD", "USDBRL", "US500"),
     "counterparties": ("local banks", "offshore funds"),
     "observables": ("BCCh derivatives-repository outstanding", "copper COT", "AUD beta"),
     "impact": "the reason a CHILEAN political event moves COPPER: the position, not the metal's "
               "fundamentals, is what unwinds",
     "persistence": "position builds over months, unwinds in days",
     "falsifier": "copper shows no abnormal move around Chilean political events that do not "
                  "affect mine output -- which would mean the position channel does not exist",
     "notes": "this is the pack's most important edge and its most falsifiable one"},
    {"name": "Chinese state stockpiler (SRB) and the strategic reserve",
     "holds": "a strategic copper reserve bought and released opaquely",
     "forced_to": ("buy into weakness when the state judges the price strategically low",
                   "release into strength to suppress input costs"),
     "when": "unannounced; inferred from import and inventory anomalies",
     "information": ("Chinese customs imports", "bonded warehouse stock", "SHFE inventory"),
     "constraints": ("purchases are not disclosed",
                     "the policy objective is industrial cost, not profit"),
     "instruments": ("XCUUSD", "USDCNH", "CHINAH", "AUDUSD"),
     "counterparties": ("traders", "Andean producers"),
     "observables": ("import volumes above apparent consumption", "bonded stock"),
     "impact": "a price-elastic buyer of last resort that truncates copper's left tail, which "
               "makes the metal's return distribution asymmetric in a way its volatility does not "
               "reveal",
     "persistence": "episodic, months",
     "falsifier": "copper's downside tail is no shorter than that of a metal with no state "
                  "stockpiler (nickel, zinc) after controlling for liquidity",
     "notes": "the within-metals control set (XZNUSD, XNIUSD, XALUSD) exists for exactly this"},
    {"name": "Chilean and Peruvian exporter hedging the local currency",
     "holds": "dollar receipts against peso and sol cost bases",
     "forced_to": ("sell dollars forward to cover domestic costs",
                   "roll hedges as shipments slip"),
     "when": "monthly, with a quarter-end concentration",
     "information": ("the forward curve", "the dolar observado", "shipment schedules"),
     "constraints": ("cost bases are local-currency and non-negotiable",
                     "hedge accounting fixes the tenor"),
     "instruments": ("XCUUSD", "AUDUSD"),
     "counterparties": ("local banks", "the BCCh and BCRP as residual counterparties"),
     "observables": ("BCCh derivatives-repository outstanding", "BCRP forward statistics"),
     "impact": "the structural forward-market supply of dollars that the central banks' books sit "
               "opposite; when it dries up, intervention is what replaces it",
     "persistence": "continuous, with a quarter-end shape",
     "falsifier": "no relationship between measured exporter forward outstanding and the central "
                  "banks' own derivative books",
     "notes": "the only Andean positioning series that exists is this one, in the Chilean "
              "repository statistics"},
    {"name": "Andean sovereign wealth and the copper-revenue cycle",
     "holds": "FEES and FRP (Chile) and the Peruvian fiscal stabilisation fund",
     "forced_to": ("accumulate when copper is above the reference price",
                   "draw down in a downturn on a legislated trigger"),
     "when": "annual budget cycle with quarterly reporting",
     "information": ("the copper reference price", "fiscal balances", "fund reports"),
     "constraints": ("the accumulation rule is legislated and the drawdown trigger is explicit",),
     "instruments": ("XCUUSD", "UST10Y", "US500"),
     "counterparties": ("global asset managers", "the Treasury"),
     "observables": ("fund balances", "quarterly fiscal reports"),
     "impact": "a rule-based, price-triggered cross-border flow: high copper means Chilean saving "
               "abroad, which is a peso-negative flow at exactly the moment the terms of trade "
               "are peso-positive -- the two partially cancel and the NET is the research object",
     "persistence": "slow, annual",
     "falsifier": "no offsetting relationship between the copper price and measured sovereign-fund "
                  "accumulation in the currency leg",
     "notes": "this cancellation is why the CLP-copper beta is lower than a naive terms-of-trade "
              "model predicts, and testing that is the domain CL-J"},
)

# --------------------------------------------------------------------------- domains
_CONTROLS = ("a matched non-event day of the same weekday and month",
             "the global dollar factor (USDX) and US500 on the same session",
             "the within-metals control set XZNUSD / XNIUSD / XALUSD")

DOMAINS: tuple[dict[str, Any], ...] = (
    {"id": "CL-A", "title": "BCCh policy surprise against the EOF consensus",
     "objects": ("the TPM decision versus the Encuesta de Operadores Financieros",
                 "the 18:00 Santiago announcement", "the IPoM and the Senate presentation"),
     "conditions": ("the announcement is after the local close",
                    "the UTC minute moves TWICE a year and in antiphase with the broker clock"),
     "instruments": ("XCUUSD", "AUDUSD", "UST10Y", "US500"),
     "controls": (*_CONTROLS, "BCRP decisions in the same month as the cross-country control"),
     "notes": "the antiphase DST is the trap; a fixed-UTC event window mis-bins half the sample"},
    {"id": "CL-B", "title": "The dolar observado one-session offset",
     "objects": ("the published reference against the same day's market rate",
                 "the legal-reference basis"),
     "conditions": ("the published value describes the PREVIOUS session",
                    "no CLP instrument exists here, so the effect must be read in the carriers"),
     "instruments": ("XCUUSD", "AUDUSD"),
     "controls": (*_CONTROLS, "Peru's same-day interbank convention as the contrast"),
     "notes": "the structural analogue of Korea's MAR; two countries with the same defect is "
              "evidence about the convention rather than about either country"},
    {"id": "CL-C", "title": "Strike windows and the collective-bargaining calendar",
     "objects": ("known contract expiry dates at the large Chilean mines",
                 "strike votes and stoppages", "production guidance revisions"),
     "conditions": ("the RISK window is announced years ahead and the OUTCOME is not",
                    "one mine can be one to two percent of world supply"),
     "instruments": ("XCUUSD", "XZNUSD", "AUDUSD"),
     "controls": (*_CONTROLS, "Peruvian conflict episodes as the unscheduled-disruption class"),
     "notes": "the scheduled-versus-unscheduled pair is the identification"},
    {"id": "CL-D", "title": "The AFP multifondo switch as a forced cross-border flow",
     "objects": ("monthly transfers between funds A-E", "the foreign-investment share",
                 "the legislated withdrawal windows of 2020-2021"),
     "conditions": ("the trigger is a newsletter, not a macro variable, so the flow is "
                    "orthogonal to the usual factors by construction",
                    "the withdrawal episodes are a regime of their own and must not be pooled"),
     "instruments": ("US500", "XCUUSD", "AUDUSD", "UST10Y"),
     "controls": (*_CONTROLS, "Peruvian AFP withdrawal windows as the institutional comparison"),
     "notes": "the orthogonality is the whole value: a flow uncorrelated with the factors is a "
              "flow whose price impact can actually be identified"},
    {"id": "CL-E", "title": "Pre-announced intervention as a commitment device",
     "objects": ("the 2019 and 2022 programmes", "daily published amounts",
                 "the announced end dates"),
     "conditions": ("the programme is known in full at announcement, so the ANNOUNCEMENT is the "
                    "event and the execution is not",),
     "instruments": ("XCUUSD", "AUDUSD", "USDBRL"),
     "controls": (*_CONTROLS, "Brazilian auction-by-auction intervention and Argentine opacity"),
     "notes": "three intervention regimes in one command is a natural experiment about "
              "commitment, and it is the reason these packs are worth writing together"},
    {"id": "CL-F", "title": "Copper supply state versus Chinese demand state",
     "objects": ("Cochilco and MINEM monthly output", "TC/RC benchmark and spot",
                 "Chinese imports and bonded stock"),
     "conditions": ("supply and demand shocks have OPPOSITE price-quantity signatures and "
                    "pooling them measures neither",),
     "instruments": ("XCUUSD", "USDCNH", "CHINAH", "AUDUSD", "HK50"),
     "controls": (*_CONTROLS, "aluminium and zinc, which share the demand state and not the "
                              "Andean supply state"),
     "notes": "the core domain of this pack and the anchor of the cross-region copper triple"},
    {"id": "CL-G", "title": "Copper as a gold and risk signal",
     "objects": ("the copper-gold ratio", "copper's behaviour in risk-off",
                 "the metal's asymmetric left tail"),
     "conditions": ("the copper-gold ratio is a growth-versus-fear spread and is used as one by "
                    "practitioners, which makes it crowded and therefore reflexive",),
     "instruments": ("XCUUSD", "XAUUSD", "XAGUSD", "US500", "UST10Y"),
     "controls": (*_CONTROLS, "the same ratio built with aluminium, which has no monetary leg"),
     "notes": "the principal's 'local state as a SENSOR for XAUUSD' instruction, on the metal leg"},
    {"id": "CL-H", "title": "Peruvian conflict, canon minero and unscheduled supply loss",
     "objects": ("Defensoria monthly conflict counts", "corredor minero blockades",
                 "MINEM regional output"),
     "conditions": ("episodes cluster with the political and transfer calendar, which makes the "
                    "TIMING partially predictable even though each episode is not",),
     "instruments": ("XCUUSD", "XAUUSD", "XZNUSD"),
     "controls": (*_CONTROLS, "Chilean scheduled strikes as the announced-risk comparison"),
     "notes": "the unscheduled half of the CL-C pair"},
    {"id": "PE-A", "title": "BCRP monthly decisions and the best-anchored expectations in LatAm",
     "objects": ("twelve decisions a year against a 2% target",
                 "the Reporte de Inflacion", "expectation surveys"),
     "conditions": ("twelve events a year against Chile's eight unbalances any pooled Andean "
                    "study and must be weighted by country",
                    "Peru has no DST, so the UTC minute is fixed while Chile's is not"),
     "instruments": ("XCUUSD", "USDBRL", "UST10Y"),
     "controls": (*_CONTROLS, "Chilean RPM dates as the paired-country control"),
     "notes": "the lowest inflation target in the region is the reason the surprise distribution "
              "here is tighter, which is a property of the target and not of the economy"},
    {"id": "PE-B", "title": "Managed sol volatility as a policy output",
     "objects": ("CDR and swap outstanding", "realised USD/PEN volatility",
                 "political shock episodes"),
     "conditions": ("the currency is not free, so a political-risk test on it measures the "
                    "central bank's tolerance rather than the market's assessment",),
     "instruments": ("XCUUSD", "USDBRL", "XAUUSD"),
     "controls": (*_CONTROLS, "Chile's free float during the same political episodes"),
     "notes": "the control case that makes the Chilean and Brazilian political-risk claims "
              "identifiable at all"},
    {"id": "PE-C", "title": "Peruvian terms of trade and the precious-metals leg",
     "objects": ("the BCRP export and import price indices separately",
                 "gold and silver export volumes"),
     "conditions": ("Peru is a top-three silver producer and a large gold producer, so its terms "
                    "of trade carry a PRECIOUS leg Chile's does not",),
     "instruments": ("XAUUSD", "XAGUSD", "XCUUSD"),
     "controls": (*_CONTROLS, "Chile's copper-only terms of trade as the contrast"),
     "notes": "the precious leg is what stops this pack being a single-factor copper bet"},
    {"id": "CL-I", "title": "Andean stress as an EM-stress component",
     "objects": ("joint moves with BRL, MXN and ZAR",
                 "copper's behaviour when the EM complex sells off"),
     "conditions": ("neither currency is quotable, so the test must run on the metal and the "
                    "peer currencies rather than on the Andean pair itself",),
     "instruments": ("XCUUSD", "USDBRL", "USDMXN", "USDZAR", "XAUUSD"),
     "controls": (*_CONTROLS, "AUDUSD as the developed-market copper beta"),
     "notes": "AUD is the control that separates 'copper fell' from 'EM sold off'"},
    {"id": "CL-J", "title": "The fiscal rule's reference-price threshold and the cancelling flows",
     "objects": ("the annually published copper reference price",
                 "sovereign-fund accumulation", "the structural balance"),
     "conditions": ("terms-of-trade inflow and sovereign-fund outflow have OPPOSITE currency "
                    "signs and partially cancel; the net is the object and neither leg alone is",),
     "instruments": ("XCUUSD", "UST10Y", "US500"),
     "controls": (*_CONTROLS, "Peru, which has a weaker and less explicit rule"),
     "notes": "explains why the measured CLP-copper beta is lower than a naive model predicts"},
    {"id": "CL-K", "title": "Andean practitioner claims, converted and falsified",
     "objects": ("strike and blockade reports in the Spanish press before the English wire",
                 "AFP advisory calls", "Rankia and Diario Financiero mechanism claims"),
     "conditions": ("a claim is a hypothesis with a falsifier and never evidence",
                    "the Spanish-language lead time is the only reason this is worth a charge"),
     "instruments": ("XCUUSD", "AUDUSD"),
     "controls": (*_CONTROLS, "the same claims dated to their ENGLISH publication instead"),
     "notes": "the control here is exact: if the effect survives only at the Spanish date, the "
              "lead time is real; if it survives at both, the claim was already public"},
)

# --------------------------------------------------------------------------- miners
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    {"name": "cl_bcch_lane", "domain_ids": ("CL-A", "CL-B", "CL-D", "CL-E"), "kind": "mechanism",
     "entry": "research.countries.cl.data_plane:fetch", "cadence_s": 21600.0, "steerable": True,
     "notes": "the BCCh and BCRP lane with its vintage store"},
    {"name": "cl_copper_state", "domain_ids": ("CL-F", "CL-G", "CL-H"), "kind": "mechanism",
     "entry": "research.countries.cl.data_plane:copper_state", "cadence_s": 21600.0,
     "steerable": True,
     "notes": "the Andean supply state against the Chinese demand state"},
    {"name": "cl_holiday_liquidity", "domain_ids": ("CL-B", "PE-B"), "kind": "calendar",
     "entry": "research.countries.cl.pack:is_closed", "cadence_s": 86400.0, "steerable": False,
     "notes": "the two national calendars overlap on four dates a year, which makes each a "
              "liquidity control for the other"},
)

# --------------------------------------------------------------------------- the two vocabularies
# THE FRAMEWORK AND THIS PACKAGE NAME THE SAME ROW DIFFERENTLY, AND BOTH CONSUMERS ARE REAL.
# `countries.check_pack` validates an edge written as {id, source, mechanism, targets, sign,
# horizon, lag, control, evidence}; `libs.research.country_lab.TransmissionSeed` coerces a row
# into {to_country, asset, actor, constraint, flow, source_series, source_symbol, lag_days, era}
# and DROPS every key it does not know. A row written in one vocabulary therefore arrives at the
# other consumer EMPTY -- not wrong, blank, which is worse because it reads as a declared absence.
# So every seed here carries BOTH sets of keys: the desk's own vocabulary is authored and the
# framework's is DERIVED from it, once, here, rather than transcribed by hand fifty times.


def _lag_days(text: str) -> float:
    """The first whole number in a lag phrase (`"1-10 sessions"` -> 1.0). An unparseable lag is
    0.0 and NOT one day: inventing a lag is how a transmission gets measured at the wrong
    horizon and reported as a null."""
    digits = ""
    for ch in str(text or ""):
        if ch.isdigit():
            digits += ch
        elif digits:
            break
    return float(digits) if digits else 0.0


def _dual(rows: tuple[dict[str, Any], ...]) -> tuple[dict[str, Any], ...]:
    """Every transmission seed in both vocabularies, with the DERIVED keys written FIRST.

    Order is load-bearing and it is the whole reason this function is not two lines. The
    framework walks a row in insertion order and keeps the FIRST key that maps to a field, so an
    alias it already owns (`mechanism`->flow, `source`->source_series, `lag`->lag_days) wins over
    anything added afterwards. `lag` reaching `lag_days` that way puts the STRING "1-10 sessions"
    into a float field. Writing `lag_days` first makes the parsed number win and sends the prose
    to `notes`, where it is still readable. `targets` is plural and the framework's row holds one
    asset, so the primary carrier -- the first declared target -- is named explicitly.
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
    """Policy eras with the readable LABEL as the framework's `name`, written first.

    Without this the framework's `id`->`name` alias fires first and every era is filed under its
    token instead of its sentence, which is what a human reading a coerced pack actually sees.
    """
    return tuple({"name": str(r.get("label") or r.get("id") or ""), **r} for r in rows)


# --------------------------------------------------------------------------- transmission
_EDGE_ROWS: tuple[dict[str, Any], ...] = (
    {"id": "cl_pe_copper_supply_to_metal",
     "source": "Cochilco and MINEM monthly output, strike and blockade episodes",
     "mechanism": "Chile and Peru are the marginal copper supplier; a supply loss at one large "
                  "mine is one to two percent of world output and prices immediately",
     "targets": ("XCUUSD", "XZNUSD"), "sign": "opposite",
     "horizon": "1-30 sessions", "lag": "0-3 sessions",
     "control": "aluminium and nickel, which share the demand state and not the Andean supply",
     "evidence": "HYPOTHESIS",
     "notes": "the supply half; the sign is opposite because less supply means a higher price"},
    {"id": "cl_pe_copper_to_aud",
     "source": "the Andean copper supply state",
     "mechanism": "AUD is the most liquid copper-beta currency open during the Asian session, so "
                  "an Andean supply state reaches FX through the Australian leg first",
     "targets": ("AUDUSD", "AUDJPY", "NZDUSD"), "sign": "same",
     "horizon": "1-20 sessions", "lag": "0-5 sessions",
     "control": "AUD moves driven by the RBA with no metals component",
     "evidence": "HYPOTHESIS",
     "notes": "the Andes-to-Oceania leg named in the principal's order"},
    {"id": "cl_copper_china_to_risk",
     "source": "copper acceleration conditioned on the Chinese demand state",
     "mechanism": "copper acceleration is the cleanest industrial-demand signal; conditioned on "
                  "Chinese activity it is a global risk signal rather than a metals one",
     "targets": ("US500", "NAS100", "HK50", "CHINAH"), "sign": "same",
     "horizon": "5-40 sessions", "lag": "1-10 sessions",
     "control": "gold, which shares the dollar factor and not the industrial one",
     "evidence": "HYPOTHESIS",
     "notes": "the conditional form is the hypothesis: the edge should EXIST only in one China "
              "state, and an unconditional test that finds nothing has not refuted it"},
    {"id": "cl_copper_gold_ratio_to_gold",
     "source": "the copper-gold ratio as a growth-versus-fear spread",
     "mechanism": "a crowded practitioner ratio is reflexive; its extremes should mean-revert "
                  "and its breaks should carry information about which leg is moving",
     "targets": ("XAUUSD", "XAGUSD", "UST10Y"), "sign": "opposite",
     "horizon": "5-60 sessions", "lag": "0-5 sessions",
     "control": "the aluminium-gold ratio, which no practitioner watches",
     "evidence": "HYPOTHESIS",
     "notes": "the control is the point: if only the WATCHED ratio works, the mechanism is "
              "crowding and not growth"},
    {"id": "cl_afp_switch_to_global_assets",
     "source": "AFP multifondo transfers and the foreign-investment share",
     "mechanism": "a mass switch forces the AFPs to rebalance an offshore book within days; the "
                  "flow is triggered by a newsletter and is therefore orthogonal to the factors",
     "targets": ("US500", "XCUUSD", "UST10Y"), "sign": "same",
     "horizon": "1-15 sessions", "lag": "0-5 sessions",
     "control": "months with comparable copper and risk moves and no measured switch",
     "evidence": "HYPOTHESIS",
     "notes": "the orthogonality is what makes the price impact identifiable"},
    {"id": "cl_political_shock_to_copper",
     "source": "Chilean political events that do not affect mine output",
     "mechanism": "CLP is the crowded copper expression; a Chilean political shock unwinds the "
                  "POSITION, and the position is in copper as well as in the peso",
     "targets": ("XCUUSD", "AUDUSD"), "sign": "opposite",
     "horizon": "1-10 sessions", "lag": "0-2 sessions",
     "control": "Chilean events that DO affect output, which should move copper through supply "
                "instead and with a different persistence",
     "evidence": "HYPOTHESIS",
     "notes": "the most falsifiable edge in this pack and the most valuable if it survives"},
    {"id": "pe_stress_to_em_risk",
     "source": "Peruvian political crises and the BCRP's intervention response",
     "mechanism": "Peru's currency is managed, so political stress shows up in the INTERVENTION "
                  "book and in the metal rather than in the exchange rate",
     "targets": ("XCUUSD", "USDBRL", "USDMXN", "XAUUSD"), "sign": "same",
     "horizon": "1-20 sessions", "lag": "0-3 sessions",
     "control": "Chilean political events under a free float",
     "evidence": "HYPOTHESIS",
     "notes": "the managed-versus-free pair identifies what a currency would have done"},
    {"id": "pe_precious_exports_to_metals",
     "source": "Peruvian gold and silver export volumes",
     "mechanism": "Peru is a top-three silver producer; a Peruvian precious supply state is a "
                  "global silver supply state and silver's float is thin",
     "targets": ("XAGUSD", "XAUUSD", "XPTUSD"), "sign": "opposite",
     "horizon": "10-60 sessions", "lag": "5-20 sessions",
     "control": "gold, whose supply is far more diversified than silver's",
     "evidence": "HYPOTHESIS",
     "notes": "the precious leg that keeps this pack from being a single-factor copper bet"},
    {"id": "cl_fiscal_threshold_to_copper",
     "source": "the published copper reference price and sovereign-fund accumulation",
     "mechanism": "an explicit published threshold changes the sovereign's flow direction; "
                  "crossing it is a policy discontinuity with a public number",
     "targets": ("XCUUSD", "UST10Y"), "sign": "same",
     "horizon": "20-120 sessions", "lag": "5-20 sessions",
     "control": "Peru, whose rule is weaker and less explicit",
     "evidence": "HYPOTHESIS",
     "notes": "discontinuity design rather than a level regression"},
    {"id": "cl_tcrc_benchmark_to_copper",
     "source": "the annual Chinese treatment-charge benchmark round",
     "mechanism": "the benchmark is a dated annual read on concentrate tightness that is "
                  "independent of the refined price",
     "targets": ("XCUUSD", "USDCNH"), "sign": "opposite",
     "horizon": "20-90 sessions", "lag": "0-20 sessions",
     "control": "refined-price moves in the same window with no benchmark news",
     "evidence": "HYPOTHESIS",
     "notes": "one event a year, so the trial charge must be spent carefully and the era "
              "structure matters more than the sample size"},
    {"id": "cl_pe_supply_to_china_proxies",
     "source": "joint Andean supply disruption",
     "mechanism": "a supply squeeze raises Chinese industrial input costs, which is a margin "
                  "event for the Chinese industrial complex and prices in the equity proxies",
     "targets": ("CHINAH", "HK50", "USDCNH"), "sign": "opposite",
     "horizon": "5-40 sessions", "lag": "1-10 sessions",
     "control": "demand-driven copper rallies, which should move the same proxies the OTHER way",
     "evidence": "HYPOTHESIS",
     "notes": "the sign flip between supply-driven and demand-driven copper is the test"},
)

#: Authored in the desk's vocabulary; `_dual` adds the framework's.
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = _dual(_EDGE_ROWS)


# --------------------------------------------------------------------------- eras
_ERA_ROWS: tuple[dict[str, Any], ...] = (
    {"id": "cl_estallido_social", "start": "2019-10-18", "end": "2020-03-01",
     "label": "The estallido social and the first pre-announced FX programme",
     "what_changed": "the peso depreciated to a record and the BCCh announced a USD 20bn spot "
                     "and NDF programme on 2019-11-28 -- the first pre-committed intervention",
     "invalidates": "any Chilean political-risk or FX-volatility estimate that pools this window "
                    "with the pre-2019 float is averaging two intervention regimes"},
    {"id": "cl_pension_withdrawals", "start": "2020-07-30", "end": "2021-05-31",
     "label": "Three legislated pension withdrawals",
     "what_changed": "roughly a fifth of pension assets were liquidated on legislated timetables, "
                     "forcing the largest involuntary cross-border flow in Chilean history and "
                     "inverting the local rates curve",
     "invalidates": "AFP-flow, local-rate and FX estimates from this window describe a forced "
                    "liquidation and transfer to nothing outside it"},
    {"id": "cl_constitutional_process", "start": "2021-05-15", "end": "2023-12-17",
     "label": "Two constitutional conventions and two rejected texts",
     "what_changed": "a two-and-a-half-year period in which Chilean political risk was a "
                     "scheduled, dated, plebiscite-driven variable rather than a diffuse one",
     "invalidates": "political-risk estimates fitted here have DATED events; the periods either "
                    "side do not, so the event class itself is different"},
    {"id": "cl_intervention_2022", "start": "2022-07-18", "end": "2022-12-31",
     "label": "The USD 25bn pre-announced intervention programme",
     "what_changed": "the second and larger commitment device, announced with daily amounts and "
                     "an end date",
     "invalidates": "an intervention-response study that pools the announced programmes with "
                    "discretionary episodes is pooling a commitment with a surprise"},
    {"id": "pe_political_instability", "start": "2020-11-09", "end": "2023-03-31",
     "label": "Six presidents, a failed self-coup and sustained protest",
     "what_changed": "extreme political instability with essentially NO currency response, "
                     "because the BCRP absorbed it through the derivative book",
     "invalidates": "any claim that political risk moves a currency, tested on Peru, is testing "
                    "the central bank's tolerance instead -- and that is the finding"},
    {"id": "andean_copper_supercycle_2021", "start": "2020-04-01", "end": "2022-03-31",
     "label": "The post-pandemic copper run to record highs",
     "what_changed": "copper doubled on a demand impulse with constrained supply, and the Chilean "
                     "fiscal rule's reference price was repeatedly exceeded",
     "invalidates": "supply-elasticity estimates from this window are contaminated by a demand "
                    "shock of the same magnitude"},
    {"id": "cl_royalty_reform", "start": "2023-08-01", "end": None,
     "label": "The Chilean mining royalty reform",
     "what_changed": "the marginal tax on copper margins changed, which changes the supply curve's "
                     "response to price at the top end",
     "invalidates": "pre-2023 supply-response estimates carry a different after-tax incentive and "
                    "do not transfer forward"},
)

POLICY_ERAS: tuple[dict[str, Any], ...] = _named_eras(_ERA_ROWS)


# --------------------------------------------------------------------------- access constraints
ACCESS_CONSTRAINTS: tuple[dict[str, Any], ...] = (
    {"constraint": "neither CLP nor PEN is quoted on this broker",
     "measured": "universe.json holds USDBRL and USDMXN and no other LatAm currency",
     "consequence": "this pack is TRANSMISSION-ONLY. Every mechanism names a carrier and the "
                    "basis that substitution costs; no cell here claims to trade an Andean "
                    "currency"},
    {"constraint": "the BCCh statistical API requires a registered user and password",
     "measured": "SieteRestWS takes user and pass as query parameters",
     "consequence": "without credentials in data/secrets/latam_apis.json every Chilean series is "
                    "UNMEASURED BY NAME; the Peruvian half of the lane still runs, which is why "
                    "the two are in one lane rather than two"},
    {"constraint": "LME warehouse stock and the cash-3m spread are not collected",
     "measured": "XCUUSD is a CFD on the COMEX price and carries no inventory information",
     "consequence": "every physical-tightness claim in this pack is BLOCKED_ON_DATA and counted "
                    "as blocked rather than reported as a null"},
)

# --------------------------------------------------------------------------- assembly
_PACK_FIELDS: tuple[str, ...] = (
    "code", "name", "region_command", "currency", "executable_instruments", "central_bank",
    "fixing_conventions", "settlement_conventions", "exchanges", "holidays_rule",
    "fiscal_year_end", "positioning_sources", "native_languages", "terminology", "source_classes",
    "datasets", "actors", "domains", "custom_miners", "transmission_edges_seed", "policy_eras")

MISSION = ("mine the Andean copper complex to exhaustion as ONE object with two flags: the "
           "world's marginal copper supply against the Chinese demand state, a forced pension "
           "flow triggered by newsletters, three different intervention regimes in one command, "
           "and a managed currency next door that serves as the control for every political-risk "
           "claim -- all of it expressed in XCUUSD, AUDUSD, gold and the China proxies, because "
           "neither local currency is quoted here and this pack never pretends otherwise")


def as_dict() -> dict[str, Any]:
    """The pack as a plain mapping, with the Peruvian central bank and the extras carried
    alongside the twenty-one frozen fields rather than dropped."""
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
        "central_bank_pe": CENTRAL_BANK_PE, "secondary_currency": SECONDARY_CURRENCY,
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
