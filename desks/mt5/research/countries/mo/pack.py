"""MACAU: a peg on a peg, and the one unrevised monthly read on Chinese discretionary spending.

WHY MACAU EARNS A PACK OF ITS OWN AND IS NOT A ROW IN THE HONG KONG ONE. Five things belong to
this economy and to no other on the desk's book:

  1. THE DICJ PUBLISHES MONTHLY GROSS GAMING REVENUE ON THE FIRST WORKING DAY OF THE FOLLOWING
     MONTH, ON A FIXED CLOCK, AND NEVER REVISES IT. The Direccao de Inspeccao e Coordenacao de
     Jogos posts `Receitas Brutas dos Jogos de Fortuna ou Azar` around 13:00 Macau time on the
     first working day of each month, for the whole prior month, in MOP, with no revision and no
     vintage problem. Almost nothing else in public data has that shape. It is a monthly,
     zero-lag, unrevised measurement of MAINLAND CHINESE DISCRETIONARY CONSUMPTION and of
     CROSS-BORDER CAPITAL MOVEMENT at once, and between June 2014 and August 2016 it printed
     twenty-six consecutive year-on-year declines while the anti-corruption campaign and the
     UnionPay withdrawal limits ran -- which is why it was the single best-known public proxy
     for the intensity of mainland policy in those years. MO-A is that series, dated to the
     minute, against HK50, CHINAH, USDCNH and the China risk complex.

  2. THE PATACA IS A PEG ON A PEG. MOP 1.03 = HKD 1.00 at the note-issuing banks (Banco Nacional
     Ultramarino and the Bank of China Macau branch), and the Hong Kong dollar is itself held
     between the HKMA's 7.75 and 7.85 convertibility undertakings. So a Macau shock reaches the
     US dollar only THROUGH the Hong Kong band, and the band belongs to the `hk` pack, which
     owns its Aggregate Balance, its undertaking triggers and its HIBOR leg. This pack names the
     chain, computes the implied USD/MOP corridor from it (`peg_chain`), and duplicates none of
     Hong Kong's mechanics. The one thing Macau adds that Hong Kong does not have is a REAL
     HKD FLOW underneath: the casinos quote and settle in Hong Kong dollars, so DICJ's MOP
     headline is a Hong Kong dollar receipt translated at a fixed rate, and gaming demand is
     therefore a direct, countable source of HKD demand.

  3. THE REGIME BOUNDARIES ARE DATED AND THEY INVALIDATE ANY POOLED STUDY OF THE SERIES. The
     2002 end of the STDM monopoly, the 2003 Individual Visit Scheme, the 2014-16 decline, the
     2020-22 border closure, Alvin Chau's arrest on 2021-11-27 and the collapse of the junket
     licence count from 235 in 2013 to a few dozen, Law 7/2022 which banned the junket
     revenue-share model and put satellite casinos on a transition clock, and the ten-year
     concessions that began on 2023-01-01 with a non-gaming investment commitment attached.
     A GGR study that pools across those boundaries is measuring several different businesses
     and calling the average a mechanism. MO-E and POLICY_ERAS exist to stop that.

  4. A GOVERNMENT WITH NO DEBT, AN ENORMOUS FISCAL RESERVE, AND EIGHTY PER CENT OF ITS REVENUE
     FROM ONE TAX ON ONE INDUSTRY. The direct gaming tax is 35% of GGR and the contributions
     take it to about 39-40%, and that single line has been roughly four fifths of public
     revenue. The fiscal reserve the AMCM manages is larger than several years of spending and
     the SAR carries essentially no public debt. That makes Macau's public finances a PURE
     DERIVATIVE of the series in (1) -- the only fiscal position on this desk's book whose
     monthly revenue run-rate is published before the month's accounts exist.

  5. A DUAL CALENDAR THAT NO SINGLE RULE COMPUTES. Macau closes for the Chinese lunar festivals
     -- three days of Lunar New Year, Ching Ming, Tuen Ng, the day AFTER Mid-Autumn, Chung
     Yeung and the Winter Solstice -- and ALSO for the Catholic and Portuguese dates that came
     with four centuries of Portuguese administration: Good Friday, the day before Easter, All
     Souls' Day on 2 November and the Feast of the Immaculate Conception on 8 December. The
     second set is DERIVABLE (Easter is computed here) and the first set is not, so the first is
     typed from the Government Printing Bureau's gazetted table and the second is computed. SAR
     Establishment Day is 20 December. Nothing else on the desk's book has two religious
     calendars stacked on one 30-square-kilometre trading day.

WHAT IS EXECUTABLE AND WHAT IS NOT. MOP is ABSENT from `data/universe/universe.json` and is
carried in `TRANSMISSION_TARGETS` with the double-peg chain and its route through USDHKD. The
gaming operators are single names listed in Hong Kong and New York; under the two-lane order
(2026-09-06) they are EVENT LANE ONLY and appear here as ACTORS and OBSERVABLES -- never as an
executable instrument, never as a domain instrument, never as an edge target. There is no
Macau securities exchange at all: MOX (the Chongwa (Macao) Financial Asset Exchange) lists bonds
only, and the announced yuan-denominated exchange has not launched. Macau's listing venue of
record is HKEX, which is exactly why HK50 and CHINAH carry this pack's transmission.

NATIVE GROUND IS BILINGUAL AND THE PACK MEANS IT. Traditional Chinese is the working language of
the DICJ tables, the Macau Daily News and the punter forums; PORTUGUESE is co-official, the
Boletim Oficial is published in both, and the legal layer -- the gaming law, the concession
contracts, the dispatches that fix the holiday table -- is read in Portuguese or not at all. A
Chinese-only crawl of Macau reads the numbers and misses the statute that changed them.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Any

# --------------------------------------------------------------------------- identity
CODE = "MO"
NAME = "Macau"
#: THE PARITY FENCE COUNTS THIS (`scripts/check_regional_parity.py::jurisdictions_of`). Declared
#: even though the directory name would imply it, because an implied claim is not a measurement.
JURISDICTIONS: tuple[str, ...] = ("mo",)
REGION_COMMAND = "asia"
REGION_DESK = "GREATER_CHINA"
FOREST = "china"
CURRENCY = "MOP"
FISCAL_YEAR_END = "12-31"          # the SAR budget (Lei do Orcamento) runs the calendar year
NATIVE_LANGUAGES: tuple[str, ...] = ("zh-Hant", "pt", "yue", "en")
COT_CURRENCY = ""                  # no CFTC contract exists for the pataca and none ever will
EXPORT_ECONOMY = "services_exporter"            # one service, sold to one country, at the border
RETAIL_LEVERAGE_REGIME = "UNMEASURED"           # no local broker, no local margin statistics
MISSION = ("mine Macau as the first-working-day, never-revised gaming-revenue clock it is: the "
           "DICJ monthly GGR against the China risk complex, the pataca's peg on Hong Kong's "
           "peg and the HKD receipt underneath it, the visitor and border-crossing physical "
           "series, the dated junket and concession regime breaks that invalidate any pooled "
           "study, the Hengqin and Greater Bay Area integration clock, and the dual "
           "lunar-and-Catholic calendar that no single rule computes")

#: The instruments this pack may compile a cell against. Every one is in the broker registry and
#: none is a single-name equity. The pataca is absent (see TRANSMISSION_TARGETS), and the
#: US-listed and HK-listed gaming operators are EVENT LANE and appear nowhere in this tuple.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "HK50", "CHINAH",                                  # the listing venue of record
    "USDHKD", "EURHKD", "HKDJPY",                      # the middle link of the double peg
    "USDCNH", "USDJPY",                                # the mainland demand and funding legs
    "XAUUSD",                                          # the pawnshop channel and reserve asset
    "US500", "NAS100",                                 # the global risk leg the GGR print meets
)

TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "MOP (the pataca) -- USD/MOP and HKD/MOP",
     "venue": "the AMCM currency board and the two note-issuing banks (BNU, Bank of China Macau)",
     "why": "THE DOUBLE PEG, AND IT IS THE PACK'S WHOLE FX STORY: MOP 1.03 = HKD 1.00 at the "
            "note-issuing banks inside a narrow trading band, and the HKD is itself inside the "
            "HKMA's 7.75/7.85 convertibility band, so a Macau shock reaches the dollar ONLY "
            "through the Hong Kong band. The `hk` pack owns that band; this pack computes the "
            "implied USD/MOP corridor from it and routes every domestic mechanism through "
            "USDHKD rather than re-deriving Hong Kong's mechanics",
     "proxies": ("USDHKD", "EURHKD", "HKDJPY")},
    {"name": "The HKD cash the casinos actually take",
     "venue": "the casino cage and the Macau banking system's HKD deposit book",
     "why": "the DICJ headline is reported in patacas and the tables are dealt in Hong Kong "
            "dollars, so gaming demand is a countable source of HKD demand; the AMCM's monthly "
            "deposit split by currency is the observable and USDHKD is the executable leg",
     "proxies": ("USDHKD", "HK50")},
    {"name": "The Macau gaming concessionaires' equity (HKEX and NYSE listings)",
     "venue": "HKEX and the US exchanges",
     "why": "EVENT LANE ONLY under the two-lane order (2026-09-06). These are single names and "
            "may never mint a statistical hypothesis here; their index membership is what makes "
            "HK50 the carrier, and the US listings are why a Macau print lands inside the New "
            "York session as well as the Hong Kong one",
     "proxies": ("HK50", "CHINAH", "US500", "NAS100")},
    {"name": "MOX / Chongwa (Macao) Financial Asset Exchange bond listings",
     "venue": "Chongwa (Macao) Financial Asset Exchange",
     "why": "Macau's only exchange lists BONDS, mostly mainland-issuer offshore paper; no CFD "
            "exists and no price is public at a usable frequency, so the China credit leg is "
            "read through CHINAH and USDCNH instead",
     "proxies": ("CHINAH", "USDCNH")},
    {"name": "MAIBOR and the Macau interbank money market",
     "venue": "the AMCM's reference interbank rates",
     "why": "the pataca money market is small and thin and its rates track HIBOR with a spread; "
            "no instrument is quoted, so the funding leg is Hong Kong's and is named as such",
     "proxies": ("USDHKD", "HKDJPY")},
    {"name": "The Macau SAR fiscal reserve's investment portfolio",
     "venue": "AMCM (the reserve is managed, not disclosed line by line)",
     "why": "one of the largest reserve-to-GDP positions anywhere, held by a government with "
            "essentially no debt; the holdings are not published at instrument level, so the "
            "exposure is carried as a gold-and-dollar reserve hypothesis and never as a position",
     "proxies": ("XAUUSD", "USDHKD")},
)

# --------------------------------------------------------------------------- the central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "Autoridade Monetaria de Macau / 澳門金融管理局 (AMCM)",
    "short": "AMCM",
    "framework": "peg",
    "committee": "the AMCM Board of Directors; monetary policy is not a decision this authority "
                 "takes, because the currency board removes it",
    "policy_instrument": "NONE OF ITS OWN. The AMCM operates a currency board: the note-issuing "
                         "banks deposit Hong Kong dollars with the authority against every "
                         "pataca issued, at MOP 1.03 = HKD 1.00. The AMCM 'base rate' follows "
                         "the HKMA's base rate, which follows the federal funds target",
    "mandate": "maintain the external value and stability of the pataca, supervise the banking "
               "and insurance systems, and manage the exchange fund and the fiscal reserve",
    "decision_rule": "THERE IS NO SCHEDULED POLICY DECISION. The base rate changes when Hong "
                     "Kong's changes, which is when the Fed's changes; an AMCM announcement is "
                     "therefore an IMPORTED event and its date is the FOMC's date plus the Hong "
                     "Kong lag, never a domestic clock",
    "decision_calendar_rule": "DECLARED EMPTY. Copying the FOMC calendar into a Macau pack would "
                              "claim a domestic event where there is an imported one; the "
                              "generic central-bank miner reporting UNMEASURED here is the "
                              "correct answer (L1.28a), and the FOMC leg belongs to the `us` "
                              "pack and the band leg to the `hk` pack",
    "decision_dates": (),
    "dates_status": "EMPTY ON PURPOSE: Macau has no domestic monetary decision to date. The "
                    "imported clock is the FOMC's, and the transmission link is the HKMA's "
                    "base-rate formula -- both owned by other packs",
    "decision_time_utc": "",
    "announce_local": "n/a -- the AMCM publishes a base-rate notice after the HKMA moves",
    "dst_rule": "Asia/Macau is UTC+8 all year with no daylight saving; the whole local calendar "
                "is therefore a fixed 8-hour offset and never moves in UTC",
    "minutes_lag_days": 0,
    "publication_classes": ("aviso_amcm", "estatisticas_monetarias_e_financeiras",
                            "relatorio_anual", "taxa_de_cambio_de_referencia",
                            "reserva_financeira", "boletim_estatistico"),
    "policy_rate_series": "AMCM:base_rate_follows_HKMA",
    "expected_rate_series": "UNMEASURED",
    "consensus_proxy": "the HKMA base rate and HIBOR; there is no Macau rate expectation to "
                       "measure a surprise against, and the pack says so rather than inventing "
                       "one",
    "consensus_proxy_trap": "a Macau base-rate notice is NOT news -- it is the arithmetic of a "
                            "decision taken in Washington and passed through Hong Kong; an event "
                            "study on the notice date is measuring the FOMC with a lag",
    "reserves_clock": "the AMCM publishes monetary and financial statistics monthly, including "
                      "the foreign exchange reserves backing the note issue and the currency "
                      "split of bank deposits; the fiscal reserve is reported separately and "
                      "less often",
    "programme": "none; Macau has no IMF programme, no public debt of consequence and a reserve "
                 "position measured in years of spending -- the opposite of the programme "
                 "economies elsewhere in this package",
    "off_cycle": (),
    "root": "https://www.amcm.gov.mo",
}

# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "DICJ monthly gross gaming revenue publication (the pack's primary clock)",
     "local": "about 13:00 Asia/Macau on the FIRST WORKING DAY of the month, for the whole "
              "prior month",
     "time_utc": "05:00", "dst_rule": "none (Asia/Macau is UTC+8 all year)",
     "instruments": ("HK50", "CHINAH", "USDCNH"), "window_minutes": 60,
     "why": "the unrevised monthly read on mainland discretionary consumption; the release "
            "lands INSIDE the Hong Kong afternoon session, which is why HK50 is the first leg"},
    {"name": "AMCM pataca reference rate against the Hong Kong dollar",
     "local": "published each business day; the note-issuing link is fixed at MOP 1.03 = HKD 1",
     "time_utc": "01:30", "dst_rule": "none",
     "instruments": ("USDHKD", "EURHKD"), "window_minutes": 30,
     "why": "the first link of the double peg; it is an ARITHMETIC fixing, not a market one, "
            "which is why the informative coordinate is the Hong Kong band and not this rate"},
    {"name": "HKMA convertibility undertaking levels 7.7500 and 7.8500 (the second link)",
     "local": "the Hong Kong trading day, 09:00-17:00 Asia/Hong_Kong",
     "time_utc": "08:00", "dst_rule": "none",
     "instruments": ("USDHKD",), "window_minutes": 60,
     "why": "OWNED BY THE `hk` PACK. Named here because it is the only door a Macau shock can "
            "reach the dollar through; this pack reads the band position and never re-derives it"},
    {"name": "PBoC CNY central parity (the mainland demand leg)",
     "local": "09:15 Asia/Shanghai", "time_utc": "01:15", "dst_rule": "none",
     "instruments": ("USDCNH",), "window_minutes": 30,
     "why": "Macau's customer is the mainland visitor; the parity and the offshore rate are the "
            "price of the money that crosses the Gongbei gate"},
    {"name": "HKEX closing auction (the carrier's fixing)",
     "local": "16:00-16:10 Asia/Hong_Kong", "time_utc": "08:00", "dst_rule": "none",
     "instruments": ("HK50", "CHINAH"), "window_minutes": 10,
     "why": "Macau's listed exposure settles in Hong Kong; a first-working-day print is marked "
            "against this close"},
    {"name": "LBMA gold price PM auction (the pawnshop channel's dollar leg)",
     "local": "15:00 Europe/London", "time_utc": "15:00", "dst_rule": "GMT/BST",
     "instruments": ("XAUUSD",), "window_minutes": 15,
     "why": "the Macau pawnshop and jewellery counters on the Gongbei approach are a cash-out "
            "channel priced off this fix; the flow is a capital-control observable"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "DICJ monthly gaming revenue release (first working day)", "kind": "day_of_month",
     "days": (1, 2, 3, 4), "roll": "next", "window_utc": ("04:30", "06:00"),
     "instruments": ("HK50", "CHINAH", "USDCNH"),
     "why": "the release is dated to the first WORKING day, so the calendar day moves with both "
            "the lunar and the Catholic holiday tables; `first_working_day` computes it"},
    {"name": "DSEC monthly visitor arrivals and hotel occupancy", "kind": "day_of_month",
     "days": (20, 21, 22, 23, 24, 25), "roll": "next", "window_utc": ("08:00", "10:00"),
     "instruments": ("HK50", "USDCNH"),
     "why": "the physical counterpart of the gaming series, published about three weeks after "
            "the month it covers -- a lag that must be carried, never assumed away"},
    {"name": "Monthly gaming tax settlement to the SAR treasury", "kind": "month_end",
     "roll": "previous", "window_utc": ("02:00", "09:00"),
     "instruments": ("HK50", "USDHKD"),
     "why": "35% direct tax plus contributions, about four fifths of public revenue, settled "
            "monthly -- the fiscal position is a derivative of the published GGR"},
    {"name": "Concession premium and non-gaming investment milestones",
     "kind": "fiscal_year_end", "roll": "previous", "window_utc": ("02:00", "09:00"),
     "instruments": ("HK50", "CHINAH"),
     "why": "the ten-year concessions that began 2023-01-01 carry dated investment commitments "
            "reported on the SAR budget year"},
    {"name": "HKEX T+2 settlement and the quarterly index review", "kind": "quarter_end",
     "roll": "previous", "window_utc": ("06:00", "08:10"),
     "instruments": ("HK50", "CHINAH"),
     "why": "Macau's listed exposure is a Hong Kong index constituent; the review dates are when "
            "its weight actually changes"},
    {"name": "Golden Week and Lunar New Year travel blocks", "kind": "week_of_month",
     "weekday": 0, "week_of_month": 1, "roll": "next", "window_utc": ("00:00", "09:00"),
     "instruments": ("HK50", "USDCNH", "CHINAH"),
     "why": "the mainland holiday blocks are the demand calendar; the first working day of "
            "October and of the lunar year is both a travel peak AND a release date"},
)

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "NO DOMESTIC SECURITIES EXCHANGE -- MOX (Chongwa (Macao) Financial Asset Exchange)",
     "index_symbols": (),
     "open_local": "n/a", "close_local": "n/a", "open_utc": "", "close_utc": "",
     "dst_rule": "none",
     "auction": "none; MOX is a bond listing and registration venue, not a continuous market",
     "expiry_rule": "NO LISTED DERIVATIVES AND NO EQUITY TAPE. The yuan-denominated exchange "
                    "announced since 2018 has not launched, so there is no domestic expiry "
                    "clock to mine and the generic expiry miner correctly reports UNMEASURED",
     "holidays": "the SAR general-holiday calendar",
     "notes": "MACAU IS THE ONLY ECONOMY ON THIS DESK'S BOOK WITH A THIRTY-BILLION-DOLLAR "
              "INDUSTRY AND NO STOCK EXCHANGE. That is not a footnote: it is why the listed "
              "exposure lives in Hong Kong and New York, why the two-lane order bites so hard "
              "here, and why this pack's carrier is an index of another jurisdiction"},
    {"name": "HKEX as Macau's listing venue of record",
     "index_symbols": ("HK50", "CHINAH"),
     "open_local": "09:30 (pre-opening 09:00)", "close_local": "16:00",
     "open_utc": "01:30", "close_utc": "08:00", "dst_rule": "none (Asia/Hong_Kong is UTC+8)",
     "auction": "opening auction 09:00-09:30, lunch 12:00-13:00, closing auction 16:00-16:10",
     "expiry_rule": "HSI and HSCEI settle on the business day immediately preceding the last "
                    "business day of the month; the rule and its mechanics belong to the `hk` "
                    "pack and are read here, never re-derived",
     "holidays": "the Hong Kong calendar, which is NOT Macau's: Hong Kong substitutes a weekend "
                 "holiday to the next weekday and Macau's general-holiday statute does not, so "
                 "the two closed-day sets diverge in weeks that look identical on a lunar "
                 "calendar -- a first-working-day release can therefore land on a day the "
                 "carrier is shut",
     "notes": "the carrier. Every Macau mechanism that reaches equity reaches it here"},
)

SESSION_WINDOWS: tuple[dict[str, Any], ...] = (
    {"name": "mo_ggr_release", "start_utc": "04:30", "end_utc": "06:00",
     "notes": "the DICJ first-working-day publication around 13:00 Macau time; it lands in the "
              "Hong Kong AFTERNOON session, so HK50 is the first leg and US500 is the second"},
    {"name": "mo_hk_morning", "start_utc": "01:30", "end_utc": "04:00",
     "notes": "the HKEX morning session, the carrier's first window of the Macau day"},
    {"name": "mo_hk_afternoon", "start_utc": "05:00", "end_utc": "08:10",
     "notes": "the HKEX afternoon session including the closing auction; the GGR print is "
              "inside it"},
    {"name": "mo_border_morning", "start_utc": "00:00", "end_utc": "03:00",
     "notes": "the Gongbei and Qingmao checkpoint morning surge, 08:00-11:00 Macau time; the "
              "physical demand series' own hour"},
    {"name": "mo_us_gaming_overlap", "start_utc": "13:30", "end_utc": "20:00",
     "notes": "the New York session in which the US-listed operators trade. DECLARED FOR "
              "COMPLETENESS AND NEVER MINED FOR A SINGLE NAME: the two-lane order makes those "
              "listings event-lane, and the only executable legs in this window are US500 and "
              "NAS100"},
)

RELEASE_CLASSES: tuple[dict[str, Any], ...] = (
    {"name": "DICJ monthly gross gaming revenue (Receitas Brutas dos Jogos)",
     "cadence": "monthly", "time_utc": "05:00", "source": "DICJ",
     "actual_series": "DICJ:ggr_monthly", "expected_series": "UNMEASURED",
     "notes": "FIRST WORKING DAY of the following month, unrevised; the whole pack's clock"},
    {"name": "DICJ quarterly gaming revenue by segment (VIP baccarat, mass, slots)",
     "cadence": "quarterly", "time_utc": "05:00", "source": "DICJ",
     "actual_series": "DICJ:ggr_by_segment", "expected_series": "n/a",
     "notes": "the VIP/mass split is what the junket collapse actually changed; the monthly "
              "headline hides it"},
    {"name": "DSEC visitor arrivals by origin and by mode of transport",
     "cadence": "monthly", "time_utc": "08:00", "source": "DSEC",
     "actual_series": "DSEC:visitor_arrivals", "expected_series": "UNMEASURED",
     "notes": "about three weeks late; by-origin is the mainland demand read and by-transport is "
              "the bridge-versus-ferry-versus-gate physical read"},
    {"name": "DSEC hotel occupancy, average room rate and length of stay",
     "cadence": "monthly", "time_utc": "08:00", "source": "DSEC",
     "actual_series": "DSEC:hotel_occupancy", "expected_series": "n/a",
     "notes": "the non-gaming pivot's own series; the concessions' investment commitments are "
              "measured against it"},
    {"name": "DSEC consumer price index", "cadence": "monthly", "time_utc": "08:00",
     "source": "DSEC", "actual_series": "DSEC:cpi", "expected_series": "UNMEASURED",
     "notes": "imported inflation by construction: the pataca is pegged and nearly everything "
              "is imported from the mainland and Hong Kong"},
    {"name": "DSEC gross domestic product and the gaming share",
     "cadence": "quarterly", "time_utc": "08:00", "source": "DSEC",
     "actual_series": "DSEC:gdp", "expected_series": "UNMEASURED",
     "notes": "the most GGR-levered GDP anywhere; the quarterly print is the GGR months added up"},
    {"name": "AMCM monetary and financial statistics (money supply, deposits by currency, "
             "reserves backing the note issue)",
     "cadence": "monthly", "time_utc": "08:00", "source": "AMCM",
     "actual_series": "AMCM:monetary_statistics", "expected_series": "n/a",
     "notes": "THE HKD DEPOSIT SHARE IS THE PACK'S BEST MONETARY OBSERVABLE: it is where the "
              "casino cage's Hong Kong dollars show up"},
    {"name": "DSF public accounts and gaming tax receipts",
     "cadence": "monthly", "time_utc": "08:00", "source": "Direccao dos Servicos de Financas",
     "actual_series": "DSF:gaming_tax_receipts", "expected_series": "n/a",
     "notes": "the fiscal derivative of the GGR series, published on its own clock"},
    {"name": "Boletim Oficial da RAEM (the bilingual gazette)",
     "cadence": "weekly", "time_utc": "UNMEASURED", "source": "Imprensa Oficial",
     "actual_series": "BO:diplomas", "expected_series": "n/a",
     "notes": "Series I and II, Chinese and Portuguese side by side; a gaming-law amendment, a "
              "concession dispatch or the next year's holiday table becomes citable only here"},
    {"name": "Border crossing statistics (Public Security Police / DSEC)",
     "cadence": "monthly", "time_utc": "08:00", "source": "Corpo de Policia de Seguranca Publica",
     "actual_series": "PSP:border_crossings", "expected_series": "n/a",
     "notes": "by checkpoint -- Gongbei, Qingmao, Hengqin, the HZMB, the ferry terminals and the "
              "airport; the only daily-resolution physical series Macau has"},
)

# --------------------------------------------------------------------------- holidays
#: THE SOLAR HALF OF THE DUAL CALENDAR -- fixed general holidays that recur on the same date
#: every year and can therefore be computed rather than typed. Four of these are Portuguese and
#: Catholic inheritances (All Souls' on 2 November, the Immaculate Conception on 8 December,
#: Christmas Eve and Christmas Day) and three are Chinese and constitutional (the two National
#: Days and SAR Establishment Day on 20 December).
FIXED_GENERAL: tuple[tuple[int, int, str], ...] = (
    (1, 1, "元旦 / Ano Novo (New Year's Day)"),
    (5, 1, "勞動節 / Dia do Trabalhador (Labour Day)"),
    (10, 1, "中華人民共和國國慶日 / Dia Nacional da RPC (National Day, day 1)"),
    (10, 2, "國慶日翌日 / Dia Nacional da RPC (day 2)"),
    (11, 2, "追思節 / Dia de Finados (All Souls' Day)"),
    (12, 8, "聖母無原罪瞻禮 / Imaculada Conceicao (Feast of the Immaculate Conception)"),
    (12, 20, "澳門特別行政區成立紀念日 / Dia do Estabelecimento da RAEM"),
    (12, 24, "冬節前夕/聖誕前夕 / Vespera de Natal (Christmas Eve, afternoon)"),
    (12, 25, "聖誕節 / Natal (Christmas Day)"),
)

#: THE LUNAR AND SOLAR-TERM HALF -- Lunar New Year (three days), Ching Ming, the Feast of the
#: Buddha, Tuen Ng, the day AFTER Mid-Autumn, Chung Yeung and the Winter Solstice. NONE of these
#: can be produced by a weekday rule, so they are TYPED from the Government Printing Bureau's
#: gazetted general-holiday table (published in the Boletim Oficial for each year) and carry
#: their status. Typing a gazetted table is honest; inventing a rule for it is not.
#: Rows are (date, name, status).
LUNAR_GENERAL: dict[int, tuple[tuple[date, str, str], ...]] = {
    2024: ((date(2024, 2, 10), "農曆正月初一 / Ano Novo Lunar (day 1)", "GAZETTED"),
           (date(2024, 2, 11), "農曆正月初二 / Ano Novo Lunar (day 2)", "GAZETTED"),
           (date(2024, 2, 12), "農曆正月初三 / Ano Novo Lunar (day 3)", "GAZETTED"),
           (date(2024, 4, 4), "清明節 / Dia de Cheng Ming", "GAZETTED"),
           (date(2024, 5, 15), "佛誕節 / Dia do Buda (Bathing of Lord Buddha)", "GAZETTED"),
           (date(2024, 6, 10), "端午節 / Festival de Tun Ng (Dragon Boat)", "GAZETTED"),
           (date(2024, 9, 18), "中秋節翌日 / Dia seguinte ao Bolo Lunar", "GAZETTED"),
           (date(2024, 10, 11), "重陽節 / Dia de Chong Yeong", "GAZETTED"),
           (date(2024, 12, 21), "冬至 / Solsticio de Inverno", "GAZETTED")),
    2025: ((date(2025, 1, 29), "農曆正月初一 / Ano Novo Lunar (day 1)", "GAZETTED"),
           (date(2025, 1, 30), "農曆正月初二 / Ano Novo Lunar (day 2)", "GAZETTED"),
           (date(2025, 1, 31), "農曆正月初三 / Ano Novo Lunar (day 3)", "GAZETTED"),
           (date(2025, 4, 4), "清明節 / Dia de Cheng Ming", "GAZETTED"),
           (date(2025, 5, 5), "佛誕節 / Dia do Buda (Bathing of Lord Buddha)", "GAZETTED"),
           (date(2025, 5, 31), "端午節 / Festival de Tun Ng (Dragon Boat)", "GAZETTED"),
           (date(2025, 10, 7), "中秋節翌日 / Dia seguinte ao Bolo Lunar", "GAZETTED"),
           (date(2025, 10, 29), "重陽節 / Dia de Chong Yeong", "GAZETTED"),
           (date(2025, 12, 21), "冬至 / Solsticio de Inverno", "GAZETTED")),
    2026: ((date(2026, 2, 17), "農曆正月初一 / Ano Novo Lunar (day 1)", "GAZETTED"),
           (date(2026, 2, 18), "農曆正月初二 / Ano Novo Lunar (day 2)", "GAZETTED"),
           (date(2026, 2, 19), "農曆正月初三 / Ano Novo Lunar (day 3)", "GAZETTED"),
           (date(2026, 4, 5), "清明節 / Dia de Cheng Ming", "GAZETTED"),
           (date(2026, 5, 24), "佛誕節 / Dia do Buda (Bathing of Lord Buddha)", "PROJECTED"),
           (date(2026, 6, 19), "端午節 / Festival de Tun Ng (Dragon Boat)", "PROJECTED"),
           (date(2026, 9, 26), "中秋節翌日 / Dia seguinte ao Bolo Lunar", "PROJECTED"),
           (date(2026, 10, 18), "重陽節 / Dia de Chong Yeong", "PROJECTED"),
           (date(2026, 12, 22), "冬至 / Solsticio de Inverno", "PROJECTED")),
}

#: One-off closures and dated clock facts that no recurring rule produces.
DECLARED_CLOSURES: dict[date, str] = {
    date(2024, 2, 12): "Lunar New Year day 3 on a Monday -- the only lost trading session of "
                       "the 2024 block, because Macau does not substitute a weekend holiday",
    date(2025, 10, 1): "National Day day 1 inside the mainland Golden Week travel block, which "
                       "is also the month in which the first-working-day release is pushed out",
}

#: THE STATUS LABELS the holiday table may carry. GAZETTED means the Government Printing Bureau's
#: published general-holiday table for that year; PROJECTED means the pack computed the lunar
#: date and the Bureau's table has not been read for it. A projected row may be a day off and a
#: cell compiled on one is a hypothesis, never a promotion.
HOLIDAY_STATUSES: tuple[str, ...] = ("GAZETTED", "PROJECTED")


def easter(year: int) -> date:
    """Gregorian Easter Sunday, by the anonymous Gregorian computus.

    THE CATHOLIC HALF OF MACAU'S CALENDAR IS DERIVABLE AND IS THEREFORE DERIVED. Good Friday and
    the day before Easter are general holidays in the SAR by inheritance from four centuries of
    Portuguese administration, and typing them where a rule exists would be the failure the
    depth rule names.
    """
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    m = (32 + 2 * e + 2 * i - h - k) % 7
    n = (a + 11 * h + 22 * m) // 451
    month, day = divmod(h + m - 7 * n + 114, 31)
    return date(year, month, day + 1)


def catholic_movable(year: int) -> dict[date, str]:
    """The two movable Catholic general holidays Macau closes for: Good Friday and the day
    before Easter Sunday. Computed from `easter`, never typed."""
    sunday = easter(year)
    return {
        sunday - timedelta(days=2): "耶穌受難日 / Sexta-feira Santa (Good Friday)",
        sunday - timedelta(days=1): "復活節前日 / Vespera da Pascoa (the day before Easter)",
    }


def national_holidays(year: int) -> dict[date, str]:
    """Macau's general holidays for a year: the fixed solar dates, the computed Catholic dates,
    the gazetted lunar dates and the one-off declarations.

    NO WEEKEND SUBSTITUTION. Macau's general-holiday statute carries no automatic move of a
    Sunday holiday to the following weekday of the Hong Kong kind, so a holiday at the weekend
    costs no session and is simply lost -- which is exactly why the Macau and Hong Kong closed
    sets diverge in weeks that look identical on a lunar calendar.
    """
    out: dict[str, str] = {}
    for m, d, name in FIXED_GENERAL:
        out[date(year, m, d).isoformat()] = name
    for day, name in catholic_movable(year).items():
        out[day.isoformat()] = name
    for day, name, status in LUNAR_GENERAL.get(year, ()):
        out[day.isoformat()] = f"{name} [{status}]"
    for day, name in DECLARED_CLOSURES.items():
        if day.year == year:
            out[day.isoformat()] = name
    return {date.fromisoformat(k): v for k, v in sorted(out.items())}


def market_holidays(year: int) -> dict[date, str]:
    """The closed days that cost a WEEKDAY. A Saturday or Sunday closure costs no session and
    must not enter a holiday-liquidity sample as if it did."""
    return {d: n for d, n in national_holidays(year).items() if d.weekday() < 5}


def is_market_holiday(day: date) -> bool:
    return day in market_holidays(day.year)


def gazetted_dates(year: int) -> dict[date, str]:
    """Only the lunar rows the Government Printing Bureau's table actually carries. A study that
    pools PROJECTED rows into a gazetted sample must say so."""
    return {d: n for d, n, st in LUNAR_GENERAL.get(year, ()) if st == "GAZETTED"}


def first_working_day(year: int, month: int) -> date:
    """THE DICJ CLOCK. The first day of a month that is neither a weekend nor a Macau general
    holiday -- the day the monthly gross gaming revenue is published, around 13:00 local.

    This is the pack's single most load-bearing function. The release date is NOT the first of
    the month: January opens on a general holiday, October opens on two, and a Lunar New Year
    that lands at the start of February pushes the print out by days. A study that stamps the
    print to the 1st is stamping a third of its events to a day the number did not exist.
    """
    day = date(year, month, 1)
    closed = market_holidays(year)
    while day.weekday() >= 5 or day in closed:
        day += timedelta(days=1)
    return day


def ggr_release_days(year: int) -> list[date]:
    """Every DICJ publication day in a Gregorian year: twelve dates, each the first working day
    of its month, each carrying the PRIOR month's revenue."""
    return [first_working_day(year, m) for m in range(1, 13)]


