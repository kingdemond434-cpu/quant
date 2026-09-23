"""BLACK SEA: the grain corridor, the potash route, and two currencies the broker does not quote.

WHAT THIS PACK IS AND WHY UKRAINE AND BELARUS ARE ONE PACK. Six mechanisms belong to this pair
of economies and to no other in the desk's book, and each one is why a domain below exists
rather than a row inside a generic emerging-market domain:

  1. THE BLACK SEA GRAIN INITIATIVE IS A PUBLISHED, VESSEL-BY-VESSEL NATURAL EXPERIMENT. From
     2022-07-22 to 2023-07-17 the Joint Coordination Centre in Istanbul published, in public,
     every outbound vessel, its cargo, its tonnage, its destination and the date its inspection
     cleared. There is almost nothing else like it: a high-frequency PHYSICAL FLOW series, with
     a signature date and a termination date, running against WHEAT and CORN -- two of the most
     liquid futures on earth. The initiative also SUSPENDED and RESUMED on dated days
     (2022-10-29 to 2022-11-02) and was renewed on shortening terms (120 days, then 60, then
     60), each renewal an announcement with its own minute. UA-A exists for this and nothing
     else, and it is the cleanest event ground in the whole department.

  2. THE CORRIDOR THAT REPLACED IT IS A DIFFERENT OBJECT AND MUST NOT BE POOLED WITH IT. The
     Ukrainian maritime corridor announced by the Navy on 2023-08-10 hugs Bulgarian, Romanian
     and Turkish territorial waters, carries no Russian inspection, and is insured rather than
     negotiated. Its throughput eventually EXCEEDED the BSGI's. A study that pools July 2022 to
     July 2023 with August 2023 onward is averaging a negotiated regime and a defended one.

  3. THE HRYVNIA HAS THREE NAMED WARTIME ERAS AND EACH INVALIDATES A POOLED STUDY. The National
     Bank fixed the official rate on 2022-02-24, devalued it about 25% to 36.5686 on 2022-07-21,
     and moved to MANAGED FLEXIBILITY on 2023-10-03. UAH is not quoted by this broker, which is
     exactly why the eras matter: the mechanism reaches the desk through the EU and IMF support
     flow, the Polish and Hungarian crosses, and the grain basis -- and all three behave
     differently in each era.

  4. BELARUS IS ABOUT A FIFTH OF WORLD POTASH AND ITS ROUTE WAS CLOSED BY A DATE. EU measures
     from June 2021, US measures on Belaruskali (2021-08-09) and on BPC (2021-12-08, wind-down
     to 2022-04-01), and Lithuania's termination of rail transit to Klaipeda FROM 2022-02-01
     took roughly a fifth of world supply off its normal route. Potash is not a broker symbol.
     The pack therefore routes it EXPLICITLY -- through fertiliser affordability into CORN,
     WHEAT and SOYBEAN acreage economics, and through Belarusian rail re-routing into the
     Russian Baltic and the Chinese ports -- and says so in `TRANSMISSION_TARGETS`. The
     direction is declared as an INPUT-cost claim; the pack never says Minsk pushes Chicago.

  5. THE BELARUSIAN RUBLE'S PEG IS A PUBLISHED BASKET, WHICH MAKES ITS ROUBLE BETA MEASURABLE
     RATHER THAN ESTIMATED. The National Bank of the Republic of Belarus publishes the basket's
     COMPOSITION AND ITS WEIGHTS. That is rare: almost every managed currency's basket is
     inferred by regression. Here the weights are given, so the implied rouble beta is
     arithmetic, the residual is the policy, and BY-D is a real hypothesis rather than a fit.

  6. THE GAS AND THE GRID ARE DATED PHYSICAL SERIES INTO EUROPEAN PRICES. Ukraine's five-year
     gas transit contract expired 2024-12-31 and flows stopped on 2025-01-01; the Druzhba crude
     line runs through both countries; Ukrenergo publishes the grid's state and the strikes on
     it are dated; the Zaporizhzhia plant's status is reported by the IAEA. Every one of them is
     a European gas, power and industrial-cost observable, which is XNGUSD, GER40 and EUSTX50.

WHAT IS EXECUTABLE AND WHAT IS NOT. UAH and BYN are ABSENT from `data/universe/universe.json`,
and so are the potash and fertiliser assessments, the Odesa FOB grain basis, the Ukrainian
eurobonds and GDP warrants, the TTF gas benchmark and the Ukrainian day-ahead power price. Every
one is named in `TRANSMISSION_TARGETS` with the broker symbols its mechanism reaches, so an
absent instrument mints a transmission hypothesis and never a cell that can never be filled
(L1.49).

THE TWO-LANE ORDER (2026-09-06). MHP, Kernel, Astarta, ArcelorMittal Kryvyi Rih, Belaruskali,
Naftan and Ukrnafta are every one of them a single name. They appear in this pack as ACTORS ONLY.
No share CFD appears in any instrument tuple in this file, and the instruments those actors move
are the softs, the energy legs, the European indices and the euro crosses.

LAWFULNESS, STATED ONCE HERE AND AGAIN IN `ACCESS_CONSTRAINTS`. Both jurisdictions are under
sanctions regimes. Nothing in this pack touches a sanctioned entity's private systems and nothing
bypasses an access control. Everything here is PUBLIC official statistics, PUBLIC
international-organisation data (FAO AMIS, UN Comtrade, IGC, USDA FAS GAIN, the UN's own
published BSGI vessel table) and PUBLIC press. Sanctions constrain TRANSACTIONS, not the reading
of published statistics -- and this desk executes broker symbols only, never a Ukrainian or a
Belarusian instrument.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Any

# ruff: noqa: RUF001
# RUF001 flags Cyrillic characters that look like Latin ones. They exist to catch homoglyph
# attacks in IDENTIFIERS. This file carries Ukrainian, Russian and Belarusian terminology as
# DATA, because a text screen that cannot match "зерновий коридор" or "калійныя ўгнаенні"
# cannot find the ministry's own headline. Suppressed file-wide and explained here rather than
# scattered as per-line noqa; no identifier in this module is non-ASCII.

# --------------------------------------------------------------------------- identity
CODE = "BLACK_SEA"
NAME = "Black Sea grain and fertiliser plane (Ukraine, Belarus)"
REGION_COMMAND = "russia_cis"      # the framework's command; the forest is russia_cis
REGION_DESK = "BLACK_SEA"
FOREST = "russia_cis"

#: THE ISO-2 CODES THIS PACK ANSWERS FOR. `scripts/check_regional_parity.py::jurisdictions_of`
#: reads this tuple and nothing else; both are on the `russia_cis` forest's roster in
#: `libs/research/forests.py` and both were UNANSWERED before this pack.
JURISDICTIONS: tuple[str, ...] = ("ua", "by")
#: The framework carries ONE currency field. Both are declared here so no jurisdiction is
#: silently represented by the other's money -- and NEITHER is quoted by the broker.
CURRENCIES: dict[str, str] = {"ua": "UAH", "by": "BYN"}
CURRENCY = "UAH"
FISCAL_YEAR_END = "12-31"          # both budgets run the calendar year
#: FOUR LANGUAGES AND THE PACK MEANS ALL FOUR. Ukrainian is the language of the laws, the
#: ministry and the agrarian trade press; RUSSIAN IS STILL READ AND WRITTEN IN UKRAINE and is
#: the working language of a large part of the grain trade and of APK-Inform's own copy, so a
#: Ukrainian-only crawl misses half the commercial ground; Belarusian is the language of the
#: statute book (pravo.by) and of the independent press in exile; Russian is the working
#: language of the Belarusian state, the NBRB and BELTA. English reads neither country.
NATIVE_LANGUAGES: tuple[str, ...] = ("uk", "ru", "be", "en")
COT_CURRENCY = ""                  # no CFTC contract exists for UAH or BYN
EXPORT_ECONOMY = "agricultural_exporter"
RETAIL_LEVERAGE_REGIME = "restricted"   # NBU currency controls since 2022-02-24; NBRB licensing
MISSION = ("mine Ukraine and Belarus as the dated physical-route economies they are: the Black "
           "Sea Grain Initiative's published vessel table and its termination, the Ukrainian "
           "maritime corridor that replaced it, the Danube ports and the solidarity lanes with "
           "the neighbours' 2023 import bans, the hryvnia's three wartime eras, the grid war "
           "and the gas-transit expiry, Belarusian potash and the Lithuanian transit "
           "termination, the Mozyr and Naftan refineries on the Druzhba, and the NBRB's "
           "PUBLISHED currency basket whose rouble beta is arithmetic rather than a regression")

#: The instruments this pack may compile a cell against. Every one is in the broker registry and
#: none is a single-name equity. UAH and BYN are absent (see TRANSMISSION_TARGETS).
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "WHEAT", "CORN", "SOYBEAN",            # the grain corridor and the fertiliser input
    "SUGAR", "COTTON",                     # the acreage substitutes the nutrient cost reaches
    "XNGUSD", "XBRUSD", "XTIUSD",          # transit, Druzhba, the refineries, the grid
    "USDRUB", "EURRUB",                    # the rouble leg of the Belarusian basket
    "EURPLN", "USDPLN",                    # the solidarity lanes and the border blockades
    "EURHUF", "EURCZK",                    # the other banning neighbours and the CEE basis
    "EURTRY", "USDTRY",                    # Istanbul: the JCC, the TMO and the marginal miller
    "GER40", "EUSTX50",                    # European industrial cost: gas, fertiliser, steel
    "EURUSD", "XAUUSD",                    # the euro leg and the escalation hedge
)

#: WHAT THE BOX CANNOT QUOTE, NAMED WITH WHAT CARRIES IT. An absent instrument produces a
#: transmission hypothesis, never a cell that can never be compiled (L1.49).
TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "USD/UAH and EUR/UAH (the NBU official rate)",
     "venue": "National Bank of Ukraine / the domestic interbank market",
     "why": "the currency UA-D is about, absent from the broker. Three named eras -- the "
            "fix of 2022-02-24, the 36.5686 devaluation of 2022-07-21 and managed flexibility "
            "from 2023-10-03 -- each of which invalidates a study pooled across it. The "
            "mechanism reaches the desk through the EU and IMF support flow, the Polish crosses "
            "and the grain basis",
     "proxies": ("EURPLN", "USDPLN", "EURUSD", "WHEAT")},
    {"name": "The Ukrainian cash and card (parallel) hryvnia rate and its spread to the NBU fix",
     "venue": "licensed exchange offices and the card-settlement rate",
     "why": "the second price of the hryvnia under wartime capital controls; its spread to the "
            "official rate is the control-stress state UA-D conditions on, and the banks "
            "publish both sides of it daily",
     "proxies": ("EURPLN", "XAUUSD")},
    {"name": "BYN and the NBRB currency basket (the published RUB / USD / CNY-or-EUR weights)",
     "venue": "National Bank of the Republic of Belarus / the BCSE continuous double auction",
     "why": "a rare EXPLICITLY PUBLISHED basket, which makes the implied rouble beta arithmetic "
            "rather than a regression; BYN is absent from the broker, so the beta is tested on "
            "the rouble leg the basket itself names",
     "proxies": ("USDRUB", "EURRUB", "EURUSD")},
    {"name": "Potash (MOP) contract and spot assessments -- Argus, CRU, Profercy, ICIS",
     "venue": "price reporting agencies and the annual China and India contract settlements",
     "why": "THE PRICE OF THE THING BELARUS SELLS, and it is paywalled. Registered here with "
            "machine_use_allowed=false and never scraped; BY-A is therefore measured on the "
            "CROPS the nutrient cost reaches and on the published TRADE VOLUMES, never on the "
            "assessment",
     "proxies": ("CORN", "WHEAT", "SOYBEAN")},
    {"name": "Ukrainian FOB grain basis at Odesa, Chornomorsk and Pivdennyi",
     "venue": "APK-Inform, UkrAgroConsult and the trade's own indications",
     "why": "the basis IS the corridor: when the route closes the futures barely move and the "
            "basis collapses, which is why a corridor study run on flat price alone measures "
            "the wrong variable. The assessments are subscription ground, so the pack uses the "
            "ministry's published TONNAGE as the measurable half",
     "proxies": ("WHEAT", "CORN", "SOYBEAN")},
    {"name": "Danube barge freight and the Black Sea war-risk insurance premium",
     "venue": "the Lloyd's market, the Baltic Exchange and the brokers' fixture reports",
     "why": "the corridor's COST. The war-risk premium on a Black Sea call moved by an order of "
            "magnitude and back on dated days, and it is the transmission channel XX-A studies "
            "-- reported in the public press even where the assessment itself is licensed",
     "proxies": ("WHEAT", "CORN", "XBRUSD")},
    {"name": "TTF and the European gas hubs",
     "venue": "ICE Endex and EEX",
     "why": "THE TRUE LEG of every Ukrainian transit and Belarusian refinery mechanism. TTF is "
            "not quoted here and XNGUSD (Henry Hub) is a WEAK proxy whose relationship to TTF "
            "is regime-dependent; every gas edge in this pack says so on its face",
     "proxies": ("XNGUSD", "GER40", "EUSTX50")},
    {"name": "Ukrainian day-ahead electricity price and the Ukrenergo cross-border cap",
     "venue": "the Market Operator (RDN/VDR) and Ukrenergo",
     "why": "the grid war as a price. The cross-border capacity Ukrenergo publishes is the "
            "physical link into ENTSO-E, so a strike week is a European power observable before "
            "it is a Ukrainian one",
     "proxies": ("XNGUSD", "GER40", "EUSTX50")},
    {"name": "Ukrainian sovereign eurobonds, the GDP warrants and the 2024 restructuring",
     "venue": "OTC",
     "why": "the external-financing channel and the only continuously-priced Ukrainian risk "
            "object; the 2024 restructuring is a dated regime break inside it",
     "proxies": ("EURTRY", "USDTRY", "EURUSD")},
    {"name": "Sunflower oil FOB and the vegetable-oil complex (sunoil, rapeseed, palm)",
     "venue": "the oils trade and the Rotterdam and Kandla assessments",
     "why": "Ukraine was about 45% of world sunflower-oil exports; the substitutes are soybean "
            "and palm oil, so the executable leg of a sunoil shock is SOYBEAN and the oilseed "
            "complex, never a sunflower contract, because none is quoted here",
     "proxies": ("SOYBEAN", "CORN", "COTTON")},
    {"name": "Ukrainian iron-ore concentrate and the Kryvyi Rih steel complex",
     "venue": "the seaborne iron-ore market and the European steel mills",
     "why": "the ore can be mined and cannot be shipped without the ports; the constraint is "
            "LOGISTICAL and its release is a European steel-input observable",
     "proxies": ("EUSTX50", "GER40", "XTIUSD")},
    {"name": "Belarusian oil-product exports and the Druzhba premium dispute",
     "venue": "Belneftekhim, Transneft tariff and premium negotiations",
     "why": "the 2020 pricing dispute halted supply to Mozyr and Naftan for weeks on dated days "
            "and is a clean refinery-margin event; the products themselves are not quoted, so "
            "the crude legs carry it",
     "proxies": ("XBRUSD", "XTIUSD", "USDRUB")},
)

# --------------------------------------------------------------------------- the central banks
#: THE FRAMEWORK CARRIES ONE CENTRAL BANK. The NBU takes the slot because Ukraine is the larger
#: mechanism and the one with a published decision calendar; the NBRB is carried beside it in
#: `NBRB` and is NOT demoted to a footnote -- both banks' clocks are in RELEASE_CLASSES and both
#: are actors. A pack that silently represented Belarus by Ukraine's central bank would be
#: measuring one country and reporting two.
CENTRAL_BANK: dict[str, Any] = {
    "name": "National Bank of Ukraine (Національний банк України)",
    "short": "NBU",
    "framework": "managed_float",
    "committee": "the Monetary Policy Committee (Комітет з монетарної політики), advisory to "
                 "the Board (Правління), which takes the decision",
    "policy_instrument": "the key policy rate (облікова ставка) with an interest-rate corridor "
                         "set by the overnight refinancing and overnight certificate-of-deposit "
                         "rates; since 2024 a THREE-MONTH certificate of deposit is used to "
                         "term out hryvnia liquidity and it is a separate instrument",
    "mandate": "price stability first, then financial stability and support for sustainable "
               "economic growth; a 5% +/-1pp medium-term inflation target that was explicitly "
               "SUSPENDED as an operating anchor in favour of exchange-rate stability from "
               "2022-02-24 and restored gradually from 2023-10-03",
    "decision_rule": "eight scheduled Board decisions a year on a calendar published in advance "
                     "at bank.gov.ua; the decision is released at 14:00 Kyiv and the Governor's "
                     "briefing follows the same afternoon. DURING MARTIAL LAW the Board has "
                     "also acted between meetings and the unscheduled decisions are their own "
                     "class, never pooled with the scheduled eight",
    "decision_calendar_rule": "eight a year, published as a calendar at bank.gov.ua; the "
                              "announcement minute must be stamped from the release itself and "
                              "never assumed, because the wartime briefing time has moved",
    "decision_time_utc": "11:00",
    "announce_local": "14:00 Europe/Kyiv (UTC+2 winter, UTC+3 summer -- Ukraine keeps EU DST, "
                      "so the UTC minute of every Kyiv event MOVES twice a year)",
    "dst_rule": "Europe/Kyiv observes EU summer time: last Sunday of March to last Sunday of "
                "October. A fixed-UTC event window is therefore WRONG for half the year, which "
                "is the opposite of the Russian case in the `ru` pack (Moscow is fixed UTC+3)",
    "minutes_lag_days": 11,
    "publication_classes": ("rishennia_pro_oblikovu_stavku", "inflatsiinyi_zvit",
                            "pidsumky_dyskusii_kmp", "ofitsiinyi_kurs_hryvni",
                            "mizhnarodni_rezervy", "zvit_pro_finansovu_stabilnist"),
    "policy_rate_series": "NBU:oblikova_stavka",
    "expected_rate_series": "UNMEASURED",
    "consensus_proxy": "there is NO traded hryvnia curve the desk can read. The usable public "
                       "expectation is the NBU's own survey of professional forecasters plus "
                       "the Interfax-Ukraine and Ekonomichna Pravda polls; both are SURVEYS and "
                       "a surprise built from them is a weaker object than an IB-implied one",
    "consensus_proxy_trap": "the domestic bond (ОВДП) primary auction yield is set at a "
                            "Ministry of Finance auction with a STATE-OWNED bank bid behind it, "
                            "so it is a policy variable as much as a market one; treating it as "
                            "a market expectation of the key rate reads the government's own "
                            "funding decision as the market's view",
    "crisis_history": ("2022-02-24: the official rate FIXED and the key rate frozen at 10%; a "
                       "blanket capital control and a ban on cross-border FX transfers",
                       "2022-06-02: the key rate raised from 10% to 25% in one step",
                       "2022-07-21: the official rate devalued about 25% to 36.5686",
                       "2023-10-03: the move to MANAGED FLEXIBILITY -- a daily fixing derived "
                       "from the interbank market inside an intervention policy rather than a "
                       "number the Board announces"),
    "off_cycle": "the Board acted out of cycle repeatedly in 2022; every unscheduled decision "
                 "is its own class and none may be pooled with the scheduled eight",
    "other_clocks": (
        {"what": "official hryvnia rate (офіційний курс) for the NEXT business day",
         "when_local": "about 15:30 Kyiv every business day", "when_utc": "12:30",
         "reference_lag_days": 0},
        {"what": "international reserves (міжнародні резерви), preliminary then final",
         "when_local": "the first business days of the month", "when_utc": "12:00",
         "reference_lag_days": 5},
        {"what": "Inflation Report (Інфляційний звіт) with the macro forecast",
         "when_local": "the quarterly forecast decision days", "when_utc": "11:00",
         "reference_lag_days": 0},
        {"what": "the summary of the Monetary Policy Committee discussion",
         "when_local": "about eleven days after the decision", "when_utc": "11:00",
         "reference_lag_days": 11},
    ),
    "root": "https://bank.gov.ua",
}

#: THE SECOND CENTRAL BANK, CARRIED IN FULL. Belarus is a BASKET regime with published weights,
#: which is a different object from Ukraine's managed float and must not be folded into it.
NBRB: dict[str, Any] = {
    "name": "National Bank of the Republic of Belarus (Нацыянальны банк Рэспублікі Беларусь)",
    "short": "NBRB",
    "framework": "band",
    "policy_instrument": "the refinancing rate (стаўка рэфінансавання) and the standing "
                         "facilities; monetary policy operates through a BROAD MONEY target "
                         "alongside an exchange-rate reference, not through an inflation target",
    "exchange_regime": "a MANAGED rate against a PUBLISHED CURRENCY BASKET. The basket's "
                       "composition and weights are announced by the NBRB, which is what makes "
                       "the implied rouble beta arithmetic rather than a regression -- see "
                       "`BASKET_ERAS` and `byn_basket_weights`",
    "fixing": "the official BYN rate is set from the BCSE continuous double auction and "
              "published for the NEXT calendar day; the additional session rates for CNY, PLN "
              "and UAH are published beside it",
    "administered_prices": "Council of Ministers Resolution No. 713 of 2022 put a general "
                           "administrative price regime over the consumer basket, so BELARUSIAN "
                           "CPI IS A POLICY VARIABLE and not a market-clearing measurement -- a "
                           "release-surprise study on it is measuring the regulation",
    "root": "https://www.nbrb.by",
    "publication_classes": ("stauka_refinansavannia", "aficyjny_kurs", "karzina_valiut",
                            "statystyka_zamezhnaha_handliu"),
}

# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "NBU official hryvnia rate (офіційний курс гривні), effective the NEXT day",
     "local": "published about 15:30 Kyiv each business day", "time_utc": "12:30",
     "time_utc_dst": "12:30", "dst_rule": "Europe/Kyiv EU summer time; the UTC minute moves "
                                          "twice a year and this row is the WINTER anchor",
     "instruments": ("EURPLN", "USDPLN", "EURUSD"), "window_minutes": 30,
     "confidence": "SETTLED",
     "why": "the rate every Ukrainian customs declaration, tax liability and budget line is "
            "struck at. THE NEXT-DAY EFFECTIVE DATE IS THE TRAP: an event study that applies "
            "the official rate on its publication day is using tomorrow's number today"},
    {"name": "NBU official rate under the wartime FIX (2022-02-24 to 2023-10-02)",
     "local": "unchanged for months at a time", "time_utc": "12:30", "time_utc_dst": "12:30",
     "dst_rule": "n/a while fixed",
     "instruments": ("EURPLN", "EURUSD"), "window_minutes": 30,
     "confidence": "SETTLED as a fact; the SERIES BREAK is the object",
     "why": "a fixed number is not a price. Any volatility, correlation or beta computed on the "
            "official hryvnia series inside this window is a measurement of the fix and not of "
            "the currency -- and the parallel cash rate is where the information went"},
    {"name": "NBRB official BYN rate from the BCSE session, effective the NEXT calendar day",
     "local": "the BCSE session closes about 13:00 Minsk; the rate is published after it",
     "time_utc": "10:30", "time_utc_dst": "10:30",
     "dst_rule": "none (Belarus abolished seasonal clock changes in 2014 and is fixed UTC+3)",
     "instruments": ("USDRUB", "EURRUB"), "window_minutes": 30, "confidence": "SETTLED",
     "why": "the basket's own measuring stick. Belarus is FIXED UTC+3 and Ukraine is not, so "
            "the two countries' publication minutes DRIFT APART twice a year -- a joint study "
            "on a fixed UTC hour is comparing two different local times for half the year"},
    {"name": "The NBRB currency basket value (вартасць кошыка валют)",
     "local": "published daily beside the official rates", "time_utc": "10:30",
     "time_utc_dst": "10:30", "dst_rule": "none",
     "instruments": ("USDRUB", "EURRUB", "EURUSD"), "window_minutes": 30,
     "confidence": "DECLARED, VERIFY against nbrb.by",
     "why": "the basket is PUBLISHED with its weights, so the implied rouble beta of BYN is "
            "arithmetic; the residual between the realised basket move and the arithmetic one "
            "is the policy, and that residual is BY-D's object"},
    {"name": "Chicago grain settlement (the corridor's executable clock)",
     "local": "13:20 America/Chicago", "time_utc": "19:20", "time_utc_dst": "18:20",
     "dst_rule": "US DST", "instruments": ("WHEAT", "CORN", "SOYBEAN"), "window_minutes": 20,
     "confidence": "SETTLED",
     "why": "every corridor, ban and vessel mechanism in this pack terminates in a Chicago "
            "settlement, and the Kyiv announcement hour sits INSIDE the Chicago day session -- "
            "which is why the pack's event windows are stated in UTC and not in local time"},
    {"name": "MATIF milling wheat settlement (the European leg of the same corridor)",
     "local": "18:30 Europe/Paris", "time_utc": "17:30", "time_utc_dst": "16:30",
     "dst_rule": "EU DST", "instruments": ("WHEAT", "EURUSD"), "window_minutes": 30,
     "confidence": "DECLARED",
     "why": "the European milling-wheat benchmark is the one the Ukrainian FOB basis is quoted "
            "against for European buyers; it is not a broker symbol, so WHEAT and the euro leg "
            "carry it and the pack says which"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "Ukrainian domestic bond (ОВДП) primary auction", "kind": "weekday", "weekday": 1,
     "days": (), "roll": "next", "window_utc": ("08:00", "12:00"),
     "instruments": ("EURPLN", "EURUSD"),
     "why": "the Ministry of Finance auctions ОВДП on Tuesdays; since 2022 the domestic bond is "
            "the government's main non-grant funding and the bid is substantially state-owned "
            "banks, so the cut-off is a policy variable"},
    {"name": "NBU scheduled decision afternoon", "kind": "weekday", "weekday": 3, "days": (),
     "roll": "next", "window_utc": ("11:00", "14:00"),
     "instruments": ("EURPLN", "EURUSD", "WHEAT"),
     "why": "the Board's scheduled decisions land on a Thursday at 14:00 Kyiv; the window is "
            "declared in UTC and is one hour earlier in summer"},
    {"name": "Belarusian monthly tax and social-contribution settlement", "kind": "day_of_month",
     "days": (22,), "roll": "previous", "window_utc": ("07:00", "12:00"),
     "instruments": ("USDRUB", "EURRUB"),
     "why": "the Belarusian corporate calendar concentrates hard-currency conversion into the "
            "third week; the exporters that hold roubles and yuan must convert to pay, which is "
            "a structural monthly bid inside the basket regime"},
    {"name": "Grain marketing-year boundary (1 July) and the export-memorandum quota reset",
     "kind": "month_end", "days": (), "roll": "previous", "window_utc": ("06:00", "16:00"),
     "instruments": ("WHEAT", "CORN", "SOYBEAN"),
     "why": "Ukraine's grain export memorandum between the ministry and the traders sets a "
            "season quota that resets at the 1 July boundary; the BSGI's own termination "
            "(2023-07-17) fell two weeks inside that boundary, which is a confound the pack "
            "names rather than averages"},
    {"name": "Fiscal year end (31 December) for both budgets", "kind": "fiscal_year_end",
     "days": (), "roll": "previous", "window_utc": ("07:00", "16:00"),
     "instruments": ("EURPLN", "USDRUB"),
     "why": "the Ukrainian budget law and the Belarusian budget law are both calendar-year; the "
            "Ukrainian external-financing schedule the NBU's reserves depend on is dated to it"},
    {"name": "Ukrainian gas-transit contract quarter boundary", "kind": "quarter_end",
     "days": (), "roll": "previous", "window_utc": ("06:00", "16:00"),
     "instruments": ("XNGUSD", "GER40"),
     "why": "the 2020-2024 transit contract booked capacity on a quarterly ship-or-pay basis; "
            "the contract's EXPIRY at 2024-12-31 is the single largest boundary in the series "
            "and 2025-01-01 is the first day of a different world"},
)

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Ukrainian Exchange (UX) and PFTS -- equity and derivatives",
     "index_symbols": (), "open_local": "10:30", "close_local": "17:30", "open_utc": "08:30",
     "close_utc": "15:30", "dst_rule": "Europe/Kyiv EU summer time",
     "auction": "opening and closing auctions on the equity market",
     "expiry_rule": "the UX index future expired quarterly; the market has been effectively "
                    "dormant since 2022-02-24",
     "holidays": "the Ukrainian public-holiday calendar; under martial law the closure decision "
                 "belongs to the NSSMC and the NBU, not to the calendar",
     "notes": "NO CFD IS QUOTED on any Ukrainian index and there is no usable public tape after "
              "2022-02-24. This row exists so the ABSENCE is named rather than assumed: the "
              "Ukrainian equity mechanism reaches this desk only through EUSTX50 and GER40"},
    {"name": "Belarusian Currency and Stock Exchange (BCSE / БВФБ)",
     "index_symbols": (), "open_local": "10:00", "close_local": "13:00", "open_utc": "07:00",
     "close_utc": "10:00", "dst_rule": "none (Belarus is fixed UTC+3 since 2014)",
     "auction": "a continuous double auction in USD, EUR, RUB and CNY against BYN; the official "
                "rate is derived from it",
     "expiry_rule": "no meaningful listed derivatives clock",
     "holidays": "the Belarusian public-holiday calendar plus the Council of Ministers' annual "
                 "working-day transfer resolution",
     "notes": "THE ONE EXCHANGE IN THIS PACK THAT STILL PRICES SOMETHING THE PACK CARES ABOUT. "
              "The desk has no feed and no licence; the published daily rates are read instead"},
    {"name": "Belarusian Universal Commodity Exchange (BUCE / БУТБ)",
     "index_symbols": (), "open_local": "09:00", "close_local": "17:00", "open_utc": "06:00",
     "close_utc": "14:00", "dst_rule": "none",
     "auction": "public commodity auctions in timber, metals, agricultural products and "
                "industrial goods, with results published",
     "expiry_rule": "n/a",
     "holidays": "the Belarusian public-holiday calendar",
     "notes": "BUCE PUBLISHES ITS AUCTION RESULTS, which makes it the one place a Belarusian "
              "physical price is visible without a licence -- the timber and dairy lines of "
              "BY-E are built on it and on Belstat's trade tables"},
)

SESSION_WINDOWS: tuple[dict[str, Any], ...] = (
    {"name": "bs_kyiv_morning_winter", "start_utc": "06:00", "end_utc": "09:00",
     "notes": "the Kyiv working morning in winter (UTC+2): the ministry's tonnage posts, the "
              "port notices and the overnight-strike reporting land here"},
    {"name": "bs_kyiv_morning_summer", "start_utc": "05:00", "end_utc": "08:00",
     "notes": "THE SAME LOCAL HOURS in summer (UTC+3). Ukraine keeps EU DST and Belarus does "
              "not, so a fixed-UTC study pools two different Kyiv hours for half the year"},
    {"name": "bs_nbu_decision", "start_utc": "11:00", "end_utc": "13:00",
     "notes": "the NBU Board release at 14:00 Kyiv and the Governor's briefing (winter anchor)"},
    {"name": "bs_minsk_fixing", "start_utc": "07:00", "end_utc": "11:00",
     "notes": "the BCSE session and the NBRB rate publication; Minsk is FIXED UTC+3 all year"},
    {"name": "bs_chicago_day", "start_utc": "14:30", "end_utc": "19:20",
     "notes": "the CBOT day session, where every corridor and ban mechanism in this pack is "
              "actually executable; a Kyiv morning announcement reaches it five hours later"},
    {"name": "bs_istanbul_jcc", "start_utc": "07:00", "end_utc": "15:00",
     "notes": "the Joint Coordination Centre's working day in Istanbul during the BSGI: "
              "inspection clearances and the daily vessel movement table"},
)

RELEASE_CLASSES: tuple[dict[str, Any], ...] = (
    {"name": "NBU key policy rate decision (рішення про облікову ставку)", "cadence": "8 a year",
     "time_utc": "11:00", "source": "National Bank of Ukraine",
     "actual_series": "NBU:oblikova_stavka", "expected_series": "UNMEASURED",
     "notes": "eight a year on a published calendar; the unscheduled wartime decisions are a "
              "SEPARATE class and are never pooled with them"},
    {"name": "NBU official hryvnia rate (daily, effective next business day)", "cadence": "daily",
     "time_utc": "12:30", "source": "National Bank of Ukraine", "actual_series": "NBU:kurs",
     "expected_series": "n/a",
     "notes": "the next-day effective date is the trap; the fixed-rate era is a different series"},
    {"name": "Ministry of Agrarian Policy monthly grain export tonnage",
     "cadence": "monthly (with weekly in-season updates)", "time_utc": "09:00",
     "source": "Ministry of Agrarian Policy and Food of Ukraine / the State Customs Service",
     "actual_series": "MINAGRO:export_tonnage", "expected_series": "n/a",
     "notes": "the measurable half of the corridor: a counted physical flow published by the "
              "state that ships it, in Ukrainian, with a season-to-date cumulative beside it"},
    {"name": "Black Sea Grain Initiative daily vessel movement and inspection table",
     "cadence": "daily while the initiative stood", "time_utc": "15:00",
     "source": "UN Joint Coordination Centre, Istanbul", "actual_series": "JCC:vessel_table",
     "expected_series": "n/a",
     "notes": "2022-08 to 2023-07 ONLY. Vessel-by-vessel, with tonnage, cargo and destination: "
              "the cleanest public physical-flow series against a liquid future this desk has"},
    {"name": "Ukrenergo grid status, consumption and emergency-outage notices",
     "cadence": "daily and event-driven", "time_utc": "06:00", "source": "NPC Ukrenergo",
     "actual_series": "UKRENERGO:grid_status", "expected_series": "n/a",
     "notes": "the strike days are dated; the outage schedule is the physical-economy series"},
    {"name": "GTSOU gas transit nominations and the transit-contract status",
     "cadence": "daily", "time_utc": "07:00", "source": "Gas TSO of Ukraine",
     "actual_series": "GTSOU:transit_nominations", "expected_series": "n/a",
     "notes": "ran to 2024-12-31; the expiry is the largest boundary in the European gas map "
              "this pack touches and 2025-01-01 is a different regime, not a lower number"},
    {"name": "Ukrstat consumer price index and industrial output",
     "cadence": "monthly", "time_utc": "12:00", "source": "State Statistics Service of Ukraine",
     "actual_series": "UKRSTAT:cpi", "expected_series": "UNMEASURED",
     "notes": "publication was curtailed and partially reclassified under martial law; what is "
              "missing is NAMED in the dataset row rather than silently treated as zero"},
    {"name": "NBRB refinancing rate and the official BYN rate with the basket value",
     "cadence": "daily (rate) / irregular (refinancing)", "time_utc": "10:30",
     "source": "National Bank of the Republic of Belarus", "actual_series": "NBRB:kurs_kosh",
     "expected_series": "n/a",
     "notes": "the basket weights are published alongside, which is the whole point of BY-D"},
    {"name": "Belstat monthly foreign trade by commodity group",
     "cadence": "monthly", "time_utc": "09:00",
     "source": "National Statistical Committee of the Republic of Belarus",
     "actual_series": "BELSTAT:trade", "expected_series": "n/a",
     "notes": "the potash and oil-product lines were reclassified and partly withheld after "
              "2022; the WITHHOLDING is itself the measurement and is named in the dataset"},
    {"name": "EU Commission DG AGRI cereals dashboard and the import-restriction decisions",
     "cadence": "weekly (dashboard) / event-driven (decisions)", "time_utc": "12:00",
     "source": "European Commission DG AGRI", "actual_series": "DGAGRI:cereals_dashboard",
     "expected_series": "n/a",
     "notes": "the licence and import series that dates the 2023 neighbour bans and the "
              "solidarity-lane volumes; the decisions themselves are Official Journal acts"},
)

# --------------------------------------------------------------------------- calendars
#: UKRAINE'S STATUTORY HOLIDAYS AS REWRITTEN IN 2023. Law No. 3258-IX of 14 July 2023 amended
#: Article 73 of the Labour Code: CHRISTMAS MOVED TO 25 DECEMBER, 7 January ceased to be a
#: statutory holiday, the Soviet-era 8 March and 1 May dates were abolished, 9 May was replaced
#: by 8 May as the Day of Remembrance and Victory over Nazism, the Day of Ukrainian Statehood
#: moved from 28 July to 15 July, and Defenders' Day moved from 14 October to 1 October. A study
#: that pools 2021 with 2024 on a Ukrainian holiday calendar is using two different calendars.
UA_FIXED_FROM_2023: tuple[tuple[int, int, str], ...] = (
    (1, 1, "Новий рік"),
    (5, 8, "День пам'яті та перемоги над нацизмом у Другій світовій війні 1939-1945 років"),
    (6, 28, "День Конституції України"),
    (7, 15, "День Української Державності"),
    (8, 24, "День Незалежності України"),
    (10, 1, "День захисників і захисниць України"),
    (12, 25, "Різдво Христове"),
)
#: THE CALENDAR THE SAME LAW REPLACED, kept because it is the only way to date the break. These
#: are the pre-2023 statutory days; every one of them is a CLOSED day before 2023 and an ORDINARY
#: working day after it, which is a regime break no rainfall or price series will explain.
UA_FIXED_BEFORE_2023: tuple[tuple[int, int, str], ...] = (
    (1, 1, "Новий рік"),
    (1, 7, "Різдво Христове (за юліанським календарем)"),
    (3, 8, "Міжнародний жіночий день"),
    (5, 1, "День праці"),
    (5, 9, "День перемоги над нацизмом у Другій світовій війні"),
    (6, 28, "День Конституції України"),
    (7, 28, "День Української Державності (2021-2022)"),
    (8, 24, "День Незалежності України"),
    (10, 14, "День захисника України"),
)
#: The year from which UA_FIXED_FROM_2023 is the calendar in force.
UA_CALENDAR_BREAK_YEAR = 2023

#: BELARUS KEPT ITS CALENDAR, which is the other half of the joint mechanism: the two countries'
#: closed days now COINCIDE far less than they did, and a CIS-wide holiday-liquidity study that
#: treats them as one region is averaging two calendars. 2 January became a non-working day from
#: 2020; 17 September (Day of People's Unity) was made non-working from 2024 -- that row carries
#: its status because the desk has not read the amending act itself.
BY_FIXED: tuple[tuple[int, int, str, str], ...] = (
    (1, 1, "Новы год", "SETTLED"),
    (1, 2, "Новы год (другі дзень, з 2020)", "SETTLED"),
    (1, 7, "Раство Хрыстова (праваслаўнае)", "SETTLED"),
    (3, 8, "Дзень жанчын", "SETTLED"),
    (5, 1, "Свята працы", "SETTLED"),
    (5, 9, "Дзень Перамогі", "SETTLED"),
    (7, 3, "Дзень Незалежнасці Рэспублікі Беларусь", "SETTLED"),
    (9, 17, "Дзень народнага адзінства (непрацоўны з 2024)", "DECLARED_VERIFY"),
    (11, 7, "Дзень Кастрычніцкай рэвалюцыі", "SETTLED"),
    (12, 25, "Раство Хрыстова (каталіцкае)", "SETTLED"),
)
#: The year from which 17 September is carried as a non-working day.
BY_UNITY_DAY_FROM = 2024


def orthodox_easter(year: int) -> date:
    """Orthodox Pascha as a Gregorian date, by MEEUS'S JULIAN ALGORITHM plus the 13-day offset.

    DERIVED, NEVER TYPED. Radunitsa is the ninth day after Pascha and is the one movable public
    holiday Belarus still keeps, so a typed table would go stale the year after it was written.
    The 13-day Julian-to-Gregorian offset is correct for 1900-2099 and this function is not
    valid outside that span -- which is stated rather than silently assumed.
    """
    if not 1900 <= int(year) <= 2099:
        raise ValueError(f"orthodox_easter({year}): the 13-day offset holds only for 1900-2099")
    a = year % 4
    b = year % 7
    c = year % 19
    d = (19 * c + 15) % 30
    e = (2 * a + 4 * b - d + 34) % 7
    month = (d + e + 114) // 31
    day = ((d + e + 114) % 31) + 1
    return date(year, month, day) + timedelta(days=13)


def radunitsa(year: int) -> date:
    """RADUNITSA (Радуніца): the ninth day after Orthodox Pascha, always a Tuesday, and a
    non-working public holiday in Belarus by the Labour Code and the annual decree. Derived from
    the paschalion above -- the one movable national closure in either jurisdiction."""
    return orthodox_easter(year) + timedelta(days=9)


def orthodox_trinity(year: int) -> date:
    """Trinity (Трійця): Pascha plus 49 days. It was a Ukrainian non-working day BEFORE the 2023
    amendment and is carried for the pre-break era only, so a pooled study can be split."""
    return orthodox_easter(year) + timedelta(days=49)


def ua_national_holidays(year: int) -> dict[date, str]:
    """Ukraine's statutory holidays for a year, on the calendar in force THAT year.

    NO WEEKEND SUBSTITUTION is applied: Ukraine's transfer rule was itself suspended under
    martial law, and inventing a Monday the state did not grant would put a closed day into a
    liquidity sample that was an ordinary working day.
    """
    out: dict[date, str] = {}
    if int(year) >= UA_CALENDAR_BREAK_YEAR:
        for m, d, name in UA_FIXED_FROM_2023:
            out[date(year, m, d)] = name
    else:
        for m, d, name in UA_FIXED_BEFORE_2023:
            if (m, d) == (7, 28) and year < 2021:
                continue
            out[date(year, m, d)] = name
        out[orthodox_easter(year)] = "Великдень (неробочий день до 2023)"
        out[orthodox_trinity(year)] = "Трійця (неробочий день до 2023)"
    return dict(sorted(out.items()))


def by_national_holidays(year: int) -> dict[date, str]:
    """Belarus's statutory non-working days for a year, including the derived Radunitsa."""
    out: dict[date, str] = {}
    for m, d, name, status in BY_FIXED:
        if (m, d) == (9, 17) and int(year) < BY_UNITY_DAY_FROM:
            continue
        out[date(year, m, d)] = name if status == "SETTLED" else f"{name} [{status}]"
    out[radunitsa(year)] = "Радуніца"
    return dict(sorted(out.items()))


