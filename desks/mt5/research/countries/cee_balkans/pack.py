"""CENTRAL EUROPE AND THE BALKANS: eight monetary regimes on one industrial supply chain.

WHAT THIS REGION IS AS A MARKET MECHANISM, AND WHY IT IS NOT A SMALLER EURO AREA. Czechia,
Hungary, Romania, Bulgaria, Croatia, Serbia, Slovakia and Slovenia sit inside one German
industrial chain and one EU legal order while running EIGHT DIFFERENT monetary regimes at once.
That divergence is the whole research object: the same German order book reaches a free-floating
koruna, a managed forint, an administratively crawled leu, a currency board, and two economies
that have already given up their currency. Six things belong to this region and to no other in
the desk's book, and each is why a domain below exists rather than a row in a generic EM domain.

  1. THE CNB PUBLISHES ITS OWN INTEREST-RATE PATH. The Czech National Bank's Bank Board meets
     EIGHT times a year on monetary policy, sets the two-week repo rate, and -- almost uniquely
     among inflation targeters -- publishes its own FORECAST FAN CHART together with the implied
     trajectory of market rates the forecast is consistent with. The surprise a decision carries
     is therefore measurable against a PUBLISHED path rather than against a survey, which makes
     EURCZK the cleanest policy-surprise tape in the region.

  2. THE KORUNA HAD A FLOOR, AND ITS EXIT IS A DATED REGIME BREAK. From 7 November 2013 to
     6 April 2017 the CNB held EUR/CZK at or above 27.00 by unlimited intervention (the
     `kurzovy zavazek`). The exit was announced at an extraordinary meeting and is one of the
     cleanest regime-break dates in modern FX: the same instrument, the same venue, a floored
     distribution on one side and a float on the other. Any EURCZK statistic pooled across
     6 April 2017 is pooling two different animals.

  3. HUNGARY RAN TWO POLICY RATES AT ONCE. On 14 October 2022 the MNB introduced a ONE-DAY
     DEPOSIT QUICK TENDER at 18% while the base rate stayed at 13%, and ran the pair until the
     two converged on 26 September 2023. For eleven months the effective policy rate of an EU
     member state was set by an emergency instrument announced at a separate hour of the day from
     the Monetary Council's monthly decision -- an administered two-rate regime nothing else in
     Europe had. A study that reads Hungary's "policy rate" over that window reads the wrong one.

  4. THE SWISS FRANC IS A RETAIL BALANCE SHEET HERE, NOT A SAFE HAVEN. Hungarian, Croatian,
     Serbian and Romanian households borrowed in francs before 2008. Hungary converted the stock
     by law in 2015, Croatia by law in 2015 and again by court ruling from 2019, Serbia in 2019.
     CHF crosses in this region are therefore POLITICALLY REFLEXIVE: a franc move is a household
     solvency event that produces legislation, and CHFHUF is the instrument that carries it.

  5. THE LEU'S VOLATILITY IS AN ADMINISTRATIVE CHOICE. The NBR does not declare a band and does
     not float: it runs a near-crawl, defends it with reserves and with the interbank liquidity
     it controls, and re-bases it in steps. EUR/RON realised volatility is therefore lower than
     any of its fundamentals would produce, and the suppression -- not the level -- is the
     mechanism. RON is absent from this broker, so the leu reaches the book through EURHUF and
     EURCZK as the unmanaged siblings and through the Danube grain chain as the real economy.

  6. THE EURO ACCESSION CLOCK IS A HARD, DATEABLE REGIME BREAK. Croatia joined the euro on
     1 January 2023 and the kuna ceased to exist; Bulgaria's currency board has held BGN at
     1.95583 to the euro since 1999 and the Council's decision of 8 July 2025 set its own entry
     at 1 January 2026. An accession date removes an instrument, re-prices every convergence
     trade around it, and is known years in advance -- which makes it the rarest thing in FX
     research: a structural break with a pre-announced date.

WHAT IS EXECUTABLE AND WHAT IS NOT. EURRON, USDRON, EURBGN, EURHRK, EURRSD, the BUX, the PX, the
BET, the Prague and Budapest bond curves, the Bulgarian and Serbian Eurobonds, the CEGH and MGP
gas hubs, HUPX/OPCOM/IBEX power and the Danube barge freight rates are all absent from
`data/universe/universe.json`. Every one is named in `TRANSMISSION_TARGETS` with the broker
symbols its mechanism reaches, so an absent instrument produces a transmission hypothesis and
never a cell that can never be filled (L1.49).

POLAND IS A SEPARATE PACK. The NBP, the zloty, the frankowicze litigation and the WIG are the
`pl` pack's ground and are not restated here. EURPLN appears in this file exactly once, as a
NEIGHBOUR CONTROL in CEE-HU-D: the question "is this the forint or is it CEE beta?" cannot be
asked without it, and borrowing a neighbour as a control is not the same as hunting it.

THE TWO-LANE ORDER. Skoda, OTP, Erste, MOL, OMV Petrom and Romgaz are EVENT-lane instruments.
They enter this pack only as ACTORS -- a carmaker that buys aluminium, a bank that carries a
converted franc book, a producer that sells Black Sea gas -- and the instruments those actors
move are FX crosses, softs, energy and the two European indices. No share CFD appears in any
instrument tuple in this file.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, timedelta
from typing import Any

# --------------------------------------------------------------------------- identity
CODE = "CEE_BALKANS"
NAME = "Central Europe and the Balkans"
REGION_COMMAND = "europe"          # the framework's command; the forest is central_europe
REGION_DESK = "CENTRAL_EUROPE_BALKANS"
FOREST = "central_europe"
#: THE PACK IS MULTI-CURRENCY AND SAYS SO. The forint carries five of the region's eight
#: executable crosses and is the only regional currency the broker quotes against five funding
#: legs, so HUF is the reference the framework's single `currency` slot is given; CZK, RON, BGN,
#: HRK, RSD, EUR (Slovakia, Slovenia, Croatia and, from 2026-01-01, Bulgaria) are carried in
#: `CURRENCY_REGIMES` below, which is where the eight-regime fact actually lives.
CURRENCY = "HUF"
FISCAL_YEAR_END = "12-31"          # every jurisdiction here runs the calendar year
NATIVE_LANGUAGES: tuple[str, ...] = ("cs", "hu", "ro", "bg", "hr", "sr", "sk", "sl", "en")
COT_CURRENCY = ""                  # no CFTC contract exists for CZK, HUF, RON, BGN or RSD
EXPORT_ECONOMY = "manufacturing_exporter"   # autos and their tiers are the regional export
RETAIL_LEVERAGE_REGIME = "capped"           # ESMA 30:1/20:1 caps bind in every EU member here
MISSION = ("mine central Europe and the Balkans as the eight-monetary-regime region on one "
           "German industrial chain: the CNB's published rate path and its 2013-2017 koruna "
           "floor, the MNB's monthly council and its 2022-23 one-day quick-tender era, the CHF "
           "mortgage legacy, the NBR's administered leu, Bulgaria's currency board and the euro "
           "accession clock, the Danube and Constanta grain corridor, the TurkStream and Krk "
           "gas routes, and the Balkan flashpoints -- all of it reaching the HUF and CZK "
           "crosses, the grains, the gas legs and GER40")

#: THE EIGHT REGIMES, declared rather than implied. `framework` uses the country_lab vocabulary.
CURRENCY_REGIMES: tuple[dict[str, Any], ...] = (
    {"country": "Czechia", "currency": "CZK", "framework": "inflation_targeter",
     "note": "free float since 2017-04-06; a hard floor at 27.00 before it"},
    {"country": "Hungary", "currency": "HUF", "framework": "inflation_targeter",
     "note": "free float; a de facto second policy rate 2022-10-14 to 2023-09-26"},
    {"country": "Romania", "currency": "RON", "framework": "managed_float",
     "note": "an undeclared near-crawl the NBR defends and re-bases in steps"},
    {"country": "Bulgaria", "currency": "BGN", "framework": "peg",
     "note": "currency board at 1.95583 from 1999; euro entry dated 2026-01-01"},
    {"country": "Croatia", "currency": "EUR", "framework": "inflation_targeter",
     "note": "euro from 2023-01-01 at 7.53450 HRK; ECB policy from that date"},
    {"country": "Serbia", "currency": "RSD", "framework": "managed_float",
     "note": "a tightly managed float around 117.0-117.3 EUR/RSD, NBS-defended"},
    {"country": "Slovakia", "currency": "EUR", "framework": "inflation_targeter",
     "note": "euro from 2009-01-01; ECB policy, national industrial cycle"},
    {"country": "Slovenia", "currency": "EUR", "framework": "inflation_targeter",
     "note": "euro from 2007-01-01; the first of the 2004 entrants to join"},
)

#: The instruments this pack may compile a cell against. Every one is in the broker registry and
#: none is a single-name equity. EURPLN is DELIBERATELY ABSENT: it is the `pl` pack's ground and
#: appears here only as a neighbour control inside CEE-HU-D.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "EURCZK", "USDCZK",                                # the koruna: floor, exit, published path
    "EURHUF", "USDHUF", "CHFHUF", "GBPHUF", "AUDHUF", "NZDHUF",   # the forint and its carry legs
    "EURCHF",                                          # the funding leg of the CHF mortgage book
    "WHEAT", "CORN", "SOYBEAN",                        # Constanta, the Danube, the Black Sea
    "XNGUSD", "XBRUSD",                                # TurkStream, Krk, Druzhba
    "GER40", "EUSTX50",                                # the chain the region is a tier of
    "EURUSD",                                          # the accession and convergence leg
)

TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "EUR/RON and USD/RON", "venue": "Bucharest interbank / NBR reference",
     "why": "the administered leu itself; the NBR's near-crawl is the mechanism of CEE-RO-A and "
            "the broker quotes no RON, so the suppression is read against the unmanaged siblings",
     "proxies": ("EURHUF", "EURCZK", "WHEAT")},
    {"name": "EUR/BGN (the currency-board rate 1.95583)", "venue": "BNB / Sofia interbank",
     "why": "a board rate has no variance by construction; what moves is the SPREAD of Bulgarian "
            "assets to the euro and the accession clock around it",
     "proxies": ("EURUSD", "EURHUF")},
    {"name": "EUR/RSD (the National Bank of Serbia's managed dinar)", "venue": "Belgrade interbank",
     "why": "the NBS holds it in a corridor of a few hundredths; the Balkan risk premium shows up "
            "in the reserve draw and the CDS instead of in the rate",
     "proxies": ("EURHUF", "EUSTX50")},
    {"name": "PX (Prague), BUX (Budapest), BET (Bucharest), SOFIX, CROBEX and BELEX15",
     "venue": "PSE, BSE, BVB, BSE-Sofia, ZSE, Belgrade SE",
     "why": "no CEE index CFD is quoted; the regional equity beta is read through EUSTX50 and "
            "GER40 and the national indices are targets",
     "proxies": ("EUSTX50", "GER40")},
    {"name": "Czech and Hungarian government bond curves (CZGB, MAK/ÁKK)",
     "venue": "Prague and Budapest primary dealers",
     "why": "the rate path a policy surprise actually moves; the FX leg is the executable one",
     "proxies": ("EURCZK", "EURHUF")},
    {"name": "Hungarian, Romanian, Bulgarian and Serbian Eurobonds and 5-year CDS",
     "venue": "OTC",
     "why": "the sovereign-stress channel of the EU conditionality dispute and of the Balkan "
            "flashpoints; the maturity calendar is a forced-flow clock",
     "proxies": ("EURHUF", "EUSTX50", "EURUSD")},
    {"name": "CEGH (Baumgarten), MGP and the Bulgarian and Romanian gas balancing points",
     "venue": "CEGH / BRM / Bulgarian Gas Hub",
     "why": "the price the TurkStream and Krk flows actually settle against; XNGUSD is Henry Hub "
            "and is a weak proxy, which every gas edge in this pack says out loud",
     "proxies": ("XNGUSD", "XBRUSD")},
    {"name": "HUPX, OPCOM, IBEX and OTE day-ahead power", "venue": "the CEE power exchanges",
     "why": "the industrial cost shock of 2022 landed here first; the aluminium and steel tiers "
            "of the German chain cut output against these prices",
     "proxies": ("XNGUSD", "GER40")},
    {"name": "Danube barge freight and the Constanta grain basis",
     "venue": "Danube Commission gauges / Constanta traders",
     "why": "the physical cost of moving Romanian, Bulgarian and Ukrainian grain to the Black Sea; "
            "a low-water clock is a supply-side event with no financial instrument on this box",
     "proxies": ("WHEAT", "CORN")},
    {"name": "Skoda, Audi Gyor, Kia Zilina and the CEE automotive production series",
     "venue": "AutoSAP, ZAP SR, the national statistics offices",
     "why": "the region's export in one number; a single-name equity is EVENT-lane by the "
            "two-lane order, so production volumes reach the book through GER40 and EUSTX50",
     "proxies": ("GER40", "EUSTX50")},
)

# --------------------------------------------------------------------------- the central bank
#: THE FRAMEWORK HAS ONE CENTRAL-BANK SLOT AND THIS REGION HAS EIGHT MONETARY AUTHORITIES. The
#: slot is given to the CNB because it is the one with a published rate path, a published fan
#: chart and a dated regime break, and because EURCZK is the cleanest policy tape here. The MNB
#: is carried at equal depth in `MNB` below and its dates drive their own miner; the other six
#: are in `OTHER_CENTRAL_BANKS`. Nothing about this region is inferred from the Czech row.
CENTRAL_BANK: dict[str, Any] = {
    "name": "Ceska narodni banka -- the Bank Board (CNB)",
    "short": "CNB",
    "framework": "inflation_targeter",
    "committee": "the seven-member Bank Board: the Governor, two Deputy Governors and four "
                 "further members, all appointed by the President for six-year terms",
    "policy_instrument": "the two-week repo rate (dvoutydenni repo sazba), with the discount and "
                         "Lombard rates as the corridor floor and ceiling",
    "mandate": "price stability under the Czech constitution and the CNB Act; a 2% inflation "
               "target with a +/-1pp tolerance band, measured on the CZSO's CPI",
    "decision_rule": "EIGHT scheduled monetary Bank Board meetings a year on a schedule published "
                     "the previous year; the decision is announced at 14:30 Prague, the press "
                     "conference follows at about 15:45, and the vote split is published the same "
                     "day. FOUR of the eight are FORECAST meetings that publish the Monetary "
                     "Policy Report, the fan chart and the CNB's own implied rate path -- a "
                     "forecast meeting and a non-forecast meeting are not one sample",
    "decision_calendar_rule": "eight meetings a year, published at cnb.cz the preceding autumn; "
                              "the announcement is 14:30 Europe/Prague (CET/CEST), so the UTC "
                              "minute MOVES between 13:30 and 12:30 twice a year",
    "decision_dates": (
        "2024-02-08", "2024-03-20", "2024-05-02", "2024-06-27", "2024-08-01", "2024-09-25",
        "2024-11-07", "2024-12-19",
        "2025-02-06", "2025-03-26", "2025-05-07", "2025-06-25", "2025-08-06", "2025-09-25",
        "2025-11-06", "2025-12-17"),
    "forecast_meetings": ("2024-02-08", "2024-05-02", "2024-08-01", "2024-11-07",
                          "2025-02-06", "2025-05-07", "2025-08-06", "2025-11-06"),
    "dates_status": "2024: the eight monetary meetings as held (the cutting cycle from 6.75% to "
                    "4.00%); 2025: the schedule as published by the CNB, re-verify each date "
                    "against the press release before a cell is compiled on it; 2026: NOT LISTED "
                    "-- the pack refuses to invent a calendar it has not read",
    "decision_time_utc": "13:30",
    "announce_local": "14:30 Europe/Prague; press conference about 15:45; vote split same day",
    "dst_rule": "Prague is CET (UTC+1) in winter and CEST (UTC+2) in summer, switching on the "
                "last Sundays of March and October with the rest of the EU; a decision study "
                "keyed to a fixed UTC hour measures an ordinary minute for seven months a year",
    "minutes_lag_days": 8,
    "publication_classes": ("monetary_policy_decision", "monetary_policy_report", "fan_chart",
                            "implied_rate_path", "minutes_with_vote_split", "fx_intervention_data",
                            "financial_stability_report"),
    "policy_rate_series": "CNB:repo_2w",
    "expected_rate_series": "CNB:implied_path",
    "consensus_proxy": "the CNB's OWN published rate path from the most recent forecast meeting, "
                       "plus the FRA curve and the Reuters/Bloomberg analyst polls between them",
    "consensus_proxy_trap": "the published path is conditional on the forecast's assumptions and "
                            "the Board votes against it often; a surprise measured against the "
                            "path is not the same quantity as a surprise against a survey and "
                            "the two must never be pooled",
    "intervention_history": "unlimited one-sided intervention to defend EUR/CZK >= 27.00 from "
                            "2013-11-07 to 2017-04-06; discretionary koruna-supporting sales in "
                            "2022 announced at the 2022-05-12 meeting",
    "off_cycle": ("2017-04-06 extraordinary meeting: the exchange-rate commitment exited",
                  "2020-03-16, 2020-03-26 and 2020-05-07 pandemic cuts, two of them unscheduled"),
    "root": "https://www.cnb.cz",
}

#: THE MNB AT EQUAL DEPTH. Twelve rate-setting Monetary Council meetings a year, plus the
#: 2022-2023 quick-tender era that ran BESIDE them at a different hour of the day.
MNB: dict[str, Any] = {
    "name": "Magyar Nemzeti Bank -- the Monetary Council (Monetaris Tanacs)",
    "short": "MNB",
    "framework": "inflation_targeter",
    "committee": "the Governor, the Deputy Governors and the externally elected members; "
                 "rate-setting meetings are monthly and non-rate-setting meetings sit between",
    "policy_instrument": "the base rate (alapkamat) plus, in stress, the overnight corridor and "
                         "the one-day deposit quick tender (egynapos beteti gyorstender)",
    "mandate": "a 3% inflation target with a +/-1pp tolerance band; price stability first, then "
               "financial stability, then the government's economic policy",
    "decision_rule": "twelve rate-setting meetings a year, normally the fourth Tuesday of the "
                     "month; the decision is published at 14:00 Budapest and the Deputy "
                     "Governor's briefing follows at 15:00; the minutes come two weeks later",
    "decision_dates": (
        "2024-01-30", "2024-02-27", "2024-03-26", "2024-04-23", "2024-05-21", "2024-06-18",
        "2024-07-23", "2024-08-27", "2024-09-24", "2024-10-22", "2024-11-19", "2024-12-17",
        "2025-01-28", "2025-02-25", "2025-03-25", "2025-04-29", "2025-05-27", "2025-06-24",
        "2025-07-22", "2025-08-26", "2025-09-23", "2025-10-21", "2025-11-18", "2025-12-16"),
    "dates_status": "the published rate-setting schedule as read from mnb.hu; the fourth-Tuesday "
                    "rule reproduces it but is NOT a substitute for the published list, and 2026 "
                    "is deliberately not listed",
    "decision_time_utc": "13:00",
    "announce_local": "14:00 Europe/Budapest; briefing 15:00; minutes two weeks later",
    "dst_rule": "Budapest is CET/CEST on the EU switch dates, so the UTC minute is 13:00 in "
                "winter and 12:00 in summer -- the same trap as Prague and one hour apart from "
                "neither, because the two capitals share the zone",
    "quick_tender_era": "2022-10-14 to 2023-09-26: a ONE-DAY DEPOSIT QUICK TENDER at 18% run "
                        "beside a 13% base rate, allotted at about 14:00 Budapest on the tender "
                        "day. For eleven months the effective policy rate was the tender rate, "
                        "not the base rate, and the two were cut back into line in steps from "
                        "2023-05-23 until they met at 13% on 2023-09-26",
    "policy_rate_series": "MNB:base_rate",
    "effective_rate_series": "MNB:one_day_deposit",
    "root": "https://www.mnb.hu",
}

OTHER_CENTRAL_BANKS: tuple[dict[str, Any], ...] = (
    {"name": "Banca Nationala a Romaniei (BNR)", "country": "Romania",
     "framework": "managed_float", "instrument": "the monetary policy rate plus the interbank "
                                                 "liquidity it rations and the FX it sells",
     "rule": "eight scheduled Board meetings a year; the FX policy is never announced",
     "root": "https://www.bnr.ro"},
    {"name": "Balgarska narodna banka (BNB)", "country": "Bulgaria", "framework": "peg",
     "instrument": "none -- a currency board has no policy rate; the base rate is a published "
                   "reference derived from the interbank market",
     "rule": "the board fixes BGN at 1.95583 to the euro; euro entry dated 2026-01-01",
     "root": "https://www.bnb.bg"},
    {"name": "Hrvatska narodna banka (HNB)", "country": "Croatia",
     "framework": "inflation_targeter",
     "instrument": "none of its own since 2023-01-01: the ECB sets the rate and the HNB is a "
                   "Eurosystem national central bank",
     "rule": "before 2023 a tightly managed kuna float defended by FX interventions",
     "root": "https://www.hnb.hr"},
    {"name": "Narodna banka Srbije (NBS)", "country": "Serbia", "framework": "managed_float",
     "instrument": "the key policy rate and near-daily interventions in the EUR/RSD market",
     "rule": "monthly Executive Board meetings; the dinar is held within a few hundredths",
     "root": "https://www.nbs.rs"},
    {"name": "Narodna banka Slovenska (NBS-SK)", "country": "Slovakia",
     "framework": "inflation_targeter",
     "instrument": "none of its own; a Eurosystem national central bank since 2009-01-01",
     "rule": "the Governor sits on the ECB Governing Council", "root": "https://nbs.sk"},
    {"name": "Banka Slovenije (BSI)", "country": "Slovenia", "framework": "inflation_targeter",
     "instrument": "none of its own; a Eurosystem national central bank since 2007-01-01",
     "rule": "the Governor sits on the ECB Governing Council", "root": "https://www.bsi.si"},
)

# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "ECB euro foreign exchange reference rates (the CZK, HUF, RON and BGN legs)",
     "local": "concertation at 14:10-14:15 Europe/Frankfurt, published about 16:00",
     "time_utc": "13:15", "time_utc_dst": "12:15", "dst_rule": "CET/CEST, EU switch dates",
     "instruments": ("EURCZK", "EURHUF", "EURUSD"), "window_minutes": 20,
     "why": "the benchmark every CEE index, fund NAV and EU accounting entry in this region is "
            "struck against; the single most-referenced minute in the regional day"},
    {"name": "CNB daily exchange-rate declaration (kurz devizoveho trhu)",
     "local": "fixed at 14:30 Europe/Prague and published within fifteen minutes",
     "time_utc": "13:30", "time_utc_dst": "12:30", "dst_rule": "CET/CEST",
     "instruments": ("EURCZK", "USDCZK"), "window_minutes": 30,
     "why": "the official koruna rate for tax, customs and accounting, struck in the SAME minute "
            "as the Bank Board decision on the eight meeting days -- which is why a decision "
            "study on EURCZK must separate the fixing effect from the policy effect"},
    {"name": "MNB official exchange rate (hivatalos devizaarfolyam)",
     "local": "fixed on the 11:00 Europe/Budapest interbank quotes and published at once",
     "time_utc": "10:00", "time_utc_dst": "09:00", "dst_rule": "CET/CEST",
     "instruments": ("EURHUF", "USDHUF", "CHFHUF"), "window_minutes": 30,
     "why": "the rate the converted CHF mortgage book, the state debt and every Hungarian "
            "balance sheet are revalued at; the CHFHUF leg is the politically reflexive one"},
    {"name": "BNR daily reference rate (cursul de schimb de referinta)",
     "local": "set on the 12:30-13:00 Europe/Bucharest interbank window, published at 13:00",
     "time_utc": "11:00", "time_utc_dst": "10:00", "dst_rule": "EET/EEST, EU switch dates",
     "instruments": ("EURHUF", "EURCZK"), "window_minutes": 30,
     "why": "the leu's managed print; RON is absent from this broker, so the observable is the "
            "reference rate's own step pattern read against the unmanaged siblings"},
    {"name": "BNB daily rate under the currency board",
     "local": "published each morning Europe/Sofia; the EUR leg is fixed by law at 1.95583",
     "time_utc": "13:00", "time_utc_dst": "12:00", "dst_rule": "EET/EEST",
     "instruments": ("EURUSD",), "window_minutes": 60,
     "why": "the only thing that moves in a board rate is the USD cross, which is EURUSD by "
            "construction; a BGN 'FX move' is an EURUSD move wearing a Bulgarian hat"},
    {"name": "WM/Refinitiv 16:00 London fix on the CEE crosses",
     "local": "16:00 Europe/London, a five-minute window either side",
     "time_utc": "16:00", "time_utc_dst": "15:00", "dst_rule": "GMT/BST, UK switch dates",
     "instruments": ("EURHUF", "EURCZK", "CHFHUF"), "window_minutes": 10,
     "why": "the index and benchmark fix the regional EM funds rebalance against; month-end is "
            "where the CEE crosses carry their largest scheduled flow"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "CNB two-week repo tender maturity ladder", "kind": "weekday", "weekday": 3,
     "roll": "previous", "window_utc": ("08:00", "10:00"), "instruments": ("EURCZK",),
     "why": "the 2W repo is the policy instrument itself; its fortnightly maturities land on the "
            "same weekday and are the koruna money market's largest scheduled liquidity event"},
    {"name": "AKK Hungarian government bond and discount bill auctions", "kind": "weekday",
     "weekday": 3, "roll": "previous", "window_utc": ("09:00", "11:00"),
     "instruments": ("EURHUF", "USDHUF"),
     "why": "bonds on Thursday, bills on Tuesday, settlement T+2; a failed or cut auction in a "
            "conditionality episode is the forint's fastest domestic stress print"},
    {"name": "Month-end index and EM fund rebalancing on the CEE crosses", "kind": "month_end",
     "roll": "previous", "window_utc": ("14:00", "17:00"),
     "instruments": ("EURHUF", "EURCZK", "EUSTX50"),
     "why": "the 16:00 London fix on the last business day carries the scheduled regional flow"},
    {"name": "Quarter-end EU cohesion and RRF disbursement test dates", "kind": "quarter_end",
     "roll": "previous", "window_utc": ("08:00", "16:00"), "instruments": ("EURHUF",),
     "why": "the Commission pays against dated milestones; a withheld quarter is a forint event"},
    {"name": "Gas month-ahead contract expiry on the Balkan routes", "kind": "month_end",
     "roll": "previous", "window_utc": ("10:00", "16:00"), "instruments": ("XNGUSD", "XBRUSD"),
     "why": "the TurkStream and Krk nominations are month-ahead products; the last business day "
            "is where the transit and storage decisions are made public"},
    {"name": "Calendar year end: the accession, conversion and tariff switch date",
     "kind": "fiscal_year_end", "roll": "previous", "window_utc": ("08:00", "16:00"),
     "instruments": ("EURUSD", "EURHUF", "EURCZK"),
     "why": "Slovenia 2007, Slovakia 2009, Croatia 2023 and Bulgaria 2026 all entered the euro on "
            "1 January, and the region's regulated energy tariffs reset on the same date"},
)

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Burza cennych papiru Praha (Prague Stock Exchange) -- PX",
     "index_symbols": (),
     "open_local": "09:00 (pre-open 08:00)", "close_local": "16:20 (closing auction to 16:30)",
     "open_utc": "07:00", "close_utc": "14:30", "dst_rule": "CET/CEST",
     "auction": "opening call 08:00-09:00; closing auction 16:20-16:30",
     "expiry_rule": "no liquid listed derivatives; the PX futures line is dormant",
     "holidays": "the Czech state-holiday calendar; the exchange also closes 24 and 31 December",
     "notes": "NO CFD IS QUOTED on the PX, so the index is a transmission target; the exchange "
              "matters here because its two heavyweight listings are a bank and a utility whose "
              "dividend calendar moves the koruna money market"},
    {"name": "Budapesti Ertektozsde (Budapest Stock Exchange) -- BUX", "index_symbols": (),
     "open_local": "09:00", "close_local": "17:00 (closing auction to 17:05)",
     "open_utc": "07:00", "close_utc": "15:05", "dst_rule": "CET/CEST",
     "auction": "opening call 08:30-09:00; closing auction 17:00-17:05",
     "expiry_rule": "BUX futures expire on the third Friday of the contract month",
     "holidays": "the Hungarian state-holiday calendar, including the March, August and October "
                 "national days no other market in Europe closes for",
     "notes": "owned by the MNB since 2015, which is its own research object: the central bank "
              "owns the exchange whose listed banks it supervises"},
    {"name": "Bursa de Valori Bucuresti (BVB) -- BET", "index_symbols": (),
     "open_local": "10:00", "close_local": "17:45 (closing auction to 18:00)",
     "open_utc": "08:00", "close_utc": "16:00", "dst_rule": "EET/EEST",
     "auction": "opening call 09:45-10:00; closing auction 17:45-18:00",
     "expiry_rule": "SIBEX derivatives are gone; no liquid listed expiry remains",
     "holidays": "the Romanian calendar, which follows the ORTHODOX Easter and therefore closes "
                 "on days Prague, Budapest and Zagreb are open",
     "notes": "promoted to FTSE Secondary Emerging in September 2020, which is the dated flow "
              "event CEE-RO-A conditions on"},
    {"name": "Zagrebacka burza (Zagreb SE) and the Belgrade and Sofia exchanges",
     "index_symbols": (), "open_local": "09:00", "close_local": "16:00",
     "open_utc": "07:00", "close_utc": "14:00", "dst_rule": "CET/CEST (Sofia EET/EEST)",
     "auction": "opening and closing calls at both ends of the session",
     "expiry_rule": "none listed and liquid",
     "holidays": "Croatian, Serbian and Bulgarian national calendars, three different Easters "
                 "between them in any year the Orthodox and Western feasts diverge",
     "notes": "CROBEX, BELEX15 and SOFIX are small and illiquid; they are carried for the "
              "calendar asymmetry they prove, not for a tradeable signal"},
)

SESSION_WINDOWS: tuple[dict[str, Any], ...] = (
    {"name": "cee_morning_fix", "start_utc": "08:00", "end_utc": "10:00",
     "notes": "the MNB's 11:00 Budapest official fixing and the CEE cash opens; the thinnest "
              "liquidity of the regional day sits just before it"},
    {"name": "cee_ecb_concertation", "start_utc": "12:00", "end_utc": "13:30",
     "notes": "the ECB reference-rate window; the CNB's 14:30 Prague declaration sits inside it "
              "in summer and just after it in winter"},
    {"name": "cee_policy_announcement", "start_utc": "12:00", "end_utc": "15:00",
     "notes": "the CNB at 14:30 Prague and the MNB at 14:00 Budapest, one hour apart in the same "
              "zone; the two press conferences overlap and their statements cross-quote"},
    {"name": "cee_london_close", "start_utc": "15:00", "end_utc": "16:30",
     "notes": "the 16:00 London fix, where the regional EM funds rebalance the HUF and CZK legs"},
)

RELEASE_CLASSES: tuple[dict[str, Any], ...] = (
    {"name": "CZSO flash consumer price index (Czechia)", "cadence": "monthly",
     "time_utc": "08:00", "source": "Cesky statisticky urad", "actual_series": "CZSO:cpi",
     "expected_series": "UNMEASURED",
     "notes": "about the 10th at 09:00 Prague; the CNB's target is measured on this print and "
              "the Board's own forecast for it is public, so the surprise is two-sided"},
    {"name": "KSH consumer price index (Hungary)", "cadence": "monthly", "time_utc": "07:30",
     "source": "Kozponti Statisztikai Hivatal", "actual_series": "KSH:cpi",
     "expected_series": "UNMEASURED",
     "notes": "08:30 Budapest, typically the 8th-11th; the MNB's 3% target band is measured here "
              "and the food-price cap episodes of 2022-23 distorted the basket deliberately"},
    {"name": "INSSE and NSI consumer prices (Romania, Bulgaria)", "cadence": "monthly",
     "time_utc": "08:00", "source": "INSSE / NSI", "actual_series": "INSSE:cpi",
     "expected_series": "UNMEASURED",
     "notes": "Romania about the 12th, Bulgaria about the 15th; the Bulgarian print is the "
              "convergence criterion the ECB's report measures accession against"},
    {"name": "CNB Monetary Policy Report with the fan chart and the implied rate path",
     "cadence": "quarterly", "time_utc": "13:00", "source": "CNB",
     "actual_series": "CNB:implied_path", "expected_series": "n/a",
     "notes": "published at the four FORECAST meetings; the fan chart and the path are the "
              "expectation object CEE-CZ-A measures surprises against"},
    {"name": "MNB Inflation Report and the quarterly forecast", "cadence": "quarterly",
     "time_utc": "08:00", "source": "MNB", "actual_series": "MNB:forecast",
     "expected_series": "n/a",
     "notes": "four a year, a few days after the rate decision it belongs to"},
    {"name": "Eurostat HICP flash and the national industrial production prints",
     "cadence": "monthly", "time_utc": "09:00", "source": "Eurostat", "actual_series": "ESTAT:hicp",
     "expected_series": "UNMEASURED",
     "notes": "the harmonised series the convergence criteria are measured on; the industrial "
              "production line is where the German order book shows up in CEE data"},
    {"name": "ENTSOG physical gas flows and the Bulgarian and Serbian transit nominations",
     "cadence": "daily", "time_utc": "05:00", "source": "ENTSOG / Bulgartransgaz / Srbijagas",
     "actual_series": "ENTSOG:physical_flow", "expected_series": "n/a",
     "notes": "day-ahead nominations and day-after physical flows; the 2022 cut-offs and the "
              "2023 Bulgarian transit fee are step changes in this series"},
    {"name": "Constanta port throughput and the Danube water-level gauges", "cadence": "monthly",
     "time_utc": "10:00", "source": "Port of Constanta / the Danube Commission gauges",
     "actual_series": "CONSTANTA:grain_throughput", "expected_series": "n/a",
     "notes": "the grain line is published monthly; the gauges are daily and the draught "
              "restriction is the binding constraint, not the water level itself"},
    {"name": "EC convergence report and the Council's euro-accession decisions",
     "cadence": "quarterly", "time_utc": "UNMEASURED",
     "source": "European Commission / ECB / ECOFIN",
     "actual_series": "EC:convergence_report", "expected_series": "n/a",
     "notes": "the biennial report plus any ad-hoc one a candidate requests; the Council decision "
              "and the conversion-rate regulation are two separate dated events"},
)

# --------------------------------------------------------------------------- holidays
#: THE EIGHT JURISDICTIONS THIS PACK CLOSES FOR. They are not one calendar and must never be
#: merged into one: the whole point of the region is that Prague, Budapest, Bucharest, Sofia,
#: Zagreb, Belgrade, Bratislava and Ljubljana are shut on DIFFERENT days, and the days one is
#: shut while the others trade are the only sessions a liquidity study can use.
JURISDICTIONS: tuple[str, ...] = ("cz", "hu", "ro", "bg", "hr", "rs", "sk", "si")

#: THE CALENDAR SPLIT THAT MAKES THIS REGION WORTH MINING. Czechia, Hungary, Croatia, Slovakia
#: and Slovenia keep the WESTERN (Gregorian) computus; Romania, Bulgaria and Serbia keep the
#: JULIAN one used by the Orthodox churches. The two coincide in some years and diverge by one,
#: four or five weeks in others -- 2024 diverged by five weeks, 2025 coincided exactly, 2026
#: diverges by one. In a divergence year Bucharest, Sofia and Belgrade are closed on days
#: Prague, Budapest and Zagreb are open, and the reverse, and that asymmetry is dateable years
#: ahead from two arithmetic rules with no table at all.
EASTER_RITE: dict[str, str] = {"cz": "western", "hu": "western", "hr": "western",
                               "sk": "western", "si": "western",
                               "ro": "orthodox", "bg": "orthodox", "rs": "orthodox"}

#: Jurisdictions whose law moves a weekend holiday to the next working day. Bulgaria and Serbia
#: substitute; Czechia, Hungary, Croatia, Slovakia, Slovenia and Romania do not, so a holiday on
#: a Saturday there simply costs the market nothing -- which is itself a fact a study must carry.
SUBSTITUTES: frozenset[str] = frozenset({"bg", "rs"})

FIXED_HOLIDAYS: dict[str, tuple[tuple[int, int, str], ...]] = {
    "cz": ((1, 1, "Den obnovy samostatného českého státu / Nový rok"),
           (5, 1, "Svátek práce"), (5, 8, "Den vítězství"),
           (7, 5, "Den slovanských věrozvěstů Cyrila a Metoděje"),
           (7, 6, "Den upálení mistra Jana Husa"),
           (9, 28, "Den české státnosti (svatý Václav)"),
           (10, 28, "Den vzniku samostatného československého státu"),
           (11, 17, "Den boje za svobodu a demokracii"),
           (12, 24, "Štědrý den"), (12, 25, "1. svátek vánoční"), (12, 26, "2. svátek vánoční")),
    "hu": ((1, 1, "Újév"), (3, 15, "Az 1848-as forradalom ünnepe"), (5, 1, "A munka ünnepe"),
           (8, 20, "Az államalapítás ünnepe (Szent István)"),
           (10, 23, "Az 1956-os forradalom ünnepe"), (11, 1, "Mindenszentek"),
           (12, 25, "Karácsony"), (12, 26, "Karácsony másnapja")),
    "ro": ((1, 1, "Anul Nou"), (1, 2, "A doua zi de Anul Nou"),
           (1, 24, "Ziua Unirii Principatelor Române"), (5, 1, "Ziua Muncii"),
           (6, 1, "Ziua Copilului"), (8, 15, "Adormirea Maicii Domnului"),
           (11, 30, "Sfântul Andrei"), (12, 1, "Ziua Națională a României"),
           (12, 25, "Crăciunul"), (12, 26, "A doua zi de Crăciun")),
    "bg": ((1, 1, "Нова година"), (3, 3, "Ден на Освобождението на България"),
           (5, 1, "Ден на труда"),
           (5, 6, "Гергьовден — Ден на храбростта и Българската армия"),
           (5, 24, "Ден на светите братя Кирил и Методий"),
           (9, 6, "Ден на Съединението"), (9, 22, "Ден на Независимостта на България"),
           (12, 24, "Бъдни вечер"), (12, 25, "Рождество Христово"),
           (12, 26, "Втори ден на Коледа")),
    "hr": ((1, 1, "Nova godina"), (1, 6, "Bogojavljenje (Sveta tri kralja)"),
           (5, 1, "Praznik rada"), (5, 30, "Dan državnosti"),
           (6, 22, "Dan antifašističke borbe"),
           (8, 5, "Dan pobjede i domovinske zahvalnosti"), (8, 15, "Velika Gospa"),
           (11, 1, "Svi sveti"), (11, 18, "Dan sjećanja na žrtve Domovinskog rata"),
           (12, 25, "Božić"), (12, 26, "Sveti Stjepan")),
    "rs": ((1, 1, "Нова година"), (1, 2, "Нова година — други дан"),
           (1, 7, "Божић (православни)"), (2, 15, "Дан државности — Сретење"),
           (2, 16, "Дан државности — други дан"), (5, 1, "Празник рада"),
           (5, 2, "Празник рада — други дан"),
           (11, 11, "Дан примирја (Први светски рат)")),
    "sk": ((1, 1, "Deň vzniku Slovenskej republiky"), (1, 6, "Zjavenie Pána (Traja králi)"),
           (5, 1, "Sviatok práce"), (5, 8, "Deň víťazstva nad fašizmom"),
           (7, 5, "Sviatok svätého Cyrila a Metoda"), (8, 29, "Výročie SNP"),
           (9, 1, "Deň Ústavy Slovenskej republiky"), (9, 15, "Sedembolestná Panna Mária"),
           (11, 1, "Sviatok všetkých svätých"), (11, 17, "Deň boja za slobodu a demokraciu"),
           (12, 24, "Štedrý deň"), (12, 25, "Prvý sviatok vianočný"),
           (12, 26, "Druhý sviatok vianočný")),
    "si": ((1, 1, "Novo leto"), (1, 2, "Novo leto — drugi dan"), (2, 8, "Prešernov dan"),
           (4, 27, "Dan upora proti okupatorju"), (5, 1, "Praznik dela"),
           (5, 2, "Praznik dela — drugi dan"), (6, 25, "Dan državnosti"),
           (8, 15, "Marijino vnebovzetje"), (10, 31, "Dan reformacije"),
           (11, 1, "Dan spomina na mrtve"), (12, 25, "Božič"),
           (12, 26, "Dan samostojnosti in enotnosti")),
}

#: The moving feasts each jurisdiction closes for, as OFFSETS from its own Easter Sunday. The
#: offsets are declared here and the Sunday is computed, so the table extends to any year.
MOVING_FEASTS: dict[str, tuple[tuple[int, str], ...]] = {
    "cz": ((-2, "Velký pátek"), (1, "Velikonoční pondělí")),
    "hu": ((-2, "Nagypéntek"), (1, "Húsvéthétfő"), (50, "Pünkösdhétfő")),
    "hr": ((0, "Uskrs"), (1, "Uskrsni ponedjeljak"), (60, "Tijelovo")),
    "sk": ((-2, "Veľký piatok"), (1, "Veľkonočný pondelok")),
    "si": ((0, "Velikonočna nedelja"), (1, "Velikonočni ponedeljek"), (49, "Binkoštna nedelja")),
    "ro": ((-2, "Vinerea Mare"), (0, "Paștele"), (1, "A doua zi de Paște"),
           (49, "Rusalii"), (50, "A doua zi de Rusalii")),
    "bg": ((-2, "Разпети петък"), (-1, "Велика събота"), (0, "Великден"),
           (1, "Втори ден на Великден")),
    "rs": ((-2, "Велики петак"), (0, "Васкрс"), (1, "Васкршњи понедељак")),
}

#: ONE-OFF CLOSURES NO RULE PRODUCES, with their status. Hungary's government moves rest days by
#: DECREE every year (áthelyezett pihenőnap: a Friday or a Monday becomes a rest day and a
#: Saturday is worked instead), and the decree is the only authority -- a year whose decree this
#: pack has not read is UNMEASURED, never silently absent.
DECLARED_CLOSURES: dict[date, tuple[str, str, str]] = {
    date(2024, 12, 24): ("hu", "Áthelyezett pihenőnap (karácsonyi hídnap)", "DECREED"),
    date(2025, 5, 2): ("hu", "Áthelyezett pihenőnap (május 1. utáni hídnap)", "DECREED"),
    date(2023, 1, 1): ("hr", "Prvi dan eura — kuna povučena iz optjecaja", "HISTORICAL"),
    date(2026, 1, 1): ("bg", "Първи ден на еврото — левът преминава в евро", "SCHEDULED"),
}


def western_easter(year: int) -> date:
    """Gregorian Easter Sunday by the anonymous computus -- Prague, Budapest, Zagreb,
    Bratislava and Ljubljana. 2024-03-31, 2025-04-20, 2026-04-05."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    li = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * li) // 451
    month, day = divmod(h + li - 7 * m + 114, 31)
    return date(year, month, day + 1)