#: THE DOUBLE PEG, AS ARITHMETIC. The note-issuing banks hold the pataca at MOP 1.03 per Hong
#: Kong dollar; the AMCM permits a narrow trading band around it. The Hong Kong dollar is itself
#: held between the HKMA's two convertibility undertakings.
MOP_PER_HKD = 1.03
MOP_BAND_PCT = 0.01               # the AMCM's permitted deviation around the 1.03 link
HKD_BAND: tuple[float, float] = (7.7500, 7.8500)


def peg_chain(usdhkd: float) -> dict[str, float]:
    """THE PEG ON A PEG, COMPUTED. Given USD/HKD, the implied USD/MOP and the corridor the
    double peg bounds it inside.

    `band_position` is 0.0 at the strong-side undertaking (7.7500, where the HKMA sells Hong
    Kong dollars) and 1.0 at the weak side (7.8500, where it buys them). That coordinate is the
    informative one: the chain's arithmetic makes USD/MOP a deterministic function of a price
    with two reflecting barriers, so Macau's external value has no independent variance of its
    own and every "Macau FX" cell is really a Hong Kong band cell wearing a Macau hat.
    """
    lo, hi = HKD_BAND
    pos = (float(usdhkd) - lo) / (hi - lo)
    return {
        "usdhkd": float(usdhkd),
        "usdmop": float(usdhkd) * MOP_PER_HKD,
        "usdmop_strong": lo * MOP_PER_HKD,
        "usdmop_weak": hi * MOP_PER_HKD,
        "mop_per_hkd": MOP_PER_HKD,
        "mop_band_low": MOP_PER_HKD * (1.0 - MOP_BAND_PCT),
        "mop_band_high": MOP_PER_HKD * (1.0 + MOP_BAND_PCT),
        "band_position": pos,
        "distance_to_weak_pct": (hi - float(usdhkd)) / hi * 100.0,
        "distance_to_strong_pct": (float(usdhkd) - lo) / lo * 100.0,
    }


HOLIDAYS_RULE: dict[str, Any] = {
    "kind": "computed_solar_plus_computed_easter_plus_gazetted_lunar_table",
    "authority": "the general holidays are fixed by the SAR's Labour Relations Law and published "
                 "each year by the Government Printing Bureau (Imprensa Oficial) in the Boletim "
                 "Oficial; the lunar rows come from that gazetted table, the Catholic rows are "
                 "computed from Easter and the fixed solar rows are computed from the statute",
    "rule": "THREE GENERATORS, NOT ONE, BECAUSE MACAU KEEPS TWO RELIGIOUS CALENDARS AT ONCE. "
            "(1) NINE FIXED SOLAR DAYS computed from the statute: 1 Jan, 1 May, 1 and 2 Oct "
            "(National Day), 2 Nov (All Souls'), 8 Dec (Immaculate Conception), 20 Dec (Macau "
            "SAR Establishment Day), 24 Dec (Christmas Eve, afternoon) and 25 Dec. (2) TWO "
            "MOVABLE CATHOLIC DAYS computed from Easter by `catholic_movable(year)`: Good "
            "Friday and the day before Easter Sunday -- derivable, therefore derived. (3) NINE "
            "LUNAR AND SOLAR-TERM DAYS that no weekday rule produces and that are TYPED from "
            "the Government Printing Bureau's gazetted table with their status: Lunar New Year "
            "days 1-3, Ching Ming, the Feast of the Buddha, Tuen Ng, the day AFTER Mid-Autumn, "
            "Chung Yeung and the Winter Solstice. NO WEEKEND SUBSTITUTION: Macau does not move "
            "a weekend holiday to the next weekday the way Hong Kong does, so the day is lost "
            "and the two SARs' closed sets diverge. THE CLOCK NEVER MOVES: Asia/Macau is UTC+8 "
            "all year with no daylight saving.",
    "years": (2024, 2025, 2026),
    "weekend": "Saturday and Sunday",
    "national_rule": "see `rule`; `national_holidays(year)` is the computed form",
    "market_rule": "the general calendar on weekdays; there is no domestic securities session to "
                   "close, so the calendar's market meaning is the FIRST-WORKING-DAY release "
                   "clock and the border-crossing peak, not an exchange session",
    "lunar_rule": "GAZETTED, not inferred: the Government Printing Bureau publishes the next "
                  "year's general holidays in the Boletim Oficial, and a PROJECTED row in this "
                  "table is the pack's own lunar computation awaiting that gazette",
    "catholic_rule": "computed from Easter; Good Friday and the day before Easter Sunday",
    "dual_calendar": "the distinguishing calendar fact of this jurisdiction: a Catholic movable "
                     "feast and a Chinese lunar festival close the same small economy in the "
                     "same quarter, and a study that models only one of them mislabels the other",
    "table": {y: {d.isoformat(): n for d, n in national_holidays(y).items()}
              for y in (2024, 2025, 2026)},
    "status": {2024: "GAZETTED for every row", 2025: "GAZETTED for every row",
               2026: "GAZETTED for the fixed, Catholic and Lunar New Year rows; PROJECTED for "
                     "the Feast of the Buddha, Tuen Ng, Mid-Autumn, Chung Yeung and the Winter "
                     "Solstice until the Bureau's table is read"},
    "known_dates": {
        "2024-02-10": "Lunar New Year day 1 on a Saturday -- two of the three days cost no "
                      "session, and Macau does not substitute them",
        "2025-01-29": "Lunar New Year day 1 on a Wednesday: the whole block is trading days lost",
        "2025-04-18": "Good Friday, computed from Easter 2025-04-20",
        "2025-12-20": "SAR Establishment Day, a fixed solar date certain in every year",
        "2026-04-03": "Good Friday, computed from Easter 2026-04-05",
    },
    "fn": market_holidays,
    "national_fn": national_holidays,
    "gazetted_fn": gazetted_dates,
    "release_fn": first_working_day,
}

# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "AMCM monthly deposits by currency (the MOP / HKD / CNY split)",
     "root": "https://www.amcm.gov.mo/pt/publications-statistics/statistics",
     "fields": ("deposits_mop", "deposits_hkd", "deposits_cny", "deposits_usd",
                "non_resident_deposits"),
     "frequency": "monthly", "snapshot": "month end", "publish_utc": "08:00", "lag_days": 45,
     "licence": "free, public", "available": True,
     "why": "THE CLOSEST THING MACAU HAS TO A POSITIONING SERIES. The casino cage takes Hong "
            "Kong dollars and the banking system carries them, so the HKD share of deposits is "
            "where gaming demand becomes a monetary fact; the non-resident line is the "
            "cross-border half",
     "pit_warning": "about six weeks late and month-end stamped; it can condition a quarter, "
                    "never a week"},
    {"name": "DICJ junket promoter and gaming-intermediary licence register",
     "root": "https://www.dicj.gov.mo/web/cn/information/DadosEstat_mensal/index.html",
     "fields": ("licensed_promoters", "satellite_casinos", "gaming_tables", "slot_machines"),
     "frequency": "annual (register) with monthly table and machine counts",
     "snapshot": "1 January for the register", "publish_utc": "05:00", "lag_days": 5,
     "licence": "free, public", "available": True,
     "why": "the count fell from 235 promoters in 2013 to a few dozen after the 2021-22 "
            "prosecutions and Law 7/2022; it is the cleanest single measure of the VIP channel's "
            "capacity and it dates the regime break MO-E is about",
     "pit_warning": "a REGISTER, not a flow: a licence that still exists is not a promoter that "
                    "still operates, and the pack says so rather than treating the count as "
                    "volume"},
    {"name": "DSEC visitor arrivals by place of origin and mode of transport",
     "root": "https://www.dsec.gov.mo/zh-MO/Statistic?id=401",
     "fields": ("arrivals_mainland", "arrivals_hong_kong", "arrivals_taiwan",
                "arrivals_overnight_share", "by_checkpoint", "by_transport_mode"),
     "frequency": "monthly", "snapshot": "calendar month", "publish_utc": "08:00",
     "lag_days": 22, "licence": "free, public", "available": True,
     "why": "the physical demand series behind the revenue series; the by-origin split "
            "separates a mainland policy shock from a regional one and the by-transport split "
            "separates the bridge from the gate from the ferry",
     "pit_warning": "three weeks late, so it NEVER conditions the same month's GGR print; it is "
                    "a confirmation series and treating it as a leading one is a look-ahead"},
    {"name": "a CFTC, exchange or dealer positioning series for the pataca",
     "root": "", "fields": (), "frequency": "n/a", "snapshot": "", "publish_utc": "",
     "lag_days": 0, "licence": "", "available": False,
     "why": "DECLARED ABSENT: no pataca future, forward or option trades on any exchange the "
            "desk can read, and no COT contract exists for MOP anywhere",
     "pit_warning": "DOES NOT EXIST: pataca positioning is UNMEASURED and is never proxied by "
                    "the HKD or CNH legs, which are positions in the currencies the pataca is "
                    "pegged THROUGH and not in the pataca"},
    {"name": "a domestic equity or derivatives positioning series",
     "root": "", "fields": (), "frequency": "n/a", "snapshot": "", "publish_utc": "",
     "lag_days": 0, "licence": "", "available": False,
     "why": "DECLARED ABSENT: Macau has no securities exchange, no local brokerage industry and "
            "no margin statistics. MOX lists bonds and publishes no tape",
     "pit_warning": "DOES NOT EXIST: there is no Macau order book, no short-interest series and "
                    "no retail margin series to condition on, and the Hong Kong ones belong to "
                    "the `hk` pack and measure Hong Kong"},
)