def national_holidays(jurisdiction: str, year: int) -> dict[date, str]:
    """One jurisdiction's closures. An unknown code returns {} rather than a guess."""
    code = str(jurisdiction).lower()
    if code == "ua":
        return ua_national_holidays(year)
    if code == "by":
        return by_national_holidays(year)
    return {}


def market_holidays(year: int) -> dict[date, str]:
    """Every day EITHER jurisdiction closes, tagged with which one. The union is the honest
    table for a pack that answers for two countries: a day Belarus closes and Ukraine does not
    is still a day half this plane's physical reporting stops."""
    out: dict[date, list[str]] = {}
    for code in JURISDICTIONS:
        for day, name in national_holidays(code, year).items():
            out.setdefault(day, []).append(f"{code.upper()}: {name}")
    return {day: " | ".join(names) for day, names in sorted(out.items())}


def joint_closure_days(year: int) -> dict[date, str]:
    """The days BOTH countries are closed -- since 2023 there are very few of them, which is
    itself the measurement that makes XX-C a domain rather than a footnote."""
    ua = set(ua_national_holidays(year))
    by = set(by_national_holidays(year))
    both = sorted(ua & by)
    table = market_holidays(year)
    return {day: table[day] for day in both}


def asymmetric_closure_days(year: int) -> dict[date, str]:
    """The days exactly ONE of the two is closed. This is the sample XX-C runs and the reason
    the pack refuses to treat 'the CIS' as one calendar."""
    ua = set(ua_national_holidays(year))
    by = set(by_national_holidays(year))
    table = market_holidays(year)
    return {day: table[day] for day in sorted(ua ^ by)}


def is_market_holiday(day: date) -> bool:
    return day in market_holidays(day.year)


def _last_sunday(year: int, month: int) -> date:
    """The last Sunday of a month -- the EU summer-time switch day."""
    day = date(year, month, 31) if month in (3, 10) else date(year, month, 28)
    while day.weekday() != 6:
        day -= timedelta(days=1)
    return day


def utc_offset_hours(jurisdiction: str, day: date) -> int:
    """THE CLOCK ASYMMETRY, WHICH IS A REAL AND OFTEN-MISSED MECHANISM.

    Kyiv keeps EU summer time (UTC+2 winter, UTC+3 summer). Minsk ABOLISHED seasonal clock
    changes in 2014 and is fixed UTC+3 all year. So for roughly five months a year the two
    capitals of this pack are on DIFFERENT clocks, and a joint study run on a fixed UTC hour is
    comparing the Kyiv mid-morning with the Minsk late morning for half the sample.
    """
    code = str(jurisdiction).lower()
    if code == "by":
        return 3
    if code != "ua":
        return 0
    lo = _last_sunday(day.year, 3)
    hi = _last_sunday(day.year, 10)
    return 3 if lo <= day < hi else 2


def clock_divergence_days(year: int) -> list[date]:
    """Every weekday in a year on which Kyiv and Minsk are on DIFFERENT UTC offsets. These are
    the days a fixed-UTC session window means two different local times, and they are the
    control sample XX-C's microstructure leg runs against."""
    out: list[date] = []
    day = date(year, 1, 1)
    while day.year == year:
        if day.weekday() < 5 and utc_offset_hours("ua", day) != utc_offset_hours("by", day):
            out.append(day)
        day += timedelta(days=1)
    return out


HOLIDAYS_RULE: dict[str, Any] = {
    "kind": "computed_from_rules_plus_derived_paschalion",
    "authority": "Ukraine: Article 73 of the Labour Code as amended by Law No. 3258-IX of "
                 "14 July 2023 (zakon.rada.gov.ua). Belarus: the Labour Code and the annual "
                 "Council of Ministers resolution transferring working days (pravo.by). NEITHER "
                 "binds a market: Ukraine has been under martial law since 2022-02-24 and the "
                 "statutory rest days are not granted in the ordinary way, so this table is the "
                 "NOMINAL calendar and the banking closure is the NBU's decision",
    "rule": "UKRAINE, from 2023: SEVEN fixed days -- 1 January, 8 May (Day of Remembrance and "
            "Victory over Nazism), 28 June (Constitution Day), 15 July (Day of Ukrainian "
            "Statehood), 24 August (Independence Day), 1 October (Defenders' Day) and "
            "25 DECEMBER (Christmas, MOVED from 7 January by Law No. 3258-IX of 14 July 2023). "
            "The same law abolished the Soviet-era 8 March and 1 May, replaced 9 May with "
            "8 May, moved Statehood Day from 28 July to 15 July and Defenders' Day from "
            "14 October to 1 October, and ended Easter and Trinity as statutory non-working "
            "days. BEFORE 2023 the calendar is the nine pre-break days PLUS Easter and Trinity, "
            "computed from the Orthodox paschalion. NO WEEKEND SUBSTITUTION is applied in "
            "either era. BELARUS: ten fixed days -- 1 and 2 January, 7 January (Orthodox "
            "Christmas), 8 March, 1 May, 9 May, 3 July, 17 September (non-working from 2024), "
            "7 November and 25 December (Catholic Christmas) -- PLUS RADUNITSA, the ninth day "
            "after Orthodox Pascha, which is always a Tuesday and is DERIVED here with Meeus's "
            "Julian algorithm rather than typed. The published table is the UNION of the two, "
            "tagged by jurisdiction, because a day either country stops reporting is a day half "
            "this plane's physical data stops.",
    "years": (2024, 2025, 2026),
    "weekend": "Saturday and Sunday in both jurisdictions",
    "movable_rule": "Radunitsa = Orthodox Pascha + 9 days (Belarus, every year); Trinity = "
                    "Pascha + 49 days (Ukraine, pre-2023 era only). Pascha itself is computed, "
                    "never typed -- see `orthodox_easter`",
    "clock_rule": "Kyiv keeps EU summer time (UTC+2/UTC+3); Minsk is FIXED UTC+3 since 2014. "
                  "The two diverge for about five months a year -- see `utc_offset_hours` and "
                  "`clock_divergence_days`",
    "table": {y: {d.isoformat(): n for d, n in market_holidays(y).items()}
              for y in (2024, 2025, 2026)},
    "status": {
        2024: "SETTLED for both fixed calendars; Radunitsa 2024-05-14 is derived; the "
              "Belarusian 17 September row is DECLARED_VERIFY against pravo.by",
        2025: "SETTLED for both fixed calendars; Radunitsa 2025-04-29 is derived",
        2026: "SETTLED for both fixed calendars; Radunitsa 2026-04-21 is derived. MARTIAL LAW "
              "in Ukraine means the statutory days are nominal, and that is a state, not a gap",
    },
    "known_dates": {
        "2024-05-14": "Radunitsa, derived as Pascha (2024-05-05) + 9 days; a Tuesday",
        "2025-04-29": "Radunitsa, derived as Pascha (2025-04-20) + 9 days; a Tuesday",
        "2026-04-21": "Radunitsa, derived as Pascha (2026-04-12) + 9 days; a Tuesday",
        "2026-12-25": "Christmas in BOTH jurisdictions for the first time in history -- "
                      "Ukraine by the 2023 law, Belarus by its long-standing Catholic Christmas",
        "2026-01-07": "BELARUS ONLY since 2023; an ordinary Ukrainian working day",
        "2026-07-15": "Day of Ukrainian Statehood, moved here from 28 July by the 2023 law",
    },
    "fn": market_holidays,
    "national_fn": national_holidays,
    "joint_fn": joint_closure_days,
    "asymmetric_fn": asymmetric_closure_days,
    "easter_fn": orthodox_easter,
    "radunitsa_fn": radunitsa,
    "utc_offset_fn": utc_offset_hours,
}

# --------------------------------------------------------------------------- the dated regimes
#: THE BLACK SEA EXPORT REGIME, AS DATED PHASES. Every one of these boundaries is a public,
#: reported fact with a day attached, and a study that pools two of them is averaging two
#: different physical worlds. `corridor_regime` is the state function a cell conditions on.
CORRIDOR_ERAS: tuple[tuple[date, date, str, str], ...] = (
    (date(2019, 1, 1), date(2022, 2, 23), "PREWAR",
     "normal deep-sea loading out of Odesa, Chornomorsk, Pivdennyi and Mykolaiv"),
    (date(2022, 2, 24), date(2022, 7, 21), "PORTS_CLOSED",
     "the deep-sea ports stop; roughly 20 mt of grain is stranded and the only routes out are "
     "rail, road and the Danube"),
    (date(2022, 7, 22), date(2023, 7, 17), "BSGI",
     "the Black Sea Grain Initiative: a negotiated corridor with Russian participation in the "
     "inspections, administered from the Joint Coordination Centre in Istanbul, with a public "
     "vessel-by-vessel table"),
    (date(2023, 7, 18), date(2023, 8, 9), "GAP",
     "the initiative is terminated; strikes on Odesa and Danube port infrastructure follow and "
     "no corridor is in operation"),
    (date(2023, 8, 10), date(2030, 12, 31), "UKRAINIAN_CORRIDOR",
     "the unilateral Ukrainian maritime corridor hugging Bulgarian, Romanian and Turkish "
     "territorial waters, defended rather than negotiated and insured rather than inspected"),
)
#: The BSGI's own internal dates. Each is an ANNOUNCEMENT with a minute, not a slow drift.
BSGI_EVENTS: tuple[tuple[date, str, str], ...] = (
    (date(2022, 7, 22), "the Initiative and the Russia-UN memorandum signed in Istanbul",
     "SETTLED"),
    (date(2022, 8, 1), "the first outbound vessel sails from Odesa", "SETTLED"),
    (date(2022, 10, 29), "Russia announces suspension of participation after the Sevastopol "
                         "drone attack", "SETTLED"),
    (date(2022, 11, 2), "Russia resumes participation", "SETTLED"),
    (date(2022, 11, 17), "first renewal, 120 days", "SETTLED"),
    (date(2023, 3, 18), "second renewal, announced on divergent terms (60 vs 120 days)",
     "SETTLED"),
    (date(2023, 5, 18), "third renewal, 60 days", "SETTLED"),
    (date(2023, 7, 17), "the Initiative TERMINATES", "SETTLED"),
)
#: THE NEIGHBOURS' UNILATERAL IMPORT BANS AND THE EU ACT THAT ABSORBED THEM. A direct, dated
#: interaction with the `pl` and `cee_balkans` packs, and the only place in this pack where a
#: Ukrainian supply event shows up as an intra-EU BASIS event rather than a flat-price one.
IMPORT_BAN_EVENTS: tuple[tuple[date, str, str], ...] = (
    (date(2023, 4, 15), "Poland and Hungary announce unilateral bans on Ukrainian grain "
                        "imports; Slovakia follows within days", "PRESS_REPORTED"),
    (date(2023, 5, 2), "the European Commission adopts a temporary restriction on wheat, maize, "
                       "rapeseed and sunflower seed entering Bulgaria, Hungary, Poland, Romania "
                       "and Slovakia, replacing the unilateral measures", "PRESS_REPORTED"),
    (date(2023, 9, 15), "the EU measure lapses; Poland, Hungary and Slovakia extend their own "
                        "bans unilaterally and Ukraine files at the WTO", "PRESS_REPORTED"),
    (date(2023, 11, 6), "Polish hauliers begin blockading the Ukrainian border crossings",
     "PRESS_REPORTED"),
    (date(2024, 2, 20), "Polish farmers' blockade extends to the rail crossings and grain is "
                        "spilled from wagons", "PRESS_REPORTED"),
)
#: THE HRYVNIA'S THREE WARTIME ERAS. Rows are (start, end, regime, official rate or None).
UAH_ERAS: tuple[tuple[date, date, str, float | None], ...] = (
    (date(2019, 1, 1), date(2022, 2, 23), "FLOATING_MANAGED", None),
    (date(2022, 2, 24), date(2022, 7, 20), "FIXED_PREDEVALUATION", 29.2549),
    (date(2022, 7, 21), date(2023, 10, 2), "FIXED_POSTDEVALUATION", 36.5686),
    (date(2023, 10, 3), date(2030, 12, 31), "MANAGED_FLEXIBILITY", None),
)
#: THE NBRB'S PUBLISHED BASKET, BY ERA. Weights sum to 1.0 in every row, which is asserted by
#: the tests -- a basket whose weights do not sum to one is a typo, not a regime.
BASKET_ERAS: tuple[tuple[date, date, dict[str, float], str], ...] = (
    (date(2009, 1, 2), date(2014, 12, 31), {"USD": 1 / 3, "EUR": 1 / 3, "RUB": 1 / 3},
     "SETTLED"),
    (date(2015, 1, 1), date(2016, 12, 31), {"RUB": 0.40, "USD": 0.30, "EUR": 0.30}, "SETTLED"),
    (date(2017, 1, 1), date(2022, 7, 13), {"RUB": 0.50, "USD": 0.30, "EUR": 0.20}, "SETTLED"),
    (date(2022, 7, 14), date(2030, 12, 31), {"RUB": 0.60, "USD": 0.30, "CNY": 0.10},
     "DECLARED_VERIFY"),
)