def orthodox_easter(year: int) -> date:
    """Julian (Orthodox) Easter Sunday expressed in the Gregorian calendar -- Bucharest, Sofia
    and Belgrade. The Julian computus plus the thirteen-day offset that holds for 1900-2099.
    2024-05-05, 2025-04-20 (the coinciding year), 2026-04-12."""
    a, b, c = year % 4, year % 7, year % 19
    d = (19 * c + 15) % 30
    e = (2 * a + 4 * b - d + 34) % 7
    month, day = divmod(d + e + 114, 31)
    return date(year, month, day + 1) + timedelta(days=13)


def easter_for(jurisdiction: str, year: int) -> date:
    """The Easter Sunday THIS jurisdiction keeps. Never assume one rite for the region."""
    rite = EASTER_RITE.get(jurisdiction, "")
    if not rite:
        raise ValueError(f"unknown jurisdiction {jurisdiction!r}; known: {list(JURISDICTIONS)}")
    return orthodox_easter(year) if rite == "orthodox" else western_easter(year)


def easter_divergence_days(year: int) -> int:
    """How many days the Orthodox Easter falls after the Western one. Zero is a coinciding
    year and the natural PLACEBO for every study built on the divergence."""
    return (orthodox_easter(year) - western_easter(year)).days


def _substitute(day: date, taken: set[date]) -> date:
    """Bulgaria's and Serbia's weekend substitution: the next working day not already taken."""
    out = day
    while out.weekday() >= 5 or out in taken:
        out += timedelta(days=1)
    return out