# --------------------------------------------------------------------------- terminology
#: TWO OFFICIAL LANGUAGES AND THE PACK MEANS BOTH. Traditional Chinese is the working language
#: of the DICJ tables, the Macau Daily News and the punter forums. PORTUGUESE is co-official:
#: the Boletim Oficial is bilingual, the gaming law, the concession contracts and the dispatches
#: that fix the holiday table are read in Portuguese, and the whole Lusophone press corps in
#: Macau writes in it. A Chinese-only crawl of Macau reads the numbers and misses the statute
#: that changed them; a Portuguese-only crawl misses the demand side entirely.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "gaming_revenue": ("博彩毛收入", "幸運博彩毛收入", "賭收", "博彩收入統計", "月度博彩收入",
                       "同比變化", "中場博彩", "貴賓廳博彩", "角子機",
                       "receitas brutas dos jogos", "jogos de fortuna ou azar",
                       "receita bruta mensal", "jogo VIP", "jogo de massas"),
    "regulator": ("博彩監察協調局", "博監局", "博彩委員會", "批給", "承批公司", "衛星場",
                  "中介人", "博彩中介人牌照",
                  "Direccao de Inspeccao e Coordenacao de Jogos", "DICJ", "concessao",
                  "concessionaria", "promotor de jogo", "casino satelite"),
    "monetary": ("澳門金融管理局", "金管局", "澳門元", "聯繫匯率", "發鈔銀行", "貨幣發行",
                 "外匯儲備", "基本利率", "存款貨幣結構",
                 "Autoridade Monetaria de Macau", "AMCM", "pataca", "taxa de cambio fixa",
                 "bancos emissores", "reservas cambiais", "taxa de juro base"),
    "peg_chain": ("港元掛鈎", "一點零三", "雙重掛鈎", "兌換保證", "強方兌換保證",
                  "弱方兌換保證", "香港金融管理局",
                  "ligacao ao dolar de Hong Kong", "duplo cambio fixo", "banda de conversao"),
    "fiscal": ("博彩稅", "直接稅", "財政儲備", "基本儲備", "超額儲備", "財政局", "預算案",
               "特區政府收入", "現金分享",
               "imposto especial sobre o jogo", "reserva financeira", "reserva basica",
               "Direccao dos Servicos de Financas", "orcamento", "comparticipacao pecuniaria"),
    "visitors": ("入境旅客", "旅客來源地", "內地旅客", "自由行", "個人遊", "留宿旅客",
                 "不過夜旅客", "旅客平均逗留時間", "酒店入住率", "平均房價",
                 "visitantes", "entradas de visitantes", "turismo", "taxa de ocupacao hoteleira",
                 "visitantes do interior da China"),
    "border": ("關閘", "青茂口岸", "橫琴口岸", "港珠澳大橋", "出入境人次", "通關", "口岸",
               "噴射飛航", "外港客運碼頭", "澳門國際機場",
               "posto fronteirico das Portas do Cerco", "Ponte Hong Kong-Zhuhai-Macau",
               "travessia fronteirica", "Terminal Maritimo do Porto Exterior"),
    "junket": ("貴賓廳", "疊碼仔", "博彩中介人", "泥碼", "轉碼數", "太陽城", "非法兌換",
               "地下錢莊", "跨境賭資",
               "salas VIP", "promotores de jogo", "fichas mortas", "branqueamento de capitais",
               "casas de cambio ilegais"),
    "law_and_gazette": ("澳門特別行政區公報", "印務局", "法律", "行政長官批示", "第7/2022號法律",
                        "第16/2001號法律", "立法會", "博彩法",
                        "Boletim Oficial da RAEM", "Imprensa Oficial", "despacho do Chefe do "
                        "Executivo", "Assembleia Legislativa", "lei do jogo", "Lei 7/2022"),
    "integration": ("粵港澳大灣區", "橫琴粵澳深度合作區", "琴澳一體化", "一國兩制",
                    "澳門經濟適度多元", "中葡平台", "合作區管委會",
                    "Grande Baia", "Zona de Cooperacao Aprofundada em Hengqin",
                    "diversificacao economica", "plataforma China-paises lusofonos"),
    "statistics": ("統計暨普查局", "本地生產總值", "消費物價指數", "就業調查", "外地僱員",
                   "藍卡", "最低工資", "人均GDP",
                   "Direccao dos Servicos de Estatistica e Censos", "DSEC",
                   "produto interno bruto", "indice de precos no consumidor",
                   "trabalhadores nao residentes"),
    "calendar": ("公眾假期", "農曆新年", "清明節", "端午節", "中秋節翌日", "重陽節", "冬至",
                 "追思節", "聖母無原罪瞻禮", "耶穌受難日", "澳門特別行政區成立紀念日",
                 "feriados obrigatorios", "Ano Novo Lunar", "Dia de Finados",
                 "Imaculada Conceicao", "Sexta-feira Santa", "Solsticio de Inverno"),
    "physical_economy": ("輕軌", "澳電", "供水", "珠海供水", "酒店房間數", "非博彩投資",
                         "會展業", "零售銷售額", "典當業", "金舖",
                         "transportes publicos", "Companhia de Electricidade de Macau",
                         "investimento nao-jogo", "casas de penhores", "ourivesarias"),
    "capital_controls": ("銀聯", "提款上限", "跨境資金", "數字人民幣", "外匯管制", "反洗錢",
                         "可疑交易報告", "澳門通", "資金外流",
                         "UnionPay", "limites de levantamento", "fluxos transfronteiricos",
                         "yuan digital", "controlo cambial", "combate ao branqueamento"),
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

#: Han (Traditional Chinese) so a test can assert this pack did not become an English glossary,
#: and a declared Portuguese marker list so it cannot quietly become a Chinese-only one either.
_HAN_RANGES = ((0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF), (0x20000, 0x2A6DF))
#: Portuguese working vocabulary the pack must carry: the gazette, the gaming law, the regulator,
#: the currency board and the holiday statute are all read in it or not at all.
PORTUGUESE_MARKERS: tuple[str, ...] = (
    "receitas brutas dos jogos", "jogos de fortuna ou azar", "concessao", "concessionaria",
    "promotor de jogo", "Boletim Oficial da RAEM", "Imprensa Oficial", "pataca",
    "Autoridade Monetaria de Macau", "reserva financeira", "imposto especial sobre o jogo",
    "visitantes", "Zona de Cooperacao Aprofundada em Hengqin", "feriados obrigatorios",
    "Sexta-feira Santa", "Imaculada Conceicao", "salas VIP", "Direccao de Inspeccao e "
    "Coordenacao de Jogos")


def has_han(text: str) -> bool:
    """True when the text contains at least one Han codepoint (Traditional Chinese here)."""
    return any(any(lo <= ord(ch) <= hi for lo, hi in _HAN_RANGES) for ch in str(text))


def han_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    rows = TERMINOLOGY if terminology is None else terminology
    return [t for terms in rows.values() for t in terms if has_han(t)]


def portuguese_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    """Every declared Portuguese marker actually present in the terminology table."""
    rows = TERMINOLOGY if terminology is None else terminology
    flat = {t for terms in rows.values() for t in terms}
    return [m for m in PORTUGUESE_MARKERS if any(m in t for t in flat)]


def term_count(terminology: Mapping[str, Iterable[str]] | None = None) -> int:
    rows = TERMINOLOGY if terminology is None else terminology
    return len({t for terms in rows.values() for t in terms})


def _seq(values: Iterable[Any]) -> tuple[str, ...]:
    return tuple(str(v) for v in values)


