"""BRAZIL: the carry trade with a published fixing, and a commodity current account under it.

WHY BRAZIL IS THE ANCHOR OF THIS COMMAND AND NOT JUST ITS LARGEST MEMBER. Four mechanisms exist
here and nowhere else on the continent in combination:

  1. A REAL POLICY RATE THAT HAS BEEN THE HIGHEST IN THE LIQUID WORLD FOR MOST OF THE SAMPLE. The
     Selic went 2.00% (Aug 2020) -> 13.75% (Aug 2022) -> 10.50% (May 2024) -> 15.00% (Jun 2025).
     A carry cell on USDBRL is not a yield-differential curiosity, it is the largest funded
     position in EM FX, and its unwind is a GLOBAL risk event rather than a Brazilian one. The
     broker's own swap on USDBRL is the same fact from the other side, and it is why a long-USD
     cell here pays and a short-USD cell collects.

  2. A FIXING THAT IS A WINDOW AVERAGE OF FOUR ANNOUNCED CONSULTATIONS, NOT A SNAPSHOT. PTAX is
     the arithmetic mean of four intraday dealer consultations run between 10:00 and 13:10
     Brasilia, published at about 13:15 Brasilia. Every USD-settled Brazilian contract references
     it, so the hour before each window is a scheduled, dated, repeatable flow event. A study
     that treats PTAX as a close is measuring the wrong minute by three hours.

  3. A DOLLAR FUTURE THAT IS MORE LIQUID THAN ITS OWN SPOT. B3's DOL/WDO expires on the FIRST
     business day of the contract month and cash-settles to the PTAX of the PRECEDING business
     day. The spot market is an interbank appendix to that future, the "casado" (future minus
     spot) is the funding basis, and the roll is a dated flow that is not a third Friday and must
     never be modelled as one.

  4. AN EXPORT BOOK THAT IS FOUR PRICES THE DESK ALREADY QUOTES. Iron ore, crude, soybeans, sugar
     and coffee are most of the Brazilian trade balance, and three of the five are in this
     broker's registry (SOYBEAN, SUGAR/SUGARRAW, COFARA/COFROB) with the oil leg in XTIUSD and
     XBRUSD. Brazil is therefore the one country in this package where the terms-of-trade channel
     can be measured on BOTH legs with instruments that exist.

WHAT IS EXECUTABLE. USDBRL is in the broker registry as a Forex Exotic. The Ibovespa is NOT, and
neither is the DI curve, the DOL future, the B3 FX option or the NTN-B; each is named in
`TRANSMISSION_TARGETS` with the symbols its mechanism actually reaches, because an instrument that
is silently dropped becomes a mechanism that is silently dropped.

THE TWO-LANE ORDER IS LOAD-BEARING HERE. Brazilian retail research vocabulary -- InfoMoney, Bastter,
Clube do Valor, the Rankia boards -- is overwhelmingly single-name equity and dividend talk. None
of it may mint a statistical hypothesis (order of 2026-09-06). Petrobras and Vale appear in this
pack ONLY as ACTORS whose forced flows move FX and commodities; neither is ever a symbol on a
docket, and the CVM lane in `data_plane.py` aggregates to sector and cycle sensors before any
number leaves it.

POINT-IN-TIME, THE BRAZILIAN VERSION. Three lags dominate and every dataset row carries its own.
PTAX is same-day at 13:15 Brasilia. IPCA lands around the 10th of the following month with a
15-day IPCA-15 preview mid-month, and the preview is the PIT object a cell may trade. The Focus
survey is published Mondays at 08:25 Brasilia covering the previous Friday's responses and is the
ONE natively point-in-time Brazilian series, because every row carries the survey date alongside
the reference year -- which is exactly the pair a surprise needs.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------- identity
CODE = "br"
NAME = "Brazil"
#: The canonical token from `country_lab.REGION_COMMANDS`. `REGION_DESK` is the desk-facing label
#: this command is run under; the two differ on purpose and the canonical one is what miners group
#: by.
REGION_COMMAND = "latam"
REGION_DESK = "SOUTH_AMERICA"
CURRENCY = "BRL"
NATIVE_LANGUAGES: tuple[str, ...] = ("pt-BR",)
#: Calendar year for both the federal budget and essentially every listed company.
FISCAL_YEAR_END = "12-31"

#: Brazil's OWN price on this broker, and the reason every other Brazilian mechanism here can be
#: tested against something rather than only described.
OWN_PRICE: tuple[str, ...] = ("USDBRL",)

#: What the BR department may place an order in. Every symbol is in
#: `desks/mt5/data/universe/universe.json` and none is a single-name equity.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "USDBRL",                                  # the sovereign quote, Forex Exotics
    "USDMXN", "USDZAR", "USDTRY",              # the EM-stress peer set
    "USDCNH",                                  # the China demand leg every BR commodity needs
    "EURUSD", "AUDUSD", "USDJPY", "AUDJPY",    # the carry and risk legs
    "XAUUSD", "XAGUSD",                        # the reserve-asset and EM-stress legs
    "XTIUSD", "XBRUSD",                        # Petrobras export parity and the fuel-price rule
    "XCUUSD",                                  # the industrial-demand control for iron ore
    "SOYBEAN", "CORN", "SUGAR", "SUGARRAW",    # the safra complex
    "COFARA", "COFROB", "COTTON", "USCOCOA",   # arabica is Brazilian; robusta is the control
    "US500", "NAS100", "US2000", "USDX",       # the global risk and dollar factors
    "UST10Y", "UST05Y",                        # the duration leg a carry cell must control for
)

#: The COT market the desk's own axis carries for this country. USDMXN is mapped in
#: `data/axes/cot.json`; the CFTC publishes a Brazilian real contract and the desk's axis does NOT
#: carry it, so BRL positioning is UNMEASURED BY NAME rather than assumed absent.
COT_CURRENCY = "BRL"
COT_STATUS = ("CFTC publishes 6L Brazilian Real futures at the CME. The desk's cot.json axis maps "
              "USDMXN and not USDBRL, so Brazilian positioning is UNMEASURED on this box until "
              "the axis adds the market -- it is not a zero and it is not an absence of data.")

#: Instruments these mechanisms are ABOUT that this broker does not quote, each naming the
#: universe symbols its economics actually reaches. Absence is recorded, never silently dropped.
TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "B3 DOL / WDO US dollar futures", "venue": "B3",
     "why": "the price-forming venue for USD/BRL; spot is an interbank appendix to it, and the "
            "future-minus-spot 'casado' is the local dollar funding rate",
     "proxies": ("USDBRL",)},
    {"name": "Ibovespa (IBOV) and its WIN/IND futures", "venue": "B3",
     "why": "the domestic risk asset; its foreign-investor flow print is one of this pack's best "
            "observables and the index itself is not quotable here",
     "proxies": ("US500", "US2000", "USDBRL", "XCUUSD")},
    {"name": "DI1 one-day interbank deposit futures (the DI curve)", "venue": "B3",
     "why": "the entire Brazilian rates expression; the Copom surprise is priced here first and "
            "reaches FX second",
     "proxies": ("USDBRL", "UST10Y", "UST05Y")},
    {"name": "NTN-B inflation-linked and LTN/NTN-F nominal Treasury bonds", "venue": "Tesouro",
     "why": "the Treasury's own auction calendar is a dated supply event and the local real-rate "
            "term premium is the carry cell's true discount rate",
     "proxies": ("USDBRL", "UST10Y")},
    {"name": "SGX / DCE 62% Fe iron ore swaps and futures", "venue": "SGX / DCE",
     "why": "the single largest Brazilian export price after crude; it sets Vale's receipts and "
            "the mining half of the trade balance",
     "proxies": ("USDBRL", "XCUUSD", "USDCNH", "AUDUSD")},
    {"name": "CBOT soybean crush and the Paranagua FOB premium", "venue": "CBOT / physical",
     "why": "Brazilian beans clear at a BASIS to Chicago, and the basis is where the safra and "
            "the real actually show up; the flat price is a US object",
     "proxies": ("SOYBEAN", "CORN", "USDBRL")},
    {"name": "B3 FX options and the 25-delta risk reversal on USD/BRL", "venue": "B3 / OTC",
     "why": "the only forward-looking measure of Brazilian tail pricing; realised vol on the CFD "
            "is a lagging substitute and is declared as one",
     "proxies": ("USDBRL", "XAUUSD")},
    {"name": "BCB FX swap (swap cambial) auction book", "venue": "BCB",
     "why": "the central bank intervenes in DERIVATIVES rather than spot; the outstanding swap "
            "stock is the intervention observable and it is published daily",
     "proxies": ("USDBRL",)},
    {"name": "CRB / Brazilian commodity index (IC-Br)", "venue": "BCB",
     "why": "the BCB's own terms-of-trade index in BRL -- the exact object its reaction function "
            "responds to, which no dollar commodity index reproduces",
     "proxies": ("USDBRL", "SOYBEAN", "SUGAR", "XTIUSD")},
)

# --------------------------------------------------------------------------- central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "Banco Central do Brasil",
    "short": "BCB",
    "native_name": "Banco Central do Brasil",
    "framework": "inflation_targeter",
    "committee": "COPOM -- Comite de Politica Monetaria, nine members (the Governor and eight "
                 "Directors). Formally autonomous since Lei Complementar 179/2021, with fixed "
                 "four-year terms staggered against the presidential cycle.",
    "policy_rate": "Meta Selic -- the target for the overnight rate on operations backed by "
                   "federal securities, set as a level, in whole or quarter points",
    "meetings_per_year": 8,
    "schedule_rule": (
        "EIGHT scheduled meetings a year (reduced from twelve in 2006). Each runs Tuesday and "
        "Wednesday; the decision is published in the comunicado at about 18:30 Brasilia on the "
        "WEDNESDAY, after the B3 close and after the New York close of the local session. The "
        "following year's calendar is published in advance, normally in June."),
    "announce_local": "18:30 America/Sao_Paulo",
    "announce_utc": "21:30",
    "announce_utc_dst": "21:30",
    "dst_rule": ("Brazil ABOLISHED daylight saving in 2019 (Decreto 9.772/2019). America/Sao_Paulo "
                 "has been UTC-3 all year since then, so 18:30 Brasilia is 21:30 UTC with no "
                 "seasonal shift -- but the BROKER's clock still moves (UTC+2 winter, UTC+3 "
                 "summer), so the bar index of a Copom decision moves twice a year even though "
                 "the Brazilian minute never does. A pre-2019 sample DOES carry the Brazilian "
                 "shift and must be handled with the historical rule."),
    "minutes_rule": "The ata is published the following TUESDAY at 08:00 Brasilia (11:00 UTC). "
                    "Dissent counts and the forward-guidance paragraph move the DI curve on "
                    "release and reach FX second.",
    "other_clocks": (
        {"what": "Relatorio de Politica Monetaria (quarterly inflation report, ex-RTI)",
         "when_local": "the Thursday of the last week of March, June, September and December, "
                       "08:30 Brasilia", "when_utc": "11:30"},
        {"what": "Focus -- Relatorio de Mercado (the weekly market expectations survey)",
         "when_local": "Mondays 08:25 Brasilia, covering responses to the previous Friday",
         "when_utc": "11:25"},
        {"what": "Ata do Copom", "when_local": "Tuesday after the meeting, 08:00 Brasilia",
         "when_utc": "11:00"},
    ),
    "inflation_target": (
        "3.00% with a +/-1.5pp tolerance band for 2024, 2025 and 2026. From JANUARY 2025 the "
        "target became CONTINUOUS (meta continua, CMN Resolucao 5.090/2023) rather than a "
        "calendar-year target: the breach test is now whether 12-month IPCA sits outside the band "
        "for six consecutive months, which changes WHEN the Governor must write the open letter "
        "and therefore changes the reaction function's timing, not just its level."),
    "fx_operations": (
        "The BCB intervenes mainly in DERIVATIVES: swap cambial tradicional (equivalent to "
        "selling dollars forward) and swap reverso (buying). Spot auctions -- leilao de linha "
        "(with repurchase) and leilao a vista -- are used in stress. Every auction is ANNOUNCED "
        "and the outstanding swap stock is published daily, so intervention here is observable in "
        "near real time, unlike Korea's quarterly disclosure or Chile's pre-announced programmes."),
    "policy_rate_series": "BCB SGS 432 (Meta Selic definida pelo Copom, % a.a.)",
    "expected_rate_series": "BCB Olinda Expectativas -- ExpectativasMercadoTop5Mensais / "
                            "ExpectativaMercadoMensais for Selic, which is a SURVEY and not a "
                            "traded consensus; the traded consensus lives in the DI curve, which "
                            "this box does not hold, and the gap between the two is itself a "
                            "measurable object once DI is collected",
    "decision_dates": {
        2024: ("2024-01-31", "2024-03-20", "2024-05-08", "2024-06-19", "2024-07-31",
               "2024-09-18", "2024-11-06", "2024-12-11"),
        2025: ("2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18", "2025-07-30",
               "2025-09-17", "2025-11-05", "2025-12-10"),
        2026: ("2026-01-28", "2026-03-18", "2026-05-06", "2026-06-17", "2026-07-29",
               "2026-09-16", "2026-11-04", "2026-12-09"),
    },
    "decision_dates_status": (
        "2024 and 2025 are the published calendars. 2026 is DERIVED from the BCB's own rule "
        "(eight Tuesday/Wednesday meetings, roughly six to seven weeks apart, announced on the "
        "Wednesday) and must be replaced by the published calendar before any event study is "
        "read as confirmatory. A derived date used as a published one is a silent lookahead in "
        "the opposite direction: it puts the event in the wrong bar and reports a null."),
    "root": "https://www.bcb.gov.br",
}

# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "PTAX (Taxa de cambio referencial BCB, compra e venda)",
     "publisher": "Banco Central do Brasil",
     "definition": "the arithmetic mean of the rates from FOUR intraday dealer consultations. "
                   "Each consultation samples the interbank market inside a defined window; the "
                   "extremes of each consultation are trimmed before averaging.",
     "windows_local": ("10:00-10:10", "11:00-11:10", "12:00-12:10", "13:00-13:10"),
     "windows_utc": ("13:00-13:10", "14:00-14:10", "15:00-15:10", "16:00-16:10"),
     "published_local": "about 13:15 America/Sao_Paulo",
     "published_utc": "16:15",
     "dst_rule": "Brazil has no DST since 2019, so these UTC times are fixed year-round. Samples "
                 "before 2019-11 must shift the Brazilian leg by one hour in the southern summer.",
     "instruments": ("USDBRL",),
     "why_it_matters": "essentially every USD-settled Brazilian contract -- DOL/WDO settlement, "
                       "NDFs, corporate hedges, ADR conversions -- references PTAX. The four "
                       "windows are therefore FOUR scheduled, dated, ten-minute liquidity events "
                       "a day, and the flow into the LAST one is the largest because it is the "
                       "final chance to influence the day's average.",
     "trap": "PTAX is a WINDOW AVERAGE published after the fourth window closes. A study that "
             "aligns a PTAX value with the day's close is off by roughly three hours and will "
             "attribute the afternoon's move to the fixing that preceded it."},
    {"name": "PTAX D-1 settlement reference for B3 dollar futures",
     "publisher": "B3 / BCB",
     "definition": "DOL and WDO cash-settle to the PTAX venda of the business day PRECEDING "
                   "expiry, so the settlement price is KNOWN before the contract stops trading",
     "windows_local": ("13:00-13:10",), "windows_utc": ("16:00-16:10",),
     "published_local": "13:15 on the day before expiry", "published_utc": "16:15",
     "dst_rule": "none",
     "instruments": ("USDBRL",),
     "why_it_matters": "the expiry-day flow is therefore on the day BEFORE expiry, not on expiry. "
                       "An expiry study dated to the contract's last trading day is measuring the "
                       "session after the event.",
     "trap": "this is the single most common Brazilian calendar error in public backtests"},
    {"name": "Casado (future minus spot) -- the local dollar funding basis",
     "publisher": "B3 (implicit, from the DOL and spot prints)",
     "definition": "the spread between the front DOL future and interbank spot; it prices local "
                   "USD funding (cupom cambial) against the DI curve",
     "windows_local": ("16:55-17:00",), "windows_utc": ("19:55-20:00",),
     "published_local": "continuous; the close print is the reference",
     "published_utc": "20:00", "dst_rule": "none",
     "instruments": ("USDBRL",),
     "why_it_matters": "a widening casado is Brazilian dollar scarcity and it leads spot in "
                       "stress; it is the local analogue of a cross-currency basis",
     "trap": "not quotable on this broker; it is a TRANSMISSION TARGET and any cell claiming to "
             "trade it is actually trading USDBRL with an unmeasured basis"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "FX spot", "kind": "weekday",
     "rule": "USD/BRL interbank spot settles D+2. The onshore market is CLOSED: every trade goes "
             "through a contrato de cambio registered with the BCB, which is what makes the "
             "fluxo cambial statistic exist at all.",
     "window_utc": ("13:00", "20:00"),
     "instruments": ("USDBRL",)},
    {"name": "B3 dollar future expiry", "kind": "day_of_month",
     "rule": "DOL and WDO expire on the FIRST BUSINESS DAY of the contract month and settle to "
             "the PTAX venda of the PRECEDING business day. Not a third Friday. The roll "
             "therefore concentrates in the last three business days of the previous month.",
     "days": (1,), "roll": "following",
     "window_utc": ("13:00", "16:15"),
     "instruments": ("USDBRL",)},
    {"name": "Equity and index settlement", "kind": "weekday",
     "rule": "B3 cash equities settle D+2. Foreign investors settle through custodians, so the "
             "B3 foreign-flow print LEADS its own FX conversion by one to two sessions.",
     "window_utc": ("13:00", "20:55"),
     "instruments": ("USDBRL", "US500")},
    {"name": "Dividend and interest-on-capital repatriation", "kind": "month_end",
     "rule": "Multinationals concentrate remittances at quarter ends and especially in the first "
             "quarter, after the December balance date. This is the largest recurring structural "
             "BRL-selling window of the year and it is separate from the exporter flow.",
     "months": (3, 6, 9, 12), "roll": "previous",
     "window_utc": ("13:00", "16:15"),
     "instruments": ("USDBRL",)},
    {"name": "Safra export conversion", "kind": "month_end",
     "rule": "Soybean export receipts concentrate February to May and the corn safrinha July to "
             "September; the exporter converts dollars into reais to pay domestic costs, which is "
             "structural BRL BUYING concentrated in those windows and around month end.",
     "months": (2, 3, 4, 5, 7, 8, 9), "roll": "previous",
     "window_utc": ("13:00", "16:15"),
     "instruments": ("USDBRL", "SOYBEAN", "CORN")},
)

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "B3 S.A. -- Brasil, Bolsa, Balcao",
     "index_symbols": (),
     "index_symbols_absent": ("IBOV", "IND", "WIN"),
     "hours_local": "10:00-17:00 (cash, with a closing call from 16:55); 09:00-18:25 for DOL/WDO",
     "hours_utc": "13:00-20:00 cash; 12:00-21:25 derivatives",
     "closing_auction": "16:55-17:00 local (19:55-20:00 UTC), a single-price call with a random "
                        "end of up to one minute",
     "expiry_rule": "DOL/WDO: first business day of the contract month, settled to PTAX D-1. "
                    "IND/WIN (Ibovespa futures): the nearest Wednesday to the 15th of even "
                    "months, settled to a call-auction average. DI1: first business day of the "
                    "contract month. THREE DIFFERENT RULES on one exchange -- a single 'Brazilian "
                    "expiry' constant is wrong for at least two of them.",
     "price_limits": "per-instrument tunnels (tuneis de rejeicao e de leilao); a breach triggers "
                     "an auction rather than a halt",
     "circuit_breakers": "Ibovespa trading halts for 30 minutes at -10% and one hour at -15%; "
                         "below -20% B3 decides ad hoc",
     "notes": "B3 is simultaneously the cash equity venue, the sole listed derivatives venue and "
              "the registrar for OTC FX -- which is why Brazilian flow data is unusually complete "
              "and unusually centralised."},
)

# --------------------------------------------------------------------------- holidays
_EASTER = {2024: date(2024, 3, 31), 2025: date(2025, 4, 20), 2026: date(2026, 4, 5)}


def easter(year: int) -> date:
    """Western Easter Sunday, tabulated for the years this pack declares.

    TABULATED AND NOT COMPUTED, on purpose: three of Brazil's national closures (Carnaval, Sexta-
    feira Santa, Corpus Christi) are Easter-relative, and an anonymous-Gregorian implementation
    that is off by a day silently moves three holidays. An unknown year raises rather than
    guessing -- a guessed calendar is the most expensive kind of wrong here.
    """
    if year not in _EASTER:
        raise KeyError(f"easter: {year} is not tabulated on this pack; tabulated: "
                       f"{sorted(_EASTER)}")
    return _EASTER[year]


def carnaval(year: int) -> tuple[date, date]:
    """Carnaval Monday and Tuesday: Easter minus 48 and 47 days. 2026 is 16 and 17 February."""
    e = easter(year)
    return e - timedelta(days=48), e - timedelta(days=47)


def _br_year(year: int) -> dict[str, str]:
    """One year of national closures, derived from the fixed statute plus the Easter anchor."""
    mon, tue = carnaval(year)
    e = easter(year)
    rows = {
        f"{year}-01-01": "Confraternizacao Universal",
        mon.isoformat(): "Carnaval (segunda-feira)",
        tue.isoformat(): "Carnaval (terca-feira)",
        (e - timedelta(days=2)).isoformat(): "Sexta-feira Santa",
        f"{year}-04-21": "Tiradentes",
        f"{year}-05-01": "Dia do Trabalho",
        (e + timedelta(days=60)).isoformat(): "Corpus Christi",
        f"{year}-09-07": "Independencia do Brasil",
        f"{year}-10-12": "Nossa Senhora Aparecida",
        f"{year}-11-02": "Finados",
        f"{year}-11-15": "Proclamacao da Republica",
        f"{year}-11-20": "Dia Nacional de Zumbi e da Consciencia Negra",
        f"{year}-12-25": "Natal",
    }
    return dict(sorted(rows.items()))


#: B3's own non-trading days beyond the national list. The exchange does not trade on 24 and 31
#: December, and those two are NOT national holidays -- a study using the national calendar will
#: find two phantom sessions a year with no bars in them.
_B3_EXTRA: dict[int, dict[str, str]] = {
    2024: {"2024-12-24": "B3: sem negociacao (vespera de Natal)",
           "2024-12-31": "B3: sem negociacao (vespera de Ano Novo)"},
    2025: {"2025-12-24": "B3: sem negociacao (vespera de Natal)",
           "2025-12-31": "B3: sem negociacao (vespera de Ano Novo)"},
    2026: {"2026-12-24": "B3: sem negociacao (vespera de Natal)",
           "2026-12-31": "B3: sem negociacao (vespera de Ano Novo)"},
}

HOLIDAYS_RULE: dict[str, Any] = {
    "rule": (
        "National closures are Lei 662/1949 and Lei 6.802/1980 plus the Easter anchor, with "
        "Consciencia Negra (20 November) national since Lei 14.759/2023 -- so 2024 is the FIRST "
        "year that day is a national closure and a pre-2024 sample must not carry it. Carnaval "
        "Monday and Tuesday are Easter-48 and Easter-47, Sexta-feira Santa is Easter-2 and Corpus "
        "Christi is Easter+60. Brazil does NOT move a holiday that falls at a weekend -- there is "
        "no substitution law -- so a Saturday holiday simply costs the market nothing. B3 adds 24 "
        "and 31 December as non-trading days, and those are in `b3_extra`, not in the national "
        "table, because the two calendars are different objects. Sao Paulo's municipal holiday "
        "(25 January) and the state holiday (9 July) close the CITY but NOT B3; that distinction "
        "has produced more than one phantom gap in public Brazilian backtests. Weekends are "
        "Saturday and Sunday."),
    "table": {2024: _br_year(2024), 2025: _br_year(2025), 2026: _br_year(2026)},
    "b3_extra": _B3_EXTRA,
    "years": (2024, 2025, 2026),
    "status": {2024: "CONFIRMED", 2025: "CONFIRMED",
               2026: "DERIVED from the statute plus the tabulated Easter; B3 publishes its own "
                     "calendar annually and that circular is the authority"},
    "weekly_closed": (5, 6),
    "half_days": "Carnaval Wednesday (Quarta-feira de Cinzas) is a HALF DAY: B3 opens at 13:00 "
                 "local (16:00 UTC). It is not a closure and not a normal session, and pooling it "
                 "with either is wrong.",
}


def holidays(year: int) -> dict[str, str]:
    """The national closure table for one year; `{}` for a year this pack does not declare."""
    return dict(HOLIDAYS_RULE["table"].get(year) or {})


def b3_closed(day: date) -> bool:
    """True when B3 does not trade: a weekend, a national closure, or 24/31 December."""
    if day.weekday() >= 5:
        return True
    iso = day.isoformat()
    return iso in holidays(day.year) or iso in (_B3_EXTRA.get(day.year) or {})


def dol_expiry(year: int, month: int) -> date:
    """The DOL/WDO expiry: the FIRST BUSINESS DAY of the contract month, rolled forward."""
    day = date(year, month, 1)
    while b3_closed(day):
        day += timedelta(days=1)
    return day


# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "B3 posicoes em aberto por tipo de investidor (DOL, IND, DI1)",
     "publisher": "B3", "frequency": "daily", "lag": "T+1 morning",
     "field": "open interest split into estrangeiro / institucional / pessoa fisica / "
              "instituicao financeira",
     "why": "the ONLY daily, free, exchange-published positioning split in this command. The "
            "foreign leg of the DOL book is the carry trade's own footprint.",
     "pit": True,
     "status": "declared; not collected on this box -- UNMEASURED until the lane fetches it"},
    {"name": "B3 fluxo de investidores (equity flow by investor type)",
     "publisher": "B3", "frequency": "daily", "lag": "T+1 evening",
     "field": "net buy/sell in BRL for foreign, institutional, retail and corporate",
     "why": "foreign equity flow LEADS its own FX conversion by one to two sessions because of "
            "D+2 settlement through custodians",
     "pit": True,
     "status": "declared; not collected on this box"},
    {"name": "CFTC Commitments of Traders -- 6L Brazilian Real (CME)",
     "publisher": "CFTC", "frequency": "weekly", "lag": "Friday 15:30 ET for Tuesday positions",
     "field": "non-commercial net, open interest",
     "why": "the offshore speculative leg of the carry trade",
     "pit": True,
     "status": "UNMEASURED ON THIS BOX: desks/mt5/data/axes/cot.json maps USDMXN and not USDBRL. "
               "Naming it here is the measurement; assuming Brazilian positioning is unavailable "
               "would be wrong, and assuming it is available would be worse."},
    {"name": "BCB outstanding FX swap stock (estoque de swap cambial)",
     "publisher": "BCB", "frequency": "daily", "lag": "same day",
     "field": "notional outstanding, tradicional less reverso",
     "why": "the central bank's own position; a rising traditional stock is the BCB short dollars "
            "forward, which is intervention with a published size",
     "pit": True,
     "status": "declared; SGS code not yet resolved -- the lane reports it needs_lookup"},
)

# --------------------------------------------------------------------------- terminology
#: THE PACK'S NATIVE VOCABULARY. A miner querying Brazilian sources in English finds the English-
#: language wire copy and nothing else; these are the words the market actually uses about itself.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "policy": ("Selic", "Meta Selic", "COPOM", "Comite de Politica Monetaria", "ata do Copom",
               "comunicado", "juro real", "IPCA", "IPCA-15", "meta de inflacao", "meta continua",
               "carta aberta", "Focus", "Relatorio de Mercado", "boletim Focus", "IGP-M",
               "Banco Central do Brasil", "Bacen", "CMN", "aperto monetario", "ciclo de alta"),
    "fx": ("PTAX", "dolar comercial", "dolar futuro", "casado", "cupom cambial", "fluxo cambial",
           "contrato de cambio", "swap cambial", "swap reverso", "leilao de linha",
           "intervencao cambial", "cambio flutuante", "real", "desvalorizacao", "apreciacao",
           "kit de reversao", "kit Brasil", "internalizacao de recursos", "boleta", "boletar"),
    "flow": ("exportadores", "nego de exportador", "fluxo comercial", "fluxo financeiro",
             "remessa de lucros e dividendos", "investimento direto no pais", "IDP",
             "capital estrangeiro", "B3 fluxo de investidores", "saida de estrangeiro"),
    "commodities": ("agro", "safra", "safrinha", "soja", "milho", "cafe arabica", "cafe robusta",
                    "acucar", "etanol", "minerio de ferro", "Petrobras paridade de importacao",
                    "PPI", "CONAB", "Abiove", "quebra de safra", "plantio", "colheita",
                    "premio do porto", "Paranagua", "Santos"),
    "market": ("Ibovespa", "IBOV", "mini indice", "WIN", "WDO", "DOL", "DI", "DI1", "curva de "
               "juros", "vertice", "tunel de rejeicao", "leilao de fechamento", "day trade",
               "gringo", "estrangeiro", "institucional", "pessoa fisica", "zeragem"),
    "fiscal": ("arcabouco fiscal", "teto de gastos", "resultado primario", "divida bruta",
               "DBGG", "Tesouro Nacional", "leilao do Tesouro", "NTN-B", "LTN", "LFT",
               "precatorios", "risco fiscal", "premio de risco", "CDS Brasil"),
    "community": ("InfoMoney", "Valor Economico", "Bastter", "Clube do Valor", "Rankia Brasil",
                  "Suno", "Empiricus", "Money Times", "Brazil Journal", "trader profissional"),
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
    {"id": "br_bcb_sgs", "layer": "official",
     "label": "BCB Sistema Gerenciador de Series Temporais (SGS)",
     "roots": ("https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados?formato=json",
               "https://www3.bcb.gov.br/sgspub/"),
     "languages": ("pt-BR", "en"), "licence": "public open data, no key, attribution requested",
     "access_label": "OPEN_DATA", "credibility": "AUTHORITATIVE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("serie historica Selic meta SGS", "PTAX venda serie 1 BCB",
                 "fluxo cambial contratado comercial e financeiro",
                 "reservas internacionais conceito liquidez"),
     "notes": "the spine of the lane. JSON and CSV, unauthenticated; dd/mm/yyyy dates and STRING "
              "values with a dot decimal are the two parsing traps"},
    {"id": "br_bcb_olinda", "layer": "official",
     "label": "BCB Olinda OData -- Expectativas de Mercado (Focus) and PTAX",
     "roots": ("https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/",
               "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"),
     "languages": ("pt-BR",), "licence": "public open data, no key; OData v4",
     "access_label": "OPEN_DATA", "credibility": "AUTHORITATIVE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("expectativa de mercado IPCA mediana Focus", "boletim Focus projecao Selic",
                 "cotacao do dolar PTAX boletim de fechamento"),
     "notes": "the ONE natively point-in-time Brazilian source: every row carries the survey Data "
              "beside DataReferencia, so a vintage is exact rather than modelled from a lag"},
    {"id": "br_ibge_sidra", "layer": "official",
     "label": "IBGE SIDRA (IPCA, IPCA-15, PIB, PNAD, PIM, PMC)",
     "roots": ("https://apisidra.ibge.gov.br/values/",
               "https://servicodados.ibge.gov.br/api/v3/agregados/"),
     "languages": ("pt-BR",), "licence": "public open data, no key",
     "access_label": "OPEN_DATA", "credibility": "AUTHORITATIVE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("IPCA-15 previa da inflacao tabela SIDRA", "IPCA grupos e subitens mensal",
                 "producao industrial PIM-PF"),
     "notes": "IPCA-15 is the PIT object a cell may trade; the headline lands around the 10th"},
    {"id": "br_comex_secex", "layer": "official",
     "label": "ComexStat / SECEX merchandise trade",
     "roots": ("https://comexstat.mdic.gov.br/", "https://api-comexstat.mdic.gov.br/"),
     "languages": ("pt-BR", "en"), "licence": "public open data, no key",
     "access_label": "OPEN_DATA", "credibility": "AUTHORITATIVE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("balanca comercial parcial semanal media diaria",
                 "exportacao de soja em graos por pais de destino",
                 "exportacao minerio de ferro para a China"),
     "notes": "the WEEKLY partial is the fast object -- the earliest read on the Chinese soy and "
              "iron-ore bid, published while the month is still running"},
    {"id": "br_conab_agro", "layer": "official",
     "label": "CONAB safra bulletins and MAPA crop statistics",
     "roots": ("https://www.conab.gov.br/info-agro/safras",
               "https://portaldeinformacoes.conab.gov.br/"),
     "languages": ("pt-BR",), "licence": "public; PDF/XLS bulletins plus an open-data portal",
     "access_label": "OPEN_DATA", "credibility": "AUTHORITATIVE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("levantamento de safra CONAB soja e milho boletim",
                 "quebra de safra estimativa de produtividade", "safrinha area plantada"),
     "notes": "the Brazilian counterpart of the USDA WASDE on a DIFFERENT date -- two independent "
              "crop prints a month instead of one"},
    {"id": "br_b3_market", "layer": "institutional",
     "label": "B3 market data, calendars, expiry tables and investor-flow files",
     "roots": ("https://www.b3.com.br/pt_br/market-data-e-indices/",
               "https://arquivos.b3.com.br/"),
     "languages": ("pt-BR", "en"),
     "licence": "public summary files free; intraday depth and tick are LICENSED products",
     "access_label": "PUBLIC_WITH_TERMS", "credibility": "AUTHORITATIVE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("posicoes em aberto por tipo de investidor DOL",
                 "calendario de vencimentos B3 dolar futuro",
                 "fluxo de investidores B3 estrangeiro institucional pessoa fisica",
                 "leilao de fechamento B3 horario"),
     "notes": "summary files are machine-readable; DEPTH IS LICENSED and is declared UNMEASURED "
              "rather than approximated from a CFD's synthetic spread"},
    {"id": "br_cvm_open", "layer": "institutional",
     "label": "CVM Dados Abertos (funds, issuers, filings)",
     "roots": ("https://dados.cvm.gov.br/dados/",
               "https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/",
               "https://dados.cvm.gov.br/dados/FI/DOC/CDA/DADOS/"),
     "languages": ("pt-BR",), "licence": "public open data (CC-BY), monthly CSV in ZIP",
     "access_label": "OPEN_DATA", "credibility": "AUTHORITATIVE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("informe diario de fundos captacao e resgate",
                 "composicao da carteira CDA fundo multimercado",
                 "fundos com investimento no exterior limite"),
     "notes": "AGGREGATED INSIDE THE LANE. `cvm_sensors` reduces to sector and cycle aggregates "
              "before anything leaves; no CNPJ reaches a docket (two-lane order, 2026-09-06)"},
    {"id": "br_academic", "layer": "academic",
     "label": "Brazilian economics and finance research (FGV/EPGE, IPEA, SciELO, ANPEC)",
     "roots": ("https://www.scielo.br/j/rbe/", "https://portal.fgv.br/publicacoes",
               "https://www.ipea.gov.br/portal/publicacoes/",
               "https://www.anpec.org.br/novosite/br/encontros-anteriores"),
     "languages": ("pt-BR", "en"), "licence": "open access (SciELO) and free working papers",
     "access_label": "PUBLIC", "credibility": "RELIABLE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("efeito calendario na bolsa brasileira anomalia",
                 "repasse cambial pass-through IPCA choque cambial",
                 "previsibilidade dos retornos do Ibovespa",
                 "fluxo de estrangeiros e retorno acionario no Brasil"),
     "notes": "a published Brazilian anomaly paper is a hypothesis with a citation and never a "
              "privileged claim; weak public claims are hypotheses (growth governance)"},
    {"id": "br_practitioner", "layer": "practitioner",
     "label": "Manager letters and sell-side macro (cartas de gestores, relatorios)",
     "roots": ("https://braziljournal.com/", "https://valor.globo.com/financas/",
               "https://www.anbima.com.br/pt_br/informar/relatorios/",
               "https://www.itau.com.br/itaubba-pt/analises-economicas/publicacoes"),
     "languages": ("pt-BR",), "licence": "public web; per-site terms, claims extracted only",
     "access_label": "PUBLIC_WITH_TERMS", "credibility": "RELIABLE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("carta do gestor macro Brasil posicionamento juros e cambio",
                 "kit de reversao kit Brasil operacao",
                 "fluxo de exportador no fim do mes dolar",
                 "carrego em juros nominais e NTN-B relatorio"),
     "notes": "the professional half of the forest. 'Kit Brasil' and 'kit de reversao' are named "
              "local trades -- testable mechanisms that exist in no English-language source"},
    {"id": "br_retail_ecology", "layer": "retail_ecology",
     "label": "Retail investor communities and trading-room culture",
     "roots": ("https://www.bastter.com/", "https://clubedovalor.com.br/blog/",
               "https://www.rankia.com.br/", "https://www.reddit.com/r/investimentos/",
               "https://forum.tradersclub.com.br/"),
     "languages": ("pt-BR",),
     "licence": "public web and public social; user-submitted, nothing republished",
     "access_label": "PUBLIC_SOCIAL", "credibility": "UNRELIABLE",
     "predictive_state": "NARRATIVE_FEATURE", "machine_use_allowed": True,
     "queries": ("day trade mini indice WIN estrategia",
                 "operar dolar WDO no fechamento", "robos de day trade resultado real",
                 "gringo comprando bolsa fluxo estrangeiro forum",
                 "stop no numero redondo dolar zeragem"),
     "notes": "UNRELIABLE AND KEPT, because the crowd's BELIEFS are the mechanism in BR-J: a "
              "crowd using the same levels is a supply of stops, so what they say they do has "
              "price consequences even when the claim itself is false"},
    {"id": "br_app_ecosystem", "layer": "app_ecosystem",
     "label": "Retail platforms, automation and their public code",
     "roots": ("https://www.mql5.com/pt/code", "https://www.nelogica.com.br/produtos/profit",
               "https://smarttbot.com/", "https://statusinvest.com.br/",
               "https://github.com/search?q=b3+backtest+language%3APython"),
     "languages": ("pt-BR",), "licence": "public web and public code repositories; per-site terms",
     "access_label": "PUBLIC_WITH_TERMS", "credibility": "UNRELIABLE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("robo trader WDO codigo fonte", "setup de day trade Profit Nelogica",
                 "estrategia automatizada mini indice MQL5",
                 "backtest B3 python biblioteca de dados"),
     "notes": "WHAT THE RETAIL BOOK IS AUTOMATED TO DO. A published robot's entry rule is a "
              "specific, testable statement about where the crowd's orders sit -- far more "
              "specific than any forum opinion, and it is code rather than talk"},
    {"id": "br_media", "layer": "media",
     "label": "Brazilian financial press",
     "roots": ("https://www.infomoney.com.br/", "https://valor.globo.com/",
               "https://www.moneytimes.com.br/", "https://exame.com/invest/"),
     "languages": ("pt-BR",),
     "licence": "public web with terms; several are paywalled and none is republished",
     "access_label": "PUBLIC_WITH_TERMS", "credibility": "RELIABLE",
     "predictive_state": "NARRATIVE_FEATURE", "machine_use_allowed": True,
     "queries": ("dolar fecha em alta fluxo estrangeiro",
                 "Copom decisao de juros reacao do mercado",
                 "reajuste da gasolina paridade de importacao",
                 "risco fiscal arcabouco mercado reage"),
     "notes": "a DATING source and a narrative feature, not evidence. Its value is that it dates "
              "the unscheduled fiscal and repricing events no official calendar carries"},
    {"id": "br_archive", "layer": "archive",
     "label": "Historical archives: BCB library, Hemeroteca Digital, exchange circulars",
     "roots": ("https://www.bcb.gov.br/acessoinformacao/biblioteca",
               "https://memoria.bn.gov.br/",
               "https://web.archive.org/web/*/bmfbovespa.com.br/*"),
     "languages": ("pt-BR",),
     "licence": "public archive; digitised public-domain and institutional material",
     "access_label": "PUBLIC_ARCHIVE", "credibility": "AUTHORITATIVE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("circular BM&F vencimento do dolar futuro historico",
                 "regulamento da PTAX consulta historica",
                 "horario de pregao historico bolsa brasileira"),
     "notes": "the era table's PRIMARY evidence. A rule change is dated by its circular and not "
              "by the day somebody wrote about it -- the pre-2019 DST rule lives only here"},
    {"id": "br_physical_economy", "layer": "physical_economy",
     "label": "Physical flow: ports, crush, fuel, power and freight",
     "roots": ("https://web.antaq.gov.br/anuario/", "https://unicadata.com.br/",
               "https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-estatisticos",
               "https://dados.ons.org.br/"),
     "languages": ("pt-BR",),
     "licence": "public open data (ANTAQ, ONS, ANP) and public industry statistics (UNICA)",
     "access_label": "OPEN_DATA", "credibility": "AUTHORITATIVE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("movimentacao portuaria Paranagua e Santos soja",
                 "UNICA moagem quinzenal mix acucar etanol",
                 "ANP vendas de combustiveis por distribuidora",
                 "carga de energia ONS demanda"),
     "notes": "COUNTED PHYSICAL QUANTITIES, separable from price -- the only way to ask whether "
              "the terms-of-trade channel is quantity or price. The UNICA fortnight IS the "
              "sugar/ethanol mix decision rather than a forecast of it"},
    {"id": "br_source_graph", "layer": "source_graph",
     "label": "The graph that finds the NEXT Brazilian source",
     "roots": ("https://www.bcb.gov.br/pec/wps/port/", "https://dados.gov.br/dados/conjuntos-dados",
               "https://github.com/topics/b3",
               "https://scholar.google.com/citations?view_op=search_venues"),
     "languages": ("pt-BR", "en"),
     "licence": "public; reference sections, citation lists and open-data catalogues",
     "access_label": "PUBLIC", "credibility": "RELIABLE",
     "predictive_state": "UNTESTED", "machine_use_allowed": True,
     "queries": ("referencias bibliograficas working paper BCB fonte de dados",
                 "quem cita a metodologia de safra da CONAB",
                 "conjunto de dados abertos financeiro dados.gov.br",
                 "repositorio github com dados da B3 quem usa"),
     "notes": "THE LAYER THAT STOPS THE LIST FREEZING. Every other layer is names somebody typed "
              "once; this one is the PROCEDURE for finding the names nobody has typed yet -- "
              "reference sections, open-data catalogues, and who reuses whose data"},
)

#: A layer with no source is named here WITH A REASON. Brazil currently reaches all ten, which is
#: a measurement of this pack's depth rather than a target: if a layer later becomes unreachable
#: it belongs here rather than quietly disappearing from the tuple above.
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
    {"name": "Meta Selic (BCB SGS 432)", "source": "br_bcb_sgs",
     "coverage": "1986-06 to present, daily step function", "frequency": "event (8/yr)",
     "publication_lag_days": 0.0,
     "revisions": "never revised; the level is a decision, not an estimate",
     "licence": "public open data", "history_from": "1986-06-04", "pit_feasible": True,
     "assets": ("USDBRL", "UST10Y", "XAUUSD"),
     "mechanism_families": ("carry_funding", "central_bank_surprise"),
     "how_to_fetch": "GET api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados?formato=json"},
    {"name": "PTAX venda diaria (BCB SGS 1)", "source": "br_bcb_sgs",
     "coverage": "1984-11 to present", "frequency": "daily",
     "publication_lag_days": 0.0,
     "revisions": "corrections are rare and are republished under the same date",
     "licence": "public open data", "history_from": "1984-11-28", "pit_feasible": True,
     "assets": ("USDBRL",),
     "mechanism_families": ("calendar_settlement", "session_microstructure"),
     "how_to_fetch": "GET api.bcb.gov.br/dados/serie/bcdata.sgs.1/dados?formato=json"},
    {"name": "PTAX four-consultation detail (Olinda PTAX OData)", "source": "br_bcb_olinda",
     "coverage": "2015 to present", "frequency": "4x daily",
     "publication_lag_days": 0.0,
     "revisions": "none", "licence": "public open data", "history_from": "2015-01-02",
     "pit_feasible": True,
     "assets": ("USDBRL",),
     "mechanism_families": ("calendar_settlement", "session_microstructure"),
     "how_to_fetch": "GET olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
                     "CotacaoDolarPeriodo(dataInicial=@d1,dataFinalCotacao=@d2)?$format=json"},
    {"name": "Focus market expectations -- Selic, IPCA, cambio, PIB (Olinda Expectativas)",
     "source": "br_bcb_olinda",
     "coverage": "2000 to present", "frequency": "weekly (published Monday 08:25 local)",
     "publication_lag_days": 3.0,
     "revisions": "none; each row is a dated survey observation and later rows are new surveys",
     "licence": "public open data", "history_from": "2000-01-03", "pit_feasible": True,
     "assets": ("USDBRL", "US500", "XAUUSD"),
     "mechanism_families": ("central_bank_surprise", "release_surprise"),
     "how_to_fetch": "GET olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/"
                     "ExpectativaMercadoMensais?$format=json&$filter=Indicador eq 'IPCA'"},
    {"name": "Fluxo cambial -- contratado comercial e financeiro", "source": "br_bcb_sgs",
     "coverage": "1982 to present", "frequency": "weekly and monthly",
     "publication_lag_days": 5.0,
     "revisions": "the weekly partial is superseded by the monthly total",
     "licence": "public open data", "history_from": "1982-01-01", "pit_feasible": True,
     "assets": ("USDBRL",),
     "mechanism_families": ("corporate_flow", "institutional_flow"),
     "how_to_fetch": "BCB Estatisticas do setor externo -- fluxo cambial; the SGS series code is "
                     "NOT yet resolved on this box and the lane reports it needs_lookup rather "
                     "than fetching a guessed code"},
    {"name": "Reservas internacionais (BCB SGS 3546 / 13621)", "source": "br_bcb_sgs",
     "coverage": "1970 to present", "frequency": "daily and monthly",
     "publication_lag_days": 1.0,
     "revisions": "occasional restatement of the liquidity concept",
     "licence": "public open data", "history_from": "1970-01-31", "pit_feasible": True,
     "assets": ("USDBRL", "XAUUSD"),
     "mechanism_families": ("institutional_flow", "carry_funding"),
     "how_to_fetch": "GET api.bcb.gov.br/dados/serie/bcdata.sgs.3546/dados?formato=json"},
    {"name": "IPCA and IPCA-15 (IBGE SIDRA 1737 / 3065)", "source": "br_ibge_sidra",
     "coverage": "1979 to present", "frequency": "monthly",
     "publication_lag_days": 9.0,
     "revisions": "IPCA is not revised; the annual weight update changes the basket, not history",
     "licence": "public open data", "history_from": "1979-12-01", "pit_feasible": True,
     "assets": ("USDBRL", "UST10Y"),
     "mechanism_families": ("release_surprise", "central_bank_surprise"),
     "how_to_fetch": "GET apisidra.ibge.gov.br/values/t/1737/n1/all/v/63/p/all"},
    {"name": "Balanca comercial mensal e parcial semanal (ComexStat/SECEX)",
     "source": "br_comex_secex",
     "coverage": "1997 to present", "frequency": "monthly, with weekly partials",
     "publication_lag_days": 4.0,
     "revisions": "the weekly partial is replaced by the monthly close",
     "licence": "public open data", "history_from": "1997-01-01", "pit_feasible": True,
     "assets": ("USDBRL", "SOYBEAN", "XCUUSD", "USDCNH"),
     "mechanism_families": ("corporate_flow", "release_surprise"),
     "how_to_fetch": "POST api-comexstat.mdic.gov.br/general with a JSON body naming the NCM "
                     "chapters for soy, iron ore, crude and sugar"},
    {"name": "CONAB safra survey (monthly crop bulletin)", "source": "br_conab_agro",
     "coverage": "1976 to present", "frequency": "monthly (bulletin, usually 2nd week)",
     "publication_lag_days": 10.0,
     "revisions": "each bulletin revises the running season estimate; the FIRST print is the "
                  "only PIT object and the final is not knowable in season",
     "licence": "public", "history_from": "1976-01-01", "pit_feasible": True,
     "assets": ("SOYBEAN", "CORN", "SUGAR", "COFARA", "USDBRL"),
     "mechanism_families": ("release_surprise", "corporate_flow"),
     "how_to_fetch": "portaldeinformacoes.conab.gov.br open data portal; bulletins are PDF/XLS "
                     "and the portal serves the same tables as CSV"},
    {"name": "CVM daily fund file aggregated to industry flow (INF_DIARIO_FI)",
     "source": "br_cvm_open",
     "coverage": "2005 to present", "frequency": "daily, published monthly in a ZIP",
     "publication_lag_days": 32.0,
     "revisions": "funds restate late; the monthly file is superseded by the next month's file "
                  "for overlapping dates",
     "licence": "public open data (CC-BY)", "history_from": "2005-01-03", "pit_feasible": True,
     "assets": ("USDBRL", "US500"),
     "mechanism_families": ("institutional_flow", "corporate_flow"),
     "how_to_fetch": "GET dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/inf_diario_fi_YYYYMM.zip "
                     "-- AGGREGATE to industry totals before anything leaves the lane"},
    {"name": "CVM fund portfolio composition aggregated to asset-class share (CDA)",
     "source": "br_cvm_open",
     "coverage": "2005 to present", "frequency": "monthly",
     "publication_lag_days": 90.0,
     "revisions": "three-month disclosure delay is the rule, not a lag to be modelled away",
     "licence": "public open data (CC-BY)", "history_from": "2005-01-31", "pit_feasible": True,
     "assets": ("USDBRL", "US500", "XAUUSD"),
     "mechanism_families": ("institutional_flow", "positioning"),
     "how_to_fetch": "GET dados.cvm.gov.br/dados/FI/DOC/CDA/DADOS/cda_fi_YYYYMM.zip -- the "
                     "offshore and equity SHARES are the sensors; no fund is named downstream"},
    {"name": "Credit stock and default rate (BCB SGS, Estatisticas monetarias e de credito)",
     "source": "br_bcb_sgs",
     "coverage": "2000 to present", "frequency": "monthly",
     "publication_lag_days": 25.0,
     "revisions": "routinely revised one period back",
     "licence": "public open data", "history_from": "2000-06-30", "pit_feasible": True,
     "assets": ("USDBRL", "US2000"),
     "mechanism_families": ("release_surprise", "corporate_flow"),
     "how_to_fetch": "BCB SGS credit aggregates; the exact code set is not resolved on this box "
                     "and the lane reports needs_lookup"},
    {"name": "B3 open interest by investor type (DOL, IND, DI1)", "source": "br_b3_market",
     "coverage": "2010 to present", "frequency": "daily",
     "publication_lag_days": 1.0,
     "revisions": "none", "licence": "public summary file", "history_from": "2010-01-04",
     "pit_feasible": True,
     "assets": ("USDBRL", "US500"),
     "mechanism_families": ("positioning", "institutional_flow"),
     "how_to_fetch": "arquivos.b3.com.br daily position files; not collected on this box yet"},
    {"name": "Brazilian practitioner mechanism claims (verbatim, pt-BR)",
     "source": "br_practitioner_forest",
     "coverage": "rolling", "frequency": "continuous",
     "publication_lag_days": 0.0,
     "revisions": "n/a -- claims are dated at capture and never rewritten",
     "licence": "public web, claims only", "history_from": "2015-01-01", "pit_feasible": False,
     "assets": ("USDBRL", "SOYBEAN", "US500"),
     "mechanism_families": ("scouts", "transfer"),
     "how_to_fetch": "deep_forest_miner grounds; pit_feasible is FALSE and every cell minted "
                     "from a claim is a hypothesis with a falsifier, never evidence"},
)

# --------------------------------------------------------------------------- actors
ACTORS: tuple[dict[str, Any], ...] = (
    {"name": "agricultural exporter (trading house / cooperative)",
     "holds": "physical soybeans, corn, sugar, coffee and a dollar receivable against them",
     "forced_to": ("sell dollars into reais to pay domestic costs (frete, armazenagem, folha)",
                   "hedge the flat price on CBOT/ICE while leaving the basis open",
                   "roll the FX hedge as shipment dates slip"),
     "when": "concentrated February-May for soy and July-September for the corn safrinha; within "
             "a month, around the PTAX windows and the last three business days",
     "information": ("ComexStat weekly partial exports", "CONAB safra bulletin", "port line-ups",
                     "Paranagua/Santos FOB premium"),
     "constraints": ("must convert to pay BRL costs regardless of the level",
                     "credit lines are secured against the cargo",
                     "cannot warehouse a perishable indefinitely"),
     "instruments": ("USDBRL", "SOYBEAN", "CORN", "SUGAR", "COFARA"),
     "counterparties": ("local banks", "Chinese crushers", "the BCB via registered contracts"),
     "observables": ("fluxo cambial comercial", "ComexStat weekly exports", "CONAB estimates"),
     "impact": "structural BRL buying in the safra window; a quantifiable seasonal in the fluxo "
               "cambial comercial series",
     "persistence": "seasonal and recurring; the WINDOW is stable and the size tracks the crop",
     "falsifier": "no measurable USDBRL drift difference between safra and non-safra months once "
                  "the dollar factor, the Selic differential and the commodity price level are "
                  "controlled for",
     "notes": "this is the flow every Brazilian trader calls 'exportador' and it is the cleanest "
              "forced flow in the pack because the timing is agronomic rather than discretionary"},
    {"name": "Petrobras and the fuel-import complex",
     "holds": "domestic refining capacity priced against an import-parity reference",
     "forced_to": ("buy dollars for crude and refined imports",
                   "reprice domestic fuel when the parity gap becomes fiscally intolerable",
                   "hedge a dollar-denominated debt stack"),
     "when": "continuous for imports; repricing is discrete, political and unannounced",
     "information": ("XBRUSD and XTIUSD", "the domestic-vs-parity gap", "ANP import statistics"),
     "constraints": ("state control makes the pricing rule political rather than mechanical",
                     "a widening parity gap is a fiscal liability that eventually resolves"),
     "instruments": ("USDBRL", "XTIUSD", "XBRUSD"),
     "counterparties": ("international oil majors", "distributors", "the Treasury"),
     "observables": ("the parity gap", "ANP volumes", "announced price changes"),
     "impact": "a dated, discrete BRL and inflation shock at each repricing; a continuous dollar "
               "bid from imports",
     "persistence": "the import bid is structural; the repricing shock decays within weeks",
     "falsifier": "no IPCA or USDBRL response to announced fuel repricings once the oil price "
                  "move that caused them is controlled for -- which would make the repricing an "
                  "echo of the oil move rather than an event of its own",
     "notes": "named as an ACTOR only. The two-lane order forbids any single-name equity cell "
              "here and none exists in this pack"},
    {"name": "iron ore and mining exporter",
     "holds": "iron ore volumes sold into a Chinese steel cycle at a dollar price",
     "forced_to": ("convert a share of receipts to reais for domestic costs and royalties",
                   "hedge nothing on the flat price -- the industry is famously unhedged"),
     "when": "shipment-linked, monthly, with a Chinese new-year trough and a fourth-quarter peak",
     "information": ("SGX 62% Fe curve", "Chinese port inventory", "ComexStat volumes"),
     "constraints": ("mine output is capital-bound and cannot respond within a quarter",
                     "weather (the Q1 rains) truncates shipments on a schedule"),
     "instruments": ("USDBRL", "XCUUSD", "USDCNH", "AUDUSD"),
     "counterparties": ("Chinese mills", "shipping", "the federal and state fiscs"),
     "observables": ("ComexStat iron ore volume", "SGX price", "Chinese steel margins"),
     "impact": "the terms-of-trade term in USDBRL; jointly with Australia it IS the Chinese "
               "industrial-demand read",
     "persistence": "cyclical, quarters not days",
     "falsifier": "USDBRL shows no sensitivity to the iron-ore complex once AUDUSD, the dollar "
                  "factor and Chinese equity risk are controlled for, which would make Brazil a "
                  "pure carry currency and not a commodity one",
     "notes": "the proxy chain is declared rather than hidden: SGX iron ore is not quotable here "
              "and XCUUSD plus AUDUSD carry the demand state"},
    {"name": "multinational subsidiary repatriating profits",
     "holds": "BRL earnings and a foreign parent's dollar reporting currency",
     "forced_to": ("remit dividends and interest on capital at declared dates",
                   "buy dollars in size through the contratos de cambio financeiros"),
     "when": "quarter ends, and heavily in the first quarter after the December balance date",
     "information": ("board dividend declarations", "the BRL level versus budget rate",
                     "tax treatment of juros sobre capital proprio"),
     "constraints": ("declared dividends must be paid",
                     "transfer-pricing and tax rules fix the timing more than the level does"),
     "instruments": ("USDBRL",),
     "counterparties": ("local banks", "the parent's treasury"),
     "observables": ("fluxo cambial financeiro", "BCB balance-of-payments income account"),
     "impact": "the largest recurring structural BRL-SELLING window of the year, opposite in sign "
               "to the exporter flow and on a different calendar",
     "persistence": "annual and quarterly, stable in timing",
     "falsifier": "no first-quarter USDBRL seasonal in the fluxo cambial financeiro series once "
                  "the global dollar's own January seasonal is removed",
     "notes": "this actor and the exporter are the two halves of 'fluxo cambial' and they net; "
              "a study using the NET number cannot see either"},
    {"name": "offshore carry investor (real-money and hedge fund)",
     "holds": "a long BRL position funded in dollars, expressed in NDFs, DOL futures or local "
              "bonds",
     "forced_to": ("cut on a vol shock because the carry-to-vol ratio is the position's whole "
                   "thesis",
                   "roll monthly as DOL contracts expire"),
     "when": "entry is opportunistic; the EXIT is forced and clustered",
     "information": ("Selic versus Fed funds", "realised and implied USDBRL vol",
                     "CFTC positioning", "B3 foreign open interest"),
     "constraints": ("VaR and stop discipline at the fund level",
                     "the monthly DOL roll is a calendar obligation"),
     "instruments": ("USDBRL", "USDJPY", "AUDJPY", "XAUUSD"),
     "counterparties": ("local banks", "B3 clearing", "other carry funds"),
     "observables": ("B3 open interest by investor type", "CFTC 6L net", "realised vol"),
     "impact": "carry-unwind cascades: USDBRL gaps in the same sessions as every other funded EM "
               "carry, which is what makes Brazil a GLOBAL risk instrument and not a local one",
     "persistence": "position builds over months and unwinds in days -- asymmetric by construction",
     "falsifier": "USDBRL drawdowns show no clustering with other high-carry EM crosses once the "
                  "dollar factor and global equity vol are controlled for",
     "notes": "the crossing point with the Japan package: the same book is often funded in yen"},
    {"name": "local bank FX and DI desk",
     "holds": "the casado book, the cupom cambial curve and the DI position against it",
     "forced_to": ("arbitrage the future against spot into the PTAX windows",
                   "square the dollar position over regulatory reporting dates",
                   "absorb the client flow the BCB registers"),
     "when": "intraday around the four PTAX consultations; month end for capital ratios",
     "information": ("the casado", "client flow", "the BCB's swap auction announcements"),
     "constraints": ("exposure limits are regulatory (Resolucao CMN) and binding",
                     "the PTAX methodology makes the average, not the close, the target"),
     "instruments": ("USDBRL",),
     "counterparties": ("exporters", "multinationals", "the BCB", "offshore funds"),
     "observables": ("casado level", "PTAX consultation dispersion", "DOL volume by window"),
     "impact": "the mechanical source of the PTAX-window microstructure: the ten minutes before "
               "each consultation is where the day's average is decided",
     "persistence": "permanent -- it is the market's plumbing",
     "falsifier": "no excess volatility or volume in USDBRL in the ten minutes preceding each "
                  "PTAX window relative to matched control minutes on the same days",
     "notes": "the only actor here whose mechanism is measurable on this box TODAY, because it "
              "lives in USDBRL bars and a clock"},
    {"name": "Banco Central do Brasil as an FX intervenor",
     "holds": "USD 340-370bn of reserves and an outstanding swap book",
     "forced_to": ("supply hedge when the local dollar market cannot clear",
                   "roll the traditional swap stock at published auctions"),
     "when": "announced, usually in the morning session; rolls are pre-announced",
     "information": ("the casado", "realised vol", "the reserve level", "the fiscal narrative"),
     "constraints": ("a floating-rate mandate means no level target may be admitted",
                     "the swap is BRL-settled, so intervention does not spend reserves"),
     "instruments": ("USDBRL", "XAUUSD"),
     "counterparties": ("local banks", "offshore funds"),
     "observables": ("announced auctions", "outstanding swap stock", "reserve series"),
     "impact": "a dated, announced, sized supply of dollar hedge -- the cleanest intervention "
               "observable in this command, and unusually, in real time",
     "persistence": "episodic; clusters in stress",
     "falsifier": "no USDBRL response to announced swap auctions beyond what the vol level at "
                  "announcement already predicts",
     "notes": "compare Korea (quarterly disclosure) and Argentina (opaque): Brazil's intervention "
              "is the transparent case and is therefore where the mechanism can be identified"},
    {"name": "Tesouro Nacional as a debt issuer",
     "holds": "a domestic debt stack of LTN, NTN-B and LFT with a published auction calendar",
     "forced_to": ("issue on the announced calendar regardless of the level",
                   "shorten duration or shift to LFT when demand for duration fails"),
     "when": "Tuesday and Thursday auctions; monthly and annual financing plans",
     "information": ("the DI curve", "the fiscal result", "the Focus IPCA path"),
     "constraints": ("refinancing needs are contractual",
                     "the debt profile is a published, tracked statistic"),
     "instruments": ("USDBRL", "UST10Y"),
     "counterparties": ("local banks", "pension funds", "offshore real money"),
     "observables": ("auction results and cut-off rates", "the DBGG series",
                     "the primary result"),
     "impact": "a failed or heavily-discounted auction is a fiscal-risk event that reaches FX "
               "within the session",
     "persistence": "episodic; clusters with fiscal news",
     "falsifier": "no USDBRL or risk-premium response to auction cut-offs once the global rates "
                  "move on the same day is controlled for",
     "notes": "the DI curve is the transmission medium and is not on this box; UST10Y is the only "
              "duration control available and the substitution is declared"},
    {"name": "domestic pension fund and asset manager (EFPC / gestora)",
     "holds": "BRL liabilities against a portfolio whose offshore allocation is capped and "
              "recently liberalised",
     "forced_to": ("rebalance toward NTN-B when the real rate clears the actuarial target",
                   "sell equities when the risk-free alone meets the liability"),
     "when": "when the real rate crosses the actuarial hurdle -- a THRESHOLD, not a calendar",
     "information": ("the NTN-B real rate", "the actuarial target",
                     "CVM portfolio disclosures"),
     "constraints": ("CMN allocation limits", "actuarial solvency rules",
                     "a real rate above the target makes risk assets economically unnecessary"),
     "instruments": ("USDBRL", "US500", "XAUUSD"),
     "counterparties": ("the Treasury", "B3", "offshore managers"),
     "observables": ("CVM CDA asset-class shares (aggregated)", "ANBIMA industry statistics"),
     "impact": "a real-rate threshold effect on domestic risk appetite that propagates into "
               "foreign-asset demand and therefore into FX",
     "persistence": "slow, quarters; the threshold makes it non-linear rather than gradual",
     "falsifier": "no discontinuity in the aggregated equity or offshore share of fund portfolios "
                  "around the actuarial real-rate threshold",
     "notes": "the CVM lane exists to measure exactly this and it aggregates before publishing"},
    {"name": "Brazilian retail derivatives trader (pessoa fisica on WDO/WIN)",
     "holds": "intraday mini-contract positions, overwhelmingly day-traded",
     "forced_to": ("close at the day's end because overnight margin is punitive",
                   "stop out in clusters because the crowd uses the same levels"),
     "when": "the local session, 13:00-20:00 UTC, with a forced flattening into the close",
     "information": ("B3's own investor-type prints", "the retail education complex",
                     "Brazilian trading-room chatter"),
     "constraints": ("overnight margin", "day-trade tax treatment",
                     "the broker-imposed forced closing hour"),
     "instruments": ("USDBRL",),
     "counterparties": ("market makers", "institutional desks"),
     "observables": ("B3 pessoa fisica open interest and volume share",
                     "the end-of-session volume spike"),
     "impact": "a dated, mechanical liquidation window near the local close; a supply of stops at "
               "round numbers that makes failed breakouts more likely than clean ones",
     "persistence": "structural while the tax and margin regime holds",
     "falsifier": "no excess reversal or volume in USDBRL in the final thirty minutes of the "
                  "Brazilian session relative to matched control windows",
     "notes": "this is the pack's microstructure actor and it is the one that produces cells "
              "TODAY with no external data at all"},
    {"name": "Chinese crusher and steel mill as the demand counterparty",
     "holds": "processing capacity that must be fed with Brazilian soybeans and iron ore",
     "forced_to": ("buy Brazilian cargoes when the crush margin is positive",
                   "switch origin between Brazil and the US on the basis, not the flat price"),
     "when": "Brazil-dominant February-July; US-dominant September-January",
     "information": ("crush margins", "the Paranagua vs Gulf basis", "port inventory"),
     "constraints": ("capacity is fixed in the short run",
                     "policy (reserves, tariffs) can override the margin"),
     "instruments": ("SOYBEAN", "CORN", "USDCNH", "USDBRL", "XCUUSD"),
     "counterparties": ("Brazilian exporters", "US exporters", "shipping"),
     "observables": ("ComexStat exports by destination", "Chinese customs",
                     "the origin basis spread"),
     "impact": "the demand half of the Brazilian terms of trade; the ORIGIN SWITCH is a seasonal "
               "with a known date range and is testable in the soybean/BRL relationship",
     "persistence": "seasonal, structural",
     "falsifier": "no seasonal difference in the SOYBEAN-USDBRL relationship between the Brazilian "
                  "and US export windows once the dollar factor is removed",
     "notes": "the first leg of the cross-region triple with the CL/PE copper channel"},
    {"name": "federal and state fiscal authority",
     "holds": "a primary balance under the arcabouco fiscal rule and a rising gross debt ratio",
     "forced_to": ("announce contingency measures when the rule's band is threatened",
                   "settle precatorios on a constitutional schedule"),
     "when": "bimonthly revenue-expenditure reports; the annual budget cycle; ad hoc announcements",
     "information": ("the primary result series", "DBGG", "Focus fiscal expectations"),
     "constraints": ("the fiscal rule is a law with a band",
                     "constitutionally mandated spending floors limit discretion"),
     "instruments": ("USDBRL", "UST10Y", "US2000"),
     "counterparties": ("the Treasury", "Congress", "bondholders"),
     "observables": ("primary result", "DBGG", "CDS Brasil", "the NTN-B real rate"),
     "impact": "Brazilian risk premium is a FISCAL variable more than a monetary one; the largest "
               "USDBRL moves of the sample cluster on fiscal, not Copom, dates",
     "persistence": "regime-length; it defines the policy eras below",
     "falsifier": "USDBRL jump days cluster no more densely around fiscal announcements than "
                  "around Copom dates once the size of the global risk move is controlled for",
     "notes": "this is the actor that makes Brazil's carry cell conditional -- a high real rate "
              "with a deteriorating fiscal is not the same trade as a high real rate without one"},
    {"name": "coffee and sugar producer with an ethanol option",
     "holds": "cane that can be crushed for sugar or ethanol, and arabica inventory",
     "forced_to": ("switch the cane mix toward whichever of sugar and ethanol pays",
                   "sell forward to fund the harvest"),
     "when": "the April-November cane harvest; arabica flowering in September-October decides "
             "the next crop",
     "information": ("the sugar-ethanol parity", "UNICA fortnightly crush data",
                     "frost and drought bulletins"),
     "constraints": ("the mix is decided weeks ahead and cannot be reversed",
                     "a frost event is irreversible for two seasons"),
     "instruments": ("SUGAR", "SUGARRAW", "COFARA", "COFROB", "USDBRL"),
     "counterparties": ("trading houses", "domestic fuel distributors"),
     "observables": ("UNICA crush reports", "the parity spread", "CONAB coffee survey"),
     "impact": "Brazil is the price-setter in both arabica and raw sugar; a Brazilian weather "
               "event is a GLOBAL softs event and reaches the BRL through the export receipt",
     "persistence": "one to two seasons for a weather shock; the mix switch is fortnightly",
     "falsifier": "no arabica-robusta spread response to Brazilian weather episodes beyond the "
                  "response of the flat price -- which would mean the shock is global rather "
                  "than Brazilian-origin",
     "notes": "COFROB (robusta, largely Vietnamese) is the built-in negative control for every "
              "arabica claim in this pack"},
)

# --------------------------------------------------------------------------- domains
_CONTROLS = ("a matched non-event day of the same weekday and month",
             "the global dollar factor (USDX) and US500 on the same session",
             "a placebo instrument with no Brazilian exposure")

DOMAINS: tuple[dict[str, Any], ...] = (
    {"id": "BR-A", "title": "Copom decision and the ata: surprise versus the Focus path",
     "objects": ("the Selic decision against the Focus median", "the 18:30 comunicado",
                 "the Tuesday ata and its dissent count"),
     "conditions": ("announcement falls after the local close, so the first tradable reaction is "
                    "the next session's open",
                    "the surprise must be measured against a SURVEY, not a traded curve"),
     "instruments": ("USDBRL", "UST10Y", "XAUUSD", "US500"),
     "controls": (*_CONTROLS, "non-Copom Wednesdays with the same US calendar"),
     "notes": "the survey-vs-curve gap is itself a research object once DI is collected"},
    {"id": "BR-B", "title": "The PTAX window microstructure",
     "objects": ("the ten minutes before each of the four consultations",
                 "consultation dispersion", "the day-before-expiry window"),
     "conditions": ("Brazilian local session only", "no DST since 2019 -- fixed UTC windows"),
     "instruments": ("USDBRL",),
     "controls": (*_CONTROLS, "matched ten-minute windows on the same days at non-fixing hours"),
     "notes": "the one domain here measurable on this box today with nothing but bars and a clock"},
    {"id": "BR-C", "title": "The DOL expiry and roll calendar",
     "objects": ("the first business day of each month", "the three days of roll before it",
                 "the PTAX D-1 settlement window"),
     "conditions": ("expiry is the FIRST business day, not a third Friday",
                    "settlement is known before the last trading session ends"),
     "instruments": ("USDBRL",),
     "controls": (*_CONTROLS, "the first business day of months in a pre-2002 regime where the "
                              "contract was different"),
     "notes": "a wrong expiry constant here silently inverts the sign of the whole domain"},
    {"id": "BR-D", "title": "Fluxo cambial: exporter conversion against dividend repatriation",
     "objects": ("the weekly commercial flow", "the weekly financial flow",
                 "their seasonal peaks in opposite months"),
     "conditions": ("the NET number hides both legs and must never be the regressor",
                    "the flow is registered at the contract, not at settlement"),
     "instruments": ("USDBRL", "SOYBEAN", "CORN"),
     "controls": (*_CONTROLS, "the same calendar months in years with a crop failure"),
     "notes": "the series code is unresolved; the domain is BLOCKED_ON_DATA and says so"},
    {"id": "BR-E", "title": "Terms of trade: iron ore, crude and the safra in one current account",
     "objects": ("ComexStat monthly and weekly exports by chapter",
                 "the commodity index in BRL (IC-Br)", "the trade balance"),
     "conditions": ("the dollar price and the BRL price move differently and the BRL one is what "
                    "the BCB reacts to",
                    "volume and price must be separated or the channel cannot be attributed"),
     "instruments": ("USDBRL", "XCUUSD", "XTIUSD", "SOYBEAN", "SUGAR"),
     "controls": (*_CONTROLS, "AUDUSD as the other China-facing commodity currency"),
     "notes": "the negative control is the point: if AUD moves and BRL does not, the channel is "
              "Chinese demand and not Brazilian supply"},
    {"id": "BR-F", "title": "The carry trade and its unwind",
     "objects": ("the Selic-Fed differential", "realised and implied USDBRL vol",
                 "the carry-to-vol ratio", "drawdown clustering across EM crosses"),
     "conditions": ("entry is gradual and exit is clustered -- the distribution is asymmetric "
                    "by construction and a symmetric test will find nothing",),
     "instruments": ("USDBRL", "USDMXN", "USDZAR", "USDTRY", "AUDJPY", "USDJPY", "XAUUSD"),
     "controls": (*_CONTROLS, "a zero-carry cross with the same vol (EURUSD)"),
     "notes": "this domain is the bridge to the Japan carry state in the cross-region triple"},
    {"id": "BR-G", "title": "Fiscal risk premium as the conditioning state",
     "objects": ("the primary result and DBGG prints", "arcabouco compliance announcements",
                 "the NTN-B real rate", "CDS Brasil"),
     "conditions": ("fiscal events are unscheduled, so an event study needs a dated announcement "
                    "list built from the source rather than a calendar",),
     "instruments": ("USDBRL", "UST10Y", "US2000"),
     "controls": (*_CONTROLS, "Copom dates as the scheduled-event comparison class"),
     "notes": "the hypothesis is CONDITIONAL: carry pays in a stable fiscal state and does not in "
              "a deteriorating one, and the two must be estimated separately"},
    {"id": "BR-H", "title": "The safra calendar and the softs complex",
     "objects": ("CONAB bulletin dates and revisions", "planting and harvest windows",
                 "the arabica flowering window", "UNICA crush fortnights"),
     "conditions": ("the FIRST print of a season estimate is the only PIT object",
                    "weather shocks are irreversible and asymmetric"),
     "instruments": ("SOYBEAN", "CORN", "SUGAR", "SUGARRAW", "COFARA", "COFROB", "USDBRL"),
     "controls": (*_CONTROLS, "COFROB as the non-Brazilian coffee control",
                              "USDA WASDE dates as the competing information event"),
     "notes": "two independent crop prints a month is the structural advantage of this domain"},
    {"id": "BR-I", "title": "Intervention: announced swap auctions and the reserve stock",
     "objects": ("auction announcements and sizes", "the outstanding swap stock",
                 "reserve-level changes"),
     "conditions": ("announcement precedes execution, so the event is the ANNOUNCEMENT minute",
                    "the swap is BRL-settled and spends no reserves -- a reserve fall is a "
                    "different event from a swap auction and pooling them is wrong"),
     "instruments": ("USDBRL", "XAUUSD"),
     "controls": (*_CONTROLS, "high-vol days with no auction as the matched control"),
     "notes": "the transparent intervention case in this command; Chile is the pre-announced "
              "programme case and Argentina the opaque one"},
    {"id": "BR-J", "title": "Retail and the local-session close",
     "objects": ("the last thirty minutes of the Brazilian session",
                 "B3 pessoa fisica volume share", "round-number clustering"),
     "conditions": ("day-trade tax and overnight margin force flattening",
                    "the effect must be measured in local-session minutes, not UTC hours, "
                    "because the broker's clock shifts and Brazil's does not"),
     "instruments": ("USDBRL",),
     "controls": (*_CONTROLS, "the equivalent window on Brazilian holidays when the local "
                              "session is closed but the CFD still quotes"),
     "notes": "the Brazilian-holiday control is unusually clean: the instrument keeps trading "
              "while the actor is absent"},
    {"id": "BR-K", "title": "Brazil as an EM-stress instrument",
     "objects": ("joint drawdowns with MXN, ZAR, TRY", "the dollar factor",
                 "gold's behaviour in EM stress"),
     "conditions": ("the question is whether Brazil LEADS or FOLLOWS the EM complex, and the "
                    "answer is likely regime-dependent",),
     "instruments": ("USDBRL", "USDMXN", "USDZAR", "USDTRY", "XAUUSD", "US500"),
     "controls": (*_CONTROLS, "developed high-beta (AUDUSD) as the non-EM comparison"),
     "notes": "feeds the Argentina reserve-stress channel from the other side"},
    {"id": "BR-L", "title": "Fund-industry flow as a domestic risk-appetite sensor",
     "objects": ("aggregated CVM daily net captacao", "the equity-fund share",
                 "the offshore-allocation share"),
     "conditions": ("a 32-day publication lag makes this a SLOW sensor and it must never be used "
                    "at a daily horizon",
                    "aggregation happens inside the lane -- no fund is identifiable downstream"),
     "instruments": ("USDBRL", "US500"),
     "controls": (*_CONTROLS, "the same months in a low-Selic regime"),
     "notes": "the two-lane order is enforced here by the lane's own aggregation, not by taste"},
    {"id": "BR-M", "title": "Practitioner claims, converted and falsified",
     "objects": ("'kit de reversao' and 'kit Brasil' as named local trades",
                 "month-end exporter lore", "the 'gringo' flow narrative"),
     "conditions": ("a claim is a hypothesis with a falsifier and never evidence",
                    "no single-name claim may be converted"),
     "instruments": ("USDBRL", "US500"),
     "controls": (*_CONTROLS, "the same rule applied to a country with no such folklore"),
     "notes": "the deep-forest lane in Portuguese; the vocabulary in TERMINOLOGY is what makes "
              "the query find anything at all"},
)

# --------------------------------------------------------------------------- miners
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    {"name": "br_ptax_window", "domain_ids": ("BR-B", "BR-C"), "kind": "calendar",
     "entry": "research.countries.br.pack:ptax_windows_utc", "cadence_s": 3600.0,
     "steerable": False,
     "notes": "the four fixed UTC windows a session miner conditions on"},
    {"name": "br_dol_expiry", "domain_ids": ("BR-C",), "kind": "calendar",
     "entry": "research.countries.br.pack:dol_expiry", "cadence_s": 86400.0,
     "steerable": False,
     "notes": "first business day of the contract month, rolled over closures"},
    {"name": "br_sgs_lane", "domain_ids": ("BR-A", "BR-D", "BR-E", "BR-I"), "kind": "mechanism",
     "entry": "research.countries.br.data_plane:fetch", "cadence_s": 21600.0,
     "steerable": True,
     "notes": "the BCB SGS and Olinda lane with its vintage store"},
    {"name": "br_cvm_sensors", "domain_ids": ("BR-L",), "kind": "mechanism",
     "entry": "research.countries.br.data_plane:cvm_sensors", "cadence_s": 86400.0,
     "steerable": True,
     "notes": "CVM open data aggregated to sector and cycle sensors; never a single name"},
)

#: The four PTAX consultation windows in UTC, as (start, end). Fixed year-round because Brazil
#: abolished DST in 2019; a pre-2019 sample must shift the southern-summer leg by one hour.
PTAX_WINDOWS_UTC: tuple[tuple[str, str], ...] = (
    ("13:00", "13:10"), ("14:00", "14:10"), ("15:00", "15:10"), ("16:00", "16:10"))


def ptax_windows_utc() -> tuple[tuple[str, str], ...]:
    """The four PTAX consultation windows in UTC. Named as a miner entry so a session miner can
    condition on them without importing the whole pack."""
    return PTAX_WINDOWS_UTC


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
    {"id": "br_carry_to_usdbrl", "source": "Selic-Fed differential and the Focus Selic path",
     "mechanism": "a wider real-rate differential funds a larger carry position, which is BRL "
                  "buying while it is built and BRL selling when it is cut",
     "targets": ("USDBRL", "USDMXN", "USDZAR"), "sign": "opposite",
     "horizon": "1-20 sessions", "lag": "0-3 sessions",
     "control": "USDX and the same-day US500 move; EURUSD as the zero-carry comparison",
     "evidence": "HYPOTHESIS",
     "notes": "the single most crowded EM position in the sample; its unwind is the object"},
    {"id": "br_carry_stress_to_gold",
     "source": "USDBRL realised vol and the EM carry drawdown cluster",
     "mechanism": "a carry unwind is a dollar-funding event; gold is bid as the funding currency "
                  "strengthens against everything except itself",
     "targets": ("XAUUSD", "XAGUSD"), "sign": "same",
     "horizon": "1-10 sessions", "lag": "0-2 sessions",
     "control": "US500 drawdown of the same magnitude with no EM component",
     "evidence": "HYPOTHESIS",
     "notes": "the principal's 'local state as a SENSOR for XAUUSD' instruction, in one edge"},
    {"id": "br_iron_oil_agri_to_commodities",
     "source": "ComexStat export volumes and the Brazilian terms of trade",
     "mechanism": "Brazilian supply is a large share of world soy, sugar, coffee and iron ore; a "
                  "supply state moves the global price before it moves the currency",
     "targets": ("SOYBEAN", "SUGAR", "COFARA", "XCUUSD"), "sign": "opposite",
     "horizon": "5-60 sessions", "lag": "1-10 sessions",
     "control": "COFROB for the coffee leg; CORN for the non-Brazilian grain leg",
     "evidence": "HYPOTHESIS",
     "notes": "supply-side, so the sign is opposite: more Brazilian supply, lower world price"},
    {"id": "br_petro_parity_to_oil",
     "source": "the domestic-vs-import-parity fuel gap and announced repricings",
     "mechanism": "a suppressed domestic price is a fiscal liability that resolves in a discrete "
                  "repricing; the anticipation of it trades in crude and in the BRL together",
     "targets": ("XTIUSD", "XBRUSD", "USDBRL"), "sign": "same",
     "horizon": "1-15 sessions", "lag": "0-5 sessions",
     "control": "crude moves of the same size with no Brazilian repricing pending",
     "evidence": "HYPOTHESIS",
     "notes": "the actor is Petrobras and the instrument is never Petrobras"},
    {"id": "br_flow_seasonal_to_usdbrl",
     "source": "fluxo cambial comercial and financeiro, weekly",
     "mechanism": "exporter conversion and dividend repatriation are forced flows on OPPOSITE "
                  "calendars; the net series hides both and the legs are the signal",
     "targets": ("USDBRL",), "sign": "opposite",
     "horizon": "5-25 sessions", "lag": "1-5 sessions",
     "control": "the same calendar weeks in years with a crop failure",
     "evidence": "HYPOTHESIS",
     "notes": "BLOCKED_ON_DATA until the SGS code is resolved -- and it says so rather than "
              "reporting an empty result"},
    {"id": "br_fiscal_to_em_risk",
     "source": "fiscal announcements, the primary result and the NTN-B real rate",
     "mechanism": "Brazilian fiscal risk is the largest idiosyncratic EM risk premium in the "
                  "sample; it repriced the whole EM complex in 2024-12 and again in 2025",
     "targets": ("USDBRL", "USDMXN", "USDZAR", "US2000"), "sign": "same",
     "horizon": "1-20 sessions", "lag": "0-2 sessions",
     "control": "US fiscal and rates events of the same magnitude on the same days",
     "evidence": "HYPOTHESIS",
     "notes": "this is what makes the BR carry cell conditional rather than unconditional"},
    {"id": "br_china_demand_to_aud",
     "source": "Brazilian iron-ore and soy exports to China (ComexStat by destination)",
     "mechanism": "Brazil and Australia sell the same Chinese demand; a Brazilian volume surprise "
                  "is information about that demand and the liquid expression is AUD",
     "targets": ("AUDUSD", "USDCNH", "XCUUSD"), "sign": "same",
     "horizon": "5-40 sessions", "lag": "1-10 sessions",
     "control": "AUD moves driven by RBA policy with no Chinese trade component",
     "evidence": "HYPOTHESIS",
     "notes": "the Brazil leg of the copper/China cross-region triple"},
    {"id": "br_safra_to_softs_and_brl",
     "source": "CONAB safra bulletins, UNICA crush, arabica flowering weather",
     "mechanism": "Brazil sets the world arabica and raw-sugar price; a Brazilian crop state is "
                  "therefore a global softs event AND a Brazilian export-receipt event",
     "targets": ("COFARA", "SUGAR", "SUGARRAW", "SOYBEAN", "USDBRL"), "sign": "opposite",
     "horizon": "10-120 sessions", "lag": "1-15 sessions",
     "control": "COFROB and non-Brazilian sugar origins; USDA WASDE as the competing print",
     "evidence": "HYPOTHESIS",
     "notes": "the agriculture leg the principal asked for, with its negative control built in"},
    {"id": "br_ptax_window_to_usdbrl",
     "source": "the four PTAX consultation windows",
     "mechanism": "every USD-settled Brazilian contract references a window AVERAGE, so the "
                  "minutes before each window carry a mechanical, dated flow",
     "targets": ("USDBRL",), "sign": "same",
     "horizon": "intraday", "lag": "0",
     "control": "matched ten-minute windows at non-fixing hours on the same days",
     "evidence": "HYPOTHESIS",
     "notes": "the one edge in this pack that needs no external data to test"},
    {"id": "br_local_close_to_usdbrl",
     "source": "the forced retail flattening into the Brazilian close",
     "mechanism": "day-trade tax and overnight margin force a mechanical liquidation window; a "
                  "crowd with the same levels is a supply of stops",
     "targets": ("USDBRL",), "sign": "opposite",
     "horizon": "intraday", "lag": "0",
     "control": "the same window on Brazilian holidays, when the CFD quotes and the actor is away",
     "evidence": "HYPOTHESIS",
     "notes": "the holiday control makes the actor's ABSENCE observable, which is rare"},
)

#: Authored in the desk's vocabulary; `_dual` adds the framework's.
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = _dual(_EDGE_ROWS)


# --------------------------------------------------------------------------- eras
_ERA_ROWS: tuple[dict[str, Any], ...] = (
    {"id": "br_covid_zero_rate", "start": "2020-03-18", "end": "2021-03-16",
     "label": "Selic at 2.00%: the first negative real rate in Brazilian history",
     "what_changed": "the carry trade INVERTED -- the real became a funding currency and foreign "
                     "positioning went flat or short for the first time in the sample",
     "invalidates": "any carry estimate pooled across this window is averaging a long-carry and a "
                    "short-carry regime and will report a null that is about the pooling"},
    {"id": "br_hiking_cycle_2021_2022", "start": "2021-03-17", "end": "2022-08-03",
     "label": "Selic 2.00% -> 13.75% in seventeen months",
     "what_changed": "the fastest hiking cycle in the inflation-targeting era rebuilt the carry "
                     "position from nothing",
     "invalidates": "a Copom surprise study that pools this cycle with the 2023-2025 easing is "
                    "pooling opposite reaction functions"},
    {"id": "br_new_fiscal_framework", "start": "2023-08-31", "end": None,
     "label": "The arcabouco fiscal (Lei Complementar 200/2023) replaces the spending cap",
     "what_changed": "the fiscal rule became a band with a primary-result target rather than a "
                     "hard real-spending ceiling, so fiscal news became CONTINUOUS rather than "
                     "binary",
     "invalidates": "fiscal-event studies from the teto de gastos era do not transfer: the events "
                    "they were dated on no longer exist"},
    {"id": "br_continuous_target", "start": "2025-01-01", "end": None,
     "label": "The inflation target becomes CONTINUOUS rather than calendar-year",
     "what_changed": "the breach test became six consecutive months outside the band, which moves "
                     "WHEN the Governor must explain and therefore when the reaction function "
                     "binds",
     "invalidates": "a Copom reaction function fitted on calendar-year-target data mis-times the "
                    "constraint in both directions"},
    {"id": "br_bcb_autonomy", "start": "2021-02-25", "end": None,
     "label": "Formal BCB autonomy with fixed staggered terms (LC 179/2021)",
     "what_changed": "board turnover became a SCHEDULED political event with published dates, "
                     "which makes composition risk datable",
     "invalidates": "pre-2021 policy-surprise estimates carry a political-pressure term that the "
                    "post-2021 sample does not, and the 2025 board handover is its own break"},
    {"id": "br_no_dst", "start": "2019-11-03", "end": None,
     "label": "Brazil abolishes daylight saving (Decreto 9.772/2019)",
     "what_changed": "every Brazilian UTC timestamp became fixed year-round while the broker's "
                     "own clock kept shifting",
     "invalidates": "ANY intraday Brazilian study pooled across this date is misaligned by one "
                    "hour for part of each pre-2019 year, and the PTAX windows are the exact "
                    "object that misaligns"},
    {"id": "br_selic_15", "start": "2025-06-19", "end": None,
     "label": "Selic at 15.00%: the highest nominal rate since 2006",
     "what_changed": "the real rate cleared most domestic actuarial hurdles, which is the "
                     "threshold BR-K is about",
     "invalidates": "domestic risk-appetite estimates from a sub-hurdle regime do not transfer "
                    "across the threshold"},
)

POLICY_ERAS: tuple[dict[str, Any], ...] = _named_eras(_ERA_ROWS)


# --------------------------------------------------------------------------- access constraints
ACCESS_CONSTRAINTS: tuple[dict[str, Any], ...] = (
    {"constraint": "the DI curve is the transmission medium for every Brazilian rates mechanism "
                   "and this box holds none of it",
     "measured": "universe.json has UST05Y and UST10Y and no Brazilian rates instrument",
     "consequence": "every rates edge routes through USDBRL with the local term premium declared "
                    "UNMEASURED; a cell claiming to trade Brazilian duration is trading USDBRL"},
    {"constraint": "B3 intraday depth and tick are licensed products",
     "measured": "public B3 files are end-of-day summaries",
     "consequence": "PTAX-window microstructure runs on the broker's own USDBRL tape; order-book "
                    "claims are UNMEASURED rather than approximated from a CFD spread"},
    {"constraint": "CFTC positioning for BRL is not in the desk's COT axis",
     "measured": "data/axes/cot.json maps 22 symbols including USDMXN and not USDBRL",
     "consequence": "the offshore leg of the carry position is UNMEASURED BY NAME; the B3 "
                    "investor-type file is the substitute and is not yet collected"},
)

# --------------------------------------------------------------------------- assembly
_PACK_FIELDS: tuple[str, ...] = (
    "code", "name", "region_command", "currency", "executable_instruments", "central_bank",
    "fixing_conventions", "settlement_conventions", "exchanges", "holidays_rule",
    "fiscal_year_end", "positioning_sources", "native_languages", "terminology", "source_classes",
    "datasets", "actors", "domains", "custom_miners", "transmission_edges_seed", "policy_eras")

MISSION = ("mine Brazil to exhaustion as the anchor of the SOUTH AMERICA command: the largest "
           "funded carry position in EM FX, a fixing that is a four-window average rather than a "
           "snapshot, a dollar future that expires on the first business day and settles to "
           "yesterday's fix, and a current account made of four commodities this desk already "
           "quotes -- and use every one of those states as a SENSOR for XAUUSD, oil, the softs "
           "and global risk, not only as a reason to trade USDBRL")


def as_dict() -> dict[str, Any]:
    """The pack as a plain mapping, with the extras the frozen dataclass has no field for kept
    alongside rather than silently dropped."""
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
    """Put the repository root on `sys.path` so the lazy `libs.research` import can succeed even
    when this file was loaded BY PATH (`transmission_engine.load_packs` does exactly that)."""
    root = str(Path(__file__).resolve().parents[5])
    if root not in sys.path:
        sys.path.insert(0, root)


def pack() -> Any:
    """`libs.research.country_lab.CountryPack` when that module has landed, else this mapping.

    IMPORTED LAZILY AND ON PURPOSE. `country_lab` is a sibling builder's file; a module-scope
    import would make the whole country department un-importable on a tree where it has not
    arrived, and the DATA is the deliverable here rather than the container.
    """
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


#: `transmission_engine.load_packs` loads this file by path and reads a module-level `PACK`.
PACK = pack()