def national_holidays(jurisdiction: str, year: int) -> dict[date, str]:
    """One jurisdiction's statutory closed days for one year: the fixed table, its own Easter's
    moving feasts, the substitution rule where the law has one, and the declared one-offs."""
    if jurisdiction not in FIXED_HOLIDAYS:
        raise ValueError(f"unknown jurisdiction {jurisdiction!r}; known: {list(JURISDICTIONS)}")
    out: dict[date, str] = {}
    for m, d, name in FIXED_HOLIDAYS[jurisdiction]:
        out[date(year, m, d)] = name
    sunday = easter_for(jurisdiction, year)
    moving = {sunday + timedelta(days=offset): name
              for offset, name in MOVING_FEASTS[jurisdiction]}
    if jurisdiction in SUBSTITUTES:
        # THE EASTER BLOCK IS EXEMPT AND THAT IS THE LAW, NOT A SHORTCUT. Кодекс на труда чл.
        # 154 and the Serbian state-holidays act both move a FIXED holiday that falls at the
        # weekend to the next working day, and explicitly do NOT move the Easter days -- the
        # Saturday and Sunday of that block are non-working BY NAME. Substituting them would
        # invent two closures a year that no Bulgarian or Serbian market ever took.
        taken = set(out) | set(moving)
        for day, name in sorted(out.items()):
            if day.weekday() >= 5:
                sub = _substitute(day, taken)
                taken.add(sub)
                out[sub] = f"{name} (substituted)"
    out.update(moving)
    for day, (owner, name, status) in DECLARED_CLOSURES.items():
        if owner == jurisdiction and day.year == year:
            out[day] = f"{name} [{status}]"
    return dict(sorted(out.items()))


def regional_holidays(year: int) -> dict[date, tuple[str, ...]]:
    """Every closed day in the region, mapped to the jurisdictions closed on it.

    The value is a TUPLE because the asymmetry is the object: a day with one entry is a
    one-country closure and therefore a tradeable liquidity event, and a day with eight is a
    regional shutdown that tells a study nothing.
    """
    out: dict[date, list[str]] = {}
    for code in JURISDICTIONS:
        for day, name in national_holidays(code, year).items():
            out.setdefault(day, []).append(f"{code}: {name}")
    return {day: tuple(names) for day, names in sorted(out.items())}


def market_holidays(year: int) -> dict[date, str]:
    """The regional closed-day table on WEEKDAYS only, one line per day.

    A statutory holiday on a Saturday costs the tape nothing in six of these eight
    jurisdictions, so pooling it with a weekday closure would put part of the sample on days the
    market was never open anyway.
    """
    return {day: " | ".join(names)
            for day, names in regional_holidays(year).items() if day.weekday() < 5}


def orthodox_only_days(year: int) -> dict[date, str]:
    """The DIVERGENCE WEEKS: weekdays Romania, Bulgaria or Serbia are closed and no Western-rite
    jurisdiction here is. This is the sample `orthodox_vs_western_easter` mines, and in a
    coinciding year (2025) the Easter half of it is empty, which is the placebo."""
    west: set[date] = set()
    for code in ("cz", "hu", "hr", "sk", "si"):
        west |= set(national_holidays(code, year))
    out: dict[date, str] = {}
    for code in ("ro", "bg", "rs"):
        for day, name in national_holidays(code, year).items():
            if day.weekday() < 5 and day not in west:
                out[day] = f"{code}: {name}"
    return dict(sorted(out.items()))


def western_only_days(year: int) -> dict[date, str]:
    """The mirror image: weekdays a Western-rite jurisdiction is closed and Bucharest, Sofia and
    Belgrade are open. The two samples together are the asymmetry, and either one alone is a
    one-sided study."""
    east: set[date] = set()
    for code in ("ro", "bg", "rs"):
        east |= set(national_holidays(code, year))
    out: dict[date, str] = {}
    for code in ("cz", "hu", "hr", "sk", "si"):
        for day, name in national_holidays(code, year).items():
            if day.weekday() < 5 and day not in east:
                out[day] = f"{code}: {name}"
    return dict(sorted(out.items()))


def is_market_holiday(day: date) -> bool:
    return day in market_holidays(day.year)


def _iso_table(year: int) -> dict[str, str]:
    return {day.isoformat(): name for day, name in market_holidays(year).items()}


HOLIDAYS_RULE: dict[str, Any] = {
    "kind": "computed_from_rules",
    "calendar": "eight national statutory calendars, two Easter computations, one region",
    "authority": "each jurisdiction's own statute: zákoník práce and zákon č. 245/2000 Sb. "
                 "(Czechia), 2012. évi I. törvény and the annual rest-day decree (Hungary), "
                 "Codul muncii art. 139 (Romania), Кодекс на труда чл. 154 (Bulgaria), Zakon o "
                 "blagdanima (Croatia), Zakon o državnim praznicima (Serbia), zákon č. 241/1993 "
                 "Z. z. (Slovakia), Zakon o praznikih in dela prostih dnevih (Slovenia)",
    "years": (2024, 2025, 2026),
    "weekend": "Saturday and Sunday everywhere here; no jurisdiction in this pack trades at the "
               "weekend",
    "rule": "FIXED DAYS are computed from the eight per-jurisdiction tables in FIXED_HOLIDAYS. "
            "MOVING DAYS are computed as offsets from each jurisdiction's OWN Easter Sunday: "
            "Czechia, Hungary, Croatia, Slovakia and Slovenia from the Gregorian computus "
            "(western_easter), Romania, Bulgaria and Serbia from the Julian one shifted thirteen "
            "days (orthodox_easter). The two Easters diverged by 35 days in 2024, COINCIDED on "
            "2025-04-20, and diverge by 7 days in 2026 -- a checkable arithmetic fact, not a "
            "typed table. Bulgaria and Serbia move a weekend holiday to the next working day; "
            "the other six do not, so a Saturday holiday there costs the tape nothing. Hungary's "
            "rest-day rearrangements are DECREED annually and are carried in DECLARED_CLOSURES "
            "with their status; a year whose decree has not been read is UNMEASURED, never "
            "silently absent.",
    "moving_feasts": "Good Friday, Easter Monday, Whit Monday, Corpus Christi and Rusalii, each "
                     "from the rite its own jurisdiction keeps",
    "asymmetries": "orthodox_only_days() and western_only_days() name the weekdays one rite is "
                   "shut and the other is open; in 2024 the two Easters are five weeks apart and "
                   "in 2025 they coincide, which makes 2025 the placebo year",
    "status": "DERIVED_FROM_RULE",
    "verified": "four dates a human can check without this code: Czech statehood day 2026-10-28, "
                "Serbian Orthodox Christmas 2026-01-07, Hungarian Szent István 2026-08-20 and "
                "Bulgarian Liberation Day 2026-03-03",
    "function": "countries.cee_balkans.pack:market_holidays",
    "known_dates": {
        "2024-05-05": "Orthodox Easter Sunday; the Western one was 31 March, five weeks earlier",
        "2025-04-20": "the two Easters COINCIDE; the divergence sample is empty and this year is "
                      "the natural placebo",
        "2026-04-12": "Orthodox Easter Sunday; the Western one was 5 April, one week earlier",
        "2023-01-01": "Croatia adopts the euro at 7.53450 HRK and enters Schengen the same day",
        "2026-01-01": "Bulgaria's scheduled euro entry at the currency-board rate 1.95583",
    },
    "table": {year: _iso_table(year) for year in (2024, 2025, 2026)},
    "fn": market_holidays,
    "national_fn": national_holidays,
    "regional_fn": regional_holidays,
    "orthodox_only_fn": orthodox_only_days,
    "western_only_fn": western_only_days,
}

# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "CNB FX intervention and reserve statistics (the floor era and after)",
     "root": "https://www.cnb.cz/en/financial-markets/foreign-exchange-market/",
     "fields": ("fx_reserves_eur", "monthly_intervention_volume", "reserve_composition"),
     "frequency": "monthly", "snapshot": "month end", "publish_utc": "13:00", "lag_days": 7,
     "licence": "free, public", "available": True,
     "why": "the only published measure of how hard a CEE central bank actually leaned on its "
            "currency; the 2013-2017 reserve build is the floor's cost in one series",
     "pit_warning": "published with a week's lag and revised once; never a same-week conditioner"},
    {"name": "MNB one-day deposit quick-tender allotments (2022-10 to 2023-09)",
     "root": "https://www.mnb.hu/en/monetary-policy/monetary-policy-instruments",
     "fields": ("tender_rate", "allotted_amount", "bid_amount", "bid_to_cover"),
     "frequency": "daily", "snapshot": "tender day", "publish_utc": "13:30", "lag_days": 0,
     "licence": "free, public", "available": True,
     "why": "the allotment is the size of the emergency regime; the bid-to-cover is the banks' "
            "own measure of how binding it was, and both stop dead on 2023-09-26",
     "pit_warning": "the allotment is published AFTER the tender clears, so the same-day window "
                    "is not PIT-safe; the tender ANNOUNCEMENT is"},
    {"name": "Non-resident holdings of Hungarian and Czech government bonds",
     "root": "https://akk.hu/statistics", "fields": ("nonresident_share", "nonresident_stock",
                                                     "domestic_bank_holdings"),
     "frequency": "weekly", "snapshot": "Friday", "publish_utc": "15:00", "lag_days": 4,
     "licence": "free, public", "available": True,
     "why": "the closest thing this region has to a positioning series: foreign ownership of the "
            "local curve is the carry trade's balance-sheet footprint",
     "pit_warning": "four days stale; the weekly change is the usable object, not the level"},
    {"name": "ECB and EBA consolidated banking data on the residual CHF loan stock",
     "root": "https://sdw.ecb.europa.eu", "fields": ("chf_loan_stock", "npl_ratio_by_currency",
                                                     "household_fx_exposure"),
     "frequency": "quarterly", "snapshot": "quarter end", "publish_utc": "09:00", "lag_days": 90,
     "licence": "free, public", "available": True,
     "why": "how much franc exposure is actually left after Hungary's 2015 conversion and "
            "Croatia's rulings; the size of the political reflex CHFHUF carries",
     "pit_warning": "a quarter stale by construction; a conditioner for the era, not the week"},
    {"name": "a CFTC or exchange-traded CZK, HUF, RON or RSD positioning series",
     "root": "", "fields": (), "frequency": "n/a", "snapshot": "", "publish_utc": "",
     "lag_days": 0, "licence": "", "available": False,
     "why": "no CME or ICE contract exists for any currency in this region",
     "pit_warning": "DOES NOT EXIST: CEE FX positioning is UNMEASURED and is never proxied by "
                    "the EUR or PLN COT, which are different currencies with different holders"},
)