def corridor_regime(day: date) -> str:
    """Which Black Sea export regime was in force on a date. UNMEASURED outside the declared
    span -- absence is never resolved into a clean verdict (L1.28a)."""
    for lo, hi, name, _why in CORRIDOR_ERAS:
        if lo <= day <= hi:
            return name
    return "UNMEASURED"


def corridor_regime_note(day: date) -> str:
    for lo, hi, _name, why in CORRIDOR_ERAS:
        if lo <= day <= hi:
            return why
    return "outside the pack's declared corridor span"


def uah_regime(day: date) -> tuple[str, float | None]:
    """The hryvnia regime on a date and the official rate if the regime FIXED one.

    A fixed number is not a price: any volatility or beta computed on the official series inside
    a FIXED era measures the fix. The function returns the rate so a study can refuse the window
    rather than quietly average it.
    """
    for lo, hi, name, rate in UAH_ERAS:
        if lo <= day <= hi:
            return name, rate
    return "UNMEASURED", None


def byn_basket_weights(day: date) -> dict[str, float]:
    """The NBRB's PUBLISHED basket weights in force on a date, or {} outside the declared span.

    This is the pack's central Belarusian claim in one function: because the weights are
    published rather than inferred, the rouble beta implied for BYN is ARITHMETIC. A study can
    therefore test the RESIDUAL -- what the basket does not explain -- instead of re-estimating
    what the central bank already told everybody.
    """
    for lo, hi, weights, _status in BASKET_ERAS:
        if lo <= day <= hi:
            return dict(weights)
    return {}


def byn_basket_status(day: date) -> str:
    for lo, hi, _weights, status in BASKET_ERAS:
        if lo <= day <= hi:
            return status
    return "UNMEASURED"


def implied_rub_beta(day: date) -> float:
    """The rouble weight in the basket on a date -- the arithmetic beta of BYN to RUB inside the
    basket regime, and 0.0 where the pack declares no basket. It is a DECLARED coefficient, not
    an estimated one, which is the whole reason BY-D exists."""
    return float(byn_basket_weights(day).get("RUB", 0.0))


def bsgi_event_dates(status: str = "SETTLED") -> list[date]:
    """The Black Sea Grain Initiative's own announcement days at or above a confidence label."""
    order = {"PRESS_REPORTED": 0, "SETTLED": 1}
    floor = order.get(status, 0)
    return [d for d, _what, st in BSGI_EVENTS if order.get(st, 0) >= floor]


def import_ban_dates() -> list[date]:
    """The dated EU-level and neighbour-level restriction events, all PRESS_REPORTED until an
    Official Journal or gazette citation is attached. Nothing compiled on them is promoted."""
    return [d for d, _what, _st in IMPORT_BAN_EVENTS]

# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "Ministry of Agrarian Policy and State Customs Service grain export tonnage",
     "root": "https://minagro.gov.ua", "available": True,
     "fields": ("season_to_date_mt", "monthly_mt", "by_crop", "by_port_vs_rail_vs_danube"),
     "frequency": "monthly with weekly in-season updates", "snapshot": "marketing year from "
                                                                      "1 July",
     "publish_utc": "09:00", "lag_days": 7, "licence": "free, public",
     "why": "THE POSITIONING SERIES OF THIS PACK. There is no hryvnia COT and no Ukrainian "
            "futures open interest; what exists instead is a counted physical flow published by "
            "the state that ships it, which is a better object than a survey",
     "pit_warning": "revised upward as customs declarations clear; the first print is an "
                    "undercount and a cell compiled on it must use the FIRST print, not the "
                    "revised one"},
    {"name": "UN Joint Coordination Centre vessel movement and inspection table (BSGI)",
     "root": "https://www.un.org/en/black-sea-grain-initiative", "available": True,
     "fields": ("vessel", "cargo", "tonnage", "destination", "inspection_date", "direction"),
     "frequency": "daily while the Initiative stood", "snapshot": "2022-08-01 to 2023-07-17",
     "publish_utc": "15:00", "lag_days": 1, "licence": "free, public (UN)",
     "why": "vessel-by-vessel physical flow with tonnage and destination, published by the "
            "administering body itself -- the single best positioning-substitute in the pack",
     "pit_warning": "ENDS 2023-07-17 and has no successor: the Ukrainian corridor that replaced "
                    "it publishes tonnage, not vessels, so the two eras are not the same series"},
    {"name": "European Commission DG AGRI cereal import licences and the solidarity-lane data",
     "root": "https://agriculture.ec.europa.eu/data-and-analysis/markets/overviews/"
             "market-observatories/crops_en",
     "available": True,
     "fields": ("import_licences_by_member_state", "ukrainian_origin_volumes", "tariff_status"),
     "frequency": "weekly", "snapshot": "EU marketing year", "publish_utc": "12:00",
     "lag_days": 7, "licence": "free, public",
     "why": "the only public series that separates 'Ukraine exported' from 'the EU absorbed it', "
            "which is exactly the distinction the 2023 bans were about",
     "pit_warning": "licences are not shipments; the gap between them is itself the object"},
    {"name": "NBU international reserves and FX intervention volumes",
     "root": "https://bank.gov.ua/ua/markets/currency-market", "available": True,
     "fields": ("reserves_usd", "nbu_fx_sales", "nbu_fx_purchases", "interbank_turnover"),
     "frequency": "daily (interventions) / monthly (reserves)", "snapshot": "month end",
     "publish_utc": "12:00", "lag_days": 2, "licence": "free, public",
     "why": "the NBU PUBLISHES ITS OWN INTERVENTION, which is rare; under managed flexibility "
            "the intervention volume is the policy and the rate is the residual",
     "pit_warning": "the daily intervention number is same-day but the reserves are monthly and "
                    "revised; never mix the two frequencies into one state variable"},
    {"name": "Belstat foreign trade by commodity group (potash, oil products, timber, dairy)",
     "root": "https://www.belstat.gov.by", "available": True,
     "fields": ("exports_by_group", "imports_by_group", "by_partner_country"),
     "frequency": "monthly and quarterly", "snapshot": "calendar month",
     "publish_utc": "09:00", "lag_days": 45, "licence": "free, public",
     "why": "the only official read on Belarusian potash and oil-product volumes",
     "pit_warning": "SEVERAL LINES WERE RECLASSIFIED OR WITHHELD AFTER 2022. The withholding is "
                    "itself a measurement and the pack reports UNMEASURED for those months "
                    "rather than substituting a mirror estimate without saying so"},
    {"name": "UN Comtrade mirror statistics for Belarusian potash and Ukrainian grain",
     "root": "https://comtrade.un.org", "available": True,
     "fields": ("hs3104_potash", "hs1001_wheat", "hs1005_maize", "hs1512_sunflower_oil"),
     "frequency": "monthly, lagged", "snapshot": "calendar month", "publish_utc": "12:00",
     "lag_days": 90, "licence": "free, public",
     "why": "THE MIRROR IS THE ANSWER TO THE WITHHOLDING: what Belarus stops publishing, its "
            "counterparties still report as imports, and the sum of the mirrors bounds the flow",
     "pit_warning": "90 days late and revised; it can date an era and can never condition a week"},
    {"name": "A CFTC or exchange-traded UAH or BYN positioning series",
     "root": "", "available": False, "fields": (), "frequency": "n/a", "snapshot": "",
     "publish_utc": "", "lag_days": 0, "licence": "",
     "why": "DECLARED ABSENT: no hryvnia or Belarusian-ruble future trades on any exchange the "
            "desk can read, and no COT contract exists for either",
     "pit_warning": "DOES NOT EXIST: UAH and BYN positioning is UNMEASURED and is never proxied "
                    "by the EUR or RUB COT legs, which are positions in other currencies"},
)

# --------------------------------------------------------------------------- terminology
#: THE WORKING VOCABULARY, PER DOMAIN, IN THE SCRIPTS THE GROUND IS ACTUALLY WRITTEN IN. A
#: crawler handed English finds English articles ABOUT the release and never the release: the
#: ministry posts "експорт зерна", the NBRB posts "кошык валют", the trade posts "форвардна ціна".
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "UA-A": ("зернова ініціатива", "зерновий коридор", "Чорноморська зернова ініціатива",
             "Спільний координаційний центр", "інспекція суден", "судно з зерном",
             "черговість суден", "зерновая инициатива", "зерновой коридор", "инспекция судов",
             "морські коридори України", "європейські покупці зерна",
             "Black Sea Grain Initiative"),
    "UA-B": ("морський коридор", "український морський коридор", "Одеський порт",
             "Чорноморськ", "Південний", "перевалка зерна", "експорт зерна", "тоннаж",
             "морской коридор", "перевалка зерна", "экспорт зерна",
             "експорт української продукції", "порти Одеської області"),
    "UA-C": ("Дунайські порти", "Ізмаїл", "Рені", "шляхи солідарності", "солідарні коридори",
             "заборона імпорту зерна", "польське ембарго", "блокада кордону",
             "дунайские порты", "запрет импорта зерна", "блокада границы",
             "Європейська комісія обмеження", "кордон з Польщею черги"),
    "UA-D": ("облікова ставка", "офіційний курс гривні", "курс гривні", "фіксований курс",
             "керована гнучкість", "девальвація", "валютні обмеження", "готівковий курс",
             "міжнародні резерви", "учетная ставка", "официальный курс", "девальвация",
             "Національний банк України рішення", "гривня знецінюється",
             "валютные ограничения"),
    "UA-E": ("Укренерго", "відключення світла", "графіки відключень", "обстріл енергетики",
             "Запорізька АЕС", "дефіцит потужності", "імпорт електроенергії",
             "отключения света", "обстрел энергетики", "Запорожская АЭС",
             "енергосистема України", "європейська енергомережа"),
    "UA-F": ("транзит газу", "ГТС України", "Нафтогаз", "транзитний контракт", "Дружба",
             "нафтопровід", "газосховища", "транзит газа", "транзитный контракт",
             "транзит через територію України", "європейські покупці газу",
             "нефтепровод Дружба"),
    "UA-G": ("соняшникова олія", "соняшник", "олійні культури", "ріпак", "шрот",
             "переробка соняшнику", "подсолнечное масло", "подсолнечник", "масличные культуры",
             "олійні культури України", "європейський ринок олії"),
    "UA-H": ("залізна руда", "Кривий Ріг", "металургія", "агломерат", "окатиші",
             "експорт руди", "железная руда", "Кривой Рог", "металлургия",
             "гірничо-металургійний комплекс України", "залізорудна сировина"),
    "BY-A": ("калійныя ўгнаенні", "калійная соль", "хларыд калію", "экспарт угнаенняў",
             "калийные удобрения", "хлорид калия", "экспорт удобрений", "Беларуськалий",
             "экспарт ва ўмовах санкцый", "калійная прамысловасць"),
    "BY-B": ("транзіт праз Літву", "Клайпеда", "чыгунка", "перавозкі", "порт Клайпеда",
             "транзит через Литву", "железная дорога", "перевалка в российских портах",
             "перавозкі ўгнаенняў чыгункай", "новыя маршруты ўнутры саюза"),
    "BY-C": ("нафтаперапрацоўка", "Мазырскі НПЗ", "Нафтан", "прэмія да нафты",
             "паставы нафты", "нефтепереработка", "Мозырский НПЗ", "премия к нефти",
             "поставки нефти", "паставы нафты ў Беларусь", "Дружба"),
    "BY-D": ("кошык валют", "курс беларускага рубля", "стаўка рэфінансавання",
             "афіцыйны курс", "БВФБ", "валютная корзина", "курс белорусского рубля",
             "попыт на валюту ўнутры краіны", "ставка рефинансирования",
             "официальный курс"),
    "BY-E": ("драўніна", "лесаматэрыялы", "малочная прадукцыя", "паралельны імпарт",
             "БУТБ", "таварная біржа", "древесина", "молочная продукция",
             "гандаль ва ўмовах санкцый", "параллельный импорт", "товарная биржа"),
    "XX-A": ("ваенны рызыка", "страхаванне суднаў", "військовий ризик", "страхування суден",
             "фрахт", "ставка фрахту", "фрахт ва ўмовах вайны", "воєнні ризики для суден",
             "военный риск", "страхование судов", "ставка фрахта"),
    "XX-B": ("санкцыі", "санкції", "санкционный пакет", "пакет санкцій", "перамовы",
             "переговори", "припинення вогню", "Європейський Союз санкції",
             "рашэнні ўлад аб санкцыях", "эскалацыя", "ескалація"),
    "XX-C": ("святкові дні", "робочі дні", "перенесення робочих днів", "святочныя дні",
             "Радуніца", "выхадныя дні", "святочныя дні ў Беларусі",
             "перенесення робочих днів в Україні", "праздничные дни",
             "перенос рабочих дней"),
}

_CYRILLIC_RANGES: tuple[tuple[int, int], ...] = ((0x0400, 0x04FF), (0x0500, 0x052F))
#: Letters that exist in Ukrainian and NOT in Russian: ї, є, ґ (and their capitals).
_UKRAINIAN_ONLY = "їєґЇЄҐ"
#: The letter that exists in Belarusian and in no other Cyrillic orthography here: ў.
_BELARUSIAN_ONLY = "ўЎ"
#: Letters that exist in Russian and in neither Ukrainian nor Belarusian: ы (BE has ы too), ъ, э.
_RUSSIAN_MARKERS = "ъэЪЭ"


def has_cyrillic(text: str) -> bool:
    """True when the text carries at least one Cyrillic codepoint."""
    return any(any(lo <= ord(ch) <= hi for lo, hi in _CYRILLIC_RANGES) for ch in str(text))


def has_ukrainian(text: str) -> bool:
    """True when the text carries a letter that exists in Ukrainian and not in Russian."""
    return any(ch in _UKRAINIAN_ONLY for ch in str(text))


def has_belarusian(text: str) -> bool:
    """True when the text carries the Belarusian-only letter u-short (ў)."""
    return any(ch in _BELARUSIAN_ONLY for ch in str(text))


def has_russian(text: str) -> bool:
    """True when the text carries a hard or reversed sign -- Russian and Belarusian orthography,
    absent from Ukrainian. Russian is declared as a native language of BOTH jurisdictions and
    this is how the pack proves it actually carries it rather than claiming it."""
    return any(ch in _RUSSIAN_MARKERS for ch in str(text))


def terms_for(predicate: Any, terminology: Mapping[str, Iterable[str]] | None = None
              ) -> list[str]:
    rows = TERMINOLOGY if terminology is None else terminology
    return [t for terms in rows.values() for t in terms if predicate(t)]


def term_count(terminology: Mapping[str, Iterable[str]] | None = None) -> int:
    rows = TERMINOLOGY if terminology is None else terminology
    return len({t for terms in rows.values() for t in terms})


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


def _seq(values: Iterable[Any]) -> tuple[str, ...]:
    return tuple(str(v) for v in values)


def source_class(sid: str, label: str, *, layer: str, roots: Iterable[str],
                 queries: Iterable[str], languages: Iterable[str], access_label: str,
                 credibility: str, predictive_state: str, licence: str,
                 machine_use_allowed: bool = True, notes: str = "") -> dict[str, Any]:
    """One class of source with the concrete roots a crawler can start from, tagged with the ONE
    layer it belongs to and the three INDEPENDENT labels: what the terms permit, how much the
    desk believes it, and whether it has ever been shown to predict anything."""
    if layer not in SOURCE_LAYERS:
        raise ValueError(f"source {sid}: layer {layer!r} not one of {list(SOURCE_LAYERS)}")
    if access_label not in ACCESS_LABELS:
        raise ValueError(f"source {sid}: access_label {access_label!r} is not recognised")
    if credibility not in CREDIBILITY_LABELS:
        raise ValueError(f"source {sid}: credibility {credibility!r} is not recognised")
    if predictive_state not in PREDICTIVE_STATES:
        raise ValueError(f"source {sid}: predictive_state {predictive_state!r} is not recognised")
    return {"id": sid, "label": label, "layer": layer, "roots": _seq(roots),
            "queries": _seq(queries), "languages": _seq(languages),
            "access_label": access_label, "credibility": credibility,
            "predictive_state": predictive_state,
            "machine_use_allowed": bool(machine_use_allowed), "licence": licence, "notes": notes}


def absent_layer(layer: str, reason: str) -> dict[str, Any]:
    """A layer with nothing in it, declared BY NAME with the reason. A blank layer and an absent
    layer look identical in a table and mean opposite things (L1.28a)."""
    if layer not in SOURCE_LAYERS:
        raise ValueError(f"absent layer {layer!r} not one of {list(SOURCE_LAYERS)}")
    return {"id": f"absent_{layer}", "label": f"NO SOURCE IN THIS LAYER: {layer}", "layer": layer,
            "roots": (), "queries": (), "languages": (), "access_label": "ACCESS_UNCLEAR",
            "credibility": "UNKNOWN", "predictive_state": "UNTESTED",
            "machine_use_allowed": False, "licence": "n/a",
            "notes": f"DECLARED ABSENT, NOT BLANK: {reason}"}


