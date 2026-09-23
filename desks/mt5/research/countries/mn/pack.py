"""MONGOLIA: one customer, one border, and a copper ramp published years in advance.

WHY MONGOLIA EARNS A PACK AND IS NOT A ROW IN THE CHINA ONE. Four things belong to this economy
and to no other on the desk's book:

  1. A DATED, SANCTIONED, MULTI-YEAR COPPER SUPPLY CURVE FROM ONE MINE. Oyu Tolgoi's underground
     block cave reached sustainable production in 2023 and the operator's published guidance is
     an average of about 500 kt of copper a year across 2028-2036, against world mine supply of
     roughly 22 Mt. That is on the order of two per cent of world supply arriving on a schedule
     that is public YEARS in advance and reported QUARTERLY with grade and tonnage. Almost
     nothing else in the metals complex is a supply shock with a timetable attached, and
     `oyu_tolgoi_ramp` carries it as arithmetic rather than as a story.

  2. A DAILY, PUBLIC, PHYSICAL BORDER-FLOW SERIES WITH A DIRECT PRICE CONSEQUENCE. Mongolia is
     China's largest supplier of imported coking coal and it arrives BY LAND: the
     Gashuunsukhait-Ganqimaodu crossing is reported in TRUCKS PER DAY, publicly, daily, and the
     Shiveekhuren-Ceke and Zamyn-Uud-Erenhot crossings beside it. When that border shut in
     2020-2022 Chinese coking coal prices moved measurably, and when it reopened the count went
     to records. The Tavantolgoi-Gashuunsukhait railway, built and opened across 2022-2024, is a
     DATED CAPACITY STEP in the same series -- which is the control that separates "more coal was
     wanted" from "more coal could physically move".

  3. THE ONE-CUSTOMER STRUCTURE MAKES THE FLOW MEASURABLE TWICE. About nine tenths of Mongolian
     exports go to China, and the Chinese customs administration publishes imports BY ORIGIN
     every month. So the desk can difference two independent public measurements of the same
     physical flow: Mongolian customs exports by destination against Chinese customs imports by
     origin. The wedge between them is itself an observable (valuation, timing, transit stock and
     under-invoicing all live in it), and no amount of narrative can produce it.

  4. A CALENDAR THAT IS NOT CHINA'S AND MUST NOT BE BORROWED FROM IT. Tsagaan Sar is the largest
     closure of the Mongolian year and it follows the MONGOLIAN lunar calendar, computed from the
     Kalachakra tradition by the astrologers of Gandantegchinlen Monastery and fixed each year by
     government resolution. It can differ from the Chinese lunar new year by up to a month: in
     2024 the two fell on the SAME DAY and in 2025 Tsagaan Sar fell THIRTY-ONE DAYS LATER. A
     study that reuses a Chinese holiday table for Mongolia mislabels the one week the border
     trade genuinely stops. `tsagaan_sar_gap` measures that offset instead of assuming it, and
     Naadam (11-15 July) is fixed by statute and shuts the country for five days.

WHAT IS EXECUTABLE AND WHAT IS NOT. The TUGRIK (MNT) is ABSENT from `data/universe/universe.json`
and is carried in `TRANSMISSION_TARGETS` with its managed-float regime, the Bank of Mongolia's FX
auctions, the PBoC swap line and its routes into USDCNH, USDRUB and XAUUSD. COKING COAL is not a
broker symbol: it is routed through the Chinese steel complex (CHINAH), through the offshore
renminbi that invoices it (USDCNH) and through AUDUSD, because Australian seaborne coking coal is
the marginal substitute for the buyer at the other end of the border -- that leg belongs to the
`au` pack and is named as the CONTROL, never re-derived here. CASHMERE is not a broker symbol
either and is routed through USDCNH, because China buys and dehairs the overwhelming majority of
Mongolian raw fibre. Mongolian Mining Corporation and the other listed miners are SINGLE NAMES:
under the two-lane order (2026-09-06) they are EVENT LANE ONLY and appear here as actors and
observables, never as an executable instrument, a domain instrument or an edge target.

NATIVE GROUND IS MONGOLIAN CYRILLIC AND THE PACK MEANS IT. The Bank of Mongolia's bulletins, the
National Statistics Office tables, the customs releases, the MRPAM licence register, legalinfo.mn
and the whole Ulaanbaatar press are written in Cyrillic; an English-only crawl reads the four
English-language summaries a ministry publishes and reports that corner as the ground. And
TRADITIONAL MONGOLIAN SCRIPT (U+1800..U+18AF) is a LIVE CRAWLING FACT rather than a curiosity:
under the national script programme, official state documents carry the traditional script
alongside Cyrillic from 2025, so a crawler that cannot see those codepoints will progressively
miss the gazetted half of new documents.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime
from typing import Any

# ruff: noqa: RUF001, RUF002, RUF003
# RUF001/2/3 flag Cyrillic characters that look like Latin ones. They exist to catch homoglyph
# attacks in IDENTIFIERS. This file carries Mongolian Cyrillic terminology as DATA, because a
# crawler that cannot match "нүүрсний экспорт" or "Гашуунсухайт боомт" cannot find the customs
# release it is looking for, and the glosses beside those terms are deliberately bilingual so a
# human reading the pack knows what each series is. Suppressed file-wide and explained here
# rather than scattered as per-line noqa; no identifier in this module is non-ASCII.

# --------------------------------------------------------------------------- identity
CODE = "MN"
NAME = "Mongolia"
#: THE PARITY FENCE COUNTS THIS (`scripts/check_regional_parity.py::jurisdictions_of`). Declared
#: even though the directory name would imply it, because an implied claim is not a measurement.
JURISDICTIONS: tuple[str, ...] = ("mn",)
REGION_COMMAND = "asia"
REGION_DESK = "NORTH_ASIA_STEPPE"
FOREST = "china"
CURRENCY = "MNT"
FISCAL_YEAR_END = "12-31"          # the Budget Law runs the calendar year
#: FIVE LANGUAGES AND THE PACK MEANS ALL FIVE. Mongolian Cyrillic is the working language of the
#: state and the press; TRADITIONAL MONGOLIAN SCRIPT joins official documents from 2025; Chinese
#: is the language of the MIRROR customs series and of the Ganqimaodu trade; Russian is the
#: language of the fuel supply and the railway joint venture; English reaches the operator's own
#: quarterly production reports and the IMF and World Bank programme documents.
NATIVE_LANGUAGES: tuple[str, ...] = ("mn", "mn-Mong", "zh", "ru", "en")
COT_CURRENCY = ""                  # no CFTC contract exists for the tugrik and none ever will
EXPORT_ECONOMY = "commodity_exporter"           # copper, coking coal, gold, fluorspar, cashmere
RETAIL_LEVERAGE_REGIME = "UNMEASURED"           # no domestic margin-FX industry, no statistics
MISSION = ("mine Mongolia as the single-customer resource border it is: Oyu Tolgoi's published "
           "underground copper ramp against XCUUSD, the Gashuunsukhait truck-per-day coking "
           "coal series and the Tavantolgoi railway step against the Chinese steel complex, the "
           "mirror of Mongolian customs against Chinese customs by origin, the Bank of "
           "Mongolia's managed float, FX auctions, swap line and domestic gold purchases, the "
           "dzud-to-cashmere livestock shock, the sovereign refinancing calendar, and the "
           "MONGOLIAN lunar calendar that is not the Chinese one")

#: The instruments this pack may compile a cell against. Every one is in the broker registry and
#: none is a single-name equity. The tugrik is absent (see TRANSMISSION_TARGETS), and the listed
#: Mongolian miners are EVENT LANE and appear nowhere in this tuple.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "XCUUSD",                                  # Oyu Tolgoi's own contract
    "XAUUSD",                                  # the Bank of Mongolia's gold purchase programme
    "XZNUSD", "XALUSD",                        # the rest of the industrial-metals basket
    "USDCNH",                                  # the currency that invoices the border trade
    "USDRUB",                                  # the fuel and rail dependency to the north
    "HK50", "CHINAH",                          # the listing venue and the Chinese steel complex
    "XBRUSD", "XNGUSD",                        # the imported-energy and diesel-cost leg
    "AUDUSD",                                  # THE CONTROL: the seaborne coking-coal substitute
)

TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "MNT (the tugrik) -- USD/MNT and CNY/MNT",
     "venue": "the Bank of Mongolia's FX auctions and the interbank market in Ulaanbaatar",
     "why": "A MANAGED FLOAT WITH AN AUCTION, NOT A BAND AND NOT A FREE FLOAT. The Bank of "
            "Mongolia publishes a daily official reference rate, runs announced spot and swap "
            "auctions whose results are published, and holds a renminbi swap line with the "
            "PBoC that has been renewed repeatedly since 2011. The tugrik is not quoted by this "
            "broker and never will be, so every domestic monetary mechanism is routed into the "
            "currency that actually invoices the export trade (USDCNH), the currency of the "
            "fuel import (USDRUB) and the reserve asset the central bank buys at home (XAUUSD)",
     "proxies": ("USDCNH", "USDRUB", "XAUUSD")},
    {"name": "Coking (metallurgical) coal -- the export that pays for the country",
     "venue": "the Gashuunsukhait-Ganqimaodu and Shiveekhuren-Ceke land crossings, the Erdenes "
              "Tavan Tolgoi price announcements, and the Dalian Commodity Exchange contract the "
              "buyer marks against",
     "why": "NO BROKER SYMBOL EXISTS FOR COKING COAL AND THE PACK SAYS SO RATHER THAN PRETENDING "
            "OTHERWISE. The flow is routed three ways, each with its control named: through "
            "CHINAH because the buyer is the Chinese steel complex and the coal is an input "
            "cost inside it; through USDCNH because the trade is invoiced and settled in "
            "renminbi at the border; and through AUDUSD because AUSTRALIAN SEABORNE COKING COAL "
            "IS THE MARGINAL SUBSTITUTE for the same buyer -- that leg belongs to the `au` pack "
            "and is read here as the CONTROL that separates a Mongolian supply event from a "
            "global steel-demand event, never re-derived",
     "proxies": ("CHINAH", "USDCNH", "AUDUSD")},
    {"name": "Raw cashmere and wool -- the herder economy's cash crop",
     "venue": "the Mongolian Agricultural Commodity Exchange (all raw cashmere must be traded "
              "through it by statute) and the Chinese dehairing and spinning mills",
     "why": "NOT A BROKER SYMBOL. Mongolia is the second-largest raw cashmere producer in the "
            "world and China buys and dehairs the overwhelming majority of it, so the fibre is "
            "routed through USDCNH with the Chinese apparel cycle as the demand control. The "
            "broker's only fibre contract is COTTON, and it is named here as a SUBSTITUTE-FIBRE "
            "CONTROL rather than as cashmere's carrier: a vegetable fibre with a different "
            "growing season and a different demand cycle is a placebo, not a proxy, and calling "
            "it a proxy would be the failure this field exists to prevent",
     "proxies": ("USDCNH", "AUDUSD")},
    {"name": "The listed Mongolian miners (Hong Kong and MSE listings)",
     "venue": "HKEX and the Mongolian Stock Exchange",
     "why": "EVENT LANE ONLY under the two-lane order (2026-09-06). Mongolian Mining "
            "Corporation and the coal and copper names listed in Hong Kong are single names and "
            "may never mint a statistical hypothesis here; their index membership is what makes "
            "HK50 and CHINAH the carriers, and the MSE names have no tradable derivative at all",
     "proxies": ("HK50", "CHINAH", "XCUUSD")},
    {"name": "The Mongolian sovereign eurobond curve and the refinancing calendar",
     "venue": "the offshore USD and CNY bond market (the Chinggis, Gerege, Mazaalai and "
              "successor issues) and the Development Bank of Mongolia's paper",
     "why": "A FRONTIER HARD-CURRENCY CURVE WITH NO CFD AND NO PUBLIC INTRADAY PRICE. The "
            "2023-2024 liability-management and refinancing exercises are DATED EVENTS with a "
            "known cash cost, and the thing that services them is the export receipt -- so the "
            "executable legs are the commodities that generate the receipt and the offshore "
            "renminbi that carries frontier-Asia funding tone, with the bond price itself "
            "recorded as UNMEASURED rather than proxied",
     "proxies": ("XCUUSD", "USDCNH", "AUDUSD")},
    {"name": "Fluorspar, uranium, rare earths and the rest of the strategic basket",
     "venue": "the MRPAM licence register and the bilateral offtake agreements",
     "why": "Mongolia is a top-three fluorspar producer, holds large uranium deposits under a "
            "French development agreement, and is repeatedly named as a non-Chinese rare-earth "
            "source in policy documents. NONE of these has a broker instrument. They are routed "
            "into the industrial-metals complex the desk CAN trade, with the explicit warning "
            "that a fluorspar or uranium headline moving XALUSD or XZNUSD is a sentiment "
            "channel and not a physical one until the mirror customs series says otherwise",
     "proxies": ("XALUSD", "XZNUSD", "XCUUSD")},
)

# --------------------------------------------------------------------------- the central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "Mongolbank / Монголбанк (the Bank of Mongolia)",
    "short": "BoM",
    "framework": "managed_float",
    "committee": "the Monetary Policy Committee of the Bank of Mongolia, chaired by the Governor",
    "policy_instrument": "the policy rate (бодлогын хүү), reserve requirements including a "
                         "separate ratio on foreign-currency liabilities, announced spot and "
                         "swap FX auctions, and a domestic gold purchase programme that is a "
                         "monetary operation as much as a reserve one",
    "mandate": "price stability under the Law on the Central Bank, with financial stability and "
               "the stability of the tugrik's external value in practice",
    "decision_rule": "the Monetary Policy Committee publishes a resolution with its reasoning "
                     "after each meeting; the schedule is announced in advance in the Monetary "
                     "Policy Guidelines that the State Great Khural approves each year",
    "decision_calendar_rule": "DECLARED EMPTY RATHER THAN INVENTED. The Bank publishes its own "
                              "meeting schedule and this pack has not read a machine-readable "
                              "copy of it, so the generic central-bank miner reporting "
                              "UNMEASURED here is the correct answer (L1.28a). Typing a guessed "
                              "calendar would stamp every rate event to a wrong day and produce "
                              "a clean-looking null",
    "decision_dates": (),
    "dates_status": "UNMEASURED: the schedule exists and is published in Mongolian on "
                    "mongolbank.mn; until the crawler reads it, rate-decision cells are "
                    "UNMEASURED and no event study on this pack's rate dates may be promoted",
    "decision_time_utc": "",
    "announce_local": "the resolution and the Governor's statement are posted on mongolbank.mn, "
                      "in Mongolian first and in English later or not at all",
    "dst_rule": "Asia/Ulaanbaatar is UTC+8 all year. MONGOLIA ABOLISHED DAYLIGHT SAVING IN 2017 "
                "after several reversals, so a series that spans 2015-2017 carries a one-hour "
                "seam in the summer months and a naive local-to-UTC conversion is wrong there",
    "minutes_lag_days": 14,
    "publication_classes": ("мөнгөний бодлогын мэдэгдэл", "статистикийн эмхэтгэл",
                            "валютын дуудлага худалдааны үр дүн", "албан ханш",
                            "алт худалдан авалт", "жилийн тайлан"),
    "policy_rate_series": "BoM:policy_rate",
    "expected_rate_series": "UNMEASURED",
    "consensus_proxy": "there is no published survey of expectations for the Mongolian policy "
                       "rate; the nearest thing is the interbank rate and the commercial banks' "
                       "own deposit repricing, and the pack says so rather than inventing one",
    "consensus_proxy_trap": "a Mongolian rate move is very often a RESPONSE to a tugrik move "
                            "that has already happened, not news about the future; an event "
                            "study that treats the decision as the shock is measuring the "
                            "currency with a lag and calling it policy",
    "reserves_clock": "gross international reserves are published monthly and are the single "
                      "most watched Mongolian macro number, because the 2016 reserve drawdown "
                      "is what ended in an IMF programme; the reserve series and the monthly "
                      "domestic gold purchase series must be read together, since the second "
                      "adds to the first without any balance-of-payments inflow at all",
    "programme": "an IMF Extended Fund Facility ran from 2017 with a bilateral package around "
                 "it; the country has been out of programme since, and the refinancing of the "
                 "2020s eurobond maturities was done in the market",
    "off_cycle": (),
    "root": "https://www.mongolbank.mn",
}

# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "Bank of Mongolia daily official MNT reference rate (албан ханш)",
     "local": "published each business day in Ulaanbaatar for application the following day",
     "time_utc": "07:00", "dst_rule": "none (Asia/Ulaanbaatar is UTC+8 all year since 2017)",
     "instruments": ("USDCNH", "USDRUB"), "window_minutes": 120,
     "why": "the administered reference around which the interbank market trades. THE MINUTE IS "
            "APPROXIMATE AND THE WINDOW IS WIDE ON PURPOSE: the pack has measured the day but "
            "not the minute, and a two-hour window that contains the truth beats a false minute"},
    {"name": "Bank of Mongolia FX auction result announcement",
     "local": "auctions are announced in advance and the accepted amounts and rates are "
              "published the same day",
     "time_utc": "08:00", "dst_rule": "none", "instruments": ("USDCNH", "XAUUSD"),
     "window_minutes": 120,
     "why": "THE ONLY DIRECT READ ON OFFICIAL FX SUPPLY. The auction size relative to the "
            "monthly import bill is the intervention intensity variable, and it is public"},
    {"name": "Dalian Commodity Exchange coking coal and coke settlement",
     "local": "15:00 Asia/Shanghai", "time_utc": "07:00", "dst_rule": "none",
     "instruments": ("CHINAH", "USDCNH"), "window_minutes": 30,
     "why": "the price the Mongolian border trade is marked against. Mongolian mine-gate and "
            "border prices are negotiated at a discount to this curve, so a truck-count shock "
            "shows up here first and in the Mongolian fiscal accounts a quarter later"},
    {"name": "LME copper official settlement",
     "local": "12:30 Europe/London (second ring)", "time_utc": "12:30", "dst_rule": "GMT/BST",
     "instruments": ("XCUUSD", "XZNUSD", "XALUSD"), "window_minutes": 30,
     "why": "Oyu Tolgoi's concentrate is priced off this benchmark; the quarterly production "
            "report is therefore a supply-side event marked against a price the desk can trade"},
    {"name": "LBMA gold price PM auction",
     "local": "15:00 Europe/London", "time_utc": "15:00", "dst_rule": "GMT/BST",
     "instruments": ("XAUUSD",), "window_minutes": 15,
     "why": "the Bank of Mongolia buys domestic artisanal and mine gold against this fix; the "
            "monthly purchase tonnage is published and is a genuine, dated, official bid"},
    {"name": "PBoC CNY central parity",
     "local": "09:15 Asia/Shanghai", "time_utc": "01:15", "dst_rule": "none",
     "instruments": ("USDCNH",), "window_minutes": 30,
     "why": "the border trade is invoiced in renminbi, so the parity is the price of Mongolia's "
            "export receipt before any Mongolian institution has opened for the day"},
    {"name": "Bank of Russia official USD/RUB rate (the fuel import leg)",
     "local": "published each business day in Moscow", "time_utc": "12:30",
     "dst_rule": "none (Europe/Moscow has no daylight saving)",
     "instruments": ("USDRUB", "XBRUSD"), "window_minutes": 120,
     "why": "Mongolia imports the overwhelming majority of its refined fuel from Russia under "
            "annual intergovernmental quotas, so the rouble and Russian export policy are a "
            "direct input into Mongolian transport costs and therefore into mine-gate margins"},
    {"name": "Mongolian Stock Exchange continuous session close",
     "local": "13:00 Asia/Ulaanbaatar", "time_utc": "05:00", "dst_rule": "none",
     "instruments": ("HK50", "CHINAH"), "window_minutes": 30,
     "why": "declared for completeness. The MSE's turnover is small enough that its close is an "
            "information event about Mongolia and not a price the desk can trade; the executable "
            "equity legs are Hong Kong's, which is where the miners are actually listed"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "Mongolian Customs monthly foreign trade bulletin", "kind": "day_of_month",
     "days": (10, 11, 12, 13, 14, 15), "roll": "next", "window_utc": ("02:00", "06:00"),
     "instruments": ("XCUUSD", "CHINAH", "USDCNH"),
     "why": "exports by commodity and by destination; the Mongolian half of the mirror pair"},
    {"name": "National Statistics Office monthly socio-economic bulletin", "kind": "day_of_month",
     "days": (15, 16, 17, 18, 19, 20), "roll": "next", "window_utc": ("02:00", "06:00"),
     "instruments": ("USDCNH", "XCUUSD"),
     "why": "inflation, the herd count, industrial output, the budget and the trade balance in "
            "one release -- the widest single Mongolian macro print of the month"},
    {"name": "Bank of Mongolia monthly statistical bulletin and reserves", "kind": "day_of_month",
     "days": (20, 21, 22, 23, 24, 25), "roll": "next", "window_utc": ("02:00", "08:00"),
     "instruments": ("USDCNH", "XAUUSD"),
     "why": "reserves, money, the official rate history and the monthly gold purchase tonnage"},
    {"name": "Chinese customs detailed imports by origin (the MIRROR series)",
     "kind": "day_of_month", "days": (18, 19, 20, 21, 22, 23, 24, 25), "roll": "next",
     "window_utc": ("01:00", "04:00"), "instruments": ("CHINAH", "USDCNH", "XCUUSD"),
     "why": "THE OTHER HALF OF THE PAIR, and it is published by the buyer rather than the "
            "seller: coal and copper concentrate imports from Mongolia, by tonnage and value"},
    {"name": "Operator quarterly production and operations review (Oyu Tolgoi)",
     "kind": "quarter_end", "days": (), "roll": "next", "window_utc": ("06:00", "08:00"),
     "instruments": ("XCUUSD",),
     "why": "the block cave's tonnage, grade and guidance -- the dated supply curve's own print"},
    {"name": "The Naadam national closure block", "kind": "day_of_month",
     "days": (11, 12, 13, 14, 15), "roll": "next", "window_utc": ("00:00", "23:59"),
     "instruments": ("USDCNH", "CHINAH"),
     "why": "11-15 July by statute: the country, the customs posts and the exchange all stop, "
            "and the border queue that builds through it is the cleanest supply interruption "
            "in the Mongolian year because it is scheduled and has nothing to do with demand"},
    {"name": "The consolidated budget and the fiscal year", "kind": "fiscal_year_end",
     "days": (), "roll": "prior", "window_utc": ("02:00", "06:00"),
     "instruments": ("XCUUSD", "CHINAH"),
     "why": "mineral royalties and the Erdenes dividends dominate revenue, so the budget is a "
            "commodity-price derivative with a legislature attached"},
)

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Mongolian Stock Exchange (Монголын хөрөнгийн бирж, MSE)",
     "index_symbols": (),
     "open_local": "10:00", "close_local": "13:00", "open_utc": "02:00", "close_utc": "05:00",
     "dst_rule": "none (Asia/Ulaanbaatar is UTC+8 all year since 2017)",
     "auction": "an opening call followed by a short continuous session; there is no closing "
                "auction of the depth the desk's microstructure miners assume",
     "expiry_rule": "NO LISTED DERIVATIVES. There is no Mongolian futures or options market, so "
                    "there is no domestic expiry clock and the generic expiry miner correctly "
                    "reports UNMEASURED",
     "holidays": "the national public-holiday calendar, including the full Naadam block",
     "notes": "a real exchange with a real regulator and a TOP-20 index, and a market "
              "capitalisation and turnover small enough that a single state IPO changes its "
              "shape. It matters to this pack as an INFORMATION venue -- the 2024 New Recovery "
              "Policy mining-IPO programme is how the state monetises Tavan Tolgoi -- and never "
              "as an executable one"},
    {"name": "Mongolian Agricultural Commodity Exchange (Хөдөө аж ахуйн бирж, MACE)",
     "index_symbols": (),
     "open_local": "10:00", "close_local": "16:00", "open_utc": "02:00", "close_utc": "08:00",
     "dst_rule": "none",
     "auction": "auction trading in raw cashmere, wool, hides and grain",
     "expiry_rule": "spot and forward lots, no standardised financial contract",
     "holidays": "the national calendar; the cashmere season itself runs from the spring combing",
     "notes": "A STATUTORY CHOKE POINT AND THEREFORE A MEASUREMENT: raw cashmere and wool must "
              "be traded through this exchange, which makes its auction volumes a near-complete "
              "census of the fibre crop rather than a sample. That is the series a dzud shock "
              "eventually lands in, and it exists for no other country on this desk's book"},
    {"name": "HKEX as the listing venue for the Mongolian coal and copper names",
     "index_symbols": ("HK50", "CHINAH"),
     "open_local": "09:30 (pre-opening 09:00)", "close_local": "16:00",
     "open_utc": "01:30", "close_utc": "08:00", "dst_rule": "none (Asia/Hong_Kong is UTC+8)",
     "auction": "opening auction 09:00-09:30, lunch 12:00-13:00, closing auction 16:00-16:10",
     "expiry_rule": "the HSI and HSCEI settlement rule belongs to the `hk` pack and is read "
                    "here, never re-derived",
     "holidays": "the Hong Kong calendar, which shares NOTHING with the Mongolian one except "
                 "the first of January -- Tsagaan Sar and Chinese New Year can be a month apart "
                 "and Naadam is a Mongolian statute, so the two closed sets are independent",
     "notes": "the executable equity carrier. Every Mongolian mechanism that reaches equity "
              "reaches it here, and the single names themselves stay in the event lane"},
    {"name": "Dalian Commodity Exchange as the price-setting venue for the export",
     "index_symbols": (),
     "open_local": "09:00-15:00 with a night session", "close_local": "15:00",
     "open_utc": "01:00", "close_utc": "07:00", "dst_rule": "none",
     "auction": "continuous, with a night session that opens at 21:00 Asia/Shanghai",
     "expiry_rule": "the coking coal and coke contracts settle on their own monthly cycle; the "
                    "mechanics belong to the `cn` pack",
     "holidays": "the Chinese calendar -- which is why a Chinese closure and a Mongolian closure "
                 "can strand a border queue on either side independently",
     "notes": "MONGOLIA'S BIGGEST EXPORT IS PRICED IN ANOTHER COUNTRY'S FUTURES MARKET. The "
              "contract is not executable on this desk, so the pack reads it as an observable "
              "and terminates its cells in CHINAH, USDCNH and AUDUSD"},
)

SESSION_WINDOWS: tuple[dict[str, Any], ...] = (
    {"name": "mn_border_morning", "start_utc": "00:00", "end_utc": "03:00",
     "notes": "08:00-11:00 Ulaanbaatar and Ganqimaodu: the morning truck surge at the coal "
              "crossings, and the hour the day's throughput is effectively decided"},
    {"name": "mn_release_window", "start_utc": "02:00", "end_utc": "06:00",
     "notes": "10:00-14:00 local: customs, the statistics office and the central bank publish "
              "inside this window, which overlaps the Chinese morning session"},
    {"name": "mn_china_afternoon", "start_utc": "05:00", "end_utc": "07:00",
     "notes": "the Dalian and Shanghai afternoon, where the coal and steel complex reprices a "
              "Mongolian border headline the same day"},
    {"name": "mn_london_metals", "start_utc": "11:30", "end_utc": "16:30",
     "notes": "the LME rings and the London afternoon: where an Oyu Tolgoi production number "
              "actually meets the copper price"},
    {"name": "mn_operator_report", "start_utc": "06:00", "end_utc": "08:00",
     "notes": "the operator's quarterly production report reaches the wires in the European "
              "morning; DECLARED FOR COMPLETENESS AND NEVER MINED FOR THE SINGLE NAME -- the "
              "two-lane order makes the listed parent event lane, and the executable leg is "
              "XCUUSD"},
)

RELEASE_CLASSES: tuple[dict[str, Any], ...] = (
    {"name": "Mongolian Customs monthly foreign trade (exports by commodity and destination)",
     "cadence": "monthly", "time_utc": "04:00", "source": "Гаалийн ерөнхий газар",
     "actual_series": "MNCUSTOMS:exports_by_commodity", "expected_series": "UNMEASURED",
     "notes": "coal tonnage, copper concentrate tonnage and value; the seller's half of the pair"},
    {"name": "Chinese customs imports by origin (coal and copper ore from Mongolia)",
     "cadence": "monthly", "time_utc": "02:00", "source": "中华人民共和国海关总署",
     "actual_series": "CNCUSTOMS:imports_from_mongolia", "expected_series": "UNMEASURED",
     "notes": "THE MIRROR. The buyer's own count of the same physical flow, on a different "
              "clock and a different valuation basis; the wedge is the observable"},
    {"name": "National Statistics Office monthly socio-economic bulletin",
     "cadence": "monthly", "time_utc": "04:00", "source": "Үндэсний статистикийн хороо",
     "actual_series": "NSO:monthly_bulletin", "expected_series": "UNMEASURED",
     "notes": "CPI, the herd census, industrial production, the budget balance and trade"},
    {"name": "Bank of Mongolia Monetary Policy Committee resolution",
     "cadence": "as scheduled (schedule published annually)", "time_utc": "UNMEASURED",
     "source": "Монголбанк", "actual_series": "BoM:policy_rate", "expected_series": "UNMEASURED",
     "notes": "the date is known to the Bank and not yet read by this pack; UNMEASURED by name"},
    {"name": "Bank of Mongolia monthly gold purchases (алт худалдан авалт)",
     "cadence": "monthly", "time_utc": "06:00", "source": "Монголбанк",
     "actual_series": "BoM:gold_purchases_kg", "expected_series": "n/a",
     "notes": "a dated official bid for physical gold, in kilogrammes, published by the buyer"},
    {"name": "Bank of Mongolia gross international reserves",
     "cadence": "monthly", "time_utc": "06:00", "source": "Монголбанк",
     "actual_series": "BoM:reserves_usd", "expected_series": "UNMEASURED",
     "notes": "the most watched Mongolian macro number; read WITH the gold purchases, because "
              "domestic gold adds to reserves with no balance-of-payments inflow behind it"},
    {"name": "Rio Tinto quarterly operations review (Oyu Tolgoi copper and gold)",
     "cadence": "quarterly", "time_utc": "06:30", "source": "the operator",
     "actual_series": "OT:quarterly_production", "expected_series": "sell-side consensus",
     "notes": "tonnage, grade, the underground ramp's progress and any guidance change; the one "
              "release on this pack's book that has a real published consensus beside it"},
    {"name": "Erdenes Tavan Tolgoi coal price announcement and auction result",
     "cadence": "irregular, announced", "time_utc": "UNMEASURED",
     "source": "Эрдэнэс Тавантолгой", "actual_series": "ETT:announced_price",
     "expected_series": "n/a",
     "notes": "a STATE SELLER that announces its own price rather than accepting a market one; "
              "the announcement is a policy event about supply, not a market clearing print"},
    {"name": "MRPAM production, licence and royalty statistics",
     "cadence": "monthly and quarterly", "time_utc": "UNMEASURED",
     "source": "Ашигт малтмал, газрын тосны газар", "actual_series": "MRPAM:production",
     "expected_series": "n/a",
     "notes": "extraction by mineral and the live state of the exploration and mining licence "
              "register -- the register is where resource-nationalism episodes become visible"},
    {"name": "Border crossing throughput (trucks per day, by crossing)",
     "cadence": "daily", "time_utc": "UNMEASURED", "source": "Гаалийн ерөнхий газар and the "
                                                             "border port authorities",
     "actual_series": "MN:border_trucks_per_day", "expected_series": "n/a",
     "notes": "THE ONLY DAILY PHYSICAL SERIES THIS PACK HAS, and the reason the coal mechanism "
              "is testable at all; published as a count, per crossing, by the state"},
    {"name": "Ministry of Finance monthly consolidated budget execution",
     "cadence": "monthly", "time_utc": "04:00", "source": "Сангийн яам",
     "actual_series": "MoF:budget_execution", "expected_series": "n/a",
     "notes": "mineral royalties and state-owned dividends dominate the revenue line, so this "
              "is the fiscal derivative of the coal and copper price with a one-quarter lag"},
    {"name": "Government resolution fixing the next year's public holidays",
     "cadence": "annual", "time_utc": "UNMEASURED", "source": "Засгийн газар",
     "actual_series": "GOV:holiday_resolution", "expected_series": "n/a",
     "notes": "THE AUTHORITY FOR TSAGAAN SAR'S DATE. The lunar computation is done by the "
              "astrologers of Gandantegchinlen Monastery and the Cabinet fixes it by "
              "resolution; until that resolution exists, a future Tsagaan Sar is PROJECTED"},
)

# --------------------------------------------------------------------------- holidays
#: THE SOLAR HALF -- statutory public holidays (нийтээр амрах өдөр) that recur on the same date
#: every year and are therefore COMPUTED rather than typed. The Naadam block is five days by
#: statute (11-15 July) and is the longest fixed closure of the Mongolian year.
FIXED_GENERAL: tuple[tuple[int, int, str], ...] = (
    (1, 1, "Шинэ жил / New Year's Day"),
    (3, 8, "Олон улсын эмэгтэйчүүдийн эрхийг хамгаалах өдөр / International Women's Day"),
    (6, 1, "Эх, үрсийн баяр / Mother and Child Day"),
    (7, 11, "Үндэсний их баяр наадам, 1 дэх өдөр / Naadam day 1"),
    (7, 12, "Үндэсний их баяр наадам, 2 дахь өдөр / Naadam day 2"),
    (7, 13, "Үндэсний их баяр наадам, 3 дахь өдөр / Naadam day 3"),
    (7, 14, "Үндэсний их баяр наадам, 4 дэх өдөр / Naadam day 4"),
    (7, 15, "Үндэсний их баяр наадам, 5 дахь өдөр / Naadam day 5"),
    (11, 26, "Улс тунхагласан өдөр / Republic Day"),
    (12, 29, "Тусгаар тогтнолоо сэргээсэн өдөр / Independence Restoration Day"),
)

#: THE LUNAR HALF -- TSAGAAN SAR AND CHINGGIS KHAAN'S BIRTHDAY, WHICH NO WEEKDAY RULE PRODUCES
#: AND WHICH THE CHINESE TABLE DOES NOT ANSWER. Tsagaan Sar is the first days of the first month
#: of the MONGOLIAN lunar calendar, computed in the Kalachakra tradition by the astrologers of
#: Gandantegchinlen Monastery and fixed each year by Cabinet resolution; Chinggis Khaan's
#: birthday is the first day of the first winter month of the same calendar. Rows are
#: (date, name, status). GAZETTED means the resolution for that year is known; PROJECTED means
#: the pack computed or inferred the date and the resolution has not been read.
LUNAR_GENERAL: dict[int, tuple[tuple[date, str, str], ...]] = {
    2024: ((date(2024, 2, 10), "Цагаан сар, шинийн нэгэн / Tsagaan Sar day 1", "GAZETTED"),
           (date(2024, 2, 11), "Цагаан сар, шинийн хоёр / Tsagaan Sar day 2", "GAZETTED"),
           (date(2024, 2, 12), "Цагаан сар, шинийн гурав / Tsagaan Sar day 3", "GAZETTED"),
           (date(2024, 11, 1), "Их Эзэн Чингис хааны төрсөн өдөр / Chinggis Khaan's birthday",
            "PROJECTED")),
    2025: ((date(2025, 3, 1), "Цагаан сар, шинийн нэгэн / Tsagaan Sar day 1", "GAZETTED"),
           (date(2025, 3, 2), "Цагаан сар, шинийн хоёр / Tsagaan Sar day 2", "GAZETTED"),
           (date(2025, 3, 3), "Цагаан сар, шинийн гурав / Tsagaan Sar day 3", "GAZETTED"),
           (date(2025, 11, 20), "Их Эзэн Чингис хааны төрсөн өдөр / Chinggis Khaan's birthday",
            "PROJECTED")),
    2026: ((date(2026, 2, 18), "Цагаан сар, шинийн нэгэн / Tsagaan Sar day 1", "PROJECTED"),
           (date(2026, 2, 19), "Цагаан сар, шинийн хоёр / Tsagaan Sar day 2", "PROJECTED"),
           (date(2026, 2, 20), "Цагаан сар, шинийн гурав / Tsagaan Sar day 3", "PROJECTED"),
           (date(2026, 11, 9), "Их Эзэн Чингис хааны төрсөн өдөр / Chinggis Khaan's birthday",
            "PROJECTED")),
}

#: CHINESE LUNAR NEW YEAR DAY ONE, for the ONE purpose of measuring how far Mongolia's own new
#: year sits from it. These belong to the `cn` pack and are read here, never re-derived: the
#: comparison is the mechanism, so the pack must hold both sides of it.
CHINESE_NEW_YEAR: dict[int, date] = {
    2024: date(2024, 2, 10), 2025: date(2025, 1, 29), 2026: date(2026, 2, 17),
}

#: One-off closures and dated clock facts that no recurring rule produces.
DECLARED_CLOSURES: dict[date, str] = {
    date(2024, 2, 10): "Tsagaan Sar day 1 fell on the SAME DAY as Chinese New Year in 2024 -- "
                       "the coincidence year, and the one year a borrowed Chinese table would "
                       "have been accidentally right",
    date(2025, 3, 1): "Tsagaan Sar day 1 fell THIRTY-ONE DAYS after Chinese New Year in 2025 -- "
                      "the divergence year, and the proof that the two calendars are not one",
    date(2024, 7, 11): "Naadam 2024 opened on a Thursday, so the statutory five-day block ran "
                       "into the weekend and the border queue built for nine days",
}

#: THE STATUS LABELS the holiday table may carry. GAZETTED means the Cabinet resolution for that
#: year is known; PROJECTED means the pack computed or inferred the lunar date and the resolution
#: has not been read. A cell compiled on a PROJECTED row is a hypothesis, never a promotion.
HOLIDAY_STATUSES: tuple[str, ...] = ("GAZETTED", "PROJECTED")


def national_holidays(year: int) -> dict[date, str]:
    """Mongolia's statutory public holidays for a year: the fixed solar dates, the gazetted or
    projected lunar dates, and the one-off declarations.

    NO WEEKEND SUBSTITUTION IS ASSUMED. The Government does move working days around a holiday
    block by resolution in some years, but that is a per-year administrative act and not a rule,
    so the pack records the statutory days and leaves the substitution to the year's resolution
    rather than inventing a general rule for it.
    """
    out: dict[str, str] = {}
    for m, d, name in FIXED_GENERAL:
        out[date(year, m, d).isoformat()] = name
    for day, name, status in LUNAR_GENERAL.get(year, ()):
        out[day.isoformat()] = f"{name} [{status}]"
    for day, name in DECLARED_CLOSURES.items():
        # APPENDED, NEVER OVERWRITTEN: a one-off note about a day the recurring rules already
        # produce is extra information about that closure, and replacing the name would delete
        # the festival a study is trying to align on.
        if day.year == year:
            prior = out.get(day.isoformat())
            out[day.isoformat()] = f"{prior} -- {name}" if prior else name
    return {date.fromisoformat(k): v for k, v in sorted(out.items())}


def market_holidays(year: int) -> dict[date, str]:
    """The closed days that cost a WEEKDAY. A Saturday or Sunday closure costs no exchange
    session and must not enter a holiday-liquidity sample as if it did -- though the BORDER is a
    different object, because the customs posts stop for the statutory day whichever day it is."""
    return {d: n for d, n in national_holidays(year).items() if d.weekday() < 5}


def is_market_holiday(day: date) -> bool:
    return day in market_holidays(day.year)


def gazetted_dates(year: int) -> dict[date, str]:
    """Only the lunar rows whose Cabinet resolution is known. A study that pools PROJECTED rows
    into a gazetted sample must say so."""
    return {d: n for d, n, st in LUNAR_GENERAL.get(year, ()) if st == "GAZETTED"}


def tsagaan_sar(year: int) -> date | None:
    """Day one of Tsagaan Sar, or None for a year the pack does not hold."""
    for day, name, _status in LUNAR_GENERAL.get(year, ()):
        if "шинийн нэгэн" in name:
            return day
    return None


def tsagaan_sar_gap(year: int) -> dict[str, Any]:
    """THE PACK'S DISTINGUISHING CALENDAR MEASUREMENT: how far Mongolia's new year sits from
    China's, in days, for a year the pack holds both sides of.

    This exists because the cheap thing to do is to reuse the Chinese lunar table for Mongolia,
    and the cheap thing is WRONG. Both calendars are lunisolar and both insert intercalary
    months, but they do not insert them in the same years: in 2024 the two new years fell on the
    SAME DAY and in 2025 Tsagaan Sar fell thirty-one days later. A borrowed table therefore
    mislabels the largest closure of the Mongolian year in some years and not in others, which
    is the worst possible failure mode -- it looks right often enough to be trusted.
    """
    mine = tsagaan_sar(year)
    theirs = CHINESE_NEW_YEAR.get(year)
    if mine is None or theirs is None:
        return {"year": year, "tsagaan_sar": None, "chinese_new_year": None,
                "gap_days": None, "coincides": None,
                "status": "UNMEASURED: the pack holds no table for this year"}
    gap = (mine - theirs).days
    status = next((st for d, n, st in LUNAR_GENERAL.get(year, ())
                   if d == mine and "шинийн нэгэн" in n), "PROJECTED")
    return {"year": year, "tsagaan_sar": mine.isoformat(), "chinese_new_year": theirs.isoformat(),
            "gap_days": gap, "coincides": gap == 0, "status": status,
            "why": "a borrowed Chinese holiday table is right when this is 0 and wrong by "
                   "`gap_days` when it is not; 2025 is the proof at 31 days"}


def naadam_block(year: int) -> tuple[date, ...]:
    """The statutory Naadam closure, 11-15 July, as dates. Fixed by law and therefore computed.

    It is the cleanest supply interruption in the Mongolian year for exactly the reason a
    researcher wants: it is SCHEDULED, it is the same five days every year, and it has nothing
    whatever to do with the demand for coal at the other end of the border.
    """
    return tuple(date(year, 7, d) for d in (11, 12, 13, 14, 15))


def in_naadam(day: date) -> bool:
    return day in naadam_block(day.year)


HOLIDAYS_RULE: dict[str, Any] = {
    "kind": "computed_solar_plus_gazetted_mongolian_lunar_table",
    "authority": "the Law on Public Holidays and Commemorative Days fixes the solar days; the "
                 "Cabinet of Mongolia (Засгийн газар) fixes the Tsagaan Sar and Chinggis Khaan "
                 "birthday dates each year by resolution, on the lunar computation of the "
                 "astrological institute of Gandantegchinlen Monastery (Гандантэгчэнлин хийд)",
    "rule": "TWO GENERATORS. (1) TEN FIXED SOLAR DAYS computed from the statute: 1 January, "
            "8 March, 1 June, the five-day Naadam block on 11-15 July, 26 November (Republic "
            "Day) and 29 December (Independence Restoration Day). (2) FOUR LUNAR DAYS that no "
            "weekday rule produces and that are TYPED with their status: the three days of "
            "Tsagaan Sar and Chinggis Khaan's birthday. TSAGAAN SAR IS NOT CHINESE NEW YEAR: "
            "the Mongolian lunisolar calendar inserts its intercalary months on its own "
            "schedule, so the two coincided in 2024 and fell thirty-one days apart in 2025 -- "
            "`tsagaan_sar_gap` measures the offset and a borrowed Chinese table is refused. "
            "NAADAM IS FIVE DAYS AND IS THE LONGEST FIXED CLOSURE, and because it is statutory "
            "and unrelated to demand it is the pack's built-in scheduled supply interruption. "
            "NO GENERAL WEEKEND SUBSTITUTION RULE IS CLAIMED: the Government moves working days "
            "around a block by resolution in some years and that is a per-year act, not a rule. "
            "THE CLOCK NEVER MOVES: Asia/Ulaanbaatar is UTC+8 all year since daylight saving "
            "was abolished in 2017, and a series spanning 2015-2017 carries a summer seam.",
    "years": (2024, 2025, 2026),
    "weekend": "Saturday and Sunday",
    "national_rule": "see `rule`; `national_holidays(year)` is the computed form",
    "market_rule": "the MSE follows the national calendar; the BORDER is a different object and "
                   "stops for the statutory day whichever weekday it falls on, which is why the "
                   "truck series and the exchange series need different holiday masks",
    "lunar_rule": "GAZETTED, not inferred: the Cabinet resolution for the year is the authority, "
                  "and a PROJECTED row is the pack's own computation awaiting that resolution",
    "cross_calendar": "the distinguishing calendar fact of this jurisdiction: the largest "
                      "closure of the Mongolian year is on a DIFFERENT lunar calendar from the "
                      "largest closure of its only customer's year, and the offset changes",
    "table": {y: {d.isoformat(): n for d, n in national_holidays(y).items()}
              for y in (2024, 2025, 2026)},
    "status": {2024: "GAZETTED for the Tsagaan Sar block; PROJECTED for Chinggis Khaan's "
                     "birthday until the resolution is read",
               2025: "GAZETTED for the Tsagaan Sar block; PROJECTED for Chinggis Khaan's "
                     "birthday until the resolution is read",
               2026: "PROJECTED throughout: the Cabinet resolution fixing 2026 has not been "
                     "read, so every lunar row that year is the pack's own computation"},
    "known_dates": {
        "2024-02-10": "Tsagaan Sar day 1 and Chinese New Year day 1 on the SAME date",
        "2025-03-01": "Tsagaan Sar day 1, thirty-one days after Chinese New Year 2025-01-29",
        "2025-07-11": "Naadam day 1, fixed by statute in every year",
        "2026-02-18": "Tsagaan Sar day 1 PROJECTED, one day after Chinese New Year 2026-02-17",
    },
    "fn": market_holidays,
    "national_fn": national_holidays,
    "gazetted_fn": gazetted_dates,
    "naadam_fn": naadam_block,
}

# ------------------------------------------------------------------- the copper ramp, as data
#: THE PUBLISHED OYU TOLGOI RAMP. Copper in thousands of tonnes a year, from the operator's own
#: public guidance: sustainable underground production from 2023, a rise through the second half
#: of the decade, and an average of about 500 kt/yr across 2028-2036 when the block cave and the
#: open pit are running together. Rows are (kt_of_copper, status).
#:
#: THE STATUS FIELD IS THE POINT. A number the operator has GUIDED is a different research object
#: from a number the pack interpolated between two guided ones, and a cell fitted on the second
#: is a cell fitted on this pack's arithmetic rather than on the mine's plan.
OT_RAMP: dict[int, tuple[float, str]] = {
    2023: (150.0, "REPORTED_RANGE"),     # first sustainable underground production year
    2024: (200.0, "REPORTED_RANGE"),
    2025: (300.0, "GUIDED_RANGE"),
    2026: (380.0, "INTERPOLATED"),
    2027: (450.0, "INTERPOLATED"),
    2028: (500.0, "GUIDED_AVERAGE"),     # the guided 2028-2036 average begins
    2029: (500.0, "GUIDED_AVERAGE"),
    2030: (500.0, "GUIDED_AVERAGE"),
}
#: World copper MINE supply, thousands of tonnes a year, order of magnitude only. The share this
#: pack computes is a SCALE, not a precision claim, and the field says so.
WORLD_MINE_SUPPLY_KT = 22_000.0


def oyu_tolgoi_ramp(year: int) -> dict[str, Any]:
    """THE DATED SUPPLY CURVE, AS ARITHMETIC. One year of the published Oyu Tolgoi ramp, with the
    share of world mine supply it represents and the status of the number behind it.

    A supply shock with a PUBLISHED TIMETABLE is a different object from a supply shock: the
    market has had the schedule for years, so the testable claim is never "production rose" but
    "production deviated from the schedule everybody already had", and this function exists so a
    cell can be conditioned on the deviation rather than on the level.
    """
    row = OT_RAMP.get(int(year))
    if row is None:
        return {"year": int(year), "copper_kt": None, "status": "UNMEASURED",
                "share_of_world_mine_supply": None,
                "why": "outside the published guidance horizon this pack holds"}
    kt, status = row
    return {"year": int(year), "copper_kt": kt, "status": status,
            "share_of_world_mine_supply": round(kt / WORLD_MINE_SUPPLY_KT, 5),
            "world_mine_supply_kt": WORLD_MINE_SUPPLY_KT,
            "why": "the schedule is public years in advance, so the tradable object is the "
                   "DEVIATION from it and never the level"}


# ------------------------------------------------------- the border, as a countable object
#: TRUCKS PER DAY AT GASHUUNSUKHAIT, as the regime buckets a cell conditions on. The pre-2020
#: normal was of the order of a thousand a day; the 2020-2022 closure cut it to a small fraction
#: of that; the post-reopening years set records well above the old normal, helped by the new
#: railway taking volume off the road. Each bucket is a STATE, not a forecast.
BORDER_BUCKETS: tuple[tuple[float, float, str], ...] = (
    (0.0, 200.0, "CLOSED_OR_NEAR_CLOSED"),
    (200.0, 600.0, "SEVERELY_RESTRICTED"),
    (600.0, 1100.0, "PRE_2020_NORMAL"),
    (1100.0, 1700.0, "POST_REOPENING_HIGH"),
    (1700.0, 100000.0, "RECORD"),
)
#: Net coal carried by one border truck, tonnes. The heavy combinations that run this route carry
#: far more than a highway lorry, and the number is an ORDER OF MAGNITUDE used to turn a count
#: into a tonnage -- which is the only reason a truck count is comparable to a customs table.
TONNES_PER_TRUCK = 75.0


def border_throughput_state(trucks_per_day: float) -> dict[str, Any]:
    """The Gashuunsukhait crossing's regime bucket for a given daily truck count, and the annual
    coal tonnage that count implies.

    THE CONVERSION IS WHY THIS FUNCTION EXISTS. A truck count and a customs tonnage are two
    measurements of one flow on different units and different clocks; putting the count on the
    tonnage's units is what lets the daily series be used as a NOWCAST of the monthly one, and
    it is also what exposes the error -- if the implied tonnage and the customs tonnage diverge
    persistently, either the trucks-per-truck assumption or the customs valuation is wrong, and
    that divergence is itself a measurement worth having.
    """
    n = max(0.0, float(trucks_per_day))
    bucket = "UNCLASSIFIED"
    for lo, hi, label in BORDER_BUCKETS:
        if lo <= n < hi:
            bucket = label
            break
    annual_mt = round(n * TONNES_PER_TRUCK * 365.0 / 1_000_000.0, 3)
    return {"trucks_per_day": n, "bucket": bucket, "tonnes_per_truck": TONNES_PER_TRUCK,
            "implied_annual_mt": annual_mt,
            "control": "the Shiveekhuren-Ceke crossing over the same days, which separates 'the "
                       "coal moved' from 'this crossing moved it', and the rail tonnage, which "
                       "separates a capacity step from a demand change",
            "why": "the daily count is a nowcast of a monthly customs tonnage; a persistent "
                   "divergence between the two is a measurement, not an error to be smoothed"}


# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "Bank of Mongolia FX auction announcements and results",
     "root": "https://www.mongolbank.mn/mn/p/74",
     "fields": ("auction_date", "instrument", "offered_amount", "accepted_amount",
                "accepted_rate", "swap_leg"),
     "frequency": "as announced, several times a month",
     "snapshot": "auction day", "publish_utc": "08:00", "lag_days": 0, "licence": "free, public",
     "available": True,
     "why": "THE CLOSEST THING MONGOLIA HAS TO AN OFFICIAL POSITIONING SERIES. The size the "
            "central bank offers and the size the market takes is a direct, dated read on "
            "official FX supply and on the private sector's demand for dollars",
     "pit_warning": "the announcement precedes the result by a day or two and the archive is "
                    "overwritten in place; without a daily crawl the as-announced size is lost"},
    {"name": "Bank of Mongolia gross international reserves and monthly gold purchases",
     "root": "https://www.mongolbank.mn/mn/p/113",
     "fields": ("gross_reserves_usd", "gold_purchased_kg", "gold_holdings",
                "reserve_months_of_import"),
     "frequency": "monthly", "snapshot": "month end", "publish_utc": "06:00", "lag_days": 25,
     "licence": "free, public", "available": True,
     "why": "the reserve number is the country's risk gauge and the gold purchase number is a "
            "real, dated, official bid for bullion; they must be read together because domestic "
            "gold raises reserves without any balance-of-payments inflow at all",
     "pit_warning": "revised; and the gold line is in kilogrammes of domestically purchased "
                    "metal, which is not the same object as the valuation change in reserves"},
    {"name": "Mongolian Stock Exchange trading and investor statistics",
     "root": "https://www.mse.mn/mn/statistics",
     "fields": ("turnover", "market_capitalisation", "foreign_share", "new_accounts",
                "top20_index"),
     "frequency": "daily and monthly", "snapshot": "session close", "publish_utc": "05:30",
     "lag_days": 0, "licence": "free, public", "available": True,
     "why": "the only domestic positioning-adjacent series that exists; the foreign share of "
            "turnover is the one line that connects the MSE to external risk appetite",
     "pit_warning": "turnover is small enough that a single block trade dominates a month; the "
                    "series is an information source about sentiment and never a flow proxy"},
    {"name": "a CFTC, exchange or dealer positioning series for the tugrik",
     "root": "", "fields": (), "frequency": "n/a", "snapshot": "", "publish_utc": "",
     "lag_days": 0, "licence": "", "available": False,
     "why": "DECLARED ABSENT: no tugrik future, forward or option trades on any exchange the "
            "desk can read, and no COT contract exists for MNT anywhere",
     "pit_warning": "DOES NOT EXIST: tugrik positioning is UNMEASURED and is never proxied by "
                    "the CNH or RUB legs, which are positions in other countries' currencies"},
    {"name": "a domestic derivatives, short-interest or retail-margin series",
     "root": "", "fields": (), "frequency": "n/a", "snapshot": "", "publish_utc": "",
     "lag_days": 0, "licence": "", "available": False,
     "why": "DECLARED ABSENT: Mongolia has no listed derivatives market, no securities lending "
            "of consequence and no published retail margin statistics; the Financial Regulatory "
            "Commission licenses brokers but publishes no leverage series",
     "pit_warning": "DOES NOT EXIST: there is no domestic expiry clock, no short interest and "
                    "no margin series, so the generic expiry and leverage miners report "
                    "UNMEASURED by name rather than substituting another country's"},
)

# --------------------------------------------------------------------------- terminology
#: MONGOLIAN CYRILLIC IS THE WORKING LANGUAGE AND THE PACK MEANS IT. The Bank of Mongolia's
#: bulletins, the statistics office tables, the customs releases, the MRPAM register, the legal
#: database and the entire Ulaanbaatar press are written in Cyrillic with the two Mongolian
#: letters Ө and Ү that no Russian keyboard has. TRADITIONAL MONGOLIAN SCRIPT is carried too,
#: because official documents take it alongside Cyrillic from 2025 and a crawler blind to
#: U+1800..U+18AF will progressively miss the gazetted half of new state documents.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "mining": ("уул уурхай", "ашигт малтмал", "олборлолт", "хүдэр", "агуулга",
               "зэсийн баяжмал", "далд уурхай", "баяжуулах үйлдвэр", "нөөц",
               "ил уурхай", "блок кейвинг"),
    "copper": ("зэс", "Оюу толгой", "Эрдэнэт", "зэсийн үнэ", "баяжмалын экспорт",
               "Рио Тинто", "Эрдэнэс Оюу толгой", "зэсийн олборлолт"),
    "coal": ("нүүрс", "коксжих нүүрс", "Таван толгой", "Эрдэнэс Тавантолгой",
             "нүүрсний экспорт", "нүүрсний үнэ", "уурхайн ам дахь үнэ", "эрчим хүчний нүүрс",
             "нүүрс тээвэрлэлт"),
    "border": ("хилийн боомт", "Гашуунсухайт", "Ганцмод", "Шивээхүрэн", "Замын-Үүд",
               "автотээврийн хэрэгсэл", "нэвтрүүлэх хүчин чадал", "ачаа тээвэр",
               "гааль", "гаалийн мэдүүлэг", "хилийн дамжуулалт", "боомтын ачаалал"),
    "railway": ("төмөр зам", "Тавантолгой-Гашуунсухайтын төмөр зам", "вагон", "ачилт",
                "төмөр замын тээвэр", "Улаанбаатар төмөр зам"),
    "monetary": ("Монголбанк", "бодлогын хүү", "төгрөг", "валютын ханш", "албан ханш",
                 "валютын дуудлага худалдаа", "инфляци", "гадаад валютын нөөц",
                 "алт худалдан авалт", "своп хэлцэл", "мөнгөний бодлого", "заавал байлгах нөөц"),
    "fiscal": ("төсөв", "нэгдсэн төсөв", "төсвийн орлого", "нөөц ашигласны төлбөр",
               "Сангийн яам", "Засгийн газрын бонд", "гадаад өр", "өрийн дарамт",
               "эргэн төлөлт", "Хөгжлийн банк"),
    "statistics": ("Үндэсний статистикийн хороо", "нийгэм, эдийн засгийн байдал",
                   "гадаад худалдаа", "худалдааны тэнцэл", "аж үйлдвэрийн үйлдвэрлэл",
                   "хэрэглээний үнийн индекс", "ажилгүйдэл"),
    "livestock": ("мал сүрэг", "зуд", "малын хорогдол", "ноолуур", "ноос", "малчин",
                  "отор", "өвөлжилт", "мал тооллого", "түүхий эдийн үнэ"),
    "exchange": ("Монголын хөрөнгийн бирж", "хувьцаа", "арилжаа", "ТОП-20 индекс",
                 "анхдагч зах зээл", "Хөдөө аж ахуйн бирж", "Санхүүгийн зохицуулах хороо"),
    "energy": ("шатахуун", "газрын тос", "дизель түлш", "эрчим хүч", "цахилгаан эрчим хүч",
               "шатахууны импорт", "түлш шатахууны хомсдол"),
    "legal": ("хууль", "Улсын Их Хурал", "Засгийн газрын тогтоол", "хөрөнгө оруулалтын гэрээ",
              "тусгай зөвшөөрөл", "Эрдэнэс Монгол", "Ашигт малтмал, газрын тосны газар",
              "Шинэ сэргэлтийн бодлого"),
    "calendar": ("Цагаан сар", "Наадам", "Үндэсний их баяр наадам", "нийтээр амрах өдөр",
                 "билгийн тооллын", "Их Эзэн Чингис хааны төрсөн өдөр", "шинийн нэгэн",
                 "Гандантэгчэнлин хийд"),
    "script": ("монгол бичиг", "кирилл үсэг", "үндэсний бичгийн хөтөлбөр",
               "ᠮᠣᠩᠭᠣᠯ ᠪᠢᠴᠢᠭ", "ᠮᠣᠩᠭᠣᠯ ᠤᠯᠤᠰ"),
    "market_talk": ("зах зээл", "хөрөнгө оруулагч", "эдийн засаг", "үнийн өсөлт",
                    "экспортын орлого", "гадаадын хөрөнгө оруулалт", "эрсдэл"),
}

# --------------------------------------------------------------------------- script detection
_CYRILLIC_RANGES = ((0x0400, 0x04FF), (0x0500, 0x052F), (0x2DE0, 0x2DFF), (0xA640, 0xA69F))
_MONGOLIAN_RANGES = ((0x1800, 0x18AF),)
#: The two letters that make a string MONGOLIAN Cyrillic rather than merely Cyrillic. A crawler
#: tuned on Russian will transliterate or drop them and then find nothing.
MONGOLIAN_LETTERS: tuple[str, ...] = ("ө", "Ө", "ү", "Ү")


def has_cyrillic(text: str) -> bool:
    """True when the text contains at least one Cyrillic codepoint."""
    return any(any(lo <= ord(ch) <= hi for lo, hi in _CYRILLIC_RANGES) for ch in str(text))


def has_mongolian_script(text: str) -> bool:
    """True when the text contains at least one TRADITIONAL Mongolian script codepoint
    (U+1800..U+18AF). Official documents carry the script alongside Cyrillic from 2025."""
    return any(any(lo <= ord(ch) <= hi for lo, hi in _MONGOLIAN_RANGES) for ch in str(text))


def cyrillic_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    rows = TERMINOLOGY if terminology is None else terminology
    return [t for terms in rows.values() for t in terms if has_cyrillic(t)]


def mongolian_script_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    rows = TERMINOLOGY if terminology is None else terminology
    return [t for terms in rows.values() for t in terms if has_mongolian_script(t)]


def mongolian_letter_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    """Terms carrying Ө or Ү -- the proof the glossary is Mongolian and not Russian."""
    rows = TERMINOLOGY if terminology is None else terminology
    return [t for terms in rows.values() for t in terms
            if any(ch in t for ch in MONGOLIAN_LETTERS)]


def term_count(terminology: Mapping[str, Iterable[str]] | None = None) -> int:
    rows = TERMINOLOGY if terminology is None else terminology
    return len({t for terms in rows.values() for t in terms})


def _seq(values: Iterable[Any]) -> tuple[str, ...]:
    return tuple(str(v) for v in values)


# --------------------------------------------------------------------------- source layers
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


def source_class(sid: str, label: str, *, layer: str, roots: Iterable[str],
                 queries: Iterable[str], languages: Iterable[str], access_label: str,
                 credibility: str, predictive_state: str, licence: str,
                 machine_use_allowed: bool = True, notes: str = "") -> dict[str, Any]:
    """One class of source with the roots a crawler starts from and its three INDEPENDENT
    labels. `queries` are native-script terms, never translations. `machine_use_allowed=True`
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
        "mn_mongolbank", "Монголбанк (the Bank of Mongolia): policy resolutions, the daily "
                         "official rate, FX auction announcements and results, monthly "
                         "statistics, reserves and the domestic gold purchase programme",
        layer="official",
        roots=("https://www.mongolbank.mn/mn", "https://www.mongolbank.mn/mn/p/74",
               "https://www.mongolbank.mn/mn/p/113", "https://www.mongolbank.mn"),
        queries=("бодлогын хүү шийдвэр", "валютын дуудлага худалдааны үр дүн", "албан ханш",
                 "гадаад валютын улсын нөөц", "алт худалдан авалт тонн",
                 "мөнгөний бодлогын мэдэгдэл", "статистикийн эмхэтгэл"),
        languages=("mn", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE MONETARY ROOT. The auction results and the monthly gold tonnage are the two "
              "series here that no other country on the desk's book has in the same shape: a "
              "central bank that publishes both its FX intervention size and its physical gold "
              "bid, monthly, in a currency nobody can trade"),
    source_class(
        "mn_nso", "Үндэсний статистикийн хороо (the National Statistics Office): the monthly "
                  "socio-economic bulletin, CPI, the herd census, industrial production, the "
                  "budget and the full 1212.mn statistical database",
        layer="official",
        roots=("https://www.nso.mn/mn", "https://www.1212.mn/mn", "https://www.nso.mn"),
        queries=("нийгэм, эдийн засгийн байдал", "хэрэглээний үнийн индекс", "мал тооллого",
                 "аж үйлдвэрийн үйлдвэрлэл", "гадаад худалдааны тойм", "статистик мэдээлэл"),
        languages=("mn", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="1212.mn is a genuine machine-readable statistical database with an API-shaped "
              "query interface, which is unusual for a frontier economy and is why this pack "
              "can carry a herd census as a research object rather than as a newspaper claim"),
    source_class(
        "mn_customs", "Гаалийн ерөнхий газар (the Customs General Administration): monthly "
                      "foreign trade by commodity and destination, and the border-crossing "
                      "throughput counts",
        layer="official",
        roots=("https://customs.gov.mn/", "https://customs.gov.mn/statistics",
               "https://gaali.mn/"),
        queries=("гадаад худалдааны статистик", "нүүрсний экспорт тонн", "боомтын мэдээ",
                 "хилийн боомтоор нэвтэрсэн тээврийн хэрэгсэл", "экспортын бүтээгдэхүүн",
                 "гаалийн статистик мэдээ"),
        languages=("mn", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE SELLER'S HALF OF THE MIRROR PAIR, and the publisher of the truck counts. The "
              "tables are posted as spreadsheets and overwritten by the next month, so a vintage "
              "of the first print exists only in a crawl taken that week or in the archive layer"),
    source_class(
        "mn_mrpam", "Ашигт малтмал, газрын тосны газар (MRPAM, the Mineral Resources and "
                    "Petroleum Authority): the exploration and mining licence register, "
                    "production by mineral, royalties and the cadastre map",
        layer="official",
        roots=("https://mrpam.gov.mn/", "https://mrpam.gov.mn/article/list/",
               "https://cmcs.mrpam.gov.mn/"),
        queries=("ашигт малтмалын тусгай зөвшөөрөл", "олборлолтын мэдээ", "кадастрын мэдээлэл",
                 "нөөц ашигласны төлбөр", "хайгуулын тусгай зөвшөөрөл"),
        languages=("mn", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the licence register is where RESOURCE NATIONALISM becomes visible before it "
              "becomes a headline: a moratorium on new licences, a revocation, a transfer to a "
              "state entity are all register events with dates on them"),
    source_class(
        "mn_legalinfo", "Хууль зүйн үндэсний төв: legalinfo.mn, the national legal database "
                        "carrying every law, Cabinet resolution and ministerial order, including "
                        "the annual public-holiday resolution and the minerals law amendments",
        layer="official",
        roots=("https://legalinfo.mn/", "https://legalinfo.mn/mn/detail",
               "https://www.parliament.mn/"),
        queries=("Ашигт малтмалын тухай хууль", "Засгийн газрын тогтоол нийтээр амрах өдөр",
                 "Төсвийн тухай хууль", "хөрөнгө оруулалтын гэрээ", "Улсын Их Хурлын тогтоол"),
        languages=("mn",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE LEGAL LAYER, AND IT IS READ IN CYRILLIC. The dated regime breaks this pack's "
              "era table depends on -- the investment agreement, the windfall-tax episodes, the "
              "licence moratoria, the holiday resolution -- are citable only from here"),
    source_class(
        "mn_minfin", "Сангийн яам (the Ministry of Finance): the consolidated budget, monthly "
                     "execution, the debt bulletin and the sovereign bond programme",
        layer="official",
        roots=("https://mof.gov.mn/", "https://iltod.gov.mn/", "https://mof.gov.mn/debt"),
        queries=("нэгдсэн төсвийн гүйцэтгэл", "Засгийн газрын өрийн мэдээлэл",
                 "гадаад зээлийн эргэн төлөлт", "төсвийн орлогын гүйцэтгэл",
                 "Засгийн газрын үнэт цаас"),
        languages=("mn", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the refinancing calendar lives here, and so does the fiscal transmission of the "
              "coal price: royalties and the Erdenes dividends are the revenue line that moves"),
    # ---- institutional
    source_class(
        "mn_mse", "Монголын хөрөнгийн бирж (the Mongolian Stock Exchange) and the Financial "
                  "Regulatory Commission: listings, the TOP-20 index, the IPO programme, "
                  "turnover and the broker register",
        layer="institutional",
        roots=("https://www.mse.mn/mn", "https://www.mse.mn/mn/statistics", "https://frc.mn/"),
        queries=("хөрөнгийн зах зээлийн мэдээ", "ТОП-20 индекс", "анхдагч зах зээлийн арилжаа",
                 "үнэт цаасны арилжаа", "Санхүүгийн зохицуулах хорооны шийдвэр"),
        languages=("mn", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="an exchange whose whole turnover is smaller than one Hong Kong block trade, which "
              "is exactly why it is an INFORMATION source and never an executable one here"),
    source_class(
        "mn_erdenes", "Эрдэнэс Монгол and Эрдэнэс Тавантолгой: the state mining holding and the "
                      "state coal seller -- announced prices, auction results, production "
                      "reports and the dividend and IPO programme",
        layer="institutional",
        roots=("https://erdenes.mn/", "https://www.ettjsc.mn/", "https://erdenesmongol.mn/"),
        queries=("нүүрсний үнэ зарлалаа", "Эрдэнэс Тавантолгой арилжаа", "хувьцаа эзэмшигч",
                 "олборлолт тээвэрлэлтийн мэдээ", "ногдол ашиг"),
        languages=("mn", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="A STATE SELLER THAT ANNOUNCES ITS OWN PRICE is a different research object from a "
              "market: the announcement is a policy act about supply, and treating it as a "
              "clearing price is the single easiest mistake to make in this pack"),
    source_class(
        "mn_banks_icsg", "The Mongolian commercial banks' research (Khan, Golomt, TDB, XacBank) "
                         "and the international commodity bodies (ICSG for copper, the "
                         "World Steel Association for the buyer's demand)",
        layer="institutional",
        roots=("https://www.khanbank.com/", "https://www.golomtbank.com/", "https://www.tdb.mn/",
               "https://icsg.org/"),
        queries=("эдийн засгийн тойм банк", "макро судалгаа", "зэсийн зах зээлийн тойм",
                 "copper market forecast ICSG", "банкны судалгааны тайлан"),
        languages=("mn", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the ICSG's monthly bulletin is the standing world-supply denominator this pack's "
              "`oyu_tolgoi_ramp` share is computed against, and the bank research is the only "
              "regular domestic macro commentary that is written to be read by professionals"),
    # ---- academic
    source_class(
        "mn_academia", "The National University of Mongolia, the Mongolian University of Science "
                       "and Technology, the Economic Research Institute and the Mongolian "
                       "journals, plus the open indices where their work is findable",
        layer="academic",
        roots=("https://num.edu.mn/", "https://www.must.edu.mn/", "https://openalex.org/",
               "https://core.ac.uk/"),
        queries=("Монголын эдийн засгийн судалгаа", "уул уурхайн салбарын судалгаа",
                 "төгрөгийн ханшийн судалгаа", "зудын нөлөөллийн судалгаа",
                 "Mongolia resource curse working paper"),
        languages=("mn", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="mixed; per-paper",
        notes="a small but real domestic literature, and a large EXTERNAL one -- Mongolia is a "
              "favourite case study for the resource-curse and Dutch-disease literatures, which "
              "means published, dated, testable claims about exactly this pack's mechanisms"),
    source_class(
        "mn_ifi", "The IMF Article IV and programme documents, the World Bank Mongolia Economic "
                  "Update, the ADB country diagnostics and the EITI reconciliation reports",
        layer="academic",
        roots=("https://www.imf.org/en/Countries/MNG", "https://www.worldbank.org/en/country/"
               "mongolia", "https://www.adb.org/countries/mongolia/main", "https://eiti.org/"
               "countries/mongolia"),
        queries=("IMF Article IV Mongolia", "Mongolia economic update", "ОУВС-ийн хөтөлбөр",
                 "олборлох үйлдвэрлэлийн ил тод байдал", "EITI Mongolia reconciliation"),
        languages=("en", "mn"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE EITI REPORT IS THE UNDERRATED ONE: it reconciles what companies say they paid "
              "against what the state says it received, by company and by payment stream, which "
              "is a second independent measurement of the royalty flow this pack's fiscal "
              "domain depends on"),
    # ---- practitioner
    source_class(
        "mn_practitioner", "Domestic brokerage and advisory research (BDSec, Golomt Capital, "
                           "Ard Capital, Mongolian Economy) and the mining-consultancy notes "
                           "that actually forecast the coal border",
        layer="practitioner",
        roots=("https://www.bdsec.mn/", "https://www.ardcapital.mn/",
               "https://mongolianeconomy.mn/"),
        queries=("хөрөнгө оруулалтын судалгаа", "нүүрсний экспортын төсөөлөл",
                 "зах зээлийн тойм долоо хоног", "компанийн үнэлгээний тайлан",
                 "уул уурхайн салбарын төлөв"),
        languages=("mn", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free with registration in places",
        notes="the only domestic ground that publishes an explicit forward view on the border "
              "and the coal price; it is also the ground most likely to be talking its own book, "
              "which is why it is RELIABLE rather than AUTHORITATIVE"),
    source_class(
        "mn_price_assessors", "The commercial coking-coal and cashmere price assessments "
                              "(the seaborne and Chinese domestic assessment services)",
        layer="practitioner",
        roots=("https://www.fastmarkets.com/", "https://www.spglobal.com/commodityinsights/"),
        queries=("coking coal assessment China", "Mongolian coal price assessment",
                 "cashmere price index", "нүүрсний үнийн үнэлгээ"),
        languages=("en", "zh", "mn"), access_label="LICENSED", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="commercial licence; machine extraction prohibited",
        machine_use_allowed=True,
        notes="REGISTERED AND NEVER SCRAPED. These are the assessments the physical trade "
              "actually prices against, and their terms forbid machine extraction; omitting the "
              "row would lose the knowledge that the ground exists, so it is recorded with "
              "machine_use_allowed=false and the public DCE curve is used as the tradable proxy"),
    # ---- retail_ecology
    source_class(
        "mn_retail_forums", "Mongolian retail investor and trucker communities: the Facebook "
                            "groups where border queue times and mine-gate prices are posted, "
                            "the MSE retail boards and the Ulaanbaatar classifieds",
        layer="retail_ecology",
        roots=("https://www.facebook.com/", "https://www.zaluu.com/", "https://unegui.mn/"),
        queries=("боомтын ачаалал хэдэн цаг", "нүүрс тээврийн жолооч", "хувьцаа авах зөвлөгөө",
                 "хөрөнгө оруулалтын групп", "Гашуунсухайт дараалал"),
        languages=("mn",), access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="platform terms apply",
        notes="KEPT AT LOW WEIGHT AND NEVER DROPPED. The truckers' own posts are the highest "
              "frequency human read on the border queue that exists, hours ahead of any "
              "official count, and they are also anecdote -- so the row is UNRELIABLE by label "
              "and is used to time a hypothesis, never to evidence one"),
    source_class(
        "mn_broker_retail", "The domestic brokers' retail account and trading statistics, and "
                            "the state's securities-account registry drive",
        layer="retail_ecology",
        roots=("https://www.mse.mn/mn/statistics", "https://frc.mn/"),
        queries=("үнэт цаасны данс нээлгэх", "хувьцаа эзэмшигчдийн тоо", "иргэдийн хөрөнгө "
                 "оруулалт", "арилжааны идэвх"),
        languages=("mn",), access_label="OPEN_DATA", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="account counts and turnover exist; MARGIN and leverage statistics do not, which "
              "is why `retail_leverage_regime` on this pack is UNMEASURED rather than a guess"),
    # ---- app_ecosystem
    source_class(
        "mn_apps", "The apps a Mongolian actually uses for money and market data: the bank "
                   "super-apps, the state services app, the MSE trading apps and the customs "
                   "single-window portal",
        layer="app_ecosystem",
        roots=("https://www.khanbank.com/mn/personal/digital/", "https://e-mongolia.mn/",
               "https://www.mse.mn/mn"),
        queries=("банкны аппликейшн", "И-Монголиа үйлчилгээ", "гаалийн цахим систем",
                 "арилжааны програм", "мобайл банк"),
        languages=("mn",), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="platform terms apply",
        notes="e-mongolia and the customs single window matter here for a specific reason: the "
              "border formalities moved online, which changes the MEASUREMENT of throughput "
              "without changing the throughput, and a step in the series at that date is an "
              "administrative artefact a study must control for"),
    source_class(
        "mn_border_apps", "The border-port queue and permit systems the haulage industry runs "
                          "on, including the electronic queue for the coal crossings",
        layer="app_ecosystem",
        roots=("https://customs.gov.mn/", "https://e-mongolia.mn/"),
        queries=("боомтын цахим дараалал", "тээврийн зөвшөөрөл", "ачаа тээврийн бүртгэл",
                 "хилийн боомтын цагийн хуваарь"),
        languages=("mn", "zh"), access_label="ACCESS_UNCLEAR", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="unclear; state portal",
        notes="an electronic queue is a MEASUREMENT INSTRUMENT for the pack's core physical "
              "series and a rationing device at the same time; both readings are testable and "
              "the pack refuses to assume which one a change in the series is"),
    # ---- media
    source_class(
        "mn_wire", "МОНЦАМЭ (Montsame, the state news agency) and the official government "
                   "communications: the first place a resolution, a border decision or a state "
                   "coal price becomes public",
        layer="media",
        roots=("https://montsame.mn/mn", "https://www.gogo.mn/", "https://zasag.mn/"),
        queries=("Засгийн газрын хуралдаан шийдвэр", "нүүрсний экспорт нэмэгдлээ",
                 "боомтын хүчин чадал", "Ерөнхий сайд мэдэгдэл", "албан ёсны мэдээлэл"),
        languages=("mn", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="a state agency reports the state's own decisions accurately and its emphasis "
              "selectively; the dates are AUTHORITATIVE and the framing is not, which is why "
              "the label is RELIABLE"),
    source_class(
        "mn_press", "The Ulaanbaatar commercial press: ikon.mn, news.mn, Өнөөдөр, Zindaa, "
                    "Eguur and the business weeklies",
        layer="media",
        roots=("https://ikon.mn/", "https://news.mn/", "https://unuudur.mn/",
               "https://www.zindaa.mn/"),
        queries=("нүүрсний экспортын мэдээ", "төгрөгийн ханш суларлаа", "уул уурхайн мэдээ",
                 "Оюу толгойн мэдээ", "хилийн боомтын мэдээ", "эдийн засгийн мэдээ"),
        languages=("mn",), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the only ground that covers a border closure the day it happens. Mongolian "
              "outlets are also where a mine-gate price rumour appears before an official "
              "announcement, which is precisely the kind of dated claim the gauntlet exists for"),
    source_class(
        "mn_chinese_mirror_press", "The Chinese-language trade press on the Mongolian border: "
                                   "the Inner Mongolia coal portals, 甘其毛都 port coverage and "
                                   "the mainland commodity media",
        layer="media",
        roots=("https://www.sxcoal.com/", "https://www.mysteel.com/", "https://www.cnmn.com.cn/"),
        queries=("甘其毛都口岸 通关车数", "蒙煤进口", "策克口岸 通关", "蒙古国 焦煤 价格",
                 "口岸 通关 恢复"),
        languages=("zh",), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE BUYER'S PRESS REPORTS THE BORDER FASTER THAN THE SELLER'S. The Chinese coal "
              "portals publish daily customs-clearance vehicle counts at Ganqimaodu and Ceke, "
              "which is the same physical series this pack's Mongolian sources carry -- read "
              "from the other side and often a day earlier"),
    # ---- archive
    source_class(
        "mn_archive", "The National Library and National Archives of Mongolia, the Төрийн "
                      "мэдээлэл state bulletin, and the web archives that hold the overwritten "
                      "customs and central-bank tables",
        layer="archive",
        roots=("http://www.nationallibrary.mn/", "https://archives.gov.mn/",
               "https://web.archive.org/"),
        queries=("Төрийн мэдээлэл эмхэтгэл", "архивын сан хөмрөг", "түүхэн статистик",
                 "эмхэтгэл 1990", "хуучин мэдээллийн сан"),
        languages=("mn",), access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE ONLY ROUTE TO A POINT-IN-TIME VINTAGE. Both customs and the statistics office "
              "overwrite their current-year tables in place, so the as-published first print of "
              "a month exists only in a crawl taken that week or in a web-archive snapshot"),
    source_class(
        "mn_script_archive", "The traditional-Mongolian-script corpus: the national script "
                             "programme's digitised documents and the bilingual state documents "
                             "published from 2025 onward",
        layer="archive",
        roots=("https://legalinfo.mn/", "http://www.nationallibrary.mn/",
               "https://e-mongolia.mn/"),
        queries=("ᠮᠣᠩᠭᠣᠯ ᠪᠢᠴᠢᠭ", "монгол бичгийн үндэсний хөтөлбөр", "хос бичигт баримт",
                 "уламжлалт монгол бичиг"),
        languages=("mn-Mong", "mn"), access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="A REAL CRAWLING FACT AND NOT A CURIOSITY. Official state documents carry the "
              "traditional script alongside Cyrillic from 2025 under the national script "
              "programme, so a crawler whose normalisation drops U+1800..U+18AF will silently "
              "lose half of each new gazetted document -- and will report the loss as absence"),
    # ---- physical_economy
    source_class(
        "mn_border_physical", "The border ports themselves: Gashuunsukhait, Shiveekhuren and "
                              "Zamyn-Uud -- daily vehicle counts, clearance hours, the "
                              "electronic queue and the seasonal closures",
        layer="physical_economy",
        roots=("https://customs.gov.mn/", "https://www.sxcoal.com/",
               "https://montsame.mn/mn"),
        queries=("Гашуунсухайт боомтоор өдөрт", "Шивээхүрэн боомт нэвтрүүлэлт",
                 "Замын-Үүд боомтын ачаалал", "甘其毛都 通关车数", "боомт хаагдлаа"),
        languages=("mn", "zh"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE PACK'S CORE SERIES. A daily physical count, published by two states, of the "
              "flow that pays for the country -- and the reason a frontier economy with no "
              "tradable currency can still mint high-frequency cells"),
    source_class(
        "mn_rail_logistics", "Ulaanbaatar Railway, the Tavantolgoi-Gashuunsukhait line and the "
                             "transit corridors: loadings, wagon availability and the dated "
                             "capacity steps",
        layer="physical_economy",
        roots=("https://ubtz.mn/", "https://www.tt-tg.mn/", "https://montsame.mn/mn"),
        queries=("төмөр замын ачилт", "Тавантолгой Гашуунсухайт төмөр зам ашиглалт",
                 "вагон хүрэлцээ", "төмөр замын тээврийн хэмжээ", "транзит тээвэр"),
        languages=("mn", "ru"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the railway is the DATED CAPACITY STEP that makes the truck series interpretable: "
              "without it, tonnage moving off the road looks like a demand fall"),
    source_class(
        "mn_energy_physical", "The fuel supply chain from Russia and the domestic power system: "
                              "import quotas, refinery outages at the supplying plants, the "
                              "Ulaanbaatar combined heat and power plants and the winter load",
        layer="physical_economy",
        roots=("https://mmhi.gov.mn/", "https://www.energy.gov.mn/", "https://montsame.mn/mn"),
        queries=("шатахууны нөөц", "шатахууны импорт Орос", "цахилгаан эрчим хүчний хэрэглээ",
                 "дулааны цахилгаан станц", "түлшний хомсдол"),
        languages=("mn", "ru"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="A LANDLOCKED COUNTRY THAT IMPORTS ALMOST ALL ITS REFINED FUEL FROM ONE NEIGHBOUR "
              "has a transport cost that is set in Moscow; the 2022 Russian export restrictions "
              "reached Mongolian mine-gate margins through exactly this channel"),
    # ---- source_graph
    source_class(
        "mn_attribution", "The attribution phrases Mongolian and Chinese reporting uses when it "
                          "is repeating a number rather than measuring one -- the expansion "
                          "edges the deep-forest miner follows",
        layer="source_graph",
        roots=("https://ikon.mn/", "https://montsame.mn/mn", "https://www.sxcoal.com/"),
        queries=("гаалийн мэдээллээр", "Монголбанкны мэдээлснээр", "эх сурвалж мэдээлэв",
                 "据海关数据", "业内人士表示"),
        languages=("mn", "zh"), access_label="PUBLIC", credibility="UNKNOWN",
        predictive_state="UNTESTED", licence="free, public",
        notes="the graph layer's job is to find WHERE A NUMBER CAME FROM. In a one-customer "
              "economy the same figure is reported on both sides of the border with different "
              "framing, and following the attribution is how the desk tells two measurements "
              "apart from one measurement quoted twice"),
    source_class(
        "mn_diaspora_aggregators", "Aggregators, mirrors and diaspora channels that republish "
                                   "Mongolian official data: the trade-data aggregators, the "
                                   "mining-news mirrors and the Telegram forwarding chains",
        layer="source_graph",
        roots=("https://comtradeplus.un.org/", "https://web.archive.org/", "https://t.me/"),
        queries=("Mongolia coal export data", "Монголын экспортын тоо баримт",
                 "уул уурхайн мэдээ түгээх", "mongolia trade statistics mirror"),
        languages=("en", "mn"), access_label="PUBLIC", credibility="FRINGE",
        predictive_state="UNTESTED", licence="mixed",
        notes="KEPT AT LOW WEIGHT AND NEVER DROPPED. A mirror that republishes a number a day "
              "before the official page updates is either a leak or an error, and both are "
              "dated, testable claims; FRINGE is the weight, not a reason to delete it"),
)

#: NO LAYER IS BLANK FOR MONGOLIA. Every one of the ten carries at least one real source with
#: crawlable roots, so there is nothing to declare absent at pack level. The measured refusals
#: this pack does make live in `ACCESS_CONSTRAINTS` and in the unavailable `POSITIONING_SOURCES`
#: rows -- no tugrik positioning series, no domestic derivatives, no retail margin statistics.
LAYER_ABSENCES: dict[str, str] = {}

#: NATIVE QUERY TERRITORIES: what the deep-forest miner actually runs, per layer, in Mongolian
#: Cyrillic (with the Chinese mirror where the buyer's press is the faster ground). Three or more
#: per layer for every layer that is not declared absent.
QUERY_TERRITORIES: dict[str, tuple[str, ...]] = {
    "official": ("Монголбанк бодлогын хүү шийдвэр", "гаалийн статистик нүүрсний экспорт",
                 "Үндэсний статистикийн хороо сарын мэдээ", "ашигт малтмалын тусгай зөвшөөрөл",
                 "Засгийн газрын тогтоол нийтээр амрах өдөр", "нэгдсэн төсвийн гүйцэтгэл"),
    "institutional": ("Эрдэнэс Тавантолгой нүүрсний үнэ", "Монголын хөрөнгийн бирж арилжаа",
                      "банкны эдийн засгийн тойм", "Эрдэнэс Монгол ногдол ашиг",
                      "Санхүүгийн зохицуулах хорооны шийдвэр"),
    "academic": ("Монголын эдийн засгийн судалгаа уул уурхай", "төгрөгийн ханшийн судалгаа",
                 "зудын эдийн засгийн нөлөө судалгаа", "нөөцийн хараал Монгол",
                 "олборлох үйлдвэрлэлийн ил тод байдал тайлан"),
    "practitioner": ("нүүрсний экспортын төсөөлөл", "зах зээлийн долоо хоногийн тойм",
                     "хөрөнгө оруулалтын зөвлөмж", "уул уурхайн салбарын төлөв",
                     "компанийн үнэлгээний тайлан"),
    "retail_ecology": ("Гашуунсухайт дараалал хэдэн өдөр", "нүүрс тээврийн жолооч групп",
                       "хувьцаа авах зөвлөгөө", "үнэт цаасны данс нээх", "боомтын ачаалал"),
    "app_ecosystem": ("И-Монголиа үйлчилгээ", "гаалийн цахим нэг цонх", "боомтын цахим дараалал",
                      "мобайл банкны шилжүүлэг", "арилжааны програм татах"),
    "media": ("нүүрсний экспорт өссөн", "төгрөгийн ханш суларлаа", "Оюу толгойн олборлолт",
              "хилийн боомт хаагдлаа", "甘其毛都口岸 通关车数", "蒙煤进口 价格"),
    "archive": ("Төрийн мэдээлэл эмхэтгэл архив", "түүхэн статистик мэдээлэл",
                "ᠮᠣᠩᠭᠣᠯ ᠪᠢᠴᠢᠭ баримт", "хуучин гаалийн мэдээ", "архивын сан хөмрөг"),
    "physical_economy": ("Гашуунсухайт боомтоор өдөрт хэдэн машин",
                         "Тавантолгой Гашуунсухайт төмөр замын ачилт", "шатахууны импорт Орос",
                         "цахилгаан эрчим хүчний хэрэглээ өвөл", "策克口岸 通关 恢复"),
    "source_graph": ("гаалийн мэдээллээр", "Монголбанкны мэдээлснээр", "эх сурвалж дурдав",
                     "据海关数据 蒙古", "业内人士 蒙煤"),
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
                    "and unreliable PUBLIC material is kept as a low-weight evidence object and "
                    "never dropped; a page whose terms forbid machine extraction is registered "
                    "machine_use_allowed=false, never scraped and never omitted"}


# --------------------------------------------------------------------------- datasets
DATASETS: tuple[dict[str, Any], ...] = (
    {"name": "Mongolian customs monthly exports by commodity and destination",
     "source": "Гаалийн ерөнхий газар (Customs General Administration)",
     "coverage": "1997 onward, monthly, by HS code and partner", "frequency": "monthly",
     "publication_lag_days": 12.0,
     "revisions": "revised in the annual bulletin; the monthly first print is not versioned",
     "licence": "free, public", "history_from": "1997-01", "pit_feasible": False,
     "assets": ("XCUUSD", "CHINAH", "USDCNH"),
     "mechanism_families": ("trade_flow", "release_surprise", "commodity_supply"),
     "how_to_fetch": "customs.gov.mn/statistics -- monthly foreign-trade spreadsheets, "
                     "downloaded per month; the current-year workbook is OVERWRITTEN in place, "
                     "so the first print's vintage needs a same-week crawl or a Wayback snapshot"},
    {"name": "Chinese customs imports from Mongolia by commodity (the MIRROR series)",
     "source": "中华人民共和国海关总署 (General Administration of Customs of China)",
     "coverage": "2000 onward, monthly, by HS code and origin country", "frequency": "monthly",
     "publication_lag_days": 20.0,
     "revisions": "occasionally restated in the annual yearbook", "licence": "free, public",
     "history_from": "2000-01", "pit_feasible": False,
     "assets": ("CHINAH", "USDCNH", "XCUUSD"),
     "mechanism_families": ("trade_flow", "mirror_statistics", "commodity_supply"),
     "how_to_fetch": "stats.customs.gov.cn online query -- select origin country Mongolia and "
                     "HS 2701 (coal) and 2603 (copper ores and concentrates), monthly, quantity "
                     "and value; the same flow measured by the BUYER rather than the seller"},
    {"name": "Border crossing daily vehicle throughput (Gashuunsukhait, Shiveekhuren, Zamyn-Uud)",
     "source": "Гаалийн ерөнхий газар and the Chinese port authorities at Ganqimaodu and Ceke",
     "coverage": "daily counts per crossing; continuous since the 2022 reopening and patchy "
                 "through the closure years",
     "frequency": "daily", "publication_lag_days": 1.0,
     "revisions": "none published; a corrected count simply replaces the earlier one",
     "licence": "free, public", "history_from": "2019-01", "pit_feasible": False,
     "assets": ("CHINAH", "USDCNH", "AUDUSD"),
     "mechanism_families": ("physical_flow", "high_frequency_proxy", "supply_disruption"),
     "how_to_fetch": "the daily port bulletins on customs.gov.mn and montsame.mn, cross-read "
                     "against the Chinese coal portals' 甘其毛都 and 策克 clearance-vehicle "
                     "counts; store BOTH sides daily because neither keeps a history"},
    {"name": "Oyu Tolgoi quarterly production, grade and guidance",
     "source": "the operator's quarterly operations review",
     "coverage": "2013 onward for the open pit, 2023 onward for the underground block cave",
     "frequency": "quarterly", "publication_lag_days": 16.0,
     "revisions": "restated only when a reporting definition changes", "licence": "free, public",
     "history_from": "2013-Q1", "pit_feasible": True,
     "assets": ("XCUUSD", "XAUUSD"),
     "mechanism_families": ("commodity_supply", "release_surprise", "guidance_revision"),
     "how_to_fetch": "the operator's quarterly operations review PDF and the accompanying "
                     "production table; extract copper in thousand tonnes, gold in ounces, mill "
                     "throughput and head grade, plus any change to the 2028-2036 guidance"},
    {"name": "Bank of Mongolia FX auction announcements and results",
     "source": "Монголбанк", "coverage": "2013 onward, every announced auction",
     "frequency": "irregular, several a month", "publication_lag_days": 0.0,
     "revisions": "none", "licence": "free, public", "history_from": "2013-01",
     "pit_feasible": False, "assets": ("USDCNH", "XAUUSD"),
     "mechanism_families": ("intervention", "central_bank_surprise", "carry_funding"),
     "how_to_fetch": "mongolbank.mn FX-auction pages -- announcement (date, instrument, offered "
                     "size) and result (bids, accepted size, accepted rate); crawl daily, the "
                     "announcement page is replaced by the result page"},
    {"name": "Bank of Mongolia monthly domestic gold purchases",
     "source": "Монголбанк", "coverage": "2010 onward, kilogrammes purchased per month",
     "frequency": "monthly", "publication_lag_days": 25.0,
     "revisions": "cumulative year-to-date figures are restated", "licence": "free, public",
     "history_from": "2010-01", "pit_feasible": True, "assets": ("XAUUSD", "USDCNH"),
     "mechanism_families": ("official_flow", "reserve_accumulation", "commodity_demand"),
     "how_to_fetch": "mongolbank.mn statistics -- the monthly gold purchase table in kilogrammes; "
                     "read it BESIDE the reserves series, because domestic gold raises reserves "
                     "with no balance-of-payments inflow behind it"},
    {"name": "Bank of Mongolia gross international reserves and the official MNT rate",
     "source": "Монголбанк", "coverage": "1996 onward, monthly reserves and daily official rate",
     "frequency": "daily rate, monthly reserves", "publication_lag_days": 25.0,
     "revisions": "reserves are revised; the daily rate is not", "licence": "free, public",
     "history_from": "1996-01", "pit_feasible": True, "assets": ("USDCNH", "USDRUB", "XAUUSD"),
     "mechanism_families": ("fx_regime", "reserve_accumulation", "macro_state"),
     "how_to_fetch": "mongolbank.mn statistical bulletin tables plus the daily official-rate "
                     "archive; the rate archive is the only long, clean, unrevised Mongolian "
                     "daily series that exists"},
    {"name": "National Statistics Office monthly socio-economic bulletin",
     "source": "Үндэсний статистикийн хороо / 1212.mn",
     "coverage": "1990s onward; CPI, industry, budget, trade, employment",
     "frequency": "monthly", "publication_lag_days": 17.0,
     "revisions": "routinely revised one and two months later", "licence": "free, public",
     "history_from": "2000-01", "pit_feasible": False, "assets": ("USDCNH", "XCUUSD"),
     "mechanism_families": ("macro_release", "release_surprise", "inflation"),
     "how_to_fetch": "1212.mn database query interface by table code, or the monthly bulletin "
                     "PDF on nso.mn; 1212.mn returns machine-readable series and is the route a "
                     "collector should take"},
    {"name": "National livestock census and the dzud winter mortality series",
     "source": "Үндэсний статистикийн хороо with the National Agency for Meteorology's dzud maps",
     "coverage": "annual census every December; mortality reported through the winter",
     "frequency": "annual with winter updates", "publication_lag_days": 45.0,
     "revisions": "the December census is provisional until the spring", "licence": "free, public",
     "history_from": "1990-12", "pit_feasible": False, "assets": ("USDCNH", "AUDUSD"),
     "mechanism_families": ("supply_shock", "weather", "household_income"),
     "how_to_fetch": "1212.mn livestock tables by aimag and species, joined to the dzud risk "
                     "maps published by the meteorological agency; the 2023-24 winter is the "
                     "recent extreme and the natural event-study window"},
    {"name": "Mongolian Agricultural Commodity Exchange cashmere and wool auctions",
     "source": "Хөдөө аж ахуйн бирж (MACE)",
     "coverage": "2013 onward; lots, volumes and clearing prices by grade",
     "frequency": "per auction, seasonal", "publication_lag_days": 1.0,
     "revisions": "none", "licence": "free, public", "history_from": "2013-04",
     "pit_feasible": False, "assets": ("USDCNH", "AUDUSD"),
     "mechanism_families": ("commodity_supply", "auction_clearing", "household_income"),
     "how_to_fetch": "the MACE auction results pages; because statute requires raw cashmere and "
                     "wool to be traded through this exchange, the volumes are close to a CENSUS "
                     "of the crop rather than a sample"},
    {"name": "MRPAM production, licence register and royalty statistics",
     "source": "Ашигт малтмал, газрын тосны газар (MRPAM)",
     "coverage": "2010 onward; extraction by mineral, the live licence cadastre, royalties paid",
     "frequency": "monthly and quarterly", "publication_lag_days": 30.0,
     "revisions": "the cadastre is a live register, not a versioned series",
     "licence": "free, public", "history_from": "2010-01", "pit_feasible": False,
     "assets": ("XCUUSD", "XZNUSD", "XALUSD"),
     "mechanism_families": ("commodity_supply", "regulatory_event", "fiscal_flow"),
     "how_to_fetch": "mrpam.gov.mn statistics pages and the cmcs.mrpam.gov.mn cadastre; snapshot "
                     "the cadastre monthly, because a revoked or transferred licence leaves no "
                     "trace in the live register once it is gone"},
    {"name": "Ministry of Finance monthly budget execution and the debt bulletin",
     "source": "Сангийн яам", "coverage": "2010 onward; revenue by source, the debt stock and "
                                          "the external repayment schedule",
     "frequency": "monthly and quarterly", "publication_lag_days": 25.0,
     "revisions": "revised at year end", "licence": "free, public", "history_from": "2010-01",
     "pit_feasible": False, "assets": ("XCUUSD", "CHINAH", "USDCNH"),
     "mechanism_families": ("fiscal_flow", "sovereign_credit", "commodity_pass_through"),
     "how_to_fetch": "mof.gov.mn budget-execution tables and the debt bulletin; the royalty and "
                     "state-dividend lines are the ones that carry the commodity price"},
    {"name": "Mongolian Stock Exchange daily trading and the TOP-20 index",
     "source": "Монголын хөрөнгийн бирж (MSE)",
     "coverage": "1995 onward, daily", "frequency": "daily", "publication_lag_days": 0.0,
     "revisions": "none", "licence": "free, public", "history_from": "1995-01",
     "pit_feasible": True, "assets": ("HK50", "CHINAH"),
     "mechanism_families": ("equity_mechanics", "sentiment", "session_microstructure"),
     "how_to_fetch": "mse.mn statistics -- daily turnover, the TOP-20 level and the foreign "
                     "share; an INFORMATION series about domestic sentiment, never a flow proxy, "
                     "because a single block trade can dominate a whole month"},
    {"name": "Erdenes Tavan Tolgoi announced coal prices and auction results",
     "source": "Эрдэнэс Тавантолгой", "coverage": "2019 onward, per announcement",
     "frequency": "irregular, announced", "publication_lag_days": 0.0,
     "revisions": "superseded rather than revised", "licence": "free, public",
     "history_from": "2019-01", "pit_feasible": False, "assets": ("CHINAH", "USDCNH", "AUDUSD"),
     "mechanism_families": ("administered_price", "commodity_supply", "policy_proxy"),
     "how_to_fetch": "ettjsc.mn and erdenes.mn announcement pages, cross-read with the Chinese "
                     "coal portals' reporting of the same announcement; a STATE price decision "
                     "is a policy event about supply and not a market clearing print"},
    {"name": "Rail loadings on the Tavantolgoi-Gashuunsukhait line and Ulaanbaatar Railway",
     "source": "Улаанбаатар төмөр зам and the Tavantolgoi-Gashuunsukhait operator",
     "coverage": "2022 onward for the new line; long history for the main north-south line",
     "frequency": "monthly, with announcements", "publication_lag_days": 20.0,
     "revisions": "none published", "licence": "free, public", "history_from": "2022-09",
     "pit_feasible": False, "assets": ("CHINAH", "USDCNH", "USDRUB"),
     "mechanism_families": ("physical_flow", "capacity_step", "logistics"),
     "how_to_fetch": "ubtz.mn and the line operator's announcements plus Montsame reporting; "
                     "THE CONTROL VARIABLE for the truck series -- tonnage that moved to rail is "
                     "not tonnage that stopped moving"},
    {"name": "Fuel import volumes and the Russian supply quota",
     "source": "Уул уурхай, хүнд үйлдвэрийн яам and the customs energy tables",
     "coverage": "2010 onward, monthly diesel and petrol imports by origin",
     "frequency": "monthly", "publication_lag_days": 25.0, "revisions": "minor",
     "licence": "free, public", "history_from": "2010-01", "pit_feasible": False,
     "assets": ("USDRUB", "XBRUSD", "XNGUSD"),
     "mechanism_families": ("import_dependency", "energy_cost", "supply_disruption"),
     "how_to_fetch": "the ministry's fuel-supply bulletins plus the customs import tables for "
                     "HS 2710; the 2022 Russian export-restriction episode is the natural "
                     "event-study window for the dependency"},
    {"name": "Sovereign external debt repayment schedule and the eurobond calendar",
     "source": "Сангийн яам debt bulletin, with the IMF and World Bank programme documents",
     "coverage": "the full outstanding external schedule by year",
     "frequency": "quarterly", "publication_lag_days": 40.0,
     "revisions": "restated after each liability-management exercise", "licence": "free, public",
     "history_from": "2012-01", "pit_feasible": False, "assets": ("XCUUSD", "USDCNH", "AUDUSD"),
     "mechanism_families": ("sovereign_credit", "refinancing_event", "fiscal_flow"),
     "how_to_fetch": "mof.gov.mn debt bulletin tables and the IMF country page; what matters is "
                     "the DATE and SIZE of each maturity against the export receipt that has to "
                     "service it, which is why the commodity legs carry this row"},
    {"name": "ICSG world copper supply and demand balance",
     "source": "International Copper Study Group",
     "coverage": "1960s onward, monthly world mine and refined production",
     "frequency": "monthly", "publication_lag_days": 60.0,
     "revisions": "revised routinely as members report", "licence": "free summary, paid detail",
     "history_from": "1995-01", "pit_feasible": False, "assets": ("XCUUSD", "XZNUSD"),
     "mechanism_families": ("commodity_balance", "supply_share", "denominator"),
     "how_to_fetch": "icsg.org press-release bulletins for the world mine-production total; this "
                     "is the DENOMINATOR `oyu_tolgoi_ramp` divides by, and it is held as a "
                     "separate row so the share is a measured ratio rather than a typed claim"},
)

# --------------------------------------------------------------------------- actors
ACTORS: tuple[dict[str, Any], ...] = (
    {"name": "The Oyu Tolgoi operator as the keeper of a published copper timetable",
     "holds": "the block cave, the open pit, the concentrator and a development schedule "
              "published years in advance with the state as a 34% partner",
     "forced_to": ("report tonnage, head grade and mill throughput every quarter",
                   "restate guidance publicly when the ramp slips",
                   "sell concentrate priced off the LME benchmark, not off a domestic price",
                   "meet the investment-agreement commitments the state can enforce"),
     "when": "quarterly operations review, roughly a fortnight after each quarter end, in the "
             "European morning",
     "information": ("the cave's actual draw rate and undercut progress before anyone else",
                     "the grade profile of the ore already broken",
                     "the concentrate shipment schedule to the border",
                     "the state of the power supply agreement that constrains everything"),
     "constraints": ("A BLOCK CAVE CANNOT BE THROTTLED LIKE AN OPEN PIT: once caving starts the "
                     "production profile is set by rock mechanics and years of development, not "
                     "by this quarter's copper price",
                     "power is imported and contracted, and the domestic supply commitment is a "
                     "political variable",
                     "a 34% state partner whose parliament revisits the agreement periodically",
                     "one export route, one border, one customer"),
     "instruments": ("XCUUSD", "XAUUSD", "XALUSD"),
     "counterparties": ("Chinese smelters taking the concentrate",
                        "the Government of Mongolia as partner and taxing authority",
                        "the trade finance banks funding the shipments",
                        "the haulage contractors running concentrate to the border"),
     "observables": ("quarterly copper tonnes and gold ounces", "head grade and throughput",
                     "the 2028-2036 guidance and any change to it",
                     "the customs concentrate export line"),
     "impact": "on the order of two per cent of world mine supply once the cave is at plateau; a "
               "guidance change here is one of the few genuinely dated supply-side events in the "
               "copper market",
     "persistence": "the plateau is guided for roughly a decade, so this is the longest-lived "
                    "mechanism in the pack and the one least likely to decay from crowding",
     "falsifier": "XCUUSD's reaction in the report window matches the reaction on quarters when "
                  "the operator's OTHER assets drove the print and Oyu Tolgoi did not, and "
                  "matches the matched-hour control on non-report days; if it does, the pack is "
                  "measuring a diversified miner's results and calling them Mongolian supply",
     "notes": "THE LISTED PARENT IS A SINGLE NAME AND IS EVENT LANE ONLY. It appears here as an "
              "actor and never as an executable instrument, a domain instrument or an edge "
              "target (two-lane order, 2026-09-06)"},
    {"name": "Erdenes Tavan Tolgoi as a state seller that announces its own coal price",
     "holds": "the Tavan Tolgoi coking coal deposit's state share, the mine-gate stockpile and "
              "the right to set an announced selling price rather than accept a market one",
     "forced_to": ("announce prices and auction terms publicly",
                   "pay dividends into the budget the Ministry of Finance has already spent",
                   "move coal through two border crossings and one new railway",
                   "answer to a parliament that treats the deposit as a national asset"),
     "when": "price announcements and auctions are irregular and are published when they happen",
     "information": ("the true mine-gate stockpile and its quality split",
                     "the discount actually being realised against the Chinese curve",
                     "the state's fiscal need for the next dividend",
                     "the haulage capacity contracted for the coming quarter"),
     "constraints": ("AN ANNOUNCED PRICE IS A POLICY ACT: raising it loses volume at the border "
                     "and lowering it is read domestically as selling the patrimony cheap",
                     "the buyer is concentrated enough to wait",
                     "the border's physical capacity caps the volume regardless of price",
                     "a dividend obligation that does not move with the coal price"),
     "instruments": ("CHINAH", "USDCNH", "AUDUSD"),
     "counterparties": ("the Chinese washing plants and traders at Ganqimaodu",
                        "the Ministry of Finance as owner and revenue claimant",
                        "the haulage and rail operators",
                        "the domestic power plants taking thermal coal"),
     "observables": ("the announced price and the auction clearing price",
                     "monthly export tonnage in the customs table",
                     "the implied discount to the Dalian curve",
                     "the stockpile visible at the mine and at the border"),
     "impact": "sets the marginal price of the largest single physical trade Mongolia has, and "
               "therefore the royalty and dividend line in the national budget",
     "persistence": "the announced-price regime has persisted through several governments; it "
                    "is an institutional feature, not a cyclical one",
     "falsifier": "an announcement date shows no abnormal move in CHINAH or in the coal complex "
                  "beyond what the Dalian curve had already done in the preceding week -- which "
                  "would mean the announcement is confirming a price the market set, not setting"
                  " one",
     "notes": "the cleanest example on this desk's book of a PRICE THAT IS DECIDED RATHER THAN "
              "DISCOVERED, which is a different statistical object and must be modelled as one"},
    {"name": "The Bank of Mongolia as a managed float with an auction and a gold desk",
     "holds": "the policy rate, the reserve requirement including a separate ratio on "
              "foreign-currency liabilities, the FX auction and a standing domestic bid for gold",
     "forced_to": ("publish the daily official rate and the auction results",
                   "publish reserves monthly",
                   "defend the tugrik with a reserve stock that is small against the import bill",
                   "buy domestic gold at the LBMA-linked price under the purchase programme"),
     "when": "auctions as announced through the month; statistics around the fourth week",
     "information": ("the banking system's true FX position before it is published",
                     "the pipeline of import payments the auction is about to meet",
                     "the actual composition of reserves",
                     "the gold that artisanal miners are about to deliver"),
     "constraints": ("A SMALL RESERVE STOCK AGAINST A CONCENTRATED IMPORT BILL: the defence is "
                     "credible for weeks, not quarters, which is why the auction is rationed "
                     "rather than unlimited",
                     "a renminbi swap line that is a liquidity backstop and not a reserve",
                     "an export receipt that arrives in renminbi and an import bill that is "
                     "part rouble and part dollar",
                     "domestic gold purchases add to reserves without any inflow behind them"),
     "instruments": ("USDCNH", "USDRUB", "XAUUSD"),
     "counterparties": ("the four large domestic banks",
                        "the PBoC through the swap line",
                        "the Ministry of Finance as the sovereign borrower",
                        "the artisanal and hard-rock gold producers"),
     "observables": ("the daily official rate", "the auction offered and accepted amounts",
                     "monthly reserves", "monthly gold purchases in kilogrammes"),
     "impact": "sets the price at which the country's export receipt becomes domestic money, and "
               "is one of the few central banks anywhere whose PHYSICAL GOLD BID is published "
               "monthly as a tonnage",
     "persistence": "the managed-float-plus-auction regime has survived a reserve crisis and an "
                    "IMF programme; it is structural",
     "falsifier": "XAUUSD shows no abnormal behaviour around the monthly gold-purchase print "
                  "relative to matched months, which would mean the tonnage is too small to "
                  "matter at world scale and belongs in the reserve story only -- the expected "
                  "result, and the pack says so in advance",
     "notes": "the pack's honest-prior actor: a central bank buying twenty-odd tonnes a year is "
              "a rounding error in the gold market and a first-order fact in Mongolia"},
    {"name": "The Ministry of Finance as a frontier issuer with a commodity revenue line",
     "holds": "the consolidated budget, the external debt stock and a refinancing calendar that "
              "must be met out of mineral royalties and state dividends",
     "forced_to": ("publish budget execution monthly and the debt bulletin quarterly",
                   "refinance eurobond maturities in the market or with bilateral help",
                   "book royalties that move with a price it does not set",
                   "fund transfers and subsidies the legislature has already promised"),
     "when": "monthly execution around the fourth week; refinancing when a maturity approaches",
     "information": ("the true near-term cash position",
                     "the state of negotiations on any bilateral facility",
                     "the royalty accruals before they are published",
                     "the dividend the state miners are about to be told to pay"),
     "constraints": ("REVENUE IS A COMMODITY PRICE AND SPENDING IS A POLITICAL PROMISE, and the "
                     "two are set by different people on different clocks",
                     "a hard-currency maturity schedule against a local-currency tax base",
                     "a small domestic bond market that cannot absorb a real shortfall",
                     "an election cycle that reliably widens the deficit"),
     "instruments": ("XCUUSD", "USDCNH", "AUDUSD"),
     "counterparties": ("international bondholders", "the Development Bank of Mongolia",
                        "the state mining companies as dividend payers",
                        "the IMF and the bilateral lenders"),
     "observables": ("monthly budget execution", "the external repayment schedule",
                     "royalty receipts", "each liability-management announcement"),
     "impact": "a refinancing event is the moment Mongolia's commodity cycle becomes a credit "
               "event, and the date of every such event is known years ahead",
     "persistence": "structural: the revenue base has been mineral-dominated for two decades and "
                    "no diversification has changed it",
     "falsifier": "commodity legs show no differential behaviour in the weeks around a known "
                  "maturity relative to matched weeks, which would mean the sovereign's cash "
                  "need is too small to reach any price the desk can trade",
     "notes": "the bond itself has NO broker instrument; this actor's cells terminate in the "
              "commodities that service the coupon, which is stated rather than hidden"},
    {"name": "The Customs General Administration as the publisher of the border series",
     "holds": "the monthly trade tables, the daily crossing counts and the clearance process "
              "that decides how many trucks physically pass",
     "forced_to": ("publish monthly trade statistics",
                   "publish crossing throughput",
                   "process clearances within the hours the border is open",
                   "implement whatever the Cabinet decides about the border"),
     "when": "monthly tables around the second week; crossing counts daily",
     "information": ("the clearance backlog before it is a queue anyone can see",
                     "the valuation being applied to each consignment",
                     "the true commodity split of what crossed yesterday"),
     "constraints": ("THE AGENCY IS BOTH THE MEASURING INSTRUMENT AND PART OF THE CONSTRAINT: "
                     "clearance capacity is one of the things that limits throughput, so a fall "
                     "in the count can be a fall in demand or a fall in this agency's own "
                     "processing, and the two look identical in the published series",
                     "opening hours agreed bilaterally with the Chinese side",
                     "an electronic queue that rations as well as measures",
                     "seasonal closures for the statutory holidays"),
     "instruments": ("CHINAH", "USDCNH", "AUDUSD"),
     "counterparties": ("the Chinese customs authority at Ganqimaodu and Ceke",
                        "the haulage companies", "the state and private coal sellers"),
     "observables": ("daily vehicle counts by crossing", "monthly tonnage by commodity",
                     "declared value per tonne", "announced closures and hour changes"),
     "impact": "produces the only daily physical series in the pack, and its own capacity is one "
               "of the variables that series measures",
     "persistence": "permanent as an institution; its capacity steps with each infrastructure "
                    "project",
     "falsifier": "the daily count adds nothing to a model of the monthly customs tonnage once "
                  "the Chinese mirror count is included -- which would mean the two states are "
                  "publishing one measurement, not two",
     "notes": "the instrument-and-constraint duality here is the single most important caveat in "
              "the whole pack and is repeated in MN-B's controls"},
    {"name": "The Chinese buyer at Ganqimaodu as the only customer that matters",
     "holds": "the washing plants, the coking capacity and the trader balance sheets on the "
              "southern side of the crossing, and the option to buy seaborne coal instead",
     "forced_to": ("feed coke ovens on a schedule set by steel mills",
                   "hold inventory against a border that has closed before",
                   "price against the Dalian curve their own hedges are struck on",
                   "clear customs on the Chinese side within the port's hours"),
     "when": "continuously, with a distinct seasonality around the Chinese winter heating and "
             "construction cycle",
     "information": ("their own coke-oven utilisation and inventory days",
                     "the seaborne alternative's landed cost today",
                     "the state of the Chinese steel margin before it is published"),
     "constraints": ("A SUBSTITUTE EXISTS AND IT IS SEABORNE: Australian and Russian coking coal "
                     "compete for the same ovens, which caps what the land route can charge and "
                     "is exactly why AUDUSD is this pack's named control",
                     "inland logistics from the border to the mills",
                     "Chinese import policy, which has been used as a lever before",
                     "the steel margin, which is set far from this border"),
     "instruments": ("CHINAH", "USDCNH", "AUDUSD"),
     "counterparties": ("Mongolian sellers, state and private",
                        "the Chinese steel mills", "the Dalian futures market"),
     "observables": ("Chinese customs imports from Mongolia by month",
                     "port clearance vehicle counts", "Dalian coking coal and coke settlements",
                     "Chinese coking coal inventory series"),
     "impact": "sets the realised price of Mongolia's largest export and therefore the country's "
               "fiscal position, one quarter later",
     "persistence": "the geography is permanent; the policy lever is not, and the era table "
                    "dates the episodes when it was used",
     "falsifier": "a Mongolian border disruption shows no differential effect on the Chinese "
                  "coal complex relative to seaborne-supply disruptions of similar size -- which "
                  "would mean the land route is fully substitutable and the mechanism is a "
                  "global coal mechanism wearing a Mongolian hat",
     "notes": "THE CONTROL IS THE MECHANISM'S OWN TEST. Naming `au` here is not politeness: "
              "without the seaborne leg the pack cannot tell a Mongolian supply event from a "
              "Chinese demand event"},
    {"name": "The border haulage operators as the physical throughput constraint",
     "holds": "the trucks, the drivers, the permits and the queue position that decides whose "
              "coal crosses today",
     "forced_to": ("queue for days when clearance is slow",
                   "pay for diesel priced off an imported Russian barrel",
                   "stop for the statutory holiday blocks whatever the coal price is",
                   "compete with a railway that now takes part of the volume"),
     "when": "daily, with a sharp morning peak and a hard stop at the border's closing hour",
     "information": ("today's real queue length hours before any count is published",
                     "the clearance rate on the Chinese side this morning",
                     "the mine-gate loading rate upstream"),
     "constraints": ("A ROAD WITH A FIXED NUMBER OF CLEARANCE LANES cannot be scaled by price; "
                     "when demand rises, the queue lengthens rather than the flow",
                     "fuel cost that is a Russian policy variable",
                     "weather, which closes the route outright in the worst winter days",
                     "the new railway, which is a capacity step and a competitor at once"),
     "instruments": ("CHINAH", "USDCNH", "XBRUSD"),
     "counterparties": ("the coal sellers who charter them", "the customs agencies on both sides",
                        "the fuel importers"),
     "observables": ("trucks cleared per day", "queue length reported by the drivers themselves",
                     "diesel price at the border", "rail tonnage as the substitute"),
     "impact": "the difference between coal that is sold and coal that is stockpiled is very "
               "often nothing more than this queue",
     "persistence": "the constraint relaxes with each infrastructure step and returns as volume "
                    "grows into it; it has never disappeared",
     "falsifier": "the driver-reported queue in the social layer adds nothing to a next-day "
                  "forecast of the official count once the previous day's count is known, which "
                  "would make the social layer narrative rather than data",
     "notes": "the actor whose own posts are the retail_ecology layer's content; kept at "
              "UNRELIABLE weight and used to TIME a hypothesis, never to evidence one"},
    {"name": "The Tavantolgoi-Gashuunsukhait railway as a dated capacity step",
     "holds": "a purpose-built heavy-haul line from the coal field to the border, opened across "
              "2022-2024, with a cross-border connection negotiated between two states",
     "forced_to": ("publish loadings and capacity milestones",
                   "interchange with a Chinese network of a different gauge",
                   "run to a timetable rather than a queue"),
     "when": "commissioning milestones are announced; loadings are reported monthly",
     "information": ("actual wagon availability and cycle times",
                     "the interchange throughput agreed with the Chinese operator",
                     "the tonnage that has genuinely shifted off the road"),
     "constraints": ("A GAUGE BREAK AND A BILATERAL AGREEMENT at the border, so the line's "
                     "capacity is not its own",
                     "capital cost that must be recovered from a tariff the sellers will pay",
                     "a road haulage industry it displaces and that lobbies"),
     "instruments": ("CHINAH", "USDCNH", "AUDUSD"),
     "counterparties": ("the state and private coal sellers", "the Chinese rail network",
                        "the road hauliers it competes with"),
     "observables": ("commissioning announcements with dates",
                     "monthly rail tonnage", "the road count over the same months",
                     "total exports as the sum of both"),
     "impact": "raises the ceiling on Mongolian coal exports in discrete, dated steps, which is "
               "the cleanest kind of structural break a time series can be given",
     "persistence": "permanent once built; the step does not reverse",
     "falsifier": "total coal exports show no level shift at the commissioning dates once the "
                  "Chinese steel cycle is controlled for -- which would mean the line "
                  "substituted for road haulage without adding capacity at all",
     "notes": "THE CONTROL THAT MAKES MN-B INTERPRETABLE: without the dated rail step, tonnage "
              "moving from road to rail reads as a demand collapse in the truck series"},
    {"name": "The herder household as the dzud-exposed producer of the fibre crop",
     "holds": "the national herd -- tens of millions of animals held by hundreds of thousands of "
              "households -- and with it the cashmere and wool crop",
     "forced_to": ("winter the herd on open pasture with no shelter for most animals",
                   "sell fibre in a short spring season through the statutory exchange",
                   "restock after a mortality event, which takes years",
                   "borrow against next year's crop when this year's fails"),
     "when": "the dzud window runs from December to April; the fibre season follows in spring",
     "information": ("the true state of the herd months before the census counts it",
                     "local pasture and snow conditions",
                     "the price being offered at the local collection point"),
     "constraints": ("A LIVESTOCK POPULATION CANNOT BE REBUILT IN A SEASON: a mortality shock "
                     "has a multi-year echo in the fibre crop, which makes it one of the few "
                     "genuinely PERSISTENT supply shocks in the pack",
                     "no meaningful insurance for most households",
                     "a statutory requirement to sell raw fibre through the exchange",
                     "one dominant buyer across the border"),
     "instruments": ("USDCNH", "AUDUSD"),
     "counterparties": ("the Chinese dehairing and spinning mills",
                        "the domestic cashmere processors",
                        "the banks lending against the crop",
                        "the state, through emergency response and subsidies"),
     "observables": ("the December livestock census", "winter mortality reports by aimag",
                     "the meteorological agency's dzud risk maps",
                     "MACE auction volumes and clearing prices in the spring"),
     "impact": "a severe dzud is a multi-year supply shock in a commodity with no broker symbol, "
               "which reaches the desk through the trade balance, the tugrik and the rural "
               "credit channel rather than through a fibre price",
     "persistence": "years: the herd rebuild is slow and the fibre crop follows the herd",
     "falsifier": "a severe dzud winter shows no differential effect on the spring MACE auction "
                  "volumes relative to mild winters -- which would mean the census and the "
                  "mortality reports are measuring something other than the crop",
     "notes": "the pack routes this into USDCNH and names COTTON as a SUBSTITUTE-FIBRE PLACEBO "
              "rather than a proxy, because a vegetable fibre with a different growing season "
              "shares no supply mechanism with an animal one"},
    {"name": "MRPAM as the keeper of the licence register",
     "holds": "every exploration and mining licence in the country, the cadastre map, the "
              "production returns and the royalty calculations",
     "forced_to": ("maintain a public cadastre",
                   "publish production and royalty statistics",
                   "implement moratoria and revocations the government decides",
                   "process transfers between holders"),
     "when": "the register is live; statistics are monthly and quarterly",
     "information": ("pending applications and transfers before they are public",
                     "which licences are about to lapse",
                     "production returns before they are aggregated"),
     "constraints": ("A LIVE REGISTER KEEPS NO HISTORY OF ITSELF: once a licence is revoked or "
                     "transferred, the previous state is gone unless somebody snapshotted it",
                     "political direction on moratoria that arrives without notice",
                     "a cadastre whose boundaries are contested in places"),
     "instruments": ("XCUUSD", "XZNUSD", "XALUSD"),
     "counterparties": ("the licence holders, domestic and foreign",
                        "the Ministry of Finance as royalty claimant",
                        "the parliament, which legislates over the register"),
     "observables": ("the live cadastre", "monthly production by mineral",
                     "royalty receipts", "announced moratoria and revocations"),
     "impact": "resource-nationalism episodes are visible HERE first, as register events with "
               "dates, before they are visible as headlines or as prices",
     "persistence": "each episode is dated and bounded; the institution is permanent",
     "falsifier": "register events show no relationship to the industrial-metals complex beyond "
                  "what the commodity cycle already explains, which would mean Mongolian "
                  "regulatory risk is not priced anywhere the desk can reach",
     "notes": "MONTHLY SNAPSHOTS ARE MANDATORY for this actor to be researchable at all; the "
              "dataset row says so and `ACCESS_CONSTRAINTS` records the consequence"},
    {"name": "The Russian fuel supplier as the monopoly input to every Mongolian tonne-kilometre",
     "holds": "the refined-product supply on which Mongolian road haulage, mining fleets and "
              "power generation depend, under annual intergovernmental arrangements",
     "forced_to": ("supply under quota arrangements negotiated state to state",
                   "price off a Russian domestic-plus-netback basis rather than a world one",
                   "meet its own domestic obligations first when policy restricts exports"),
     "when": "annual quota negotiations, with episodic export restrictions",
     "information": ("its own refinery run and maintenance schedule",
                     "the export policy decision before it is announced",
                     "the Mongolian buyer's stock cover"),
     "constraints": ("RUSSIAN EXPORT POLICY IS SET FOR RUSSIAN REASONS and Mongolia is a price "
                     "and quantity taker with no alternative route at scale",
                     "rail capacity on the northern corridor",
                     "sanctions and payment frictions that change settlement mechanics"),
     "instruments": ("USDRUB", "XBRUSD", "XNGUSD"),
     "counterparties": ("the Mongolian fuel importers and the state",
                        "the mining fleets and haulage companies as end users"),
     "observables": ("monthly fuel import volumes by origin",
                     "domestic pump and wholesale prices",
                     "announced Russian export restrictions",
                     "Mongolian emergency fuel-reserve announcements"),
     "impact": "moves the cost of moving every tonne of coal and concentrate to the border, and "
               "therefore the realised margin on the country's export",
     "persistence": "structural; no alternative supply route exists at the volumes required",
     "falsifier": "Mongolian fuel-supply episodes show no differential effect on the border "
                  "throughput series relative to matched periods with no fuel disruption -- "
                  "which would mean the cost channel does not bind the physical flow",
     "notes": "the reason USDRUB is executable in this pack at all; the `ru` pack owns the "
              "Russian side and this pack reads it rather than re-deriving it"},
    {"name": "The Mongolian Stock Exchange and the state IPO programme",
     "holds": "the domestic listing venue, the TOP-20 index and the pipeline of state mining "
              "assets the government has said it will list",
     "forced_to": ("publish daily turnover and the index",
                   "list what the government decides to list",
                   "operate a market whose turnover is small enough to be moved by one order"),
     "when": "daily sessions 10:00-13:00 local; IPOs when the government announces them",
     "information": ("the state of the IPO pipeline before announcement",
                     "the order book, which no one outside sees",
                     "the domestic retail account opening rate"),
     "constraints": ("TURNOVER TOO SMALL TO ABSORB A REAL FLOW, which is why a state IPO is an "
                     "event about fiscal policy rather than about equity valuation",
                     "no derivatives, so no hedging and no expiry clock",
                     "foreign participation that arrives and leaves in blocks"),
     "instruments": ("HK50", "CHINAH"),
     "counterparties": ("domestic retail and pension money",
                        "the few foreign frontier funds that participate",
                        "the state as issuer"),
     "observables": ("daily turnover and the TOP-20 level", "the foreign share of turnover",
                     "IPO announcements and their sizes", "new account openings"),
     "impact": "an information venue about domestic sentiment and about the state's fiscal "
               "intentions; it is never an executable venue for this desk",
     "persistence": "the venue is permanent; the IPO programme is a dated policy episode",
     "falsifier": "MSE turnover and the TOP-20 add nothing to a model of the executable legs "
                  "once the commodity complex is controlled for, which is the EXPECTED result "
                  "and is why the venue is declared non-executable in advance",
     "notes": "declared so a miner does not discover the absence of a tradable Mongolian equity "
              "leg by failing silently (L1.28a)"},
    {"name": "The State Great Khural as the periodic rewriter of the resource bargain",
     "holds": "the minerals law, the tax code, the investment agreements' ratification and the "
              "power to declare a deposit strategic",
     "forced_to": ("publish every law and resolution on the legal database",
                   "face an election cycle in which resource nationalism is reliably popular",
                   "fund a budget whose revenue it does not control",
                   "ratify or renegotiate the agreements that bring the capital in"),
     "when": "sessions through the year; the dated episodes cluster around elections and around "
             "commodity price peaks",
     "information": ("the draft of an amendment before it is tabled",
                     "the political arithmetic behind a windfall-tax proposal",
                     "the state of any renegotiation with a foreign operator"),
     "constraints": ("EVERY TIGHTENING RAISES THE COST OF THE NEXT FOREIGN CAPITAL, and the "
                     "legislature knows it, which is why episodes have historically been "
                     "followed by reversals",
                     "the budget's dependence on the very investors being pressured",
                     "an IMF or bilateral relationship that constrains the extremes"),
     "instruments": ("XCUUSD", "CHINAH", "USDCNH"),
     "counterparties": ("the foreign operators", "the state mining companies",
                        "the international lenders and bondholders"),
     "observables": ("bills and resolutions on legalinfo.mn with dates",
                     "licence moratoria in the MRPAM register",
                     "tax-code amendments", "ratification votes"),
     "impact": "sets the dated regime boundaries that make any pooled study of Mongolian mining "
               "data invalid, which is why POLICY_ERAS exists at all",
     "persistence": "each episode is bounded; the tendency recurs with the commodity cycle",
     "falsifier": "an episode's dates show no differential behaviour in the executable legs "
                  "relative to matched windows, which would mean Mongolian political risk is "
                  "priced entirely in the unlisted equity of a single name and nowhere the desk "
                  "can reach",
     "notes": "the actor that produces the era table; a study that pools across its dates is "
              "measuring several different bargains and calling the average a mechanism"},
    {"name": "The domestic commercial banks as the tugrik's transmission mechanism",
     "holds": "the deposit base, the FX position, the mining-sector credit book and the "
              "household loans that the herder economy runs on",
     "forced_to": ("meet a reserve requirement that differs by liability currency",
                   "bid in the central bank's FX auctions to meet client import payments",
                   "hold capital against a loan book concentrated in one cyclical sector",
                   "reprice deposits when the policy rate moves"),
     "when": "continuously, with a distinct year-end and Tsagaan Sar cash cycle",
     "information": ("the real FX demand pipeline from importers",
                     "loan quality in the mining supply chain before it is provisioned",
                     "household cash behaviour ahead of the Tsagaan Sar gift season"),
     "constraints": ("A DEPOSIT BASE PARTLY IN A CURRENCY THE BANK CANNOT PRINT and a loan book "
                     "concentrated in the sector that determines the exchange rate",
                     "a small interbank market with few counterparties",
                     "regulatory limits on open FX positions"),
     "instruments": ("USDCNH", "USDRUB", "XAUUSD"),
     "counterparties": ("the central bank in the auctions", "importers and exporters",
                        "households", "the correspondent banks abroad"),
     "observables": ("deposit dollarisation", "auction bid sizes",
                     "credit growth to mining and to households",
                     "the seasonal cash withdrawal spike before Tsagaan Sar"),
     "impact": "decides whether an export receipt becomes domestic credit or an FX deposit, "
                 "which is the difference between a commodity boom and a currency crisis",
     "persistence": "structural; the concentration has survived every cycle so far",
     "falsifier": "deposit dollarisation adds nothing to a model of the official rate once the "
                  "auction size and the terms of trade are included, which would mean the "
                  "banking channel is a consequence rather than a mechanism",
     "notes": "the Tsagaan Sar cash cycle is the one seasonal banking fact in this pack, and it "
              "moves with the MONGOLIAN lunar calendar rather than the Chinese one"},
)

# --------------------------------------------------------------------------- domains
DOMAINS: tuple[dict[str, Any], ...] = (
    {"id": "MN-A", "title": "The Oyu Tolgoi underground ramp as a published supply curve",
     "objects": ("the quarterly copper tonnage and head grade from the block cave",
                 "the published 2028-2036 guidance and every restatement of it",
                 "the deviation of the realised quarter from the schedule the market already had",
                 "the concentrate export line in the Mongolian customs table"),
     "conditions": ("the deviation of realised tonnage from the pack's own `oyu_tolgoi_ramp` "
                    "schedule for that year",
                    "whether the report carried a GUIDANCE CHANGE as opposed to a tonnage miss",
                    "the ramp phase: reported years, guided years, or interpolated years"),
     "instruments": ("XCUUSD", "XAUUSD", "XALUSD"),
     "controls": ("the same report-hour window on quarters where the operator's other assets "
                  "drove the print and Oyu Tolgoi did not, which separates a Mongolian supply "
                  "event from a diversified miner's results",
                  "the matched weekday-plus-hour control on XCUUSD with no report in it",
                  "the ICSG world mine-supply series over the same quarters, so a Mongolian "
                  "share change must beat the world balance to be Mongolia's"),
     "notes": "A PUBLISHED SCHEDULE CHANGES THE OBJECT. The market has had the guidance for "
              "years, so the level carries no information and only the deviation can; a study "
              "that regresses price on tonnage is fitting a number everybody already knew"},
    {"id": "MN-B", "title": "The Gashuunsukhait truck count as a daily coking-coal supply read",
     "objects": ("daily cleared vehicles at Gashuunsukhait, Shiveekhuren and Zamyn-Uud",
                 "the Chinese mirror count at Ganqimaodu and Ceke",
                 "the implied annual tonnage from `border_throughput_state`",
                 "the monthly customs tonnage the daily count is meant to nowcast"),
     "conditions": ("the throughput bucket: closed, severely restricted, pre-2020 normal, "
                    "post-reopening high, or record",
                    "whether the day sits inside a statutory closure block (Naadam, Tsagaan Sar)",
                    "the sign and size of the wedge between the implied tonnage and the customs "
                    "tonnage for the month to date"),
     "instruments": ("CHINAH", "USDCNH", "AUDUSD"),
     "controls": ("the SAME DAYS at Shiveekhuren-Ceke, which separates 'the coal moved' from "
                  "'this crossing moved it'",
                  "rail tonnage over the same months, without which a shift from road to rail "
                  "reads as a demand collapse",
                  "seaborne coking coal and AUDUSD over the same window, which separates a "
                  "Mongolian supply event from a Chinese steel-demand event"),
     "notes": "THE MEASURING INSTRUMENT IS PART OF THE CONSTRAINT. Clearance capacity limits "
              "throughput AND produces the number, so a fall can be demand or can be the "
              "customs agency itself; the controls exist for exactly that ambiguity"},
    {"id": "MN-C", "title": "The Tavantolgoi railway as a dated capacity step",
     "objects": ("the commissioning and cross-border connection milestones with their dates",
                 "monthly rail tonnage on the new line",
                 "the road count over the same months",
                 "total coal exports as the sum of both routes"),
     "conditions": ("pre-commissioning, commissioning year, or post-connection era",
                    "the rail share of total coal tonnage in the month",
                    "whether total exports stepped or merely re-routed"),
     "instruments": ("CHINAH", "USDCNH", "AUDUSD"),
     "controls": ("the pre-commissioning months with the Chinese steel cycle held fixed",
                  "the Shiveekhuren route, which the new line does not serve and which "
                  "therefore should show no step at all",
                  "a placebo step placed at a random date in the same year"),
     "notes": "a STRUCTURAL BREAK WITH A KNOWN DATE is the cleanest thing a time series can be "
              "given, and it is also the control MN-B needs; both readings live here"},
    {"id": "MN-D", "title": "The tugrik's managed float, the auctions and the swap line",
     "objects": ("the daily official MNT rate and its drift",
                 "the FX auction offered and accepted amounts",
                 "gross reserves and their months of import cover",
                 "the renminbi swap line as a backstop that is not a reserve"),
     "conditions": ("the auction intensity bucket: accepted size relative to the trailing "
                    "monthly import bill",
                    "the reserve cover bucket in months of imports",
                    "whether the terms of trade moved with the currency or against it"),
     "instruments": ("USDCNH", "USDRUB", "XAUUSD"),
     "controls": ("the SAME conditioning states measured on days with no auction at all, which "
                  "is the null for a state variable that only exists on event days",
                  "the `cn` pack's own CNH behaviour over the identical window, so a Mongolian "
                  "claim must beat the offshore renminbi's own story",
                  "a block-permuted official-rate series, the null for an administered price"),
     "notes": "THE HONEST PRIOR IS THAT A CURRENCY THE DESK CANNOT TRADE TRANSMITS LITTLE. This "
              "domain exists to MEASURE that rather than assume it, and a positive result "
              "against these controls would be the surprise"},
    {"id": "MN-E", "title": "The Bank of Mongolia's domestic gold purchase programme",
     "objects": ("monthly kilogrammes of domestically purchased gold",
                 "the reserve series it feeds without a balance-of-payments inflow",
                 "the artisanal and hard-rock supply response to the domestic price",
                 "the royalty treatment that makes selling to the central bank attractive"),
     "conditions": ("the monthly purchase tonnage relative to its trailing twelve-month mean",
                    "whether the gold price in tugrik terms is at a domestic record",
                    "the season -- the placer mining season is short and northern"),
     "instruments": ("XAUUSD", "USDCNH", "XCUUSD"),
     "controls": ("matched months with no unusual purchase, which is the base rate",
                  "world central-bank purchases over the same quarters, so a Mongolian tonnage "
                  "claim must be distinguishable from the global official bid",
                  "the domestic tugrik gold price as the supply-side explanation, which must be "
                  "ruled out before any world-price channel is claimed"),
     "notes": "THE EXPECTED RESULT IS NULL AT WORLD SCALE and first-order domestically. Saying "
              "so in advance is the point: a twenty-tonne annual bid is a rounding error in the "
              "gold market and the whole story of Mongolian reserve accumulation"},
    {"id": "MN-F", "title": "The sovereign refinancing calendar as a dated credit event",
     "objects": ("the external repayment schedule by date and size",
                 "each liability-management and new-issue announcement",
                 "monthly budget execution and the royalty line that services it",
                 "the state miners' dividend obligations"),
     "conditions": ("the distance in weeks to the next hard-currency maturity",
                    "whether the commodity price over the prior quarter covered the coupon",
                    "whether a liability-management exercise has been announced"),
     "instruments": ("XCUUSD", "USDCNH", "AUDUSD"),
     "controls": ("matched windows with no maturity approaching",
                  "a frontier-Asia credit control over the same window, so a Mongolian claim is "
                  "not the region's risk appetite wearing a Mongolian hat",
                  "the commodity complex's own trend, which must be removed before any "
                  "refinancing effect is claimed"),
     "notes": "THE BOND ITSELF HAS NO BROKER INSTRUMENT and the pack says so; these cells "
              "terminate in the commodities that generate the receipt, which is a weaker claim "
              "honestly stated rather than a stronger one invented"},
    {"id": "MN-G", "title": "The dzud, the herd and the fibre crop",
     "objects": ("the December livestock census and the winter mortality reports",
                 "the meteorological agency's dzud risk maps by aimag",
                 "spring MACE auction volumes and clearing prices by grade",
                 "the rural credit book and the emergency response spending"),
     "conditions": ("the severity bucket of the winter, from the dzud risk maps",
                    "the year of the echo: the shock winter, the first spring after, or the "
                    "multi-year rebuild",
                    "whether the herd was above or below its own long-run carrying capacity "
                    "going into the winter"),
     "instruments": ("USDCNH", "AUDUSD", "XAUUSD"),
     "controls": ("mild winters with the same herd size, which is the base rate",
                  "the Chinese apparel and luxury cycle over the same seasons, which separates "
                  "a supply shock from a demand collapse",
                  "COTTON as an explicit SUBSTITUTE-FIBRE PLACEBO: a vegetable fibre with a "
                  "different growing season should NOT move with a Mongolian winter, and if it "
                  "does the finding is global and not Mongolian"),
     "notes": "the only MULTI-YEAR persistent supply shock in the pack. Cashmere has no broker "
              "symbol, so every cell here terminates in the currency and trade channel and the "
              "fibre price is an observable, never a target"},
    {"id": "MN-H", "title": "The Mongolian calendar, which is not the Chinese one",
     "objects": ("Tsagaan Sar day one on the Mongolian lunar calendar",
                 "Chinese New Year day one, read from the `cn` pack and never re-derived",
                 "the offset between them computed by `tsagaan_sar_gap`",
                 "the statutory five-day Naadam block on 11-15 July"),
     "conditions": ("the calendar offset bucket: coincident, within a week, or a month apart",
                    "whether the closure block falls wholly inside one week or straddles two",
                    "whether the year's lunar rows are GAZETTED or PROJECTED"),
     "instruments": ("CHINAH", "USDCNH", "AUDUSD"),
     "controls": ("the Chinese closure window in the same year, which is the whole point: when "
                  "the two calendars diverge the border has TWO separate stoppages and when "
                  "they coincide it has one",
                  "matched weeks with no closure at all",
                  "the Naadam block as the fixed-date placebo -- a statutory closure unrelated "
                  "to demand, which any genuine calendar effect must also show"),
     "notes": "THE PACK'S DISTINGUISHING CALENDAR FACT. A borrowed Chinese table is right when "
              "the gap is zero and wrong by the gap when it is not, which is the worst failure "
              "mode available: it looks right often enough to be trusted"},
    {"id": "MN-I", "title": "The mirror: two states counting one flow",
     "objects": ("Mongolian customs exports to China by commodity and value",
                 "Chinese customs imports from Mongolia by the same HS codes",
                 "the wedge between them in tonnage and in unit value",
                 "the transit stock sitting between the two measurement points"),
     "conditions": ("the sign and size of the tonnage wedge for the month",
                    "the sign and size of the UNIT VALUE wedge, which is a different object",
                    "whether the month contained a closure, a holiday block or a policy change"),
     "instruments": ("CHINAH", "USDCNH", "XCUUSD"),
     "controls": ("the historical mean wedge for the same month of year, because a structural "
                  "valuation difference is not an anomaly",
                  "a third-country mirror pair over the same months, which calibrates how large "
                  "a normal mirror wedge is anywhere",
                  "the transit-stock explanation, which must be exhausted before any "
                  "under-invoicing or smuggling reading is entertained"),
     "notes": "TWO INDEPENDENT PUBLIC MEASUREMENTS OF ONE PHYSICAL FLOW is a rare gift and the "
              "wedge is not automatically a scandal: valuation basis, timing and transit stock "
              "explain most of it, and the residual is what is worth testing"},
    {"id": "MN-J", "title": "Resource nationalism as a dated regime boundary",
     "objects": ("minerals-law amendments and windfall-tax episodes with their dates",
                 "licence moratoria and revocations visible in the MRPAM cadastre",
                 "the investment agreements and their renegotiations",
                 "the strategic-deposit designations"),
     "conditions": ("the era the date sits in, from POLICY_ERAS",
                    "whether the episode is a tightening or a reversal",
                    "whether the commodity price was at a cyclical high when it happened"),
     "instruments": ("XCUUSD", "CHINAH", "USDCNH"),
     "controls": ("matched windows with no legislative event",
                  "the commodity cycle over the same window, because these episodes CLUSTER at "
                  "price peaks and the price must be removed before the politics is claimed",
                  "a peer frontier-mining jurisdiction's episodes as the regional control"),
     "notes": "the episodes cluster at price peaks BY CONSTRUCTION -- resource nationalism is "
              "popular when the resource is expensive -- so the naive event study here is "
              "measuring the copper price and calling it Mongolian politics"},
    {"id": "MN-K", "title": "The Russian fuel dependency and the cost of every tonne-kilometre",
     "objects": ("monthly fuel imports by origin and product",
                 "announced Russian export restrictions and their dates",
                 "domestic wholesale and pump prices and the state's reserve releases",
                 "the border haulage cost that follows them"),
     "conditions": ("whether a Russian export restriction was in force in the window",
                    "the domestic fuel stock cover in days",
                    "the diesel cost per tonne-kilometre relative to the coal price"),
     "instruments": ("USDRUB", "XBRUSD", "XNGUSD"),
     "controls": ("matched periods with no disruption and the same coal price",
                  "the `ru` pack's own reading of the same Russian policy event, so this pack "
                  "measures the Mongolian consequence and never re-derives the Russian cause",
                  "world refined-product cracks over the same window, which separates a "
                  "bilateral quota event from a global refining event"),
     "notes": "a LANDLOCKED COUNTRY WITH ONE FUEL SUPPLIER has a transport cost set abroad; this "
              "is the channel through which a Moscow decision reaches a Mongolian mine's margin"},
    {"id": "MN-L", "title": "The domestic venue, the state IPO programme and the absent tape",
     "objects": ("MSE daily turnover, the TOP-20 index and the foreign share",
                 "the announced state mining IPO pipeline",
                 "retail securities-account openings",
                 "the complete absence of any listed derivative"),
     "conditions": ("whether an IPO or a placement is live in the window",
                    "the foreign share of turnover bucket",
                    "whether the commodity complex was rising or falling over the same weeks"),
     "instruments": ("HK50", "CHINAH", "XCUUSD"),
     "controls": ("matched windows with no listing activity",
                  "the Hong Kong listed Mongolian names' own behaviour, which belongs to the "
                  "event lane and is read as an observable only",
                  "the commodity complex itself, which must be removed before any domestic "
                  "equity signal is claimed"),
     "notes": "THE EXPECTED RESULT IS NULL and the domain exists to record that honestly: a "
              "venue whose whole daily turnover is smaller than one Hong Kong block trade "
              "cannot carry information into a global price, and a miner must be told so rather "
              "than discovering it as a silent failure"},
    {"id": "MN-M", "title": "The rest of the basket: zinc, fluorspar, uranium and rare earths",
     "objects": ("zinc concentrate exports and the Tumurtei-type operations behind them",
                 "fluorspar production, in which Mongolia is a world top-three supplier",
                 "the uranium development agreement and its milestones",
                 "the recurring policy interest in Mongolia as a non-Chinese critical-minerals "
                 "source"),
     "conditions": ("whether the window contained a critical-minerals policy announcement "
                    "naming Mongolia",
                    "the zinc export tonnage relative to its trailing year",
                    "whether the announcement was accompanied by a financing or an offtake"),
     "instruments": ("XZNUSD", "XALUSD", "XCUUSD"),
     "controls": ("matched windows with no announcement",
                  "the industrial-metals complex's own move, because a critical-minerals "
                  "headline arrives in a risk environment that moves everything",
                  "THE MIRROR CUSTOMS SERIES as the physical test: an announcement that never "
                  "shows up as tonnage is a sentiment channel and must be labelled one"),
     "notes": "this domain's honest state is that most of its objects are ANNOUNCEMENTS rather "
              "than flows; the customs control is what stops the pack from trading a press "
              "release as though it were a supply change"},
)

# --------------------------------------------------------------------------- cells
#: WHAT EACH DOMAIN MINTS. The horizon and mechanism family a cell inherits from its domain, so
#: a cell is never a cartesian product of nothing: every row below is one real condition this
#: pack's own data plane can evaluate against one symbol the box can actually trade.
DOMAIN_CELL_SPEC: dict[str, tuple[str, str]] = {
    "MN-A": ("commodity_supply", "0 to 10 sessions"),
    "MN-B": ("high_frequency_proxy", "0 to 5 sessions"),
    "MN-C": ("capacity_step", "1 to 4 quarters"),
    "MN-D": ("fx_regime", "1 to 20 sessions"),
    "MN-E": ("official_flow", "1 to 3 months"),
    "MN-F": ("sovereign_credit", "1 to 2 quarters"),
    "MN-G": ("supply_shock", "1 to 4 quarters"),
    "MN-H": ("calendar_event", "0 to 5 sessions"),
    "MN-I": ("mirror_statistics", "1 to 3 months"),
    "MN-J": ("regime_break", "1 to 4 quarters"),
    "MN-K": ("import_dependency", "1 to 3 months"),
    "MN-L": ("equity_mechanics", "0 to 10 sessions"),
    "MN-M": ("announcement_vs_flow", "1 to 2 quarters"),
}


def cells() -> tuple[dict[str, Any], ...]:
    """THE TESTABLE CELLS THIS PACK MINTS, for the one gauntlet.

    The cross product of each domain's own conditions with each domain's own EXECUTABLE
    instruments. It is a product and not a blow-up because both factors are already the pack's
    measured claims: a condition is a state this pack's data plane can evaluate, and an
    instrument is a symbol the broker registry carries. A domain that names three conditions and
    three instruments is claiming nine testable statements, and the pack writes all nine down
    rather than testing one and calling the country covered.
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
#: observable that carries it and the executable targets, so a Mongolian finding is measured
#: against the sibling that owns the other end rather than in isolation.
INTERACTIONS: tuple[dict[str, Any], ...] = (
    {"with": "cn",
     "mechanism": "ONE CUSTOMER, AND THAT IS THE WHOLE STRUCTURE. Roughly nine tenths of "
                  "Mongolian exports cross one land border into China, the coal is priced off "
                  "the Dalian curve, the trade is invoiced in renminbi, and Chinese customs "
                  "publishes the MIRROR of the flow by origin every month. The `cn` pack owns "
                  "the Chinese steel cycle, the customs release and the offshore renminbi; this "
                  "pack reads them and measures the Mongolian side against them rather than "
                  "re-deriving a single one of China's mechanics",
     "observable": "Chinese customs imports from Mongolia by HS code beside the Mongolian "
                   "customs export table, and the Ganqimaodu clearance count beside the "
                   "Gashuunsukhait one",
     "targets": ("CHINAH", "USDCNH", "XCUUSD"),
     "control": "the `cn` pack's own steel and coal-inventory study over the identical window; "
                "a Mongolian claim must beat China's own measurement of its own demand"},
    {"with": "au",
     "mechanism": "THE SEABORNE SUBSTITUTE AND THEREFORE THE CONTROL. Australian coking coal "
                  "competes for the same Chinese coke ovens the Mongolian land route feeds, so "
                  "the land route's pricing power is bounded by the seaborne landed cost. This "
                  "is what makes AUDUSD the pack's named control rather than a decoration: a "
                  "Mongolian border disruption that moves the coal complex the same way a "
                  "seaborne disruption of similar size does is a GLOBAL coal mechanism, not a "
                  "Mongolian one. The `au` pack owns the seaborne leg",
     "observable": "Australian coking coal exports and the seaborne landed cost against the "
                   "Mongolian border tonnage over the same months",
     "targets": ("AUDUSD", "CHINAH", "USDCNH"),
     "control": "matched seaborne-supply disruptions (weather, rail, port) of comparable size, "
                "which is the placebo any Mongolian supply claim must fail"},
    {"with": "ru",
     "mechanism": "THE OTHER NEIGHBOUR, AND THE ONE THAT SETS THE COST OF MOVING EVERYTHING. "
                  "Mongolia imports the overwhelming majority of its refined fuel from Russia "
                  "under intergovernmental arrangements, and the northern railway is a joint "
                  "venture. A Russian export restriction is therefore a direct input shock to "
                  "Mongolian haulage and mining costs, and the `ru` pack owns the Russian cause "
                  "while this pack measures the Mongolian consequence",
     "observable": "Mongolian monthly fuel imports by origin and the domestic wholesale price, "
                   "against the dated Russian export-policy announcements",
     "targets": ("USDRUB", "XBRUSD", "XNGUSD"),
     "control": "world refined-product cracks over the same window, which separates a bilateral "
                "quota event from a global refining event"},
    {"with": "kz",
     "mechanism": "THE SIBLING LANDLOCKED RESOURCE ECONOMY BETWEEN THE SAME TWO NEIGHBOURS. "
                  "Kazakhstan and Mongolia both export minerals across a Chinese land border "
                  "and both depend on Russian transit and inputs, so Kazakh series are the "
                  "natural control that separates 'the Chinese land-border resource trade "
                  "moved' from 'Mongolia moved'. The `kz` pack owns the Kazakh side",
     "observable": "Kazakh mineral exports to China and the Kazakh border throughput over the "
                   "same months as the Mongolian series",
     "targets": ("XCUUSD", "USDCNH", "USDRUB"),
     "control": "the Kazakh series itself as the placebo: a mechanism that fires in both is a "
                "Chinese land-border mechanism and belongs to neither pack alone"},
    {"with": "hk",
     "mechanism": "THE LISTING VENUE OF RECORD FOR MONGOLIAN MINING EQUITY. The Mongolian coal "
                  "and copper names that trade at all trade in Hong Kong, which is why HK50 and "
                  "CHINAH are this pack's equity carriers and why a Mongolian border headline "
                  "reprices inside the Hong Kong session. The `hk` pack owns the venue's "
                  "mechanics, the band and the Aggregate Balance; this pack reads them",
     "observable": "the Hong Kong session reaction to Mongolian border and production news, "
                   "against the same news' effect on the commodity legs",
     "targets": ("HK50", "CHINAH"),
     "control": "the `hk` pack's own session study over the identical window, so a Mongolian "
                "claim must beat Hong Kong's own measurement of its own session"},
    {"with": "kr",
     "mechanism": "THE OTHER END OF THE SAME STEEL CHAIN. Korean steelmakers buy the coking "
                  "coal Mongolia competes to supply and sit inside the same North Asian "
                  "industrial cycle, which makes Korean steel and trade series a demand-side "
                  "control on whether a Mongolian coal finding is supply or is North Asian "
                  "industrial demand wearing a Mongolian hat",
     "observable": "Korean steel output and the first-twenty-days export series over the same "
                   "months as the Mongolian border tonnage",
     "targets": ("CHINAH", "AUDUSD"),
     "control": "the Korean demand series itself; a coal move that tracks it is demand and a "
                "move that does not is the supply candidate"},
)

# --------------------------------------------------------------------------- transmission
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    {"id": "MN-T1",
     "source": "Oyu Tolgoi quarterly production against the published 2028-2036 ramp",
     "target": "XCUUSD", "targets": ("XCUUSD", "XALUSD"), "to_country": "global", "sign": "-",
     "mechanism": "a dated, sanctioned supply curve on the order of two per cent of world mine "
                  "supply; the market holds the schedule already, so the tradable object is the "
                  "DEVIATION from it and a downgrade is a supply loss the balance must absorb",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 0.0,
     "actor": "the Oyu Tolgoi operator", "constraint": "block-cave rock mechanics, not price",
     "flow": "scheduled supply into the world copper balance",
     "condition": "the realised quarter's deviation from `oyu_tolgoi_ramp` for that year",
     "control": "quarters where the operator's other assets drove the print; the ICSG world "
                "mine-supply series over the same quarters",
     "falsifier": "the report-window move matches the matched-hour control and matches quarters "
                  "with no Mongolian content, which would make it a diversified-miner effect",
     "evidence": "HYPOTHESIS"},
    {"id": "MN-T2",
     "source": "Gashuunsukhait-Ganqimaodu daily cleared vehicles",
     "target": "CHINAH", "targets": ("CHINAH", "USDCNH"), "to_country": "cn", "sign": "-",
     "mechanism": "the land route is the largest single source of China's imported coking coal "
                  "and it is counted daily by both states; a throughput collapse is a direct, "
                  "dated input-cost shock to the Chinese steel complex",
     "horizon": "0 to 5 sessions", "horizon_class": "intraday", "lag_days": 0.0,
     "actor": "the customs agencies and the haulage operators",
     "constraint": "clearance lanes and opening hours",
     "flow": "physical coal into coke ovens",
     "condition": "the throughput bucket from `border_throughput_state`",
     "control": "the Shiveekhuren-Ceke count over the same days; rail tonnage over the same "
                "months; seaborne coking coal and AUDUSD over the same window",
     "falsifier": "the move matches what a seaborne disruption of similar tonnage does, which "
                  "would make it a global coal mechanism and not a Mongolian one",
     "evidence": "HYPOTHESIS"},
    {"id": "MN-T3",
     "source": "The Tavantolgoi-Gashuunsukhait railway commissioning milestones",
     "target": "AUDUSD", "targets": ("AUDUSD", "CHINAH"), "to_country": "au", "sign": "-",
     "mechanism": "a dated step in the land route's capacity displaces seaborne tonnage at the "
                  "margin, which is a structural and permanent claim on the Australian "
                  "coking-coal share rather than a cyclical one",
     "horizon": "1 to 4 quarters", "horizon_class": "quarterly", "lag_days": 30.0,
     "actor": "the railway operator and the two states",
     "constraint": "a gauge break and a bilateral interchange agreement",
     "flow": "permanent capacity into the land route",
     "condition": "pre-commissioning, commissioning year, or post-connection era",
     "control": "the Shiveekhuren route, which the line does not serve and should not step; a "
                "placebo step at a random date in the same year",
     "falsifier": "total Mongolian coal exports show no level shift at the commissioning dates "
                  "once the Chinese steel cycle is controlled, meaning the line only re-routed",
     "evidence": "HYPOTHESIS"},
    {"id": "MN-T4",
     "source": "Bank of Mongolia FX auction size relative to the monthly import bill",
     "target": "USDCNH", "targets": ("USDCNH", "USDRUB"), "to_country": "cn", "sign": "+",
     "mechanism": "the auction is the pipe through which a renminbi export receipt becomes "
                  "domestic money and through which importers get dollars; auction intensity is "
                  "therefore a read on frontier dollar scarcity at the Chinese land border",
     "horizon": "1 to 20 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "the Bank of Mongolia", "constraint": "a small reserve stock against a "
                                                    "concentrated import bill",
     "flow": "official FX supply into the domestic market",
     "condition": "the accepted size relative to the trailing monthly import bill",
     "control": "the same state measured on days with no auction; the `cn` pack's own CNH "
                "behaviour over the identical window",
     "falsifier": "no differential CNH behaviour around auction days relative to matched days, "
                  "which is the EXPECTED result for a currency nobody can trade",
     "evidence": "HYPOTHESIS"},
    {"id": "MN-T5",
     "source": "Bank of Mongolia monthly domestic gold purchases in kilogrammes",
     "target": "XAUUSD", "targets": ("XAUUSD",), "to_country": "global", "sign": "+",
     "mechanism": "a published, dated, physical official bid for bullion from a central bank "
                  "that buys its own country's production; the flow is small at world scale and "
                  "the publication is unusually clean, which is exactly the shape a null result "
                  "should be measured in rather than assumed",
     "horizon": "1 to 3 months", "horizon_class": "monthly", "lag_days": 25.0,
     "actor": "the Bank of Mongolia", "constraint": "a reserve target and a royalty incentive",
     "flow": "physical gold from domestic producers into reserves",
     "condition": "the monthly tonnage relative to its trailing twelve-month mean",
     "control": "matched months with no unusual purchase; world central-bank purchases over the "
                "same quarters; the domestic tugrik gold price as the supply-side explanation",
     "falsifier": "no differential XAUUSD behaviour in the publication window, which is the "
                  "expected result and is declared in advance so a null is not reported as news",
     "evidence": "HYPOTHESIS"},
    {"id": "MN-T6",
     "source": "The sovereign external repayment schedule and liability-management events",
     "target": "USDCNH", "targets": ("USDCNH", "XCUUSD"), "to_country": "global", "sign": "+",
     "mechanism": "a frontier hard-currency maturity must be met out of a commodity receipt, so "
                  "the weeks around a known maturity are when the country's commodity cycle "
                  "becomes a credit question; the dates are public years in advance",
     "horizon": "1 to 2 quarters", "horizon_class": "quarterly", "lag_days": 5.0,
     "actor": "the Ministry of Finance", "constraint": "hard-currency debt against a "
                                                       "local-currency tax base",
     "flow": "export receipts into external debt service",
     "condition": "the distance in weeks to the next hard-currency maturity",
     "control": "matched windows with no maturity approaching; a frontier-Asia credit control; "
                "the commodity complex's own trend",
     "falsifier": "no differential behaviour in the commodity legs around known maturities, "
                  "which would mean the sovereign's cash need is too small to reach a price",
     "evidence": "HYPOTHESIS"},
    {"id": "MN-T7",
     "source": "The dzud severity maps and the winter livestock mortality series",
     "target": "USDCNH", "targets": ("USDCNH", "AUDUSD"), "to_country": "cn", "sign": "+",
     "mechanism": "a mortality shock is a multi-year supply shock in raw cashmere and wool, "
                  "which reaches the desk through the trade balance, the tugrik and the Chinese "
                  "buyer rather than through any fibre price the broker quotes",
     "horizon": "1 to 4 quarters", "horizon_class": "quarterly", "lag_days": 60.0,
     "actor": "the herder household", "constraint": "a herd that cannot be rebuilt in a season",
     "flow": "lost fibre crop into the export receipt and the rural credit book",
     "condition": "the severity bucket of the winter from the dzud risk maps",
     "control": "mild winters with the same herd size; the Chinese apparel cycle; COTTON as an "
                "explicit substitute-fibre placebo that should NOT move with a Mongolian winter",
     "falsifier": "COTTON moves with the dzud series as strongly as the Mongolian legs do, "
                  "which would prove the finding is a global fibre or risk effect",
     "evidence": "HYPOTHESIS"},
    {"id": "MN-T8",
     "source": "The Tsagaan Sar and Naadam statutory closure blocks",
     "target": "USDCNH", "targets": ("USDCNH", "CHINAH"), "to_country": "cn", "sign": "-",
     "mechanism": "the border, the customs posts and the haulage industry stop for statutory "
                  "days that are set by the MONGOLIAN lunar calendar and by Mongolian statute, "
                  "so in years when the two calendars diverge the flow has TWO separate "
                  "stoppages and in years when they coincide it has one",
     "horizon": "0 to 5 sessions", "horizon_class": "intraday", "lag_days": 0.0,
     "actor": "the state, through the holiday resolution",
     "constraint": "a statutory closure unrelated to demand",
     "flow": "a scheduled interruption in the physical export",
     "condition": "the calendar offset bucket from `tsagaan_sar_gap`",
     "control": "the Chinese closure window in the same year; matched weeks with no closure; "
                "the fixed-date Naadam block as the demand-independent placebo",
     "falsifier": "the closure effect is indistinguishable from the Chinese closure effect in "
                  "divergence years, which would mean the border stops for the buyer's calendar "
                  "and the Mongolian table adds nothing",
     "evidence": "HYPOTHESIS"},
    {"id": "MN-T9",
     "source": "The wedge between Mongolian export and Chinese import statistics",
     "target": "CHINAH", "targets": ("CHINAH", "XCUUSD"), "to_country": "cn", "sign": "+",
     "mechanism": "two states publish independent counts of one physical flow; after valuation "
                  "basis, timing and transit stock are removed, a persistent residual is "
                  "information about what is actually crossing and at what declared value",
     "horizon": "1 to 3 months", "horizon_class": "monthly", "lag_days": 20.0,
     "actor": "the two customs administrations",
     "constraint": "different valuation bases and different clocks",
     "flow": "the same coal and concentrate, counted twice",
     "condition": "the sign and size of the tonnage and unit-value wedges for the month",
     "control": "the historical mean wedge for the same month of year; a third-country mirror "
                "pair as the calibration of what a normal wedge looks like anywhere",
     "falsifier": "the residual wedge is fully explained by transit stock and the month-of-year "
                  "mean, leaving nothing to test",
     "evidence": "MEASURED_ELSEWHERE"},
    {"id": "MN-T10",
     "source": "Russian refined-product export restrictions and the Mongolian fuel stock",
     "target": "USDRUB", "targets": ("USDRUB", "XBRUSD"), "to_country": "ru", "sign": "+",
     "mechanism": "a landlocked country with one fuel supplier has a tonne-kilometre cost set "
                  "abroad; a Russian restriction raises Mongolian haulage costs and compresses "
                  "mine-gate margins within weeks, which is a real bilateral channel and not a "
                  "correlation with the oil price",
     "horizon": "1 to 3 months", "horizon_class": "monthly", "lag_days": 10.0,
     "actor": "the Russian supplier and the Mongolian importers",
     "constraint": "no alternative route at scale",
     "flow": "imported diesel into the cost of every exported tonne",
     "condition": "whether a Russian export restriction was in force and the stock cover in days",
     "control": "matched periods with no disruption and the same coal price; world refined "
                "cracks over the same window; the `ru` pack's own reading of the same event",
     "falsifier": "the Mongolian effect is fully explained by the world crack, which would make "
                  "it a global refining story and not a bilateral one",
     "evidence": "HYPOTHESIS"},
    {"id": "MN-T11",
     "source": "Minerals-law amendments, windfall-tax episodes and licence moratoria",
     "target": "XCUUSD", "targets": ("XCUUSD", "CHINAH"), "to_country": "global", "sign": "+",
     "mechanism": "a resource-nationalism episode raises the expected cost of future Mongolian "
                  "supply and is dated precisely in the legal database and in the licence "
                  "cadastre; the claim is about the forward supply curve, not about today's "
                  "tonnage",
     "horizon": "1 to 4 quarters", "horizon_class": "quarterly", "lag_days": 1.0,
     "actor": "the State Great Khural", "constraint": "a budget that depends on the investors "
                                                      "being pressured",
     "flow": "regulatory risk into the cost of future supply",
     "condition": "whether the episode is a tightening or a reversal, and the commodity price "
                  "level when it happened",
     "control": "matched windows with no legislative event; THE COMMODITY CYCLE ITSELF, because "
                "these episodes cluster at price peaks by construction; a peer frontier-mining "
                "jurisdiction's episodes",
     "falsifier": "the effect disappears once the copper price's own trend is removed, which "
                  "would mean the event study was measuring the price that caused the politics",
     "evidence": "HYPOTHESIS"},
)

# --------------------------------------------------------------------------- policy eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    {"name": "post-socialist transition and the first mining opening",
     "start": "1990-01-01", "end": "2009-10-05",
     "regime": "a newly democratic economy with a nascent minerals law, foreign exploration "
               "arriving, Erdenet as the only large operating mine and a currency that had to "
               "be invented as a market price",
     "markers": ("1990 the democratic transition", "1997 the Minerals Law",
                 "2006 the windfall-profit tax on copper and gold"),
     "why_it_matters": "there is no Oyu Tolgoi and no coal border trade of consequence here; a "
                       "study that pools this era with the modern one is averaging two "
                       "different economies and calling the mean a mechanism",
     "status": "SETTLED"},
    {"name": "the Oyu Tolgoi investment agreement and the first commodity boom",
     "start": "2009-10-06", "end": "2016-05-31",
     "regime": "the investment agreement signed, construction at scale, the coal export trade to "
               "China taking off, a credit and property boom in Ulaanbaatar, and then the bust "
               "as Chinese demand slowed and the agreement was disputed",
     "markers": ("2009-10-06 the Oyu Tolgoi investment agreement",
                 "2012 the Chinggis eurobond issue",
                 "2013 the strategic-entities foreign-investment law and the investment collapse"),
     "why_it_matters": "the boom-era elasticities are fitted on an economy whose binding "
                       "constraint was capital inflow; the modern one's binding constraint is "
                       "physical export capacity, which is a different model entirely",
     "status": "SETTLED"},
    {"name": "the reserve crisis and the IMF programme",
     "start": "2016-06-01", "end": "2020-01-31",
     "regime": "reserves fell hard, the tugrik weakened sharply, an Extended Fund Facility with "
               "a bilateral package around it ran from 2017, and fiscal consolidation and a "
               "renminbi swap line carried the external position",
     "markers": ("2016 the reserve drawdown and the emergency rate rise",
                 "2017 the IMF Extended Fund Facility",
                 "2018-2019 the recovery in coal volumes"),
     "why_it_matters": "THE TUGRIK'S BEHAVIOUR IN THIS WINDOW IS NOT THE TUGRIK'S BEHAVIOUR "
                       "NOW: a managed float under programme conditionality is a different "
                       "regime from a managed float with a record export receipt behind it",
     "status": "SETTLED"},
    {"name": "the border closure",
     "start": "2020-02-01", "end": "2022-12-31",
     "regime": "the pandemic closed the land border to normal traffic; truck counts fell to a "
               "small fraction of normal, coal exports collapsed, and the Chinese buyer "
               "substituted toward seaborne and domestic supply",
     "markers": ("2020-02 the first border restrictions",
                 "2021 the contactless-handover arrangements at Gashuunsukhait",
                 "2022 the phased reopening"),
     "why_it_matters": "THE BUILT-IN NATURAL EXPERIMENT AND THE BUILT-IN PLACEBO AT ONCE. It is "
                       "the cleanest supply interruption the series contains, and it is also "
                       "the window in which every Mongolian macro variable moved for a reason "
                       "that had nothing to do with Mongolia",
     "status": "SETTLED"},
    {"name": "reopening, the underground ramp and the railway",
     "start": "2023-01-01", "end": "2026-12-31",
     "regime": "record coal export volumes, Oyu Tolgoi's underground block cave in sustainable "
               "production and ramping, the Tavantolgoi-Gashuunsukhait railway carrying volume, "
               "the New Recovery Policy's border-capacity programme, and a state-IPO programme "
               "intended to monetise the coal field",
     "markers": ("2023-03 sustainable underground production at Oyu Tolgoi",
                 "2023-2024 record coking-coal export tonnage to China",
                 "2024 the cross-border rail connection and the mining-IPO programme"),
     "why_it_matters": "the current regime and the only one whose data the desk can actually "
                       "trade; it is a few years long, which bounds every cell fitted inside it "
                       "and is stated rather than worked around",
     "status": "OPEN"},
    {"name": "the guided copper plateau",
     "start": "2027-01-01", "end": "2036-12-31",
     "regime": "the published guidance window in which Oyu Tolgoi averages around 500 kt of "
               "copper a year with the open pit and the block cave running together, making "
               "Mongolia a structurally larger share of world mine supply than it has ever been",
     "markers": ("2028 the guided plateau begins", "2036 the guided plateau ends"),
     "why_it_matters": "DECLARED IN ADVANCE BECAUSE IT IS PUBLISHED IN ADVANCE. A forward regime "
                       "boundary is exactly as important as a historical one: a cell fitted "
                       "today on the ramp years will not be exchangeable with the plateau "
                       "years, and the pack records the boundary before it arrives",
     "status": "SCHEDULED"},
)

ACCESS_CONSTRAINTS: tuple[dict[str, Any], ...] = (
    {"constraint": "the tugrik is not quoted by this broker",
     "measured": "data/universe/universe.json holds no MNT symbol",
     "consequence": "every domestic monetary mechanism terminates in USDCNH, USDRUB, XAUUSD or "
                    "the metals complex; MNT is an INPUT, never a cell"},
    {"constraint": "COKING COAL, THE COUNTRY'S LARGEST EXPORT, HAS NO BROKER SYMBOL",
     "measured": "the universe carries no coal contract of any kind",
     "consequence": "the coal mechanism is routed through CHINAH, USDCNH and AUDUSD with the "
                    "seaborne substitute named as the control; the pack states this as a "
                    "weakened claim rather than proxying coal with an unrelated energy symbol"},
    {"constraint": "cashmere and wool have no broker symbol either",
     "measured": "the universe's only fibre contract is COTTON, a vegetable fibre with a "
                 "different growing season and a different demand cycle",
     "consequence": "COTTON is used as an explicit SUBSTITUTE-FIBRE PLACEBO that should NOT "
                    "move with a Mongolian winter, and never as cashmere's carrier"},
    {"constraint": "the listed Mongolian miners are single names",
     "measured": "Mongolian Mining Corporation and its peers are listed in Hong Kong and on the "
                 "MSE",
     "consequence": "EVENT LANE ONLY under the two-lane order (2026-09-06). They appear as "
                    "actors and observables and never as an executable instrument, a domain "
                    "instrument or an edge target"},
    {"constraint": "customs and the statistics office overwrite their current-year tables",
     "measured": "the monthly workbooks are replaced rather than versioned",
     "consequence": "the as-published first print of a month is recoverable only from a "
                    "same-week crawl or a web-archive snapshot; a cell compiled on an "
                    "un-archived month is UNMEASURED rather than assumed to be the first print"},
    {"constraint": "the MRPAM cadastre is a LIVE register that keeps no history of itself",
     "measured": "a revoked or transferred licence leaves no trace in the current register",
     "consequence": "resource-nationalism cells require MONTHLY SNAPSHOTS of the cadastre to "
                    "exist at all; without them MN-J is a narrative domain and is labelled one"},
    {"constraint": "the physical coking-coal price assessments forbid machine extraction",
     "measured": "the commercial assessment services are LICENSED and their terms prohibit "
                 "automated collection (machine_use_allowed=false on that source row)",
     "consequence": "REGISTERED AND NEVER SCRAPED. The public Dalian curve is used as the "
                    "tradable proxy and the realised border discount is UNMEASURED by name"},
    {"constraint": "there is no tugrik positioning series and no domestic derivatives market",
     "measured": "no COT contract, no exchange future, no listed option, no margin statistics",
     "consequence": "positioning and expiry miners report UNMEASURED by name; the CNH and RUB "
                    "legs are positions in OTHER countries' currencies and are never substituted"},
    {"constraint": "the Bank of Mongolia's decision calendar has not been read",
     "measured": "CENTRAL_BANK.decision_dates is empty and dates_status says so",
     "consequence": "no event study on Mongolian rate-decision dates may be promoted from this "
                    "pack until a crawler reads the published schedule; a guessed calendar "
                    "would stamp every event to a wrong day and manufacture a clean null"},
    {"constraint": "a truck count is a proxy for a tonnage and the conversion is an assumption",
     "measured": "TONNES_PER_TRUCK is an order-of-magnitude figure, not a measurement",
     "consequence": "`border_throughput_state`'s implied tonnage is a NOWCAST whose error "
                    "against the customs tonnage is itself reported; a persistent divergence is "
                    "a measurement about the conversion or the valuation, never smoothed away"},
    {"constraint": "the 2026 holiday table is PROJECTED, not gazetted",
     "measured": "the Cabinet resolution fixing 2026 has not been read, so every lunar row that "
                 "year is this pack's own computation",
     "consequence": "a calendar cell compiled on a 2026 lunar date is a hypothesis and may "
                    "never be promoted on that row alone; the status field says which is which"},
)

INSTITUTIONAL_FLOW_SOURCES: tuple[str, ...] = (
    "Bank of Mongolia FX auction accepted amounts and rates",
    "Bank of Mongolia monthly domestic gold purchases in kilogrammes",
    "Mongolian customs monthly exports by commodity and destination",
    "Chinese customs monthly imports from Mongolia by HS code (the mirror)",
    "Daily border-crossing vehicle counts at Gashuunsukhait, Shiveekhuren and Zamyn-Uud",
    "Tavantolgoi-Gashuunsukhait rail loadings",
    "Mongolian Agricultural Commodity Exchange cashmere and wool auction volumes",
    "Ministry of Finance monthly budget execution and the royalty line",
)

SERIES: dict[str, str] = {
    "MN_EXPORTS": "MNCUSTOMS:exports_by_commodity",
    "MN_COAL_EXPORT": "MNCUSTOMS:coal_export_tonnes",
    "MN_CU_CONC_EXPORT": "MNCUSTOMS:copper_concentrate_tonnes",
    "MN_MIRROR_CN": "CNCUSTOMS:imports_from_mongolia",
    "MN_BORDER_TRUCKS": "MN:border_trucks_per_day",
    "MN_RAIL_TONNES": "UBTZ:tavantolgoi_line_tonnes",
    "MN_OT_COPPER": "OT:quarterly_copper_kt",
    "MN_OT_RAMP": "computed:oyu_tolgoi_ramp(year)",
    "MN_POLICY_RATE": "BoM:policy_rate",
    "MN_OFFICIAL_RATE": "BoM:official_mnt_rate",
    "MN_FX_AUCTION": "BoM:fx_auction_accepted",
    "MN_RESERVES": "BoM:reserves_usd",
    "MN_GOLD_PURCHASES": "BoM:gold_purchases_kg",
    "MN_CPI": "NSO:cpi",
    "MN_HERD": "NSO:livestock_census",
    "MN_DZUD": "NAMEM:dzud_risk_index",
    "MN_CASHMERE_AUCTION": "MACE:cashmere_auction_volume",
    "MN_BUDGET": "MoF:budget_execution",
    "MN_EXT_DEBT": "MoF:external_repayment_schedule",
    "MN_MSE_TOP20": "MSE:top20_index",
    "MN_FUEL_IMPORT": "MNCUSTOMS:fuel_imports_by_origin",
    "MN_CALENDAR_GAP": "computed:tsagaan_sar_gap(year)",
}

# --------------------------------------------------------------------------- the pack's miners
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    {"name": "mn_copper_ramp_clock", "domain_ids": ("MN-A", "MN-M"), "kind": "commodity",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.mn.pack:mine_copper_ramp",
     "needs": ("OT_RAMP", "WORLD_MINE_SUPPLY_KT", "XCUUSD D1 bars"),
     "notes": "the published ramp as a year-by-year supply curve with the world-supply share "
              "and the STATUS of each number, so an interpolated year is never mined as guidance"},
    {"name": "mn_border_throughput", "domain_ids": ("MN-B", "MN-C", "MN-K"), "kind": "physical",
     "cadence_s": 3600.0, "steerable": True, "wired": False,
     "entry": "countries.mn.pack:mine_border_throughput",
     "needs": ("BORDER_BUCKETS", "TONNES_PER_TRUCK", "the daily crossing counts"),
     "notes": "the truck-count regime buckets and the tonnage each implies, with the "
              "Shiveekhuren and rail controls named on every row"},
    {"name": "mn_calendar_divergence", "domain_ids": ("MN-H",), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": False, "wired": False,
     "entry": "countries.mn.pack:mine_calendar_divergence",
     "needs": ("LUNAR_GENERAL", "CHINESE_NEW_YEAR", "FIXED_GENERAL"),
     "notes": "the Mongolian-versus-Chinese lunar offset per year and the statutory closure "
              "blocks, which is the pack's own distinguishing calendar measurement"},
    {"name": "mn_regime_boundaries", "domain_ids": ("MN-J", "MN-F", "MN-D"), "kind": "event",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.mn.pack:mine_regime_boundaries",
     "needs": ("POLICY_ERAS", "XCUUSD, CHINAH, USDCNH D1 bars"),
     "notes": "the dated era table including the SCHEDULED forward boundary at the guided "
              "copper plateau, with the closure years flagged as the built-in placebo"},
    {"name": "mn_transmission_seeds",
     "domain_ids": ("MN-E", "MN-G", "MN-I", "MN-L"),
     "kind": "transfer", "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.mn.pack:mine_transmission_seeds",
     "needs": ("TRANSMISSION_EDGES_SEED", "INTERACTIONS"),
     "notes": "the pack's map and its sibling interactions as HYPOTHESIS discoveries, "
              "deduplicated by the registry"},
)

MINER_DOMAINS: dict[str, tuple[str, ...]] = {
    "central_bank_surprise": ("MN-D",), "release_surprise": ("MN-A", "MN-I"),
    "calendar_settlement": ("MN-H",), "holiday_liquidity": ("MN-H",),
    "positioning": ("MN-D",), "carry_funding": ("MN-D", "MN-F"),
    "corporate_flow": ("MN-A", "MN-L"), "institutional_flow": ("MN-E", "MN-F"),
    "equity_mechanics": ("MN-L",), "derivatives_expiry": ("MN-L",),
    "failure": ("MN-J", "MN-K"), "residual": ("MN-I", "MN-M"),
    "transfer": ("MN-B", "MN-C"), "scouts": ("MN-G", "MN-M"),
    "session_microstructure": ("MN-L", "MN-B"),
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
        "mission": MISSION, "ramp": oyu_tolgoi_ramp(2028),
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
    """The keyword set `country_lab.CountryPack` is built from, in the shapes its coercion reads
    best: sources as rows AND as tagged lines, positioning and miners as strings, the holiday
    rule as dates, absent layers as a mapping."""
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
def mine_copper_ramp(pack_obj: Any = None, ctx: Any = None) -> dict[str, Any]:
    """MN-A / MN-M: the published Oyu Tolgoi ramp, year by year, with the world-supply share and
    the STATUS of each number. The status is the point -- a guided year and an interpolated year
    are different research objects and a cell fitted on the second is fitted on arithmetic."""
    rows = [oyu_tolgoi_ramp(year) for year in sorted(OT_RAMP)]
    return {"miner": "mn_copper_ramp_clock", "domain_ids": ("MN-A", "MN-M"), "rows": tuple(rows),
            "n": len(rows), "symbols": ("XCUUSD", "XAUUSD", "XALUSD"),
            "control": "the ICSG world mine-supply series over the same years; a Mongolian "
                       "share change must beat the world balance to be Mongolia's"}


def mine_border_throughput(pack_obj: Any = None, ctx: Any = None) -> dict[str, Any]:
    """MN-B / MN-C / MN-K: the border's regime buckets as states a cell conditions on, with the
    tonnage each implies. No data is fetched: the buckets are the pack's own measured regimes
    and the conversion's uncertainty is reported rather than smoothed."""
    probes = (0.0, 150.0, 400.0, 900.0, 1400.0, 1900.0)
    rows = [dict(border_throughput_state(n), probe=n) for n in probes]
    return {"miner": "mn_border_throughput", "domain_ids": ("MN-B", "MN-C", "MN-K"),
            "rows": tuple(rows), "n": len(rows), "symbols": ("CHINAH", "USDCNH", "AUDUSD"),
            "control": "the Shiveekhuren-Ceke count over the same days and the rail tonnage "
                       "over the same months; without both, a route change reads as a collapse"}


def mine_calendar_divergence(pack_obj: Any = None, ctx: Any = None) -> dict[str, Any]:
    """MN-H: the Mongolian lunar calendar against the Chinese one, year by year, plus the
    statutory Naadam block. THE OFFSET IS THE MEASUREMENT: a borrowed Chinese table is right
    when the gap is zero and wrong by the gap when it is not."""
    rows: list[dict[str, Any]] = []
    for year in HOLIDAYS_RULE["years"]:
        y = int(year)
        gap = tsagaan_sar_gap(y)
        rows.append({**gap, "naadam": [d.isoformat() for d in naadam_block(y)],
                     "n_market_holidays": len(market_holidays(y)),
                     "symbols": ("CHINAH", "USDCNH", "AUDUSD")})
    return {"miner": "mn_calendar_divergence", "domain_ids": ("MN-H",), "rows": tuple(rows),
            "n": len(rows), "symbols": ("CHINAH", "USDCNH", "AUDUSD"),
            "control": "the Chinese closure window in the same year, and the fixed-date Naadam "
                       "block as the demand-independent placebo"}


def mine_regime_boundaries(pack_obj: Any = None, ctx: Any = None) -> dict[str, Any]:
    """MN-J / MN-F / MN-D: the dated boundaries that make a pooled Mongolian study invalid,
    emitted as the era table a cell must be fitted inside -- including the SCHEDULED forward
    boundary at the guided copper plateau, which is published and therefore knowable now."""
    rows = [{"era": str(e["name"]), "start": str(e["start"]), "end": str(e["end"]),
             "status": str(e["status"]), "markers": tuple(e["markers"]),
             "invalidates": str(e["why_it_matters"])} for e in POLICY_ERAS]
    return {"miner": "mn_regime_boundaries", "domain_ids": ("MN-J", "MN-F", "MN-D"),
            "rows": tuple(rows), "n": len(rows), "symbols": ("XCUUSD", "CHINAH", "USDCNH"),
            "control": "the commodity cycle over the same windows, because resource-nationalism "
                       "episodes cluster at price peaks by construction; the 2020-22 closure as "
                       "the built-in placebo where a policy proxy must NOT fire"}


def mine_transmission_seeds(pack_obj: Any = None, ctx: Any = None) -> dict[str, Any]:
    """The pack's own map and its sibling interactions, as HYPOTHESIS rows the registry
    deduplicates. Nothing here is a measurement and every row says so."""
    rows = [{"id": str(e["id"]), "targets": tuple(e["targets"]), "evidence": str(e["evidence"]),
             "falsifier": str(e["falsifier"]), "control": str(e["control"])}
            for e in TRANSMISSION_EDGES_SEED]
    rows += [{"id": f"MN-X:{r['with']}", "targets": tuple(r["targets"]),
              "evidence": "HYPOTHESIS", "falsifier": str(r["control"]),
              "control": str(r["control"])} for r in INTERACTIONS]
    return {"miner": "mn_transmission_seeds",
            "domain_ids": ("MN-E", "MN-G", "MN-I", "MN-L"),
            "rows": tuple(rows), "n": len(rows),
            "control": "every row is HYPOTHESIS until the gauntlet says otherwise"}


#: name -> callable, so the two registrations (CUSTOM_MINERS and this) are ONE set and a test
#: can assert it rather than trusting it.
MINERS: dict[str, Any] = {
    "mine_copper_ramp": mine_copper_ramp,
    "mine_border_throughput": mine_border_throughput,
    "mine_calendar_divergence": mine_calendar_divergence,
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