# --------------------------------------------------------------------------- terminology
#: NINE LANGUAGES, THREE SCRIPTS AND NO TRANSLATIONS. A crawler asking a Czech board for
#: "interest rate" finds nothing: the word is `úroková sazba` and the instrument is the
#: `dvoutýdenní repo sazba`. A query for "Bulgarian currency board" in English returns analyst
#: commentary; `валутен борд` returns the BNB, the Sofia press and the retail argument about it.
#: Serbian is written in BOTH scripts by the same outlets on the same day, so both are carried:
#: a Cyrillic-only query misses half of Belgrade and a Latin-only query misses the other half.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "CEE-CZ-A": ("úroková sazba", "dvoutýdenní repo sazba", "bankovní rada ČNB",
                 "měnová politika", "inflační cíl", "prognóza ČNB", "vějířový graf",
                 "trajektorie úrokových sazeb", "zasedání bankovní rady",
                 "hlasování bankovní rady", "inflace", "diskontní sazba"),
    "CEE-CZ-B": ("kurzový závazek", "devizové intervence", "ukončení kurzového závazku",
                 "koruna posílila", "27 korun za euro", "opuštění kurzového závazku",
                 "spekulace na posílení koruny", "devizové rezervy ČNB", "oslabení koruny"),
    "CEE-HU-A": ("alapkamat", "Monetáris Tanács", "kamatdöntés", "jegybanki alapkamat",
                 "inflációs cél", "forint árfolyam", "kamatemelés", "kamatvágás", "infláció",
                 "forint"),
    "CEE-HU-B": ("egynapos betéti gyorstender", "effektív kamat", "kamatfolyosó",
                 "overnight betéti kamat", "rendkívüli kamatemelés", "kamatkonvergencia",
                 "gyorstender allokáció", "egynapos betét"),
    "CEE-HU-C": ("kohéziós források", "jogállamisági eljárás", "uniós pénzek befagyasztása",
                 "helyreállítási alap", "feltételességi mechanizmus", "mérföldkövek",
                 "Brüsszel és Budapest vitája", "uniós forrás felfüggesztése"),
    "CEE-HU-D": ("carry trade forint", "kamatkülönbözet", "forintgyengülés", "határidős forint",
                 "spekulatív pozíció", "devizaswap", "forintpiaci likviditás",
                 "külföldi befektetők állampapír-állománya"),
    "CEE-XX-A": ("devizahitel", "forintosítás", "svájci frank alapú hitel", "devizahiteles",
                 "kredit u švicarcima", "konverzija kredita", "kredit u francima",
                 "credite în franci elvețieni", "dužnici u francima", "конверзија кредита",
                 "франак", "švicarski franak"),
    "CEE-RO-A": ("rata dobânzii de politică monetară", "cursul de schimb de referință",
                 "leu", "inflație", "intervenție valutară", "lichiditate interbancară",
                 "ROBOR", "consiliul de administrație al BNR", "deprecierea leului"),
    "CEE-RO-B": ("portul Constanța", "export de grâu", "recolta de porumb", "Dunărea",
                 "nivelul Dunării", "cereale ucrainene", "barje",
                 "adâncimea șenalului navigabil", "culoarele de solidaritate"),
    "CEE-BG-A": ("валутен борд", "основен лихвен процент", "инфлация", "приемане на еврото",
                 "конвергентен доклад", "фиксиран курс", "преминаване към еврото",
                 "Българска народна банка", "лев", "еврозона"),
    "CEE-BG-B": ("Турски поток", "Балкански поток", "транзитна такса", "спиране на газа",
                 "Булгартрансгаз", "газова връзка Гърция-България", "доставки на газ",
                 "природен газ", "Газпром"),
    "CEE-HR-A": ("uvođenje eura", "kuna", "tečaj konverzije", "terminal za ukapljeni plin na Krku",
                 "Plinacro", "inflacija", "Hrvatska narodna banka", "kamatna stopa",
                 "ulazak u europodručje"),
    "CEE-RS-A": ("динар", "инфлација", "каматна стопа", "Народна банка Србије",
                 "интервенција на девизном тржишту", "Косово", "Република Српска",
                 "dinar", "referentna kamatna stopa", "devizne rezerve"),
    "CEE-SK-A": ("úroková sadzba", "automobilový priemysel", "výroba automobilov",
                 "objednávky z Nemecka", "priemyselná výroba", "avtomobilska industrija",
                 "obrestna mera", "výroba áut na obyvateľa", "autoprůmysl", "Škoda Auto",
                 "priemyselná produkcia"),
    "CEE-XX-B": ("státní svátek", "munkaszüneti nap", "áthelyezett pihenőnap",
                 "sărbătoare legală", "Paștele ortodox", "официален празник", "Великден",
                 "Васкрс", "državni praznik", "štátny sviatok", "dela prost dan",
                 "Velký pátek", "Vinerea Mare"),
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
    """A layer this region has nothing in, declared BY NAME with the reason (L1.28a)."""
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
        "cee_cnb", "Ceska narodni banka: decisions, the Monetary Policy Report, the fan chart, "
                   "the implied rate path, the ARAD database and the FX intervention record",
        layer="official",
        roots=("https://www.cnb.cz/cs/menova-politika/br-zapisy-z-jednani/",
               "https://www.cnb.cz/cs/menova-politika/zpravy-o-menove-politice/",
               "https://www.cnb.cz/cnbcz/data/arad/",
               "https://www.cnb.cz/cs/financni-trhy/devizovy-trh/"),
        queries=("dvoutýdenní repo sazba", "zasedání bankovní rady", "prognóza ČNB",
                 "vějířový graf", "trajektorie úrokových sazeb", "kurzový závazek",
                 "devizové intervence", "zápis z jednání bankovní rady", "inflační cíl"),
        languages=("cs", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public (CNB website terms)",
        notes="the only central bank in the region that publishes its OWN rate path, which is "
              "what makes CEE-CZ-A's surprise measurable against something other than a survey; "
              "ARAD carries the floor-era reserve build as a single series"),
    source_class(
        "cee_mnb", "Magyar Nemzeti Bank: Monetary Council decisions and minutes, the base rate, "
                   "the one-day deposit quick-tender allotments, the Inflation Report",
        layer="official",
        roots=("https://www.mnb.hu/monetaris-politika/a-monetaris-tanacs/kozlemenyek",
               "https://www.mnb.hu/monetaris-politika/jegybanki-eszkoztar",
               "https://www.mnb.hu/kiadvanyok/jelentesek/inflacios-jelentes"),
        queries=("alapkamat", "Monetáris Tanács közleménye", "kamatdöntés",
                 "egynapos betéti gyorstender", "kamatfolyosó", "inflációs jelentés",
                 "effektív kamat", "jegybanki eszköztár"),
        languages=("hu", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the quick-tender announcements sit in a DIFFERENT section of the site from the "
              "rate decisions, which is exactly how a study that reads only the decision page "
              "misses the instrument that actually set the price of forint liquidity in 2022-23"),
    source_class(
        "cee_other_central_banks", "BNR, BNB, HNB, NBS Serbia, NBS Slovakia and Banka Slovenije: "
                                   "rates, reference fixings, reserves, financial stability",
        layer="official",
        roots=("https://www.bnr.ro/Home.aspx", "https://www.bnb.bg", "https://www.hnb.hr",
               "https://www.nbs.rs", "https://nbs.sk", "https://www.bsi.si"),
        queries=("rata dobânzii de politică monetară", "cursul de schimb de referință",
                 "валутен борд", "основен лихвен процент", "kamatna stopa",
                 "интервенција на девизном тржишту", "девизне резерве", "úroková sadzba"),
        languages=("ro", "bg", "hr", "sr", "sk", "sl", "en"), access_label="OPEN_DATA",
        credibility="AUTHORITATIVE", predictive_state="UNTESTED", licence="free, public",
        notes="six banks in three monetary regimes; the BNR publishes a reference rate and never "
              "its FX policy, so the STEP PATTERN in the published rate is the only observable "
              "CEE-RO-A has, and the NBS Serbia publishes its intervention volumes monthly"),
    source_class(
        "cee_statistics_offices", "CZSO, KSH, INSSE, NSI, DZS, RZS and SURS: CPI, industrial "
                                  "production, trade, harvest and automotive output",
        layer="official",
        roots=("https://www.czso.cz", "https://www.ksh.hu", "https://insse.ro",
               "https://www.nsi.bg", "https://podaci.dzs.hr", "https://www.stat.gov.rs",
               "https://www.stat.si"),
        queries=("míra inflace", "index spotřebitelských cen", "fogyasztóiár-index",
                 "ipari termelés", "rata anuală a inflației", "producția industrială",
                 "индекс на потребителските цени", "industrijska proizvodnja"),
        languages=("cs", "hu", "ro", "bg", "hr", "sr", "sl", "en"), access_label="OPEN_DATA",
        credibility="AUTHORITATIVE", predictive_state="UNTESTED", licence="free, public",
        notes="the CPI prints the two inflation targets are measured on, and the industrial "
              "production line where a German order-book turn shows up in CEE data six to ten "
              "weeks before it shows up in GER40 earnings"),
    source_class(
        "cee_eu_institutions", "European Commission, ECB and ECOFIN: convergence reports, the "
                               "ERM II decisions, the conditionality mechanism, cohesion and RRF "
                               "milestone decisions", layer="official",
        roots=("https://economy-finance.ec.europa.eu/euro/enlargement-euro-area_en",
               "https://www.ecb.europa.eu/pub/convergence/html/index.en.html",
               "https://commission.europa.eu/strategy-and-policy/eu-budget/protection-eu-budget_en"),
        queries=("convergence report Bulgaria", "ERM II participation", "euro adoption decision",
                 "conditionality mechanism Hungary", "cohesion funds suspension",
                 "recovery and resilience milestones", "конвергентен доклад",
                 "jogállamisági eljárás"),
        languages=("en", "bg", "hu"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the accession clock and the conditionality clock are BOTH dated here and nowhere "
              "else; the Council decision and the conversion-rate regulation are two events "
              "weeks apart and pooling them blends two reactions"),
    # ---- institutional
    source_class(
        "cee_exchanges_and_clearers", "PSE Prague, BSE Budapest, BVB Bucharest, BSE Sofia, ZSE "
                                      "Zagreb, Belgrade SE, plus AKK and the Czech MoF debt desks",
        layer="institutional",
        roots=("https://www.pse.cz", "https://bse.hu", "https://bvb.ro", "https://www.bse-sofia.bg",
               "https://zse.hr", "https://www.belex.rs", "https://akk.hu"),
        queries=("burzovní index PX", "BUX index", "indicele BET", "SOFIX", "CROBEX",
                 "државни записи", "állampapír-aukció", "licitație titluri de stat"),
        languages=("cs", "hu", "ro", "bg", "hr", "sr", "en"), access_label="PUBLIC",
        credibility="AUTHORITATIVE", predictive_state="UNTESTED", licence="free, public",
        notes="none of these indices has a CFD on this broker, so they are transmission targets; "
              "the AUCTION calendars are the usable object, because a cut or failed Hungarian "
              "auction is the forint's fastest domestic stress print"),
    source_class(
        "cee_bank_research", "Erste, Raiffeisen, UniCredit, Komercni banka, OTP, Erste Group CEE "
                             "strategy and the local brokers' published macro notes",
        layer="institutional",
        roots=("https://www.erstegroup.com/en/research", "https://www.rbinternational.com/en/raiffeisen-research.html",
               "https://www.kb.cz/cs/o-bance/ekonomicke-analyzy", "https://www.otpbank.hu/portal/hu/Megtakaritas/Elemzesek"),
        queries=("CEE macro outlook", "CNB preview", "MNB preview", "forint forecast",
                 "koruna forecast", "prognóza kurzu koruny", "forint előrejelzés",
                 "previziuni curs euro leu"),
        languages=("en", "cs", "hu", "ro"), access_label="PUBLIC_WITH_TERMS",
        credibility="RELIABLE", predictive_state="UNTESTED",
        licence="free notes; some behind registration",
        notes="the Austrian and Hungarian banks OWN most of the region's banking systems, so "
              "their CEE research is a participant's view and is kept as the stated consensus "
              "CEE-CZ-A and CEE-HU-A measure a surprise against, never as a view"),
    # ---- academic
    source_class(
        "cee_academic", "CNB Working Paper Series, MNB Working Papers and the Financial and "
                        "Economic Review, CERGE-EI, Corvinus, the Romanian Journal of Economic "
                        "Forecasting, IER Zagreb and the RePEc CEE lists",
        layer="academic",
        roots=("https://www.cnb.cz/en/economic-research/research-publications/cnb-working-paper-series/",
               "https://www.mnb.hu/en/publications/mnb-working-papers",
               "https://hitelintezetiszemle.mnb.hu", "https://www.cerge-ei.cz/publications",
               "https://ideas.repec.org/i/ecee.html"),
        queries=("exchange rate commitment Czech National Bank", "koruna floor exit",
                 "foreign currency mortgages Hungary conversion", "monetary transmission CEE",
                 "Hitelintézeti Szemle devizahitel", "managed float Romania",
                 "currency board Bulgaria euro adoption", "pass-through forint"),
        languages=("en", "cs", "hu"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="open access / publisher terms",
        notes="the CNB's own working papers on the floor exit and the MNB's on the CHF "
              "conversion are the mechanism sources for CEE-CZ-B and CEE-XX-A; they are "
              "hypotheses until the desk reproduces them on its own tape"),
    # ---- practitioner
    source_class(
        "cee_practitioner_press", "Patria.cz, Kurzy.cz, Portfolio.hu, Privatbankar, Profit.ro, "
                                  "ZF Ziarul Financiar, Capital.bg, Lider.hr and Nova Ekonomija",
        layer="practitioner",
        roots=("https://www.patria.cz", "https://www.kurzy.cz", "https://www.portfolio.hu",
               "https://www.profit.ro", "https://www.zf.ro", "https://www.capital.bg",
               "https://lider.media"),
        queries=("ČNB sazby komentář", "koruna vůči euru", "forint árfolyam elemzés",
                 "MNB kamatdöntés elemzés", "curs euro leu analiza", "лихвен процент анализ",
                 "tečaj eura komentar", "carry trade forint"),
        languages=("cs", "hu", "ro", "bg", "hr", "en"), access_label="PUBLIC_WITH_TERMS",
        credibility="RELIABLE", predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="Patria and Portfolio publish the desk-level commentary that dates a positioning "
              "unwind hours before the official statistics do; Portfolio's forint coverage "
              "during the quick-tender era is the closest thing to a tick record of the "
              "two-rate regime that exists outside a terminal"),
    source_class(
        "cee_energy_practitioner", "SeeNews, bne IntelliNews, Balkan Green Energy News, "
                                   "Euractiv's CEE desks and the regional gas-trade newsletters",
        layer="practitioner",
        roots=("https://seenews.com", "https://www.intellinews.com",
               "https://balkangreenenergynews.com", "https://www.euractiv.ro"),
        queries=("TurkStream transit fee", "Balkan Stream capacity", "Krk LNG terminal capacity",
                 "Neptun Deep", "Bulgargaz contract", "gas interconnector Greece Bulgaria",
                 "Турски поток", "Булгартрансгаз транзит"),
        languages=("en", "bg", "ro"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms; some paywalled",
        notes="the Balkan energy press dates the transit and cut-off events CEE-BG-B is built "
              "on; the physical flow series then confirms or refutes each dated claim, which is "
              "the two-source discipline this layer exists for"),
    # ---- retail ecology
    source_class(
        "cee_retail_forums", "Czech and Slovak Patria/Modrastrecha discussion boards, Hungarian "
                             "Portfolio and Privatbankar comment ecologies, Romanian and "
                             "Bulgarian investing forums, the national Reddit and Facebook groups",
        layer="retail_ecology",
        roots=("https://www.reddit.com/r/czech/", "https://www.reddit.com/r/hungary/",
               "https://www.reddit.com/r/Romania/", "https://forum.investo.cz",
               "https://www.facebook.com/groups/tozsdezes"),
        queries=("hypotéka fixace sazba", "devizahitel per", "cum investesc in actiuni",
                 "инвестиране в акции", "kam investovat peníze", "forint gyengülés miért",
                 "mennyi lesz az euró árfolyam"),
        languages=("cs", "hu", "ro", "bg", "sk", "en"), access_label="PUBLIC_SOCIAL",
        credibility="FRINGE", predictive_state="UNTESTED",
        licence="platform terms; public posts only",
        notes="KEPT AT LOW WEIGHT AND NEVER DROPPED: the retail mortgage-rate and FX panic "
              "vocabulary dates the CHF and forint stress episodes CEE-XX-A and CEE-HU-D study, "
              "and a search for it is the only way to see a household balance-sheet event "
              "before it becomes legislation; nothing here is a source of edge"),
    source_class(
        "cee_signal_sellers", "Czech, Hungarian, Romanian and Serbian 'forex signal', prop-firm "
                              "and MT5 EA sellers on YouTube, Telegram and TikTok",
        layer="retail_ecology",
        roots=("https://www.youtube.com/results?search_query=forex+magyarul",
               "https://www.youtube.com/results?search_query=forex+romania+tranzactionare",
               "https://t.me/s/forexbalkan"),
        queries=("forex kereskedés magyarul", "tranzactionare forex romania",
                 "форекс сигнали", "prop firm kihívás", "arany kereskedés", "zlato signály"),
        languages=("hu", "ro", "bg", "cs", "sr"), access_label="PUBLIC_SOCIAL",
        credibility="UNRELIABLE", predictive_state="UNTESTED",
        licence="platform terms; public posts only",
        notes="ESMA-capped retail is the other side of a CEE-cross stop cascade; the EURHUF and "
              "EURCZK stop clusters this ecology advertises are a real microstructure "
              "observable, and the trade ideas in it are not"),
    # ---- app ecosystem
    source_class(
        "cee_broker_and_payment_apps", "Fio e-Broker, Portu, XTB CEE, Patria Finance, OTP "
                                       "eBroker, Tradeville and Revolut penetration, plus the "
                                       "instant-payment systems (AFR Hungary, Czech okamzite "
                                       "platby, Romania's Plati Instant)",
        layer="app_ecosystem",
        roots=("https://www.fio.cz/e-broker", "https://www.portu.cz", "https://www.xtb.com/hu",
               "https://www.mnb.hu/fizetesi-rendszer", "https://www.cnb.cz/cs/platebni-styk/"),
        queries=("azonnali átutalás", "okamžitá platba", "plăți instant", "e-broker poplatky",
                 "befektetési app", "investiční aplikace", "брокер приложение"),
        languages=("cs", "hu", "ro", "bg", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="central bank statistics free; app stores public",
        notes="Hungary's AFR has run 24/7 five-second instant payments since 2020 and Czechia's "
              "since 2018: the region's household FX conversion is a phone transaction with a "
              "published aggregate, which is a retail-flow series most countries do not have"),
    source_class(
        "cee_crypto_cfd_commentary", "Press and app-store coverage of the EUR-stablecoin and "
                                     "crypto-CFD channel in CEE retail, as a household FX proxy",
        layer="app_ecosystem",
        roots=("https://www.portfolio.hu/kereses?q=stablecoin",
               "https://www.patria.cz/hledani.html?q=kryptomeny"),
        queries=("stablecoin árfolyam", "kryptoměny daně", "criptomonede taxe",
                 "криптовалути данъци"),
        languages=("hu", "cs", "ro", "bg"), access_label="PUBLIC_WITH_TERMS",
        credibility="UNRELIABLE", predictive_state="UNTESTED", licence="publisher terms",
        notes="PUBLIC COMMENTARY ONLY: no venue feed, no order book, no crypto exchange named as "
              "a source (mandate 2026-08-18). Carried at low weight as one more read on "
              "household demand for hard currency beside the instant-payment aggregates"),
    # ---- media
    source_class(
        "cee_national_media", "iDNES, Seznam Zpravy, HN.cz, HVG, Telex, Index, HotNews, "
                             "Digi24, Dnevnik.bg, Jutarnji, Vecernji, Blic and Danas",
        layer="media",
        roots=("https://www.idnes.cz/ekonomika", "https://www.seznamzpravy.cz/sekce/ekonomika",
               "https://hvg.hu/gazdasag", "https://telex.hu/gazdasag",
               "https://hotnews.ro/economie", "https://www.dnevnik.bg/biznes/",
               "https://www.jutarnji.hr/biznis", "https://www.blic.rs/biznis"),
        queries=("ČNB snížila sazby", "MNB kamatot emelt", "BNR a majorat dobanda",
                 "БНБ основен лихвен процент", "HNB kamatna stopa", "НБС каматна стопа",
                 "forint történelmi mélyponton", "koruna oslabila"),
        languages=("cs", "hu", "ro", "bg", "hr", "sr"), access_label="PUBLIC_WITH_TERMS",
        credibility="RELIABLE", predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="the broadcast and wire MINUTE is the best public stamp for a CNB or MNB "
              "announcement when the press release carries only a date; HVG and Telex carry the "
              "conditionality dispute in the vocabulary CEE-HU-C's queries are written in"),
    source_class(
        "cee_licensed_terminals", "Bloomberg, LSEG/Refinitiv and the paid CEE data vendors "
                                  "(Portfolio Terminal, Ceska tiskova kancelar wire)",
        layer="media", roots=("https://www.ctk.cz", "https://www.portfolio.hu/terminal"),
        queries=("CTK ekonomicky servis", "Portfolio Terminal adatok"),
        languages=("cs", "hu", "en"), access_label="LICENSED", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="subscription; terms forbid machine extraction",
        machine_use_allowed=False,
        notes="REGISTERED, NEVER SCRAPED: machine_use_allowed=False. The CTK wire carries the "
              "announcement minute the CNB's own PDF does not, and the desk reads only the "
              "public headlines; the intraday CEE tick record is therefore UNMEASURED and says "
              "so rather than being silently absent"),
    # ---- archive
    source_class(
        "cee_archive", "The national gazettes and the pre-accession record: Sbirka zakonu, "
                       "Magyar Kozlony, Monitorul Oficial, Darzhaven vestnik, Narodne novine, "
                       "Sluzbeni glasnik, plus web.archive.org captures of the floor-era CNB "
                       "and the kuna-era HNB",
        layer="archive",
        roots=("https://www.zakonyprolidi.cz", "https://magyarkozlony.hu",
               "https://monitoruloficial.ro", "https://dv.parliament.bg",
               "https://narodne-novine.nn.hr", "https://web.archive.org/web/*/cnb.cz*"),
        queries=("kurzový závazek 2013 prohlášení", "2014. évi LXXVII. törvény forintosítás",
                 "Legea 77/2016 darea in plata", "закон за БНБ валутен борд",
                 "Zakon o konverziji kredita u CHF", "Narodne novine euro uvođenje"),
        languages=("cs", "hu", "ro", "bg", "hr", "sr"), access_label="PUBLIC_ARCHIVE",
        credibility="AUTHORITATIVE", predictive_state="UNTESTED", licence="free, public",
        notes="the CHF conversion laws and the euro conversion-rate regulations are PRIMARY "
              "TEXTS with dates, and they are the only way to pin the exact day a household "
              "balance sheet changed; the Wayback captures of cnb.cz carry the floor-era "
              "statements the current site has reorganised away"),
    # ---- physical economy
    source_class(
        "cee_physical", "Port of Constanta throughput, the Danube Commission and national water "
                        "gauges, ENTSOG physical gas flows, Bulgartransgaz and Transgaz "
                        "nominations, LNG Hrvatska at Krk, and the HUPX/OPCOM/IBEX/OTE power "
                        "exchanges", layer="physical_economy",
        roots=("https://www.portofconstantza.com", "https://www.danubecommission.org",
               "https://www.vizugy.hu", "https://transparency.entsog.eu",
               "https://www.bulgartransgaz.bg", "https://www.lng.hr", "https://hupx.hu",
               "https://www.opcom.ro"),
        queries=("trafic marfuri portul Constanta", "nivelul Dunării cote",
                 "adâncimea șenalului navigabil", "Дунав нива на реката",
                 "транзит на природен газ", "terminal LNG Krk kapacitet",
                 "HUPX day-ahead ár", "preț energie OPCOM"),
        languages=("ro", "bg", "hu", "hr", "en"), access_label="PUBLIC",
        credibility="AUTHORITATIVE", predictive_state="UNTESTED", licence="free, public",
        notes="the DRAUGHT RESTRICTION, not the water level, is the binding constraint on Danube "
              "grain: the gauges are daily and the restriction is announced against them, which "
              "is why CEE-RO-B reads the announcement and treats the level as the covariate"),
    source_class(
        "cee_agriculture_physical", "USDA FAS GAIN for Romania, Bulgaria, Hungary and Serbia, "
                                    "the EU Commission's cereals balance sheets, and the "
                                    "national grain-trade associations",
        layer="physical_economy",
        roots=("https://fas.usda.gov/data/search?f%5B0%5D=country%3A%22Romania%22",
               "https://agriculture.ec.europa.eu/data-and-analysis/markets/overviews/market-observatories/crops_en",
               "https://www.apia.org.ro"),
        queries=("Romania grain and feed annual", "Bulgaria grain and feed", "recolta de grâu",
                 "производство на пшеница", "kukorica termés", "export cereale Constanta"),
        languages=("en", "ro", "bg", "hu"), access_label="OPEN_DATA", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="public domain (US government work) / EU open data",
        notes="Romania and Bulgaria together are a top-five wheat exporter out of the Black Sea "
              "in a good year; the USDA balance and the EU export licences are the counted "
              "quantity WHEAT and CORN actually read"),
    # ---- source graph
    source_class(
        "cee_source_graph", "Who cites whom across the nine layers: the CNB and MNB press "
                            "releases into Patria and Portfolio into iDNES and HVG into the "
                            "retail boards, and the SeeNews/bne chain that carries a Bulgarian "
                            "or Serbian official statement into English",
        layer="source_graph",
        roots=("https://www.patria.cz", "https://www.portfolio.hu", "https://seenews.com",
               "https://www.intellinews.com"),
        queries=("podle ČNB", "az MNB közleménye szerint", "potrivit BNR",
                 "според БНБ", "prema HNB-u", "према НБС", "citing the central bank",
                 "информация от източници"),
        languages=("cs", "hu", "ro", "bg", "hr", "sr", "en"), access_label="PUBLIC",
        credibility="UNKNOWN", predictive_state="UNTESTED",
        licence="derived from the public sources above",
        notes="the attribution phrases are the graph's edges: `podle ČNB` and `az MNB "
              "közleménye szerint` mark a repost, and an unattributed `информация от източници` "
              "in the Bulgarian press a day before a transit-fee decision marks a LEAK -- the "
              "graph is how the desk tells one from the other"),
)

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


# --------------------------------------------------------------------------- datasets
DATASETS: tuple[dict[str, Any], ...] = (
    {"name": "CNB two-week repo rate decisions, vote splits and the implied rate path",
     "source": "Ceska narodni banka", "coverage": "1995 onward; the path from 2008",
     "frequency": "8 per year", "publication_lag_days": 0.0,
     "revisions": "never revised; the path is re-published each forecast round",
     "licence": "free, public", "history_from": "2008-02", "pit_feasible": True,
     "assets": ("EURCZK", "USDCZK", "EUSTX50"),
     "mechanism_families": ("policy_surprise", "event_reaction", "path_revision"),
     "how_to_fetch": "cnb.cz decision pages plus the Monetary Policy Report PDFs; the path is a "
                     "table in the Report and must be read per forecast round, never averaged"},
    {"name": "CNB FX interventions and reserves across the koruna floor",
     "source": "Ceska narodni banka (ARAD)", "coverage": "2010 onward",
     "frequency": "monthly", "publication_lag_days": 7.0, "revisions": "one revision, next month",
     "licence": "free, public", "history_from": "2010-01", "pit_feasible": True,
     "assets": ("EURCZK", "USDCZK"),
     "mechanism_families": ("regime_break", "intervention"),
     "how_to_fetch": "cnb.cz ARAD series for reserves and the monthly intervention volume; the "
                     "2013-11 to 2017-04 build is the floor's cost and the exit is a step"},
    {"name": "MNB base rate, corridor and Monetary Council minutes",
     "source": "Magyar Nemzeti Bank", "coverage": "2001 onward", "frequency": "12 per year",
     "publication_lag_days": 0.0, "revisions": "never", "licence": "free, public",
     "history_from": "2001-06", "pit_feasible": True,
     "assets": ("EURHUF", "USDHUF", "CHFHUF"),
     "mechanism_families": ("policy_surprise", "event_reaction"),
     "how_to_fetch": "mnb.hu Monetary Council communications; the 14:00 Budapest stamp is on the "
                     "release and the minutes follow two weeks later"},
    {"name": "MNB one-day deposit quick-tender rate and allotments (2022-10 to 2023-09)",
     "source": "Magyar Nemzeti Bank", "coverage": "2022-10-14 to 2023-09-26",
     "frequency": "daily within the era", "publication_lag_days": 0.0, "revisions": "never",
     "licence": "free, public", "history_from": "2022-10", "pit_feasible": True,
     "assets": ("EURHUF", "CHFHUF", "GBPHUF"),
     "mechanism_families": ("administered_rate", "regime_break", "two_rate_regime"),
     "how_to_fetch": "mnb.hu monetary policy instruments; the tender ANNOUNCEMENT is PIT-safe "
                     "and the allotment is not, because it publishes after the tender clears"},
    {"name": "BNR daily reference exchange rate and policy rate decisions",
     "source": "Banca Nationala a Romaniei", "coverage": "1999 onward", "frequency": "daily",
     "publication_lag_days": 0.0, "revisions": "never", "licence": "free, public",
     "history_from": "1999-01", "pit_feasible": True, "assets": ("EURHUF", "EURCZK", "WHEAT"),
     "mechanism_families": ("managed_float", "administered_price", "volatility_suppression"),
     "how_to_fetch": "bnr.ro cursBNR daily series; the object is the STEP structure -- long flat "
                     "stretches broken by discrete re-basings -- not the level"},
    {"name": "BNB currency-board balance sheet and the euro-accession documents",
     "source": "Balgarska narodna banka / ECB / European Commission",
     "coverage": "1997 onward; the accession file from 2020-07 ERM II entry",
     "frequency": "weekly balance sheet, per-report accession", "publication_lag_days": 3.0,
     "revisions": "never", "licence": "free, public", "history_from": "1999-01",
     "pit_feasible": True, "assets": ("EURUSD", "EURHUF"),
     "mechanism_families": ("peg_regime", "accession_clock", "convergence"),
     "how_to_fetch": "bnb.bg issue-department balance sheet plus the EC/ECB convergence reports "
                     "and the Council decision and conversion regulation, three dated events"},
    {"name": "Residual Swiss franc household loan stock and the conversion legislation",
     "source": "ECB SDW, national central banks, the national gazettes",
     "coverage": "2004 onward", "frequency": "quarterly", "publication_lag_days": 90.0,
     "revisions": "restated on reclassification", "licence": "free, public",
     "history_from": "2004-03", "pit_feasible": False,
     "assets": ("CHFHUF", "EURCHF"),
     "mechanism_families": ("balance_sheet_channel", "legal_event", "forced_conversion"),
     "how_to_fetch": "ECB SDW MFI loans by currency plus the conversion statutes; PIT IS PARTIAL "
                     "because the stock is a quarter stale, so a cell compiled inside a quarter "
                     "is UNMEASURED and says so"},
    {"name": "Port of Constanta grain throughput and the Danube gauge and draught record",
     "source": "Port of Constanta, the Danube Commission and the national water authorities",
     "coverage": "2015 onward; the solidarity-lane volumes from 2022-05",
     "frequency": "monthly throughput, daily gauges", "publication_lag_days": 20.0,
     "revisions": "cumulative, never restated", "licence": "free, public",
     "history_from": "2015-01", "pit_feasible": True, "assets": ("WHEAT", "CORN", "SOYBEAN"),
     "mechanism_families": ("physical_flow", "logistics_constraint", "export_pace"),
     "how_to_fetch": "portofconstantza.com monthly traffic tables plus the daily gauge "
                     "readings; the DRAUGHT RESTRICTION announcement is the event and the "
                     "level is the covariate"},
    {"name": "ENTSOG physical gas flows through Bulgaria and Serbia, and Krk LNG send-out",
     "source": "ENTSOG transparency platform, Bulgartransgaz, Transgaz, LNG Hrvatska",
     "coverage": "2017 onward", "frequency": "daily", "publication_lag_days": 1.0,
     "revisions": "re-stated once as measured flow replaces nomination",
     "licence": "free, public", "history_from": "2017-01", "pit_feasible": True,
     "assets": ("XNGUSD", "XBRUSD"),
     "mechanism_families": ("physical_flow", "supply_interruption", "transit_politics"),
     "how_to_fetch": "transparency.entsog.eu physical flow points; the 2022-04-27 Bulgarian "
                     "cut-off and the 2023-10 transit fee are step changes visible in one chart"},
    {"name": "CEE automotive production and the German order book",
     "source": "AutoSAP, ZAP SR, KSH, the national statistics offices and VDA",
     "coverage": "2005 onward", "frequency": "monthly", "publication_lag_days": 30.0,
     "revisions": "minor, next month", "licence": "free, public", "history_from": "2005-01",
     "pit_feasible": True, "assets": ("GER40", "EUSTX50", "EURCZK"),
     "mechanism_families": ("supply_chain", "industrial_cycle", "second_derivative"),
     "how_to_fetch": "the national association tables plus the industrial production releases; "
                     "Slovakia's per-capita output is the highest in the world and is the "
                     "cleanest single read on the chain's utilisation"},
    {"name": "EU cohesion and RRF disbursement decisions for Hungary",
     "source": "European Commission / Council", "coverage": "2022-12 onward",
     "frequency": "irregular, dated", "publication_lag_days": 0.0, "revisions": "never",
     "licence": "free, public", "history_from": "2022-12", "pit_feasible": True,
     "assets": ("EURHUF", "USDHUF"),
     "mechanism_families": ("conditionality", "forced_flow_calendar", "political_event"),
     "how_to_fetch": "the Commission's protection-of-the-budget page and the Council decisions; "
                     "the December 2022 suspension and the December 2023 partial release are the "
                     "two anchors of the era"},
    {"name": "National CPI and HICP prints for the eight jurisdictions",
     "source": "CZSO, KSH, INSSE, NSI, DZS, RZS, SURS and Eurostat",
     "coverage": "2000 onward", "frequency": "monthly", "publication_lag_days": 10.0,
     "revisions": "rebasing and seasonal-factor revisions only", "licence": "free, public",
     "history_from": "2000-01", "pit_feasible": True,
     "assets": ("EURCZK", "EURHUF", "EURUSD"),
     "mechanism_families": ("release_surprise", "convergence_criterion"),
     "how_to_fetch": "the national offices for the domestic index and Eurostat for the "
                     "harmonised one; the two differ and the convergence criterion is measured "
                     "on the HARMONISED one, which is the trap in the Bulgarian accession file"},
)

# --------------------------------------------------------------------------- actors
#: EVERY ACTOR NAMES ITS COUNTRY IN ITS OWN NAME. Eight jurisdictions in one pack is exactly how
#: a region becomes a blur, and the cure is that no row here can be read without knowing which
#: state's law forces it.
ACTORS: tuple[dict[str, Any], ...] = (
    {"name": "CZECHIA: the Czech National Bank Bank Board (CNB)",
     "holds": "the two-week repo rate, about EUR 140bn of FX reserves built during the floor, "
              "and the only published central-bank rate path in the region",
     "forced_to": ("decide at eight scheduled meetings a year on a calendar published the "
                   "preceding autumn and announce at 14:30 Prague the same day",
                   "publish a Monetary Policy Report with a fan chart and an implied rate path "
                   "at four of those eight meetings",
                   "publish the vote split on the decision day and the minutes eight days later"),
     "when": "14:30 Europe/Prague on the meeting day (13:30 UTC in winter, 12:30 in summer); the "
             "press conference follows at about 15:45",
     "information": ("the CZSO's CPI before the market at the forecast round",
                     "its own forecast and the Board's votes before publication",
                     "the banks' repo bids in the daily tender"),
     "constraints": ("a 2% target with a +/-1pp band written into its own strategy",
                     "an economy whose exports are one German order book",
                     "reserves so large relative to GDP that their revaluation swings its own "
                     "capital, which constrains how loudly it can talk the koruna"),
     "instruments": ("EURCZK", "USDCZK", "EUSTX50"),
     "counterparties": ("the Czech banks bidding in the 2W repo tender",
                        "the ECB, whose decisions it is measured against",
                        "the exporters who hedge the koruna forward"),
     "observables": ("the decision and its vote split", "the published rate path and the fan "
                     "chart", "the monthly intervention volume in ARAD",
                     "the FRA curve between meetings"),
     "impact": "a decision moves the koruna curve immediately and EURCZK within the minute; the "
               "PATH revision at a forecast meeting moves it more than the rate itself, which "
               "is the mechanism a survey-based surprise measure cannot see",
     "persistence": "the level effect lasts to the next meeting; the path revision persists to "
                    "the next forecast round a quarter later",
     "falsifier": "the decision-day window on EURCZK matches the eight nearest non-meeting "
                  "weekdays, or matches the same window on MNB decision days -- in which case "
                  "the effect is CEE beta or a weekday effect wearing the Bank Board's hat and "
                  "not a Czech policy effect at all",
     "notes": "the 14:30 Prague FIXING is struck in the same minute as the announcement, so a "
              "decision study must separate the two or it is measuring the fix"},
    {"name": "CZECHIA: the CNB's FX desk under the exchange-rate commitment (2013-2017)",
     "holds": "during the commitment, an unlimited one-sided offer to sell koruna at 27.00",
     "forced_to": ("buy euros without limit whenever EUR/CZK traded down to 27.00",
                   "keep doing it for as long as the commitment stood, which meant taking the "
                   "whole speculative inflow onto its own balance sheet in 2016-17",
                   "exit at a meeting, publicly, once it judged the condition met"),
     "when": "2013-11-07 to 2017-04-06; the exit was announced at an extraordinary meeting",
     "information": ("its own reserve accumulation in real time",
                     "the maturity profile of the speculative koruna positions the banks held"),
     "constraints": ("the zero lower bound it was trying to escape",
                     "the size of the inflow, which reached multiples of monthly GDP",
                     "the political cost of a balance sheet that large"),
     "instruments": ("EURCZK", "USDCZK"),
     "counterparties": ("the hedge funds and corporates long koruna against the floor",
                        "the Czech exporters the floor was built for"),
     "observables": ("the monthly intervention volume", "the reserve level",
                     "the distribution of EUR/CZK itself, truncated at 27.00 by construction"),
     "impact": "a truncated distribution: realised volatility collapsed to near zero for three "
               "and a half years and jumped on the exit day; every moment of EURCZK computed "
               "across 2017-04-06 mixes a floored series with a floating one",
     "persistence": "three and a half years, then a step; the post-exit unwind ran for months as "
                    "the long-koruna positions were closed",
     "falsifier": "if EURCZK's realised volatility, skew and kurtosis inside the commitment are "
                  "statistically indistinguishable from the two years before it, then the floor "
                  "was not binding and CEE-CZ-B has no regime to break",
     "notes": "the single cleanest declared regime break available to this desk in any currency"},
    {"name": "HUNGARY: the MNB Monetary Council (Monetaris Tanacs)",
     "holds": "the base rate, the interest-rate corridor and, in stress, the emergency "
              "instruments it may create between meetings",
     "forced_to": ("decide at twelve rate-setting meetings a year and publish at 14:00 Budapest",
                   "publish minutes two weeks later and an Inflation Report quarterly",
                   "defend a 3% target it has missed by more than any other EU inflation "
                   "targeter in the 2021-23 episode"),
     "when": "14:00 Europe/Budapest, normally the fourth Tuesday; briefing at 15:00",
     "information": ("the KSH's CPI before the market",
                     "the banks' forint liquidity position from its own instruments",
                     "the government's fiscal intentions through its own ownership of the "
                     "exchange and its development mandates"),
     "constraints": ("an inflation target it has repeatedly overshot",
                     "a government that disputes tight policy publicly",
                     "a currency whose weakness is a political object, not only a price"),
     "instruments": ("EURHUF", "USDHUF", "CHFHUF", "GBPHUF"),
     "counterparties": ("the Hungarian banks it lends to and takes deposits from",
                        "the non-resident holders of Hungarian government bonds",
                        "the Ministry of Finance and AKK"),
     "observables": ("the decision and the minutes", "the corridor width",
                     "the non-resident bond holding series", "the FRA and BUBOR curve"),
     "impact": "the forint reacts inside the minute and the reaction is asymmetric: a hawkish "
               "surprise in a stress era moves it more than a dovish one of the same size, "
               "because the holders being reassured are leveraged and the ones being disappointed",
     "persistence": "to the next meeting in calm; days in a stress era, where the effective rate "
                    "was set by an instrument the Council did not decide on",
     "falsifier": "the MNB decision-day window on EURHUF matches the CNB decision-day window on "
                  "EURHUF -- a Hungarian decision that moves the forint no more than a Czech one "
                  "does is CEE beta, not Hungarian policy, and the two-country cross-control is "
                  "the whole point of running the samples separately",
     "notes": "the MNB has owned the Budapest Stock Exchange since 2015, which is its own object"},
    {"name": "HUNGARY: the MNB's one-day deposit quick-tender desk (2022-2023)",
     "holds": "during the era, the rate that actually cleared forint overnight liquidity: 18% "
              "against a 13% base rate",
     "forced_to": ("announce and allot the quick tender on the day, at a rate the Council had "
                   "not set at its monthly meeting",
                   "keep the base rate unchanged while doing it, so the two rates diverged in "
                   "public for eleven months",
                   "converge the two back together in steps once the forint stabilised"),
     "when": "2022-10-14 to 2023-09-26; allotments around 14:00 Budapest on the tender day",
     "information": ("the banks' bids, which are a direct read of forint funding stress",
                     "its own FX-market intelligence hours before the market saw it"),
     "constraints": ("a forint that had just traded through 430 to the euro",
                     "the political cost of an explicit 18% base rate",
                     "the need to show the EU and the market two different things at once"),
     "instruments": ("EURHUF", "CHFHUF", "USDHUF"),
     "counterparties": ("the Hungarian banks bidding", "the carry investors the 18% was for"),
     "observables": ("the tender rate and the allotment", "the bid-to-cover",
                     "the gap between the tender rate and the base rate, which IS the regime"),
     "impact": "the forint's reaction function changed shape: the monthly Council meeting stopped "
               "being the event and the daily tender became it, so an event study on the Council "
               "dates over this window is measuring the wrong clock",
     "persistence": "the whole era; the convergence in steps from 2023-05-23 is the unwind and "
                    "each step is its own dated event",
     "falsifier": "if EURHUF's response to Monetary Council dates inside the quick-tender era is "
                  "the same size as its response outside it, the two-rate regime made no "
                  "difference to the reaction function and CEE-HU-B is measuring nothing",
     "notes": "an administered regime measured against ITSELF -- the same country, the same "
              "instrument, eleven months apart, which is a better control than any peer"},
    {"name": "HUNGARY: the government and the European Commission in the conditionality dispute",
     "holds": "between them, roughly EUR 20bn of cohesion and recovery money that is released or "
              "withheld by dated decision",
     "forced_to": ("the Commission: assess milestones and decide, in public, on a calendar",
                   "the government: legislate the judicial and procurement changes the "
                   "milestones name, or forgo the money",
                   "both: act before the de-commitment deadlines that destroy unspent envelopes"),
     "when": "irregular but dated: the December 2022 suspension and the December 2023 partial "
             "release are the two anchors; quarterly milestone assessments between them",
     "information": ("the Commission's own assessment before publication",
                     "the government's legislative timetable"),
     "constraints": ("the EU treaties and the conditionality regulation",
                     "Hungary's veto over unrelated EU files, which is the bargaining chip",
                     "the de-commitment calendar, which is a hard clock"),
     "instruments": ("EURHUF", "USDHUF"),
     "counterparties": ("the non-resident holders of Hungarian bonds",
                        "the other member states whose files Hungary can block"),
     "observables": ("the Council and Commission decisions", "the summit calendar",
                     "the forint's move on summit days", "the non-resident bond holding series"),
     "impact": "a release is a forint rally and a suspension a sell-off, but the size depends on "
               "how much was already priced by the summit calendar, which is public -- so the "
               "surprise is the DECISION against the expectation the calendar created",
     "persistence": "weeks; the fiscal effect is years and the FX effect is not",
     "falsifier": "conditionality-decision windows on EURHUF show no abnormal move against the "
                  "matched weekday control and against the same windows on EURCZK, which has no "
                  "conditionality dispute -- if Prague moves as much as Budapest it is Europe",
     "notes": "the only political-legal clock in this pack that is a genuine forced flow"},
    {"name": "HUNGARY AND CROATIA: the CHF-mortgage households and the banks that lent to them",
     "holds": "before conversion, roughly CHF 15bn of Hungarian and EUR 5bn-equivalent of "
              "Croatian household debt denominated in a currency none of them earned",
     "forced_to": ("service a loan whose principal rises with the franc",
                   "the banks: absorb the conversion losses parliament and the courts imposed "
                   "(Hungary 2014-15 by statute, Croatia 2015 by statute and from 2019 by "
                   "Supreme Court ruling, Serbia 2019 by statute)",
                   "litigate, because the residual claims are still being decided"),
     "when": "the 2015-01-15 franc shock is the trigger; Hungary's conversion settled in the "
             "first months of 2015 and Croatia's litigation is still producing dated rulings",
     "information": ("the banks' own loan books before any regulator publishes them",
                     "the government's legislative intention before it is law"),
     "constraints": ("household solvency, which is a political limit and not an economic one",
                     "the banks' capital, which is mostly Austrian and Italian",
                     "EU consumer-credit law, which the courts keep applying retroactively"),
     "instruments": ("CHFHUF", "EURCHF"),
     "counterparties": ("the Austrian and Italian parent banks",
                        "the national central banks that supplied the FX for the conversion",
                        "the courts"),
     "observables": ("the conversion statutes and the court rulings, all dated",
                     "the residual CHF loan stock in ECB banking data",
                     "the banks' provisions"),
     "impact": "a franc move here is not a safe-haven trade, it is a household balance-sheet "
               "event that produces legislation within months; CHFHUF therefore carries a "
               "political reflex no other CHF cross does",
     "persistence": "the Hungarian stock is gone and the reflex is not: the vocabulary, the "
                    "litigation and the political memory persist and still price the cross",
     "falsifier": "if CHFHUF's behaviour around franc shocks after the 2015 conversion is "
                  "indistinguishable from EURCHF times EURHUF -- that is, if the cross carries "
                  "no residual of its own -- then the political reflex is a story and the "
                  "mechanism is arithmetic",
     "notes": "the conversion statutes in the national gazettes are the primary dated texts"},
    {"name": "ROMANIA: the National Bank of Romania's FX desk (BNR)",
     "holds": "about EUR 60bn of reserves, the interbank liquidity it rations, and an undeclared "
              "band it has never admitted to",
     "forced_to": ("publish a daily reference rate at 13:00 Bucharest whatever it did to get it",
                   "supply euros to keep the leu inside the band it does not name",
                   "re-base the band in discrete steps when the defence becomes too expensive"),
     "when": "daily; the re-basings are irregular and each is its own dated event",
     "information": ("the banks' FX orders it sees before anyone",
                     "the Treasury's foreign-currency issuance calendar"),
     "constraints": ("a twin deficit among the largest in the EU",
                     "an inflation rate that the suppressed currency does not help",
                     "reserves that are finite and a political preference for a stable leu that "
                     "is not"),
     "instruments": ("EURHUF", "EURCZK", "WHEAT"),
     "counterparties": ("the Romanian banks", "the importers and the Treasury",
                        "the foreign investors who price Romanian risk in the bond spread "
                        "instead, because the FX rate will not tell them"),
     "observables": ("the daily reference rate's step structure",
                     "the reserve level", "the interbank ROBOR fixing",
                     "the bond spread, which carries the risk the FX rate is not allowed to"),
     "impact": "EUR/RON realised volatility is an order of magnitude below EURHUF's on the same "
               "days; the risk does not vanish, it MIGRATES to the bond spread and to the "
               "reserve draw, which is where a study must look for it",
     "persistence": "years per band; the re-basings are the punctuation",
     "falsifier": "if EUR/RON's realised volatility conditional on a common CEE risk factor is "
                  "no lower than EURHUF's and EURCZK's on the same days, then the leu is not "
                  "being managed and the whole domain is an artefact of a quiet sample",
     "notes": "RON is absent from this broker, so every reading here is a transmission reading"},
    {"name": "ROMANIA AND BULGARIA: the Constanta grain exporters and the Danube barge operators",
     "holds": "the EU's largest Black Sea grain gateway and the barge capacity that feeds it",
     "forced_to": ("move the Romanian and Bulgarian harvest to the sea before the new crop needs "
                   "the silos",
                   "absorb the Ukrainian solidarity-lane volume when the sea route is closed, "
                   "which at its peak was more grain than Romania's own crop",
                   "cut barge loadings when the Danube's navigable depth falls below the "
                   "draught the authorities allow"),
     "when": "the Romanian and Bulgarian harvest runs late June to August; the low-water season "
             "is late summer to autumn; the Ukrainian transit peaked 2022-2023",
     "information": ("the loading queue and the silo position before any statistic",
                     "the gauge readings, which are public but read by almost nobody"),
     "constraints": ("the navigable depth of the lower Danube, which is weather",
                     "port and rail capacity at Constanta",
                     "the Black Sea war risk premium on the shipping itself"),
     "instruments": ("WHEAT", "CORN", "SOYBEAN"),
     "counterparties": ("the international grain houses", "the Egyptian and North African buyers",
                        "the Ukrainian exporters using the lane"),
     "observables": ("the monthly Constanta throughput", "the daily gauge and draught notices",
                     "the EU export-licence series", "the USDA balance for both countries"),
     "impact": "a draught restriction is a supply-side shock with a known lag: barges that cannot "
               "load do not become vessels three weeks later, and the Black Sea basis widens "
               "before the futures move",
     "persistence": "weeks per low-water episode; a season per harvest",
     "falsifier": "a low-water episode that is NOT followed by a wider Constanta basis and a "
                  "slower export pace within a month refutes the logistics channel; and if the "
                  "same windows move WHEAT in years with no restriction, it is the harvest "
                  "calendar and not the river",
     "notes": "Kaub is the Rhine's gauge and the analogue everyone reaches for; the Danube's own "
              "binding points are the lower reaches between Zimnicea and Calarasi"},
    {"name": "BULGARIA: the BNB currency board and the euro-accession authorities",
     "holds": "a board that has fixed the lev at 1.95583 since 1999 and a scheduled entry date",
     "forced_to": ("back every lev in issue with euro reserves, which means it has no policy "
                   "rate and no discretion at all",
                   "meet the convergence criteria on the HARMONISED inflation measure, not the "
                   "national one",
                   "convert at the board rate on the entry date, which was set by Council "
                   "decision in July 2025 for 1 January 2026"),
     "when": "the board is continuous; the accession events are the ERM II entry (2020-07-10), "
             "the convergence report, the Council decision and the entry date itself",
     "information": ("its own issue-department balance sheet weekly before it publishes",
                     "the Commission's and the ECB's convergence assessments before they "
                     "are laid before the Council"),
     "constraints": ("the board's own arithmetic, which is the constraint",
                     "an inflation criterion measured against the three best performers",
                     "a political system that has had to hold the date through repeated elections"),
     "instruments": ("EURUSD", "EURHUF"),
     "counterparties": ("the Bulgarian banks, mostly foreign-owned",
                        "the ECB and the Commission", "the holders of Bulgarian Eurobonds"),
     "observables": ("the weekly balance sheet", "the HICP print",
                     "the convergence report and the Council decision, two separate dated events",
                     "the Bulgarian bond spread, which converges into the date"),
     "impact": "BGN itself cannot move, so the accession clock prices in the SPREAD and in the "
               "regional convergence trade; the date is known years ahead, which makes the "
               "reaction a slow convergence and not a jump",
     "persistence": "the run-up is years and the entry is a single step",
     "falsifier": "if the Bulgarian spread's convergence into the decision date is no different "
                   "from the Romanian spread's over the same window -- Romania having no date -- "
                   "then the accession clock priced nothing and the domain is decoration",
     "notes": "Croatia's 2023 entry is the natural experiment this one is measured against"},
    {"name": "BULGARIA AND SERBIA: Bulgartransgaz, Srbijagas and the TurkStream transit route",
     "holds": "the pipeline capacity that carries Russian gas into south-east Europe and on to "
              "Hungary, and the transit fees on it",
     "forced_to": ("nominate and deliver against long-term contracts",
                   "stop deliveries when the counterparty refuses the payment terms, which is "
                   "what happened to Bulgaria on 27 April 2022",
                   "set and then withdraw a transit levy under pressure from the neighbours who "
                   "depend on the route, as Bulgaria did in late 2023 and early 2024"),
     "when": "daily nominations; the cut-off and the levy are dated single events",
     "information": ("the nomination book a day ahead",
                     "the contractual terms the public does not see"),
     "constraints": ("the physical route, which has no alternative for Serbia and few for Hungary",
                     "EU law on transit levies",
                     "Bulgaria's own storage at Chiren, which is small"),
     "instruments": ("XNGUSD", "XBRUSD"),
     "counterparties": ("Gazprom Export", "the Hungarian and Serbian buyers",
                        "the Greek interconnector and the Krk terminal as the alternatives"),
     "observables": ("ENTSOG physical flows at the entry and exit points",
                     "the transit-fee legislation", "the Chiren storage level",
                     "the Krk send-out as the substitute"),
     "impact": "a route decision here reprices European gas at the margin and is the reason "
               "Hungary's supply politics differ from Poland's and Czechia's; Henry Hub is a "
               "weak proxy for it and this pack says so on every gas edge",
     "persistence": "the cut-off was permanent; the levy lasted a quarter",
     "falsifier": "a transit or cut-off event that moves XNGUSD no more than the matched control "
                  "is the EXPECTED result, because the true leg is the European hub and not "
                  "Henry Hub; a reading that does move it needs the European leg before it is "
                  "believed",
     "notes": "an honest weak edge: the pack refuses to promote it above HYPOTHESIS"},
    {"name": "CROATIA: the HNB, the Krk LNG terminal and the euro conversion of 2023",
     "holds": "the LNG regasification capacity at Omisalj and, until 2023, a tightly managed kuna",
     "forced_to": ("convert every kuna balance in the country at 7.53450 on 1 January 2023",
                   "expand Krk's capacity because Hungary, Slovenia and Slovakia need the route",
                   "hand monetary policy to the ECB on the same date"),
     "when": "the conversion was a single date; the terminal's capacity steps are dated decisions",
     "information": ("the terminal's booking book before it is published",
                     "the conversion mechanics before the households saw them"),
     "constraints": ("a tourism economy whose receipts are seasonal and were in euros already",
                     "the terminal's physical size", "the Adriatic pipeline's capacity inland"),
     "instruments": ("EURUSD", "XNGUSD"),
     "counterparties": ("the Hungarian and Slovak buyers booking Krk capacity",
                        "the ECB", "the Croatian banks, mostly Italian and Austrian owned"),
     "observables": ("the conversion regulation and its date", "the terminal's booked capacity",
                     "the send-out series", "the HICP convergence path before entry"),
     "impact": "the kuna ceased to exist, which removed an instrument and re-priced the regional "
               "convergence trade; the terminal changed Hungary's and Slovakia's supply options "
               "and therefore their negotiating position on the TurkStream route",
     "persistence": "permanent for the currency; per-contract for the terminal",
     "falsifier": "if the Croatian spread and the regional convergence basket showed no "
                  "measurable path into 2023-01-01 relative to the same window a year earlier, "
                  "then a pre-announced accession date prices nothing and CEE-HR-A is wrong "
                  "about the mechanism it shares with CEE-BG-A",
     "notes": "the completed natural experiment the Bulgarian one is measured against"},
    {"name": "SERBIA: the National Bank of Serbia and the Belgrade political calendar",
     "holds": "about EUR 28bn of reserves and a dinar it holds within a few hundredths of a "
              "chosen level by near-daily intervention",
     "forced_to": ("intervene on most trading days to keep EUR/RSD where it wants it",
                   "publish the intervention volumes monthly, which few managed floats do",
                   "hold the line through the Kosovo and Republika Srpska escalations, which are "
                   "dated, public and recurrent"),
     "when": "daily intervention; monthly Executive Board meetings; the flashpoints are dated "
             "events (the Banjska attack of 2023-09-24, the Kosovo dinar restriction effective "
             "2024-02-01, the recurring Republika Srpska secession votes)",
     "information": ("the banks' FX orders before the market",
                     "the political calendar, which it shares with the government"),
     "constraints": ("an EU accession process that constrains the policy it can run",
                     "a euroised economy where most household savings are already in euros",
                     "reserves that must also cover the euroisation"),
     "instruments": ("EURHUF", "EUSTX50"),
     "counterparties": ("the Serbian banks", "the EU and the IMF",
                        "the holders of Serbian Eurobonds, who price the flashpoints"),
     "observables": ("the published intervention volumes", "the reserve level",
                     "the Serbian CDS and bond spread on flashpoint dates",
                     "the EU accession chapter openings"),
     "impact": "the dinar does not move, so a Balkan escalation prices in the Serbian and "
               "regional spread and, at the margin, in the European risk complex; the effect on "
               "an executable instrument is small and this pack expects it to be",
     "persistence": "days per escalation; the accession process is a decade",
     "falsifier": "flashpoint dates show no abnormal move on EURHUF or EUSTX50 against the "
                  "matched weekday control -- which is the expected result, and the pack records "
                  "it rather than hiding an absent effect behind a narrative",
     "notes": "carried for completeness of the regional actor map, not for executable strength"},
    {"name": "SLOVAKIA, CZECHIA AND HUNGARY: the German OEMs' assembly plants and their tiers",
     "holds": "Slovakia's four car plants, Czechia's three and Hungary's four, plus the battery "
              "capacity being built at Debrecen and Goed",
     "forced_to": ("build to a German order book they do not control",
                   "stop lines when a tier-one supplier or a wiring-harness plant stops, which "
                   "is what the 2022 Ukrainian harness interruption proved",
                   "pay the region's power price, which is set on HUPX, OPCOM and OTE"),
     "when": "monthly production statistics; the model-year changeover shutdowns in July and "
             "August are a scheduled and large seasonal",
     "information": ("the order book weeks before the statistics office publishes",
                     "their own supplier stoppages in real time"),
     "constraints": ("German demand", "the power price", "the labour supply, which is tight",
                     "the EU emissions timetable that is reshaping the model mix"),
     "instruments": ("GER40", "EUSTX50", "EURCZK"),
     "counterparties": ("the German parents", "the tier-one suppliers across the region",
                        "the power exchanges"),
     "observables": ("the national automotive production series",
                     "industrial production in Czechia, Slovakia and Hungary",
                     "the German new-orders print", "the day-ahead power price"),
     "impact": "Slovakia produces more cars per head than any country on earth, so its "
               "production series is the cleanest single read of the chain's utilisation; CEE "
               "industrial production leads the European auto complex's earnings by weeks",
     "persistence": "one production cycle; the shutdown seasonal repeats every year",
     "falsifier": "if CEE automotive production carries no information about GER40 or EUSTX50 "
                  "beyond what the German new-orders print already carries, then the region is "
                  "a pass-through with no lead and the second-derivative claim is empty",
     "notes": "the two-lane order: the plants' owners are actors; no share CFD enters a tuple"},
    {"name": "THE REGION: the foreign banks that own the CEE banking systems",
     "holds": "Erste, Raiffeisen, UniCredit, Intesa, KBC, OTP and NLB between them own most of "
              "the banking assets in every country in this pack",
     "forced_to": ("fund local books in local currency and hedge the mismatch",
                   "absorb whatever the national parliaments and courts impose on the legacy FX "
                   "loan books",
                   "consolidate or exit under supervisory pressure, which is how the Vienna "
                   "Initiative worked and how the Russian exits worked after 2022"),
     "when": "quarterly results; the legal events are dated and irregular",
     "information": ("their own local loan books and deposit flows before any statistic",
                     "the group treasury's cross-border funding intentions"),
     "constraints": ("ECB supervision at the group level and national supervision below it",
                     "the retail legal risk the CHF book created",
                     "the capital cost of cross-border funding"),
     "instruments": ("EURHUF", "EURCZK", "CHFHUF", "EUSTX50"),
     "counterparties": ("the national central banks", "the households and firms they lend to",
                        "the parent shareholders"),
     "observables": ("the ECB consolidated banking data", "the quarterly provisions",
                     "the cross-border funding series in the BIS locational statistics"),
     "impact": "the cross-border funding channel is why a euro-area funding shock arrives in "
               "Budapest and Bucharest as a credit shock rather than as an FX shock, and it is "
               "the reason the region's crosses co-move more than their macros do",
     "persistence": "the funding channel is structural; the legal events are episodic",
     "falsifier": "if the CEE crosses' co-movement is fully explained by a common euro or "
                  "risk-appetite factor with no residual loading on the foreign-bank funding "
                  "series, then the ownership channel is a story about an already-known beta",
     "notes": "an actor whose instruments are all crosses, because its own shares are event-lane"},
)

# --------------------------------------------------------------------------- domains
DOMAINS: tuple[dict[str, Any], ...] = (
    {"id": "CEE-CZ-A", "title": "CNB decisions measured against the bank's OWN published path",
     "objects": ("the eight scheduled Bank Board decisions and their vote splits",
                 "the four forecast meetings and the implied rate path each publishes",
                 "the fan chart's width, which is the bank's own stated uncertainty",
                 "the FRA curve's drift between meetings"),
     "conditions": ("forecast meeting or not -- the two are not one sample",
                    "the direction of the PATH revision, separately from the rate decision",
                    "the era: the 2021-22 hiking cycle, the 7% plateau, the 2024-25 easing"),
     "instruments": ("EURCZK", "USDCZK", "EUSTX50"),
     "controls": ("the same window on the eight nearest non-meeting weekdays",
                  "the same window on MNB decision days, which separates 'a CEE bank decided' "
                  "from 'the CNB decided'",
                  "the same window on ECB Governing Council days, which separates a Czech "
                  "surprise from a euro-area one",
                  "the 14:30 Prague fixing on non-meeting days, because the fix and the "
                  "announcement share a minute"),
     "notes": "the only pack in the department where the expectation is PUBLISHED rather than "
              "surveyed; a surprise against the path and a surprise against a poll are two "
              "different quantities and must never be pooled"},
    {"id": "CEE-CZ-B", "title": "The koruna floor of 2013-2017 and its exit as a regime break",
     "objects": ("the introduction on 2013-11-07 and the exit on 2017-04-06",
                 "the truncated EUR/CZK distribution while the commitment stood",
                 "the reserve build in ARAD as the floor's running cost",
                 "the post-exit unwind of the long-koruna positions"),
     "conditions": ("inside the commitment, before it, or after it",
                    "distance from 27.00 while inside",
                    "whether the month carried a published intervention volume"),
     "instruments": ("EURCZK", "USDCZK"),
     "controls": ("the two years BEFORE the floor as the explicit pre-period",
                  "EURHUF over the identical windows, a CEE cross with no floor",
                  "EURCHF across the SNB's own 2011-2015 floor and its exit, the same mechanism "
                  "in another currency, which separates 'a floor' from 'the koruna'"),
     "notes": "a declared regime break with a known date on both ends; any moment of EURCZK "
              "computed across either date is a mixture of two distributions"},
    {"id": "CEE-HU-A", "title": "MNB Monetary Council decisions and the forint's asymmetry",
     "objects": ("the twelve rate-setting decisions a year and their minutes",
                 "the corridor width, which the Council moves without moving the base rate",
                 "the non-resident government-bond holding series around each decision"),
     "conditions": ("inside or outside the 2022-23 quick-tender era",
                    "the sign of the surprise, because the reaction is asymmetric",
                    "whether an EU conditionality decision was pending"),
     "instruments": ("EURHUF", "USDHUF", "CHFHUF", "GBPHUF"),
     "controls": ("the same window on the nearest non-meeting Tuesdays",
                  "the same window on CNB decision days, the cross-country control",
                  "the same window on EURCZK, which has a decision on a different day"),
     "notes": "the Council's own dates are the wrong clock inside the quick-tender era, which is "
              "why CEE-HU-B exists as a separate domain rather than as a condition here"},
    {"id": "CEE-HU-B", "title": "The one-day deposit quick tender: an administered two-rate regime",
     "objects": ("the 2022-10-14 introduction at 18% against a 13% base rate",
                 "the daily tender rate, allotment and bid-to-cover",
                 "the gap between the tender rate and the base rate, which IS the regime",
                 "the convergence in steps from 2023-05-23 to 2023-09-26"),
     "conditions": ("era: single-rate before, two-rate during, single-rate after",
                    "the size of the gap in basis points",
                    "whether the day carried a tender at all"),
     "instruments": ("EURHUF", "CHFHUF", "USDHUF"),
     "controls": ("the SAME instrument outside the era -- the cleanest control available, "
                  "because it is the same country, the same cross and the same broker",
                  "EURCZK over the identical windows, a CEE cross with one policy rate "
                  "throughout",
                  "the Monetary Council dates inside the era, which should carry LESS reaction "
                  "than outside it if the regime really moved the clock"),
     "notes": "an administered regime measured against itself; the falsifier is that the Council "
              "dates react identically inside and outside, which would kill the whole domain"},
    {"id": "CEE-HU-C", "title": "EU rule-of-law conditionality and the frozen cohesion funds",
     "objects": ("the 2022-12 suspension and the 2023-12 partial release",
                 "the quarterly milestone assessments between them",
                 "the European Council summit calendar, which is public and creates the "
                 "expectation the decision surprises against",
                 "the de-commitment deadlines, which are a hard clock"),
     "conditions": ("release, suspension or no decision",
                    "whether a summit fell in the same week",
                    "the non-resident bond holding level going in"),
     "instruments": ("EURHUF", "USDHUF"),
     "controls": ("the same windows on EURCZK, a neighbour with no conditionality dispute",
                  "the summit dates with no Hungarian file on the agenda",
                  "a randomised-date null drawn from the same quarters"),
     "notes": "the only political-legal forced flow in this pack; the money is real, dated and "
              "large enough to matter to a small open economy's external position"},
    {"id": "CEE-HU-D", "title": "The forint as a carry currency across four funding legs",
     "objects": ("GBPHUF, AUDHUF and NZDHUF as receive-forint legs at different funding rates",
                 "the non-resident bond holding series as the position's footprint",
                 "the unwind episodes, which are the object -- carry pays slowly and unwinds "
                 "fast"),
     "conditions": ("the carry differential bucket",
                    "the global risk state, because a carry unwind is a risk event first",
                    "the era, since the differential was 18% for eleven months of it"),
     "instruments": ("EURHUF", "GBPHUF", "AUDHUF", "NZDHUF"),
     "controls": ("EURPLN over the identical windows as the NEIGHBOUR control -- Poland's zloty "
                  "is the other CEE carry leg and is the `pl` pack's ground, borrowed here for "
                  "exactly one purpose: to ask whether an effect is the forint or is CEE beta",
                  "the same legs against a G10 funder with no CEE exposure",
                  "the matched weekday and hour control on each cross"),
     "notes": "the one place EURPLN appears in this pack, as a control and never as an "
              "executable instrument; the `pl` pack owns it"},
    {"id": "CEE-XX-A", "title": "The Swiss franc mortgage legacy as a political reflex",
     "objects": ("the Hungarian conversion statutes of 2014-15 and the fixed conversion rate",
                 "the Croatian conversion law of 2015 and the Supreme Court rulings from 2019",
                 "the Serbian conversion law of 2019 and the Romanian Law 77/2016",
                 "the residual CHF loan stock in ECB banking data"),
     "conditions": ("before or after each jurisdiction's conversion",
                    "the size of the residual stock",
                    "whether a dated court ruling fell in the window"),
     "instruments": ("CHFHUF", "EURCHF"),
     "controls": ("CHFHUF's behaviour implied by EURCHF times EURHUF, which is the no-reflex "
                  "null: any residual is the domain's claim",
                  "CHFSEK and CHFNOK over the same franc shocks, CHF crosses with no retail "
                  "mortgage legacy at all",
                  "the same windows before 2008, when the loans were being written rather than "
                  "converted"),
     "notes": "a balance-sheet channel, not a haven channel; the statutes are dated primary texts"},
    {"id": "CEE-RO-A", "title": "The NBR's administered leu and where the suppressed risk goes",
     "objects": ("the daily reference rate's step structure",
                 "the realised volatility of EUR/RON against its CEE siblings",
                 "the reserve level and the interbank liquidity the NBR rations",
                 "the Romanian bond spread, which carries what the FX rate is not allowed to"),
     "conditions": ("distance from the current band's apparent centre",
                    "whether a re-basing step fell in the window",
                    "the political calendar, since the 2024-25 election turmoil moved the band"),
     "instruments": ("EURHUF", "EURCZK", "WHEAT"),
     "controls": ("EURHUF and EURCZK on the identical days as the UNMANAGED siblings -- the "
                  "suppression is only visible as a ratio to them",
                  "the Bulgarian board rate, which is the fully-administered extreme of the same "
                  "axis and should show zero",
                  "the Romanian bond spread as the migration destination: if risk is suppressed "
                  "in FX it must appear here or the mechanism is wrong"),
     "notes": "RON is absent from this broker; every cell here is a transmission cell and is "
              "compiled on the siblings, never on the leu"},
    {"id": "CEE-RO-B", "title": "Constanta, the Danube and the Black Sea grain corridor",
     "objects": ("monthly Constanta grain throughput",
                 "the daily lower-Danube gauge readings and the draught-restriction notices",
                 "the Romanian and Bulgarian harvest and export pace",
                 "the Ukrainian solidarity-lane volume through the same port"),
     "conditions": ("restriction in force or not",
                    "harvest season or carry-out season",
                    "whether the Black Sea maritime corridor was open"),
     "instruments": ("WHEAT", "CORN", "SOYBEAN"),
     "controls": ("the same calendar windows in years with no draught restriction",
                  "the Rhine at Kaub over the same weeks, which is the OTHER European river "
                  "constraint and separates 'European low water' from 'the Danube'",
                  "a randomised-date null on the restriction notices"),
     "notes": "the strongest outward edge in the pack: a counted physical flow with a dated "
              "constraint and a published gauge"},
    {"id": "CEE-BG-A", "title": "The currency board and the euro-accession clock",
     "objects": ("the board's weekly issue-department balance sheet",
                 "the ERM II entry of 2020-07-10 and the convergence reports after it",
                 "the Council decision of 2025-07-08 and the entry date of 2026-01-01",
                 "the Bulgarian bond spread's convergence into the date"),
     "conditions": ("before ERM II, inside it, or after the decision",
                    "whether the window contained a convergence report",
                    "the harmonised inflation criterion's distance from the reference value"),
     "instruments": ("EURUSD", "EURHUF"),
     "controls": ("Croatia's 2023 accession over the identical relative windows -- a COMPLETED "
                  "version of the same mechanism, which is the best control this pack owns",
                  "the Romanian spread over the same windows, a neighbour with no date",
                  "the matched weekday control on the executable legs"),
     "notes": "a structural break with a pre-announced date, which is the rarest object in FX "
              "research and is why the domain exists despite BGN being unquotable"},
    {"id": "CEE-BG-B", "title": "TurkStream, the Balkan Stream and the 2022 cut-off",
     "objects": ("the 2022-04-27 Gazprom cut-off to Bulgaria",
                 "the Bulgarian transit levy of late 2023 and its withdrawal",
                 "the daily ENTSOG physical flows at the Bulgarian and Serbian points",
                 "the Greek interconnector and Chiren storage as the substitutes"),
     "conditions": ("flow interrupted or normal",
                    "levy in force or not",
                    "the season, because storage and demand are seasonal"),
     "instruments": ("XNGUSD", "XBRUSD"),
     "controls": ("the same windows on days with no transit event",
                  "the Krk send-out series as the substitution channel: a route event that does "
                  "not move the substitute is not a supply event",
                  "the matched weekday control, and the honest note that the true leg is the "
                  "European hub and Henry Hub is a weak proxy"),
     "notes": "every reading in this domain is declared a weak-proxy reading; the pack expects "
              "an absent executable effect and records it rather than dressing it up"},
    {"id": "CEE-HR-A", "title": "Croatia's euro entry and the Adriatic energy route",
     "objects": ("the 2023-01-01 conversion at 7.53450 and the Schengen entry the same day",
                 "the Krk LNG terminal's booked capacity and send-out",
                 "the pre-entry convergence of the Croatian spread",
                 "the seasonal euro receipts of a tourism economy"),
     "conditions": ("before or after the entry date",
                    "the tourist season",
                    "whether Hungarian or Slovak capacity bookings changed in the window"),
     "instruments": ("EURUSD", "XNGUSD"),
     "controls": ("Slovenia's 2007 and Slovakia's 2009 entries as the older completed cases",
                  "the Serbian spread over the same windows, a neighbour with no accession date",
                  "the same seasonal windows in the kuna years"),
     "notes": "the completed experiment CEE-BG-A is measured against, and the reason the "
              "accession mechanism is a hypothesis with evidence rather than a guess"},
    {"id": "CEE-RS-A", "title": "The Balkan flashpoints and the managed dinar",
     "objects": ("the Banjska attack of 2023-09-24 and the escalations around it",
                 "the Kosovo dinar restriction effective 2024-02-01",
                 "the recurring Republika Srpska secession votes and the 2025 escalation",
                 "the EU accession chapter openings, which are dated and rare"),
     "conditions": ("escalation or de-escalation",
                    "whether an EU or US sanction decision fell in the window",
                    "the NBS's published intervention volume that month"),
     "instruments": ("EURHUF", "EUSTX50"),
     "controls": ("the matched weekday control on both instruments",
                  "the Serbian CDS and bond spread, where the risk actually prices",
                  "the same windows on EURCZK, far enough from the Balkans to be a placebo"),
     "notes": "the expected result is no executable move; the domain exists so that the absence "
              "is MEASURED rather than assumed, and so the desk stops re-asking it"},
    {"id": "CEE-SK-A", "title": "The German automotive chain and its CEE second derivative",
     "objects": ("Slovak, Czech and Hungarian automotive production, monthly",
                 "the July-August model-year shutdown seasonal",
                 "the German new-orders print the region builds against",
                 "the day-ahead power price the plants and their aluminium tiers pay"),
     "conditions": ("shutdown season or not",
                    "the power-price regime, since 2022 changed the tiers' cost structure",
                    "whether a supply interruption (the 2022 wiring-harness stop) was in force"),
     "instruments": ("GER40", "EUSTX50", "EURCZK"),
     "controls": ("the German new-orders print itself: any CEE lead must survive controlling "
                  "for it, or the region is a pass-through and not a signal",
                  "the same months in years with no shutdown disruption",
                  "Spanish and French automotive production, the other European assembly bases"),
     "notes": "Slovakia's per-capita output is the highest in the world, which is what makes its "
              "series a utilisation read rather than a national statistic"},
    {"id": "CEE-XX-B", "title": "Two Easters, eight calendars and the asymmetric session",
     "objects": ("the weekdays Bucharest, Sofia and Belgrade are shut and Prague, Budapest and "
                 "Zagreb are open",
                 "the mirror image in the Western-rite weeks",
                 "the Czech 28 September, 28 October and 17 November, the Hungarian 15 March, "
                 "20 August and 23 October, the Bulgarian 3 March, 6 September and 22 September, "
                 "the Croatian 30 May and the Serbian 15-16 February",
                 "the coinciding years, where the Easter half of the sample vanishes"),
     "conditions": ("how many jurisdictions are closed that day",
                    "divergence year or coinciding year",
                    "whether the day is adjacent to a weekend, which creates a bridge"),
     "instruments": ("EURHUF", "EURCZK", "EUSTX50"),
     "controls": ("the COINCIDING years (2025) as the placebo: the same seasonal position in the "
                  "year with no calendar asymmetry at all",
                  "the matched weekday control on each instrument",
                  "the days when ALL eight are closed, which should show a different signature "
                  "from a one-country closure if the mechanism is missing liquidity"),
     "notes": "the pack's own calendar, computed from two computations rather than typed; the "
              "asymmetry is arithmetic and is knowable years ahead"},
)

# --------------------------------------------------------------------------- the pack's miners
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    {"name": "cee_cnb_mnb_decision_windows", "domain_ids": ("CEE-CZ-A", "CEE-HU-A"),
     "kind": "event", "cadence_s": 86400.0, "steerable": False, "wired": False,
     "entry": "countries.cee_balkans.miners:cnb_mnb_decision_windows",
     "needs": ("CNB and MNB decision dates", "EURCZK, EURHUF, USDCZK, USDHUF H1 bars"),
     "notes": "NOT WIRED. Two SEPARATE samples on two instruments, each carrying the other "
              "country's decision days as its cross-country control"},
    {"name": "cee_czk_floor_regime_break", "domain_ids": ("CEE-CZ-B",), "kind": "event",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.cee_balkans.miners:czk_floor_regime_break",
     "needs": ("the 2013-11-07 and 2017-04-06 dates", "EURCZK, USDCZK H1 bars"),
     "notes": "NOT WIRED. The two declared break dates as events, with the pre-floor window run "
              "as the explicit control sample"},
    {"name": "cee_mnb_quick_tender_era", "domain_ids": ("CEE-HU-B", "CEE-XX-A"), "kind": "macro",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.cee_balkans.miners:mnb_quick_tender_era",
     "needs": ("the 2022-10-14 to 2023-09-26 era bounds and the MNB dates",
               "EURHUF, CHFHUF H1 bars"),
     "notes": "NOT WIRED. The two-rate era measured against the single-rate era on the same "
              "instrument, which is the same country as its own control"},
    {"name": "cee_orthodox_vs_western_easter", "domain_ids": ("CEE-XX-B",), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.cee_balkans.miners:orthodox_vs_western_easter",
     "needs": ("orthodox_only_days and western_only_days", "EURHUF, EURCZK, EUSTX50 H1 bars"),
     "notes": "NOT WIRED. The divergence weekdays as the sample and the coinciding years as the "
              "placebo; both halves of the asymmetry are run"},
    {"name": "cee_transmission_seeds",
     "domain_ids": ("CEE-HU-C", "CEE-HU-D", "CEE-RO-A", "CEE-RO-B", "CEE-BG-A", "CEE-BG-B",
                    "CEE-HR-A", "CEE-RS-A", "CEE-SK-A"), "kind": "transfer",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.cee_balkans.miners:transmission_seeds",
     "needs": ("TRANSMISSION_EDGES_SEED",),
     "notes": "NOT WIRED. The pack's map as HYPOTHESIS discoveries, deduplicated by the registry"},
)
MINER_DOMAINS: dict[str, tuple[str, ...]] = {
    "central_bank_surprise": ("CEE-CZ-A", "CEE-HU-A"),
    "release_surprise": ("CEE-CZ-A", "CEE-SK-A"),
    "calendar_settlement": ("CEE-HU-A", "CEE-XX-B"),
    "holiday_liquidity": ("CEE-XX-B",),
    "positioning": ("CEE-HU-D",),
    "carry_funding": ("CEE-HU-D", "CEE-HU-B"),
    "corporate_flow": ("CEE-SK-A", "CEE-RO-B"),
    "institutional_flow": ("CEE-HU-C", "CEE-BG-A", "CEE-HR-A"),
    "equity_mechanics": ("CEE-SK-A",),
    "derivatives_expiry": ("CEE-HU-A",),
    "failure": ("CEE-BG-B", "CEE-RS-A"),
    "residual": ("CEE-RO-A", "CEE-XX-A"),
    "transfer": ("CEE-RO-B", "CEE-BG-B"),
    "scouts": ("CEE-CZ-B", "CEE-XX-A"),
}

# --------------------------------------------------------------------------- transmission
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    {"id": "CEE-E1", "source": "CNB Bank Board decision and the published rate-path revision",
     "target": "EURCZK", "targets": ("EURCZK", "USDCZK"), "to_country": "global", "sign": "+",
     "mechanism": "a policy surprise measured against the bank's OWN published path reprices "
                  "the koruna curve and the cross within the minute; the path revision at a "
                  "forecast meeting is the larger of the two shocks",
     "horizon": "0 to 8 hours", "horizon_class": "intraday", "lag_days": 0.0,
     "actor": "the Czech National Bank Bank Board",
     "constraint": "eight scheduled meetings a year, announced at 14:30 Prague",
     "flow": "rate repricing", "condition": "forecast meetings and non-forecast meetings kept "
                                            "as separate samples",
     "control": "MNB decision days on EURCZK; the eight nearest non-meeting weekdays",
     "falsifier": "the decision-day window matches the matched weekday control or matches the "
                  "MNB's own decision days on the same cross",
     "evidence": "HYPOTHESIS"},
    {"id": "CEE-E2", "source": "The koruna floor's introduction (2013-11-07) and exit (2017-04-06)",
     "target": "EURCZK", "targets": ("EURCZK", "USDCZK"), "to_country": "global", "sign": "-",
     "mechanism": "an unlimited one-sided offer truncates the distribution while it stands and "
                  "releases three and a half years of suppressed adjustment when it goes",
     "horizon": "the break day plus the multi-week unwind", "horizon_class": "multi_day",
     "lag_days": 0.0, "actor": "the CNB's FX desk under the exchange-rate commitment",
     "constraint": "the commitment was absolute while it stood", "flow": "intervention",
     "condition": "inside, before or after the commitment -- never pooled",
     "control": "the two pre-floor years; EURHUF over identical windows; the SNB's own floor exit",
     "falsifier": "EURCZK's moments inside the commitment are indistinguishable from the "
                  "pre-floor period, which would mean the floor never bound",
     "evidence": "MEASURED_ELSEWHERE"},
    {"id": "CEE-E3", "source": "MNB one-day deposit quick-tender rate and allotment",
     "target": "EURHUF", "targets": ("EURHUF", "USDHUF"), "to_country": "global", "sign": "-",
     "mechanism": "for eleven months the tender rate, not the base rate, cleared forint "
                  "overnight liquidity; the gap between the two is the regime and its "
                  "convergence is the unwind",
     "horizon": "0 to 3 sessions", "horizon_class": "intraday", "lag_days": 0.0,
     "actor": "the MNB's quick-tender desk",
     "constraint": "a forint that had traded through 430 and a base rate held at 13%",
     "flow": "administered liquidity pricing",
     "condition": "2022-10-14 to 2023-09-26 only; the convergence steps are their own events",
     "control": "the same cross outside the era; EURCZK over identical windows; the Monetary "
                "Council dates inside the era",
     "falsifier": "EURHUF's response to Council dates is the same size inside and outside the "
                  "era, which would mean the two-rate regime changed no reaction function",
     "evidence": "HYPOTHESIS"},
    {"id": "CEE-E4", "source": "CHF conversion statutes and court rulings in Hungary, Croatia, "
                               "Serbia and Romania",
     "target": "CHFHUF", "targets": ("CHFHUF", "EURCHF"), "to_country": "global", "sign": "+",
     "mechanism": "a franc move in this region is a household solvency event that produces "
                  "legislation, so the cross carries a political reflex the arithmetic of "
                  "EURCHF times EURHUF does not",
     "horizon": "1 to 8 weeks", "horizon_class": "multi_day", "lag_days": 5.0,
     "actor": "the CHF-mortgage households and the foreign-owned banks that lent to them",
     "constraint": "household solvency is a political limit, not an economic one",
     "flow": "balance-sheet and legal risk",
     "condition": "dated statutes and rulings only, never a continuous narrative",
     "control": "the EURCHF x EURHUF synthetic as the no-reflex null; CHFSEK and CHFNOK over the "
                "same franc shocks",
     "falsifier": "CHFHUF carries no residual over the synthetic around franc shocks and around "
                  "the dated rulings, in which case the reflex is a story",
     "evidence": "HYPOTHESIS"},
    {"id": "CEE-E5",
     "source": "The NBR suppression of EUR/RON volatility and its step re-basings",
     "target": "EURHUF", "targets": ("EURHUF", "EURCZK"), "to_country": "global", "sign": "+",
     "mechanism": "risk the leu is not allowed to express migrates to the siblings and to the "
                  "Romanian spread; a re-basing step releases it in one jump",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "the National Bank of Romania's FX desk",
     "constraint": "finite reserves and a political preference for a stable leu",
     "flow": "administered FX", "condition": "re-basing dates and high-stress weeks only",
     "control": "the Bulgarian board rate as the fully-administered extreme; the Romanian bond "
                "spread as the migration destination",
     "falsifier": "EUR/RON's conditional volatility is no lower than EURHUF's and EURCZK's on "
                  "the same days, in which case nothing is being suppressed",
     "evidence": "HYPOTHESIS"},
    {"id": "CEE-E6", "source": "Lower-Danube draught restrictions and the Constanta export pace",
     "target": "WHEAT", "targets": ("WHEAT", "CORN"), "to_country": "global", "sign": "+",
     "mechanism": "barges that cannot load do not become vessels three weeks later; the Black "
                  "Sea basis widens before the futures move",
     "horizon": "2 to 8 weeks", "horizon_class": "multi_day", "lag_days": 14.0,
     "actor": "the Constanta exporters and the Danube barge operators",
     "constraint": "the navigable depth of the lower Danube, which is weather",
     "flow": "export logistics",
     "condition": "a restriction in force during the export season, not in carry-out",
     "control": "the Rhine at Kaub over the same weeks; years with no restriction",
     "falsifier": "a low-water episode not followed by a wider Constanta basis and a slower "
                  "export pace within a month",
     "evidence": "HYPOTHESIS"},
    {"id": "CEE-E7", "source": "Romanian and Bulgarian harvest and EU export-licence pace",
     "target": "CORN", "targets": ("CORN", "WHEAT", "SOYBEAN"), "to_country": "global",
     "sign": "-",
     "mechanism": "two of the EU's largest Black Sea exporters; a large harvest removes a swing "
                  "seller from the same basin Ukraine ships into",
     "horizon": "1 to 3 months", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "the Romanian and Bulgarian grain exporters",
     "constraint": "the crop and the storage it must clear before the next one",
     "flow": "export supply", "condition": "harvest-estimate surprises against the USDA balance",
     "control": "the French and Ukrainian export pace over the same weeks",
     "falsifier": "the harvest surprise carries no information for CORN or WHEAT beyond the "
                  "EU-wide balance already published",
     "evidence": "HYPOTHESIS"},
    {"id": "CEE-E8", "source": "TurkStream and Balkan Stream transit events and the 2022 cut-off",
     "target": "XNGUSD", "targets": ("XNGUSD", "XBRUSD"), "to_country": "global", "sign": "+",
     "mechanism": "a route decision on the only pipeline into south-east Europe reprices the "
                  "European hub; Henry Hub is a weak proxy and this edge says so",
     "horizon": "0 to 5 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "Bulgartransgaz, Srbijagas and Gazprom Export",
     "constraint": "no alternative route for Serbia and few for Hungary",
     "flow": "physical supply", "condition": "dated cut-off and levy events only",
     "control": "the Krk send-out as the substitution channel; non-event weeks",
     "falsifier": "no move on XNGUSD beyond the matched control, which is the EXPECTED result "
                  "and is recorded rather than hidden",
     "evidence": "HYPOTHESIS"},
    {"id": "CEE-E9", "source": "Krk LNG capacity bookings by Hungarian and Slovak buyers",
     "target": "XNGUSD", "targets": ("XNGUSD",), "to_country": "global", "sign": "-",
     "mechanism": "an Adriatic substitute for the Balkan route changes the buyers' negotiating "
                  "position and the region's marginal molecule",
     "horizon": "1 to 3 months", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "LNG Hrvatska and the Hungarian and Slovak shippers",
     "constraint": "the terminal's physical regasification capacity",
     "flow": "capacity booking", "condition": "dated capacity-auction results only",
     "control": "the Greek Revithoussa and Alexandroupolis bookings over the same windows",
     "falsifier": "booking events carry no information for the European gas complex beyond the "
                  "weather and storage already priced",
     "evidence": "HYPOTHESIS"},
    {"id": "CEE-E10", "source": "CEE automotive production and the German order book",
     "target": "GER40", "targets": ("GER40", "EUSTX50"), "to_country": "de", "sign": "+",
     "mechanism": "Slovak, Czech and Hungarian assembly is the German chain's utilisation "
                  "measured a tier upstream, and it publishes before the German earnings do",
     "horizon": "2 to 10 weeks", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "the German OEMs' CEE plants and their tiers",
     "constraint": "they build to an order book they do not control",
     "flow": "industrial output",
     "condition": "outside the July-August shutdown, which is a scheduled seasonal",
     "control": "the German new-orders print itself; Spanish and French assembly",
     "falsifier": "CEE production carries no information for GER40 beyond the German new-orders "
                  "print, which would make the region a pass-through rather than a lead",
     "evidence": "HYPOTHESIS"},
    {"id": "CEE-E11", "source": "EU conditionality decisions on Hungarian cohesion and RRF funds",
     "target": "EURHUF", "targets": ("EURHUF", "USDHUF"), "to_country": "global", "sign": "-",
     "mechanism": "roughly EUR 20bn released or withheld by dated decision is a real external "
                  "flow for a small open economy, and the summit calendar prices the expectation",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "the European Commission and the Hungarian government",
     "constraint": "the conditionality regulation and the de-commitment clock",
     "flow": "fiscal transfer", "condition": "decision dates and summit weeks only",
     "control": "EURCZK over identical windows; summits with no Hungarian file",
     "falsifier": "decision windows show no abnormal move on EURHUF against the matched control "
                  "and against EURCZK on the same days",
     "evidence": "HYPOTHESIS"},
    {"id": "CEE-E12", "source": "The euro-accession clock: Croatia 2023 and Bulgaria 2026",
     "target": "EURUSD", "targets": ("EURUSD", "EURHUF"), "to_country": "global", "sign": "+",
     "mechanism": "a pre-announced accession date removes a currency and compresses the regional "
                  "convergence spread on a schedule known years ahead",
     "horizon": "the twelve months into the date", "horizon_class": "multi_day", "lag_days": 0.0,
     "actor": "the accession authorities and the Council",
     "constraint": "the convergence criteria measured on the harmonised index",
     "flow": "convergence repricing",
     "condition": "the Council decision and the entry date as two separate events",
     "control": "Romania over the same windows, a neighbour with no date; Slovenia 2007 and "
                "Slovakia 2009 as the older completed cases",
     "falsifier": "the acceding spread's path into the date is indistinguishable from a "
                  "no-date neighbour's over the same window",
     "evidence": "MEASURED_ELSEWHERE"},
)

# --------------------------------------------------------------------------- policy eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    {"name": "the post-Lehman CEE crisis and the CHF mortgage shock", "start": "2008-09-15",
     "end": "2013-11-06",
     "regime": "the Vienna Initiative holds the foreign parent banks in place, the franc rises "
               "against every currency in the region, and the CHF household books that were "
               "written in the boom become a political object",
     "markers": ("2008-10-28 the Hungarian IMF/EU programme",
                 "2011-09-06 the SNB's own floor at 1.20, which caps the damage for four years",
                 "2011-09-29 Hungary's early-repayment scheme at a fixed rate"),
     "why_it_matters": "the CHF exposure every later conversion statute deals with is created "
                       "here; a franc statistic pooled across this era mixes the build-up with "
                       "the resolution",
     "status": "SETTLED"},
    {"name": "the koruna floor, the first half", "start": "2013-11-07", "end": "2015-01-14",
     "regime": "EUR/CZK truncated at 27.00 by unlimited CNB intervention while the SNB's own "
               "floor still holds at 1.20, so two European floors stand at once",
     "markers": ("2013-11-07 the commitment announced",
                 "2014 the reserve build begins in earnest"),
     "why_it_matters": "the only window in which the Czech and Swiss floors coexist, which is "
                       "the cleanest available comparison of two floor regimes",
     "status": "SETTLED"},
    {"name": "the franc shock, the forced conversions and the floor's last years",
     "start": "2015-01-15", "end": "2017-04-05",
     "regime": "the SNB abandons 1.20 and the franc jumps; Hungary's conversion settles the "
               "forint book at a fixed rate, Croatia legislates its own, and the koruna floor "
               "takes the whole speculative inflow onto the CNB's balance sheet",
     "markers": ("2015-01-15 the SNB abandons the 1.20 floor",
                 "2015-02 the Hungarian conversion settlement completes",
                 "2016-2017 the speculative koruna inflow reaches multiples of monthly GDP"),
     "why_it_matters": "CHFHUF before and after the conversion are different instruments: the "
                       "household exposure that made the cross reflexive is removed inside this "
                       "era and the political reflex is not",
     "status": "SETTLED"},
    {"name": "the post-floor float and the pandemic", "start": "2017-04-06", "end": "2021-06-21",
     "regime": "the koruna floats and the long positions unwind; the MNB runs an experimental "
               "toolkit at the lower bound; the pandemic cuts and then the reopening",
     "markers": ("2017-04-06 the commitment exited at an extraordinary meeting",
                 "2020-03 the pandemic cuts across the region",
                 "2020-07-10 Bulgaria and Croatia enter ERM II on the same day"),
     "why_it_matters": "the only clean float sample for the koruna before the inflation shock; "
                       "the ERM II entries start the accession clocks CEE-BG-A and CEE-HR-A run on",
     "status": "SETTLED"},
    {"name": "the CEE inflation shock and the Hungarian two-rate emergency",
     "start": "2021-06-22", "end": "2023-09-25",
     "regime": "the CNB to 7% and the MNB base rate to 13% with an 18% one-day deposit beside "
               "it; Gazprom cuts Bulgaria off; the EU freezes Hungarian cohesion funds; Croatia "
               "is cleared for the euro",
     "markers": ("2021-06-22 the MNB's first hike, the first in the EU",
                 "2022-04-27 the Gazprom cut-off to Bulgaria",
                 "2022-10-14 the one-day deposit quick tender at 18%",
                 "2022-12-12 the Council suspends Hungarian cohesion funds",
                 "2023-01-01 Croatia adopts the euro"),
     "why_it_matters": "the region's reaction functions are not exchangeable with any other "
                       "era's: Hungary's effective policy rate was set by an instrument the "
                       "Monetary Council did not vote on",
     "status": "SETTLED"},
    {"name": "disinflation, convergence and the Bulgarian accession", "start": "2023-09-26",
     "end": "2026-12-31",
     "regime": "the MNB's two rates converge at 13% and then fall together; the CNB eases from "
               "7% toward 3.5%; the EU releases part of the Hungarian envelope; Bulgaria's euro "
               "entry is decided and taken",
     "markers": ("2023-09-26 the quick-tender rate meets the base rate at 13%",
                 "2023-12-13 the partial release of Hungarian cohesion funds",
                 "2025-07-08 the Council decision on Bulgaria's euro entry",
                 "2026-01-01 Bulgaria's scheduled entry at 1.95583"),
     "why_it_matters": "the current regime; the Hungarian decision sample is single-rate again "
                       "and the Bulgarian accession is the live experiment",
     "status": "OPEN"},
)