def source_class(sid: str, label: str, *, layer: str, roots: Iterable[str],
                 queries: Iterable[str], languages: Iterable[str], access_label: str,
                 credibility: str, predictive_state: str, licence: str,
                 machine_use_allowed: bool = True, notes: str = "") -> dict[str, Any]:
    """One class of source with the roots a crawler starts from and its three INDEPENDENT
    labels. `queries` are native-script terms, never translations. `machine_use_allowed=False`
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
        "mo_dicj", "DICJ (Direccao de Inspeccao e Coordenacao de Jogos): monthly and quarterly "
                   "gross gaming revenue, table and machine counts, the promoter register, the "
                   "concession dispatches", layer="official",
        roots=("https://www.dicj.gov.mo/web/cn/information/DadosEstat_mensal/index.html",
               "https://www.dicj.gov.mo/web/cn/information/DadosEstat/index.html",
               "https://www.dicj.gov.mo/web/pt/information/DadosEstat_mensal/index.html",
               "https://www.dicj.gov.mo"),
        queries=("幸運博彩毛收入", "博彩毛收入統計", "每月博彩收入", "博彩中介人名單",
                 "賭枱數目", "角子機數目", "receitas brutas dos jogos de fortuna ou azar",
                 "estatisticas mensais DICJ", "lista de promotores de jogo",
                 "numero de mesas de jogo"),
        languages=("zh-Hant", "pt", "en"), access_label="OPEN_DATA",
        credibility="AUTHORITATIVE", predictive_state="UNTESTED", licence="free, public",
        notes="THE PACK'S PRIMARY CLOCK. The monthly table is posted on the FIRST WORKING DAY "
              "of the following month around 13:00 local, in patacas, and is never revised. The "
              "page OVERWRITES the current-year table in place, so the only point-in-time "
              "vintage of a given month's first print is a crawl taken that day or the archive "
              "layer's snapshot"),
    source_class(
        "mo_dsec", "DSEC (Direccao dos Servicos de Estatistica e Censos): visitor arrivals by "
                   "origin and transport, hotel occupancy and ADR, CPI, GDP, employment, "
                   "non-resident workers, external trade", layer="official",
        roots=("https://www.dsec.gov.mo/zh-MO/", "https://www.dsec.gov.mo/pt-PT/",
               "https://www.dsec.gov.mo/zh-MO/Statistic?id=401",
               "https://www.dsec.gov.mo/zh-MO/Statistic?id=101"),
        queries=("入境旅客統計", "旅客來源地", "酒店入住率", "消費物價指數", "本地生產總值",
                 "外地僱員統計", "對外商品貿易",
                 "entradas de visitantes", "taxa de ocupacao hoteleira",
                 "indice de precos no consumidor", "produto interno bruto de Macau"),
        languages=("zh-Hant", "pt", "en"), access_label="OPEN_DATA",
        credibility="AUTHORITATIVE", predictive_state="UNTESTED", licence="free, public",
        notes="the physical counterpart of the revenue series, and the one that separates a "
              "mainland policy shock from a regional one; published about three weeks after the "
              "month it covers, so it never conditions the same month's GGR print"),
    source_class(
        "mo_amcm", "AMCM (Autoridade Monetaria de Macau): monetary and financial statistics, "
                   "deposits by currency, the note issue and its Hong Kong dollar backing, the "
                   "base rate notices, the fiscal reserve, banking supervision",
        layer="official",
        roots=("https://www.amcm.gov.mo/zh-hant/", "https://www.amcm.gov.mo/pt/",
               "https://www.amcm.gov.mo/pt/publications-statistics/statistics",
               "https://www.amcm.gov.mo/pt/about-amcm/financial-reserve"),
        queries=("貨幣及金融統計", "存款貨幣結構", "澳門元發行", "基本利率", "財政儲備",
                 "外匯儲備資產", "金融管理局年報",
                 "estatisticas monetarias e financeiras", "reserva financeira",
                 "taxa de juro base", "emissao de patacas", "reservas cambiais"),
        languages=("zh-Hant", "pt", "en"), access_label="OPEN_DATA",
        credibility="AUTHORITATIVE", predictive_state="UNTESTED", licence="free, public",
        notes="the currency board's own books. The HKD SHARE OF DEPOSITS is the pack's best "
              "monetary observable because it is where the casino cage's Hong Kong dollars "
              "surface; the base-rate notices are imported events and are labelled as such"),
    source_class(
        "mo_boletim_oficial", "Imprensa Oficial: the Boletim Oficial da RAEM (Series I and II), "
                              "bilingual, carrying the gaming law and its amendments, the "
                              "concession dispatches, the annual general-holiday table and every "
                              "Chief Executive dispatch", layer="official",
        roots=("https://bo.io.gov.mo/", "https://www.io.gov.mo/",
               "https://bo.io.gov.mo/bo/i/", "https://bo.io.gov.mo/bo/ii/"),
        queries=("澳門特別行政區公報", "第7/2022號法律", "第16/2001號法律", "行政長官批示",
                 "公眾假期表", "批給合同",
                 "Boletim Oficial da RAEM", "Lei 7/2022 alteracao a lei do jogo",
                 "despacho do Chefe do Executivo", "contrato de concessao",
                 "mapa dos feriados obrigatorios"),
        languages=("pt", "zh-Hant"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE LEGAL LAYER, AND IT IS READ IN PORTUGUESE. A Chinese-only crawl of Macau gets "
              "the numbers and misses the statute that changed them: the 2022 gaming-law "
              "amendment, the six concession contracts and the gazetted holiday table are all "
              "citable only here, side by side in both languages"),
    source_class(
        "mo_dsf_government", "DSF (Direccao dos Servicos de Financas) and the SAR government "
                             "portal: the budget, monthly public accounts, gaming tax receipts, "
                             "the Policy Address and the cash-handout scheme", layer="official",
        roots=("https://www.dsf.gov.mo/", "https://www.gov.mo/zh-hant/",
               "https://www.gov.mo/pt/", "https://www.policyaddress.gov.mo/"),
        queries=("財政局預算執行", "博彩稅收入", "財政年度預算案", "施政報告", "現金分享計劃",
                 "公共收支", "execucao orcamental", "imposto especial sobre o jogo",
                 "linhas de accao governativa", "comparticipacao pecuniaria"),
        languages=("zh-Hant", "pt"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the fiscal derivative of the GGR series: one tax on one industry is about four "
              "fifths of public revenue, so the monthly accounts are the gaming series arriving "
              "a second time through the treasury"),
    source_class(
        "mo_hkma_customs", "The transmission ground OUTSIDE Macau that the chain runs through: "
                           "the HKMA's convertibility undertakings and Aggregate Balance, and "
                           "China's customs and SAFE data on Guangdong and the Greater Bay Area",
        layer="official",
        roots=("https://www.hkma.gov.hk/eng/", "http://www.customs.gov.cn/",
               "https://www.safe.gov.cn/"),
        queries=("兌換保證", "總結餘", "香港金融管理局", "海關總署進出口", "國家外匯管理局",
                 "跨境資金流動", "Aggregate Balance convertibility undertaking",
                 "粵港澳大灣區貿易數據"),
        languages=("zh-Hant", "zh", "en"), access_label="OPEN_DATA",
        credibility="AUTHORITATIVE", predictive_state="UNTESTED", licence="free, public",
        notes="REGISTERED HERE AND OWNED ELSEWHERE. The 7.75/7.85 band belongs to the `hk` pack "
              "and the mainland capital account to `cn`; this row exists so the Macau miners "
              "read them rather than re-deriving them, which is the whole point of naming the "
              "double peg instead of duplicating it"),
    # ---- institutional
    source_class(
        "mo_mox_banks", "Chongwa (Macao) Financial Asset Exchange (MOX), Banco Nacional "
                        "Ultramarino, the Bank of China Macau branch and the Macau Association "
                        "of Banks: bond listings, the note issue, the annual reports",
        layer="institutional",
        roots=("https://www.mox.mo/", "https://www.bnu.com.mo/", "https://www.bocmacau.com/",
               "https://www.amcm.gov.mo/pt/supervision/banking"),
        queries=("中華(澳門)金融資產交易股份有限公司", "債券上市", "大西洋銀行", "中國銀行澳門分行",
                 "發鈔銀行年報", "澳門銀行公會",
                 "Banco Nacional Ultramarino relatorio anual", "listagem de obrigacoes MOX",
                 "bancos emissores de patacas"),
        languages=("zh-Hant", "pt", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public (issuer and supervisory disclosure)",
        notes="MACAU'S ONLY EXCHANGE LISTS BONDS. MOX publishes listing documents, not a tape, "
              "so there is no price series to mine here -- the row is kept because the note "
              "issuers' balance sheets are where the currency board's Hong Kong dollar backing "
              "is actually visible"),
    source_class(
        "mo_industry_bodies", "The gaming and tourism trade bodies and the chambers: the Macau "
                              "Gaming Information Association, the Macau Chamber of Commerce, "
                              "the hotel and travel agency associations, the labour unions of "
                              "the casino floor", layer="institutional",
        roots=("https://www.acm.org.mo/", "https://www.macauchamber.org.mo/",
               "https://www.macautourism.gov.mo/"),
        queries=("澳門中華總商會", "博彩企業員工", "旅遊業議會", "酒店業協會", "荷官",
                 "博彩從業員權益", "associacao comercial de Macau",
                 "associacao de agencias de viagens", "trabalhadores dos casinos"),
        languages=("zh-Hant", "pt"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the dealer unions and the travel-agency body publish dated positions before a "
              "concession or labour-importation decision lands in the gazette, which makes them "
              "the cheapest leading indicator of a MO-K regime move"),
    source_class(
        "mo_operator_disclosure", "The concessionaires' own regulated disclosure as an "
                                  "OBSERVABLE: HKEX and SEC filings, quarterly results, "
                                  "non-gaming investment progress reports", layer="institutional",
        roots=("https://www.hkexnews.hk/", "https://www.sec.gov/cgi-bin/browse-edgar"),
        queries=("澳門博彩承批公司業績", "非博彩投資承諾", "貴賓廳業務", "中場收入",
                 "resultados das concessionarias", "investimento nao-jogo",
                 "relatorio trimestral concessionaria"),
        languages=("zh-Hant", "en", "pt"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public (regulated disclosure)",
        notes="EVENT LANE ONLY AND THE PACK IS STRICT ABOUT IT (two-lane order, 2026-09-06). "
              "These are single names and may never mint a statistical hypothesis here. They "
              "are registered because their filings carry the VIP/mass split and the investment "
              "milestones at a resolution the DICJ headline does not"),
    # ---- academic
    source_class(
        "mo_universities", "University of Macau, Macao Polytechnic University's gaming and "
                           "tourism research centre, the Macao Institute for Tourism Studies and "
                           "the City University of Macau: gaming demand, tourism elasticity and "
                           "the currency board literature", layer="academic",
        roots=("https://www.um.edu.mo/", "https://www.mpu.edu.mo/",
               "https://www.iftm.edu.mo/", "https://library.um.edu.mo/"),
        queries=("澳門博彩業研究", "博彩收入影響因素", "旅客消費行為", "澳門經濟適度多元研究",
                 "聯繫匯率制度研究", "estudos sobre o jogo em Macau",
                 "procura turistica de Macau", "diversificacao economica estudo"),
        languages=("zh-Hant", "pt", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="open access / publisher terms",
        notes="Macau is one of the few economies whose principal industry has a dedicated local "
              "research literature; the demand-elasticity papers written in Taipa are the "
              "mechanism source for MO-C, and every one is a hypothesis until reproduced"),
    source_class(
        "mo_academic_index", "The international literature and the open indexes: OpenAlex, CORE, "
                             "CNKI, the UNLV Center for Gaming Research, and the Hong Kong and "
                             "mainland working-paper series on Macau", layer="academic",
        roots=("https://openalex.org/", "https://core.ac.uk/", "https://www.cnki.net/",
               "https://gaming.library.unlv.edu/"),
        queries=("澳門博彩收入 反腐", "澳門 資本外流 研究", "Macau gaming revenue anti-corruption",
                 "Macau VIP baccarat junket literature", "pataca currency board",
                 "estudo economico de Macau"),
        languages=("zh", "zh-Hant", "en", "pt"), access_label="OPEN_DATA",
        credibility="RELIABLE", predictive_state="UNTESTED", licence="index terms; open access",
        notes="the 2014-16 anti-corruption literature is where the GGR-as-policy-proxy claim was "
              "first made; it is registered as a HYPOTHESIS the desk must re-measure on its own "
              "data and never as a settled result"),
    # ---- practitioner
    source_class(
        "mo_gaming_trade_press", "The gaming trade desk press: GGRAsia, Inside Asian Gaming, "
                                 "Asia Gaming Brief and Macau Business -- the analysts' channel "
                                 "checks, the monthly run-rate estimates and the sell-side "
                                 "previews", layer="practitioner",
        roots=("https://www.ggrasia.com/", "https://www.asgam.com/",
               "https://agbrief.com/", "https://www.macaubusiness.com/"),
        queries=("澳門博彩收入預測", "月中博彩數據", "分析員預測", "賭收按年",
                 "previsao das receitas de jogo", "estimativa mensal do jogo",
                 "GGR run rate forecast Macau", "analista receitas brutas"),
        languages=("en", "zh-Hant", "pt"), access_label="PUBLIC_WITH_TERMS",
        credibility="RELIABLE", predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="THIS IS MACAU'S CONSENSUS TAPE AND THERE IS NO OTHER. The sell-side publishes a "
              "mid-month run-rate estimate before the DICJ print, which is the only stated "
              "expectation a surprise can be measured against; it is kept as the EXPECTATION "
              "source MO-A measures against, never as a view the desk adopts"),
    source_class(
        "mo_hk_sellside", "Hong Kong and mainland sell-side gaming coverage published openly: "
                          "the brokers' Macau monthlies, the Greater Bay Area strategy notes and "
                          "the China consumer desks", layer="practitioner",
        roots=("https://www.aastocks.com/tc/", "https://www.hkexnews.hk/",
               "https://www.ggrasia.com/category/analysis/"),
        queries=("澳門賭收預測", "博彩股評級", "中場復甦", "大灣區消費", "券商研報 澳門",
                 "analise do sector do jogo", "perspectivas do mercado de Macau"),
        languages=("zh-Hant", "zh", "en"), access_label="PUBLIC_WITH_TERMS",
        credibility="RELIABLE", predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="the Hong Kong desks are where a Macau number becomes an index-level view; the "
              "row is kept for the DATED expectation and the single names in it are event lane"),
    # ---- retail ecology
    source_class(
        "mo_punter_forums", "The punter and visitor communities: the Macau and Hong Kong "
                            "discussion boards, LIHKG's Macau threads, Baidu Tieba's 澳門吧, "
                            "the Xiaohongshu and Douyin travel and border-queue posts",
        layer="retail_ecology",
        roots=("https://lihkg.com/", "https://tieba.baidu.com/f?kw=%E6%BE%B3%E9%97%A8",
               "https://www.xiaohongshu.com/search_result?keyword=%E6%BE%B3%E9%96%80"),
        queries=("關閘排隊", "澳門自由行攻略", "賭場 中場 最低下注", "澳門酒店房價",
                 "過關人多嗎", "澳門 匯率 兌換", "橫琴口岸 通關時間"),
        languages=("zh-Hant", "zh", "yue"), access_label="PUBLIC_SOCIAL", credibility="FRINGE",
        predictive_state="UNTESTED", licence="platform terms; public posts only",
        notes="KEPT AT LOW WEIGHT AND NEVER A SOURCE OF EDGE, but this is a genuine DEMAND "
              "observable: queue complaints at the Gongbei and Qingmao gates and room-rate "
              "chatter lead the DSEC arrivals series by weeks. THE SECURITIES HALF OF THIS "
              "LAYER DOES NOT EXIST IN MACAU -- no exchange, no local broker, no margin "
              "statistics -- and that absence is recorded in ACCESS_CONSTRAINTS rather than "
              "dressed up as coverage"),
    source_class(
        "mo_cash_channel_chatter", "Public commentary on the cash-out channels: the pawnshop and "
                                   "jewellery counters on the Gongbei approach, the UnionPay "
                                   "withdrawal limits and the informal exchange trade",
        layer="retail_ecology",
        roots=("https://www.macaubusiness.com/?s=pawnshop",
               "https://www.exmoo.com/", "https://lihkg.com/"),
        queries=("澳門典當", "金舖 刷卡", "銀聯提款限額", "換錢 澳門", "地下錢莊",
                 "casas de penhores Macau", "limites de levantamento UnionPay"),
        languages=("zh-Hant", "yue", "pt"), access_label="PUBLIC_SOCIAL",
        credibility="UNRELIABLE", predictive_state="UNTESTED",
        licence="platform and publisher terms; public posts only",
        notes="PUBLIC COMMENTARY ONLY. The pawnshop-and-jewellery card channel is the documented "
              "route by which a mainland visitor's card limit becomes chips, so the chatter is "
              "a capital-control stress observable; it is carried at low weight beside the AMCM "
              "deposit split and never promoted on its own"),
    # ---- app ecosystem
    source_class(
        "mo_payment_rails", "The payment and identity rails: MPay / Macau Pass, BOC Macau Pay, "
                            "the SAR's one-account public services app, the e-CNY pilot in "
                            "Macau, UnionPay and the Hengqin cross-border wallets",
        layer="app_ecosystem",
        roots=("https://www.macaupass.com/", "https://www.bocmacau.com/",
               "https://www.gov.mo/zh-hant/services/", "https://www.amcm.gov.mo/zh-hant/"),
        queries=("澳門通", "聚易用", "一戶通", "數字人民幣試點", "跨境支付", "電子支付統計",
                 "carteira electronica Macau", "pagamentos transfronteiricos"),
        languages=("zh-Hant", "pt", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free statistics; app stores public",
        notes="the AMCM publishes electronic-payment volumes and the government publishes the "
              "e-CNY pilot's scope; together they are the one app-layer series that reads "
              "directly on how mainland money legally crosses the gate"),
    source_class(
        "mo_border_apps", "The border and transport apps: the Macau customs and immigration "
                          "waiting-time services, the HZMB shuttle and ferry booking apps, the "
                          "Light Rapid Transit and the airport's own schedule feeds",
        layer="app_ecosystem",
        roots=("https://www.gov.mo/zh-hant/services/ps-1049/",
               "https://www.hzmbus.com/", "https://www.macau-airport.com/",
               "https://www.mlm.com.mo/"),
        queries=("口岸人流", "通關輪候時間", "港珠澳大橋穿梭巴士", "輕軌時刻表", "機場航班",
                 "tempo de espera nas fronteiras", "autocarro da ponte HZMB"),
        languages=("zh-Hant", "pt", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the checkpoint waiting-time service is the highest-frequency public series this "
              "jurisdiction has -- minutes, not months -- and it is the only way to see a "
              "demand shock before the DSEC arrivals table admits it"),
    # ---- media
    source_class(
        "mo_chinese_press", "The Chinese-language press and broadcast: Macau Daily News "
                            "(澳門日報), Exmoo (力報), Macao Daily's economy desk and TDM's "
                            "Chinese channels", layer="media",
        roots=("https://www.macaodaily.com/", "https://www.exmoo.com/",
               "https://www.tdm.com.mo/zh-hant/"),
        queries=("澳門日報 經濟", "力報 博彩", "賭收公布", "特區政府表示", "博監局公布",
                 "旅客人次創新高", "通關新安排"),
        languages=("zh-Hant", "yue"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="Macau Daily News is the paper of record for the Chinese-reading half of the "
              "economy and carries the DICJ figure within the hour, usually before the trade "
              "press translates it"),
    source_class(
        "mo_lusophone_press", "The Portuguese-language press: Jornal Tribuna de Macau, Ponto "
                              "Final, Hoje Macau, Macau Daily Times and TDM Radio Macau",
        layer="media",
        roots=("https://jtm.com.mo/", "https://pontofinalmacau.wordpress.com/",
               "https://hojemacau.com.mo/", "https://www.macaudailytimes.com.mo/"),
        queries=("receitas do jogo", "concessionarias de jogo", "Assembleia Legislativa Macau",
                 "reserva financeira de Macau", "Zona de Cooperacao de Hengqin",
                 "Governo da RAEM anuncia", "lei do jogo alteracao"),
        languages=("pt", "en"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="THE LUSOPHONE PRESS IS NOT A TRANSLATION OF THE CHINESE ONE. It covers the legal "
              "and institutional layer -- the Assembly, the concession contracts, the "
              "Portuguese-language legal debate -- that the Chinese business pages treat as "
              "settled, which is why a Chinese-only crawl of Macau systematically under-reads "
              "the statute risk in MO-E"),
    source_class(
        "mo_licensed_terminals", "Licensed terminals and paywalled sector data: Bloomberg and "
                                 "Refinitiv, the subscription tiers of the gaming trade press, "
                                 "and the hotel benchmarking services that sell Macau occupancy "
                                 "and average-rate panels", layer="media",
        roots=("https://www.bloomberg.com/", "https://www.lseg.com/en/data-analytics"),
        queries=("Macau GGR consensus estimate terminal", "Macau hotel RevPAR benchmark panel",
                 "gaming sector subscription research Macau",
                 "estimativas de consenso receitas de jogo"),
        languages=("en",), access_label="LICENSED", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="subscription; terms forbid machine extraction",
        machine_use_allowed=False,
        notes="REGISTERED, NEVER SCRAPED. The only true CONSENSUS number for a Macau monthly "
              "print lives on a terminal, and the hotel benchmarking panels are the only "
              "cross-property occupancy series. Both are paywalled, so MO-A's surprise is "
              "measured against the FREE mid-month run-rate estimates the trade press "
              "publishes and the absence is named rather than worked around"),
    # ---- archive
    source_class(
        "mo_archive_official", "The deep official archive: the Boletim Oficial full run back to "
                              "the nineteenth century, the Macau Memory digital archive, the "
                              "DSEC statistical yearbooks and the AMCM annual reports",
        layer="archive",
        roots=("https://bo.io.gov.mo/", "https://www.macaumemory.mo/",
               "https://www.dsec.gov.mo/zh-MO/Statistic?id=601",
               "https://www.library.gov.mo/"),
        queries=("澳門特別行政區公報 歷年", "統計年鑑", "澳門記憶", "澳門中央圖書館",
                 "arquivo do Boletim Oficial", "anuario estatistico de Macau",
                 "Memoria de Macau", "relatorio anual AMCM"),
        languages=("pt", "zh-Hant"), access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the only place a concession contract, a gazetted holiday table or a repealed "
              "gaming-law article becomes citable at a date; Macau Memory also carries the "
              "monopoly-era record that dates the 2002 liberalisation boundary"),
    source_class(
        "mo_wayback", "web.archive.org snapshots of the DICJ monthly revenue table, the DSEC "
                      "arrivals pages and the checkpoint statistics, all of which overwrite in "
                      "place", layer="archive",
        roots=("https://web.archive.org/web/*/dicj.gov.mo*",
               "https://web.archive.org/web/*/dsec.gov.mo*",
               "https://web.archive.org/web/*/amcm.gov.mo*"),
        queries=("dicj 博彩毛收入 存檔", "dsec 入境旅客 存檔", "DICJ monthly revenue archive",
                 "arquivo estatisticas DICJ"),
        languages=("zh-Hant", "pt", "en"), access_label="PUBLIC_ARCHIVE",
        credibility="RELIABLE", predictive_state="UNTESTED", licence="Internet Archive terms",
        notes="THE MACAU OFFICIAL WEB OVERWRITES IN PLACE. The DICJ current-year table shows the "
              "year to date and keeps no first-print vintage, so without this layer the "
              "as-published value of a given month is unrecoverable and every MO-A cell is "
              "NOT_PIT_SAFE by construction"),
    # ---- physical economy
    source_class(
        "mo_border_infrastructure", "The border and transport plane: the Public Security Police "
                                    "checkpoint statistics, the Hong Kong-Zhuhai-Macau Bridge "
                                    "traffic, the Qingmao and Hengqin ports, the ferry terminals "
                                    "and Macau International Airport", layer="physical_economy",
        roots=("https://www.fsm.gov.mo/psp/", "https://www.hzmb.gov.hk/en/",
               "https://www.macau-airport.com/", "https://www.dsec.gov.mo/zh-MO/Statistic?id=401"),
        queries=("出入境人次統計", "關閘口岸", "青茂口岸", "橫琴口岸 客流", "港珠澳大橋車流",
                 "澳門機場客運量", "外港客運碼頭",
                 "estatisticas de travessias fronteiricas", "trafego da ponte HZMB"),
        languages=("zh-Hant", "pt", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE PHYSICAL ECONOMY OF A 30-SQUARE-KILOMETRE CITY IS ITS GATES. Six checkpoints "
              "carry everything, they are counted daily, and the bridge's 2018-10-24 opening and "
              "Qingmao's 2021-09-08 opening are dated capacity changes that a pooled arrivals "
              "study will read as demand"),
    source_class(
        "mo_utilities_supply", "The supply plane: CEM electricity (imported from the mainland "
                              "grid), the Zhuhai water supply, the hotel room inventory, the "
                              "Light Rapid Transit and the retail and pawnshop footprint",
        layer="physical_economy",
        roots=("https://www.cem-macau.com/", "https://www.macaowater.com/",
               "https://www.dsec.gov.mo/zh-MO/Statistic?id=501",
               "https://www.mlm.com.mo/"),
        queries=("澳電 售電量", "珠海供水", "酒店房間供應", "輕軌乘客量", "零售業銷售額",
                 "典當業數目", "consumo de electricidade Macau",
                 "fornecimento de agua de Zhuhai", "numero de quartos de hotel"),
        languages=("zh-Hant", "pt"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="Macau imports essentially all of its power and water from Guangdong, which makes "
              "the utilities plane a literal measure of how integrated the economy already is; "
              "the hotel room count is the capacity constraint the non-gaming pivot is "
              "measured against"),
    # ---- source graph
    source_class(
        "mo_source_graph", "Who cites whom: DICJ -> GGRAsia and Inside Asian Gaming -> the Hong "
                           "Kong sell-side -> 澳門日報 and the mainland wires -> Xiaohongshu and "
                           "Weibo; the Boletim Oficial -> the Lusophone press -> the Chinese "
                           "business pages", layer="source_graph",
        roots=("https://www.ggrasia.com/", "https://www.macaodaily.com/", "https://jtm.com.mo/",
               "https://bo.io.gov.mo/"),
        queries=("據博監局數據", "消息人士稱", "有分析員指", "據了解", "引述政府消息",
                 "segundo fontes", "de acordo com o Boletim Oficial",
                 "segundo dados da DICJ"),
        languages=("zh-Hant", "pt", "en"), access_label="PUBLIC", credibility="UNKNOWN",
        predictive_state="UNTESTED", licence="derived from the public sources above",
        notes="'消息人士稱' and 'segundo fontes' mark the unattributed leak that precedes a "
              "concession dispatch or a border-policy change by a day or two here; the graph is "
              "how a leak is told from a repost, and it is also how the desk sees a mid-month "
              "run-rate estimate propagate from one house into the whole tape"),
)

#: DECLARED EMPTY AND MEASURED, NOT ASSUMED. All ten layers carry a real, named root for Macau.
#: The honest absences in this jurisdiction are INSTRUMENT- and SERIES-level, not layer-level --
#: no pataca contract anywhere, no securities exchange, no order book, no margin statistics --
#: and each is recorded in `ACCESS_CONSTRAINTS` and in `POSITIONING_SOURCES` with
#: `available=False`. Declaring a layer absent while a real ground exists would be padding in
#: reverse and would read as a measurement it is not.
LAYER_ABSENCES: dict[str, str] = {}

#: NATIVE QUERY TERRITORIES: what the deep-forest miner actually runs, per layer, in Traditional
#: Chinese and Portuguese. Three or more per layer for every layer that is not declared absent.
QUERY_TERRITORIES: dict[str, tuple[str, ...]] = {
    "official": ("幸運博彩毛收入 按月", "博彩監察協調局 統計", "入境旅客 按來源地",
                 "澳門金融管理局 貨幣統計", "財政儲備 報告",
                 "receitas brutas dos jogos mensais", "estatisticas de visitantes DSEC",
                 "Boletim Oficial lei do jogo"),
    "institutional": ("大西洋銀行 年報", "中國銀行澳門分行 發鈔", "澳門中華總商會 聲明",
                      "承批公司 非博彩投資", "MOX 債券上市",
                      "relatorio anual do BNU", "associacao comercial de Macau comunicado"),
    "academic": ("澳門博彩業 需求彈性 研究", "澳門 聯繫匯率 論文", "博彩收入 反腐 實證",
                 "澳門經濟多元 研究", "estudos economicos sobre Macau",
                 "procura turistica Macau elasticidade"),
    "practitioner": ("澳門賭收 月中預測", "分析員 賭收預測", "中場收入 復甦 預測",
                     "券商 澳門博彩 研報", "previsao receitas de jogo",
                     "estimativa mensal GGR Macau"),
    "retail_ecology": ("關閘 排隊 人多", "澳門 自由行 攻略", "賭場 中場 最低投注",
                       "橫琴口岸 通關時間", "澳門酒店 房價 貴",
                       "filas nas Portas do Cerco"),
    "app_ecosystem": ("澳門通 支付", "一戶通 服務", "數字人民幣 澳門 試點", "跨境支付 澳門",
                      "口岸 輪候時間 查詢", "carteira MPay pagamentos",
                      "yuan digital piloto Macau"),
    "media": ("澳門日報 博彩收入", "力報 賭收", "TDM 經濟新聞", "特區政府 公布",
              "Jornal Tribuna de Macau jogo", "Ponto Final concessoes",
              "Hoje Macau reserva financeira"),
    "archive": ("澳門特別行政區公報 歷年 存檔", "統計年鑑 澳門", "澳門記憶 檔案",
                "博彩毛收入 歷史數據", "arquivo do Boletim Oficial",
                "anuario estatistico de Macau"),
    "physical_economy": ("出入境人次 統計 口岸", "港珠澳大橋 車流量", "青茂口岸 客流",
                         "澳門機場 客運量", "澳電 售電量",
                         "trafego da ponte Hong Kong-Zhuhai-Macau",
                         "estatisticas de travessias por posto fronteirico"),
    "source_graph": ("據博監局數據", "引述政府消息", "有分析員指", "消息人士稱 博彩",
                     "segundo fontes do Governo", "de acordo com dados da DICJ"),
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
    for layer, extra in QUERY_TERRITORIES.items():
        if layer not in out:
            continue
        for q in extra:
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
            "query_territories": {k: len(v) for k, v in QUERY_TERRITORIES.items()},
            "rule": "ten layers, each carrying a source or named ABSENT with a reason; fringe "
                    "and contradicted PUBLIC material is kept as a low-weight evidence object "
                    "and never dropped; a page whose terms forbid machine extraction is "
                    "registered machine_use_allowed=false, never scraped and never omitted"}

# --------------------------------------------------------------------------- datasets
DATASETS: tuple[dict[str, Any], ...] = (
    {"name": "DICJ monthly gross gaming revenue (the first-working-day print)",
     "source": "DICJ", "coverage": "2002 onward, monthly, in MOP",
     "frequency": "monthly", "publication_lag_days": 0.0,
     "revisions": "NEVER REVISED -- the first print is the final number",
     "licence": "free, public", "history_from": "2002-01", "pit_feasible": True,
     "assets": ("HK50", "CHINAH", "USDCNH", "US500"),
     "mechanism_families": ("release_surprise", "event_reaction", "policy_proxy"),
     "how_to_fetch": "dicj.gov.mo/web/cn/information/DadosEstat_mensal/index.html -- the "
                     "current-year table is HTML and OVERWRITES IN PLACE, so a daily crawl or "
                     "the Wayback snapshot is the only way to hold the first print's vintage"},
    {"name": "DICJ quarterly gaming revenue by segment (VIP baccarat, mass baccarat, slots)",
     "source": "DICJ", "coverage": "2002 onward, quarterly", "frequency": "quarterly",
     "publication_lag_days": 20.0, "revisions": "rarely restated with the annual accounts",
     "licence": "free, public", "history_from": "2002-Q1", "pit_feasible": True,
     "assets": ("HK50", "CHINAH"),
     "mechanism_families": ("regime_break", "composition_shift"),
     "how_to_fetch": "dicj.gov.mo DadosEstat quarterly tables; the VIP share is the series the "
                     "junket collapse actually moved and the monthly headline hides"},
    {"name": "DICJ gaming table, machine and promoter counts",
     "source": "DICJ", "coverage": "2004 onward; the promoter register annually",
     "frequency": "quarterly (tables/machines), annual (promoters)",
     "publication_lag_days": 20.0, "revisions": "never", "licence": "free, public",
     "history_from": "2004-Q1", "pit_feasible": True,
     "assets": ("HK50", "CHINAH"),
     "mechanism_families": ("capacity", "regime_break"),
     "how_to_fetch": "dicj.gov.mo DadosEstat and the annual promoter list; the collapse from "
                     "235 promoters in 2013 to a few dozen is the cleanest date stamp on MO-E"},
    {"name": "DSEC visitor arrivals by place of origin",
     "source": "DSEC", "coverage": "1998 onward, monthly", "frequency": "monthly",
     "publication_lag_days": 22.0, "revisions": "occasionally revised one month later",
     "licence": "free, public", "history_from": "1998-01", "pit_feasible": True,
     "assets": ("HK50", "USDCNH", "CHINAH"),
     "mechanism_families": ("physical_flow", "seasonality"),
     "how_to_fetch": "dsec.gov.mo/zh-MO/Statistic?id=401 -- the time-series database exports "
                     "CSV and XLS; take the by-origin split, not the headline"},
    {"name": "DSEC visitor arrivals by mode of transport and by checkpoint",
     "source": "DSEC and the Public Security Police", "coverage": "2003 onward, monthly",
     "frequency": "monthly", "publication_lag_days": 22.0, "revisions": "rare",
     "licence": "free, public", "history_from": "2003-01", "pit_feasible": True,
     "assets": ("HK50", "USDCNH"),
     "mechanism_families": ("physical_flow", "capacity"),
     "how_to_fetch": "dsec.gov.mo arrivals tables plus the PSP checkpoint statistics; the "
                     "2018-10-24 bridge opening and the 2021-09-08 Qingmao opening are capacity "
                     "steps that must be modelled or they read as demand"},
    {"name": "DSEC hotel occupancy rate, average daily rate and length of stay",
     "source": "DSEC", "coverage": "2004 onward, monthly", "frequency": "monthly",
     "publication_lag_days": 25.0, "revisions": "rare", "licence": "free, public",
     "history_from": "2004-01", "pit_feasible": True,
     "assets": ("HK50", "CHINAH"),
     "mechanism_families": ("capacity", "non_gaming_pivot"),
     "how_to_fetch": "dsec.gov.mo tourism statistics; the room inventory series beside it is "
                     "the denominator the concessions' investment commitments are measured on"},
    {"name": "AMCM monetary and financial statistics: deposits by currency and the note issue",
     "source": "AMCM", "coverage": "1999 onward, monthly", "frequency": "monthly",
     "publication_lag_days": 45.0, "revisions": "revised with the annual report",
     "licence": "free, public", "history_from": "1999-12", "pit_feasible": True,
     "assets": ("USDHKD", "EURHKD", "HKDJPY"),
     "mechanism_families": ("monetary_aggregate", "cross_border_flow"),
     "how_to_fetch": "amcm.gov.mo publications-statistics; take the deposits-by-currency table "
                     "-- the HKD share is where the casino cage becomes a monetary fact"},
    {"name": "AMCM fiscal reserve: basic reserve, excess reserve and the return",
     "source": "AMCM", "coverage": "2012 onward (the reserve was constituted in 2012)",
     "frequency": "monthly headline, annual detail", "publication_lag_days": 45.0,
     "revisions": "annual audit restatement", "licence": "free, public",
     "history_from": "2012-01", "pit_feasible": True,
     "assets": ("XAUUSD", "USDHKD", "US500"),
     "mechanism_families": ("sovereign_balance_sheet",),
     "how_to_fetch": "amcm.gov.mo financial-reserve page and the annual report; the instrument "
                     "detail is NOT published, so the exposure is a hypothesis and never a "
                     "position"},
    {"name": "DSF monthly public accounts and gaming tax receipts",
     "source": "Direccao dos Servicos de Financas", "coverage": "2000 onward, monthly",
     "frequency": "monthly", "publication_lag_days": 30.0,
     "revisions": "restated in the annual accounts", "licence": "free, public",
     "history_from": "2000-01", "pit_feasible": True,
     "assets": ("HK50", "USDHKD"),
     "mechanism_families": ("fiscal_flow", "release_surprise"),
     "how_to_fetch": "dsf.gov.mo budget-execution reports; the gaming tax line is about four "
                     "fifths of revenue, so this is the GGR series arriving a second time"},
    {"name": "DSEC consumer price index and the imported-inflation split",
     "source": "DSEC", "coverage": "1998 onward, monthly", "frequency": "monthly",
     "publication_lag_days": 20.0, "revisions": "rebased periodically",
     "licence": "free, public", "history_from": "1998-01", "pit_feasible": True,
     "assets": ("USDCNH", "USDHKD"),
     "mechanism_families": ("imported_inflation",),
     "how_to_fetch": "dsec.gov.mo price statistics; with a pegged currency and near-total "
                     "import dependence this series is the mainland's and Hong Kong's inflation "
                     "arriving with a lag, which is a transfer test, not a domestic one"},
    {"name": "DSEC gross domestic product, the gaming share and the non-resident workforce",
     "source": "DSEC", "coverage": "1999 onward, quarterly", "frequency": "quarterly",
     "publication_lag_days": 60.0, "revisions": "two rounds of revision",
     "licence": "free, public", "history_from": "1999-Q1", "pit_feasible": True,
     "assets": ("HK50", "CHINAH"),
     "mechanism_families": ("macro_state",),
     "how_to_fetch": "dsec.gov.mo national accounts; the non-resident worker count (the blue "
                     "card series) is the labour-supply constraint the capacity domains need"},
    {"name": "Boletim Oficial da RAEM: the gaming law, the concession dispatches and the "
             "gazetted general-holiday table",
     "source": "Imprensa Oficial",
     "coverage": "the full run; Law 16/2001 and Law 7/2022 and every concession dispatch",
     "frequency": "weekly and irregular", "publication_lag_days": 0.0, "revisions": "never",
     "licence": "free, public", "history_from": "2001-08", "pit_feasible": True,
     "assets": ("HK50", "CHINAH"),
     "mechanism_families": ("regime_break", "administered_event"),
     "how_to_fetch": "bo.io.gov.mo Series I (laws and dispatches) and Series II; search in "
                     "PORTUGUESE as well as Chinese -- the Portuguese text is the legal one and "
                     "the searchable one for the older run"},
    {"name": "HZMB (Hong Kong-Zhuhai-Macau Bridge) traffic and shuttle passenger counts",
     "source": "HZMB Authority, Hong Kong Transport Department, Macau DSEC",
     "coverage": "2018-10-24 onward, daily and monthly", "frequency": "monthly (daily peaks "
                 "published in press releases)",
     "publication_lag_days": 15.0, "revisions": "never", "licence": "free, public",
     "history_from": "2018-10", "pit_feasible": True,
     "assets": ("HK50", "USDCNH"),
     "mechanism_families": ("physical_flow", "capacity"),
     "how_to_fetch": "hzmb.gov.hk traffic statistics and the Macau DSEC arrivals-by-checkpoint "
                     "table; the northbound/southbound split is the Greater Bay Area "
                     "integration series nobody triangulates"},
    {"name": "Checkpoint border-crossing statistics by gate",
     "source": "Corpo de Policia de Seguranca Publica / DSEC",
     "coverage": "2005 onward; Qingmao from 2021-09-08, the Hengqin port from 2020-08-18",
     "frequency": "monthly (real-time waiting times published continuously)",
     "publication_lag_days": 20.0, "revisions": "never", "licence": "free, public",
     "history_from": "2005-01", "pit_feasible": True,
     "assets": ("HK50", "USDCNH", "CHINAH"),
     "mechanism_families": ("physical_flow", "high_frequency_proxy"),
     "how_to_fetch": "the PSP statistics pages plus the government's live waiting-time service; "
                     "the live feed is the highest-frequency public Macau series that exists"},
    {"name": "The mid-month gross gaming revenue run-rate estimates (the only consensus)",
     "source": "GGRAsia, Inside Asian Gaming, Asia Gaming Brief and the Hong Kong sell-side",
     "coverage": "roughly 2011 onward, monthly", "frequency": "monthly",
     "publication_lag_days": 0.0, "revisions": "superseded rather than revised",
     "licence": "publisher terms", "history_from": "2011-01", "pit_feasible": False,
     "assets": ("HK50", "CHINAH"),
     "mechanism_families": ("expectation", "release_surprise"),
     "how_to_fetch": "ggrasia.com and asgam.com mid-month analyst notes; NOT PIT-SAFE because "
                     "the pages are edited in place and no vintage is kept, which is why an "
                     "MO-A surprise built on it is a hypothesis until the archive layer backs it"},
    {"name": "The junket, concession and gaming-law event table",
     "source": "Boletim Oficial, DICJ registers and the court record",
     "coverage": "2002 liberalisation to the 2023-01-01 concessions",
     "frequency": "irregular, dated", "publication_lag_days": 0.0, "revisions": "never",
     "licence": "free, public", "history_from": "2002-02", "pit_feasible": True,
     "assets": ("HK50", "CHINAH", "USDCNH"),
     "mechanism_families": ("regime_break", "administered_event"),
     "how_to_fetch": "assemble from bo.io.gov.mo dispatches and the DICJ register; the dates "
                     "are in POLICY_ERAS and each one invalidates a pooled GGR study"},
    {"name": "AMCM electronic payment and cross-border wallet statistics",
     "source": "AMCM", "coverage": "2016 onward, quarterly", "frequency": "quarterly",
     "publication_lag_days": 60.0, "revisions": "rare", "licence": "free, public",
     "history_from": "2016-Q1", "pit_feasible": True,
     "assets": ("USDCNH", "USDHKD"),
     "mechanism_families": ("cross_border_flow", "capital_controls"),
     "how_to_fetch": "amcm.gov.mo payment statistics; read beside the mainland's UnionPay "
                     "withdrawal-limit announcements, which are the binding constraint"},
    {"name": "CEM electricity sales and the Zhuhai water supply volumes",
     "source": "Companhia de Electricidade de Macau, Macao Water",
     "coverage": "2005 onward, monthly and annual", "frequency": "monthly",
     "publication_lag_days": 40.0, "revisions": "rare", "licence": "free, public",
     "history_from": "2005-01", "pit_feasible": True,
     "assets": ("HK50", "USDCNH"),
     "mechanism_families": ("physical_flow", "integration"),
     "how_to_fetch": "cem-macau.com and macaowater.com annual and interim reports; casino floor "
                     "load is a large share of the total, so the series is an independent "
                     "physical read on whether the properties are actually full"},
)
# --------------------------------------------------------------------------- actors
ACTORS: tuple[dict[str, Any], ...] = (
    {"name": "The DICJ as the publisher of the monthly revenue clock",
     "holds": "the only count of what every casino in the territory took last month, and the "
              "register of concessions, promoters, tables and machines",
     "forced_to": ("publish gross gaming revenue on the FIRST WORKING DAY of the following "
                   "month, for the whole month, in patacas",
                   "never revise it -- the first print is the final number",
                   "maintain and publish the promoter and satellite-casino registers"),
     "when": "about 13:00 Asia/Macau on the first working day, which is 05:00 UTC and inside "
             "the Hong Kong afternoon session",
     "information": ("every property's daily drop and win before anyone else sees it",
                     "the concession compliance file",
                     "the promoter register's live state",
                     "the table and machine allocations it itself grants"),
     "constraints": ("a statutory publication date it does not choose",
                     "a single aggregate: no property-level breakdown is published monthly",
                     "the segment split is QUARTERLY, so the monthly number mixes a collapsing "
                     "VIP channel with a growing mass one and says nothing about which moved"),
     "instruments": ("HK50", "CHINAH", "USDCNH"),
     "counterparties": ("the six concessionaires", "the SAR treasury, which taxes the number",
                        "the Hong Kong and US listed-equity market that trades it"),
     "observables": ("the monthly table", "the quarterly segment split",
                     "the table, machine and promoter counts",
                     "the timestamp of the page's own update"),
     "impact": "the single largest scheduled information event this jurisdiction produces; it "
               "reprices the Hong Kong gaming complex within minutes and reaches HK50 through "
               "index membership",
     "persistence": "the level information persists a month by construction -- there is no "
                    "intra-month official update at all",
     "falsifier": "the same 05:00-06:00 UTC window on the first working day of months in which "
                  "no release fell there, and the matched-weekday control on HK50; an effect "
                  "that survives both is a first-working-day effect and not a DICJ effect",
     "notes": "TWELVE EVENTS A YEAR, and that is the binding constraint on MO-A; it is stated "
              "rather than worked around by pooling eras that are not exchangeable"},
    {"name": "The AMCM as a currency board with no monetary policy",
     "holds": "the pataca's issue, the Hong Kong dollar backing behind every note, the banking "
              "supervision file and the management of the fiscal reserve",
     "forced_to": ("hold MOP 1.03 against HKD 1.00 at the note-issuing banks",
                   "publish monetary and financial statistics monthly",
                   "follow the HKMA's base rate, which follows the federal funds target"),
     "when": "monthly statistics about six weeks after the month end; base-rate notices within "
             "hours of a Hong Kong move",
     "information": ("the banking system's currency composition before it is published",
                     "the note issue and its backing in real time",
                     "the fiscal reserve's actual holdings, which are never disclosed"),
     "constraints": ("A CURRENCY BOARD REMOVES THE DECISION: there is no domestic rate to set "
                     "and no exchange rate to defend that Hong Kong is not already defending",
                     "the pataca's external value is Hong Kong's problem one link up",
                     "a banking system whose largest deposit currency is not its own"),
     "instruments": ("USDHKD", "EURHKD", "HKDJPY"),
     "counterparties": ("Banco Nacional Ultramarino and the Bank of China Macau branch as note "
                        "issuers", "the HKMA one link up", "the SAR treasury"),
     "observables": ("the monthly deposits-by-currency table",
                     "the note issue and its HKD backing",
                     "the base-rate notices", "the fiscal reserve headline"),
     "impact": "no direct market impact at all, and saying so is the point: an AMCM notice is "
               "arithmetic on a decision taken in Washington and passed through Hong Kong",
     "persistence": "the peg has held since 1977 in its modern form; the regime is the longest "
                    "lived object in this pack",
     "falsifier": "an event study on AMCM base-rate notice dates shows nothing beyond what the "
                  "FOMC and HKMA dates already carry -- which is the EXPECTED result, and a "
                  "finding here would mean the notice leaked something Hong Kong's did not",
     "notes": "the pack's null actor: it exists to stop a miner inventing a domestic policy "
              "event where there is an imported one (L1.28a)"},
    {"name": "The six gaming concessionaires as a block",
     "holds": "every table and machine in the territory under ten-year concessions running "
              "2023-01-01 to 2032-12-31, with dated non-gaming investment commitments attached",
     "forced_to": ("report to the DICJ daily and be aggregated into the monthly print",
                   "meet the non-gaming investment milestones written into the concessions",
                   "hold a Macau-resident shareholding floor and an approved management structure "
                   "under Law 7/2022",
                   "settle with the treasury monthly at 35% plus contributions"),
     "when": "continuously; the reporting surfaces monthly through the DICJ and quarterly "
             "through their own listed disclosure",
     "information": ("their own daily drop, hold and credit book",
                     "the mass-versus-VIP mix weeks before the quarterly split is published",
                     "the junket relationships they may no longer share revenue with"),
     "constraints": ("a fixed table and machine allocation granted by the government",
                     "the ban on the junket revenue-share model since Law 7/2022",
                     "a hotel room inventory that caps peak weekends",
                     "a non-resident workforce that requires government quota"),
     "instruments": ("HK50", "CHINAH"),
     "counterparties": ("the mainland visitor", "the promoters that remain",
                        "the SAR treasury", "their Hong Kong and US listed shareholders"),
     "observables": ("the DICJ aggregate", "the quarterly segment split",
                     "their own regulated filings", "the hotel occupancy and ADR series"),
     "impact": "they ARE the economy's cash flow; the executable consequence is index-level "
               "through HK50 and CHINAH, never single-name",
     "persistence": "a concession term is ten years; the current one runs to 2032-12-31",
     "falsifier": "index-level HK50 moves around a Macau print are explained by the Hong Kong "
                  "market's own beta to the same session's mainland news, measured with a "
                  "matched-session control",
     "notes": "EVENT LANE ONLY AS INDIVIDUAL NAMES (two-lane order 2026-09-06). They enter as a "
              "BLOCK because the block is what the DICJ aggregates and what the index carries"},
    {"name": "The junket promoters and the VIP room operators",
     "holds": "the credit, the collection and the cross-border settlement that made the VIP "
              "channel work, and historically most of the rolling chip volume",
     "forced_to": ("operate under a licence the DICJ grants and publishes",
                   "abandon the revenue-share model banned by Law 7/2022",
                   "settle debts in a jurisdiction where gambling debt is not enforceable at "
                   "the other end of the border"),
     "when": "the collapse is DATED: the Suncity prosecution from 2021-11-27, Law 7/2022 in "
             "June 2022, and the licence count falling from 235 in 2013 to a few dozen",
     "information": ("the identity and credit of the mainland high roller",
                     "the real cross-border settlement route",
                     "the capital-control pressure before any official series shows it"),
     "constraints": ("mainland anti-corruption and capital-control enforcement",
                     "a criminal-law exposure that was demonstrated, not theorised",
                     "no revenue share, so the economics of the model are gone"),
     "instruments": ("HK50", "CHINAH", "USDCNH"),
     "counterparties": ("the concessionaires", "the mainland borrower",
                        "the informal settlement network"),
     "observables": ("the DICJ promoter register count",
                     "the VIP share of the quarterly segment split",
                     "the court record of the prosecutions",
                     "the rolling-chip disclosure in the operators' filings"),
     "impact": "the channel's destruction changed the LEVEL and the VARIANCE of the whole "
               "series; it is the single largest structural break in the data",
     "persistence": "permanent as far as the record shows: a licensed channel that lost its "
                    "economics does not come back on the same terms",
     "falsifier": "the VIP share's decline is explained by the mainland's own consumption cycle "
                  "over the same quarters rather than by the dated legal events, tested by "
                  "comparing the break dates against a mainland retail-sales control",
     "notes": "THE REASON POLICY_ERAS EXISTS. A GGR study pooled across 2019-2024 is averaging "
              "two different businesses"},
    {"name": "The mainland visitor under the Individual Visit Scheme",
     "holds": "the discretionary spending decision, and a card limit set in Beijing",
     "forced_to": ("obtain an exit endorsement whose issuance policy the mainland controls",
                   "cross at one of six physical gates with published capacity",
                   "respect UnionPay withdrawal limits and the cash declaration rules"),
     "when": "clustered in the mainland holiday blocks: Lunar New Year, the May and October "
             "Golden Weeks, and the weekend pattern of a Greater Bay Area day trip",
     "information": ("their own intent, visible only in booking and queue data",
                     "the endorsement policy as it is actually applied at the desk"),
     "constraints": ("the exit-endorsement regime", "the card and cash limits",
                     "the gate's physical throughput",
                     "the hotel room supply on a peak weekend"),
     "instruments": ("HK50", "USDCNH", "CHINAH"),
     "counterparties": ("the concessionaires", "the retail and pawnshop channel",
                        "the transport operators"),
     "observables": ("DSEC arrivals by origin and by checkpoint",
                     "the live gate waiting times", "hotel occupancy and ADR",
                     "the overnight versus same-day split"),
     "impact": "the demand side of the whole pack; a policy change in Beijing about endorsements "
               "or card limits is a Macau revenue event with no Macau announcement",
     "persistence": "the scheme has run since 2003 and its intensity has been adjusted many "
                    "times without ever being withdrawn",
     "falsifier": "arrivals explain the monthly print no better than a seasonal dummy plus the "
                  "prior month's print, tested out of sample across the era boundaries",
     "notes": "the actor whose constraint is set in another jurisdiction entirely, which is why "
              "MO-J treats the series as a read on MAINLAND policy rather than on Macau"},
    {"name": "The SAR treasury (DSF) as a single-tax government",
     "holds": "a budget about four fifths funded by one tax on one industry, and no public debt "
              "of consequence",
     "forced_to": ("publish budget execution monthly",
                   "fund the annual cash handout and the social programmes from gaming tax",
                   "draw on the fiscal reserve when the industry stops, as it did 2020-2022"),
     "when": "monthly accounts about a month after the period; the budget and the Policy "
             "Address on the SAR's calendar-year cycle",
     "information": ("the tax receipt before the accounts publish it",
                     "the concession premium and investment compliance file"),
     "constraints": ("revenue concentration with no diversification to fall back on",
                     "a statutory requirement to fund the reserve",
                     "no borrowing tradition and no sovereign curve to borrow on"),
     "instruments": ("HK50", "USDHKD"),
     "counterparties": ("the concessionaires", "the AMCM as reserve manager",
                        "the residents who receive the handout"),
     "observables": ("monthly budget execution", "the gaming tax line",
                     "the reserve balance", "the budget and the Policy Address"),
     "impact": "a fiscal position that is a pure derivative of a published monthly series -- the "
               "only one on this desk's book where the revenue run-rate is public before the "
               "accounts exist",
     "persistence": "structural; the concentration has not fallen in twenty years despite being "
                    "the stated target of every diversification policy",
     "falsifier": "the monthly tax receipt carries information beyond the DICJ print it is "
                  "computed from -- tested by regressing receipts on the published GGR and "
                  "asking whether the residual predicts anything at all",
     "notes": "the actor that makes MO-G a real domain rather than a civics lesson"},
    {"name": "The two note-issuing banks (Banco Nacional Ultramarino and Bank of China Macau)",
     "holds": "the right to issue patacas against Hong Kong dollars deposited with the AMCM, "
              "and the largest share of the territory's deposit book",
     "forced_to": ("deposit HKD with the AMCM against every pataca issued, at the fixed link",
                   "publish annual accounts under AMCM supervision",
                   "serve a deposit base that holds a large share of its money in a foreign "
                   "currency that circulates freely alongside the legal tender"),
     "when": "continuously; the balance sheets annually and the aggregate monthly through the "
             "AMCM statistics",
     "information": ("the currency composition of deposits before the AMCM aggregates it",
                     "the casino sector's own cash cycle through the cage accounts"),
     "constraints": ("a currency board arrangement they cannot vary",
                     "a parent structure that reaches Lisbon and Beijing respectively",
                     "a Hong Kong dollar liability book against pataca assets"),
     "instruments": ("USDHKD", "EURHKD"),
     "counterparties": ("the AMCM", "the concessionaires' cage accounts",
                        "the Hong Kong interbank market"),
     "observables": ("the note issue", "the AMCM deposits-by-currency table",
                     "the banks' annual reports"),
     "impact": "the mechanical link that turns gaming HKD receipts into a monetary aggregate; "
               "the executable leg is USDHKD and it is Hong Kong's band that carries it",
     "persistence": "the arrangement is decades old and is not a decision anybody re-takes",
     "falsifier": "the HKD deposit share carries no information about USDHKD's position in the "
                  "convertibility band beyond what Hong Kong's own Aggregate Balance carries",
     "notes": "BNU is a Portuguese-parented bank issuing notes in a Chinese SAR, which is the "
              "institutional shape of the whole jurisdiction in one balance sheet"},
    {"name": "The Hong Kong Monetary Authority as the next link of the chain",
     "holds": "the 7.7500 and 7.8500 convertibility undertakings and the Aggregate Balance",
     "forced_to": ("buy or sell Hong Kong dollars at the two undertaking levels",
                   "publish each triggering on the day, with the amount"),
     "when": "the Hong Kong trading day; triggers are announced the same afternoon",
     "information": ("the banks' settlement positions in real time",
                     "the Exchange Fund's own book"),
     "constraints": ("the two hard barriers it is obliged to defend",
                     "a base rate formula over the federal funds target"),
     "instruments": ("USDHKD", "HKDJPY", "EURHKD"),
     "counterparties": ("the licensed banks in Hong Kong", "the Federal Reserve by construction",
                        "the AMCM one link down"),
     "observables": ("the undertaking triggers and their amounts", "the Aggregate Balance",
                     "HIBOR", "the base rate"),
     "impact": "IT OWNS THE ONLY DOOR a Macau shock can reach the dollar through; this pack "
               "reads its band position and never re-derives its mechanics",
     "persistence": "the band has stood since 2005 in its current two-sided form",
     "falsifier": "a Macau GGR surprise moves USDHKD's band position measurably beyond what the "
                  "same day's Hong Kong equity and rates flow explains -- the honest prior is "
                  "that it does not, and MO-B exists to measure that rather than assume it",
     "notes": "DECLARED AS A FOREIGN ACTOR ON PURPOSE. The `hk` pack owns this mechanism; "
              "naming it here is how the double peg is carried without being duplicated"},
    {"name": "Beijing's capital-control and anti-corruption apparatus",
     "holds": "the exit endorsement policy, the UnionPay withdrawal limits, the cash "
              "declaration rules and the enforcement intensity on cross-border gambling",
     "forced_to": ("announce limit and endorsement changes through the mainland regulators, "
                   "usually without reference to Macau at all",
                   "prosecute cross-border gambling promotion under mainland criminal law"),
     "when": "irregular and dated; the 2014-16 campaign, the 2017 and 2020 UnionPay and cash "
             "measures, and the criminal-law amendment that made cross-border gambling "
             "promotion an offence",
     "information": ("enforcement intent before any announcement",
                     "the real size of the outbound channel it is closing"),
     "constraints": ("a policy aimed at capital flight and corruption whose most visible "
                     "public measurement happens to be a Macau revenue table",
                     "enforcement that is announced by mainland regulators without reference to "
                     "Macau at all",
                     "a channel whose real size is unknown even to the authority closing it"),
     "instruments": ("USDCNH", "CHINAH", "XAUUSD"),
     "counterparties": ("the mainland visitor", "the promoters", "the banks and card networks"),
     "observables": ("the DICJ monthly print, which is the proxy",
                     "UnionPay and SAFE announcements", "the court record",
                     "the pawnshop and jewellery channel chatter"),
     "impact": "THE MECHANISM THAT MAKES THIS PACK WORTH ITS TRIAL BUDGET: between June 2014 and "
               "August 2016 the GGR series printed twenty-six consecutive year-on-year declines "
               "while the campaign ran, which is a monthly, unrevised, zero-lag public read on "
               "mainland policy intensity that exists nowhere else",
     "persistence": "campaign intensity runs in multi-year waves, not months",
     "falsifier": "the GGR series' deviation from a mainland-consumption control carries no "
                  "information about USDCNH or CHINAH beyond what mainland retail sales and the "
                  "credit impulse already carry",
     "notes": "the actor is FOREIGN and the observable is DOMESTIC, which is exactly the shape "
              "a third-party read is supposed to have"},
    {"name": "The Hengqin cooperation zone and the Greater Bay Area authorities",
     "holds": "the integration clock: the Hengqin Guangdong-Macao In-Depth Cooperation Zone "
              "established 2021-09-05, its tax and customs regime, and the Macau New Neighbourhood",
     "forced_to": ("publish the zone's rules, its tax rates and its investment targets",
                   "open and staff the border facilities that make the zone usable",
                   "report progress against the diversification targets the SAR is measured on"),
     "when": "policy documents on the mainland's own schedule; the physical openings are dated "
             "(the Hengqin port 24-hour co-location from 2020-08-18, Qingmao from 2021-09-08)",
     "information": ("the next phase of the integration plan before it is published",
                     "the actual take-up of the zone's incentives"),
     "constraints": ("two legal systems, two currencies and two customs regimes inside one "
                     "cooperation zone",
                     "a diversification target that has never yet been met"),
     "instruments": ("CHINAH", "USDCNH", "HK50"),
     "counterparties": ("the SAR government", "the Guangdong provincial authorities",
                        "the concessionaires' non-gaming investment programmes"),
     "observables": ("the zone's published rules and investment figures",
                     "the Hengqin checkpoint crossing counts",
                     "Macau-registered company formation in the zone"),
     "impact": "a slow, dated, policy-driven change in what the Macau economy IS; it moves the "
               "China-domestic complex more than it moves Macau's own series",
     "persistence": "a decade-scale programme with dated milestones",
     "falsifier": "Hengqin milestone dates carry no information about CHINAH beyond the "
                  "mainland policy news of the same week, tested with a matched-session control",
     "notes": "the one domain here whose executable leg is more mainland than Hong Kong"},
    {"name": "The border and transport operators as the physical throughput constraint",
     "holds": "six gates, a bridge, two ferry terminals, an airport and a light rail line, each "
              "with a published capacity and a counted flow",
     "forced_to": ("publish crossing statistics by checkpoint",
                   "run the HZMB shuttle and the ferry schedules to a timetable",
                   "open and close the gates on the hours the government sets"),
     "when": "daily, with monthly publication; the live waiting-time service updates "
             "continuously",
     "information": ("the real-time queue at each gate",
                     "the booking book for the bridge shuttle and the ferries"),
     "constraints": ("physical throughput that cannot be expanded within a month",
                     "immigration staffing and the opening hours",
                     "weather closing the ferries and the bridge"),
     "instruments": ("HK50", "USDCNH"),
     "counterparties": ("the mainland and Hong Kong visitor",
                        "the concessionaires' own shuttle fleets"),
     "observables": ("crossings by checkpoint", "the live waiting times",
                     "HZMB traffic and shuttle counts", "airport passenger volumes"),
     "impact": "the ONLY high-frequency public observable this jurisdiction has, and therefore "
               "the only candidate for a same-month read on the revenue print",
     "persistence": "capacity changes are dated and permanent: 2018-10-24 the bridge, "
                    "2020-08-18 Hengqin co-location, 2021-09-08 Qingmao",
     "falsifier": "checkpoint counts add nothing to a model of the monthly print that already "
                  "contains the seasonal block and the prior month; and a capacity opening that "
                  "raises counts without raising revenue proves the series is throughput, not "
                  "demand",
     "notes": "the capacity steps MUST be modelled or a pooled arrivals study reads a new gate "
              "as new demand"},
    {"name": "The pawnshop, jewellery and cash-out channel",
     "holds": "the documented route by which a mainland card limit becomes chips: a card swipe "
              "against gold or a watch, a cancelled sale, and cash across the counter",
     "forced_to": ("operate under a Macau licensing regime and the anti-money-laundering "
                   "reporting rules",
                   "sit physically on the Gongbei approach where the demand is"),
     "when": "continuously, and most visibly when mainland card limits tighten",
     "information": ("the real cost of moving money across the border that day",
                     "the demand for cash at the margin before any official series sees it"),
     "constraints": ("AML reporting and the periodic enforcement campaigns against the practice",
                     "the mainland's card-network limits, which are set elsewhere"),
     "instruments": ("XAUUSD", "USDCNH"),
     "counterparties": ("the mainland visitor", "the card networks", "the gold trade"),
     "observables": ("the pawnshop and jewellery shop count in the DSEC business series",
                     "the AML reporting statistics", "the press and forum chatter",
                     "gold retail turnover"),
     "impact": "a weak, honest XAUUSD edge: physical gold demand as a capital-control release "
               "valve, at a scale that is real for Macau and marginal for the world price",
     "persistence": "the channel adapts to each enforcement wave rather than disappearing",
     "falsifier": "Macau gold retail turnover carries no information about XAUUSD beyond "
                  "mainland gold demand and the dollar leg, tested against the mainland's own "
                  "retail gold series",
     "notes": "DECLARED WEAK ON ITS FACE. The pack states the direction and the size rather "
              "than claiming a 30-square-kilometre pawnshop trade moves the London fix"},
    {"name": "The Legislative Assembly and the Chief Executive as the source of dated statute",
     "holds": "the gaming law and its amendments, the concession framework and the annual "
              "gazetted general-holiday table",
     "forced_to": ("publish every law and dispatch in the Boletim Oficial, in Chinese and "
                   "Portuguese",
                   "gazette the next year's general holidays before the year begins",
                   "re-tender the concessions on a ten-year clock"),
     "when": "the Assembly's session calendar; Law 7/2022 in June 2022 and the concession "
             "dispatches in December 2022 are the two that matter most to this pack",
     "information": ("the text of an amendment before it is gazetted",
                     "the concession evaluation before the award"),
     "constraints": ("a bilingual legal system in which the Portuguese text is the legal one "
                     "for the older run",
                     "a mainland policy direction the SAR implements rather than sets"),
     "instruments": ("HK50", "CHINAH"),
     "counterparties": ("the concessionaires", "the DICJ as enforcer",
                        "the Lusophone and Chinese press"),
     "observables": ("the Boletim Oficial Series I and II",
                     "the Assembly's debate record", "the Policy Address"),
     "impact": "every structural break in this pack's data has a gazette number; the statute is "
               "the event and the press report is the stamp",
     "persistence": "a gaming law amendment sets the terms for a decade",
     "falsifier": "the gazette dates carry no market information beyond the press reports that "
                  "preceded them, which is the honest prior and is exactly what the source "
                  "graph layer exists to date",
     "notes": "READ IN PORTUGUESE OR NOT AT ALL: the Chinese business pages report the outcome "
              "and the Portuguese legal press reports the drafting, which is where the lead is"},
    {"name": "The non-resident workforce and the labour-importation quota",
     "holds": "roughly a fifth of the working population on government-issued blue cards, "
              "concentrated on the casino floor's support functions and in construction",
     "forced_to": ("hold a quota the government grants and can withdraw",
                   "leave when the quota is cut, as happened through the 2020-22 closure"),
     "when": "quota decisions are administrative and dated; the stock is published quarterly "
             "by DSEC",
     "information": ("the real staffing constraint on a peak weekend before it shows in "
                     "occupancy",
                     "the quota applications in hand before the labour bureau decides them"),
     "constraints": ("a statutory preference for resident employment, especially for dealers",
                     "housing and transport capacity in a 30-square-kilometre territory"),
     "instruments": ("HK50", "CHINAH"),
     "counterparties": ("the concessionaires and the hotels", "the SAR labour bureau",
                        "the Guangdong labour market next door"),
     "observables": ("the DSEC non-resident worker series",
                     "the unemployment rate and the median wage",
                     "the dealer unions' public positions"),
     "impact": "the supply-side cap on how fast the industry can restart after a shock; it is "
               "why the 2023 recovery in arrivals ran ahead of the recovery in capacity",
     "persistence": "quota policy moves on a multi-quarter clock",
     "falsifier": "the non-resident worker series adds nothing to a capacity model that already "
                  "contains the room inventory and the table count",
     "notes": "the labour constraint is the half of the capacity story the table count misses"},
)
# --------------------------------------------------------------------------- domains
DOMAINS: tuple[dict[str, Any], ...] = (
    {"id": "MO-A", "title": "The DICJ first-working-day gaming revenue print",
     "objects": ("the monthly gross gaming revenue table, dated to the first working day",
                 "the year-on-year and month-on-month change the tape actually trades",
                 "the mid-month run-rate estimate the trade press publishes as the only "
                 "consensus",
                 "the publication minute inside the Hong Kong afternoon session"),
     "conditions": ("the surprise against the published mid-month run-rate estimate",
                    "whether the first working day was pushed out by a holiday block",
                    "the era: pre-2014 boom, 2014-16 decline, 2020-22 closure, post-2023"),
     "instruments": ("HK50", "CHINAH", "US500"),
     "controls": ("the same 05:00-06:00 UTC window on the first working day of months when no "
                  "release fell there, which separates a release effect from a "
                  "first-working-day effect",
                  "the matched weekday-plus-hour control on HK50",
                  "a randomised-date null drawn from the same month's sessions"),
     "notes": "TWELVE EVENTS A YEAR and four usable eras: the sample is the binding constraint "
              "and is reported, never manufactured by pooling across the era boundaries"},
    {"id": "MO-B", "title": "The peg on a peg and the pataca's absent variance",
     "objects": ("the MOP 1.03 = HKD 1.00 note-issuing link and its narrow band",
                 "USDHKD's position between the 7.7500 and 7.8500 undertakings",
                 "the implied USD/MOP corridor computed by `peg_chain`",
                 "the AMCM deposits-by-currency table as the flow underneath"),
     "conditions": ("the band-position bucket at the Hong Kong end",
                    "whether the Hong Kong undertakings triggered in the window",
                    "the HKD share of Macau deposits"),
     "instruments": ("USDHKD", "EURHKD", "HKDJPY"),
     "controls": ("the SAME band-position state measured on a day with no Macau event at all, "
                  "which is the null for a state variable borrowed from another jurisdiction",
                  "the `hk` pack's own band study over the identical window, so a finding here "
                  "must beat Hong Kong's own measurement of its own band to be Macau's",
                  "a block-permuted USDHKD series, the null for a bounded price"),
     "notes": "THE HONEST PRIOR IS THAT THIS DOMAIN FINDS NOTHING, and it is here to measure "
              "that rather than assume it: a bounded price two links away has almost no room "
              "to carry a Macau shock, and a positive result would be the surprise"},
    {"id": "MO-C", "title": "Visitor arrivals by origin, by checkpoint and by transport mode",
     "objects": ("the DSEC monthly arrivals series and its by-origin split",
                 "the by-checkpoint and by-transport split",
                 "the overnight versus same-day share",
                 "hotel occupancy, average daily rate and length of stay"),
     "conditions": ("the mainland holiday block the month contains",
                    "the capacity era: pre-bridge, post-2018-10-24, post-Qingmao 2021-09-08",
                    "the overnight share bucket, which separates a gambler from a day-tripper"),
     "instruments": ("HK50", "USDCNH", "CHINAH"),
     "controls": ("Hong Kong's own mainland arrivals over the same months, separating 'the "
                  "mainland travelled' from 'the mainland came to Macau'",
                  "the same months in the pre-bridge capacity era",
                  "a seasonal-dummy-plus-lag benchmark the series must beat to be informative"),
     "notes": "THREE WEEKS LATE BY CONSTRUCTION, so this series NEVER conditions the same "
              "month's revenue print; treating it as leading is a look-ahead and is refused"},
    {"id": "MO-D", "title": "The gates: border crossings, the bridge and the live waiting times",
     "objects": ("crossings by checkpoint, monthly",
                 "HZMB traffic and shuttle passenger counts since 2018-10-24",
                 "the live gate waiting-time service, the only sub-daily public Macau series",
                 "airport and ferry passenger volumes"),
     "conditions": ("the checkpoint (Gongbei, Qingmao, Hengqin, the bridge, the ferries, the "
                    "airport)",
                    "weekend versus weekday and holiday-block membership",
                    "the capacity era, because a new gate raises counts without raising demand"),
     "instruments": ("HK50", "USDCNH"),
     "controls": ("the Shenzhen-Hong Kong crossing counts over the same days, which separates "
                  "'the border reopened' from 'Macau was the destination'",
                  "the same weekday in weeks with no holiday block",
                  "a capacity-step dummy at 2018-10-24, 2020-08-18 and 2021-09-08"),
     "notes": "THE ONLY HIGH-FREQUENCY GROUND THIS PACK HAS. It is also the one most likely to "
              "be throughput rather than demand, which is what the capacity controls are for"},
    {"id": "MO-E", "title": "The junket collapse and the gaming-law regime break",
     "objects": ("the DICJ promoter licence count, from 235 in 2013 to a few dozen",
                 "the VIP share of the quarterly segment split",
                 "the dated legal events: the 2021-11-27 prosecution, Law 7/2022, the "
                 "2023-01-01 concessions",
                 "the satellite-casino transition clock"),
     "conditions": ("which side of each dated boundary the window sits on",
                    "the VIP-share bucket",
                    "whether the window contains a court or gazette date"),
     "instruments": ("HK50", "CHINAH"),
     "controls": ("the mass-segment series over the same quarters, the other half of the same "
                  "revenue, which separates 'the VIP channel broke' from 'Macau slowed'",
                  "a mainland luxury-consumption control over the same quarters",
                  "the same windows in quarters with no dated legal event"),
     "notes": "EVERY POOLED GGR STUDY DIES HERE. These boundaries are not regime 'context': "
              "they changed what the series measures, and POLICY_ERAS carries their dates"},
    {"id": "MO-F", "title": "Hengqin, the Greater Bay Area and the integration clock",
     "objects": ("the Cooperation Zone established 2021-09-05 and its published milestones",
                 "the Hengqin checkpoint crossing counts and the 24-hour co-location from "
                 "2020-08-18",
                 "Macau-registered company formation in the zone",
                 "the concessions' non-gaming investment commitments"),
     "conditions": ("whether the window contains a published zone milestone",
                    "the crossing-count trend at the Hengqin gate",
                    "the mainland policy cycle the milestone sits inside"),
     "instruments": ("CHINAH", "USDCNH", "HK50"),
     "controls": ("other Greater Bay Area policy dates with no Macau content, which separates "
                  "'the mainland announced' from 'Macau was integrated'",
                  "the matched-session control on CHINAH",
                  "milestone dates that were pre-announced, as the null for a known event"),
     "notes": "the one domain whose executable leg is more mainland than Hong Kong; the effect "
              "is expected to be slow and small and the pack says so on its face"},
    {"id": "MO-G", "title": "A debt-free government, a single tax and the fiscal reserve",
     "objects": ("the monthly gaming tax receipt and budget execution",
                 "the basic and excess fiscal reserve balances",
                 "the reserve drawdown through the 2020-22 closure",
                 "the annual cash handout as a dated fiscal event"),
     "conditions": ("the receipt's residual after the published GGR is accounted for",
                    "whether the reserve was being drawn or rebuilt",
                    "the budget year's position"),
     "instruments": ("HK50", "USDHKD"),
     "controls": ("the published GGR print itself as the benchmark the receipt must beat to "
                  "carry any information at all",
                  "the same windows in months with no accounts publication",
                  "a placebo drawn from the budget-execution series' own noise"),
     "notes": "THE HONEST TEST IS WHETHER THE RESIDUAL EXISTS. A tax that is 35% of a published "
              "number carries information only in what it is NOT explained by"},
    {"id": "MO-H", "title": "The dual calendar: lunar festivals, Catholic feasts and the "
                            "first-working-day clock",
     "objects": ("the nine gazetted lunar and solar-term closures",
                 "Good Friday and the day before Easter, computed from Easter",
                 "the nine fixed solar general holidays",
                 "the first working day of each month, which the two calendars jointly set"),
     "conditions": ("whether the month's first working day was pushed out, and by how many days",
                    "whether the closure was Chinese, Catholic or constitutional",
                    "whether Hong Kong was open when Macau was shut, which happens because "
                    "Hong Kong substitutes weekend holidays and Macau does not"),
     "instruments": ("HK50", "CHINAH", "USDHKD"),
     "controls": ("the same weekday in weeks with no closure, matched on the month",
                  "the Hong Kong calendar as the paired control, since the carrier is a Hong "
                  "Kong index and its own closures must be separated out",
                  "a randomised-date null over the same year's sessions"),
     "notes": "THE DISTINGUISHING CALENDAR FACT of this jurisdiction: two religious calendars "
              "on one trading day, one derivable and one not, and a release clock that both of "
              "them move"},
    {"id": "MO-I", "title": "The capital-control channel: cards, wallets, pawnshops and gold",
     "objects": ("the mainland card and withdrawal limits as dated announcements",
                 "the AMCM electronic-payment and cross-border wallet statistics",
                 "the pawnshop and jewellery trade as the documented cash-out route",
                 "the e-CNY pilot's scope in Macau"),
     "conditions": ("whether a limit change was announced in the window",
                    "the enforcement-intensity era",
                    "the gold retail turnover trend"),
     "instruments": ("USDCNH", "XAUUSD"),
     "controls": ("the mainland's own gold retail and outbound-travel series over the same "
                  "months, separating 'capital left China' from 'capital left through Macau'",
                  "the same windows in periods with no announced limit change",
                  "a Hong Kong jewellery-trade control, the sibling channel"),
     "notes": "DECLARED WEAK. The claim is about DIRECTION and about a channel being open or "
              "shut, never about a 30-square-kilometre pawnshop trade moving the London fix"},
    {"id": "MO-J", "title": "Gaming revenue as a third-party read on mainland policy intensity",
     "objects": ("the twenty-six consecutive year-on-year declines from June 2014 to August 2016",
                 "the GGR series' deviation from a mainland-consumption control",
                 "the dated mainland enforcement and capital-control measures",
                 "the VIP share as the campaign-sensitive component"),
     "conditions": ("the deviation bucket against the mainland control",
                    "whether a dated mainland measure falls in the window",
                    "the VIP-versus-mass composition"),
     "instruments": ("USDCNH", "CHINAH", "XAUUSD"),
     "controls": ("mainland retail sales and the credit impulse over the same months, which is "
                  "the benchmark the deviation must beat to be POLICY and not CONSUMPTION",
                  "Hong Kong retail sales, the sibling cross-border spending series",
                  "the same windows in the 2020-22 closure, when the channel was shut for a "
                  "different reason entirely and the proxy must NOT fire"),
     "notes": "THE REASON MACAU EARNS A PACK. A monthly, zero-lag, never-revised public series "
              "that was the best-known proxy for mainland policy intensity in 2014-16; the "
              "2020-22 closure is the built-in placebo that says whether the proxy still works"},
    {"id": "MO-K", "title": "The concession cycle and the non-gaming investment commitments",
     "objects": ("the ten-year concessions running 2023-01-01 to 2032-12-31",
                 "the dated non-gaming investment milestones",
                 "the table and machine allocations the government grants",
                 "the satellite-casino transition clock under Law 7/2022"),
     "conditions": ("whether the window contains a gazetted dispatch or an allocation change",
                    "the progress against the investment commitments",
                    "the hotel room and non-gaming capacity trend"),
     "instruments": ("HK50", "CHINAH"),
     "controls": ("the same windows in years with no concession action, which is most of them",
                  "the Hong Kong index's own session beta as the matched control",
                  "pre-announced milestone dates as the null for a known event"),
     "notes": "SINGLE NAMES ARE THE EVENT LANE HERE AND THE INDEX IS THE ONLY EXECUTABLE LEG; "
              "the domain is about the ALLOCATION regime, not about any operator"},
    {"id": "MO-L", "title": "Imported inflation and the price level of a pegged, import-total "
                            "economy",
     "objects": ("the DSEC consumer price index and its imported component",
                 "the mainland and Hong Kong price levels it is a function of",
                 "the non-resident wage and the minimum wage as the domestic component",
                 "the exchange-rate pass-through that the peg removes by construction"),
     "conditions": ("the mainland producer and consumer price trend",
                    "the Hong Kong CPI over the same months",
                    "whether the window contains a labour-quota decision"),
     "instruments": ("USDCNH", "USDHKD"),
     "controls": ("Hong Kong's CPI over the same months, the sibling pegged import economy, "
                  "which separates 'the peg imported it' from 'Macau did something'",
                  "the mainland CPI as the upstream control",
                  "the same windows with no quota decision"),
     "notes": "A TRANSFER TEST, NOT A DOMESTIC ONE: with a pegged currency and near-total import "
              "dependence, this series is other people's inflation arriving with a lag, and the "
              "domain exists to measure the LAG rather than to claim a Macau price mechanism"},
    {"id": "MO-M", "title": "Capacity: tables, machines, rooms, power and the workforce",
     "objects": ("the DICJ table and machine counts",
                 "the hotel room inventory and occupancy",
                 "CEM electricity sales and the Zhuhai water supply",
                 "the non-resident workforce and the labour quota"),
     "conditions": ("whether capacity was the binding constraint in the window",
                    "the occupancy bucket",
                    "the quota era"),
     "instruments": ("HK50", "CHINAH"),
     "controls": ("the arrivals series over the same months, which separates a capacity "
                  "constraint from a demand shortfall",
                  "the same months in years with the same room inventory",
                  "electricity sales as the independent physical read on whether the floors "
                  "were actually busy"),
     "notes": "the supply side of every other domain; it is what makes a demand finding "
              "falsifiable rather than a restatement of the revenue series"},
    {"id": "MO-N", "title": "The Hong Kong carrier itself: how a Macau print reaches an index",
     "objects": ("the index membership through which Macau exposure enters HK50 and CHINAH",
                 "the Hong Kong session the print lands inside",
                 "the New York session the US-listed operators trade in, hours later",
                 "the Hong Kong closing auction that marks the day"),
     "conditions": ("whether the Hong Kong market was open on the release day at all",
                    "the index weight of the Macau complex in the window",
                    "whether the print landed before or after the Hong Kong lunch break"),
     "instruments": ("HK50", "CHINAH", "US500", "NAS100"),
     "controls": ("the same window on Hong Kong sessions with no Macau release, the base rate "
                  "of the carrier's own volatility",
                  "the mainland session's own news over the same hours",
                  "release days when Hong Kong was closed and Macau was not, which is the "
                  "cleanest available separation of the two calendars"),
     "notes": "MACAU'S ONLY EQUITY LEG IS ANOTHER JURISDICTION'S INDEX, so the carrier's own "
              "mechanics must be controlled for before anything here is called a Macau effect"},
)

# --------------------------------------------------------------------------- cells
#: WHAT EACH DOMAIN MINTS. The horizon and mechanism family a cell inherits from its domain, so
#: a cell is never a cartesian product of nothing: every row below is one real condition this
#: pack's own data plane can evaluate against one symbol the box can actually trade.
DOMAIN_CELL_SPEC: dict[str, tuple[str, str]] = {
    "MO-A": ("release_surprise", "0 to 5 sessions"),
    "MO-B": ("band_state", "1 to 20 sessions"),
    "MO-C": ("physical_flow", "1 to 3 months"),
    "MO-D": ("high_frequency_proxy", "0 to 10 sessions"),
    "MO-E": ("regime_break", "1 to 4 quarters"),
    "MO-F": ("administered_event", "1 to 2 quarters"),
    "MO-G": ("fiscal_flow", "0 to 10 sessions"),
    "MO-H": ("calendar_event", "0 to 3 sessions"),
    "MO-I": ("capital_controls", "1 to 3 months"),
    "MO-J": ("policy_proxy", "1 to 2 quarters"),
    "MO-K": ("administered_event", "0 to 10 sessions"),
    "MO-L": ("imported_inflation", "1 to 3 months"),
    "MO-M": ("capacity", "1 to 2 quarters"),
    "MO-N": ("session_microstructure", "0 to 2 sessions"),
}


def cells() -> tuple[dict[str, Any], ...]:
    """THE TESTABLE CELLS THIS PACK MINTS, for the one gauntlet.

    The cross product of each domain's own conditions with each domain's own EXECUTABLE
    instruments. It is a product and not a blow-up because both factors are already the pack's
    measured claims: a condition is a state this pack's data plane can evaluate, and an
    instrument is a symbol the broker registry carries. A domain that names three conditions
    and three instruments is claiming nine testable statements and the pack writes all nine
    down rather than testing one and calling the country covered.
    """
    execs = set(EXECUTABLE_INSTRUMENTS)
    out: list[dict[str, Any]] = []
    for dom in DOMAINS:
        did = str(dom["id"])
        family, horizon = DOMAIN_CELL_SPEC.get(did, ("mechanism", "1 to 10 sessions"))
        controls = tuple(dom["controls"])
        for symbol in dom["instruments"]:
            if symbol not in execs:
                continue
            for i, condition in enumerate(dom["conditions"]):
                out.append({
                    "cell_id": f"{did}:{symbol}:C{i + 1}",
                    "domain": did, "symbol": symbol, "condition": condition,
                    "mechanism_family": family, "horizon": horizon,
                    "control": controls[i % len(controls)],
                    "why": str(dom["title"]),
                })
    return tuple(out)


CELLS: tuple[dict[str, Any], ...] = cells()

# --------------------------------------------------------------------------- interactions
#: HOW THIS COUNTRY IS NOT TESTED ALONE. Each row names another pack, the shared mechanism, the
#: observable that carries it and the executable targets, so a Macau finding is measured against
#: the sibling that owns the other end rather than in isolation.
INTERACTIONS: tuple[dict[str, Any], ...] = (
    {"with": "hk",
     "mechanism": "THE DOUBLE PEG. MOP 1.03 = HKD 1.00 at the note-issuing banks, and the HKD "
                  "is held between the HKMA's 7.75 and 7.85 convertibility undertakings, so "
                  "every Macau external shock reaches the dollar through Hong Kong's band and "
                  "through nothing else. The `hk` pack owns the band, the Aggregate Balance and "
                  "the undertaking triggers; this pack reads them and computes the implied "
                  "USD/MOP corridor rather than re-deriving a single one of Hong Kong's "
                  "mechanics",
     "observable": "USDHKD's band position on the release day, the HKMA's undertaking triggers, "
                   "and the HKD share of Macau bank deposits as the flow underneath",
     "targets": ("USDHKD", "EURHKD", "HKDJPY", "HK50"),
     "control": "the `hk` pack's own band study over the identical window -- a Macau claim must "
                "beat Hong Kong's own measurement of its own band before it is Macau's"},
    {"with": "cn",
     "mechanism": "the customer is the mainland. Exit endorsements, UnionPay withdrawal limits, "
                  "cash declaration rules and anti-corruption enforcement are all set in "
                  "Beijing and all land on a Macau revenue table that publishes monthly with no "
                  "lag, which makes the DICJ print a third-party read on mainland policy "
                  "intensity and on cross-border capital movement",
     "observable": "the GGR series' deviation from a mainland retail-consumption control, "
                   "beside the dated UnionPay, SAFE and enforcement announcements",
     "targets": ("USDCNH", "CHINAH", "XAUUSD"),
     "control": "mainland retail sales and the credit impulse over the same months; a deviation "
                "that does not beat them is consumption wearing policy's hat"},
    {"with": "tw",
     "mechanism": "the two remaining cross-strait and regional visitor sources. Taiwan arrivals "
                  "are a small but separately published origin line in the DSEC table, and they "
                  "move with cross-strait travel policy rather than with mainland policy -- "
                  "which makes them the natural control that separates 'Chinese demand' from "
                  "'regional Chinese-speaking demand'",
     "observable": "the Taiwan and Hong Kong origin lines of DSEC arrivals against the mainland "
                   "line over the same months",
     "targets": ("HK50", "CHINAH"),
     "control": "Taiwan's own outbound travel statistics, so a divergence is a Macau fact and "
                "not a Taiwanese one"},
    {"with": "sg",
     "mechanism": "THE OTHER INTEGRATED RESORT JURISDICTION. Singapore's two integrated resorts "
                  "are the only comparable regulated gaming duopoly in Asia and they draw on an "
                  "overlapping regional VIP customer, so Singapore's gaming and tourism series "
                  "is the sibling control that separates 'Asian gaming demand' from 'the "
                  "mainland policy channel' -- the single most useful placebo this pack has",
     "observable": "Singapore visitor arrivals and gaming-adjacent tourism receipts against the "
                   "Macau arrivals and GGR series over the same months",
     "targets": ("USDSGD", "HK50"),
     "control": "the 2014-16 window, in which Macau fell for twenty-six months and the Singapore "
                "series did not -- if a mechanism fires in both, it is regional and not Macau's"},
    {"with": "us",
     "mechanism": "the concessionaires' US parents are listed in New York, so a Macau print "
                  "lands twice: once in the Hong Kong afternoon and again eight hours later in "
                  "the New York session. That double landing is a genuine, dated, testable "
                  "information-diffusion object, and the only executable legs in the second "
                  "window are the US indices because the operators themselves are event lane",
     "observable": "the HK50 reaction in the release hour against the US500 and NAS100 reaction "
                   "in the same calendar day's New York session",
     "targets": ("US500", "NAS100", "HK50"),
     "control": "the same two windows on first working days with no Macau release, and the US "
                "session's own macro calendar for that day"},
    {"with": "kr",
     "mechanism": "the regional foreigner-only casino and outbound-travel complex: Korean "
                  "outbound travel and the won's risk beta move with the same regional risk "
                  "appetite that fills Macau's mass floor, which makes USDKRW-adjacent regional "
                  "risk a control on whether a Macau demand finding is Macau's or Asia's",
     "observable": "regional outbound travel and the Asian risk complex over the release windows",
     "targets": ("HK50", "USDJPY"),
     "control": "the Asian session's own risk beta on days with no Macau release"},
)
# --------------------------------------------------------------------------- transmission
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    {"id": "MO-T1",
     "source": "DICJ monthly gross gaming revenue, published on the first working day",
     "target": "HK50", "targets": ("HK50", "CHINAH"), "to_country": "hk", "sign": "+",
     "mechanism": "the only scheduled information event this jurisdiction produces lands at "
                  "05:00 UTC inside the Hong Kong afternoon session, and the gaming complex is "
                  "an index constituent, so the aggregate reprices the index through membership",
     "horizon": "0 to 5 sessions", "horizon_class": "intraday", "lag_days": 0.0,
     "actor": "the DICJ as publisher", "constraint": "a statutory publication date",
     "flow": "scheduled release into index repricing",
     "condition": "a surprise against the published mid-month run-rate estimate",
     "control": "the same window on first working days with no release; the matched "
                "weekday-plus-hour control on HK50",
     "falsifier": "the release-hour move matches the same hour on first working days in months "
                  "when no release fell there, which would make it a first-working-day effect",
     "evidence": "HYPOTHESIS"},
    {"id": "MO-T2",
     "source": "The GGR series' deviation from a mainland consumption control",
     "target": "USDCNH", "targets": ("USDCNH", "CHINAH"), "to_country": "cn", "sign": "-",
     "mechanism": "the series is a monthly, unrevised, zero-lag public read on mainland "
                  "enforcement intensity and on cross-border capital movement; a deviation that "
                  "survives a consumption control is policy, and policy intensity is a CNH and "
                  "China-risk state",
     "horizon": "1 to 2 quarters", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "Beijing's capital-control and anti-corruption apparatus",
     "constraint": "a policy aimed at capital flight whose most visible public measurement is a "
                   "Macau revenue table",
     "flow": "enforcement intensity into cross-border flow",
     "condition": "a deviation beyond its historical interquartile range against the control",
     "control": "mainland retail sales and the credit impulse over the same months; the 2020-22 "
                "closure as the built-in placebo where the proxy must NOT fire",
     "falsifier": "the deviation carries no information about USDCNH or CHINAH beyond what "
                  "mainland retail sales and the credit impulse already carry",
     "evidence": "HYPOTHESIS"},
    {"id": "MO-T3",
     "source": "USDHKD's position between the 7.7500 and 7.8500 convertibility undertakings",
     "target": "USDHKD", "targets": ("USDHKD", "EURHKD", "HKDJPY"), "to_country": "hk",
     "sign": "+",
     "mechanism": "THE DOUBLE PEG'S ONLY DOOR. The pataca's external value is a fixed multiple "
                  "of the Hong Kong dollar's, so every Macau external shock is a Hong Kong band "
                  "event or it is nothing; the casinos' HKD receipts are the flow underneath",
     "horizon": "1 to 20 sessions", "horizon_class": "multi_day", "lag_days": 2.0,
     "actor": "the HKMA as the band's counterparty and the note-issuing banks below it",
     "constraint": "two hard barriers the HKMA is obliged to defend",
     "flow": "gaming HKD receipts into the Hong Kong deposit and settlement system",
     "condition": "a band-position bucket at the weak or strong extreme",
     "control": "the `hk` pack's own band study over the identical window; a block-permuted "
                "USDHKD series as the null for a bounded price",
     "falsifier": "the Macau deposit and revenue series add nothing to a band-position model "
                  "that already contains Hong Kong's Aggregate Balance -- which is the honest "
                  "prior, and a positive result here would be the surprise",
     "evidence": "HYPOTHESIS"},
    {"id": "MO-T4",
     "source": "DSEC visitor arrivals by origin, with the overnight share",
     "target": "HK50", "targets": ("HK50", "USDCNH"), "to_country": "hk", "sign": "+",
     "mechanism": "arrivals are the physical demand series behind the revenue series; the "
                  "by-origin split separates a mainland policy shock from a regional one and "
                  "the overnight share separates a gambler from a day-tripper",
     "horizon": "1 to 3 months", "horizon_class": "multi_day", "lag_days": 22.0,
     "actor": "the mainland visitor under the Individual Visit Scheme",
     "constraint": "the exit-endorsement regime and the gates' physical throughput",
     "flow": "cross-border travel into gaming and retail spend",
     "condition": "an overnight-share move beyond its seasonal band",
     "control": "Hong Kong's own mainland arrivals over the same months; the same months in the "
                "pre-bridge capacity era",
     "falsifier": "arrivals explain the monthly print no better than a seasonal dummy plus the "
                  "prior month's print, out of sample across the era boundaries",
     "evidence": "HYPOTHESIS"},
    {"id": "MO-T5",
     "source": "Checkpoint crossings and the live gate waiting times",
     "target": "HK50", "targets": ("HK50", "CHINAH"), "to_country": "hk", "sign": "+",
     "mechanism": "the only sub-daily public Macau series; a queue at the Gongbei and Qingmao "
                  "gates is a same-month read on demand weeks before the arrivals table admits "
                  "it and a month before the revenue table does",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 0.0,
     "actor": "the border and transport operators",
     "constraint": "physical throughput that cannot be expanded within a month",
     "flow": "gate throughput into floor traffic",
     "condition": "a crossing count above its trailing seasonal norm at a specific checkpoint",
     "control": "the Shenzhen-Hong Kong crossings over the same days; a capacity-step dummy at "
                "2018-10-24, 2020-08-18 and 2021-09-08",
     "falsifier": "crossing counts add nothing to a model of the print that already contains "
                  "the seasonal block and the prior month, and a capacity opening raises counts "
                  "without raising revenue",
     "evidence": "HYPOTHESIS"},
    {"id": "MO-T6",
     "source": "The dated junket and gaming-law regime boundaries",
     "target": "CHINAH", "targets": ("CHINAH", "HK50"), "to_country": "hk", "sign": "-",
     "mechanism": "the 2021-11-27 prosecution, Law 7/2022 and the 2023-01-01 concessions "
                  "destroyed the VIP credit channel and changed both the LEVEL and the VARIANCE "
                  "of the whole series; a gazette date is an administered event, not a price "
                  "response",
     "horizon": "1 to 4 quarters", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "the Legislative Assembly, the Chief Executive and the courts",
     "constraint": "a criminal-law exposure that was demonstrated rather than theorised",
     "flow": "legal change into channel capacity",
     "condition": "a window containing a dated court or gazette event",
     "control": "the mass-segment series over the same quarters; a mainland luxury-consumption "
                "control; quarters with no dated legal event",
     "falsifier": "the VIP share's decline is explained by the mainland consumption cycle over "
                  "the same quarters rather than by the dated legal events",
     "evidence": "HYPOTHESIS"},
    {"id": "MO-T7",
     "source": "Hengqin Cooperation Zone milestones and the Greater Bay Area integration clock",
     "target": "CHINAH", "targets": ("CHINAH", "USDCNH"), "to_country": "cn", "sign": "+",
     "mechanism": "a dated, published, decade-scale change in what the Macau economy is, driven "
                  "by mainland policy; the effect is expected on the China-domestic complex "
                  "rather than on Macau's own series",
     "horizon": "1 to 2 quarters", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "the Hengqin and Guangdong authorities",
     "constraint": "two legal systems, two currencies and two customs regimes in one zone",
     "flow": "policy milestone into cross-border investment and traffic",
     "condition": "a window containing a published zone milestone",
     "control": "other Greater Bay Area policy dates with no Macau content; the matched-session "
                "control on CHINAH",
     "falsifier": "milestone dates carry no information about CHINAH beyond the mainland policy "
                  "news of the same week",
     "evidence": "HYPOTHESIS"},
    {"id": "MO-T8",
     "source": "The Macau pawnshop, jewellery and card cash-out channel",
     "target": "XAUUSD", "targets": ("XAUUSD", "USDCNH"), "to_country": "global", "sign": "+",
     "mechanism": "physical gold and watches are the documented route by which a mainland card "
                  "limit becomes cash at the border; the channel opens and shuts with "
                  "enforcement, which is a capital-control release valve with a physical metal "
                  "leg",
     "horizon": "1 to 3 months", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "the pawnshop and jewellery trade on the Gongbei approach",
     "constraint": "AML reporting and the periodic enforcement campaigns",
     "flow": "card limit into physical metal into cash",
     "condition": "an announced mainland card or withdrawal limit change in the window",
     "control": "the mainland's own gold retail series; a Hong Kong jewellery-trade control; "
                "periods with no announced limit change",
     "falsifier": "Macau gold retail turnover carries no information about XAUUSD beyond "
                  "mainland gold demand and the dollar leg -- DECLARED WEAK ON ITS FACE",
     "evidence": "HYPOTHESIS"},
    {"id": "MO-T9",
     "source": "The first-working-day clock itself, set by two religious calendars at once",
     "target": "HK50", "targets": ("HK50", "USDHKD"), "to_country": "hk", "sign": "+",
     "mechanism": "the release date is not the 1st: January opens on a general holiday, October "
                  "on two, and a Lunar New Year at the start of February pushes the print out by "
                  "days -- and because Hong Kong substitutes weekend holidays and Macau does "
                  "not, the print can land on a day the carrier is shut",
     "horizon": "0 to 3 sessions", "horizon_class": "intraday", "lag_days": 0.0,
     "actor": "the Legislative Assembly's gazetted holiday table and the lunar calendar",
     "constraint": "no weekend substitution in Macau and full substitution in Hong Kong",
     "flow": "calendar into release timing into carrier availability",
     "condition": "a month whose first working day was pushed out by two days or more",
     "control": "the same weekday in weeks with no closure; the Hong Kong calendar as the "
                "paired control",
     "falsifier": "pushed-out release days behave identically to on-time ones once the weekday "
                  "and the month are matched",
     "evidence": "HYPOTHESIS"},
    {"id": "MO-T10",
     "source": "The DSF monthly gaming tax receipt's residual against the published GGR",
     "target": "HK50", "targets": ("HK50", "USDHKD"), "to_country": "hk", "sign": "+",
     "mechanism": "a tax that is 35% of a published number carries information only in what it "
                  "is NOT explained by: collection timing, the concession premium and the "
                  "reserve transfer are the residual, and the residual is the only part that is "
                  "news",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "the SAR treasury", "constraint": "revenue concentration with no diversification",
     "flow": "gaming tax into budget execution into the fiscal reserve",
     "condition": "a receipt residual beyond its historical interquartile range",
     "control": "the published GGR print itself as the benchmark the receipt must beat; months "
                "with no accounts publication",
     "falsifier": "the residual is white noise against the published GGR, which is the honest "
                  "prior and makes this edge a measured refusal rather than a finding",
     "evidence": "HYPOTHESIS"},
    {"id": "MO-T11",
     "source": "The same Macau print landing twice: the Hong Kong afternoon and the New York "
               "session eight hours later",
     "target": "US500", "targets": ("US500", "NAS100", "HK50"), "to_country": "us", "sign": "+",
     "mechanism": "the concessionaires' US parents trade in New York, so a 05:00 UTC Macau "
                  "number is priced once in Asia and again in America; that is a dated, "
                  "testable information-diffusion object and the only executable legs in the "
                  "second window are the indices, because the operators are event lane",
     "horizon": "0 to 2 sessions", "horizon_class": "intraday", "lag_days": 0.0,
     "actor": "the Hong Kong and New York equity markets",
     "constraint": "two sessions, one number, eight hours apart",
     "flow": "information diffusion across two time zones",
     "condition": "a release-day HK50 move beyond its own release-window norm",
     "control": "the same two windows on first working days with no Macau release; the US "
                "session's own macro calendar for that day",
     "falsifier": "the New York window's move is fully explained by the US session's own macro "
                  "calendar and by the overnight Asian beta",
     "evidence": "HYPOTHESIS"},
    {"id": "MO-T12",
     "source": "The AMCM deposits-by-currency table as the monetary trace of the casino cage",
     "target": "USDHKD", "targets": ("USDHKD", "EURHKD"), "to_country": "hk", "sign": "+",
     "mechanism": "the tables are dealt in Hong Kong dollars and the receipts land in the Macau "
                  "banking system, so gaming demand becomes a countable HKD deposit fact one "
                  "step before it becomes a Hong Kong settlement fact",
     "horizon": "1 to 3 months", "horizon_class": "multi_day", "lag_days": 45.0,
     "actor": "the two note-issuing banks and the AMCM",
     "constraint": "a currency board that cannot vary and a six-week publication lag",
     "flow": "cage receipts into deposits into the Hong Kong interbank system",
     "condition": "an HKD deposit-share move beyond its trailing band",
     "control": "the `hk` pack's Aggregate Balance over the same months; months with no deposit "
                "share move",
     "falsifier": "the HKD deposit share carries no information about USDHKD's band position "
                  "beyond Hong Kong's own Aggregate Balance",
     "evidence": "HYPOTHESIS"},
)

# --------------------------------------------------------------------------- policy eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    {"name": "the STDM monopoly", "start": "1999-12-20", "end": "2002-02-07",
     "regime": "one concessionaire held every table in the territory under a monopoly running "
               "since 1962; the SAR was established on 1999-12-20 and inherited it",
     "markers": ("1999-12-20 the establishment of the Macau SAR",),
     "why_it_matters": "there is no competitive supply here at all, so a capacity or "
                       "allocation mechanism cannot exist and a study that pools this era into "
                       "the modern one is averaging a monopoly with a six-firm market",
     "status": "SETTLED"},
    {"name": "liberalisation and the Individual Visit Scheme boom",
     "start": "2002-02-08", "end": "2014-05-31",
     "regime": "three concessions and three sub-concessions replaced the monopoly; the "
               "Individual Visit Scheme opened mainland travel from 2003 and the junket-funded "
               "VIP channel drove revenue to a peak nobody has matched since",
     "markers": ("2002-02-08 the concessions awarded", "2003 the Individual Visit Scheme",
                 "2013 the revenue peak and 235 licensed promoters"),
     "why_it_matters": "the VIP share was the majority of revenue here and is a minority now; "
                       "any elasticity fitted on this era is fitted on a different business",
     "status": "SETTLED"},
    {"name": "the anti-corruption decline", "start": "2014-06-01", "end": "2016-08-31",
     "regime": "twenty-six consecutive months of year-on-year decline while the mainland "
               "anti-corruption campaign ran and the card and cash channels were tightened; "
               "the single cleanest natural experiment in the whole series",
     "markers": ("2014-06 the first year-on-year decline",
                 "2016-08 the last month of the run"),
     "why_it_matters": "THIS IS THE ERA THAT EARNS THE PACK. It is where the GGR-as-policy-proxy "
                       "claim comes from, and it is the window MO-J must reproduce before the "
                       "claim is anything more than a story",
     "status": "SETTLED"},
    {"name": "the recovery and the bridge", "start": "2016-09-01", "end": "2020-01-31",
     "regime": "revenue recovered without the VIP channel returning to its old share; the "
                "Hong Kong-Zhuhai-Macau Bridge opened on 2018-10-24 and added a capacity step "
                "that a pooled arrivals study reads as demand",
     "markers": ("2018-10-24 the bridge opens",),
     "why_it_matters": "the capacity step must be modelled; arrivals and revenue diverge here "
                       "because a new gate is throughput, not customers",
     "status": "SETTLED"},
    {"name": "the border closure", "start": "2020-02-01", "end": "2022-12-31",
     "regime": "the gates effectively shut, revenue fell to a fraction of its former level, the "
               "fiscal reserve was drawn on, Alvin Chau was arrested on 2021-11-27, the Hengqin "
               "Cooperation Zone was established on 2021-09-05, the Qingmao checkpoint opened "
               "on 2021-09-08 and Law 7/2022 banned the junket revenue-share model",
     "markers": ("2020-02 the closure", "2021-09-05 Hengqin", "2021-11-27 the prosecution",
                 "2022-06 Law 7/2022"),
     "why_it_matters": "THE BUILT-IN PLACEBO for MO-J: revenue collapsed here for a reason that "
                       "was not mainland enforcement at all, so a policy proxy that fires in "
                       "this window is measuring closure and calling it policy",
     "status": "SETTLED"},
    {"name": "the ten-year concessions and the non-gaming pivot",
     "start": "2023-01-01", "end": "2032-12-31",
     "regime": "six ten-year concessions with dated non-gaming investment commitments, a mass "
               "market carrying the revenue, a junket channel reduced to a few dozen licensees "
               "and a diversification target measured against Hengqin",
     "markers": ("2023-01-01 the concessions take effect",
                 "2023 the reopening of the gates and the arrivals recovery"),
     "why_it_matters": "the current regime, and the only one whose data the desk can actually "
                       "trade; it is three years long, which bounds every cell fitted inside it",
     "status": "OPEN"},
)

ACCESS_CONSTRAINTS: tuple[dict[str, Any], ...] = (
    {"constraint": "the pataca is not quoted by this broker",
     "measured": "data/universe/universe.json holds no MOP symbol",
     "consequence": "every domestic mechanism terminates in USDHKD, EURHKD, HKDJPY, the Hong "
                    "Kong indices, USDCNH or gold; MOP is an INPUT, never a cell"},
    {"constraint": "MACAU HAS NO SECURITIES EXCHANGE AT ALL",
     "measured": "MOX lists bonds and publishes no tape; the announced yuan-denominated "
                 "exchange has not launched",
     "consequence": "there is no domestic order book, no expiry clock, no short interest and no "
                    "retail margin series; the generic expiry and positioning miners correctly "
                    "report UNMEASURED and the equity leg is another jurisdiction's index"},
    {"constraint": "the gaming operators are single names",
     "measured": "every concessionaire is listed in Hong Kong or New York",
     "consequence": "EVENT LANE ONLY under the two-lane order (2026-09-06). They appear as "
                    "actors and observables and never as an executable instrument, a domain "
                    "instrument or an edge target"},
    {"constraint": "the DICJ current-year revenue table overwrites in place",
     "measured": "the page shows the year to date and keeps no first-print vintage",
     "consequence": "the as-published value of a given month is recoverable only from a daily "
                    "crawl or the archive layer's snapshot; an MO-A cell compiled on an "
                    "un-archived month is UNMEASURED rather than assumed"},
    {"constraint": "the only consensus for a Macau print is paywalled or edited in place",
     "measured": "terminal consensus is LICENSED (machine_use_allowed=false) and the free "
                 "mid-month run-rate notes are edited rather than versioned",
     "consequence": "an MO-A surprise is a HYPOTHESIS until the archive layer backs the "
                    "expectation it was measured against; the dataset row is pit_feasible=false "
                    "and says so"},
    {"constraint": "there is no pataca positioning series anywhere",
     "measured": "no COT contract, no exchange future, no dealer survey",
     "consequence": "pataca positioning is UNMEASURED and is never proxied by the HKD or CNH "
                    "legs, which are positions in the currencies the pataca is pegged THROUGH"},
    {"constraint": "the DSEC arrivals series is published three weeks after its month",
     "measured": "a 22-day publication lag on the arrivals table",
     "consequence": "it NEVER conditions the same month's revenue print; treating it as a "
                    "leading series is a look-ahead and the pack refuses it by construction"},
    {"constraint": "twelve scheduled events a year, split across six eras",
     "measured": "one release a month and six dated policy eras since 1999",
     "consequence": "MO-A's usable sample inside the current regime is about thirty-six prints; "
                    "the pack reports POORLY_MEASURED rather than pooling eras that are not "
                    "exchangeable to manufacture events"},
)

INSTITUTIONAL_FLOW_SOURCES: tuple[str, ...] = (
    "AMCM monthly deposits by currency (the HKD share)",
    "DICJ quarterly VIP-versus-mass segment split",
    "DICJ annual junket promoter register",
    "DSF monthly gaming tax receipts",
    "DSEC arrivals by origin and by checkpoint",
    "AMCM quarterly electronic-payment and cross-border wallet statistics")

SERIES: dict[str, str] = {
    "MO_GGR": "DICJ:ggr_monthly", "MO_GGR_SEGMENT": "DICJ:ggr_by_segment",
    "MO_TABLES": "DICJ:table_count", "MO_PROMOTERS": "DICJ:promoter_register",
    "MO_ARRIVALS": "DSEC:visitor_arrivals", "MO_CROSSINGS": "PSP:border_crossings",
    "MO_OCCUPANCY": "DSEC:hotel_occupancy", "MO_CPI": "DSEC:cpi", "MO_GDP": "DSEC:gdp",
    "MO_DEPOSITS_HKD": "AMCM:deposits_hkd_share", "MO_RESERVE": "AMCM:fiscal_reserve",
    "MO_GAMING_TAX": "DSF:gaming_tax_receipts", "MO_HZMB": "HZMB:traffic",
    "MO_PEG_CHAIN": "computed:peg_chain(USDHKD)",
}

# --------------------------------------------------------------------------- the pack's miners
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    {"name": "mo_ggr_release_clock", "domain_ids": ("MO-A", "MO-H"), "kind": "event",
     "cadence_s": 86400.0, "steerable": False, "wired": False,
     "entry": "countries.mo.pack:mine_ggr_release_clock",
     "needs": ("HOLIDAYS_RULE", "first_working_day", "HK50, CHINAH, US500 H1 bars"),
     "notes": "twelve events a year, each dated to the first WORKING day, with the "
              "no-release first-working-day placebo built in"},
    {"name": "mo_peg_chain_state", "domain_ids": ("MO-B",), "kind": "macro",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.mo.pack:mine_peg_chain_state",
     "needs": ("USDHKD D1 bars", "peg_chain", "the AMCM deposit split"),
     "notes": "the double peg's implied USD/MOP corridor and the Hong Kong band position; the "
              "honest prior is that it finds nothing and the miner reports that as a result"},
    {"name": "mo_dual_calendar", "domain_ids": ("MO-H", "MO-N"), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.mo.pack:mine_dual_calendar",
     "needs": ("LUNAR_GENERAL", "catholic_movable", "FIXED_GENERAL", "HK50 H1 bars"),
     "notes": "the lunar half typed from the gazette, the Catholic half computed from Easter, "
              "and the Hong Kong calendar as the paired control"},
    {"name": "mo_regime_boundaries", "domain_ids": ("MO-E", "MO-K", "MO-J"), "kind": "event",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.mo.pack:mine_regime_boundaries",
     "needs": ("POLICY_ERAS", "CHINAH, HK50, USDCNH D1 bars"),
     "notes": "the dated junket, gaming-law and concession boundaries with the mass-segment "
              "control beside them"},
    {"name": "mo_transmission_seeds",
     "domain_ids": ("MO-C", "MO-D", "MO-F", "MO-G", "MO-I", "MO-L", "MO-M"),
     "kind": "transfer", "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.mo.pack:mine_transmission_seeds",
     "needs": ("TRANSMISSION_EDGES_SEED", "INTERACTIONS"),
     "notes": "the pack's map and its sibling interactions as HYPOTHESIS discoveries, "
              "deduplicated by the registry"},
)

MINER_DOMAINS: dict[str, tuple[str, ...]] = {
    "central_bank_surprise": ("MO-B",), "release_surprise": ("MO-A", "MO-C", "MO-G"),
    "calendar_settlement": ("MO-H", "MO-A"), "holiday_liquidity": ("MO-H", "MO-N"),
    "positioning": ("MO-B",), "carry_funding": ("MO-B",),
    "corporate_flow": ("MO-K", "MO-M"), "institutional_flow": ("MO-I", "MO-G"),
    "equity_mechanics": ("MO-N",), "derivatives_expiry": ("MO-N",),
    "failure": ("MO-E", "MO-J"), "residual": ("MO-L", "MO-G"),
    "transfer": ("MO-F", "MO-J"), "scouts": ("MO-D", "MO-I"),
    "session_microstructure": ("MO-N", "MO-A"),
}
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
        "jurisdictions": JURISDICTIONS,
        "executable_instruments": EXECUTABLE_INSTRUMENTS, "central_bank": CENTRAL_BANK,
        "fixing_conventions": FIXING_CONVENTIONS,
        "settlement_conventions": SETTLEMENT_CONVENTIONS, "exchanges": EXCHANGES,
        "release_classes": RELEASE_CLASSES, "session_windows": SESSION_WINDOWS,
        "holidays_rule": HOLIDAYS_RULE, "fiscal_year_end": FISCAL_YEAR_END,
        "positioning_sources": POSITIONING_SOURCES, "native_languages": NATIVE_LANGUAGES,
        "terminology": TERMINOLOGY, "source_classes": SOURCE_CLASSES,
        "source_layers": SOURCE_LAYERS, "layer_absences": LAYER_ABSENCES,
        "layer_terms": layer_terms(), "source_layer_coverage": source_layer_coverage(),
        "query_territories": QUERY_TERRITORIES,
        "datasets": DATASETS, "actors": ACTORS, "domains": DOMAINS,
        "cells": CELLS, "interactions": INTERACTIONS,
        "custom_miners": CUSTOM_MINERS, "miner_domains": MINER_DOMAINS,
        "transmission_edges_seed": TRANSMISSION_EDGES_SEED, "policy_eras": POLICY_ERAS,
        "transmission_targets": TRANSMISSION_TARGETS, "access_constraints": ACCESS_CONSTRAINTS,
        "region_desk": REGION_DESK, "forest": FOREST, "cot_currency": COT_CURRENCY,
        "export_economy": EXPORT_ECONOMY, "retail_leverage_regime": RETAIL_LEVERAGE_REGIME,
        "institutional_flow_sources": INSTITUTIONAL_FLOW_SOURCES, "series": SERIES,
        "mission": MISSION, "peg_chain": peg_chain(7.8000),
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
            "fixed_md": tuple(f"{m:02d}-{d:02d}" for m, d, _ in FIXED_GENERAL),
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


# --------------------------------------------------------------- the department's own miners
#: Every `CUSTOM_MINERS` entry points at one of these. They are PURE PYTHON -- no network, no
#: LLM, no heavy import -- and they read only this pack's own tables, so `mine()` can run them
#: inside any budget and a test can call them with no fixtures at all.
def mine_ggr_release_clock(pack_obj: Any = None, ctx: Any = None) -> dict[str, Any]:
    """MO-A / MO-H: the twelve first-working-day release dates a year, and how far each one was
    pushed out by the dual calendar. The push-out IS the placebo: a first working day that is
    also the 1st is a different object from one four days in."""
    rows: list[dict[str, Any]] = []
    for year in HOLIDAYS_RULE["years"]:
        for day in ggr_release_days(int(year)):
            rows.append({"date": day.isoformat(), "month": day.month,
                         "pushed_out_days": day.day - 1,
                         "weekday": day.weekday(),
                         "symbols": ("HK50", "CHINAH", "US500"),
                         "window_utc": ("04:30", "06:00")})
    return {"miner": "mo_ggr_release_clock", "domain_ids": ("MO-A", "MO-H"), "rows": tuple(rows),
            "n": len(rows),
            "control": "the same window on first working days in months with no release"}


def mine_peg_chain_state(pack_obj: Any = None, ctx: Any = None) -> dict[str, Any]:
    """MO-B: the double peg's arithmetic across the Hong Kong band, as the state buckets a cell
    would condition on. No data is fetched: the corridor is a function of the band, and the band
    belongs to the `hk` pack."""
    rows = [dict(peg_chain(x), bucket=f"hkd_{i}")
            for i, x in enumerate((7.7500, 7.7750, 7.8000, 7.8250, 7.8500))]
    return {"miner": "mo_peg_chain_state", "domain_ids": ("MO-B",), "rows": tuple(rows),
            "n": len(rows), "symbols": ("USDHKD", "EURHKD", "HKDJPY"),
            "prior": "the honest prior is NO Macau information in a bounded price two links "
                     "away; a positive result here would be the surprise",
            "control": "the `hk` pack's own band study over the identical window"}


def mine_dual_calendar(pack_obj: Any = None, ctx: Any = None) -> dict[str, Any]:
    """MO-H / MO-N: the two religious calendars side by side, with each closure tagged by which
    calendar produced it and whether it cost a weekday session."""
    rows: list[dict[str, Any]] = []
    for year in HOLIDAYS_RULE["years"]:
        y = int(year)
        catholic = {d.isoformat() for d in catholic_movable(y)}
        lunar = {d.isoformat() for d, _n, _s in LUNAR_GENERAL.get(y, ())}
        for day, name in national_holidays(y).items():
            iso = day.isoformat()
            kind = ("catholic_computed" if iso in catholic else
                    "lunar_gazetted" if iso in lunar else "fixed_solar")
            rows.append({"date": iso, "name": name, "calendar": kind,
                         "costs_a_session": day.weekday() < 5})
    return {"miner": "mo_dual_calendar", "domain_ids": ("MO-H", "MO-N"), "rows": tuple(rows),
            "n": len(rows), "symbols": ("HK50", "CHINAH", "USDHKD"),
            "control": "the Hong Kong calendar as the paired control -- Hong Kong substitutes a "
                       "weekend holiday and Macau does not"}


def mine_regime_boundaries(pack_obj: Any = None, ctx: Any = None) -> dict[str, Any]:
    """MO-E / MO-K / MO-J: the dated boundaries that make a pooled GGR study invalid, emitted as
    the era table a cell must be fitted inside."""
    rows = [{"era": str(e["name"]), "start": str(e["start"]), "end": str(e["end"]),
             "status": str(e["status"]), "markers": tuple(e["markers"]),
             "invalidates": str(e["why_it_matters"])} for e in POLICY_ERAS]
    return {"miner": "mo_regime_boundaries", "domain_ids": ("MO-E", "MO-K", "MO-J"),
            "rows": tuple(rows), "n": len(rows), "symbols": ("CHINAH", "HK50", "USDCNH"),
            "control": "the mass-segment series over the same quarters; the 2020-22 closure as "
                       "the built-in placebo where a policy proxy must NOT fire"}


def mine_transmission_seeds(pack_obj: Any = None, ctx: Any = None) -> dict[str, Any]:
    """The pack's own map and its sibling interactions, as HYPOTHESIS rows the registry
    deduplicates. Nothing here is a measurement and every row says so."""
    rows = [{"id": str(e["id"]), "targets": tuple(e["targets"]), "evidence": str(e["evidence"]),
             "falsifier": str(e["falsifier"]), "control": str(e["control"])}
            for e in TRANSMISSION_EDGES_SEED]
    rows += [{"id": f"MO-X:{r['with']}", "targets": tuple(r["targets"]),
              "evidence": "HYPOTHESIS", "falsifier": str(r["control"]),
              "control": str(r["control"])} for r in INTERACTIONS]
    return {"miner": "mo_transmission_seeds",
            "domain_ids": ("MO-C", "MO-D", "MO-F", "MO-G", "MO-I", "MO-L", "MO-M"),
            "rows": tuple(rows), "n": len(rows),
            "control": "every row is HYPOTHESIS until the gauntlet says otherwise"}


#: name -> callable, so the two registrations (CUSTOM_MINERS and this) are ONE set and a test
#: can assert it rather than trusting it.
MINERS: dict[str, Any] = {
    "mine_ggr_release_clock": mine_ggr_release_clock,
    "mine_peg_chain_state": mine_peg_chain_state,
    "mine_dual_calendar": mine_dual_calendar,
    "mine_regime_boundaries": mine_regime_boundaries,
    "mine_transmission_seeds": mine_transmission_seeds,
}


def mine(ctx: Any = None) -> dict[str, Any]:
    """THE DEPARTMENT ENTRY. Runs this pack's own miners over its own tables and returns the
    report; when a department Ctx is given it emits each row through `ctx.record` as well.

    Pure Python: no network, no LLM, no heavy import. `unmeasured` is a first-class part of the
    answer -- a thing this pack knows it cannot see is a measurement and never a blank (L1.28a).
    """
    rows: list[dict[str, Any]] = []
    for name, fn in MINERS.items():
        got = fn(None, ctx)
        rows.append({"miner": name, "n": int(got.get("n", 0)),
                     "domain_ids": tuple(got.get("domain_ids", ()))})
        record = getattr(ctx, "record", None) if ctx is not None else None
        if callable(record):
            record(got)
    unmeasured = [str(c["constraint"]) for c in ACCESS_CONSTRAINTS]
    return {"code": CODE, "at": datetime.now(tz=UTC).date().isoformat(), "emitted": len(rows),
            "cells_emitted": len(cells()), "rows": tuple(rows),
            "unmeasured": tuple(unmeasured),
            "layers": source_layer_coverage()["n_layers_covered"],
            "interactions": tuple(str(r["with"]) for r in INTERACTIONS),
            "note": "pure-python department pass over this pack's own tables; every row is a "
                    "HYPOTHESIS for the one gauntlet and nothing here is a measurement"}