SOURCE_CLASSES: tuple[dict[str, Any], ...] = (
    # ---- official
    source_class(
        "ua_nbu", "National Bank of Ukraine: rate decisions, the official hryvnia rate, "
                  "reserves, interventions, the inflation report and the FX regulation",
        layer="official",
        roots=("https://bank.gov.ua/ua/monetary/archive-rish",
               "https://bank.gov.ua/ua/markets/exchangerates",
               "https://bank.gov.ua/ua/statistic/sector-external",
               "https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange"),
        queries=("облікова ставка", "рішення Правління НБУ", "офіційний курс гривні",
                 "міжнародні резерви", "валютні інтервенції", "керована гнучкість курсу",
                 "інфляційний звіт", "валютні обмеження"),
        languages=("uk", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public; the rate endpoint is an open API",
        notes="the NBU publishes an OPEN JSON endpoint for the official rate, which is the "
              "cheapest point-in-time series in this pack -- and the rate it returns is "
              "EFFECTIVE THE NEXT BUSINESS DAY, which is the trap every hryvnia study falls in"),
    source_class(
        "ua_minagro_customs", "Ministry of Agrarian Policy and Food and the State Customs "
                              "Service: grain export tonnage, the export memorandum, sowing and "
                              "harvest progress",
        layer="official",
        roots=("https://minagro.gov.ua/news", "https://customs.gov.ua/statistika-ta-reiestri",
               "https://minagro.gov.ua/napryamki/roslinnictvo"),
        queries=("експорт зерна", "меморандум щодо експорту", "посівна кампанія",
                 "збирання врожаю", "намолочено тонн", "митна статистика", "експорт олії",
                 "врожай зернових"),
        languages=("uk",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE MEASURABLE HALF OF THE CORRIDOR. A counted physical flow published by the "
              "state that ships it; the season-to-date cumulative is posted in Ukrainian first "
              "and reaches the English trade press a day or two later"),
    source_class(
        "ua_rada_zakon", "The Verkhovna Rada's legal database (zakon.rada.gov.ua) and the "
                         "Cabinet's resolutions: martial-law acts, the holiday law, export "
                         "licensing, the budget",
        layer="official",
        roots=("https://zakon.rada.gov.ua", "https://www.kmu.gov.ua/npa",
               "https://zakon.rada.gov.ua/laws/show/3258-20"),
        queries=("Закон України про внесення змін", "воєнний стан", "постанова Кабінету "
                 "Міністрів", "ліцензування експорту", "перенесення святкових днів",
                 "Кодекс законів про працю стаття 73", "державний бюджет"),
        languages=("uk",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE LEGAL DATABASE IS THE ONLY CITABLE STAMP for a Ukrainian dated event. The "
              "pack's holiday rule cites Law No. 3258-IX here and its import-ban rows stay "
              "PRESS_REPORTED precisely because no act number is attached to them yet"),
    source_class(
        "ua_ukrstat_mof", "State Statistics Service and the Ministry of Finance of Ukraine: "
                          "CPI, industrial output, the bond auction results, external financing",
        layer="official",
        roots=("https://www.ukrstat.gov.ua", "https://mof.gov.ua/uk/ovdp",
               "https://mof.gov.ua/uk/news"),
        queries=("індекс споживчих цін", "промислове виробництво", "аукціон ОВДП",
                 "зовнішнє фінансування", "державний борг", "валовий внутрішній продукт"),
        languages=("uk", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="PUBLICATION WAS CURTAILED UNDER MARTIAL LAW: several series were suspended, "
              "delayed or reclassified from 2022. What is missing is named in the dataset rows "
              "as UNMEASURED and never silently treated as a zero"),
    source_class(
        "by_nbrb", "National Bank of the Republic of Belarus: the refinancing rate, the official "
                   "BYN rate, THE PUBLISHED CURRENCY BASKET and its weights, monetary statistics",
        layer="official",
        roots=("https://www.nbrb.by/statistics/rates/ratesdaily.asp",
               "https://www.nbrb.by/mp/refrate", "https://www.nbrb.by/statistics",
               "https://api.nbrb.by/exrates/rates"),
        queries=("кошык валют", "стаўка рэфінансавання", "афіцыйны курс беларускага рубля",
                 "валютная корзина", "ставка рефинансирования", "официальный курс",
                 "золотовалютные резервы", "двусторонний курс"),
        languages=("be", "ru", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public; an open rates API exists",
        notes="THE BASKET AND ITS WEIGHTS ARE PUBLISHED HERE, which is what makes BY-D a "
              "hypothesis about a RESIDUAL rather than a re-estimation of a coefficient the "
              "central bank already announced; the rates API is point-in-time friendly"),
    source_class(
        "by_belstat_customs", "National Statistical Committee and the State Customs Committee of "
                              "Belarus: foreign trade by commodity group, output, prices",
        layer="official",
        roots=("https://www.belstat.gov.by/ofitsialnaya-statistika/",
               "https://www.customs.gov.by", "https://www.belstat.gov.by/en/"),
        queries=("знешні гандаль", "экспарт тавараў", "калійныя ўгнаенні экспарт",
                 "внешняя торговля", "экспорт товаров", "индекс потребительских цен",
                 "производство продукции", "таможенная статистика"),
        languages=("be", "ru"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="SEVERAL EXPORT LINES WERE RECLASSIFIED OR WITHHELD AFTER 2022 -- potash and oil "
              "products above all. The withholding is a measurement, not a gap: the pack reads "
              "the mirror in UN Comtrade for those months and says which half it used"),
    source_class(
        "by_pravo", "pravo.by (the National Legal Internet Portal) and the President's and "
                    "Council of Ministers' acts: the Labour Code, the holiday transfers, the "
                    "administered-price resolutions",
        layer="official",
        roots=("https://pravo.by", "https://president.gov.by/ru/documents",
               "https://www.government.by/ru/solutions/"),
        queries=("Працоўны кодэкс артыкул 147", "пастанова Савета Міністраў",
                 "перанос рабочых дзён", "указ Прэзідэнта", "регулирование цен постановление",
                 "государственные праздники", "непрацоўныя дні"),
        languages=("be", "ru"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the Belarusian statute book, where Radunitsa's status and the annual working-day "
              "transfers are citable; Resolution No. 713's administered-price regime lives here "
              "and is why Belarusian CPI is a policy variable rather than a measurement"),
    source_class(
        "intl_official", "IMF Ukraine country page, the EU Official Journal, the World Bank and "
                         "the EBRD: programme reviews, the import-restriction acts, the "
                         "financing schedule",
        layer="official",
        roots=("https://www.imf.org/en/Countries/UKR", "https://eur-lex.europa.eu",
               "https://www.worldbank.org/en/country/ukraine"),
        queries=("Ukraine Extended Fund Facility review", "Commission Implementing Regulation "
                 "Ukraine cereals", "solidarity lanes", "Ukraine Facility disbursement",
                 "Ukraine reconstruction financing"),
        languages=("en",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the IMF review calendar is the DISBURSEMENT clock the NBU's reserves depend on, "
              "and EUR-Lex is where a neighbour import ban becomes a citable act rather than a "
              "press report -- the two things this pack most needs to date"),
    # ---- institutional
    source_class(
        "ua_grain_trade_bodies", "The Ukrainian Grain Association, the Ukrainian Agrarian "
                                 "Council, UkrOliyaProm and the Ukrainian Sea Ports Authority: "
                                 "export forecasts, port throughput, the memorandum",
        layer="institutional",
        roots=("https://uga.ua", "https://uac.org.ua", "https://uspa.gov.ua",
               "https://www.ukroliya.com.ua"),
        queries=("прогноз експорту зерна", "Українська зернова асоціація", "перевалка в портах",
                 "Адміністрація морських портів", "олійно-жировий комплекс",
                 "потужності перевалки", "баланс зерна"),
        languages=("uk", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the associations publish an export forecast BEFORE the ministry revises its own, "
              "and the ports authority publishes throughput by terminal -- between them they "
              "date a corridor change about a week earlier than the official monthly"),
    source_class(
        "by_exchanges", "The Belarusian Currency and Stock Exchange (BCSE) and the Belarusian "
                        "Universal Commodity Exchange (BUCE): the FX session and the published "
                        "commodity auction results",
        layer="institutional",
        roots=("https://www.bcse.by", "https://www.butb.by", "https://www.bcse.by/ru/"),
        queries=("БВФБ гандлі", "валютная сесія", "БУТБ таргі", "біржавыя таргі лесаматэрыялы",
                 "гандаль ва ўмовах санкцый", "валютная сессия", "биржевые торги",
                 "результаты торгов", "экспортные торги"),
        languages=("be", "ru"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="NO VENUE FEED AND NO ORDER BOOK IS TOUCHED. These exchanges PUBLISH their session "
              "results, and the published result is the ground; BUCE's timber and dairy auction "
              "prices are the only unlicensed Belarusian physical prices the desk can read"),
    source_class(
        "ua_energy_institutions", "Ukrenergo, the Gas TSO of Ukraine, Naftogaz and the Market "
                                  "Operator: grid status, transit nominations, storage, the "
                                  "day-ahead market",
        layer="institutional",
        roots=("https://ua.energy", "https://tsoua.com", "https://www.naftogaz.com",
               "https://www.oree.com.ua"),
        queries=("Укренерго", "графіки відключень", "транзит газу", "потужність газосховищ",
                 "ринок на добу наперед", "переток електроенергії", "аварійна допомога",
                 "обсяг транспортування газу"),
        languages=("uk", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="these are the operators, not the ministry: the numbers are the SYSTEM'S and are "
              "posted daily, which is the only way to tell a strike's physical effect from its "
              "political reporting"),
    # ---- academic
    source_class(
        "ua_academic", "Kyiv School of Economics, the Vernadsky National Library, the NBU's own "
                       "working papers and the international literature on the grain corridor",
        layer="academic",
        roots=("https://kse.ua/research/", "http://www.nbuv.gov.ua",
               "https://bank.gov.ua/ua/research", "https://openalex.org"),
        queries=("вплив війни на економіку України", "експорт зерна дослідження",
                 "курсова політика НБУ", "трансмісійний механізм монетарної політики",
                 "Black Sea Grain Initiative food prices", "war and commodity markets Ukraine"),
        languages=("uk", "en"), access_label="OPEN_DATA", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="open access / publisher terms",
        notes="KSE's own agricultural-damage and export-cost estimates are the mechanism source "
              "for UA-B and UA-C; every paper is a HYPOTHESIS here until the desk reproduces it"),
    source_class(
        "by_academic", "BEROC (the Belarusian Economic Research and Outreach Centre, in exile), "
                       "the BSU electronic library and the CIS monetary literature",
        layer="academic",
        roots=("https://beroc.org/en/publications/", "https://elib.bsu.by", "https://core.ac.uk"),
        queries=("беларуская эканоміка даследаванне", "валютная политика Беларуси",
                 "курсовая политика корзина", "белорусская экономика прогноз",
                 "Belarus potash export economics", "Belarus exchange rate basket"),
        languages=("be", "ru", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="open access",
        notes="BEROC IS THE MEASUREMENT AND THE ABSENCE AT ONCE: independent Belarusian "
              "macroeconomics is now written outside the country, so the academic layer for BY "
              "exists but is thinner and slower than Ukraine's, and that is stated rather than "
              "papered over"),
    # ---- practitioner
    source_class(
        "ua_agri_trade_press", "The agrarian trade press: Latifundist, APK-Inform, "
                               "UkrAgroConsult, Agravery and Agropolit -- forward prices, "
                               "logistics costs, port queues, the traders' own commentary",
        layer="practitioner",
        roots=("https://latifundist.com", "https://www.apk-inform.com",
               "https://ukragroconsult.com", "https://agravery.com"),
        queries=("закупівельні ціни на пшеницю", "ціна кукурудзи CPT порт", "вартість логістики",
                 "черга в порту", "форвардні контракти", "ціна соняшнику",
                 "закупочные цены пшеница", "стоимость перевалки"),
        languages=("uk", "ru", "en"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms; some behind a paywall",
        notes="LATIFUNDIST AND APK-INFORM ARE GENUINELY THE BEST UKRAINIAN GRAIN GROUND, and "
              "they publish in Ukrainian and Russian for a commercial audience that trades. The "
              "PRICE ASSESSMENTS inside them are subscription ground and are registered "
              "separately; what is free is the dated logistics and queue reporting"),
    source_class(
        "price_assessments", "The licensed price reporting agencies for grain, oils and "
                             "fertiliser: Argus, CRU, Profercy, ICIS and the terminal vendors",
        layer="practitioner",
        roots=("https://www.argusmedia.com", "https://www.crugroup.com"),
        queries=("potash MOP Brazil cfr assessment", "urea Middle East fob",
                 "Black Sea wheat fob assessment", "sunflower oil fob Ukraine assessment"),
        languages=("en",), access_label="LICENSED", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="subscription; terms forbid machine extraction",
        machine_use_allowed=False,
        notes="REGISTERED, NEVER SCRAPED. The potash price and the Black Sea FOB basis are the "
              "two numbers this pack would most like and cannot lawfully have, which is exactly "
              "why BY-A and UA-B are written to be measured on TONNAGE and on the CROPS instead "
              "-- the absence is named and worked WITH, not worked around"),
    source_class(
        "by_practitioner", "Belarusian business and market commentary that still publishes: "
                           "Myfin, Banki.by, Infobank and the exiled analytical outlets",
        layer="practitioner",
        roots=("https://myfin.by", "https://infobank.by", "https://banki24.by"),
        queries=("курс валют прогноз", "стаўка рэфінансавання прагноз", "курс доллара Беларусь",
                 "девальвация белорусского рубля", "попыт на валюту ўнутры краіны",
                 "депозитные ставки", "обменный курс банки"),
        languages=("ru", "be"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="Myfin publishes the bank-by-bank cash rate beside the official one, which is the "
              "spread BY-D conditions on; there is no Belarusian sell-side research to read"),
    # ---- retail ecology
    source_class(
        "ua_retail", "Ukrainian retail money communities: Minfin.com.ua rate boards and forums, "
                     "the bank Telegram channels, r/ukraine and the cash-rate chats",
        layer="retail_ecology",
        roots=("https://minfin.com.ua/ua/currency/", "https://index.minfin.com.ua",
               "https://www.reddit.com/r/ukraine/"),
        queries=("готівковий курс долара", "курс в обмінниках", "де купити долар",
                 "курс на чорному ринку", "обмежння на картку", "готівка євро",
                 "наличный курс доллара", "курс в обменниках сегодня"),
        languages=("uk", "ru"), access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="platform terms; public posts only",
        notes="KEPT AT LOW WEIGHT AND NEVER A SOURCE OF EDGE. The cash-rate boards and the "
              "queue chatter DATE the capital-control stress episodes UA-D conditions on, which "
              "is a calendar contribution and not a price one"),
    source_class(
        "by_retail", "Belarusian retail money ecology and the NBRB-licensed forex companies' "
                     "own client statistics and marketing",
        layer="retail_ecology",
        roots=("https://myfin.by/currency", "https://www.nbrb.by/finsector/forex",
               "https://t.me/s/myfinby"),
        queries=("форекс-кампаніі Беларусі", "форекс компании Беларусь статистика",
                 "курс наличный Минск", "попыт на валюту ўнутры краіны",
                 "обменные пункты курс", "клиенты форекс отчет"),
        languages=("be", "ru"), access_label="PUBLIC", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="free statistics; platform terms for the channels",
        notes="BELARUS IS UNUSUAL AND WORTH THE ROW: retail margin FX is LICENSED and the "
              "central bank publishes aggregate client statistics for it, which almost no other "
              "country in this department does. It is a retail-flow series, not an edge"),
    # ---- app ecosystem
    source_class(
        "ua_apps", "The Ukrainian state and banking app rails: Diia, the NBU open-data and rate "
                   "APIs, Privat24 and monobank rate endpoints, the air-raid alert apps",
        layer="app_ecosystem",
        roots=("https://bank.gov.ua/ua/open-data/api-dev", "https://diia.gov.ua",
               "https://api.monobank.ua/docs/"),
        queries=("відкриті дані НБУ API", "курс готівковий API", "Дія послуги",
                 "тривога застосунок", "курс банку онлайн", "картковий курс"),
        languages=("uk", "en"), access_label="OPEN_DATA", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public APIs with published terms",
        notes="THE ONE APP-LAYER SERIES IN THIS PACK WITH A REAL LEAD: the banks' CARD "
              "settlement rate moves before the official next-day fix does, and both are "
              "published through documented endpoints rather than scraped"),
    source_class(
        "by_apps", "The Belarusian payment and rate rails: the ERIP single settlement space, the "
                   "NBRB rates API and the bank apps' published rate boards",
        layer="app_ecosystem",
        roots=("https://api.nbrb.by", "https://raschet.by", "https://myfin.by/bank"),
        queries=("ЕРИП адзіная разліковая прастора", "плацяжы ва ўсіх банках", "ЕРИП платежи",
                 "курсы банков приложение", "API курсов НБРБ", "безналичный курс банка"),
        languages=("be", "ru"), access_label="OPEN_DATA", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public API",
        notes="the NBRB's rates API returns the official rate AND the basket value, which makes "
              "the Belarusian half of this pack unusually easy to keep point-in-time"),
    # ---- media
    source_class(
        "ua_media", "Ukrainian news and business media: Ukrinform, Ukrainska Pravda and "
                    "Ekonomichna Pravda, Suspilne, Interfax-Ukraine and Forbes Ukraine",
        layer="media",
        roots=("https://www.ukrinform.ua/rubric-economy", "https://www.epravda.com.ua",
               "https://suspilne.media/economics/", "https://interfax.com.ua"),
        queries=("зернова угода новини", "курс гривні сьогодні", "обстріл порту Одеси",
                 "енергетика новини", "експорт зерна новини", "санкції проти Білорусі",
                 "зерновая сделка новости", "курс гривны сегодня"),
        languages=("uk", "ru", "en"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="EKONOMICHNA PRAVDA IS THE ONE THAT MATTERS: it carries the ministry's number and "
              "the trader's reaction in the same piece, and Interfax-Ukraine timestamps the "
              "announcement minute the official page often omits"),
    source_class(
        "by_media", "Belarusian media on both sides: BELTA and the state wire, and the exiled "
                    "independent press -- Nasha Niva, Zerkalo (the tut.by successor), Euroradio",
        layer="media",
        roots=("https://www.belta.by/economics/", "https://nashaniva.com",
               "https://news.zerkalo.io", "https://euroradio.fm"),
        queries=("калійныя ўгнаенні навіны", "санкцыі супраць Беларусі", "экспарт навіны",
                 "калийные удобрения новости", "транзит через Литву новости",
                 "нефтепереработка Беларусь", "курс рубля Беларусь новости"),
        languages=("be", "ru"), access_label="PUBLIC_WITH_TERMS", credibility="UNRELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="BOTH SIDES ARE KEPT AND BOTH ARE LABELLED. BELTA is AUTHORITATIVE for what the "
              "state SAID and UNRELIABLE as a description of the economy; the exiled outlets "
              "are the opposite shape of error. The row is carried at UNRELIABLE and at low "
              "weight, never dropped, because a dated claim is testable even when it is wrong"),
    # ---- archive
    source_class(
        "archive_web", "web.archive.org snapshots of the pages that overwrite in place: the "
                       "ministry's tonnage posts, the NBU and NBRB daily rate tables, the JCC's "
                       "vessel page and Ukrenergo's outage schedule",
        layer="archive",
        roots=("https://web.archive.org/web/*/minagro.gov.ua*",
               "https://web.archive.org/web/*/nbrb.by/statistics/rates*",
               "https://web.archive.org/web/*/un.org/*black-sea-grain*"),
        queries=("minagro експорт зерна archive", "nbrb курс архив", "JCC vessel movements "
                 "archive", "Ukrenergo графіки відключень архів"),
        languages=("uk", "ru", "en"), access_label="PUBLIC_ARCHIVE", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="Internet Archive terms",
        notes="THE BSGI VESSEL PAGE IS THE REASON THIS LAYER EXISTS. The Initiative ended in "
              "2023 and its live page is gone; without the crawl the single cleanest physical "
              "experiment in the pack is reconstructible only from press quotes"),
    source_class(
        "archive_legal", "The legal and statistical archives: zakon.rada.gov.ua's full act "
                         "history, pravo.by's archive, Ukrstat's and Belstat's discontinued "
                         "series, and the pre-2022 NBU statistical bulletins",
        layer="archive",
        roots=("https://zakon.rada.gov.ua/laws/main", "https://pravo.by/document/",
               "https://www.ukrstat.gov.ua/druk/publicat/kat_u/publ1_u.htm"),
        queries=("редакція закону від", "архіў пастаноў", "архив постановлений",
                 "статистичний щорічник України", "статыстычны штогоднік", "припинена серія"),
        languages=("uk", "be", "ru"), access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="zakon.rada.gov.ua keeps EVERY REDACTION of an act with its effective date, which "
              "is the only way to reconstruct the pre-2023 Ukrainian holiday calendar from a "
              "document rather than from memory -- and this pack's calendar break depends on it"),
    # ---- physical economy
    source_class(
        "ports_and_shipping", "Ports, corridors and shipping: the Ukrainian Sea Ports Authority, "
                              "the Danube ports, the UN's published BSGI vessel table, the "
                              "Turkish Straits notices and the public AIS port-call ground",
        layer="physical_economy",
        roots=("https://uspa.gov.ua", "https://www.un.org/en/black-sea-grain-initiative",
               "https://atlas.cnr.it/", "https://www.marinetraffic.com/en/ais/home"),
        queries=("перевалка вантажів порт", "Ізмаїл Рені вантажообіг", "судно зайшло в порт",
                 "Black Sea Grain Initiative vessel movements", "Bosphorus transit notice",
                 "грузооборот порта"),
        languages=("uk", "en", "tr"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public; platform terms for the AIS sites",
        notes="NO EXCHANGE FEED AND NO ORDER BOOK ANYWHERE HERE (mandate 2026-08-18). A vessel "
              "call is a physical fact reported by a port authority and by public AIS, and it "
              "leads the customs tonnage by two to six weeks"),
    source_class(
        "energy_physical", "The physical energy plane: Ukrenergo and ENTSO-E transparency, GTSOU "
                           "nominations, AGSI gas storage, the IAEA's Zaporizhzhia updates and "
                           "the Druzhba flow reporting",
        layer="physical_economy",
        roots=("https://transparency.entsoe.eu", "https://agsi.gie.eu", "https://tsoua.com",
               "https://www.iaea.org/newscenter/focus/ukraine"),
        queries=("переток електроенергії ENTSO-E", "запаси газу в сховищах",
                 "транзит газу добовий", "Запорізька АЕС стан", "поставки по Дружбе",
                 "аварийная помощь энергосистеме"),
        languages=("uk", "ru", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="ENTSO-E and AGSI are MACHINE-READABLE and European, so a Ukrainian grid event "
              "becomes a European power and gas observable without needing a Ukrainian feed -- "
              "which is the only reason UA-E has an executable leg at all"),
    source_class(
        "agri_balances", "The world agricultural balance sheets: USDA FAS GAIN and PSD, FAO "
                         "AMIS and GIEWS, the IGC grain market report and UN Comtrade",
        layer="physical_economy",
        roots=("https://fas.usda.gov/data/search?f%5B0%5D=country%3A%22Ukraine%22",
               "https://www.amis-outlook.org", "https://www.igc.int",
               "https://comtrade.un.org"),
        queries=("Ukraine grain and feed annual", "Ukraine oilseeds and products annual",
                 "Belarus fertiliser export", "AMIS market monitor Black Sea",
                 "IGC grain market report", "HS 3104 potash exports"),
        languages=("en",), access_label="OPEN_DATA", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="public domain (US government work) / free",
        notes="THE INDEPENDENT READ, and for Belarus often the ONLY one: when Belstat stops "
              "publishing a line, the counterparties' import declarations in Comtrade still "
              "bound it, and the GAIN reports describe the regime in English WITH its dates"),
    # ---- source graph
    source_class(
        "bs_source_graph", "Who cites whom across this plane: minagro -> Latifundist and "
                           "APK-Inform -> Reuters and the futures desks; the NBU release -> "
                           "Ekonomichna Pravda -> the cash-rate boards; BELTA -> the Russian "
                           "wires -> the fertiliser trade press",
        layer="source_graph",
        roots=("https://latifundist.com", "https://www.epravda.com.ua",
               "https://www.belta.by/economics/"),
        queries=("за даними Мінагрополітики", "повідомляє Укренерго", "як повідомили в НБУ",
                 "паведамляе БЕЛТА", "со ссылкой на источники", "за інформацією джерел",
                 "трейдери повідомляють"),
        languages=("uk", "ru", "be"), access_label="PUBLIC", credibility="UNKNOWN",
        predictive_state="UNTESTED", licence="derived from the public sources above",
        notes="'за інформацією джерел' and 'со ссылкой на источники' mark the unattributed leak "
              "that precedes a corridor or ban decision by a day or two on this plane; the "
              "graph is how a leak is told from a repost, and it is the only way to date an "
              "IMPORT_BAN_EVENTS row before the Official Journal prints the act"),
)

#: EVERY LAYER IS SOURCED. Nothing is declared absent at the PACK level -- both jurisdictions
#: have, between them, a real ground in all ten. What is NOT symmetric is named below instead,
#: because a per-jurisdiction hole is invisible in a per-pack table and is still a hole.
LAYER_ABSENCES: dict[str, str] = {}

#: PER-JURISDICTION MEASURED ABSENCES. The pack covers a layer when EITHER country has ground in
#: it; these rows say which country does not, so a miner steered at one jurisdiction reports
#: UNMEASURED by name rather than quietly reading the other country and calling it coverage.
JURISDICTION_LAYER_GAPS: tuple[dict[str, str], ...] = (
    {"jurisdiction": "ua", "layer": "institutional",
     "reason": "there is NO functioning Ukrainian equity or derivatives tape. The Ukrainian "
               "Exchange and PFTS have been effectively dormant since 2022-02-24 and no public "
               "order book or index series is available, so UA's institutional layer is the "
               "grain associations, the ports authority and the energy operators -- never an "
               "exchange. Any equity-mechanics cell for Ukraine is UNMEASURED by construction"},
    {"jurisdiction": "ua", "layer": "retail_ecology",
     "reason": "resident margin FX is PROHIBITED: the NBU's 2022-02-24 currency restrictions ban "
               "cross-border transfers for investment, so there is no lawful Ukrainian retail "
               "leverage population to measure. What remains is the CASH rate ecology, which is "
               "what the row above actually reads, and the pack says so rather than presenting "
               "a cash-queue forum as a retail-flow series"},
    {"jurisdiction": "by", "layer": "academic",
     "reason": "independent Belarusian macroeconomic research now happens OUTSIDE the country "
               "(BEROC in exile); domestic university output on exchange-rate and trade policy "
               "is sparse and largely descriptive after 2020. The layer exists for BY and is "
               "thin, slow and one-institution deep, which bounds what BY-D can cite"},
    {"jurisdiction": "by", "layer": "physical_economy",
     "reason": "Belarus is LANDLOCKED and its physical export flow is now rail into third-party "
               "ports that do not break out its cargo. There is no Belarusian port authority to "
               "read and the Russian Baltic terminals publish no Belarusian line, so BY-B's "
               "physical half is reconstructed from Lithuanian and Russian rail statistics and "
               "from Comtrade mirrors -- an INFERENCE, labelled as one"},
)


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
    return {"code": CODE, "jurisdictions": JURISDICTIONS, "layer_counts": counts,
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
            "jurisdiction_gaps": JURISDICTION_LAYER_GAPS,
            "rule": "ten layers, each carrying a source or named ABSENT with a reason; a "
                    "PER-JURISDICTION hole is named separately in JURISDICTION_LAYER_GAPS "
                    "because a two-country pack can cover a layer while one of its countries "
                    "has nothing in it; fringe and unreliable PUBLIC material is kept as a "
                    "low-weight evidence object and never dropped; a page whose terms forbid "
                    "machine extraction is registered machine_use_allowed=false, never scraped "
                    "and never omitted"}


#: NATIVE SEARCH TERRITORIES FOR THE DEEP-FOREST MINER: at least three phrases per layer, in the
#: script the layer is actually written in. This is the list a crawler runs, as opposed to the
#: TERMINOLOGY above, which is the vocabulary a text screen matches on.
QUERY_TERRITORIES: dict[str, tuple[str, ...]] = {
    "official": ("рішення Правління Національного банку України",
                 "офіційний курс гривні на сьогодні", "експорт зерна з початку сезону",
                 "кошык валют Нацыянальнага банка", "пастанова Савета Міністраў перанос",
                 "внешняя торговля Беларуси экспорт удобрений"),
    "institutional": ("Українська зернова асоціація прогноз", "перевалка зерна в портах",
                      "БВФБ вынікі валютнай сесіі", "БУТБ біржавыя таргі лесаматэрыялы",
                      "гандаль ва ўмовах санкцый", "Укренерго стан енергосистеми"),
    "academic": ("дослідження експорту зерна України", "вплив зернової угоди на ціни",
                 "БЕРОК аналіз беларускай эканомікі", "валютная корзина Беларуси исследование",
                 "Black Sea Grain Initiative price impact study"),
    "practitioner": ("закупівельні ціни на кукурудзу CPT порт", "вартість фрахту Чорне море",
                     "форвардні ціни на пшеницю", "прагноз курсу ва ўмовах санкцый",
                     "прогноз курса белорусского рубля", "ставки перевалки в Ізмаїлі"),
    "retail_ecology": ("готівковий курс долара в обмінниках", "курс на чорному ринку гривня",
                       "курс наличный Минск обменники", "форекс-кампаніі Беларусі статыстыка",
                       "попыт на валюту ўнутры краіны", "ліміти на купівлю валюти"),
    "app_ecosystem": ("відкриті дані НБУ API курс", "картковий курс банку сьогодні",
                      "API курсаў НБРБ", "ЕРИП плацяжы", "плацяжы ва ўсіх банках",
                      "Дія довідка послуга"),
    "media": ("зернова угода новини сьогодні", "обстріл порту Одеса новини",
              "санкцыі супраць Беларусі навіны", "калийные удобрения новости экспорт",
              "транзит газу через Україну новини"),
    "archive": ("архів експорт зерна Мінагрополітики", "редакція закону від 2023 року",
                "архіў пастаноў pravo.by", "JCC vessel movements archive",
                "nbrb курс валют архив"),
    "physical_economy": ("вантажообіг Ізмаїла та Рені", "графіки відключень Укренерго",
                         "запаси газу в підземних сховищах", "перавозкі ўгнаенняў чыгункай",
                         "перевалка калия в российских портах", "Запорізька АЕС стан МАГАТЕ"),
    "source_graph": ("за даними Мінагрополітики повідомляє", "со ссылкой на источники в отрасли",
                     "паведамляе БЕЛТА з спасылкай", "трейдери повідомляють про",
                     "як повідомили в Національному банку"),
}


# --------------------------------------------------------------------------- datasets
DATASETS: tuple[dict[str, Any], ...] = (
    {"name": "Black Sea Grain Initiative vessel movement and inspection table",
     "source": "UN Joint Coordination Centre, Istanbul",
     "coverage": "2022-08-01 to 2023-07-17, every outbound and inbound vessel",
     "frequency": "daily", "publication_lag_days": 1.0,
     "revisions": "cumulative totals restated; the per-vessel rows are not revised",
     "licence": "free, public (UN)", "history_from": "2022-08", "pit_feasible": True,
     "assets": ("WHEAT", "CORN", "SOYBEAN"),
     "mechanism_families": ("supply_count", "event_reaction", "regime_break"),
     "how_to_fetch": "un.org/en/black-sea-grain-initiative -- the vessel movements page and its "
                     "daily table; the live page is GONE since the termination, so the only "
                     "vintage now is the Wayback crawl named in the archive layer"},
    {"name": "Ukrainian grain and oilseed export tonnage, season-to-date and monthly",
     "source": "Ministry of Agrarian Policy and Food / State Customs Service of Ukraine",
     "coverage": "2010 onward; marketing years from 1 July",
     "frequency": "monthly with weekly in-season updates", "publication_lag_days": 7.0,
     "revisions": "revised upward as customs declarations clear; use the FIRST print",
     "licence": "free, public", "history_from": "2010-07", "pit_feasible": True,
     "assets": ("WHEAT", "CORN", "SOYBEAN"),
     "mechanism_families": ("supply_count", "export_pace", "seasonal_flow"),
     "how_to_fetch": "minagro.gov.ua news feed for the weekly tonnage post and "
                     "customs.gov.ua/statistika-ta-reiestri for the monthly declaration data; "
                     "the Ukrainian post precedes the English trade summary by a day or two"},
    {"name": "Ukrainian port throughput by terminal (deep-sea and Danube)",
     "source": "Ukrainian Sea Ports Authority (AMPU/USPA)",
     "coverage": "2015 onward; Izmail and Reni broken out separately from 2022",
     "frequency": "monthly", "publication_lag_days": 20.0, "revisions": "minor, next month",
     "licence": "free, public", "history_from": "2015-01", "pit_feasible": False,
     "assets": ("WHEAT", "CORN", "SOYBEAN"),
     "mechanism_families": ("logistics", "supply_count"),
     "how_to_fetch": "uspa.gov.ua statistics section; the DANUBE split is what separates a "
                     "corridor closure from a corridor re-routing, and the page is overwritten "
                     "in place so the archive layer carries the point-in-time history"},
    {"name": "NBU official hryvnia rate, daily, effective the next business day",
     "source": "National Bank of Ukraine",
     "coverage": "1996 onward; the fixed eras 2022-02-24 to 2023-10-02 are a different series",
     "frequency": "daily (business days)", "publication_lag_days": 0.0, "revisions": "never",
     "licence": "free, public (open API)", "history_from": "1996-01", "pit_feasible": True,
     "assets": ("EURPLN", "USDPLN", "EURUSD"),
     "mechanism_families": ("fixing", "regime_break"),
     "how_to_fetch": "bank.gov.ua/NBUStatService/v1/statdirectory/exchange?date=YYYYMMDD&json "
                     "-- a documented open endpoint; the NEXT-DAY effective date must be "
                     "applied or every event study on it is one session ahead of itself"},
    {"name": "NBU key policy rate decisions and the MPC discussion summaries",
     "source": "National Bank of Ukraine",
     "coverage": "2015 onward under inflation targeting; eight scheduled decisions a year plus "
                 "the unscheduled wartime ones as a separate class",
     "frequency": "8 per year", "publication_lag_days": 0.0, "revisions": "never revised",
     "licence": "free, public", "history_from": "2015-08", "pit_feasible": True,
     "assets": ("EURPLN", "EURUSD", "XAUUSD"),
     "mechanism_families": ("policy_surprise", "event_reaction"),
     "how_to_fetch": "bank.gov.ua/ua/monetary/archive-rish for the decisions and "
                     "bank.gov.ua/ua/monetary/mpc for the discussion summary eleven days later"},
    {"name": "NBU international reserves and published FX intervention volumes",
     "source": "National Bank of Ukraine",
     "coverage": "2005 onward (reserves); daily intervention volumes from 2015",
     "frequency": "daily (interventions) / monthly (reserves)", "publication_lag_days": 2.0,
     "revisions": "reserves revised at the monthly final; interventions not revised",
     "licence": "free, public", "history_from": "2015-01", "pit_feasible": True,
     "assets": ("EURPLN", "EURUSD"),
     "mechanism_families": ("intervention", "external_balance"),
     "how_to_fetch": "bank.gov.ua/ua/markets/currency-market for the daily intervention and "
                     "bank.gov.ua/ua/statistic/sector-external for the reserves; under managed "
                     "flexibility the INTERVENTION is the policy and the rate is the residual"},
    {"name": "Ukrenergo grid status, consumption and emergency outage schedules",
     "source": "NPC Ukrenergo",
     "coverage": "2022-10 onward as a dated strike-and-outage series; consumption from 2019",
     "frequency": "daily and event-driven", "publication_lag_days": 0.0,
     "revisions": "outage schedules are replaced intraday", "licence": "free, public",
     "history_from": "2019-01", "pit_feasible": False,
     "assets": ("XNGUSD", "GER40", "EUSTX50"),
     "mechanism_families": ("physical_disruption", "event_reaction"),
     "how_to_fetch": "ua.energy news and the operator's Telegram/Facebook posts for the dated "
                     "outage notices, with ENTSO-E transparency for the cross-border flow; the "
                     "schedules are OVERWRITTEN IN PLACE, so a crawl is the only vintage"},
    {"name": "Ukrainian gas transit nominations and the transit contract status",
     "source": "Gas TSO of Ukraine (GTSOU)",
     "coverage": "2020-01-01 to 2024-12-31 under the five-year contract; zero from 2025-01-01",
     "frequency": "daily", "publication_lag_days": 1.0, "revisions": "same-day renomination",
     "licence": "free, public", "history_from": "2020-01", "pit_feasible": True,
     "assets": ("XNGUSD", "GER40", "EUSTX50"),
     "mechanism_families": ("physical_flow", "regime_break"),
     "how_to_fetch": "tsoua.com transparency pages for the daily nomination and the entry/exit "
                     "points; the 2024-12-31 EXPIRY is the largest single boundary in this "
                     "series and 2025-01-01 is a different regime, not a smaller number"},
    {"name": "European gas storage fill (AGSI) and ENTSO-E cross-border power flows",
     "source": "Gas Infrastructure Europe and ENTSO-E",
     "coverage": "2011 onward (AGSI); 2015 onward (ENTSO-E transparency)",
     "frequency": "daily (storage) / hourly (power)", "publication_lag_days": 1.0,
     "revisions": "ENTSO-E values are revised for up to a month", "licence": "free, public",
     "history_from": "2015-01", "pit_feasible": True,
     "assets": ("XNGUSD", "GER40", "EUSTX50"),
     "mechanism_families": ("physical_flow", "input_cost"),
     "how_to_fetch": "agsi.gie.eu API for storage and transparency.entsoe.eu for the Ukrainian "
                     "and Belarusian cross-border interconnector flows; these are the "
                     "MACHINE-READABLE European mirrors of two series the desk cannot fetch "
                     "locally, which is the only reason UA-E and UA-F have executable legs"},
    {"name": "EU cereal import licences, the solidarity-lane volumes and the restriction acts",
     "source": "European Commission DG AGRI and the Official Journal",
     "coverage": "2016 onward (dashboard); the restriction acts 2023-05 to 2023-09",
     "frequency": "weekly (dashboard) / event-driven (acts)", "publication_lag_days": 7.0,
     "revisions": "licence data restated weekly", "licence": "free, public",
     "history_from": "2016-07", "pit_feasible": True,
     "assets": ("WHEAT", "CORN", "EURPLN"),
     "mechanism_families": ("trade_decision", "administered_price", "basis"),
     "how_to_fetch": "the DG AGRI cereals dashboard for the weekly licences and EUR-Lex for the "
                     "Implementing Regulations; the NEIGHBOUR bans that preceded and outlived "
                     "the EU act are PRESS_REPORTED here until an act number is attached"},
    {"name": "Ukrainian domestic bond (OVDP) primary auction results",
     "source": "Ministry of Finance of Ukraine", "coverage": "2015 onward",
     "frequency": "weekly (Tuesdays)", "publication_lag_days": 0.0, "revisions": "never",
     "licence": "free, public", "history_from": "2015-01", "pit_feasible": True,
     "assets": ("EURPLN", "EURUSD"),
     "mechanism_families": ("liquidity", "calendar_settlement"),
     "how_to_fetch": "mof.gov.ua/uk/ovdp for the auction result; TREAT THE CUT-OFF AS A POLICY "
                     "VARIABLE, not a market expectation -- the bid is substantially "
                     "state-owned banks and reading it as consensus reads the government's own "
                     "funding decision as the market's view"},
    {"name": "NBRB official BYN rate, the published currency basket and its weights",
     "source": "National Bank of the Republic of Belarus",
     "coverage": "2009 onward (the basket); 2015 onward for the redenominated rate",
     "frequency": "daily", "publication_lag_days": 0.0, "revisions": "never",
     "licence": "free, public (open API)", "history_from": "2009-01", "pit_feasible": True,
     "assets": ("USDRUB", "EURRUB", "EURUSD"),
     "mechanism_families": ("fixing", "basket_state", "regime_break"),
     "how_to_fetch": "api.nbrb.by/exrates/rates?ondate=YYYY-MM-DD&periodicity=0 for the rates "
                     "and nbrb.by for the basket composition; the WEIGHTS make the rouble beta "
                     "arithmetic, and the residual to that arithmetic is what BY-D tests"},
    {"name": "Belarusian foreign trade by commodity group (potash, oil products, timber, dairy)",
     "source": "Belstat and the State Customs Committee of Belarus",
     "coverage": "2010 onward; several lines reclassified or withheld from 2022",
     "frequency": "monthly and quarterly", "publication_lag_days": 45.0,
     "revisions": "quarterly restatement", "licence": "free, public",
     "history_from": "2010-01", "pit_feasible": False,
     "assets": ("CORN", "WHEAT", "SOYBEAN"),
     "mechanism_families": ("supply_count", "terms_of_trade"),
     "how_to_fetch": "belstat.gov.by foreign-trade tables; WHERE A LINE IS WITHHELD the pack "
                     "reports UNMEASURED for that month and reads the Comtrade mirror below "
                     "instead -- the two are never silently spliced into one series"},
    {"name": "UN Comtrade mirror statistics: HS 3104 potash and HS 1001/1005/1512 grain and oil",
     "source": "UN Comtrade", "coverage": "2000 onward",
     "frequency": "monthly, heavily lagged", "publication_lag_days": 90.0,
     "revisions": "reporters restate for up to a year", "licence": "free, public",
     "history_from": "2000-01", "pit_feasible": False,
     "assets": ("CORN", "WHEAT", "SOYBEAN"),
     "mechanism_families": ("supply_count", "trade_decision"),
     "how_to_fetch": "comtrade.un.org API by reporter and HS code; THE MIRROR IS THE ANSWER TO "
                     "THE WITHHOLDING -- what Belarus stopped publishing, its counterparties "
                     "still declare as imports, and the sum bounds the flow"},
    {"name": "USDA FAS PSD balances and GAIN reports for Ukraine and Belarus",
     "source": "USDA Foreign Agricultural Service",
     "coverage": "PSD from 1960; the GAIN grain-and-feed and oilseeds annuals from 2000",
     "frequency": "monthly (PSD) / annual and semi-annual (GAIN)",
     "publication_lag_days": 10.0, "revisions": "PSD revised every month",
     "licence": "public domain (US government work)", "history_from": "2000-01",
     "pit_feasible": True, "assets": ("WHEAT", "CORN", "SOYBEAN"),
     "mechanism_families": ("balance_sheet", "release_surprise"),
     "how_to_fetch": "fas.usda.gov/data for PSD and the GAIN report search by country; the GAIN "
                     "report is also where the export regime and the neighbour bans are "
                     "described in English WITH their effective dates"},
    {"name": "IGC grain market report and FAO AMIS market monitor",
     "source": "International Grains Council and FAO AMIS",
     "coverage": "IGC from 1990; AMIS from 2011", "frequency": "monthly",
     "publication_lag_days": 5.0, "revisions": "forecasts revised monthly",
     "licence": "free, public (summary level)", "history_from": "2011-09", "pit_feasible": True,
     "assets": ("WHEAT", "CORN", "SOYBEAN", "SUGAR"),
     "mechanism_families": ("balance_sheet", "narrative_feature"),
     "how_to_fetch": "igc.int grain market report summary and amis-outlook.org market monitor; "
                     "AMIS is the G20's own Black Sea commentary and dates the policy events "
                     "the trade reacted to, which is the calendar half of the value"},
    {"name": "Black Sea war-risk insurance premium and Danube barge freight, as reported",
     "source": "the public press reporting of the Lloyd's market and the freight brokers",
     "coverage": "2022-02 onward as a dated, press-reported series",
     "frequency": "irregular, event-driven", "publication_lag_days": 3.0,
     "revisions": "never (each report is its own observation)",
     "licence": "publisher terms; the underlying assessments are LICENSED and not fetched",
     "history_from": "2022-02", "pit_feasible": False,
     "assets": ("WHEAT", "CORN", "XBRUSD"),
     "mechanism_families": ("freight_cost", "risk_premium"),
     "how_to_fetch": "the reported premium levels in Reuters, Lloyd's List and the Ukrainian "
                     "trade press; PRESS_REPORTED by construction -- the assessment itself is "
                     "subscription ground and is registered, never scraped, so no cell compiled "
                     "on this series is promoted without a second, independent dated source"},
    {"name": "Ukrainian and Belarusian statutory holiday calendars and the calendar break",
     "source": "zakon.rada.gov.ua (Law No. 3258-IX of 2023-07-14) and pravo.by",
     "coverage": "1991 onward; the Ukrainian break at 2023 and the Belarusian additions at "
                 "2020 (2 January) and 2024 (17 September)",
     "frequency": "annual (with the Belarusian transfer resolution each autumn)",
     "publication_lag_days": 0.0, "revisions": "never; an amended act is a new redaction",
     "licence": "free, public", "history_from": "1991-01", "pit_feasible": True,
     "assets": ("EURPLN", "EURUSD", "USDRUB"),
     "mechanism_families": ("holiday_liquidity", "regime_break", "calendar_settlement"),
     "how_to_fetch": "zakon.rada.gov.ua/laws/show/3258-20 for the Ukrainian amendment and "
                     "pravo.by for the Belarusian Labour Code and the annual transfer "
                     "resolution; DERIVED here rather than typed -- see `market_holidays`, "
                     "`orthodox_easter` and `radunitsa`"},
    {"name": "IAEA Zaporizhzhia status updates and the nuclear-plant event dates",
     "source": "International Atomic Energy Agency",
     "coverage": "2022-03-04 onward", "frequency": "event-driven, several a month",
     "publication_lag_days": 1.0, "revisions": "never", "licence": "free, public",
     "history_from": "2022-03", "pit_feasible": True,
     "assets": ("XNGUSD", "GER40", "XAUUSD"),
     "mechanism_families": ("tail_risk", "event_reaction"),
     "how_to_fetch": "iaea.org/newscenter/focus/ukraine update series, each numbered and dated; "
                     "the pack uses it as a TAIL-RISK event date list and says plainly that the "
                     "expected effect is a jump risk, not a drift"},
)


# --------------------------------------------------------------------------- actors
ACTORS: tuple[dict[str, Any], ...] = (
    # ------------------------------------------------------------------ Ukraine
    {"name": "The Board of the National Bank of Ukraine",
     "jurisdiction": "ua",
     "holds": "the key policy rate, the official hryvnia fixing, about US$40-45bn of reserves "
              "built almost entirely out of external grants and loans, and the wartime capital "
              "controls that decide who may buy foreign currency at all",
     "forced_to": ("decide at eight scheduled meetings a year on a published calendar and "
                   "release the decision at 14:00 Kyiv",
                   "publish an official rate every business day, effective the NEXT business day",
                   "sell reserves to defend the rate it has chosen, because under a fix or "
                   "managed flexibility the bank IS the market's counterparty",
                   "hold the capital controls in place while the current account is financed by "
                   "grants rather than by exports"),
     "when": "14:00 Europe/Kyiv on decision days, which is 11:00 UTC in winter and 12:00 UTC in "
             "summer -- the Kyiv clock moves and a fixed-UTC window is wrong for half the year",
     "information": ("the external-financing schedule before the market sees a disbursement",
                     "the daily interbank FX turnover and its own intervention book",
                     "the banking system's hryvnia liquidity in real time",
                     "the harvest and export forecast the government works to"),
     "constraints": ("reserves that are a function of EU and IMF disbursements, not of exports",
                     "a war that makes the exchange rate a confidence variable before it is a "
                     "trade variable",
                     "an inflation target explicitly subordinated to exchange-rate stability "
                     "from 2022-02-24 and restored only gradually after 2023-10-03",
                     "capital controls it cannot lift without testing the rate"),
     "instruments": ("EURPLN", "USDPLN", "EURUSD"),
     "counterparties": ("the domestic banks at the interbank fixing",
                        "the IMF under the Extended Fund Facility",
                        "the EU under the Ukraine Facility",
                        "the exporters and importers who must transact at the official rate"),
     "observables": ("the decision and the Governor's briefing",
                     "the daily official rate and its next-day effective date",
                     "the published daily intervention volume",
                     "the monthly reserves and the cash-rate spread"),
     "impact": "the hryvnia itself is not quoted here, so the executable effect is on the Polish "
               "crosses that carry Ukrainian risk sentiment, on the euro leg, and on the grain "
               "basis through the exporters' conversion economics",
     "persistence": "a regime lasts years: three eras since 2022 and only two switch dates",
     "falsifier": "NBU decision days carry no abnormal move on EURPLN or EURUSD beyond the "
                  "matched weekday-plus-hour control and beyond the nearest ECB and NBP days -- "
                  "which is the honest expectation for a currency the desk cannot trade",
     "notes": "THE CLOCK IS THE TRAP TWICE OVER: the announcement minute moves with EU DST and "
              "the published rate is effective TOMORROW"},
    {"name": "The Ministry of Agrarian Policy and Food and the grain export memorandum",
     "jurisdiction": "ua",
     "holds": "the export memorandum with the traders, the seasonal export balance, the sowing "
              "and harvest progress reporting, and the licensing levers over the crops it wants "
              "kept at home",
     "forced_to": ("publish a season-to-date export tonnage its own traders and the world's "
                   "balance-sheet analysts will check against customs data",
                   "agree a memorandum quota with the trade before each marketing year",
                   "keep domestic bread wheat supply politically acceptable while exporting"),
     "when": "weekly in-season tonnage posts in the Kyiv morning; the memorandum around the "
             "1 July marketing-year boundary",
     "information": ("the customs declarations before they are aggregated publicly",
                     "the port queue and the rail allocation",
                     "which terminals are damaged and which are loading"),
     "constraints": ("a corridor it does not control militarily",
                     "neighbours who close their land borders to the same cargo",
                     "a farm sector short of working capital, fuel and labour"),
     "instruments": ("WHEAT", "CORN", "SOYBEAN"),
     "counterparties": ("the international grain traders and the domestic agroholdings",
                        "the State Customs Service", "the European Commission's DG AGRI",
                        "the Turkish and Egyptian state buyers"),
     "observables": ("the weekly and monthly export tonnage by crop",
                     "the memorandum quota and its revisions",
                     "the harvest and sowing progress bulletins",
                     "the split between deep-sea, Danube and land routes"),
     "impact": "the export pace is the world balance sheet's Ukrainian line; a pace surprise "
               "against the USDA and IGC forecast is the mechanism that reaches WHEAT and CORN",
     "persistence": "a season; the marketing year is the natural unit and the 1 July boundary "
                    "is a real reset rather than a convention",
     "falsifier": "a month in which Ukrainian export tonnage surprised the USDA balance by more "
                  "than its historical interquartile range shows no abnormal move on WHEAT or "
                  "CORN in the following fortnight, controlling for the US and Russian crops",
     "notes": "THE MEASURABLE HALF OF THE CORRIDOR, and the reason this pack does not need the "
              "licensed FOB assessment to have a study"},
    {"name": "The Ukrainian Sea Ports Authority and the Odesa-Chornomorsk-Pivdennyi terminals",
     "jurisdiction": "ua",
     "holds": "the deep-sea berths, the grain terminals' throughput capacity and the pilotage "
              "the corridor's vessels need",
     "forced_to": ("publish throughput by port and by cargo group",
                   "keep loading while the terminals themselves are targets",
                   "route around damaged berths and silos within the same month"),
     "when": "monthly throughput statistics; port notices and damage reports the same day",
     "information": ("the vessel queue and which berths are actually working",
                     "the terminal-level damage before the ministry aggregates it",
                     "the draught and the pilotage constraint"),
     "constraints": ("the physical capacity of the remaining berths",
                     "strikes on terminal infrastructure",
                     "insurance: a vessel that cannot be covered does not sail"),
     "instruments": ("WHEAT", "CORN", "SOYBEAN"),
     "counterparties": ("the shipowners and their war-risk underwriters",
                        "the grain terminals", "the Ukrainian Navy running the corridor"),
     "observables": ("monthly throughput by port",
                     "the Danube versus deep-sea split",
                     "the vessel queue length", "the dated damage notices"),
     "impact": "a port constraint is a supply constraint with a two-to-six week lag into the "
               "export tonnage and therefore into the world balance sheet",
     "persistence": "weeks for a single strike, quarters for the capacity it removes",
     "falsifier": "dated strikes on port infrastructure are not followed by a measurable fall "
                  "in the next month's throughput, which would mean the damage was cosmetic",
     "notes": "the physical counterpart of UA-A, UA-B and UA-H at once; the page is overwritten "
              "in place, so the archive layer holds its point-in-time history"},
    {"name": "The Joint Coordination Centre in Istanbul (2022-07 to 2023-07)",
     "jurisdiction": "ua",
     "holds": "the inspection queue, the corridor's traffic schedule and the only jointly-agreed "
              "mechanism through which Ukrainian grain moved under Russian participation",
     "forced_to": ("inspect every inbound and outbound vessel with all four parties present",
                   "PUBLISH the vessel movements, cargoes, tonnages and destinations daily",
                   "stop entirely when any party suspended participation"),
     "when": "the Istanbul working day; the daily movement table in the afternoon",
     "information": ("the inspection backlog before the market sees the loading rate",
                     "which vessels were being slowed and by whom"),
     "constraints": ("unanimity: any party could halt the mechanism, and one did",
                     "a 120-day term that shortened to 60 and then ended",
                     "no authority over the ports themselves"),
     "instruments": ("WHEAT", "CORN", "SOYBEAN"),
     "counterparties": ("the UN, Türkiye, Ukraine and Russia",
                        "the shipowners and charterers queuing for inspection"),
     "observables": ("the daily vessel table with tonnage and destination",
                     "the inspection backlog", "the renewal announcements and their terms",
                     "the suspension of 2022-10-29 and the resumption of 2022-11-02"),
     "impact": "the single cleanest dated supply mechanism in this pack: an announced suspension "
               "is an immediate, unambiguous supply shock to WHEAT and CORN with a known minute",
     "persistence": "the suspension episode lasted four days; the termination is permanent",
     "falsifier": "the announcement windows on 2022-10-29, 2022-11-02 and 2023-07-17 carry no "
                  "abnormal WHEAT or CORN move beyond the matched weekday-plus-hour control -- "
                  "and if that is the finding, it is a finding, because these are the largest "
                  "and best-dated grain-supply announcements of the decade",
     "notes": "EIGHT EVENTS IS A SMALL SAMPLE AND THE PACK SAYS SO; the compensation is that "
              "each one is unambiguous, timestamped and unrepeatable"},
    {"name": "NPC Ukrenergo, the transmission system operator",
     "jurisdiction": "ua",
     "holds": "the Ukrainian transmission grid, the ENTSO-E interconnection and the emergency "
              "outage schedule every household and smelter is rationed by",
     "forced_to": ("publish the system's state and the outage schedules",
                   "import emergency power from the EU when generation is short",
                   "shed load rather than let the system collapse"),
     "when": "daily, and within hours of a strike",
     "information": ("the true generation deficit before the public schedule reflects it",
                     "which substations are repairable and which are not"),
     "constraints": ("a generation fleet under attack and an interconnector capacity cap",
                     "the season: a winter deficit is a different object from a summer one",
                     "the Zaporizhzhia plant's status, which it does not control"),
     "instruments": ("XNGUSD", "GER40", "EUSTX50"),
     "counterparties": ("the European TSOs under the ENTSO-E emergency synchronisation",
                        "the domestic industrial consumers, above all the steel and ore plants"),
     "observables": ("the daily outage schedule and consumption",
                     "the ENTSO-E cross-border flow, which is machine-readable in Europe",
                     "the dated strike reports and the IAEA's plant updates"),
     "impact": "a Ukrainian power deficit is a European power and gas demand event through the "
               "interconnectors, and an industrial-output event through the smelters it rations",
     "persistence": "an outage regime lasts a winter; the capacity destroyed lasts years",
     "falsifier": "dated mass-strike days show no abnormal move on European gas or power proxies "
                  "and no change in the ENTSO-E flow into Ukraine in the following week",
     "notes": "the ENTSO-E mirror is what gives this actor an executable leg at all; without it "
              "the whole mechanism would be a Ukrainian series with no tradable counterpart"},
    {"name": "The Gas TSO of Ukraine and Naftogaz",
     "jurisdiction": "ua",
     "holds": "the transit system that carried Russian gas to Europe until 2024-12-31, about "
              "30 bcm of underground storage, and the domestic supply obligation",
     "forced_to": ("publish daily transit nominations while the contract ran",
                   "refill storage before each heating season whatever the price",
                   "keep the domestic tariff politically survivable"),
     "when": "daily nominations; the storage cycle runs April to October",
     "information": ("the shipper's booked capacity before the market sees the flow",
                     "the true storage injection pace and the domestic production shortfall"),
     "constraints": ("a ship-or-pay contract that EXPIRED on 2024-12-31 and was not renewed",
                     "strikes on compressor stations and on production",
                     "a storage facility in a country at war, which is why the European traders "
                     "who used it withdrew"),
     "instruments": ("XNGUSD", "GER40", "EUSTX50"),
     "counterparties": ("the European shippers and the Slovak, Hungarian and Moldovan buyers",
                        "the EU traders storing gas in Ukrainian facilities"),
     "observables": ("the daily transit nomination and the entry/exit points",
                     "the storage fill against the AGSI European series",
                     "the contract expiry itself, which is the largest boundary in the series"),
     "impact": "the transit route's closure removed a European supply path on a known date; the "
               "effect belongs to TTF, and XNGUSD is a declared WEAK proxy for it",
     "persistence": "permanent from 2025-01-01",
     "falsifier": "the 2024-12-31 expiry window carries no abnormal European gas move once the "
                  "storage level, the weather and the LNG arrival schedule are controlled -- "
                  "which is plausible, because the expiry was known a year in advance",
     "notes": "A FULLY ANTICIPATED EVENT IS THE HARDEST KIND TO TRADE AND THE PACK SAYS SO: the "
              "hypothesis is about the WEEKS AROUND it and about the winters after, not the day"},
    {"name": "The Ukrainian grain traders and the agroholdings (Kernel, MHP, Astarta, Nibulon)",
     "jurisdiction": "ua",
     "holds": "the elevators, the river fleet, the export licences and the forward book the "
              "corridor's throughput is actually sold into",
     "forced_to": ("sell the crop within the marketing year or carry it at a cost",
                   "hedge in Chicago and Paris because there is no liquid domestic hedge",
                   "sign the ministry's export memorandum to keep licensing"),
     "when": "continuous, with the harvest and the 1 July boundary",
     "information": ("the real farmgate price and the farmer's willingness to sell",
                     "the terminal queue and the freight they are actually paying",
                     "the forward book before any of it is public"),
     "constraints": ("working capital in a war economy and a banking system under controls",
                     "the corridor's availability, which they do not control",
                     "the basis, which is the corridor's cost and is where their margin lives"),
     "instruments": ("WHEAT", "CORN", "SOYBEAN"),
     "counterparties": ("the international trade houses",
                        "the Egyptian, Turkish, Chinese and Spanish buyers",
                        "the CME and Euronext clearing members through their hedges"),
     "observables": ("the association export forecasts, published before the ministry revises",
                     "the reported CPT-port bid and the farmgate spread",
                     "the elevator stock reports"),
     "impact": "these are the agents that turn a corridor state into a Chicago hedge; their "
               "hedging is a real, dated flow into WHEAT and CORN",
     "persistence": "the forward book is a season long",
     "falsifier": "weeks in which the reported CPT-port bid moved sharply show no abnormal "
                  "WHEAT or CORN activity once the flat price move is removed",
     "notes": "EVERY NAME HERE IS A SINGLE NAME AND NONE IS AN INSTRUMENT (two-lane order, "
              "2026-09-06); they are actors because their hedging is the transmission"},
    {"name": "Ukrzaliznytsia and the 1520-to-1435 gauge break at the western border",
     "jurisdiction": "ua",
     "holds": "the rail wagons, the border transhipment capacity and the allocation of it "
              "between grain, ore, fuel and military cargo",
     "forced_to": ("tranship every westbound wagon at the gauge break",
                   "allocate scarce wagons between competing national priorities",
                   "keep running while the crossings are blockaded from the Polish side"),
     "when": "continuous; the blockades are dated episodes",
     "information": ("the wagon turnaround time and the queue at each crossing",
                     "which cargoes are being prioritised"),
     "constraints": ("A PHYSICAL GAUGE BREAK: 1520 mm meets 1435 mm and every wagon must be "
                     "transhipped or bogie-changed, which caps the land route far below the "
                     "sea route whatever the political will",
                     "Polish, Slovak and Hungarian hauliers' blockades",
                     "damaged track and traction power"),
     "instruments": ("WHEAT", "CORN", "EURPLN"),
     "counterparties": ("the Polish, Slovak, Hungarian and Romanian railways",
                        "the grain traders competing for wagons",
                        "the EU's solidarity-lane programme"),
     "observables": ("the dated blockade episodes and their duration",
                     "the crossing queue length reported by both sides",
                     "the monthly land-route tonnage in the ministry's split"),
     "impact": "the land route is the SUBSTITUTE for the sea route and its capacity is the "
               "reason a corridor closure is not fully offset; a blockade is a second, "
               "independent supply constraint with its own dates",
     "persistence": "a blockade lasts days to months; the gauge break is permanent",
     "falsifier": "blockade episodes show no measurable shift in the deep-sea versus land split "
                  "and no abnormal EURPLN or WHEAT behaviour in the following fortnight",
     "notes": "THE GAUGE BREAK IS THE UNDERRATED FACT of the whole solidarity-lane story: it is "
              "physics, not policy, and no amount of EU goodwill removes it"},
    {"name": "The Ministry of Finance of Ukraine and the external financing schedule",
     "jurisdiction": "ua",
     "holds": "the domestic bond programme, the external grant and loan schedule, and the "
              "eurobonds restructured in 2024 together with the GDP warrants",
     "forced_to": ("auction domestic bonds every Tuesday to a substantially state-owned bid",
                   "publish the external financing received, because the donors require it",
                   "fund a deficit that no tax base could cover"),
     "when": "weekly auctions; monthly financing reports; the IMF review calendar",
     "information": ("the disbursement timetable before the market sees the money",
                     "the cash position and the monetisation pressure on the NBU"),
     "constraints": ("a deficit financed by grants and concessional loans, not by markets",
                     "IMF programme conditionality with dated reviews",
                     "a domestic investor base that is mostly the state's own banks"),
     "instruments": ("EURPLN", "EURUSD", "EURTRY"),
     "counterparties": ("the IMF, the EU, the G7 bilaterals",
                        "the domestic banks at the OVDP auction",
                        "the restructured eurobond holders"),
     "observables": ("the weekly auction cut-off and volume",
                     "the monthly external financing receipts",
                     "the IMF review dates and their outcomes"),
     "impact": "the financing schedule is what makes the reserves possible and therefore what "
               "makes the managed rate possible; a disbursement miss is a currency event before "
               "it is a fiscal one",
     "persistence": "a programme review cycle is quarterly and the eras last years",
     "falsifier": "IMF review and large-disbursement dates carry no abnormal move on the Polish "
                  "crosses or on Ukrainian risk proxies beyond the global risk tape",
     "notes": "the one Ukrainian actor whose clock is EXTERNAL and published in advance, which "
              "makes it the most tractable event source in the fiscal half of this pack"},
    {"name": "The Kryvyi Rih iron-ore and steel complex",
     "jurisdiction": "ua",
     "holds": "the ore reserves, the mines and the concentrators that fed a fifth of Europe's "
              "imported pellet feed, plus the steel mills that consume the country's power",
     "forced_to": ("ship through the ports or not at all -- ore is too low-value for rail to "
                   "Europe to clear at scale",
                   "curtail when the grid cannot supply the arc furnaces",
                   "sell into a seaborne market priced far away from Ukraine"),
     "when": "continuous, with the grid and the corridor as the two binding constraints",
     "information": ("its own production and the mine-gate stock",
                     "the real power availability before the outage schedule says so"),
     "constraints": ("THE PORT CONSTRAINT, which is the whole point: ore CAN be mined and CANNOT "
                     "be moved when the corridor is shut",
                     "a power system that rations it first",
                     "European steel demand, which is itself a gas-cost story"),
     "instruments": ("EUSTX50", "GER40", "XTIUSD"),
     "counterparties": ("the European steel mills and their pellet buyers",
                        "the shipping market out of Pivdennyi",
                        "the domestic power system"),
     "observables": ("the export tonnage in the customs data",
                     "the port throughput for ore at Pivdennyi",
                     "the curtailment notices and the outage schedule"),
     "impact": "a European steel-input observable: when Ukrainian pellet feed cannot sail, "
               "European mills pay a different price for the same input",
     "persistence": "quarters; a corridor reopening restores it within a season",
     "falsifier": "months in which Ukrainian ore exports collapsed show no abnormal European "
                  "steel-sector behaviour once iron-ore benchmark prices and gas costs are "
                  "controlled -- the honest expectation, and the pack measures it",
     "notes": "the one Ukrainian mechanism whose executable leg is an EQUITY INDEX rather than a "
              "soft, and the index is the leg precisely because no single name may be hunted"},
    # ------------------------------------------------------------------ Belarus
    {"name": "The Board of the National Bank of the Republic of Belarus",
     "jurisdiction": "by",
     "holds": "the refinancing rate, the official BYN rate derived from the BCSE session, and "
              "the PUBLISHED currency basket the rate is managed against",
     "forced_to": ("publish the basket's composition and its weights",
                   "publish an official rate every business day, effective the next day",
                   "manage the rate against a basket dominated by the rouble, which means "
                   "importing Russian monetary conditions whether or not it wants to",
                   "operate under a broad-money framework rather than an inflation target"),
     "when": "the BCSE session closes about 13:00 Minsk (10:00 UTC) and the rate follows; Minsk "
             "is FIXED UTC+3 all year, unlike Kyiv",
     "information": ("the session's order flow before the rate is published",
                     "the exporters' conversion schedule",
                     "the true inflation pressure under an administered price regime"),
     "constraints": ("A BASKET WHOSE LARGEST WEIGHT IS THE ROUBLE, which ties Belarusian "
                     "monetary conditions to Russian ones by published arithmetic",
                     "reserves that are small relative to the import bill",
                     "an administered price regime that makes the CPI a policy output"),
     "instruments": ("USDRUB", "EURRUB", "EURUSD"),
     "counterparties": ("the banks at the BCSE session",
                        "the exporters converting hard currency",
                        "the Bank of Russia, informally, through the basket"),
     "observables": ("the daily official rate and the basket value",
                     "the published weights and any change to them",
                     "the refinancing rate decisions", "the cash-rate spread at the banks"),
     "impact": "the arithmetic beta of BYN to RUB is DECLARED rather than estimated, so the "
               "testable object is the RESIDUAL -- what the basket does not explain -- and the "
               "executable leg is the rouble the basket itself names",
     "persistence": "a basket composition lasts years: four eras since 2009",
     "falsifier": "the residual of the BYN basket move over its arithmetic basket-implied move "
                  "carries no information about the following days' USDRUB path, in which case "
                  "the NBRB is a pure follower and the pack records that as the finding",
     "notes": "THE RARE CASE WHERE A PEG'S COEFFICIENTS ARE PUBLISHED. Most managed-currency "
              "studies begin by estimating what this central bank simply announces"},
    {"name": "Belaruskali and the Belarusian Potash Company (BPC)",
     "jurisdiction": "by",
     "holds": "roughly a fifth of world potash capacity at Soligorsk and the export company "
              "that sold it, historically through Klaipeda",
     "forced_to": ("keep the mines running -- a potash mine cannot be idled cheaply",
                   "find a route to a port after the Lithuanian transit ended on 2022-02-01",
                   "sell into annual contract settlements with China and India that set the "
                   "world reference price"),
     "when": "continuous production; the contract settlements are annual and dated",
     "information": ("its own shipment volumes and the real discount it is granting",
                     "the rail capacity it has actually secured to Russian ports"),
     "constraints": ("EU measures from June 2021 and US measures on Belaruskali (2021-08-09) "
                     "and on BPC (2021-12-08, wind-down to 2022-04-01)",
                     "THE LITHUANIAN TRANSIT TERMINATION FROM 2022-02-01, which removed the "
                     "route rather than the production",
                     "Russian port and rail capacity it must now compete for",
                     "a mine that fills with brine if it stops"),
     "instruments": ("CORN", "WHEAT", "SOYBEAN"),
     "counterparties": ("the Chinese and Indian contract buyers",
                        "Russian Railways and the Baltic and Far Eastern port operators",
                        "the Brazilian and Southeast Asian spot market"),
     "observables": ("Belstat and Comtrade mirror export volumes",
                     "the annual China and India contract settlement levels, reported publicly",
                     "the Lithuanian and Russian rail statistics",
                     "the price reporting agencies' assessments, which are LICENSED and unread"),
     "impact": "an INPUT-COST mechanism into the northern-hemisphere planting decision: a farmer "
               "who cannot afford potash applies less of it or switches crop, which is a supply "
               "effect on the NEXT crop, not on this one",
     "persistence": "the route disruption is structural; the affordability shock lasted about "
                    "two planting seasons",
     "falsifier": "seasons with a large move in the potash-to-corn affordability ratio show no "
                  "change in USDA's applied-rate or acreage estimates, which would mean the "
                  "nutrient cost does not reach the planting decision at all",
     "notes": "A SINGLE NAME AND AN ACTOR ONLY. The claim is explicitly about the acreage "
              "economics of the crops, never about Minsk moving Chicago"},
    {"name": "Belarusian Railway (BelZhD) and the re-routed potash corridor",
     "jurisdiction": "by",
     "holds": "the wagons and the route allocation that decide whether Belarusian potash and "
              "oil products reach a port at all",
     "forced_to": ("re-route to Russian Baltic and Far Eastern ports after the Lithuanian "
                   "termination of 2022-02-01",
                   "compete for Russian port slots with Russian exporters of the same goods",
                   "carry the same tonnage over a much longer haul"),
     "when": "continuous; the re-routing was a step change in early 2022",
     "information": ("the wagon availability and the real turnaround time",
                     "the slot allocation it has been granted at Russian terminals"),
     "constraints": ("a landlocked country whose only lawful sea access is through a country "
                     "that closed the route",
                     "Russian port capacity that was built for Russian cargo",
                     "a haul length that changes the economics of every tonne"),
     "instruments": ("CORN", "WHEAT", "EURPLN"),
     "counterparties": ("Russian Railways and the Baltic port operators",
                        "Lithuanian Railways, historically",
                        "the Chinese rail corridor for containerised cargo"),
     "observables": ("Lithuanian and Russian rail statistics",
                     "Comtrade mirror volumes by partner and route",
                     "the port-call ground at the Russian Baltic terminals"),
     "impact": "the route determines HOW MUCH potash actually reaches the market, which is the "
               "supply half of the fertiliser affordability mechanism",
     "persistence": "structural since 2022",
     "falsifier": "the re-routing shows no measurable effect on delivered potash volumes in the "
                  "Comtrade mirrors once Belarusian production is controlled -- which would "
                  "mean the route was never the constraint",
     "notes": "THE PER-JURISDICTION PHYSICAL GAP THIS PACK DECLARES: Belarus has no port "
              "authority to read, so this actor's physical half is an INFERENCE from third "
              "countries' statistics and is labelled as one"},
    {"name": "The Mozyr and Naftan refineries (Belneftekhim) on the Druzhba",
     "jurisdiction": "by",
     "holds": "about 24 mt a year of nameplate refining capacity fed by Russian crude down the "
              "Druzhba, and the oil-product export stream that was a major hard-currency earner",
     "forced_to": ("take crude at a negotiated premium to the Russian domestic netback",
                   "keep the units running or pay the restart cost",
                   "find buyers for product after the European market closed"),
     "when": "continuous; the supply disputes are dated episodes",
     "information": ("the real premium being paid and the crude actually delivered",
                     "the product placement it has secured"),
     "constraints": ("THE 2020 PRICING DISPUTE, which halted or curtailed supply for weeks in "
                     "the first quarter of that year -- a clean, dated refinery-margin event",
                     "EU measures on Naftan and on Belarusian oil products",
                     "a single pipeline supplier with pricing power"),
     "instruments": ("XBRUSD", "XTIUSD", "USDRUB"),
     "counterparties": ("the Russian producers and Transneft",
                        "the former European product buyers",
                        "the Russian domestic market as the substitute outlet"),
     "observables": ("the dated supply-halt and resumption reports",
                     "Belstat's oil-product export line, where it is still published",
                     "the Druzhba flow reporting from the downstream countries"),
     "impact": "a dated refinery-margin and crude-demand event on a known pipeline; the products "
               "are not quoted, so the crude legs carry it and the pack says which",
     "persistence": "the 2020 dispute lasted a quarter; the sanctions effect is structural",
     "falsifier": "the dated 2020 supply-halt days show no abnormal crude behaviour beyond the "
                  "global tape, which is the likely finding given the volumes involved -- and "
                  "the pack keeps the mechanism because the DATE is unambiguous and cheap",
     "notes": "the honest size statement: this is a small mechanism on a large market, carried "
              "because it is dated and because it interacts with the `ru` pack's Urals leg"},
    {"name": "The Belarusian Universal Commodity Exchange (BUCE) and the timber and dairy trade",
     "jurisdiction": "by",
     "holds": "the public auction mechanism through which a large part of Belarusian timber, "
              "dairy, metals and industrial goods is legally exported",
     "forced_to": ("publish auction results, because the exchange's legal purpose is price "
                   "transparency for state-controlled exports",
                   "clear volumes the state has decided must be exported"),
     "when": "auction sessions through the Minsk working day",
     "information": ("the bid depth and the participants before the result is posted",
                     "which product groups the state has decided must clear this month"),
     "constraints": ("a buyer base narrowed to Russia, China and the parallel-import corridor",
                     "sanctions on several product groups",
                     "administered prices upstream of the auction"),
     "instruments": ("EURPLN", "EURUSD", "EURHUF"),
     "counterparties": ("Russian and Chinese buyers",
                        "the re-export intermediaries in Central Asia and the Caucasus",
                        "the remaining European buyers of unsanctioned groups"),
     "observables": ("the published auction results by product group",
                     "Belstat's trade tables", "the mirror import data of the buyer countries"),
     "impact": "the only unlicensed Belarusian physical price series the desk can read; it "
               "conditions the parallel-import and re-export mechanism rather than pricing it",
     "persistence": "structural",
     "falsifier": "BUCE auction price moves carry no relationship to the corresponding European "
                  "product prices once the euro cross is controlled, which would mean the "
                  "Belarusian market has fully decoupled and the series conditions nothing",
     "notes": "a rare thing in this pack: a PUBLISHED PRICE from a jurisdiction whose statistics "
              "are otherwise being withdrawn, and it costs nothing to read"},
    {"name": "The Council of Ministers and the administered-price regime",
     "jurisdiction": "by",
     "holds": "the general price-regulation powers used from October 2022 over most of the "
              "consumer basket, plus the export-licensing and currency-surrender levers",
     "forced_to": ("keep the measured consumer price index politically acceptable",
                   "grant exemptions when a regulated price makes supply disappear",
                   "publish the resolutions in the legal gazette"),
     "when": "resolutions are dated and published on pravo.by; the regime has run since 2022-10",
     "information": ("the true cost pressure the regulated prices are suppressing",
                     "which shortages are appearing before they are reported"),
     "constraints": ("a regulated price cannot clear a market and produces shortages instead",
                     "an import bill denominated in currencies it does not print",
                     "the rouble's behaviour, which enters through the basket"),
     "instruments": ("USDRUB", "EURRUB", "EURUSD"),
     "counterparties": ("the domestic retailers and producers",
                        "the NBRB, whose CPI series is the regime's output",
                        "the Russian suppliers of the regulated goods"),
     "observables": ("the dated resolutions in pravo.by",
                     "the Belstat CPI, which is the regime's output rather than a measurement",
                     "the reported shortages in the independent press"),
     "impact": "BELARUSIAN CPI IS A POLICY VARIABLE. A release-surprise study on it measures the "
               "regulation, not the economy, and this actor exists so no miner makes that error",
     "persistence": "the regime has run since 2022 and is periodically re-tightened",
     "falsifier": "Belarusian CPI prints behave like an ordinary market-clearing index -- that "
                  "is, they respond to the exchange rate with the usual pass-through and lag -- "
                  "in which case the administered regime is not binding and this actor is wrong",
     "notes": "AN ACTOR WHOSE ONLY JOB IS TO BLOCK A BAD CELL. Naming the reason a release "
              "cannot be traded is worth as much as naming one that can"},
    # ------------------------------------------------------------------ joint
    {"name": "The war-risk underwriters and the Black Sea hull-and-cargo facility",
     "jurisdiction": "joint",
     "holds": "the war-risk cover without which no owner sends a vessel into the Black Sea, and "
              "the premium rate that is the corridor's real cost",
     "forced_to": ("reprice within days of any incident",
                   "quote a premium per voyage rather than per year in a war zone",
                   "accept or refuse the state-backed facility's reinsurance terms"),
     "when": "continuous; repriced within days of a strike on a port or a vessel",
     "information": ("the claims experience and the incident reports before the press has them",
                     "which owners are actually willing to sail"),
     "constraints": ("a risk with no long history and therefore no credible base rate",
                     "a facility whose capacity is finite",
                     "the London market's own appetite, which moves with unrelated events"),
     "instruments": ("WHEAT", "CORN", "XBRUSD"),
     "counterparties": ("the shipowners and charterers",
                        "the Ukrainian state-backed insurance facility and its reinsurers",
                        "the grain traders who ultimately pay the premium in the basis"),
     "observables": ("the press-reported premium levels and their dated moves",
                     "the number of vessels sailing",
                     "the fixture reports and the freight quotes"),
     "impact": "THE PREMIUM IS THE CORRIDOR'S PRICE. When cover is dear the basis widens without "
               "the futures moving, which is why a corridor study run on flat price alone "
               "measures the wrong variable",
     "persistence": "a premium regime lasts weeks to months; incidents reset it in days",
     "falsifier": "dated premium moves are not followed by a measurable change in sailings or "
                  "in the export pace within a fortnight, which would mean the premium is a "
                  "reported number and not a constraint",
     "notes": "PRESS_REPORTED BY CONSTRUCTION: the assessments themselves are licensed ground "
              "and are registered, never fetched, so nothing compiled here is promoted without "
              "a second independent dated source"},
    {"name": "The European Commission's DG AGRI and the frontline member states",
     "jurisdiction": "joint",
     "holds": "the tariff suspension for Ukrainian agricultural goods, the solidarity-lane "
              "programme, and the power to replace a unilateral national ban with an EU act",
     "forced_to": ("choose between the single market's rules and five member states acting "
                   "alone, which is a political constraint with a publication date",
                   "publish the acts in the Official Journal",
                   "renew or let lapse on stated deadlines"),
     "when": "the 2023 sequence: 2023-04-15 (national bans), 2023-05-02 (the EU act), "
             "2023-09-15 (lapse and unilateral extension)",
     "information": ("the licence and import data before the market aggregates it",
                     "which capitals are about to move"),
     "constraints": ("farmer politics in Poland, Hungary, Slovakia, Romania and Bulgaria",
                     "a single market whose rules a national ban breaks",
                     "a Ukrainian export need it has promised to support"),
     "instruments": ("WHEAT", "CORN", "EURPLN"),
     "counterparties": ("the five frontline member states",
                        "Ukraine, which filed at the WTO",
                        "the EU traders and millers who buy the grain"),
     "observables": ("the Official Journal acts and their dates",
                     "the weekly DG AGRI licence and import data",
                     "the national announcements, which lead the EU act by about two weeks"),
     "impact": "an intra-EU BASIS event rather than a flat-price one: the same tonnage is "
               "redirected, so the CEE cash market and the euro crosses move while Chicago "
               "barely does -- which is a real and testable directional prediction",
     "persistence": "the 2023 measures ran five months; the national extensions outlived them",
     "falsifier": "the ban announcement windows carry no abnormal EURPLN, EURHUF or MATIF-proxy "
                  "behaviour and no measurable redirection in the DG AGRI licence data",
     "notes": "THE DIRECT SEAM WITH THE `pl` AND `cee_balkans` PACKS, named in INTERACTIONS so "
              "the two are tested against each other rather than separately"},
    {"name": "Türkiye as the corridor's host and the marginal buyer (TMO and the millers)",
     "jurisdiction": "joint",
     "holds": "the Straits, the Istanbul inspection venue, the largest milling industry in the "
              "region and a state grain board that tenders when it chooses",
     "forced_to": ("regulate Straits transit under the Montreux Convention",
                   "buy wheat for a milling and re-export industry larger than its own crop",
                   "balance both belligerents, which is what made the JCC possible at all"),
     "when": "continuous; TMO tenders are announced and dated",
     "information": ("the Straits traffic and the vessel queue before anyone else",
                     "its own tender intentions"),
     "constraints": ("a domestic wheat crop that varies with Anatolian rainfall",
                     "an inflation and currency regime that makes import timing political",
                     "the diplomatic balance the corridor depended on"),
     "instruments": ("WHEAT", "CORN", "EURTRY", "USDTRY"),
     "counterparties": ("the Ukrainian and Russian exporters",
                        "the Turkish flour millers and the re-export market",
                        "the UN and the JCC"),
     "observables": ("the TMO tender announcements and awards",
                     "the Straits transit notices", "Turkish wheat and flour trade statistics"),
     "impact": "the marginal buyer of Black Sea wheat and the venue of its administration at "
               "once; a TMO tender is a dated demand event and the lira legs carry the "
               "import-cost side of it",
     "persistence": "tender effects last days; the structural milling demand is permanent",
     "falsifier": "TMO tender dates carry no abnormal WHEAT move beyond the matched control and "
                  "no measurable effect on the Ukrainian export pace in the following month",
     "notes": "the seam with the `tr` pack: Türkiye's own reaction function is THEIRS, and what "
              "belongs here is only its role as this corridor's host and marginal buyer"},
)


# --------------------------------------------------------------------------- domains
DOMAINS: tuple[dict[str, Any], ...] = (
    {"id": "UA-A", "title": "The Black Sea Grain Initiative as a published vessel-level experiment",
     "jurisdiction": "ua", "family": "supply_shock_event", "horizon": "intraday",
     "objects": ("the daily JCC vessel table: vessel, cargo, tonnage, destination, inspection "
                 "date",
                 "the eight dated Initiative events from signature to termination",
                 "the 2022-10-29 suspension and the 2022-11-02 resumption",
                 "the inspection backlog as a throughput constraint"),
     "conditions": ("the Initiative's phase: running, suspended, or in a renewal window",
                    "the inspection backlog quartile",
                    "the destination mix (low-income buyers versus commercial)"),
     "instruments": ("WHEAT", "CORN", "SOYBEAN"),
     "controls": ("the matched weekday-plus-hour window on the same instruments",
                  "the SAME windows on the days the Russian wheat export pace was the story, "
                  "which separates 'Black Sea supply' from 'Ukrainian supply'",
                  "a randomised-date null drawn from the Initiative's own operating days"),
     "notes": "EIGHT EVENTS. The sample is small by construction and is reported rather than "
              "padded; the compensation is that each one is unambiguous and timestamped"},
    {"id": "UA-B", "title": "The Ukrainian maritime corridor and the monthly export tonnage",
     "jurisdiction": "ua", "family": "export_pace", "horizon": "multi_day",
     "objects": ("the corridor's announcement on 2023-08-10 and its first sailings",
                 "the monthly and weekly export tonnage published by the ministry",
                 "the deep-sea versus Danube versus land split",
                 "the port throughput by terminal"),
     "conditions": ("the corridor regime in force (see `corridor_regime`)",
                    "the export pace against the USDA and IGC balance-sheet expectation",
                    "the season: harvest pressure versus carry-out"),
     "instruments": ("WHEAT", "CORN", "SOYBEAN"),
     "controls": ("the BSGI months on the same instruments -- the country as its own control "
                  "under a different corridor regime",
                  "the Romanian and Bulgarian export pace over the same weeks, which is the "
                  "`cee_balkans` pack's ground and separates 'the basin' from 'Ukraine'",
                  "months in which the pace matched the forecast, as the null"),
     "notes": "NEVER POOLED WITH UA-A: a negotiated corridor and a defended one are different "
              "physical regimes that happen to move the same cargo"},
    {"id": "UA-C", "title": "The Danube ports, the solidarity lanes and the neighbours' bans",
     "jurisdiction": "ua", "family": "trade_policy_basis", "horizon": "multi_day",
     "objects": ("the Izmail and Reni throughput and the strikes on them",
                 "the five dated 2023 ban and restriction events",
                 "the Polish haulier and farmer blockades of 2023-11 and 2024-02",
                 "the DG AGRI weekly import-licence data by member state"),
     "conditions": ("whether an EU act or a national ban was in force",
                    "the blockade state at the rail and road crossings",
                    "the Danube's navigable draught in the same weeks"),
     "instruments": ("WHEAT", "CORN", "EURPLN"),
     "controls": ("the same windows in 2022, before any ban existed",
                  "the Romanian Constanta export pace, the unbanned neighbour's route",
                  "the matched weekday control on EURPLN, which is a zloty pair first and a "
                  "grain-politics pair second"),
     "notes": "THE PREDICTION IS A BASIS EFFECT, NOT A FLAT-PRICE ONE: the same tonnage is "
               "redirected, so CEE cash and the euro crosses move while Chicago barely does"},
    {"id": "UA-D", "title": "The hryvnia's three wartime eras and the capital-control spread",
     "jurisdiction": "ua", "family": "fx_regime", "horizon": "multi_day",
     "objects": ("the 2022-02-24 fix, the 2022-07-21 devaluation and the 2023-10-03 move to "
                 "managed flexibility",
                 "the daily official rate and its next-day effective date",
                 "the published NBU intervention volume",
                 "the cash and card rate spread to the official fix"),
     "conditions": ("the era from `uah_regime`",
                    "the cash-spread quartile as the control-stress state",
                    "whether a large external disbursement landed in the same week"),
     "instruments": ("EURPLN", "USDPLN", "EURUSD"),
     "controls": ("the same state built on a BLOCK-PERMUTED official-rate series, which is the "
                  "null for a state variable",
                  "the pre-2022 floating era, when the state could vary freely",
                  "the Polish zloty's own NBP days, separating 'Poland' from 'Ukraine'"),
     "notes": "A FIXED NUMBER IS NOT A PRICE: any volatility or beta computed on the official "
              "series inside a fixed era measures the fix, which is why the era function "
              "returns the rate so a study can refuse the window"},
    {"id": "UA-E", "title": "The grid war: Ukrenergo, the ZNPP and the ENTSO-E interconnection",
     "jurisdiction": "ua", "family": "physical_disruption", "horizon": "multi_day",
     "objects": ("the dated mass-strike days on generation and transmission from 2022-10",
                 "the emergency outage schedules and measured consumption",
                 "the ENTSO-E cross-border flow into and out of Ukraine",
                 "the IAEA's numbered Zaporizhzhia updates"),
     "conditions": ("the season (a winter deficit is a different object from a summer one)",
                    "the size of the outage in hours per day",
                    "whether emergency import was drawn from the EU in the same week"),
     "instruments": ("XNGUSD", "GER40", "EUSTX50"),
     "controls": ("the matched weekday-plus-hour control on the European legs",
                  "the same windows on European cold snaps with no Ukrainian event, which is "
                  "the weather null",
                  "the days with strikes on NON-energy targets, separating 'a strike happened' "
                  "from 'the grid was hit'"),
     "notes": "THE EXECUTABLE LEG IS EUROPEAN, and it exists only because ENTSO-E and AGSI "
              "publish machine-readable mirrors of series the desk cannot fetch in Ukraine"},
    {"id": "UA-F", "title": "Gas transit to 2024-12-31, the Druzhba and the European gas map",
     "jurisdiction": "ua", "family": "physical_flow", "horizon": "multi_day",
     "objects": ("the daily GTSOU transit nominations from 2020-01-01 to 2024-12-31",
                 "the contract expiry and the first days of 2025 with no transit",
                 "the Ukrainian storage cycle against the European AGSI series",
                 "the Druzhba flow reporting from the downstream countries"),
     "conditions": ("before or after the 2024-12-31 expiry -- never pooled",
                    "the European storage fill percentile in the same week",
                    "the heating season versus the injection season"),
     "instruments": ("XNGUSD", "GER40", "EUSTX50"),
     "controls": ("the same calendar weeks in the years the contract ran, as the base rate",
                  "European weather-adjusted demand as the competing explanation",
                  "the LNG arrival schedule, which is the substitute supply"),
     "notes": "A FULLY ANTICIPATED EVENT IS THE HARDEST KIND TO TRADE and the pack says so: "
              "XNGUSD is a DECLARED WEAK proxy for TTF and the hypothesis is about the weeks "
              "around the expiry and the winters after it, not about the day itself"},
    {"id": "UA-G", "title": "Sunflower oil and the vegetable-oil substitution chain",
     "jurisdiction": "ua", "family": "substitution", "horizon": "multi_day",
     "objects": ("the sunflower crush and the oil export tonnage",
                 "the 2022 collapse and recovery of sunoil shipments",
                 "the USDA oilseeds balance for Ukraine",
                 "the crush margin implied by the reported seed and oil prices"),
     "conditions": ("the corridor regime, because oil ships in the same vessels as grain",
                    "the palm-oil policy state in Indonesia and Malaysia in the same months",
                    "the crush-margin quartile"),
     "instruments": ("SOYBEAN", "CORN", "COTTON"),
     "controls": ("the Russian sunoil export pace over the same months, which separates "
                  "'sunflower' from 'Ukraine'",
                  "Indonesian palm export-levy changes as the competing substitution shock",
                  "the matched-season control in years with no corridor disruption"),
     "notes": "NO SUNFLOWER CONTRACT IS QUOTED HERE, so the claim is explicitly a SUBSTITUTION "
              "claim into the soy complex and the acreage that competes with it"},
    {"id": "UA-H", "title": "Iron ore, steel and the port constraint on a landlocked cargo",
     "jurisdiction": "ua", "family": "logistics_constraint", "horizon": "multi_day",
     "objects": ("the ore and pellet export tonnage in the customs data",
                 "Pivdennyi throughput for ore",
                 "the power curtailment notices that ration the smelters",
                 "the European mills' import substitution"),
     "conditions": ("the corridor regime, which decides whether ore can sail at all",
                    "the grid state in the same weeks",
                    "the European steel cycle and the gas cost inside it"),
     "instruments": ("EUSTX50", "GER40", "XTIUSD"),
     "controls": ("the seaborne iron-ore benchmark as the price explanation",
                  "the same windows for Brazilian and Australian supply events",
                  "European gas cost as the competing steel-margin driver"),
     "notes": "the one Ukrainian mechanism whose executable leg is an EQUITY INDEX; the index is "
              "the leg precisely because the two-lane order forbids hunting the mills themselves"},
    {"id": "BY-A", "title": "Belarusian potash, the route closure and fertiliser affordability",
     "jurisdiction": "by", "family": "input_cost", "horizon": "quarterly",
     "objects": ("the dated measures of 2021-06, 2021-08-09 and 2021-12-08 and the 2022-04-01 "
                 "wind-down",
                 "the Lithuanian transit termination effective 2022-02-01",
                 "the Belstat and Comtrade-mirror export volumes",
                 "the annual China and India contract settlements as the world reference"),
     "conditions": ("the potash-to-corn affordability ratio bucket",
                    "whether a contract settlement fell in the same quarter",
                    "the Russian and Canadian supply response in the same season"),
     "instruments": ("CORN", "WHEAT", "SOYBEAN"),
     "controls": ("PHOSPHATE affordability over the same seasons -- the other nutrient, which "
                  "separates 'fertiliser' from 'potash' and is the `ma` pack's ground",
                  "seasons in which the ratio did not move, as the null",
                  "USDA applied-rate and acreage estimates as the independent read"),
     "notes": "INPUT DIRECTION, DECLARED: the claim is about the NEXT crop's acreage economics, "
              "and the price leg itself is LICENSED and unreadable, so tonnage carries it"},
    {"id": "BY-B", "title": "The Lithuanian transit termination and the rail re-routing",
     "jurisdiction": "by", "family": "logistics_constraint", "horizon": "quarterly",
     "objects": ("the 2022-02-01 effective date of the Lithuanian termination",
                 "Lithuanian and Russian rail statistics before and after",
                 "the Russian Baltic and Far Eastern port slot competition",
                 "the Comtrade mirrors by partner and route"),
     "conditions": ("before or after 2022-02-01 -- never pooled",
                    "the Russian port capacity state in the same quarter",
                    "whether the Chinese rail corridor was carrying containerised volume"),
     "instruments": ("CORN", "WHEAT", "EURPLN"),
     "controls": ("Russian potash exports over the same quarters, which shared the new route "
                  "and separates 'the route' from 'Belarus'",
                  "the Klaipeda port's other cargo, which continued",
                  "the pre-2021 quarters as the undisrupted base rate"),
     "notes": "THE PACK'S DECLARED PHYSICAL GAP FOR BELARUS: there is no Belarusian port "
              "authority, so this domain's physical half is an INFERENCE from third countries' "
              "statistics and every cell compiled here carries that label"},
    {"id": "BY-C", "title": "Mozyr, Naftan and the Druzhba crude premium",
     "jurisdiction": "by", "family": "refinery_margin", "horizon": "multi_day",
     "objects": ("the 2020 pricing dispute and its dated supply halts and resumptions",
                 "the Druzhba flow reporting from the downstream countries",
                 "Belstat's oil-product export line where it is still published",
                 "the EU measures on Naftan and on Belarusian products"),
     "conditions": ("whether a supply halt was in force",
                    "the Urals-to-Brent differential in the same weeks, which is the `ru` "
                    "pack's ground",
                    "the European product market's openness to Belarusian barrels"),
     "instruments": ("XBRUSD", "XTIUSD", "USDRUB"),
     "controls": ("the same windows for Russian refinery outages, separating 'a refinery "
                  "stopped' from 'Belarus stopped'",
                  "the matched weekday control on the crude legs",
                  "quarters with no dispute, as the base rate"),
     "notes": "A SMALL MECHANISM ON A LARGE MARKET, carried because it is precisely dated and "
              "cheap to test, and because it interacts with the `ru` pack's Urals leg"},
    {"id": "BY-D", "title": "The published currency basket and the arithmetic rouble beta",
     "jurisdiction": "by", "family": "fx_basket", "horizon": "multi_day",
     "objects": ("the four declared basket eras and their published weights",
                 "the daily official BYN rate and the published basket value",
                 "the RESIDUAL of the realised basket move over its arithmetic implied move",
                 "the refinancing-rate decisions"),
     "conditions": ("the basket era from `byn_basket_weights`",
                    "the residual's quartile -- the policy that the arithmetic does not explain",
                    "whether the rouble itself was in a stress week"),
     "instruments": ("USDRUB", "EURRUB", "EURUSD"),
     "controls": ("the SAME residual computed on a block-permuted BYN series, which is the null "
                  "for a constructed state variable",
                  "the pre-2022 basket era, when the euro rather than the yuan was the third leg",
                  "the Kazakh tenge's own managed regime over the same weeks, which is the `kz` "
                  "pack's ground and separates 'CIS' from 'Belarus'"),
     "notes": "THE RARE CASE WHERE THE COEFFICIENTS ARE PUBLISHED. Almost every managed-currency "
              "study begins by estimating what this central bank simply announces"},
    {"id": "BY-E", "title": "Timber, dairy and the parallel-import corridor",
     "jurisdiction": "by", "family": "trade_redirection", "horizon": "quarterly",
     "objects": ("the BUCE published auction results by product group",
                 "Belstat's trade tables and the partner-country mirrors",
                 "the re-export intermediaries in Central Asia and the Caucasus",
                 "the dated sanctions packages that closed each product group"),
     "conditions": ("whether the product group was inside a sanctions package that quarter",
                    "the share of trade reported by Russia and China versus the EU",
                    "the mirror gap between declared exports and declared imports"),
     "instruments": ("EURPLN", "EURUSD", "EURHUF"),
     "controls": ("the same product groups' Russian trade over the same quarters",
                  "the pre-2021 quarters as the undisrupted base rate",
                  "product groups that were never sanctioned, as the within-country null"),
     "notes": "the mirror GAP is the object: what a sanctioned exporter stops declaring, its "
              "buyers keep declaring, and the difference dates the corridor"},
    {"id": "XX-A", "title": "The Black Sea war-risk premium as a freight-cost state",
     "jurisdiction": "joint", "family": "freight_cost", "horizon": "multi_day",
     "objects": ("the press-reported war-risk premium levels and their dated moves",
                 "the number of vessels sailing in each corridor regime",
                 "the Danube barge freight in the same weeks",
                 "the dated incidents that repriced the cover"),
     "conditions": ("the corridor regime in force",
                    "the premium's reported quartile",
                    "whether an incident occurred in the preceding fortnight"),
     "instruments": ("WHEAT", "CORN", "XBRUSD"),
     "controls": ("the Red Sea war-risk episode over its own dates, which is the same insurance "
                  "market reacting to a different war",
                  "the matched-season control in 2021, before any premium existed",
                  "global dry-bulk freight as the competing explanation"),
     "notes": "PRESS_REPORTED BY CONSTRUCTION: the assessments are licensed and registered "
              "unread, so no cell here is promoted without a second independent dated source"},
    {"id": "XX-B", "title": "The sanctions and negotiation headline plane",
     "jurisdiction": "joint", "family": "policy_event", "horizon": "intraday",
     "objects": ("the dated EU sanctions packages and the US designations",
                 "the negotiation and ceasefire-talk announcements",
                 "the IAEA plant-status updates as tail-risk events",
                 "the corridor and ban announcements already dated elsewhere in this pack"),
     "conditions": ("the event class: sanctions, negotiation, or nuclear-safety",
                    "whether the announcement was pre-trailed in the source graph",
                    "the prevailing European gas price percentile"),
     "instruments": ("XNGUSD", "GER40", "EURUSD", "XAUUSD"),
     "controls": ("the matched weekday-plus-hour control on all four legs",
                  "days with a comparable global risk headline and no Black Sea content",
                  "the pre-trailed versus surprise split, which is the source graph's own test"),
     "notes": "THE MOST OVER-TRADED AND LEAST-MEASURED PLANE IN THIS REGION. The domain exists "
              "to measure whether headline reaction survives a matched control AT ALL, and a "
              "null here is a valuable result that stops a great deal of bad trading"},
    {"id": "XX-C", "title": "Two calendars and two clocks: the 2023 Ukrainian break",
     "jurisdiction": "joint", "family": "calendar_microstructure", "horizon": "session",
     "objects": ("the 2023 Ukrainian holiday law and the days it created and destroyed",
                 "the Belarusian calendar, unchanged, with Radunitsa derived each year",
                 "the asymmetric closure days when exactly one country is shut",
                 "the five months a year when Kyiv and Minsk are on different UTC offsets"),
     "conditions": ("whether the day is a joint closure, an asymmetric one, or neither",
                    "whether the clocks diverge that week",
                    "the pre-2023 versus post-2023 calendar era"),
     "instruments": ("EURPLN", "EURUSD", "USDRUB"),
     "controls": ("the same weekday in the adjacent weeks, which is the holiday-liquidity null",
                  "the pre-2023 Ukrainian calendar on the same instruments, the country as its "
                  "own control across its own legal break",
                  "Polish and Hungarian closures over the same days, which is the `pl` and "
                  "`cee_balkans` ground"),
     "notes": "A CALENDAR BREAK IS A REGIME BREAK NO PRICE SERIES EXPLAINS: 7 January was a "
              "closed Ukrainian day until 2023 and is an ordinary working day now, and a study "
              "that pools 2021 with 2024 is using two different calendars without knowing it"},
)

# --------------------------------------------------------------------------- miners
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    {"name": "bs_bsgi_event_windows", "domain_ids": ("UA-A",), "kind": "event",
     "cadence_s": 86400.0, "steerable": False, "wired": False,
     "entry": "countries.black_sea.miners:bsgi_event_windows",
     "needs": ("BSGI_EVENTS", "WHEAT, CORN, SOYBEAN H1 bars"),
     "notes": "NOT WIRED. Eight dated Initiative announcements with the matched weekday-plus-"
              "hour control beside them; the sample is small and is reported, never padded"},
    {"name": "bs_corridor_regime_split", "domain_ids": ("UA-B", "XX-A"), "kind": "macro",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.black_sea.miners:corridor_regime_split",
     "needs": ("CORRIDOR_ERAS", "WHEAT, CORN H1 bars"),
     "notes": "NOT WIRED. Each corridor regime measured against the others on the same "
              "instruments -- the country as its own control across its own route changes"},
    {"name": "bs_import_ban_events", "domain_ids": ("UA-C",), "kind": "event",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.black_sea.miners:import_ban_events",
     "needs": ("IMPORT_BAN_EVENTS", "WHEAT, CORN, EURPLN H1 bars"),
     "notes": "NOT WIRED. All five rows are PRESS_REPORTED, so this miner may mint hypotheses "
              "and nothing compiled on it is promoted until an act number is attached"},
    {"name": "bs_uah_regime_break", "domain_ids": ("UA-D",), "kind": "macro",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.black_sea.miners:uah_regime_break",
     "needs": ("UAH_ERAS", "EURPLN, USDPLN, EURUSD H1 bars"),
     "notes": "NOT WIRED. Two switch dates and four eras; the fixed eras are declared UNTRADABLE "
              "as volatility samples and the miner says so instead of averaging them"},
    {"name": "bs_byn_basket_residual", "domain_ids": ("BY-D",), "kind": "macro",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.black_sea.miners:byn_basket_residual",
     "needs": ("BASKET_ERAS", "NBRB:kurs_kosh", "USDRUB, EURRUB H1 bars"),
     "notes": "NOT WIRED. The arithmetic basket-implied move is subtracted first; what is left "
              "is the policy, and that residual is the only thing tested"},
    {"name": "bs_potash_route_break", "domain_ids": ("BY-A", "BY-B"), "kind": "transfer",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.black_sea.miners:potash_route_break",
     "needs": ("the 2021-2022 measure dates and 2022-02-01", "CORN, WHEAT, SOYBEAN H1 bars"),
     "notes": "NOT WIRED. An INPUT-cost claim on a one-to-two quarter horizon, run with "
              "phosphate affordability as the other-nutrient control"},
    {"name": "bs_calendar_asymmetry", "domain_ids": ("XX-C",), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.black_sea.miners:calendar_asymmetry",
     "needs": ("market_holidays", "asymmetric_closure_days", "EURPLN, EURUSD, USDRUB H1 bars"),
     "notes": "NOT WIRED. The asymmetric closure days as the sample and the joint closures as "
              "the placebo; both halves of the asymmetry are run"},
    {"name": "bs_transmission_seeds",
     "domain_ids": ("UA-E", "UA-F", "UA-G", "UA-H", "BY-C", "BY-E", "XX-A", "XX-B"),
     "kind": "transfer", "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.black_sea.miners:transmission_seeds",
     "needs": ("TRANSMISSION_EDGES_SEED",),
     "notes": "NOT WIRED. The pack's map as HYPOTHESIS discoveries, deduplicated by the registry"},
)
MINER_DOMAINS: dict[str, tuple[str, ...]] = {
    "central_bank_surprise": ("UA-D", "BY-D"),
    "release_surprise": ("UA-B", "BY-E"),
    "calendar_settlement": ("XX-C", "UA-D"),
    "holiday_liquidity": ("XX-C",),
    "session_microstructure": ("XX-C", "XX-B"),
    "positioning": ("UA-B", "UA-A"),
    "carry_funding": ("BY-D", "UA-D"),
    "corporate_flow": ("UA-G", "UA-H"),
    "institutional_flow": ("UA-C", "BY-B"),
    "equity_mechanics": ("UA-H",),
    "derivatives_expiry": ("UA-A",),
    "failure": ("UA-E", "BY-C"),
    "residual": ("BY-D", "XX-A"),
    "transfer": ("BY-A", "UA-F"),
    "scouts": ("XX-B", "BY-E"),
}


# --------------------------------------------------------------------------- transmission
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    {"id": "BS-E1", "source": "Black Sea Grain Initiative suspension, resumption and termination "
                              "announcements",
     "target": "WHEAT", "targets": ("WHEAT", "CORN"), "to_country": "global", "sign": "+",
     "mechanism": "an announced halt to the only corridor moving roughly 33 mt of grain is an "
                  "immediate, unambiguous supply shock with a known minute; a resumption is the "
                  "same shock with the sign reversed",
     "horizon": "0 to 5 sessions", "horizon_class": "intraday", "lag_days": 0.0,
     "actor": "the Joint Coordination Centre and the four participating parties",
     "constraint": "unanimity -- any party could halt the mechanism and one did",
     "flow": "physical export supply",
     "condition": "the eight dated Initiative events only; renewals and suspensions are "
                  "separate classes",
     "control": "the matched weekday-plus-hour window; Russian export-pace news days on the "
                "same instruments; a randomised-date null on the Initiative's operating days",
     "falsifier": "the announcement windows carry no abnormal WHEAT or CORN move beyond the "
                  "matched control -- which would be a major negative result, because these "
                  "are the best-dated grain supply announcements of the decade",
     "evidence": "HYPOTHESIS"},
    {"id": "BS-E2", "source": "Ukrainian monthly grain export tonnage against the USDA balance",
     "target": "CORN", "targets": ("CORN", "WHEAT", "SOYBEAN"), "to_country": "global",
     "sign": "-",
     "mechanism": "the export pace is the world balance sheet's Ukrainian line; a pace that "
                  "beats the forecast is supply arriving sooner than the balance assumed",
     "horizon": "1 to 6 weeks", "horizon_class": "multi_day", "lag_days": 7.0,
     "actor": "the Ministry of Agrarian Policy and the exporting trade",
     "constraint": "the corridor's availability and the port capacity that survives",
     "flow": "export pace", "condition": "months whose surprise exceeds the historical "
                                         "interquartile range of the forecast error",
     "control": "the Romanian and Bulgarian export pace over the same weeks; months with no "
                "surprise as the null; the Russian crop as the competing supply story",
     "falsifier": "large Ukrainian export-pace surprises are not followed by abnormal WHEAT or "
                  "CORN behaviour once the US and Russian balances are controlled",
     "evidence": "HYPOTHESIS"},
    {"id": "BS-E3", "source": "The 2023 neighbour import bans and the EU restriction acts",
     "target": "EURPLN", "targets": ("EURPLN", "WHEAT", "CORN"), "to_country": "global",
     "sign": "+",
     "mechanism": "closing five land markets to the same tonnage REDIRECTS rather than destroys "
                  "it, so the effect is an intra-EU basis and a CEE political-risk event before "
                  "it is a flat-price one",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "the European Commission and the five frontline member states",
     "constraint": "farmer politics against single-market rules",
     "flow": "trade redirection",
     "condition": "the five dated 2023 events and the two blockade episodes",
     "control": "the same windows in 2022 before any ban existed; the Romanian route, which "
                "stayed open; the matched weekday control on EURPLN",
     "falsifier": "the ban announcement windows carry no abnormal EURPLN behaviour and no "
                  "measurable redirection in the DG AGRI weekly licence data",
     "evidence": "HYPOTHESIS"},
    {"id": "BS-E4", "source": "Belarusian potash route closure and the affordability ratio",
     "target": "CORN", "targets": ("CORN", "WHEAT", "SOYBEAN"), "to_country": "global",
     "sign": "+",
     "mechanism": "potash is the nutrient the next crop's yield is bought with; removing a "
                  "fifth of world supply from its normal route raises the delivered cost, and "
                  "an unaffordable nutrient cuts applied rates and shifts acreage toward the "
                  "crops that need less of it",
     "horizon": "1 to 2 quarters", "horizon_class": "multi_day", "lag_days": 90.0,
     "actor": "Belaruskali, BPC and Belarusian Railway",
     "constraint": "the farmer's affordability, not the producer's cost",
     "flow": "input cost into acreage",
     "condition": "an affordability-ratio move beyond its historical interquartile range",
     "control": "PHOSPHATE affordability over the same seasons, the other nutrient; seasons "
                "with no ratio move; USDA applied-rate and acreage estimates",
     "falsifier": "seasons with a large potash-affordability move show no change in USDA's "
                  "applied-rate or acreage estimates, which would break the mechanism at its "
                  "first link",
     "evidence": "MEASURED_ELSEWHERE"},
    {"id": "BS-E5", "source": "The NBRB published basket residual",
     "target": "USDRUB", "targets": ("USDRUB", "EURRUB"), "to_country": "global", "sign": "+",
     "mechanism": "the basket's weights are PUBLISHED, so the arithmetic implied move is known "
                  "exactly; what is left over is the National Bank's own decision, and a "
                  "central bank deviating from its announced arithmetic is information",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "the NBRB Board and its BCSE session desk",
     "constraint": "a basket whose largest weight is the rouble",
     "flow": "administered FX",
     "condition": "the residual's outer quartiles only",
     "control": "the same residual on a block-permuted BYN series; the pre-2022 basket era; the "
                "Kazakh tenge over the same weeks",
     "falsifier": "the residual carries no information about the following days' USDRUB path, "
                  "in which case the NBRB is a pure follower and the pack records it",
     "evidence": "HYPOTHESIS"},
    {"id": "BS-E6", "source": "Ukrainian gas transit expiry and the Ukrainian grid war",
     "target": "XNGUSD", "targets": ("XNGUSD", "GER40", "EUSTX50"), "to_country": "global",
     "sign": "+",
     "mechanism": "a supply route closing and a demand centre being rationed are both European "
                  "gas and power events; they reach this desk through the European industrial "
                  "cost the indices carry, and through a gas benchmark that is a declared WEAK "
                  "proxy for the true leg",
     "horizon": "1 to 8 weeks", "horizon_class": "multi_day", "lag_days": 3.0,
     "actor": "GTSOU, Naftogaz and Ukrenergo",
     "constraint": "a ship-or-pay contract that ended on a known date and a grid under attack",
     "flow": "physical energy flow",
     "condition": "the European storage-fill percentile and the season",
     "control": "European weather-adjusted demand; the LNG arrival schedule; the same calendar "
                "weeks in the years the contract ran",
     "falsifier": "the expiry and the dated strike weeks carry no abnormal European gas or "
                  "index behaviour once storage, weather and LNG are controlled -- which is "
                  "plausible for an event known a year in advance, and is the honest prior",
     "evidence": "HYPOTHESIS"},
    {"id": "BS-E7", "source": "The Black Sea war-risk insurance premium",
     "target": "WHEAT", "targets": ("WHEAT", "CORN", "XBRUSD"), "to_country": "global",
     "sign": "+",
     "mechanism": "the premium is the corridor's real cost: when cover is dear the FOB basis "
                  "widens and fewer vessels sail, which shows up as export pace before it shows "
                  "up as price",
     "horizon": "2 to 8 weeks", "horizon_class": "multi_day", "lag_days": 14.0,
     "actor": "the London war-risk market and the state-backed facility",
     "constraint": "a risk with no long history and therefore no credible base rate",
     "flow": "freight and insurance cost",
     "condition": "dated premium moves and the fortnight after an incident",
     "control": "the Red Sea war-risk episode over its own dates; 2021 as the no-premium base; "
                "global dry-bulk freight as the competing explanation",
     "falsifier": "dated premium moves are not followed by a measurable change in sailings or "
                  "in the export pace within a fortnight",
     "evidence": "HYPOTHESIS"},
    {"id": "BS-E8", "source": "Ukrainian sunflower-oil disruption and the vegetable-oil complex",
     "target": "SOYBEAN", "targets": ("SOYBEAN", "CORN", "COTTON"), "to_country": "global",
     "sign": "+",
     "mechanism": "about 45% of world sunflower-oil exports do not simply disappear: buyers "
                  "substitute into soy and palm oil, and the crush and acreage economics of the "
                  "substitutes move with them",
     "horizon": "1 to 3 months", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "the Ukrainian crushers and the international oils trade",
     "constraint": "crush capacity, the corridor, and the palm policy of two other governments",
     "flow": "substitution demand",
     "condition": "corridor-disrupted months with a measurable sunoil export shortfall",
     "control": "Russian sunoil exports over the same months; Indonesian palm export-levy "
                "changes; matched seasons with no disruption",
     "falsifier": "months with a large sunoil export shortfall show no abnormal soy-complex "
                  "behaviour once the palm policy state and the soybean balance are controlled",
     "evidence": "HYPOTHESIS"},
    {"id": "BS-E9", "source": "Ukrainian ore and steel export constrained by the ports",
     "target": "EUSTX50", "targets": ("EUSTX50", "GER40"), "to_country": "global", "sign": "-",
     "mechanism": "a fifth of Europe's imported pellet feed cannot sail when the corridor is "
                  "shut, so European mills pay a different price for the same input and the "
                  "industrial index carries it",
     "horizon": "1 to 2 quarters", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "the Kryvyi Rih complex and the European steel mills",
     "constraint": "ore is too low-value for rail to Europe to clear at scale",
     "flow": "input supply", "condition": "quarters with a large ore-export shortfall",
     "control": "the seaborne iron-ore benchmark; Brazilian and Australian supply events; "
                "European gas cost as the competing steel-margin driver",
     "falsifier": "quarters with collapsed Ukrainian ore exports show no abnormal European "
                  "index behaviour once the benchmark and the gas cost are controlled -- the "
                  "honest expectation, and the pack measures it rather than assuming it",
     "evidence": "HYPOTHESIS"},
    {"id": "BS-E10", "source": "The hryvnia regime switches and the Ukrainian risk complex",
     "target": "EURPLN", "targets": ("EURPLN", "USDPLN"), "to_country": "global", "sign": "+",
     "mechanism": "Poland carries Ukrainian risk in its currency more than any other quoted "
                  "market -- refugees, the border, the trade and the security premium -- so a "
                  "Ukrainian regime break is a zloty event when it is not a hryvnia one",
     "horizon": "0 to 20 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "the NBU Board and the Ministry of Finance",
     "constraint": "reserves that are a function of external disbursements",
     "flow": "risk repricing",
     "condition": "the two switch dates and the outer quartile of the cash-rate spread",
     "control": "NBP decision days on the same pair, separating 'Poland' from 'Ukraine'; the "
                "pre-2022 era; the matched weekday-plus-hour control",
     "falsifier": "Ukrainian regime and control-stress dates carry no abnormal EURPLN move "
                  "beyond the NBP's own calendar and the global risk tape",
     "evidence": "HYPOTHESIS"},
    {"id": "BS-E11", "source": "Turkish TMO tenders and the Straits as the corridor's host",
     "target": "WHEAT", "targets": ("WHEAT", "EURTRY", "USDTRY"), "to_country": "global",
     "sign": "+",
     "mechanism": "Türkiye is the marginal buyer of Black Sea wheat and the venue of the "
                  "corridor's administration at once; a state tender is a dated demand event "
                  "and the lira legs carry its import-cost side",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 2.0,
     "actor": "the TMO and the Turkish milling industry",
     "constraint": "a domestic crop that varies with Anatolian rainfall",
     "flow": "import demand", "condition": "announced TMO tender and award dates",
     "control": "Egyptian GASC tender windows over the same weeks; the matched weekday control; "
                "months with no tender as the null",
     "falsifier": "TMO tender dates carry no abnormal WHEAT move beyond the matched control and "
                  "no effect on the Ukrainian export pace in the following month",
     "evidence": "HYPOTHESIS"},
    {"id": "BS-E12", "source": "Belarusian refinery supply halts on the Druzhba",
     "target": "XBRUSD", "targets": ("XBRUSD", "XTIUSD"), "to_country": "global", "sign": "+",
     "mechanism": "about 24 mt a year of refining capacity stopping or restarting is a dated "
                  "crude-demand event on a named pipeline, with a published dispute behind it",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "Belneftekhim, Transneft and the Russian producers",
     "constraint": "a single pipeline supplier with pricing power",
     "flow": "refinery crude demand",
     "condition": "the dated 2020 halt and resumption days",
     "control": "Russian refinery outage windows over the same months; the matched weekday "
                "control on the crude legs; quarters with no dispute",
     "falsifier": "the dated halt days show no abnormal crude behaviour beyond the global tape "
                  "-- the likely finding given the volumes, and the mechanism is kept because "
                  "the DATE is unambiguous and the test is cheap",
     "evidence": "HYPOTHESIS"},
    {"id": "BS-E13", "source": "The 2023 Ukrainian calendar break and the Kyiv-Minsk clock "
                               "divergence",
     "target": "EURUSD", "targets": ("EURUSD", "EURPLN", "USDRUB"), "to_country": "global",
     "sign": "+",
     "mechanism": "a legal change to which days a country stops reporting, and a five-month "
                  "annual divergence between two capitals' UTC offsets, both change WHICH HOUR "
                  "a fixed-UTC window is measuring -- a microstructure effect with no price "
                  "cause at all",
     "horizon": "the session", "horizon_class": "intraday", "lag_days": 0.0,
     "actor": "the Verkhovna Rada and the Belarusian Council of Ministers",
     "constraint": "Kyiv keeps EU summer time and Minsk has been fixed UTC+3 since 2014",
     "flow": "reporting and liquidity calendar",
     "condition": "asymmetric closure days and clock-divergence weeks",
     "control": "the same weekday in adjacent weeks; the pre-2023 Ukrainian calendar; Polish "
                "and Hungarian closures over the same days",
     "falsifier": "asymmetric closure days and clock-divergence weeks are indistinguishable "
                  "from their matched controls, in which case the calendar carries no "
                  "measurable microstructure and the pack records that",
     "evidence": "HYPOTHESIS"},
)

# --------------------------------------------------------------------------- policy eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    {"name": "pre-war: a floating hryvnia, an open corridor and a functioning potash route",
     "start": "2019-01-01", "end": "2022-02-23",
     "regime": "Ukraine on a managed float with inflation targeting and full deep-sea export; "
               "Belarus selling potash through Klaipeda under a 50/30/20 published basket",
     "markers": ("2020-01-01 the five-year gas transit contract begins",
                 "2020-01 to 2020-03 the Russia-Belarus oil pricing dispute halts Druzhba "
                 "supply to Mozyr and Naftan",
                 "2021-06 the first EU potash measures", "2021-08-09 US measures on Belaruskali",
                 "2021-12-08 US measures on BPC with a wind-down to 2022-04-01"),
     "why_it_matters": "the only modern baseline for both economies; a corridor study that "
                       "needs a no-disruption control uses this era and no other",
     "status": "SETTLED"},
    {"name": "the route closures: Klaipeda ends, then the ports close",
     "start": "2022-02-01", "end": "2022-07-21",
     "regime": "Lithuanian potash transit terminates on 2022-02-01; the Ukrainian deep-sea "
               "ports stop on 2022-02-24 with roughly 20 mt stranded; the hryvnia is fixed and "
               "capital controls are imposed; the key rate is frozen and then taken to 25%",
     "markers": ("2022-02-01 the Lithuanian transit termination takes effect",
                 "2022-02-24 the ports close and the official rate is fixed",
                 "2022-06-02 the key rate goes from 10% to 25%"),
     "why_it_matters": "two independent route closures inside six months, which is why the "
                       "grain and the fertiliser legs must be controlled against each other",
     "status": "SETTLED"},
    {"name": "the Black Sea Grain Initiative",
     "start": "2022-07-22", "end": "2023-07-17",
     "regime": "a negotiated corridor with Russian participation in the inspections, "
               "administered from Istanbul with a public vessel table; the hryvnia devalued "
               "about 25% to 36.5686 on 2022-07-21, the day before the signature",
     "markers": ("2022-07-21 the hryvnia devaluation", "2022-07-22 the Initiative signed",
                 "2022-08-01 the first vessel sails",
                 "2022-10-29 to 2022-11-02 the suspension and resumption",
                 "2022-11-17, 2023-03-18 and 2023-05-18 the three renewals"),
     "why_it_matters": "THE CLEANEST EVENT GROUND IN THE PACK, and a regime that cannot be "
                       "pooled with what came before or after it",
     "status": "SETTLED"},
    {"name": "the gap and the unilateral corridor",
     "start": "2023-07-18", "end": "2023-10-02",
     "regime": "the Initiative is terminated; port and Danube infrastructure is struck; the "
               "Ukrainian maritime corridor is announced on 2023-08-10 and the first vessels "
               "sail under it; the EU restriction on the five member states lapses on "
               "2023-09-15 and three of them extend unilaterally",
     "markers": ("2023-07-17 the termination", "2023-08-10 the corridor announcement",
                 "2023-09-15 the EU measure lapses and the national bans are extended"),
     "why_it_matters": "the shortest and most information-dense era in the pack: three "
                       "independent regime changes in eleven weeks",
     "status": "SETTLED"},
    {"name": "managed flexibility and the defended corridor",
     "start": "2023-10-03", "end": "2024-12-31",
     "regime": "the NBU moves to managed flexibility; the Ukrainian corridor's throughput "
               "eventually exceeds the Initiative's; the Polish border blockades run through "
               "the winter; the eurobonds are restructured",
     "markers": ("2023-10-03 the exchange-rate regime change",
                 "2023-11-06 the Polish haulier blockade begins",
                 "2024-02-20 the farmers' blockade reaches the rail crossings"),
     "why_it_matters": "the first era in which a Ukrainian FX state variable can vary at all, "
                       "and the era the pack's forward cells actually live in",
     "status": "SETTLED"},
    {"name": "no transit: the European gas map after 2025-01-01",
     "start": "2025-01-01", "end": "2026-12-31",
     "regime": "the gas transit contract has expired and flows are zero; the corridor operates "
               "under insurance rather than negotiation; the grid war continues through the "
               "winters",
     "markers": ("2024-12-31 the transit contract expires",
                 "2025-01-01 the first day with no Russian gas transit through Ukraine"),
     "why_it_matters": "the current regime; every forward cell this pack mints is compiled here "
                       "and nowhere else",
     "status": "OPEN"},
    {"name": "the Belarusian basket: euro out, yuan in",
     "start": "2022-07-14", "end": "2026-12-31",
     "regime": "the NBRB's published basket replaces the euro leg with the renminbi and raises "
               "the rouble weight; the administered-price regime follows in October 2022",
     "markers": ("2022-07-14 the basket recomposition, PRESS_REPORTED and to be verified "
                 "against the NBRB resolution",
                 "2022-10 Council of Ministers Resolution No. 713 and the general price regime"),
     "why_it_matters": "the arithmetic of BY-D changes here, so every BYN-to-rouble mapping "
                       "before and after is a different function",
     "status": "OPEN"},
    {"name": "the Ukrainian calendar break",
     "start": "2023-07-14", "end": "2026-12-31",
     "regime": "Law No. 3258-IX moves Christmas to 25 December, abolishes the Soviet-era 8 March "
               "and 1 May, replaces 9 May with 8 May, and moves Statehood Day and Defenders' "
               "Day; Belarus keeps its calendar unchanged",
     "markers": ("2023-07-14 the law is adopted",
                 "2023-12-25 the first 25 December Christmas as a statutory holiday",
                 "2024-01-07 the first ordinary working 7 January in Ukraine"),
     "why_it_matters": "a regime break in the CALENDAR that no price or weather series explains, "
                       "and one a pooled holiday-liquidity study will silently average away",
     "status": "OPEN"},
)

# --------------------------------------------------------------------------- constraints
ACCESS_CONSTRAINTS: tuple[dict[str, Any], ...] = (
    {"constraint": "BOTH JURISDICTIONS ARE UNDER SANCTIONS REGIMES, AND THIS PACK TOUCHES NONE "
                   "OF THEM. Nothing here reaches a sanctioned entity's private systems and "
                   "nothing bypasses an access control",
     "measured": "every source row in SOURCE_CLASSES is PUBLIC official statistics, PUBLIC "
                 "international-organisation data (FAO AMIS, UN Comtrade, IGC, USDA FAS GAIN, "
                 "the UN's own published BSGI vessel table) or PUBLIC press; no credential, no "
                 "private feed, no venue connectivity and no scraping of a terms-forbidden page",
     "consequence": "SANCTIONS CONSTRAIN TRANSACTIONS, NOT THE READING OF PUBLISHED STATISTICS. "
                    "The desk executes broker symbols only and never a Ukrainian or Belarusian "
                    "instrument, so no cell this pack mints can transact with either economy"},
    {"constraint": "UAH and BYN are not quoted by this broker",
     "measured": "data/universe/universe.json holds no UAH or BYN symbol",
     "consequence": "every domestic mechanism terminates in the softs, the energy legs, the "
                    "European indices, the Polish and Turkish crosses or the rouble; both "
                    "currencies are INPUTS and never cells"},
    {"constraint": "the potash and Black Sea FOB price assessments forbid machine extraction",
     "measured": "Argus, CRU, Profercy and ICIS terms; registered machine_use_allowed=false",
     "consequence": "the two prices this pack would most like are UNMEASURED, so BY-A is tested "
                    "on the CROPS and on published TONNAGE and UA-B is tested on the ministry's "
                    "export series -- the absence is named and worked WITH, never around"},
    {"constraint": "Belarusian trade statistics were reclassified or withheld after 2022",
     "measured": "several Belstat export lines, potash and oil products above all, stop or lose "
                 "their commodity breakdown",
     "consequence": "those months are UNMEASURED in the official series and are read from the "
                    "UN Comtrade mirror instead; the two are NEVER silently spliced, and a cell "
                    "compiled on a mirror month carries that label"},
    {"constraint": "Ukrainian statistical publication was curtailed under martial law",
     "measured": "Ukrstat suspended, delayed or reclassified several series from 2022",
     "consequence": "a release-surprise cell on a suspended Ukrainian series is UNMEASURED and "
                    "is reported as such rather than filled from a private estimate"},
    {"constraint": "the BSGI vessel page no longer exists",
     "measured": "the Initiative ended 2023-07-17 and the live UN page was retired",
     "consequence": "the cleanest physical experiment in the pack is reachable only through the "
                    "ARCHIVE layer's crawls; a cell compiled on an un-archived week is "
                    "UNMEASURED rather than assumed"},
    {"constraint": "the import-ban and basket-recomposition dates are PRESS_REPORTED",
     "measured": "IMPORT_BAN_EVENTS and the 2022-07-14 basket row carry no act, regulation or "
                 "resolution number",
     "consequence": "the desk may generate hypotheses off them and may PROMOTE nothing until an "
                    "Official Journal or NBRB citation is attached to the date the cell was "
                    "compiled on"},
    {"constraint": "there is no Ukrainian equity or derivatives tape and no venue access "
                   "anywhere in this pack",
     "measured": "the Ukrainian Exchange and PFTS have been dormant since 2022-02-24; the "
                 "desk has no BCSE or BUCE feed, no licence and no connectivity, and seeks none",
     "consequence": "equity-mechanics and derivatives-expiry cells are UNMEASURED by "
                    "construction for both jurisdictions; the published session RESULTS are "
                    "read and no order book is touched anywhere (mandate 2026-08-18)"},
    {"constraint": "the true gas leg is TTF and it is not quoted here",
     "measured": "data/universe/universe.json holds XNGUSD (Henry Hub) and no European hub",
     "consequence": "every gas edge in this pack declares XNGUSD a WEAK proxy on its face, and "
                    "the European indices carry the industrial-cost half of the mechanism"},
)

INSTITUTIONAL_FLOW_SOURCES: tuple[str, ...] = (
    "Ministry of Agrarian Policy weekly and monthly grain export tonnage",
    "UN Joint Coordination Centre vessel movement table (2022-2023)",
    "Ukrainian Sea Ports Authority monthly throughput by port",
    "NBU published daily FX intervention volumes and monthly reserves",
    "EU DG AGRI weekly cereal import licences by member state",
    "NBRB daily official rate and published basket value",
    "Belstat monthly trade by commodity group and the UN Comtrade mirror",
    "BUCE published commodity auction results",
)
SERIES: dict[str, str] = {
    "UA_POLICY": "NBU:oblikova_stavka", "UA_FX": "NBU:kurs",
    "UA_INTERVENTION": "NBU:fx_intervention", "UA_RESERVES": "NBU:reserves",
    "UA_EXPORT": "MINAGRO:export_tonnage", "UA_PORTS": "USPA:throughput",
    "UA_GRID": "UKRENERGO:grid_status", "UA_TRANSIT": "GTSOU:transit_nominations",
    "UA_CPI": "UKRSTAT:cpi", "UA_OVDP": "MOF:ovdp_auction",
    "BY_POLICY": "NBRB:refinancing_rate", "BY_FX": "NBRB:kurs_kosh",
    "BY_BASKET": "NBRB:basket_weights", "BY_TRADE": "BELSTAT:trade",
    "BY_AUCTION": "BUCE:auction_results",
    "JOINT_BSGI": "JCC:vessel_table", "JOINT_LICENCES": "DGAGRI:cereals_dashboard",
    "JOINT_MIRROR": "COMTRADE:mirror", "JOINT_WARRISK": "PRESS:war_risk_premium",
}


# --------------------------------------------------------------------------- interactions
#: WHERE THIS PACK MEETS ITS SIBLINGS. The desk's failure mode is testing each country alone and
#: calling the shared shock a discovery in both. Each row names the OTHER pack, the mechanism
#: that joins them, the observable that separates them, and the control that must be run.
INTERACTIONS: tuple[dict[str, Any], ...] = (
    {"with": "ru",
     "mechanism": "the same Black Sea basin and the same wheat book: Russian export pace, the "
                  "export duty and the floor price are the OTHER half of every corridor study, "
                  "and the Druzhba crude that feeds Mozyr and Naftan is the `ru` pack's Urals "
                  "leg one pipeline upstream",
     "observable": "Russian weekly export pace and duty resets against the Ukrainian tonnage in "
                   "the same weeks; the Urals-to-Brent differential against the Belarusian "
                   "refinery premium",
     "targets": ("WHEAT", "CORN", "XBRUSD", "USDRUB"),
     "control": "every Ukrainian corridor event is run with Russian export-pace news days as an "
                "explicit control sample, so 'the basin moved' is told from 'Ukraine moved'; "
                "the `ru` pack owns the budget rule, the tax date and the Urals discount and "
                "this pack owns none of them"},
    {"with": "pl",
     "mechanism": "Poland is the land route, the blockading neighbour and the currency that "
                  "carries Ukrainian risk; the 2023 ban and the 2023-11 and 2024-02 blockades "
                  "are Polish domestic politics with a Ukrainian supply consequence",
     "observable": "the dated ban and blockade events against EURPLN and against the DG AGRI "
                   "licence data by member state; the rail-crossing queue at the gauge break",
     "targets": ("EURPLN", "USDPLN", "WHEAT", "CORN"),
     "control": "NBP decision days on the same pair as the separating control -- EURPLN is a "
                "zloty pair first and a grain-politics pair second, and the `pl` pack owns the "
                "NBP reaction function while this pack owns only the grain politics"},
    {"with": "cee_balkans",
     "mechanism": "the Danube is one river with two packs on it: the lower reach and Constanta "
                  "belong to `cee_balkans` and the Izmail-Reni reach to this one, and the "
                  "Romanian, Bulgarian, Hungarian and Slovak import bans are the same 2023 act",
     "observable": "the Constanta export pace against the Ukrainian Danube throughput in the "
                   "same weeks; lower-Danube draught restrictions against Izmail and Reni "
                   "tonnage; EURHUF and EURCZK around the same ban dates",
     "targets": ("WHEAT", "CORN", "EURHUF", "EURCZK"),
     "control": "the Romanian route stayed open when the Polish and Hungarian ones closed, so "
                "Constanta IS the natural control for a ban study and the Rhine at Kaub is the "
                "control for a low-water one"},
    {"with": "tr",
     "mechanism": "Türkiye hosted the corridor's administration, controls the Straits under the "
                  "Montreux Convention and is the marginal buyer of Black Sea wheat; the lira's "
                  "own import-cost channel is the `tr` pack's and the corridor role is this "
                  "pack's",
     "observable": "TMO tender announcements and awards against WHEAT and against the Ukrainian "
                   "export pace; Straits transit notices against the vessel counts",
     "targets": ("WHEAT", "EURTRY", "USDTRY"),
     "control": "Egyptian GASC tender windows over the same weeks separate 'a big buyer "
                "tendered' from 'Türkiye tendered'; the `tr` pack's own CBRT reaction function "
                "is never re-tested here"},
    {"with": "kz",
     "mechanism": "Kazakhstan is the CIS grain and transit sibling: it exports wheat into the "
                  "same Central Asian and Caucasus markets Ukrainian and Russian grain reaches, "
                  "and its managed tenge is the other CIS FX regime a Belarusian basket study "
                  "must be told apart from",
     "observable": "Kazakh wheat export volumes against Ukrainian ones into the shared markets; "
                   "the tenge's managed path against the BYN basket residual over the same weeks",
     "targets": ("WHEAT", "USDRUB", "EURUSD"),
     "control": "the tenge over identical windows is the control that separates 'CIS FX "
                "conditions' from 'the NBRB decided'; the `kz` pack owns the CPC route and the "
                "National Fund and this pack owns neither"},
    {"with": "ma",
     "mechanism": "TWO NUTRIENTS, ONE PLANTING DECISION. Morocco is the phosphate and Belarus "
                  "is the potash, and a farmer's affordability constraint is over the nutrient "
                  "BUNDLE -- which makes each pack the other's natural control for telling "
                  "'fertiliser' from 'this fertiliser'",
     "observable": "the potash-to-corn and the DAP-to-corn affordability ratios over the same "
                   "seasons, against USDA applied-rate and acreage estimates",
     "targets": ("CORN", "WHEAT", "SOYBEAN"),
     "control": "BY-A is run with phosphate affordability as its explicit other-nutrient "
                "control and `ma`'s MA-D is run with potash as its own; neither may claim the "
                "shared acreage effect alone"},
)

# --------------------------------------------------------------------------- cells
#: THE TESTABLE CELLS THIS PACK MINTS: domain x executable instrument x named condition. Every
#: condition is one the pack's OWN data plane can evaluate -- a corridor regime from
#: `corridor_regime`, an era from `uah_regime`, a basket era from `byn_basket_weights`, a
#: published tonnage surprise, a dated event list. No cartesian blow-up of nothing: a domain's
#: instruments are the ones its mechanism actually reaches and its conditions are the states it
#: actually declares.
def cells() -> tuple[dict[str, Any], ...]:
    """Every cell this pack can send to the one gauntlet, as plain rows."""
    out: list[dict[str, Any]] = []
    for dom in DOMAINS:
        did = str(dom["id"])
        family = str(dom.get("family") or "residual")
        horizon = str(dom.get("horizon") or "multi_day")
        controls = tuple(dom.get("controls") or ())
        control = str(controls[0]) if controls else ""
        for symbol in dom.get("instruments") or ():
            for i, condition in enumerate(dom.get("conditions") or ()):
                out.append({
                    "cell_id": f"{CODE.lower()}:{did}:{symbol}:c{i + 1}",
                    "domain": did, "symbol": str(symbol), "condition": str(condition),
                    "mechanism_family": family, "horizon": horizon, "control": control,
                    "why": f"{dom['title']} -- conditioned on {condition}",
                })
    return tuple(out)


CELLS: tuple[dict[str, Any], ...] = cells()


def cells_by_domain() -> dict[str, int]:
    """How many cells each domain contributes. A domain contributing none is a domain with no "
    instruments or no conditions, which the tests refuse."""
    out: dict[str, int] = {}
    for row in CELLS:
        out[str(row["domain"])] = out.get(str(row["domain"]), 0) + 1
    return out


#: What this pack CANNOT measure, by name. `mine` returns these on every pass so an absence is a
#: reported state and never a quiet zero (L1.28a).
UNMEASURED_BY_NAME: tuple[str, ...] = (
    "potash and Black Sea FOB price assessments: LICENSED, machine_use_allowed=false, never "
    "fetched -- BY-A and UA-B are measured on tonnage and on the crops instead",
    "Belstat potash and oil-product export lines after 2022: withheld or reclassified; read "
    "from the UN Comtrade mirror and never silently spliced",
    "Ukrainian equity and derivatives tape: dormant since 2022-02-24, so equity-mechanics and "
    "derivatives-expiry cells are UNMEASURED by construction",
    "TTF and the European gas hubs: absent from the broker, so every gas edge declares XNGUSD a "
    "WEAK proxy on its face",
    "UAH and BYN positioning: no COT contract and no exchange-traded future anywhere the desk "
    "can read, and never proxied by the EUR or RUB legs",
)


def mine(ctx: Any = None) -> dict[str, Any]:
    """THE DEPARTMENT ENTRY. Pure Python, no network, no LLM, no heavy import.

    Reads this pack's own data and returns a plain report. When a country-lab `ctx` is handed
    in, every transmission edge is also recorded through `ctx.record` -- the ONE door a miner
    writes discoveries through -- and the report says how many landed. With `ctx=None` nothing
    is emitted anywhere and the report is the whole answer.
    """
    rows: list[dict[str, Any]] = []
    emitted = 0
    for edge in TRANSMISSION_EDGES_SEED:
        row = {"kind": "transmission_seed", "id": str(edge["id"]),
               "source": str(edge["source"]), "targets": tuple(edge["targets"]),
               "sign": str(edge.get("sign") or ""), "horizon": str(edge.get("horizon") or ""),
               "evidence": str(edge.get("evidence") or "HYPOTHESIS"),
               "control": str(edge.get("control") or ""),
               "falsifier": str(edge.get("falsifier") or "")}
        rows.append(row)
        record = getattr(ctx, "record", None) if ctx is not None else None
        if callable(record):
            try:
                record(mechanism=f"black_sea_transmission:{str(edge['id']).lower()}",
                       source_id="black_sea:edges", source_type="transmission_seed",
                       actor=str(edge.get("actor") or NAME),
                       constraint=str(edge.get("constraint") or ""),
                       economic_rationale=str(edge.get("mechanism") or ""),
                       assets=[str(edge["target"])],
                       horizons=[str(edge.get("horizon_class") or "multi_day")],
                       sessions=["all"], regimes=["unconditional"],
                       required_data=[str(edge.get("source") or "")],
                       pit_requirements=["source publication stamp"],
                       novelty=0.45, confidence=0.3,
                       falsifier=str(edge.get("falsifier") or ""),
                       payload={"edge": dict(edge), "jurisdictions": JURISDICTIONS})
                emitted += 1
            except Exception as exc:  # a miner never takes the department down
                rows.append({"kind": "record_failed", "id": str(edge["id"]),
                             "why": f"{type(exc).__name__}: {exc}"})
    return {"code": CODE.lower(), "jurisdictions": JURISDICTIONS,
            "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "emitted": emitted, "rows": rows,
            "cells_emitted": len(CELLS), "cells_by_domain": cells_by_domain(),
            "n_actors": len(ACTORS), "n_domains": len(DOMAINS),
            "n_datasets": len(DATASETS), "n_sources": len(SOURCE_CLASSES),
            "n_interactions": len(INTERACTIONS),
            "unmeasured": list(UNMEASURED_BY_NAME)}


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
        "mission": MISSION, "jurisdictions": JURISDICTIONS, "currencies": CURRENCIES,
        "nbrb": NBRB, "corridor_eras": CORRIDOR_ERAS, "bsgi_events": BSGI_EVENTS,
        "import_ban_events": IMPORT_BAN_EVENTS, "uah_eras": UAH_ERAS,
        "basket_eras": BASKET_ERAS, "interactions": INTERACTIONS,
        "query_territories": QUERY_TERRITORIES,
        "jurisdiction_layer_gaps": JURISDICTION_LAYER_GAPS,
        "cells": CELLS, "unmeasured": UNMEASURED_BY_NAME,
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
    """The framework's HolidayRule shape: every closed date the rule produces for 2024-2026,
    from BOTH jurisdictions, plus the fixed month-days of each calendar in force."""
    dates = sorted({d.isoformat() for y in HOLIDAYS_RULE["years"] for d in market_holidays(y)})
    fixed = sorted({f"{m:02d}-{d:02d}" for m, d, _n in UA_FIXED_FROM_2023}
                   | {f"{m:02d}-{d:02d}" for m, d, _n, _s in BY_FIXED})
    return {"dates": tuple(dates), "fixed_md": tuple(fixed), "weekly_closed": (5, 6),
            "notes": str(HOLIDAYS_RULE["authority"])}


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