ACCESS_CONSTRAINTS: tuple[dict[str, Any], ...] = (
    {"constraint": "no CEE currency in this pack is quoted by this broker except through the "
                   "HUF and CZK crosses",
     "measured": "data/universe/universe.json holds EURCZK, USDCZK and the five HUF crosses and "
                 "no RON, BGN, HRK or RSD symbol at all",
     "consequence": "Romanian, Bulgarian, Croatian and Serbian mechanisms terminate in a "
                    "Hungarian or Czech cross, a grain, a gas leg or a European index; the leu, "
                    "the lev, the kuna and the dinar are INPUTS and never cells"},
    {"constraint": "no CEE equity index has a CFD here",
     "measured": "PX, BUX, BET, SOFIX, CROBEX and BELEX15 are all absent from the registry",
     "consequence": "regional equity beta is read on EUSTX50 and GER40; the national indices are "
                    "transmission targets and the automotive production series is the object"},
    {"constraint": "the true gas leg is the European hub and the box quotes Henry Hub",
     "measured": "XNGUSD is the only gas symbol in the registry; CEGH, MGP and the Bulgarian and "
                 "Romanian balancing points are absent",
     "consequence": "every gas reading in CEE-BG-B and CEE-HR-A is declared a weak-proxy reading "
                    "and is never promoted above HYPOTHESIS on XNGUSD alone"},
    {"constraint": "the CNB and MNB announcement minutes are not always in the release",
     "measured": "the CNB press release carries a date and the CTK wire carries the minute; the "
                 "MNB publishes at 14:00 Budapest and the timestamp is on the page",
     "consequence": "a Czech decision cell is compiled on the wire stamp or declared UNMEASURED; "
                    "the 14:30 Prague fixing shares the minute and must be separated"},
    {"constraint": "the licensed terminals and the CTK wire forbid machine extraction",
     "measured": "their terms; registered machine_use_allowed=False in cee_licensed_terminals",
     "consequence": "the intraday CEE tick record is UNMEASURED; the ECB reference rates and the "
                    "national central banks' own fixings are the PIT record the pack uses"},
    {"constraint": "the MNB quick-tender allotment publishes after the tender clears",
     "measured": "the announcement is same-morning and the allotment is same-afternoon",
     "consequence": "a same-day window conditioned on the ALLOTMENT is not PIT-safe; only the "
                    "announcement is, and CEE-HU-B says so on every cell"},
)
INSTITUTIONAL_FLOW_SOURCES: tuple[str, ...] = (
    "non-resident holdings of Hungarian and Czech government bonds",
    "CNB monthly FX intervention volumes and reserves",
    "NBS Serbia published monthly intervention volumes",
    "ECB consolidated banking data on the residual CHF loan stock",
    "EU cohesion and RRF disbursement decisions")
SERIES: dict[str, str] = {
    "CEE_CZ_REPO": "CNB:repo_2w", "CEE_CZ_PATH": "CNB:implied_path",
    "CEE_CZ_INTERVENTION": "CNB:fx_intervention", "CEE_HU_BASE": "MNB:base_rate",
    "CEE_HU_ONEDAY": "MNB:one_day_deposit", "CEE_HU_NONRES": "AKK:nonresident_share",
    "CEE_RO_REF": "BNR:reference_rate", "CEE_BG_BOARD": "BNB:issue_department",
    "CEE_GAS_FLOW": "ENTSOG:physical_flow", "CEE_GRAIN": "CONSTANTA:grain_throughput",
    "CEE_DANUBE": "DANUBE:gauge_draught", "CEE_AUTO": "CEE:automotive_production",
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
        "mission": MISSION, "currency_regimes": CURRENCY_REGIMES, "mnb": MNB,
        "other_central_banks": OTHER_CENTRAL_BANKS, "jurisdictions": JURISDICTIONS,
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
    """The framework's HolidayRule shape: every closed weekday the eight calendars produce for
    2024-2026, plus the fixed month-days of the largest two jurisdictions as the recurring set."""
    dates = sorted({d.isoformat() for y in HOLIDAYS_RULE["years"] for d in market_holidays(y)})
    fixed = tuple(f"{m:02d}-{d:02d}"
                  for code in JURISDICTIONS for m, d, _ in FIXED_HOLIDAYS[code])
    return {"dates": tuple(dates), "fixed_md": tuple(dict.fromkeys(fixed)),
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
